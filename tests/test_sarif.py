"""Tests for aipr SARIF output."""

import json

from aipr.sarif import to_sarif


def test_sarif_schema_and_version():
    doc = to_sarif([], version="0.2.2")
    assert doc["$schema"] == "https://json.schemastore.org/sarif-2.1.0.json"
    assert doc["version"] == "2.1.0"
    assert len(doc["runs"]) == 1


def test_sarif_human_only_is_error():
    results = [
        {
            "repo": "org/restricted-repo",
            "verdict": "human_only",
            "evidence": ["AI should never be the main author"],
            "files": ["CONTRIBUTING.md"],
        }
    ]
    doc = to_sarif(results, version="0.2.2")
    run = doc["runs"][0]

    # Tool metadata
    assert run["tool"]["driver"]["name"] == "aipr"
    assert run["tool"]["driver"]["version"] == "0.2.2"
    assert run["tool"]["driver"]["informationUri"] == "https://github.com/yunaremaia/aipr"

    # One rule + one result
    assert len(run["tool"]["driver"]["rules"]) == 1
    rules = run["tool"]["driver"]["rules"]
    assert rules[0]["id"] == "ai-policy-human-only"

    assert len(run["results"]) == 1
    result = run["results"][0]
    assert result["ruleId"] == "ai-policy-human-only"
    assert result["level"] == "error"
    assert "human authorship" in result["message"]["text"].lower()
    assert result["locations"][0]["logicalLocations"][0]["fullyQualifiedName"] == "org/restricted-repo"


def test_sarif_permissive_is_note():
    results = [
        {
            "repo": "org/open-repo",
            "verdict": "permissive",
            "evidence": ["We warmly welcome AI-assisted contributions"],
            "files": ["CONTRIBUTING.md"],
        }
    ]
    doc = to_sarif(results, version="0.2.2")
    result = doc["runs"][0]["results"][0]
    assert result["level"] == "note"
    assert result["ruleId"] == "ai-policy-permissive"


def test_sarif_unknown_is_warning():
    results = [
        {
            "repo": "org/plain-repo",
            "verdict": "unknown",
            "evidence": [],
            "files": [],
        }
    ]
    doc = to_sarif(results, version="0.2.2")
    result = doc["runs"][0]["results"][0]
    assert result["level"] == "warning"
    assert result["ruleId"] == "ai-policy-unknown"


def test_sarif_disclose_ok_is_note():
    results = [
        {
            "repo": "org/disclose-repo",
            "verdict": "disclose_ok",
            "evidence": ["Assisted-by: AI"],
            "files": ["CONTRIBUTING.md"],
        }
    ]
    doc = to_sarif(results, version="0.2.2")
    result = doc["runs"][0]["results"][0]
    assert result["level"] == "note"
    assert result["ruleId"] == "ai-policy-disclose-required"


def test_sarif_restrictive_is_error():
    results = [
        {
            "repo": "org/cautious-repo",
            "verdict": "restrictive",
            "evidence": ["Full AI-automation without human review is not currently permitted"],
            "files": ["AI_TOOL_POLICY.md"],
        }
    ]
    doc = to_sarif(results, version="0.2.2")
    result = doc["runs"][0]["results"][0]
    assert result["level"] == "error"
    assert result["ruleId"] == "ai-policy-restrictive"


def test_sarif_batch_multiple_repos():
    """Multiple repos produce multiple results, deduplicated rules."""
    results = [
        {"repo": "org/a", "verdict": "human_only", "evidence": ["no ai"], "files": ["README.md"]},
        {"repo": "org/b", "verdict": "permissive", "evidence": ["welcome ai"], "files": ["CONTRIBUTING.md"]},
        {"repo": "org/c", "verdict": "human_only", "evidence": ["human only"], "files": ["AI_POLICY.md"]},
        {"repo": "org/d", "verdict": "unknown", "evidence": [], "files": []},
    ]
    doc = to_sarif(results, version="0.2.2")
    run = doc["runs"][0]

    # 4 results
    assert len(run["results"]) == 4

    # 3 unique rules (human_only, permissive, unknown)
    assert len(run["tool"]["driver"]["rules"]) == 3
    rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert rule_ids == {"ai-policy-human-only", "ai-policy-permissive", "ai-policy-unknown"}


def test_sarif_evidence_and_files_in_message():
    results = [
        {
            "repo": "org/example",
            "verdict": "human_only",
            "evidence": ["must be fully human-written"],
            "files": ["CONTRIBUTING.md", "AI_POLICY.md"],
        }
    ]
    doc = to_sarif(results, version="0.2.2")
    msg = doc["runs"][0]["results"][0]["message"]["text"]
    assert "must be fully human-written" in msg
    assert "CONTRIBUTING.md" in msg
    assert "AI_POLICY.md" in msg


def test_sarif_single_dict_input():
    """to_sarif accepts a single result dict (not a list)."""
    result = {"repo": "org/x", "verdict": "permissive", "evidence": ["welcome"], "files": []}
    doc = to_sarif(result, version="0.2.2")
    assert len(doc["runs"][0]["results"]) == 1


def test_sarif_empty_results():
    doc = to_sarif([], version="0.2.2")
    assert doc["runs"][0]["results"] == []
    assert doc["runs"][0]["tool"]["driver"]["rules"] == []


def test_sarif_all_levels_correct():
    """Verify all 5 verdicts map to the correct SARIF level."""
    expected = {
        "human_only": "error",
        "restrictive": "error",
        "disclose_ok": "note",
        "permissive": "note",
        "unknown": "warning",
    }
    for verdict, expected_level in expected.items():
        doc = to_sarif(
            [{"repo": "org/t", "verdict": verdict, "evidence": [], "files": []}],
            version="0.2.2",
        )
        result = doc["runs"][0]["results"][0]
        assert result["level"] == expected_level, f"{verdict} should map to {expected_level}, got {result['level']}"
