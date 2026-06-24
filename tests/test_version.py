"""Tests for package version resolution."""

from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from pr2md._version import _fallback_version, _pyproject_path, get_version


class TestVersion:
    """Tests for get_version and fallback parsing."""

    def test_get_version_uses_installed_metadata(self) -> None:
        """Test installed package metadata is preferred when available."""
        from importlib.metadata import PackageNotFoundError, version

        version_value = get_version()
        assert version_value
        try:
            installed = version("PR2MD")
        except PackageNotFoundError:
            return
        assert installed == version_value

    def test_pyproject_path_points_at_repo_root(self) -> None:
        """Test pyproject path resolves beside the repository root."""
        assert _pyproject_path().name == "pyproject.toml"
        assert _pyproject_path().is_file()

    def test_fallback_reads_pyproject(self, mocker: MockerFixture) -> None:
        """Test fallback parses pyproject.toml when metadata is missing."""
        mocker.patch(
            "pr2md._version.version",
            side_effect=PackageNotFoundError("PR2MD"),
        )
        _fallback_version.cache_clear()
        version_value = get_version()
        assert version_value
        assert version_value != "unknown"

    def test_fallback_unknown_when_pyproject_missing(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test fallback returns unknown when pyproject.toml is absent."""
        missing = tmp_path / "missing.toml"
        mocker.patch("pr2md._version._pyproject_path", return_value=missing)
        _fallback_version.cache_clear()
        assert _fallback_version() == "unknown"

    def test_fallback_unknown_without_version_key(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test fallback returns unknown when pyproject has no version field."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'x'\n", encoding="utf-8")
        mocker.patch("pr2md._version._pyproject_path", return_value=pyproject)
        _fallback_version.cache_clear()
        assert _fallback_version() == "unknown"
