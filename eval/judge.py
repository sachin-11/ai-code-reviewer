import json

from agent.llm_client import get_openai_client
from agent.schemas import Issue

JUDGE_MODEL = "gpt-4o"
JUDGE_TEMPERATURE = 0.0

OFFLINE_SYSTEM_PROMPT = (
    "You are an expert code review judge. You are given a code snippet, a "
    "list of EXPECTED issues a good reviewer should find, and a list of "
    "ACTUAL issues an AI reviewer actually reported. Your job is to grade "
    "the AI reviewer's output.\n\n"
    "For each EXPECTED issue, decide if any ACTUAL issue substantively "
    "covers it (same underlying problem, even if worded differently) -- "
    "mark it 'caught' or 'missed'.\n"
    "For each ACTUAL issue that does not correspond to an EXPECTED issue, "
    "decide if it is still a genuinely valid, well-grounded finding in the "
    "code ('valid_extra') or if it is incorrect, hallucinated, or not "
    "actually a problem in this code ('false_positive').\n\n"
    'Respond with ONLY a JSON object: {"expected_results": '
    '[{"description": ..., "status": "caught|missed"}], "actual_results": '
    '[{"title": ..., "status": "valid_extra|false_positive"}]}'
)

ONLINE_SYSTEM_PROMPT = (
    "You are an expert code review judge. You are given a code diff and a "
    "list of issues an AI reviewer reported about it. For each issue, "
    "decide whether it is a genuinely valid, well-grounded finding in the "
    "actual code shown, or whether it looks incorrect, hallucinated, or not "
    "actually a problem here.\n\n"
    'Respond with ONLY a JSON object: {"results": [{"title": ..., "status": '
    '"valid|false_positive", "reason": ...}]}'
)


def _format_actual_issues(issues: list[Issue]) -> str:
    lines = [f"- [{i.severity.value}/{i.category.value}] {i.title}: {i.description}" for i in issues]
    return "\n".join(lines) or "(none)"


def judge_offline_case(file_content: str, expected_issues: list[dict], actual_issues: list[Issue]) -> dict:
    expected_text = "\n".join(f"- {e['description']}" for e in expected_issues) or "(none)"
    user_prompt = (
        f"## Code\n{file_content}\n\n"
        f"## Expected issues\n{expected_text}\n\n"
        f"## Actual issues reported by the AI reviewer\n{_format_actual_issues(actual_issues)}"
    )

    client = get_openai_client()
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=JUDGE_TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": OFFLINE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return json.loads(response.choices[0].message.content)


def judge_online_sample(diff: str, actual_issues: list[Issue]) -> dict:
    if not actual_issues:
        return {"results": []}

    user_prompt = f"## Diff\n{diff[:6000]}\n\n## Issues reported\n{_format_actual_issues(actual_issues)}"

    client = get_openai_client()
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=JUDGE_TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": ONLINE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return json.loads(response.choices[0].message.content)
