"""Selfune Hiring Verify: web demo (Hugging Face Space).

Four tabs: check a job post, check one decision, run a full audit, and how it works.
Checks the hiring PROCESS, never a person: it does not score, rank or reject anyone. No emotion or personality
inference. LLM output is never evidence: an optional small model may only cut messy text into claims, and rules decide
every verdict. Nothing you paste or upload is stored.
Code: https://github.com/saurabhdhuliya/selfune-hiring-verify
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import gradio as gr

import llm_split
import views
from selfune_hv.decision_mode import verify_decision
from selfune_hv.loop import report_json, run_folder
from selfune_hv.paths import resource_root
from selfune_hv.report import render_html
from selfune_hv.text_mode import verify_text

ROOT = resource_root()
JOB_CHECKS = ["C01", "C02", "C03", "C08"]     # C01-C03 as asked; C08 so an age rule is never asked to justify itself
MAX_TEXT = 20000
MAX_ZIP_BYTES = 5 * 1024 * 1024
MAX_UNZIPPED_BYTES = 20 * 1024 * 1024
DATA_FILES = {"company.json", "decisions.jsonl", "tools.json", "group_counts.json", "role_memory.json",
              "ai_text.jsonl", "tool_probes.jsonl", "policy_statements.jsonl"}

JOB_EXAMPLES = [
    ["Customer Support Rep\n\nWe want a rockstar support ninja with excellent communication skills and a great attitude.\n"
     "Strong team player and a culture fit.\n"
     "Answers 40 chat tickets per shift with an average customer rating of 4.5 or higher, because ratings drive renewals."],
    ["Backend Engineer\n\nWhat you bring:\n- Minimum 5 years of backend experience.\n- 3+ years of Go experience.\n"
     "- Ships and debugs production services, because the team owns uptime."],
    ["Operations Assistant\n\nRequirements:\n- Graduation year 2022 or later.\n- Applicants must be aged 21 to 30.\n"
     "- Uses spreadsheets daily, tested in a 30-minute exercise, because stock reports are built in Excel."],
    ["Data Analyst\n\nRequirements:\n"
     "- Writes SQL that answers a weekly sales question, tested in a 90-minute work sample, because reports pull from SQL.\n"
     "- Reconciles two exports with under 1% variance in a 2-hour exercise, so that finance can close the month on time."],
]
DECISION_EXAMPLES = [
    ["Rejected: no references on file; the vendor AI rated low potential; vendor reports 95% accuracy.", "rejected", "tool", "EU", "references"],
    ["Graduation year 2012 is too early for this role.", "rejected", "human", "NYC", ""],
    ["Candidate video analysis: dominant emotion anxiety, intensity 6/10.", "rejected", "both", "other", ""],
    ["Work sample 72/100, above the pre-set 60, reviewed by a hiring manager.", "advanced", "human", "EU", ""],
]
FOLDER_DOC = """\
**Zip format** (same as `docs/schema.md` in the repo). Put these files at the top of the zip or in one folder inside it:

| File | Required | What |
|---|---|---|
| `company.json` | yes | employer and jobs, each with `requirements` and `jurisdiction` |
| `decisions.jsonl` | yes | one decision per line: `decision_id`, `candidate_ref` (anonymous), `job_id`, `stage`, `outcome`, `reason_text`, `fields_present`, `fields_missing`, `decision_date`, optional `decided_by`, `tools_used` |
| `tools.json`, `group_counts.json`, `role_memory.json`, `ai_text.jsonl`, `tool_probes.jsonl`, `policy_statements.jsonl` | no | a missing file means those checks report NOT_CHECKED |

