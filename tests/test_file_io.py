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
        assert not list(target.parent.glob(f"{target.stem}.*.tmp"))

    def test_cleans_up_temp_file_on_write_failure(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Test temp file is removed when write fails."""
        target = tmp_path / "output.md"
        original_write_text = Path.write_text

        def failing_write_text(
            self: Path, data: str, encoding: str = "utf-8", errors: str | None = None
        ) -> int:
            if self.name.endswith(".tmp"):
                raise OSError("disk full")
            return original_write_text(self, data, encoding=encoding, errors=errors)

        mocker.patch.object(Path, "write_text", failing_write_text)

        with pytest.raises(OSError, match="disk full"):
            write_text_atomic(target, "content")

        assert not list(tmp_path.glob("*.tmp"))
        assert not target.exists()

    def test_cleans_up_temp_file_on_replace_failure(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Test temp file is removed when atomic replace fails."""
        target = tmp_path / "output.md"
        original_replace = Path.replace

        def failing_replace(self: Path, target_path: Path) -> Path:
            if self.name.endswith(".tmp"):
                raise OSError("replace failed")
            return original_replace(self, target_path)

        mocker.patch.object(Path, "replace", failing_replace)

        with pytest.raises(OSError, match="replace failed"):
            write_text_atomic(target, "content")

        assert not list(tmp_path.glob("*.tmp"))
        assert not target.exists()

    def test_unique_temp_filenames(self, tmp_path: Path, mocker: MockerFixture) -> None:
        """Test concurrent writes use distinct temporary files."""
        target = tmp_path / "output.md"
        temp_names: list[str] = []
        original_write_text = Path.write_text

        def capture_temp_write(
            self: Path, data: str, encoding: str = "utf-8", errors: str | None = None
        ) -> int:
            if self.name.endswith(".tmp"):
                temp_names.append(self.name)
            return original_write_text(self, data, encoding=encoding, errors=errors)

        mocker.patch.object(Path, "write_text", capture_temp_write)
        write_text_atomic(target, "first")
        write_text_atomic(target, "second")

        assert len(temp_names) == 2
        assert temp_names[0] != temp_names[1]
