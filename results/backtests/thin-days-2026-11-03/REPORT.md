# Thin sessions: the harness's hold rule against the live flatten rule (final report, 2026-11-03)

Written to disk by the main session from the workflow's final report (the subagent's file tool refused
report files), 2026-11-03. The code and data it cites are committed on `research-thin-days` at f975f4a.

**Report only. Zero trials, no spec change, no edit to the live path, no pre-registration drafted.**
Branch `research-thin-days`. The CEF counter is not moved. This follows up F3 of
`results/backtests/turnover-live-2026-11-02/REPORT.md` and defect A1 of
`results/cef/ALPHA_LEAKAGE_2026-10-13.md`. Three independent passes checked the first build (7c0b709): a
review, a re-derivation from the code and a beta-detector pass. This version includes their fixes and attacks
(§7).

**Labels.**
- [V]: computed in this workflow by the committed script named, on the repo panels.
- [S]: quoted from the document or pass named, not re-run here.
- [U]: an interpretation, or arithmetic on approximate inputs.

**Panels.**
- Spec `cef_discount.v7.20260928`, read through `scripts/cef/spec.py`. That is the spec on this branch and on
  `main`. The newest release tag carries v8 (§6).
- Prices end 2026-10-15 and NAV 2026-10-14, so the paired panel and the targets end **2026-10-14**.
- Universe distributions end 2026-09-03 (AWF), so **every return is cut at DIST_END = 2026-09-03**. The
  script asserts that each name's next expected ex-date falls after that date; the earliest is 2026-09-13 [V].
- IBKR fee panel 2021-09-13 to 2026-09-09; borrow snapshot file to 2026-09-21.
- All panels are stale against today, 2026-11-02. `data/` was read, never written: the file times are
  unchanged [V].

---

## The answer

**Which rule scored higher.** The figures are gross total return [V, `thin_days.py`]:

| window | higher gross return | hold − flatten, pp/yr (NW t) |
|---|---|---|
| FIT, before 2023 | **hold** | +1.71 (2.13) |
| 2010-14 | hold | +1.54 (1.78) |
| 2015-19 | hold | +4.76 (1.81) |
| 2020-22 | flatten, by a margin with no significance | −0.24 (−0.12) |
| H13, 2023 on | a tie | −0.02 (−0.03) |

Hold scored higher in the fit period. Almost all of that came from 2015-19. On the 2023 holdout the two rules
are the same book except for one 138-session stretch, and they earned the same.

On Sharpe, flatten is higher in 2020-22 (1.37 against 1.02) and H13 (2.07 against 1.95), and lower in the fit
period (0.58 against 0.69). Bootstrap intervals for the Sharpe gap contain zero in every window (§5.G).

**Did hold's extra return survive the attack as alpha? No.** It is real gross P&L on this panel. It is not
a stale-price artefact, not distribution carry, not market beta and not leverage. But it is not shown to be
alpha, for five reasons [V, `attack.py`]:

1. **It is under the deflated bar.** The t is 2.13 on daily differences and 1.88 across the 21 fit-period
   thin stretches. The bar √(2 ln N) is 2.81 to 2.83 for N = 52 to 54. Under the desk's `read_result`, with
   a Šidák adjustment at N = 54, the result reads **INCONCLUSIVE**: interval [−0.94, +4.36]pp/yr.
2. **It is one name.** Take PHK's own P&L out of the gap and the fit edge falls from 1.71 to 0.58pp/yr
   (t 0.87). Rebuild the books on the universe without PHK and the gap is −0.12 (t −0.20). Take out any
   other single name and the gap keeps a t of at least 1.83.
3. **It is ten days.** The ten best days of the gap in 2015-19 sum to 23.77pp, against an era total of
   23.74pp. Without the best ten days, the fit gap's t is 0.52.
4. **It is one stretch.** The thin stretch from 2019-03-27 to 2020-01-02 earned 12.15 of the 25.34pp that
   hold made on thin days (48%).
5. **Borrow could reverse its sign for real money.** A uniform fee of 9.2%/yr on hold's extra shorts erases
   the fit gap. Over 2021-09-13 to 2022-12-30, where the IBKR panel measures borrow, hold's extra shorts cost
   5.53%/yr and the gap goes from +1.02 gross to −4.51 net. Borrow before 2021-09 is unmeasured.

One control favours hold. Reassign each stretch's frozen weights at random across names and hold beats the
result: p 0.011 over 5,000 draws. So the direction of the frozen book matters. That direction is the
strategy's standing tilt, which books from 21 to 252 sessions earlier share and earn on as well (§4.6). In
practice the tilt is the PHK and PTY positions.

**What follows.**
- No thin-day rule change survives as plausible alpha, so **no pre-registration is drafted** (§8). A fair
  test is not feasible on this universe. At the observed per-stretch effect it would need about 47 thin
  stretches to clear the bar, and the fit period has 21 (§5.E).
- The rule choice stays the team lead's (open question 1).
- Three findings matter whichever rule is kept:
  - **Trial 53 is active in tag `release-20261102-1`.** Its core figures were derived on the hold book.
    Under the live rule, its m = 1.13 core reads SR 0.795 and maximum drawdown 7.53% on W1, against the
    0.923 and 14.84% it was approved on (§6).
  - **On 2020-03-18 and 2025-04-07 the harness and the live sleeve do different things** (§5.H). The
    harness's choice on 2025-04-07 adds about 0.6pp/yr to every H13 figure.
  - **The rule can still bind.** The eligible count sat at exactly 6 on 192 sessions up to 2026-02-12
    (§5.I).

---

## Summary of the attack and its disposition

