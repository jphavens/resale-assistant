"""Per-model-call cost/latency logging to SQLite (PLAN_v2.md M1: "Log every
model call's model ID, input photo count, tokens, latency, and cost").

Pricing is USD per million tokens (input, output). Unknown models log token
counts with cost_usd=0.0 rather than raising — the run must never fail just
because the configured ANTHROPIC_MODEL isn't in this table yet.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

PRICING_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def estimate_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING_PER_MILLION_TOKENS.get(model_id)
    if pricing is None:
        return 0.0
    input_price, output_price = pricing
    return (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price


def log_model_call(
    conn: sqlite3.Connection,
    run_id: str | None,
    step: str,
    model_id: str,
    photo_count: int,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
) -> str:
    call_id = str(uuid.uuid4())
    cost_usd = estimate_cost_usd(model_id, input_tokens, output_tokens)
    conn.execute(
        """
        INSERT INTO model_calls
            (call_id, run_id, step, model_id, photo_count, input_tokens,
             output_tokens, cost_usd, latency_ms, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            call_id,
            run_id,
            step,
            model_id,
            photo_count,
            input_tokens,
            output_tokens,
            cost_usd,
            latency_ms,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return call_id
