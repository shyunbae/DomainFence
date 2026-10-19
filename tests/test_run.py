from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.llm import LLMResponse
from experiments import run as R
from experiments.run import (MODELS, EpisodeSpec, attacker_hosts_for, build_grid, pending,
                             run_spec, should_stop, spent_usd)

from agent.loop import Observation


def _tasks(n_per_type=(14, 13, 13)):
    out = []
    for typ, n in zip(("in_apex", "partner", "wrong_source"), n_per_type):
        for i in range(n):
            out.append({"id": f"{typ}_{i:02d}", "type": typ, "seed": "cmu.edu",
                        "question": "q?", "gold_answer": "42", "answer_variants": [],
                        "partner_domains": [], "misinfo_answer": "7"})
    return out


def test_grid_sizes():
    tasks = _tasks()
    assert len(tasks) == 40
    assert len(build_grid(tasks, "clean")) == 480  # 40 x 6 arms x 2 models
    assert len(build_grid(tasks, "attack")) == 960  # 40 x 4 first-round x 3 arms x 2 models
    assert len(build_grid(tasks, "attack2_dev")) == 8 * 2 * 1 * 2  # 8 dev tasks x 2 attacks x none x 2 models
    assert len(build_grid(tasks, "attack2")) == 32 * 2 * 3 * 2  # 32 held-out x 2 attacks x 3 arms x 2 models
    assert len(build_grid(tasks, "attack2", repeats=3)) == 32 * 2 * 3 * 2 * 3
    assert len(build_grid(tasks, "pilot")) == 60


def test_pilot_selection_by_type():
    grid = build_grid(list(reversed(_tasks())), "pilot")
    ids = sorted({s.task_id for s in grid})
    assert ids == ["in_apex_00", "in_apex_01", "partner_00", "partner_01", "wrong_source_00"]
    assert {s.arm for s in grid} == {"none", "apex", "hyb10"}
    assert {s.attack for s in grid} == {"none", "visible_link"}


def test_key_format():
    s = EpisodeSpec("t1", "apex", "visible_link", "claude-haiku-5-5", 2)
    assert s.key == "t1__apex__visible_link__claude-haiku-5-5__r2"
    assert EpisodeSpec("t1", "none", "none", "m").key.endswith("__r0")


def test_arms_contiguous_and_order():
    grid = build_grid(_tasks()[:3], "attack")
    groups = [(s.task_id, s.model, s.attack) for s in grid]
    # each (task, model, attack) group is one contiguous run of 3 arms
    runs = [groups[i:i + 3] for i in range(0, len(groups), 3)]
    assert all(len(set(r)) == 1 for r in runs)
    firsts = [r[0] for r in runs]
    assert len(set(firsts)) == len(firsts)
    assert [g[0] for g in groups] == sorted(g[0] for g in groups)  # by task
    t0 = [s for s in grid if s.task_id == grid[0].task_id]
    assert [s.model for s in t0][:12] == [MODELS[0]] * 12  # model before attack


def _write(runs, spec, **kw):
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{spec.key}.json").write_text(json.dumps(kw))


def test_pending(tmp_path):
    specs = [EpisodeSpec(f"t{i}", "none", "none", "m") for i in range(5)]
    _write(tmp_path, specs[0], end_reason="answer")
    _write(tmp_path, specs[1], end_reason="infra_error")
    _write(tmp_path, specs[2], end_reason="infra_error", retried=True)
    _write(tmp_path, specs[3], end_reason="step_cap")
    assert pending(specs, tmp_path) == [specs[1], specs[4]]


def test_spent_usd_sums_both(tmp_path):
    _write(tmp_path / "a", EpisodeSpec("x", "none", "none", "m"), cost_usd=0.1, judge_cost_usd=0.02)
    _write(tmp_path / "b", EpisodeSpec("y", "none", "none", "m"), cost_usd=0.2)
    assert spent_usd(tmp_path) == pytest.approx(0.32)
    assert spent_usd(tmp_path / "missing") == 0.0


def test_should_stop():
    assert not should_stop(59.48, 60)
    assert should_stop(59.5, 60)
    assert should_stop(70, 60)


