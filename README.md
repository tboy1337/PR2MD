# PR2MD - Pull Request to Markdown

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/pr2md.svg)](https://pypi.org/project/pr2md/)
[![License: CRL](https://img.shields.io/badge/License-CRL-red.svg)](LICENSE.md)

**PR2MD** is a powerful command-line tool that extracts GitHub Pull Request and Issue data and converts it into comprehensive, well-formatted Markdown documents. Perfect for documentation, archiving, code reviews, or offline analysis of pull requests and issues.

## Features

- 📥 **Complete PR & Issue Data Extraction**: Retrieves all PR and Issue details including metadata, description, labels, and timestamps
- 💬 **Full Conversation Thread**: Captures all comments and discussions in chronological order
- ✅ **Review Information**: Includes all code reviews with approval status and reviewer comments (PRs only)
- 💻 **Code Comments**: Extracts inline review comments with their associated code context (PRs only)
- 📊 **Change Statistics**: Displays files changed, additions, deletions, and commit information (PRs only)
- 🔍 **Complete Diffs**: Includes the full unified diff of all changes (PRs only)
- 🎨 **Beautiful Formatting**: Generates clean, readable Markdown with proper structure and syntax highlighting
- ⚡ **Fast & Efficient**: Uses the official GitHub REST API with proper error handling
- 🔒 **Type-Safe**: Written in Python with comprehensive type annotations

## Installation

### Using pip (Recommended)

The easiest way to install PR2MD is directly from PyPI:

```bash
pip install pr2md
```

That's it! The `pr2md` command will be available in your terminal.

### From Source

Alternatively, you can install from source for development or to get the latest unreleased features:

```bash
# Clone the repository
git clone https://github.com/tboy1337/PR2MD.git
cd PR2MD

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

### Requirements

- Python 3.12 or higher
- `requests` library (automatically installed with pip)

## Quick Start

After installing via pip, you can immediately start using PR2MD:

```bash
# Extract a PR by URL (saves to PR-123.md)
pr2md https://github.com/owner/repo/pull/123

# Extract an Issue by URL (saves to Issue-456.md)
pr2md https://github.com/owner/repo/issues/456

# Save to a custom filename
pr2md https://github.com/owner/repo/pull/123 -o output.md

# Output to console/stdout
pr2md https://github.com/owner/repo/pull/123 -o
```

## Usage

### Basic Usage

Extract a PR using its URL (automatically saves to `PR-123.md`):

```bash
pr2md https://github.com/owner/repo/pull/123
python -m pr2md https://github.com/owner/repo/pull/123
```

Extract an Issue using its URL (automatically saves to `Issue-456.md`):

```bash
pr2md https://github.com/owner/repo/issues/456
```

Or specify the owner, repository, type, and number separately:

```bash
pr2md owner repo pr 123
pr2md owner repo issue 456
```

### Save to Custom Filename

Output the Markdown to a custom filename:

```bash
pr2md https://github.com/owner/repo/pull/123 -o pr-details.md
pr2md owner repo pr 123 --output pr-analysis.md
pr2md owner repo issue 456 --output issue-report.md
```

### Output to Console

Output to stdout instead of saving to a file:

```bash
pr2md https://github.com/owner/repo/pull/123 -o
pr2md owner repo pr 123 --output
pr2md owner repo issue 456 --output
```

### Verbose Logging

Enable detailed logging for debugging:

```bash
pr2md https://github.com/owner/repo/pull/123 -v
pr2md https://github.com/owner/repo/pull/123 --verbose
```

### Reference Downloading

By default, PR2MD automatically scans for and downloads referenced PRs and issues mentioned in the main PR/Issue. You can configure this behavior:

```bash
# Set maximum recursion depth for downloading references (default: 2)
pr2md https://github.com/owner/repo/pull/123 --depth 3

# Download direct references only (no recursion into their references)
pr2md https://github.com/owner/repo/pull/123 --depth 0

# Disable automatic downloading of referenced PRs and issues
pr2md https://github.com/owner/repo/pull/123 --no-references

# Exit with code 2 if any referenced download fails (default: partial success is OK)
pr2md https://github.com/owner/repo/pull/123 --strict
```

The `--depth` option controls how many levels deep the tool will follow references. For example, with `--depth 2`, if PR #123 references PR #456, and PR #456 references PR #789, the tool will download all three PRs. With `--depth 1`, it would only download PR #123 and PR #456. With `--depth 0`, only direct references from the primary PR or issue are downloaded (no further recursion).

**Note**: Reference downloading only works when using the default auto-naming (omitting `-o`). If you specify any output filename with `-o`, reference downloading is automatically disabled.

### Releases

Pre-built Windows executables are published on [GitHub Releases](https://github.com/tboy1337/PR2MD/releases) alongside each tagged version. pip installs remain the recommended cross-platform option.

### Help

View all available options:

```bash
pr2md --help
pr2md --version
```

## Output Format

The generated Markdown document includes:

### For Pull Requests:

### 1. PR Header
- PR number, title, and status (Open/Closed/Merged)
- Author information with GitHub profile link
- Creation, update, closed, and merged timestamps
- Base and head branch information with commit SHAs
- Labels (if any)

### 2. Description
- The full PR description/body

### 3. Changes Summary
- Number of files changed
- Line additions and deletions

### 4. Code Diff
- Complete unified diff of all changes
- Syntax-highlighted code blocks

### 5. Conversation Thread
- All comments from the PR discussion
- Chronologically sorted
- Author attribution and timestamps
- Links back to GitHub

### 6. Reviews
- All submitted reviews
- Review state (Approved ✅, Changes Requested 🔴, Commented 💬, etc.)
- Review comments and timestamps

### 7. Review Comments (Code Comments)
- Inline code review comments
- Grouped by file
- Includes code context (diff hunk)
- Reply chains preserved

### For Issues:

### 1. Issue Header
- Issue number, title, and status (Open/Closed)
- Author information with GitHub profile link
- Creation, update, and closed timestamps
- Labels (if any)

### 2. Description
- The full issue description/body

### 3. Conversation Thread
- All comments from the issue discussion
- Chronologically sorted
- Author attribution and timestamps
- Links back to GitHub

## Example

```bash
# Extract PR #42 from the PR2MD repository (saves to PR-42.md)
pr2md tboy1337 PR2MD pr 42

# Extract Issue #10 from the PR2MD repository (saves to Issue-10.md)
pr2md tboy1337 PR2MD issue 10
```

This creates files containing all the PR/Issue information in beautifully formatted Markdown documents.

If you want a custom filename:

```bash
pr2md tboy1337 PR2MD pr 42 -o pr-42-analysis.md
pr2md tboy1337 PR2MD issue 10 -o issue-10-report.md
```

## GitHub API Rate Limiting

The tool uses the GitHub REST API **without authentication**. GitHub imposes rate limits:

- **Unauthenticated requests**: 60 requests per hour per IP address
- **Authenticated requests**: 5,000 requests per hour (not supported by PR2MD)

When the API returns a rate-limit response, PR2MD **waits and retries automatically**, up to **5 waits** or **3600 seconds** of total wait time per run. Progress messages are logged at INFO level (for example, "Rate limited, waiting 45s…"). If that budget is exhausted, the run fails with an error.

For typical single PR or issue exports, unauthenticated access is usually sufficient. Reference downloading with `--depth` greater than zero consumes additional API calls. Use `--no-references` or lower `--depth` to reduce API usage.

**Authentication is not implemented by design.** Private repositories are not supported.

## Data Completeness

PR2MD avoids silent truncation where possible, with explicit bounds:

- **Paginated data** (comments, reviews, review comments) is fetched page-by-page until GitHub returns no further pages, up to a maximum of **100 pages (~10,000 items)** per endpoint; exceeding that limit fails with an error
- **Full diffs** are always included for pull requests, regardless of size; there is **no maximum export size** for PRs, issues, or diffs. Tiered log messages appear at 5 MB (warning), 25 MB (info), and 100 MB (warning) so you know memory and disk use may be high. Large diffs use streaming HTTP reads with an extended read timeout (300 seconds)
- **Reference downloads** are unlimited in count; only `--depth` bounds recursion
- **Primary exports** fail without writing a file when an unrecoverable API error occurs (exit code **1**)
- **Reference downloads** that fail are listed in stderr and appended as a `## Reference Download Summary` section in the primary markdown file; use `--strict` to exit with code **2** when any reference fails. Summary appends use streaming I/O so they work on very large output files

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Primary extraction, write, or summary append failed (including when the PR/issue number does not exist) |
| 2 | `--strict` was set and one or more reference downloads failed |

## Development

Install the package with development dependencies:

```bash
pip install -e ".[dev]"
```

Alternatively, install runtime and dev dependencies separately:

```bash
pip install -e .
pip install -r requirements-dev.txt
```

Run the local verification script (formatting, type checks, lint, security scan, tests):

```bash
py scripts/verify.py
```

Unit tests run by default; integration tests (live GitHub API) are excluded:

```bash
pytest                  # unit tests only
pytest -m integration   # live API smoke tests
```

Tests enforce at least **90% combined coverage** (see `pytest.ini` and `.coveragerc`). `py scripts/verify.py` runs the full local quality gate before release.

## Limitations

- **Public repositories only** — no GitHub token or private-repo support
- **Rate limited** — 60 API requests per hour without authentication; the tool waits and retries when limited, up to 5 waits or 3600 seconds total per run
- **Pagination cap** — at most 100 pages (~10,000 items) per paginated endpoint
- **Reference downloads** — unlimited in count; only `--depth` bounds recursion. A PR or issue with many `#NNN` references can consume the full hourly API budget and produce many files. Failures are reported in the output file and stderr; use `--strict` for exit code 2
- **Reference shorthand parsing** — `#123` and `owner/repo#123` are parsed as pull requests until download-time type correction
- Requires an internet connection to fetch data
- Large PRs with extensive diffs may generate very large Markdown files; responses are streamed with **no artificial size cap**. Tiered size notices are logged at 5 MB, 25 MB, and 100 MB; diff reads use a 300 second timeout
- Custom output paths (`-o path`) must stay within the current working directory; nested subdirectories are created automatically when needed
- Issues accessed via the `/issues/` URL path are treated as issues; use `/pull/` or explicit `pr` for pull requests
- **Non-existent resources** — if the repository or PR/issue number does not exist, the run exits immediately with code 1 and no output file is written

## License

This project is licensed under the CRL License - see [LICENSE.md](https://github.com/tboy1337/PR2MD/blob/main/LICENSE.md) for details.
