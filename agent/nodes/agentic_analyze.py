import json
import os

from openai import OpenAI

from agent.schemas import AgentState, Issue, Patch
from agent.tools.agent_tools import TOOL_SCHEMAS, build_tool_dispatch

MODEL = "gpt-4o"
TEMPERATURE = 0.1
MAX_ITERATIONS = 8

SYSTEM_PROMPT = (
    "You are a senior security-focused code reviewer investigating a pull "
    "request diff. You have tools to search the codebase for similar "
    "patterns, read files, run tests, check past similar bugs, look up "
    "known CVEs, stage fixes, and post comments. Use them as needed before "
    "concluding.\n\n"
    "When you are done investigating, respond with ONLY a JSON object (no "
    "tool calls, no markdown) of the form:\n"
    '{"issues": [{"file": ..., "line_start": ..., "line_end": ..., '
    '"severity": "critical|high|medium|low", "category": "security|bug|'
    'performance|style", "title": ..., "description": ..., "suggestion": '
    '..., "confidence": 0-1, "fixable": true|false}], "fixed_issue_indexes": '
    '[indexes into "issues" for which you successfully called apply_fix and '
    "it was staged]}"
)


def _build_user_prompt(state: AgentState) -> str:
    files_list = "\n".join(f"- {f}" for f in state.changed_files) or "(none)"
    return (
        f"## Diff\n{state.diff[:8000]}\n\n"
        f"## Changed files\n{files_list}\n\n"
        "Investigate this change using your tools, then report your findings "
        "in the required JSON format."
    )


def _parse_final_response(content: str) -> tuple[list[dict], list[int]]:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return [], []

    issues = data.get("issues", [])
    if not isinstance(issues, list):
        issues = []

    fixed_indexes = data.get("fixed_issue_indexes", [])
    if not isinstance(fixed_indexes, list):
        fixed_indexes = []

    return issues, fixed_indexes


def agentic_analyze_node(state: AgentState) -> AgentState:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    dispatch = build_tool_dispatch(state.workspace, state.pr_number)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(state)},
    ]

    staged_fixes: dict[str, dict] = {}
    issues_raw: list[dict] = []
    fixed_indexes: list[int] = []

    for _ in range(MAX_ITERATIONS):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                temperature=TEMPERATURE,
                messages=messages,
                tools=TOOL_SCHEMAS,
            )
        except Exception as exc:
            print(f"[agentic_analyze] LLM call failed: {exc}")
            return state.model_copy(update={"issues": [], "patches": []})

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            issues_raw, fixed_indexes = _parse_final_response(message.content or "")
            break

        messages.append(message.model_dump(exclude_none=True))

        for call in tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            print(f"[agentic_analyze] tool call: {name}({args})")

            fn = dispatch.get(name)
            if fn is None:
                result = {"error": f"unknown tool {name}"}
            else:
                try:
                    result = fn(**args)
                except Exception as exc:
                    result = {"error": str(exc)}

            if name == "apply_fix" and isinstance(result, dict) and result.get("staged"):
                staged_fixes[result["file"]] = result

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result)[:4000],
                }
            )
    else:
        print(f"[agentic_analyze] hit max iterations ({MAX_ITERATIONS}) without a final answer")

    issues: list[Issue] = []
    for item in issues_raw:
        try:
            issues.append(Issue(**item))
        except Exception:
            continue

    patches: list[Patch] = []
    for idx in fixed_indexes:
        if not isinstance(idx, int) or idx < 0 or idx >= len(issues):
            continue
        issue = issues[idx]
        staged = staged_fixes.get(issue.file)
        if not staged:
            continue
        patches.append(
            Patch(
                issue=issue,
                file=issue.file,
                original_snippet=staged["original_snippet"],
                fixed_snippet=staged["fixed_snippet"],
                commit_message=f"fix: {issue.title[:43]}",
            )
        )

    print(f"[agentic_analyze] {len(issues)} issue(s), {len(patches)} staged patch(es)")

    return state.model_copy(update={"issues": issues, "patches": patches})
