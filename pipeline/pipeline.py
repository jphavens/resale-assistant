"""M1 pipeline orchestrator — runs all six steps in order (PLAN_v2.md).

seller_context is injected into Steps 2, 4, and 5 only, per the plan. Every
model call's cost is logged to SQLite via pipeline.cost_log.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ebay_client.auth import EbayAuthClient
from ebay_client.taxonomy import TaxonomyClient
from pipeline.anthropic_client import AnthropicStructuredClient
from pipeline.cost_log import log_model_call
from pipeline.models import PhotoClass, PipelineOutput
from pipeline.steps.category_aspects import get_category_and_aspects
from pipeline.steps.classify import classify_photos
from pipeline.steps.identify import identify_item
from pipeline.steps.measurements import read_measurements, read_package_weight
from pipeline.steps.price import get_price_guidance
from pipeline.steps.title_description import generate_title_and_description

MARKETPLACE_ID = "EBAY_US"


def run_pipeline(
    item_id: str,
    photo_paths: list[Path],
    seller_context: str | None,
    conn: sqlite3.Connection,
    anthropic_client: AnthropicStructuredClient,
    taxonomy_client: TaxonomyClient,
    run_id: str | None = None,
) -> PipelineOutput:
    run_id = run_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO items (item_id, seller_context, status, created_at, updated_at)
        VALUES (?, ?, 'processing', ?, ?)
        ON CONFLICT(item_id) DO UPDATE SET
            seller_context = excluded.seller_context,
            status = 'processing',
            updated_at = excluded.updated_at
        """,
        (item_id, seller_context, now, now),
    )
    conn.execute(
        "INSERT INTO runs (run_id, item_id, model_id, with_seller_context, started_at) VALUES (?, ?, ?, ?, ?)",
        (run_id, item_id, anthropic_client.model, 1 if seller_context else 0, now),
    )
    conn.commit()

    # Step 1 — classify
    classifications, classify_call = classify_photos(anthropic_client, photo_paths)
    log_model_call(conn, run_id, "classify", classify_call.model_id, len(photo_paths),
                    classify_call.input_tokens, classify_call.output_tokens, classify_call.latency_ms)

    ruler_photos = [
        Path(c.photo_path) for c in classifications if c.photo_class == PhotoClass.RULER_MEASUREMENT
    ]
    scale_photos = [
        Path(c.photo_path) for c in classifications if c.photo_class == PhotoClass.SCALE_READOUT
    ]

    # Step 2 — identify (seller_context injected)
    identification, identify_call = identify_item(anthropic_client, photo_paths, seller_context)
    log_model_call(conn, run_id, "identify", identify_call.model_id, len(photo_paths),
                    identify_call.input_tokens, identify_call.output_tokens, identify_call.latency_ms)

    # Step 3 — measurements
    measurements, measurements_call = read_measurements(anthropic_client, ruler_photos)
    if measurements_call:
        log_model_call(conn, run_id, "measurements", measurements_call.model_id, len(ruler_photos),
                        measurements_call.input_tokens, measurements_call.output_tokens, measurements_call.latency_ms)

    package_weight, weight_call = read_package_weight(anthropic_client, scale_photos)
    if weight_call:
        log_model_call(conn, run_id, "weight", weight_call.model_id, len(scale_photos),
                        weight_call.input_tokens, weight_call.output_tokens, weight_call.latency_ms)

    # Step 4 — category + aspects (seller_context injected)
    category_tree_id = taxonomy_client.get_default_category_tree_id(MARKETPLACE_ID)
    category_and_aspects, aspects_call = get_category_and_aspects(
        anthropic_client, taxonomy_client, category_tree_id, identification, seller_context
    )
    if aspects_call:
        log_model_call(conn, run_id, "aspects", aspects_call.model_id, 0,
                        aspects_call.input_tokens, aspects_call.output_tokens, aspects_call.latency_ms)

    # Step 5 — title + description (seller_context injected)
    title_and_description, title_call = generate_title_and_description(
        anthropic_client, identification, measurements, category_and_aspects, seller_context
    )
    log_model_call(conn, run_id, "title_description", title_call.model_id, 0,
                    title_call.input_tokens, title_call.output_tokens, title_call.latency_ms)

    # Step 6 — price guidance (no seller_context per plan)
    price_guidance, price_usage = get_price_guidance(anthropic_client, identification)
    log_model_call(conn, run_id, "price", price_usage.model_id, 0,
                    price_usage.input_tokens, price_usage.output_tokens, price_usage.latency_ms)

    output = PipelineOutput(
        item_id=item_id,
        seller_context=seller_context,
        photo_classifications=classifications,
        identification=identification,
        measurements=measurements,
        package_weight=package_weight,
        category_and_aspects=category_and_aspects,
        title_and_description=title_and_description,
        price_guidance=price_guidance,
    )

    finished_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE runs SET output_json = ?, finished_at = ? WHERE run_id = ?",
        (output.model_dump_json(), finished_at, run_id),
    )
    conn.execute(
        "UPDATE items SET status = 'ready', updated_at = ? WHERE item_id = ?",
        (finished_at, item_id),
    )
    conn.commit()

    return output


def build_default_clients(conn: sqlite3.Connection) -> tuple[AnthropicStructuredClient, TaxonomyClient]:
    import os

    anthropic_client = AnthropicStructuredClient(api_key=os.environ["ANTHROPIC_API_KEY"])
    auth = EbayAuthClient(os.environ["EBAY_CLIENT_ID"], os.environ["EBAY_CLIENT_SECRET"])
    taxonomy_client = TaxonomyClient(auth, conn)
    return anthropic_client, taxonomy_client
