# Five zero-trial screens, 2026-10-26

The team lead asked what to do next as PM, whether macro regime filters would help, and which
event angles to try. They chose these five screens and asked for gross P&L only: "don't
overcomplicate it with costs". **No trial was spent and no counter moved.** Every return is dated
on or before 2022-12-30, which each script asserts. The 2023-01-01 time holdout and the 27 sealed
`cef_universe.csv` names were not read.

| folder | question | verdict | headline [V] |
|---|---|---|---|
| `r1_macro_state/` | Does a group's own macro observable (HY OAS; SIFMA; repo) change the deployed signal's within-group IC? This is a zero-trial preview of C2 Part D. | **NOTHING** | No own-observable split reaches \|t\| 2. The mismatched-observable control scores the same. Within-muni IC is −0.077 to −0.123 in every SIFMA state. |
| `r2_macro_days/` | Do discount moves on FOMC/CPI/NFP days revert more than same-size moves on other days? | **NOTHING** | Extra price-leg reversion −6.9bp per unit (t −0.36). Placebo weeks score +19.1 (t +0.97). Ordinary-day reversion runs through price, −37.3 (t −3.39), not NAV. |
| `r3_c4_exdate/` + `r3_review/` + `r6_exdrift/` | Is C4's ex-date P&L concentration (82.1% committed / 52.6% corrected holdout; 33.1% fit) real? | **MIXED** after the independent review | The post-ex drift is real and generic, and shorting into any ex-date earns it. Once that profile is removed, the C4-specific window excess is t 1.69 against the 2.0 bar. Paper overstates C4: price-only Sharpe 1.360 vs total-return 1.217 on the fit. |
| `r4_index_rebal/` | Do YYY/PCEF/XMPT reconstitutions force flow ≥ 1 ADV that a `shift(2)` book can trade? | **ARTIFACT** (pooled) after the R2 pull; *was INFEASIBLE on 2026-10-26* | On CRSP MF holdings, 137 events ≥ 1 ADV, sized without lookahead, pass the gate. The pooled pressure is +50bp (t 2.23) and the reversal −73bp (t −3.58). **But the placebo one month earlier scores +113bp (t 2.87)**, from YYY, whose window follows its own yield-and-discount ranking. PCEF alone: +184bp (t 5.5), then −120bp (t −5.6); placebo +8bp. That is a post-hoc subgroup. |
| `r5_bdc/` + `r5_review/` | Does the discount z-score work on BDCs? | **NOTHING in the tradable set** after the R2 pull and an adversarial review; *was INFEASIBLE on 2026-10-26* | Compustat ceqq/cshoq matches XBRL NAV on 167 of 175 checks. All 54 BDCs: IC +0.0258 (t 5.14), not stale prices, and a NAV placebo scores less. **ADV ≥ $3m (14 names): 2012–17 null, and in 2018–22 the NAV term is t 0.48 next to 5-day reversal.** In the names the book could trade, it is short-term reversal. |

## The finding that came out of r3: the post-ex-date drift

A second method in `r6_exdrift/` is independent of `c4_families.py`. It computes its own total returns,
measured against the same-date equal-weight mean.

- On C4's families, a short at the ex-date close covered at +3 earns **CAR(+1..+3) −34.3bp (t −14.9,
  month-clustered) on 2005–22**, and −30.1bp (t −5.6) on every year in the panel (1982–2022).
  *Corrected 2026-10-27: this line first gave the 1982–2022 figure without saying so.*
  - With Eaton Vance excluded it is −34.8bp (t −14.3) on 2005–22, and −30.0bp on 1982–2022.
  - It is negative in 2005–09, 2010–15 and 2016–22.
  - It is larger for larger distributions.
- On the 17 credit CEFs it is **−20.5bp (t −6.8)**.

**It was found after the fit window was seen, so it is a hypothesis, not evidence.** *Provenance, corrected 2026-10-27:* W4 recorded the same pattern first, on the credit funds (`results/cef/W4_ARTIFACTS_2026-10-11.md` §1, "Ex-date arithmetic": the discount falls a further −0.306pp and −0.197pp over the two sessions after the ex-date, "a post-ex-date price pattern, not arithmetic"), as an observation it did not test. The 2026-10-26 review rediscovered it. A
pre-registration draft is with the team lead.

## How to reproduce

The runs used an export of `simon` at `dff4b5c`, with `data/` linked in, and **cwd = the repo root**.
Paths inside the scripts are relative to each script's own folder (`HERE`), so run them from the root:

```bash
python3 -B results/cef/screens_2026-10-26/r1_macro_state/r1_macro_state.py
python3 -B results/cef/screens_2026-10-26/r2_macro_days/r2_macro_days.py
python3 -B results/cef/screens_2026-10-26/r6_exdrift/check.py .
python3 -B results/cef/screens_2026-10-26/r6_exdrift/check_credit.py .
```

What is not in the repo, and why:

- **Fetched raw files** (FRED, SIFMA, the Fed's FOMC pages, Wayback snapshots) were left out
  because this repository is public. Re-fetch them with each folder's `fetch_*.py` into its `raw/`.
  Each NOTE.md names its sources and fetch times.
- **CRSP and Compustat data.** `r3_c4_exdate/`, `r3_review/`, `r4_index_rebal/` (part 2), `r5_bdc/` and `r5_review/` read
  licensed data that is never committed: local research-worktree CRSP caches, and the team lead's R2 pull in the gitignored
  `results/events/_cache_r7_r2_pull/`. Row-level outputs (`p2_*.csv`, the part-2 run logs) were left out. The r4/r5 scripts were run from
  the scratch layout (`SCRATCH/tree` + `SCRATCH/<screen>/`), so they need those caches, and their paths, set up again.
