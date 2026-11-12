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

_guard_on = False


def _labels_guard(event: str, args: tuple) -> None:
    if _guard_on and event == "open" and args and isinstance(args[0], (str, bytes, Path)):
        try:
            p = Path(args[0] if not isinstance(args[0], bytes) else args[0].decode()).resolve()
        except (OSError, ValueError):
            return
        if p == LABELS_DIR or LABELS_DIR in p.parents:
            raise PermissionError(f"A check tried to read {p}. Checks must never read labels/.")


def run_checks() -> tuple[list[dict], list[str]]:
    global _guard_on
    findings, ran = [], []
    for mod_info in sorted(pkgutil.iter_modules(checks_pkg.__path__), key=lambda m: m.name):
        mod = importlib.import_module(f"{checks_pkg.__name__}.{mod_info.name}")
        if not (hasattr(mod, "CHECK_ID") and hasattr(mod, "run")):
            continue
        _guard_on = True
        try:
            out = mod.run(ROOT)
        finally:
            _guard_on = False
        findings.extend(out)
        ran.append(mod.CHECK_ID)
    return findings, ran


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
    findings, ran = run_checks()
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for fd in findings:
            f.write(json.dumps(fd, ensure_ascii=False) + "\n")
    print(f"Ran {', '.join(ran) or 'no checks'}: {len(findings)} findings -> {OUT.relative_to(ROOT)}\n")
    ok = score(findings, load_labels(), ran)
    print("\nRelease rule: 100% planted caught, 100% NOT_CHECKED correct, false alarms < 10%.")
    print("Overall:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
