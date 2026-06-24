"""Markdown formatting utilities."""

import re


def fenced_code_block(content: str, lang: str = "") -> str:
    """Wrap content in a fence longer than any run of backticks inside content."""
    max_run = max(
        (len(match.group()) for match in re.finditer(r"`+", content)), default=0
    )
    fence = "`" * max(3, max_run + 1)
    return f"{fence}{lang}\n{content}\n{fence}"
