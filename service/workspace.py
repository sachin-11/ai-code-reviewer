import shutil
import subprocess
import tempfile


def _redact(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def clone_workspace(repo_full_name: str, head_sha: str, github_token: str) -> str:
    workspace = tempfile.mkdtemp(prefix="ai-review-")
    clone_url = f"https://x-access-token:{github_token}@github.com/{repo_full_name}.git"

    try:
        subprocess.run(
            ["git", "clone", "--quiet", clone_url, workspace],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "checkout", "--quiet", head_sha],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        shutil.rmtree(workspace, ignore_errors=True)
        # CalledProcessError.cmd/stderr/output can contain the token-bearing
        # clone URL. `raise ... from None` only suppresses *display* of the
        # implicit __context__ chain -- Python still attaches this exact exc
        # object as __context__, so redact its own attributes in place
        # rather than relying on chain-suppression alone.
        exc.cmd = [_redact(str(part), github_token) for part in exc.cmd]
        if exc.stderr:
            exc.stderr = _redact(exc.stderr, github_token)
        if exc.output:
            exc.output = _redact(exc.output, github_token)
        raise RuntimeError(
            f"failed to prepare workspace for {repo_full_name}@{head_sha[:10]}: {exc.stderr or ''}"
        ) from None

    return workspace


def cleanup_workspace(workspace: str) -> None:
    shutil.rmtree(workspace, ignore_errors=True)
