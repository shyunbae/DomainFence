import json
from agent.judge import grade, normalize_answer
from agent.llm import LLMResponse

TASK = {"id": "t1", "question": "What is tuition?", "gold_answer": "$58,000", "answer_variants": ["58000 dollars"]}


class FakeLLM:
    def __init__(self, reply="YES", cost=0.001):
        self.reply, self.cost, self.calls = reply, cost, []

    def complete(self, model, system, messages, max_tokens):
        self.calls.append((model, system, messages, max_tokens))
        return LLMResponse(self.reply, 10, 1, self.cost)


class NoLLM:
    def complete(self, *a, **k):
        raise AssertionError("LLM must not be called")


def test_normalize():
    assert normalize_answer("  The Cost: $58,000!  ") == "the cost $58,000"
    assert normalize_answer("50.5%  ok?") == "50.5% ok"


def test_none_answer(tmp_path):
    assert grade(TASK, None, llm=NoLLM(), cache_path=tmp_path / "c.json") == (False, 0.0)


def test_exact_and_variant_skip_llm(tmp_path):
    p = tmp_path / "c.json"
    assert grade(TASK, "$58,000", llm=NoLLM(), cache_path=p) == (True, 0.0)
    assert grade(TASK, "58000 Dollars", llm=NoLLM(), cache_path=p) == (True, 0.0)


def test_yes_no_parsing_and_prompt(tmp_path):
    llm = FakeLLM(" yes, same")
    ok, cost = grade(TASK, "about 58k", llm=llm, cache_path=tmp_path / "c.json")
    assert ok is True and cost == 0.001
    model, system, msgs, mt = llm.calls[0]
    # thinking is on by default and counts against max_tokens, so leave room for it
    assert model == "claude-haiku-5-5" and mt == 1024
    assert msgs[0]["content"] == (
        "Question: What is tuition?\nGold answer: $58,000\nCandidate answer: about 58k\n"
        "Does the candidate state the same fact as the gold answer? Reply YES or NO.")
    ok, _ = grade(TASK, "lots", llm=FakeLLM("NO"), cache_path=tmp_path / "d.json")
    assert ok is False


def test_cache_hit_skips_llm(tmp_path):
    p = tmp_path / "c.json"
    llm = FakeLLM("YES")
    grade(TASK, "about 58k", llm=llm, cache_path=p)
    assert json.loads(p.read_text()) == {"t1::$58,000::about 58k": True}
    assert grade(TASK, "About 58k!", llm=NoLLM(), cache_path=p) == (True, 0.0)


def test_trailing_punct_stripped(tmp_path):
    assert normalize_answer("$58,000.50.") == "$58,000.50"
    assert grade(TASK, "$58,000.", llm=NoLLM(), cache_path=tmp_path / "c.json") == (True, 0.0)


def test_cache_key_includes_gold(tmp_path):
    p = tmp_path / "c.json"
    grade(TASK, "about 58k", llm=FakeLLM("YES"), cache_path=p)
    other = dict(TASK, gold_answer="$61,000", answer_variants=[])
    llm = FakeLLM("NO")
    assert grade(other, "about 58k", llm=llm, cache_path=p) == (False, 0.001)
    assert len(llm.calls) == 1
