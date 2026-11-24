# Re-run of the CEF event analyses: merger pair and term CEFs — 2026-10-11

**What this is.** Two of the six analyses in item 0.9 of
`results/cef/RESEARCH_PLAN_2026-10-09.md` ("bring the agents' scratch analyses
into the repo and re-run them"), rebuilt as repo scripts and re-run:

- the **NAV-for-NAV CEF merger pair**, SCALING §7.1 row 1;
- the **term-CEF census and pull-to-par**, SCALING §7.1 row 7, plus the census
  filter correction of SCALING §7.4.

The original agents' scratch scripts were deleted with their session. Their code
was recovered from the agents' transcripts (`502a27a9…/subagents/agent-a77f1a26…`
for the merger pair and `agent-a805c27e…` for term CEFs) and used **as
provenance only**: the figures they printed are what this note checks, not
evidence.

**Zero trials.** This is a descriptive reproduction. No counter moves and
nothing is pre-registered. It is not a harness backtest: there is no `shift(2)`
policy, no turnover matching and no cost grid. The originals were descriptive
too.

**Holdouts.**
- Every return statistic uses CRSP rows dated before 2023-01-01.
  `scripts/events/crsp_events.py::daily` cannot return a later row and asserts
  so.
- No return is computed on any of the 44 `cef_universe.csv` funds. Universe funds
  are matched by ticker (as the original did) and by CRSP permno. The 27-name
  comparison set was opened for event trades on 2026-10-09 (`docs/SYSTEM.md` §5),
  but it is consumed only by a pre-registered test that says so, and this is not
  one.
- The G1c event count does include the 27. It is a count, not a return.
- Events from 2023–24 are counted only.

**Data dates.**

| source | coverage |
|---|---|
| CRSP mirror (R2): names and delistings | to 2024-12-31 |
| CRSP mirror (R2): daily extract | last row 2022-12-30 |
| FRB DGS3MO (R2) | to 2025-02-11 |
| CEFConnect | daily rows to 2026-10-08 (NMCO and MMD to 2026-10-09), fetched 2026-10-11T19:57Z |
| Alpaca asset flags and corporate actions | read 2026-10-11 |

**Labels.**
- "Original" figures are the agents' of 2026-10-09: [S], transcript.
- Re-run figures are [V]: produced by the named script on the data above, on
  2026-10-11.

## 0. The answer

- **Almost every figure reproduces exactly.** Every number in rows 1 and 7 now
  comes from a script in the repo.
- **Corrections, all visible below:**
  - **One merger event in the original sample touched a comparison-set fund.**
    SBW merged into ESD in 2016, and ESD is today's EMD. Excluding it moves
    +129/+25bp to **+128/+26bp**. That is immaterial.
  - **The live term-CEF discounts were 2026-10-07's, not 2026-10-08's.** On
    2026-10-08, FTHY was **−4.50%** and DTF **−4.75%**.
  - **Borrow on historical acquirers, read from Alpaca today.** 27 of the 61
    still-active acquirers are not shortable, 16 of them munis.
  - **The beta-adjusted term excess with a fetchable risk-free source** is
    −0.02 / +0.24 / +1.92%/yr, against the original −0.07 / +0.22 / +1.84.
  - **The census filter now finds 154 name records**, against 92 before.
- **A negative result the original did not show.** The at-announcement +35bp
  median rests on 13 announcement dates, 7 of them from search summaries. On
  the **6 groups whose dates the agent read in EDGAR (18 events), the median is
  −19bp** (50% positive).
- **The gates:**
  - **G1c passes** on every clustering, from 69 to 122 groups.
  - **G1a is marginal**: 56% of active historical acquirers are shortable, but
    only 30% of the muni acquirers, and munis are where the effect lives.
  - **G1b cannot be measured** until the NAV history of plan item 0.8 exists.

## 1. How to re-run

