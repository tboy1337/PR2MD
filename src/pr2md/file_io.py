"""Atomic file write utilities."""

import logging
import os
import uuid
from pathlib import Path

from pr2md.validation import _STREAM_CHUNK_SIZE, assert_safe_write_path

logger = logging.getLogger(__name__)


def _temp_path_for(target: Path) -> Path:
    """Return a unique temporary path alongside *target* for atomic writes."""
    unique = f"{os.getpid()}.{uuid.uuid4().hex}"
    return target.with_name(f"{target.stem}.{unique}{target.suffix}.tmp")


def _fsync_path(path: Path) -> None:
    """Flush file contents to storage when supported by the platform."""
    try:
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
    except OSError:
        pass


def _ensure_parent_directory(target: Path) -> None:
    """Create parent directories for *target* when missing."""
    parent = target.parent
    if str(parent) not in ("", ".") and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)


def write_text_atomic(
    path: Path | str, content: str, *, encoding: str = "utf-8"
) -> None:
    """
    Write text to a file atomically via a temporary file and rename.

    Args:
        path: Destination file path
        content: Text content to write
        encoding: Text encoding

    Raises:
        OSError: If the write or rename fails
        ValueError: If the path is not safe to write
    """
    target = assert_safe_write_path(path)
    _ensure_parent_directory(target)
    temp_path = _temp_path_for(target)
    try:
        temp_path.write_text(content, encoding=encoding)
        _fsync_path(temp_path)
        temp_path.replace(target)
    except OSError:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise


def append_text_atomic(
    path: Path | str, suffix: str, *, encoding: str = "utf-8"
) -> None:
    """
    Append text to a file atomically via a temporary file and rename.

    Streams existing content when present so large files are not loaded entirely
    into memory.

    Args:
        path: Destination file path
        suffix: Text to append (may include leading newlines)
        encoding: Text encoding

    Raises:
        OSError: If the read, write, or rename fails
        ValueError: If the path is not safe to write
    """
    target = assert_safe_write_path(path)
    _ensure_parent_directory(target)
    temp_path = _temp_path_for(target)
    try:
        with temp_path.open("w", encoding=encoding) as dest:
            if target.exists():
                with target.open("r", encoding=encoding) as src:
                    while True:
                        chunk = src.read(_STREAM_CHUNK_SIZE)
                        if not chunk:
                            break
                        dest.write(chunk)
                dest.write(suffix)
            else:
                dest.write(suffix)
        _fsync_path(temp_path)
        temp_path.replace(target)
    except OSError:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise


def log_overwrite_if_exists(path: Path | str) -> None:
    """Log when an existing output file will be overwritten."""
    target = Path(path)
    if target.exists():
        logger.info("Overwriting existing file: %s", target)
