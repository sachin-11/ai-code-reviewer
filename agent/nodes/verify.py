import importlib.util
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

from agent.schemas import AgentState, Patch

logger = logging.getLogger(__name__)

PYTHON_EXTENSIONS = {".py"}
JS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}

LINT_TIMEOUT_SECONDS = 60
TEST_TIMEOUT_SECONDS = 120


def _run_subprocess(cmd: list[str], timeout: int, cwd: Optional[str] = None) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s: {' '.join(cmd)}"
    except OSError as exc:
        return False, f"failed to run {' '.join(cmd)}: {exc}"

    if result.returncode == 0:
        return True, ""

    output = (result.stdout + result.stderr).strip()
    return False, output[:2000]


def _lint_python(filepath: str) -> tuple[bool, str]:
    if shutil.which("ruff"):
        cmd = ["ruff", "check", "--select=E,F,S", filepath]
    elif shutil.which("flake8"):
        cmd = ["flake8", filepath]
    else:
        return True, ""

    return _run_subprocess(cmd, timeout=LINT_TIMEOUT_SECONDS)


def _lint_js(filepath: str) -> tuple[bool, str]:
    if not shutil.which("npx"):
        return True, ""

    cmd = ["npx", "eslint", "--max-warnings=0", filepath]
    return _run_subprocess(cmd, timeout=LINT_TIMEOUT_SECONDS)


def _run_linter(ext: str, filepath: str) -> tuple[bool, str]:
    if ext in PYTHON_EXTENSIONS:
        return _lint_python(filepath)
    if ext in JS_EXTENSIONS:
        return _lint_js(filepath)
    return True, ""


def _lint_in_tempfile(full_path: str, ext: str, content: str) -> tuple[bool, str]:
    fd, temp_path = tempfile.mkstemp(suffix=ext, dir=os.path.dirname(full_path) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        return _run_linter(ext, temp_path)
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


def _run_python_tests(workspace: str) -> tuple[bool, str]:
    # sys.executable -m pytest, not a bare "pytest" resolved off PATH: on a
    # machine with multiple projects' venvs, PATH can put an unrelated
    # project's pytest.exe first, which then fails against this workspace's
    # dependencies with no useful output. sys.executable pins it to this
    # interpreter's own environment.
    if importlib.util.find_spec("pytest") is None:
        return True, ""

    cmd = [sys.executable, "-m", "pytest", "--tb=short", "-q", "--timeout=30"]
    return _run_subprocess(cmd, timeout=TEST_TIMEOUT_SECONDS, cwd=workspace)


def _run_ts_tests(workspace: str) -> tuple[bool, str]:
    package_json_path = os.path.join(workspace, "package.json")
    try:
        with open(package_json_path, "r", encoding="utf-8") as f:
            package_json = json.load(f)
    except (OSError, json.JSONDecodeError):
        return True, ""

    if not package_json.get("scripts", {}).get("test"):
        return True, ""

    cmd = ["npm", "test", "--", "--passWithNoTests"]
    return _run_subprocess(cmd, timeout=TEST_TIMEOUT_SECONDS, cwd=workspace)


def _run_tests(ext: str, workspace: str) -> tuple[bool, str]:
    if ext in PYTHON_EXTENSIONS:
        return _run_python_tests(workspace)
    if ext in JS_EXTENSIONS:
        return _run_ts_tests(workspace)
    return True, ""


def _verify_patch(patch: Patch, workspace: str) -> Patch:
    full_path = os.path.join(workspace, patch.file)
    ext = os.path.splitext(patch.file)[1]

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            original_content = f.read()
    except OSError as exc:
        return patch.model_copy(
            update={"verified": False, "verify_error": f"could not read file: {exc}"}
        )

    if patch.original_snippet not in original_content:
        return patch.model_copy(
            update={"verified": False, "verify_error": "original_snippet not found in current file"}
        )

    patched_content = original_content.replace(patch.original_snippet, patch.fixed_snippet, 1)

    lint_ok, lint_error = _lint_in_tempfile(full_path, ext, patched_content)
    if not lint_ok:
        return patch.model_copy(
            update={"verified": False, "verify_error": f"lint failed: {lint_error}"}
        )

    tests_ok, test_error = True, ""
    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(patched_content)
        tests_ok, test_error = _run_tests(ext, workspace)
    except Exception as exc:
        tests_ok, test_error = False, str(exc)
    finally:
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(original_content)
        except OSError as exc:
            logger.critical("failed to restore %s: %s", patch.file, exc)

    if not tests_ok:
        return patch.model_copy(
            update={"verified": False, "verify_error": f"tests failed: {test_error}"}
        )

    return patch.model_copy(update={"verified": True, "verify_error": None})


def verify_node(state: AgentState) -> AgentState:
    verified_patches = [_verify_patch(patch, state.workspace) for patch in state.patches]

    passed = sum(1 for p in verified_patches if p.verified)
    logger.info("%d/%d patch(es) passed verification", passed, len(verified_patches))

    return state.model_copy(update={"verified_patches": verified_patches})
