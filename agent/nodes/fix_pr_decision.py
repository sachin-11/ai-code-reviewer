from agent import github_client


def handle_fix_pr_decision(pr_number: int, decision: str, comment_author: str) -> None:
    bot_login = github_client.get_authenticated_login()
    if bot_login and comment_author == bot_login:
        print("[fix_pr_decision] ignoring the bot's own comment")
        return

    if not github_client.is_fix_pr(pr_number):
        print(f"[fix_pr_decision] PR #{pr_number} is not one of our fix PRs, ignoring")
        return

    if not github_client.has_write_access(comment_author):
        github_client.post_pr_comment(
            pr_number,
            f"@{comment_author} you need write access to this repository to {decision} this PR.",
        )
        print(f"[fix_pr_decision] {comment_author} lacks write access, denied {decision}")
        return

    if decision == "approve":
        if github_client.merge_fix_pr(pr_number):
            print(f"[fix_pr_decision] merged fix PR #{pr_number} (approved by {comment_author})")
        else:
            github_client.post_pr_comment(
                pr_number, "Merge failed — please merge manually or check for conflicts."
            )
        return

    if github_client.close_fix_pr(pr_number):
        github_client.post_pr_comment(pr_number, f"Closed without merging, per {comment_author}'s request.")
        print(f"[fix_pr_decision] closed fix PR #{pr_number} (rejected by {comment_author})")
