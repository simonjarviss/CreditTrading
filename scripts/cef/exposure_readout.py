"""Report-only exposure readout: the book's MUNI exposure (headline) and TERM / CREDIT / LOANS (indicative), per day.

ZERO TRIALS. IT READS A BOOK AND REPORTS. IT NEVER TRADES.

WHY THIS EXISTS (team lead, 2026-11-02)
---------------------------------------
The live attribution of the cef paper account (results/cef/LIVE_ATTRIBUTION_2026-11-02.md,
PR #26) split its 09-29..10-30 loss into a discount part (the signal's leg) that made money
and a NAV part that lost it, most of it in the muni shorts as muni NAVs rose against
taxable ones [S: that note]. The Sharpe-framed NAV hedge was screened the same day and
CLOSED at the power gate (results/cef/NAVHEDGE_SCREEN_2026-11-02.md). The team lead
approved this readout in its place: position-based daily telemetry of the live book's
exposure to rates, HY credit, munis and loans, so that the next muni-vs-taxable move is
measured, not inferred from a few weeks of P&L. It is the deleted `/api/factors`, rebuilt.

It holds no order code, imports nothing from quantt/ or src/deploy/, reads no key and
opens no broker connection. Its only network call is keyless yfinance, in `fetch`.
Nothing on the live path imports it. A test pins all of that.

    fetch       keyless yfinance -> a gitignored cache (closes, adjusted closes, actions)
    crosscheck  the cache against the repo's own panels on the overlap (read-only)
    derive      re-measures the two modelling choices below on the fit era (< 2023, H13)
    analyse     a positions CSV + the cache -> exposures, the review list, factor P&L

THE FACTORS, AND WHY THEY ARE ORTHOGONALISED
--------------------------------------------
TERM = IEF, CREDIT = HYG, MUNI = MUB, LOANS = BKLN, each a daily TOTAL return (below).

Collinearity was measured first (`derive`, fit era 2011-03-04 .. 2022-12-30, 2,978
sessions, after BKLN's first return) [V: derive, re-run 2026-11-02]:
  * full-era correlations: IEF-MUB +0.394, HYG-BKLN +0.703, MUB-HYG +0.305,
    MUB-BKLN +0.342, IEF-HYG -0.100, IEF-BKLN -0.135; VIF 1.32 / 1.48 / 2.01 / 2.14
    (IEF, MUB, HYG, BKLN); condition number of the correlation matrix 6.67;
  * but the readout estimates on a 252-session window, and there the pairs are much
    tighter and unstable. Over the era's rolling windows: IEF-MUB median +0.64, up to
    +0.83; HYG-BKLN median +0.63, up to +0.88; IEF-HYG changes sign, -0.59 to +0.50;
    MUB-HYG -0.48 to +0.64. Rolling VIF median about 1.8, max 4.5;
  * netting IEF out of the other three is not enough. The residuals MUB|IEF and HYG|IEF
    still correlate up to +0.75 (p95 +0.66), and BKLN|IEF with HYG|IEF up to +0.83
    (median +0.63).
The VIFs alone would not call this severe. The reason to orthogonalise is what the readout
reports: each factor's vol contribution |E_k| x sigma_k, read one factor at a time, and a
review rule on it. That number is the factor's contribution only if the cross terms
2 E_j E_k rho_jk sigma_j sigma_k are small, and with window correlations of 0.6-0.9 they
are as large as the own terms. Offsetting raw betas (long MUB, short IEF) would each look
large and cancel. So the four are orthogonalised by Gram-Schmidt on each window, in this
order, general to specific:
  TERM   = IEF                                  (every ETF here carries duration)
  CREDIT = HYG  net of IEF                      (HY spread, beyond rates)
  MUNI   = MUB  net of IEF and HYG              (the muni-vs-taxable move this exists for)
  LOANS  = BKLN net of IEF, HYG and MUB         (the floating-rate remainder)
Each is a tradable spread return: the ETF less its window OLS slopes times the earlier
ETFs (the intercept is not subtracted, so the factor stays a return). On the window the
four are exactly uncorrelated in sample, so the factor variance of the book is the sum of
the squared contributions on that window. CREDIT comes before MUNI because a joint
muni-and-HY sell-off (outflows, a risk-off week) is a general credit move. MUNI is then
what munis did that Treasuries and taxable HY did not. That is the muni-vs-taxable
dimension, and it is where the order matters most: the MUB|IEF and HYG|IEF residuals are
near zero in the median window but +0.66 at p95. The framework's fixed differences
(MUB - IEF, HYG - IEF; PORTFOLIO_FRAMEWORK_2026-10-15 §3.1) do not orthogonalise: the
window OLS slope of MUB on IEF has a median of +0.33 in the fit era, not 1.

Orthogonalising changes how the exposure is SPLIT, never its total. On the window the
orthogonal set spans the same space as the raw ETFs, so the fitted values, and the total
factor P&L sum_k E_k f_k, are identical in either basis; a test pins that.

DIMSON LAGS: THE LEAD-PLACEBO RULE (team lead, 2026-11-02: re-derive L before the next reading)
-----------------------------------------------------------------------------------------------
A CEF's close can trail the ETFs' closes: the fund trades thinner, and its price partly
anchors to a NAV that is struck from stale evaluated bond prices (W4 measured NAV AC(1) of
+0.26 to +0.54 by group; results/cef/W4_ARTIFACTS_2026-10-11.md §3 [S]). Dimson (1979)
regresses on the factor at t, t-1, ..., t-L and sums the betas. The exposure uses that sum:
the whole eventual response of the price to a factor move.

THE RULE. Written into this module, with its tests, and committed on its own (09d3dad,
2026-11-02 22:02:51 New York time) before it was first run on any data. No alternative to
it was computed before that commit.
`lead_placebo_counts` makes the counts and `placebo_lag_rule` decides; `derive` runs both.
  Data      the cache's total returns, cut at FIT_END (2022-12-30) BEFORE anything is
            shifted, so no response, lag or lead is dated 2023 or later (H13;
            `lead_placebo_counts` raises if one is). The four ETFs orthogonalised once on the
            whole fit era, in FACTORS order. Names: the frozen spec's UNIVERSE, read at run
            time; the pairs are names x 4 factors (52 on 13 names).
  Model     ONE OLS per name: its daily total return on a constant, the four factors at lags
            0..K and the four factors at leads 1..J, with HAC (Newey-West, 5 lags) standard
            errors, on every session where all of them exist. K = DERIVE_MAX_LAG = 10, the
            bound W4 used for its NAV-staleness sensitivity. J = DERIVE_RULE_LEADS = 19.
  Counts    c(l), l = 0..K: pairs whose lag-l coefficient has a two-sided p < 0.05.
            p(j), j = 1..J: pairs whose lead-j coefficient does. Same model, same sample.
  Bound     T = max over j of p(j): the largest count the placebo produced.
  Decision  Lag 0 must have c(0) > T, or the rule raises: the factors would then explain the
            funds no better than their future returns, and no L means anything. Then for
            l = 1, 2, ..., K in that order, lag l is included if and only if c(l) > T,
            strictly. L is the last lag included before the first lag that is not.
  Ties      c(l) = T does not include lag l, and it stops the sequence.
  Gaps      A lag that clears T after a lag that did not is NOT included: the Dimson sum
            needs lags 0..L without a hole, and the sequence below needs the stop.
  Censoring If every lag 1..K clears T the rule raises. L would then be censored at K; K is
            widened only under a new rule declared first, and K is never taken as the answer.
WHY EACH PIECE
  * The null is a placebo, not Binomial(52, 0.05). A lead coefficient loads the fund's
    return on the factor's FUTURE return. With the lags in the model it has no causal
    channel unless the fund leads the ETF. So its count is what 5% noise produces under the
    real dependence among 13 co-moving funds' t-statistics, which a Binomial treats as 52
    independent draws: the review's 5-lead placebo reached 18 against a Binomial 95% point
    of 5 (below). Lags and leads come from ONE model per name so that they share the
    residuals, the HAC weights, the sample and the design; the leads are then the nearest
    available copies of a lag that carries nothing.
  * q is the maximum of J = 19 lead counts. If lag l carries no response, its count is
    (assumed) exchangeable with the 19 lead counts, and the chance that it strictly exceeds
    all 19 is at most 1/20 = 0.05. That is the placebo's 95% point in the rank sense. It
    matches the 5% that each pair is counted at, and it needs no quantile interpolated from
    a small sample. J = 19 is the fewest leads at which the maximum gives a 5% test
    (1/(J + 1) <= 0.05); a test pins that relation.
  * The fixed order. Testing lags 1, 2, ... in a declared order, each at 5%, and stopping at
    the first that fails keeps the chance of including ANY null lag at 5% with no
    multiplicity adjustment: including a null lag requires including the first null lag in
    the order, and that is one 5% event.
  * The tie. Strict ">" keeps the rank test at or below 5% when counts tie. A lag that only
    matches the largest placebo count has not shown more than the placebo.
  * Risks, stated and not corrected. (a) If a fund does lead an ETF, some lead counts are
    not null: T is then too high and L too short. (b) Exchangeability of lag and lead counts
    is an assumption [U]. (c) The 19 lead counts are correlated with each other, so the
    maximum comes from fewer than 19 effective draws [U how many].
    [Added after the result, 2026-11-02; the rule above is unchanged: on this data the lead
    counts are not null draws. One episode inflates some of them, so T is too high, which is
    (a)'s effect by another cause. See WHAT L = 0 DOES AND DOES NOT SHOW, below.]
WHAT WAS IN SIGHT WHEN THE RULE WAS WRITTEN: the review's figures below (the lags-only counts
at K = 10 and the five lead counts), all of 2026-11-02. No piece of the rule (K, J, the 5% per
pair, HAC(5), the maximum, the tie, the stop, the single joint model) was computed on data
before the commit that declared it. One consequence was visible in advance: the review's
lead-1 count (18) exceeds every lags-only count from lag 1 on, so if the 19-lead maximum
lands near it, this rule gives L = 0. That outcome was accepted in advance. The rule is not
re-tuned after it runs, and any change to it lands in a commit of its own, before it is run.

The plateau check sits beside it, as before, and nothing is chosen from it: `derive` prints
the muni names' summed MUNI beta at every L, and `analyse --plateau` the per-factor review
counts at L - 1 .. L + 2.

THE RULE'S RESULT: L = 0, so DIMSON_LAGS = 0 [V: `derive`, run 2026-11-02 at 22:02:56 New
York time, 5 s after the commit that declared the rule (09d3dad, 22:02:51 -0500). The cache
was asof RULE_CACHE_ASOF (2026-10-30), and its prices.parquet hashes to RULE_CACHE_SHA256;
`derive` prints whether the cache it reads is that one. Sample 2011-03-18 .. 2022-12-02, the
last response row, whose lead-19 row is 2022-12-30. 464 to 2,949 sessions per name; PDO
starts 2021-02-02]:
  lag counts  c(0..10)  46 18 16  8  4 12 14 13  6  7 17                      (of 52 pairs)
  lead counts p(1..19)  12  6 12 16  8 13 13 12 14 11  7 11 19 18  3  4  1  5  5
  T = 19, at lead 13. Lag 1's count is 18, not above 19, so the sequence stops at lag 1.
  The margin is thin: L leaves 0 if lag 1 gains 2 pairs, or if lead 13 loses 2 and lead 14
  loses 1. That is why the cache's hash is recorded beside the counts.

WHAT L = 0 DOES AND DOES NOT SHOW. The review of this result (2026-11-02) measured most of
what follows. The session that fixed the review's findings added the year control, the
trend test with no cut and the offset-for-offset comparison of far lags and leads.
`derive` section 2b prints every count and rate below [V: re-run 2026-11-02 in this module,
and by a second implementation that builds the episode mask from dates, with identical
counts]. All of it came after the result. Nothing was chosen from it, the rule was not re-run
on it, and the episode's window and the lead cut at 14 were picked by the review after it
had seen the counts.
  * L = 0 is what the declared rule outputs. It is NOT evidence that the lags carry nothing.
    The rule reads T as the largest of 19 null draws, and on this data T is not that.
  * One episode sets T. The 19 significant pairs at lead 13 are all taxable funds (no MHD or
    MQY): 18 CREDIT or LOANS pairs and PCN's MUNI, every coefficient negative. Drop, from
    every name, the rows whose regressor span t-10..t+19 touches 2020-02-20 .. 2020-04-30
    (79 rows of a full-sample name, 2.7% of it; PDO, which starts in 2021, loses none).
    Lead rejections fall from 190/988 (19.2%) to 86/988 (8.7%), lags 4..10 from 73/364
    (20.1%) to 38/364 (10.4%), lead 13's count from 19 to 5, and the largest lead count from
    19 to 10. The lag counts become 45 14 10 4 3 6 10 1 4 7 7, on which the same decision
    step would give L = 1. That is the review's reading, disclosed and not adopted.
  * The control. Dropping each calendar year in turn instead (its rows and those whose span
    reaches into it): for every year but 2020, lead rejections stay at 19.1% to 21.0% and the
    largest lead count at 18 to 21. Dropping 2020 gives 7.9% and 8. It is the episode, not
    the loss of any one year of rows.
  * Exchangeability, measured. Every lead count at 1..14 (smallest 6) is above every count at
    15..19 (largest 5): 172/728 tests (23.6%) against 18/260 (6.9%). The review put the
    chance of that, under exchangeable counts, at 1/C(19,5) = 1/11,628, or about 1.5e-3
    "allowing for the 18 possible cut points". That allowance is too small. The cut was
    chosen after seeing the counts, and over every cut 1..18 the chance of some such clean
    split is at most the sum of 1/C(19,k), 0.12 [V: arithmetic], and about 0.11 [V: 400,000
    random orders, seed 0; not printed by derive]. A test that needs no cut,
    the Spearman trend of count on lead with a permutation null, gives rho -0.45, one-sided
    p 0.025 and two-sided p 0.053 [V: derive 2b, 20,000 permutations, seed 0]. So the order
    of the lead counts alone is suggestive, not decisive. What shows that T is not a null
    draw is the episode recount and its control.
  * Direction. An episode that inflates some lead counts raises T, so on this data the rule
    leans conservative: L too short, as in risk (a). How far is [U].
  * Far lags against far leads, offset for offset (lags 0..19 beside leads 1..19, full
    sample): at offsets 11..14 lags reject 13.9% and leads 28.8%; at 15..19, 10.8% and 6.2%;
    over 11..19, 12.2% and 16.2%. The review set lags 11..19 (12.2%) beside leads 15..19
    (6.2%), which are different offsets. Offset for offset, the far leads reject at least as
    often as the far lags overall, so that comparison does not show the lags falling off more
    slowly than the leads.
  * The cause of the excess, corrected. This docstring said, after the result, that "either
    the HAC(5) tests on these funds are oversized about fourfold, or the returns carry
    structure at every offset", and that "no single name drives it". Most of the excess is
    the one episode, and it sits in the taxable funds. By name, leads reject 27 of 76 tests
    for BIT, 16 to 20 for AWF, DSL, HYT, JFR, PCN and PFN, 8 to 13 for PDI, PDO, PHK and PTY,
    and 7 for each muni fund, against 3.8 at 5%. With the episode dropped, BIT rejects 13 and
    every other name 2 to 9. Whether the episode is real crash-and-rebound dynamics or a HAC
    test losing its size on a few extreme cross-products is [U]. A wider Newey-West bandwidth
    corrects for serial correlation; nothing here shows it would correct either. Even with
    the episode dropped, leads reject 8.7% against 5%.
  * By name, the muni funds show the clearest lag response. MHD and MQY reject 6 and 8 of
    their 12 lag 1..3 tests and 7 of their 76 lead tests each [V: derive 2b]. The rule pools
    all 52 pairs and does not look by group. That is a property of the rule as declared; the
    rule was not re-run on it.
  * The plateau at L = 0 is the median cumulative summed beta by group, from the lags-only
    0..10 models; L - 1 does not exist. The muni group's MUNI beta is 1.03 at L = 0, 0.97 at
    L = 1 and 1.10 at L = 10, so that cell is level. The muni group's TERM beta is 0.40 at
    L = 0, 0.50 at 1 and 0.73 at 10, so that cell is not. The taxable groups' MUNI beta
    loses half or more from L = 0 to L = 1: hy 0.66 -> 0.11, multi 1.00 -> 0.40, loan
    1.01 -> 0.64. Loan TERM goes -0.26 -> -0.42 (-0.66 at L = 10).
  * At L = 0 the exposure is the same-day beta only. It no longer carries the staleness
    response that the Dimson sum was put in to catch. Each window's design falls from 17
    regressors to 5.
Whether to keep L = 0, knowing that T is set by March-April 2020, or to declare a different
rule first (one that withstands the episode, one by group, or neither) is the team lead's
call. A rule declared now would be written with the episode-dropped counts and the year
control in view, and must say so, as this one disclosed the counts it was written beside.
Any new rule is declared and committed before it runs, as this one was.

THE TEAM LEAD'S RULING (2026-11-03). Keep DIMSON_LAGS = 0, the declared rule's output, and
make MUNI the headline; TERM, CREDIT and LOANS are marked indicative. No new lag rule is
declared. THE RULE, DIMSON_LAGS, REVIEW_FRACTION and every computation are unchanged: the
five CSVs `analyse` writes are byte-identical before and after the change [V: diffed on
synthetic positions files, with and without equity and with --plateau, 2026-11-03]. Only the
order and headings of summary.md, which `analyse` also prints, changed (`summary_md`):
  * first, "Headline: MUNI": the review rule, then MUNI against it, MUNI per date (exposure,
    vol contribution, review flag), and the muni-vs-taxable group reading
    (`muni_vs_taxable`): the book's MUNI exposure from the muni group (grp `muni` in
    data/cef/cef_universe.csv) beside the taxable groups (every other grp), with the MUNI
    factor P&L by group;
  * then, under INDICATIVE_HEADING ("Indicative: depends on the lag choice (see DIMSON_LAGS
    docstring)"): TERM, CREDIT and LOANS against the rule and per date, the book totals
    (whose total factor vol sums all four factors) and the factor P&L of the three and of
    all four;
  * the plateau check, when asked for, stays last.
Each factor now gets its own line against the rule, "within the line" included; the first
build listed only the flagged ones, which would have left a MUNI within the line silent.
Why MUNI leads and the other three do not, from the fit-era plateau and the review counts
above [S: this docstring; not re-run for the ruling]: the muni group's MUNI beta is level
across L; the muni group's TERM beta moves with L, LOANS has no plateau at any L, and the
review counts moved more with L for TERM, CREDIT and LOANS than for MUNI. Even in the fit
era the book's MUNI exposure also sums the taxable funds' MUNI betas, and those move with L.
MEASURED WHILE RECORDING THE RULING (it changes nothing; whether it bears on the ruling was
the team lead's call, and on 2026-11-08 the team lead ruled: keep L = 0 and the MUNI headline). On the current window the muni funds' own MUNI beta is NOT level in
L. Summed MUNI beta on the 252 sessions strictly before 2026-10-30 (cache asof 2026-10-30),
at L = 0, 1, 2, 3: MHD +1.21 +1.49 +1.59 +1.65, MQY +1.27 +1.33 +1.44 +1.67; the taxable
names' group medians fall from L = 0 to L = 3 (hy +0.02 to -0.31, loan, JFR alone, -0.13 to
-0.55, multi +0.24 to -0.06) [V: `fit_window` on the 13 spec names, 2026-11-03, public
prices only; MHD, MQY, PDI and JFR re-derived by a second implementation, statsmodels' OLS
for both the Gram-Schmidt and the regression, agreeing to 2 dp]. So on this window a book
short munis and long taxable funds has a MUNI exposure that grows in size with L from both
sides. The fit-era level cell is a fit-era fact, and the headline at L = 0 is
the same-day beta, as every factor's is. Re-measure, never read these figures: `analyse
--plateau` prints the MUNI review counts and mean |E| at L = 0 .. 2 on the book read, and
`fit_window(...).beta_sum["MUNI"]` gives the names' betas at any L. If MUNI's reading moves
with L on the book read, the plateau rows show it beside the adopted row; if it does not,
they show that. The group reading sits in the headline so that the muni and taxable shares
of MUNI are read on every date, not assumed. A test pins the order.

THE RULES IT REPLACES (2026-11-02; history). DIMSON_LAGS = 3 came from this rule (`derive`,
fit era, 13 names, factors orthogonalised on the whole era, HAC(5)) [V: derive, re-run
2026-11-02]. For each lag l, count the (name, factor) pairs, of 52, whose lag-l coefficient
is significant at 5%, with lags 0..K in the model and K = 10. Take the first gap: L = the last
lag before the first lag whose count is within Binomial(52, 0.05)'s 95% point, 5. The counts
were 43, 14, 10, 7, 2 at lags 0..4, so L = 3. `derive` still prints it and the three rules
tried before it, labelled superseded; nothing is chosen from them.

The review of 2026-11-02 (finding 1) showed that the data pin this L weakly. `derive` now
prints the first three points below and `analyse --plateau` the fourth [V: both re-run
2026-11-02]:
  * The adopted rule was the fourth tried, all in one session, and the only one that gave
    3. The first build's docstring disclosed only the first. All four, at both lag bounds:
                                                              K = 5   K = 10
      joint Wald test of lag l, a majority of the 13 names      1       1    (tried first)
      sum of lags L+1..K, pairs within the bound                2       1
      single-lag first gap (adopted)                            2       3
    One (rule, K) pair of the six gives 3. The adopted rule gives 2 at K = 5.
  * The null bound fails a placebo. Binomial(52, 0.05) treats the 52 pairs as independent,
    and 13 co-moving funds are not. With five LEADS in the model (the factors' returns at
    t+1..t+5, which cannot cause anything), 18, 1, 9, 11 and 4 pairs come out significant:
    three of the five exceed 5. Under the first-gap rule a bound of 2-6 gives L = 3, 7-9
    gives 2, 10-13 gives 1, and 14 or more gives 0. The counts at lags 5..10 (12, 9, 12, 5,
    7, 10), which the first build read as a possible weekly flow pattern, sit in the same
    range as the lead counts, so noise under that dependence explains them as well [U which].
  * The plateau check picks a hump, not a plateau. The muni names' summed MUNI beta (group
    median) is 0.97 at L = 1, 1.13 at 2, 1.42 at 3, 1.38-1.40 at 4-5, 1.11-1.23 at 6-9 and
    1.10 at 10. L = 3 is the peak, 29% above the L = 10 value. The first build called
    L = 1 "about a third short"; that compared it to the peak, and against L = 10 it is 12%
    short. The muni names' TERM beta does level off: 0.50 at L = 1, 0.63-0.65 at 3-5,
    0.63-0.74 at 6-10. CREDIT moves by up to 0.17 per group from L = 3 to L = 5 (loan
    1.00 -> 1.17, hy 1.28 -> 1.37, multi 1.35 -> 1.43, muni 0.74 -> 0.75; the first build
    said "at most 0.10", which these same figures contradict). LOANS has no plateau at any
    L: outside the loan fund (JFR) its group medians wander between -0.20 and 0.73.
  * The per-factor review counts move with L. On the first validation book, between
    L = 1 and L = 3 the dates flagged moved by 7 to 12 of 24 for TERM, CREDIT and LOANS,
    and by 3 for MUNI [V: `analyse --plateau`, 2026-11-02; the reading is not committed,
    because it derives from the account's positions]. `analyse --plateau` prints the
    counts at L = 0 .. L + 2 beside the adopted row.

The team lead ruled on 2026-11-02: re-derive L properly, under a lead-calibrated null
declared before it is run, before the next reading. THE RULE above is that null. At the
commit that declared it DIMSON_LAGS was still 3, from the superseded first-gap rule. The
next commit, made after `derive` had run the rule, set it to the rule's output, 0. The rule
reads only the fit era's public prices, never a reading of any account. Each lag costs
estimation noise: at L = 3, 17 regressors on 252 sessions, about 15 sessions each.

THE WINDOW: THE SLEEVE'S OWN z_window
-------------------------------------
W = frozen `z_window` (252 sessions today, read through scripts/cef/spec.py at run time).
  * It is the memory of the signal that chose the positions, so the readout reads the book
    through the same window as the signal that built it.
  * It is the framework's trailing-beta convention (PORTFOLIO_FRAMEWORK_2026-10-15 §3.1).
  * One year spans a full distribution and tax calendar, including munis' year-end.
  * A shorter window was tried for z and failed out of sample (the spec's z_window note).
`analyse --plateau` re-runs at W/2 and 2W (lags fixed) and at lags 0 .. L + 2 (window
fixed), and prints the factor P&L, by book and by group, and the per-factor review counts
beside the adopted row. That is a check for a plateau; nothing is chosen from it.

NO LOOKAHEAD (H7, asserted at run time)
---------------------------------------
The exposure on date t uses betas, orthogonalisation slopes and factor vols estimated on
the W sessions STRICTLY BEFORE t (the y rows), with lagged factor rows reaching L sessions
further back. `assert_strictly_before` raises `LookaheadError` if any row of either window
is dated t or later; it is an explicit raise, not an `assert`, so `python -O` cannot strip
it. The factor P&L of session t uses the exposure of the previous session (E(t-1) x f(t)),
with f(t) built from E(t-1)'s own slopes.

TOTAL RETURNS (H15)
-------------------
r_t = (1 + close_t / close_{t-1} - 1) * k_t - 1 + D_t / close_{t-1}, on yfinance's raw
`Close` and `Dividends`, where k is the split multiplier on an ex-split date: the harness's
own formula (`band_frontier.total_returns`), checked by the same split-basis guard
(`data_guards.guard_split_basis`). It does not use Yahoo's Adj Close for returns, because
Adj Close is re-based at every distribution and is not stable even between two fetches
(docs/REFERENCES.md §8, the byte-identity row). Adj Close is cached and cross-checked only.
A split and a distribution on one name-date raise, as in the harness. Yahoo reports no
capital-gains column for the CEFs; for an ETF a non-zero `Capital Gains` value raises,
because whether Yahoo also counts it in `Dividends` is not documented here [U].

The CEF closes and distributions come from the same vendor as data/cef/'s panels, so
`crosscheck` agreeing with those panels confirms the fetch, not the data (review 2026-11-02,
finding 6); every cross-check row now names its panel's vendor. docs/REFERENCES.md records
11 CRSP distributions missing from the yfinance distribution panel in 2005-2022 [S], three
of them large year-end specials (PFN 2012-12-26, PTY 2011-12-28, PCN 2012-12-26). The cache
lacks those three as well [V: cache read, 2026-11-02], so they enter `derive` as price
returns. Dropping the three name-days from derive's regressions leaves its lag counts and
the muni group's plateau table unchanged [V: re-run 2026-11-02]. All three fall years
before any 2025-26 window.

EXPOSURE, VOL CONTRIBUTION AND THE REVIEW RULE
----------------------------------------------
For held name i on date t, v_i = shares_i(t) x close_i(t), signed (a short is negative):
  E_k(t)     = sum_i v_i x beta_ik(t)                     dollars; beta = summed Dimson beta
  e_k(t)     = E_k(t) / equity(t)                         fraction of equity
  sigma_k(t) = sd of factor k's daily return on the window x sqrt(252)
  c_k(t)     = |e_k(t)| x sigma_k(t)                      ex-ante vol contribution
  t-stat     = E_k / SE(E_k), SE^2 = (v' S v) a_k' (X'X)^-1 a_k, the OLS identity for
               names that share one design X (S = the names' residual covariance, a_k
               selects factor k's lag columns). Homoskedastic OLS; read it as a guide.
The total factor vol is sqrt(e' Sigma_f e), with Sigma_f the window covariance of the
factors (diagonal on the window, by construction).

REVIEW RULE (proposed 2026-11-02, declared and committed BEFORE the first reading on any
account's positions; it is a proposal, and the team lead decides it). Provenance: the rule
landed in one commit with this module, its tests and its REFERENCES row (034f1df), so git
alone cannot show that it came first (review 2026-11-02, finding 5). File times show it as
far as they go: the first analyse run on the account's positions wrote its outputs 11 s
after that commit, and the only earlier analyse run used invented three-name positions
[V: file times, 2026-11-02]. Any change to the rule lands in a commit of its own, before
any reading made under it.
  On each date t, a factor k whose c_k(t) exceeds REVIEW_FRACTION x vol_target_annual x
  sizing_multiplier goes to the team lead's review (the multiplier since the team lead's
  ruling of 2026-11-10, THE LINE IS ON THE ACCOUNT'S SCALE, below). Both are read from the
  book's own frozen spec at run time.
  NOTHING IS EVER HEDGED, TRADED OR RESIZED AUTOMATICALLY. Without an equity figure for t
  the rule is UNMEASURED on t. It is never evaluated against a default capital.

How REVIEW_FRACTION = 0.10 was derived (H14: the rule re-measures e_k and sigma_k at run
time and reads the vol target from the spec; the 0.10 is a rule, not a measurement):
  * D4 (docs/BRIEF.md; .claude/rules/research-harness.md) tolerates a factor beta of at
    most 0.10 in a strategy at its vol target ("alpha only, beta tolerated only as
    residual", team lead, 2026-10-09). PORTFOLIO_FRAMEWORK_2026-10-15 §3.1 applies the
    same bar to the whole book.
  * A beta bar does not compare factors whose vols differ. In the fit era's 252-session
    windows the orthogonal factors' median vols are TERM 5.5%, CREDIT 5.8%, MUNI 2.0% and
    LOANS 2.7% a year [V: derive, 2026-11-02]: a MUNI beta of 0.10 carries about a third
    of the risk of a CREDIT beta of 0.10. So the bar is applied to
    each factor rescaled to the book's own vol target: beta x sigma_k / vol_target <= 0.10,
    which is c_k <= 0.10 x vol_target. For the account the book's own vol target is
    vol_target_annual x sizing_multiplier (team lead, 2026-11-10; below).
  * Read another way, a factor at the line explains 0.10^2 = 1% of the target variance on
    its own, or correlates 0.10 with a book at its target.
  * Beside it the readout prints D4's literal reading |e_k| > 0.10 and the exposure's t, so
    the team lead can see whether a flag is size or noise. Neither is part of the rule.

THE LINE IS ON THE ACCOUNT'S SCALE (team lead, 2026-11-10)
  The line is REVIEW_FRACTION x vol_target_annual x sizing_multiplier, each read at run
  time from the book's own frozen spec (the core's through scripts/cef/spec.py, C4's from
  ops/specs/c4_families.frozen.json). WHY: the spec's `_sizing_multiplier_note` says the
  account holds m x the unit book and that vol_target_annual stays on the unit book's
  scale, so the account's effective ex-ante target is vol_target_annual x m. This readout
  measures the account's real positions (its shares at its closes, over its equity), so
  its line belongs on that scale. Before the ruling the line sat on the unit book's scale,
  and a book running at its effective target read m times closer to the line than it was.
  WHAT MOVES: the line, and the REVIEW flags and review counts read against it. What does
  not: E, e, sigma, c, t, c/target and total/target (both still over vol_target_annual),
  the betas and the factor P&L. So the flag is c/target > REVIEW_FRACTION x m, and every
  output prints the line's three inputs beside it. The multiplier is parsed by
  `sizing_multiplier`, a COPY of src/deploy/registry.cef_sizing_multiplier, the runner's
  own parse: absent or null is the unit book (m = 1, what the runner then holds, not a
  default invented here), and a malformed value or a near-miss spelling of the key raises.
  It is a copy because this module imports nothing from src/ (the test of what it is not
  pins that); a test holds the two equal on valid, absent, null, malformed and misspelt
  inputs, as live_attribution's copy of data_books.c4_nav_symbols is held.

WHAT IT REFUSES (raises, naming what is missing; never a default)
-----------------------------------------------------------------
  * a fetch as of today or later: yfinance serves today's bar intraday (REFERENCES §8);
  * a ticker whose rows are not exactly the NYSE sessions from its first row to the asof
    (`ops/schedule/nyse_calendar.py`), a duplicate row, a non-finite or non-positive close,
    a negative dividend, a non-zero ETF capital gain;
  * a held name or a factor ETF with a missing return anywhere in its window, or with fewer
    sessions than the window needs; a close missing on a positions date (for a held name,
    in the default strict mode; the report job's partial mode leaves it out, named: PARTIAL,
    below);
  * a split on a held name after the first positions date (the cached close would no
    longer match the share count), and a split the guard reads as already adjusted;
  * a positions file with a duplicate (date, symbol), a non-finite share count, a date
    that is not a cached session, or an equity column that holds a value that is not a
    plain number (e.g. "$100,000.00"), is empty on every row, is missing on some rows,
    differs within a date, or is not a finite positive number. A file without the column
    reads every rule cell as UNMEASURED;
  * a held symbol with no group in data/cef/cef_universe.csv;
  * any write under data/ (CLAUDE.md landmine 9), or of a file git could see in the
    repository that encloses the target (from a linked worktree, that can be the main
    checkout): the outputs carry the caller's positions, and this repository is public.

PARTIAL: THE REPORT JOB'S MODE (team lead, 2026-11-10)
----------------------------------------------------
The daily P&L job (scripts/ops/pnl_report.py) runs at 20:30 ET, and a held name's same-day
close is not always served by then (HYT lags, CLAUDE.md landmine 6). Before this ruling that
made the job's whole factor block UNMEASURED. Where it was enforced: `fetch_yf` raises when
a ticker's last row is not the asof session, `fetch_each` then drops every row of that
ticker into `failed`, and the job refused the block for any held name in `failed`; past the
fetch, `readout` raises on a missing close on a positions date and `fit_window` on a held
name with no price column or a missing return in its window. The ruling: read the held
names that have every input the computation needs, mark the block PARTIAL, and name the
rest. So, behind explicit parameters that every research path and the CLI leave at False:
  * `fetch_each(partial=True)` keeps a ticker that is not `required` and whose rows stop
    before the asof, with the rows it has, validated up to its own last session. A required
    ticker (a factor ETF) stays strict and raises.
  * `readout(partial=True)` reads each held name on each date it has every input for: a
    price history, a finite close on the date, and a finite return on every session of its
    beta window. A name without one is left out of that date's exposure, value, groups and
    betas, and recorded in `Readout.excluded` (date, symbol, shares, reason). So a name
    whose close is late only today is read on every earlier date and left out today; the
    factor P&L of today, E(yesterday) x f(today), keeps it. If no held name has its inputs
    on a date, `NoInputsError` (a ReadoutError) is raised: there is no book to read. A
    factor ETF's missing return still raises as in strict mode.
With both at False (the default) nothing above runs and the outputs are byte-identical to
the strict build's (the proof is in the commit that added this).

TWO BOOKS (team lead, 2026-11-09)
---------------------------------
The team lead ordered a daily report for both paper books. Everything above is the
core's (book "cef"). C4 (book "c4") is a set of equity, sector, covered-call,
preferred and multi-asset CEFs, so the core's four credit factors are the wrong set
for it. The ruling: a factor set designed for C4, EQUITY = SPY (the headline), TERM =
IEF, CREDIT = HYG, PREFERRED = PFF, orthogonalised by the same Gram-Schmidt in that
order (general to specific, as the core's), TERM, CREDIT and PREFERRED marked
indicative as the core's non-headline factors are, and the book read in the report
split by family (equity_domestic, equity_sector, equity_covered_call, preferred,
multi_asset; C4's spec's frozen.level_signal.family_of) as the core's is split muni
against taxable. C4's method is the core's: the same lag rule, declared in its own
commit before any C4 result is read; the rolling z_window sessions strictly before t;
the review line at REVIEW_FRACTION x C4's own vol_target_annual x C4's own
sizing_multiplier (the multiplier since 2026-11-10), each read from its spec at run time.
Zero trials, no counter moved. `FactorSet` holds what differs and the
functions take it, defaulting to the core's, so the core's outputs do not move; the
proof is a byte diff on a synthetic positions file before and after this change.
Until C4's lag rule has run, `factor_set("c4").dimson_lags` is None and `analyse
--book c4` raises naming the missing rule.

THE C4 LAG RULE (DECLARED 2026-11-09, ITS OWN COMMIT, BEFORE ANY C4 PRICE WAS FETCHED
OR ANY C4 RESULT READ; team lead, 2026-11-09: "the same lag rule", "fit rows only").
Nothing in this rule was computed on C4's data before the commit that declares it: no C4
price had been fetched, and the only C4 facts in sight were the frozen universe, the
family map and the vol target, all from the spec. It is the core's rule (THE RULE, above),
applied to C4's factors, and its counts are `lead_placebo_counts` and `placebo_lag_rule`,
the core's code, with C4's factor set. `derive --book c4` runs it; `derive_c4` holds it.
  Data      Total returns (`returns_panel`, the harness's formula, one difference: a
            yfinance split record the split-basis check reads as `adjusted`, meaning the
            cached close has no split-sized step because yfinance adjusts Close for splits
            after the fact, is not applied, and each such name-date is named in the output
            [C4's fit booked BTO, TYG, NXG and EMO at -75% to -80% when this was not
            handled; `data_guards.guard_split_basis`]. The core has no such name). Cut at
            FIT_END (2022-12-30) BEFORE anything is shifted, so no response, lag or lead
            is dated 2023 or later (H13; `lead_placebo_counts` raises if one is). Fetched
            keyless by `fetch --book c4`, tickers SPY, IEF, HYG, PFF and the frozen universe,
            FETCH_START (2010-01-01) to the asof session.
  Factors   C4's, orthogonalised once on the whole fit era in C4's order (module docstring,
            TWO BOOKS).
  Names     The frozen C4 universe (the 74 of ops/specs/c4_families.frozen.json, read at
            run time), each with the rule's model (K = DERIVE_MAX_LAG = 10, J = 19, HAC(5),
            5%) on every session where all of the name's return and the 120 factor rows it
            needs exist. A name enters the pair set only if that sample has at least
            C4_RULE_MIN_SESSIONS = 252 rows (one readout window; 121 regressors need
            room beyond them); fewer, it is excluded and named in the output. A
            name whose yfinance history fails the cache's validation (`validate_prices`), or
            that yfinance has no rows for, is excluded and named. A factor ETF's failure
            raises. The pairs are names x 4 factors, on whatever names remain: the output
            states the count; the counts are compared within that count, so the rule does
            not depend on 74 being reached. THE SAMPLE IS STATED IN THE OUTPUT (first and
            last rows, sessions per name).
  Model, counts, bound, decision, ties, gaps, censoring: exactly as THE RULE above,
            including that lag 0 must beat T and that every lag 1..K clearing T raises.
  OUTCOMES (H14: re-measured when `derive --book c4` runs, and what follows either way
            is fixed here). If the rule returns L = 0: C4_DIMSON_LAGS = 0, C4's report uses
            same-day betas, exactly as the core's does. If it returns L >= 1:
            C4_DIMSON_LAGS = L and C4's report uses the summed Dimson beta 0..L. If it raises
            (lag 0 does not beat the largest lead count, or every lag 1..K clears it, or fewer than
            one name qualifies), the rule has no answer: C4_DIMSON_LAGS stays None, C4's
            factor readout in the report is UNMEASURED naming the raise, and nothing defaults
            to the core's L or to 0; the team lead decides whether a new rule is declared.
            Whichever it is, the result lands in the commit that follows this one, with the
            counts, the cache hash and the sample, and the rule is not re-tuned after it runs.
  What is NOT re-derived for C4: K, J, the 5%, HAC(5), the maximum-of-leads bound and the
            stop-at-first-failure sequence are the core's own, kept by instruction; the
            core's risks (a) to (c) (lead counts that are not null draws, exchangeability,
            the 19 leads' correlation) apply unchanged, and the same caveat holds: an episode
            could set T. No diagnostics are run after the result: section 2b of the core's
            `derive` is the core's review, and C4's was not ordered.

THE C4 RULE'S RESULT: L = 2, so C4_DIMSON_LAGS = 2 [V: `derive --book c4`, run 2026-11-09 at
18:48 ET, one minute after the commit that declared the rule (d37a86d, 18:47:25 -0500), on
a keyless yfinance cache fetched after that commit (asof C4_RULE_CACHE_ASOF, fetched
2026-11-09T23:48:19Z, prices.parquet sha256 C4_RULE_CACHE_SHA256); output in
results/cef/C4_LAG_RULE_RESULT_2026-11-09.txt]. Sample: 72 of the 74 names, 288 pairs (NPFD
and RLTY excluded with 242 and 195 usable rows < 252); response rows 2010-01-20 .. 2022-12-02,
the last row whose lead-19 row is on or before FIT_END; 257 to 3,242 sessions per name;
three recorded splits read as `adjusted` and not applied (NXG 2020-06-15, EMO 2020-07-28,
and IGR 2026-09-08, after the fit era).
  lag counts  c(0..10)  254 128 83 41 36 39 48 41 35 38 29                       (of 288 pairs)
  lead counts p(1..19)  56 42 47 46 24 36 25 20 26 16 44 16 65 61 36 22 25 28 16
  T = 65, at lead 13. Lags 1 and 2 clear it (128, 83); lag 3's count is 41, not above 65, so the
  sequence stops at lag 3: L = 2. A lag-4-or-later count above T would not matter (the stop
  rule). Under THE RULE's outcome table above this makes C4's exposure the Dimson sum over
  lags 0..2. The caveats of the core's result apply unchanged and unexamined here (the
  lead counts as null draws, an episode inflating T): the rule was applied as declared and
  is not re-tuned; the team lead may ask for a different rule, declared first.

USAGE
-----
    python3 scripts/cef/exposure_readout.py fetch --asof YYYY-MM-DD [--book cef|c4] [--start YYYY-MM-DD] [--cache-dir D] [--symbols S ...]
    python3 scripts/cef/exposure_readout.py crosscheck [--book cef|c4] [--cache-dir D]
    python3 scripts/cef/exposure_readout.py derive [--book cef|c4] [--cache-dir D]
    python3 scripts/cef/exposure_readout.py analyse --positions P.csv [--book cef|c4] [--cache-dir D] [--out-dir D] [--plateau]

The positions CSV has columns date, symbol, shares (signed; short < 0), and optionally
equity (one value per date). A date's rows are the book at that date's close; a symbol
absent on a date is not held. Both default directories (results/cef/exposure_readout/
_cache and _out) are gitignored. A directory outside every git repository is allowed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops.schedule import nyse_calendar as NYSE  # noqa: E402  (stdlib only)
from scripts.cef.data_guards import guard_split_basis, split_basis_check  # noqa: E402  (numpy/pandas only)
from scripts.cef.spec import SPEC_ID, UNIVERSE, VOL_TARGET, Z_WINDOW  # noqa: E402  (a JSON read)
from scripts.cef.spec import spec as _core_spec_doc  # noqa: E402  (the same JSON read, whole)

NY = ZoneInfo("America/New_York")
DATA_DIR = REPO / "data"
UNIVERSE_CSV = DATA_DIR / "cef" / "cef_universe.csv"
# Both gitignored (.gitignore); `_refuse_git_visible` enforces it at write time, in whichever
# repository encloses the target.
DEFAULT_CACHE = REPO / "results" / "cef" / "exposure_readout" / "_cache"
DEFAULT_OUT = REPO / "results" / "cef" / "exposure_readout" / "_out"
DEFAULT_CACHE_C4 = REPO / "results" / "cef" / "exposure_readout" / "_cache_c4"   # results/**/_cache_*
DEFAULT_OUT_C4 = REPO / "results" / "cef" / "exposure_readout" / "_out_c4"
CACHE_FILES = ("prices.parquet", "meta.json")
OUT_FILES = ("exposure.csv", "exposure_by_group.csv", "betas.csv", "factor_defs.csv",
             "factor_pnl.csv", "summary.md")

# (factor, ETF) in Gram-Schmidt order, general to specific (module docstring).
FACTORS: tuple[tuple[str, str], ...] = (("TERM", "IEF"), ("CREDIT", "HYG"), ("MUNI", "MUB"),
                                        ("LOANS", "BKLN"))
FACTOR_NAMES = tuple(f for f, _ in FACTORS)
FACTOR_ETFS = tuple(e for _, e in FACTORS)

DIMSON_LAGS = 0          # THE RULE's output on the fit era (module docstring, THE RULE'S
                         # RESULT); was 3 under the superseded first-gap rule
WINDOW = Z_WINDOW        # the sleeve's own z_window, read from the frozen spec
ANNUALISE = 252          # sessions a year, the convention of every vol on this desk
D4_BETA_BAR = 0.10       # D4: factor betas <= 0.10 (docs/BRIEF.md; research-harness rules)
REVIEW_FRACTION = D4_BETA_BAR   # D4 applied to each factor rescaled to the vol target
FETCH_START = dt.date(2010, 1, 1)   # covers the fit era from BKLN's 2011-03 inception
FIT_END = pd.Timestamp("2022-12-30")   # H13: derive reads nothing after this
DERIVE_MAX_LAG = 10      # K: W4's NAV-staleness sensitivity bound (module docstring)
DERIVE_RULE_LEADS = 19   # J: the lead placebo's draws; the max of 19 is a 1/(J+1) = 5% rank test
DERIVE_RULE_ALPHA = 0.05 # two-sided p at which each (name, factor) lag or lead is counted
DERIVE_RULE_HAC = 5      # Newey-West lags of every derive regression (unchanged from 2026-11-02)
DERIVE_ALT_MAX_LAG = 5   # the bound the first lag rule was tried at (superseded; history)
DERIVE_PLACEBO_LEADS = 5 # leads in the review's 2026-11-02 placebo (superseded; history)

# The cache THE RULE's recorded counts were made on (review of the result, 2026-11-02,
# finding 3). The tests pin those counts as literals, so a re-fetch that revised a few Yahoo
# distributions could flip two or three pair verdicts and move L while every test still
# passed. `derive` prints whether the cache it reads is this one.
RULE_CACHE_ASOF = "2026-10-30"
RULE_CACHE_SHA256 = "0bda865692aa6d79047a79c9f0d153efaf7707790846e71223f0c603b1058a7c"  # prices.parquet

# The diagnostics printed AFTER THE RESULT (module docstring; they decide nothing and THE RULE
# is never re-run on them). Both were chosen by the review of the result, after it had seen
# the counts: the episode's window, and the split of the leads into 1..14 and 15..J.
DIAG_EPISODE = ("2020-02-20", "2020-04-30")
DIAG_LEAD_CUT = 14
DIAG_PERMUTATIONS = 20_000   # draws of the trend test's permutation null (fixed seed 0)

# The tolerances the cross-check reports against. They label disagreements; they decide
# nothing. Half a cent: yfinance stores closes as float32 and Yahoo rounds to the cent
# (docs/REFERENCES.md §8, the Alpaca daily-bars row). Dividends: Yahoo rounds to 3dp
# (same row: "dividends differ by <= $0.00054/share").
TOL_CLOSE = 0.005
TOL_DIV = 0.0006
TOL_TR_BP = 1.0

# Defined before anything that can raise at import (CORE parses the core's spec below).
class ReadoutError(RuntimeError):
    """Missing, inconsistent or refused input. The message names what."""


class LookaheadError(ReadoutError):
    """A window reached the date it is used on (H7)."""


class NoInputsError(ReadoutError):
    """`readout(partial=True)`: no held name has every input on a date (module docstring,
    PARTIAL), so there is no book to read and the caller's block stays UNMEASURED."""


