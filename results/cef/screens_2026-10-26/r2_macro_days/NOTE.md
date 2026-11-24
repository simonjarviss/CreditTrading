# R2 — Do discount moves on macro-release days revert more? — 2026-10-26

**Reproduce:** `python3 -B results/cef/screens_2026-10-26/r2_macro_days/r2_macro_days.py` from the repo root (it was run 2026-10-26 from a scratch export of `simon`; see `../README.md`).


**Zero-trial screen, report only.** No trial is spent and no counter moves (CEF stays
as `docs/RESEARCH_STATE.md` records it; MACRO is not touched). Nothing on the live
path, the spec or `data/` changes. **This overlaps the MACRO lane** (macro events).
As a zero-trial screen it does not consume that lane's counter. A real version
would be a pre-registered, counted trial.

Asked by the team lead (PM), 2026-10-26.

---

## Part A — declared BEFORE any return, IC or slope was computed (written 2026-10-26)

### A1. The question

Do CEF discount moves on scheduled macro-release days revert more over the next
sessions than discount moves of similar size on ordinary days? The releases are the
FOMC statement, CPI and the BLS Employment Situation (NFP). If they do, the core book
could lean harder into signals formed on macro days, as an event overlay.

Two mechanisms, and the test must tell them apart:

- **(a) Price overreaction.** Retail-held CEF prices overreact to the news relative to
  NAV, and the PRICE comes back. This is tradable.
- **(b) Stale NAV.** Bond marks inside the NAV lag the macro move, so the discount
  "shock" closes because the NAV catches up. This is NOT tradable, because the book
  trades price. It is the graveyard's #1 cause of death (`single-fund-PD`, `leadlag` in
  `docs/RESEARCH_STATE.md`).

**Only the price leg counts as evidence for (a).**

### A2. Event dates and their provenance

**FOMC.** Source: the Federal Reserve's own pages, fetched 2026-10-26 22:36–22:39 UTC
by `fetch_fomc.py` into `raw/fed/` (URLs, times and sha256 in `raw/fed/FETCH_LOG.csv`):
`federalreserve.gov/monetarypolicy/fomchistorical{2005..2020}.htm` and
`fomccalendars.htm` (for 2021–22). `parse_fomc.py` reads them into `fomc_fed.csv`.

- **Scheduled meetings.** 144 in 2005–22: eight a year, one of them cancelled
  (2020-03-17/18). Statement day = the last meeting day. The parser requires each
  Statement href to agree with that day.
- **One href disagrees.** The June 27–28, 2007 Statement link is `20070618a.htm`. The
  page behind it (fetched, `raw/fed_stmt/`) reads "June 28, 2007 FOMC statement", so
  the date used is 2007-06-28.
- **Cross-check against the repo.** Against `data/events.parquet` (FOMC rows from the
  Kuttner, USMPD and Bauer–Swanson event-study spines), all 143 held scheduled
  statements agree [V].
- **Unscheduled actions** are excluded from the event set, and their sessions are
  DROPPED from the sample (neither event nor ordinary). They are the 8 unscheduled
  statements on the Fed pages, plus 6 further "emergency" rows that only the repo panel
  carries (2019-10-04, 2019-10-11, 2020-03-19, 2020-03-23, 2020-03-31, 2020-08-27). An
  action dated on a non-session (2010-05-09, 2020-03-15, both Sundays) drops the next
  session.

**CPI and NFP.** BLS refused the script (HTTP 403). Its body says bot activity "that
doesn't conform to BLS usage policy is prohibited". That policy wants a contact
User-Agent, which the team lead holds (like EDGAR), so no browser string was spoofed.
FRED's keyless `fredgraph.csv` ignores `vintage_date` (tested: PAYEMS vintages
2013-10-21 and 2013-10-22 return identical current data), so it cannot date releases.

**So CPI/NFP dates come from the repo panel `data/events.parquet`** (source
`forexfactory:Ehsanrs2/Forex_Factory_Calendar`, built 2026-07-20 by the archived
`build_events_deploy.py`). They are **[S]**: a secondary source, not re-read against
BLS. Structural checks [V]:

