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

## Test results (v0.1, 2026-11-12)
`py scripts/score.py`:

| Check | Planted caught | Clean false alarms | NOT_CHECKED correct | Release |
|---|---|---|---|---|
| C01 undefined trait | 5/5 | 0/13 | - | PASS |
| C02 years as proxy | 3/3 | 0/13 | - | PASS |
| C03 no stated reason | 9/9 | 0/7 | - | PASS |
| C04 weak method | 2/2 | 0/1 | - | PASS |
| C05 4/5 rule | 2/2 | 0/2 | 1/1 | PASS |
| C06 missing field as negative | 4/4 | 0/4 | - | PASS |
| C07 name swap | 4/4 | 0/4 | - | PASS |
| C08 age or age proxy | 2/2 | 0/3 | - | PASS |
| C09 emotion inference | 4/4 | 0/6 | - | PASS |
| C10 NYC LL144 | 3/3 | 0/3 | 1/1 | PASS |
| C11 GDPR Art 22 | 2/2 | 0/3 | 1/1 | PASS |
| C12 Illinois | 1/1 | 0/1 | - | PASS |
| C13 timing | 1/1 | 0/1 | - | PASS |
| C14 India DPDP | 2/2 | 0/2 | - | PASS |
| C15 vendor claim as proof | 3/3 | 0/2 | - | PASS |

- **C09 corpus** (`data/c9_corpus/`, 496 texts): 248/248 caught, 0/248 false alarms.
- **Unit tests:** `py -m pytest tests`: 207 passed.
- `py scripts/validate.py`: 0 failures.

## Limits
- **Synthetic data, built alongside the checks.** The test set and the checks were written in the same project, and the C01-C03 requirement labels follow each check's stated rule. A perfect score shows the checks follow their rules on this data, not that they are right on real hiring data.
- **Rule baselines.** C01, C02, C03, C06 and C15 are keyword and pattern rules. Unclear cases are meant for an AVL agent mode that is not built yet.
- **C09 corpus is template-based.** The cue list catches all 248 positives with no false alarms, which shows the corpus is too easy, not that the detector is good (see `docs/erd_use.md`).
- **Real-world accuracy is unmeasured.** No check has been scored on real postings or decisions, or on labels written by someone who hasn't seen the code.
- **Not legal advice.** Legal checks flag for review and cite ledger rows with their source and date. Ledger rows record what sources say; check the source before relying on one.

## Quick start
The synthetic data, labels and ledger are already in the repo.
```
pip install openpyxl jsonschema
python scripts/validate.py
python scripts/score.py
python scripts/run_loop.py
```
Then open `out/report.html`.

To run on your own data, put it in a folder under `data/` (git-ignored) in the format described in `docs/schema.md`, then run `python scripts/run_loop.py --data data/real/<company>`. To rebuild the synthetic set from source, see `docs/test_set.md`.

## License
- **Code:** Apache-2.0, © 2026 Selfune AI. See `LICENSE`.
- **Ledger text** (`ledger/`): CC BY 4.0. Credit Selfune AI, and credit the sources per row. See `LEDGER_LICENSE.md`.
