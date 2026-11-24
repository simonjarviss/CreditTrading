# Re-run of the corporate-event figures in SCALING §7 — 2026-10-11

**What this is.** Plan item 0.9 (`results/cef/RESEARCH_PLAN_2026-10-09.md`):
bring the agents' scratch analyses into the repo and re-run them. This note
covers three rows of `results/cef/SCALING_RESEARCH_2026-10-08.md` §7.1:

- row 4, the convertible-issuance event study;
- row 5, the listed mandatory convertibles census;
- row 6 and row 11's BDC figures, the BDC release events and co-held loan marks.

It also covers §7.4's suspected pandas fault.

It reads gates G3, G4 and G5.

**Reproduce** (with `QUANTT_ENV_FILE` set; R2 and Alpaca keys, read-only):

```bash
python3 scripts/events/convert_issuance.py       # row 4, G3
python3 scripts/events/mandatory_census.py       # row 5, G4 (Alpaca GETs)
python3 scripts/events/numexpr_fault.py --agent  # §7.4
```

**Zero trials.** This is a descriptive reproduction. No counter moves and
nothing is pre-registered.

- No return statistic touches 2023-01-01 or later. The scripts assert this.
- No name in `data/cef/cef_universe.csv` is used. Checked: none of the convert
  issuers' tickers, and no BDC or CLO-equity name, is in it. So the 27-name set
  is not consumed.
- **The convert windows (days +2..+5) were already looked at on 2026-10-09.**
  2011–22 is not out of sample for them, as §7.1 says.

**Where the originals came from.** The agents' scratch scripts were deleted with
the session scratchpad. Their code was recovered from the session transcripts
(Bash inputs and outputs) and used as provenance only. Every method below was
rebuilt as a repo script.

**Panels and last dates** (measured 2026-10-11):

| panel | last date | used to |
|---|---|---|
| CRSP `dsf` (R2) | 2024-12-31 | 2022-12-30 |
| TRACE 144A trades, `trace_btds144a_enhanced` (R2) | 2025-12-04 | first trades only, day 0 ≤ 2022-10-31 |
| TRACE master, `camasterfile` (R2) | `stdt` 2026-06-05 | flags only |

Alpaca's asset lists and SIP bars were fetched 2026-10-11 at 15:55–15:58 ET. The
last completed session was 2026-10-09.

## 1. The reproduction table

Status key: **reproduced** (same figure from the repo script); **corrected**
(the figure was wrong or misleading, and the right one is given); **could not
re-run** (why).

