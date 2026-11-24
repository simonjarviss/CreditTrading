# R1 — Does within-group IC change with each group's own macro state? (2026-10-26)

**Zero-trial screen, report only.** Requested by the team lead (PM) on 2026-10-26.
No trial is spent, no counter moves (CEF stays where `docs/RESEARCH_STATE.md`
says), no spec, harness default or live-path file is touched.

**This is a zero-trial PREVIEW of C2 Part D** (`results/cef/RESEARCH_PLAN_2026-10-09.md`
§3 row 7; W10 Part B §9–10). **Any later C2 Part D trial must declare that its
authors have seen this result.**

**Graveyard context** (`docs/RESEARCH_STATE.md`, `.claude/skills/graveyard/SKILL.md`):
"regime-switching" is on the do-not-build list ("the dispersion-quintile table *is*
the regime study, and vol targeting already exploits it continuously"), and
"sizing up on dislocation" was best in calm markets and produced −12.9% at 35.8%
vol in 2008 [S]. A per-group macro filter is a cousin of both; this screen asks only
whether the *within-group* IC differs by state, and builds no filter, no P&L and no
policy.

## The question

Does the deployed CEF discount signal's WITHIN-GROUP predictive power change with
macro state, in a way a per-group macro filter ("which funds to trade when") could
exploit? W10 Part B found within-group selection carries 89% of gross; W4 found
the deployed IC concentrated in the top-2 realised-vol quintiles and in Dec–Jan.

---

## Declared design (written 2026-10-26 BEFORE any result was computed)

### Data, names, window

- **Fit window only**: every return, IC and statistic uses dates ≤ 2022-12-30;
  every frame that reaches a statistic is checked by W4's `_assert_fit` (raises on
  any 2023+ index). Observables are truncated to ≤ 2022-12-30 on load as well.
- **Signal**: the frozen-spec z, from `build_panel(end=FIT_END)` in
  `scripts/cef/band_frontier.py` (moments `shift(1)`, clip ±4). Imported, not copied.
- **Forward return**: W4's `fwd(r_tr, 2, 3)` — total return close t+1 → close t+3
  (what a book decided at t earns under shift(2)), on W4's non-overlapping grid
  (every second session). **Phase 0 is the headline**; phase 1 (the other half of
  the grid) is reported beside it as a stability check of the same specification.
- **Universes, reported separately:**
  - **DEP13** = W4's deployed set `M_dep` on the 13 spec names (`scripts/cef/spec.py`):
    z present, 63d ADV through t−1 ≥ `min_adv_usd`, ≥ `min_names` such names.
  - **WIDE17** = the v6 17-name research set W4 reconciles to (`UNIVERSE + NAD NEA
    NVG NZF`): names with a z on dates with ≥ `min_names` of them (W10's wide
    convention), no ADV filter. Context, not the deployed signal.
  - **C4 families universe**: allowed but NOT used — it has no credit or loan
    families (`equity_*`, `multi_asset`, `preferred`), so no declared C2 observable
    applies to it.
  - **Sealed name holdout**: the other 27 names in `data/cef/cef_universe.csv`.
    Counted, excluded, no return computed on any of them.
- **Groups**: the static `grp` column of `data/cef/cef_universe.csv` (W10's
  definition). multi = BIT DSL PCN PDI PDO PFN PHK PTY; hy = AWF HYT; muni = MHD MQY
  (+ NAD NEA NVG NZF in WIDE17); loan = JFR.

### Within-group IC (W10's within-group construction, W4's IC machinery)

