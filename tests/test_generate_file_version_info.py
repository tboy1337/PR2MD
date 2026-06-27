"""Tests for Windows version resource generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.generate_file_version_info import (
    _build_version_info,
    _read_project_version,
    _version_tuple,
)


class TestGenerateFileVersionInfo:
    """Tests for generate_file_version_info helpers."""

    def test_version_tuple_pads_short_versions(self) -> None:
        """Test semantic versions with fewer than three parts are padded."""
        assert _version_tuple("1") == (1, 0, 0)
        assert _version_tuple("1.2") == (1, 2, 0)
        assert _version_tuple("1.2.3") == (1, 2, 3)

    def test_build_version_info_includes_version_strings(self) -> None:
        """Test generated VSVersionInfo contains product and file version."""
        content = _build_version_info("1.0.25")
        assert "filevers=(1, 0, 25, 0)" in content
        assert "StringStruct(u'FileVersion', u'1.0.25')" in content
        assert "StringStruct(u'ProductVersion', u'1.0.25')" in content
        assert "StringStruct(u'ProductName', u'PR2MD')" in content

    def test_read_project_version_from_pyproject(self, tmp_path: Path) -> None:
        """Test version is read from a pyproject.toml [project] table."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nversion = "2.3.4"\n', encoding="utf-8")
        assert _read_project_version(pyproject) == "2.3.4"

    def test_read_project_version_missing_table(self, tmp_path: Path) -> None:
        """Test missing [project] table raises ValueError."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("name = \"orphan\"\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Missing \\[project\\]"):
            _read_project_version(pyproject)

    def test_read_project_version_missing_version(self, tmp_path: Path) -> None:
        """Test missing project.version raises ValueError."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "PR2MD"\n', encoding="utf-8")
        with pytest.raises(ValueError, match="Missing project.version"):
            _read_project_version(pyproject)
