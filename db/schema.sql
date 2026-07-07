-- Taxonomy API response cache (7-day TTL, enforced in application code).
CREATE TABLE IF NOT EXISTS taxonomy_cache (
    cache_key TEXT PRIMARY KEY,     -- e.g. "category_suggestions:{tree_id}:{query}"
    response_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL        -- ISO 8601 UTC timestamp
);

-- One row per intake item (photos + optional seller note).
CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    seller_context TEXT,
    status TEXT NOT NULL DEFAULT 'queued',  -- queued | processing | ready | done
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- One row per pipeline run over an item (M0 harness runs and later live M1 runs).
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    item_id TEXT,
    model_id TEXT NOT NULL,
    with_seller_context INTEGER NOT NULL DEFAULT 1,  -- 0/1
    output_json TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (item_id) REFERENCES items(item_id)
);

-- Per-model-call cost/latency log (Step 1-6 Anthropic calls).
CREATE TABLE IF NOT EXISTS model_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT,
    step TEXT NOT NULL,              -- classify | identify | measurements | aspects | title_description | price
    model_id TEXT NOT NULL,
    photo_count INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

-- Field-level edit + origin tracking (Phase 2 gate data — do not skip).
CREATE TABLE IF NOT EXISTS edits (
    edit_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    model_value TEXT,
    edited_value TEXT,
    origin TEXT NOT NULL,            -- vision | seller_context | manual
    edited_at TEXT NOT NULL,
    FOREIGN KEY (item_id) REFERENCES items(item_id)
);
