"""Package version resolution."""

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

_PACKAGE_NAME = "PR2MD"


def _pyproject_path() -> Path:
    """Return the repository pyproject.toml path."""
    return Path(__file__).resolve().parent.parent.parent / "pyproject.toml"


@lru_cache(maxsize=1)
def _fallback_version() -> str:
    """Read version from pyproject.toml when the package is not installed."""
    pyproject = _pyproject_path()
    if not pyproject.is_file():
        return "unknown"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version = "):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return "unknown"


def get_version() -> str:
    """Return the installed package version, falling back to pyproject.toml."""
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return _fallback_version()
