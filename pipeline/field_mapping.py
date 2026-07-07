"""Isolated field-mapping layer (PLAN_v2.md Phase 2 prep).

`PipelineOutput` (pipeline/models.py) is the single source of truth. This
module is the ONLY place that reshapes it for an external consumer, so
Phase 2's `publisher` module can target the eBay Listing API's
`createItemDraft` schema by changing this file alone — no changes to the
pipeline itself.

The Listing API draft schema is NOT verified yet (Phase 2 gate, "verify at
build time, not from memory" — PLAN_v2.md Phase 2). `to_generic_draft`
therefore produces a stable, well-structured generic shape, not a claimed
Listing API payload. Phase 2 replaces/extends this function once the real
contract is pulled and pinned, the same way ebay_client/ was built.
"""
from __future__ import annotations

from pipeline.models import PipelineOutput


def to_generic_draft(output: PipelineOutput) -> dict:
    ident = output.identification
    cat = output.category_and_aspects
    title_desc = output.title_and_description
    price = output.price_guidance

    return {
        "item_id": output.item_id,
        "title": title_desc.title if title_desc else None,
        "description": title_desc.description if title_desc else None,
        "category_id": cat.category_id if cat else None,
        "aspects": {
            a.name: a.field.value
            for a in (cat.aspects if cat else [])
            if a.field.value is not None
        },
        "identification": {
            "brand": ident.brand.value if ident else None,
            "size": ident.size.value if ident else None,
            "color": ident.color.value if ident else None,
            "material": ident.material.value if ident else None,
        }
        if ident
        else None,
        "measurements": {m.name: {"value": m.value, "unit": m.unit} for m in output.measurements},
        "package_weight": (
            {"value": output.package_weight.value, "unit": output.package_weight.unit}
            if output.package_weight
            else None
        ),
        "price_range": {"low": price.low, "high": price.high} if price else None,
    }
