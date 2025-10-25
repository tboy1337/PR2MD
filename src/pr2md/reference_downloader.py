"""Orchestrate downloading of referenced issues and pull requests."""

import logging
from pathlib import Path
from typing import Literal, Optional

from pr2md.formatter import MarkdownFormatter
from pr2md.issue_extractor import GitHubAPIError, GitHubIssueExtractor
from pr2md.models import Comment, Issue, PullRequest, Review, ReviewComment
from pr2md.pr_extractor import GitHubPRExtractor
from pr2md.reference_parser import GitHubReference, ReferenceParser

logger = logging.getLogger(__name__)


class ReferenceDownloader:
    """Download referenced issues and PRs recursively."""

    def __init__(
        self,
        base_owner: str,
        base_repo: str,
        max_depth: int = 2,
        verbose: bool = False,
    ) -> None:
        """
        Initialize the reference downloader.

        Args:
            base_owner: Owner of the base repository
            base_repo: Name of the base repository
            max_depth: Maximum recursion depth (0 = no recursion)
            verbose: Enable verbose logging
        """
        self.base_owner = base_owner
        self.base_repo = base_repo
        self.max_depth = max_depth
        self.verbose = verbose
        self.parser = ReferenceParser(base_owner, base_repo)
        self.downloaded: set[GitHubReference] = set()
        logger.info(
            "Initialized ReferenceDownloader for %s/%s with max_depth=%d",
            base_owner,
            base_repo,
            max_depth,
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

        # Parse PR body
        references.update(self.parser.parse_references(pull_request.body))

        # Parse comments
        for comment in comments:
            references.update(self.parser.parse_references(comment.body))

        # Parse reviews
        for review in reviews:
            references.update(self.parser.parse_references(review.body))

        # Parse review comments
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

        # Parse issue body
        references.update(self.parser.parse_references(issue.body))

        # Parse comments
        for comment in comments:
            references.update(self.parser.parse_references(comment.body))

        logger.info("Found %d references in Issue #%d", len(references), issue.number)
        return references

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
        logger.info("Downloading PR %s/%s #%d", owner, repo, pr_number)

        try:
            extractor = GitHubPRExtractor(owner, repo, pr_number)
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
        except GitHubAPIError as err:
            logger.error(
                "Failed to download PR %s/%s #%d: %s", owner, repo, pr_number, err
            )
            return "", None
        except Exception as err:  # pylint: disable=broad-exception-caught
            logger.error(
                "Unexpected error downloading PR %s/%s #%d: %s",
                owner,
                repo,
                pr_number,
                err,
            )
            if self.verbose:
                logger.exception("Full traceback:")
            return "", None

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
        logger.info("Downloading Issue %s/%s #%d", owner, repo, issue_number)

        try:
            extractor = GitHubIssueExtractor(owner, repo, issue_number)
            issue, comments = extractor.extract_all()

            markdown = MarkdownFormatter.format_issue(issue, comments)

            references = self.extract_references_from_issue(issue, comments)

            return markdown, references
        except GitHubAPIError as err:
            logger.error(
                "Failed to download Issue %s/%s #%d: %s",
                owner,
                repo,
                issue_number,
                err,
            )
            return "", None
        except Exception as err:  # pylint: disable=broad-exception-caught
            logger.error(
                "Unexpected error downloading Issue %s/%s #%d: %s",
                owner,
                repo,
                issue_number,
                err,
            )
            if self.verbose:
                logger.exception("Full traceback:")
            return "", None

    def determine_ref_type(
        self, owner: str, repo: str, number: int
    ) -> Optional[Literal["issue", "pr"]]:
        """
        Determine if a reference is an issue or PR by attempting to fetch it.

        Args:
            owner: Repository owner
            repo: Repository name
            number: Issue/PR number

        Returns:
            'pr' if it's a pull request, 'issue' if it's an issue, None if not found
        """
        # Try as PR first
        try:
            extractor = GitHubPRExtractor(owner, repo, number)
            extractor.fetch_pr_details()
            return "pr"
        except GitHubAPIError:
            pass

        # Try as issue
        try:
            extractor_issue = GitHubIssueExtractor(owner, repo, number)
            extractor_issue.fetch_issue_details()
            return "issue"
        except GitHubAPIError:
            pass

        logger.warning(
            "Could not determine type for %s/%s #%d (not found)", owner, repo, number
        )
        return None

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
        # Check if already downloaded
        if reference in self.downloaded:
            logger.debug(
                "Skipping already downloaded reference: %s/%s %s #%d",
                reference.owner,
                reference.repo,
                reference.ref_type,
                reference.number,
            )
            return []

        # Check depth limit
        if current_depth > self.max_depth:
            logger.debug(
                "Skipping reference due to depth limit: %s/%s %s #%d",
                reference.owner,
                reference.repo,
                reference.ref_type,
                reference.number,
            )
            return []

        # Determine actual ref type if not from URL
        ref_type = reference.ref_type
        if ref_type == "pr" and not self._is_from_url(reference):
            actual_type = self.determine_ref_type(
                reference.owner, reference.repo, reference.number
            )
            if actual_type is None:
                return []
            ref_type = actual_type
            # Update reference with correct type
            reference = GitHubReference(
                ref_type=ref_type,
                owner=reference.owner,
                repo=reference.repo,
                number=reference.number,
            )

        # Mark as downloaded
        self.downloaded.add(reference)

        # Download the reference
        if ref_type == "pr":
            markdown, found_refs = self.download_pr(
                reference.owner, reference.repo, reference.number
            )
        else:
            markdown, found_refs = self.download_issue(
                reference.owner, reference.repo, reference.number
            )

        if not markdown:
            return []

        # Save to file
        filename = self.generate_filename(
            ref_type, reference.owner, reference.repo, reference.number
        )
        try:
            Path(filename).write_text(markdown, encoding="utf-8")
            logger.info("Saved %s", filename)
        except Exception as err:  # pylint: disable=broad-exception-caught
            logger.error("Failed to save %s: %s", filename, err)
            return []

        downloaded_files = [filename]

        # Recursively download references found in this reference
        if found_refs and current_depth < self.max_depth:
            for found_ref in found_refs:
                downloaded_files.extend(
                    self.download_reference(found_ref, current_depth + 1)
                )

        return downloaded_files

    def _is_from_url(self, _reference: GitHubReference) -> bool:
        """
        Check if a reference was parsed from a URL.

        This is a heuristic - URL-based references have explicit type info,
        so we trust them. Non-URL references need verification.

        Args:
            _reference: GitHubReference to check (currently unused)

        Returns:
            True if from URL (trustworthy type), False otherwise
        """
        # This is a simplified heuristic. In practice, we always verify
        # non-URL references by attempting to fetch them.
        return False

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

        for reference in references:
            downloaded = self.download_reference(reference, current_depth=1)
            all_downloaded.extend(downloaded)

        logger.info(
            "Completed download of %d files from %d initial references",
            len(all_downloaded),
            len(references),
        )
        return all_downloaded
