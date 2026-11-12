"""Build three worked decision chains from the synthetic data.

1. VERIFIED      J2 requirement "Strong Python" verified through role memory (no human asked)
2. UNVERIFIED    J1 rejection resting on a missing field (C06), plus an undefined trait (C01)
3. ESCALATE      J2 interview where the tool inferred emotion (C09): chain blocked
"""
import json
import sys
from datetime import date

sys.path.insert(0, "src")
from selfune_hv.decision_chain import Link, HumanQuestion, build_chain, evidence_status  # noqa: E402
from selfune_hv.role_memory import RoleMemory  # noqa: E402

TODAY = date(2026, 11, 12)
rm = RoleMemory.load("data/synthetic/role_memory.json", TODAY)
company = json.load(open("data/synthetic/company.json"))
decisions = [json.loads(l) for l in open("data/synthetic/decisions.jsonl")]
title = {j["job_id"]: j["title"] for j in company["jobs"]}
reqs = {r["req_id"]: r["text"] for j in company["jobs"] for r in j["requirements"]}

chains = []

# ---- 1. VERIFIED via role memory
lk = rm.lookup("J2", reqs["J2-R1"])
assert lk.status == "FOUND", lk
d = next(x for x in decisions if x["job_id"] == "J2" and x["outcome"] == "advanced")
links = [
    Link("N1", "role_need", lk.role_need, "VERIFIED", "role_memory", note="Defined by Engineering Manager, Billing."),
    Link("R1", "requirement", reqs["J2-R1"], "VERIFIED", "role_memory", ["N1"], trait_ref=lk.trait["trait_id"],
         check_refs=["C01"], note=f"Matched term '{lk.matched_term}'. Definition: {lk.trait['definition']}"),
    Link("E1", "evidence", "Work sample passes 9 of 10 hidden tests.", evidence_status("High", "High", []), "code", ["R1"],
         observed="work_sample_score present; 9/10 hidden tests", inferred="Meets TR-J2-PY observable threshold (8/10)",
         observed_confidence="High", inference_confidence="High", ledger_refs=["GT-0006"]),
    Link("D1", "decision", d["reason_text"], "VERIFIED", "code", ["E1"]),
]
chains.append(build_chain("CH-EX-1", "J2", d["candidate_ref"], "screen", links))

# ---- 2. UNVERIFIED: missing field used as a negative + undefined trait
d = next(x for x in decisions if x["reason_text"].startswith("No references provided"))
lk = rm.lookup("J1", reqs["J1-R1"])
assert lk.status == "MISSING"
links = [
    Link("N1", "role_need", rm.role_need("J1"), "VERIFIED", "role_memory"),
    Link("R1", "requirement", reqs["J1-R1"], "UNVERIFIED", "human", ["N1"], check_refs=["C01"],
         ledger_refs=["GT-0019", "GT-0021"], note="'Strong' has no definition in role memory."),
    Link("E1", "evidence", "Candidate is not reliable.", evidence_status("Low", "Low", ["references"]), "code", ["R1"],
         observed="references field is empty", inferred="candidate is not reliable",
         observed_confidence="High", inference_confidence="Low",
         alternative_explanations=["form did not ask for references", "referees not yet contacted",
                                   "candidate keeps references until a later stage"],
         fields_missing=["references"], check_refs=["C06"]),
    Link("D1", "decision", d["reason_text"], "UNVERIFIED", "avl", ["E1"], check_refs=["C06"]),
]
qs = [
    HumanQuestion("R1", RoleMemory.question_for("strong communication skills", title["J1"]),
                  "Without a definition the requirement cannot be checked, for this or any later candidate.",
                  do_not_ask="Do you think this candidate communicates well?", store_answer_in="role_memory"),
    HumanQuestion("E1", "Did the application form ask for references at this stage?",
                  "If it did not, the empty field says nothing about the candidate.",
                  do_not_ask="Was the candidate hiding something?", store_answer_in="decision_record"),
]
chains.append(build_chain("CH-EX-2", "J1", d["candidate_ref"], "screen", links, qs))

# ---- 3. ESCALATE: emotion inference blocked
at = [json.loads(l) for l in open("data/synthetic/ai_text.jsonl")]
emo = next(x for x in at if x["source"].startswith("AI interview analysis"))
links = [
    Link("N1", "role_need", rm.role_need("J2"), "VERIFIED", "role_memory"),
    Link("R1", "requirement", reqs["J2-R2"], "VERIFIED", "role_memory", ["N1"], trait_ref="TR-J2-PROD"),
    Link("E1", "evidence", emo["text"], "ESCALATE", "code", ["R1"], check_refs=["C09"], ledger_refs=["GT-0008"],
         note="Tool output infers emotion/personality. Blocked; not evaluated, not shown to decision maker."),
    Link("D1", "decision", "Pending interview outcome.", "NOT_CHECKED", "human", ["E1"]),
]
qs = [HumanQuestion("E1", "Can InterviewLens emotion and stress scores be switched off for all candidates?",
                    "The EU AI Act bans emotion inference in hiring; the output cannot be used.",
                    store_answer_in="decision_record")]
chains.append(build_chain("CH-EX-3", "J2", "CAND-0090", "interview", links, qs, blocked=True))

with open("examples/decision_chains.json", "w", encoding="utf-8") as f:
    json.dump(chains, f, indent=2, ensure_ascii=False)
for c in chains:
    print(c["chain_id"], c["chain_status"], "weakest:", c["weakest_link"], "questions:", len(c["human_questions"]))