| attack | result [V, `attack.py` unless marked] | disposition |
|---|---|---|
| stale prices | thin-held name-days have 5.42% zero-return days against 5.29% on active days (fit); no zero-volume days (`thin_days.py`) | not the cause |
| distribution carry | of the 1.41%/yr thin-day P&L (fit), the price leg is 1.43 and distributions are −0.02 (`thin_days.py`) | not the cause |
| market beta | beta to the equal-weight universe −0.012; alpha part 1.49 (t 1.81) (`thin_days.py`) | not the cause |
| factor beta (HYG, IEF, MUB, BKLN, SPY) | summed betas within ±0.04, R² 0.004; alpha t 2.16 [S: beta-detector pass] | not the cause; also fails D4's alpha t of 3.0 |
| leverage | thin-day gross 1.22 against 1.18 active (2013-22); return per unit of gross 3.85 against 6.88%/yr [S: beta-detector] | not the cause |
| harness rebalancing | frozen shares, as the live hold key holds them, earn 26.96pp against frozen weights' 25.34pp; under frozen shares gross reaches 1.91, above the 1.8 cap | the harness understates hold slightly; not the cause |
| one name | without PHK's own P&L: fit 0.58 (t 0.87); rebuilt without PHK: −0.12 (t −0.20) | **explains it** |
| a handful of days | 2015-19: the best 10 days sum to 23.77pp of 23.74pp | **explains it** |
| one stretch | 2019-03-27 to 2020-01-02 earned 48% of thin-day P&L; run-level t 1.88, 16 of 21 positive, exact sign-flip p 0.019 | **concentrated** |
| deflated bar | t 2.13 and 1.88 against 2.81 to 2.83; P(clearing the bar, if the true t equals the observed one) 0.24 to 0.25 | **fails** |
| borrow (real money) | break-even 9.2%/yr (fit); where measured, net −4.51pp/yr (2021-09 to 2022) | **sign unknown before 2021**; a gap, not a kill |
| lagged-book placebo (§4.6) | books 63 to 126 sessions earlier earn 1.48 to 1.53%/yr against hold's 1.41 | the P&L is not specific to the frozen book; it belongs to the strategy's tilt |
| random-name control | hold 1.41%/yr against a null mean of 0.17 (sd 0.54), p 0.011 | direction matters; that direction is the tilt toward PHK and PTY |
| hindsight universe | the fit-period thin stretches exist because the 2026 universe is projected back into years when most of it was illiquid [S: beta-detector] | cannot be measured; disclosed |
| flatten's 2020-22 edge | return gap t −0.12; Sharpe gap interval [−0.08, +0.89]; on days flatten held a book, its SR is 1.84 against hold's 1.78 | there is nothing to explain (§4.7) |

---

## 1. The live rule, read from the code (no file edited)

`src/deploy/sleeves/cef_discount.py::target_positions`, at this branch's HEAD:

| behaviour | where | what it does |
|---|---|---|
| panel | l.625 to l.636 | an inner join of price and NAV (`nav > 0.5 & close > 0.5`), pivoted |
| z | l.756 to l.758 | `rolling(z_window, min_periods=120)` of the discount, `.shift(1)`, clipped at ±4; the same as `band_frontier.build_panel` |
| ADV | l.759 | `(px*vol).rolling(63, min_periods=21).mean().shift(1)`; the same as the harness |
| eligibility | l.795 to l.827 | the name needs a finite z, a measured ADV and an ADV at or above `min_adv_usd` |
| NAV age (`max_nav_age_bd`) | l.829 to l.834 | **cannot bind behind a finite z**, because `nav` comes from the same inner join. The sleeve dropped no name for it on any of 5,480 dates [V, `sleeve_thin.csv`] |
| runner holds (`extras["nav_hold"]`) | l.796 to l.808, l.837 | run time only; no history |
| `min_names` (6) | l.841 | `len(row) < min_names` starts the thin branch |
| `below_min_names = "hold"` | l.884 to l.891 | not live: the core spec has no key, and `src/deploy/registry.py` reads an absent key as `"flatten"`. C4's spec sets `"hold"` |
| **flatten** | **l.892 to l.895** | **every name FLAT, returned before the band (l.1061 to l.1091) and the ceiling (l.1116)** |

`quantt/session/decide.py`:
- FLAT becomes 0 shares (l.243 to l.244).
- A close is not a flip: l.332 needs `tgt != 0`.
- v7's `min_trade_usd` is $0.

**So a flattened sleeve goes straight to zero.** At the next session with 6 or more eligible names, the band
opens from flat to the **band edge**. `is_opening_session` (`quantt/session/run.py` l.666 to l.678) is True
only before the account's first fill, so re-entry is not a full-target build.

Runner gate 5 (refuse or hold on a missing NAV) would have turned 0 of the 3,622 historical thin sessions
into a hold [S: review pass, `gap_check`].

Both behaviours are modelled:
- The harness's `"flatten"` is exactly the live rule.
- Its `"hold"` carries the previous target, so in practice it freezes the book in weight space.
- The live `"hold"` key would freeze **shares**, with the ceiling off while it lasts (§5.C).

## 2. The harness option, its no-op proof, its tests, and the guard added after review

`scripts/cef/band_frontier.py`:
- **`_eligible`.** `build_targets`' loop body, moved verbatim, so there is one eligibility rule.
- **`thin_sessions(index, ...)`.** True when fewer than `min_names` names are eligible.
- **`band_gross_capped(..., below_min_names="hold", thin=None)`.** `"hold"`, the default, runs the
  unchanged loop. `"flatten"` sets the held book to zero on a thin row and requires `thin`.
- **`_check_thin_matches_T`** (new, review defect 3). It refuses a mask that was not counted with T's own
  arguments, using `build_targets`' own signature:
  - a row flagged thin must repeat the previous row exactly;
  - a nonzero row that repeats its predecessor must be flagged thin.

  Zero rows are exempt. On today's panel the check passes on every row of both the spec targets and the WIDE
  targets. It fails the review's mismatch (WIDE targets with the spec-floor mask) on 3,621 rows [V,
  `attack.py`'s run and a scratch check].

**The default is byte-identical** [V]. `noop_hash.py` hashes eight default-path objects (sha256 over
values, index and columns), and its output after the guard was added equals both `noop_before.txt` and
`noop_after.txt`.