| row | figure (SCALING §7) | original (agent, 2026-10-08/09) | re-run 2026-10-11 | status |
|---|---|---|---|---|
| 4 | events, 2011–22 | 755 (from 1,044 new 144A convert CUSIPs, 761 matched, 500 issuers) | 755 (1,044 → 761 → 755; 500 permnos) [V] | reproduced |
| 4 | [−1,0] abnormal return | −4.41% | −4.41% (median −2.95%; t −12.65 plain, −11.41 week-clustered) [V] | reproduced |
| 4 | straight-debt control [−1,0] | −0.64% (n 1,625) | −0.64% (n 1,625; t −4.75) [V] | reproduced |
| 4 | days +2..+5 | +0.54% (t 2.6) | +0.54% (median +0.38%). t is 2.56 plain, 2.37 clustered by date and **2.24 clustered by week**. The calendar-time portfolio gives t 2.58, or 2.45 Newey-West [V] | reproduced. The t was plain; the clustered t is lower but still above 2 |
| 4 | control days +2..+5 | −0.17% | −0.17% (t −1.26) [V] | reproduced |
| 4 | net on the 5/15/30bp grid | +44 / +24 / −6bp | +44 / +24 / −6bp (gross +54bp, one round trip per event) [V] | reproduced; **the sign flips at 30bp** (H3) |
| 4 | one bond can be several events | not addressed | 59 of the 755 events are extra share classes of one issuer on one day: Liberty tracking stocks, dual-class shares. Collapsed to one event per issuer-day: n 696, [−1,0] −4.86%, [+2,+5] +0.54% (t 2.10 week-clustered) [V] | **corrected** (small) |
| 4 | stability across eras | 2011–16 +0.64% (t 1.9), 2017–22 +0.49% (t 1.8), plain t | 2010–14 +1.02% (t 2.44), 2015–19 +0.14% (t 0.55), 2020–22 +0.69% (t 1.28), week-clustered. **Convert minus control**: +1.53% (t 3.43), +0.55% (t 1.84), **+0.17% (t 0.32)** [V] | **new: the edge over the control decays to zero by 2020–22** |
| 5 | mandatories listed at Alpaca | 24 (23 by name rule + NFEGP patched by hand) | 24. The name rule now matches "Mandatorily Convertible", so no symbol is patched [V] | reproduced |
| 5 | clear the volume floor | 12 | 12, on the agent's statistic and window: median daily $ volume, 2026-07-01..10-07, against the spec's `min_adv_usd`; values identical to 2dp [V]. On the sleeve's own ADV rule (63-session mean, shifted 1, min 21 bars, to 2026-10-09): **19** [V] | reproduced; the house definition is looser |
| 5 | liquid and shortable | 7 (flags of 2026-10-08) | **6** on the agent's statistic, 8 on the sleeve's rule, with flags of 2026-10-11. Mandatories shortable: 9 → 8. ARES.PRB and DUKU lost it; MCHPP gained it [V] | **changed with the date** (landmine 5); both reported |
| 5 | hedged residual vol | 6–14% (DHR.PRA 11.3, DHR.PRB 13.7, BDXB 6.5, AVTR.PRA 6.2) | raw closes: 11.28 / 13.72 / 6.46 / 6.16%. Dividend-adjusted: 11.27 / 13.82 / 5.78 / 5.89%. Weekly, 2019–22 [V] | reproduced |
| 5 | cheapness | unmeasured | unmeasured: no implied vol for the issuers' options in any panel | gap stands |
| 6 | release-day reaction 0.46× the fund-specific NAV surprise; corr +0.28, t 4.0; no drift; ceiling ≈ 43bp per event | 193 events, 5 BDCs, 2012–22 | — | **could not re-run** (§4). The NAVs were typed in from about 205 press releases read through WebFetch; there is no fetcher, and building one needs the SEC user-agent (plan 0.7). The arithmetic is internally consistent: t = r√(n−2)/√(1−r²) = 4.02; 0.459 × 0.0094 = 43bp; R² 0.078 = 0.279². The t is not clustered by quarter |
| 11 | BDC discount 88% persistent between funds | 21 BDCs, XBRL NAV, 2022-08..2024-12 | — | **could not re-run** (same reason). Arithmetic consistent: 0.0450 / (0.0450 + 0.0059) = 0.88. It is a level statistic, not a return |
| 11 | point-in-time NAV only from 2022-08 (Inline XBRL) | "2022-08-01 (seasoned filers) or 2023-02-01 (others)" | SEC, 2020-04-08: Forms "filed on or after August 1, 2022" for BDCs and CEFs **eligible to file a short-form registration statement**, "February 1, 2023" for others [V]. ARCC's first `NetAssetValuePerShare` fact is in its 10-Q filed 2022-10-25 [V] | reproduced; **wording corrected** ("short-form eligible", not "seasoned") |
| §7.4 | "the suspected pandas rolling-sum fault does not reproduce on the live inputs" | values ≈ 1e-316 in the agent's first run; cause not isolated | **It reproduces, and it is not the agent's code.** Re-running the agent's original pandas lines gives its corrupted figures exactly ([−1,0] −1.20%, 756 events); with numexpr off the same lines give −4.41% and 755 (§3) [V] | **corrected** |

## 2. Convertible issuance (row 4) and gate G3

`python3 scripts/events/convert_issuance.py` (output:
`results/events/convert_issuance_2026-10-11.txt`; events:
`results/events/convert_issuance_events.csv`).

**Method, kept from the agent so the figures compare:**

- **Universe.** TRACE master CUSIPs flagged convertible (`cnvrb_fl='Y'`,
  CORP), ever 144A.
- **Day 0.** The first 144A trade, within 10 days of the master's set-up date.
- **Issuer.** CUSIP6 → CRSP common.
- **Returns.** CRSP `ret` − SPY's `ret`, summed over each window.
- **Control.** The same pipeline on straight 144A debt.

