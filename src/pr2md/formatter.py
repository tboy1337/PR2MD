"""Markdown formatter for GitHub PR data."""

import logging
from collections import defaultdict
from datetime import datetime, timezone

from pr2md.markdown_utils import fenced_code_block
from pr2md.models import Comment, Issue, PullRequest, Review, ReviewComment, User
from pr2md.reference_parser import GitHubReference

logger = logging.getLogger(__name__)

DIFF_UNAVAILABLE_PREFIX = "__DIFF_UNAVAILABLE__:"

_REVIEW_STATE_EMOJI: dict[str, str] = {
    "APPROVED": "✅",
    "CHANGES_REQUESTED": "🔴",
    "COMMENTED": "💬",
    "DISMISSED": "🚫",
    "PENDING": "⏳",
}


def _format_user_link(user: User) -> str:
    """Format a GitHub user as a markdown link or plain text."""
    if user.html_url:
        return f"[{user.login}]({user.html_url})"
    return user.login


def _format_utc(moment: datetime) -> str:
    """Format a timezone-aware datetime as a UTC timestamp string."""
    if moment.tzinfo is None:
        utc_dt = moment.replace(tzinfo=timezone.utc)
    else:
        utc_dt = moment.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _escape_markdown_title(title: str) -> str:
    """Prevent user titles starting with '#' from breaking heading structure."""
    if title.startswith("#"):
        return "\\" + title
    return title


