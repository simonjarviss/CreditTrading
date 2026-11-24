# E1 revived: can a liquid ETF hedge the merger target? Zero-trial gate — 2026-10-15

**What this is.** Job 2 of the special-situations sprint (team lead,
2026-10-15). E1 is the NAV-for-NAV CEF merger pair. You go long the target
from the close of A+1 and short the acquirer, to completion. Its gross effect
lives in munis: median +167bp, clustered t 2.41
[S: `EDGAR_EVENTS_2026-10-12.md` §3; re-measured below]. Gate G1a failed
because Alpaca will not lend most muni acquirers (`G1A_SHORTABILITY_2026-10-13.md`).
The idea tested here: keep the long target and short a liquid ETF instead.
This note asks only whether that hedge is good enough, buildable and large
enough.

**Reproducer.** `python3 scripts/events/e1_etf_hedge_gate.py`, or
`python3 scripts/events/e1_etf_hedge_gate.py --offline --today 2026-10-15` to
run from the caches. Its tests are in
`scripts/events/tests/test_e1_etf_hedge_gate.py`.

**Zero trials.** No counter moves and nothing is pre-registered.
- **No ETF-hedged announcement→completion return was computed for any deal.**
  That return is the trial.
- Every target return here sits in a window that ends 42 sessions before
  the deal's EDGAR announcement date.
- The only deal-window figures read are the existing acquirer-pair returns
  (published 2026-10-12). They are read only per whole segment, to
  re-measure the effect's median, dispersion and clustered t at run time
  (H14). No sub-sample of them is computed.

**Holdouts.**
- Every return is dated before 2023-01-01. The latest test window ends on
  2022-02-01, and the CRSP extract's last row is 2022-12-30.
  `assert_pre_holdout` checks every window end and every N-PORT month.
- The sample is the 167 EDGAR-dated, priced deals, and no other deal is used.
- `assert_no_universe` checks every target and acquirer against
  `data/cef/cef_universe.csv`, by ticker and by CRSP permno (44 tickers,
  every permno that carried one). It found none. **The 27-name set is not
  consumed.**
- Alpaca flags, Alpaca dollar volume and the IBKR file are dated 2026-10.
  They are availability and cost, not returns.

**Data dates.**

| source | coverage |
|---|---|
| sample (`merger_ann_sample_edgar.csv`, gitignored) | regenerated in this worktree from the EDGAR and CRSP caches; byte-identical to the 2026-10-13 copy |
| CRSP daily (R2 mirror) | targets, acquirers, 19 ETFs, pulled 2026-10-15 20:38 and 20:43 UTC; rows before 2023-01-01 only (last 2022-12-30) |
| EDGAR N-PORT-P filings | 28 targets' filings with windows reaching 2019+; fetched 2026-10-15 |
| Alpaca `GET /v2/assets/{symbol}` (paper, cef key) | 19 ETFs, read 2026-10-15 20:38–20:43 UTC |
| Alpaca daily bars (SIP, raw) | 63 sessions, 2026-07-17 → 2026-10-14 |
| earlier Alpaca read on file | `results/xasset/feasibility/slate_feasibility_2026-10-12.csv` (2026-10-12 22:42 UTC) |
| IBKR shortstock file | `#BOF\|2026.10.13\|18:03:03`, cached by G1a |

**Labels.** Figures produced on 2026-10-15 by the reproducer are [V]. Each
Alpaca and IBKR flag is true on its date only (CLAUDE.md landmine 5).

## 0. The answer

**The gate fails in every segment. In munis, where the effect lives, it fails
twice over.**

1. **No muni ETF can be shorted at Alpaca.** MUB, VTEB, TFI, HYD, SUB, SHM,
   MLN, CMF and NYF all read `shortable: false` and `hard_to_borrow` on
   2026-10-15. MUB read the same on 2026-10-12. A second route (the Alpaca
   MCP server's `get_asset`) agrees for MUB and VTEB.
2. **Even if they could be, the hedge leaves too much risk.**
   - **The residual is several times the effect's own dispersion.** The
     muni deals' gross effect (acquirer pair) has a dispersion of **336bp**
     across 92 deals. A beta-hedged muni target over the median hold
     (168 sessions) keeps **787–794bp** of residual vol with the best ETFs.
     That is **2.3× the effect's dispersion**, against a proposed bar of 0.5×.
   - **The out-of-sample check agrees.** The realised out-of-sample
     residuals have a cross-sectional sd of 698–781bp.
   - **The hedge removes about a quarter of the target's variance** (26%
     with MUB).
   - **The power falls below the kill line.** If that residual were
     independent of the effect, an ETF-hedged E1 on the same deals would
     have an implied clustered t of about **0.94**, against 2.41 for the
     acquirer pair and E1's kill line of 2.

