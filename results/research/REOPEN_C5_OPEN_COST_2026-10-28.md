# C5 re-opened as an execution choice: the opening cross's cost on recent quotes (zero trials), 2026-10-28

**Reproduce** (offline: two local gitignored caches and two committed records; no network, broker or key):

```bash
python3 scripts/research/reopen_c5/reopen_c5_open_cost.py \
  --recent-cache <main checkout>/.claude/worktrees/research-exec-capacity/results/cef/exec_capacity/_cache_exec \
  --frozen <main checkout>/.claude/worktrees/trial-c5/results/cef/c5/_cache_c5_frozen
```

**Spends no trial, and moves no counter.** It changes no spec, does not edit `docs/RESEARCH_STATE.md`,
`CLAUDE.md` or the rule-3 amendment draft, and touches nothing on the order path. The run is
`results/research/reopen_c5/reopen_c5_output_2026-10-28.txt`, with every figure and every input hash
in `reopen_c5_result_2026-10-28.json` and the per-name-day differences in
`reopen_c5_recent_pairs_2026-10-28.csv`. Tests: `scripts/research/tests/test_reopen_c5_open_cost.py`.

**Labels.** **[V]** means measured on 2026-10-28 by the command above. **[S]** means read from the
note or record named beside it. The design was committed (`34d2e02`) before the script first ran.

**Why it exists.** This is the team lead's re-open (2), ruled on 2026-10-27 (`docs/SYSTEM.md` §5;
`results/research/DESK_METHOD_2026-10-27.md` §2 and §7 item 5): "C5 as an execution choice, with the
opening-auction cost re-measured on 2023–26 quotes".

---

## Update, 2026-10-28 evening: the 2023–26 sample, the primary reading

The team lead had the 2023–26 quotes fetched: 64 sessions, 415 read-only requests, done
2026-10-28T21:28Z, written to the gitignored `_cache_reopen_c5_2023`. The design was committed before
they existed, and under it this sample is now the **primary** reading. Reproducer: the command above, plus
`--stride-cache results/research/reopen_c5/_cache_reopen_c5_2023 --stamp 2026-10-28-stride`. Outputs are
in `results/research/reopen_c5/*_2026-10-28-stride.*` [V].

| reading | `s_open` | net per unit of turnover (SE) | interval | outcome |
|---|---|---|---|---|
| **2023–26 stride, primary** | **3.735bp** (SE 0.936; h5 binds) | **+3.382bp** (1.816) | [−0.18, +6.94] | **INCONCLUSIVE**; the 1bp hurdle straddles the interval |
| 2026-Q3 window, beside | 2.021bp | +5.096bp (1.756) | [+1.66, +8.54] | PRESENT |
| the trial's own 6.516bp, beside | 6.516bp | +0.601bp (1.851) | [−3.03, +4.23] | INCONCLUSIVE |

- **The single-quarter PRESENT does not survive the full sample.** 2023–26 `s_open` landed at 3.7bp, which
  is where this note's caveat said the reading would turn. By year: 2023 is +7.6bp (h5), 2024 +0.9bp, 2025
  +3.4bp, 2026 +2.7bp.
- **More quotes would barely help.** The net's SE is now mostly the holdout gain's (1.556bp), not the
  cost's (0.936bp). Measuring the cost on every 2023–26 session would cut its SE to about 0.25bp, and that
  is not enough to decide.
- **C5 as an execution choice stays INCONCLUSIVE.** Its point estimate is positive: about +149bp a year of
  capital, which is not established. Nothing in this note supports proposing a move from MOC to the open.
- No independent review was run on this update. The result supports no change to the live book.

## The answer in brief

