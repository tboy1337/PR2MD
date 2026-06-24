"""Tests for GitHub API client."""

import json
import logging

import pytest
import requests
from pytest_mock import MockerFixture

from pr2md.exceptions import GitHubAPIError
from pr2md.github_client import GitHubClient, _parse_next_link
from tests.conftest import make_http_response


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
        mock_response = make_http_response(mocker, json_data={"key": "value"})
        mocker.patch.object(client.session, "get", return_value=mock_response)

        assert client.get("/repos/o/r") == {"key": "value"}
        client.close()

    def test_get_success_diff(self, mocker: MockerFixture) -> None:
        """Test successful diff GET."""
        client = GitHubClient()
        mock_response = make_http_response(mocker, body="diff content")
        mocker.patch.object(client.session, "get", return_value=mock_response)

        result = client.get(
            "/repos/o/r/pulls/1", accept="application/vnd.github.v3.diff"
        )
        assert result == "diff content"
        client.close()

    def test_get_404_error(self, mocker: MockerFixture) -> None:
        """Test 404 handling."""
        client = GitHubClient()
        mock_response = make_http_response(mocker, status_code=404, body="Not Found")
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Resource not found"):
            client.get("/missing")
        client.close()

    def test_get_403_rate_limit_retries(self, mocker: MockerFixture) -> None:
        """Test rate limit response waits and retries until success."""
        client = GitHubClient()
        rate_limited = make_http_response(
            mocker,
            status_code=403,
            body="API rate limit exceeded",
            headers={"Retry-After": "1"},
        )
        ok_response = make_http_response(mocker, json_data={"ok": True})
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
        mock_response = make_http_response(mocker, status_code=403, body="Forbidden")
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Access forbidden"):
            client.get("/repos/o/r")
        client.close()

    def test_get_other_error(self, mocker: MockerFixture) -> None:
        """Test other HTTP error handling."""
        client = GitHubClient()
        mock_response = make_http_response(
            mocker, status_code=500, body="Internal Server Error"
        )
        mocker.patch.object(client.session, "get", return_value=mock_response)
        mocker.patch("pr2md.github_client.time.sleep")

        with pytest.raises(GitHubAPIError, match="request failed with status 500"):
            client.get("/repos/o/r")
        client.close()

    def test_get_retries_transient_error(self, mocker: MockerFixture) -> None:
        """Test retry on 503 then success."""
        client = GitHubClient()
        fail_response = make_http_response(
            mocker, status_code=503, body="Service Unavailable"
        )
        ok_response = make_http_response(mocker, json_data={"ok": True})
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
        page1 = make_http_response(
            mocker,
            json_data=[{"id": 1}],
            headers={"Link": '<https://api.github.com/page2>; rel="next"'},
        )
        page2 = make_http_response(mocker, json_data=[{"id": 2}])
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
        mock_response = make_http_response(mocker, json_data={"unexpected": True})
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Expected paginated list"):
            client.get_paginated("/repos/o/r/issues/1/comments")
        client.close()

    def test_get_retries_exhausted_on_502(self, mocker: MockerFixture) -> None:
        """Test retry exhaustion on persistent 502."""
        client = GitHubClient()
        fail_response = make_http_response(mocker, status_code=502, body="Bad Gateway")
        mocker.patch.object(client.session, "get", return_value=fail_response)
        mocker.patch("pr2md.github_client.time.sleep")

        with pytest.raises(GitHubAPIError, match="request failed with status 502"):
            client.get("/repos/o/r")
        client.close()

    def test_get_paginated_fetches_all_pages(self, mocker: MockerFixture) -> None:
        """Test pagination continues until no next link."""
        client = GitHubClient()

        def make_page(page_id: int, *, has_next: bool) -> object:
            headers: dict[str, str] = {}
            if has_next:
                headers = {
                    "Link": (f'<https://api.github.com/page{page_id + 1}>; rel="next"')
                }
            return make_http_response(
                mocker, json_data=[{"id": page_id}], headers=headers
            )

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
        page1 = make_http_response(
            mocker,
            json_data=[{"id": 1}],
            headers={"Link": '<https://evil.example.com/page2>; rel="next"'},
        )
        mocker.patch.object(client.session, "get", return_value=page1)

        with pytest.raises(GitHubAPIError, match="rejected"):
            client.get_paginated("/repos/o/r/issues/1/comments")
        client.close()

    def test_get_401_error(self, mocker: MockerFixture) -> None:
        """Test 401 handling."""
        client = GitHubClient()
        mock_response = make_http_response(mocker, status_code=401, body="Unauthorized")
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="authentication required"):
            client.get("/repos/o/r")
        assert mock_response.status_code == 401  # type: ignore[attr-defined]
        client.close()

    def test_get_json_decode_error(self, mocker: MockerFixture) -> None:
        """Test invalid JSON response handling."""
        client = GitHubClient()
        mock_response = make_http_response(mocker, body="{not-json")
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Invalid JSON"):
            client.get("/repos/o/r")
        client.close()

    def test_get_429_retries_until_success(self, mocker: MockerFixture) -> None:
        """Test 429 waits and retries until success."""
        client = GitHubClient()
        rate_limited = make_http_response(
            mocker,
            status_code=429,
            body="Too Many Requests",
            headers={"Retry-After": "2"},
        )
        ok_response = make_http_response(mocker, json_data={"ok": True})
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
        mock_response = make_http_response(mocker, status_code=404, body="Not Found")
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError) as exc_info:
            client.get("/missing")
        assert exc_info.value.status_code == 404
        client.close()

    def test_get_truncates_large_error_body(self, mocker: MockerFixture) -> None:
        """Test error messages truncate very large response bodies."""
        client = GitHubClient()
        mock_response = make_http_response(mocker, status_code=500, body="x" * 1000)
        mocker.patch.object(client.session, "get", return_value=mock_response)
        mocker.patch("pr2md.github_client.time.sleep")

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
        gateway_timeout = make_http_response(
            mocker, status_code=504, body="Gateway Timeout"
        )
        ok_response = make_http_response(mocker, json_data={"ok": True})
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
        rate_limited = make_http_response(
            mocker,
            status_code=429,
            body="Too Many Requests",
            headers={"Retry-After": "1"},
        )
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
            return make_http_response(
                mocker,
                json_data=[{"id": 1}],
                headers={"Link": '<https://api.github.com/next>; rel="next"'},
            )

        mocker.patch.object(
            client.session,
            "get",
            side_effect=[make_page() for _ in range(_MAX_PAGINATED_PAGES + 1)],
        )

        with pytest.raises(GitHubAPIError, match="Pagination limit exceeded"):
            client.get_paginated("/repos/o/r/issues/1/comments")
        client.close()

    def test_log_rate_limit_low_remaining(
        self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test low remaining rate limit triggers info log."""
        client = GitHubClient()
        mock_response = make_http_response(
            mocker,
            json_data={"ok": True},
            headers={"X-RateLimit-Remaining": "5"},
        )
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with caplog.at_level(logging.INFO, logger="pr2md.github_client"):
            client.get("/repos/o/r")

        assert any("nearly exhausted" in record.message for record in caplog.records)
        client.close()

    def test_rate_limit_wait_invalid_reset_header(self, mocker: MockerFixture) -> None:
        """Test invalid reset header falls back to default wait."""
        from pr2md.github_client import _rate_limit_wait_seconds

        response = mocker.Mock()
        response.headers = {"X-RateLimit-Reset": "not-a-timestamp"}
        assert _rate_limit_wait_seconds(response) == 60.0

    def test_connection_error_retry_exhausted(self, mocker: MockerFixture) -> None:
        """Test connection errors retry until exhausted."""
        client = GitHubClient()
        mock_get = mocker.patch.object(
            client.session,
            "get",
            side_effect=requests.ConnectionError("network down"),
        )
        mocker.patch("pr2md.github_client.time.sleep")

        with pytest.raises(GitHubAPIError, match="GitHub API request failed"):
            client.get("/repos/o/r")
        assert mock_get.call_count == 3
        client.close()

    def test_session_trust_env_disabled(self) -> None:
        """Test HTTP session ignores proxy environment variables."""
        client = GitHubClient()
        assert client.session.trust_env is False
        client.close()

    def test_proactive_wait_when_remaining_zero(self, mocker: MockerFixture) -> None:
        """Test proactive wait when successful response has zero remaining quota."""
        client = GitHubClient()
        mock_response = make_http_response(
            mocker,
            json_data={"ok": True},
            headers={"X-RateLimit-Remaining": "0", "Retry-After": "1"},
        )
        mocker.patch.object(client.session, "get", return_value=mock_response)
        mock_sleep = mocker.patch("pr2md.github_client.time.sleep")

        assert client.get("/repos/o/r") == {"ok": True}
        mock_sleep.assert_called_once_with(1.0)
        client.close()

    def test_proactive_wait_skipped_when_remaining_positive(
        self, mocker: MockerFixture
    ) -> None:
        """Test no proactive wait when quota remains."""
        client = GitHubClient()
        mock_response = make_http_response(
            mocker,
            json_data={"ok": True},
            headers={"X-RateLimit-Remaining": "10"},
        )
        mocker.patch.object(client.session, "get", return_value=mock_response)
        mock_sleep = mocker.patch("pr2md.github_client.time.sleep")

        assert client.get("/repos/o/r") == {"ok": True}
        mock_sleep.assert_not_called()
        client.close()

    def test_proactive_rate_limit_budget_exceeded(self, mocker: MockerFixture) -> None:
        """Test proactive wait stops when the session wait budget is exhausted."""
        client = GitHubClient()
        client._rate_limit_waits = 5
        client._total_rate_limit_wait_seconds = 3600.0
        mock_response = make_http_response(
            mocker,
            json_data={"ok": True},
            headers={"X-RateLimit-Remaining": "0", "Retry-After": "1"},
        )
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="maximum wait time reached"):
            client.get("/repos/o/r")
        client.close()

    def test_fetch_issue_or_pr_metadata_pr(self, mocker: MockerFixture) -> None:
        """Test metadata probe returns PR type without issue payload."""
        client = GitHubClient()
        mocker.patch.object(
            client,
            "get",
            return_value={"number": 1, "pull_request": {"url": "https://example.com"}},
        )

        ref_type, payload = client.fetch_issue_or_pr_metadata("o", "r", 1)
        assert ref_type == "pr"
        assert payload is None
        client.close()

    def test_fetch_issue_or_pr_metadata_issue(self, mocker: MockerFixture) -> None:
        """Test metadata probe returns issue payload for reuse."""
        client = GitHubClient()
        issue_data = {"number": 1, "title": "Issue"}
        mocker.patch.object(client, "get", return_value=issue_data)

        ref_type, payload = client.fetch_issue_or_pr_metadata("o", "r", 1)
        assert ref_type == "issue"
        assert payload == issue_data
        client.close()

    def test_raise_for_status_forbidden_on_403(self, mocker: MockerFixture) -> None:
        """Test 403 responses surface as access forbidden errors."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 403
        mock_response.text = "API rate limit exceeded"
        mock_response.headers = {}

        with pytest.raises(GitHubAPIError, match="Access forbidden"):
            client._raise_for_status(mock_response, "https://api.github.com/repos/o/r")
        client.close()

    def test_log_rate_limit_invalid_remaining_header(
        self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test invalid X-RateLimit-Remaining header is ignored safely."""
        from pr2md.github_client import _log_rate_limit_headers

        response = mocker.Mock()
        response.headers = {"X-RateLimit-Remaining": "not-a-number"}
        with caplog.at_level(logging.DEBUG, logger="pr2md.github_client"):
            _log_rate_limit_headers(response)
        assert not any("nearly exhausted" in r.message for r in caplog.records)

    def test_package_version_fallback(self, mocker: MockerFixture) -> None:
        """Test package version fallback when metadata is unavailable."""
        from importlib.metadata import PackageNotFoundError

        from pr2md._version import _fallback_version, get_version

        mocker.patch(
            "pr2md._version.version",
            side_effect=PackageNotFoundError("PR2MD"),
        )
        _fallback_version.cache_clear()
        assert get_version() != "unknown"


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

    def test_str_message_only(self) -> None:
        """Test string representation with message only."""
        err = GitHubAPIError("failed")
        assert str(err) == "failed"

    def test_str_includes_url_without_status(self) -> None:
        """Test string representation with URL but no status code."""
        err = GitHubAPIError("failed", url="https://api.github.com/test")
        text = str(err)
        assert "failed" in text
        assert "url=https://api.github.com/test" in text
        assert "status_code" not in text

    def test_str_includes_status_without_url(self) -> None:
        """Test string representation with status code but no URL."""
        err = GitHubAPIError("failed", status_code=503)
        text = str(err)
        assert "failed" in text
        assert "status_code=503" in text
        assert "url=" not in text


class TestAllowedGithubApiUrl:
    """Tests for GitHub API URL allowlist."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://api.github.com/repos/o/r/pulls/1", True),
            ("http://api.github.com/repos/o/r/pulls/1", False),
            ("https://evil.com/repos/o/r/pulls/1", False),
            ("https://api.github.com.evil.com/repos/o/r/pulls/1", False),
        ],
    )
    def test_is_allowed_github_api_url(self, url: str, expected: bool) -> None:
        """Test URL allowlist accepts only HTTPS api.github.com."""
        from pr2md.github_client import _is_allowed_github_api_url

        assert _is_allowed_github_api_url(url) is expected

    def test_request_rejects_non_github_url(self) -> None:
        """Test HTTP requests reject URLs outside the GitHub API host."""
        client = GitHubClient()
        with pytest.raises(GitHubAPIError, match="Request URL rejected"):
            client._request_with_retries("https://evil.com/steal")
        client.close()

    def test_get_streams_large_json_body(self, mocker: MockerFixture) -> None:
        """Test large JSON payloads are assembled from streamed chunks."""
        client = GitHubClient()
        large_payload = {"items": ["x" * 1000 for _ in range(200)]}
        mock_response = make_http_response(mocker, json_data=large_payload)
        mocker.patch.object(client.session, "get", return_value=mock_response)

        assert client.get("/repos/o/r") == large_payload
        client.close()

    def test_get_diff_uses_extended_read_timeout(self, mocker: MockerFixture) -> None:
        """Test diff requests use the extended read timeout."""
        client = GitHubClient()
        mock_response = make_http_response(mocker, body="large diff")
        mock_get = mocker.patch.object(
            client.session, "get", return_value=mock_response
        )

        client.get("/repos/o/r/pulls/1", accept="application/vnd.github.v3.diff")

        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == (10, 300)
        client.close()

    def test_get_403_rate_limit_via_remaining_header(
        self, mocker: MockerFixture
    ) -> None:
        """Test 403 with zero remaining quota is treated as rate limited."""
        client = GitHubClient()
        rate_limited = make_http_response(
            mocker,
            status_code=403,
            body="secondary limit",
            headers={"X-RateLimit-Remaining": "0", "Retry-After": "1"},
        )
        ok_response = make_http_response(mocker, json_data={"ok": True})
        mocker.patch.object(
            client.session,
            "get",
            side_effect=[rate_limited, ok_response],
        )
        mocker.patch("pr2md.github_client.time.sleep")

        assert client.get("/repos/o/r") == {"ok": True}
        client.close()

    def test_get_retries_500_until_success(self, mocker: MockerFixture) -> None:
        """Test HTTP 500 is retried before failing."""
        client = GitHubClient()
        fail_response = make_http_response(mocker, status_code=500, body="error")
        ok_response = make_http_response(mocker, json_data={"ok": True})
        mocker.patch.object(
            client.session,
            "get",
            side_effect=[fail_response, ok_response],
        )
        mocker.patch("pr2md.github_client.time.sleep")

        assert client.get("/repos/o/r") == {"ok": True}
        client.close()

    def test_get_rejects_invalid_endpoint(self) -> None:
        """Test malformed endpoints are rejected."""
        client = GitHubClient()
        with pytest.raises(GitHubAPIError, match="must start with"):
            client.get("repos/o/r")
        with pytest.raises(GitHubAPIError, match="contains"):
            client.get("/repos/../evil")
        client.close()

    def test_fetch_issue_or_pr_metadata_rejects_invalid_owner(self) -> None:
        """Test metadata probe validates owner names."""
        client = GitHubClient()
        with pytest.raises(ValueError, match="Invalid owner"):
            client.fetch_issue_or_pr_metadata("bad owner", "repo", 1)
        client.close()

    def test_redirect_hook_rejects_foreign_location(
        self, mocker: MockerFixture
    ) -> None:
        """Test redirect hook rejects non-GitHub redirect targets."""
        from pr2md.github_client import _redirect_pin_hook

        response = mocker.Mock()
        response.is_redirect = True
        response.status_code = 302
        response.url = "https://api.github.com/start"
        response.headers = {"Location": "https://evil.example.com/steal"}

        with pytest.raises(GitHubAPIError, match="Redirect rejected"):
            _redirect_pin_hook(response)
