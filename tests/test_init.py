"""Tests for pr2md package initialization."""

import importlib
import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest
from pytest_mock import MockerFixture


def _pyproject_version() -> str:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        return str(tomllib.load(pyproject_file)["project"]["version"])


class TestPackageInit:
    """Tests for pr2md.__init__ exports and version."""

    def test_version_from_metadata(self) -> None:
        """Test __version__ is resolved from pyproject.toml or package metadata."""
        import pr2md

        assert pr2md.__version__
        assert isinstance(pr2md.__version__, str)

    def test_fallback_version_matches_pyproject(self, mocker: MockerFixture) -> None:
        """Test get_version fallback matches pyproject.toml when uninstalled."""
        from pr2md._version import _fallback_version, get_version

        expected_version = _pyproject_version()
        mocker.patch(
            "pr2md._version.version",
            side_effect=PackageNotFoundError("PR2MD"),
        )
        _fallback_version.cache_clear()
        assert get_version() == expected_version

    def test_version_fallback_when_metadata_missing(
        self, mocker: MockerFixture
    ) -> None:
        """Test __version__ fallback when package is not installed."""
        import pr2md

        expected_version = _pyproject_version()

        mocker.patch(
            "pr2md._version.version",
            side_effect=PackageNotFoundError("PR2MD"),
        )
        from pr2md._version import _fallback_version

        _fallback_version.cache_clear()
        importlib.reload(pr2md)
        assert pr2md.__version__ == expected_version
        importlib.reload(pr2md)
