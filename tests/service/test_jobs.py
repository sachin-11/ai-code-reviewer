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
