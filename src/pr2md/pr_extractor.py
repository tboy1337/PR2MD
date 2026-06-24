"""GitHub Pull Request data extraction."""

import logging
from typing import Any, Optional

from pr2md.github_client import GitHubClient
from pr2md.models import Comment, PullRequest, Review, ReviewComment

logger = logging.getLogger(__name__)

_DIFF_SIZE_WARNING_BYTES = 5 * 1024 * 1024


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
        exc_tb: Optional[object],
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
        if diff_size > _DIFF_SIZE_WARNING_BYTES:
            size_mb = diff_size / (1024 * 1024)
            logger.warning(
                "PR diff is large (%.1f MB); full diff will be included in export",
                size_mb,
            )
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
            GitHubAPIError: If any request fails
        """
        logger.info("Extracting all PR data")
        pull_request = self.fetch_pr_details()
        comments = self.fetch_comments()
        reviews = self.fetch_reviews()
        review_comments = self.fetch_review_comments()
        diff = self.fetch_diff()
        logger.info("Successfully extracted all PR data")
        return pull_request, comments, reviews, review_comments, diff
