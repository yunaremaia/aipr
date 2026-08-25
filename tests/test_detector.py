"""Tests for aipr policy detection."""

from aipr.detector import Verdict, detect_policy


HUMAN_ONLY = """
# Contributing

## AI Policy
All AI usage in any form must be disclosed.
AI should never be the main author of the PR. Issues and PR descriptions must
be fully human-written. Bad AI drivers will be denounced.
"""

DISCLOSE_OK = """
# Contributing
AI-assisted contributions are welcome as long as they are disclosed.
Add the `Assisted-by: AI` trailer to your commits.
"""

PERMISSIVE = """
# Contributing
We warmly welcome AI-assisted contributions. Feel free to use Claude, Copilot,
ChatGPT or any LLM tooling - just stand by the code you ship. Agents are welcome.
"""

SILENT = """# Contributing

Thanks for your interest! Fork, hack, open a PR. We use ruff and pytest.
"""


def test_human_only_detected():
    p = detect_policy(HUMAN_ONLY)
    assert p.verdict is Verdict.HUMAN_ONLY
    assert p.autonomous_safe is False
    assert any("never be the main author" in e for e in p.evidence)


def test_disclose_ok_detected():
    p = detect_policy(DISCLOSE_OK)
    # "welcome as long as disclosed" reads as permissive-with-terms; either
    # permissive or disclose_ok is acceptable, both are autonomous-safe.
    assert p.verdict in (Verdict.DISCLOSE_OK, Verdict.PERMISSIVE)
    assert p.autonomous_safe is True
    assert p.score < 0


def test_permissive_detected():
    p = detect_policy(PERMISSIVE)
    assert p.verdict is Verdict.PERMISSIVE
    assert p.autonomous_safe is True


def test_silent_is_unknown():
    p = detect_policy(SILENT)
    assert p.verdict is Verdict.UNKNOWN
    assert p.confidence == 0.0
    assert p.autonomous_safe is False


def test_empty_text():
    p = detect_policy("")
    assert p.verdict is Verdict.UNKNOWN


def test_restrictive_beats_weak_permissive():
    # disclosure requirement (+2.5) outweighs the trailer mention (-1.5)
    mixed = (
        "All AI usage in any form must be disclosed. "
        "Add the Assisted-by: AI trailer.\n"
    )
    p = detect_policy(mixed)
    assert p.verdict is Verdict.RESTRICTIVE
    assert p.autonomous_safe is False


def test_evidence_always_present_when_not_unknown():
    for text in (HUMAN_ONLY, DISCLOSE_OK, PERMISSIVE):
        p = detect_policy(text)
        assert p.evidence, "expected at least one evidence snippet"


def test_verdicts_are_distinct():
    values = {v.value for v in Verdict}
    assert {"human_only", "restrictive", "disclose_ok", "permissive", "unknown"} <= values
