"""Atomic file write utilities."""

import logging
import os
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


def _temp_path_for(target: Path) -> Path:
    """Return a unique temporary path alongside *target* for atomic writes."""
    unique = f"{os.getpid()}.{uuid.uuid4().hex}"
    return target.with_name(f"{target.stem}.{unique}{target.suffix}.tmp")


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
    """
    target = Path(path)
    temp_path = _temp_path_for(target)
    try:
        temp_path.write_text(content, encoding=encoding)
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

    Reads existing content (if the file exists), combines it with *suffix*,
    and writes the result in a single atomic replace.

    Args:
        path: Destination file path
        suffix: Text to append (may include leading newlines)
        encoding: Text encoding

    Raises:
        OSError: If the read, write, or rename fails
    """
    target = Path(path)
    existing = target.read_text(encoding=encoding) if target.exists() else ""
    combined = f"{existing}{suffix}" if existing else suffix.lstrip("\n")
    temp_path = _temp_path_for(target)
    try:
        temp_path.write_text(combined, encoding=encoding)
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
