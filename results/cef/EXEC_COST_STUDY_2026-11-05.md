# Execution-cost study, both paper books (measured 2026-11-05)

**Report only, zero trials.** It measures the books' own fills and prices counterfactual send
times and limit prices from the SIP tape. It changes no spec, nothing on the live path, and no
counter. Nothing here is adopted. The candidates at the end each need a pre-registration and a
release.

- **Reproducer:** `results/cef/exec_cost_2026-11-05/exec_cost.py`. `fetch` makes GETs only and
  needs QUANTT_ENV_FILE; `analyse` is offline. The commands are at the end.
- **Output of record:** `results/cef/exec_cost_2026-11-05/aggregates_2026-11-05.json`.
- **Provenance.** Every figure tagged [V] was measured on 2026-11-05 by that script, from two
  inputs:
  - the runner's private records (orders.jsonl, plan.json, send.json, reconcile.json, copied from
    the VM);
  - Alpaca SIP market data: quotes and trades for 15:30–16:00:30 ET, auction prints, raw daily
    bars.

  The two days whose records carry no fill price (2026-09-30 and 10-01) use the cef account's
  FILL activities. [S] figures are copied from the file named beside them. Confidence intervals
  are arithmetic on the run's day-clustered mean and t (t quantile 2.086, 20 df).
- **Public repository.** This note and the JSON hold aggregates only: no account or order id, no
  symbol, no per-order or per-fill row. The script refuses to write rows anywhere git can see and
  checks the JSON for symbols and ids before writing it. Per-name tables stay in its
  `--private-dir`, under the team lead's ruling "Aggregates in repo, rows private"
  (E-2026-11-03-34).

**Data and dates.**