**Tests** (`scripts/cef/tests/test_band_below_min_names.py`, synthetic panels; 7 tests):
1. The default is `"hold"` and equals a copy of the pre-edit loop.
2. Flatten goes straight to zero and reopens at the band edge. The fixture's day 1 moved to 0.29, so that
   no active day repeats its predecessor.
3. Flatten equals an independent loop, with T held on thin rows as `build_targets` holds it.
4. Bad arguments raise.
5. `thin_sessions` flags exactly the sessions on which `build_targets` holds.
6. Flatten and hold agree up to the first thin session.
7. **New:** a mask built with other arguments raises in both directions. This is checked by hand and on a
   synthetic panel at a looser and at a stricter ADV floor.

**Mutation checks**, each applied and reverted [V]:
- The guard's call removed, either raise removed, or the zero-row exemption removed: test 7 fails in each
  case.
- Default `"flatten"`: tests 1, 2, 3, 4 and 6 fail.
- A thin row banded toward zero instead of zeroed: tests 2, 3 and 6 fail.

**The full suite** (`python3 -m pytest`) exits 0 [V].

**Second methods.** Each is asserted on every run of `thin_days.py` [V]:
- The live sleeve run on all 5,480 dates gives the same 3,622 thin dates and the same counts.
- An independent pandas loop gives the same flatten books (max abs difference 0.0).
- `harness.report` reproduces the flatten book's fit and holdout Sharpe ratios.

The re-derivation also rebuilt all four books from the code, before reading the build's code, and matched
them to 0.0 [S: re-derivation pass].

## 3. Both rules × both flip modes, by era

**What every row is.**
- Total return. Decide at t, fill at t+1, earn the t+2 return (`evaluate`).
- Turnover is Σ|ΔH| × 252 / n.
- Net = ann − turn × c at c = 5, 15 and 30bp. This is the **real-money view, labelled, not the headline.**
- BE = ann / turn. maxDD is compounded within the window.
- **No borrow is charged** (§5.F).
- The "sign flips?" column gives the first grid cost at which net and gross have opposite signs.

**Sizing.** These are v7 unit-sized books; §6 adds trial 53's m.

**Effect of the two degenerate sessions.** The live sleeve's behaviour on those dates (§5.H) lowers every
book's H13 return by 0.59 to 0.61pp/yr. FIT moves by 0.01 or less, and hold − flatten does not move.

All figures are [V], `thin_days.py`.

| window | rule | flips | SR | ann % | vol % | maxDD % | turn/yr | net %/yr @5 / @15 / @30 | BE bp | sign flips? |
|---|---|---|---:|---:|---:|---:|---:|---|---:|---|
| 2005-09 | both | both | flat: nothing held | | | | 0.0 | | | |
| 2010-14 | hold | instant | 0.72 | 2.24 | 3.12 | -4.5 | 5.2 | 1.98 / 1.46 / 0.69 | 43.3 | no |
| 2010-14 | hold | deferred | 0.72 | 2.25 | 3.12 | -4.5 | 5.0 | 2.00 / 1.50 / 0.75 | 44.9 | no |
| 2010-14 | flatten | instant | 0.29 | 0.69 | 2.40 | -5.2 | 7.3 | 0.33 / -0.40 / -1.50 | 9.5 | yes (15bp) |
| 2010-14 | flatten | deferred | 0.30 | 0.73 | 2.40 | -5.2 | 7.2 | 0.37 / -0.35 / -1.42 | 10.2 | yes (15bp) |
| 2015-19 | hold | instant | 0.84 | 5.70 | 6.83 | -12.8 | 7.8 | 5.31 / 4.53 / 3.36 | 73.2 | no |
| 2015-19 | hold | deferred | 0.82 | 5.62 | 6.83 | -12.8 | 7.6 | 5.24 / 4.48 / 3.34 | 74.0 | no |
| 2015-19 | flatten | instant | 0.38 | 0.95 | 2.48 | -6.6 | 8.7 | 0.51 / -0.36 / -1.68 | 10.8 | yes (15bp) |
| 2015-19 | flatten | deferred | 0.35 | 0.86 | 2.48 | -6.8 | 8.6 | 0.43 / -0.44 / -1.73 | 9.9 | yes (15bp) |
| 2020-22 | hold | instant | 1.02 | 6.49 | 6.36 | -4.3 | 21.5 | 5.41 / 3.27 / 0.05 | 30.2 | no |
| 2020-22 | hold | deferred | 0.90 | 5.84 | 6.52 | -4.3 | 20.7 | 4.80 / 2.74 / -0.37 | 28.2 | **yes (30bp)** |
| 2020-22 | flatten | instant | 1.37 | 6.73 | 4.92 | -3.5 | 24.2 | 5.52 / 3.10 / -0.52 | 27.8 | yes (30bp) |
| 2020-22 | flatten | deferred | 1.19 | 6.12 | 5.15 | -3.7 | 23.4 | 4.96 / 2.62 / -0.89 | 26.2 | yes (30bp) |
| FIT <2023 | hold | instant | 0.69 | 3.29 | 4.73 | -12.8 | 7.2 | 2.93 / 2.21 / 1.13 | 45.8 | no |
| FIT <2023 | hold | deferred | 0.66 | 3.16 | 4.77 | -12.8 | 7.0 | 2.81 / 2.12 / 1.07 | 45.4 | no |
| FIT <2023 | flatten | instant | 0.58 | 1.58 | 2.72 | -6.6 | 8.5 | 1.15 / 0.30 / -0.97 | 18.6 | yes (30bp) |
| FIT <2023 | flatten | deferred (live rule) | 0.53 | 1.46 | 2.78 | -6.8 | 8.3 | 1.05 / 0.22 / -1.02 | 17.6 | yes (30bp) |
| H13 2023+ | hold | instant | 1.95 | 10.61 | 5.43 | -4.9 | 44.7 | 8.37 / 3.91 / -2.79 | 23.8 | yes (30bp) |
| H13 2023+ | hold | deferred | 1.81 | 9.85 | 5.44 | -5.0 | 42.1 | 7.75 / 3.55 / -2.76 | 23.4 | yes (30bp) |
| H13 2023+ | flatten | instant | 2.07 | 10.63 | 5.13 | -2.9 | 44.7 | 8.39 / 3.92 / -2.79 | 23.8 | yes (30bp) |
| H13 2023+ | flatten | deferred (live rule) | 2.02 | 10.34 | 5.11 | -3.2 | 42.2 | 8.23 / 4.00 / -2.34 | 24.5 | yes (30bp) |
| full | hold | instant | 0.93 | 4.52 | 4.86 | -12.8 | 13.5 | 3.85 / 2.50 / 0.47 | 33.5 | no |
| full | hold | deferred | 0.88 | 4.29 | 4.89 | -12.8 | 12.9 | 3.65 / 2.36 / 0.42 | 33.3 | no |
| full | flatten | instant | 0.95 | 3.11 | 3.26 | -6.6 | 14.6 | 2.38 / 0.92 / -1.28 | 21.3 | yes (30bp) |
| full | flatten | deferred | 0.90 | 2.96 | 3.30 | -6.8 | 14.0 | 2.26 / 0.86 / -1.25 | 21.1 | yes (30bp) |

