"""PR2MD - GitHub Pull Request and Issue to Markdown Exporter.

A tool for extracting GitHub Pull Request and Issue data and formatting it as Markdown.
"""

from importlib.metadata import PackageNotFoundError, version

from pr2md.exceptions import GitHubAPIError
from pr2md.formatter import MarkdownFormatter
from pr2md.issue_extractor import GitHubIssueExtractor
from pr2md.models import (
    Comment,
    Issue,
    Label,
    PullRequest,
    Review,
    ReviewComment,
    User,
)
from pr2md.pr_extractor import GitHubPRExtractor

try:
    __version__ = version("PR2MD")
except PackageNotFoundError:
    __version__ = "1.0.15"

__all__ = [
    "Comment",
    "GitHubAPIError",
    "GitHubIssueExtractor",
    "GitHubPRExtractor",
    "Issue",
    "Label",
    "MarkdownFormatter",
    "PullRequest",
    "Review",
    "ReviewComment",
    "User",
]
