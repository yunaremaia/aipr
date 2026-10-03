"""Tests for the on-disk policy cache."""

import json
import logging
import time

from aipr import cli as cli_mod
from aipr.cli import main, fetch_policy_text, clear_cache, _cache_dir, _cache_get


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
    """A corrupt cache entry must be ignored, not raised, and must not be served.

    The entry is written under the real cache key for "owner/repo-x"
    (``repo.replace("/", "__")``), so ``_cache_get`` actually parses it. The
    corrupted JSON must be swallowed by the try/except, the network fetch must
    proceed, and the fetched result must overwrite the damaged entry.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("AIPR_CACHE_DIR", str(cache_dir))
    entry = cache_dir / "owner__repo-x.json"
    entry.write_text("{corrupt")
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return "We warmly welcome AI-assisted contributions."

    monkeypatch.setattr(cli_mod, "_fetch_gh", fake_fetch)

    # Must not raise, and must not return the corrupt payload as cached data.
    files = fetch_policy_text("owner/repo-x")
    assert calls, "corrupt cache entry must be ignored so the fetch proceeds"
    assert files, "the fetch must produce the policy files"
    assert all(text == "We warmly welcome AI-assisted contributions." for _, text in files)
    assert "AI_POLICY.md" in [name for name, _ in files]

    # The damaged entry must have been replaced by a valid, re-readable one.
    stored = json.loads(entry.read_text())
    assert stored["files"] == [[name, text] for name, text in files]
    clear_cache()


def test_clear_cache_removes_dir(tmp_path, monkeypatch):
    """clear_cache() must delete the cached entries so the next call refetches.

    ``clear_cache`` unlinks every ``*.json`` entry under the cache directory
    (it does not remove the directory itself), so the post-condition to assert
    is that no cache entries survive and that a subsequent fetch is a miss.
    """
    cache_dir = tmp_path / "c"
    monkeypatch.setenv("AIPR_CACHE_DIR", str(cache_dir))
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return "test policy"

    monkeypatch.setattr(cli_mod, "_fetch_gh", fake_fetch)

    fetch_policy_text("o/r")
    assert _cache_dir() == cache_dir, "test must exercise the patched cache dir"
    assert list(_cache_dir().glob("*.json")), "a fetch must have populated the cache"

    clear_cache()
    assert not list(_cache_dir().glob("*.json")), "clear_cache() must delete every cache entry"
    assert _cache_get("o__r") is None, "no cache entry may survive clear_cache()"

    # The cleared cache must miss, so the next call goes back to the network.
    n_before = len(calls)
    fetch_policy_text("o/r")
    assert len(calls) > n_before, "a cleared cache must not serve the previous entry"


def test_cache_get_logs_warning_on_error(tmp_path, monkeypatch, caplog):
    """Cache read failure should log a warning."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("AIPR_CACHE_DIR", str(cache_dir))
    (cache_dir / "corrupt.json").write_text("{not valid json")
    with caplog.at_level(logging.WARNING):
        result = _cache_get("corrupt")
    assert result is None
    assert any("Cache read failed" in rec.message for rec in caplog.records)

def test_fetch_gh_logs_warning_on_network_error(monkeypatch, caplog):
    """GitHub fetch failure should log a warning."""
    import urllib.error
    import unittest.mock
    from aipr.cli import _fetch_gh
    with unittest.mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("simulated")):
        with caplog.at_level(logging.WARNING):
            result = _fetch_gh("https://api.github.com/repos/test/repo/contents/AI_POLICY.md")
    assert result is None
    assert any("GitHub fetch failed" in rec.message for rec in caplog.records)


def test_int_env_valid(monkeypatch):
    from aipr.cache import _int_env
    monkeypatch.setenv("TEST_INT_VAR", "42")
    assert _int_env("TEST_INT_VAR", 10) == 42


def test_int_env_unset(monkeypatch):
    from aipr.cache import _int_env
    monkeypatch.delenv("TEST_INT_VAR", raising=False)
    assert _int_env("TEST_INT_VAR", 10) == 10


def test_int_env_invalid_fallback_and_logs_warning(monkeypatch, caplog):
    from aipr.cache import _int_env
    monkeypatch.setenv("TEST_INT_VAR", "abc")
    with caplog.at_level(logging.WARNING):
        val = _int_env("TEST_INT_VAR", 100)
    assert val == 100
    assert any("TEST_INT_VAR='abc' is not an integer; using 100" in rec.message for rec in caplog.records)


def test_invalid_cache_env_vars_cli_and_defaults(monkeypatch, caplog):
    """Non-numeric AIPR_CACHE_TTL or AIPR_CACHE_SIZE fall back to defaults and CLI works."""
    import importlib
    import pytest
    import aipr.cache
    monkeypatch.setenv("AIPR_CACHE_TTL", "invalid_ttl")
    monkeypatch.setenv("AIPR_CACHE_SIZE", "invalid_size")

    try:
        with caplog.at_level(logging.WARNING):
            importlib.reload(aipr.cache)

        assert aipr.cache.DEFAULT_CACHE_TTL == 86400
        assert aipr.cache.MAX_CACHE_SIZE == 1024
        assert any("AIPR_CACHE_TTL='invalid_ttl' is not an integer" in rec.message for rec in caplog.records)
        assert any("AIPR_CACHE_SIZE='invalid_size' is not an integer" in rec.message for rec in caplog.records)

        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])
        assert excinfo.value.code == 0
    finally:
        monkeypatch.undo()
        importlib.reload(aipr.cache)

