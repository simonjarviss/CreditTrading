# NAV tenders (EVENTS trial 2): result — KILL D2 at stage 3; the holdout halted at its own gate

**Date** 2026-10-20 · **Pre-registration** `results/events/PREREG_NAV_TENDER_2026-10-19.md`
(approved 2026-10-19, all twelve defaults; bar N = 6) · **Counter** EVENTS 2 of N = 6,
spent (it moved on approval; it does not move again) · **Stage 0**
`results/events/NAV_TENDER_STAGE0_2026-10-19.md` (rulings: 73 flags, all signed by the
team lead on 2026-10-20) · **Author** research agent, branch `trial-events-navtender`

> **Verdict: KILL D2 (stage 3).** The tender trade earns a significant gross P&L per
> event and beats its placebo, but the per-event mean net of 15bp is not significant
> (cluster t 1.53 < 2.0). This is the graveyard paper's finding ("no longer significant
> after adjustments for transaction costs"), reproduced with an entry at the
> announcement. Stages 4 (D4) and 5 (the bar) fail as well.
>
> **The 2023–24 holdout was opened once, after the fit verdict was committed
> (`8a296a3`).** It halted at its own 20% unread gate: 14 of 42 events (33%) have an
> unread outcome or P_final. No 2023–24 price or return was read. Under §4.3 and §11.1
> the holdout is reported and the fit verdict stands.
>
> No sleeve. The no-tender twin (B) cannot be promoted from this trial (§2.1).

**Reproducers** (2026-10-20). Each writes a tracked JSON of aggregates; per-event rows
are not tracked.

| step | command | output |
|---|---|---|
| Stage 0 | `python3 scripts/events/nav_tender_trial.py stage0` | `results/events/nav_tender/stage0_2026-10-19.json` |
| the fit, once | `python3 scripts/events/nav_tender_trial.py fit` | `results/events/nav_tender/fit_2026-10-19.json` (code `16eab25`; verdict committed `8a296a3`) |
| second method | `python3 scripts/events/nav_tender_trial.py rederive` | `results/events/nav_tender/rederive_2026-10-19.json` |
| the holdout, once | `python3 scripts/events/nav_tender_trial.py holdout` | `results/events/nav_tender/holdout_2026-10-19.json` |

**Data:**

- CRSP daily rows to 2022-12-30 (R2 mirror, pulled 2026-10-20; the fit reader cannot
  return a 2023 row);
- French FF5 + UMD, vintage 202608;
- EDGAR filings to 2026-10-09;
- hedge availability: Alpaca read and IBKR's file, both 2026-10-20.

## 1. The event set

The 134 fit events (120 groups) shrink to the traded set:

- 26 have an unread outcome or P_final (19.4%, inside the 20% gate);
- 108 are read;
- 4 have no beta history (DRA ×3, JGH);
- **104 events in 96 groups are traded.**

None failed the election cut-off or was blocked by one-position-per-fund. 8 are hedged
with MUB at IBKR; the rest with Alpaca easy-to-borrow ETFs. Beta's median is 0.90.

## 2. The headline: gross P&L, with costs, borrow and the election fee beside it

**Per event, raw units** (u = 1/m, P&L per unit of original notional times u; prereg §8):

| | mean | cluster t (CR1) | plain t | group bootstrap 95% | P(mean ≤ 0) |
|---|---:|---:|---:|---|---:|
| **gross** | **+1.084%** | **2.80** | 2.86 | +0.31% to +1.82% | 0.25% |
| net at 15bp, every leg (stage 3) | +0.594% | **1.53** | 1.56 | −0.18% to +1.33% | 6.5% |

The mean of group means beside it is +1.17%.

**The tradable sleeve, 2010-03-24 to 2022-12-30** (T = 3,217 sessions, idle sessions
included). It is sized at k = 0.283 = 6% ÷ σ_active, and σ_active is 21.2%; the 1.80
gross cap is applied at entry.

| | gross | net 5bp | net 15bp | net 30bp | hedge borrow (IBKR MUB) | election fee at $100k | at $1m |
|---|---:|---:|---:|---:|---:|---:|---:|
| Sharpe | **0.450** | 0.381 | 0.244 | 0.037 | −0.075 | −0.160 | −0.016 |
| %/yr of capital | **+2.03** | +1.72 | +1.10 | +0.17 | −0.34 | −0.72 | −0.07 |

