"""
Shared data structures used across ControlPlane Checker.

Keeping these as plain dataclasses (rather than scattering dicts everywhere)
makes the pipeline easy to follow: every stage takes and returns one of these.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PIIFinding:
    """A single piece of sensitive data found in a response."""
    category: str          # e.g. "EMAIL", "PHONE", "CREDIT_CARD", "PERSON_NAME"
    matched_text: str       # the actual substring matched (redacted in logs)
    start: int
    end: int


@dataclass
class PIIResult:
    findings: list[PIIFinding] = field(default_factory=list)

    @property
    def has_pii(self) -> bool:
        return len(self.findings) > 0

    @property
    def categories(self) -> list[str]:
        return sorted({f.category for f in self.findings})


@dataclass
class JudgeResult:
    """Output of the AI-as-judge groundedness/consistency check."""
    score: int              # 0-100, higher = more trustworthy / well-supported
    rationale: str
    mode: str                # "llm" or "simulated"


@dataclass
class DetectionResult:
    """Combined output of all detectors for a single AI response."""
    response_id: str
    use_case: str
    pii: PIIResult
    judge: JudgeResult


@dataclass
class Decision:
    """Final tiered decision for a response, after policy is applied."""
    response_id: str
    use_case: str
    tier: str                # "allow" | "edit" | "block" | "escalate"
    reason: str
    pii_categories: list[str]
    judge_score: int
    judge_mode: str
    policy_version: str
    scoring_mode: str        # "sync" or "async", from policy
