# Related work notes: PPR-derived allowlists for LLM web agents

Checked 2026-10-18 with web searches; abstracts only, not full papers. Treat this as a starting point, not a literature review.

## Bottom line

No paper found that **builds an agent's domain allowlist automatically from a link graph** (PageRank, Personalized PageRank or TrustRank). The pieces exist separately, but the combination looks open. Before claiming novelty in the paper or README, read the full texts of Prismata and ceLLMate (below), since their abstracts don't say how their policies are chosen.

## Closest work

| Work | What it does | How it differs from DomainFence |
|---|---|---|
| **Prismata** (arXiv 2607.08147) | Labels page content by derived trust, hides untrusted parts and restricts agent actions; no developer annotations needed | Content- and action-level confinement within pages; abstract doesn't mention domain allowlists or link graphs |
| **ceLLMate** (arXiv 2512.12594) | Browser-extension sandbox enforcing policies at the HTTP layer; blocks WASP attacks at 7–15% latency overhead | Same enforcement layer as ours (network requests); abstract doesn't say how policies are set. **Most important to read in full** |
| **Silent Egress** (arXiv 2602.22450) | Implicit prompt injection that makes agents leak data | Reports domain allowlisting blocked all egress to clearly external attacker domains in their ablations, but notes allowlists are hard to deploy in practice. Supports our motivation: **automating the list is the gap** |
| **WASP** (arXiv 2504.18575) | Standard benchmark for web-agent prompt-injection security | Possible external benchmark for a later version; ours uses live university sites |
| **WAInjectBench** (arXiv 2510.01354), **StakeBench** (arXiv 2606.13385), **IPI-proxy** (arXiv 2605.11868), **WARD** (arXiv 2605.15030) | Injection benchmarks, detectors and red-teaming proxies | Detection or evaluation, not allowlist construction |
| **TrustRank** (Gyöngyi et al., 2004); **Topical TrustRank** (WWW 2006) | Seed-biased PageRank to separate trusted from spam pages | Same core math as our restart vector; must be cited. Difference: whole-web spam ranking vs. one organization's ecosystem, and use as an agent guardrail |

## Threats to the claim worth stating

- **Trusted domains can still be abused.** Silent Egress notes attackers use compromised legitimate sites, subdomain takeovers or open redirects. A high-PPR domain isn't automatically safe, which matches our threat-model limitation.
- **Social media ranks high in our whitelists.** That is exactly the kind of high-traffic platform where attackers can post content.

## Suggested framing

> Domain allowlists are an effective but manually maintained defense for web agents. We show they can be derived automatically from a single seed domain with seed-personalized PageRank over the organization's link graph (cf. TrustRank), and evaluate the trade-off against a naive same-apex rule on live sites.

## Sources

- [WebMCP-Phalanx](https://arxiv.org/pdf/2608.24017)
- [TRUSTDESC](https://arxiv.org/pdf/2604.07536)
- [ceLLMate: Sandboxing Browser AI Agents](https://arxiv.org/abs/2512.12594)
- [WARD](https://arxiv.org/pdf/2605.15030)
- [Adaptive Evaluation of Out-of-Band Defenses](https://arxiv.org/pdf/2606.26479)
- [AgentTrust](https://arxiv.org/pdf/2606.08539)
- [Silent Egress](https://arxiv.org/pdf/2602.22450)
- [Prompt Injection Prevention: defense-in-depth guide](https://dev.to/brennhill/prompt-injection-prevention-a-defense-in-depth-guide-for-ai-agents-5209)
- [Prompt Injection Defense, OWASP LLM Top 10](https://theroadtoenterprise.com/blog/prompt-injection-ai-features-production)
- [StakeBench](https://arxiv.org/html/2606.13385v1)
- [WAInjectBench](https://www.alphaxiv.org/abs/2510.01354)
- [LoginTrap](https://arxiv.org/pdf/2608.04741)
- [Domain-Conditioned Safety in Computer-Using Agents](https://arxiv.org/pdf/2606.05233)
- [Plan-Then-Execute for Web Agents](https://arxiv.org/pdf/2605.14290)
- [WebSentinel](https://arxiv.org/pdf/2602.03792)
- [Prismata](https://arxiv.org/abs/2607.08147)
- [IPI-proxy](https://arxiv.org/pdf/2605.11868)
- [TrustRank seed-biased PageRank (pagerankr docs)](https://rdrr.io/cran/pagerankr/man/trustrank.html)
- [Seed teleport prior (pagerankr docs)](https://rdrr.io/cran/pagerankr/man/seed_prior.html)
- [Waterloo CS451 big data slides](https://student.cs.uwaterloo.ca/~cs451/F21/slides/big-data-part10b.pdf)
- [Topical TrustRank (WWW 2006)](https://archives.iw3c2.org/www2006/programme/files/xhtml/3115/fp3115-wu/fp3115-wu-xhtml.html)
