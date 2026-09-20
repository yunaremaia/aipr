"""aipr CLI: read an open-source repository's AI contribution policy.

Usage:
  aipr <owner/repo>          # fetch governance files from GitHub and classify
  aipr --text <file>         # classify a local file
  aipr --json <owner/repo>   # machine-readable output
  aipr init                  # scaffold AI_POLICY.md and AI_TOOL_POLICY.md

Exit codes: 0 = autonomous-safe, 1 = not safe / restricted, 2 = unknown, 64 = usage error.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from . import __version__
from .detector import Verdict, detect_policy
from .http import fetch_with_retry, RateLimitError

logger = logging.getLogger(__name__)

# Files that commonly carry AI policy, in priority order. The org-level
# .github repo is also probed because many foundations centralize there.
CANDIDATE_FILES = [
    "AI_POLICY.md",
    "AI_POLICY.rst",
    "AI_TOOL_POLICY.md",
    "CONTRIBUTING.md",
    "CONTRIBUTING.rst",
    "CONTRIBUTING-BEGINNERS.md",
    ".github/AI_POLICY.md",
    ".github/CONTRIBUTING.md",
    "docs/CONTRIBUTING.md",
    "docs/CONTRIBUTING-BEGINNERS.md",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
]

ORG_FALLBACK_FILES = [".github/AI_POLICY.md", ".github/CONTRIBUTING.md"]

EXIT_OK = 0
EXIT_UNSAFE = 1
EXIT_UNKNOWN = 2
EXIT_USAGE = 64

# --- on-disk cache ----------------------------------------------------------
# Each governance file fetch is cached under AIPR_CACHE_DIR (default:
# ~/.cache/aipr) with a TTL (AIPR_CACHE_TTL seconds, default 86400 = 24h).
# The cron scans ~10 repos/day and each repo costs up to 11 API calls; the
# cache keeps repeat scans free of charge. --no-cache bypasses it entirely.


def _cache_dir() -> Path:
    return Path(os.environ.get("AIPR_CACHE_DIR", str(Path.home() / ".cache" / "aipr")))


def _cache_ttl() -> int:
    try:
        return int(os.environ.get("AIPR_CACHE_TTL", "86400"))
    except ValueError:
        return 86400


def clear_cache() -> None:
    """Delete every cached policy entry."""
    d = _cache_dir()
    if d.exists():
        for f in d.glob("*.json"):
            f.unlink(missing_ok=True)


def _cache_get(key: str):
    path = _cache_dir() / f"{key}.json"
    try:
        entry = json.loads(path.read_text())
        if time.time() - entry["ts"] <= _cache_ttl():
            return entry["files"]
        path.unlink(missing_ok=True)
    except Exception as e:
        logger.warning("Cache read failed for %s: %s", key, e)
    return None


def _cache_put(key: str, files: list) -> None:
    d = _cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{key}.json"
    try:
        path.write_text(json.dumps({"ts": time.time(), "files": files}))
    except OSError:
        pass


def _fetch_gh(url: str) -> str | None:
    """Fetch raw content via the GitHub API (honors GH_TOKEN; no hard dep on gh).

    Delegates to :func:`aipr.http.fetch_with_retry` for retry + rate-limit
    handling. Transient errors (502/503/504/408/429) are retried up to 3 times
    with exponential backoff. HTTP 403 (rate limit) raises RateLimitError.
    """
    return fetch_with_retry(url)


def fetch_policy_text(repo: str, use_cache: bool = True) -> list[tuple[str, str]]:
    """Return [(filename, text), ...] for every candidate file found in owner/repo.

    Raises :class:`RateLimitError` if rate-limited by the GitHub API. In that case,
    no caching occurs — a later retry can succeed.
    """
    key = repo.replace("/", "__")
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return [(name, text) for name, text in cached]

    results: list[tuple[str, str]] = []
    for name in CANDIDATE_FILES:
        try:
            text = _fetch_gh(f"https://api.github.com/repos/{repo}/contents/{name}")
        except RateLimitError:
            raise  # propagate — caller handles, no caching
        if text and text.strip():
            results.append((name, text))
    if not results and "/" in repo:
        org = repo.split("/")[0]
        for name in ORG_FALLBACK_FILES:
            try:
                text = _fetch_gh(f"https://api.github.com/repos/{org}/.github/contents/{name}")
            except RateLimitError:
                raise
            if text and text.strip():
                results.append((f"{org}/.github/{name}", text))
                break
    if use_cache and results:
        _cache_put(key, [(name, text) for name, text in results])
    return results


def _validate_repo(repo: str) -> bool:
    """Validate that repo matches the expected OWNER/REPO format."""
    import re
    return bool(re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', repo))


def classify_repo(repo: str, use_cache: bool = True) -> dict:
    """Fetch + classify all governance files of one repository.

    On :class:`RateLimitError`, the cache is NOT populated with an empty result
    so that a later retry can succeed. The returned dict contains
    ``rate_limited: true`` to allow callers to distinguish this case from
    genuine "no policy found" unknowns.
    """
    if not _validate_repo(repo):
        raise ValueError(f"Invalid repository format: {repo!r}. Expected OWNER/REPO with alphanumeric, hyphen, underscore, dot characters.")
    try:
        files = fetch_policy_text(repo, use_cache=use_cache)
    except RateLimitError as e:
        logger.warning("Rate-limited on %s: %s", repo, e)
        return {
            "repo": repo,
            "verdict": Verdict.UNKNOWN.value,
            "files": [],
            "rate_limited": True,
            "autonomous_safe": False,
            "confidence": 0.0,
            "score": 0.0,
        }
    if not files:
        return {"repo": repo, "verdict": Verdict.UNKNOWN.value, "files": [],
                "autonomous_safe": False, "confidence": 0.0, "score": 0.0}

    combined = "\n\n".join(text for _, text in files)
    policy = detect_policy(combined)
    return {
        "repo": repo,
        "verdict": policy.verdict.value,
        "files": [name for name, _ in files],
        "evidence": policy.evidence,
        "autonomous_safe": policy.autonomous_safe,
        "confidence": policy.confidence,
        "score": policy.score,
    }


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for aipr."""
    parser = argparse.ArgumentParser(
        prog="aipr",
        description="Read a repository's AI contribution policy before contributing.",
    )
    parser.add_argument("repo", nargs="*", help="owner/repo to inspect (accepts several for batch)")
    parser.add_argument("--text", metavar="FILE", help="classify a local file instead")
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    parser.add_argument("--sarif", action="store_true", dest="as_sarif", help="SARIF 2.1.0 output (for GitHub Code Scanning)")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        dest="no_cache",
        help="fetch fresh policy files even if a cached copy exists",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _parse_init_args(argv: list[str]) -> argparse.Namespace:
    """Parse args for the 'init' subcommand."""
    parser = argparse.ArgumentParser(prog="aipr init", description="Scaffold AI policy files")
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("."),
        help="Directory to create policy files (default: current dir)",
    )
    parser.add_argument(
        "--type",
        choices=["permissive", "disclose", "human_only"],
        default="disclose",
        help="Policy preset (default: disclose)",
    )
    parser.add_argument(
        "--org",
        help="Organization name for centralized policies",
    )
    return parser.parse_args(argv)


