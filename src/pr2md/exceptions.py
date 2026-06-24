"""Common exceptions for pr2md package."""


class GitHubAPIError(Exception):
    """Exception raised for GitHub API errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url

    def __str__(self) -> str:
        base = super().__str__()
        extras: list[str] = []
        if self.status_code is not None:
            extras.append(f"status_code={self.status_code}")
        if self.url is not None:
            extras.append(f"url={self.url}")
        if extras:
            return f"{base} ({', '.join(extras)})"
        return base
