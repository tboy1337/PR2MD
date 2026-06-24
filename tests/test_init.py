"""Tests for pr2md package initialization."""

import importlib
import re
import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest
from pytest_mock import MockerFixture


def _pyproject_version() -> str:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        return str(tomllib.load(pyproject_file)["project"]["version"])


def _init_fallback_version() -> str:
    init_path = Path(__file__).resolve().parent.parent / "src" / "pr2md" / "__init__.py"
    init_text = init_path.read_text(encoding="utf-8")
    match = re.search(
        r'except PackageNotFoundError:\s+__version__ = "([^"]+)"',
        init_text,
    )
    assert match is not None, "Could not find __version__ fallback in __init__.py"
    return str(match.group(1))


class TestPackageInit:
    """Tests for pr2md.__init__ exports and version."""

    def test_version_from_metadata(self) -> None:
        """Test __version__ is resolved from installed package metadata."""
        import pr2md

        assert pr2md.__version__
        assert isinstance(pr2md.__version__, str)

    def test_fallback_version_matches_pyproject(self) -> None:
        """Test hardcoded __version__ fallback matches pyproject.toml."""
        assert _init_fallback_version() == _pyproject_version()

    def test_version_fallback_when_metadata_missing(
        self, mocker: MockerFixture
    ) -> None:
        """Test __version__ fallback when package is not installed."""
        import pr2md

        expected_version = _pyproject_version()

        mocker.patch(
            "importlib.metadata.version",
            side_effect=PackageNotFoundError("PR2MD"),
        )
        importlib.reload(pr2md)
        assert pr2md.__version__ == expected_version
        importlib.reload(pr2md)