```bash
export QUANTT_ENV_FILE=".../config/.env"          # R2 and Alpaca keys; never printed
python3 scripts/events/merger_pairs.py            # -> results/events/merger_*.csv, merger_summary.json
python3 scripts/events/acquirer_shortability.py   # read-only Alpaca -> g1a/alpaca_acquirers_<date>.csv, g1a/alpaca_g1a_summary_<date>.json
python3 scripts/events/term_pull_to_par.py        # -> term_cef/term_pull_to_par_measure.csv, term_cef/term_beta_adj*.csv, term_cef/term_pull_to_par_summary.json
python3 scripts/events/fetch_term_cef_live.py     # CEFConnect + read-only Alpaca -> term_cef/term_cef_live_<date>.csv, term_cef/term_cef_live_summary_<date>.csv
python3 scripts/data/term_cef_census.py --csv     # -> term_cef_census.csv
python3 -m pytest scripts/events/tests            # the four method corrections, each checked to fail on the old code
```

The CRSP extracts are cached in `results/events/_cache_crsp/`, which is
gitignored. `--refresh` re-pulls them.

## 2. Row 1: the NAV-for-NAV merger pair

Source: `merger_summary.json`, `merger_ann_sample.csv` and
`g1a/alpaca_g1a_summary_2026-10-11.json`. Two exclusions are shown:
- "ticker" is the original's ticker-only universe exclusion;
- "permno" also catches a universe fund under an older ticker.

| figure (SCALING §7.1 row 1) | original | re-run | verdict |
|---|---|---|---|
| CRSP merger delistings of share code 14/44, 2010–22 | 269 (stock 232, shell 16, cash 15, stock+cash 6) | 269, same split | **reproduced** |
| Events touching `cef_universe.csv` | 45 | 45 by ticker; **46** by ticker or permno (SBW→ESD, 2016-12-16; ESD's permno 89970 is today's EMD) | **corrected** (+1) |
| Stock events with no universe name, and their groups | 193 events in 115 groups | 193 in 115 (ticker; original key). By acquirer permno × date: 116, because the original's key dropped one acquirer with no CRSP name. Permno exclusion: 192 events, 115 groups | **reproduced**; grouping fixed |
| Ratio = CRSP `dlamt` ÷ acquirer price; matches filings "to 6 decimals" | GGM 1.123347, GPM 0.527929 | GGM 1.123347, GPM 0.527929 | CRSP side **reproduced**. The filed ratios (1.12334682, 0.52792920) were not re-read [S] |
| Deals with no universe name (pairs at T−63) | N=168 | 168 (ticker); **167** (permno) | **reproduced**; corrected −1 |
| Pair median, last 63 days, against the control a year earlier | **+129 vs +25bp** | **+129.0 vs +25.0** (ticker); +127.9 vs +26.0 (permno) | **reproduced** |
| T−21 / T−126 pair against control | +113 / −19; +166 / +19 | +113.4 / −18.8; +166.1 / +19.1 (ticker) | **reproduced** |
| Munis at T−63 | **+148 vs −43** (N 92) | +148.5 vs −43.5 (N 92); identical under both exclusions | **reproduced** |
| Equity CEFs at T−63 (the control wins) | **+36 vs +214** (N 33) | +35.7 vs +213.6 (N 33) | **reproduced** |
| Taxable CEFs at T−63 | +115 vs +24 (N 40) | +115.3 vs +24.1 (ticker); +109.3 vs +29.8 (permno, N 39; SBW was taxable) | **reproduced**; corrected under permno |
| Spread the day before the target's last trade; completion-day `dlret` | +51bp; +34bp (N 186) | +51.0; +33.6 (N 186, ticker) | **reproduced** |
| Realisation at T−63: slope, correlation, sign by hindsight | 0.80, 0.93, +259bp, 97% | 0.804, 0.928, +259.2bp, 97% | **reproduced** |
| **At announcement** (entry at the close of A+1, held to completion) | **+35bp median, N=36 events in 12 groups** | +35.1bp median, mean +83.9, 55.6% positive; N 36, 12 announcement dates (15 acquirer × date groups) | **reproduced** (arithmetic). The dates were not re-fetched: [S] |
| … by class | muni +227 (16); taxable +20 (10); Aberdeen country −739 (7); BDC −183 (3) | +226.8; +20.4; −738.5; −183.0 | **reproduced** |
| … on the EDGAR-read dates only (NRK, BLE, CH, OCSI, SUNS, FSKR) | not reported | **−18.9bp median, mean −78.7, 50% positive, N 18 in 6 groups** | **new; a negative** |
| Below the 32.6bp-per-unit breakeven | +35bp per deal ≈ 18bp per unit | 35.1 ÷ 2 ≈ 17.6bp per unit | **reproduced** (arithmetic) |
| "26 of 59 historical acquirers, mostly munis, not shortable today" | 26 of 59 (2026-10-08 map) | The map gives exactly 26 of 59. **Alpaca, 2026-10-11:** of the 97 acquirer tickers, 11 are not listed, 25 are inactive (merged away) and 61 are active. Of the 61, **34 are shortable and 27 are not**. Of the 23 muni acquirers by name, 7 are shortable. **11 of the 59 map flags changed between 2026-10-08 and 2026-10-11** (6 to not shortable, 5 to shortable) | **corrected** (re-measured; same picture) |
| Capacity "about $0.5m per deal" | $0.5m (from ADV median $262k target, $587k acquirer) | ADV63 medians $262,259 and $587,201 (ticker) | inputs **reproduced**. **The $0.5m could not be re-run**: no formula was recorded |

