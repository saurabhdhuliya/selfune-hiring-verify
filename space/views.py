"""HTML for the Space tabs. Pure functions of report dicts: no Gradio, no model, no I/O, so they are testable.

Verifies process, not people. Nothing here scores, ranks or rejects anyone.
"""
from __future__ import annotations

import html

from selfune_hv import mother as mother_mod

REPO = "https://github.com/saurabhdhuliya/selfune-hiring-verify"
BANNER_TEXT = "Do not paste real candidate names or personal data."

COLORS = {"VERIFIED": "#16a34a", "WARN": "#a855f7", "NOT_CHECKED": "#6b7280", "UNVERIFIED": "#ca8a04",
          "CONTRADICTED": "#ea580c", "ESCALATE": "#dc2626"}
PLAIN = {"VERIFIED": "No issue found", "WARN": "Warning", "NOT_CHECKED": "Not checked",
         "UNVERIFIED": "Needs a human answer", "CONTRADICTED": "Contradicted", "ESCALATE": "High risk: review before use"}
CHECK_NAMES = {
    "C01": "Undefined trait", "C02": "Years used as proxy for ability", "C03": "No stated reason",
    "C04": "Weak selection method", "C05": "Four-fifths rule", "C06": "Missing field used as a negative",
    "C07": "Name-swap probe", "C08": "Age or age proxy", "C09": "Emotion / personality inference",
    "C10": "NYC LL144", "C11": "GDPR Art 22", "C12": "Illinois", "C13": "Legal-date timing", "C14": "India DPDP",
    "C15": "Vendor claim used as proof",
}

CSS = """
<style>
.sv{line-height:1.5}
.sv-banner{border:2px solid #ca8a04;background:rgba(202,138,4,.15);border-radius:8px;padding:10px 14px;margin:0 0 12px;font-weight:600}
.sv-badge{display:inline-block;padding:1px 8px;border-radius:6px;font-weight:600;font-size:.85em;white-space:nowrap;border:1px solid var(--c);background:color-mix(in srgb,var(--c) 18%,transparent)}
.sv-table{width:100%;border-collapse:collapse;margin:8px 0}
.sv-table td,.sv-table th{border-bottom:1px solid rgba(128,128,128,.35);padding:8px;vertical-align:top;text-align:left}
.sv-small{opacity:.75;font-size:.85em}
.sv-head{padding:12px 14px;border-radius:8px;margin:8px 0;border:1px solid var(--c);background:color-mix(in srgb,var(--c) 14%,transparent)}
.sv-card{border:1px solid rgba(128,128,128,.4);border-left:5px solid var(--c);border-radius:8px;padding:10px 14px;margin:10px 0}
.sv-card .q{font-size:1.1em;font-weight:700;margin:4px 0}
.sv-wrap{overflow-x:auto}
.sv a{color:inherit;text-decoration:underline}
</style>
"""


def e(s) -> str:
    return html.escape(str(s), quote=True)


def banner() -> str:
    return f'<div class="sv sv-banner">{e(BANNER_TEXT)}</div>' + CSS


def badge(status: str) -> str:
    return f'<span class="sv-badge" style="--c:{COLORS.get(status, "#6b7280")}">{e(PLAIN.get(status, status))}</span>'


def first_sentence(message: str) -> str:
    return message.split(" Source:")[0].strip()


def cites(refs: list[str], citations: dict) -> str:
    parts = [f'{e(r)} · {e(citations[r]["label"])} · <a href="{e(citations[r]["url"])}" target="_blank" rel="noopener">source</a>'
             f' · retrieved {e(citations[r]["retrieved"])}' for r in refs if r in citations]
    return "<br>".join(parts)


def mother_block(items: list[dict], empty: str = "No unverified or contradicted line was found, so nothing needs answering first.") -> str:
    """The 1-3 mother assumptions: the question, what answering it unblocks, and the ledger citation."""
    if not items:
        return f'<h3>Mother assumptions</h3><p class="sv-small">{e(empty)}</p>'
    out = ['<h3>Mother assumptions: answer these first</h3>',
           '<p class="sv-small">Each is an unverified or contradicted link that other links and decisions rest on. '
           "Found by counting dependencies with rules, not by a model.</p>"]
    for m in items:
        cite = cites(m.get("ledger_refs", []), {c["id"]: c for c in m.get("citations", [])})
        out.append(
            f'<div class="sv-card" style="--c:{COLORS.get(m["status"], "#6b7280")}">'
            f'<div>{m["order"]}. {badge(m["status"])} <span class="sv-small">{e(", ".join(m["checks"]))}'
            + (f' · {e(", ".join(m["job_ids"]))}' if m.get("job_ids") else "") + "</span></div>"
            f'<div class="q">{e(m["question"])}</div>'
            f'<div>{e(mother_mod.unblocks_text(m))}</div>'
            + (f'<div class="sv-small">About: {e(m["statement"][:240])}</div>' if m.get("statement") else "")
            + (f'<div class="sv-small">Avoid asking: {e(m["do_not_ask"])}</div>' if m.get("do_not_ask") else "")
            + f'<div class="sv-small">{cite or e(m.get("ledger_note", ""))}</div></div>')
    return "".join(out)


