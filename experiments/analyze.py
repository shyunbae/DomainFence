"""Analysis of agent-fence runs: grouped metrics with task-level bootstrap CIs, pilot report, plot."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from agent.metrics import episode_metrics, partner_recall
from agent.tasks import load_tasks
from agent.whitelists import load_ranking, load_seeds
from experiments.run import MODELS, RUNS_ROOT, SEEDS_PATH, TASKS_PATH, WHITELIST_DIR, _file_cost, build_grid

RESULTS_DIR = Path("experiments") / "results"
SUMMARY_METRICS = ("success", "attack_attempted", "attack_reached", "misinfo_adopted",
                   "wrong_source", "grounded_source", "off_ecosystem_navs", "steps", "cost_usd")


def load_rows(runs_dir: Path, tasks: list[dict], seeds: list[dict]) -> list[dict]:
    """One row per graded, non-infra episode file under runs_dir."""
    by_id = {t["id"]: t for t in tasks}
    aliases = {s["seed"]: s["aliases"] for s in seeds}
    rows = []
    for path in sorted(Path(runs_dir).rglob("*.json")):
        data = json.loads(path.read_text())
        if data.get("end_reason") == "infra_error" or "grade_error" in data:
            continue
        task = by_id[data["task_id"]]
        row = {"task_id": data["task_id"], "arm": data["arm"], "attack": data["attack"],
               "model": data["model"], "task_type": task["type"]}
        row.update(episode_metrics(data, task, aliases.get(task["seed"], []), data["correct"]))
        row["judge_cost_usd"] = data.get("judge_cost_usd") or 0.0
        row["end_reason"] = data["end_reason"]
        rows.append(row)
    return rows


def _num(v) -> float:
    return float(v)


def summarize(rows: list[dict], by: tuple[str, ...], metrics: tuple[str, ...],
              n_boot: int = 2000, seed: int = 0) -> list[dict]:
    """Per-group metric means with 95% bootstrap CIs resampling task ids."""
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault(tuple(r[b] for b in by), []).append(r)
    out = []
    for key in sorted(groups):
        grows = groups[key]
        rec = dict(zip(by, key))
        task_ids = sorted({r["task_id"] for r in grows})
        for m in metrics:
            sums = np.zeros(len(task_ids))
            counts = np.zeros(len(task_ids))
            pos = {t: i for i, t in enumerate(task_ids)}
            for r in grows:
                if r[m] is not None:
                    sums[pos[r["task_id"]]] += _num(r[m])
                    counts[pos[r["task_id"]]] += 1
            n = int(counts.sum())
            if n == 0:
                rec.update({f"{m}_mean": None, f"{m}_low": None, f"{m}_high": None, f"{m}_n": 0})
                continue
            rng = np.random.default_rng(seed)
            idx = rng.integers(0, len(task_ids), size=(n_boot, len(task_ids)))
            c = counts[idx].sum(axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                means = np.where(c > 0, sums[idx].sum(axis=1) / np.where(c > 0, c, 1), np.nan)
            low, high = np.nanpercentile(means, [2.5, 97.5])
            rec.update({f"{m}_mean": float(sums.sum() / n), f"{m}_low": float(low),
                        f"{m}_high": float(high), f"{m}_n": n})
        out.append(rec)
    return out


def load_raw(runs_dir: Path) -> list[dict]:
    """Every trajectory file under runs_dir (infra_error, retried and grade_error included)."""
    out = []
    for path in sorted(Path(runs_dir).rglob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def pilot_report(rows: list[dict], tasks: list[dict], raw: list[dict]) -> dict:
    """Token stats from graded rows; cost stats and projection from all raw pilot files.

    cost_mean is the mean total spend per file (agent + judge + prior attempt), so failed
    and retried episodes are priced in; the projection therefore needs no separate judge term.
    """
    rep = {"input_tokens_mean": {}, "input_tokens_p90": {}, "cost_mean": {},
           "end_reasons": {}, "projected_full_usd": 0.0}
    grid = build_grid(tasks, "clean") + build_grid(tasks, "attack")
    projected = 0.0
    for model in MODELS:
        mrows = [r for r in rows if r["model"] == model]
        mraw = [r for r in raw if r["model"] == model]
        if not mrows or not mraw:
            raise ValueError(f"no pilot rows for model {model}")
        toks = [r["input_tokens"] for r in mrows]
        rep["input_tokens_mean"][model] = float(np.mean(toks))
        rep["input_tokens_p90"][model] = float(np.percentile(toks, 90))
        rep["cost_mean"][model] = float(np.mean([_file_cost(r) for r in mraw]))
        projected += rep["cost_mean"][model] * sum(1 for s in grid if s.model == model)
    for r in rows:
        rep["end_reasons"][r["end_reason"]] = rep["end_reasons"].get(r["end_reason"], 0) + 1
    rep["judge_cost_mean"] = float(np.mean([float(r.get("judge_cost_usd") or 0.0) for r in raw]))
    rep["projected_full_usd"] = projected
    return rep


def _write_csv(path: Path, records: list[dict]) -> None:
    fields: list[str] = []
    for r in records:
        fields += [k for k in r if k not in fields]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(records)


def plot_utility_vs_safety(rows: list[dict], path: Path, n_boot: int = 2000) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    clean = {(g["arm"], g["model"]): g for g in summarize(
        [r for r in rows if r["attack"] == "none"], ("arm", "model"), ("success",), n_boot)}
    att = {(g["arm"], g["model"]): g for g in summarize(
        [r for r in rows if r["attack"] != "none"], ("arm", "model"), ("attack_reached",), n_boot)}
    fig, ax = plt.subplots(figsize=(6, 5))
    for key in sorted(set(clean) & set(att)):
        c, a = clean[key], att[key]
        if c["success_mean"] is None or a["attack_reached_mean"] is None:
            continue
        x, y = c["success_mean"], a["attack_reached_mean"]
        ax.errorbar(x, y, xerr=[[x - c["success_low"]], [c["success_high"] - x]],
                    yerr=[[y - a["attack_reached_low"]], [a["attack_reached_high"] - y]],
                    fmt="o", capsize=3)
        ax.annotate(f"{key[0]}/{key[1].split('-')[1]}", (x, y), fontsize=7,
                    xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("Success rate on clean episodes")
    ax.set_ylabel("Attack-reached rate")
    ax.set_title("Utility vs safety")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_partner_recall(tasks: list[dict], whitelist_dir: Path, path: Path) -> bool:
    seeds = {t["seed"] for t in tasks}
    files = {s: Path(whitelist_dir) / f"{s}.json" for s in seeds}
    if not all(p.exists() for p in files.values()):
        print(f"partner recall skipped: whitelists missing in {whitelist_dir}")
        return False
    rankings = {s: load_ranking(p) for s, p in files.items()}
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fence", "k", "partner_recall"])
        for kind in ("hyb", "ppr"):
            for k in (5, 10, 20):
                w.writerow([kind, k, partner_recall(tasks, rankings, k, kind=kind)])
    return True


def full(runs_root: Path, tasks: list[dict], seeds: list[dict], out_dir: Path,
         whitelist_dir: Path = WHITELIST_DIR, n_boot: int = 2000) -> None:
    """Write summary.csv, utility_vs_safety.png and (if whitelists exist) partner_recall.csv."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for phase in ("clean", "attack"):
        if (Path(runs_root) / phase).is_dir():
            rows += load_rows(Path(runs_root) / phase, tasks, seeds)
    records = [{"grouping": "arm_model_attack", **g}
               for g in summarize(rows, ("arm", "model", "attack"), SUMMARY_METRICS, n_boot)]
    clean = [r for r in rows if r["attack"] == "none"]
    records += [{"grouping": "arm_task_type_clean", **g}
                for g in summarize(clean, ("arm", "task_type"), SUMMARY_METRICS, n_boot)]
    _write_csv(out_dir / "summary.csv", records)
    plot_utility_vs_safety(rows, out_dir / "utility_vs_safety.png", n_boot)
    write_partner_recall(tasks, whitelist_dir, out_dir / "partner_recall.csv")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m experiments.analyze")
    ap.add_argument("command", choices=("pilot", "full"))
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)
    from experiments.run import usable_tasks

    tasks, dropped = usable_tasks(load_tasks(TASKS_PATH), WHITELIST_DIR)
    if dropped:
        print(f"excluded tasks for seeds without a whitelist: {dropped}")
    seeds = load_seeds(SEEDS_PATH)
    if args.command == "pilot":
        rows = load_rows(RUNS_ROOT / "pilot", tasks, seeds)
        print(json.dumps(pilot_report(rows, tasks, load_raw(RUNS_ROOT / "pilot")), indent=2))
    else:
        full(RUNS_ROOT, tasks, seeds, RESULTS_DIR)


if __name__ == "__main__":
    main()
