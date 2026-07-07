"""Step 2 — Identify (PLAN_v2.md).

Vision call over all photos + seller_context. The model reports what it can
read from the PHOTOS and what the SELLER_CONTEXT states as two separate
readings per field; pipeline.seller_context.resolve_field then combines them
deterministically so the no-guess/conflict/no-confidence-upgrade rules are
enforced in code, not left to model behavior alone.

The readings are a single array (one entry per FIELDS, in that fixed order)
rather than 16 separately-named object properties — a schema with many
distinct named sub-schemas blows up the strict-mode compiled grammar
("compiled grammar is too large"); a single reused array item schema does not.
"""
from __future__ import annotations

from pathlib import Path

from pipeline.anthropic_client import AnthropicStructuredClient, CallResult
from pipeline.images import load_image_as_api_content_block
from pipeline.models import Confidence, Flaw, Identification
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
    "The `readings` array must have exactly one entry per field, IN THIS ORDER: "
    + ", ".join(FIELDS) + ". For each field, report separately what the PHOTOS show "
    "(vision_value/vision_confidence) and what SELLER_CONTEXT states (seller_value/"
    "seller_confidence), each independently. Leave a value null if that source doesn't "
    "address the field — do not guess. This is absolute for brand, size, and material: a "
    "wrong value there causes returns, so leave null rather than infer. confidence is "
    "always one of high/medium/low even when value is null (it's ignored in that case); "
    "mirror the seller's own hedging in seller_confidence — never report high confidence "
    "for a hedged claim like 'I think it's cashmere'.\n\n"
    "Also report style_descriptors (real resale vocabulary — Y2K, gorpcore, grunge, "
    "coquette, western, coastal, etc — only when genuinely supported by the photos), "
    "notable_features (pockets, hardware, wash, etc), and visible flaws with "
    "plain-language descriptions and a confidence each."
)

_CONFIDENCE_ENUM = {"type": "string", "enum": ["high", "medium", "low"]}

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "readings": {
            "type": "array",
            "description": f"Exactly {len(FIELDS)} entries, one per field in FIELDS order.",
            "items": {
                "type": "object",
                "properties": {
                    "vision_value": {"type": ["string", "null"]},
                    "vision_confidence": _CONFIDENCE_ENUM,
                    "seller_value": {"type": ["string", "null"]},
                    "seller_confidence": _CONFIDENCE_ENUM,
                },
                "required": ["vision_value", "vision_confidence", "seller_value", "seller_confidence"],
                "additionalProperties": False,
            },
        },
        "style_descriptors": {"type": "array", "items": {"type": "string"}},
        "notable_features": {"type": "array", "items": {"type": "string"}},
        "flaws": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "confidence": _CONFIDENCE_ENUM,
                },
                "required": ["description", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["readings", "style_descriptors", "notable_features", "flaws"],
    "additionalProperties": False,
}


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
    readings = data["readings"]

    field_values = {}
    for name, reading in zip(FIELDS, readings):
        field_values[name] = resolve_field(
            field_name=name,
            vision_value=reading.get("vision_value"),
            vision_confidence=Confidence(reading["vision_confidence"]),
            seller_value=reading.get("seller_value"),
            seller_confidence=Confidence(reading["seller_confidence"]),
        )

    identification = Identification(
        **field_values,
        style_descriptors=data.get("style_descriptors", []),
        notable_features=data.get("notable_features", []),
        flaws=[
            Flaw(description=f["description"], confidence=Confidence(f["confidence"]))
            for f in data.get("flaws", [])
        ],
    )
    return identification, result
