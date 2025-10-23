# PR2MD - Pull Request to Markdown

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: CRL](https://img.shields.io/badge/License-CRL-red.svg)](LICENSE.md)

**PR2MD** is a powerful command-line tool that extracts GitHub Pull Request data and converts it into comprehensive, well-formatted Markdown documents. Perfect for documentation, archiving, code reviews, or offline analysis of pull requests.

## Features

- 📥 **Complete PR Data Extraction**: Retrieves all PR details including metadata, description, labels, and timestamps
- 💬 **Full Conversation Thread**: Captures all comments and discussions in chronological order
- ✅ **Review Information**: Includes all code reviews with approval status and reviewer comments
- 💻 **Code Comments**: Extracts inline review comments with their associated code context
- 📊 **Change Statistics**: Displays files changed, additions, deletions, and commit information
- 🔍 **Complete Diffs**: Includes the full unified diff of all changes
- 🎨 **Beautiful Formatting**: Generates clean, readable Markdown with proper structure and syntax highlighting
- ⚡ **Fast & Efficient**: Uses the official GitHub REST API with proper error handling
- 🔒 **Type-Safe**: Written in Python with comprehensive type annotations

## Installation

### From Source

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

- Python 3.13 or higher
- `requests` library (for GitHub API communication)

## Usage

### Basic Usage

Extract a PR using its URL:

```bash
pr2md https://github.com/owner/repo/pull/123
```

Or specify the owner, repository, and PR number separately:

```bash
pr2md owner repo 123
```

### Save to File

Output the Markdown to a file instead of stdout:

```bash
pr2md https://github.com/owner/repo/pull/123 -o pr-details.md
pr2md owner repo 123 --output pr-analysis.md
```

### Verbose Logging

Enable detailed logging for debugging:

```bash
pr2md https://github.com/owner/repo/pull/123 --verbose
```

### Help

View all available options:

```bash
pr2md --help
```

## Output Format

The generated Markdown document includes:

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

## Example

```bash
# Extract PR #42 from the PR2MD repository
pr2md tboy1337 PR2MD 42 -o pr-42.md
```

This creates a file `pr-42.md` containing all the PR information in a beautifully formatted Markdown document.

## GitHub API Rate Limiting

The tool uses the GitHub REST API without authentication by default. GitHub imposes rate limits:

- **Unauthenticated requests**: 60 requests per hour
- **Authenticated requests**: 5,000 requests per hour

For most use cases, unauthenticated access is sufficient as the tool makes only a few API calls per PR. If you encounter rate limiting issues, the tool will provide clear error messages.

**Future Enhancement**: Authentication support is planned for a future release to enable higher rate limits and access to private repositories.

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/tboy1337/PR2MD.git
cd PR2MD

# Install development dependencies
pip install -r requirements-dev.txt

# Install the package in editable mode
pip install -e .
```

### Running Tests

The project includes comprehensive tests using pytest:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=pr2md --cov-report=html

# Run specific test file
pytest tests/test_cli.py

# Run with verbose output
pytest -v
```

### Code Quality

The project maintains high code quality standards:

```bash
# Type checking with mypy
mypy src/pr2md

# Linting with pylint
pylint src/pr2md

# Code formatting with black
black src/pr2md tests

# Import sorting with isort
isort src/pr2md tests

# Remove trailing whitespace
py -m autopep8 --in-place --select=W291,W293 src tests
```

### Project Structure

```
PR2MD/
├── src/
│   └── pr2md/
│       ├── __init__.py
│       ├── __main__.py      # Entry point
│       ├── cli.py           # Command-line interface
│       ├── models.py        # Data models
│       ├── pr_extractor.py  # GitHub API client
│       ├── formatter.py     # Markdown formatter
│       └── py.typed         # Type checking marker
├── tests/                   # Comprehensive test suite
├── pyproject.toml          # Project configuration
├── requirements.txt        # Runtime dependencies
├── requirements-dev.txt    # Development dependencies
├── mypy.ini               # Type checking configuration
├── pytest.ini             # Test configuration
└── README.md              # This file
```

## Architecture

### Core Components

1. **CLI Module** (`cli.py`): Handles command-line argument parsing, logging setup, and orchestrates the extraction and formatting process.

2. **PR Extractor** (`pr_extractor.py`): Communicates with the GitHub REST API to fetch PR data, comments, reviews, and diffs. Includes comprehensive error handling.

3. **Models** (`models.py`): Type-safe data classes representing GitHub entities (PullRequest, Comment, Review, ReviewComment, User, Label).

4. **Formatter** (`formatter.py`): Converts structured PR data into beautifully formatted Markdown with proper sections and syntax highlighting.

### Design Principles

- **Type Safety**: Full type annotations throughout the codebase
- **Error Handling**: Graceful handling of API errors and edge cases
- **Logging**: Comprehensive logging for debugging and monitoring
- **Testability**: Modular design with clear separation of concerns
- **Extensibility**: Easy to add new features or output formats

## Use Cases

- **Code Review Documentation**: Archive code reviews for compliance or historical reference
- **Offline Analysis**: Review PRs without internet connectivity
- **Pull Request Templates**: Learn from well-structured PRs
- **Change Management**: Document significant changes in projects
- **Training Materials**: Create educational resources from real-world code reviews
- **Audit Trails**: Maintain records of development decisions
- **Report Generation**: Include PR details in project reports

## Limitations

- Currently supports only public GitHub repositories (authentication coming soon)
- Rate limited by GitHub API (60 requests/hour without authentication)
- Requires internet connection to fetch data
- Large PRs with extensive diffs may generate very large Markdown files

## Roadmap

- [ ] GitHub authentication support (personal access tokens)
- [ ] Support for GitHub Enterprise
- [ ] Private repository access
- [ ] Batch processing of multiple PRs
- [ ] Custom output templates
- [ ] Additional output formats (HTML, PDF)
- [ ] Diff filtering and summarization
- [ ] PR comparison tool
- [ ] Integration with CI/CD pipelines

## Contributing

This project is maintained by tboy1337. Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/tboy1337/PR2MD/issues).

## License

This project is licensed under the **Commercial Restricted License (CRL) Version 1.1**.

**Summary:**
- ✅ **Free for non-commercial use** (personal, educational, research, open source)
- ❌ **Commercial use requires a separate commercial license**
- 📧 Contact the copyright holder for commercial licensing inquiries

See the [LICENSE.md](LICENSE.md) file for the complete license text.

## Author

**tboy1337**
- GitHub: [@tboy1337](https://github.com/tboy1337)

## Acknowledgments

- Built with Python 3.13+
- Uses the [GitHub REST API](https://docs.github.com/en/rest)
- Inspired by the need for better PR documentation tools

---

**Made with ❤️ for the developer community**

