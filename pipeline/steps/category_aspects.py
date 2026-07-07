"""Step 4 — Category + aspects (PLAN_v2.md, with the FREE_TEXT addendum).

Calls getCategorySuggestions with the identified item, takes the top
suggestion (alternates surfaced for the M2 dropdown), calls
getItemAspectsForCategory for that category, then one text-only model call
fills each aspect FROM THE IDENTIFICATION DATA (no photos re-sent). The
aspectMode-specific confidence discipline (pipeline.aspect_fill) is applied
in code afterward, not left to the model.
"""
from __future__ import annotations

from ebay_client.taxonomy import TaxonomyClient
from pipeline.anthropic_client import AnthropicStructuredClient, CallResult
from pipeline.aspect_fill import fill_aspect
from pipeline.models import (
    AspectResult,
    CategoryAndAspects,
    CategorySuggestion,
    Confidence,
    Field,
    Identification,
    Origin,
)
from pipeline.seller_context import SELLER_CONTEXT_PROMPT_NOTE

# Aspects with more allowed values than this are too large to usefully list in
# the prompt (e.g. Brand has 4000+ suggested values) — the model free-texts
# those, and aspect_fill still checks the full list programmatically.
LARGE_LIST_THRESHOLD = 300

_KNOWN_FIELD_ORIGINS = {
    "brand": "brand",
    "size": "size",
    "color": "color",
    "material": "material",
}


def _build_identification_summary(identification: Identification, seller_context: str | None) -> str:
    lines = []
    for name in ("brand", "item_type", "gender_department", "size", "color", "material", "pattern", "era_estimate"):
        field: Field = getattr(identification, name)
        if field.value is not None:
            lines.append(f"{name}: {field.value} (confidence={field.confidence}, origin={field.origin})")
    if identification.style_descriptors:
        lines.append(f"style_descriptors: {', '.join(identification.style_descriptors)}")
    if identification.notable_features:
        lines.append(f"notable_features: {', '.join(identification.notable_features)}")
    if identification.flaws:
        lines.append("flaws: " + "; ".join(f.description for f in identification.flaws))
    if seller_context:
        lines.append(f"seller_context: {seller_context}")
    return "\n".join(lines)


def _build_aspect_prompt(aspects: list[dict]) -> str:
    lines = []
    for i, aspect in enumerate(aspects):
        constraint = aspect["aspectConstraint"]
        name = aspect["localizedAspectName"]
        mode = constraint.get("aspectMode")
        required = constraint.get("aspectRequired")
        allowed = [v["localizedValue"] for v in aspect.get("aspectValues") or []]
        line = f"{i}. {name} (required={required}, mode={mode})"
        if allowed and len(allowed) <= LARGE_LIST_THRESHOLD:
            label = "allowed values" if mode == "SELECTION_ONLY" else "suggested values (not exhaustive)"
            line += f" — {label}: {', '.join(allowed)}"
        lines.append(line)
    return "\n".join(lines)


def _build_system_prompt(aspects: list[dict]) -> str:
    return (
        "You are filling eBay item-specific fields (aspects) for a resale listing from "
        "already-identified item data — you are not looking at photos in this step.\n\n"
        f"{SELLER_CONTEXT_PROMPT_NOTE}\n\n"
        "For each numbered aspect below, in order, provide a value and confidence "
        "(high/medium/low) based ONLY on what the identification data actually supports. "
        "If the data doesn't clearly support a value for an aspect, return null — do not "
        "guess just because the field exists. This applies especially to aspects with a "
        "closed list of allowed values: only answer with one of the allowed values, or "
        "null.\n\n"
        f"Aspects:\n{_build_aspect_prompt(aspects)}"
    )


_FILL_SCHEMA = {
    "type": "object",
    "properties": {
        "fills": {
            "type": "array",
            "description": "One entry per numbered aspect above, in the same order.",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": ["string", "null"]},
                    # Ignored downstream when value is null.
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["value", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["fills"],
    "additionalProperties": False,
}


def get_category_and_aspects(
    client: AnthropicStructuredClient,
    taxonomy_client: TaxonomyClient,
    category_tree_id: str,
    identification: Identification,
    seller_context: str | None,
) -> tuple[CategoryAndAspects, CallResult]:
    query_parts = [
        identification.brand.value,
        identification.item_type.value,
        *identification.style_descriptors,
    ]
    query = " ".join(p for p in query_parts if p)

    suggestions = taxonomy_client.get_category_suggestions(category_tree_id, query)
    category_suggestions = suggestions.get("categorySuggestions", [])
    if not category_suggestions:
        return CategoryAndAspects(), None

    top = category_suggestions[0]["category"]
    alternates = [
        CategorySuggestion(category_id=s["category"]["categoryId"], category_name=s["category"]["categoryName"])
        for s in category_suggestions[1:5]
    ]

    aspects_meta = taxonomy_client.get_item_aspects_for_category(category_tree_id, top["categoryId"])["aspects"]

    system_prompt = _build_system_prompt(aspects_meta)
    content = [{"type": "text", "text": _build_identification_summary(identification, seller_context)}]

    result = client.call_structured(
        system=system_prompt,
        content=content,
        tool_name="fill_aspects",
        tool_schema=_FILL_SCHEMA,
        max_tokens=2048,
    )

    aspect_results = []
    for aspect, fill in zip(aspects_meta, result.data["fills"]):
        name = aspect["localizedAspectName"]
        confidence = Confidence(fill["confidence"]) if fill.get("confidence") else None

        origin = Origin.VISION
        known_field = _KNOWN_FIELD_ORIGINS.get(name.lower())
        if known_field:
            source_field: Field = getattr(identification, known_field)
            if source_field.origin is not None:
                origin = source_field.origin

        candidate = Field(value=fill.get("value"), confidence=confidence, origin=origin)
        final = fill_aspect(aspect, candidate)
        aspect_results.append(
            AspectResult(
                name=name,
                field=final,
                required=aspect["aspectConstraint"].get("aspectRequired", False),
                aspect_mode=aspect["aspectConstraint"].get("aspectMode"),
            )
        )

    # Required aspects first, then recommended/optional — matches eBay's form order
    # (PLAN_v2.md hard constraint #3).
    aspect_results.sort(key=lambda a: not a.required)

    return (
        CategoryAndAspects(
            category_id=top["categoryId"],
            category_name=top["categoryName"],
            category_alternates=alternates,
            aspects=aspect_results,
        ),
        result,
    )
