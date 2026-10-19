import json
from pathlib import Path

import pytest

from experiments import analyze
from experiments.run import MODELS, build_grid


def row(task, **kw):
    base = dict(task_id=task, arm="apex", attack="none", model="m", task_type="in_apex",
                success=True, attack_attempted=False, attack_reached=False,
                misinfo_adopted=None, wrong_source=None, off_ecosystem_navs=0, steps=3,
                input_tokens=100, output_tokens=10, cost_usd=0.1, judge_cost_usd=0.01,
                end_reason="answered")
    base.update(kw)
    return base


M = ("success", "wrong_source")


def test_summarize_means_and_ci():
    rows = [row("a", success=True), row("a", success=False), row("b", success=True),
            row("c", success=False, wrong_source=True), row("c", wrong_source=False)]
    out = analyze.summarize(rows, ("arm",), M, n_boot=200, seed=1)
    assert len(out) == 1
    g = out[0]
    assert g["arm"] == "apex"
    assert g["success_mean"] == pytest.approx(3 / 5)
    assert g["success_n"] == 5
    assert g["success_low"] <= g["success_mean"] <= g["success_high"]
    # None values ignored
    assert g["wrong_source_mean"] == pytest.approx(0.5)
    assert g["wrong_source_n"] == 2


def test_summarize_all_none_and_sorted_groups():
    rows = [row("a", arm="z"), row("a", arm="b", wrong_source=True)]
    out = analyze.summarize(rows, ("arm",), ("wrong_source",), n_boot=50)
    assert [g["arm"] for g in out] == ["b", "z"]
    z = out[1]
    assert z["wrong_source_mean"] is None and z["wrong_source_low"] is None
    assert z["wrong_source_high"] is None and z["wrong_source_n"] == 0


def test_summarize_deterministic_and_task_level():
    rows = [row(t, success=(i % 2 == 0)) for i, t in enumerate("abcdef") for _ in range(2)]
    a = analyze.summarize(rows, ("arm",), ("success",), n_boot=300, seed=7)
    b = analyze.summarize(rows, ("arm",), ("success",), n_boot=300, seed=7)
    assert a == b
    # single task: resampling cannot vary
    one = analyze.summarize([row("a"), row("a", success=False)], ("arm",), ("success",), n_boot=50)[0]
    assert one["success_low"] == one["success_high"] == 0.5


def _tasks():
    return [{"id": f"t{i}", "seed": "x.edu", "type": typ, "partner_domains": ["p.org"],
             "misinfo_answer": "z"}
            for i, typ in enumerate(["in_apex"] * 2 + ["partner"] * 2 + ["wrong_source"])]


def raw(model, cost, judge=0.0, prior=0.0, end_reason="answer"):
    return dict(model=model, cost_usd=cost, judge_cost_usd=judge, prior_cost_usd=prior,
                end_reason=end_reason)


def test_pilot_report_projection():
    tasks = _tasks()
    rows = []
    for m, cost in zip(MODELS, (0.2, 0.1)):
        for i, toks in enumerate((100, 200, 300, 400, 500)):
            rows.append(row(f"t{i}", model=m, input_tokens=toks, cost_usd=cost,
                            judge_cost_usd=0.01))
    rows.append(row("t0", model=MODELS[0], end_reason="max_steps", input_tokens=100,
                    cost_usd=0.2, judge_cost_usd=0.01))
    # raw files include an infra_error (no graded row) and a retried file with prior cost
    files = ([raw(MODELS[0], 0.2, 0.01)] * 4
             + [raw(MODELS[0], 0.1, 0.0, 0.2, end_reason="infra_error"),
                raw(MODELS[0], 0.4, 0.0, 0.0, end_reason="infra_error")]
             + [raw(MODELS[1], 0.09, 0.01)] * 3)
    rep = analyze.pilot_report(rows, tasks, files)
    assert rep["input_tokens_mean"][MODELS[0]] == pytest.approx((1500 + 100) / 6)
    assert rep["input_tokens_p90"][MODELS[1]] == pytest.approx(460.0)
    m0 = (4 * 0.21 + 0.3 + 0.4) / 6
    assert rep["cost_mean"][MODELS[0]] == pytest.approx(m0)
    assert rep["cost_mean"][MODELS[1]] == pytest.approx(0.1)
    assert rep["end_reasons"]["max_steps"] == 1
    per_model = len(build_grid(tasks, "clean")) // 2 + len(build_grid(tasks, "attack")) // 2
    assert rep["projected_full_usd"] == pytest.approx((m0 + 0.1) * per_model)


def test_pilot_report_missing_model():
    with pytest.raises(ValueError, match=MODELS[1]):
        analyze.pilot_report([row("t0", model=MODELS[0])], _tasks(), [raw(MODELS[0], 0.1)])
    with pytest.raises(ValueError, match=MODELS[1]):
        analyze.pilot_report([row("t0", model=MODELS[0]), row("t0", model=MODELS[1])],
                             _tasks(), [raw(MODELS[0], 0.1)])


def test_load_raw_reads_all_files(tmp_path):
    _write_traj(tmp_path, "ok")
    _write_traj(tmp_path, "infra", end_reason="infra_error")
    assert len(analyze.load_raw(tmp_path)) == 2


def _write_traj(d: Path, key, **kw):
    t = dict(key=key, task_id="t0", arm="apex", attack="none", model=MODELS[0],
             steps=[{"url": "https://x.edu/"}], answer="a", source_url="https://x.edu/p",
             end_reason="answered", infra_detail=None, events=[], input_tokens=10,
             output_tokens=5, cost_usd=0.05, correct=True, judge_cost_usd=0.001,
             retried=False, phase="clean")
    t.update(kw)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{key}.json").write_text(json.dumps(t))


def test_load_rows_filters(tmp_path):
    tasks = [{"id": "t0", "seed": "x.edu", "type": "in_apex", "partner_domains": [],
              "misinfo_answer": "z"}]
    seeds = [{"seed": "x.edu", "aliases": ["xx.edu"]}]
    _write_traj(tmp_path, "ok")
    _write_traj(tmp_path, "infra", end_reason="infra_error")
    _write_traj(tmp_path, "bad", grade_error="boom")
    rows = analyze.load_rows(tmp_path, tasks, seeds)
    assert len(rows) == 1
    r = rows[0]
    assert r["task_type"] == "in_apex" and r["success"] is True
    assert r["judge_cost_usd"] == 0.001 and r["end_reason"] == "answered"
    assert r["wrong_source"] is False


def test_full_writes_outputs(tmp_path):
    tasks = [{"id": f"t{i}", "seed": "x.edu", "type": "in_apex", "partner_domains": [],
              "misinfo_answer": "z"} for i in range(3)]
    seeds = [{"seed": "x.edu", "aliases": []}]
    runs = tmp_path / "runs"
    for i in range(3):
        for arm in ("apex", "ppr10"):
            _write_traj(runs / "clean", f"c{i}{arm}", task_id=f"t{i}", arm=arm)
            _write_traj(runs / "attack", f"a{i}{arm}", task_id=f"t{i}", arm=arm,
                        attack="visible_link", correct=False,
                        events=[{"type": "sink_hit", "attacker": True}])
    out = tmp_path / "out"
    analyze.full(runs, tasks, seeds, out, tmp_path / "nowhitelists", n_boot=50)
    assert (out / "summary.csv").stat().st_size > 0
    assert (out / "utility_vs_safety.png").read_bytes()[:4] == b"\x89PNG"
    assert not (out / "partner_recall.csv").exists()
