"""Step 6 — Price guidance (PLAN_v2.md).

Uses Claude's server-side web_search tool to look up sold/active comparables,
then a custom `report_price_guidance` tool call to get the final structured
answer. Web search runs entirely server-side (no client execution loop for
it); pause_turn (server tool iteration cap) is resumed per Anthropic's
documented pattern — resend the same two messages, no synthetic
"Continue" text.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import quote_plus

from pipeline.anthropic_client import AnthropicStructuredClient
from pipeline.models import Identification, PriceComp, PriceGuidance

MAX_ITERATIONS = 5

SYSTEM_PROMPT = (
    "You are researching resale price guidance for an eBay listing. Search for sold/"
    "completed and active listings matching the brand, item type, and size given. Once "
    "you have enough comparables, call report_price_guidance exactly once with: a "
    "suggested price range, 2-4 comp links with titles and prices where visible, and a "
    "one-paragraph reasoning. This is a suggestion for the seller to review, not an "
    "authoritative price — never present a single number as definitive."
)

REPORT_TOOL = {
    "name": "report_price_guidance",
    "description": "Report the final price guidance after researching comps.",
    "input_schema": {
        "type": "object",
        "properties": {
            "low": {"type": "number"},
            "high": {"type": "number"},
            "reasoning": {"type": "string"},
            "comps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "price": {"type": ["number", "null"]},
                    },
                    "required": ["title", "url", "price"],
                },
            },
        },
        "required": ["low", "high", "reasoning", "comps"],
    },
}

WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}


def _terapeak_url(query: str) -> str:
    return f"https://www.ebay.com/sh/research?keywords={quote_plus(query)}"


@dataclass
class PriceGuidanceUsage:
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    call_count: int


def get_price_guidance(
    client: AnthropicStructuredClient, identification: Identification
) -> tuple[PriceGuidance, PriceGuidanceUsage]:
    query_parts = [identification.brand.value, identification.item_type.value, identification.size.value]
    query = " ".join(p for p in query_parts if p)

    messages: list[dict] = [{"role": "user", "content": f"Research price guidance for: {query}"}]
    tools = [WEB_SEARCH_TOOL, REPORT_TOOL]

    usage = PriceGuidanceUsage(model_id=client.model, input_tokens=0, output_tokens=0, latency_ms=0, call_count=0)
    started = time.monotonic()

    for _ in range(MAX_ITERATIONS):
        response = client.create_raw(system=SYSTEM_PROMPT, messages=messages, tools=tools, max_tokens=2048)
        usage.call_count += 1
        usage.input_tokens += response.usage.input_tokens
        usage.output_tokens += response.usage.output_tokens
        usage.model_id = response.model

        report_block = next(
            (b for b in response.content if b.type == "tool_use" and b.name == "report_price_guidance"),
            None,
        )
        if report_block is not None:
            usage.latency_ms = int((time.monotonic() - started) * 1000)
            data = report_block.input
            guidance = PriceGuidance(
                low=data.get("low"),
                high=data.get("high"),
                reasoning=data.get("reasoning", ""),
                comps=[PriceComp(**c) for c in data.get("comps", [])],
                terapeak_url=_terapeak_url(query),
            )
            return guidance, usage

        if response.stop_reason == "pause_turn":
            messages = [messages[0], {"role": "assistant", "content": response.content}]
            continue

        # end_turn (or tool_use with no report_block, which shouldn't happen
        # since report_price_guidance is the only client tool declared): the
        # model finished without reporting — nudge it explicitly.
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": "Call report_price_guidance now with your findings."})

    usage.latency_ms = int((time.monotonic() - started) * 1000)
    guidance = PriceGuidance(
        reasoning="Could not gather price guidance — search did not complete.",
        terapeak_url=_terapeak_url(query),
    )
    return guidance, usage
