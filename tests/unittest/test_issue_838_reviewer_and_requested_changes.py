import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pr_agent.algo.types import FilePatchInfo
from pr_agent.config_loader import get_settings
from pr_agent.git_providers.github_provider import GithubProvider
from pr_agent.tools import pr_reviewer as pr_reviewer_module
from pr_agent.tools.pr_reviewer import PRReviewer
from tests.unittest._settings_helpers import restore_settings, snapshot_settings


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


@pytest.mark.parametrize("state", ["COMMENTED", None, "APPROVED"])
def test_github_provider_request_changes_unexpected_state(state):
    provider = GithubProvider.__new__(GithubProvider)
    provider.pr = MagicMock()
    provider.max_comment_chars = 1000
    fake_review = SimpleNamespace() if state is None else SimpleNamespace(state=state)
    provider.pr.create_review.return_value = fake_review

    assert provider.request_changes("Fix this bug") is False
    provider.pr.create_review.assert_called_once_with(body="Fix this bug", event="REQUEST_CHANGES")


def test_pr_reviewer_requests_self_review_when_enabled():
    reviewer = PRReviewer.__new__(PRReviewer)
    reviewer.git_provider = MagicMock()
    reviewer.git_provider.get_files.return_value = []
    reviewer.incremental = SimpleNamespace(is_incremental=False)
    reviewer.pr_url = "https://github.com/org/repo/pull/1"

    # Default is false: should not request review
    with patch.dict(get_settings().pr_reviewer, {"request_self_review": False}):
        asyncio.run(reviewer.run())
    reviewer.git_provider.request_self_review.assert_not_called()

    # When enabled: should request review
    with patch.dict(get_settings().pr_reviewer, {"request_self_review": True}):
        asyncio.run(reviewer.run())
    reviewer.git_provider.request_self_review.assert_called_once()


@pytest.mark.parametrize("enable_request_changes", [True, False])
def test_pr_reviewer_request_changes_driven_by_run(enable_request_changes):
    snapshot = snapshot_settings([
        "config.publish_output",
        "pr_reviewer.enable_request_changes",
        "pr_reviewer.require_merge_recommendation",
    ])
    try:
        get_settings().set("config.publish_output", True)
        get_settings().set("pr_reviewer.enable_request_changes", enable_request_changes)
        get_settings().set("pr_reviewer.require_merge_recommendation", False)

        reviewer = PRReviewer.__new__(PRReviewer)
        reviewer.git_provider = MagicMock()
        reviewer.git_provider.get_files.return_value = [
            FilePatchInfo(base_file="a.py", head_file="a.py", patch="@@ -1 +1 @@", filename="a.py")
        ]
        reviewer.git_provider.should_publish_review_as_thread.return_value = False
        reviewer.git_provider.publish_comment = MagicMock()
        reviewer.git_provider.request_changes = MagicMock(return_value=True)

        reviewer.incremental = SimpleNamespace(is_incremental=False)
        reviewer.pr_url = "https://github.com/org/repo/pull/1"
        reviewer.vars = {}
        reviewer.prediction = "dummy prediction"
        reviewer.prediction_data = {
            "review": {
                "merge_recommendation": "changes_required"
            }
        }

        async def fake_extract(git_provider, vars):
            return None

        async def fake_retry(func, *args, **kwargs):
            return None

        with (
            patch("pr_agent.tools.pr_reviewer.extract_and_cache_pr_tickets", side_effect=fake_extract),
            patch("pr_agent.tools.pr_reviewer.retry_with_fallback_models", side_effect=fake_retry),
            patch.object(reviewer, "_prepare_pr_review", return_value="Prepared review body"),
            patch.object(reviewer, "_should_publish_review_no_suggestions", return_value=True),
        ):
            asyncio.run(reviewer.run())

        if enable_request_changes:
            reviewer.git_provider.request_changes.assert_called_once_with("Prepared review body")
        else:
            reviewer.git_provider.request_changes.assert_not_called()
    finally:
        restore_settings(snapshot)


@pytest.mark.parametrize(
    "require_merge_rec, enable_req_changes, expected",
    [
        (False, False, False),
        (True, False, True),
        (False, True, True),
        (True, True, True),
    ],
)
def test_pr_reviewer_init_require_merge_recommendation(monkeypatch, require_merge_rec, enable_req_changes, expected):
    snapshot = snapshot_settings([
        "pr_reviewer.require_merge_recommendation",
        "pr_reviewer.enable_request_changes",
    ])
    try:
        get_settings().set("pr_reviewer.require_merge_recommendation", require_merge_rec)
        get_settings().set("pr_reviewer.enable_request_changes", enable_req_changes)

        provider = MagicMock()
        provider.is_supported.return_value = True
        provider.get_languages.return_value = {}
        provider.get_files.return_value = []
        provider.get_pr_description.return_value = ("desc", [])

        monkeypatch.setattr(pr_reviewer_module, "get_git_provider_with_context", lambda pr_url: provider)
        monkeypatch.setattr(pr_reviewer_module, "get_main_pr_language", lambda languages, files: "Python")
        monkeypatch.setattr(pr_reviewer_module, "TokenHandler", MagicMock())

        reviewer = PRReviewer("https://example/pr/1", ai_handler=lambda: SimpleNamespace(main_pr_language=None))
        assert reviewer.vars["require_merge_recommendation"] is expected
    finally:
        restore_settings(snapshot)
