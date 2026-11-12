"""The 2026-11-12 decisions on the adversary check, and how pending rows affect verdicts (hard rule 7)."""
from conftest import ROOT

from selfune_hv import ledger
from selfune_hv.checks._common import Sources

ROWS = ledger.load(str(ROOT / "ledger/hiring.jsonl"))
CHANGED = ("GT-0023", "GT-0008", "GT-0035")


def test_changed_rows_wait_for_relock_with_history():
    for rid in CHANGED:
        r = ROWS[rid]
        assert r["user_decision"] == "PENDING_RELOCK"
        assert r["claim_history"]
        assert r["adversary_date"] == "2026-11-12" and r["adversary_check"] in ("FAILED", "INCONCLUSIVE")


def test_gt0023_decision():
    r = ROWS["GT-0023"]
    assert r["status"] == "VERIFIED_SECONDARY" and r["use_as"] == "cite_with_caveat"
    assert r["recheck_by"] == "2027-01-31"
    assert "EEOC plans to rescind" in r["claim"] and "Title VII" in r["claim"]
    assert any("ogletree.com" in u for u in r["evidence"]["other_urls"])
    assert any("shrm.org" in u for u in r["evidence"]["other_urls"])


def test_gt0008_decision():
    r = ROWS["GT-0008"]
    assert "from biometric data" in r["claim"] and "written text is outside" in r["claim"]
    assert r["status"] == "VERIFIED_SECONDARY"
    assert any("fpf.org" in u for u in r["evidence"]["other_urls"])
    assert any("lewissilkin.com" in u for u in r["evidence"]["other_urls"])


def test_gt0035_caveat_only():
    r = ROWS["GT-0035"]
    assert "Order of penalty amounts could not be confirmed" in r["caveats"]
    assert r["status"] == "VERIFIED_SOURCE" and r["claim"].startswith("The NYC DCWP penalty schedule")


def test_soften_only_hard_fails():
    src = Sources(ROOT, ["GT-0023"])           # pending re-lock
    assert src.soften("UNVERIFIED", ["GT-0023"]) == "UNVERIFIED"
    assert src.soften("ESCALATE", ["GT-0023"]) == "WARN"
    assert src.soften("CONTRADICTED", ["GT-0023"]) == "WARN"
    locked = Sources(ROOT, ["GT-0048"])
    assert locked.soften("ESCALATE", ["GT-0048"]) == "ESCALATE"
