"""Tests for input validation helpers."""

from pathlib import Path

import pytest

from pr2md.validation import (
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

    def test_validate_output_path_within_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        with pytest.raises(ValueError, match="must be within the current working directory"):
            validate_output_path("../../outside.md")
