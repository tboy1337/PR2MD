"""Shared GitHub REST API client."""

import json
import logging
import re
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from types import TracebackType
from typing import Any, Literal, Optional
from urllib.parse import urlparse

import requests

from pr2md.exceptions import GitHubAPIError

try:
    _PACKAGE_VERSION = version("PR2MD")
except PackageNotFoundError:
    _PACKAGE_VERSION = "unknown"

logger = logging.getLogger(__name__)

# Transient server errors: bounded retries with exponential backoff.
_RETRYABLE_STATUS_CODES = {502, 503, 504}
_MAX_RETRIES = 3
# Connect and read timeouts in seconds (connect, read).
_REQUEST_TIMEOUT = (10, 30)
# Items per page when paginating list endpoints.
_PER_PAGE = 100
_MAX_PAGINATED_PAGES = 100
_MAX_ERROR_BODY_LENGTH = 500
_ALLOWED_API_HOST = "api.github.com"
_RATE_LIMIT_REMAINING_WARN_THRESHOLD = 10
_MAX_RATE_LIMIT_WAITS = 5
_MAX_RATE_LIMIT_WAIT_SECONDS = 3600.0


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


def _is_allowed_github_api_url(url: str) -> bool:
    """Return True if url targets the public GitHub REST API host."""
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.netloc == _ALLOWED_API_HOST


def _is_rate_limited(response: requests.Response) -> bool:
    """Return True when the response indicates an API rate limit."""
    if response.status_code == 429:
        return True
    if response.status_code == 403 and "rate limit" in response.text.lower():
        return True
    return False


def _rate_limit_wait_seconds(response: requests.Response) -> float:
    """Compute how long to wait before retrying after a rate-limit response."""
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(float(retry_after), 1.0)
        except ValueError:
            pass

    reset_header = response.headers.get("X-RateLimit-Reset")
    if reset_header is not None:
        try:
            reset_at = datetime.fromtimestamp(int(reset_header), tz=timezone.utc)
            wait = (reset_at - datetime.now(timezone.utc)).total_seconds()
            return max(wait, 1.0)
        except (ValueError, OSError):
            pass

    return 60.0


def _log_rate_limit_headers(response: requests.Response) -> None:
    """Log rate-limit header values for observability."""
    remaining = response.headers.get("X-RateLimit-Remaining")
    reset = response.headers.get("X-RateLimit-Reset")
    if remaining is not None:
        logger.debug("X-RateLimit-Remaining: %s", remaining)
        try:
            if int(remaining) < _RATE_LIMIT_REMAINING_WARN_THRESHOLD:
                logger.info(
                    "GitHub API rate limit nearly exhausted (%s remaining); "
                    "waits may occur",
                    remaining,
                )
        except ValueError:
            pass
    if reset is not None:
        logger.debug("X-RateLimit-Reset: %s", reset)


