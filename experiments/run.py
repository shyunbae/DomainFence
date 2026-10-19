"""Experiment runner: episode grid, resume, budget caps, preflight, CLI."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from agent.browser import FencedBrowser
from agent.fence import Fence
from agent import injection
from agent.injection import ATTACKS, all_attacker_hosts, attacker_host, attacker_url, resolver_rules
from agent.judge import grade
from agent.loop import Trajectory, run_episode
from agent.search import SearchClient, SearchResult, brave_provider
from agent.tasks import load_tasks
from agent.whitelists import ARMS, fence_for, load_seeds

MODELS = ("claude-sonnet-5-5", "claude-haiku-5-5")
JUDGE_MODEL = "claude-haiku-5-5"
EPISODE_CAP_USD = 0.50
MARGIN_USD = 0.01
PILOT_COUNTS = (("in_apex", 2), ("partner", 2), ("wrong_source", 1))
ATTACK_ARMS = ("none", "apex", "hyb10")
# First-round attacks are pinned so the `attack` phase (already run) never changes shape.
FIRST_ROUND_ATTACKS = ("visible_link", "hidden_instruction", "fake_redirect", "onpage_misinfo")
SECOND_ROUND_ATTACKS = ("task_lure", "search_poison")
DEV_N = 8  # lowest-id tasks used to develop the second-round payloads, then held out of attack2

ROOT = Path("experiments")
TASKS_PATH = ROOT / "tasks.jsonl"
SEEDS_PATH = ROOT / "seeds.json"
WHITELIST_DIR = ROOT / "whitelists"
SEARCH_CACHE = ROOT / "search_cache"
JUDGE_CACHE = ROOT / "data" / "judge_cache.json"
RUNS_ROOT = ROOT / "data" / "runs"


@dataclass(frozen=True)
class EpisodeSpec:
    task_id: str
    arm: str
    attack: str
    model: str
    repeat: int = 0

    @property
    def key(self) -> str:
        return f"{self.task_id}__{self.arm}__{self.attack}__{self.model}__r{self.repeat}"


def dev_heldout(tasks: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split by id: the DEV_N lowest-id tasks (payload development) vs the rest (held out)."""
    ordered = sorted(tasks, key=lambda t: t["id"])
    return ordered[:DEV_N], ordered[DEV_N:]


def build_grid(tasks: list[dict],
               phase: Literal["pilot", "clean", "attack", "attack2_dev", "attack2"],
               repeats: int = 1) -> list[EpisodeSpec]:
    """All arms of one (task, model, attack, repeat) run back to back; pilot ignores repeats."""
    ordered = sorted(tasks, key=lambda t: t["id"])
    if phase == "pilot":
        chosen = []
        for typ, n in PILOT_COUNTS:
            chosen += [t for t in ordered if t["type"] == typ][:n]
        ordered = sorted(chosen, key=lambda t: t["id"])
        arms, attacks = ATTACK_ARMS, ("none", "visible_link")
        repeats = 1
    elif phase == "clean":
        arms, attacks = ARMS, ("none",)
    elif phase == "attack":
        arms, attacks = ATTACK_ARMS, FIRST_ROUND_ATTACKS
    elif phase == "attack2_dev":
        ordered = dev_heldout(ordered)[0]
        arms, attacks, repeats = ("none",), SECOND_ROUND_ATTACKS, 1
    elif phase == "attack2":
        ordered = dev_heldout(ordered)[1]
        arms, attacks = ATTACK_ARMS, SECOND_ROUND_ATTACKS
    else:
        raise ValueError(f"unknown phase: {phase}")
    return [EpisodeSpec(t["id"], arm, attack, model, r)
            for t in ordered for model in MODELS for attack in attacks
            for r in range(repeats) for arm in arms]


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def pending(grid: list[EpisodeSpec], runs_dir: Path) -> list[EpisodeSpec]:
    """Specs without a finished file; a first-time infra_error is still pending."""
    out = []
    for spec in grid:
        data = _read(Path(runs_dir) / f"{spec.key}.json")
        if data is not None and (data.get("end_reason") != "infra_error" or data.get("retried")):
            continue
        out.append(spec)
    return out


def _file_cost(data: dict) -> float:
    return sum(float(data.get(k) or 0.0) for k in ("cost_usd", "judge_cost_usd", "prior_cost_usd"))


