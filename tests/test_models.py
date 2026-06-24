"""Tests for data models."""

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from pr2md.models import Comment, Issue, Label, PullRequest, Review, ReviewComment, User


class TestUser:
    """Tests for User model."""

    def test_from_dict(self) -> None:
        """Test User creation from dictionary."""
        data = {
            "login": "testuser",
            "id": 123,
            "avatar_url": "https://example.com/avatar.jpg",
            "html_url": "https://github.com/testuser",
        }
        user = User.from_dict(data)
        assert user.login == "testuser"
        assert user.id == 123
        assert user.avatar_url == "https://example.com/avatar.jpg"
        assert user.html_url == "https://github.com/testuser"


class TestLabel:
    """Tests for Label model."""

    def test_from_dict_with_description(self) -> None:
        """Test Label creation with description."""
        data = {
            "name": "bug",
            "color": "d73a4a",
            "description": "Something isn't working",
        }
        label = Label.from_dict(data)
        assert label.name == "bug"
        assert label.color == "d73a4a"
        assert label.description == "Something isn't working"

    def test_from_dict_without_description(self) -> None:
        """Test Label creation without description."""
        data = {"name": "enhancement", "color": "a2eeef", "description": None}
        label = Label.from_dict(data)
        assert label.name == "enhancement"
        assert label.color == "a2eeef"
        assert label.description is None


class TestComment:
    """Tests for Comment model."""

    def test_from_dict(self) -> None:
        """Test Comment creation from dictionary."""
        data = {
            "id": 456,
            "user": {
                "login": "commenter",
                "id": 789,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/commenter",
            },
            "body": "This is a comment",
            "created_at": "2025-01-01T12:00:00Z",
            "updated_at": "2025-01-01T12:30:00Z",
            "html_url": "https://github.com/owner/repo/issues/1#issuecomment-456",
        }
        comment = Comment.from_dict(data)
        assert comment.id == 456
        assert comment.user.login == "commenter"
        assert comment.body == "This is a comment"
        assert isinstance(comment.created_at, datetime)
        assert isinstance(comment.updated_at, datetime)

    def test_from_dict_null_body(self) -> None:
        """Test Comment creation when body is null."""
        data = {
            "id": 456,
            "user": {
                "login": "commenter",
                "id": 789,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/commenter",
            },
            "body": None,
            "created_at": "2025-01-01T12:00:00Z",
            "updated_at": "2025-01-01T12:30:00Z",
            "html_url": "https://github.com/owner/repo/issues/1#issuecomment-456",
        }
        comment = Comment.from_dict(data)
        assert comment.body == ""


class TestIssue:
    """Tests for Issue model."""

    def test_from_dict(self) -> None:
        """Test Issue creation from dictionary."""
        data = {
            "number": 42,
            "title": "Bug report",
            "body": "Steps to reproduce",
            "state": "open",
            "user": {
                "login": "reporter",
                "id": 1,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/reporter",
            },
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
            "closed_at": None,
            "html_url": "https://github.com/owner/repo/issues/42",
            "labels": [],
        }
        issue = Issue.from_dict(data)
        assert issue.number == 42
        assert issue.title == "Bug report"
        assert issue.body == "Steps to reproduce"
        assert issue.closed_at is None

    def test_from_dict_closed_with_labels(self) -> None:
        """Test closed Issue with labels."""
        data = {
            "number": 7,
            "title": "Closed issue",
            "body": None,
            "state": "closed",
            "user": {
                "login": "reporter",
                "id": 1,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/reporter",
            },
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
            "closed_at": "2025-01-03T00:00:00Z",
            "html_url": "https://github.com/owner/repo/issues/7",
            "labels": [
                {"name": "bug", "color": "d73a4a", "description": "Bug"},
            ],
        }
        issue = Issue.from_dict(data)
        assert issue.state == "closed"
        assert issue.body is None
        assert issue.closed_at is not None
        assert issue.labels[0].name == "bug"