The agent named that control before running it (H12).

**Added:**

- clustered SEs (by date and by week; the gate statistic, declared in the
  docstring before the run, is the week-clustered t);
- a calendar-time portfolio;
- convert minus control, overall and by era;
- the issuer-day collapse;
- a beta-adjusted check: β from days −260..−11, no intercept. That gives
  +0.51% (t 2.19) on 708 events, against +0.52% market-adjusted on the same
  events. Median β 1.19.

**Clustering of issue dates.**

- Events per year: 2011 37, 2012 25, 2013 63, 2014 46, 2015 44, 2016 41, 2017 62,
  2018 92, 2019 66, 2020 130, 2021 118, 2022 31.
- The busiest day had 9 events, the busiest week 13. 328 weeks have an event.

**The cost grid.** A long MOC on day +1 and an exit MOC on day +5 is one round
trip:

| | gross | 5bp | 15bp | 30bp |
|---|---:|---:|---:|---:|
| convert, per event | +54bp | +44bp | +24bp | −6bp |

Borrow: none (long only). The sign flips at 30bp.

**Eras (H5).** All t are week-clustered.

| era | convert [+2,+5] | control [+2,+5] | convert − control |
|---|---|---|---|
| 2010–14 (n 171) | +1.02% (t 2.44) | −0.51% | +1.53% (t 3.43) |
| 2015–19 (n 305) | +0.14% (t 0.55) | −0.41% | +0.55% (t 1.84) |
| 2020–22 (n 279) | +0.69% (t 1.28) | **+0.52%** (t 1.51) | +0.17% (t 0.32) |
| 2023–26 | sealed | sealed | sealed |

**G3 reading: passes on its letter, narrowly.** The re-run reproduces +0.54% over
days +2..+5 with clustered t ≥ 2: 2.24 by week (the declared statistic), 2.37 by
date, and 2.58 calendar-time. The issuer-day collapse gives 2.10.

But three things belong in any E2 pre-registration:

1. **The effect lives in 2010–14.** Over 2015–22 the convert mean is +0.14% and
   +0.69%, neither with t above 1.3.
2. **In 2020–22 the straight-debt control earns +0.52%, almost all of the
   convert's +0.69%.** That is the graveyard's second pattern: a control
   scoring as well as the treatment.
3. **Net at 30bp one-way is negative.** E2's kill test is set at 15bp (+24bp
   here), but H3 asks that the answer not flip across the grid, and it does.

A 2023–24 holdout run is the test that matters, and it is untouched.

## 3. The §7.4 fault: numexpr, not the agent's code

`python3 scripts/events/numexpr_fault.py --agent` (output:
`results/events/numexpr_fault_2026-10-11.txt`).

**What happened.** The agent's second run used ordinary pandas:

```
R = px.pivot(...)
AR = R.sub(spy, axis=0)
AR[p].iloc[a:b].sum()
```

R was 3,105 days × 501 permnos, which is 1.56m cells. pandas 2.3.3 sends frame
arithmetic to numexpr above 1,000,000 cells. On this laptop (Anaconda, Python
3.13.5, numexpr 2.10.1, numpy 2.3.4), numexpr gets **broadcast** arithmetic wrong.

**Measured on synthetic data** (a check on our code, not a market claim). On a
1.56m-cell frame:

| operation | wrong cells, numexpr on | numexpr off |
|---|---:|---:|
| `df.sub(col, axis=0)` | 790,400 | 0 |
| `df - df.mean()` | 1,125,004 | 0 |
| `df.div(rowsum, axis=0)` | 790,674 | 0 |
| `df + df` (same shape, no broadcast) | 0 | 0 |

- The wrong cells hold denormals (~1e-316), NaN where the answer is finite, or
  other cells' values.
- The pattern changes from run to run. A 931,500-cell frame (below the
  threshold) is exact.

**On the agent's own inputs and lines:**

