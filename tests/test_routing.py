from agent.fence import Fence
from agent.routing import decide
from related_domains import RankedHost

ATT = {"evil-attacker.test"}
APEX = Fence.apex("cmu.edu", [])
RANK = [RankedHost("cmu.edu", .5, True), RankedHost("gostanford.com", .1, False)]


def test_off_fence_document_blocks():
    assert decide("https://other.com/x", True, APEX, ATT, APEX, "visible_link") == "block"


def test_attacker_document_under_none_fence_sinks():
    assert decide("http://evil-attacker.test/p", True, Fence.none(), ATT, APEX, "visible_link") == "sink"


def test_attacker_document_under_apex_blocks_fence_first():
    assert decide("http://evil-attacker.test/p", True, APEX, ATT, APEX, "visible_link") == "block"


def test_first_party_document_with_attack_injects():
    assert decide("https://www.cmu.edu/a", True, APEX, ATT, APEX, "hidden_instruction") == "inject"


def test_first_party_document_attack_none_passes():
    assert decide("https://cmu.edu/a", True, APEX, ATT, APEX, "none") == "pass"


def test_partner_domain_document_under_ppr_passes():
    ppr = Fence.ppr(RANK, 2)
    assert decide("https://gostanford.com/", True, ppr, ATT, APEX, "visible_link") == "pass"


def test_non_document_off_fence_passes():
    assert decide("https://cdn.other.com/a.js", False, APEX, ATT, APEX, "visible_link") == "pass"


def test_attacker_host_compared_canonically():
    assert decide("http://WWW.Evil-Attacker.test:80/p", False, Fence.none(), ATT, APEX, "none") == "sink"


def test_missing_host_document_blocks():
    assert decide("about:blank", True, Fence.none(), ATT, APEX, "none") == "block"


def test_missing_host_non_document_passes():
    assert decide("data:text/plain,hi", False, APEX, ATT, APEX, "none") == "pass"
