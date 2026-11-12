"""Generate the synthetic hiring test set (section 9 of the brief).

Fake employer, 3 jobs, 200 fake candidates, ~40 planted problems, ~40 clean
items, a few NOT_CHECKED cases. Answers go to labels/labels.jsonl, which the
loop must never read. Deterministic (fixed seed). No real names anywhere:
candidates are CAND-0001..0200; name-swap probes use placeholder markers.

ERD is used only to build C9 inputs (emotion-inference text the loop must
block). See scripts/build_c9_corpus.py and docs/erd_use.md.

Usage: python scripts/generate_synthetic.py [--erd path/to/ERD.xlsx]
"""
import argparse
import json
import os
import random
from datetime import date

SEED = 20261112
TODAY = date(2026, 11, 12)
OUT = "data/synthetic"
LABELS = "labels/labels.jsonl"

rng = random.Random(SEED)
labels: list[dict] = []


def label(obj_ref: str, check: str, planted: bool, expected: str, note: str, ledger: list[str]):
    labels.append({
        "label_id": f"L{len(labels) + 1:03d}",
        "object_ref": obj_ref,
        "check": check,
        "planted": planted,
        "expected_verdict": expected,
        "ledger_refs": ledger,
        "note": note,
    })


# ---------------------------------------------------------------- company + jobs
company = {
    "employer_id": "EMP-NORTHWIND-SYN",
    "employer_name": "Northwind Synthetic Ltd (fictional)",
    "jobs": [
        {
            "job_id": "J1",
            "title": "Customer Support Specialist",
            "description": "Handle inbound chat and email for a subscription product. Some customers are upset; agents de-escalate within policy.",
            "jurisdiction": ["NYC"],
            "selection_method": {
                "stages": ["tool ranking (T1)", "unstructured interview"],
                "combine": "holistic",
                "combine_note": "Hiring manager reviews the rank and interview impressions and decides overall.",
            },
            "requirements": [
                {"req_id": "J1-R1", "text": "Strong communication skills, because agents resolve escalated customer complaints."},
                {"req_id": "J1-R2", "text": "Resolves at least 85% of tier-1 tickets within 24 hours in a paid trial week, because response time drives renewals."},
                {"req_id": "J1-R3", "text": "Minimum 5 years of customer support experience."},
                {"req_id": "J1-R4", "text": "Excellent attitude and positive energy."},
                {"req_id": "J1-R5", "text": "Typing speed of 60 words per minute."},
            ],
        },
        {
            "job_id": "J2",
            "title": "Backend Engineer",
            "description": "Build and run Python services for the billing platform. On-call one week in six.",
            "jurisdiction": ["EU"],
            "selection_method": {
                "stages": ["tool screen (T5)", "work sample", "structured interview"],
                "combine": "mechanical",
                "combine_note": "Fixed weights set before screening: work sample 50%, structured interview 50%.",
            },
            "requirements": [
                {"req_id": "J2-R1", "text": "Strong Python skills, because the billing backend is Python."},
                {"req_id": "J2-R2", "text": "Ships and debugs production services, because the team owns uptime."},
                {"req_id": "J2-R3", "text": "3+ years of Go experience."},
                {"req_id": "J2-R4", "text": "Has contributed to open-source projects, because it shows code review experience."},
                {"req_id": "J2-R5", "text": "Team player with a great culture fit."},
            ],
        },
        {
            "job_id": "J3",
            "title": "Operations Analyst",
            "description": "Inventory and cost reporting for warehouses. Offices in Bengaluru and Chicago.",
            "jurisdiction": ["IN", "IL"],
            "selection_method": {
                "stages": ["tool filter (T9)", "job knowledge test", "structured interview"],
                "combine": "holistic",
                "combine_note": "Panel discusses test and interview results and reaches a consensus.",
            },
            "requirements": [
                {"req_id": "J3-R1", "text": "Excellent attention to detail."},
                {"req_id": "J3-R2", "text": "Reconciles weekly inventory with under 1% variance in a 2-hour exercise, because stock errors cost margin."},
                {"req_id": "J3-R3", "text": "Minimum 8 years in operations."},
                {"req_id": "J3-R4", "text": "Advanced Excel certification (MO-201)."},
                {"req_id": "J3-R5", "text": "MBA from a top-20 school."},
                {"req_id": "J3-R6", "text": "Has used SQL to answer a business question, tested in the work sample, because reports pull from SQL."},
            ],
        },
    ],
}

