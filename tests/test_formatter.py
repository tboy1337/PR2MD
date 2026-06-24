"""Tests for Markdown formatter."""

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pr2md.formatter import MarkdownFormatter
from pr2md.models import Comment, Issue, Label, PullRequest, Review, ReviewComment, User
from pr2md.reference_parser import GitHubReference

# pylint: disable=redefined-outer-name  # pytest fixtures
# pylint: disable=protected-access  # testing private methods


@pytest.fixture
def sample_user() -> User:
    """Create a sample user."""
    return User(
        login="testuser",
        id=123,
        avatar_url="https://example.com/avatar.jpg",
        html_url="https://github.com/testuser",
    )


@pytest.fixture
def sample_pr(sample_user: User) -> PullRequest:
    """Create a sample pull request."""
    return PullRequest(
        number=1,
        title="Test Pull Request",
        body="This is a test PR",
        state="open",
        user=sample_user,
        created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        closed_at=None,
        merged_at=None,
        merge_commit_sha=None,
        html_url="https://github.com/owner/repo/pull/1",
        labels=[Label("bug", "d73a4a", "Something isn't working")],
        additions=10,
        deletions=5,
        changed_files=2,
        head_ref="feature",
        base_ref="main",
        head_sha="abc123def456",
        base_sha="def456abc123",
    )


@pytest.fixture
def sample_comment(sample_user: User) -> Comment:
    """Create a sample comment."""
    return Comment(
        id=456,
        user=sample_user,
        body="This is a comment",
        created_at=datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
        html_url="https://github.com/owner/repo/issues/1#issuecomment-456",
    )


