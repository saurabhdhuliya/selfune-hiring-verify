# Outcome log

Records what people did with each flag, so we can learn which checks they disagree with.

- **File:** `out/outcome_log.jsonl`. Append-only: entries are added and never edited or deleted by the tools. `out/` is git-ignored, so **real logs stay local** and never enter the repo.
- **Code:** `src/selfune_hv/outcome_log.py` (validation, append, summary) and `scripts/log_outcome.py` (command line). No LLM.

## Entry
| Field | Meaning |
|---|---|
| `logged_at` | UTC time the entry was written (automatic). |
| `run_id` | The run the flag came from (automatic, from `out/report.json`). |
| `flag_ref` | `object_ref|check`, e.g. `tool:T1:audit_age|C10`. Must be a flag in that run. |
| `verdict_shown` | The verdict the person saw (automatic, from the report). |
| `seen_by_role`, `decided_by_role` | A role, never a name: e.g. "HR lead", "Hiring manager", "Interview panel". |
| `action` | `accepted` (agree, will act), `overridden` (disagree, keep as is), `fixed` (changed the process), `deferred` (later). |
| `override_reason` | Required for `overridden`, at least 10 words. |
| `outcome_note`, `outcome_date` | Optional: what happened and when (ISO date). |

## Rejected entries
Nothing is written if any rule fails:
- the flag isn't in the current run, or the run_id or verdict doesn't match the report;
- an override without a reason of at least 10 words;
- a role that doesn't name a function (a person's name is rejected; the role must contain a word such as HR, lead, manager, recruiter, panel, head, director);
- any free text with a candidate reference (`CAND-...`), an email address or a phone number (9+ digits; ISO dates don't count);
- unknown fields.

The role rule catches bare names, not names written next to a role ("Jane, HR lead" passes). Don't type names.

## Use
```
py scripts/run_loop.py                       # writes out/report.json with a run_id
py scripts/log_outcome.py --flag "tool:T1:audit_age|C10" --seen-by "HR lead" --decided-by "HR lead" \
    --action fixed --note "New audit ordered" --outcome-date 2026-11-20
py scripts/log_outcome.py --summary
```
After logging, run `scripts/run_loop.py` again: `out/report.html` then shows a **Flag history** column with the last action per flag (from any run).

## Summary and override rate
`--summary` prints counts by action and by check, and the **override rate per check**: overridden ÷ flags with an action. Each flag counts once per run, using its latest action, so "deferred" then "fixed" counts as fixed.

A high override rate means people often disagree with that check. It's a prompt to read the override reasons and either fix the check or the guidance, not proof that the check is wrong: people can be wrong too. Rates on a handful of flags mean little.