**Correction to the first build's text (review defect 2).** The build said "hold's net never changes sign in
any fit era". That holds for **instant** flips only. With **deferred** flips, which is how the live runner
trades, hold turns negative at 30bp in 2020-22 (−0.37%/yr). Hold with instant flips survives that era by
+0.05%/yr. Flatten turns negative at 15bp in 2010-14 and 2015-19, and at 30bp in the fit period as a whole.

**The vol-matched view** (each book scaled to the spec's 6% on its own ex-post vol, descriptive only), the
A2-window context rows and the era turnover dispersion are in `run.log` and `results.json`. Era turnover
sd/mean (H5) over the four traded eras is 0.91 for hold and 0.82 for flatten, both with instant flips [V].

**Deferred minus instant** (pp/yr, NW t) [V]:

| window | hold | flatten |
|---|---|---|
| FIT | −0.13 (−1.28) | −0.12 (−1.24) |
| H13 | −0.75 (−1.89) | −0.29 (−0.73) |
| A2 2013-06-14+ | −0.38 (−2.13) | −0.24 (−1.37) |

**H2 context (turnover matching).** The rows are not turnover-matched: fit turnover is 7.18/yr under hold and
8.5/yr under flatten. To match them, flatten (instant) was matched to hold's fit turnover by bisection on
turnover only, which lands at a band of 6.42% [V].
- Fit: SR 0.52, ann 1.38%, net 1.02 / 0.30 / −0.77, break-even 19.2bp.
- H13: SR 2.06, ann 10.46%.

The fit ordering does not change. The 6.42% width is a matching device, not a proposal.

## 4. Where hold's extra return comes from

The book is hold with instant flips unless stated. An earning day d is attributed H[d−2] × R[d] by name, and
the script asserts that the attribution sums to `evaluate`'s P&L. All figures are [V], `thin_days.py`.

### 4.1 The split (flatten minus hold, pp/yr)

| window | flips | total | on thin-decision days (flatten earns exactly 0) | active days, books differ [days] |
|---|---|---:|---:|---|
| 2010-14 | instant | −1.54 | −1.45 | −0.10 [265] |
| 2015-19 | instant | −4.76 | −3.99 | −0.77 [352] |
| 2020-22 | instant | +0.24 | +0.60 | −0.36 [357] |
| FIT | instant | −1.71 | −1.41 | −0.30 [**974**] |
| H13 | instant | +0.02 | +0.02 | +0.01 [664] |
| FIT | deferred | −1.70 | −1.43 | −0.26 [**977**] |
| H13 | deferred | +0.48 | 0.00 | +0.48 [671] |

The fit day counts were 976 and 979 in the first build. The extra two days were 2005-01-03 and 2005-01-04,
counted because NaN != NaN; the error was found by the re-derivation and is now fixed. The P&L was not
affected.

So 1.41 of the 1.71pp/yr fit edge is P&L earned on thin days by a book flatten does not hold. The other 0.30
is the cost of reopening at the band edge.

### 4.2 Which names were held on thin days

| window | name passed every test; the cross-section was short | ADV below the $3m floor |
|---|---|---|
| 2010-14 | +1.08 [555 name-days] | +0.37 [376] |
| 2015-19 | +4.36 [4,328] | −0.37 [4,732] |
| 2020-22 | −1.01 [1,641] | +0.41 [1,925] |
| FIT | +1.34 [6,524] | +0.07 [7,033] |
| H13 | +0.35 [690] | −0.37 [966] |

No held name lacked a z-score on a thin session, and the NAV-age test never bound.

Eligible names on thin dates, as count (sessions):
- 2010-14: 1 (81), 2 (316), 3 (258), 4 (173), 5 (155).
- 2015-19: 4 (202), 5 (706).
- 2020-22: 4 (39), 5 (295).
- 2023 on: 5 (138).

So since 2015 a thin session has meant one or two names short of 6.

**For real-money capacity:** hold carries names below the ADV floor on 7,033 of the 13,557 fit-period
thin-held name-days [V].

### 4.3 By name

Thin-day P&L (ann % of the window):

| name | 2010-14 | 2015-19 | 2020-22 | 2023+ | FIT |
|---|---:|---:|---:|---:|---:|
| PHK | 0.82 | 2.60 | 0.76 | 0.01 | 1.08 |
| PTY | 0.48 | 1.65 | −0.76 | −0.16 | 0.46 |
| HYT | −0.15 | 0.88 | −0.58 | 0.30 | 0.11 |
| JFR | 0.00 | 0.67 | 0.38 | −0.01 | 0.25 |
| PDI | 0.65 | 0.12 | 0.13 | 0.21 | 0.23 |
| AWF | −0.26 | −1.67 | 0.28 | 0.04 | −0.49 |
| DSL | −0.07 | −0.63 | −0.29 | −0.07 | −0.24 |

§5.A measures what this concentration means for the gap.

### 4.4 to 4.5 Stale prices, gross and the age of the frozen book

**Stale prices.** On held name-days, the share of exactly-zero total returns is 5.42% on thin days and 5.29%
on active days (fit). It is 5.67% against 6.14% in 2015-19 and 5.19% against 4.35% in 2020-22. No held
name-day had zero volume.

**Mean gross held, thin against active decisions:**

| window | thin | active |
|---|---:|---:|
| 2015-19 | 1.33 | 1.18 |
| 2020-22 | 0.99 | 1.12 |
| FIT | 0.48 | 1.18 |

**Age of the frozen book.** In 2015-19, 2.25 of the 3.99%/yr thin-day P&L came from books not re-decided for
more than 21 sessions.

### 4.6 Carry, beta, and the lagged-book placebo (reading revised)

| window | thin ann % | price leg | distribution leg | beta to equal-weight universe TR | alpha part (NW t) |
|---|---:|---:|---:|---:|---|
| 2015-19 | 3.99 | 3.35 | 0.64 | −0.115 | 4.24 (1.62) |
| 2020-22 | −0.60 | 0.26 | −0.86 | −0.094 | −0.16 (−0.08) |
| FIT | 1.41 | 1.43 | −0.02 | −0.012 | 1.49 (1.81) |
| H13 | −0.02 | 0.34 | −0.36 | −0.328 | 0.03 (0.04) |

**The lagged-book placebo.** Over every thin stretch, the frozen book is replaced by the book held L
sessions before it. Each cell is thin-day P&L in ann %, with the mean cosine to the L = 0 book in brackets:

| window | L=0 | L=21 | L=63 | L=126 | L=252 |
|---|---:|---|---|---|---|
| 2015-19 | 4.04 | 2.29 (0.67) | 4.25 (0.34) | 2.90 (0.08) | 0.70 (0.18) |
| 2020-22 | −0.60 | 0.62 (0.70) | 0.20 (−0.05) | 2.57 (−0.37) | 1.81 (−0.57) |
| FIT | 1.42 | 1.09 (0.69) | 1.48 (0.26) | 1.53 (−0.02) | 0.61 (−0.01) |

**Revised reading** (beta-detector F8 and the review; the first build said "fails the placebo control"):
- The lagged books are the same strategy at an earlier date, not a control in which the mechanism cannot
  work.
- So the test shows that the thin-day P&L is **not specific to hold's frozen book**: being invested in
  any recent book of this strategy earned about as much.
- It does not show that the strategy earns nothing on those days.
- The random-name control in §5.D does test direction, and the direction matters (p 0.011). The direction
  that pays is the strategy's standing tilt. Over 2013-22 active decisions it was short PHK 61% of the time
  and PTY 58% [S: beta-detector].
- Hold's thin-day book earns −0.22pp/yr without PHK and PTY over 2013-22 [S: beta-detector], so the tilt that
  pays is those two names (§5.A).

### 4.7 Flatten's 2020-22 edge

- **The Sharpe gap is vol arithmetic.** Flatten is flat on 334 of 756 sessions. On the 420 earning days it
  held a book, its SR is 1.84 against hold's 1.78 on the same days [V, `attack.py`].
- **The return gap is not significant** (t −0.12). It is +0.60 from not holding hold's losing frozen books,
  less 0.36 for reopening at the band edge.
- **The March-2020 crash is not the explanation.** There were zero thin decisions from 2020-01-03 to
  2020-06-22 [S: beta-detector].

## 5. The attack, re-run on the canonical path (`attack.py`)

All of §5 is [V] from `attack.py`, except where marked. Seeds and draw counts were declared in the script
before it ran.

**A. One name.** Hold − flatten with one name's own P&L taken out, pp/yr (NW t):

| left out | 2015-19 | FIT | H13 |
|---|---|---|---|
| none | 4.76 (1.81) | 1.71 (2.13) | −0.02 (−0.03) |
| PHK | 1.95 (0.95) | **0.58 (0.87)** | 0.32 (0.38) |
| PTY | 3.13 (1.35) | 1.26 (1.75) | 0.15 (0.22) |
| PHK and PTY | 0.32 (0.29) | **0.13 (0.28)** | 0.49 (0.78) |
| every other single name | 3.81 to 6.45 | 1.46 to 2.24 (t ≥ 1.83) | −0.36 to 0.20 |

`attack.log` prints all 13 rows. The fit gap's largest contributors are PHK +1.13, PTY +0.45, JFR +0.25 and
PDI +0.22.

**Rebuilt universes.** These are different, thinner books, because a smaller universe is thin more often:

| rebuilt without | thin sessions | FIT gap (t) | 2015-19 gap (t) |
|---|---:|---|---|
| PHK | 4,175 | −0.12 (−0.20) | +0.39 (0.23) |
| PTY | 4,517 | +1.38 (1.30) | +3.76 (1.12) |
| PHK and PTY | 4,800 | −0.17 (−0.43) | +0.25 (0.45) |

The two methods agree: the fit edge does not survive without PHK.

**What happened on PHK's biggest days** [S: beta-detector, from a read of the panel]:
- On 2019-04-02 PHK opened at 8.23 against a prior close of 9.04, on 6.17m shares. The panel shows the
  distribution cut from 0.081 to 0.061 at the 2019-04-10 ex-date.
- On 2015-04-09 PHK fell 9.7% and on 2015-06-22 it fell 7.3%.

These are real, high-volume collapses of a fund trading at a premium, not bad prints. PHK was held long on
two-thirds of 2015-19 thin decisions; the gap's largest PHK days were short [S: beta-detector].

**B. A handful of days.**
- 2015-19: the gap totals 23.74pp and its best 10 days sum to 23.77pp. Without the best and worst 10 days
  the t is 1.29.
- FIT: without the best 10 days the gap is 6.11pp (t 0.52).
- The best days are 2019-04-02 (+3.63), 2015-04-09 (+3.18), 2015-06-22 (+3.00), 2018-06-14 (+2.57) and
  2018-10-11 (+2.27).

**C. Thin stretches as the unit of inference.**
- There are 21 fit-period stretches with a held book. Together they earned 25.34pp, which is 1.41%/yr of the
  fit window.
- Run-level t is 1.88, 16 of 21 stretches are positive, and the exact one-sided sign-flip p over all 2^21
  sign vectors is 0.019.
- The largest stretch (2019-03-27 to 2020-01-02, gross 1.70) earned 12.15pp. Without it the total is
  13.19pp.
- **The live `"hold"` key** freezes shares, not weights. Frozen shares earn 26.96pp over the same stretches,
  and gross drifts up to 1.91, above the 1.8 ceiling, which that key leaves off while it lasts. So the
  harness's hold slightly understates what the deployable hold key would earn, and understates its gross.

**D. Random-name control.** Each stretch's held weights were reassigned across the names that traded, in
5,000 draws (seed 20261103). Hold's thin-day P&L is 1.41%/yr. The null has mean 0.17, sd 0.54 and a 95th
percentile of 1.05, so P(null ≥ hold) = 0.011. The direction matters; §4.6 says which direction.

**E. Bar and power** (`scripts/research/inference.py`):

| N | bar √(2 ln N) | P(clear the bar \| true t = 2.13 paired / 1.88 runs) | stretches needed at the observed per-stretch effect | `read_result`, Šidák at N |
|---|---:|---|---:|---|
| 52 (main) | 2.811 | 0.25 / 0.18 | 47 | INCONCLUSIVE [−0.93, +4.35]pp/yr |
| 53 (release tag; trial 53) | 2.818 | 0.25 / 0.17 | 47 | INCONCLUSIVE [−0.94, +4.36] |
| 54 (a thin-rule trial) | 2.825 | 0.24 / 0.17 | 47 | INCONCLUSIVE [−0.94, +4.36] |

`read_result` takes the observed fit gap, 1.71pp/yr, as the meaningful size. Its power at that size is 0.12.

**The counter differs between refs** [V, `git show`]: 52 on `main` and this branch, 53 on `prereg-voltarget`
and at `release-20261102-1`. The reading is the same at either.

**F. Borrow.** No other figure in this report charges borrow. Paper charges none, so this matters for real
money only.
- **The uniform fee that erases the gap** on hold's extra short weight is 9.2%/yr over FIT (extra short
  0.185) and 10.4%/yr over 2015-19 (extra short 0.456).
