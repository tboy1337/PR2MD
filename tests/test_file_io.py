"""Tests for atomic file write utilities."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from pr2md.file_io import write_text_atomic


class TestWriteTextAtomic:
    """Tests for write_text_atomic."""

    def test_writes_content(self, tmp_path: Path) -> None:
        """Test successful atomic write."""
        target = tmp_path / "output.md"
        write_text_atomic(target, "hello world")
        assert target.read_text(encoding="utf-8") == "hello world"
        assert not target.with_suffix(target.suffix + ".tmp").exists()

    def test_cleans_up_temp_file_on_write_failure(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Test temp file is removed when write fails."""
        target = tmp_path / "output.md"
        temp_path = target.with_suffix(target.suffix + ".tmp")
        original_write_text = Path.write_text

        def failing_write_text(
            self: Path, data: str, encoding: str = "utf-8", errors: str | None = None
        ) -> int:
            if self == temp_path:
                raise OSError("disk full")
            return original_write_text(self, data, encoding=encoding, errors=errors)

        mocker.patch.object(Path, "write_text", failing_write_text)

        with pytest.raises(OSError, match="disk full"):
            write_text_atomic(target, "content")

        assert not temp_path.exists()
        assert not target.exists()
