import os
from unittest.mock import MagicMock
from unittest.mock import patch as mock_patch

import service.jobs as jobs


def test_dispatch_routes_to_correct_handler():
    fake_handler = MagicMock()
    with mock_patch.dict(jobs.JOB_HANDLERS, {"review_pr": fake_handler}):
        jobs.dispatch_job("review_pr", {"x": 1})
    assert fake_handler.call_args == (({"x": 1},), {})


def test_dispatch_unknown_type_does_not_crash():
    jobs.dispatch_job("totally_unknown_type", {})


def test_handle_review_pr_cleans_up_workspace_on_success():
    payload = {
        "pr_number": 12,
        "head_sha": "headsha",
        "base_sha": "basesha",
        "head_branch": "feature",
        "base_branch": "main",
        "repo_full_name": "org/repo",
    }

    with mock_patch("service.jobs.clone_workspace", return_value="/tmp/fake-ws") as mock_clone, mock_patch(
        "service.jobs.cleanup_workspace"
    ) as mock_cleanup, mock_patch("service.jobs.build_graph") as mock_build_graph, mock_patch(
        "service.jobs._record_review_history"
    ):
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "diff": "d",
            "issues": [],
            "verified_patches": [],
            "fix_pr_url": None,
            "cost_usd": 0.0,
        }
        mock_build_graph.return_value = mock_graph

        jobs.handle_review_pr(payload)

    assert os.environ.get("REPO_FULL_NAME") == "org/repo"
    assert mock_clone.call_args[0] == ("org/repo", "headsha", os.environ["GITHUB_TOKEN"])
    assert mock_cleanup.call_args[0] == ("/tmp/fake-ws",)


def test_handle_review_pr_cleans_up_workspace_even_if_graph_raises():
    payload = {
        "pr_number": 12,
        "head_sha": "headsha",
        "base_sha": "basesha",
        "head_branch": "feature",
        "base_branch": "main",
        "repo_full_name": "org/repo",
    }

    with mock_patch("service.jobs.clone_workspace", return_value="/tmp/fake-ws-2"), mock_patch(
        "service.jobs.cleanup_workspace"
    ) as mock_cleanup, mock_patch("service.jobs.build_graph") as mock_build_graph:
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = RuntimeError("LLM API blew up")
        mock_build_graph.return_value = mock_graph

        raised = None
        try:
            jobs.handle_review_pr(payload)
        except RuntimeError as exc:
            raised = exc

    assert raised is not None
    assert mock_cleanup.call_args[0] == ("/tmp/fake-ws-2",)


def test_maybe_sample_skips_when_review_id_is_none():
    with mock_patch("eval.judge.judge_online_sample") as mock_judge, mock_patch(
        "service.jobs.reviews_repo.record_eval_sample"
    ) as mock_record:
        jobs._maybe_sample_for_eval(None, "diff", [MagicMock()])
    assert not mock_judge.called
    assert not mock_record.called


def test_maybe_sample_skips_when_no_issues():
    with mock_patch("eval.judge.judge_online_sample") as mock_judge:
        jobs._maybe_sample_for_eval(1, "diff", [])
    assert not mock_judge.called


def test_maybe_sample_skips_when_random_draw_misses():
    with mock_patch("service.jobs.random.random", return_value=0.99), mock_patch(
        "eval.judge.judge_online_sample"
    ) as mock_judge:
        jobs._maybe_sample_for_eval(1, "diff", [MagicMock()])
    assert not mock_judge.called


def test_maybe_sample_judges_and_records_when_sampled():
    fake_issue = MagicMock()
    with mock_patch("service.jobs.random.random", return_value=0.0), mock_patch(
        "eval.judge.judge_online_sample",
        return_value={"results": [{"status": "valid"}, {"status": "false_positive"}]},
    ), mock_patch("service.jobs.reviews_repo.record_eval_sample") as mock_record:
        jobs._maybe_sample_for_eval(42, "the-diff", [fake_issue])

    assert mock_record.call_args[0][0] == 42
    assert mock_record.call_args[0][1] == 2
    assert mock_record.call_args[0][2] == 1


def test_maybe_sample_judge_failure_does_not_crash():
    with mock_patch("service.jobs.random.random", return_value=0.0), mock_patch(
        "eval.judge.judge_online_sample", side_effect=RuntimeError("judge API down")
    ), mock_patch("service.jobs.reviews_repo.record_eval_sample") as mock_record:
        jobs._maybe_sample_for_eval(42, "the-diff", [MagicMock()])
    assert not mock_record.called


