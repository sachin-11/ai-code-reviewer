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


def test_latency_summary_aggregates_across_reviews(postgres_conn):
    init_schema()

    with postgres_conn.cursor() as cur:
        cur.execute("DELETE FROM reviews WHERE repo_full_name = %s", (TEST_REPO,))
    postgres_conn.commit()

    reviews_repo.record_review(
        TEST_REPO, 1, "h1", "b1", [], 0, None, None,
        latency_seconds=10.0, iteration_count=2, hit_max_iterations=False,
        node_latencies={"fetch": 1.0, "analyze": 8.0},
    )
    reviews_repo.record_review(
        TEST_REPO, 2, "h2", "b2", [], 0, None, None,
        latency_seconds=30.0, iteration_count=6, hit_max_iterations=True,
        node_latencies={"fetch": 1.0, "analyze": 28.0},
    )

    summary = reviews_repo.get_latency_summary(TEST_REPO)
    assert summary["review_count"] == 2
    assert abs(summary["avg_latency_seconds"] - 20.0) < 1e-9
    assert abs(summary["max_latency_seconds"] - 30.0) < 1e-9
    assert abs(summary["avg_iteration_count"] - 4.0) < 1e-9
    assert summary["max_iteration_count"] == 6
    assert summary["hit_max_iterations_count"] == 1
    assert abs(summary["hit_max_iterations_rate"] - 0.5) < 1e-9

    history = reviews_repo.get_review_history(TEST_REPO)
    by_pr = {r["pr_number"]: r for r in history}
    assert by_pr[1]["node_latencies"] == {"fetch": 1.0, "analyze": 8.0}
    assert by_pr[2]["hit_max_iterations"] is True

    with postgres_conn.cursor() as cur:
        cur.execute("DELETE FROM reviews WHERE repo_full_name = %s", (TEST_REPO,))
    postgres_conn.commit()


def test_latency_summary_with_no_reviews_has_no_rate(postgres_conn):
    init_schema()
    summary = reviews_repo.get_latency_summary("org/no-latency-data-xyz")
    assert summary["review_count"] == 0
    assert summary["avg_latency_seconds"] is None
    assert summary["hit_max_iterations_rate"] is None
