"""Tests for the aipr CLI (no network)."""

import json
import subprocess

import pytest
from aipr.cli import _validate_repo, main, EXIT_USAGE


class TestValidateRepo:
    """Tests for the _validate_repo function."""

    @pytest.mark.parametrize("repo", [
        "owner/repo",
        "OWNER/REPO",
        "my-org/my-repo",
        "my_org/my_repo",
        "user123/repo456",
        "a-b/c-d",
        "user.name/repo.name",
        "1inch/1inch-limit-order-protocol",
        "yiiframework/yii2",
    ])
    def test_valid_repo_accepted(self, repo):
        assert _validate_repo(repo) is True

    @pytest.mark.parametrize("repo", [
        "",                       # empty
        "no-slash",               # missing slash
        "too/many/slashes",       # multiple slashes
        "/startswithslash",       # leading slash
        "endswithslash/",         # trailing slash
        "owner/ repo",            # space in name
        "owner/rep o",            # space in name
        "owner /repo",            # space in name
        "owner/rep@o",            # @ in name
        "owner/rep:o",            # : in name
        "owner/rep/o",            # extra slash
        "../../etc/passwd",       # path traversal
        "https://evil.com/x",     # URL
        "owner/repo?foo=bar",     # query string
        "owner/repo#fragment",    # fragment
    ])
    def test_invalid_repo_rejected(self, repo):
        assert _validate_repo(repo) is False


class TestMainValidation:
    """Tests for the main() function's input validation."""

    def test_invalid_repo_returns_usage_error(self, capsys):
        code = main(["invalid-repo"])
        assert code == EXIT_USAGE

    def test_multiple_invalid_repos_returns_usage_error(self, capsys):
        code = main(["bad-repo", "also-bad"])
        assert code == EXIT_USAGE

    def test_mixed_valid_invalid_returns_usage_error(self, capsys):
        code = main(["owner/repo", "bad-repo"])
        assert code == EXIT_USAGE

    def test_ssrf_payload_rejected(self, capsys):
        # Attempt a path traversal / SSRF-style payload
        code = main(["../../etc/passwd"])
        assert code == EXIT_USAGE

    def test_url_as_repo_rejected(self, capsys):
        code = main(["https://evil.com/malicious"])
        assert code == EXIT_USAGE


def test_text_mode_human_only(tmp_path, capsys):
    f = tmp_path / "policy.md"
    f.write_text("AI should never be the main author of the PR.\n")
    code = main(["--text", str(f), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["verdict"] == "human_only"
    assert out["autonomous_safe"] is False


def test_text_mode_permissive(tmp_path, capsys):
    f = tmp_path / "policy.md"
    f.write_text("We warmly welcome AI-assisted contributions.\n")
    code = main(["--text", str(f)])
    out = capsys.readouterr().out
    assert code == 0
    assert "[OK]" in out


def test_text_mode_unknown_exit_code(tmp_path, capsys):
    f = tmp_path / "plain.md"
    f.write_text("Just a README, nothing about AI.\n")
    code = main(["--text", str(f), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["verdict"] == "unknown"


def test_no_args_is_usage_error(capsys):
    code = main([])
    assert code == 64


@pytest.mark.parametrize("policy_file", [
    ".github/copilot-instructions.md",
    ".cursorrules",
    ".windsurfrules",
    ".aider.conf.yml",
])
def test_local_policy_files_detected(monkeypatch, policy_file):
    from aipr import cli as cli_mod
    from aipr.cli import classify_repo, fetch_policy_text

    content = "Never generate code for files in src/legacy/ without human review."

    def fake_fetch(url):
        if url.endswith(f"/contents/{policy_file}"):
            return content
        return None

    monkeypatch.setattr(cli_mod, "_fetch_gh", fake_fetch)

    # Verify discovered and fetched
    fetched = fetch_policy_text("owner/repo", use_cache=False)
    assert fetched == [(policy_file, content)]

    # Verify participates in classification
    result = classify_repo("owner/repo", use_cache=False)
    assert result["verdict"] == "restrictive"
    assert policy_file in result["files"]
    assert result["autonomous_safe"] is False
    assert any("Never generate code for" in e for e in result["evidence"])


def test_explain_source_reported_for_cursorrules(monkeypatch, capsys):
    from aipr import cli as cli_mod

    def fake_fetch(url):
        if url.endswith("/contents/.cursorrules"):
            return "Never generate code for files in src/legacy/ without human review."
        return None

    monkeypatch.setattr(cli_mod, "_fetch_gh", fake_fetch)

    code = main(["owner/repo", "--explain", "--no-cache"])
    out = capsys.readouterr().out
    assert code == 1
    assert "sources: .cursorrules" in out
    assert "Never generate code for" in out


def test_explain_text_mode(tmp_path, capsys):
    f = tmp_path / ".cursorrules"
    f.write_text("Never generate code for files in src/legacy/ without human review.\n")
    code = main(["--text", str(f), "--explain"])
    out = capsys.readouterr().out
    assert code == 1
    assert ".cursorrules" in out
    assert "Never generate code for" in out


def test_multiple_policy_files_sources_reported(monkeypatch, capsys):
    from aipr import cli as cli_mod

    def fake_fetch(url):
        if url.endswith("/contents/CONTRIBUTING.md"):
            return "# Contributing\n\nThanks for contributing! Fork, branch, and open a PR."
        if url.endswith("/contents/.cursorrules"):
            return "Never generate code for files in src/legacy/ without human review."
        return None

    monkeypatch.setattr(cli_mod, "_fetch_gh", fake_fetch)

    code = main(["owner/repo", "--explain", "--no-cache"])
    out = capsys.readouterr().out
    assert code == 1
    assert "sources: CONTRIBUTING.md, .cursorrules" in out
    assert "Never generate code for" in out


def test_no_policy_files_unknown(monkeypatch, capsys):
    from aipr import cli as cli_mod

    monkeypatch.setattr(cli_mod, "_fetch_gh", lambda url: None)
    code = main(["owner/repo", "--explain", "--no-cache"])
    out = capsys.readouterr().out
    assert code == 2
    assert "[UNKNOWN]" in out


def test_ordinary_ai_tools_mention_not_restrictive(monkeypatch, capsys):
    from aipr import cli as cli_mod

    def fake_fetch(url):
        if url.endswith("/contents/.cursorrules"):
            return "This project uses Cursor, Windsurf, Copilot, and Aider for coding."
        return None

    monkeypatch.setattr(cli_mod, "_fetch_gh", fake_fetch)
    code = main(["owner/repo", "--json", "--no-cache"])
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["verdict"] == "unknown"
