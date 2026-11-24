# Idea card — reinvestment buying around the payment date in closed-end funds

**Slug:** `cef_drip_paydate` · **Started:** 2026-11-16 · **Interrupted** on 2026-11-16 (the editor was
force quit about 20 minutes in, during staging) · **Completed:** 2026-11-18 ·
**Status: EXPLORE.** The mechanism as stated fails its sharp test (discount funds do no better than
premium funds). A payment-date price bump exists all the same, in three sessions, and gives part back.
**Reproducer:** `python3 scripts/research/stage_crsp_cefs.py`, `python3 results/ideas/cef_drip_paydate/stage.py r2`,
`… stage.py yahoo`, `… explore.py`, `… checks.py` (the first two with `QUANTT_ENV_FILE` set).
**Panels:** every closed-end fund on CRSP (R2 mirror), 1,123 funds with dead ones included, last date
**2025-12-31**; CRSP `stkdistributions` for the same funds, last ex-date 2025-12-31; NAVs from the desk's
panels (188 tickers, last dates 2026-10-14 and 2026-10-09) and Yahoo `X<TICKER>X` (116 of 237 further
live funds served, fetched 2026-11-16 and 2026-11-18, read to 2025-12-31). Every figure below is
[V: computed 2026-11-18 by the reproducer] unless tagged otherwise.

## What the interruption left, and what was done on resuming

On disk: `stage.py`, `explore.py` (rule written in its docstring, never run), a complete distributions
file, a **0-byte quotes file** (killed mid-write) and 13 Yahoo NAV files. No `results.json`, so no
return had been read. The rule in the `explore.py` docstring was kept word for word and run once.

Fixes made after the interruption (bugs, not choices):
1. `stage.py` rebuilds a staged file that does not open, instead of trusting it (the quotes file).
2. `explore.py`, event-time profile: an event needs only P+5 inside the panel, so P+6..P+10 could index
   past the last row. Those sessions are now left out of that column.
3. `explore.py`, P−10 placebo: one event in the panel's first 11 sessions blanked the placebo for its
   whole group. Such events are now dropped from the placebo only.

Everything in `checks.py` was chosen after the returns were read and is **not pre-specified**.

## The idea

Most closed-end funds run a reinvestment plan. Below net asset value the plan agent buys the reinvested
shares in the market on or after the payment date; at a premium the fund issues new shares and nobody
buys. So discount funds should have a small dated buyer every month and premium funds none.
Agenda item B3 (`results/cef/RESEARCH_AGENDA_2026-10-08.md`) named it; it had not been run.

## The rule (fixed on 2026-11-16, before any return was read)

- **Universe:** every CRSP closed-end fund; at the decision, price ≥ $2 and 21-session average dollar
  volume ≥ $500,000.