**Why: the discount, not the rate risk.**
- On the 10 muni targets with N-PORT NAV history, the ETF hedges NAV well.
  NAV correlates 0.955 with MUB and 0.975 with VTEB month to month. The
  NAV residual over the hold is 1.8–2.4%.
- On the same months, the price residual is 5.5–5.9%. Half or more of it is
  the fund's discount, which no ETF carries.
- Inside a deal, the acquirer short removes that discount risk through the
  NAV ratio. Nothing else here does.

**The best hedge per segment** (lowest median residual over the hold, among
the candidates fixed in advance):

| segment | best hedge | residual over hold | ÷ effect sd | buildable at Alpaca? | verdict |
|---|---|---:|---:|---|---|
| **muni** | TFI. MUB, HYD, MLN and VTEB are tied within 1% on common targets | 787bp (MUB 789) | 2.34 | **no**: every muni ETF is `hard_to_borrow`. The best shortable hedge is IEF (added post hoc), 851bp | **FAIL** (buildability and residual) |
| taxable | BKLN. PFF and HYG are within 5% | 641bp | 0.86; out-of-sample 1.96 | yes, but BKLN's capacity at $1m is 1.3% of ADV. HYG passes buildability and capacity at 0.90 / 1.62 | **FAIL** (residual); the effect is +5bp anyway |
| equity | SPY (EFA the same) | 829bp | 1.34 | yes | **FAIL** (residual); the effect is +15bp, t −0.16 |
| BDC | HYG (2 targets measured) | 1,357bp | 11.5 | yes; BIZD is not | **FAIL**; N too small to read |

**Against the acquirer hedge, on the same pre-announcement windows:**
- **Muni, all 81 targets.** The acquirer as hedge leaves 653bp, against
  787bp for TFI. The ETF is lower for 17% of targets.
- **Muni, the 12 deals whose acquirer Alpaca can short today.** The
  acquirer leaves 656bp, against 741bp for TFI. The out-of-sample sd is
  423bp against 641bp.
- **Inside the deal, the acquirer does much better.** The acquirer pair's
  own dispersion is 336bp, about half its pre-announcement residual.
  That is the NAV-ratio tie at work.

**Recommendation.** Do not spend EVENTS 0→1 on an ETF-hedged E1. The decision
is the team lead's; recording it is theirs (§7).

## 1. How to re-run

```bash
export QUANTT_ENV_FILE=".../config/.env"     # R2 (CRSP), Alpaca cef key, SEC_USER_AGENT; never printed
# inputs (gitignored), as in G1a's note §1:
python3 scripts/data/fetch_edgar_events.py
python3 scripts/events/edgar_merger_dates.py
python3 scripts/events/merger_pairs.py --edgar-dates
python3 scripts/events/g1a_shortability.py --offline --today 2026-10-13   # H3 flags + IBKR file
# this gate:
python3 scripts/events/e1_etf_hedge_gate.py --today 2026-10-15            # CRSP, EDGAR N-PORT, Alpaca
python3 scripts/events/e1_etf_hedge_gate.py --offline --today 2026-10-15  # the same from caches
python3 -m pytest scripts/events/tests/test_e1_etf_hedge_gate.py
```

Re-running offline reproduces the online summary exactly, apart from its
timestamp; this was checked.

**Outputs.**
- `results/events/e1_etf_hedge_summary_2026-10-15.json` (tracked): segment
  aggregates, the gate, and the Alpaca and IBKR rows.
- `results/events/e1_etf_hedge_detail.csv` (gitignored): one row per
  target and hedge. It carries CRSP permnos and statistics computed on CRSP
  returns.