@pytest.fixture
def sample_review(sample_user: User) -> Review:
    """Create a sample review."""
    return Review(
        id=789,
        user=sample_user,
        body="Looks good",
        state="APPROVED",
        html_url="https://github.com/owner/repo/pull/1#pullrequestreview-789",
        submitted_at=datetime(2025, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
        commit_id="abc123",
    )


@pytest.fixture
def sample_review_comment(sample_user: User) -> ReviewComment:
    """Create a sample review comment."""
    return ReviewComment(
        id=999,
        user=sample_user,
        body="This needs improvement",
        path="src/file.py",
        position=10,
        original_position=10,
        commit_id="abc123",
        original_commit_id="abc123",
        diff_hunk="@@ -1,3 +1,3 @@\n line1\n-line2\n+line2_modified",
        created_at=datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
        html_url="https://github.com/owner/repo/pull/1#discussion_r999",
        in_reply_to_id=None,
    )


class TestMarkdownFormatter:
    """Tests for MarkdownFormatter class."""

    def test_format_header(self, sample_pr: PullRequest) -> None:
        """Test header formatting."""
        header = MarkdownFormatter._format_header(sample_pr)
        assert "# Test Pull Request" in header
        assert "**PR Number:** #1" in header
        assert "**Status:** OPEN" in header
        assert "**Author:** [testuser]" in header
        assert "**Labels:** `bug`" in header

    def test_format_header_merged(self, sample_pr: PullRequest) -> None:
        """Test header formatting for merged PR."""
        sample_pr.merged_at = datetime(2025, 1, 3, 12, 0, 0, tzinfo=timezone.utc)
        header = MarkdownFormatter._format_header(sample_pr)
        assert "**Status:** MERGED" in header
        assert "**Merged:**" in header

    def test_format_description(self, sample_pr: PullRequest) -> None:
        """Test description formatting."""
        description = MarkdownFormatter._format_description(sample_pr)
        assert "## Description" in description
        assert "This is a test PR" in description

    def test_format_description_empty(self, sample_pr: PullRequest) -> None:
        """Test description formatting when empty."""
        sample_pr.body = None
        description = MarkdownFormatter._format_description(sample_pr)
        assert "*No description provided.*" in description

    def test_format_changes_summary(self, sample_pr: PullRequest) -> None:
        """Test changes summary formatting."""
        summary = MarkdownFormatter._format_changes_summary(sample_pr)
        assert "## Changes Summary" in summary
        assert "**Files changed:** 2" in summary
        assert "**Additions:** +10" in summary
        assert "**Deletions:** -5" in summary

    def test_format_diff(self) -> None:
        """Test diff formatting."""
        diff = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py"
        formatted = MarkdownFormatter._format_diff(diff)
        assert "## Code Diff" in formatted
        assert "```diff" in formatted
        assert diff in formatted

    def test_format_diff_empty(self) -> None:
        """Test diff formatting when empty."""
        formatted = MarkdownFormatter._format_diff("")
        assert "*No diff available.*" in formatted

    def test_format_diff_with_embedded_backticks(self) -> None:
        """Test diff formatting when content contains markdown fences."""
        diff = "line before\n```python\nprint('hi')\n```\nline after"
        formatted = MarkdownFormatter._format_diff(diff)
        assert "````diff" in formatted
        assert diff in formatted
        assert formatted.count("````") >= 2

    def test_format_pr_deleted_author(self, sample_pr: PullRequest) -> None:
        """Test PR header renders deleted users without broken links."""
        deleted_user = User(
            login="[deleted user]",
            id=0,
            avatar_url="",
            html_url="",
        )
        sample_pr.user = deleted_user
        header = MarkdownFormatter._format_header(sample_pr)
        assert "**Author:** [deleted user]" in header
        assert "](https://" not in header.split("**Author:**")[1].split("\n")[0]

    def test_format_conversation(self, sample_comment: Comment) -> None:
        """Test conversation formatting."""
        conversation = MarkdownFormatter._format_conversation([sample_comment])
        assert "## Conversation Thread" in conversation
        assert "[testuser]" in conversation
        assert "This is a comment" in conversation

    def test_format_conversation_empty(self) -> None:
        """Test conversation formatting when empty."""
        conversation = MarkdownFormatter._format_conversation([])
        assert "*No comments in the conversation thread.*" in conversation

    def test_format_reviews(self, sample_review: Review) -> None:
        """Test reviews formatting."""
        reviews = MarkdownFormatter._format_reviews([sample_review])
        assert "## Reviews" in reviews
        assert "APPROVED" in reviews
        assert "Looks good" in reviews
        assert "✅" in reviews

    def test_format_reviews_empty(self) -> None:
        """Test reviews formatting when empty."""
        reviews = MarkdownFormatter._format_reviews([])
        assert "*No reviews submitted.*" in reviews

    def test_format_reviews_single_reviewer_progression(
        self, sample_user: User
    ) -> None:
        """Test review formatting with status progression from same reviewer."""
        # First review: CHANGES_REQUESTED
        review1 = Review(
            id=100,
            user=sample_user,
            body="Please fix the tests",
            state="CHANGES_REQUESTED",
            html_url="https://github.com/owner/repo/pull/1#pullrequestreview-100",
            submitted_at=datetime(2025, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            commit_id="abc123",
        )
        # Second review: APPROVED (same reviewer)
        review2 = Review(
            id=101,
            user=sample_user,
            body="LGTM now",
            state="APPROVED",
            html_url="https://github.com/owner/repo/pull/1#pullrequestreview-101",
            submitted_at=datetime(2025, 1, 2, 14, 0, 0, tzinfo=timezone.utc),
            commit_id="def456",
        )

        formatted = MarkdownFormatter._format_reviews([review1, review2])
        assert "## Reviews" in formatted
        assert "CHANGES REQUESTED" in formatted
        assert "APPROVED" in formatted
        assert "🔴" in formatted  # CHANGES_REQUESTED emoji
        assert "✅" in formatted  # APPROVED emoji
        # Check for superseded note on first review
        assert "superseded by a later" in formatted
        assert "✅ **APPROVED** review" in formatted

    def test_format_reviews_multi_reviewers(self, sample_user: User) -> None:
        """Test review formatting with different reviewers (no progression)."""
        user2 = User(
            login="reviewer2",
            id=456,
            avatar_url="https://example.com/avatar2.jpg",
            html_url="https://github.com/reviewer2",
        )

        review1 = Review(
            id=200,
            user=sample_user,
            body="Please fix",
            state="CHANGES_REQUESTED",
            html_url="https://github.com/owner/repo/pull/1#pullrequestreview-200",
            submitted_at=datetime(2025, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            commit_id="abc123",
        )
        review2 = Review(
            id=201,
            user=user2,
            body="LGTM",
            state="APPROVED",
            html_url="https://github.com/owner/repo/pull/1#pullrequestreview-201",
            submitted_at=datetime(2025, 1, 2, 14, 0, 0, tzinfo=timezone.utc),
            commit_id="def456",
        )

        formatted = MarkdownFormatter._format_reviews([review1, review2])
        assert "## Reviews" in formatted
        # Should NOT have superseded note since different reviewers
        assert "superseded" not in formatted

    def test_format_reviews_three_from_same_reviewer(self, sample_user: User) -> None:
        """Test review formatting with three reviews from same reviewer."""
        review1 = Review(
            id=300,
            user=sample_user,
            body="Needs work",
            state="CHANGES_REQUESTED",
            html_url="https://github.com/owner/repo/pull/1#pullrequestreview-300",
            submitted_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            commit_id="abc123",
        )
        review2 = Review(
            id=301,
            user=sample_user,
            body="Better but still issues",
            state="COMMENTED",
            html_url="https://github.com/owner/repo/pull/1#pullrequestreview-301",
            submitted_at=datetime(2025, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            commit_id="def456",
        )
        review3 = Review(
            id=302,
            user=sample_user,
            body="Perfect!",
            state="APPROVED",
            html_url="https://github.com/owner/repo/pull/1#pullrequestreview-302",
            submitted_at=datetime(2025, 1, 3, 10, 0, 0, tzinfo=timezone.utc),
            commit_id="ghi789",
        )

        formatted = MarkdownFormatter._format_reviews([review1, review2, review3])
        # Both first and second reviews should be marked as superseded
        superseded_count = formatted.count("superseded by a later")
        assert superseded_count == 2
        # All three reviews should be present
        assert "Needs work" in formatted
        assert "Better but still issues" in formatted
        assert "Perfect!" in formatted

    def test_format_review_comments(self, sample_review_comment: ReviewComment) -> None:
        """Test review comments formatting."""
        formatted = MarkdownFormatter._format_review_comments([sample_review_comment])
        assert "## Review Comments" in formatted
        assert "File: `src/file.py`" in formatted
        assert "This needs improvement" in formatted
        assert "```diff" in formatted

    def test_format_review_comments_empty(self) -> None:
        """Test review comments formatting when empty."""
        formatted = MarkdownFormatter._format_review_comments([])
        assert "*No review comments on code.*" in formatted

    def test_format_review_comments_with_new_fields(self, sample_user: User) -> None:
        """Test review comments formatting with new optional fields."""
        review_comment = ReviewComment(
            id=999,
            user=sample_user,
            body="This needs improvement",
            path="src/file.py",
            position=10,
            original_position=10,
            commit_id="abc123",
            original_commit_id="abc123",
            diff_hunk="@@ -1,3 +1,3 @@\n line1\n-line2\n+line2_modified",
            created_at=datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
            html_url="https://github.com/owner/repo/pull/1#discussion_r999",
            in_reply_to_id=None,
            subject_type="line",
            start_line=5,
            line=10,
            start_side="RIGHT",
            side="RIGHT",
        )
        formatted = MarkdownFormatter._format_review_comments([review_comment])
        assert "## Review Comments" in formatted
        assert "File: `src/file.py`" in formatted
        assert "This needs improvement" in formatted

    def test_format_review_comments_in_reply_to(self, sample_user: User) -> None:
        """Test review comment reply formatting."""
        review_comment = ReviewComment(
            id=1000,
            user=sample_user,
            body="Reply text",
            path="src/file.py",
            position=10,
            original_position=10,
            commit_id="abc123",
            original_commit_id="abc123",
            diff_hunk="@@ -1 +1 @@",
            created_at=datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
            html_url="https://github.com/owner/repo/pull/1#discussion_r1000",
            in_reply_to_id=999,
        )
        formatted = MarkdownFormatter._format_review_comments([review_comment])
        assert "in reply to comment #999" in formatted

    def test_format_header_closed_not_merged(self, sample_pr: PullRequest) -> None:
        """Test PR header when closed but not merged."""
        sample_pr.state = "closed"
        sample_pr.closed_at = datetime(2025, 1, 3, 12, 0, 0, tzinfo=timezone.utc)
        sample_pr.merged_at = None
        header = MarkdownFormatter._format_header(sample_pr)
        assert "**Status:** CLOSED" in header
        assert "**Closed:**" in header
        assert "**Merged:**" not in header

    def test_format_reviews_with_null_submitted_at(self, sample_user: User) -> None:
        """Test review sorting when submitted_at is None."""
        reviews = [
            Review(
                id=1,
                user=sample_user,
                body="Pending",
                state="PENDING",
                html_url="https://example.com/review/1",
                submitted_at=None,
                commit_id="abc",
            ),
            Review(
                id=2,
                user=sample_user,
                body="Approved",
                state="APPROVED",
                html_url="https://example.com/review/2",
                submitted_at=datetime(2025, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
                commit_id="abc",
            ),
        ]
        formatted = MarkdownFormatter._format_reviews(reviews)
        assert "Approved" in formatted
        assert "Pending" in formatted

    def test_format_reference_download_summary(
        self,
    ) -> None:
        """Test reference download summary formatting."""
        ref = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=42)
        summary = MarkdownFormatter.format_reference_download_summary(
            [(ref, "not found")]
        )
        assert "## Reference Download Summary" in summary
        assert "owner/repo#42" in summary
        assert "not found" in summary
        assert MarkdownFormatter.format_reference_download_summary([]) == ""

    def test_format_reference_download_summary_depth_skipped(self) -> None:
        """Test depth-limited reference summary formatting."""
        ref = GitHubReference(ref_type="issue", owner="owner", repo="repo", number=7)
        summary = MarkdownFormatter.format_reference_download_summary(
            [],
            depth_skipped=[(ref, "Exceeded reference depth limit (--depth 1)")],
        )
        assert "skipped" in summary.lower()
        assert "depth limit" in summary.lower()
        assert "owner/repo#7" in summary

    def test_format_issue_closed_at_overrides_open_status(self) -> None:
        """Test issue header shows CLOSED when closed_at is set."""
        from datetime import datetime, timezone

        from pr2md.models import Issue, User

        issue = Issue(
            number=1,
            title="Open but closed",
            body=None,
            state="open",
            user=User(
                login="user",
                id=1,
                avatar_url="https://example.com/a",
                html_url="https://github.com/user",
            ),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            closed_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
            html_url="https://github.com/o/r/issues/1",
            labels=[],
        )
        header = MarkdownFormatter._format_issue_header(issue)
        assert "**Status:** CLOSED" in header

    def test_format_pr_complete(
        self,
        sample_pr: PullRequest,
        sample_comment: Comment,
        sample_review: Review,
        sample_review_comment: ReviewComment,
    ) -> None:
        """Test complete PR formatting."""
        diff = "diff content"
        markdown = MarkdownFormatter.format_pr(
            sample_pr, [sample_comment], [sample_review], [sample_review_comment], diff
        )

        assert "# Test Pull Request" in markdown
        assert "## Description" in markdown
        assert "## Changes Summary" in markdown
        assert "## Code Diff" in markdown
        assert "## Conversation Thread" in markdown
        assert "## Reviews" in markdown
        assert "## Review Comments" in markdown


class TestMarkdownFormatterHypothesis:
    """Hypothesis tests for MarkdownFormatter."""

    @given(
        title=st.text(min_size=1, max_size=200).filter(lambda x: x.strip()),
        body=st.one_of(st.none(), st.text(max_size=1000)),
        pr_number=st.integers(min_value=1, max_value=100000),
    )
    @settings(max_examples=50, deadline=2000)
    def test_format_header_always_includes_title(
        self, title: str, body: str | None, pr_number: int
    ) -> None:
        """Test that header formatting always includes the PR title."""
        pull_request = PullRequest(
            number=pr_number,
            title=title,
            body=body,
            state="open",
            user=User(
                login="test",
                id=123,
                avatar_url="https://example.com/avatar.jpg",
                html_url="https://github.com/test",
            ),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            closed_at=None,
            merged_at=None,
            merge_commit_sha=None,
            html_url="https://github.com/owner/repo/pull/1",
            labels=[],
            additions=10,
            deletions=5,
            changed_files=2,
            head_ref="feature",
            base_ref="main",
            head_sha="a" * 40,
            base_sha="b" * 40,
        )
        header = MarkdownFormatter._format_header(pull_request)
        assert f"# {title}" in header
        assert f"**PR Number:** #{pr_number}" in header

    @given(
        state=st.sampled_from(["open", "closed"]),
        merged_at=st.one_of(
            st.none(), st.just(datetime(2025, 1, 2, tzinfo=timezone.utc))
        ),
    )
    @settings(max_examples=20, deadline=2000)
    def test_format_header_status_correct(
        self, state: str, merged_at: datetime | None
    ) -> None:
        """Test that header status is correctly determined."""
        pull_request = PullRequest(
            number=1,
            title="Test",
            body=None,
            state=state,
            user=User(
                login="test",
                id=123,
                avatar_url="https://example.com/avatar.jpg",
                html_url="https://github.com/test",
            ),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            closed_at=None,
            merged_at=merged_at,
            merge_commit_sha=None,
            html_url="https://github.com/owner/repo/pull/1",
            labels=[],
            additions=10,
            deletions=5,
            changed_files=2,
            head_ref="feature",
            base_ref="main",
            head_sha="a" * 40,
            base_sha="b" * 40,
        )
        header = MarkdownFormatter._format_header(pull_request)
        if merged_at:
            assert "**Status:** MERGED" in header
        else:
            assert f"**Status:** {state.upper()}" in header

    @given(
        body=st.text(min_size=0, max_size=5000),
    )
    @settings(max_examples=50, deadline=2000)
    def test_format_description_preserves_body(self, body: str) -> None:
        """Test that description formatting preserves PR body content."""
        pull_request = PullRequest(
            number=1,
            title="Test",
            body=body if body else None,
            state="open",
            user=User(
                login="test",
                id=123,
                avatar_url="https://example.com/avatar.jpg",
                html_url="https://github.com/test",
            ),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            closed_at=None,
            merged_at=None,
            merge_commit_sha=None,
            html_url="https://github.com/owner/repo/pull/1",
            labels=[],
            additions=10,
            deletions=5,
            changed_files=2,
            head_ref="feature",
            base_ref="main",
            head_sha="a" * 40,
            base_sha="b" * 40,
        )
        description = MarkdownFormatter._format_description(pull_request)
        assert "## Description" in description
        if body:
            assert body in description
        else:
            assert "*No description provided.*" in description

    @given(
        additions=st.integers(min_value=0, max_value=100000),
        deletions=st.integers(min_value=0, max_value=100000),
        changed_files=st.integers(min_value=0, max_value=1000),
    )
    @settings(max_examples=50, deadline=2000)
    def test_format_changes_summary_correct_numbers(
        self, additions: int, deletions: int, changed_files: int
    ) -> None:
        """Test that changes summary shows correct numbers."""
        pull_request = PullRequest(
            number=1,
            title="Test",
            body=None,
            state="open",
            user=User(
                login="test",
                id=123,
                avatar_url="https://example.com/avatar.jpg",
                html_url="https://github.com/test",
            ),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            closed_at=None,
            merged_at=None,
            merge_commit_sha=None,
            html_url="https://github.com/owner/repo/pull/1",
            labels=[],
            additions=additions,
            deletions=deletions,
            changed_files=changed_files,
            head_ref="feature",
            base_ref="main",
            head_sha="a" * 40,
            base_sha="b" * 40,
        )
        summary = MarkdownFormatter._format_changes_summary(pull_request)
        assert f"**Files changed:** {changed_files}" in summary
        assert f"**Additions:** +{additions}" in summary
        assert f"**Deletions:** -{deletions}" in summary

    @given(
        diff=st.text(min_size=0, max_size=2000),
    )
    @settings(max_examples=50, deadline=2000)
    def test_format_diff_preserves_content(self, diff: str) -> None:
        """Test that diff formatting preserves diff content."""
        formatted = MarkdownFormatter._format_diff(diff)
        assert "## Code Diff" in formatted
        if diff:
            assert diff in formatted
            assert "```diff" in formatted
        else:
            assert "*No diff available.*" in formatted

    @given(
        comments=st.lists(
            st.fixed_dictionaries(
                {
                    "body": st.text(min_size=1, max_size=500),
                    "created_at": st.datetimes(
                        min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)
                    ).map(lambda dt: dt.replace(tzinfo=timezone.utc)),
                }
            ),
            min_size=0,
            max_size=10,
        )
    )
    @settings(max_examples=30, deadline=3000)
    def test_format_conversation_ordering(
        self, comments: list[dict[str, str | datetime]]
    ) -> None:
        """Test that conversation comments are ordered by creation time."""
        comment_objects = [
            Comment(
                id=i,
                user=User(
                    login="test",
                    id=123,
                    avatar_url="https://example.com/avatar.jpg",
                    html_url="https://github.com/test",
                ),
                body=str(c["body"]),
                created_at=c["created_at"],
                updated_at=c["created_at"],
                html_url=f"https://github.com/owner/repo/issues/1#issuecomment-{i}",
            )
            for i, c in enumerate(comments)
        ]
        formatted = MarkdownFormatter._format_conversation(comment_objects)
        assert "## Conversation Thread" in formatted
        if not comment_objects:
            assert "*No comments in the conversation thread.*" in formatted
            return

        sorted_comments = sorted(comment_objects, key=lambda c: c.created_at)
        positions = [
            formatted.index(comment.user.login)
            for comment in sorted_comments
            if comment.user.login in formatted
        ]
        assert positions == sorted(positions)

    @given(
        review_state=st.sampled_from(
            ["APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"]
        ),
        body=st.one_of(st.none(), st.text(min_size=1, max_size=500)),
    )
    @settings(max_examples=30, deadline=2000)
    def test_format_reviews_includes_state(
        self, review_state: str, body: str | None
    ) -> None:
        """Test that review formatting includes the review state."""
        review = Review(
            id=123,
            user=User(
                login="test",
                id=456,
                avatar_url="https://example.com/avatar.jpg",
                html_url="https://github.com/test",
            ),
            body=body,
            state=review_state,
            html_url="https://github.com/owner/repo/pull/1#pullrequestreview-123",
            submitted_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            commit_id="a" * 40,
        )
        formatted = MarkdownFormatter._format_reviews([review])
        assert "## Reviews" in formatted
        assert review_state.replace("_", " ") in formatted

    @given(
        file_paths=st.lists(
            st.from_regex(r"[\w/]+\.[\w]+", fullmatch=True),
            min_size=0,
            max_size=5,
            unique=True,
        )
    )
    @settings(max_examples=30, deadline=3000)
    def test_format_review_comments_groups_by_file(self, file_paths: list[str]) -> None:
        """Test that review comments are grouped by file path."""
        review_comments = [
            ReviewComment(
                id=i,
                user=User(
                    login="test",
                    id=123,
                    avatar_url="https://example.com/avatar.jpg",
                    html_url="https://github.com/test",
                ),
                body=f"Comment {i}",
                path=path,
                position=10,
                original_position=10,
                commit_id="a" * 40,
                original_commit_id="a" * 40,
                diff_hunk="@@ test @@",
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                html_url=f"https://github.com/owner/repo/pull/1#discussion_r{i}",
                in_reply_to_id=None,
            )
            for i, path in enumerate(file_paths)
        ]
        formatted = MarkdownFormatter._format_review_comments(review_comments)
        assert "## Review Comments" in formatted
        if not review_comments:
            assert "*No review comments on code.*" in formatted
        else:
            for path in file_paths:
                assert f"File: `{path}`" in formatted

    @given(
        text=st.text(
            alphabet=st.characters(blacklist_categories=("Cs", "Cc"), min_codepoint=32),
            min_size=0,
            max_size=500,
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_format_pr_produces_valid_markdown_structure(self, text: str) -> None:
        """Test that full PR formatting always produces expected structure."""
        pull_request = PullRequest(
            number=1,
            title=text[:100] if text else "Test",
            body=text,
            state="open",
            user=User(
                login="test",
                id=123,
                avatar_url="https://example.com/avatar.jpg",
                html_url="https://github.com/test",
            ),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            closed_at=None,
            merged_at=None,
            merge_commit_sha=None,
            html_url="https://github.com/owner/repo/pull/1",
            labels=[],
            additions=10,
            deletions=5,
            changed_files=2,
            head_ref="feature",
            base_ref="main",
            head_sha="a" * 40,
            base_sha="b" * 40,
        )
        markdown = MarkdownFormatter.format_pr(pull_request, [], [], [], "")
        # Check all major sections exist
        assert "## Description" in markdown
        assert "## Changes Summary" in markdown
        assert "## Code Diff" in markdown
        assert "## Conversation Thread" in markdown
        assert "## Reviews" in markdown
        assert "## Review Comments" in markdown
        # Markdown should be non-empty
        assert len(markdown) > 0


class TestIssueFormatting:
    """Tests for issue formatting."""

    @pytest.fixture
    def sample_issue(self, sample_user: User) -> Issue:
        """Create a sample issue."""
        return Issue(
            number=42,
            title="Test Issue",
            body="This is a test issue",
            state="open",
            user=sample_user,
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            closed_at=None,
            html_url="https://github.com/owner/repo/issues/42",
            labels=[Label("bug", "d73a4a", "Something isn't working")],
        )

    def test_format_issue_header(self, sample_issue: Issue) -> None:
        """Test issue header formatting."""
        header = MarkdownFormatter._format_issue_header(sample_issue)
        assert "# Test Issue" in header
        assert "**Issue Number:** #42" in header
        assert "**Status:** OPEN" in header
        assert "**Author:** [testuser]" in header
        assert "**Labels:** `bug`" in header

    def test_format_issue_header_closed(self, sample_issue: Issue) -> None:
        """Test issue header formatting for closed issue."""
        sample_issue.closed_at = datetime(2025, 1, 3, 12, 0, 0, tzinfo=timezone.utc)
        sample_issue.state = "closed"
        header = MarkdownFormatter._format_issue_header(sample_issue)
        assert "**Status:** CLOSED" in header
        assert "**Closed:**" in header

    def test_format_issue_description(self, sample_issue: Issue) -> None:
        """Test issue description formatting."""
        description = MarkdownFormatter._format_issue_description(sample_issue)
        assert "## Description" in description
        assert "This is a test issue" in description

    def test_format_issue_description_empty(self, sample_issue: Issue) -> None:
        """Test issue description formatting when empty."""
        sample_issue.body = None
        description = MarkdownFormatter._format_issue_description(sample_issue)
        assert "*No description provided.*" in description

    def test_format_issue_complete(
        self, sample_issue: Issue, sample_comment: Comment
    ) -> None:
        """Test complete issue formatting."""
        markdown = MarkdownFormatter.format_issue(sample_issue, [sample_comment])

        assert "# Test Issue" in markdown
        assert "## Description" in markdown
        assert "## Conversation Thread" in markdown
        assert "This is a comment" in markdown

    def test_format_issue_no_comments(self, sample_issue: Issue) -> None:
        """Test issue formatting with no comments."""
        markdown = MarkdownFormatter.format_issue(sample_issue, [])

        assert "# Test Issue" in markdown
        assert "*No comments in the conversation thread.*" in markdown
