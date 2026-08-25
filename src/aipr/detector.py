"""Detect a repository's AI contribution policy from its governance text.

Scoring model: weighted phrase matching over the files most likely to carry
governance (CONTRIBUTING.md, AI_POLICY.md, README.md, AGENTS.md, CLAUDE.md).
Restrictive signals outweigh permissive ones; silence yields UNKNOWN.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Verdict(Enum):
    HUMAN_ONLY = "human_only"      # AI must not be the main author / human-written only
    RESTRICTIVE = "restrictive"    # heavy limits: mandatory process, bans on parts
    DISCLOSE_OK = "disclose_ok"    # allowed with disclosure / trailer
    PERMISSIVE = "permissive"      # explicitly welcomes AI contributions
    UNKNOWN = "unknown"            # no policy text found


# (compiled pattern, weight). Positive = restrictive signal, negative = permissive.
RULES: list[tuple[re.Pattern[str], float]] = [
    # --- human-only / ban level (strongest) ---
    (re.compile(r"must\s+be\s+fully\s+human[- ]written", re.I), 5.0),
    (re.compile(r"ai\s+should\s+never\s+be\s+the\s+main\s+author", re.I), 5.0),
    (re.compile(r"human[\s-]+authored\s+only", re.I), 5.0),
    (re.compile(r"(?:we\s+)?(?:do\s+not|don't)\s+accept\s+(?:any\s+)?ai", re.I), 4.5),
    (re.compile(r"(?:will\s+not\s+be\s+accepted|not\s+accepted\s+here)[^.]*\bai\b", re.I), 4.5),
    (re.compile(r"no\s+ai[- ]generated\s+(?:code|content|contributions)", re.I), 4.5),
    (re.compile(r"ai\s+contributions?\s+are\s+(?:strictly\s+)?(?:forbidden|prohibited|banned)", re.I), 4.5),
    (re.compile(r"(?:full(?:y|)\s+)?ai[- ]generated\s+contributions?[^.]{0,80}are\s+not\s+(?:allowed|permitted)", re.I), 4.5),
    (re.compile(r"fully\s+generated\s+code\s+is\s+not\s+allowed", re.I), 4.5),
    (re.compile(r"agents?\s+are\s+strictly\s+forbidden", re.I), 5.0),
    (re.compile(r"bad\s+ai\s+\w+\s+will\s+be\s+(?:denounced|blocked)", re.I), 3.0),
    (re.compile(r"human[\s-]+in[\s-]+the[\s-]+loop\s+is\s+(?:required|mandatory)", re.I), 2.0),
    (re.compile(r"(?:full\s+)?ai[- ]automation\s+without\s+human\s+review\s+is\s+not\s+(?:currently\s+)?permitted", re.I), 3.0),
    (re.compile(r"write\s+pr\s+descriptions?\s+yourself", re.I), 1.5),
    # --- restrictive ---
    (re.compile(r"all\s+ai\s+usage[^.]{0,60}must\s+be\s+disclosed", re.I), 2.5),
    (re.compile(r"mandatory\s+disclosure", re.I), 2.0),
    (re.compile(r"must\s+state\s+the\s+tool\s+you\s+used", re.I), 2.0),
    (re.compile(r"may\s+not\s+use\s+ai\s+for\s+['\"]?good\s+first\s+issues?", re.I), 2.0),
    (re.compile(r"extractive\s+contribution", re.I), 1.5),
    (re.compile(r"assisted[- ]by:\s*ai\s+(?:trailer\s+)?is\s+(?:required|mandatory)", re.I), 1.5),
    # --- disclose-ok ---
    (re.compile(r"assisted[- ]by:\s*ai", re.I), -1.5),
    (re.compile(r"disclos\w+[^.]{0,40}\b(?:is|are)\s+(?:required|expected)", re.I), -1.0),
    (re.compile(r"ai[- ]assisted\s+contributions?\s+are\s+(?:welcome|allowed|accepted)", re.I), -3.0),
    (re.compile(r"ai\s+(?:usage|assistance)\s+is\s+(?:welcome|allowed|fine|ok)\b", re.I), -3.0),
    # --- permissive ---
    (re.compile(r"we\s+(?:warmly\s+)?welcome\s+ai[- ](?:assisted|generated)", re.I), -3.5),
    (re.compile(r"feel\s+free\s+to\s+use\s+(?:claude|copilot|chatgpt|llms?|ai\s+tools)", re.I), -3.0),
    (re.compile(r"agents?\s+are\s+welcome", re.I), -3.0),
]

RESTRICTIVE_THRESHOLD = 2.0
DISCLOSE_THRESHOLD = -0.5


@dataclass
class Policy:
    verdict: Verdict
    confidence: float
    evidence: list[str] = field(default_factory=list)
    score: float = 0.0

    @property
    def autonomous_safe(self) -> bool:
        """True when an autonomous agent may contribute without human co-authorship."""
        return self.verdict in (Verdict.DISCLOSE_OK, Verdict.PERMISSIVE)


def detect_policy(text: str) -> Policy:
    """Score one blob of governance text and classify the stance."""
    if not text or not text.strip():
        return Policy(Verdict.UNKNOWN, 0.0)

    score = 0.0
    evidence: list[str] = []
    matched_strong = False

    for pattern, weight in RULES:
        match = pattern.search(text)
        if not match:
            continue
        score += weight
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 50)
        snippet = re.sub(r"\s+", " ", text[start:end]).strip()
        evidence.append(f"[{weight:+.1f}] ...{snippet}...")
        if abs(weight) >= 3.0:
            matched_strong = True

    if not evidence or score == 0.0:
        return Policy(Verdict.UNKNOWN, 0.0, evidence, score)

    if score >= 4.0:
        verdict = Verdict.HUMAN_ONLY
    elif score >= RESTRICTIVE_THRESHOLD:
        verdict = Verdict.RESTRICTIVE
    elif score <= DISCLOSE_THRESHOLD:
        verdict = (
            Verdict.PERMISSIVE if score <= -3.0 else Verdict.DISCLOSE_OK
        )
    else:
        # weak mixed signals: lean restrictive for agent safety
        verdict = Verdict.RESTRICTIVE if score > 0 else Verdict.DISCLOSE_OK

    confidence = min(1.0, abs(score) / 5.0)
    if matched_strong:
        confidence = max(confidence, 0.7)
    return Policy(verdict, round(confidence, 2), evidence, round(score, 2))