- The Alpaca reads are cached in `results/events/_cache_e1_hedge/`
  (gitignored).

**How this worktree got its inputs.** The CRSP, EDGAR and G1a caches were
cloned from the `research-merger-g1a` worktree, and the inputs were then
rebuilt from them:
- `merger_edgar_dates.csv`, `merger_ann_sample_edgar.csv` and
  `g1a_historical_deals.csv` came out **byte-identical** to that worktree's
  copies.
- The index for the current quarter was re-fetched, because the cache marks
  it stale after a day. That changed tracked EDGAR summary files only through
  2026-10 filings. Those files were restored, not committed.

## 2. Method

**Windows.** Each target's windows are counted in its own valid CRSP
sessions:

```
... | estimation: 252 | test: h | guard: 42 | EDGAR announcement date
```

- **h, the segment's median hold.** It is re-measured from the sample's
  `tdays_to_close`:

  | segment | h (sessions) | calendar days |
  |---|---:|---:|
  | muni | 168 | 243.5 |
  | taxable | 95 | 140 |
  | equity | 116 | 168 |
  | BDC | 100 | 143 |

  The EDGAR note's 184.5-day median is announcement → completion across
  all 186 deals. Munis hold longer.
- **The guard.** 93 of 186 EDGAR dates are upper bounds, and announcement
  dates have been found up to 40 calendar days before EDGAR's
  (`EDGAR_EVENTS_2026-10-12.md` §3, §6). The 42-session guard was set from
  that, before any residual was computed.
- **Targets with too little history.** 13 of 167 lack 252 + h + 43
  sessions before the announcement (11 of them munis). They are counted,
  not shortened.

**Returns.** CRSP `ret`, which is total return.
- A target return that bridges a missing price is matched with the hedge's
  return over the same span.
- A bridge longer than CRSP's 10 periods is dropped and counted.

**The hedge ratio and the residuals.**
- **Hedge ratio.** A Dimson beta (lag 0 + lag 1), estimated on the
  estimation window. Thin CEF trading biases a lag-0 beta toward zero: for
  munis on MUB, the Dimson beta is 1.00 and OLS gives 0.80.
- **Time-series residual over the hold.** The sd of the hedged residual on
  non-overlapping 5-session blocks of the estimation window, × √(h/5).
  - Daily residuals × √h overstate it (906bp against 789bp for MUB),
    because the lead-lag noise cancels over a hold.
  - An independent re-computation with calendar-week returns and plain OLS
    gives **774bp** against 789bp, and beta 1.04 against 1.00 (scratch
    check, not shipped).
- **Out-of-sample residual.** e = R_T(test) − β_est · R_H(test): one number
  per target, taken over a test window as long as the median hold. Its
  cross-sectional sd is the like-for-like comparison with the dispersion of
  deal returns.
  - `cum` and `merger_pairs.window_return` agree on R_T(test) to 5e-9 on all
    81 muni targets.

**Candidates**, fixed before the first run:

| segment | candidates |
|---|---|
| muni | MUB, VTEB, TFI, HYD, SUB, SHM (short duration), MLN (long duration) |
| muni, state-matched | CMF (California, 17 targets) and NYF (New York, 10), matched by CRSP name |
| taxable | HYG, JNK, LQD, BKLN, PFF |
| equity | SPY, EFA, PFF |
| BDC | BIZD, HYG, BKLN, SPY |
| all | the deal's own acquirer, as the comparison |

**IEF and TLT were added after the first run** and are labelled post hoc
everywhere. That run found every muni ETF unshortable, which left Treasury
ETFs as the only shortable rate hedges for a muni target. They enter the gate
but never the "best" selection.

**NAV.**
- No daily NAV history for merged-away 2010–22 funds exists in the repo or
  in any source found (`docs/DATA.md` §3).
- **Form N-PORT** gives monthly total returns per fiscal quarter (Item
  B.5.a). For a closed-end fund they are computed under Form N-2's
  instruction, so they are NAV-based.
  - Public filings begin in 2019, so only 10 muni targets (three
    announcement groups, 2020-08 to 2021-09) have 9 or more NAV months in
    their windows. The median is 20 months.
  - Month 1 is the earliest month of the quarter. Every run re-tests this:
    pooled over 321 months, the same-month correlation with the segment ETF
    is 0.673, against −0.189 two months away.

