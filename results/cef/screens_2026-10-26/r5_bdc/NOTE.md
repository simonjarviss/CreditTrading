# R5: does the CEF discount z-score work on BDCs? Zero-trial screen, 2026-10-26

Report only. **No trial spent and no counter moved.** Asked by the team lead on 2026-10-26.
Code tree: export of branch `simon` at dff4b5c. No network fetch was made, so `raw/` is empty.

Labels: [V] computed now by a script in this folder, [S] sourced but not re-read,
[U] uncertain, [doc] copied from a repo note.

## 1. Question and scope

The book's signal is the z-score of each fund's price-to-NAV discount against the fund's
own trailing window, demeaned across funds: long the cheap funds, short the rich ones.
Does it work on listed Business Development Companies (BDCs)? BDCs are closed-end, with no
creation or redemption.

**This screen covers BDCs only.**
- Preferred ETFs against their NAV are already dead: `single-fund-PD` (D1) in
  `docs/RESEARCH_STATE.md` [doc]. An ETF's premium or discount is NAV staleness.
- Preferred CEFs already sit inside C4's preferred family.

**Prior (graveyard pattern #1, `.claude/skills/graveyard/SKILL.md`)** [doc]. Six of
thirteen deaths were "price minus a stale mark". A quarterly NAV is the stalest mark
there is. Between filings, P/NAV moves only through price. The frozen spec's
`z_window` is 252 sessions [V, read through `scripts/cef/spec.py`], so one trailing window
holds about four NAV prints. Inside it, the z-score of P/NAV is mostly a z-score of price
with a few step changes.

## 2. Feasibility requirement (declared before searching)

We need a point-in-time NAV per share, with the date it became public, for **≥ 20 listed
BDCs across ≥ 5 years of 2012–2022**, plus their daily prices. The NAV counts as known
on the filing date of the 10-Q, 10-K or press release that reports it, never on the
quarter-end date.

## 3. Feasibility findings: what is on this machine

| ingredient | where it was looked for | result |
|---|---|---|
| BDC NAV in `data/` | every parquet and CSV identifier column, plus every column name in wide panels (`scripts/scan_data_dir.py`, `scripts/scan_data_wide.py`) | **None.** No panel in `data/` holds a BDC NAV [V]. The NAV panels (`data/cef/cef_nav.parquet`, `data/cef_families/cef_nav*.parquet`, the iShares and JNK NAV files) hold CEFs and ETFs only. The only BDC tickers anywhere in `data/` are three names (MAIN, ORCC, SSSS) in the merger-target name map `events/merger_targets/crsp_names_linked.csv`, with no NAV [V]. Some files under `holdings/raw/*.csv` are iShares bond-ETF holdings files that do not parse as plain CSV. They are not BDC sources. |
| CEFConnect coverage | `data/cef_families/raw/cefconnect_dailypricing_2026-10-12.json` (359 funds) | **0 BDCs** listed [V] |
| NAV knowledge dates | `d2_bdc_reports.parquet` in the D2 cache (worktree `research-ss-expansion`, `results/events/ssx/_cache_ssx_fil/`) | **Present.** 1,943 10-Q/10-K reports from 61 listed BDCs, filed 2012-01-01 → 2022-12-16. Of these BDCs, 46 have ≥ 20 reports spanning ≥ 5 years [V]. The index includes dead names such as ACAS, MCGC and MVC, so it is not survivor-only [V]. |
| NAV values from XBRL, point-in-time | `d2_bdc_navps_facts.parquet` (cached companyfacts) | **Fails.** For these 61 BDCs, the facts known by 2022-12-31 cover only 175 distinct BDC period-ends, 2017–22, almost all of them 2020–22 (35 / 79 / 49). They come from 39 BDCs. **0 BDCs have ≥ 20 quarters, and 1 spans ≥ 5 years** [V]. See the note on the 9.0% figure below this table. |
| NAV values from XBRL, read loosely (not point-in-time) | the same file, allowing values from later filings that restate old periods | **Fails even so.** 505 period-ends, mostly year-ends, and **0 BDCs reach ≥ 20** [V] |
| NAV values from Compustat | `comp_fundq_rdq.parquet` (local cache) | The local cache holds only `gvkey, datadate, rdq`, with **no `ceqq`/`cshoq`** [V]. It does show the route would cover the universe: 2,017 BDC-quarters with an `rdq` in 2012–22 across the 61 linked gvkeys, 49 of them with ≥ 20 quarters. `rdq − datadate` is 32 / 39 / 65 days at p10 / p50 / p90 [V]. |
| NAV from filing text already cached | all 17 local `_cache_edgar` and `_cache_event_engine` folders in the worktrees (`scripts/scan_edgar_caches.py`) | **Fails.** The caches hold 31 of the 1,943 listed-BDC 10-Q/10-K reports, and 23 of the 2,440 BDC 8-K item 2.02 earnings releases for 2012–22 (16 BDCs) [V]. |
| daily prices | local licensed CRSP caches (`scripts/scan_prices.py`; read only through 2022-12-30) | **Present.** `research-ss-expansion/results/events/_cache_crsp/dsf_44015b5199.parquet` covers 54 of 61 BDC permnos in 2012–22, and 44 of them have ≥ 1,260 price days. Last date read: 2022-12-30 [V]. These files are not in `data/`. |

**Note on the 9.0% point-in-time figure.** It is 175 period-ends against 1,943 reports.
This is a looser metric than D2's 1.6% [doc]. It counts any NAV-per-share fact known by
the end of 2022, including the comparative periods printed in 2022 filings. D2 counted
only a report's own period. Both say the same thing: XBRL NAV starts in 2022.

**Conclusion.** Dates and prices exist locally; **the NAV values do not.** The
requirement fails: 0 BDCs have ≥ 20 point-in-time quarters, against the ≥ 20 BDCs needed.
I stopped here. I computed no signal, IC or P&L, and loaded no return.

## 4. Step-1 verdict (2026-10-26): **INFEASIBLE**. Superseded by step 2 (§8–§9)

The team lead then ran the R2 pull named in §5.1 (2026-10-27). §3 and §5 record step 1
as it stood.

## 5. What would make it feasible (each needs the team lead)

1. **R2 read, the cheapest route.** Read `comp_na_daily_all.fundq` (Compustat; it is on
   R2 per `results/events/ssx/ssx_data/r2_full_inventory_columns_2026-10-19.csv` [V])
   with the columns `gvkey, datadate, rdq, ceqq, cshoq, cshopq, tic, cik`, for the
   61 linked gvkeys.
   - Coverage: about **2,017 BDC-quarters, 49 BDCs with ≥ 20 quarters**, sized from the
     local `rdq` rows [V].
   - Needs: R2 credentials, held by the team lead.
   - NAV per share ≈ `ceqq / cshoq` [U]. This is book equity per share. It equals NAV
     per share only up to preferred equity and the date of the share count, and
     Compustat can carry restated values.
   - Validate it against the 175 point-in-time XBRL NAV values for 2020–22 before
     using it.
2. **EDGAR text route.** Parse NAV per share from the text of the filings. This needs the
   team lead's `SEC_USER_AGENT`. The local index already lists every accession, so no
   search is needed.
   - **10-Q/10-K text: 1,943 listed reports, 61 BDCs** [V].
   - Or the earnings releases (8-K item 2.02, EX-99.1): **2,440 releases, 59 BDCs** [V].
     17 of 20 sampled releases print NAV per share as text [doc].
   - Either way that is about 2,000–2,500 document fetches, less the 31 + 23 already
     cached.
3. **Prices.** The CRSP BDC prices exist only in a worktree cache. A trial would need
   them staged by a fetcher, with a source note in `docs/REFERENCES.md` (never copied
   by hand), and written outside `data/`.

## 6. Design for a real trial (declared now; not run)

This is the design any later run must keep. It is fixed before anyone sees a number.

- **Universe.** Listed BDCs from the local report index. Each name enters on its first
  filing date with a NAV and a price, and leaves at delisting.
- **Window.** Fit window only: dates ≤ 2022-12-30, asserted in code. Eras 2012–17 and
  2018–22 (H5).
- **Knowledge date.** NAV_q is known from the session of the 10-Q/10-K `filingDate`, or
  the next session if the filing was accepted at or after 16:00 ET. Sensitivity run: the
  2.02 release or `rdq` date, under the same 16:00 rule. Assert that the known date is
  after the period end and no earlier than the filing date.
- **Signal.** d_t = P_t / NAV_last-known(t) − 1. Its z-score uses the fund's own trailing
  `z_window` (read from the spec), shifted one day and demeaned across funds. Long cheap,
  short rich, as in the book.
- **IC.** Use W4's forward window, close t+1 → close t+3, on non-overlapping dates
  (`scripts/cef/w4_artifacts.py`), reported by era. Any P&L mirrors `evaluate()` in
  `scripts/cef/band_frontier.py` (shift(2)). Gross only.
- **Negative control.** The z-score of log price against its own trailing `z_window`,
  with no NAV, under the same demeaning, forward window and dates. **ARTIFACT/NOTHING**
  if either holds:
  - the control's IC ≥ the treatment's IC in either era;
  - the treatment's IC, partialled on the control, has t < 2.
- **Second check.** IC on the 5 sessions after each fresh NAV filing, against all other
  sessions. If the NAV carries information, the IC should concentrate after filings. If
  it is flat or lower there, the signal is price reversal.
- **PROMISING** needs all three:
  - treatment IC > 0 with t ≥ 2 in both eras;
  - it beats the control under both conditions above;
  - the post-filing IC ≥ the IC on other sessions.

## 6a. Amendment, 2026-10-27, written BEFORE any NAV, signal or IC was computed

On 2026-10-27 the team lead ran the R2 pull named in §5.1. The data is in
`.claude/worktrees/simon/results/events/_cache_r7_r2_pull/bdc/`. It is gitignored and
licensed, and no value from it goes into a tracked file. The coordinator relayed three
rules: validate against the 175 XBRL values first; a NAV is known on `rdq`; a null
`rdq` is excluded, never imputed. Those rules, and the clarifications below, replace §6
wherever the two differ.

**A. NAV validation (gate, run first).**
- NAV per share = `ceqq / cshoq`.
- Exclude rows with a null `rdq`, `ceqq` or `cshoq`, or `cshoq ≤ 0`. Count each kind;
  nothing is imputed.
- A duplicated `(gvkey, datadate)` collapses only if all its values agree. Otherwise both
  rows are excluded and counted.
- Compare against the 175 point-in-time XBRL values on `(cik, period end = datadate)`.
  Where XBRL holds several values for one period-end, use the earliest-filed one.
- **Match** = |Compustat / XBRL − 1| ≤ 1%. Also reported: the shares within 0.1% and
  within 5%, and the median absolute difference.
- **Stop rule.** If fewer than 90% of the comparable pairs match, stop. Report both
  sources and pick neither.
- Second check, labelled and not the gate: the same comparison against the 505 XBRL
  values read loosely (not point-in-time), which reach back to 2012.

**B. Knowledge date.** The primary knowledge date is now `rdq`, replacing §6's
`filingDate`.
- NAV_q enters the discount on every session t ≥ `rdq`.
- This is the book's own alignment. `disc_t` uses information from date t, and the
  book's decision at t is made after t's close (the CEF NAV for t is also published
  after the close), with the fill in the t+1 closing auction. Assert that `rdq` falls
  after `datadate`.
- **Sensitivity (§6's primary):** knowledge date = the first 10-Q/10-K `filingDate`
  that reports the period, moved to the next session if accepted at or after 16:00 ET.
  This guards the 3 of 20 releases that print no NAV [doc].
- **Expiry.** A NAV whose `datadate` is more than 200 calendar days before t is expired,
  and that day's discount is NaN. 200 days is one quarter plus the p90 10-K lag of
  89 days [doc], with margin. The expired name-days are counted.

**C. Prices and splits.**
- Prices are CRSP `dsf_44015b5199.parquet`, read only through 2022-12-30 and asserted.
- The price is `|prc|`, CRSP's close or its bid/ask midpoint on no-trade days. The
  no-trade share is reported.
- Forward returns use CRSP `ret` (total return), filtered to |ret| < 0.5 as W4 does.
- Splits: `disc_t = 100 · (P̃_t − Ñ_q) / Ñ_q`, with P̃_t = |prc_t| / cfacpr_t and
  Ñ_q = NAV_q / cfacpr at the last CRSP session ≤ datadate. A missing `cfacpr` raises.

**D. Signal, exactly the book's (`build_panel`).**
- `mu` and `sd` are the rolling mean and standard deviation of `disc` over
  `Z_WINDOW` = 252 sessions with `MIN_PERIODS` = 120 non-NaN rows, each `.shift(1)`.
- z = (disc − mu) / sd, clipped to ±4. Parameters are read from the spec and
  band_frontier, never written as literals.
- Control: the same construction on log(P̃_t).

**E. IC.**
- Spearman across names per date, with the forward window closes t+1 → t+3
  (`fwd(r, 2, 3)`). The grid is every second session: phase 0 is the headline, phase 1
  is reported beside it. Min names = the spec's `MIN_NAMES`. t = mean / sd · √n, with
  Newey-West beside it.
- **Sign.** The traded signal is s = −z (long cheap). The IC is reported on s, so
  **IC > 0 means the signal works**, and §6's "> 0" reads that way. W4 prints
  Spearman(z, ·), which is negative when the signal works.
- **Primary set.** Every name with a z on that date (§6's universe). The deployed-style
  set (63-day ADV through t−1 ≥ the spec's `MIN_ADV_USD`) is reported beside it,
  labelled, and does not decide.
- **Eras:** 2012–17, 2018–22, and fit 2012–22.

**F. Partial IC.** Per date, the Spearman partial correlation of s_T with the forward
return, given s_C:
`(r_TF − r_TC·r_CF) / √((1 − r_TC²)(1 − r_CF²))`. Report its mean and t across the
grid dates.

**G. Post-filing check.**
- k = sessions since the NAV in use became known, with k = 0 on the first session ≥ `rdq`.
- Post = {k ≤ 4}, the five sessions that start with the knowledge date.
- Per date, compute the IC on post names and on the other names, each needing
  ≥ `MIN_NAMES`. Compare the means.
- The control's IC on the same split is shown for context and does not decide.

**Verdict rules: §6, unchanged.** Three readings were fixed before any IC was
computed:
- **Common sample.** Treatment and control are scored on the same name-dates: those
  where both z's exist.
- **Where the partial t is read.** The partial-IC t condition applies to fit 2012–22,
  primary set, phase 0. The eras are reported beside it.
- **Which failure is which.**
  - **NOTHING:** the treatment IC is not > 0 with t ≥ 2 in both eras.
  - **ARTIFACT:** the treatment IC passes that, but the control matches or beats it,
    or the partial t is < 2.
  - **PROMISING:** everything in §6 passes, including the post-filing check.

**Added after gate A, before any IC.** A NAV whose `datadate` precedes the security's
first CRSP price row has no CRSP share basis. These are pre-listing periods, and 4 of
gate A's 8 misses are such rows. They are excluded and counted, rather than raising.

## 7. Reproduce

```bash
S=/private/tmp/claude-501/-Users-simonjarvis-Downloads-2027-Projects-Quant---PM2027-2027/767b4ac8-7cb7-4bf6-953a-b785b037a5b4/scratchpad
# step 1 (feasibility)
cd $S/tree && python3 ../r5_bdc/scripts/scan_data_dir.py && python3 ../r5_bdc/scripts/scan_data_wide.py
cd $S/r5_bdc && python3 -I scripts/scan_edgar_caches.py && python3 -I scripts/scan_prices.py && python3 -I scripts/feasibility_counts.py
# step 2 (needs the 2026-10-27 R2 pull in .claude/worktrees/simon/results/events/_cache_r7_r2_pull/bdc/)
cd $S/r5_bdc && python3 scripts/validate_nav.py && python3 scripts/validate_misses.py \
  && python3 scripts/bdc_ic.py > out_bdc_ic.txt && python3 scripts/summarize.py > out_summary.txt \
  && python3 scripts/second_method.py
```

Outputs, all in this folder:
- step 1: `feasibility_counts.json` and `out_scan_*.txt`;
- step 2: `validate_nav.json`, `validate_misses.json`, `bdc_ic_results.json`,
  `out_summary.txt`, `second_method.json` and `out_second_method.txt`.

`_cache_r5/` holds licensed derived panels (Compustat/CRSP). It is scratch only, never to
be copied into a tracked file. No script uses the network. Every price, NAV and return
read is limited to dates ≤ 2022-12-30 and asserted.

## 8. Step-2 results (2026-10-27). Every figure is [V], computed now, unless labelled

### 8.1 Gate A: is Compustat `ceqq/cshoq` the NAV? **PASS**

- **Exclusions** (counted, nothing imputed):
  - 2,385 rows in;
  - 124 with a null `rdq`;
  - 15 more with a null `ceqq`/`cshoq`;
  - 3 duplicated keys, all with agreeing values, collapsed;
  - 2,243 rows usable, covering 61 BDCs.
- **Against the 175 point-in-time XBRL values** (39 BDCs, all 175 comparable): **167 of
  175 = 95.4% match within 1%**, which clears the 90% stop rule. 93.1% are within 0.1%;
  the median |diff| is 0.017% and p90 0.06%.
- **The 8 misses** come from 6 BDCs. Compustat is below XBRL by ratios of about 0.1 to
  0.95, and none falls between 1% and 5%.
  - 4 are explained within 1% by CRSP's split factor: a split between the quarter-end and
    the XBRL filing, so a share-basis difference.
  - The other 4 are quarters before the stock's first CRSP price row (pre-listing). They
    are excluded from the signal (§6a addendum).
  - Every miss with a CRSP basis is therefore explained.
- **Second check, the 505 loosely-read values:** 485 comparable, 92.0% within 1%.
  - 26 of the 39 misses are split-explained.
  - 8 are not, and all 8 come from XBRL filed after 2022, which this screen will not read
    CRSP to check.
  - The remaining 5 have no CRSP factor on or before the quarter-end.
- **Caveat [U].** Compustat is a current vintage, not point-in-time. The point-in-time
  check covers period-ends 2017–22. Earlier years rest on the loose set (2012–16:
  62 values, 93–100% matching).

### 8.2 Panel

- **Sources.** The CRSP cache covers 54 of the 61 BDCs. 7 have no rows, and their
  167 NAV rows drop. Survivorship direction unknown [U].
- **NAV rows excluded:** 86 pre-listing rows.
- **NAV in use (rdq rule):**
  - 1,983 NAV quarters;
  - 122,993 name-days carry a NAV;
  - 308 name-days were expired by the 200-day rule.
- **Prices:**
  - build_panel's own `close ≤ 0.5` filter dropped 289 price rows;
  - no-trade (bid/ask midpoint) days are 0.66% of signal name-days;
  - the calendar runs 2009-01-02 → 2022-12-30, at 250–253 sessions a year.
- **Coverage:**
  - the primary set has a median of 42 names per date;
  - the deployed-style set (ADV ≥ `MIN_ADV_USD`) has 14;
  - the ≥ `MIN_NAMES` threshold is first met on 2010-10-25.
- **Overlap.** The median rank correlation between the treatment and control signals is
  0.84.
- **Construction check.** The z code reproduces build_panel's z exactly (asserted).

### 8.3 IC on the traded signal s = −z (IC > 0 means long cheap works)

Forward window closes t+1 → t+3; Spearman; non-overlapping grid; CRSP total return. Each
cell is mean IC (t). Phase 0 is the headline.

| primary set, phase 0 | 2012–17 | 2018–22 | fit 2012–22 |
|---|---|---|---|
| **treatment** (discount z, NAV known on `rdq`) | **+0.0220 (3.07)** | **+0.0304 (4.38)** | **+0.0258 (5.14)** |
| **control** (log-price z, no NAV) | +0.0070 (0.96) | +0.0215 (2.96) | +0.0136 (2.62) |
| **partial**: treatment given control | +0.0325 (4.81) | +0.0200 (3.00) | **+0.0268 (5.62)** |
| post-filing (k ≤ 4), treatment | +0.0256 (0.83) | +0.0569 (2.00) | **+0.0409 (1.95)**, 254 dates |
| other sessions, treatment | +0.0186 (2.49) | +0.0266 (3.64) | **+0.0223 (4.23)** |
| post-filing, control (context) | −0.0149 | −0.0091 | −0.0120 (−0.64) |
| other sessions, control (context) | +0.0054 | +0.0222 | +0.0131 (2.41) |

Robustness. None of these decide; all are labelled.

| view | treatment fit IC (t) | control fit IC (t) | partial fit (t) | what changes |
|---|---|---|---|---|
| phase 1 grid | +0.0277 (5.65) | +0.0152 (2.95) | +0.0274 (5.75) | **post-filing +0.0123 (0.59) < others +0.0284 (5.43): the second check reverses** |
| knowledge date = 10-Q/10-K `filingDate`, phase 0 | +0.0258 (5.09) | +0.0134 (2.57) | +0.0267 (5.52) | post-filing +0.0752 (3.32) vs others +0.0225. Phase 1 reverses again: +0.0185 vs +0.0259 |
| **deployed-style set, ADV ≥ $3m**, phase 0 | **+0.0136 (1.65)**; 2012–17 **+0.0024 (0.21)**; 2018–22 +0.0270 (2.33) | +0.0045 (0.54) | +0.0195 (2.47) | **fails the era test in 2012–17**: the effect sits mostly in the less-liquid BDCs |
| second method: Fama-MacBeth slope, total return | +10.6 bp per z per 2 days (t 6.20); eras +6.1 (3.81) and +16.0 (4.96) | +10.7 (1.14) | — | sign and significance agree. A separate script reproduced the IC to four decimals |
| price returns instead of total (diagnostic only) | +0.0344 (6.85) | +0.0209 (4.04) | — | inflated by the dividend cycle, which is why the headline uses total return |

- **Knowledge-date gap.** `filingDate` minus `rdq` is 0 / 1 / 1 days at p10 / p50 / p90.
  34 filings precede their `rdq`. The sensitivity run dropped 21 NAV rows that match no
  10-Q/10-K.
- **Comparison with the book.** The CEF book's IC on 17 names was quoted as −0.074 on z,
  i.e. +0.074 on s [doc: `w4_artifacts.py`, citing docs/BRIEF.md 2026-09-05, itself
  [S]]. The BDC IC is about a third of that.

### 8.4 Reading against graveyard pattern #1

The ETF case (`single-fund-PD`) died because price led a stale NAV: the discount
predicted the NAV revision, not the price. Here the sign runs the other way. Price moves
toward the NAV, and the NAV adds information beyond pure price reversal (partial t 5.6,
in both eras, on both knowledge-date rules and both phases). So this is not the
stale-mark artifact in its ETF form.

Two things weaken it:
1. **The liquid names barely show it.** Before 2018, the deployed-style ADV set has no
   effect. A stale-price or illiquidity story is not ruled out for the full set.
2. **The post-filing check is unstable.** Its sign depends on which half of the grid is
   sampled (254 dates). The data does not show that the effect concentrates when a NAV
   arrives.

## 9. Step-2 verdict: **PROMISING** (by the declared rules; fragile)

Each declared condition, primary set, phase 0, `rdq` knowledge date:

| condition | result |
|---|---|
| treatment IC > 0 with t ≥ 2 in both eras | t 3.07 and 4.38 ✓ |
| control IC below treatment IC in both eras | 0.0070 vs 0.0220; 0.0215 vs 0.0304 ✓ |
| partial t ≥ 2 on fit 2012–22 | t 5.62 ✓ |
| post-filing IC ≥ IC on other sessions | 0.0409 vs 0.0223 ✓ |

**Fragile.** Two non-deciding views fail:
- the post-filing check reverses on the phase-1 grid, under both knowledge-date rules;
- the set the book would actually trade (ADV ≥ `MIN_ADV_USD`, 14 names) has no
  2012–17 effect (t 0.21; fit t 1.65).

Zero trials spent; no counter moved; no P&L computed (gross IC only, as asked).

**What a real trial would need:**
1. A `/prereg` under the counter the team lead rules on. C4, the same signal on the CEF
   families, is the precedent. It must name the ADV-filtered set as the traded set and
   say in advance how it treats the 2012–17 null.
2. Staged inputs. The Compustat pull and the CRSP BDC prices need fetchers and source
   notes in `docs/REFERENCES.md`, written outside `data/`. The 7 BDCs missing from CRSP
   need resolving.
3. A P&L through `evaluate()`, turnover-matched, with gross as the headline and the
   5/15/30bp grid beside it.
4. A borrow census: 23 of 34 BDCs are shortable today [doc: ssx_fund2].
5. One opening of the 2023+ time holdout. There, XBRL NAV covers 84–92% of
   BDC-quarters [doc: D2], which gives a point-in-time NAV to check Compustat against.
