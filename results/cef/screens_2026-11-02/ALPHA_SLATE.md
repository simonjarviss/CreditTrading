# Alpha slate for the two-account CEF set-up — 2026-11-02

**Zero trials. No counter moved (CEF 53, EVENTS 3, read from `docs/RESEARCH_STATE.md` at run time by
`alpha_common.counters()`). Nothing here touches the live path, a broker, or `data/`.** The team lead asked
on 2026-11-02 for new return sources that this exact set-up can trade: the core's 13 credit CEFs (account 1)
and C4's 74 non-credit CEFs (account 2). One candidate earns a pre-registration, and it is a **DRAFT** for the
team lead: `results/cef/PREREG_C4_LEVEL_2026-11-02.md` (approved 2026-11-03 as CEF trial 54).

**Holdout discipline.** Every statistic is computed on sessions on or before 2022-12-30. `build_panel(end=…)`
truncates the raw history before any z, mean or ADV is formed, and `alpha_common.assert_fit` asserts it on
every frame. The 27 sealed `cef_universe.csv` names are never loaded: WIDE17 is named explicitly. Counts of
2023–26 corporate events (S6) read no price, NAV or return.

**Panels** (last date in the file / as used):

| panel | last date | used to |
|---|---|---|
| `data/cef/cef_prices.parquet`, `cef_nav.parquet` | 2026-10-15 / 2026-10-14 | 2022-12-30 |
| `data/cef/cef_distributions.parquet` | last ex-date 2026-09-10 | 2022-12-30 |
| `data/cef_families/cef_prices.parquet`, `cef_nav.parquet`, `cef_actions.parquet` | 2026-10-09 | 2022-12-30 |
| `data/etf_daily.parquet` (HYG, IEF) / `data/benchmarks/spy_daily.parquet` | 2026-10-09 / 2026-07-21 (starts 2011-06-01) | 2022-12-30 |
| `results/events/cef_corp_action_events.csv` (EDGAR census) | last filing 2026-10-09 (its note) | counts |