# C1 undefined trait (GT-0019, GT-0021)
for r, p, n in [
    ("J1-R1", True, "'Strong' undefined; reason given, trait not defined."),
    ("J1-R4", True, "'Excellent attitude', 'positive energy' undefined."),
    ("J2-R5", True, "'Team player', 'culture fit' undefined."),
    ("J3-R1", True, "'Excellent attention to detail' undefined."),
    ("J1-R2", False, "Observable, measured in trial week."),
    ("J2-R1", False, "'Strong Python' is defined in role memory TR-J2-PY: should verify without asking."),
    ("J2-R2", False, "Defined in role memory TR-J2-PROD."),
    ("J3-R2", False, "Observable, measured in exercise."),
]:
    label(f"requirement:{r}", "C01", p, "UNVERIFIED" if p else "VERIFIED", n, ["GT-0019", "GT-0021"])

# C2 years as proxy (GT-0019)
for r, p, n in [
    ("J1-R3", True, "5 years as proxy for ability."),
    ("J2-R3", True, "3+ years Go as proxy."),
    ("J3-R3", True, "8 years as proxy."),
    ("J2-R4", False, "Experience type, not a years count."),
    ("J3-R6", False, "Tested directly in work sample."),
]:
    label(f"requirement:{r}", "C02", p, "UNVERIFIED" if p else "VERIFIED", n, ["GT-0019"])

# C3 no stated reason (GT-0020)
for r, p, n in [
    ("J1-R5", True, "Typing speed: no reason it predicts performance."),
    ("J3-R4", True, "Certification: no reason stated."),
    ("J3-R5", True, "Top-20 MBA: no reason stated (also a degree proxy)."),
    ("J1-R2", False, "Reason stated: response time drives renewals."),
    ("J2-R4", False, "Reason stated (itself an assumption, but stated)."),
    ("J3-R2", False, "Reason stated: stock errors cost margin."),
]:
    label(f"requirement:{r}", "C03", p, "UNVERIFIED" if p else "VERIFIED", n, ["GT-0020"])

# C4 selection method (GT-0006, GT-0007, GT-0033)
label("job:J1:selection_method", "C04", True, "UNVERIFIED", "Unstructured interview only plus holistic combination.", ["GT-0006", "GT-0033"])
label("job:J3:selection_method", "C04", True, "UNVERIFIED", "Holistic panel combination of valid methods.", ["GT-0033"])
label("job:J2:selection_method", "C04", False, "VERIFIED", "Work sample + structured interview, mechanical weights.", ["GT-0006", "GT-0033"])

# ---------------------------------------------------------------- role memory
role_memory = {
    "employer_id": company["employer_id"],
    "roles": [
        {
            "role_id": "J1",
            "role_need": "Keep paying customers by resolving their problems quickly.",
            "role_need_defined_by": "Head of Support",
            "traits": [],
        },
        {
            "role_id": "J2",
            "role_need": "Keep the billing platform correct and available.",
            "role_need_defined_by": "Engineering Manager, Billing",
            "traits": [
                {
                    "trait_id": "TR-J2-PY",
                    "terms": ["strong python", "python skills", "strong python skills"],
                    "definition": "Writes and tests a small Python service change that passes review without major rework.",
                    "observable_evidence": ["work sample passes 8 of 10 hidden tests", "structured interview Q3 score of 3 or more out of 5"],
                    "measured_by": "work sample + structured interview Q3",
                    "why_it_predicts": "Most tickets are Python changes to billing services.",
                    "ledger_refs": ["GT-0006"],
                    "defined_by": "Engineering Manager, Billing",
                    "defined_on": "2026-09-01",
                    "review_by": "2027-09-01",
                    "status": "ACTIVE",
                    "version": 1,
                },
                {
                    "trait_id": "TR-J2-PROD",
                    "terms": ["ships and debugs production services", "production debugging"],
                    "definition": "Finds the cause of a seeded production bug from logs within 45 minutes.",
                    "observable_evidence": ["debugging exercise: root cause named and fix proposed in 45 minutes"],
                    "measured_by": "work sample part B",
                    "why_it_predicts": "The team is on call and owns uptime.",
                    "ledger_refs": ["GT-0006"],
                    "defined_by": "Engineering Manager, Billing",
                    "defined_on": "2026-09-01",
                    "review_by": "2027-09-01",
                    "status": "ACTIVE",
                    "version": 1,
                },
            ],
        },
        {
            "role_id": "J3",
            "role_need": "Cut stock and cost errors in warehouse reporting.",
            "role_need_defined_by": "Operations Director",
            "traits": [
                {
                    "trait_id": "TR-J3-DETAIL",
                    "terms": ["attention to detail"],
                    "definition": "Finds seeded errors in a reconciliation sheet.",
                    "observable_evidence": ["finds 4 of 5 seeded errors in exercise"],
                    "measured_by": "job knowledge test part 2",
                    "why_it_predicts": "Errors in weekly reports drive stock losses.",
                    "ledger_refs": ["GT-0006"],
                    "defined_by": "Operations Director",
                    "defined_on": "2025-06-01",
                    "review_by": "2026-06-01",
                    "status": "ACTIVE",
                    "version": 1,
                }
            ],
        },
    ],
}
# J3-R1 maps to TR-J3-DETAIL, but that definition passed review_by: lookup returns STALE -> still UNVERIFIED (label above).