def test_get_node_latencies_returns_empty_when_tracing_disabled():
    with mock_patch("service.jobs.tracing_enabled", return_value=False):
        assert jobs._get_node_latencies("run-1") == {}


def test_get_node_latencies_extracts_child_run_durations():
    from datetime import datetime, timedelta

    fetch_child = MagicMock(name="fetch")
    fetch_child.name = "fetch"
    fetch_child.start_time = datetime(2026, 1, 1, 0, 0, 0)
    fetch_child.end_time = datetime(2026, 1, 1, 0, 0, 2)

    analyze_child = MagicMock(name="analyze")
    analyze_child.name = "analyze"
    analyze_child.start_time = datetime(2026, 1, 1, 0, 0, 2)
    analyze_child.end_time = datetime(2026, 1, 1, 0, 0, 7, 500000)

    unfinished_child = MagicMock(name="publish")
    unfinished_child.name = "publish"
    unfinished_child.start_time = datetime(2026, 1, 1, 0, 0, 7)
    unfinished_child.end_time = None

    mock_run = MagicMock()
    mock_run.child_runs = [fetch_child, analyze_child, unfinished_child]

    mock_client = MagicMock()
    mock_client.read_run.return_value = mock_run

    with mock_patch("service.jobs.tracing_enabled", return_value=True), mock_patch(
        "langsmith.Client", return_value=mock_client
    ):
        result = jobs._get_node_latencies("run-1")

    assert result == {"fetch": 2.0, "analyze": 5.5}
    mock_client.read_run.assert_called_once_with("run-1", load_child_runs=True)


def test_get_node_latencies_returns_empty_on_error():
    with mock_patch("service.jobs.tracing_enabled", return_value=True), mock_patch(
        "langsmith.Client", side_effect=RuntimeError("API down")
    ):
        assert jobs._get_node_latencies("run-1") == {}


def test_daily_cost_cap_exceeded_true_when_over_cap():
    with mock_patch("service.jobs.reviews_repo.get_total_cost_since", return_value=jobs.DAILY_COST_CAP_USD):
        assert jobs._daily_cost_cap_exceeded() is True


def test_daily_cost_cap_exceeded_false_when_under_cap():
    with mock_patch("service.jobs.reviews_repo.get_total_cost_since", return_value=0.01):
        assert jobs._daily_cost_cap_exceeded() is False


def test_daily_cost_cap_exceeded_fails_open_on_error():
    with mock_patch(
        "service.jobs.reviews_repo.get_total_cost_since", side_effect=RuntimeError("db down")
    ):
        assert jobs._daily_cost_cap_exceeded() is False


def test_handle_review_pr_skips_and_notifies_when_cost_cap_exceeded():
    payload = {
        "pr_number": 12,
        "head_sha": "headsha",
        "base_sha": "basesha",
        "head_branch": "feature",
        "base_branch": "main",
        "repo_full_name": "org/repo",
    }

    with mock_patch("service.jobs._daily_cost_cap_exceeded", return_value=True), mock_patch(
        "service.jobs.clone_workspace"
    ) as mock_clone, mock_patch("service.jobs.github_client.post_pr_comment") as mock_comment, mock_patch(
        "service.jobs.build_graph"
    ) as mock_build_graph:
        jobs.handle_review_pr(payload)

    assert not mock_clone.called
    assert not mock_build_graph.called
    assert mock_comment.call_args[0][0] == 12
    assert "cost cap" in mock_comment.call_args[0][1]


def test_record_review_history_passes_new_fields_through():
    payload = {
        "repo_full_name": "org/repo",
        "pr_number": 12,
        "head_sha": "headsha",
        "base_sha": "basesha",
    }
    final_state = {
        "issues": [],
        "verified_patches": [],
        "fix_pr_url": None,
        "cost_usd": 0.05,
        "iteration_count": 3,
        "hit_max_iterations": True,
        "hit_cost_cap": False,
    }

    with mock_patch("service.jobs.reviews_repo.record_review", return_value=99) as mock_record:
        review_id = jobs._record_review_history(
            payload, final_state, "https://trace.url", 12.5, {"fetch": 2.0}
        )

    assert review_id == 99
    _, kwargs = mock_record.call_args
    assert kwargs["latency_seconds"] == 12.5
    assert kwargs["iteration_count"] == 3
    assert kwargs["hit_max_iterations"] is True
    assert kwargs["hit_cost_cap"] is False
    assert kwargs["node_latencies"] == {"fetch": 2.0}
