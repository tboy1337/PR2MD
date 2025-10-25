"""Tests for CLI."""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pytest_mock import MockerFixture

from pr2md.cli import (
    create_parser,
    extract_pr_data,
    main,
    parse_arguments,
    parse_pr_url,
    setup_logging,
    write_output,
)
from pr2md.pr_extractor import GitHubAPIError


class TestCLI:
    """Tests for CLI functions."""

    def test_parse_pr_url_valid_https(self) -> None:
        """Test parsing valid HTTPS URL."""
        owner, repo, pr_number = parse_pr_url("https://github.com/owner/repo/pull/123")
        assert owner == "owner"
        assert repo == "repo"
        assert pr_number == 123

    def test_parse_pr_url_valid_http(self) -> None:
        """Test parsing valid HTTP URL."""
        owner, repo, pr_number = parse_pr_url("http://github.com/owner/repo/pull/456")
        assert owner == "owner"
        assert repo == "repo"
        assert pr_number == 456

    def test_parse_pr_url_with_trailing_slash(self) -> None:
        """Test parsing URL with trailing content."""
        owner, repo, pr_number = parse_pr_url("https://github.com/owner/repo/pull/789")
        assert owner == "owner"
        assert repo == "repo"
        assert pr_number == 789

    def test_parse_pr_url_invalid_format(self) -> None:
        """Test parsing invalid URL format."""
        with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
            parse_pr_url("https://github.com/owner/repo/issues/123")

    def test_parse_pr_url_invalid_domain(self) -> None:
        """Test parsing URL with wrong domain."""
        with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
            parse_pr_url("https://gitlab.com/owner/repo/pull/123")

    def test_parse_pr_url_missing_number(self) -> None:
        """Test parsing URL without PR number."""
        with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
            parse_pr_url("https://github.com/owner/repo/pull/")

    def test_parse_pr_url_not_a_url(self) -> None:
        """Test parsing non-URL string."""
        with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
            parse_pr_url("not a url")


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_default(self, mocker: MockerFixture) -> None:
        """Test default logging setup."""
        mock_basic_config = mocker.patch("logging.basicConfig")
        setup_logging()
        mock_basic_config.assert_called_once()
        assert mock_basic_config.call_args[1]["level"] == logging.INFO

    def test_setup_logging_verbose(self, mocker: MockerFixture) -> None:
        """Test verbose logging setup."""
        mock_basic_config = mocker.patch("logging.basicConfig")
        setup_logging(verbose=True)
        mock_basic_config.assert_called_once()
        assert mock_basic_config.call_args[1]["level"] == logging.DEBUG


