"""SARIF output generation for aipr.

Converts aipr classification results to SARIF 2.1.0 for ingestion by GitHub Code Scanning,
GitLab Vulnerability Reports, and any other consumer that speaks SARIF.
"""
from __future__ import annotations

from typing import Any

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

# Verdict metadata: (rule_id, rule_name, rule_description)
# Maps aipr verdict strings to SARIF rule metadata.
VERDICT_RULES = {
    "human_only": (
        "ai-policy-human-only",
        "AI Contributions Prohibited",
        "Repository policy forbids AI-generated contributions without human co-authorship.",
    ),
    "restrictive": (
        "ai-policy-restrictive",
        "AI Contributions Restricted",
        "Repository policy imposes heavy limits on AI contributions (mandatory process, partial bans).",
    ),
    "disclose_ok": (
        "ai-policy-disclose-required",
        "AI Disclosure Required",
        "Repository allows AI-assisted contributions but requires disclosure in PR/commit.",
    ),
    "permissive": (
        "ai-policy-permissive",
        "AI Contributions Allowed",
        "Repository explicitly welcomes AI-assisted contributions.",
    ),
    "unknown": (
        "ai-policy-unknown",
        "No AI Policy Found",
        "Repository has no explicit AI contribution policy — contribution risk is unknown.",
    ),
}

# Map verdict to SARIF level.
# human_only / restrictive = error (blocks contribution)
# unknown = warning (needs manual review)
# permissive / disclose_ok = note (safe to proceed)
VERDICT_LEVEL = {
    "human_only": "error",
    "restrictive": "error",
    "disclose_ok": "note",
    "permissive": "note",
    "unknown": "warning",
}


def _make_rule(rule_id: str, name: str, description: str) -> dict:
    return {
        "id": rule_id,
        "name": name,
        "shortDescription": {"text": description},
        "fullDescription": {"text": description},
        "helpUri": "https://github.com/yunaremaia/aipr",
    }


def _make_result(
    rule_id: str,
    message: str,
    *,
    level: str = "warning",
    repo: str | None = None,
    source: str | None = None,
) -> dict:
    result: dict[str, Any] = {
        "ruleId": rule_id,
        "message": {"text": message},
        "level": level,
    }
    # repo for remote, source for local text mode
    qualified_name = repo or source or "unknown"
    result["locations"] = [
        {
            "logicalLocations": [
                {
                    "fullyQualifiedName": qualified_name,
                    "kind": "repository" if repo else "file",
                }
            ]
        }
    ]
    return result


def to_sarif(results: list[dict] | dict, version: str | None = None) -> dict:
    """Convert aipr classification results to SARIF 2.1.0 document.

    Args:
        results: list of classification dicts from classify_repo() or single-mode payload.
        version: aipr version string (for the tool metadata).

    Returns:
        SARIF 2.1.0 document as a dict.
    """
    if version is None:
        try:
            from . import __version__ as version
        except ImportError:
            version = "0.2.2"

    # Normalize to list
    if isinstance(results, dict):
        results = [results]

    rules: list[dict] = []
    sarif_results: list[dict] = []
    rule_set: set[str] = set()

    for r in results:
        verdict = r.get("verdict", "unknown")
        repo = r.get("repo")
        source = r.get("source")
        meta = VERDICT_RULES.get(verdict)
        if not meta:
            continue
        rule_id, rule_name, rule_desc = meta

        if rule_id not in rule_set:
            rules.append(_make_rule(rule_id, rule_name, rule_desc))
            rule_set.add(rule_id)

        level = VERDICT_LEVEL.get(verdict, "warning")

        # Build message
        evidence = r.get("evidence", [])
        evidence_text = ""
        if evidence:
            evidence_text = " | Evidence: " + "; ".join(evidence[:3])
        files = r.get("files", [])
        source_text = f" Sources: {', '.join(files)}" if files else ""

        target = repo or source or "repository"
        if verdict == "human_only":
            message = (
                f"Autonomous AI contributions NOT SAFE for {target}. "
                f"Policy requires human authorship.{evidence_text}{source_text}"
            )
        elif verdict == "restrictive":
            message = (
                f"Autonomous AI contributions NOT SAFE for {target}. "
                f"Policy has restrictive AI requirements.{evidence_text}{source_text}"
            )
        elif verdict == "disclose_ok":
            message = (
                f"AI contributions allowed with disclosure for {target}. "
                f"Remember to add 'Assisted-by: AI' trailer.{evidence_text}{source_text}"
            )
        elif verdict == "permissive":
            message = (
                f"AI contributions welcome for {target}.{evidence_text}{source_text}"
            )
        else:  # unknown
            message = (
                f"No explicit AI policy found for {target}. "
                f"Manual review recommended before contributing.{source_text}"
            )

        sarif_results.append(
            _make_result(rule_id, message, level=level, repo=repo, source=source)
        )

    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "aipr",
                        "version": version,
                        "informationUri": "https://github.com/yunaremaia/aipr",
                        "rules": rules,
                    }
                },
                "results": sarif_results,
            }
        ],
    }
