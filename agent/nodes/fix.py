import asyncio
import json
import logging
from typing import Optional

from openai import AsyncOpenAI

from agent.llm_client import get_async_openai_client, resolve_model
from agent.llm_cost import cost_from_response
from agent.schemas import AgentState, Issue, Patch, Severity

logger = logging.getLogger(__name__)

MODEL = resolve_model("gpt-4o")
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
) -> tuple[Optional[Patch], float]:
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
        cost = cost_from_response(MODEL, response)
    except Exception as exc:
        logger.error("patch generation failed for %s:%d: %s", issue.file, issue.line_start, exc)
        return None, 0.0

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("invalid JSON returned for %s:%d", issue.file, issue.line_start)
        return None, cost

    original_snippet = data.get("original_snippet", "")
    fixed_snippet = data.get("fixed_snippet", "")
    commit_message = data.get("commit_message", "")

    if not original_snippet or not fixed_snippet:
        return None, cost

    if original_snippet not in file_content:
        logger.warning("original_snippet not found verbatim in %s, discarding patch", issue.file)
        return None, cost

    return (
        Patch(
            issue=issue,
            file=issue.file,
            original_snippet=original_snippet,
            fixed_snippet=fixed_snippet,
            commit_message=commit_message,
        ),
        cost,
    )


async def _fix_async(state: AgentState) -> tuple[list[Patch], float]:
    client = get_async_openai_client()

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
        return [], 0.0

    results = await asyncio.gather(*tasks)
    patches = [patch for patch, _ in results if patch is not None]
    total_cost = sum(cost for _, cost in results)
    return patches, total_cost


def fix_node(state: AgentState) -> AgentState:
    patches, cost_usd = asyncio.run(_fix_async(state))
    logger.info("%d patch(es) generated, $%.4f", len(patches), cost_usd)
    return state.model_copy(update={"patches": patches, "cost_usd": state.cost_usd + cost_usd})