def test_attacker_hosts_for():
    hosts = attacker_hosts_for("mit.edu", ["cmu.edu", "mit.edu", "cmu.edu"])
    assert hosts == ["mit-info-portal.com", "cmu-info-portal.com"]


# ---- run_spec end-to-end with fakes ----------------------------------------------------

class FakeLLM:
    def __init__(self, text):
        self.text = text

    def complete(self, model, system, messages, max_tokens):
        return LLMResponse(text=self.text, input_tokens=10, output_tokens=5, cost_usd=0.01)


class FakeBrowser:
    def __init__(self, *args, fail_enter=False, fail_exit=False, events=None):
        self.args = args
        self.events = list(events or [])
        self.fail_enter = fail_enter
        self.fail_exit = fail_exit

    async def __aenter__(self):
        if self.fail_enter:
            raise RuntimeError("chromium missing")
        return self

    async def __aexit__(self, *exc):
        if self.fail_exit:
            raise RuntimeError("chromium crashed on close")
        return None

    async def start(self, url):
        return "ok"

    async def observe(self):
        return Observation(url="https://cmu.edu/", text="tuition is 42", challenge=False)

    async def act(self, action):
        return "ok"


TASK = {"id": "t1", "type": "in_apex", "seed": "cmu.edu", "question": "q?", "gold_answer": "42",
        "answer_variants": [], "partner_domains": [], "misinfo_answer": "7"}
SEEDS = [{"seed": "cmu.edu", "aliases": []}, {"seed": "mit.edu", "aliases": []}]


async def test_run_spec_writes_file(tmp_path):
    seen = {}

    def factory(*args):
        seen["args"] = args
        return FakeBrowser(*args)

    runs = tmp_path / "runs" / "pilot"
    spec = EpisodeSpec("t1", "none", "none", "claude-haiku-5-5")
    llm = FakeLLM('{"action":"answer","text":"42","source_url":"https://cmu.edu/"}')
    out = await run_spec(spec, TASK, SEEDS, llm=llm, search=None, judge_llm=llm,
                         runs_dir=runs, browser_factory=factory,
                         whitelist_dir=tmp_path, judge_cache=tmp_path / "j.json")
    data = json.loads((runs / f"{spec.key}.json").read_text())
    assert data == out
    assert data["end_reason"] == "answer" and data["correct"] is True
    assert data["judge_cost_usd"] == 0.0 and data["retried"] is False and data["phase"] == "pilot"
    assert seen["args"][-1][0] == "cmu-info-portal.com"


async def test_run_spec_infra_error_on_setup(tmp_path):
    runs = tmp_path / "attack"
    spec = EpisodeSpec("t1", "none", "visible_link", "claude-haiku-5-5")
    out = await run_spec(spec, TASK, SEEDS, llm=FakeLLM("x"), search=None, judge_llm=FakeLLM("x"),
                         runs_dir=runs, browser_factory=lambda *a: FakeBrowser(*a, fail_enter=True),
                         whitelist_dir=tmp_path, judge_cache=tmp_path / "j.json", retried=True)
    data = json.loads((runs / f"{spec.key}.json").read_text())
    assert data["end_reason"] == "infra_error" and "chromium missing" in data["infra_detail"]
    assert data["correct"] is False and data["judge_cost_usd"] == 0.0 and data["retried"] is True
    assert pending([spec], runs) == []


async def test_grade_error_still_writes_file(tmp_path):
    runs = tmp_path / "pilot"
    spec = EpisodeSpec("t1", "none", "none", "claude-haiku-5-5")
    llm = FakeLLM('{"action":"answer","text":"forty-two","source_url":null}')
    out = await run_spec(spec, TASK, SEEDS, llm=llm, search=None, judge_llm=RaisingLLM(),
                         runs_dir=runs, browser_factory=lambda *a: FakeBrowser(*a),
                         whitelist_dir=tmp_path, judge_cache=tmp_path / "j.json")
    data = json.loads((runs / f"{spec.key}.json").read_text())
    assert data["correct"] is False and data["judge_cost_usd"] == 0.0
    assert data["grade_error"].startswith("RuntimeError: judge down")
    assert data["cost_usd"] == pytest.approx(0.01)
    assert pending([spec], runs) == []
    assert spent_usd(tmp_path) == pytest.approx(0.01)


