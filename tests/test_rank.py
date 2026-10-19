from bs4 import BeautifulSoup
from related_domains import DomainGraph, first_party_links, rank_graph
from ppr import PPRConfig

def paper_graph():  # worked example, paper §6
    g = DomainGraph("cmu.edu")
    for h in ["cmu.edu", "cs.cmu.edu", "scs.cmu.edu", "andrew.cmu.edu"]:
        g.add_node(h, True)
    for h in ["nsf.gov", "github.com", "linkedin.com"]:
        g.add_node(h, False)
    for s, t, w in [("cmu.edu","cs.cmu.edu",5),("cmu.edu","scs.cmu.edu",3),("cmu.edu","andrew.cmu.edu",2),
                    ("cs.cmu.edu","cmu.edu",2),("cs.cmu.edu","scs.cmu.edu",1),("cs.cmu.edu","nsf.gov",4),
                    ("scs.cmu.edu","cmu.edu",1),("scs.cmu.edu","cs.cmu.edu",2),("scs.cmu.edu","github.com",3),
                    ("andrew.cmu.edu","cmu.edu",2),("andrew.cmu.edu","linkedin.com",1)]:
        g.add_edge(s, t, w)
    return g

def test_rank_graph_paper_example():
    r = rank_graph(paper_graph(), PPRConfig(damping=0.85, seed_weight=0.5, subdomain_weight=0.5))
    assert r[0].host == "cmu.edu"
    assert r[-1].host == "linkedin.com"
    assert abs(sum(x.score for x in r) - 1.0) < 1e-9
    assert [x.score for x in r] == sorted((x.score for x in r), reverse=True)
    assert {x.host for x in r if x.is_first_party} == {"cmu.edu","cs.cmu.edu","scs.cmu.edu","andrew.cmu.edu"}

def test_first_party_links_resolves_relative_hrefs():
    soup = BeautifulSoup('<a href="/sfs/tuition">t</a><a href="https://x.com/">x</a>'
                         '<a href="https://cs.cmu.edu/a#frag">c</a><a href="mailto:a@cmu.edu">m</a>', "html.parser")
    links = first_party_links(soup, "https://cmu.edu/about/", "cmu.edu", [])
    assert links == ["https://cmu.edu/sfs/tuition", "https://cs.cmu.edu/a"]
