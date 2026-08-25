"""
Rule-based PII / entity detection — the "fast-path" detector.

Deliberately deterministic (regex + a lightweight name heuristic) rather than
a trained model: this sidesteps the ground-truth problem entirely for the
categories where a fixed pattern is enough, and runs in well under the
sub-100ms budget the proposal commits to for the inline fast-path.

In a production deployment this would be swapped for something like
Microsoft Presidio or spaCy NER — see README for that extension note.
"""

import re
from controlplane.types import PIIFinding, PIIResult

# --- Regex patterns for structured PII -------------------------------------

PATTERNS = {
    "EMAIL": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "PHONE": re.compile(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?\d{10}(?!\d)"),
    "CREDIT_CARD": re.compile(r"(?<!\d)(?:\d{4}[-\s]?){3}\d{4}(?!\d)"),
    # Indian PAN as a stand-in "government ID" pattern; swap/extend per jurisdiction
    "GOV_ID": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
}

# --- Lightweight name heuristic ---------------------------------------------
# Not a real NER model — flags capitalized multi-word sequences preceded by a
# small set of person-indicating cues. Good enough for a prototype demo;
# explicitly called out as a simplification in the README.

_NAME_CUES = re.compile(
    r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|patient|customer|applicant|named|for)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"
)


def detect(text: str) -> PIIResult:
    """Run all rule-based detectors over `text` and return combined findings."""
    findings: list[PIIFinding] = []

    for category, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            findings.append(
                PIIFinding(category=category, matched_text=m.group(0), start=m.start(), end=m.end())
            )

    for m in _NAME_CUES.finditer(text):
        findings.append(
            PIIFinding(category="PERSON_NAME", matched_text=m.group(1), start=m.start(1), end=m.end(1))
        )

    return PIIResult(findings=findings)