- **The 2015-19 extra shorts by name:** PTY 0.095, PHK 0.086, AWF 0.078, DSL 0.073, PDI 0.060, JFR 0.051.

**Measured on the IBKR FEE_RATE panel**, as a simple annual rate on short weight:

| window | hold | flatten | extra | gap gross → net |
|---|---:|---:|---:|---|
| 2021-09-13 to 2022-12-30 | 12.78% | 7.26% | 5.53% | +1.02 → **−4.51** |
| 2023-01-03 to DIST_END | 6.75% | 4.63% | 2.12% | −0.02 → −2.15 |

The panel has no independent source for its levels before 2026-09 [S: `docs/REFERENCES.md`].

**A sensitivity, not history.** Later fee regimes applied to 2015-19:

| fee regime | net gap, pp/yr |
|---|---:|
| the 2021-22 mean (PHK 27.2, PTY 26.5%/yr) | −3.40 |
| the 2023+ mean (PHK 12.9, PTY 30.8) | −0.64 |
| the 2026-09-21 snapshot (PHK 0.7, PTY 1.4) | +4.34 |

The sign depends on fees that were never measured for 2013-19.

**G. Sharpe gap** (flatten − hold). Stationary bootstrap with a mean block of 21 and 4,000 draws:

| window | gap | 95% interval |
|---|---:|---|
| 2020-22 | +0.35 | [−0.08, +0.89] |
| H13 | +0.12 | [−0.18, +0.49] |
| FIT, from 2013-06-25 (the first earning day of either book) | −0.16 | [−0.60, +0.30] |

