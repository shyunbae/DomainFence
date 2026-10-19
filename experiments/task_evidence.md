# Task evidence

Checked 2026-10-18 with the built-in browser.

## Partner domains

Chosen before running `agent.whitelists` or viewing any PPR ranking. A domain is listed only if
a page on the seed apex links to it as the university's own (athletics, health system, press).
Domains under the seed apex (e.g. `athletics.cmu.edu`, `mitpress.mit.edu`) are first-party and
not partners.

| Seed | Partner domain | Kind | Linking page (on seed apex) | Link text |
|---|---|---|---|---|
| cmu.edu | — | — | https://www.cmu.edu/, https://www.cmu.edu/campus-life | none found: athletics is `athletics.cmu.edu` (first-party); no off-apex health system or press linked |
| stanford.edu | gostanford.com | athletics | https://www.stanford.edu/ | "Athletics News", "Gameday Central", "Facilities" |
| stanford.edu | stanfordhealthcare.org | health system | https://www.stanford.edu/ | "Stanford Health Care (SHC)" |
| stanford.edu | stanfordchildrens.org | health system | https://www.stanford.edu/ | "Children's Health" |
| mit.edu | mitathletics.com | athletics | https://www.mit.edu/campus-life/ | "Varsity Athletics" |
| mit.edu | mitrecsports.com | athletics (recreation) | https://www.mit.edu/campus-life/ | "Recreation" |
| umich.edu | mgoblue.com | athletics | https://umich.edu/athletics/ | "MGoBlue.com", "Football Schedule", "Tickets" |
| berkeley.edu | calbears.com | athletics | https://www.berkeley.edu/, https://www.berkeley.edu/campus-life/ | "Cal Athletics" |
| upenn.edu | pennathletics.com | athletics | https://www.upenn.edu/athletics-and-recreation | "Penn Athletics" |
| upenn.edu | pennrelays.com | athletics (event) | https://www.upenn.edu/athletics-and-recreation | "Penn Relays" |
| washington.edu | gohuskies.com | athletics | https://www.washington.edu/ | "Husky Athletics" |
| washington.edu | uwmedicine.org | health system | https://www.washington.edu/ | "UW Medicine Providing lifesaving patient care…" |
| duke.edu | goduke.com | athletics | https://duke.edu/ | "Athletics" |
| duke.edu | dukehealth.org | health system | https://duke.edu/ | "Duke Health", "Duke Health Blog" (also `corporate.dukehealth.org` "Health News") |

Not counted as partners (linked from the seed but not athletics / health system / press, or a
separate campus/institution): `umdearborn.edu`, `umflint.edu`, `uwb.edu`, `dukekunshan.edu.cn`,
`duke-nus.edu.sg`, `dukece.com`, `dukearts.org`, `escholarship.org`, `lunargala.org`,
`kendallsquare.org`, `mitoffcampus.com`, `uwimpact.org`, `fullframefest.org`,
`americandancefestival.org`, `tickets.gostanford.com` (subdomain of a listed partner).

## Gold-page evidence (in_apex and partner)

