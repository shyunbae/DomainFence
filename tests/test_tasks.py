import json

import pytest

from agent.tasks import TASK_TYPES, load_tasks


def task(i="t1", **kw):
    t = {"id": i, "seed": "cmu.edu", "type": "in_apex", "question": "q?", "gold_answer": "A",
         "answer_variants": ["a"], "gold_urls": ["https://cmu.edu/x"], "partner_domains": [],
         "misinfo_answer": "B", "checked_date": "2026-10-18"}
    t.update(kw)
    return t


def write(tmp_path, rows):
    p = tmp_path / "tasks.jsonl"
    p.write_text("\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows) + "\n")
    return p


def test_valid(tmp_path):
    rows = [task("a"), task("b", type="partner", partner_domains=["gocmu.com"]),
            task("c", type="wrong_source")]
    out = load_tasks(write(tmp_path, [rows[0], "", rows[1], rows[2]]))
    assert [t["id"] for t in out] == ["a", "b", "c"]
    assert TASK_TYPES == ("in_apex", "partner", "wrong_source")


@pytest.mark.parametrize("rows,msg", [
    ([{k: v for k, v in task().items() if k != "question"}], "line 1.*question"),
    ([task(type="nope")], "line 1.*type"),
    ([task("a"), task("a")], "line 2.*duplicate"),
    ([task(type="partner", partner_domains=[])], "line 1.*partner_domains"),
    ([task(gold_urls=[])], "line 1.*gold_urls"),
    ([task(misinfo_answer=" a ", gold_answer="A")], "line 1.*misinfo"),
    ([task(answer_variants="a")], "line 1.*answer_variants"),
    ([task(gold_urls="x")], "line 1.*gold_urls"),
    ([task(partner_domains="x")], "line 1.*partner_domains"),
    ([task("a"), "{bad json"], "line 2"),
])
def test_invalid(tmp_path, rows, msg):
    with pytest.raises(ValueError, match=msg):
        load_tasks(write(tmp_path, rows))
