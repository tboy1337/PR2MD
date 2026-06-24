"""Shared pytest fixtures."""

import json
from pathlib import Path
from typing import Any, Iterator

import pytest
from pytest_mock import MockerFixture


def make_http_response(
    mocker: MockerFixture,
    *,
    status_code: int = 200,
    body: bytes | str = b"",
    json_data: object | None = None,
    headers: dict[str, str] | None = None,
    encoding: str = "utf-8",
    is_redirect: bool = False,
    redirect_location: str = "",
) -> object:
    """Build a requests.Response mock with streaming iter_content support."""
    if json_data is not None:
        payload = json.dumps(json_data).encode(encoding)
    elif isinstance(body, str):
        payload = body.encode(encoding)
    else:
        payload = body

    response = mocker.Mock()
    response.status_code = status_code
    response.headers = headers or {}
    response.encoding = encoding
    response.is_redirect = is_redirect
    if is_redirect:
        response.headers = {**response.headers, "Location": redirect_location}

    def iter_content(chunk_size: int = 65536) -> Iterator[bytes]:
        offset = 0
        while offset < len(payload):
            yield payload[offset : offset + chunk_size]
            offset += chunk_size

    response.iter_content = iter_content
    return response


@pytest.fixture
def work_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Use a temporary directory as the process working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def sample_pr_dict() -> dict[str, Any]:
    """Minimal pull request API payload."""
    return {
        "number": 123,
        "title": "Test PR",
        "body": "Description",
        "state": "open",
        "user": {
            "login": "author",
            "id": 1,
            "avatar_url": "https://example.com/avatar.jpg",
            "html_url": "https://github.com/author",
        },
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
        "closed_at": None,
        "merged_at": None,
        "merge_commit_sha": None,
        "html_url": "https://github.com/owner/repo/pull/123",
        "labels": [],
        "additions": 10,
        "deletions": 5,
        "changed_files": 2,
        "head": {"ref": "feature", "sha": "abc123"},
        "base": {"ref": "main", "sha": "def456"},
    }


@pytest.fixture
def sample_issue_dict() -> dict[str, Any]:
    """Minimal issue API payload."""
    return {
        "number": 123,
        "title": "Test Issue",
        "body": "Issue body",
        "state": "open",
        "user": {
            "login": "author",
            "id": 1,
            "avatar_url": "https://example.com/avatar.jpg",
            "html_url": "https://github.com/author",
        },
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
        "closed_at": None,
        "html_url": "https://github.com/owner/repo/issues/123",
        "labels": [],
    }
