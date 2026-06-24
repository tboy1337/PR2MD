"""Shared pytest fixtures."""

from typing import Any

import pytest

from pr2md.github_client import GitHubClient


@pytest.fixture
def mock_github_client(mocker: Any) -> GitHubClient:
    """Provide a GitHubClient with a mocked session."""
    client = GitHubClient()
    mocker.patch.object(client.session, "close")
    return client


@pytest.fixture
def sample_pr_dict() -> dict[str, Any]:
    """Minimal pull request API payload."""
    return {
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


@pytest.fixture
def sample_issue_dict() -> dict[str, Any]:
    """Minimal issue API payload."""
    return {
        "number": 456,
        "title": "Test Issue",
        "body": "Issue body",
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
        "html_url": "https://github.com/owner/repo/issues/456",
        "labels": [],
    }