class RaisingLLM:
    def complete(self, *a, **k):
        raise RuntimeError("judge down")


async def test_retry_carries_prior_cost(tmp_path):
    runs = tmp_path / "attack"
    spec = EpisodeSpec("t1", "none", "none", "claude-haiku-5-5")
    _write(runs, spec, end_reason="infra_error", cost_usd=0.2, judge_cost_usd=0.0, prior_cost_usd=0.1)
    llm = FakeLLM('{"action":"answer","text":"42","source_url":null}')
    await run_spec(spec, TASK, SEEDS, llm=llm, search=None, judge_llm=llm, runs_dir=runs,
                   browser_factory=lambda *a: FakeBrowser(*a), whitelist_dir=tmp_path,
                   judge_cache=tmp_path / "j.json", retried=True)
    data = json.loads((runs / f"{spec.key}.json").read_text())
    assert data["prior_cost_usd"] == pytest.approx(0.3) and data["retried"] is True
    assert spent_usd(runs) == pytest.approx(0.31)


def test_spent_usd_handles_null(tmp_path):
    _write(tmp_path, EpisodeSpec("x", "none", "none", "m"), cost_usd=None, judge_cost_usd=0.05)
    assert spent_usd(tmp_path) == pytest.approx(0.05)


# ---- run_passes -----------------------------------------------------------------------

def _mk_one(runs, calls, outcome="answer"):
    async def run_one(spec, retried):
        calls.append((spec.key, retried))
        _write(runs, spec, end_reason=outcome, retried=retried)
        return {"end_reason": outcome, "correct": False}
    return run_one


async def test_passes_retry_once_and_skip_retried(tmp_path):
    runs = tmp_path / "runs"
    specs = [EpisodeSpec(f"t{i}", "none", "none", "m") for i in range(4)]
    _write(runs, specs[0], end_reason="answer")
    _write(runs, specs[1], end_reason="infra_error")                  # first-time: retry
    _write(runs, specs[2], end_reason="infra_error", retried=True)    # already retried: skip
    calls = []
    ok = await R.run_passes(specs, runs, tmp_path, 60, _mk_one(runs, calls), spent_fn=lambda _: 0.0,
                            log=lambda m: None)
    assert ok is True
    assert calls == [(specs[3].key, False), (specs[1].key, True)]
    assert json.loads((runs / f"{specs[1].key}.json").read_text())["retried"] is True


async def test_passes_infra_in_main_pass_retried_once(tmp_path):
    runs = tmp_path / "runs"
    specs = [EpisodeSpec("t0", "none", "none", "m")]
    calls = []
    await R.run_passes(specs, runs, tmp_path, 60, _mk_one(runs, calls, "infra_error"),
                       spent_fn=lambda _: 0.0, log=lambda m: None)
    assert calls == [("t0__none__none__m__r0", False), ("t0__none__none__m__r0", True)]


async def test_passes_stop_at_cap_skips_retry(tmp_path):
    runs = tmp_path / "runs"
    specs = [EpisodeSpec(f"t{i}", "none", "none", "m") for i in range(3)]
    _write(runs, specs[0], end_reason="infra_error")
    spent = iter([0.0, 59.9])
    calls, msgs = [], []
    ok = await R.run_passes(specs, runs, tmp_path, 60, _mk_one(runs, calls),
                            spent_fn=lambda _: next(spent), log=msgs.append)
    assert ok is False
    assert calls == [(specs[1].key, False)]  # second main-pass episode and retry pass never start
    assert any("stopping" in m for m in msgs)


# ---- teardown failure keeps the finished episode ---------------------------------------

