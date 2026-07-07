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


class PhotoClassification(BaseModel):
    photo_path: str
    photo_class: PhotoClass


class Flaw(BaseModel):
    description: str
    confidence: Optional[Confidence] = None


class Identification(BaseModel):
    """Step 2 output. Every factual field is a Field so confidence/origin/
    conflict travel with it. Style descriptors and features are plain lists
    since they aren't single-value facts.
    """

    brand: Field[str] = Field()
    item_type: Field[str] = Field()
    gender_department: Field[str] = Field()
    size: Field[str] = Field()
    color: Field[str] = Field()
    material: Field[str] = Field()
    pattern: Field[str] = Field()
    era_estimate: Field[str] = Field()
    style_descriptors: list[str] = []
    notable_features: list[str] = []
    flaws: list[Flaw] = []


class MeasurementReading(BaseModel):
    name: str  # e.g. pit_to_pit, length, inseam, waist_flat, sleeve
    value: float
    unit: str
    confidence: Confidence


class WeightReading(BaseModel):
    value: float
    unit: str
    confidence: Confidence


class CategorySuggestion(BaseModel):
    category_id: str
    category_name: str


class AspectResult(BaseModel):
    name: str
    field: Field[str]
    required: bool
    aspect_mode: Optional[str] = None  # SELECTION_ONLY | FREE_TEXT, from the Taxonomy response
    checked: bool = False  # her transcription checkbox state (M2), defaults unchecked


class CategoryAndAspects(BaseModel):
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    category_alternates: list[CategorySuggestion] = []
    aspects: list[AspectResult] = []


class TitleAndDescription(BaseModel):
    title: str
    description: str
    depop_hashtags: list[str] = []


class PriceComp(BaseModel):
    title: str
    url: str
    price: Optional[float] = None


class PriceGuidance(BaseModel):
    low: Optional[float] = None
    high: Optional[float] = None
    reasoning: str = ""
    comps: list[PriceComp] = []
    terapeak_url: Optional[str] = None


class PipelineOutput(BaseModel):
    """The single source of truth for one pipeline run — must be
    serializable to the Phase 2 Listing API draft schema without
    restructuring (PLAN_v2.md Phase 2 section).
    """

    item_id: str
    seller_context: Optional[str] = None
    photo_classifications: list[PhotoClassification] = []
    identification: Optional[Identification] = None
    measurements: list[MeasurementReading] = []
    package_weight: Optional[WeightReading] = None
    category_and_aspects: Optional[CategoryAndAspects] = None
    title_and_description: Optional[TitleAndDescription] = None
    price_guidance: Optional[PriceGuidance] = None
