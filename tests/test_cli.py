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
    download_references_if_needed,
    extract_issue_data,
    extract_pr_data,
    main,
    parse_arguments,
    parse_pr_url,
    setup_logging,
    write_output,
)
from pr2md.exceptions import GitHubAPIError


def _mock_extractor_context(mock_extractor: MagicMock) -> MagicMock:
    """Configure a mock extractor for use as a context manager."""
    mock_extractor.__enter__.return_value = mock_extractor
    mock_extractor.__exit__.return_value = False
    return mock_extractor


class TestCLI:
    """Tests for CLI functions."""

    def test_parse_pr_url_valid_https(self) -> None:
        """Test parsing valid HTTPS PR URL."""
        owner, repo, ref_type, number = parse_pr_url(
            "https://github.com/owner/repo/pull/123"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "pr"
        assert number == 123

    def test_parse_pr_url_valid_http(self) -> None:
        """Test parsing valid HTTP PR URL."""
        owner, repo, ref_type, number = parse_pr_url(
            "http://github.com/owner/repo/pull/456"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "pr"
        assert number == 456

    def test_parse_pr_url_with_trailing_slash(self) -> None:
        """Test parsing PR URL with trailing content."""
        owner, repo, ref_type, number = parse_pr_url(
            "https://github.com/owner/repo/pull/789"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "pr"
        assert number == 789

    def test_parse_issue_url_valid_https(self) -> None:
        """Test parsing valid HTTPS Issue URL."""
        owner, repo, ref_type, number = parse_pr_url(
            "https://github.com/owner/repo/issues/123"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "issue"
        assert number == 123

    def test_parse_issue_url_valid_http(self) -> None:
        """Test parsing valid HTTP Issue URL."""
        owner, repo, ref_type, number = parse_pr_url(
            "http://github.com/owner/repo/issues/456"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "issue"
        assert number == 456

    def test_parse_pr_url_invalid_format(self) -> None:
        """Test parsing invalid URL format."""
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_pr_url("https://github.com/owner/repo/commits/123")

    def test_parse_pr_url_invalid_domain(self) -> None:
        """Test parsing URL with wrong domain."""
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_pr_url("https://gitlab.com/owner/repo/pull/123")

    def test_parse_pr_url_missing_number(self) -> None:
        """Test parsing URL without PR number."""
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_pr_url("https://github.com/owner/repo/pull/")

    def test_parse_pr_url_not_a_url(self) -> None:
        """Test parsing non-URL string."""
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
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

    def test_parser_accepts_owner_repo_type_number(self) -> None:
        """Test parser accepts owner, repo, type, number format."""
        parser = create_parser()
        args = parser.parse_args(["owner", "repo", "pr", "123"])
        assert args.pr_identifier == ["owner", "repo", "pr", "123"]

    def test_parser_accepts_owner_repo_issue_number(self) -> None:
        """Test parser accepts owner, repo, issue, number format."""
        parser = create_parser()
        args = parser.parse_args(["owner", "repo", "issue", "456"])
        assert args.pr_identifier == ["owner", "repo", "issue", "456"]

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

    def test_parse_arguments_pr_url_format(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with PR URL format."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123"],
        )
        owner, repo, ref_type, number, output_path, verbose, depth, no_references = (
            parse_arguments(parser)
        )
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "pr"
        assert number == 123
        assert output_path == "PR-123.md"
        assert verbose is False
        assert depth == 2  # default value
        assert no_references is False

    def test_parse_arguments_issue_url_format(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with Issue URL format."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/issues/456"],
        )
        owner, repo, ref_type, number, output_path, verbose, depth, no_references = (
            parse_arguments(parser)
        )
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "issue"
        assert number == 456
        assert output_path == "Issue-456.md"
        assert verbose is False
        assert depth == 2
        assert no_references is False

    def test_parse_arguments_owner_repo_pr_number(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with owner/repo/pr/number format."""
        parser = create_parser()
        mocker.patch.object(sys, "argv", ["pr2md", "owner", "repo", "pr", "123"])
        owner, repo, ref_type, number, output_path, verbose, depth, no_references = (
            parse_arguments(parser)
        )
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "pr"
        assert number == 123
        assert output_path == "PR-123.md"
        assert verbose is False
        assert depth == 2
        assert no_references is False

    def test_parse_arguments_owner_repo_issue_number(
        self, mocker: MockerFixture
    ) -> None:
        """Test parsing arguments with owner/repo/issue/number format."""
        parser = create_parser()
        mocker.patch.object(sys, "argv", ["pr2md", "owner", "repo", "issue", "789"])
        owner, repo, ref_type, number, output_path, verbose, depth, no_references = (
            parse_arguments(parser)
        )
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "issue"
        assert number == 789
        assert output_path == "Issue-789.md"
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
        (
            _owner,
            _repo,
            _ref_type,
            _number,
            output_path,
            _verbose,
            _depth,
            _no_references,
        ) = parse_arguments(parser)
        assert Path(output_path).name == "output.md"

    def test_parse_arguments_with_verbose(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with verbose flag."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123", "--verbose"],
        )
        (
            _owner,
            _repo,
            _ref_type,
            _number,
            _output_path,
            verbose,
            _depth,
            _no_references,
        ) = parse_arguments(parser)
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

    def test_parse_arguments_invalid_type(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with invalid type."""
        parser = create_parser()
        mocker.patch.object(sys, "argv", ["pr2md", "owner", "repo", "invalid", "123"])
        with pytest.raises(SystemExit):
            parse_arguments(parser)

    def test_parse_arguments_invalid_pr_number(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with invalid number."""
        parser = create_parser()
        mocker.patch.object(
            sys, "argv", ["pr2md", "owner", "repo", "pr", "not-a-number"]
        )
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
        (
            _owner,
            _repo,
            _ref_type,
            _number,
            output_path,
            _verbose,
            _depth,
            _no_references,
        ) = parse_arguments(parser)
        assert output_path is None

    def test_parse_arguments_auto_generated_pr_filename(
        self, mocker: MockerFixture
    ) -> None:
        """Test that auto-generated filename follows PR-{number}.md format."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "owner", "repo", "pr", "999"],
        )
        (
            _owner,
            _repo,
            _ref_type,
            _number,
            output_path,
            _verbose,
            _depth,
            _no_references,
        ) = parse_arguments(parser)
        assert output_path == "PR-999.md"

    def test_parse_arguments_auto_generated_issue_filename(
        self, mocker: MockerFixture
    ) -> None:
        """Test that auto-generated filename follows Issue-{number}.md format."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "owner", "repo", "issue", "888"],
        )
        (
            _owner,
            _repo,
            _ref_type,
            _number,
            output_path,
            _verbose,
            _depth,
            _no_references,
        ) = parse_arguments(parser)
        assert output_path == "Issue-888.md"

    def test_parse_arguments_with_depth(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with depth flag."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123", "--depth", "5"],
        )
        (
            _owner,
            _repo,
            _ref_type,
            _number,
            _output_path,
            _verbose,
            depth,
            _no_references,
        ) = parse_arguments(parser)
        assert depth == 5

    def test_parse_arguments_with_no_references(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with no-references flag."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123", "--no-references"],
        )
        (
            _owner,
            _repo,
            _ref_type,
            _number,
            _output_path,
            _verbose,
            _depth,
            no_references,
        ) = parse_arguments(parser)
        assert no_references is True


    def test_parse_arguments_invalid_depth(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with invalid depth."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "owner", "repo", "pr", "123", "--depth", "-1"],
        )
        with pytest.raises(SystemExit):
            parse_arguments(parser)

    def test_parse_arguments_invalid_owner(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with invalid owner characters."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "bad owner", "repo", "pr", "123"],
        )
        with pytest.raises(SystemExit):
            parse_arguments(parser)

    def test_parse_arguments_output_outside_cwd(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test parsing arguments with output path outside CWD."""
        parser = create_parser()
        outside = tmp_path / "outside.md"
        mocker.patch.object(
            sys,
            "argv",
            [
                "pr2md",
                "owner",
                "repo",
                "pr",
                "123",
                "-o",
                str(outside),
            ],
        )
        with pytest.raises(SystemExit):
            parse_arguments(parser)


class TestDownloadReferencesIfNeeded:
    """Tests for reference download orchestration."""

    def test_download_references_when_auto_naming(self, mocker: MockerFixture) -> None:
        """Test reference download is triggered for auto-named output."""
        mock_downloader = mocker.patch("pr2md.cli.ReferenceDownloader")
        instance = mock_downloader.return_value.__enter__.return_value
        instance.extract_references_from_pr.return_value = set()
        mock_pr = MagicMock()

        download_references_if_needed(
            "owner",
            "repo",
            "pr",
            123,
            "PR-123.md",
            2,
            False,
            False,
            mock_pr,
            None,
            [],
            [],
            [],
        )

        instance.extract_references_from_pr.assert_called_once()

    def test_skips_when_no_references_flag(self, mocker: MockerFixture) -> None:
        """Test reference download is skipped with --no-references."""
        mock_downloader = mocker.patch("pr2md.cli.ReferenceDownloader")
        mock_pr = MagicMock()

        download_references_if_needed(
            "owner",
            "repo",
            "pr",
            123,
            "PR-123.md",
            2,
            True,
            False,
            mock_pr,
            None,
            [],
            [],
            [],
        )

        mock_downloader.assert_not_called()


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
        _mock_extractor_context(mock_extractor)
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
        _mock_extractor_context(mock_extractor)
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
        mock_extractor.extract_all.side_effect = ValueError("Unexpected error")
        _mock_extractor_context(mock_extractor)
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
        mock_extractor.extract_all.side_effect = ValueError("Unexpected error")
        _mock_extractor_context(mock_extractor)
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
        _mock_extractor_context(mock_extractor)
        mocker.patch("pr2md.cli.GitHubPRExtractor", return_value=mock_extractor)
        mocker.patch(
            "pr2md.cli.MarkdownFormatter.format_pr",
            side_effect=TypeError("Format error"),
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
        _mock_extractor_context(mock_extractor)
        mocker.patch("pr2md.cli.GitHubPRExtractor", return_value=mock_extractor)
        mocker.patch(
            "pr2md.cli.MarkdownFormatter.format_pr",
            side_effect=TypeError("Format error"),
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


class TestExtractIssueData:
    """Tests for extract_issue_data function."""

    def test_extract_issue_data_success(self, mocker: MockerFixture) -> None:
        """Test successful Issue data extraction."""
        mock_issue = MagicMock()
        mock_extractor = MagicMock()
        mock_extractor.extract_all.return_value = (mock_issue, [])
        _mock_extractor_context(mock_extractor)
        mocker.patch("pr2md.cli.GitHubIssueExtractor", return_value=mock_extractor)
        mocker.patch(
            "pr2md.cli.MarkdownFormatter.format_issue", return_value="# Issue Markdown"
        )

        markdown, success, issue, comments = extract_issue_data(
            "owner", "repo", 456, False
        )
        assert success is True
        assert markdown == "# Issue Markdown"
        assert issue is mock_issue
        assert comments == []

    def test_extract_issue_data_api_error(self, mocker: MockerFixture) -> None:
        """Test Issue data extraction with API error."""
        mock_extractor = MagicMock()
        mock_extractor.extract_all.side_effect = GitHubAPIError("API Error")
        _mock_extractor_context(mock_extractor)
        mocker.patch("pr2md.cli.GitHubIssueExtractor", return_value=mock_extractor)

        markdown, success, issue, comments = extract_issue_data(
            "owner", "repo", 456, False
        )
        assert success is False
        assert markdown == ""
        assert issue is None
        assert comments == []

    def test_extract_issue_data_unexpected_error(self, mocker: MockerFixture) -> None:
        """Test Issue data extraction with unexpected error."""
        mock_extractor = MagicMock()
        mock_extractor.extract_all.side_effect = ValueError("Unexpected error")
        _mock_extractor_context(mock_extractor)
        mocker.patch("pr2md.cli.GitHubIssueExtractor", return_value=mock_extractor)

        markdown, success, issue, comments = extract_issue_data(
            "owner", "repo", 456, False
        )
        assert success is False
        assert markdown == ""
        assert issue is None
        assert comments == []

    def test_extract_issue_data_format_error(self, mocker: MockerFixture) -> None:
        """Test Issue data extraction with formatting error."""
        mock_issue = MagicMock()
        mock_extractor = MagicMock()
        mock_extractor.extract_all.return_value = (mock_issue, [])
        _mock_extractor_context(mock_extractor)
        mocker.patch("pr2md.cli.GitHubIssueExtractor", return_value=mock_extractor)
        mocker.patch(
            "pr2md.cli.MarkdownFormatter.format_issue",
            side_effect=TypeError("Format error"),
        )

        markdown, success, issue, comments = extract_issue_data(
            "owner", "repo", 456, False
        )
        assert success is False
        assert markdown == ""
        assert issue is None
        assert comments == []


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
        mocker.patch("pr2md.cli.write_text_atomic", side_effect=OSError("Write error"))

        success = write_output(markdown, "/invalid/path/output.md", False)
        assert success is False

    def test_write_output_file_error_verbose(self, mocker: MockerFixture) -> None:
        """Test writing output with file error in verbose mode."""
        markdown = "# Test Markdown"
        mocker.patch("pr2md.cli.write_text_atomic", side_effect=OSError("Write error"))

        success = write_output(markdown, "/invalid/path/output.md", True)
        assert success is False


class TestMain:
    """Tests for main function."""

    def test_main_pr_success(self, mocker: MockerFixture) -> None:
        """Test successful main execution for PR."""
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

    def test_main_issue_success(self, mocker: MockerFixture) -> None:
        """Test successful main execution for Issue."""
        mocker.patch.object(
            sys, "argv", ["pr2md", "https://github.com/owner/repo/issues/456"]
        )
        mock_issue = MagicMock()
        mock_issue.body = "Test Issue body"
        mocker.patch(
            "pr2md.cli.extract_issue_data",
            return_value=("# Issue Markdown", True, mock_issue, []),
        )
        mocker.patch("pr2md.cli.write_output", return_value=True)

        # Should not raise SystemExit
        main()

    def test_main_pr_extract_failure(self, mocker: MockerFixture) -> None:
        """Test main execution with PR extraction failure."""
        mocker.patch.object(
            sys, "argv", ["pr2md", "https://github.com/owner/repo/pull/123"]
        )
        mocker.patch(
            "pr2md.cli.extract_pr_data", return_value=("", False, None, [], [], [])
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_issue_extract_failure(self, mocker: MockerFixture) -> None:
        """Test main execution with Issue extraction failure."""
        mocker.patch.object(
            sys, "argv", ["pr2md", "https://github.com/owner/repo/issues/456"]
        )
        mocker.patch("pr2md.cli.extract_issue_data", return_value=("", False, None, []))

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
    def test_parse_pr_url_valid_pr_urls(
        self, owner: str, repo: str, pr_number: int, protocol: str
    ) -> None:
        """Test parsing various valid GitHub PR URLs."""
        url = f"{protocol}://github.com/{owner}/{repo}/pull/{pr_number}"
        parsed_owner, parsed_repo, ref_type, parsed_number = parse_pr_url(url)
        assert parsed_owner == owner
        assert parsed_repo == repo
        assert ref_type == "pr"
        assert parsed_number == pr_number

    @given(
        owner=st.from_regex(r"[\w-]{1,39}", fullmatch=True),
        repo=st.from_regex(r"[\w.-]{1,100}", fullmatch=True),
        issue_number=st.integers(min_value=1, max_value=100000),
        protocol=st.sampled_from(["http", "https"]),
    )
    @settings(max_examples=100, deadline=2000)
    def test_parse_pr_url_valid_issue_urls(
        self, owner: str, repo: str, issue_number: int, protocol: str
    ) -> None:
        """Test parsing various valid GitHub Issue URLs."""
        url = f"{protocol}://github.com/{owner}/{repo}/issues/{issue_number}"
        parsed_owner, parsed_repo, ref_type, parsed_number = parse_pr_url(url)
        assert parsed_owner == owner
        assert parsed_repo == repo
        assert ref_type == "issue"
        assert parsed_number == issue_number

    @given(
        url=st.one_of(
            # Not GitHub domain
            st.from_regex(
                r"https?://[a-z]+\.com/[\w-]+/[\w.-]+/pull/\d+", fullmatch=True
            ).filter(lambda x: "github.com" not in x),
            # Wrong path structure (commits instead of pull/issues)
            st.from_regex(
                r"https?://github\.com/[\w-]+/[\w.-]+/commits/\d+", fullmatch=True
            ),
            # Missing number
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
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
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
        parsed_owner, parsed_repo, ref_type, parsed_number = parse_pr_url(url)
        assert isinstance(parsed_owner, str)
        assert isinstance(parsed_repo, str)
        assert isinstance(ref_type, str)
        assert isinstance(parsed_number, int)
