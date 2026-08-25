"""Tests for the aipr CLI (no network)."""

import json

from aipr.cli import main


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
