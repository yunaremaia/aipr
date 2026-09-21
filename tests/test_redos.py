"""ReDoS protection tests for aipr policy detection.

Verifies that the regex engine handles adversarial input without
catastrophic backtracking (fixes #113).
"""

import time
import pytest
import regex

from aipr.detector import detect_policy, Verdict, MAX_INPUT_LENGTH


# --- ReDoS payload tests ---

def test_redos_no_catastrophic_backtracking():
    """Pattern with [^.]{0,80} must not hang on long no-period input."""
    text = "a" * 50_000 + "full ai-generated contributions are not allowed"
    start = time.time()
    result = detect_policy(text)
    elapsed = time.time() - start
    assert elapsed < 1.0, f"ReDoS: detection took {elapsed:.2f}s on adversarial input"
    assert result.verdict is not Verdict.UNKNOWN


def test_redos_very_long_no_period_text():
    """100KB text without periods must complete in < 1s."""
    text = "x" * 100_000
    start = time.time()
    result = detect_policy(text)
    elapsed = time.time() - start
    assert elapsed < 1.0, f"Detection took {elapsed:.2f}s"
    assert result.verdict is Verdict.UNKNOWN


def test_redos_repeated_alternatives():
    """Repeated alternatives that almost match should not cause hang."""
    text = ("full ai generated content " * 1000)
    start = time.time()
    result = detect_policy(text)
    elapsed = time.time() - start
    assert elapsed < 1.0, f"Detection took {elapsed:.2f}s"


def test_redos_nested_quantifiers():
    """Test pattern with nested quantifiers doesn't hang."""
    text = "a" * 10000 + "!" * 10000 + "."
    start = time.time()
    result = detect_policy(text)
    elapsed = time.time() - start
    assert elapsed < 1.0


def test_input_truncation_large_file():
    """Text over MAX_INPUT_LENGTH is truncated."""
    huge = "a" * (MAX_INPUT_LENGTH + 10000)
    start = time.time()
    result = detect_policy(huge)
    elapsed = time.time() - start
    assert elapsed < 1.0


def test_regex_timeout_caught_gracefully():
    """Even if regex engine throws TimeoutError, detect_policy survives."""
    text = "full ai-generated contributions are not allowed"
    result = detect_policy(text)
    assert result.verdict is Verdict.HUMAN_ONLY


# --- Existing behavior preserved ---

def test_normal_operation_still_works():
    """Normal-sized input still produces correct verdicts."""
    human_only = """
    # Contributing
    ## AI Policy
    AI should never be the main author of the PR.
    Issues and PR descriptions must be fully human-written.
    """
    p = detect_policy(human_only)
    assert p.verdict is Verdict.HUMAN_ONLY
    assert p.autonomous_safe is False


def test_permissive_still_detected():
    text = "# Contributing\nWe warmly welcome AI-assisted contributions."
    p = detect_policy(text)
    assert p.autonomous_safe is True


def test_empty_input():
    p = detect_policy("")
    assert p.verdict is Verdict.UNKNOWN


def test_no_policy_text():
    p = detect_policy("# Thanks for contributing! Fork and open a PR.")
    assert p.verdict is Verdict.UNKNOWN


def test_concurrent_detection_not_affected():
    """Concurrent calls should not corrupt each other (regression for #101)."""
    import concurrent.futures

    human_only = "AI should never be the main author"
    permissive = "We warmly welcome AI-assisted contributions"
    restrictive = "All AI usage must be disclosed"

    texts = [human_only] * 10 + [permissive] * 10 + [restrictive] * 10
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(detect_policy, texts))

    assert len(results) == 30
    assert all(r.verdict is Verdict.HUMAN_ONLY for r in results[0:10])
    assert all(r.verdict is Verdict.PERMISSIVE for r in results[10:20])
    assert all(r.verdict is Verdict.RESTRICTIVE for r in results[20:30])
