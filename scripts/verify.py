#!/usr/bin/env python3
"""Run local quality checks for PR2MD."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run_step(name: str, args: list[str]) -> None:
    print(f"==> {name}")
    result = subprocess.run(args, cwd=_repo_root(), check=False)
    if result.returncode != 0:
        raise SystemExit(f"Step failed: {name} (exit code {result.returncode})")


def main() -> None:
    """Execute formatting, linting, security, and test checks."""
    python = sys.executable
    steps: list[tuple[str, list[str]]] = [
        (
            "autopep8 (trailing whitespace)",
            [
                python,
                "-m",
                "autopep8",
                "--in-place",
                "--select=W291,W293",
                "-r",
                "src",
                "tests",
            ],
        ),
        ("isort", [python, "-m", "isort", "src", "tests"]),
        ("black", [python, "-m", "black", "--check", "src", "tests"]),
        ("mypy", [python, "-m", "mypy", "src/pr2md", "tests"]),
        ("pylint", [python, "-m", "pylint", "src/pr2md", "--output=pylint-report.txt"]),
        ("bandit", [python, "-m", "bandit", "-r", "src/pr2md", "-q"]),
        ("pytest", [python, "-m", "pytest"]),
    ]

    for name, args in steps:
        _run_step(name, args)

    print("All verification steps passed.")


if __name__ == "__main__":
    main()
