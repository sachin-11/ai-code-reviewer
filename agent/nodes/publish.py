import json
import os

from openai import OpenAI

from agent import github_client
from agent.schemas import AgentState, Issue, Severity

MODEL = "gpt-4o-mini"
TEMPERATURE = 0.3

OUTPUT_DIR = ".review_output"
OUTPUT_FILE = "issues.json"

NO_ISSUES_MESSAGE = "No significant issues found ✅"

SYSTEM_PROMPT = (
    "You are a senior engineer summarizing an automated code review for a "
    "pull request. Write exactly two sentences, plain text, no markdown."
)


def _severity_counts(issues: list[Issue]) -> dict[str, int]:
    counts = {severity.value: 0 for severity in Severity}
    for issue in issues:
        counts[issue.severity.value] += 1
    return counts


def _fallback_summary(issues: list[Issue], verified_count: int) -> str:
    counts = _severity_counts(issues)
    return (
        f"Found {len(issues)} issue(s) "
        f"(critical={counts['critical']}, high={counts['high']}, "
        f"medium={counts['medium']}, low={counts['low']}). "
        f"{verified_count} fix(es) were verified."
    )


def _generate_summary(issues: list[Issue], verified_count: int) -> str:
    counts = _severity_counts(issues)
    user_prompt = (
        f"Total issues found: {len(issues)}\n"
        f"Severity breakdown: critical={counts['critical']}, high={counts['high']}, "
        f"medium={counts['medium']}, low={counts['low']}\n"
        f"Verified fixes: {verified_count}\n\n"
        "Write a 2-sentence summary of this code review for the PR author."
    )

    try:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        print(f"[publish] summary generation failed: {exc}")
        return _fallback_summary(issues, verified_count)


def _save_issues(issues: list[Issue], workspace: str) -> None:
    output_dir = os.path.join(workspace, OUTPUT_DIR)
    try:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, OUTPUT_FILE)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([issue.model_dump(mode="json") for issue in issues], f, indent=2)
        print(f"[publish] saved {len(issues)} issue(s) to {output_path}")
    except OSError as exc:
        print(f"[publish] failed to save issues.json: {exc}")


def publish_node(state: AgentState) -> AgentState:
    if not state.issues:
        print("[publish] no issues found, posting clean summary")
        github_client.post_summary_comment(NO_ISSUES_MESSAGE, state.issues, None, state.pr_number)
        return state

    print(f"[publish] posting {len(state.issues)} inline review comment(s)")
    github_client.post_review_comments(state.issues, state.head_sha, state.pr_number)

    verified_patches = [p for p in state.verified_patches if p.verified]
    print(f"[publish] {len(verified_patches)}/{len(state.verified_patches)} patch(es) verified")

    fix_pr_url = None
    if verified_patches:
        print("[publish] opening fix PR for verified patches")
        fix_pr_url = github_client.raise_fix_pr(
            verified_patches,
            state.head_branch,
            state.base_branch,
            state.pr_number,
            state.workspace,
        )
        print(f"[publish] fix PR: {fix_pr_url}")

    print("[publish] generating summary")
    summary = _generate_summary(state.issues, len(verified_patches))

    print("[publish] posting summary comment")
    github_client.post_summary_comment(summary, state.issues, fix_pr_url, state.pr_number)

    _save_issues(state.issues, state.workspace)

    return state.model_copy(update={"fix_pr_url": fix_pr_url})
