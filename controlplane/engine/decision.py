"""
Tiered decision logic — turns detector output + policy into one of:
  allow | edit | block | escalate

This is deliberately the smallest module in the codebase: all the nuance
lives in the policy config, not in branching logic here. That's the point —
the same function behaves differently for a customer chatbot vs. a
regulated decision tool purely because it's handed a different Policy.
"""

from controlplane.policy.loader import Policy
from controlplane.types import Decision, PIIResult, JudgeResult


def decide(response_id: str, policy: Policy, pii: PIIResult, judge: JudgeResult) -> Decision:
    # PII is a hard gate: any hit at "block" policy mode blocks outright,
    # regardless of the judge score. Privacy leaks aren't a spectrum here.
    if pii.has_pii and policy.pii_detection == "block":
        return Decision(
            response_id=response_id,
            use_case=policy.use_case,
            tier="block",
            reason=f"PII detected: {', '.join(pii.categories)}",
            pii_categories=pii.categories,
            judge_score=judge.score,
            judge_mode=judge.mode,
            policy_version=policy.version,
            scoring_mode=policy.scoring_mode,
        )

    t = policy.thresholds
    if judge.score < t.escalate_below:
        tier = "escalate"
        reason = f"judge score {judge.score} below escalate threshold ({t.escalate_below})"
    elif judge.score < t.edit_below:
        tier = "edit"
        reason = f"judge score {judge.score} below edit threshold ({t.edit_below})"
    else:
        tier = "allow"
        reason = f"judge score {judge.score} at or above allow threshold ({t.allow_above})"

    return Decision(
        response_id=response_id,
        use_case=policy.use_case,
        tier=tier,
        reason=reason,
        pii_categories=[],
        judge_score=judge.score,
        judge_mode=judge.mode,
        policy_version=policy.version,
        scoring_mode=policy.scoring_mode,
    )
