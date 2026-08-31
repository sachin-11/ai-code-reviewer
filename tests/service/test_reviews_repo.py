from service import reviews_repo
from service.db import init_schema

TEST_REPO = "org/pytest-test-repo"


def test_record_review_and_read_back(postgres_conn):
    init_schema()

    with postgres_conn.cursor() as cur:
        cur.execute("DELETE FROM reviews WHERE repo_full_name = %s", (TEST_REPO,))
    postgres_conn.commit()

    issues = [
        {
            "fingerprint": "fp1",
            "file": "a.py",
            "category": "security",
            "severity": "critical",
            "title": "SQLi",
            "confidence": 0.95,
            "fixable": True,
        },
        {
            "fingerprint": "fp2",
            "file": "b.py",
            "category": "style",
            "severity": "low",
            "title": "unused import",
            "confidence": 0.7,
            "fixable": False,
        },
    ]

    review_id = reviews_repo.record_review(
        TEST_REPO, 42, "headsha", "basesha", issues, 1, "https://github.com/x/y/pull/9", None, cost_usd=0.05
    )
    assert isinstance(review_id, int)

    history = reviews_repo.get_review_history(TEST_REPO)
    assert len(history) == 1
    assert history[0]["pr_number"] == 42
    assert history[0]["issue_count"] == 2
    assert history[0]["severity_breakdown"] == {"critical": 1, "low": 1}

    stats = reviews_repo.get_false_positive_rate(TEST_REPO)
    assert stats == {"total": 2, "dismissed": 0, "false_positive_rate": 0.0}

    cost = reviews_repo.get_cost_summary(TEST_REPO)
    assert cost["review_count"] == 1
    assert abs(cost["total_cost_usd"] - 0.05) < 1e-9

    with postgres_conn.cursor() as cur:
        cur.execute("DELETE FROM reviews WHERE repo_full_name = %s", (TEST_REPO,))
    postgres_conn.commit()


def test_unknown_repo_returns_empty_history(postgres_conn):
    init_schema()
    assert reviews_repo.get_review_history("org/does-not-exist-xyz") == []


def test_eval_samples_aggregate_valid_rate(postgres_conn):
    init_schema()

    with postgres_conn.cursor() as cur:
        cur.execute("DELETE FROM reviews WHERE repo_full_name = %s", (TEST_REPO,))
    postgres_conn.commit()

    review_id = reviews_repo.record_review(TEST_REPO, 1, "h1", "b1", [], 0, None, None)

    reviews_repo.record_eval_sample(review_id, 4, 3, {"results": [{"title": "x", "status": "valid"}]})

    summary = reviews_repo.get_eval_quality_summary(TEST_REPO)
    assert summary["sample_count"] == 1
    assert summary["total_judged"] == 4
    assert abs(summary["valid_rate"] - 0.75) < 1e-9

    with postgres_conn.cursor() as cur:
        cur.execute("DELETE FROM reviews WHERE repo_full_name = %s", (TEST_REPO,))
    postgres_conn.commit()


def test_eval_quality_summary_with_no_samples_has_no_rate(postgres_conn):
    init_schema()
    summary = reviews_repo.get_eval_quality_summary("org/no-eval-samples-xyz")
    assert summary == {"sample_count": 0, "total_judged": 0, "valid_rate": None}