## 3. Muni (92 deals; 81 targets measured)

The effect, re-measured: N 92 in 47 groups, median **+167bp**, mean +126bp,
**sd 336bp** (robust 303bp), clustered t **2.41**.

| hedge | targets | β (Dimson) | corr, 5-day | residual over hold | OOS residual sd | ÷ effect sd (TS / OOS) | variance removed | implied t | Alpaca 2026-10-15 | ADV today | short at $1m, % of ADV |
|---|---:|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| *unhedged* | 81 | — | — | 916bp | 1,039bp | 2.73 / 3.09 | — | — | | | |
| MUB | 81 | 1.00 | 0.49 | 789 | 751 | 2.35 / 2.24 | 26% | 0.94 | **hard_to_borrow** | $793m | 0.13% |
| TFI | 81 | 0.83 | 0.49 | 787 | 781 | 2.34 / 2.33 | 26% | 0.95 | **hard_to_borrow** | $43m | 1.92% |
| HYD | 80 | 0.56 | 0.45 | 792 | 754 | 2.36 / 2.24 | 25% | 0.94 | **hard_to_borrow** | $67m | 0.84% |
| MLN | 81 | 0.61 | 0.48 | 794 | 698 | 2.36 / 2.08 | 25% | 0.94 | **hard_to_borrow** | $4.4m | 13.7% |
| VTEB | 30 (2016+ windows) | 1.18 | 0.47 | 704 | 648 | 2.10 / 1.93 | 29% | 1.04 | **hard_to_borrow** | $580m | 0.20% |
| SUB | 81 | 1.27 | 0.37 | 840 | 977 | 2.50 / 2.91 | 16% | 0.89 | **hard_to_borrow** | $58m | 2.18% |
| SHM | 81 | 0.92 | 0.36 | 886 | 1,004 | 2.64 / 2.99 | 6% | 0.85 | **hard_to_borrow** | $13m | 6.89% |
| IEF *(post hoc)* | 81 | 0.33 | 0.28 | 851 | 991 | 2.54 / 2.95 | 14% | 0.88 | easy_to_borrow | $713m | 0.05% |
| TLT *(post hoc)* | 81 | 0.14 | 0.26 | 874 | 1,004 | 2.60 / 2.99 | 9% | 0.86 | easy_to_borrow | $2.6bn | 0.01% |
| *acquirer (comparison)* | 81 | 0.51 | 0.64 | 653 | 499 | 1.95 / 1.49 | 49% | 1.10 | 7 of 23 shortable (G1a) | | |

Notes on the table:
- **ADV and participation.** "ADV today" is Alpaca SIP dollar volume
  (median of 63 sessions). Participation is β × $1m ÷ ADV; at $100k it is a
  tenth of that.
- **Implied t.** 2.41 ÷ √(1 + k²), with k the time-series ratio. It is
  arithmetic that assumes the residual is independent of the effect, not
  a return.
- **The t-ceiling.** The largest k that would keep t ≥ 2 is **0.67**.
  Every hedge is above 2 on both measures.

**Like-for-like comparisons.**
- **VTEB against MUB.** On VTEB's 30 targets MUB leaves 710bp and VTEB
  704bp. The median ratio is 1.003. VTEB's lower figure in the table comes
  from its later windows, not from a better hedge.
- **The post-hoc Treasury hedges.** Against MUB on the same 81 targets, the
  ratio is 1.04 for IEF and 1.05 for TLT.
- **State-matched ETFs are no better than MUB on their own states.** CMF
  leaves 912bp against MUB's 886bp on 14 California targets. NYF leaves
  718bp against 646bp on 9 New York targets.

**By era** (H5; residual over the hold with MUB, then the acquirer as
hedge):

| era | targets | MUB | acquirer |
|---|---:|---:|---:|
| 2010–14 | 47 | 863bp | 743bp |
| 2015–19 | 19 | 601bp | 529bp |
| 2020–22 | 15 | 882bp | 749bp |

The calmest era still gives 601 ÷ 336 = **1.8×** the effect's dispersion.

**The NAV view** (N-PORT; 10 muni targets, 20 months median, on identical
months):