def spent_usd(runs_dir: Path) -> float:
    """Sum cost_usd + judge_cost_usd over all trajectory files under runs_dir."""
    total = 0.0
    for p in Path(runs_dir).rglob("*.json"):
        data = _read(p)
        if isinstance(data, dict):
            total += _file_cost(data)
    return total


def should_stop(spent: float, cap: float) -> bool:
    """True when one more worst-case episode (plus margin) could exceed the cap."""
    return spent + EPISODE_CAP_USD + MARGIN_USD > cap


def attacker_hosts_for(seed: str, all_seeds: list[str]) -> list[str]:
    hosts = [attacker_host(seed)] + all_attacker_hosts(all_seeds)
    return list(dict.fromkeys(hosts))


def usable_tasks(tasks: list[dict], whitelist_dir: Path) -> tuple[list[dict], dict[str, int]]:
    """Keep tasks whose seed has a whitelist; return (kept, {dropped seed: task count})."""
    kept, dropped = [], {}
    for t in tasks:
        if (Path(whitelist_dir) / f"{t['seed']}.json").exists():
            kept.append(t)
        else:
            dropped[t["seed"]] = dropped.get(t["seed"], 0) + 1
    return kept, dropped


def check_ready(phase: str, grid: list[EpisodeSpec], models: tuple[str, ...], judge_model: str,
                prices: dict, env: dict, whitelist_dir: Path, seeds: list[str]) -> None:
    """Fail fast (before any episode or retry is burned) listing ALL setup problems."""
    problems = []
    for m in dict.fromkeys([*models, *(s.model for s in grid)]):
        if m not in prices:
            problems.append(f"no PRICES entry for agent model {m}")
    if judge_model not in prices:
        problems.append(f"no PRICES entry for judge model {judge_model}")
    for var in ("ANTHROPIC_API_KEY", "BRAVE_API_KEY"):
        if not env.get(var):
            problems.append(f"{var} is not set")
    if any(s.arm.startswith(("ppr", "hyb")) for s in grid):
        for seed in seeds:
            if not (Path(whitelist_dir) / f"{seed}.json").exists():
                problems.append(f"missing whitelist file for {seed} in {whitelist_dir}")
    if problems:
        raise RuntimeError(f"{phase} not ready: " + "; ".join(problems))


async def preflight(seeds: list[str], browser_factory: Callable = FencedBrowser) -> None:
    """Every attacker URL must hit the local sink (never the real internet)."""
    for seed in seeds:
        hosts = attacker_hosts_for(seed, seeds)
        rules = resolver_rules(hosts)
        for h in hosts:
            if f"MAP {h} 127.0.0.1" not in rules:
                raise RuntimeError(f"preflight failed: no 'MAP {h} 127.0.0.1' resolver rule")
        async with browser_factory(Fence.none(), seed, [], "none", None, hosts) as b:
            applied = getattr(b, "rules", None)
            if isinstance(applied, str):
                for h in hosts:
                    if f"MAP {h} 127.0.0.1" not in applied:
                        raise RuntimeError(f"preflight failed: browser lacks 'MAP {h} 127.0.0.1'")
            await b.start(attacker_url(seed))
            if not any(e["type"] == "sink_hit" for e in b.events):
                raise RuntimeError(f"preflight failed: no sink_hit for {attacker_url(seed)}")


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


