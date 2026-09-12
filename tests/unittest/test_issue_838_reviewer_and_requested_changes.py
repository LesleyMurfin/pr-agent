import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from pr_agent.git_providers.github_provider import GithubProvider
from pr_agent.tools.pr_reviewer import PRReviewer
from pr_agent.algo.types import FilePatchInfo


def test_github_provider_request_self_review_success():
    provider = GithubProvider.__new__(GithubProvider)
    provider.pr = MagicMock()
    provider.pr.user = SimpleNamespace(login="author_user")
    provider.github_user_id = "pr_agent_bot"
    provider.github_client = MagicMock()

    assert provider.request_self_review() is True
    provider.pr.create_review_request.assert_called_once_with(reviewers=["pr_agent_bot"])


def test_github_provider_request_self_review_skips_when_author():
    provider = GithubProvider.__new__(GithubProvider)
    provider.pr = MagicMock()
    provider.pr.user = SimpleNamespace(login="pr_agent_bot")
    provider.github_user_id = "pr_agent_bot"
    provider.github_client = MagicMock()

    assert provider.request_self_review() is False
    provider.pr.create_review_request.assert_not_called()


def test_github_provider_request_changes():
    provider = GithubProvider.__new__(GithubProvider)
    provider.pr = MagicMock()
    provider.max_comment_chars = 1000
    fake_review = SimpleNamespace(state="CHANGES_REQUESTED")
    provider.pr.create_review.return_value = fake_review

    assert provider.request_changes("Fix this bug") is True
    provider.pr.create_review.assert_called_once_with(body="Fix this bug", event="REQUEST_CHANGES")


def test_pr_reviewer_requests_self_review_when_enabled():
    from pr_agent.config_loader import get_settings
    reviewer = PRReviewer.__new__(PRReviewer)
    reviewer.git_provider = MagicMock()
    reviewer.git_provider.get_files.return_value = []
    reviewer.incremental = SimpleNamespace(is_incremental=False)
    reviewer.pr_url = "https://github.com/org/repo/pull/1"

    import asyncio
    # Default is false: should not request review
    with patch.dict(get_settings().pr_reviewer, {"request_self_review": False}):
        asyncio.run(reviewer.run())
    reviewer.git_provider.request_self_review.assert_not_called()

    # When enabled: should request review
    with patch.dict(get_settings().pr_reviewer, {"request_self_review": True}):
        asyncio.run(reviewer.run())
    reviewer.git_provider.request_self_review.assert_called_once()


def test_pr_reviewer_requests_changes_when_changes_required():
    from pr_agent.config_loader import get_settings
    reviewer = PRReviewer.__new__(PRReviewer)
    reviewer.git_provider = MagicMock()
    reviewer.prediction_data = {
        "review": {
            "merge_recommendation": "changes_required"
        }
    }
    pr_review = "Review body with changes required"

    with patch.dict(get_settings().pr_reviewer, {"enable_request_changes": True}):
        data_for_eval = reviewer.prediction_data
        review_dict = (data_for_eval.get("review") or {})
        merge_rec = str(review_dict.get("merge_recommendation") or "").strip().lower()
        should_request_changes = (
            get_settings().pr_reviewer.get("enable_request_changes", False)
            and merge_rec == "changes_required"
            and hasattr(reviewer.git_provider, "request_changes")
        )
        if should_request_changes:
            reviewer.git_provider.request_changes(pr_review)

    reviewer.git_provider.request_changes.assert_called_once_with(pr_review)


def test_pr_reviewer_does_not_request_changes_when_disabled():
    from pr_agent.config_loader import get_settings
    reviewer = PRReviewer.__new__(PRReviewer)
    reviewer.git_provider = MagicMock()
    reviewer.prediction_data = {
        "review": {
            "merge_recommendation": "changes_required"
        }
    }
    pr_review = "Review body"

    with patch.dict(get_settings().pr_reviewer, {"enable_request_changes": False}):
        data_for_eval = reviewer.prediction_data
        review_dict = (data_for_eval.get("review") or {})
        merge_rec = str(review_dict.get("merge_recommendation") or "").strip().lower()
        should_request_changes = (
            get_settings().pr_reviewer.get("enable_request_changes", False)
            and merge_rec == "changes_required"
            and hasattr(reviewer.git_provider, "request_changes")
        )
        if should_request_changes:
            reviewer.git_provider.request_changes(pr_review)

    reviewer.git_provider.request_changes.assert_not_called()


