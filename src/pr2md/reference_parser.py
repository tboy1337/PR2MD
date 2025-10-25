"""Parse GitHub issue and PR references from text content."""

import logging
import re
from dataclasses import dataclass
from typing import Literal, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitHubReference:
    """Represents a GitHub issue or PR reference."""

    ref_type: Literal["issue", "pr"]
    owner: str
    repo: str
    number: int

    def __hash__(self) -> int:
        """Make GitHubReference hashable for use in sets."""
        return hash((self.ref_type, self.owner, self.repo, self.number))


class ReferenceParser:
    """Parser for detecting GitHub references in text."""

    # Regex patterns for different reference formats
    # Pattern 1: Full URLs - https://github.com/owner/repo/pull/123 or /issues/123
    URL_PATTERN = re.compile(
        r"https?://github\.com/([^/\s]+)/([^/\s]+)/(pull|issues)/(\d+)",
        re.IGNORECASE,
    )

    # Pattern 2: Cross-repo - owner/repo#123
    CROSS_REPO_PATTERN = re.compile(
        r"(?:^|\s)([a-zA-Z0-9\-_]+)/([a-zA-Z0-9\-_\.]+)#(\d+)(?:\s|$|[,.\)])"
    )

    # Pattern 3: Same repo - #123
    SAME_REPO_PATTERN = re.compile(r"(?:^|\s)#(\d+)(?:\s|$|[,.\)])")

    def __init__(self, base_owner: str, base_repo: str) -> None:
        """
        Initialize the reference parser.

        Args:
            base_owner: The owner of the base repository
            base_repo: The name of the base repository
        """
        self.base_owner = base_owner
        self.base_repo = base_repo
        logger.debug("Initialized ReferenceParser for %s/%s", base_owner, base_repo)

    def parse_references(self, text: Optional[str]) -> set[GitHubReference]:
        """
        Parse all GitHub references from text.

        Args:
            text: Text content to parse

        Returns:
            Set of unique GitHubReference objects
        """
        if not text:
            return set()

        references: set[GitHubReference] = set()

        # Parse URL references
        references.update(self._parse_url_references(text))

        # Parse cross-repo references
        references.update(self._parse_cross_repo_references(text))

        # Parse same-repo references
        references.update(self._parse_same_repo_references(text))

        logger.debug("Found %d references in text", len(references))
        return references

    def _parse_url_references(self, text: str) -> set[GitHubReference]:
        """Parse full GitHub URL references."""
        references: set[GitHubReference] = set()

        for match in self.URL_PATTERN.finditer(text):
            owner, repo, ref_type_str, number_str = match.groups()
            ref_type: Literal["issue", "pr"] = (
                "pr" if ref_type_str.lower() == "pull" else "issue"
            )
            number = int(number_str)

            reference = GitHubReference(
                ref_type=ref_type,
                owner=owner,
                repo=repo,
                number=number,
            )
            references.add(reference)
            logger.debug(
                "Found URL reference: %s/%s %s #%d",
                owner,
                repo,
                ref_type,
                number,
            )

        return references

    def _parse_cross_repo_references(self, text: str) -> set[GitHubReference]:
        """Parse cross-repository references (owner/repo#123)."""
        references: set[GitHubReference] = set()

        for match in self.CROSS_REPO_PATTERN.finditer(text):
            owner, repo, number_str = match.groups()
            number = int(number_str)

            # We need to determine if it's a PR or issue by checking GitHub API
            # For now, we'll try to fetch as both. The downloader will handle this.
            # But to be consistent with the API, we'll mark cross-repo references
            # as 'pr' by default and let the downloader verify.
            reference = GitHubReference(
                ref_type="pr",  # Will be verified during download
                owner=owner,
                repo=repo,
                number=number,
            )
            references.add(reference)
            logger.debug("Found cross-repo reference: %s/%s #%d", owner, repo, number)

        return references

    def _parse_same_repo_references(self, text: str) -> set[GitHubReference]:
        """Parse same-repository references (#123)."""
        references: set[GitHubReference] = set()

        for match in self.SAME_REPO_PATTERN.finditer(text):
            number_str = match.group(1)
            number = int(number_str)

            # Same as cross-repo, we'll default to 'pr' and verify during download
            reference = GitHubReference(
                ref_type="pr",  # Will be verified during download
                owner=self.base_owner,
                repo=self.base_repo,
                number=number,
            )
            references.add(reference)
            logger.debug("Found same-repo reference: #%d", number)

        return references