class TestCreateParser:
    """Tests for create_parser function."""

    def test_create_parser(self) -> None:
        """Test parser creation."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog is not None

    def test_parser_accepts_url(self) -> None:
        """Test parser accepts URL."""
        parser = create_parser()
        args = parser.parse_args(["https://github.com/owner/repo/pull/123"])
        assert args.pr_identifier == ["https://github.com/owner/repo/pull/123"]

    def test_parser_accepts_owner_repo_number(self) -> None:
        """Test parser accepts owner, repo, number format."""
        parser = create_parser()
        args = parser.parse_args(["owner", "repo", "123"])
        assert args.pr_identifier == ["owner", "repo", "123"]

    def test_parser_output_argument(self) -> None:
        """Test parser handles output argument."""
        parser = create_parser()
        args = parser.parse_args(
            ["https://github.com/owner/repo/pull/123", "-o", "output.md"]
        )
        assert args.output == "output.md"

    def test_parser_verbose_argument(self) -> None:
        """Test parser handles verbose argument."""
        parser = create_parser()
        args = parser.parse_args(
            ["https://github.com/owner/repo/pull/123", "--verbose"]
        )
        assert args.verbose is True


class TestParseArguments:
    """Tests for parse_arguments function."""

    def test_parse_arguments_url_format(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with URL format."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123"],
        )
        owner, repo, pr_number, output_path, verbose, depth, no_references = (
            parse_arguments(parser)
        )
        assert owner == "owner"
        assert repo == "repo"
        assert pr_number == 123
        assert output_path == "PR-123.md"
        assert verbose is False
        assert depth == 2  # default value
        assert no_references is False

    def test_parse_arguments_owner_repo_number(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with owner/repo/number format."""
        parser = create_parser()
        mocker.patch.object(sys, "argv", ["pr2md", "owner", "repo", "123"])
        owner, repo, pr_number, output_path, verbose, depth, no_references = (
            parse_arguments(parser)
        )
        assert owner == "owner"
        assert repo == "repo"
        assert pr_number == 123
        assert output_path == "PR-123.md"
        assert verbose is False
        assert depth == 2
        assert no_references is False

    def test_parse_arguments_with_output(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with output file."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123", "-o", "output.md"],
        )
        _owner, _repo, _pr_number, output_path, _verbose, _depth, _no_references = (
            parse_arguments(parser)
        )
        assert output_path == "output.md"

    def test_parse_arguments_with_verbose(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with verbose flag."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123", "--verbose"],
        )
        _owner, _repo, _pr_number, _output_path, verbose, _depth, _no_references = (
            parse_arguments(parser)
        )
        assert verbose is True

    def test_parse_arguments_invalid_count(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with invalid argument count."""
        parser = create_parser()
        mocker.patch.object(sys, "argv", ["pr2md", "arg1", "arg2"])
        with pytest.raises(SystemExit):
            parse_arguments(parser)

    def test_parse_arguments_invalid_url(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with invalid URL."""
        parser = create_parser()
        mocker.patch.object(sys, "argv", ["pr2md", "not-a-valid-url"])
        with pytest.raises(SystemExit):
            parse_arguments(parser)

    def test_parse_arguments_invalid_pr_number(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with invalid PR number."""
        parser = create_parser()
        mocker.patch.object(sys, "argv", ["pr2md", "owner", "repo", "not-a-number"])
        with pytest.raises(SystemExit):
            parse_arguments(parser)

    def test_parse_arguments_output_without_filename(
        self, mocker: MockerFixture
    ) -> None:
        """Test parsing arguments with -o flag but no filename (stdout)."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/456", "-o"],
        )
        _owner, _repo, _pr_number, output_path, _verbose, _depth, _no_references = (
            parse_arguments(parser)
        )
        assert output_path is None

    def test_parse_arguments_auto_generated_filename(
        self, mocker: MockerFixture
    ) -> None:
        """Test that auto-generated filename follows PR-{number}.md format."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "owner", "repo", "999"],
        )
        _owner, _repo, _pr_number, output_path, _verbose, _depth, _no_references = (
            parse_arguments(parser)
        )
        assert output_path == "PR-999.md"

    def test_parse_arguments_with_depth(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with depth flag."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123", "--depth", "5"],
        )
        _owner, _repo, _pr_number, _output_path, _verbose, depth, _no_references = (
            parse_arguments(parser)
        )
        assert depth == 5

    def test_parse_arguments_with_no_references(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with no-references flag."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123", "--no-references"],
        )
        _owner, _repo, _pr_number, _output_path, _verbose, _depth, no_references = (
            parse_arguments(parser)
        )
        assert no_references is True


class TestExtractPRData:
    """Tests for extract_pr_data function."""

    def test_extract_pr_data_success(self, mocker: MockerFixture) -> None:
        """Test successful PR data extraction."""
        mock_pr = MagicMock()
        mock_extractor = MagicMock()
        mock_extractor.extract_all.return_value = (
            mock_pr,
            [],
            [],
            [],
            "diff content",
        )
        mocker.patch("pr2md.cli.GitHubPRExtractor", return_value=mock_extractor)
        mocker.patch("pr2md.cli.MarkdownFormatter.format_pr", return_value="# Markdown")

        markdown, success, pull_request, comments, reviews, review_comments = (
            extract_pr_data("owner", "repo", 123, False)
        )
        assert success is True
        assert markdown == "# Markdown"
        assert pull_request is mock_pr
        assert comments == []
        assert reviews == []
        assert review_comments == []

    def test_extract_pr_data_api_error(self, mocker: MockerFixture) -> None:
        """Test PR data extraction with API error."""
        mock_extractor = MagicMock()
        mock_extractor.extract_all.side_effect = GitHubAPIError("API Error")
        mocker.patch("pr2md.cli.GitHubPRExtractor", return_value=mock_extractor)

        markdown, success, pull_request, comments, reviews, review_comments = (
            extract_pr_data("owner", "repo", 123, False)
        )
        assert success is False
        assert markdown == ""
        assert pull_request is None
        assert comments == []
        assert reviews == []
        assert review_comments == []

    def test_extract_pr_data_unexpected_error(self, mocker: MockerFixture) -> None:
        """Test PR data extraction with unexpected error."""
        mock_extractor = MagicMock()
        mock_extractor.extract_all.side_effect = Exception("Unexpected error")
        mocker.patch("pr2md.cli.GitHubPRExtractor", return_value=mock_extractor)

        markdown, success, pull_request, comments, reviews, review_comments = (
            extract_pr_data("owner", "repo", 123, False)
        )
        assert success is False
        assert markdown == ""
        assert pull_request is None
        assert comments == []
        assert reviews == []
        assert review_comments == []

    def test_extract_pr_data_unexpected_error_verbose(
        self, mocker: MockerFixture
    ) -> None:
        """Test PR data extraction with unexpected error in verbose mode."""
        mock_extractor = MagicMock()
        mock_extractor.extract_all.side_effect = Exception("Unexpected error")
        mocker.patch("pr2md.cli.GitHubPRExtractor", return_value=mock_extractor)

        markdown, success, pull_request, comments, reviews, review_comments = (
            extract_pr_data("owner", "repo", 123, True)
        )
        assert success is False
        assert markdown == ""
        assert pull_request is None
        assert comments == []
        assert reviews == []
        assert review_comments == []

    def test_extract_pr_data_format_error(self, mocker: MockerFixture) -> None:
        """Test PR data extraction with formatting error."""
        mock_pr = MagicMock()
        mock_extractor = MagicMock()
        mock_extractor.extract_all.return_value = (
            mock_pr,
            [],
            [],
            [],
            "diff content",
        )
        mocker.patch("pr2md.cli.GitHubPRExtractor", return_value=mock_extractor)
        mocker.patch(
            "pr2md.cli.MarkdownFormatter.format_pr",
            side_effect=Exception("Format error"),
        )

        markdown, success, pull_request, comments, reviews, review_comments = (
            extract_pr_data("owner", "repo", 123, False)
        )
        assert success is False
        assert markdown == ""
        assert pull_request is None
        assert comments == []
        assert reviews == []
        assert review_comments == []

    def test_extract_pr_data_format_error_verbose(self, mocker: MockerFixture) -> None:
        """Test PR data extraction with formatting error in verbose mode."""
        mock_pr = MagicMock()
        mock_extractor = MagicMock()
        mock_extractor.extract_all.return_value = (
            mock_pr,
            [],
            [],
            [],
            "diff content",
        )
        mocker.patch("pr2md.cli.GitHubPRExtractor", return_value=mock_extractor)
        mocker.patch(
            "pr2md.cli.MarkdownFormatter.format_pr",
            side_effect=Exception("Format error"),
        )

        markdown, success, pull_request, comments, reviews, review_comments = (
            extract_pr_data("owner", "repo", 123, True)
        )
        assert success is False
        assert markdown == ""
        assert pull_request is None
        assert comments == []
        assert reviews == []
        assert review_comments == []


class TestWriteOutput:
    """Tests for write_output function."""

    def test_write_output_to_file(self, tmp_path: Path) -> None:
        """Test writing output to file."""
        output_file = tmp_path / "output.md"
        markdown = "# Test Markdown"

        success = write_output(markdown, str(output_file), False)
        assert success is True
        assert output_file.read_text(encoding="utf-8") == markdown

    def test_write_output_to_stdout(self, mocker: MockerFixture) -> None:
        """Test writing output to stdout."""
        markdown = "# Test Markdown"
        mock_print = mocker.patch("builtins.print")

        success = write_output(markdown, None, False)
        assert success is True
        mock_print.assert_called_once_with(markdown)

    def test_write_output_file_error(self, mocker: MockerFixture) -> None:
        """Test writing output with file error."""
        markdown = "# Test Markdown"
        mocker.patch("pathlib.Path.write_text", side_effect=Exception("Write error"))

        success = write_output(markdown, "/invalid/path/output.md", False)
        assert success is False

    def test_write_output_file_error_verbose(self, mocker: MockerFixture) -> None:
        """Test writing output with file error in verbose mode."""
        markdown = "# Test Markdown"
        mocker.patch("pathlib.Path.write_text", side_effect=Exception("Write error"))

        success = write_output(markdown, "/invalid/path/output.md", True)
        assert success is False


class TestMain:
    """Tests for main function."""

    def test_main_success(self, mocker: MockerFixture) -> None:
        """Test successful main execution."""
        mocker.patch.object(
            sys, "argv", ["pr2md", "https://github.com/owner/repo/pull/123"]
        )
        mock_pr = MagicMock()
        mock_pr.body = "Test PR body"
        mocker.patch(
            "pr2md.cli.extract_pr_data",
            return_value=("# Markdown", True, mock_pr, [], [], []),
        )
        mocker.patch("pr2md.cli.write_output", return_value=True)

        # Should not raise SystemExit
        main()

    def test_main_extract_failure(self, mocker: MockerFixture) -> None:
        """Test main execution with extraction failure."""
        mocker.patch.object(
            sys, "argv", ["pr2md", "https://github.com/owner/repo/pull/123"]
        )
        mocker.patch(
            "pr2md.cli.extract_pr_data", return_value=("", False, None, [], [], [])
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_write_failure(self, mocker: MockerFixture) -> None:
        """Test main execution with write failure."""
        mocker.patch.object(
            sys, "argv", ["pr2md", "https://github.com/owner/repo/pull/123"]
        )
        mock_pr = MagicMock()
        mocker.patch(
            "pr2md.cli.extract_pr_data",
            return_value=("# Markdown", True, mock_pr, [], [], []),
        )
        mocker.patch("pr2md.cli.write_output", return_value=False)

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


class TestCLIHypothesis:
    """Hypothesis tests for CLI functions."""

    @given(
        owner=st.from_regex(r"[\w-]{1,39}", fullmatch=True),
        repo=st.from_regex(r"[\w.-]{1,100}", fullmatch=True),
        pr_number=st.integers(min_value=1, max_value=100000),
        protocol=st.sampled_from(["http", "https"]),
    )
    @settings(max_examples=100, deadline=2000)
    def test_parse_pr_url_valid_urls(
        self, owner: str, repo: str, pr_number: int, protocol: str
    ) -> None:
        """Test parsing various valid GitHub PR URLs."""
        url = f"{protocol}://github.com/{owner}/{repo}/pull/{pr_number}"
        parsed_owner, parsed_repo, parsed_pr_number = parse_pr_url(url)
        assert parsed_owner == owner
        assert parsed_repo == repo
        assert parsed_pr_number == pr_number

    @given(
        url=st.one_of(
            # Not GitHub domain
            st.from_regex(
                r"https?://[a-z]+\.com/[\w-]+/[\w.-]+/pull/\d+", fullmatch=True
            ).filter(lambda x: "github.com" not in x),
            # Wrong path structure
            st.from_regex(
                r"https?://github\.com/[\w-]+/[\w.-]+/issues/\d+", fullmatch=True
            ),
            # Missing PR number
            st.just("https://github.com/owner/repo/pull/"),
            # Just random text
            st.text(min_size=1, max_size=100).filter(
                lambda x: not x.startswith("http")
            ),
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_parse_pr_url_invalid_urls(self, url: str) -> None:
        """Test that invalid URLs raise ValueError."""
        with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
            parse_pr_url(url)

    @given(
        markdown=st.text(min_size=10, max_size=5000),
    )
    @settings(
        max_examples=30,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_write_output_stdout_property(
        self, markdown: str, mocker: MockerFixture
    ) -> None:
        """Test writing output to stdout with various markdown content."""
        mock_print = mocker.patch("builtins.print")
        success = write_output(markdown, None, False)
        assert success is True
        mock_print.assert_called_once_with(markdown)

    @given(
        markdown=st.text(min_size=10, max_size=5000).filter(
            lambda x: "\r\n" not in x and "\r" not in x
        ),
        filename=st.from_regex(r"[\w-]{1,50}\.md", fullmatch=True),
    )
    @settings(
        max_examples=20,
        deadline=3000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_write_output_file_property(
        self, markdown: str, filename: str, tmp_path: Path
    ) -> None:
        """Test writing output to file with various markdown content."""
        output_file = tmp_path / filename
        success = write_output(markdown, str(output_file), False)
        assert success is True
        assert output_file.exists()
        assert output_file.read_text(encoding="utf-8") == markdown

    @given(
        owner=st.from_regex(r"[\w-]{1,39}", fullmatch=True),
        repo=st.from_regex(r"[\w.-]{1,100}", fullmatch=True),
        pr_number=st.integers(min_value=1, max_value=100000),
    )
    @settings(max_examples=30, deadline=2000)
    def test_parse_pr_url_consistency(
        self, owner: str, repo: str, pr_number: int
    ) -> None:
        """Test that parsing is consistent for the same URL."""
        url = f"https://github.com/{owner}/{repo}/pull/{pr_number}"
        result1 = parse_pr_url(url)
        result2 = parse_pr_url(url)
        assert result1 == result2

    @given(
        owner=st.from_regex(r"[\w-]{1,39}", fullmatch=True),
        repo=st.from_regex(r"[\w.-]{1,100}", fullmatch=True),
        pr_number=st.integers(min_value=1, max_value=100000),
    )
    @settings(max_examples=30, deadline=2000)
    def test_parse_pr_url_types(self, owner: str, repo: str, pr_number: int) -> None:
        """Test that parsed values have correct types."""
        url = f"https://github.com/{owner}/{repo}/pull/{pr_number}"
        parsed_owner, parsed_repo, parsed_pr_number = parse_pr_url(url)
        assert isinstance(parsed_owner, str)
        assert isinstance(parsed_repo, str)
        assert isinstance(parsed_pr_number, int)