**Universes.** WIDE17 is the deployed 13 plus NAD, NEA, NVG and NZF (credit; `band_frontier.build_panel`, the
live panels). C4 is the frozen 74 (`results/cef/c4/c4_universe_frozen_2026-10-14.csv`); 65 have a paired price
and NAV before 2023. C4 is built with C4's own declared M1|M2 mask. **C4's returns here are the yfinance leg**
(`bf.total_returns` on `cef_actions.parquet` with C4's split rulings). C4's committed fit used CRSP, which is
not in this tree, so every C4 figure below is a second-source figure. As a calibration, the C4 z book on this
leg scores gross SR 1.13, against 1.217 in C4's committed fit [S].

**Reproduce** (worktree root, `862b1d0` + this folder, about 40 s in total):

```bash
python3 -B results/cef/screens_2026-11-02/alpha_taxloss.py         # S1
python3 -B results/cef/screens_2026-11-02/alpha_distchange.py      # S2
python3 -B results/cef/screens_2026-11-02/alpha_leadlag.py         # S3
python3 -B results/cef/screens_2026-11-02/alpha_horizon.py         # S4
python3 -B results/cef/screens_2026-11-02/alpha_level.py           # S5
python3 -B results/cef/screens_2026-11-02/alpha_level_checks.py    # S5, checks K1-K8
python3 -B results/cef/screens_2026-11-02/alpha_events_census.py   # S6
```

Every figure below is **[V]**: computed this session by the named script. Exceptions are labelled. **Each
script's docstring names its negative control before its code.** The controls were written before the first
run (H12).

Bars: CEF √(2 ln 54) = **2.825**; EVENTS √(2 ln 4) = **1.665**, as the brief asked. EVENTS' running N for a new
test is 7, which gives 1.973 (`docs/RESEARCH_STATE.md`, 2026-10-27). That discrepancy needs a ruling, and both
bars are shown where they matter. P(pass) is Φ(t_expected − bar) with the in-sample t taken as the truth, so it
is an upper bound.

> **CORRECTED 2026-11-02 (later), the EVENTS bar.** Neither 1.665 nor "a running N of 7" is the bar of record.
> `docs/RESEARCH_STATE.md` on `origin/main` (26ed351) reads EVENTS **3**. `results/research/trials/declared_slates.json`
> holds a **standing EVENTS slate at N = 6** (ruled 2026-10-19). So `scripts/research/registry.py::minimum_declared_n("EVENTS",
> pending=1)` returns **6**, and `_check_declared` would refuse a declared N of 4. **The bar of record for a new EVENTS
> trial is therefore at least √(2 ln 6) = 1.893.** N = 7 (1.973) was trial 3's own declaration ("The N = 6 fixed on
> 2026-10-19 covered six named tests, and this is not one of them", RESEARCH_STATE.md, 2026-10-27). By that precedent,
> a further test outside the six named would be declared above 6, which is the team lead's ruling at approval. S2's
> EVENTS P(pass) at 1.893 is 0.31 on the fit and 0.11 on 2023–26. Its verdict (KILL, D2) does not change.

---

## The slate, ranked by information per trial

| rank | id | candidate | universe | verdict | key figures (gross headline; grid beside it) | P(pass) | expected gross gain, all capital |
|---|---|---|---|---|---|---|---|
| **1** | **S5-C4** | **The discount level against family peers (Pontiff), monthly. The z cannot see it by construction** | C4 | **PURSUE (draft prereg)** | Book gross SR **+1.12**, 5.77%/yr, turn 5.4; net **+1.06 / +0.96 / +0.80** at 5/15/30bp, no flip. Every era positive (1.02 / 1.53 / 0.66 / 1.75). NC1 NAV leg −0.26bp/pp (t −0.32). Placebo 20 of 20. Corr with C4's z book +0.10. **Equal-risk blend SR 1.52 vs z alone 1.13.** Second method: FM IC −0.074 (NW t −5.72) | fit bar: ≈0.97 [in-sample]; holdout-sign (C4 precedent): 0.86–0.99; holdout alone at 2.825: **0.04–0.26** | **+0.4 to +1.0%/yr** [model, U] *(corrected 2026-11-02, later: first written +0.8 to +1.5 before the shared 1.90 cap was measured; under it the blend's held gross is 0.67 of uncapped and it sits at the cap on 29.0% of sessions, `prereg_c4_level_design.py`)* |
| 2 | S1-C4 | Year-end tax-loss: losers' discounts recover in January, beyond z | C4 | **WATCH** (mechanism PRESENT, magnitude and seasons fail) | Discount leg b_L +242bp/rank (t **3.54**, z in); NC1 NAV −58 (t −0.51), pass; NC2 Dec − other months t **4.43**, pass. But the tradable price TR is +191 (t 1.25). Overlay: gross SR 0.39, +64bp/season, net 0.33/0.21/0.02. 2020–22 negative | 0.06 | ≈ +0.3% (≈ +0.18% net@15) |
| 3 | S2-C4 | Distribution cuts re-rate the fund; the z reads that as cheap | C4 (core null) | **KILL as a sleeve (D2)**; mechanism PRESENT on C4's discount leg | Cut discount leg −72bp/42 sessions (t **−3.18**), NC1 NAV +18 (t 0.47). Price TR −57 (t −1.73). Cut-book gross SR 0.33, net 0.20 / −0.06 / −0.45, **flips**. Raise-book 0.05 | CEF 0.08; EVENTS (1.665) 0.40 fit, 0.15 on 2023–26 | ≈ +0.2% gross, ≈ 0 net@15. A flag is worth < 0.01% |
| 4 | S3 | C4 fresh-NAV discount move leads the core (executable closes) | both | **KILL (D1 for the stated mechanism)** | Wrong sign: −40bp per pp (t −2.16), i.e. reversal, not lead. 2020–22 carries it (Y2 t −4.11); the other three eras are null. NC1 NAV −0.8 (t −0.11), NC2 IEF −3.8 (t −0.78) | — | 0 |
| 5 | S5-core | The same level signal on the credit names | WIDE17 | **KILL (fails its own control)** | NC1 fails: the NAV leg is **+1.17bp/pp (t 3.01)**. Premium funds' NAVs outperform: fair value (M4), not convergence. Price TR −0.81 (t −0.93) | — | ≈ 0 |
| 6 | S4 | A fast and a slow z on the same names | both | **KILL (graveyard: `z_window = 63`)** | The z63 part orthogonal to z252 carries information (WIDE17 −10.5bp/z, t −8.40; NAV control flat). That is exactly why 63 scored gross 1.75 and **net −0.298** [S]: it is a re-parameterisation paid for in turnover, not a new source | — | negative net [S] |
| 7 | S6 | Tenders, rights, 13Ds and mergers on the book's own names | 87 | **KILL (D7)** | 2005–22: deployed 13: **0 NAV tenders**, 2 13Ds, 5 proxy contests. C4-74: 7 tenders, 12 13Ds. 2023–26 (count only): C4 10 tenders. Rights offerings are undated in the census | — | < 0.01% |
| — | M5 / structural | Size the group spread deliberately; pool the 87 into one cross-section | — | **not run here** | M5 is C2 Part C, queued (`results/cef/W10_PARTB_2026-10-12.md`). Pooling is a variant comparison, which is a trial, and W10-B says between pays less than within. The structural edge this set-up has is S5-C4 itself: it needs C4's breadth, and it fails on the 17 credit names | — | — |

