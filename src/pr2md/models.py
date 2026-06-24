"""Data models for GitHub PR extraction."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


def _require(data: dict[str, Any], key: str, *, model: str) -> Any:
    """Return a required field from API data or raise a clear ValueError."""
    if key not in data:
        raise ValueError(
            f"Missing required field '{key}' in GitHub API response for {model}"
        )
    return data[key]


@dataclass
class User:
    """GitHub user information."""

    login: str
    id: int
    avatar_url: str
    html_url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        """Create User from API response dictionary."""
        return cls(
            login=str(_require(data, "login", model="User")),
            id=int(_require(data, "id", model="User")),
            avatar_url=str(_require(data, "avatar_url", model="User")),
            html_url=str(_require(data, "html_url", model="User")),
        )

    @classmethod
    def from_dict_optional(cls, data: dict[str, Any] | None) -> "User":
        """Create User from API data, using DELETED_USER when user is null."""
        if data is None:
            return DELETED_USER
        return cls.from_dict(data)


DELETED_USER = User(
    login="[deleted user]",
    id=0,
    avatar_url="",
    html_url="",
)


@dataclass
class Label:
    """GitHub label information."""

    name: str
    color: str
    description: Optional[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Label":
        """Create Label from API response dictionary."""
        return cls(
            name=str(_require(data, "name", model="Label")),
            color=str(_require(data, "color", model="Label")),
            description=(
                str(data["description"])
                if data.get("description") is not None
                else None
            ),
        )


@dataclass
class Comment:
    """GitHub issue/PR comment."""

    id: int
    user: User
    body: str
    created_at: datetime
    updated_at: datetime
    html_url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Comment":
        """Create Comment from API response dictionary."""
        return cls(
            id=int(_require(data, "id", model="Comment")),
            user=User.from_dict_optional(
                dict(data["user"]) if data.get("user") is not None else None
            ),
            body=str(data["body"]) if data.get("body") is not None else "",
            created_at=datetime.fromisoformat(
                str(_require(data, "created_at", model="Comment")).replace(
                    "Z", "+00:00"
                )
            ),
            updated_at=datetime.fromisoformat(
                str(_require(data, "updated_at", model="Comment")).replace(
                    "Z", "+00:00"
                )
            ),
            html_url=str(_require(data, "html_url", model="Comment")),
        )


@dataclass
class ReviewComment:
    """GitHub review comment (inline code comment)."""

    id: int
    user: User
    body: Optional[str]
    path: str
    position: Optional[int]
    original_position: Optional[int]
    commit_id: str
    original_commit_id: str
    diff_hunk: str
    created_at: datetime
    updated_at: datetime
    html_url: str
    in_reply_to_id: Optional[int]
    subject_type: Optional[str] = None
    start_line: Optional[int] = None
    line: Optional[int] = None
    start_side: Optional[str] = None
    side: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewComment":
        """Create ReviewComment from API response dictionary."""
        return cls(
            id=int(_require(data, "id", model="ReviewComment")),
            user=User.from_dict_optional(
                dict(data["user"]) if data.get("user") is not None else None
            ),
            body=str(data["body"]) if data.get("body") is not None else None,
            path=str(_require(data, "path", model="ReviewComment")),
            position=(
                int(data["position"]) if data.get("position") is not None else None
            ),
            original_position=(
                int(data["original_position"])
                if data.get("original_position") is not None
                else None
            ),
            commit_id=str(_require(data, "commit_id", model="ReviewComment")),
            original_commit_id=str(
                _require(data, "original_commit_id", model="ReviewComment")
            ),
            diff_hunk=str(_require(data, "diff_hunk", model="ReviewComment")),
            created_at=datetime.fromisoformat(
                str(_require(data, "created_at", model="ReviewComment")).replace(
                    "Z", "+00:00"
                )
            ),
            updated_at=datetime.fromisoformat(
                str(_require(data, "updated_at", model="ReviewComment")).replace(
                    "Z", "+00:00"
                )
            ),
            html_url=str(_require(data, "html_url", model="ReviewComment")),
            in_reply_to_id=(
                int(data["in_reply_to_id"])
                if data.get("in_reply_to_id") is not None
                else None
            ),
            subject_type=(
                str(data["subject_type"])
                if data.get("subject_type") is not None
                else None
            ),
            start_line=(
                int(data["start_line"]) if data.get("start_line") is not None else None
            ),
            line=int(data["line"]) if data.get("line") is not None else None,
            start_side=str(data["start_side"]) if data.get("start_side") else None,
            side=str(data["side"]) if data.get("side") else None,
        )


@dataclass
class Review:
    """GitHub PR review."""

    id: int
    user: User
    body: Optional[str]
    state: str
    html_url: str
    submitted_at: Optional[datetime]
    commit_id: Optional[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Review":
        """Create Review from API response dictionary."""
        submitted_at = None
        if data.get("submitted_at"):
            submitted_at = datetime.fromisoformat(
                str(data["submitted_at"]).replace("Z", "+00:00")
            )

        return cls(
            id=int(_require(data, "id", model="Review")),
            user=User.from_dict_optional(
                dict(data["user"]) if data.get("user") is not None else None
            ),
            body=str(data["body"]) if data.get("body") is not None else None,
            state=str(_require(data, "state", model="Review")),
            html_url=str(_require(data, "html_url", model="Review")),
            submitted_at=submitted_at,
            commit_id=(
                str(data["commit_id"]) if data.get("commit_id") is not None else None
            ),
        )


@dataclass
class Issue:
    """GitHub Issue."""

    number: int
    title: str
    body: Optional[str]
    state: str
    user: User
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    html_url: str
    labels: list[Label]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Issue":
        """Create Issue from API response dictionary."""
        closed_at = None
        if data.get("closed_at"):
            closed_at = datetime.fromisoformat(
                str(data["closed_at"]).replace("Z", "+00:00")
            )

        return cls(
            number=int(_require(data, "number", model="Issue")),
            title=str(_require(data, "title", model="Issue")),
            body=str(data["body"]) if data.get("body") is not None else None,
            state=str(_require(data, "state", model="Issue")),
            user=User.from_dict_optional(
                dict(data["user"]) if data.get("user") is not None else None
            ),
            created_at=datetime.fromisoformat(
                str(_require(data, "created_at", model="Issue")).replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                str(_require(data, "updated_at", model="Issue")).replace("Z", "+00:00")
            ),
            closed_at=closed_at,
            html_url=str(_require(data, "html_url", model="Issue")),
            labels=[
                Label.from_dict(dict(label))
                for label in list(_require(data, "labels", model="Issue"))
            ],
        )


@dataclass
class PullRequest:
    """GitHub Pull Request."""

    number: int
    title: str
    body: Optional[str]
    state: str
    user: User
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    merged_at: Optional[datetime]
    merge_commit_sha: Optional[str]
    html_url: str
    labels: list[Label]
    additions: int
    deletions: int
    changed_files: int
    head_ref: str
    base_ref: str
    head_sha: str
    base_sha: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PullRequest":
        """Create PullRequest from API response dictionary."""
        closed_at = None
        if data.get("closed_at"):
            closed_at = datetime.fromisoformat(
                str(data["closed_at"]).replace("Z", "+00:00")
            )

        merged_at = None
        if data.get("merged_at"):
            merged_at = datetime.fromisoformat(
                str(data["merged_at"]).replace("Z", "+00:00")
            )

        head = dict(_require(data, "head", model="PullRequest"))
        base = dict(_require(data, "base", model="PullRequest"))

        return cls(
            number=int(_require(data, "number", model="PullRequest")),
            title=str(_require(data, "title", model="PullRequest")),
            body=str(data["body"]) if data.get("body") is not None else None,
            state=str(_require(data, "state", model="PullRequest")),
            user=User.from_dict_optional(
                dict(data["user"]) if data.get("user") is not None else None
            ),
            created_at=datetime.fromisoformat(
                str(_require(data, "created_at", model="PullRequest")).replace(
                    "Z", "+00:00"
                )
            ),
            updated_at=datetime.fromisoformat(
                str(_require(data, "updated_at", model="PullRequest")).replace(
                    "Z", "+00:00"
                )
            ),
            closed_at=closed_at,
            merged_at=merged_at,
            merge_commit_sha=(
                str(data["merge_commit_sha"])
                if data.get("merge_commit_sha") is not None
                else None
            ),
            html_url=str(_require(data, "html_url", model="PullRequest")),
            labels=[
                Label.from_dict(dict(label))
                for label in list(_require(data, "labels", model="PullRequest"))
            ],
            additions=int(_require(data, "additions", model="PullRequest")),
            deletions=int(_require(data, "deletions", model="PullRequest")),
            changed_files=int(_require(data, "changed_files", model="PullRequest")),
            head_ref=str(_require(head, "ref", model="PullRequest.head")),
            base_ref=str(_require(base, "ref", model="PullRequest.base")),
            head_sha=str(_require(head, "sha", model="PullRequest.head")),
            base_sha=str(_require(base, "sha", model="PullRequest.base")),
        )
