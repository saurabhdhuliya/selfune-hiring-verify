"""Vocabulary for C9 (emotion / personality inference) and for guarding role memory.

Emotion and readiness labels come from the ERD label set (Primary Emotion,
Readiness Level, Pattern Category). ERD is used here only so the loop can
DETECT and BLOCK this kind of output. It is never used to label a person.
"""
import re

EMOTION_LABELS = [
    "anxiety", "anxious", "fear", "fearful", "frustration", "frustrated", "anger", "angry",
    "sadness", "sad", "guilt", "guilty", "shame", "confusion", "confused", "exhaustion",
    "exhausted", "stress", "stressed", "nervous", "nervousness", "enthusiasm", "enthusiastic",
    "excitement", "joy", "happiness", "calm", "confidence level", "emotional state", "mood",
    "sentiment", "affect", "emotion",
]

PERSONALITY_LABELS = [
    "personality", "big five", "ocean score", "introvert", "extrovert", "extraversion",
    "neuroticism", "agreeableness", "conscientiousness score", "openness score",
    "attachment style", "anxious attachment", "avoidant attachment", "emotional readiness",
    "readiness level", "temperament", "character type", "disc profile", "mbti",
    "emotional intelligence score", "eq score", "culture fit score", "grit score",
]

# Phrases that signal the SYSTEM is inferring (not quoting, not describing a task).
INFERENCE_CUES = [
    r"\bdetected\b", r"\binferred\b", r"\bdominant emotion\b", r"\bprimary emotion\b",
    r"\bemotion(al)? (score|state|profile|analysis)\b", r"\bintensity\s*\d+\s*/\s*10\b",
    r"\breadiness:?\s*(green|yellow|red|grey)\b", r"\bfacial (expression|analysis)\b",
    r"\bvoice (tone|stress|analysis)\b", r"\bmicro-?expressions?\b", r"\bsentiment score\b",
    r"\bpersonality (profile|score|type|trait)s?\b", r"\b(appears|seemed|seems) (anxious|nervous|stressed|unenthusiastic|angry|sad)\b",
    r"\bpattern:? [a-z -]*attachment\b",
]

_INF = [re.compile(p, re.I) for p in INFERENCE_CUES]


def mentions_banned_construct(text: str) -> bool:
    """True if text names an emotion or personality construct at all (broad)."""
    t = text.lower()
    return any(re.search(rf"\b{re.escape(w)}\b", t) for w in EMOTION_LABELS + PERSONALITY_LABELS)


def has_inference_cue(text: str) -> bool:
    return any(p.search(text) for p in _INF)