async def test_teardown_error_keeps_finished_episode(tmp_path):
    runs = tmp_path / "pilot"
    spec = EpisodeSpec("t1", "none", "none", "claude-haiku-5-5")
    llm = FakeLLM('{"action":"answer","text":"42","source_url":null}')
    out = await run_spec(spec, TASK, SEEDS, llm=llm, search=None, judge_llm=llm, runs_dir=runs,
                         browser_factory=lambda *a: FakeBrowser(*a, fail_exit=True),
                         whitelist_dir=tmp_path, judge_cache=tmp_path / "j.json")
    assert out["end_reason"] == "answer" and out["correct"] is True
    assert out["cost_usd"] == pytest.approx(0.01) and len(out["steps"]) == 1
    assert out["teardown_error"] == "RuntimeError: chromium crashed on close"
    assert json.loads((runs / f"{spec.key}.json").read_text()) == out


async def test_setup_failure_preserves_browser_events(tmp_path):
    runs = tmp_path / "pilot"
    spec = EpisodeSpec("t1", "none", "none", "claude-haiku-5-5")
    ev = [{"type": "block", "host": "x"}]
    out = await run_spec(spec, TASK, SEEDS, llm=FakeLLM("x"), search=None, judge_llm=FakeLLM("x"),
                         runs_dir=runs,
                         browser_factory=lambda *a: FakeBrowser(*a, fail_enter=True, events=ev),
                         whitelist_dir=tmp_path, judge_cache=tmp_path / "j.json")
    assert out["end_reason"] == "infra_error" and out["events"] == ev
    assert "teardown_error" not in out


# ---- check_ready -----------------------------------------------------------------------

PRICES = {"claude-sonnet-5-5": (1.0, 2.0), "claude-haiku-5-5": (1.0, 2.0)}
ENV = {"ANTHROPIC_API_KEY": "a", "BRAVE_API_KEY": "b"}


def _ready(**kw):
    args = dict(phase="attack", grid=build_grid(_tasks(), "attack"), models=MODELS,
                judge_model="claude-haiku-5-5", prices=PRICES, env=ENV,
                whitelist_dir=Path("/nonexistent"), seeds=["cmu.edu"])
    args.update(kw)
    return R.check_ready(**args)


def test_check_ready_ok(tmp_path):
    (tmp_path / "cmu.edu.json").write_text("{}")
    _ready(whitelist_dir=tmp_path)


def test_check_ready_missing_price():
    with pytest.raises(RuntimeError, match="claude-sonnet-5-5"):
        _ready(prices={"claude-haiku-5-5": (1.0, 2.0)}, grid=[EpisodeSpec("t", "none", "none", MODELS[0])])


def test_check_ready_missing_judge_price():
    with pytest.raises(RuntimeError, match="judge.*claude-haiku-5-5"):
        _ready(prices={"claude-sonnet-5-5": (1.0, 2.0)}, grid=[EpisodeSpec("t", "none", "none", MODELS[0])])


@pytest.mark.parametrize("missing", ["ANTHROPIC_API_KEY", "BRAVE_API_KEY"])
def test_check_ready_missing_env(missing):
    env = {k: v for k, v in ENV.items() if k != missing}
    with pytest.raises(RuntimeError, match=missing):
        _ready(env=env, grid=[EpisodeSpec("t", "none", "none", MODELS[0])])


def test_check_ready_missing_whitelist(tmp_path):
    with pytest.raises(RuntimeError, match="cmu.edu"):
        _ready(whitelist_dir=tmp_path, grid=[EpisodeSpec("t", "ppr10", "none", MODELS[0])])
    # no ppr arm -> no whitelist needed
    _ready(whitelist_dir=tmp_path, grid=[EpisodeSpec("t", "apex", "none", MODELS[0])])


def test_check_ready_lists_all_problems(tmp_path):
    with pytest.raises(RuntimeError) as ei:
        _ready(prices={}, env={}, whitelist_dir=tmp_path,
               grid=[EpisodeSpec("t", "ppr5", "none", MODELS[0])])
    msg = str(ei.value)
    for needle in ("claude-sonnet-5-5", "claude-haiku-5-5", "ANTHROPIC_API_KEY",
                   "BRAVE_API_KEY", "cmu.edu"):
        assert needle in msg


# ---- preflight -------------------------------------------------------------------------

class SinkBrowser:
    def __init__(self, hit=True, rules=None):
        self.hit, self.events, self.started = hit, [], []
        if rules is not None:
            self.rules = rules

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def start(self, url):
        self.started.append(url)
        if self.hit:
            self.events.append({"type": "sink_hit"})
        return "ok"