Use anonymous references only. Files are read in a temporary folder that is deleted right after the run.
"""


# ---------------------------------------------------------------- tab 1
def check_job_post(text: str, use_model: bool) -> str:
    text = (text or "").strip()
    if not text:
        return views.message("Paste a job post first.")
    if len(text) > MAX_TEXT:
        return views.message(f"Text is too long. Paste up to {MAX_TEXT:,} characters.")
    try:
        claims, note = (llm_split.split_claims(text) if use_model else (None, llm_split.FALLBACK))
        return views.job_post(verify_text(text, ROOT, checks=JOB_CHECKS, claims=claims), note)
    except Exception as err:  # a plain message, never a stack trace
        return views.message(f"Something went wrong ({type(err).__name__}). Please report it on GitHub.")


# ---------------------------------------------------------------- tab 2
def check_decision(reason: str, outcome: str, decided_by: str, jurisdiction: str, fields_missing: str) -> str:
    reason = (reason or "").strip()
    if not reason:
        return views.message("Paste the stated reason for the decision first.")
    if len(reason) > MAX_TEXT:
        return views.message(f"Text is too long. Paste up to {MAX_TEXT:,} characters.")
    try:
        return views.decision(verify_decision(reason, outcome, None if decided_by == "not recorded" else decided_by,
                                              jurisdiction, fields_missing, ROOT))
    except Exception as err:
        return views.message(f"Something went wrong ({type(err).__name__}). Please report it on GitHub.")


# ---------------------------------------------------------------- tab 3
def _audit_outputs(report: dict, label: str):
    """(summary + inline report HTML, [files to download]). Files are purged from Gradio's cache within minutes."""
    out_dir = Path(tempfile.mkdtemp(prefix="selfune-out-"))
    files = []
    for name, body in (("report.json", json.dumps(report_json(report), indent=2, ensure_ascii=False)),
                       ("report.html", render_html(report))):
        p = out_dir / name
        p.write_text(body, encoding="utf-8")
        files.append(str(p))
    return views.audit(report, label) + views.report_frame(render_html(report)), files


def _error_html(problems: list[str]) -> str:
    items = "".join(f"<li>{views.e(p)}</li>" for p in problems[:20])
    return f'<div class="sv">{views.CSS}<b>Nothing was run.</b><ul>{items}</ul></div>'


def run_sample():
    report, errs = run_folder(ROOT, ROOT / "data/synthetic")
    if errs:
        return _error_html(errs), None
    return _audit_outputs(report, "Sample company (synthetic data)")


def unpack_zip(path: str, dest: Path) -> list[str]:
    """Copy the known data files from a zip into `dest`. Returns problems. Never extracts anything else, never trusts paths."""
    if os.path.getsize(path) > MAX_ZIP_BYTES:
        return [f"Zip is over {MAX_ZIP_BYTES // 1024 // 1024} MB."]
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return ["That file is not a zip."]
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir() and Path(i.filename).name in DATA_FILES
                 and not Path(i.filename).name.startswith("._") and "__MACOSX" not in i.filename]
        if sum(i.file_size for i in infos) > MAX_UNZIPPED_BYTES:
            return ["The data files are too large (over 20 MB unzipped)."]
        folders = {}
        for i in infos:
            folders.setdefault(str(Path(i.filename).parent), {})[Path(i.filename).name] = i
        ready = [f for f, files in folders.items() if {"company.json", "decisions.jsonl"} <= set(files)]
        if not ready:
            return ["No folder with both company.json and decisions.jsonl found in the zip."]
        for name, info in folders[min(ready, key=lambda f: len(Path(f).parts))].items():
            (dest / name).write_bytes(zf.read(info))     # fixed names only: no path from the zip is ever used
    return []


def run_upload(zip_path: str | None):
    """(report html, download files, cleared upload box). The uploaded copy is deleted after the run."""
    if not zip_path or not os.path.exists(zip_path):
        return _error_html(["Upload a zip first."]), None, None
    work = Path(tempfile.mkdtemp(prefix="selfune-in-"))
    try:
        problems = unpack_zip(zip_path, work)
        if problems:
            return _error_html(problems), None, None
        report, errs = run_folder(ROOT, work)
        if errs:
            return _error_html(errs), None, None
        html_out, files = _audit_outputs(report, "Your uploaded folder")
        return html_out, files, None
    except Exception as err:
        return _error_html([f"Something went wrong ({type(err).__name__}). Check the folder format."]), None, None
    finally:
        shutil.rmtree(work, ignore_errors=True)          # nothing uploaded is stored
        try:
            os.remove(zip_path)
        except OSError:
            pass


