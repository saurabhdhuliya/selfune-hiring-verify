"""Run every check in src/selfune_hv/checks/, write out/findings.jsonl, and score against labels/.

Only this script may read labels/labels.jsonl. While checks run, any attempt to open
a file under labels/ raises an error.

Usage: py scripts/score.py
Exit code 0 if every scored check meets the release rule, otherwise 1.
"""
from __future__ import annotations

import importlib
import json
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import selfune_hv.checks as checks_pkg  # noqa: E402

LABELS_DIR = (ROOT / "labels").resolve()
OUT = ROOT / "out" / "findings.jsonl"
MAX_FALSE_ALARM = 0.10
# Checks with a separate corpus (run_corpus): check -> (findings file in out/, labels file, object_ref prefix, id key)
CORPORA = {"C09": ("c9_findings.jsonl", "c9_labels.jsonl", "c9_corpus:", "c9_id")}

_guard_on = False


def _labels_guard(event: str, args: tuple) -> None:
    if _guard_on and event == "open" and args and isinstance(args[0], (str, bytes, Path)):
        try:
            p = Path(args[0] if not isinstance(args[0], bytes) else args[0].decode()).resolve()
        except (OSError, ValueError):
            return
        if p == LABELS_DIR or LABELS_DIR in p.parents:
            raise PermissionError(f"A check tried to read {p}. Checks must never read labels/.")


def _guarded(fn):
    global _guard_on
    _guard_on = True
    try:
        return fn(ROOT)
    finally:
        _guard_on = False


def run_checks() -> tuple[list[dict], list[str], dict[str, list[dict]]]:
    findings, ran, corpus = [], [], {}
    for mod_info in sorted(pkgutil.iter_modules(checks_pkg.__path__), key=lambda m: m.name):
        mod = importlib.import_module(f"{checks_pkg.__name__}.{mod_info.name}")
        if not (hasattr(mod, "CHECK_ID") and hasattr(mod, "run")):
            continue
        findings.extend(_guarded(mod.run))
        ran.append(mod.CHECK_ID)
        if hasattr(mod, "run_corpus") and mod.CHECK_ID in CORPORA:
            corpus[mod.CHECK_ID] = _guarded(mod.run_corpus)
    return findings, ran, corpus


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def score_corpus(check: str, findings: list[dict]) -> bool:
    """Corpus labels are {<id>, block: bool}. Caught = blocked item gets ESCALATE; false alarm = allowed item does."""
    _, labels_file, prefix, id_key = CORPORA[check]
    with open(LABELS_DIR / labels_file, encoding="utf-8") as f:
        labels = [json.loads(l) for l in f if l.strip()]
    got = {fd["object_ref"]: fd["verdict"] for fd in findings}
    block = [l for l in labels if l["block"]]
    allow = [l for l in labels if not l["block"]]
    caught = sum(got.get(prefix + l[id_key]) == "ESCALATE" for l in block)
    missing = sum(prefix + l[id_key] not in got for l in labels)
    fa = sum(got.get(prefix + l[id_key]) == "ESCALATE" for l in allow)
    fa_rate = fa / len(allow) if allow else 0.0
    ok = caught == len(block) and fa_rate < MAX_FALSE_ALARM and missing == 0
    print(f"{check} corpus ({labels_file}): caught {caught}/{len(block)}, missed {len(block) - caught}, "
          f"false alarms {fa}/{len(allow)}, no finding {missing}  {'PASS' if ok else 'FAIL'}")
    return ok


def load_labels() -> list[dict]:
    with open(LABELS_DIR / "labels.jsonl", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def kind(label: dict) -> str:
    if label["expected_verdict"] == "NOT_CHECKED":
        return "not_checked"
    return "planted" if label["planted"] else "clean"


def score(findings: list[dict], labels: list[dict], ran: list[str]) -> bool:
    by_key: dict[tuple[str, str], dict] = {}
    for f in findings:
        key = (f["object_ref"], f["check"])
        if key in by_key:
            print(f"warning: duplicate finding for {key}; using the last one")
        by_key[key] = f

    all_ok = True
    print(f"{'Check':<6} {'Planted caught':>15} {'Clean false alarms':>19} {'NOT_CHECKED correct':>20} "
          f"{'No finding':>11}  Release")
    for check in sorted(ran):
        stats = {"planted": [0, 0], "clean": [0, 0], "not_checked": [0, 0]}
        missing, problems = 0, []
        for lab in (l for l in labels if l["check"] == check):
            k = kind(lab)
            stats[k][1] += 1
            f = by_key.get((lab["object_ref"], check))
            got = f["verdict"] if f else None
            if f is None:
                missing += 1
            if k == "planted":
                ok = got == lab["expected_verdict"]
                stats[k][0] += ok
            elif k == "clean":
                ok = got is None or got in ("VERIFIED", lab["expected_verdict"])
                stats[k][0] += not ok
            else:
                ok = got == "NOT_CHECKED"
                stats[k][0] += ok
            if not ok:
                problems.append(f"  {lab['label_id']} {lab['object_ref']}: expected {lab['expected_verdict']}, got {got}")

        p, c, n = stats["planted"], stats["clean"], stats["not_checked"]
        fa_rate = c[0] / c[1] if c[1] else 0.0
        passed = p[0] == p[1] and n[0] == n[1] and fa_rate < MAX_FALSE_ALARM
        all_ok &= passed
        n_txt = f"{n[0]}/{n[1]}" if n[1] else "-"
        print(f"{check:<6} {f'{p[0]}/{p[1]}':>15} {f'{c[0]}/{c[1]}':>19} {n_txt:>20} {missing:>11}  "
              f"{'PASS' if passed else 'FAIL'}")
        for line in problems:
            print(line)

    not_built = sorted({l["check"] for l in labels} - set(ran))
    if not_built:
        print(f"\nNot built yet (not scored): {', '.join(not_built)}")
    return all_ok


def main() -> int:
    sys.addaudithook(_labels_guard)
    findings, ran, corpus = run_checks()
    write_jsonl(OUT, findings)
    print(f"Ran {', '.join(ran) or 'no checks'}: {len(findings)} findings -> {OUT.relative_to(ROOT)}")
    for check, rows in corpus.items():
        path = OUT.parent / CORPORA[check][0]
        write_jsonl(path, rows)
        print(f"Ran {check} corpus: {len(rows)} findings -> {path.relative_to(ROOT)}")
    print()
    ok = score(findings, load_labels(), ran)
    if corpus:
        print()
    for check, rows in corpus.items():
        ok &= score_corpus(check, rows)
    print("\nRelease rule: 100% planted caught, 100% NOT_CHECKED correct, false alarms < 10%.")
    print("Overall:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
