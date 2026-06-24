"""Atomic file write utilities."""

import os
import uuid
from pathlib import Path


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
    unique = f"{os.getpid()}.{uuid.uuid4().hex}"
    temp_path = target.with_name(f"{target.stem}.{unique}{target.suffix}.tmp")
    try:
        temp_path.write_text(content, encoding=encoding)
        temp_path.replace(target)
    except OSError:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise
