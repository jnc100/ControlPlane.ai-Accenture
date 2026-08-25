"""
AI-as-judge detector — the "slow-path" detector.

Scores how well a response is supported by its own prompt/context, rather
than checking it against absolute ground truth (which the proposal argues is
usually unavailable in production). This is a *relative* plausibility and
consistency check, not a fact-checker.

Three modes, tried in this order:
  - "llm" via Groq: used when GROQ_API_KEY is set. Groq has a free tier
    (no payment required to get a key), so this is the recommended way for
    a reviewer to see the real LLM-judge path without any cost.
  - "llm" via Anthropic: used when ANTHROPIC_API_KEY is set instead
    (paid — offered as an alternative, not the default expectation).
  - "simulated": a deterministic, explainable heuristic stand-in, used when
    no API key is available at all. This keeps the prototype runnable out
    of the box with zero setup, and every output is clearly labeled with
    which mode produced it.

Swapping between modes requires no change anywhere else in the pipeline —
the decision engine only ever consumes a JudgeResult.
"""

import hashlib
import json
import os
import re

from controlplane.types import JudgeResult

_JUDGE_PROMPT_TEMPLATE = """You are grading how well an AI response is supported by its prompt/context.
Score 0-100 (100 = fully supported and consistent, 0 = fabricated or contradicts context).

Prompt: {prompt}
Response: {response}

Reply with ONLY a JSON object: {{"score": <int 0-100>, "rationale": "<one sentence>"}}"""

_HEDGE_WORDS = re.compile(
    r"\b(?:might|may|could|possibly|approximately|around|roughly|likely|"
    r"i think|i believe|not certain|unclear)\b",
    re.IGNORECASE,
)
_ABSOLUTE_CLAIM_WORDS = re.compile(
    r"\b(?:always|never|guaranteed|100%|definitely|certainly|proven fact)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_NUMBER = re.compile(r"\b\d{2,}(?:\.\d+)?%|\$\s?\d[\d,]*\b")


def _simulated_score(prompt: str, response: str) -> JudgeResult:
    """
    Deterministic heuristic scorer used when no LLM API key is configured.

    Not a substitute for the real judge model — it exists so the prototype
    demonstrates the *mechanism* (scoring -> tiering -> policy) without
    requiring reviewers to provide their own API key. The scoring logic is
    intentionally simple and fully explainable in the rationale string.
    """
    score = 75  # neutral starting point
    reasons = []

    if _ABSOLUTE_CLAIM_WORDS.search(response):
        score -= 20
        reasons.append("contains unqualified absolute claims")

    if _UNSUPPORTED_NUMBER.search(response) and not _HEDGE_WORDS.search(response):
        score -= 15
        reasons.append("cites specific figures with no hedging or sourcing")

    if _HEDGE_WORDS.search(response):
        score += 5
        reasons.append("appropriately hedges uncertain claims")

    # Very short answers to substantive prompts are penalized lightly —
    # a proxy for "confidently terse", a common failure pattern.
    if len(response.split()) < 6 and len(prompt.split()) > 8:
        score -= 10
        reasons.append("response is unusually short relative to prompt complexity")

    # Deterministic jitter so identical inputs always score identically
    # (reproducibility matters for a demo/audit trail).
    jitter_seed = int(hashlib.sha256((prompt + response).encode()).hexdigest(), 16) % 7
    score += jitter_seed - 3

    score = max(0, min(100, score))
    rationale = "; ".join(reasons) if reasons else "no notable risk signals in heuristic scan"
    return JudgeResult(score=score, rationale=f"[simulated] {rationale}", mode="simulated")


def _groq_score(prompt: str, response: str) -> JudgeResult:
    """
    Real judge call via Groq's free-tier API (OpenAI-compatible endpoint).
    Requires GROQ_API_KEY. Get a free key at https://console.groq.com/keys —
    no payment required.
    """
    import requests

    judge_prompt = _JUDGE_PROMPT_TEMPLATE.format(prompt=prompt, response=response)
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": judge_prompt}],
            "max_tokens": 200,
            "temperature": 0,
        },
        timeout=15,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"].strip()
    try:
        parsed = json.loads(text)
        return JudgeResult(score=int(parsed["score"]), rationale=parsed["rationale"], mode="llm")
    except (json.JSONDecodeError, KeyError, ValueError):
        return JudgeResult(score=30, rationale="[llm] judge output unparseable, treated as low confidence", mode="llm")


def _anthropic_score(prompt: str, response: str) -> JudgeResult:
    """Real judge call via the Anthropic API. Requires ANTHROPIC_API_KEY (paid)."""
    import anthropic

    client = anthropic.Anthropic()
    judge_prompt = _JUDGE_PROMPT_TEMPLATE.format(prompt=prompt, response=response)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": judge_prompt}],
    )
    text = msg.content[0].text.strip()
    try:
        parsed = json.loads(text)
        return JudgeResult(score=int(parsed["score"]), rationale=parsed["rationale"], mode="llm")
    except (json.JSONDecodeError, KeyError, ValueError):
        return JudgeResult(score=30, rationale="[llm] judge output unparseable, treated as low confidence", mode="llm")


def score(prompt: str, response: str) -> JudgeResult:
    """
    Public entry point. Tries, in order: Groq (free) -> Anthropic (paid) ->
    simulated (no key needed). Any network/SDK error falls back gracefully
    to simulated rather than crashing the pipeline.
    """
    if os.environ.get("GROQ_API_KEY"):
        try:
            return _groq_score(prompt, response)
        except Exception as e:
            fallback = _simulated_score(prompt, response)
            fallback.rationale = f"[groq call failed: {e}; fell back to simulated] {fallback.rationale}"
            return fallback

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _anthropic_score(prompt, response)
        except Exception as e:
            fallback = _simulated_score(prompt, response)
            fallback.rationale = f"[anthropic call failed: {e}; fell back to simulated] {fallback.rationale}"
            return fallback

    return _simulated_score(prompt, response)
