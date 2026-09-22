import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pr_agent.algo.types import FilePatchInfo
from pr_agent.config_loader import get_settings
from pr_agent.git_providers.github_provider import GithubProvider
from pr_agent.tools.pr_reviewer import PRReviewer
from tests.unittest._settings_helpers import restore_settings, snapshot_settings

# --------------------------------------------------------------------------- #
# GithubProvider.request_self_review() / request_changes(): direct coverage
# for the methods PRReviewer.run() relies on below.
# --------------------------------------------------------------------------- #

def test_github_provider_request_self_review_calls_create_review_request_without_comment_stub():
    provider = GithubProvider.__new__(GithubProvider)
    provider.pr = MagicMock()
    provider.github_user_id = None

    assert provider.request_self_review() is True
    provider.pr.create_review_request.assert_called_once_with(reviewers=["riley-pr-agent[bot]"])
    provider.pr.create_review.assert_not_called()


def test_github_provider_request_self_review_handles_422_failure():
    provider = GithubProvider.__new__(GithubProvider)
    provider.pr = MagicMock()
    provider.github_user_id = None
    provider.pr.create_review_request.side_effect = RuntimeError("422 Reviews may only be requested from collaborators")

    assert provider.request_self_review() is False
    provider.pr.create_review_request.assert_called_once_with(reviewers=["riley-pr-agent[bot]"])
    provider.pr.create_review.assert_not_called()


def test_github_provider_request_self_review_uses_custom_config_and_never_pr_agent():
    provider = GithubProvider.__new__(GithubProvider)
    provider.pr = MagicMock()
    provider.github_user_id = None

    snapshot = snapshot_settings(["GITHUB.APP_NAME", "PR_REVIEWER.SELF_REVIEWER_LOGIN"])
    try:
        # Explicit custom login
        get_settings().set("PR_REVIEWER.SELF_REVIEWER_LOGIN", "custom-bot[bot]")
        provider.request_self_review()
        provider.pr.create_review_request.assert_called_with(reviewers=["custom-bot[bot]"])

        # Literal "pr-agent" is never used, falls back to riley-pr-agent[bot]
        get_settings().set("PR_REVIEWER.SELF_REVIEWER_LOGIN", "")
        get_settings().set("GITHUB.APP_NAME", "pr-agent")
        provider.request_self_review()
        provider.pr.create_review_request.assert_called_with(reviewers=["riley-pr-agent[bot]"])
    finally:
        restore_settings(snapshot)


def test_github_provider_request_self_review_handles_failure():
    provider = GithubProvider.__new__(GithubProvider)
    provider.pr = MagicMock()
    provider.pr.create_review_request.side_effect = RuntimeError("API error")

    assert provider.request_self_review() is False
    provider.pr.create_review.assert_not_called()


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
    reviewer.git_provider.get_files.return_value = [
        FilePatchInfo(base_file="a.py", head_file="a.py", patch="@@ -1 +1 @@", filename="a.py")
    ]
    reviewer.git_provider.should_publish_review_as_thread.return_value = False
    reviewer.git_provider.publish_comment = MagicMock()
    reviewer.incremental = SimpleNamespace(is_incremental=False)
    reviewer.pr_url = "https://github.com/org/repo/pull/1"
    reviewer.vars = {}
    reviewer.prediction = ""

    snapshot = snapshot_settings(["config.publish_output", "pr_reviewer.request_self_review"])
    try:
        get_settings().set("config.publish_output", True)

        # Default is false: should not request review
        get_settings().set("pr_reviewer.request_self_review", False)
        asyncio.run(reviewer.run())
        reviewer.git_provider.request_self_review.assert_not_called()

        # When enabled: should request review
        get_settings().set("pr_reviewer.request_self_review", True)
        asyncio.run(reviewer.run())
        reviewer.git_provider.request_self_review.assert_called_once()
    finally:
        restore_settings(snapshot)


def test_pr_reviewer_self_review_not_called_when_publish_output_false():
    reviewer = PRReviewer.__new__(PRReviewer)
    reviewer.git_provider = MagicMock()
    reviewer.git_provider.get_files.return_value = [
        FilePatchInfo(base_file="a.py", head_file="a.py", patch="@@ -1 +1 @@", filename="a.py")
    ]
    reviewer.incremental = SimpleNamespace(is_incremental=False)
    reviewer.pr_url = "https://github.com/org/repo/pull/1"
    reviewer.vars = {}
    reviewer.prediction = ""

    snapshot = snapshot_settings(["config.publish_output", "pr_reviewer.request_self_review"])
    try:
        get_settings().set("config.publish_output", False)
        get_settings().set("pr_reviewer.request_self_review", True)
        asyncio.run(reviewer.run())
        reviewer.git_provider.request_self_review.assert_not_called()
    finally:
        restore_settings(snapshot)


def test_pr_reviewer_self_review_not_called_when_no_files():
    reviewer = PRReviewer.__new__(PRReviewer)
    reviewer.git_provider = MagicMock()
    reviewer.git_provider.get_files.return_value = []
    reviewer.incremental = SimpleNamespace(is_incremental=False)
    reviewer.pr_url = "https://github.com/org/repo/pull/1"

    snapshot = snapshot_settings(["config.publish_output", "pr_reviewer.request_self_review"])
    try:
        get_settings().set("config.publish_output", True)
        get_settings().set("pr_reviewer.request_self_review", True)
        asyncio.run(reviewer.run())
        reviewer.git_provider.request_self_review.assert_not_called()
    finally:
        restore_settings(snapshot)



# --------------------------------------------------------------------------- #
# Issue #869: PR-Agent fails to create REQUEST_CHANGES review and inline
# diff comments on live GitHub PRs.
# --------------------------------------------------------------------------- #

