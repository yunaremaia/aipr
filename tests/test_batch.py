"""Tests for batch scanning and multi-repo output."""

import json
from pathlib import Path
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
    # EXIT_UNSAFE (1) outranks EXIT_UNKNOWN (2) because a hard prohibition
    # is more restrictive than an absent policy
    assert code == 1


def test_batch_ordering_independence(capsys):
    policies = {
        "blocked/repo": [("CONTRIBUTING.md", "AI should never be the main author of the PR.")],
        "blank/repo": [("CONTRIBUTING.md", "Just a README, no AI mention.")],
    }
    fetch = lambda repo, use_cache=True: policies.get(repo, [])
    with patch("aipr.cli.fetch_policy_text", side_effect=fetch):
        code1 = main(["blocked/repo", "blank/repo", "--json"])
        code2 = main(["blank/repo", "blocked/repo", "--json"])
    assert code1 == 1
    assert code2 == 1


def test_batch_all_unknown_exit_code(capsys):
    policies = {
        "blank/repo1": [("CONTRIBUTING.md", "Just a README.")],
        "blank/repo2": [("CONTRIBUTING.md", "No AI mention here.")],
    }
    with patch("aipr.cli.fetch_policy_text", side_effect=lambda repo, use_cache=True: policies.get(repo, [])):
        code = main(["blank/repo1", "blank/repo2", "--json"])
    assert code == 2


def test_batch_all_safe_exit_code(capsys):
    policies = {
        "safe/repo1": [("CONTRIBUTING.md", "We warmly welcome AI-assisted contributions. Agents are welcome.")],
        "safe/repo2": [("CONTRIBUTING.md", "We warmly welcome AI-assisted contributions. Agents are welcome.")],
    }
    with patch("aipr.cli.fetch_policy_text", side_effect=lambda repo, use_cache=True: policies.get(repo, [])):
        code = main(["safe/repo1", "safe/repo2", "--json"])
    assert code == 0


def test_exit_severity_ranking_invariants():
    from aipr.cli import EXIT_OK, EXIT_UNSAFE, EXIT_UNKNOWN, EXIT_SEVERITY

    assert EXIT_SEVERITY[EXIT_UNSAFE] > EXIT_SEVERITY[EXIT_UNKNOWN]
    assert EXIT_SEVERITY[EXIT_UNKNOWN] > EXIT_SEVERITY[EXIT_OK]


def test_docs_state_the_implemented_ranking():
    """The documented exit-code ranking must match EXIT_SEVERITY.

    Batch aggregation ranks `EXIT_UNSAFE` (1) above `EXIT_UNKNOWN` (2), so a doc
    line claiming 2 "ranks worse than 1" describes the pre-#157 `max()` and sends
    a CI author to the wrong gate.
    """
    root = Path(__file__).resolve().parents[1]
    for rel in ("README.md", "docs/usage.md"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "ranks worse than 1" not in text, (
            f"{rel} still documents the inverted exit-code ranking; batch mode ranks "
            "EXIT_UNSAFE (1) above EXIT_UNKNOWN (2)"
        )
        assert "reflects the worst result" not in text, (
            f"{rel} still calls the batch exit code 'the worst result'; it is the most "
            "restrictive one, and 'worst' is what the pre-#157 max() computed"
        )
    from aipr.cli import EXIT_OK, EXIT_SEVERITY, EXIT_UNSAFE, EXIT_UNKNOWN

    assert EXIT_SEVERITY[EXIT_UNSAFE] > EXIT_SEVERITY[EXIT_UNKNOWN] > EXIT_SEVERITY[EXIT_OK]
