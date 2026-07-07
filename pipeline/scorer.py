"""Four-bucket scorer for the M0 validation harness (PLAN_v2.md M0).

Compares a flat "expected" field map (from groundtruth) against a flat
"actual" field map (from a pipeline run) and buckets every field into
exactly one of:

- match: both present and equal (case-insensitive, whitespace-normalized).
- contradiction: both present and different.
- model_null_expected_value: expected has a value, actual is missing/None.
- unverified_extra: actual has a value for a field ABSENT from expected.
  This is NOT a miss — her real listings have blank aspects, and the model
  exceeding ground truth is expected. Excluded from accuracy scoring.

Only match / contradiction / model_null_expected_value count toward
accuracy; unverified_extra is reported separately and never penalized.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ScoreBucket(str, Enum):
    MATCH = "match"
    CONTRADICTION = "contradiction"
    MODEL_NULL_EXPECTED_VALUE = "model_null_expected_value"
    UNVERIFIED_EXTRA = "unverified_extra"


@dataclass
class FieldScore:
    field: str
    bucket: ScoreBucket
    expected_value: Optional[str]
    actual_value: Optional[str]


def _normalize(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return " ".join(str(value).split()).strip().lower()


def score_fields(expected: dict[str, str], actual: dict[str, Optional[str]]) -> list[FieldScore]:
    """Bucket every field in the union of `expected` and `actual` keys."""
    results: list[FieldScore] = []

    for field, expected_value in expected.items():
        actual_value = actual.get(field)
        if actual_value is None:
            results.append(FieldScore(field, ScoreBucket.MODEL_NULL_EXPECTED_VALUE, expected_value, None))
        elif _normalize(actual_value) == _normalize(expected_value):
            results.append(FieldScore(field, ScoreBucket.MATCH, expected_value, actual_value))
        else:
            results.append(FieldScore(field, ScoreBucket.CONTRADICTION, expected_value, actual_value))

    for field, actual_value in actual.items():
        if field not in expected and actual_value is not None:
            results.append(FieldScore(field, ScoreBucket.UNVERIFIED_EXTRA, None, actual_value))

    return results


def accuracy(results: list[FieldScore], fields: Optional[set[str]] = None) -> Optional[float]:
    """Fraction of `match` among match+contradiction+model_null for the given
    fields (or all scored fields if `fields` is None). unverified_extra is
    always excluded. Returns None if there are no scorable fields (avoids a
    misleading 0/0 -> 0.0).
    """
    relevant = [r for r in results if r.bucket != ScoreBucket.UNVERIFIED_EXTRA]
    if fields is not None:
        relevant = [r for r in relevant if r.field in fields]
    if not relevant:
        return None
    matches = sum(1 for r in relevant if r.bucket == ScoreBucket.MATCH)
    return matches / len(relevant)


def summarize(results: list[FieldScore]) -> dict[str, int]:
    counts = {bucket.value: 0 for bucket in ScoreBucket}
    for r in results:
        counts[r.bucket.value] += 1
    return counts