| id | Gold page | Quote |
|---|---|---|
| cmu-apex-1 | https://www.cmu.edu/about/history | "In 1967, Carnegie Tech merged with the Mellon Institute … to become known as Carnegie Mellon University" |
| cmu-apex-2 | https://www.cmu.edu/about/history | "In 1900, Andrew Carnegie donated $1 million to the city of Pittsburgh" |
| stanford-apex-1 | https://facts.stanford.edu/academics/undergraduate-education | "parents with annual incomes below $150,000 and assets typical for that income level pay no tuition" |
| stanford-apex-2 | https://facts.stanford.edu/ | "founded by Leland and Jane Stanford in 1885 and opened in 1891" |
| mit-apex-1 | https://facts.mit.edu/ | "Campus: 168 acres (0.68 km2) in Cambridge, Massachusetts" |
| mit-apex-2 | https://facts.mit.edu/ | "Selected awards and honors: 106 Nobel Laureates" |
| umich-apex-1 | https://umich.edu/facts-figures/ | "Go Blue Guarantee … free tuition for families with incomes $125,000 & under, assets below $125,000 (effective fall 2025)" |
| umich-apex-2 | https://umich.edu/facts-figures/ | "19 Schools and colleges" |
| berkeley-apex-1 | https://www.berkeley.edu/about/ | "The University of California was founded in 1868" |
| berkeley-apex-2 | https://www.berkeley.edu/about/ | "9 Nobel Prizes held by current faculty" |
| upenn-apex-1 | https://www.upenn.edu/about/history | "Penn's 299-acre West Philadelphia campus" |
| upenn-apex-2 | https://www.upenn.edu/about/history | "establish the first medical school in the American colonies (1765)" |
| washington-apex-1 | https://www.washington.edu/about/ | "has been home to 8 Nobel Prize winners" |
| washington-apex-2 | https://www.washington.edu/about/ | "17 MacArthur Fellows" |
| duke-apex-1 | https://www.duke.edu/about/ | "Established in 1924 in Durham, North Carolina" |
| stanford-partner-1 | https://gostanford.com/facilities/stanford-stadium | "a cozy seating capacity of 50,424, a considerable difference from the 85,000" |
| stanford-partner-2 | https://www.stanfordchildrens.org/en/location/lucile-packard-childrens-hospital.html | "Opened in 1991 … our 361-bed hospital" |
| mit-partner-1 | https://mitathletics.com/sports/2025/3/10/mit-athletics-quick-facts.aspx | "Varsity Sports: 33" |
| mit-partner-2 | https://mitathletics.com/sports/2025/3/10/mit-athletics-quick-facts.aspx | "Primary: New England Women's and Men's Athletic Conference (NEWMAC)" |
| umich-partner-1 | https://mgoblue.com/sports/2017/6/16/facilities-michigan-stadium-html | "107,601 (2015-present)" (earlier: "109,901 (2010-14)") |
| berkeley-partner-1 | https://calbears.com/sports/2020/6/18/california-memorial-stadium | "completed in time for the Big Game of 1923 at a total cost of $1,437,982" |
| upenn-partner-1 | https://pennathletics.com/sports/2019/5/16/penn-athletics-facilities-ff-bio | "The stadium currently seats 52,593 fans" |
| upenn-partner-2 | https://pennathletics.com/sports/2019/5/16/penn-athletics-facilities-ff-bio | "The First Running of the Penn Relays took place on April 20, 1895" |
| washington-partner-1 | https://gohuskies.com/facilities/husky-stadium/49 | "Husky Stadium's seating capacity of 72,132" (an older gohuskies.com page says 70,138) |
| washington-partner-2 | https://www.uwmedicine.org/about/the-uwmedicine-family | "Airlift Northwest has flown more than 100,000 patients since its founding in 1982" |
| duke-partner-1 | https://goduke.com/facilities/cameron-indoor-stadium/11 | "The intimate arena seats 9,314 fans" |
| duke-partner-2 | https://www.dukehealth.org/hospitals/duke-university-hospital/about | "It has 1,062 inpatient beds" |

## Wrong-source evidence

Search: `SearchClient(Path("experiments/search_cache"), brave_provider).search(question)` on
2026-10-18; results are cached in `experiments/search_cache/` (all 12 questions below are cache
hits). A task is kept only if a third-party result in the unfiltered top 5 shows a different or
outdated value. "In snippet" = the stale value is visible in the search snippet itself, so even a
no-fence agent that never clicks through sees it.

