"""Task schema and validating loader for the agent experiment."""
from __future__ import annotations

import json
from pathlib import Path

TASK_TYPES = ("in_apex", "partner", "wrong_source")
REQUIRED = ("id", "seed", "type", "question", "gold_answer", "answer_variants", "gold_urls",
            "partner_domains", "misinfo_answer", "checked_date")
LIST_FIELDS = ("answer_variants", "gold_urls", "partner_domains")


def load_tasks(path: Path) -> list[dict]:
    """Load and validate tasks.jsonl; ValueError names the offending line."""
    tasks: list[dict] = []
    seen: set[str] = set()
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            t = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"line {n}: malformed JSON: {e}") from e
        if not isinstance(t, dict):
            raise ValueError(f"line {n}: task must be a JSON object")
        for f in REQUIRED:
            if f not in t:
                raise ValueError(f"line {n}: missing field {f}")
        for f in LIST_FIELDS:
            if not isinstance(t[f], list):
                raise ValueError(f"line {n}: {f} must be a list")
        if t["type"] not in TASK_TYPES:
            raise ValueError(f"line {n}: unknown type {t['type']!r}")
        if t["id"] in seen:
            raise ValueError(f"line {n}: duplicate id {t['id']!r}")
        if t["type"] == "partner" and not t["partner_domains"]:
            raise ValueError(f"line {n}: partner task needs non-empty partner_domains")
        if not t["gold_urls"]:
            raise ValueError(f"line {n}: gold_urls must be non-empty")
        if str(t["misinfo_answer"]).strip().lower() == str(t["gold_answer"]).strip().lower():
            raise ValueError(f"line {n}: misinfo_answer equals gold_answer")
        seen.add(t["id"])
        tasks.append(t)
    return tasks
