"""Tests for pr2md package initialization."""

from importlib.metadata import PackageNotFoundError

import pytest
from pytest_mock import MockerFixture


class TestPackageInit:
    """Tests for pr2md.__init__ exports and version."""

    def test_version_from_metadata(self) -> None:
        """Test __version__ is resolved from installed package metadata."""
        import pr2md

        assert pr2md.__version__
        assert isinstance(pr2md.__version__, str)

    def test_version_fallback_when_metadata_missing(
        self, mocker: MockerFixture
    ) -> None:
        """Test __version__ fallback when package is not installed."""
        import importlib

        import pr2md

        mocker.patch(
            "importlib.metadata.version",
            side_effect=PackageNotFoundError("PR2MD"),
        )
        importlib.reload(pr2md)
        assert pr2md.__version__ == "1.0.16"
        importlib.reload(pr2md)
