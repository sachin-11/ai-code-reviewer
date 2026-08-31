import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from agent import github_client

CODE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__"}
MAX_SEARCH_RESULTS = 15
MAX_SEARCH_FILE_BYTES = 200_000

TEST_TIMEOUT_SECONDS = 60

NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
MAX_CVE_RESULTS = 5
WEB_SEARCH_TIMEOUT_SECONDS = 10


def search_codebase(query: str, workspace: str) -> list[dict]:
    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    root = Path(workspace)
    matches: list[dict] = []

    for ext in CODE_EXTENSIONS:
        for path in root.rglob(f"*{ext}"):
            if len(matches) >= MAX_SEARCH_RESULTS:
                return matches
            if any(part in SKIP_DIRS for part in path.parts):
                continue

            try:
                if path.stat().st_size > MAX_SEARCH_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for line_num, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    matches.append(
                        {
                            "file": str(path.relative_to(root)),
                            "line": line_num,
                            "text": line.strip()[:200],
                        }
                    )
                    if len(matches) >= MAX_SEARCH_RESULTS:
                        break

    return matches


def read_file(path: str, workspace: str) -> str:
    return github_client.fetch_file_content(path, workspace)


def run_tests(file: str, workspace: str) -> dict:
    full_path = os.path.join(workspace, file)
    target = file if os.path.isfile(full_path) else "."

    try:
        result = subprocess.run(
            ["pytest", target, "--tb=short", "-q"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return {"ran": False, "passed": None, "output": "pytest not available"}
    except subprocess.TimeoutExpired:
        return {"ran": True, "passed": False, "output": f"timed out after {TEST_TIMEOUT_SECONDS}s"}

    return {
        "ran": True,
        "passed": result.returncode == 0,
        "output": (result.stdout + result.stderr).strip()[:2000],
    }


def search_similar_bugs(description: str) -> list[dict]:
    keywords = re.findall(r"[A-Za-z0-9_]{4,}", description)[:6]
    if not keywords:
        return []

    try:
        repo_full_name = os.environ["REPO_FULL_NAME"]
        client = github_client.get_client()
        issues = client.search_issues(f"{' '.join(keywords)} repo:{repo_full_name}")
        return [
            {"number": issue.number, "title": issue.title, "url": issue.html_url, "state": issue.state}
            for issue in issues[:5]
        ]
    except Exception as exc:
        return [{"error": str(exc)}]


def web_search(query: str) -> list[dict]:
    params = urllib.parse.urlencode({"keywordSearch": query, "resultsPerPage": MAX_CVE_RESULTS})
    url = f"{NVD_API_URL}?{params}"

    try:
        with urllib.request.urlopen(url, timeout=WEB_SEARCH_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return [{"error": str(exc)}]

    results = []
    for item in data.get("vulnerabilities", [])[:MAX_CVE_RESULTS]:
        cve = item.get("cve", {})
        descriptions = cve.get("descriptions", [])
        english_desc = next((d["value"] for d in descriptions if d.get("lang") == "en"), "")
        cve_id = cve.get("id")
        results.append(
            {
                "id": cve_id,
                "description": english_desc[:300],
                "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
            }
        )
    return results


def post_comment(body: str, pr_number: int) -> dict:
    try:
        repo = github_client.get_repo()
        pr = repo.get_pull(pr_number)
        comment = pr.create_issue_comment(body)
        return {"posted": True, "url": comment.html_url}
    except Exception as exc:
        return {"posted": False, "error": str(exc)}


def apply_fix(file: str, original: str, fixed: str, workspace: str) -> dict:
    # Does not write to disk: only validates the patch applies verbatim and
    # stages it, so the existing verify_node lint/test/restore gate still
    # runs before anything is committed.
    content = read_file(file, workspace)
    if not content:
        return {"staged": False, "error": f"could not read {file}"}

    if original not in content:
        return {"staged": False, "error": "original snippet not found verbatim in file"}

    return {"staged": True, "file": file, "original_snippet": original, "fixed_snippet": fixed}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_codebase",
            "description": "Search the workspace's code files for a literal or regex pattern.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the test suite, optionally scoped to one file, and report pass/fail.",
            "parameters": {
                "type": "object",
                "properties": {"file": {"type": "string"}},
                "required": ["file"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_similar_bugs",
            "description": "Search this repository's GitHub issues for past reports similar to the given description.",
            "parameters": {
                "type": "object",
                "properties": {"description": {"type": "string"}},
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Look up known CVEs/vulnerabilities matching a keyword query via the NVD database.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "post_comment",
            "description": "Post a comment on the pull request being reviewed.",
            "parameters": {
                "type": "object",
                "properties": {"body": {"type": "string"}},
                "required": ["body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_fix",
            "description": (
                "Stage a minimal verbatim fix for a file: original must be an exact "
                "substring of the file's current content. Does not write to disk — "
                "staged fixes are verified and applied later in the pipeline."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "original": {"type": "string"},
                    "fixed": {"type": "string"},
                },
                "required": ["file", "original", "fixed"],
            },
        },
    },
]


def build_tool_dispatch(workspace: str, pr_number: int) -> dict:
    return {
        "search_codebase": lambda query: search_codebase(query, workspace),
        "read_file": lambda path: read_file(path, workspace),
        "run_tests": lambda file: run_tests(file, workspace),
        "search_similar_bugs": lambda description: search_similar_bugs(description),
        "web_search": lambda query: web_search(query),
        "post_comment": lambda body: post_comment(body, pr_number),
        "apply_fix": lambda file, original, fixed: apply_fix(file, original, fixed, workspace),
    }