## 3. Row 7: term-CEF pull-to-par, and the §7.4 census

Source: `term_cef/term_pull_to_par_summary.json`, `term_cef/term_pull_to_par_measure.csv`,
`term_cef/term_beta_adj*.csv` and `term_cef/term_cef_live_summary_2026-10-11.csv`.

| figure (SCALING §7.1 row 7, §7.4) | original | re-run | verdict |
|---|---|---|---|
| "All 19 modern credit term funds that terminated before 2023 paid out NAV (CRSP code 450)" | 19, all code 450 | 19, all `dlstcd` 450. The 26 old trusts are also all 450 | **reproduced** for the code. "Paid NAV" is an inference: there is no NAV history for dead funds (plan 0.8), so it is unverified |
| Price against terminal value, 24 months out (modern, median [IQR]) | +0.20% [−2.4, +2.5] | +0.20 [−2.39, +2.54] | **reproduced** |
| d_adj, dy and raw excess, modern 24 months | −5.41, 2.70, −4.85 | −5.41, 2.70, −4.85 | **reproduced** |
| Beta-adjusted excess, modern, 24 / 12 months | **−0.07 / +0.22%/yr** (9 and 10 of 19 positive; β 0.24 / 0.15) | Original inputs: −0.07 / +0.22 (9, 10; β 0.236 / 0.151). **DGS3MO from the R2 FRB mirror: −0.02 / +0.24** (9, 10) | **reproduced**, and **corrected** for the source of the risk-free rate |
| The 1990s cohort | **+1.8%/yr** (+1.84 at 24 months, 20/26; +1.60 at 12 months; β 0.05) | Original inputs: +1.84 (20/26) / +1.60 (19/26). **R2 FRB: +1.92 (21/26) / +1.68 (20/26)**; β 0.054 | **reproduced** and **corrected**, as above |
| Target misses | JCO $8.02, EFL $8.66 against $9.85 | Terminal value from CRSP: JCO $8.0159, EFL $8.6647. The $9.85 target is [S], not re-read | **reproduced** |
| Live: FTHY −4.7% (2027-08), DTF −5.1% (2028-03), "2026-10-08" | −4.73, −5.08 | Those are the **2026-10-07** dated rows. **2026-10-08: FTHY −4.50%, DTF −4.75%** (same-date price and NAV, CEFConnect) | **corrected** (the date) |
| FTHY and DTF are outside the holdout; BSL and BGB are holdout names | yes | Same (`cef_universe.csv`). BSL −3.58%, BGB −5.31% on 2026-10-08 | **reproduced** |
| Borrow on the live term funds | map 2026-10-08: FTHY T/T, DTF T/F, BGB T/T | **Alpaca 2026-10-11:** FTHY shortable, DTF not, **BGB not** (was shortable on 2026-10-08), BSL not | **corrected** (re-measured) |
| D7: "about 47 events" | 47 | 19 + 2 + 26 = 47 in `FUNDS` | **reproduced** (by construction) |
| §7.4: the census filter misses abbreviated, 19xx-dated and tender-clause funds | stated, not fixed | **Fixed** (`scripts/data/term_cef_census.py`). There are now 154 name records, against 92 under the old filter. By rule: TERM 59, abbreviation 68, year 58, tender list 21. Every row names its rule. Struck names are flagged (13 records), not dropped. All 20 tender-list tickers have a CRSP CEF record | **corrected** |

