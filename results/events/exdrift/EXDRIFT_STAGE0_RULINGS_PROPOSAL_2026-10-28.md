# Ex-date drift (EVENTS trial 3), Stage 0: rulings proposal, one recommendation per flag class

**Date** 2026-10-28 · **For** the team lead, who rules · **From** the Stage-0 re-run on the Alpaca
fetch of 2026-10-27T21:38:45Z (`results/events/EXDRIFT_STAGE0_2026-10-27.md`, banner of
2026-10-28) · **Reproducer** `python3 scripts/events/exdrift_trial.py stage0` (offline; exit 2 =
halted) · **Flags** `results/events/exdrift/exdrift_stage0_flags_2026-10-27.csv` (657 rows; each
row's `recommended` column repeats the class recommendation below)

**The rulings file is not filled.** `exdrift_stage0_rulings_2026-10-27.csv` is the blank form, one
row per flag, with columns `ruling`, `ruled_by` and `ruled_on`. A class ruling below fills every row
of its class. `fit-k` and `open` refuse until every row is filled. **Nothing here was computed on a
2023+ return.** Every count is a date, a presence or an equality test.

## The proposal

| # | class (flags) | gate | recommended ruling | consequence for the test |
|---|---|---|---|---|
| 1 | `X2_source_invalid` (1) | **DG-X2 FAIL** | **Build a declaration source from the sponsors' own monthly releases**: a verified notice table for every test event, quotes re-found offline (`exdrift_sponsor_notices_2026-10-28.csv` is the template, 6 rows now). The releases are PIMCO's, BlackRock's, Nuveen's, DoubleLine's and AllianceBernstein's. By arithmetic that is about 5 releases a month for 46 months [U]. PIMCO's release fetches with the repo's `fetch_sponsor_notices.fetch` (verified 2026-10-28); the other sponsors' sites are untested. *Alternative:* CRSP's distribution table (`dclrdt`) to 2024-12-31, which needs your credential, plus sponsor notices for 2025–26 | Until this is ruled and built, rule 1 (declared by e−1) and the H-E declared calendar cannot run, and **the test cannot open**. On Alpaca's derived field, 32 events would have been excluded. With real declarations about two weeks ahead (PIMCO: 9 sessions before ex in the one release read), the declared calendar is close to the realised one [U] |
| 2 | `X1_amount_mismatch` (32, all BIT, 2023-01-12 → 2025-08-15) | DG-X1 | **Keep the 32 events.** Their ex-dates are confirmed by both sources. Use Alpaca's amount for BIT before 2025-08-19 in the report-only size strata | **None on any deciding statistic.** No held cell carries a distribution (§4.5 asserts it), so an amount enters no price-leg or NAV-leg P&L. The one exception is a calendar-surprise basket leg, which §4.3 prints separately |
| 3 | (DG-X3: no flag) | **DG-X3 PASS** | none needed | The premise of §4.2 holds on all 768 events: a short opened at e's close is never a holder of record |
| 4 | `X4_no_bar` (24) | DG-X4 | **Fill each close from Alpaca's raw SIP bar**, logged per cell, as C4's ruling of 2026-10-14 did. All 24 bars have a close and volume > 0 (presence only). At the opening, check Alpaca's bars against yfinance's on the adjacent sessions on one share basis, as C4 did. *Alternative:* exclude the 24 events and count them | Fill: **729** events on the realised calendar. Exclude: **705**, losing 24 events, all in 2026, on 5 sponsor ex-dates (02-12, 02-13, 02-18, 03-18, 09-15). Each missing close is the short's entry price, so without a fill those events cannot exist. The fill also restores those funds as basket legs on their ex-dates |
| 5 | `X4_split` (1: BIT 2025-08-19, factor 1.029) | DG-X4 | **Keep rule 3 (reading R1):** BIT's returns are masked within ±5 sessions and the 1 BIT event is excluded. Record that the "split" is in yfinance only: Alpaca's v1 returned no split record in the window (it was asked for split types). It is probably a yfinance adjustment factor, not a share split [U] | 1 event out; BIT leaves every basket for 11 sessions around 2025-08-19. The same yfinance factor is the likely cause of the 32 BIT amount mismatches (#2) [U] |
| 6 | `X5_nav_repeat_on_e` (37 events, 2023–25) | DG-X5 | **Exclude each from the NAV leg only, and count it.** NAV(e) = NAV(e−1) on an ex-date is a stale cum-distribution NAV (Yahoo serves a NAV dated D carrying D−1's value: `docs/DATA.md`, 2026-10-12) | Left in, each moves a distribution-sized NAV drop onto hold row e+1. That reads as the NAV falling with the price and **pushes the NAV control (stage 3) towards a kill**. The price leg is unaffected. Fit rate on the same test: 98 of 3,197 |
| 7 | `X5_nav_repeat` (552 cells: 194 on e+1, 179 on e+2, 179 on e+3) | DG-X5 | **On e+1 and e+2, book as is.** The leg's three-row sum depends, to first order, only on NAV(e) and NAV(e+3), so a repeat inside the window only shifts the move. **On e+3, exclude the event from the NAV leg, counted** (179 events). The test rate (0.240) lies above every fit era's (0.165–0.212), so these are not all cent-rounding. A CEFConnect check of the cells would settle it, but CEFConnect blocks scripted requests from this machine. It would be a run on the VM | A stale NAV(e+3) cuts the window by a day and pulls the NAV leg towards zero, which is towards **passing** stage 3, a bias for the trade. Excluding those events removes it, at the cost of NAV-leg sample size. The price leg is unaffected |
| 8 | `X6_FF6_uncovered` (French ends 2026-09-30; 4 of 935 sessions) | DG-X6 | **Wait for French's 202610 vintage** before the opening, which is waiting on #1 anyway. *Alternative:* run R-D4 on the 931 covered sessions and print the 4 | None on stages 1–4. Stage 5's regression loses 4 sessions under the alternative |
| 9 | R1 (rule 3 from the splits panel) | DG-X4 | Keep | 1 BIT event out (#5) |
| 10 | R2 (Alpaca v1 is DG-X1's second source) | DG-X1 | Keep. It matched all 769 ex-dates both ways and every record date. Note that the announcements endpoint fails as a declaration source (#1) | DG-X1 rests on Alpaca v1 alone for 2023–26 |
| 11 | R3 (amounts agree within $0.001; Alpaca summed per ex-date) | DG-X1 | Keep | 737 agree, 32 flagged (#2) |
| 12 | R4 (a declaration dated e−1 passes) | DG-X2 | Keep, applied to the sponsor-notice table of #1 | Decides rule 1 once #1 is built |
| 13 | R5 (bar checks on the event fund only; basket legs leave by the H-E rule) | DG-X4 | Keep | Basket legs without a bar are dropped mechanically and counted |
| 14 | R6 (NAV repeats) | DG-X5 | Superseded by #6 and #7 (by position, not as one class) | — |
| 15 | R7 (end frozen at ex-date 2026-10-12) | DG-X1 | Keep | The last event is e = 2026-10-01. The test window for returns ends 2026-10-06 |
| 16 | R8 (factor coverage) | DG-X6 | As #8 | — |
| 17 | R9 (k and the cap-binding share from `fit-k`) | DG-X7 | **Authorise `fit-k`** once every row is ruled. It forms fit P&L only, and must be committed before `open` | Required by §4.4 before the opening |

**Not flags.** 39 events have an H-E basket of fewer than 3 funds on the realised calendar. Rule 5
excludes them mechanically.

## Why DG-X2 fails (the evidence, dates only)

- **PIMCO's own release** is the PDF at
  `https://www.pimco.com/us/en/documents/1dd4ec77…?app=dot` (sha256 prefix `a836ccb8e7495b72`).
  It was fetched 2026-10-28 by `scripts/data/fetch_sponsor_notices.fetch`, and its quotes are
  re-found by `exdrift_trial.verify_notices`. It reads:
  - "NEW YORK, NY, October 1, 2025";
  - "to shareholders of record on October 14, 2025, with an ex-dividend date of October 14, 2025";
  - PCN, PTY, PHK, PFN, PDI and PDO, each "(NYSE: …)".
- **Alpaca's announcement** gives `declaration_date` 2025-10-12 for all six.
- **The field follows the record date.** Weekdays from Alpaca's "declaration" to the record date,
  over all 785 announcements: 2 on 688; 1 on 86; 3 on 5; −1 (after the record date) on 6. It also
  falls on a weekend 60 times.

## Separately: the 24 empty-close rows in `data/cef/cef_prices.parquet`, a systematic fetch fault

**What the rows are.** All 24 are present in the panel with OHLC empty and volume 0, each on that
fund's own ex-date. The panel holds no other empty-close row for the 17.

**Where they come from: yfinance's own output.** `yfinance.utils.safe_merge_dfs` (0.2.66, the
pinned version) handles a dividend dated after the last price row of the response: "Adding
out-of-range Dividends … in new prices row of NaNs", built as `{OHLC: NaN, 'Volume': 0}`, for
`interval='1d'`. So Yahoo's response for that fetch carried the ex-date's dividend but no bar for
the ex-date yet.

**The fetch path: `scripts/cef/fetch_daily.py`, `_refresh_locked`.** It is the live path, run by
the session (step 1) and by `quantt/collect` `step_prices_nav` every 30 minutes. It calls
`yf.Ticker(tk).history(period="6mo", auto_adjust=False)`, whose default is `actions=True`, and then:
- writes every row without testing the close;
- keeps the newest fetch's row for each date (`drop_duplicates(keep="last")`), so an empty row
  replaces a good bar fetched earlier;
- its `--require-asof` check counts a ticker as having a close by row presence
  (`P.loc[P["date"] == asof, "ticker"]`), so an empty row passes the as-of gate.

**Evidence that it is systematic, not random.**
- All 24 rows sit on sponsor-wide ex-dates: PIMCO's six on 2026-02-12; seven BlackRock and Nuveen
  funds on 02-13; nine on 09-15; DSL on 02-18 and 03-18.
- The 2026-09-28 backup of the panel (`cef_prices.parquet.pre-20261015.bak`) already held the
  February and March rows. It had good bars on 09-15, which the refresh of 2026-10-15 replaced with
  empty rows.
- Today yfinance returns a full bar (a close, volume > 0) on all 9 cells re-checked (PTY, PCN, NAD
  ×2, HYT ×2, DSL ×2, MHD), so Yahoo's history is now whole and the empty rows persist only in the
  panel.

**What is [U].** Why a 6-month refresh on 2026-10-15 drew an out-of-range dividend for 09-15 is
unexplained: the merge rule needs the response's price rows to end before 09-15. Whether prod's
panel on the VM holds the same rows was not checked. **No live-path file was changed.**