class GitHubClient:
    """HTTP client for the GitHub REST API."""

    def __init__(self) -> None:
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"PR2MD/{_PACKAGE_VERSION}",
            }
        )

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
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
        return self._parse_json_response(response, url)

    def get_paginated(self, endpoint: str) -> list[Any]:
        """
        Fetch all pages for a list endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            Combined list of items from all pages
        """
        separator = "&" if "?" in endpoint else "?"
        url: Optional[str] = f"{self.base_url}{endpoint}{separator}per_page={_PER_PAGE}"
        items: list[Any] = []
        page_count = 0

        while url:
            page_count += 1
            if page_count > _MAX_PAGINATED_PAGES:
                raise GitHubAPIError(
                    f"Pagination limit exceeded ({_MAX_PAGINATED_PAGES} pages) "
                    f"for {endpoint}",
                    url=url,
                )
            if not _is_allowed_github_api_url(url):
                raise GitHubAPIError(
                    f"Pagination URL rejected (not GitHub API): {url}",
                    url=url,
                )
            logger.debug("Fetching paginated URL %s", url)
            response = self._request_with_retries(url)
            self._raise_for_status(response, url)

            data = self._parse_json_response(response, url)
            if not isinstance(data, list):
                raise GitHubAPIError(
                    f"Expected paginated list from {endpoint}, got {type(data)}",
                    url=url,
                )
            items.extend(data)
            next_url = _parse_next_link(response.headers.get("Link"))
            if next_url is not None and not _is_allowed_github_api_url(next_url):
                raise GitHubAPIError(
                    f"Pagination URL rejected (not GitHub API): {next_url}",
                    url=next_url,
                )
            url = next_url

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
        except GitHubAPIError as err:
            if err.status_code == 404:
                return None
            raise

        if not isinstance(data, dict):
            return None
        if data.get("pull_request"):
            return "pr"
        return "issue"

    def _parse_json_response(self, response: requests.Response, url: str) -> Any:
        try:
            return response.json()
        except json.JSONDecodeError as err:
            raise GitHubAPIError(
                f"Invalid JSON response from {url}: {err}",
                status_code=response.status_code,
                url=url,
            ) from err

    def _request_with_retries(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        if not _is_allowed_github_api_url(url):
            raise GitHubAPIError(
                f"Request URL rejected (not GitHub API): {url}",
                url=url,
            )

        merged_headers = dict(self.session.headers)
        if headers:
            merged_headers.update(headers)

        transient_attempt = 0
        rate_limit_waits = 0
        total_rate_limit_wait_seconds = 0.0

        while True:
            try:
                logger.debug(
                    "Making request to %s (transient attempt %d)",
                    url,
                    transient_attempt + 1,
                )
                response = self.session.get(
                    url,
                    headers=merged_headers,
                    params=params,
                    timeout=_REQUEST_TIMEOUT,
                )
            except requests.RequestException as err:
                if transient_attempt < _MAX_RETRIES - 1:
                    time.sleep(2**transient_attempt)
                    transient_attempt += 1
                    continue
                raise GitHubAPIError(
                    f"GitHub API request failed: {err}",
                    url=url,
                ) from err

            _log_rate_limit_headers(response)

            if _is_rate_limited(response):
                wait_seconds = _rate_limit_wait_seconds(response)
                rate_limit_waits += 1
                total_rate_limit_wait_seconds += wait_seconds
                if (
                    rate_limit_waits > _MAX_RATE_LIMIT_WAITS
                    or total_rate_limit_wait_seconds > _MAX_RATE_LIMIT_WAIT_SECONDS
                ):
                    raise GitHubAPIError(
                        "GitHub API rate limit exceeded; maximum wait time reached. "
                        "Try again later or reduce the number of requests.",
                        status_code=response.status_code,
                        url=url,
                    )
                resume_at = datetime.now(timezone.utc).timestamp() + wait_seconds
                resume_str = datetime.fromtimestamp(
                    resume_at, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S UTC")
                logger.info(
                    "Rate limited by GitHub API; waiting %.0fs (resuming ~%s)",
                    wait_seconds,
                    resume_str,
                )
                time.sleep(wait_seconds)
                transient_attempt = 0
                continue

            if response.status_code in _RETRYABLE_STATUS_CODES:
                if transient_attempt < _MAX_RETRIES - 1:
                    time.sleep(2**transient_attempt)
                    transient_attempt += 1
                    continue

            return response

    def _raise_for_status(self, response: requests.Response, url: str) -> None:
        status = response.status_code
        if status == 404:
            raise GitHubAPIError(
                f"Resource not found: {url}. "
                "Please check that the repository and resource number are correct.",
                status_code=status,
                url=url,
            )
        if status == 401:
            raise GitHubAPIError(
                "GitHub API authentication required. "
                "PR2MD uses the unauthenticated public API only.",
                status_code=status,
                url=url,
            )
        if status == 403:
            if _is_rate_limited(response):
                raise GitHubAPIError(
                    "GitHub API rate limit exceeded unexpectedly.",
                    status_code=status,
                    url=url,
                )
            raise GitHubAPIError(
                f"Access forbidden: {url}",
                status_code=status,
                url=url,
            )
        if status != 200:
            body = response.text
            if len(body) > _MAX_ERROR_BODY_LENGTH:
                body = f"{body[:_MAX_ERROR_BODY_LENGTH]}... (truncated)"
            raise GitHubAPIError(
                f"GitHub API request failed with status {status}: {body}",
                status_code=status,
                url=url,
            )
