from unittest.mock import patch as mock_patch

from agent.nodes.fix_pr_decision import handle_fix_pr_decision


def test_bots_own_comment_is_ignored():
    with mock_patch("agent.github_client.get_authenticated_login", return_value="ai-code-reviewer[bot]"), \
        mock_patch("agent.github_client.is_fix_pr") as mock_is_fix_pr:
        handle_fix_pr_decision(9, "approve", "ai-code-reviewer[bot]")
    assert not mock_is_fix_pr.called


def test_comment_on_non_fix_pr_is_ignored():
    with mock_patch("agent.github_client.get_authenticated_login", return_value="bot"), \
        mock_patch("agent.github_client.is_fix_pr", return_value=False), \
        mock_patch("agent.github_client.has_write_access") as mock_write_access:
        handle_fix_pr_decision(9, "approve", "someone")
    assert not mock_write_access.called


def test_approve_without_write_access_is_denied():
    with mock_patch("agent.github_client.get_authenticated_login", return_value="bot"), \
        mock_patch("agent.github_client.is_fix_pr", return_value=True), \
        mock_patch("agent.github_client.has_write_access", return_value=False), \
        mock_patch("agent.github_client.merge_fix_pr") as mock_merge, \
        mock_patch("agent.github_client.post_pr_comment") as mock_comment:
        handle_fix_pr_decision(9, "approve", "random_user")

    assert not mock_merge.called
    assert mock_comment.call_args[0][0] == 9
    assert "write access" in mock_comment.call_args[0][1]


def test_approve_with_write_access_merges():
    with mock_patch("agent.github_client.get_authenticated_login", return_value="bot"), \
        mock_patch("agent.github_client.is_fix_pr", return_value=True), \
        mock_patch("agent.github_client.has_write_access", return_value=True), \
        mock_patch("agent.github_client.merge_fix_pr", return_value=True) as mock_merge, \
        mock_patch("agent.github_client.post_pr_comment") as mock_comment:
        handle_fix_pr_decision(9, "approve", "owner1")

    mock_merge.assert_called_once_with(9)
    assert not mock_comment.called


def test_approve_merge_failure_posts_comment():
    with mock_patch("agent.github_client.get_authenticated_login", return_value="bot"), \
        mock_patch("agent.github_client.is_fix_pr", return_value=True), \
        mock_patch("agent.github_client.has_write_access", return_value=True), \
        mock_patch("agent.github_client.merge_fix_pr", return_value=False), \
        mock_patch("agent.github_client.post_pr_comment") as mock_comment:
        handle_fix_pr_decision(9, "approve", "owner1")

    assert mock_comment.call_args[0][0] == 9
    assert "Merge failed" in mock_comment.call_args[0][1]


def test_reject_with_write_access_closes_pr():
    with mock_patch("agent.github_client.get_authenticated_login", return_value="bot"), \
        mock_patch("agent.github_client.is_fix_pr", return_value=True), \
        mock_patch("agent.github_client.has_write_access", return_value=True), \
        mock_patch("agent.github_client.close_fix_pr", return_value=True) as mock_close, \
        mock_patch("agent.github_client.merge_fix_pr") as mock_merge, \
        mock_patch("agent.github_client.post_pr_comment") as mock_comment:
        handle_fix_pr_decision(9, "reject", "owner1")

    mock_close.assert_called_once_with(9)
    assert not mock_merge.called
    assert mock_comment.call_args[0][0] == 9
    assert "Closed" in mock_comment.call_args[0][1]