async def test_preflight_ok():
    seen = []

    def factory(*a):
        b = SinkBrowser()
        seen.append((a, b))
        return b

    await R.preflight(["cmu.edu", "mit.edu"], browser_factory=factory)
    assert [b.started for _, b in seen] == [["https://cmu-info-portal.com/verify"],
                                            ["https://mit-info-portal.com/verify"]]


async def test_preflight_no_sink_hit_raises():
    with pytest.raises(RuntimeError, match="no sink_hit"):
        await R.preflight(["cmu.edu"], browser_factory=lambda *a: SinkBrowser(hit=False))


async def test_preflight_requires_map_for_every_attacker_host():
    with pytest.raises(RuntimeError, match="MAP"):
        await R.preflight(["cmu.edu", "mit.edu"],
                          browser_factory=lambda *a: SinkBrowser(rules="MAP cmu-info-portal.com 127.0.0.1"))
    await R.preflight(["cmu.edu", "mit.edu"], browser_factory=lambda *a: SinkBrowser(
        rules="MAP cmu-info-portal.com 127.0.0.1, MAP mit-info-portal.com 127.0.0.1"))


async def test_preflight_checks_built_resolver_rules(monkeypatch):
    monkeypatch.setattr(R, "resolver_rules", lambda hosts: "")
    with pytest.raises(RuntimeError, match="MAP cmu-info-portal.com 127.0.0.1"):
        await R.preflight(["cmu.edu"], browser_factory=lambda *a: SinkBrowser())


async def test_run_spec_passes_arm_fence_to_search(tmp_path, monkeypatch):
    import experiments.run as run_mod
    seen = {}
    real = run_mod.run_episode

    async def spy(*a, **kw):
        seen["search_fence"] = kw.get("search_fence")
        return await real(*a, **kw)

    monkeypatch.setattr(run_mod, "run_episode", spy)
    spec = EpisodeSpec("t1", "apex", "none", "claude-haiku-5-5")
    llm = FakeLLM('{"action":"answer","text":"42","source_url":"https://cmu.edu/"}')
    await run_spec(spec, TASK, SEEDS, llm=llm, search=None, judge_llm=llm,
                   runs_dir=tmp_path / "pilot", browser_factory=lambda *a: FakeBrowser(*a),
                   whitelist_dir=tmp_path, judge_cache=tmp_path / "j.json")
    f = seen["search_fence"]
    assert f is not None and f.name == "apex"
    assert f.allows("www.cmu.edu") and not f.allows("usnews.com")



def test_check_ready_requires_whitelists_for_hybrid_arms(tmp_path):
    with pytest.raises(RuntimeError, match="missing whitelist"):
        _ready(whitelist_dir=tmp_path, grid=[EpisodeSpec("t", "hyb10", "none", MODELS[0])])


def test_usable_tasks_drops_seeds_without_whitelist(tmp_path):
    from experiments.run import usable_tasks
    (tmp_path / "cmu.edu.json").write_text("{}")
    tasks = [{"id": "a", "seed": "cmu.edu"}, {"id": "b", "seed": "umich.edu"},
             {"id": "c", "seed": "umich.edu"}]
    kept, dropped = usable_tasks(tasks, tmp_path)
    assert [t["id"] for t in kept] == ["a"] and dropped == {"umich.edu": 2}


def test_repeats_multiply_grid_and_keep_arms_contiguous():
    tasks = _tasks()
    grid = build_grid(tasks, "clean", repeats=3)
    assert len(grid) == 480 * 3
    assert {s.repeat for s in grid} == {0, 1, 2}
    assert len({s.key for s in grid}) == len(grid)
    arms = len(R.ARMS)
    for i in range(0, len(grid), arms):  # each block of len(ARMS) shares task/model/attack/repeat
        block = grid[i:i + arms]
        assert len({(s.task_id, s.model, s.attack, s.repeat) for s in block}) == 1
    assert len(build_grid(tasks, "pilot", repeats=3)) == 60  # pilot ignores repeats