| question | answer |
|---|---|
| What did `s_open` measure? | The extra distance from fair value of the NYSE opening-cross print over the closing-cross print, in bp: the mean, over name-days paired on both sides, of \|print − mid\|/mid at the open minus the same at the close. Mids are taken 1 minute (h1) and 5 minutes (h5) from each auction. `s_open` = max(h1, h5). The sample was every 14th session of 2016-01-04 → 2022-12-30 (126 sessions, 13 names) (§1) |
| Do 2023–26 quotes exist? | **Partly.** The only cached 2023+ reference quotes are the EXEC note's 60-session window, **2026-07-21 → 2026-10-13**. The quotes for 2023-01-03 → 2026-07-20 are **missing**: fetching them means loading the Alpaca key file, which no agent may do (§2) |
| Re-measured `s_open` on that window | **+2.02bp (SE 0.81)**, set by h1; h5 +1.39bp (SE 0.65) **[V]**. The trial charged **6.52bp** (h5; SE 1.00 on its own sample) **[S, reproduced exactly here, V]** |
| Holdout gain less `s_open` | **+5.10bp per unit of turnover (SE 1.76)**, 95% interval **[+1.66, +8.54]**: **PRESENT**, above the 1bp meaningful size. Less the trial's 6.52bp instead: +0.60bp, [−3.03, +4.23], **INCONCLUSIVE** (§5) |
| Cost grid 5/15/30bp | **Does not apply.** Both fills share one holdings path and one turnover, so any per-unit cost cancels in the difference |
| How firm is it? | **Conditional on one calm quarter of 2026.** In 2016–22 the yearly means of the same statistic ranged **+1.5 to +9.9bp (h1)** and **+2.1 to +13.0bp (h5)** **[V]**. At the same SE, a 2023–26 `s_open` above about **3.7bp** would turn the reading INCONCLUSIVE. Six of the seven fit years are above it (§4, §5) |

---

## 1. What `s_open` measured

**The definition [S]: code, not prose.** It is computed in two steps:
- `scripts/cef/exec_capacity_open_cross.py::cost_table` builds the cost table, using `ref_points` for
  the horizons and `last_valid_quote` for the mids;
- `scripts/cef/c5_open_auction.py::stage6` builds the pairing and the maximum.

This script calls both unchanged.

- **Data source.** Alpaca SIP market data:
  - `/v2/stocks/auctions` for the auction prints;
  - `/v2/stocks/trades` for the primary's tape, used to classify the cross;
  - `/v2/stocks/quotes` for the consolidated NBBO.

  The 2016–22 sized prints are W4's cache (`fetch_alpaca_auction_history.py --sizes`).
- **Names.** The 13 deployed names, `scripts/cef/spec.py::UNIVERSE`: AWF, BIT, DSL, HYT, JFR, MHD, MQY,
  PCN, PDI, PDO, PFN, PHK, PTY. All list on NYSE, SIP code `N`.
- **The auction price.** The primary's volume-carrying cross print: `O` at the open, `6` at the close.
  Where there is no round lot, the odd-lot cross on the primary's tape is used. A name-day with no
  auction trade is not scored.
- **The horizons.** At each one, the mid of the last valid NBBO (bid > 0, ask ≥ bid) strictly before:

  | horizon | open | close |
  |---|---|---|
  | h1 | 09:31 | 1 minute before the close |
  | h5 | 09:35 | 5 minutes before the close |

  h0, the pre-open quote, is not part of `s_open`. It is 58bp wide at the half and biased
  (`results/cef/EXEC_CAPACITY_OPEN_CROSS_2026-10-13.md` §6) [S].
- **The statistic.** Close rows that are not `unmeasured` are inner-joined on (date, ticker) with open
  rows referenced to the NBBO. The statistic is the mean of the open dislocation minus the close
  dislocation. `s_open` is the larger of the h1 and h5 means.
- **The sample.** Every 14th session of 2016-01-04 → 2022-12-30, 126 sessions. The frozen copy was
  re-fetched on 2026-10-14 and its hashes are in `results/cef/c5/c5_frozen_inputs_2026-10-14.json` [S].
- **What it is.** It is an **upper bound**, not a cost. It is what a participant on the imbalance side
  of every cross would pay; the other side earns it. C5's gain is already priced at the opening print,
  so subtracting `s_open` charges the print's distance twice whenever C5 is not on the imbalance side.
  C5's own signed dislocation in the fit was −2.87bp per material trade, the favourable side
  (`results/cef/C5_RESULT_2026-10-14.md` stage 6) [S]. The comparison below is the trial's stress row,
  re-priced.

**Definition check [V].** The script first verifies all 131 frozen `exec/` and `w4/` files against
their recorded SHA-256. It then recomputes the trial's figures on them:
- h1 **+5.995263bp** and h5 **+6.516430bp**;
- these equal the trial's record (`results/cef/c5/C5_FIT_VERDICT.json` stage6) with a difference of 0.0;
- the script raises if the difference exceeds 1e-9bp.

So the recent figure below is the same quantity, measured by the same code.

## 2. What 2023–26 data exists, and what is missing

