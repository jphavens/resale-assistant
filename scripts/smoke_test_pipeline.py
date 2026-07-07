"""One-off smoke test: run the M1 pipeline on a single item folder and print
the full structured output. No scoring — this is for eyeballing pipeline
output before trusting it on a batch, not the M0 harness (which needs
expected.json).

Run: .venv/bin/python scripts/smoke_test_pipeline.py testdata/item-01
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from db.connection import connect
from pipeline.pipeline import build_default_clients, run_pipeline

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}


def main(item_dir: Path) -> None:
    photos_dir = item_dir / "photos"
    photo_paths = sorted(p for p in photos_dir.iterdir() if p.suffix.lower() in PHOTO_EXTENSIONS)
    notes_path = item_dir / "notes.md"
    seller_context = notes_path.read_text().strip() if notes_path.exists() else None

    print(f"Item: {item_dir.name}")
    print(f"Photos: {len(photo_paths)} -> {[p.name for p in photo_paths]}")
    print(f"seller_context: {seller_context!r}")
    print()

    conn = connect()
    anthropic_client, taxonomy_client = build_default_clients(conn)

    output = run_pipeline(
        item_id=item_dir.name,
        photo_paths=photo_paths,
        seller_context=seller_context,
        conn=conn,
        anthropic_client=anthropic_client,
        taxonomy_client=taxonomy_client,
    )

    print("=" * 70)
    print("STEP 1 — PHOTO CLASSIFICATION")
    print("=" * 70)
    for c in output.photo_classifications:
        print(f"  {Path(c.photo_path).name:20s} -> {c.photo_class.value}")

    print()
    print("=" * 70)
    print("STEP 2 — IDENTIFICATION")
    print("=" * 70)
    ident = output.identification
    for name in ("brand", "item_type", "gender_department", "size", "color", "material", "pattern", "era_estimate"):
        f = getattr(ident, name)
        conflict_str = ""
        if f.conflict:
            conflict_str = f"  [CONFLICT: vision={f.conflict.vision_value!r} vs seller={f.conflict.seller_context_value!r}]"
        print(f"  {name:18s} = {f.value!r:30}  confidence={f.confidence}  origin={f.origin}{conflict_str}")
    print(f"  style_descriptors  = {ident.style_descriptors}")
    print(f"  notable_features   = {ident.notable_features}")
    if ident.flaws:
        print("  flaws:")
        for flaw in ident.flaws:
            print(f"    - {flaw.description} (confidence={flaw.confidence})")
    else:
        print("  flaws: none noted")

    print()
    print("=" * 70)
    print("STEP 3 — MEASUREMENTS")
    print("=" * 70)
    if output.measurements:
        for m in output.measurements:
            print(f"  {m.name:20s} = {m.value} {m.unit}  (confidence={m.confidence})")
    else:
        print("  (no ruler_measurement photos classified)")
    if output.package_weight:
        w = output.package_weight
        print(f"  package_weight = {w.value} {w.unit}  (confidence={w.confidence})")
    else:
        print("  package_weight: (no scale_readout photos classified)")

    print()
    print("=" * 70)
    print("STEP 4 — CATEGORY + ASPECTS")
    print("=" * 70)
    cat = output.category_and_aspects
    if cat and cat.category_id:
        print(f"  chosen category: {cat.category_name!r} (categoryId={cat.category_id})")
        if cat.category_alternates:
            print("  alternates:")
            for alt in cat.category_alternates:
                print(f"    - {alt.category_name!r} (categoryId={alt.category_id})")
        print()
        print(f"  {'aspect':25s} {'mode':15s} {'req?':6s} {'value':25s} confidence")
        for a in cat.aspects:
            status = a.field.value if a.field.value is not None else "(blank — couldn't determine)"
            print(f"  {a.name:25s} {str(a.aspect_mode):15s} {str(a.required):6s} {str(status):25s} {a.field.confidence}")
    else:
        print("  No category suggestion found.")

    print()
    print("=" * 70)
    print("STEP 5 — TITLE + DESCRIPTION")
    print("=" * 70)
    td = output.title_and_description
    print(f"  Title ({len(td.title)}/80 chars): {td.title}")
    print()
    print("  Description:")
    for line in td.description.splitlines():
        print(f"    {line}")
    if td.depop_hashtags:
        print(f"\n  Depop hashtags (not in eBay description): {td.depop_hashtags}")

    print()
    print("=" * 70)
    print("STEP 6 — PRICE GUIDANCE")
    print("=" * 70)
    price = output.price_guidance
    print(f"  Range: ${price.low} - ${price.high}")
    print(f"  Reasoning: {price.reasoning}")
    print("  Comps:")
    for comp in price.comps:
        print(f"    - {comp.title} — ${comp.price} — {comp.url}")
    print(f"  Terapeak: {price.terapeak_url}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: smoke_test_pipeline.py <item_dir>", file=sys.stderr)
        sys.exit(2)
    main(Path(sys.argv[1]))
