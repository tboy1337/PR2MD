"""GitHub Pull Request data extraction."""

import logging
from types import TracebackType
from typing import Any, Optional

from pr2md.exceptions import GitHubAPIError
from pr2md.formatter import DIFF_UNAVAILABLE_PREFIX
from pr2md.github_client import GitHubClient
from pr2md.models import Comment, PullRequest, Review, ReviewComment

logger = logging.getLogger(__name__)

_DIFF_SIZE_WARNING_BYTES = 5 * 1024 * 1024
_DIFF_SIZE_INFO_BYTES = 25 * 1024 * 1024
_DIFF_SIZE_HIGH_WARNING_BYTES = 100 * 1024 * 1024


def _log_diff_size(diff_size: int) -> None:
    """Log tiered size notices for large diffs without refusing the download."""
    size_mb = diff_size / (1024 * 1024)
    if diff_size > _DIFF_SIZE_HIGH_WARNING_BYTES:
        logger.warning(
            "PR diff is very large (%.1f MB); full diff will be included in export",
            size_mb,
        )
    elif diff_size > _DIFF_SIZE_INFO_BYTES:
        logger.info(
            "PR diff is large (%.1f MB); full diff will be included in export",
            size_mb,
        )
    elif diff_size > _DIFF_SIZE_WARNING_BYTES:
        logger.warning(
            "PR diff is large (%.1f MB); full diff will be included in export",
            size_mb,
        )


class GitHubPRExtractor:
    """Extract Pull Request data from GitHub API."""

    def __init__(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        client: Optional[GitHubClient] = None,
    ) -> None:
        """
        Initialize the PR extractor.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            client: Optional shared GitHub API client
        """
        self.owner = owner
        self.repo = repo
        self.pr_number = pr_number
        self._owns_client = client is None
        self._client = client or GitHubClient()
        logger.info("Initialized extractor for %s/%s PR #%d", owner, repo, pr_number)

    def __enter__(self) -> "GitHubPRExtractor":
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

    def fetch_pr_details(self) -> PullRequest:
        """
        Fetch pull request details.

        Returns:
            PullRequest object

        Raises:
            GitHubAPIError: If the request fails
        """
        logger.info("Fetching PR details")
        endpoint = f"/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}"
        data: dict[str, Any] = self._client.get(endpoint)
        return PullRequest.from_dict(data)

    def fetch_comments(self) -> list[Comment]:
        """
        Fetch issue/PR comments (conversation thread).

        Returns:
            List of Comment objects

        Raises:
            GitHubAPIError: If the request fails
        """
        logger.info("Fetching comments")
        endpoint = f"/repos/{self.owner}/{self.repo}/issues/{self.pr_number}/comments"
        data: list[dict[str, Any]] = self._client.get_paginated(endpoint)
        comments = [Comment.from_dict(dict(comment)) for comment in data]
        logger.info("Found %d comments", len(comments))
        return comments

    def fetch_review_comments(self) -> list[ReviewComment]:
        """
        Fetch review comments (inline code comments).

        Returns:
            List of ReviewComment objects

        Raises:
            GitHubAPIError: If the request fails
        """
        logger.info("Fetching review comments")
        endpoint = f"/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}/comments"
        data: list[dict[str, Any]] = self._client.get_paginated(endpoint)
        review_comments = [ReviewComment.from_dict(dict(comment)) for comment in data]
        logger.info("Found %d review comments", len(review_comments))
        return review_comments

    def fetch_reviews(self) -> list[Review]:
        """
        Fetch PR reviews.

        Returns:
            List of Review objects

        Raises:
            GitHubAPIError: If the request fails
        """
        logger.info("Fetching reviews")
        endpoint = f"/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}/reviews"
        data: list[dict[str, Any]] = self._client.get_paginated(endpoint)
        reviews = [Review.from_dict(dict(review)) for review in data]
        logger.info("Found %d reviews", len(reviews))
        return reviews

    def fetch_diff(self) -> str:
        """
        Fetch PR diff.

        Returns:
            Diff as a string

        Raises:
            GitHubAPIError: If the request fails
        """
        logger.info("Fetching diff")
        endpoint = f"/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}"
        diff: str = self._client.get(endpoint, accept="application/vnd.github.v3.diff")
        diff_size = len(diff.encode("utf-8"))
        _log_diff_size(diff_size)
        logger.info("Fetched diff (%d bytes)", len(diff))
        return diff

    def extract_all(
        self,
    ) -> tuple[PullRequest, list[Comment], list[Review], list[ReviewComment], str]:
        """
        Extract all PR data.

        Returns:
            Tuple of (PullRequest, comments, reviews, review_comments, diff)

        Raises:
            GitHubAPIError: If PR details cannot be fetched
        """
        logger.info("Extracting all PR data")
        pull_request = self.fetch_pr_details()

        comments: list[Comment] = []
        try:
            comments = self.fetch_comments()
        except GitHubAPIError as err:
            logger.warning("Failed to fetch comments: %s", err)

        reviews: list[Review] = []
        try:
            reviews = self.fetch_reviews()
        except GitHubAPIError as err:
            logger.warning("Failed to fetch reviews: %s", err)

        review_comments: list[ReviewComment] = []
        try:
            review_comments = self.fetch_review_comments()
        except GitHubAPIError as err:
            logger.warning("Failed to fetch review comments: %s", err)

        diff = ""
        try:
            diff = self.fetch_diff()
        except GitHubAPIError as err:
            logger.warning("Failed to fetch diff: %s", err)
            diff = f"{DIFF_UNAVAILABLE_PREFIX}{err}"

        logger.info("Successfully extracted all PR data")
        return pull_request, comments, reviews, review_comments, diff