def _cmd_init(args: argparse.Namespace) -> int:
    """Scaffold AI policy files in the target directory."""
    target_dir: Path = args.dir
    target_dir.mkdir(parents=True, exist_ok=True)

    policy_file = target_dir / "AI_POLICY.md"
    tool_policy_file = target_dir / "AI_TOOL_POLICY.md"

    org_line = f" for {args.org}" if args.org else ""

    if args.type == "permissive":
        policy_text = f"""# AI Usage Policy{org_line}

This repository welcomes contributions made with the assistance of AI tools.

## Guidelines

- AI-assisted contributions are encouraged.
- Contributors are responsible for verifying the correctness of all submitted code.
- No disclosure is required for AI-assisted work.

## Scope

This policy applies to all contributions: code, documentation, tests, and design.
"""
    elif args.type == "human_only":
        policy_text = f"""# AI Usage Policy{org_line}

This repository does NOT accept contributions generated by AI tools.

## Policy

- All contributions must be authored by humans.
- AI-generated code, documentation, or design submissions will be rejected.
- Automated pull requests from bots or AI agents are not permitted.

## Rationale

[Explain why human authorship is required: e.g., IP concerns, code quality, regulatory requirements.]
"""
    else:  # disclose
        policy_text = f"""# AI Usage Policy{org_line}

This repository accepts AI-assisted contributions with disclosure.

## Guidelines

- Contributions made with AI assistance are welcome.
- You MUST disclose the use of AI tools in your pull request description.
- Add the following trailer to your commit messages when AI was involved:

  `Assisted-by: AI`

- You are responsible for reviewing and verifying all AI-generated content.

## Scope

This policy applies to all contributions: code, documentation, tests, and design.
"""

    tool_policy_text = f"""# AI Tool Policy{org_line}

Classification of AI tools and their permitted usage.

## Permitted Tools

| Tool | Usage | Notes |
|------|-------|-------|
| GitHub Copilot | Code completion | Must review all suggestions |
| ChatGPT / Claude | Code generation | Must disclose in PR |
| aipr | Policy checking | Encouraged before contributing |

## Restricted Tools

- Fully autonomous coding agents (without human review) are not permitted.
- Tools that submit PRs automatically without human oversight.

## Disclosure Format

In your PR description, include:

- Tool name and version
- What it was used for
- How you verified the output
"""

    created = []
    if not policy_file.exists():
        policy_file.write_text(policy_text)
        created.append(str(policy_file))
    else:
        print(f"WARNING: {policy_file} already exists — skipping", file=sys.stderr)

    if not tool_policy_file.exists():
        tool_policy_file.write_text(tool_policy_text)
        created.append(str(tool_policy_file))
    else:
        print(f"WARNING: {tool_policy_file} already exists — skipping", file=sys.stderr)

    if created:
        print(f"✓ Created {', '.join(created)}")
        return 0
    else:
        print("No files created (already exist).", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    # Fast-path: if first arg is "init", dispatch to init subcommand
    # before building the main parser (avoids argparse subparser conflicts
    # with "owner/repo" positional args).
    if argv is not None and argv and argv[0] == "init":
        args = _parse_init_args(argv[1:])
        return _cmd_init(args)

    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.repo and not args.text:
        parser.print_usage(sys.stderr)
        return EXIT_USAGE

    if args.text:
        if len(args.repo) > 1:
            parser.error("--text cannot be combined with multiple repos")
        text = Path(args.text).read_text(encoding="utf-8", errors="replace")
        result = detect_policy(text)
        payload = {
            "source": args.text,
            "verdict": result.verdict.value,
            "evidence": result.evidence,
            "autonomous_safe": result.autonomous_safe,
            "confidence": result.confidence,
            "score": result.score,
        }
        exit_code = {
            Verdict.UNKNOWN: EXIT_UNKNOWN,
        }.get(result.verdict, EXIT_OK if result.autonomous_safe else EXIT_UNSAFE)
        if args.as_sarif:
            from .sarif import to_sarif
            print(json.dumps(to_sarif(payload), indent=2))
        else:
            print(json.dumps(payload, indent=2) if args.as_json else _render(payload))
        return exit_code

    # Batch mode: classify every repo, aggregate the exit code, and emit either
    # a JSON array or a per-repo human-readable block.
    try:
        if args.no_cache:
            from .detector import clear_policy_cache
            clear_policy_cache()
        results = [classify_repo(repo, use_cache=not args.no_cache) for repo in args.repo]
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_USAGE

    def _exit_code(r: dict) -> int:
        if r["verdict"] == Verdict.UNKNOWN.value:
            return EXIT_UNKNOWN
        return EXIT_OK if r["autonomous_safe"] else EXIT_UNSAFE

    worst = max(_exit_code(r) for r in results)

    if args.as_sarif:
        from .sarif import to_sarif
        print(json.dumps(to_sarif(results), indent=2))
    elif args.as_json:
        print(json.dumps(results if len(results) > 1 else results[0], indent=2))
    else:
        for i, r in enumerate(results):
            if i:
                print()
            print(_render(r))
    return worst


def _render(payload: dict) -> str:
    icon = {
        Verdict.HUMAN_ONLY.value: "[BLOCKED] human-only policy",
        Verdict.RESTRICTIVE.value: "[CAUTION] restrictive policy",
        Verdict.DISCLOSE_OK.value: "[OK] allowed with disclosure",
        Verdict.PERMISSIVE.value: "[OK] permissive",
        Verdict.UNKNOWN.value: "[UNKNOWN] no explicit AI policy found",
    }[payload["verdict"]]
    lines = [f"aipr: {payload.get('repo') or payload.get('source')}", icon]
    if "files" in payload and payload["files"]:
        lines.append(f"sources: {', '.join(payload['files'])}")
    if payload.get("confidence") is not None:
        lines.append(f"confidence: {payload['confidence']}  score: {payload.get('score')}")
    if payload.get("autonomous_safe"):
        lines.append("autonomous contribution: SAFE (still follow disclosure rules)")
    elif payload["verdict"] != Verdict.UNKNOWN.value:
        lines.append("autonomous contribution: NOT SAFE - require human co-authorship")
    for ev in payload.get("evidence", [])[:3]:
        lines.append(f"  {ev}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
