from unittest.mock import patch as mock_patch

import agent.graph as graph_module
from agent.schemas import AgentState, Issue, Patch


def _issue():
    return Issue(
        file="a.py",
        line_start=1,
        line_end=1,
        severity="high",
        category="bug",
        title="t",
        description="d",
        suggestion="s",
        confidence=0.9,
        fixable=True,
    )


def test_no_issues_skips_fix_and_verify():
    visited = []

    def fake_fetch(state):
        return state.model_copy(update={"diff": "D"})

    def fake_analyze(state):
        return state.model_copy(update={"issues": []})

    def fail(name):
        def _f(state):
            raise AssertionError(f"{name} should not run")

        return _f

    def track_publish(state):
        visited.append("publish")
        return state

    with mock_patch.object(graph_module, "fetch_node", fake_fetch), mock_patch.object(
        graph_module, "agentic_analyze_node", fake_analyze
    ), mock_patch.object(graph_module, "fix_node", fail("fix")), mock_patch.object(
        graph_module, "verify_node", fail("verify")
    ), mock_patch.object(graph_module, "publish_node", track_publish):
        graph_module.build_graph().invoke(AgentState())

    assert visited == ["publish"]


def test_issues_without_patches_runs_fix_then_skips_verify():
    fix_ran = []
    issue = _issue()

    def fake_fetch(state):
        return state.model_copy(update={"diff": "D"})

    def fake_analyze(state):
        return state.model_copy(update={"issues": [issue]})

    def fake_fix(state):
        fix_ran.append(1)
        return state.model_copy(update={"patches": []})

    def fail(name):
        def _f(state):
            raise AssertionError(f"{name} should not run")

        return _f

    with mock_patch.object(graph_module, "fetch_node", fake_fetch), mock_patch.object(
        graph_module, "agentic_analyze_node", fake_analyze
    ), mock_patch.object(graph_module, "fix_node", fake_fix), mock_patch.object(
        graph_module, "verify_node", fail("verify")
    ), mock_patch.object(graph_module, "publish_node", lambda s: s):
        graph_module.build_graph().invoke(AgentState())

    assert fix_ran == [1]


def test_analyze_with_staged_patches_skips_fix_goes_to_verify():
    issue = _issue()
    patch = Patch(issue=issue, file="a.py", original_snippet="x", fixed_snippet="y", commit_message="fix: x")
    verify_ran = []

    def fake_fetch(state):
        return state.model_copy(update={"diff": "D"})

    def fake_analyze(state):
        return state.model_copy(update={"issues": [issue], "patches": [patch]})

    def fail(name):
        def _f(state):
            raise AssertionError(f"{name} should not run")

        return _f

    def fake_verify(state):
        verify_ran.append(1)
        return state.model_copy(
            update={"verified_patches": [p.model_copy(update={"verified": True}) for p in state.patches]}
        )

    with mock_patch.object(graph_module, "fetch_node", fake_fetch), mock_patch.object(
        graph_module, "agentic_analyze_node", fake_analyze
    ), mock_patch.object(graph_module, "fix_node", fail("fix")), mock_patch.object(
        graph_module, "verify_node", fake_verify
    ), mock_patch.object(graph_module, "publish_node", lambda s: s):
        result = graph_module.build_graph().invoke(AgentState())

    assert verify_ran == [1]
    assert result["verified_patches"][0].verified is True
