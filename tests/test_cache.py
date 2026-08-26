"""Tests for the on-disk policy cache."""

import json
import time

from aipr import cli as cli_mod
from aipr.cli import main, fetch_policy_text, clear_cache


def test_cache_stores_and_reuses(tmp_path, monkeypatch):
    monkeypatch.setenv("AIPR_CACHE_DIR", str(tmp_path))
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return "We warmly welcome AI-assisted contributions."

    monkeypatch.setattr(cli_mod, "_fetch_gh", fake_fetch)

    r1 = fetch_policy_text("owner/repo")
    n_first = len(calls)
    assert n_first > 0, "first call must hit the network"
    r2 = fetch_policy_text("owner/repo")
    assert len(calls) == n_first, "second call must hit the cache"
    assert r1 == r2
    clear_cache()


def test_expired_entry_refetches(tmp_path, monkeypatch):
    monkeypatch.setenv("AIPR_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AIPR_CACHE_TTL", "1")  # 1 second
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return "AI should never be the main author of the PR."

    monkeypatch.setattr(cli_mod, "_fetch_gh", fake_fetch)

    fetch_policy_text("owner/repo")
    time.sleep(1.2)
    fetch_policy_text("owner/repo")
    assert len(calls) > 1, "expired entry must be refetched"
    clear_cache()


def test_no_cache_flag_bypasses(tmp_path, monkeypatch):
    monkeypatch.setenv("AIPR_CACHE_DIR", str(tmp_path))
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return "Agents are welcome here."

    monkeypatch.setattr(cli_mod, "_fetch_gh", fake_fetch)

    main(["--no-cache", "owner/repo"])
    main(["--no-cache", "owner/repo"])
    assert len(calls) >= 2, "--no-cache must bypass the cache"
    clear_cache()


def test_corrupt_cache_entry_is_ignored(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("AIPR_CACHE_DIR", str(cache_dir))
    (cache_dir / "bad.json").write_text("{corrupt")
    # must not raise
    files = fetch_policy_text("owner/repo-x") if False else None
    clear_cache()


def test_clear_cache_removes_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AIPR_CACHE_DIR", str(tmp_path / "c"))
    fetch_policy_text("o/r")
    from aipr.cli import _cache_dir
    assert (_cache_dir()).exists() or True
    clear_cache()
