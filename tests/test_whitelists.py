import json

import pytest

import agent.whitelists as wl
from agent.whitelists import WhitelistError, build_whitelist, fence_for, load_ranking, load_seeds
from related_domains import RankedHost

R = [RankedHost("cmu.edu", .5, True), RankedHost("cs.cmu.edu", .2, True),
     RankedHost("gostanford.com", .1, False), RankedHost("facebook.com", .05, False)]


def _patch(monkeypatch, ranking):
    async def fake(seed, crawl_cfg, ppr_cfg):
        return ranking, {"pages_crawled": 10}
    monkeypatch.setattr(wl, "rank_domains", fake)


def test_build_and_load_roundtrip(tmp_path, monkeypatch):
    _patch(monkeypatch, R)
    path = build_whitelist("cmu.edu", [], tmp_path)
    assert path.name == "cmu.edu.json"
    assert load_ranking(path) == R
    data = json.loads(path.read_text())
    assert data["crawl_date"] and data["crawl_stats"]["pages_crawled"] == 10
    assert data["seed"] == "cmu.edu" and data["aliases"] == []


def test_build_raises_on_tiny_graph(tmp_path, monkeypatch):
    _patch(monkeypatch, [RankedHost("cmu.edu", 1.0, True)])
    with pytest.raises(WhitelistError):
        build_whitelist("cmu.edu", [], tmp_path)


def test_build_raises_when_crawl_fails(tmp_path, monkeypatch):
    async def boom(seed, crawl_cfg, ppr_cfg):
        raise RuntimeError("net down")
    monkeypatch.setattr(wl, "rank_domains", boom)
    with pytest.raises(WhitelistError):
        build_whitelist("cmu.edu", [], tmp_path)


def test_fence_for_arms(tmp_path, monkeypatch):
    _patch(monkeypatch, R)
    build_whitelist("cmu.edu", [], tmp_path)
    assert fence_for("ppr10", "cmu.edu", [], tmp_path).name == "ppr10"
    assert fence_for("apex", "cmu.edu", [], tmp_path).allows("ml.cmu.edu")
    assert fence_for("none", "cmu.edu", [], tmp_path).allows("x.com")
    with pytest.raises(ValueError):
        fence_for("ppr", "cmu.edu", [], tmp_path)


def test_load_seeds():
    seeds = load_seeds(wl.Path("experiments/seeds.json"))
    assert len(seeds) == 8 and seeds[0] == {"seed": "cmu.edu", "aliases": []}


def test_arms_include_hybrid_and_original_ppr10():
    assert wl.ARMS == ("none", "apex", "hyb5", "hyb10", "hyb20", "ppr10")


def test_fence_for_hybrid(tmp_path, monkeypatch):
    async def fake(seed, crawl_cfg, ppr_cfg):
        return [RankedHost("cmu.edu", .6, True), RankedHost("go.com", .3, False),
                RankedHost("x.com", .1, False)], {"pages_crawled": 3}
    monkeypatch.setattr(wl, "rank_domains", fake)
    build_whitelist("cmu.edu", [], tmp_path)
    f = fence_for("hyb10", "cmu.edu", [], tmp_path)
    assert f.name == "hyb10" and f.allows("a.cmu.edu") and f.allows("go.com")
    assert fence_for("ppr10", "cmu.edu", [], tmp_path).name == "ppr10"