Neither rule can be told apart on Sharpe in any window.

**H. Two degenerate sessions** (found by the re-derivation, confirmed here).

**What happened.** On 2020-03-18 (9 eligible names) and 2025-04-07 (7 eligible), every eligible z sat at
the −4 clip. The weights are then 0/0, which gives NaN.

**What each side does with that:**
- **The harness.** `build_targets` fills the NaN with 0, so the band cuts every held name to ±0.048: 1.91
  gross of turnover with instant flips.
- **The live sleeve.** It gets a NaN gap, `abs(nan) > band` is False, and it **holds every name**. Called
  read-only on both dates with the previous book as holdings, it held all 9 names on each date, with the
  reason "cef band hold: |gap|<=0.0480". That reason is false.

Neither side raises, so on these sessions both are silent fallbacks.

**Replay of every book with the sleeve's behaviour** (ann %, harness → sleeve):

| book | FIT | 2020-22 | H13 |
|---|---|---|---|
| hold, instant | 3.29 → 3.28 | 6.49 → 6.44 | 10.61 → 10.02 |
| hold, deferred | 3.16 → 3.16 | 5.84 → 5.83 | 9.85 → 9.24 |
| flatten, instant | 1.58 → 1.57 | 6.73 → 6.68 | 10.63 → 10.04 |
| flatten, deferred (live rule) | 1.46 → 1.46 | 6.12 → 6.12 | **10.34 → 9.73** |

Hold − flatten is unchanged in every window. **Every H13 figure the harness produces is about 0.6pp/yr
higher than the live code would have earned, almost all from 2025-04-07.** This report does not change
`build_targets`, because that would move every figure that cites it, and `src/deploy/` is outside this task
(open question 4).

**I. The rule can still bind.**
- The last thin session was 2023-08-30. Since then the eligible count sat at exactly 6 on **192 sessions**,
  from 2023-08-31 to 2026-02-12: 77 in 2023, 114 in 2024 and 1 in 2026.
