"""Decision mode: verify the reasoning of ONE hiring decision given as text and a few fields. No LLM.

Checks the decision's own evidence and decision links: C06 missing field as a negative, C15 vendor claim as proof,
C09 emotion or personality inference (evidence link), C08 age or age proxy and C11 GDPR Art 22 (decision link).
The rules are the same functions the full loop uses.

It checks how the decision was reasoned, never the person: nothing here scores, ranks, accepts or rejects anyone.
Nothing is stored. Never reads labels/.
"""
from __future__ import annotations

from pathlib import Path

from selfune_hv import ledger as ledger_mod
from selfune_hv.checks import (c06_missing_field as c06, c08_age_proxy as c08, c09_emotion_inference as c09,
                               c11_gdpr_art22 as c11, c15_vendor_claim as c15)
from selfune_hv.checks._common import LEGAL, Sources
from selfune_hv.decision_chain import SEVERITY, HumanQuestion, Link, _clean, build_chain
from selfune_hv.paths import resource_root
from selfune_hv.report import C06_ALTERNATIVES, FOOTER, decision_questions

DECISION_CHECKS = ["C06", "C08", "C09", "C11", "C15"]
OUTCOMES = ("rejected", "advanced", "on_hold")
DECIDED_BY = ("human", "tool", "both")
JURISDICTIONS = ("EU", "NYC", "IL", "IN", "CO", "other")
REFS = {"C06": [], "C08": ["GT-0027", "GT-0024"], "C09": ["GT-0008"], "C11": ["GT-0048", "GT-0049"],
        "C15": ["GT-0015", "GT-0017"]}
EVIDENCE = ("C06", "C15", "C09")
LEGAL_CHECKS = {"C08", "C11"}


def parse_fields(fields: str | list[str] | None) -> list[str]:
    """'references, salary expectation' -> ['references', 'salary_expectation']."""
    if not fields:
        return []
    parts = fields.replace("\n", ",").split(",") if isinstance(fields, str) else fields
    return [p.strip().lower().replace(" ", "_") for p in parts if p and p.strip()]


