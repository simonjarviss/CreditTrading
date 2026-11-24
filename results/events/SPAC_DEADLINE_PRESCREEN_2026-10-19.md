# SPAC deadline-only route: is it alpha? A zero-trial D4 pre-screen — 2026-10-19

**What this is.** The team lead asked on 2026-10-19 for a pre-screen of the
deadline-only SPAC route. In that route the desk buys a SPAC common below its
trust value, makes no election at any vote, and takes the trust when the SPAC
liquidates at its deadline. At Alpaca that exit is a mandatory corporate action
with no fee. The census (`results/events/SPAC_TRUST_CENSUS_2026-10-15.md`)
models the route at about +2.0%/yr over T-bills, gross. The 2026-10-09 ruling
is "alpha only" (`docs/SYSTEM.md` §5): a sleeve must earn beyond beta (D4), and
carry is closed. **This note tries to show that the +2% is not alpha.**

**Zero trials. EVENTS stays at 2. The 2023-01-01 time holdout is sealed.** No
SPAC return dated on or after 2023-01-01 is formed. The script raises on any
CRSP row inside the holdout, and it cuts the cached delisting file (which runs to
2025) before reading it. The history in §2 is an **asset-class** series: every
linked pre-deal SPAC common, equal-weighted, with no discount screen, no
deadline screen and no parameter. It is **not** the census's trade. That trade
buys only below the trust, and a return series for it is the trial's own fit
(§4). Today's figures (§3) are the census's terms-implied yields on its
2026-10-15 snapshot: a price against a trust figure on one date, not a
backtest. **One cost, stated plainly:** this note has now looked at the
2015–22 SPAC asset class. Any later SPAC pre-registration will be written by
people who have seen these fit-period betas. The 2023+ holdout stays its only
blind test.

**Reproduce.**

```bash
python3 scripts/data/fetch_ff_factors.py             # Ken French's library (public; no key)
python3 scripts/data/fetch_pastor_liquidity.py       # Lubos Pastor's page (public; no key)
python3 scripts/events/spac_trust_census.py --frozen # stages the census's CRSP/FRED caches (needs R2 + SEC_USER_AGENT; licensed rows stay in _cache_spac/)
python3 scripts/events/spac_deadline_prescreen.py    # this note: writes the summary JSON below
python3 -m pytest scripts/events/tests/test_spac_deadline_prescreen.py
```

The pre-screen itself reads only gitignored caches and committed files. It
opens no network connection and reads no credentials. For this note its CRSP,
names, delisting and DTB3 caches were copied, byte for byte, from the census's
own `_cache_spac/`. Every figure below is in
`results/events/spac/spac_deadline_prescreen_summary_2026-10-19.json`. That file
holds aggregates only, with no permno and no CRSP row, because CRSP is
licensed and this repository is public.

**Data dates.**

