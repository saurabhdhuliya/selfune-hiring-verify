"""Check the data layer before any check code is written.

Exits non-zero on any failure. Run from repo root: python scripts/validate.py
"""
import glob
import json
import sys
from datetime import date

import jsonschema

sys.path.insert(0, "src")
from selfune_hv.role_memory import RoleMemory  # noqa: E402
from selfune_hv import ledger as L  # noqa: E402

TODAY = date(2026, 11, 12)
fails = []


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


# ---- ledger
led = L.load("ledger/hiring.jsonl")
ok(len(led) == 50, "ledger has 50 rows")
ok(all("recheck_by" in r and "use_as" in r for r in led.values()), "every row has recheck_by and use_as")
ok(not [r for r in led.values() if r["status"] == "CONTESTED"], "no CONTESTED rows left after re-check")
reviewed = ("GT-0008", "GT-0009", "GT-0023", "GT-0025", "GT-0035")
ok(all(led[i]["user_decision"] == "LOCKED" and "review, 2026-11-12" in led[i]["locked_by"] for i in reviewed),
   "re-checked rows re-locked by human review (2026-11-12)")
ok(all(r["use_as"] != "proof" for r in led.values() if r["status"] in ("VENDOR_CLAIM", "OWN_DATA")),
   "VENDOR_CLAIM and OWN_DATA rows are never proof")
expired = [r["id"] for r in led.values() if date.fromisoformat(r["recheck_by"]) < TODAY]
ok(not expired, f"no expired rows today ({expired})")

# ---- synthetic set
company = json.load(open("data/synthetic/company.json"))
cands = jl("data/synthetic/candidates.jsonl")
decs = jl("data/synthetic/decisions.jsonl")
ok(len(company["jobs"]) == 3, "3 jobs")
ok(len(cands) == 200, "200 candidates")
ok(len({c["candidate_ref"] for c in cands}) == 200, "candidate refs unique")
ok(all("name" not in k for c in cands for k in c), "no name fields on candidates")
gc = json.load(open("data/synthetic/group_counts.json"))
for job, groups in gc.items():
    sel = sum(1 for d in decs if d["job_id"] == job and d["outcome"] == "advanced")
    for g, vals in groups.items():
        ok(sum(v["selected"] for v in vals.values()) == sel, f"{job} {g} selected total matches decisions ({sel})")
        ok(sum(v["applied"] for v in vals.values()) == sum(1 for c in cands if c["job_id"] == job),
           f"{job} {g} applied total matches candidates")

# ---- labels hidden and resolvable
labels = jl("labels/labels.jsonl")
blob = " ".join(open(p, encoding="utf-8").read().lower() for p in glob.glob("data/**/*.*", recursive=True))
ok(all(w not in blob for w in ["planted", "expected_verdict", "\"block\":"]), "no answer words inside data/")
p = sum(l["planted"] for l in labels)
nc = sum(l["expected_verdict"] == "NOT_CHECKED" for l in labels)
# v2: every (requirement, check) pair for C01-C03 labelled (docs/test_set.md has the per-check counts).
ok(p == 47, f"planted count is 47 ({p})")
ok(len(labels) - p - nc == 65, f"clean count is 65 ({len(labels) - p - nc})")
ok(nc >= 2, f"NOT_CHECKED cases present ({nc})")
checks = {l["check"] for l in labels if l["planted"]}
ok(checks == {f"C{i:02d}" for i in range(1, 16)}, f"every check C01-C15 has a planted case (missing: {sorted({f'C{i:02d}' for i in range(1, 16)} - checks)})")

ids = set()
ids |= {f"requirement:{r['req_id']}" for j in company["jobs"] for r in j["requirements"]}
ids |= {f"job:{j['job_id']}:selection_method" for j in company["jobs"]}
ids |= {f"decision:{d['decision_id']}" for d in decs}
ids |= {f"ai_text:{a['text_id']}" for a in jl("data/synthetic/ai_text.jsonl")}
ids |= {f"policy:{s['stmt_id']}" for s in jl("data/synthetic/policy_statements.jsonl")}
ids |= {f"probe_pair:{p['pair_id']}" for p in jl("data/synthetic/tool_probes.jsonl")}
tools = {t["tool_id"] for t in json.load(open("data/synthetic/tools.json"))}
unresolved = []
for l in labels:
    ref = l["object_ref"]
    if ref.startswith("tool:"):
        if ref.split(":")[1] not in tools:
            unresolved.append(ref)
    elif ref.startswith("group_counts:"):
        if ref.split(":")[1] not in ("J1", "J2", "J3"):
            unresolved.append(ref)
    elif ref not in ids:
        unresolved.append(ref)
ok(not unresolved, f"every label points at a real object ({unresolved})")
ok(all(r in led for l in labels for r in l["ledger_refs"]), "every label cites real ledger rows")

# ---- C9 corpus
c9 = jl("data/c9_corpus/c9_inputs.jsonl")
c9l = jl("labels/c9_labels.jsonl")
ok(len(c9) == len(c9l) and {x["c9_id"] for x in c9} == {x["c9_id"] for x in c9l}, f"C9 corpus aligned ({len(c9)})")
ok(abs(sum(x["block"] for x in c9l) - sum(not x["block"] for x in c9l)) == 0, "C9 corpus balanced")
erd_markers = ["my partner", "i feel", "i can't stop"]
ok(not any(m in x["text"].lower() for x in c9 for m in erd_markers), "no ERD personal narrative copied into corpus")

# ---- schemas
dc = json.load(open("schemas/decision_chain.schema.json"))
rms = json.load(open("schemas/role_memory.schema.json"))
rmd = json.load(open("data/synthetic/role_memory.json"))
try:
    jsonschema.validate(rmd, rms)
    ok(True, "role_memory.json valid against schema")
except jsonschema.ValidationError as e:
    ok(False, f"role_memory schema: {e.message}")
ds = json.load(open("schemas/decision.schema.json"))
bad_d = [(d["decision_id"], e.message) for d in jl("data/synthetic/decisions.jsonl")
         for e in jsonschema.Draft202012Validator(ds).iter_errors(d)]
ok(not bad_d, f"decisions.jsonl valid against decision schema ({bad_d[:3]})")
for ch in json.load(open("examples/decision_chains.json")):
    try:
        jsonschema.validate(ch, dc)
        ok(True, f"{ch['chain_id']} valid against decision_chain schema")
    except jsonschema.ValidationError as e:
        ok(False, f"{ch['chain_id']}: {e.message}")
    ok(all(len(q["ask"].split()) < 25 for q in ch["human_questions"]), f"{ch['chain_id']} questions under 25 words")

# ---- role memory behaviour
rm = RoleMemory(rmd, TODAY)
ok(rm.lookup("J2", "Strong Python skills, because the billing backend is Python.").status == "FOUND", "J2 'strong python' FOUND")
ok(rm.lookup("J3", "Excellent attention to detail.").status == "STALE", "J3 'attention to detail' STALE (review date passed)")
ok(rm.lookup("J1", "Strong communication skills").status == "MISSING", "J1 'strong communication' MISSING")
try:
    rm.propose_definition("J1", {"trait_id": "TR-J1-X", "terms": ["positive energy"],
                                 "definition": "Shows enthusiasm and low anxiety in interview.",
                                 "observable_evidence": ["interviewer rates mood"]})
    ok(False, "role memory rejects emotion-based definitions")
except ValueError:
    ok(True, "role memory rejects emotion-based definitions")

print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
