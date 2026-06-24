"""Tests for GitHub API client."""

import json

import pytest
import requests
from pytest_mock import MockerFixture

from pr2md.exceptions import GitHubAPIError
from pr2md.github_client import GitHubClient, _parse_next_link


class TestParseNextLink:
    """Tests for Link header parsing."""

    def test_parse_next_link_present(self) -> None:
        """Test parsing a Link header with a next URL."""
        header = (
            '<https://api.github.com/repos/o/r/issues/1/comments?page=2>; rel="next", '
            '<https://api.github.com/repos/o/r/issues/1/comments?page=5>; rel="last"'
        )
        assert (
            _parse_next_link(header)
            == "https://api.github.com/repos/o/r/issues/1/comments?page=2"
        )

    def test_parse_next_link_absent(self) -> None:
        """Test parsing a Link header without next."""
        assert _parse_next_link(None) is None
        assert _parse_next_link('rel="last"') is None


class TestGitHubClient:
    """Tests for GitHubClient."""

    def test_get_success_json(self, mocker: MockerFixture) -> None:
        """Test successful JSON GET."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}
        mock_response.headers = {}
        mocker.patch.object(client.session, "get", return_value=mock_response)

        assert client.get("/repos/o/r") == {"key": "value"}
        client.close()

    def test_get_success_diff(self, mocker: MockerFixture) -> None:
        """Test successful diff GET."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "diff content"
        mock_response.headers = {}
        mocker.patch.object(client.session, "get", return_value=mock_response)

        result = client.get(
            "/repos/o/r/pulls/1", accept="application/vnd.github.v3.diff"
        )
        assert result == "diff content"
        client.close()

    def test_get_404_error(self, mocker: MockerFixture) -> None:
        """Test 404 handling."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.headers = {}
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Resource not found"):
            client.get("/missing")
        client.close()

    def test_get_403_rate_limit_retries(self, mocker: MockerFixture) -> None:
        """Test rate limit response waits and retries until success."""
        client = GitHubClient()
        rate_limited = mocker.Mock()
        rate_limited.status_code = 403
        rate_limited.text = "API rate limit exceeded"
        rate_limited.headers = {"Retry-After": "1"}
        ok_response = mocker.Mock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"ok": True}
        ok_response.headers = {}
        mocker.patch.object(
            client.session,
            "get",
            side_effect=[rate_limited, ok_response],
        )
        mocker.patch("pr2md.github_client.time.sleep")

        assert client.get("/repos/o/r") == {"ok": True}
        client.close()

    def test_get_403_forbidden(self, mocker: MockerFixture) -> None:
        """Test forbidden handling."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.headers = {}
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Access forbidden"):
            client.get("/repos/o/r")
        client.close()

    def test_get_other_error(self, mocker: MockerFixture) -> None:
        """Test other HTTP error handling."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.headers = {}
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="request failed with status 500"):
            client.get("/repos/o/r")
        client.close()

    def test_get_retries_transient_error(self, mocker: MockerFixture) -> None:
        """Test retry on 503 then success."""
        client = GitHubClient()
        fail_response = mocker.Mock()
        fail_response.status_code = 503
        fail_response.text = "Service Unavailable"
        fail_response.headers = {}
        ok_response = mocker.Mock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"ok": True}
        ok_response.headers = {}
        mocker.patch.object(
            client.session,
            "get",
            side_effect=[fail_response, ok_response],
        )
        mocker.patch("pr2md.github_client.time.sleep")

        assert client.get("/repos/o/r") == {"ok": True}
        client.close()

    def test_get_request_exception(self, mocker: MockerFixture) -> None:
        """Test connection error handling."""
        client = GitHubClient()
        mocker.patch.object(
            client.session,
            "get",
            side_effect=requests.ConnectionError("network down"),
        )
        mocker.patch("pr2md.github_client.time.sleep")

        with pytest.raises(GitHubAPIError, match="GitHub API request failed"):
            client.get("/repos/o/r")
        client.close()

    def test_get_paginated(self, mocker: MockerFixture) -> None:
        """Test paginated list fetching."""
        client = GitHubClient()
        page1 = mocker.Mock()
        page1.status_code = 200
        page1.json.return_value = [{"id": 1}]
        page1.headers = {"Link": '<https://api.github.com/page2>; rel="next"'}
        page2 = mocker.Mock()
        page2.status_code = 200
        page2.json.return_value = [{"id": 2}]
        page2.headers = {}
        mocker.patch.object(client.session, "get", side_effect=[page1, page2])

        items = client.get_paginated("/repos/o/r/issues/1/comments")
        assert items == [{"id": 1}, {"id": 2}]
        client.close()

    def test_fetch_issue_or_pr_type_pr(self, mocker: MockerFixture) -> None:
        """Test type detection for a pull request."""
        client = GitHubClient()
        mocker.patch.object(
            client,
            "get",
            return_value={"number": 1, "pull_request": {"url": "http://example"}},
        )
        assert client.fetch_issue_or_pr_type("o", "r", 1) == "pr"
        client.close()

    def test_fetch_issue_or_pr_type_issue(self, mocker: MockerFixture) -> None:
        """Test type detection for a plain issue."""
        client = GitHubClient()
        mocker.patch.object(client, "get", return_value={"number": 1})
        assert client.fetch_issue_or_pr_type("o", "r", 1) == "issue"
        client.close()

    def test_fetch_issue_or_pr_type_not_found(self, mocker: MockerFixture) -> None:
        """Test type detection when resource is missing."""
        client = GitHubClient()
        mocker.patch.object(
            client,
            "get",
            side_effect=GitHubAPIError("Resource not found", status_code=404),
        )
        assert client.fetch_issue_or_pr_type("o", "r", 1) is None
        client.close()

    def test_context_manager(self, mocker: MockerFixture) -> None:
        """Test client context manager closes session."""
        with GitHubClient() as client:
            mock_close = mocker.patch.object(client.session, "close")
        mock_close.assert_called_once()

    def test_get_paginated_non_list_response(self, mocker: MockerFixture) -> None:
        """Test paginated fetch rejects non-list JSON."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"unexpected": True}
        mock_response.headers = {}
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Expected paginated list"):
            client.get_paginated("/repos/o/r/issues/1/comments")
        client.close()

    def test_get_retries_exhausted_on_502(self, mocker: MockerFixture) -> None:
        """Test retry exhaustion on persistent 502."""
        client = GitHubClient()
        fail_response = mocker.Mock()
        fail_response.status_code = 502
        fail_response.text = "Bad Gateway"
        fail_response.headers = {}
        mocker.patch.object(client.session, "get", return_value=fail_response)
        mocker.patch("pr2md.github_client.time.sleep")

        with pytest.raises(GitHubAPIError, match="request failed with status 502"):
            client.get("/repos/o/r")
        client.close()

    def test_get_paginated_fetches_all_pages(self, mocker: MockerFixture) -> None:
        """Test pagination continues until no next link."""
        client = GitHubClient()

        def make_page(page_id: int, *, has_next: bool) -> object:
            page = mocker.Mock()
            page.status_code = 200
            page.json.return_value = [{"id": page_id}]
            if has_next:
                page.headers = {
                    "Link": (f'<https://api.github.com/page{page_id + 1}>; rel="next"')
                }
            else:
                page.headers = {}
            return page

        pages = [make_page(i, has_next=True) for i in range(1, 6)]
        pages.append(make_page(6, has_next=False))
        mocker.patch.object(client.session, "get", side_effect=pages)

        items = client.get_paginated("/repos/o/r/issues/1/comments")
        assert len(items) == 6
        client.close()

    def test_get_paginated_rejects_foreign_next_url(
        self, mocker: MockerFixture
    ) -> None:
        """Test pagination rejects non-GitHub next URLs."""
        client = GitHubClient()
        page1 = mocker.Mock()
        page1.status_code = 200
        page1.json.return_value = [{"id": 1}]
        page1.headers = {"Link": '<https://evil.example.com/page2>; rel="next"'}
        mocker.patch.object(client.session, "get", return_value=page1)

        with pytest.raises(GitHubAPIError, match="rejected"):
            client.get_paginated("/repos/o/r/issues/1/comments")
        client.close()

    def test_get_401_error(self, mocker: MockerFixture) -> None:
        """Test 401 handling."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.headers = {}
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="authentication required"):
            client.get("/repos/o/r")
        assert mock_response.status_code == 401
        client.close()

    def test_get_json_decode_error(self, mocker: MockerFixture) -> None:
        """Test invalid JSON response handling."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("bad", "doc", 0)
        mock_response.headers = {}
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Invalid JSON"):
            client.get("/repos/o/r")
        client.close()

    def test_get_429_retries_until_success(self, mocker: MockerFixture) -> None:
        """Test 429 waits and retries until success."""
        client = GitHubClient()
        rate_limited = mocker.Mock()
        rate_limited.status_code = 429
        rate_limited.text = "Too Many Requests"
        rate_limited.headers = {"Retry-After": "2"}
        ok_response = mocker.Mock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"ok": True}
        ok_response.headers = {}
        mocker.patch.object(
            client.session,
            "get",
            side_effect=[rate_limited, ok_response],
        )
        mocker.patch("pr2md.github_client.time.sleep")

        assert client.get("/repos/o/r") == {"ok": True}
        client.close()

    def test_api_error_has_status_code(self, mocker: MockerFixture) -> None:
        """Test GitHubAPIError includes status code."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.headers = {}
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError) as exc_info:
            client.get("/missing")
        assert exc_info.value.status_code == 404
        client.close()

    def test_get_truncates_large_error_body(self, mocker: MockerFixture) -> None:
        """Test error messages truncate very large response bodies."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 500
        mock_response.text = "x" * 1000
        mock_response.headers = {}
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError) as exc_info:
            client.get("/repos/o/r")
        assert "truncated" in str(exc_info.value)
        assert len(str(exc_info.value)) < 700
        client.close()

    def test_fetch_issue_or_pr_type_non_dict(self, mocker: MockerFixture) -> None:
        """Test type detection when API returns unexpected data."""
        client = GitHubClient()
        mocker.patch.object(client, "get", return_value="not a dict")
        assert client.fetch_issue_or_pr_type("o", "r", 1) is None
        client.close()

    def test_get_504_retries_until_success(self, mocker: MockerFixture) -> None:
        """Test 504 gateway timeout is retried."""
        client = GitHubClient()
        gateway_timeout = mocker.Mock()
        gateway_timeout.status_code = 504
        gateway_timeout.text = "Gateway Timeout"
        gateway_timeout.headers = {}
        ok_response = mocker.Mock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"ok": True}
        ok_response.headers = {}
        mocker.patch.object(
            client.session,
            "get",
            side_effect=[gateway_timeout, ok_response],
        )
        mocker.patch("pr2md.github_client.time.sleep")

        assert client.get("/repos/o/r") == {"ok": True}
        client.close()

    def test_rate_limit_invalid_retry_after_uses_reset_header(
        self, mocker: MockerFixture
    ) -> None:
        """Test invalid Retry-After falls back to X-RateLimit-Reset."""
        from pr2md.github_client import _rate_limit_wait_seconds

        response = mocker.Mock()
        response.headers = {
            "Retry-After": "not-a-number",
            "X-RateLimit-Reset": "4102444800",
        }
        wait = _rate_limit_wait_seconds(response)
        assert wait >= 1.0

    def test_rate_limit_default_wait_when_headers_missing(
        self, mocker: MockerFixture
    ) -> None:
        """Test default wait when rate-limit headers are absent."""
        from pr2md.github_client import _rate_limit_wait_seconds

        response = mocker.Mock()
        response.headers = {}
        assert _rate_limit_wait_seconds(response) == 60.0

    def test_fetch_issue_or_pr_type_propagates_non_404(
        self, mocker: MockerFixture
    ) -> None:
        """Test type detection re-raises non-404 API errors."""
        client = GitHubClient()
        mocker.patch.object(
            client,
            "get",
            side_effect=GitHubAPIError("Rate limit", status_code=403),
        )

        with pytest.raises(GitHubAPIError, match="Rate limit"):
            client.fetch_issue_or_pr_type("o", "r", 1)
        client.close()

    def test_rate_limit_wait_cap_exceeded(self, mocker: MockerFixture) -> None:
        """Test rate limit retries stop after maximum waits."""
        client = GitHubClient()
        rate_limited = mocker.Mock()
        rate_limited.status_code = 429
        rate_limited.text = "Too Many Requests"
        rate_limited.headers = {"Retry-After": "1"}
        mocker.patch.object(client.session, "get", return_value=rate_limited)
        mocker.patch("pr2md.github_client.time.sleep")

        with pytest.raises(GitHubAPIError, match="maximum wait time reached"):
            client.get("/repos/o/r")
        client.close()

    def test_get_paginated_page_cap_exceeded(self, mocker: MockerFixture) -> None:
        """Test pagination stops when page limit is exceeded."""
        from pr2md.github_client import _MAX_PAGINATED_PAGES

        client = GitHubClient()

        def make_page() -> object:
            page = mocker.Mock()
            page.status_code = 200
            page.json.return_value = [{"id": 1}]
            page.headers = {"Link": '<https://api.github.com/next>; rel="next"'}
            return page

        mocker.patch.object(
            client.session,
            "get",
            side_effect=[make_page() for _ in range(_MAX_PAGINATED_PAGES + 1)],
        )

        with pytest.raises(GitHubAPIError, match="Pagination limit exceeded"):
            client.get_paginated("/repos/o/r/issues/1/comments")
        client.close()


class TestGitHubAPIError:
    """Tests for GitHubAPIError formatting."""

    def test_str_includes_status_and_url(self) -> None:
        """Test string representation includes metadata."""
        err = GitHubAPIError(
            "failed",
            status_code=404,
            url="https://api.github.com/missing",
        )
        text = str(err)
        assert "failed" in text
        assert "status_code=404" in text
        assert "url=https://api.github.com/missing" in text
