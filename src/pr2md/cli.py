"""Command-line interface for GitHub PR extractor."""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Callable, NamedTuple, Optional, cast

import requests

from pr2md.exceptions import GitHubAPIError
from pr2md.file_io import write_text_atomic
from pr2md.formatter import MarkdownFormatter
from pr2md.issue_extractor import GitHubIssueExtractor
from pr2md.models import Comment, Issue, PullRequest, Review, ReviewComment
from pr2md.pr_extractor import GitHubPRExtractor
from pr2md.reference_downloader import ReferenceDownloader
from pr2md.reference_parser import GitHubReference
from pr2md.validation import (
    validate_depth,
    validate_issue_number,
    validate_output_path,
    validate_owner,
    validate_repo,
)

# Sentinel value for stdout output
_STDOUT_SENTINEL = "__STDOUT__"


class ParsedArguments(NamedTuple):
    """Parsed CLI arguments for a PR or issue export."""

    owner: str
    repo: str
    ref_type: str
    number: int
    output_path: Optional[str]
    verbose: bool
    depth: int
    no_references: bool
    strict: bool


def setup_logging(verbose: bool = False) -> None:
    """
    Set up logging configuration.

    Args:
        verbose: Enable verbose logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def parse_pr_url(url: str) -> tuple[str, str, str, int]:
    """
    Parse GitHub PR or Issue URL to extract owner, repo, type, and number.

    Args:
        url: GitHub PR or Issue URL

    Returns:
        Tuple of (owner, repo, ref_type, number) where ref_type is "pr" or "issue"

    Raises:
        ValueError: If URL is invalid
    """
    pattern = r"https?://github\.com/([^/]+)/([^/]+)/(pull|issues)/(\d+)"
    match = re.match(pattern, url)
    if not match:
        raise ValueError(
            f"Invalid GitHub URL: {url}\n"
            "Expected format: https://github.com/owner/repo/pull/123 or "
            "https://github.com/owner/repo/issues/123"
        )
    owner, repo, ref_type_str, number_str = match.groups()
    # Normalize "issues" to "issue"
    ref_type = "issue" if ref_type_str == "issues" else "pr"
    return str(owner), str(repo), ref_type, int(number_str)


def create_parser() -> argparse.ArgumentParser:
    """
    Create command-line argument parser.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Extract GitHub Pull Request or Issue details to Markdown format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://github.com/owner/repo/pull/123          # Saves to PR-123.md
  %(prog)s https://github.com/owner/repo/issues/456        # Saves to Issue-456.md
  %(prog)s owner repo pr 123                               # Saves to PR-123.md
  %(prog)s owner repo issue 456                            # Saves to Issue-456.md
  %(prog)s https://github.com/owner/repo/pull/123 -o       # Outputs to stdout
  %(prog)s owner repo pr 123 --output pr-details.md --verbose
        """,
    )

    parser.add_argument(
        "pr_identifier",
        nargs="+",
        help=(
            "GitHub PR/Issue URL (https://github.com/owner/repo/pull/123 or "
            "https://github.com/owner/repo/issues/456) or owner repo pr/issue number"
        ),
    )

    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        const=_STDOUT_SENTINEL,
        help=(
            "Output file path (default: PR-{number}.md). "
            "Use -o without filename for stdout"
        ),
        default=None,
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        help=(
            "Maximum recursion depth for downloading referenced PRs/issues "
            "(default: 2)"
        ),
    )

    parser.add_argument(
        "--no-references",
        action="store_true",
        help="Disable automatic downloading of referenced PRs and issues",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 2 if any referenced PR/issue download fails",
    )

    return parser


def _parse_identifier_from_args(pr_args: list[str]) -> tuple[str, str, str, int]:
    """Parse owner, repo, ref type, and number from CLI identifier arguments."""
    if len(pr_args) == 1:
        return parse_pr_url(str(pr_args[0]))
    if len(pr_args) == 4:
        owner = str(pr_args[0])
        repo = str(pr_args[1])
        ref_type_arg = str(pr_args[2]).lower()
        if ref_type_arg not in ("pr", "issue"):
            raise ValueError(
                f"Invalid reference type: {ref_type_arg}. Must be 'pr' or 'issue'"
            )
        return owner, repo, ref_type_arg, int(pr_args[3])
    raise ValueError(
        "Invalid arguments. Provide either a GitHub URL or "
        "owner repo pr/issue number"
    )


def _output_path_from_args(
    args: argparse.Namespace,
    ref_type: str,
    number: int,
) -> Optional[str]:
    """Resolve the output path from parsed CLI arguments."""
    if args.output is None:
        type_str = "PR" if ref_type == "pr" else "Issue"
        return f"{type_str}-{number}.md"
    if args.output == _STDOUT_SENTINEL:
        return None
    try:
        return validate_output_path(str(args.output))
    except ValueError as err:
        logger = logging.getLogger(__name__)
        logger.error("%s", err)
        sys.exit(1)


def parse_arguments(parser: argparse.ArgumentParser) -> ParsedArguments:
    """
    Parse command-line arguments and extract PR/Issue details.

    Args:
        parser: Argument parser

    Returns:
        Tuple of (owner, repo, ref_type, number, output_path, verbose, depth,
                  no_references, strict)
    """
    args = parser.parse_args()
    logger = logging.getLogger(__name__)

    try:
        owner, repo, ref_type, number = _parse_identifier_from_args(
            list(args.pr_identifier)
        )
        validate_owner(owner)
        validate_repo(repo)
        validate_issue_number(number)
    except (ValueError, IndexError) as err:
        logger.error("Error parsing identifier: %s", err)
        sys.exit(1)

    output_path = _output_path_from_args(args, ref_type, number)
    verbose = bool(args.verbose)
    depth = int(args.depth)
    no_references = bool(args.no_references)
    strict = bool(args.strict)

    try:
        validate_depth(depth)
    except ValueError as err:
        logger.error("%s", err)
        sys.exit(1)

    return ParsedArguments(
        owner=owner,
        repo=repo,
        ref_type=ref_type,
        number=number,
        output_path=output_path,
        verbose=verbose,
        depth=depth,
        no_references=no_references,
        strict=strict,
    )


def _log_processing_error(logger: logging.Logger, message: str, verbose: bool) -> None:
    logger.error(message)
    if verbose:
        logger.exception("Full traceback:")


def _extract_and_format(
    extract_fn: Callable[[], object],
    format_fn: Callable[[object], str],
    *,
    resource_label: str,
    verbose: bool,
) -> tuple[str, bool, Optional[object]]:
    """Extract data via extract_fn, format via format_fn, with shared error handling."""
    logger = logging.getLogger(__name__)

    try:
        data = extract_fn()
    except GitHubAPIError as err:
        logger.error("GitHub API error: %s", err)
        return "", False, None
    except (
        requests.RequestException,
        OSError,
        json.JSONDecodeError,
        KeyError,
        ValueError,
    ) as err:
        _log_processing_error(
            logger, f"Unexpected error extracting {resource_label}: {err}", verbose
        )
        return "", False, None

    try:
        markdown = format_fn(data)
        return markdown, True, data
    except (KeyError, ValueError, TypeError) as err:
        _log_processing_error(
            logger, f"Error formatting {resource_label}: {err}", verbose
        )
        return "", False, None


def extract_pr_data(
    owner: str, repo: str, pr_number: int, verbose: bool
) -> tuple[
    str, bool, Optional[PullRequest], list[Comment], list[Review], list[ReviewComment]
]:
    """
    Extract PR data and format as Markdown.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        verbose: Enable verbose logging

    Returns:
        Tuple of (markdown, success, pull_request, comments, reviews, review_comments)
    """

    def extract_fn() -> (
        tuple[PullRequest, list[Comment], list[Review], list[ReviewComment], str]
    ):
        with GitHubPRExtractor(owner, repo, pr_number) as extractor:
            return extractor.extract_all()

    def format_fn(
        data: tuple[PullRequest, list[Comment], list[Review], list[ReviewComment], str],
    ) -> str:
        pull_request, comments, reviews, review_comments, diff = data
        return MarkdownFormatter.format_pr(
            pull_request, comments, reviews, review_comments, diff
        )

    markdown, success, data = _extract_and_format(
        extract_fn,
        cast(Callable[[object], str], format_fn),
        resource_label="PR data",
        verbose=verbose,
    )
    if not success or data is None:
        return "", False, None, [], [], []

    pull_request, comments, reviews, review_comments, _diff = cast(
        tuple[PullRequest, list[Comment], list[Review], list[ReviewComment], str],
        data,
    )
    return markdown, True, pull_request, comments, reviews, review_comments


def extract_issue_data(
    owner: str, repo: str, issue_number: int, verbose: bool
) -> tuple[str, bool, Optional[Issue], list[Comment]]:
    """
    Extract Issue data and format as Markdown.

    Args:
        owner: Repository owner
        repo: Repository name
        issue_number: Issue number
        verbose: Enable verbose logging

    Returns:
        Tuple of (markdown, success, issue, comments)
    """

    def extract_fn() -> tuple[Issue, list[Comment]]:
        with GitHubIssueExtractor(owner, repo, issue_number) as extractor:
            return extractor.extract_all()

    def format_fn(data: tuple[Issue, list[Comment]]) -> str:
        issue, comments = data
        return MarkdownFormatter.format_issue(issue, comments)

    markdown, success, data = _extract_and_format(
        extract_fn,
        cast(Callable[[object], str], format_fn),
        resource_label="issue data",
        verbose=verbose,
    )
    if not success or data is None:
        return "", False, None, []

    issue, comments = cast(tuple[Issue, list[Comment]], data)
    return markdown, True, issue, comments


def append_reference_summary(
    output_path: str,
    skipped: list[tuple[GitHubReference, str]],
) -> bool:
    """Append a reference download summary section to an existing output file."""
    if not skipped:
        return True

    logger = logging.getLogger(__name__)
    summary = MarkdownFormatter.format_reference_download_summary(skipped)
    if not summary:
        return True

    try:
        existing = Path(output_path).read_text(encoding="utf-8")
        write_text_atomic(output_path, f"{existing}\n\n{summary}")
        logger.info("Appended reference download summary to %s", output_path)
        return True
    except OSError as err:
        logger.error("Failed to append reference summary to %s: %s", output_path, err)
        return False


def write_output(markdown: str, output_path: Optional[str], verbose: bool) -> bool:
    """
    Write markdown output to file or stdout.

    Args:
        markdown: Formatted markdown string
        output_path: Optional output file path
        verbose: Enable verbose logging

    Returns:
        True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)

    try:
        if output_path:
            write_text_atomic(output_path, markdown)
            logger.info("Output written to %s", output_path)
        else:
            print(markdown)  # noqa: T201
        return True
    except OSError as err:
        _log_processing_error(logger, f"Error writing output: {err}", verbose)
        return False


