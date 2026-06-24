"""Atomic file write utilities."""

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
    temp_path = target.with_suffix(target.suffix + ".tmp")
    try:
        temp_path.write_text(content, encoding=encoding)
        temp_path.replace(target)
    except OSError:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise
