"""Tests for aipr SARIF output."""

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


def test_sarif_no_root_omits_original_uri_base_ids():
    """Verify originalUriBaseIds is omitted when root is None."""
    doc = to_sarif([], version="0.2.2")
    run = doc["runs"][0]
    assert "originalUriBaseIds" not in run


def test_sarif_with_root_includes_original_uri_base_ids(tmp_path):
    """Verify passing a root directory sets originalUriBaseIds to that absolute URI."""
    doc = to_sarif([], version="0.2.2", root=tmp_path)
    run = doc["runs"][0]
    assert "originalUriBaseIds" in run
    expected_uri = tmp_path.resolve().as_uri().rstrip("/") + "/"
    assert run["originalUriBaseIds"]["repoRoot"]["uri"] == expected_uri
    assert run["originalUriBaseIds"]["repoRoot"]["description"]["text"] == "Root of the repository being scanned"


def test_sarif_artifact_location_relative_to_root(tmp_path):
    """Verify findings with files generate relative paths in artifactLocation without {repoRoot}/ prefix."""
    sub = tmp_path / "docs"
    sub.mkdir()
    f1 = sub / "AI_POLICY.md"
    f1.write_text("no AI")

    results = [
        {
            "repo": "org/repo",
            "verdict": "human_only",
            "evidence": ["no AI"],
            "files": [str(f1)],
        }
    ]
    doc = to_sarif(results, version="0.2.2", root=tmp_path)
    locations = doc["runs"][0]["results"][0]["locations"]
    assert len(locations) == 1

    assert locations[0]["physicalLocation"]["artifactLocation"]["uri"] == "docs/AI_POLICY.md"
    assert locations[0]["physicalLocation"]["artifactLocation"]["uriBaseId"] == "repoRoot"
    assert locations[0]["logicalLocations"][0]["fullyQualifiedName"] == "org/repo"


def test_sarif_out_of_root_fallback(tmp_path):
    """Verify paths outside repo root fall back to file name to prevent leaking absolute paths."""
    results = [
        {
            "repo": "org/repo",
            "verdict": "human_only",
            "evidence": ["no AI"],
            "files": ["/outside/repo/path/CONTRIBUTING.md"],
        }
    ]
    doc = to_sarif(results, version="0.2.2", root=tmp_path)
    loc = doc["runs"][0]["results"][0]["locations"][0]
    assert loc["physicalLocation"]["artifactLocation"]["uri"] == "CONTRIBUTING.md"
    assert loc["physicalLocation"]["artifactLocation"]["uriBaseId"] == "repoRoot"


def test_sarif_no_root_artifact_location():
    """Verify when root is None, artifactLocation has no uriBaseId."""
    result = {
        "source": "AI_POLICY.md",
        "verdict": "permissive",
        "evidence": ["welcome"],
        "files": ["AI_POLICY.md"],
    }
    doc = to_sarif(result, version="0.2.2")
    loc = doc["runs"][0]["results"][0]["locations"][0]
    assert loc["physicalLocation"]["artifactLocation"]["uri"] == "AI_POLICY.md"
    assert "uriBaseId" not in loc["physicalLocation"]["artifactLocation"]


def test_sarif_cli_text_mode_with_root(tmp_path, capsys):
    """Verify CLI --text with --sarif and --root passes root through."""
    from aipr.cli import main
    policy = tmp_path / "AI_POLICY.md"
    policy.write_text("We warmly welcome AI-assisted contributions.\n")
    code = main(["--text", str(policy), "--sarif", "--root", str(tmp_path)])
    assert code == 0
    import json
    out = json.loads(capsys.readouterr().out)
    run = out["runs"][0]
    assert "originalUriBaseIds" in run
    assert run["originalUriBaseIds"]["repoRoot"]["uri"] == tmp_path.resolve().as_uri().rstrip("/") + "/"
    loc = run["results"][0]["locations"][0]
    assert loc["physicalLocation"]["artifactLocation"]["uri"] == "AI_POLICY.md"
    assert loc["physicalLocation"]["artifactLocation"]["uriBaseId"] == "repoRoot"