# ---------------------------------------------------------------- tools
tools = [
    {"tool_id": "T1", "job_ids": ["J1"], "name": "ScreenRank", "vendor": "Acme Talent AI (fictional)",
     "what_it_outputs": "rank 1-100", "used_for": "rank", "decision_mode": "weighted_most",
     "employer_scope_claim": "in scope", "last_bias_audit_date": "2025-09-15",
     "notice_sent_date": "2026-10-26", "first_use_date": "2026-11-02", "infers_emotion": False,
     "vendor_claims": ["Predicts top performers with 95% accuracy."]},
    {"tool_id": "T2", "job_ids": ["J1"], "name": "SchedBot", "vendor": "Calendly-like Co (fictional)",
     "what_it_outputs": "interview time slots", "used_for": "interview", "decision_mode": "none",
     "employer_scope_claim": "not in scope", "infers_emotion": False, "vendor_claims": []},
    {"tool_id": "T3", "job_ids": ["J1"], "name": "QuickFilter", "vendor": "FastHire (fictional)",
     "what_it_outputs": "pass/fail", "used_for": "screen", "decision_mode": "overrides_human",
     "employer_scope_claim": "not in scope", "last_bias_audit_date": None,
     "notice_sent_date": None, "first_use_date": "2026-08-01", "infers_emotion": False, "vendor_claims": []},
    {"tool_id": "T4", "job_ids": ["J1"], "name": "SkillCheck", "vendor": "TestWorks (fictional)",
     "what_it_outputs": "typing and ticket-triage score", "used_for": "assess", "decision_mode": "weighted_most",
     "employer_scope_claim": "in scope", "last_bias_audit_date": "2026-03-01",
     "notice_sent_date": "2026-09-01", "first_use_date": "2026-09-20", "infers_emotion": False, "vendor_claims": []},
    {"tool_id": "T13", "job_ids": ["J1"], "name": "ChatScreen", "vendor": "TalkHire (fictional)",
     "what_it_outputs": "screen score", "used_for": "screen", "decision_mode": "weighted_most",
     "employer_scope_claim": "in scope",
     "notice_sent_date": "2026-09-01", "first_use_date": "2026-09-25", "infers_emotion": False, "vendor_claims": []},
    {"tool_id": "T5", "job_ids": ["J2"], "name": "CodeSift", "vendor": "DevGate (fictional)",
     "what_it_outputs": "score 0-100, auto-reject below 70", "used_for": "screen", "decision_mode": "alone",
     "human_review": False, "lawful_basis": None, "infers_emotion": False, "vendor_claims": []},
    {"tool_id": "T6", "job_ids": ["J2"], "name": "InterviewLens", "vendor": "FaceSignal (fictional)",
     "what_it_outputs": "enthusiasm and stress scores from facial expressions and voice tone", "used_for": "interview",
     "decision_mode": "advisory", "human_review": True, "lawful_basis": "consent", "infers_emotion": True,
     "vendor_claims": ["Measures candidate enthusiasm and stress from video."]},
    {"tool_id": "T7", "job_ids": ["J2"], "name": "CalendarAI", "vendor": "SlotCo (fictional)",
     "what_it_outputs": "time slots", "used_for": "interview", "decision_mode": "none",
     "human_review": True, "lawful_basis": "legitimate interest", "infers_emotion": False, "vendor_claims": []},
    {"tool_id": "T8", "job_ids": ["J2"], "name": "TestGrader", "vendor": "GradeIt (fictional)",
     "what_it_outputs": "job knowledge test score", "used_for": "assess", "decision_mode": "advisory",
     "human_review": True, "lawful_basis": "contract necessity; human review and contest route offered",
     "infers_emotion": False, "vendor_claims": ["Assesses critical thinking."]},
    {"tool_id": "T9", "job_ids": ["J3"], "name": "AgeSmart Filter", "vendor": "QuickOps HR (fictional)",
     "what_it_outputs": "pass/reject", "used_for": "screen", "decision_mode": "alone",
     "rules": ["auto-reject if graduation_year < 1995"],
     "il_notice_sent": None, "il_disparate_effect_review": None,
     "consent_notice": None, "purpose_stated": "screening", "retention_days": "indefinite",
     "infers_emotion": False, "vendor_claims": []},
    {"tool_id": "T10", "job_ids": ["J3"], "name": "SheetTest", "vendor": "Gridly (fictional)",
     "what_it_outputs": "Excel test score", "used_for": "assess", "decision_mode": "advisory",
     "il_notice_sent": "2026-08-01", "il_disparate_effect_review": "2026-07-15: aggregated selection rates reviewed, ratio 0.91",
     "consent_notice": "2026-08-01", "purpose_stated": "assess spreadsheet skill for this role only", "retention_days": 180,
     "infers_emotion": False, "vendor_claims": []},
    {"tool_id": "T11", "job_ids": ["J3"], "name": "VideoScreen", "vendor": "ClipHire (fictional)",
     "what_it_outputs": "video interview summary", "used_for": "interview", "decision_mode": "advisory",
     "infers_emotion": "unknown", "consent_notice": "2026-08-01", "purpose_stated": "interview summary",
     "retention_days": 365, "vendor_claims": []},
]

