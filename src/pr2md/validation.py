"""Input validation helpers for CLI arguments."""

import re
from pathlib import Path

_GITHUB_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")
_MAX_OWNER_LENGTH = 39
_MAX_REPO_LENGTH = 100
_MAX_ISSUE_NUMBER = 2**31 - 1
_MAX_DEPTH = 10


def validate_github_name(name: str, field: str, *, max_length: int) -> None:
    """
    Validate a GitHub owner or repository name.

    Raises:
        ValueError: If the name is invalid
    """
    if not name:
        raise ValueError(f"Invalid {field}: name cannot be empty")
    if len(name) > max_length:
        raise ValueError(
            f"Invalid {field}: '{name}' exceeds maximum length of {max_length}"
        )
    if not _GITHUB_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid {field}: '{name}' contains invalid characters "
            "(allowed: letters, digits, '.', '_', '-')"
        )


def validate_owner(owner: str) -> None:
    """Validate a GitHub repository owner."""
    validate_github_name(owner, "owner", max_length=_MAX_OWNER_LENGTH)


def validate_repo(repo: str) -> None:
    """Validate a GitHub repository name."""
    validate_github_name(repo, "repository", max_length=_MAX_REPO_LENGTH)


def validate_issue_number(number: int) -> None:
    """Validate a GitHub issue or PR number."""
    if number < 1:
        raise ValueError(f"Invalid number: {number} must be positive")
    if number > _MAX_ISSUE_NUMBER:
        raise ValueError(
            f"Invalid number: {number} exceeds maximum "
            f"{_MAX_ISSUE_NUMBER}"
        )


def validate_depth(depth: int) -> None:
    """Validate reference download recursion depth."""
    if depth < 0:
        raise ValueError(f"Invalid depth: {depth} must be non-negative")
    if depth > _MAX_DEPTH:
        raise ValueError(f"Invalid depth: {depth} exceeds maximum of {_MAX_DEPTH}")


def validate_output_path(output_path: str) -> str:
    """
    Validate and resolve an output file path within the current working directory.

    Returns:
        Resolved path string

    Raises:
        ValueError: If the path escapes the current working directory
    """
    cwd = Path.cwd().resolve()
    resolved = Path(output_path).resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError as err:
        raise ValueError(
            f"Invalid output path: '{output_path}' must be within the current "
            f"working directory ({cwd})"
        ) from err
    return str(resolved)
