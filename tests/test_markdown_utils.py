"""Tests for markdown formatting utilities."""

from pr2md.markdown_utils import fenced_code_block


class TestFencedCodeBlock:
    """Tests for fenced_code_block."""

    def test_empty_content(self) -> None:
        """Test empty content uses a three-backtick fence."""
        result = fenced_code_block("")
        assert result == "```\n\n```"

    def test_with_language(self) -> None:
        """Test language tag is placed after opening fence."""
        result = fenced_code_block("print('hi')", "python")
        assert result.startswith("```python\n")
        assert "print('hi')" in result
        assert result.endswith("```")

    def test_content_with_long_backtick_run(self) -> None:
        """Test fence length exceeds backtick runs inside content."""
        content = "outer `` inner ```` code"
        result = fenced_code_block(content)
        assert result.startswith("`````\n")
        assert content in result
        assert result.endswith("`````")
