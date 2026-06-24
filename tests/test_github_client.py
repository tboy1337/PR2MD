"""Tests for GitHub API client."""

# pylint: disable=protected-access

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
        mocker.patch.object(client.session, "get", return_value=mock_response)

        assert client.get("/repos/o/r") == {"key": "value"}
        client.close()

    def test_get_success_diff(self, mocker: MockerFixture) -> None:
        """Test successful diff GET."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "diff content"
        mocker.patch.object(client.session, "get", return_value=mock_response)

        result = client.get("/repos/o/r/pulls/1", accept="application/vnd.github.v3.diff")
        assert result == "diff content"
        client.close()

    def test_get_404_error(self, mocker: MockerFixture) -> None:
        """Test 404 handling."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="Resource not found"):
            client.get("/missing")
        client.close()

    def test_get_403_rate_limit(self, mocker: MockerFixture) -> None:
        """Test rate limit handling."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 403
        mock_response.text = "API rate limit exceeded"
        mocker.patch.object(client.session, "get", return_value=mock_response)

        with pytest.raises(GitHubAPIError, match="rate limit"):
            client.get("/repos/o/r")
        client.close()

    def test_get_403_forbidden(self, mocker: MockerFixture) -> None:
        """Test forbidden handling."""
        client = GitHubClient()
        mock_response = mocker.Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
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
        ok_response = mocker.Mock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"ok": True}
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
        page1.headers = {
            "Link": '<https://api.github.com/page2>; rel="next"'
        }
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
            side_effect=GitHubAPIError("Resource not found"),
        )
        assert client.fetch_issue_or_pr_type("o", "r", 1) is None
        client.close()

    def test_context_manager(self, mocker: MockerFixture) -> None:
        """Test client context manager closes session."""
        with GitHubClient() as client:
            mock_close = mocker.patch.object(client.session, "close")
        mock_close.assert_called_once()
