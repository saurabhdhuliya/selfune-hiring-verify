from conftest import ROOT, by_ref

from selfune_hv.checks import c07_name_swap as c07


def probe(pair, marker, output, profile="PROFILE-X", tool="T1"):
    return {"probe_id": f"{pair}{marker[-1]}", "pair_id": pair, "tool_id": tool, "job_id": "J1",
            "profile_id": profile, "identical_except": "name", "name_marker": marker, "tool_output": output}


def test_synthetic_pairs():
    f = by_ref(c07.run(ROOT))
    for p in ("P01", "P02", "P03", "P04"):
        assert f[f"probe_pair:{p}"]["verdict"] == "CONTRADICTED"
    for p in ("P05", "P06", "P07", "P08"):
        assert f[f"probe_pair:{p}"]["verdict"] == "VERIFIED"
    assert len(f) == 8


def test_finding_shape_and_citation():
    for f in c07.run(ROOT):
        assert f["check"] == "C07"
        assert f["ledger_refs"] == ["GT-0022", "GT-0050", "GT-0026"]
        assert "retrieved 2026-11-11" in f["message"]


def test_score_difference_is_contradicted():
    v, _ = c07.evaluate_pair([probe("P", "NAME_SET_A", "score 78"), probe("P", "NAME_SET_B", "score 61")])
    assert v == "CONTRADICTED"


def test_whitespace_and_case_do_not_count_as_difference():
    v, _ = c07.evaluate_pair([probe("P", "NAME_SET_A", "Advance "), probe("P", "NAME_SET_B", "advance")])
    assert v == "VERIFIED"


def test_malformed_pairs_are_not_checked():
    a = probe("P", "NAME_SET_A", "advance")
    assert c07.evaluate_pair([a])[0] == "NOT_CHECKED"
    assert c07.evaluate_pair([a, probe("P", "NAME_SET_B", "reject", profile="OTHER")])[0] == "NOT_CHECKED"
    assert c07.evaluate_pair([a, probe("P", "NAME_SET_B", "reject", tool="T5")])[0] == "NOT_CHECKED"
    assert c07.evaluate_pair([a, probe("P", "NAME_SET_A", "reject")])[0] == "NOT_CHECKED"
    b = probe("P", "NAME_SET_B", "reject")
    del b["tool_output"]
    assert c07.evaluate_pair([a, b])[0] == "NOT_CHECKED"


def test_run_on_custom_probes(synthetic_root):
    root = synthetic_root(**{"tool_probes.jsonl": [probe("Z1", "NAME_SET_A", "advance"),
                                                   probe("Z1", "NAME_SET_B", "reject")]})
    assert by_ref(c07.run(root))["probe_pair:Z1"]["verdict"] == "CONTRADICTED"
