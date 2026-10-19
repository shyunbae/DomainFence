# DRAFT: README section "DomainFence for AI agents"

*Draft for the README (plan Task 14). Results stay as placeholders until the full run; everything else describes the code as built. Merge into README.md once results exist.*

---

## DomainFence for AI agents

Domain allowlists are an effective defense for web agents, but someone has to write them by hand. DomainFence builds one **automatically from a single seed domain**: Stage 1 ranks the organization's link graph with seed-personalized PageRank, and the agent may only load pages, and only sees search results, from:

- the seed domain, its subdomains and aliases, plus
- the **top-k external domains** by PPR score (`hybK`).

The agent never sees the list. A blocked page load simply comes back as `blocked: <host> not in allow-list`.

### Experiment

- **Tasks:** 35 questions about 7 universities, of three kinds:
  - answers on the university's own sites;
  - answers on official partner sites, such as `gostanford.com`;
  - questions where stale third-party pages rank high in search.
- **Agents:** Claude Sonnet 5.5 and Claude Haiku 5.5, starting on a blank page with search, page navigation and an answer action.
- **Fences compared:**
  - no fence;
  - a naive `*.seed` fence;
  - `hyb5`, `hyb10`, `hyb20`;
  - `ppr10`, the original top-k-overall form.
- **Attacks:** planted only inside our own test browser (live sites are never modified):
  - a visible "moved" link;
  - a hidden instruction;
  - a script redirect;
  - misinformation that stays on the page.

  Attacker hostnames resolve to a local sink and never reach the internet.
- **Metrics:** task success, attack attempted vs. reached, answers from sources outside the organization, and cost. All reported with bootstrap confidence intervals over tasks.

### Results

1,260 episodes without attacks and 2,520 with them. Claude Sonnet 5.5 and Haiku 5.5, 3 repeats, 95% bootstrap CIs over tasks. Full tables: `docs/experiment-report-2026-10-18.md`.

| Fence | Task success | Partner-site tasks | Non-official sources | Drive-by redirect reached attacker |
|---|---|---|---|---|
| none | 77.6% | 78.8% | 14.3% | 6.7% |
| `*.seed` | 61.4% | 33.3% | 5.8% | 0% |
| **hyb10 (PPR)** | **78.6%** | **77.3%** | **6.7%** | **0%** |
| ppr10 (top-k overall) | 63.8% | 33.3% | 5.6% | n/a |

- **Text injections** (a "moved" link, hidden instructions, planted misinformation) never succeeded against either model in any condition: 0 of 1,890 attacked episodes.
- **Partner recall:** 67% of official partner domains are in `hyb10`, and 89% in `hyb20`.

### Limitations

- **The fence form was revised after seeing the rankings.** As first specified, the PPR fence (top-k hosts overall) admitted 0% of labeled partner domains at k=10, because universities have 130–720 subdomains. The main arm became `hybK` before any agent episode ran. The original form is still reported as `ppr10`.
- **Social media ranks high among external domains.** Instagram, Facebook, YouTube and LinkedIn rank in the top 10, and for cmu.edu so does `usnews.com`. `hyb10` therefore admits some third-party platforms.
- **Server-side redirects are detected and reverted, not prevented.** A redirect from an allowed site to a disallowed one reaches the target once, then the agent is sent back and a block is recorded. All four attacks are triggered client-side, so attack results are unaffected.
- **A fence cannot stop on-page misinformation.** An injected instruction that changes the answer without navigating anywhere gets through. It is measured separately (`onpage_misinfo`).
- **The operator names the seed.** Inferring it from the user's request is future work.
- **Small study on live sites.** 35 tasks across 7 universities (umich.edu was dropped because its crawl reached only one host), 3 runs per condition, and sites change over time. Confidence intervals are wide, especially for the 11 partner-site tasks. Conditions for each task run back-to-back to limit drift.
- **Related work.** TrustRank (Gyöngyi et al., 2004) uses the same seed-biased PageRank for spam detection. ceLLMate and Prismata confine web agents with HTTP-level or content-level policies. See `docs/related-work-notes.md`.
