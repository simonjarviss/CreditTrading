# A1 re-open: the live book's shorts inside share-issuance programme windows — fit period only, 2026-10-28

**Zero trials. No counter, spec or `docs/RESEARCH_STATE.md` edited. The 2023 holdout is not opened. It decides nothing.**
**Reproducer** (about 90 s; no network, no R2, no credential; the caches are A1's own), from this branch's tree:
`W="$(git rev-parse --path-format=absolute --git-common-dir)/../.claude/worktrees"` then
`python3 -m scripts.research.reopen_a1.book_windows --edgar-cache "$W/ss-cef-events/results/events/_cache_edgar" --crsp-cache "$W"/{research-ss-expansion,ss-cef-events,research-cef-events,ss-e1-hedge,trial-events-e1,research-edgar}/results/events/_cache_crsp`
It writes `results/research/reopen_a1/reopen_a1_2026-10-28.json` (with the commit it ran at and whether the tree was clean). Tests: `python3 -m pytest scripts/research/tests/test_reopen_a1.py scripts/research/tests/test_inference.py`.
Branch `research-reopen-a1`, cut from `origin/main` at 79a2745. Approved by the team lead on 2026-10-28 (`docs/SYSTEM.md` §5,
row "Re-opens (3) and (4)"). It is item 1 of §7 of `results/events/A1_CEF_ISSUANCE_GATE_2026-10-20.md`, built on the pattern of
`scripts/events/g6_corporate_action_shorts.py`. **[V]** = from that command's JSON; **[S]** = read in the cited document.

## 0. The answer

**No: on the fit period the book's shorts did not lose money inside programme windows. They earned more there than
elsewhere, and blocking them would have cost the book about 0.22 of gross Sharpe.** The difference in means is
INCONCLUSIVE on the declared hurdle, not ABSENT. Its interval lies almost entirely on the side opposite to the
hypothesis. The windows are seven, five of them PIMCO's, and one (PTY 2018–20) carries 68% of the in-window P&L.

**1. P&L per short name-day, bp of book, SEs clustered by decision date** [V]. The estimate is outside − inside, so
positive means the in-window shorts earn **less**, the direction asked about.

| | inside: mean (SE) | n · dates | outside: mean (SE) | n · dates | estimate (SE), t | `read_result`, n_trials 1 |
|---|---|---|---|---|---|---|
| **total returns (H15)** | **+0.905 (0.536)** | 1,677 · 937 | −0.030 (0.307) | 7,596 · 2,398 | **−0.935 (0.552), −1.70** | **INCONCLUSIVE**: [−2.02, +0.15], hurdle 0.046, STRADDLES; power at the hurdle 0.05 |
| paper view (price) | +1.275 (0.550) | same | +0.646 (0.314) | same | −0.629 (0.567), −1.11 | INCONCLUSIVE: [−1.74, +0.48] |
| second method, within date (d_t on 937 dates; Newey–West t) | | | | | total −0.29 (t −0.27); paper −0.09 (t −0.08) | |
| independent prices: CRSP `ret` / `retx` | +0.905 / +1.275 | same | −0.030 / +0.626 | same | −0.934 / −0.649 | INCONCLUSIVE both; same sign as the panel |
| per unit of short weight (total) | +2.88 (4.07) | | −2.17 (2.04) | | −5.05 (3.69), −1.37 | INCONCLUSIVE |

- **The reading.** The question's direction is not found. The point estimate has the opposite sign: the in-window
  shorts earned 0.9bp a name-day more than the others. The interval's upper end, +0.15bp, is just above the hurdle
  of 0.046bp, so the reading is INCONCLUSIVE rather than ABSENT. At that hurdle the test's power is 0.05; it could
  never have found an effect that small (§1).
- **Most of the gap is which dates the windows fall on.** Compared within each date, the difference shrinks to
  −0.29bp (NW t −0.27). The windows sit only in 2016–17 and 2018–22 (§2).
- **The in-window shorts made money as a series** [V]: +159.5bp a year of book on total returns, +224.7 on paper.
  The daily mean is +0.63bp (NW t 1.49) on total and +0.89bp (t 1.99) on paper, over 2,398 sessions. Six of the
  seven windows are positive.

**2. The block counterfactual.** Where the book would be short a name inside its window, it holds the name flat
(G6's filter, fixed before any return). Window: 2013-06-25 (the first held session) to 2022-12-30; T 2,398 [V].

| total returns | gross SR | net 5 / 15 / 30bp | ann. return | turn/yr |
|---|---|---|---|---|
| book | **0.955** | 0.852 / 0.645 / 0.334 | 6.21% | 13.47 |
| block | **0.735** | 0.636 / 0.438 / 0.142 | 4.62% | 12.42 |
| **change** | **−0.220** | −0.216 / −0.206 / −0.192 | −1.60pp | **−1.05** |
| paper view: book → block | 0.959 → 0.647 (**−0.313**) | 0.859 / 0.658 / 0.356 → 0.551 / 0.359 / 0.070 | 6.43 → 4.18% | 13.47 → 12.42 |

- **The block hurts at every cost and in both views.** The sign does not flip across the grid (H3).
- **It lowers turnover rather than adding it** (−1.05 turns a year), because the book trades its in-window shorts
  inside the windows. The block's added turnover is negative, so A1 §7's kill line ("immaterial if the in-window
  P&L is below the added turnover × 5bp") cannot bind (§5).
- **Borrow (H4, real money only; paper charges none)** [V]. IBKR's fee panel exists only from 2021-09-13. On
  2021-09-13 → 2022-12-30 (328 sessions, 99.0% covered), the in-window shorts would have paid 445bp a year. On the
  same span they earned 601bp a year gross. **Net of borrow, the block still loses** 156bp a year (total) or 313bp
  (paper) on that span.

**3. The negative control (H12), the book's longs** [V]. Total view: inside +0.431 (SE 0.469, n 1,642), outside
+0.294 (0.161, n 13,320). The estimate is −0.137 (SE 0.409, t −0.34), INCONCLUSIVE; within date it is −0.25
(NW t −0.77). Paper view: −0.216 (0.414). **The longs are not hurt inside the windows either.** That fits the
premise that only shorts could be hurt, but the shorts were not hurt, so the control has no effect to separate.

## 1. What was measured, and what was fixed first

The design is in the script's docstring (`scripts/research/reopen_a1/book_windows.py`). It was committed at 97d3d18
before the first run. Summary:

- **The windows are A1's, not redefined.** `a1.census` was re-run on A1's caches, then filtered exactly as
  `a1.book_exposure` filters ("programme_episode"). That is a deployed name's EDGAR supplement episode with at least
  4 supplements, its first supplement before 2023-01-01, and not a rights offering. Each window runs from the first
  supplement to the last, cut at 2022-12-30.
- **The run asserts that A1's committed output reproduces** [V]:
  - the seven windows equal `a1_levels_2026-10-20.json`'s list;
  - the short name-days come to 9,285, with 1,681 inside;
  - the first live decision is 2013-06-21.
  The windows are listed in `results/research/reopen_a1/reopen_a1_windows.csv` (EDGAR facts only):

  | window | supplements | end |
  |---|---:|---|
  | JFR 2016-11-22 → 2017-02-28 | 6 | last supplement |
  | PTY 2018-06-12 → 2020-11-24 | 9 | last supplement |
  | PFN 2018-09-10 → 2022-12-30 | 15 | the fit period ends (last supplement 2024-08-20) |
  | PDI 2019-11-08 → 2022-06-23 | 12 | last supplement |
  | PCN 2020-12-03 → 2022-12-30 | 10 | the fit period ends (2024-08-20) |
  | HYT 2022-02-10 → 2022-12-30 | 13 | the fit period ends (2026-01-05) |
  | PHK 2022-06-01 → 2022-12-30 | 6 | the fit period ends (2025-04-15) |

- **The book.** The price and NAV panels are cut at 2022-12-30 before any computation (`build_targets(source=…)`),
  then `fit_only` is applied. The policy is `band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)` from spec
  `cef_discount.v7.20260928`, "band 4.8% + gmax 1.80x".
  - The full panels end 2026-10-15 (prices) and 2026-10-14 (NAV).
  - Cutting the distribution and split inputs at 2022-12-30 changes no cell of the total returns [V]. The cut
    ignores 1,831 distribution rows and one split row.
  - **Cross-check:** the book row reproduces the sibling note `REOPEN_BOOK_NAVTENDER_E1_2026-10-28.md` [S]
    exactly. Total view: 0.955 gross, 0.852 / 0.645 / 0.334 net. Paper view: 0.959, 0.859 / 0.658 / 0.356.
- **The unit.** A short name-day is a pair (decision session t, name) with H < 0. Its P&L is
  H[t]·R[t+2] (`harness.label`, H1). Summed, it equals `evaluate()`'s P&L on the short book, which the script
  asserts. The last two decisions, which earn in 2023, are dropped: 1,677 of the 1,681 inside remain.
- **Inside** means the window covers the decision session. A supplement dated t is public by 17:30 ET, and the book
  decides in the evening, so the start is causal.
- **The statistics come only from `scripts/research/inference.py`.**
  - `clustered_mean_diff` is new. It is the OLS sandwich on [1, 1(inside)] with date-clustered scores (CR0 ×
    G/(G−1), the desk's convention), pinned to statsmodels' cluster covariance by a parity test.
  - `read_result` and `newey_west_t` are as they were.
- **`meaningful`** is the round-trip cost of the positions themselves at 15bp: 15bp × 2 × mean|w|, summed over the
  in-window spells and divided by the in-window name-days.
  - Shorts: 24 spells, median 24.5 sessions, giving **0.046bp** a name-day. Longs: 21 spells, 0.028bp.
  - This is revision 1 (§5). The rule declared first could not be formed.

## 2. Where the in-window short P&L came from

| window | short name-days | P&L, bp of book: total · paper [V] |
|---|---:|---|
| PTY 2018-06-12 → 2020-11-24 | 317 | **+1,028 · +1,311** |
| HYT 2022-02-10 → 2022-12-30 | 93 | +291 · +328 |
| PDI 2019-11-08 → 2022-06-23 | 201 | +262 · +402 |
| PHK 2022-06-01 → 2022-12-30 | 146 | +63 · +94 |
| PCN 2020-12-03 → 2022-12-30 | 521 | +50 · +123 |
| PFN 2018-09-10 → 2022-12-30 | 349 | +23 · +53 |
| JFR 2016-11-22 → 2017-02-28 | 50 | −199 · −174 |

- **By year, total view** [V]:

  | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 |
  |---:|---:|---:|---:|---:|---:|---:|
  | −44 | −155 | **+1,048** | +10 | −40 | −74 | **+773** |

  Two years carry the result.
- **2018 is mostly PTY.** The five largest in-window short days are all PTY [V]. Four are in 2018, at a decided
  weight of −0.48 (vol-scaled), each worth +147 to +233bp of book:
  - −4.86%, the t+2 return after the decision of 2018-06-12, the date of PTY's first supplement;
  - then −4.31%, −3.52% and −3.06% (total returns), in October and November.
  The fifth is the 2020 crash: −10.12% at a weight of −0.15. CRSP's independent returns for the same five cells match
  to a thousandth of a percent, except one (−3.08% against −3.06%). The moves are real, not stale-price or split
  artefacts.
- **The 2020 crash is not the source.** 2020-02-15 → 04-30 (the sibling note's crash span, reused) contributed
  +155bp. Without it, the in-window shorts made +146bp a year (total) or +213bp (paper).
- **By era** [V], total view, mean per short name-day inside / outside:
  - 2015–19: +3.71 / −0.47 (n 226 / 3,854);
  - 2020–22: +0.47 / +0.69 (n 1,451 / 2,328);
  - 2013–14: no in-window name-days.
  In 2020–22, which holds 87% of the in-window name-days, inside and outside are close, and inside is the lower.
- **Sizing.** The in-window shorts are smaller: mean |w| 0.104 against 0.161 outside. Per unit of weight the gap is
  wider, but no more significant (table §0, last row).

## 3. The block by era (H5) [V]

| era (from the first held session) | book gross · net 5 / 15 / 30 | block gross · net 5 / 15 / 30 | change, gross · turn/yr |
|---|---|---|---|
| 2013-06-25 → 2014-12-31 (2010–14) | 1.298 · 1.154 / 0.864 / 0.431 | identical: no windows | 0 · 0 |
| 2015–19 | 0.835 · 0.778 / 0.664 / 0.493 | 0.656 · 0.593 / 0.466 / 0.277 | −0.179 · −0.12 |
| 2020–22 | 1.020 · 0.852 / 0.514 / 0.008 | 0.622 · 0.489 / 0.223 / −0.175 | **−0.399** · −3.14 |
| paper view, 2015–19 · 2020–22 | 0.719 · 1.084 | 0.438 · 0.539 | −0.281 · −0.545 |

- The book's era turnover sd/mean is 0.454.
- **The block leaves the book net long.** Mean net held weight rises from +0.039 to +0.112 over the window, on the 937
  sessions it binds. It is not re-neutralised, as G6's filter was not. So part of what it changes is market exposure,
  not alpha.
- **What the post-hoc filter leaves out.** It is applied after the band and the 1.80× ceiling, not inside their loop.
  A real block would lower the book's gross and change when the ceiling binds. That second-order effect is not
  measured.

## 4. What this does and does not establish

- **Established on the fit period (measured):**
  - the in-window shorts made money, +159.5bp a year (total) and +224.7 (paper);
  - two price sources agree to within 0.03bp a name-day;
  - blocking them costs 0.22 (total) to 0.31 (paper) of gross Sharpe at every cost point, and still loses net of
    measured borrow on the 15 months where borrow is measured.
- **Not established:**
  - whether in-window shorts differ from other shorts, as a property of issuance. The interval is wide, the
    within-date difference is near zero, and the result rests on seven windows. PTY's alone carries 68% of the
    in-window P&L, and five of the seven are one sponsor's (A1 §5.4's D7 point, unchanged). Clustering by date does
    not count that dependence; the effective sample is closer to seven than to 1,677.
  - whether the windows are knowable in time.
    - The start is causal; the end is not. Four of the seven windows run to 2022-12-30 only because their last
      supplements are 2024–26 EDGAR filings (dates, not prices).
    - The "≥ 4 supplements" label reads later filings (A1 §3).
    - So the block is an ex-post-window counterfactual. A tradable rule would classify the first supplement's cover
      (A1 §7 item 2, unwritten).
  - **2023 onward**, where the large programmes are (A1 §2.5: PDI, PTY and PCN report large ATM proceeds in
    2025–26 [S]). That is the time holdout, and opening it is a trial on the CEF counter.
- **Paper fills** are modelled at the close (`shift(2)`). Paper does not run the closing auction (CLAUDE.md landmine
  1), and nothing here is a broker fill.

**What follows, as a rule (H14), re-measured rather than read from this note.** Run the script. If the block's
change in net Sharpe is negative at 5, 15 and 30bp in both views, an issuance block on the live book's shorts is not
worth a pre-registration on this data. If a later measurement reads the short split as PRESENT in the question's
direction (lower bound of outside − inside above zero), with the long control not PRESENT in the same direction, and
the block's net change is positive at every grid point, an issuance-aware short rule becomes a CEF-counter
candidate. That candidate would still need the ex-ante classifier and the holdout. On this run the first branch
holds.

## 5. Order of work, for the record

1. **97d3d18.** The design, the code and the tests were committed before the first run. That includes
   `inference.clustered_mean_diff` and its statsmodels parity test.
2. **Run 1 raised before any return was computed.** The script computes holdings-only quantities first. The block's
   added turnover measured −10.0 turns over the window, so the declared hurdle, 15bp × added turnover / in-window
   name-days, could not be formed, and the script refused to invent one.
3. **Revision 1 (e113561)** replaced the hurdle with the positions' own round trip per spell. It is recorded in the
   docstring with its reason, and it was committed before run 2.
4. **Run 2** produced every reading above.
5. **After run 2**, descriptive lines were added (aa41438, b288619): the in-window P&L by year, without the crash
   span, and on the borrow span net of borrow; and the five largest in-window days with CRSP's return for each. They
   enter no reading.
6. **The final run** was at b288619 on a clean tree (the JSON's `git_head` and `git_clean`). It reproduced run 2's
   figures. Only this note's prose changed after it.