def _foot(extra: str = "") -> str:
    return ('<p class="sv-small">GT-xxxx codes are rows in the open ledger of sources '
            f'(<a href="{REPO}/blob/main/ledger/hiring.jsonl" target="_blank" rel="noopener">see ledger</a>). '
            "Checks the process, not people. Rule baselines tested on synthetic data; accuracy on real hiring data is "
            f"not measured. Not legal advice. {e(extra)}</p>")


def message(text: str) -> str:
    return f'<div class="sv"><p>{e(text)}</p></div>'


# ---------------------------------------------------------------- tab 1
def job_post(report: dict, split_note: str) -> str:
    items, status = report["items"], report["status"]
    flagged = sum(1 for i in items if i["status"] != "VERIFIED")
    out = ['<div class="sv">', CSS]
    if not items:
        out.append("<p>No requirement-like lines found. Paste a job post with a requirements list.</p>")
        return "".join(out) + _foot() + "</div>"
    out.append(f'<div class="sv-head" style="--c:{COLORS.get(status, "#6b7280")}"><b>Overall: {e(PLAIN.get(status, status))}</b>'
               f"<br>{flagged} of {len(items)} lines flagged · checks {e(', '.join(report['checks']))}"
               f'<br><span class="sv-small">Split into lines by: {e(split_note)}</span></div>')
    out.append(mother_block(report["mother_assumptions"]))
    out.append('<h3>Every line</h3><div class="sv-wrap"><table class="sv-table"><tr><th>Line</th><th>Result</th><th>Why</th></tr>')
    for i in items:
        why = [f"<b>{e(CHECK_NAMES.get(f['check'], f['check']))}</b>: {e(first_sentence(f['message']))} "
               f"<span class='sv-small'>({e(', '.join(f['ledger_refs']))})</span>"
               for f in i["findings"] if f["verdict"] != "VERIFIED"]
        out.append(f"<tr><td>{e(i['text'])}</td><td>{badge(i['status'])}</td>"
                   f"<td>{'<br>'.join(why) or '<span class=sv-small>-</span>'}</td></tr>")
    out.append("</table></div>")
    qs = report["human_questions"]
    if qs:
        out.append(f"<details><summary>All questions for the hiring team ({len(qs)})</summary><ol>")
        for q in qs:
            out.append(f"<li>{e(q['ask'])}" + (f"<br><span class='sv-small'>Avoid asking: {e(q['do_not_ask'])}</span>"
                                                if q.get("do_not_ask") else "") + "</li>")
        out.append("</ol></details>")
    return "".join(out) + _foot() + "</div>"


# ---------------------------------------------------------------- tab 2
def decision(report: dict) -> str:
    status = report["status"]
    nc = report["not_checked"]
    head = PLAIN.get(status, status)
    if status == "VERIFIED" and nc:
        head = f"No issue found by the checks that ran ({len(nc)} not run)"
    out = ['<div class="sv">', CSS,
           f'<div class="sv-head" style="--c:{COLORS.get(status, "#6b7280")}"><b>Overall: {e(head)}</b>'
           + (f"<br>Weakest link: {e(report['weakest_link'])}" if report["weakest_link"] else "")
           + ("<br><b>Blocked by C09</b>: emotion or personality inference is not allowed as evidence." if report["blocked"] else "")
           + ("<br>High risk." if report["high_risk"] else "")
           + (f"<br><span class='sv-small'>Not run: {e(', '.join(nc))}. Not a pass.</span>" if nc else "") + "</div>",
           '<div class="sv-wrap"><table class="sv-table"><tr><th>Check</th><th>Result</th><th>Why</th></tr>']
    for f in report["findings"]:
        out.append(f"<tr><td><b>{e(f['check'])}</b> {e(CHECK_NAMES.get(f['check'], ''))}</td><td>{badge(f['verdict'])}</td>"
                   f"<td>{e(first_sentence(f['message']))}"
                   + (f"<div class='sv-small'>{e(', '.join(f['ledger_refs']))}</div>" if f["ledger_refs"] else "") + "</td></tr>")
    out.append("</table></div>")
    qs = report["human_questions"]
    out.append("<h3>Questions for the hiring team</h3>")
    if qs:
        out.append("<ol>")
        for q in qs:
            out.append(f"<li><b>{e(q['ask'])}</b><br><span class='sv-small'>{e(q['why'])}"
                       + (f" Avoid asking: {e(q['do_not_ask'])}" if q.get("do_not_ask") else "") + "</span></li>")
        out.append("</ol>")
    else:
        out.append('<p class="sv-small">None.</p>')
    cited = [c for c in report["citations"].values()]
    if cited:
        out.append("<h3>Sources</h3><p class='sv-small'>" + "<br>".join(cites([c["id"]], report["citations"]) for c in cited) + "</p>")
    return "".join(out) + _foot() + "</div>"


