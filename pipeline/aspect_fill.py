"""Aspect-fill constraint logic (Step 4), implementing the PLAN_v2.md addendum:

- SELECTION_ONLY: candidate value must case-insensitively match one of the
  Taxonomy API's aspectValues, or the field stays blank.
- FREE_TEXT: candidate value is only kept at medium+ confidence — a
  low-confidence or inferred-only read leaves the field blank, exactly like
  an unreadable SELECTION_ONLY field. When the aspect has a suggested-value
  list, a confident read snaps to the closest suggested value rather than
  emitting a novel string.

This module is pure value logic — no API calls — so it's fully unit-testable
against fixture Taxonomy aspect definitions.
"""
from __future__ import annotations

from pipeline.models import Confidence, Field, Origin

SELECTION_ONLY = "SELECTION_ONLY"
FREE_TEXT = "FREE_TEXT"


def _normalize(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def _allowed_values(aspect: dict) -> list[str]:
    return [v["localizedValue"] for v in aspect.get("aspectValues") or []]


def _find_match(value: str, allowed: list[str]) -> str | None:
    normalized = _normalize(value)
    for candidate in allowed:
        if _normalize(candidate) == normalized:
            return candidate
    return None


def fill_aspect(aspect: dict, candidate: Field) -> Field:
    """Apply the aspectMode-specific fill rule to a candidate Field.

    `aspect` is one entry from the Taxonomy getItemAspectsForCategory
    response (has `aspectConstraint.aspectMode` and `aspectValues`).
    `candidate` is the model's proposed value for this aspect, already
    carrying a confidence and origin from earlier pipeline steps.
    """
    if candidate.value is None:
        return Field(value=None, confidence=None, origin=None)

    mode = aspect.get("aspectConstraint", {}).get("aspectMode")
    allowed = _allowed_values(aspect)

    if mode == SELECTION_ONLY:
        matched = _find_match(candidate.value, allowed)
        if matched is None:
            return Field(value=None, confidence=None, origin=None)
        return Field(value=matched, confidence=candidate.confidence, origin=candidate.origin)

    # FREE_TEXT (and any other/unknown mode defaults to the same discipline):
    # only keep medium+ confidence reads — never a low-confidence guess.
    if candidate.confidence == Confidence.LOW or candidate.confidence is None:
        return Field(value=None, confidence=None, origin=None)

    if allowed:
        matched = _find_match(candidate.value, allowed)
        if matched is not None:
            return Field(value=matched, confidence=candidate.confidence, origin=candidate.origin)

    return Field(value=candidate.value, confidence=candidate.confidence, origin=candidate.origin)