label("tool:T1:audit_age", "C10", True, "ESCALATE", "Audit 2025-09-15, over 1 year before use; tool weighted most -> in scope.", ["GT-0036", "GT-0038"])
label("tool:T1:notice", "C10", True, "ESCALATE", "Notice 4 business days (strictly between) before first use; needs 10.", ["GT-0037"])
label("tool:T3:scope", "C10", True, "ESCALATE", "Employer says not in scope, but output overrides humans -> in scope; no audit.", ["GT-0038", "GT-0002", "GT-0036"])
label("tool:T4:audit_age", "C10", False, "VERIFIED", "Audit 2026-03-01, within 1 year.", ["GT-0036"])
label("tool:T4:notice", "C10", False, "VERIFIED", "Notice 13 business days before use.", ["GT-0037"])
label("tool:T2:scope", "C10", False, "VERIFIED", "Scheduling only, no decision role; out-of-scope claim holds.", ["GT-0038"])
label("tool:T13:audit_age", "C10", False, "NOT_CHECKED", "Audit date field absent from input: report NOT_CHECKED, never pass.", ["GT-0036"])

label("tool:T6", "C09", True, "ESCALATE", "Infers emotion from face and voice: block (EU ban).", ["GT-0008"])
label("tool:T11", "C09", False, "UNVERIFIED", "infers_emotion unknown: ask the employer, do not pass, do not block.", ["GT-0008"])
label("tool:T1", "C09", False, "VERIFIED", "Rank tool; no emotion output.", ["GT-0008"])

label("tool:T5", "C11", True, "ESCALATE", "EU: tool decides alone, no human review, no lawful basis.", ["GT-0048", "GT-0049"])
label("tool:T7", "C11", False, "VERIFIED", "Scheduling, human review true.", ["GT-0048"])
label("tool:T8", "C11", False, "VERIFIED", "Advisory, human review and contest route documented.", ["GT-0048", "GT-0049"])

label("tool:T9:age_rule", "C08", True, "ESCALATE", "Graduation year < 1995 is a proxy for age.", ["GT-0027", "GT-0024"])
label("tool:T10:rules", "C08", False, "VERIFIED", "No age or age-proxy rule.", ["GT-0027"])

label("tool:T9:illinois", "C12", True, "ESCALATE", "IL applicants screened by tool alone; no notice, no disparate-effect review.", ["GT-0031"])
label("tool:T10:illinois", "C12", False, "VERIFIED", "Notice and aggregated effect review documented.", ["GT-0031"])

label("tool:T9:consent", "C14", True, "ESCALATE", "India: no consent notice.", ["GT-0030"])
label("tool:T9:retention", "C14", True, "ESCALATE", "India: retention 'indefinite'.", ["GT-0030"])
label("tool:T10:dpdp", "C14", False, "VERIFIED", "Consent notice, single purpose, 180-day retention.", ["GT-0030"])
label("tool:T11:dpdp", "C14", False, "VERIFIED", "Consent notice, purpose, 365-day retention stated.", ["GT-0030"])

label("tool:T8:vendor_claim", "C15", False, "VERIFIED", "Vendor claim listed but never used as decision evidence.", ["GT-0017"])

# ---------------------------------------------------------------- candidates + decisions
N = {"J1": 80, "J2": 70, "J3": 50}
SELECTED = {"J1": 20, "J2": 17, "J3": 10}
SKILLS = {
    "J1": ["chat support", "email support", "Zendesk", "refund policy", "billing questions"],
    "J2": ["Python", "Go", "PostgreSQL", "Kubernetes", "observability"],
    "J3": ["Excel", "SQL", "inventory", "cost reporting", "Power BI"],
}

