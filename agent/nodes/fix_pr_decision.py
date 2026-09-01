import logging

from agent import github_client

logger = logging.getLogger(__name__)


def handle_fix_pr_decision(pr_number: int, decision: str, comment_author: str) -> None:
    bot_login = github_client.get_authenticated_login()
    if bot_login and comment_author == bot_login:
        logger.info("ignoring the bot's own comment")
        return

    if not github_client.is_fix_pr(pr_number):
        logger.info("PR #%d is not one of our fix PRs, ignoring", pr_number)
        return

    if not github_client.has_write_access(comment_author):
        github_client.post_pr_comment(
            pr_number,
            f"@{comment_author} you need write access to this repository to {decision} this PR.",
        )
        logger.warning("%s lacks write access, denied %s", comment_author, decision)
        return

    if decision == "approve":
        if github_client.merge_fix_pr(pr_number):
            logger.info("merged fix PR #%d (approved by %s)", pr_number, comment_author)
        else:
            github_client.post_pr_comment(
                pr_number, "Merge failed — please merge manually or check for conflicts."
            )
            logger.error("failed to merge fix PR #%d (approved by %s)", pr_number, comment_author)
        return

    if github_client.close_fix_pr(pr_number):
        github_client.post_pr_comment(pr_number, f"Closed without merging, per {comment_author}'s request.")
        logger.info("closed fix PR #%d (rejected by %s)", pr_number, comment_author)
