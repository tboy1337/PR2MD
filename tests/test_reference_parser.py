"""Tests for reference parser."""

import pytest

from pr2md.reference_parser import GitHubReference, ReferenceParser


class TestGitHubReference:
    """Tests for GitHubReference dataclass."""

    def test_create_reference(self) -> None:
        """Test creating a GitHubReference."""
        ref = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=123)
        assert ref.ref_type == "pr"
        assert ref.owner == "owner"
        assert ref.repo == "repo"
        assert ref.number == 123

    def test_reference_is_hashable(self) -> None:
        """Test that references can be used in sets."""
        ref1 = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=123)
        ref2 = GitHubReference(ref_type="pr", owner="owner", repo="repo", number=123)
        ref3 = GitHubReference(ref_type="issue", owner="owner", repo="repo", number=123)

        refs = {ref1, ref2, ref3}
        assert len(refs) == 2  # ref1 and ref2 are the same


class TestReferenceParser:
    """Tests for ReferenceParser class."""

    @pytest.fixture
    def parser(self) -> ReferenceParser:
        """Create a reference parser."""
        return ReferenceParser("testowner", "testrepo")

    def test_parse_same_repo_reference(self, parser: ReferenceParser) -> None:
        """Test parsing same-repository references."""
        text = "This fixes #123 and relates to #456"
        refs = parser.parse_references(text)

        assert len(refs) == 2
        numbers = {ref.number for ref in refs}
        assert 123 in numbers
        assert 456 in numbers

        for ref in refs:
            assert ref.owner == "testowner"
            assert ref.repo == "testrepo"
            assert ref.ref_type == "pr"

    def test_parse_cross_repo_reference(self, parser: ReferenceParser) -> None:
        """Test parsing cross-repository references."""
        text = "Related to microsoft/vscode#12345"
        refs = parser.parse_references(text)

        assert len(refs) == 1
        ref = list(refs)[0]
        assert ref.owner == "microsoft"
        assert ref.repo == "vscode"
        assert ref.number == 12345
        assert ref.ref_type == "pr"

    def test_parse_url_pr_reference(self, parser: ReferenceParser) -> None:
        """Test parsing full URL PR references."""
        text = "See https://github.com/owner/repo/pull/789"
        refs = parser.parse_references(text)

        assert len(refs) == 1
        ref = list(refs)[0]
        assert ref.ref_type == "pr"
        assert ref.owner == "owner"
        assert ref.repo == "repo"
        assert ref.number == 789

    def test_parse_url_issue_reference(self, parser: ReferenceParser) -> None:
        """Test parsing full URL issue references."""
        text = "Bug report: https://github.com/python/cpython/issues/54321"
        refs = parser.parse_references(text)

        assert len(refs) == 1
        ref = list(refs)[0]
        assert ref.ref_type == "issue"
        assert ref.owner == "python"
        assert ref.repo == "cpython"
        assert ref.number == 54321

    def test_parse_multiple_formats(self, parser: ReferenceParser) -> None:
        """Test parsing multiple reference formats in one text."""
        text = """
        This PR fixes #100 and relates to owner/repo#200.
        Also see https://github.com/other/project/pull/300
        and https://github.com/other/project/issues/400
        """
        refs = parser.parse_references(text)

        assert len(refs) == 4
        numbers = {ref.number for ref in refs}
        assert numbers == {100, 200, 300, 400}

    def test_parse_with_punctuation(self, parser: ReferenceParser) -> None:
        """Test that references with surrounding punctuation are parsed."""
        text = "Fixes #123, #456. Also #789)"
        refs = parser.parse_references(text)

        assert len(refs) == 3
        numbers = {ref.number for ref in refs}
        assert numbers == {123, 456, 789}

    def test_parse_empty_text(self, parser: ReferenceParser) -> None:
        """Test parsing empty text."""
        refs = parser.parse_references("")
        assert len(refs) == 0

    def test_parse_none_text(self, parser: ReferenceParser) -> None:
        """Test parsing None text."""
        refs = parser.parse_references(None)
        assert len(refs) == 0

    def test_parse_no_references(self, parser: ReferenceParser) -> None:
        """Test parsing text with no references."""
        text = "This is just a regular text with no references."
        refs = parser.parse_references(text)
        assert len(refs) == 0

    def test_parse_duplicate_references(self, parser: ReferenceParser) -> None:
        """Test that duplicate references are deduplicated."""
        text = "Fixes #123, also fixes #123, and definitely fixes #123"
        refs = parser.parse_references(text)

        assert len(refs) == 1
        ref = list(refs)[0]
        assert ref.number == 123

    def test_dedupes_same_number_different_ref_type(
        self, parser: ReferenceParser
    ) -> None:
        """Test URL type wins over shorthand for the same number."""
        text = (
            "Fixes #123 and see "
            "https://github.com/testowner/testrepo/issues/123 for details"
        )
        refs = parser.parse_references(text)

        assert len(refs) == 1
        ref = list(refs)[0]
        assert ref.number == 123
        assert ref.ref_type == "issue"
        assert ref.from_url is True

    def test_parse_url_case_insensitive(self, parser: ReferenceParser) -> None:
        """Test that URL parsing is case insensitive."""
        text = "See HTTPS://GITHUB.COM/owner/repo/PULL/999"
        refs = parser.parse_references(text)

        assert len(refs) == 1
        ref = list(refs)[0]
        assert ref.number == 999

    def test_parse_url_sets_from_url(self, parser: ReferenceParser) -> None:
        """Test URL references are marked as from_url."""
        refs = parser.parse_references("See https://github.com/owner/repo/pull/42")
        ref = list(refs)[0]
        assert ref.from_url is True

    def test_parse_same_repo_from_url_false(self, parser: ReferenceParser) -> None:
        """Test hash references are not marked as from_url."""
        refs = parser.parse_references("Fixes #99")
        ref = list(refs)[0]
        assert ref.from_url is False

    def test_skips_invalid_owner_in_url(self, parser: ReferenceParser) -> None:
        """Test invalid owner names in URLs are skipped."""
        refs = parser.parse_references("See https://github.com/bad!owner/repo/pull/1")
        assert len(refs) == 0

    def test_parse_repo_with_dots(self, parser: ReferenceParser) -> None:
        """Test parsing cross-repo references with dots in repo name."""
        text = "See owner/repo.js#123"
        refs = parser.parse_references(text)

        assert len(refs) == 1
        ref = list(refs)[0]
        assert ref.owner == "owner"
        assert ref.repo == "repo.js"
        assert ref.number == 123

    def test_parse_repo_with_hyphens(self, parser: ReferenceParser) -> None:
        """Test parsing cross-repo references with hyphens."""
        text = "See my-org/my-repo#456"
        refs = parser.parse_references(text)

        assert len(refs) == 1
        ref = list(refs)[0]
        assert ref.owner == "my-org"
        assert ref.repo == "my-repo"
        assert ref.number == 456

    def test_parse_https_urls_only(self, parser: ReferenceParser) -> None:
        """Test that only https URLs are parsed."""
        text = """
        http://github.com/owner/repo/pull/100
        https://github.com/owner/repo/pull/200
        """
        refs = parser.parse_references(text)

        assert len(refs) == 1
        assert list(refs)[0].number == 200

    def test_parse_multiline_text(self, parser: ReferenceParser) -> None:
        """Test parsing references in multiline text."""
        text = """
        Line 1: Fixes #100
        Line 2: Also owner/repo#200
        Line 3: https://github.com/test/test/pull/300
        """
        refs = parser.parse_references(text)

        assert len(refs) == 3

    def test_no_false_positives_in_code(self, parser: ReferenceParser) -> None:
        """Test that code-like patterns don't create false positives."""
        # This is tricky - we want to avoid matching things like color codes
        # but still match actual references. Current implementation may match
        # some edge cases.
        text = "array[#123] = value"
        refs = parser.parse_references(text)

        assert refs == set()

    def test_dedupe_prefers_url_ref_type_over_shorthand(
        self, parser: ReferenceParser
    ) -> None:
        """Test URL-derived issue type wins over same-repo PR shorthand."""
        text = "See #42 and https://github.com/testowner/testrepo/issues/42"
        refs = parser.parse_references(text)

        assert len(refs) == 1
        ref = next(iter(refs))
        assert ref.ref_type == "issue"
        assert ref.from_url is True
        assert ref.number == 42

    def test_dedupe_keeps_url_when_shorthand_arrives_first(
        self, parser: ReferenceParser
    ) -> None:
        """Test URL-derived reference replaces earlier shorthand for same key."""
        text = "https://github.com/testowner/testrepo/issues/42 then #42"
        refs = parser.parse_references(text)

        assert len(refs) == 1
        ref = next(iter(refs))
        assert ref.ref_type == "issue"
        assert ref.from_url is True
