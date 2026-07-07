"""`python -m pipeline.validate testdata/` (PLAN_v2.md M0).

Runs the M1 pipeline over every testdata/<item>/ folder that has an
expected.json, scores the output against it with the four-bucket scorer,
and reports the go/no-go gate: brand+size+category >=90% on readable
photos, aspects >=75% (contradiction + model-null counted against;
unverified-extra excluded).

If notes.md exists for an item, the pipeline runs twice — with and without
seller_context — and both are reported, so the value of her notes on
tagless/vintage items is measurable. The with-notes run (when present) is
the one that counts toward the aggregate gate, since that reflects real
usage once she's writing notes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from db.connection import connect
from pipeline.pipeline import build_default_clients, run_pipeline
from pipeline.scorer import FieldScore, accuracy, score_fields, summarize

CORE_FIELDS = {"categoryId", "Brand", "Size"}
CORE_THRESHOLD = 0.90
ASPECTS_THRESHOLD = 0.75

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}


def find_validate_items(testdata_dir: Path) -> list[Path]:
    return sorted(
        p.parent for p in testdata_dir.glob("*/expected.json")
    )


def _load_photo_paths(item_dir: Path) -> list[Path]:
    photos_dir = item_dir / "photos"
    if not photos_dir.is_dir():
        return []
    return sorted(p for p in photos_dir.iterdir() if p.suffix.lower() in PHOTO_EXTENSIONS)


def _build_actual_fields(output) -> dict[str, str]:
    actual: dict[str, str] = {}
    if output.category_and_aspects:
        if output.category_and_aspects.category_id:
            actual["categoryId"] = output.category_and_aspects.category_id
        for aspect in output.category_and_aspects.aspects:
            if aspect.field.value is not None:
                actual[aspect.name] = aspect.field.value
    return actual


def _build_expected_fields(expected: dict) -> dict[str, str]:
    fields = dict(expected.get("aspects", {}))
    if expected.get("categoryId"):
        fields["categoryId"] = expected["categoryId"]
    return fields


def _run_and_score(item_dir: Path, item_id: str, seller_context: str | None, conn, anthropic_client, taxonomy_client, expected_fields: dict) -> list[FieldScore]:
    photo_paths = _load_photo_paths(item_dir)
    output = run_pipeline(
        item_id=item_id,
        photo_paths=photo_paths,
        seller_context=seller_context,
        conn=conn,
        anthropic_client=anthropic_client,
        taxonomy_client=taxonomy_client,
    )
    actual_fields = _build_actual_fields(output)
    return score_fields(expected_fields, actual_fields)


def _report(label: str, results: list[FieldScore]) -> None:
    counts = summarize(results)
    core_acc = accuracy(results, fields=CORE_FIELDS)
    all_acc = accuracy(results)
    print(f"  [{label}] match={counts['match']} contradiction={counts['contradiction']} "
          f"model_null={counts['model_null_expected_value']} unverified_extra={counts['unverified_extra']}")
    core_str = f"{core_acc:.0%}" if core_acc is not None else "n/a"
    all_str = f"{all_acc:.0%}" if all_acc is not None else "n/a"
    print(f"  [{label}] brand+size+category={core_str}  all-fields={all_str}")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: python -m pipeline.validate <testdata_dir>", file=sys.stderr)
        return 2

    testdata_dir = Path(argv[0])
    if not testdata_dir.is_dir():
        print(f"Not a directory: {testdata_dir}", file=sys.stderr)
        return 2

    item_dirs = find_validate_items(testdata_dir)
    if not item_dirs:
        print(f"No items with expected.json found under {testdata_dir} — nothing to validate.")
        return 0

    load_dotenv()
    conn = connect()
    anthropic_client, taxonomy_client = build_default_clients(conn)

    gate_results: list[FieldScore] = []

    for item_dir in item_dirs:
        item_id = item_dir.name
        expected = json.loads((item_dir / "expected.json").read_text())
        expected_fields = _build_expected_fields(expected)
        notes_path = item_dir / "notes.md"

        print(f"\n=== {item_id} ===")

        without_notes_results = _run_and_score(
            item_dir, item_id, None, conn, anthropic_client, taxonomy_client, expected_fields
        )
        _report("without notes", without_notes_results)

        primary_results = without_notes_results

        if notes_path.exists():
            seller_context = notes_path.read_text().strip()
            with_notes_results = _run_and_score(
                item_dir, item_id, seller_context, conn, anthropic_client, taxonomy_client, expected_fields
            )
            _report("with notes", with_notes_results)
            primary_results = with_notes_results

        gate_results.extend(primary_results)

    print("\n=== Overall (go/no-go gate) ===")
    core_acc = accuracy(gate_results, fields=CORE_FIELDS)
    all_acc = accuracy(gate_results)
    core_str = f"{core_acc:.1%}" if core_acc is not None else "n/a"
    all_str = f"{all_acc:.1%}" if all_acc is not None else "n/a"
    print(f"brand+size+category: {core_str} (threshold {CORE_THRESHOLD:.0%})")
    print(f"aspects (all fields): {all_str} (threshold {ASPECTS_THRESHOLD:.0%})")

    passed = (
        core_acc is not None and core_acc >= CORE_THRESHOLD
        and all_acc is not None and all_acc >= ASPECTS_THRESHOLD
    )
    print("GO" if passed else "NO-GO")
    if not passed:
        print(
            "Below gate — iterate on prompts/photo guidance, then rerun the same testdata "
            "under a stronger ANTHROPIC_MODEL to check whether the gap is prompt or model "
            "before building any UI (PLAN_v2.md M0)."
        )

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
