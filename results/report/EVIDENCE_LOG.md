# Evidence log

**The dated record a research report on this desk will be written from.** One entry per result,
ruling, release, incident or live-P&L day, from the desk's first commits (tag `pre-clean-slate`)
to today. What the pack is and the report skeleton the `supports:` field points at:
`results/report/README.md`. The format is checked by `scripts/report/evidence_log.py`; the
reproducer for the pack's figures is `python3 -m scripts.report.build_pack`.

**How it is appended to.**
- **Append-only.** A new entry goes at the end, in the same commit as the change it records
  (`CLAUDE.md`, research rules; `.claude/rules/report.md`). Live days are appended by
  `python3 -m scripts.report.snapshot_live` (ids `E-<date>-90` for the core, `-91` for C4).
- **Corrections are dated, never silent edits.** An existing entry is never changed or deleted.
  A correction is a new entry (`kind: correction`) giving the old and the new figure and what it
  supersedes. `build_pack.py` and `snapshot_live.py` refuse a log whose existing entries changed.
- **The backfill of 2026-11-03** (everything before the first live-day entry) was copied from
  the named files by the pack's agents, file by file, and is in date order; later entries are in
  the order they were appended.

**Tags on every figure.**
- `[S]` copied verbatim from the named committed file, not re-run by the pack (the default);
- `[V]` the named file itself labels the figure verified or re-run, or `build_pack.py` re-derived it
  from committed data;
- `[U]` the source labels it uncertain, or two sources disagree. Then both figures are given, each
  tagged `[U]`, and the entry says which is the record (`docs/SYSTEM.md` §0, order of authority).

**Eras.** `HISTORY` is everything before the 2026-09-28 clean slate, read from tag
`pre-clean-slate` (f6d155f) or `ibkr-final` (db795a9): **provenance, never evidence of what is
true now** (`CLAUDE.md`). Where a later correction superseded a HISTORY figure, both are shown,
dated. `ALPACA` is 2026-09-28 onward.

**Sources.** `path @ commit` is the file the figures were copied from and its last commit on
`main` (or the tag's commit). A branch file not yet on `main` says so. A live day cites the VM
pull it came from (`pull:<sha12>`, recorded in `data/live/<book>/pulls.csv`), because the commit
that adds it does not exist when it is written.

## Entries

### E-2026-07-28-01 · credit_rv, the first family: a real cross-sectional signal on credit ETFs that was far too small to pay for its own execution
- kind: result
- era: HISTORY
- date: 2026-07-28
- figures:
  - signal information coefficient (h=1..20) −0.076 to −0.082, t = −12 to −13 [S]
  - gross Sharpe, costs switched off +0.56 (CAGR +5.15% at 7.5% vol) [S]
  - net Sharpe, realistic costs −0.62 (CAGR −3.49%) [S]
  - net edge per trade at |s|≥2, ex-COVID +2.51bp, t = 3.71 [S]
  - trials consumed 82 against a pre-registered budget of 60 [S]
- source: `pre-clean-slate:results/credit_rv/FINDINGS.md` @ `f6d155f`
- supports: §6
- status: superseded by E-2026-07-30-01 (2026-07-30)

### E-2026-07-30-01 · credit_rv was killed at its sealed holdout: the gross edge was negative before costs (D1)
- kind: kill
- era: HISTORY
- date: 2026-07-30
- figures:
  - gross edge NEGATIVE before costs (−0.19%/yr) [S]
  - sealed holdout net SR −1.44, t −2.29 [S]
  - holdout n_obs 644; spec_id credit_rv.v1.20260730 [S]
  - credit_rv got 141 trials and a sealed holdout before being killed [S]
- source: `pre-clean-slate:results/credit_rv/HOLDOUT_OPENED.json` @ `f6d155f`; `docs/RESEARCH_STATE.md` @ `5dbd739`; `pre-clean-slate:results/AUDIT_2026-07-31.md` @ `f6d155f`
- supports: §6
- status: provenance only

### E-2026-07-30-02 · E1 (HYG vs JNK premium/discount reversion) died because the dislocation collapsed, not because the mechanism was wrong; its band form went to WATCH (D1 reclassified D5)
- kind: kill
- era: HISTORY
- date: 2026-07-30
- figures:
  - relative-premium σ_eq IS 2007–2019 65.2bp → OOS 2020–2023 14.2bp [S]
  - gross bp/turn IS 3.72 → OOS −0.15; net SR IS +0.64 → OOS −6.65 [S]
  - headline net conservative Sharpe −0.17 in-sample, −3.97 out-of-sample [S]
  - band form: Sharpe held 0.75→2.64→0.41→0.48 across eras while return fell 2.54%→0.05%/yr [S]
- source: `pre-clean-slate:results/e1/E1_RESEARCH_NOTE.md` @ `f6d155f`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: provenance only

### E-2026-07-30-03 · Night one found that HYG's published NAV is smoothed and that the ETF "opportunity" shrank with the smoothing: the stale-price well is dry in ETFs
- kind: result
- era: HISTORY
- date: 2026-07-30
- figures:
  - today's published-value change predicts tomorrow's +0.388; price change −0.005 [S]
  - published-value volatility 6.05% vs the fund's 9.51% [S]
  - smoothing and apparent opportunity by era: 2007–10 +0.580 / 187.9bp; 2011–14 +0.427 / 14.0bp; 2015–18 +0.303 / 5.6bp; 2023–26 +0.148 / 3.8bp [S]
- source: `pre-clean-slate:_archive/docs/HOW_WE_GOT_HERE.md` @ `f6d155f`
- supports: §3, §6
- status: provenance only

### E-2026-07-30-04 · S1-as-specified was killed: cross-issuer bond-price disagreement carries no information because every issuer buys from the same vendor (D1)
- kind: kill
- era: HISTORY
- date: 2026-07-30
- figures:
  - median disagreement 0.09bp, p99 1.03bp across 1,132 shared bonds [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `pre-clean-slate:_archive/docs/HOW_WE_GOT_HERE.md` @ `f6d155f`
- supports: §6
- status: provenance only

### E-2026-07-30-05 · S3 forced flow: index deletion of fallen angels causes real, temporary price pressure, but only as a rare crisis-regime sleeve (WATCH, D6)
- kind: result
- era: HISTORY
- date: 2026-07-30
- figures:
  - 16,388 bonds, 2003 to 2025 [S]
  - −424bp trough, t −17.5, 82–85% reversal with dropouts carried flat [S]
  - the first run showed a 414% recovery, caused by survivorship and broken event time [S]
  - crisis regime (>400 migrations/mo) fired 4× in 273 months; 104 migrating bonds vs 350 holdings is 5× noise [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `pre-clean-slate:_archive/docs/HOW_WE_GOT_HERE.md` @ `f6d155f`
- supports: §6
- status: provenance only

### E-2026-07-30-06 · S3-wrapper was killed: the fallen-angel ETF expression was a credit-quality premium in costume, and the unconditional pair beat the signal (D4)
- kind: kill
- era: HISTORY
- date: 2026-07-30
- figures:
  - alpha t 1.98 (need 3.0), HY beta −0.163, IG beta +0.123 (need ≤0.10) [S]
  - unconditional pair (0.37) BEATS signal-conditioned (0.03–0.24) [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: provenance only

### E-2026-07-30-07 · raw-flow-z was killed: an ETF creation/redemption z-score is a precise zero, and the Treasury control is equally flat (D1)
- kind: kill
- era: HISTORY
- date: 2026-07-30
- figures:
  - 28,025 obs, all |t|<0.8 [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: provenance only

### E-2026-07-30-08 · Benchmarks and a random null trader were run through one accounting path; the null trader lost exactly its costs, so the accounting does not invent profit
- kind: method
- era: HISTORY
- date: 2026-07-30
- figures:
  - null trader lost 20.68% a year against a modelled cost of 21.2% a year [S]
  - before-cost Sharpe of the null trader −0.77 before the financing fix, −0.39 after [S]
- source: `pre-clean-slate:_archive/docs/HOW_WE_GOT_HERE.md` @ `f6d155f`
- supports: §2
- status: provenance only

### E-2026-07-31-01 · The 21.2%/yr cost headline was a full-sample artefact of 2007–14 ETF illiquidity; current-era cost is 1.73bp per trade, and fixing it rescued no dead signal
- kind: correction
- era: HISTORY
- date: 2026-07-31
- figures:
  - 2007–10 13.91bp/trade, 42.5%/yr; 2023–26 1.73bp/trade, 5.9%/yr [S]
  - current-era cost 1.73bp/trade, 3.7× cheaper than the full-sample 6.36bp [S]
  - ANGL modelled 4.334bp vs measured 1.735bp, over-charged by exactly 2.5× [S]
  - half-spread modelled/measured 1.00–1.02 on 7 of 8 names [S]
- source: `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/HOW_WE_GOT_HERE.md` @ `f6d155f`
- supports: §2, §6
- status: provenance only

### E-2026-07-31-02 · single-fund-PD was killed: wide ETF premium/discount dispersion is NAV staleness, and trading it fades price discovery (D1)
- kind: kill
- era: HISTORY
- date: 2026-07-31
- figures:
  - dispersion EMB 28.6bp, ANGL 23.3bp, viability 6-19x cost [S]
  - PD predicts the NAV revision at t=15-24; where it predicts price the sign is positive (EMB +15.3, LQD +11.7, HYG +10.0) [S]
  - Treasury controls mid->mid t=-15..-18 [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: provenance only

### E-2026-07-31-03 · leadlag was killed: thin-wrapper lag was non-synchronous trading measured on a price that cannot be traded (D1)
- kind: kill
- era: HISTORY
- date: 2026-07-31
- figures:
  - raw mean t by group IG_long 17.7, HY 12.4, MBS 11.7, EM 11.0, PREF 9.5 on (H+L)/2 [S]
  - executable close-to-close overall mean t 5.20 -> −0.50 [S]
  - Treasury CONTROL +3.48, higher than every credit group but one [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: provenance only

### E-2026-07-31-04 · nport-trace-nav was infeasible: the bonds that print on TRACE each day cover too little of a fund and are selected for news (D7)
- kind: kill
- era: HISTORY
- date: 2026-07-31
- figures:
  - daily TRACE coverage of HYG's N-PORT weight 17-30% and declining (26.5% in 2020 -> 17.4% in 2022) [S]
  - N-PORT 136,268 rows, 95.3% CUSIP overlap vs the live iShares file [S]
  - fair_val_level degenerate: 135,850/135,870 corporate bonds are Level 2 [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: provenance only

### E-2026-07-31-05 · dealer-constraint was killed: no credit name responds to primary-dealer inventory, and the Treasury control shows the same magnitude (D1)
- kind: kill
- era: HISTORY
- date: 2026-07-31
- figures:
  - ZERO credit names significant at any horizon 5-63d (best t=1.59, ANGL 42d) [S]
  - UST control mean t 0.95-1.50 [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: provenance only

### E-2026-07-31-06 · short-pressure was killed: crowded credit hedges do not reverse, and the rates comparison group scores higher (D1)
- kind: kill
- era: HISTORY
- date: 2026-07-31
- figures:
  - credit mean t 0.28/0.03/-0.20/-0.42 at h=1/3/5/10d; 2/10 names significant at the best horizon [S]
  - RATES comparison group 1.01/0.92/1.05/0.45 [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: provenance only

### E-2026-07-31-07 · pair-reversion was killed on arithmetic: the 22 pairs diversified, but costs do not, and the book could not reach the mandate's vol (D2 + capacity)
- kind: kill
- era: HISTORY
- date: 2026-07-31
- figures:
  - mean pairwise correlation +0.027, combined GROSS Sharpe +1.03, net -0.16 [S]
  - combined vol 0.37%; the 12% mandate needs 32.8x leverage against a ~2x Reg T ceiling [S]
  - capacity chain: all 22 pairs achievable vol 0.65%; best subset (both legs >$100M ADV) net SR +0.03 at 4.85% vol, ~0.15%/yr [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`
- supports: §5, §6
- status: provenance only

### E-2026-07-31-08 · The trial counters as they stood when the ETF search was stopped: LEGACY carried the ETF work, and each new data source got its own counter
- kind: counter
- era: HISTORY
- date: 2026-07-31
- figures:
  - LEGACY 162 (counter table, the file's canonical record) [`pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md`]; the record, because the file states the counter table is canonical and its prose is not [U]
  - "Global trial count: 156" and "the legacy counter (156)" (same file's header and prose); `results/credit_rv/trial_log.csv` "holds 156 numbered trials" [`pre-clean-slate:_archive/docs/SUMMER_2026_SUMMARY.md`]; not the record [U]
  - NPORT 1, BREADTH 4, DISP 3, DEALER 1, MBS 0, CEF 18, POSITIONING 1 [S]
  - "Thirteen mechanisms tested. Twelve dead."; the luck threshold had risen to about 3.2; our best real result was 0.37 [S]
- source: `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/SUMMER_2026_SUMMARY.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/HOW_WE_GOT_HERE.md` @ `f6d155f`
- supports: §5, §6
- status: provenance only

### E-2026-07-31-09 · The pivot: "credit" had silently meant "credit ETFs"; the instruction "it has to be credit" opened closed-end funds
- kind: ruling
- era: HISTORY
- date: 2026-07-31
- figures:
  - none (a ruling)
- source: `pre-clean-slate:_archive/docs/HOW_WE_GOT_HERE.md` @ `f6d155f`
- supports: §3, §6
- status: provenance only

### E-2026-07-31-10 · The CEF premise was checked first: credit CEF discounts are about 150× the ETF gap, and the ETF decomposition reverses — the discount predicts price, not NAV
- kind: result
- era: HISTORY
- date: 2026-07-31
- figures:
  - credit CEF discounts average −3.16% with sd 5.95%, p5 −11.88%, p95 +7.11%, roughly 150x the ETF gap [S]
  - discount → NAV revision: ETF t = +15 to +24 (artifact); CEF t = +1.72 (weak) [S]
  - discount → PRICE: ETF ~0; CEF t = −1.75 mean, 6/18 at t<−2 [S]
  - joint regression against trailing 21d price return: 11/18 funds keep a significant discount effect (mean joint t = −3.16) [S]
- source: `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/HOW_WE_GOT_HERE.md` @ `f6d155f`
- supports: §2, §3, §6
- status: provenance only

### E-2026-07-31-11 · The first CEF sleeve was the first candidate to pass Test 7 (not a market exposure); its modern-era alpha t missed the 3.0 gate, and the gate was lowered to 2.0 on instruction
- kind: result
- era: HISTORY
- date: 2026-07-31
- figures:
  - long 4 cheapest / short 4 richest, 5d hold: gross SR 1.06, net SR 0.76, CAGR 2.69%, vol 3.57%, maxDD −7.3% [S]
  - Test 7 full 2005–26: R² 0.005, alpha +2.68%/yr, t +3.11, 5/5 factor betas pass [S]
  - modern 2019–26: alpha +5.10%/yr, t +2.58, FAIL against a 3.0 gate [S]
  - era net SR 1.17 (2010–14), 0.62 (2015–19), 1.87 (2020–22), 0.13–0.32 (2023–26) [S]
  - opportunity narrowed: discount sd 15.22% → 9.52%, top-bottom spread 27.48% → 22.47% [S]
- source: `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`
- supports: §3, §6
- status: provenance only

### E-2026-07-31-12 · Sizing up into dislocation was backwards: the strategy is best in calm markets, so vol targeting replaced dispersion sizing
- kind: result
- era: HISTORY
- date: 2026-07-31
- figures:
  - net Sharpe by quintile of discount dispersion, calm → dislocated: 1.24 / 0.59 / 0.80 / -0.23 / 0.68 [S]
  - sizing up into dislocation produced 2008: -12.9% return at 35.8% vol with a -31.5% drawdown [S]
  - universe-wide flat gross 0.97 / net 0.73 → vol-target 6% gross 1.09 / net 0.72; turnover 24 -> 29/yr [S]
  - maxDD -27.1% → -15.4% (spec table) [`pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md`]; the record, because it is the measured row for the vol-targeted spec [U]
  - "Vol targeting cut full-sample drawdown −27% → −12%" [`pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md`; also HOW_WE_GOT_HERE §4.6]; not the record [U]
- source: `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/HOW_WE_GOT_HERE.md` @ `f6d155f`
- supports: §3, §5, §6
- status: provenance only

### E-2026-07-31-13 · Hard group (muni) neutrality was measured and rejected: within-group demeaning throws away most of a thin cross-section
- kind: kill
- era: HISTORY
- date: 2026-07-31
- figures:
  - group-neutral, flat: gross 0.97 → 0.82, net 0.73 → 0.57 [S]
  - with only 18 funds across 5 groups, several groups hold 2-3 members [S]
  - later nextgen reading (GN-N1): traded turnover 1.5002× the reference, stress cap breached on 83.3% of last-12m days [S]
- source: `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`; `docs/RESEARCH_STATE.md` @ `5dbd739`; `results/cef/PREREG_GROUP_CAP_2026-09-16.md` @ `6217c96`
- supports: §6
- status: provenance only

### E-2026-07-31-14 · Sizing up on |z| was rejected: every threshold above zero lowers the Sharpe, so the edge is spread across the cross-section
- kind: kill
- era: HISTORY
- date: 2026-07-31
- figures:
  - every |z| threshold above zero lowers the Sharpe (0.81 → 0.40 → 0.29 → 0.27) [S]
- source: `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: provenance only

### E-2026-07-31-15 · How the names were chosen: a credit-only CEF list, a first cut on today's ADV that was then rebuilt point-in-time, and 17 names frozen at a $3m ADV screen
- kind: method
- era: HISTORY
- date: 2026-07-31
- figures:
  - staging universe is credit ONLY: municipal, high yield, bank loan, EM debt, and multi-sector credit; no equity or covered-call funds [S]
  - closed-end funds: 44 funds, 265,615 price rows, 232,799 value rows, back to 1986 [S]
  - the first version picked 18 funds using today's trading volumes; point-in-time rebuild improved net Sharpe 0.72 → 0.82 (median 8 eligible, up to 25) [S]
  - specification under test: 17 credit CEFs, PIT-eligible, ADV >= $3m evaluated per date [S]
- source: `pre-clean-slate:scripts/cef/stage_cef.py` @ `f6d155f`; `pre-clean-slate:_archive/docs/HOW_WE_GOT_HERE.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/RESEARCH_AND_METHODOLOGY.md` @ `f6d155f`; `pre-clean-slate:results/cef/HOLDOUT_PREREG.md` @ `f6d155f`
- supports: §2, §5
- status: provenance only

### E-2026-07-31-16 · The CEF search was stopped at ten specifications, with a deflated Sharpe that passed only because the trial count was recorded as ten
- kind: result
- era: HISTORY
- date: 2026-07-31
- figures:
  - SEARCH STOPPED at 10 specifications; DSR haircut at N=10 is sqrt(2*ln 10) = 2.15 [S]
  - deflated Sharpe 0.956, roughly a 95.6% probability the edge is real [S]
  - 0.956 was computed at N=10 by a validate.py that hard-coded N_SPECS_TRIED = 10 [S]
- source: `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/RESEARCH_AND_METHODOLOGY.md` @ `f6d155f`; `pre-clean-slate:ops/specs/cef_discount.frozen.json` @ `f6d155f`
- supports: §6
- status: superseded by E-2026-09-09-01 and E-2026-09-10-01 (2026-09-10)

### E-2026-07-31-17 · The CEF book was deployed to IBKR paper at $500k on a validation battery that later failed to reproduce
- kind: release
- era: HISTORY
- date: 2026-07-31
- figures:
  - evidence block: gross_sharpe 1.26, net_sharpe 0.82, vol_pct 6.0, cagr_pct 4.85, max_dd_pct -12.0 [S]
  - purged_walkforward "9/9 blocks positive, median 1.12, worst 0.01"; block_bootstrap_p_sr_le_0 0.0; deflated_sharpe 0.956; test7_alpha_t 3.11 [S]
  - known weaknesses: kurtosis 41.2; most recent walk-forward block 0.05; 2023-26 era net Sharpe 0.30 [S]
  - deployed at $751,463 gross, long $375,678 / short $375,784, net -$106 [S]
- source: `pre-clean-slate:_archive/ops/_archive/cef_discount.v5.20260731.frozen.json` @ `f6d155f`; `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`
- supports: §2, §4, §5
- status: superseded by E-2026-09-10-01 (2026-09-10)

### E-2026-07-31-18 · Day one: plain market orders rested overnight and filled pre-market, costing far more than the modelled spread; the order type was changed to MOC
- kind: incident
- era: HISTORY
- date: 2026-07-31
- figures:
  - traded $682,351, slippage $6,405, realised 0.94% vs modelled ~0.10%, ratio 9.4x [`pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md`]; $6,405 / $682,351, not the record [U]
  - 2026-07-31 overnight market orders realised 100.5bp against a 32.6bp breakeven [`pre-clean-slate:results/cef/ALPHA_AUDIT_2026-09-05.md`]; the record, the figure CLAUDE.md rule 3 cites; it is the share-weighted mean of the 16 rows [U]
  - 16 fills, 120.6bp realised vs 15.5 modelled [`pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md`]; the simple mean of the 16 rows, not the record [U]
  - priced at decision prices +$50 (+0.01%); at fills −$7,350; difference $7,399 [S]
  - fills at 07:27 ET; worst names BIT 2.87%, DSL 2.62%, PFN 2.27% [S]
- source: `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`; `pre-clean-slate:results/cef/ALPHA_AUDIT_2026-09-05.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md` @ `f6d155f`
- supports: §4, §5
- status: provenance only

### E-2026-07-31-19 · Standing instruction: the paper book runs observe-only; the pre-committed kill rule became a human checklist and automatic drawdown suspends were raised to 99%
- kind: ruling
- era: HISTORY
- date: 2026-07-31
- figures:
  - original rule: KILL if, after 60 live sessions, (a) live net Sharpe < 0.0; (b) realised slippage exceeds modelled by more than 2x for 5 consecutive sessions; (c) top-bottom discount spread below 12% (half its current 22.5%) [S]
  - every book-level drawdown suspend is raised to 99% [S]
- source: `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`
- supports: §5
- status: provenance only

### E-2026-07-31-20 · The 2026-07-31 audit tried twice to kill the alpha as a muni-vs-taxable bet and failed; the signal is a breadth machine, not a timing machine
- kind: result
- era: HISTORY
- date: 2026-07-31
- figures:
  - live book 66% net short municipal CEFs and 57% net long multi-sector taxable; full-sample mean net muni −5.1% of gross [S]
  - Test 7 set alpha +8.21%/yr, t +5.67; + MUB, HYD, duration spread +8.83, t +5.67 [S]
  - all five CEF group factors: alpha +7.63%/yr, t +5.90, R² 0.0057; every group beta ≤ 0.025 [S]
  - IC 0.040 at 1d rising to 0.103 at 42d; IC/√h half-life 31.1 trading days; n = 41,000–42,000 fund-days per horizon [S]
- source: `pre-clean-slate:results/AUDIT_2026-07-31.md` @ `f6d155f`
- supports: §3, §6
- status: provenance only

### E-2026-07-31-21 · The audit diagnosed that the headline backtest entered at a price that did not exist (shift(1)), predicted its cost, and left it unfixed
- kind: correction
- era: HISTORY
- date: 2026-07-31
- figures:
  - gross SR shift(1) 1.26 → shift(2) 0.95 (−25%) [S]
  - net SR at hold=5 0.82 → 0.51 (−38%) [S]
  - the honest expected net Sharpe of the running configuration is 0.51 [S]
- source: `pre-clean-slate:results/AUDIT_2026-07-31.md` @ `f6d155f`
- supports: §2, §6
- status: superseded by E-2026-09-10-01 (2026-09-10)

### E-2026-07-31-22 · Specification, code and optimum disagreed on the holding period: the spec said 5 days, the sleeve traded every session, and the measured optimum was 2
- kind: result
- era: HISTORY
- date: 2026-07-31
- figures:
  - net SR at shift(2), what MOC gets: hold 1 0.62, hold 2 0.73, hold 3 0.70, hold 5 0.51 [S]
  - turn/yr: hold 1 52.8, hold 2 36.8, hold 5 24.2 [S]
- source: `pre-clean-slate:results/AUDIT_2026-07-31.md` @ `f6d155f`
- supports: §2, §5
- status: superseded by E-2026-09-06-04 (2026-09-06)

### E-2026-07-31-23 · Order stacking during the fix: repeated armed runs queued orders unseen from fresh client ids, which established that the trade phase is not idempotent
- kind: incident
- era: HISTORY
- date: 2026-07-31
- figures:
  - reqAllOpenOrders() finally showed 79 PreSubmitted MOC orders [S]
  - end state: one clean set of 16 MOC orders, $27,790 notional [S]
- source: `pre-clean-slate:results/AUDIT_2026-07-31.md` @ `f6d155f`
- supports: §5
- status: provenance only

### E-2026-07-31-24 · The graveyard's two patterns: most deaths were stale-price artefacts, the next most common a control group scoring as well as the treatment
- kind: method
- era: HISTORY
- date: 2026-07-31
- figures:
  - six were stale-price artifacts: credit_rv (bid-ask bounce), S1 (one vendor prices every issuer), single-fund-PD (NAV staleness, sign positive), leadlag (non-synchronous trading), E1, nport-trace-nav [S]
  - three lost to their own control group: dealer-constraint, short-pressure, S3-wrapper [S]
  - two died on arithmetic: pair-reversion needed 32.8× leverage [S]
  - the well is dry in ETFs because APs arbitraged it (188bp → 3.8bp); CEF discount works because no AP mechanism exists there [S]
- source: `pre-clean-slate:results/AUDIT_2026-07-31.md` @ `f6d155f`; `.claude/skills/graveyard/SKILL.md` @ `20e9755`; `docs/HISTORY.md` @ `bdbe563`
- supports: §3, §6
- status: provenance only

### E-2026-07-31-25 · A distribution-cut filter was rejected: cuts do re-rate the discount, but the damage arrives at 63 days and excluding cut funds costs more breadth than it saves
- kind: kill
- era: HISTORY
- date: 2026-07-31
- figures:
  - 11,988 distributions across 44 funds, 1987–2026, of which 1,145 cuts [S]
  - cuts widen the discount −0.580pp at t+60; raises tighten +0.557 [S]
  - cut-minus-no-cut excess return at 63d −0.486%, t −2.91; at 5–21d |t| < 0.8 [S]
  - only one of eight variants beats baseline (+0.83 → +0.88 shift2), chosen after looking at eight [S]
  - CEF counter +9 [S]
- source: `pre-clean-slate:results/cef/DIST_CUT_NOTE.md` @ `f6d155f`
- supports: §6
- status: provenance only

### E-2026-07-31-26 · A Kalman state-space estimator was built and lost to a shorter rolling window; z_window 252 → 63 was recommended, at a cost of 29 trials
- kind: result
- era: HISTORY
- date: 2026-07-31
- figures:
  - phi = 0.9722 measured, a 24.6-day dislocation half-life [S]
  - rolling z net SR: 21d 0.37, 63d 0.84, 126d 0.65, 252d (live) 0.69; turn/yr 63d 45.3, 252d 26.3 [S]
  - Kalman lam=30 gross 1.60, net 0.81 [S]
  - distribution cuts inside the Kalman: cuts-on 1.28 vs cuts-off 1.60 [S]
  - CEF source counter +29: 9 (distribution-cut study) + 16 (Kalman sweeps) + 4 (window control) [S]
- source: `pre-clean-slate:results/cef/ESTIMATOR_NOTE.md` @ `f6d155f`
- supports: §2, §6
- status: superseded by E-2026-07-31-28 (2026-07-31)

### E-2026-07-31-27 · Spec v3 (z_window 63, rebalance 2) was frozen and the 2024+ holdout pre-registered with a decision rule written before it was run
- kind: ruling
- era: HISTORY
- date: 2026-07-31
- figures:
  - spec_id cef_discount.v3.20260731: z_window 63, rebalance_days 2, execution shift 2 [S]
  - holdout window 2024-01-01 → 2026-07-30; rule ≥ +0.40 PASS, 0.00 to +0.40 WEAK, < 0.00 FAIL [S]
  - 0.40 is roughly half the pre-holdout net of 0.84; haircut at N=29 is sqrt(2*ln 29) = 2.60 [S]
- source: `pre-clean-slate:results/cef/HOLDOUT_PREREG.md` @ `f6d155f`
- supports: §5, §6
- status: provenance only

### E-2026-07-31-28 · The holdout was opened once and the z_window 63 change failed on net: the signal generalised but its turnover did not (the argmax lesson)
- kind: kill
- era: HISTORY
- date: 2026-07-31
- figures:
  - v3 (63/2), 646 days: gross_sharpe 1.75, net_sharpe -0.298, net_t_stat -0.48, cagr_pct -2.05 [S]
  - turnover_per_yr 102.6 (vs 45.3×/yr in-sample); cost_pct_of_gross 117.2 [S]
  - by year 2024 0.02, 2025 -1.12, 2026 0.61; verdict FAIL [S]
  - reference as deployed (252/5): gross 0.962, net 0.352, net t 0.56, turnover 32.0, cost_pct_of_gross 63.8 [S]
  - opened_utc 2026-07-31T21:47:15 [S]
- source: `pre-clean-slate:results/cef/HOLDOUT_OPENED.json` @ `f6d155f`; `pre-clean-slate:results/cef/ESTIMATOR_NOTE.md` @ `f6d155f`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §5, §6
- status: provenance only

### E-2026-07-31-29 · Spec v4 reverted to z_window 252 and a 5-day rebalance after the holdout failure; the 16 queued MOC orders for the failed configuration were cancelled
- kind: release
- era: HISTORY
- date: 2026-07-31
- figures:
  - reverted to z_window=252, rebalance_days=5 (cef_discount.v4.20260731) [S]
  - the 16 MOC orders queued for Monday's close were cancelled [S]
- source: `pre-clean-slate:results/cef/ESTIMATOR_NOTE.md` @ `f6d155f`
- supports: §2, §5
- status: superseded by E-2026-07-31-30 (2026-07-31)

### E-2026-07-31-30 · Spec v5 set the calendar to 2 days with a cadence gate and fixed the order type at MOC; it was the live spec until the band
- kind: release
- era: HISTORY
- date: 2026-07-31
- figures:
  - rebalance_days changed 5 -> 2 on 2026-07-31 with user sign-off; the sleeve gained the cadence gate [S]
  - measured net Sharpe at shift(2): hold=1 0.62, hold=2 0.73, hold=3 0.70, hold=5 0.51, hold=10 0.30, hold=21 0.20 (36.8 vs 24.2 turns/yr) [S]
  - order_type MOC; on 2026-07-31 market orders filled at 07:27 ET at up to 2.9% from the decision price against a ~0.1% modelled cost [S]
  - capital_usd 500000.0; kill_drawdown 0.18, halve_drawdown 0.12, max_gross_exposure_usd 1300000.0 [S]
  - in force from 2026-07-31 to 2026-09-06 [S]
- source: `pre-clean-slate:_archive/ops/_archive/cef_discount.v5.20260731.frozen.json` @ `f6d155f`; `pre-clean-slate:_archive/ops/_archive/README.md` @ `f6d155f`
- supports: §2, §5
- status: superseded by E-2026-09-06-04 (2026-09-06)

### E-2026-07-31-31 · The first execution study rejected a no-trade band on the 5-day calendar and found that holding longer destroys the edge; price-weighting was recommended but never entered a frozen spec
- kind: result
- era: HISTORY
- date: 2026-07-31
- figures:
  - baseline hold 5d net 0.82; no-trade band 0.01 net 0.83; band 0.05 net 0.74 (rejected) [S]
  - hold 10d net 0.47, hold 21d 0.27 [S]
  - price-weighted, hold 5d: gross 1.37, net 0.98, modelled cost 265 → 215bp [S]
  - January CEF basis: +11.71bp/day, t 3.99, 20/23 Januaries positive, correlation with the deployed strategy -0.001 [S]
- source: `pre-clean-slate:results/cef/research/NICHE_EDGE_RESEARCH.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`
- supports: §2, §6
- status: superseded by E-2026-09-06-02 (2026-09-06)

### E-2026-09-01-01 · A 21-session silent outage ended: the book had refused to arm on a broker-port misconfiguration while every surface read "ok"
- kind: incident
- era: HISTORY
- date: 2026-09-01
- figures:
  - 21 consecutive silent dry-runs, 08-03 → 08-28, all ok_not_armed, reason "nothing listening on 127.0.0.1:4002" [V]
  - config/.env had IBKR_PORT=7497 (TWS paper) while the gateway serves 4002; corrected by ops/switch_broker.py at 2026-09-01 16:58 [S]
- source: `pre-clean-slate:_archive/results/ops/NUMBER_CONSISTENCY_2026-09-10.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md` @ `f6d155f`; `docs/HISTORY.md` @ `bdbe563`
- supports: §4, §5
- status: provenance only

### E-2026-09-01-02 · The units trap: a drawdown limit meant to be off at 99% was live at 0.99% because the code divides percent keys by 100
- kind: incident
- era: HISTORY
- date: 2026-09-01
- figures:
  - book_drawdown_suspend_pct read 0.99; cap = -abs(pct)/100 made it live at 0.99%, breached 2026-08-31 at -1.84%; now 99.0 [S]
  - kill_drawdown (0.18) and halve_drawdown (0.12) read by no code path [S]
  - pointing risk.py at kill_drawdown (0.18, a fraction) would arm a KILL at -0.18% [S]
- source: `pre-clean-slate:_archive/ops/books/phase0_book.json` @ `f6d155f`; `pre-clean-slate:.claude/skills/spec-change/SKILL.md` @ `f6d155f`; `pre-clean-slate:results/ops/hardening_2026-09-21/FINDINGS.json` @ `f6d155f`
- supports: §5
- status: provenance only

### E-2026-09-01-03 · The first MOC session realised a few basis points, but it was one session, and its own documents disagree on the cost, the dispersion and the fill count
- kind: live-pnl
- era: HISTORY
- date: 2026-09-01
- figures:
  - 15 fills, realised 2.8bp vs 12.1 modelled; n=1, dispersion ±93.8bp [`pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md`]; taken as the record because it is the per-session row with its modelled comparator that later documents cite, though broker_fills.csv is the authority and was not re-read [U]
  - one MOC session (2026-09-01, 15 fills), 3.4bp, dispersion ±25bp per fill [`pre-clean-slate:results/cef/ALPHA_AUDIT_2026-09-05.md`]; not the record [U]
  - 2026-09-01: 19 broker-confirmed executions [`pre-clean-slate:_archive/results/ops/NUMBER_CONSISTENCY_2026-09-10.md`]; broker_fills.csv is the fact under SYSTEM.md §0's order of authority, so 19 executions is the record for the count [U]
- source: `pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md` @ `f6d155f`; `pre-clean-slate:results/cef/ALPHA_AUDIT_2026-09-05.md` @ `f6d155f`; `pre-clean-slate:_archive/results/ops/NUMBER_CONSISTENCY_2026-09-10.md` @ `f6d155f`
- supports: §4, §5
- status: provenance only

### E-2026-09-05-01 · An independent alpha audit confirmed the discount IC at a tradable lag, distinct from reversal, not credit beta, not one name, and present in every era
- kind: result
- era: HISTORY
- date: 2026-09-05
- figures:
  - 17 frozen names, 6,989 days, 1998-11-18 to 2026-09-02 [S]
  - IC 1d / 2d / 5d / 21d traded at close t+1: −0.053 (t −12.1) / −0.074 (t −11.6) / −0.096 (t −9.4) / −0.131 (t −6.1) [`pre-clean-slate:results/cef/ALPHA_AUDIT_2026-09-05.md`]; the record, because the archived SYSTEM.md names this note as what settles the claim [U]
  - IC 0.040 at 1d and 0.097 at 21d, n = 41,000–42,000 fund-days per horizon [`pre-clean-slate:results/AUDIT_2026-07-31.md`]; a different construction, not the record [U]
  - operative cell −0.074, t −11.6, 57.9% of periods correctly signed; lagging a day costs ~31% of the 1d IC and ~10% of the 21d IC [S]
  - price-reversal control IC −0.046 (t −6.7); the two IC series correlate 0.575 [S]
  - beta on the equal-weighted universe +0.013, R² 0.0008 [S]
  - leave-one-out gross Sharpe 2.23 (without PFN) to 2.93 (without PHK) against 2.49 [S]
  - mean IC by period 1998-2004 −0.094, 2005-2010 −0.086, 2011-2015 −0.091, 2016-2020 −0.047, 2021-2026 −0.064 [S]
  - the deployed 13-name, ADV-filtered IC is about half the 17-name figure the docs quote (W4, 2026-10-11) [S]
- source: `pre-clean-slate:results/cef/ALPHA_AUDIT_2026-09-05.md` @ `f6d155f`; `pre-clean-slate:results/AUDIT_2026-07-31.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/SYSTEM_2026-09-28.md` @ `f6d155f`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §2, §3, §6
- status: provenance only

### E-2026-09-05-02 · The audit fixed the strategy's cost threshold: breakeven is 32.6bp per unit turnover, so whether the edge is harvestable is a question of execution
- kind: result
- era: HISTORY
- date: 2026-09-05
- figures:
  - 2-day rebalance, 6% vol target, T+1: gross 17.68%, Sharpe 2.90; net @ 15bp 1.57; net @ 30bp 0.23; net @ 50bp −1.46 [S]
  - turnover 21.5% of gross per day, 54x annualised [S]
  - breakeven 32.6bp full sample, 28.9bp for 2021-2026 [S]
  - survivorship: the panel contains only funds alive today; PDO 1,402 days of history, MHD 6,989 [S]
- source: `pre-clean-slate:results/cef/ALPHA_AUDIT_2026-09-05.md` @ `f6d155f`
- supports: §3, §5
- status: provenance only

### E-2026-09-06-01 · The short leg was charged for the first time: borrow cost about a quarter of a Sharpe on one day's fees, and availability bound on two Nuveen munis
- kind: result
- era: HISTORY
- date: 2026-09-06
- figures:
  - borrow 1.22%/yr on held short market value, 0.23 of Sharpe [S]
  - net after spread and borrow: calendar 2d 0.10; band 4.8% 0.43; band 6.4% 0.48 [S]
  - fees median 0.83%, mean 2.29%, max 10.56%; HYT 10.56, NAD 9.98, NVG 4.23 [S]
  - PHK 1.06%, PTY 1.09%, PCN 0.63%: premium does not predict borrow cost [S]
  - NAD binds at $44,978; 11.4% of the desired short book unfillable at $500k; capacity roughly $5m [S]
- source: `pre-clean-slate:results/cef/BORROW_NOTE_2026-09-06.md` @ `f6d155f`
- supports: §3, §5
- status: superseded by E-2026-09-10-05 and E-2026-09-10-06 (2026-09-10)

### E-2026-09-06-02 · On the 2-day calendar, a no-trade band dominated the calendar at matched turnover and stayed positive at 30bp where every calendar went negative
- kind: result
- era: HISTORY
- date: 2026-09-06
- figures:
  - 5,452 trading days, identical signal and T+1 MOC execution [S]
  - calendar 2d: gross 1.20, 31.1 turn/yr, net@15bp 0.33, net@30bp −0.55 [S]
  - band 4.8%: gross 1.16, 17.6 turn/yr, hold 12.6d, net@15bp 0.66, net@30bp 0.17 [S]
  - band 6.4%, which topped the swept column: gross 1.11, 14.2 turn/yr, net@15bp 0.71 [S]
  - turnover sd/mean 2015+: calendar 2d 12.2%, band 6.4% 20.9% (the band's turnover is less stable) [S]
  - capture after measured borrow: calendar 1.20 gross → 0.10 net, kept 8% [S]
- source: `pre-clean-slate:_archive/docs/PLAN.md` @ `f6d155f`
- supports: §2, §3
- status: provenance only

### E-2026-09-06-03 · The band width was derived from the cube-root law on measured target-weight dynamics, not swept; the sweep-topping 6.4% was deliberately not chosen
- kind: method
- era: HISTORY
- date: 2026-09-06
- figures:
  - σ_w = 0.04083/day, φ_w = 0.95280, κ_w = 0.04835, half-life 14.3d [S]
  - h* = 4.26% at 15bp, 4.85% at 22bp [S]
  - h(30)/h(15) = 1.260 against 2^(1/3) = 1.2599 [S]
  - 4.8% is the lower edge of the measured plateau (4.8–9.6%) [S]
- source: `results/cef/PREREG_BAND_2026-09-06.md` @ `9636502`
- supports: §2
- status: provenance only

### E-2026-09-06-04 · Spec v6 replaced the 2-day calendar with the 4.8% band (CEF trial 48), proved a byte-identical no-op with the key absent
- kind: release
- era: HISTORY
- date: 2026-09-06
- figures:
  - spec cef_discount.v5.20260731 → cef_discount.v6.20260906; band_width = 0.048; rebalance_days retained and inert [S]
  - Trial 48 of the CEF counter [S]
  - committed readout: turnover ~17.6×/yr against 31.1, average hold ~6 to ~12 business days, within 20 armed sessions [S]
  - the book had armed on 3 of 26 sessions when this was written [S]
- source: `results/cef/PREREG_BAND_2026-09-06.md` @ `9636502`; `pre-clean-slate:ops/specs/cef_discount.frozen.json` @ `f6d155f`
- supports: §2, §5
- status: provenance only

### E-2026-09-06-05 · Per-name OU reversion speed in the score was withdrawn: the z-score already carries κ^(1/2), so the extra term double-counts
- kind: kill
- era: HISTORY
- date: 2026-09-06
- figures:
  - band 6.4% net@15bp: A live z 0.70; C OU shrunk per-name κ 0.49; E raw κ 0.35 [S]
  - score = x·κ^p/σ^d, band net@15bp: p −0.50 0.70, 0 (live) 0.71, +0.50 0.65, +1.00 0.57 [S]
  - slope of log σ^d on log κ across 17 names −0.463 against OU's predicted −0.500 [S]
  - Trials: 0 — withdrawn [S]
- source: `pre-clean-slate:_archive/docs/PLAN.md` @ `f6d155f`
- supports: §2, §6
- status: provenance only

### E-2026-09-06-06 · Σ⁻¹α construction confirmed the concentration diagnosis and raised gross Sharpe, but bought breadth with turnover; it wins only if execution is cheap
- kind: result
- era: HISTORY
- date: 2026-09-06
- figures:
  - w ∝ Σ⁻¹(σz) (LW): gross 1.54, 44.4 turn/yr, net@15bp 0.28, BR_eff 3.95 vs live 1.20 / 31.1 / 0.33 / 2.24 [S]
  - turnover-matched: Σ⁻¹ band 6.4% net@5bp 1.11 vs live 0.97; net@30bp −0.03 vs 0.31 [S]
- source: `pre-clean-slate:_archive/docs/PLAN.md` @ `f6d155f`
- supports: §2, §6
- status: provenance only

### E-2026-09-06-07 · Sequential Σ⁻¹α plus a scalar band was rejected: the band gives back what Σ⁻¹ buys
- kind: kill
- era: HISTORY
- date: 2026-09-06
- figures:
  - at matched turnover gross 1.07, below plain α's 1.10 [S]
  - Σ⁻¹α + band 12.1% (sequential), 14.2 turn/yr: net@15bp 0.62 [S]
- source: `pre-clean-slate:_archive/docs/PLAN.md` @ `f6d155f`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: provenance only

### E-2026-09-06-08 · A joint cost-aware optimiser beat the band at matched turnover but was not deployed, on turnover stability and an ADV modelling fork
- kind: result
- era: HISTORY
- date: 2026-09-06
- figures:
  - turnover-matched at 14.2 turns/yr: joint net@15bp 0.90 vs band 6.4% 0.70; c_model 25.2bp [S]
  - turnover stability era sd/mean 36.9% vs 11.9%; 2013–16 loses (0.92 vs 1.43) [S]
  - leaving ineligible names as decision variables puts 28% of gross in untradeable names and loses (0.54) [S]
- source: `pre-clean-slate:_archive/docs/PLAN.md` @ `f6d155f`
- supports: §2, §6
- status: superseded by E-2026-09-10-04 (2026-09-10)

### E-2026-09-06-09 · Effective breadth was 2.24, not 17: two-thirds of book variance was one unmanaged muni-versus-taxable factor
- kind: result
- era: HISTORY
- date: 2026-09-06
- figures:
  - PC1 3.6%, PC2 65.7% (muni vs taxable), PC3 9.6%, PC4–17 21.1% [S]
  - BR_eff = 2.24 of 17 names; IR computed on 17 names overstates by 2.75× [S]
  - effective breadth 1.17 on the live weights and 2.24 historically, as of 2026-09-07 [S]
- source: `pre-clean-slate:_archive/docs/PLAN.md` @ `f6d155f`; `docs/BRIEF.md` @ `df87c59`
- supports: §3, §5
- status: provenance only

### E-2026-09-06-10 · Combining the discount with a price-reversal signal was rejected: the price signal is almost entirely subsumed
- kind: kill
- era: HISTORY
- date: 2026-09-06
- figures:
  - optimal combined |IC| 0.0748 vs 0.0747 for discount alone = +0.1% [S]
  - price signal 95% subsumed (weights −0.95/−0.05) [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md` @ `f6d155f`
- supports: §6
- status: provenance only

### E-2026-09-06-11 · Cointegration pairs were listed among the rejected CEF construction variants, on the same figures as the ETF pair-reversion kill
- kind: kill
- era: HISTORY
- date: 2026-09-06
- figures:
  - gross 1.03 → net −0.16; needed 32.8× leverage against a 2× ceiling [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md` @ `f6d155f`
- supports: §6
- status: provenance only

### E-2026-09-08-01 · Team lead: keep the 17 as the liquid set, treat the other 27 CEFs as the illiquid tail and a sealed holdout, and add a 2023 time holdout to every fit
- kind: ruling
- era: HISTORY
- date: 2026-09-08
- figures:
  - Keep the 17. They already are the liquid set (median $5.6m ADV). The 27 are the illiquid tail [S]
  - Holdout: keep the 27 and add a 2023–2026 time holdout to every fit [S]
  - later correction: for the core book the 2023+ has been seen; 2024–26 was opened on 2026-07-31 [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`
- supports: §2, §5
- status: provenance only

### E-2026-09-08-02 · Team lead's standing decisions of 2026-09-08: two trial counters (CEF and GAMMA), HALVE/KILL to be armed on broker NAV, paper indefinitely, retire the null trader
- kind: ruling
- era: HISTORY
- date: 2026-09-08
- figures:
  - Trial counters: two, CEF and GAMMA, each its own bar; GAMMA opened at 0 [S]
  - Judged on absolute return; derive the vol target, cap 20% [S]
  - Risk controls: arm HALVE/KILL on broker-confirmed NAV once W6 §A lands [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §5
- status: provenance only

### E-2026-09-08-03 · Dust orders: band HOLDs were leaking out as small live orders through a price mismatch; HOLDs were expressed in shares and a derived $517 minimum trade added
- kind: correction
- era: HISTORY
- date: 2026-09-08
- figures:
  - 12 orders/session of share-rounding drift, $3,019 gross, ~$14.91/session = 0.75%/yr of the book [S]
  - 1.52x/yr of phantom turnover against the band's pre-registered 17.6x readout [S]
  - min_trade_usd N = 1e4/(30 − 10.67) = $517.33, floored to $517 [S]
  - not a trial; the CEF counter stays at 48 [S]
- source: `pre-clean-slate:results/cef/DUST_ORDERS_2026-09.md` @ `f6d155f`; `pre-clean-slate:ops/specs/cef_discount.frozen.json` @ `f6d155f`; `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`
- supports: §2, §5
- status: provenance only

### E-2026-09-09-01 · The CEF trial counter was corrected from 18 to 48: it had missed the 29 trials of the estimator session and the band trial
- kind: counter
- era: HISTORY
- date: 2026-09-09
- figures:
  - the CEF row read 18 until today; 48 is correct [S]
  - it missed the +29 (9 distribution-cut + 16 Kalman sweeps + 4 window control) and the band trial [S]
  - GAMMA opened by the 2026-09-08 standing decisions at 0 [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §5, §6
- status: supersedes the CEF 18 of E-2026-07-31-08

### E-2026-09-09-02 · The harness books raw-price returns, so longs were never credited distributions; the bias nets out on average but swings by era
- kind: correction
- era: HISTORY
- date: 2026-09-09
- figures:
  - band holdings path, 3,962 ex-dates, 2005–2026: −0.01%/yr full sample [S]
  - −0.77%/yr in 2010–14, +0.25 to +0.36 since 2015; standard deviation 1.23%/yr [S]
- source: `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`
- supports: §2
- status: provenance only

### E-2026-09-09-03 · The book's first real band trades were transmitted from the 2026-09-09 decision, sized against the epoch NAV row
- kind: live-pnl
- era: HISTORY
- date: 2026-09-09
- figures:
  - transmitted JFR SELL 4,630; MHD BUY 115; MQY BUY 185; NEA SELL 4,458 [V]
  - SKIP NAD +37 @ 11.15 = $413 < min_trade_usd $517 [V]
  - placement sized against the epoch NAV $500,000.00; the 09-09 mark of $504,573.20 is 0.914% larger [V]
- source: `pre-clean-slate:_archive/results/cef/FIRST_BAND_SESSIONS.md` @ `f6d155f`
- supports: §4
- status: provenance only

### E-2026-09-10-01 · The headline validation was re-scored at shift(2) with its announced embargo applied: the retired calendar fails its deflated-Sharpe bar at every trial count
- kind: correction
- era: HISTORY
- date: 2026-09-10
- figures:
  - point-in-time: gross 1.26 → 1.27 (shift(1), 14:37) → 0.94; net 0.82 → 0.83 → 0.51 [S]
  - walk-forward 9/9 (as run 07-31) → 8/9 (shift(1), 14:37) → 7/9, median 0.63, worst −0.45 [S]
  - block bootstrap P(SR≤0) 0.000% → 0.300%; 5th/95th 0.20/0.79 [S]
  - DSR 0.956 at N=10 → 0.870 at N=48 → 0.333 at N=48; also 0.588 at N=10, 0.197 at N=162 [S]
  - observed Sharpe 0.51 below the best-of-48 null of 0.60 [S]
  - shift(2) era gross: 2005-2009 −0.18, 2010-2014 1.26, 2015-2019 0.89, 2020-2022 1.74, 2023-2026 0.83 (universe 2.6 / 6.3 / 9.3 / 11.8 / 12.3 funds) [S]
  - counter stays at 48: a lookahead fix re-measures an existing trial [S]
- source: `pre-clean-slate:results/cef/EXECUTION_CONVENTION_2026-09-10.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`; `pre-clean-slate:ops/specs/cef_discount.frozen.json` @ `f6d155f`
- supports: §2, §5, §6
- status: supersedes the shift(1) figures (E-2026-07-31-16, E-2026-07-31-17, E-2026-07-31-21)

### E-2026-09-10-02 · "Gross 1.23 in-sample, 1.75 out-of-sample" was withdrawn as evidence: 1.75 is the gross of a holdout whose recorded verdict is FAIL
- kind: correction
- era: HISTORY
- date: 2026-09-10
- figures:
  - 1.23 reproduces from nothing currently runnable [S]
  - 1.75 is the gross of a holdout with net_sharpe -0.298 and cost_pct_of_gross 117.2 [S]
- source: `pre-clean-slate:results/cef/EXECUTION_CONVENTION_2026-09-10.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/PLAN.md` @ `f6d155f`
- supports: §5, §6
- status: provenance only

### E-2026-09-10-03 · The traded band policy has never been walk-forwarded, bootstrapped or deflated; its only figures come from the full-sample harness
- kind: result
- era: HISTORY
- date: 2026-09-10
- figures:
  - band 4.8% on the same panel: gross 1.17, net@15bp 0.67, turn 17.6×/yr, hold 12.6d [S]
  - band_frontier output byte-identical before and after the validate.py change [S]
- source: `pre-clean-slate:results/cef/EXECUTION_CONVENTION_2026-09-10.md` @ `f6d155f`; `docs/HISTORY.md` @ `bdbe563`
- supports: §2, §5
- status: provenance only

### E-2026-09-10-04 · The joint optimiser's comparison had been run against the band width not chosen; re-run against the live 4.8% band its edge was larger
- kind: correction
- era: HISTORY
- date: 2026-09-10
- figures:
  - as first written: matched at 14.2/yr, net@15bp 0.90 vs the band's 0.70, against band(T, 0.064) [S]
  - corrected: turnover-matched at 17.6/yr, net@15bp 0.91 vs the band's 0.67; +0.24 at 15bp, +0.26 at 5bp [S]
  - c_model "moved 25.4 → 20.1bp" [`pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md`]; the record for the corrected 20.1bp, which no other file contradicts [U]
  - c_model 25.2bp in the original turnover-matched table [`pre-clean-slate:_archive/docs/PLAN.md`]; disagrees with the 25.4 the correction says it moved from, not the record [U]
- source: `pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md` @ `f6d155f`
- supports: §2, §6
- status: supersedes E-2026-09-06-08

### E-2026-09-10-05 · Borrow history overturned the one-day borrow estimate: the PIMCO premium funds had borrowed at double-digit fees over 2021–26
- kind: correction
- era: HISTORY
- date: 2026-09-10
- figures:
  - daily fee series by name, 2021-09-13 onward, 43 of 44 names, 52,978 rows, as built 2026-09-10 [S]
  - 2021–26 averages PTY 29.7% (max 178%), PFN 19.7%, PHK 16.6%, PCN 13.8%, PDO 13.4%, against 0.3–1% today [S]
  - every net-of-borrow figure computed on today's fees (the 1.22%/yr drag included) is suspect until re-measured [S]
  - on the live 4.8% band the top three borrow names are 28.2 / 27.1 / 12.1 = 67.4% of the drag (was "70%" on the retired calendar) [S]
- source: `docs/BRIEF.md` @ `df87c59`; `pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md` @ `f6d155f`
- supports: §5
- status: supersedes E-2026-09-06-01

### E-2026-09-10-06 · The borrow-availability dispute could not be settled: the two sources never reported on the same day, and the public file died
- kind: result
- era: HISTORY
- date: 2026-09-10
- figures:
  - NAD available: 3,000 (public file, 2026-09-06 and -08) vs 83,942 (TWS tick 236, 2026-09-10) [V]
  - paired readings in the panel: zero; the public file returns HTTP 404 [V]
  - NAD fee 9.98 → 10.21 → 10.88 %/yr over the four dates [V]
  - no live short under 5× cover; NEA returned no availability tick [V]
- source: `pre-clean-slate:results/cef/BORROW_AVAILABILITY_2026-09-10.md` @ `f6d155f`
- supports: §5
- status: supersedes E-2026-09-06-01

### E-2026-09-10-07 · The IBKR arm rate and fill record as re-measured on 2026-09-10: few sessions armed, three dates with broker-confirmed fills, and a ledger of modelled fills
- kind: live-pnl
- era: HISTORY
- date: 2026-09-10
- figures:
  - 5 of 29 sessions reached ARMED: 08-31, 09-01, 09-04, 09-08, 09-09 [V]
  - "armed on 3 of 26 sessions" was stale, repeated undated in eight places [V]
  - 294 broker-confirmed executions, 3 fill dates (07-31: 257, 09-01: 19, 09-08: 18) [V]
  - 22 of 24 ledger trade dates are modelled, true only against the pre-epoch archive [V]
- source: `pre-clean-slate:_archive/results/ops/NUMBER_CONSISTENCY_2026-09-10.md` @ `f6d155f`
- supports: §4
- status: provenance only

### E-2026-09-10-08 · The honest CEF track record on IBKR was two NAV observations: the pre-epoch ledger had booked fills for sessions the account never made
- kind: live-pnl
- era: HISTORY
- date: 2026-09-10
- figures:
  - pre-epoch ledger booked 22 sessions of fills the account never made (broker port misconfigured 2026-08-03..2026-09-03) [S]
  - archived series 2026-07-30 → 2026-09-03 ends at 498,178.71; live restarts at 500,000.00 on 2026-09-08 [V]
  - NAV observations 2; trades in the live ledger 0; broker-confirmed fills post-epoch 0; quotable return +0.9146% over one session [S]
- source: `pre-clean-slate:results/ops/LEDGER_DIVERGENCE_2026-09-10.md` @ `f6d155f`
- supports: §4, §5
- status: provenance only

### E-2026-09-11-01 · The book is not short volatility in a way an option can profitably hedge: the convexity overlay's pre-written gate failed on both conditions
- kind: result
- era: HISTORY
- date: 2026-09-11
- figures:
  - β_ΔVIX −0.000092/pt, t −0.69 (NW5, n = 2,742); univariate −0.000343 (t −2.80) [S]
  - 0 of 10 worst 21-session windows start in the top VIX quintile [S]
  - SHORTVOL loading +0.105 (t +1.34) full sample [S]
  - full-model R² 0.036, alpha +10.09%/yr (t +5.05) [S]
  - IC by VIX tercile −0.0392 / −0.0417 / −0.0936 [S]
  - Feb–Mar 2020: book −3.98%, PHK −8.37%, the other sixteen names +4.39% [S]
  - Trials spent: 0 on either counter [S]
- source: `pre-clean-slate:results/cef/STRESS_BETA_2026-09-11.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` @ `f6d155f`
- supports: §5
- status: provenance only

### E-2026-09-11-02 · The live band held nothing before 2013-06-14, so the book has never traded a credit crisis; the documented flat-period count was wrong
- kind: correction
- era: HISTORY
- date: 2026-09-11
- figures:
  - flat on 2,126 of 5,456 sessions, first position 2013-06-14 (measured on the live band) [`pre-clean-slate:results/cef/STRESS_BETA_2026-09-11.md`]; the record, measured on the live policy [U]
  - "the 2411 dates before 2013 are flat" [`pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md`, CLAUDE.md landmine 6 as then written]; not the record [U]
  - traded sessions only: gross SR 1.551, 28.8 turn/yr, 2013-06-14 .. 2026-09-10; full panel 1.210 [S]
- source: `pre-clean-slate:results/cef/STRESS_BETA_2026-09-11.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md` @ `f6d155f`
- supports: §2, §5
- status: provenance only

### E-2026-09-13-01 · The options programme was closed: credit gamma is far more expensive than equity gamma and no declared conditioner times it; GAMMA stays at 0
- kind: kill
- era: HISTORY
- date: 2026-09-13
- figures:
  - variance ratio HYG (credit) 2.77x vs SPY (equity) 1.28x; HYG implied 7.78% vs realised 4.68% [S]
  - implied below subsequent realised on 9.1% of days full sample, 1.8% in 2023–2026 [S]
  - C3 beside C1: β +0.0097, t +2.42, incremental R² +0.0358 [S]
  - C3 on the 2023–2026 holdout falls to 24% of full sample, t +1.69; on the stated target −0.20 [S]
  - best cell C3 > 2.0 at −0.0113 [S]
- source: `pre-clean-slate:results/gamma/CREDIT_BASE_RATE_2026-09-13.md` @ `f6d155f`; `pre-clean-slate:results/gamma/PREREG_GAMMA_TIMING_2026-09-13.md` @ `f6d155f`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §5, §6
- status: provenance only

### E-2026-09-13-02 · The vol scalar was measured over its history: the "1.5×" in the sizing note was never a bound, and the real bound is the gross-exposure cap
- kind: result
- era: HISTORY
- date: 2026-09-13
- figures:
  - 3,046 decision dates 2013-06-14 .. 2026-09-11: scalar median 1.330, mean 1.345 [S]
  - above 1.5 on 1,115 dates (36.6%); at the 2.5 cap on 75 (2.5%) [`pre-clean-slate:results/cef/VOL_SCALAR_2026-09-13.md`]; the record, measured on the traded window with its command named [U]
  - "pinned at its 2.5 cap on 5.2% of days" [`pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md`, 2026-09-06]; sample not stated, not the record [U]
  - 2026-09-11 scalar 0.06/0.0379 = 1.58; gross $813,682, 63% of max_gross_exposure_usd $1,300,000 [S]
  - Trials: 0 [S]
- source: `pre-clean-slate:results/cef/VOL_SCALAR_2026-09-13.md` @ `f6d155f`; `pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md` @ `f6d155f`
- supports: §5
- status: provenance only

### E-2026-09-13-03 · The W3 go-live moved decisions to the morning on yesterday's complete pair and re-seeded the CEF ledger from broker positions at a clean epoch
- kind: release
- era: HISTORY
- date: 2026-09-13
- figures:
  - re-seeded at epoch 2026-09-11, NAV $500,000, at 2026-09-13 23:04 [V]
  - prod worktree detached at v2026.09.13.4 when IBKR was retired [S]
- source: `pre-clean-slate:results/ops/GO_LIVE_W3_2026-09-13.md` @ `f6d155f`; `pre-clean-slate:results/ops/LEDGER_NOOP_MORNING_2026-09-15.md` @ `f6d155f`; `pre-clean-slate:_archive/prod_state_2026-09-28/README.md` @ `f6d155f`
- supports: §2, §5
- status: provenance only

### E-2026-09-14-01 · Team lead, 2026-09-14: the frozen vol target stays in force until W6 derives a new one; retiring the null trader is open
- kind: ruling
- era: HISTORY
- date: 2026-09-14
- figures:
  - vol_target_annual stays in force (0.06 when this was decided) until W6 derives a new value [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`
- supports: §5
- status: provenance only

### E-2026-09-15-01 · Ledger desyncs halted all three IBKR books: the morning schedule's first sessions sent orders the ledger never recorded; the last broker-confirmed fills were on 2026-09-15
- kind: incident
- era: HISTORY
- date: 2026-09-15
- figures:
  - cef_discount_paper halted 2026-09-15 08:39:04; benchmarks_paper 2026-09-14 17:25:10; phase0_null 2026-09-10 [V]
  - broker_fills.csv carries 4 executions on 2026-09-14 and 4 on 2026-09-15, filled in the closing auction [V]
  - UnbookedExecution: the broker reports 4 execution(s) that no ledger order accounts for [S]
  - last broker-confirmed fill 2026-09-15 [V]
- source: `pre-clean-slate:results/ops/LEDGER_NOOP_MORNING_2026-09-15.md` @ `f6d155f`; `pre-clean-slate:_archive/prod_state_2026-09-28/ops/HALT_cef_discount_paper.md` @ `f6d155f`; `pre-clean-slate:results/ops/ALPACA_MIGRATION_MANIFEST_2026-09-28.md` @ `f6d155f`
- supports: §4, §5
- status: provenance only

### E-2026-09-15-02 · Team lead (D19/D20): the paper account is scored on gross P&L with no borrow or execution cost
- kind: ruling
- era: HISTORY
- date: 2026-09-15
- figures:
  - none (a ruling)
- source: `pre-clean-slate:CLAUDE.md` @ `f6d155f`; `ng/05_research_no_borrow_rescore.md` @ `7b8eb25` (branch nextgen-20260914, no PR, unmerged)
- supports: §3, §5
- status: provenance only

### E-2026-09-16-01 · Spec v7 (group cap 0.30, gross ceiling 1.90×) was pre-registered on the nextgen branch as a risk change, not a return change; it never traded on IBKR
- kind: release
- era: HISTORY
- date: 2026-09-16
- figures:
  - spec cef_discount.v6.20260906 → cef_discount.v7.20260916 [S]
  - group_cap k = 0.30 from the pre-2023 median |net group weight| 0.304953; the argmax k = 0.15 (traded gross SR 1.706) was not chosen [S]
  - max_gross_stress = floor₀.₀₅(1.930940 − 0.02) = 1.90 [S]
  - v6 live band traded era: gross SR 1.537, ann 10.10%, vol 6.57%, maxDD −9.47%, turn 28.8/yr, max gross 2.77× [S]
  - v7 both: gross SR 1.724, vol 5.45%, maxDD −5.58%, turn 25.6/yr, max gross 1.90× [S]
  - paired change vs v6: traded −0.71 %/yr, t −1.06; pre-2023 −1.16 %/yr, t −1.71 [S]
  - counter on the nextgen branch: CEF 55 → 56, bar √(2 ln 56) = 2.836 [S]
- source: `results/cef/PREREG_GROUP_CAP_2026-09-16.md` @ `6217c96`; `docs/HISTORY.md` @ `bdbe563`
- supports: §2, §5
- status: superseded by the Alpaca v7 pre-registration, group_cap not adopted (2026-09-28)

### E-2026-09-21-01 · The hardening freeze decisions D1–D20: no external alerting, retire the null trader before re-arming, nextgen and spec v7 parked
- kind: ruling
- era: HISTORY
- date: 2026-09-21
- figures:
  - D3/D4: no external dead-man; alerts local only [S]
  - D6: retire phase0 BEFORE re-arm [S]
  - D14: nextgen and spec v7 parked and pushed, never merged; eligible after 20 clean sessions [S]
  - D19 (off-disk copy) and D20 (20-session bar: launch-to-trade ≤ 30 min, verifier PASS) are different questions from the 2026-09-15 D19/D20 scoring ruling [S]
- source: `pre-clean-slate:results/ops/hardening_2026-09-21/DECISIONS.md` @ `f6d155f`
- supports: §5
- status: provenance only

### E-2026-09-28-01 · IBKR was retired: a final flatten of 34 MOC orders was sent, reached the broker as PendingSubmit, and was left unconfirmed by the team lead's decision
- kind: incident
- era: HISTORY
- date: 2026-09-28
- figures:
  - all 12 com.quantt.* launchd jobs unloaded; launchctl list | grep quantt empty afterwards [V]
  - dry run: 34 whole-share USD stock positions, no open orders [V]
  - 15:05:57 ET re-read: exactly 34 open orders at the broker, all MOC, no duplicates, all PendingSubmit [V]
  - whether the account ended flat is unknown and will not be checked [S]
  - three scoped halts active in prod: cef_discount_paper, benchmarks_paper, phase0_null [V]
- source: `pre-clean-slate:results/ops/ALPACA_MIGRATION_MANIFEST_2026-09-28.md` @ `f6d155f`
- supports: §4, §5
- status: provenance only

### E-2026-09-28-02 · Team lead, 2026-09-28: move to Alpaca paper with one account per book, keep only the CEF book and the b6 benchmark, and hold main's CEF counter of 48 as authoritative
- kind: ruling
- era: HISTORY
- date: 2026-09-28
- figures:
  - Books: CEF strategy + b6 equal-weight credit benchmark; phase0/null trader, b1/b3/b4/b5 and credit_rv retire [S]
  - CEF trial counter 48 (main) is authoritative; nextgen's 53–56 were shadow research [S]
  - Spec: v7 from day one on Alpaca, superseding hardening D14 [S]
  - max_gross_stress re-derived on Alpaca; its 1.90 came from the IBKR-Canada account [S]
  - Capital $100k default per paper account [S]
- source: `pre-clean-slate:results/ops/ALPACA_MIGRATION_MANIFEST_2026-09-28.md` @ `f6d155f`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §5
- status: supersedes the nextgen counter of E-2026-09-16-01

### E-2026-09-28-03 · The 17-name v6 spec was tagged as the revert path for v7-on-Alpaca; ibkr-final marks the last IBKR-era commit
- kind: release
- era: HISTORY
- date: 2026-09-28
- figures:
  - spec_id cef_discount.v6.20260906, 17 names, capital_usd 500000.0, band_width 0.048, z_window 252 [S]
  - revert path example: spec-cef_discount.v6.20260906 [S]
- source: `ops/specs/cef_discount.frozen.json` @ `22b3a64` (tag spec-cef_discount.v6.20260906); `ibkr-final:ops/specs/cef_discount.frozen.json` @ `db795a9`; `.claude/skills/spec-change/SKILL.md` @ `b2b0509`
- supports: §2, §5
- status: provenance only

### E-2026-09-28-04 · IBKR was retired and the book moved to Alpaca paper, one $100k account per book, with both P&Ls recorded
- kind: ruling
- era: ALPACA
- date: 2026-09-28
- figures:
  - Accounts: "One Alpaca paper account per book, $100k each (the default)" [S]
  - Books: "The CEF strategy and the b6 equal-weight credit benchmark"; phase0/null trader, b1/b3/b4/b5 and credit_rv retire [S]
  - CEF trial counter: "48 is authoritative; adopting v7 makes it 49" [S]
  - The IBKR record ended "with 34 flatten orders left unacknowledged and the account's final state unknown by decision" [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`
- supports: §4, §5
- status: current (the scoring row was refined by E-2026-10-19-02; hosting by E-2026-10-07-02)

### E-2026-09-28-05 · Spec v7 for Alpaca spent two CEF trials: the universe cut 17 → 13 (trial 49) and a 1.80 gross ceiling derived from Reg T (trial 50)
- kind: counter
- era: ALPACA
- date: 2026-09-28
- figures:
  - Counter "CEF, 48 → 50. Bar √(2 ln 50) = 2.797" [S]
  - NAD, NEA, NVG, NZF "`shortable: false`, `borrow_status: hard_to_borrow`" on the first Alpaca probe [V]
  - G_stress = 1.843041 from NLV $100,000, m 0.50 (Reg T), w5 0.0425814 ending 2020-03-18; floored to 0.05 → `max_gross_stress` 1.80 [S]
  - without a cap "the 13-name band reaches 2.77× gross, and exceeds 1.80× on 13.2% of traded days" [S]
  - plateau: gross SR 1.141 / 1.155 / 1.170 / 1.174 / 1.168 / 1.160 at caps 1.60 / 1.70 / 1.80 / 1.843 / 2.00 / none [S]
  - `group_cap` not adopted: its rule gives k = 0.00 on 13 names (0.304953 on 17 [V]); R² of the 13-name P&L to the muni-minus-taxable spread 0.091 against 0.754 on 17 [S]
  - `min_trade_usd` 517 → 0.0, `capital_usd` 500,000 → 100,000, `risk.max_gross_exposure_usd` 1,300,000 → 260,000 [S]
- source: `results/cef/PREREG_ALPACA_V7_2026-09-28.md` @ `fcf0f27`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §2, §3, §5
- status: current (v7's `sizing_multiplier` was later added by v8/v9: E-2026-11-01-01, E-2026-11-02-17)

### E-2026-09-28-06 · The v7 report-only backtest (2013-06-14 → 2026-09-21) showed the 13-name book weaker than the 17 overall but stronger since 2023
- kind: result
- era: ALPACA
- date: 2026-09-28
- figures:
  - v7-on-Alpaca (13 + cap 1.80): gross SR 1.17, ann 7.29%, vol 6.23%, maxDD −12.78%, turn 22.2/yr; net@5/15/30 0.99 / 0.64 / 0.10 [S]
  - v6 band, 17 names: gross SR 1.54, ann 10.15%, maxDD −9.47%, turn 28.8/yr; net@30 0.23 [S]
  - by era, v7: 2010–14 0.72 (2.2), 2015–19 0.82 (5.6), 2020–22 1.06 (6.7), 2023–26 1.90 (10.4), last 12m 1.60 (9.9) [S]
  - "This is a report, not a gate" — the change went ahead on tradability grounds whatever §5 showed [S]
- source: `results/cef/PREREG_ALPACA_V7_2026-09-28.md` @ `fcf0f27`
- supports: §2, §5, §6
- status: current; its 2023–26 rows mean the core's 2023+ is no longer sealed (E-2026-11-01-02)

### E-2026-09-28-07 · release-20260928-1: the first Alpaca runner release, laptop prod, DRY_RUN=1 until the team lead's go
- kind: release
- era: ALPACA
- date: 2026-09-28
- figures:
  - tag message: "First Alpaca runner release: laptop prod, DRY_RUN=1 until the team lead's go" (tag at aa244f4, created 2026-09-28 17:24:28 −0400) [S]
  - "The build, two independent reviews (quant, execution) and the fixes changed or settled these points" (flips deferred; reject skips a symbol; gate 8 on Reg T) [S]
  - release-check verdict: none recorded in the tag or the files read [U]
- source: `tag:release-20260928-1` @ `aa244f4`; `docs/RUNNER.md` @ `8ce0395`; `docs/ROADMAP.md` @ `82a30f6`
- supports: §2, §5
- status: superseded by release-20260928-2 (2026-09-28)

### E-2026-09-28-08 · release-20260928-2: verify reads closing-auction prints in a timestamp window (Basic-plan SIP 403 fix)
- kind: release
- era: ALPACA
- date: 2026-09-28
- figures:
  - tag message: "Verify reads auction prints with timestamp window (Basic-plan SIP 403 fix)" (b9cd0a3, 2026-09-28 19:56:27 −0400) [S]
  - release-check verdict: none recorded [U]
- source: `tag:release-20260928-2` @ `b9cd0a3`
- supports: §2, §5
- status: superseded by release-20260929-1 (2026-09-29)

### E-2026-09-28-09 · Go-live rulings: arm on 2026-09-29, trade day one to full target, no fallback from `cls` to `day`, skip a rejected name and send the rest
- kind: ruling
- era: ALPACA
- date: 2026-09-28
- figures:
  - none (a ruling)
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/ROADMAP.md` @ `82a30f6`
- supports: §4, §5
- status: current ("If cls is rejected: no trade" was overtaken on paper by the late_market exception, E-2026-09-29-02)

### E-2026-09-29-01 · The first armed Alpaca session sent 13 MOC (`cls`) orders; paper filled 2 and let 11 expire
- kind: incident
- era: ALPACA
- date: 2026-09-29
- figures:
  - "13 `cls` orders accepted at 10:33 ET, plan_sha `74154e1e…`, sent on the team lead's go" [S]
  - "paper filled 2 of 13 `cls` orders (PHK 4,019/4,019, PFN 1,529/2,227; eleven expired)" [S]
  - every NYSE auction printed more shares than were asked for; Alpaca staff say paper treats `cls` as a market order at the close with random partial fills [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RUNNER.md` @ `8ce0395`
- supports: §4, §5
- status: current

### E-2026-09-29-02 · Paper-only exception to the MOC rule: decide in the evening, send market `day` orders 8 to 2 minutes before the close, fully automatic
- kind: ruling
- era: ALPACA
- date: 2026-09-29
- figures:
  - "obviously this is unacceptable" (team lead) → `execution = {mode: late_market, window_minutes_before_close: [8, 2]}`, paper only [S]
  - schedule: evening 22:00 ET retrying every 30 min until 01:00; morning backstop every 30 min 06:00–15:15 ET [S]
  - "Fully automatic from 2026-09-29 evening: prod installed with DRY_RUN=0 and AUTO_ARMED" [S]
  - the two unhedged longs (PHK 4,019, PFN 1,529) were not flattened [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RUNNER.md` @ `8ce0395`
- supports: §4, §5
- status: current (never for a live-money account)

### E-2026-09-29-03 · release-20260929-1: evening decision, morning backstop, nightly collector and shadow benchmark
- kind: release
- era: ALPACA
- date: 2026-09-29
- figures:
  - tag message: "Evening decision + morning backstop, nightly collector, shadow benchmark, review fixes" (7051359, 2026-09-29 18:00:57 −0400) [S]
  - release-check verdict: none recorded; the commit is "Review fixes: send window, collector independence, no silent data loss" [U]
- source: `tag:release-20260929-1` @ `7051359`; `commit:7051359` (subject) @ `7051359`; `docs/RUNNER.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20260929-2 (2026-09-29)

### E-2026-09-29-04 · release-20260929-2: paper late-market execution (decide in the evening, send market `day` from 15:52)
- kind: release
- era: ALPACA
- date: 2026-09-29
- figures:
  - tag message: "Paper late-market execution (decide evening, send 15:52 market day), review fixes" (e465f56, 2026-09-29 19:15:44 −0400) [S]
  - release-check verdict: none recorded [U]
- source: `tag:release-20260929-2` @ `e465f56`; `docs/RUNNER.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261007-1 (2026-10-07)

### E-2026-10-07-01 · The laptop prod sent no orders on three of its first six sessions; two sources give different causes for 2026-10-06
- kind: incident
- era: ALPACA
- date: 2026-10-07
- figures:
  - "from 2026-09-30 to 2026-10-07 the laptop sent no orders on 2026-10-02, 2026-10-05 and 2026-10-06, each time because it was asleep or offline" (SYSTEM.md §5) [U]
  - "2026-10-06's 21 buying-power refusals"; "The old `min(buying_power, regt_buying_power)` refused 2026-10-06's catch-up plan that Alpaca would have accepted" (RUNNER.md) [U]
  - the two disagree on 2026-10-06's cause. SYSTEM.md ranks above design notes in SYSTEM.md §0, but neither cites a broker read; unresolved, both kept [U]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RUNNER.md` @ `8ce0395`
- supports: §4, §5
- status: current

### E-2026-10-07-02 · The cloud VM was chosen: Azure for Students, Standard_B2pts_v2 (Arm64) in canadacentral
- kind: ruling
- era: ALPACA
- date: 2026-10-07
- figures:
  - "The VM size is free for 12 months; anything else ... comes out of the $100 student credit" [S]
  - when the credit or the 12 months run out "the subscription is disabled and the book stops" [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/ROADMAP.md` @ `82a30f6`
- supports: §5
- status: current

### E-2026-10-07-03 · release-20261007-1: verify parses `sell_short` fills
- kind: release
- era: ALPACA
- date: 2026-10-07
- figures:
  - tag message: "Verify parses sell_short fills" (415eb59, 2026-10-07 10:39:29 −0400) [S]
  - release-check verdict: none recorded [U]
- source: `tag:release-20261007-1` @ `415eb59`
- supports: §2, §5
- status: superseded by release-20261007-2 (2026-10-07)

### E-2026-10-07-04 · release-20261007-2: the exposure gate becomes two checks, plans scale to fit, fills are polled and TCA is recorded
- kind: release
- era: ALPACA
- date: 2026-10-07
- figures:
  - tag message: "Exposure gate two checks, scale-to-fit, polling, TCA, regime-proof test, frontier repro" (fce577e, 2026-10-07 16:49:28 −0400) [S]
  - maintenance at the account's live measured ratio, "47.8% on 2026-10-06" [S]
  - slower rebalancing re-tested: "no slower policy matches or beats the live band on the fit period; no trial spent" [S]
  - release-check verdict: none recorded ("Execution-desk review after the first week") [U]
- source: `tag:release-20261007-2` @ `fce577e`; `docs/RUNNER.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261008-1 (2026-10-08)

### E-2026-10-08-01 · release-20261008-1: the Azure VM prod package and the late-market send-budget gate, after eight release-check NO-GOs
- kind: release
- era: ALPACA
- date: 2026-10-08
- figures:
  - tag message: "Azure VM prod package (systemd installer, Key Vault boot secrets, bootstrap, runbook) + late-market send budget gate" (e8fde26, 2026-10-08 08:56:06 −0400) [S]
  - commits marked "release-check no-go" #1 to #8 on 2026-10-07/08, the last being e8fde26 itself [S]
  - send budget `n_orders × 3 s + 42 s` (margin corrected from 30 s, release-check #7) [S]
  - final release-check verdict: not recorded [U]
- source: `tag:release-20261008-1` @ `e8fde26`; `git-log:35202aa..e8fde26` (commit subjects, 2026-10-07/08) @ `e8fde26`; `docs/RUNNER.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261008-2 (2026-10-08)

### E-2026-10-08-02 · release-20261008-2: a duckdb pin with no order-path change; the VM was armed at this tag
- kind: release
- era: ALPACA
- date: 2026-10-08
- figures:
  - tag message: "duckdb==1.5.2 pin (research R2 layer) + test_r2 httpfs skip; no order-path change" (d769fb3, 2026-10-08 10:36:15 −0400) [S]
  - "Armed 2026-10-08 11:35 ET at `release-20261008-2`" [S]
  - release-check verdict: none recorded [U]
- source: `tag:release-20261008-2` @ `d769fb3`; `docs/ROADMAP.md` @ `82a30f6`
- supports: §2, §5
- status: superseded by release-20261011-1 (2026-10-11)

### E-2026-10-08-03 · Prod cut over from the laptop to the VM the same morning, skipping the shadow, and the VM was made fully automatic
- kind: ruling
- era: ALPACA
- date: 2026-10-08
- figures:
  - shadow: "same 8 orders; 2 names 1 share apart, explained by equity read 0.02% apart" [S]
  - cut-over "2026-10-08 11:32–11:38 ET"; laptop launchd jobs unloaded and disabled [S]
  - first VM send: "the laptop's decided plan `c5f20357…` (8 orders)", approved by the team lead and sent by the VM's 15:52 timer [S]
  - "I want the VM fully automated and deployed" — `AUTO_ARMED` after the first armed send's verify PASSes [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/ROADMAP.md` @ `82a30f6`
- supports: §4, §5
- status: current

### E-2026-10-09-01 · On 2026-10-09 the VM refused both sends on the stress cap, for a plan that took gross down, and verify read PASS
- kind: incident
- era: ALPACA
- date: 2026-10-09
- figures:
  - "projected gross $182,154.75 > max_gross_stress 1.8 x equity $100,666.16" [S]
  - sized at 1.7994× the evening's equity ($101,229.74); equity 0.56% lower at 15:52, so 1.8095× live [S]
  - the plan took gross down from $183,413.36 to $182,154.75; refusing it left the book at 1.83× [S]
  - replay of 40 recorded runs (38 replayable): the old rule passed 10-07 by $168 and 10-08 by $765, refused 10-09 by $956 at 15:52 and $702 at 15:55; the new code refuses none [S]
- source: `docs/RUNNER.md` @ `8ce0395`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §4, §5
- status: current (fixed by E-2026-10-11-01, E-2026-10-11-02)

### E-2026-10-09-02 · Real capital was planned, the target set at ≥10%/yr gross, the book made alpha-only, and EVENTS and XASSET opened as counters
- kind: ruling
- era: ALPACA
- date: 2026-10-09
- figures:
  - "≥10%/yr absolute return, measured gross of costs, with net shown beside it. Reg T for now (`max_gross_stress` 1.80). The vol target is derived under W6 (cap 20%)" [S]
  - "the real-money cost re-run is the gate for deploying any capital" [S]
  - the 27-name holdout opened for event trades; "The 2023-01-01 time holdout stays sealed" [S]
  - a passing sleeve runs "Inside the CEF account, one combined book"; dividends on paper get a third, distribution-adjusted P&L line [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §3, §4, §5
- status: superseded by E-2026-10-28-05 (2026-10-28) for "real capital soon", by E-2026-10-27-01 (2026-10-27) for "one combined book", and by E-2026-11-01-02 (2026-11-01) for "2023+ stays sealed" as applied to the core

### E-2026-10-09-03 · The research plan put C4 (the z-score on other CEF families) on the slate to add breadth, the book's binding weakness
- kind: method
- era: ALPACA
- date: 2026-10-09
- figures:
  - "The book's effective breadth is a small fraction of its name count — 1.17 on the live weights and 2.24 historically when this was written (2026-09-07 [S]) — because most of its variance is one factor: municipal CEFs against taxable ones ... This is the biggest hole in the strategy" (BRIEF.md §1) [S]
  - the group spread M5: "Taken by accident at 92.5% of risk" (BRIEF.md M5 row) [S]
  - "N independent sleeves of equal Sharpe combine to about √N times that Sharpe" (SCALING_RESEARCH_2026-10-08, "Arithmetic") [S]
  - "Return comes from breadth and the vol target"; plan row 9: "C4: discount z-score on equity, preferred and multi-asset CEF families", kill on "D1/D4, or correlation with the book ≥ 0.5" [S]
- source: `docs/BRIEF.md` @ `df87c59`; `results/cef/SCALING_RESEARCH_2026-10-08.md` @ `8315ba7`; `results/cef/RESEARCH_PLAN_2026-10-09.md` @ `deba719`
- supports: §2, §3, §6
- status: current; the 1.17 / 92.5% figure was later shown to be a 17-name fact (E-2026-10-12-02)

### E-2026-10-11-01 · The stress cap is judged on the lower of the sized and the live equity for a plan that adds gross; a plan that cuts gross always passes
- kind: ruling
- era: ALPACA
- date: 2026-10-11
- figures:
  - judging on sized equity alone "lets an adding plan exceed the derived G_stress 1.843 × live once equity falls more than 2.34% after decide" [S]
  - a no-trade day not explained by DRY_RUN, arming or a halt becomes a `MISSED:` FAIL [S]
  - pre-flight: the worst one-day loss of the book held into 2026-10-12 was $2,074.61 (2.06% of equity) on 2026-03-20 [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RUNNER.md` @ `8ce0395`
- supports: §5
- status: current

### E-2026-10-11-02 · release-20261011-1: the missed-day fix, release-check GO on cd5082e after a NO-GO on b3e4e9e
- kind: release
- era: ALPACA
- date: 2026-10-11
- figures:
  - tag message: "Missed-day fix: stress cap on the lower of sized and live equity (team lead 2026-10-11), fit rounds whole shares the safe way, missed days FAIL, evening pre-flight. Release-check GO 2026-10-11 on cd5082e." [S]
  - "Release-check of b3e4e9e (2026-10-11) said NO-GO on one order-path defect" (commit cd5082e) [S]
- source: `tag:release-20261011-1` @ `cd5082e`; `commit:cd5082e` (message body) @ `cd5082e`; `docs/RUNNER.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261014-1 (2026-10-14)

### E-2026-10-11-03 · W4: the signal the book actually trades is about half as strong as the documents quoted, and no artifact explains it
- kind: result
- era: ALPACA
- date: 2026-10-11
- figures:
  - deployed 13 with the ADV filter: IC "−0.033 (t −1.68) on 523 non-overlapping dates" [S]
  - factor alpha "t 2.94 daily on FF5 + momentum, every |β| ≤ 0.021; 3.22 monthly with Pástor–Stambaugh" [S]
  - "half the summed IC sits on December–January signal dates"; none of bounce, stale NAV, distributions, ex-dates or crises explains more than about 7% [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `results/cef/W4_ARTIFACTS_2026-10-11.md` @ `b466565`
- supports: §2, §5, §6
- status: current

### E-2026-10-12-01 · SYSTEM.md's IC row was corrected: the −0.074 is the wide 17-name set, the deployed book's is −0.033
- kind: correction
- era: ALPACA
- date: 2026-10-12
- figures:
  - wide 17-name set, no ADV filter: "−0.078, t −11.1, 2005–22; the −0.074 quoted elsewhere" [S]
  - deployed 13 with the ADV filter: "−0.033 (t −1.68)" [S]
  - record: the deployed figure for anything about the book that trades (team lead, 2026-10-12: "Corrected") [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/BRIEF.md` @ `df87c59`
- supports: §2, §5
- status: supersedes the −0.074 row as a statement about the book (provenance at tag pre-clean-slate)

### E-2026-10-12-02 · W10-B: the "BR_eff 1.17, 92.5% of risk" figure is a 17-name fact; the deployed 13's fit book had median BR_eff 3.30, and its edge is within-group selection
- kind: correction
- era: ALPACA
- date: 2026-10-12
- figures:
  - "today PC2 is 92.5%, BR_eff 1.17, net muni weight −74.9%" is "a 17-name measurement from before v7" (W10_PARTB) [U]
  - 13-name deployed fit book: BR_eff median 3.30 (p10–p90 2.25–5.55), between risk share 0.140 (W10_PARTB) [U]
  - record: W10_PARTB for the deployed 13 (the later dated note, by its method); BRIEF.md §1 still reads "1.17 on the live weights" and was not edited [S]
  - within −9.07bp/z (t −3.02), between −3.29 (t −0.87); "today's book is 67% between (long multi, short muni and JFR)" [S]
- source: `results/cef/W10_PARTB_2026-10-12.md` @ `b466565`; `docs/BRIEF.md` @ `df87c59`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §2, §3, §6
- status: current

### E-2026-10-12-03 · The real-money cost gate failed: net of measured borrow the deployed book lost money over 2021-09-14 → 2022-12-30, so real capital waits
- kind: result
- era: ALPACA
- date: 2026-10-12
- figures:
  - gross, total returns: +9.63%/yr (SR 1.57) [V]
  - measured borrow (IBKR FEE_RATE by name-date): −13.11%/yr [V]
  - net, MOC at the print: −3.51%/yr (t −0.65 / −0.64; CI [−11.5, +5.6]); net at 30bp −11.57 [V]
  - "The short book paid a short-weighted 19.91%/yr in that window, against a breakeven fee of 14.58%/yr (at MOC)" [V]
- source: `results/cef/REAL_MONEY_COSTS_2026-10-12.md` @ `7e8dc83`
- supports: §5
- status: current

### E-2026-10-12-04 · Live NAV quality: Yahoo served stale NAV copies at decision time, and real orders were sized on them
- kind: incident
- era: ALPACA
- date: 2026-10-12
- figures:
  - "stale copies at decision time on 28 of 73 checkable name-days on the laptop" [S]
  - "11 submitted orders were in a name whose own NAV" was stale [S]
- source: `results/cef/LIVE_NAV_QUALITY_2026-10-12.md` @ `eeb5cb2`; `docs/RUNNER.md` @ `8ce0395`
- supports: §2, §5
- status: current (answered by E-2026-10-13-01)

### E-2026-10-12-05 · Appendix — CORE-a/CORE-b: no distribution adjustment around specials, and no December–January tax-loss sleeve or gate
- kind: kill
- era: ALPACA
- date: 2026-10-12
- figures:
  - (a) around specials the deployed z "reads funds rich and is right (slope −49.5bp/z, t −3.76; 22 dates, D7)" [S]
  - (b) the loser/winner gradient holds in Feb–Nov too; "there are 9 seasons (D7)"; kept as a declared stratum; zero trials [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-13-01 · The stale-NAV gate was redesigned the same day to defer and hold rather than drop, and starts in report mode
- kind: ruling
- era: ALPACA
- date: 2026-10-13
- figures:
  - the first rule "Use CEFConnect, else drop" was replayed: "on 2026-10-05 the drops would have flattened the whole book" [S]
  - under the redesign, worst case "2026-10-05: 9 names held, 4 left eligible, so the whole book holds that day"; "No date flattens the book" [S]
  - "Report mode first, `on` after a measured week" [S]
  - the released book json still sets `data.stale_nav = report` at 4485a96 [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RUNNER.md` @ `8ce0395`; `ops/books/cef_discount_book.json` @ `de75da4`
- supports: §2, §5
- status: current

### E-2026-10-13-02 · Appendix — E1-G1a: E1's short-acquirer leg cannot be built at Alpaca for munis, where the merger-pair effect lives
- kind: kill
- era: ALPACA
- date: 2026-10-13
- figures:
  - pending muni acquirers "1 of 2 shortable (NZF no, MMU yes)"; historical muni acquirers "7 of 23 on today's flags: FAIL" [S]
  - taxable (78%) and equity (62.5%) pass, but their at-announcement medians (+4.6bp, +15bp [S]) are under E1's kill line; zero trials [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-14-01 · release-20261014-1: the stale-NAV gate in report mode, MISSED on a send scaled to zero, the exact fit and the third P&L line
- kind: release
- era: ALPACA
- date: 2026-10-14
- figures:
  - tag message: "stale-NAV gate in report mode (record failure never stops the session; no scripts/ on the send path); verify MISSED on a zero-order send; exact fit; phase 0 (third P&L line, borrow snapshot, ADV-NaN guard)" (0e99db2) [S]
  - "Release-check said GO on the second run, after the first run's two defects were fixed"; the first run was NO-GO on 35c6514 [S]
  - installed on the VM, armed, "at 17:05 ET, after the day's send" [S]
  - exact fit: on the 2026-10-07 plan after a 0.5% dip it keeps 98.7% of traded notional against the grid's 72.0%; mean share kept 48.3% → 60.0% over 1,741 binding draws [S]
- source: `tag:release-20261014-1` @ `0e99db2`; `commit:0e99db2` (message body) @ `0e99db2`; `docs/SYSTEM.md` @ `4ed3c04`; `docs/RUNNER.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261019-1 (2026-10-19)

### E-2026-10-14-02 · CEF 50 → 52: C5 (the opening-auction fill) became trial 51 and C4 (the z-score on five other CEF families) trial 52
- kind: counter
- era: ALPACA
- date: 2026-10-14
- figures:
  - "Both are judged at N = 52, bar √(2 ln 52) = 2.811" [S]
  - C4's holdout "ends 2026-09-30, fixed" [S]
  - C4 universe: "74 of the 105 pool funds tradable and shortable, all easy to borrow", frozen at one `GET /v2/assets` read at 2026-10-14T21:40:33Z [S]
  - by family: sector 29, covered-call 15, multi-asset 15, preferred 9, domestic 6 [S]
  - breadth: the declared C4 book's median eligible funds per session is 10 over the fit 2005–22 (13 in 2023–26); "The deployed 13 have a median of 5 eligible by the same rule over 2013–22"; "Breadth is about twice the deployed set's" [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `results/cef/PREREG_C4_FAMILIES_2026-10-13.md` @ `9131197`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §2, §6
- status: current

### E-2026-10-14-03 · C4 (CEF trial 52) passed all six fit stages: gross Sharpe 1.217 over 2005–22, positive in 16 of 18 years, with costs flipping its sign by 30bp
- kind: result
- era: ALPACA
- date: 2026-10-14
- figures:
  - 74 frozen funds, 65 with paired price and NAV before 2023; fit 2005-02-22 → 2022-12-30, 4,497 sessions, CRSP total return [S]
  - gross SR 1.217, ann 7.16%, vol 5.89%, turn 38.1/yr; net@5/15/30 0.894 / 0.247 / −0.724, flips between 15 and 30bp [S]
  - `_dsr` 0.991 at N = 52, NW t 5.32; both independent reviews confirmed the fit [S]
  - eras: 2005–09 1.135, 2010–14 1.004, 2015–19 1.217, 2020–22 1.686 [S]
- source: `results/cef/C4_RESULT_2026-10-14.md` @ `daac2bb`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §2, §6
- status: current

### E-2026-10-14-04 · Appendix — C5 (CEF trial 51), the opening-auction fill, was killed at the fit: a placebo earned more than the treatment
- kind: kill
- era: ALPACA
- date: 2026-10-14
- figures:
  - gain +293bp/yr (SR 1.16, t 2.82, 2016–22 WIDE); the same open fill on the trade decided a day earlier earns +351bp/yr [S]
  - also fails D4 (MUB β −0.22) and `_dsr` (0.61 at N = 52) [S]
  - holdout opened once on 2026-10-19 under the D-5 repair rule: G +313.6bp/yr, SR 2.12, NW t 4.66, the fit's sign; "C5 stays KILLED (D1)" [S]
  - evidence outcome (2026-10-27): gain PRESENT, lagged-placebo split INCONCLUSIVE (t −0.56) [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `results/cef/C5_RESULT_2026-10-14.md` @ `6096ef9`
- supports: §6
- status: current (D1; evidence PRESENT / INCONCLUSIVE)

### E-2026-10-14-05 · Appendix — XASSET-X1, credit and rates trend (MOP TSMOM on nine ETFs): D1
- kind: kill
- era: ALPACA
- date: 2026-10-14
- figures:
  - slate declared at N = 4, bar √(2 ln 4) = 1.665 [S]
  - sized gross Sharpe 0.41, NW t 1.62 < 1.96 (2008-05 to 2022-12); holdout Sharpe −0.39; spanned by AQR TSMOM^FI (alpha t 0.65) [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `results/xasset/XASSET_RESULTS_2026-10-14.md` @ `c52a3ec`
- supports: §6
- status: current (D1; spanned, D4 in substance)

### E-2026-10-14-06 · Appendix — XASSET-X2, front-running pension rebalancing (SPY vs IEF): D1
- kind: kill
- era: ALPACA
- date: 2026-10-14
- figures:
  - Sharpe 0.33, NW t 1.59 (2002-09 to 2022-12); the rates control scores 0.18; 57 turns a year, net −1.09 at 15bp; holdout 0.25 [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current (D1)

### E-2026-10-14-07 · Appendix — XASSET-X3, month-end Treasury extension: real effect, but term premium in a part-time wrapper (D4, and D2)
- kind: kill
- era: ALPACA
- date: 2026-10-14
- figures:
  - Sharpe 1.04, NW t 4.94; `_dsr` 0.999; but TERM β 0.34 / 0.33 (> 0.10); 58 turns a year, net −0.42 at 15bp; holdout 0.59 [S]
  - the TERM-hedged re-open was closed at the power gate on 2026-10-28: P(pass) ≤ 0.13 over 10 years [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §6
- status: current (D4; re-open UNDERPOWERED)

### E-2026-10-14-08 · Appendix — XASSET-X4, multi-asset trend: D4 on the historical-mean rule; the XASSET slate closed with no sleeve
- kind: kill
- era: ALPACA
- date: 2026-10-14
- figures:
  - Sharpe 0.45, NW t 1.964; alpha t 1.00; `_dsr` 0.58; holdout 0.19; spanned by AQR TSMOM (t 5.3) [S]
  - "XASSET is at 4 = N. The slate is closed" [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current (D4)

### E-2026-10-18-01 · C4's holdout, opened once, first read gross Sharpe 0.725 and net −0.304 at 15bp (labelled D2)
- kind: result
- era: ALPACA
- date: 2026-10-18
- figures:
  - holdout 2023-01-03 → 2026-09-30, 939 sessions: mean daily gross +2.07bp (+5.20%/yr), gross SR 0.725 (NW t 1.32) [S]
  - net 0.382 / −0.304 / −1.332 at 5 / 15 / 30bp; 2023–24 +12.78%/yr, 2025–26 −3.50%/yr [S]
  - 82% of the holdout P&L in the ex-date window [0,2] (fit 33%) [S]
- source: `results/cef/C4_RESULT_2026-10-14.md` @ `daac2bb`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §2
- status: superseded by E-2026-10-18-02 and the ruling E-2026-10-19-01 (2026-10-19)

### E-2026-10-18-02 · An independent review found four bad IGR price bars in C4's holdout; corrected, gross Sharpe is 1.434 and net at 15bp turns positive
- kind: correction
- era: ALPACA
- date: 2026-10-18
- figures:
  - four bars (2026-07-29, 08-04, 08-07, 08-11), post-split basis inside a raw pre-split series, flagged by Stage 0 Q5 on 2026-10-14 and never triaged, "costing −10.87% of capital" [S]
  - as committed: gross SR 0.725, net@5/15/30 0.382 / −0.304 / −1.332, NW t21 1.32 [S]
  - corrected: gross SR 1.434, net@5/15/30 0.999 / +0.130 / −1.174, NW t21 2.89 [V]
- source: `results/cef/C4_RESULT_2026-10-14.md` @ `daac2bb`
- supports: §2, §5
- status: supersedes E-2026-10-18-01

### E-2026-10-18-03 · Appendix — SS5-MA / SS5-IBKR: equity merger arbitrage is D4 in costume on the published evidence; IBKR's cost and unlocks measured
- kind: kill
- era: ALPACA
- date: 2026-10-18
- figures:
  - MP2001's index manager net of costs: α t 2.9, β 0.12, and β 0.49 in months below −4% (a short index put) [S]
  - regex reader right on all fields for 0 of 16 sampled deals; IBKR would short the six munis Alpaca cannot at 0.83–5.15%/yr today; zero trials [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-19-01 · C4's verdict is the corrected book: PASS, with a recorded deviation, paper only and no real-money sleeve
- kind: ruling
- era: ALPACA
- date: 2026-10-19
- figures:
  - verdict book: gross SR 1.434, net@15 +0.130; "Stage 9 (net@15 > 0) now passes, so the D2 label does not apply" [S]
  - paper only because "The grid turns negative by 30bp" and borrow is a single-snapshot counterfactual at 0.000%/yr; measured borrow cost the core 13.11%/yr over 2021-09-14 → 2022-12-30 [V]
  - "The CEF counter stays at 52" [S]
- source: `results/cef/C4_RESULT_2026-10-14.md` @ `daac2bb`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §2, §5
- status: current

### E-2026-10-19-02 · Alpaca's end-of-day portfolio history became the paper book's official daily P&L; the 17:30 reading is a labelled snapshot
- kind: ruling
- era: ALPACA
- date: 2026-10-19
- figures:
  - on four sessions (2026-09-29, 10-05, 10-07, 10-16) the snapshot "differed from Alpaca's end-of-day change on every day, by tens to hundreds of dollars" [V]
  - "The end-of-day change agreed with verify's auction-marked score to within fifty cents on every day" [V]
  - 1D stamps read at 00:00 UTC of the day after the session (2026-10-17T00:00Z carries the 2026-10-16 close) [V]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/REFERENCES.md` @ `1be6750`; `docs/RUNNER.md` @ `8ce0395`
- supports: §4, §5
- status: supersedes the 2026-09-28 "Alpaca's paper fill is the official record" reading of E-2026-09-28-04

### E-2026-10-19-03 · HALVE/KILL had been read by no code on the Alpaca path; they were wired in report mode on the official equity series
- kind: ruling
- era: ALPACA
- date: 2026-10-19
- figures:
  - "The frozen spec's two drawdown lines were read by no code on the Alpaca path, and the runner never called `risk_check`" [S]
  - series: Alpaca's end-of-day history in `<state>/eod_equity.csv`; "Absent or unreadable is UNMEASURED; never a fallback" [S]
  - "An acting mode is not built"; the book json sets `risk.drawdown = report` [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RUNNER.md` @ `8ce0395`; `ops/books/cef_discount_book.json` @ `de75da4`
- supports: §5
- status: current

### E-2026-10-19-04 · release-20261019-1: the official daily P&L is Alpaca's end-of-day history; the collector writes eod_equity.csv
- kind: release
- era: ALPACA
- date: 2026-10-19
- figures:
  - tag message: "Official daily P&L = Alpaca end-of-day history; collector writes eod_equity.csv (team lead ruling 2026-10-19). release-20261014-1 + 64c253b, 109cb2b, abc20b9. Release-check GO." [S]
- source: `tag:release-20261019-1` @ `abc20b9`
- supports: §2, §5
- status: superseded by release-20261019-2 (2026-10-20)

### E-2026-10-19-05 · Appendix — SSX-1: of 57 special-situation candidates, 8 passed a zero-trial gate and 20 were killed
- kind: kill
- era: ALPACA
- date: 2026-10-19
- figures:
  - "8 pass a gate" (D1 clustered insider buying, CR15 PFF additions, D9 earnings delay, A2, A1, D6, D8, B4); "20 killed" [S]
  - "The adversary's base rate: 2 of 207 published predictors pass the desk's D4 as published"; no trial spent [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-20-01 · release-20261019-2 (tagged 2026-10-20): the HALVE/KILL drawdown check in report mode, orders proved unchanged
- kind: release
- era: ALPACA
- date: 2026-10-20
- figures:
  - tag message: "Drawdown check HALVE/KILL in report mode (risk.drawdown = report; orders unchanged, proved); orient official P&L section; equity.csv labelled a snapshot. release-20261019-1 + 97 commits. Release-check GO (wf_2b4ca4ae-f6b)." (ebf1fac, 2026-10-20 11:39:39 −0400) [S]
- source: `tag:release-20261019-2` @ `ebf1fac`
- supports: §2, §5
- status: superseded by release-20261028-1 (2026-10-28)

### E-2026-10-20-02 · Appendix — IBKR as a second broker waits for a trigger: its benefit to the core is small and indistinguishable from zero
- kind: ruling
- era: ALPACA
- date: 2026-10-20
- figures:
  - extreme case f = 1: +0.33%/yr gross (NW t 0.26) on the deployed set, +0.76%/yr (t 0.64) on WIDE; after IBKR's own borrow and commissions +0.12 and +0.09%/yr [V]
  - VM resize USD 26.86 a month; "52 manual logins a year" [V]
  - "MHD never cleared the ADV floor before 2023, and MQY did on 3.7% of 2013-06 → 2022 sessions" while the live book holds both short at 13–26% of equity each [V]
- source: `results/ops/IBKR_WORTH_IT_2026-10-19.md` @ `a255aa7`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §5, §6
- status: current

### E-2026-10-20-03 · Appendix — EVENTS trial 2, NAV tenders: a real gross payoff that costs eat (D2 at stage 3)
- kind: kill
- era: ALPACA
- date: 2026-10-20
- figures:
  - 104 events (96 groups), 2010–22: gross +1.08% per event (cluster t 2.80), above the placebo p95 (+0.74%); net at 15bp +0.59% (t 1.53) [S]
  - sleeve gross Sharpe 0.450, net 0.381 / 0.244 / 0.037 at 5 / 15 / 30bp; D4 fails (alpha t 1.92, MUNI β 0.17); `_dsr` 0.39 at N = 6 [S]
  - holdout halted at its own 20% unread gate (14 of 42); paper admission (2026-10-28): gross Sharpe 0.055 on paper's convention, the combined book falls 0.959 → 0.738, "does not qualify" [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `results/events/NAV_TENDER_RESULT_2026-10-20.md` @ `ac2c7ca`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §6
- status: current (D2)

### E-2026-10-20-04 · Appendix — SPAC-DL: the deadline-only SPAC route is a premium in costume (D4), closed at zero trials
- kind: kill
- era: ALPACA
- date: 2026-10-20
- figures:
  - every pre-deal SPAC common 2019–22: alpha 8.93%/yr t 2.18; MKT β 0.090 daily, 0.154 weekly, 0.463 monthly; β 0.53 in months below −4% [S]
  - −6.6% over bills in Feb–Mar 2020; top 5 names 34% of gross [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §6
- status: current (D4)

### E-2026-10-20-05 · Appendix — MA-HZ, merger arbitrage on the completion-hazard hump: mechanism holds, cost marginal; WATCH, then closed UNDERPOWERED
- kind: kill
- era: ALPACA
- date: 2026-10-20
- figures:
  - hump holds on unseen 2001–09 deals (High-week hazard 0.069 vs Low-1 0.025); half-spread drag 202–233bp/yr between the decayed (174) and late-sample (276) gross; P(D4 t ≥ 3) ≈ 1–10% [S]
  - 2026-10-28: closed UNDERPOWERED, P(pass) ≤ 7% after post-publication decay [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §6
- status: current (WATCH → UNDERPOWERED)

### E-2026-10-20-06 · Appendix — A1-ISSUANCE: CEF share issuance at a premium gives no event the z-score misses; closed at zero trials
- kind: kill
- era: ALPACA
- date: 2026-10-20
- figures:
  - 33 programme events in 31 funds, 2008–22; only 7 have a premium path outside the 44; premium +10.9% at the event, live z +2.02 [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-20-07 · Appendix — A2-INSIDER: insider buying in CEFs and BDCs is the book's own signal; gate G2 fails
- kind: kill
- era: ALPACA
- date: 2026-10-20
- figures:
  - event z mean −0.35 vs +0.03 for all fund-days; matched on z, 21-session discount excess +0.15pp (t 1.09), price excess +9.5bp (t 0.44), 1,179 events 2006–22 [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-20-08 · Appendix — MUNI-HZ (B1, B2): subtract-only muni hazard flags are not worth building, not even in report mode
- kind: kill
- era: ALPACA
- date: 2026-10-20
- figures:
  - B1 fails on its source: EMMA's terms bar monitoring and "the MSRB feed costs $45,000/yr"; N-PORT default flags are quarterly, 54–59 days late [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-22-01 · The book missed 2026-10-22: one late NAV refused all 13 names, because CEFConnect had refused every scripted request since 2026-10-21
- kind: incident
- era: ALPACA
- date: 2026-10-22
- figures:
  - "PDO's NAV was late, there was no fallback, and gate 5 refused all 13" [S]
  - "CEFConnect has refused every scripted request since 2026-10-21 (JSONDecodeError)"; the collector ended INCOMPLETE and the stale-NAV gate could verify nothing (found 2026-10-29) [S]
  - CEFConnect's terms prohibit automated commercial use (2026-10-19 ruling: options brief first; NAV licensing is upstream, at Nasdaq Fund Network) [S]
- source: `docs/JOURNAL.md` @ `8ce0395`; `docs/RUNNER.md` @ `8ce0395`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §2, §5
- status: current (answered by the missing-NAV hold, E-2026-10-29-06)

### E-2026-10-22-02 · Appendix — EVENTS trial 1, E1 (the CEF merger pair): Stage 0 cleared on 2026-10-22; the fit's alpha failed D4 on power; parked until real capital
- kind: kill
- era: ALPACA
- date: 2026-10-22
- figures:
  - "Stage 0 CLEAR 2026-10-22 at 732fc9d: all seven gates pass" (RESEARCH_STATE ACTIVE row, which still says "The fit has not run") [U]
  - "muni pair median +167.4bp, t 2.79"; "D4 alpha t 1.90 < 3.0, with max |Σβ| 0.021"; the pre-registration forecast P(alpha t ≥ 3) ≈ 0.28 (DESK_METHOD, citing `E1_RESULT_2026-10-22.md` on branch trial-events-e1, not read here) [U]
  - record: the later dated DESK_METHOD note and the 2026-10-27 relabel (alpha INCONCLUSIVE); the ACTIVE row is stale [S]
  - 2026-10-28: "Parked until real capital. No paper account open to the desk processes mergers" [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `results/research/DESK_METHOD_2026-10-27.md` @ `db88b14`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §6
- status: current (D4; evidence INCONCLUSIVE)

### E-2026-10-26-01 · C4's ex-date P&L concentration was MIXED: the drift is generic, and paper overstates C4; the team lead sent C4 to paper anyway
- kind: result
- era: ALPACA
- date: 2026-10-26
- figures:
  - ex-date window P&L share: fit 33.1%; holdout 82.1% committed, 52.6% corrected [S]
  - data causes carry 12.6% of window P&L; once the z-blind ex-date profile is removed, C4's own window excess is t 1.69 against the 2.0 bar [S]
  - "Paper overstates C4: price-only Sharpe 1.360 vs total return 1.217 on the fit" [S]
  - ruling: "Proceed anyway (2026-10-26). Paper is scored against a price-only backtest" [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `docs/SYSTEM.md` @ `4ed3c04`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §5
- status: current

### E-2026-10-26-02 · Live session 2026-10-26: PASS, 6 of 6 orders filled; snapshot −$446.70, auction-marked −$520.85
- kind: live-pnl
- era: ALPACA
- date: 2026-10-26
- figures:
  - "PASS, 6 orders, 6 filled. Snapshot −$446.70 gross; auction-marked −$520.85" [V]
- source: `docs/JOURNAL.md` @ `8ce0395`
- supports: §4
- status: superseded by E-2026-11-02-03 (2026-11-02) as a P&L figure; the order count stands

### E-2026-10-26-03 · Appendix — SCR-MACRO-STATE: no fund group's own macro observable changes the within-group IC
- kind: kill
- era: ALPACA
- date: 2026-10-26
- figures:
  - no own-observable split reaches |t| 2 on the deployed 13 or the wide 17; within-muni IC holds in every SIFMA state (−0.077 to −0.123, all t ≤ −3.7) [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-26-04 · Appendix — SCR-MACRO-DAYS: discount moves on FOMC, CPI and NFP days do not revert more; the placebo scores more
- kind: kill
- era: ALPACA
- date: 2026-10-26
- figures:
  - extra reversion −6.9bp per unit (t −0.36); placebo weeks +19.1 (t +0.97); ordinary-day reversion runs through price (−37.3, t −3.39), not NAV [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-27-01 · C4 goes in its own paper account (the spare connector account), an exception to "one combined book", because one account couples the books
- kind: ruling
- era: ALPACA
- date: 2026-10-27
- figures:
  - "the runner's gates refuse a shared account (`quantt/session/gate.py` gates 6 and 9)" [S]
  - one account couples the 13 in five places: gate 9, gate 6, gate 5 ("any one missing NAV"), verify's missing print, and `max_gross_stress`'s M_other = $0 [S]
  - "An enabled C4 entry in the core book json would make the 13's refresh exit 4 every day"; the universes are disjoint (0 of 74 in the core panel [V]) [S]
  - C4's setup as a set: its own $100k, the spec's vol target, its own gross cap, no CEFConnect (the NAV-repeat mask instead) [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `results/cef/C4_DEPLOY_PLAN_2026-10-27.md` @ `da72ebb`
- supports: §3, §5
- status: current; confirmed 2026-11-02 and 2026-11-03 (E-2026-11-02-05, E-2026-11-03-06)

### E-2026-10-27-02 · The 82-kill audit: most kills were sound, but four of seven counted-trial kills since 2026-09-28 had a real gross effect killed by a gate their own power forecast said they would fail
- kind: method
- era: ALPACA
- date: 2026-10-27
- figures:
  - 82 ideas: CORRECT KILL 29, IMPLEMENTATION 26, UNDERPOWERED 20, STANDALONE 3, PROCESS ERROR 1 (C5) [S]
  - "Four of the seven counted-trial kills since 2026-09-28 (C5, E1, NAV tenders, X3) had a real gross effect that beat its own control or placebo" [S]
  - named failures: power computed and then ignored; verdicts that name the gate, not the evidence; a passing component dying with a failing expression; sleeves judged alone; a bar stricter than the method it cites [S]
- source: `results/research/DESK_METHOD_2026-10-27.md` @ `db88b14`
- supports: §2, §6
- status: current

### E-2026-10-27-03 · Research-method rulings: evidence outcomes beside every D-code, a power gate in the workflow, paper-only admission by marginal contribution, and the paper's deflated-Sharpe bar once trial series are stored
- kind: ruling
- era: ALPACA
- date: 2026-10-27
- figures:
  - "The workflow stops when any P(pass) is below 0.5, unless overridden" [S]
  - evidence outcome PRESENT / ABSENT / INCONCLUSIVE; "Only ABSENT justifies 'never re-test without new data'" [S]
  - admission by marginal contribution: "Allowed, paper only" (SR > ρ·SR_book across ρ's range and the combined net positive across 5/15/30bp) [S]
  - trial P&L series: "Backfill what is reproducible" [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §2, §5
- status: current

### E-2026-10-27-04 · The autonomous research loop: a daily cycle on the laptop that approves its own trials, and the canonical evaluate() restructured into a harness byte-identical on the live book
- kind: ruling
- era: ALPACA
- date: 2026-10-27
- figures:
  - "Who approves a trial: The loop, with no cap"; each trial is counted and stores its daily P&L [S]
  - `band_frontier.evaluate` delegates to `scripts/research/harness.py`, "byte-identical on the live book" [S]
  - revised 2026-10-28: the lab uses the spare connector account, which C4 also trades in [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`
- supports: §2, §5
- status: current; the 2026-11-02 autonomy table lists "approving a trial stays the team lead's" as unchanged, which reads against "The loop, with no cap"; not reconciled in the files read

### E-2026-10-27-05 · A "pytest exit 0" had been read through a pipe, so it measured tail's exit; re-verified and corrected
- kind: correction
- era: ALPACA
- date: 2026-10-27
- figures:
  - "commit 7c02236's 'pytest exit 0' had been read through a pipe (`| tail`) ... It was re-verified and corrected in ef6b1b4" [S]
- source: `docs/JOURNAL.md` @ `8ce0395`
- supports: §5
- status: current

### E-2026-10-27-06 · Live session 2026-10-27: PASS, 6 of 6 orders filled; snapshot +$251.43, auction-marked +$192.95
- kind: live-pnl
- era: ALPACA
- date: 2026-10-27
- figures:
  - "PASS, 6 orders, 6 filled. Snapshot +$251.43; auction-marked +$192.95" [V]
- source: `docs/JOURNAL.md` @ `8ce0395`
- supports: §4
- status: superseded by E-2026-11-02-03 (2026-11-02) as a P&L figure; the order count stands

### E-2026-10-27-07 · Appendix — SCR-IDX-REBAL: fund-of-CEF index reconstitution pressure is an artifact when pooled; the placebo scores more
- kind: kill
- era: ALPACA
- date: 2026-10-27
- figures:
  - 137 events ≥ 1 ADV: pressure +50bp (t 2.23), reversal −73bp (t −3.58); the placebo one month earlier +113bp (t 2.87) [S]
  - PCEF alone +184bp (t 5.5) then −120bp (t −5.6), a post-hoc subgroup [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-27-08 · Appendix — SCR-BDC-DISC: the discount z-score on BDCs is nothing in the tradable set; at ADV ≥ $3m it is short-term reversal
- kind: kill
- era: ALPACA
- date: 2026-10-27
- figures:
  - all 54 BDCs: IC +0.0258 (t 5.14); at ADV ≥ $3m, 2012–17 is null and the 2018–22 NAV term is t 0.48 next to 5-day reversal [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-28-01 · fetch_daily had written yfinance's empty ex-date rows over good bars; prod's panel held 91 empty closes, 24 of them on the live book
- kind: incident
- era: ALPACA
- date: 2026-10-28
- figures:
  - empty rows: "no close, volume 0"; "The laptop's refresh had blanked 15 bars; prod's panel held 91 empty closes (Feb–Apr 2026), 24 of them on the live book" [S]
  - rulings: fix the fetcher, NAV side included, in one release; repair prod's panel from Alpaca's official closing prints [S]
- source: `docs/JOURNAL.md` @ `8ce0395`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §2, §5
- status: current

### E-2026-10-28-02 · release-20261028-1: empty fetched rows and non-finite NAVs are refused (PR #6), release-check GO
- kind: release
- era: ALPACA
- date: 2026-10-28
- figures:
  - tag message: "empty fetched rows and non-finite NAVs are refused (de6e9c5; PR #6; release-check GO 2026-10-28)" [S]
  - installed 16:30 ET; "Empty price or NAV rows are never merged; NAVs must be finite (and later positive)" [V]
- source: `tag:release-20261028-1` @ `de6e9c5`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261029-1 (2026-10-29)

### E-2026-10-28-03 · Prod's panel was repaired from Alpaca's closing-auction prints; the day's plan barely moved
- kind: incident
- era: ALPACA
- date: 2026-10-28
- figures:
  - "87 closes filled from Alpaca's closing-auction prints"; one log line per cell [V]
  - "Measured effect on the day's plan: weights moved ≤ 0.0008, and PTY went flat" [V]
  - "4 NYSE American cells (DHY, EAD) are left empty. DHY's history is split-adjusted, so a raw print would be 10× off" [V]
- source: `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §5
- status: current

### E-2026-10-28-04 · The trial-series backfill: EVENTS and XASSET qualify for the paper's deflated-Sharpe bar (with safeguards); CEF stays on the desk's √(2 ln N)
- kind: method
- era: ALPACA
- date: 2026-10-28
- figures:
  - stored: EVENTS 2 of 2, XASSET 4 of 4, CEF 2 of 52 (C5 and C4) [V]
  - safeguarded hurdles (annualised): EVENTS 0.363 against the desk's 0.530; XASSET 0.337 against 0.435; unfloored, EVENTS would be 0.060 [V]
  - CEF: "every committed CEF headline before C4 and C5 used data from 2023 on"; trials 1–18 were scored at `shift(1)` [S]
  - ruling: "The desk's √(2 ln N) on the raw counter, unchanged" for CEF, because 50 of its 52 trials cannot be rebuilt [S]
- source: `results/research/BACKFILL_TRIAL_SERIES_2026-10-28.md` @ `73324fe`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §2, §6
- status: current

### E-2026-10-28-05 · Real capital is deferred until Alpaca Canada is approved; paper stays on Alpaca because no paper broker processes corporate actions
- kind: ruling
- era: ALPACA
- date: 2026-10-28
- figures:
  - "Alpaca Clearing & Custody Canada Ltd. is not yet a CIRO Dealer Member" [V]
  - "IBKR Canada is the only candidate that meets every hard requirement"; it was not chosen [V]
  - approval "takes at least six months, scope [U]"; re-check each quarter [U]
  - IBKR paper: "certain corporate actions like dividends and splits won't be processed" [V]
- source: `results/ops/BROKER_OPTIONS_CANADA_2026-10-28.md` @ `8b180ca`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §5
- status: supersedes the "real capital soon" row of E-2026-10-09-02

### E-2026-10-28-06 · A corporate-action HALT guard was ruled for the paper runner, because Alpaca paper processes no splits or mergers
- kind: ruling
- era: ALPACA
- date: 2026-10-28
- figures:
  - "paper accounts do not implement any corporate actions such as stock splits or dividends" (Alpaca staff, 2026-07-15) [V]
  - the session refuses when Alpaca lists a non-dividend corporate action naming a held or targeted name in its window, and when the list cannot be read; modes off / `report` / `halt` [S]
  - twelve months of the real feed (2025-10-29 → 2026-10-29): 3,443 rows across 13 non-dividend types [V]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RUNNER.md` @ `8ce0395`; `docs/REFERENCES.md` @ `1be6750`
- supports: §5
- status: current (shipped in report mode, E-2026-11-02-12)

### E-2026-10-28-07 · Live session 2026-10-28: PASS, 10 of 10 filled; the "equity at the close" figure was a 17:10 after-hours read
- kind: live-pnl
- era: ALPACA
- date: 2026-10-28
- figures:
  - "PASS, 10 orders, 10 filled. Snapshot +$414.46; auction-marked +$421.90" [V]
  - "Equity $99,528.31 at the close" [U]
- source: `docs/JOURNAL.md` @ `8ce0395`
- supports: §4
- status: superseded by E-2026-11-02-04 (2026-11-02): official close $99,535.06, official day +$421.21

### E-2026-10-28-08 · Appendix — A1-BOOK: the live book's shorts earned more, not less, inside share-issuance windows; blocking them would cost Sharpe
- kind: kill
- era: ALPACA
- date: 2026-10-28
- figures:
  - out − in −0.935bp per short name-day (SE 0.552), INCONCLUSIVE; blocking costs gross Sharpe 0.955 → 0.735 [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current

### E-2026-10-28-09 · Appendix — GAMMA G2 (TLT short-variance) closed UNDERPOWERED with no data pulled; GAMMA stays at 0
- kind: kill
- era: ALPACA
- date: 2026-10-28
- figures:
  - "G2's variance premium is t 1.33 before 2023, which no cost convention makes significant" [S]
  - the GAMMA holdout was touched before it was opened: on the strict window the upper bound nets −18.9 %² (t −1.12) against −18.4 (t −1.09) [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §6
- status: current (UNDERPOWERED)

### E-2026-10-29-01 · An order-path defect reached main in PR #20: gate 6 judged order lists read before the corporate-action fetch
- kind: incident
- era: ALPACA
- date: 2026-10-29
- figures:
  - "One GET that exhausts its retries takes about 250 s", so a stall could send on lists minutes old, blind to a set placed meanwhile [S]
  - "Nothing from `main`'s head is released until it is fixed" (branch `fix-gate6-stale`) [S]
- source: `docs/RUNNER.md` @ `8ce0395`; `docs/JOURNAL.md` @ `8ce0395`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §5
- status: current (fixed in release-20261102-1)

### E-2026-10-29-02 · C4's spec v1 was frozen with its own gross cap, 1.90, derived by the core's Reg T rule; the team lead ruled it is not a trial
- kind: counter
- era: ALPACA
- date: 2026-10-29
- figures:
  - G_stress = 1.900638 → 1.90; w5 = 0.0261393 ending 2008-07-23 (IGR, RQI and RNP short and rising) [S]
  - the uncapped band "reaches 3.20x and is above 1.90x on 34.1% of fit sessions" [S]
  - plateau fit gross SR: 1.60 1.247, 1.70 1.233, 1.80 1.217, 1.90 1.200, 2.00 1.185, none 1.137 [S]
  - "Not counted as a CEF trial: applying a frozen rule with no performance test, unlike trial 50"; CEF stays 52 [S]
- source: `ops/specs/c4_families.frozen.json` @ `ccf783e`; `docs/SYSTEM.md` @ `4ed3c04`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §2, §5
- status: current (spec moved to v2–v4 for trial 53, E-2026-11-02-20)

### E-2026-10-29-03 · C4 step 2: the live sleeve rebuilds trial 52's book on 907 of 907 fit sessions; at the 1.90 cap paper trades a book the trial did not test exactly
- kind: result
- era: ALPACA
- date: 2026-10-29
- figures:
  - "sessions compared 907: trial trades on 829, holds on 78; matched 907 (100.0000%)" at tolerance 1e-12 [S]
  - spec book (1.90): gross SR 1.200 TR / 1.344 PR; trial book (1.80): 1.217 / 1.360 [S]
  - re-run on spec v4 (2026-11-02): matched 907 of 907 again [S]
- source: `results/cef/c4/c4_paper_benchmark_2026-10-29.txt` @ `6f62527`; `results/cef/c4/c4_paper_benchmark_2026-11-02.txt` @ `ccf783e`
- supports: §2, §5
- status: current

### E-2026-10-29-04 · The independent risk-split review chose equal risk per account; core + C4 came to about 9% gross on the fit
- kind: result
- era: ALPACA
- date: 2026-10-29
- figures:
  - "Core + C4 is about 9% gross on the fit, with a realistic Sharpe of 1.2–1.5 and P(HALVE in 12m) of 4–6%. Three sleeves is about 10.6% in-sample. Reg T binds before KILL" (journal; its owner, scratchpad `alloc/` and `alloc_review/`, is not committed) [U]
- source: `docs/JOURNAL.md` @ `8ce0395`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §5
- status: superseded by the 2026-10-30 sizing ruling (E-2026-10-30-02)

### E-2026-10-29-05 · "Add all 3": C4, the ex-date short as a forward test and PCEF (EVENTS trial 4) were all to go to paper at a full equal-risk share
- kind: ruling
- era: ALPACA
- date: 2026-10-29
- figures:
  - PCEF as "EVENTS trial 4 (N = 8) in a third paper account"; "Its counter moves in the commit that records its pre-registration" [S]
  - "Full equal-risk share for every sleeve from day one" [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §5
- status: superseded by E-2026-10-30-02 (2026-10-30): core + C4 only; the ex-date short and PCEF built but off

### E-2026-10-29-06 · One missing NAV no longer refuses the book: the fund is held for at most 2 sessions (a policy, not derived) and the rest trade; switched ON the same day
- kind: ruling
- era: ALPACA
- date: 2026-10-29
- figures:
  - limit `data.missing_nav_max_sessions` = 2; "prod's NAV panel (copy of 2026-10-28) shows no gap in 12 months", and PDO's 10-22 gap was one session long [S]
  - refused as before past `gate.max_missing_nav_holds` = n − `min_names` missing NAVs [S]
  - "Switched ON 2026-10-29 (`release-20261029-3`)"; the collector records CEFConnect as an unavailable second source [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RUNNER.md` @ `8ce0395`; `ops/books/cef_discount_book.json` @ `de75da4`
- supports: §2, §5
- status: current

### E-2026-10-29-07 · release-20261029-1: the multi-sleeve combiner, dark for the one-sleeve book, GO after a first NO-GO on two defects
- kind: release
- era: ALPACA
- date: 2026-10-29
- figures:
  - tag message: "multi-sleeve combiner, dark for the one-sleeve book; stale-NAV gate on fetch exit 4; overlapping universes refused (bd87144; PR #19; release-check GO 2026-10-28)" [S]
  - "The first release-check was NO-GO on two defects, both fixed"; installed 10:36 ET [V]
- source: `tag:release-20261029-1` @ `bd87144`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261029-2 (2026-10-29)

### E-2026-10-29-08 · release-20261029-2: the missing-NAV hold built dark, CEFConnect-down status and NYSE American/Nasdaq official closes; both reviewers GO
- kind: release
- era: ALPACA
- date: 2026-10-29
- figures:
  - tag message: "missing-NAV hold for gate 5 (dark, data.missing_nav) with a 2-session limit and the min_names refusal; collector reports CEFConnect down; NYSE American and Nasdaq official closes; C4 sleeve keys (no-op when absent). PR #21. quant-reviewer GO ... + execution-trader GO (run separately after the workflow failed to start it)" [S]
  - installed 19:04 ET [V]
- source: `tag:release-20261029-2` @ `5e627ff`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261029-3 (2026-10-29)

### E-2026-10-29-09 · release-20261029-3: the missing-NAV hold switched ON, deliberately excluding PR #20's corporate-action gate; the VM armed at it
- kind: release
- era: ALPACA
- date: 2026-10-29
- figures:
  - tag message: "missing-NAV hold ON (data.missing_nav hold, missing_nav_max_sessions 2; team lead 2026-10-29). Book json + one test only over release-20261029-2; excludes PR #20's corporate-action gate (merged later, NO-GO). quant-reviewer GO (wf 2026-10-29 on cee16ad) + execution-trader GO (separate run)" [S]
  - every release that day "passed a release-check (both reviewers) and a history replay (0 new refusals), and was applied with `--armed`"; installed 20:20 ET [V]
- source: `tag:release-20261029-3` @ `cee16ad`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261102-1 (2026-11-02)

### E-2026-10-29-10 · The corporate-action gate's windows and malformed rows were ruled: two windows, and a malformed row is skipped and recorded unless it could be ours
- kind: ruling
- era: ALPACA
- date: 2026-10-29
- figures:
  - a merger acquirer and a process-date-only match use the short window `(as-of, session]`; every other role keeps the long window back to when the name's shares were last set [S]
  - "Skip it, and record it, unless it could concern one of our funds; refuse only then" [S]
  - a stuck backfilled action "clears by the team lead's recorded acknowledgement of that action ID only (`ca-ack` CLI, logged)" [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`
- supports: §5
- status: current (the missing-party case was re-ruled on 2026-11-02, E-2026-11-02-01)

### E-2026-10-29-11 · Live session 2026-10-29: PASS, 3 of 3 filled; the "equity at the close" figure was again a 17:10 read
- kind: live-pnl
- era: ALPACA
- date: 2026-10-29
- figures:
  - "PASS, 3 orders, 3 filled. Snapshot +$78.64; auction-marked −$13.43" [V]
  - "Equity $99,530.59 at the close" [U]
- source: `docs/JOURNAL.md` @ `8ce0395`
- supports: §4
- status: superseded by E-2026-11-02-04 (2026-11-02): official close $99,521.57, official day −$13.49

### E-2026-10-29-12 · Appendix — EVENTS trial 3, the post-ex-date short: passes D4 on the full 2005–22 fit but every era fails alone; kept built and off as a forward test
- kind: kill
- era: ALPACA
- date: 2026-10-29
- figures:
  - approved 2026-10-27 at N = 7, bar √(2 ln 7) = 1.973; part (a) withdrawn on power (expected t 0.80) [S]
  - full fit: "+11.6bp per event, t 3.87, alpha t 4.57, rate betas ≈ −0.05. Every 3.8-year era fails D4 on its own"; amendment 1 (a duration hedge) was worse and withdrawn [S]
  - Stage 0 CLEAR on 649 events; `open` (the sealed 2023+ test) waits on French's 202610 vintage; not run [S]
  - 2026-10-30: built but off, "because they lower the percentage" [S]
- source: `docs/JOURNAL.md` @ `8ce0395`; `docs/RESEARCH_STATE.md` @ `5dbd739`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §6
- status: current (no verdict; forward test, off)

### E-2026-10-29-13 · Appendix — EVENTS trial 4, PCEF reconstitution: approved, weakly powered, built and kept off; its counter never moved
- kind: kill
- era: ALPACA
- date: 2026-10-29
- figures:
  - "PCEF pre-registration drafted: about 23 test events, so power is weak" [S]
  - EVENTS counter reads 3 at 5dbd739; the PCEF pre-registration is not on main [S]
  - 2026-10-30: "PCEF's $100k sits idle on 93% of days"; built but off [U]
- source: `docs/JOURNAL.md` @ `8ce0395`; `docs/RESEARCH_STATE.md` @ `5dbd739`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §6
- status: current (off; no verdict)

### E-2026-10-30-01 · Four sleeves across three $100k accounts would give only about 6.1%/yr gross; core + C4 gives about 9%
- kind: result
- era: ALPACA
- date: 2026-10-30
- figures:
  - "The four-sleeve, three-account split (zero trials, fit) gives 6.1%/yr gross at full equal shares. Reg T caps each account, and PCEF's $100k sits idle on 93% of days. Core + C4 gives about 9%" (journal; owner scratchpad `alloc4/NOTE.md`, not committed) [U]
- source: `docs/JOURNAL.md` @ `8ce0395`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §5
- status: current

### E-2026-10-30-02 · The book optimises % return on all capital: core + C4 only, the ex-date short and PCEF built but off, and the core's vol-target raise pre-registered as trial 53
- kind: ruling
- era: ALPACA
- date: 2026-10-30
- figures:
  - "Core + C4 at their per-account equal-risk multipliers (core ×1.24, C4 ×1.41, 5.75% combined target; about 9% gross on the fit)" [S]
  - "C4's HALVE/KILL drawdown levels: The core's levels, in report mode" [S]
  - "Invesco gave written consent" for PCEF holdings (team lead, 2026-10-30) [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §4, §5
- status: supersedes E-2026-10-29-05; the multipliers were superseded by trial 53's approval (E-2026-11-01-01)

### E-2026-10-30-03 · The corporate-action gate's release-check found a second order-path defect: rows with a null id were de-duplicated as one
- kind: incident
- era: ALPACA
- date: 2026-10-30
- figures:
  - "two rows with `id: null` counted as one, and the second was dropped. In the reviewer's probe that was a split effective on the session date, and the gate read CLEAR under `halt`" (release-check of 9630322) [S]
- source: `docs/RUNNER.md` @ `8ce0395`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §5
- status: current (fixed from 9cf5cf2)

### E-2026-10-30-04 · Live session 2026-10-30, the first with the missing-NAV hold on: PASS, 7 of 7 filled
- kind: live-pnl
- era: ALPACA
- date: 2026-10-30
- figures:
  - "2026-10-30 PASS, 7 orders, 7 filled (the first session with the missing-NAV hold on)" [V]
  - "Equity $99,124.35 at the close" [U]
- source: `docs/JOURNAL.md` @ `8ce0395`
- supports: §4
- status: superseded by E-2026-11-02-04 (2026-11-02): official close $99,017.86, official day −$503.71

### E-2026-11-01-01 · CEF 52 → 53: the vol-target raise was approved at the milder pair, core ×1.13 and C4 ×1.27, through a new `sizing_multiplier` key; spec v8 activated
- kind: counter
- era: ALPACA
- date: 2026-11-01
- figures:
  - derived 1.1357 / 1.2712 at a 5.25% combined target, rounded down to 1.13 / 1.27; chosen over the draft's ×1.24 / ×1.39 at 5.75% [V]
  - "Judged at N = 53, bar √(2 ln 53) = 2.818"; the raise claims no Sharpe and is judged by its stops [S]
  - expected (fit, model): combined 8.50%/yr TR, 9.18% PR, Sharpe 1.681 / 1.756; net +6.63 / +2.88 / −2.73 %/yr at 5 / 15 / 30bp [V]
  - core account P(HALVE, 12m, zero edge, through 2008) 7.2 / 15.2 / 51.4% (min/median/max); C4 16.3% [V]
  - stops at approval: core R1 11.17%, R2 −3.52%, R3 12.12% [V]
  - framework gate on a vol increase "Waived for paper only ... Never for real money"; core activation eca5feb (v7 → v8) [S]
- source: `results/cef/PREREG_VOLTARGET_2026-10-30.md` @ `debb128`; `docs/RESEARCH_STATE.md` @ `5dbd739`; `docs/SYSTEM.md` @ `4ed3c04`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by E-2026-11-02-17 (2026-11-02) in its multipliers and stops; the trial and its key stand

### E-2026-11-01-02 · The core's 2023+ is not sealed: its 2024–26 returns were opened on 2026-07-31 and the v7 pre-registration computed 2013-06-14 → 2026-09-21
- kind: correction
- era: ALPACA
- date: 2026-11-01
- figures:
  - "its 2024-01-01 → 2026-07-30 returns were opened on 2026-07-31 (`pre-clean-slate:results/cef/HOLDOUT_OPENED.json`, FAIL on net, for z 63)" [S]
  - "the v7 pre-registration then computed the deployed book over 2013-06-14 → 2026-09-21" [S]
  - "Treat the core's 2023+ as seen. The rule still holds for any book whose 2023+ has not been computed" [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §2, §5
- status: supersedes the 2026-10-09 "2023-01-01 time holdout stays sealed" as applied to the core

### E-2026-11-01-03 · After two more corporate-action NO-GOs, "any null party symbol refuses" was recorded as a team-lead ruling; it was not one
- kind: correction
- era: ALPACA
- date: 2026-11-01
- figures:
  - release-checks NO-GO on 10-30 (null `id` de-duplication) and 11-01 (null subject, then null acquirer, skipped as "not ours") [S]
  - the rule was recorded on 2026-11-01 as "any null party symbol refuses" [S]
- source: `docs/JOURNAL.md` @ `8ce0395`; `docs/RUNNER.md` @ `8ce0395`
- supports: §5
- status: superseded by E-2026-11-02-01 (2026-11-02)

### E-2026-11-02-01 · The null-party rule was corrected: a row with a missing party symbol halts only where a well-formed row would halt for one of our held funds, and ca-ack clears it on its full content
- kind: correction
- era: ALPACA
- date: 2026-11-02
- figures:
  - the 2026-11-01 "any null party refuses" rule "would stop the book indefinitely: one malformed row anywhere in the market halts every session, and `ca-ack` could not clear it" (release-check of 709d6cb) [S]
  - "It was the agent's reading of ruling A, so it is corrected in place in `docs/SYSTEM.md` §5" [S]
  - team lead, 2026-11-02: it halts only "when a well-formed row with the same type and dates would halt for one of our held funds"; outside those windows it is recorded only [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/JOURNAL.md` @ `8ce0395`; `docs/RUNNER.md` @ `8ce0395`
- supports: §5
- status: supersedes E-2026-11-01-03

### E-2026-11-02-02 · The corporate-action reader now validates every field; the journal and the runner design give different failure counts for the property test on 1c64638
- kind: correction
- era: ALPACA
- date: 2026-11-02
- figures:
  - "A property test (4,598 adversarial cases) fails 794 on 1c64638 and 0 on a40170c" (JOURNAL.md) [U]
  - "On 1c64638 the property test fails 2026 of its 4598 cases; 794 of those raise" (RUNNER.md) [U]
  - record: RUNNER.md, the design that owns the gate; the journal says "It owns nothing ... If this journal and an owner disagree, the owner is right" [S]
- source: `docs/JOURNAL.md` @ `8ce0395`; `docs/RUNNER.md` @ `8ce0395`
- supports: §5
- status: current

### E-2026-11-02-03 · Reconciled against Alpaca's official closes, the desk's own records had flattered the account: the 17:30 snapshot ran $560 too favourable over 10-07..10-30
- kind: correction
- era: ALPACA
- date: 2026-11-02
- figures:
  - 10-07..10-30 total: Alpaca official end-of-day (the P&L of record) −$1,794.53 [U]
  - same window: auction-marked score −$1,789.74 ($4.79 from official; never more than $0.69 on a day) [U]
  - same window: 17:30 snapshot (`alpaca_equity_change_usd`) −$1,234.29, "+$560.24: after-hours marks" [U]
  - record: Alpaca official end-of-day history (the broker, SYSTEM.md §0 rank 1; team lead ruling 2026-10-19) [S]
  - `equity.csv`'s 17:10 read differs from the official close by $52.88 a day on average, at most $332.00 (10-09) [S]
  - "This journal's 10-26..10-30 snapshots sum to −$89.05; official is −$424.44" [S]
  - "Official total since $100,000, to the 10-30 close: −$982.14" [V]
  - days with no score at all, 2026-09-30..10-02 and 10-06: official −$192.97, +$626.70, $0.00, +$252.63 [S]
- source: `docs/JOURNAL.md` @ `8ce0395`
- supports: §4, §5
- status: supersedes the snapshot figures of E-2026-10-26-02 and E-2026-10-27-06 as P&L

### E-2026-11-02-04 · The journal's "equity at the close" for 10-28, 10-29 and 10-30 were 17:10 ET after-hours reads; the official closes differ
- kind: correction
- era: ALPACA
- date: 2026-11-02
- figures:
  - 10-28: $99,528.31 (17:10 read) against the official close $99,535.06; official day +$421.21 [U]
  - 10-29: $99,530.59 (17:10 read) against $99,521.57; official day −$13.49 [U]
  - 10-30: $99,124.35 (17:10 read) against $99,017.86; official day −$503.71 [U]
  - record: the official close (Alpaca end-of-day history, the broker) [S]
- source: `docs/JOURNAL.md` @ `8ce0395`
- supports: §4
- status: supersedes the equity figures in E-2026-10-28-07, E-2026-10-29-11, E-2026-10-30-04

### E-2026-11-02-05 · Trial 53 ships tonight even if the gate fails review, and C4 uses the existing spare account: no new account, and not inside the core's
- kind: ruling
- era: ALPACA
- date: 2026-11-02
- figures:
  - "if the gate fails its release-check, the book runs with `corporate_actions` in report mode (records, does not block). Prod had no gate at all before this" [S]
  - C4 inside the core's account was declined: "shared gross cap, the combiner cannot yet run with the missing-NAV hold, and the trial-53 sizing assumes two accounts" [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §5
- status: current

### E-2026-11-02-06 · The release-check of 3478159 was NO-GO on three market-wide unresolved rows; the corporate-action gate shipped in report mode under the fallback ruling
- kind: incident
- era: ALPACA
- date: 2026-11-02
- figures:
  - "Today's real feed carries three market-wide rows with a missing party symbol: a partial call, an SNTI spin-off and a JAGX merger"; under halt each halts for every held fund [S]
  - "`ca-ack` could write a file the gate then rejects"; "Two no-op pins still skipped on the v7 hash" [S]
  - book json `corporate_actions.mode = report` at release; the bond-ISIN misread must be fixed before it returns to `halt` [S]
- source: `docs/JOURNAL.md` @ `8ce0395`; `ops/books/cef_discount_book.json` @ `de75da4`
- supports: §5
- status: current

### E-2026-11-02-07 · Alpaca's winter end-of-day stamps are 01:00Z, which the client refused; from 11-02 the official P&L would have stayed PENDING
- kind: incident
- era: ALPACA
- date: 2026-11-02
- figures:
  - "Alpaca's winter end-of-day stamps are 01:00Z (20:00 EST), and the client accepted only 00:00Z" [S]
  - "prices and NAVs are unaffected, since collector steps are independent. Fixed in this release" [S]
- source: `docs/JOURNAL.md` @ `8ce0395`; `docs/REFERENCES.md` @ `1be6750`
- supports: §5
- status: current

### E-2026-11-02-08 · Paper does charge SEC and CAT regulatory fees on this account, contradicting CLAUDE.md landmine 1; the team lead deferred the correction
- kind: correction
- era: ALPACA
- date: 2026-11-02
- figures:
  - CLAUDE.md landmine 1: paper charges "no borrow, no dividends and no regulatory fees [V: docs]" [U]
  - broker: "GET /v2/account/activities/FEE lists 37 REG (SEC) and CAT rows, summing to −6.16" over 09-29..10-30; the per-session totals equal the modelled fees on 34 of 34 sessions [U]
  - record: the broker's FEE activities (SYSTEM.md §0 rank 1); "The paper-fees correction ... Not yet (2026-11-02)" [S]
- source: `results/cef/LIVE_ATTRIBUTION_2026-11-02.md` @ `32d9961`; `CLAUDE.md` @ `9cd5951`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §4, §5
- status: current

### E-2026-11-02-09 · Live attribution 09-29 → 10-30: the signal's discount leg earned +$1,583; unchosen NAV exposure, mostly the muni shorts, lost −$2,251
- kind: live-pnl
- era: ALPACA
- date: 2026-11-02
- figures:
  - official EOD equity change 09-28 close → 10-30 close −982.14 USD; rebuilt hold + fill + fees −982.14; largest single-session residual 0.00 over 34 sessions [V]
  - hold −667.27 = NAV part −2,250.74 + discount part +1,583.47 USD [V]
  - muni group NAV part −1,849.36 USD (short MQY/MHD), after 10-13 [V]
  - fill against that day's close −308.71 USD (−5.5bp) on $558,926.55 traded; regulatory fees −6.16 [V]
  - distributions paper did not book +320.85 USD (long +956.04, short −635.19) [V]
  - EOD equity peak 2026-10-12, 101,474.24; 10-13..10-30 fill −9.5bp [V]
- source: `results/cef/LIVE_ATTRIBUTION_2026-11-02.md` @ `32d9961`
- supports: §4, §5
- status: current

### E-2026-11-02-10 · Live fill cost and live turnover: two zero-trial notes measure them on different windows and reach different readings
- kind: result
- era: ALPACA
- date: 2026-11-02
- figures:
  - fill vs close −5.5bp on $558,926.55 traded, 09-29..10-30 (LIVE_ATTRIBUTION, reconciled to the official EOD to $0.00) [U]
  - "The late-market fill cost (5.1bp vs close) is the quoted half-spread (6.2bp) less about 1bp of drift"; "The live account traded $570,482 in 20 sessions on about $100,000: 5.7× capital", against the fit's 20-session 95th percentile 4.42× (UNIQUE_ANGLES) [U]
  - "The live rate of about 58.7/yr [U] ... matches the policy's trailing-year rate: 57.2/yr"; "I found no sign that the live book trades more than the policy" (turnover-live) [U]
  - record: for fill cost, LIVE_ATTRIBUTION (broker-reconciled); for turnover neither is a broker figure, and the two compare against different baselines (fit windows vs the policy's trailing year) [S]
- source: `results/cef/LIVE_ATTRIBUTION_2026-11-02.md` @ `32d9961`; `results/cef/screens_2026-11-02/UNIQUE_ANGLES.md` @ `69609e6`; `results/backtests/turnover-live-2026-11-02/REPORT.md` @ `32f69df`
- supports: §4, §5
- status: current

### E-2026-11-02-11 · The canonical harness holds the last target on thin sessions where the live sleeve flattens, so the fit-era cost case for the live policy was weaker than stated
- kind: correction
- era: ALPACA
- date: 2026-11-02
- figures:
  - "Thin, held books earn 3,484 of the 4,531 fit-period P&L days"; they carry 1.41 of the fit period's 3.29%/yr [V]
  - under the live flatten rule, "Fit break-even is 18.6bp, against 45.8bp on the hold book. H13 break-even is 23.8bp under either rule" [V]
  - "There has been no thin session since 2026-09-28" [V]
- source: `results/backtests/turnover-live-2026-11-02/REPORT.md` @ `32f69df`
- supports: §2, §5
- status: current (fed trial 53 amendment 1, E-2026-11-02-17, and trial 55)

### E-2026-11-02-12 · release-20261102-1: CEF trial 53 live at ×1.13 (spec v8), the corporate-action gate in report mode, the gate-6 fix and the winter stamp fix; GO after six NO-GOs
- kind: release
- era: ALPACA
- date: 2026-11-02
- figures:
  - tag message: "CEF trial 53 (spec cef_discount.v8.20261101, sizing_multiplier 1.13); corporate-action gate in report mode; gate-6 fresh reads; winter EOD stamps" (f83b2a3; PR #28, merged as 862b1d0) [S]
  - "The release-check was GO on f83b2a3, after NO-GOs on 9630322, 9cf5cf2, 04aca24, 709d6cb, 1c64638 and 3478159" [V]
  - "History replay: 67 runs, 0 refused now. Dry run clean. Applied with `--armed`"; first decided at the 22:00 ET slot [V]
  - main's CI had been red since 2026-10-29 on a research test needing `arch`; PR #29 (26ed351) made it green [S]
- source: `tag:release-20261102-1` @ `f83b2a3`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261103-1 (2026-11-03)

### E-2026-11-02-13 · Autonomy: agents may run releases and arming end to end when every gate passes; the journal is the only notice
- kind: ruling
- era: ALPACA
- date: 2026-11-02
- figures:
  - "Do the trades need the team lead's approval? No, and they never did. The VM has been armed since 2026-10-08" [S]
  - unchanged: `DRY_RUN=1` set by the team lead wins; credentials are never read or moved; "approving a trial stays the team lead's" [S]
  - agents merge "with `--admin`, only after CI has passed on the PR's exact head" [S]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §5
- status: current

### E-2026-11-02-14 · Two accounts as one portfolio: arming C4 is the largest available gain, about +6%/yr gross on all capital, and the accounts are uncorrelated
- kind: result
- era: ALPACA
- date: 2026-11-02
- figures:
  - arm C4 at ×1.27: +6.0 / +5.4 %/yr gross on all capital (PR / TR, W1); combined Sharpe 0.97 → 1.84 PR; net +4.5 / +1.5 / −3.1 at 5 / 15 / 30bp, flips [V]
  - daily ρ core–C4, W1 2013-06 → 2022: +0.011 (−0.029, +0.055) [V]
  - "Reg T's 2× never binds"; joint re-split +0.07 / +0.10, "On a plateau and inside the noise" [V]
  - "The fit's core book never held the muni group": MHD clears the ADV floor on 0% of W1 sessions [V]
- source: `results/cef/screens_2026-11-02/PM_TWO_ACCOUNTS.md` @ `69609e6`
- supports: §2, §3, §5
- status: current

### E-2026-11-02-15 · Thin sessions: the harness's hold rule out-earned the live flatten rule on the fit, but the gap is one name, ten days and one stretch, not alpha
- kind: result
- era: ALPACA
- date: 2026-11-02
- figures:
  - hold − flatten, fit before 2023: +1.71pp/yr (NW t 2.13); 2015–19 +4.76 (1.81); H13 2023 on −0.02 (−0.03) [V]
  - "Take PHK's own P&L out of the gap and the fit edge falls from 1.71 to 0.58pp/yr (t 0.87)" [V]
  - "The ten best days of the gap in 2015-19 sum to 23.77pp, against an era total of 23.74pp" [V]
  - report labelled 2026-11-03, committed 2026-11-02 21:44 −0500 (c7a1635) [S]
- source: `results/backtests/thin-days-2026-11-03/REPORT.md` @ `c7a1635`
- supports: §2, §5
- status: current

### E-2026-11-02-16 · Trial 53 re-measured on the live flatten rule: the core is flat on 56% of W1, and the same sizing rule on the sessions it trades gives ×1.30
- kind: result
- era: ALPACA
- date: 2026-11-02
- figures:
  - "W1 sessions on which the core earns: 1,045 of 2,398 (43.6%)" [V]
  - core unit daily sd: hold 0.004095; flatten 0.002351 calendar, 0.003556 on earning sessions [V]
  - the rule literally (calendar sd): core 1.9675 → 1.96, C4 1.2642 → 1.26; on earning sessions: core 1.3007 → 1.30 [V]
  - at ×1.13 on earning sessions zero-edge P(HALVE) / P(KILL) 10.3% / 0.66% against 15.9% / 1.5% approved on the hold book [V]
  - the hold-calibrated stops under-fire while the book trades: 0.4% (R1), 3.1% (R2), 3.6% (R3) against a 5% design [V]
  - the note recommended keeping ×1.13 and amending only the stops; ×1.30 was "The team lead's alternative" [S]
- source: `results/cef/prereg_voltarget/FLATTEN_REMEASURE_2026-11-02.md` @ `50af817`
- supports: §2, §5
- status: current

### E-2026-11-02-17 · Trial 53 amendment 1: core ×1.13 → ×1.30 (spec v9), C4 ×1.27 → ×1.26 (spec v4), the core's stops recalibrated; CEF stays 53
- kind: counter
- era: ALPACA
- date: 2026-11-02
- figures:
  - approved "about 22:00 ET"; "It is an amendment, NOT a new trial: CEF stays 53"; bar stays 2.818 [S]
  - while trading at ×1.30, zero-edge P(HALVE) / P(KILL) in 12 months 16.7% / 1.68% [V]
  - new core stops R1 10.14%, R2 −3.06%, R3 12.07%; C4 at ×1.26 R1 10.04%, R2 −3.02%, R3 9.90% [V]
  - expected core account: 3.78%/yr over the calendar and 8.67%/yr while trading (SR 1.222); combined +0.21pp/yr (model) [V]
  - the literal ×1.96 "was not chosen"; activation commits 82a30f6 (core v8 → v9) and ccf783e (C4 v3 → v4) [S]
- source: `results/cef/PREREG_VOLTARGET_2026-10-30.md` @ `debb128`; `docs/SYSTEM.md` @ `4ed3c04`; `docs/RESEARCH_STATE.md` @ `5dbd739`; `git-log:ops/specs/` (commit subjects 82a30f6, ccf783e) @ `ccf783e`
- supports: §2, §5
- status: supersedes the values of E-2026-11-01-01

### E-2026-11-02-18 · C4's corporate-action halt was measured on today's unresolved rows; C4's gate was ruled into report mode, as the core's
- kind: result
- era: ALPACA
- date: 2026-11-02
- figures:
  - on a replica of the three unresolved rows "a flat C4 book is refused only on 11-03 (the JAGX merger); a held one on every session" [S]
  - on every unresolved row in the day's read "a flat book would have been refused on 17 of the 23 sessions from 10-01 to 11-02 [U: feed as read today]" [U]
  - ruled: "C4's gate runs in REPORT, as the core, until the ISIN fix and the re-ruling of the unresolved rows land" [S]
- source: `docs/JOURNAL.md` @ `8ce0395`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §5
- status: current

### E-2026-11-02-19 · The release-check of 8b14298 was NO-GO: C4 could decide on an unruled spike bar on a day with a late NAV; fixed by exit-code precedence
- kind: incident
- era: ALPACA
- date: 2026-11-02
- figures:
  - "C4's fetch exited 4 (INCOMPLETE) over 6 (unruled spike), and C4's missing-NAV hold accepts 4 at the final check"; now 6 outranks 4 [S]
  - "The core runs no spike guard: its fetch is still proved byte-identical to cee16ad's" [S]
- source: `docs/JOURNAL.md` @ `8ce0395`
- supports: §5
- status: current

### E-2026-11-02-20 · C4's spec moved v1 → v4 before arming: ×1.27 (v2), the core's halve/kill levels in report (v3), ×1.26 (v4)
- kind: counter
- era: ALPACA
- date: 2026-11-02
- figures:
  - v2.20261101: `sizing_multiplier` 1.27 (3961ba7); v3.20261102: the core's halve/kill levels, report only (8c92088); v4.20261102: 1.26 (ccf783e) [S]
  - at 1.26 (fit only): W1 10.05%/yr total return, SR 1.449; at the cap's decided-gross line on 46.2% of W1 sessions; zero-edge P(HALVE) 15.95%, P(KILL) 1.52% through 2008 [S]
  - "The unit book's effective cap is 1.90 / 1.26 = 1.508"; effective ex-ante vol target 0.06 × 1.26 = 7.56% [S]
  - C4 spends no trial; "the CEF counter is 53 because of trial 53, not C4" [S]
- source: `ops/specs/c4_families.frozen.json` @ `ccf783e`; `docs/RESEARCH_STATE.md` @ `5dbd739`; `results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md` @ `8ce0395`; `git-log:ops/specs/` (commit subjects 3961ba7, 8c92088, ccf783e) @ `ccf783e`
- supports: §2, §5
- status: current

### E-2026-11-02-21 · The research loop's standing exception lets it trade in the same spare account C4 will use; the account read flat, and the loop must be confirmed off before C4 arms
- kind: incident
- era: ALPACA
- date: 2026-11-02
- figures:
  - "That account is flat today [V, connector read: $100,000 cash, no positions]" [V]
  - "The repository has no lab book today (`BOOKS` holds `cef` and `c4` only), and the loop's wrapper denies `python3 -m quantt.session` and holds no key file" [S]
- source: `docs/JOURNAL.md` @ `8ce0395`; `results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md` @ `8ce0395`
- supports: §5
- status: current

### E-2026-11-02-22 · The 2026-11-02 alpha slate found one signal to pursue: C4's discount level against its family peers, which the z-score cannot see; it went to a pre-registration
- kind: result
- era: ALPACA
- date: 2026-11-02
- figures:
  - S5-C4 (monthly, yfinance leg, fit only): book gross SR +1.12, 5.77%/yr, turn 5.4; net +1.06 / +0.96 / +0.80 at 5/15/30bp, no flip [S]
  - NC1 NAV leg −0.26bp/pp (t −0.32); placebo 20 of 20; corr with C4's z book +0.10; "Equal-risk blend SR 1.52 vs z alone 1.13" [S]
  - the same signal on the credit names fails its own control: NAV leg +1.17bp/pp (t 3.01) [S]
  - expected "+0.4 to +1.0%/yr [model, U]", corrected from +0.8 to +1.5 once the shared 1.90 cap was measured [U]
  - ruling: "The C4 family-level discount signal only" goes to a pre-registration; Gate 0 (survivorship with dead funds) before any 2023+ return [S]
- source: `results/cef/screens_2026-11-02/ALPHA_SLATE.md` @ `4ed3c04`; `docs/SYSTEM.md` @ `4ed3c04`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §6
- status: current

### E-2026-11-02-23 · Gate 0 became a post-data judgment ("keep it flexible and make judgment off results"); the first CRSP pull was too thin to test survivorship
- kind: ruling
- era: ALPACA
- date: 2026-11-02
- figures:
  - "A gate decided after its data have been seen is not a pre-registered gate ... It cannot claim a pre-registered pass" [S]
  - pull 1: 1,003 CEF permnos; "0 of 36 matches are on CUSIP. 34 are recycled tickers"; only 2 genuine, 9 fund-half-years [S]
  - survivors' semiannual slope b_A −27.24bp/pp (t −4.55); with pull 1's NAVs P(flag | halving) = 0.00 [S]
- source: `results/cef/PREREG_C4_LEVEL_2026-11-02.md` @ `4ed3c04`
- supports: §2, §5
- status: current

### E-2026-11-02-24 · Appendix — the rest of the 2026-11-02 alpha slate: tax-loss on WATCH; distribution cuts, lead-lag, fast/slow z and own-name corporate events killed
- kind: kill
- era: ALPACA
- date: 2026-11-02
- figures:
  - S1 tax-loss WATCH: discount leg t 3.54, but tradable price TR +191 (t 1.25); P(pass) 0.06 [S]
  - S2 distribution cuts KILL as a sleeve (D2): cut-book gross SR 0.33, net 0.20 / −0.06 / −0.45 [S]
  - S3 lead-lag KILL (D1): wrong sign, −40bp per pp (t −2.16) [S]
  - S4 fast + slow z KILL (graveyard `z_window = 63`); S6 own-name events KILL (D7): 0 NAV tenders on the deployed 13, 2005–22 [S]
- source: `results/cef/screens_2026-11-02/ALPHA_SLATE.md` @ `4ed3c04`
- supports: §6
- status: current

### E-2026-11-02-25 · Appendix — the 2026-11-02 unique angles: turn-of-month found post hoc and left on WATCH; the NAV drag, muni recall, bond holidays and leverage cost killed; paper scoring an artefact
- kind: kill
- era: ALPACA
- date: 2026-11-02
- figures:
  - F turn-of-month: +54.6bp a month, t 5.06 (CRSP, 187 months), placebo 10 sessions earlier −42.4bp (t −3.28); "a hypothesis found after the fit was seen, not evidence"; WATCH by ruling until a test anchored on pay dates [S]
  - A NAV drag KILL: the NAV part is unpriced, −0.27%/yr (t −0.36), against the discount part's +6.70%/yr (t 3.29) [S]
  - E bond holidays KILL: 0.17% of fit turnover; D leverage cost KILL: +0.61 (t 1.20), the wrong sign; C muni recall KILL: +0.003 (t 0.08) [S]
  - B paper scoring: PAPER ARTEFACT; the distribution leg averages −0.21%/yr (t −0.65) on the fit [S]
- source: `results/cef/screens_2026-11-02/UNIQUE_ANGLES.md` @ `69609e6`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §6
- status: current

### E-2026-11-02-26 · Appendix — NAV-HEDGE-1: an ETF overlay to hedge the core's NAV moves was closed at the power gate (UNDERPOWERED), zero trials
- kind: kill
- era: ALPACA
- date: 2026-11-02
- figures:
  - "P(pass) 0.07–0.11 one-sided at the factor R² 0.011–0.074 on record, and it cannot raise return on capital under Reg T"; replaced by a report-only exposure readout [S]
- source: `docs/RESEARCH_STATE.md` @ `5dbd739`; `docs/SYSTEM.md` @ `4ed3c04`
- supports: §5, §6
- status: current

### E-2026-11-02-27 · Paper fills cost 10.8bp against the 15:50 mid: about 6.2bp half-spread at the fill and 4.6bp mid drift to 15:52
- kind: result
- era: ALPACA
- date: 2026-11-02
- figures:
  - scope 344 fills, 2026-09-29..2026-11-02, 20 sessions, 13 names [V]
  - 99.4% of fills in the 15:52 ET minute (paper late_market); earliest 15:52:02, latest 15:59:58 [V]
  - A (fill vs 15:50 mid) 10.76bp, notional-weighted, positive = worse [V]
  - B (fill vs close) 5.1bp; C (15:50 mid to close, in trade direction) 5.67bp; A = B + C asserted [V]
  - D (15:50 mid to fill-time mid) 4.6bp; E (fill vs fill-time mid, effective half-spread) 6.16bp [V]
  - buys A 14.97bp against sells 6.59bp [V]
- source: `results/cef/FILL_DRIFT_2026-11-02.md` @ `45b7c9d`; `results/cef/fill_drift_2026-11-02/aggregates_2026-11-02.json` @ `45b7c9d`
- supports: §4, §3
- status: current (report only, zero trials; twenty sessions, no cell is a tested effect)

### E-2026-11-02-28 · The fill-vs-close cost splits by period: zero to 2026-10-12, 8.6bp from 2026-10-13, because the post-15:50 market move stopped running against the book
- kind: result
- era: ALPACA
- date: 2026-11-02
- figures:
  - to 10-12: 97 fills, B −0bp, C 12.64bp, A 12.64bp [V]
  - 10-13 on: 247 fills, B 8.63bp, C 0.83bp, A 9.46bp [V]
  - over the 338 fills to 10-30, B in USD is a $308.71 cost, equal to the live attribution's fill line −$308.71 [V]
- source: `results/cef/FILL_DRIFT_2026-11-02.md` @ `45b7c9d`; `results/cef/LIVE_ATTRIBUTION_2026-11-02.md` @ `9bd43ad`
- supports: §4
- status: current

### E-2026-11-02-29 · No evidence that the pre-15:50 move predicts the fill cost or the move to the close (127 symbol-days)
- kind: result
- era: ALPACA
- date: 2026-11-02
- figures:
  - difference (+1 minus −1), clustered by date over 17 days: B 2.95bp (t 0.55), C 0.03bp (t 0.0) [V]
  - Spearman over 127 symbol-days: x vs B 0.009, x vs C 0.061 [V]
- source: `results/cef/FILL_DRIFT_2026-11-02.md` @ `45b7c9d`
- supports: §4, §3
- status: current (INCONCLUSIVE at this sample)

### E-2026-11-03-01 · release-20261103-1: trial 53 amendment 1 (core ×1.30, spec v9) with C4 integrated dark (spec v4, ×1.26); GO for the core only
- kind: release
- era: ALPACA
- date: 2026-11-03
- figures:
  - tag message: "CEF trial 53 amendment 1: core sizing_multiplier 1.30 (cef_discount.v9.20261102); C4 integrated dark (c4_families.v4.20261102, x1.26)" (336df9d, 2026-11-03 02:14:36 −0500; merged to main as f27ef81, PR #36) [S]
  - "That release was GO for the core only" [S]
  - whether it was installed on the VM is not recorded in the files read [U]
- source: `tag:release-20261103-1` @ `336df9d`; `git-log:f27ef81` (merge subject, PR #36) @ `f27ef81`; `results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md` @ `8ce0395`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261103-2 (2026-11-03)

### E-2026-11-03-02 · A third thin-session rule, trading the 4 or 5 eligible names, scored the highest gross return in every window but was not shown to be alpha
- kind: result
- era: ALPACA
- date: 2026-11-03
- figures:
  - gross ann %, fit before 2023 (instant / deferred flips): hold 3.29 / 3.16, flatten (live) 1.58 / 1.46, te4 5.77 / 5.35 [V]
  - at matched turnover (H2) the gap over flatten is +2.13pp/yr, NW t 2.34, under the bar of 2.818; `read_result` INCONCLUSIVE, interval [−0.87, +5.14] [V]
  - "Take PHK's and PDI's own P&L out, and the fit gap is +1.08 (t 1.43)"; the six PIMCO funds carry +3.63 of the +4.19pp/yr [V]
  - 2023 holdout gap +0.87pp/yr (t 0.72); net of measured 2023+ borrow −2.33pp/yr [V]
  - "There has been no thin session since 2023-08-30" [V]
- source: `results/backtests/thin-third-rule-2026-11-03/REPORT.md` @ `9245459`
- supports: §2, §5
- status: current

### E-2026-11-03-03 · Gate 0 evidence for trial 54: dead CEFs show the family-level discount effect at least as strongly as survivors, so survivorship does not explain it
- kind: result
- era: ALPACA
- date: 2026-11-03
- figures:
  - pull 2 (EDGAR N-CSR): 1,795 NAVs for 148 of 190 dead candidates; coverage 0.642, below the 80% reference [V]
  - slopes (bp per pp, half-year-clustered t): b_A −27.35 (t −4.96) on 65 funds; b_D −37.19 (t −6.48) on 133; b_B −32.90 (t −7.55) [V]
  - b_D/b_A +1.360, 95% CI 0.799–2.127 by fund-half-year, 0.946–2.321 by calendar half-year; b_B/b_A +1.203 (0.955–1.542) [V]
  - dead-only slope negative in 30 of 33 half-years; P(b_D ≥ 0) 0.000 [V]
  - the 42 never-covered funds earned −1,535bp against covered dead funds in their last year (t −2.70); the adverse imputation still gives b_B/b_A 1.031 [V]
- source: `results/cef/screens_2026-11-02/gate0_analysis_output.txt` @ `389f61a`; `results/cef/PREREG_C4_LEVEL_2026-11-02.md` @ `4ed3c04`
- supports: §2, §5
- status: current (post-data evidence, not a pre-registered pass)

### E-2026-11-03-04 · release-20261103-2: C4 arming prep — the opening-session probe, specs named everywhere, and a C4 install that scans every book's units
- kind: release
- era: ALPACA
- date: 2026-11-03
- figures:
  - tag message: "C4 arming prep (QR1 opening-session probe, QR3 book text, ET1 C4 unit scan); core order path unchanged since release-20261103-1" (de75da4; merged as f7f7be5, PR #37) [S]
  - QR1: in the shared spare account a past fill "would open C4 at the band edge: 28–42% of target, net long" [V]
  - release-check of de75da4: verdict word not recorded; it "left" R1 (the first-session gate in code) [U]
- source: `tag:release-20261103-2` @ `de75da4`; `git-log:f7f7be5` (merge subject, PR #37) @ `f7f7be5`; `docs/JOURNAL.md` @ `8ce0395`; `results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261103-3 (2026-11-03)

### E-2026-11-03-05 · The journal and the C4 checklist had named f27ef81 as release-20261103-1; the tag's commit is 336df9d
- kind: correction
- era: ALPACA
- date: 2026-11-03
- figures:
  - "this line first said f27ef81 = release-20261103-1, but `git rev-parse release-20261103-1^{commit}` is 336df9d" [S]
- source: `docs/JOURNAL.md` @ `8ce0395`; `results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md` @ `8ce0395`
- supports: §5
- status: current

### E-2026-11-03-06 · CEF 53 → 54: Gate 0 cleared post-data ("I approve, lets try and deploy as fast as possible"), trial 54 approved, on the two existing accounts, with C4 to open from flat
- kind: ruling
- era: ALPACA
- date: 2026-11-03
- figures:
  - Gate 0 "Not a pre-registered pass, and never to be described as one" [S]
  - pass rule unchanged: P1 alpha NW t ≥ √(2 ln 54) = 2.825 on the fit, the deflated-Sharpe bars at N = 54, NC1, the placebo, D4, P3, then the 2023–26 holdout's sign, opened once [S]
  - accounts: "use the 2 accounts I gave you, i dont hvae any other" — the core account and the C4 (spare) account [S]
  - C4's first session: "just flat it" — the research loop's fills do not count against C4's opening; any position does [S]
  - risk split 0.50; the 1.90 cap kept; expected +0.4 to +1.0%/yr gross on all capital [U]
- source: `docs/SYSTEM.md` @ `4ed3c04`; `docs/RESEARCH_STATE.md` @ `5dbd739`; `results/cef/PREREG_C4_LEVEL_2026-11-02.md` @ `4ed3c04`
- supports: §2, §5
- status: current

### E-2026-11-03-07 · release-20261103-3: C4 opens correctly in the shared spare account (`own_prefix`), and an armed first session is gated in code
- kind: release
- era: ALPACA
- date: 2026-11-03
- figures:
  - tag message: "C4 own_prefix opening rule + first-session gate (R1 amended; team lead 2026-11-03 'just flat it'); core identical to release-20261103-2" (4f759a9; PR #38 merged as 61589a8) [S]
  - on the loop-history fixture armed C4 opens at full target: "the same 63 orders and $188,509 gross as a fresh account"; with the key absent "11 band-edge orders ($20,377), which the gate refuses" [S]
  - release-check of 4f759a9: verdict word not recorded; it left five fixes [U]
- source: `tag:release-20261103-3` @ `4f759a9`; `git-log:61589a8` (merge subject, PR #38) @ `61589a8`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §5
- status: superseded by release-20261103-4 (2026-11-03)

### E-2026-11-03-08 · Trial 54 Stage 0: the second-source gate cleared and the team lead signed the data-flag rulings as proposed (KEEP 237, MASK 9)
- kind: result
- era: ALPACA
- date: 2026-11-03
- figures:
  - DG-L2: level-only book gross SR +0.882 on CRSP against +0.810 on the yfinance leg; |difference| 0.071 against 0.2: CLEAR [V]
  - DG-L3: 242 fit name-days with |price TR − NAV TR| > 10%; signed "KEEP 237, MASK 9" (the masks on the level leg's discount only) [V]
- source: `results/cef/prereg_c4_level/dgl2_output_2026-11-03.txt` @ `3d1c37c` (branch trial54-run, PR #42, unmerged); `results/cef/prereg_c4_level/TRIAL54_RESULT_2026-11-03.md` @ `f78255a` (branch trial54-run, PR #42, unmerged)
- supports: §2
- status: current

### E-2026-11-03-09 · CEF 54 → 55: the thin-session rule `trade_eligible` (floor 4) was approved for paper only, against the drafting session's recommendation
- kind: counter
- era: ALPACA
- date: 2026-11-03
- figures:
  - approved "at about 09:25 ET, for paper only, with K0"; judged at N = 55, bar 2.831, one-sided p 0.00232; each declared PRESENT read at p / 4 = 0.00058 [V]
  - trial 53 under te4 at ×1.30: zero-edge P(HALVE) / P(KILL) 23.2% / 3.28%, against 16.7% / 1.69% at ×1.15 and flatten's 17.1% / 1.75% [V]
  - "The drafting session recommended keeping flatten (§10 Q1, option c). The team lead chose approval" [S]
  - key absent until activation, after the core's 60-session review is graded; "This commit changes no spec and no live code" [S]
- source: `results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md` @ `ac15d09`; `docs/RESEARCH_STATE.md` @ `5dbd739`
- supports: §2, §5
- status: current

### E-2026-11-03-10 · Trial 54's fit stages, as committed: P1 passed at the bar, P2, K1 and K2 passed, and K3 (D4) killed it on the level book's post-2007 alpha t 2.96
- kind: result
- era: ALPACA
- date: 2026-11-03
- figures:
  - P1 level-only on z-only: alpha +5.72%/yr, β +0.191, t 2.8271 at lag 6 against 2.8245; "2.791 at lag 5 on the dependent series" [V]
  - P2 blend desk DSR 0.9997 (SR 1.481, SR0 0.669); K1 NAV leg −0.26bp/pp (t −0.32); K2 real +0.882 above 20 of 20 placebos [V]
  - K3 level-only: full fit alpha t 3.06 (pass); "from 2007-04-12 with HY: alpha +7.14%/yr, t 2.96, max|β| 0.082 (fail)"; on the blend D4 passes (alpha t 6.68) [V]
  - fit books gross SR: z-only 1.269, level-only 0.882, blend 1.481; net@15 0.256 / 0.269 / 0.424 [V]
- source: `results/cef/prereg_c4_level/TRIAL54_RESULT_2026-11-03.md` @ `f78255a` (branch trial54-run, PR #42, unmerged)
- supports: §2
- status: superseded by E-2026-11-03-12 (2026-11-03) in its P1 figure; K3 overridden by E-2026-11-03-11 (2026-11-03)

### E-2026-11-03-11 · The team lead overrode trial 54's K3 kill post-data ("revive it and figure out a way to not kill it"); it is not a pass of K3, and the holdout decides
- kind: ruling
- era: ALPACA
- date: 2026-11-03
- figures:
  - "verdict_as_committed": "KILL (D4)", "is_a_pass": false, "ruled_by": "team lead (post-data, asked interactively)" [V]
  - "The coordinator had recommended recording the KILL and was overruled" [V]
  - covers K3 only: "a failure at P3, DG-L4 or the holdout is a KILL" [V]
- source: `results/cef/prereg_c4_level/k3_override_2026-11-03.json` @ `e4b0d71` (branch trial54-run, PR #42, unmerged); `results/cef/prereg_c4_level/TRIAL54_RESULT_2026-11-03.md` @ `f78255a` (branch trial54-run, PR #42, unmerged)
- supports: §2, §5
- status: current

### E-2026-11-03-12 · DG-L4 halted trial 54 on a defect in the trial script (a truncated vol lookback); the corrected run matched the sleeve on 907 of 907 sessions and moved P1 to t 2.8315
- kind: correction
- era: ALPACA
- date: 2026-11-03
- figures:
  - first read: key present against the trial's blend 901 of 907; "6 breaks, all from 2005-02-23 to 2005-03-31, largest gap 0.0499 (RNP 2005-03-09)" [V]
  - corrected (2ed752f): 907 of 907, 61,346 cells, gap 5.6e-16 [V]
  - P1 t: first read 2.8271 → corrected 2.8315 (L = 5: 2.80; L = 21: 2.80), bar 2.8245; "lag-fragile" [V]
  - every other fit stage unchanged; K3 still reads KILL (D4), overridden [V]
- source: `results/cef/prereg_c4_level/TRIAL54_RESULT_2026-11-03.md` @ `f78255a` (branch trial54-run, PR #42, unmerged)
- supports: §2, §5
- status: supersedes the P1 figure of E-2026-11-03-10

### E-2026-11-03-13 · Trial 54 P3 passed: the blend beat the z-only book at matched turnover on the fit
- kind: result
- era: ALPACA
- date: 2026-11-03
- figures:
  - blend gross SR 1.481 at 51.2 turns/yr against the z-only spec book at its turnover-matched band 0.0447: 1.310 at 51.2/yr [V]
  - `sharpe_diff`, reported and not gated: Δ +0.17/yr, d 0.93, p 0.353 (corrected run p 0.354) [V]
- source: `results/cef/prereg_c4_level/TRIAL54_RESULT_2026-11-03.md` @ `f78255a` (branch trial54-run, PR #42, unmerged)
- supports: §2
- status: current

### E-2026-11-03-14 · release-20261103-4: the C4 arming fixes; the team lead ruled "no dry sessions", so C4 arms at the night's install
- kind: release
- era: ALPACA
- date: 2026-11-03
- figures:
  - tag message: "C4 arming fixes (first_session gate name, cls-path test, UNMEASURED open orders, probe paging, ruling citations); core unchanged" (8ce0395; PR #40 merged as 4485a96) [S]
  - the probe pages the whole closed-order history and "caps at 200 pages, beyond which it reads UNMEASURED"; each fix's test fails on 61589a8 [S]
  - "the team lead ruled 'no dry sessions': C4 arms at tonight's install" [S]
  - release-check verdict for 8ce0395: none recorded [U]
- source: `tag:release-20261103-4` @ `8ce0395`; `git-log:4485a96` (merge subject, PR #40) @ `4485a96`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §2, §5
- status: current (newest release tag)

### E-2026-11-03-15 · Trial 54's holdout, opened once (2023-01-03 → 2026-09-30), passed: the level book earned a gross Sharpe of 1.636 and the blend beat C4's z book; the evidence is still INCONCLUSIVE
- kind: result
- era: ALPACA
- date: 2026-11-03
- figures:
  - z-only: gross SR +1.497, ann +10.32%, net@5/15/30 +1.040 / +0.125 / −1.247 [V]
  - level-only: gross SR +1.636, ann +12.18%, net +1.394 / +0.911 / +0.186, no flip [V]
  - blend ½ : ½: gross SR +2.065, ann +14.56%, vol 7.05%, turn 57.4/yr, net +1.658 / +0.843 / −0.378 [V]
  - rule: level gross SR > 0 and blend ann above z-only: PASS; net@15 0.843 ≥ 0.125, so no D2 [V]
  - level-on-z alpha +10.43%/yr, SE 3.80, NW t 2.74 (lag 7); Šidák interval at N = 54 −2.14 to +22.99%/yr: INCONCLUSIVE, straddling the declared 0.8%/yr [V]
  - C4's z-only 2023–26 had been seen for trial 52; "This signal's 2023+ is new" [V]
- source: `results/cef/prereg_c4_level/holdout_output_2026-11-03.txt` @ `f78255a` (branch trial54-run, PR #42, unmerged); `results/cef/prereg_c4_level/TRIAL54_RESULT_2026-11-03.md` @ `f78255a` (branch trial54-run, PR #42, unmerged)
- supports: §2, §5
- status: current (PASS on the pre-registered remainder; K3 overridden post-data; not yet activated: spec c4_families.v5 pending)

### E-2026-11-03-16 · Release tag release-20261103-4 is commit 8ce0395, carrying core spec v9 at ×1.30 and C4 spec v4 at ×1.26 with C4's arming fixes
- kind: release
- era: ALPACA
- date: 2026-11-03
- figures:
  - Capital and limits follow the frozen spec cef_discount.v9.20261102 (capital_usd 100000, risk.max_gross_exposure_usd 260000, sizing_multiplier 1.3 from CEF trial 53 amendment 1 (from `ops/books/cef_discount_book.json`) [S]
  - Capital and limits follow the frozen spec c4_families.v4.20261102 (CEF trial 52's book; sizing_multiplier 1.26 from CEF trial 53 amendment 1 (from `ops/books/c4_families_book.json`) [S]
  - Each fix's test fails on 61589a8, and the core is unchanged by its pins. (from `docs/JOURNAL.md`) [S]
  - It caps at 200 pages, beyond which it reads UNMEASURED and plan.json is the authority (from `docs/JOURNAL.md`) [S]
- source: `ops/books/cef_discount_book.json` @ `8ce0395`; `ops/books/c4_families_book.json` @ `8ce0395`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §1, §2, §3, §5
- status: current

### E-2026-11-03-17 · The core account trades cef_discount.v9.20261102: 13 credit CEFs, a 6% unit vol target held at ×1.30, a 4.8% no-trade band and a 1.80× gross cap
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - universe AWF, BIT, DSL, HYT, JFR, MHD, MQY, PCN, PDI, PDO, PFN, PHK, PTY (13 names) [S]
  - z_window 252; min_names 6; min_adv_usd 3000000.0; max_nav_age_bd 3; min_abs_weight 0.005 [S]
  - the account's effective ex-ante vol target is 0.06 x 1.30 = 7.8% on the unit book's 6% scale [S]
  - band_width 0.048: gives 4.26% at 15bp and 4.85% at 22bp; the lower edge of the measured plateau (4.8-9.6%) [S]
  - 6.4% topped the swept column and was NOT chosen [S]
  - Measured full sample: gross 1.16, turnover 17.6x/yr (vs 31.1 on the calendar), net@15bp 0.66 (vs 0.33), and net@30bp +0.17 [S]
  - 17 -> 13 … traded-era gross SR 1.54 -> 1.16 on the band alone [S]
  - capital_usd 100000.0; risk.max_gross_exposure_usd 260000.0 [S]
- source: `ops/specs/cef_discount.frozen.json` @ `8ce0395`
- supports: §1, §2, §3
- status: current

### E-2026-11-03-18 · The core's sizing multiplier 1.30 was re-derived on the live thin-day rule (flatten); 1.13 and 1.96 were not chosen
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - the core is flat on 1,353 of W1's 2,398 sessions [S]
  - 1.2642 x 0.003659 / 0.003556 = 1.3007, written to 2 dp ROUNDED DOWN: 1.30 [S]
  - NOT CHOSEN: 1.13 (v8: the hold book's sd 0.004095 … zero-edge P(HALVE)/P(KILL) 10.3% / 0.66% while trading) [S]
  - and 1.96, the same rule fed the flatten book's CALENDAR sd 0.002351, which is inflated because the flat sessions count as zero risk [S]
  - with C4 at 1.26 the combined Sharpe is 1.624-1.638 for every core multiplier from 0.8 to 2.5; 1.30 is at 1.626 [S]
  - exact-build gross 3.78%/yr total return over the calendar and 8.67%/yr while trading (SR 1.222), against 3.31 / 7.59 at 1.13 [S]
  - max drawdown 8.39% (7.53% at 1.13); zero-edge P(HALVE in 12 months) 16.7%, P(KILL) 1.68% while trading [S]
  - It is an amendment, not a new trial: CEF stays 53 [S]
- source: `ops/specs/cef_discount.frozen.json` @ `8ce0395`
- supports: §1, §2, §3, §5
- status: current

### E-2026-11-03-19 · C4 is spec c4_families.v4.20261102: the core's z-score on 74 non-credit CEFs in five families, ×1.26, its own 1.90× cap, holding on thin days; its book json says DARK
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - 74 of the 105 pool funds tradable, shortable and easy to borrow [S]
  - By family: sector 29, covered-call 15, multi-asset 15, preferred 9, domestic 6 [S]
  - G_stress = 1.900638; no mark sensitivity (no other book's margin) -> floor_0.05 = 1.90 [S]
  - w5 = 0.0261393, the worst 5-session total-return loss per unit gross held of C4's UNCAPPED 4.8% band [S]
  - PLATEAU (fit gross SR; the value comes from the arithmetic, not from this): 1.60 1.247, 1.70 1.233, 1.80 1.217, 1.90 1.200, 2.00 1.185, none 1.137 [S]
  - -> 1.2642, written to 2 dp ROUNDED DOWN: 1.26 [S]
  - the account's effective ex-ante vol target is 0.06 x 1.26 = 7.56% [S]
  - W1 10.05%/yr total return, SR 1.449; held at the cap's decided-gross line on 46.2% of W1 sessions [S]
  - The declared book had fewer than 6 eligible on 10.5% of fit sessions [S]
- source: `ops/specs/c4_families.frozen.json` @ `8ce0395`
- supports: §1, §2, §3, §5
- status: current

### E-2026-11-03-20 · The b6 equal-weight credit benchmark has a frozen spec but no book json and no runner entry, so nothing trades it at this tag
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - capital_usd 20000.0 (from `ops/specs/bench_b6_ew_credit.frozen.json`) [S]
  - weights HYG, JNK, LQD, VCIT, USHY, SHYG, EMB, ANGL 0.125 each; rebalance_days 21 (from `ops/specs/bench_b6_ew_credit.frozen.json`) [S]
  - BOOKS holds "cef" and "c4" only (from `quantt/session/run.py`) [S]
- source: `ops/specs/bench_b6_ew_credit.frozen.json` @ `8ce0395`; `quantt/session/run.py` @ `8ce0395`
- supports: §1, §3, §5
- status: current

### E-2026-11-03-21 · The run pipeline: collector at :10/:40; session slots at 22:00–01:00 and 06:00–15:15 ET; final check at close − 90 min; late send at 15:52/15:55; verify at 17:30 ET
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - every :10 and :40, every day (from `quantt/deploy/templates/systemd/quantt-cef-collect.timer.tmpl`) [S]
  - every :00 and :30, every day. The runner decides whether this is a slot (evening 22:00-01:00 ET, morning 06:00-15:15 ET) and otherwise idles (from `quantt/deploy/templates/systemd/quantt-cef-session.timer.tmpl`) [S]
  - 15:52 and 15:55 Mon-Fri: the paper account's late-market send window for a 16:00 close. 12:52 and 12:55: the same window for a 13:00 early close (from `quantt/deploy/templates/systemd/quantt-cef-session.timer.tmpl`) [S]
  - 17:30 ET Mon-Fri, after the close and the auction prints (from `quantt/deploy/templates/systemd/quantt-cef-verify.timer.tmpl`) [S]
  - The final check is the session's calendar close minus 90 minutes, on the session date: 14:30 ET, or 11:30 ET on a 13:00 close (from `docs/RUNNER.md`) [S]
  - At the live size (13 orders) the budget is 81 s. A set may start until 15:56:39 (from `quantt/session/gate.py`) [S]
  - The refresh timeout is capped at 25 minutes (from `docs/RUNNER.md`) [S]
- source: `quantt/deploy/templates/systemd/quantt-cef-collect.timer.tmpl` @ `8ce0395`; `quantt/deploy/templates/systemd/quantt-cef-session.timer.tmpl` @ `8ce0395`; `quantt/deploy/templates/systemd/quantt-cef-verify.timer.tmpl` @ `8ce0395`; `docs/RUNNER.md` @ `8ce0395`; `quantt/session/gate.py` @ `8ce0395`
- supports: §1, §5
- status: current

### E-2026-11-03-22 · Both paper books decide in the evening and send market day orders 8 to 2 minutes before the close, the recorded paper-only exception to the MOC rule, because paper runs no closing auction
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - on 2026-09-29 eleven of thirteen cls orders expired unfilled although every NYSE closing auction printed more shares than we asked for (from `ops/books/cef_discount_book.json`) [S]
  - window_minutes_before_close [8, 2] (15:52-15:58 ET; 12:52-12:58 on a 13:00 early close) (from `ops/books/cef_discount_book.json`) [S]
  - paper filled 2 of 13 `cls` orders (PHK 4,019/4,019, PFN 1,529/2,227; eleven expired) (from `docs/RUNNER.md`) [S]
  - Overnight market orders realised 100.5bp against a 32.6bp breakeven on 2026-07-31 (from `CLAUDE.md`) [S]
- source: `ops/books/cef_discount_book.json` @ `8ce0395`; `ops/books/c4_families_book.json` @ `8ce0395`; `docs/RUNNER.md` @ `8ce0395`; `CLAUDE.md` @ `8ce0395`
- supports: §1, §2, §5
- status: current

### E-2026-11-03-23 · The official daily P&L is Alpaca's end-of-day portfolio history (1D); the 17:30 ET equity reading is a labelled snapshot, never blended
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - On the four days compared on 2026-10-19 it disagreed with the history every time, while the history agreed with the auction-marked score (from `docs/RUNNER.md`) [S]
  - It stamped the 2026-10-16 close at 20:00 ET (from `docs/RUNNER.md`) [S]
  - Alpaca's winter end-of-day stamps are 01:00Z (20:00 EST), and the client accepted only 00:00Z (from `docs/JOURNAL.md`) [S]
  - Each write rewrites every funded session from 2026-09-28, atomically (from `docs/RUNNER.md`) [S]
- source: `docs/RUNNER.md` @ `8ce0395`; `docs/SYSTEM.md` @ `8ce0395`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §1, §4, §5
- status: current

### E-2026-11-03-24 · Nine pure pre-transmit gates run on every send, and every refusal is returned; only dry_run, arming and halt explain a no-trade day, and any other refusal is a MISSED FAIL
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - CLS_CUTOFF_ET = dt.time(15, 45); QUEUE_OPEN_ET = dt.time(19, 15) (from `quantt/session/gate.py`) [S]
  - SEND_MARGIN_S = 10 + 30 + 2; MEASURED_MAX_ORDER_CYCLE_S = 0.259 (from `quantt/session/gate.py`) [S]
  - SHORT_ORDER_BP_MULTIPLIER = 1.03 (from `quantt/session/gate.py`) [S]
  - DELIBERATE_GATES = frozenset({"dry_run", "arming", "halt"}) (from `quantt/session/verify.py`) [S]
  - One GET that exhausts its retries takes about 250 s (from `docs/RUNNER.md`) [S]
  - The late window is 360 s (15:52–15:58 ET), and a 13-order set needs 81 s of it (from `docs/RUNNER.md`) [S]
- source: `quantt/session/gate.py` @ `8ce0395`; `quantt/session/verify.py` @ `8ce0395`; `docs/RUNNER.md` @ `8ce0395`
- supports: §1, §5
- status: current

### E-2026-11-03-25 · C4's first armed session must be an opening session: only C4's own c4- fills count against it, and a position, another runner's open order or an unreadable order list refuses it under its own gate
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - 28-42% of full target and net long +4.7% to +11.1% (the release-check of 336df9d, data/cef_families to 2026-10-09, spec v4) (from `ops/books/c4_families_book.json`) [S]
  - armed C4 now opens at full target: the same 63 orders and $188,509 gross as a fresh account. With the key absent it is still 11 band-edge orders ($20,377) (from `docs/JOURNAL.md`) [S]
  - OPENING_REQUIRED_BOOKS = frozenset({"c4"}) (from `quantt/session/run.py`) [S]
- source: `ops/books/c4_families_book.json` @ `8ce0395`; `quantt/session/run.py` @ `8ce0395`; `docs/JOURNAL.md` @ `8ce0395`
- supports: §1, §5
- status: current

### E-2026-11-03-26 · Data gates at the tag: the core's stale-NAV gate records only (report); both books hold a late-NAV fund for at most 2 sessions; C4 has no stale-NAV gate and relies on its NAV-repeat mask
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - stale_nav report: 28 of 73 checkable laptop name-days decided on NAV(D-1), 11 orders sized on one (from `ops/books/cef_discount_book.json`) [S]
  - missing_nav_max_sessions 2: the team lead's POLICY of 2026-10-29, 2 consecutive sessions, NOT derived (from `ops/books/cef_discount_book.json`) [S]
  - more missing NAVs than n - min_names from the frozen spec (13 - 6 = 7 (from `ops/books/cef_discount_book.json`) [S]
  - The name limit is derived by the runner from the C4 spec's min_names (74 - 6 = 68) (from `ops/books/c4_families_book.json`) [S]
  - prod's NAV panel (copy of 2026-10-28) shows 0 gaps in 12 months (from `ops/books/cef_discount_book.json`) [S]
- source: `ops/books/cef_discount_book.json` @ `8ce0395`; `ops/books/c4_families_book.json` @ `8ce0395`; `quantt/session/gate.py` @ `8ce0395`
- supports: §1, §2, §5
- status: current

### E-2026-11-03-27 · The corporate-action gate runs in report mode on both books at this tag, recording events and sending anyway, until the ISIN fix and the re-ruling of unresolved rows
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - today's real feed carries three market-wide rows with a missing party symbol (a partial call, an SNTI spin-off, a JAGX merger) (from `ops/books/cef_discount_book.json`) [S]
  - on all 43 unresolved rows in the core's 2026-11-02 read, a flat C4 book would have been refused on 17 of the 23 sessions 2026-10-01..11-02 (the feed as read on 11-02, not as it stood on each date) (from `ops/books/c4_families_book.json`) [U]
  - The query asks for process dates from 31 days before the earliest window to 731 days after the session (from `docs/RUNNER.md`) [S]
  - On twelve months of the real feed, 29 reorganizations carried such legs (from `docs/RUNNER.md`) [S]
- source: `ops/books/cef_discount_book.json` @ `8ce0395`; `ops/books/c4_families_book.json` @ `8ce0395`; `docs/RUNNER.md` @ `8ce0395`
- supports: §1, §5
- status: current

### E-2026-11-03-28 · HALVE/KILL are measured on the EOD equity series in report mode only, and trial 53's stops R1–R3 are read and acted on by the team lead; no stop is enforced in code
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - risk.halve_drawdown 0.12; risk.kill_drawdown 0.18 (from `ops/specs/cef_discount.frozen.json`) [S]
  - THE STOPS (pre-registration section 0.B): R1 10.14%, R2 -3.06%, R3 12.07% … read and acted on by the team lead; nothing in code reads them (from `ops/specs/cef_discount.frozen.json`) [S]
  - the stops R1 10.04%, R2 -3.02%, R3 9.90% (stops.py --m-c4 1.26) (from `ops/specs/c4_families.frozen.json`) [S]
  - Review at 60 live sessions, not before. KILL if any of: (a) live net Sharpe < 0.0; (b) realised slippage > 2x modelled for 5 consecutive sessions (from `ops/specs/cef_discount.frozen.json`) [S]
  - REVERSE at 120 armed sessions if the live cumulative gross return on the official-fill line is below the 5th percentile (from `ops/specs/c4_families.frozen.json`) [S]
  - book_drawdown_suspend_pct 99.0: Effectively disabled 2026-07-31 on standing instruction (from `ops/books/cef_discount_book.json`) [S]
- source: `ops/specs/cef_discount.frozen.json` @ `8ce0395`; `ops/specs/c4_families.frozen.json` @ `8ce0395`; `ops/books/cef_discount_book.json` @ `8ce0395`; `ops/books/c4_families_book.json` @ `8ce0395`
- supports: §1, §5
- status: current

### E-2026-11-03-29 · The gross ceiling is derived from Reg T initial margin and the worst five-session loss; gate 8 judges it on the lower of sized and live equity and always passes a plan that does not add gross
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - G_stress = 1.843041; no mark sensitivity (no other books) -> floor_0.05 = 1.80 (from `ops/specs/cef_discount.frozen.json`) [S]
  - w5 = 0.0425814 = worst 5-session total-return loss per unit gross held of the 13-name band, ending 2020-03-18 (from `ops/specs/cef_discount.frozen.json`) [S]
  - Reg T initial margin 50%, so 1.80x gross needs $90k of margin against $100k equity (from `ops/specs/cef_discount.frozen.json`) [S]
  - more than 1 - 1.8/1.843 = 2.34% under the sized equity (from `quantt/session/gate.py`) [S]
  - projected gross $182,154.75 > max_gross_stress 1.8 x equity $100,666.16 (the 2026-10-09 refusal) (from `docs/RUNNER.md`) [S]
  - Alpaca's maintenance on these names is 0.30 (from `ops/specs/cef_discount.frozen.json`; the core spec's stated rate, not what gate 8 uses) [U]
  - maintenance at the account's LIVE measured ratio, maintenance_margin / current gross, 47.8% on 2026-10-06 (from `quantt/session/gate.py`; gate 8 uses this live ratio, never a literal, so it is the record) [U]
- source: `ops/specs/cef_discount.frozen.json` @ `8ce0395`; `quantt/session/gate.py` @ `8ce0395`; `docs/RUNNER.md` @ `8ce0395`
- supports: §1, §5
- status: current

### E-2026-11-03-30 · Each book has its own Alpaca paper account because Alpaca rejects opposite-side orders in one symbol and gates 6 and 9 refuse a shared account; paper diverges from a live account
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - One Alpaca paper account per book, $100k each (the default) (from `docs/SYSTEM.md`) [S]
  - Putting C4 inside the core's account was declined: shared gross cap, the combiner cannot yet run with the missing-NAV hold, and the trial-53 sizing assumes two accounts (from `docs/SYSTEM.md`) [S]
  - REG_T_INITIAL = 0.5 (from `quantt/session/gate.py`) [S]
  - Paper DOES charge regulatory fees on this account: 37 SEC and CAT fee activities, −$6.16 over 09-29..10-30 (from `docs/JOURNAL.md`, a broker read of FEE activities; the record, since the broker ranks first in docs/SYSTEM.md §0) [U]
  - Paper also charges no borrow, no dividends and no regulatory fees (from `CLAUDE.md` landmine 1, labelled verified from Alpaca docs; the team lead ruled the correction Not yet on 2026-11-02) [U]
- source: `docs/SYSTEM.md` @ `8ce0395`; `quantt/session/gate.py` @ `8ce0395`; `docs/JOURNAL.md` @ `8ce0395`; `CLAUDE.md` @ `8ce0395`
- supports: §1, §3, §4, §5
- status: current

### E-2026-11-03-31 · The pack's own re-derivation of paper fill cost against the official close agrees with FILL-DRIFT within 0.2bp
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - notional-weighted fill vs primary-exchange official close (condition M), 115 name-side-days in 18 sessions, 2026-09-29..2026-11-02: +4.99bp, positive = worse (fill_cost_pooled.csv, group all) [V]
  - FILL-DRIFT's B (fill vs the SIP daily-bar close, 344 fills, same window): 5.1bp [V]
  - the references differ (official closing print against the SIP daily close; per name-side-day against per fill), so agreement is a cross-check, not an identity [S]
- source: `results/report/data/live/cef/fill_cost_pooled.csv` @ `pull:24d55dcbfe1b` (figure F09); `results/cef/FILL_DRIFT_2026-11-02.md` @ `45b7c9d`
- supports: §4
- status: current

### E-2026-11-03-32 · The 17:10 ET equity snapshot and the P&L of record disagree over 2026-09-28..10-30; Alpaca's own last_equity confirms the record
- kind: correction
- era: ALPACA
- date: 2026-11-03
- figures:
  - official EOD equity change 09-28 close → 10-30 close: −982.14 USD (Alpaca portfolio history, the record) [U]
  - collector snapshot equity on 2026-10-30 (read 21:10 UTC): 99,124.35 USD, i.e. −875.65 USD against the 100,000 funding [U]
  - the 2026-11-02 snapshot's last_equity (Alpaca's prior-close equity) 99,017.86 USD = 100,000 − 982.14, so the record reconciles and the 10-30 snapshot carried after-hours marks [V]
  - the record is the EOD history (docs/SYSTEM.md §5, 2026-10-19) [S]
- source: `results/cef/LIVE_ATTRIBUTION_2026-11-02.md` @ `9bd43ad`; `results/report/data/live/cef/equity_snapshot.csv` @ `pull:24d55dcbfe1b`
- supports: §4, §5
- status: current

### E-2026-11-03-33 · The research evidence pack opens: an append-only evidence log, the sanitised live record, and figures rebuilt from committed sources
- kind: method
- era: ALPACA
- date: 2026-11-03
- figures:
  - first live pull ingested: 22 core score days, 2026-09-28..2026-11-02, 245 name-day rows, 115 name-side fills; verify lines from 2026-10-08 [V]
  - the official EOD line is PENDING: the pull carries no eod_equity.csv [V]
- source: `results/report/data/live/cef/pulls.csv` @ `pull:24d55dcbfe1b`
- supports: §4, §5
- status: current

### E-2026-09-28-90 · cef paper book, 2026-09-28: FAIL, did not trade
- kind: live-pnl
- era: ALPACA
- date: 2026-09-28
- figures:
  - verify verdict FAIL; orders sent 0, filled 0 [S]
  - 17:30 ET snapshot equity change 0.00 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 0.00 USD [S]
  - distribution-adjusted P&L 0.00 USD (credits distributions paper does not) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-09-29-90 · cef paper book, 2026-09-29: FAIL, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-09-29
- figures:
  - verify verdict FAIL; orders sent 13, filled 1 [S]
  - 17:30 ET snapshot equity change -80.38 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 0.00 USD [S]
  - fills vs official close 0.00 bp (+ = worse) [S]
  - distribution-adjusted P&L 0.00 USD (credits distributions paper does not) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-05-90 · cef paper book, 2026-10-05: FAIL, did not trade
- kind: live-pnl
- era: ALPACA
- date: 2026-10-05
- figures:
  - verify verdict FAIL; orders sent 0, filled 0 [S]
  - 17:30 ET snapshot equity change 1068.53 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 126.05 USD [S]
  - distribution-adjusted P&L 126.05 USD (credits distributions paper does not) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-07-90 · cef paper book, 2026-10-07: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-07
- figures:
  - verify verdict PASS; orders sent 12, filled 12 [S]
  - 17:30 ET snapshot equity change 368.67 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 329.08 USD [S]
  - fills vs official close -17.95 bp (+ = worse) [S]
  - TCA notional-weighted slippage -17.95 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L 329.08 USD (credits distributions paper does not) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-08-90 · cef paper book, 2026-10-08: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-08
- figures:
  - verify verdict PASS; orders sent 8, filled 8 [S]
  - 17:30 ET snapshot equity change -8.91 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 71.09 USD [S]
  - fills vs official close 15.75 bp (+ = worse) [S]
  - TCA notional-weighted slippage 15.75 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L 71.09 USD (credits distributions paper does not) [S]
  - shadow book 131.47 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-09-90 · cef paper book, 2026-10-09: PASS, did not trade
- kind: live-pnl
- era: ALPACA
- date: 2026-10-09
- figures:
  - verify verdict PASS; orders sent 0, filled 0 [S]
  - 17:30 ET snapshot equity change -445.67 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L -777.67 USD [S]
  - distribution-adjusted P&L -777.67 USD (credits distributions paper does not) [S]
  - shadow book -777.67 USD (MODELLED, not broker evidence) [S]
  - refusing gate(s): exposure [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-12-90 · cef paper book, 2026-10-12: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-12
- figures:
  - verify verdict PASS; orders sent 4, filled 4 [S]
  - 17:30 ET snapshot equity change 1085.88 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 1040.50 USD [S]
  - fills vs official close 9.52 bp (+ = worse) [S]
  - TCA notional-weighted slippage 9.52 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L 1040.50 USD (credits distributions paper does not) [S]
  - shadow book 1053.60 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-13-90 · cef paper book, 2026-10-13: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-13
- figures:
  - verify verdict PASS; orders sent 13, filled 13 [S]
  - 17:30 ET snapshot equity change -1249.71 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L -1238.87 USD [S]
  - fills vs official close 11.86 bp (+ = worse) [S]
  - TCA notional-weighted slippage 11.86 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L -717.71 USD (credits distributions paper does not) [S]
  - shadow book -1198.00 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-14-90 · cef paper book, 2026-10-14: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-14
- figures:
  - verify verdict PASS; orders sent 7, filled 7 [S]
  - 17:30 ET snapshot equity change -748.26 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L -791.69 USD [S]
  - fills vs official close 15.06 bp (+ = worse) [S]
  - TCA notional-weighted slippage 15.06 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L -574.33 USD (credits distributions paper does not) [S]
  - shadow book -732.18 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-15-90 · cef paper book, 2026-10-15: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-15
- figures:
  - verify verdict PASS; orders sent 6, filled 6 [S]
  - 17:30 ET snapshot equity change -233.09 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L -238.34 USD [S]
  - fills vs official close 9.89 bp (+ = worse) [S]
  - TCA notional-weighted slippage 9.89 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L -656.01 USD (credits distributions paper does not) [S]
  - shadow book -193.74 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-16-90 · cef paper book, 2026-10-16: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-16
- figures:
  - verify verdict PASS; orders sent 5, filled 5 [S]
  - 17:30 ET snapshot equity change 242.56 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 160.68 USD [S]
  - fills vs official close 29.77 bp (+ = worse) [S]
  - TCA notional-weighted slippage 29.77 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L 160.68 USD (credits distributions paper does not) [S]
  - shadow book 428.59 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-19-90 · cef paper book, 2026-10-19: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-19
- figures:
  - verify verdict PASS; orders sent 6, filled 6 [S]
  - 17:30 ET snapshot equity change -573.86 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L -579.99 USD [S]
  - fills vs official close 19.90 bp (+ = worse) [S]
  - TCA notional-weighted slippage 19.90 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L -579.99 USD (credits distributions paper does not) [S]
  - shadow book -531.51 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-20-90 · cef paper book, 2026-10-20: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-20
- figures:
  - verify verdict PASS; orders sent 5, filled 5 [S]
  - 17:30 ET snapshot equity change 162.04 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 235.81 USD [S]
  - fills vs official close 24.33 bp (+ = worse) [S]
  - TCA notional-weighted slippage 24.33 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L 235.81 USD (credits distributions paper does not) [S]
  - shadow book 234.54 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-21-90 · cef paper book, 2026-10-21: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-21
- figures:
  - verify verdict PASS; orders sent 9, filled 9 [S]
  - 17:30 ET snapshot equity change 261.16 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 309.02 USD [S]
  - fills vs official close 8.92 bp (+ = worse) [S]
  - TCA notional-weighted slippage 8.92 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L 309.02 USD (credits distributions paper does not) [S]
  - shadow book 314.92 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-22-90 · cef paper book, 2026-10-22: FAIL MISSED, did not trade
- kind: live-pnl
- era: ALPACA
- date: 2026-10-22
- figures:
  - verify verdict FAIL MISSED; orders sent 0, filled 0 [S]
  - 17:30 ET snapshot equity change -216.30 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L -94.28 USD [S]
  - distribution-adjusted P&L -94.28 USD (credits distributions paper does not) [S]
  - shadow book -136.03 USD (MODELLED, not broker evidence) [S]
  - refusing gate(s): data [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-23-90 · cef paper book, 2026-10-23: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-23
- figures:
  - verify verdict PASS; orders sent 2, filled 2 [S]
  - 17:30 ET snapshot equity change 210.25 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 207.85 USD [S]
  - fills vs official close 9.79 bp (+ = worse) [S]
  - TCA notional-weighted slippage 9.79 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L 207.85 USD (credits distributions paper does not) [S]
  - shadow book 242.96 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-26-90 · cef paper book, 2026-10-26: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-26
- figures:
  - verify verdict PASS; orders sent 6, filled 6 [S]
  - 17:30 ET snapshot equity change -446.70 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L -520.85 USD [S]
  - fills vs official close 1.43 bp (+ = worse) [S]
  - TCA notional-weighted slippage 1.43 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L -520.85 USD (credits distributions paper does not) [S]
  - shadow book -536.83 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-27-90 · cef paper book, 2026-10-27: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-27
- figures:
  - verify verdict PASS; orders sent 6, filled 6 [S]
  - 17:30 ET snapshot equity change 251.43 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 192.95 USD [S]
  - fills vs official close 2.22 bp (+ = worse) [S]
  - TCA notional-weighted slippage 2.22 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L 192.95 USD (credits distributions paper does not) [S]
  - shadow book 19.41 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-28-90 · cef paper book, 2026-10-28: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-28
- figures:
  - verify verdict PASS; orders sent 10, filled 10 [S]
  - 17:30 ET snapshot equity change 414.46 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 421.90 USD [S]
  - fills vs official close -4.57 bp (+ = worse) [S]
  - TCA notional-weighted slippage -4.57 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L 421.90 USD (credits distributions paper does not) [S]
  - shadow book 518.50 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-29-90 · cef paper book, 2026-10-29: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-29
- figures:
  - verify verdict PASS; orders sent 3, filled 3 [S]
  - 17:30 ET snapshot equity change 78.64 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L -13.43 USD [S]
  - fills vs official close 21.27 bp (+ = worse) [S]
  - TCA notional-weighted slippage 21.27 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L -13.43 USD (credits distributions paper does not) [S]
  - shadow book -86.17 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-10-30-90 · cef paper book, 2026-10-30: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-10-30
- figures:
  - verify verdict PASS; orders sent 7, filled 7 [S]
  - 17:30 ET snapshot equity change -386.88 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L -503.50 USD [S]
  - fills vs official close -6.82 bp (+ = worse) [S]
  - TCA notional-weighted slippage -6.82 bp, fill rate 1.0000 of shares [S]
  - shadow book -525.84 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-11-02-90 · cef paper book, 2026-11-02: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-11-02
- figures:
  - verify verdict PASS; orders sent 4, filled 4 [S]
  - 17:30 ET snapshot equity change 103.87 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 178.71 USD [S]
  - fills vs official close -15.25 bp (+ = worse) [S]
  - TCA notional-weighted slippage -15.25 bp, fill rate 1.0000 of shares [S]
  - shadow book 174.59 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/verify.csv` @ `pull:24d55dcbfe1b`; `results/report/data/live/cef/tca.csv` @ `pull:24d55dcbfe1b`
- supports: §4
- status: current

### E-2026-11-03-34 · Ruling: the public repository keeps the live record as daily aggregates; per-name and per-fill rows stay in a gitignored cache
- kind: ruling
- era: ALPACA
- date: 2026-11-03
- figures:
  - none (a ruling: "Aggregates in repo, rows private", team lead, on PR #45)
- source: `docs/SYSTEM.md` @ `8ed6135`; `.gitignore` @ `8ed6135`; `scripts/report/snapshot_live.py` @ `8ed6135`
- supports: §4, §5
- status: current (the branch's history was rewritten so the row files never appear in it)

### E-2026-11-02-30 · The Sharpe-framed NAV hedge on the core book was closed as underpowered at Stage 0, spending no trial; a report-only exposure readout replaces it
- kind: ruling
- era: ALPACA
- date: 2026-11-02
- figures:
  - "close the Sharpe-framed NAV hedge as UNDERPOWERED at Stage 0"; "Zero trials, no hedged return computed, no data pulled" (team lead, 2026-11-02) [S]
  - the factor R² on record is 0.011–0.074 [S]
  - with an oracle hedge, at book Sharpe 0.96 over 9.5 years: P(paired ΔSR passes one-sided 5%) is 0.07–0.11, and P(PRESENT at N=54) is at most 0.002 [V]
  - P(pass) = 0.5 needs the hedge to remove R² ≥ 0.51 (one-sided) or 0.79 (Šidák, N=54) [V]
  - "NYSE Arca's closing freeze is 15:59", recorded as a dated correction (SEC Rel. 34-103886) [S]
- source: `results/cef/NAVHEDGE_SCREEN_2026-11-02.md` @ `df87c59`; `results/cef/navhedge_2026-11-02/navhedge_power.py` @ `df87c59`; `docs/REFERENCES.md` @ `8ed6135`
- supports: §3, §5
- status: current

### E-2026-11-03-35 · The exposure readout's declared lag rule gave L = 0, and the team lead made MUNI its headline, with TERM, CREDIT and LOANS indicative
- kind: ruling
- era: ALPACA
- date: 2026-11-03
- figures:
  - "THE RULE'S RESULT: L = 0, so DIMSON_LAGS = 0", run 2026-11-02, 5 s after the commit that declared the rule (09d3dad) [V]
  - "Keep DIMSON_LAGS = 0, the declared rule's output, and make MUNI the headline; TERM, CREDIT and LOANS are marked indicative. No new lag rule is declared." (team lead, 2026-11-03) [S]
  - a factor whose vol contribution exceeds REVIEW_FRACTION = 0.10 × vol_target_annual goes to the team lead's review; "No hedge is ever added automatically" [S]
- source: `scripts/cef/exposure_readout.py` @ `6eee579`; `results/cef/NAVHEDGE_SCREEN_2026-11-02.md` @ `df87c59`
- supports: §5
- status: current

### E-2026-11-03-36 · On the current window the muni funds' own MUNI beta rises with the lag choice, unlike the fit era; the L = 0 headline is unchanged pending the team lead
- kind: result
- era: ALPACA
- date: 2026-11-03
- figures:
  - summed MUNI beta on the 252 sessions strictly before 2026-10-30, at L = 0, 1, 2, 3: MHD +1.21 +1.49 +1.59 +1.65, MQY +1.27 +1.33 +1.44 +1.67 [V]
  - the taxable names' group medians fall from L = 0 to L = 3: hy +0.02 to -0.31; loan (JFR alone) -0.13 to -0.55; multi +0.24 to -0.06 [V]
  - "it changes nothing; whether it bears on the ruling is the team lead's call" [S]
- source: `scripts/cef/exposure_readout.py` @ `6eee579`
- supports: §3, §5
- status: current

### E-2026-11-03-37 · Ruling: on a te4 reduced session, a short skipped at send time is accepted and labelled; the send path is unchanged
- kind: ruling
- era: ALPACA
- date: 2026-11-03
- figures:
  - none (a ruling: "Ruled: accept it and label it." Today's skip-and-send stays on reduced and full sessions alike; the owning session's preference, refusing the whole reduced send, was not chosen; team lead, 2026-11-03)
- source: `results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md` @ `ac15d09`
- supports: §5
- status: current

### E-2026-11-03-38 · Release: release-20261103-4 installed; the core armed at ×1.30 (spec v9) and C4 installed and armed on v4 after VM pre-arm reads
- kind: release
- era: ALPACA
- date: 2026-11-03
- figures:
  - tag release-20261103-4 = 8ce0395 (release-check GO 12:21 ET) [V]
  - replay: 69 runs, 0 refused now [V]
  - C4 pre-arm (VM probe): positions 0, open orders 0, equity $100,000.00, 0 closed orders in the account's history, opening_session True under own_prefix; cap re-check G_stress 1.900638 → 1.90 [V]
  - C4 seed sha256 3fb68e38… / c7073db8…, the same on laptop and VM; treated_closes = IGR's four rebases [V]
- source: `docs/JOURNAL.md` @ `0aaaa1f`
- supports: §1, §4
- status: superseded the same evening by E-2026-11-03-40 (release-20261103-5)

### E-2026-11-03-39 · Ruling: C4 v5's gross cap stays 1.90 over the frozen rule's 1.80 (the blend's w5 0.0536 against the z book's 0.0261)
- kind: ruling
- era: ALPACA
- date: 2026-11-03
- figures:
  - blend w5 0.0536 (total return), 0.0560 (price only); z book 0.0261; the rule gives 1.80 / 1.75 / 1.90 (release-check of e41f10b, measured two ways) [S]
  - a 2020-03-12..18 week held at 1.90×: blend about −10.2% of NLV, z book about −4.6% [S]
- source: `docs/SYSTEM.md` @ `b95296d` (§5 "Team lead, 2026-11-03 — C4 v5's gross cap"; the release-check of e41f10b, workflow run wf_266f659d-5f8)
- supports: §1, §5
- status: current. An override of the rule, made with these figures in front of the team lead ("Keep 1.90, install tonight"). The arming gate's `recap` still read the z book's w5 at install, and is to be fixed

### E-2026-11-03-40 · Release: release-20261103-5 installed; C4 re-armed on the v5 blend (CEF trial 54's level_signal); the core byte-identical
- kind: release
- era: ALPACA
- date: 2026-11-03
- figures:
  - tag release-20261103-5 = e41f10b (PR #41 merged d963fb1); spec `c4_families.v5.20261103`; the core `cef_discount.v9.20261102` unchanged [V]
  - v5 on the VM's C4 panel as of 2026-11-02 (read-only): 74 targets, 18 eligible (8 long / 10 short), held gross 1.667× NAV, net 0.000 [V]
  - C4 AUTO_ARMED 18:02 ET; the first armed decide 22:00 2026-11-03; first sends 2026-11-04 15:52 [V]
- source: `docs/JOURNAL.md` (PR #48); `ops/specs/c4_families.frozen.json` @ `d963fb1`
- supports: §1, §4
- status: current

### E-2026-11-03-41 · Finding: the drawdown read is UNMEASURED at every 22:00 decide, because the EOD row for the as-of date is never written yet
- kind: result
- era: ALPACA
- date: 2026-11-03
- figures:
  - 4 of 4 core decides that carry the field (as-of 10-28, 10-29, 10-30, 11-02): UNMEASURED, each because eod_equity.csv's newest row is D−1 (prod plan.json records, read 2026-11-03) [V]
  - the missing-NAV field: present in 3 decides, 0 holds (n too small) [V]
- source: `results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md` @ `37806f7` (the K0 ruling that answers this finding); the VM's `quantt_state/cef/<date>/plan.json` records, read over ssh, read-only, not tracked
- supports: §5
- status: open. HALVE/KILL in `on` mode would refuse every decide, and te4's K0 would flatten every reduced session, until the read rule is ruled on

### E-2026-11-03-42 · Ruling: te4's K0 reads the previous session's EOD row, answering E-2026-11-03-41 (the 22:00 decide never has the day's row); the missing-NAV hold frequency stays unmeasured
- kind: ruling
- era: ALPACA
- date: 2026-11-03
- figures:
  - The drawdown field exists in 4 decides (as-of 10-28, 10-29, 10-30, 11-02). All 4 read UNMEASURED for the same reason: "eod_equity.csv's newest row on or before the as-of is D−1, not the as-of D" [S]
  - "Ruled: K0 reads D−1's row, labelled one session stale." If that row is older than D−1, missing or bad, K0 reads UNMEASURED and the session flattens (team lead, 2026-11-03) [S]
  - §6.3's bootstrap modelled K0 acting from the second session after the crossing; under D−1 it acts from the third, so §6.3's K0 figures are slightly optimistic [U]
  - The `missing_nav` field exists in 3 decides, none with a hold; the hold frequency stays UNMEASURED [S]
- source: `results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md` @ `e45e852`
- supports: §5
- status: current (answers E-2026-11-03-41, the owning session's finding; covers te4's K0 only)

### E-2026-11-03-43 · The first plans at release-20261103-5: the core's first ×1.30 and C4's first armed plan on the v5 blend (session 2026-11-04)
- kind: result
- era: ALPACA
- date: 2026-11-03
- figures:
  - core `cef_discount.v9.20261102`, smult 1.30: decided, no refusals; 11 orders (buy $14,313, sell $36,892); gross 1.025× → 1.797× NAV against the 1.80 cap (binding: gmax 1.80×0.9237); net −0.010×; pre-flight ok, stressed equity $98,431.87 (shock $1,529.38, 2026-03-20); gate 8 bp_scale 1.0, not binding; missing NAV none; 3 unresolved corporate-action rows BLOCKING in report mode, so nothing refused (the VM's quantt_state/cef/2026-11-04/plan.json) [V]
  - C4 `c4_families.v5.20261103`, smult 1.26: decided, no refusals; 15 orders (buy $63,363, sell $63,331); gross 0 → 1.267× NAV against the 1.90 cap; net 0.000×; all 74 targets tagged `level z_share=0.5000`; opening_session True, first_session CLEAR (0 foreign fills, 0 positions); missing NAV none; borrow: 7 names not shortable (DNP, HGLB, NFJ, PFO, RFI, RNP, SCD), none of them among the plan's shorts (quantt_state/c4/2026-11-04/plan.json and data/2026-11-03/report.json) [V]
  - C4's first fetch: `fetch_daily` exit 0, prices 402,947 rows and NAV 326,846 rows to 2026-11-03; 12 NAV-repeat flags masked by C4's M1; VM memory 292 MB used of 950 with both books [V]
- source: `docs/JOURNAL.md` @ `f296969` (2026-11-03, 22:17–23:50 ET); the VM's plan.json and collect report, read-only, not tracked
- supports: §1, §4
- status: the core's plan stands; C4's is withheld (E-2026-11-03-44)

### E-2026-11-03-44 · Incident: C4's first fetch wrote IGR's split-adjusted pre-split closes against unadjusted NAVs; C4 halted for the 2026-11-04 session
- kind: incident
- era: ALPACA
- date: 2026-11-03
- figures:
  - IGR closes for 2026-05-04..2026-09-04 replaced at a constant ×3.0 against the seed (83 rows); NAVs unchanged; IGR's discount reads about +200% (05-04: close 14.04 vs NAV 4.64; seed close 4.68) instead of about +1.5% (the VM's data/cef_c4 against ~/c4_seed) [V]
  - the 2026-11-04 plan bought 520 IGR (about $5,876, 5.9% of NAV) on z=−0.79, mostly the artifact; the other 14 orders were clean (no other price row moved beyond 0.5%; one SCD NAV row 0.7%) [V]
  - checklist step 5 (a step, not a spike, means STOP): the team lead ruled "Hold C4 one day, fix IGR". `ops/HALT_c4.md` was written in the prod clone at 23:47 ET; the runner's `halts_for` reads it for c4 and nothing for cef [V]
- source: `docs/JOURNAL.md` @ `f296969` (2026-11-03, 22:17–23:50 ET); `results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md` @ `f296969` step 5
- supports: §4, §5
- status: open. The fix makes C4's fetch keep one price basis with its NAVs, plus a fetch-time step guard, then a release; the halt is cleared after a clean decide

### E-2026-11-03-90 · cef paper book, 2026-11-03: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-11-03
- figures:
  - verify verdict PASS; orders sent 6, filled 6 [S]
  - 17:30 ET snapshot equity change 813.19 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L 793.28 USD [S]
  - fills vs official close 16.67 bp (+ = worse) [S]
  - TCA notional-weighted slippage 16.67 bp, fill rate 1.0000 of shares [S]
  - shadow book 864.14 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:b5e46b822424`; `results/report/data/live/cef/verify.csv` @ `pull:b5e46b822424`; `results/report/data/live/cef/tca.csv` @ `pull:b5e46b822424`
- supports: §4
- status: current

### E-2026-11-04-10 · Correction: a merge interleaved E-2026-11-03-35..39, and E-39/41/43/44 failed the log's format; restored from the clean commits, no figure changed
- kind: correction
- era: ALPACA
- date: 2026-11-04
- figures:
  - none (a structural repair: the merge of #49 into #50's branch, b66179f, joined conflict hunks so that E-2026-11-03-35..39 each carried another entry's body, and E-37 had two source blocks; `scripts/report/evidence_log.validate` found 12 problems on main f296969, and CI does not run it)
- source: `results/report/EVIDENCE_LOG.md` @ `f296969` (corrupted); restored from `results/report/EVIDENCE_LOG.md` @ `37806f7` for E-35..37 and E-42 (main before #50 merged, the merge's first parent), @ `fde513b` for E-38..41 and E-2026-11-03-90, and @ `699a15b` for E-43..44
- supports: §5
- status: current. Each header has its own body again, with the text as first written. E-39, -41, -43 and -44 have their format fixed: kind `finding`/`live-plan` became `result`, the provenance tags moved to the end of each figure, and sources now cite `path` @ `commit`. No figure changed. Found by 2027-ae

### E-2026-11-04-11 · Release: release-20261104-1 (C4 fetch keeps one price basis with its NAVs; fetch-time basis-step guard; repair-basis) installed, and IGR's stored history repaired
- kind: release
- era: ALPACA
- date: 2026-11-04
- figures:
  - tag release-20261104-1 = 509b3ff (PR #53 merged b24af5e; release-check GO with conditions); the core unchanged, armed at ×1.30 [V]
  - IGR ruling signed by the team lead on 2026-11-04: ex-date 2026-09-08, factor 1/3, to_nav_basis [V]
  - repair-basis on the VM's C4 panel: 87 IGR rows 2026-05-04..2026-09-04, close_before/close_after = 3.0 on every row, and close_after identical to the seed's raw close on all 87 (max difference 0.0) [V]
  - IGR premium 2026-05-04..09-04 after the repair: median +0.64%, min −1.96%, max +3.17% (about +200% before) [V]
  - a direct `fetch_daily --data-book c4 --require-asof 2026-11-03`: exit 0, with the line "BASIS IGR 2026-05-04..2026-09-04: 87 fetched pre-split row(s) ... put on the NAV's" and no BASIS-STEP [V]
- source: `scripts/cef/data_books.py` @ `509b3ff`; `results/cef/c4/c4_fetch_split_rulings_2026-11-03.json` @ `509b3ff`; the VM's repair log `data/cef_c4/basis_repair_log.csv` (not tracked), read-only
- supports: §1, §4, §5
- status: current. A pre-repair backup is at `quantt_state/c4/_backup_20261104_pre_repair/`

### E-2026-11-04-12 · C4's 2026-11-04 plan re-decided on the repaired panel and approved by sha; the unsent corrupt plan retired
- kind: result
- era: ALPACA
- date: 2026-11-04
- figures:
  - the retired plan (decided 22:00 on 11-03, never sent: no STARTED, send.json or orders.jsonl; at Alpaca 0 positions, 0 open and 0 closed orders) moved to `quantt_state/c4/_retired/2026-11-04_igr_basis/` [V]
  - re-decided at the 09:30 slot: 15 orders, gross 1.284× against the 1.90 cap, net +0.001×, opening_session True, first_session CLEAR, no refusals; plan_sha 17ddda95fe06df1de726cd3fec0ab99efaada7bdc4eb62682fbe489d17e67ee5 [V]
  - IGR: z −2.65, w +0.1152, buy 1,019, against the retired plan's z −0.79, w +0.0588, buy 520; the same 15 names, the others re-scaled [V]
  - approved by sha at 09:36 ET (C4 was armed without AUTO_ARMED until then); AUTO_ARMED restored at 09:36 for later sessions; the send window is 15:52–15:58 [V]
- source: `scripts/cef/fetch_daily.py` @ `509b3ff`; the VM's `quantt_state/c4/2026-11-04/plan.json` and APPROVED (not tracked), read-only
- supports: §1, §4
- status: current

### E-2026-11-04-90 · cef paper book, 2026-11-04: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-11-04
- figures:
  - verify verdict PASS; orders sent 11, filled 11 [S]
  - 17:30 ET snapshot equity change -69.91 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]
  - auction-marked P&L -232.04 USD [S]
  - fills vs official close 18.30 bp (+ = worse) [S]
  - TCA notional-weighted slippage 18.30 bp, fill rate 1.0000 of shares [S]
  - shadow book -249.75 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:c3fef52e05e2`; `results/report/data/live/cef/verify.csv` @ `pull:c3fef52e05e2`; `results/report/data/live/cef/tca.csv` @ `pull:c3fef52e05e2`
- supports: §4
- status: current

### E-2026-11-04-13 · Both books traded on 2026-11-04: the core's first ×1.30 session and C4's first session ever, both verify PASS
- kind: live-pnl
- era: ALPACA
- date: 2026-11-04
- figures:
  - core: 11 of 11 orders filled; verify PASS; snapshot 17:30 ET −$69.91, auction-marked −$232.04 (gross); fill against the auction +18.3bp (worse); official EOD pending at verify [V]
  - C4: 15 of 15 orders filled (sha 17ddda95… approved at 09:36); verify PASS; snapshot 17:30 ET −$89.10, auction-marked −$8.60 (gross); fill against the auction +0.7bp; official EOD pending at verify [V]
- source: `results/report/data/live/cef/verify.csv` @ `8fd35ee` (the core, pull:c3fef52e05e2); C4's pull `pull:98c1901d5803` (its verify.out.log; C4's automated ingest is PENDING because C4 writes no distribution_scores.csv yet)
- supports: §4
- status: current

### E-2026-11-04-14 · Correction to E-2026-11-03-43: the core's "gross 1.025× → 1.797×" was the sleeve's target gross, not the book after the trades
- kind: correction
- era: ALPACA
- date: 2026-11-04
- figures:
  - E-43 summed |target shares × close| over every name. Names inside their band are not traded to target, so that is the target gross. 11-04's 11 orders totalled about $51.2k, so gross after them could not exceed about 1.54× [V]
  - the core's book at the 11-05 decide (after 11-04's fills): 1.174× NAV, the measured figure [V]
- source: `docs/JOURNAL.md` @ `718b699` (11-04 entry); `results/report/EVIDENCE_LOG.md` @ `718b699` (E-2026-11-03-43, as written)
- supports: §1, §4
- status: current. E-43's other figures stand. C4's 1.267× in E-43 was an opening session, where every name trades to target, so it is unaffected. The same error was in the 11-03 report to the team lead and is corrected there

### E-2026-11-04-15 · C4's 11-05 decide is deferred on KYN's late NAV (the missing-NAV hold, by design); the IGR fix holds through a nightly fetch
- kind: result
- era: ALPACA
- date: 2026-11-04
- figures:
  - C4 22:00 decide REFUSED (data): "NAV not dated 2026-11-04 for KYN (2026-11-03)", deferred to a later slot; from the final check (14:30 ET) KYN is held at its current shares and the other names decide; refresh exit 4 (INCOMPLETE), not 7 [V]
  - checklist step 5 after the 11-04 fetch: IGR premium 05-04..09-04 median +0.64%, min −1.96%, max +3.17%, unchanged; 0 seed-window closes moved beyond 0.5% [V]
  - 20 collect flags, all borrow-snapshot changes in 10 funds (e.g. HPS, JRS, STK and TY no longer shortable, RNP now shortable); none of C4's eight held shorts is among them [V]
  - the core's 11-05 plan: decided, 6 orders, the book 1.174× before, pre-flight ok, missing NAV none, drawdown UNMEASURED (the D−1 row, E-2026-11-03-41) [V]
- source: C4's pull `pull:98c1901d5803`; `scripts/cef/fetch_daily.py` @ `509b3ff`
- supports: §4, §5
- status: current

### E-2026-11-03-91 · c4 paper book, 2026-11-03: FAIL, did not trade
- kind: live-pnl
- era: ALPACA
- date: 2026-11-03
- figures:
  - verify verdict FAIL; orders sent 0, filled 0 [S]
  - 17:30 ET snapshot equity change 0.00 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change 0.00 USD (Alpaca portfolio history 1D, the P&L of record) [S]
  - auction-marked P&L 0.00 USD [S]
  - distribution-adjusted P&L UNMEASURED: distribution_scores.csv not in this pull [U]
  - shadow book 0.00 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/c4/scores.csv` @ `pull:98c1901d5803`; `results/report/data/live/c4/verify.csv` @ `pull:98c1901d5803`; `results/report/data/live/c4/tca.csv` @ `pull:98c1901d5803`
- supports: §4
- status: current

### E-2026-11-04-91 · c4 paper book, 2026-11-04: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-11-04
- figures:
  - verify verdict PASS; orders sent 15, filled 15 [S]
  - 17:30 ET snapshot equity change -89.10 USD (gross; a snapshot, not the P&L of record) [S]
  - official EOD equity change UNMEASURED: eod_equity.csv in this pull has no change_usd for 2026-11-04 [U]
  - auction-marked P&L -8.60 USD [S]
  - fills vs official close 0.66 bp (+ = worse) [S]
  - TCA notional-weighted slippage 0.66 bp, fill rate 1.0000 of shares [S]
  - distribution-adjusted P&L UNMEASURED: distribution_scores.csv not in this pull [U]
  - shadow book 0.00 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/c4/scores.csv` @ `pull:98c1901d5803`; `results/report/data/live/c4/verify.csv` @ `pull:98c1901d5803`; `results/report/data/live/c4/tca.csv` @ `pull:98c1901d5803`
- supports: §4
- status: current

### E-2026-11-05-20 · Correction to E-2026-11-03-90: its official EOD figure was UNMEASURED because eod_equity.csv had no point for 11-03 yet, not because the file was missing from the pull
- kind: correction
- era: ALPACA
- date: 2026-11-05
- figures:
  - E-2026-11-03-90 reads "official EOD equity change UNMEASURED: eod_equity.csv not in this pull"; its pull b5e46b822424 carried eod_equity.csv (pulls.csv lists it) [S]
  - that file's last point was 2026-11-02 (change 178.55 USD), so it held none for 2026-11-03 [S]
  - snapshot_live now writes "eod_equity.csv in this pull has no change_usd for <D>" in that case, and "not in this pull" only when the file is absent [S]
- source: `results/report/data/live/cef/pulls.csv` @ `718b699`; `results/report/data/live/cef/eod_equity.csv` @ `718b699`; `scripts/report/snapshot_live.py` @ `f579eb1`
- supports: §4
- status: supersedes the stated reason in E-2026-11-03-90's EOD figure only; the figure was UNMEASURED either way and its other figures stand. The earlier cef live-day entries (pull 24d55dcbfe1b) are right: that pull did not carry eod_equity.csv

### E-2026-11-05-21 · Method: snapshot_live ingests a C4 pull without distribution_scores.csv and names the distribution-adjusted P&L UNMEASURED; a core pull must still carry the file
- kind: method
- era: ALPACA
- date: 2026-11-05
- figures:
  - none (a method change. C4's verify scores a session's distributions two sessions late, so its first pulls carry no distribution_scores.csv, and the core's rule refused them. Optional for C4 only: no distribution table is written, and each live-day entry says "distribution-adjusted P&L UNMEASURED: distribution_scores.csv not in this pull"; never a zero. The first ingest under it is C4's pull 98c1901d5803: E-2026-11-03-91 and E-2026-11-04-91. C4's equity is figure F06_live_equity_c4)
- source: `scripts/report/snapshot_live.py` @ `264d00b`; `scripts/report/tests/test_snapshot_live.py` @ `264d00b`; `results/report/data/live/c4/pulls.csv` @ `905fb00`
- supports: §4, §5
- status: current

### E-2026-11-05-22 · Correction to E-2026-11-04-90: its official EOD figure was UNMEASURED because eod_equity.csv had no point for 11-04 yet, not because the file was missing from the pull
- kind: correction
- era: ALPACA
- date: 2026-11-05
- figures:
  - E-2026-11-04-90 reads "official EOD equity change UNMEASURED: eod_equity.csv not in this pull"; its pull c3fef52e05e2 carried eod_equity.csv (pulls.csv lists it) [S]
  - that file's last point was 2026-11-03 (change 793.10 USD), so it held none for 2026-11-04 [S]
  - snapshot_live now writes "eod_equity.csv in this pull has no change_usd for <D>" in that case, and "not in this pull" only when the file is absent [S]
- source: `results/report/data/live/cef/pulls.csv` @ `837408c`; `results/report/data/live/cef/eod_equity.csv` @ `837408c`; `scripts/report/snapshot_live.py` @ `f579eb1`
- supports: §4
- status: supersedes the stated reason in E-2026-11-04-90's EOD figure only; the figure was UNMEASURED either way and its other figures stand (the same defect as E-2026-11-03-90, corrected by E-2026-11-05-20)

### E-2026-11-05-30 · The core's paper fill cost is the quoted half-spread (half a cent a share); no send time inside the window narrows it, and none of it carries over to a live MOC fill
- kind: result
- era: ALPACA
- date: 2026-11-05
- figures:
  - core, 21 late_market sessions 2026-09-30..11-04, 142 orders, 376 fills: B (fill vs the official closing print) 7.14bp pooled; day mean 8.62bp, t 3.20 [V]
  - of which paid vs the mid at send 5.90bp (day t 26.66) = quoted half-spread 5.98bp + fill vs touch −0.08bp; drift send → print C2 −1.24bp (day t −1.02) [V]
  - every late_market fill of both books (427) printed at the touch; 89.7% of core notional traded at a one-cent spread; paid $0.00538 a share [V]
  - fill vs the decide-time estimate 31.52bp, of which decide close → mid at send 25.62bp (day t 2.81; open → send 20.81bp) [V]
  - B ties to verify.csv fill_vs_auction_bp on 17 of 17 days, max difference 0.05bp [V]
  - quoted half-spread, core 13 names × 21 sessions: 8.98bp at 15:50:00, 5.98–6.15bp from 15:51:00 to 15:59:30 [V]
  - post at the passive touch, cross the rest at 15:58:00: B 4.12bp, −2.18bp against actual (day t −1.93) [V]
  - core turnover 62.14 turns/yr (2026-09-29..11-04) and 66.25 (from 10-07); paper B at that turnover 4.44–4.73% of NAV a year [V]
  - core orders as a share of the day's primary closing cross: median 6.2%, notional-weighted median 15.2%, p90 35.9% [V]
  - C4, one session (2026-11-04, opening build): B 0.66bp, spread paid 10.66bp; C4's 15 names quote a mean 10.55bp half-spread at 15:52 over 21 sessions [V]
- source: `results/cef/EXEC_COST_STUDY_2026-11-05.md` @ `137ea8e`; `results/cef/exec_cost_2026-11-05/aggregates_2026-11-05.json` @ `137ea8e`; `results/cef/exec_cost_2026-11-05/exec_cost.py` @ `137ea8e`
- supports: §4, §3
- status: current (report only, zero trials; 21 sessions and one C4 session, so no cell or counterfactual is a tested effect; candidates proposed, none adopted)

### E-2026-11-05-40 · Method: the band width re-derived from the measured paper cost lands at 4.55% (core) and 4.07% (C4); the draft recommends adopting neither, and CEF stays 55
- kind: method
- era: ALPACA
- date: 2026-11-05
- figures:
  - core: the cube-root law at the measured paper cost 7.14bp, sigma_w 0.06134/day and phi_w 0.95807 (half-life 16.2d) on the fit's active pairs 2013-06-24..2022-12-30, gives h* 4.55% in unit weights (0.045 as written); the cost's 95% interval 3.00-14.24bp gives 3.41-5.72%; live 4.8% [V]
  - C4 (v5 blend): c = 7.14bp x quoted-spread ratio 1.741 = 12.43bp; sigma_w 0.04880, phi_w 0.93624; h* 4.07% (0.040 as written) [V]
  - plateau on the fit, the accounts' books (core x1.30 flatten, C4 x1.26): both derived widths pass the declared paired test (argmax minus h*, HAC p 0.20 core, 0.14 C4); grid argmaxes 1.6% (core) and 6.4% (C4) named and not chosen [V]
  - core 0.045 minus 0.048: net at 7.14bp +0.0385pp/yr, Newey-West t 1.34 (lag 21) against the bar sqrt(2 ln 56) = 2.837; turnover +3.3% [V]
  - C4 h* minus live at 12.43bp: -0.058 Sharpe, HAC p 0.038 on total return (unadjusted), p 0.15 price only [V]
  - the 2026-09-06 sigma_w (0.04083) is not reproduced: the 17-name fit gives 0.06050 under this definition, with phi_w 0.95246 against 0.95280 [V]
- source: `results/cef/PREREG_DRAFT_BAND_COST_2026-11-05.md` @ `bb1c237`; `results/cef/band_cost_2026-11-05/band_cost_2026-11-05.json` @ `bb1c237`; `results/cef/band_cost_2026-11-05/crosscheck_2026-11-05.txt` @ `bb1c237`; `results/cef/band_cost_2026-11-05/band_cost.py` @ `d06ed06`
- supports: §3, §6
- status: current (a DRAFT pre-registration, not approved; zero trials; fit only, no 2023+ figure computed; the cost inputs are from the unmerged execution-cost study, PR #58 at 2476a16)

### E-2026-11-05-41 · Ruling: the band stays 4.8% on both books (the re-derivation at the measured cost is CLOSED at zero trials, CEF stays 55), and post-then-cross is "not now"
- kind: ruling
- era: ALPACA
- date: 2026-11-05
- figures:
  - the band: "Accept: keep 4.8%, close" (team lead, relayed by the coordinating session). Both books keep band_width 0.048; zero trials; CEF stays 55; a CLOSED row BAND-COST in docs/RESEARCH_STATE.md [S]
  - follow-ups ruled with it: C4's band is re-measured on its own fill cost after 21 sessions, no earlier than 2026-12-03; the band is re-derived on a measured live auction impact before any real capital [S]
  - post-then-cross on paper (the execution study's candidate 1): "Not now"; not built; re-test after 60+ sessions of fills [S]
  - what was ruled on: derived h* 4.55% (core, at 7.14bp) and 4.07% (C4, at 12.43bp); the core's 0.045 minus 0.048 nets +0.0385pp/yr at NW t 1.34 against the bar 2.837 at N = 56 (E-2026-11-05-40) [V]
- source: `results/cef/BAND_COST_REDERIVATION_2026-11-05.md` @ `3668da1`; `docs/SYSTEM.md` @ `3668da1`; `docs/RESEARCH_STATE.md` @ `3668da1`; `results/cef/EXEC_COST_STUDY_2026-11-05.md` @ `1f44bbf` (PR #58's merge to main; byte-identical to 2476a16, which the analysis read)
- supports: §2, §3, §6
- status: current; closes the draft pre-registration of E-2026-11-05-40 (that entry stands as the record of the analysis; its note was renamed from PREREG_DRAFT_BAND_COST_2026-11-05.md)

### E-2026-11-05-90 · cef paper book, 2026-11-05: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-11-05
- figures:
  - verify verdict PASS; orders sent 5, filled 5 [S]
  - 17:30 ET snapshot equity change 22.75 USD (gross; a snapshot, not the P&L of record) [U]
  - official EOD equity change -83.72 USD (Alpaca portfolio history 1D, the P&L of record) [U]
  - auction-marked P&L -83.31 USD [S]
  - snapshot and EOD disagree; the record is the EOD history (docs/SYSTEM.md §5, 2026-10-19) [U]
  - fills vs official close 10.20 bp (+ = worse) [S]
  - TCA notional-weighted slippage 10.20 bp, fill rate 1.0000 of shares [S]
  - shadow book 109.44 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:ae2279000743`; `results/report/data/live/cef/verify.csv` @ `pull:ae2279000743`; `results/report/data/live/cef/tca.csv` @ `pull:ae2279000743`
- supports: §4
- status: current

### E-2026-11-06-90 · cef paper book, 2026-11-06: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-11-06
- figures:
  - verify verdict PASS; orders sent 13, filled 13 [S]
  - 17:30 ET snapshot equity change -308.14 USD (gross; a snapshot, not the P&L of record) [U]
  - official EOD equity change -266.98 USD (Alpaca portfolio history 1D, the P&L of record) [U]
  - auction-marked P&L -266.09 USD [S]
  - snapshot and EOD disagree; the record is the EOD history (docs/SYSTEM.md §5, 2026-10-19) [U]
  - fills vs official close 7.20 bp (+ = worse) [S]
  - TCA notional-weighted slippage 7.20 bp, fill rate 1.0000 of shares [S]
  - shadow book -283.69 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:ae2279000743`; `results/report/data/live/cef/verify.csv` @ `pull:ae2279000743`; `results/report/data/live/cef/tca.csv` @ `pull:ae2279000743`
- supports: §4
- status: current

### E-2026-11-05-91 · c4 paper book, 2026-11-05: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-11-05
- figures:
  - verify verdict PASS; orders sent 2, filled 2 [S]
  - 17:30 ET snapshot equity change 1278.00 USD (gross; a snapshot, not the P&L of record) [U]
  - official EOD equity change 1243.68 USD (Alpaca portfolio history 1D, the P&L of record) [U]
  - auction-marked P&L 1244.07 USD [S]
  - snapshot and EOD disagree; the record is the EOD history (docs/SYSTEM.md §5, 2026-10-19) [U]
  - fills vs official close 18.04 bp (+ = worse) [S]
  - TCA notional-weighted slippage 18.04 bp, fill rate 1.0000 of shares [S]
  - shadow book 1279.07 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/c4/scores.csv` @ `pull:56ee16669d9a`; `results/report/data/live/c4/verify.csv` @ `pull:56ee16669d9a`; `results/report/data/live/c4/tca.csv` @ `pull:56ee16669d9a`
- supports: §4
- status: current

### E-2026-11-06-91 · c4 paper book, 2026-11-06: PASS, traded
- kind: live-pnl
- era: ALPACA
- date: 2026-11-06
- figures:
  - verify verdict PASS; orders sent 3, filled 3 [S]
  - 17:30 ET snapshot equity change -1190.10 USD (gross; a snapshot, not the P&L of record) [U]
  - official EOD equity change -1225.93 USD (Alpaca portfolio history 1D, the P&L of record) [U]
  - auction-marked P&L -1225.80 USD [S]
  - snapshot and EOD disagree; the record is the EOD history (docs/SYSTEM.md §5, 2026-10-19) [U]
  - fills vs official close 23.38 bp (+ = worse) [S]
  - TCA notional-weighted slippage 23.38 bp, fill rate 1.0000 of shares [S]
  - shadow book -1181.63 USD (MODELLED, not broker evidence) [S]
- source: `results/report/data/live/c4/scores.csv` @ `pull:56ee16669d9a`; `results/report/data/live/c4/verify.csv` @ `pull:56ee16669d9a`; `results/report/data/live/c4/tca.csv` @ `pull:56ee16669d9a`
- supports: §4
- status: current

### E-2026-11-08-01 · Sessions 2026-11-05 and 11-06: both books verify PASS; the core's ×1.30 book reaches its cap; one send-time short skip
- kind: result
- era: ALPACA
- date: 2026-11-08
- figures:
  - official EOD change, core: 11-04 −$232.83, 11-05 −$83.72, 11-06 −$266.98; equity $99,405.98, −$594.02 since funding [V]
  - official EOD change, C4: 11-04 −$9.96, 11-05 +$1,243.68, 11-06 −$1,225.93; equity $100,007.79, +$7.79 since funding [V]
  - core 11-05: 5 of 6 planned orders sent and filled; the sixth, an MHD short, was skipped at send (shortable=False); 11-06: 13 of 13 filled [V]
  - C4 11-05: 2 of 2 filled; 11-06: 3 of 3 filled [V]
  - fill against the official close: core +10.2bp and +7.2bp; C4 +18.0bp and +23.4bp, on 2 and 3 orders [V]
  - core gross from positions and orders: 1.517× before the 11-06 plan, 1.799× after it; Alpaca's account values read 2026-11-08 give 1.827× gross and +0.176× net, with maintenance margin 0.80 of equity [V]
- source: `results/report/data/live/cef/verify.csv` @ `pull:ae2279000743`; `results/report/data/live/c4/verify.csv` @ `pull:56ee16669d9a`; the VM's plan.json and send.json records, read-only, not tracked
- supports: §4, §5
- status: current

### E-2026-11-08-02 · The plans for 2026-11-09, read before the send; C4's data checks clean
- kind: result
- era: ALPACA
- date: 2026-11-08
- figures:
  - core `cef_discount.v9.20261102`: decided, no refusals, 13 orders ($37,973 notional); the book 1.828× before and 1.784× after them against the 1.80 cap; net +0.177× to +0.055×; pre-flight ok; gate 8 bp_scale 1.0; drawdown UNMEASURED [V]
  - C4 `c4_families.v5.20261103`: decided, no refusals, 2 orders ($1,431 notional); the book 1.350× before and 1.335× after them against the 1.90 cap; net −0.089× to −0.075×; pre-flight ok [V]
  - short-opens on 11-09: core PTY and JFR, both shortable in the 11-06 borrow snapshot; C4 none [V]
  - C4 held shorts against borrow: UTF is no longer shortable (an existing short, no new short planned); the other eight are shortable [V]
  - checklist step 5 on the panel to 2026-11-06: IGR premium 05-04..09-04 median +0.64%, min −1.96%, max +3.17%; 0 seed-window closes moved beyond 0.5% [V]
- source: `results/report/data/live/c4/verify.csv` @ `pull:56ee16669d9a`; the VM's plan.json and collect reports, read-only, not tracked
- supports: §1, §4
- status: current

### E-2026-11-08-03 · Incident: the 2026-11-05 evening check ran three days late, and the VM was out of reach until the ssh firewall rule was updated
- kind: incident
- era: ALPACA
- date: 2026-11-08
- figures:
  - the check scheduled for 22:17 ET on 2026-11-05 ran on 2026-11-08, because the scheduled job lives only in an open, idle Claude session; the 11-06 plans sent unread (both passed verify) [V]
  - ssh timed out because the firewall rule no longer matched the team lead's IP; the VM was running and the book trading throughout (Alpaca: core fills on 11-05 and 11-06); the team lead updated the rule on 2026-11-08 [V]
- source: `docs/RUNBOOK.md` @ `6c6b9fd` (the IP-change procedure)
- supports: §5
- status: open. The evening check has no owner outside an open session; the VM timer in the agent-desk draft (PR #46) is the proposed fix

### E-2026-11-08-04 · Ruling: research is not pass or fail. A failed gate no longer ends an idea, the power check stops only at very low odds, holdouts can be re-opened with each look counted, and entry to the paper account is the team lead's decision on a scorecard
- kind: ruling
- era: ALPACA
- date: 2026-11-08
- figures:
  - the team lead: "not a no go no only rules, we need to be dynamic - this is too binary" [S]
  - the audit behind the re-review, 82 ideas: CORRECT KILL 29, IMPLEMENTATION 26, UNDERPOWERED 20; the 26 and the 20 are re-reviewed, best first on market reasoning [S]
  - the power check stops below P(pass) 0.10 and warns from 0.10 to 0.50; it stopped below 0.50 before (the 2026-10-27 row of `docs/SYSTEM.md` §5) [S]
- source: `results/research/DESK_METHOD_2026-10-27.md` @ `a5b94c8`; `docs/SYSTEM.md` @ `a5b94c8` (the rows it changes; the ruling itself is added in this commit)
- supports: §5
- status: current; for research agents and the research loop only. The live book's stops, real-capital admission and the analysts' process are unchanged

### E-2026-11-05-31 · Ruling: the analysts' lanes reopen as starting points, any analyst may propose a signal, and each pitches one idea to the execs at the end of November
- kind: ruling
- era: ALPACA
- date: 2026-11-05
- figures:
  - no figures; lanes recorded as FICC risk, equity risk, and cross-asset signals with the dashboard, "open ended" [S]
  - the team lead approves every test, and a trial still needs approval before any return is computed; supersedes the 2026-11-03 report-only lanes [S]
  - each analyst pitches separately, a short talk with slides, end of November; date and length to be set [S]
- source: `docs/SYSTEM.md` @ `b63253d`
- supports: §5
- status: current

### E-2026-11-04-01 · CEF trial 55's code is built dark: paper declared only on the paper endpoint, K0 restricting on the freshest EOD row, a gate-7 flatten and K0–K3 report lines; with the key absent the sleeve and the session are byte-identical to main
- kind: method
- era: ALPACA
- date: 2026-11-04
- figures:
  - base: a worktree at 0b1a2ef2b308101b3512aec24dc49a22de98c888 [S]
  - decision dates: 7018 (1998-11-18 .. 2026-10-14, --dates all); books flat and held; 14036 (date, book) target lists per variant [S]
  - new:absent vs base:absent: 14036 of 14036 (date, book) pickles byte-identical [S]
  - new:flatten vs base:absent: 14036 of 14036 (date, book) pickles byte-identical [S]
  - new:hold vs base:hold: 14036 of 14036 (date, book) pickles byte-identical [S]
  - new:te4 vs base:absent on (date, book) with >= min_names eligible: 3716 of 3716 byte-identical with meta['cef_thin'] removed [S]
  - thin (date, book): 10320; reduced build ran on 3416; below the floor (FLAT) 6904; with holds 0 [S]
  - VERDICT: NO-OP PROVED (every comparison byte-identical) [S]
- source: `results/cef/te4_impl/sleeve_noop_diff_output_2026-11-04-headf3ad29f-main0b1a2ef.txt` @ `e4953e4`; `quantt/session/tests/test_trade_eligible_noop.py` @ `29ba857`; `quantt/session/run.py` @ `dbe46f3`; `quantt/session/drawdown.py` @ `f3ad29f`; `src/deploy/sleeves/cef_discount.py` @ `f3ad29f`
- supports: §1, §5
- status: current (the key is not set; it trades only from its activation commit)

### E-2026-11-04-02 · Ruling: te4's K0 reads the freshest EOD row it has, the as-of's own when it is there, else the previous session's
- kind: ruling
- era: ALPACA
- date: 2026-11-04
- figures:
  - none (a ruling: "K0 reads the as-of's own row when it is there (labelled 0 sessions stale), whatever it reads; a bad row reads UNMEASURED. Only when D's row has not landed does it read D−1's (labelled one session stale)"; team lead, 2026-11-04)
- source: `results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md` @ `dbe46f3`; `quantt/session/run.py` @ `dbe46f3`
- supports: §5
- status: current (refines E-2026-11-03-42: at the 22:00 decide nothing changes)

### E-2026-11-08-22 · CEF trial 55's stop lines after the owner's review: a reduced decision counts only if its targets were sent and filled, K3's run length is a required spec key, and missing sessions blank only the stops whose window holds them
- kind: method
- era: ALPACA
- date: 2026-11-08
- figures:
  - VERDICT: NO-OP PROVED (every comparison byte-identical), base 718b6996d87cf9a5ef83873f4fae4f82272def18, new 44808edda54d87dab321746b4be58cc00f413afc [S]
  - the compose.py re-run at `--k3-run-sessions 3` matches the drafting day's record apart from the stamp and the recorded run length [S]
  - "Sent, nothing filled": a SENT where every order in `final` ended with 0 shares filled, canceled, expired or rejected, and `not_final` is empty; never a FAIL [S]
- source: `results/cef/te4_impl/sleeve_noop_diff_output_2026-11-05-head44808ed-main718b699.txt` @ `30bcac5`; `results/cef/prereg_thin_te4/compose_output_2026-11-05.txt` @ `a126324`; `docs/RUNNER.md` @ `702b5de`; `quantt/session/drawdown.py` @ `702b5de`; `src/deploy/tests/test_thin_k3_run_provenance.py` @ `03d978b`
- supports: §1, §5
- status: current (the key is not set; it trades only from its activation commit)

### E-2026-11-08-20 · Correction: Alpaca paper does charge SEC and CAT regulatory fees, so CLAUDE.md landmine 1 and the paper rows of docs/REFERENCES.md are corrected
- kind: correction
- era: ALPACA
- date: 2026-11-08
- figures:
  - "GET /v2/account/activities/FEE lists 37 REG (SEC) and CAT rows, summing to −6.16" [V]
  - released by the team lead on 2026-11-08, after being held on 2026-11-02; Alpaca's page still says regulatory fees are not simulated, and the quotes of it are kept with a dated note [S]
- source: `results/cef/LIVE_ATTRIBUTION_2026-11-02.md` @ `32d9961`; `CLAUDE.md` @ `55dc94e`; `docs/REFERENCES.md` @ `55dc94e`
- supports: §4
- status: supersedes E-2026-11-02-08 (its deferral); corrects the landmine text quoted in E-2026-11-03-30

### E-2026-11-08-21 · Ruling: the exposure readout keeps 0 lags and the MUNI headline after the current-window lag sensitivity was put to the team lead
- kind: ruling
- era: ALPACA
- date: 2026-11-08
- figures:
  - none (a ruling: "on 2026-11-08 the team lead ruled: keep L = 0 and the MUNI headline"; it answers the question left open in E-2026-11-03-36)
- source: `scripts/cef/exposure_readout.py` @ `55dc94e`
- supports: §5
- status: current

### E-2026-11-08-23 · Rulings on CEF trial 55: the code ships dark, and the in-place edit of the approved pre-registration's compose commands is accepted
- kind: ruling
- era: ALPACA
- date: 2026-11-08
- figures:
  - none (rulings: "The implementation (PR #55) merges with the key absent, so the book keeps today's flatten rule"; the in-place edit carries a dated note and changes no figure; team lead, 2026-11-08)
- source: `results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md` @ `ca80123`
- supports: §2, §5
- status: current

### E-2026-11-08-05 · Rulings: a VM timer owns the nightly check, with push on fired stops; single-name size is measured, not capped; the corporate-action gate goes back to halt after a fix; HALVE/KILL's read is fixed, report-only
- kind: ruling
- era: ALPACA
- date: 2026-11-08
- figures:
  - none (rulings by the team lead: "VM timer, push on stops", "Measure it, change nothing", "Start the fix", "Fix the read, stay report-only")
- source: `docs/SYSTEM.md` @ `a5b94c8` (the section is added by this commit, on top of that main)
- supports: §1, §5
- status: current. The builds are in progress on branches `nightly-checks` and `ca-isin-fix`; the HALVE/KILL read follows PR #55

### E-2026-11-09-01 · Ruling: the mission. Scope is open, paper trading is the test, research is judged gross with no cost model, and pre-registration, the trial counters, the holdout ceremony and alpha-only are dropped; prod releases go back to the team lead alone
- kind: ruling
- era: ALPACA
- date: 2026-11-09
- figures:
  - none (a ruling: the team lead's written brief, kept verbatim as `docs/MISSION.md`, and three answers given interactively: "Team lead only" on prod releases, "Drop it" on alpha-only, "Rewrite to master.md §2" on `CLAUDE.md`'s research rules)
- source: `docs/SYSTEM.md` @ `3595ec8` (the section "Team lead, 2026-11-09" is added by this commit, on top of that main); `docs/MISSION.md` @ `3595ec8` (added by this commit)
- supports: §1, §5
- status: current. Supersedes E-2026-11-08-04 (2026-11-08) where the two differ: re-tests and holdout looks are no longer counted, and entry to paper is the agent's own through a paper/shadow path whose design the team lead approves once. `docs/RESEARCH_STATE.md`'s counters are frozen

### E-2026-11-09-02 · Method: the idea ledger replaces the trial counters, and is backfilled with every idea tested before 2026-11-09; 13 of them had a measured positive gross effect and were stopped by a cost, factor-exposure or deflated-bar gate
- kind: method
- era: ALPACA
- date: 2026-11-09
- figures:
  - 13 backfilled ideas with a measured positive gross effect stopped by a retired gate (a count of the ledger's rows, the author's reading of each) [S]
  - month-end Treasury extension (XASSET-X3): gross Sharpe 1.04, NW t 4.94, 2002-09 to 2022-12 [S]
- source: `results/IDEA_LEDGER.md` @ `3595ec8` (added by this commit); `docs/RESEARCH_STATE.md` @ `3595ec8`; `results/mission/PHASE0_2026-11-09.md` @ `3595ec8` (added by this commit)
- supports: §3, §5
- status: current

### E-2026-11-09-03 · Ruling: the shadow-book runner's design is approved once; it runs on the VM as a separate user, is marked on Alpaca's auction prints with a yfinance check, and simulates each book at $1M; the analysts keep their process
- kind: ruling
- era: ALPACA
- date: 2026-11-09
- figures:
  - none (a ruling: "Approve", "VM, separate user and clone", "Alpaca auction prints + yfinance check", "$1M per book", "Keep TEAM.md process", "Shadow books first", "I run the free fetchers")
- source: `docs/SYSTEM.md` @ `d98fa5e` (the rows are added by this commit); `results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md` @ `d98fa5e` (added by this commit)
- supports: §1, §5
- status: current. The engine is built in `shadow/` with tests; no book is running, and the VM install is the team lead's

### E-2026-11-09-04 · Method: the shadow engine decides on truncated panels, writes each decision once, scores only decisions written before 13:00 New York on the fill session, and reproduces the harness's shift(2) P&L on synthetic data
- kind: method
- era: ALPACA
- date: 2026-11-09
- figures:
  - none (code and tests on synthetic data: a claim about the code, not the market)
- source: `shadow/engine.py` @ `d98fa5e` (added by this commit); `shadow/tests/test_engine.py` @ `d98fa5e` (added by this commit)
- supports: §5
- status: current

### E-2026-11-09-05 · Method: the agent layer is rebuilt for the mission: six seats and seven commands, the pre-registration skill and the event census removed, and the research loop reduced to a stub that stops
- kind: method
- era: ALPACA
- date: 2026-11-09
- figures:
  - none (agent, skill, workflow and rule files; no return computed)
- source: `.claude/README.md` @ `d98fa5e` (rewritten by this commit); `CLAUDE.md` @ `d98fa5e` (its desk section is rewritten by this commit)
- supports: §5
- status: current. Three scripts still cite the removed pre-registration skill in comments, and `scripts/research/harness.py` `report()` still returns cost columns: both are left for the next change to those files

### E-2026-11-09-06 · Ruling and result: the shadow runner reads data with the core account's key, and its auction-print reader returned every print asked for, each equal to yfinance's close
- kind: ruling
- era: ALPACA
- date: 2026-11-09
- figures:
  - 88 of 88 closing-auction prints returned (8 symbols: SPY IEF PDI PTY QQQ JFR HYG TLT; 11 sessions, 2026-10-26 to 2026-11-09) [S]
  - 0 of 88 differ from yfinance's unadjusted close (maximum absolute difference 0.00bp) [S]
  - NYSE Arca maps to SIP code P, official close at condition M (measured on SPY, 2026-11-06) [S]
- source: `results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md` @ `d98fa5e` (the amendment is added by this commit); `docs/SYSTEM.md` @ `d98fa5e` (the row is added by this commit); `shadow/sources.py` @ `d98fa5e`
- supports: §4, §5
- status: current. Supersedes the "otherwise empty paper account" part of E-2026-11-09-03 (2026-11-09). One run from the laptop, not independently repeated

### E-2026-11-10-01 · Result: month-end Treasury demand (long IEF over the last three sessions of a month) earns a gross Sharpe of 1.07 over 2002-09 to 2026-10-09, in both halves and all five eras, and goes on shadow
- kind: result
- era: ALPACA
- date: 2026-11-10
- figures:
  - gross Sharpe 1.07, t 5.26, 2.63%/yr at 2.45% vol, 6,064 sessions of which 861 in the window; shift(2), unit weight, no cost modelled; panel to 2026-10-09 [S]
  - early half (to 2014-09-19) Sharpe 1.01; late half 1.15 [S]
  - eras: 2002–08 1.04; 2009–15 0.97; 2016–19 1.76; 2020–22 1.08; 2023 to 2026-10-09 0.88 [S]
  - control, IEF on every other session: Sharpe 0.10, t 0.49 [S]
  - position against IEF's 2026 median daily dollar volume: 0.14% at $1M, 0.68% at $5M, 1.35% at $10M [S]
- source: `results/ideas/2026-11-10_month_end_treasury.md` @ `e36ee83` (added by this commit); `results/ideas/month_end_treasury/results.json` @ `e36ee83` (added by this commit)
- supports: §3, §4
- status: current. One run, not independently re-derived. The shadow book `month_end_ief` starts 2026-11-10; its figures will be SIMULATED

### E-2026-11-10-02 · Release: the shadow-book runner is installed on the VM beside prod, as its own user following the branch shadow; its first run exited 0 and its timer is enabled
- kind: release
- era: ALPACA
- date: 2026-11-10
- figures:
  - installed 11:12:14 to 11:12:36 New York (22 seconds), between prod's 11:10 and 11:30 jobs [S]
  - the first run exited 0 on code `29a7006` and printed "month_end_ief: starts 2026-11-10; as-of 2026-11-09 is before it" [S]
  - the next timer firing is 2026-11-10 18:50 New York [S]
  - a first attempt at 10:12 stopped at its first step (`useradd: group shadow exists`) and created nothing [S]
- source: `docs/RUNBOOK.md` @ `29a7006` (section 8.10; its install note is added by this commit); `shadow/deploy/install_shadow_vm.sh` @ `29a7006`
- supports: §5
- status: current. Not a prod release: no tag, and prod's units, clone and state were not touched. The figures are from the install's own output, read once over ssh and not stored in the repository

### E-2026-11-10-03 · Result: the equity turn of the month is set aside as a sleeve, because SPY on every other session scores the same Sharpe
- kind: result
- era: ALPACA
- date: 2026-11-10
- figures:
  - window (last session of a month and the next three), long SPY: gross Sharpe 0.48, t 2.78, 1993-02-05 to 2026-11-09, 8,498 sessions of which 1,605 active; shift(2), no cost modelled [S]
  - halves 0.47 and 0.49 [S]
  - control, SPY on every other session: Sharpe 0.48, t 2.80 [S]
  - mean return per active day: 7.9bp in the window against 4.0bp outside it [S]
- source: `results/ideas/2026-11-10_turn_of_month_eq.md` @ `852a0ab` (added by this commit); `results/ideas/turn_of_month_eq/results.json` @ `852a0ab` (added by this commit)
- supports: §3
- status: current. One run, not independently re-derived

### E-2026-11-10-04 · Result: the Treasury auction concession is present but modest, a third of it is the month-end trade, and it is flat since 2023; explored, not promoted
- kind: result
- era: ALPACA
- date: 2026-11-10
- figures:
  - short IEF or TLT over the two sessions before a 7-, 10-, 20- or 30-year auction and long the two after: gross Sharpe 0.57, t 2.77, 2002-08-14 to 2026-07-22; 482 IEF and 291 TLT auctions; shift(2), no cost modelled [S]
  - halves 0.59 and 0.57; placebo dates ten sessions later 0.03 [S]
  - with the last three sessions of each month removed: Sharpe 0.39, t 1.89 [S]
  - 2023-01-03 to 2026-07-22: Sharpe −0.02 over 890 sessions; 2020–22: 1.40 [S]
  - announcement dates are not in the panel, so the four-session notice the rule needs is unverified [U]
- source: `results/ideas/2026-11-10_ust_auction_cycle.md` @ `852a0ab` (added by this commit); `results/ideas/ust_auction_cycle/results.json` @ `852a0ab` (added by this commit)
- supports: §3
- status: current. One run, not independently re-derived

### E-2026-11-10-05 · Result: short-term reversal within industry on the 1,500 largest US stocks earns a gross Sharpe of 0.96 over 2000 to 2025, mostly in high-volatility sessions, and clears Explore
- kind: result
- era: ALPACA
- date: 2026-11-10
- figures:
  - gross Sharpe 0.96, t 4.90, 6.84%/yr at 7.10% vol, 2000-01-12 to 2025-12-31, 6,532 sessions, about 1,430 names a day; shift(2), unit gross, no cost modelled [S]
  - early half 1.26; late half 0.67; 2016–19 −0.13 [S]
  - control, the signal 21 sessions stale: Sharpe 0.04; without the industry step: 0.79 [S]
  - sessions with market volatility above its median: Sharpe 1.35 (12.36%/yr); below: 0.32 (1.35%/yr) [S]
  - turnover 160.1 times a year; beta to the equal-weighted market 0.081 [S]
  - at $10M, the median position is 0.005% of the stock's 21-session average dollar volume and the 95th percentile 0.058% (2024–25) [S]
- source: `results/ideas/2026-11-10_st_reversal_wide.md` @ `852a0ab` (added by this commit); `results/ideas/st_reversal_wide/results.json` @ `852a0ab` (added by this commit)
- supports: §3
- status: current. The reproducer was run three times with identical output; not independently re-derived. Not on shadow: no live equity panel exists

### E-2026-11-10-06 · Incident: numexpr corrupted the first wide-universe run's weights on the laptop, differently on each run; it is now off for every Explore script
- kind: incident
- era: ALPACA
- date: 2026-11-10
- figures:
  - the frame was 6,539 sessions by 6,882 stocks, about 45 million cells, above numexpr's one-million-cell threshold [S]
  - one call of the same function returned 0 non-finite weights and the next returned some, on identical inputs [S]
- source: `scripts/research/explore.py` @ `852a0ab` (the option and its comment are added by this commit); `scripts/events/numexpr_fault.py` @ `852a0ab`
- supports: §5
- status: current. No result was recorded from a corrupted run: the harness refused the infinite weight. `CLAUDE.md` landmine 11 is added by this commit

### E-2026-11-10-07 · Result: across every closed-end fund on CRSP, a fund falls about 30bp against other funds in the three sessions after its ex-date; the pre-specified book has a gross Sharpe of 4.18 and is not a stale-price artifact
- kind: result
- era: ALPACA
- date: 2026-11-10
- figures:
  - short for three sessions after the ex-date, long the other eligible funds: gross Sharpe 4.18, t 21.25, 17.85%/yr at 4.27% vol, 2000-02-15 to 2025-12-29; 73,741 eligible ex-dates; shift(2); no cost and no borrow modelled [S]
  - halves 3.68 and 4.78; eras 4.19, 4.71, 5.53, 4.90, 4.80 [S]
  - event funds less the eligible universe: X+1 −15.5bp, X+2 −8.7bp, X+3 −6.2bp; X−3 to X−1 +5.8, +6.8, +9.0bp [S]
  - the ex-day price drop averages 90.8bp against a distribution of 83.8bp; no eligible ex-date had zero volume [S]
  - three-session drop by average daily dollar volume: −27.9bp at $0.5–2M, −32.1bp at $2–5M, −44.9bp above $5M [S]
  - variant, not pre-specified: long the three sessions before, short the three after: Sharpe 4.72 [S]
  - at $5M the median short is 1.9% of the fund's average daily volume and the 95th percentile 15.9% (2024–25) [S]
- source: `results/ideas/2026-11-10_cef_exdate_drift.md` @ `852a0ab` (added by this commit); `results/ideas/cef_exdate_drift/results.json` @ `852a0ab` (added by this commit)
- supports: §3, §4
- status: current. One run of the reproducer and one of the robustness checks; not independently re-derived. The by-liquidity and trading-volume checks were run in the session and their figures are in the card, not in a stored file

### E-2026-11-10-08 · Method: the two ex-date shadow books start on 91 funds, with declared ex-dates stored by the day they were first seen
- kind: method
- era: ALPACA
- date: 2026-11-10
- figures:
  - 91 funds in the universe, built from files already in the repository; 91 of 91 returned prices [S]
  - 76 of the 91 had a future ex-date listed in Alpaca's corporate-actions feed on 2026-11-10 [S]
  - on 2026-11-09, 82 funds were eligible and 6 were in their post-ex window; the pre-specified book would hold 76 long and 6 short [S]
- source: `results/ideas/2026-11-10_cef_exdate_drift.md` @ `852a0ab` (its "On shadow" section is added by this commit); `shadow/signals/cef_exdate.py` @ `852a0ab` (added by this commit); `shadow/fetch/exdates.py` @ `852a0ab` (added by this commit)
- supports: §4, §5
- status: current. The counts are from one live run of the fetchers on the laptop, not stored in the repository. Every figure these books produce will be SIMULATED

### E-2026-11-09-40 · Nightly report-only data QA and risk checks built on VM timers; thresholds derived on fit data with recall as measured
- kind: method
- era: ALPACA
- date: 2026-11-09
- figures:
  - budget 1 flag per book per week jointly, 0.2/wk per free-threshold check; fit 2005-01-01..2022-12-31 (Q6 from 2013), deployed names only, sealed names and 2023+ not read for any rate; sum of check rates core 0.683/wk, C4 0.653/wk [V]
  - Q2 z core 6.5 (0.192/wk), C4 10.0 (0.177/wk); recall on C4's 9 DG-L3 masks 9/9 (7 episodes); the core has no positive in its 13 names [V]
  - Q3 delta core 0 (0.110 new runs/wk), C4 1 (0.087/wk); recall not measurable and 0 by construction on the gate's one-row stale copies [V]
  - Q4 tolerance ln(1.15), 0.000/wk core, 0.004/wk C4; IGR's step of 2026-09-08 flagged (close x2.88, NAV x2.99); BTO, NXG, EMO 0/3 (no panel step), TYG not in C4's 74 [V]
  - Q5 (first night past the line) line core 22% (0.181/wk), C4 27% (0.189/wk); BME 2021-06-28 +75.6% flagged; the design's 50pp line runs 0.053/wk core, 0.004/wk C4 [V]
  - Q6 margin core 2.5% (0.200/wk), recall 13/22 thin-episode starts; C4 13% (0.196/wk), recall not measurable [V]
  - peak memory measured on the laptop's panels: data_qa 151 MB core, 220 MB C4; risk_daily 102 MB; units set MemoryMax=450M; not yet measured on the VM [V]
- source: `results/ops/DATA_QA_CALIBRATION_2026-11-08.md` @ `86a0c08`
- supports: §5
- status: built, PR open, not merged or installed; the ACT push needs the team lead's two vault secrets (docs/RUNBOOK.md 8.11); drawdown read marked for follow-up on PR #55

### E-2026-11-09-60 · CEF trial 55's three pre-activation fixes from the owner's release-check: late_market only, a plan the buying-power fit emptied is not sent, and the drift guard compares the K-line values
- kind: method
- era: ALPACA
- date: 2026-11-09
- figures:
  - "`thin_rule_for` refuses, at session start, any execution mode but `late_market`" [S]
  - "a reduced plan the buying-power fit scaled to nothing (`bp_scale` orders_in > 0, orders_out 0) is not sent" [S]
  - "A spec value may be the compose value rounded, at 3 decimals or more; any other difference fails the activation commit" [S]
- source: `docs/RUNNER.md` @ `5eb8bf5`; `quantt/session/run.py` @ `5eb8bf5`; `quantt/session/drawdown.py` @ `5eb8bf5`; `src/deploy/tests/test_thin_k3_run_provenance.py` @ `5eb8bf5`
- supports: §5
- status: current (the key is not set; it trades only from its activation commit)

### E-2026-11-10-51 · Method and ruling: an independent review of CEF trial 55's pre-activation fixes found the activation guard blind to the band, the gross ceiling and min_names; on the team lead's ruling all three findings are fixed before the merge
- kind: method
- era: ALPACA
- date: 2026-11-10
- figures:
  - none (a review and a fix: the guard now holds the spec's band_width, max_gross_stress and min_names to the compose run's recorded band, cap and min_names, beside m and floor; an empty plan beside a `bp_scale` record that run.py cannot write, or beside STARTED, reads UNMEASURED instead of sent; three stale passages of drawdown.py's rule are corrected. The team lead ruled on 2026-11-10: "Fix all three, then merge". Nothing here runs while no spec sets `below_min_names = "trade_eligible"`)
- source: `src/deploy/tests/test_thin_k3_run_provenance.py` @ `0c5d747` (fixed by this commit); `quantt/session/drawdown.py` @ `0c5d747` (fixed by this commit); `results/cef/prereg_thin_te4/compose.py` @ `0c5d747`
- supports: §5
- status: current

### E-2026-11-10-09 · Incident: the broker client and the probe followed HTTP redirects with the Alpaca key headers attached; both now refuse any redirect, with tests on requests' own redirect code
- kind: incident
- era: ALPACA
- date: 2026-11-10
- figures:
  - 3 calls in the run package carried the key headers and followed redirects: the client's GET, the client's order POST and the probe's GET; 2 research scripts borrowed the same sessions [S]
  - on an unprotected session, each of 301, 302, 303, 307 and 308 delivered both key headers to the second host, in a test on a recording transport with fake keys [S]
  - 22 of the new tests fail against the client and probe as they stood on main [S]
- source: `quantt/broker/alpaca.py` @ `89bf145` (`refuse_redirects` is added by this commit); `quantt/tests/test_alpaca_redirects.py` @ `89bf145` (added by this commit)
- supports: §5
- status: current. Found by another session's review of its report reader and passed on at the team lead's request; no evidence that a redirect was ever served. The fix is in the repository only: prod runs it after the team lead's next release

### E-2026-11-09-50 · Rulings: a daily VM report for both paper books, the P&L attribution and factor readout; C4's factors are equity, term, credit and preferred with equity as headline; report only, read through the broker key with read-only code
- kind: ruling
- era: ALPACA
- date: 2026-11-09
- figures:
  - none (rulings: the job covers the core and C4; C4's factor set is EQUITY=SPY (headline), TERM=IEF, CREDIT=HYG, PREFERRED=PFF with a by-family split; C4 uses the core's method, a lag rule declared in a commit before any C4 price is read; a review-line breach is reported and sends nothing; the account is read with the book's own key from the secret service, by code with no path to an order; the report shows the latest session and the total since the first trade)
- source: `scripts/ops/pnl_report.py` @ `6387362`; `scripts/cef/exposure_readout.py` @ `6387362`; `docs/RUNBOOK.md` @ `6387362`
- supports: §4, §5
- status: current

### E-2026-11-09-51 · Result: C4's declared lag rule, run on public prices one minute after it was committed, gives L = 2, so C4's factor betas sum lags 0 to 2
- kind: result
- era: ALPACA
- date: 2026-11-09
- figures:
  - lag counts of 288 pairs, lag 0 to 3: 254, 128, 83, 41; T = max lead count = 65 (at lead 13); first lag not above T: 3; so L = 2 [S]
  - names in the pair set 72 of 74 (NPFD 242 and RLTY 195 usable rows, under the 252 required) [S]
  - fit era 2010-01-05..2022-12-30, 3271 sessions, cut before any shift; nothing dated 2023 or later read [S]
- source: `results/cef/C4_LAG_RULE_RESULT_2026-11-09.txt` @ `e72e1b7`; rule declared in `scripts/cef/exposure_readout.py` @ `d37a86d`
- supports: §5
- status: current

### E-2026-11-10-50 · Method: the daily P&L report job is built and reviewed, not installed. Two reviews found 11 defects and all are fixed: C4's NAVs were read at the wrong symbol for 15 funds, and a redirect could have carried the read key to another host
- kind: method
- era: ALPACA
- date: 2026-11-10
- figures:
  - 15 of C4's 74 funds use a NAV symbol other than the core's X<ticker>X rule, and yfinance returned no rows at the X-rule symbol for any of the 15 [V]
- source: `scripts/cef/live_attribution.py` @ `c8bf828`; `scripts/ops/alpaca_read.py` @ `2bf1d4d`; `scripts/ops/pnl_report.py` @ `60dee01`
- supports: §4, §5
- status: built on branch reports-attribution, no PR yet (it opens after PR #65 merges); not installed; the reader has never read a live account

### E-2026-11-10-52 · Rulings on the daily report job: the review line carries each book's sizing multiplier, an unreconciled report fails its run, and a late price makes the factor block partial, not unmeasured
- kind: ruling
- era: ALPACA
- date: 2026-11-10
- figures:
  - none (rulings, put to the team lead on 2026-11-10 after the build's review: the factor review line is REVIEW_FRACTION x vol_target_annual x sizing_multiplier, from each book's own spec, because the account holds the multiplier times the unit book (this changes the core's readout as well); a report whose rebuild does not reconcile to Alpaca's official equity exits 5 after writing its files; a held name with no same-day price is left out and named, and the factor block reads PARTIAL with the missing share of gross; NAV timing at 20:30 is accepted as built; C4 keeps L = 2; the runner client's redirect finding goes to the code's owner (PR #79))
- source: `scripts/cef/exposure_readout.py` @ `774fd52`; `scripts/ops/pnl_report.py` @ `5c42757`; `scripts/ops/pnl_report.py` @ `2cd374f`; `scripts/ops/risk_daily.py` @ `2cd374f`
- supports: §4, §5
- status: current

### E-2026-11-11-50 · Ruling and method: both specs' sizing-multiplier notes now name the report job's factor readout among their readers; no value and no spec id changed, and C4's three sha-pinned artifacts were regenerated and match except their spec sha256 and run-time fields
- kind: method
- era: ALPACA
- date: 2026-11-11
- figures:
  - none (a note edit: one line in each spec, `json.load` equal on every other key; spec ids stay cef_discount.v9.20261102 and c4_families.v5.20261103. The team lead ruled on 2026-11-11: edit both notes, regenerate C4's pinned artifacts, do not bump the id. Regenerated on the same panels, cut at 2022-12-30: the C4 paper benchmark and trial 54's activation measures differ from the committed ones only in the spec sha256 and run-time fields; the H11 series is byte-identical. Two tests that hash spec content were re-pinned: the trial-54 frozen-block hash, and the core's combine no-op input hash, which had turned a pass into a skip)
- source: `ops/specs/cef_discount.frozen.json` @ `73c213e`; `ops/specs/c4_families.frozen.json` @ `73c213e`; `results/cef/c4/c4_paper_benchmark_2026-11-03.json` @ `73c213e`; `results/cef/prereg_c4_level/activation_measures_2026-11-03.json` @ `73c213e`
- supports: §1, §5
- status: current

### E-2026-11-11-51 · Method: an independent review of the report job's later changes found four low-severity defects, all fixed: a book flat at the close now reads FLAT, and a name left out only on an earlier date no longer holds the block at WATCH
- kind: method
- era: ALPACA
- date: 2026-11-11
- figures:
  - none (a review and its fixes. On a day the book holds nothing at the as-of close the factor block reads FLAT, with no exposure and no flag, and risk_daily reads INFO; before, it showed the previous close's exposure with status OK, and a flat close with an earlier exclusion raised. PARTIAL and WATCH now follow the as-of close only, and earlier exclusions become a named history note. The installer's --reports help names the pnl units and their key services. The team lead ruled on 2026-11-11: fix all four, then merge, and keep the PARTIAL flags as ruled, with no cap on the missing share)
- source: `scripts/ops/pnl_report.py` @ `9839a14`; `scripts/ops/risk_daily.py` @ `9839a14`; `quantt/deploy/install_vm.py` @ `bbd5c09`; `scripts/cef/exposure_readout.py` @ `d7a0f85`
- supports: §4, §5
- status: current

### E-2026-11-12-50 · Ruling and method: the report job never reads a book as flat from an unreconciled rebuild, and the risk check confirms every flat reading against the account's own positions record
- kind: method
- era: ALPACA
- date: 2026-11-12
- figures:
  - none (a second review of the report job's fixes, and the team lead's ruling of 2026-11-11 to add both checks. A flat reading needs a reconciled rebuild, or the factor block is UNMEASURED. risk_daily compares each flat reading with that session's account.json, which the collector writes after the close: an empty record gives INFO, any position gives WATCH, and a missing or other-session record gives UNMEASURED. On a flat night a bug or a lookahead failure in the history read now ends as on a held night, instead of reading calm. Every cumulative factor P&L line names the sessions it covers. The session on which the whole book goes flat is not yet in the factor P&L; the team lead chose a follow-up PR for it. No figure changed)
- source: `scripts/ops/pnl_report.py` @ `bf98dec`; `scripts/ops/risk_daily.py` @ `bf98dec`; `scripts/ops/pnl_report.py` @ `d498c4f`; `scripts/ops/pnl_report.py` @ `d2f3e19`
- supports: §4, §5
- status: current

### E-2026-11-12-51 · Ruling: the report job merges after its third review; three older gaps it found go, with the flat-session factor P&L gap, into one reviewed follow-up before any install
- kind: ruling
- era: ALPACA
- date: 2026-11-12
- figures:
  - none (a ruling. The third review found the new commits correct with no figure moved, and three gaps older than them: a held night's factor exposure is never checked against the account's positions; a late end-of-day point can show the previous close's reading as INFO without marking it stale; a split in any fund ever held leaves the factor block UNMEASURED every night after. The team lead ruled on 2026-11-12: merge now, and fix these three and the flat-session factor P&L gap in one reviewed follow-up PR before any install. Also on 2026-11-12: a flat night with yfinance down stays UNMEASURED, like a held night)
- source: `scripts/ops/pnl_report.py` @ `d2f3e19`; `scripts/ops/risk_daily.py` @ `bf98dec`; `scripts/cef/exposure_readout.py` @ `d2f3e19`
- supports: §5
- status: current

### E-2026-11-11-01 · Result: earnings drift on the 1,500 largest US stocks is present but small; the pre-specified book has a gross Sharpe of 0.21 and is not promoted
- kind: result
- era: ALPACA
- date: 2026-11-11
- figures:
  - long the top tenth and short the bottom tenth by IBES surprise score for 40 sessions after a quarterly release: gross Sharpe 0.21, t 1.09, 1.20%/yr at 5.59% vol, 2000-03-03 to 2025-12-31; 255,475 releases; shift(2); no cost modelled [S]
  - halves 0.12 and 0.34; eras 1.12, −0.14, 0.20, 0.67, 0.50 [S]
  - controls: the surprise 126 sessions late −0.16; ranks 1 to 500 only 0.33; ranks 501 to 1,500 only 0.13 [S]
  - turnover 39 times a year; beta to the equal-weighted market 0.01 [S]
  - event time, top less bottom tenth, market-adjusted, t+2 to t+41: 56.8bp sorted on the surprise score, 105.7bp sorted on the two-session announcement move; 141,703 releases [S]
  - variant, not pre-specified, sorted on the announcement move: Sharpe 0.73 held 40 sessions (0.88 to 2012, 0.55 from 2013), 0.52 held 20 sessions [S]
- source: `results/ideas/2026-11-11_pead_wide.md` @ `8c8bfe5`; `results/ideas/pead_wide/results.json` @ `8c8bfe5`
- supports: §3, §4
- status: current. One run of each reproducer; not independently re-derived. The event-time table and the variant are printed by `results/ideas/pead_wide/event_time.py` and stored only in the card

### E-2026-11-11-02 · Ruling: the desk is event-driven and special situations as well as systematic, in any asset class, and every idea hunt looks for niche verticals there
- kind: ruling
- era: ALPACA
- date: 2026-11-11
- figures:
  - none (a ruling)
- source: `docs/SYSTEM.md` @ `e02abb1` (§5, the 2026-11-11 block); `docs/MISSION.md` @ `e02abb1` (§5, the block dated 2026-11-11); `.claude/skills/hunt/SKILL.md` @ `e02abb1`
- supports: §2, §5
- status: current. The team lead's instruction in the session of 2026-11-11. It adds to the 2026-11-09 ruling (E-2026-11-09-01) and changes nothing else in it. The seed list in `docs/MISSION.md` is hypotheses; none is tested

### E-2026-11-11-03 · Result: the fall after the ex-date is also in partnership and trust units (gross Sharpe 3.03), weakly in REITs, and absent in ETFs and large common stocks
- kind: result
- era: ALPACA
- date: 2026-11-11
- figures:
  - units (CRSP share type UG), the closed-end fund test unchanged: gross Sharpe 3.03, t 15.40, 32.26%/yr at 10.65% vol, 2000-02-15 to 2025-12-29; 9,044 eligible ex-dates on 242 units; shift(2); no cost and no borrow modelled [S]
  - units: halves 3.34 and 2.77; eras 3.16, 3.39, 2.77, 3.08, 2.10; placebo events ten sessions later −0.02 [S]
  - units, event names less the group: X−3..X−1 +44.2bp, X+1..X+3 −85.2bp [S]
  - units, dating check: on the ex-date the price falls 203.5bp against a mean distribution of 176.8bp, slope 1.18 on the distribution's size; the X+1 slope is 0.14; one eligible ex-date had no volume [S]
  - units, X+1..X+3 by average daily dollar volume: −106.7bp at $0.5–2M, −81.7bp at $2–10M, −61.4bp above $10M [S]
  - REITs: Sharpe 0.91, t 4.62, halves 1.00 and 0.81, −0.45 in 2023–25; X+1..X+3 −13.2bp on 13,050 ex-dates [S]
  - ETFs: Sharpe 0.28 with the placebo at 0.34; the 1,500 largest common stocks: −0.02 [S]
- source: `results/ideas/2026-11-11_exdate_other_wrappers.md` @ `fc6bc2b`; `results/ideas/exdate_other_wrappers/results.json` @ `fc6bc2b`
- supports: §3, §4
- status: current. One run of the reproducer; not independently re-derived. The dating and liquidity checks were run in the session and their figures are in the card, not in a stored file. Borrow, capacity and the live list of units are unmeasured

### E-2026-11-11-04 · Method: two ex-date shadow books start on 48 partnership and trust units, on a list rebuilt from the public exchange directory
- kind: method
- era: ALPACA
- date: 2026-11-11
- figures:
  - 294 listed names pass the name rule; 294 are tradable at Alpaca; 48 paid a cash distribution in the 400 days to 2026-11-11 [S]
  - 34 of the 48 were shortable at Alpaca on 2026-11-11, all 34 easy to borrow [S]
  - the list holds 46 of the 51 CRSP units with an ex-date since 2025-06 (local check against the R2 mirror) [S]
  - first fetch: prices for 48 of 48 symbols; 30 ex-dates, 11 units with a future ex-date listed [S]
  - both books' decisions for 2026-11-11 were flat (no ex-date on 11-10 to 11-12), from a local run too late to be scored [S]
- source: `shadow/universes/build_units_v1.py` @ `90960fd`; `shadow/universes/units_v1.csv` @ `90960fd`; `shadow/books/units_exdate_after.json` @ `90960fd`; `shadow/books/units_exdate_before_after.json` @ `90960fd`; `docs/REFERENCES.md` @ `90960fd` (§12sd)
- supports: §4, §5
- status: current. Shadow books under the 2026-11-09 one-time approval (E-2026-11-09-03); SIMULATED, $1M each, no borrow modelled. The VM's first run of them is unconfirmed: ssh from the laptop timed out on 2026-11-11

### E-2026-11-12-01 · Result: clustered insider buying has no effect in the 2,000 largest US stocks (gross Sharpe 0.05) and is set aside there
- kind: result
- era: ALPACA
- date: 2026-11-12
- figures:
  - long each cluster stock for 21 sessions against the other eligible stocks: gross Sharpe 0.05, t 0.21, 0.30%/yr at 6.48% vol, 2006-02-08 to 2025-12-31; shift(2); no cost modelled [S]
  - halves 0.23 and −0.14; eras 0.30, 0.15, 0.95, −0.69, −0.41 [S]
  - controls: the events 126 sessions late −0.33; the worst tenth by one-month return with no insider data 0.16; correlation of the book with that control 0.25; held 60 sessions −0.11 [S]
  - 14,421 clean clusters (the 2026-10-19 census rule); 3,725 (26%) are in the panel on their date; about 14 cluster stocks held a day; 18% of sessions flat [S]
- source: `results/ideas/2026-11-12_insider_clusters.md` @ `f103660`; `results/ideas/insider_clusters/results.json` @ `f103660`
- supports: §3, §4
- status: current. One run of the reproducer; not independently re-derived. The cluster file was built on 2026-10-19 by `scripts/events/ssx/ssx_ins_insider_census.py` and was not rebuilt for this test. Stocks below the 2,000th by market value are untested

### E-2026-11-12-02 · Result: ex-dates were declared in advance for 99% of closed-end fund and unit distributions, so the ex-date tests' timing assumption holds
- kind: result
- era: ALPACA
- date: 2026-11-12
- figures:
  - closed-end funds: 143,200 ordinary distributions since 2000; 99.2% declared at least one day before the ex-date, 99.0% at least three; median gap 11 days; 0.7% with no declaration date [S]
  - units: 12,987 ordinary distributions; 98.9% at least one day before, 98.2% at least three; median gap 9 days; 0.9% with no declaration date [S]
- source: `results/ideas/2026-11-10_cef_exdate_drift.md` @ `70a35dc`; `results/ideas/2026-11-11_exdate_other_wrappers.md` @ `70a35dc`
- supports: §3
- status: current. One query of CRSP `stkdistributions` on the R2 mirror in the session; the query is not stored as a script. Gaps are calendar days. Closes the [U] on declaration dates in E-2026-11-10-07 for the short-after book; the week's notice the long-before leg needs is covered by the median, and its tail is unmeasured

### E-2026-11-12-03 · Result: agreed all-cash US mergers earn a modest premium (raw Sharpe 0.71, 0.48 over bills, on a universe corrected after the first run); the event-time spread of the October design is absent
- kind: result
- era: ALPACA
- date: 2026-11-12
- figures:
  - pre-specified universe, one-step all-cash 'Merger' deals, long every live target: raw Sharpe 0.50, t 2.53, 4.48%/yr at 9.02% vol, 2000-02-01 to 2025-12-31; 2.62%/yr and Sharpe 0.29 over 3-month bills; maximum drawdown −42.5% on summed daily returns; 1,529 deals held; shift(2); no cost modelled [S]
  - friendly deals only, chosen after the first run: raw Sharpe 0.71, t 3.63, halves 0.71 and 0.73; 3.73%/yr and Sharpe 0.48 over bills; maximum drawdown −23.4%; beta to SPY 0.17; alpha 2.38%/yr, Newey-West t 2.19; 1,366 deals held, 18 live a day at the median [S]
  - of 1,529 eligible deals 155 are marked unsolicited or hostile and 148 of those were withdrawn; friendly deals were withdrawn 8.3% of the time [S]
  - event-time (hazard) book: raw Sharpe 0.04 as pre-specified and 0.06 on friendly deals; the tender-offer control was invested on 1% of sessions and is unmeasured [S]
  - announcement dating: targets rise 23.7% on SDC's date and 6.9% on the next session, then 0.03%; the first return earned is three sessions after SDC's date [S]
  - CRSP's new-format delisting row equals the legacy delisting return within 1bp on 98.3% of 2,137 merger delistings [S]
  - cross-check on the desk's EDGAR list, 2001-01-31 to 2010-03-31, entered after the first proxy: raw Sharpe 0.36 at 19.6% vol, beta 0.69; the SDC friendly book over the same sessions 0.61; daily correlation 0.48; 1,595 later deals left out for want of a first-proxy date [S]
  - independent review: friendly premium re-derived at 0.713 raw and 0.478 over bills; weights rebuilt on data cut at 14 dates matched exactly; one more session of delay gives 0.717 [S]
- source: `results/ideas/2026-11-12_merger_arb.md` @ `3c1d68f`; `results/ideas/merger_arb/results.json` @ `3c1d68f`; `results/ideas/merger_arb/crosscheck_edgar.json` @ `3c1d68f`; `docs/REFERENCES.md` @ `3c1d68f` (§12ma)
- supports: §3, §4
- status: current. The premium figures were re-derived by a separate reviewer agent in the session; the reviewer's own script is not stored. The friendly filter is not pre-specified. The staging selects on SDC's final status (830 rumour, seeking-buyer and intent rows left out), whose effect is unmeasured. Stock deals, costs and borrow are untested. Not on shadow: there is no live deal list with break dates yet

### E-2026-11-12-04 · Result: a newly spun-off company falls about 3% against small companies in its first week and other new listings do not; a short over its sessions 3 to 5 has a gross Sharpe of 0.96, not pre-specified
- kind: result
- era: ALPACA
- date: 2026-11-12
- figures:
  - 387 new spin-offs (CRSP code SECSO, the distributed company a US common share first listed within 10 days of the ex-date), ex-dates 2000 to 2025; 26 already-listed children left out [S]
  - return less IWM over life sessions 2–5: −3.2% (t −4.6 by start month); 6–20 +1.8% (t 1.9); 21–63 +1.5% (t 1.7); the control, 5,725 other new listings: −0.3% over sessions 2–5 [S]
  - pre-specified book, long from life session 21 to 252 against IWM: gross Sharpe 0.49, t 2.46, halves 0.67 and 0.28; eras 0.46, 0.50, −0.12, −0.34, 1.96; the parents' book −0.01 and the other new listings' −0.33 [S]
  - not pre-specified, windows read from the session profile: short over sessions 3–5 at 10% of the book a name against IWM: gross Sharpe 0.96, t 4.84, 3.18%/yr at 3.31% vol, halves 1.07 and 0.88, eras 1.31, 0.35, 1.25, 1.58, 0.50; 336 names; invested on 12% of sessions [S]
  - not pre-specified: long over sessions 7–63: 0.47, t 2.36; both together 0.80, t 4.03 [S]
  - independent review: on the 336 traded names the sessions 3–5 fall is 2.45% (t −4.5), 2.31% winsorised; the ten best names are 41% of the first-week book's P&L and without them the Sharpe is 0.64; using only companies whose first row is the ex-date gives 0.97; a window of sessions 6–8 gives 0.14; beta to IWM 0.006 [S]
- source: `results/ideas/2026-11-12_spinoffs.md` @ `549de39`; `results/ideas/spinoffs/results.json` @ `549de39`
- supports: §3, §4
- status: current. Figures re-derived by a separate reviewer agent in the session; the reviewer's scripts and the liquidity and era splits quoted in the card are not stored in the repository. The event books' windows were chosen after seeing the profile. No cost or borrow is modelled, and whether a share can be borrowed on its second day of trading is unknown. Not on shadow: no live spin-off reader yet

### E-2026-11-14-01 · Method: a spin-off first-week shadow book starts on a first-seen reader of Alpaca's feed; the nightly marks step now follows changing names; four units' closing prints were on the Texas Stock Exchange
- kind: method
- era: ALPACA
- date: 2026-11-14
- figures:
  - Alpaca's feed: 215 spin-off rows with process dates 2023-01-01 to 2026-11-14, none later; process date equals the ex-date at the median and is 10 days later at the 75th percentile [S]
  - of 6 rows with process dates in the 30 days to 2026-11-14: 3 contingent value rights, 1 already listed share, 1 back-filled, 1 new common share [S]
  - replay on that one share (MSGR, first regular-way session 2026-10-27, $69.6M traded): the rule holds it on 10-27, 10-28 and 10-29; over sessions 3 to 5 the trade would have lost about 1.7% of the book (Yahoo closes; a replay, not a record) [S]
  - ET, SUN, SUNC and USAC: no closing print under NYSE on any of 6 sessions (2026-11-06 to 11-13); a print under the Texas Stock Exchange equal to Yahoo's close on 2026-11-13 (19.40, 65.23, 66.00, 25.14) [S]
  - a full nightly cycle on the laptop against the real sources, twice: six books loaded, five decided for 2026-11-13, 109 symbols marked, the four units' gaps filled on the second run after the mapping [S]
- source: `shadow/signals/spinoff.py` @ `fcfccd3`; `shadow/fetch/spinoffs.py` @ `fcfccd3`; `shadow/books/spinoff_first_week.json` @ `fcfccd3`; `shadow/nightly.py` @ `fcfccd3`; `shadow/sources.py` @ `fcfccd3`; `docs/REFERENCES.md` @ `fcfccd3` (§12so)
- supports: §4, §5
- status: current. A shadow book under the 2026-11-09 one-time approval (E-2026-11-09-03); SIMULATED, $1M, no borrow modelled. The probe of the feed and the print-by-exchange check were run in the session and are not stored as scripts. The VM has been unreachable from the laptop since 2026-11-10, so no shadow run there has been read and the units books' sessions from 2026-11-11 until this commit reaches the VM are expected to be UNMEASURED

### E-2026-11-14-02 · Method: Alpaca stamps a half day's end-of-day point at 17:00 New York, and the client's fixed 20:00 rule would have stopped the official P&L from 2026-11-27; the rule is now the session's close plus four hours
- kind: method
- era: ALPACA
- date: 2026-11-14
- figures:
  - 754 daily points read on the cef paper account (`period=3A`, last 2026-11-13): 747 sessions with a 16:00 calendar close, all stamped 20:00:00 New York; 7 sessions with a 13:00 close, all stamped 17:00:00 [V]
  - the 7 half days: 2023-11-24, 2024-07-03, 2024-11-29, 2024-12-24, 2025-07-03, 2025-11-28, 2025-12-24; the first five are before funding (equity 0), the last two carry equity [V]
  - with the new rule the client reads 2023-11-13 to 2026-11-13 on the live endpoint: 292 funded points, 2025-09-18 to 2026-11-13, two of them at 17:00 [V]
  - eight of the new and changed tests fail on `8eb9ce1`, the old rule; the half-day stamp was found by a peer session's read-only GET on 2026-11-14 and re-measured here [V]
  - none for the effect on 2026-11-27 (from the code, not run: every point is checked before the window is applied, so the collector's EOD step would raise on each run once the half-day point is served, and verify would show the official P&L as PENDING)
- source: `quantt/broker/alpaca.py` @ `6814c2e`; `quantt/tests/test_alpaca_client.py` @ `6814c2e`; `docs/REFERENCES.md` @ `6814c2e`
- supports: §5
- status: current (an independent review found no material defect; its one low finding, a calendar date served twice, now raises. Not measured: whether a half day's point is final at 17:00, so the 2026-11-27 evening figure should be compared with the next day's re-read. Not released: prod runs the old rule until the team lead installs a release with this change; the report job's reader `scripts/ops/alpaca_read.py` still has the 20:00 rule and is the peer's follow-up PR)

### E-2026-11-14-50 · Result: Alpaca stamps a half day's end-of-day point four hours after its 13:00 close, at 17:00 New York, and the core paper account holds no row of any of the nine corporate-action activity types paper accepts
- kind: result
- era: ALPACA
- date: 2026-11-14
- figures:
  - cef paper, `period=3A`, 754 points: all 747 sessions with a 16:00 calendar close stamped 20:00:00 New York; all 7 with a 13:00 close stamped 17:00:00 (2023-11-24, 2024-07-03, 2024-11-29, 2024-12-24, 2025-07-03, 2025-11-28, 2025-12-24; the last two funded) [V]
  - cef paper account activities, read 2026-11-14: each of the nine types SPLIT, CIL, MA, NC, SC, SPIN, REO, REORG and JNLS returned 0 rows; SSP and SSO answered HTTP 422 [S]
- source: `scripts/ops/alpaca_read.py` @ `fa84045` (the half-day stamps); `scripts/ops/alpaca_read.py` @ `8dfe3eb` (the activity types)
- supports: §4, §5
- status: current

### E-2026-11-14-51 · Rulings: splits leave a fund out of the factor block, named; corporate actions are narrowed and handled from the account's own records; the half-day stamp is fixed in the runner's client by its owner and in the report's reader here
- kind: ruling
- era: ALPACA
- date: 2026-11-14
- figures:
  - none (rulings, 2026-11-14: a fund that split is left out and named on the dates the split can touch, with the PARTIAL rules (option A); the attribution's corporate-action refusal is narrowed to a fund held into an event that changes the holder's share count, never an acquirer, with the rebuild from the account's own activity rows, never the market feed, and an unprocessed paper split shown on its own labelled phantom line beside the official P&L; an unreconciled held night keeps its factor figures, labelled UNRECONCILED; the runner owner fixes AlpacaClient's half-day stamp rule in its own PR before 2026-11-27, and the report's reader copies its rule exactly; the report's follow-up PR is reviewed and merged before any install)
- source: `scripts/cef/live_attribution.py` @ `8dfe3eb`; `scripts/cef/exposure_readout.py` @ `5984cd2`; `scripts/ops/alpaca_read.py` @ `fa84045`
- supports: §4, §5
- status: superseded in part by E-2026-11-15-53 (2026-11-15): the rebuild from the account's own activity rows was not kept; any such row now stops the report, named

### E-2026-11-14-52 · Method: the report job's follow-up is built: account cross-checks on every factor reading, no stale reading shown as current, the flat-entry session counted in factor P&L, splits scoped, half-day stamps read, corporate actions narrowed and handled
- kind: method
- era: ALPACA
- date: 2026-11-14
- figures:
  - none (six fixes from the third review of PR #82 and the corporate-action investigation, each with tests that fail on the code before it. No attribution figure moved in any earlier scenario; the factor P&L changed only by the added flat-entry term; one scenario that refused before now attributes, because its fund was flat into the split. Research mode's readout output is byte-identical to before except the factor P&L rows the flat-entry fix adds on sessions where the book goes flat)
- source: `scripts/ops/pnl_report.py` @ `92c90f7`; `scripts/ops/risk_daily.py` @ `459fc73`; `scripts/cef/exposure_readout.py` @ `3743ad9`; `scripts/cef/exposure_readout.py` @ `5984cd2`; `scripts/ops/alpaca_read.py` @ `fa84045`; `scripts/cef/live_attribution.py` @ `8dfe3eb`
- supports: §4, §5
- status: built on branch reports-followup, under review; not installed; superseded in part by E-2026-11-15-53 (2026-11-15): corporate actions are narrowed, and an account corporate-action row stops the report rather than being handled

### E-2026-11-15-01 · Incident: the VM's shadow runner was read for the first time since 2026-11-10; every run since the 2026-11-12 evening ended non-zero because four units had no closing print, as expected, and one run stopped on an exchange name the map did not have
- kind: incident
- era: ALPACA
- date: 2026-11-15
- figures:
  - 6 runs from 2026-11-12 18:50 to 2026-11-14 07:20 ET, all on code `508bf6c`: five ended with exit 3 and one (2026-11-13 07:20) with exit 1 [V]
  - the five books decided for 2026-11-12 and 2026-11-13 and were marked for both sessions; the marks step reported 12 (session, symbol) pairs with no primary print after 2026-11-12 and 16 after 2026-11-13 [V]
  - the exit-1 run stopped with UnmappedExchange: Alpaca's asset record for ET named the exchange 'TXSE'; the same record read 'NYSE' on 2026-11-14 and 2026-11-15 from the laptop [V]
  - 12 active assets carry exchange 'TXSE' on 2026-11-15; the 11 with a Yahoo price each have a closing print under the Texas Stock Exchange code on 2026-11-13 equal to Yahoo's close to the cent, and none under the NYSE or Nasdaq codes [V]
  - none for the fix on the VM (the mapping commits `fcfccd3` and this one were pushed after the last run; the next run is 2026-11-16 18:50 ET)
- source: `shadow/sources.py` @ `db57aa7`; `shadow/tests/test_sources_exchange.py` @ `db57aa7`
- supports: §5
- status: current. The log files were printed by the team lead's own command (the agent's read as the service user was refused by the permission check); the state directory, scoreboard and marks_gaps.csv on the VM have not been read. The venue check was run in the session and is not stored as a script

### E-2026-11-15-02 · Result: a common stock gains between a special dividend's announcement and its ex-date; gross Sharpe 1.10 against IWM, 0.62 in names trading $5M a day; a shadow book is built and not yet running
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - 3,601 special cash dividends on common shares with ex-dates 2000-06-01 to 2025-12-31 (CRSP on R2, prices to 2025-12-31); 64 have no declaration date and are left out [V]
  - pre-specified WAIT book (long from the session after the news is public to the close before the ex-date, 10% a name against IWM, yield 1% or more): 1,654 events, gross Sharpe 1.10 (t 5.57), halves 0.78 / 1.36, eras 0.67, 1.09, 1.76, 2.23, 0.64; the same book on ordinary dividends 0.59 [V]
  - pre-specified AFTER book (short X+1 to X+3): 0.63 (t 3.21), halves 0.64 / 0.64, −0.20 in 2023–25, placebo ten sessions later 0.06. EXDAY book: 0.56, with the ordinary-dividend control at 1.11 [V]
  - checks not pre-specified: WAIT alpha 6.9% a year (t 5.85) with betas to IWM and SPY of −0.07 and 0.05; 0.98 without its ten best events; 0.62 (t 3.15) on dollar volume of $5M or more and 0.49 (t 2.46) on $20M or more; the same names over windows moved 60, 40 and 20 sessions earlier 0.66, 0.68, 1.02, and later −0.14, 0.03, −0.14 [V]
  - Alpaca's feed on 2026-11-15: 67 special cash-dividend rows not marked foreign, 47 with a future ex-date; 22 companies pass the shadow book's type filter with an ex-date three or more sessions ahead, 12 of them yielding 1% or more [V]
  - none for the feed's lag after an announcement (every row was already listed when the reader first ran)
- source: `results/ideas/special_dividends/explore.py` @ `77d6119`; `results/ideas/special_dividends/checks.py` @ `77d6119`; `scripts/research/stage_crsp_special_divs.py` @ `77d6119`; `shadow/signals/specdiv.py` @ `77d6119`; `shadow/fetch/specdivs.py` @ `77d6119`; `docs/REFERENCES.md` @ `77d6119` (§12sv)
- supports: §4, §5
- status: current. Gross, no costs, no borrow, dividend tax not modelled. The shadow book is SIMULATED, $1M, under the 2026-11-09 one-time approval (E-2026-11-09-03), and is a local commit: it does not run until the commit reaches the remote `shadow` branch. An independent review on 2026-11-15 re-derived WAIT at 1.10 (t 5.57) from its own code and found no lookahead; it corrected two readings in the card: the windows moved earlier are 0.63, 0.57 and 0.69 once announcement sessions are removed (not 0.66, 0.68, 1.02), and a start 1 to 3 sessions late gives 0.89 to 0.98. Those figures are the reviewer's and are not stored as a script. AFTER and EXDAY were not re-derived

### E-2026-11-15-03 · Result: the fall at an IPO lock-up expiry is in the data but the textbook three-session short has earned nothing since 2016; the selling now comes in the four sessions before the date
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - 2,823 US IPOs with a lock-up date on SDC matched to a CRSP common share, IPO dates 2000-01-24 to 2025-12-16, prices to 2025-12-31; 1,670 eligible events [V]
  - pre-specified book (short L−1 to L+1 against IWM, 10% a name): gross Sharpe 0.56 (t 2.82); halves 1.29 / 0.19; eras 1.04, 0.85, −0.04, 0.37, −0.21; the window moved 30 sessions earlier −0.00 and later −0.16 [V]
  - event-time profile against IWM: −32bp on L−4, −24bp on L−2, −32bp on L−1, −37bp on L, +3bp on L+1 [V]
  - per event, not pre-specified: L−1 to L+1 −1.40% in 2000–08, −0.61% in 2009–15, then +0.09%, −0.18%, +0.33%; L−4 to L −1.21% over the whole sample (t −4.4 by month) and −1.59%, −0.94%, −1.98%, −0.43%, −1.31% by era [V]
- source: `results/ideas/ipo_lockups/explore.py` @ `b94c91f`; `results/ideas/ipo_lockups/checks.py` @ `b94c91f`; `scripts/research/stage_sdc_ipo_lockups.py` @ `b94c91f`; `docs/REFERENCES.md` @ `b94c91f` (§12lk)
- supports: §4
- status: current. Gross, no costs, no borrow; a revival of K5, dropped 2026-10-19 on a borrow count. Not promoted: the earlier window was chosen on this sample. Not independently reviewed

### E-2026-11-15-04 · Result: a reverse-split share keeps falling for a month (gross short Sharpe 1.02), and Alpaca lends 4 of the 32 names the book would hold today
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - 3,375 reverse splits on common shares on CRSP, ex-dates 2000-01-03 to 2025-12-31, prices to 2025-12-31; 1,260 eligible at the close of the ex-date (price ≥ $2, 21-session dollar volume ≥ $500,000) [V]
  - pre-specified book (short X+2 to X+21 against IWM, 10% a name): gross Sharpe 1.02 (t 5.18), 25.1% a year on 24.5% volatility, worst drawdown −49%; halves 0.76 / 1.28; eras 1.08, 0.97, 1.81, 0.51, 1.55; 0.95 (t 4.79) on names trading $5M a day [V]
  - controls: forward splits on the same rule 0.47; the same reverse splits 60 sessions later 0.45 and earlier 0.63; the book less the mean of those two 0.50 (t 2.53, not pre-specified) [V]
  - per event over 20 sessions, short less IWM: mean +9.1%, median +7.8%, 64% positive; worst −714% of the position; Sharpe 0.80 without the ten best events [V]
  - the pre-specified wait book (declaration to ex-date) had 114 tradable events: 0.27 (t 1.37); CRSP's declaration date is a median of one session before the ex-date [V]
  - borrow at Alpaca read 2026-11-15: of 32 feed rows with an ex-date in the last 30 days passing the same floors, 4 shortable (one a closed-end fund); of the 8 trading $5M a day, 0; true on that date only [V]
- source: `results/ideas/reverse_splits/explore.py` @ `21fceb3`; `results/ideas/reverse_splits/checks.py` @ `21fceb3`; `results/ideas/reverse_splits/borrow_now.py` @ `21fceb3`; `scripts/research/stage_crsp_reverse_splits.py` @ `21fceb3`; `docs/REFERENCES.md` @ `21fceb3` (§12rs)
- supports: §4
- status: current. Gross, no costs, no borrow fee. A revival of G1, closed 2026-10-15 on a borrow count with no return read; set aside again as a short at Alpaca, now with the return known and the borrow read on the names held. No shadow book built. Not independently reviewed

### E-2026-11-15-05 · Result: the recovery after a follow-on share offering was about 0.7% in five sessions before 2013 and has faded; the later short shows nothing
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - 13,491 US public follow-ons on SDC matched to a CRSP common share, issue dates 2000-01-05 to 2025-12-31, prices to 2025-12-31; 10,409 eligible at the close of the session after the issue date [V]
  - pre-specified long (D+3 to D+7 against IWM, 10% a name): gross Sharpe 0.71 (t 3.57); halves 1.56 / 0.26; eras 1.34, 1.30, 0.17, 0.10, 0.15; the window 30 sessions later 0.04; 0.15 on names trading $5M a day [V]
  - pre-specified short (D+8 to D+47): 0.07 (t 0.34); negative in four of five eras [V]
  - named cut: launched before the issue date 1.00 (t 5.1), on it −0.30 (t −1.5) [V]
  - not pre-specified: the launched-before book by era 2.09, 1.56, 1.02, 0.46, 1.00, with the median event at +0.69% in 2000–07 and 0.00% and +0.03% in 2018–22 and 2023–25; events launched one session before pricing 0.67 (t 3.37), positive in all five eras [V]
- source: `results/ideas/follow_ons/explore.py` @ `c24c1fc`; `results/ideas/follow_ons/checks.py` @ `c24c1fc`; `scripts/research/stage_sdc_follow_ons.py` @ `c24c1fc`; `docs/REFERENCES.md` @ `c24c1fc` (§12fo)
- supports: §4
- status: current. Gross, no costs. The first return read on catalogue card K6. Not promoted; no shadow book. Not independently reviewed

### E-2026-11-15-06 · Correction to E-2026-11-15-02: the special-dividend wait book is 0.89 to 0.98 once a dating exposure is removed, and about zero in 2023–25
- kind: correction
- era: ALPACA
- date: 2026-11-15
- figures:
  - 60 sampled events from 2019 on, checked against 8-K acceptance times on EDGAR: first 8-K naming the dividend by the close of CRSP's declaration date 7, by the close of the next session 15, later 12, none found 26; none before CRSP's date [V]
  - of the 12 later ones, 10 were public before the book's fill and 2 were not (THG, NREF): 2 of 34 checked events [V]
  - the book decided 1, 2 and 3 sessions later, eligibility re-read: gross Sharpe 0.93 (t 4.71), 0.98 (t 4.96), 0.89 (t 4.50) against 1.10 as first reported [V]
  - by era, decided at D1 / one / two / three sessions later: 2000–07 0.42 / 0.52 / 0.62 / 0.47; 2008–12 1.18 / 1.07 / 0.99 / 1.02; 2013–17 1.69 / 1.74 / 1.69 / 1.79; 2018–22 1.95 / 1.66 / 1.71 / 1.36; 2023–25 0.64 / −0.13 / 0.05 / 0.26 [V]
- source: `results/ideas/special_dividends/edgar_dates.py` @ `f8f26c0`; `results/ideas/special_dividends/checks.py` @ `f8f26c0`; `results/ideas/2026-11-15_special_dividends.md` @ `f8f26c0`
- supports: §4
- status: current. Corrects the headline of E-2026-11-15-02 (1.10, and 0.64 in 2023–25). An 8-K can follow a press release, so the count of late events is an upper bound; foreign filers and REITs in the sample were not checked. The shadow book enters on the feed's first listing and is unaffected

### E-2026-11-15-07 · Result: no drift after a dividend initiation or resumption once the news is two sessions old
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - 1,625 initiations and resumptions on CRSP common shares (no cash dividend in the prior 730 days), ex-dates 2000-01-27 to 2025-12-30, prices to 2025-12-31; 1,123 eligible [V]
  - pre-specified long (D1+3 to D1+62 against IWM, 10% a name): gross Sharpe 0.31 (t 1.57); halves 0.54 / 0.08; eras 0.49, 0.34, −0.19, 0.77, −0.31 [V]
  - controls: the same events 120 sessions later 0.36 (t 1.82); 60 sessions earlier 1.45 (t 7.34) [V]
  - per event against IWM: +1.34% in the ten sessions before D1, +1.66% in the ten from D1, then 0.2% to 0.4% a block [V]
- source: `results/ideas/div_initiations/explore.py` @ `ee428e5`; `scripts/research/stage_crsp_div_initiations.py` @ `ee428e5`
- supports: §4
- status: current. Gross, no costs. Set aside: the later-window control equals the book. Not independently reviewed

### E-2026-11-15-08 · Result: buying the issuer three sessions after a convertible issue is 0.67 gross, positive in every era and on liquid names, and small per event
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - 3,337 SDC convertible issues matched to a CRSP common share, issue dates 2000-01-13 to 2025-12-23, prices to 2025-12-31; 2,840 eligible [V]
  - the follow-on rule unchanged (long D+3 to D+7 against IWM, 10% a name): gross Sharpe 0.67 (t 3.39); halves 0.77 / 0.59; eras 0.81, 0.24, 1.04, 0.36, 0.62; the window 30 sessions later −0.10; 0.68 on names trading $5M a day and 0.49 on $20M [V]
  - issued 2011–22 (seen by E2 in October) 0.33; issued outside those years 0.59 (t 3.0) [V]
  - not pre-specified: alpha 4.5% a year (t 3.30); per event +0.44% mean and +0.26% median; 0.42 without the ten best events; the hold begun one and two sessions later 0.45 and 0.56 [V]
- source: `results/ideas/convert_issuance/explore.py` @ `40d1c60`; `results/ideas/convert_issuance/checks.py` @ `40d1c60`; `scripts/research/stage_sdc_convertibles.py` @ `40d1c60`; `results/ideas/follow_ons/explore.py` @ `40d1c60`
- supports: §4
- status: current. Gross, no costs. A re-run of E2 on a longer, differently dated list. Not on shadow: no live list of pricings. Not independently reviewed

### E-2026-11-15-09 · Result: dated from the first news headline, the convertible rebound is not confirmed (0.29, t 0.96, 392 events); Alpaca's news feed names 73% of 2025's issues
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - a headline containing "convertible" exists on Alpaca's news feed for 430 of 1,286 SDC issues of 2015–2025: 8% to 30% a year through 2022, 46% in 2023, 69% in 2024, 73% in 2025; 118 of 119 first headlines in 2025 came outside trading hours [V]
  - the first session opening after the headline equals SDC's issue date for 218 events, is one session later for 110 and one earlier for 64 [V]
  - long from two sessions after that session, five sessions, against IWM: gross Sharpe 0.29 (t 0.96) on 392 events; −0.30 in 2015–22 and 1.02 in 2023–25; filled at that session's own close 0.20 (t 0.67) [V]
- source: `results/ideas/convert_issuance/news_dating.py` @ `0b47e1d`; `results/ideas/convert_issuance/headline_dated.py` @ `0b47e1d`; `results/ideas/2026-11-15_convert_issuance.md` @ `0b47e1d`
- supports: §4
- status: current. A second look at the events of E-2026-11-15-08 with other dates, not a new sample; the headline-covered events are a non-random third. Gross, no costs. Not independently reviewed

### E-2026-11-15-10 · Result: the special-dividend wait still works in small names (1.23 gross on $100k–$5M a day, 1.54 in 2023–25) and has stopped in large ones
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - the corrected book (decided one session late) by 21-session dollar volume at the decision: $100k–$1M 1.12 (478 events); $1M–$5M 0.58 (486); $5M and over 0.51 (967) with −0.35 in 2023–25; $100k–$5M 1.23 (t 6.22, 964 events), eras 0.92, 0.61, 1.53, 1.78, 1.54 [V]
  - the $100k–$5M book two and three sessions late: 1.19 and 0.90; window moved 20, 40, 60 sessions later −0.18, 0.01, −0.13; without ten best events 0.99; beta to IWM −0.04 [V]
  - ordinary dividends of the same companies in the same band: 1.00 on 17,606 events (0.32 in 2023–25); per session held 4bp against the special's 19bp [V]
  - by yield inside the band: 0.37 (1–2%), 0.64 (2–5%), 1.04 (5% and over) [V]
- source: `results/ideas/special_dividends/checks.py` @ `bfce4dc`; `results/ideas/2026-11-15_special_dividends.md` @ `bfce4dc`; `shadow/signals/specdiv.py` @ `bfce4dc`; `shadow/books/specdiv_wait_small.json` @ `bfce4dc`
- supports: §4
- status: current. Not pre-specified: the size cut was made after the result, at the team lead's request for small-capital ideas. Gross; closing prices; bid-ask spread in thin names unmeasured. A second shadow book, `specdiv_wait_small`, is the forward test

### E-2026-11-15-11 · Result: short-term reversal is stronger in stocks ranked 1,501–4,000 (1.18 gross) than in the top 1,500 (0.96), and since 2013 all of it is on the short side
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - the `st_reversal_wide` rule unchanged on rank 1,501–4,000, price ≥ $5, $500k a day, CRSP to 2025-12-31: both sides gross Sharpe 1.18 (t 6.00), halves 2.09 / 0.93; signal 21 sessions stale 0.30; turnover 164 a year [V]
  - long leg against IWM 0.52 (t 2.63), halves 1.13 / −0.02, −1.26 in 2023–25; short leg against IWM 0.90 (t 4.56), halves 1.05 / 0.99 [V]
  - rank 1,501–2,500 1.19 and 2,501–4,000 1.24; median position 0.01% of a day's volume at $1M [V]
- source: `results/ideas/st_reversal_small/explore.py` @ `bfce4dc`; `results/ideas/st_reversal_wide/explore.py` @ `bfce4dc`; `scripts/research/stage_crsp_equities.py` @ `bfce4dc`
- supports: §4
- status: current. Gross, no costs, no borrow. Not promoted: the leg that needs no borrow has earned nothing since 2013. Not independently reviewed

### E-2026-11-15-12 · Result: the follow-on rebound held in small issuers through 2022 (1.00 gross on $100k–$5M a day) after stopping in large ones in 2013; 2023–25 is unclear
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - the pre-specified rebound book by 21-session dollar volume at the decision: $100k–$5M 1.00 (t 5.03, 3,285 events), eras 1.50, 1.02, 1.58, 1.53, 0.59; begun one session later 0.94; $5M and over 0.15 with −0.07, −0.88, −0.24 in the three eras since 2013 [V]
  - median event in the $100k–$5M band by era: +0.37%, +0.21%, +0.52%, +1.11%, −0.53% [V]
- source: `results/ideas/follow_ons/checks.py` @ `28ac8f3`; `results/ideas/2026-11-15_follow_ons.md` @ `28ac8f3`
- supports: §4
- status: current. Not pre-specified (a size cut made after E-2026-11-15-05). Gross, closing prices, spread unmeasured. No shadow book: no live list of offerings

### E-2026-11-15-13 · Result: the small-name special-dividend book survives the quoted spread (ask-to-bid +1.21% per event against +1.72% gross)
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - CRSP closing bid and ask on the book's own trades, $100k–$5M a day, 959 of 964 events quoted: spread at the entry close median 0.27%, mean 0.57%, 90th percentile 1.25% [V]
  - per event against IWM, bought at the closing ask and sold at the closing bid: mean +1.21%, median +0.48%, 55% positive, against +1.72% and +0.97% at closing prices [V]
  - the same by era: +0.92%, +0.21%, +1.71%, +1.88%, +2.24% (medians +0.19%, −0.41%, +1.40%, +1.03%, +1.00%) [V]
  - by band: $100k–$1M spread median 0.58%, ask-to-bid +1.74% (median +0.54%); $1M–$5M 0.14%, +0.68% (+0.40%); $5M and over 0.05%, +0.60% (+0.36%) [V]
- source: `results/ideas/special_dividends/checks.py` @ `d03e025`; `scripts/research/stage_crsp_special_divs.py` @ `d03e025`; `results/ideas/2026-11-15_special_dividends.md` @ `d03e025`
- supports: §4
- status: current. A real-money view, labelled and kept apart from the gross result; an upper bound on one round trip's quoted cost, not an estimate of fills. Depth at the quote is unmeasured

### E-2026-11-15-14 · Result: merger targets too small for arbitrage funds pay a wider spread per deal and make a worse book (0.32 over bills)
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - friendly all-cash deals, target priced $2+ and trading $100k to under $1M a day, CRSP to 2025-12-31: 541 deals (21 a year), 14.4% withdrawn; per deal +3.84% mean and +2.53% median over a median 60 sessions; 5th percentile −13.4% [V]
  - the book (equal weights, flat under five live deals): Sharpe over bills 0.32 (t 1.65), halves 0.82 / −0.15, −0.52 in 2023–25, flat on 52% of sessions [V]
  - the same rules on $5 and $1M or more: 1,865 deals, 6.5% withdrawn, +1.77% mean and +1.48% median per deal, 0.71 over bills (t 3.61); on $2 and $1M–$5M: 542 deals, 0.58 [V]
- source: `results/ideas/merger_arb/micro.py` @ `45148ea`; `results/ideas/merger_arb/explore.py` @ `45148ea`; `results/ideas/2026-11-12_merger_arb.md` @ `45148ea`
- supports: §4
- status: current. The band was fixed before its returns were read. Gross, no costs; spread not staged. Set aside

### E-2026-11-15-15 · Result: earnings drift in stocks ranked 1,501–4,000 is 1.27 gross on the long side alone against IWM, positive in every era; independently re-derived
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - universe and rule fixed before any return was read: rank 1,501–4,000, price ≥ $5, $500k a day; the `pead_wide` rule on the IBES surprise score, 40 sessions, shift(2); CRSP to 2025-12-31, 291,872 releases [V]
  - both sides gross Sharpe 1.30 (t 6.60), halves 1.29 / 1.33, signal 126 sessions late 0.41 [V]
  - long leg against IWM 1.27 (t 6.42), 12.8% a year on 10.1% volatility, halves 1.45 / 1.06, eras 1.65, 1.18, 1.40, 0.54, 1.50, late control 0.27; short leg 0.33 (t 1.68) [V]
  - the announcement-move sort, pre-specified as the second sort: 0.59, −0.06 since 2013, late control 0.68 [V]
  - independent review: long leg re-derived at 1.26 (t 6.39), identical on 6,435 of 6,437 days; no lookahead found; delay 1, 2, 5, 10, 20 sessions gives 1.12, 0.99, 0.77, 0.59, 0.36 [S]
  - stored checks, not pre-specified: 1.37 less its own universe; 1.12 with every release known the session after its date; 0.68 (t 3.41) sorted on surprise over consensus with that timing; stock-side cost of 5 / 15 / 30bp per unit traded gives 1.06 / 0.65 / 0.03 [V]
- source: `results/ideas/pead_small/explore.py` @ `525d299`; `results/ideas/pead_small/checks.py` @ `525d299`; `results/ideas/pead_wide/explore.py` @ `525d299`; `scripts/research/stage_ibes_surprises.py` @ `525d299`; `results/ideas/2026-11-15_pead_small.md` @ `525d299`
- supports: §4
- status: current. Gross; the cost figures are a labelled real-money view. The IBES consensus construction and CRSP's delisting row could not be checked at source by the reviewer. Not on shadow

### E-2026-11-15-16 · Result: the core paper book is flat on a near-worst NAV draw while its signal earned; an ETF hedge of the NAV part lowers the backtest Sharpe
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - `cef` paper account, Alpaca end-of-day equity: $100,000.00 to $99,902.79 over 34 sessions to 2026-11-13, 7.3% annualised volatility [V]
  - rebuilt from fills (sums to −$87 against −$97): hold +$522, of which NAV part −$3,164 and discount part +$3,685; fills −$609 (6.5bp on $931,022 traded); the two muni funds' NAV part −$3,350 [V]
  - backtest of the frozen spec, 2013-01 to 2026-10-14, gross: book Sharpe 1.00 (t 4.20), discount part 1.02, NAV part −0.09 (t −0.40) with 15% of the variance and correlation −0.22 with the discount part [V]
  - ETF hedge fixed before any hedged return was read (MUB, HYG, BKLN; 5-session NAV betas over 252 sessions to t−1): every group 0.93, muni only 0.94, no MUB short 0.94; volatility unchanged (5.71% to 5.73%); lower than unhedged in 2016–19, 2020–22 and 2023–26 [V]
  - 34-session windows in the backtest at 1.3× sizing: NAV part mean −0.03%, worst −3.52%, 0.4% of windows below the live −3.16%; discount part mean +1.34%, 82% of windows below the live +3.69%; book mean +1.31%, 30% of windows below the live −0.10% [V]
- source: `results/ideas/core_nav_hedge/explore.py` @ `e59f4d3`; `results/ideas/core_nav_hedge/live_split.py` @ `e59f4d3`; `results/ideas/2026-11-15_core_nav_hedge.md` @ `e59f4d3`
- supports: §4
- status: current. Gross, no costs. The live split uses Yahoo closes and NAVs and does not rebuild fees or unbooked distributions; panels end 2026-10-14, so the live window is outside the backtest. Hedge set aside; not independently reviewed

### E-2026-11-15-17 · Result: newly converted savings banks earn thrift beta in their first year, 0.32 against seasoned thrifts and negative since 2016; the niche hunt's 32 ideas are logged
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - niche hunt, six scouts and three skeptics on public sources: 32 ideas; skeptics' verdicts 5 test first, 9 worth a test, 15 weak, 3 dead [S]
  - thrift conversions, rule fixed before any return was read: 147 new CRSP listings with SIC 6035/6036 and a first close of $8 to $16, 1995-02-14 to 2025-05-02, prices to 2025-12-31; days 6 to 250, 10% a name [V]
  - first year less the equal-weighted seasoned-thrift return: Sharpe 0.32 (t 1.79), halves 0.56 / −0.08, eras 0.21, 0.94, 0.09, −0.29; less IWM from 2000-05: 0.36 (t 1.81); unhedged 1.10 [V]
  - per event, days 6 to 250 less seasoned thrifts: mean +3.0%, median −1.9%, 45% positive (t 1.13); the 17 listed 2016–25: −6.9% (t −1.89) [V]
  - control, days 251 to 630 less seasoned thrifts: −8.2% per event (t −3.27); book −0.12 [V]
  - median dollar volume on days 6 to 60 $165,038; median closing spread on day 5 0.60% [V]
- source: `results/ideas/thrift_conversions/explore.py` @ `7da05ab`; `scripts/research/stage_crsp_thrift_listings.py` @ `7da05ab`; `results/ideas/2026-11-15_thrift_conversions.md` @ `7da05ab`; `results/ideas/2026-11-15_niche_hunt.md` @ `7da05ab`; `results/ideas/niche_hunt/hunt.json` @ `7da05ab`
- supports: §4
- status: current. Gross, no costs. Second-step conversions could not be separated in CRSP. The hunt's figures are the scouts' and skeptics', not re-read here. Set aside

### E-2026-11-15-18 · Kill: a recent share offering does not spoil a small-stock earnings-drift long
- kind: kill
- era: ALPACA
- date: 2026-11-15
- figures:
  - rule fixed before the filtered return was read: drop from the long tenth any stock that priced an SDC follow-on in the 90 days strictly before the decision; CRSP to 2025-12-31 [V]
  - long leg against IWM as fixed 1.27 (t 6.42); flagged names removed 1.24 (t 6.26); removed only when primary shares were sold 1.25 (t 6.34) [V]
  - 2.9% of long name-days are flagged; the filtered leg less the unfiltered one −0.22% a year (t −0.94); flagged names alone 0.34 (t 1.72), 10.8% a year on 31.7% volatility [V]
- source: `results/ideas/pead_small/issuance_filter.py` @ `4919bfd`; `results/ideas/2026-11-15_pead_small.md` @ `4919bfd`
- supports: §4
- status: current. Gross. A second look at a sample already read; proposed by the niche hunt. Closed

### E-2026-11-15-19 · Method: the small-stock earnings-drift book is on shadow, on a free earnings feed checked against the licensed one
- kind: method
- era: ALPACA
- date: 2026-11-15
- figures:
  - Yahoo's earnings calendar by day against IBES on five 2025 release days: 1,443 of 1,524 releases found; rank correlation of the surprise 0.80 on 1,276; sign agrees on 87%; top tenths among ranks 1,501–4,000 share 44 of 64 names [V]
  - first fetch, 76 days back: 3,699 rows listed, 1,791 stored as small US companies with a complete result; 1,455 live signals on 2026-11-13 and 96 names in the long tenth; 2 min 59 s [V]
  - the book runs the version the backtest scored 0.68 (t 3.41) on licensed figures, not the 1.27 version (E-2026-11-15-15) [S]
- source: `shadow/fetch/earnings.py` @ `afd24b9`; `shadow/signals/pead.py` @ `afd24b9`; `shadow/books/pead_small_long.json` @ `afd24b9`; `shadow/tests/test_pead.py` @ `afd24b9`; `docs/REFERENCES.md` @ `afd24b9`; `results/ideas/2026-11-15_pead_small.md` @ `afd24b9`
- supports: §4
- status: current. Simulated book, starts 2026-11-17 once the VM's shadow clone has this commit. The IBES comparison was run in the session and is not stored as a script. Size is a dollar limit, not a rank; foreign listings are not removed

### E-2026-11-15-50 · Ruling and method: the corporate-action handling is fixed properly after its review: one phantom per split, the account's own rows rebased in a corp line of their own, and late rows closing the open phantom
- kind: method
- era: ALPACA
- date: 2026-11-15
- figures:
  - none (a review of the report follow-up found three ways the new corporate-action handling could show confidently wrong side figures while still reconciling; the account-row paths do not run today, the account having no such rows, but the phantom path runs on paper's first unprocessed split of a held fund. The team lead ruled on 2026-11-14 to fix all three properly rather than refuse: a split the feed lists twice is one event, and records disagreeing on the ratio raise; a position the account's rows move is rebased in its own corp component, so hold and fill stay true and every session still reconciles to the cent; rows posting within ten sessions after the event close the open phantom with a labelled reversal, and the cumulative phantom carries the later moves on the extra shares, intended to equal what is still inside the official P&L (ruled 2026-11-15); that holds only until the account trades the fund, corrected by E-2026-11-15-51. The risk check also refuses a held reading whose two session fields disagree. With no corporate action, the attribution's output is byte-identical to before)
- source: `scripts/cef/live_attribution.py` @ `adf42b2`; `scripts/cef/live_attribution.py` @ `813676a`; `scripts/ops/risk_daily.py` @ `5d9bcdf`
- supports: §4, §5
- status: superseded in part by E-2026-11-15-53 (2026-11-15): the corp component and the late-row tie-back were removed; the one-event-per-split dedupe stands

### E-2026-11-15-51 · Ruling and method: a paper split's phantom freezes at the first trade in the fund, and the account's own corporate-action rows are applied for every fund a record names, checked against the split ratio
- kind: method
- era: ALPACA
- date: 2026-11-15
- figures:
  - none (a second review of the report follow-up found the phantom kept adding the extra shares' daily moves after the runner had traded them away, so it drifted from what is in the official P&L. The team lead ruled on 2026-11-15: it freezes on the first session the account trades the fund, labelled crystallised; it then equals an independent simulation of a processed account exactly in the six tested cases, with one named gap, when paper applies the split late to an already re-sized count. Also ruled: the account's rows are applied for any fund a corporate-action record names, in any role, with late cash in lieu tied to its split; a new share count that contradicts the split ratio stops the attribution, named (rounded toward zero, which for a short is unverified); a second record of an already-handled split stops it, naming both. A method choice beyond the brief: a session whose account rows do not net to zero at their own prices values every row at the close, which two of the tested cases need to reconcile. With no corporate action the attribution's output is byte-identical to before, except one gap line on a cache without corp_activities.json)
- source: `scripts/cef/live_attribution.py` @ `891aea3`; `scripts/cef/live_attribution.py` @ `1a7a1a9`; `scripts/cef/live_attribution.py` @ `6b68fe9`
- supports: §4, §5
- status: superseded in part by E-2026-11-15-53 (2026-11-15): the account-row handling it describes was removed; the phantom's freeze at the first trade stands; and superseded in part by E-2026-11-15-54 (2026-11-15): every crystallised phantom is labelled approximate

### E-2026-11-15-52 · Method: the report job's reader reads the half-day end-of-day stamp by the same rule as the runner's client, held equal by test
- kind: method
- era: ALPACA
- date: 2026-11-15
- figures:
  - none (after PR #83 merged the client's rule (E-2026-11-14-02), the reader's own copy, close plus four hours from the calendar, is held equal to it on half days and on full days, and both refuse each wrong stamp with the same message. This updates E-2026-11-14-02's note that the reader still had the 20:00 rule, once this branch merges)
- source: `scripts/ops/alpaca_read.py` @ `f550da3`; `scripts/ops/tests/test_alpaca_read.py` @ `f550da3`
- supports: §5
- status: built on branch reports-followup, under review; not installed

### E-2026-11-15-53 · Ruling: the report stops, naming the row, whenever the account records a corporate-action row, until one has been seen; the paper-split phantom stays, labelled approximate where it cannot be exact
- kind: ruling
- era: ALPACA
- date: 2026-11-15
- figures:
  - none (a third review found four more defects in the code that applied the account's own corporate-action rows, a path paper has never exercised and whose row format is undocumented; each review round had fixed the last and found new ones. The team lead ruled on 2026-11-15 to simplify: any such row on or before the as-of stops the attribution, naming each row, and the job exits 4; no code applies one. Kept: the narrowed trigger, the paper-split phantom with its freeze at the first trade, one event per split, and the refusal of a second record of a handled split. The phantom is labelled approximate, with the reason, when the crystallising session has fills on both sides or the split leaves a fraction of a share. With no corporate action the attribution's output is byte-identical to before, except one gap line on a cache without corp_activities.json)
- source: `scripts/cef/live_attribution.py` @ `82ff173`; `scripts/cef/live_attribution.py` @ `bcc3446`; `scripts/ops/pnl_report.py` @ `bcc3446`
- supports: §4, §5
- status: built on branch reports-followup, under review; not installed; supersedes the account-row parts of E-2026-11-15-50 and E-2026-11-15-51; superseded in part by E-2026-11-15-54 (2026-11-15): every crystallised phantom is labelled approximate

### E-2026-11-15-54 · Ruling: a paper split's phantom, once frozen by a trade, is always labelled approximate, because the runner's no-trade band means a correctly processed account need not have traded to the same position
- kind: ruling
- era: ALPACA
- date: 2026-11-15
- figures:
  - none (a review found the frozen phantom's claim to equal official equity minus a processed account rested on both ending at the same position after the trade; the live sleeve trades only outside its no-trade band and only to the band's edge, sizing on equity that carries the phantom, so the true gap keeps moving after the trade. The team lead ruled on 2026-11-15: every frozen phantom is labelled approximate, naming the band, and nothing calls it exact; the figure is unchanged. An open phantom, before any trade, stays unlabelled unless the split leaves a fraction of a share. Also fixed in the same round: the stop checks the job's own as-of and names every row, and a research run on data cached before the stop existed says it did not run)
- source: `scripts/cef/live_attribution.py` @ `aead2da`; `scripts/ops/pnl_report.py` @ `aead2da`; `scripts/cef/live_attribution.py` @ `fa0c2a0`; `scripts/ops/pnl_report.py` @ `fa0c2a0`; `scripts/cef/live_attribution.py` @ `e14f79b`
- supports: §4, §5
- status: built on branch reports-followup, under review; not installed

### E-2026-11-15-55 · Ruling: the release check runs on 49b99db now; C4's corporate-action rows are read by the installed report job's first run, not by a separate script; the team lead restores the VM's ssh access
- kind: ruling
- era: ALPACA
- date: 2026-11-15
- figures:
  - none (the team lead ruled on 2026-11-15, about 20:15 New York, after PR #84 merged: (1) run the read-only release check on 49b99db tonight; (2) C4's account corporate-action rows, on which the P&L report job stops (exit 4, naming each row), are read by starting C4's report unit once by hand after the release and the `--reports` install, with no separate script and no key handling outside the existing units; (3) `ssh quantt-vm` timed out from the laptop at 20:10 New York, so `ops.prod_state` showed the VM UNMEASURED, and the team lead restores access, after which prod_state is re-run before any install)
- source: `docs/RUNBOOK.md` @ `49b99db` (8.12); `scripts/ops/pnl_report.py` @ `49b99db`
- supports: §5
- status: current

### E-2026-11-15-56 · Result: the release check on 49b99db (main after PR #84) is GO to tag; the install waits until the VM is measured
- kind: result
- era: ALPACA
- date: 2026-11-15
- figures:
  - PR #84 merged by the team lead at 20:10 New York (merge commit 49b99db); E-2026-11-14-50 to -52 and E-2026-11-15-50 to -54, whose status reads "on branch reports-followup", are on main from that merge and installed nowhere [V]
  - release-20261104-1..49b99db: 235 commits (`git rev-list --count`) [V]
  - `python3 -m pytest` exit 0, 4559 passed, 2 skipped; the real-panel replay skipped on the laptop's stale `data/cef`, its synthetic version ran [S]
  - `ops.doc_audit --check` 0 DRIFT, 2 NOTE, neither on the order path; `ops.orient` exit 0 at 49b99db with nothing uncommitted [S]
  - the DRY_RUN=1 preview exited 4 (PREVIEW); the laptop's panels end 2026-10-15 (closes) and 2026-10-14 (NAV), so the data gate refused all 13 names and no order list was built: the te4 runner path is covered by its unit tests only [S]
  - quant-reviewer and execution-engineer each covered the whole range and found no order-path defect; the only spec change is `_sizing_multiplier_note` text, `ops/books/` is unchanged, and no spec sets `below_min_names = "trade_eligible"`, so the te4 path is dormant [S]
  - the first run was NO-GO only because the execution-engineer seat, added on main in the desk rebuild, was not in the running session's agent registry, so that review never ran; it was re-run by a general agent told to act as `.claude/agents/execution-engineer.md` at 49b99db, read-only, with the other stages' results reused [V]
  - the preview's corporate-action check, in report mode on both books, showed two rows with no symbol as BLOCKING for every held name (a partial call processed 2026-11-12, a reorganisation effective 2026-11-16); report mode refuses nothing. Open PR #68 (the bond-ISIN and CUSIP fix) is the standing work on rows of this kind [S]
- source: `.claude/workflows/release-check.js` @ `49b99db`; `docs/RUNBOOK.md` @ `49b99db` (8.6, 8.9, 8.11, 8.12); `ops/books/cef_discount_book.json` @ `49b99db`; `ops/books/c4_families_book.json` @ `49b99db`
- supports: §1, §5
- status: current. Not tagged, released or installed; the tag and the install are the team lead's. Before the install: prod_state must measure the VM, because a re-install without `--armed` disarms; `quantt/session/run.py` changed, so RUNBOOK 8.6 step 2's replay applies; C4's timers are disabled before the core's install and C4 is re-installed after it (8.9); the alert push needs `alert-smtp-user` and `alert-smtp-pass` in the vault (8.11)

### E-2026-11-16-01 · Method: a paper runner for the event sleeves is built and reviewed; it is not installed or armed
- kind: method
- era: ALPACA
- date: 2026-11-16
- figures:
  - team lead's ruling of 2026-11-15: build and test a runner that trades chosen shadow books in one separate Alpaca paper account; the team lead installs and arms it [V]
  - an independent review of the order phase found no path that sends an order it must not, four book-keeping defects and four notes; all eight are fixed, each with a test that fails without the fix [S]
  - read from Alpaca on 2026-11-16, GET only: a single-asset lookup returns easy_to_borrow and borrow_status (IWM, MHD, PDI); a daily-bar request with start equal to end returns that day's bar, stamped 05:00Z [V]
  - the shadow runner writes decisions at 18:50 and 20:50 on the as-of day and 07:20 on the trading day, before the runner's 09:30 New York cut-off [V]
- source: `quantt/sleeves/run.py` @ `5b9ec56`; `quantt/sleeves/net.py` @ `5b9ec56`; `quantt/sleeves/ledger.py` @ `5b9ec56`; `quantt/sleeves/inputs.py` @ `5b9ec56`; `quantt/sleeves/prices.py` @ `5b9ec56`; `quantt/sleeves/tests/test_run.py` @ `5b9ec56`; `ops/sleeves/events_sleeves.json` @ `5b9ec56`
- supports: §4
- status: current. Paper only. Never run against a broker: the command-line entry and key loading are untested. No systemd units exist for it yet. Every value in the book file is a proposal for the team lead

### E-2026-11-16-02 · Ruling: the event sleeves trade in a new $100,000 paper account, seven books at $15,000 each, gross to 1.5x
- kind: ruling
- era: ALPACA
- date: 2026-11-16
- figures:
  - team lead, by question prompt: "New $100k paper account (Recommended)" and "Equal, gross up to 1.5x (Recommended)" [V]
  - books: specdiv_wait_small, specdiv_wait, cef_exdate_after, cef_exdate_before_after, units_exdate_after, units_exdate_before_after, pead_small_long [V]
  - derived from the ruling and awaiting confirmation at install: minimum order $25, largest name $35,000, at most 300 orders, sent from 20 to 2 minutes before the close; the core's send budget fits 346 orders in that window [V]
- source: `ops/sleeves/events_sleeves.json` @ `369a8bb`; `quantt/sleeves/tests/test_run.py` @ `369a8bb`; `quantt/sleeves/deploy/install_events_vm.sh` @ `369a8bb`; `quantt/sleeves/deploy/README.md` @ `369a8bb`
- supports: §4
- status: current. Nothing is installed or armed; the installer has passed a shell syntax check only and has never run. Supersedes "shadow books first" (2026-11-09) for these seven books

### E-2026-11-16-03 · Ruling: the events paper account is $1,000,000, $100,000 a book; the core stays at $100,000
- kind: ruling
- era: ALPACA
- date: 2026-11-16
- figures:
  - team lead, by question prompt: "$1M, $100k per book (Recommended)", the small-name special-dividend book at $25,000; and "Leave the core at $100k (Recommended)" [V]
  - the sleeves cannot share the core's account: each runner requires every position in its account to be its own, and the ex-date books hold the core's funds [V]
  - re-derived limits awaiting confirmation at install: minimum order $100, largest name $190,000 (IWM hedges three books for up to $162,500), 300 orders, 20 to 2 minutes before the close [V]
  - Alpaca's paper-trading page: a paper account starts at $100k and can be reset to an arbitrary amount; the largest amount is not stated [S]
- source: `ops/sleeves/events_sleeves.json` @ `ef8b93a`; `quantt/sleeves/tests/test_run.py` @ `ef8b93a`; `quantt/sleeves/deploy/README.md` @ `ef8b93a`; `docs/REFERENCES.md` @ `ef8b93a`
- supports: §4
- status: current. Supersedes the $15,000-a-book sizing of E-2026-11-16-02; the gross cap of 1.5x stands. Nothing is installed or armed

### E-2026-11-16-04 · Kill: the antidumping-decision calendar has too few listed small petitioners to test
- kind: kill
- era: ALPACA
- date: 2026-11-16
- figures:
  - USITC investigations file, fetched 2026-11-16: 4,446 records; 76 preliminary-phase antidumping or countervailing cases started 2021–2025 name a petitioner (10, 7, 12, 27, 20 by year); none does before 2021 [V]
  - 11 of the 76 name a company matched by name to a CRSP common stock; 7 one with a median market value under $5bn in 2021–25 (0, 0, 3, 1, 3 by year), against a gate of about 8 a year set before the count [V]
  - 184 distinct petitioner names, led by a union and by coalitions whose members the file does not list [V]
- source: `results/ideas/2026-11-15_niche_hunt.md` @ `1713155`; `results/ideas/niche_hunt/hunt.json` @ `1713155`
- supports: §4
- status: current. Counts only; no return read. The name match is rough and the count was made in the session, not stored as a script. Coalition member lists would reopen it

### E-2026-11-16-05 · Kill: patent import cases at the trade commission give about four small listed complainants a year
- kind: kill
- era: ALPACA
- date: 2026-11-16
- figures:
  - USITC investigations file, fetched 2026-11-16: 1,390 violation-phase (section 337) investigations; matched to CRSP issuer names valid on the event date, 2009–2025 [V]
  - institutions with a matched complainant 165, of which 71 under $5bn at the event (1 to 10 a year); judges' merit rulings for those small complainants 21 violation and 16 no violation [V]
  - matched respondents: 448 institutions, 136 under $5bn [V]
- source: `results/ideas/usitc_337/stage.py` @ `c8a31de`; `results/ideas/2026-11-15_niche_hunt.md` @ `c8a31de`
- supports: §4
- status: current. Counts only; no return read. Exact match on the reduced company name, so subsidiaries filing under their own names are missed

### E-2026-11-16-06 · Result: companies priced below net cash earn 0.75 against IWM, but nothing over cash-rich peers once they must be tradable
- kind: result
- era: ALPACA
- date: 2026-11-16
- figures:
  - rule fixed before any return was read: latest reported Compustat quarter, cash less all debt at or above market value; non-financial, $1, $10M, $100k a day; equal weights monthly against IWM; CRSP to 2025-12-31 [V]
  - BELOW against IWM: Sharpe 0.75 (t 3.77), 19.0% a year on 25.4% volatility, halves 1.00 / 0.57, eras 0.80, 1.04, 0.35, −0.01, 1.33; worst drawdown −83% [V]
  - control (net cash half to one times market value) 0.45; BELOW less the control 0.51 (t 2.56), halves 0.70 / 0.37 [V]
  - not pre-specified: on price $2 and $500k a day 0.28 (t 1.42) and −0.02 less its control; lists three months late 0.52; non-drug companies less their control 0.00 [V]
  - per name-month against IWM, 9,369: mean +1.9%, median −2.1%, 44% positive, best +1,211% [V]
- source: `results/ideas/net_cash/explore.py` @ `e872349`; `results/ideas/net_cash/checks.py` @ `e872349`; `scripts/research/stage_comp_net_cash.py` @ `e872349`; `results/ideas/2026-11-16_net_cash.md` @ `e872349`
- supports: §4
- status: current. Gross. The harness's constant weights rebalance daily at closing prices, which flatters shares this thin; not rescored at the quote. Not promoted; not independently reviewed

### E-2026-11-18-01 · Release: release-20261116-1 is installed on the VM for both books, armed as measured, with the report jobs; a C4 or reports install refuses while the shadow runner's unit files are on disk
- kind: release
- era: ALPACA
- date: 2026-11-18
- figures:
  - tag release-20261116-1 = 49b99db (annotated, pushed by the team lead on 2026-11-16); installed by the team lead on 2026-11-18 between about 10:14 and 10:19 New York, one wrapper step at a time, outside every send window [S]
  - before the install the VM measured: core ARMED at release-20261104-1 (DRY_RUN=0, AUTO_ARMED present); C4 DRY_RUN=0, AUTO_ARMED present; no halt file; no job running [V]
  - replay of the core's day records through the new runner (RUNBOOK 8.6 step 2, `ops.replay_exposure`): 90 runs replayed, 31 skipped; gate 8 refused 24 then, 0 now [S]
  - core install: 24 steps, units written with DRY_RUN=0, three timers read back active; C4 install: 20 steps, DRY_RUN=0, three timers read back active; reports install: 23 steps, six report timers read back active (pnl 20:30/20:35, dataqa 21:45/21:50, risk 22:15/22:20) [S]
  - after the install `ops.prod_state` measured: clone at release-20261116-1, core ARMED, newest plan 2026-11-18 decided, 10 orders, not yet sent [V]
  - the C4 install and the reports install each REFUSED on first try: "unit file /etc/systemd/system/quantt-shadow-secret.service is no unit any book installs" (and the same for quantt-shadow.service and quantt-shadow.timer). The shadow runner was installed on 2026-11-10, after the last C4 install on 2026-11-04, so this was the first meeting. The core's install does not run that scan and passed [S]
  - the way round it, twice: the three shadow unit files were moved to a holding directory outside systemd's search path, the install was run, and the files were moved back with a daemon-reload; after each restore the shadow timer and key service read enabled and active and the next firing was still 18:50 [S]
  - C4's P&L report, started once by hand (team lead's ruling, E-2026-11-15-55): unit exit 0, overall OK, as-of 2026-11-17; every session reconciles to the cent (largest residual 0.01); cumulative official from the first trade (2026-11-04, 10 sessions) -360.50 USD; no corporate-action row named; the distribution line is UNMEASURED on 17 name-days for 2026-11-17 because the second source's panel was not yet current, and is retried on a later run [S]
  - the VM's ssh rule was opened to any source address the same morning at the team lead's request ("make it reachable from any ip"); the VM accepts key logins only (a login with no key returned "Permission denied (publickey)") [V]
- source: `docs/RUNBOOK.md` @ `49b99db` (8.6, 8.9, 8.10, 8.11, 8.12); `quantt/deploy/install_vm.py` @ `49b99db` (`dormant_overrides`, `scan_units`); the install's own output, read once in the session and not stored in the repository
- supports: §1, §5
- status: current. Open: (1) `install_vm.py`'s scan does not know the shadow runner's three unit names, so every C4 or reports install needs the park-and-restore until it does; (2) the vault has no `alert-smtp-user` / `alert-smtp-pass`, so a fired stop is recorded as not delivered; (3) the ssh rule is open to any address until `nsg_ip.sh` narrows it

### E-2026-11-18-02 · Result: the installer's unit scan now knows the shadow runner's three unit names, so a C4 or reports install no longer refuses beside it
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - `install_vm.dormant_overrides` treats `quantt-shadow-secret.service`, `quantt-shadow.service` and `quantt-shadow.timer` (`SHADOW_UNIT_FILES`) as known, as it already did the report units; the installer still never writes, starts or stops them [V]
  - three new tests: a C4 install and a `--reports` install each go through with the three files on disk, leave them byte-identical, and still refuse a stray `quantt-shadow-extra.service`; the names are pinned to what `shadow/deploy/install_shadow_vm.sh` writes [V]
  - with only the scan line reverted, the C4 test and the reports test both fail on the refusal seen on the VM ("is no unit any book installs") [V]
- source: `quantt/deploy/install_vm.py` @ `6087ab5` (`SHADOW_UNIT_FILES`, `dormant_overrides`); `quantt/deploy/tests/test_install_vm_books.py` @ `6087ab5`; `quantt/deploy/tests/test_install_vm_reports.py` @ `6087ab5`; `docs/RUNBOOK.md` @ `6087ab5` (8.10)
- supports: §5
- status: current, not released. Until a release carries it, a C4 or reports install on the VM needs the park-and-restore in RUNBOOK 8.10. The event sleeves' installer (branch mission-work, `quantt-events-*` units) is not covered and must register its names when it reaches main

### E-2026-11-18-03 · Result: CEFConnect serves its block page to the laptop as well as the VM, so the core's NAV cross-check still has no second source; the nightly data QA now flags that every night with the day count
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the core collector's log on the VM carried "nav_crosscheck: second source unavailable (cefconnect: JSONDecodeError)" on 821 lines, the first dated 2026-10-29; `docs/JOURNAL.md` dates the refusals from 2026-10-21 [S]
  - the same request from the laptop on 2026-11-18 at about 15:24 UTC (PDI, `scripts/cef/fetch_daily.py` `_cefconnect_navs`): HTTP 200, `text/html`, 17,298 bytes, titled "Your request was blocked"; not an Azure-only block and no sign the endpoint moved [S]
  - recording the outage as a status and calling the day COMPLETE was the team lead's ruling of 2026-10-29 (E-2026-10-29-08), not an unnoticed failure; what was missing is any report that named it [V]
  - `scripts/ops/data_qa.py` gains Q9: it reads the collector's `report.json` for the as-of day and FLAGs a cross-check that was unavailable or did not complete, with the count of consecutive trading days and the first day ("at least N" when an earlier report is missing); UNMEASURED, never OK, when there is no report; NOT_RUN for C4, which has no second source by ruling. No threshold was chosen: it flags from the first night [V]
  - seven new tests in `scripts/ops/tests/test_data_qa.py`, all failing against `8cac532`'s `data_qa.py`; nothing on the live path changed (collector, session and fetcher untouched) [S]
- source: `scripts/ops/data_qa.py` @ `4098634` (`q9_second_source`); `scripts/ops/tests/test_data_qa.py` @ `4098634`; `docs/DATA.md` @ `4098634`; `docs/REFERENCES.md` @ `4098634` (today's row); `results/ops/NAV_SOURCE_WORKAROUND_2026-10-19.md` @ `8cac532` (the shortlist of replacement sources)
- supports: §1, §5
- status: current, not released. The book still decides on one NAV source (Yahoo). The replacement second source is the team lead's choice from the 2026-10-19 shortlist; changing how the fetcher looks to the site is ruled out there. Not determined: whether the 21:45 QA job always finds the 21:40 collect's report for the as-of day (if not, Q9 says UNMEASURED and names the file)

### E-2026-11-18-04 · Ruling: the event sleeves are sized by equal risk per family and start at a quarter size on a ladder; a shadow book is promoted after ten clean sessions; no combined risk budget yet
- kind: ruling
- era: ALPACA
- date: 2026-11-18
- figures:
  - backtest daily correlations between sleeves of different families are within ±0.06 (11 series; core against C4 0.02 over 3,145 sessions, 2013-06-25 to 2025-12-23); within a family the variants are one bet: CEF ex-date pair 0.70, units pair 0.65, special-dividend pair 0.49; from the portfolio-manager run of 2026-11-18, gross; panels: core to 2026-10-14, CRSP event panels to 2025-12-31 [S]
  - live, core against C4 official daily P&L: +0.16 over 10 sessions (2026-11-04 to 11-17), 95% interval -0.52 to +0.72: no information yet [S]
  - the seven event sleeves at the 2026-11-16 sizes ($100,000 each, $25,000 for the small-name book): the units ex-date pair is 68.3% of the account's backtest risk, earnings drift 16.6%, CEF ex-date 10.5%, special dividends 4.6%; covariance of the seven series, 2000-06-01 to 2025-12-23, 6,430 sessions [V]
  - equal risk per family on the same $625,000, the small-name book kept at $25,000 and the $81,000 that frees left unallocated: cef_exdate_after $132,000, cef_exdate_before_after $97,000, units_exdate_after $52,000, units_exdate_before_after $36,000, specdiv_wait $105,000, specdiv_wait_small $25,000, pead_small_long $96,000 [V]
  - three schemes on 2014-06-25 to 2025-12-23: equal risk beats equal dollars by +0.59 to +1.22 of Sharpe on all 11 series and +0.22 to +0.70 without the four ex-date books (90% block-bootstrap intervals); a shrunk mean-variance scheme is within noise of equal risk. The portfolio Sharpes themselves (5 to 6 with the ex-date books, about 3 without) are gross backtests leaning on unreviewed ex-date results and are not forecasts [S]
  - the team lead's answers: sizing "Equal risk per family"; combined budget "No combined budget yet"; promotion "10 clean sessions + ladder"; build order "Runner PR, then report" [V]
  - `ops/sleeves/events_sleeves.json` now holds each sleeve at a quarter of its full size (every sleeve has zero live sessions), with `min_order_usd` 25 and `max_name_usd` 50,000 re-derived for that stage; the pinning test was edited with it [V]
- source: `ops/sleeves/events_sleeves.json` @ `b5b5687`; `quantt/sleeves/tests/test_run.py` @ `b5b5687`; `docs/SYSTEM.md` @ `b5b5687` (section 5, the block dated 2026-11-16 and 2026-11-18); the allocation scripts and per-sleeve series are outside the repository in `~/quantt_research/pm_alloc_2026-11-18/`
- supports: §5
- status: current. The events runner is not installed and has never run against a broker. The allocation analysis was one run by one agent and has not been independently re-derived; the C4 series in it is the trial-52 series, not the deployed blend

### E-2026-11-18-05 · Result: a thin ETF's gap to its liquid twin closes before a next-close fill; killed, and the review agrees
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: a thin ETF's gap to its most-correlated liquid twin, traded back for 5 sessions; data: every CRSP fund/ETF, 6,933 with dead ones (2025-12-31) [S]
  - last-trade prices 0.32 (t 1.55); mid quotes 0.48 (t 2.35); one more session's wait 0.09; 29,439 events [S]
  - independent adversarial review, which re-ran the scripts: kill holds; without the 10 best days 0.24 [S]
- source: `results/ideas/2026-11-16_etf_twins.md` @ `a9f6c44`; `results/ideas/etf_twins/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. SET ASIDE (killed): the gap closes before a next-close fill. Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-06 · Result: share-class spreads revert (0.89 gross) but the average trade is smaller than the quoted spread; not promoted
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: spread reversion between two share classes of one company, 245 pairs; data: CRSP daily with delisted (2025-12-31) [S]
  - gross Sharpe 0.89 (t 4.54), every era positive, both controls flat; +28.5bp a trade against a 28.9bp two-leg quoted spread [S]
  - independent adversarial review, which re-ran the scripts: holds; at fill-day closing quotes the mean trade is −40bp [S]
- source: `results/ideas/2026-11-16_dual_class_pairs.md` @ `a9f6c44`; `results/ideas/dual_class_pairs/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. EXPLORE, not promoted: smaller than the spread; reopens on closing-auction fill data or a borrow reading. Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-07 · Result: S&P SmallCap 600 deletions do not beat matched controls at month-end entry; set aside with a 3-session lead
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: rebound in S&P SmallCap 600 deletions and give-back in additions after the effective date; data: CRSP daily; change list (2025-12-31) [S]
  - deletions vs IWM 20 sessions 0.19 (t 0.80), no better than matched controls [S]
  - independent adversarial review, which re-ran the scripts: holds; lead, picked after looking: a 3-session rebound on the 160 deletions datable to the rebalance Friday [S]
- source: `results/ideas/2026-11-16_sp600_changes.md` @ `a9f6c44`; `results/ideas/sp600_changes/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. SET ASIDE; reopens as one pre-specified 3-session rule. Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-08 · Result: the leveraged-ETF give-back happens on the next session before a next-close fill; set aside, with an open-fill lead found in review
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: fade the underlying after days when leveraged ETFs' forced closing trade was large against its volume; data: CRSP daily, 373 leveraged funds identified by rule (2025-12-31) [S]
  - next-close fills: sector/index book 0.09 (t 0.37); the give-back is at t+1 (+11.3bp, t 5.56), before the fill [S]
  - independent adversarial review, which re-ran the scripts: weaker than claimed; open-to-close on t+1 scores 1.49 (t 6.5) gross at 154× turnover, found after the fact [S]
- source: `results/ideas/2026-11-16_levered_etf_reversal.md` @ `a9f6c44`; `results/ideas/levered_etf_reversal/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. SET ASIDE under next-close fills; reopens as a pre-specified next-open rule scored on opening quotes. Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-09 · Result: nothing is left of a thin ETF's stale close at the desk's fill; killed
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: drift left after a thin ETF's stale close, filled at the next close; data: every CRSP fund/ETF (2025-12-31) [S]
  - main book 0.18 (t 0.92); +3.1bp per event against a 28bp median spread; controls flat [S]
  - independent adversarial review, which re-ran the scripts: kill holds; a residual on mids in the fastest cells earns about 1.2bp per unit traded against a 14bp half spread [S]
- source: `results/ideas/2026-11-16_thin_etf_catchup.md` @ `a9f6c44`; `results/ideas/thin_etf_catchup/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. SET ASIDE (killed). Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-10 · Result: predicted crossings of the Russell 2000's bottom edge earn nothing over their controls; set aside
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: stocks crossing between the Russell 2000 and the microcap zone, predicted from market-value ranks; data: CRSP daily (2025-10-31) [S]
  - additions vs IWM 0.10; deletions less additions 20 sessions +1.8% a year (t 1.19), 60 sessions +4.0% (t 1.41), 2009 alone +54%; controls match [S]
  - independent adversarial review, which re-ran the scripts: holds [S]
- source: `results/ideas/2026-11-16_russell_micro_boundary.md` @ `a9f6c44`; `results/ideas/russell_micro_boundary/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. SET ASIDE; reopens on FTSE Russell's published add/delete lists. Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-11 · Result: closed-end funds keep falling after a distribution cut; the raise drift is weaker than first claimed
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: a CEF's regular distribution cut (rebound) or raise (drift) as a dated event, 20 and 60 sessions; data: every CRSP closed-end fund with dead ones (2025-12-31) [S]
  - cuts keep falling: book −0.94 (t −4.78), −85bp per event over 20 sessions (t −5.49, n 2,224), every era; raises +0.80 (t 4.08), +83bp per event (n 1,097), taxable funds only [S]
  - independent adversarial review, which re-ran the scripts: raises weaker than claimed, +25bp (t 1.2) dated from the ex-date and −15bp in 2024–25 [S]
- source: `results/ideas/2026-11-16_cef_dist_changes.md` @ `a9f6c44`; `results/ideas/cef_dist_changes/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. EXPLORE: long-after-a-cut killed; the cut list is a candidate filter for the core book (untested); raises need a timed live feed. Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-12 · Result: closed-end funds fall about 2.5% through a rights offering's subscription period; the long after expiry does not beat its control
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: a CEF's fall through a rights offering's subscription period and its recovery after expiry; data: CRSP distributions and daily (2025-12-31), 130 eligible events [S]
  - long after expiry 60 sessions 0.39 (t 1.99), no better than the same funds a year earlier; the fall is the result: −252bp over the subscription period (t −6.4) [S]
  - independent adversarial review, which re-ran the scripts: holds; earning the fall needs a short, and at 10% borrow the short book falls from 0.71 to 0.45 [S]
- source: `results/ideas/2026-11-16_cef_rights_offerings.md` @ `a9f6c44`; `results/ideas/cef_rights_offerings/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. EXPLORE: reopens on borrow measured inside the window. Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-13 · Result: dated term trusts earn the bill rate into termination and nothing over it; set aside
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: dated term CEFs converging to NAV into their termination date; data: CRSP names and daily (2025-12-31), 38 events in 31 years [S]
  - long only 0.60 (t 3.33) but 0.06 less the CEF market and +0.05% per event less SHY: the return is the bill rate [S]
  - independent adversarial review, which re-ran the scripts: null holds; the liquidating payment was missing from the panel and adding it does not change the answer [S]
- source: `results/ideas/2026-11-16_cef_term_trusts.md` @ `a9f6c44`; `results/ideas/cef_term_trusts/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. SET ASIDE; reopens with point-in-time NAVs from EDGAR. Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-14 · Result: the January rebound in the year's worst closed-end funds is not there; set aside
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: the year's worst fifth of CEFs bought in mid-December for the January rebound; data: CRSP CEF panel (2025-12-31), 25 seasons [S]
  - worst fifth less all funds +0.50% a season (t 0.97, 14 of 25); small-cap stocks under the same rule +0.91% [S]
  - independent adversarial review, which re-ran the scripts: null holds [S]
- source: `results/ideas/2026-11-16_cef_tax_loss_january.md` @ `a9f6c44`; `results/ideas/cef_tax_loss_january/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. SET ASIDE. Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-15 · Result: a small pay-date bump exists in closed-end funds but the reinvestment mechanism's own tests fail; explore
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: the reinvestment plan agent's buying around a CEF's payment date; data: CRSP distributions and daily (2025-12-31), 72,439 events [S]
  - book 1.66 (t 8.41) at 71× turnover; +9.1bp per event (t 3.68); the mechanism's own tests fail (discount less premium funds −0.05) [S]
  - independent adversarial review, which re-ran the scripts: weaker than claimed; about +28bp over P−1..P since T+1 settlement, against a 19bp spread [S]
- source: `results/ideas/2026-11-16_cef_drip_paydate.md` @ `a9f6c44`; `results/ideas/cef_drip_paydate/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. EXPLORE: reopens as one settlement-aligned rule run forward. Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-16 · Result: unit trusts' forced selling of closed-end funds into a termination date, and the rebound after, survive an adversarial review; promising
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: forced selling of CEFs by unit trusts into their mandatory termination date, and the rebound after; data: EDGAR 487 filings (First Trust, a one-in-three sample) and CRSP daily (2025-12-31), 24,623 events [S]
  - T−9..T −39.9bp (t −9.8); T+1..T+10 +33.2bp (t 7.8); pre-specified T+2..T+11 +14.9bp (t 3.7); dose-response by sale share; controls score nothing [S]
  - independent adversarial review, which re-ran the scripts: could not break it; the T-close entry was chosen after seeing the profile, and a day late keeps 13bp [S]
- source: `results/ideas/2026-11-16_uit_cef_flows.md` @ `a9f6c44`; `results/ideas/uit_cef_flows/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. PROMISING (EXPLORE, cleared): next a pre-specified T-close rule and a shadow book. Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-17 · Result: a soft group cap on the core book is no better than a plain size cut; set aside
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule, fixed before any return was read except where the card says otherwise: a soft cap on each group's net position in the core book, on the canonical harness; data: the desk's CEF panels (2026-10-14) [S]
  - uncapped 1.15 (t 4.20); a 25% flat cap 1.13 at lower gross; no cap beats a plain size cut [S]
  - independent adversarial review, which re-ran the scripts: holds; the muni evidence is one episode in 2026 [S]
- source: `results/ideas/2026-11-16_core_group_cap.md` @ `a9f6c44`; `results/ideas/core_group_cap/explore.py` @ `a9f6c44`; `results/IDEA_LEDGER.md` @ `a9f6c44`
- supports: §4
- status: current. SET ASIDE: no cap (team lead, 2026-11-18, leaves the core uncapped). Gross. The builder's run was cut off on 2026-11-16 and completed on 2026-11-18 by a second agent holding the written rule; figures are the agents' reports, not re-derived by the desk lead. The reviewer's own scripts were scratch files and are not in the repository

### E-2026-11-18-20 · Method: two unit-trust termination shadow books are written, on a rule fixed before any 2026 price was read and a calendar of 271 trusts built from every First Trust and Guggenheim prospectus since 2023-07
- kind: method
- era: ALPACA
- date: 2026-11-18
- figures:
  - the rule as written: a closed-end fund held by a terminating First Trust or Guggenheim closed-end trust, price $2 or more and 21-session dollar volume $100,000 or more read 10 sessions before T; decided after the close of T−1, bought at the close of T, sold at the close of T+3; long only; weights in proportion to the number of trusts, adding to 1, no fund above 10% [S]
  - the second book keeps events whose estimated sale is 5% or more of the fund's dollar volume over T−18..T−10, size from 24F-2NT notices filed more than 30 days before T [S]
  - forms 487 of the two sponsors filed 2023-07-01 to 2026-11-17: 2,374; read in full (15 or more mentions of "closed-end"): 426; trusts parsed 605; closed-end trusts 334; in the calendar (terminating 2026-01-02 to 2028-11-13) 271, First Trust 204 and Guggenheim 67; 6,876 trust-fund rows, 6,249 fund-events on 307 funds [V]
  - unparsed and listed by accession number: 7 trusts, all Guggenheim's Flaherty & Crumrine Preferred Portfolio; forms 24F-2NT parsed: 269, for 206 of 241 registrants [V]
  - the prospectus's own "CLOSED-END FUNDS" heading against the research's CRSP rule, on the 384 trusts the idea's crawl parsed from filings since 2023-07-01: the same answer on all 384 (195 closed-end, 189 not); local check on licensed rows, not stored [V]
  - terminations from 2026-11-19 to 2027-11-18: 101 trusts (First Trust 78, Guggenheim 23) on 64 dates, 2,276 fund-events on 249 funds; trusts by month from November 2026: 2, 12, 10, 7, 6, 11, 7, 9, 5, 5, 8, 12, 7 [V]
  - decisions in the next 252 sessions that hold anything: 151, median 30 funds, none under ten funds, so the 10% cap does not bind on the all-events book [V]
  - first price fetch (Yahoo, 2026-11-18, after the rule was committed): 153 of 167 funds near a termination date have prices to 2026-11-17; the 14 without cannot be held [V]
  - the first termination date ahead is 2026-11-20 (one trust, 30 funds, 29 with prices): decided 2026-11-19, bought at that close, if the commit is on the shadow branch by then [V]
- source: `shadow/signals/uit_termination.py` @ `96b05ff`; `shadow/universes/build_uit_terminations_v1.py` @ `96b05ff`; `shadow/universes/uit_terminations_v1.csv` @ `96b05ff`; `shadow/books/uit_termination.json` @ `96b05ff`; `shadow/books/uit_termination_big_sale.json` @ `96b05ff`; `results/ideas/2026-11-16_uit_cef_flows.md` @ `96b05ff`; `docs/REFERENCES.md` @ `96b05ff` (§12ut)
- supports: §4, §5
- status: current. SIMULATED books, not evidence of what trading earns; committed locally on branch shadow-uit, not pushed and not on the VM. The nightly run itself was not run on the laptop (it needs the Alpaca data key); the price fetch and both signal functions were run on real prices, weights only, no return read. The 98 trusts that terminated between 2026-01-02 and 2026-11-18 are the out-of-sample year and have not been scored

### E-2026-11-18-21 · A read-only promotion and ladder report for the event sleeves; the book file now states each sleeve's full size and family; three of the ladder's tests cannot be measured yet
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - `quantt/sleeves/promote.py` (`python3 -m quantt.sleeves.promote --shadow-state <dir> --events-state <dir>`) counts both rules of E-2026-11-18-04 from the two state directories and prints the one-line edit of the book file that is due; exit 0 agree, 30 a change is due, 31 unmeasured, 32 refused. It imports the standard library and `config.py` only and names no call that writes a file, which a test checks from source [V]
  - a clean session, as implemented and for the team lead to confirm: one row of the shadow book's `scores.csv` whose status is SCORED or FLAT and whose filling decision (`decisions/<prev>.json`) was written before 13:00 New York on that session; eligible when the latest 10 rows are all clean. A flat day with an on-time decision counts; the engine also writes FLAT when no on-time decision exists, so the status alone is not used [V]
  - the book file gains two required keys per sleeve, `full_capital_usd` and `family`: 132,000, 97,000, 52,000, 36,000, 105,000, 25,000 and 96,000 dollars in four families, the figures of E-2026-11-18-04; `capital_usd` is unchanged and is still the only size the runner trades (`run.py`, `net.py` and `ledger.py` are untouched) [V]
  - the report refuses, naming the sleeve, a `capital_usd` that is not its full size x 0.25, 0.5 or 1; all 7 sleeves in the released file read as a quarter [V]
  - not measurable, and reported as UNMEASURED: the 20-to-59 stage ("if fills track the shadow book" has no written definition; the report prints paper and shadow P&L on the same sessions and their difference, with no pass or fail) and the stage from 60 sessions (no sigma is recorded for any sleeve, and `sleeve_scores.csv` does not record the capital each session traded at) [V]
  - run on the laptop on 2026-11-18 against the copy of the VM's 2026-11-17 scoreboard, which holds no state files, and no events state: all 7 shadow records and all 7 sleeve verdicts UNMEASURED, each naming the missing path, exit 31. The report has not been run against real state [V]
  - on that 2026-11-17 scoreboard the most sessions any shadow book had was 5 (scored plus flat), so no book can have had 10 clean sessions then; whether each was on time cannot be read from a scoreboard [S]
  - `.claude/skills/paper/SKILL.md` told agents to refuse "anything under `quantt/`" for a new sleeve; it now refuses a new account, a book config under `ops/books/` and a scheduler entry, and sends a sleeve in the events account through the report and a one-file PR [V]
- source: `quantt/sleeves/promote.py` @ `99cbae4`; `quantt/sleeves/tests/test_promote.py` @ `99cbae4`; `quantt/sleeves/config.py` @ `99cbae4`; `ops/sleeves/events_sleeves.json` @ `99cbae4`; `quantt/sleeves/deploy/README.md` @ `99cbae4` ("Promotion and the ladder"); `.claude/skills/paper/SKILL.md` @ `99cbae4`
- supports: §5
- status: current, on branch `sleeve-promotion`, not merged and not released. Open for the team lead: whether a flat day with an on-time decision is a clean session; what "fills track the shadow book" means; which sigma the 60-session test uses (the backtest volatilities in `_note_sleeves` are the only candidate on record) and at what capital; whether a sleeve that has traded is demoted by a later unclean shadow day (the report does not)

### E-2026-11-18-22 · Result: a hold-off after a distribution cut lowers the return of both live closed-end-fund books; no change to either
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - asked because E-2026-11-18-11 found funds keep falling after a cut, and a discount-reversion book might buy that; tested on the canonical harness with that card's event definition, rule fixed before any return was read: no new long, or flat, for 20 or 60 sessions after the cut is known [S]
  - events: 38 cuts on 10 of the core's 13 funds since 2013-06-25 (2.9 a year, none after 2023-03-02); 235 cuts on 58 of the C4 z book's 74 funds since 2005 (10.9 a year); panels end core 2026-10-14, families 2026-10-09, CRSP events 2025-12-31 [S]
  - the books do buy: position change from K-3 to K+5 is +4.1% of capital on the core (t 2.3) and +0.8% on C4 (t 3.5), against about zero at unchanged declarations; book P&L in the cut fund per event is +11bp and +17bp of capital at 20 and 60 sessions on the core (t 0.7, 0.8) [S]
  - against the unchanged book, gross Sharpe: core 1.15, no new long 1.04 (20) and 0.91 (60, -140bp a year, t -2.2), flat 1.11 and 1.08; C4 1.34, no new long 1.34 and 1.24, flat 1.32 and 1.25; turnover moves 3.2% at most [S]
  - placebo dates, 200 draws each: no variant beats them; no new long on the core is worse than 98.5% to 100% of draws; the 60-session rules are negative in every era with events on both books [S]
- source: `results/ideas/2026-11-18_core_dist_cut_filter.md` @ `c85dd8e`; `results/ideas/core_dist_cut_filter/explore.py` @ `c85dd8e`; `results/IDEA_LEDGER.md` @ `c85dd8e`
- supports: §4
- status: current. Set aside: no spec change. One agent's run, not independently reviewed. Not done: the deployed C4 blend (only the z book could be driven), C4 on total returns, cuts after 2025-12-31

### E-2026-11-18-23 · Result: the shadow runner's nightly loop now contains one book's exception, so a faulty book cannot leave the books after it without a decision
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - before: `engine.decide` turned a book's own Unmeasured into a status, but any other exception from a signal left `nightly.run`'s loop, and every later book got no decision that night [V]
  - now the broken book is printed with its exception, the run exits 3 as it does for UNMEASURED, nothing is decided for that book, and the remaining books decide; one new test, which fails on `b2df5e5` [V]
  - made the same day two unit-trust books joined the branch, taking the list to eleven books [V]
- source: `shadow/nightly.py` @ `9c4409c`; `shadow/tests/test_nightly.py` @ `9c4409c`
- supports: §5
- status: current. On branch mission-work; reaches the VM's shadow runner when the branch `shadow` is next pushed

### E-2026-11-18-24 · Ruling: a clean session is any on-time day, ten in a row; fills track means paper within twice the modelled fill cost; the 60-session sigma is each sleeve's backtest volatility. Neither ladder test can be decided yet: the capital a sleeve traded at each session is not recorded
- kind: ruling
- era: ALPACA
- date: 2026-11-18
- figures:
  - the team lead's answers to the three points E-2026-11-18-21 left open: clean session "Any on-time day, ten in a row"; fills track "Paper within 2x modelled gap"; sigma "Each sleeve's backtest vol", scaled to the capital the sleeve traded at [V]
  - the clean-session rule is what the report already counted; only its wording changed, from a reading to be confirmed to a ruling [V]
  - the book file gains a required key per sleeve, `backtest_vol_annual`: 0.042, 0.057, 0.107, 0.154, 0.053, 0.053 and 0.117 for cef_exdate_after, cef_exdate_before_after, units_exdate_after, units_exdate_before_after, specdiv_wait, specdiv_wait_small and pead_small_long: gross backtest daily volatility annualised, 2000-06-01 to 2025-12-23, the allocation run of E-2026-11-18-04, copied from the percentages already in `_note_sleeves` and not re-derived [S]
  - sigma x sqrt(T) in dollars is computed as backtest_vol_annual / sqrt(252) x the root of the summed squares of the capital traded at on each position session; full above -1 of these, stopped below -2, a half between (`sigma_verdict`, tested; for 60 sessions at 10,000 dollars and 10% a year the band is 487.95 dollars, a synthetic check of the arithmetic) [V]
  - fills track is computed as: shortfall = shadow P&L less paper P&L over every session from the sleeve's first position on that both measured; allowance = 2 x modelled_fill_cost_bp / 10,000 x the dollars the sleeve traded on them, read from the bookings in each session's `verify.json`, fills and crosses alike; pass if the shortfall is no more than the allowance (`track_verdict`, tested) [V]
  - `modelled_fill_cost_bp` is an optional per-sleeve key, absent for all 7 sleeves: the shadow engine assumes no cost and no idea card or shadow book file records a modelled cost in a form a program can read; absent is reported as UNMEASURED and never read as zero [V]
  - what the cards would support, for the team lead to set: special dividends, measured closing spread, median 0.27% for the small-name band (100,000 to 5,000,000 dollars a day), 0.14% at 1,000,000 to 5,000,000 and 0.05% above; earnings drift, the 5 / 15 / 30bp grid only; closed-end fund ex-date, "the same order as a round trip through a closed-end fund's spread" against 20 to 30bp an event, no measurement; units, nothing [S]
  - neither verdict can be reached from what the runner records: `sleeve_scores.csv` has no per-session capital column and `plan.json` holds share targets, not the capital they were sized from. Both stay UNMEASURED naming that column, with or without the cost key; the report shows a labelled what-if at today's `capital_usd` for the fills-track test only. `run.py` was not changed [V]
- source: `quantt/sleeves/promote.py` @ `beefe1f`; `quantt/sleeves/tests/test_promote.py` @ `beefe1f`; `quantt/sleeves/config.py` @ `beefe1f`; `ops/sleeves/events_sleeves.json` @ `beefe1f`; `quantt/sleeves/deploy/README.md` @ `beefe1f` (open items, and the table of what each card supports); `docs/SYSTEM.md` @ `beefe1f` (section 5, the block dated 2026-11-16 and 2026-11-18)
- supports: §5
- status: current, on branch `sleeve-promotion`, not merged and not released. Open: a per-session `capital_usd` column in `sleeve_scores.csv`, a change to the order path that needs its own PR and release before the first sleeve reaches 20 position sessions; the team lead's `modelled_fill_cost_bp` for each sleeve; whether a cross inside the account counts as dollars traded (the report counts it); the backtest volatilities are from one unreviewed run

### E-2026-11-18-25 · Method: `ops.prod_state` and `ops.orient` read every book on the VM (C4 beside the core) in the one ssh call
- kind: method
- era: ALPACA
- date: 2026-11-18
- figures:
  - the team lead asked on 2026-11-18, about 10:15 New York: "make the c4 reachable as easily as everything else". Until then `ops.prod_state` read the core only; C4's newest figure in reach of the laptop was the repo's copy, last row 2026-11-06 ($100,007.79), seven sessions old [V]
  - the core's remote script is byte-identical to main's at 8cac532 (compared in the session; `TestOtherBooks` pins it); each other book in `install_vm.VM_BOOKS` adds its own script with keys prefixed `<book>.` to the same call [V]
  - first read, 2026-11-18 about 10:18 New York, from `quantt-vm:/home/quantt/quantt_state/c4/eod_equity.csv`: C4 official cumulative -$360.50 over 35 sessions, the 2026-09-29 close ($100,000.00) to the 2026-11-17 close ($99,639.50); high-water mark $101,233.72 at the 2026-11-05 close [V]
  - the same read for the core: -$204.54 over 36 sessions, to $99,795.46 at the 2026-11-17 close; the same figures as Alpaca's end-of-day history fetched directly on the laptop that morning [V]
  - a defect found and fixed in the same change: `_systemd_scheduled` read every book against the core's session timer, so an armed C4 printed "whether the scheduler fires it is UNMEASURED" [V]
  - `python3 -m pytest ops/tests` exit 0 [V]
- source: `ops/prod_state.py` @ `dd5a885`; `ops/orient.py` @ `dd5a885`; `ops/tests/test_prod_state.py` @ `dd5a885`; `ops/tests/test_orient.py` @ `dd5a885` (branch `ops-prod-state-books`)
- supports: §5
- status: on branch `ops-prod-state-books`, committed locally, not pushed, not merged, installed nowhere (the reader runs on the laptop; nothing on the VM changes)

### E-2026-11-18-26 · Result: why the two paper books are below $100,000 at the 2026-11-17 close, and why C4 sends few orders
- kind: result
- era: ALPACA
- date: 2026-11-18
- figures:
  - core, attributed from Alpaca's own records read on 2026-11-18 (568 fills from `/v2/account/activities/FILL`, raw daily SIP closes from `/v2/stocks/bars`): holding P&L +$592.57, fills against the same day's close -$785.10, CAT fees -$12.01 (61 FEE rows), total -$204.54, equal to the official end-of-day record to the cent [V]
  - core, the holding P&L by side: positions held long -$2,199.52, positions held short +$2,792.09; the equal-weight return of the 13 names from the 2026-09-29 close was negative in the 2026-11-02 to 2026-11-17 window (-2.73%) [V]
  - core, by name: the two municipal funds lost $3,105.68 between them (short from 2026-09-30 while they rose, covered 2026-11-03 and 2026-11-04, long from 2026-11-06 while they fell, flat on 2026-11-16); the other eleven names made +$2,913.15 [V]
  - core, by window: +$1,476.76 to the 2026-10-12 peak; -$2,688.21 from 2026-10-13 to 2026-10-19; +$235.47 to 2026-10-30; +$783.45 from 2026-11-02 to 2026-11-17 [V]
  - core, execution: $1,096,900 traded in 36 sessions, every fill between 15:50 and 15:59 New York; -$785.10 against the close is 7.2bp of traded notional [V]
  - Alpaca paper DID charge fees on this account: 61 CAT fee rows, $12.01. `CLAUDE.md` landmine 1 says paper charges no regulatory fees [V: docs]; the account's activity record disagrees, and the record is what was measured [V]
  - C4, official: -$360.50 at the 2026-11-17 close, eleven trading sessions from 2026-11-03. Not attributed by name: its account keys and plan are on the VM only [V]
  - distributions paper never paid or charged (dist-adjusted minus auction-marked, sessions where both exist): core +$49.32 over 28 sessions to 2026-11-13; C4 +$328.07 over 9 sessions to 2026-11-13 [V]
  - C4's plan for 2026-11-18, by the new `plan shape` reading: 74 names, of which 49 `illiquid` (under the spec's `min_adv_usd`), 7 `no discount today` (NAV-repeat mask), 1 below the minimum weight, and 17 held (7 long, 10 short), all 17 `band hold`; 0 orders; gross $122,196.86 = 1.23x the plan's equity [V]
  - the core's plan for the same day: 13 names, 12 re-targeted (`cef discount`), none on a band hold, 10 orders; gross $166,226.76 = 1.67x [V]
- source: `ops/prod_state.py` @ `8c87afd` (`plan_shape`, branch `ops-prod-state-books`); the attribution script is session scratch, not in the repo; Alpaca paper account `cef`, read-only, 2026-11-18
- supports: §5
- status: current as measured on 2026-11-18. A result about 36 sessions of one account; not a test of the strategy

### E-2026-11-18-27 · Ruling and result: the close is modelled for the investor view; at the closing-auction print the core is +$592.57 and C4 -$237.79 to the 2026-11-17 close
- kind: ruling
- era: ALPACA
- date: 2026-11-18
- figures:
  - the team lead, 2026-11-18: "on a real account we would get close, so we should model closing for showing investors" [V]
  - the measure is the runner's own `auction_hold_pnl_usd` (`quantt/session/score.py` (b), first term): the book held into the close, marked official auction print to auction print, as if every fill had printed in the auction. MODELLED, gross: no borrow, no distributions, no fees, no allowance for our orders moving the auction. The official record stays Alpaca's end-of-day history (team lead 2026-10-19) [V]
  - core, 36 sessions from the 2026-09-29 close: modelled +$592.57 against official -$204.54. Annualised sd of the modelled daily P&L on $100,000: 7.13% [V]
  - the core's score file on the VM has no row for 2026-09-30, 10-01, 10-02 and 10-06 (the laptop ran those sessions); those four days are from raw SIP daily closes and the account's fills, read on 2026-11-18. On the 32 sessions the runner scored, that second method gives -$143.74 and the runner -$143.74, with no daily difference above $0.005 [V]
  - C4, 11 sessions from 2026-11-03: modelled -$237.79 against official -$360.50 [V]
  - the two accounts together, each on $100,000: modelled +$354.78 against official -$565.04 (a sum of two books' dollars, shown for scale; the books are separate accounts) [V]
  - NOT in the modelled figure: the distributions paper never paid (measured, to 2026-11-13: core +$49.32, C4 +$328.07, E-2026-11-18-26) and the borrow a live account pays on its shorts (unmeasured) [V]
  - `ops.orient` PNL now prints an `at-close` column and a "modelled at the close" line per book, with the official sum on the same sessions beside it; scores.csv is read whole for that sum [V]
- source: `ops/orient.py` @ `9d49a98` (`close_model`); `ops/prod_state.py` @ `9d49a98` (`PNL_FILES`; branch `ops-prod-state-books`); `quantt-vm:/home/quantt/quantt_state/{cef,c4}/scores.csv` and `eod_equity.csv`, read 2026-11-18
- supports: §5
- status: current. 36 and 11 sessions: a description of what happened, not evidence of an edge

### E-2026-11-18-28 · Rulings and results: the investor headline is the net modelled view (core +$506.21); the core's gross cap is why its band never holds; C4's volume filter measured; the shadow books join the reader
- kind: ruling
- era: ALPACA
- date: 2026-11-18
- figures:
  - the team lead, 2026-11-18, by question: the investor headline is the NET modelled view (closing-auction fills, plus the distributions paper never paid, minus a fetched borrow cost); the core's churn is investigated before any change; C4's volume filter is measured and nothing changes; the VM's ssh rule stays open to any address as it is; C4's by-name attribution comes from one read-only script the team lead runs; the shadow books join the reader; PR #87 is merged after this round [V]
  - core, 36 sessions to the 2026-11-17 close: modelled close +$592.57, distributions +$49.33, borrow -$135.68, NET +$506.21 against official -$204.54. Annualised sd of the net daily P&L on $100,000: 6.64% [V]
  - the distributions figure: 24 cash dividends on held names, +$1,526.82 received on longs and -$1,477.50 paid on shorts, from Alpaca's corporate-actions endpoint and the position at the close before each ex-date. The runner's own figure on the 29 sessions both cover is +$49.32, the same five days to the cent [V]
  - the borrow figure: each close's short market value x 1.02 x fee rate / 360 x calendar days (the formula in `docs/REFERENCES.md` 12l), at IBKR's indicative fee rates in the public shortstock file stamped `#BOF|2026.11.18|17:16:53`, between 0.45% and 2.13% a year on the 13 names, 1.41% blended on an average short book of $66,144. TODAY'S rates applied to every day back to 2026-09-29: no fee history covers the period (the repo's FEE_RATE panel ends 2026-09-09). The file as fetched is verified; the rates on the earlier days are not [U]
  - under Alpaca's own live fee schedule (easy-to-borrow free, `docs/REFERENCES.md` 12l) the borrow is $0 on easy-to-borrow names and the net is +$641.90 before any hard-to-borrow fee, which Alpaca does not publish per name. The schedule is verified; the hard-to-borrow cost is not [U]
  - why the core's band holds nothing: the sleeve turns every band HOLD into a trade on any day its gross cap scales the book (`src/deploy/sleeves/cef_discount.py`, "THE BAND'S HOLDS BECOME TRADES WHEN THIS BINDS"). The core's plan for 2026-11-18 carries the cap's mark on all 13 names; C4's carries it on none [V]
  - consistent with it: $558,927 traded in the 24 sessions to 2026-10-30 and $537,973 in the 12 from 2026-11-02, when the sizing multiplier went to 1.13 and then 1.30; fills against the close cost -$308.71 in the first window and -$476.39 in the second [V]
  - C4's volume filter, by the sleeve's own rule (mean of close x volume over 63 sessions) on Alpaca SIP daily bars to 2026-11-17: 19 of 74 names at or above the spec's $3.0M; 33 at $2.0M; 45 at $1.5M; 58 at $1.0M; 66 at $0.5M. Median $1.91M. The runner's own plan for 2026-11-18, on its own panel, passes 25 (74 less 49 `illiquid`). The two counts are from different volume sources and are both reported; the runner's is what the book trades on [V]
  - a $10,000 position (10% of C4's equity) is under 1% of a day's volume on 58 of the 74 names and at most 6.4% on the thinnest [V]
  - shadow books, first read through `ops.prod_state` (SIMULATED, each on its own $1,000,000 notional, sums over SCORED sessions to 2026-11-17): cef_exdate_after -$8,419.64 price-only (-$3,249.44 total return, 4 scored); cef_exdate_before_after +$68.04 (4); units_exdate_after +$21,200.13 (+$24,480.85 total return, 2); units_exdate_before_after +$7,978.98 (1); month_end_ief and spinoff_first_week flat on every session so far [V]
- source: `ops/prod_state.py` @ `fc0232b` (`plan_shape`, `SHADOW_SCRIPT`); `ops/orient.py` @ `fc0232b` (branch `ops-prod-state-books`); `src/deploy/sleeves/cef_discount.py` @ `fc0232b`; `https://www.interactivebrokers.com/shortstock/usa.txt`, fetched 2026-11-18; Alpaca paper account `cef`, read-only; the attribution and net-view scripts are session scratch, not in the repo
- supports: §5
- status: current. C4's net view and by-name attribution wait on the team lead's run of the read-only VM script. One to four scored sessions say nothing about a shadow book

### E-2026-11-19-01 · Ruling: the events runner records the capital each sleeve was sized from, each sleeve has a modelled fill cost, and only market fills earn the allowance; both ladder tests are now computed
- kind: ruling
- era: ALPACA
- date: 2026-11-19
- figures:
  - the team lead's answers: the capital column "Yes, add it now"; the modelled cost "Card figures where measured, 15bp elsewhere"; netted trades "No, only real fills" [V]
  - runner: PLAN writes each sleeve's `capital_usd` (the config value its targets were sized from) into `plan.json`, inside `record_sha`; VERIFY copies it to a new last column of `sleeve_scores.csv`; an empty cell for the book row and for a sleeve the plan did not list. Nothing in planning, netting, the gates, the send or the ledger changed. Two new tests fail on `4ad01d0` [V]
  - book file: `modelled_fill_cost_bp` 13.5 for specdiv_wait_small and 7 for specdiv_wait, half the closing spreads measured on their card (0.27% and 0.14%); 15 for the other five, an assumption [S]
  - report: the shadow book's P&L is put in the sleeve's dollars session by session with the capital carried into that session; the allowance is 2 x the modelled cost on market fills only; 20 to 59 position sessions now end in PASS (a half) or FAIL (a quarter) and 60 on in full, half or stopped. On synthetic state: a $125 shortfall on $12,500 of fills passes at 50bp and fails at 49bp; a sleeve whose trades were all crossed fails at any cost; at $20,000 and 10% a year over 60 sessions the band is $975.90 [V]
  - an empty capital cell, a missing booked `verify.json` or a shadow decision with no notional leaves the verdict UNMEASURED, naming the date or file; nothing is read from today's book file in its place [V]
- source: `quantt/sleeves/run.py` @ `ea26621` (`SCORES_COLUMNS`, `score_rows`); `quantt/sleeves/promote.py` @ `ea26621`; `ops/sleeves/events_sleeves.json` @ `ea26621`; `docs/SYSTEM.md` @ `ea26621` (section 5); `results/ideas/2026-11-15_special_dividends.md` @ `ea26621`
- supports: §5
- status: current, not released; the events runner has never been installed, so no score file exists yet. The 15bp figures are an assumption to be replaced by each sleeve's own paper fills against the closing print. The promotion agent's run was cut off by a usage limit after it had written the runner's two tests; the rest was written and tested in the main session

### E-2026-11-19-02 · Ruling: the P&L and risk reports move to the morning after the session, because Alpaca publishes the end-of-day point in the small hours and the evening runs reported the day before
- kind: ruling
- era: ALPACA
- date: 2026-11-19
- figures:
  - first night of the report jobs on release-20261116-1 (2026-11-18): all six ran and exited 0; both pnl reports were titled "READ AT THE CLOSE OF 2026-11-17, NOT 2026-11-18", status PARTIAL, and both risk reports' drawdown blocks read UNMEASURED on the 2026-11-17 row [V]
  - when the point arrives: the core collector's run failed at 03:10 New York and the next finished at 03:40 on 2026-11-19, and `eod_equity.csv`'s read time is 08:40 UTC (03:40 New York) on the rows for 2026-11-16, -17 and -18: three nights, no exception [V]
  - the same wait is why each collector unit shows failed from the 17:10 run to the 03:10 run every night, about twenty times [V]
  - official P&L for 2026-11-18, read on 2026-11-19: core +77.39 USD to 99,872.85; C4 -550.40 USD to 99,089.10 [V]
  - the team lead's answer: "Move both to ~05:15-05:50 ET" [V]
  - built: pnl at 05:15 (core) and 05:20 (C4), risk at 05:45 and 05:50, Tuesday to Saturday; data QA unchanged at 21:45 and 21:50 on session days. The reports already choose the previous session before 16:45, so no report script's logic changed. The morning kinds have their own timer template; the installer's value check was not widened [V]
- source: `quantt/deploy/install_vm.py` @ `5092b4b` (`REPORT_SCHEDULE`, `REPORT_WEEKDAYS`); `quantt/deploy/templates/systemd/quantt-report-morning.timer.tmpl` @ `5092b4b`; `quantt/deploy/tests/test_install_vm_reports.py` @ `5092b4b`; `docs/RUNBOOK.md` @ `5092b4b` (8.11, 8.12)
- supports: §1, §5
- status: current, not released: the VM still runs the evening times until the next release is installed with `--reports`. Alpaca documents no publication time; three nights is the whole evidence, and a later point would show in the report's title as it did on 2026-11-18. Many notes inside `pnl_report.py` and `risk_daily.py` still describe the 20:30 and 22:15 runs they were written for

### E-2026-11-19-03 · Result: the VM was rebooted for its pending kernel and libc updates; both books came back armed exactly as before, and that night's decide was waiting on late NAVs before and after
- kind: result
- era: ALPACA
- date: 2026-11-19
- figures:
  - the team lead's ruling by question prompt on 2026-11-19: reboot "Tonight after 22:30 ET"; the agent runs VM upkeep itself [V]
  - before, read 22:47 to 23:00 New York: up 42 days; `/var/run/reboot-required` present since 2026-11-14 (libc6, linux-image 7.0.0-1014 and 7.0.0-1017); clone at release-20261119-1; no systemd job running; core and C4 each DRY_RUN=0 with AUTO_ARMED present; 13 quantt timers enabled [V]
  - the reboot was sent at 23:01:00 New York, 40 seconds after the 23:00 decide slot ended; ssh answered again by 23:01:28 on kernel 7.0.0-1017-azure [V]
  - after, read 23:01:34: systemd state `running` with no failed unit; all 13 timers waiting again (collect 23:10, session 23:30, P&L 05:15 and 05:20, risk 05:45 and 05:50, shadow 07:20); the core, C4 and shadow key services active with their key files present (existence only, never read); core and C4 each DRY_RUN=0 with AUTO_ARMED present; `/var/run/reboot-required` gone; `python3 -m ops.prod_state` measures both books ARMED at release-20261119-1 [V]
  - the session for 2026-11-20 was not decided for either book before or after: the decide slots of 22:00, 22:30 and 23:00 each exited 11 on the missing-NAV hold, the core for 4 of 13 funds (BIT, DSL, PDI, PDO) and C4 for 24 funds whose newest NAV was dated 2026-11-18; each book's `plan.json` (status refused) and `runs` folder were unchanged by the reboot [V]
  - Yahoo's chart feed, fetched from the laptop at 22:50 New York, had no 2026-11-19 value for XBITX, XDSLX, XPDIX or XPDOX, so the lateness is at the source [V]
  - the core's eleven sessions before this one were each decided at 22:00 the evening before [V]
- source: `docs/RUNBOOK.md` @ `d4d80cb` (section 8); `quantt/session/run.py` @ `f1ba445` (exit 11 is REFUSED); the readings are ssh output of this session, not in the repo
- supports: §5
- status: current. Whether the 2026-11-20 session was decided later that night or held the late funds at their shares from the final check is not measured here. The alert-settings unit, the one failed unit before the reboot, had not run again when the after reading was taken

### E-2026-11-19-04 · Ruling: the ten-session rule is waived for the seven event sleeves; they trade in a third paper account the team lead opens; the core's cap and the risk target are backtested before any change
- kind: ruling
- era: ALPACA
- date: 2026-11-19
- figures:
  - the team lead's answers, by question prompt: the ten clean sessions "waive it, i think deploying is better and we can adjust as eneded"; the events account "Try a third paper account (Recommended)"; the core's cap "Backtest the options first (Recommended)"; the risk target "Measure first, then decide (Recommended)"; the open pull requests "I take over everything" [V]
  - shadow sessions at the 2026-11-18 close, scored plus flat: cef_exdate_after 6, cef_exdate_before_after 6, units_exdate_after 5, units_exdate_before_after 5, pead_small_long 1, specdiv_wait 1, specdiv_wait_small 1; none had ten [V]
  - the core's plan for 2026-11-19 carries the gross cap's mark on all 13 names with a scale factor of 0.8207: the signal asked for about 2.19x gross (1.80 / 0.8207) and the cap took it to 1.80x. The multiplier is 1.30, so about 1.07 of it is delivered (1.30 x 0.8207) [V]
  - the combiner refuses a budgeted sleeve whose spec sets `sizing_multiplier` or `level_signal`; the core's spec sets the first and C4's sets both, so C4 cannot be netted into the core's account as deployed [V]
  - the live path on main is the installed tag's: `git diff release-20261116-1 origin/main -- quantt src ops/specs ops/books` is empty at bf0446a [V]
  - no code changes with the waiver: all seven sleeves are already `enabled` at a quarter of their full size in the book file, and the promotion report is read-only [V]
- source: `docs/SYSTEM.md` @ `4f5eb83` (section 5, the block dated 2026-11-19, added in the commit that carries this entry); `ops/sleeves/events_sleeves.json` @ `4f5eb83`; `quantt/session/combine.py` @ `4f5eb83`; `ops/prod_state.py` @ `4f5eb83`
- supports: §5
- status: current. Nothing is installed or armed for the events book: it waits on the account and its two vault secrets (the team lead), a release that holds `quantt/sleeves/`, and its installer's first run

### E-2026-11-19-05 · Result: a stale-NAV gate that needs no second source costs more than the stale NAVs do; the core's gate stays in report mode
- kind: result
- era: ALPACA
- date: 2026-11-19
- figures:
  - the VM's 38 core plans: the stale-NAV gate runs in `report` mode on every one; no name was held and no decide deferred; from 2026-10-21 to 2026-11-19 (21 plans) every CEFConnect read was an error and 111 of 273 name-days had a NAV dated D equal to the cent to the previous NAV [V]
  - on the desk's panel (NAV to 2026-10-14) 18.8% of name-days repeat genuinely, so about 21.8% of name-days are assumed stale; an inference from two shares, not a count of confirmed stale rows [V]
  - canonical harness, 2013-06-25 to 2026-10-14, gross: every NAV current 1.15 (t 4.20); 21.8% of name-days stale at random 1.108 (5th to 95th percentile of 200 draws 0.984 to 1.208), 7.41% a year against 7.60%; every NAV a session old 1.03 [V]
  - the hold rule: no trade on a genuine repeat alone 1.07; stale and genuine repeats both held 0.990 (0.910 to 1.075); against deciding on stale NAVs -0.118 of Sharpe (-0.239 to +0.008) and -0.70% a year (-1.39% to +0.05%) [V]
  - the team lead had chosen "gate without a second source"; the measured answer is that the only such rule, holding, loses about 0.7% a year to remove a cost of about 0.2% [V]
- source: `results/ideas/2026-11-19_nav_stale_gate.md` @ `1f27318`; `results/ideas/nav_stale_gate/explore.py` @ `1f27318`; `quantt/session/nav_gate.py` @ `1f27318`
- supports: §1, §4
- status: current. Set aside: nothing built, no spec change. Staleness is drawn at random; if stale copies sit on large NAV moves the cost is higher. One run, not independently reviewed

### E-2026-11-19-06 · Result: stale NAV copies on the core's funds are ordinary lateness, not big-move days; a quarter of fund-days are decided on one, at about 0.26% a year
- kind: result
- era: ALPACA
- date: 2026-11-19
- figures:
  - asked by the team lead ("Test the caveat first") after E-2026-11-19-05, which drew stale days at random [V]
  - 325 fund-days checked by the VM's gate (as-of 2026-10-14 to 2026-11-18) against Yahoo's NAV for the same dates fetched on 2026-11-19: 81 confirmed stale copies (24.9%), 45 genuine repeats (13.8%), 199 fresh; 3 non-repeats were also revised later [V]
  - true one-session NAV move, mean and median absolute: fresh 37.0bp and 23.9bp; confirmed stale 30.9bp and 23.7bp; within the same session stale less fresh is -0.45bp (t -0.12, 21 sessions); of the largest tenth of moves 21% were stale against 25% overall [V]
  - the cost with stale days drawn by the measured share in each move quintile, 200 draws on the canonical harness to 2026-10-14: Sharpe 1.097 (0.976 to 1.185) and 7.34% a year against 1.152 and 7.60% with every NAV current [V]
- source: `results/ideas/nav_stale_gate/checks.py` @ `1cd5351`; `results/ideas/2026-11-19_nav_stale_gate.md` @ `1cd5351`; `scripts/cef/fetch_daily.py` @ `1cd5351` (the X<TICKER>X NAV symbol the check fetches)
- supports: §1, §4
- status: current. E-2026-11-19-05's conclusion stands: no hold gate. A confirmed stale copy is a lower bound (a row Yahoo never corrected looks genuine); 21 sessions; one run, not independently reviewed. The VM's check rows and the fetched NAVs are outside the repository in `~/quantt_research/nav_stale_gate/`

### E-2026-11-19-07 · Result: one read-only page now shows every paper account together; on its first run the two accounts are down 1,038 USD combined
- kind: result
- era: ALPACA
- date: 2026-11-19
- figures:
  - built at the team lead's choice ("P&L and risk by book, one page"): `python3 -m ops.daily_page` reads, over one ssh call, each account's `eod_equity.csv` and newest risk report and the shadow scoreboard; no broker call, no key, no order code (a test pins the remote script to cat, test and ls, and the module's imports) [V]
  - first run, 2026-11-19: core official equity 99,872.85 USD at the 2026-11-18 close (+77.39 that session, -127.15 over 37 sessions, 1.58% below its high-water mark of 2026-10-12); C4 99,089.10 USD (-550.40, -910.90 over 36 sessions, 2.12% below its mark of 2026-11-05) [V]
  - the two accounts summed over the 36 sessions both have an official row for: 198,961.95 USD, -473.01 on 2026-11-18, -1,038.03 to date, 1.25% below the combined high-water mark of 2026-10-12 [V]
  - both risk reports read WATCH; neither names an ACT line; each could not measure its attribution, factor-exposure and stops blocks that night (the first two for the timing reason of E-2026-11-19-02) [V]
  - thirteen tests on synthetic replies: an account a session behind is named and the combined line stops there; an unreadable file is UNMEASURED for that book only; a malformed equity file is refused by name [V]
- source: `ops/daily_page.py` @ `d4d80cb`; `ops/tests/test_daily_page.py` @ `d4d80cb`; `docs/RUNBOOK.md` @ `d4d80cb` (8.6)
- supports: §1, §5
- status: current. It runs from the laptop on demand; nothing schedules it. The page holds no limit of its own, and the combined drawdown is judged against nothing: there is no combined risk budget (team lead, 2026-11-18). Combined factor exposure is not in this version

### E-2026-11-19-08 · Rulings and results: the core's cap stays as it is after a backtest of four variants; an all-equal-z session holds and says so; the review of the installed release found no order-path defect; the events waiver is a key in the book file
- kind: ruling
- era: ALPACA
- date: 2026-11-19
- figures:
  - the team lead's answers, by question prompt: the core's cap "Leave it as it is (Recommended)"; the vol fallback "Stop and name it (Recommended)", then, once the replay showed when it fires, "Hold, but say so (Recommended)"; the release steps "You prepare, I run them (Recommended)"; pushing the integration branch "Yes, push it (Recommended)" [V]
  - an independent read-only review of the live path at release-20261116-1 (the sleeve, decide and score read in full; run, gate, verify, collect and dist_score in part): no defect that double-sends, sizes on a wrong denominator or mis-states P&L. Confirmed by running code: with `min_trade_usd` 0 a cap-scaled day orders every held name. Latent: `max_nav_age_bd` cannot fire under the band; the vol scalar's `else 1.0`; `ops/books/*.json` `limits.*` are read by no code [S]
  - the cap backtest, canonical harness (`band_frontier.build_targets`, `band_gross_capped`, `evaluate`, shift(2)), price-only gross, 2013-06-25 to 2026-10-14, panels to 2026-10-14: deployed (x1.30, cap 1.80) 6.85% a year, vol 5.36%, Sharpe 1.28, turnover 31.7; band after the cap 6.32%, 5.30%, 1.19, 26.1; cap 2.00 6.91%, 5.53%, 1.25; cap 2.20 6.99%, 5.67%, 1.23; x1.00 5.41%; x1.13 6.03%; no cap 7.04% [S]
  - the same run at 5 / 15 / 30bp a trade, the real-money view: deployed 5.26 / 2.09 / -2.67; band after the cap 5.02 / 2.41 / -1.50. The ranking flips between 5bp and 15bp [S]
  - its reproduction check on the fit-cut panel (to 2022-12-30) against `results/cef/prereg_voltarget/flatten_exact_output_2026-11-02.txt`: x1.30 3.78% / 0.81 / 8.39% max drawdown / 1.343 gross when held, against the recorded 3.78% / 0.805 / 8.39% / 1.343 [S]
  - in the backtest the cap binds on 30.7% of held days over the whole period and 50.8% from 2023; over the panel's last 60 full sessions the target gross x 1.30 has a median of 2.23 and is above 1.80 on 98.3% of them [S]
  - the real-panel replay of the changed sleeve, the core's spec, 750 sessions (2023-10-18 to 2026-10-14): no session raises; the trailing vol is positive on all 749 sessions that reach it (minimum 0.0159); the 750th, 2025-04-07, is the explicit hold (every eligible z at -4.00 on 7 names) [V]
  - on that day, from a held book of five names, the released sleeve and the changed one return the same five share counts; from a flat book on an opening session the released sleeve returns seven SHORT targets with NaN weights and the changed one opens nothing [V]
  - `ops/sleeves/events_sleeves.json` gains `promotion_waived: true` on all seven sleeves (optional, may only be true, read by `promote.py` only); `capital_usd`, `enabled` and every limit are unchanged [V]
  - the vault holds secrets named `alpaca-events-key-id` and `alpaca-events-secret-key`, both enabled (names and the enabled flag read on 2026-11-19; no value read; whether the keys authenticate and the account's balance are not measured) [V]
- source: `src/deploy/sleeves/cef_discount.py` @ `860d5f3` (the cap block as reviewed; the change is in the commit that carries this entry); `scripts/cef/band_frontier.py` @ `860d5f3`; `quantt/sleeves/config.py` @ `860d5f3`; `quantt/sleeves/promote.py` @ `860d5f3`; `ops/sleeves/events_sleeves.json` @ `860d5f3`; `docs/SYSTEM.md` @ `860d5f3` (section 5, 2026-11-19); the backtest, review and replay scripts are session scratch, not in the repo
- supports: §5
- status: current, on branch `events-runner-main`, not merged, tagged or installed. The backtest and the review are each one run by one agent, not independently re-derived. The C4 spec was not replayed (its panel is not on the laptop); its level-signal path already raised on a vol with no ratio

### E-2026-11-19-09 · Ruling: the unit-trust termination book is the events account's eighth sleeve at a quarter size; the events runner has one dry session before it is armed; the release goes on 2026-11-19 for the core and C4
- kind: ruling
- era: ALPACA
- date: 2026-11-19
- figures:
  - the team lead's answers, by question prompt in this session: the eighth sleeve "Yes, add it (Recommended)" (the other session's prompt: "Yes, at a quarter size"); release timing "This afternoon, before 15:25 ET"; the first arming "One dry session first (Recommended)" [V]
  - `ops/sleeves/events_sleeves.json` gains `uit_termination`: family `unit_trust_terminations`, `full_capital_usd` 139,000, `capital_usd` 34,750, `backtest_vol_annual` 0.081, `modelled_fill_cost_bp` 15, `promotion_waived` true. The eight sleeves' `capital_usd` sum to $170,500 [V]
  - the full size is the other session's derivation, not re-derived here: one family's risk unit 96,000 x 0.117 = 11,232 dollars a year, over the book's 8.07% annual volatility on the 225 sessions 2025-12-29 to 2026-11-18 [S]
  - the rule's out-of-sample result is E-2026-11-19-20; this entry adds nothing to it [S]
  - `quantt/sleeves/deploy/install_events_vm.sh` stops if a listed book has no `decisions` directory under the shadow state; the other session reports `uit_termination`'s first shadow decision is the 18:50 New York run of 2026-11-19, so the events install cannot pass before it [S]
- source: `ops/sleeves/events_sleeves.json` @ `f4a5aad` (the sleeve is in the commit that carries this entry); `quantt/sleeves/tests/test_run.py` @ `f4a5aad`; `quantt/sleeves/deploy/install_events_vm.sh` @ `f4a5aad`; `shadow/books/uit_termination.json` @ `f4a5aad`; `docs/SYSTEM.md` @ `f4a5aad` (section 5, 2026-11-19)
- supports: §5
- status: current, on branch `events-runner-main`; not merged, tagged or installed

### E-2026-11-19-10 · Release: release-20261119-1 is installed on the VM for the core, C4 and the report jobs, both books armed as measured; the events runner is in the tag and not installed
- kind: release
- era: ALPACA
- date: 2026-11-19
- figures:
  - the team lead, 2026-11-19, on the prepared steps: "Can you runt htose i dont want too". This session then ran the admin merge of PR #89 (merge commit f1ba445, CI passed on 8eb1bb9), the tag and the VM install [V]
  - `release-20261119-1` = f1ba445; its files equal the tested head 8eb1bb9 (`git diff --quiet`), on which `python3 -m pytest` exited 0 and `ops.doc_audit --check` gave 0 DRIFT [V]
  - before the install (12:37 New York): clone at release-20261116-1; core and C4 each DRY_RUN=0 loaded and AUTO_ARMED present; no HALT file; no job running [V]
  - `ops.replay_exposure` on the core's day records copied from the VM, through the tag's code: 92 runs replayed, 31 skipped, gate 8 refused 24 then and 0 now [V]
  - the install, 13:01 to 13:04 New York: C4's timers disabled and the core's stopped; the core's dry run did not refuse (the installed installer checks the clone out at the new tag itself, so no separate checkout step was run); core `--apply --enable --armed`; C4 `--book c4 --apply --enable --armed` beside the shadow runner's unit files with no park step; `--reports --apply --enable`. Every installer run exited 0 and read its timers back as active [V]
  - after (13:04, `ops.prod_state` from the tag): clone at release-20261119-1; core ARMED and C4 ARMED (DRY_RUN=0 loaded, AUTO_ARMED present, session, verify and collect timers active and enabled); the core's plan for 2026-11-19 decided with 13 orders and C4's with 2, neither sent yet; `quantt-shadow.timer` active and enabled [V]
  - the report timers after: data QA Mon-Fri 21:45 and 21:50; P&L Tue-Sat 05:15 and 05:20; risk Tue-Sat 05:45 and 05:50. The four P&L and risk jobs each ran once at 13:02:22, when their timers were started, and exited 0; they are read-only [V]
  - `quantt-reports-secret.service` is failed: the vault has no `alert-smtp-user` or `alert-smtp-pass`, as the installer warned and as before this release [V]
  - no `quantt-events-*` unit exists. The events installer stops on a listed book with no shadow decisions directory, and `uit_termination`'s first decision is the 18:50 run of 2026-11-19 [S]
- source: `quantt/deploy/install_vm.py` @ `f1ba445`; `src/deploy/sleeves/cef_discount.py` @ `f1ba445`; `ops/sleeves/events_sleeves.json` @ `f1ba445`; `docs/RUNBOOK.md` @ `f1ba445` (8.6, 8.9, 8.11); the wrapper `vmrelease_1119.sh` is local and untracked
- supports: §1, §5
- status: current. The release check was this session's own read of the change list and one independent read-only review of the installed tag (E-2026-11-19-08); no multi-agent release check was run. C4's spec was not replayed on its own panel. The events book is installed next, with DRY_RUN=1, for one dry session before the team lead arms it

### E-2026-11-19-20 · Result: the unit-trust termination rule holds out of sample on 2026, a year its data never held
- kind: result
- era: ALPACA
- date: 2026-11-19
- figures:
  - the rule was committed at `96b05ff` (2026-11-18) before any 2026 price was fetched; the idea's data ended 2025-12-31; the measures were written in the script before any 2026 return was read [V]
  - sample: all 64 termination sessions from 2026-01-02 to 2026-11-12 in the committed calendar (112 trusts), 2,142 eligible fund-events on 228 funds, eligibility by the committed signal itself; Yahoo total returns to 2026-11-18; 38 of 272 calendar funds have no price and are excluded [V]
  - T+1..T+3 less control funds, one observation a session: mean +42.6bp, median +34.8bp, 86% of sessions positive, t 6.28; less PCEF +43.5bp (t 6.56); halves +50.2bp and +35.0bp; every month positive; in sample it was +33bp with 77% of sessions positive [V]
  - T+1 alone +33.3bp (t 8.41); the selling window T-9..T -32.6bp (t -1.44); the same trade a day late +12.6bp (t 1.99) [V]
  - not pre-specified, added after the first run: the same funds 20 sessions later -6.0bp (t -0.96); 30 sessions earlier +41.3bp in the mean and -3.4bp in the median (t 1.03); the trade without its ten best sessions +24.8bp [V]
  - the committed long-only books over the period, 151 of 225 sessions invested: all events +25.6%, big sales only +28.1%; raw T+1..T+3 was +59.1bp, so about 16bp of the raw return was the market [V]
- source: `results/ideas/uit_cef_flows/oos_2026.py` @ `a4a5ccb`; `results/ideas/2026-11-16_uit_cef_flows.md` @ `a4a5ccb`; `shadow/signals/uit_termination.py` @ `a4a5ccb`; `shadow/universes/uit_terminations_v1.csv` @ `a4a5ccb`
- supports: §4
- status: current. Gross; no closing quotes, so whether an order gets the termination session's closing price is not shown and remains the open condition; survivors only where Yahoo has no price; the control is the calendar's own funds outside their windows; one run, not independently reviewed. The id skips to -20 because the peer session takes -08 onward

### E-2026-11-20-10 · Release: the events book's runner is installed on the VM with every order switched off; its first plan is 212 orders on an account that holds $100,000, not the $1,000,000 ruled
- kind: release
- era: ALPACA
- date: 2026-11-20
- figures:
  - the team lead, 2026-11-20: "Do the next steps in full now". This session ran the install; nothing was armed [V]
  - under release-20261119-1 both books passed their first session: core 2026-11-19 PASS, 13 orders, 13 filled; C4 PASS, 2 orders, 2 filled (`ops.prod_state`, 11:37 New York on 2026-11-20) [V]
  - before the install: clone at release-20261119-1; no `quantt-events-*` unit; all eight listed shadow books had a decisions directory (1 file for `uit_termination`, dated 2026-11-19); no job running [V]
  - the VM had no `acl` package, and the installer refuses without `setfacl` and `getfacl`. `acl` 2.3.2-1build1.1 alone was installed at 11:42 New York (0 upgraded, 1 newly installed), with no book job running before or after and no change in the failed-unit list. `quantt/deploy/vm/bootstrap.sh` now lists it [V]
  - `install_events_vm.sh --vault <the VM's vault>` exited 0: a read-only ACL for user `quantt` on the eight decisions directories, tested both ways; `/home/quantt/quantt_state/events` (0700); one key service and a service and timer for plan, send and verify, every unit with DRY_RUN=1; no AUTO_ARMED [V]
  - the key service fetched `ALPACA_EVENTS_KEY_ID` and `ALPACA_EVENTS_SECRET_KEY` (names only are logged) and the plan read the account, so the keys authenticate [V]
  - the first scheduled PLAN, 11:45 New York, exit 6 PLANNED, the same `plan_sha` as the hand preview a minute earlier (59fdf5b27b6d): as-of 2026-11-19; all eight sleeves decided, none stale; 212 orders, 202 buys for $84,754 and 10 sells for $51,985, of which the IWM hedge is a short of 146 shares, $38,576; gross after $136,739, 1.37x the account's equity against a limit of 1.5x; send window 15:40 to 15:58 [V]
  - the account's equity as the runner read it: $100,000.00. The ruling of 2026-11-16 is a $1,000,000 account; the eight sleeves' quarter sizes sum to $170,500. The runner sized the plan inside its 1.5x limit with a scale factor of 1.0000, so nothing was cut, but the account is a tenth of the size ruled [V]
  - `cef_exdate_after` names two blocked short legs (EMO, SCD) and scales its long side by 0.8188 to stay balanced [V]
- source: `quantt/sleeves/deploy/install_events_vm.sh` @ `f1ba445`; `quantt/sleeves/run.py` @ `f1ba445`; `ops/sleeves/events_sleeves.json` @ `f1ba445`; `quantt/deploy/vm/bootstrap.sh` @ `f1ba445` (the `acl` line is in the commit that carries this entry); the wrapper `vmevents.sh` is local and untracked
- supports: §1, §5
- status: current. NOT ARMED: the 2026-11-20 session is the dry session the team lead asked for (SEND will stop on DRY_RUN, VERIFY at 17:35). Open for the team lead: reset the account to $1,000,000 or keep it at $100,000; then arming, which is theirs

### E-2026-11-20-11 · Result and rulings: C4's loss by fund, and its net modelled view (-$110.35 to 2026-11-19); the events account stays at $100,000; arming waits for the team lead's go on Monday's list
- kind: result
- era: ALPACA
- date: 2026-11-20
- figures:
  - the team lead's answers, by question prompt, 2026-11-20: the account "Keep $100,000 for now (Recommended)"; arming "Show me Monday's list, I say go (Recommended)"; alerts "Skip alerts for now (Recommended)" [V]
  - C4, from the VM's own `scores.csv` (13 rows, 2026-11-03 to 2026-11-19, the runner's per-symbol auction-marked P&L; no unmeasured symbol-day): -$600.99 = holding -$477.80 + fills against the auction -$123.19; the official end-of-day record is -$603.21 ($99,396.79 at the 2026-11-19 close) [V]
  - by the side held at the start of each day: long positions -$4,384.12, short positions +$3,841.35 [V]
  - by family: equity sector -$602.15, preferred -$202.53, covered call -$79.83, domestic equity +$132.22, multi-asset +$151.30. Seventeen funds have traded; the worst five lost $3,979.32 between them and the best five made $2,964.07 [V]
  - distributions paper never paid, the runner's `distribution_scores.csv`, 11 sessions to 2026-11-17: +$395.45; no row yet for 2026-11-18 and -19 [V]
  - borrow on C4's shorts at IBKR's indicative rates in the file stamped 2026-11-18 (0.43% to 1.58% a year on its ten shorted funds, 0.91% blended), on each plan's holdings and closes, as-of 2026-11-03 to 2026-11-19: -$28.00. Current rates applied backwards, as for the core (E-2026-11-18-28) [U]
  - C4's net modelled view to 2026-11-19: -$477.80 + $395.45 - $28.00 = -$110.35, against -$603.21 official [V]
- source: `quantt/session/score.py` @ `00b1cd1`; `quantt/session/dist_score.py` @ `00b1cd1`; `docs/SYSTEM.md` @ `00b1cd1` (section 5, the 2026-11-20 rows are in the commit that carries this entry); the VM's `quantt_state/c4` score files and plans, copied read-only on 2026-11-20; the attribution script is session scratch
- supports: §5
- status: current. Thirteen sessions: a description of what happened, not evidence about the strategy


### E-2026-11-20-12 · Incident: the events book's first evening check failed on a refused price read; the request now ends twenty minutes in the past
- kind: incident
- era: ALPACA
- date: 2026-11-20
- figures:
  - the dry session, read from the VM at 17:42 ET on 2026-11-20: PLAN exit 6 (planned) at 15:20; SEND exit 10 at 15:46, refused twice (DRY_RUN is 1; not armed), no order sent; VERIFY exit 1 at 17:35 on HTTP 403 "subscription does not permit querying recent SIP data" from `/v2/stocks/bars`. No AUTO_ARMED file; the account holds no position [V]
  - the cause, measured the same evening with the core account's keys, GET only, 17:43 ET, for the 2026-11-20 daily bar of IWM and EIM: `end=2026-11-20` refused (403); `end` 14 minutes ago refused (403); `end` 16 minutes ago served; no `end` served; the day before with `end` as its date served. A date-only `end` is the end of that day, inside the 15 minutes the plan withholds [V]
  - the bars served at 17:43 ET: IWM 256.61, EIM 8.76 [V]
  - the fix: a same-day read ends at the caller's clock minus 20 minutes; a read of a day that has not closed (before 16:20 ET) raises and makes no request; a past day is asked for by its date, as before. The core and C4 do not use this module [V]
  - measured again on 2026-11-22, GET only: for 2026-11-19 and 2026-11-20, eight symbols, `end` as the date, as 21:00Z and as 22:15Z returned the same close and volume; IWM 256.61 and EIM 8.76 for 2026-11-20 were unchanged from the 17:43 ET read [V]
  - not measured: whether a daily bar is ever revised after the evening it is first served, beyond those two symbols on that one day [U]
  - the same read showed the core and C4 collectors "failed" with exit 5 (incomplete) at 17:10 and 17:40 ET; the same exit is in the journal every evening checked (2026-11-10, -18, -19) and clears by the morning. Both books' sessions passed on 2026-11-20: 13 of 13 and 2 of 2 orders filled [V]
- source: `quantt/sleeves/prices.py` @ `17c7823` (the fix is in the commit that carries this entry); `quantt/sleeves/tests/test_run.py` @ `17c7823`; the VM's unit results and the events book's logs, read on 2026-11-20; the probe script is session scratch
- supports: §5
- status: current. The fix is not on the VM until the next release is installed

### E-2026-11-22-01 · Release: release-20261122-1 installed on the VM; the three books are as they were
- kind: release
- era: ALPACA
- date: 2026-11-22
- figures:
  - `release-20261122-1` is main at `70e1228`. Against `release-20261119-1`, outside documents and research, it changes `quantt/sleeves/prices.py`, `quantt/sleeves/run.py`, their tests, `quantt/deploy/vm/bootstrap.sh` and one README: the events book's same-day close read (E-2026-11-20-12). No file of the core's or C4's order path differs [V]
  - before tagging: the full suite and the document audit passed on the tested tree (`e9be427`, identical in content to `70e1228`); the diff was reviewed by a second reader, which found no defect and asked for three boundary tests, since added [V]
  - installed Sunday 2026-11-22, 11:42 to about 11:50 ET, market closed: timers stopped, core applied armed, C4 applied armed, report jobs re-applied, events units re-installed. Read back afterwards: clone at `release-20261122-1`; core and C4 DRY_RUN=0 with AUTO_ARMED present, as before; every events unit DRY_RUN=1 with no AUTO_ARMED; no job running [V]
  - not yet seen: the events book's VERIFY passing on the VM with the new read. Its first run is 17:35 ET on 2026-11-23 [U]
- source: `quantt/sleeves/prices.py` @ `70e1228`; `quantt/deploy/install_vm.py` @ `70e1228`; the VM's installer output and `ops/prod_state.py` @ `70e1228` read on 2026-11-22
- supports: §5
- status: current

### E-2026-11-22-02 · Ruling and incident: one fund-day with two official closes stalled C4's collector and the shadow marks; the later print stands when the daily bar agrees
- kind: ruling
- era: ALPACA
- date: 2026-11-22
- figures:
  - found on 2026-11-22 while reading the VM after the install: C4's collector had ended "incomplete" on every run for data day 2026-11-20 since that evening (86 lines in its data log against 21 or 22 for each of the five days before), and the shadow books' nightly job had failed three times (2026-11-20 18:54 and 20:54, 2026-11-21 07:24 ET). One cause: `AmbiguousAuctionPrint` for SCD [V]
  - Alpaca's auction record for SCD on 2026-11-20, GET only: NYSE condition M at 14.348 (1,400 shares, 16:00:02 ET) and again at 14.28 (300 shares, 16:10:00 ET); NYSE Arca M 14.348, Nasdaq M 14.18. The raw SIP daily bar closes at 14.28 [V]
  - what it did not touch: both live books passed on 2026-11-20 (13 of 13 and 2 of 2 orders filled); the shadow books' decisions for 2026-11-20 were written before the marks step failed; C4's order path reads no official-close file [V]
  - the team lead's answers, by question prompt, 2026-11-22: the close for that fund-day "$14.28, the later print (Recommended)"; the standing rule "Take the later print if the daily bar agrees" [V]
  - the rule in code, run on the real feed for 2026-11-20: SCD 14.28 with 14.348 named as superseded; USA, one print, 5.40, unchanged [V]
  - still to do when this entry was written: a release carrying the rule, and the same client change on the `shadow` branch, which keeps its own copy of the client [U]
- source: `quantt/broker/alpaca.py` @ `70e1228` (the rule is in the commit that carries this entry); `quantt/collect/collect.py` @ `70e1228`; `docs/SYSTEM.md` @ `70e1228` (section 5, the 2026-11-22 row is in the commit that carries this entry); the VM's `quantt_state/c4` data log and report and the shadow job's log, read on 2026-11-22
- supports: §5
- status: current

### E-2026-11-22-03 · Release: release-20261122-2 installed; C4's stuck data day, the shadow marks and the events book's Friday check all cleared
- kind: release
- era: ALPACA
- date: 2026-11-22
- figures:
  - `release-20261122-2` is main at `a624e13`. Against `release-20261122-1`, outside documents, it changes `quantt/broker/alpaca.py` (the two-prices rule of E-2026-11-22-02, inside `closing_auction_prints` and one new helper), `quantt/collect/collect.py` (the flag, carried across retries) and their tests. Before tagging: full suite and document audit passed on the tested tree; a second reader found no defect in the rule and one in the flag (lost on a retry), fixed with a test that fails without it [V]
  - installed Sunday 2026-11-22 from 12:42 ET, market closed. Read back: clone at `release-20261122-2`; core and C4 DRY_RUN=0 with AUTO_ARMED present, as before; every events unit DRY_RUN=1, no AUTO_ARMED [V]
  - C4's collector at 13:10 ET: "2026-11-20 DATA COMPLETE flags=63 gaps=0"; the day's report carries `two_primary_prints_later_used` for SCD, price 14.28, superseded 14.348 [V]
  - the shadow books' job, started once by hand at about 13:13 ET on the `shadow` branch at `a8e944e` (the other session's port of the client change): exit 0 at 13:17 ET, one new marked session for each book read back [V]
  - the events book's check for 2026-11-20, re-run by hand with `--date` (PLAN refuses while an earlier session is unbooked): "2026-11-20 PASS events no trade: send ended DRY; 0 symbol(s) filled, 0 booking(s); ledger booked to 2026-11-20" [V]
  - not yet seen: the events book's same-evening VERIFY on the new read (first run 17:35 ET, 2026-11-23); whether the daily bar already carries a later print by 16:45 to 17:30 ET the same evening (measured only two days after); a correction printed after 16:30 ET is outside the auction query's window and would not be seen [U]
  - units left failed on the VM: `quantt-reports-secret.service` only, by the team lead's choice of 2026-11-20 [V]
- source: `quantt/broker/alpaca.py` @ `a624e13`; `quantt/collect/collect.py` @ `a624e13`; `quantt/sleeves/run.py` @ `a624e13`; the VM's installer output, C4 data log and report, shadow log and events verify line, read on 2026-11-22
- supports: §5
- status: current

### E-2026-11-22-04 · Ruling: the standard for a clean platform and for real money is written; research carries on; real capital still waits for a broker
- kind: ruling
- era: ALPACA
- date: 2026-11-22
- figures:
  - the team lead, 2026-11-22: the infrastructure and the strategy "are very disorganized and not done at the proper standard we need it to be done, we cant deploy capital on this infrastructure" [V]
  - measured that day on the team lead's laptop: the main dev folder on branch `research-alpha-leakage`, 841 commits behind `origin/main`, 148 uncommitted files, with an untracked `CLAUDE.md` 179 changed lines from main's; 199 local branches, 102 remote branches and 143 worktrees, read with `git log`, `git status`, `git branch` and `git worktree list` [V]
  - measured on `origin/main` a624e13: 681 commits from 2026-10-22, 132 merge commits from 2026-11-01; Python lines by top folder `scripts` 127,532, `quantt` 47,121, `src` 11,632, `ops` 8,989, `shadow` 5,023; `docs/SYSTEM.md` §5 holds 41 ruling sections in 654 lines; CI runs the tests and `ops.doc_audit` only; read with `git log`, `git ls-tree` and `wc -l`, and from `.github/workflows/checks.yml` [V]
  - the team lead's answers, by question prompt: keep research as it is; everything on the desk; draft the standard first; save the dev folder and switch it to main after release-20261122-2 is installed; dashboard and logs for alerts; HALVE/KILL act on real money; a combined risk budget before real capital; agent review is enough; broker-neutral, the 2026-10-28 wait stands; types, coverage floor and import boundary in CI; a rehearsed recovery procedure; the daily acknowledgement not ruled ("we arnt deploying capital anytime soon"); then keep the draft's three proposals (monthly stop rehearsal, the 14-day branch rule, the go-live variant count), run the audit, push this standard as a pull request, switch the dev folder [V]
  - external sources read through a fetch agent: SEC 15c3-5, FINRA 15-09, EU 2017/589 (RTS 6), FIA 2024, the SEC's Knight Capital order, Bailey and López de Prado 2014, Bailey et al. 2014, AIMA's DDQ topics. None binds the desk [S]
  - what it does not change: no book, spec, gate or schedule; nothing on the VM [V]
- source: `docs/SYSTEM.md` @ `a624e13` and `.github/workflows/checks.yml` @ `a624e13` (the base measured); `docs/STANDARD.md`, `docs/REFERENCES.md` §12st and the §5 standard ruling are in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-22-05 · Result: the first audit against the standard's Part A finds 1 of 45 checks passing; the events book's orders can be changed by an unreviewed push to the `shadow` branch
- kind: result
- era: ALPACA
- date: 2026-11-22
- figures:
  - 45 checks audited (A5.3, the deferred daily acknowledgement, names no measurer): auditors' verdicts 1 PASS, 24 PARTIAL, 19 GAP, 1 NOT MEASURABLE; the five verifiers agreed with all 45 [S]
  - read strictly by `docs/STANDARD.md` §0.3, where a missing measurer counts as a gap: 1 PASS, 17 PARTIAL, 27 GAP [S]
  - the one PASS is A3.4: shadow books never transmit an order [S]
  - every verifier confirmed it: the events runner trades decision files written by the VM's shadow clone, which checks out the head of `shadow` before every run, and whose identity can read every secret in the vault [V]
  - read from the GitHub API at 16:20 ET: `shadow` is not protected; the two rulesets cover the default branch and the release, spec and provenance tags; six accounts can push, four of them admins; `origin/shadow` a8e944e is 4 commits ahead of `main` and 87 behind [V]
  - the events units are `DRY_RUN=1`, so the exposure is latent until the events book is armed [S]
  - 34 ranked work orders, carried as `docs/ROADMAP.md` Phase 7; 18 findings outside the checks [S]
  - method: five auditors and five verifiers, read-only, workflow run `wf_039a7231-1cb`, 732 tool calls; its first run stopped at the account's usage limit at 14:05 ET and was re-run from the start [V]
  - what it does not change: no book, spec, gate, schedule or GitHub setting; nothing on the VM [V]
- source: `docs/STANDARD.md` @ `877320c` (the standard audited); `shadow/deploy/nightly.sh` @ `07532f2`; `quantt/sleeves/inputs.py` @ `07532f2`; `shadow/deploy/install_shadow_vm.sh` @ `07532f2`; `results/ops/STANDARD_AUDIT_2026-11-22.md` and `results/ops/standard_audit_2026-11-22.json` are in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-23-01 · Ruling: after the first standard audit, `shadow` gets a ruleset, the events book arms on Monday as planned, and one rule says who runs a release
- kind: ruling
- era: ALPACA
- date: 2026-11-23
- figures:
  - none (a ruling). Through question prompts: "Protect it now" (a ruleset on `shadow` like main's); "Arm Monday, build them next" (work orders 7.2 to 7.5 come first in the build); "Agents release; arming is yours" (an agent in the team lead's session merges, tags and installs; arming, disarming and any order only on the team lead's go after the list is shown). The last supersedes the two 2026-11-19 rows on who runs releases and the 2026-11-02 standing authority still written in `docs/RUNBOOK.md` §8.6
  - the ruleset "shadow: only the team lead updates it" (update, deletion and non-fast-forward blocked; the team lead's account bypasses), created through the GitHub API and read back active at 11:48 ET. The repository then held three rulesets: `main`, the protected tags, and `shadow` [V]
- source: `docs/SYSTEM.md` @ `05ca236` (the 2026-11-19 rows superseded) and `results/ops/STANDARD_AUDIT_2026-11-22.md` @ `05ca236`; the §5 rows, `CLAUDE.md` order-path rule 1, `docs/RUNBOOK.md` §8.6 and `docs/TEAM.md` are in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-23-02 · Release: the events book is armed for its first session: send unit DRY_RUN=0 and the 2026-11-23 plan approved by its sha, on the team lead's go after the list was shown
- kind: release
- era: ALPACA
- date: 2026-11-23
- figures:
  - the plan for 2026-11-23 (as of 2026-11-20), `plan_sha` dff7c3783eaff1b2ea5237ae3ba40ddd3a973aa3e0c015df7e63f09854bf12ad: 219 orders, 210 buys of $89,643 and 9 sells of $56,956 estimated; gross after $146,599.30 against the limit of 1.5 × the $100,000.00 equity; eight sleeves decided, two holding nothing; window 15:40 to 15:58 ET [V]
  - before the go: the 12:00 ET preview printed the same sha with no "WOULD REFUSE AT SEND" line; the ledger held no shares in any of the eight sleeves (booked to 2026-11-20); no events or global halt file; the clone at `release-20261122-2`; the day's plan runs from 09:45 to 12:15 ET all printed the same sha [V]
  - the team lead's answer to the question naming the sha, the order count, the two sides' totals and the window: "Go" [V]
  - read back at 14:11 ET: `quantt-events-send` DRY_RUN=0, `quantt-events-plan` and `quantt-events-verify` DRY_RUN=1; `APPROVED` for that sha with 219 orders; AUTO_ARMED absent; the next send timer 15:41 ET; the 12:46 ET send run "before the send window ... nothing read, nothing written", exit 5 [V]
  - not yet seen: whether the send passes every gate in the window, what fills, and the 17:35 ET VERIFY. AUTO_ARMED waits for that VERIFY to pass and the team lead's word [U]
- source: `quantt/sleeves/run.py` @ `07532f2` (the approve and send rules); `quantt/sleeves/deploy/README.md` @ `07532f2` (the first-day checklist); the VM's events plan log, preview, ledger, unit environment and APPROVED file, read on 2026-11-23
- supports: §1, §5
- status: current

### E-2026-11-23-10 · Ruling: a public investor site served from the VM at event-driven.quantt.ca, built on Lucy's dashboard, with every active book's live paper results
- kind: ruling
- era: ALPACA
- date: 2026-11-23
- figures:
  - none (a ruling). Through question prompts and messages: the dashboard is a "website all can see", served from the VM, at `event-driven.quantt.ca`; Lucy's PR #62 is built on in a new PR with her commits kept; snapshots stay on the VM ("VM only"), superseding 2026-10-26's repository route; an agent installs it after the release check
  - the content asked for: team overview with full names, bios and LinkedIn; the in-depth deck "with the same tweaks that were applied to make Event Driven Trading"; "our library (all literary sources)"; "anything any R&D website would have"; "connected to our live P&L and live updates ... presentable to VC / investors"; contact `simon.jarvis@queensu.ca`; quantt.ca is "just inspiration" [V]
  - the site's statistics reproduce `ops/orient.py` PNL on the VM's records of 2026-11-20 to the cent: core cumulative -$632.20, high-water $101,474.24 (2026-10-12), drawdown -2.08%, volatility 6.97%; C4 +$1,958.13, volatility 9.07%; the two accounts combined $201,325.93, +$1,325.95 on $199,999.98 over 38 common sessions [V]
- source: `dashboard/README.md` @ `87728af` (the 2026-10-26 repository route it supersedes) and `ops/orient.py` @ `87728af` (the PNL figures it reproduces); `dashboard/` (export.py, metrics.py, build.py, site.py), `dashboard/tests/test_metrics.py` (parity with `ops.orient.official_pnl`), `docs/SYSTEM.md` §5 "the public site" and `docs/RUNBOOK.md` §8.13 are in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-23-03 · Incident: the events book's first armed send hit Alpaca's rate limit; 46 of 219 orders went, 173 were answered HTTP 429, and the book holds a partial, unhedged position
- kind: incident
- era: ALPACA
- date: 2026-11-23
- figures:
  - the send at 15:41 ET on plan dff7c378…12ad: 46 orders sent and all 46 fully filled; 173 answered HTTP 429 "rate limit exceeded" ("too many requests" for the last few) and booked as rejections, the index hedge among them; exit 20 FAIL [V]
  - the later send runs that day refused (exit 11): a set had already started, the projected gross was over 1.5 × live equity, and positions had moved since the plan. Read at 15:54 ET by a second session as well: gross held $22,664.71, live equity $99,958.06 [V]
  - cause: before its first order the send read every symbol's asset flags (219 GETs), then sent each order as a clock read and a POST, none of it paced, against Alpaca's "200 requests per minute, per account" [S: the support page cited in `quantt/broker/alpaca.py`]. GETs retry on 429 in the client; a POST never does, by design (the doubled-book rule). The core and C4 send a few dozen orders and never reached the limit [V]
  - what it did not do: no order was doubled, nothing was sent outside the window, and the runner refused every retry that day [V]
  - the team lead, through question prompts: "Disarm until the fix ships" (send unit DRY_RUN=1 again at 16:57 ET, read back); "Hold them" (the 46 positions); "Build it now and release" [V]
  - the fix: the client paces the trading host (a burst of 40, then 150 a minute), and a 429 to an order is waited out and the id read before any resend; tests that fail against the old code [V]
- source: `quantt/session/run.py` @ `87728af` (`_transmit`: a 4xx is a rejection, never retried); `quantt/broker/alpaca.py` @ `87728af` (`GET_BACKOFF_S` and the rate-limit note); the VM's events send log and unit environment, read on 2026-11-23; the fix is in the commit that carries this entry
- supports: §1, §5
- status: current

### E-2026-11-23-04 · Ruling: the branch clean-up goes ahead with the caches kept; AUTO_ARMED for the events book only on a passing VERIFY
- kind: ruling
- era: ALPACA
- date: 2026-11-23
- figures:
  - none (a ruling). "Go, keep the caches" on the list of 116 worktrees, 147 local and 88 GitHub branches, each fully merged into `main`; "Yes, if VERIFY passes" for AUTO_ARMED (not created: the session's send failed, E-2026-11-23-03)
  - applied at 15:52 to 15:53 ET with no skips: 116 worktrees removed after their ignored files (research caches and one-off wrappers, 35 GB) were moved to a folder outside the repository; 147 local and 88 GitHub branches deleted; 185 `archive/*` tags kept on the laptop and not pushed. The inventory afterwards: 55 local branches (10 with no reason, each holding commits not on main), 28 worktrees, 16 GitHub branches [V]
- source: `ops/branch_inventory.py` @ `87728af` (the inventory, read before and after); `docs/STANDARD.md` @ `87728af` (A1.2)
- supports: §5
- status: current

### E-2026-11-23-11 · Release: release-20261123-1, the public site, installed in its own clone on the VM; the trading clone and every book's arming unchanged
- kind: release
- era: ALPACA
- date: 2026-11-23
- figures:
  - release check on 83a7b14: GO with conditions. pytest exit 0, doc_audit 0 DRIFT in 95 checks, orient exit 0, preview exit 4 (nothing sent); quant-reviewer and execution-engineer found no defect on the order path (in quantt/ only install_vm.py's SITE_UNIT_FILES and its test changed). Its follow-ups (the .gitignore the merge had indented, the installer's unguarded daemon-reload, one empty change_usd failing the whole build, the combined figure's start date) are fixed in PR #101 [V]
  - merged as exactly 83a7b14 through PR #102 (`--admin --match-head-commit`), origin/main's tree equal to 83a7b14; tagged release-20261123-1 on merge commit 1f93b56 [V]
  - VM, 19:05 to 19:07 ET: no quantt job queued or running and NeedDaemonReload=no on all 39 quantt unit files before the install; caddy 2.6.2 from Ubuntu's archive; the site clone at release-20261123-1; first build published; quantt-site.timer active (every 30 minutes at :20 and :50) [V]
  - read back after: the trading clone still at release-20261122-2, cef DRY_RUN=0 and AUTO_ARMED present, as before [V]
  - live over HTTPS on the VM's own name: every page 200, an unknown path 404, the Content-Security-Policy, HSTS and frame headers sent; the performance page built 19:06 ET shows the 2026-11-23 after-close reading beside the official history to 2026-11-20 [V]
- source: `dashboard/deploy/install_site_vm.sh` @ `83a7b14`; `docs/RUNBOOK.md` §8.13 @ `83a7b14`; the release check's verdict (workflow run wf_22fe6f40-95c) and the install's read-back, 2026-11-23
- supports: §5
- status: current

### E-2026-11-23-12 · Ruling: the public site without the slideshow, the team first, quantt.ca's photographs and logo, served at event-driven.quantt.ca by a read-only Cloudflare Worker
- kind: ruling
- era: ALPACA
- date: 2026-11-23
- figures:
  - none (a ruling). Through messages after release-20261123-1: the address is `event-driven.quantt.ca`, "running on a cloudflare worker called quantt-event-driven", which "deploys [our] repository ... all needs to be run on main"; "use the same pictures on the quant site"; "include the quant logo too"; "a higher resolution image in the back"; it looked "not professionally made and ... not well organized"; "take out the slideshow and make the team the first thing"; on the team page "the 2nd photo (the one in the middle) ... should be taken out"; the footer "is organized bad" [V]
  - done: the strategy page, its 63 slide images and the deck PDF removed; Team first in the menu and the overview's first section; quantt.ca's photographs at 2400 px and its logo; serif headlines over Inter on a 12-column grid; the footer in three columns. The Worker (PR #103, merged as 3247a23) is a read-only caching proxy to the VM: GET and HEAD only, the target host fixed to the variable ORIGIN, off-site redirects refused, a 503 page when the VM is down; its config sits in `dashboard/` so the build installs no Python [V]
  - the release check's review findings fixed: the overview's combined P&L names the books it sums and is withheld when a book is unmeasured; the site installer's guard runs before caddy's package can reload systemd, refuses on a unit file changed on disk (NeedDaemonReload) and on a failed systemctl query, and its two `enable` calls pass `--no-reload` [V]
  - not yet done: Cloudflare's build of `main` has failed on every commit so far (6d2786ba at the repository root; 3247a23 not yet read), so `event-driven.quantt.ca` does not serve the site yet [V]
- source: `dashboard/worker/index.js` @ `3247a23` and `dashboard/wrangler.jsonc` @ `3247a23` (the Worker, PR #103); `dashboard/site.py` @ `3858e67` (the redesign, no slideshow, the team first); the combined figure's label, the installer's guard and `docs/SYSTEM.md` §5 "the public site" are in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-23-05 · Release: release-20261123-2 paces the Alpaca trading host and waits out a 429 before any resend; installed for the core and C4 armed, and the events book armed with AUTO_ARMED
- kind: release
- era: ALPACA
- date: 2026-11-23
- figures:
  - `release-20261123-2` is df7f6fc (PR #100, merged to main as b1f2279), and it contains release-20261123-1. Three release checks: NO-GO on 81e1071 (a 429 path left an order with no terminal event, so the events VERIFY would not book the day); NO-GO on 4cf8431 (it did not contain release-20261123-1); NO-GO on 93021c8 (the fourth 429 was not looked up; a banner test read the real repository); GO on df7f6fc: pytest exit 0 (5077 passed, 2 skipped), doc_audit 0 DRIFT, two reviewers with no order-path defect [V]
  - the replay through the tagged code (RUNBOOK §8.6 step 2): 97 runs replayed, none refused now [V]
  - that evening's events VERIFY for 2026-11-23: FAIL (the partial send), no problems, ledger booked to 2026-11-23, 46 symbols filled, 63 bookings [V]
  - installed 21:41 to 21:42 ET: the core and C4 `--armed` (DRY_RUN=0 and AUTO_ARMED as before, timers read back active); the events installer re-run with `--keep-state`; then, on "AUTO_ARMED now", the events send unit DRY_RUN=0 and AUTO_ARMED created; no HALT. ops.prod_state read back: the VM ARMED at release-20261123-2 for the core and C4; the site clone left at release-20261123-1 [V]
  - not yet seen: the events book's first paced send (2026-11-24, 15:40 to 15:58 ET) [U]
  - follow-ups from the release check, not blockers: about 226 paced asset reads now come before gate 4, so a set above about 290 orders is refused even at 15:41, and the 15:46 retry holds about 201 (fails closed, nothing sent in part); a non-429 4xx on a resend is booked `rejected` where the safer reading is ambiguous; from the release check of df7f6fc [S]
- source: `quantt/broker/alpaca.py` @ `df7f6fc`; `quantt/session/run.py` @ `df7f6fc`; `quantt/sleeves/run.py` @ `df7f6fc`; the VM's installer output, events VERIFY and `ops.prod_state`, read on 2026-11-23
- supports: §1, §5
- status: current

### E-2026-11-23-13 · Release, incident and ruling: release-20261123-3 put the redesigned site on the VM; the event book's rejected order ids were on the public performance page from 19:06 ET; the site shows aggregates only from the next release
- kind: release
- era: ALPACA
- date: 2026-11-23
- figures:
  - release-20261123-3 on 4ecc202, the merge of PR #101 (`--admin --match-head-commit` 76c477a; the merge's tree equal to 76c477a's). Since release-20261123-2 it changes only `dashboard/`, documents and this log [V]
  - VM, 22:35 ET: the site clone moved from release-20261123-1 to release-20261123-3 and is clean; quantt-site.service built and published (`current` -> builds/20261124T033501756816Z); the timer active (every 30 minutes at :20 and :50); caddy active. The units' text is unchanged, so the installer was not re-run [V]
  - read back after: the trading clone still at release-20261123-2; cef and c4 AUTO_ARMED present; cef DRY_RUN=0 [V]
  - the release check (workflow run wf_f8af21e8-8df) returned GO on 76c477a, the same tree as the tag. The tag was pushed at 22:34 ET, before the verdict, on the team lead's "we need it deployed"; the verdict covers it [V]
  - Cloudflare's Workers Builds of 4ecc202 failed, as on every commit before it, so `event-driven.quantt.ca` still answers with Cloudflare's default page. The site owner is fixing the build settings [V]
  - incident: the event book's 2026-11-23 verify (written 17:35 ET) lists its 173 rejected orders by client order id in `reason` and `problems`; every site build from the first (19:06 ET) carried that list on the performance page, at the VM's own address only. `dashboard/README.md` §2 forbids order ids on the site. The exporter now withholds them ("order ids withheld") and `find_private` refuses a snapshot that still carries one; on a copy of tonight's records the built pages hold none [V]
  - the release check's three findings, fixed in the same change: the overview's combined P&L states its window (29 Sep to 20 Nov 2026), a new book is dated by its first send (the oldest STARTED record: 23 Nov 2026 for the event book; 20 Nov was a dry run), and each Sharpe ratio shows its session count [V]
  - correction to E-2026-11-23-11: its "the combined figure's start date" was fixed on the performance page in PR #101; the overview's headline figure gains it here [V]
  - ruling, through a question prompt after the other session counted order ids in nearly every per-day record of every book: the public site shows **"Aggregates only"**. Snapshot 0.3 reduces each session to counts and dollar exposure and copies no symbol, share count, order line or note text; `find_private` refuses a snapshot with a per-name key. On a copy of tonight's records, none of the 219 symbols held or traded and no order id appears on any built page [V]
- source: `dashboard/deploy/install_site_vm.sh` @ `4ecc202`; `dashboard/export.py` @ `4ecc202` (`scrub`, which kept order ids); the VM's site journal, `/srv/quantt-site` and the event book's verify.json, read 2026-11-23 22:35 to 22:50 ET; the withholding, the privacy pattern and the three fixes are in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-23-14 · Release: release-20261123-4, the public site in aggregates only, on the VM; event-driven.quantt.ca serving through the Worker
- kind: release
- era: ALPACA
- date: 2026-11-23
- figures:
  - release check (workflow run wf_87329e9e-eca) GO on ed56ade: pytest 5097 passed and 2 skipped, doc_audit 0 DRIFT, orient exit 0 with prod the VM and core and C4 armed, preview exit 4; no order-path file in the range [V]
  - merged as 4c75294 (PR #105, `--admin --match-head-commit` ed56ade; the merge's tree equal to ed56ade's) and tagged release-20261123-4 after the verdict [V]
  - VM, 23:29 ET: the site clone moved from release-20261123-3 to release-20261123-4 and is clean; the build published; no client order id on any page. The trading clone still at release-20261123-2; cef and c4 AUTO_ARMED present [V]
  - `event-driven.quantt.ca` answers 200 on every page through the Worker since Cloudflare's build of 4ecc202 succeeded (04:06 UTC); an unknown path is answered `no-store` by the Worker. Every cached answer reached browsers as `max-age=14400`, the zone's Browser Cache TTL, so a returning visitor could see figures four hours old; the Worker now sends `no-cache` with 304 revalidation (the commit that carries this entry) [V]
  - the review's site findings fixed in the same commit: exposure is not measured when any position has no close (it was summed over the priced names only); a core FAIL's unmeasured items are counted as notes; the two exposure rows are labelled by their source [V]
  - ruled after release-20261123-4 and done in the same commit: quantt.ca's headshots, team cards with name and LinkedIn only, Toronto night photographs on the team and library pages (Andrew Gosine, CC0; Ken Lund, CC BY-SA 2.0; credited), a GitHub link in the header, and the performance page rebuilt as a tearsheet (team lead, 2026-11-23 and 2026-11-24) [V]
- source: `dashboard/export.py` @ `4c75294` (exposure over the priced names, notes from `problems` only); `dashboard/worker/index.js` @ `4c75294` (the edge lifetime sent to browsers); the VM's site journal and `/srv/quantt-site`, read 2026-11-23 23:29 ET; response headers of `event-driven.quantt.ca`, read 2026-11-24 04:25 UTC; the fixes, the photographs and the tearsheet are in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-24-01 · Release: release-20261123-5 put the performance tearsheet, the headshots and the Worker's browser caching live; the edge then paired new pages with the previous stylesheet for up to an hour
- kind: release
- era: ALPACA
- date: 2026-11-24
- figures:
  - PR #106 merged as b5c9913 (`--admin --match-head-commit` b8ee07e; the merge's tree equal to b8ee07e's) and tagged release-20261123-5 at 23:59 ET on the team lead's "all the new made stuff", before the release check's last reviewer returned. Its pytest, doc_audit, orient and preview steps had passed and its execution review found no order-path change [V]
  - VM: the site clone moved from release-20261123-4 to release-20261123-5 and is clean; the build published; no client order id on any page; the trading clone still at release-20261123-2, cef and c4 AUTO_ARMED present [V]
  - Cloudflare's build of b5c9913 succeeded; every page answered `cache-control: no-cache` and a conditional request for the stylesheet answered 304 [V]
  - the edge still held the previous stylesheet (age 2469 s of its 3600 s), so for up to an hour the new pages were served with the old styles. The stylesheet and script URLs now carry their content hash (`?v=`, dashboard/layout.py `asset_version`) and the Worker keys /static/ on it, so a page always gets its own release's styles (the commit that carries this entry) [V]
  - ruled after the release and done in the same commit: daytime photographs of Toronto under cloud on the team and library pages (Dlsz, CC BY-SA 4.0; Gregory Karastergios, CC0; credited), and the research and library pages reorganised (team lead, 2026-11-24) [V]
- source: `dashboard/layout.py` @ `b5c9913` (fixed stylesheet URL); `dashboard/worker/index.js` @ `b5c9913` (cache key without `v`); response headers of `event-driven.quantt.ca`, read 2026-11-24 00:02 ET; the VM's site journal, read 2026-11-23 23:59 ET; the versioning, the photographs and the two pages are in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-24-02 · Release and ruling: release-20261124-1 on the VM; the performance page becomes one portfolio line over the books, each from its first traded session, with the event book included
- kind: release
- era: ALPACA
- date: 2026-11-24
- figures:
  - release-20261124-1 on 89c145d (PR #107 merged `--admin --match-head-commit` b803b9e, trees equal), after the release check's pytest, doc_audit, orient and preview steps passed on b803b9e; the VM's site clone moved from release-20261123-5 and the build published; `event-driven.quantt.ca` served the page with the stylesheet of the same content hash. The trading clone still at release-20261123-2, cef and c4 AUTO_ARMED present [V]
  - the release check of b8ee07e (wf_df1960fd-7e8) cleared the code; its quant review found C4's statistics counted 25 sessions in which the account held nothing (in the VM's STARTED records, read 2026-11-24, C4's first is 2026-11-04; its account was funded 2026-09-29) [V]
  - ruled, through messages: one portfolio line that splits into the books, the analysis an institutional investor reads, the event book included automatically, the page kept current [V]
  - on the VM's records read 2026-11-24 00:30 ET: portfolio from 29 Sep 2026, 39 sessions, +0.66%, P&L +$1,325.93 (cef −$632.20 + C4 +$1,958.13, the figures E-2026-11-23-10 reproduced from orient), annualised volatility 7.90%, Sharpe 0.57, Sortino 0.82, maximum drawdown −2.65%, one-day 95% VaR 0.77% and expected shortfall 1.01%; C4 13 sessions from 4 Nov 2026, so its ratios are not shown; the event book joins on 23 Nov 2026 from its after-close reading [V]
- source: `dashboard/metrics.py` @ `89c145d` (statistics over each account's funded rows); the VM's `quantt_state/{cef,c4,events}` STARTED, eod_equity.csv and verify.json, read 2026-11-24; `dashboard/build.py` `portfolio`, `metrics.composite` and `metrics.profile` are in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-24-03 · Release: release-20261124-2 put the portfolio page live; the event book's record now refuses a skipped session, and an unreadable book is named and left out instead of hiding the portfolio
- kind: release
- era: ALPACA
- date: 2026-11-24
- figures:
  - release check (workflow run wf_56e06952-0a7) on 904bd35: pytest 5113 passed and 2 skipped, doc_audit 0 DRIFT, orient exit 0, preview exit 4; no order-path file in the range. Merged as 0c03c96 (PR #108, trees equal) and tagged release-20261124-2 after its checks passed, before its reviewers returned; their verdict, GO, covers it [V]
  - VM, 01:4x ET: the site clone moved from release-20261124-1 to release-20261124-2 and is clean; the build published; the performance page reads "Return since 29 Sep 2026 (+$1,326)"; no client order id on any page. Cloudflare's build of 0c03c96 succeeded and `event-driven.quantt.ca` serves the same page and stylesheet hash. The trading clone still at release-20261123-2; cef and c4 AUTO_ARMED present [V]
  - the reviewers' site findings, fixed in the commit that carries this entry: a traded session without verify.json was skipped, understating the event book's P&L (the reviewer's probe: +$500 shown for +$1,500); an unreadable record withheld the whole portfolio until repaired by hand; metrics.py still said every figure matched orient. The record now refuses a missing reading or a `last_equity` that is not the previous reading's equity, the newest unverified sessions count as pending, and an unreadable book is left out and named above the figures and in the overview's label [V]
  - outside the site, from the same check, for the team lead: the cef plan for 2026-11-24 carries a pre-flight WARNING (worst-day shock $1,220.47); a worthless_removal corporate action with no symbol (3d567376-eccf-458b-977d-49469e51f0f7) is read as touching every held cef name, BLOCKING in report mode, so nothing is refused; the newest Alpaca probe snapshot is 40 days old (from the release check's preview and orient, not re-read here) [S]
- source: `dashboard/export.py` @ `0c03c96` (`after_close` read only the days with a verify.json); `dashboard/build.py` @ `0c03c96` (`portfolio_section` withheld on any unreadable book); the VM's site journal and `/srv/quantt-site`, read 2026-11-24 01:4x ET; the fixes are in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-24-04 · Release: release-20261124-3 on the VM; the event book's sessions are now dated by their plans, and every portfolio figure names a book left out
- kind: release
- era: ALPACA
- date: 2026-11-24
- figures:
  - release-20261124-3 on 6a50403 (PR #109 merged `--admin --match-head-commit` 455eff4, trees equal), tagged after the release check's pytest, doc_audit, orient and preview steps passed on 455eff4; its reviewers then returned GO (workflow run wf_c19c6252-09b). The VM's site clone moved to it and the build published; Cloudflare's build of 6a50403 succeeded. The trading clone still at release-20261123-2, cef and c4 AUTO_ARMED present [V]
  - the reviewers' site findings, fixed in the commit that carries this entry: the missing-session check compared equity to $1 or 0.1%, which on a $1M account lets a $1,000 session through; it now requires each session's plan to have been decided on the previous reading's session (plan.json `asof`). The overview's P&L figure and chart now name a book left out, and a page with every book unreadable says why instead of "no traded session yet" [V]
  - on the VM's event records (2026-11-20, 2026-11-23): plan `asof` 2026-11-19 and 2026-11-20; the record reads 100,000.00 then 99,970.14 (−$29.86), as before [V]
- source: `dashboard/export.py` @ `6a50403` (the equity tolerance); `dashboard/site.py` @ `6a50403`; the VM's `quantt_state/events/<day>/plan.json` and verify.json, read 2026-11-24; the fixes are in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-24-05 · Release: release-20261124-4 on the VM; the event book's P&L on the site becomes the move between its readings, so after-hours drift can no longer distort it
- kind: release
- era: ALPACA
- date: 2026-11-24
- figures:
  - release-20261124-4 on 591f4db (PR #110 merged `--admin --match-head-commit` 0a4852b, trees equal), tagged after the release check's pytest, doc_audit, orient and preview steps passed on 0a4852b; its reviewers then returned GO (workflow run wf_48248878-36b). The VM's site clone moved to it and the build published; Cloudflare's build of 591f4db succeeded; the performance page reads "Return since 29 Sep 2026 (+$1,326)" on both addresses. The trading clone still at release-20261123-2, cef and c4 AUTO_ARMED present [V]
  - the quant review's finding, fixed in the commit that carries this entry: the event book's record summed Alpaca's `change_usd`, which runs from the official close, while its readings are taken after the close, so the drift between a reading and the next close fell out of the sum (the reviewer's probe: +$700 shown, +$200 moved). Each session's P&L is now the change between consecutive readings, which sums to the account's move exactly; the plan-date check still catches a missing session. On the VM's records the one traded session reads −$29.86, as before [V]
  - the all-unreadable page no longer says "the portfolio below is the other books only" over no portfolio [V]
- source: `dashboard/export.py` @ `591f4db` (`after_close` took `change_usd` from verify); the VM's site journal and `/srv/quantt-site`, read 2026-11-24 ~03:00 ET; the fix is in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-24-06 · Release: release-20261124-5 on the VM; with the 2026-11-23 official figures the portfolio read +0.06% time-weighted beside −$472, so the page names the return time-weighted and shows the P&L apart
- kind: release
- era: ALPACA
- date: 2026-11-24
- figures:
  - release-20261124-5 on 5c947c4 (PR #111 merged `--admin --match-head-commit` 596ba7f, trees equal), tagged after the release check's pytest, doc_audit, orient and preview steps passed on 596ba7f. The VM's site clone moved to it and the build published. The trading clone still at release-20261123-2, cef and c4 AUTO_ARMED present [V]
  - the 2026-11-23 official end-of-day rows had landed: cef +$485.25 (equity $99,853.05), C4 −$2,253.57 ($99,704.56); the event book's after-close reading −$29.86. The session's −$1,798.18 takes the portfolio's P&L from +$1,325.93 to −$472.25; by book cef −$146.95, C4 −$295.44, events −$29.86, which the page's contribution table shows [V]
  - the portfolio's time-weighted return over the same 40 sessions is +0.06%: its gains came while one book traded and most of its losses on 2026-11-23, when three did, on about three times the capital. Both figures are right; the page showed them as "+0.06% (−$472)". The commit that carries this entry names the return time-weighted everywhere, shows the P&L as its own figure, and explains the difference in the method note [V]
- source: the VM's `quantt_state/{cef,c4}/eod_equity.csv` and the page built by release-20261124-5, read 2026-11-24 ~04:00 ET; `dashboard/build.py` @ `5c947c4` (the combined label); the labelling is in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-24-07 · Release: release-20261124-6 on the VM; the event book's session P&L now reads the same in its tile, its row and its record
- kind: release
- era: ALPACA
- date: 2026-11-24
- figures:
  - release-20261124-6 on 13eb3a0 (PR #112 merged `--admin --match-head-commit` a62bce4, trees equal), tagged after the release check's pytest, doc_audit, orient and preview steps passed on a62bce4. The VM's site clone moved to it; the build published; Cloudflare's build of 13eb3a0 succeeded; both addresses read "+0.06% Time-weighted return since 29 Sep 2026" and "−$472 P&L since 29 Sep 2026" as separate figures. The trading clone still at release-20261123-2, cef and c4 AUTO_ARMED present [V]
  - the quant review of 596ba7f (workflow run wf_0e0e23f4-c81) found the event book's "That session" tile and its Latest session row still taking Alpaca's `change_usd` while its record takes the move between readings; they would first disagree at its second verified session, 2026-11-24. Fixed in the commit that carries this entry: one function gives a session's P&L to every figure (official, else the after-close record, else the reading). Its EXPORTER_SPEC row and the metrics docstring now say how the after-close record's change is made; the empty-portfolio message names every book and why [V]
- source: `dashboard/build.py` @ `13eb3a0` (`book_section` and `latest_sessions` read `equity_snapshot.change_usd`); the VM's site journal and both addresses, read 2026-11-24 ~04:40 ET; the fix is in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-24-08 · Release: release-20261124-7 on the VM; the release checks of release-20261124-6 and -7 returned GO, and the event book's tile caption is corrected
- kind: release
- era: ALPACA
- date: 2026-11-24
- figures:
  - release-20261124-7 on a4385db (PR #113 merged `--admin --match-head-commit` 8daa34a, trees equal), tagged after its release check's pytest, doc_audit, orient and preview steps passed; its reviewers then returned GO (workflow run wf_989a2eb5-e7d). The VM's site clone moved to it and the build published; Cloudflare's build of a4385db succeeded. The trading clone still at release-20261123-2, cef and c4 AUTO_ARMED present [V]
  - the release check of a62bce4, the content of release-20261124-6 (workflow run wf_f5f1f7ac-3d5), passed every check and found nothing in review [V]
  - the one finding on 8daa34a, fixed in the commit that carries this entry: the event book's tile still carried the caption "account snapshot at verify (not the P&L of record)" under a session P&L now taken from the after-close record. The caption now says what each figure is [V]
- source: `dashboard/build.py` @ `a4385db` (`book_section` printed `equity_snapshot.kind`); the VM's site journal, read 2026-11-24 ~05:00 ET; the caption is in the commit that carries this entry
- supports: §5
- status: current

### E-2026-11-24-10 · The team's data/ copy in R2 for the analysts is merged (pull request #3): the team lead confirmed the analysts still need it
- kind: ruling
- era: ALPACA
- date: 2026-11-24
- figures:
  - none (the team lead's answer by question prompt, "Yes, update it", to whether the analysts still need the R2 copy; no figure)
- source: `scripts/data/team_data.py` @ `56c2dd0`; `docs/SYSTEM.md` §5 "Sharing the desk's data" @ `b5c9913` (the row is added by the commit that carries this entry)
- supports: §5
- status: current. Ruled 2026-10-26, unmerged until now. On the merge, boto3 moved from requirements.txt to requirements-research.txt so the VM's trading venv is not rebuilt for a research package. The copy is as fresh as the team lead's last push (`team_data.py status` says when)