# ---------------------------------------------------------------- tab 3
def audit(report: dict, label: str) -> str:
    """Summary above the inline report.html."""
    s = report["summary"]
    return (f'<div class="sv">{CSS}<div class="sv-head" style="--c:#6b7280"><b>{e(label)}</b>: {s["chains"]} decision chains, '
            f'{s["job_level_issues"]} job-level issues, {s["human_questions"]} questions. Chains by status: '
            + e(", ".join(f"{k} {v}" for k, v in sorted(s["chains_by_status"].items()))) + ".</div></div>")


def report_frame(report_html: str, height: int = 900) -> str:
    """The full report.html, inline. Sandboxed: no scripts run in it."""
    return (f'<iframe title="report.html" sandbox srcdoc="{html.escape(report_html, quote=True)}" '
            f'style="width:100%;height:{height}px;border:1px solid rgba(128,128,128,.4);border-radius:8px;background:#fff"></iframe>')


# ---------------------------------------------------------------- tab 4
DIAGRAM = """
<svg viewBox="0 0 940 330" role="img" aria-label="Decision chain: role need, requirement, evidence, decision; job-level flags feed evidence" style="width:100%;max-width:940px;font-family:system-ui,sans-serif">
  <defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="currentColor"/></marker></defs>
  <g fill="none" stroke="currentColor" stroke-width="2">
    <rect x="10" y="110" width="190" height="70" rx="10"/><rect x="250" y="110" width="190" height="70" rx="10"/>
    <rect x="490" y="110" width="190" height="70" rx="10"/><rect x="730" y="110" width="190" height="70" rx="10"/>
    <path d="M200 145H246" marker-end="url(#ar)"/><path d="M440 145H486" marker-end="url(#ar)"/><path d="M680 145H726" marker-end="url(#ar)"/>
    <rect x="440" y="10" width="300" height="52" rx="10" stroke-dasharray="6 4"/><path d="M585 62V106" marker-end="url(#ar)"/>
    <rect x="10" y="240" width="910" height="64" rx="10" stroke="#ca8a04" stroke-width="3"/>
  </g>
  <g fill="currentColor" font-size="15" text-anchor="middle">
    <text x="105" y="140" font-weight="700">N  Role need</text><text x="105" y="162" font-size="12">why the role exists</text>
    <text x="345" y="140" font-weight="700">R  Requirement</text><text x="345" y="162" font-size="12">C01 C02 C03</text>
    <text x="585" y="140" font-weight="700">E  Evidence</text><text x="585" y="162" font-size="12">C06 C09 C15</text>
    <text x="825" y="140" font-weight="700">D  Decision</text><text x="825" y="162" font-size="12">C08 C11</text>
    <text x="590" y="32" font-weight="700">Job-level flags</text><text x="590" y="52" font-size="12">tool · selection method · group counts · AI text · policy</text>
    <text x="465" y="266" font-weight="700">Mother assumption</text>
    <text x="465" y="290" font-size="13">the flagged link with the most decisions and links resting on it: answer it first</text>
  </g>
</svg>
"""

CHECKS = [
    ("C01", "Undefined trait", "Requirement", "Rule baseline"), ("C02", "Years used as proxy for ability", "Requirement", "Rule baseline"),
    ("C03", "No stated reason", "Requirement", "Rule baseline"), ("C04", "Weak selection method", "Job-level", "Code"),
    ("C05", "Four-fifths rule on group counts", "Job-level", "Code"), ("C06", "Missing field used as a negative", "Evidence", "Rule baseline"),
    ("C07", "Name-swap probe", "Job-level (tool)", "Code"), ("C08", "Age or age proxy", "Requirement, tool, decision", "Code"),
    ("C09", "Emotion or personality inference (blocks the chain)", "Evidence, tool, text", "Code"),
    ("C10", "NYC LL144", "Job-level (tool)", "Code"), ("C11", "GDPR Art 22", "Decision, tool", "Code"),
    ("C12", "Illinois", "Job-level (tool)", "Code"), ("C13", "Legal-date timing", "Job-level (policy)", "Code"),
    ("C14", "India DPDP", "Job-level (tool)", "Code"), ("C15", "Vendor claim used as proof", "Evidence, text", "Rule baseline"),
]

