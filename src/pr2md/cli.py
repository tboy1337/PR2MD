"""Command-line interface for GitHub PR extractor."""

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Optional

from pr2md.formatter import MarkdownFormatter
from pr2md.issue_extractor import GitHubIssueExtractor
from pr2md.models import Comment, Issue, PullRequest, Review, ReviewComment
from pr2md.pr_extractor import GitHubAPIError, GitHubPRExtractor
from pr2md.reference_downloader import ReferenceDownloader

# Sentinel value for stdout output
_STDOUT_SENTINEL = "__STDOUT__"


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

    return parser


def parse_arguments(
    parser: argparse.ArgumentParser,
) -> tuple[str, str, str, int, Optional[str], bool, int, bool]:
    """
    Parse command-line arguments and extract PR/Issue details.

    Args:
        parser: Argument parser

    Returns:
        Tuple of (owner, repo, ref_type, number, output_path, verbose, depth,
                  no_references)
    """
    args = parser.parse_args()
    logger = logging.getLogger(__name__)

    # Initialize variables to satisfy pylint - they will be assigned in all code paths
    owner: str = ""
    repo: str = ""
    ref_type: str = ""
    number: int = 0

    # Parse PR/Issue identifier
    try:
        pr_args: list[str] = list(args.pr_identifier)
        if len(pr_args) == 1:
            # URL format
            owner, repo, ref_type, number = parse_pr_url(str(pr_args[0]))
        elif len(pr_args) == 4:
            # owner repo pr/issue number format
            owner = str(pr_args[0])
            repo = str(pr_args[1])
            ref_type_arg = str(pr_args[2]).lower()
            if ref_type_arg not in ("pr", "issue"):
                parser.error(
                    f"Invalid reference type: {ref_type_arg}. Must be 'pr' or 'issue'"
                )
            ref_type = ref_type_arg
            number = int(pr_args[3])
        else:
            parser.error(
                "Invalid arguments. Provide either a GitHub URL or "
                "owner repo pr/issue number"
            )
    except (ValueError, IndexError) as err:
        logger.error("Error parsing identifier: %s", err)
        sys.exit(1)

    # Handle output path: None -> default filename,
    # sentinel -> stdout, else -> provided path
    if args.output is None:
        # No -o specified, use default filename
        type_str = "PR" if ref_type == "pr" else "Issue"
        output_path = f"{type_str}-{number}.md"
    elif args.output == _STDOUT_SENTINEL:
        # -o without filename, use stdout (None value)
        output_path = None
    else:
        # -o with filename, use provided path
        output_path = str(args.output)

    verbose: bool = bool(args.verbose)
    depth: int = int(args.depth)
    no_references: bool = bool(args.no_references)

    return owner, repo, ref_type, number, output_path, verbose, depth, no_references


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
    logger = logging.getLogger(__name__)

    # Extract PR data
    try:
        extractor = GitHubPRExtractor(owner, repo, pr_number)
        pull_request, comments, reviews, review_comments, diff = extractor.extract_all()
    except GitHubAPIError as err:
        logger.error("GitHub API error: %s", err)
        return "", False, None, [], [], []
    except Exception as err:  # pylint: disable=broad-exception-caught
        logger.error("Unexpected error: %s", err)
        if verbose:
            logger.exception("Full traceback:")
        return "", False, None, [], [], []

    # Format as Markdown
    try:
        markdown = MarkdownFormatter.format_pr(
            pull_request, comments, reviews, review_comments, diff
        )
        return markdown, True, pull_request, comments, reviews, review_comments
    except Exception as err:  # pylint: disable=broad-exception-caught
        logger.error("Error formatting data: %s", err)
        if verbose:
            logger.exception("Full traceback:")
        return "", False, None, [], [], []


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
    logger = logging.getLogger(__name__)

    # Extract Issue data
    try:
        extractor = GitHubIssueExtractor(owner, repo, issue_number)
        issue, comments = extractor.extract_all()
    except GitHubAPIError as err:
        logger.error("GitHub API error: %s", err)
        return "", False, None, []
    except Exception as err:  # pylint: disable=broad-exception-caught
        logger.error("Unexpected error: %s", err)
        if verbose:
            logger.exception("Full traceback:")
        return "", False, None, []

    # Format as Markdown
    try:
        markdown = MarkdownFormatter.format_issue(issue, comments)
        return markdown, True, issue, comments
    except Exception as err:  # pylint: disable=broad-exception-caught
        logger.error("Error formatting data: %s", err)
        if verbose:
            logger.exception("Full traceback:")
        return "", False, None, []


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
            Path(output_path).write_text(markdown, encoding="utf-8")
            logger.info("Output written to %s", output_path)
        else:
            print(markdown)  # noqa: T201
        return True
    except Exception as err:  # pylint: disable=broad-exception-caught
        logger.error("Error writing output: %s", err)
        if verbose:
            logger.exception("Full traceback:")
        return False


def main() -> None:  # pylint: disable=too-many-locals,too-many-branches
    """Main entry point for the CLI."""
    parser = create_parser()
    owner, repo, ref_type, number, output_path, verbose, depth, no_references = (
        parse_arguments(parser)
    )

    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    type_str = "PR" if ref_type == "pr" else "Issue"
    logger.info("Extracting %s %s/%s #%d", type_str, owner, repo, number)

    # Extract data based on type
    if ref_type == "pr":
        markdown, success, pull_request, comments, reviews, review_comments = (
            extract_pr_data(owner, repo, number, verbose)
        )
        issue = None
    else:  # ref_type == "issue"
        markdown, success, issue, comments = extract_issue_data(
            owner, repo, number, verbose
        )
        pull_request = None
        reviews = []
        review_comments = []

    if not success:
        sys.exit(1)

    if not write_output(markdown, output_path, verbose):
        sys.exit(1)

    logger.info("Extraction completed successfully")

    # Download references only if auto-naming is used and not disabled
    using_auto_naming = output_path == f"{type_str}-{number}.md"
    if using_auto_naming and not no_references and (pull_request or issue):
        logger.info("Scanning for referenced PRs and issues...")

        downloader = ReferenceDownloader(owner, repo, max_depth=depth, verbose=verbose)

        # Extract references based on type
        if pull_request:
            references = downloader.extract_references_from_pr(
                pull_request, comments, reviews, review_comments
            )
        else:  # issue
            assert issue is not None  # issue is guaranteed to exist here
            references = downloader.extract_references_from_issue(issue, comments)

        if references:
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
        else:
            logger.info("No references found in %s", type_str)


if __name__ == "__main__":
    main()
