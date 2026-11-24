# NAV tenders (EVENTS trial 2): Stage 0, part A, and the halt before any return

**Date** 2026-10-19 · **Pre-registration** `results/events/PREREG_NAV_TENDER_2026-10-19.md`
(approved 2026-10-19, all twelve defaults, N = 6) · **Counter** EVENTS 2, unchanged (it
moved on approval) · **Author** research agent, branch `trial-events-navtender`

> **Status: HALTED in Stage 0, before any price or return was read.** Part A (EDGAR)
> ran and is recorded here. Part B (DG-NT-3 to DG-NT-6, the quality screen, the hedge
> and beta) needs CRSP extracts and an Alpaca read that load credentials, which agents
> never do. The team lead runs one staging command (§5). After that, Stage 0 part B
> writes the rulings form and stops again until every flag has a ruling (prereg skill
> §4b). **No P&L, k, Sharpe or hedged return exists for any event. The 2023-01-01
> holdout was not touched. No CRSP row was read.**

Reproducer: `python3 scripts/events/nav_tender_trial.py stage0 --edgar-only` (run
2026-10-19; exit 2 = the halt). Outputs, all tracked, EDGAR facts and counts only:

| file | holds |
|---|---|
| `results/events/nav_tender/stage0_2026-10-19.json` | counts by period, the 20% gate, the halt |
| `results/events/nav_tender/stage0_events_2026-10-19.csv` | per event: day 0, the filings read, expiry, pricing session, P_final, pi and how each was read |
| `results/events/nav_tender/stage0_flags_2026-10-19.csv` | the Stage-0 flags awaiting rulings (part A's 72; see the correction in §3) |
| `results/events/nav_tender/dg_nt1_readings_2026-10-19.csv` | the DG-NT-1 hand readings, each with a verbatim quote the script checks against the filing |

Tests: `python3 -m pytest scripts/events/tests/test_nav_tender_trial.py` (synthetic
data only, including a tender with a known payoff, the shift(2) alignment and
an end-to-end run of part B and the fit on a fake CRSP).

## 1. The event set and the 20% gate (DG-NT-2): PASS, 26 of 134 unread

| period | events | groups | completed | terminated | unread | re-dated |
|---|---:|---:|---:|---:|---:|---:|
| fit | 134 | 120 | 108 | 0 | **26** | 7 |
| gap | 1 | 1 | 1 | 0 | 0 | 0 |
| holdout (counts only) | 42 | 21 | 28 | 0 | 14 | not yet read |

The 44 `cef_universe.csv` funds (8 events) and the 4 merger-open fit events are excluded
first, as declared. The fit is 134 events in 120 groups, exactly the pre-registration's
proxy count (§11).

**26 of 134 fit events (19.4%) have an unread outcome or P_final, at or under the 20%
line, so the gate passes and part B may proceed.** The margin is one event: 27 would
halt the trial with no trial spent. Part B re-reads every event after the staging fills
the 55 intermediate amendments the cache lacks (47 fit events have at least one), so
the count is recomputed there and can still move.

The unread 26, by reason:

| reason | n | events |
|---|---:|---|
| no SC TO-I/A after the offer document | 10 | EEA 2010-12, GFY 2010-01, SCD 2011-03, AEF 2018-04, MXE 2018-01, 2019-01, 2019-12, SPE 2016-09, 2022-03, CHN 2019-01 |
| pi unread (the census reader declares a gap) | 8 | HIX, EHI 2020-08; WIA 2020-11; GLV, GLQ, GLO 2017-07; IDE 2021-02; SVVC 2019-12 |
| pi and P_final unread (joint releases) | 6 | VLT, VTA 2019-10; NMA, NQU 2014-08; EVF 2021-05; FTP 2017-06 |
| P_final unread (no price in the results filing) | 2 | ERC 2017-04, NRO 2011-10 |

**Second method.** `scripts/events/nav_tender_feasibility.py` (the pre-registration's
zero-trial script, which never reads a filing) gives the same 134-event fit set and the
same 24 events with pi unread. Stage 0's re-dating and re-reading changed neither. The
other 2 are the P_final gaps, each confirmed by hand: neither filing prints a price.

## 2. What Stage 0 read

**DG-NT-1 (day 0).** The 47 fit events whose offer document came more than 60 days after
day 0, or that followed a triggered discount-programme window, were read by hand:

- 40 day-0 filings announce a definite tender;
- 7 announced a tender that still depended on a future discount average, a future
  vote or a board's later decision, and are re-dated to the filing that announced the
  decided tender, by 45 to 112 calendar days:

| event | day 0 moves | why |
|---|---|---|
| Thai Fund 2013-05-31 | → 2013-07-19 | subject to the stockholder vote on restructuring |
| HERZ 2021-08-20 | → 2021-10-04 | policy "subject to annual Board approval" |
| IFN 2013-11-18 | → 2014-02-19 | stockholder vote, then the Board's authorisation |
| NRO 2016-07-26 | → 2016-10-04 | discount window still open to 2016-09-30 |
| EVG 2021-03-09 | → 2021-06-29 (offer document) | conditioned on a shareholder vote |
| MCN 2018-06-29 | → 2018-10-10 (offer document) | to follow a merger needing a vote; the merger-open screen missed it |
| GFY 2010-01-12 | → 2010-04-05 | a twelve-week measuring period "to determine whether to proceed" |

The 15 flagged holdout events are read at the holdout's own Stage 0. Every quote is in
the readings file, and the script checks each against its filing. Day 0 is then the first
session whose 22:00 ET decision follows the filing's `observed_at`, taken from the SEC
header (§4.2).

**DG-NT-2 (terms and outcome), the 108 completed fit events.**

- **Final expiry:**
  - read from the results filing for 105;
  - from the offer document for 3 (no extension found).
  - Five differ from the census's offer expiry: PCF, FGF, FGI, RGT and GGO, all
    extended.
- **Pricing session X_p:**
  - the NAV date printed with the final price for 68;
  - the offer's terms for 23;
  - the expiry, as the pre-registration states, for 17.
  - X_p falls 0 to 5 calendar days after the expiry. DDF 2014's 5 days are its offer's
    stated pricing date, and the event is flagged.
- **P_final:**
  - read by narrative statement, results table, or a fund-anchored statement in a joint
    release, all statements agreeing;
  - the filing-fee block is never read unless it is dated at the final expiry.
  - Check against the offer's stated NAV: P_final / (k% × NAV) has median 1.005
    (n 101, range 0.90 to 1.22, the energy funds of autumn 2022 at the top). The one
    above 1.15, NDP 2022, is flagged.
- **pi:** the census's reader, unchanged, on each offer's own last amendment. One event
  uses the second method only, labelled.
- **Episodes that hold two offers.** The census paired 6 of the 8 such fit events with a
  later offer's results. Here each is read on its own offer's last amendment. All 6 are
  read: each release prints only the fund's own ticker, so the census's joint-release
  test cannot fire, whatever CRSP's ticker list holds.
- **No offer in the fit was terminated or withdrawn.**

## 3. The flags awaiting rulings (part A: 72)

> **Corrected 2026-10-20.** This heading and the hand-back said 65. That was the
> line count of an earlier run's flag file. The committed file has 72 rows, the sum of
> this table.

| check | fit | holdout | what the team lead rules |
|---|---:|---:|---|
| `dg1_definite`, `dg1_redated` | 47 | — | each DG-NT-1 reading (§2) |
| `quality_episode_far` | 8 | 11 | the episode holds more than one offer; the event is its first (§4.4) |
| `time_key` | 1 | — | DDF 2017: EDGAR's filing date precedes acceptance; observed_at = acceptance by the max rule |
| `pricing_session` | 1 | — | DDF 2014 priced 3 sessions after expiry (its own stated pricing date) |
| `pfinal_vs_offer_nav` | 1 | — | NDP 2022 at 1.22 × the offer's NAV |
| `spec_beta_window` | 1 (all) | | `e1_etf_hedge_gate.windows` refuses a test window of 0, so the script fits beta on 252 spans ending 43 valid sessions before day 0, one more than §5.2's 42. Keep, or use est = 251 on (s_est, e] |
| `spec_results_filing` | 1 (all) | | three of the 10 no-results events published results only in a post-expiry SC TO-C press release (EEA 2010, GFY 2010, SCD 2011). Keep them unread (the census's reader, §4.3), or admit the press release |
| `spec_per_event_units` | 1 (all) | | stages 1 and 3 use x_e = u_e × (fund + hedge P&L per unit notional), mean over events, `cluster_t` by sponsor × day 0, the literal "raw units". The mean of group means is printed beside it |

Part B adds the CRSP flags:

- `quality_abs_ret` and `quality_no_close`;
- `quality_delisted_in_hold`, if any;
- `spec_dg4_reads`, if the Alpaca and IBKR reads are not from one date.

The rulings file is `results/events/nav_tender/nav_tender_stage0_rulings_2026-10-19.csv`.
Part B writes its blank form, and `require_stage0_rulings` refuses to form any P&L until
every row carries a ruling, `ruled_by` and `ruled_on`. Stage 0's P&L-dependent items
(k and the cap-binding share) come after that block, because §4b forbids P&L before the
rulings.

## 4. Divergences and provenance, stated

- **EDGAR documents.** EDGAR needs `SEC_USER_AGENT` from the env file, which agents never
  read. So the 937 public filings read here were clone-copied from sibling worktrees'
  gitignored EDGAR caches (the census's and the N1 census's), with a sha256 manifest in
  this worktree's gitignored cache. 55 intermediate amendments of fit events (82 in all)
  were in no cache. The staging run fetches them, and part B re-reads everything.
- **CRSP.** No CRSP file was copied or read. The census worktree's cache does hold
  pre-2023 daily rows for all 139 pre-2023 tender permnos, by its manifest. That is
  licensed data outside this worktree, so it was not used. The team lead may authorise
  it in place of the R2 pull.
- **DG-NT-4.** The pre-registration's own reads were not one date: Alpaca on 2026-10-18,
  IBKR's file on 2026-10-19. The staging step reads Alpaca with the cef paper key beside
  a fresh IBKR file.

## 5. What the team lead must run, then rule

In this worktree (`.claude/worktrees/trial-events-navtender`):

```bash
curl -s -o /tmp/usa.txt https://www.interactivebrokers.com/shortstock/usa.txt   # public file
export QUANTT_ENV_FILE=/abs/path/config/.env                                     # SEC agent, R2, Alpaca cef key
python3 scripts/events/nav_tender_trial.py stage --ibkr /tmp/usa.txt
```

This command:

- fetches the uncached EDGAR amendments;
- pulls CRSP names, delistings and one batch of pre-2023 `dsf` rows (R2);
- fetches the French factors;
- writes `results/events/nav_tender/dg_nt4_reads.json` (Alpaca flags and IBKR rows for
  the hedge ETFs).

It computes no return. Then:

1. `python3 scripts/events/nav_tender_trial.py stage0` runs part B and writes the
   rulings form.
2. The team lead rules every row of the form.
3. `fit` runs stages 1 to 5. Its verdict is committed before the holdout reader will run.
4. The holdout's own 2023-24 CRSP pull is `stage --holdout`. It refuses until the fit
   verdict is committed.

**The holdout's count is reported now, and decides nothing yet.** 14 of its 42 events
(33%) are unread on today's reading. If that stands at the holdout's Stage 0, the
holdout halts under §4.3 and is reported, and the fit verdict stands (§11.1).

## 6. Proposed rulings, 2026-10-20 (zero trials; nothing ruled yet)

The form is `results/events/nav_tender/nav_tender_stage0_rulings_2026-10-19.csv`, one
row per part-A flag (72). Each row's `ruling` holds the recommendation and its reason.
`ruled_by` and `ruled_on` are blank, so `require_stage0_rulings` still refuses until
the team lead signs.

| class | rows | recommendation |
|---|---:|---|
| R1 day 0 kept | 31 | accept: the census's day-0 filing announces a definite tender (quote checked) |
| R2 day 0 kept, closer call | 9 | accept; each row says why (KEF 2010, DSU 2019 and 2020, HIX and EHI 2020, AVK and AGC 2017, PHD 2020, NBB 2018) |
| R3 re-dated | 6 | accept the move to the filing that announces the decided tender |
| R3b MCN 2018, re-dated | 1 | accept the re-dating and keep the event. Its merger episode closed (2018-08-29) before the re-dated day 0, so it does not overlap E1. Alternative: exclude under §1 |
| R4 episode holds several offers | 19 | genuine, no action; reported as a robustness row (§4.4) |
| R5 DDF 2017 time key; DDF 2014 pricing date; NDP 2022 P_final | 3 | accept as read |
| M1 beta window | 1 | keep h = 1 (ends 43 valid sessions before day 0; windows() unchanged) |
| M2 results filing | 1 | keep: the last SC TO-I/A only; the 3 SC TO-C-only events stay unread. The gate passes either way |
| M3 per-event units | 1 | keep the literal u-weighted x_e with cluster_t; group means printed beside it |

A check made for R3b: no event's merger-open status changes when the screen is applied at
the re-dated day 0 instead of the census's day 0.

**CRSP: reuse the census worktree's cache, or pull from R2?** Recommendation: **pull from
R2 through `stage`.** The team lead runs `stage` anyway, for the SEC agent and the Alpaca
key, so the pull costs one more query. What reuse would and would not change:

- **Vintage:** the same R2 mirror (`crsp_a_stock`, `dsf` to 2024-12-31,
  `results/data/R2_CATALOG.md`), pulled 2026-10-11 to 2026-10-18. Whether the mirror
  changed since then cannot be checked without a pull.
- **Fields:** identical. Both go through the same `crsp_events.daily` SQL (permno, date,
  prc, ret, retx, vol, shrout, cfacpr), with the same `date < 2023-01-01` cut. The
  delisting and name tables are the same unhashed extracts.
- **Permno mapping:** not reused either way. The trial re-runs the census's `CrspMap` on
  its own (re-dated) day 0. The cache only has to contain those permnos; a missing one
  halts part B by name.
- **Mechanics:** the cache's extracts are separate batches named by other permno lists.
  `crsp_events.daily` would miss them, so reuse needs new assembly code on the data path,
  with its own manifest.
- **Provenance:** the extracts are licensed data that another agent pulled for a
  zero-trial census, outside this worktree. Reusing them needs the team lead's explicit
  authorisation.

**DG-NT-4 without a same-day Alpaca read?** **The pre-registration requires one:** §4.4 says
"Alpaca `GET /v2/assets/{symbol}` (read-only, cef paper key) and IBKR's public
`usa.txt`, read the same day, with their stamps". The committed Alpaca probe snapshots
(`results/ops/alpaca_probe/*_cef.json`, the last 2026-10-15) record the book's own
account and assets, not the hedge ETFs, so they cannot supply the flags. The only tracked
read of all 52 hedge symbols is the census's (2026-10-18T22:33Z,
`cef_corp_action_summary.json`), and no IBKR file is stamped that day. Pairing them with
a later IBKR file is a deviation. `stage0` would flag it (`spec_dg4_reads`), and the team
lead would have to rule on it. On that read:

- every non-muni primary was shortable at Alpaca;
- MUB was not, so the 11 muni fit events would route to IBKR at the file's fee.

Recommendation: the same-day read inside `stage`, as declared.

## 7. Stage 0 part B, 2026-10-20: one new flag stands between Stage 0 and the fit

On 2026-10-20 the team lead accepted all 72 recommended rulings (commit `2dbf949`) and
ran `stage --ibkr`, which exited 0. It wrote:

- **CRSP:** names, delistings and one batch of fit `dsf` rows for 125 permnos, all of
  them dated before 2023 (pulled 2026-10-20T20:17-20:19Z;
  `results/events/_cache_crsp/_manifest.json`, gitignored).
- **DG-NT-4:** Alpaca's flags for all 52 hedge ETFs, read 2026-10-20T20:19:40Z, beside
  IBKR's file stamped 2026-10-20 16:10:37: one date, as §4.4 requires
  (`results/events/nav_tender/dg_nt4_reads.json`). Five ETFs were not shortable at
  Alpaca: HYD, MUB, PGX, TFI and VTEB. MUB's IBKR fee read 10.29%/yr; it was 7.73% in
  the pre-registration's 2026-10-19 file. The borrow line uses DG-NT-4's date.
- **French factors:** vintage 202608, to 2026-08-31.
- **EDGAR:** the 82 filings the cache lacked. None is missing now.

Then `python3 scripts/events/nav_tender_trial.py stage0` ran parts A and B on 2026-10-20
and exited 2, at the rulings block.

**Part A, re-read with every amendment: unchanged.**

- The gate is still 26 of 134 fit events unread (19.4%): PASS.
- Holdout count: 14 of 42 unread.
- No expiry, pricing session, P_final, outcome or period moved.
- The joint-release rule now runs on CRSP's ticker list. With it, the census's reader
  reproduces the census's pro-ration reading on every census filing, to float
  precision. That is the reader checked a second way.

**Part B, on the 108 read fit events:**

- the universe check passed (108 events, 44 tickers, 46 permnos);
- no event fails the election cut-off, is blocked by one-position-per-fund, or lacks a
  permno;
- 4 are excluded for no beta history (§5.2), all funds listed within months of their
  tender: DRA 2014-09, 2015-03 and 2015-10, and JGH 2014-11;
- **104 events in 96 groups are traded;**
- 8 events are hedged with MUB at IBKR;
- beta's median is 0.90 (10th to 90th percentile 0.60 to 1.41);
- no return inside a hold needed bridging, none exceeds 50%, and no fund delisted inside
  a hold;
- CRSP's SPY dates match the NYSE calendar from 2008;
- the factors cover 2009-2022 (3,524 rows).

No P&L, k or Sharpe was formed. Those come after the rulings block.

**The one new flag** is `quality_no_close` for GGO on 2021-10-08:

- CRSP has no closing trade on GGO's exit session and prices it at the bid/ask average;
- the offer was for any and all shares, with 97% of those tendered accepted, so the
  residual sold that day is 3% of the original notional;
- **recommended:** genuine, no action. The event stays in the headline and is left out of
  §4.4's quality-screen robustness row.

The row is appended to the rulings file with `ruled_by` and `ruled_on` blank. The 72
signed rows are unchanged, and `require_stage0_rulings` now refuses on that row alone.

**Not a block, but before the fit:** the script still lacks some rows the
pre-registration reports and never decides on. Recommendation: add them, tested on
synthetic data, before the one fit run, so that run carries them:

- R-BOOK (§9);
- the mechanism slope (§8);
- the capacity block (§10);
- the residual-lag rows at 0 and 10 sessions;
- the quality-screen-removed row;
- the IEF-for-muni hedge row.