| hedge | NAV β | NAV corr | NAV residual over hold | price corr | price residual over hold | NAV ÷ price residual |
|---|---:|---:|---:|---:|---:|---:|
| MUB | 1.52 | 0.955 | 2.4% | 0.82 | 5.9% | 0.50 |
| VTEB | 1.61 | 0.975 | 1.8% | 0.84 | 5.5% | 0.42 |
| MLN | 0.93 | 0.968 | 2.1% | 0.82 | 5.7% | 0.39 |
| TFI | 1.34 | 0.912 | 3.3% | 0.80 | 5.9% | 0.63 |
| IEF *(post hoc)* | −0.19 | −0.12 | 7.9% | −0.19 | 9.2% | 0.87 |

**Reading:**
- **A muni ETF hedges a muni CEF's NAV well.** Only the price matters to the
  trade, and its residual is 2–3× the NAV residual: that gap is the
  discount.
- **Even the NAV-only residual sits at or above the 0.5 bar.** It is
  1.8–2.4% ÷ 3.36% = 0.54–0.71.
- **Muni NAVs did not move with Treasury ETFs** in these 2019–21 windows,
  which include March 2020.

## 4. Taxable, equity, BDC

**Taxable** (39 deals). The effect: median **+5bp**, mean +138bp, sd 750bp,
clustered t 0.98.

| hedge | targets | β | residual over hold | OOS sd | ÷ effect sd (TS / OOS) | Alpaca | short at $1m, % of ADV |
|---|---:|---:|---:|---:|---|---|---:|
| BKLN | 26 | 2.05 | 641bp | 1,466 | 0.86 / 1.96 | easy | 1.28% |
| PFF | 39 | 0.95 | 647 | 1,142 | 0.86 / 1.52 | easy | 1.14% |
| HYG | 39 | 1.07 | 671 | 1,213 | 0.90 / 1.62 | easy | 0.04% |
| JNK | 39 | 1.03 | 673 | 1,189 | 0.90 / 1.59 | easy | 0.45% |
| LQD | 39 | 0.44 | 784 | 1,573 | 1.05 / 2.10 | easy | 0.01% |
| *acquirer* | 39 | 0.69 | 501 | 527 | 0.67 / 0.70 | 14 of 18 (G1a) | |

**Equity** (33 deals). The effect: median +15bp, sd 617bp, t −0.16.

| hedge | residual over hold | ÷ effect sd (TS / OOS) | Alpaca |
|---|---:|---|---|
| SPY | 829bp | 1.34 / 1.74 | easy |
| EFA | 830bp | 1.35 / 1.37 | easy |
| PFF | 892bp | 1.45 / 1.32 | easy |
| *acquirer* | 768bp | 1.24 / 1.10 | |

**BDC** (3 deals). Two targets were measured. The residual is about 1,360bp
against an effect sd of 118bp. BIZD is `hard_to_borrow`. Nothing can be read
from N = 2.

## 5. Shortability, borrow cost and capacity

**Alpaca, 2026-10-15 20:38–20:43 UTC** (`shortable` / `easy_to_borrow`):

| status | symbols |
|---|---|
| **hard to borrow, not shortable** | **MUB, VTEB, TFI, HYD, SUB, SHM, MLN, CMF, NYF**, BIZD |
| easy to borrow | HYG, JNK, LQD, BKLN, PFF, SPY, EFA, IEF, TLT |

- The 2026-10-12 read on file agrees for every symbol it covers: MUB not
  shortable; HYG, LQD, PFF, BKLN, SPY, EFA, IEF and TLT easy.
- The spec's own borrow-reopen rule asks for **20 consecutive sessions**
  shortable and easy (`ops/specs/cef_discount.frozen.json`
  `_universe_note`). The muni ETFs have no session at all on file.

**IBKR, as a second source and context only** (the book cannot borrow
there). Each figure is the fee in %/yr, then the shares available, on
2026-10-13:

| ETF | fee, %/yr | shares available |
|---|---:|---:|
| MUB | 5.51 | 1.0m |
| VTEB | 4.55 | 1.5m |
| TFI | 9.34 | 100k |
| HYD | 18.20 | 55k |
| SUB | 5.67 | 50k |
| SHM | 8.44 | 600k |
| MLN | 4.03 | 60k |
| CMF | 8.75 | 300k |
| NYF | 6.77 | 30k |
| HYG | 0.57 | 6.0m |
| JNK | 0.89 | 5.9m |
| BKLN | 0.55 | 950k |
| PFF | 2.11 | 500k |
| SPY | 0.25 | 5.1m |
| IEF | 0.28 | 2.6m |

**Muni ETF borrow is scarce and dear everywhere.** This is arithmetic on [S]
fee levels, not a measured cost:
- MUB at 5.51%/yr over the muni median hold of 243.5 days is about **368bp**
  of hedge notional at β 1.0.
- VTEB at 4.55% × 1.18 is about 358bp.
- Either is more than twice the +167bp gross effect.

**Capacity.**
- **Today, the hedge's liquidity is not the binding limit.** MUB and VTEB
  turn over $793m and $580m a day, so a $1m long's hedge is 0.13–0.20% of
  ADV.
- **Before 2023 it would have been.** MUB's median ADV inside the windows
  was $21.6m (minimum $8.5m), so the same hedge would have been about 4.6%
  of ADV.
- **The target is the binding constraint** (context: E1's own capacity,
  whatever the hedge). The muni targets' median 63-day ADV before
  announcement was **$145k**. A $100k long is about 0.7 of a day's volume,
  and $1m is about 7 days.

## 6. Against the acquirer-leg hedge (the deals where it was shortable)

The comparison runs on pre-announcement windows with the same method.
"Shortable" is G1a's H3: today's Alpaca flag for an acquirer that is still
the same fund. It is the only shortability measure that exists for these
deals.

| segment | sample | targets | best ETF residual | acquirer residual | ETF ÷ acquirer (median) | ETF lower for | OOS sd, ETF / acquirer |
|---|---|---:|---:|---:|---:|---:|---|
| muni | all | 81 | TFI 787bp | 653bp | 1.09 | 17% | 781 / 499 |
| muni | acquirer shortable at Alpaca today | 12 | TFI 741bp | 656bp | 1.01 | 33% | 641 / 423 |
| taxable | all | 26 | BKLN 641bp | 441bp | 1.42 | 19% | 1,466 / 570 |
| taxable | acquirer shortable today | 12 | BKLN 737bp | 616bp | 1.18 | 42% | 932 / 428 |
| equity | acquirer shortable today | 17 | SPY 834bp | 819bp | 1.09 | 35% | 1,086 / 657 |

**Inside a deal the acquirer is a different hedge.** The target converts
into acquirer shares at the NAV ratio, so the pair's residual collapses:
- The muni acquirer pair's own dispersion over the deal is **336bp**,
  measured on the whole segment and computed on no subset.
- That is about half the acquirer's pre-announcement residual, and well
  under half the ETF's.
- **No ETF can share that tie.**

## 7. The gate, as proposed, and its verdict

**Proposed rule, per segment.** A hedge passes when all three hold:
- **(a) Buildable.** Alpaca shows it `shortable` and `easy_to_borrow` today
  and on every earlier read on file.
- **(b) Capacity.** At a $1m long, β × $1m is at most **1%** of the hedge's
  dollar ADV today.
- **(c) Residual.** The median time-series residual over the segment's
  median hold, **and** the cross-sectional sd of the out-of-sample
  residuals, are each at most **X = 0.5** of the segment's deal-return sd.
  The sd is re-measured at run time.

A segment passes if any hedge passes.

**Why 0.5.**
- If the residual is independent of the effect, it inflates the trade's
  dispersion by √(1 + X²), which is 12% at X = 0.5.
- The most lenient defensible bar is the one that keeps the re-measured
  clustered t at or above E1's kill line of 2. For munis that is **0.67**
  (`t_ceiling_x`).

**Verdict.**

