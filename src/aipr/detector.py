"""Detect a repository's AI contribution policy from its governance text.

Scoring model: weighted phrase matching over the files most likely to carry
governance (CONTRIBUTING.md, AI_POLICY.md, README.md, AGENTS.md, CLAUDE.md).
Restrictive signals outweigh permissive ones; silence yields UNKNOWN.
"""

from __future__ import annotations

import re as _re
import regex
from dataclasses import dataclass, field
from enum import Enum

from aipr.cache import TTLCache


class Verdict(Enum):
    HUMAN_ONLY = "human_only"      # AI must not be the main author / human-written only
    RESTRICTIVE = "restrictive"    # heavy limits: mandatory process, bans on parts
    DISCLOSE_OK = "disclose_ok"    # allowed with disclosure / trailer
    PERMISSIVE = "permissive"      # explicitly welcomes AI contributions
    UNKNOWN = "unknown"            # no policy text found


# Maximum input length before truncation (prevents ReDoS on adversarial input)
MAX_INPUT_LENGTH = 1_000_000  # 1 MB

# Timeout in milliseconds for regex operations (prevents catastrophic backtracking)
REGEX_TIMEOUT_MS = 500  # 0.5 seconds

# Global TTL cache instance (replaces lru_cache)
_policy_cache = TTLCache()

