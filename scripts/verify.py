#!/usr/bin/env python3
"""Run local quality checks for PR2MD."""

from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description="Run PR2MD quality checks.")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply autopep8 and isort fixes before running checks",
    )
    args = parser.parse_args()

    python = sys.executable
    autopep8_args = [
        python,
        "-m",
        "autopep8",
        "--select=W291,W293",
        "-r",
        "src",
        "tests",
    ]
    if args.fix:
        autopep8_args.insert(3, "--in-place")
    else:
        autopep8_args.insert(3, "--diff")

    isort_args = [python, "-m", "isort", "src", "tests"]
    if not args.fix:
        isort_args.insert(3, "--check-only")

    steps: list[tuple[str, list[str]]] = [
        ("autopep8 (trailing whitespace)", autopep8_args),
        ("isort", isort_args),
        ("black", [python, "-m", "black", "--check", "src", "tests"]),
        ("mypy", [python, "-m", "mypy", "src/pr2md", "tests"]),
        ("pylint", [python, "-m", "pylint", "src/pr2md", "--output=pylint-report.txt"]),
        ("bandit", [python, "-m", "bandit", "-r", "src/pr2md", "-q"]),
        ("pytest", [python, "-m", "pytest"]),
    ]

    for name, step_args in steps:
        _run_step(name, step_args)

    print("All verification steps passed.")


if __name__ == "__main__":
    main()
