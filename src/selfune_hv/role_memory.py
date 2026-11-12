"""Role memory: employer trait definitions, stored once per role and reused.

The loop READS role memory. Only a human WRITES and locks it (hard rule 3).
A requirement that maps to an ACTIVE definition can be verified without asking
anyone; a missing or stale definition produces one question, once per role.
No LLM in this module.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from .emotion_terms import mentions_banned_construct


@dataclass
class Lookup:
    status: str                 # FOUND | STALE | MISSING | RETIRED
    trait: Optional[dict]
    role_need: Optional[str]
    matched_term: Optional[str]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


class RoleMemory:
    def __init__(self, data: dict, today: date | None = None):
        self.data = data
        self.today = today or date.today()
        self._roles = {r["role_id"]: r for r in data["roles"]}

    @classmethod
    def load(cls, path: str, today: date | None = None) -> "RoleMemory":
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f), today)

    def role_need(self, role_id: str) -> Optional[str]:
        r = self._roles.get(role_id)
        return r["role_need"] if r else None

    def lookup(self, role_id: str, requirement_text: str) -> Lookup:
        """Match a requirement line to a stored trait by its terms (longest match wins)."""
        role = self._roles.get(role_id)
        if not role:
            return Lookup("MISSING", None, None, None)
        req = f" {_norm(requirement_text)} "
        best, best_term = None, None
        for t in role["traits"]:
            for term in t["terms"]:
                nt = f" {_norm(term)} "
                if nt in req and (best_term is None or len(term) > len(best_term)):
                    best, best_term = t, term
        if not best:
            return Lookup("MISSING", None, role["role_need"], None)
        if best["status"] == "RETIRED":
            return Lookup("RETIRED", best, role["role_need"], best_term)
        if best["status"] == "STALE" or date.fromisoformat(best["review_by"]) < self.today:
            return Lookup("STALE", best, role["role_need"], best_term)
        return Lookup("FOUND", best, role["role_need"], best_term)

    @staticmethod
    def question_for(requirement_text: str, role_title: str) -> str:
        """The one question asked when a definition is missing. Under 25 words."""
        q = f'For {role_title}, what observable result shows "{requirement_text}", and how does it help the role succeed?'
        if len(q.split()) > 24:
            q = f'What observable result shows "{requirement_text}" in this role?'
        return q

    def propose_definition(self, role_id: str, trait: dict) -> dict:
        """Validate a human's answer before it is stored. Returns the trait marked for human lock.

        Rejects definitions built on emotion or personality (hard rule 1),
        and definitions with no observable evidence.
        """
        text = " ".join([trait.get("definition", "")] + trait.get("observable_evidence", []))
        if mentions_banned_construct(text):
            raise ValueError("Definition uses an emotion or personality construct; restate as observable job behaviour.")
        if not trait.get("observable_evidence"):
            raise ValueError("Definition needs at least one observable piece of evidence.")
        if role_id not in self._roles:
            raise KeyError(role_id)
        return {**trait, "status": "ACTIVE", "version": trait.get("version", 1)}
