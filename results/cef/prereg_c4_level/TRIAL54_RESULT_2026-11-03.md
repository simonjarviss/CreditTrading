# CEF trial 54: result of the fit stages, 2026-11-03

**Trial:** C4's discount level against family peers (`results/cef/PREREG_C4_LEVEL_2026-11-02.md`), approved
2026-11-03, CEF 53 → 54, judged at N = 54, bar √(2 ln 54) = 2.8245. Branch `trial54-run`.

**Verdict as committed: KILL, D4, at K3. Evidence: INCONCLUSIVE.** The alpha t is 2.96 against 3.0, and every
|β| ≤ 0.082, so this is a power miss, not a risk premium in costume. **K3's subject needs a ruling** (§3). The
stop-at-first-KILL rule has been honoured: P3, DG-L4 and the holdout were **not run**, and no 2023+ return was
read.

All figures are [V], from `results/cef/prereg_c4_level/trial54.py` (one subcommand per stage; outputs
`<stage>_output_2026-11-03.txt` and `.json`):
- fit only, ≤ 2022-12-30;
- CRSP primary returns (C4's fit source);
- C4's spec `c4_families.v4.20261102` read at run time: m 1.26, cap 1.90, band 0.048.

> **FINAL (2026-11-03): the trial PASSES its pre-registered remainder, and the holdout (opened once) is
> decisive.**
> - **K3 (D4) FAILED as committed** (the level-only book's post-2007 alpha t 2.96 < 3.0, every |β| ≤ 0.082). It was
>   **overridden post-data by the team lead**. That stays in the record: this is not a pass of K3.
> - **Corrected run** (the trial-script vol-lookback fix, 2ed752f):
>   - DG-L4 907 of 907 both ways;
>   - **P1 t 2.8315** (lag 6, bar 2.8245; lag-fragile: 2.80 at L = 5 and L = 21);
>   - P2 desk DSR 0.9997, K1 t −0.32, K2 20 of 20, P3 1.481 vs 1.310.
> - **Holdout 2023-01-03 → 2026-09-30:** level-only gross SR **+1.636**, blend **+14.56%/yr** against z-only
>   **+10.32%/yr**. **PASS.** Net at 15bp: blend +0.843 against z-only +0.125, so **no D2 label**.
> - **Evidence: INCONCLUSIVE.** The holdout's level-on-z alpha is +10.43%/yr, NW t 2.74. At N = 54 the Šidák-adjusted
>   interval is −2.14 to +22.99%/yr, so it includes zero and straddles the 0.8%/yr meaningful effect.
> - **D-code: none at the holdout; D4 at K3, overridden.** Details are in §7.

**2026-11-03 (later), K3 OVERRIDDEN POST-DATA by the team lead.**
- **K3 (D4) FAILED as committed.** The level-only book's post-2007 alpha is t 2.96 < 3.0, and every |β| ≤ 0.082.
  The failure is significance, not factor exposure.
- **The team lead overrode it post-data,** asked interactively on 2026-11-03 after seeing the KILL: "revive it and
  figure out a way to not kill it". The coordinator had recommended recording the KILL and was overruled.
- **This is NOT a pass of K3 and must never be described as one.**
- **P1 is lag-fragile.** Its t is 2.8271 at the automatic lag 6 on the residual, as committed, and 2.791 at lag 5 on
  the dependent series, against a bar of 2.8245.
- **The trial continues under the pre-registered remainder:** P3, then DG-L4, then the 2023–26 holdout opened once.
  **The holdout's result is decisive.** The override covers K3 only. A failure at P3, DG-L4 or the holdout is a
  KILL.

**2026-11-03 (later still): P3 PASS; DG-L4 HALT, on a defect in the trial script, not in the sleeve.**
- **P3**, read once (`p3_output`): the blend's gross SR 1.481 at 51.2 turns/yr, against the z-only spec book at its
  turnover-matched band 0.0447: 1.310 at 51.2/yr. `sharpe_diff`, reported and not gated: Δ +0.17/yr, d 0.93,
  p 0.353, block 42 (`calibrate_block`). The first P3 run raised before forming any Sharpe, because its turnover
  bracket started at the live band; the corrected bracket is `match_band_width`'s own (4823db0).
- **DG-L4** (`dgl4_output`), against the sleeve at 3b4c963 (c4-level-impl, PR #41), through that tree's own
  fidelity machinery (TOL 1e-12, 907 sessions). The sleeve was run, never edited.
  - (a) key absent against `build_book`: 907 of 907 sessions match, 61,346 of 61,346 cells, largest gap 0.0.
  - (b) key present against the trial's blend: 901 of 907 match. **6 breaks, all from 2005-02-23 to 2005-03-31**,
    largest gap 0.0499 (RNP 2005-03-09). After that every session matches.
  - **The cause is the trial script.** `level_targets` reindexed price returns to the fit index, which starts
    2005-01-03, so the 63-session vol window was truncated for the first 62 sessions. §1.2 and `build_targets` use
    the full history, as the sleeve does. The defect touches about the first 30 sessions with targets. **P1's
    margin is 0.0026 (t 2.8271 against 2.8245), so the correction could move P1 either way.**
  - **Stopped here** (the instruction: any DG-L4 diff stops the trial). No corrected figure has been computed, and
    the holdout is not opened.

## 1. The stages, in order

| stage | rule | result | read |
|---|---|---|---|
| DG-L2 | CRSP against the yfinance leg, \|ΔSR\| ≤ 0.2 | level-only book SR +0.882 (CRSP) vs +0.810 (yf); Δ 0.071 | **CLEAR** |
| DG-L3 | every flag ruled | the team lead signed as proposed, 2026-11-03: KEEP 237, MASK 9 (level leg only); `dgl3_rulings_2026-11-03.csv` | **CLEAR** |
| P1 | level-only on z-only, alpha NW t (automatic lag) ≥ 2.8245 | alpha +5.72%/yr, β +0.191; **t 2.8271** at lag 6 (`nw_auto_lag` on the residual); 4,497 sessions | **PASS, at the bar** (§3) |
| P2 | the deflated-Sharpe bar(s) that gate CEF | blend: desk DSR **0.9997** (SR 1.481, SR0 0.669); the paper bar is refused, not_qualified, by construction; §5 2026-10-28 says the desk bar gates CEF | **PASS** |
| K1 | NC1: NAV-leg slope \|t\| < 2 | NAV leg −0.26bp/pp (t −0.32); discount leg −5.09 (t −7.88); price TR −5.52 (t −4.76) | **PASS** |
| K2 | placebo ≥ 19 of 20 | real +0.882 above **20 of 20** (mean +0.046, max +0.604) | **PASS** |
| K3 | D4 on C4's factor set, both windows: alpha t ≥ 3.0, every \|β\| ≤ 0.10 | level-only: full fit alpha +6.68%/yr, t 3.06, max\|β\| 0.072 (pass); **from 2007-04-12 with HY: alpha +7.14%/yr, t 2.96**, max\|β\| 0.082 (fail) | **KILL (D4)** |
| P3, DG-L4, holdout | — | not run | — |

The books on the fit (gross headline; the grid beside it):

| book | gross SR | ann | vol | turns/yr | net @5 / 15 / 30bp | flips |
|---|---:|---:|---:|---:|---|---|
| z-only (C4's v4 spec book) | 1.269 | 9.09% | 7.17% | 48.4 | +0.931 / +0.256 / −0.757 | yes |
| level-only | 0.882 | 7.45% | 8.45% | 34.5 | +0.678 / +0.269 / −0.343 | yes |
| blend, ½ : ½ | 1.481 | 10.76% | 7.26% | 51.2 | +1.129 / +0.424 / −0.633 | yes |

Registry: CEF-54/blend (judged; ledger commit c14c197), CEF-54/level and CEF-54/z (not judged), all with
`dirty: false`. The series files are gitignored; the ledger lines are committed.

## 2. The verdict and its evidence label

As committed, K3 fires on the level-only book's HY window: t 2.96 < 3.0.

- **The evidence is INCONCLUSIVE, not ABSENT.** The alpha is positive in both windows (t 3.06 and 2.96), and
  every beta is small (≤ 0.082). It is the same shape as E1 ("a power failure, not a risk premium in costume").
- **D-code: D4, as the gate that fired.**

## 3. Two results that depend on the reading, for the team lead

1. **P1's lag input.** The pre-registration says "automatic lag, `w4_artifacts.nw_auto_lag`" and does not name the
   series. The committed code, written before the run in 22e9126, uses the regression residual, the standard
   HAC input for an intercept, which gives lag 6 and t 2.8271 (PASS). On the dependent series the rule gives
   lag 5 and t 2.791 (FAIL). By lag, t is 2.775 / 2.791 / 2.827 / 2.847 / 2.856 at L = 4 / 5 / 6 / 7 / 8. P1 sits
   on the bar under every reading.
2. **K3's subject.** §6.2 K3 does not name the book. The committed code tests the level-only book, the signal under
   test (§6.1's claim), with the blend reported beside it. **On the blend, D4 passes easily:** alpha +10.84%/yr,
   t 6.68, max|β| 0.063 on the full fit; +11.33%/yr, t 6.38, max|β| 0.060 with HY.
   - If the team lead rules that K3 judges the blend, K3 passes and the trial continues to P3, then DG-L4, then
     the holdout.
   - If K3 judges the level book, as committed, the KILL stands.

What the fit says, either way: **the level signal's increment over C4's z sits at the desk's thresholds,
t ≈ 2.8–3.0, and does not clear them by a margin.** The screen's +1.12 standalone Sharpe was a monthly book.
Traded daily through the 4.8% band, the level book turns 34.5 times a year, and its gross Sharpe is 0.88.

## 4. Caveats

- **Gate 0 was cleared post-data.** It is the team lead's judgment (§0.A), not a pre-registered pass.
- **NAV misprints in C4's fit history.** The nine masked name-days fall between 2006-04-19 and 2021-06-28: BME,
  ASG, PFO ×3, JPC, SCD, GAM, BME. C4's z book, and so the trial-52 backtest, was built on the same unmasked NAVs.
  This is a **fit-history caveat for C4's trial 52, not a live defect**: every one is outside the live z's
  252-session window, so nothing live trades on them (team lead's coordinator, 2026-11-03).
- **A test edit was found uncommitted in this worktree.** `test_c4_paper_benchmark.py`'s counter assertion had moved
  53 → 54. It was not written by this runner and was committed as found (b573f5c), so that the registry's
  clean-tree rule could hold.
- **The P2 wording.** §6.2 said "both bars". The standing §5 ruling of 2026-10-28 says the desk bar gates CEF and
  the paper bar can never qualify. The ruling was applied (`stage_p2`), and the wording is flagged for the record.

## 5. The KILL row, for `docs/RESEARCH_STATE.md` (KILLED table), when the team lead confirms K3's subject

> | C4-LEVEL (CEF trial 54) | the discount level against family peers (Pontiff), within C4's five families, as a second signal blended ½ : ½ by risk into C4's z book (`results/cef/PREREG_C4_LEVEL_2026-11-02.md`) | **D4 at K3** (the gate that fired; evidence **INCONCLUSIVE**). The level-only book's HY-window alpha is t 2.96 < 3.0, with every \|β\| ≤ 0.082; the full fit is t 3.06. P1 passed at the bar (t 2.8271 vs 2.8245, automatic lag 6), P2 desk DSR 0.9997, NC1 t −0.32, placebo 20 of 20. Blend D4 alpha t 6.68. The holdout was not opened | `results/cef/prereg_c4_level/TRIAL54_RESULT_2026-11-03.md`; `python3 -B results/cef/prereg_c4_level/trial54.py k3` | 2026-11-03 |

## 6. Reproduce

```bash
python3 -B results/cef/prereg_c4_level/trial54.py dgl2
python3 -B results/cef/prereg_c4_level/trial54.py dgl3        # needs the signed rulings for the fit
python3 -B results/cef/prereg_c4_level/trial54.py p1
python3 -B results/cef/prereg_c4_level/trial54.py p2          # reads the registry's CEF-54/blend
python3 -B results/cef/prereg_c4_level/trial54.py k1
python3 -B results/cef/prereg_c4_level/trial54.py k2          # about 3 minutes
python3 -B results/cef/prereg_c4_level/trial54.py k3
```

**Inputs** (gitignored, copied into this worktree):
- `results/cef/c4/_cache_c4/` from `trial53-amend1`: CRSP families returns, sha256 47f20b47…;
- `results/cef/w4/_cache_w4/ff5_umd_daily.parquet`: French, the 202609 vintage, sha256 c98ca0f1…, identical to the
  earlier vintage over 2005–22.

**Panels:** the families panels, last date 2026-10-09, read to 2022-12-30.


## 7. The corrected run and the holdout (2026-11-03)

### 7.1 The fit stages: corrected beside the first read

The fix (2ed752f) changes one thing: the 63-session vol lookback now reads the full history through t, as §1.2,
`build_targets` and the sleeve do. Every stage was read once more, in order. The first reads are kept in
`*_firstread_2026-11-03.*`.

| stage | first read (trial script bug: truncated vol lookback, 6 sessions 2005-02-23..03-31) | corrected | read |
|---|---|---|---|
| DG-L4 (a) key absent | 907 of 907, gap 0.0 | 907 of 907, gap 0.0 | CLEAR |
| DG-L4 (b) key present | 901 of 907, 6 breaks, max 0.0499 | **907 of 907**, 61,346 cells, gap 5.6e-16 | **CLEAR** |
| P1 alpha NW t (lag 6, residual) | 2.8271 | **2.8315** (L = 5: 2.80; L = 21: 2.80) | PASS, at the bar |
| P2 desk DSR (blend) | 0.9997 (CEF-54/blend, judged) | 0.9997 (CEF-54/blend_corrected, unjudged) | PASS |
| K1 NAV-leg t | −0.32 | −0.32 | PASS |
| K2 placebo | 20 of 20 | 20 of 20 | PASS |
| K3 level-only | full t 3.06; **HY t 2.96** | full t 3.06; **HY t 2.96** | **KILL (D4), overridden post-data** |
| P3 blend vs matched z-only | 1.481 vs 1.310 (band 0.0447) | 1.481 vs 1.310 (band 0.0447), sharpe_diff p 0.354 | PASS |

**The registry.** The judged ledger line is still the first read's CEF-54/blend, because a judged line is never
replaced or re-flagged. The corrected series are stored as CEF-54/blend_corrected and CEF-54/level_corrected, both
unjudged. P2's corrected DSR uses the registry's own `desk_dsr` on the stored corrected bytes.

### 7.2 The holdout, opened once

The holdout ran 2023-01-03 → 2026-09-30 at commit 4badc45; its marker is `holdout_opened_2026-11-03.txt`. Returns
are C4's holdout construction:
- CRSP `ret` to 2024-12-31, identity-checked on the fit and on the 2023–24 leg;
- the yfinance formula from 2025, on amendment 4's ruled actions with C4's bar and split rulings;
- IGR's ruled fill, applied: 2026-09-08 −0.4454%, 2026-09-09 −3.5048%.

Each book is the declared rule run continuously. Its rows through 2022-12-30 were asserted equal to the fit's, and
its fit P&L reproduces P1's.

| book | gross SR | ann | vol | turns/yr | net @5 / 15 / 30bp | flips | 2023–24 SR (ann) | 2025–26 SR (ann) |
|---|---:|---:|---:|---:|---|---|---|---|
| z-only (C4's v4 spec book) | 1.497 | 10.32% | 6.89% | 63.1 | +1.040 / +0.125 / −1.247 | yes | +2.21 (+15.43%) | +0.66 (+4.45%) |
| level-only | **1.636** | 12.18% | 7.44% | 36.0 | +1.394 / +0.911 / +0.186 | no | +1.37 (+10.57%) | +1.97 (+14.03%) |
| **blend, ½ : ½** | **2.065** | **14.56%** | 7.05% | 57.4 | +1.658 / **+0.843** / −0.378 | yes | +2.34 (+16.80%) | +1.74 (+11.99%) |

- **The rule** (§6.2 step 6): the level gross SR is +1.636 > 0, and the blend's +14.56% is above z-only's +10.32%.
  **PASS.**
- **Net at 15bp:** the blend's +0.843 is at least z-only's +0.125, so there is **no D2**. The blend flips sign
  only at 30bp.
- **Evidence** (`read_result`, report): the level-on-z alpha in the holdout is +10.43%/yr, SE 3.80, NW t 2.74 at
  lag 7. At N = 54 (α_adj 0.00095) the interval is −2.14 to +22.99%/yr, **INCONCLUSIVE**, and it **straddles** the
  0.8%/yr meaningful effect declared before opening.
- **Seen before:** C4's z-only book's 2023–26 returns had been opened for trial 52 (declared in §4). This signal's
  2023+ is new.

### 7.3 Suggested ACTIVE row for `docs/RESEARCH_STATE.md` (the coordinator writes the ledger)

> | **C4-LEVEL** (CEF trial 54) | the discount level against family peers, blended ½ : ½ by risk into C4's z book (`results/cef/PREREG_C4_LEVEL_2026-11-02.md`) | **PASS on the pre-registered remainder; holdout decisive.** Holdout 2023-01-03 → 2026-09-30: level-only gross SR 1.636; blend 14.56%/yr against z-only 10.32%; net@15 0.843 against 0.125 (no D2). **K3 (D4) failed as committed** (HY-window alpha t 2.96 < 3.0, betas ≤ 0.082) and was **overridden post-data by the team lead** (2026-11-03), so it is not a pass. P1 t 2.8315 at the bar, lag-fragile. Evidence INCONCLUSIVE at N 54 (holdout alpha t 2.74). Gate 0 was cleared post-data. Paper only, as C4 | the sleeve key `level_signal` (PR #41, 3b4c963; DG-L4 907 of 907) and its activation in C4's spec; borrow on the premium-fund shorts measured before any real-money view |