candidates, decisions = [], []
cid = 0
for job, n in N.items():
    for i in range(n):
        cid += 1
        ref = f"CAND-{cid:04d}"
        candidates.append({
            "candidate_ref": ref,
            "job_id": job,
            "years_experience": rng.randint(0, 15),
            "skills": rng.sample(SKILLS[job], k=rng.randint(2, 4)),
            "work_sample_score": rng.randint(30, 95) if rng.random() > 0.1 else None,
            "references_provided": rng.choice([True, True, False, None]),
            "portfolio_present": rng.choice([True, False]),
            "graduation_year": rng.randint(1982, 2024),
            "applicant_location": {"J1": "NYC", "J2": "EU", "J3": rng.choice(["IN", "IL"])}[job],
        })

by_job = {j: [c for c in candidates if c["job_id"] == j] for j in N}

PLANTED_DECISIONS = {
    # (job, index): (outcome, reason, decided_by, fields_missing, label tuple list)
    ("J1", 0): ("rejected", "No references provided, so likely not reliable.", "human", ["references"],
                [("C06", True, "UNVERIFIED", "Missing references treated as evidence of unreliability.", ["GT-0020"])]),
    ("J1", 1): ("rejected", "No salary expectation given, so probably not serious about the role.", "human", ["salary_expectation"],
                [("C06", True, "UNVERIFIED", "Missing field treated as lack of seriousness.", [])]),
    ("J1", 2): ("rejected", "Rejected: the vendor AI rated low potential; vendor reports 95% accuracy.", "both", [],
                [("C15", True, "UNVERIFIED", "Vendor accuracy claim used as proof.", ["GT-0017", "GT-0015"])]),
    ("J1", 3): ("advanced", "Advanced: trial week 91% tier-1 tickets resolved in 24h, above pre-set 85%.", "human", [],
                [("C06", False, "VERIFIED", "Reason rests on measured data.", [])]),
    ("J2", 0): ("rejected", "Portfolio link missing; assume no relevant projects.", "human", ["portfolio_url"],
                [("C06", True, "UNVERIFIED", "Missing link treated as no projects.", [])]),
    ("J2", 1): ("rejected", "Auto-rejected: CodeSift score 64 below 70. No human review.", "tool", [],
                [("C11", True, "ESCALATE", "Solely automated rejection, EU applicant.", ["GT-0048", "GT-0049"])]),
    ("J2", 2): ("on_hold", "Work authorization field missing; held for recruiter follow-up, not rejected.", "human", ["work_authorization"],
                [("C06", False, "VERIFIED", "Missing field routed to a human, not used as a negative.", [])]),
    ("J2", 3): ("rejected", "Rejected after human review of work sample (44/100, pre-set cut-off 60); candidate offered contest route.", "both", [],
                [("C11", False, "VERIFIED", "Human reviewed; contest route offered.", ["GT-0049"])]),
    ("J2", 4): ("rejected", "Rejected: work sample 48/100, pre-set cut-off 60.", None, [],
                [("C11", False, "NOT_CHECKED", "decided_by missing: cannot tell if solely automated.", ["GT-0048"])]),
    ("J3", 0): ("rejected", "Did not list a degree; lacks foundational knowledge.", "human", ["education"],
                [("C06", True, "UNVERIFIED", "Missing degree field treated as lack of knowledge.", ["GT-0019"])]),
    ("J3", 1): ("rejected", "Auto-rejected by AgeSmart Filter: graduation year 1991.", "tool", [],
                [("C08", True, "ESCALATE", "Auto-reject by age proxy.", ["GT-0027", "GT-0024"])]),
    ("J3", 2): ("rejected", "Rejected by panel: job knowledge test 41/100 below pre-set 60.", "human", [],
                [("C08", False, "VERIFIED", "Test score, no age factor.", ["GT-0027"]),
                 ("C06", False, "VERIFIED", "Reason rests on measured data.", [])]),
    ("J3", 3): ("rejected", "Did not complete the required work sample after two reminders.", "human", [],
                [("C06", False, "VERIFIED", "A fact (non-completion), not a missing field.", [])]),
    ("J3", 4): ("rejected", "Rejected: vendor says SheetTest measures critical thinking; candidate scored low.", "both", [],
                [("C15", True, "UNVERIFIED", "Vendor capability claim used as proof.", ["GT-0017"])]),
    ("J3", 5): ("advanced", "Advanced: reconciliation exercise variance 0.4%, under pre-set 1%.", "human", [],
                [("C08", False, "VERIFIED", "No age factor.", ["GT-0027"])]),
}