- 192 releases of each in 2007–22, exactly one per calendar month;
- every row timed 08:30;
- NFP falls on a Friday 186 times, a Thursday 5 times and a Tuesday once
  (2013-10-22, the shutdown-delayed September report);
- CPI falls Tuesday–Friday, on day-of-month 10–30.

**The panel has no CPI/NFP before 2007**, so the WIDE sample starts 2007-01-02. A day
in 2005–06 could not be classed as ordinary.

All three releases come before the 16:00 close (CPI and NFP 08:30; FOMC 12:30–14:15),
so close *t* reflects them. A release dated on a non-session (for example NFP on a
Good Friday) is assigned to the next session and counted.

### A3. Universes (never the sealed names)

- **DEPLOYED** — the spec's 13 names (`scripts/cef/spec.py`), with W4's deployed mask:
  a z-score, 63-day ADV through *t−1* ≥ `min_adv_usd`, and ≥ `min_names` such names
  that date. Natural sample 2013-06-21 → 2022-12-30.
- **WIDE17** — the 13 plus NAD, NEA, NVG and NZF (W4's v6 reconciliation set; deployed
  until 2026-09-28, never in the untouched set). No ADV filter; ≥ `min_names` names
  with a z-score. Sample 2007-01-02 → 2022-12-30.
- **Sealed.** The other 27 names in `data/cef/cef_universe.csv` are the sealed name
  holdout. They are counted here and never read.
- C4's families universe is not used.

**Fit window only.** `build_panel(end="2022-12-30")`. Every frame that reaches a
statistic is asserted to end before 2023-01-01. A forward window needing a 2023 return
is NaN and drops out.

### A4. The test: option (ii), a pooled regression (declared)

**Why (ii) and not (i).** The question is about the day's **move**, and two of the
three controls are defined on it. Control 2 matches on the size of Δdiscount.
Control 3 needs a decomposition of each leg's response to the same regressor, and a
linear regression splits exactly (price = NAV + discount, in logs). The deployed z's
IC (option i) mixes the day's move with the accumulated level, and the rank IC cannot
be split into legs additively. The z level enters instead as a control.

**Variables.** Each is cross-sectionally demeaned on each date, over the names in the
set's mask that have every variable. A date needs ≥ `min_names` such names.

- `x_it` = (disc_it − disc_i,t−1) / sd_it, where disc = 100·(P−N)/N and sd_it is the
  harness's rolling-252 sd of the discount through *t−1* (`build_panel`, `shift(1)`).
  **Alignment:** sd uses data ≤ *t−1*; disc_t is known after *t*'s NAV is published,
  exactly as z is. x is the day's move in the book's own z units (the book's weights
  are linear in z).
