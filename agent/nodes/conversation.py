import json
import logging

from agent import github_client, memory_store
from agent.llm_client import get_openai_client, resolve_model
from agent.llm_cost import cost_from_response

logger = logging.getLogger(__name__)

MODEL = resolve_model("gpt-4o-mini")
TEMPERATURE = 0.2
MAX_FILE_CHARS = 4000

DEFAULT_DISMISSAL_REPLY = "Got it — marking this as intentional, I won't flag it again."

SYSTEM_PROMPT = (
    "You are the AI code reviewer bot responding to a human reviewer's reply "
    "on one of your prior findings. Given the original finding and their "
    "reply, classify their intent and respond appropriately.\n\n"
    'Respond with ONLY a JSON object: {"intent": "question|disagreement|other", '
    '"reply": "your reply text, or empty string if intent is \\"other\\""}\n\n'
    "- question: they're asking you to explain or justify the finding. Reply "
    "with a clear, specific explanation and, if applicable, an alternative "
    "fix suggestion.\n"
    "- disagreement: they're saying it's intentional, not a bug, or otherwise "
    "dismissing the finding. Reply with a short acknowledgment that you won't "
    "flag this again.\n"
    "- other: anything else (e.g., unrelated chatter). Do not reply."
)


def _build_user_prompt(finding: dict, reply_text: str, file_content: str) -> str:
    return (
        f"## Original finding\n"
        f"File: {finding['file']}\n"
        f"Category: {finding['category']}\n"
        f"Title: {finding['title']}\n\n"
        f"## File content\n{file_content[:MAX_FILE_CHARS]}\n\n"
        f"## Reviewer's reply\n{reply_text}"
    )


def _classify_and_respond(finding: dict, reply_text: str, file_content: str) -> dict:
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(finding, reply_text, file_content)},
            ],
        )
        data = json.loads(response.choices[0].message.content)
        logger.info("classification cost: $%.4f", cost_from_response(MODEL, response))
    except Exception as exc:
        logger.error("classification failed: %s", exc)
        return {"intent": "other", "reply": ""}

    intent = data.get("intent")
    if intent not in {"question", "disagreement", "other"}:
        intent = "other"

    return {"intent": intent, "reply": data.get("reply") or ""}


def handle_comment(comment_id: int, comment_author: str, pr_number: int, workspace: str) -> None:
    bot_login = github_client.get_authenticated_login()
    if bot_login and comment_author == bot_login:
        logger.info("ignoring the bot's own comment")
        return

    comment = github_client.get_review_comment(comment_id, pr_number)
    if comment is None:
        return

    root = github_client.get_thread_root(comment, pr_number)
    if root is None:
        logger.warning("could not resolve thread root, ignoring")
        return

    finding = memory_store.parse_marker(root.body)
    if finding is None:
        logger.info("thread root is not a bot finding, ignoring")
        return

    file_content = github_client.fetch_file_content(finding["file"], workspace)
    result = _classify_and_respond(finding, comment.body, file_content)

    if result["intent"] == "disagreement":
        memory = memory_store.load_memory()
        memory_store.record_dismissal(
            memory,
            finding["fingerprint"],
            finding["file"],
            finding["category"],
            finding["title"],
            comment_author,
        )
        memory_store.save_memory(memory)
        github_client.reply_to_review_comment(
            pr_number, comment_id, result["reply"] or DEFAULT_DISMISSAL_REPLY
        )
        logger.info("recorded dismissal from %s for %s", comment_author, finding["file"])
        return

    if result["intent"] == "question" and result["reply"]:
        github_client.reply_to_review_comment(pr_number, comment_id, result["reply"])
        logger.info("replied to question from %s", comment_author)
        return

    logger.info("intent=%s, no reply sent", result["intent"])