# ---------------------------------------------------------------- app
with gr.Blocks(title="Selfune Hiring Verify", delete_cache=(60, 300)) as demo:
    gr.Markdown("# Selfune Hiring Verify\nChecks the hiring **process**, never the person. It does not score, rank or "
                f"reject anyone. Nothing you paste or upload is stored. [Open source on GitHub]({views.REPO}).")
    with gr.Tabs():
        with gr.Tab("Check a job post"):
            gr.HTML(views.banner())
            gr.Markdown("Paste a job post. It is split into requirement lines, each is checked for an undefined trait (C01), "
                        "years used as a proxy (C02) and no stated reason (C03), then the **mother assumptions** are "
                        "returned: the 1-3 questions that unblock the most. It also screens for age proxies (C08), so an "
                        "age rule is never asked to justify itself.")
            post = gr.Textbox(lines=12, label="Job post", placeholder="Requirements:\n- 5+ years of experience\n- Excellent communication skills")
            use_model = gr.Checkbox(False, label="Use a small open model to split messy text into one-sentence claims (optional)",
                                    info="Rules still decide every verdict. If the model fails, lines are split by line breaks.")
            b1 = gr.Button("Check job post", variant="primary")
            out1 = gr.HTML()
            gr.Examples(JOB_EXAMPLES, inputs=post, label="Try an example")
            b1.click(check_job_post, [post, use_model], out1, api_name="check_job_post")
        with gr.Tab("Check a decision"):
            gr.HTML(views.banner())
            gr.Markdown("Paste the stated reason for one decision, with its outcome and who decided. Checks: missing field "
                        "used as a negative (C06), age or age proxy (C08), emotion or personality inference (C09), GDPR "
                        "Art 22 (C11, EU jobs only), vendor claim as proof (C15).")
            reason = gr.Textbox(lines=5, label="Stated reason for the decision")
            with gr.Row():
                outcome = gr.Radio(["rejected", "advanced", "on_hold"], value="rejected", label="Outcome")
                decided_by = gr.Radio(["human", "tool", "both", "not recorded"], value="human", label="Decided by")
                jurisdiction = gr.Dropdown(["EU", "NYC", "IL", "IN", "CO", "other"], value="other", label="Jurisdiction")
            fields = gr.Textbox(label="Application fields left empty (optional, comma-separated)",
                                placeholder="references, portfolio url")
            b2 = gr.Button("Check decision", variant="primary")
            out2 = gr.HTML()
            gr.Examples(DECISION_EXAMPLES, inputs=[reason, outcome, decided_by, jurisdiction, fields], label="Try an example")
            b2.click(check_decision, [reason, outcome, decided_by, jurisdiction, fields], out2, api_name="check_decision")
        with gr.Tab("Full audit"):
            gr.HTML(views.banner())
            gr.Markdown("Run the full loop (all 15 checks, one decision chain per decision) on a company folder. "
                        "The report starts with the mother assumptions.")
            b3 = gr.Button("Run on sample company", variant="primary")
            gr.Markdown("**Or upload your own folder as a zip** (anonymous references only).")
            up = gr.File(label="Zip of the data folder", file_types=[".zip"], type="filepath")
            b4 = gr.Button("Run on uploaded zip")
            with gr.Accordion("Zip format", open=False):
                gr.Markdown(FOLDER_DOC)
            out3 = gr.HTML()
            dl = gr.File(label="Download report.json and report.html", file_count="multiple", interactive=False)
            b3.click(run_sample, None, [out3, dl], api_name="run_sample")
            b4.click(run_upload, up, [out3, dl, up], api_name="run_upload")
        with gr.Tab("How it works & limits"):
            gr.HTML(views.banner())
            gr.HTML(views.how_it_works())

if __name__ == "__main__":
    demo.launch(max_file_size="5mb")
