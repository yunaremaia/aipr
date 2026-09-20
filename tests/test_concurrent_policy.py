"""Tests for thread-safety of detect_policy (fixes #95, #80, #72)."""

import threading
import copy
from aipr.detector import detect_policy, Policy, Verdict


def test_detect_policy_returns_deep_copy():
    """detect_policy should return a Policy whose evidence list is independent."""
    text = "AI contributions are welcome"  # permissive
    p1 = detect_policy(text)
    p2 = detect_policy(text)
    
    assert p1.verdict == p2.verdict
    assert p1 is not p2  # different objects
    assert p1.evidence is not p2.evidence  # different lists
    
    # Mutating p1 should not affect p2
    p1.evidence.append("mutated")
    assert "mutated" not in p2.evidence


def test_concurrent_detect_policy_no_corruption():
    """100 concurrent calls should not corrupt each other results."""
    text = "We do not accept any AI contributions"  # human_only
    results = []
    errors = []
    
    def call_detect():
        try:
            p = detect_policy(text)
            results.append(p)
        except Exception as e:
            errors.append(e)
    
    threads = [threading.Thread(target=call_detect) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(errors) == 0, f"Concurrent errors: {errors}"
    assert len(results) == 100
    
    # All should have same verdict and confidence
    for p in results:
        assert p.verdict == Verdict.HUMAN_ONLY
        assert p.confidence > 0
        # Evidence should not contain snippets from other results
        for e in p.evidence:
            assert "mutated" not in e


def test_mutating_result_does_not_affect_cache():
    """Mutating a returned Policy must not corrupt the cache."""
    text = "Please disclose AI usage"  # restrictive
    
    p1 = detect_policy(text)
    original_evidence = p1.evidence.copy()
    
    # Mutate p1
    p1.evidence.append("EXTRA MUTATED")
    p1.score = 999
    
    # Get fresh result
    p2 = detect_policy(text)
    assert p2.evidence == original_evidence
    assert p2.score != 999

