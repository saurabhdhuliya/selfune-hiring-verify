# Input schemas

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