# (compiled pattern, weight). Positive = restrictive signal, negative = permissive.
# Note: patterns use regex module (not re) for timeout support.
RULES: list[tuple[regex.Pattern[str], float]] = [
    # --- human-only / ban level (strongest) ---
    (regex.compile(r"must\s+be\s+fully\s+human[- ]written", regex.I), 5.0),
    (regex.compile(r"ai\s+should\s+never\s+be\s+the\s+main\s+author", regex.I), 5.0),
    (regex.compile(r"human[\s-]+authored\s+only", regex.I), 5.0),
    (regex.compile(r"(?:\bwe\s+)?(?:do\s+not|don't)\s+accept\s+(?:any\s+)?ai", regex.I), 4.5),
    (regex.compile(r"(?:will\s+not\s+be\s+accepted|not\s+accepted\s+here)[^.]*\bai\b", regex.I), 4.5),
    (regex.compile(r"no\s+ai[- ]generated\s+(?:code|content|contributions)", regex.I), 4.5),
    (regex.compile(r"ai\s+contributions?\s+are\s+(?:strictly\s+)?(?:forbidden|prohibited|banned)", regex.I), 4.5),
    (regex.compile(r"(?:full(?:y|)\s+)?ai[- ]generated\s+contributions?[^.]{0,80}are\s+not\s+(?:allowed|permitted)", regex.I), 4.5),
    (regex.compile(r"fully\s+generated\s+code\s+is\s+not\s+allowed", regex.I), 4.5),
    (regex.compile(r"agents?\s+are\s+strictly\s+forbidden", regex.I), 5.0),
    (regex.compile(r"bad\s+ai\s+\w+\s+will\s+be\s+(?:denounced|blocked)", regex.I), 3.0),
    (regex.compile(r"human[\s-]+in[\s-]+the[\s-]+loop\s+is\s+(?:required|mandatory)", regex.I), 2.0),
    (regex.compile(r"(?:\b)?ai[- ]automation\s+without\s+human\s+review\s+is\s+not\s+(?:currently\s+)?permitted", regex.I), 3.0),
    (regex.compile(r"write\s+pr\s+descriptions?\s+yourself", regex.I), 1.5),
    # --- restrictive ---
    (regex.compile(r"all\s+ai\s+usage[^.]{0,60}must\s+be\s+disclosed", regex.I), 2.5),
    (regex.compile(r"mandatory\s+disclosure", regex.I), 2.0),
    (regex.compile(r"must\s+state\s+the\s+tool\s+you\s+used", regex.I), 2.0),
    (regex.compile(r"may\s+not\s+use\s+ai\s+for\s+['\"]?good\s+first\s+issues?", regex.I), 2.0),
    (regex.compile(r"extractive\s+contribution", regex.I), 1.5),
    (regex.compile(r"assisted[- ]by:\s*ai\s+(?:trailer\s+)?is\s+(?:required|mandatory)", regex.I), 1.5),
    # --- understanding / human-in-the-loop mandate (e.g. alibaba/open-code-review AGENTS.md) ---
    (regex.compile(r"(?:you\s+must|contributors?\s+must)\s+(?:disclose|report|declare)[^.]{0,80}\b(?:ai|artificial\s+intelligence|llm|copilot|claude|gpt|coding\s+agent)\b", regex.I), 2.5),
    (regex.compile(r"(?:review|understand)\s+(?:every\s+line|all\s+(?:code|content|text))\s+(?:written|generated)\s+by\s+ai", regex.I), 2.0),
    (regex.compile(r"(?:must\s+not|shall\s+not)\s+attribute\s+commits?\s+(?:to\s+(?:ai|llm)|through\s+(?:assisted[- ]by|co[- ]developed))", regex.I), 1.5),
    # --- local AI tool policy rules (.cursorrules, copilot-instructions, etc.) ---
    (regex.compile(r"never\s+(?:generate|write|create)(?:\s+or\s+(?:generate|write|create))?\s+(?:any\s+)?(?:code|content)\s+(?:for|in|without)\b", regex.I), 2.5),
    (regex.compile(r"all\s+(?:(?:code|ai)\s+)?(?:changes|edits|modifications)\s+must\s+be\s+(?:human[- ]?)?reviewed\b", regex.I), 2.0),
    (regex.compile(r"(?:do\s+not|don't|never|may\s+not)\s+use\s+(?:ai|copilot|cursor|windsurf|aider|llms?)\s+(?:for|to)\b", regex.I), 2.5),
    # --- disclose-ok ---
    (regex.compile(r"assisted[- ]by:\s*ai", regex.I), -1.5),
    (regex.compile(r"disclos\w+[^.]{0,40}\b(?:is|are)\s+(?:required|expected)\b", regex.I), -1.0),
    (regex.compile(r"ai[- ]assisted\s+contributions?\s+are\s+(?:welcome|allowed|accepted)", regex.I), -3.0),
    (regex.compile(r"ai\s+(?:usage|assistance)\s+is\s+(?:welcome|allowed|fine|ok)\b", regex.I), -3.0),
    # --- permissive ---
    (regex.compile(r"(?:\bwe\s+)?(?:warmly\s+)?welcome\s+ai[- ](?:assisted|generated)", regex.I), -3.5),
    (regex.compile(r"feel\s+free\s+to\s+use\s+(?:claude|copilot|chatgpt|llms?|ai\s+tools)", regex.I), -3.0),
    (regex.compile(r"agents?\s+are\s+welcome", regex.I), -3.0),
    # --- permissive (agent-guide patterns seen in the wild: openhuman etc.) ---
    (regex.compile(r"let\s+an\s+ai\s+coding\s+agent\s+guide\s+you", regex.I), -3.0),
    (regex.compile(r"if\s+you\s+use\s+(?:claude\s+code|cursor|ampcode|codex).*?coding\s+agent", regex.I | regex.S), -3.0),
    (regex.compile(r"paste\s+this\s+prompt.*?(?:agents\.md|claude\.md)", regex.I | regex.S), -2.5),
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


def _score_text(text: str) -> Policy:
    """Score a single blob of governance text (pure computation, no caching)."""
    score = 0.0
    evidence: list[str] = []
    matched_strong = False

    for pattern, weight in RULES:
        try:
            match = pattern.search(text, timeout=REGEX_TIMEOUT_MS)
        except TimeoutError:
            continue
        if not match:
            continue
        score += weight
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 50)
        snippet = _re.sub(r"\s+", " ", text[start:end]).strip()
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
        verdict = Verdict.RESTRICTIVE if score > 0 else Verdict.DISCLOSE_OK

    confidence = min(1.0, abs(score) / 5.0)
    if matched_strong:
        confidence = max(confidence, 0.7)
    return Policy(verdict, round(confidence, 2), evidence, round(score, 2))


def clear_policy_cache() -> None:
    """Clear the in-memory cache for policy scoring."""
    _policy_cache.clear()


def detect_policy(text: str) -> Policy:
    """Score one blob of governance text and classify the stance.
    
    Uses a thread-safe TTL cache with deep copy on read to prevent
    mutation of shared state across concurrent callers.
    
    Input text is truncated to MAX_INPUT_LENGTH to prevent ReDoS on
    adversarial input.
    """
    if not text or not text.strip():
        return Policy(Verdict.UNKNOWN, 0.0)
    # Truncate to prevent catastrophic backtracking on adversarial input
    if len(text) > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]
    
    # Check cache first (returns deep copy on hit)
    cached = _policy_cache.get(text)
    if cached is not None:
        return cached
    
    # Compute and cache
    result = _score_text(text)
    _policy_cache.put(text, result)
    return result
