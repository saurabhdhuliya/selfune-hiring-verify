# Decision chain

```
N  role_need     Why the role exists (employer's words, from role memory)
R  requirement   What is asked for, and why it serves N
E  evidence      What the data shows about the requirement
D  decision      Outcome and stated reason
```

## Verdicts per link
| Verdict | Meaning |
|---|---|
| VERIFIED | Supported by the user's data, a code result or a locked ledger row |
| UNVERIFIED | Could not be confirmed, so a human is asked |
| CONTRADICTED | The data says otherwise |
| ESCALATE | High risk plus unverified or contradicted, or blocked by C9 |
| NOT_CHECKED | The input is missing. This never counts as a pass. |
| WARN | Rests on a contested or pending row. Never a fail. |

## Roll-up
- The chain status is the worst verdict among its links (severity, lowest to highest: VERIFIED, WARN, NOT_CHECKED, UNVERIFIED, CONTRADICTED, ESCALATE).
- The weakest link is the first link that isn't VERIFIED, in the order N → R → E → D, because everything downstream inherits its doubt.
- **Inherited links don't count.** Role-need and requirement links built from job-level findings are marked `inherited: true` with the note "inherited from job". They stay in the chain for context, but chain status and weakest link come only from the decision's own evidence and decision links (C06, C08, C09, C11, C15). Job-level flags are reported once, as job-level issues with "affects N decisions", instead of being repeated in every chain.
- High risk (a legal check, or a decision made by a tool alone) turns UNVERIFIED or CONTRADICTED into ESCALATE.
- C9 blocks the whole chain, but only when the C9-flagged tool is in the decision's `tools_used` (see `docs/schema.md`).

## Evidence links (taken from ERD)
ERD separates **Behavior Confidence** (did it happen?) from **Explanation Confidence** (does it mean what we think?). The chain applies the same split to claims about the process:

- `observed` and `observed_confidence`: is the fact really in the data?
- `inferred` and `inference_confidence`: does the fact support the conclusion?
- `alternative_explanations`: other readings of the same fact.

"References field empty" is a fact with high confidence. "So the candidate is unreliable" is a conclusion with low confidence. The link is UNVERIFIED and C06 fires.

## Human questions (taken from ERD)
Each question names the link, the question (under 25 words), why it matters and `do_not_ask`, the leading wording to avoid (from ERD's "What NOT to Ask"). A definition answer goes to role memory, so it's asked once per role. A one-off fact goes to the decision record.
