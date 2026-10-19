"""Answer grading: normalized match first, LLM judge as fallback."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from agent.llm import LLM

_STRIP = re.compile(r"[^\w\s$.,%]")


def normalize_answer(s: str) -> str:
    """Lowercase, drop punctuation except $.,%, collapse whitespace, trim trailing .,"""
    return " ".join(_STRIP.sub("", s.lower()).split()).rstrip(".,").strip()


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _save(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(cache))
    os.replace(tmp, path)


def grade(task: dict, answer: str | None, *, llm: LLM, cache_path: Path,
          model: str = "claude-haiku-5-5") -> tuple[bool, float]:
    """Return (correct, judge cost in USD)."""
    if answer is None:
        return False, 0.0
    norm = normalize_answer(answer)
    golds = [task["gold_answer"], *task.get("answer_variants", [])]
    if norm in {normalize_answer(g) for g in golds}:
        return True, 0.0
    key = f"{task['id']}::{normalize_answer(task['gold_answer'])}::{norm}"
    cache = _load(cache_path)
    if key in cache:
        return cache[key], 0.0
    prompt = (f"Question: {task['question']}\nGold answer: {task['gold_answer']}\n"
              f"Candidate answer: {answer}\n"
              "Does the candidate state the same fact as the gold answer? Reply YES or NO.")
    reply = llm.complete(model, "You grade short factual answers.",
                         [{"role": "user", "content": prompt}], 1024)  # room for thinking
    ok = reply.text.strip().upper().startswith("YES")
    cache[key] = ok
    _save(cache_path, cache)
    return ok, reply.cost_usd
