# Ledger changes

## 2026-11-12
- Added `recheck_by` to every row: legal rows (hiring_regulation, hiring_litigation, hiring_agent_failure) at retrieved + 6 months, all other rows at + 24 months.
- Added `use_as` (proof, cite_with_caveat, context_only, warn_only) and `display_label`.
- **GT-0009** (CONTESTED → VERIFIED_SECONDARY): Regulation (EU) 2026/1744 was published 24 July 2026 and has been in force since 27 July 2026. It moves the Annex III high-risk obligations to 2 December 2027. The EUR-Lex text was not read. Status: PENDING_RELOCK.
- **GT-0025** (CONTESTED → VERIFIED_SECONDARY): Colorado SB 26-189 was signed 14 May 2026 and takes effect 1 January 2027. A pending court challenge and outstanding Attorney General rules may affect it. Recheck by 2027-01-15. Status: PENDING_RELOCK.
- C13 stays warn-only until a human re-locks both rows.
