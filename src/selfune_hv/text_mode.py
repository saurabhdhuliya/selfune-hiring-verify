"""Text mode: verify a job post or an AI hiring summary given as plain text. No LLM.

Never reads labels/.

The text is split into lines. Requirement lines (in a requirements section, or worded like a requirement) get
C01 undefined trait, C02 years as proxy and C03 no stated reason. Every line gets C08 age or age proxy,
C09 emotion/personality inference and C15 vendor claim as proof. The rules are the same functions the main
loop uses, so a line gets the same verdict it would get as a requirement or AI text there.

It checks the wording of a process, never a person: no line is scored as a candidate.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from selfune_hv import ledger as ledger_mod
from selfune_hv.checks import (c01_undefined_trait as c01, c02_years_proxy as c02, c03_no_reason as c03,
                               c08_age_proxy as c08, c09_emotion_inference as c09, c15_vendor_claim as c15)
from selfune_hv.checks._common import LEGAL, Sources
from selfune_hv.decision_chain import SEVERITY, HumanQuestion, Link, _clean, roll_up
from selfune_hv.paths import resource_root
from selfune_hv.role_memory import RoleMemory

FOOTER = "Verifies process, not people. Not legal advice."
REFS = {"C01": ["GT-0019", "GT-0021"], "C02": ["GT-0019"], "C03": ["GT-0020"], "C08": ["GT-0027", "GT-0024"],
        "C09": ["GT-0008"], "C15": ["GT-0015", "GT-0017"]}
TEXT_CHECKS = ["C01", "C02", "C03", "C08", "C09", "C15"]
LEGAL_CHECKS = {"C08", "C09"}

_BULLET = re.compile(r"^\s*(?:[-*•·–]|\d{1,2}[.)])\s+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")
_REQ_SECTION = re.compile(r"\b(requirements?|qualifications?|what you(?:'ll)? (?:bring|need|have)|must[- ]haves?|"
                          r"about you|who you are|skills|you have|we(?:'re| are) looking for|nice to have|preferred)\b", re.I)
_REQ_CUE = re.compile(r"\b(must|required|requirements?|minimum|at least|\d+\+?\s*years?|experience|skills?|ability|"
                      r"able to|proficien\w*|strong|excellent|exceptional|degree|certif\w*|knowledge of|familiar\w*|"
                      r"you have|you are|we want|we need|looking for|preferred|team player|culture fit|attitude|"
                      r"rockstar|ninja|graduat\w*)\b", re.I)


# ---------------------------------------------------------------- splitting
def split_lines(text: str) -> list[dict]:
    """Lines of the text with kind 'requirement' or 'statement'. Headings set the section and are not checked."""
    out, section_req, after_blank = [], False, False
    for raw in text.splitlines():
        is_bullet = bool(_BULLET.match(raw))
        line = _BULLET.sub("", raw).strip()
        if not line:
            after_blank = True
            continue
        if line.endswith(":") and len(line.split()) <= 6:            # a heading
            section_req, after_blank = bool(_REQ_SECTION.search(line)), False
            continue
        if after_blank and not is_bullet:                             # plain paragraph after a list ends the section
            section_req = False
        after_blank = False
        for sent in _SENTENCE.split(line):
            sent = sent.strip()
            if not re.search(r"\w", sent):                            # keep short skills like "Go", "R", "C#"
                continue
            kind = "requirement" if section_req or _REQ_CUE.search(sent) else "statement"
            out.append({"text": sent, "kind": kind})
    return out


# ---------------------------------------------------------------- one line
def _f(check: str, verdict: str, message: str, cite: str, **extra) -> dict:
    return {"check": check, "verdict": verdict, "ledger_refs": REFS[check], "message": message + cite, **extra}


def check_line(text: str, kind: str, src: Sources, memory: RoleMemory, role_id: str | None = None,
               role_title: str = "this role") -> list[dict]:
    """All text-mode findings for one line (VERIFIED ones included, so callers can compare with the main loop)."""
    cite = lambda c: src.cite(REFS[c])  # noqa: E731
    out = []
    if kind == "requirement":
        v, detail, extra = c01.evaluate(text, role_id or "", role_title, memory)
        head = "Flag for review" if v == "UNVERIFIED" else "OK"
        out.append(_f("C01", src.soften(v, REFS["C01"]), f"{head} (baseline): {detail}", cite("C01"), **extra))
        years = c02.years_counts(text)
        if years:
            out.append(_f("C02", src.soften("UNVERIFIED", REFS["C02"]), f"Flag for review (baseline): years count "
                          f"({', '.join(years)}) used as a proxy for ability. Ask what the years should show, and "
                          "test that directly.", cite("C02"), years=years))
        else:
            out.append(_f("C02", "VERIFIED", "OK (baseline): no years-of-experience count.", cite("C02")))
        reason = c03.stated_reason(text)
        if reason:
            out.append(_f("C03", "VERIFIED", f"OK (baseline): reason stated ('{reason}'); its truth is not checked here.",
                          cite("C03")))
        else:
            out.append(_f("C03", src.soften("UNVERIFIED", REFS["C03"]), "Flag for review (baseline): no stated reason "
                          "why this serves the role. Ask how it predicts success in this role.", cite("C03")))
    terms = c08.age_terms(text)
    if terms:
        out.append(_f("C08", src.soften("ESCALATE", REFS["C08"]), f"Uses an age or age proxy ({', '.join(terms)}): "
                      f"{LEGAL}.", cite("C08"), terms=terms))
    else:
        out.append(_f("C08", "VERIFIED", "No age or age-proxy term.", cite("C08")))
    v, detail = c09.evaluate_text(text)                      # hard rule 1: never softened
    bio = c09.biometric_input(text)
    out.append(_f("C09", v, c09._msg(v, detail, "", "text", bio), cite("C09"), biometric=bio))
    v, detail = c15.evaluate_text(text)
    out.append(_f("C15", src.soften(v, REFS["C15"]), ("Flag for review (baseline): " if v == "UNVERIFIED" else "OK (baseline): ")
                  + detail, cite("C15")))
    return out


# ---------------------------------------------------------------- questions
def _short(text: str, words: int = 8) -> str:
    w = text.rstrip(".").split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def line_questions(link_id: str, text: str, kind: str, flags: dict[str, dict]) -> list[HumanQuestion]:
    """At most one requirement question per line (C01, then C02, then C03), plus one per flagged C08/C09/C15.

    An age or age-proxy line (C08) gets only the age question: asking how an age rule "helps the role succeed"
    would invite a justification of it.
    """
    qs = []
    if kind == "requirement" and "C08" not in flags:
        if "C01" in flags:
            qs.append(HumanQuestion(link_id, flags["C01"]["question"], "Until defined, the trait can't be checked "
                                    "against evidence.", "Don't ask about personality, attitude or 'fit'; ask for an "
                                    "observable result.", "role_memory"))
        elif "C02" in flags:
            qs.append(HumanQuestion(link_id, f"What should {', '.join(flags['C02']['years'])} show for this role, and "
                                    "could a work sample test that directly?", "Years of experience is a proxy; the "
                                    "ability itself is not checked.", "Don't ask whether younger applicants could cope.",
                                    "role_memory"))
        elif "C03" in flags:
            qs.append(HumanQuestion(link_id, f'How does "{_short(text)}" help someone succeed in this role?',
                                    "No stated reason links this requirement to the role.",
                                    "Don't ask 'is this a nice-to-have?'; ask what fails without it.", "role_memory"))
    if "C09" in flags:
        qs.append(HumanQuestion(link_id, "Which job-related evidence can replace this emotion or personality reading?",
                                "Emotion or personality inference about candidates is blocked (hard rule 1).",
                                "Don't ask the candidate how they felt or what their personality is."))
    if "C08" in flags:
        qs.append(HumanQuestion(link_id, "What job-related reason, other than age or graduation year, supports this?",
                                "Age and age proxies are high legal risk.",
                                "Don't ask the applicant's age or graduation year."))
    if "C15" in flags:
        qs.append(HumanQuestion(link_id, "What data from your own process shows this vendor claim holds for this role?",
                                "A vendor's claim is context, not proof.", "Don't ask whether the vendor is trusted."))
    return qs


# ---------------------------------------------------------------- report
def verify_text(text: str, root: Path | None = None, role_memory: dict | None = None, role_id: str | None = None,
                role_title: str = "this role", today: date | None = None) -> dict:
    """Verify plain text. Returns a JSON-ready report: per-line verdicts, status, weakest link, questions."""
    root = Path(root) if root else resource_root()
    refs_all = sorted({r for rs in REFS.values() for r in rs})
    src = Sources(root, refs_all)
    memory = RoleMemory(role_memory or {"roles": []}, today)
    lines = split_lines(text)
    items, links, questions, seen = [], [], [], set()
    n_req = n_stmt = 0
    for ln in lines:
        if ln["kind"] == "requirement":
            n_req += 1
            lid, ltype = f"R{n_req}", "requirement"
        else:
            n_stmt += 1
            lid, ltype = f"E{n_stmt}", "evidence"
        findings = check_line(ln["text"], ln["kind"], src, memory, role_id, role_title)
        flags = {f["check"]: f for f in findings if f["verdict"] != "VERIFIED"}
        status = max((f["verdict"] for f in findings), key=lambda s: SEVERITY[s])
        items.append({"link_id": lid, "kind": ln["kind"], "text": ln["text"], "status": status,
                      "findings": [f for f in findings if f["verdict"] != "VERIFIED"],
                      "checks_run": [f["check"] for f in findings]})
        links.append(Link(lid, ltype, ln["text"], status, "code" if status == "VERIFIED" else "human",
                          ledger_refs=sorted({r for f in flags.values() for r in f["ledger_refs"]}),
                          check_refs=sorted(flags)))
        for q in line_questions(lid, ln["text"], ln["kind"], flags):
            if q.ask not in seen:
                seen.add(q.ask)
                questions.append(_clean(q.__dict__))

    high_risk = any(f["check"] in LEGAL_CHECKS for it in items for f in it["findings"]
                    if f["verdict"] not in ("VERIFIED", "WARN"))
    blocked_link = next((it["link_id"] for it in items for f in it["findings"]
                         if f["check"] == "C09" and f["verdict"] == "ESCALATE"), None)
    if not links:
        status, weakest = "NOT_CHECKED", None
    elif blocked_link:
        status, weakest = "ESCALATE", blocked_link
    else:
        status, weakest = roll_up(links, high_risk)
    cited = sorted({r for it in items for f in it["findings"] for r in f["ledger_refs"]})
    rows = ledger_mod.load(str(root / "ledger/hiring.jsonl"))
    counts: dict[str, int] = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    return {
        "mode": "text",
        "checks": TEXT_CHECKS,
        "status": status,
        "weakest_link": weakest,
        "blocked": blocked_link is not None,
        "high_risk": high_risk,
        "summary": {"lines": len(items), "requirement_lines": n_req, "statement_lines": n_stmt,
                    "lines_by_status": counts, "human_questions": len(questions)},
        "items": items,
        "human_questions": questions,
        "citations": {r: {"id": r, "label": rows[r]["display_label"], "url": rows[r]["evidence"]["url"],
                          "retrieved": rows[r]["evidence"]["retrieved"]} for r in cited},
        "footer": FOOTER,
    }


def format_text(report: dict) -> str:
    """A readable plain-text rendering of a text-mode report."""
    s = report["summary"]
    out = [f"Selfune Hiring Verification: text mode ({', '.join(report['checks'])})",
           f"Status: {report['status']}" + (f" · weakest link {report['weakest_link']}" if report["weakest_link"] else "")
           + (" · BLOCKED by C09" if report["blocked"] else "") + (" · high risk" if report["high_risk"] else ""),
           f"Lines: {s['lines']} ({s['requirement_lines']} requirement, {s['statement_lines']} other) · "
           + ", ".join(f"{k} {v}" for k, v in sorted(s["lines_by_status"].items())), ""]
    for it in report["items"]:
        mark = "OK " if it["status"] == "VERIFIED" else "!! "
        out.append(f"{mark}{it['link_id']:<4} {it['status']:<12} {it['text']}")
        for f in it["findings"]:
            msg = f["message"].split(" Source: ")[0]
            out.append(f"       {f['check']} {f['verdict']}: {msg}")
            out.append(f"       cites {', '.join(f['ledger_refs'])}")
    if report["human_questions"]:
        out += ["", f"Questions for you ({len(report['human_questions'])}):"]
        for i, q in enumerate(report["human_questions"], 1):
            out.append(f"  {i}. [{q['link_id']}] {q['ask']}")
            if q.get("do_not_ask"):
                out.append(f"     Avoid: {q['do_not_ask']}")
    if report["citations"]:
        out += ["", "Sources:"]
        for c in report["citations"].values():
            out.append(f"  {c['id']} · {c['label']} · {c['url']} · retrieved {c['retrieved']}")
    out += ["", report["footer"]]
    return "\n".join(out)
