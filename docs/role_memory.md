# Role memory

Why it exists: in Selfune's study, 31 of 50 requirement lines could only be checked once the employer defined the trait (GT-0021). Without stored definitions, the loop would ask a human about every requirement for every candidate.

## Flow
1. The loop matches a requirement line to a stored trait by its `terms` (the longest match wins).
2. `FOUND` and ACTIVE: the requirement is verified against the definition. No question.
3. `MISSING`: one question is asked, once per role.
4. `STALE` (past `review_by`) or `RETIRED`: treated as unverified, and the human is asked to confirm or update the definition.
5. A human answers, `propose_definition()` validates the answer, and a human locks it. The loop never writes role memory itself.

## Each definition needs
- An observable definition and at least one piece of `observable_evidence`.
- `measured_by`: the selection method that observes it.
- `why_it_predicts`: the link back to the role need (C03).
- Who defined it (a role, not a name), the date, and a review date.

## Rejected definitions
Definitions that use an emotion or personality construct ("enthusiasm", "low anxiety", "culture fit score") are refused (hard rule 1). They must be restated as observable job behaviour. For example, "stays calm under pressure" becomes "handles 3 simulated escalations in 30 minutes".

## In the synthetic set
- J1: no definitions, so the loop asks.
- J2: "strong python" and "production debugging" are defined, so it verifies without asking.
- J3: "attention to detail" is defined but past its review date, so it's STALE.
