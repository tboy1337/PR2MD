"""Tests for input validation helpers."""

import pytest

from pr2md.validation import (
    validate_depth,
    validate_issue_number,
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
