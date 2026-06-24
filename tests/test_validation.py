"""Tests for input validation helpers."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from pr2md.validation import (
    assert_safe_write_path,
    sanitize_filename_component,
    validate_depth,
    validate_github_name,
    validate_issue_number,
    validate_output_path,
    validate_owner,
    validate_repo,
)


class TestValidation:
    """Tests for validation helpers."""

    def test_validate_owner_valid(self) -> None:
        """Test valid owner names."""
        validate_owner("psf")
        validate_owner("tboy1337")

    def test_validate_owner_invalid(self) -> None:
        """Test invalid owner names."""
        with pytest.raises(ValueError, match="Invalid owner"):
            validate_owner("bad owner")
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_owner("")

    def test_validate_repo_valid(self) -> None:
        """Test valid repository names."""
        validate_repo("requests")

    def test_validate_repo_invalid(self) -> None:
        """Test invalid repository names."""
        with pytest.raises(ValueError, match="Invalid repository"):
            validate_repo("repo/name")

    def test_validate_repo_max_length(self) -> None:
        """Test repository name at maximum allowed length."""
        validate_repo("a" * 100)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_repo("a" * 101)

    def test_validate_issue_number_valid(self) -> None:
        """Test valid issue numbers."""
        validate_issue_number(1)
        validate_issue_number(6523)

    def test_validate_issue_number_invalid(self) -> None:
        """Test invalid issue numbers."""
        with pytest.raises(ValueError, match="must be positive"):
            validate_issue_number(0)
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_issue_number(2**31)

    def test_validate_depth_valid(self) -> None:
        """Test valid depth values."""
        validate_depth(0)
        validate_depth(10)

    def test_validate_depth_invalid(self) -> None:
        """Test invalid depth values."""
        with pytest.raises(ValueError, match="must be non-negative"):
            validate_depth(-1)
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_depth(11)

    def test_validate_github_name_max_length(self) -> None:
        """Test name length validation."""
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_github_name("a" * 40, "owner", max_length=39)

    def test_validate_github_name_invalid_characters(self) -> None:
        """Test invalid character rejection."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_github_name("bad/name", "repository", max_length=100)

    def test_validate_output_path_within_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test valid output path inside working directory."""
        monkeypatch.chdir(tmp_path)
        resolved = validate_output_path("report.md")
        assert Path(resolved) == (tmp_path / "report.md").resolve()

    def test_validate_output_path_rejects_traversal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test path traversal outside CWD is rejected."""
        work_dir = tmp_path / "work"
        work_dir.mkdir(parents=True)
        monkeypatch.chdir(work_dir)
        with pytest.raises(
            ValueError, match="must be within the current working directory"
        ):
            validate_output_path("../../outside.md")

    def test_validate_output_path_rejects_empty(self) -> None:
        """Test empty output paths are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_output_path("")
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_output_path("   ")

    def test_validate_output_path_rejects_symlink_component(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
    ) -> None:
        """Test symlink components are rejected without creating real symlinks."""
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        monkeypatch.chdir(work_dir)

        original_is_symlink = Path.is_symlink

        def mocked_is_symlink(self: Path) -> bool:
            if self.name == "escape_link":
                return True
            return original_is_symlink(self)

        mocker.patch.object(Path, "is_symlink", mocked_is_symlink)

        with pytest.raises(ValueError, match="contains a symlink component"):
            validate_output_path("escape_link/outside.md")

    def test_validate_output_path_rejects_symlink_escape(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test symlink targets outside CWD are rejected when symlinks can be created."""
        pytest.importorskip("os")
        import os

        if not hasattr(os, "symlink"):
            pytest.skip("symlinks not supported on this platform")

        work_dir = tmp_path / "work"
        outside_dir = tmp_path / "outside"
        work_dir.mkdir()
        outside_dir.mkdir()
        link_path = work_dir / "escape_link"
        try:
            os.symlink(outside_dir, link_path, target_is_directory=True)
        except OSError as err:
            pytest.skip(f"cannot create symlink: {err}")

        monkeypatch.chdir(work_dir)
        with pytest.raises(ValueError):
            validate_output_path("escape_link/outside.md")

    def test_sanitize_filename_component_reserved_names(self) -> None:
        """Test Windows reserved device names are prefixed."""
        assert sanitize_filename_component("CON") == "_CON"
        assert sanitize_filename_component("com1") == "_com1"
        assert sanitize_filename_component("owner") == "owner"
        assert sanitize_filename_component("CON.txt") == "_CON.txt"

    def test_assert_safe_write_path_rejects_escape(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test pre-write path check rejects paths outside CWD."""
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        monkeypatch.chdir(work_dir)
        with pytest.raises(
            ValueError, match="must be within the current working directory"
        ):
            assert_safe_write_path(work_dir.parent / "outside.md")

    def test_assert_safe_write_path_accepts_valid_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test pre-write path check accepts paths inside CWD."""
        monkeypatch.chdir(tmp_path)
        resolved = assert_safe_write_path("report.md")
        assert resolved == (tmp_path / "report.md").resolve()

    def test_assert_safe_write_path_rejects_symlink_escape(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test symlink targets outside CWD are rejected before writing."""
        pytest.importorskip("os")
        import os

        if not hasattr(os, "symlink"):
            pytest.skip("symlinks not supported on this platform")

        work_dir = tmp_path / "work"
        outside_dir = tmp_path / "outside"
        work_dir.mkdir()
        outside_dir.mkdir()
        link_path = work_dir / "escape_link"
        try:
            os.symlink(outside_dir, link_path, target_is_directory=True)
        except OSError as err:
            pytest.skip(f"cannot create symlink: {err}")

        monkeypatch.chdir(work_dir)
        with pytest.raises(ValueError, match="symlink component"):
            assert_safe_write_path("escape_link/outside.md")