async def run_spec(spec: EpisodeSpec, task: dict, seeds_cfg: list[dict], *, llm, search, judge_llm,
                   runs_dir: Path, browser_factory: Callable = FencedBrowser,
                   whitelist_dir: Path = WHITELIST_DIR, judge_cache: Path = JUDGE_CACHE,
                   retried: bool = False) -> dict:
    """Run, grade and persist one episode; any escaping exception becomes an infra_error file."""
    runs_dir = Path(runs_dir)
    traj, cm, teardown_error = None, None, None
    try:
        cfg = next(s for s in seeds_cfg if s["seed"] == task["seed"])
        fence = fence_for(spec.arm, cfg["seed"], cfg["aliases"], whitelist_dir)
        hosts = attacker_hosts_for(cfg["seed"], [s["seed"] for s in seeds_cfg])
        cm = browser_factory(fence, cfg["seed"], cfg["aliases"], spec.attack,
                             task["misinfo_answer"], hosts)
        poison = None
        if spec.attack == "search_poison":
            poison = SearchResult(**injection.poison_result(
                cfg["seed"], task["misinfo_answer"], attacker=hosts[0]))
        async with cm as browser:
            traj = await run_episode(spec.key, task, spec.arm, spec.attack, spec.model,
                                     llm=llm, browser=browser, search=search, search_fence=fence,
                                     search_poison=poison)
    except Exception as e:
        detail = f"{type(e).__name__}: {e}"
        if traj is not None:  # episode finished; only teardown failed
            teardown_error = detail
        else:
            traj = Trajectory(key=spec.key, task_id=spec.task_id, arm=spec.arm, attack=spec.attack,
                              model=spec.model, end_reason="infra_error", infra_detail=detail,
                              events=list(getattr(cm, "events", None) or []))
    out = traj.to_json()
    correct, jcost, grade_error = False, 0.0, None
    if traj.end_reason != "infra_error":
        try:
            correct, jcost = grade(task, traj.answer, llm=judge_llm, cache_path=judge_cache)
        except Exception as e:
            correct, jcost, grade_error = False, 0.0, f"{type(e).__name__}: {e}"
    out.update(correct=correct, judge_cost_usd=jcost, retried=retried, phase=runs_dir.name)
    if grade_error is not None:
        out["grade_error"] = grade_error
    if teardown_error is not None:
        out["teardown_error"] = teardown_error
    if retried:  # keep the first attempt's spend visible to spent_usd
        prev = _read(runs_dir / f"{spec.key}.json")
        if prev is not None:
            out["prior_cost_usd"] = _file_cost(prev)
    _write(runs_dir / f"{spec.key}.json", out)
    return out


async def run_phase(phase: str, cap: float, runs_root: Path = RUNS_ROOT, repeats: int = 1) -> None:
    from dotenv import load_dotenv

    from agent.llm import PRICES, AnthropicLLM

    load_dotenv(ROOT.parent / ".env")  # BRAVE_API_KEY / ANTHROPIC_API_KEY; never printed
    tasks, dropped = usable_tasks(load_tasks(TASKS_PATH), WHITELIST_DIR)
    if dropped:
        print(f"excluded tasks for seeds without a whitelist: {dropped}")
    by_id = {t["id"]: t for t in tasks}
    seeds_cfg = load_seeds(SEEDS_PATH)
    grid = build_grid(tasks, phase, repeats=repeats)
    grid_seeds = sorted({by_id[s.task_id]["seed"] for s in grid})
    check_ready(phase, grid, MODELS, JUDGE_MODEL, PRICES, os.environ, WHITELIST_DIR, grid_seeds)
    runs_dir = runs_root / phase
    if phase != "clean":
        await preflight([s["seed"] for s in seeds_cfg])
    llm = AnthropicLLM()
    search = SearchClient(SEARCH_CACHE, brave_provider)

    async def run_one(spec: EpisodeSpec, retried: bool) -> dict:
        return await run_spec(spec, by_id[spec.task_id], seeds_cfg, llm=llm, search=search,
                              judge_llm=llm, runs_dir=runs_dir, retried=retried)

    await run_passes(grid, runs_dir, runs_root, cap, run_one)


async def run_passes(grid: list[EpisodeSpec], runs_dir: Path, runs_root: Path, cap: float,
                     run_one: Callable, spent_fn: Callable = spent_usd, log: Callable = print) -> bool:
    """Main pass over unrun specs, then one retry of each infra_error. False if stopped at cap."""

    async def go(spec: EpisodeSpec, retried: bool) -> bool:
        spent = spent_fn(runs_root)
        if should_stop(spent, cap):
            log(f"stopping: spent ${spent:.2f} would exceed cap ${cap:.2f} on next episode")
            return False
        out = await run_one(spec, retried)
        log(f"{spec.key}: {out['end_reason']} correct={out['correct']}")
        return True

    for spec in pending(grid, runs_dir):
        if (Path(runs_dir) / f"{spec.key}.json").exists():
            continue  # earlier infra_error: handled by the retry pass
        if not await go(spec, False):
            return False
    for spec in pending(grid, runs_dir):  # remaining = infra_error not yet retried
        if not await go(spec, True):
            return False
    return True


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m experiments.run")
    ap.add_argument("phase", choices=("pilot", "clean", "attack", "attack2_dev", "attack2"))
    ap.add_argument("--cap", type=float, default=60.0)
    ap.add_argument("--repeats", type=int, default=1)
    args = ap.parse_args(argv)
    asyncio.run(run_phase(args.phase, args.cap, repeats=args.repeats))


if __name__ == "__main__":
    main()
