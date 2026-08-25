"""
Append-only audit trail.

Every decision is written as one JSON line — enough to reconstruct why a
given response was allowed, edited, blocked, or escalated: which policy
version was active, what the detectors found, and the final action. This is
the artifact a compliance stakeholder or regulator would actually ask for.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from controlplane.types import Decision

LOG_PATH = Path(__file__).resolve().parents[2] / "audit_log.jsonl"


def _input_hash(text: str) -> str:
    # Log a hash, not the raw response text, so the audit trail itself
    # doesn't become a second copy of potentially sensitive data.
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def log_decision(decision: Decision, response_text: str, path: Path = LOG_PATH) -> dict:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "response_id": decision.response_id,
        "use_case": decision.use_case,
        "input_hash": _input_hash(response_text),
        "tier": decision.tier,
        "reason": decision.reason,
        "pii_categories": decision.pii_categories,
        "judge_score": decision.judge_score,
        "judge_mode": decision.judge_mode,
        "policy_version": decision.policy_version,
        "scoring_mode": decision.scoring_mode,
    }
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry
