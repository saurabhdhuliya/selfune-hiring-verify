from conftest import ROOT, by_ref

from selfune_hv.checks import c04_selection_method as c04


def test_synthetic_jobs():
    f = by_ref(c04.run(ROOT))
    assert f["job:J1:selection_method"]["verdict"] == "UNVERIFIED"
    assert f["job:J3:selection_method"]["verdict"] == "UNVERIFIED"
    assert f["job:J2:selection_method"]["verdict"] == "VERIFIED"


def test_holistic_alone_is_unverified():
    v, d = c04.evaluate_method({"stages": ["work sample", "structured interview"], "combine": "holistic"})
    assert v == "UNVERIFIED" and "GT-0033" in d


def test_unstructured_only_interview_is_unverified():
    v, d = c04.evaluate_method({"stages": ["work sample", "unstructured interview"], "combine": "mechanical"})
    assert v == "UNVERIFIED" and "GT-0006" in d


def test_structured_plus_unstructured_is_fine():
    v, _ = c04.evaluate_method({"stages": ["unstructured interview", "structured interview"], "combine": "mechanical"})
    assert v == "VERIFIED"


def test_no_interview_mechanical_is_verified():
    assert c04.evaluate_method({"stages": ["work sample"], "combine": "mechanical"})[0] == "VERIFIED"


def test_missing_method_is_not_checked():
    assert c04.evaluate_method(None)[0] == "NOT_CHECKED"
    assert c04.evaluate_method({"stages": ["work sample"]})[0] == "NOT_CHECKED"
    assert c04.evaluate_method({"stages": [], "combine": "mechanical"})[0] == "NOT_CHECKED"


def test_citations():
    for f in c04.run(ROOT):
        assert f["ledger_refs"] == ["GT-0006", "GT-0007", "GT-0033"]
        assert "retrieved 2026-10-29" in f["message"] and "retrieved 2026-11-11" in f["message"]
