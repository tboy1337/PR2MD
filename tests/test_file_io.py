"""Tests for atomic file write utilities."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from pr2md.file_io import append_text_atomic, log_overwrite_if_exists, write_text_atomic


class TestWriteTextAtomic:
    """Tests for write_text_atomic."""

    def test_writes_content(self, work_dir: Path) -> None:
        """Test successful atomic write."""
        target = work_dir / "output.md"
        write_text_atomic(target, "hello world")
        assert target.read_text(encoding="utf-8") == "hello world"
        assert not list(target.parent.glob(f"{target.stem}.*.tmp"))

    def test_cleans_up_temp_file_on_write_failure(
        self, work_dir: Path, mocker: MockerFixture
    ) -> None:
        """Test temp file is removed when write fails."""
        target = work_dir / "output.md"
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

        assert not list(work_dir.glob("*.tmp"))
        assert not target.exists()

    def test_cleans_up_temp_file_on_replace_failure(
        self, work_dir: Path, mocker: MockerFixture
    ) -> None:
        """Test temp file is removed when atomic replace fails."""
        target = work_dir / "output.md"
        original_replace = Path.replace

        def failing_replace(self: Path, target_path: Path) -> Path:
            if self.name.endswith(".tmp"):
                raise OSError("replace failed")
            return original_replace(self, target_path)

        mocker.patch.object(Path, "replace", failing_replace)

        with pytest.raises(OSError, match="replace failed"):
            write_text_atomic(target, "content")

        assert not list(work_dir.glob("*.tmp"))
        assert not target.exists()

    def test_unique_temp_filenames(self, work_dir: Path, mocker: MockerFixture) -> None:
        """Test concurrent writes use distinct temporary files."""
        target = work_dir / "output.md"
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

    def test_appends_to_existing_file(self, work_dir: Path) -> None:
        """Test appending content to an existing file."""
        target = work_dir / "output.md"
        target.write_text("existing", encoding="utf-8")
        append_text_atomic(target, "\n\nappended")
        assert target.read_text(encoding="utf-8") == "existing\n\nappended"

    def test_creates_file_when_missing(self, work_dir: Path) -> None:
        """Test append creates a new file when the target is missing."""
        target = work_dir / "output.md"
        append_text_atomic(target, "new content")
        assert target.read_text(encoding="utf-8") == "new content"

    def test_custom_encoding(self, work_dir: Path) -> None:
        """Test append with a custom encoding."""
        target = work_dir / "output.md"
        append_text_atomic(target, "café", encoding="utf-8")
        assert target.read_text(encoding="utf-8") == "café"

    def test_overwrites_via_atomic_replace(self, work_dir: Path) -> None:
        """Test append replaces the file atomically."""
        target = work_dir / "output.md"
        write_text_atomic(target, "first")
        append_text_atomic(target, "\nsecond")
        assert target.read_text(encoding="utf-8") == "first\nsecond"

    def test_cleans_up_temp_file_on_write_failure(
        self, work_dir: Path, mocker: MockerFixture
    ) -> None:
        """Test temp file is removed when append write fails."""
        target = work_dir / "output.md"
        target.write_text("existing", encoding="utf-8")
        original_open = Path.open

        def failing_open(self: Path, *args: object, **kwargs: object) -> object:
            if self.name.endswith(".tmp") and "w" in args:
                raise OSError("disk full")
            return original_open(self, *args, **kwargs)  # type: ignore[call-overload]

        mocker.patch.object(Path, "open", failing_open)

        with pytest.raises(OSError, match="disk full"):
            append_text_atomic(target, "\nappended")

        assert not list(work_dir.glob("*.tmp"))
        assert target.read_text(encoding="utf-8") == "existing"

    def test_cleans_up_temp_file_on_append_replace_failure(
        self, work_dir: Path, mocker: MockerFixture
    ) -> None:
        """Test temp file is removed when append replace fails."""
        target = work_dir / "output.md"
        target.write_text("existing", encoding="utf-8")
        original_replace = Path.replace

        def failing_replace(self: Path, target_path: Path) -> Path:
            if self.name.endswith(".tmp"):
                raise OSError("replace failed")
            return original_replace(self, target_path)

        mocker.patch.object(Path, "replace", failing_replace)

        with pytest.raises(OSError, match="replace failed"):
            append_text_atomic(target, "\nappended")

        assert not list(work_dir.glob("*.tmp"))
        assert target.read_text(encoding="utf-8") == "existing"


class TestStreamingAppend:
    """Tests for streaming append behavior."""

    def test_appends_large_existing_file(self, work_dir: Path) -> None:
        """Test append streams large existing files without loading all at once."""
        target = work_dir / "output.md"
        target.write_text("a" * 200_000, encoding="utf-8")
        append_text_atomic(target, "\nEND")
        content = target.read_text(encoding="utf-8")
        assert content.endswith("\nEND")
        assert len(content) == 200_004

    def test_creates_parent_directory(self, work_dir: Path) -> None:
        """Test write creates missing parent directories under CWD."""
        nested = work_dir / "nested" / "dir" / "output.md"
        write_text_atomic(nested, "nested content")
        assert nested.read_text(encoding="utf-8") == "nested content"

    def test_fsync_called_before_replace(
        self, work_dir: Path, mocker: MockerFixture
    ) -> None:
        """Test durability flush is attempted before atomic replace."""
        target = work_dir / "output.md"
        mock_fsync = mocker.patch("pr2md.file_io._fsync_path")
        write_text_atomic(target, "content")
        mock_fsync.assert_called_once()


class TestLogOverwriteIfExists:
    """Tests for log_overwrite_if_exists."""

    def test_logs_when_file_exists(
        self, work_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test overwrite warning is logged for existing files."""
        target = work_dir / "output.md"
        target.write_text("existing", encoding="utf-8")
        with caplog.at_level("INFO", logger="pr2md.file_io"):
            log_overwrite_if_exists(target)
        assert "Overwriting existing file" in caplog.text

    def test_silent_when_file_missing(
        self, work_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test no log when the target file does not exist."""
        target = work_dir / "missing.md"
        with caplog.at_level("INFO", logger="pr2md.file_io"):
            log_overwrite_if_exists(target)
        assert "Overwriting existing file" not in caplog.text
