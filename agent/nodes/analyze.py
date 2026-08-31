import asyncio
import json
import os
from typing import Optional

from openai import AsyncOpenAI

from agent.llm_cost import cost_from_response
from agent.schemas import AgentState, Issue, Severity

MODEL = "gpt-4o-mini"
TEMPERATURE = 0.1

MAX_DIFF_CHARS = 8000
MAX_FILES_CHARS = 6000
MAX_FILES = 6

MIN_CONFIDENCE = 0.60
MAX_ISSUES = 20

SYSTEM_PROMPT = (
    "You are a senior code reviewer. Analyze the given diff and file context. "
    "Return ONLY a JSON array of issues with fields: file, line_start, line_end, "
    "severity, category, title (max 80 chars), description, suggestion, "
    "confidence (0-1), fixable (bool). Return [] if no issues. Raw JSON only."
)

CATEGORY_INSTRUCTIONS = {
    "security": (
        "Focus on security issues: injection, hardcoded secrets, missing auth "
        "checks, path traversal, XSS, SSRF."
    ),
    "bug": (
        "Focus on bugs: logic bugs, off-by-one errors, null dereferences, "
        "race conditions, unhandled exceptions."
    ),
    "performance": (
        "Focus on performance issues: N+1 queries, blocking I/O in async code, "
        "unnecessary loops, redundant computations."
    ),
    "style": (
        "Focus on style/quality issues: dead code, unused imports, functions "
        "with cyclomatic complexity > 10, missing error handling."
    ),
}

SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}


def _build_user_prompt(category: str, diff: str, file_contents: dict[str, str]) -> str:
    truncated_diff = diff[:MAX_DIFF_CHARS]

    sections = []
    remaining = MAX_FILES_CHARS
    for filepath, content in list(file_contents.items())[:MAX_FILES]:
        if remaining <= 0:
            break
        snippet = content[:remaining]
        remaining -= len(snippet)
        sections.append(f"### {filepath}\n{snippet}")

    files_section = "\n\n".join(sections)

    return (
        f"{CATEGORY_INSTRUCTIONS[category]}\n\n"
        f"## Diff\n{truncated_diff}\n\n"
        f"## File contents\n{files_section}"
    )


def _parse_issue_items(raw: str, category: str) -> list[dict]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        print(f"[analyze] {category} analyzer returned invalid JSON")
        return []

    if isinstance(parsed, dict):
        for value in parsed.values():
            if isinstance(value, list):
                parsed = value
                break
        else:
            parsed = []

    if not isinstance(parsed, list):
        return []

    return parsed


def _to_issue(item: dict) -> Optional[Issue]:
    try:
        return Issue(**item)
    except Exception:
        return None


async def _run_analyzer(
    client: AsyncOpenAI, category: str, diff: str, file_contents: dict[str, str]
) -> tuple[list[dict], float]:
    user_prompt = _build_user_prompt(category, diff, file_contents)

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content
        cost = cost_from_response(MODEL, response)
    except Exception as exc:
        print(f"[analyze] {category} analyzer failed: {exc}")
        return [], 0.0

    return _parse_issue_items(raw, category), cost


async def _analyze_async(state: AgentState) -> tuple[list[Issue], float]:
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    categories = list(CATEGORY_INSTRUCTIONS.keys())
    results = await asyncio.gather(
        *[
            _run_analyzer(client, category, state.diff, state.file_contents)
            for category in categories
        ]
    )

    issues: list[Issue] = []
    total_cost = 0.0
    for raw_items, cost in results:
        total_cost += cost
        for item in raw_items:
            issue = _to_issue(item)
            if issue is not None:
                issues.append(issue)

    return issues, total_cost


def analyze_node(state: AgentState) -> AgentState:
    issues, cost_usd = asyncio.run(_analyze_async(state))
    print(f"[analyze] {len(issues)} raw issue(s) found across 4 analyzers, ${cost_usd:.4f}")

    issues = [issue for issue in issues if issue.confidence >= MIN_CONFIDENCE]
    issues.sort(key=lambda issue: (SEVERITY_ORDER[issue.severity], -issue.confidence))
    issues = issues[:MAX_ISSUES]

    print(f"[analyze] {len(issues)} issue(s) kept after filtering (confidence >= {MIN_CONFIDENCE})")

    return state.model_copy(update={"issues": issues, "cost_usd": state.cost_usd + cost_usd})