**The one to pre-register first: S5-C4.** It is the only candidate with a positive net at 30bp, a passing
negative control, a passing placebo, a second method that agrees, and near-zero correlation with what the
account already trades. The mechanism is published, so the fit window is already post-publication. It
closes itself cheaply: Stage 0's survivorship re-run on CRSP (dead funds included) can kill it before any
2023+ return is read.

---

## S1 — year-end tax-loss selling (`alpha_taxloss.py`)

**Mechanism and loser.** Taxable retail holders sell their year-to-date losers in December to harvest the loss
(Starks, Yong & Zheng 2006, in muni CEFs [S]). They sell the SHARE, not the holdings, so price falls against NAV
and recovers in January. The seller accepts the concession because the tax value exceeds it, and the tax code
repeats every year.

**Graveyard.** CORE-b (CLOSED, 2026-10-12) found the deployed 13's Dec–Jan concentration inside the z's own
slope. The loser gradient also held in Feb–Nov, and 9 seasons is D7. This screen adds three things: the loser
score as its own regressor beside z, the discount/NAV split, and 17 seasons per universe.

**Design.** Decide at the penultimate December session, fill at the last December close, earn t+2..t+21. The
loser score is the trailing-252-session total-return rank, demeaned within group. There is one cross-section
per season, and t is over seasons.

| universe | leg | b_L, no z (t) | b_L, z in (t) | Dec − other months (t) |
|---|---|---|---|---|
| WIDE17 | discount | +282.5 (2.11) | +28.2 (0.25) | +94.6 (0.79) |
| WIDE17 | price TR | +298.4 (1.68) | −10.8 (−0.07) | +60.8 (0.34) |
| C4 | discount | +358.9 (5.49) | **+242.5 (3.54)** | **+308.6 (4.43)** |
| C4 | NC1 NAV | −85.3 (−0.80) | −58.0 (−0.51) | −37.4 (−0.31) |
| C4 | price TR | +281.0 (2.08) | +191.0 (1.25) | +270.3 (1.62) |

In C4 the discount leg is positive in 15 of 17 seasons. The harness P&L of the overlay alone (C4, unit gross
for 20 sessions a year) is gross SR 0.39, +0.60%/yr, turn 1.89. Net SR is +0.33 / +0.21 / +0.02 at 5/15/30bp.
By era it is +0.71, +0.46, +0.56 and −0.90 (2020–22). On WIDE17 it is +0.06 gross.

**Reading.** On the credit core the z already takes it, as CORE-b found. In C4 the signature is clean: the
discount leg, not NAV, carries it, and December differs from the other eleven month-ends. **But the NAV leg's
noise sits between the discount effect and the P&L**, the effect is small per year, and one season a year
cannot reach 2.825 (P 0.06). **WATCH.** A future C4 pre-registration should report December as a declared
stratum.

## S2 — distribution cuts and raises (`alpha_distchange.py`)

**Mechanism (M7).** Yield-screening retail holders re-rate a fund when its regular distribution changes. The
252-session z reads a cut fund as cheap. The ex-date is used as the event date because declaration dates are not
in the panel (EXDRIFT Stage 0). That is late information, which makes the test conservative.

**Graveyard.** "Distribution data" failed twice as a filter and inside the Kalman, and M7 says "do not rebuild".
Nothing is built here. Control events are the same funds' unchanged ex-dates, so the generic post-ex drift (r6)
cancels.

**Result.** WIDE17 (171 cuts, 154 raises, 2,682 controls): no discount-leg coefficient reaches |t| 2. The
cut×z interaction is +23.9 (t 1.85): the z is weaker after cuts but not wrong-way. C4 (347 cuts in 57 funds):