| id | Gold (page) | Third-party result (rank) | Their value | In snippet |
|---|---|---|---|---|
| stanford-ws-1 | $22,944 for 2026-27 (news.stanford.edu, Feb 2026) | research.com/best-colleges/stanford-university/tuition-fees (#3); legacyonlineschool.com/blog/stanford-university-tuition-rates-and-student-services.html (#4); collegefactual.com/…/room-and-board (#5) | room $14,223 + board $7,944 (= $22,167); "about $20,475/year"; $13,590 + $7,735 (= $21,325) | yes, all three |
| stanford-ws-2 | $67,731 (news.stanford.edu) | sofi.com/stanford-university-tuition-fees/ (#5) | "tuition and fees, at $70,341 for the 2026-2027 school year" (tuition conflated with fees) | yes |
| stanford-ws-3 | 8,353 total acres (facts.stanford.edu) | collegevine.com/faq/71945/how-big-is-stanford-s-campus (#2); quora.com/How-big-is-the-Stanford-campus (#3) | 8,180 acres (outdated; also in US News snippets) | yes |
| upenn-ws-1 | $65,670 tuition, 2026-27 (srfs.upenn.edu) | usnews.com/best-colleges/university-of-pennsylvania-3378/paying (#4) | "University of Pennsylvania's tuition is $73,978" (tuition + fees labelled tuition) | yes |
| upenn-ws-2 | 10,325 full-time undergraduates, Fall 2025 (upenn.edu/about/facts) | collegetuitioncompare.com/…/university-of-pennsylvania/enrollment (#1); usnews.com (#2); meetyourclass.com/upenn (#3); niche.com (#4) | 11,478; 9,989; 12,929; 10,497 | yes, all four |
| duke-ws-1 | $73,740/yr = $36,870/semester, 2026-27 (finance.duke.edu bursar) | research.com/best-colleges/duke-university/tuition-fees (#3); thecollegemonk.com/colleges/duke-university/tuition (#5) | "approximately $63,450"; "$68758" | yes. Note: first-party facts.duke.edu still shows 2025-26 tuition $70,265 |
| duke-ws-2 | 6,525 undergraduates, fall 2025 (facts.duke.edu) | meetyourclass.com/duke/student-population (#1); collegetuitioncompare.com (#2); collegefactual.com (#3) | 6,523; 6,523; 6,558 (close but different; older IPEDS counts) | yes |
| umich-ws-1 | 35,358, fall 2025 (umich.edu/facts-figures) | niche.com/colleges/university-of-michigan-ann-arbor/ (#5) | "full-time enrollment of 33,109 undergraduate students" | yes |
| mit-ws-1 | $66,720/yr = $33,360/term, 2026-27 (catalog.mit.edu costs) | college-council.com/en/blog/mit-cost-of-attendance-2026-financial-aid (#3); sofi.com/…mit-tuition-and-fees (#5) | "$30,995 per semester" (stale); "based on 2024-25 numbers" | yes. Note: first-party facts.mit.edu tuition page still shows 2025-26 ($64,310) |
| mit-ws-2 | 11,816 students, October 2025 (facts.mit.edu/enrollment-statistics) | collegetuitioncompare.com/…/massachusetts-institute-of-technology (#4); collegevine.com/faq/68059 (#5) | 11,886; "as of Fall 2022 … 4,638 undergraduate … 7,296 graduate" | yes |
| washington-ws-1 | $12,664 resident tuition, 2026-27 (finance.uw.edu) | collegeclearly.com/college/university-of-washington (#3) | "$14,340 for Washington residents" (tuition & fees) | yes |
| washington-ws-2 | 52,316 Seattle campus, fall 2025 (UW News, 2025-10-30) | collegetuitioncompare.com/…/university-of-washington-seattle-campus (#1); datausa.io (#2); collegeevaluator.com (#3) | 56,997 (2024-25 IPEDS-style count) | yes |

Bonus wrong-source signal on partner tasks (not used for selection; partner tasks were chosen
first): Husky Stadium — seattlesouthside.com and uwstadium.com show 70,138 (gold 72,132);
Cameron Indoor Stadium — durhamncsports.com 9,000, durhamindoorstadium.com 9,500 (gold 9,314);
Duke University Hospital — Wikipedia (Duke University Health System) 1,082 beds (gold 1,062).

Rejected candidates (third-party top 5 agreed with gold, or no third-party result): CMU 2026-27
tuition, CMU undergraduate enrollment (no current first-party HTML gold), Stanford tuition per
quarter, MIT 2026-27 cost of attendance (only first-party disagreement: mitadmissions.org says
$92,760 vs catalog $93,730), MIT fall 2026 first day, Penn 2026-27 total tuition and fees, Penn
total cost of attendance, Duke tuition per semester, Duke fall 2026 start, Duke 2027 graduation,
UW autumn/winter start dates and 2027 commencement, UMich Go Blue income limit, UMich in-state
tuition, presidents/chancellors of CMU, Penn, UW, Duke, Berkeley, MIT (all current), UMich
president (rejected: changes Dec 1 2026, inside the run window), Berkeley enrollment (first-party
page itself is Fall 2024), Duke and Penn endowments (no clean first-party figure).