class TestReviewComment:
    """Tests for ReviewComment model."""

    def test_from_dict(self) -> None:
        """Test ReviewComment creation from dictionary."""
        data = {
            "id": 789,
            "user": {
                "login": "reviewer",
                "id": 111,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/reviewer",
            },
            "body": "This needs improvement",
            "path": "file.py",
            "position": 10,
            "original_position": 10,
            "commit_id": "abc123",
            "original_commit_id": "abc123",
            "diff_hunk": "@@ -1,3 +1,3 @@\n line1\n-line2\n+line2_modified",
            "created_at": "2025-01-01T13:00:00Z",
            "updated_at": "2025-01-01T13:00:00Z",
            "html_url": "https://github.com/owner/repo/pull/1#discussion_r789",
            "in_reply_to_id": None,
        }
        review_comment = ReviewComment.from_dict(data)
        assert review_comment.id == 789
        assert review_comment.user.login == "reviewer"
        assert review_comment.path == "file.py"
        assert review_comment.position == 10
        assert review_comment.in_reply_to_id is None

    def test_from_dict_with_reply(self) -> None:
        """Test ReviewComment creation with reply reference."""
        data = {
            "id": 790,
            "user": {
                "login": "reviewer",
                "id": 111,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/reviewer",
            },
            "body": "Reply to previous comment",
            "path": "file.py",
            "position": None,
            "original_position": 10,
            "commit_id": "abc123",
            "original_commit_id": "abc123",
            "diff_hunk": "@@ -1,3 +1,3 @@\n line1\n-line2\n+line2_modified",
            "created_at": "2025-01-01T13:30:00Z",
            "updated_at": "2025-01-01T13:30:00Z",
            "html_url": "https://github.com/owner/repo/pull/1#discussion_r790",
            "in_reply_to_id": 789,
        }
        review_comment = ReviewComment.from_dict(data)
        assert review_comment.in_reply_to_id == 789
        assert review_comment.position is None

    def test_from_dict_with_optional_fields(self) -> None:
        """Test ReviewComment creation with new optional fields."""
        data = {
            "id": 791,
            "user": {
                "login": "reviewer",
                "id": 111,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/reviewer",
            },
            "body": "Comment with optional fields",
            "path": "file.py",
            "position": 15,
            "original_position": 15,
            "commit_id": "abc123",
            "original_commit_id": "abc123",
            "diff_hunk": "@@ -1,3 +1,3 @@\n line1\n-line2\n+line2_modified",
            "created_at": "2025-01-01T13:45:00Z",
            "updated_at": "2025-01-01T13:45:00Z",
            "html_url": "https://github.com/owner/repo/pull/1#discussion_r791",
            "in_reply_to_id": None,
            "subject_type": "line",
            "start_line": 10,
            "line": 15,
            "start_side": "RIGHT",
            "side": "RIGHT",
        }
        review_comment = ReviewComment.from_dict(data)
        assert review_comment.subject_type == "line"
        assert review_comment.start_line == 10
        assert review_comment.line == 15
        assert review_comment.start_side == "RIGHT"
        assert review_comment.side == "RIGHT"

    def test_from_dict_without_optional_fields(self) -> None:
        """Test ReviewComment creation without new optional fields."""
        data = {
            "id": 792,
            "user": {
                "login": "reviewer",
                "id": 111,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/reviewer",
            },
            "body": "Comment without optional fields",
            "path": "file.py",
            "position": 20,
            "original_position": 20,
            "commit_id": "abc123",
            "original_commit_id": "abc123",
            "diff_hunk": "@@ -1,3 +1,3 @@\n line1\n-line2\n+line2_modified",
            "created_at": "2025-01-01T14:00:00Z",
            "updated_at": "2025-01-01T14:00:00Z",
            "html_url": "https://github.com/owner/repo/pull/1#discussion_r792",
            "in_reply_to_id": None,
        }
        review_comment = ReviewComment.from_dict(data)
        # Optional fields should default to None
        assert review_comment.subject_type is None
        assert review_comment.start_line is None
        assert review_comment.line is None
        assert review_comment.start_side is None
        assert review_comment.side is None


