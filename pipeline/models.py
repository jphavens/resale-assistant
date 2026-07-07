"""Shared data structures for the pipeline.

Every identified field carries a confidence, an origin, and — where the
vision read and the seller's note disagree — a conflict with both candidate
values. Unreadable/unstated fields are `None`, never guessed (PLAN_v2.md
Step 2).
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Origin(str, Enum):
    VISION = "vision"
    SELLER_CONTEXT = "seller_context"
    MANUAL = "manual"


class PhotoClass(str, Enum):
    ITEM_SHOT = "item_shot"
    BRAND_TAG = "brand_tag"
    CARE_TAG = "care_tag"
    SIZE_TAG = "size_tag"
    RULER_MEASUREMENT = "ruler_measurement"
    FLAW = "flaw"
    SCALE_READOUT = "scale_readout"
    OTHER = "other"


class Conflict(BaseModel):
    vision_value: Any = None
    seller_context_value: Any = None


class Field(BaseModel, Generic[T]):
    """A single identified attribute with provenance.

    `value` is None when unreadable/unstated — the no-guess rule is absolute
    for size, brand, and fabric content.
    """

    value: Optional[T] = None
    confidence: Optional[Confidence] = None
    origin: Optional[Origin] = None
    conflict: Optional[Conflict] = None
