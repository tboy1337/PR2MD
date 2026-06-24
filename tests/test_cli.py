"""Tests for CLI."""

import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pytest_mock import MockerFixture

from pr2md.cli import (
    _resolve_primary_ref_type,
    _run_primary_extraction,
    append_reference_summary,
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
from pr2md.reference_parser import GitHubReference
from pr2md.validation import validate_output_path

# pylint: disable=too-many-lines


def _resolved_output_path(name: str) -> str:
    """Return validated absolute output path for auto-generated filenames."""
    return validate_output_path(name)


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

    def test_parse_pr_url_rejects_http(self) -> None:
        """Test parsing rejects non-HTTPS PR URL."""
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_pr_url("http://github.com/owner/repo/pull/456")

    def test_parse_pr_url_with_trailing_slash(self) -> None:
        """Test parsing PR URL with trailing slash."""
        owner, repo, ref_type, number = parse_pr_url(
            "https://github.com/owner/repo/pull/789/"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "pr"
        assert number == 789

    def test_parse_pr_url_invalid_owner_in_url(self) -> None:
        """Test parsing URL with invalid owner name."""
        with pytest.raises(ValueError, match="Invalid owner"):
            parse_pr_url("https://github.com/bad!owner/repo/pull/1")

    def test_parse_issue_url_valid_https(self) -> None:
        """Test parsing valid HTTPS Issue URL."""
        owner, repo, ref_type, number = parse_pr_url(
            "https://github.com/owner/repo/issues/123"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "issue"
        assert number == 123

    def test_parse_issue_url_rejects_http(self) -> None:
        """Test parsing rejects non-HTTPS Issue URL."""
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_pr_url("http://github.com/owner/repo/issues/456")

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
        """Test default logging setup when no handlers exist."""
        mocker.patch("logging.root.handlers", [])
        mock_basic_config = mocker.patch("logging.basicConfig")
        setup_logging()
        mock_basic_config.assert_called_once()
        assert mock_basic_config.call_args[1]["level"] == logging.INFO

    def test_setup_logging_verbose(self, mocker: MockerFixture) -> None:
        """Test verbose logging setup when no handlers exist."""
        mocker.patch("logging.root.handlers", [])
        mock_basic_config = mocker.patch("logging.basicConfig")
        setup_logging(verbose=True)
        mock_basic_config.assert_called_once()
        assert mock_basic_config.call_args[1]["level"] == logging.DEBUG

    def test_setup_logging_verbose_preserves_existing_handlers(
        self, mocker: MockerFixture
    ) -> None:
        """Test verbose mode adjusts level without reconfiguring existing handlers."""
        mocker.patch("logging.root.handlers", [mocker.Mock()])
        mock_basic_config = mocker.patch("logging.basicConfig")
        mock_set_level = mocker.patch("logging.root.setLevel")
        setup_logging(verbose=True)
        mock_basic_config.assert_not_called()
        mock_set_level.assert_called_once_with(logging.DEBUG)


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
        (
            owner,
            repo,
            ref_type,
            number,
            output_path,
            auto_output,
            verbose,
            depth,
            no_references,
            strict,
        ) = parse_arguments(parser)
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "pr"
        assert number == 123
        assert output_path is None
        assert auto_output is True
        assert verbose is False
        assert depth == 2  # default value
        assert no_references is False
        assert strict is False

    def test_parse_arguments_issue_url_format(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with Issue URL format."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/issues/456"],
        )
        (
            owner,
            repo,
            ref_type,
            number,
            output_path,
            auto_output,
            verbose,
            depth,
            no_references,
            strict,
        ) = parse_arguments(parser)
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "issue"
        assert number == 456
        assert output_path is None
        assert auto_output is True
        assert verbose is False
        assert depth == 2
        assert no_references is False
        assert strict is False

    def test_parse_arguments_owner_repo_pr_number(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with owner/repo/pr/number format."""
        parser = create_parser()
        mocker.patch.object(sys, "argv", ["pr2md", "owner", "repo", "pr", "123"])
        (
            owner,
            repo,
            ref_type,
            number,
            output_path,
            auto_output,
            verbose,
            depth,
            no_references,
            strict,
        ) = parse_arguments(parser)
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "pr"
        assert number == 123
        assert output_path is None
        assert auto_output is True
        assert verbose is False
        assert depth == 2
        assert no_references is False
        assert strict is False

    def test_parse_arguments_owner_repo_issue_number(
        self, mocker: MockerFixture
    ) -> None:
        """Test parsing arguments with owner/repo/issue/number format."""
        parser = create_parser()
        mocker.patch.object(sys, "argv", ["pr2md", "owner", "repo", "issue", "789"])
        (
            owner,
            repo,
            ref_type,
            number,
            output_path,
            auto_output,
            verbose,
            depth,
            no_references,
            strict,
        ) = parse_arguments(parser)
        assert owner == "owner"
        assert repo == "repo"
        assert ref_type == "issue"
        assert number == 789
        assert output_path is None
        assert auto_output is True
        assert verbose is False
        assert depth == 2
        assert no_references is False
        assert strict is False

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
            auto_output,
            _verbose,
            _depth,
            _no_references,
            _strict,
        ) = parse_arguments(parser)
        assert Path(output_path).name == "output.md"
        assert auto_output is False

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
            auto_output,
            verbose,
            _depth,
            _no_references,
            _strict,
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
            auto_output,
            _verbose,
            _depth,
            _no_references,
            _strict,
        ) = parse_arguments(parser)
        assert output_path is None

    def test_parse_arguments_auto_output_deferred(self, mocker: MockerFixture) -> None:
        """Test auto output path is deferred until type resolution in main."""
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
            auto_output,
            _verbose,
            _depth,
            _no_references,
            _strict,
        ) = parse_arguments(parser)
        assert output_path is None
        assert auto_output is True

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
            auto_output,
            _verbose,
            depth,
            _no_references,
            _strict,
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
            auto_output,
            _verbose,
            _depth,
            no_references,
            _strict,
        ) = parse_arguments(parser)
        assert no_references is True

    def test_parse_arguments_with_strict(self, mocker: MockerFixture) -> None:
        """Test parsing arguments with strict flag."""
        parser = create_parser()
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123", "--strict"],
        )
        (
            _owner,
            _repo,
            _ref_type,
            _number,
            _output_path,
            auto_output,
            _verbose,
            _depth,
            _no_references,
            strict,
        ) = parse_arguments(parser)
        assert strict is True

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

    def test_filters_self_reference(self, mocker: MockerFixture) -> None:
        """Test primary self-references are excluded from downloads."""
        mock_downloader = mocker.patch("pr2md.cli.ReferenceDownloader")
        instance = mock_downloader.return_value.__enter__.return_value
        self_ref = GitHubReference(
            ref_type="pr", owner="owner", repo="repo", number=123
        )
        other_ref = GitHubReference(
            ref_type="issue", owner="owner", repo="repo", number=456
        )
        instance.extract_references_from_pr.return_value = {self_ref, other_ref}
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

        instance.download_all_references.assert_called_once_with({other_ref})

    def test_self_reference_only_logs_and_skips_download(
        self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test only self-references produce an info log and skip downloading."""
        mock_downloader = mocker.patch("pr2md.cli.ReferenceDownloader")
        instance = mock_downloader.return_value.__enter__.return_value
        self_ref = GitHubReference(
            ref_type="pr", owner="owner", repo="repo", number=123
        )
        instance.extract_references_from_pr.return_value = {self_ref}
        mock_pr = MagicMock()

        with caplog.at_level(logging.INFO, logger="pr2md.cli"):
            success, skipped, depth_skipped = download_references_if_needed(
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

        instance.download_all_references.assert_not_called()
        assert success is True
        assert not skipped
        assert not depth_skipped
        assert any("self-references excluded" in r.message for r in caplog.records)

    def test_issue_path_skips_when_issue_missing(self, mocker: MockerFixture) -> None:
        """Test issue reference extraction is skipped when issue object is None."""
        mock_downloader = mocker.patch("pr2md.cli.ReferenceDownloader")

        success, skipped, depth_skipped = download_references_if_needed(
            "owner",
            "repo",
            "issue",
            456,
            "Issue-456.md",
            2,
            False,
            False,
            None,
            None,
            [],
            [],
            [],
        )

        mock_downloader.assert_not_called()
        assert success is True
        assert not skipped
        assert not depth_skipped

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

    def test_returns_false_when_downloads_fail(self, mocker: MockerFixture) -> None:
        """Test failure flag propagates from downloader."""
        mock_downloader = mocker.patch("pr2md.cli.ReferenceDownloader")
        instance = mock_downloader.return_value.__enter__.return_value
        instance.extract_references_from_pr.return_value = {
            GitHubReference(ref_type="pr", owner="owner", repo="repo", number=2)
        }
        instance.download_all_references.return_value = []
        instance.had_download_failures = True
        instance.skipped_references = []
        instance.skipped_depth_references = []
        mock_pr = MagicMock()

        success, skipped, depth_skipped = download_references_if_needed(
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

        assert success is False
        assert not skipped
        assert not depth_skipped

    def test_download_references_for_issue_auto_naming(
        self, mocker: MockerFixture
    ) -> None:
        """Test reference download is triggered for auto-named issue output."""
        mock_downloader = mocker.patch("pr2md.cli.ReferenceDownloader")
        instance = mock_downloader.return_value.__enter__.return_value
        instance.extract_references_from_issue.return_value = set()
        mock_issue = MagicMock()

        download_references_if_needed(
            "owner",
            "repo",
            "issue",
            456,
            "Issue-456.md",
            2,
            False,
            False,
            None,
            mock_issue,
            [],
            [],
            [],
        )

        instance.extract_references_from_issue.assert_called_once()

    def test_skips_references_for_custom_output(self, mocker: MockerFixture) -> None:
        """Test reference download skipped when custom output path is used."""
        mock_downloader = mocker.patch("pr2md.cli.ReferenceDownloader")
        mock_pr = MagicMock()

        success, skipped, depth_skipped = download_references_if_needed(
            "owner",
            "repo",
            "pr",
            123,
            "custom.md",
            2,
            False,
            False,
            mock_pr,
            None,
            [],
            [],
            [],
        )

        mock_downloader.assert_not_called()
        assert success is True
        assert not skipped
        assert not depth_skipped

    def test_append_reference_summary(self, work_dir: Path) -> None:
        """Test appending reference summary to an existing file."""
        output = work_dir / "PR-1.md"
        output.write_text("# PR\n", encoding="utf-8")
        ref = GitHubReference(ref_type="issue", owner="o", repo="r", number=2)

        assert append_reference_summary(str(output), [(ref, "not found")]) is True
        content = output.read_text(encoding="utf-8")
        assert "## Reference Download Summary" in content
        assert "not found" in content

    def test_append_reference_summary_depth_skipped_only(self, work_dir: Path) -> None:
        """Test appending depth-limit summary without failures."""
        output = work_dir / "PR-1.md"
        output.write_text("# PR\n", encoding="utf-8")
        ref = GitHubReference(ref_type="issue", owner="o", repo="r", number=2)

        assert (
            append_reference_summary(
                str(output),
                [],
                depth_skipped=[(ref, "Exceeded reference depth limit (--depth 1)")],
            )
            is True
        )
        content = output.read_text(encoding="utf-8")
        assert "skipped" in content.lower()
        assert "depth limit" in content.lower()

    def test_main_strict_ignores_depth_skips_only(self, mocker: MockerFixture) -> None:
        """Test --strict does not fail when only depth-limited refs were skipped."""
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123", "--strict"],
        )
        mock_pr = MagicMock()
        mocker.patch(
            "pr2md.cli.extract_pr_data",
            return_value=("# Markdown", True, mock_pr, [], [], []),
        )
        mocker.patch("pr2md.cli.write_output", return_value=True)
        depth_skipped = [
            (
                GitHubReference(ref_type="issue", owner="owner", repo="repo", number=2),
                "Exceeded reference depth limit (--depth 1)",
            )
        ]
        mocker.patch(
            "pr2md.cli.download_references_if_needed",
            return_value=(True, [], depth_skipped),
        )
        mocker.patch("pr2md.cli.append_reference_summary", return_value=True)

        main()


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

    def test_extract_issue_data_unexpected_error_verbose(
        self, mocker: MockerFixture
    ) -> None:
        """Test issue data extraction with unexpected error in verbose mode."""
        mock_extractor = MagicMock()
        mock_extractor.extract_all.side_effect = ValueError("Unexpected error")
        _mock_extractor_context(mock_extractor)
        mocker.patch("pr2md.cli.GitHubIssueExtractor", return_value=mock_extractor)

        markdown, success, issue, comments = extract_issue_data(
            "owner", "repo", 456, True
        )
        assert success is False
        assert markdown == ""
        assert issue is None
        assert comments == []

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


class TestResolvePrimaryRefType:
    """Tests for primary resource type resolution."""

    def test_returns_same_type_when_matching(self, mocker: MockerFixture) -> None:
        """Test no change when CLI type matches API type."""
        mock_client = mocker.Mock()
        mock_client.fetch_issue_or_pr_metadata.return_value = ("pr", None)

        resolved_type, payload = _resolve_primary_ref_type(
            "pr", "owner", "repo", 1, mock_client
        )
        assert resolved_type == "pr"
        assert payload is None

    def test_auto_corrects_issue_to_pr(self, mocker: MockerFixture) -> None:
        """Test auto-correction when issue arg targets a PR."""
        mock_client = mocker.Mock()
        mock_client.fetch_issue_or_pr_metadata.return_value = ("pr", None)

        resolved_type, payload = _resolve_primary_ref_type(
            "issue", "owner", "repo", 1, mock_client
        )
        assert resolved_type == "pr"
        assert payload is None

    def test_auto_corrects_pr_to_issue(self, mocker: MockerFixture) -> None:
        """Test auto-correction when pr arg targets an issue."""
        mock_client = mocker.Mock()
        issue_payload = {"number": 1, "title": "Issue"}
        mock_client.fetch_issue_or_pr_metadata.return_value = ("issue", issue_payload)

        resolved_type, payload = _resolve_primary_ref_type(
            "pr", "owner", "repo", 1, mock_client
        )
        assert resolved_type == "issue"
        assert payload == issue_payload

    def test_returns_original_type_when_not_found(
        self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test original type is kept when resource is not found."""
        mock_client = mocker.Mock()
        mock_client.fetch_issue_or_pr_metadata.return_value = (None, None)

        with caplog.at_level(logging.WARNING, logger="pr2md.cli"):
            resolved_type, payload = _resolve_primary_ref_type(
                "pr", "owner", "repo", 1, mock_client
            )

        assert resolved_type == "pr"
        assert payload is None
        assert any("not found during type probe" in r.message for r in caplog.records)

    def test_run_primary_extraction_uses_resolved_type(
        self, mocker: MockerFixture
    ) -> None:
        """Test extraction path uses auto-corrected type."""
        mocker.patch(
            "pr2md.cli._resolve_primary_ref_type",
            return_value="pr",
        )
        mocker.patch(
            "pr2md.cli.extract_pr_data",
            return_value=("# Markdown", True, MagicMock(), [], [], []),
        )
        mock_issue_extract = mocker.patch("pr2md.cli.extract_issue_data")

        _run_primary_extraction(
            "issue", "owner", "repo", 1, False, mocker.Mock(), resolved_type="pr"
        )

        mock_issue_extract.assert_not_called()


class TestWriteOutput:
    """Tests for write_output function."""

    def test_write_output_to_file(self, work_dir: Path) -> None:
        """Test writing output to file."""
        output_file = work_dir / "output.md"
        markdown = "# Test Markdown"

        success = write_output(markdown, str(output_file), False)
        assert success is True
        assert output_file.read_text(encoding="utf-8") == markdown

    def test_write_output_to_stdout(self, mocker: MockerFixture) -> None:
        """Test writing output to stdout."""
        markdown = "# Test Markdown"
        mock_write = mocker.patch("pr2md.cli._write_stdout")

        success = write_output(markdown, None, False)
        assert success is True
        mock_write.assert_called_once_with(markdown)

    def test_write_output_logs_overwrite(
        self, work_dir: Path, mocker: MockerFixture
    ) -> None:
        """Test overwrite warning when writing to an existing file."""
        output_file = work_dir / "output.md"
        output_file.write_text("old", encoding="utf-8")
        mock_log = mocker.patch("pr2md.cli.log_overwrite_if_exists")

        success = write_output("# New", str(output_file), False)
        assert success is True
        mock_log.assert_called_once_with(str(output_file))

    def test_write_stdout_success_path(self, mocker: MockerFixture) -> None:
        """Test stdout write uses reconfigure and print on success."""
        from pr2md.cli import _write_stdout

        mock_stdout = mocker.patch("pr2md.cli.sys.stdout")
        mock_stdout.reconfigure = mocker.Mock()
        mock_print = mocker.patch("builtins.print")

        _write_stdout("hello world")

        mock_stdout.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace"
        )
        mock_print.assert_called_once_with("hello world")

    def test_write_stdout_unicode_fallback(self, mocker: MockerFixture) -> None:
        """Test stdout write uses UTF-8 when console reconfigure fails."""
        from pr2md.cli import _write_stdout

        mock_stdout = mocker.patch("pr2md.cli.sys.stdout")
        mock_stdout.reconfigure = mocker.Mock(side_effect=OSError("unsupported"))
        mock_stdout.buffer = mocker.Mock()

        _write_stdout("café ☕")

        mock_stdout.buffer.write.assert_any_call(
            "café ☕".encode("utf-8", errors="replace")
        )
        mock_stdout.buffer.write.assert_any_call(b"\n")
        mock_stdout.buffer.flush.assert_called_once()

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

    @pytest.fixture(autouse=True)
    def _mock_resolve_primary_type(self, mocker: MockerFixture) -> None:
        """Avoid live API calls for type resolution in main tests."""
        mocker.patch(
            "pr2md.cli._resolve_primary_ref_type",
            side_effect=lambda ref_type, *_args, **_kwargs: (ref_type, None),
        )

    @pytest.fixture(autouse=True)
    def _isolated_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Run main() tests in a temp directory so auto-named outputs never land in the repo."""
        monkeypatch.chdir(tmp_path)

    def test_main_type_probe_api_error_exits(self, mocker: MockerFixture) -> None:
        """Test main exits when shared client type probe fails."""
        mocker.patch.object(
            sys, "argv", ["pr2md", "https://github.com/owner/repo/pull/123"]
        )
        mocker.patch(
            "pr2md.cli._resolve_primary_ref_type",
            side_effect=GitHubAPIError("Rate limit exceeded", status_code=403),
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_auto_output_validation_error(self, mocker: MockerFixture) -> None:
        """Test main exits when auto output path validation fails."""
        mocker.patch.object(
            sys, "argv", ["pr2md", "https://github.com/owner/repo/pull/123"]
        )
        mocker.patch(
            "pr2md.cli._resolve_primary_ref_type",
            return_value=("pr", None),
        )
        mocker.patch(
            "pr2md.cli._auto_output_path",
            side_effect=ValueError("Invalid output path"),
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

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

    def test_main_uses_single_github_client(self, mocker: MockerFixture) -> None:
        """Test main creates one shared GitHubClient for the full run."""
        mocker.patch.object(
            sys, "argv", ["pr2md", "https://github.com/owner/repo/pull/123"]
        )
        mock_client = mocker.Mock()
        mock_client_cm = mocker.patch("pr2md.cli.GitHubClient")
        mock_client_cm.return_value.__enter__.return_value = mock_client
        mocker.patch(
            "pr2md.cli._run_primary_extraction",
            return_value=("# Markdown", True, MagicMock(), None, [], [], [], "pr"),
        )
        mocker.patch("pr2md.cli.write_output", return_value=True)
        mocker.patch(
            "pr2md.cli.download_references_if_needed",
            return_value=(True, [], []),
        )

        main()

        mock_client_cm.assert_called_once()
        mock_client_cm.return_value.__enter__.assert_called_once()
        mock_client_cm.return_value.__exit__.assert_called_once()

    def test_run_primary_extraction_type_probe_api_error(
        self, mocker: MockerFixture
    ) -> None:
        """Test extraction fails when type probe hits a non-404 API error."""
        mock_client = mocker.Mock()
        mock_client.fetch_issue_or_pr_metadata.side_effect = GitHubAPIError(
            "Rate limit exceeded",
            status_code=403,
        )

        markdown, success, *_rest = _run_primary_extraction(
            "pr", "owner", "repo", 1, False, mock_client
        )

        assert success is False
        assert markdown == ""

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

    def test_main_strict_reference_failure(self, mocker: MockerFixture) -> None:
        """Test main exits with code 2 when strict and references fail."""
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123", "--strict"],
        )
        mock_pr = MagicMock()
        mocker.patch(
            "pr2md.cli.extract_pr_data",
            return_value=("# Markdown", True, mock_pr, [], [], []),
        )
        mocker.patch("pr2md.cli.write_output", return_value=True)
        mocker.patch(
            "pr2md.cli.download_references_if_needed",
            return_value=(False, [], []),
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_main_append_summary_failure(self, mocker: MockerFixture) -> None:
        """Test main exits with code 1 when summary append fails."""
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123"],
        )
        mock_pr = MagicMock()
        mocker.patch(
            "pr2md.cli.extract_pr_data",
            return_value=("# Markdown", True, mock_pr, [], [], []),
        )
        mocker.patch("pr2md.cli.write_output", return_value=True)
        skipped = [
            (
                GitHubReference(ref_type="issue", owner="owner", repo="repo", number=2),
                "not found",
            )
        ]
        mocker.patch(
            "pr2md.cli.download_references_if_needed",
            return_value=(False, skipped, []),
        )
        mocker.patch("pr2md.cli.append_reference_summary", return_value=False)

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_append_summary_os_error(self, mocker: MockerFixture) -> None:
        """Test main exits when appending summary hits OSError."""
        mocker.patch.object(
            sys,
            "argv",
            ["pr2md", "https://github.com/owner/repo/pull/123"],
        )
        mock_pr = MagicMock()
        mocker.patch(
            "pr2md.cli.extract_pr_data",
            return_value=("# Markdown", True, mock_pr, [], [], []),
        )
        mocker.patch("pr2md.cli.write_output", return_value=True)
        skipped = [
            (
                GitHubReference(ref_type="issue", owner="owner", repo="repo", number=2),
                "not found",
            )
        ]
        mocker.patch(
            "pr2md.cli.download_references_if_needed",
            return_value=(False, skipped, []),
        )
        mocker.patch(
            "pr2md.cli.append_text_atomic",
            side_effect=OSError("read failed"),
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_append_reference_summary_noop_when_empty(self) -> None:
        """Test append returns True when there is nothing to summarize."""
        assert append_reference_summary("output.md", []) is True

    def test_append_reference_summary_noop_when_summary_empty(
        self, mocker: MockerFixture
    ) -> None:
        """Test append returns True when formatter produces no summary text."""
        ref = GitHubReference(ref_type="issue", owner="o", repo="r", number=2)
        mocker.patch(
            "pr2md.cli.MarkdownFormatter.format_reference_download_summary",
            return_value="",
        )
        assert append_reference_summary("output.md", [(ref, "reason")]) is True

    def test_append_reference_summary_write_failure(
        self, work_dir: Path, mocker: MockerFixture
    ) -> None:
        """Test append returns False when atomic append fails."""
        output = work_dir / "PR-1.md"
        output.write_text("# PR\n", encoding="utf-8")
        ref = GitHubReference(ref_type="issue", owner="o", repo="r", number=2)
        mocker.patch("pr2md.cli.append_text_atomic", side_effect=OSError("disk full"))

        assert append_reference_summary(str(output), [(ref, "not found")]) is False

    def test_main_auto_corrects_output_filename(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test auto output filename uses resolved type, not user-supplied type."""
        mocker.patch.object(sys, "argv", ["pr2md", "owner", "repo", "issue", "42"])
        mocker.patch("pr2md.cli._resolve_primary_ref_type", return_value=("pr", None))
        mocker.patch(
            "pr2md.cli.extract_pr_data",
            return_value=("# Markdown", True, MagicMock(), [], [], []),
        )
        mock_write = mocker.patch("pr2md.cli.write_output", return_value=True)
        mocker.patch(
            "pr2md.cli.download_references_if_needed",
            return_value=(True, [], []),
        )
        mocker.patch(
            "pr2md.cli.validate_output_path", side_effect=lambda p: str(tmp_path / p)
        )

        main()

        write_path = mock_write.call_args[0][1]
        assert write_path is not None
        assert Path(write_path).name == "PR-42.md"

    def test_module_entry_point_help(self) -> None:
        """Test python -m pr2md --help runs successfully."""
        result = subprocess.run(
            [sys.executable, "-m", "pr2md", "--help"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0
        assert "Extract GitHub Pull Request or Issue" in result.stdout

    def test_main_module_invokes_cli_main(self, mocker: MockerFixture) -> None:
        """Test pr2md.__main__ delegates to cli.main."""
        mock_main = mocker.patch("pr2md.cli.main")
        from pr2md.__main__ import main as entry_main

        entry_main()
        mock_main.assert_called_once()


class TestCLIHypothesis:
    """Hypothesis tests for CLI functions."""

    @given(
        owner=st.from_regex(r"[a-zA-Z0-9._-]{1,39}", fullmatch=True),
        repo=st.from_regex(r"[a-zA-Z0-9._-]{1,100}", fullmatch=True),
        pr_number=st.integers(min_value=1, max_value=100000),
        protocol=st.sampled_from(["https"]),
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
        owner=st.from_regex(r"[a-zA-Z0-9._-]{1,39}", fullmatch=True),
        repo=st.from_regex(r"[a-zA-Z0-9._-]{1,100}", fullmatch=True),
        issue_number=st.integers(min_value=1, max_value=100000),
        protocol=st.sampled_from(["https"]),
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
        mock_write = mocker.patch("pr2md.cli._write_stdout")
        success = write_output(markdown, None, False)
        assert success is True
        mock_write.assert_called_once_with(markdown)

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
        self,
        markdown: str,
        filename: str,
        work_dir: Path,
    ) -> None:
        """Test writing output to file with various markdown content."""
        output_file = work_dir / filename
        success = write_output(markdown, str(output_file), False)
        assert success is True
        assert output_file.exists()
        assert output_file.read_text(encoding="utf-8") == markdown

    @given(
        owner=st.from_regex(r"[a-zA-Z0-9._-]{1,39}", fullmatch=True),
        repo=st.from_regex(r"[a-zA-Z0-9._-]{1,100}", fullmatch=True),
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
        owner=st.from_regex(r"[a-zA-Z0-9._-]{1,39}", fullmatch=True),
        repo=st.from_regex(r"[a-zA-Z0-9._-]{1,100}", fullmatch=True),
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
