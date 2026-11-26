"""C16: an unvalidated product claim in hiring-tool marketing or AI output.

baseline - AVL agent mode will handle unclear cases later

Text mode only. Rule-based, no LLM. Never reads labels/.

C15 catches a vendor claim used as *grounds* for a decision. C16 catches the claim itself, as a
hiring-tool vendor writes it on a website or in a product screen: a score with no stated meaning, a
"verified" with no stated check, a "bias-free" promise, a behavioural reading from voice or video,
a prediction with no validation, or screening that runs with no person in the loop.

Each kind returns one question that asks for the evidence, never a verdict on the product.
"""
from __future__ import annotations

import re

CHECK_ID = "C16"
BASELINE = True
# Validity (Sackett), LLM screening bias (UW), solely automated decisions (GDPR Art 22).
REFS_BY_KIND = {
    "score": ["GT-0006", "GT-0007"],
    "predicts": ["GT-0006", "GT-0007"],
    "signal": ["GT-0006", "GT-0007"],
    "verified": ["GT-0007"],
    "bias_free": ["GT-0022"],
    "no_human": ["GT-0048"],
}
REFS = sorted({r for rs in REFS_BY_KIND.values() for r in rs})

_SIG = r"(?:voice|video|facial|face|tone|speech|vocal|camera)"
_BEH = r"(?:behaviou?ral|personality|soft[- ]skills?|confidence|enthusiasm|sentiment)"
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("signal", re.compile(rf"\b{_BEH}\b[^.]*\b{_SIG}\b|\b{_SIG}\b[^.]*\b{_BEH}\b", re.I)),
    ("score", re.compile(r"\b\d{1,3}\s*%\s*(?:match|fit|score|overall)\b|\b(?:match|fit|overall|ai|candidate|culture[- ]fit)"
                         r"\s+score\b|\btop fit\b|\bmatch(?:ing)? (?:percentage|rate)\b|\branks? every candidate\b", re.I)),
    ("predicts", re.compile(r"\bpredict\w*\b[^.]*\b(?:performance|success|attrition|retention|fit|top performers?)\b", re.I)),
    ("verified", re.compile(r"\b(?:verified|vetted|pre-?screened|pre-?vetted|certified)\s+(?:employers?|candidates?|talent|"
                            r"profiles?|workers?|recruiters?|professionals?|jobs?)\b", re.I)),
    ("bias_free", re.compile(r"\bbias[- ]free\b|\bunbiased\b|\bzero bias\b|\b(?:eliminat|remov)\w*\s+(?:\w+\s+){0,2}bias\b|"
                             r"\bwithout bias\b|\b100\s*%\s*(?:fair|objective)\b", re.I)),
    ("no_human", re.compile(r"\bwithout (?:a |any )?(?:recruiter|human|person)s?\b|\bno (?:recruiter|human) (?:in the loop|needed|"
                            r"involved)\b|\bauto(?:matically)?[- ]?(?:reject|shortlist|disqualif)\w*\b|\bfully autonomous\b|"
                            r"\brecruiters? only (?:touch|see|review)\b", re.I)),
]
# Text that already states the evidence or the limit.
SUPPORTED = re.compile(r"\bvalidated (?:against|on|with)\b|\bvalidation study\b|\badverse impact\b|\bbias audit\b|"
                       r"\bhuman review\b|\breviewed by (?:a )?(?:recruiter|human|person)\b|\bnot used (?:to|for) (?:decide|reject)\b",
                       re.I)

QUESTIONS = {
    "score": ("What job outcome does this score predict, and what data from real hires shows that a higher score "
              "means better work?"),
    "predicts": "Which hires was this prediction tested on, and how often was it right?",
    "signal": ("Which voice or video signals feed this result, and what shows they predict job performance rather than "
               "delivery on camera?"),
    "verified": "What exactly does 'verified' check, and what happens when a check misses?",
    "bias_free": "Which groups was this tested on, with what result, and when was it last checked?",
    "no_human": "Which decisions run with no person reviewing them, and who can a rejected candidate ask?",
}
WHY = {
    "score": "A score with no stated outcome looks like evidence but can't be checked.",
    "predicts": "A prediction claim needs a test on real hires.",
    "signal": "Delivery signals can track comfort on camera, not ability.",
    "verified": "'Verified' with no stated check can't be relied on.",
    "bias_free": "No screening method is bias-free by default; it has to be tested.",
    "no_human": "Solely automated hiring decisions carry legal duties in some places.",
}


def kinds(text: str) -> list[str]:
    return [k for k, p in PATTERNS if p.search(text)]


def evaluate_text(text: str) -> tuple[str, list[str], str]:
    """Return (verdict, kinds, detail)."""
    found = kinds(text)
    if not found:
        return "VERIFIED", [], "No unvalidated product claim."
    if SUPPORTED.search(text):
        return "VERIFIED", found, f"Claim ({', '.join(found)}) states its evidence or limit."
    return "UNVERIFIED", found, (f"Unvalidated claim ({', '.join(found)}): {WHY[found[0]]} "
                                 f"Ask: {QUESTIONS[found[0]]}")


def refs_for(found: list[str]) -> list[str]:
    return sorted({r for k in found for r in REFS_BY_KIND[k]}) or REFS
