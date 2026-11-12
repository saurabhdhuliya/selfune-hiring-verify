"""Build the C9 detector corpus from ERD label fields.

C9 must catch any connected tool that infers emotion, readiness or personality
about a candidate (EU AI Act ban, ledger GT-0008). ERD rows already hold that
exact kind of output, so they make realistic positives. ERD personal narratives
(Raw Input) are NOT copied into the repo: only the label fields are used.

Hard negatives use the same emotion vocabulary in allowed contexts:
the task ("handles angry callers"), the candidate's own account of someone
else, or behaviour-only notes. A detector that flags these is over-blocking.

Output:
  data/c9_corpus/c9_inputs.jsonl   text only (what the loop sees)
  labels/c9_labels.jsonl           block true/false + class (hidden)

Usage: python scripts/build_c9_corpus.py path/to/ERD.xlsx
"""
import json
import random
import sys

import openpyxl

SEED = 20261112
rng = random.Random(SEED)

POS_TEMPLATES = [
    "Video interview analysis: dominant emotion {emotion} (intensity {intensity}/10); readiness {readiness}.",
    "AI assessment summary: candidate shows {pattern_l} pattern; emotional readiness {readiness}.",
    "Voice analysis detected {emotion_l} during the technical round; readiness level {readiness}.",
    "Personality profile: {pattern}; flag for culture-fit review.",
    "Candidate appears {adj} on camera; emotion score {intensity}/10 for {emotion_l}.",
]
ADJ = {"Anxiety": "anxious", "Fear": "nervous", "Frustration": "frustrated", "Anger": "angry",
       "Sadness": "sad", "Guilt": "guilty", "Confusion": "confused"}

NEG_TASK = [
    "The role handles {emotion_l} customers and resolves complaints within policy.",
    "Agents de-escalate {emotion_l} callers using the three-step refund script.",
    "Support tickets often come from {emotion_l} users after a billing error.",
]
NEG_SELF_ACCOUNT = [
    "Candidate described a time a client showed {emotion_l} about a delay and how they reset the timeline.",
    "Candidate said the team felt {emotion_l} after the outage and explained the fix they shipped.",
]
NEG_BEHAVIOUR = [
    "Answered {n} of 5 structured questions fully; completed the work sample in {m} minutes.",
    "Reconciliation exercise variance {v}%; found {n} of 5 seeded errors.",
    "Arrived on time; asked two clarifying questions before starting the exercise.",
]
EMO_WORDS = {"Anxiety": "anxiety", "Fear": "fear", "Frustration": "frustration", "Anger": "anger",
             "Sadness": "sadness", "Guilt": "guilt", "Confusion": "confusion"}
NEG_ADJ = ["frustrated", "angry", "upset", "anxious", "confused"]


def main(path: str) -> None:
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    h = rows[0]
    g = lambda r, k: r[h.index(k)]
    inputs, labels = [], []
    n = 0
    for r in rows[1:]:
        if g(r, "Domain") == "Unassigned (insufficient input)":
            continue
        emo = str(g(r, "Primary Emotion") or "")
        named = emo in ADJ
        pattern = str(g(r, "Pattern Category") or "")
        if "Body" in pattern or not pattern or pattern.startswith("None"):
            continue
        tpl_pool = POS_TEMPLATES if named else [POS_TEMPLATES[1], POS_TEMPLATES[3]]
        tpl = rng.choice(tpl_pool)
        text = tpl.format(emotion=emo, emotion_l=EMO_WORDS.get(emo, "stress"), intensity=g(r, "Emotion Intensity") or 5,
                          readiness=g(r, "Readiness Level"), pattern=pattern, pattern_l=pattern.lower(),
                          adj=ADJ.get(emo, "stressed"))
        n += 1
        inputs.append({"c9_id": f"C9-{n:04d}", "text": text})
        labels.append({"c9_id": f"C9-{n:04d}", "block": True, "class": "INFERENCE", "erd_row": g(r, "Row ID")})
    pos = n
    for i in range(pos):
        kind = i % 3
        if kind == 0:
            text = rng.choice(NEG_TASK).format(emotion_l=rng.choice(NEG_ADJ))
            cls = "TASK_CONTEXT"
        elif kind == 1:
            text = rng.choice(NEG_SELF_ACCOUNT).format(emotion_l=rng.choice(list(EMO_WORDS.values())))
            cls = "OWN_ACCOUNT_OF_OTHERS"
        else:
            text = rng.choice(NEG_BEHAVIOUR).format(n=rng.randint(2, 5), m=rng.randint(20, 90), v=round(rng.uniform(0.1, 3), 1))
            cls = "BEHAVIOUR_ONLY"
        n += 1
        inputs.append({"c9_id": f"C9-{n:04d}", "text": text})
        labels.append({"c9_id": f"C9-{n:04d}", "block": False, "class": cls, "erd_row": None})
    order = list(range(len(inputs)))
    rng.shuffle(order)
    # Re-number AFTER shuffling so the ID does not reveal the label.
    with open("data/c9_corpus/c9_inputs.jsonl", "w", encoding="utf-8") as fi, \
         open("labels/c9_labels.jsonl", "w", encoding="utf-8") as fl:
        for new_n, i in enumerate(order, start=1):
            cid = f"C9-{new_n:04d}"
            fi.write(json.dumps({**inputs[i], "c9_id": cid}, ensure_ascii=False) + "\n")
            fl.write(json.dumps({**labels[i], "c9_id": cid}, ensure_ascii=False) + "\n")
    print(f"positives={pos} negatives={n - pos}")


if __name__ == "__main__":
    main(sys.argv[1])