did = 0
for job in N:
    pool = by_job[job]
    sel_left = SELECTED[job]
    for i, c in enumerate(pool):
        did += 1
        dec_id = f"D{did:04d}"
        if (job, i) in PLANTED_DECISIONS:
            outcome, reason, by, missing, labs = PLANTED_DECISIONS[(job, i)]
            for chk, p, exp, note, led in labs:
                label(f"decision:{dec_id}", chk, p, exp, note, led)
        else:
            remaining = len(pool) - i
            if sel_left > 0 and (rng.random() < sel_left / remaining):
                outcome = "advanced"
                reason = "Advanced: structured interview score above pre-set threshold."
            else:
                outcome = "rejected"
                reason = "Not advanced: work sample below pre-set cut-off."
            by, missing = "human", []
        if outcome == "advanced":
            sel_left -= 1
        present = [k for k, v in c.items() if v is not None and k not in ("candidate_ref", "job_id")]
        d = {
            "decision_id": dec_id,
            "candidate_ref": c["candidate_ref"],
            "job_id": job,
            "stage": "screen",
            "outcome": outcome,
            "reason_text": reason,
            "fields_present": present,
            "fields_missing": missing,
            "decision_date": "2026-11-05",
        }
        if by is not None:
            d["decided_by"] = by
        decisions.append(d)

# Exact selected count per job (for consistency with group counts)
for job in N:
    adv = [d for d in decisions if d["job_id"] == job and d["outcome"] == "advanced"]
    assert len(adv) <= SELECTED[job] + 2

# ---------------------------------------------------------------- group counts (aggregated only)
group_counts = {
    "J1": {
        "sex_self_reported": {"women": {"applied": 40, "selected": 6}, "men": {"applied": 40, "selected": 14}},
        "age_band": {"under_40": {"applied": 56, "selected": 17}, "40_plus": {"applied": 24, "selected": 3}},
    },
    "J2": {
        "sex_self_reported": {"women": {"applied": 35, "selected": 8}, "men": {"applied": 35, "selected": 9}},
        "age_band": {"under_40": {"applied": 50, "selected": 12}, "40_plus": {"applied": 20, "selected": 5}},
    },
    # J3: not provided -> C5 NOT_CHECKED
}
label("group_counts:J1:sex_self_reported", "C05", True, "UNVERIFIED", "Women 0.15 vs men 0.35: ratio 0.43 < 0.8.", ["GT-0023"])
label("group_counts:J1:age_band", "C05", True, "UNVERIFIED", "40+ 0.125 vs under 40 0.304: ratio 0.41 < 0.8.", ["GT-0023", "GT-0024"])
label("group_counts:J2:sex_self_reported", "C05", False, "VERIFIED", "0.229 vs 0.257: ratio 0.89.", ["GT-0023"])
label("group_counts:J2:age_band", "C05", False, "VERIFIED", "0.25 vs 0.24: ratio 0.96 (40+ higher).", ["GT-0023"])
label("group_counts:J3", "C05", False, "NOT_CHECKED", "No group counts provided.", ["GT-0023"])

# ---------------------------------------------------------------- name-swap probes (C7)
probes = []
pid = 0
for tool, job, outcomes, planted in [
    ("T1", "J1", ("advance", "reject"), True),
    ("T1", "J1", ("advance", "reject"), True),
    ("T5", "J2", ("score 78", "score 61"), True),
    ("T5", "J2", ("advance", "reject"), True),
    ("T1", "J1", ("advance", "advance"), False),
    ("T1", "J1", ("reject", "reject"), False),
    ("T5", "J2", ("score 74", "score 74"), False),
    ("T5", "J2", ("advance", "advance"), False),
]:
    pid += 1
    pair = f"P{pid:02d}"
    profile = f"PROFILE-{pid:02d}"
    for variant, out, marker in zip("AB", outcomes, ["NAME_SET_A", "NAME_SET_B"]):
        probes.append({"probe_id": f"{pair}{variant}", "pair_id": pair, "tool_id": tool, "job_id": job,
                       "profile_id": profile, "identical_except": "name", "name_marker": marker, "tool_output": out})
    label(f"probe_pair:{pair}", "C07", planted, "CONTRADICTED" if planted else "VERIFIED",
          "Identical profile, only name marker differs; " + ("different outcome." if planted else "same outcome."),
          ["GT-0022", "GT-0050", "GT-0026"])

