"""Tests for GitHub issue extractor."""

import pytest
from pytest_mock import MockerFixture

from pr2md.exceptions import GitHubAPIError
from pr2md.issue_extractor import GitHubIssueExtractor


class TestGitHubIssueExtractor:
    """Tests for GitHubIssueExtractor class."""

    def test_initialization(self) -> None:
        """Test extractor initialization."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)
        assert extractor.owner == "owner"
        assert extractor.repo == "repo"
        assert extractor.issue_number == 123
        assert extractor.base_url == "https://api.github.com"

    def test_fetch_issue_details(self, mocker: MockerFixture) -> None:
        """Test fetching issue details."""
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
            "labels": [],
        }
        mocker.patch.object(extractor, "_make_request", return_value=mock_data)

        issue = extractor.fetch_issue_details()
        assert issue.number == 123
        assert issue.title == "Test Issue"
        assert issue.state == "open"
        assert issue.user.login == "testuser"

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
        mocker.patch.object(extractor, "_make_request", return_value=mock_data)

        comments = extractor.fetch_comments()
        assert len(comments) == 1
        assert comments[0].body == "Test comment"

    def test_extract_all(self, mocker: MockerFixture) -> None:
        """Test extracting all issue data."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)

        mock_issue = {
            "number": 123,
            "title": "Test Issue",
            "body": "Test body",
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
            "labels": [],
        }

        mock_comments = [
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

        mocker.patch.object(
            extractor,
            "_make_request",
            side_effect=[mock_issue, mock_comments],
        )

        issue, comments = extractor.extract_all()

        assert issue.number == 123
        assert len(comments) == 1

    def test_404_error(self, mocker: MockerFixture) -> None:
        """Test handling of 404 errors."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)

        mock_response = mocker.Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mocker.patch.object(extractor.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Resource not found"):
            extractor.fetch_issue_details()

    def test_rate_limit_error(self, mocker: MockerFixture) -> None:
        """Test handling of rate limit errors."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)

        mock_response = mocker.Mock()
        mock_response.status_code = 403
        mock_response.text = "rate limit exceeded"
        mocker.patch.object(extractor.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="rate limit exceeded"):
            extractor.fetch_issue_details()

    def test_forbidden_error(self, mocker: MockerFixture) -> None:
        """Test handling of 403 forbidden errors."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)

        mock_response = mocker.Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mocker.patch.object(extractor.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Access forbidden"):
            extractor.fetch_issue_details()

    def test_other_error(self, mocker: MockerFixture) -> None:
        """Test handling of other HTTP errors."""
        extractor = GitHubIssueExtractor("owner", "repo", 123)

        mock_response = mocker.Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mocker.patch.object(extractor.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="failed with status 500"):
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
        mocker.patch.object(extractor, "_make_request", return_value=mock_data)

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
        mocker.patch.object(extractor, "_make_request", return_value=mock_data)

        issue = extractor.fetch_issue_details()
        assert issue.state == "closed"
        assert issue.closed_at is not None
