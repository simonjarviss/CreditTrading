# Trial 53 re-measured on the live thin-session rule (flatten): multipliers, odds, stops (2026-11-02)

**Report only. Zero trials, no spec or book change, no edit to the live path.** Fit data only: every
frame ends by 2022-12-30, asserted. CEF stays at 53. Branch `trial53-flatten-remeasure`, from
origin/main 26ed351.

**Labels.**
- **[V]** computed here by the helper named, in this folder.
- **[S]** quoted from the thin-days report, not re-run.
- **[U]** an interpretation, or arithmetic on stated inputs.

**Why this exists.** Trial 53 (`results/cef/PREREG_VOLTARGET_2026-10-30.md`, live at ×1.13 in
`release-20261102-1`) was derived on the canonical harness's book. That book **HOLDS** the previous
target on a thin session, where fewer than `min_names` names are eligible. The live core sleeve
**FLATTENS** there instead: `src/deploy/sleeves/cef_discount.py`, the `min_names` block, every name
FLAT, before the band and the cap. The thin-days report found this
(`results/backtests/thin-days-2026-11-03/REPORT.md` §6, branch `research-thin-days` at c7a1635) and
gave the harness the live rule as `band_gross_capped(below_min_names="flatten", thin=thin_sessions(...))`.
Its default is byte-identical, and it matches the live sleeve on all 5,480 dates [S]. **C4 is not
affected:** its spec sets `below_min_names: "hold"`, so its live rule and its scored rule are the same.

**How it was run.**
- `flatten_series.py` imports that harness option from the `research-thin-days` worktree, asserted
  clean at c7a1635. It does not fork it.
- It builds the flatten core book on fit-cut panels. The panels end 2022-12-30; the live panels end
  2026-10-15 (prices) and 2026-10-14 (NAV), and no later row was loaded.
- It writes two input roots in `_common.load`'s layout: one with the core as the **flatten** book,
  one as the **hold** book.
- Every check passes:
  - the hold root reproduces the derivation's core series and proxies to 0.0;
  - the flatten root reproduces the thin-days report's W1 row (SR 0.799, 2.98%/yr, mean gross 0.465,
    daily sd 0.002351) and its ×1.13 row (SR 0.795, maxDD 7.53%) [V];
  - `stops.py` on the hold root reproduces the approved thresholds exactly (11.17% / −3.52% / 12.12%) [V].
- `derive.py --remeasure`, `risk.py --books`, `stops.py` and a new `flatten_remeasure.py` then run on
  both roots.
- One reporting fix in `_common.account`: a session with no decided book now counts as "cap not
  binding". It had read as binding. The P&L is unchanged, and the hold book is invested on every W1
  session, so its published figures do not move.

---

## 0. The answer

