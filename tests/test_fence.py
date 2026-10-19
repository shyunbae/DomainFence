import pytest
from agent.fence import Fence, canonical_host
from related_domains import RankedHost

R = [RankedHost("cmu.edu",.5,True), RankedHost("cs.cmu.edu",.2,True), RankedHost("gostanford.com",.1,False),
     RankedHost("facebook.com",.05,False)]

def test_canonical_host():
    assert canonical_host("WWW.CMU.EDU:443") == "cmu.edu"
    assert canonical_host("cmu.edu.") == "cmu.edu"
    assert canonical_host("bücher.de") == "xn--bcher-kva.de"

def test_none_allows_everything():
    assert Fence.none().allows("evil.com")

@pytest.mark.parametrize("host,ok", [("cmu.edu",True),("cs.cmu.edu",True),("www.cmu.edu",True),("CMU.EDU:8080",True),
    ("cmu.edu.",True),("notcmu.edu",False),("cmu.edu.evil.com",False),("128.2.42.10",False),("troy.k12.mi.us",True)])
def test_apex(host, ok):
    assert Fence.apex("cmu.edu", ["troy.k12.mi.us"]).allows(host) is ok

def test_ppr_exact_hosts():
    f = Fence.ppr(R, 3)
    assert f.name == "ppr3"
    assert f.allows("www.gostanford.com") and f.allows("cs.cmu.edu")
    assert not f.allows("facebook.com")
    assert not f.allows("ml.cmu.edu")          # no apex wildcard
    assert not f.allows("sub.cs.cmu.edu")

def test_ppr_k_larger_than_ranking_and_invalid_k():
    assert Fence.ppr(R, 50).allows("facebook.com")
    with pytest.raises(ValueError):
        Fence.ppr(R, 0)


H = [RankedHost("cmu.edu", .5, True), RankedHost("cs.cmu.edu", .2, True),
     RankedHost("www.instagram.com", .1, False), RankedHost("ml.cmu.edu", .09, True),
     RankedHost("gotartans.com", .08, False), RankedHost("usnews.com", .01, False)]


def test_hybrid_is_apex_plus_top_k_external_hosts():
    f = Fence.hybrid("cmu.edu", [], H, 2)
    assert f.name == "hyb2"
    assert f.allows("anything.cmu.edu") and f.allows("www.cmu.edu")  # apex rule, any subdomain
    assert f.allows("instagram.com") and f.allows("gotartans.com")    # top-2 externals
    assert not f.allows("usnews.com")                                  # 3rd external
    assert not f.allows("sub.gotartans.com")                           # externals are exact-host
    assert not f.allows("cmu.edu.evil.com") and not f.allows("128.2.42.10")


def test_hybrid_counts_only_external_hosts_toward_k():
    # first-party entries in the ranking don't use up k
    assert Fence.hybrid("cmu.edu", [], H, 3).allows("usnews.com")


def test_hybrid_includes_aliases_and_rejects_bad_k():
    assert Fence.hybrid("cmu.edu", ["troy.k12.mi.us"], H, 1).allows("a.troy.k12.mi.us")
    with pytest.raises(ValueError):
        Fence.hybrid("cmu.edu", [], H, 0)
