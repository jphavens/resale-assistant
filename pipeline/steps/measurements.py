"""Step 3 — Measurements (PLAN_v2.md).

For each ruler_measurement photo: read the measurement, infer what's being
measured from garment orientation, return value + unit + confidence. For
scale_readout photos: read weight. Low-confidence reads must be surfaced
prominently in the UI (M2), not silently included — this step only reads
and reports confidence; it never filters a low-confidence reading out.
"""
from __future__ import annotations

from pathlib import Path

from pipeline.anthropic_client import AnthropicStructuredClient, CallResult
from pipeline.images import load_image_as_api_content_block
from pipeline.models import MeasurementReading, WeightReading

MEASUREMENTS_SYSTEM_PROMPT = (
    "Each photo shows a garment being measured with a ruler or tape measure. For each "
    "photo, in order: read the numeric measurement, infer what is being measured from the "
    "garment's orientation and the ruler's placement (e.g. pit_to_pit, length, inseam, "
    "waist_flat, sleeve, shoulder_to_shoulder), and report the unit (in or cm) as actually "
    "shown. Report your confidence honestly — a blurry or ambiguous ruler read should be "
    "low confidence, not omitted."
)

MEASUREMENTS_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "readings": {
            "type": "array",
            "description": "One entry per input photo, in the same order provided.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "number"},
                    "unit": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["name", "value", "unit", "confidence"],
            },
        }
    },
    "required": ["readings"],
}

WEIGHT_SYSTEM_PROMPT = (
    "Each photo shows a scale or notebook readout of a package's weight. For each photo, "
    "in order, read the weight value and unit as shown."
)

WEIGHT_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "readings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": "number"},
                    "unit": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["value", "unit", "confidence"],
            },
        }
    },
    "required": ["readings"],
}


def read_measurements(
    client: AnthropicStructuredClient, ruler_photo_paths: list[Path]
) -> tuple[list[MeasurementReading], CallResult | None]:
    if not ruler_photo_paths:
        return [], None

    content = [load_image_as_api_content_block(p) for p in ruler_photo_paths]
    content.append({"type": "text", "text": f"Read these {len(ruler_photo_paths)} ruler measurement photos, in order."})

    result = client.call_structured(
        system=MEASUREMENTS_SYSTEM_PROMPT,
        content=content,
        tool_name="read_measurements",
        tool_schema=MEASUREMENTS_TOOL_SCHEMA,
        max_tokens=1024,
    )
    readings = [MeasurementReading(**r) for r in result.data["readings"]]
    return readings, result


def read_package_weight(
    client: AnthropicStructuredClient, scale_photo_paths: list[Path]
) -> tuple[WeightReading | None, CallResult | None]:
    if not scale_photo_paths:
        return None, None

    content = [load_image_as_api_content_block(p) for p in scale_photo_paths]
    content.append({"type": "text", "text": "Read the weight shown in this photo."})

    result = client.call_structured(
        system=WEIGHT_SYSTEM_PROMPT,
        content=content,
        tool_name="read_package_weight",
        tool_schema=WEIGHT_TOOL_SCHEMA,
        max_tokens=512,
    )
    readings = result.data["readings"]
    if not readings:
        return None, result
    return WeightReading(**readings[0]), result
