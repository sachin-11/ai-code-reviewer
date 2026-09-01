import json

from agent import github_client, memory_store
from agent.fingerprint import fingerprint as compute_fingerprint
from agent.llm_client import get_openai_client, resolve_model
from agent.llm_cost import cost_from_response
from agent.schemas import AgentState, Issue, Patch
from agent.tools.agent_tools import TOOL_SCHEMAS, build_tool_dispatch

MODEL = resolve_model("gpt-4o")
TEMPERATURE = 0.1
MAX_ITERATIONS = 8

SYSTEM_PROMPT = (
    "You are a senior security-focused code reviewer investigating a pull "
    "request diff. You have tools to search the codebase for similar "
    "patterns, read files, run tests, check past similar bugs, look up "
    "known CVEs, check this file's owner and their past dismissal notes, "
    "semantically search past issues you've found across PRs (even ones "
    "worded differently), stage fixes, and post comments. Use them as "
    "needed before concluding. If check_author_style shows the owner has "
    "repeatedly dismissed a category of finding, weigh that when deciding "
    "whether to report a similar one again.\n\n"
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


def _load_memory_and_scan_dismissals(pr_number: int) -> dict:
    memory = memory_store.load_memory()

    try:
        repo = github_client.get_repo()
        pr = repo.get_pull(pr_number)
        new_dismissals = memory_store.scan_for_new_dismissals(pr, memory)
        if new_dismissals:
            print(f"[agentic_analyze] recorded {new_dismissals} new dismissal(s) from reactions")
            memory_store.save_memory(memory)
    except Exception as exc:
        print(f"[agentic_analyze] could not scan for dismissals: {exc}")

    return memory


def agentic_analyze_node(state: AgentState) -> AgentState:
    memory = _load_memory_and_scan_dismissals(state.pr_number)

    client = get_openai_client()
    dispatch = build_tool_dispatch(
        state.workspace, state.pr_number, memory["author_notes"], state.repo_full_name
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(state)},
    ]

    staged_fixes: dict[str, dict] = {}
    issues_raw: list[dict] = []
    fixed_indexes: list[int] = []
    cost_usd = 0.0
    iteration_count = 0
    hit_max_iterations = False

    for _ in range(MAX_ITERATIONS):
        iteration_count += 1
        try:
            response = client.chat.completions.create(
                model=MODEL,
                temperature=TEMPERATURE,
                messages=messages,
                tools=TOOL_SCHEMAS,
            )
        except Exception as exc:
            print(f"[agentic_analyze] LLM call failed: {exc}")
            return state.model_copy(
                update={
                    "issues": [],
                    "patches": [],
                    "cost_usd": state.cost_usd + cost_usd,
                    "iteration_count": iteration_count,
                }
            )

        cost_usd += cost_from_response(MODEL, response)
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
        hit_max_iterations = True
        print(f"[agentic_analyze] hit max iterations ({MAX_ITERATIONS}) without a final answer")

    all_issues: list[Issue] = []
    for item in issues_raw:
        try:
            all_issues.append(Issue(**item))
        except Exception:
            continue

    patches: list[Patch] = []
    for idx in fixed_indexes:
        if not isinstance(idx, int) or idx < 0 or idx >= len(all_issues):
            continue
        issue = all_issues[idx]
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

    dismissed_fps = set(memory["dismissed_fingerprints"].keys())

    def _is_dismissed(issue: Issue) -> bool:
        return compute_fingerprint(issue.file, issue.category.value, issue.title) in dismissed_fps

    issues = [issue for issue in all_issues if not _is_dismissed(issue)]
    patches = [patch for patch in patches if not _is_dismissed(patch.issue)]

    skipped = len(all_issues) - len(issues)
    if skipped:
        print(f"[agentic_analyze] skipped {skipped} previously-dismissed issue(s)")

    print(
        f"[agentic_analyze] {len(issues)} issue(s), {len(patches)} staged patch(es), "
        f"${cost_usd:.4f}, {iteration_count} iteration(s)"
    )

    return state.model_copy(
        update={
            "issues": issues,
            "patches": patches,
            "cost_usd": state.cost_usd + cost_usd,
            "iteration_count": iteration_count,
            "hit_max_iterations": hit_max_iterations,
        }
    )
