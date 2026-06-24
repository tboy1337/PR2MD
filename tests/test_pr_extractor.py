"""Tests for PR extractor."""

import logging
from typing import Any

import pytest
from pytest_mock import MockerFixture

from pr2md.exceptions import GitHubAPIError
from pr2md.pr_extractor import GitHubPRExtractor

# pylint: disable=protected-access  # testing private attributes


class TestGitHubPRExtractor:
    """Tests for GitHubPRExtractor class."""

    def test_initialization(self) -> None:
        """Test extractor initialization."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        assert extractor.owner == "owner"
        assert extractor.repo == "repo"
        assert extractor.pr_number == 123
        assert extractor._client is not None

    def test_fetch_pr_details(
        self, mocker: MockerFixture, sample_pr_dict: dict[str, Any]
    ) -> None:
        """Test fetching PR details."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mocker.patch.object(extractor._client, "get", return_value=sample_pr_dict)

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
        mocker.patch.object(extractor._client, "get_paginated", return_value=mock_data)

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
        mocker.patch.object(extractor._client, "get_paginated", return_value=mock_data)

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
        mocker.patch.object(extractor._client, "get_paginated", return_value=mock_data)

        reviews = extractor.fetch_reviews()
        assert len(reviews) == 1
        assert reviews[0].state == "APPROVED"

    def test_fetch_diff(self, mocker: MockerFixture) -> None:
        """Test fetching diff."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mock_diff = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py"
        mocker.patch.object(extractor._client, "get", return_value=mock_diff)

        diff = extractor.fetch_diff()
        assert "diff --git" in diff

    def test_extract_all(self, mocker: MockerFixture) -> None:
        """Test extracting all PR data."""
        extractor = GitHubPRExtractor("owner", "repo", 123)

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

    def test_context_manager_closes_client(self, mocker: MockerFixture) -> None:
        """Test that context manager closes the owned client."""
        with GitHubPRExtractor("owner", "repo", 123) as extractor:
            mock_close = mocker.patch.object(extractor._client, "close")
        mock_close.assert_called_once()

    def test_fetch_pr_details_api_error(self, mocker: MockerFixture) -> None:
        """Test API errors propagate from fetch_pr_details."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        mocker.patch.object(
            extractor._client,
            "get",
            side_effect=GitHubAPIError("Resource not found"),
        )

        with pytest.raises(GitHubAPIError, match="Resource not found"):
            extractor.fetch_pr_details()

    def test_fetch_diff_logs_large_diff(
        self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test large diff triggers informational log but returns full content."""
        extractor = GitHubPRExtractor("owner", "repo", 123)
        large_diff = "x" * (6 * 1024 * 1024)
        mocker.patch.object(extractor._client, "get", return_value=large_diff)

        with caplog.at_level(logging.INFO, logger="pr2md.pr_extractor"):
            diff = extractor.fetch_diff()

        assert diff == large_diff
        assert any("large" in record.message.lower() for record in caplog.records)
