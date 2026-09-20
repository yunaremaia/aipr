"""HTTP helpers for aipr: retry + rate-limit awareness for GitHub API calls."""

from __future__ import annotations

import logging
import os
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when the GitHub API returns HTTP 403 (rate limit)."""

    def __init__(self, message: str = "GitHub API rate limit exceeded"):
        super().__init__(message)


def fetch_with_retry(
    url: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: int = 15,
) -> str | None:
    """Fetch raw content via the GitHub API with retry + rate-limit handling.

    Transient errors (502/503/504/408/429) are retried up to *max_retries* times
    with exponential backoff. HTTP 403 (rate limit) raises :class:`RateLimitError`.

    Returns the decoded text on success, or ``None`` if the request fails
    for any non-rate-limit reason (e.g. 404 Not Found).
    """
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    for attempt in range(max_retries + 1):
        from . import __version__
        req = urllib.request.Request(
            url, headers={
                "Accept": "application/vnd.github.raw+json",
                "User-Agent": f"aipr/{__version__}",
            }
        )
        if token:
            req.add_header("Authorization", f"Bearer {token}")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise RateLimitError(
                    f"GitHub API rate limit exceeded (HTTP 403) for {url}"
                )
            if e.code in (502, 503, 504, 408, 429) and attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "Transient HTTP %s on attempt %s/%s, retrying in %.1fs",
                    e.code,
                    attempt + 1,
                    max_retries + 1,
                    delay,
                )
                time.sleep(delay)
                continue
            logger.warning("HTTP error %s fetching %s", e.code, url)
            return None
        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "Fetch error on attempt %s/%s, retrying in %.1fs: %s",
                    attempt + 1,
                    max_retries + 1,
                    delay,
                    e,
                )
                time.sleep(delay)
                continue
            logger.warning("GitHub fetch failed for %s: %s", url, e)
            return None

    return None
