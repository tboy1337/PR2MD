"""GitHub Issue data extraction."""

import logging
from types import TracebackType
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
        *,
        cached_issue_payload: Optional[dict[str, Any]] = None,
        warn_if_pull_request: bool = True,
    ) -> None:
        """
        Initialize the issue extractor.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            client: Optional shared GitHub API client
            cached_issue_payload: Optional issue JSON from a prior type probe
            warn_if_pull_request: Log when the issues endpoint returns a PR
        """
        self.owner = owner
        self.repo = repo
        self.issue_number = issue_number
        self._owns_client = client is None
        self._client = client or GitHubClient()
        self._cached_issue_payload = cached_issue_payload
        self._warn_if_pull_request = warn_if_pull_request
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
        exc_tb: Optional[TracebackType],
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
        if self._cached_issue_payload is not None:
            data = self._cached_issue_payload
            self._cached_issue_payload = None
        else:
            endpoint = f"/repos/{self.owner}/{self.repo}/issues/{self.issue_number}"
            data = self._client.get(endpoint)
        if self._warn_if_pull_request and data.get("pull_request"):
            logger.warning(
                "Issue #%d in %s/%s is a pull request; use GitHubPRExtractor for "
                "full diff and reviews",
                self.issue_number,
                self.owner,
                self.repo,
            )
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