- On 2026-10-14 (the last panel date) 12 of 13 names were eligible, and AWF was just under the $3m floor at
  $2.97m.

A dip of one or two names makes the rule live again.

**Not re-run here** [S: beta-detector pass]:
- Factor regression: summed betas HYG +0.029, IEF −0.008, MUB +0.033, BKLN −0.005, SPY −0.017; R² 0.004;
  alpha t 2.16. A second HYG and IEF source gives t 2.06.
- Thin-day Sharpe ratio: 0.69 on thin days against 1.35 on active days (2013-22).

## 6. Trial 53 rests on the hold rule, and it is active in the newest release tag

**Correction (review defect 1).** The first build treated activating `sizing_multiplier` on the core as a
future step. It is already done, and it is in a release tag [V, `git`]:
- Commit eca5feb, "ACTIVATE CEF trial 53 on the core: sizing_multiplier 1.13 (v7 → v8.20261101)", is in tag
  `release-20261102-1`.
- That tag's frozen spec reads `cef_discount.v8.20261101` with `sizing_multiplier` 1.13 and no
  `below_min_names`, so the thin rule there is flatten.
- `main` and this branch are on v7.

**Whether prod runs that tag is UNMEASURED here.** `python3 -m ops.orient` PROD answers it, but it reaches
the VM, which this task may not do.

`thin_days.py` builds the m-sized book the way the spec note says the sleeve does: band in unit weights,
ceiling at 1.8/m, emitted as m × the unit weight. It reads m from the tag's frozen spec and asserts that the
hold row reproduces trial 53's committed "B sizing_multiplier" row (`impl_core_2026-11-01_m1.13.json` at the
tag) to 1e-9. It does.

W1, 2013-06-25 to 2022-12-30, total return [V]:

