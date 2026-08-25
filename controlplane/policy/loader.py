"""
Loads per-use-case policy configuration from YAML.

This is the module that makes the checker "configurable, not hard-coded" —
every threshold and mode the decision engine uses comes from here, never
from a literal in the detection or decision code.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


@dataclass
class Thresholds:
    escalate_below: int
    edit_below: int
    allow_above: int


@dataclass
class Policy:
    use_case: str
    jurisdiction: str
    pii_detection: str          # "block" (only mode supported in this prototype)
    thresholds: Thresholds
    scoring_mode: str           # "sync" or "async"
    audit_retention_days: int
    version: str                # filename + mtime, used as an audit fingerprint


def load_policy(use_case: str) -> Policy:
    path = CONFIG_DIR / f"{use_case}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"No policy config found for use case '{use_case}' (expected {path})"
        )
    raw = yaml.safe_load(path.read_text())
    th = raw["thresholds"]["hallucination_score"]
    return Policy(
        use_case=raw["use_case"],
        jurisdiction=raw["jurisdiction"],
        pii_detection=raw["thresholds"]["pii_detection"],
        thresholds=Thresholds(
            escalate_below=th["escalate_below"],
            edit_below=th["edit_below"],
            allow_above=th["allow_above"],
        ),
        scoring_mode=raw["scoring_mode"],
        audit_retention_days=raw["audit_retention_days"],
        version=f"{path.name}@{int(path.stat().st_mtime)}",
    )


def list_use_cases() -> list[str]:
    return sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))
