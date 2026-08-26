"""aipr CLI: read an open-source repository's AI contribution policy.

Usage:
  aipr <owner/repo>          # fetch governance files from GitHub and classify
  aipr --text <file>         # classify a local file
  aipr --json <owner/repo>   # machine-readable output

Exit codes: 0 = autonomous-safe, 1 = not safe / restricted, 2 = unknown, 64 = usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .detector import Verdict, detect_policy

# Files that commonly carry AI policy, in priority order. The org-level
# .github repo is also probed because many foundations centralize there.
CANDIDATE_FILES = [
    "AI_POLICY.md",
    "AI_POLICY.rst",
    "AI_TOOL_POLICY.md",
    "CONTRIBUTING.md",
    "CONTRIBUTING.rst",
    ".github/AI_POLICY.md",
    ".github/CONTRIBUTING.md",
    "docs/CONTRIBUTING.md",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
]

ORG_FALLBACK_FILES = [".github/AI_POLICY.md", ".github/CONTRIBUTING.md"]

EXIT_OK = 0
EXIT_UNSAFE = 1
EXIT_UNKNOWN = 2
EXIT_USAGE = 64


def _fetch_gh(url: str) -> str | None:
    """Fetch raw content via the GitHub API (honors GH_TOKEN; no hard dep on gh)."""
    import urllib.request

    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.raw+json"})
    token = __import__("os").environ.get("GH_TOKEN") or __import__("os").environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def fetch_policy_text(repo: str) -> list[tuple[str, str]]:
    """Return [(filename, text), ...] for every candidate file found in owner/repo."""
    results: list[tuple[str, str]] = []
    for name in CANDIDATE_FILES:
        text = _fetch_gh(f"https://api.github.com/repos/{repo}/contents/{name}")
        if text and text.strip():
            results.append((name, text))
    if not results and "/" in repo:
        org = repo.split("/")[0]
        for name in ORG_FALLBACK_FILES:
            text = _fetch_gh(f"https://api.github.com/repos/{org}/.github/contents/{name}")
            if text and text.strip():
                results.append((f"{org}/.github/{name}", text))
                break
    return results


def classify_repo(repo: str) -> dict:
    """Fetch + classify all governance files of one repository."""
    files = fetch_policy_text(repo)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aipr",
        description="Read a repository's AI contribution policy before contributing.",
    )
    parser.add_argument("repo", nargs="*", help="owner/repo to inspect (accepts several for batch)")
    parser.add_argument("--text", metavar="FILE", help="classify a local file instead")
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

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
        print(json.dumps(payload, indent=2) if args.as_json else _render(payload))
        return exit_code

    # Batch mode: classify every repo, aggregate the exit code, and emit either
    # a JSON array or a per-repo human-readable block.
    results = [classify_repo(repo) for repo in args.repo]

    def _exit_code(r: dict) -> int:
        if r["verdict"] == Verdict.UNKNOWN.value:
            return EXIT_UNKNOWN
        return EXIT_OK if r["autonomous_safe"] else EXIT_UNSAFE

    worst = max(_exit_code(r) for r in results)

    if args.as_json:
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
