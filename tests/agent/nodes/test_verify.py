from unittest.mock import MagicMock
from unittest.mock import patch as mock_patch

from agent.nodes.verify import verify_node
from agent.schemas import AgentState, Issue, Patch


def _issue():
    return Issue(
        file="a.py",
        line_start=1,
        line_end=2,
        severity="high",
        category="bug",
        title="t",
        description="d",
        suggestion="s",
        confidence=0.9,
        fixable=True,
    )


def test_lint_pass_no_test_runner_marks_verified_and_restores_file(tmp_path):
    a_path = tmp_path / "a.py"
    original = "def add(a, b):\n    return a + b\n"
    a_path.write_text(original, encoding="utf-8")

    issue = _issue()
    patch = Patch(
        issue=issue,
        file="a.py",
        original_snippet="return a + b",
        fixed_snippet="return a + b  # fixed",
        commit_message="fix: x",
    )

    def which_side_effect(name):
        return "/fake/ruff" if name == "ruff" else None

    def run_side_effect(cmd, cwd=None, capture_output=True, text=True, timeout=None):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with mock_patch("agent.nodes.verify.shutil.which", side_effect=which_side_effect), mock_patch(
        "agent.nodes.verify.subprocess.run", side_effect=run_side_effect
    ):
        state = AgentState(patches=[patch], workspace=str(tmp_path))
        new_state = verify_node(state)

    verified_patch = new_state.verified_patches[0]
    assert verified_patch.verified is True
    assert verified_patch.verify_error is None
    assert a_path.read_text(encoding="utf-8") == original


def test_test_failure_still_restores_file(tmp_path):
    a_path = tmp_path / "a.py"
    original = "def add(a, b):\n    return a + b\n"
    a_path.write_text(original, encoding="utf-8")

    issue = _issue()
    patch = Patch(
        issue=issue,
        file="a.py",
        original_snippet="return a + b",
        fixed_snippet="return a + b + 1",
        commit_message="fix: y",
    )

    def which_side_effect(name):
        return f"/fake/{name}" if name in ("ruff", "pytest") else None

    def run_side_effect(cmd, cwd=None, capture_output=True, text=True, timeout=None):
        result = MagicMock()
        if cmd[0] == "ruff":
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        elif cmd[0] == "pytest":
            result.returncode = 1
            result.stdout = "1 failed"
            result.stderr = ""
        return result

    with mock_patch("agent.nodes.verify.shutil.which", side_effect=which_side_effect), mock_patch(
        "agent.nodes.verify.subprocess.run", side_effect=run_side_effect
    ):
        state = AgentState(patches=[patch], workspace=str(tmp_path))
        new_state = verify_node(state)

    verified_patch = new_state.verified_patches[0]
    assert verified_patch.verified is False
    assert "tests failed" in verified_patch.verify_error
    # The critical invariant: even on failure, the real file is untouched.
    assert a_path.read_text(encoding="utf-8") == original