| | numexpr on | numexpr off |
|---|---|---|
| events | 756 | 755 |
| [−1,0] | −1.20% (the agent's second-run figure) | −4.41% |
| [+2,+5] | +0.13% | +0.54% |
| denormal window sums | 46–195 per window, none in the 60-day window (counts change run to run: an earlier run gave 72–318) | none |

**What fixed it for the agent.** It switched to numpy arrays, which bypass
numexpr. Turning bottleneck off did nothing.

**Why §7.4's check passed.** The discount panel is under 1e6 cells, and the check
tested rolling reductions, not broadcast arithmetic.

**The live book.** `build_targets()` frames are 5,467 × 13 = 71,071 cells [V], so
the sleeve's arithmetic is far below the threshold. `numexpr` is not in
`requirements.txt`, so the VM probably lacks it. That is [U]: run the script there.

**The scripts here.** Everything in `scripts/events/` turns
`compute.use_numexpr` off at import and asserts that no window sum is
denormal-like.

**Recommendation (for the team lead, not acted on).** Add a repo-wide guard,
either `pd.set_option("compute.use_numexpr", False)` in a shared import or a
test that runs `numexpr_fault.py`. Without it, any research script on the laptop
that broadcasts over a wide CRSP or TRACE frame can be silently wrong.

## 4. Listed mandatory convertibles (row 5) and gate G4

`python3 scripts/events/mandatory_census.py` (output:
`results/events/mandatory/mandatory_census_2026-10-11.txt`).

**Files written:**

- `mandatory/alpaca_convertible_assets_2026-10-11.csv`, with `.meta.json`: every
  convertible-named asset on the active and inactive lists, with today's flags;
- `mandatory/mandatory_liquidity.csv`;
- `mandatory/mandatory_hedged_vol.csv`;
- `mandatory/mandatory_g4_history.csv`.

**Shortability (2026-10-11, true on that date only).** 8 of the 24 active
mandatories are shortable, all easy to borrow: GOOGM, GOOGN, HPE.PRC, MCHPP,
NEE.PRS, NEE.PRT, ORCL.PRD, SMCIP. 1 of 11 tradable optional convertible
preferreds is shortable (RLJ.PRA); WFC.PRL was shortable on 2026-10-08 and is
not today.

**Two floor definitions, both reported.**

- **The agent's.** The median over its window: 12 clear.
- **The sleeve's.** The 63-session mean, shifted 1: 19 clear.

NFEGP has 19 prior bars, under the sleeve's 21-bar minimum, so it has no ADV and
is counted as not clearing.

**G4 reading: not met on what is measurable; the full census is blocked.**
CRSP holds no mandatory, unit or preferred share class (checked 2026-10-11 on
`dsenames` 2016–22). So the census uses Alpaca's own lists.

- **The lists.** The active and inactive lists hold 44 distinct mandatory-named
  symbols.
- **With history.** 19 have SIP bars in 2016-01..2022-12, all with ≥ 250 bars.
  3 of those span 4.6–7.0 years, longer than a mandatory lives (CCI.PRA, NEE.PRQ,
  NEE.PRR), so their symbols carried other securities too.
- **N, clean.** That leaves **16**.
- **Off the lists.** Two more, DHR.PRB and BDXB, have bars but are on neither
  list, so Alpaca's inactive list is incomplete.

**Measured N: 16 to 21, below 30.** It is a lower bound, not a kill.

The full census needs EDGAR 424B filings, which wait on the SEC user-agent
(0.7). Until then E3 cannot be pre-registered.

## 5. BDC release events and co-held loan marks (rows 6 and 11), and gate G5

**Why the figures could not be re-run.** The agent's NAV inputs were not
fetched by code. It read about 205 BDC press releases and 21 XBRL
`companyconcept` files through WebFetch, a model-mediated reader. It then
**typed the values into CSVs by hand** (heredocs in its Bash calls).

That breaks "never hand-copy a data series". A fetcher must call EDGAR with a
declared contact user-agent. The env file has no `SEC_USER_AGENT` (checked as a
boolean), and plan 0.7 reserves that string for the team lead. So no figure in
row 6, and none of row 11's BDC figures, is reproduced. They stay agent
measurements [U].

**What was checked [V]:**

- **ARCC's XBRL values.** WebFetch of ARCC's `companyconcept` on 2026-10-11
  gives 8 values for overlapping period-ends. All 8 match the agent's ARCC
  XBRL file.
- **ARCC's year-end NAVs.** Its 10-K XBRL values for 2012–15 (16.04, 16.46,
  16.82, 16.46) match the press-release NAVs the agent typed. That is one fund,
  not a fetcher.
