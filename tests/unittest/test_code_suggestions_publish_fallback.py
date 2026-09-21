import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from pr_agent.algo.types import FilePatchInfo
from pr_agent.config_loader import get_settings
from pr_agent.git_providers.github_provider import GithubProvider
from pr_agent.tools import pr_code_suggestions as pr_code_suggestions_module
from pr_agent.tools.pr_code_suggestions import PRCodeSuggestions
from tests.unittest._settings_helpers import restore_settings, snapshot_settings


class _FakeGithubException(Exception):
    def __init__(self, status, message="error"):
        super().__init__(f"GithubException status={status}: {message}")
        self.status = status


_TRACKED_SETTINGS = (
    "config.publish_output",
    "config.publish_output_progress",
    "config.is_auto_command",
    "config.propagate_tool_errors",
    "pr_code_suggestions.commitable_code_suggestions",
    "pr_code_suggestions.dual_publishing_score_threshold",
    "pr_code_suggestions.persistent_comment",
    "github.publish_as_check_run",
)


def _make_tool(provider):
    provider.should_publish_improve_as_thread.return_value = False
    tool = PRCodeSuggestions.__new__(PRCodeSuggestions)
    tool.git_provider = provider
    tool.pr_url = "https://example.invalid/pull/1"
    tool.progress_response = None
    tool.incremental = SimpleNamespace(is_incremental=False)
    return tool


def _valid_suggestions_payload():
    return {
        "code_suggestions": [
            {
                "one_sentence_summary": "Use a helper method",
                "relevant_file": "src/example.py",
                "relevant_lines_start": 1,
                "relevant_lines_end": 2,
                "suggestion_content": "Use helper method instead of manual loop",
                "existing_code": "for x in items:\n    process(x)",
                "improved_code": "process_all(items)",
                "label": "best practice",
                "score": 9,
            }
        ]
    }


@pytest.mark.asyncio
async def test_run_falls_back_to_summary_when_inline_publishing_fails(monkeypatch):
    settings_snapshot = snapshot_settings(_TRACKED_SETTINGS)
    try:
        provider = MagicMock()
        provider.get_files.return_value = [object()]
        provider.is_supported.return_value = True
        provider.supports_code_suggestions_artifact.return_value = False
        provider.publish_code_suggestions.return_value = False
        provider.get_issue_comments.return_value = []
        provider.get_latest_commit_url.return_value = "https://example.invalid/commit/abcdef"

        tool = _make_tool(provider)
        tool._validate_suggestion = MagicMock(return_value=(True, "", True))
        tool.dedent_code = MagicMock(side_effect=lambda _f, _l, code: code)

        monkeypatch.setattr(
            pr_code_suggestions_module,
            "retry_with_fallback_models",
            AsyncMock(return_value=_valid_suggestions_payload()),
        )

        settings = get_settings()
        settings.config.publish_output = True
        settings.config.publish_output_progress = False
        settings.config.is_auto_command = True
        settings.pr_code_suggestions.commitable_code_suggestions = True
        settings.pr_code_suggestions.persistent_comment = False

        await tool.run()

        # Must not post the misleading failure comment
        published_bodies = [call.args[0] for call in provider.publish_comment.call_args_list if call.args]
        assert not any("Failed to generate code suggestions for PR" in b for b in published_bodies), \
            f"Posted failure comment unexpectedly: {published_bodies}"
        # Must have published the suggestions via fallback comment
        assert any("Use helper method instead of manual loop" in b for b in published_bodies), \
            f"Suggestions were silently dropped; published comments: {published_bodies}"
    finally:
        restore_settings(settings_snapshot)


@pytest.mark.asyncio
async def test_run_falls_back_to_summary_on_github_403_create_review(monkeypatch):
    settings_snapshot = snapshot_settings(_TRACKED_SETTINGS)
    try:
        provider = GithubProvider.__new__(GithubProvider)
        provider.pr = MagicMock()
        provider.repo_obj = MagicMock()
        provider.last_commit_id = "abcdef1234567890"
        diff_file = FilePatchInfo(
            base_file="src/example.py",
            head_file="src/example.py",
            patch="@@ -1,5 +1,5 @@\n for x in items:\n     process(x)\n",
            filename="src/example.py",
        )
        provider.get_diff_files = MagicMock(return_value=[diff_file])
        provider.get_files = MagicMock(return_value=[diff_file])
        provider.get_issue_comments = MagicMock(return_value=[])
        provider.get_latest_commit_url = MagicMock(return_value="https://github.com/org/repo/commit/abcdef")
        provider.publish_comment = MagicMock()
        provider.remove_initial_comment = MagicMock()
        provider.should_publish_improve_as_thread = MagicMock(return_value=False)
        provider.supports_code_suggestions_artifact = MagicMock(return_value=False)
        provider.can_verify_inline_comment_publication = MagicMock(return_value=True)
        provider.is_supported = MagicMock(return_value=True)

        # Simulate 403 Forbidden on create_review (both batch and individual retries)
        provider.pr.create_review.side_effect = _FakeGithubException(
            status=403, message="Resource not accessible by integration"
        )

        tool = _make_tool(provider)
        tool._validate_suggestion = MagicMock(return_value=(True, "", True))
        tool.dedent_code = MagicMock(side_effect=lambda _f, _l, code: code)

        monkeypatch.setattr(
            pr_code_suggestions_module,
            "retry_with_fallback_models",
            AsyncMock(return_value=_valid_suggestions_payload()),
        )

        settings = get_settings()
        settings.config.publish_output = True
        settings.config.publish_output_progress = False
        settings.config.is_auto_command = True
        settings.pr_code_suggestions.commitable_code_suggestions = True
        settings.pr_code_suggestions.persistent_comment = False

        await tool.run()

        # Must not post the misleading failure comment
        published_bodies = [call.args[0] for call in provider.publish_comment.call_args_list if call.args]
        assert not any("Failed to generate code suggestions for PR" in b for b in published_bodies), \
            f"Posted failure comment unexpectedly: {published_bodies}"
        # Must have published the suggestions via fallback comment
        assert any("Use helper method instead of manual loop" in b for b in published_bodies), \
            f"Suggestions were silently dropped; published comments: {published_bodies}"
    finally:
        restore_settings(settings_snapshot)