REVIEW_RULE = (
    "A factor whose ex-ante vol contribution c_k(t) = |E_k(t)/equity(t)| x sigma_k(t) exceeds "
    "REVIEW_FRACTION x vol_target_annual x sizing_multiplier (each the book's own frozen spec's, "
    "read at run time; an absent sizing_multiplier is the unit book, 1; team lead, 2026-11-10) goes "
    "to the team lead's review. Nothing is ever hedged, traded or resized automatically. With no "
    "equity for t the rule is UNMEASURED on t.")

# The account sizing key and its near-miss distance: src/deploy/registry.py's CEF_SIZING_KEY
# and CEF_C4_NEAR, copied with `sizing_multiplier` below (a test holds the copies equal).
SIZING_KEY = "sizing_multiplier"
SIZING_NEAR = 2


def _osa_distance(a: str, b: str) -> int:
    """A COPY of src/deploy/registry._osa_distance (optimal-string-alignment edit distance:
    insertions, deletions, substitutions and adjacent transpositions, each costing 1), for
    `sizing_multiplier`'s near-miss check."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def sizing_multiplier(frozen: dict) -> float | None:
    """The book's `sizing_multiplier` as the runner parses it: a float, or None when the key
    is absent or null, which the runner reads as the unit book (module docstring, THE LINE
    IS ON THE ACCOUNT'S SCALE; team lead, 2026-11-10).

    A COPY OF src/deploy/registry.cef_sizing_multiplier, with the same messages, raising
    ReadoutError where the registry raises ValueError. It cannot be imported: this module
    imports nothing from src/ (`test_module_holds_no_order_code_no_keys_and_no_live_path_import`),
    and the registry's own import closure reaches the strategy sleeve. A test holds the two
    equal on valid, absent, null, malformed and misspelt inputs, so a change to the runner's
    parse that is not made here fails a test rather than moving one line silently.
    Refused, as there: a bool, a string or any non-number, NaN or inf, zero or below, and a
    frozen key that looks like a misspelling of it (a misspelt key would read as the unit
    book while the spec reads as raised)."""
    note = f"_{SIZING_KEY}_note"
    for key in frozen:
        if not isinstance(key, str) or key in (SIZING_KEY, note):
            continue
        stem = key.strip().lower().replace("-", "_").replace(" ", "_").strip("_")
        if stem.endswith("_note"):
            stem = stem[:-len("_note")].strip("_")
        if (stem == SIZING_KEY or stem.replace("_", "") == SIZING_KEY.replace("_", "")
                or _osa_distance(stem, SIZING_KEY) <= SIZING_NEAR):
            raise ReadoutError(
                f"cef_discount frozen key {key!r} looks like a misspelling of "
                f"{SIZING_KEY!r}; the sleeve would ignore it and size the book at 1.0. "
                f"Spell it {SIZING_KEY!r}, or delete it (absent is today's book)")
    if SIZING_KEY not in frozen or frozen[SIZING_KEY] is None:
        return None
    v = frozen[SIZING_KEY]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ReadoutError(f"cef_discount {SIZING_KEY} must be a number, got {v!r} "
                           f"({type(v).__name__})")
    if not math.isfinite(float(v)) or not float(v) > 0.0:
        raise ReadoutError(f"cef_discount {SIZING_KEY} {v!r} must be a finite number above 0 "
                           f"(a multiple of the unit book; 1.0 is today's size)")
    return float(v)


@dataclass(frozen=True)
class FactorSet:
    """One book's factor model and the frozen values the readout reads for it (module
    docstring, TWO BOOKS). `factors` is in Gram-Schmidt order; `headline` is the factor the
    report leads with; `dimson_lags` is None until the book's lag rule has been run;
    `sizing_multiplier` is the spec's as `sizing_multiplier()` parses it, None when the key
    is absent (team lead, 2026-11-10: the review line carries it)."""
    book: str
    factors: tuple
    headline: str
    spec_id: str
    vol_target: float
    window: int
    universe: tuple
    dimson_lags: int | None
    group_split: str          # "muni": muni against taxable (cef); "family": by family (c4)
    sizing_multiplier: float | None
    groups_path: str = ""     # what the group labels come from, printed in summary.md

    @property
    def names(self) -> tuple:
        return tuple(f for f, _ in self.factors)

    @property
    def etfs(self) -> tuple:
        return tuple(e for _, e in self.factors)

    @property
    def indicative(self) -> tuple:
        return tuple(k for k in self.names if k != self.headline)

    @property
    def multiplier(self) -> float:
        """m, the account's multiple of the unit book: the spec's sizing_multiplier, or 1.0
        when the key is absent, because the runner then holds the unit book exactly
        (src/deploy/registry.cef_sizing_multiplier: absent is today's book). Not a default
        chosen here: it is what the account holds."""
        return 1.0 if self.sizing_multiplier is None else self.sizing_multiplier

    @property
    def review_line(self) -> float:
        """REVIEW_FRACTION x vol_target_annual x m, the line c_k is compared with (team lead,
        2026-11-10; module docstring, THE LINE IS ON THE ACCOUNT'S SCALE)."""
        return REVIEW_FRACTION * self.vol_target * self.multiplier

    def line_inputs(self) -> str:
        """The line and its three inputs, in words, for every output that shows the line."""
        m = "absent (the unit book, 1)" if self.sizing_multiplier is None else f"{self.sizing_multiplier:.4g}"
        return (f"REVIEW_FRACTION {REVIEW_FRACTION} x vol_target_annual {self.vol_target:.4g} x "
                f"sizing_multiplier {m} = {self.review_line:.6g}")


# The core's multiplier, from the frozen spec scripts/cef/spec.py read (H14: never a literal).
CORE = FactorSet("cef", FACTORS, "MUNI", SPEC_ID, VOL_TARGET, WINDOW, tuple(UNIVERSE), DIMSON_LAGS, "muni",
                 sizing_multiplier(_core_spec_doc()["frozen"]), "data/cef/cef_universe.csv")

# C4's factors (team lead, 2026-11-09), in Gram-Schmidt order, general to specific. EQUITY is
# the headline; TERM, CREDIT and PREFERRED are indicative, as the core's non-headline
# factors are. FETCH_START covers the fit era (SPY 1993, IEF 2002, HYG 2007, PFF 2007).
C4_SPEC = REPO / "ops" / "specs" / "c4_families.frozen.json"
C4_FACTORS: tuple[tuple[str, str], ...] = (("EQUITY", "SPY"), ("TERM", "IEF"), ("CREDIT", "HYG"),
                                           ("PREFERRED", "PFF"))
C4_HEADLINE = "EQUITY"
C4_DIMSON_LAGS: int | None = 2      # THE C4 LAG RULE's output on the fit era (module docstring, THE C4 RULE'S
                                    # RESULT); the rule declared in d37a86d, run after it on keyless public prices
C4_RULE_MIN_SESSIONS = 252          # THE C4 LAG RULE: a name's regression sample must be at least this many
                                    # rows (one readout window; it has 121 regressors at K = 10, J = 19)
C4_RULE_CACHE_ASOF = "2026-11-06"
C4_RULE_CACHE_SHA256 = "d44a6fe83830a90f9642989723b3c8db91bd970ddfe16dcf673ac6ca5cfd3238"  # prices.parquet


def c4_frozen() -> dict:
    """C4's frozen spec section, read at run time (H14, the spec is the authority)."""
    if not C4_SPEC.is_file():
        raise ReadoutError(f"C4's frozen spec is missing at {C4_SPEC}")
    spec = json.loads(C4_SPEC.read_text())
    frozen = spec.get("frozen")
    if not isinstance(frozen, dict):
        raise ReadoutError(f"{C4_SPEC} has no `frozen` section")
    for k in ("vol_target_annual", "z_window", "universe", "level_signal"):
        if k not in frozen:
            raise ReadoutError(f"{C4_SPEC} frozen section lacks {k!r}")
    if not isinstance(frozen["level_signal"], dict) or not frozen["level_signal"].get("family_of"):
        raise ReadoutError(f"{C4_SPEC} frozen.level_signal has no family_of map")
    return frozen


def c4_families() -> dict:
    """C4's family of each fund: the frozen spec's level_signal.family_of (team lead,
    2026-11-09, the report's split by family), read, never retyped."""
    return dict(c4_frozen()["level_signal"]["family_of"])


def factor_set(book: str) -> FactorSet:
    """The factor set of `book` ("cef" or "c4"). C4's is built from its frozen spec here,
    at run time, so a missing or changed key is a raise naming it, never a stale literal."""
    if book == "cef":
        return CORE
    if book == "c4":
        f = c4_frozen()
        return FactorSet("c4", C4_FACTORS, C4_HEADLINE, json.loads(C4_SPEC.read_text()).get("spec_id", "<unknown>"),
                         float(f["vol_target_annual"]), int(f["z_window"]), tuple(f["universe"]),
                         C4_DIMSON_LAGS, "family", sizing_multiplier(f),
                         "ops/specs/c4_families.frozen.json level_signal.family_of")
    raise ReadoutError(f"unknown book {book!r} (books: cef, c4)")


# --------------------------------------------------------------------------- refusals

def _refuse_data_dir(path: Path, data_dir: Path = DATA_DIR) -> None:
    """Never write under data/ (CLAUDE.md landmine 9): in every worktree it is a symlink to
    the panels the live sleeve decides on."""
    p = Path(path).resolve()
    d = Path(data_dir).resolve()
    if p == d or d in p.parents:
        raise ReadoutError(f"refusing to write {path}: it is under data/ ({d})")


def _enclosing_repo(path: Path) -> Path | None:
    """The innermost git work tree containing `path` (which need not exist yet), found the way
    git finds it: the nearest ancestor holding a `.git` entry, a directory in a main checkout
    or a file in a linked worktree. None if no ancestor has one."""
    p = Path(path).resolve()
    for d in (p, *p.parents):
        if (d / ".git").exists():
            return d
    return None


def _refuse_git_visible(directory: Path, names) -> None:
    """Refuse to write any of `names` into `directory` if git could see it.

    Copied from scripts/cef/live_attribution.py (branch research-live-attribution), whose
    first build had a git-visible default out-dir (review 2026-11-02). The analyse outputs
    carry the caller's positions and the cache sits beside them, and this repository is
    public.

    The check runs in the repository that encloses the TARGET, not in this module's own
    checkout. The first build checked only its own checkout (review 2026-11-02, finding 3):
    a linked worktree sits inside the main checkout, so from the worktree `--out-dir
    <main checkout>/results/cef/x` counted as "outside the repository", was let through, and
    git in the main checkout could see the files. Now: no enclosing repository, nothing to
    check; otherwise every file must be ignored there (`git check-ignore`; a tracked file
    counts as visible). If git cannot answer, the write is refused: there is no default."""
    p = Path(directory).resolve()
    root = _enclosing_repo(p)
    if root is None:
        return
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=30)
        if top.returncode != 0 or Path(top.stdout.strip()).resolve() != root:
            raise ReadoutError(f"refusing to write in {directory}: {root} holds a .git entry but git "
                               f"does not report it as a work tree's top level (exit {top.returncode}: "
                               f"{(top.stderr or top.stdout).strip()[:200]})")
        paths = [(p / n).relative_to(root).as_posix() for n in names]
        r = subprocess.run(["git", "-C", str(root), "check-ignore", *paths],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        raise ReadoutError(f"refusing to write in {directory}: git could not run "
                           f"({type(e).__name__}: {e})") from None
    if r.returncode not in (0, 1):      # 0 some ignored, 1 none ignored, else an error
        raise ReadoutError(f"refusing to write in {directory}: git check-ignore exited "
                           f"{r.returncode}: {r.stderr.strip()[:200]}")
    visible = sorted(set(paths) - set(r.stdout.splitlines()))
    if visible:
        raise ReadoutError(
            f"refusing to write {visible[:3]}{' ...' if len(visible) > 3 else ''}: git in {root} "
            "can see them, and this public repository must not carry an account's positions. "
            "Use the gitignored default, or a directory outside every git repository")


def _refuse_write(directory: Path, names) -> None:
    _refuse_data_dir(directory)
    _refuse_git_visible(directory, names)


# --------------------------------------------------------------------------- fetch

def nyse_sessions(start: dt.date, end: dt.date) -> pd.DatetimeIndex:
    """NYSE sessions from start to end inclusive (ops/schedule/nyse_calendar.py rules)."""
    days, d = [], start
    while d <= end:
        if NYSE.is_trading_day(d):
            days.append(d)
        d += dt.timedelta(days=1)
    return pd.DatetimeIndex(pd.to_datetime(days))


def check_asof(asof: dt.date, now: dt.datetime | None = None) -> None:
    """The asof must be an NYSE session strictly before today in New York. yfinance serves
    the current session's bar while it trades, and a cache written at 10:46 once froze an
    intraday bar as a close (docs/REFERENCES.md §8, the byte-identity row)."""
    today = (now or dt.datetime.now(NY)).astimezone(NY).date()
    if asof >= today:
        raise ReadoutError(f"asof {asof} is not before today ({today}, New York): its bar may be "
                           "intraday. Fetch a completed session.")
    if not NYSE.is_trading_day(asof):
        raise ReadoutError(f"asof {asof} is not an NYSE session")


def validate_prices(px: pd.DataFrame, asof: dt.date) -> None:
    """Raise unless every ticker's rows are exactly the NYSE sessions from its first row to
    `asof`, with finite positive closes, non-negative dividends and no duplicate."""
    need = {"date", "ticker", "close", "adj_close", "dividend", "split"}
    miss = need - set(px.columns)
    if miss:
        raise ReadoutError(f"price cache lacks columns {sorted(miss)}")
    dup = px.duplicated(["ticker", "date"])
    if dup.any():
        raise ReadoutError(f"duplicate (ticker, date) rows: {px.loc[dup, ['ticker', 'date']].head(5).values.tolist()}")
    bad = ~np.isfinite(px["close"].to_numpy(float)) | (px["close"].to_numpy(float) <= 0)
    if bad.any():
        raise ReadoutError("non-finite or non-positive closes: "
                           f"{px.loc[bad, ['ticker', 'date']].head(5).astype(str).values.tolist()}")
    for col in ("dividend", "split"):
        v = px[col].to_numpy(float)
        if (~np.isfinite(v)).any() or (v < 0).any():
            raise ReadoutError(f"non-finite or negative {col} values: "
                               f"{px.loc[~np.isfinite(v) | (v < 0), ['ticker', 'date']].head(5).astype(str).values.tolist()}")
    for tk, g in px.groupby("ticker"):
        have = pd.DatetimeIndex(g["date"]).sort_values()
        want = nyse_sessions(have[0].date(), asof)
        missing = want.difference(have)
        extra = have.difference(want)
        if len(missing) or len(extra):
            raise ReadoutError(
                f"{tk}: rows are not the NYSE sessions {have[0].date()}..{asof}: missing "
                f"{[d.date().isoformat() for d in missing[:5]]}{' ...' if len(missing) > 5 else ''} "
                f"({len(missing)}), extra {[d.date().isoformat() for d in extra[:5]]} ({len(extra)})")


def fetch_yf(tickers, start: dt.date, asof: dt.date, *, through_asof: bool = True) -> tuple[pd.DataFrame, dict]:
    """Keyless yfinance `Ticker.history(auto_adjust=False, actions=True)` for each ticker,
    start..asof. Returns the long frame and a note of which tickers carry a Capital Gains
    column. An exception propagates; nothing is written then. `through_asof` False is
    `fetch_each(partial=True)`'s only (module docstring, PARTIAL): a ticker whose last row is
    before the asof is returned as it is instead of raising; a row after it still raises."""
    import yfinance as yf
    frames, cg = [], {}
    for tk in sorted(set(tickers)):
        h = yf.Ticker(tk).history(start=start.isoformat(),
                                  end=(asof + dt.timedelta(days=1)).isoformat(),
                                  auto_adjust=False, actions=True)
        if h is None or h.empty:
            raise ReadoutError(f"yfinance returned no rows for {tk}")
        miss = [c for c in ("Close", "Adj Close", "Dividends", "Stock Splits") if c not in h.columns]
        if miss:
            raise ReadoutError(f"yfinance rows for {tk} lack {miss}")
        if "Capital Gains" in h.columns:
            v = h["Capital Gains"].to_numpy(float)
            if (np.isfinite(v) & (v != 0)).any():
                raise ReadoutError(f"{tk}: yfinance reports a non-zero Capital Gains value; whether "
                                   "Dividends also counts it is not documented here (module docstring)")
            cg[tk] = "present, all zero"
        else:
            cg[tk] = "absent"
        idx = pd.DatetimeIndex(h.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)        # the exchange's wall date
        frames.append(pd.DataFrame({
            "date": idx.normalize(), "ticker": tk,
            "close": h["Close"].to_numpy(float), "adj_close": h["Adj Close"].to_numpy(float),
            "dividend": h["Dividends"].to_numpy(float), "split": h["Stock Splits"].to_numpy(float)}))
        last = frames[-1]["date"].max().date()
        if (last != asof) if through_asof else (last > asof):
            raise ReadoutError(f"{tk}: the last yfinance row is {last}, not the asof session {asof}")
    px = pd.concat(frames, ignore_index=True).sort_values(["ticker", "date"]).reset_index(drop=True)
    return px, cg


def fetch_each(tickers, start: dt.date, asof: dt.date, *, required=(),
               partial: bool = False) -> tuple[pd.DataFrame, dict, dict]:
    """`fetch_yf` and `validate_prices` one ticker at a time: (px, cg, failed). A ticker that
    fails is put in `failed` with the reason (THE C4 LAG RULE names such exclusions) and
    the fetch goes on, except a `required` ticker (a factor ETF), whose failure raises.

    `partial` (default False, which the CLI and every research path keep; True from the daily
    report job only, team lead 2026-11-10, module docstring PARTIAL): a ticker that is not
    `required` and whose rows stop before `asof` is kept with the rows it has, validated up to
    its own last session, so that `readout(partial=True)` can read it on the dates it has."""
    frames, cg, failed = [], {}, {}
    for tk in sorted(set(tickers)):
        late_ok = partial and tk not in required
        try:
            one, c = fetch_yf([tk], start, asof, through_asof=False) if late_ok else fetch_yf([tk], start, asof)
            validate_prices(one, one["date"].max().date() if late_ok else asof)
        except Exception as e:
            if tk in required:
                raise
            failed[tk] = f"{type(e).__name__}: {e}"
            continue
        frames.append(one)
        cg.update(c)
    if not frames:
        raise ReadoutError("fetch_each: no ticker could be fetched")
    return pd.concat(frames, ignore_index=True).sort_values(["ticker", "date"]).reset_index(drop=True), cg, failed


def write_cache(cache_dir: Path, px: pd.DataFrame, meta: dict) -> None:
    cache_dir = Path(cache_dir)
    _refuse_write(cache_dir, CACHE_FILES)
    cache_dir.mkdir(parents=True, exist_ok=True)
    px.to_parquet(cache_dir / "prices.parquet", index=False)
    (cache_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True))


def load_cache(cache_dir: Path) -> tuple[pd.DataFrame, dict]:
    cache_dir = Path(cache_dir)
    for n in CACHE_FILES:
        if not (cache_dir / n).exists():
            raise ReadoutError(f"{cache_dir / n} is missing: run `exposure_readout.py fetch` first")
    px = pd.read_parquet(cache_dir / "prices.parquet")
    px["date"] = pd.to_datetime(px["date"])
    meta = json.loads((cache_dir / "meta.json").read_text())
    validate_prices(px, dt.date.fromisoformat(meta["asof"]))
    return px, meta


def cache_sha256(cache_dir: Path) -> str:
    """sha256 of the cache's prices.parquet: which cache a set of `derive` counts came from.
    The asof alone does not say it (review 2026-11-02, finding 3): two fetches with one asof
    can differ where Yahoo revised a distribution (docs/REFERENCES.md §8)."""
    p = Path(cache_dir) / "prices.parquet"
    if not p.exists():
        raise ReadoutError(f"{p} is missing: run `exposure_readout.py fetch` first")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cache_provenance_line(sha: str | None, recorded_sha: str = RULE_CACHE_SHA256,
                          recorded_asof: str = RULE_CACHE_ASOF) -> str:
    """The line `derive` prints beside THE RULE's counts: is this the cache the recorded
    counts (module docstring, THE RULE'S RESULT; the tests' RECORDED_*_COUNTS) came from?
    C4's run passes its own recorded cache."""
    if not sha:
        return ("cache prices.parquet sha256 UNMEASURED (no cache path given): whether these counts "
                f"come from the recorded cache (asof {recorded_asof}) is unknown")
    if sha == recorded_sha:
        return (f"cache prices.parquet sha256 {sha[:16]}...: the cache the recorded counts came from "
                f"(asof {recorded_asof}); they should reproduce exactly")
    return (f"cache prices.parquet sha256 {sha[:16]}... DIFFERS from the recorded cache's "
            f"{recorded_sha[:16]}... (asof {recorded_asof}): these counts need not match the "
            "recorded ones, and a different L here is a different cache, not a different rule")


# --------------------------------------------------------------------------- returns

def returns_panel(px: pd.DataFrame, *, drop_adjusted_splits: bool = False,
                  dropped: list | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
    """(R, C, sessions): wide daily total returns, wide raw closes, and the session index.

    R is the harness's formula on yfinance's raw Close and Dividends (module docstring,
    TOTAL RETURNS), with the split-basis guard. A ticker's first row has no return (NaN):
    that is the absence of a previous close, and any window that needs it raises later.

    `drop_adjusted_splits` (C4 only; module docstring, THE C4 LAG RULE): a split the check
    reads as `adjusted` (the cached close made no split-sized step; yfinance adjusts Close
    for splits after the fact) is not applied, and each such (ticker, date, factor) is
    appended to `dropped`. The core's call keeps False: the guard raises on such a cell."""
    C = px.pivot(index="date", columns="ticker", values="close").sort_index()
    D = px.pivot(index="date", columns="ticker", values="dividend").reindex_like(C)
    S = px.pivot(index="date", columns="ticker", values="split").reindex_like(C)
    sessions = pd.DatetimeIndex(C.index)
    prev = C.shift(1)
    Rpx = C / prev - 1.0
    # yfinance codes "no split" as 0.0; the multiplier is the ratio where one is recorded
    # and 1.0 (the identity, not an estimate) where none is.
    k = S.where((S != 0.0) & S.notna(), 1.0).astype(float)
    if drop_adjusted_splits:
        chk = split_basis_check(Rpx, k)
        adj = chk[chk["basis"] == "adjusted"]
        if len(adj):
            k = k.copy()
            for r in adj.itertuples():
                k.at[r.ex_date, r.ticker] = 1.0
                if dropped is not None:
                    dropped.append((r.ticker, pd.Timestamp(r.ex_date).date().isoformat(), float(r.factor)))
    k = guard_split_basis(Rpx, k, series="close", context="exposure_readout.returns_panel")
    clash = (k != 1.0) & (D.fillna(0.0) != 0.0)
    if clash.to_numpy().any():
        where = [(C.index[i].date().isoformat(), C.columns[j]) for i, j in np.argwhere(clash.to_numpy())]
        raise ReadoutError(f"a split and a distribution fall on the same name-date {where[:5]}; "
                           "the per-share amount is ambiguous and this module will not guess")
    R = (1.0 + Rpx) * k - 1.0 + D / prev
    return R, C, sessions


# --------------------------------------------------------------------------- windows (H7)

def assert_strictly_before(dates, t, what: str) -> None:
    """H7 at run time: every row of a window used on date t is dated strictly before t.
    An explicit raise, so `python -O` cannot strip it."""
    t = pd.Timestamp(t)
    d = pd.DatetimeIndex(dates)
    if len(d) == 0:
        raise LookaheadError(f"{what} for {t.date()} is empty")
    if d.max() >= t:
        raise LookaheadError(f"{what} for {t.date()} reaches {d.max().date()}: a window used on t "
                             "must end strictly before t (H7)")


def window_rows(sessions: pd.DatetimeIndex, t, window: int, lags: int
                ) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    """(y_dates, f_dates): the `window` sessions strictly before t, and those plus `lags`
    earlier sessions (the lagged factor rows). Both are asserted strictly before t."""
    t = pd.Timestamp(t)
    i = int(sessions.searchsorted(t))
    if i >= len(sessions) or sessions[i] != t:
        raise ReadoutError(f"{t.date()} is not a session in the price cache")
    if i - window - lags < 0:
        raise ReadoutError(f"the window for {t.date()} needs {window + lags} sessions before it; "
                           f"the cache has {i}")
    y_dates = sessions[i - window:i]
    f_dates = sessions[i - window - lags:i]
    assert_strictly_before(y_dates, t, "beta window")
    assert_strictly_before(f_dates, t, "lagged factor window")
    return y_dates, f_dates


def _require_finite(frame: pd.DataFrame, what: str) -> None:
    bad = ~np.isfinite(frame.to_numpy(float))
    if bad.any():
        cells = [(frame.columns[j], frame.index[i].date().isoformat()) for i, j in np.argwhere(bad)[:5]]
        raise ReadoutError(f"{what}: {int(bad.sum())} missing or non-finite returns, e.g. {cells}. "
                           "The readout does not drop or fill them.")


# --------------------------------------------------------------------------- the fit

def orthogonaliser(E: pd.DataFrame, fs: FactorSet = CORE) -> pd.DataFrame:
    """M (ETF rows x factor columns) such that E @ M is the Gram-Schmidt factor set in the
    book's factor order: each ETF less its OLS slopes (with intercept) on the earlier ETFs,
    on E's rows."""
    M = pd.DataFrame(0.0, index=list(fs.etfs), columns=list(fs.names))
    for k, (fname, etf) in enumerate(fs.factors):
        M.loc[etf, fname] = 1.0
        prev = list(fs.etfs[:k])
        if prev:
            X = np.column_stack([np.ones(len(E)), E[prev].to_numpy(float)])
            b = np.linalg.lstsq(X, E[etf].to_numpy(float), rcond=None)[0][1:]
            for j, p in enumerate(prev):
                M.loc[p, fname] = -b[j]
    return M


def design(F: pd.DataFrame, y_dates: pd.DatetimeIndex, lags: int) -> tuple[np.ndarray, list]:
    """[1, F_k(s - l) for k for l in 0..lags] for s in y_dates. F must hold the lagged rows."""
    pos = F.index.get_indexer(y_dates)
    if (pos < lags).any() or (pos < 0).any():
        raise ReadoutError("design: the factor rows do not reach the lags the window needs")
    Fv = F.to_numpy(float)
    cols, blocks = ["const"], [np.ones((len(y_dates), 1))]
    for j, k in enumerate(F.columns):
        for l in range(lags + 1):
            cols.append((k, l))
            blocks.append(Fv[pos - l, j][:, None])
    return np.hstack(blocks), cols


@dataclass
class WindowFit:
    t: pd.Timestamp
    y_dates: pd.DatetimeIndex
    f_dates: pd.DatetimeIndex
    M: pd.DataFrame                 # ETF -> factor
    beta: pd.DataFrame              # names x (factor, lag)
    beta_sum: pd.DataFrame          # names x factor (the summed Dimson beta)
    cols: list
    xtx_inv: np.ndarray
    resid_cov: pd.DataFrame         # names x names
    factor_vol: pd.Series           # annualised, on y_dates
    factor_cov: pd.DataFrame        # annualised, on y_dates
    n_obs: int
    lags: int
    fs: FactorSet = CORE


def fit_window(R: pd.DataFrame, sessions: pd.DatetimeIndex, t, names, *,
               window: int = WINDOW, lags: int = DIMSON_LAGS, fs: FactorSet = CORE) -> WindowFit:
    """Summed-Dimson betas of each name's total return on the orthogonal factors, the
    orthogonalisation slopes and the factor vols, all from sessions strictly before t."""
    t = pd.Timestamp(t)
    names = list(names)
    y_dates, f_dates = window_rows(sessions, t, window, lags)
    for etf in fs.etfs:
        if etf not in R.columns:
            raise ReadoutError(f"factor ETF {etf} is not in the price cache")
    miss = [n for n in names if n not in R.columns]
    if miss:
        raise ReadoutError(f"held symbols not in the price cache: {miss}")
    Eraw = R.loc[f_dates, list(fs.etfs)]
    _require_finite(Eraw, f"factor ETF returns on the window for {t.date()}")
    M = orthogonaliser(Eraw.loc[y_dates], fs)
    F = Eraw @ M
    F.columns = list(fs.names)
    X, cols = design(F, y_dates, lags)
    p = X.shape[1]
    if len(y_dates) <= p:
        raise ReadoutError(f"window {len(y_dates)} is not longer than the {p} regressors")
    xtx = X.T @ X
    if np.linalg.cond(xtx) > 1e12:
        raise ReadoutError(f"the factor design for {t.date()} is singular (cond {np.linalg.cond(xtx):.3g})")
    xtx_inv = np.linalg.inv(xtx)
    if names:
        Y = R.loc[y_dates, names]
        _require_finite(Y, f"held names' returns on the window for {t.date()}")
        B = xtx_inv @ X.T @ Y.to_numpy(float)
        U = Y.to_numpy(float) - X @ B
        S = U.T @ U / (len(y_dates) - p)
    else:
        B = np.zeros((p, 0))
        S = np.zeros((0, 0))
    idx = pd.MultiIndex.from_tuples(cols[1:], names=["factor", "lag"])
    beta = pd.DataFrame(B[1:].T, index=names, columns=idx)
    beta_sum = beta.T.groupby(level="factor", sort=False).sum().T.reindex(columns=list(fs.names))
    Fy = F.loc[y_dates]
    fcov = Fy.cov() * ANNUALISE
    return WindowFit(t=t, y_dates=y_dates, f_dates=f_dates, M=M, beta=beta, beta_sum=beta_sum,
                     cols=cols, xtx_inv=xtx_inv, resid_cov=pd.DataFrame(S, index=names, columns=names),
                     factor_vol=np.sqrt(pd.Series(np.diag(fcov), index=list(fs.names))),
                     factor_cov=fcov, n_obs=len(y_dates), lags=lags, fs=fs)


def exposures(fit: WindowFit, value: pd.Series, equity: float | None,
              vol_target: float | None = None, review_fraction: float = REVIEW_FRACTION,
              multiplier: float | None = None) -> pd.DataFrame:
    """One row per factor: E (dollars), e (fraction of equity), sigma, c, the review flag.

    `value` is shares x close per held name, SIGNED (a short is negative). The rule is
    REVIEW_RULE; with `equity` None every fraction and the flag are UNMEASURED (NaN and the
    string), never computed against a default capital. The line is review_fraction x
    vol_target x `multiplier` (team lead, 2026-11-10); `multiplier` None reads the fit's own
    book's (`fit.fs.multiplier`, from that book's spec), never a number written here.
    c/target stays c / vol_target, so the flag reads c/target > review_fraction x m.

    `vol_target` None reads the same book's (`fit.fs.vol_target`), so both defaults come from
    one book and a caller cannot read one book's line with another's vol target. Until the
    independent review of PR #82 (2026-11-11) its default was the core's VOL_TARGET while the
    multiplier's was the fit's book's. `readout`, the one production caller, passes both, so
    the change moves no output (the strict readout is byte-identical across it)."""
    vt = fit.fs.vol_target if vol_target is None else vol_target
    m = fit.fs.multiplier if multiplier is None else multiplier
    names = list(fit.beta_sum.index)
    v = value.reindex(names)
    if v.isna().any():
        raise ReadoutError(f"no position value for fitted names {list(v[v.isna()].index)}")
    vv = v.to_numpy(float)
    fnames = list(fit.fs.names)
    E = pd.Series(vv @ fit.beta_sum.to_numpy(float), index=fnames) if names else \
        pd.Series(0.0, index=fnames)
    vSv = float(vv @ fit.resid_cov.to_numpy(float) @ vv) if names else 0.0
    rows = []
    for k in fnames:
        a = np.array([1.0 if (c != "const" and c[0] == k) else 0.0 for c in fit.cols])
        se = math.sqrt(max(vSv, 0.0) * float(a @ fit.xtx_inv @ a))
        sig = float(fit.factor_vol[k])
        c_usd = abs(float(E[k])) * sig
        if equity is None:
            e = c = frac = float("nan")
            flag = "UNMEASURED"
        else:
            e = float(E[k]) / equity
            c = abs(e) * sig
            frac = c / vt
            flag = "REVIEW" if c > review_fraction * vt * m else "within"
        rows.append(dict(date=fit.t, factor=k, exposure_usd=float(E[k]), exposure_frac=e,
                         factor_vol=sig, contrib_usd=c_usd, contrib_frac=c, contrib_of_target=frac,
                         d4_literal_breach=(None if equity is None else abs(e) > D4_BETA_BAR),
                         t_stat=(float(E[k]) / se if se > 0 else float("nan")), review=flag))
    return pd.DataFrame(rows)


def total_factor_vol(fit: WindowFit, E: pd.Series) -> float:
    """sqrt(E' Sigma_f E), in the units of E (dollars, or a fraction of equity)."""
    e = E.reindex(list(fit.fs.names)).to_numpy(float)
    return math.sqrt(max(float(e @ fit.factor_cov.to_numpy(float) @ e), 0.0))


# --------------------------------------------------------------------------- positions

def read_positions(path: Path) -> pd.DataFrame:
    """date, symbol, shares[, equity]. Raises on anything it would otherwise have to guess."""
    P = pd.read_csv(path)
    need = {"date", "symbol", "shares"}
    miss = need - set(P.columns)
    if miss:
        raise ReadoutError(f"{path}: positions file lacks columns {sorted(miss)}")
    return validate_positions(P, str(path))


def validate_positions(P: pd.DataFrame, where: str = "positions") -> pd.DataFrame:
    P = P.copy()
    P["date"] = pd.to_datetime(P["date"])
    P["symbol"] = P["symbol"].astype(str).str.strip().str.upper()
    P["shares"] = pd.to_numeric(P["shares"], errors="raise").astype(float)
    if not np.isfinite(P["shares"].to_numpy()).all():
        raise ReadoutError(f"{where}: non-finite share counts")
    dup = P.duplicated(["date", "symbol"])
    if dup.any():
        raise ReadoutError(f"{where}: duplicate (date, symbol) rows "
                           f"{P.loc[dup, ['date', 'symbol']].astype(str).head(5).values.tolist()}")
    if "equity" in P.columns:
        # A value that is present but does not parse raises, naming it. The first build
        # coerced it to NaN, so "$100,000.00" on every row dropped the column without a word
        # and the summary blamed a missing equity (review 2026-11-02, finding 4). No format
        # is guessed here: write the equity as a plain number.
        raw = P["equity"]
        blank = raw.isna() | raw.astype(str).str.strip().eq("")
        eq = pd.to_numeric(raw.where(~blank), errors="coerce")
        bad = ~blank & eq.isna()
        if bad.any():
            raise ReadoutError(f"{where}: column 'equity' holds values that are not plain numbers, e.g. "
                               f"{raw[bad].astype(str).head(3).tolist()} (dates "
                               f"{sorted(P.loc[bad, 'date'].dt.date.astype(str).unique())[:5]}). Write it "
                               "as a number, with no currency sign or thousands separator")
        if blank.all():
            raise ReadoutError(f"{where}: column 'equity' is present but empty on every row. Drop the "
                               "column to read without equity (every rule reading is then UNMEASURED)")
        if blank.any():
            raise ReadoutError(f"{where}: equity is given on some rows and missing on others "
                               f"(dates {sorted(P.loc[blank, 'date'].dt.date.astype(str).unique())[:5]})")
        if not (np.isfinite(eq.to_numpy(float)) & (eq.to_numpy(float) > 0)).all():
            raise ReadoutError(f"{where}: equity must be a finite positive number")
        n = eq.groupby(P["date"]).nunique()
        if (n > 1).any():
            raise ReadoutError(f"{where}: more than one equity on dates "
                               f"{[d.date().isoformat() for d in n[n > 1].index[:5]]}")
        P["equity"] = eq.astype(float)
    return P.sort_values(["date", "symbol"]).reset_index(drop=True)


def load_groups(path: Path = UNIVERSE_CSV) -> dict:
    """{ticker: grp} from data/cef/cef_universe.csv (read only). Duplicates raise."""
    if not Path(path).exists():
        raise ReadoutError(f"{path} is missing: the group table needs it")
    u = pd.read_csv(path)
    if u["ticker"].duplicated().any():
        raise ReadoutError(f"{path}: duplicate tickers")
    return dict(zip(u["ticker"], u["grp"]))


# --------------------------------------------------------------------------- the readout

@dataclass
class Readout:
    exposure: pd.DataFrame
    by_group: pd.DataFrame
    betas: pd.DataFrame
    factor_defs: pd.DataFrame
    factor_pnl: pd.DataFrame
    total_vol: pd.DataFrame
    window: int
    lags: int
    fs: FactorSet = CORE
    excluded: pd.DataFrame | None = None   # partial mode only: (date, symbol, shares, reason) left out


def _missing_input(s: str, t, C: pd.DataFrame, R: pd.DataFrame, sessions: pd.DatetimeIndex,
                   window: int, lags: int) -> str | None:
    """Why held name s cannot be read on t in partial mode, or None when it has every input the
    computation needs (module docstring, PARTIAL): a price history, a finite close on t (its
    value), and a finite return on every session of its beta window, strictly before t."""
    if s not in C.columns:
        return "no price history in the fetch"
    have = C[s].dropna()
    if not np.isfinite(float(C.at[t, s])):
        if len(have) and t > have.index.max():
            return f"no close on {t.date()} (its price history ends {have.index.max().date()})"
        if len(have) and t < have.index.min():
            return f"no close on {t.date()} (its price history starts {have.index.min().date()})"
        return f"no close on {t.date()}"
    y_dates, _ = window_rows(sessions, t, window, lags)
    bad = int((~np.isfinite(R.loc[y_dates, s].to_numpy(float))).sum())
    if bad:
        return (f"{bad} missing return(s) in its {window}-session window before {t.date()} (its price "
                f"history starts {have.index.min().date()})")
    return None


def readout(px: pd.DataFrame, positions: pd.DataFrame, groups: dict, *, window: int | None = None,
            lags: int | None = None, vol_target: float | None = None, fs: FactorSet = CORE,
            partial: bool = False) -> Readout:
    """Exposures on every positions date, and the factor P&L on every positions date whose
    previous session is also a positions date (E(t-1) x f(t), and the lag-distributed
    second method). `window`, `lags` and `vol_target` default to the book's (`fs`); a book
    whose lag rule has not run raises rather than guess a lag. The line's multiplier is
    always the book's own (`fs.multiplier`, team lead, 2026-11-10).

    `partial` (default False: the strict readout, unchanged; True from the daily report job
    only, team lead 2026-11-10, module docstring PARTIAL): a held name without every input on
    a date is left out of that date and recorded in `excluded`, and a date on which no held
    name has its inputs raises NoInputsError."""
    window = fs.window if window is None else window
    vol_target = fs.vol_target if vol_target is None else vol_target
    if lags is None:
        if fs.dimson_lags is None:
            raise ReadoutError(f"book {fs.book} has no Dimson lag: its lag rule has not been run "
                               "(exposure_readout.py derive --book c4, then set C4_DIMSON_LAGS from it; "
                               "module docstring, TWO BOOKS)")
        lags = fs.dimson_lags
    P = validate_positions(positions)
    dates = list(pd.DatetimeIndex(P["date"].unique()).sort_values())
    have_eq = "equity" in P.columns
    # A split after the first positions date would put the cached close on a basis the share
    # count does not share (yfinance re-bases Close for splits). Checked before the returns,
    # so the refusal names the real problem rather than the split-basis guard's symptom.
    held_any = sorted(P.loc[P["shares"] != 0, "symbol"].unique())
    sp = px[(px["ticker"].isin(held_any)) & (px["split"] != 0) & (px["date"] > dates[0])]
    if len(sp):
        raise ReadoutError(f"split records after the first positions date on held names: "
                           f"{sp[['ticker', 'date']].astype(str).values.tolist()}")
    R, C, sessions = returns_panel(px, drop_adjusted_splits=(fs.book == "c4"))
    off = [d for d in dates if d not in sessions]
    if off:
        raise ReadoutError(f"positions dates that are not cached sessions: {[d.date().isoformat() for d in off[:5]]}")
    nogrp = [s for s in held_any if s not in groups]
    if nogrp:
        raise ReadoutError(f"held symbols with no group in the universe table: {nogrp}")

    fits, values, eqs = {}, {}, {}
    ex_rows, grp_rows, beta_rows, def_rows, tv_rows = [], [], [], [], []
    excluded_rows = []
    for t in dates:
        Pt = P[P["date"] == t].set_index("symbol")
        held = list(Pt.index[Pt["shares"] != 0])
        if partial:
            why = {s: _missing_input(s, t, C, R, sessions, window, lags) for s in held}
            gone = [s for s in held if why[s] is not None]
            if held and len(gone) == len(held):
                raise NoInputsError(f"no held name has every input the readout needs on {t.date()}: "
                                    + "; ".join(f"{s} ({why[s]})" for s in gone))
            excluded_rows += [dict(date=t, symbol=s, shares=float(Pt.at[s, "shares"]), reason=why[s]) for s in gone]
            held = [s for s in held if why[s] is None]
        close = C.loc[t, held] if held else pd.Series(dtype=float)
        if held and not np.isfinite(close.to_numpy(float)).all():
            raise ReadoutError(f"no close on {t.date()} for {list(close[~np.isfinite(close)].index)}")
        value = Pt.loc[held, "shares"] * close
        eq = float(Pt["equity"].iloc[0]) if have_eq else None
        fit = fit_window(R, sessions, t, held, window=window, lags=lags, fs=fs)
        fits[t], values[t], eqs[t] = fit, value, eq
        ex = exposures(fit, value, eq, vol_target=vol_target, multiplier=fs.multiplier)
        ex_rows.append(ex)
        E = ex.set_index("factor")["exposure_usd"]
        tv = total_factor_vol(fit, E)
        tv_rows.append(dict(date=t, gross_usd=float(value.abs().sum()), net_usd=float(value.sum()),
                            total_factor_vol_usd=tv,
                            total_factor_vol_frac=(tv / eq if eq else float("nan")),
                            total_of_target=(tv / eq / vol_target if eq else float("nan")),
                            equity=(eq if eq else float("nan"))))
        for g in sorted({groups[s] for s in held}):
            mem = [s for s in held if groups[s] == g]
            Eg = value.reindex(mem).to_numpy(float) @ fit.beta_sum.loc[mem].to_numpy(float)
            for k, x in zip(fs.names, Eg):
                grp_rows.append(dict(date=t, grp=g, factor=k, exposure_usd=float(x),
                                     exposure_frac=(float(x) / eq if eq else float("nan"))))
        for s in held:
            for k in fs.names:
                row = dict(date=t, symbol=s, grp=groups[s], factor=k, beta_sum=float(fit.beta_sum.at[s, k]))
                for l in range(lags + 1):
                    row[f"beta_l{l}"] = float(fit.beta.at[s, (k, l)])
                beta_rows.append(row)
        for etf in fs.etfs:
            def_rows.append(dict(date=t, etf=etf, **{k: float(fit.M.at[etf, k]) for k in fs.names}))

    # factor P&L: t whose previous session is a positions date
    pnl_rows = []
    pos_set = set(dates)
    for t in dates:
        i = int(sessions.searchsorted(t))
        if i == 0 or sessions[i - 1] not in pos_set:
            continue
        tp = sessions[i - 1]
        fit, value = fits[tp], values[tp]
        held = list(value.index)
        f_t = R.loc[[t], list(fs.etfs)]
        _require_finite(f_t, f"factor ETF returns on {t.date()}")
        ft = (f_t @ fit.M).iloc[0]
        ft.index = list(fs.names)
        lagdates = sessions[i - lags:i + 1]           # t - lags .. t
        assert_strictly_before(fit.y_dates, tp + pd.Timedelta(days=1), "P&L fit window")
        Fl = R.loc[lagdates, list(fs.etfs)]
        _require_finite(Fl, f"factor ETF returns on {lagdates[0].date()}..{t.date()}")
        Fl = Fl @ fit.M
        Fl.columns = list(fs.names)
        for scope, mem in [("book", held)] + [(f"grp:{g}", [s for s in held if groups[s] == g])
                                               for g in sorted({groups[s] for s in held})]:
            v = value.reindex(mem).to_numpy(float)
            Es = v @ fit.beta_sum.loc[mem].to_numpy(float) if mem else np.zeros(len(fs.names))
            for j, k in enumerate(fs.names):
                # second method: sum_l beta_l x F_k(t - l), on t-1's holdings
                lagd = 0.0
                for l in range(lags + 1):
                    b = fit.beta.loc[mem, (k, l)].to_numpy(float) if mem else np.zeros(0)
                    lagd += float(v @ b) * float(Fl[k].iloc[-1 - l])
                pnl_rows.append(dict(date=t, prev=tp, scope=scope, factor=k,
                                     exposure_prev_usd=float(Es[j]), factor_return=float(ft[k]),
                                     pnl_summed=float(Es[j]) * float(ft[k]), pnl_lagdist=lagd))
    return Readout(exposure=pd.concat(ex_rows, ignore_index=True),
                   by_group=pd.DataFrame(grp_rows), betas=pd.DataFrame(beta_rows),
                   factor_defs=pd.DataFrame(def_rows), factor_pnl=pd.DataFrame(pnl_rows),
                   total_vol=pd.DataFrame(tv_rows), window=window, lags=lags, fs=fs,
                   excluded=(pd.DataFrame(excluded_rows, columns=["date", "symbol", "shares", "reason"])
                             if partial else None))


# --------------------------------------------------------------------------- plateau check

PLATEAU_LAG_SPAN = 2     # lags 0 .. L + 2: brackets L the way W/2 .. 2W brackets W


def plateau_summary(ro: Readout) -> dict:
    """One plateau row: the book and group factor P&L, and the review counts per factor.

    The counts are here because the first build printed only P&L and mean |E| (review
    2026-11-02, finding 1), while the per-factor review counts were the quantity that moved
    most with the Dimson lag count."""
    ex = ro.exposure
    fp = ro.factor_pnl
    by_scope = fp.groupby("scope", sort=True)[["pnl_summed", "pnl_lagdist"]].sum() if len(fp) else None
    measured = bool((ex["review"] != "UNMEASURED").any())
    rev = ex[ex["review"] == "REVIEW"]
    big_t = rev[rev["t_stat"].abs() >= 2.0]
    count = (lambda g: {k: int(g.loc[g["factor"] == k, "date"].nunique()) for k in ro.fs.names})
    return dict(
        window=ro.window, lags=ro.lags,
        book_summed=(float(by_scope.at["book", "pnl_summed"]) if by_scope is not None else float("nan")),
        book_lagdist=(float(by_scope.at["book", "pnl_lagdist"]) if by_scope is not None else float("nan")),
        group_summed=({s[4:]: float(v) for s, v in by_scope["pnl_summed"].items() if s.startswith("grp:")}
                      if by_scope is not None else {}),
        n_dates=int(ex["date"].nunique()), measured=measured,
        review=(count(rev) if measured else None), review_t2=(count(big_t) if measured else None),
        mean_abs_E={k: float(ex.loc[ex["factor"] == k, "exposure_usd"].abs().mean()) for k in ro.fs.names})


def plateau_check(px: pd.DataFrame, positions: pd.DataFrame, groups: dict, ro: Readout) -> list:
    """The readout re-run at W/2 and 2W with the lags fixed, and at lags 0 .. L + 2 with the
    window fixed. A check for a plateau: NOTHING IS CHOSEN FROM IT, and the rule keeps the
    adopted W and L whatever it prints."""
    runs = [(w, ro.lags) for w in (ro.window // 2, ro.window, 2 * ro.window)]
    runs += [(ro.window, l) for l in range(0, ro.lags + PLATEAU_LAG_SPAN + 1) if l != ro.lags]
    out = []
    for w, l in runs:
        r2 = ro if (w, l) == (ro.window, ro.lags) else readout(px, positions, groups, window=w, lags=l, fs=ro.fs)
        out.append(dict(plateau_summary(r2), adopted=((w, l) == (ro.window, ro.lags))))
    return out


# --------------------------------------------------------------------------- outputs

def _fmt_money(x: float) -> str:
    return "n/a" if not np.isfinite(x) else f"{x:,.0f}"


# THE ORDER OF THE REPORT (team lead, 2026-11-03; module docstring, THE TEAM LEAD'S RULING).
# Presentation only: nothing below changes a number the readout computes or writes to a CSV.
HEADLINE_FACTOR = "MUNI"
INDICATIVE_FACTORS = tuple(k for k in FACTOR_NAMES if k != HEADLINE_FACTOR)   # TERM, CREDIT, LOANS
INDICATIVE_HEADING = "Indicative: depends on the lag choice (see DIMSON_LAGS docstring)"
# The muni funds' `grp` in data/cef/cef_universe.csv. Every other group (hy, multi, loan, emd
# today; whatever the table holds at run time) is a taxable group.
MUNI_GROUP = "muni"


def _rule_lines(ex: pd.DataFrame, factors) -> list:
    """The readings of `factors` against the review rule, one bullet each, in `factors` order.

    The first build printed one bullet per FLAGGED factor and "no factor over the line" when
    none was, so a factor within the line was silent. With MUNI read on its own (team lead,
    2026-11-03) a silent MUNI would read as missing, so each factor gets its own line."""
    sub = ex[ex["factor"].isin(factors)]
    n_all = sub["date"].nunique()
    unm = sub[sub["review"] == "UNMEASURED"]
    meas = sub[sub["review"] != "UNMEASURED"]
    out = []
    if len(unm):
        out.append(f"- UNMEASURED on {unm['date'].nunique()} date(s): no equity in the positions file.")
    for k in factors:
        g = meas[meas["factor"] == k]
        if not len(g):
            continue
        rev = g[g["review"] == "REVIEW"]
        if len(rev):
            m = rev.loc[rev["contrib_of_target"].idxmax()]
            out.append(f"- **{k}: REVIEW on {rev['date'].nunique()} of {n_all} dates**; "
                       f"largest c/target {m['contrib_of_target']:.3f} on {m['date'].date()} "
                       f"(E {_fmt_money(m['exposure_usd'])} USD, t {m['t_stat']:.2f})")
        else:
            out.append(f"- {k}: within the line on all {g['date'].nunique()} measured date(s)")
    return out


def _per_date_lines(ex: pd.DataFrame, factors) -> list:
    """The per-date rule table for `factors` (same columns and formats as the first build)."""
    out = ["| date | factor | E USD | E/equity | sigma | c/target | t | D4 literal | rule |",
           "|---|---|---:|---:|---:|---:|---:|---|---|"]
    for r in ex[ex["factor"].isin(factors)].itertuples():
        out.append(f"| {r.date.date()} | {r.factor} | {_fmt_money(r.exposure_usd)} | "
                   f"{r.exposure_frac:+.3f} | {r.factor_vol:.4f} | {r.contrib_of_target:.3f} | "
                   f"{r.t_stat:+.2f} | {r.d4_literal_breach} | {r.review} |")
    return out


def headline_by_group(ro: Readout) -> pd.DataFrame:
    """C4's report split (team lead, 2026-11-09): the book's headline-factor exposure by
    fund family, one row per (date, family held) plus the family's share of the book's
    headline exposure and the book's total, read from `ro.by_group`; nothing is
    re-estimated. Families add up to the book (a test pins it); `exposure_frac` is NaN
    with no equity, never a default."""
    H = ro.fs.headline
    ex = ro.exposure[ro.exposure["factor"] == H].set_index("date")
    bg = ro.by_group[ro.by_group["factor"] == H] if len(ro.by_group) else \
        pd.DataFrame(columns=["date", "grp", "factor", "exposure_usd", "exposure_frac"])
    rows = []
    for r in bg.itertuples():
        book = float(ex.at[r.date, "exposure_usd"])
        rows.append(dict(date=r.date, grp=r.grp, exposure_usd=float(r.exposure_usd),
                         exposure_frac=float(r.exposure_frac),
                         share_of_book=(float(r.exposure_usd) / book if book != 0.0 else float("nan")),
                         book_usd=book))
    return pd.DataFrame(rows, columns=["date", "grp", "exposure_usd", "exposure_frac", "share_of_book", "book_usd"])


def muni_vs_taxable(ro: Readout) -> pd.DataFrame:
    """The book's MUNI exposure split into the muni group and the taxable groups, per date.

    A reading of `ro.by_group` (exposure_by_group.csv), summed: no number is re-estimated.
    The groups add up to the book (a test pins it). A side with no held name on a date is
    `held = False` and its exposure is the empty sum, 0. The fractions are each side's USD
    over that date's equity, NaN with no equity: never summed from NaNs into a 0.

    Why the split is in the headline (module docstring, THE TEAM LEAD'S RULING): the book's
    MUNI exposure sums the taxable funds' MUNI betas too, which move with the lag choice in
    the fit-era plateau. On the window measured when the ruling was recorded the muni funds'
    moved as well, so neither side is assumed level: the split is read on every date."""
    H = ro.fs.headline
    ex = ro.exposure[ro.exposure["factor"] == H].set_index("date")
    eq = ro.total_vol.set_index("date")["equity"]
    bg = ro.by_group[ro.by_group["factor"] == H] if len(ro.by_group) else \
        pd.DataFrame(columns=["date", "grp", "factor", "exposure_usd"])
    rows = []
    for t in ex.index:
        g = bg[bg["date"] == t].set_index("grp")["exposure_usd"]
        tax = g[g.index != MUNI_GROUP]
        muni_usd = float(g.get(MUNI_GROUP, 0.0))
        tax_usd = float(tax.sum()) if len(tax) else 0.0
        e = float(eq.at[t])
        rows.append(dict(date=t, muni_held=MUNI_GROUP in g.index, muni_usd=muni_usd,
                         muni_frac=(muni_usd / e if np.isfinite(e) else float("nan")),
                         taxable_held=bool(len(tax)), taxable_usd=tax_usd,
                         taxable_frac=(tax_usd / e if np.isfinite(e) else float("nan")),
                         book_usd=float(ex.at[t, "exposure_usd"]),
                         taxable_by_group={k: float(v) for k, v in tax.sort_index().items()}))
    return pd.DataFrame(rows)


def summary_md(ro: Readout, meta: dict, plateau: list | None = None) -> str:
    """summary.md, which `analyse` also prints. The headline factor first (MUNI for the core,
    EQUITY for C4), then the other factors under INDICATIVE_HEADING, then the plateau check
    when asked for.

    Presentation only. Every number here is read from `ro`, whose frames are the CSVs; the
    ruling changed the order and the headings, not one computed value."""
    fs = ro.fs
    H = fs.headline
    ind = ", ".join(fs.indicative[:-1]) + " and " + fs.indicative[-1]
    ruling = ("(team lead, 2026-11-03; module docstring, THE TEAM LEAD'S RULING)" if fs.book == "cef"
              else "(team lead, 2026-11-09; module docstring, TWO BOOKS)")
    L = ["# Exposure readout (report only; zero trials)", "",
         f"- spec: `{fs.spec_id}`; vol_target_annual {fs.vol_target:.4g}; sizing_multiplier "
         f"{'absent (the unit book, 1)' if fs.sizing_multiplier is None else f'{fs.sizing_multiplier:.4g}'} "
         "(both read at run time)",
         f"- window {ro.window} sessions strictly before each date; Dimson lags 0..{ro.lags}; "
         f"factors {', '.join(f'{f}={e}' for f, e in fs.factors)}, Gram-Schmidt in that order",
         f"- price cache: yfinance, asof {meta.get('asof')}, fetched {meta.get('fetched_at_utc')}",
         f"- {H} is the headline; {ind} follow under \"{INDICATIVE_HEADING}\" {ruling}",
         "", f"## Headline: {H}", "",
         "### Review rule (declared before the first reading; it applies to every factor)", "",
         REVIEW_RULE,
         f"REVIEW_FRACTION = {REVIEW_FRACTION} (D4's beta bar on factors rescaled to the vol "
         "target; module docstring). Nothing is hedged automatically.",
         f"The line for book {fs.book}: {fs.line_inputs()} a year, so c/target above "
         f"{REVIEW_FRACTION * fs.multiplier:.4g} goes to review (team lead, 2026-11-10: the account holds "
         "m x the unit book, and this readout measures the account).", ""]
    ex = ro.exposure
    L += [f"### {H} against the rule", ""] + _rule_lines(ex, (H,))
    L += ["", f"### {H} per date: exposure, vol contribution, review flag", ""] + _per_date_lines(ex, (H,))

    if fs.group_split == "muni":
        mv = muni_vs_taxable(ro)
        L += ["", f"### {H} exposure: the muni group against the taxable groups", "",
              f"The book's {H} exposure by fund group (exposure_by_group.csv, summed): `{MUNI_GROUP}` "
              "against every other group in data/cef/cef_universe.csv, which add up to the book. "
              "Both sides are summed Dimson betas at the adopted L, and neither is assumed level in "
              "L (module docstring, THE TEAM LEAD'S RULING); `analyse --plateau` re-reads MUNI at "
              "other L on this book.", "",
              "| date | muni group E USD | muni group E/equity | taxable groups E USD | "
              "taxable groups E/equity | book E USD | taxable by group, E USD |",
              "|---|---:|---:|---:|---:|---:|---|"]
        for r in mv.itertuples():
            mu = (f"{_fmt_money(r.muni_usd)} | {r.muni_frac:+.3f}" if r.muni_held else "none held | n/a")
            tx = (f"{_fmt_money(r.taxable_usd)} | {r.taxable_frac:+.3f}" if r.taxable_held else "none held | n/a")
            by = ", ".join(f"{g} {_fmt_money(v)}" for g, v in r.taxable_by_group.items()) or "none held"
            L.append(f"| {r.date.date()} | {mu} | {tx} | {_fmt_money(r.book_usd)} | {by} |")
    else:
        hg = headline_by_group(ro)
        L += ["", f"### {H} exposure by family ({fs.groups_path})", "",
              f"The book's {H} exposure by fund family (exposure_by_group.csv): the families add up "
              "to the book. Summed Dimson betas at the adopted L; `analyse --plateau` re-reads at "
              "other L on this book.", "",
              "| date | family | E USD | E/equity | share of book E | book E USD |",
              "|---|---|---:|---:|---:|---:|"]
        for r in hg.itertuples():
            L.append(f"| {r.date.date()} | {r.grp} | {_fmt_money(r.exposure_usd)} | {r.exposure_frac:+.3f} | "
                     f"{r.share_of_book:+.3f} | {_fmt_money(r.book_usd)} |")

    fp = ro.factor_pnl
    if len(fp):
        fh = fp[fp["factor"] == H]
        L += ["", f"### {H} factor P&L by group (model reading, USD): E(t-1) x f(t) and the "
              "lag-distributed method", "",
              "| scope | summed-beta | lag-distributed |", "|---|---:|---:|"]
        for sc, g in fh.groupby("scope", sort=False):
            L.append(f"| {sc} | {g['pnl_summed'].sum():,.2f} | {g['pnl_lagdist'].sum():,.2f} |")
        tax = fh[fh["scope"].str.startswith("grp:") & (fh["scope"] != f"grp:{MUNI_GROUP}")]
        if fs.group_split == "muni" and len(tax):
            L.append(f"| taxable groups (sum of the grp: rows other than grp:{MUNI_GROUP}) | "
                     f"{tax['pnl_summed'].sum():,.2f} | {tax['pnl_lagdist'].sum():,.2f} |")
        L.append(f"\nSessions: {fp['date'].nunique()} ({fp['date'].min().date()}..{fp['date'].max().date()}).")

    indnote = (f"{ind}. The team lead ruled on 2026-11-03 to keep DIMSON_LAGS = 0 and to read these three "
               "as indicative: the module docstring shows their fit-era betas and review counts moving "
               "with L more than MUNI's. The review rule applies to them unchanged."
               if fs.book == "cef" else
               f"{ind}. The team lead ruled on 2026-11-09 that these are marked indicative, as the core's "
               "non-headline factors are; the review rule applies to them unchanged.")
    L += ["", f"## {INDICATIVE_HEADING}", "", indnote,
          "", f"### {ind} against the rule", ""] + _rule_lines(ex, fs.indicative)
    L += ["", f"### {ind} per date", ""] + _per_date_lines(ex, fs.indicative)
    L += ["", "### Book totals per date (information; not part of the rule; the total factor vol "
          "sums all four factors, so it moves with L too)", "",
          "| date | gross USD | net USD | total factor vol USD | total / target |",
          "|---|---:|---:|---:|---:|"]
    for r in ro.total_vol.itertuples():
        L.append(f"| {r.date.date()} | {_fmt_money(r.gross_usd)} | {_fmt_money(r.net_usd)} | "
                 f"{_fmt_money(r.total_factor_vol_usd)} | {r.total_of_target:.3f} |")
    if len(fp):
        L += ["", f"### Factor P&L, {ind}, and ALL {_num_words(len(fs.names))} factors (model reading, USD)", "",
              "| scope | factor | summed-beta | lag-distributed |", "|---|---|---:|---:|"]
        fi = fp[fp["factor"].isin(fs.indicative)]
        for (sc, k), g in fi.groupby(["scope", "factor"], sort=False):
            L.append(f"| {sc} | {k} | {g['pnl_summed'].sum():,.2f} | {g['pnl_lagdist'].sum():,.2f} |")
        for sc, g in fp.groupby("scope", sort=False):
            L.append(f"| {sc} | ALL | {g['pnl_summed'].sum():,.2f} | {g['pnl_lagdist'].sum():,.2f} |")
    if plateau:
        fac = "/".join(fs.names)
        L += ["", "## Plateau check: window and Dimson lags (nothing is chosen from it)", "",
              "The adopted row is marked; every other row changes one of W and L. The review "
              "counts are the dates (of those read) on which the rule flagged each factor.", "",
              f"| window | lags | book P&L summed | lag-distributed | P&L summed by group | "
              f"REVIEW dates {fac} | REVIEW and abs t >= 2 {fac} | mean abs E USD by factor |",
              "|---:|---:|---:|---:|---|---|---|---|"]
        cnt = (lambda d: "UNMEASURED" if d is None else "/".join(str(d[k]) for k in fs.names))
        for r in plateau:
            L.append(f"| {r['window']}{' (adopted)' if r['adopted'] else ''} | {r['lags']} | "
                     f"{r['book_summed']:,.2f} | {r['book_lagdist']:,.2f} | "
                     f"{', '.join(f'{g} {v:,.0f}' for g, v in r['group_summed'].items())} | "
                     f"{cnt(r['review'])} | {cnt(r['review_t2'])} | "
                     f"{', '.join(f'{k} {v:,.0f}' for k, v in r['mean_abs_E'].items())} |")
    return "\n".join(L) + "\n"


def _num_words(n: int) -> str:
    return {4: "four"}.get(n, str(n))


def write_outputs(out_dir: Path, ro: Readout, meta: dict, plateau=None) -> None:
    out_dir = Path(out_dir)
    _refuse_write(out_dir, OUT_FILES)
    out_dir.mkdir(parents=True, exist_ok=True)
    ex = ro.exposure.merge(ro.total_vol, on="date", how="left")
    ex.to_csv(out_dir / "exposure.csv", index=False)
    ro.by_group.to_csv(out_dir / "exposure_by_group.csv", index=False)
    ro.betas.to_csv(out_dir / "betas.csv", index=False)
    ro.factor_defs.to_csv(out_dir / "factor_defs.csv", index=False)
    ro.factor_pnl.to_csv(out_dir / "factor_pnl.csv", index=False)
    (out_dir / "summary.md").write_text(summary_md(ro, meta, plateau))


# --------------------------------------------------------------------------- cross-check

def _panel(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise ReadoutError(f"cross-check panel {path} is missing")
    return pd.read_parquet(path)


# Who supplies each panel's numbers, and so what agreeing with it can show. This cache is
# yfinance. Agreeing with a yfinance panel shows that this fetch reproduces that one; it does
# not show the data are right (review 2026-11-02, finding 6). Only a different vendor checks
# the data. Sources: docs/REFERENCES.md, the "ETF research panels: their fetchers" row (the rv
# panels and etf_daily) and the cef_distributions-against-CRSP row (the CEF panels).
# etf_daily carries a `source` column, so it is compared one leg at a time.
PANEL_VENDOR = {
    "rv/close_unadj_wide": ("yfinance, then Alpaca after the 2026-10-11 restore's YF_LAST", "partly"),
    "rv/returns_wide": ("yfinance, then Alpaca after the 2026-10-11 restore's YF_LAST", "partly"),
    "rv/etf_ohlc_extended": ("yfinance, then Alpaca after the 2026-10-11 restore's YF_LAST", "partly"),
    "cef/cef_prices": ("yfinance", "no"),
    "cef/cef_distributions": ("yfinance Ticker.actions", "no"),
}
ETF_DAILY_LEG_INDEPENDENT = {"crsp": "yes", "alpaca": "yes", "yfinance": "no"}


def crosscheck(px: pd.DataFrame, data_dir: Path = DATA_DIR, fs: FactorSet = CORE) -> tuple[pd.DataFrame, list]:
    """The cache against the repo's own panels on their overlap (read-only). Reports; decides
    nothing. Returns (table, notes): one row per (panel, field, ticker) with the overlap, the
    count above the tolerance, the largest gap, the panel's vendor on that overlap and whether
    that vendor is independent of yfinance; and notes with the panels' last dates."""
    R, C, _ = returns_panel(px, drop_adjusted_splits=(fs.book == "c4"))
    Dv = px.pivot(index="date", columns="ticker", values="dividend").reindex_like(C)
    rows, notes = [], []
    etfs = [e for e in fs.etfs if e in C.columns]
    cefs = [c for c in C.columns if c not in fs.etfs]

    def comp(panel, field, tk, ours: pd.Series, theirs: pd.Series, tol, scale=1.0, vendor=None):
        vend, indep = vendor if vendor is not None else PANEL_VENDOR[panel]
        a, b = ours.dropna(), theirs.dropna()
        ix = a.index.intersection(b.index)
        if not len(ix):
            rows.append(dict(panel=panel, field=field, ticker=tk, n=0, vendor=vend,
                             independent_of_yfinance=indep))
            return
        d = (a.loc[ix] - b.loc[ix]) * scale
        ad = d.abs()
        rows.append(dict(panel=panel, field=field, ticker=tk, n=len(ix), first=ix.min().date(),
                         last=ix.max().date(), n_over_tol=int((ad > tol).sum()), tol=tol,
                         max_abs=float(ad.max()), max_on=ad.idxmax().date(),
                         p99_abs=float(ad.quantile(0.99)), vendor=vend, independent_of_yfinance=indep))

    cu = _panel(data_dir / "rv" / "close_unadj_wide.parquet")
    rw = _panel(data_dir / "rv" / "returns_wide.parquet")
    ext = _panel(data_dir / "rv" / "etf_ohlc_extended.parquet")
    ed = _panel(data_dir / "etf_daily.parquet")
    cp = _panel(data_dir / "cef" / "cef_prices.parquet")
    cd = _panel(data_dir / "cef" / "cef_distributions.parquet")
    notes += [f"data/rv/close_unadj_wide.parquet last {pd.Timestamp(cu.index.max()).date()}",
              f"data/rv/returns_wide.parquet last {pd.Timestamp(rw.index.max()).date()}",
              f"data/rv/etf_ohlc_extended.parquet last {pd.Timestamp(ext['date'].max()).date()}",
              f"data/etf_daily.parquet last {pd.Timestamp(ed['date'].max()).date()}",
              f"data/cef/cef_prices.parquet last {pd.Timestamp(cp['date'].max()).date()}",
              f"data/cef/cef_distributions.parquet last ex_date {pd.Timestamp(cd['ex_date'].max()).date()}"]
    for tk in etfs:
        if tk in cu.columns:
            comp("rv/close_unadj_wide", "close", tk, C[tk], cu[tk], TOL_CLOSE)
        else:
            notes.append(f"{tk}: not in data/rv/close_unadj_wide.parquet")
        if tk in rw.columns:
            comp("rv/returns_wide", "total return (bp)", tk, R[tk], rw[tk], TOL_TR_BP, 1e4)
        else:
            notes.append(f"{tk}: not in data/rv/returns_wide.parquet")
        g = ext[ext["ticker"] == tk].set_index("date")
        if len(g):
            comp("rv/etf_ohlc_extended", "close", tk, C[tk], g["close"], TOL_CLOSE)
            comp("rv/etf_ohlc_extended", "total return (bp)", tk, R[tk], g["ret_total"], TOL_TR_BP, 1e4)
            comp("rv/etf_ohlc_extended", "dividend", tk, Dv[tk], g["dividend"], TOL_DIV)
        else:
            notes.append(f"{tk}: not in data/rv/etf_ohlc_extended.parquet")
        g = ed[ed["ticker"] == tk]
        if len(g):
            for src, leg in g.groupby("source", sort=True):
                if src not in ETF_DAILY_LEG_INDEPENDENT:
                    raise ReadoutError(f"data/etf_daily.parquet: source leg {src!r} is not one this "
                                       "cross-check knows the vendor of")
                comp(f"etf_daily[{src}]", "total return (bp)", tk, R[tk], leg.set_index("date")["ret_total"],
                     TOL_TR_BP, 1e4, vendor=(src, ETF_DAILY_LEG_INDEPENDENT[src]))
        else:
            notes.append(f"{tk}: not in data/etf_daily.parquet")
    notes.append("cef/cef_prices and cef/cef_distributions are yfinance panels, the cache's own "
                 "vendor: agreement there confirms the fetch, not the data. Their known gaps against "
                 "CRSP are in docs/REFERENCES.md (the cef_distributions-against-CRSP row)")
    last_cd = pd.Timestamp(cd["ex_date"].max())
    for tk in cefs:
        g = cp[cp["ticker"] == tk].set_index("date")
        if not len(g):
            notes.append(f"{tk}: not in data/cef/cef_prices.parquet")
            continue
        comp("cef/cef_prices", "close", tk, C[tk], g["close"], TOL_CLOSE)
        ours = px[(px["ticker"] == tk) & (px["dividend"] > 0) & (px["date"] <= last_cd)].set_index("date")["dividend"]
        theirs = cd[(cd["ticker"] == tk) & (cd["ex_date"] >= px.loc[px["ticker"] == tk, "date"].min())
                    ].groupby("ex_date")["amount"].sum()
        only_ours = ours.index.difference(theirs.index)
        only_theirs = theirs.index.difference(ours.index)
        comp("cef/cef_distributions", "dividend", tk, ours, theirs, TOL_DIV)
        rows[-1].update(only_ours=len(only_ours), only_panel=len(only_theirs))
        if len(only_ours) or len(only_theirs):
            notes.append(f"{tk}: ex-dates only in the cache {[d.date().isoformat() for d in only_ours[:4]]}, "
                         f"only in the panel {[d.date().isoformat() for d in only_theirs[:4]]}")
    return pd.DataFrame(rows), notes


# --------------------------------------------------------------------------- derive

def derive(px: pd.DataFrame, groups: dict, names=None, fit_end: pd.Timestamp = FIT_END,
           max_lag: int = DERIVE_MAX_LAG, window: int = WINDOW, cache_sha: str | None = None,
           diagnostics: bool = True) -> dict:
    """Re-measure the two modelling choices on the fit era only (< 2023, H13): factor
    collinearity (whether to orthogonalise) and the Dimson lag count (THE RULE, the lead
    placebo; then the diagnostics after its result, and the superseded rules as history).
    Prints the tables the module docstring quotes and returns them. `cache_sha` is the
    cache's prices.parquet sha256 (`cache_sha256`); the CLI always passes it."""
    from scipy.stats import binom
    names = list(names or UNIVERSE)
    R, _, _ = returns_panel(px)
    R = R.loc[:fit_end]
    E = R[list(FACTOR_ETFS)].dropna()
    out = {}
    print(f"fit era {E.index.min().date()}..{E.index.max().date()}, {len(E)} sessions (all four ETFs)")
    corr = E.corr()
    vif = pd.Series(np.diag(np.linalg.inv(corr.to_numpy())), index=corr.index)
    print("\n1. COLLINEARITY, raw total returns, whole fit era\n" + corr.round(3).to_string())
    print("VIF " + ", ".join(f"{k} {v:.2f}" for k, v in vif.items())
          + f"; condition number {np.linalg.cond(corr.to_numpy()):.2f}")
    pairs = [("IEF", "MUB"), ("HYG", "BKLN"), ("IEF", "HYG"), ("MUB", "HYG"), ("MUB", "BKLN"), ("IEF", "BKLN")]
    rc = {}
    for a, b in pairs:
        s = E[a].rolling(window).corr(E[b]).dropna()
        rc[f"{a}-{b}"] = s.describe(percentiles=[0.05, 0.5, 0.95])[["min", "5%", "50%", "95%", "max"]]
    rc = pd.DataFrame(rc).T
    print(f"\nrolling {window}-session correlations\n" + rc.round(2).to_string())

    def _res(y, X):
        X1 = np.column_stack([np.ones(len(X)), X])
        b = np.linalg.lstsq(X1, y, rcond=None)[0]
        return y - X1[:, 1:] @ b[1:]
    rr, vifs, slopes, fvols = [], [], [], []
    for i in range(window, len(E) + 1, 21):
        w = E.iloc[i - window:i]
        I, M_, H, B = (w[c].to_numpy() for c in ("IEF", "MUB", "HYG", "BKLN"))
        Mi, Hi, Bi = _res(M_, I[:, None]), _res(H, I[:, None]), _res(B, I[:, None])
        rr.append({"MUB|IEF vs HYG|IEF": np.corrcoef(Mi, Hi)[0, 1],
                   "BKLN|IEF vs HYG|IEF": np.corrcoef(Bi, Hi)[0, 1]})
        vifs.append(np.diag(np.linalg.inv(np.corrcoef(w.to_numpy().T))))
        slopes.append(np.polyfit(I, M_, 1)[0])
        Fw = w @ orthogonaliser(w)
        fvols.append((Fw.std() * math.sqrt(ANNUALISE)).to_numpy())
    rr = pd.DataFrame(rr).describe(percentiles=[0.05, 0.5, 0.95]).T[["min", "5%", "50%", "95%", "max"]]
    print("\nresidual correlations after netting IEF only (windows every 21 sessions)\n" + rr.round(2).to_string())
    v = np.array(vifs)
    print("rolling VIF median " + ", ".join(f"{k} {x:.2f}" for k, x in zip(E.columns, np.median(v, 0)))
          + "; max " + ", ".join(f"{k} {x:.2f}" for k, x in zip(E.columns, v.max(0))))
    print(f"window OLS slope of MUB on IEF: median {np.median(slopes):+.2f} (a fixed MUB - IEF assumes 1)")
    fv = np.array(fvols)
    print("orthogonal factor vol on the windows, annualised, median [min, max]: "
          + ", ".join(f"{k} {np.median(fv[:, j]):.3f} [{fv[:, j].min():.3f}, {fv[:, j].max():.3f}]"
                      for j, k in enumerate(FACTOR_NAMES)))
    out.update(corr=corr, vif=vif, rolling=rc, resid=rr)

    # 2. THE RULE (module docstring): the lead-placebo lag rule, adopted 2026-11-02. The
    # counts are printed before the decision, so a raise still leaves the table on screen.
    npairs = len(names) * len(FACTOR_NAMES)
    pc = lead_placebo_counts(R, names, fit_end=fit_end, max_lag=max_lag)
    print(f"\n2. DIMSON LAGS, THE RULE (adopted; module docstring): one OLS per name, lags 0..{max_lag} "
          f"and leads 1..{DERIVE_RULE_LEADS}, HAC({DERIVE_RULE_HAC}); pairs (of {pc['n_pairs']}) with "
          f"p < {DERIVE_RULE_ALPHA}")
    print("   " + cache_provenance_line(cache_sha))
    print(f"   sample {pc['first'].date()}..{pc['last'].date()} (last response row; its lead-"
          f"{DERIVE_RULE_LEADS} row is on or before {pd.Timestamp(fit_end).date()}), sessions per name "
          f"{min(pc['nobs'].values())}..{max(pc['nobs'].values())}")
    print("   lag counts  c(l): " + _fmt_counts(pc["lag"]))
    print("   lead counts p(j): " + _fmt_counts(pc["lead"], "m"))
    rule = placebo_lag_rule(pc["lag"], pc["lead"])
    at = [j for j, c in pc["lead"].items() if c == rule["T"]]
    print(f"   T = max lead count = {rule['T']} (at lead {at}); first lag not above T: {rule['stop_lag']} "
          f"(count {pc['lag'][rule['stop_lag']]}); so L = {rule['L']}")
    print(f"   module constant DIMSON_LAGS = {DIMSON_LAGS}: "
          + ("equals the rule's L" if DIMSON_LAGS == rule["L"] else
             f"DIFFERS from the rule's L = {rule['L']}; set it from the rule in a commit of its own"))
    L = rule["L"]
    if diagnostics:
        out.update(diagnostics=_print_diagnostics(R, names, groups, fit_end, max_lag))

    # 3. SUPERSEDED (2026-11-02; history). Every rule the build session tried, at both lag
    # bounds, and the review's 5-lead placebo, kept so the docstring's review figures stay
    # reproducible. Nothing is chosen from them.
    M = orthogonaliser(E)
    F = E @ M
    F.columns = list(FACTOR_NAMES)
    models = {K: {n: _dimson_ols(R[n], F, K) for n in names} for K in sorted({DERIVE_ALT_MAX_LAG, max_lag})}
    bound = int(binom.ppf(0.95, npairs, 0.05))
    rules = {K: lag_rule_counts(ms, alpha=0.05) for K, ms in models.items()}
    sig = rules[max_lag]["single"]
    cum = {}
    for n in names:
        m = models[max_lag][n]
        for k in FACTOR_NAMES:
            cum[(n, groups.get(n, "?"), k)] = np.cumsum([m.params[f"{k}_{l}"] for l in range(max_lag + 1)])
    L_old = _first_gap(sig, bound)
    print(f"\n3. SUPERSEDED (2026-11-02; history, nothing is chosen here). Lags-only models, lags "
          f"0..{max_lag}, HAC(5): pairs (of {npairs}) with the lag-l coefficient significant at 5%")
    print("   " + ", ".join(f"l{l} {c}" for l, c in sig.items()) + f"; Binomial({npairs}, 0.05) 95% point {bound}")
    print(f"   the superseded first-gap rule's L = {L_old}")
    maj = len(names) // 2 + 1
    print("\n   the four lag rules tried on 2026-11-02, at both lag bounds K (superseded):")
    tab = []
    for K, c in rules.items():
        tab.append(dict(K=K, rule=f"joint Wald test of lag l, a majority ({maj} of {len(names)}) of names",
                        counts=_fmt_counts(c["joint"]), L=_first_gap(c["joint"], maj - 1)))
        tab.append(dict(K=K, rule=f"sum of lags L+1..K, pairs significant <= {bound}",
                        counts=_fmt_counts(c["tail"], "L"), L=_smallest_within(c["tail"], bound)))
        tab.append(dict(K=K, rule=f"single-lag first gap, pairs significant <= {bound}"
                                  + (" (adopted until 2026-11-02)" if K == max_lag else ""),
                        counts=_fmt_counts(c["single"]), L=_first_gap(c["single"], bound)))
    tab = pd.DataFrame(tab)
    with pd.option_context("display.width", 250, "display.max_colwidth", 120):
        print(tab.to_string(index=False))
    lead = {j: 0 for j in range(1, DERIVE_PLACEBO_LEADS + 1)}
    for n in names:
        m = _dimson_ols(R[n], F, max_lag, leads=DERIVE_PLACEBO_LEADS)
        for k in FACTOR_NAMES:
            for j in lead:
                lead[j] += int(m.pvalues[f"{k}_m{j}"] < 0.05)
    over = sum(c > bound for c in lead.values())
    print(f"\n   the review's placebo: pairs (of {npairs}) with a LEAD coefficient significant at 5%, "
          f"lags 0..{max_lag} and leads 1..{DERIVE_PLACEBO_LEADS}: "
          + ", ".join(f"lead{j} {c}" for j, c in lead.items())
          + f"; {over} of {len(lead)} leads exceed the Binomial bound {bound}")
    span = range(0, max(sig[l] for l in range(1, max_lag + 1)) + 2)
    print("   the superseded rule's L as a function of the bound: "
          + _fmt_runs({b: _first_gap(sig, b) for b in span}))

    # 4. The plateau check, beside the rule; nothing is chosen from it.
    cm = pd.DataFrame(cum).T
    cm.index.names = ["name", "grp", "factor"]
    cm.columns = [f"L{l}" for l in range(max_lag + 1)]
    med = cm.groupby(level=["grp", "factor"]).median()
    print(f"\n4. PLATEAU CHECK (nothing is chosen from it): median cumulative summed beta by group and "
          f"factor, from the lags-only 0..{max_lag} models\n" + med.round(2).to_string())
    near = [f"L{l}" for l in (L - 1, L, L + 1) if 0 <= l <= max_lag]
    if ("muni", "MUNI") in med.index:
        print(f"   muni names' MUNI beta at the rule's L - 1, L, L + 1: "
              + ", ".join(f"{c} {med.at[('muni', 'MUNI'), c]:.2f}" for c in near))
    out.update(sig=sig, bound=bound, L=L, L_superseded=L_old, placebo_counts=pc, rule=rule, cum=cm,
               rules=rules, rule_table=tab, placebo=lead)
    return out


def _print_diagnostics(R, names, groups, fit_end, max_lag) -> dict:
    """Section 2b of `derive`: `placebo_diagnostics`, printed. Decides nothing."""
    d = placebo_diagnostics(R, names, groups, fit_end=fit_end, max_lag=max_lag)
    pct = lambda r, n: f"{r}/{n} ({100 * r / n:.1f}%)"
    print(f"\n2b. AFTER THE RESULT (review 2026-11-02; DECIDES NOTHING, and THE RULE is not re-run on it). "
          f"The episode window and the lead cut at {DIAG_LEAD_CUT} were chosen by the review after it "
          "had seen the counts.")
    print("   rejections by band, nominal 5%: " + "; ".join(f"{k} {pct(*v)}" for k, v in d["bands"].items()))
    lo = [d["lead"][j] for j in range(1, DIAG_LEAD_CUT + 1)]
    hi = [d["lead"][j] for j in range(DIAG_LEAD_CUT + 1, DERIVE_RULE_LEADS + 1)]
    print(f"   lead counts 1..{DIAG_LEAD_CUT}: smallest {min(lo)}; {DIAG_LEAD_CUT + 1}..{DERIVE_RULE_LEADS}: "
          f"largest {max(hi)}. T sits at lead {d['at_T']}; its significant pairs: "
          + ", ".join(f"m{j} {n} ({g}) {k} {t:+.1f}" for j, n, g, k, t in d["T_pairs"]))
    rho, p1, p2 = d["trend"]
    print(f"   trend test of the 19 lead counts (Spearman rho of count on lead, {DIAG_PERMUTATIONS} "
          f"permutations, seed 0; no cut chosen): rho {rho:+.3f}, one-sided p {p1:.3f}, two-sided p {p2:.3f}")
    with pd.option_context("display.width", 200):
        print("   per name, THE RULE's joint model:\n" + d["per_name"].to_string(index=False))
    e = d["episode"]
    rows = sorted(set(e["rows_dropped"].values()))
    print(f"   rows whose regressor span t-{max_lag}..t+{DERIVE_RULE_LEADS} touches {e['window'][0]}.."
          f"{e['window'][1]} dropped ({rows[0]}..{rows[-1]} rows a name):")
    print("     lag counts  c(l): " + _fmt_counts(e["lag"]))
    print("     lead counts p(j): " + _fmt_counts(e["lead"], "m") + f"; their maximum {e['T']}")
    print("     " + "; ".join(f"{k} {pct(*v)}" for k, v in e["bands"].items())
          + "; leads rejected by name: " + ", ".join(f"{n} {c}" for n, c in e["per_name"].items()))
    print(f"   lags 0..{DERIVE_RULE_LEADS} beside leads 1..{DERIVE_RULE_LEADS}, full sample, like-for-like "
          "offsets: " + "; ".join(f"{k}: lags {pct(*a)}, leads {pct(*b)}" for k, (a, b) in d["far"].items()))
    print("   control, each calendar year's rows dropped in turn (largest lead count, at lead; lead "
          "rejections): " + "; ".join(f"{y} {T} at {at}, {pct(r, n)}" for y, (T, at, r, n) in d["years"].items()))
    return d


def _dimson_ols(y: pd.Series, F: pd.DataFrame, max_lag: int, leads: int = 0):
    """OLS of y on F at lags 0..max_lag (and, for the placebo only, leads 1..leads), HAC(5)."""
    import statsmodels.api as sm
    cols = {f"{k}_{l}": F[k].shift(l) for k in F.columns for l in range(max_lag + 1)}
    cols.update({f"{k}_m{j}": F[k].shift(-j) for k in F.columns for j in range(1, leads + 1)})
    X = pd.concat(cols, axis=1)
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    return sm.OLS(d["y"], sm.add_constant(d.drop(columns="y"))).fit(
        cov_type="HAC", cov_kwds={"maxlags": DERIVE_RULE_HAC})


def _regression_rows(y: pd.Series, F: pd.DataFrame, max_lag: int, leads: int) -> int:
    """The number of rows `_dimson_ols` would use for this response: the sessions on which
    the response and every factor at lags 0..max_lag and leads 1..leads exist."""
    cols = {f"{k}_{l}": F[k].shift(l) for k in F.columns for l in range(max_lag + 1)}
    cols.update({f"{k}_m{j}": F[k].shift(-j) for k in F.columns for j in range(1, leads + 1)})
    d = pd.concat([y.rename("y"), pd.concat(cols, axis=1)], axis=1).dropna()
    return int(len(d))


def derive_c4(px: pd.DataFrame, meta: dict | None = None, *, names=None, fit_end: pd.Timestamp = FIT_END,
              max_lag: int = DERIVE_MAX_LAG, leads: int = DERIVE_RULE_LEADS, cache_sha: str | None = None) -> dict:
    """THE C4 LAG RULE (module docstring): the core's lead-placebo rule on C4's factors and
    fit-era names. Prints the sample, the counts, T and L (or that the rule has no answer),
    and the plateau by family; returns them. The rule's verdict is the only thing here that
    decides anything; the family plateau is printed beside it and nothing is chosen from it."""
    fs = factor_set("c4")
    groups = c4_families()
    dropped: list = []
    R, _, _ = returns_panel(px, drop_adjusted_splits=True, dropped=dropped)
    fit_end = pd.Timestamp(fit_end)
    Rc = R.loc[:fit_end]                       # H13: cut first, shift afterwards
    miss_etf = [e for e in fs.etfs if e not in Rc.columns]
    if miss_etf:
        raise LagRuleError(f"derive_c4: factor ETF(s) {miss_etf} not in the cache")
    E = Rc[list(fs.etfs)].dropna()
    if len(E) == 0 or E.index.max() > fit_end:
        raise LagRuleError(f"derive_c4: no factor rows on or before {fit_end.date()}")
    M = orthogonaliser(E, fs)
    F = E @ M
    F.columns = list(fs.names)
    print(f"C4 LAG RULE (declared in its own commit; module docstring). Factors "
          f"{', '.join(f'{f}={e}' for f, e in fs.factors)}, GS in that order. Fit era "
          f"{E.index.min().date()}..{E.index.max().date()}, {len(E)} sessions (all four ETFs), cut at "
          f"{fit_end.date()} before any shift (H13). K = {max_lag}, J = {leads}, HAC({DERIVE_RULE_HAC}), "
          f"alpha {DERIVE_RULE_ALPHA}.")
    print("   " + cache_provenance_line(cache_sha, C4_RULE_CACHE_SHA256, C4_RULE_CACHE_ASOF))
    if meta is not None:
        print(f"   cache asof {meta.get('asof')}, fetched {meta.get('fetched_at_utc')}, excluded at fetch "
              f"(no rows or failed validation): {meta.get('excluded', {})}")
    if dropped:
        print(f"   splits read as `adjusted` (yfinance Close already post-split) and not applied: {dropped}")
    universe = list(names if names is not None else fs.universe)
    rows, out = {}, {}
    for n in universe:
        if n not in Rc.columns:
            out[n] = "not in the cache"
            continue
        k = _regression_rows(Rc[n], F, max_lag, leads)
        if k < C4_RULE_MIN_SESSIONS:
            out[n] = f"{k} usable rows < {C4_RULE_MIN_SESSIONS}"
        else:
            rows[n] = k
    in_sample = sorted(rows)
    print(f"   names in the pair set: {len(in_sample)} of {len(universe)}; excluded: {out or 'none'}")
    if not in_sample:
        msg = "no name qualifies: the C4 lag rule has no answer"
        print("   " + msg)
        return dict(L=None, T=None, sample=in_sample, excluded=out, why=msg, splits_dropped=dropped)
    pc = lead_placebo_counts(R, in_sample, fit_end=fit_end, max_lag=max_lag, leads=leads, fs=fs)
    print(f"   sample {pc['first'].date()}..{pc['last'].date()} (last response row; its lead-{leads} row is on "
          f"or before {fit_end.date()}), sessions per name {min(pc['nobs'].values())}..{max(pc['nobs'].values())}; "
          f"{pc['n_pairs']} pairs")
    print("   lag counts  c(l): " + _fmt_counts(pc["lag"]))
    print("   lead counts p(j): " + _fmt_counts(pc["lead"], "m"))
    try:
        rule = placebo_lag_rule(pc["lag"], pc["lead"])
    except LagRuleError as e:
        print(f"   THE RULE HAS NO ANSWER: {e}")
        print("   C4_DIMSON_LAGS stays None; C4's factor readout is UNMEASURED and names this; nothing "
              "defaults to the core's L or to 0 (module docstring, THE C4 LAG RULE, OUTCOMES)")
        return dict(L=None, T=None, counts=pc, sample=in_sample, excluded=out, why=str(e), splits_dropped=dropped)
    at = [j for j, c in pc["lead"].items() if c == rule["T"]]
    print(f"   T = max lead count = {rule['T']} (at lead {at}); first lag not above T: {rule['stop_lag']} "
          f"(count {pc['lag'][rule['stop_lag']]}); so L = {rule['L']}")
    print(f"   module constant C4_DIMSON_LAGS = {C4_DIMSON_LAGS}: "
          + ("equals the rule's L" if C4_DIMSON_LAGS == rule["L"]
             else f"not yet the rule's L = {rule['L']}; set it from the rule in a commit of its own"))
    # the family plateau, beside the rule: nothing is chosen from it
    ks = range(max_lag + 1)
    cum = {}
    for n in in_sample:
        m = _dimson_ols(Rc[n], F, max_lag)
        fam = groups.get(n, "(no family: not in the C4 family map)")
        for k in fs.names:
            cum[(n, fam, k)] = np.cumsum([m.params[f"{k}_{l}"] for l in ks])
    cm = pd.DataFrame(cum).T
    cm.index.names = ["name", "family", "factor"]
    cm.columns = [f"L{l}" for l in ks]
    med = cm.groupby(level=["family", "factor"]).median()
    print("\n   PLATEAU CHECK (nothing is chosen from it): median cumulative summed beta by family and factor, "
          f"lags-only 0..{max_lag} models\n" + med.round(2).to_string())
    return dict(L=rule["L"], T=rule["T"], stop_lag=rule["stop_lag"], counts=pc, sample=in_sample, excluded=out,
                splits_dropped=dropped)


# --------------------------------------------------------------------------- the lag rule

class LagRuleError(ReadoutError):
    """The lead-placebo lag rule cannot place L (module docstring, THE RULE): lag 0 fails
    the placebo, every lag clears it (L censored at K), or its inputs are malformed."""


def lead_placebo_counts(R: pd.DataFrame, names, fit_end: pd.Timestamp = FIT_END,
                        max_lag: int = DERIVE_MAX_LAG, leads: int = DERIVE_RULE_LEADS,
                        alpha: float = DERIVE_RULE_ALPHA, fs: FactorSet = CORE) -> dict:
    """The counts THE RULE decides on (module docstring): one OLS per name on the four
    orthogonal factors at lags 0..max_lag AND leads 1..leads, HAC; c(l) and p(j) are the
    (name, factor) pairs whose lag-l / lead-j coefficient has a two-sided p < alpha.

    H13: R is cut at fit_end BEFORE any shift, so a lead can never reach a 2023 return; the
    cut is then checked explicitly on every name's sample (an explicit raise, not an assert):
    its last response row must sit `leads` sessions before the last factor row, and that row
    must be on or before fit_end. The factors are orthogonalised once on the whole cut era,
    as `derive` always has. Returns dict(lag, lead, n_pairs, nobs, first, last)."""
    names = list(names)
    if not names:
        raise LagRuleError("lead_placebo_counts: no names")
    miss = [c for c in (*fs.etfs, *names) if c not in R.columns]
    if miss:
        raise LagRuleError(f"lead_placebo_counts: not in the returns panel: {miss}")
    fit_end = pd.Timestamp(fit_end)
    Rc = R.loc[:fit_end]                       # H13: cut first, shift afterwards
    E = Rc[list(fs.etfs)].dropna()
    if len(E) == 0:
        raise LagRuleError(f"lead_placebo_counts: no factor rows on or before {fit_end.date()}")
    if E.index.max() > fit_end:
        raise LookaheadError(f"lead_placebo_counts: factor rows reach {E.index.max().date()}, "
                             f"after the fit era's end {fit_end.date()} (H13)")
    M = orthogonaliser(E, fs)
    F = E @ M
    F.columns = list(fs.names)
    lag = {l: 0 for l in range(max_lag + 1)}
    lead = {j: 0 for j in range(1, leads + 1)}
    nobs, first, last = {}, [], []
    for n in names:
        m = _dimson_ols(Rc[n], F, max_lag, leads=leads)
        rows = pd.DatetimeIndex(m.model.data.row_labels)
        k_reg = len(m.params)
        if len(rows) <= k_reg:
            raise LagRuleError(f"lead_placebo_counts: {n} has {len(rows)} sessions for {k_reg} regressors")
        pos_last = int(F.index.get_loc(rows.max()))
        if rows.max() > fit_end or pos_last + leads > len(F) - 1 or F.index[pos_last + leads] > fit_end:
            raise LookaheadError(f"lead_placebo_counts: {n}'s sample ends {rows.max().date()} and its "
                                 f"lead-{leads} row passes {fit_end.date()} (H13)")
        nobs[n], first, last = len(rows), first + [rows.min()], last + [rows.max()]
        for k in fs.names:
            for l in lag:
                lag[l] += int(m.pvalues[f"{k}_{l}"] < alpha)
            for j in lead:
                lead[j] += int(m.pvalues[f"{k}_m{j}"] < alpha)
    return dict(lag=lag, lead=lead, n_pairs=len(names) * len(fs.names), nobs=nobs,
                first=min(first), last=max(last))


def placebo_lag_rule(lag_counts: dict, lead_counts: dict) -> dict:
    """THE RULE's decision (module docstring), on counts already made. T = the largest lead
    count. Lag 0 must exceed T, or this raises. Lags 1, 2, ... are included in order while
    their count exceeds T STRICTLY; a tie stops the sequence; a lag after the first that
    fails is never included. Every lag 1..K clearing T raises (L censored at K). Returns
    dict(L, T, stop_lag): stop_lag is the first lag not included."""
    if not lead_counts:
        raise LagRuleError("placebo_lag_rule: no lead counts, so no placebo bound")
    lags = sorted(lag_counts)
    if lags != list(range(len(lags))) or len(lags) < 2:
        raise LagRuleError(f"placebo_lag_rule: lag counts must cover 0..K with K >= 1, got lags {lags}")
    T = max(lead_counts.values())
    if not lag_counts[0] > T:
        raise LagRuleError(f"placebo_lag_rule: lag 0 count {lag_counts[0]} does not exceed the largest "
                           f"lead count {T}; the factors explain the funds no better than their future "
                           "returns, and no L is meaningful")
    for l in lags[1:]:
        if not lag_counts[l] > T:
            return dict(L=l - 1, T=T, stop_lag=l)
    raise LagRuleError(f"placebo_lag_rule: every lag 1..{lags[-1]} exceeds the largest lead count {T}: "
                       f"L is censored at K = {lags[-1]}. Widen K only under a new rule declared first; "
                       "K is not the answer")


# ------------------------------------------------- after the result: diagnostics, deciding nothing

def episode_rows(f_index: pd.DatetimeIndex, start, end, max_lag: int, leads: int) -> pd.DatetimeIndex:
    """The response rows t whose regressor span, factor rows t-max_lag .. t+leads, touches a
    factor row dated start..end. Dropping these removes the episode from every lag AND lead
    coefficient at once: a row dated weeks before the episode still reaches it through a lead.
    Positions are rows of `f_index`, which are contiguous NYSE sessions in `derive`, so a row
    offset is a session offset. Raises if no factor row falls in start..end."""
    f_index = pd.DatetimeIndex(f_index)
    inside = np.flatnonzero((f_index >= pd.Timestamp(start)) & (f_index <= pd.Timestamp(end)))
    if len(inside) == 0:
        raise ReadoutError(f"episode_rows: no factor row in {start}..{end}")
    lo, hi = int(inside.min()), int(inside.max())
    p = np.arange(len(f_index))
    return f_index[(p + leads >= lo) & (p - max_lag <= hi)]


def _trend_test(counts: dict, n_perm: int = DIAG_PERMUTATIONS, seed: int = 0) -> tuple[float, float, float]:
    """Spearman rho between the offset and its count, with a permutation null (fixed seed):
    (rho, one-sided p that rho is this low, two-sided p). Under exchangeable counts every
    ordering is equally likely, so this is a test of exchangeability that needs no cut chosen
    after seeing the counts."""
    from scipy.stats import rankdata
    x = rankdata(list(counts.keys()))
    y = np.asarray(list(counts.values()), dtype=float)
    if len(y) < 3 or np.all(y == y[0]):
        raise ReadoutError(f"_trend_test: {len(y)} counts, {len(set(y.tolist()))} distinct; a rank "
                           "correlation needs at least 3 counts that are not all equal")

    def rho(v):
        r = rankdata(v)
        return float(np.corrcoef(x, r)[0, 1])
    obs = rho(y)
    rng = np.random.default_rng(seed)
    null = np.array([rho(rng.permutation(y)) for _ in range(n_perm)])
    return obs, float(np.mean(null <= obs + 1e-12)), float(np.mean(np.abs(null) >= abs(obs) - 1e-12))


def placebo_diagnostics(R: pd.DataFrame, names, groups: dict, fit_end: pd.Timestamp = FIT_END,
                        max_lag: int = DERIVE_MAX_LAG, leads: int = DERIVE_RULE_LEADS,
                        alpha: float = DERIVE_RULE_ALPHA, episode=DIAG_EPISODE,
                        lead_cut: int = DIAG_LEAD_CUT, years: bool = True) -> dict:
    """AFTER THE RESULT (review of 2026-11-02; module docstring, WHAT L = 0 DOES AND DOES NOT
    SHOW). Reproduces the figures that frame the team lead's choice. It DECIDES NOTHING: THE
    RULE is never re-run on any of it, DIMSON_LAGS is never set from it, and the episode window
    and the lead cut were chosen by the review after it had seen the counts.

    Same model as THE RULE (one OLS per name, lags 0..max_lag and leads 1..leads, HAC(5)), on
    the same fit-era cut (H13: R is cut at fit_end before any shift; an explicit raise checks
    it). Returns
      per_name   per name: group, sessions, lead rejections (of 4 x leads), lag 1..3 (of 12);
      bands      {label: (rejections, tests)} for lags 1..3, lags 4..K, leads 1..cut, leads cut+1..J;
      trend      the lead counts' trend test (`_trend_test`);
      T_pairs    the significant (lead, name, group, factor, t) at the lead(s) that set T;
      episode    THE RULE's counts with `episode_rows` dropped from every name: lag, lead, T,
                 rows dropped per name;
      far        lags 0..J beside leads 1..J on the full sample, by like-for-like offset band;
      years      {year: (T, lead at T, lead rejections, tests)} with each calendar year's
                 rows dropped in turn: the control that says whether ANY 8% of the rows moves
                 T as the episode does (only when years=True)."""
    names = list(names)
    fit_end = pd.Timestamp(fit_end)
    Rc = R.loc[:fit_end]                       # H13: cut first, shift afterwards
    E = Rc[list(FACTOR_ETFS)].dropna()
    if len(E) == 0 or E.index.max() > fit_end:
        raise LookaheadError(f"placebo_diagnostics: factor rows must end on or before {fit_end.date()} (H13)")
    F = E @ orthogonaliser(E)
    F.columns = list(FACTOR_NAMES)
    tests_per = len(FACTOR_NAMES)

    def run(drop=None, K=max_lag):
        fits = {}
        for n in names:
            y = Rc[n] if drop is None else Rc[n].where(~Rc.index.isin(drop))
            fits[n] = _dimson_ols(y, F, K, leads=leads)
        lag = {l: sum(int(fits[n].pvalues[f"{k}_{l}"] < alpha) for n in names for k in FACTOR_NAMES)
               for l in range(K + 1)}
        lead = {j: sum(int(fits[n].pvalues[f"{k}_m{j}"] < alpha) for n in names for k in FACTOR_NAMES)
                for j in range(1, leads + 1)}
        return fits, lag, lead

    def band(c, lo, hi):
        ks = [k for k in c if lo <= k <= hi]
        return sum(c[k] for k in ks), len(ks) * len(names) * tests_per

    fits, lag, lead = run()
    per = []
    for n in names:
        p = fits[n].pvalues
        per.append(dict(name=n, group=groups.get(n, "?"), sessions=int(fits[n].nobs),
                        leads_rejected=sum(int(p[f"{k}_m{j}"] < alpha) for k in FACTOR_NAMES
                                           for j in range(1, leads + 1)),
                        lead_tests=tests_per * leads,
                        lag1_3_rejected=sum(int(p[f"{k}_{l}"] < alpha) for k in FACTOR_NAMES
                                            for l in range(1, min(3, max_lag) + 1)),
                        lag1_3_tests=tests_per * min(3, max_lag)))
    bands = {"lags 1..3": band(lag, 1, 3), f"lags 4..{max_lag}": band(lag, 4, max_lag),
             f"leads 1..{lead_cut}": band(lead, 1, lead_cut),
             f"leads {lead_cut + 1}..{leads}": band(lead, lead_cut + 1, leads),
             f"leads 1..{leads}": band(lead, 1, leads)}
    at_T = [j for j, c in lead.items() if c == max(lead.values())]
    T_pairs = [(j, n, groups.get(n, "?"), k, float(fits[n].tvalues[f"{k}_m{j}"])) for j in at_T
               for n in names for k in FACTOR_NAMES if fits[n].pvalues[f"{k}_m{j}"] < alpha]

    drop = episode_rows(F.index, episode[0], episode[1], max_lag, leads)
    efits, elag, elead = run(drop)
    episode_out = dict(window=episode, lag=elag, lead=elead, T=max(elead.values()),
                       rows_dropped={n: int(fits[n].nobs - efits[n].nobs) for n in names},
                       bands={f"leads 1..{leads}": band(elead, 1, leads),
                              f"lags 4..{max_lag}": band(elag, 4, max_lag)},
                       per_name={n: sum(int(efits[n].pvalues[f"{k}_m{j}"] < alpha) for k in FACTOR_NAMES
                                        for j in range(1, leads + 1)) for n in names})

    _, flag, flead = run(K=leads)
    far = {f"{lo}..{hi}": (band(flag, lo, hi), band(flead, lo, hi))
           for lo, hi in ((max_lag + 1, lead_cut), (lead_cut + 1, leads), (max_lag + 1, leads))}

    yrs = {}
    if years:
        for y in sorted(set(F.index.year)):
            d = episode_rows(F.index, f"{y}-01-01", f"{y}-12-31", max_lag, leads)
            _, _, yl = run(d)
            T = max(yl.values())
            yrs[y] = (T, [j for j, c in yl.items() if c == T], *band(yl, 1, leads))
    return dict(lag=lag, lead=lead, at_T=at_T, T_pairs=T_pairs, per_name=pd.DataFrame(per), bands=bands,
                trend=_trend_test(lead), episode=episode_out, far=far, years=yrs)


def lag_rule_counts(models: dict, alpha: float = 0.05) -> dict:
    """The counts behind the four lag rules, from per-name fits at lags 0..K:
    single[l]: (name, factor) pairs whose lag-l coefficient is significant;
    joint[l]:  names whose four lag-l coefficients are jointly significant (Wald);
    tail[L]:   pairs whose sum of the lag L+1..K coefficients is significant (L < K)."""
    any_m = next(iter(models.values()))
    K = max(int(c.rsplit("_", 1)[1]) for c in any_m.params.index if c != "const" and "_m" not in c)
    single = {l: 0 for l in range(K + 1)}
    joint = {l: 0 for l in range(K + 1)}
    tail = {L: 0 for L in range(K)}
    for m in models.values():
        idx = list(m.params.index)
        for l in range(K + 1):
            Rm = np.zeros((len(FACTOR_NAMES), len(idx)))
            for j, k in enumerate(FACTOR_NAMES):
                Rm[j, idx.index(f"{k}_{l}")] = 1.0
                single[l] += int(m.pvalues[f"{k}_{l}"] < alpha)
            joint[l] += int(float(m.wald_test(Rm, scalar=True).pvalue) < alpha)
        for k in FACTOR_NAMES:
            for L in range(K):
                r = np.zeros(len(idx))
                for l in range(L + 1, K + 1):
                    r[idx.index(f"{k}_{l}")] = 1.0
                tail[L] += int(float(m.t_test(r).pvalue) < alpha)
    return dict(single=single, joint=joint, tail=tail)


def _first_gap(counts: dict, bound: int):
    """The last lag before the first lag l >= 1 whose count is within the bound (<= bound).
    None if no lag is. For the majority rule the bound is (majority - 1)."""
    for l in sorted(counts):
        if l >= 1 and counts[l] <= bound:
            return l - 1
    return None


def _smallest_within(counts: dict, bound: int):
    """The smallest L whose count is within the bound. None if none is."""
    return next((L for L in sorted(counts) if counts[L] <= bound), None)


def _fmt_counts(c: dict, p: str = "l") -> str:
    return " ".join(f"{p}{k}:{v}" for k, v in c.items())


def _fmt_runs(m: dict) -> str:
    """{bound: L} as runs, e.g. 'bound 2-6 -> L 3; 7-9 -> L 2'. The last run holds for every
    larger bound too."""
    out, keys, i = [], sorted(m), 0
    while i < len(keys):
        j = i
        while j + 1 < len(keys) and m[keys[j + 1]] == m[keys[i]]:
            j += 1
        last = j == len(keys) - 1
        out.append(f"{keys[i]}{'+' if last else ('' if i == j else '-' + str(keys[j]))} -> L {m[keys[i]]}")
        i = j + 1
    return "bound " + "; ".join(out)


# --------------------------------------------------------------------------- CLI

def _default_cache(fs: FactorSet) -> Path:
    """Each book's default price cache: the core's as ever, and C4's beside it (gitignored)."""
    return DEFAULT_CACHE if fs.book == "cef" else DEFAULT_CACHE_C4


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--asof", required=True)
    f.add_argument("--start", default=FETCH_START.isoformat())
    f.add_argument("--cache-dir", default=None)
    f.add_argument("--symbols", nargs="*", default=[])
    f.add_argument("--book", choices=("cef", "c4"), default="cef")
    c = sub.add_parser("crosscheck")
    c.add_argument("--cache-dir", default=None)
    c.add_argument("--book", choices=("cef", "c4"), default="cef")
    d = sub.add_parser("derive")
    d.add_argument("--cache-dir", default=None)
    d.add_argument("--book", choices=("cef", "c4"), default="cef")
    a = sub.add_parser("analyse")
    a.add_argument("--positions", required=True)
    a.add_argument("--cache-dir", default=None)
    a.add_argument("--out-dir", default=None)
    a.add_argument("--plateau", action="store_true")
    a.add_argument("--book", choices=("cef", "c4"), default="cef")
    args = ap.parse_args(argv)
    fs = factor_set(args.book)
    cache_dir = Path(args.cache_dir) if args.cache_dir else _default_cache(fs)

    if args.cmd == "fetch":
        asof = dt.date.fromisoformat(args.asof)
        check_asof(asof)
        cache = cache_dir
        _refuse_write(cache, CACHE_FILES)            # before any network call
        tickers = sorted(set(fs.etfs) | set(fs.universe) | {s.upper() for s in args.symbols})
        failed: dict = {}
        if fs.book == "cef":
            px, cg = fetch_yf(tickers, dt.date.fromisoformat(args.start), asof)
        else:
            px, cg, failed = fetch_each(tickers, dt.date.fromisoformat(args.start), asof, required=fs.etfs)
        validate_prices(px, asof)
        import yfinance
        meta = {"asof": asof.isoformat(), "start": args.start, "tickers": tickers, "excluded": failed,
                "source": "yfinance Ticker.history(auto_adjust=False, actions=True), keyless",
                "yfinance_version": yfinance.__version__, "capital_gains_column": cg,
                "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        write_cache(cache, px, meta)
        print(f"wrote {len(px)} rows, {len(tickers)} tickers, asof {asof}, into {cache}")
        tab, notes = crosscheck(px, fs=fs)
        _print_crosscheck(tab, notes)
        return 0
    px, meta = load_cache(cache_dir)
    if args.cmd == "crosscheck":
        tab, notes = crosscheck(px, fs=fs)
        _print_crosscheck(tab, notes)
        return 0
    if args.cmd == "derive":
        if args.book == "c4":
            derive_c4(px, meta, cache_sha=cache_sha256(cache_dir))
            return 0
        derive(px, load_groups(), cache_sha=cache_sha256(cache_dir))
        return 0
    P = read_positions(Path(args.positions))
    groups = load_groups() if fs.book == "cef" else c4_families()
    ro = readout(px, P, groups, fs=fs)
    plateau = plateau_check(px, P, groups, ro) if args.plateau else None
    out_root = DEFAULT_OUT if fs.book == "cef" else DEFAULT_OUT_C4
    out = Path(args.out_dir) if args.out_dir else out_root / P["date"].max().date().isoformat()
    write_outputs(out, ro, meta, plateau)
    print((out / "summary.md").read_text())
    print(f"outputs in {out}")
    return 0


def _print_crosscheck(tab: pd.DataFrame, notes: list) -> None:
    print("\nCROSS-CHECK against the repo panels (read-only; reports, decides nothing)")
    for n in notes:
        print("  " + n)
    with pd.option_context("display.width", 200, "display.max_rows", 500):
        print(tab.to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
