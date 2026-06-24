"""Tests for reference downloader."""

import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from pr2md.exceptions import GitHubAPIError
from pr2md.models import Comment, Issue, PullRequest, User
from pr2md.reference_downloader import ReferenceDownloader
from pr2md.reference_parser import GitHubReference

# pylint: disable=protected-access,too-many-public-methods


class TestReferenceDownloader:
    """Tests for ReferenceDownloader class."""

    @pytest.fixture
    def sample_user(self) -> User:
        """Create a sample user."""
        return User(
            login="testuser",
            id=1,
            avatar_url="https://example.com/avatar.jpg",
            html_url="https://github.com/testuser",
        )

    @pytest.fixture
    def sample_pr(self, sample_user: User) -> PullRequest:
        """Create a sample pull request."""
        return PullRequest(
            number=1,
            title="Test PR",
            body="Fixes #123 and owner/repo#456",
            state="open",
            user=sample_user,
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            closed_at=None,
            merged_at=None,
            merge_commit_sha=None,
            html_url="https://github.com/owner/repo/pull/1",
            labels=[],
            additions=10,
            deletions=5,
            changed_files=2,
            head_ref="feature",
            base_ref="main",
            head_sha="abc123",
            base_sha="def456",
        )

    @pytest.fixture
    def sample_issue(self, sample_user: User) -> Issue:
        """Create a sample issue."""
        return Issue(
            number=2,
            title="Test Issue",
            body="Related to #789",
            state="open",
            user=sample_user,
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            closed_at=None,
            html_url="https://github.com/owner/repo/issues/2",
            labels=[],
        )

    @pytest.fixture
    def sample_comment(self, sample_user: User) -> Comment:
        """Create a sample comment."""
        return Comment(
            id=1,
            user=sample_user,
            body="See also https://github.com/other/repo/pull/999",
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            html_url="https://github.com/owner/repo/issues/1#issuecomment-1",
        )

    def test_initialization(self) -> None:
        """Test downloader initialization."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=3)
        assert downloader.base_owner == "owner"
        assert downloader.base_repo == "repo"
        assert downloader.max_depth == 3

    def test_generate_filename_same_repo_pr(self) -> None:
        """Test filename generation for same-repo PR."""
        downloader = ReferenceDownloader("owner", "repo")
        filename = downloader.generate_filename("pr", "owner", "repo", 123)
        assert filename == "PR-123.md"

    def test_generate_filename_same_repo_issue(self) -> None:
        """Test filename generation for same-repo issue."""
        downloader = ReferenceDownloader("owner", "repo")
        filename = downloader.generate_filename("issue", "owner", "repo", 456)
        assert filename == "Issue-456.md"

    def test_generate_filename_cross_repo_pr(self) -> None:
        """Test filename generation for cross-repo PR."""
        downloader = ReferenceDownloader("owner", "repo")
        filename = downloader.generate_filename("pr", "other", "project", 789)
        assert filename == "other-project-PR-789.md"

    def test_generate_filename_cross_repo_issue(self) -> None:
        """Test filename generation for cross-repo issue."""
        downloader = ReferenceDownloader("owner", "repo")
        filename = downloader.generate_filename("issue", "other", "project", 123)
        assert filename == "other-project-Issue-123.md"

    def test_extract_references_from_pr(
        self, sample_pr: PullRequest, sample_comment: Comment
    ) -> None:
        """Test extracting references from PR data."""
        downloader = ReferenceDownloader("owner", "repo")
        comments = [sample_comment]
        references = downloader.extract_references_from_pr(sample_pr, comments, [], [])

        assert len(references) >= 2  # At least #123 and owner/repo#456 from PR body

    def test_extract_references_from_pr_includes_reviews(
        self, sample_pr: PullRequest, sample_comment: Comment
    ) -> None:
        """Test extracting references from review and review-comment bodies."""
        from datetime import datetime, timezone

        from pr2md.models import Review, ReviewComment, User

        downloader = ReferenceDownloader("owner", "repo")
        user = User(
            login="reviewer",
            id=1,
            avatar_url="https://example.com/a",
            html_url="https://github.com/reviewer",
        )
        reviews = [
            Review(
                id=1,
                user=user,
                body="See also #55",
                state="APPROVED",
                html_url="https://github.com/o/r/pull/1#pullrequestreview-1",
                submitted_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                commit_id="abc",
            )
        ]
        review_comments = [
            ReviewComment(
                id=2,
                user=user,
                body="Related: other/repo#99",
                path="file.py",
                position=1,
                original_position=1,
                commit_id="abc",
                original_commit_id="abc",
                diff_hunk="@@",
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                html_url="https://github.com/o/r/pull/1#discussion_r2",
                in_reply_to_id=None,
            )
        ]
        references = downloader.extract_references_from_pr(
            sample_pr, [sample_comment], reviews, review_comments
        )

        numbers = {ref.number for ref in references}
        assert 55 in numbers
        assert 99 in numbers

    def test_extract_references_from_issue(
        self, sample_issue: Issue, sample_comment: Comment
    ) -> None:
        """Test extracting references from issue data."""
        downloader = ReferenceDownloader("owner", "repo")
        comments = [sample_comment]
        references = downloader.extract_references_from_issue(sample_issue, comments)

        assert len(references) >= 1  # At least #789 from issue body

    def test_download_pr_success(self, mocker: MockerFixture) -> None:
        """Test successful PR download."""
        downloader = ReferenceDownloader("owner", "repo")

        # Mock the extractor
        mock_extractor = MagicMock()
        mock_extractor.extract_all.return_value = (
            mocker.Mock(
                number=1,
                title="Test",
                body="Test PR",
                state="open",
                user=mocker.Mock(login="user", html_url="url"),
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                closed_at=None,
                merged_at=None,
                merge_commit_sha=None,
                html_url="url",
                labels=[],
                additions=1,
                deletions=1,
                changed_files=1,
                head_ref="main",
                base_ref="main",
                head_sha="sha",
                base_sha="sha",
            ),
            [],
            [],
            [],
            "diff",
        )
        mock_extractor.__enter__.return_value = mock_extractor

        mocker.patch(
            "pr2md.reference_downloader.GitHubPRExtractor",
            return_value=mock_extractor,
        )

        markdown, refs = downloader.download_pr("owner", "repo", 1)
        assert markdown != ""
        assert refs is not None

    def test_download_pr_failure(self, mocker: MockerFixture) -> None:
        """Test PR download failure."""
        downloader = ReferenceDownloader("owner", "repo")

        # Mock the extractor to raise an exception
        mock_extractor = MagicMock()
        mock_extractor.extract_all.side_effect = ValueError("API Error")

        mock_extractor.__enter__.return_value = mock_extractor
        mock_extractor.__exit__.return_value = False

        mocker.patch(
            "pr2md.reference_downloader.GitHubPRExtractor",
            return_value=mock_extractor,
        )

        markdown, refs = downloader.download_pr("owner", "repo", 1)
        assert markdown == ""
        assert refs is None

    def test_download_issue_success(self, mocker: MockerFixture) -> None:
        """Test successful issue download."""
        downloader = ReferenceDownloader("owner", "repo")

        # Mock the extractor
        mock_extractor = MagicMock()
        mock_extractor.extract_all.return_value = (
            mocker.Mock(
                number=1,
                title="Test",
                body="Test Issue",
                state="open",
                user=mocker.Mock(login="user", html_url="url"),
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                closed_at=None,
                html_url="url",
                labels=[],
            ),
            [],
        )
        mock_extractor.__enter__.return_value = mock_extractor

        mocker.patch(
            "pr2md.reference_downloader.GitHubIssueExtractor",
            return_value=mock_extractor,
        )

        markdown, refs = downloader.download_issue("owner", "repo", 1)
        assert markdown != ""
        assert refs is not None

    def test_download_issue_failure(self, mocker: MockerFixture) -> None:
        """Test issue download failure."""
        downloader = ReferenceDownloader("owner", "repo")

        # Mock the extractor to raise an exception
        mock_extractor = MagicMock()
        mock_extractor.extract_all.side_effect = ValueError("API Error")

        mock_extractor.__enter__.return_value = mock_extractor
        mock_extractor.__exit__.return_value = False

        mocker.patch(
            "pr2md.reference_downloader.GitHubIssueExtractor",
            return_value=mock_extractor,
        )

        markdown, refs = downloader.download_issue("owner", "repo", 1)
        assert markdown == ""
        assert refs is None

    def test_determine_ref_type_pr(self, mocker: MockerFixture) -> None:
        """Test determining reference type for PR."""
        downloader = ReferenceDownloader("owner", "repo")
        mocker.patch.object(
            downloader._client,
            "fetch_issue_or_pr_type",
            return_value="pr",
        )

        ref_type = downloader.determine_ref_type("owner", "repo", 1)
        assert ref_type == "pr"

    def test_determine_ref_type_issue(self, mocker: MockerFixture) -> None:
        """Test determining reference type for issue."""
        downloader = ReferenceDownloader("owner", "repo")
        mocker.patch.object(
            downloader._client,
            "fetch_issue_or_pr_type",
            return_value="issue",
        )

        ref_type = downloader.determine_ref_type("owner", "repo", 1)
        assert ref_type == "issue"

    def test_determine_ref_type_not_found(self, mocker: MockerFixture) -> None:
        """Test determining reference type when not found."""
        downloader = ReferenceDownloader("owner", "repo")
        mocker.patch.object(
            downloader._client,
            "fetch_issue_or_pr_type",
            return_value=None,
        )

        ref_type = downloader.determine_ref_type("owner", "repo", 1)
        assert ref_type is None

    def test_download_reference_already_downloaded(self) -> None:
        """Test that already downloaded references are skipped."""
        downloader = ReferenceDownloader("owner", "repo")
        ref = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=1)

        downloader._downloaded_keys.add(("owner", "repo", 1))

        files = downloader.download_reference(ref, current_depth=1)
        assert len(files) == 0

    def test_skips_already_downloaded_by_number(self, mocker: MockerFixture) -> None:
        """Test duplicate references with different types skip second download."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=1)
        ref_pr = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=1)
        ref_issue = GitHubReference(
            ref_type="issue", owner="owner", repo="repo", number=1
        )

        mocker.patch.object(downloader, "determine_ref_type", return_value="pr")
        mocker.patch.object(
            downloader,
            "_download_and_format",
            return_value=("# PR", set(), False),
        )
        mocker.patch("pr2md.reference_downloader.write_text_atomic")

        first = downloader.download_reference(ref_pr, current_depth=1)
        second = downloader.download_reference(ref_issue, current_depth=1)

        assert len(first) == 1
        assert len(second) == 0

    def test_log_skipped_summary(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test skipped reference summary is logged."""
        downloader = ReferenceDownloader("owner", "repo")
        ref = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=9)
        downloader.record_skipped_reference(ref, "not found")

        with caplog.at_level(logging.ERROR):
            downloader.log_skipped_summary()

        assert "Failed to download 1 referenced item(s)" in caplog.text
        assert "owner/repo #9" in caplog.text

    def test_log_download_error_verbose_traceback(
        self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test verbose mode logs traceback for unexpected download errors."""
        downloader = ReferenceDownloader("owner", "repo", verbose=True)
        mocker.patch.object(
            downloader,
            "_format_pr_reference",
            side_effect=ValueError("boom"),
        )

        with caplog.at_level(logging.ERROR):
            downloader.download_pr("owner", "repo", 1)

        assert any(
            "Unexpected error downloading PR" in r.message for r in caplog.records
        )

    def test_download_reference_depth_limit(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that depth limit is respected and logged at INFO."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=1)
        ref = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=1)

        with caplog.at_level(logging.INFO):
            files = downloader.download_reference(ref, current_depth=2)

        assert len(files) == 0
        assert "depth limit" in caplog.text.lower()
        assert len(downloader.skipped_depth_references) == 1
        assert not downloader.had_download_failures

    def test_log_skipped_summary_empty(self) -> None:
        """Test skipped summary is a no-op when nothing failed."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=1)
        downloader.log_skipped_summary()

    def test_download_reference_url_type_fallback(self, mocker: MockerFixture) -> None:
        """Test fallback to alternate type when URL path mismatches resource."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=1)
        ref = GitHubReference(
            ref_type="pr",
            owner="owner",
            repo="repo",
            number=1,
            from_url=True,
        )

        mocker.patch.object(downloader, "determine_ref_type", return_value="pr")
        mocker.patch.object(
            downloader,
            "_download_and_format",
            side_effect=[("", None, True), ("# Issue", set(), False)],
        )
        mocker.patch("pr2md.reference_downloader.write_text_atomic")

        files = downloader.download_reference(ref, current_depth=1)
        assert files == ["Issue-1.md"]

    def test_download_reference_pr_type_fallback(self, mocker: MockerFixture) -> None:
        """Test fallback to PR download when issue download fails."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=1)
        ref = GitHubReference(
            ref_type="issue",
            owner="owner",
            repo="repo",
            number=1,
        )

        mocker.patch.object(downloader, "determine_ref_type", return_value="issue")
        mocker.patch.object(
            downloader,
            "_download_and_format",
            side_effect=[("", None, True), ("# Pull Request", set(), False)],
        )
        mocker.patch("pr2md.reference_downloader.write_text_atomic")

        files = downloader.download_reference(ref, current_depth=1)
        assert files == ["PR-1.md"]

    def test_download_reference_success(self, mocker: MockerFixture) -> None:
        """Test successful reference download."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=2)
        ref = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=1)

        # Mock determine_ref_type
        mocker.patch.object(downloader, "determine_ref_type", return_value="pr")

        # Mock download
        mocker.patch.object(
            downloader,
            "_download_and_format",
            return_value=("# Test PR", set(), False),
        )

        # Mock file write
        mock_write = mocker.patch("pr2md.reference_downloader.write_text_atomic")

        files = downloader.download_reference(ref, current_depth=1)
        assert len(files) == 1
        assert files[0] == "PR-1.md"
        mock_write.assert_called_once()

    def test_download_all_references(self, mocker: MockerFixture) -> None:
        """Test downloading all references."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=1)

        ref1 = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=1)
        ref2 = GitHubReference(ref_type="issue", owner="owner", repo="repo", number=2)

        # Mock download_reference
        mocker.patch.object(
            downloader,
            "download_reference",
            side_effect=[["PR-1.md"], ["Issue-2.md"]],
        )

        files = downloader.download_all_references({ref1, ref2})
        assert len(files) == 2
        assert "PR-1.md" in files
        assert "Issue-2.md" in files

    def test_download_reference_recursive(self, mocker: MockerFixture) -> None:
        """Test recursive reference download."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=2)
        child_ref = GitHubReference(
            ref_type="issue", owner="owner", repo="repo", number=2
        )
        ref = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=1)

        mocker.patch.object(
            downloader,
            "determine_ref_type",
            side_effect=lambda _o, _r, number: "pr" if number == 1 else "issue",
        )
        mocker.patch.object(
            downloader,
            "_download_and_format",
            side_effect=lambda ref_type, _o, _r, number: (
                ("# PR", {child_ref}, False)
                if number == 1
                else ("# Issue", set(), False)
            ),
        )
        mocker.patch("pr2md.reference_downloader.write_text_atomic")

        files = downloader.download_reference(ref, current_depth=1)
        assert "PR-1.md" in files
        assert "Issue-2.md" in files

    def test_download_reference_write_failure(self, mocker: MockerFixture) -> None:
        """Test reference download when file write fails."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=2)
        ref = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=1)

        mocker.patch.object(downloader, "determine_ref_type", return_value="pr")
        mocker.patch.object(
            downloader,
            "_download_and_format",
            return_value=("# Test PR", set(), False),
        )
        mocker.patch(
            "pr2md.reference_downloader.write_text_atomic",
            side_effect=OSError("disk full"),
        )

        files = downloader.download_reference(ref, current_depth=1)
        assert not files
        assert len(downloader.skipped_references) == 1

    def test_download_reference_type_not_found_records_skip(
        self, mocker: MockerFixture
    ) -> None:
        """Test skipped reference recorded when type cannot be determined."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=2)
        ref = GitHubReference(
            ref_type="pr",
            owner="owner",
            repo="repo",
            number=1,
            from_url=False,
        )
        mocker.patch.object(downloader, "determine_ref_type", return_value=None)

        files = downloader.download_reference(ref, current_depth=1)
        assert not files
        assert downloader.had_download_failures is True
        assert len(downloader.skipped_references) == 1

    def test_download_pr_github_api_error(self, mocker: MockerFixture) -> None:
        """Test PR download handles GitHubAPIError."""
        downloader = ReferenceDownloader("owner", "repo")
        mock_extractor = MagicMock()
        mock_extractor.extract_all.side_effect = GitHubAPIError("not found")
        mock_extractor.__enter__.return_value = mock_extractor
        mocker.patch(
            "pr2md.reference_downloader.GitHubPRExtractor",
            return_value=mock_extractor,
        )

        markdown, refs = downloader.download_pr("owner", "repo", 1)
        assert markdown == ""
        assert refs is None

    def test_context_manager_closes_client(self, mocker: MockerFixture) -> None:
        """Test that context manager closes the owned client."""
        with ReferenceDownloader("owner", "repo", max_depth=1) as downloader:
            mock_close = mocker.patch.object(downloader._client, "close")
        mock_close.assert_called_once()

    def test_write_failure_allows_retry_in_same_session(
        self, mocker: MockerFixture
    ) -> None:
        """Failed writes must not mark a reference as downloaded."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=2)
        ref = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=1)

        mocker.patch.object(downloader, "determine_ref_type", return_value="pr")
        mocker.patch.object(
            downloader,
            "_download_and_format",
            return_value=("# Test PR", set(), False),
        )
        mock_write = mocker.patch(
            "pr2md.reference_downloader.write_text_atomic",
            side_effect=[OSError("disk full"), None],
        )

        first_attempt = downloader.download_reference(ref, current_depth=1)
        assert not first_attempt
        assert ref not in downloader.downloaded

        second_attempt = downloader.download_reference(ref, current_depth=1)
        assert second_attempt == ["PR-1.md"]
        assert ref in downloader.downloaded
        assert mock_write.call_count == 2


class TestReferenceDownloadEfficiency:
    """Tests for reference download API efficiency."""

    def test_fetch_reference_markdown_skips_alternate_on_non_404(
        self, mocker: MockerFixture
    ) -> None:
        """Test alternate type is not tried when primary failure is not a 404."""
        downloader = ReferenceDownloader("owner", "repo")
        mock_format = mocker.patch.object(
            downloader, "_download_and_format", return_value=("", None, False)
        )

        markdown, refs, ref_type = downloader._fetch_reference_markdown(
            "pr", "owner", "repo", 1
        )

        assert markdown == ""
        assert refs is None
        assert ref_type == "pr"
        mock_format.assert_called_once()

    def test_download_issue_github_api_error(self, mocker: MockerFixture) -> None:
        """Test issue download handles GitHubAPIError."""
        downloader = ReferenceDownloader("owner", "repo")
        mock_extractor = MagicMock()
        mock_extractor.extract_all.side_effect = GitHubAPIError("not found")
        mock_extractor.__enter__.return_value = mock_extractor
        mocker.patch(
            "pr2md.reference_downloader.GitHubIssueExtractor",
            return_value=mock_extractor,
        )

        markdown, refs = downloader.download_issue("owner", "repo", 1)
        assert markdown == ""
        assert refs is None

    def test_download_all_references_max_depth_zero(
        self, mocker: MockerFixture
    ) -> None:
        """Test depth 0 still downloads top-level references without recursion."""
        downloader = ReferenceDownloader("owner", "repo", max_depth=0)
        ref = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=1)

        mocker.patch.object(
            downloader,
            "download_reference",
            return_value=["PR-1.md"],
        )

        files = downloader.download_all_references({ref})
        assert files == ["PR-1.md"]