class TestReview:
    """Tests for Review model."""

    def test_from_dict(self) -> None:
        """Test Review creation from dictionary."""
        data = {
            "id": 999,
            "user": {
                "login": "approver",
                "id": 222,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/approver",
            },
            "body": "Looks good to me",
            "state": "APPROVED",
            "html_url": "https://github.com/owner/repo/pull/1#pullrequestreview-999",
            "submitted_at": "2025-01-02T10:00:00Z",
            "commit_id": "def456",
        }
        review = Review.from_dict(data)
        assert review.id == 999
        assert review.user.login == "approver"
        assert review.state == "APPROVED"
        assert review.body == "Looks good to me"
        assert isinstance(review.submitted_at, datetime)

    def test_from_dict_without_body(self) -> None:
        """Test Review creation without body."""
        data = {
            "id": 1000,
            "user": {
                "login": "reviewer",
                "id": 333,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/reviewer",
            },
            "body": None,
            "state": "COMMENTED",
            "html_url": "https://github.com/owner/repo/pull/1#pullrequestreview-1000",
            "submitted_at": "2025-01-02T11:00:00Z",
            "commit_id": "def456",
        }
        review = Review.from_dict(data)
        assert review.body is None


class TestPullRequest:
    """Tests for PullRequest model."""

    def test_from_dict(self) -> None:
        """Test PullRequest creation from dictionary."""
        data = {
            "number": 1,
            "title": "Test PR",
            "body": "This is a test pull request",
            "state": "open",
            "user": {
                "login": "author",
                "id": 444,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/author",
            },
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
            "closed_at": None,
            "merged_at": None,
            "merge_commit_sha": None,
            "html_url": "https://github.com/owner/repo/pull/1",
            "labels": [
                {
                    "name": "bug",
                    "color": "d73a4a",
                    "description": "Something isn't working",
                }
            ],
            "additions": 10,
            "deletions": 5,
            "changed_files": 2,
            "head": {"ref": "feature-branch", "sha": "abc123def456"},
            "base": {"ref": "main", "sha": "def456abc123"},
        }
        pull_request = PullRequest.from_dict(data)
        assert pull_request.number == 1
        assert pull_request.title == "Test PR"
        assert pull_request.state == "open"
        assert pull_request.additions == 10
        assert pull_request.deletions == 5
        assert pull_request.changed_files == 2
        assert pull_request.head_ref == "feature-branch"
        assert pull_request.base_ref == "main"
        assert len(pull_request.labels) == 1

    def test_from_dict_merged(self) -> None:
        """Test PullRequest creation for merged PR."""
        data = {
            "number": 2,
            "title": "Merged PR",
            "body": None,
            "state": "closed",
            "user": {
                "login": "author",
                "id": 444,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/author",
            },
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
            "closed_at": "2025-01-02T00:00:00Z",
            "merged_at": "2025-01-02T00:00:00Z",
            "merge_commit_sha": "merged123",
            "html_url": "https://github.com/owner/repo/pull/2",
            "labels": [],
            "additions": 20,
            "deletions": 10,
            "changed_files": 3,
            "head": {"ref": "feature", "sha": "abc123"},
            "base": {"ref": "main", "sha": "def456"},
        }
        pull_request = PullRequest.from_dict(data)
        assert pull_request.state == "closed"
        assert pull_request.merged_at is not None
        assert pull_request.merge_commit_sha == "merged123"
        assert pull_request.body is None


