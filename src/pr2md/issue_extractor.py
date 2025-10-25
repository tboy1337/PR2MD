"""GitHub Issue data extraction."""

import logging
from typing import Any, Optional

import requests

from pr2md.models import Comment, Issue

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """Exception raised for GitHub API errors."""


class GitHubIssueExtractor:
    """Extract Issue data from GitHub API."""

    def __init__(self, owner: str, repo: str, issue_number: int) -> None:
        """
        Initialize the issue extractor.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
        """
        self.owner = owner
        self.repo = repo
        self.issue_number = issue_number
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GitHub-PR-Extractor",
            }
        )
        logger.info(
            "Initialized extractor for %s/%s Issue #%d",
            owner,
            repo,
            issue_number,
        )

    def _make_request(self, endpoint: str, accept_header: Optional[str] = None) -> Any:
        """
        Make a request to the GitHub API.

        Args:
            endpoint: API endpoint path
            accept_header: Optional custom Accept header

        Returns:
            Response data (JSON)

        Raises:
            GitHubAPIError: If the request fails
        """
        url = f"{self.base_url}{endpoint}"
        headers = {}
        if accept_header:
            headers["Accept"] = accept_header

        logger.debug("Making request to %s", url)
        response = self.session.get(url, headers=headers, timeout=30)

        if response.status_code == 404:
            raise GitHubAPIError(
                f"Resource not found: {url}. "
                "Please check that the repository and issue number are correct."
            )
        if response.status_code == 403:
            # Check if it's rate limiting
            if "rate limit" in response.text.lower():
                raise GitHubAPIError(
                    "GitHub API rate limit exceeded. "
                    "Please try again later or use authentication."
                )
            raise GitHubAPIError(f"Access forbidden: {url}")
        if response.status_code != 200:
            raise GitHubAPIError(
                f"GitHub API request failed with status {response.status_code}: "
                f"{response.text}"
            )

        return response.json()

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
        data: dict[str, Any] = self._make_request(endpoint)
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
        data: list[dict[str, Any]] = self._make_request(endpoint)
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
