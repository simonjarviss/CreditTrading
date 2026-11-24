# Shadow universes

Lists of symbols a shadow book may trade. Each is built from files already in the repository,
never typed by hand, and each says where it came from.

| file | what | built from |
|---|---|---|
| `cef_v1.csv` | 91 US closed-end funds: the 74 frozen for C4, the core's 13, and the four municipal funds dropped on 2026-09-28 | `results/cef/c4/c4_universe_frozen_2026-10-14.csv`, `ops/specs/cef_discount.frozen.json` (`frozen.universe`), `docs/SYSTEM.md` §5 (2026-09-28, "Universe on Alpaca") |
| `units_v1.csv` | 48 listed partnership and trust units that paid a distribution in the 400 days to 2026-11-11, with Alpaca's shortable flag on that date | `python3 -m shadow.universes.build_units_v1`: Nasdaq Trader's symbol directory and a name rule, then Alpaca (tradable, a cash distribution on the feed). `docs/REFERENCES.md` §12sd |
| `uit_terminations_v1.csv` | The termination calendar for the `uit_termination` books: 271 unit trusts of closed-end funds (First Trust 204, Guggenheim 67) with a Mandatory Termination Date from 2026-01-02 to 2028-11-13, one row per trust and fund held (6,876 rows, 307 funds). Built 2026-11-18 | `python3 -m shadow.universes.build_uit_terminations_v1` (`crawl`, then `write`): every form 487 the two sponsors filed from 2023-07-01 to 2026-11-17, through `scripts/data/edgar_client.py`. `docs/REFERENCES.md` §12ut |
| `uit_terminations_v1_unparsed.csv` | What the builder could not read, by accession number and reason: 7 rows on 2026-11-18, all Guggenheim's Flaherty & Crumrine Preferred Portfolio (preferred securities listed without tickers) | the same run |
| `uit_notices_v1.csv` | Units sold and redeemed, from each form 24F-2NT of a registrant in the calendar (269 notices of 206 of the 241 registrants): the trust sizes behind the `uit_termination_big_sale` book | the same run |

`cef_v1` is the funds this desk already knows, not the market: CRSP holds about 576 funds a
day (`results/ideas/2026-11-10_cef_exdate_drift.md`). Widening it needs a public source that
classifies a listing as a closed-end fund; CRSP's rows are licensed and stay out of the
repository.

`units_v1` is rebuilt from public sources because CRSP's own list cannot be published. Checked
locally on 2026-11-11: it holds 46 of the 51 CRSP units with an ex-date since 2025-06. 14 of the
48 were not shortable at Alpaca that day; a shadow book ignores borrow, so its short leg
overstates what a paper account could hold.

`uit_terminations_v1` holds public filing facts only: the series, its sponsor, the deposit date,
the Mandatory Termination Date as printed, each closed-end fund's ticker, percentage and share
count at deposit, and the filing's accession number and URL. A holding counts as a closed-end
fund when the prospectus's own schedule lists it under a "CLOSED-END FUNDS" heading; checked
locally on 2026-11-18 against the CRSP rule the research used, on the 384 trusts the idea's crawl
had parsed from filings since 2023-07-01, the two rules agree on every trust (195 closed-end,
189 not). It covers two sponsors; Invesco, SmartTrust and Advisors Disciplined Trust are not in
it, and a trust with a term over 30 months filed before 2023-07-01 would be missing.

**When it must be rebuilt.** The shadow runner cannot rebuild it: the VM has no EDGAR contact
header, by design. Re-run both commands on the laptop and commit the three files (a) every
month, because the big-sale book needs each new 24F-2NT notice, which a registrant files after
its fiscal year ends, and a notice counts only once it is 30 days old; (b) by 2027-10 at the
latest for the dates themselves: the shortest term in this build is 15 months and its newest
prospectus was filed on 2026-11-13, so the first termination a later filing could add is in early
2028; and (c) at once if `python3 -m shadow.fetch.uit_px` raises "rebuild it".