# Hypothesis Strategies
def user_dict_strategy() -> st.SearchStrategy[dict[str, object]]:
    """Strategy for generating valid user dictionaries."""
    return st.fixed_dictionaries(
        {
            "login": st.text(min_size=1, max_size=39).filter(
                lambda x: x.strip() and not x.isspace()
            ),
            "id": st.integers(min_value=1, max_value=2**31 - 1),
            "avatar_url": st.from_regex(
                r"https://[a-z0-9.-]+\.[a-z]{2,}/[\w/.-]+", fullmatch=True
            ),
            "html_url": st.from_regex(r"https://github\.com/[\w-]+", fullmatch=True),
        }
    )


def iso_datetime_strategy() -> st.SearchStrategy[str]:
    """Strategy for generating valid ISO datetime strings."""
    return st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2030, 12, 31),
    ).map(lambda dt: dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"))


def label_dict_strategy() -> st.SearchStrategy[dict[str, object]]:
    """Strategy for generating valid label dictionaries."""
    return st.fixed_dictionaries(
        {
            "name": st.text(min_size=1, max_size=50).filter(
                lambda x: x.strip() and not x.isspace()
            ),
            "color": st.from_regex(r"[0-9a-fA-F]{6}", fullmatch=True),
            "description": st.one_of(
                st.none(),
                st.text(max_size=200),
            ),
        }
    )


def comment_dict_strategy() -> st.SearchStrategy[dict[str, object]]:
    """Strategy for generating valid comment dictionaries."""
    return st.fixed_dictionaries(
        {
            "id": st.integers(min_value=1, max_value=2**31 - 1),
            "user": user_dict_strategy(),
            "body": st.text(min_size=0, max_size=1000),
            "created_at": iso_datetime_strategy(),
            "updated_at": iso_datetime_strategy(),
            "html_url": st.from_regex(
                r"https://github\.com/[\w-]+/[\w-]+/issues/\d+#issuecomment-\d+",
                fullmatch=True,
            ),
        }
    )


def review_comment_dict_strategy() -> st.SearchStrategy[dict[str, object]]:
    """Strategy for generating valid review comment dictionaries."""
    return st.fixed_dictionaries(
        {
            "id": st.integers(min_value=1, max_value=2**31 - 1),
            "user": user_dict_strategy(),
            "body": st.text(min_size=0, max_size=1000),
            "path": st.from_regex(r"[\w/.-]+\.[\w]+", fullmatch=True),
            "position": st.one_of(st.none(), st.integers(min_value=1, max_value=10000)),
            "original_position": st.one_of(
                st.none(), st.integers(min_value=1, max_value=10000)
            ),
            "commit_id": st.from_regex(r"[0-9a-f]{40}", fullmatch=True),
            "original_commit_id": st.from_regex(r"[0-9a-f]{40}", fullmatch=True),
            "diff_hunk": st.text(min_size=1, max_size=500),
            "created_at": iso_datetime_strategy(),
            "updated_at": iso_datetime_strategy(),
            "html_url": st.from_regex(
                r"https://github\.com/[\w-]+/[\w-]+/pull/\d+#discussion_r\d+",
                fullmatch=True,
            ),
            "in_reply_to_id": st.one_of(
                st.none(), st.integers(min_value=1, max_value=2**31 - 1)
            ),
        }
    )


def review_dict_strategy() -> st.SearchStrategy[dict[str, object]]:
    """Strategy for generating valid review dictionaries."""
    return st.fixed_dictionaries(
        {
            "id": st.integers(min_value=1, max_value=2**31 - 1),
            "user": user_dict_strategy(),
            "body": st.one_of(st.none(), st.text(max_size=1000)),
            "state": st.sampled_from(
                ["APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"]
            ),
            "html_url": st.from_regex(
                r"https://github\.com/[\w-]+/[\w-]+/pull/\d+#pullrequestreview-\d+",
                fullmatch=True,
            ),
            "submitted_at": st.one_of(st.none(), iso_datetime_strategy()),
            "commit_id": st.from_regex(r"[0-9a-f]{40}", fullmatch=True),
        }
    )


def pull_request_dict_strategy() -> st.SearchStrategy[dict[str, object]]:
    """Strategy for generating valid pull request dictionaries."""
    return st.fixed_dictionaries(
        {
            "number": st.integers(min_value=1, max_value=100000),
            "title": st.text(min_size=1, max_size=200).filter(
                lambda x: x.strip() and not x.isspace()
            ),
            "body": st.one_of(st.none(), st.text(max_size=5000)),
            "state": st.sampled_from(["open", "closed"]),
            "user": user_dict_strategy(),
            "created_at": iso_datetime_strategy(),
            "updated_at": iso_datetime_strategy(),
            "closed_at": st.one_of(st.none(), iso_datetime_strategy()),
            "merged_at": st.one_of(st.none(), iso_datetime_strategy()),
            "merge_commit_sha": st.one_of(
                st.none(), st.from_regex(r"[0-9a-f]{40}", fullmatch=True)
            ),
            "html_url": st.from_regex(
                r"https://github\.com/[\w-]+/[\w-]+/pull/\d+", fullmatch=True
            ),
            "labels": st.lists(label_dict_strategy(), max_size=10),
            "additions": st.integers(min_value=0, max_value=100000),
            "deletions": st.integers(min_value=0, max_value=100000),
            "changed_files": st.integers(min_value=0, max_value=1000),
            "head": st.fixed_dictionaries(
                {
                    "ref": st.from_regex(r"[\w/-]+", fullmatch=True),
                    "sha": st.from_regex(r"[0-9a-f]{40}", fullmatch=True),
                }
            ),
            "base": st.fixed_dictionaries(
                {
                    "ref": st.from_regex(r"[\w/-]+", fullmatch=True),
                    "sha": st.from_regex(r"[0-9a-f]{40}", fullmatch=True),
                }
            ),
        }
    )


class TestUserHypothesis:
    """Hypothesis tests for User model."""

    @given(user_dict=user_dict_strategy())
    @settings(max_examples=50, deadline=1000)
    def test_user_from_dict_property(self, user_dict: dict[str, object]) -> None:
        """Test User.from_dict with property-based testing."""
        user = User.from_dict(user_dict)
        assert isinstance(user, User)
        assert user.login == str(user_dict["login"])
        assert user.id == int(user_dict["id"])  # type: ignore[call-overload]
        assert user.avatar_url == str(user_dict["avatar_url"])
        assert user.html_url == str(user_dict["html_url"])

    @given(
        login=st.text(min_size=1, max_size=39),
        user_id=st.integers(min_value=1, max_value=2**31 - 1),
    )
    @settings(max_examples=50, deadline=1000)
    def test_user_fields_are_strings_and_ints(self, login: str, user_id: int) -> None:
        """Test User fields maintain correct types."""
        user = User(
            login=login,
            id=user_id,
            avatar_url="https://example.com/avatar.jpg",
            html_url=f"https://github.com/{login}",
        )
        assert isinstance(user.login, str)
        assert isinstance(user.id, int)
        assert user.id == user_id


class TestLabelHypothesis:
    """Hypothesis tests for Label model."""

    @given(label_dict=label_dict_strategy())
    @settings(max_examples=50, deadline=1000)
    def test_label_from_dict_property(self, label_dict: dict[str, object]) -> None:
        """Test Label.from_dict with property-based testing."""
        label = Label.from_dict(label_dict)
        assert isinstance(label, Label)
        assert label.name == str(label_dict["name"])
        assert label.color == str(label_dict["color"])
        if label_dict["description"] is None or label_dict["description"] == "":
            assert label.description is None or label.description == ""
        else:
            assert label.description == str(label_dict["description"])

    @given(
        name=st.text(min_size=1, max_size=50),
        color=st.from_regex(r"[0-9a-fA-F]{6}", fullmatch=True),
    )
    @settings(max_examples=50, deadline=1000)
    def test_label_color_format(self, name: str, color: str) -> None:
        """Test Label accepts valid hex colors."""
        label = Label(name=name, color=color, description=None)
        assert len(label.color) == 6
        assert all(c in "0123456789abcdefABCDEF" for c in label.color)


class TestCommentHypothesis:
    """Hypothesis tests for Comment model."""

    @given(comment_dict=comment_dict_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_comment_from_dict_property(self, comment_dict: dict[str, object]) -> None:
        """Test Comment.from_dict with property-based testing."""
        comment = Comment.from_dict(comment_dict)
        assert isinstance(comment, Comment)
        assert comment.id == int(comment_dict["id"])  # type: ignore[call-overload]
        assert isinstance(comment.user, User)
        assert comment.body == str(comment_dict["body"])
        assert isinstance(comment.created_at, datetime)
        assert isinstance(comment.updated_at, datetime)
        assert comment.html_url == str(comment_dict["html_url"])

    @given(comment_dict=comment_dict_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_comment_datetime_parsing(self, comment_dict: dict[str, object]) -> None:
        """Test Comment correctly parses datetime strings."""
        comment = Comment.from_dict(comment_dict)
        # All datetimes should have timezone info
        assert comment.created_at.tzinfo is not None
        assert comment.updated_at.tzinfo is not None


class TestReviewCommentHypothesis:
    """Hypothesis tests for ReviewComment model."""

    @given(review_comment_dict=review_comment_dict_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_review_comment_from_dict_property(
        self, review_comment_dict: dict[str, object]
    ) -> None:
        """Test ReviewComment.from_dict with property-based testing."""
        review_comment = ReviewComment.from_dict(review_comment_dict)
        assert isinstance(review_comment, ReviewComment)
        rc_id: object = review_comment_dict["id"]
        assert review_comment.id == int(rc_id)  # type: ignore[call-overload]
        assert isinstance(review_comment.user, User)
        assert review_comment.body == str(review_comment_dict["body"])
        assert review_comment.path == str(review_comment_dict["path"])

    @given(review_comment_dict=review_comment_dict_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_review_comment_optional_fields(
        self, review_comment_dict: dict[str, object]
    ) -> None:
        """Test ReviewComment handles optional fields correctly."""
        review_comment = ReviewComment.from_dict(review_comment_dict)
        # Position can be None
        if review_comment_dict["position"] is None:
            assert review_comment.position is None
        else:
            assert review_comment.position == int(
                review_comment_dict["position"]  # type: ignore[call-overload]
            )
        # in_reply_to_id can be None
        if review_comment_dict["in_reply_to_id"] is None:
            assert review_comment.in_reply_to_id is None
        else:
            assert review_comment.in_reply_to_id == int(
                review_comment_dict["in_reply_to_id"]  # type: ignore[call-overload]
            )


class TestReviewHypothesis:
    """Hypothesis tests for Review model."""

    @given(review_dict=review_dict_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_review_from_dict_property(self, review_dict: dict[str, object]) -> None:
        """Test Review.from_dict with property-based testing."""
        review = Review.from_dict(review_dict)
        assert isinstance(review, Review)
        assert review.id == int(review_dict["id"])  # type: ignore[call-overload]
        assert isinstance(review.user, User)
        assert review.state == str(review_dict["state"])

    @given(review_dict=review_dict_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_review_optional_fields(self, review_dict: dict[str, object]) -> None:
        """Test Review handles optional fields correctly."""
        review = Review.from_dict(review_dict)
        # Body can be None
        if review_dict["body"] is None:
            assert review.body is None
        else:
            assert review.body == str(review_dict["body"])
        # submitted_at can be None
        if review_dict["submitted_at"] is None:
            assert review.submitted_at is None
        else:
            assert isinstance(review.submitted_at, datetime)

    @given(
        state=st.sampled_from(
            ["APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"]
        )
    )
    @settings(max_examples=20, deadline=1000)
    def test_review_valid_states(self, state: str) -> None:
        """Test Review accepts all valid states."""
        review_dict = {
            "id": 123,
            "user": {
                "login": "test",
                "id": 456,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/test",
            },
            "body": "Test",
            "state": state,
            "html_url": "https://github.com/owner/repo/pull/1#pullrequestreview-123",
            "submitted_at": "2025-01-01T00:00:00Z",
            "commit_id": "0" * 40,
        }
        review = Review.from_dict(review_dict)
        assert review.state == state


class TestPullRequestHypothesis:
    """Hypothesis tests for PullRequest model."""

    @given(pr_dict=pull_request_dict_strategy())
    @settings(max_examples=10, deadline=5000)
    def test_pull_request_from_dict_property(self, pr_dict: dict[str, object]) -> None:
        """Test PullRequest.from_dict with property-based testing."""
        pull_request = PullRequest.from_dict(pr_dict)
        assert isinstance(pull_request, PullRequest)
        pr_number: object = pr_dict["number"]
        assert pull_request.number == int(pr_number)  # type: ignore[call-overload]
        assert pull_request.title == str(pr_dict["title"])
        assert pull_request.state == str(pr_dict["state"])
        assert isinstance(pull_request.user, User)
        assert isinstance(pull_request.labels, list)

    @given(pr_dict=pull_request_dict_strategy())
    @settings(max_examples=10, deadline=5000)
    def test_pull_request_statistics_non_negative(
        self, pr_dict: dict[str, object]
    ) -> None:
        """Test PullRequest statistics are always non-negative."""
        pull_request = PullRequest.from_dict(pr_dict)
        assert pull_request.additions >= 0
        assert pull_request.deletions >= 0
        assert pull_request.changed_files >= 0

    @given(pr_dict=pull_request_dict_strategy())
    @settings(max_examples=10, deadline=5000)
    def test_pull_request_optional_fields(self, pr_dict: dict[str, object]) -> None:
        """Test PullRequest handles optional fields correctly."""
        pull_request = PullRequest.from_dict(pr_dict)
        # body can be None or empty string becomes None
        if pr_dict["body"] is None or pr_dict["body"] == "":
            assert pull_request.body is None or pull_request.body == ""
        else:
            assert pull_request.body == str(pr_dict["body"])
        # closed_at can be None
        if pr_dict["closed_at"] is None:
            assert pull_request.closed_at is None
        else:
            assert isinstance(pull_request.closed_at, datetime)
        # merged_at can be None
        if pr_dict["merged_at"] is None:
            assert pull_request.merged_at is None
        else:
            assert isinstance(pull_request.merged_at, datetime)

    @given(
        labels=st.lists(label_dict_strategy(), min_size=0, max_size=20),
    )
    @settings(max_examples=20, deadline=2000)
    def test_pull_request_labels_list(self, labels: list[dict[str, object]]) -> None:
        """Test PullRequest correctly processes label lists."""
        pr_dict = {
            "number": 1,
            "title": "Test",
            "body": None,
            "state": "open",
            "user": {
                "login": "test",
                "id": 123,
                "avatar_url": "https://example.com/avatar.jpg",
                "html_url": "https://github.com/test",
            },
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "closed_at": None,
            "merged_at": None,
            "merge_commit_sha": None,
            "html_url": "https://github.com/owner/repo/pull/1",
            "labels": labels,
            "additions": 10,
            "deletions": 5,
            "changed_files": 2,
            "head": {"ref": "feature", "sha": "a" * 40},
            "base": {"ref": "main", "sha": "b" * 40},
        }
        pull_request = PullRequest.from_dict(pr_dict)
        assert len(pull_request.labels) == len(labels)
        assert all(isinstance(label, Label) for label in pull_request.labels)
