# Selfune Hiring Verification Loop

Checks a hiring decision's reasoning before it is final. It does not score, rank, accept or reject people.

Every other hiring agent asks "is this person good?". This one asks "is this decision sound?" Each decision becomes a chain:

```
role need  ->  requirement  ->  evidence  ->  decision
```

Every link gets its own verdict. The chain is only as strong as its weakest link.

**Status: all 15 checks built** in `src/selfune_hv/checks/`; C01, C02, C03, C06 and C15 are rule baselines. `scripts/score.py` passes the loop test in `labels/` on synthetic data. Not built yet: wiring check results into decision chains, and any measurement on real data.

## Hard rules
1. **No emotion or personality inference** about candidates. The loop detects and blocks tools that do it (EU AI Act, ledger GT-0008).
2. **Never decides about a person.** Output is about the process.
3. **Never auto-rejects, never auto-locks.** Anything unverified goes to a human, and a human locks.
4. **Evidence only from the user's data, code results, or locked ledger rows.** Never from LLM memory.
5. **Synthetic data only in this repo.** Real candidate data stays local.
6. **Not legal advice.** Legal checks say "flag for review" and cite the ledger row and its date.
7. **CONTESTED or pending rows only warn.** They never cause a hard fail.

## What is here
| Path | What |
|---|---|
| `ledger/hiring.jsonl` | 50 rule rows with `recheck_by`, `use_as` and `display_label`. GT-0008, GT-0009, GT-0023, GT-0025 and GT-0035 were re-checked or changed after the 2026-11-12 adversary check and re-locked by human review the same day. Pending rows never cause a hard fail (ESCALATE or CONTRADICTED drops to WARN); UNVERIFIED still asks a human. |
| `schemas/decision_chain.schema.json` | The decision chain format: one verdict per link, the weakest link, and questions for a human. |
| `schemas/role_memory.schema.json` | The employer's trait definitions, written once per role and locked by a human. |
| `src/selfune_hv/` | Chain roll-up, role-memory lookup, ledger warnings and C9 vocabulary. No LLM. |
| `data/synthetic/` | A fake employer: 3 jobs, 200 candidates, 13 tools, 8 name-swap probe pairs, 11 AI-written texts. |
| `data/c9_corpus/` | 496 texts for the emotion-inference detector, built from ERD label fields. |
| `labels/` | **The answers. The loop must never read this folder.** |
| `examples/decision_chains.json` | Three worked chains: one VERIFIED, one UNVERIFIED and one blocked (ESCALATE). |

## Test set (section 9)
- 115 scored items: 47 planted, 65 clean, 3 NOT_CHECKED. Every (requirement, check) pair for C01-C03 is labelled.
- Every check from C01 to C15 has at least one planted case.
- Release rule: every code check catches 100% of its planted cases, and false alarms stay under 10%.
- Rule baselines are tuned on synthetic data; real-world accuracy is unmeasured.

## Quick start
```
pip install openpyxl jsonschema
python scripts/update_ledger.py <hiring_ground_truth.jsonl> ledger/hiring.jsonl
python scripts/generate_synthetic.py --erd <ERD.xlsx>
python scripts/build_c9_corpus.py <ERD.xlsx>
python scripts/build_examples.py
python scripts/validate.py
```

The ERD file is not in the repo: pass its path as shown.

## License
Code: Apache-2.0 (add a LICENSE file). Ledger text: CC BY 4.0, credit Selfune, with sources credited per row.