- **Event:** a regular monthly or quarterly cash distribution; P = first session on or after CRSP's
  payment date. Used only if public by the decision (session after CRSP's declaration date ≤ P−3).
- **Trade:** decide at P−3, fill at the close of P−2, hold to the close of P+5 (earn P−1..P+5). `shift(2)`
  on `harness.evaluate`.
- **Book:** +0.5 across funds in a window, −0.5 across every eligible fund (the equal-weighted CEF market).
- **Splits:** top against bottom third of flow share (distribution × shares × 20% participation [U,
  assumed] over average dollar volume; breakpoints from the previous year); discount against premium
  funds (price/NAV at P−4; survivors only); month turn against mid month; ex-to-pay gap buckets.
- **Controls:** the same book with P moved ten sessions earlier and later; profile and per-event figure
  with every fund-day within three sessions of an own ex-date blanked.
- **Expected if true:** a gain from P to P+5, larger in the top flow third, present in discount funds and
  absent in premium funds.

Counts: 139,708 pay-date events, 72,490 eligible and known (about 2,794 a year, 783 funds); 911 had no
declaration date and 27 were not public in time. The ex-to-pay gap is 11 sessions at the median
(5th–95th percentile 6–16). 80% of events have P within two sessions of a month end or start.

## What it showed

### Main book, calendar time, gross (no cost, no borrow)

About 78 funds in a window on an average day (median 32), 26% of the eligible universe; turnover 71×
a year; 573 held fund-days had no CRSP row (scored as zero).

| sample | from | to | sessions | return / yr | vol / yr | Sharpe | t | bp per active day | hit rate |
|---|---|---|---|---|---|---|---|---|---|
| full | 2000-02-15 | 2025-12-29 | 6,507 | 5.14% | 3.10% | 1.66 | 8.41 | 2.0 | 54.3% |
| early half | 2000-02-15 | 2013-01-23 | 3,254 | 6.57% | 3.62% | 1.81 | 6.52 | 2.6 | 53.8% |
| late half | 2013-01-23 | 2025-12-29 | 3,254 | 3.69% | 2.48% | 1.49 | 5.36 | 1.5 | 54.8% |
| 2002-2008 | | | 1,763 | 5.85% | 3.49% | 1.68 | 4.43 | 2.3 | 53.2% |
| 2009-2015 | | | 1,762 | 4.37% | 3.09% | 1.41 | 3.73 | 1.7 | 53.6% |
| 2016-2019 | | | 1,006 | 3.84% | 2.07% | 1.85 | 3.70 | 1.5 | 54.7% |
| 2020-2022 | | | 756 | 5.19% | 3.27% | 1.59 | 2.75 | 2.1 | 54.1% |
| 2023-2025 | | | 750 | 3.76% | 2.35% | 1.60 | 2.75 | 1.5 | 56.8% |
| control: P moved 10 sessions earlier | | | 6,507 | −3.08% | 3.04% | −1.01 | −5.14 | −1.2 | 46.1% |
| control: P moved 10 sessions later | | | 6,507 | −1.89% | 2.95% | −0.64 | −3.25 | −0.7 | 46.9% |

The controls are negative, not zero: with an 11-session gap both shifted windows land on the three
sessions after an ex-date, which is the desk's known post-ex fall. They show the pay-date window is not
that fall; they are not clean placebos.

### Per event, buy and hold P−1..P+5, fund less the equal-weighted eligible universe

| group | n | mean bp | median bp | positive | t (by month) | on mid quotes | ex windows blanked |
|---|---|---|---|---|---|---|---|
| all | 72,439 | +9.1 | +3.4 | 50.8% | +3.68 | +8.8 (+3.5) | +4.4 (+2.0) |
| funds with a NAV (survivors) | 40,931 | +12.0 | +6.6 | 51.6% | +4.97 | +12.0 | +6.6 (+2.9) |
| funds without a NAV (dead or unmatched) | 31,508 | +5.5 | −0.9 | 49.8% | +1.43 | +4.7 | +1.6 (+0.5) |
| 2002-08 / 2009-15 / 2016-19 / 2020-22 / 2023-25 | | +14.6 / +6.1 / +9.6 / +0.6 / +16.1 | | | +2.4 / +1.2 / +2.1 / +0.1 / +3.8 | | |

Held funds: median average dollar volume **$1.23M** a day, median price **$13.1**, median market value
**$447M**, median closing bid-ask spread **17bp** (75th percentile 28bp), median assumed flow share
0.46 of a day's volume; 99.96% of
window fund-days had volume. **The pre-specified seven-session gain (9bp mean, 3bp median) is about
half the closing spread.**

### The splits: the mechanism's own predictions

| split (calendar book, long first less second) | Sharpe | t | halves | first against market | second against market |
|---|---|---|---|---|---|
| flow share, top third less bottom third | −0.04 | −0.21 | −0.02 / −0.06 | 0.98 | 1.08 |
| discount less premium (survivors) | −0.05 | −0.27 | 0.34 / −0.48 | 1.58 | 0.63 |
| discount ≤ −2% less premium ≥ +2% | −0.11 | −0.57 | 0.39 / −0.66 | 1.54 | 0.48 |
| month turn less mid month | 0.43 | 2.17 | 0.38 / 0.48 | 0.51 | 1.17 |

**The sharp test fails.** Discount funds do not beat premium funds over the window. Per event: discount
+12.8bp (t +4.95, n 31,409), premium +9.1bp (t +2.24, n 9,522). The same-pay-session difference
(`checks.py` A, not pre-specified; 673 pay sessions with three or more funds a side) is −2.1bp
(t −0.4) raw and +7.3bp (t +1.4) with ex windows blanked. Premium funds, where the plan buys nothing,
rise as much on P−1 and P.

By ex-to-pay gap (per event, P−1..P+5): ≤7 sessions −5.7bp (t −1.9, n 17,039); 8–12 +15.0 (t +4.6,
n 30,042); 13–17 +12.3 (t +2.2, n 24,008); 18+ +9.5 (t +0.7, n 1,350). Monthly payers +9.2 (t +3.1),
quarterly +8.4 (t +1.1).

### Profile by session (bp, fund less universe; t by month in brackets)

| | P−5 | P−4 | P−3 | P−2 | P−1 | P | P+1 | P+2 | P+3 | P+4 | P+5 | P+6 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | −2.9 (−3.8) | −3.1 (−3.2) | +1.7 (+2.0) | −0.6 (−0.7) | **+5.8 (+7.7)** | **+6.0 (+6.7)** | **+5.5 (+5.7)** | −3.3 (−4.1) | −1.6 (−1.9) | −1.4 (−1.5) | −1.4 (−1.5) | −2.2 (−2.7) |
| all, ex windows blanked | −1.3 | −1.6 | +2.4 | −1.1 | +4.8 (+6.3) | +4.9 (+5.5) | +4.4 (+4.5) | −3.7 (−4.6) | −2.3 | −2.5 | −2.1 | −2.4 |
| discount | −3.8 | −3.5 | +2.7 | +1.2 | +6.8 (+7.3) | +5.7 (+6.4) | +7.6 (+7.6) | −3.2 | −1.0 | −1.1 | −1.7 | −1.0 |
| premium | +0.9 | +1.1 | −5.3 | −4.9 | +5.9 (+4.3) | +8.8 (+5.5) | +0.6 (+0.3) | −1.9 | −2.3 | +0.2 | −1.6 | −4.0 |
| mid-month pay dates | −5.2 | −2.4 | +4.4 | +1.8 | +11.9 (+9.5) | +16.3 (+10.9) | +10.2 (+7.5) | −7.3 (−6.7) | −6.3 (−5.9) | −3.4 | −3.3 | −1.6 |

P−10..P+10 for ten groups is in `results.json`. The whole excess is in P−1, P and P+1; from P+2 the
funds lag the market. The only place discount and premium funds differ is P+1 (+7.6 against +0.6;
same-session difference +4.1bp, t +1.5; +5.5bp, t +2.1 ex-blanked), which is where a plan agent would
be buying, and on P itself premium funds do better (−7.2bp, t −3.3).

## Checks made afterwards (`checks.py`, `checks.json`; none pre-specified)

**Three sessions, per event (P−1..P+1) and the giveback (P+2..P+6):**

| group | n | P−1..P+1 mean (t) | median | positive | ex-blanked | P+2..P+6 | spread | ADV |
|---|---|---|---|---|---|---|---|---|
| all | 72,475 | +17.1 (+11.1) | +11.2 | 54.0% | +13.7 (+8.9) | −9.8 (−4.6) | 17bp | $1.23M |
| 2000-2001 | 1,560 | +48.4 (+6.4) | +33.3 | 60.1% | +47.7 | −34.9 | 177bp | $0.82M |
| 2002-2008 | 14,203 | +17.8 (+4.6) | +6.8 | 52.3% | +14.8 | −4.1 (−0.9) | 27bp | $1.03M |
| 2009-2015 | 22,387 | +13.5 (+4.3) | +10.4 | 53.8% | +10.4 | −9.6 | 16bp | $1.19M |
| 2016-2019 | 14,313 | +12.9 (+4.9) | +8.8 | 53.6% | +10.4 | −5.8 (−1.6) | 13bp | $1.30M |
| 2020-2022 | 10,435 | +19.6 (+5.0) | +9.6 | 53.1% | +13.5 | −20.7 | 19bp | $1.42M |
| 2023-2025 | 9,577 | +23.2 (+8.8) | +21.2 | 57.7% | +19.5 | −9.0 | 17bp | $1.45M |
| ADV $0.5–1M | 28,429 | +10.3 (+4.6) | +4.1 | 51.5% | +7.2 | −5.3 | 21bp | $0.71M |
| ADV $1–2M | 24,007 | +16.3 (+9.1) | +11.2 | 54.0% | +13.1 | −9.6 | 17bp | $1.38M |
| ADV $2–5M | 15,694 | +25.1 (+13.9) | +18.7 | 57.0% | +21.5 | −17.5 | 14bp | $2.80M |
| ADV ≥ $5M | 4,345 | +38.0 (+7.5) | +31.5 | 59.9% | +31.7 | −13.4 | 11bp | $7.08M |
| mid-month pay dates | 14,537 | +38.2 (+14.6) | +29.4 | 60.2% | +31.5 | −22.3 (−8.8) | 19bp | $1.40M |
| month-turn pay dates | 57,938 | +11.9 (+6.8) | +6.9 | 52.5% | +9.3 | −6.7 | 17bp | $1.19M |
| discount | 31,409 | +20.1 (+11.9) | +13.6 | 55.3% | +16.9 | −8.1 | 16bp | $1.44M |
| premium | 9,522 | +15.1 (+5.3) | +14.0 | 54.9% | +11.0 | −9.9 | 17bp | $1.49M |
| monthly payers | 65,008 | +14.4 (+8.3) | +9.1 | 53.4% | +11.0 | −6.1 | 17bp | $1.21M |
| quarterly payers | 7,467 | +41.2 (+9.2) | +33.0 | 59.6% | +37.5 | −41.9 (−5.0) | 17bp | $1.45M |

**The same on the canonical harness (shift(2), same weights and benchmark):**

| book (not pre-specified) | Sharpe | t | return / yr | vol / yr | halves | eras 2002-08 … 2023-25 | turnover / yr |
|---|---|---|---|---|---|---|---|
| long P−1..P+1, short the market (decide P−3) | 3.10 | 15.78 | 14.64% | 4.71% | 3.05 / 3.24 | 2.95 / 2.72 / 3.52 / 3.64 / 2.66 | 123 |
| long the market, short P+2..P+6 (decide at P) | 1.03 | 5.23 | 3.93% | 3.82% | 0.75 / 1.48 | 0.85 / 0.50 / 0.85 / 1.77 / 1.80 | 86 |
| long P−1..P+1, short P+2..P+6 | 3.03 | 15.42 | 17.90% | 5.90% | 2.77 / 3.46 | 2.90 / 2.35 / 3.39 / 3.80 / 3.28 | 196 |
| mid-month pay dates only, long P−1..P+1 | 2.72 | 13.84 | 13.36% | 4.90% | 2.72 / 2.75 | 2.73 / 2.45 / 3.04 / 3.34 / 1.83 | 103 |
| discount funds only, long P−1..P+1 | 2.92 | 14.82 | 10.30% | 3.53% | 3.03 / 2.92 | 2.37 / 3.13 / 2.47 / 3.10 / 3.08 | 102 |

These windows were chosen from the profile above, so their Sharpes are inflated by selection and are
not a test. The three-session book holds few names on many days at constant daily weights, which the
net-cash card showed flatters a result; the per-event table is the fairer figure.

**What each known killer says:**

- *Ex-date cycle.* Blanking every fund-day within three sessions of an own ex-date takes the seven-session
  figure from +9.1bp to +4.4bp (t +2.0) and the three-session figure from +17.1 to +13.7bp (t +8.9).
  Not the ex-date drift, though about a fifth of it was.
- *Bid-ask bounce.* On closing mid quotes the seven-session figure is +8.8bp against +9.1bp. Not bounce.
- *Stale closes.* 99.96% of window fund-days traded, and the effect **grows** with liquidity (+10bp in
  $0.5–1M funds, +38bp in funds trading over $5M), the opposite of a thin-fund artifact.
- *Month turn.* 80% of pay dates sit at the month turn, where the benchmark holds the same payers, so the
  relative figure is muted there (+11.9bp); the 20% paid mid month show +38.2bp. It is not the
  turn-of-month effect; it may be part of what that effect is [U].
- *Survivorship.* The main book and all per-event rows use dead funds. Only the discount split is on
  survivors (40,931 of 72,490 events have a NAV; 6,021 in 2002-08 against 6,756 in 2023-25). Funds with
  a NAV score +12.0bp, funds without +5.5bp, so the survivor sample overstates the level; the
  discount-premium *difference* is within the survivors and is nil either way.
- *Volume* (median dollar volume over the fund's own 21-session average): 0.90 at P−1, 1.01 at P, 0.99 at
  P+1, 0.89 at P+2. Top flow third 1.15 at P against 0.89 for the bottom third. Discount and premium
  funds both 1.04 at P. There is extra trading on the pay date, scaled by the size of the payout, and it
  does not depend on the discount.
- *P−1.* A plan agent cannot buy before the cash is paid, yet P−1 rises +5.8bp with no extra volume. It is
  not the last-session-of-month effect: where P is neither first nor last session of a month, P−1 is
  +11.0bp (t +9.4). Unexplained. A CRSP pay date one session late for some funds would produce it [U:
  not checked against fund notices].

## What I conclude

1. **The plan-agent mechanism is not supported.** Its two predictions, larger with flow share and absent
   in premium funds, both fail on the pre-specified splits (Sharpe −0.04 and −0.05). The one trace of it
   is P+1 (+5.5bp more in discount funds, t 2.1, found afterwards).
2. **There is a pay-date bump regardless**: about +17bp over P−1..P+1 and −10bp over the following five
   sessions, in every era, larger in liquid funds, with a volume rise on P that scales with payout size.
   The likely buyer is holders and brokers reinvesting cash on receipt, at premium and discount alike
   [U: an inference, not measured].
3. **As pre-specified it is not tradable for real money**: +9bp mean and +3bp median per event against a
   17bp spread, because the window holds through the giveback. The three-session version is the size of
   the spread on average (17bp against 17bp), and clears it only mid month, in quarterly payers and in
   funds trading over $2M a day (25–41bp against 11–19bp).
4. **For the paper desk, which is scored gross**, a three-session long is the same order as the ex-date
   books and sits about 11 sessions away from them, so it would add to them and not duplicate them. That
   claim rests on a window chosen after the fact and needs a pre-registered forward run.

**Could it run as a shadow book?** The pay date is announced with the declaration, weeks ahead, so the
event is knowable. Which live feed carries it was **not verified**: the Alpaca corporate-actions call
through the desk's MCP returned 401 on 2026-11-18. The discount split would need a live NAV, which the
desk has for its own panels only; the three-session rule does not need one.

## What would reopen it or move it on

- A pre-registered shadow book of the three-session rule (long P−1..P+1 against the CEF market or PCEF,
  mid-month and quarterly pay dates first), scored on broker-confirmed closes. It stands or falls on the
  forward record, not on the table above.
- Fund notices for a sample of pay dates against CRSP's, to settle whether P−1 is real or a dating error;
  if CRSP is a session late the true shape is P..P+2 and a later decision still catches it.
- Plan terms from N-2/N-CSR filings (which funds buy in the market at a discount, and over how many days)
  would let the plan-agent test be run on the funds it applies to, not on a discount sign alone.
- Killed outright if the forward three-session figure is inside the spread, or if the pay-date dating
  check moves the bump onto an ex-date.

## What I could not do

- Verify the live feed (Alpaca 401).
- Get NAVs for dead funds (none exists in the desk's data) or for 121 of 237 live funds outside the desk
  panels (Yahoo does not serve them, or serves them only from 2026).
- Measure plan participation; the 20% is assumed and only the ranking was used.
- Explain P−1.

## Files

`results/ideas/cef_drip_paydate/`: `stage.py`, `explore.py`, `checks.py`, `results.json`, `checks.json`,
`equity.png`. Licensed and fetched rows are outside the repository under `~/quantt_research/cef_drip_paydate/`.
