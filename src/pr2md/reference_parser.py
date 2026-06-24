"""Parse GitHub issue and PR references from text content."""

import logging
import re
from dataclasses import dataclass
from typing import Literal, Optional

from pr2md.validation import validate_issue_number, validate_owner, validate_repo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitHubReference:
    """Represents a GitHub issue or PR reference."""

    ref_type: Literal["issue", "pr"]
    owner: str
    repo: str
    number: int
    from_url: bool = False


class ReferenceParser:
    """Parser for detecting GitHub references in text."""

    # Regex patterns for different reference formats
    # Pattern 1: Full URLs - https://github.com/owner/repo/pull/123 or /issues/123
    URL_PATTERN = re.compile(
        r"https://github\.com/([^/\s]+)/([^/\s]+)/(pull|issues)/(\d+)",
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

        deduped = self._dedupe_references(references)
        logger.debug("Found %d references in text", len(deduped))
        return deduped

    @staticmethod
    def _dedupe_references(references: set[GitHubReference]) -> set[GitHubReference]:
        """Dedupe by owner/repo/number, preferring URL-derived references."""
        by_key: dict[tuple[str, str, int], GitHubReference] = {}
        for reference in references:
            key = (reference.owner, reference.repo, reference.number)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = reference
            elif reference.from_url:
                by_key[key] = reference
        return set(by_key.values())

    def _validated_reference(
        self,
        ref_type: Literal["issue", "pr"],
        owner: str,
        repo: str,
        number: int,
        *,
        from_url: bool = False,
    ) -> Optional[GitHubReference]:
        """Return a reference if owner/repo are valid GitHub names."""
        try:
            validate_owner(owner)
            validate_repo(repo)
            validate_issue_number(number)
        except ValueError as err:
            logger.debug(
                "Skipping invalid reference %s/%s #%d: %s", owner, repo, number, err
            )
            return None
        return GitHubReference(
            ref_type=ref_type,
            owner=owner,
            repo=repo,
            number=number,
            from_url=from_url,
        )

    def _parse_url_references(self, text: str) -> set[GitHubReference]:
        """Parse full GitHub URL references."""
        references: set[GitHubReference] = set()

        for match in self.URL_PATTERN.finditer(text):
            owner, repo, ref_type_str, number_str = match.groups()
            ref_type: Literal["issue", "pr"] = (
                "pr" if ref_type_str.lower() == "pull" else "issue"
            )
            number = int(number_str)

            reference = self._validated_reference(
                ref_type, owner, repo, number, from_url=True
            )
            if reference is not None:
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

            reference = self._validated_reference(
                "pr", owner, repo, number, from_url=False
            )
            if reference is not None:
                references.add(reference)
                logger.debug(
                    "Found cross-repo reference: %s/%s #%d", owner, repo, number
                )

        return references

    def _parse_same_repo_references(self, text: str) -> set[GitHubReference]:
        """Parse same-repository references (#123)."""
        references: set[GitHubReference] = set()

        for match in self.SAME_REPO_PATTERN.finditer(text):
            number_str = match.group(1)
            number = int(number_str)

            reference = self._validated_reference(
                "pr",
                self.base_owner,
                self.base_repo,
                number,
                from_url=False,
            )
            if reference is not None:
                references.add(reference)
                logger.debug("Found same-repo reference: #%d", number)

        return references
