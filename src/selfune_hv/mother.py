"""Mother assumptions: the few unverified things that most decisions rest on. No LLM.

Each decision chain is a dependency graph: role need -> requirement -> evidence -> decision, plus job-level
flags (tool, selection method, group counts, AI text, policy) that feed the evidence of every decision they affect.
For every flagged node (UNVERIFIED, CONTRADICTED, or ESCALATE, which is a high-risk UNVERIFIED/CONTRADICTED) we
count what depends on it, merge nodes that raise the same question, and return the top 1-3.

A role need that is not recorded (NOT_CHECKED) counts as an unverified assumption too: everything below it rests on it.

Verifies process, not people. The graph holds no candidate data, and nothing here scores, ranks or rejects anyone
(hard rule 2). Every question is under 25 words and comes from rules, never from an LLM (hard rule 4).
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from selfune_hv.decision_chain import MAX_QUESTION_WORDS, SEVERITY

FLAGGED = ("UNVERIFIED", "CONTRADICTED", "ESCALATE")
TOP_N = 3
NO_LEDGER_ROW = "No ledger row: code result on the employer's data."

# Decision-level question keys (report["questions"][i]["check"]) -> (check whose verdict gates it, link it sits on).
DECISION_QUESTIONS = {"C06": ("C06", "E1"), "C15": ("C15", "E1"), "C11": ("C11", "D1"),
                      "C11-who": ("C11-who", "D1"), "C08": ("C08", "D1")}


# ---------------------------------------------------------------- graph
@dataclass
class _Node:
    node_id: str
    kind: str                      # role_need | requirement | evidence | decision | job_flag | line | decisions
    label: str = ""
    status: str = "VERIFIED"
    children: set[str] = field(default_factory=set)


@dataclass
class _Candidate:
    """One question, and the graph nodes that raise it."""
    ask: str
    why: str = ""
    do_not_ask: str = ""
    members: list[str] = field(default_factory=list)
    status: str = "UNVERIFIED"
    checks: set[str] = field(default_factory=set)
    refs: set[str] = field(default_factory=set)
    job_ids: set[str] = field(default_factory=set)
    statement: str = ""
    about: str = ""


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, _Node] = {}

    def node(self, node_id: str, kind: str, label: str = "", status: str = "VERIFIED") -> _Node:
        n = self.nodes.get(node_id)
        if n is None:
            n = self.nodes[node_id] = _Node(node_id, kind, label, status)
        elif SEVERITY[status] > SEVERITY[n.status]:
            n.status = status
        return n

    def edge(self, parent: str, child: str) -> None:
        self.nodes[parent].children.add(child)

    def closure(self, members: list[str]) -> set[str]:
        """The members and everything that rests on any of them."""
        seen, todo = set(members), deque(members)
        while todo:
            for c in self.nodes[todo.popleft()].children:
                if c not in seen:
                    seen.add(c)
                    todo.append(c)
        return seen


# ---------------------------------------------------------------- questions
def fit_question(ask: str, fallback: str) -> str:
    """The ask if it is under 25 words, else the fallback (which callers keep short)."""
    return ask if len(ask.split()) <= MAX_QUESTION_WORDS else fallback


def _short(text: str, words: int = 6) -> str:
    w = text.rstrip(".").split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def job_flag_question(check: str, title: str, tool: str) -> tuple[str, str, str]:
    """(ask, why, do_not_ask) for a job-level flag. `tool` is the tool name, or '' when the flag is not about a tool."""
    t = tool or "this tool"
    table = {
        "C04": (f"Which {title} stage tests the stated requirements, and are stage results combined by a fixed rule?",
                "A weak selection method undermines every decision made with it.", ""),
        "C05": (f"Who reviews selection rates by group for {title}, and what explains any gap?",
                "Selection rates differ across groups: a human reviews the cause.",
                "Don't ask which group is better qualified."),
        "C07": (f"Why did {t} change its output when only the name changed, and what has the vendor fixed?",
                "A name-swap probe shows the tool's output depends on the name.", ""),
        "C08": (f"What job-related reason, other than age or graduation year, supports the rule in {t}?",
                "Age and age proxies are high legal risk.", "Don't ask the applicant's age or graduation year."),
        "C09": (f"Which job-related evidence can replace the emotion or personality reading from {t}?",
                "Emotion or personality inference about candidates is blocked (hard rule 1).",
                "Don't ask the candidate how they felt or what their personality is."),
        "C10": (f"When were the NYC bias audit and the candidate notice for {t} done, and who holds the records?",
                "NYC LL144 needs a recent bias audit and advance notice.", ""),
        "C11": (f"Who reviews the automated decisions of {t}, and how can an applicant contest one?",
                "GDPR Art 22 needs human intervention and a way to contest.", ""),
        "C12": (f"Were the Illinois notice and a disparate-effect review done for {t}, and where are they recorded?",
                "Illinois rules need notice and a disparate-effect review for AI in hiring.", ""),
        "C13": ("Which source supports the legal date in this statement, and who confirmed it?",
                "The statement's date differs from the ledger date.", ""),
        "C14": (f"Where are the DPDP consent notice and retention period for {t} recorded?",
                "India DPDP needs consent and a stated retention period.", ""),
        "C15": ("What data from your own process shows this vendor claim holds for this role?",
                "A vendor's claim is context, not proof.", "Don't ask whether the vendor is trusted."),
        "C01": ("What observable result replaces the vague wording in this text?",
                "Until defined, the trait can't be checked against evidence.", ""),
    }
    ask, why, avoid = table.get(check, ("What evidence supports this part of the process?",
                                        "It could not be confirmed from the data.", ""))
    return fit_question(ask, "What evidence supports this part of the process?"), why, avoid


def _worst_check(checks: dict[str, str]) -> str:
    """The check with the most severe verdict (ties: lowest check id)."""
    return min(checks, key=lambda c: (-SEVERITY[checks[c]], c))


# ---------------------------------------------------------------- full report
def mother_assumptions(report: dict, top: int = TOP_N) -> list[dict]:
    """Top 1-3 mother assumptions of a full-loop report (chains, job-level issues, questions, citations)."""
    top = max(1, min(top, TOP_N))
    g = Graph()
    jobs = {j["job_id"]: j for j in report["jobs"]}
    tools = {t["tool_id"]: t.get("name") or t["tool_id"] for t in report["tools"]}
    decisions_of_job: dict[str, list[str]] = defaultdict(list)
    link_status: dict[str, str] = {}

    # Flagged checks per job-level object (object_ref -> check -> verdict).
    flagged: dict[str, dict[str, str]] = defaultdict(dict)
    issue_info: dict[str, dict] = {}
    for i in report["job_level_issues"]:
        flagged[i["object_ref"]][i["check"]] = i["verdict"]
        info = issue_info.setdefault(i["object_ref"], {"refs": set(), "message": "", "tool_id": i.get("tool_id"),
                                                       "job_ids": set(), "decision_ids": set()})
        info["refs"].update(i["ledger_refs"])
        info["job_ids"].update(i["job_ids"])
        info["decision_ids"].update(i.get("decision_ids") or [])
        if not info["message"] or SEVERITY[i["verdict"]] > SEVERITY[flagged[i["object_ref"]].get(i["check"], "VERIFIED")]:
            info["message"] = i["message"]

    # Chain links: shared (inherited) nodes are keyed by job, a decision's own nodes by decision.
    def nid(chain: dict, link: dict) -> str:
        return f"{chain['job_id']}:{link['link_id']}" if link.get("inherited") else f"{chain['chain_id'][3:]}:{link['link_id']}"

    for c in report["chains"]:
        did = c["chain_id"][3:]
        decisions_of_job[c["job_id"]].append(did)
        by_id = {l["link_id"]: l for l in c["links"]}
        for l in c["links"]:
            n = g.node(nid(c, l), l["type"], l["statement"], l["status"])
            link_status[n.node_id] = n.status
        for l in c["links"]:
            for dep in l.get("depends_on", []):
                g.edge(nid(c, by_id[dep]), nid(c, l))

    # Job-level flags feed the evidence link of every decision they affect.
    for ref, info in issue_info.items():
        if ref.startswith("requirement:"):
            continue
        g.node(ref, "job_flag", info["message"], max(flagged[ref].values(), key=lambda s: SEVERITY[s]))
        ids = info["decision_ids"] or {d for j in info["job_ids"] for d in decisions_of_job.get(j, [])}
        for did in sorted(ids):
            if f"{did}:E1" in g.nodes:
                g.edge(ref, f"{did}:E1")

    cands: dict[str, _Candidate] = {}

    def add(ask: str, member: str, status: str, checks, refs, job_id: str, statement: str, why: str = "",
            avoid: str = "", about: str = "") -> None:
        c = cands.get(ask)
        if c is None:
            c = cands[ask] = _Candidate(ask, why, avoid, status=status, statement=statement, about=about)
        if member not in c.members:
            c.members.append(member)
        c.status = max(c.status, status, key=lambda s: SEVERITY[s])
        c.checks.update(checks)
        c.refs.update(refs)
        c.job_ids.add(job_id)

    questions = report.get("questions", [])
    q_by_about = {q["about"]: q for q in questions if q.get("about")}
    q_need = {q["job_id"]: q for q in questions if q.get("check") == "N"}

    for job_id, job in jobs.items():
        title = job["title"]
        # Role need (a missing need is an unverified assumption: every requirement rests on it).
        need = g.nodes.get(f"{job_id}:N1")
        if need and (need.status in FLAGGED or need.status == "NOT_CHECKED"):
            q = q_need.get(job_id)
            ask = q["ask"] if q else f"In one sentence, why does the {title} role exist?"
            add(ask, need.node_id, "UNVERIFIED" if need.status == "NOT_CHECKED" else need.status, ["N"], [], job_id,
                f"Why the {title} role exists is not recorded.", "Every requirement is checked against the role need.",
                about=f"role_need:{job_id}")
        # Requirements.
        for r in job.get("requirements", []):
            ref = f"requirement:{r['req_id']}"
            checks = flagged.get(ref)
            node = f"{job_id}:R{r['req_id'].split('-R')[-1]}"
            if not checks or node not in g.nodes:
                continue
            status = max(checks.values(), key=lambda s: SEVERITY[s])
            if status not in FLAGGED:
                continue
            q = q_by_about.get(ref)
            ask = fit_question(q["ask"] if q else f'How does "{_short(r["text"])}" help the {title} succeed?',
                               f'How does "{_short(r["text"], 4)}" help the {title} succeed?')
            add(ask, node, status, checks, issue_info[ref]["refs"], job_id, r["text"], q["why"] if q else "",
                q["do_not_ask"] if q else "", about=ref)
    # Job-level flags that are not requirements.
    for ref, checks in flagged.items():
        if ref.startswith("requirement:"):
            continue
        status = max(checks.values(), key=lambda s: SEVERITY[s])
        if status not in FLAGGED:
            continue
        info = issue_info[ref]
        job_id = sorted(info["job_ids"])[0] if info["job_ids"] else ""
        ask, why, avoid = job_flag_question(_worst_check({c: v for c, v in checks.items() if v in FLAGGED}),
                                            jobs.get(job_id, {}).get("title", "this role"),
                                            tools.get(info["tool_id"] or "", ""))
        add(ask, ref, status, checks, info["refs"], job_id, info["message"], why, avoid, about=ref)
    # Decision-level questions: only decisions where that check's verdict is a flag.
    verdicts = {f["flag_ref"]: f["verdict"] for f in report.get("flags", [])}
    for q in questions:
        gate = DECISION_QUESTIONS.get(q.get("check"))
        if not gate:
            continue
        check, link = gate
        for did in q.get("applies_to", []):
            v = verdicts.get(f"decision:{did}|{check.split('-')[0]}")
            node = f"{did}:{link}"
            if v in FLAGGED and node in g.nodes:
                add(q["ask"], node, v, [check.split("-")[0]], [], q["job_id"], g.nodes[node].label, q["why"],
                    q["do_not_ask"], about=f"decision:{did}")
    # Ledger rows for decision-level checks come from the chain links.
    for c in report["chains"]:
        for l in c["links"]:
            if l["link_id"] in ("E1", "D1") and l["status"] in FLAGGED:
                for cand in cands.values():
                    if nid(c, l) in cand.members:
                        cand.refs.update(l.get("ledger_refs", []))

    return _finish(g, list(cands.values()), report.get("citations", {}), top, decisions=True)


# ---------------------------------------------------------------- text report
def mother_from_text(items: list[dict], asks_by_line: dict[str, list[dict]], citations: dict, top: int = TOP_N) -> list[dict]:
    """Top 1-3 for a job post or AI summary. `items` are the text report's lines, `asks_by_line` the questions of
    each line before de-duplication. There are no decisions yet: every line feeds the screening decisions that will be
    made from this text, so the answer counts that one downstream link and ties go to severity, then position.
    """
    top = max(1, min(top, TOP_N))
    g = Graph()
    g.node("DECISIONS", "decisions", "Every screening decision made from this text.")
    cands: dict[str, _Candidate] = {}
    for it in items:
        lid = it["link_id"]
        g.node(lid, "requirement" if it["kind"] == "requirement" else "line", it["text"], it["status"])
        g.edge(lid, "DECISIONS")
        if it["status"] not in FLAGGED:
            continue
        flags = {f["check"]: f["verdict"] for f in it["findings"] if f["verdict"] in FLAGGED}
        for q in asks_by_line.get(lid, []):
            c = cands.get(q["ask"])
            if c is None:
                c = cands[q["ask"]] = _Candidate(q["ask"], q.get("why", ""), q.get("do_not_ask", ""), status=it["status"],
                                                 statement=it["text"], about=lid)
            c.members.append(lid)
            c.status = max(c.status, it["status"], key=lambda s: SEVERITY[s])
            c.checks.update(flags)
            c.refs.update(r for f in it["findings"] if f["verdict"] in FLAGGED for r in f["ledger_refs"])
    return _finish(g, list(cands.values()), citations, top, decisions=False, order={it["link_id"]: n for n, it in enumerate(items)})


# ---------------------------------------------------------------- shared
def _finish(g: Graph, cands: list[_Candidate], citations: dict, top: int, decisions: bool,
            order: dict[str, int] | None = None) -> list[dict]:
    scored = []
    for c in cands:
        closure = g.closure(c.members)
        n_dec = sum(1 for n in closure if n.endswith(":D1")) if decisions else None
        down = len(closure - set(c.members))
        pos = min((order or {}).get(m, 0) for m in c.members)
        scored.append((c, n_dec, down, pos))
    # Most decisions first, then most downstream links, then the most severe verdict, then a stable tie-break.
    scored.sort(key=lambda s: (-(s[1] or 0), -s[2], -SEVERITY[s[0].status], s[3], s[0].ask))
    out = []
    for n, (c, n_dec, down, _) in enumerate(scored[:top], 1):
        refs = sorted(c.refs)
        out.append({
            "order": n,
            "status": c.status,
            "checks": sorted(c.checks),
            "about": c.about,
            "statement": c.statement,
            "question": c.ask,
            "why": c.why,
            "do_not_ask": c.do_not_ask,
            "decisions_unblocked": n_dec,
            "downstream_links": down,
            "job_ids": sorted(c.job_ids),
            "ledger_refs": refs,
            "citations": [citations[r] for r in refs if r in citations],
            "ledger_note": "" if refs else NO_LEDGER_ROW,
        })
    return out


def unblocks_text(m: dict) -> str:
    """One plain sentence: what answering this question unblocks."""
    d = m.get("decisions_unblocked")
    if d is None:
        return (f"Unblocks {m['downstream_links']} downstream link: every screening decision made from this text "
                "rests on it.")
    return f"Unblocks {d} decision{'s' if d != 1 else ''} ({m['downstream_links']} downstream links) if answered."
