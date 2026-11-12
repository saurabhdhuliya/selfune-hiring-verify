# How ERD is used, and how it is not

Inferring the emotions of job candidates is prohibited under the EU AI Act (GT-0008). Selfune's hard rule 1 says the same. So ERD is **never** used to label, score or describe a candidate.

## Used for
1. **The C9 detector corpus** (`data/c9_corpus/`). ERD label fields (Primary Emotion, Intensity, Readiness Level, Pattern Category) are turned into texts that read like hiring-tool output. These are exactly the outputs the loop must block. They come with 248 hard negatives that use the same emotion words in allowed contexts: describing the task, the candidate's account of someone else, or behaviour only.
2. **Three planted C9 cases** in the main test set (AT09 to AT11).
3. **ERD's discipline, applied to the process.** It splits behaviour confidence from explanation confidence, lists alternative explanations, and records what not to ask. All three are now fields in the decision chain.
4. **Guarding role memory.** Definitions built on ERD-style constructs are rejected.

## Not used for
- Inferring any person's emotion, readiness or personality.
- ERD's raw narratives (Raw Input). They are not copied into the repo.

## Known limit
The corpus is built from templates. A simple cue list catches 248 of 248 positives with no false alarms, which shows the corpus is too easy, not that the detector is good. Before release, add paraphrased and adversarial tool outputs, for example from real vendor documentation.
