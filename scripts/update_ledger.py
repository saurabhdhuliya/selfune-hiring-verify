"""Build ledger/hiring.jsonl from the locked source file.

Adds: recheck_by, use_as, display_label. Applies the 2026-11-12 re-check of
CONTESTED rows GT-0009 and GT-0025. Re-checked rows are set to
user_decision = PENDING_RELOCK: a human must lock them again (hard rule 3).

Usage: python scripts/update_ledger.py <source_jsonl> ledger/hiring.jsonl
"""
import json
import sys
from datetime import date

LEGAL_DOMAINS = {"hiring_regulation", "hiring_litigation", "hiring_agent_failure"}
RECHECK_DATE = "2026-11-12"


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, 28)
    return date(y, m, day)


def use_as(status: str) -> str:
    if status == "VENDOR_CLAIM":
        return "context_only"      # never proof: "this is what the vendor says"
    if status == "CONTESTED":
        return "warn_only"         # never a hard fail
    if status == "OWN_DATA":
        return "context_only"      # until second-person review
    if status == "VERIFIED_SECONDARY":
        return "cite_with_caveat"  # flag allowed, but show "what sources report"
    return "proof"


def display_label(status: str) -> str:
    return {
        "VERIFIED_SOURCE": "Verified against the primary or official source",
        "VERIFIED_SECONDARY": "What secondary sources report; not checked against the primary text",
        "VENDOR_CLAIM": "What the vendor says; not proof",
        "OWN_DATA": "Selfune study, not independently verified",
        "CONTESTED": "Sources disagree; warning only",
    }[status]


FIXES = {
    "GT-0009": {
        "claim": "Regulation (EU) 2026/1744 (the Digital Omnibus on AI), published in the Official Journal on 24 July 2026 and in force since 27 July 2026, deferred EU AI Act high-risk obligations for Annex III systems, which include recruitment and candidate selection, from 2 August 2026 to 2 December 2027.",
        "status": "VERIFIED_SECONDARY",
        "source_tier": "T3",
        "evidence": {
            "url": "https://www.actuia.com/en/news/ai-act-obligations-in-force-and-delays-under-omnibus-2026-1744/",
            "locator": "opening paragraphs and timeline table",
            "retrieved": RECHECK_DATE,
            "other_urls": [
                "https://www.aiacto.eu/en/blog/digital-omnibus-ai-act-report-2027",
                "https://www.secureaudit.nl/en/knowledge-base/eu-ai-act-digital-omnibus-deadlines",
                "https://www.joneswalker.com/en/insights/blogs/ai-law-blog/yes-august-2-still-matters-the-eu-approved-a-high-risk-ai-delay-but-most-trans.html",
            ],
        },
        "caveats": "Several independent secondary sources agree on the regulation number, publication and dates; the EUR-Lex text was not read. The Article 5 prohibitions, including emotion inference at work (GT-0008), were not deferred.",
        "claim_history": "Was CONTESTED (one older source said August 2026 still stood). Re-checked 2026-11-12: the deferral is now published law per multiple sources. Upgraded to VERIFIED_SECONDARY.",
        "recheck_by": "2027-05-12",
    },
    "GT-0025": {
        "claim": "Colorado SB 26-189, signed 14 May 2026, repealed and replaced the 2024 Colorado AI Act (SB 24-205) with a narrower law on automated decision-making technology used to materially influence consequential decisions, including employment; it takes effect 1 January 2027 for decisions made on or after that date.",
        "status": "VERIFIED_SECONDARY",
        "source_tier": "T3",
        "evidence": {
            "url": "https://www.finnegan.com/en/insights/articles/colorado-replaces-landmark-ai-act-an-overview-of-the-new-sb-26-189-framework.html",
            "locator": "opening paragraphs",
            "retrieved": RECHECK_DATE,
            "other_urls": [
                "https://www.dwt.com/blogs/privacy--security-law-blog/2026/05/colorado-ai-act-repeal-new-transparency-law",
                "https://www.eckertseamans.com/legal-updates/colorado-repeals-and-replaces-its-landmark-ai-statute-what-businesses-need-to-know",
            ],
        },
        "caveats": "Several law-firm sources agree. One source says the effective date could be delayed by a pending federal court challenge, and another says enforcement depends on Attorney General rules. Colorado legislature text not read. Keep C13 warn-only until a human re-locks.",
        "claim_history": "Was CONTESTED (one unread headline seemed to conflict). Re-checked 2026-11-12: the conflicting headline concerned the repealed 2024 law. Upgraded to VERIFIED_SECONDARY. Recheck date shortened because of the pending court challenge.",
        "recheck_by": "2027-01-15",
    },
}


def main(src: str, dst: str) -> None:
    rows = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
    assert len(rows) == 50, len(rows)
    out = []
    for r in rows:
        fix = FIXES.get(r["id"])
        if fix:
            r.update({k: v for k, v in fix.items() if k != "recheck_by"})
            r["user_decision"] = "PENDING_RELOCK"
            r["lock_note"] = "Re-checked by Claude on 2026-11-12. A human must review and re-lock."
            r["recheck_by"] = fix["recheck_by"]
        else:
            retrieved = date.fromisoformat(r["evidence"]["retrieved"])
            months = 6 if r["domain"] in LEGAL_DOMAINS else 24
            r["recheck_by"] = add_months(retrieved, months).isoformat()
        r["use_as"] = use_as(r["status"])
        r["display_label"] = display_label(r["status"])
        out.append(r)
    with open(dst, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
