"""Tests for GitHub issue extractor."""

from typing import Any

import pytest
from pytest_mock import MockerFixture

from pr2md.exceptions import GitHubAPIError
from pr2md.issue_extractor import GitHubIssueExtractor

# pylint: disable=protected-access  # testing private attributes


class TestGitHubIssueExtractor:
    """Tests for GitHubIssueExtractor class."""

    def test_initialization(self) -> None:
        """Test extractor initialization."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)
        assert extractor.owner == "owner"
        assert extractor.repo == "repo"
        assert extractor.issue_number == 123
        assert extractor._client is not None

    def test_fetch_issue_details(
        self, mocker: MockerFixture, sample_issue_dict: dict[str, Any]
    ) -> None:
        """Test fetching issue details."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)
        mocker.patch.object(extractor._client, "get", return_value=sample_issue_dict)

        issue = extractor.fetch_issue_details()
        assert issue.number == 456
        assert issue.title == "Test Issue"
        assert issue.state == "open"
        assert issue.user.login == "author"

    def test_fetch_comments(self, mocker: MockerFixture) -> None:
        """Test fetching issue comments."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)
        mock_data = [
            {
                "id": 1,
                "user": {
                    "login": "commenter",
                    "id": 2,
                    "avatar_url": "https://example.com/avatar.jpg",
                    "html_url": "https://github.com/commenter",
                },
                "body": "Test comment",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
                "html_url": "https://github.com/owner/repo/issues/123#issuecomment-1",
            }
        ]
        mocker.patch.object(extractor._client, "get_paginated", return_value=mock_data)

        comments = extractor.fetch_comments()
        assert len(comments) == 1
        assert comments[0].body == "Test comment"

    def test_extract_all(self, mocker: MockerFixture) -> None:
        """Test extracting all issue data."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)

        mock_issue = mocker.Mock()
        mock_comments = [mocker.Mock()]

        mocker.patch.object(extractor, "fetch_issue_details", return_value=mock_issue)
        mocker.patch.object(extractor, "fetch_comments", return_value=mock_comments)

        issue, comments = extractor.extract_all()

        assert issue == mock_issue
        assert comments == mock_comments

    def test_404_error(self, mocker: MockerFixture) -> None:
        """Test handling of 404 errors."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)
        mocker.patch.object(
            extractor._client,
            "get",
            side_effect=GitHubAPIError("Resource not found"),
        )

        with pytest.raises(GitHubAPIError, match="Resource not found"):
            extractor.fetch_issue_details()

    def test_issue_with_labels(self, mocker: MockerFixture) -> None:
        """Test fetching issue with labels."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)
        mock_data = {
            "number": 123,
            "title": "Test Issue",
            "body": "This is a test issue",
            "state": "open",
            "user": {
                "login": "testuser",
                "id": 1,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/testuser",
            },
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
            "closed_at": None,
            "html_url": "https://github.com/owner/repo/issues/123",
            "labels": [
                {
                    "name": "bug",
                    "color": "d73a4a",
                    "description": "Something isn't working",
                },
                {"name": "help wanted", "color": "008672", "description": None},
            ],
        }
        mocker.patch.object(extractor._client, "get", return_value=mock_data)

        issue = extractor.fetch_issue_details()
        assert len(issue.labels) == 2
        assert issue.labels[0].name == "bug"
        assert issue.labels[1].name == "help wanted"

    def test_closed_issue(self, mocker: MockerFixture) -> None:
        """Test fetching closed issue."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)
        mock_data = {
            "number": 123,
            "title": "Test Issue",
            "body": "This is a test issue",
            "state": "closed",
            "user": {
                "login": "testuser",
                "id": 1,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/testuser",
            },
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
            "closed_at": "2025-01-03T00:00:00Z",
            "html_url": "https://github.com/owner/repo/issues/123",
            "labels": [],
        }
        mocker.patch.object(extractor._client, "get", return_value=mock_data)

        issue = extractor.fetch_issue_details()
        assert issue.state == "closed"
        assert issue.closed_at is not None

    def test_context_manager_closes_client(self, mocker: MockerFixture) -> None:
        """Test that context manager closes the owned client."""
        with GitHubIssueExtractor("owner", "repo", 123) as extractor:
            mock_close = mocker.patch.object(extractor._client, "close")
        mock_close.assert_called_once()
