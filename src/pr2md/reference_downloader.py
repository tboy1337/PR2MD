"""Orchestrate downloading of referenced issues and pull requests."""

import json
import logging
from typing import Literal, Optional

import requests

from pr2md.exceptions import GitHubAPIError
from pr2md.file_io import log_overwrite_if_exists, write_text_atomic
from pr2md.formatter import MarkdownFormatter
from pr2md.github_client import GitHubClient
from pr2md.issue_extractor import GitHubIssueExtractor
from pr2md.models import Comment, Issue, PullRequest, Review, ReviewComment
from pr2md.pr_extractor import GitHubPRExtractor
from pr2md.reference_parser import GitHubReference, ReferenceParser
from pr2md.validation import validate_output_path

logger = logging.getLogger(__name__)


class ReferenceDownloader:
    """Download referenced issues and PRs recursively."""

    def __init__(
        self,
        base_owner: str,
        base_repo: str,
        max_depth: int = 2,
        verbose: bool = False,
        client: Optional[GitHubClient] = None,
    ) -> None:
        """
        Initialize the reference downloader.

        Args:
            base_owner: Owner of the base repository
            base_repo: Name of the base repository
            max_depth: Maximum recursion depth (0 = no recursion)
            verbose: Enable verbose logging
            client: Optional shared GitHub API client
        """
        self.base_owner = base_owner
        self.base_repo = base_repo
        self.max_depth = max_depth
        self.verbose = verbose
        self.parser = ReferenceParser(base_owner, base_repo)
        self.downloaded: set[GitHubReference] = set()
        self._downloaded_keys: set[tuple[str, str, int]] = set()
        self.skipped_references: list[tuple[GitHubReference, str]] = []
        self.skipped_depth_references: list[tuple[GitHubReference, str]] = []
        self.had_download_failures = False
        self._owns_client = client is None
        self._client = client or GitHubClient()
        logger.info(
            "Initialized ReferenceDownloader for %s/%s with max_depth=%d",
            base_owner,
            base_repo,
            max_depth,
        )

    def __enter__(self) -> "ReferenceDownloader":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying API client if owned by this downloader."""
        if self._owns_client:
            self._client.close()

    def record_skipped_reference(self, reference: GitHubReference, reason: str) -> None:
        """Record a reference that could not be downloaded."""
        self.skipped_references.append((reference, reason))
        self.had_download_failures = True

    def record_depth_skipped_reference(
        self, reference: GitHubReference, reason: str
    ) -> None:
        """Record a reference skipped due to the depth limit (not a failure)."""
        self.skipped_depth_references.append((reference, reason))

    def log_skipped_summary(self) -> None:
        """Log a summary of skipped references."""
        if not self.skipped_references:
            return
        logger.error(
            "Failed to download %d referenced item(s):",
            len(self.skipped_references),
        )
        for reference, reason in self.skipped_references:
            type_label = "PR" if reference.ref_type == "pr" else "Issue"
            logger.error(
                "  - %s %s/%s #%d: %s",
                type_label,
                reference.owner,
                reference.repo,
                reference.number,
                reason,
            )

    def generate_filename(
        self, ref_type: Literal["issue", "pr"], owner: str, repo: str, number: int
    ) -> str:
        """
        Generate filename for a reference.

        Args:
            ref_type: Type of reference ('issue' or 'pr')
            owner: Repository owner
            repo: Repository name
            number: Issue or PR number

        Returns:
            Generated filename
        """
        prefix = ""
        if (owner, repo) != (self.base_owner, self.base_repo):
            prefix = f"{owner}-{repo}-"

        type_str = "PR" if ref_type == "pr" else "Issue"
        return f"{prefix}{type_str}-{number}.md"

    def extract_references_from_pr(
        self,
        pull_request: PullRequest,
        comments: list[Comment],
        reviews: list[Review],
        review_comments: list[ReviewComment],
    ) -> set[GitHubReference]:
        """
        Extract all references from PR data.

        Args:
            pull_request: Pull request object
            comments: List of comments
            reviews: List of reviews
            review_comments: List of review comments

        Returns:
            Set of unique GitHubReference objects
        """
        logger.debug("Extracting references from PR #%d", pull_request.number)
        references: set[GitHubReference] = set()

        references.update(self.parser.parse_references(pull_request.body))

        for comment in comments:
            references.update(self.parser.parse_references(comment.body))

        for review in reviews:
            references.update(self.parser.parse_references(review.body))

        for review_comment in review_comments:
            references.update(self.parser.parse_references(review_comment.body))

        logger.info(
            "Found %d references in PR #%d", len(references), pull_request.number
        )
        return references

    def extract_references_from_issue(
        self, issue: Issue, comments: list[Comment]
    ) -> set[GitHubReference]:
        """
        Extract all references from issue data.

        Args:
            issue: Issue object
            comments: List of comments

        Returns:
            Set of unique GitHubReference objects
        """
        logger.debug("Extracting references from Issue #%d", issue.number)
        references: set[GitHubReference] = set()

        references.update(self.parser.parse_references(issue.body))

        for comment in comments:
            references.update(self.parser.parse_references(comment.body))

        logger.info("Found %d references in Issue #%d", len(references), issue.number)
        return references

    def _log_download_error(
        self,
        err: Exception,
        *,
        resource_label: str,
        owner: str,
        repo: str,
        number: int,
    ) -> None:
        """Log a download failure."""
        if isinstance(err, GitHubAPIError):
            logger.error(
                "Failed to download %s %s/%s #%d: %s",
                resource_label,
                owner,
                repo,
                number,
                err,
            )
            return
        logger.error(
            "Unexpected error downloading %s %s/%s #%d: %s",
            resource_label,
            owner,
            repo,
            number,
            err,
        )
        if self.verbose:
            logger.exception("Full traceback:")

    def _format_pr_reference(
        self, owner: str, repo: str, number: int
    ) -> tuple[str, set[GitHubReference]]:
        """Download and format a pull request reference."""
        with GitHubPRExtractor(owner, repo, number, client=self._client) as extractor:
            pull_request, comments, reviews, review_comments, diff = (
                extractor.extract_all()
            )
        markdown = MarkdownFormatter.format_pr(
            pull_request, comments, reviews, review_comments, diff
        )
        references = self.extract_references_from_pr(
            pull_request, comments, reviews, review_comments
        )
        return markdown, references

    def _format_issue_reference(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        cached_issue_payload: Optional[dict[str, object]] = None,
    ) -> tuple[str, set[GitHubReference]]:
        """Download and format an issue reference."""
        with GitHubIssueExtractor(
            owner,
            repo,
            number,
            client=self._client,
            cached_issue_payload=cached_issue_payload,
            warn_if_pull_request=False,
        ) as extractor:
            issue, comments = extractor.extract_all()
        markdown = MarkdownFormatter.format_issue(issue, comments)
        references = self.extract_references_from_issue(issue, comments)
        return markdown, references

    def _download_and_format(
        self,
        ref_type: Literal["issue", "pr"],
        owner: str,
        repo: str,
        number: int,
        *,
        cached_issue_payload: Optional[dict[str, object]] = None,
    ) -> tuple[str, Optional[set[GitHubReference]], bool]:
        """Download and format a PR or issue reference.

        Returns:
            Tuple of markdown, references found, and whether a 404 was received
            (caller may retry with the alternate resource type).
        """
        resource_label = "PR" if ref_type == "pr" else "Issue"
        logger.info("Downloading %s %s/%s #%d", resource_label, owner, repo, number)

        try:
            if ref_type == "pr":
                markdown, references = self._format_pr_reference(owner, repo, number)
            else:
                markdown, references = self._format_issue_reference(
                    owner,
                    repo,
                    number,
                    cached_issue_payload=cached_issue_payload,
                )
            return markdown, references, False
        except (
            GitHubAPIError,
            requests.RequestException,
            OSError,
            json.JSONDecodeError,
            KeyError,
            ValueError,
            TypeError,
        ) as err:
            self._log_download_error(
                err,
                resource_label=resource_label,
                owner=owner,
                repo=repo,
                number=number,
            )
            try_alternate = isinstance(err, GitHubAPIError) and err.status_code == 404
            return "", None, try_alternate

    def download_pr(
        self, owner: str, repo: str, pr_number: int
    ) -> tuple[str, Optional[set[GitHubReference]]]:
        """
        Download a pull request and format as markdown.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number

        Returns:
            Tuple of (markdown content, set of references found)
            Returns (empty string, None) if download fails
        """
        return self._download_and_format("pr", owner, repo, pr_number)[:2]

    def download_issue(
        self, owner: str, repo: str, issue_number: int
    ) -> tuple[str, Optional[set[GitHubReference]]]:
        """
        Download an issue and format as markdown.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number

        Returns:
            Tuple of (markdown content, set of references found)
            Returns (empty string, None) if download fails
        """
        return self._download_and_format("issue", owner, repo, issue_number)[:2]

    def determine_ref_type(
        self, owner: str, repo: str, number: int
    ) -> Optional[Literal["issue", "pr"]]:
        """
        Determine if a reference is an issue or PR.

        Args:
            owner: Repository owner
            repo: Repository name
            number: Issue/PR number

        Returns:
            'pr' if it's a pull request, 'issue' if it's an issue, None if not found
        """
        ref_type, _payload = self.determine_ref_type_and_payload(owner, repo, number)
        return ref_type

    def determine_ref_type_and_payload(
        self, owner: str, repo: str, number: int
    ) -> tuple[Optional[Literal["issue", "pr"]], Optional[dict[str, object]]]:
        """
        Determine reference type and return cached issue payload when applicable.

        Returns:
            Tuple of (ref_type, issue_payload). issue_payload is set only for issues.
        """
        ref_type, payload = self._client.fetch_issue_or_pr_metadata(owner, repo, number)
        if ref_type is None:
            logger.warning(
                "Could not determine type for %s/%s #%d (not found)",
                owner,
                repo,
                number,
            )
            return None, None
        issue_payload: Optional[dict[str, object]] = (
            payload if ref_type == "issue" else None
        )
        return ref_type, issue_payload

    def _reference_with_type(
        self, reference: GitHubReference, ref_type: Literal["issue", "pr"]
    ) -> GitHubReference:
        """Return a copy of reference with an updated type."""
        return GitHubReference(
            ref_type=ref_type,
            owner=reference.owner,
            repo=reference.repo,
            number=reference.number,
            from_url=reference.from_url,
        )

    def _fetch_reference_markdown(
        self,
        ref_type: Literal["issue", "pr"],
        owner: str,
        repo: str,
        number: int,
        *,
        type_confirmed: bool = False,
        cached_issue_payload: Optional[dict[str, object]] = None,
    ) -> tuple[str, Optional[set[GitHubReference]], Literal["issue", "pr"]]:
        """Download markdown, falling back to the alternate type only on 404."""
        markdown, found_refs, try_alternate = self._download_and_format(
            ref_type,
            owner,
            repo,
            number,
            cached_issue_payload=cached_issue_payload,
        )
        if markdown:
            return markdown, found_refs, ref_type

        if not try_alternate or type_confirmed:
            return "", found_refs, ref_type

        alternate: Literal["issue", "pr"] = "issue" if ref_type == "pr" else "pr"
        markdown, found_refs, _ = self._download_and_format(
            alternate, owner, repo, number
        )
        if markdown:
            return markdown, found_refs, alternate
        return "", found_refs, ref_type

    def download_reference(
        self, reference: GitHubReference, current_depth: int
    ) -> list[str]:
        """
        Download a single reference and recursively download its references.

        Args:
            reference: GitHubReference to download
            current_depth: Current recursion depth

        Returns:
            List of filenames that were downloaded
        """
        ref_key = (reference.owner, reference.repo, reference.number)
        if ref_key in self._downloaded_keys:
            logger.debug(
                "Skipping already downloaded reference: %s/%s #%d",
                reference.owner,
                reference.repo,
                reference.number,
            )
            return []

        if current_depth > self.max_depth:
            logger.info(
                "Skipping reference due to depth limit (%d): %s/%s %s #%d",
                self.max_depth,
                reference.owner,
                reference.repo,
                reference.ref_type,
                reference.number,
            )
            self.record_depth_skipped_reference(
                reference,
                f"Exceeded reference depth limit (--depth {self.max_depth})",
            )
            return []

        actual_type, cached_issue_payload = self.determine_ref_type_and_payload(
            reference.owner, reference.repo, reference.number
        )
        if actual_type is None:
            self.record_skipped_reference(
                reference, "Could not determine issue or PR type (not found)"
            )
            return []

        ref_type = actual_type
        reference = self._reference_with_type(reference, ref_type)

        markdown, found_refs, ref_type = self._fetch_reference_markdown(
            ref_type,
            reference.owner,
            reference.repo,
            reference.number,
            type_confirmed=True,
            cached_issue_payload=cached_issue_payload,
        )
        reference = self._reference_with_type(reference, ref_type)

        if not markdown:
            self.record_skipped_reference(
                reference, "Download failed (see logs for details)"
            )
            return []

        filename = self.generate_filename(
            ref_type, reference.owner, reference.repo, reference.number
        )
        try:
            validated_path = validate_output_path(filename)
            log_overwrite_if_exists(validated_path)
            write_text_atomic(validated_path, markdown)
            logger.info("Saved %s", filename)
        except (ValueError, OSError) as err:
            logger.error("Failed to save %s: %s", filename, err)
            self.record_skipped_reference(reference, f"Failed to save file: {err}")
            return []

        self.downloaded.add(reference)
        self._downloaded_keys.add(ref_key)
        downloaded_files = [filename]

        if found_refs and current_depth < self.max_depth:
            for found_ref in found_refs:
                downloaded_files.extend(
                    self.download_reference(found_ref, current_depth + 1)
                )

        return downloaded_files

    def download_all_references(self, references: set[GitHubReference]) -> list[str]:
        """
        Download all references recursively.

        Args:
            references: Set of GitHubReference objects to download

        Returns:
            List of filenames that were downloaded
        """
        logger.info("Starting download of %d references", len(references))
        all_downloaded: list[str] = []

        sorted_refs = sorted(
            references,
            key=lambda ref: (ref.owner, ref.repo, ref.ref_type, ref.number),
        )
        for reference in sorted_refs:
            downloaded = self.download_reference(reference, current_depth=1)
            all_downloaded.extend(downloaded)

        logger.info(
            "Completed download of %d files from %d initial references",
            len(all_downloaded),
            len(references),
        )
        return all_downloaded