- **Columns:** the grid is `band_frontier._stats` on Q, charged on every leg. Borrow and
  the fee are separate lines, in Sharpe units of the gross vol (4.51%/yr).
- **The sign does not flip** across 5, 15 and 30bp. It is +0.04 at 30bp before borrow and
  fees.
- **Borrow is a counterfactual.** One day's fee (MUB at IBKR, 10.29%/yr on 2026-10-20)
  is applied to 2010–22.
- **All charges at once, labelled:** at 15bp, with borrow and the fee at $100k, the
  sleeve earns +0.04%/yr.
- **ETF legs at 5bp** (fund legs on the grid): net 0.381 / 0.319 / 0.226.
- **The raw sleeve, unsized:** gross 0.501; net 0.426 / 0.276 / 0.050.
- **Sleeve inference:**
  - NW t is 2.15 at L = 21 (the automatic lag is 8);
  - the stationary bootstrap Sharpe 95% interval is 0.03 to 0.92 at block 21, and
    0.02 to 0.92 at block 63;
  - skew is −2.08 and kurtosis 81.

**Second method** (`rederive`) uses plain loops on CRSP rows read again, with none of
`build_matrices`, `evaluate` or `cluster_t`. It reproduces the per-event mean (+1.084%),
its t (2.80), the stage-3 net (+0.594%, t 1.53) and both Sharpes (0.450 tradable, 0.501
raw) to within 1e-15.

## 3. The stages, in the declared order

| stage | statistic | result | rule | outcome |
|---|---|---|---|---|
| 1 | per-event mean gross, cluster t | +1.084%, t 2.80 | t ≥ 2.0 | pass |
| 2 | placebo dates (1,000 draws) | real +1.084% vs placebo p95 +0.738% (placebo mean −0.107%; 0.6% of draw means ≥ the real one) | real > p95 | pass |
| **3** | **per-event mean net at 15bp, cluster t** | **+0.594%, t 1.53** | **t ≥ 2.0** | **FAIL: KILL D2** |
| 4 | R-D4: alpha t; summed \|β\| at the vol target | alpha t 1.92 (+1.79%/yr); MUNI β 0.166, TERM 0.075, the rest ≤ 0.065 | t ≥ 3.0, all ≤ 0.10 | fail (D4) |
| 5 | `_dsr` at N = 6 | 0.392 (SR 0.450; SR0 0.530; SR·√years 1.61 vs √(2 ln 6) = 1.89) | > 0.95 | fail |
| 7 | holdout: (a) per-event mean > 0; (b) sleeve mean > 0 | not reached: the holdout halted at its 20% gate (14 of 42 unread) | both > 0 | not computed |

Stage 2's placebo:

- 1,470 of 104,000 event-draws were skipped (no beta at the drawn date);
- each event had a median of 2,292 candidate dates.

R-0, the contemporaneous-only regression, gives alpha t 1.88 and MUNI β 0.28.

## 4. Report-only rows (they decide nothing)