## 4. What was wrong in the original code, and what changed

Each change has a test in `scripts/events/tests/test_event_methods.py`. Each
test was checked to fail when the old behaviour was restored.

1. **Missing daily returns were treated as zero** (`ret.fillna(0)`). That was a
   silent fallback in the merger pair legs.
   - The fix: `window_return` compounds across a gap only where CRSP's
     convention holds (the next return spans from the last valid price).
     `bridging_check` verified this on all 5 gaps of 10 days or less in the
     extract, to within 4e-7. The window's first and last prices must also
     exist. Otherwise the window is NaN, and that is counted.
   - Effect: none on any headline. 4 windows at T−21/63/126 were bridged
     validly; at T−1 the stricter rule drops 4 windows with no price on the
     entry day.
2. **The holdout was matched by ticker only.**
   - The permno match catches SBW→ESD (ESD is today's EMD).
   - It also shows that **the universe ticker EMD maps to three CRSP funds**
     inside the panel's window: permno 78011 to 2008, 79329 to 2016-12-16 and
     89970 since. The yfinance-keyed history in `data/cef/` may therefore
     splice three funds; this has not been checked against the panel [U].
   - All three permnos are now excluded.
3. **An acquirer with no CRSP name in force on the delisting date** (a fund
   created by the merger) silently took its first later name. It still does, but
   the row now says so: 35 events.
4. **Weekly returns of empty weeks were zero** in the term-CEF regression, and
   partial peer baskets were averaged silently.
   - Fixed (an empty week is NaN, and partial baskets are counted).
   - Effect: none. There were no empty weeks and no partial baskets in any
     window.
5. **The risk-free rate came from `data/riskfree_daily.parquet`**, which has no
   fetcher in the repo.
   - The re-run uses FRB DGS3MO from the R2 mirror. It agrees with the panel on
     all 10,861 shared dates.
   - The panel also carries 451 forward-filled weekday holidays before 2023,
     each accruing an extra day of T-bill at /252. That alone explains the
     0.02–0.08pp/yr differences above.
6. **Live discounts mixed dates.** The agent's DailyPricing snapshot used a
   2026-10-07 discount beside a 2026-10-08 price. The re-run uses CEFConnect's
   dated daily rows, so each discount is a price and a NAV of the same date.

## 5. The zero-trial gates

**G1c: event count with the 27 opened, clustered** (`merger_g1c_counts.csv`;
stock and stock-plus-cash mergers; a count, no returns). The gate passes at
≥30 independent groups.

| tier, 2010–22 | events | acquirer × completion date | completion date | acquirer | sponsor × year (heuristic) |
|---|---:|---:|---:|---:|---:|
| (a) no universe name | 192 | 115 | 84 | 101 | 67 |
| **(b) the 27 opened; the deployed 17 still out** | **206** | **122** | **88** | **107** | **69** |
| (c) every event | 238 | 136 | 96 | 114 | 73 |

**Reading:** G1c **passes** on every clustering, the most conservative giving
69 groups. Three caveats:
- **The priced sample is smaller.** With returns computable (no universe name),
  it is 167 events in 100 acquirer × date groups.
- **The usable sample today is far smaller.** Entry at announcement needs a
  date, and dates exist for only 12 groups until the EDGAR fetcher (0.7) runs.
- **2023–24 is counted only.** It adds 29 events (20 groups) under tier (b).

**G1a: borrow on acquirers** (`g1a/alpaca_g1a_summary_2026-10-11.json`; true on
2026-10-11 only). The gate passes if most acquirers are shortable.
- **Historical acquirers.** 34 of the 61 still active are shortable (56%), but
  only 7 of the 23 munis (30%). Munis are the class where the effect is
  measured: +148bp against −43bp.
- **Pending acquirers today: not measurable.**
  - Alpaca's corporate-actions feed listed one future-dated merger in the next
    two years (NSC→UNP), and no CEF or BDC. Its coverage of pending deals is
    partial at best [U].
  - EDGAR (0.7) is the source, and it waits on the team lead's SEC user-agent.
- **The nearest proxy: CEF and BDC mergers effective in the last 365 days.**
  There were 31 mergers (41 feed rows, deduplicated) with 16 acquirers. Today
  10 of those acquirers are shortable and 6 are not; 20 of the 31 mergers have
  a shortable acquirer. The BlackRock muni acquirers are shortable. NMZ
  (Nuveen), MFM and FAX (abrdn/Aberdeen), ASGI, TYG and HRZN are not.

**Reading:** G1a is **marginal overall and fails for munis**. Borrow flags moved
on 11 of 59 names in three days, so any pre-registration must re-read them on
the day (H14).

*Measured 2026-10-13 (`G1A_SHORTABILITY_2026-10-13.md`):*
- The pending acquirers are now read from EDGAR: 5 deals, 7 pairs.
- At Alpaca: munis 1 of 2 acquirers shortable; historical munis 7 of 23.
- **G1a fails for munis** and passes for taxable and equity.
- Alpaca's feed listed none of the pending pairs.

**G1b: the ex-ante sign of the spread from NAVs at announcement.** **Not
measurable today.** It needs the N-CSR / N-PORT NAV history of plan item 0.8.
The [V]-dated result above (−19bp) is a warning sign for it, not a measurement
of it.

## 6. Findings outside the table

- **Two deployed names were acquirers in 2026** (Alpaca corporate actions,
  [V] 2026-10-11):
  - MHD took BFK, BYM, MUE and BLE on 2026-02-09;
  - MQY took MQT, BKN and MYD on 2026-02-23.

  This bears on C1, the corporate-action filter: the live book held names
  whose share count and NAV changed by merger. It also offers a **probable
  explanation for SCALING §7.4's MQY share-count disagreement**: yfinance's
  71.8m against about 150.5m implied by a 13G of 2026-03-31. That explanation
  is [U] until a filing is read.
- **Alpaca's corporate-actions feed repeats actions.** The same pair appears
  with a rate differing in the sixth decimal, or a second effective date three
  days later (BXMX/DIAX→SPXX). Anything built on it must deduplicate.

## 7. Gaps (stated, not filled)

- **The announcement dates were not re-fetched.** They are the agent's: 6 [V]
  and 7 [S]. A merger trial needs plan 0.7, and 0.7 needs the team lead's SEC
  contact user-agent.
  *Closed 2026-10-12:* every deal is now dated from EDGAR
  (`EDGAR_EVENTS_2026-10-12.md` §3). On EDGAR dates the median is +86.5bp
  (N 167, 102 groups). The agent's 36 events give +15bp on EDGAR dates.
- **The filed exchange ratios (GGM, GPM) were not re-read.** Only the CRSP side
  reproduces.
- **"Paid NAV" at termination, and NAVs at merger announcement, need plan 0.8.**
- **The "$0.5m per deal" capacity has no formula.**
- **The term-CEF fund list, classes, targets ($9.85 etc.), peer baskets and
  JLS/JPT tender prices are the agent's hand-curated inputs [S]**
  (`term_pull_to_par.py::FUNDS`). The live term dates are also the agent's
  ([V] four, [S] seven). So is the census's tender-clause ticker list [S].
- **The other four analyses of item 0.9 are not covered here**: convertible
  issuance, VRP/IV, BDC release events and the specialists' betas.

## 8. Files

- **Scripts**:
  - `scripts/events/crsp_events.py`;
  - `scripts/events/merger_pairs.py`;
  - `scripts/events/acquirer_shortability.py`;
  - `scripts/events/term_pull_to_par.py`;
  - `scripts/events/fetch_term_cef_live.py`;
  - `scripts/data/term_cef_census.py` (filter fixed);
  - `scripts/events/tests/test_event_methods.py` (added to `pytest.ini`).
- **Tables**: everything else in `results/events/`. Sources are in
  `docs/REFERENCES.md` §12e.
- **Correction note**: the head of SCALING §7, and §7.4.


**Licensed rows are not in git (2026-10-11).** Row-level tables derived from CRSP
and TRACE (WRDS, licensed) are written by the scripts above but kept out of this
public repository (`.gitignore`). Only aggregates are tracked. Re-run the scripts
with R2 access to rebuild them.
