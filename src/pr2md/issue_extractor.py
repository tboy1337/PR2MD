"""GitHub Issue data extraction."""

import logging
from typing import Any, Optional

from pr2md.github_client import GitHubClient
from pr2md.models import Comment, Issue

logger = logging.getLogger(__name__)


class GitHubIssueExtractor:
    """Extract Issue data from GitHub API."""

    def __init__(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        client: Optional[GitHubClient] = None,
    ) -> None:
        """
        Initialize the issue extractor.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            client: Optional shared GitHub API client
        """
        self.owner = owner
        self.repo = repo
        self.issue_number = issue_number
        self._owns_client = client is None
        self._client = client or GitHubClient()
        logger.info(
            "Initialized extractor for %s/%s Issue #%d",
            owner,
            repo,
            issue_number,
        )

    def __enter__(self) -> "GitHubIssueExtractor":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying API client if owned by this extractor."""
        if self._owns_client:
            self._client.close()

    def fetch_issue_details(self) -> Issue:
        """
        Fetch issue details.

        Returns:
            Issue object

        Raises:
            GitHubAPIError: If the request fails
        """
        logger.info("Fetching issue details")
        endpoint = f"/repos/{self.owner}/{self.repo}/issues/{self.issue_number}"
        data: dict[str, Any] = self._client.get(endpoint)
        return Issue.from_dict(data)

    def fetch_comments(self) -> list[Comment]:
        """
        Fetch issue comments.

        Returns:
            List of Comment objects

        Raises:
            GitHubAPIError: If the request fails
        """
        logger.info("Fetching comments")
        endpoint = (
            f"/repos/{self.owner}/{self.repo}/issues/{self.issue_number}/comments"
        )
        data: list[dict[str, Any]] = self._client.get_paginated(endpoint)
        comments = [Comment.from_dict(dict(comment)) for comment in data]
        logger.info("Found %d comments", len(comments))
        return comments

    def extract_all(self) -> tuple[Issue, list[Comment]]:
        """
        Extract all issue data.

        Returns:
            Tuple of (Issue, comments)

        Raises:
            GitHubAPIError: If any request fails
        """
        logger.info("Extracting all issue data")
        issue = self.fetch_issue_details()
        comments = self.fetch_comments()
        logger.info("Successfully extracted all issue data")
        return issue, comments
