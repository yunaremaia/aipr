"""HTTP helpers with retry + rate-limit awareness for aipr.

Handles transient GitHub API errors (502/503/504/408/429) with exponential
backoff, and signals rate-limit exhaustion via a dedicated exception so callers
can avoid caching a false "no policy found" result.
"""
from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from typing import Any

# HTTP status codes that warrant a retry with exponential backoff
TRANSIENT_STATUS = {502, 503, 504, 408, 429}

# Retry configuration
MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # seconds; attempt N sleeps BACKOFF_BASE * 2**N


class RateLimitError(Exception):
    """Raised when GitHub responds with HTTP 403 due to rate limiting.

    Attributes:
        reset_time: Unix timestamp when the rate limit resets, if available
                    from the X-RateLimit-Reset response header.
    """

    def __init__(self, reset_time: int | None = None):
        self.reset_time = reset_time
        super().__init__(
            f"GitHub API rate limit exceeded (resets at {reset_time})"
        )


def _get_token() -> str | None:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _build_request(url: str, token: str | None = None) -> urllib.request.Request:
    req = urllib.request.Request(
        url, headers={
            "Accept": "application/vnd.github.raw+json",
            "User-Agent": f"aipr/{__import__('aipr').__version__}",
        }
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return req


def fetch_with_retry(url: str, timeout: int = 15) -> str | None:
    """Fetch a URL via urllib with exponential-backoff retry.

    Args:
        url: the URL to fetch
        timeout: socket timeout in seconds per attempt

    Returns:
        The response body as a string, or None if the request fails after
        all retries OR returns a non-transient error (e.g. 404).

    Raises:
        RateLimitError: if the server responds with HTTP 403 due to rate
            limiting. This is a *signal* to the caller — do NOT cache a
            false "unknown" result.
    """
    token = _get_token()
    for attempt in range(MAX_RETRIES):
        req = _build_request(url, token)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                reset = int(e.headers.get("X-RateLimit-Reset", 0)) or None
                raise RateLimitError(reset_time=reset) from e
            if e.code in TRANSIENT_STATUS and attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE * (2 ** attempt))
                continue
            # Non-transient HTTP error (404, 401, etc.) — caller sees None
            return None
        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            OSError,
        ) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE * (2 ** attempt))
                continue
            return None
    return None