def test_sarif_validates_against_official_schema(tmp_path):
    """Verify generated SARIF document validates against the SARIF 2.1.0 JSON schema.

    The schema is vendored at ``tests/sarif-2.1.0.schema.json`` so this test needs
    no network access and runs identically on every machine and CI leg.

    ``jsonschema`` is required: if it is missing the test must SKIP loudly rather
    than silently ``return``. A silent ``return`` here reported a green run while
    asserting nothing at all, because CI installs only ``pytest``.
    """
    import json
    from pathlib import Path

    import pytest

    jsonschema = pytest.importorskip(
        "jsonschema", reason="jsonschema is required to validate SARIF output"
    )

    schema_file = Path(__file__).parent / "sarif-2.1.0.schema.json"
    assert schema_file.exists(), f"vendored SARIF schema missing: {schema_file}"

    schema = json.loads(schema_file.read_text())
    results = [
        {
            "repo": "org/repo",
            "verdict": "human_only",
            "evidence": ["no AI"],
            "files": ["CONTRIBUTING.md"],
        },
        {
            "source": "AI_POLICY.md",
            "verdict": "permissive",
            "evidence": ["welcome"],
            "files": [],
        },
        {
            "repo": "org/unknown-repo",
            "verdict": "unknown",
            "evidence": [],
            "files": [],
        },
    ]
    # Control: the schema must actually reject a malformed document. Without this,
    # a validator that silently accepts everything would make the two assertions
    # below pass forever while checking nothing.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            instance={"version": "2.1.0", "runs": [], "bogus": 1}, schema=schema
        )

    # Validate with root
    doc_with_root = to_sarif(results, version="0.2.2", root=tmp_path)
    jsonschema.validate(instance=doc_with_root, schema=schema)

    # Validate without root
    doc_without_root = to_sarif(results, version="0.2.2")
    jsonschema.validate(instance=doc_without_root, schema=schema)


def test_sarif_message_text_uses_relpath_for_out_of_root_files(tmp_path):
    """Verify message.text does not disclose absolute paths for out-of-root files (Issue #146)."""
    from pathlib import Path

    doc = to_sarif(
        [
            {
                "verdict": "human_only",
                "repo": "r",
                "files": ["/home/alice/private/secret_creds.conf"],
                "evidence": [],
            }
        ],
        root=Path("/home/alice/repo"),
    )
    result = doc["runs"][0]["results"][0]
    loc = result["locations"][0]["physicalLocation"]["artifactLocation"]
    assert loc["uri"] == "secret_creds.conf"
    assert loc["uriBaseId"] == "repoRoot"
    # Ensure message.text uses relative/sanitized name, not the absolute path
    msg = result["message"]["text"]
    assert "Sources: secret_creds.conf" in msg
    assert "/home/alice" not in msg
    assert "secret_creds.conf" in msg


def test_sarif_relative_path_traversal_outside_root(tmp_path):
    """Verify relative paths traversing outside root (e.g. ../outside) are sanitized."""
    doc = to_sarif(
        [
            {
                "verdict": "human_only",
                "repo": "r",
                "files": ["../outside/secret.conf", "docs/policy.md"],
                "evidence": [],
            }
        ],
        root=tmp_path,
    )
    result = doc["runs"][0]["results"][0]
    msg = result["message"]["text"]
    assert "Sources: secret.conf, docs/policy.md" in msg
    assert ".." not in msg

    locations = result["locations"]
    assert locations[0]["physicalLocation"]["artifactLocation"]["uri"] == "secret.conf"
    assert locations[1]["physicalLocation"]["artifactLocation"]["uri"] == "docs/policy.md"


def test_sarif_symlink_pointing_outside_root_demoted(tmp_path):
    """Verify symlinks pointing outside root are demoted to link name without leaking outside target."""
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()

    target = outside / "secret_target.txt"
    target.write_text("secret")

    symlink = repo / "link_to_secret.txt"
    symlink.symlink_to(target)

    doc = to_sarif(
        [
            {
                "verdict": "human_only",
                "repo": "my-repo",
                "files": [str(symlink)],
                "evidence": [],
            }
        ],
        root=repo,
    )
    result = doc["runs"][0]["results"][0]
    loc = result["locations"][0]["physicalLocation"]["artifactLocation"]
    assert loc["uri"] == "link_to_secret.txt"

    msg = result["message"]["text"]
    assert "Sources: link_to_secret.txt" in msg
    assert "secret_target.txt" not in msg
    assert str(outside) not in msg


