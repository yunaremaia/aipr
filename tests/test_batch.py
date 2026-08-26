"""Tests for batch scanning and multi-repo output."""

import json
from unittest.mock import patch

from aipr.cli import main


def _fake_gh(url):
    # Return a permissive policy for every file requested
    return "We warmly welcome AI-assisted contributions. Feel free to use Claude."


def test_batch_mode_multiple_repos(capsys):
    with patch("aipr.cli.fetch_policy_text", side_effect=lambda repo, use_cache=True: [("CONTRIBUTING.md", _fake_gh(""))]):
        code = main(["a/c1", "b/c2", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list)
    assert len(out) == 2
    repos = {r["repo"] for r in out}
    assert repos == {"a/c1", "b/c2"}
    assert code == 0
    assert all(r["autonomous_safe"] for r in out)


def test_batch_mixed_verdicts_exit_code(tmp_path, capsys):
    policies = {
        "ok/repo": [("CONTRIBUTING.md", "We warmly welcome AI-assisted contributions.")],
        "bad/repo": [("CONTRIBUTING.md", "AI should never be the main author of the PR.")],
        "meh/repo": [("CONTRIBUTING.md", "Just a README, no AI mention.")],
    }
    with patch("aipr.cli.fetch_policy_text", side_effect=lambda repo, use_cache=True: policies.get(repo, [])):
        code = main(list(policies) + ["--json"])
    out = json.loads(capsys.readouterr().out)
    verdicts = {r["repo"]: r["verdict"] for r in out}
    assert verdicts["ok/repo"] == "permissive"
    assert verdicts["bad/repo"] == "human_only"
    assert verdicts["meh/repo"] == "unknown"
    # any non-safe result fails the batch for CI purposes; unknown (2) ranks
    # worse than unsafe (1) so an unverified repo can never pass silently
    assert code == 2