| source | coverage |
|---|---|
| CRSP `dsf` (prc, bid, ask), `dsenames`, `stkdelists` for the census's 1,085 linked SPAC commons | 2014-03-12 → **2022-12-30**; nothing later is read |
| French daily and monthly FF5 + UMD | CRSP vintage 202608, daily to 2026-08-31, fetched 2026-10-19T20:36Z; used to 2022-12-30 |
| Pastor–Stambaugh traded liquidity (LIQ_V), monthly | "updated through DEC 2025", fetched 2026-10-19T20:36Z |
| HYG and IEF total returns, `data/etf_daily.parquet` | source `crsp` for every row used; panel last date 2026-10-09, used to 2022-12-30 |
| FRED DTB3 (the census's bill) | to 2026-10-14 (4.10%), the census's cache |
| Census live snapshot (prices, trust, ADV) | **2026-10-15 close**, four days old; deadlines and votes have moved since (the IBKR note lost TVA and BEAG this way) |

**Labels.** [V] means our own method, re-run on the cited source, or read on
the fetched page. [S] means sourced but not re-read. [U] means unknown.
**[model]** marks the census's accrual model: the trust earning the bill rate,
gross of trust taxes and withdrawals, which makes it an upper bound. Sources are
in `docs/REFERENCES.md` §12at.

---

## 0. The answer

**Verdict: the deadline-only route does not pass D4 at zero trials.**

1. **As an asset class it fails D4.** The series holds every pre-deal SPAC
   common, 2019–22, executable closes, shift(2).
   - **Alpha:** **+8.93%/yr, t 2.18** (daily, Dimson). The bar is 3.0.
   - **Market beta:** **0.090** daily (t 3.58), **0.154** weekly and **0.463**
     monthly. The bar is 0.10. The beta grows with the horizon: stale prices
     hide it at the daily frequency.
   - **Down markets:** **beta 0.53** in months when the market fell more than
     4% (8 months, t 2.17), against 0.17 above that line. That is the short
     index put that killed merger arbitrage (SS5-MA: 0.49).
   - **No declared cut reaches t 3.0.** The highest is 2.66.
   - **Code: D4**, a risk premium in costume.
2. **The census's own trade cannot be tested at zero trials.** That trade buys
   below the trust when there is no deal mania.
   - **2022 is the only pre-2023 year like today.** Rates were rising, SPACs
     were liquidating, and the deal option was dead. Its betas pass: market
     0.020, HY −0.024, TERM −0.024.
   - **Its alpha does not.** Over French's one-month bill it is **+1.72%/yr,
     t 1.93**. **Over the census's own 3-month bill it is +0.93%/yr, t 1.05**:
     less than half the modelled +2.0%.
   - **One year is too short.** Reaching t 3 at 2022's alpha and volatility
     needs about 1.4 years, and 2023 is the sealed holdout.
   - **The conditional series cannot be run here.** Below-trust on pre-2023
     data is the trial's own fit.
3. **The most likely boring explanation:**
   - **2019–22:** the common's embedded **deal option**, which is IPO-sentiment
     equity beta. Five names earn 34% of the gross P&L, and 28 name-days carry
     half the alpha.
   - **Every year:** a **funding-liquidity premium**. The desk would be paid for
     holding a T-bill claim that levered SPAC-arbitrage funds dump in a crisis.
     From 2020-02-20 to 2020-03-23 the series fell **−6.6%** over bills while
     the market fell −34.4%.
   - **What is left in a bond-like year** is about **+0.9%/yr over the 3-month
     bill**.
4. **The one test that would settle it.** Pre-register the census's trade as
   an EVENTS trial:
   - **The trade:** below the point-in-time accrued trust, no deal announced,
     hold through extensions, liquidation or a pre-vote sale as the exit.
   - **The test:** this note's declared D4 regressions, plus the −4% kink and a
     funding-liquidity factor.
   - **Where:** the 2023-01-01 holdout, opened once.
   - **Power:** at 2022's residual volatility (0.68%/yr), the 3.8 holdout years
     reach t 3 only if the alpha is at least **+1.05%/yr**. That is close to
     what 2022 showed over the 3-month bill.
5. **Capacity and turnover at Alpaca** (§3; median ADV, the census's
   convention):
   - **Below the accrued trust:** **$17.9M** across 246 names, about
     **1.2 entries per slot a year**.
   - **Near the deadline:** **$3.4M** across 48 names.
   - **The exit is not free.** "Deadline-only" still ends in a market sale at
     the **69%** of terminal events that are deals (2024–25). Charge that sale,
     and the discount a redeeming buyer still asks for. The near-deadline
     spread then falls from **+3.66%** to **+0.19%/yr at 30bp** [model].
6. **What the team lead must decide** is in §5. Whether to spend an EVENTS
   trial at all. Whether the crash kink and the funding-liquidity exposure
   count as beta under "alpha only". The deal-dating repair. The paper
   plumbing.

---

## 1. What the excess over bills pays for

Each candidate below is a reason a rational seller accepts less than the bill
plus trust. Each is tested against our data where the data allow.

| candidate | mechanism | evidence | beta, or alpha? |
|---|---|---|---|
| **Liquidity** | A ~$10 claim that trades in blocks. The census measured a median daily dollar volume of $3.5k (93 of 288 names at zero, 63 sessions to 2026-10-15). A seller who must exit before the deadline pays for the bid | Historical members traded on 37–88% of sessions by year (§2.2). The bid–ask bounce is worth **~1.0%/yr** of the measured excess: closes earn 10.08%/yr against 9.06% on quote midpoints (2019–22), and 2.66% against 1.69% (2015–18) [V] | A **liquidity premium**. The PS traded-liquidity beta is 0.11 (t 1.83, monthly, report-only) |
| **Lock-up to an uncertain date** | The "next deadline" is the earliest date. 89% of first events in 2024–25 were votes (extension or deal) [V census], and sponsor-deposit extensions open no redemption window [V census quotes] | Below the accrued trust, the spread to the next deadline is **+2.08%**, and to the latest deadline any filing allows **+1.98%** [model]. Near the deadline it is **+3.66% → +2.29%**: the near-deadline premium is mostly the assumption that the deadline holds | Term/maturity risk. Not a factor beta, but it shrinks the annual spread |
| **Trust-value uncertainty** | Payouts are "net of taxes payable" and of up to $100,000 for dissolution, plus working-capital draws (up to $500,000 a year at one SPAC) and third-party claims [V census quotes] | US-domiciled names (34 below the accrued trust) show the **same** modelled spread as Cayman names (212): +2.13% against +2.07% [model]. A US trust pays income tax on its interest and the model is gross of it, so the US names' true spread is lower than shown. **The market does not visibly price the tax, so tax does not explain the Cayman discount** [V levels; tax rates not measured, U] | Not beta; it is a model overstatement |
| **The embedded deal option** | Rights and warrants are stripped from the common, but the common keeps the option on a deal. Gahng, Ritter & Zhang (RFS 2023) call the SPAC-period investment "equivalent to investing in default-free Treasury Bills, along with an option to convert into the common stock of a company going public" [V] | 2019–22: market beta rises from 0.09 (daily) to 0.46 (monthly). **The top 5 names earn 34% of the gross P&L.** Removing the 28 name-days with \|r\| ≥ 50% (the harness's own filter) cuts the alpha from 8.93% to **4.27%/yr (t 1.33)** [V] | **Beta**: IPO-sentiment equity exposure. This is what fails D4 in 2019–21 |
| **Crowding by SPAC-arbitrage funds** | The marginal holder is levered. IPO investors are "almost entirely large institutional investment managers affiliated with hedge funds" (Klausner et al.) [V §12ac]. "Many hedge funds have used leverage when buying SPAC IPOs" (GRZ, n. 20) [V]. The spread over bills sits near their funding spread, and widens when they de-lever | **2020-02-20 → 2020-03-23: −6.6% over bills** (−7.1% on midpoints), against a market of −34.4% and HYG−IEF of −27.1%. It recovered to **+3.6%** cumulative by 2020-06-30 [V]. **Beta 0.53 in months below −4%** [V] | **Beta to arbitrage-funding liquidity**: a short put, the merger-arbitrage signature |

**Who is on the other side, and why they accept less.**

- **The IPO buyer who sells after the units separate.** That buyer's return
  sits in the free warrants and rights (Klausner et al., [V §12ac]) and in new
  IPOs. The census counts **141 SPAC IPOs in 2025 and 149 in 2026** to
  2026-10-15 [V census].
- **Why selling makes sense to them.** Selling the bare common a little below
  the trust recycles capital into the next IPO, which they expect to pay more.
- **The bond leg alone has historically earned about the bill.** GRZ find
  "even liquidated SPACs provide positive returns (2% per year)" over 2010–20,
  on units bought at the IPO and including warrants [V].
- **What the desk would be selling.** The levered arbitrage fund's
  opportunity cost is the desk's premium, so the desk would be the
  balance-sheet provider of last resort. That is paid only while arbitrage
  capital is scarce, and it is lost exactly when that capital runs (March
  2020).

---

## 2. D4 on pre-2023 data

### 2.1 The series, as declared

The specification is in the script's docstring. It was fixed before the first
return was computed. The parts that matter:

- **Universe.** The census's 1,097 SPACs with a first 424B4 dated 2014–22.
  Of these, **1,085 link to a CRSP common** (the census's own `link_crsp`) and
  **1,079 were ever members**. The universe is built from prospectuses, so
  dead SPACs are in it. It is not a survivor sample.
- **Membership, decided at t.** A SPAC joins on its first CRSP *trade*. It
  leaves at the first of: the census's first 425 (the deal), its completion, or
  CRSP's delisting date. Extension votes do not end membership: a
  deadline-only holder does not redeem.
- **Weights and execution.** Equal weights, through `band_frontier.evaluate()`
  (shift(2)). A second computation without `evaluate()` matches it to
  1e-17 [V].
- **Returns.**
  - **P**, the headline: close-to-close on **trade** prices. CRSP's negative
    prc (a bid/ask midpoint on a day with no trade) is never treated as a
    trade.
  - **B**: quote midpoints, where the quoted spread is ≤ 5%.
  - **The payout:** CRSP's delisting value, booked the session after delisting.
    124 were booked, and 2 had no delisting return and were left out, not
    invented.
- **Factors.**
  - MKT = French Mkt-RF.
  - HY = HYG − IEF.
  - TERM = IEF − RF.
  - Betas are summed over lags 0–2 (daily), 0–1 (weekly) and 0–1 (monthly).
    HAC(5/4/3).
- **The D4 bar:** alpha t ≥ 3.0 and every |β| ≤ 0.10.

### 2.2 What the series earned, by era (H5)

Excess is over French's 1-month RF unless the column says DTB3.

| window | sessions | mean members | raw %/yr | excess %/yr (P) | excess %/yr (B, midpoints) | excess over DTB3 %/yr | vol %/yr | Sharpe | AC(1) |
|---|---|---|---|---|---|---|---|---|---|
| **headline 2019–22** | 1,008 | 65 → 518 | 11.19 | **10.08** | 9.06 | 10.07 | 6.73 | 1.50 | 0.17 |
| 2015–18 | 1,006 | 12 → 50 | 3.29 | 2.66 | 1.69 | 2.48 | 3.59 | 0.74 | −0.26 |
| 2019 | 252 | 65 | 12.99 | 10.47 | 7.92 | 10.93 | 8.69 | 1.21 | 0.04 |
| 2020–21 | 505 | 94 → 354 | 14.41 | 14.10 | 13.44 | 14.21 | 7.24 | 1.95 | 0.26 |
| **2022** | 251 | 518 | 2.90 | **1.61** | 1.38 | **0.87** | 0.72 | 2.24 | 0.10 |
| all 2015–22 | 2,014 | | 7.24 | 6.37 | 5.38 | 6.28 | 5.40 | 1.18 | 0.08 |

- **The share of member-days with a trade**, by year from 2015: 37%, 42%, 53%,
  58%, 59%, 80%, 88% and 72%.
- **Compounded excess by calendar year:** 2019 +10.7%, 2020 **+23.6%**, 2021
  +6.7%, 2022 +1.6%.

### 2.3 The D4 regressions

Columns: alpha in %/yr, then (t). Each β is Dimson-summed, then (t).

| frequency, window, series | n | alpha | β MKT | β HY | β TERM | D4 |
|---|---|---|---|---|---|---|
| **daily, 2019–22, P (headline)** | 1,008 | **8.93 (2.18)** | **0.090 (3.58)** | −0.001 (−0.02) | 0.052 (0.73) | **fail: alpha t** |
| daily, 2019–22, B | 1,008 | 7.98 (2.01) | 0.087 (3.37) | −0.018 | 0.038 | fail |
| daily, 2019–22, P net 5 / 15 / 30bp | 1,008 | 8.78 (2.15) / 8.46 (2.07) / 7.99 (1.95) | 0.090 / 0.089 / 0.089 | ≈ 0 | 0.052 | fail |
| **weekly, 2019–22, P** | 209 | 8.20 (1.73) | **0.154 (2.06)** | −0.005 | 0.060 | **fail: β and t** |
| **monthly, 2019–22, P** | 47 | 4.83 (1.69) | **0.463 (2.20)** | −0.382 (−1.07) | −0.464 (−1.26) | **fail** |
| daily, 2020–21, P | 505 | 9.51 (1.42) | **0.176 (4.42)** | −0.040 | 0.092 | fail |
| weekly, 2020–21, P | 105 | 6.37 (0.67) | **0.324 (2.35)** | −0.161 | 0.206 | fail |
| daily, 2019, P | 252 | 7.32 (0.75) | −0.154 (−1.25) | 0.526 (1.32) | 0.756 (1.32) | fail (n small) |
| daily, 2015–18, P | 1,006 | 2.74 (2.17) | −0.031 (−2.23) | 0.092 (3.41) | 0.018 | fail: alpha t |
| daily, 2015–18, B | 1,006 | 1.62 (1.48) | 0.003 | 0.034 | 0.006 | fail: alpha t |
| monthly, 2015–18, P | 48 | 2.66 (2.01) | −0.043 | **0.138** (1.18) | 0.018 | fail |
| **daily, 2022, P** | 251 | **1.72 (1.93)** | **0.020 (2.39)** | −0.024 (−1.54) | −0.024 (−1.83) | **betas pass; alpha t fails** |
| weekly, 2022, P | 52 | 1.75 (2.40) | 0.023 | 0.001 | −0.019 | betas pass; alpha t fails |
| daily, 2022, P, **over DTB3** (added, §2.7) | 251 | **0.93 (1.05)** | 0.019 | −0.023 | −0.025 | betas pass; alpha t fails |
| daily, all 2015–22, P | 2,014 | 5.75 (2.66) | 0.053 (3.03) | 0.037 | 0.060 | fail: alpha t |
| monthly, all 2015–22, P | 95 | 3.71 (2.33) | **0.286 (1.87)** | −0.134 | −0.168 | fail |

**No cut reaches alpha t 3.0. The cost grid does not flip the sign** (+7.99%/yr
at 30bp in the headline), so this is not a cost bet. The monthly regressions for
2019, 2020–21 and 2022 alone have fewer than 30 months and are refused, not
reported.

### 2.4 Down markets

| test | window | β up / above | β down / below | note |
|---|---|---|---|---|
| daily, MKT split at 0 (Dimson) | 2019–22 | 0.031 (t 0.76) | **0.126 (t 3.55)** | falls with the market, does not rise with it |
| same | 2020–21 | 0.106 (2.18) | **0.212 (4.75)** | |
| same | 2022 | 0.017 (1.31) | 0.023 (2.55) | symmetric and small |
| same | all 2015–22 | 0.014 (0.45) | 0.077 (2.71) | |
| monthly, continuous kink at MKT = −4% | 2019–22 | 0.17 (1.87) | **0.53 (2.17)**, 8 months, mean excess −0.71% in them | the merger-arbitrage kink (SS5-MA: 0.49) |
| same | all 2015–22 | 0.10 (1.26) | 0.25 (1.65), 12 months | |
| Covid window, 2020-02-20 → 03-23 | | | SPAC −6.6% over bills; MKT −34.4%; HY −27.1% | +3.6% over bills by 2020-06-30 |

### 2.5 Report-only lines

- **FF5 + UMD + Pastor–Stambaugh LIQ_V, monthly, 2019–22:**
  - **alpha 9.5%/yr, t 2.61**;
  - MKT 0.12 (t 2.58), SMB 0.22, RMW −0.18, CMA 0.14, **LIQ_V 0.11 (t 1.83)**;
  - **fail**.
  - Over all 2015–22: alpha 6.3%, t 2.78; MKT 0.07; SMB 0.12; LIQ_V 0.08.
- **The harness's own |r| < 50% filter:** alpha **4.27%/yr (t 1.33)** in
  2019–22, and 3.17% (t 1.81) over 2015–22. Twenty-eight held name-days are
  past it.
- **The SPACs that went on to liquidate.** This is **ex-post selection and was
  never tradable**. It is shown only to see the trust leg without a deal.
  - 2019–22: alpha 3.85%/yr (t 1.26), MKT β 0.070 daily, 0.13 weekly, 0.24
    monthly.
  - All 2015–22, monthly: 2.42%, t 2.53.
  - **Even the SPACs that never found a deal carry market beta above 0.10 at
    the weekly frequency.** In 2020–21 they too traded on deal hopes.
- **The asset-class book's own turnover:** 3.1× a year.

### 2.6 The standard attacks

| attack | result here |
|---|---|
| 1. Stale price | **Bites.** Members traded on 37–88% of sessions. The market beta is 0.09 daily, 0.15 weekly and 0.46 monthly, so the daily figure, even with two Dimson lags, understates it. The headline uses trade prices only; a midpoint is never a price. A synthetic test checks that the Dimson sum finds a beta a one-day-stale series hides |
| 2. Control group | Not run. The D4 regression is the test, and there is no market where the trust floor is absent but the shares are otherwise the same. The ex-post liquidated subset is the nearest thing, and it also carries beta |
| 3. Execution convention | shift(2), through `evaluate()`. A test pins that a 425 on day *a* earns *a*+1 and never *a*+2 |
| 4. Swept parameter | None. One declared series. The DTB3 regression (§2.7) is a disclosed addition, not a choice between variants |
| 5. Trial count | Zero. The EVENTS bar is √(2 ln 6) = 1.893, but D4's 3.0 binds first |
| 6. Bounce and stale NAV | Bounce is about 1.0%/yr of the excess (P minus B), and 1.0 of 2.7%/yr in 2015–18. There is no NAV here; the trust is a balance-sheet figure |
| 7. Survivorship | The universe comes from prospectuses, so dead SPACs are in it. 12 of 1,097 are unlinked to CRSP and left out. **Deal dating misses foreign private issuers** (§2.8), which biases the series up |
| 8. One name, one era | **Bites.** The top 5 names earn 34% of the 2019–22 gross P&L. The eras disagree: 2020–21 is a boom, 2022 is bond-like |
| 9. Cost grid | No sign flip (+7.99%/yr at 30bp). The edge is not a cost bet; it is beta |
| 10. Arithmetic | **Bites today** (§3): the pre-vote sale and the residual discount cut the near-deadline spread to +0.19% at 30bp |

### 2.7 How the 2021 boom limits the test, and the bill it is measured against

- **Most of the 2015–22 sample is a different market.**
  - In 2020–21, pre-deal SPAC commons traded on rumours and at premiums. They
    earned +23.6% over bills in 2020, and a series built on them measures IPO
    sentiment.
  - Today's live SPACs trade at a median −0.58% to the reported trust
    (census). Deal-announced names sit at +0.19%. That is not 2021.
  - So the 2019–21 betas say little about today's trade. **They do show what the
    common carries when the deal option is in the money**, and the sleeve
    cannot refuse that option: it comes with the share.
- **2022 is the only pre-2023 year that resembles today**, and it is one year:
  - the census's 3-month-out levels show 90% below trust (§3.2 there);
  - rising rates; the liquidation wave (131 liquidations).
  - Its daily residual volatility is 0.68%/yr. At that volatility the census's
    +2%/yr would need 1.0 year for t 3, and 2022's own +1.72% needs 1.4.
  - Pooling 2022 with 2015–21 does not help: the residual volatility rises to
    6.5%/yr, and t 3 at +2% would need about 96 years.
- **Which bill: added after the first run.** The regressions were declared
  over French's 1-month RF. The census states its spread over the 3-month bill
  (DTB3). In 2022, a hiking year, the two averaged 1.29% and 2.02%.
  - Over DTB3, the 2022 excess is **+0.87%/yr** (mean) and the daily D4 alpha
    is **+0.93%/yr, t 1.05**, with the same betas.
  - The 2019–22 headline barely moves (8.92%, t 2.18).
  - **It is reported, not substituted**: both lines are in the JSON, and the
    declared basis stays French RF.

### 2.8 A data defect found on the way

**Hunter Maritime Acquisition Corp.** was a foreign private issuer, which
files 6-K rather than 8-K or 425. The census never dated its deal (status
"unclassified", no 425).

- **The deal closed on 2019-03-21.** Its 6-K press release of that date
  "announced the consummation of its business combination with privately-held
  NCF Wealth Holdings Limited" [V]. The deal was first announced in October
  2018 [S].
- **So the series held a de-SPAC as if it were a pre-deal SPAC.** Its
  post-merger price moved by several hundred per cent in two sessions. That one
  name contributes **8.5 points of March 2019's 8.4-point** arithmetic
  equal-weighted return (`largest_one_name_month` in the JSON). The CRSP rows
  stay in the gitignored cache.
- **It biases the 2019–22 headline up.** The verdict does not depend on it:
  the |r| < 50% line removes it, and the alpha t falls to 1.33.
- **Before any SPAC trial, the census must date deals from 6-K filings too.**
  How many of its 123 unclassified SPACs are foreign private issuers was not
  counted [U].

---

## 3. Capacity and turnover at Alpaca, deadline-only

The census's 2026-10-15 snapshot. The pool is redeemable, Alpaca-tradable,
with a deadline ahead and a modelled spread (274 names). Capacity is the
census's convention: 10% of the **median** daily dollar volume for 20 sessions,
gap screen applied. The spreads are over the 3-month bill [model].

**The exit is not free in most cases.** "Deadline-only" means no election. A
holder who has not elected must **sell in the market before the redemption
deadline** when a deal comes, or ride the merger. The census measured five
live names 13–52% below trust after their vote. In 2024–25 **69% of terminal
events were deals** (92 completions against 41 liquidations; census counts, the
completions a floor) [V]. So the arithmetic below charges:

- the entry at the grid cost;
- a sale at the grid cost on 69% of exits;
- optionally, the discount a buyer who *can* redeem still asks for. That is
  the census's pre-2023 median, **0.59%** below the accrued trust one month
  before the base deadline (a level, census §3.2).

All are amortised over the days to the next deadline.

| set (n) | median days | capacity, median ADV | one-off gain over bills at that capacity | entries per slot a year | one-way turnover a year | spread gross | at 5 / 15 / 30bp, sale charged | at 5 / 15 / 30bp, sale + 0.59% residual (share > 0 at 30bp) |
|---|---|---|---|---|---|---|---|---|
| pool (274) | 311 | not summed (includes names above trust) | | 1.17 | 1.99 | +2.04% | 1.95 / 1.72 / 1.44 | 1.45 / 1.28 / 0.96 (78%) |
| **below accrued trust (246)** | 315 | **$17.9M** (86 names at $0) | $289k | 1.16 | 1.96 | +2.08% | 1.98 / 1.77 / **1.47** | 1.49 / 1.31 / **1.03** (87%) |
| … no deal announced (186) | 381 | $7.4M | $141k | 0.96 | 1.62 | +2.05% | 1.96 / 1.77 / 1.51 | 1.52 / 1.34 / 1.09 (93%) |
| **near deadline ≤ 6 months, below accrued (48)** | 105 | **$3.4M** (top 3 = 52%) | $33k | 3.48 | 5.88 | +3.66% | 3.19 / 1.97 / **1.16** | 1.19 / 0.82 / **0.19** (54%) |
| … no deal announced (25) | 107 | $0.61M (top 3 = 80%) | $11k | 3.41 | 5.77 | +3.74% | 3.35 / 2.38 / 1.70 | 1.73 / 1.28 / 0.30 (68%) |

- **The census's no-sale grid**, for comparison: +1.67% at 30bp on the pool,
  and +1.61% near the deadline.
- **Charging the exit sale** costs the long-dated sets about 0.2–0.5%/yr. It
  costs the near-deadline set most of its spread.
- **Holding past an extension** lowers the spread again: near the deadline,
  +3.66% falls to +2.29% to the latest allowed deadline.
- **A gross ceiling.** At full capacity the one-off gain is about **$0.29M
  over bills** on **$17.9M**, earned over a median 315-day hold [model].
- **Against the target.** The spread over bills is about 1–2%/yr, against
  the ≥ 10%/yr gross target (`docs/SYSTEM.md` §5). Unlevered, the sleeve
  cannot reach it alone.
- **Paper.** Whether Alpaca *paper* processes a SPAC liquidation is [U]
  (census §2.3). If it does not, a paper sleeve's only broker-confirmed exits
  are market sales. The route then becomes a price-convergence trade with no
  guaranteed exit at trust.

---

## 4. Verdict, and what a pre-registration would need

**Verdict at zero trials:**

- **The asset class fails D4.** Alpha t is below 3.0 everywhere. Market beta
  is above 0.10 at the weekly and monthly horizons. The crash-kink beta is
  0.53.
- **The census's below-trust, deadline-only trade is untestable on our data
  without spending the trial.** In 2022, its only analogue year:
  - the betas pass;
  - the alpha over the census's own bill is +0.93%/yr at t 1.05;
  - the year is too short to reach 3.0.

**No D-code is assigned to the census's trade.** A code needs a trial. The
asset class is **D4**.

If the team lead spends an EVENTS trial, the pre-registration must fix, before
any return is computed:

1. **The trade.**
   - Buy when the price is below the **point-in-time** accrued trust: the
     latest 10-Q or 10-K trust *filed by t*, accrued at the bill rate, net of
     the filing's own tax and withdrawal language.
   - Only when no deal has been announced. **Date deals from 8-K, 425 and 6-K**
     (§2.8).
   - Hold through extension votes.
   - Exit at the liquidation payout, or by a market sale at a stated session
     before any deal vote's redemption deadline.
2. **The data the fit needs.**
   - CRSP `ret` with distributions (the cache holds `prc` only). Without it,
     a trust paid out as a distribution while the shell stayed listed reads
     as a price crash.
   - Point-in-time XBRL trust per share.
   - The census's universe with 6-K deal dates.
3. **The D4 test, as declared here.**
   - Daily Dimson-2, weekly and monthly. MKT, HY and TERM, each |β| ≤ 0.10.
   - **The −4% kink beta ≤ 0.10, and a funding-liquidity factor declared as a
     kill.** Pastor–Stambaugh LIQ_V is the one available. Whether it is the
     right one is the team lead's call.
   - Alpha t ≥ 3.0, measured **over the 3-month bill** (the census's basis),
     with French RF beside it.
4. **Where it is judged.**
   - The 2015–22 fit is not blind: this note has seen the asset class.
   - The 2023-01-01 holdout is opened once.
   - **Power** at 2022's residual volatility: alpha ≥ +1.05%/yr for t 3 over
     the 3.8 years to the census date.
5. **The exit must be broker-confirmable.**
   - Either Alpaca confirms in writing what paper does with a SPAC
     liquidation;
   - or a one-name paper plumbing test is run first (an order, so the team
     lead's go, CLAUDE.md rule 1);
   - or the trial says that only market-sale exits count on paper.
6. **The cost grid on the trade's own turnover.** That is about 2× one-way a
   year, and 6× near the deadline, with the sale leg and the residual discount
   charged as in §3.

---

## 5. What the team lead must decide

1. **Whether to spend an EVENTS trial at all.**
   - On this pre-screen, the most a 2022-like regime has shown over the
     3-month bill is about +0.9%/yr.
   - The capacity is $3–18M.
   - The holdout's power is borderline at that size.
2. **Whether the crash kink and funding-liquidity exposure count as beta
   under "alpha only".**
   - The desk's D4 legend tests MKT, HY and TERM betas.
   - The SPAC trade's real risk is the March-2020 kind: a −6.6% gap while
     arbitrage capital runs.
   - Merger arbitrage was ruled D4 on exactly this kink (SS5-MA). Consistency
     says the same rule applies here, and the team lead should say so before a
     pre-registration is drafted.
3. **The census repair**: dating deals from 6-K filings (§2.8), before any
   trial.
4. **The paper plumbing** (§3): a written question to Alpaca, or a one-name
   paper test with an explicit go.

---

## 6. What this does not show, and provenance

- **No return of the census's trade.** §2 is the asset class. The below-trust
  conditional series is the trial.
- **No 2023+ return.** 2023 alone had 170 liquidations and 419 extension
  votes (census §1.2). It is the regime most like today's, and it is sealed.
- **The accrual model** (§3) is gross of trust taxes and withdrawals, and its
  inputs are four days stale. The Q3 10-Qs, due by mid-November, replace it.
  Fetching them needs the SEC contact string in `config/.env`, which this
  session did not read.
- **The 0.59% residual discount** is a pre-2023 level at a fixed point before
  the base deadline. It is not a measured price at a deal vote. The four
  proxies in the census (§2.2 there) sit 0.0–1.2% below their redemption
  value.
- **Code.** `scripts/events/spac_deadline_prescreen.py` reuses the census's
  link, caches and snapshot. It reuses `band_frontier.evaluate()` for the
  execution convention; it builds no new backtester.
  `scripts/events/tests/test_spac_deadline_prescreen.py` has 12 synthetic
  tests: membership without lookahead, the shift(2) exit, the payout, the
  missing-payout count, the trade-price rule, the holdout cut, the exit
  arithmetic, the D4 rule and the Dimson sum. Mutations to the trade-price
  rule, the membership end and the payout booking each fail a test.
- **No counter moves.** EVENTS stays at 2, the 27-name set is untouched, and
  the 2023 holdout is sealed.
