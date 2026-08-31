from agent import github_client
from agent.schemas import AgentState

MAX_FILE_LINES = 400


def _truncate(content: str) -> str:
    lines = content.splitlines()
    if len(lines) <= MAX_FILE_LINES:
        return content

    truncated = lines[:MAX_FILE_LINES]
    truncated.append(f"... (truncated, {len(lines)} total lines)")
    return "\n".join(truncated)


def fetch_node(state: AgentState) -> AgentState:
    diff = github_client.fetch_diff(state.base_sha, state.head_sha, state.workspace)
    changed_files = github_client.fetch_changed_files(
        state.base_sha, state.head_sha, state.workspace
    )

    print(f"[fetch] {len(changed_files)} file(s) changed")

    file_contents = {}
    for filepath in changed_files:
        content = github_client.fetch_file_content(filepath, state.workspace)
        file_contents[filepath] = _truncate(content)

    return state.model_copy(
        update={
            "diff": diff,
            "changed_files": changed_files,
            "file_contents": file_contents,
        }
    )