| book | SR | ann % | vol % | maxDD % | turn/yr | mean gross | at cap | BE bp | daily sd |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v7 unit, hold, instant (trial 53's unit book) | 0.955 | 6.21 | 6.50 | 12.78 | 13.5 | 1.206 | 7.3% | 46.1 | 0.004095 |
| v7 unit, flatten, instant | 0.799 | 2.98 | 3.73 | 6.64 | 15.9 | 0.465 | 0.5% | 18.7 | 0.002351 |
| v7 unit, flatten, deferred | 0.723 | 2.76 | 3.82 | 6.82 | 15.6 | 0.460 | 0.5% | 17.7 | 0.002407 |
| **m 1.13, hold, instant (trial 53 as approved)** | 0.923 | 6.66 | 7.22 | **14.84** | 15.4 | 1.289 | 19.5% | 43.2 | 0.004546 |
| m 1.13, hold, deferred | 0.877 | 6.38 | 7.28 | 14.91 | 14.9 | 1.279 | 19.1% | 42.8 | 0.004585 |
| **m 1.13, flatten, instant (the live rule)** | 0.795 | 3.31 | 4.16 | **7.53** | 18.1 | 0.522 | 2.8% | 18.3 | 0.002622 |
| m 1.13, flatten, deferred (the live runner) | 0.718 | 3.06 | 4.27 | 7.74 | 17.6 | 0.516 | 2.6% | 17.3 | 0.002687 |

**What rests on the hold rule.** The trial-53 figures are quoted [S] from
`results/cef/PREREG_VOLTARGET_2026-10-30.md` and the tag's spec note.
- **The multiplier.** The derivation's input sd_k = 0.004095 daily is the hold book's. Under flatten it is
  0.002351 [V]. The multiplier was not recomputed.
- **Term (d)**, the core's mean uncapped gross (1.36 against 1.80).
- **The combined and core return figures:**
  - core exact 6.66% TR, SR 0.923, maxDD 14.84%, at cap 19.5%;
  - zero-edge P(HALVE) 15.9% and P(KILL) 1.5%;
  - the W2 year-end-book proxies.
- **The year-end books.** Five of trial 53's ten year-end core books are thin sessions: 2015-12-31,
  2017-12-29, 2019-12-31, 2020-12-31 and 2021-12-31. Under the live rule those books are flat, including both
  "dangerous" 1.70 to 1.80 books [V].
- **The W1 worst drawdown** (−12.78% at m 1.00) runs from 2017-06-05 to 2018-06-12. 190 of its 257 earning
  days were decided on thin sessions [V].
- **The live stops R1 to R3.** `stops.py` re-measures them from the same hold series.
  - Under the live rule the m 1.13 W1 maximum drawdown is 7.53%, not 14.84%, so the derived drawdown stops
    are calibrated on a book about twice as volatile as the one the core trades in thin stretches.
  - The hold book's thin-day P&L is also PHK-concentrated and sensitive to borrow (§5), so trial 53's core
    risk figures inherit both properties [U].

**Not affected.** C4 sets `below_min_names: "hold"`, so its live rule and its scored rule are the same [S:
first build, `git show`].

This report does not revisit trial 53's approval (open question 2).

## 7. Defects found by the three passes, and what was done

| # | from | finding | verdict | done |
|---|---|---|---|---|
| 1 | review | §5 and Q2 framed activating trial 53 on the core as a future step; it is in `release-20261102-1` | confirmed [V, `git`] | §6 rewritten; m-sized rows added and reproduced; Q2 reframed |
| 2 | review | "hold's net never changes sign in any fit era" is false with deferred flips (2020-22, 30bp) | confirmed [V] | corrected in §3 |
| 3 | review | the flatten path accepted a thin mask built with other arguments (WIDE targets: 3,621 sessions wrongly flattened) | confirmed [V] | `_check_thin_matches_T` added, both directions; test 7 added; four mutations caught; no-op hashes unchanged |
| 4 | re-derivation | the §4.1 [days] counted NaN != NaN on two rows (976 / 979 for 974 / 977) | confirmed [V] | fixed in `thin_days.py`; only those two numbers moved in `results.json` |
| 5 | re-derivation | on 2020-03-18 and 2025-04-07 the harness cuts to the edge while the sleeve holds under a false reason; H13 about −0.6pp/yr on every book | confirmed [V, including a read-only sleeve call] | measured in §5.H; not fixed (the harness and `src/deploy` belong to others); open question 4 |
| 6 | re-derivation | `min_abs_weight` is not modelled; adding it moves FIT ≤ 0.03pp/yr and H13 +0.15 to +0.31 | [S] | disclosed below; ordering unchanged |
| 7 | beta-detector | the gap is PHK, ten days and one stretch; below the bar; borrow could flip its sign | confirmed [V, `attack.py`] | it is now the answer; no pre-registration |
| 8 | beta-detector | the lagged-book placebo is not a valid control | confirmed: the books are the same strategy | §4.6 re-read; random-name control added (§5.D) |
| 9 | beta-detector | "none since 2023-08-30" understates how close the rule is to binding | confirmed [V] | §5.I |
| 10 | beta-detector | the counter differs between refs (52 / 53) | confirmed [V] | bars stated for 52, 53 and 54; the reading is the same; owning session to reconcile |

No finding was refuted. One caveat on finding 7: the rebuilt-without-PHK universe is thin more often (4,175
sessions against 3,622), so it is a different book. The attribution leave-out (0.58, t 0.87) is the cleaner
measure, and the two agree.

## 8. Why no pre-registration is drafted

The task allowed a draft only if a thin-day rule change survives the attack as plausible alpha. None does:
- The one candidate, switching the live sleeve to `"hold"`, scores higher only in the fit period.
- That edge is under the deflated bar at every N, and `read_result` reads it INCONCLUSIVE with power 0.12.
- It does not survive leaving out PHK.
- It rests on ten days and one stretch.
- Its real-money sign depends on borrow that is unmeasured before 2021-09.
- On the 2023 holdout the rules tie.

**A fair test is not feasible on this universe.** At the observed per-stretch effect it needs about 47 thin
stretches, against 21 in the fit period and 1 in the holdout (§5.E). Only opening another panel would add
stretches, and that would spend a holdout or a trial.

**What a test would need, if the team lead wants one later** [U]:
- Thin stretches as the unit.
- Universe-level leave-outs of PHK, and of PHK and PTY, declared as gates in advance.
- Turnover matched within 5%.
- Borrow from the IBKR panel where it exists, with the edge required to survive the 2023+ fee regime.
- Scoring of the deployable hold key (frozen shares, ceiling off), not the harness's frozen weights.
- A statement of how it composes with trial 53's `sizing_multiplier` and the vol scalar. The vol scalar sets
  the unit book on active days only, and the multiplier scales whatever book the thin rule leaves.

## Not modelled (both rules)

- **Run-time holds** (the stale-NAV gate and the missing-NAV hold). On history they never apply.
- **`min_abs_weight`, whole shares and share drift.** The re-derivation measured the `min_abs_weight` steps
  at ≤ 0.03pp/yr on FIT [S].
- **Paper's `late_market` fills.**
- **Borrow,** except in §5.F.
- **Distributions.** Every return is total return, but paper pays no distributions.
- **The live `"hold"` key's frozen shares.** §5.C measures them over the fit stretches only.
- **A third rule** (trading the 4 or 5 eligible names). It is unscored.

## Reproduce (from the worktree root)

```
python3 results/backtests/thin-days-2026-11-03/noop_hash.py           # default-path hashes (compare noop_before.txt / noop_after.txt)
python3 results/backtests/thin-days-2026-11-03/sleeve_thin_check.py   # the live sleeve on all 5,480 dates -> sleeve_thin.csv (about 6 min)
python3 results/backtests/thin-days-2026-11-03/thin_days.py           # §1-§4, §6 -> run.log (gitignored), results.json (about 10 s)
python3 results/backtests/thin-days-2026-11-03/attack.py              # §5 -> attack.log (gitignored), attack.json (about 15 s)
python3 -m pytest scripts/cef/tests/test_band_below_min_names.py
```

`thin_days.py` and `attack.py` read trial 53's spec and figures from tag `release-20261102-1` with
`git show`. They raise if the clone does not hold that tag.

**Committed:**
- 7c0b709: the option, tests, `thin_days.py`, `sleeve_thin_check.py` and the no-op files.
- f975f4a: the guard, test 7, the day-count fix, the release-tag rows, `attack.py` and `attack.json`.

## Open questions for the team lead

1. **The live thin-session rule.**
   - (a) Keep flatten.
   - (b) Switch to hold, which would be CEF trial 54 through `/spec-change`.
   - (c) Score a third rule first.

   **Recommendation: (a).** Hold's extra return is not shown to be alpha. It ties in H13. For real money it
   costs borrow on extra shorts, which already exceeds the gap where borrow is measured. A trial on this
   universe would be underpowered.
2. **Trial 53's core figures rest on the hold book, and v8 is in `release-20261102-1`.** Whether prod runs
   that tag is unmeasured here.
   - (a) Re-measure `derive.py`, `risk.py` and `stops.py` on the flatten book (the rule Q1 keeps).
   - (b) Leave them, with a dated correction note.

   **Recommendation: (a).** First confirm the prod tag with `python3 -m ops.orient` PROD.
3. **The harness reference policy.** The default stays `"hold"`, byte-identical, so every fit-era "live
   policy" figure in the documents is a hold-rule figure. **Recommendation:** the owning session adds dated
   "harness hold, not the live rule" notes.
4. **The two degenerate sessions** (2020-03-18 and 2025-04-07; §5.H).
   - (a) Make both sides explicit: the sleeve holds with an honest reason, and the harness models the hold.
   - (b) Both cut to the band edge.
   - (c) Both raise.

   **Recommendation: (a)**, with a test, done by the sessions that own `src/deploy/` and the harness.
5. **Borrow as a gate, and buying 2013-19 PHK and PTY securities-lending fees.** This is only worth deciding
   if Q1 is reopened.