| input | 2023-01-03 → 2026-07-20 | 2026-07-21 → 2026-10-13 |
|---|---|---|
| Opening and closing auction prints (prices) | **cached**: C5's holdout freeze, `trial-c5` worktree `results/cef/w4/_cache_w4/alpaca_{opening,closing}_prints_holdout_2023_2026.parquet`, 2023-01-03 → 2026-09-30, prices without sizes [V: read] | **cached**, with sizes (`auctions_recent.parquet`) |
| NBBO reference quotes at h1 and h5 | **MISSING** | **cached**: the EXEC note's 60-session window, fetched 2026-10-13 (`research-exec-capacity` worktree, `results/cef/exec_capacity/_cache_exec/days/`) |

**Exactly what is missing.** For each sampled session of 2023-01-03 → 2026-07-20, and for each of the 13
names, four quotes are needed: the last valid consolidated NBBO before 09:31, before 09:35, 1 minute
before the close and 5 minutes before the close.
- Every 14th session gives about 64 sessions. The trial fetched its 126 sessions in about 25 minutes [S].
- The fetch is read-only: `GET /v2/stocks/quotes` on Alpaca's market-data host, which
  `exec_capacity_open_cross.py::fetch_refs` already implements.
- No new paid data is needed. The SIP history is on the plan the desk already uses [S: the EXEC note's
  fetch].

**Why it was not fetched.**
- Any Alpaca call needs the key file loaded. The repo's fetchers build their client with
  `AlpacaClient.from_environment`, which requires `QUANTT_ENV_FILE`. An agent may not load that file,
  through dotenv or any other way (CLAUDE.md hard rule 5).
- No CLI in the repo fetches a 2023–26 quote sample:
  - `exec_capacity_open_cross.py fetch` takes only the last 60 sessions and the 2016–22 sample;
  - `fetch_alpaca_auction_history.py --holdout` refuses `--sizes`.
- The cached holdout prints carry prices, and this note's second method (§4) scores round-lot crosses
  from prices alone. So the quotes are the only gap.

