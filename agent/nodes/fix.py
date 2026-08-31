import asyncio
import json
import os
from typing import Optional

from openai import AsyncOpenAI

from agent.schemas import AgentState, Issue, Patch, Severity

MODEL = "gpt-4o"
TEMPERATURE = 0.0

MAX_FILE_CHARS = 6000

FIXABLE_SEVERITIES = {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM}

SYSTEM_PROMPT = (
    "You are a senior engineer generating minimal safe patches. Return JSON "
    "with exactly: original_snippet (exact verbatim text from file), "
    "fixed_snippet (replacement), commit_message (fix: max 50 chars). If you "
    "cannot make a safe minimal fix return empty strings."
)


def _build_user_prompt(issue: Issue, file_content: str) -> str:
    return (
        f"File: {issue.file}\n"
        f"Lines: {issue.line_start}-{issue.line_end}\n"
        f"Severity: {issue.severity.value}\n"
        f"Title: {issue.title}\n"
        f"Description: {issue.description}\n"
        f"Suggestion: {issue.suggestion}\n\n"
        f"## File content\n{file_content[:MAX_FILE_CHARS]}"
    )


async def _generate_patch(
    client: AsyncOpenAI, issue: Issue, file_content: str
) -> Optional[Patch]:
    user_prompt = _build_user_prompt(issue, file_content)

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
    except Exception as exc:
        print(f"[fix] patch generation failed for {issue.file}:{issue.line_start}: {exc}")
        return None

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        print(f"[fix] invalid JSON returned for {issue.file}:{issue.line_start}")
        return None

    original_snippet = data.get("original_snippet", "")
    fixed_snippet = data.get("fixed_snippet", "")
    commit_message = data.get("commit_message", "")

    if not original_snippet or not fixed_snippet:
        return None

    if original_snippet not in file_content:
        print(f"[fix] original_snippet not found verbatim in {issue.file}, discarding patch")
        return None

    return Patch(
        issue=issue,
        file=issue.file,
        original_snippet=original_snippet,
        fixed_snippet=fixed_snippet,
        commit_message=commit_message,
    )


async def _fix_async(state: AgentState) -> list[Patch]:
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    candidates = [
        issue
        for issue in state.issues
        if issue.fixable and issue.severity in FIXABLE_SEVERITIES
    ]

    tasks = []
    for issue in candidates:
        file_content = state.file_contents.get(issue.file, "")
        if not file_content:
            continue
        tasks.append(_generate_patch(client, issue, file_content))

    if not tasks:
        return []

    results = await asyncio.gather(*tasks)
    return [patch for patch in results if patch is not None]


def fix_node(state: AgentState) -> AgentState:
    patches = asyncio.run(_fix_async(state))
    print(f"[fix] {len(patches)} patch(es) generated")
    return state.model_copy(update={"patches": patches})