| input | window | note |
|---|---|---|
| core (cef) orders | 22 sessions with orders, 2026-09-29 → 2026-11-04 | 2026-09-29 was `cls` (13 orders, 2 filled: paper's under-fill, reported apart). The other **21 sessions, 142 orders, 376 fills** are `late_market` and are the sample [V] |
| C4 orders | **1 session, 2026-11-04**, 15 orders, the opening build from flat | one day: a description, not evidence [V] |
| SIP quotes, trades, auctions | the same 22 sessions, 13 core names + C4's 15 traded names, read 2026-11-05 | 5 crossed or zero quotes dropped out of the whole read [V] |
| SIP raw daily bars | 2026-05-22 → **2026-11-04**, the last complete session | ADV, opens, next-session closes [V] |
| `data/cef/cef_universe.csv` | read only, for the group column | its price panel (last date 2026-10-15) is **not** used |
| `results/cef/c4/c4_universe_frozen_2026-10-14.csv` | C4's family and listing exchange | |

**Ties and checks [V].**
- Per day, B below equals verify's `fill_vs_auction_bp` in `results/report/data/live/cef/verify.csv`
  on all 17 days both have (max difference 0.05bp; verify rounds to 0.1). The 11-04 lines quoted
  in the brief reproduce: core +18.30bp, C4 +0.66bp.
- The official print equals verify's own print on 147 of 147 symbol-days, and the SIP daily close
  on every one.
- The plan's `est_price` equals the SIP close of the decide date on every order (max difference 0.0bp).
- The prior study's split reproduces: B is −0.00bp to 10-12, as `results/cef/FILL_DRIFT_2026-11-02.md`
  found (that note: −0; its 8.6bp from 10-13 ran to 11-02, and this sample to 11-04 gives 10.58bp).
- The two counterfactuals behind the ranking were re-run by a second, independent implementation
  (merge-on-time rather than array search), which gives the same 4.12bp and 3.00bp.

---

## The answer in brief

| question | answer |
|---|---|
| where the core's paper cost comes from | **B = 7.14bp** against the auction print (day mean 8.62, t 3.20, 95% CI 3.0 to 14.2). **5.90bp is the spread paid at send** (day mean 5.86, t 26.7, CI 5.4 to 6.3). It equals the quoted half-spread (5.98bp), because every fill printed at the touch (all 427 across both books). **The other 1.24bp is the market moving against us between send and the close** (C2 −1.24bp, day t −1.02: not distinguishable from zero) [V] |
| what sets the spread | **The tick.** 89.7% of the notional traded at a one-cent spread. The paid cost is half a cent a share ($0.00538 per share traded), so it scales as 1/price: 7.3bp in the lowest price tercile against 4.8bp in the highest. Side, short opens, muni against taxable and order size do not move it [V] |
| against the decide-time estimate | **IS = 31.5bp**: 25.6bp of market move from the decide-time close to 15:52 (OVN), plus the 5.9bp spread. OVN is mostly intraday (open → 15:52: 20.8bp, t 2.29) and in buys. The backtest bears it too (shift(2)), so **it is not an execution cost against the model** [V] |
| timing inside the window | **The spread is flat from 15:51 to 15:59:30** (mean 6.0–6.1bp across 273 core name-days), so sending later saves no spread. The point estimates do fall late: −2.2bp at 15:58 (t −1.50), −4.3bp at 15:59 (t −2.28). That comes from the late-day price path, on 21 days, after 12 send times were looked at: not a tested effect. **15:50:00 is wider (9.0bp)**, so an earlier send costs more [V] |
| order type on paper | Paper fills at the NBBO and fills a limit only once it is marketable [V: docs], so **a limit never pays less than the touch on paper**; it only decides which orders trade. **Post at the passive touch, cross the rest at 15:58**: 4.12bp against 7.14bp actual (−2.2bp, t −1.93, CI −4.5 to +0.2) [V] |
| unfilled risk | A limit at the decide-time close fills 47% of the notional on paper, and a live LOC at that price 48%. An unfilled order forgoes the next session's move, on average 12.3bp in the trade's direction (day t 1.3) [V] |
| dollars | At the core's measured **62.1–66.3 turns/yr**, paper B costs **4.4–4.7% of NAV a year ($4,426–4,717)**. Per unit of turnover that is **30% of the policy's 2023+ break-even of 23.8bp** [S]. C4's names quote about twice the core's spread (10.5bp). At its design 51.2 turns/yr that implies **about 5.4%/yr, half its modelled 10.76%/yr gross** [V/S] |
| paper artifact? | **Both measured parts are.** A live MOC order fills at the print, so it pays neither the spread nor the drift. **The real-money cost is the auction impact, which is unmeasured (n = 0)**, on orders that were a notional-weighted median of **15.2%** of the day's closing cross (p90 35.9%) [V] |

---

## 1. Decomposition

**Signs and units.** s = +1 for a buy, −1 for a sell or short. Every component is in bp of the
official close P_c, positive = worse for us, and notional-weighted on qty × P_c, as verify weights
it. Each identity is asserted per order.

| | definition | meaning |
|---|---|---|
| IS | s(f − P_e)/P_c | fill against the decide-time estimate (P_e = the plan's `est_price`, the decide date's close) |
| OVN = OVNn + OVNd | s(m_s − P_e)/P_c | decide-time close → mid at send, split at the day's open (SIP daily-bar open) |
| HS = QHS + TCH | s(f − m_s)/P_c | paid against the mid at send = quoted half-spread at send + fill against the touch at send |
| C2 = C2a + C2b | s(P_c − m_s)/P_c | mid at send → official print, in our trade direction, split at the 15:59:50 mid |
| **B = HS − C2** | s(f − P_c)/P_c | **fill against the auction print: verify's line, and the cost against the model** |
| | IS = OVN + HS | |

### Core, 21 `late_market` sessions, 142 orders, $638,612 notional at the print [V]

| component | pooled bp | day mean bp | day t |
|---|---:|---:|---:|
| **B, fill vs auction** | **7.14** | 8.62 | 3.20 |
| HS, paid vs mid at send | 5.90 | 5.86 | 26.66 |
| · QHS, quoted half-spread at send | 5.98 | | |
| · TCH, fill vs touch at send | −0.08 | | |
| C2, send → print (+ = the market moved our way) | −1.24 | −2.76 | −1.02 |
| · C2a, mid 15:52 → 15:59:50 | −4.54 | −4.78 | −2.52 |
| · C2b, 15:59:50 mid → print | +3.30 | +2.02 | 0.78 |
| **IS, fill vs decide-time estimate** | **31.52** | | |
| OVN, decide close → mid at send | 25.62 | 28.24 | 2.81 |
| · OVNn, decide close → open | 4.80 | 3.38 | 0.58 |
| · OVNd, open → mid at send | 20.81 | 24.85 | 2.29 |

**Per day [V]:** B ranges from −17.95bp to +29.77bp (day sd 12.3bp) and is positive on 17 of 21
days. HS stays in 4.4–8.1bp on every day. The day-to-day swing in B is drift; the spread is
nearly constant.

**Paper mechanics, measured [V].**
- Both books: submits at 15:52:01–15:52:08 ET. The last fill was at 15:52:23, a median 2.0s after
  submit (p90 5.9s, max 18.6s).
- **65% of the core's orders split into several fills (C4: 67%).** Alpaca's page says partial
  fills happen "for a random size 10% of the time" [V: docs]. All 427 fills of both books are at the
  touch at their own time.
- No `late_market` order went unfilled.
- 13 orders were re-fitted to buying power at send (sent qty ≠ plan), and 4 were skipped at send as
  unshortable. Neither is a cost.

### C4, 2026-11-04 only (the opening build; 15 orders, $129,335) [V]

| B | HS | QHS | C2 | C2b | IS | OVN |
|---:|---:|---:|---:|---:|---:|---:|
| **0.66** | 10.66 | 10.51 | +9.99 | +12.51 | 27.79 | 17.13 |

C4 paid **10.7bp of spread**, nearly twice the core's. Its B of +0.7bp is low only because the
closing prints sat 12.5bp in its trade direction from the 15:59:50 mid on that one day. **The 0.7bp
is not evidence of a low cost.** The spread is the stable part, and it was $0.01408 a share
(several of C4's names are higher-priced and quote multi-tick spreads).

### By side and kind (core) [V]

| | orders | days | B | HS | QHS | C2 | B day t |
|---|---:|---:|---:|---:|---:|---:|---:|
| buy | 71 | 21 | 8.11 | 6.06 | 6.06 | −2.04 | 2.20 |
| sell | 71 | 21 | 6.25 | 5.75 | 5.90 | −0.49 | 2.02 |
| buy long | 36 | 17 | 6.35 | 6.01 | 6.01 | −0.34 | 1.17 |
| buy to cover | 35 | 17 | 9.87 | 6.12 | 6.12 | −3.75 | 2.23 |
| sell long | 46 | 19 | 12.11 | 5.18 | 6.03 | −6.94 | 3.01 |
| sell short (open or add) | 25 | 14 | 2.87 | 6.08 | 5.83 | +3.22 | 0.80 |

- **Short opens pay the same spread as everything else (6.08bp).** Their lower B is drift.
- OVN differs sharply by side. Names bought moved 41.0bp against us between the decide-time close
  and 15:52 (OVNd 43.4bp, t 2.79). Names sold moved 11.3bp (OVNd −0.2bp).

---

## 2. Which names and conditions carry the cost

**The paid cost is the quoted spread, and the quoted spread is the tick.**

| check [V] | result |
|---|---|
| HS on QHS, order level, day-clustered | slope **0.93** (t 16.8), intercept 0.39bp |
| Spearman, HS vs share price | **−0.91** |
| Spearman, HS vs QHS | 0.94 |
| share of notional at a 1-tick spread at send | 89.7% (2 ticks: 10.3%) |
| paid vs mid per share traded | **$0.00538** (core), $0.01408 (C4) |
| core: share of spread dollars in the 3 names that carry most of it | 50.1% (the names are in the private table) |
| per-name mean half-spread at 15:52, across names (min / p25 / median / p75 / max) | core 3.5 / 4.6 / 5.1 / 6.9 / 12.2bp; C4's 15 traded names 4.5 / 6.0 / 8.8 / 11.5 / 33.6bp |

**By condition (core; terciles of the 142 orders) [V].** HS follows QHS in every split. B does not
follow any condition beyond noise.

| split | low | mid | high |
|---|---|---|---|
| share price: HS bp | **7.31** (≤ $9.74) | 5.49 | 4.77 (> $10.78) |
| share price: B bp | 5.14 | 8.21 | 7.87 |
| order / 63-session $ADV: HS bp | 5.04 (≤ 0.016%) | 5.75 | 6.04 (> 0.071%) |
| order / 63-session $ADV: B bp | 5.84 | 12.44 | 5.85 |
| order / closing cross: HS bp | 4.65 (≤ 3.0%) | 6.16 | 5.99 (> 10.9%) |
| order / closing cross: B bp | 18.65 | 5.15 | 6.21 |
| 2-tick spread at send (7 orders): HS / B | | | 8.03 / 10.76 |

- **Size.** Orders were a median 0.033% of 63-session dollar ADV (notional-weighted mean 0.17%,
  max 0.47%).
  - Paper does not check quantity against the quote, so size cannot cost more there by
    construction.
  - The small rise of HS with size is name composition: QHS rises the same way.
  - 11.5% of orders (both books) were larger than the displayed touch size at send [U: Alpaca's
    quote-size unit is not stated on the pages read]. A live market order of that size would walk the book; paper
    did not.
- **Muni against taxable:** HS 5.82 vs 5.94bp, B 8.16 vs 6.64bp. **No difference in the paid cost.**
- **Group:** HS is 5.6–6.8bp in every group (hy, loan, multi, muni).
- **B on QHS with the day's mean removed** has slope 2.4 (t 2.3). Wider-spread names also drifted
  against us more on this sample. With 142 orders, 21 days and several splits read, that is not
  separable from noise.

---

## 3. Timing inside the 15:52–15:58 window

Every order went at 15:52:0x, so the sample has no variation in send time. Each alternative is
priced counterfactually by paper's own rule: a market order fills at the touch then.

**Quoted half-spread by time of day: every name-day, not only our orders (market data) [V].**

| ET | 15:50:00 | 15:51 | 15:52 | 15:53 | 15:54 | 15:55 | 15:56 | 15:57 | 15:58 | 15:59 | 15:59:30 | 15:59:50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| core 13, 273 name-days, mean bp | **8.98** | 6.15 | 6.06 | 6.08 | 6.03 | 6.08 | 5.99 | 6.08 | 6.03 | 5.98 | 6.12 | 6.33 |
| core, median bp | 6.83 | 5.04 | 5.04 | 5.04 | 5.02 | 5.02 | 5.02 | 5.03 | 5.02 | 5.02 | 5.06 | 5.06 |
| C4's 15, 315 name-days, mean bp | 11.40 | 10.78 | 10.55 | 10.54 | 10.59 | 11.05 | 10.53 | 10.57 | 10.36 | 10.19 | 10.21 | 10.74 |

**Our orders sent at another time (core, 142 orders, 21 days) [V].**

| send at | B bp | QHS bp | C2 bp | B minus actual, day mean (t) | 95% CI |
|---|---:|---:|---:|---|---|
| 15:50:00 | 9.18 | 9.93 | 0.75 | +1.36 (0.86) | |
| 15:52:00 | 7.19 | 5.98 | −1.21 | +0.03 (0.22) | |
| 15:55:00 | 7.81 | 6.42 | −1.39 | −0.22 (−0.22) | |
| 15:57:00 | 5.25 | 6.21 | 0.96 | −1.88 (−1.57) | |
| 15:58:00 | 4.73 | 6.05 | 1.32 | −2.24 (−1.50) | −5.4 to +0.9 |
| 15:59:00 | 3.00 | 5.82 | 2.82 | −4.29 (−2.28) | −8.2 to −0.4 |
| 15:59:30 | 2.33 | 5.98 | 3.65 | −4.76 (−2.57) | |
| 15:59:50 | 3.66 | 6.95 | 3.30 | −3.84 (−2.20) | |
| spread evenly, 15:52–15:58 (TWAP) | 6.40 | 6.12 | | −0.87 (−1.48) | |
| post at the passive touch, cross the rest at 15:58:00 | **4.12** | | | **−2.18 (−1.93)** | **−4.5 to +0.2** |
| actual | 7.14 | 5.98 | −1.24 | | |

The full grid (all 12 times) is in the JSON.

**Reading.**
1. **No minute in the window has a narrower spread.** Any saving from a later send would come from
   the price path, not from cost structure.
2. **The path, on this sample.** After 15:52 the mid drifted back against our trade direction by
   4.8bp by 15:59:50 (C2a, t −2.52). That is a partial retracement of the open → 15:52 move
   (OVNd +20.8bp). This retracement is what makes late sends look cheaper.
   - It is 21 days, and 12 send times were looked at.
   - The day-level sd of B is about 12bp at every send time: 12.6bp at 15:52, 11.9bp at
     15:59:50. A later send does not make the paper fill track the print more closely.
3. **15:50:00 is the worst minute:** a 9.0bp mean spread, against 6.1bp a minute later.
4. **Spreading orders over the window** buys nothing on paper. There is no impact to spread out,
   and the TWAP's −0.9bp (t −1.5) is the same path effect diluted.
5. **Post-then-cross** puts each order at the passive touch at 15:52 and crosses any remainder at
   15:58:00.
   - The passive leg filled 47.5% of the notional at B −0.36bp; paper fills it only once the
     opposite quote moves through it.
   - The crossed remainder cost 8.17bp.
   - The total of 4.12bp is −2.2bp against actual, t −1.93. Its 95% interval includes zero.
6. **Sample size.** At a day-level sd of about 12bp, a 2bp difference in B needs roughly 140
   sessions to reach t 2 by itself. A paired difference (post-then-cross against market on the
   same day) has a smaller sd here (2.18 / 1.93 → 1.13bp SE on 21 days). **Nothing in this section
   is a tested effect.**

---

## 4. Order type on paper

### What Alpaca's documents say [V: fetched 2026-11-05; `docs/REFERENCES.md` §12bp]

- **Paper trading** (updated 2026-07-07):
  - paper simulates "the order filling based on the real-time quotes";
  - "all orders submitted in paper trading will be matched against the best available current
    market price (NBBO)";
  - "Orders are filled only when they become marketable";
  - "a non-marketable buy limit order will not be filled until its limit price is equal to or
    greater than the best ask price";
  - "Your order quantity is not checked against the NBBO quantities";
  - partial fills "for a random size 10% of the time";
  - not simulated: market impact, latency slippage, queue position, price improvement, regulatory
    fees, dividends.
  - The page is silent on auctions and on the last minutes of the session.
- **Placing Orders** (updated 2026-10-13):
  - `cls` "is eligible to execute only in the market closing auction";
  - "CLS orders submitted after 3:50pm but before 7:00pm ET will be rejected";
  - on/close orders are "routed to the primary exchange".
- **Measured against the paper page [V]:**
  - 65% of the core's orders and 67% of C4's split into several fills, not 10%;
  - paper charged regulatory fees on this account (`results/cef/LIVE_ATTRIBUTION_2026-11-02.md`,
    37 rows [S]), although the page says it does not.

**Consequence.** A marketable limit fills on paper at the same touch as a market order. A
non-marketable limit fills at the touch later, only if the quote moves through it. On paper,
**no limit order can pay less than the touch**: it changes *whether and when* an order trades, not
the spread it pays.

### Would a limit at the decide-time close ± k bp have filled? (core) [V]

L = P_e(1 + s·k/1e4); k > 0 pays up to k bp through the decide-time close. The opportunity cost
(OC) of an unfilled order is the next session's close-to-close move in its trade direction. It
needs D+1's close, so 2026-11-04 is excluded: 131 orders on 20 days. On those orders, B for the
market orders actually sent is 6.16bp.

| k (bp) | −50 | −25 | −10 | 0 | +10 | +25 | +50 | +100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| paper: fill rate, notional | 0.219 | 0.366 | 0.423 | **0.467** | 0.525 | 0.554 | 0.727 | 0.831 |
| paper: B of filled, bp | 5.14 | 0.50 | 3.84 | 5.05 | 5.92 | 7.10 | 3.47 | 5.99 |
| paper: OC of unfilled, bp | 7.11 | 3.99 | 0.88 | −2.71 | −10.48 | −12.45 | 15.95 | 8.44 |
| paper: filled at B, unfilled at OC, bp | 5.50 | 1.24 | 0.65 | −0.57 | −3.38 | −3.03 | 5.50 | 5.25 |
| prints rule (live continuous market): fill rate, notional | 0.273 | 0.421 | 0.495 | 0.501 | 0.554 | 0.595 | 0.763 | 0.840 |
| LOC rule (live closing auction): fill rate, notional | 0.147 | 0.281 | 0.445 | **0.483** | 0.518 | 0.527 | 0.697 | 0.787 |

- **The combined column swings from −3.4 to +5.5bp, with no order in k.** It is noise from the OC
  term on 20 days, not a schedule to choose k from. A limit here selects trades (drop the ones
  whose price ran away). That is a signal question, and the prior study found no predictability
  in it (`FILL_DRIFT_2026-11-02.md`, t 0.55).
- **The risk of an unfilled order.** The next session's move in the trade's direction averaged
  **+12.3bp** of notional (day mean 12.5, t 1.3): that is what an unfilled order forgoes per
  session, on average and with wide noise. A tight limit leaves about half the book's intended
  trades undone (47–48% fill at k = 0). With the no-trade band, that keeps a position outside its
  band until a later session trades it.
- **On a live account a tight LOC would do the same.** It would fill 48% of the notional at k = 0
  and 79% at +100bp. A LOC is a collar against a dislocated print, not a cost saver.

---

## 5. In dollars, beside the modelled edge

**Turnover, measured [V]:** traded dollars over decide-time equity, per session, × 252 / every NYSE
session in the window, traded or not.

| window | sessions (traded) | traded $ | mean decide-time equity | turns/yr |
|---|---:|---:|---:|---:|
| 2026-09-29 → 11-04 (includes the build from flat) | 27 (22) | 664,831 | 99,714 | **62.1** |
| 2026-10-07 → 11-04 (after the build and the missed 10-02..10-06) | 21 (19) | 551,233 | 99,678 | **66.3** |

This is the policy's own recent rate, not excess trading: live about 58.7/yr against the policy's
last-252-decision 57.2/yr (`results/backtests/turnover-live-2026-11-02/REPORT.md` [S]).

**Cost at that turnover.** The paper rows are [V]. The MOC row and the grid are arithmetic on the
labelled input.

| | bp per unit turnover | %/yr of NAV at 62.1 / 66.3 | $/yr at 62.1 / 66.3 |
|---|---:|---:|---:|
| **paper B, measured (the paper P&L of record pays this)** | **7.14** | **4.44 / 4.73** | **4,426 / 4,717** |
| of which the quoted half-spread at send | 5.98 | 3.72 / 3.96 | 3,706 / 3,950 |
| live MOC: regulatory fees only (`REAL_MONEY_COSTS_2026-10-12.md` §3 [S]) + **impact, unmeasured** | 0.106 + ? | 0.07 / 0.07 + ? | 66 / 70 + ? |
| grid 5bp (real-money view) | 5 | 3.11 / 3.31 | 3,098 / 3,302 |
| grid 15bp | 15 | 9.32 / 9.94 | 9,294 / 9,906 |
| grid 30bp | 30 | 18.64 / 19.88 | 18,589 / 19,811 |

**Beside the modelled gross: a model, labelled.** The modelled figures come at their own turnover,
so the scale-free comparison is cost per unit turnover against break-even (gross / turnover).
Under the sizing multiplier, gross and turnover scale together, so break-even is roughly unchanged
[U].

| model figure | source | paper B as a share of break-even |
|---|---|---:|
| the policy, 2023+ (H13), unit book: gross 10.61%/yr at 44.7 turns/yr, **break-even 23.8bp** | turnover REPORT [S] | **30%** |
| the policy under the live flatten rule, fit era: **break-even 18.6bp** | turnover REPORT [S] | 38% |
| the deployed ×1.30 book (flatten), W1 2013-06-25 → 2022-12-30: 8.67%/yr gross while trading | spec note `_sizing_multiplier_note` [S] | (turnover not stated there) |

**C4 [V for the spread, S for the model].**
- C4's design turnover is **51.2 turns/yr**: the spec's `_level_signal_note`, re-measured on the
  sleeve's construction, which corrects the pre-registration's 32.9 [S].
- The modelled gross is the fit blend, 10.76%/yr at 51.2 turns (SR 1.481;
  `prereg_c4_level/TRIAL54_RESULT_2026-11-03.md` [S]), so break-even is **21.0bp** (arithmetic).
- C4's quoted half-spread at send was 10.51bp on its one day, and 10.55bp on average over its 15
  names × 21 sessions at 15:52.
- At 51.2 turns that is **about 5.4%/yr of NAV, $5,379 on $100,000: half the modelled gross**.
- Its one-day B (0.66bp → 0.34%/yr) is drift luck, not a cost estimate.
- The 5/15/30bp grid at 51.2 turns gives 2.56 / 7.68 / 15.36%/yr.

---

## 6. Which part is a paper artifact

| component | paper (core) | a live MOC (`cls`) order | carries over to real money? |
|---|---:|---|---|
| spread at send (HS) | 5.90bp | fills at the print: no spread | **no** (it applies again only to a live order that misses the 15:50 cut-off and must cross; there it is a lower bound, because paper ignores size) |
| drift send → print (−C2) | 1.24bp | fills at the print | **no** |
| decide-time close → fill (OVN) | 25.6bp | borne the same way: the fill is at t+1 | real, but already in the model (shift(2)); not a cost against it |
| regulatory fees | (charged on paper) | 0.106bp per unit turnover [S] | **yes**, tiny |
| **impact of our own order on the print** | 0 by construction | **unmeasured, n = 0** | **yes: the real-money unknown** |

**How large our orders are against the closing cross (core, 142 orders) [V]:** median 6.2%,
notional-weighted median **15.2%**, p90 **35.9%** of the primary exchange's condition-6 cross. Every
order's day had one. This agrees in order of magnitude with
`EXEC_CAPACITY_OPEN_CROSS_2026-10-13.md`, which measured 10-01..10-13 at a median of 5.9% and a
notional-weighted median of 31% [S].

**So the paper fill line is not a forecast of live execution cost.**
- It is a **paper-only drag of about 7bp per unit turnover** that a live MOC book would not pay.
- The live book pays an impact term instead, unmeasured, in auctions where it can be a third of
  the cross.
- The verify line "auction-marked" is the impact-free live proxy (CLAUDE.md research rules: record
  both). The gap between it and the paper record is this note's B, about 4.4–4.7%/yr at today's
  turnover.

---

## What the data cannot tell us yet

1. **Live auction impact (n = 0).** This is the only execution cost a real-money MOC book pays
   besides fees, and paper cannot measure it.
2. **Whether the late-day path is persistent.** That covers C2a −4.8bp (t −2.52), the 15:59 send's
   −4.3bp (t −2.28) and post-then-cross's −2.2bp (t −1.93). It rests on 21 sessions, several
   splits, 12 send times and 8 limit offsets: none is a pre-registered test.
3. **Per-name or per-condition differences in B beyond the spread.** B's day-level sd is about
   12bp, so ±3bp needs about 60+ sessions. Half-spreads per name are already measured to well under
   1bp.
4. **C4's cost.** One session, an opening build. Only its quoted spreads (21 sessions) are
   informative.
5. **Limit-order economics.** The opportunity-cost term is a 20-day mean with t 1.3.
6. Quote-size units [U], so the "larger than displayed size" share is indicative.
7. **OVN** (25.6bp, t 2.81; buys 41bp, munis 42bp) is the session drift C5 measured. C5 is dead:
   D1, the control earned as much (`docs/RESEARCH_STATE.md`, trial 51). This note reopens nothing
   there.

---

## Candidate changes, ranked (recommendations; none adopted)

Each would need a pre-registration (`/prereg`) before the session that trades it, and a release.
Order-path rule 3 keeps MOC for live money. The paper `late_market` exception is the only path
1–3 touch.

| # | candidate | expected saving (bp per unit turnover) | what changes in the send path | applies to |
|---|---|---|---|---|
| 1 | **Post-then-cross on paper.** At 15:52, a limit `day` order at the passive touch (bid for a buy, ask for a sell). At 15:58:00 cancel the remainder and send it as a market order | **−2.2bp** day mean, 95% CI **−4.5 to +0.2** (t −1.93, 21 days); pooled 7.14 → 4.12. Structural reason: about half the notional (47.5%) trades without crossing. The CI includes zero | Two legs per name and a cancel. It must survive rule 2: `client_order_id` is unique only among active orders, and gate 6's no-set check must recognise the book's own resting limits. The send budget must cover both legs. The remainder qty comes from the broker's filled qty. send.json and verify must record both legs. Final positions are unchanged, so it is an execution A/B, not a signal change (whether it counts as a trial is the team lead's call) | paper, both books (C4's twice-wider spread raises its stake) |
| 2 | **Before real capital: pre-register a live impact measurement, with a per-order cap against the expected closing cross as the A/B.** Example: the excess above a fixed share of the trailing cross goes to a 15:4x limit | **unmeasured** (n = 0). Exposure: orders a notional-weighted median of 15% of the cross, p90 36% | live path only: the `cls` order size per name, and a record of print vs pre-close mid on traded and untraded names | live money |
| 3 | **Send at the end of the window (15:57–15:58) instead of 15:52.** Do not move earlier: 15:50 is 3bp wider | **0bp structural** (the spread is flat). Point estimate −1.9 to −2.2bp, CI about −5.4 to +0.9, from the price path only | the book json's `window_minutes_before_close`. Less slack before the close for the send budget and the 15:55 retry | paper |
| 4 | **A per-name, tick-aware no-trade band** (the cube-root law at each name's own half-spread: core 3.5–12.2bp, C4 4.5–33.6bp across names) | **not estimable without the harness**: it changes traded behaviour, so it is a **CEF trial** | the frozen spec, not the send path | both books |

**Not recommended, with the reason [V unless tagged]:**
- **Limit at the decide-time close ± k on paper.** It never pays less than the touch. It only
  selects trades, its 20-day economics are noise, and it changes traded behaviour (a trial).
- **A tight LOC on a live account.** About half the book stays untraded at k = 0. A wide LOC is
  insurance against a dislocated print, not a saving.
- **Back to `cls` on paper.** 11 of 13 expired on 2026-09-29 (CLAUDE.md rule 3 [S]).
- **An earlier send:** 15:50:00 is the widest minute.
- **Spreading orders over the window:** no impact on paper to spread out.
- **The open fill.** C5 is dead (D1).
- **A wider uniform band on cost grounds.** By the spec's own cube-root law (4.26% at 15bp,
  `_band_width_note` [S]), a 7.14bp cost implies about 3.3%, narrower than 4.8% (arithmetic, not
  proposed). The measured paper cost does not argue for trading less. Real money's cost is the
  unmeasured impact.

---

## Reproduce

```bash
# every directory outside the repository; the aggregates path is the committed one
QUANTT_ENV_FILE=<the cef key file> python3 results/cef/exec_cost_2026-11-05/exec_cost.py fetch \
    --records <private copies: <dir>/{cef,c4}/<date>/> --cache-dir <outside the repo>
python3 results/cef/exec_cost_2026-11-05/exec_cost.py analyse --records <same> --cache-dir <same> \
    --private-dir <outside the repo> --c4-design-turns 51.2 \
    --verify-csv results/report/data/live/cef/verify.csv \
    --aggregates results/cef/exec_cost_2026-11-05/aggregates_2026-11-05.json
```

`fetch` stops at the last complete session. The first run of 2026-11-05 read that day's partial
bar at 10:3x ET, and `analyse` now refuses one. `--c4-design-turns` has no default (H14): pass the
value the spec note gives on the day.
