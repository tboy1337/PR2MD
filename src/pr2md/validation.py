"""Input validation helpers for CLI arguments."""

import re
from pathlib import Path

_GITHUB_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *{f"COM{i}" for i in range(1, 10)},
        *{f"LPT{i}" for i in range(1, 10)},
    }
)
_MAX_OWNER_LENGTH = 39
_MAX_REPO_LENGTH = 100
_MAX_ISSUE_NUMBER = 2**31 - 1
_MAX_DEPTH = 10
_STREAM_CHUNK_SIZE = 64 * 1024


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
            f"Invalid number: {number} exceeds maximum " f"{_MAX_ISSUE_NUMBER}"
        )


def validate_depth(depth: int) -> None:
    """Validate reference download recursion depth."""
    if depth < 0:
        raise ValueError(f"Invalid depth: {depth} must be non-negative")
    if depth > _MAX_DEPTH:
        raise ValueError(f"Invalid depth: {depth} exceeds maximum of {_MAX_DEPTH}")


def sanitize_filename_component(name: str) -> str:
    """
    Prefix Windows reserved device names so they are safe as filename parts.

    Args:
        name: A single path component (no directory separators)

    Returns:
        The original name, or '_' + name when reserved on Windows
    """
    stem = Path(name).stem.upper() if "." in name else name.upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        return f"_{name}"
    return name


def _contains_symlink_component(base: Path, logical_path: Path) -> bool:
    """Return True when any component under *base* is a symlink."""
    candidate = base
    for part in logical_path.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            return True
    return False


def _assert_within_cwd(dest: Path, base: Path, display_path: str) -> None:
    """Raise ValueError when *dest* is outside *base*."""
    try:
        dest.relative_to(base)
    except ValueError as err:
        raise ValueError(
            f"Invalid output path: '{display_path}' must be within the current "
            f"working directory ({base})"
        ) from err


def assert_safe_write_path(path: Path | str) -> Path:
    """
    Re-validate a resolved path immediately before writing.

    Returns:
        Resolved absolute path under the current working directory

    Raises:
        ValueError: If the path escapes CWD or contains a symlink component
    """
    target = Path(path)
    base = Path.cwd().resolve()
    try:
        relative = target.resolve().relative_to(base)
    except ValueError as err:
        raise ValueError(
            f"Invalid output path: '{target}' must be within the current "
            f"working directory ({base})"
        ) from err

    if _contains_symlink_component(base, relative):
        raise ValueError(
            f"Invalid output path: '{relative}' contains a symlink component"
        )

    dest = (base / relative).resolve()
    _assert_within_cwd(dest, base, str(relative))
    return dest


def validate_output_path(output_path: str) -> str:
    """
    Validate and resolve an output file path within the current working directory.

    Returns:
        Resolved path string

    Raises:
        ValueError: If the path escapes the current working directory
    """
    if not output_path or not output_path.strip():
        raise ValueError("Invalid output path: path cannot be empty")

    base = Path.cwd().resolve()
    logical = base / output_path
    if _contains_symlink_component(base, Path(output_path)):
        raise ValueError(
            f"Invalid output path: '{output_path}' contains a symlink component"
        )

    dest = logical.resolve()
    _assert_within_cwd(dest, base, output_path)
    return str(dest)
