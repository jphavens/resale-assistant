"""Step 2 — Identify (PLAN_v2.md).

Vision call over all photos + seller_context. The model reports what it can
read from the PHOTOS and what the SELLER_CONTEXT states as two separate
readings per field; pipeline.seller_context.resolve_field then combines them
deterministically so the no-guess/conflict/no-confidence-upgrade rules are
enforced in code, not left to model behavior alone.
"""
from __future__ import annotations

from pathlib import Path

from pipeline.anthropic_client import AnthropicStructuredClient, CallResult
from pipeline.images import load_image_as_api_content_block
from pipeline.models import Confidence, Flaw, Identification, Origin
from pipeline.seller_context import SELLER_CONTEXT_PROMPT_NOTE, resolve_field

FIELDS = [
    "brand",
    "item_type",
    "gender_department",
    "size",
    "color",
    "material",
    "pattern",
    "era_estimate",
]

SYSTEM_PROMPT = (
    "You are identifying a clothing/shoes/accessories item for an eBay reseller from "
    "photos and an optional seller note.\n\n"
    f"{SELLER_CONTEXT_PROMPT_NOTE}\n\n"
    "For each of these fields: " + ", ".join(FIELDS) + " — report separately what the "
    "PHOTOS show (vision_value/vision_confidence) and what SELLER_CONTEXT states "
    "(seller_value/seller_confidence), each independently. Leave a value null if that "
    "source doesn't address the field — do not guess. This is absolute for brand, size, "
    "and material: a wrong value there causes returns, so leave null rather than infer. "
    "confidence is one of high/medium/low; mirror the seller's own hedging in "
    "seller_confidence — never report high confidence for a hedged claim like 'I think "
    "it's cashmere'.\n\n"
    "Also report style_descriptors (real resale vocabulary — Y2K, gorpcore, grunge, "
    "coquette, western, coastal, etc — only when genuinely supported by the photos), "
    "notable_features (pockets, hardware, wash, etc), and visible flaws with "
    "plain-language descriptions and a confidence each."
)

_FIELD_READING_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": ["string", "null"]},
        "confidence": {"type": ["string", "null"], "enum": ["high", "medium", "low", None]},
    },
    "required": ["value", "confidence"],
}

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "vision_readings": {
            "type": "object",
            "properties": {f: _FIELD_READING_SCHEMA for f in FIELDS},
            "required": FIELDS,
        },
        "seller_readings": {
            "type": "object",
            "properties": {f: _FIELD_READING_SCHEMA for f in FIELDS},
            "required": FIELDS,
        },
        "style_descriptors": {"type": "array", "items": {"type": "string"}},
        "notable_features": {"type": "array", "items": {"type": "string"}},
        "flaws": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "confidence": {"type": ["string", "null"], "enum": ["high", "medium", "low", None]},
                },
                "required": ["description"],
            },
        },
    },
    "required": ["vision_readings", "seller_readings", "style_descriptors", "notable_features", "flaws"],
}


def _confidence_or_none(raw: str | None) -> Confidence | None:
    return Confidence(raw) if raw else None


def identify_item(
    client: AnthropicStructuredClient,
    photo_paths: list[Path],
    seller_context: str | None,
) -> tuple[Identification, CallResult]:
    content = [load_image_as_api_content_block(p) for p in photo_paths]
    content.append(
        {
            "type": "text",
            "text": f"seller_context: {seller_context!r}" if seller_context else "seller_context: (none provided)",
        }
    )

    result = client.call_structured(
        system=SYSTEM_PROMPT,
        content=content,
        tool_name="identify_item",
        tool_schema=TOOL_SCHEMA,
        max_tokens=2048,
    )

    data = result.data
    vision = data["vision_readings"]
    seller = data["seller_readings"]

    field_values = {}
    for name in FIELDS:
        v, s = vision[name], seller[name]
        field_values[name] = resolve_field(
            field_name=name,
            vision_value=v.get("value"),
            vision_confidence=_confidence_or_none(v.get("confidence")),
            seller_value=s.get("value"),
            seller_confidence=_confidence_or_none(s.get("confidence")),
        )

    identification = Identification(
        **field_values,
        style_descriptors=data.get("style_descriptors", []),
        notable_features=data.get("notable_features", []),
        flaws=[
            Flaw(description=f["description"], confidence=_confidence_or_none(f.get("confidence")))
            for f in data.get("flaws", [])
        ],
    )
    return identification, result