def download_references_if_needed(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    owner: str,
    repo: str,
    ref_type: str,
    number: int,
    output_path: Optional[str],
    depth: int,
    no_references: bool,
    verbose: bool,
    pull_request: Optional[PullRequest],
    issue: Optional[Issue],
    comments: list[Comment],
    reviews: list[Review],
    review_comments: list[ReviewComment],
) -> tuple[bool, list[tuple[GitHubReference, str]]]:
    """
    Download referenced PRs and issues when auto-naming is used.

    Returns:
        Tuple of (all succeeded, list of skipped references with reasons)
    """
    logger = logging.getLogger(__name__)
    type_str = "PR" if ref_type == "pr" else "Issue"
    using_auto_naming = output_path == f"{type_str}-{number}.md"

    if not using_auto_naming or no_references or not (pull_request or issue):
        return True, []

    logger.info("Scanning for referenced PRs and issues...")

    with ReferenceDownloader(
        owner, repo, max_depth=depth, verbose=verbose
    ) as downloader:
        if pull_request:
            references = downloader.extract_references_from_pr(
                pull_request, comments, reviews, review_comments
            )
        else:
            if issue is None:
                return True, []
            references = downloader.extract_references_from_issue(issue, comments)

        if not references:
            logger.info("No references found in %s", type_str)
            return True, []

        logger.info("Found %d references to download", len(references))
        downloaded_files = downloader.download_all_references(references)

        if downloaded_files:
            logger.info(
                "Downloaded %d referenced files: %s",
                len(downloaded_files),
                ", ".join(downloaded_files),
            )
        else:
            logger.info("No references were successfully downloaded")

        if downloader.skipped_references:
            downloader.log_skipped_summary()

        return not downloader.had_download_failures, downloader.skipped_references


