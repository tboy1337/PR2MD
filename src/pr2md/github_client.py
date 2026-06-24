"""Shared GitHub REST API client."""

import logging
import re
import time
from typing import Any, Literal, Optional

import requests

from pr2md.exceptions import GitHubAPIError

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {502, 503, 504}
_MAX_RETRIES = 3
_REQUEST_TIMEOUT = 30
_PER_PAGE = 100


def _parse_next_link(link_header: Optional[str]) -> Optional[str]:
    """Extract the next page URL from a GitHub Link header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.strip()
        if 'rel="next"' in section:
            match = re.search(r"<([^>]+)>", section)
            if match:
                return match.group(1)
    return None


class GitHubClient:
    """HTTP client for the GitHub REST API."""

    def __init__(self) -> None:
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GitHub-PR-Extractor",
            }
        )

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.session.close()

    def get(
        self,
        endpoint: str,
        *,
        accept: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Make a GET request to the GitHub API.

        Args:
            endpoint: API endpoint path
            accept: Optional custom Accept header
            params: Optional query parameters

        Returns:
            Response data (JSON or text)

        Raises:
            GitHubAPIError: If the request fails after retries
        """
        url = f"{self.base_url}{endpoint}"
        headers: dict[str, str] = {}
        if accept:
            headers["Accept"] = accept

        response = self._request_with_retries(url, headers=headers, params=params)
        self._raise_for_status(response, url)

        if accept and "diff" in accept:
            return str(response.text)
        return response.json()

    def get_paginated(self, endpoint: str) -> list[Any]:
        """
        Fetch all pages for a list endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            Combined list of items from all pages
        """
        separator = "&" if "?" in endpoint else "?"
        url: Optional[str] = (
            f"{self.base_url}{endpoint}{separator}per_page={_PER_PAGE}"
        )
        items: list[Any] = []

        while url:
            logger.debug("Fetching paginated URL %s", url)
            response = self._request_with_retries(url)
            self._raise_for_status(response, url)

            data = response.json()
            if not isinstance(data, list):
                raise GitHubAPIError(
                    f"Expected paginated list from {endpoint}, got {type(data)}"
                )
            items.extend(data)
            url = _parse_next_link(response.headers.get("Link"))

        return items

    def fetch_issue_or_pr_type(
        self, owner: str, repo: str, number: int
    ) -> Optional[Literal["issue", "pr"]]:
        """
        Determine whether a number refers to a PR or a plain issue.

        Uses the issues endpoint which returns both; PRs include a pull_request key.
        """
        endpoint = f"/repos/{owner}/{repo}/issues/{number}"
        try:
            data = self.get(endpoint)
        except GitHubAPIError:
            return None

        if not isinstance(data, dict):
            return None
        if data.get("pull_request"):
            return "pr"
        return "issue"

    def _request_with_retries(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        merged_headers = dict(self.session.headers)
        if headers:
            merged_headers.update(headers)

        last_error: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                logger.debug("Making request to %s (attempt %d)", url, attempt + 1)
                response = self.session.get(
                    url,
                    headers=merged_headers,
                    params=params,
                    timeout=_REQUEST_TIMEOUT,
                )
            except requests.RequestException as err:
                last_error = err
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(2**attempt)
                    continue
                raise GitHubAPIError(
                    f"GitHub API request failed: {err}"
                ) from err

            if response.status_code in _RETRYABLE_STATUS_CODES:
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(2**attempt)
                    continue
            return response

        if last_error is not None:
            raise GitHubAPIError(
                f"GitHub API request failed: {last_error}"
            ) from last_error
        raise GitHubAPIError("GitHub API request failed after retries")

    def _raise_for_status(self, response: requests.Response, url: str) -> None:
        if response.status_code == 404:
            raise GitHubAPIError(
                f"Resource not found: {url}. "
                "Please check that the repository and resource number are correct."
            )
        if response.status_code == 403:
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
