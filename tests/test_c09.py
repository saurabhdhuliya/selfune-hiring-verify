import pytest
from conftest import ROOT, by_ref

from selfune_hv.checks import c09_emotion_inference as c09


def test_synthetic_tools():
    f = by_ref(c09.run(ROOT))
    assert f["tool:T6"]["verdict"] == "ESCALATE"
    assert f["tool:T11"]["verdict"] == "UNVERIFIED"
    assert f["tool:T1"]["verdict"] == "VERIFIED"
    escalated = {k for k, v in f.items() if k.startswith("tool:") and v["verdict"] == "ESCALATE"}
    assert escalated == {"tool:T6"}


def test_synthetic_ai_text():
    f = by_ref(c09.run(ROOT))
    for t in ("AT09", "AT10", "AT11"):
        assert f[f"ai_text:{t}"]["verdict"] == "ESCALATE"
    for t in ("AT05", "AT06", "AT07", "AT08"):
        assert f[f"ai_text:{t}"]["verdict"] == "VERIFIED"


def test_output_naming_construct_escalates_even_if_flag_false():
    v, _ = c09.evaluate_tool({"infers_emotion": False, "what_it_outputs": "culture fit score and personality profile"})
    assert v == "ESCALATE"


def test_infers_emotion_missing_is_not_checked():
    assert c09.evaluate_tool({"what_it_outputs": "rank 1-100"})[0] == "NOT_CHECKED"


@pytest.mark.parametrize("text", [
    "Voice analysis detected frustration during the technical round.",
    "Candidate appears anxious; sentiment score 0.2.",
    "Personality profile: high neuroticism.",
])
def test_inference_text_escalates(text):
    assert c09.evaluate_text(text)[0] == "ESCALATE"


@pytest.mark.parametrize("text", [
    "Candidate described calming a frustrated customer.",
    "The role handles angry callers.",
    "Stays calm under pressure, measured by 3 simulated escalations.",
])
def test_emotion_words_in_allowed_context_pass(text):
    assert c09.evaluate_text(text)[0] == "VERIFIED"


def test_corpus_runs_on_every_input():
    out = c09.run_corpus(ROOT)
    assert len(out) == 496
    assert all(f["object_ref"].startswith("c9_corpus:C9-") for f in out)
    assert {f["verdict"] for f in out} <= {"ESCALATE", "VERIFIED"}


def test_biometric_tool_cites_eu_ban():
    m = by_ref(c09.run(ROOT))["tool:T6"]["message"]
    assert m.startswith("Would block any decision chain that uses this tool")
    assert "EU AI Act prohibits inferring emotions from biometric data at work (GT-0008)" in m
    assert "hard rule 1" not in m


def test_video_ai_text_is_biometric():
    f = by_ref(c09.run(ROOT))
    for t in ("AT09", "AT10", "AT11"):   # "Candidate video analysis ..."
        assert "EU AI Act prohibits" in f[f"ai_text:{t}"]["message"]


def test_text_only_inference_is_policy_block(synthetic_root):
    texts = [{"text_id": "TX1", "job_id": "J2", "source": "screening summary",
              "text": "Personality profile: high neuroticism; sentiment score 0.2."}]
    f = by_ref(c09.run(synthetic_root(**{"ai_text.jsonl": texts})))["ai_text:TX1"]
    assert f["verdict"] == "ESCALATE"
    assert ("Blocked by Selfune hard rule 1 (policy, not a legal claim); EU AI Act ban covers biometric "
            "inference (GT-0008).") in f["message"]
    assert "EU AI Act prohibits" not in f["message"]


@pytest.mark.parametrize("text,bio", [
    ("Voice analysis detected frustration", True),
    ("facial expression scores", True),
    ("keystroke patterns show stress", True),
    ("Personality profile: Boundaries and Enmeshment", False),
    ("Written answers suggest the candidate seems anxious", False),
])
def test_biometric_input_detection(text, bio):
    assert c09.biometric_input(text) is bio


def test_pending_gt0008_does_not_soften_block():
    """C09 rests on hard rule 1 (policy); a pending GT-0008 shows as a warning, not a softer verdict."""
    f = by_ref(c09.run(ROOT))["tool:T6"]
    assert f["verdict"] == "ESCALATE" and "GT-0008 is PENDING_RELOCK" in f["message"]


def test_corpus_messages_split_by_input():
    out = [f for f in c09.run_corpus(ROOT) if f["verdict"] == "ESCALATE"]
    assert any("EU AI Act prohibits" in f["message"] for f in out)
    assert any("Selfune hard rule 1" in f["message"] for f in out)


def test_message_and_citation():
    f = by_ref(c09.run(ROOT))["tool:T6"]
    assert "flag for review, not legal advice" in f["message"]
    assert "GT-0008" in f["message"] and "retrieved 2026-10-29" in f["message"]
