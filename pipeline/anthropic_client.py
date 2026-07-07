"""Thin wrapper around the Anthropic SDK for structured tool-call outputs.

The model ID always comes from ANTHROPIC_MODEL (PLAN_v2.md hard constraint
#5) so the M0 harness can A/B models with a one-line env change — never
hardcode a model ID here or in any step module.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import anthropic

DEFAULT_MODEL = "claude-sonnet-4-6"


def get_model_id() -> str:
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)


@dataclass
class CallResult:
    data: dict
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class AnthropicStructuredClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.model = model or get_model_id()

    def call_structured(
        self,
        system: str,
        content: list[dict[str, Any]],
        tool_name: str,
        tool_schema: dict,
        max_tokens: int = 4096,
        extra_tools: list[dict] | None = None,
    ) -> CallResult:
        """Force a single tool call and return its parsed input plus usage.

        Using a forced tool_choice (rather than output_config.format) works
        across whatever model ANTHROPIC_MODEL names, including older ones
        used for A/B comparison during M0.
        """
        tools = [
            {
                "name": tool_name,
                "description": f"Return the {tool_name} result.",
                "input_schema": tool_schema,
                "strict": True,
            }
        ]
        if extra_tools:
            tools.extend(extra_tools)

        started = time.monotonic()
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": content}],
        )
        latency_ms = int((time.monotonic() - started) * 1000)

        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return CallResult(
                    data=block.input,
                    model_id=response.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    latency_ms=latency_ms,
                )
        raise RuntimeError(f"Model did not return the {tool_name} tool call")

    def create_raw(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict],
        max_tokens: int = 4096,
    ) -> anthropic.types.Message:
        """Raw passthrough for multi-turn tool loops (e.g. web search + a
        final custom tool call) that don't fit the single forced-tool shape
        of call_structured.
        """
        return self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
