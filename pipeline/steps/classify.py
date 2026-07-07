"""Step 1 — Classify photos (PLAN_v2.md).

One vision call tags each image: {item_shot, brand_tag, care_tag, size_tag,
ruler_measurement, flaw, scale_readout, other}. Cheap, fast, drives the
missing-photo nudges in Step 6/M2.
"""
from __future__ import annotations

from pathlib import Path

from pipeline.anthropic_client import AnthropicStructuredClient, CallResult
from pipeline.images import load_image_as_api_content_block
from pipeline.models import PhotoClass, PhotoClassification

SYSTEM_PROMPT = (
    "You are classifying photos taken by a clothing/shoes/accessories reseller for an "
    "eBay listing. For each image, in order, assign exactly one class: item_shot (the "
    "garment/item itself), brand_tag, care_tag (fabric/care label), size_tag, "
    "ruler_measurement (a tape measure or ruler laid against the item), flaw (a close-up "
    "of damage/staining/wear), scale_readout (a kitchen/postal scale display), or other."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "classifications": {
            "type": "array",
            "description": "One entry per input image, in the same order the images were provided.",
            "items": {
                "type": "object",
                "properties": {
                    "photo_class": {
                        "type": "string",
                        "enum": [c.value for c in PhotoClass],
                    }
                },
                "required": ["photo_class"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["classifications"],
    "additionalProperties": False,
}


def classify_photos(
    client: AnthropicStructuredClient, photo_paths: list[Path]
) -> tuple[list[PhotoClassification], CallResult]:
    content = [load_image_as_api_content_block(p) for p in photo_paths]
    content.append({"type": "text", "text": f"Classify these {len(photo_paths)} photos, in order."})

    result = client.call_structured(
        system=SYSTEM_PROMPT,
        content=content,
        tool_name="classify_photos",
        tool_schema=TOOL_SCHEMA,
        max_tokens=1024,
    )

    classifications = result.data["classifications"]
    photo_classifications = [
        PhotoClassification(photo_path=str(path), photo_class=PhotoClass(c["photo_class"]))
        for path, c in zip(photo_paths, classifications)
    ]
    return photo_classifications, result
