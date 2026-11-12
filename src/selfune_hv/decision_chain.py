"""Decision chain: role need -> requirement -> evidence -> decision.

No LLM in this module. It builds, rolls up and validates chains.
The chain describes the process, never the person (hard rule 2).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

LINK_ORDER = ["role_need", "requirement", "evidence", "decision"]
VERDICTS = {"VERIFIED", "UNVERIFIED", "CONTRADICTED", "ESCALATE", "NOT_CHECKED", "WARN"}

# Severity for roll-up: the chain takes the worst verdict among its links.
# WARN never fails a chain (hard rule 7); NOT_CHECKED is never a pass (section 4).
SEVERITY = {"VERIFIED": 0, "WARN": 1, "NOT_CHECKED": 2, "UNVERIFIED": 3, "CONTRADICTED": 4, "ESCALATE": 5}

MAX_QUESTION_WORDS = 24  # "under 25 words"


@dataclass
class Link:
    link_id: str
    type: str
    statement: str
    status: str
    route: str
    depends_on: list[str] = field(default_factory=list)
    observed: Optional[str] = None
    inferred: Optional[str] = None
    observed_confidence: Optional[str] = None
    inference_confidence: Optional[str] = None
    alternative_explanations: list[str] = field(default_factory=list)
    fields_missing: list[str] = field(default_factory=list)
    trait_ref: Optional[str] = None
    ledger_refs: list[str] = field(default_factory=list)
    check_refs: list[str] = field(default_factory=list)
    note: str = ""

    def __post_init__(self) -> None:
        if self.type not in LINK_ORDER:
            raise ValueError(f"bad link type {self.type}")
        if self.status not in VERDICTS:
            raise ValueError(f"bad verdict {self.status}")


@dataclass
class HumanQuestion:
    link_id: str
    ask: str
    why: str
    do_not_ask: str = ""
    store_answer_in: str = "decision_record"

    def __post_init__(self) -> None:
        if len(self.ask.split()) > MAX_QUESTION_WORDS:
            raise ValueError(f"question over 24 words: {self.ask!r}")


def evidence_status(observed_confidence: Optional[str], inference_confidence: Optional[str],
                    fields_missing: list[str], contradicted: bool = False) -> str:
    """ERD-style split: a fact can be certain while the conclusion drawn from it is not.

    - contradicted by the data                       -> CONTRADICTED
    - conclusion rests on a missing field            -> UNVERIFIED (missing is not a negative fact; C6)
    - fact not in data (observed Low or None)        -> UNVERIFIED
    - fact certain but conclusion weak (Low)         -> UNVERIFIED
    - both High/Medium                               -> VERIFIED
    """
    if contradicted:
        return "CONTRADICTED"
    if fields_missing:
        return "UNVERIFIED"
    if observed_confidence in (None, "Low"):
        return "UNVERIFIED"
    if inference_confidence in (None, "Low"):
        return "UNVERIFIED"
    return "VERIFIED"


def roll_up(links: list[Link], high_risk: bool = False) -> tuple[str, Optional[str]]:
    """Return (chain_status, weakest_link_id).

    Weakest link = first non-VERIFIED link in chain order (need -> requirement -> evidence -> decision),
    because everything downstream inherits its doubt. Status = worst verdict.
    High-risk chains (legal check involved, or decision by tool alone) escalate
    UNVERIFIED/CONTRADICTED to ESCALATE (section 5, step 4).
    """
    ordered = sorted(links, key=lambda l: LINK_ORDER.index(l.type))
    worst = max((l.status for l in ordered), key=lambda s: SEVERITY[s])
    weakest = next((l.link_id for l in ordered if l.status != "VERIFIED"), None)
    if high_risk and worst in ("UNVERIFIED", "CONTRADICTED"):
        worst = "ESCALATE"
    return worst, weakest


def build_chain(chain_id: str, job_id: str, candidate_ref: str, stage: str,
                links: list[Link], questions: list[HumanQuestion] | None = None,
                high_risk: bool = False, blocked: bool = False) -> dict:
    types = {l.type for l in links}
    missing = [t for t in LINK_ORDER if t not in types]
    if missing:
        raise ValueError(f"chain {chain_id} missing link types {missing}")
    ids = {l.link_id for l in links}
    for l in links:
        for d in l.depends_on:
            if d not in ids:
                raise ValueError(f"{l.link_id} depends on unknown {d}")
    status, weakest = roll_up(links, high_risk)
    if blocked:
        status, weakest = "ESCALATE", next(l.link_id for l in links if "C09" in l.check_refs)
    return {
        "chain_id": chain_id,
        "job_id": job_id,
        "candidate_ref": candidate_ref,
        "stage": stage,
        "links": [_clean(asdict(l)) for l in links],
        "chain_status": status,
        "weakest_link": weakest,
        "human_questions": [_clean(asdict(q)) for q in (questions or [])],
        "blocked": blocked,
    }


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [])}