# ---------------------------------------------------------------- AI-written text
ai_text = [
    {"text_id": "AT01", "job_id": "J1", "source": "AI-written job post",
     "text": "We want a rockstar support ninja with exceptional drive and an amazing attitude."},
    {"text_id": "AT02", "job_id": "J1", "source": "AI-written job post",
     "text": "Answer 40 chat tickets per shift with an average customer rating of 4.5 or higher."},
    {"text_id": "AT03", "job_id": "J2", "source": "screening summary",
     "text": "Our cheating detector proves this candidate used AI; industry data shows 38.5% of candidates cheat."},
    {"text_id": "AT04", "job_id": "J2", "source": "vendor note",
     "text": "Vendor states TestGrader assesses critical thinking. Not independently validated; not used as decision evidence."},
    {"text_id": "AT05", "job_id": "J1", "source": "interviewer note",
     "text": "Candidate described calming a frustrated customer by offering a refund within policy."},
    {"text_id": "AT06", "job_id": "J1", "source": "AI-written job post",
     "text": "The role handles angry callers and de-escalates within the refund policy."},
    {"text_id": "AT07", "job_id": "J3", "source": "interviewer note",
     "text": "Answered 4 of 5 structured questions fully; arrived on time; completed the exercise."},
    {"text_id": "AT08", "job_id": "J1", "source": "AI-written job post",
     "text": "Stays calm under pressure, measured by handling 3 simulated escalations in 30 minutes."},
]
label("ai_text:AT01", "C01", True, "UNVERIFIED", "'Rockstar', 'exceptional drive', 'amazing attitude' undefined.", ["GT-0019"])
label("ai_text:AT02", "C01", False, "VERIFIED", "Observable, measurable.", ["GT-0019"])
label("ai_text:AT03", "C15", True, "UNVERIFIED", "Vendor dataset figure used as proof about a person.", ["GT-0015"])
label("ai_text:AT04", "C15", False, "VERIFIED", "Vendor claim labelled as claim.", ["GT-0017"])
label("ai_text:AT05", "C09", False, "VERIFIED", "Candidate's account of a customer's emotion: not inference about the candidate.", ["GT-0008"])
label("ai_text:AT06", "C09", False, "VERIFIED", "Emotion word describes the task, not the candidate.", ["GT-0008"])
label("ai_text:AT07", "C09", False, "VERIFIED", "Behaviour-only note.", ["GT-0008"])
label("ai_text:AT08", "C09", False, "VERIFIED", "'Calm' defined as an observable task result.", ["GT-0008"])

# EU / Colorado timing statements (C13, warn only)
policy_statements = [
    {"stmt_id": "PS01", "job_id": "J2", "text": "EU AI Act high-risk duties apply to our screening tool from 2 August 2026."},
    {"stmt_id": "PS02", "job_id": "J2", "text": "EU high-risk duties for recruitment tools are scheduled for 2 December 2027 under Regulation 2026/1744."},
]
label("policy:PS01", "C13", True, "WARN", "Date superseded by GT-0009 re-check; warn only, row pending re-lock.", ["GT-0009"])
label("policy:PS02", "C13", False, "WARN", "Consistent with GT-0009, but row is pending re-lock: still warn-only.", ["GT-0009"])


# ---------------------------------------------------------------- ERD-derived C9 inputs
def erd_ai_text(erd_path: str | None) -> None:
    """Add 3 interview-analysis outputs built from ERD label fields (not the personal narratives)."""
    picks = [
        {"emotion": "Anxiety", "intensity": 7, "readiness": "RED", "pattern": "Anxious Attachment"},
        {"emotion": "Other (none named)", "intensity": None, "readiness": "YELLOW", "pattern": "Avoidant Attachment"},
        {"emotion": "Frustration", "intensity": 6, "readiness": "YELLOW", "pattern": "Perfectionism"},
    ]
    if erd_path:
        import openpyxl
        ws = openpyxl.load_workbook(erd_path, read_only=True).worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        h = rows[0]
        ix = {k: h.index(k) for k in ["Primary Emotion", "Emotion Intensity", "Readiness Level", "Pattern Category"]}
        hd = h.index("Domain")
        body = [r for r in rows[1:]
                if r[ix["Pattern Category"]] and r[hd] != "Unassigned (insufficient input)"
                and not str(r[ix["Primary Emotion"]]).startswith("Other")
                and "Body" not in str(r[ix["Pattern Category"]])]
        r3 = random.Random(SEED).sample(body, 3)
        picks = [{"emotion": r[ix["Primary Emotion"]], "intensity": r[ix["Emotion Intensity"]],
                  "readiness": r[ix["Readiness Level"]], "pattern": r[ix["Pattern Category"]]} for r in r3]
    for k, p in enumerate(picks, start=9):
        parts = []
        if p["emotion"] and not str(p["emotion"]).startswith("Other"):
            parts.append(f"dominant emotion {p['emotion']}" + (f", intensity {p['intensity']}/10" if p["intensity"] else ""))
        parts.append(f"readiness: {p['readiness']}")
        parts.append(f"personality pattern: {p['pattern']}")
        tid = f"AT{k:02d}"
        ai_text.append({"text_id": tid, "job_id": "J2", "source": "AI interview analysis (InterviewLens)",
                        "text": "Candidate video analysis - " + "; ".join(parts) + "."})
        label(f"ai_text:{tid}", "C09", True, "ESCALATE", "ERD-style emotion/personality inference about a candidate: block.", ["GT-0008"])