def _run_primary_extraction(
    ref_type: str,
    owner: str,
    repo: str,
    number: int,
    verbose: bool,
) -> tuple[
    str,
    bool,
    Optional[PullRequest],
    Optional[Issue],
    list[Comment],
    list[Review],
    list[ReviewComment],
]:
    """Extract and format the target PR or issue."""
    if ref_type == "pr":
        markdown, success, pull_request, comments, reviews, review_comments = (
            extract_pr_data(owner, repo, number, verbose)
        )
        return markdown, success, pull_request, None, comments, reviews, review_comments

    markdown, success, issue, comments = extract_issue_data(
        owner, repo, number, verbose
    )
    return markdown, success, None, issue, comments, [], []


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    setup_logging(False)
    cli_args = parse_arguments(parser)

    if cli_args.verbose:
        setup_logging(True)
    logger = logging.getLogger(__name__)

    type_str = "PR" if cli_args.ref_type == "pr" else "Issue"
    logger.info(
        "Extracting %s %s/%s #%d",
        type_str,
        cli_args.owner,
        cli_args.repo,
        cli_args.number,
    )

    (
        markdown,
        success,
        pull_request,
        issue,
        comments,
        reviews,
        review_comments,
    ) = _run_primary_extraction(
        cli_args.ref_type,
        cli_args.owner,
        cli_args.repo,
        cli_args.number,
        cli_args.verbose,
    )

    if not success:
        sys.exit(1)

    if not write_output(markdown, cli_args.output_path, cli_args.verbose):
        sys.exit(1)

    logger.info("Extraction completed successfully")

    references_ok, skipped_references = download_references_if_needed(
        cli_args.owner,
        cli_args.repo,
        cli_args.ref_type,
        cli_args.number,
        cli_args.output_path,
        cli_args.depth,
        cli_args.no_references,
        cli_args.verbose,
        pull_request,
        issue,
        comments,
        reviews,
        review_comments,
    )

    if skipped_references and cli_args.output_path:
        if not append_reference_summary(cli_args.output_path, skipped_references):
            sys.exit(1)

    if cli_args.strict and not references_ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
