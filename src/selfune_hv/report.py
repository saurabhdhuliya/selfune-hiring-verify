"""Run every check, build one decision chain per decision, and render the report. No LLM.

The report verifies the PROCESS, never the person (hard rule 2): no candidate is ranked or scored,
and the HTML page never shows a candidate reference. Never reads labels/.
"""
from __future__ import annotations

import html
import importlib
import json
import pkgutil
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from selfune_hv import ledger as ledger_mod
from selfune_hv.checks import c01_undefined_trait, c02_years_proxy
from selfune_hv.decision_chain import SEVERITY, HumanQuestion, Link, build_chain
from selfune_hv.role_memory import RoleMemory

import selfune_hv.checks as checks_pkg

REPO_ROOT = Path(__file__).resolve().parents[2]
LEGAL_CHECKS = {"C08", "C10", "C11", "C12", "C13", "C14"}
REQ_CHECKS = ["C01", "C02", "C03"]
EVIDENCE_CHECKS = ["C06", "C15", "C09"]
DECISION_CHECKS = ["C08", "C11"]
FOOTER = "Verifies process, not people. Not legal advice."
C06_ALTERNATIVES = ["The field was optional and skipped.", "A form or parsing error dropped it.",
                    "The information exists but was never requested."]


# ---------------------------------------------------------------- inputs
def _jl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _j(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_data(root: Path) -> dict:
    s = root / "data/synthetic"
    return {"company": _j(s / "company.json"), "tools": _j(s / "tools.json"),
            "decisions": _jl(s / "decisions.jsonl"), "ai_text": _jl(s / "ai_text.jsonl"),
            "probes": _jl(s / "tool_probes.jsonl"), "policies": _jl(s / "policy_statements.jsonl"),
            "ledger": ledger_mod.load(str(root / "ledger/hiring.jsonl"))}


def collect_findings(root: Path) -> list[dict]:
    """Every check's run(root). Corpus runs are for scoring only and are not part of the report."""
    out = []
    for m in sorted(pkgutil.iter_modules(checks_pkg.__path__), key=lambda m: m.name):
        mod = importlib.import_module(f"{checks_pkg.__name__}.{m.name}")
        if hasattr(mod, "CHECK_ID") and hasattr(mod, "run"):
            out.extend(mod.run(root))
    return out


def worst(statuses) -> str:
    statuses = list(statuses)
    return max(statuses, key=lambda s: SEVERITY[s]) if statuses else "NOT_CHECKED"


def short_message(msg: str) -> str:
    """The finding message without its citation tail (citations are shown separately)."""
    return msg.split(" Source: ")[0].strip()


# ---------------------------------------------------------------- object -> job
def job_index(data: dict) -> dict[str, set[str]]:
    idx: dict[str, set[str]] = defaultdict(set)
    for j in data["company"]["jobs"]:
        idx[f"job:{j['job_id']}"].add(j["job_id"])
        idx[f"group_counts:{j['job_id']}"].add(j["job_id"])
        for r in j.get("requirements", []):
            idx[f"requirement:{r['req_id']}"].add(j["job_id"])
    for t in data["tools"]:
        idx[f"tool:{t['tool_id']}"].update(t.get("job_ids") or [])
    for t in data["ai_text"]:
        idx[f"ai_text:{t['text_id']}"].add(t.get("job_id"))
    for p in data["probes"]:
        idx[f"probe_pair:{p['pair_id']}"].add(p.get("job_id"))
    for s in data["policies"]:
        if s.get("job_id"):
            idx[f"policy:{s['stmt_id']}"].add(s["job_id"])
    for d in data["decisions"]:
        idx[f"decision:{d['decision_id']}"].add(d["job_id"])
    return idx


def jobs_for(ref: str, idx: dict[str, set[str]]) -> set[str]:
    parts = ref.split(":")
    for n in range(len(parts), 0, -1):   # "tool:T1:notice" -> "tool:T1"; "group_counts:J1:age_band" -> "group_counts:J1"
        key = ":".join(parts[:n])
        if key in idx:
            return idx[key]
    return set()


# ---------------------------------------------------------------- questions
def _q(link_id: str, ask: str, why: str, do_not_ask: str = "", store: str = "decision_record") -> HumanQuestion:
    return HumanQuestion(link_id=link_id, ask=ask, why=why, do_not_ask=do_not_ask, store_answer_in=store)


def _short(text: str, words: int = 8) -> str:
    w = text.rstrip(".").split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def _a(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def requirement_questions(link_id: str, req: dict, title: str, flags: dict[str, dict]) -> list[tuple[tuple, HumanQuestion]]:
    """At most one (dedup key, question) per requirement: C01 first, then C02, then C03.

    The C01 question already asks how the trait helps the role, so it covers C03 too.
    Key = one question per role per trait (C01) or per requirement (C02, C03).
    """
    job = req["req_id"].split("-")[0]
    flagged = {c: f for c, f in flags.items() if f["verdict"] != "VERIFIED"}
    why_more = [c for c in ("C02", "C03") if c in flagged]
    if "C01" in flagged:
        f = flagged["C01"]
        words = c01_undefined_trait.trait_words(req["text"])
        key = (job, "C01", f.get("trait_ref") or tuple(words))
        return [(key, _q(link_id, f["question"], f"Until defined, '{', '.join(words)}' can't be checked against evidence."
                         + (f" Also flagged: {', '.join(why_more)}." if why_more else ""),
                         "Don't ask about personality, attitude or 'fit'; ask for an observable result.", "role_memory"))]
    if "C02" in flagged:
        years = ", ".join(c02_years_proxy.years_counts(req["text"]))
        why = "Years of experience is a proxy; the ability itself is not checked."
        if "C03" in flagged:
            why += " No reason is stated either (C03)."
        return [((job, "REQ", req["req_id"]),
                 _q(link_id, f"What should {years} show for this role, and could a work sample test that directly?",
                    why, "Don't ask whether younger applicants could cope.", "role_memory"))]
    if "C03" in flagged:
        return [((job, "REQ", req["req_id"]),
                 _q(link_id, f'How does "{_short(req["text"])}" help {_a(title)} {title} succeed?',
                    "No stated reason links this requirement to the role need.",
                    "Don't ask 'is this a nice-to-have?'; ask what fails without it.", "role_memory"))]
    return []


def decision_questions(d: dict, e_flags: dict[str, dict], d_flags: dict[str, dict]) -> list[tuple[tuple, HumanQuestion]]:
    job, out = d["job_id"], []
    f = e_flags.get("C06")
    if f and f["verdict"] != "VERIFIED":
        fields = " and ".join(x.replace("_", " ") for x in d.get("fields_missing", []))
        ask = f"Can the applicant supply {fields}, or can this decision rest on data already present?"
        out.append(((job, "C06", ask), _q("E1", ask, "An empty field is a fact, not evidence about the applicant.",
                                           "Don't ask what the gap says about the applicant.")))
    f = e_flags.get("C15")
    if f and f["verdict"] != "VERIFIED":
        ask = "What data from your own process shows this vendor claim holds for this role?"
        out.append(((job, "C15", ask), _q("E1", ask, "A vendor's claim is context, not proof.")))
    f = d_flags.get("C11")
    if f and f["verdict"] == "ESCALATE":
        ask = "Who reviewed this automated decision, and how can the applicant contest it?"
        out.append(((job, "C11", ask), _q("D1", ask, "GDPR Art 22 needs human intervention and a way to contest.")))
    elif f and f["verdict"] == "NOT_CHECKED":
        ask = "Was this decision made by a person, a tool, or both?"
        out.append(((job, "C11-who", ask), _q("D1", ask, "Without it, solely automated decisions can't be ruled out.")))
    f = d_flags.get("C08")
    if f and f["verdict"] != "VERIFIED":
        ask = "What job-related reason, other than age or graduation year, supports this outcome?"
        out.append(((job, "C08", ask), _q("D1", ask, "Age and age proxies are high legal risk.",
                                           "Don't ask the applicant's age or graduation year.")))
    return out


# ---------------------------------------------------------------- chains
def build_chains(data: dict, findings: list[dict], root: Path, today: date | None = None):
    by_ref: dict[str, dict[str, dict]] = defaultdict(dict)
    for f in findings:
        by_ref[f["object_ref"]][f["check"]] = f
    memory = RoleMemory.load(str(root / "data/synthetic/role_memory.json"), today)
    jobs = {j["job_id"]: j for j in data["company"]["jobs"]}
    chains, questions = [], {}

    def link_from(link_id, typ, statement, flags: dict[str, dict], depends, base_route="code", inherited=False, **extra):
        status = worst(f["verdict"] for f in flags.values()) if flags else "NOT_CHECKED"
        refs = sorted({r for f in flags.values() for r in f["ledger_refs"]})
        notes = [f"{c}: {short_message(f['message'])}" for c, f in sorted(flags.items()) if f["verdict"] != "VERIFIED"]
        if not flags:
            notes = ["No check covered this link."]
        route = base_route if status == "VERIFIED" else "human"
        return Link(link_id=link_id, type=typ, statement=statement, status=status, route=route, depends_on=depends,
                    ledger_refs=refs, check_refs=sorted(flags), note=" | ".join(notes), inherited=inherited, **extra)

    for d in data["decisions"]:
        job = jobs[d["job_id"]]
        need = memory.role_need(job["job_id"])
        # Role need and requirements come from job-level findings: inherited, left out of the roll-up.
        links = [Link("N1", "role_need", need or f"No role need recorded for {job['title']}.",
                      "VERIFIED" if need else "NOT_CHECKED", "role_memory" if need else "human", inherited=True)]
        job_qs: list[tuple[tuple, HumanQuestion]] = []   # report-level only, not repeated in every chain
        qs: list[tuple[tuple, HumanQuestion]] = []       # this decision's own links
        if not need:
            job_qs.append(((job["job_id"], "N"), _q("N1", f"In one sentence, why does the {job['title']} role exist?",
                                                     "Every requirement is checked against the role need.", store="role_memory")))
        r_ids = []
        for r in job.get("requirements", []):
            lid = "R" + r["req_id"].split("-R")[-1]
            flags = {c: f for c, f in by_ref[f"requirement:{r['req_id']}"].items() if c in REQ_CHECKS}
            trait = flags.get("C01", {}).get("trait_ref")
            links.append(link_from(lid, "requirement", r["text"], flags, ["N1"],
                                   "role_memory" if trait else "code", trait_ref=trait, inherited=True))
            job_qs += requirement_questions(lid, r, job["title"], flags)
            r_ids.append(lid)
        dflags = by_ref[f"decision:{d['decision_id']}"]
        e_flags = {c: f for c, f in dflags.items() if c in EVIDENCE_CHECKS}
        # C09 on a tool counts for this decision only if the decision lists that tool in tools_used.
        used_c09 = [by_ref[f"tool:{t}"]["C09"] for t in d.get("tools_used", []) if "C09" in by_ref.get(f"tool:{t}", {})]
        if used_c09:
            tool_c09 = max(used_c09, key=lambda f: SEVERITY[f["verdict"]])
            if "C09" not in e_flags or SEVERITY[tool_c09["verdict"]] > SEVERITY[e_flags["C09"]["verdict"]]:
                e_flags["C09"] = tool_c09
        extra = {"observed": d.get("reason_text", ""), "observed_confidence": "High"}
        if e_flags.get("C06", {}).get("verdict") == "UNVERIFIED":
            extra = {"observed": f"Field(s) empty: {', '.join(d['fields_missing'])}.", "observed_confidence": "High",
                     "inferred": d.get("reason_text", ""), "inference_confidence": "Low",
                     "fields_missing": list(d["fields_missing"]), "alternative_explanations": C06_ALTERNATIVES}
        links.append(link_from("E1", "evidence", f"Stated reason: {d.get('reason_text', '')}", e_flags, r_ids, **extra))
        d_flags = {c: f for c, f in dflags.items() if c in DECISION_CHECKS}
        by = d.get("decided_by") or "not recorded"
        links.append(link_from("D1", "decision", f"Outcome '{d['outcome']}' at {d['stage']}, decided by {by}.",
                               d_flags, ["E1"]))
        qs += decision_questions(d, e_flags, d_flags)

        high_risk = d.get("decided_by") == "tool" or any(
            c in LEGAL_CHECKS and f["verdict"] not in ("VERIFIED", "WARN") for c, f in dflags.items())
        blocked = e_flags.get("C09", {}).get("verdict") == "ESCALATE"
        chain = build_chain(f"CH-{d['decision_id']}", job["job_id"], d["candidate_ref"], d["stage"], links,
                            [q for _, q in qs], high_risk=high_risk, blocked=blocked)
        chain["_decision"] = {"decision_id": d["decision_id"], "outcome": d["outcome"],
                              "decided_by": d.get("decided_by"), "high_risk": high_risk,
                              "tools_used": d.get("tools_used")}
        chains.append(chain)
        for key, q in job_qs + qs:
            entry = questions.setdefault(key, {"job_id": job["job_id"], "ask": q.ask, "why": q.why,
                                               "do_not_ask": q.do_not_ask, "store_answer_in": q.store_answer_in,
                                               "about": None, "applies_to": []})
            if q.link_id.startswith("R"):
                entry["about"] = f"requirement:{job['job_id']}-{q.link_id}"
            entry["applies_to"].append(d["decision_id"])
    return chains, list(questions.values())


# ---------------------------------------------------------------- ledger
def citation(row: dict) -> dict:
    return {"id": row["id"], "label": row["display_label"], "url": row["evidence"]["url"],
            "retrieved": row["evidence"]["retrieved"]}


def ledger_warnings(rows: dict[str, dict], cited: set[str], today: date) -> list[dict]:
    out = []
    for rid in sorted(cited):
        r = rows[rid]
        reasons = []
        if date.fromisoformat(r["recheck_by"]) < today:
            reasons.append(f"expired on {r['recheck_by']}")
        if r["user_decision"] != "LOCKED":
            reasons.append(f"{r['user_decision']}: awaits a human re-lock")
        if r["use_as"] == "warn_only" or r.get("status") == "CONTESTED":
            reasons.append("contested: warning only")
        if reasons:
            out.append({**citation(r), "warnings": reasons})
    return out


# ---------------------------------------------------------------- job-level issues
CATEGORIES = [("requirement:", "requirement"), ("job:", "selection method"), ("tool:", "tool"),
              ("probe_pair:", "tool (name-swap probe)"), ("group_counts:", "group counts"),
              ("ai_text:", "AI-written text"), ("policy:", "policy statement")]


def category(ref: str) -> str:
    return next((name for prefix, name in CATEGORIES if ref.startswith(prefix)), "other")


def job_level_issues(findings: list[dict], data: dict) -> list[dict]:
    """One row per non-VERIFIED job-level finding, with how many decisions it affects.

    A tool flag affects a decision in the tool's jobs unless that decision lists tools_used without the tool.
    """
    probe_tool = {p["pair_id"]: p.get("tool_id") for p in data["probes"]}
    rows = []
    for f in findings:
        if f["verdict"] == "VERIFIED" or f["object_ref"].startswith("decision:"):
            continue
        jobs = set(f.get("job_ids", []))
        ref = f["object_ref"]
        tool = ref.split(":")[1] if ref.startswith("tool:") else probe_tool.get(ref.split(":")[1]) if ref.startswith("probe_pair:") else None
        affected = [d["decision_id"] for d in data["decisions"] if d["job_id"] in jobs
                    and (tool is None or "tools_used" not in d or tool in d["tools_used"])]
        rows.append({"object_ref": ref, "category": category(ref), "check": f["check"], "verdict": f["verdict"],
                     "job_ids": sorted(jobs), "tool_id": tool, "affects_decisions": len(affected),
                     "ledger_refs": f["ledger_refs"], "message": short_message(f["message"])})
    order = {v: i for i, v in enumerate(["ESCALATE", "CONTRADICTED", "UNVERIFIED", "NOT_CHECKED", "WARN"])}
    rows.sort(key=lambda r: (r["job_ids"], order.get(r["verdict"], 9), r["object_ref"], r["check"]))
    return rows


# ---------------------------------------------------------------- report
def build_report(root: Path = REPO_ROOT, today: date | None = None) -> dict:
    root = Path(root)
    today = today or date.today()
    data = load_data(root)
    findings = collect_findings(root)
    chains, questions = build_chains(data, findings, root, today)
    idx = job_index(data)
    non_decision = [f for f in findings if not f["object_ref"].startswith("decision:")]
    for f in non_decision:
        f["job_ids"] = sorted(j for j in jobs_for(f["object_ref"], idx) if j)
    cited = {r for f in findings for r in f["ledger_refs"]}
    issues = job_level_issues(non_decision, data)
    return {
        "employer": data["company"]["employer_name"],
        "generated_on": today.isoformat(),
        "summary": {
            "job_level_issues": len(issues),
            "job_level_issues_by_verdict": dict(Counter(i["verdict"] for i in issues)),
            "chains": len(chains),
            "chains_by_status": dict(Counter(c["chain_status"] for c in chains)),
            "findings_by_verdict": dict(Counter(f["verdict"] for f in findings)),
            "blocked_chains": sum(c["blocked"] for c in chains),
            "human_questions": len(questions),
        },
        "job_level_issues": issues,
        "questions": questions,
        "chains": chains,
        "job_and_tool_findings": non_decision,
        "ledger_warnings": ledger_warnings(data["ledger"], cited, today),
        "citations": {rid: citation(data["ledger"][rid]) for rid in sorted(cited)},
        "jobs": [{"job_id": j["job_id"], "title": j["title"], "jurisdiction": j.get("jurisdiction", []),
                  "requirements": j.get("requirements", [])} for j in data["company"]["jobs"]],
        "tools": [{"tool_id": t["tool_id"], "name": t.get("name", ""), "job_ids": t.get("job_ids", [])}
                  for t in data["tools"]],
    }


def chains_for_schema(report: dict) -> list[dict]:
    """Chains without the report-only `_decision` helper field."""
    return [{k: v for k, v in c.items() if k != "_decision"} for c in report["chains"]]


# ---------------------------------------------------------------- HTML
ORDER = ["ESCALATE", "CONTRADICTED", "UNVERIFIED", "NOT_CHECKED", "WARN", "VERIFIED"]
_CSS = """
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#57534e;--card:#fff;--line:#e7e5e4;
--ESCALATE:#b91c1c;--CONTRADICTED:#c2410c;--UNVERIFIED:#a16207;--NOT_CHECKED:#6b7280;--WARN:#7c3aed;--VERIFIED:#15803d}
@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--muted:#a8a29e;--card:#292524;--line:#44403c;
--ESCALATE:#f87171;--CONTRADICTED:#fb923c;--UNVERIFIED:#facc15;--NOT_CHECKED:#9ca3af;--WARN:#c4b5fd;--VERIFIED:#4ade80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}h1{margin:0 0 4px}h2{margin-top:40px;border-bottom:2px solid var(--line);padding-bottom:4px}
h3{margin:24px 0 8px}.muted{color:var(--muted)}.cards{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;min-width:120px}
.card b{display:block;font-size:24px}.v{font-weight:600;font-size:12px;padding:1px 6px;border-radius:4px;border:1px solid currentColor;white-space:nowrap}
.flag{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:6px;padding:8px 12px;margin:8px 0}
.cite{font-size:12px;color:var(--muted);margin-top:4px;word-break:break-all}.cite a{color:inherit}
ol.q li{margin:10px 0}table{width:100%;border-collapse:collapse;font-size:13px}td,th{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}
details{margin:8px 0}summary{cursor:pointer;font-weight:600}.wrap{overflow-x:auto}
footer{margin-top:48px;padding-top:12px;border-top:1px solid var(--line);color:var(--muted)}
"""
for _v in ORDER:
    _CSS += f".v.{_v}{{color:var(--{_v})}}.flag.{_v}{{border-left-color:var(--{_v})}}"


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _badge(v: str) -> str:
    return f'<span class="v {v}">{v}</span>'


def _cites(refs: list[str], cites: dict) -> str:
    if not refs:
        return '<div class="cite">No ledger row: code result on the employer\'s data.</div>'
    parts = [f'{_e(r)} · <a href="{_e(cites[r]["url"])}">{_e(cites[r]["url"])}</a> · retrieved {_e(cites[r]["retrieved"])}'
             for r in refs]
    return '<div class="cite">' + "<br>".join(parts) + "</div>"


def _flag(f: dict, cites: dict, title: str = "") -> str:
    head = f"{_badge(f['verdict'])} <b>{_e(f['check'])}</b> {_e(title or f['object_ref'])}"
    return (f'<div class="flag {f["verdict"]}">{head}<div>{_e(short_message(f["message"]))}</div>'
            f'{_cites(f["ledger_refs"], cites)}</div>')


def render_html(report: dict) -> str:
    cites = report["citations"]
    s = report["summary"]
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Process Verification Report</title><style>{_CSS}</style></head><body><main>",
           f"<h1>Hiring process verification</h1><div class='muted'>{_e(report['employer'])} · generated {_e(report['generated_on'])} · "
           f"{s['chains']} decision chains</div>"]
    issues = report["job_level_issues"]
    out.append(f"<h2>Job-level issues ({len(issues)})</h2><div class='muted'>Flags on requirements, selection method, "
               "tools and group counts. Each is reported once here, not repeated in every decision chain.</div><div class='cards'>")
    for v in ORDER:
        if s["job_level_issues_by_verdict"].get(v):
            out.append(f"<div class='card'>{_badge(v)}<b>{s['job_level_issues_by_verdict'][v]}</b></div>")
    out.append("</div><div class='wrap'><table><tr><th>Job</th><th>Issue</th><th>Check</th><th>Verdict</th>"
               "<th>Affects</th><th>Source</th></tr>")
    for i in issues:
        out.append(f"<tr><td>{_e(', '.join(i['job_ids']))}</td><td>{_e(i['category'])}: {_e(i['object_ref'])}"
                   f"<div class='muted'>{_e(_short(i['message'], 18))}</div></td><td>{_e(i['check'])}</td>"
                   f"<td>{_badge(i['verdict'])}</td><td>affects {i['affects_decisions']} decision"
                   f"{'s' if i['affects_decisions'] != 1 else ''}</td><td>{_cites(i['ledger_refs'], cites)}</td></tr>")
    out.append("</table></div><h2>Decision chains by verdict</h2><div class='muted'>From each decision's own evidence "
               "and decision links only (C06, C08, C09, C11, C15).</div><div class='cards'>")
    for v in ORDER:
        if s["chains_by_status"].get(v):
            out.append(f"<div class='card'>{_badge(v)}<b>{s['chains_by_status'][v]}</b></div>")
    out.append("</div><div class='muted'>All findings: " + ", ".join(
        f"{v} {s['findings_by_verdict'][v]}" for v in ORDER if s["findings_by_verdict"].get(v)) +
        f". Blocked chains: {s['blocked_chains']}.</div>")

    out.append(f"<h2>Questions for you ({len(report['questions'])})</h2><ol class='q'>")
    for q in sorted(report["questions"], key=lambda q: (q["job_id"], q["store_answer_in"] != "role_memory")):
        where = "saved to role memory, asked once" if q["store_answer_in"] == "role_memory" else "for the decision record"
        n = len(q["applies_to"])
        out.append(f"<li><b>{_e(q['ask'])}</b><div class='muted'>{_e(q['job_id'])} · {_e(q['why'])} · {where} · "
                   f"affects {n} decision{'s' if n != 1 else ''}</div>"
                   + (f"<div class='muted'>Avoid: {_e(q['do_not_ask'])}</div>" if q["do_not_ask"] else "") + "</li>")
    out.append("</ol>")

    if report["ledger_warnings"]:
        out.append("<h2>Ledger warnings</h2>")
        for w in report["ledger_warnings"]:
            out.append(f"<div class='flag WARN'>{_badge('WARN')} <b>{_e(w['id'])}</b> {_e('; '.join(w['warnings']))}"
                       f"{_cites([w['id']], cites)}</div>")

    tools = {t["tool_id"]: t for t in report["tools"]}
    flags = [f for f in report["job_and_tool_findings"] if f["verdict"] != "VERIFIED"]
    for job in report["jobs"]:
        jid = job["job_id"]
        out.append(f"<h2>{_e(jid)} {_e(job['title'])} <span class='muted'>({_e(', '.join(job['jurisdiction']))})</span></h2>")
        out.append("<h3>Requirement flags</h3>")
        reqs = {r["req_id"]: r["text"] for r in job["requirements"]}
        req_flags = [f for f in flags if f["object_ref"].startswith("requirement:") and f["object_ref"].split(":")[1] in reqs]
        if not req_flags:
            out.append("<div class='muted'>None.</div>")
        for rid, text in reqs.items():
            fs = [f for f in req_flags if f["object_ref"] == f"requirement:{rid}"]
            if fs:
                out.append(f"<div><b>{_e(rid)}</b> {_e(text)}</div>" + "".join(_flag(f, cites, rid) for f in fs))
        out.append("<h3>Tool flags</h3>")
        tool_flags = [f for f in flags if f["object_ref"].startswith("tool:") and jid in f["job_ids"]]
        if not tool_flags:
            out.append("<div class='muted'>None.</div>")
        for f in tool_flags:
            tid = f["object_ref"].split(":")[1]
            out.append(_flag(f, cites, f"{f['object_ref']} ({tools.get(tid, {}).get('name', '')})"))
        other = [f for f in flags if jid in f["job_ids"] and not f["object_ref"].startswith(("tool:", "requirement:"))]
        if other:
            out.append("<h3>Other process flags</h3>" + "".join(_flag(f, cites) for f in other))

        out.append("<h3>Decisions by chain status</h3>")
        job_chains = [c for c in report["chains"] if c["job_id"] == jid]
        for v in ORDER:
            group = sorted((c for c in job_chains if c["chain_status"] == v), key=lambda c: c["_decision"]["decision_id"])
            if not group:
                continue
            out.append(f"<details{' open' if v in ('ESCALATE', 'CONTRADICTED') else ''}><summary>{_badge(v)} "
                       f"{len(group)} decision{'s' if len(group) != 1 else ''}</summary><div class='wrap'><table>"
                       "<tr><th>Decision</th><th>Stage / outcome</th><th>Weakest link</th><th>This decision's own links</th></tr>")
            for c in group:
                links = {l["link_id"]: l for l in c["links"]}
                wl = links.get(c["weakest_link"]) if c["weakest_link"] else None
                weak = (f"{_e(wl['link_id'])} {_badge(wl['status'])} {_e(_short(wl['statement'], 12))}" if wl else "none")
                own = []
                for lid in ("E1", "D1"):
                    l = links[lid]
                    if l["status"] != "VERIFIED":
                        own.append(f"{lid} {_badge(l['status'])} {_e(', '.join(l.get('check_refs', [])))}: {_e(l.get('note', ''))}"
                                   + _cites(l.get("ledger_refs", []), cites))
                d = c["_decision"]
                hr = " · high risk" if d["high_risk"] else ""
                out.append(f"<tr><td>{_e(d['decision_id'])}</td><td>{_e(c['stage'])} / {_e(d['outcome'])}"
                           f"<div class='muted'>decided by {_e(d['decided_by'] or 'not recorded')}{hr}</div></td>"
                           f"<td>{weak}</td><td>{'<br>'.join(own) or '<span class=muted>no own flags</span>'}</td></tr>")
            out.append("</table></div></details>")
    out.append(f"<footer>{_e(FOOTER)}</footer></main></body></html>")
    return "\n".join(out)