- **Arithmetic.** The arithmetic of every row-6/11 figure is consistent (table
  above).

**Method notes from reading its code** (`analysis_bdc.py`, `robust_bdc.py` in the
transcript), for whoever builds the fetcher:

- **The t of 4.0 treats 193 events as independent.** They sit in 44
  quarter-ends, and the fund-specific surprise is demeaned within each quarter.
  Re-run with SEs clustered by quarter and by fund.
- **The 0.46 slope and the 43bp ceiling are in-sample, perfect-foresight
  numbers.** They bound the idea; they do not estimate it.
- **Survivorship.** The abnormal-return benchmark is an equal weight of BDCs
  alive at Alpaca on 2026-10-08.
- **Pre-announced estimates.** Some funds pre-announce NAV estimates (GBDC
  2020–22, TSLX 2020-Q1/Q2, NMFC 2015-Q4 and 2022-Q3). For those quarters the
  information date is earlier than the release.

**G5 reading: not measured. The feasibility evidence leans against.**

- **No loan identifier.** ARCC's 10-Q for 2021-09-30 (filed 2021-10-26) lists
  each loan by borrower legal name, business description, instrument text
  ("First lien senior secured loan ($45.6 par due 12/2024)"), coupon and spread,
  acquisition date, cost and fair value. It carries **no loan identifier**: no
  CUSIP, LoanX ID, FIGI or LIN [V, one filing, read through WebFetch]. A
  cross-BDC match would be fuzzy, on borrower name plus par, maturity and
  spread.
- **HTML before 2023.** Inline XBRL starts 2022-08-01 or 2023-02-01 [V]. So
  pre-2023 schedules for ≥ 20 BDCs mean parsing HTML filings.
- **The 70% match-rate bar is unmeasured.** It cannot be measured without the
  fetcher (0.7) and a parser. The plan says not to build the parser yet.
- **The Boston Fed paper's 168 BDCs** with loan-level data since 2022 is the
  agent's reading [S]; it was not re-read here.

## 6. Gaps

- **The SEC user-agent (plan 0.7)** blocks three things: the BDC re-run, the G4
  EDGAR census, and the G5 match rate.
- **Convert cheapness and mandatory cheapness** need issuer option implied vols.
  No panel has them.
- **Whether the VM's Python has numexpr** (and so the fault) is unmeasured.
- **Ticker reuse in the Alpaca census** is flagged by bar span, not resolved.
- **Day 0 timing.** Day 0 is the first TRACE trade, not the press release. An E2
  implementation needs announcement times, and TRACE disseminated 144A trades
  only from mid-2014 [S, agent; not re-read].

## 7. Side finding (live path, not acted on)

The live sleeve's ADV floor
(`src/deploy/sleeves/cef_discount.py`, `if float(adv.loc[last, tk] or 0.0) < self._min_adv`)
lets a name with an **undefined (NaN) ADV pass**. In Python, `nan or 0.0` is
`nan`, and `nan < x` is False.

A name with a finite z but fewer than 21 non-missing price × volume values in its
last 63 sessions would therefore skip the liquidity filter silently.

- Whether that has ever happened is unmeasured.
- It is a live-path change, so it needs its own test and release.

## Files

- `scripts/events/convert_issuance.py`: row 4, G3.
- `scripts/events/mandatory_census.py`: row 5, G4. It is also the fetcher for
  the Alpaca asset and bar data used here.
- `scripts/events/numexpr_fault.py`: §7.4.
- `results/events/`:
  - the three run outputs (`*_2026-10-11.txt`);
  - the event table;
  - the Alpaca snapshot;
  - the mandatory tables.
- R2 and bar caches go under `results/events/_cache_*`, which is gitignored and
  rebuilt with `--refresh`.


**Licensed rows are not in git (2026-10-11).** Row-level tables derived from CRSP
and TRACE (WRDS, licensed) are written by the scripts above but kept out of this
public repository (`.gitignore`). Only aggregates are tracked. Re-run the scripts
with R2 access to rebuild them.