def full_requirement_labels() -> None:
    """Label every remaining (requirement, check) pair for C01-C03 (v2: no unlabelled requirement pairs).

    Decided from the requirement text alone, using the rule in each check's docstring:
      C01: a vague trait word with no number, threshold or test, and no ACTIVE role-memory definition.
      C02: a years-of-experience count.
      C03: no stated reason (because / so that / required by / purpose 'to').
    Added after all v1 labels so existing label IDs don't change.
    """
    c01 = [
        ("J1-R3", "No vague trait word; a years count (C02's concern)."),
        ("J1-R5", "No vague trait word; measurable (60 wpm)."),
        ("J2-R3", "No vague trait word; a years count (C02's concern)."),
        ("J2-R4", "No vague trait word; an experience type."),
        ("J3-R3", "No vague trait word; a years count (C02's concern)."),
        ("J3-R4", "No vague trait word; a named certification (MO-201) is a test."),
        ("J3-R5", "No vague trait word; a degree proxy, not an undefined trait."),
        ("J3-R6", "No vague trait word; tested in the work sample."),
    ]
    for r, n in c01:
        label(f"requirement:{r}", "C01", False, "VERIFIED", n, ["GT-0019", "GT-0021"])
    c02 = [
        ("J1-R1", "No years count."),
        ("J1-R2", "No years count ('24 hours' is a time limit)."),
        ("J1-R4", "No years count."),
        ("J1-R5", "No years count."),
        ("J2-R1", "No years count."),
        ("J2-R2", "No years count."),
        ("J2-R5", "No years count."),
        ("J3-R1", "No years count."),
        ("J3-R2", "No years count ('2-hour exercise' is a time limit)."),
        ("J3-R4", "No years count."),
        ("J3-R5", "No years count (degree proxy, not years)."),
    ]
    for r, n in c02:
        label(f"requirement:{r}", "C02", False, "VERIFIED", n, ["GT-0019"])
    c03 = [
        ("J1-R3", True, "Years count with no reason stated."),
        ("J1-R4", True, "No reason stated."),
        ("J2-R3", True, "Go years with no reason stated (the backend is Python)."),
        ("J2-R5", True, "No reason stated."),
        ("J3-R1", True, "No reason stated."),
        ("J3-R3", True, "Years count with no reason stated."),
        ("J1-R1", False, "Reason stated: agents resolve escalated complaints."),
        ("J2-R1", False, "Reason stated: the billing backend is Python."),
        ("J2-R2", False, "Reason stated: the team owns uptime."),
        ("J3-R6", False, "Reason stated: reports pull from SQL."),
    ]
    for r, p, n in c03:
        label(f"requirement:{r}", "C03", p, "UNVERIFIED" if p else "VERIFIED", n, ["GT-0020"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--erd", default=None)
    a = ap.parse_args()
    erd_ai_text(a.erd)
    full_requirement_labels()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.dirname(LABELS), exist_ok=True)

    def dump(name, obj):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)

    def dumpl(name, rows):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    dump("company.json", company)
    dump("role_memory.json", role_memory)
    dump("tools.json", tools)
    dump("group_counts.json", group_counts)
    dumpl("candidates.jsonl", candidates)
    dumpl("decisions.jsonl", decisions)
    dumpl("tool_probes.jsonl", probes)
    dumpl("ai_text.jsonl", ai_text)
    dumpl("policy_statements.jsonl", policy_statements)
    with open(LABELS, "w", encoding="utf-8") as f:
        for l in labels:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    p = sum(l["planted"] for l in labels)
    nc = sum(l["expected_verdict"] == "NOT_CHECKED" for l in labels)
    print(f"candidates={len(candidates)} decisions={len(decisions)} labels={len(labels)} planted={p} clean={len(labels) - p - nc} not_checked={nc}")


if __name__ == "__main__":
    main()