| row | result |
|---|---|
| no-tender twin B (sold at the close of X_p − 1) | +0.450% per event, t 1.21 |
| **A − B (the tender's own payoff)** | **+0.634%, t 3.27** |
| late entry (5 sessions before the cut-off) | +0.727%, t 3.01 |
| shift(3), raw sleeve | Sharpe 0.397 (against 0.501); approximate, the delayed last session is not built |
| mechanism slope: P&L per unit notional on the terms-implied slice spread at day 0 | **−0.31, t −2.25** (n 72, 64 groups; median spread 7.2%): the wrong sign for the mechanism |
| R-BOOK: with the deployed CEF book, 2013-06-25 to 2022-12-30 | correlation 0.086, beta 0.063 (n 2,398) |
| capacity | the median event's entry is 1% of its 63-session ADV at $18.5k of capital, and 5% at $92k. Median participation is 5.4% at $100k, 54% at $1m and 542% at $10m. The election fee is 35bp, 3.5bp and 0.35bp of the event's notional at those capitals (91 entered events with an ADV; median ADV $0.44m) |

## 5. Robustness (reported, never chosen from; none rescues the stage-3 kill)

| row | events / groups | per-event mean gross, t | sleeve gross | net 15 | net 30 |
|---|---|---|---:|---:|---:|
| headline | 104 / 96 | +1.08%, 2.80 | 0.450 | 0.244 | 0.037 |
| one unit per event | 104 / 96 | +1.09%, 2.41 | 0.369 | 0.169 | −0.032 |
| β ≡ 1 | 104 / 96 | +1.17%, 2.83 | 0.487 | 0.285 | 0.082 |
| β ≡ 0 (unhedged) | 104 / 96 | +3.30%, 5.24 | 0.943 | 0.880 | 0.817 |
| Alpaca-only hedges (IBKR-routed dropped) | 96 / 88 | +1.02%, 2.45 | 0.383 | 0.192 | 0.002 |
| muni hedged with IEF | 104 / 96 | +1.22%, 3.01 | 0.507 | 0.306 | 0.105 |
| credit classes only | 42 / 42 | +1.24%, 2.32 | 0.305 | 0.169 | 0.033 |
| quality-screen events removed (8) | 96 / 89 | +0.99%, 2.41 | 0.388 | 0.186 | −0.016 |
| residual sold at the outcome filing (lag 0) | 104 / 96 | +1.31%, 3.34 | 0.546 | 0.334 | 0.122 |
| residual lag 10 | 104 / 96 | +0.83%, 1.89 | 0.296 | 0.102 | −0.092 |
| programme stratum | 23 / 19 | +0.33%, 0.40 | 0.056 | −0.019 | −0.094 |
| offers for ≥ 50% of shares | 7 / 7 | +1.69%, 1.29 | 0.257 | 0.191 | 0.124 |
| re-dated stratum | 6 / 6 | +1.59%, 1.28 | 0.199 | 0.140 | 0.081 |
| day-0 form SC TO-C | 87 / 79 | +1.28%, 2.88 | 0.436 | 0.253 | 0.069 |
| uncapped sized sleeve | 104 / 96 | — | 0.501 | 0.276 | 0.050 |

Other rows, not in the table:

- second-method pi: n 1, not computed;
- sizing: 21 events entered below their sized weight, 12 of them not at all;
- calendar years with a positive sleeve P&L: 9 of 13;
- the largest group carries 11.9% of the P&L;
- leave-one-group-out mean: +0.99% to +1.22%.

**Eras (H5)**, by day 0:

| era | events / groups | mean, t | sleeve gross | turnover sd/mean |
|---|---|---|---:|---:|
| 2010–14 | 41 / 39 | +1.06%, 1.67 | 0.60 | 5.0 |
| 2015–19 | 34 / 33 | +0.52%, 0.76 | −0.02 | 4.7 |
| 2020–22 | 29 / 24 | +1.77%, 2.40 | 0.75 | 4.5 |

## 6. Against what we expected (§13)

| stage | expected | found |
|---|---|---|
| 1 | passes near +1.14% | passed at +1.08% |
| 2 | the placebo has a positive mean of its own | its mean was −0.11% |
| 3 | the likeliest kill | it was the kill |
| 4 | likely to fail | failed: MUNI β 0.17 at the vol target |
| B row | most of A's return comes from the announcement drift | **the opposite**: B earns +0.45% (t 1.2), and the tender's own payoff A − B earns +0.63% (t 3.3) |

The mechanism slope runs against the terms. Events whose offer sat further above the
price did not earn more.

## 7. What this means

**D2: an edge exists before costs, and costs eat it** (the D1–D7 legend in
`docs/RESEARCH_STATE.md`). Three findings bear on the next step:

- **The return is the tender's own payoff, not the drift.** It is about +0.6% per event
  before costs, against round-trip costs of about 0.5% per event at 15bp.
- **Capacity is the binding fact.** At $1m of capital, the median event's entry is half
  a day's volume.
- **The hedge removes return.** Unhedged, the rows are much stronger (+3.3% per event),
  because these funds carried their beta through 2010–22. The pre-registration's D4 rule
  exists to keep exactly that out.

No re-test on these data (§12). A tender-capture or B-sleeve idea would be its own
pre-registration and trial, and this trial informs it only through these report-only
rows.