| segment | (a) buildable | (b) capacity at $1m | (c) residual, TS / OOS vs 0.5 | verdict |
|---|---|---|---|---|
| **muni** | **no muni ETF**; IEF and TLT yes (post hoc) | MUB, VTEB, HYD and IEF/TLT yes; TFI, SUB, SHM, MLN no | **2.10–2.64 / 1.93–2.99**, all fail, and all fail 0.67 | **FAIL** |
| taxable | all five | HYG, JNK, LQD yes; BKLN, PFF no | 0.86–1.05 / 1.52–2.10, all fail | **FAIL** |
| equity | SPY, EFA, PFF | SPY, EFA yes | 1.34–1.45 / 1.32–1.74, all fail | **FAIL** |
| BDC | HYG, BKLN, SPY (not BIZD) | HYG, SPY | about 11, fail (N = 2) | **FAIL** |

**What would change it.**
- **For munis, a hedge that removes the CEF discount.** It would need a
  residual of no more than 168bp over 168 sessions (0.5 × 336bp). Nothing
  measured here comes within a factor of 4 of that.
- **The candidates:**
  - a basket of other muni CEFs: not shortable at Alpaca either (G1a: 7 of
    23 muni acquirers);
  - the acquirer itself, inside the deal, which is E1 as designed.
- An ETF cannot remove the discount: on the N-PORT subset, the price
  residual is 2–3× the NAV residual.

**Recommendation.**
- Mark the ETF-hedged variant of E1 **failed at the hedge gate (zero
  trials)**. Do not spend EVENTS 0→1 on it.
- E1 as designed stays blocked by G1a.
- Recording both is the team lead's call.

## 8. Findings outside the question

- **Every muni ETF tried is `hard_to_borrow` at Alpaca.** That covers
  national, short, long, high-yield and state funds. It matters beyond E1.
  - Any muni hedge or muni short on this broker is unavailable today.
  - XASSET X1 already allowed shorts "only where shortable that day". MUB
    has never been shortable on a read on file.
- **Form N-PORT is a usable NAV-return source for merged-away CEFs from
  2019.** No `data/` panel holds these funds.
  - Each public NPORT-P carries the quarter's three monthly NAV total
    returns.
  - The parser (`parse_nport_returns`) and the month-order check are in
    the reproducer.
- **The target's own liquidity caps E1 at any hedge.** The muni target
  median is $145k a day before announcement.
- **Muni NAVs were uncorrelated with Treasury ETFs** in 2019–21 windows.
  Monthly corr with IEF is −0.12, with TLT −0.11. A Treasury hedge for muni
  credit is a hedge in name only.

## 9. Gaps (stated, not filled)

- **The NAV view covers 10 muni targets in 3 announcement groups.** Their
  windows (2019–21) include March 2020. There is no NAV source for 2010–18
  windows, so those deals are measured on price only.
- **The pre-announcement residual is a proxy for the in-deal residual of
  an ETF-hedged position.** In a deal, the target's discount converges on
  the acquirer's, which still floats. The proxy assumes a similar fund's
  discount moves about as much. It was not measured inside the deal: that
  would be the trial.
- **Alpaca flags have two reads at most** (2026-10-12 and 2026-10-15); the
  muni ETFs other than MUB have one. Paper cannot test locates (G1a §5), so
  a live account might differ [U].
- **"Best" is an in-sample choice among correlated candidates.** The top
  five muni ETFs are tied within 1%, so the choice does not move the
  verdict.
- **Targets in one announcement group share windows.** Their residuals are
  correlated, so the cross-sectional sd is not over independent
  observations. Both residual measures fail by a wide margin either way.
- **IEF and TLT were added after the first run.** They fail too.
- **The second Alpaca route is the MCP server's `get_asset`**, whose
  account was not identified. It is a cross-check, not the gate's input.

## 10. Files

- `scripts/events/e1_etf_hedge_gate.py`: the gate.
- `scripts/events/tests/test_e1_etf_hedge_gate.py`: 20 tests, run under
  `scripts/events/tests`.
  - Eight were checked to fail against a broken rule: no guard; the hedge
    return taken over one day instead of the target's span; the test
    window's own beta; the N-PORT month order reversed; "at most X" made
    strict; `easy_to_borrow` ignored; earlier reads ignored; a long CRSP gap
    compounded.
- **Tracked output:** `results/events/e1_etf_hedge_summary_2026-10-15.json`.
- **Gitignored:** `results/events/e1_etf_hedge_detail.csv` and
  `results/events/_cache_e1_hedge/`.
- Sources: `docs/REFERENCES.md` §12w.