def test_can_verify_inline_comment_publication_true_for_github():
    from pr_agent.algo.inline_comment_dedup import can_verify_inline_comment_publication

    provider = GithubProvider.__new__(GithubProvider)
    provider.pr = MagicMock()
    provider.pr.get_comments.return_value = []

    assert can_verify_inline_comment_publication(provider) is True


def test_github_provider_publish_inline_comments_tracks_bodies():
    provider = GithubProvider.__new__(GithubProvider)
    provider.pr = MagicMock()
    provider.pr.create_review = MagicMock(return_value=SimpleNamespace(state="COMMENTED"))
    provider.max_comment_chars = 1000
    provider.last_commit_id = "sha123"

    assert provider.get_recent_inline_comment_bodies() == []

    provider.publish_inline_comments([
        {"path": "a.py", "line": 5, "body": "First finding."},
        {"path": "b.py", "line": 9, "body": "Second finding."},
    ])

    tracked = provider.get_recent_inline_comment_bodies()
    assert len(tracked) == 2
    assert "First finding." in tracked[0]
    assert "Second finding." in tracked[1]

    # get_persistent_comment_bodies includes tracked bodies plus existing PR comments
    provider.pr.get_comments.return_value = [SimpleNamespace(body="An older, unrelated comment.")]
    persistent = provider.get_persistent_comment_bodies()
    assert "An older, unrelated comment." in persistent
    assert all(body in persistent for body in tracked)


def test_publish_key_issues_as_inline_comments_dedups_on_github_provider():
    provider = GithubProvider.__new__(GithubProvider)
    provider.pr = MagicMock()
    provider.pr.get_comments.return_value = []
    provider.pr.create_review = MagicMock(return_value=SimpleNamespace(state="COMMENTED"))
    provider.max_comment_chars = 1000
    provider.last_commit_id = "sha123"

    file = FilePatchInfo(
        base_file="a.py",
        head_file="line1\nline2\nline3\nline4\nline5\n",
        patch="@@ -1,5 +1,5 @@\n line1\n line2\n line3\n line4\n line5",
        filename="a.py",
    )
    provider.get_diff_files = MagicMock(return_value=[file])

    reviewer = PRReviewer.__new__(PRReviewer)
    reviewer.git_provider = provider

    def make_data():
        return {
            "review": {
                "key_issues_to_review": [
                    {
                        "relevant_file": "a.py",
                        "issue_header": "Bug",
                        "issue_content": "Off-by-one error in the loop bound.",
                        "start_line": 2,
                        "end_line": 2,
                    }
                ]
            }
        }

    result = reviewer._publish_key_issues_as_inline_comments(make_data())
    assert "key_issues_to_review" not in result["review"]
    provider.pr.create_review.assert_called_once()
    assert len(provider.get_recent_inline_comment_bodies()) == 1

    # A second run with the identical finding must dedup: no additional publish call,
    # and the finding is still dropped from the summary (already published).
    result_2 = reviewer._publish_key_issues_as_inline_comments(make_data())
    assert "key_issues_to_review" not in result_2["review"]
    provider.pr.create_review.assert_called_once()


def _make_reviewer_for_run(prediction_data):
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
    reviewer.prediction_data = prediction_data
    return reviewer


@pytest.mark.parametrize(
    "prediction_data",
    [
        # Explicit merge recommendation
        {"review": {"merge_recommendation": "changes_required"}},
        # Merge recommendation phrased with a space instead of underscore
        {"review": {"merge_recommendation": "changes required"}},
        # Merge recommendation says it's safe, but security concerns are present
        {
            "review": {
                "merge_recommendation": "safe_to_merge",
                "security_concerns": "SQL injection possible in the login handler.",
            }
        },
        # Merge recommendation says it's safe, but a key issue is high severity
        {
            "review": {
                "merge_recommendation": "safe_to_merge",
                "key_issues_to_review": [
                    {"issue_header": "Security vulnerability", "issue_content": "Auth bypass."}
                ],
            }
        },
    ],
    ids=["changes_required", "changes_required_spaced", "security_concerns", "high_severity_issue"],
)
def test_pr_reviewer_run_requests_changes_for_findings_beyond_merge_rec(prediction_data):
    snapshot = snapshot_settings([
        "config.publish_output",
        "pr_reviewer.enable_request_changes",
        "pr_reviewer.require_merge_recommendation",
    ])
    try:
        get_settings().set("config.publish_output", True)
        get_settings().set("pr_reviewer.enable_request_changes", True)
        get_settings().set("pr_reviewer.require_merge_recommendation", False)

        reviewer = _make_reviewer_for_run(prediction_data)

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

        reviewer.git_provider.request_changes.assert_called_once_with("Prepared review body")
    finally:
        restore_settings(snapshot)


def test_pr_reviewer_run_does_not_request_changes_when_no_findings_warrant_it():
    snapshot = snapshot_settings([
        "config.publish_output",
        "pr_reviewer.enable_request_changes",
        "pr_reviewer.require_merge_recommendation",
    ])
    try:
        get_settings().set("config.publish_output", True)
        get_settings().set("pr_reviewer.enable_request_changes", True)
        get_settings().set("pr_reviewer.require_merge_recommendation", False)

        prediction_data = {
            "review": {
                "merge_recommendation": "safe_to_merge",
                "security_concerns": "No security concerns identified.",
                "key_issues_to_review": [
                    {"issue_header": "Style nit", "issue_content": "Consider renaming this variable."}
                ],
            }
        }
        reviewer = _make_reviewer_for_run(prediction_data)

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

        reviewer.git_provider.request_changes.assert_not_called()
    finally:
        restore_settings(snapshot)
