# Input schemas

## Data folder (`scripts/run_loop.py --data <folder>`)
The loop reads one folder of JSON files. The default is `data/synthetic`; a company points `--data` at its own folder in the same format:
```
py scripts/run_loop.py --data data/real/acme
```
**Keep real data under `data/`** (e.g. `data/real/acme/`): everything in `data/` except `data/synthetic/` and `data/c9_corpus/` is git-ignored. Real candidate data never enters the repo (hard rule 5). The ledger always comes from `ledger/hiring.jsonl` in the repo.

| File | Required | Contents | If missing |
|---|---|---|---|
| `company.json` | yes | Employer and jobs (below) | Run stops |
| `decisions.jsonl` | yes | One decision record per line (below) | Run stops |
| `tools.json` | no | Hiring tools (below) | No tool checks (C08 tools, C09 tools, C10-C12, C14, C15 tools) |
| `group_counts.json` | no | Applicants and selections per group, per job | C05 reports NOT_CHECKED for every job |
| `role_memory.json` | no | Trait definitions per role (`schemas/role_memory.schema.json`, `docs/role_memory.md`) | Every role need is NOT_CHECKED and every vague trait gets a question |
| `ai_text.jsonl` | no | AI-written texts: job posts, summaries | No C01/C09/C15 text checks |
| `tool_probes.jsonl` | no | Name-swap probe pairs | No C07 findings |
| `policy_statements.jsonl` | no | Employer statements about legal dates | No C13 findings |

Before any check runs, the loop checks that the folder exists and has the two required files, that every decision matches `schemas/decision.schema.json`, and that `company.json` has at least one job. If not, it writes nothing and lists the problems.

### `company.json`
```json
{"employer_id": "EMP-1", "employer_name": "...",
 "jobs": [{"job_id": "J1", "title": "...", "description": "...",
           "jurisdiction": ["NYC", "EU", "IL", "IN", "CO"],
           "selection_method": {"stages": ["work sample", "structured interview"], "combine": "mechanical"},
           "requirements": [{"req_id": "J1-R1", "text": "..."}]}]}
```
`jurisdiction` decides which legal checks run: NYC → C10, EU → C11 and C13 (EU), IL → C12, IN → C14, CO → C13 (Colorado). `req_id` is `<job_id>-R<n>`. `combine` is `mechanical` or `holistic` (C04).

### `tools.json`
A list of tools. `tool_id` (`T<n>`), `job_ids`, `name`, `what_it_outputs`, `decision_mode` (`alone`, `weighted_most`, `overrides_human`, `advisory`, `none`) and `infers_emotion` (`true`, `false` or `"unknown"`) apply everywhere. Other fields are read only by the check that needs them:
- C08: `rules` (list of strings).
- C10 (NYC): `employer_scope_claim`, `last_bias_audit_date`, `notice_sent_date`, `first_use_date`.
- C11 (EU): `human_review`, `lawful_basis`.
- C12 (IL): `il_notice_sent`, `il_disparate_effect_review`.
- C14 (IN): `consent_notice`, `retention_days`.
- C15: `vendor_claims` (list of strings).

A field that is **absent** means "not stated" (NOT_CHECKED). A field set to **null** means "none" (usually a flag).

### `group_counts.json`
`{"J1": {"sex_self_reported": {"women": {"applied": 40, "selected": 6}, "men": {...}}, "age_band": {...}}}`. Aggregated counts only; never individual records.

### Other files
- `ai_text.jsonl`: `{"text_id": "AT01", "job_id": "J1", "source": "...", "text": "..."}`
- `tool_probes.jsonl`: two lines per `pair_id`, same `tool_id` and `profile_id`, `identical_except: "name"`, different `name_marker`, and a `tool_output`. Use placeholder name markers, not real names.
- `policy_statements.jsonl`: `{"stmt_id": "PS01", "job_id": "J2", "text": "..."}`. `job_id` is optional.

## Decision record (`schemas/decision.schema.json`)
One line of `data/synthetic/decisions.jsonl`: a decision as the employer recorded it.

| Field | Required | Meaning |
|---|---|---|
| `decision_id` | yes | `D0001` ... |
| `candidate_ref` | yes | Anonymous `CAND-0001` ... Never a name. Never shown in the HTML report. |
| `job_id` | yes | The job the decision belongs to. |
| `stage` | yes | `screen`, `assessment`, `interview` or `offer`. |
| `outcome` | yes | `rejected`, `advanced` or `on_hold`. |
| `reason_text` | yes | The stated reason, in the employer's words. |
| `fields_present`, `fields_missing` | yes | Application fields that were filled or empty. An empty field is a fact, not evidence about the applicant (C06). |
| `decision_date` | yes | ISO date. |
| `decided_by` | no | `human`, `tool` or `both`. If absent, C11 reports NOT_CHECKED. |
| `tools_used` | no | Tool IDs that fed this decision, e.g. `["T5"]`. |

### `tools_used` and C09
C09 (emotion or personality inference) blocks a decision chain only when a C09-flagged tool is listed in that decision's `tools_used`. Without `tools_used`, the loop can't tell which decisions a flagged tool touched, so the flag is reported once as a job-level issue ("affects N decisions") instead of blocking every chain in the job. The synthetic data doesn't record `tools_used` yet.

## Decision chain
See `docs/decision_chain.md` and `schemas/decision_chain.schema.json`.

## Role memory
See `docs/role_memory.md` and `schemas/role_memory.schema.json`.