- the discount leg keeps widening after a cut, **−72.3bp over 42 sessions (t −3.18)**;
- NC1 NAV is +17.9 (t 0.47), a pass;
- the price TR is −57.0 (t −1.73).

The family-hedged cut-short book has gross SR 0.33 and turn 14.2. Its net SR is 0.20 / −0.06 / −0.45, so it
**flips by 15bp**. The raise-book's gross SR is 0.05.

**Verdict: KILL as a sleeve (D2).** The mechanism is present on C4's discount leg. As a subtract-only flag it is
worth under 0.01%/yr: 19 cuts a year × about 0.35% held weight × 57bp. The modern-era cost caveat (1.73bp a
trade [S]) would put it at net 0.20, but that is still inventory, not a source.

## S3 — cross-universe lead-lag (`alpha_leadlag.py`)

**Mechanism.** A shared retail-sentiment factor shows up first in the fresh-NAV equity CEFs and later in credit
CEFs. **Graveyard.** `leadlag` died on (H+L)/2 prices. Here only executable closes are used, with shift(2), a
non-overlapping 2-session grid, and NW t. The book-relevant target is Y2, the core's taxable-minus-muni spread
(M5).

| target t+2..t+3 | b on C4 fresh ΔDisc, bp/pp | NW t |
|---|---|---|
| Y1 core EW price TR | −40.19 | −2.16 |
| Y2 taxable − muni | −35.49 | −2.01 |
| NC1 core NAV TR | −0.77 | −0.11 |
| NC2 IEF | −3.78 | −0.78 |
| NC3 reverse (core → C4) | +28.02 | +1.22 |

By era, Y2 is −40.7 (t −1.18), +4.3 (0.19), −8.2 (−0.61) and **−63.8 (−4.11) in 2020–22**. The controls pass,
but the sign is reversal, not a lead, and one era carries it. **KILL (D1 for the stated mechanism).** Used as a
timing leg it would also add the beta the book avoids.

## S4 — fast and slow z (`alpha_horizon.py`)

**KILL on the graveyard** (`z_window = 63`; OU / κ; price reversal subsumed). One number, measured to make the
kill concrete: z63's part orthogonal to z252 has a slope of −10.46bp/z (t −8.40) on WIDE17 and −13.01 (t −3.23)
on C4. The NAV control is flat (−0.52, t −1.04). The information is PRESENT, at a 2-day horizon. That is why 63
scored a higher gross, and its net was −0.298 on the opened holdout [S]. A blend is a re-parameterisation that
fails bar 3, and testing it at matched turnover would be a trial on a killed variant.

## S5 — the discount level against peers (`alpha_level.py`, `alpha_level_checks.py`)

**Mechanism and loser.** Pontiff (1995) [U on magnitude, `docs/REFERENCES.md`]: premium funds underperform and
discount funds outperform, over months. The loser is the holder who pays a premium for a brand or a
distribution rate. The arbitrage is a short of the premium fund. The lendable pool cannot grow, borrow is
dearest exactly there, and idiosyncratic risk binds (Pontiff 2006 [S]).

**Why the live z is blind to it.** The z is standardised against the fund's own 252-session history. A fund
10pp rich of its peers for a year has z near 0. The mean cross-sectional rank correlation of level with z is
+0.26.

**Graveyard.** It is in no KILLED table and is not a horizon mix. `docs/SYSTEM.md`'s warning, that the raw
discount is "a permanent long-muni bet", is about ranking across groups, so this screen demeans within group or
family.

**Pooled OLS, z in the regression, date-clustered:**

| universe | leg | h 21: bp/pp (t) | h 63: bp/pp (t) |
|---|---|---|---|
| C4 | price TR | −5.52 (−4.76) | −13.54 (−4.07) |
| C4 | discount | −5.09 (−7.88) | −12.31 (−7.19) |
| C4 | **NC1 NAV** | **−0.26 (−0.32)** | **−1.24 (−0.53)** |
| C4 | NC2 price-only / D/P | −5.63 (−5.05) / +0.21 (1.35) | −14.07 (−4.34) / +0.81 (2.20) |
| WIDE17 | price TR | −0.81 (−0.93) | −3.27 (−1.72) |
| WIDE17 | **NC1 NAV** | **+1.17 (+3.01)** | **+4.08 (+3.19)** |

