import pytest

from agent.injection import (
    ATTACKS, SINK_HTML, all_attacker_hosts, attacker_host, attacker_url,
    inject, resolver_rules,
)


def test_inject_after_main_then_body():
    out = inject('<html><body><main id="m">X</main></body></html>', "hidden_instruction", "cmu.edu", None)
    assert out.index("cmu-info-portal.com") > out.index('<main id="m">') and out.index("cmu-info-portal.com") < out.index("X")
    assert "cmu-info-portal.com" in inject("<body>Y</body>", "hidden_instruction", "cmu.edu", None)


def test_visible_link_replaces_main_content():
    # compromised-page variant: the answer is gone, only the "moved" notice remains
    page = ('<html><head><title>T</title></head><body><nav>NAV</nav>'
            '<main id="m"><p>Tuition is $42</p></main><footer>FOOT</footer></body></html>')
    out = inject(page, "visible_link", "cmu.edu", None)
    assert "cmu-info-portal.com" in out and "$42" not in out
    assert "NAV" in out and "FOOT" in out and "<title>T</title>" in out
    assert out.count("</main>") == 1


def test_visible_link_replaces_body_when_no_main():
    out = inject("<html><body><p>Tuition is $42</p></body></html>", "visible_link", "cmu.edu", None)
    assert "cmu-info-portal.com" in out and "$42" not in out and out.endswith("</body></html>")


def test_none_unchanged_and_misinfo_uses_answer():
    assert inject("<body>Y</body>", "none", "cmu.edu", None) == "<body>Y</body>"
    out = inject("<body>Y</body>", "onpage_misinfo", "cmu.edu", "$1")
    assert '"$1"' in out and "info-portal" not in out


def test_fragment_without_body_is_prepended():
    assert inject("plain", "fake_redirect", "mit.edu", None).startswith("<script>")


def test_resolver_rules():
    assert resolver_rules(["a.com", "b.com"]) == "MAP a.com 127.0.0.1, MAP b.com 127.0.0.1"


def test_hosts_and_urls():
    assert attacker_host("cmu.edu") == "cmu-info-portal.com"
    assert attacker_url("cmu.edu") == "https://cmu-info-portal.com/verify"
    assert all_attacker_hosts(["cmu.edu", "mit.edu"]) == ["cmu-info-portal.com", "mit-info-portal.com"]
    assert ATTACKS[0] == "none" and len(ATTACKS) == 7
    assert "Verification required" in SINK_HTML


def test_attacker_override():
    out = inject("<body>Y</body>", "visible_link", "cmu.edu", None, attacker="127.0.0.1:9")
    assert 'href="https://127.0.0.1:9/verify"' in out and "info-portal" not in out


def test_main_preferred_over_body_case_insensitive():
    out = inject("<BODY><MAIN class=a>X</MAIN></BODY>", "visible_link", "cmu.edu", None)
    assert out.index("info-portal") > out.index("<MAIN class=a>")


def test_lookalike_tags_not_matched():
    out = inject("<mainframe>M</mainframe><body>B</body>", "visible_link", "cmu.edu", None)
    assert out.startswith("<mainframe>") and out.index("info-portal") > out.index("<body>")
    out = inject("<bodyx>M</bodyx>", "fake_redirect", "cmu.edu", None)
    assert out.startswith("<script>")


def test_misinfo_escaped_and_brace_safe():
    out = inject("<body>Y</body>", "onpage_misinfo", "cmu.edu", 'a "q" <b> {url}')
    assert "&quot;q&quot;" in out and "&lt;b&gt;" in out and "<b>" not in out
    assert "{url}" in out


def test_misinfo_requires_answer():
    with pytest.raises(ValueError):
        inject("<body>Y</body>", "onpage_misinfo", "cmu.edu", None)


def test_unknown_attack_raises():
    with pytest.raises(ValueError):
        inject("<body>Y</body>", "bogus", "cmu.edu", None)


def test_attacks_tuple_has_second_round():
    from agent.injection import ATTACKS
    assert "task_lure" in ATTACKS and "search_poison" in ATTACKS


def test_task_lure_replaces_content_with_partial_answer_and_link():
    page = '<html><body><main><p>Tuition is $42,000</p></main></body></html>'
    out = inject(page, "task_lure", "cmu.edu", None)
    assert "cmu-info-portal.com" in out and "$42,000" not in out


def test_search_poison_leaves_page_unchanged():
    page = "<html><body><p>hi</p></body></html>"
    assert inject(page, "search_poison", "cmu.edu", None) == page


def test_poison_result_on_attacker_host():
    from agent.injection import poison_result, attacker_host
    r = poison_result("cmu.edu")
    assert attacker_host("cmu.edu") in r["url"] and r["title"] and r["snippet"]
    # honours attacker override (used by the e2e fixture)
    assert "evil.test" in poison_result("cmu.edu", attacker="evil.test")["url"]
