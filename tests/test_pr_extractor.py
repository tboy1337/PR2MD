"""Tests for PR extractor."""

# pylint: disable=protected-access  # testing private methods
# pylint: disable=duplicate-code  # some duplication in test data is expected

import pytest
from pytest_mock import MockerFixture

from pr2md.exceptions import GitHubAPIError
from pr2md.pr_extractor import GitHubPRExtractor


class TestGitHubPRExtractor:
    """Tests for GitHubPRExtractor class."""

    def test_initialization(self) -> None:
        """Test extractor initialization."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        assert extractor.owner == "owner"
        assert extractor.repo == "repo"
        assert extractor.pr_number == 123
        assert extractor.base_url == "https://api.github.com"

    def test_make_request_404_error(self, mocker: MockerFixture) -> None:
        """Test handling of 404 errors."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_response = mocker.Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mocker.patch.object(extractor.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Resource not found"):
            extractor._make_request("/test")

    def test_make_request_403_rate_limit(self, mocker: MockerFixture) -> None:
        """Test handling of rate limit errors."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_response = mocker.Mock()
        mock_response.status_code = 403
        mock_response.text = "API rate limit exceeded"
        mocker.patch.object(extractor.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="rate limit"):
            extractor._make_request("/test")

    def test_make_request_403_forbidden(self, mocker: MockerFixture) -> None:
        """Test handling of forbidden errors."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_response = mocker.Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mocker.patch.object(extractor.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Access forbidden"):
            extractor._make_request("/test")

    def test_make_request_other_error(self, mocker: MockerFixture) -> None:
        """Test handling of other HTTP errors."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_response = mocker.Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mocker.patch.object(extractor.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="request failed with status 500"):
            extractor._make_request("/test")

    def test_make_request_success_json(self, mocker: MockerFixture) -> None:
        """Test successful JSON request."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}
        mocker.patch.object(extractor.session, "get", return_value=mock_response)

        result = extractor._make_request("/test")
        assert result == {"key": "value"}

    def test_make_request_success_diff(self, mocker: MockerFixture) -> None:
        """Test successful diff request."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "diff content"
        mocker.patch.object(extractor.session, "get", return_value=mock_response)

        result = extractor._make_request(
            "/test", accept_header="application/vnd.github.v3.diff"
        )
        assert result == "diff content"

    def test_fetch_pr_details(self, mocker: MockerFixture) -> None:
        """Test fetching PR details."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_data = {
            "number": 123,
            "title": "Test PR",
            "body": "Description",
            "state": "open",
            "user": {
                "login": "author",
                "id": 1,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/author",
            },
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
            "closed_at": None,
            "merged_at": None,
            "merge_commit_sha": None,
            "html_url": "https://github.com/owner/repo/pull/123",
            "labels": [],
            "additions": 10,
            "deletions": 5,
            "changed_files": 2,
            "head": {"ref": "feature", "sha": "abc123"},
            "base": {"ref": "main", "sha": "def456"},
        }
        mocker.patch.object(extractor, "_make_request", return_value=mock_data)

        pull_request = extractor.fetch_pr_details()
        assert pull_request.number == 123
        assert pull_request.title == "Test PR"

    def test_fetch_comments(self, mocker: MockerFixture) -> None:
        """Test fetching comments."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_data = [
            {
                "id": 1,
                "user": {
                    "login": "user1",
                    "id": 1,
                    "avatar_url": "https://example.com/avatar.jpg",
                    "html_url": "https://github.com/user1",
                },
                "body": "Comment 1",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
                "html_url": "https://github.com/owner/repo/issues/123#issuecomment-1",
            }
        ]
        mocker.patch.object(extractor, "_make_request", return_value=mock_data)

        comments = extractor.fetch_comments()
        assert len(comments) == 1
        assert comments[0].id == 1

    def test_fetch_review_comments(self, mocker: MockerFixture) -> None:
        """Test fetching review comments."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_data = [
            {
                "id": 1,
                "user": {
                    "login": "reviewer",
                    "id": 2,
                    "avatar_url": "https://example.com/avatar.jpg",
                    "html_url": "https://github.com/reviewer",
                },
                "body": "Review comment",
                "path": "file.py",
                "position": 10,
                "original_position": 10,
                "commit_id": "abc123",
                "original_commit_id": "abc123",
                "diff_hunk": "@@ -1,1 +1,1 @@\n-old\n+new",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
                "html_url": "https://github.com/owner/repo/pull/123#discussion_r1",
                "in_reply_to_id": None,
            }
        ]
        mocker.patch.object(extractor, "_make_request", return_value=mock_data)

        review_comments = extractor.fetch_review_comments()
        assert len(review_comments) == 1
        assert review_comments[0].path == "file.py"

    def test_fetch_reviews(self, mocker: MockerFixture) -> None:
        """Test fetching reviews."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_data = [
            {
                "id": 1,
                "user": {
                    "login": "approver",
                    "id": 3,
                    "avatar_url": "https://example.com/avatar.jpg",
                    "html_url": "https://github.com/approver",
                },
                "body": "LGTM",
                "state": "APPROVED",
                "html_url": (
                    "https://github.com/owner/repo/pull/123#pullrequestreview-1"
                ),
                "submitted_at": "2025-01-02T00:00:00Z",
                "commit_id": "abc123",
            }
        ]
        mocker.patch.object(extractor, "_make_request", return_value=mock_data)

        reviews = extractor.fetch_reviews()
        assert len(reviews) == 1
        assert reviews[0].state == "APPROVED"

    def test_fetch_diff(self, mocker: MockerFixture) -> None:
        """Test fetching diff."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_diff = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py"
        mocker.patch.object(extractor, "_make_request", return_value=mock_diff)

        diff = extractor.fetch_diff()
        assert "diff --git" in diff

    def test_extract_all(self, mocker: MockerFixture) -> None:
        """Test extracting all PR data."""
        extractor = GitHubPRExtractor("owner", "repo", 123)

        # Mock all fetch methods
        mock_pr = mocker.Mock()
        mock_comments = [mocker.Mock()]
        mock_reviews = [mocker.Mock()]
        mock_review_comments = [mocker.Mock()]
        mock_diff = "diff content"

        mocker.patch.object(extractor, "fetch_pr_details", return_value=mock_pr)
        mocker.patch.object(extractor, "fetch_comments", return_value=mock_comments)
        mocker.patch.object(extractor, "fetch_reviews", return_value=mock_reviews)
        mocker.patch.object(
            extractor, "fetch_review_comments", return_value=mock_review_comments
        )
        mocker.patch.object(extractor, "fetch_diff", return_value=mock_diff)

        pull_request, comments, reviews, review_comments, diff = extractor.extract_all()

        assert pull_request == mock_pr
        assert comments == mock_comments
        assert reviews == mock_reviews
        assert review_comments == mock_review_comments
        assert diff == mock_diff