**C4 book** (monthly, within family, unit gross; `harness.report`, shift(2), total returns):

- gross SR **+1.12**, +5.77%/yr, vol 5.17%, turn 5.4;
- net SR **+1.06 / +0.96 / +0.80** at 5/15/30bp, no flip;
- by era: 2005–09 +1.02, 2010–14 +1.53, 2015–19 +0.66, 2020–22 +1.75;
- on price-only returns (Alpaca paper credits no dividends): +1.19.

**The checks, each named before it was run:**

| check | result | reading |
|---|---|---|
| K1 family | covered-call 0.93, sector 0.62, multi-asset 0.55, preferred 0.48. Fresh-NAV families alone 0.90 | not the stale-mark well |
| K2 concentration | top 5 (IGR, RNP, RQI, NFJ, NML) carry 46%. Without them 0.67. The worst name is short DNP, −10.6% | broad, but leans on 2008–10 REIT-fund recoveries |
| K3 persistence | rank correlation of weights at 12 months 0.59; 75% on the same side | **partly a persistent fund-level bet.** It needs the survivorship test |
| K4 overlap | daily correlation with C4's z book +0.10 (monthly −0.04); equal-risk blend SR 1.52 vs 1.13 | adds to the z rather than repeating it |
| K5 D4 (2011–22 only; SPY starts 2011-06) | SPY Σβ +0.040, HYG Σβ −0.075; alpha +4.25%/yr, NW t 3.98 | passes D4's form on the window it covers |
| K6 borrow | all 74 were easy-to-borrow on the frozen read, **so this check cannot fail**; the top shorts are DNP, GCV, GGN, RFI, BME, ASG | **fees unmeasured** |
| K7 placebo | another fund's level in the same family: mean −0.07, max +0.37; the real book beats 20 of 20 | pass |
| K8 second method | FM rank IC −0.0742 (NW t −5.72), 215 months; by era −0.106 / −0.091 / **−0.027 (t −1.69)** / −0.071 | agrees; 2015–19 is weak |

A data note: 242 C4 name-days have |price TR − NAV TR| > 10%, mostly March 2020, October 2008, and a
2006–07 IGR yfinance dividend inflated on both legs. Dropping them raises the SR to 1.31, and the price-only
book, which no dividend can touch, scores 1.19.

**Verdict: PURSUE.** On the credit core the level is fair value (NC1 fails), which is the M4 warning. In C4's
families the NAV leg is flat and the effect is convergence. **What could still kill it:**

- **survivorship.** The 74 are 2026's survivors, and K3 says the book is partly a fund-level bet. A CRSP re-run
  that includes dead funds is Stage 0;
- borrow on the premium-fund shorts;
- the weak 2015–19 era.

## S6 — corporate events on the book's own names (`alpha_events_census.py`)

**M6 is real, but it is rare on these 87 names.** The deployed 13 had no NAV tender, rights offering or merger
dated in the census in 2005–22. WIDE17 had 2 tenders (NVG and NZF, 2014; both unshortable today). C4 had 7
tenders and 12 13Ds; in 2023–26, counted only, it had 10 tenders. Rights offerings for PFN, PFL and OPP are in
the census but **undated**.

The value of a guard against shorting into a tender: about 2.7 tenders a year × about 1.5% name weight × the
+0.45% post-announcement drift (`NAV_TENDER_RESULT_2026-10-20.md`, t 1.2 [S]) × P(short) ≈ 0.5. That is under
0.01%/yr. **KILL (D7).** The EVENTS lane owns these events on the wider universe.

## Gaps and things this note did not do

- **C4's returns are the yfinance leg, not C4's CRSP primary.** Calibration: the z book scores 1.13 here against
  1.217 committed [S].
- **Survivorship is unmeasured** in every C4 figure, and it matters most for S5 (K3).
- **D4 for S5 covers 2011–22 only**, because the local SPY panel starts on 2011-06-01.
- No variant was compared at matched turnover: that would be a trial. S5's blend figure combines P&L series
  (descriptive); it is not a built book.
- **The EVENTS bar is ambiguous.** The brief gives √(2 ln 4) = 1.665; the ledger's running N for a new EVENTS
  test is 7 (1.973).
- `pm_c4_extract.py` in this folder belongs to a sibling agent and was not read or run.