def verify_decision(reason_text: str, outcome: str, decided_by: str | None, jurisdiction: str = "other",
                    fields_missing: str | list[str] | None = None, root: Path | None = None) -> dict:
    """Verify one decision. `decided_by` None or '' means not recorded; `fields_missing` is optional."""
    root = Path(root) if root else resource_root()
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}")
    decided_by = decided_by if decided_by in DECIDED_BY else None
    jurisdiction = jurisdiction if jurisdiction in JURISDICTIONS else "other"
    missing = parse_fields(fields_missing)
    src = Sources(root, sorted({r for rs in REFS.values() for r in rs}))
    d = {"decision_id": "D-INPUT", "job_id": "J-INPUT", "outcome": outcome, "reason_text": reason_text.strip(),
         "fields_missing": missing, "stage": "screen"}
    if decided_by:
        d["decided_by"] = decided_by

    raw: dict[str, tuple[str, str, dict]] = {}
    v, detail = c06.evaluate(d) if missing else ("NOT_CHECKED", "No empty application fields "
                                                                    "were listed, so C06 can't tell if a gap was "
                                                                    "used against the applicant.")
    raw["C06"] = (v, detail, {})
    terms = c08.age_terms(d["reason_text"])
    raw["C08"] = (("ESCALATE", f"Reason uses an age or age proxy ({', '.join(terms)}): {LEGAL}.", {"terms": terms})
                  if terms else ("VERIFIED", "No age or age-proxy term in the stated reason.", {}))
    v, detail = c09.evaluate_text(d["reason_text"])
    raw["C09"] = (v, detail, {"biometric": c09.biometric_input(d["reason_text"])})
    if jurisdiction != "EU":
        raw["C11"] = ("NOT_CHECKED", f"GDPR Art 22 applies to EU jobs; jurisdiction given: {jurisdiction}. "
                      "Not a pass.", {})
    else:
        v, detail = c11.evaluate_decision(d)
        raw["C11"] = (v, detail, {})
    v, detail = c15.evaluate_text(d["reason_text"])
    raw["C15"] = (v, detail, {})

    findings = []
    for check in DECISION_CHECKS:
        verdict, detail, extra = raw[check]
        refs = REFS[check]
        if check in ("C08", "C11", "C15"):
            verdict = src.soften(verdict, refs) if refs else verdict   # hard rule 7; C09 is never softened (rule 1)
        msg = (c09._msg(verdict, detail, "", "text", extra.get("biometric", False)) if check == "C09"
               else {"UNVERIFIED": "Flag for review: ", "NOT_CHECKED": "Not checked: "}.get(verdict, "") + detail)
        findings.append({"check": check, "verdict": verdict, "ledger_refs": refs,
                         "message": msg + (src.cite(refs) if refs else ""), **extra})

    by = {f["check"]: f for f in findings}
    # A check with no input (C06 without a field list, C11 outside the EU) is listed as not run; it is not a flag
    # on the chain and raises no question. C11 for an EU decision with no decided_by still asks who decided.
    def flagged(c: str) -> bool:
        v = by[c]["verdict"]
        return v not in ("VERIFIED", "NOT_CHECKED") or (c == "C11" and v == "NOT_CHECKED" and jurisdiction == "EU")

    e_flags = {c: by[c] for c in EVIDENCE if flagged(c)}
    d_flags = {c: by[c] for c in ("C08", "C11") if flagged(c)}

    def link(link_id, typ, statement, flags, depends, **extra) -> Link:
        status = max((f["verdict"] for f in flags.values()), key=lambda s: SEVERITY[s]) if flags else "VERIFIED"
        refs = sorted({r for f in flags.values() for r in f["ledger_refs"]})
        return Link(link_id, typ, statement, status, "code" if status == "VERIFIED" else "human", depends,
                    ledger_refs=refs, check_refs=sorted(flags), **extra)

    e_extra = {"observed": d["reason_text"], "observed_confidence": "High"}
    if by["C06"]["verdict"] == "UNVERIFIED":
        e_extra = {"observed": f"Field(s) empty: {', '.join(missing)}.", "observed_confidence": "High",
                   "inferred": d["reason_text"], "inference_confidence": "Low", "fields_missing": missing,
                   "alternative_explanations": C06_ALTERNATIVES}
    links = [Link("N1", "role_need", "Role need not given in this mode.", "NOT_CHECKED", "human", inherited=True),
             Link("R1", "requirement", "Requirement not given in this mode.", "NOT_CHECKED", "human", ["N1"], inherited=True),
             link("E1", "evidence", f"Stated reason: {d['reason_text']}", e_flags, ["R1"], **e_extra),
             link("D1", "decision", f"Outcome '{outcome}', decided by {decided_by or 'not recorded'}.", d_flags, ["E1"])]
    high_risk = decided_by == "tool" or any(c in LEGAL_CHECKS and f["verdict"] not in ("VERIFIED", "WARN", "NOT_CHECKED")
                                            for c, f in by.items())
    blocked = by["C09"]["verdict"] == "ESCALATE"

    qs: list[HumanQuestion] = [q for _, q in decision_questions(d, e_flags, d_flags)]
    if "C09" in e_flags and by["C09"]["verdict"] == "ESCALATE":
        qs.append(HumanQuestion("E1", "Which job-related evidence can replace this emotion or personality reading?",
                                "Emotion or personality inference about candidates is blocked (hard rule 1).",
                                "Don't ask the candidate how they felt or what their personality is."))
    chain = build_chain("CH-D-INPUT", "J-INPUT", "INPUT", "screen", links, qs, high_risk=high_risk, blocked=blocked)

    rows = ledger_mod.load(str(root / "ledger/hiring.jsonl"))
    cited = sorted({r for f in findings if f["verdict"] != "VERIFIED" for r in f["ledger_refs"]})
    return {
        "mode": "decision",
        "checks": DECISION_CHECKS,
        "status": chain["chain_status"],
        "weakest_link": chain["weakest_link"],
        "blocked": blocked,
        "high_risk": high_risk,
        "not_checked": [f["check"] for f in findings if f["verdict"] == "NOT_CHECKED"],
        "inputs": {"outcome": outcome, "decided_by": decided_by, "jurisdiction": jurisdiction,
                   "fields_missing": missing},
        "findings": findings,
        "chain": chain,
        "human_questions": [_clean(q.__dict__) for q in qs],
        "citations": {r: {"id": r, "label": rows[r]["display_label"], "url": rows[r]["evidence"]["url"],
                          "retrieved": rows[r]["evidence"]["retrieved"]} for r in cited},
        "footer": FOOTER,
    }
