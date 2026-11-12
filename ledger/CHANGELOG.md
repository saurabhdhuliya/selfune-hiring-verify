# Ledger changes

## 2026-11-12
- Added `recheck_by` to every row: legal rows (hiring_regulation, hiring_litigation, hiring_agent_failure) at retrieved + 6 months, all other rows at + 24 months.
- Added `use_as` (proof, cite_with_caveat, context_only, warn_only) and `display_label`.
- **GT-0009** (CONTESTED → VERIFIED_SECONDARY): Regulation (EU) 2026/1744 was published 24 July 2026 and has been in force since 27 July 2026. It moves the Annex III high-risk obligations to 2 December 2027. The EUR-Lex text was not read. Status: PENDING_RELOCK.
- **GT-0025** (CONTESTED → VERIFIED_SECONDARY): Colorado SB 26-189 was signed 14 May 2026 and takes effect 1 January 2027. A pending court challenge and outstanding Attorney General rules may affect it. Recheck by 2027-01-15. Status: PENDING_RELOCK.
- C13 stays warn-only until a human re-locks both rows.

## 2026-11-12: adversary check on legal rows
- Searched for evidence contradicting each hiring_regulation, hiring_litigation and hiring_agent_failure row (19 rows). Results are in `adversary_check`, `adversary_note`, `adversary_urls` and `adversary_date`. Claim, status and user_decision were not changed: a human decides what to do with each result.
- **FAILED: GT-0023.** OFCCP removed its copy of the Uniform Guidelines (41 CFR 60-3) effective 26 Oct 2026, and an EEOC final rule rescinding the interpretive parts of 29 CFR 1607 is at OIRA. C05 cites this row.
- **INCONCLUSIVE: GT-0008** (whether the Art 5(1)(f) ban covers emotion inference from text; the Commission guidelines could not be read) and **GT-0035** (penalty tier order; the official code page refused access).
- 16 rows PASSED. Several notes name developments to watch (GT-0030 12-month proposal, GT-0048/0049 Digital Omnibus).
- `lock_note` still says "Adversary search not yet run" on locked rows; it records the state at lock time and is left for the human re-lock.
- `scripts/update_ledger.py` rebuilds rows from the source file and does not carry these fields over: copy them to the source first if it is re-run.

## 2026-11-12: decisions on the adversary check
All three rows are now PENDING_RELOCK with a `claim_history`; adversary fields kept.
- **GT-0023**: claim rewritten to state that the EEOC plans to rescind the guidelines (final rule expected Nov 2026, effective Jan 2027) and that Title VII disparate-impact liability remains. VERIFIED_SOURCE → VERIFIED_SECONDARY (cite_with_caveat). recheck_by 2027-01-31. Added Ogletree and two SHRM articles.
- **GT-0008**: claim narrowed to emotion inference from biometric data (face, voice, body or behavioural signals); written text is outside the ban per Commission guidelines. Added FPF and Lewis Silkin. The guidelines PDF itself was not read.
- **GT-0035**: caveat added (order of penalty amounts not confirmed). Claim and status unchanged.

Code follow-ups:
- Hard rule 7 now softens only hard fails (ESCALATE, CONTRADICTED → WARN) on pending or contested rows. UNVERIFIED stays: it asks a human, it doesn't fail anything.
- C05 message reframed as a statistical flag; the four-fifths rule is a screening heuristic whose federal status is changing.
- C09 cites the EU AI Act ban (GT-0008) only for video, voice, face or behavioural input. Text-only inference is still ESCALATE, as a Selfune hard rule 1 policy block. C09 verdicts are not softened, because they rest on hard rule 1, not on the ledger row.