| | hold book (as approved) | flatten book (the live rule) |
|---|---|---|
| W1 sessions on which the core earns | 2,398 of 2,398 | **1,045 of 2,398 (43.6%)** [V] |
| core unit daily sd, calendar | 0.004095 (6.50%/yr) | **0.002351 (3.73%/yr)** |
| core unit daily sd, sessions it earns on | 0.004095 | **0.003556 (5.65%/yr)** [V] |
| **(a) the 2026-10-29 rule, literally (calendar sd)** | core 1.1357 → 1.13; C4 1.2712 → 1.27 | **core 1.9675 → 1.96; C4 1.2642 → 1.26** at 5.25% [V `derive.py --remeasure`] |
| the same rule on the sessions the core earns on | — | **core 1.3007 → 1.30** (C4 1.26) [V `flatten_remeasure.py`] |
| ×1.13 / ×1.27 on the plateau? | yes | **yes.** With C4 fixed at 1.27, the combined Sharpe is 1.625–1.638 for any core multiplier from 0.8 to 2.5. At 1.13 it is 1.632 TR / 1.750 PR; the maximum is 1.638 at 1.00 [V] |
| **(b) at ×1.13, the core account, 12 months, zero edge:** | | |
| — P(HALVE) / P(KILL), W1 | 15.9% / 1.5% | **0.8% / 0.0%** on every session; **10.3% / 0.66%** on the sessions it earns on (the live book while it trades) [V] |
| — the same, through 2008 (min / median / max over the 10 books) | P(HALVE) 7.2 / 15.2 / 51.4%; P(KILL) 0.35 / 2.4 / 17.4% | P(HALVE) 0.02 / 0.51 / 21.4%; P(KILL) 0.00 / 0.00 / 6.8% (5 of the 10 books are flat) [V `risk.py`] |
| — worst drawdown, W1 | 14.05% model, 14.84% exact | **7.55% model (7.53% exact [S])**; 7.55% on the earning sessions joined end to end |
| — worst drawdown through 2008, 10 books | 14.8 / 22.5 / 36.4% | 7.5 / 8.0 / 34.7% |
| **(c) R1 / R2 / R3 at ×1.13** (core) | 11.17% / −3.52% / 12.12% | every session: **6.96% / −2.31% / 7.29%**; sessions it earns on: **9.02% / −2.76% / 10.70%** [V] |
| C4's stops at ×1.27 | 10.09% / −3.04% / 9.96% | unchanged |
| **(d) a spurious live stop?** | — | **No, from the stops as approved: they UNDER-fire.** When the live book trades, the hold-calibrated stops fire 0.4% (R1), 3.1% (R2) and 3.6% (R3) of the time, against the 5% they were built for. **Re-measuring them on the flatten book's every session WOULD fire spuriously:** 7.9%, 6.4% and **18.8%** [V] |

**Recommendation.**
1. **Keep ×1.13 on the core, and amend only the core's stop thresholds**, to the flatten book's
   earning-session calibration: R1 9.02%, R2 −2.76%, R3 10.70% at ×1.13, re-measured on the read date
   by `stops.py --core-earning-only` (H14).
2. **Do not adopt the literal re-derivation of ×1.96** (§2).
3. **The team lead's alternative is ×1.30.** That is the rule on the sessions the book trades, and it
   restores the risk the approval accepted: 16.7% / 1.7% zero-edge P(HALVE) / P(KILL) while trading,
   against 15.9% / 1.5% approved.
4. **C4 at its arming: 1.26** (the re-derived 1.2642, rounded down) rather than 1.27. The difference is
   immaterial.
5. **I agree that a changed multiplier or threshold is an amendment to trial 53**, recorded before any
   live return is read, and not a new trial. The hypothesis, the rule and the counter are unchanged.
   What changed is an input the rule was fed. A changed input definition (calendar to earning-session
   sd) needs the team lead's ruling, because it departs from the rule as literally declared.

---

## 1. What the flatten book is

The live rule leaves the core **flat on 56% of W1** [V `flatten_series.py`]. 3,484 of the fit
period's sessions are thin, 1,353 of them in W1. Five of the ten year-end books used for the 2005-13
proxy are thin, so they are flat under the live rule: 2015-12-31, 2017-12-29, 2019-12-31, 2020-12-31
and 2021-12-31. They include both of the "dangerous" 1.70-1.80 gross books that drove the approved
2008 tail [V; S, the thin-days report §6].

On the sessions it trades, the flatten core is a **lower-vol** book than the hold book (5.65% against
6.50%/yr unit). The hold book's thin stretches held stale, PHK- and PTY-tilted books
(the thin-days report §4-5 [S]). At ×1.13 it earns 7.63%/yr while trading, at 6.34% vol (SR 1.20) [V].

## 2. (a) The multipliers, and why the literal re-derivation is not the answer

For b = ½, ½ the 2026-10-29 rule's multipliers satisfy **m_core / m_c4 = sd_c4 / sd_core exactly**.

