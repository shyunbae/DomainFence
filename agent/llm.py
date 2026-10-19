"""LLM wrapper: protocol, response record, Anthropic implementation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# USD per million (input, output) tokens, keyed by model id.
# From Anthropic's first-party price table (cached 2026-10-06), checked 2026-10-18.
PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

# Prompts above the threshold (input tokens) are billed at the long-context rates.
LONG_CONTEXT: dict[str, tuple[int, float, float]] = {
    "claude-haiku-5-5": (100_000, 0.50, 2.50),
}

# Thinking is on by default for both models and counts against max_tokens; low effort
# keeps per-step thinking (and cost) small for this browsing loop.
EFFORT = "low"


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class LLM(Protocol):
    def complete(self, model: str, system: str, messages: list[dict], max_tokens: int) -> LLMResponse: ...


def _rates(model: str, input_tokens: float) -> tuple[float, float]:
    if model in LONG_CONTEXT and input_tokens > LONG_CONTEXT[model][0]:
        return LONG_CONTEXT[model][1], LONG_CONTEXT[model][2]
    return PRICES[model]


def call_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD for one call; KeyError if the model has no price."""
    price_in, price_out = _rates(model, input_tokens)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def estimate_cost(model: str, system: str, messages: list[dict], max_tokens: int) -> float:
    """Worst-case USD for one call: chars/3 input tokens plus a full max_tokens output.

    Returns 0.0 for a model with no PRICES entry (run.check_ready rejects those up front).
    """
    if model not in PRICES:
        return 0.0
    chars = len(system) + sum(len(str(m.get("content", ""))) for m in messages)
    price_in, price_out = _rates(model, chars / 3)
    return (chars / 3 * price_in + max_tokens * price_out) / 1_000_000


class AnthropicLLM:
    """Thin wrapper over anthropic.Anthropic().messages.create with cost accounting."""

    def __init__(self, client=None) -> None:
        if client is None:
            import anthropic  # lazy: not needed in tests

            client = anthropic.Anthropic()
        self._client = client

    def complete(self, model: str, system: str, messages: list[dict], max_tokens: int) -> LLMResponse:
        PRICES[model]  # KeyError before spending anything if the model has no price
        resp = self._client.messages.create(
            model=model, system=system, messages=messages, max_tokens=max_tokens,
            output_config={"effort": EFFORT},
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        tin, tout = resp.usage.input_tokens, resp.usage.output_tokens
        return LLMResponse(text=text, input_tokens=tin, output_tokens=tout,
                           cost_usd=call_cost(model, tin, tout))
