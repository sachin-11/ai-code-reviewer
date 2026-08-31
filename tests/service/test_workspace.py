import os
import subprocess
from unittest.mock import MagicMock
from unittest.mock import patch as mock_patch

from service.workspace import _redact, cleanup_workspace, clone_workspace


def test_redact_hides_token():
    text = "clone failed at https://x-access-token:SECRET123@github.com/x/y.git"
    assert _redact(text, "SECRET123") == "clone failed at https://x-access-token:***@github.com/x/y.git"


def test_redact_empty_token_is_noop():
    assert _redact("some text", "") == "some text"


def test_successful_clone_and_checkout_then_cleanup():
    calls = []

    def fake_run(cmd, cwd=None, check=True, capture_output=True, text=True):
        calls.append((cmd, cwd))
        result = MagicMock()
        result.returncode = 0
        return result

    with mock_patch("service.workspace.subprocess.run", side_effect=fake_run):
        ws = clone_workspace("org/repo", "abc123sha", "TOKEN_XYZ")

    assert os.path.isdir(ws)
    assert "TOKEN_XYZ" in calls[0][0][3]
    assert calls[1][1] == ws
    assert calls[1][0][-1] == "abc123sha"

    cleanup_workspace(ws)
    assert not os.path.exists(ws)


def test_failed_clone_redacts_token_from_error_and_from_context():
    def fake_run(cmd, cwd=None, check=True, capture_output=True, text=True):
        raise subprocess.CalledProcessError(
            128,
            cmd,
            output="",
            stderr="fatal: could not read from "
            "'https://x-access-token:TOKEN_XYZ@github.com/org/repo.git'",
        )

    caught = None
    with mock_patch("service.workspace.subprocess.run", side_effect=fake_run):
        try:
            clone_workspace("org/repo", "abc123sha", "TOKEN_XYZ")
        except RuntimeError as exc:
            caught = exc

    assert caught is not None
    assert "TOKEN_XYZ" not in str(caught)
    assert "***" in str(caught)
    # from None suppresses display but the exception object itself is kept as
    # __context__ -- its own attributes must be redacted too, or a logger
    # that introspects __context__ directly (not via text formatting) would
    # still leak the token.
    assert caught.__cause__ is None
    assert caught.__context__ is None or "TOKEN_XYZ" not in str(caught.__context__)