# From README.md "Test results (v0.1, 2026-11-12)": planted caught, clean false alarms, release.
TEST_SCORES = [
    ("C01", "5/5", "0/13"), ("C02", "3/3", "0/13"), ("C03", "9/9", "0/7"), ("C04", "2/2", "0/1"), ("C05", "2/2", "0/2"),
    ("C06", "4/4", "0/4"), ("C07", "4/4", "0/4"), ("C08", "2/2", "0/3"), ("C09", "4/4", "0/6"), ("C10", "3/3", "0/3"),
    ("C11", "2/2", "0/3"), ("C12", "1/1", "0/1"), ("C13", "1/1", "0/1"), ("C14", "2/2", "0/2"), ("C15", "3/3", "0/2"),
]

LIMITS = [
    "<b>Synthetic data.</b> The test set and the checks were written in the same project, and the C01-C03 labels follow "
    "each check's stated rule. A perfect score shows the checks follow their rules on this data, not that they are right "
    "on real hiring data.",
    "<b>Rule baselines.</b> C01, C02, C03, C06 and C15 are keyword and pattern rules. Unclear cases go to a human.",
    "<b>The optional model only cuts text into claims.</b> Rules decide every verdict. Each claim must use only words from "
    "your text; if the model fails or rewrites, the Space falls back to line splitting.",
    "<b>Mother assumptions are dependency counts, not importance.</b> In a pasted job post there are no decisions yet, so "
    "answering counts one downstream link and the order falls back to severity, then position.",
    "<b>Real-world accuracy is unmeasured.</b> No check has been scored on real postings or decisions.",
    "<b>Not legal advice.</b> Legal checks flag for review and cite a ledger row with its source and date. Check the "
    "source before relying on a row.",
]


def how_it_works() -> str:
    rows = "".join(f"<tr><td><b>{c}</b></td><td>{e(n)}</td><td>{e(where)}</td><td>{e(kind)}</td></tr>" for c, n, where, kind in CHECKS)
    scores = "".join(f"<tr><td><b>{c}</b></td><td>{e(CHECK_NAMES[c])}</td><td>{p}</td><td>{f}</td><td>PASS</td></tr>"
                     for c, p, f in TEST_SCORES)
    return (f'<div class="sv">{CSS}<h3>Decision chain</h3>'
            "<p>Every decision becomes a chain. Each link gets its own verdict; the chain is only as strong as its weakest link. "
            "Flags on tools or the selection method are job-level: they are reported once and feed the evidence of every decision they affect.</p>"
            f"{DIAGRAM}"
            "<p><b>Verdicts:</b> VERIFIED, UNVERIFIED, CONTRADICTED, ESCALATE (high risk), NOT_CHECKED (input missing: never a pass), "
            "WARN (rests on a contested or pending ledger row: never a fail).</p>"
            "<p><b>Hard rules:</b> it never scores, ranks or rejects people. No emotion or personality inference. LLM output is never "
            "evidence. Nothing you paste or upload is stored.</p>"
            f'<h3>The 15 checks</h3><div class="sv-wrap"><table class="sv-table"><tr><th>ID</th><th>Check</th><th>Applies to</th><th>Kind</th></tr>{rows}</table></div>'
            f'<h3>Test scores</h3><p class="sv-small">Synthetic test set (v0.1, 2026-11-12): 115 scored items, 47 planted, 65 clean, 3 NOT_CHECKED. '
            "Release rule: every check catches 100% of planted cases and false alarms stay under 10%. "
            "C09 corpus (496 template texts): 248/248 caught, 0/248 false alarms. Unit tests pass.</p>"
            f'<div class="sv-wrap"><table class="sv-table"><tr><th>ID</th><th>Check</th><th>Planted caught</th><th>Clean false alarms</th><th>Release</th></tr>{scores}</table></div>'
            "<h3>Limits</h3><ul>" + "".join(f"<li>{x}</li>" for x in LIMITS) + "</ul>"
            f'<p class="sv-small">Open source: <a href="{REPO}" target="_blank" rel="noopener">GitHub</a>. Verifies process, not people. Not legal advice.</p></div>')
