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
