import importlib.util
import re
import sys

from conftest import ROOT

from selfune_hv.decision_mode import verify_decision
from selfune_hv.text_mode import verify_text

sys.path.insert(0, str(ROOT / "space"))
spec = importlib.util.spec_from_file_location("space_views", ROOT / "space/views.py")
views = importlib.util.module_from_spec(spec)
spec.loader.exec_module(views)


def test_banner_text():
    assert "Do not paste real candidate names or personal data." in views.banner()


def test_job_post_view_shows_mother_questions_and_escapes():
    r = verify_text("Requirements:\n- Excellent <b>attitude</b>.", ROOT, checks=["C01"])
    out = views.job_post(r, "line splitting")
    assert "Mother assumptions" in out and "<b>attitude</b>" not in out


def test_decision_view():
    out = views.decision(verify_decision("Graduation year 2012.", "rejected", "human", "NYC", root=ROOT))
    assert "C08" in out and "Not run" in out


def test_how_it_works_matches_readme_scores():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for c, p, f in views.TEST_SCORES:
        assert re.search(rf"\| {c} [^|]*\| {p} \| {f} \|", readme), c
    assert len(views.CHECKS) == 15