- `zlag_it` = the harness z at *t−1* (the level before the day's move).
- **Forward legs**, W4 §3c's construction (log total returns, bp), over sessions
  *t+2..t+3* (close *t+1* → close *t+3*, what a book decided at *t* earns under
  shift(2)):
  - `F_P` = Σ log(1 + price TR);
  - `F_N` = Σ log(1 + NAV TR), where NAV TR adds D/N_{t−1} on ex-dates;
  - `F_D` = F_P − F_N (discount leg; exact).
- `R^k_t` — 1 if session *t* is a type-*k* release day (k ∈ FOMC, CPI, NFP);
  `R^any` = any of them.
- `P^k_t` — **placebo** (control 1): 1 if *t* is the same weekday exactly 7 calendar
  days before or after a type-*k* release, *t* is a session, and *t* is not itself a
  release (any type) or a dropped session. `P^any` = any of them.

**Models.** OLS without an intercept (the demeaning absorbs date effects), on every
session of the set's sample.

- **Pooled:** `F_L = b0·x + b_any·x·R^any + p_any·x·P^any + c·zlag + e`
- **By type** (joint): `F_L = b0·x + Σ_k b_k·x·R^k + Σ_k p_k·x·P^k + c·zlag + e`

Each is run for L ∈ {P, N, D}. **b0 < 0 is reversion on ordinary days. b_any < 0 is
EXTRA reversion on release days.** On the price leg that is mechanism (a). A NAV-leg
b_any > 0 is NAV catching up in the direction of the day's price move: mechanism (b).

**Standard errors.**

- **Headline: Driscoll–Kraay.** Per-date score sums, Bartlett kernel, 5 session lags
  (the forward windows of adjacent sessions overlap by one day), times G/(G−1).
- Date-clustered errors (0 lags) are printed beside it.

**Era rows** for the pooled price-leg b_any, re-estimated within each era:

- DEPLOYED: 2013-06→14, 2015–19, 2020–22;
- WIDE17: 2007–09, 2010–14, 2015–19, 2020–22.

### A5. Controls (declared)

1. **Placebo dates** (`P^k`, above). Both dummies sit in one regression, so b_any and
   p_any are each measured against ordinary days. "Beats the placebo" is the t of
   (b_any − p_any) from the joint DK covariance.
2. **Matched size.**
   - `D_t` = the date's cross-sectional mean of |x̃| over the set's mask names with x
     and zlag defined (it does not depend on forward data).
   - `q_t` = the decile of D_t against D_s for all earlier sessions s < t of the same
     set (expanding, **strictly before t**, at least 250 prior sessions; asserted).
   - **Matched model:** replace b0·x with Σ_q b0_q·x·1{q_t = q}. b_any then compares
     release days with ordinary days in the same shock-size decile.
   - It runs on the dates where q_t exists. The unmatched pooled model is re-run on
     that same sample for a like-for-like comparison.
3. **The price-vs-NAV decomposition.** Every model is reported for F_P, F_N and F_D.

### A6. The one robustness variant (declared): Fama–MacBeth by date

For each date, run OLS of F̃_P (and F̃_N) on [x̃, z̃lag] across names (≥ `min_names`)
to get the slope β_t on x̃. Then regress β_t on [1, R^any_t, P^any_t] across dates,
with Newey–West(5) errors. The R^any coefficient is the release-minus-ordinary
difference, with every date weighted equally. It guards against a pooled estimate
driven by a few high-dispersion dates.

### A7. Context (declared; never enters the verdict)

- **The same pooled model on the t+1 window** (close *t* → close *t+1*). This is
  INFEASIBLE: no book decided at *t* can earn it. It shows where a release-day
  overreaction or NAV catch-up goes before the book could trade.
- **Release-day anatomy:**
  - mean D_t and its decile mix on release, placebo and ordinary days;
  - the share of name-days on which the NAV did not change;
  - the split of the day's demeaned discount move into price and NAV.

### A8. Verdict rule (declared)

**The deciding set is DEPLOYED**: the book an overlay would modify. The window is
*t+2..t+3* and the model is the pooled one. WIDE17 is the corroborating set.

**PROMISING** only if ALL of these hold on DEPLOYED:

1. price-leg b_any < 0 with DK t ≤ −2.0;
2. it beats the placebo: price-leg (b_any − p_any) < 0 with DK t ≤ −2.0;
3. it survives size matching: the matched price-leg b_any has DK t ≤ −2.0 and keeps
   ≥ 50% of the unmatched b_any on the same sample;
4. the Fama–MacBeth release-minus-ordinary price slope is negative;
5. WIDE17's price-leg b_any is not of the opposite sign with |t| ≥ 2.

A single release type can make PROMISING in place of the pooled dummy only if its b_k
passes 1–4 at |t| ≥ 2.39 (Bonferroni over three types).

**ARTIFACT** if the extra closure exists and comes through NAV:

- the discount-leg b_any < 0 with DK t ≤ −2.0;
- the price leg fails test 1;
- the NAV-leg b_any > 0 carries ≥ 50% of the discount-leg extra.

**NOTHING** otherwise. That includes a release effect that the placebo matches, one
that size matching removes, and one that appears only on WIDE17.

**Gross only**, as the PM asked: no cost grid. The screen has no P&L, so it has no
turnover line.

---

## Part B — results (computed after Part A was written)

Every figure here is **[V]**: computed by `r2_macro_days.py`, run 2026-10-26 22:47 UTC.
The full printout is `out/r2_output.txt` and the machine-readable copy is
`out/r2_results.json`. CPI/NFP *dates* are [S] (A2). Figures quoted from W4 or
REFERENCES are labelled [S].

**Panels (read-only):**

- `cef_prices` last 2026-10-15; `cef_nav` last 2026-10-14; `cef_distributions` last
  ex-date 2026-09-10. Only rows ≤ 2022-12-30 are used.
- `events.parquet`: CPI to 2025-03-12, NFP to 2025-04-04.
- Fed pages fetched 2026-10-26.

**Checks that passed:**

- sd_t equals the std of the 252 sessions strictly before *t*, on 25 random cells per
  set.
- Every size decile is built from prior sessions only (20 random dates re-derived).
- Synthetic method check (about the code, not the market): DK at 0 lags equals the
  date-clustered sandwich, and on iid data the DK(5)/iid SE ratio is 0.98.
- 27 sealed names were counted and not read.

### B1. Samples

| | DEPLOYED | WIDE17 |
|---|---|---|
| sessions / name-days | 1,038 / 6,849 (2013-06-21 → 2022-12-27) | 4,011 / 59,448 (2007-01-03 → 2022-12-27) |
| release sessions: FOMC / CPI / NFP / any | 33 / 48 / 49 / 124 | 127 / 192 / 191 / 497 |
| placebo sessions (any) | 220 | 845 |
| dropped unscheduled-FOMC sessions | 14 | 14 |
| releases on a non-session, moved to the next session | CPI 2017-04-14 and 2020-04-10; NFP 2007-04-06, 2010-04-02, 2012-04-06, 2015-04-03, 2021-04-02 (Good Fridays) | same |
| release dropped with its session | NFP 2019-10-04 (a repo emergency row) | same |
| sd of demeaned x / zlag / F_P | 0.270 z / 0.861 z / 108.7bp | 0.268 z / 0.907 z / 121.6bp |

### B2. Headline: pooled model, window *t+2..t+3*, bp of 2-day log TR per unit x, DK(5) t

| set | leg | b0, ordinary day | **b_any, release extra** [95% CI] | p_any, placebo extra | b_any − p_any | size-matched b_any (kept) | Fama–MacBeth release extra |
|---|---|---:|---:|---:|---:|---:|---:|
| **DEPLOYED** | **price** | −37.3 (−3.39) | **−6.9 (−0.36)** [−44.5, +30.8] | +19.1 (+0.97) | −26.0 (−1.00) | −8.1 (−0.40), 0.90 | −8.5 (−0.30) |
| DEPLOYED | NAV | +4.6 (+0.95) | −10.7 (−1.12) [−29.5, +8.1] | +15.1 (+1.73) | −25.9 (−1.71) | −12.9 (−1.30) | −5.2 (−0.49) |
| DEPLOYED | discount | −41.9 (−2.97) | +3.9 (+0.17) [−41.6, +49.3] | +4.0 (+0.19) | −0.1 (−0.00) | +4.8 (+0.20) | — |
| WIDE17 | **price** | −33.0 (−6.17) | **−6.6 (−0.49)** [−32.7, +19.5] | −10.0 (−1.16) | +3.5 (+0.23) | −6.8 (−0.51), 1.04 | +9.7 (+0.98) |
| WIDE17 | NAV | +5.0 (+1.80) | −4.9 (−0.73) [−18.2, +8.3] | −7.7 (−1.24) | +2.8 (+0.35) | −4.6 (−0.70) | +0.8 (+0.15) |
| WIDE17 | discount | −37.9 (−6.48) | −1.6 (−0.13) [−25.8, +22.5] | −2.3 (−0.25) | +0.7 (+0.05) | −2.2 (−0.18) | — |

Notes on the table:

- Date-clustered t for the price-leg b_any is −0.32 (DEPLOYED) and −0.48 (WIDE17),
  beside DK's −0.36 and −0.49.
- The size-matched DEPLOYED sample starts 2014-11-26 (788 sessions). On that sample
  the unmatched price b_any is −9.0 (−0.44).
- The zlag control has c = −5.9 (−3.01) on DEPLOYED and −10.9 (−7.76) on WIDE17
  (price leg).

**By type** (joint model, price leg; b_k, with p_k its placebo):

| type | DEPLOYED b_k | p_k | WIDE17 b_k | p_k |
|---|---:|---:|---:|---:|
| FOMC | −34.2 (−0.84) | +25.7 (+0.91) | −27.6 (−0.81) | +4.0 (+0.35) |
| CPI | +7.4 (+0.29) | −15.9 (−0.76) | −34.3 (−1.44) | −10.6 (−0.86) |
| NFP | −11.4 (−0.39) | **+64.4 (+2.93)** | +19.7 (+1.57) | −16.8 (−1.44) |

No release b_k reaches |t| 1.6 on either set, so none comes near the Bonferroni 2.39.
Every |t| ≥ 2 in the by-type tables is a **placebo** term, or a difference driven by
one:

- DEPLOYED NFP placebo: price +64.4 (t 2.93), discount +45.3 (t 2.43);
- DEPLOYED CPI placebo, NAV leg: +16.6 (t 3.13).

That suggests the type-level DK errors are optimistic on ~30–50 event days, or that
the Fridays a week either side of NFP (one is often month-end) have their own
pattern. Neither is pursued here: it would be sweep-and-pick.

**By era** (pooled price-leg b_any, re-estimated in each era):

| set | era | b_any |
|---|---|---:|
| DEPLOYED | 2013-06→14 | +10.1 (+0.26) |
| DEPLOYED | 2015–19 | +2.0 (+0.09) |
| DEPLOYED | 2020–22 | −14.6 (−0.52) |
| WIDE17 | 2007–09 | −42.1 (−0.98) |
| WIDE17 | 2010–14 | −8.9 (−0.81) |
| WIDE17 | 2015–19 | +16.3 (+1.51) |
| WIDE17 | 2020–22 | +18.5 (+0.71) |

The sign changes across eras, and no era is significant. Every era's ordinary-day b0
is negative: DEPLOYED −41 / −11 / −48; WIDE17 −55 / −25 / −27 / −36.

**Context, *t+1* only (INFEASIBLE, never decides).** Price b_any is −8.8 (−0.37) on
DEPLOYED and +13.7 (+1.36) on WIDE17; NAV b_any is −5.8 (−0.85) and +23.2 (+1.00).
Even the day no book can trade shows no release-day extra.

**Context, release-day anatomy:**

| set | days | NAV unchanged | price share of the day's demeaned discount move | mean D_t (cross-sectional mean \|x̃\|) |
|---|---|---:|---:|---:|
| DEPLOYED | release | 12.2% | 0.88 | 0.169 |
| DEPLOYED | placebo | 16.0% | 0.91 | 0.180 |
| DEPLOYED | ordinary | 16.2% | 0.91 | 0.183 |
| WIDE17 | release | 14.2% | 0.74 | 0.180 |
| WIDE17 | placebo | 17.5% | 0.84 | 0.178 |
| WIDE17 | ordinary | 19.1% | 0.85 | 0.180 |

On release days NAVs move MORE often than on other days, and (on WIDE17) more of the
relative discount move is NAV. Release days are not bigger cross-sectional shocks:
D_t is equal or smaller.

### B3. Reading

- **Ordinary-day discount moves do revert, through price**, at the traded horizon.
  b0 on the price leg is −37bp per unit x (t −3.4, DEPLOYED) and −33bp (t −6.2,
  WIDE17); the NAV leg is small and positive (+5, t 1.0 / 1.8). This agrees in kind
  with W4 §3c, where the traded-window closure is 98% price [S].
- **Release days add nothing measurable.** The extra price-leg slope is about −7bp on
  both sets (|t| < 0.5).
  - The placebo is as large or larger: +19 on DEPLOYED, −10 on WIDE17.
  - Size matching changes nothing (kept 0.90 / 1.04).
  - Fama–MacBeth gives −8.5 on DEPLOYED and the opposite sign (+9.7) on WIDE17.
- **Mechanism (a) is not supported.** **Mechanism (b) is not the explanation either**,
  because there is no extra closure to explain:
  - the discount-leg b_any is +3.9 and −1.6, both t ≈ 0;
  - the NAV-leg b_any is negative, the opposite of a catch-up;
  - NAVs are *less* often stale on release days.
- **Power, stated plainly.** The DEPLOYED 95% CI on the price extra, [−44.5, +30.8],
  spans "release days revert twice as hard" and "release days revert only a fifth as
  much". WIDE17's [−32.7, +19.5] rules out an extra reversion much beyond 100% of the
  ordinary slope. Neither rules out an extra of a few tens of percent.

### B4. Verdict — **NOTHING**

By the declared rule (A8), on DEPLOYED:

1. price b_any < 0 with t ≤ −2: **fail** (−6.9, t −0.36);
2. beats the placebo: **fail** (b − p = −26.0, t −1.00);
3. survives size matching: **fail** (−8.1, t −0.40);
4. Fama–MacBeth sign negative: pass (−8.5, t −0.30);
5. WIDE17 not of the opposite sign: pass (−6.6, t −0.49).

No single type passes at |t| 2.39. **ARTIFACT does not apply**: the discount leg shows
no extra closure (+3.9, t +0.17) for the NAV to explain.

### B5. Implementation notes made after Part A (none changes the design)

1. **NFP 2019-10-04** is also a repo-only emergency row. The day_flags assertion stopped
   the first run before any statistic. The release is dropped with the session, as A2
   says dropped sessions are neither event nor ordinary.
2. **NAV-yield check.** A blunt "missed ex-dates" check (28 misses) stopped the second
   run before any statistic. All 28 are PFN, 2005-01 → 2007-05, on days with no PFN
   NAV, where the NAV return is NaN. The check now raises only where a zero yield
   could be booked against a real NAV move; there are none.
3. **`statsmodels` cannot be imported** here (`scipy._lib._util._lazywhere` is missing).
   The third run printed every table up to the Fama–MacBeth step, then failed at that
   import. The declared NW(5) was then computed with the in-house Bartlett HAC
   (`ols_dk` with one observation per date, which is the same estimator). That is the
   only code change made after the headline was visible, and it does not touch the
   headline.

### B6. Overlap and status

**This overlaps the MACRO lane** (macro events). It is a zero-trial screen: no counter
moves, MACRO's included. A real version would be a pre-registered trial counted there,
or wherever the team lead assigns it.

**What a real trial would need**, if the team lead still wanted one (on this evidence
it is not recommended):

- **Primary CPI/NFP dates**: BLS's archive fetched with the team lead's contact
  User-Agent, or ALFRED vintage dates, back to 2005.
- **More power**: the deployed set has only 124 release sessions in 2013–22.
- **A sharper event, declared up front, never swept**: the surprise magnitude.
  `events.parquet` carries consensus/actual for CPI/NFP and Kuttner/USMPD surprises
  for FOMC.
- **Out of scope here: the aggregate version.** All CEFs' discounts reverting after
  macro days is a directional trade the dollar-neutral book cannot earn, and it is
  untested.

### B7. Reproduce

```bash
cd <SCRATCH>/r2_macro_days && python3 -I fetch_fomc.py && python3 -I parse_fomc.py   # dates (raw/ kept; re-fetch optional)
cd <SCRATCH>/tree && python3 -I -B ../r2_macro_days/r2_macro_days.py | tee ../r2_macro_days/out/r2_output.txt   # ~1 min, offline; -B: no bytecode in the tree
```

The June 2007 statement page in `raw/fed_stmt/` was fetched with curl; its URL and time
are in `raw/fed_stmt/FETCH_LOG.txt`.

Housekeeping: the runs behind this note were made without `-B`, so importing the
harness may have written `__pycache__/*.pyc` under `<SCRATCH>/tree/scripts/`. No source
file there was touched. The caches were not deleted, because other screens share the
tree.
