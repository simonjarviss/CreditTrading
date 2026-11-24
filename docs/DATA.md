# Data — which source feeds what

**Written 2026-09-28 (branch `alpaca-runner`).** This file says where each kind of data
comes from and which code reads it. It is not a place to learn figures from: every
date or count below names the run that measured it. Re-run that script before you
quote one. **Stale is a form of wrong** (`CLAUDE.md`).

## 1. The one rule

**R2 is never on the live path.** The live sleeve decides on `data/cef/*.parquet`, and
nothing under `quantt/` or `src/deploy/` imports `src/data/` or `scripts/data/`.
`src/data/tests/test_r2.py::test_live_path_never_imports_r2` fails if either does
(`docs/RUNNER.md`, module boundaries). The reason: the mirror is refreshed on WRDS's
schedule, which nobody on this desk controls. A session that read it would be deciding
on a panel whose last date is somebody else's choice.

## 2. Sources

| use | source | code | notes |
|---|---|---|---|
| **Live: prices** the sleeve decides on | yfinance `Ticker(tk).history(auto_adjust=False)` | `scripts/cef/fetch_daily.py` → `data/cef/cef_prices.parquet` | Only one source. §4 is the first independent check of it. |
| **Live: NAV** | yfinance NAV symbol `X<TK>X`, with CEFConnect's dated row as an explicit, logged fallback (`--nav-fallback cefconnect`, every fill written to `data/cef/nav_fallback_log.csv`) | `scripts/cef/fetch_daily.py` → `data/cef/cef_nav.parquet` | The session runs it with `--require-asof`. Stale data never trades (`docs/RUNNER.md` step 1). **Correction 2026-10-12:** that holds for a missing date, not a stale value. Yahoo serves a row dated D carrying D−1's NAV, and `--require-asof` passes it; on the laptop's paper sessions 28 of 73 checkable name-days were decided on such a row (`results/cef/LIVE_NAV_QUALITY_2026-10-12.md` §5). **From 2026-10-13** the session can check the value too: the stale-NAV gate (`quantt/session/nav_gate.py`; `docs/RUNNER.md` "As built (2026-10-13)") checks a NAV(D) equal to the previous NAV or to CEFConnect's NAV(D−1). It replaces a stale copy with CEFConnect's NAV, logged as `cefconnect_stale_copy`, or defers an unverified name to the morning backstop and, from the final pre-send check, holds it at its current shares. `data.stale_nav` in the book json sets the mode: `report` only records, `on` acts. |
| **Research / backtest** | Cloudflare R2 bucket, a WRDS mirror | `src/data/r2.py` (DuckDB over httpfs, read-only) | §3. Never live. |
| **Research: equity, preferred and multi-asset CEFs** (plan trial C4; never live) | yfinance price and NAV (NAV symbol from CEFConnect's `NavTicker`, not assumed `X<TK>X`); CEFConnect `pricinghistory` (`1Y` daily, `All` weekly) as the NAV check; CRSP through R2 as the price check | `scripts/data/cef_families_universe.py`, `fetch_cef_families_yf.py`, `fetch_cef_families_cefconnect.py`, `stage_crsp_cef_families.py`, `cef_families_quality.py` → `data/cef_families/` (live schema; never `data/cef/`) | No `data/cef/cef_universe.csv` name enters it. Known vendor defects, measured 2026-10-12, are in `results/cef/CEF_FAMILIES_DATA_2026-10-12.md` and `docs/REFERENCES.md` §12h. |
| **C4 on paper: prices, NAV, distributions** (DARK: plan step 3, 2026-10-29; nothing schedules it yet) | yfinance price and NAV for the 74 frozen funds, the NAV symbol from the committed map `results/cef/c4/c4_nav_symbols_2026-10-14.csv` (the symbol the families panel was built from: CEFConnect's `NavTicker` for 73, `X<TK>X` for EVT); yfinance actions for distributions. **No CEFConnect** (team lead, 2026-10-28): the sleeve's NAV-repeat mask M1 handles a stale NAV | `scripts/cef/fetch_daily.py --data-book c4`, `scripts/fetch_cef_distributions.py --data-book c4`, `python3 -m quantt.collect --book c4` → `data/cef_c4/` (live schema; its own lock `data/cef_c4/.fetch.lock`) | Books and paths in `scripts/cef/data_books.py`. First seeded from `data/cef_families/` by its `seed-c4` command (its docstring, SEED; not yet run). Without `--data-book` every fetcher is the core's, unchanged. |
| **Broker truth** (positions, fills, tradability, shortability) | Alpaca Trading API, paper | `quantt/broker/` | The authority on our accounts (`CLAUDE.md` data rule 2). |
| **Distributions for the third P&L line** | Alpaca Market Data API, corporate actions (`cash_dividend`, `capital_gains_distribution`), cross-checked against the yfinance panel | `AlpacaClient.distributions` → `quantt/session/dist_score.py` → `<state>/distribution_scores.csv` | Lists declared ex-dates weeks ahead (measured 2026-10-09: ex-dates to 2026-12-11 listed). Alpaca does not guarantee timeliness, so absence alone is not a zero: a zero also needs the yfinance panel file rewritten after the close of the session following D. Hence each day is scored two sessions late. |
| **Official closes, cross-check** | Alpaca Market Data API, closing-auction prints (condition M, primary exchange) | `quantt/collect` → `data/cef/alpaca_official_close.parquet` (§5) | A second live-era price source beside yfinance. The auction prints are also the second P&L score (`docs/RUNNER.md`, verify step). CEF coverage on the Basic plan is **not yet measured** over any run. |

The other files in `data/cef/` (distributions, borrow, splits, universe, facts) have
their own fetchers. This file does not describe them.

**yfinance distributions are rounded to 3 decimals** (measured 2026-10-09). On
the 13 names over June to August 2026, 28 of the 40 events common to the
yfinance panel and Alpaca's corporate actions differed by ≤ 0.0005 per share,
e.g. MHD 0.0595 vs 0.060, and none differed by more. 77% of the panel's amounts
have exactly 3 decimals. The research total-return panel therefore carries
rounding of up to 0.0005 per share per event. That is small, but it is not zero.

## 3. The R2 mirror

### Layout

```
s3://<bucket>/wrds/<schema>/<table>.parquet          one file per WRDS table
s3://<bucket>/options/<SYM>/tick/<YYYY-MM>.parquet   one file per underlying-month
```

`src/data/r2.py` builds both paths: `r2_path(schema, table)` and
`options_path(SYM, "YYYY-MM")`. It validates each identifier before it goes into SQL.

### What is in it

**`results/data/R2_CATALOG.md` is the inventory.** Since 2026-11-09 it is git-ignored,
because this repository is public, so it exists only on a machine that has generated
it. Generate it with
`python3 scripts/data/r2_catalog.py` (read-only, about 2 minutes). For each curated
table it gives the columns, the row count and the min/max of every DATE-typed column.
It lists every object under the research schemas, and it enumerates every options
underlying present rather than trusting a remembered list. It exits 1 if a curated
table is absent.

As measured by that run at **2026-09-28 20:31 UTC** [V]. The option-underlying table is
from the rerun at about 20:40 UTC the same day. True on that date only:

| table | what research uses it for | date coverage |
|---|---|---|
| `crsp_a_stock.dsf` | daily prices; the independent check in §4 | 1925-12-31 .. **2024-12-31** |
| `crsp_a_stock.stocknames`, `dsenames` | ticker → PERMNO by date range | to 2024-12-31 |
| `crsp_a_stock.dsf_v2`, `stocknames_v2`, `stk*` | CRSP's newer CIZ-format tables, also present | not yet described |
| `crsp_q_mutualfunds.daily_nav` | fund NAVs (`crsp_fundno`, `caldt`, `dnav`) | 1998-09-01 .. 2026-03-31 |
| `ff_all.factors_daily` | Fama-French 3 factors + momentum | 1926-07-01 .. 2026-04-30 |
| `frb_all.rates_daily` | Fed H.15-style rates, swap rates, ICE BofA OAS/yield series | 1954-01-04 .. 2025-02-13 |
| `trace_enhanced.*`, `trace_standard.*` | corporate bond trades | listed, not yet described |
| `options/{SPY,QQQ}/tick` | option ticks | 2014-06 .. 2026-07 |
| `options/{GLD,IWM,SLV}/tick` | option ticks | 2023-10 .. 2026-07 |
| `options/TLT/tick` | option ticks | 2023-11 .. 2026-07 |

The following are consequences of those dates. Re-measure before you act on any of them.

- The CRSP stock file stops at 2024-12-31. **It cannot check any price in 2025–26.**
  That covers most of the 2023-01-01 time holdout's live years.
  *(Corrected 2026-10-19: true of the legacy SIZ file `dsf` only. CRSP's CIZ files in
  the same schema (`dsf_v2`, `stkdlysecuritydata`, `stkdelists`, `stkdistributions`,
  `stkshares`) run to **2025-12-31**: French's library says the legacy format was
  "discontinued after the December 2024 data release". So CRSP can check 2025 prices,
  on the CIZ files. The mirror also holds far more than this table: **1,146 tables in
  81 schemas** (Compustat, IBES, Thomson insiders and 13F, SDC M&A and New Issues,
  MSRB trades, OTC end-of-day, FJC bankruptcies and others), written as one snapshot
  2026-06-26 → 07-03 and not refreshed since. Inventory:
  `results/events/ssx/ssx_data/R2_FULL_INVENTORY_2026-10-19.md`, by
  `python3 scripts/events/ssx/ssx_data_r2_inventory.py` [V]. `docs/REFERENCES.md` §12ssx.
  Git-ignored since 2026-11-09, like the catalogue above: run the script to get it.)*
- The only options underlyings present are SPY, QQQ, TLT, IWM, GLD and SLV. **There is no
  HYG or LQD.** `docs/SYSTEM.md` names "the R2 trades source if it carries HYG/LQD/TLT"
  for options. As of this run, R2 carries only TLT of those three.
- **`crsp_q_mutualfunds` does not hold our CEFs** (measured 2026-10-08 by
  `python3 scripts/data/r2_signal_coverage.py` → `results/data/R2_SIGNAL_COVERAGE.md`).
  None of the 44 CEF tickers appears in `fund_hdr` or `fund_hdr_hist`, so it is not an
  independent NAV source. It does hold the **open-end** credit funds, by Lipper class.
  Those funds share the CEFs' retail base, which makes them a candidate flow series
  (`results/cef/RESEARCH_AGENDA_2026-10-08.md` §4, parked). *Until 2026-10-08 this bullet
  read "not measured".*

### Credentials

The keys go in the env file `$QUANTT_ENV_FILE`, or `<repo>/config/.env` when that is
unset. Both are absolute paths, never relative to the working directory. The file must
set all four of `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` and
`R2_BUCKET`. A missing one raises and names the variable. There are no defaults and no
alias names, and `os.environ` is not consulted. The file is read with `dotenv_values`,
so it is never exported into the environment.

The connection is a DuckDB **TEMPORARY secret scoped to `s3://<bucket>`**. It lives in
memory only and applies to nothing else. There are no global `SET s3_*` statements.

```bash
python3 -m src.data.r2 --check-keys     # SET / NOT SET per variable; no network, no values
```

Agents never open the env file (`CLAUDE.md` order-path rule 5). On 2026-09-28,
python-dotenv warned that it `could not parse statement starting at line 14` of
`config/.env`. The four R2 variables still loaded. Line 14 is for the team lead to look
at.

## 4. Independent check: the live price panel against CRSP

`python3 scripts/data/cef_crosscheck_crsp.py` compares
`data/cef/cef_prices.parquet` closes for the frozen universe (`scripts/cef/spec.py`
`UNIVERSE`) against CRSP `dsf.prc`, mapping ticker → PERMNO through `stocknames` date
ranges. It never averages the two sources and never picks one. It writes
`results/data/cef_crosscheck_crsp_<date>.md`, plus a CSV of every row that did not agree.
It exits 1 unless every row maps and every comparable raw close agrees within $0.005.
The docstring explains the categories: a negative CRSP `prc` means no closing trade, so
it is never compared as a close.

**First run: 2026-09-28 20:37 UTC** [V]. The panel's last date was 2026-09-21 and CRSP's
last date was 2024-12-31. Verdict **FAIL**, for these findings (full detail in the report):

- All 13 names mapped to one PERMNO each. Every mapped PERMNO's name records carry CRSP
  share code 14 or 44. No row was ambiguous. Six tickers (BIT, DSL, PCN, PDI, PDO, PFN) were
  recycled from unrelated earlier issuers with share code 10/11 (e.g. DSL = Downey
  Financial until 2008). PDI was also Putnam Dividend Income Fund until 2001. The
  date-range join correctly left all of those out.
- Raw closes agree on all but 131 of 65,664 compared rows. 98 of the 131 differ by
  between $0.005 and $0.0051: one source prints a sub-cent or half-cent price. The
  largest are AWF in 1994–2000 (up to $0.125, the fractional-tick era), PCN and JFR in
  the days right after their IPOs (up to $0.05), and scattered single days of up to $0.03.
- **JFR 2004-03-25**: the panel has a zero-volume bar (close 15.96) one day before
  CRSP's first JFR date. That looks like a phantom pre-listing bar in the yfinance panel.
- MHD has 3 CRSP no-trade days (1997, 2001) on which the panel shows a close.
- The panel's closes match CRSP **raw** prices, not CRSP's `cfacpr`-adjusted prices. That
  is visible for HYT (`cfacpr` 1.003397 over 2004–2018) and PFN (a `cfacpr` change after
  2023-05-26). So the panel is **not** adjusted for those events. Which corporate action
  each `cfacpr` step reflects is not established here.

## 5. The nightly collector (`quantt/collect`, 2026-09-29)

`python3 -m quantt.collect --book cef` records every trading day, whether or not the
book traded. It runs every 30 minutes, all day. When the day is
already complete it reads Alpaca's clock and calendar, prints `IDLE <D> complete` and
exits 0. Prod schedules it every 30 minutes at :10 and :40 (`quantt/deploy/`: a launchd job
on the laptop, a systemd timer on the VM). The module docstring has the full design.

- **Data day D.** D is the latest date that both Alpaca's `/v2/calendar` and
  `ops/schedule/nyse_calendar` call a trading day, and whose close + 45 minutes has
  passed by Alpaca's clock. If the two calendars disagree, the run raises and names both.
- **Steps.** Each step is idempotent and recorded in
  `$QUANTT_STATE_DIR/data/<D>/status.json`. A failed step is retried next slot, and a
  step that completed is not run again.
  1. `prices_nav` runs `fetch_daily.py --require-asof D`, with the session's flags and a
     15-minute timeout.
  2. `nav_crosscheck` compares each deployed name's panel NAV with CEFConnect.
  3. `official_closes` fetches the Alpaca auction prints into
     `data/cef/alpaca_official_close.parquet`, de-duplicated on (date, ticker).
  4. `close_crosscheck` compares each official close with the panel close.
  5. `account_snapshot` writes `<D>/account.json` and one row per day in
     `$QUANTT_STATE_DIR/equity.csv`. It is taken only before the next session opens.
     Since 2026-10-19 that row is a *snapshot*, not the official P&L.
  6. `eod_equity` (added 2026-10-19) keeps `$QUANTT_STATE_DIR/eod_equity.csv`, Alpaca's
     end-of-day portfolio history: the official daily P&L of record (team lead,
     `docs/SYSTEM.md` §5). Its columns `date`, `equity`, `change_usd` are a contract
     other code reads by name. Every write covers every funded session since
     2026-09-28, and a revised value is logged in `data.log`. The step retries each
     slot until D's point is published and stamped before the read
     (`docs/RUNNER.md` "As built (2026-10-19)").
  7. `distributions` runs `scripts/fetch_cef_distributions.py`, with a 20-minute timeout.
  8. `borrow_snapshot` (added 2026-10-09) reads Alpaca's whole active US-equity
     asset list in one GET. It writes `<D>/assets.parquet`: per symbol, tradable,
     shortable, easy_to_borrow, borrow_status, margin requirements and the read
     time. A deployed name whose flags changed since the previous trading day's
     snapshot is a report-only flag; one missing from the list is a gap. Like
     `account_snapshot`, it refuses once the next session has opened. Why:
     Alpaca keeps no borrow history, and the flags churn daily. AWF and MHD were
     shortable on 2026-09-28, not on 2026-10-08, and shortable again on
     2026-10-09, when PHK was not.
- **Where it writes.** Each run that did work writes `<D>/report.json` (steps, flags,
  gaps) and appends one line to `$QUANTT_STATE_DIR/data.log`:
  `<D> DATA COMPLETE|INCOMPLETE <failed steps> flags=<n> gaps=<n>`.
- **Exit codes.** 0 means complete or idle. 5 means incomplete and will be retried.
  20 means an unexpected error: it is recorded in data.log and the traceback goes to
  stderr.
- **CEFConnect down is its own status (team lead, 2026-10-29).** When CEFConnect
  refuses every request `nav_crosscheck` makes on a run (more than one name asked,
  every one a read error), the step records `second source unavailable (cefconnect:
  <error class>)`. It is retried next slot but does not make the day INCOMPLETE, so
  the collector exits 0 when every other step is fine; the log line ends `;
  nav_crosscheck: second source unavailable (...)` and report.json carries
  `unavailable`. Nothing is compared, flagged or filled in its place. One name's error
  is still a failed step and an INCOMPLETE day, as before. Why: CEFConnect has refused
  every scripted request from the VM since 2026-10-21 (JSONDecodeError), so every
  slot exited 5 and systemd's `failed` said nothing.
- **The nightly data QA says so (2026-11-18).** That status sat in the tail of a line
  beginning `DATA COMPLETE`, and the core decided on single-source NAVs for three
  weeks with no report naming it. `scripts/ops/data_qa.py` Q9 now reads the
  collector's `report.json` for the as-of day and is FLAG whenever `nav_crosscheck`
  had no second source or did not complete, with the count of consecutive trading
  days and the first of them; no collector report is UNMEASURED, never OK. It has no
  threshold and fetches nothing. C4 has no second source by ruling, so Q9 is NOT_RUN
  there. The cause, measured from a residential address on 2026-11-18: CEFConnect
  answers the fetcher's request with an HTTP 200 `text/html` block page
  (`docs/REFERENCES.md`, the row beside the 2026-10-27 distribution-endpoint block).
- **Report only (team lead, 2026-09-29).** A cross-check disagreement of more than
  $0.005 is a *flag*. The flag names both sources and both values. It never blocks
  trading and never fails a step, and the two values are never averaged. A value that one
  source lacks is a *gap* naming the fund. Suppose the panel's NAV for D was itself
  filled from CEFConnect (`nav_fallback_log.csv`). Then that name is a gap, because
  comparing a source with itself is not a check.
  **Exception, 2026-10-13:** a panel NAV for D that equals the name's previous NAV while
  CEFConnect has no row for D is a *flag* (`check: nav_repeat_unverified`, both panel
  values named), not a gap. At the collector's ~21:40 ET check that is what Yahoo's
  stale copies looked like (`results/cef/LIVE_NAV_QUALITY_2026-10-12.md` §5).
- **CEFConnect arrival (2026-10-13).** The watch step `cefconnect_arrival` polls
  CEFConnect each slot until every deployed name's row for D has appeared. It appends
  each arrival to `$QUANTT_STATE_DIR/cefconnect_arrival.csv`, between the last poll
  without the row and the first with it. It never makes the day INCOMPLETE; the log
  line says `watching=cefconnect_arrival` while it runs. The stale-NAV gate's final
  check depends on when these rows arrive. A file that is empty or has another
  header is moved aside as `cefconnect_arrival.csv.<UTC stamp>.unreadable`, named in
  the step's detail, and a new file is started in the same slot (2026-10-14).
- **Panel lock.** The session and the collector both run `fetch_daily.py`. Its
  read-modify-write of the price and NAV panels holds an exclusive `flock` on
  `data/cef/.fetch.lock`. A second run waits up to 10 minutes, then exits 3 and names
  the lock (`fetch_daily.py` docstring, LOCKING).

## 6. Open questions

1. ~~`crsp_q_mutualfunds.daily_nav`: does it cover our CEFs?~~ **Answered 2026-10-08:
   no** (§3, `results/data/R2_SIGNAL_COVERAGE.md`). An independent NAV history for the
   CEFs is still missing.
2. Alpaca Market Data: the feed tier, and CEF coverage of daily bars and closing-auction
   prints. Measure it before relying on either.
3. Should the JFR 2004-03-25 bar be dropped from the live panel? That is a panel change
   under `data/`, so it is the team lead's call. It does not affect any date the book
   now decides on.
