"""Guard for optional claim splitting. No LLM in this module.

A model may be used ONLY to cut messy free text into one-sentence claims. It never decides a verdict and its words
are never evidence (hard rule 4): `validate_claims` keeps a claim only if every word in it is a word of the
original text, so the checks always run on the user's own wording. If the model invents, drops or rewrites
too much, the caller falls back to plain line splitting.
"""
from __future__ import annotations

import re
from collections import Counter

MAX_CLAIMS = 40
MAX_CLAIM_WORDS = 60
MIN_COVERAGE = 0.7          # share of the original words that must survive in the kept claims

_WORD = re.compile(r"[\w][\w'+#%./&-]*", re.U)
_LEAD = re.compile(r"^\s*(?:[-*•·–]|\d{1,2}[.)])\s+")


def _tokens(text: str) -> list[str]:
    return [w.lower().rstrip("'.-/&") for w in _WORD.findall(text)]


def parse_model_lines(output: str) -> list[str]:
    """One claim per non-empty line; bullets and numbering removed."""
    return [c for c in (_LEAD.sub("", ln).strip() for ln in (output or "").splitlines()) if c]


def validate_claims(source: str, claims: list[str], max_claims: int = MAX_CLAIMS,
                    min_coverage: float = MIN_COVERAGE) -> list[str] | None:
    """The claims whose every word is in `source`, or None when the result can't be trusted (use line splitting).

    None when: no claim survives, or the kept claims cover under `min_coverage` of the source words (the model
    dropped content), or there are more than `max_claims` (it did not summarise, it fragmented).
    """
    src = Counter(_tokens(source))
    if not src:
        return None
    vocab, kept, seen = set(src), [], set()
    for c in claims:
        c = c.strip()
        toks = _tokens(c)
        if not toks or len(toks) > MAX_CLAIM_WORDS or any(t not in vocab for t in toks):
            continue
        key = " ".join(toks)
        if key not in seen:
            seen.add(key)
            kept.append(c)
    if not kept or len(kept) > max_claims:
        return None
    covered = sum(min(n, src[t]) for t, n in Counter(t for c in kept for t in _tokens(c)).items())
    return kept if covered / sum(src.values()) >= min_coverage else None
