"""Integration tests with real GitHub API."""

# pylint: disable=duplicate-code  # some duplication in test assertions is expected

import pytest

from pr2md.formatter import MarkdownFormatter
from pr2md.pr_extractor import GitHubPRExtractor


@pytest.mark.integration
class TestIntegration:
    """Integration tests with real GitHub API."""

    @pytest.mark.timeout(60)
    def test_extract_real_pr(self) -> None:
        """Test extracting a real PR from psf/requests."""
        # https://github.com/psf/requests/pull/6523
        extractor = GitHubPRExtractor("psf", "requests", 6523)

        # Fetch all data
        pull_request, comments, reviews, review_comments, diff = extractor.extract_all()

        # Verify PR details
        assert pull_request.number == 6523
        assert pull_request.title is not None
        assert len(pull_request.title) > 0
        assert pull_request.user.login is not None

        # Verify we got some data (exact counts may change)
        # Just check that extraction worked
        assert pull_request.additions >= 0
        assert pull_request.deletions >= 0
        assert pull_request.changed_files >= 0

        # Comments, reviews, and review_comments may be 0 or more
        assert isinstance(comments, list)
        assert isinstance(reviews, list)
        assert isinstance(review_comments, list)

        # Verify diff exists
        assert isinstance(diff, str)
        assert len(diff) > 0

        # Format as Markdown
        markdown = MarkdownFormatter.format_pr(
            pull_request, comments, reviews, review_comments, diff
        )

        # Verify markdown structure
        assert "# " in markdown
        assert "## Description" in markdown
        assert "## Changes Summary" in markdown
        assert "## Code Diff" in markdown
        assert "## Conversation Thread" in markdown
        assert "## Reviews" in markdown
        assert "## Review Comments" in markdown

        # Verify PR number in markdown
        assert "6523" in markdown

        # Verify some basic content
        assert "psf/requests" in markdown or "requests" in markdown.lower()

    @pytest.mark.timeout(30)
    def test_extract_with_all_features(self) -> None:
        """Test with a PR that has comments, reviews, and review comments."""
        # This is the same PR, which should have various features
        extractor = GitHubPRExtractor("psf", "requests", 6523)

        pull_request = extractor.fetch_pr_details()
        assert pull_request.number == 6523

        comments = extractor.fetch_comments()
        assert isinstance(comments, list)

        reviews = extractor.fetch_reviews()
        assert isinstance(reviews, list)

        review_comments = extractor.fetch_review_comments()
        assert isinstance(review_comments, list)

        diff = extractor.fetch_diff()
        assert isinstance(diff, str)
        assert len(diff) > 0

    @pytest.mark.timeout(60)
    def test_extract_real_issue(self) -> None:
        """Test extracting a real issue from psf/requests."""
        from pr2md.issue_extractor import GitHubIssueExtractor

        extractor = GitHubIssueExtractor("psf", "requests", 1)
        issue, comments = extractor.extract_all()

        assert issue.number == 1
        assert issue.title is not None
        assert len(issue.title) > 0
        assert isinstance(comments, list)

        from pr2md.formatter import MarkdownFormatter

        markdown = MarkdownFormatter.format_issue(issue, comments)
        assert "# " in markdown
        assert "## Description" in markdown
        assert "## Conversation Thread" in markdown