class MarkdownFormatter:
    """Format GitHub PR data as Markdown."""

    @staticmethod
    def format_pr(
        pull_request: PullRequest,
        comments: list[Comment],
        reviews: list[Review],
        review_comments: list[ReviewComment],
        diff: str,
    ) -> str:
        """
        Format all PR data as Markdown.

        Args:
            pull_request: Pull request object
            comments: List of comments
            reviews: List of reviews
            review_comments: List of review comments
            diff: Diff string

        Returns:
            Formatted Markdown string
        """
        logger.info("Formatting PR data as Markdown")
        sections = [
            MarkdownFormatter._format_header(pull_request),
            MarkdownFormatter._format_description(pull_request),
            MarkdownFormatter._format_changes_summary(pull_request),
            MarkdownFormatter._format_diff(diff),
            MarkdownFormatter._format_conversation(comments),
            MarkdownFormatter._format_reviews(reviews),
            MarkdownFormatter._format_review_comments(review_comments),
        ]

        result = "\n\n".join(sections)
        logger.info("Formatted Markdown (%d characters)", len(result))
        return result

    @staticmethod
    def _format_header(pull_request: PullRequest) -> str:
        """Format PR header section."""
        status = pull_request.state.upper()
        if pull_request.merged_at:
            status = "MERGED"

        labels_str = ""
        if pull_request.labels:
            label_names = ", ".join(
                [f"`{label.name}`" for label in pull_request.labels]
            )
            labels_str = f"\n**Labels:** {label_names}"

        closed_str = ""
        if pull_request.closed_at:
            closed_time = _format_utc(pull_request.closed_at)
            closed_str = f"\n**Closed:** {closed_time}"

        merged_str = ""
        if pull_request.merged_at:
            merged_time = _format_utc(pull_request.merged_at)
            merged_str = f"\n**Merged:** {merged_time}"

        created_time = _format_utc(pull_request.created_at)
        updated_time = _format_utc(pull_request.updated_at)

        return f"""# {_escape_markdown_title(pull_request.title)}

**PR Number:** #{pull_request.number}
**Status:** {status}
**Author:** {_format_user_link(pull_request.user)}
**Created:** {created_time}
**Updated:** {updated_time}{closed_str}{merged_str}
**URL:** {pull_request.html_url}
**Base:** `{pull_request.base_ref}` (`{pull_request.base_sha[:7]}`)
**Head:** `{pull_request.head_ref}` (`{pull_request.head_sha[:7]}`){labels_str}"""

    @staticmethod
    def _format_description(pull_request: PullRequest) -> str:
        """Format PR description section."""
        if not pull_request.body:
            return "## Description\n\n*No description provided.*"
        return f"## Description\n\n{pull_request.body}"

    @staticmethod
    def _format_changes_summary(pull_request: PullRequest) -> str:
        """Format changes summary section."""
        return f"""## Changes Summary

- **Files changed:** {pull_request.changed_files}
- **Additions:** +{pull_request.additions}
- **Deletions:** -{pull_request.deletions}"""

    @staticmethod
    def _format_diff(diff: str) -> str:
        """Format diff section."""
        if diff.startswith(DIFF_UNAVAILABLE_PREFIX):
            reason = diff[len(DIFF_UNAVAILABLE_PREFIX) :]
            return f"## Code Diff\n\n*Diff unavailable: {reason}*"
        if not diff:
            return "## Code Diff\n\n*No diff available.*"

        return "## Code Diff\n\n" + fenced_code_block(diff, "diff")

    @staticmethod
    def _format_conversation(comments: list[Comment]) -> str:
        """Format conversation thread section."""
        if not comments:
            return "## Conversation Thread\n\n*No comments in the conversation thread.*"

        # Sort by creation time
        sorted_comments = sorted(comments, key=lambda c: c.created_at)

        formatted_comments = []
        for comment in sorted_comments:
            comment_time = _format_utc(comment.created_at)
            # pylint: disable=line-too-long
            formatted_comment = f"""### {_format_user_link(comment.user)} commented on {comment_time}

{comment.body}

*[View on GitHub]({comment.html_url})*"""
            # pylint: enable=line-too-long
            formatted_comments.append(formatted_comment)

        return "## Conversation Thread\n\n" + "\n\n---\n\n".join(formatted_comments)

    @staticmethod
    def _superseded_review_ids(reviews_by_user: dict[str, list[Review]]) -> set[int]:
        """Return IDs of reviews superseded by a later review from the same user."""
        superseded: set[int] = set()
        for user_reviews in reviews_by_user.values():
            if len(user_reviews) > 1:
                for review in user_reviews[:-1]:
                    superseded.add(review.id)
        return superseded

    @staticmethod
    def _format_single_review(
        review: Review,
        *,
        superseded_review_ids: set[int],
        reviews_by_user: dict[str, list[Review]],
    ) -> str:
        """Format one review entry."""
        submitted_str = (
            _format_utc(review.submitted_at) if review.submitted_at else "Unknown date"
        )
        emoji = _REVIEW_STATE_EMOJI.get(review.state, "")
        body_str = review.body if review.body else "*No comment provided.*"

        superseded_note = ""
        if review.id in superseded_review_ids:
            user_reviews = reviews_by_user[review.user.login]
            latest_review = user_reviews[-1]
            latest_state = latest_review.state.replace("_", " ")
            latest_emoji = _REVIEW_STATE_EMOJI.get(latest_review.state, "")
            superseded_note = (
                f"\n\n> **Note:** This review was superseded by a later "
                f"{latest_emoji} **{latest_state}** review from the same reviewer."
            )

        # pylint: disable=line-too-long
        return f"""### {emoji} {_format_user_link(review.user)} {review.state.replace("_", " ")} on {submitted_str}

{body_str}{superseded_note}

*[View on GitHub]({review.html_url})*"""
        # pylint: enable=line-too-long

    @staticmethod
    def _format_reviews(reviews: list[Review]) -> str:
        """Format reviews section."""
        if not reviews:
            return "## Reviews\n\n*No reviews submitted.*"

        # Sort by submission time; reviews without timestamps sort first
        sorted_reviews = sorted(
            reviews,
            key=lambda r: (
                r.submitted_at
                if r.submitted_at is not None
                else datetime.min.replace(tzinfo=timezone.utc)
            ),
        )

        # Group reviews by user to detect status progressions
        reviews_by_user: dict[str, list[Review]] = defaultdict(list)
        for review in sorted_reviews:
            reviews_by_user[review.user.login].append(review)

        superseded_review_ids = MarkdownFormatter._superseded_review_ids(
            reviews_by_user
        )
        formatted_reviews = [
            MarkdownFormatter._format_single_review(
                review,
                superseded_review_ids=superseded_review_ids,
                reviews_by_user=reviews_by_user,
            )
            for review in sorted_reviews
        ]

        return "## Reviews\n\n" + "\n\n---\n\n".join(formatted_reviews)

    @staticmethod
    def _format_review_comments(review_comments: list[ReviewComment]) -> str:
        """Format review comments section."""
        if not review_comments:
            return "## Review Comments (Code Comments)\n\n*No review comments on code.*"

        # Group by file path
        comments_by_file: dict[str, list[ReviewComment]] = defaultdict(list)
        for comment in review_comments:
            comments_by_file[comment.path].append(comment)

        # Sort files alphabetically
        sorted_files = sorted(comments_by_file.keys())

        formatted_files = []
        for file_path in sorted_files:
            file_comments = sorted(
                comments_by_file[file_path], key=lambda c: c.created_at
            )

            formatted_comments = []
            for comment in file_comments:
                # Check if this is a reply
                reply_str = ""
                if comment.in_reply_to_id:
                    reply_str = f" *(in reply to comment #{comment.in_reply_to_id})*"

                comment_time = _format_utc(comment.created_at)
                # pylint: disable=line-too-long
                formatted_comment = f"""#### {_format_user_link(comment.user)} commented on {comment_time}{reply_str}

**Code context:**
{fenced_code_block(comment.diff_hunk, "diff")}

**Comment:**
{comment.body or ""}

*[View on GitHub]({comment.html_url})*"""
                # pylint: enable=line-too-long
                formatted_comments.append(formatted_comment)

            file_section = f"""### File: `{file_path}`

{chr(10).join(formatted_comments)}"""
            formatted_files.append(file_section)

        return "## Review Comments (Code Comments)\n\n" + "\n\n---\n\n".join(
            formatted_files
        )

    @staticmethod
    def format_issue(issue: Issue, comments: list[Comment]) -> str:
        """
        Format issue data as Markdown.

        Args:
            issue: Issue object
            comments: List of comments

        Returns:
            Formatted Markdown string
        """
        logger.info("Formatting issue data as Markdown")
        sections = [
            MarkdownFormatter._format_issue_header(issue),
            MarkdownFormatter._format_issue_description(issue),
            MarkdownFormatter._format_conversation(comments),
        ]

        result = "\n\n".join(sections)
        logger.info("Formatted Markdown (%d characters)", len(result))
        return result

    @staticmethod
    def _format_issue_header(issue: Issue) -> str:
        """Format issue header section."""
        status = issue.state.upper()

        labels_str = ""
        if issue.labels:
            label_names = ", ".join([f"`{label.name}`" for label in issue.labels])
            labels_str = f"\n**Labels:** {label_names}"

        closed_str = ""
        if issue.closed_at:
            closed_time = _format_utc(issue.closed_at)
            closed_str = f"\n**Closed:** {closed_time}"
            # Update status to CLOSED if it has a closed_at date
            if status == "OPEN":
                status = "CLOSED"

        created_time = _format_utc(issue.created_at)
        updated_time = _format_utc(issue.updated_at)

        return f"""# {_escape_markdown_title(issue.title)}

**Issue Number:** #{issue.number}
**Status:** {status}
**Author:** {_format_user_link(issue.user)}
**Created:** {created_time}
**Updated:** {updated_time}{closed_str}
**URL:** {issue.html_url}{labels_str}"""

    @staticmethod
    def _format_issue_description(issue: Issue) -> str:
        """Format issue description section."""
        if not issue.body:
            return "## Description\n\n*No description provided.*"
        return f"## Description\n\n{issue.body}"

    @staticmethod
    def _format_reference_summary_items(
        items: list[tuple[GitHubReference, str]],
    ) -> list[str]:
        """Format reference summary bullet lines."""
        lines: list[str] = []
        for reference, reason in items:
            type_label = "PR" if reference.ref_type == "pr" else "Issue"
            path_segment = "pull" if reference.ref_type == "pr" else "issues"
            lines.append(
                f"- **{type_label}** [{reference.owner}/{reference.repo}"
                f"#{reference.number}](https://github.com/"
                f"{reference.owner}/{reference.repo}/"
                f"{path_segment}/{reference.number}): {reason}"
            )
        return lines

    @staticmethod
    def format_reference_download_summary(
        skipped: list[tuple[GitHubReference, str]],
        *,
        depth_skipped: list[tuple[GitHubReference, str]] | None = None,
    ) -> str:
        """Format a markdown section listing reference download outcomes."""
        depth_items = depth_skipped or []
        if not skipped and not depth_items:
            return ""

        lines = [
            "## Reference Download Summary",
            "",
        ]

        if skipped:
            lines.extend(
                [
                    "The following referenced items could **not** be downloaded:",
                    "",
                ]
            )
            lines.extend(MarkdownFormatter._format_reference_summary_items(skipped))

        if depth_items:
            if skipped:
                lines.append("")
            lines.extend(
                [
                    "The following referenced items were **skipped** (depth limit):",
                    "",
                ]
            )
            lines.extend(MarkdownFormatter._format_reference_summary_items(depth_items))

        return "\n".join(lines)
