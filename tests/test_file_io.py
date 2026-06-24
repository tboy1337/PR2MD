"""Tests for atomic file write utilities."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from pr2md.file_io import append_text_atomic, log_overwrite_if_exists, write_text_atomic


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


class TestAppendTextAtomic:
    """Tests for append_text_atomic."""

    def test_appends_to_existing_file(self, tmp_path: Path) -> None:
        """Test appending content to an existing file."""
        target = tmp_path / "output.md"
        target.write_text("existing", encoding="utf-8")
        append_text_atomic(target, "\n\nappended")
        assert target.read_text(encoding="utf-8") == "existing\n\nappended"

    def test_creates_file_when_missing(self, tmp_path: Path) -> None:
        """Test append creates a new file when the target is missing."""
        target = tmp_path / "output.md"
        append_text_atomic(target, "new content")
        assert target.read_text(encoding="utf-8") == "new content"

    def test_custom_encoding(self, tmp_path: Path) -> None:
        """Test append with a custom encoding."""
        target = tmp_path / "output.md"
        append_text_atomic(target, "café", encoding="utf-8")
        assert target.read_text(encoding="utf-8") == "café"

    def test_overwrites_via_atomic_replace(self, tmp_path: Path) -> None:
        """Test append replaces the file atomically."""
        target = tmp_path / "output.md"
        write_text_atomic(target, "first")
        append_text_atomic(target, "\nsecond")
        assert target.read_text(encoding="utf-8") == "first\nsecond"


class TestLogOverwriteIfExists:
    """Tests for log_overwrite_if_exists."""

    def test_logs_when_file_exists(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test overwrite warning is logged for existing files."""
        target = tmp_path / "output.md"
        target.write_text("existing", encoding="utf-8")
        with caplog.at_level("INFO", logger="pr2md.file_io"):
            log_overwrite_if_exists(target)
        assert "Overwriting existing file" in caplog.text

    def test_silent_when_file_missing(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test no log when the target file does not exist."""
        target = tmp_path / "missing.md"
        with caplog.at_level("INFO", logger="pr2md.file_io"):
            log_overwrite_if_exists(target)
        assert "Overwriting existing file" not in caplog.text
