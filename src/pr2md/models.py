"""Data models for GitHub PR extraction."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


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
            login=str(data["login"]),
            id=int(data["id"]),
            avatar_url=str(data["avatar_url"]),
            html_url=str(data["html_url"]),
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
            name=str(data["name"]),
            color=str(data["color"]),
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
            id=int(data["id"]),
            user=User.from_dict(dict(data["user"])),
            body=str(data["body"]),
            created_at=datetime.fromisoformat(
                str(data["created_at"]).replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                str(data["updated_at"]).replace("Z", "+00:00")
            ),
            html_url=str(data["html_url"]),
        )


@dataclass
class ReviewComment:
    """GitHub review comment (inline code comment)."""

    id: int
    user: User
    body: str
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
            id=int(data["id"]),
            user=User.from_dict(dict(data["user"])),
            body=str(data["body"]),
            path=str(data["path"]),
            position=int(data["position"]) if data.get("position") else None,
            original_position=(
                int(data["original_position"])
                if data.get("original_position")
                else None
            ),
            commit_id=str(data["commit_id"]),
            original_commit_id=str(data["original_commit_id"]),
            diff_hunk=str(data["diff_hunk"]),
            created_at=datetime.fromisoformat(
                str(data["created_at"]).replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                str(data["updated_at"]).replace("Z", "+00:00")
            ),
            html_url=str(data["html_url"]),
            in_reply_to_id=(
                int(data["in_reply_to_id"]) if data.get("in_reply_to_id") else None
            ),
            subject_type=(
                str(data["subject_type"]) if data.get("subject_type") else None
            ),
            start_line=int(data["start_line"]) if data.get("start_line") else None,
            line=int(data["line"]) if data.get("line") else None,
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
    commit_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Review":
        """Create Review from API response dictionary."""
        submitted_at = None
        if data.get("submitted_at"):
            submitted_at = datetime.fromisoformat(
                str(data["submitted_at"]).replace("Z", "+00:00")
            )

        return cls(
            id=int(data["id"]),
            user=User.from_dict(dict(data["user"])),
            body=str(data["body"]) if data.get("body") is not None else None,
            state=str(data["state"]),
            html_url=str(data["html_url"]),
            submitted_at=submitted_at,
            commit_id=str(data["commit_id"]),
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
            number=int(data["number"]),
            title=str(data["title"]),
            body=str(data["body"]) if data.get("body") is not None else None,
            state=str(data["state"]),
            user=User.from_dict(dict(data["user"])),
            created_at=datetime.fromisoformat(
                str(data["created_at"]).replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                str(data["updated_at"]).replace("Z", "+00:00")
            ),
            closed_at=closed_at,
            html_url=str(data["html_url"]),
            labels=[Label.from_dict(dict(label)) for label in list(data["labels"])],
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

        return cls(
            number=int(data["number"]),
            title=str(data["title"]),
            body=str(data["body"]) if data.get("body") is not None else None,
            state=str(data["state"]),
            user=User.from_dict(dict(data["user"])),
            created_at=datetime.fromisoformat(
                str(data["created_at"]).replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                str(data["updated_at"]).replace("Z", "+00:00")
            ),
            closed_at=closed_at,
            merged_at=merged_at,
            merge_commit_sha=(
                str(data["merge_commit_sha"])
                if data.get("merge_commit_sha") is not None
                else None
            ),
            html_url=str(data["html_url"]),
            labels=[Label.from_dict(dict(label)) for label in list(data["labels"])],
            additions=int(data["additions"]),
            deletions=int(data["deletions"]),
            changed_files=int(data["changed_files"]),
            head_ref=str(data["head"]["ref"]),
            base_ref=str(data["base"]["ref"]),
            head_sha=str(data["head"]["sha"]),
            base_sha=str(data["base"]["sha"]),
        )