For group g on grid date t: IC_{g,t} = Spearman, across g's names in the universe's
set on t, of z_t against the forward return F_t (`ic_series` from W4 restricted to
g's columns). Spearman is invariant to demeaning inside the group, so this is
exactly W10's within part against the within-group forward return, one group at a
time. **Minimum 2 names per group-date** (so a pair contributes IC = ±1, its sign
agreement, as W10's `pair_sign`).

Testable cells (decided from the group sizes, before any IC is computed):
DEP13 multi, DEP13 hy, WIDE17 multi, WIDE17 hy, WIDE17 muni — **5 primary tests**.
DEP13 muni is untestable (W10 §1: MHD and MQY are never both eligible). Loan is a
singleton (JFR) in every allowed name set: **no within-group loan statistic exists,
so the loan observable (SOFR/LIBOR) is INFEASIBLE here**.

### Each group's own observable X_g (primary)

| group | X_g (primary) | series, source |
|---|---|---|
| hy | HY OAS | `bamlh0a0hym2`, `data/spreads_daily.parquet` (ICE BofA via crsp-mirror/FRED) |
| multi | HY OAS | same (the plan pairs "HY OAS and CCC−BB" with HY/multi funds) |
| muni | SIFMA Municipal Swap Index (muni leverage-cost proxy), weekly | `sifma` rows of the repo fetcher's cache `results/cef/w10/_cache_w10/group_observables.parquet` (worktree `research-core-signal`, fetched 2026-10-12 18:34 UTC by `scripts/data/fetch_group_observables.py` from sifma.org). Read-only; the fit-window rows are copied to `raw/sifma_le2022.csv` with their source column. sifma.org is not on this task's fetch allowlist, so nothing was re-fetched |
| loan | SOFR / DFF | not tested (singleton group) |

**Robustness variant (the only one), declared now:** each group's *second* declared
observable where one exists — hy → CCC−BB effective-yield spread
(`bamlh0a3hycey − bamlh0a1hybbey`, `data/spreads_daily.parquet`; a proxy for the
CCC−BB OAS, as W10 §9 labels it); multi → "PIMCO repo cost" = OFR tri-party repo
rate on corporate-debt collateral (`repo_tri_corp`, same cache, from 2014-08-22
only, so its states start ~2015-08); muni → none (SIFMA is its only one).

### The state (declared)

- **Alignment**: X'_t = the latest observation of X dated ≤ the previous session
  t−1 (as-of join onto the CEF session calendar, then `shift(1)`). The source date
  of every X'_t is asserted < t. Staleness cap: a daily series older than 7 calendar
  days at t−1, or SIFMA older than 10, gives NO state (dropped and counted, never
  filled).
- **Tercile**: the percentile rank of X'_t among {X'_u : 2005-01-03 ≤ u ≤ t}
  (`expanding().rank(pct=True)`, ties averaged). Every element uses data dated
  ≤ t−1. Bottom p ≤ 1/3, middle 1/3 < p ≤ 2/3, top p > 2/3.
- **Window start 2005-01-03** (the harness's `SAMPLE_START`) for every observable,
  so all states share the CEF sample's calendar (rationale, fixed in advance: a
  1989–2004 SIFMA history of 1–7% would pin every post-2009 date to the bottom
  tercile). **Minimum history 252 sessions** of non-missing X' before a state exists.

### The statistic

For each (universe, group): **Δ = mean IC(top tercile) − mean IC(bottom tercile)**,
on phase-0 grid dates where both IC_{g,t} and the state exist. **t = Welch** (unequal
variances). Second method beside it: OLS of IC on [1, 1(top)] over top ∪ bottom
dates with a Newey–West (5 lags, W4's `NW_LAGS`) t. The per-tercile mean ICs, their
n and t are shown.

### Controls (declared)

1. **Mismatched observable** (the C2 plan's control): the muni observable (SIFMA)
   run on hy and multi; the HY observable (HY OAS) run on muni. Same state rule,
   same statistic.
2. **Block-shuffled state labels**: on each (universe, group) sample in date order,
   cut the own-state label vector into consecutive blocks of **63 grid dates (≈126
   sessions, ≈6 months; the last block may be shorter)**, permute the blocks,
   reassign; **20 draws**. Draw k uses `numpy.random.default_rng([20261026, k])`
   for every cell (the same random stream per draw; the permutation length is the
   cell's own block count). Permuting inside the cell's own sample keeps its exact
   tercile counts. Report how many of the 20 draws the real |Δ| exceeds.
   (Clarified 2026-10-26 before the first run: cells differ in length, so one
   literal permutation cannot serve all of them.)
3. **Generic volatility state** — **joint regression declared** (not strata). The
   vol observable is W4's: realised vol of the equal-weight 13-name total-return
   index over 63 sessions (min 40), but **through t−1** (`shift(1)`), terciled by
   the same expanding rule (start 2005-01-03, min 252). For each (universe, group):
   OLS of IC_{g,t} on [1, X_top, X_bot, V_top, V_bot] (middle terciles omitted),
   HC1 standard errors (NW-5 beside). The statistic is the own-observable
   coefficient difference (X_top − X_bot) and its t; the vol coefficient difference
   (V_top − V_bot) and its t are reported, and the 3×3 X×V cell table (n, mean IC)
   is printed so the overlap of the two states is visible.

### Verdict rule (declared)

A (universe, group) is **PROMISING** only if ALL of:

- (a) own Δ: |Welch t| ≥ **2.58** (two-sided 5% after Bonferroni over the 5 primary
  tests);
- (b) control 1: the mismatched observable on the same group has |t| < 2.0, and
  |Δ_mismatch| < |Δ_own|;
- (c) control 2: the real |Δ| exceeds **all 20** shuffled |Δ| (p < 1/21);
- (d) control 3: in the joint regression the own-observable (top − bottom)
  coefficient keeps the sign of Δ with |t| ≥ 2.0;
- (e) no contradiction: phase 1, the other universe (where the group is tested in
  both), and the robustness variant (where it exists) show no opposite-sign result
  with |t| ≥ 2.0.

The screen's verdict is PROMISING if any cell is. Otherwise:

- **ARTIFACT** if a cell passes (a) but fails (d) while the vol coefficient
  difference has |t| ≥ 2.0 (the split is the vol state);
- **NOTHING** in every other case, including when the mismatched control or the
  shuffle scores as well as the own observable;
- **INFEASIBLE** applies cell by cell where no statistic exists (loan; DEP13 muni);
  the screen-level verdict is INFEASIBLE only if no primary cell can be computed.

Eras (2005–09, 2010–14, 2015–19, 2020–22, by signal date) are reported for the own
Δ, descriptively; pre-2013 exists only on WIDE17 and is thin.

**Gross only, no costs, no P&L.** The screen measures IC, so there is no turnover to
report; a per-group filter would be a new policy scored at matched turnover, which is
a counted trial (W10 Part B's ruling on item 2).

---

## Results (final run 2026-10-26 22:40 UTC; every figure [V] unless labelled)

**Reproduce:**

```bash
cd /private/tmp/claude-501/-Users-simonjarvis-Downloads-2027-Projects-Quant---PM2027-2027/767b4ac8-7cb7-4bf6-953a-b785b037a5b4/scratchpad/tree && python3 -B ../r1_macro_state/r1_macro_state.py   # ~3s; `--prep` once first if raw/ is empty
```

The full output is `r1_output.txt` and the machine-readable results are
`r1_results.json`, both beside this note.

**Panels used** (read-only; every return truncated to ≤ 2022-12-30 before use):

| panel | last date in the file | used through |
|---|---|---|
| `data/cef/cef_prices.parquet` | 2026-10-15 | 2022-12-30 |
| `data/cef/cef_nav.parquet` | 2026-10-14 | 2022-12-30 |
| `data/cef/cef_distributions.parquet` | 2026-09-10 | 2022-12-30 |
| `data/spreads_daily.parquet` (HY OAS, BB/CCC EY) | 2026-07-16 | 2022-12-30 |
| SIFMA (`raw/sifma_le2022.csv`, from the 2026-10-12 fetcher cache) | 2022-12-28 as copied | 2022-12-28 |
| OFR tri-party corp repo (`raw/repo_tri_corp_le2022.csv`) | 2022-12-30 as copied | from 2014-08-22 |

**Integrity checks (all passed):**

- **The 17-name build matches W4 on the 13 names.** z and total return are
  identical (max \|diff\| 0) with the same availability pattern, and the 17-name
  calendar adds 0 dates.
- **The sealed names were not touched.** 27 names in `cef_universe.csv` were
  excluded, and no return was computed on any of them.
- **HY OAS agrees across two paths.** `spreads_daily` (crsp-mirror/FRED) against the
  fetcher's R2 copy: 6,787 dates, max \|diff\| 0. Both come from ICE, so this checks
  the plumbing, not the vendor.
- **The states do not look ahead.** Every state's source date is before its own date
  (asserted). Re-deriving the states from observations truncated at 2015-06-30 moved
  nothing before the cut (asserted).
- **Regression check against W10 item 6:** DEP13 multi within-group IC (≥ 4 names)
  −0.0659 (t −2.78, n 522), against W10's −0.066 (t −2.78) [S]. The DEP13 hy pair:
  the richer name underperformed on 0.520 of 271 dates, against W10's 0.520 of 271.
  Both reproduce exactly.

**States** (first state 2005-12-30; vol 2006-03-01; repo 2015-08-25):

- **Tercile shares, bottom / middle / top:** HY OAS 34 / 42 / 24%; SIFMA 58 / 16 / 26%;
  vol 27 / 39 / 34%.
- **How often two states agree** (share of sessions in the same tercile): HY OAS
  and vol 0.595; SIFMA and vol 0.251.
- **SIFMA is a rate-cycle label.** It sits in the bottom tercile for all of
  2009–2015 and 2020–21.
- **Repo is also a rate-cycle label.** It sits in the top tercile for all of
  2016–2019.

### Unconditional within-group IC (phase 0; min 2 names per group-date)

| universe | multi | hy (pair) | muni | loan |
|---|---|---|---|---|
| DEP13 | −0.066 (t −2.78, n 522) | −0.041 (t −0.67, n 271) | no date (never two eligible) | singleton |
| WIDE17 | −0.067 (t −6.04, n 2,263) | −0.090 (t −4.27, n 2,256) | **−0.104 (t −10.39, n 2,262)** | singleton |

### Main table: the own-observable split (phase 0 unless stated)

| cell (own X) | n | IC bottom (n) | IC middle (n) | IC top (n) | **Δ top − bottom** | t Welch | t NW-5 | Δ phase 1 (t) |
|---|---:|---|---|---|---:|---:|---:|---|
| DEP13 multi (HY OAS) | 522 | −0.033 (305) | −0.138 (159) | −0.042 (58) | **−0.010** | −0.14 | −0.15 | −0.111 (−1.50) |
| DEP13 hy (HY OAS) | 271 | −0.041 (121) | −0.080 (100) | +0.040 (50) | **+0.081** | +0.48 | +0.54 | +0.076 (+0.45) |
| WIDE17 multi (HY OAS) | 2,137 | −0.035 (724) | −0.077 (906) | −0.069 (507) | **−0.034** | −1.09 | −1.21 | −0.034 (−1.08) |
| WIDE17 hy (HY OAS) | 2,131 | −0.064 (722) | −0.094 (905) | −0.163 (504) | **−0.099** | −1.72 | −1.88 | −0.033 (−0.56) |
| WIDE17 muni (SIFMA) | 2,136 | −0.123 (1,243) | −0.091 (350) | −0.077 (543) | **+0.047** | +1.90 | +1.81 | +0.026 (+1.04) |

### Controls (phase 0)

| cell | (1) mismatched X: Δ (t) | (2) shuffle: real \|Δ\| beats k of 20 (draw \|Δ\| mean / max) | (3) joint: own top−bot (t HC1) | (3) joint: vol top−bot (t HC1) | vol alone: Δ (t) | robustness variant: Δ (t), p0 / p1 |
|---|---|---|---|---|---|---|
| DEP13 multi | SIFMA −0.050 (−0.77) | 1 (0.058 / 0.149) | −0.052 (−0.55) | +0.052 (+0.62) | −0.032 (−0.53) | repo +0.007 (+0.11) / −0.029 (−0.47) |
| DEP13 hy | SIFMA +0.127 (+0.89) | 13 (0.098 / 0.321) | −0.142 (−0.51) | +0.254 (+0.99) | +0.118 (+0.79) | CCC−BB −0.208 (−1.24) / −0.165 (−0.96) |
| WIDE17 multi | SIFMA +0.026 (+0.93) | 15 (0.022 / 0.059) | −0.006 (−0.15) | −0.056 (−1.60) | **−0.060 (−2.09)** | repo −0.023 (−0.79) / −0.003 (−0.09) |
| WIDE17 hy | SIFMA +0.047 (+0.91) | **20** (0.035 / 0.077) | **−0.200 (−2.70)** | +0.137 (+1.95) | +0.023 (+0.41) | CCC−BB −0.116 (−2.16) / +0.040 (+0.74) |
| WIDE17 muni | HY OAS −0.033 (−1.21) | 16 (0.026 / 0.060) | +0.028 (+1.09) | −0.055 (−2.03) | **−0.060 (−2.24)** | none declared |

**Post-hoc, NOT declared and NOT in the verdict:** the joint regression on phase 1,
added after the first run because of the WIDE17 hy row. It gives WIDE17 hy own
−0.126 (t −1.69) and vol +0.124 (t +1.77). Every other cell is |t| ≤ 1.47.

**The vol split is not stable across grid halves either.** Univariate vol Δ on
phase 1:

| cell | vol Δ, phase 1 (t) | phase 0, for comparison |
|---|---|---|
| WIDE17 multi | −0.012 (t −0.43) | −0.060 (t −2.09) |
| WIDE17 muni | −0.041 (t −1.56) | −0.060 (t −2.24) |

**Eras** (own Δ, phase 0, t in brackets):

| cell | 2005–09 | 2010–14 | 2015–19 | 2020–22 |
|---|---|---|---|---|
| DEP13 multi | — | no top-tercile date | +0.024 (+0.16) | −0.028 (−0.35) |
| DEP13 hy | — | no top-tercile date | −0.176 (−0.61) | +0.580 (+1.42; only 7 bottom dates) |
| WIDE17 multi | −0.045 (−0.64) | −0.019 (−0.25) | −0.041 (−0.74) | −0.068 (−1.06) |
| WIDE17 hy | −0.099 (−0.98) | −0.227 (−1.61) | −0.164 (−1.28) | **+0.287 (+1.78)** |
| WIDE17 muni | +0.053 (+1.22) | every date bottom tercile | +0.028 (+0.56) | −0.107 (−1.51) |

### The declared rule, applied mechanically

| cell | (a) \|t\| ≥ 2.58 | (b) mismatch | (c) shuffle 20/20 | (d) joint | (e) no contradiction | vol \|t\| ≥ 2 | verdict |
|---|---|---|---|---|---|---|---|
| DEP13 multi | no | no | no | no | yes | no | NOTHING |
| DEP13 hy | no | no | no | no | yes | no | NOTHING |
| WIDE17 multi | no | yes | no | no | yes | no | NOTHING |
| WIDE17 hy | **no** (t −1.72) | yes | yes | yes | yes | no | NOTHING |
| WIDE17 muni | no | yes | no | no | yes | yes | NOTHING (not ARTIFACT: (a) fails, so vol has no split to explain) |

**The Bonferroni bar decided nothing.** No own-observable split reaches |t| 2.0,
let alone 2.58.

---

## Verdict: **NOTHING**

**No group's own macro observable separates the deployed signal's within-group IC.**

- **The own splits are small.** Across the five testable cells, the largest own
  split is |t| 1.90.
- **The muni split points the wrong way for a filter.** WIDE17 muni with SIFMA has
  IC *weaker* when the leverage cost is high, +0.047.
- **The mismatched observables do as well.** Their |t| ≤ 1.21, which is the same
  order as the own splits.

**The deployed set shows nothing at all** (DEP13 multi Δ −0.010, t −0.14).

**The only thread is the WIDE17 hy pair (AWF/HYT) with HY OAS, and it fails the
declared rule.**

- **For it:**
  - IC is more negative in the top HY OAS tercile (Δ −0.099).
  - It beats all 20 block shuffles.
  - Holding the vol state fixed strengthens it (−0.200, t −2.70).
- **Against it:**
  - The univariate t is only −1.72.
  - On phase 1 it is −0.033 (t −0.56).
  - It reverses in 2020–22 (+0.287).
  - On the deployed set it has the opposite sign (+0.081).
  - The pair's IC is ±1 per date.
  - The deployed hy pair has no within-group edge to filter (W10: 52% hit rate).

**The generic vol control scores better than every group observable**, and even
it is fragile:

- **Phase 0:** within-group IC is more negative in high-vol terciles for WIDE17
  multi (t −2.09) and muni (t −2.24). That is W4's finding, now seen inside groups.
- **Phase 1:** it falls to t −0.43 and −1.56.

That is the graveyard's "regime-switching" territory, which vol targeting already
exploits continuously, so it is not a filter to build.

**Muni within-group selection works in every SIFMA state:** IC −0.077 to −0.123,
every t ≤ −3.7. There is nothing to switch off.

## What this means for C2 Part D

- **This is a zero-trial preview. A later C2 Part D trial must declare that it has
  seen this note.**
- **A per-group macro filter on within-group selection has no fit-period support.**
  A trial of one would be fitting noise.
- **This screen does not test the original Part D framing.** That framing is a
  group-level fair-value conditioner, which acts on the *between* bet. W10 §10
  ranked Part D after Part C and conditional on Part C's between budget, and this
  result adds no reason to move it forward.
- **Anyone who still wants a Part D trial needs four things:**
  - a mechanism for the hy-pair HY-OAS effect, tested against the sealed 2023+ time
    holdout at turnover-matched `evaluate()` P&L, knowing it is a two-name, ±1-IC
    statistic;
  - for munis, NAD/NEA/NVG/NZF, which are not in v7 (Alpaca would not short them).
    MHD and MQY alone give no within-muni statistic on the deployed set;
  - for loans, at least two loan funds. The six in the 27-name sealed set would
    consume it and conflict with E1 (W10 §10) [S];
  - for multi, the PIMCO funds' own repo cost from N-CSR (not fetched: EDGAR) in
    place of the OFR rate proxy, which is a rate-cycle label here.

## Gaps and caveats

- **Loan was not tested** (JFR is a singleton in every allowed name set; C4's
  families universe holds no credit or loan funds).
- **DEP13 muni was not tested** (MHD and MQY are never both eligible).
- **SIFMA was not re-fetched.** sifma.org is not on this task's allowlist. The rows
  are the repo fetcher's 2026-10-12 cache, copied read-only. Whether MHD and MQY
  preferred resets track SIFMA is a filing question [S, W10 §9].
- **CCC−BB is an effective-yield proxy** for the OAS difference [S, W10 §9]. The repo
  rate is the OFR tri-party corporate-collateral proxy, not PIMCO's own cost.
- **The tests overlap.** DEP13 and WIDE17 share names and most post-2013 dates, and
  hy and multi share the HY OAS state. The five cells are not independent tests.
- **One post-hoc line is labelled as such** (phase-1 joint regression) and played
  no part in the verdict.
- **No P&L, no cost and no turnover.** This is an IC screen. A filter would be a
  policy comparison, which is a counted trial.
