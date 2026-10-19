"""Cached PPR whitelists per seed and the arm -> Fence factory."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from agent.fence import Fence
from ppr import PPRConfig
from related_domains import CrawlConfig, RankedHost, rank_domains

# hybK = apex + top-k external hosts by PPR (main arms); ppr10 = top-k overall (original form,
# kept as a reported comparison). See spec §2 "PPR fence semantics".
ARMS = ("none", "apex", "hyb5", "hyb10", "hyb20", "ppr10")


class WhitelistError(Exception):
    """Crawl failed or produced too small a graph."""


def build_whitelist(seed: str, aliases: list[str], out_dir: Path) -> Path:
    """Crawl seed, rank hosts with PPR, write <out_dir>/<seed>.json."""
    crawl_cfg = CrawlConfig(seed, max_pages_total=500, max_pages_per_host=100,
                            max_depth=3, politeness_delay=0.5, alias_domains=list(aliases))
    ppr_cfg = PPRConfig(damping=0.85, seed_weight=0.9, subdomain_weight=0.1)
    try:
        ranking, stats = asyncio.run(rank_domains(seed, crawl_cfg, ppr_cfg))
    except Exception as e:
        raise WhitelistError(f"crawl of {seed} failed: {e}") from e
    if len(ranking) < 2:
        raise WhitelistError(f"crawl of {seed} found only {len(ranking)} host(s)")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{seed}.json"
    path.write_text(json.dumps({
        "seed": seed,
        "aliases": list(aliases),
        "crawl_date": date.today().isoformat(),
        "crawl_stats": stats,
        "ranking": [{"host": r.host, "score": r.score, "is_first_party": r.is_first_party}
                    for r in ranking],
    }, indent=2))
    return path


def load_ranking(path: Path) -> list[RankedHost]:
    data = json.loads(Path(path).read_text())
    return [RankedHost(r["host"], r["score"], r["is_first_party"]) for r in data["ranking"]]


def fence_for(arm: str, seed: str, aliases: list[str], whitelist_dir: Path) -> Fence:
    if arm == "none":
        return Fence.none()
    if arm == "apex":
        return Fence.apex(seed, aliases)
    if arm in ARMS:
        ranking = load_ranking(Path(whitelist_dir) / f"{seed}.json")
        k = int(arm[3:])
        if arm.startswith("hyb"):
            return Fence.hybrid(seed, aliases, ranking, k)
        return Fence.ppr(ranking, k)
    raise ValueError(f"unknown arm: {arm}")


def load_seeds(path: Path) -> list[dict]:
    return json.loads(Path(path).read_text())


def main(argv: list[str]) -> None:
    seeds_path, out_dir = Path(argv[0]), Path(argv[1])
    for s in load_seeds(seeds_path):
        try:
            print(build_whitelist(s["seed"], s["aliases"], out_dir))
        except WhitelistError as e:
            print(f"SKIP {s['seed']}: {e}")


if __name__ == "__main__":
    main(sys.argv[1:])