**Closing it (the team lead's call).**
1. A small driver applies `fetch_refs` to the 14-day stride over 2023-01-03 → 2026-07-20, using the
   cached exec calendar for early closes.
2. Someone allowed to load the key runs it.
3. This script runs again on the new cache.

> **Update, later on 2026-10-28: step 1 is done.** `scripts/research/reopen_c5/fetch_2023_refs.py`
> is the driver, tested with a fake client in `scripts/research/tests/test_reopen_c5_fetch_2023_refs.py`.
> No agent ran it: no key was loaded and no network call was made.
>
> **The run.** Its dry run (`--dry-run`, no client) lists 64 sessions, 2023-01-03 → 2026-07-13, with
> no early close on the stride, and at least 384 GETs of `/v2/stocks/quotes` [V]. From this worktree:
>
> ```bash
> QUANTT_ENV_FILE=../../../config/.env python3 -m scripts.research.reopen_c5.fetch_2023_refs \
>   --cache results/research/reopen_c5/_cache_reopen_c5_2023 \
>   --calendar ../research-exec-capacity/results/cef/exec_capacity/_cache_exec/calendar.parquet \
>   --holdout-prints ../trial-c5/results/cef/c5/_cache_c5_holdout
> ```
>
> **How it behaves.**
> - It is GET-only: the client is wrapped so that only `/v2/stocks/quotes` on the market-data host
>   can be reached.
> - It is resumable, and it refuses before any work if `QUANTT_ENV_FILE` is unset.
> - It copies the stride days' frozen holdout prices into the cache, after checking their SHA-256.
>
> **Then, step 3.**
>
> ```bash
> python3 scripts/research/reopen_c5/reopen_c5_open_cost.py \
>   --recent-cache ../research-exec-capacity/results/cef/exec_capacity/_cache_exec \
>   --frozen ../trial-c5/results/cef/c5/_cache_c5_frozen \
>   --stride-cache results/research/reopen_c5/_cache_reopen_c5_2023 --stamp 2026-10-28-stride
> ```
>
> **How the analysis reads the stride sample.** The design is in the script's docstring as items
> S1–S4, committed before any of these quotes exist:
> - the stride sample becomes the primary, and the recent window moves beside;
> - only round-lot crosses are scored, because the holdout prints carry no size and the tape is not
>   fetched;
> - without `--stride-cache`, the outputs above are reproduced byte for byte (checked 2026-10-28).
>
> **Two figures already known from real data [V].** Both come from a smoke run of the stride path on a
> synthetic quote cache; only the frozen fit data and the frozen holdout prints in it are real.
> - **The round-only restriction** moves the 2016–22 paired means by −0.08bp (h1) and −0.19bp (h5).
> - **Name-days that will not be scored:** 28 of the 832 stride name-days (3.4%) have no primary
>   `O`/`6` print: 12 at the open, 16 at the close.
>
> Both figures print again in the real run.

## 3. The design, fixed before any figure was computed

The design is in the script's docstring, committed at `34d2e02` before the first run.

1. **The cost sample** is the EXEC note's own recent window, `load_days(eras=("recent",))`: 60 sessions,
   2026-07-21 → 2026-10-13. It was not chosen here.
2. **The SE** is that of the horizon that sets `s_open`.
   - It is clustered by date, through the series x_d = D·(sum of differences on date d)/N. The mean of
     that series is exactly the pooled mean, and its lag-0 SE is the cluster-by-date SE.
   - The series goes through `inference.newey_west_t` at lag 0 and at the automatic lag (3 for 60
     sessions). The larger SE is used.
3. **The gain** is `G.bp_per_turn` in `results/cef/c5/C5_HOLDOUT_RESULT.json` [S], never re-derived.
   - Its SE is that value divided by the smallest t the record holds: t5 4.574, against t21 4.665 and
     automatic 4.683 [S].
   - Turnover is fixed by the holdings path, so the t is the same per year and per unit of turnover.
4. **The net** is the gain minus `s_open`. Its SE is √(SE_gain² + SE_s²), treating the two as
   independent **[U]**: one is a 939-session P&L series, the other a 60-session quote sample.
5. **The reading** is `inference.read_result(net, SE, meaningful=1.0, n_trials=1)`. **meaningful = 1bp per
   unit of turnover** was stated by the task before computing.
6. **Why n_trials = 1.**
   - This is one comparison, specified in advance, of a cost measurement against one estimate. The
     estimate comes from a holdout opened once under its pre-registration.
   - Nothing here is selected among alternatives: no horizon, window or name was searched.
   - The holdout figure is out of sample for C5's own selection, so the CEF counter's multiplicity does
     not inflate it.
   - The zero-trial ruling spends no counter.

   N = 52 is shown beside, never deciding.

## 4. `s_open` re-measured

**Recent window, 2026-07-21 → 2026-10-13 (60 sessions, 13 names) [V]**

Crosses classified:
- open: 780 round of 780;
- close: 779 round, plus 1 with no trade (PHK 2026-08-20, as the EXEC note found).

All 779 paired name-days are NBBO-referenced on both sides.

| horizon | mean | SE (lag 0 / lag 3) | t | name-days / dates |
|---|---:|---:|---:|---:|
| **h1** | **+2.021bp** | **0.814** (0.769 / 0.814) | +2.48 | 779 / 60 |
| h5 | +1.394bp | 0.649 (0.649 / 0.628) | +2.15 | 779 / 60 |
| **`s_open` = max** | **+2.021bp (h1)** | **0.814** | | |

**Checks.**
- **Against the EXEC note.** It printed **+2.0 (t 2.61)** at h1 and **+1.4 (t 2.13)** at h5 [S]. The same
  t, 2.61, comes back here from its own estimator (`_date_t`, the mean of date means) [V]. This note's
  SE is a little larger, because it also allows serial correlation across consecutive sessions.
- **Second method [V].** It reads the raw `O` and `6` prints straight from the auction rows, and the
  cached mids. It uses none of the tape classification. It gives +2.021bp (h1) and +1.394bp (h5) on the
  same 779 name-days, with a maximum absolute difference of 0.0. It skips 1 name-day, PHK's close
  without a `6` print.

**By name, recent window [V].** Each name has 60 sessions, PHK 59. The SE is Newey–West at the
automatic lag.

| name | h1 mean (SE) | h5 mean (SE) |
|---|---:|---:|
| AWF | +2.43 (1.67) | −0.06 (1.78) |
| BIT | +5.09 (1.81) | +3.73 (1.91) |
| DSL | +2.14 (1.85) | +0.77 (2.33) |
| HYT | +0.75 (2.32) | −1.90 (2.59) |
| JFR | −2.27 (1.92) | −3.56 (1.91) |
| MHD | +4.34 (1.64) | +2.40 (1.71) |
| MQY | +4.69 (1.67) | +3.54 (2.71) |
| PCN | +2.53 (1.47) | +2.72 (1.74) |
| PDI | +7.60 (2.95) | +7.41 (2.85) |
| PDO | +4.09 (1.49) | +5.25 (1.86) |
| PFN | −3.31 (3.55) | −1.30 (3.05) |
| PHK | −0.98 (2.08) | −2.61 (2.73) |
| PTY | −0.85 (2.66) | +1.65 (2.61) |

Sixty sessions pin no single name. Read the pooled row.

**By year.**
- **2023, 2024 and 2025 are unmeasured** (§2).
- **2026** is the window above.
- **Cut at C5's holdout end, 2026-09-30** (51 sessions; beside, never deciding) [V]:
  - h1 +2.696bp (SE 0.744);
  - h5 +1.512bp (SE 0.690);
  - `s_open` +2.696bp.

  The 9 October sessions pull h1 down.

**The fit period by year, for context [V].** These are costs, so the fit years may be read. The sample
is the trial's frozen one, 18 sessions a year; the SE is clustered by date, at the larger of lag 0 and
the automatic lag.

| year | h1 mean (SE) | h5 mean (SE) |
|---|---:|---:|
| 2016 | +4.32 (2.08) | +3.92 (1.49) |
| 2017 | +1.54 (1.04) | +2.12 (1.07) |
| 2018 | +6.47 (1.22) | +7.47 (1.68) |
| 2019 | +5.82 (1.05) | +4.55 (1.51) |
| 2020 | +9.87 (2.66) | +13.01 (3.28) |
| 2021 | +4.32 (0.94) | +3.71 (0.90) |
| 2022 | +9.29 (1.45) | +10.47 (1.74) |
| **2016–22** | **+5.995 (0.836)** | **+6.516 (1.003)** |

**This table is the main caveat.**
- The statistic moves between years by several times its within-year SE. It is highest in the stress
  years, 2020 and 2022.
- The 2026 window is one quarter. So its SE of 0.81 measures that quarter, not the 2023–26 average
  the holdout gain spans.
- What points the other way: today's closing crosses are about 6.9× their 2016–22 size, and today's
  opening cross is about 4.8× the closing cross (EXEC note §2 and §4) [S]. That is the mechanism by which the open's
  surcharge would have fallen. It is not a measurement of 2023–25.

## 5. The reading

**The gain [S]** (`results/cef/c5/C5_HOLDOUT_RESULT.json`, opened once on 2026-10-19):
- **+7.117bp per unit of turnover**: +313.6bp/yr over 939 sessions, 2023-01-03 → 2026-09-30, at 44.06
  turns/yr;
- SE = 7.117 / 4.574 = **1.556bp**.

**Declared before computing:** meaningful = 1bp per unit of turnover; n_trials = 1.

| row | `s_open` (SE) | net (SE), bp per unit of turnover | net, bp/yr of capital | 95% interval* | outcome | vs 1bp |
|---|---:|---:|---:|---:|---|---|
| **PRIMARY**: recent window, N = 1 | **2.021 (0.814)** | **+5.096 (1.756)** | +224.5 | **[+1.655, +8.538]** | **PRESENT** | ABOVE |
| beside: the trial's 2016–22 `s_open`, N = 1 | 6.516 (1.003) | +0.601 (1.851) | +26.5 | [−3.028, +4.230] | INCONCLUSIVE | STRADDLES |
| beside: recent, at the CEF counter's N = 52 | 2.021 (0.814) | +5.096 (1.756) | +224.5 | [−0.689, +10.882] (α 0.00099) | INCONCLUSIVE | STRADDLES |
| beside: recent, cut at 2026-09-30, N = 1 | 2.696 (0.744) | +4.421 (1.725) | +194.8 | [+1.041, +7.801] | PRESENT | ABOVE |

\* The Šidák-adjusted interval of `read_result`. At N = 1 it is the plain 95% interval. All figures
are [V], from the gain [S].

**The cost grid does not apply.** G is the difference between two fills of one holdings path with one
turnover. A 5, 15 or 30bp per-unit cost charged to both fills cancels, so the net is the same at every
point of the grid, and the grid cannot flip its sign. That is why no grid column is shown.

**Reading.**
- **The gain survives the opening cross's surcharge as measured on recent quotes.** The open fill's
  extra distance from fair is about 2bp per unit traded in 2026. Against the 7.12bp gain, that leaves
  +5.1bp, and the interval excludes zero and the 1bp meaningful size. **The evidence outcome is
  PRESENT.**
- **It is conditional, and the condition is unmeasured.**
  - The cost comes from 60 sessions of 2026; the gain is a 2023–26 average.
  - At the same SE, the lower bound reaches zero at an `s_open` of about 3.7bp (2.021 + 1.655). Six
    of the seven 2016–22 years measured above it.
  - Until 2023-01-03 → 2026-07-20 is measured (§2), "PRESENT on the 2026 window" is the strongest
    statement this supports.
- **The two beside rows that turn INCONCLUSIVE** do so for different reasons:
  - the trial's 6.52bp row, because that cost is about the size of the gain;
  - the N = 52 row, because the family-wise interval is about 1.7 times as wide (half-width 5.79 against
    3.44) [V].

  Neither is the primary reading.
- **The power at the meaningful size is 0.09** (`read_result`). The test can tell a 5bp net from zero.
  It could not tell a true 1bp net from zero.

**What this does not change [S].** C5 stays KILLED (D1) as a trial, with the gain's evidence relabelled
PRESENT and the placebo split INCONCLUSIVE (`docs/RESEARCH_STATE.md`, 2026-10-27 note). Three points
from the trial bear on an execution choice, and none is re-measured here:
1. **The lagged placebo.** The same open fill earns as much on a trade decided a day earlier. The gain
   is session drift on the signal's trades, not fresh NAV. For an execution choice it matters only
   that the drift persists; the holdout says it did, positive in every year 2023–26
   (`C5_RESULT_2026-10-14.md` stage 8).
2. **R-D4.** In the fit, the gain loaded on MUB's intraday return (summed β −0.216, t −3.42).
3. **The capacity-bound label.** On the fit's quote sample, the trade gain split into print → mid
   +81.7bp of capital and mid → close −128.1bp. So the trial labelled it capacity-bound: much of the
   gain sits in the print's own distance from the mid, which an order on the imbalance side would not
   get.

None of the three is a cost, and re-measuring 2 or 3 on 2023+ would be a new return statistic.

## 6. What decision this informs (not made here)

It informs **whether to propose moving the CEF book's execution from the t+1 closing auction to the t+1
opening auction (`opg`)**. That is a live-path change, and every step of it is the team lead's:

1. **A pre-registration** of the execution change, with the live statistic and horizon that would
   reverse it (H11). Whether it spends a trial is the team lead's ruling.
2. **A frozen-spec change** through `/spec-change`. The new execution key defaults to MOC, and the no-op
   is proved byte for byte.
3. **An amendment to `CLAUDE.md` order-path rule 3** ("order type stays MOC"). A draft exists in
   `results/cef/PREREG_C5_OPEN_AUCTION_2026-10-13.md` §16, from branch `research-prereg-c5`, merged at
   `77cd6a1`. This note does not edit it.

**The step before any of them.** Close the §2 gap: measure `s_open` on 2023-01-03 → 2026-07-20 quotes.
This script then reads the full 2023–26 sample with `read_result`:
- if the lower bound stays above zero, the PRESENT reading holds for the period the gain spans;
- if it does not, the reading is INCONCLUSIVE, and the open fill's cost is the obstacle.

**Blockers that no cost measurement removes [S]** (`EXEC_CAPACITY_OPEN_CROSS_2026-10-13.md` §7, §8):
- **Whether Alpaca accepts `opg` from this account type and from a live account [U].** The sources
  disagree, and only an order settles it.
- **Paper runs no auction.** Paper therefore cannot score an `opg` fill any better than a `cls` one.
- **The 09:28 ET `opg` cut-off.** The evening decision fits it: an order sent after 19:00 is queued for
  the next open.

## Gaps

- **2023-01-03 → 2026-07-20 quotes are unmeasured** (§2). The primary reading rests on 60 sessions of
  2026.
- **The recent cache is not pinned by a committed record.** It lives in another worktree's gitignored
  directory. This run's JSON records the SHA-256 of all 62 files read (combined `eaf3a9a1…`).
  `exec_capacity_open_cross.py fetch` cannot rebuild the same window: it takes the last 60 sessions at
  run time.
- **The independence of the gain's and the cost's errors is [U].** The two overlap on 2026-07-21 →
  2026-09-30.
- **`s_open` is an upper bound, not a measured cost of our own fill.** No auction impact is measured,
  because paper never entered an auction (EXEC note, Gaps) [S].
- **Not re-measured** (out of scope, or return-based on 2023+):
  - the signed dislocation of C5's own trades;
  - the print → mid split;
  - the D4 betas;
  - the lagged placebo.
