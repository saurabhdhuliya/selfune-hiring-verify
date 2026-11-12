# Synthetic test set

The employer is Northwind Synthetic Ltd (fictional). The seed is fixed (20261112), so a re-run gives the same files.

| Job | Jurisdiction | Candidates | Selected |
|---|---|---|---|
| J1 Customer Support Specialist | NYC | 80 | 20 |
| J2 Backend Engineer | EU | 70 | 17 |
| J3 Operations Analyst | IN, IL | 50 | 10 |

## Scoring
Each row of `labels/labels.jsonl` is one (object, check) pair:
- **Planted:** the check must fire with the expected verdict. If it does, the case is caught; if not, it's missed.
- **Clean:** the check must not fire. If it does, that's a false alarm.
- **NOT_CHECKED:** the input is missing. The check must report NOT_CHECKED, never a pass.

| Check | Planted | Clean | NOT_CHECKED |
|---|---|---|---|
| C01 undefined trait | 5 | 13 | |
| C02 years as proxy | 3 | 13 | |
| C03 no stated reason | 9 | 7 | |
| C04 weak method | 2 | 1 | |
| C05 4/5 rule | 2 | 2 | 1 |
| C06 missing field as negative | 4 | 4 | |
| C07 name swap | 4 | 4 | |
| C08 age or age proxy | 2 | 3 | |
| C09 emotion inference | 4 | 6 | |
| C10 NYC LL144 | 3 | 3 | 1 |
| C11 GDPR Art 22 | 2 | 3 | 1 |
| C12 Illinois | 1 | 1 | |
| C13 timing (warn only) | 1 | 1 | |
| C14 India DPDP | 2 | 2 | |
| C15 vendor claim as proof | 3 | 2 | |
| **Total (115)** | **47** | **65** | **3** |

C09's clean column includes one `UNVERIFIED` case (T11 `infers_emotion: unknown`). The expected behaviour there is to ask the employer, neither pass nor block.

## Known limits
- Every (requirement, check) pair for C01-C03 is labelled (L087-L115, added after v1 so earlier IDs are unchanged). They were decided from the requirement text using each check's stated rule, so they measure whether a check follows its rule, not whether the rule is right. Other checks still label only targeted pairs; firings on unlabelled pairs aren't counted as false alarms.
- Planted decisions sit at the first positions of each job. That doesn't matter while the loop never reads labels, but shuffle them before any learned component is trained on this set.
- Names in the C07 probes are placeholders (NAME_SET_A and NAME_SET_B). A real name-swap run needs a name list from published audit studies, kept outside the repo.