| core sd used | m_core (C4 at the rule's 1.2642) | while trading, core account ex-ante vol [U: m × 5.65%] |
|---|---:|---:|
| hold, calendar = active (0.004095) | 1.13 | 6.4% |
| **flatten, earning sessions (0.003556)** | **1.30** | **7.3%**, about C4's 7.0–7.3% |
| flatten, calendar (0.002351) | 1.96 | 11.1% ex ante; about 9.0% realised once the cap trims it |

**The literal rule gives ×1.96 only because the flat sessions count as zero risk.** The same units
trap was named for intermittent sleeves on 2026-10-29 (`SCRATCH/alloc4/NOTE.md` §8: "vol target
means active-session vol").
- The live core trades now. The thin-days report §5.I [S] notes that the eligible count was exactly
  6 on 192 sessions up to 2026-02-12, so it can still go thin.
- At ×1.96 the account, while trading, would carry about 1.3 times C4's realised risk: about 9.0%
  against 6.9% [U: the calendar vol 5.93% / √0.436]. Ex ante it is 11.1%, and the cap trims it. That
  is not equal risk.
- **Equal risk while trading gives ×1.30.**
- **×1.13 sits below it, so it is conservative under the live rule:** while trading, the core
  carries about 0.9 of C4's risk (6.34% against 6.97% [V]).

**The plateau** [V `derive.py --remeasure`, `plateau_grid_2026-11-02_flatten.csv`,
`live_pair_grid_2026-11-02_flatten.csv`]:
- At the literal point (5.25%, ×1.96 / ×1.26), Sharpe is 1.625–1.634 within ±0.5%. The Sharpe argmax
  is 6.25%, not chosen.
- With C4 at 1.27, combined Sharpe is flat in the core multiplier: 1.625–1.638 from 0.8 to 2.5. The
  maximum is at 1.00, and **1.13 is on the plateau** (1.632).
- **The choice between 1.13, 1.30 and 1.96 is return against risk, not Sharpe.** Combined fit-path
  gross, total return: 6.71%, 6.92% and 7.56%/yr [V `risk.py`].

## 3. (b) Risk at ×1.13 under the live rule

All [V `risk_output_2026-11-02_flatten.txt`, `flatten_remeasure_output_2026-11-02.txt`]:
- **Calendar flatten series** (history's thin frequency):
  - core account W1 P(HALVE) 0.77%, P(KILL) 0.00% at zero edge;
  - through 2008, P(HALVE) 0.02 / 0.51 / 21.4% and P(KILL) 0.00 / 0.00 / 6.8%. The worst book is
    2018-12-31, gross 0.87, held fixed through 2008;
  - worst drawdown 7.55% (W1) and 7.5 / 8.0 / 34.7% (through 2008);
  - combined P(HALVE) 0.42 / 0.58 / 6.4% and P(KILL) 0.00 / 0.00 / 0.44%.
- **While trading** (earning sessions only): zero-edge P(HALVE) **10.3%**, P(KILL) **0.66%**; fit edge
  0.86% / 0.01%.
  - Against the approved 15.9% / 1.5% (hold, W1), **the live core carries less risk than the trial
    approved.**
  - ×1.30 while trading gives 16.7% / 1.7%, the approved level.
- C4's account is unchanged: 16.3% / 1.6% through 2008.
- **The 2008 tail stays unmeasured.** Under the live rule the 2005-13 core would mostly have been flat
  (too few names cleared the ADV floor; CLAUDE.md landmine 8). The fixed-book proxy is a
  counterfactual and an upper bound [U].

## 4. (c) The stops, and (d) whether any could fire spuriously

**The core's thresholds at ×1.13** [V `flatten_remeasure.py`; `stops.py` reproduces each]:

| calibrated on | R1 D_R | R2 (120 sessions) | R3 (60 sessions) |
|---|---:|---:|---:|
| hold (as approved) | 11.17% | −3.52% | 12.12% |
| flatten, every session | 6.96% | −2.31% | 7.29% |
| **flatten, earning sessions** | **9.02%** | **−2.76%** | **10.70%** |

**P(a stop fires within its horizon)**, fit edge, SB21, 10,000 paths [V]. Rows are the truth: how the
live book behaves. Columns are the calibration. The nominal rate is 5%; R1's is below 5% by
construction, because it takes the largest method's 95th percentile.

| truth ↓ / calibration → | hold | flatten, every session | flatten, earning |
|---|---|---|---|
| **live book while trading (flatten, earning)**: R1 / R2 / R3 | **0.4 / 3.1 / 3.6%** | 7.9 / 6.4 / **18.8%** | 1.8 / 5.0 / 5.0% |
| flatten, every session: R1 / R2 / R3 | 0.0 / 1.8 / 1.4% | 1.4 / 5.0 / 5.0% | 0.1 / 3.5 / 2.2% |
| hold: R1 / R2 / R3 | 0.9 / 5.0 / 5.0% | 14.2 / 8.7 / 35.8% | 4.1 / 7.4 / 9.6% |

**What this means for the live stops:**
1. **R2 against the hold-measured 5th percentile does not fire spuriously.**
   - When the live book trades, its 120-session return falls below −3.52% only 3.1% of the time.
   - The hold series is the wider distribution (7.2% against 6.3% vol at ×1.13), so its 5th
     percentile is further out.
   - The flatten book's lower mean (it lacks hold's PHK-tilted thin-day P&L) does not offset that.
2. **The approved stops under-fire.** They are looser than designed for the live book. That is a
   protection gap, not a false alarm.
3. **A flat session cannot trip any stop.** It adds no drawdown, no return and no vol, so a thin
   stretch can only delay a stop. While the book is flat the stops are inert. The core's spec
   HALVE / KILL lines (report only) are unaffected.
4. **Re-measuring on the flatten book's every session would be the wrong amendment.** R3 would fire
   18.8% of the time while the book trades, because that series' 60-session vol is diluted by flat
   stretches the live book is not in.
5. **The earning-session calibration is the right one.** It is nominal while the book trades. If the
   book goes thin, it fires less.

## 4b. ×1.30 against ×1.13, on the trading-session flatten book (added 2026-11-02, for the team lead's choice)

**Basis.**
- "While trading" means the sessions on which the core earns: a book held two sessions earlier.
- "Through 2008" is W2 (2005-02-22 → 2022-12-30). The core before 2013-06-25 is proxied by each of
  the **5 non-thin** year-end flatten books; the 5 thin ones are flat under the live rule and trade
  nothing. Only trading sessions are kept.
- Odds are at zero edge: the worst of SB21, SB63 and GAUSS, and the worse of total return and price
  only. HALVE does not act.
- C4 is at 1.27 beside ×1.13 and at 1.26 beside ×1.30 (§0). It does not enter the core account's
  figures.

Sources: [V `flatten_remeasure.py` at each multiplier; `flatten_exact.py` (exact implementation B);
`risk.py`; `derive.py --remeasure` §6].

| core account | ×1.13 (live) | ×1.30 |
|---|---:|---:|
| P(HALVE) in 12 months, W1, while trading | 10.3% | **16.7%** |
| P(KILL) in 12 months, W1, while trading | 0.66% | **1.68%** |
| P(HALVE) through 2008, while trading (min / median / max over 5 books) | 2.2 / 8.9 / 35.5% | **5.1 / 15.1 / 47.1%** |
| P(KILL) through 2008, while trading (same) | 0.04 / 0.65 / 9.7% | **0.18 / 1.78 / 14.4%** |
| worst drawdown, W1 (exact B, calendar) | 7.53% | **8.39%** |
| worst drawdown, W1, trading sessions joined (model) | 7.55% | **8.52%** |
| worst drawdown through 2008, while trading (5 books; worst 2018-12-31) | 8.5 / 16.1 / 34.7% | **9.7 / 18.3 / 39.1%** |
| Sharpe, while trading (exact B, TR) | 1.205 | **1.222** |
| Sharpe, calendar W1 (exact B, TR / PR) | 0.795 / 0.862 | 0.805 / 0.875 |
| combined Sharpe with C4 (model, TR / PR) | 1.632 / 1.750 | 1.626 / 1.745 |
| gross cap: held at the cap, sessions with a book (exact B) | 6.5% | **15.2%** |
| gross cap: decided gross above the cap, sessions with a book (model) | 7.4% | 16.5% |
| mean gross when held (exact B) | 1.20 | 1.34 |
| **R1 / R2 / R3**, recalibrated on trading sessions | 9.02% / −2.76% / 10.70% | **10.14% / −3.06% / 12.07%** |
| gross %/yr, core account, exact B, TR: calendar / while trading | 3.31 / 7.59 | 3.78 / 8.67 |

**The gain from ×1.30 over ×1.13, on the fit:**
- the core account gains **+0.47pp/yr gross** over the calendar, and **+1.08pp/yr while trading**
  (exact B, total return);
- the combined $200k book gains **+0.21pp/yr** (model, total return), with C4 1.26 against 1.27;
- the core's change alone adds about +0.23pp to the combined book [U: half the core account's
  +0.46pp model gain].

These are fit-path figures (W1 2013-06-25 → 2022-12-30) [V]. They are not a forecast, and the
forward evidence is paper only (pre-registration §6.1).

**×1.30 is inside the plateau, not at its edge.**
- With C4 at 1.26, combined Sharpe moves only between 1.624 and 1.638 over every core multiplier
  from 0.8 to 2.5. ×1.30 is at 1.626, within 0.05 of the maximum (1.638 at ×1.00), in the middle of
  that range [V `live_pair_grid_2026-11-02_flatten_m1.30.csv`].
- The core's share of the combined variance rises from 0.26 at ×1.13 to 0.31 at ×1.30.
- The choice is risk against return, not Sharpe: about +1.1pp/yr while the core trades, for roughly
  1.6 times the HALVE odds and 2.5 times the KILL odds.

**×1.30 restores what the trial approved.** The approval accepted 15.9% / 1.5% zero-edge P(HALVE) /
P(KILL) on the hold book. On the live book while it trades, ×1.30 carries 16.7% / 1.7%; ×1.13
carries 10.3% / 0.66%.

## 5. What this does not settle

- The thin-days report's open question 1, hold or flatten as the live rule, is the team lead's. If
  the live rule became hold, the approved figures would apply as written.
- The live eligible count is not read here (no 2023+ computation). Whether the live book is trading
  today is `python3 -m ops.orient` PROD's.
- The 2008 tail (§3).

## Reproduce

`SCRATCH` holds the allocation series (see `_common.py`).

```bash
python3 -I results/cef/prereg_voltarget/flatten_series.py --scratch SCRATCH --out FLAT --hold-out HOLD \
    --harness-tree WORKTREES/research-thin-days          # builds both roots; reproduction checks (about 1 min)
cd results/cef/prereg_voltarget
python3 derive.py --scratch FLAT --remeasure --stamp 2026-11-02_flatten --m-core 1.13 --m-c4 1.27
python3 risk.py --scratch FLAT --stamp 2026-11-02_flatten \
    --books "today=1.0,1.0;live=1.13,1.27;flatten-active-derived=1.30,1.26;flatten-calendar-derived=1.96,1.26"
python3 stops.py --scratch HOLD --m-core 1.13 --m-c4 1.27                 # reproduces the approved thresholds
python3 stops.py --scratch FLAT --m-core 1.13 --m-c4 1.27 [--core-earning-only FLAT/flatten_masks.parquet]
python3 flatten_remeasure.py --flat-root FLAT --hold-root HOLD --m-core 1.13 --m-c4 1.27 --m-c4-rule 1.2642
python3 flatten_remeasure.py --flat-root FLAT --hold-root HOLD --m-core 1.30 --m-c4 1.26 --m-c4-rule 1.2642 --stamp 2026-11-02_m1.30
python3 derive.py --scratch FLAT --remeasure --stamp 2026-11-02_flatten_m1.30 --m-core 1.30 --m-c4 1.26   # §4b: the plateau at x1.30
cd ../../.. && python3 -I results/cef/prereg_voltarget/flatten_exact.py --flat-root FLAT \
    --harness-tree WORKTREES/research-thin-days --m 1.0 --m 1.13 --m 1.30        # §4b: exact B, cap binding
```

Outputs: `flatten_series_2026-11-02.json`, `derive_*_2026-11-02_flatten.*`, `plateau_grid_2026-11-02_flatten.csv`,
`live_pair_grid_2026-11-02_flatten.csv`, `risk_*_2026-11-02_flatten.*`, `flatten_remeasure_*_2026-11-02*.{json,txt}`.
