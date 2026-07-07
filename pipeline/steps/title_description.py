"""Step 5 — Title + description (PLAN_v2.md).

The model proposes title components and description text from the
identification/measurement/aspect data; pipeline.title.build_title then
assembles and enforces the <=80 char / no-caps / no-spam rules in code, so
compliance never depends on the model following the instruction perfectly.
"""
from __future__ import annotations

from pipeline.anthropic_client import AnthropicStructuredClient, CallResult
from pipeline.models import CategoryAndAspects, Identification, MeasurementReading, TitleAndDescription
from pipeline.seller_context import SELLER_CONTEXT_PROMPT_NOTE
from pipeline.title import build_title

SYSTEM_PROMPT = (
    "You are writing an eBay listing title and description for a resale item from "
    "already-identified data.\n\n"
    f"{SELLER_CONTEXT_PROMPT_NOTE}\n\n"
    "Title components (each must be SHORT — 1-3 words, title-appropriate, not a "
    "description): brand, item_type, up to 3 key_descriptors (style/notable features — "
    "real resale vocabulary, only if genuinely supported), size, color. color especially "
    "must be a short color name or two (e.g. 'Black/Olive' or 'Multicolor'), never a full "
    "sentence describing the pattern — save pattern/print detail for the description. Do "
    "not include marketing language, ALL CAPS, or phrases like 'L@@K' anywhere.\n\n"
    "Description: fixed sections in this order — what it is; condition & flaws (plain "
    "language, from the flaw data and seller_context); a measurements table using the "
    "REAL numbers provided (never 'see photos'); fabric content; a one-line shipping "
    "note. Clean text, no HTML.\n\n"
    "Optionally include up to 5 relevant Depop hashtags (no '#' needed, just words) — "
    "these are never merged into the eBay description, only shown separately."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "brand": {"type": ["string", "null"]},
        "item_type": {"type": ["string", "null"]},
        "key_descriptors": {"type": "array", "items": {"type": "string"}},
        "size": {"type": ["string", "null"]},
        "color": {"type": ["string", "null"]},
        "description": {"type": "string"},
        "depop_hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["brand", "item_type", "key_descriptors", "size", "color", "description", "depop_hashtags"],
    "additionalProperties": False,
}


def _build_content_text(
    identification: Identification,
    measurements: list[MeasurementReading],
    category_and_aspects: CategoryAndAspects | None,
    seller_context: str | None,
) -> str:
    lines = [
        f"brand: {identification.brand.value}",
        f"item_type: {identification.item_type.value}",
        f"size: {identification.size.value}",
        f"color: {identification.color.value}",
        f"material: {identification.material.value}",
        f"pattern: {identification.pattern.value}",
        f"style_descriptors: {', '.join(identification.style_descriptors)}",
        f"notable_features: {', '.join(identification.notable_features)}",
        "flaws: " + ("; ".join(f.description for f in identification.flaws) or "none noted"),
        "measurements: " + (", ".join(f"{m.name}={m.value}{m.unit}" for m in measurements) or "none provided"),
    ]
    if category_and_aspects:
        lines.append(f"category: {category_and_aspects.category_name}")
    if seller_context:
        lines.append(f"seller_context: {seller_context}")
    return "\n".join(lines)


def generate_title_and_description(
    client: AnthropicStructuredClient,
    identification: Identification,
    measurements: list[MeasurementReading],
    category_and_aspects: CategoryAndAspects | None,
    seller_context: str | None,
) -> tuple[TitleAndDescription, CallResult]:
    content = [{"type": "text", "text": _build_content_text(identification, measurements, category_and_aspects, seller_context)}]

    result = client.call_structured(
        system=SYSTEM_PROMPT,
        content=content,
        tool_name="write_listing_copy",
        tool_schema=TOOL_SCHEMA,
        max_tokens=1536,
    )

    data = result.data
    title = build_title(
        brand=data.get("brand"),
        item_type=data.get("item_type"),
        size=data.get("size"),
        color=data.get("color"),
        descriptors=data.get("key_descriptors", []),
    )

    return (
        TitleAndDescription(
            title=title,
            description=data["description"],
            depop_hashtags=data.get("depop_hashtags", [])[:5],
        ),
        result,
    )
