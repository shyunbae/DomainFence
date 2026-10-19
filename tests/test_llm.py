from types import SimpleNamespace

import pytest

from agent import llm as L
from agent.loop import MAX_TOKENS


def test_prices_for_experiment_models():
    assert L.PRICES["claude-sonnet-5-5"] == (2.00, 10.00)
    assert L.PRICES["claude-haiku-5-5"] == (0.10, 0.50)


def test_cost_uses_long_context_rate_above_threshold():
    assert L.call_cost("claude-haiku-5-5", 50_000, 1_000) == pytest.approx(
        (50_000 * 0.10 + 1_000 * 0.50) / 1e6)
    assert L.call_cost("claude-haiku-5-5", 150_000, 1_000) == pytest.approx(
        (150_000 * 0.50 + 1_000 * 2.50) / 1e6)
    assert L.call_cost("claude-sonnet-5-5", 150_000, 1_000) == pytest.approx(
        (150_000 * 2.00 + 1_000 * 10.00) / 1e6)


def test_estimate_cost_uses_long_context_rate():
    msgs = [{"role": "user", "content": "x" * 330_000}]  # ~110k tokens at chars/3
    assert L.estimate_cost("claude-haiku-5-5", "", msgs, 100) == pytest.approx(
        (110_000 * 0.50 + 100 * 2.50) / 1e6)


class FakeMessages:
    def __init__(self):
        self.kwargs = None

    def create(self, **kw):
        self.kwargs = kw
        return SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking=""),
                     SimpleNamespace(type="text", text='{"action":"back"}')],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
        )


def test_anthropic_llm_sets_low_effort_and_ignores_thinking_blocks():
    msgs = FakeMessages()
    llm = L.AnthropicLLM(client=SimpleNamespace(messages=msgs))
    r = llm.complete("claude-sonnet-5-5", "sys", [{"role": "user", "content": "hi"}], 4096)
    assert msgs.kwargs["output_config"] == {"effort": "low"}
    assert msgs.kwargs["max_tokens"] == 4096 and "thinking" not in msgs.kwargs
    assert r.text == '{"action":"back"}'
    assert r.cost_usd == pytest.approx((1000 * 2.00 + 200 * 10.00) / 1e6)


def test_agent_max_tokens_leaves_room_for_thinking():
    assert MAX_TOKENS == 4096
