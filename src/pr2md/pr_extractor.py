"""GitHub Pull Request data extraction."""

import logging
from typing import Any, Optional

import requests

from pr2md.exceptions import GitHubAPIError
from pr2md.models import Comment, PullRequest, Review, ReviewComment

logger = logging.getLogger(__name__)


class GitHubPRExtractor:
    """Extract Pull Request data from GitHub API."""

    def __init__(self, owner: str, repo: str, pr_number: int) -> None:
        """
        Initialize the PR extractor.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
        """
        self.owner = owner
        self.repo = repo
        self.pr_number = pr_number
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GitHub-PR-Extractor",
            }
        )
        logger.info("Initialized extractor for %s/%s PR #%d", owner, repo, pr_number)

    def _make_request(self, endpoint: str, accept_header: Optional[str] = None) -> Any:
        """
        Make a request to the GitHub API.

        Args:
            endpoint: API endpoint path
            accept_header: Optional custom Accept header

        Returns:
            Response data (JSON or text)

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
                "Please check that the repository and PR number are correct."
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

        if accept_header and "diff" in accept_header:
            return str(response.text)
        return response.json()

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
        data: dict[str, Any] = self._make_request(endpoint)
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
        data: list[dict[str, Any]] = self._make_request(endpoint)
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
        data: list[dict[str, Any]] = self._make_request(endpoint)
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
        data: list[dict[str, Any]] = self._make_request(endpoint)
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
        diff: str = self._make_request(
            endpoint, accept_header="application/vnd.github.v3.diff"
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
