# Special situations, half 2 of 2: credit and fixed-income events, calendar and mechanical events, macro event days — 2026-10-15

**The question** (team lead, 2026-10-15): *"find all sub event driven / special
situation trading strategies systematically"*. This note is the second half. The
first half covers corporate actions and fund structure, on branch
`ss-catalogue-corp`.

**What this note is.** It catalogues 36 candidate mechanisms. Each one is checked
against the graveyard and given a cheap gate that could kill it before it spends
a trial.

- **Zero trials.** No return, P&L or Sharpe ratio of any strategy was computed,
  and no counter moved.
- **Every figure has one of three origins:**
  - counted by the script below, from panels already in `data/`;
  - fetched from a primary source on 2026-10-15;
  - copied from a repo document and marked `[doc]`.

**Reproduce.**

- `python3 scripts/events/ss_credit_catalogue_counts.py` reproduces every count
  in §2–§4. It reads repo panels only and makes no network call.
- `python3 scripts/events/ss_credit_catalogue_counts.py --alpaca` adds one
  read-only `GET /v2/assets` census. It needs `QUANTT_ENV_FILE`. Last run
  2026-10-16T01:04:55Z, which was the evening of 2026-10-15 in New York.
- Output:
  - `results/events/ss_catalogue_credit/counts_2026-10-15.json`;
  - `results/events/ss_catalogue_credit/alpaca_listed_fixed_income_2026-10-15.csv`.
- Tests: `scripts/events/tests/test_ss_credit_catalogue_counts.py`.

**Labels.**

- **[V]**: fetched and read on 2026-10-15, or produced by the script above that
  day.
- **[S]**: sourced but not re-read, such as a search summary or a secondary
  quote.
- **[U]**: uncertain.
- **[doc: …]**: a figure from a repo document, not re-run here.

External sources are in `docs/REFERENCES.md` §12x; the R-numbers below
refer to its rows.

**What was not redone.** These are referenced, not repeated:

- half 1 (`ss-catalogue-corp`);
- the sprint branches:
  - `ss-cef-events` (CEF corporate actions hedged with ETFs);
  - `ss-spac`;
  - `ss-merger-arb`;
  - `ss-e1-hedge`;
  - `ss-pm-altdata` (Kalshi and alternative data);
  - `ss-event-engine` (the LLM event engine);
- `results/cef/EVENT_DRIVEN_POD_2026-10-12.md` §4;
- `results/cef/RESEARCH_PLAN_2026-10-09.md`;
- `results/xasset/XASSET_RESULTS_2026-10-14.md`.

**The panels this note reads, with their last dates.** Stale is a form of wrong.

| panel | what it holds | last date | used for |
|---|---|---|---|
| `data/forced_flow2/m6_events.parquet` (LEGACY S3) | TRACE grade-flag flips, I → H, per bond | 2025-10-31 | fallen angels |
| `data/forced_flow/rising_star_events_probe.parquet` | TRACE flips, H → I (probe) | 2026-06-04 after filters | rising stars |
| `data/agency_actions_17g7.parquet` | Moody's and Fitch Rule 17g-7 instrument histories | Fitch 2025-06-30; Moody's 2023-12-15 | rating actions |
| `data/auction/auction_calendar.parquet` | Treasury auctions (fiscaldata) | 2026-07-23 | auction cycle |
| `data/events.parquet` | FOMC, CPI, NFP | CPI 2025-03-12; NFP 2025-04-04; FOMC calendar to 2027-12-08 | macro days |
| `data/cef/cef_dist_features.parquet` | CEF distributions | ex-date 2026-09-10 | ex-dates, resets |
| `data/forced_flow2/hyg_jnk_pd_derived.parquet` | HYG and JNK close against official NAV | 2026-07-24 | ETF stress |
| `data/cef/cef_nav.parquet` | live-13 NAVs | 2026-10-14 | bond-holiday observation |
| `results/data/universe_2026-10-08/universe_map.csv` | ADV, shortability | ADV window ends **2024-12-31**; flags 2026-10-08 | capacity |

The 44-name counts read distribution dates and amounts only. No return was
computed on any name, so the H9 name holdout is not touched.

---

## 0. The answer

1. **36 candidates were swept: 16 credit, 12 calendar and 8 macro.**
   - **13 are already in the graveyard**: KILLED, CLOSED or WATCH in the repo
     record (§6).
   - One is parked (BDC NAV, B5).
   - One is an open variant of a killed test (X3, TERM-hedged).
   - One is dead in the literature (the pre-FOMC drift).
   - Three are queued proposals: CA5, CA8 and CA9.
   - The remaining 17 are new to the ledger.
2. **Most credit events live in cash bonds, which Alpaca does not carry.** The
   paper account lists no Treasury or corporate bond
   [doc: `results/ops/alpaca_bond_assets_2026-10-11.md`]. That makes six ideas
   infeasible here, not dead:
   - fallen angels;
   - index-eligibility drops;
   - new-issue concessions;
   - bond tenders;
   - distressed exchanges;
   - the CDS basis.

   The ETF-wrapper version of the strongest of them was already killed
   (S3-wrapper, D4).
3. **What is reachable:**
   - the equity side of credit events: rating downgrades and Chapter 11
     emergence;
   - the listed fixed income Alpaca does carry: **388 preferred issues** (49
     shortable today) and **159 baby bonds** (4 shortable) [V, census];
   - **BDCs**: closed-end funds with no APs, 49 active and 27 shortable today
     [V];
   - calendar hygiene on the live book.
4. **The stale-mark well appears again, in four rows.** They are bond holidays,
   macro days, BDC marks and HY ETF stress.
   - **In ETFs the well is dry.** HY ETF stress is the `single-fund-PD` death.
   - **In CEFs and BDCs it is wet.** For the live book it is a hazard to
     subtract, not a signal to add: a z-score built on a stale NAV fades correct
     price discovery. That is exactly the lesson of `single-fund-PD`.
5. **Macro event days can be measured as a subtract-only risk flag at zero
   trials** (§5).
   - The stale-NAV gate of 2026-10-13 catches only a NAV that exactly repeats.
     A matrix-priced muni NAV that moves part of the way on a rate surprise
     passes it.
   - FOMC, CPI and payrolls give a median 31.5 distinct days a year
     (2007–24) [V].
   - The book carries most of its risk in the muni-versus-taxable spread
     (`docs/BRIEF.md` M5). That is where a rate-day staleness artefact would
     land, so the flag is strongest there.
6. **The top 8**, ranked by breadth × edge × feasibility (§3). Ties are broken by
   information per trial. Each has a zero-trial kill gate.

   | # | id | candidate |
   |---|---|---|
   | 1 | MA1/2 | a macro-day stale-NAV flag that only subtracts |
   | 2 | CA5 | a CEF ex-cycle freeze |
   | 3 | CR3 | the equity drift after rating downgrades |
   | 4 | CR8 | a TERM-hedged credit month-end trade (expected to close itself on arithmetic) |
   | 5 | CR14 | BDC co-held loan marks |
   | 6 | CA9 | bond-holiday stale NAVs |
   | 7 | CR15 | listed preferreds and baby bonds: index inclusion and calls |
   | 8 | CR6 | post-reorganisation equity |

---

## 1. What decides feasibility here

| constraint | what it rules in or out | source |
|---|---|---|
| Alpaca paper lists no Treasury or corporate bond; bonds are Broker-API only | every cash-bond expression is out | [doc: `results/ops/alpaca_bond_assets_2026-10-11.md`] |
| Shortability changes daily; hard-to-borrow shorts need a locate, live accounts only; paper charges no borrow | short-only signals in small or distressed names are fragile, and paper flatters them | [doc: `docs/REFERENCES.md` §12k, §12l]; `CLAUDE.md` landmine 5 |
| The official closing print is mapped for NYSE-listed names only | Arca and Nasdaq ETFs cannot yet be scored on the auction print | [doc: plan item 0.2] |
| Alpha only; carry is closed | every sleeve faces the D4 test | `docs/SYSTEM.md` §5, 2026-10-09 |
| No paid data | CRSP through R2 ends 2024-12-31; no OptionMetrics; no CDX; no syndicate calendars | `docs/DATA.md` §3; `docs/SYSTEM.md` §5, 2026-10-12 |
| Counters, read 2026-10-15 | CEF 52 (bar 2.811); EVENTS 0; XASSET 4, a closed slate; GAMMA 0; NPORT 1; LEGACY 162; MBS 0; POSITIONING 1 | `python3 -m ops.orient` TRIALS for the four bold rows [V]; the `docs/RESEARCH_STATE.md` table for the rest |
| Breakeven | 32.6bp per unit turnover is the CEF book's; liquid ETFs are judged on the 5/15/30bp grid | `CLAUDE.md` |

---

## 2. The catalogue

**Columns.**

- **Mechanism, and who is on the other side.**
- **Event source and timing:** the source, and when the event could first be
  known.
- **Alpaca:** the expression at Alpaca.
- **Capacity:** ADV is CRSP's, over a window ending 2024-12-31 (map of
  2026-10-08).
- **Events/yr; independent groups.**
- **Edge:** from the literature or the terms; never a backtest.
- **Hold:** the holding period.
- **Crowding.**
- **Counter.**
- **Graveyard.**
- **Zero-trial kill gate.**

### 2.1 Credit and fixed-income events

| id | candidate | mechanism; other side | event source; timing | Alpaca | capacity | events/yr; independent groups | edge | hold | crowding | counter | graveyard | zero-trial kill gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CR1 | Fallen angels: IG → HY index exit | Insurers and IG index trackers must sell. Insurers hold over a third of IG bonds, and regulation limits their HY holdings [V R1] | Bloomberg rates a bond on the **middle** of Moody's, S&P and Fitch; it stays in the Returns Universe until month-end. Since 2025-07-29 membership is fixed on the Determination Date, 2 business days before the last business day [V R4]. Agency releases are public the same day | no cash bonds. ANGL (shortable) or FALN (not) against HYG [doc map, 2026-10-08]: that is S3-wrapper | ANGL $20.2m, FALN $20.3m ADV [doc map] | TRACE flips, 2010–25: median 414 bonds and 138 issuer-months a year. 4 of 268 months exceed 400 flips; the 5 busiest months hold 22% of events [V]. 17g-7 corporate IG → HY issuers a year: Fitch median 33, Moody's 40 [V] | Price declines and then reversals, larger when insurers are stressed [V R1; no magnitude in the abstract]. Bonds with no information: −1.21% (t −1.23) over [−14, +13], against −11.42% with negative information; "information effects are large, price pressure effects are small" [V R2]. LEGACY S3: −424bp trough, 82–85% reversal [doc: RESEARCH_STATE WATCH]. **R2 and S3 disagree; neither is picked** | weeks to month-end | fallen-angel ETFs and HY funds are buyers of the flow [U] | LEGACY | **WATCH** S3-forced-flow (D6); **KILLED** S3-wrapper (D4) | none at Alpaca. Reopen only with a cash-bond broker (plan 4.2) |
| CR2 | Rising stars: HY → IG | HY trackers sell, IG buyers arrive; the move is partly priced before the upgrade [S R23] | as CR1 | no ETF expression [doc: agenda §4]; no cash bonds | — | filtered probe: median 163 bonds, 77 issuer-months a year; 2018 alone had 2,306 bonds [V; the definition is U] | no peer-reviewed study found [S, negative search, R23] | weeks | — | LEGACY | **CLOSED** (agenda, "do not build") | none |
| CR3 | Equity after rating downgrades | Investors under-react to downgrades. The returns arrive at later earnings announcements and are worst for small, low-quality firms [V R5]. The losers are slow holders of those names, and it persists because those names are hard to short | agency press release, the same day. History: 17g-7 files, published with a lag, so mark rows `backfilled` [U on the lag] | short the common and hold IWM or a sector ETF long. Needs shortable/ETB. HTB locates are live-only [doc §12k] | small caps; ample at $100k [U] | 17g-7 corporate issuers with any downgrade, per year 2013–24: Fitch median 247, Moody's 596 [V]. These include unlisted issuers [the listed share is U] | −10 to −14% abnormal in the first year after downgrades; nothing reliable after upgrades; 1970–97 [V R5]. Published predictors average 58% lower after publication [doc §12b] | months | public since 2001 | new source (ratings): a ruling is needed | none. The nearest is S3-wrapper (a quality premium, D4) | §4.3 |
| CR4 | Bond tender offers and consent solicitations | The issuer pays a premium to retire bonds or to buy covenant changes [U] | EDGAR SC TO-I and 8-K [U] | the bond leg is not tradable; the issuer's equity reaction is [U] | — | [U] | none fetched [U] | days to weeks | — | EVENTS, if ruled in scope | none | count debt tenders with a listed issuer on EDGAR; kill below 30 a year |
| CR5 | Distressed exchanges | Holders swap into new paper below par to avoid default [U] | EDGAR S-4 and 8-K [U] | distressed equity, mostly HTB [U] | thin | [U] | none fetched [U] | weeks | distressed funds | EVENTS, if ruled in scope | none | as CR4; expected to fail on borrow |
| CR6 | Post-reorganisation equity (Chapter 11 emergence) | Creditors receive equity some cannot hold. The market under-reacts: the evidence is "expectational errors, not mismeasurement of risk" [V R6]. The forced-seller share is [U] | 8-K item 1.03 and plan-effective 8-Ks; the first listed trade [U] | long the new common, short IWM. Some first listings are OTC [U] | small caps | [U]; the gate counts them | 131 emergences: "large, positive excess returns" over 200 days [V R6]. 1994–2011 positive, but 2007–11 mixed, and earnings-announcement reactions negative [V R7] | about 200 days | distressed investors | EVENTS, if ruled in scope | none | §4.8 |
| CR7 | CDS–bond basis; HY ETF against CDX or iBoxx futures | Balance-sheet-constrained dealers leave the basis open. In March 2020 bonds "traded at a large discount to their corresponding CDS" [V R10] | daily | CDX: SEF minimum $25mm IG and $5mm HY; ECP needs more than $10m [doc §12c, §12d]. iBoxx futures need a futures broker [doc §12d] | — | continuous | CDX index arbitrage Sharpe 2.34 gross, 2006–12 [doc §12d] | days | dealer basis desks | — | **CLOSED on access** (pod §4.4) | none until a futures account exists (plan 4.2) |
| CR8 | Credit month-end index extension, TERM-hedged (X3's successor) | Benchmarked managers match the month-end index reset [V R4]. Insurers buy additions on the last day [doc §12i] | calendar, known ahead. The Determination Date moved on 2025-07-29 [V R4]: a regime break inside X3's holdout | long LQD, short β × IEF; both shortable on 2026-10-08 | LQD $2,515.8m, IEF $647.7m ADV | 12 a year, one date each | Treasuries: +0.25%/month, Sharpe 0.88 [doc §12b]. X3: gross 1.04, TERM β 0.34, alpha 5.33%/yr (t 4.54), 58.3 turns, net −0.42 at 15bp [doc: XASSET]. The credit leg is [U] | 3 sessions | public since 2019; last-day volume +46% [doc §12b] | the XASSET slate is closed, so a new declared slate needs a ruling | parent **KILLED** (X3, D4; D2 at 15bp) | §4.4 |
| CR9 | Index-eligibility drops: under 1 year to maturity, called, defaulted | Index trackers must sell at month-end; "uninformed index trackers" demand immediacy [V R8] | fully predictable from stated maturities [V R4] | cash bonds only | — | the LEGACY panel `data/forced_flow/f6_events.parquet` exists; its definition and outcome are [U] | "the cost of immediacy has more than doubled" since 2008 [V R8] | days | dealers | LEGACY | the outcome of the LEGACY F6 work is not in the ledger [U] | none at Alpaca |
| CR10 | New-issue concessions | Issuers pay a concession for certainty; underpricing "is highest among riskier, unknown firms" [V R9] | syndicate calendars (paid data) | primary allocations only | — | many [U] | underpricing in both IPO and seasoned bond deals; no magnitude in the abstract [V R9] | days | primary accounts | — | none | none: infeasible |
| CR11 | Muni tax-loss season and muni fund flows (M3) | Tax-motivated retail sells losers into December; the tax value exceeds the concession [doc: BRIEF M3] | calendar; ICI weekly flows | muni CEFs. MUB is not shortable [doc map] | muni CEF median $0.89m ADV | one season a year; 9 in the fit (D7) [doc: CORE-b] | muni CEF January +2.21%/month against −0.19% in other months (working paper, 1990–2000) [doc §12]; "stronger in recent years" [doc §12] | weeks | CEF specialists | CEF | **CLOSED** CORE-b (kept as a stratum only); flows PARK (agenda) | none new |
| CR12 | Muni summer reinvestment season | June–August coupons and redemptions are reinvested while issuance is light [S R24] | calendar | MUB (not shortable) or muni CEFs: a muni-beta bet | MUB $423.6m | one a year | the Bloomberg Muni index's summer months were generally positive over ten years [S R24] | months | widely known | — | none; D4 (beta) and D7 | D7 by count, one season a year: kill now |
| CR13 | HY ETF creation/redemption stress (March 2020) | Holders sell their most liquid assets for cash; bond ETFs trade below NAV [V R10] | daily PD | HYG or JNK against NAV | HYG $2,650.7m | HYG PD at or below −2%: 7 episodes; at or below −3%: 4 (2007-04 → 2026-07) [V]. March 2020 low −1.28% (03-20); then a **premium** of +4.59% on 2020-04-09 [V] | the Fed's 2020-03-23 and 2020-04-09 announcements reversed it [V R10]. The premium after them is an ETF leading a stale NAV | days | APs | LEGACY | **KILLED** single-fund-PD (D1) and raw-flow-z (D1); **WATCH** E1, S3 | none; usable only as a risk flag (S3's D6 gate) |
| CR14 | BDC non-accruals and co-held loan marks | Several BDCs hold one loan. One marks it down, or to non-accrual, a quarter before the others. The losers are holders of the laggard, priced off its stale reported NAV; no AP forces the price | 10-Q and 8-K. ARCC files NAV 28–35 days after quarter-end [doc §12b] | BDC long/short: 49 active, 27 shortable and ETB today [V] | BDC median $3.31m ADV [doc map] | about 4 reporting seasons a year; at most 49 × 4 reports [V names; arithmetic]; the co-held events are [U] | BDC alpha is 0 on market value but 2.74%/yr on NAV [doc §12c]; the event magnitude is [U] | weeks to a quarter | BDC specialists [U] | new 10-Q source: a ruling is needed [doc: plan] | **PARK** B5 (stale NAV) | §4.5 (G5) |
| CR15 | Listed preferreds and baby bonds: index inclusion and calls | (a) PFF ($12.0bn, 454 holdings [V R21]) and its peers must buy new issues when the index adds them, and retail allottees sell to them. (b) A full call pins the price to the redemption value, and holders above it lose | index rebalance: PHGY rules [U]. Call notices: 8-K and press | 388 preferred issues (371 tradable, 49 shortable); 159 baby bonds (158 and 4) [V]. Hedge with PFF or PGX | per issue [U]; PFF $130.7m, PGX $48.9m ADV | [U]; the gate counts them | no study found [S, negative search, R22] | days around month-end | [U] | NPORT (via N-PORT) or a ruling | none | §4.7 |
| CR16 | Loan and CLO technicals: repricing waves, CLO ETF flows | [U] | — | BKLN, SRLN, JAAA (shortable) | BKLN $243.2m | [U] | CLO-ETF premium/discount is `single-fund-PD` [doc: agenda] | — | — | — | **CLOSED** (agenda) | none |

### 2.2 Calendar and mechanical events

| id | candidate | mechanism; other side | event source; timing | Alpaca | capacity | events/yr; groups | edge | hold | crowding | counter | graveyard | zero-trial kill gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CA1 | Treasury auction cycle | Dealers absorb supply and are paid to warehouse it [doc §12b] | fiscaldata calendar, known ahead | TLT, IEF | TLT $3,728.0m | 72 nominal coupon auctions a year (median 2010–25), 12 in refunding weeks [V] | 8.62bp/month (t 3.65), 1980–2008, unprofitable net for holds of 6 days or less [doc §12b]; reportedly gone after 2010 [S doc] | ≤ 6 days | dealers | XASSET or LEGACY | **CLOSED** (agenda, D2) | none |
| CA2 | Month-end Treasury extension (X3) | as CR8 | as CR8 | IEF | IEF $647.7m | 12 | as CR8 [doc] | 3 sessions | as CR8 | XASSET (4 of 4) | **KILLED** D4, and D2 at 15bp | none; the open variant is CR8 |
| CA3 | Quarter- and year-end window dressing (bond funds; HY in December) | Funds tilt to government bonds at disclosure dates and back afterwards [V R15]. HY shows an abnormal December [S doc §12b] | calendar | HYG or JNK against IEF | ample | 4 a year: 64 events over 2007–22 | tilting shown in holdings and daily returns; no magnitude in the abstract [V R15] | days | — | a new slate | partly **CLOSED** (quarter-end ETF PD, agenda) | D7 by count (64 < 250): kill now |
| CA4 | Pension and balanced-fund rebalancing (X2) | Mandated rebalancers pay for immediacy [doc §12i] | calendar and drift | SPY, IEF | ample | monthly | X2: Sharpe 0.33, t 1.59; the BIL/SHY control scored 0.18 [doc: XASSET] | days | — | XASSET | **KILLED** D1 | none |
| CA5 | CEF ex-date cycle (and bond-ETF ex-dates) | Yield buyers buy before the record date and sell after it [doc: CORE §3] | declared ex-dates, weeks ahead [doc §12d] | a freeze on the live book; standalone capture is D2 [doc: CORE] | the book | deployed 13: median 147.5 ex events a year on 45.5 distinct dates. 43 names: 488 on 110.5 [V] | run-up of +12.65bp (t 2.30) at k = −1; −11.49bp (t −2.24) at +2; standalone about 24bp against 2 × 32.6bp [doc: CORE §3] | a 5-session freeze; adds no turnover | yield retail are the losers | CEF | open proposal (a′); ETF dividend capture **CLOSED** | §4.2 (already passed) |
| CA6 | Distribution-reset announcements (M7) | Cuts re-rate a fund; retail screens on yield [doc: BRIEF M7] | the ex-date panel (not declaration dates) | — | — | deployed 13: 7.8 cuts and 7.6 raises a year; 43 names: 42.4 and 33.2 (2010–25) [V] | M7 failed twice at a 2-day hold. Around specials the z-score is right: −49.5bp/z (t −3.76), 22 dates [doc] | — | — | CEF | **KILLED** (M7, "Distribution data") | none |
| CA7 | Option-expiry pinning | Market makers' delta hedging pins closes to strikes [S R16] | expiry calendar | options are closed except for one test [doc: SYSTEM §5]; the free feed is indicative [doc §12d] | — | 12 monthly expiries | a return shift of at least 16.5bp on expiry dates, in equities [S R16] | 1 day | — | GAMMA | **CLOSED** by ruling | none |
| CA8 | Index-provider rebalance days: fund-of-CEF indices (YYY, PCEF) | Index ETFs must trade thin CEFs at a dated open or close [doc §12b] | YYY is semiannual, announced 6 trading days ahead, with a 3.5% cap; PCEF rebalances at quarter-end [doc §12b] | CEF long/short | thin: CEF ADV about $1m [doc] | 6 dates a year (2 + 4) | [U] | days | CEF specialists | NPORT | queued as B2, "count first" | count from N-PORT snapshots around each reconstitution. Kill below about 100 events, or below 1 day of ADV [doc: agenda B2] |
| CA9 | Bond-holiday stale NAVs (pod N3) | On SIFMA holidays the NAV carries bond prices while the shares trade. The discount then moves with price alone. **The loser is the book, if the band trades the artefact** | SIFMA calendar, published a year ahead [doc §12j] | hygiene on the live book | — | 2 full closes with NYSE open (2026: Oct 12, Nov 11), plus 3 SIFMA 2 p.m. closes on full NYSE days [doc §12j] | on 2026-10-12 all 13 live NAVs moved by 1 cent or less, and 7 not at all. The median of the names' prior-20-session median daily moves was 2 cents [V; one day; Yahoo-sourced] | 1–2 sessions | — | CEF, only if the policy changes | queued as N3 (0 trials) | §4.6 |
| CA10 | Treasury buybacks | Treasury buys off-the-run issues for liquidity support and cash management [V R18] | a tentative schedule each quarter [V R18] | no direct expression | — | up to $38bn liquidity support and $25bn cash management, Aug–Oct 2026 quarter [V R18] | [U] | days | — | — | none | none: no expression |
| CA11 | TIPS CPI-accrual seasonality | The index ratio follows non-seasonally-adjusted CPI with a lag [U] | CPI calendar | TIP against IEF | TIP $254.2m | 12 | [U] | a month | — | — | **CLOSED** (carry; alpha only, SYSTEM §5) | none |
| CA12 | MBS factor and TBA settlement calendar | Paydowns and TBA rolls fall on fixed dates; Bloomberg's index uses the factor date [V R4, footnote 33] | calendar | MBB (shortable) | MBB $277.7m | 12 | [U] | days | — | MBS (0 trials) | none | [U]; carries stale-mark risk |

### 2.3 Macro event days

| id | candidate | mechanism; other side | event source; timing | Alpaca | capacity | events/yr; groups | edge | hold | crowding | counter | graveyard | zero-trial kill gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MA1 | FOMC days, as a subtract-only stale-NAV flag | Matrix-priced and dealer-quoted NAVs lag a rate surprise. The z-score reads the gap as a dislocation and fades a correct price move | Fed calendar, a year ahead; next meetings 2026-10-28 and 2026-12-09 [V R17] | hygiene: remove or shrink the trades decided on a flagged name | the book | 8 scheduled a year [V R17]; 7.9 in the panel, 2007–24 [V] | Corporate-bond-fund NAVs did not move on 31% of days (2009–23); stale-NAV funds see about double the pre-FOMC outflows [V R11]. The 10-year yield moves 1.7bp the same day per 10bp surprise [doc §12b] | 1 session | — | CEF if adopted; 0 trials to measure | a `fomc_event` sleeve type survives in the pre-clean-slate registry, marked "FOSSIL", with no result in this repo [U] | §5 |
| MA2 | CPI and payrolls days, same flag | as MA1 | BLS calendar; a shutdown moves it (MA7) | as MA1 | — | 12 + 12. With FOMC: a median 31.5 distinct days a year (2007–24); 14 days carried two kinds [V] | announcement-day equity excess return 11.4bp against 1.1bp, 1958–2009 [V R14]: a risk premium | 1 | — | CEF if adopted | none | §5 |
| MA3 | The macro-announcement premium as alpha | a premium for macro risk [V R14] | as MA2 | SPY or TLT on event days | ample | about 31 | as MA2 | 1 | widely known | XASSET | **CLOSED** (agenda PARK: D7 or D4) | none: the alpha-only ruling excludes it |
| MA4 | Pre-FOMC drift | Equities rise before FOMC decisions; Treasuries do not [V R12]. The drift "essentially disappeared after 2015" [V R13] | Fed calendar | SPY | — | 8 | as stated | 1 | — | — | not in the ledger; dead in the literature | none |
| MA5 | Treasury quarterly refunding announcements | supply guidance moves the term premium [U] | Treasury, quarterly. The 2026-08-05 statement names 2026-11-04 as the next [V R18]; the Feb/May/Aug/Nov cycle is [S] | the §5 flag | — | 4 | [U] | 1 | — | CEF if adopted | none | fold into §5 |
| MA6 | Debt-ceiling episodes (X-date bills) | Bills maturing near the X-date cheapen [S R20] | Treasury letters on extraordinary measures [U] | BIL and SGOV hold bills; the effect is too small to trade | BIL $628.7m | [U]: CRS R43389 covers 2011–22, not parsed [S R20] | 2023: yields on bills maturing in the expected X-date window rose [S R20] | weeks | money funds | — | none | D7 |
| MA7 | Government shutdowns | Data blackouts; SEC processing slows [U] | CRS: 21 funding gaps since FY1977; 4 with furloughs since FY2014. The last ran 42 days, from 2025-10-01 to 2025-11-12 [V R19] | hygiene: rows on the event engine's calendar | — | 4 since FY2014 | — | — | — | — | none | none. Record shutdown windows; the events panel's CPI and NFP rows end in 2025-03/04 |
| MA8 | Crisis policy announcements (Fed facilities, 2020-03-23 and 2020-04-09) | a lender of last resort ends a fire sale [V R10] | Fed press releases | the §5 flag | — | 2 (in 2020) | they reversed the ETF dislocation [V R10] | days | — | — | none | D7 |

---

## 3. Scoring and the top 8

**How the score is built.**

- **B (breadth):**
  - 3 = at least 100 independent events a year;
  - 2 = 12–99;
  - 1 = fewer than 12, or [U].
- **E (edge):**
  - 3 = an in-repo [V] effect clear of the bar;
  - 2 = published evidence, or a mechanism with partial evidence;
  - 1 = none found, or contrary.
- **F (feasibility at our constraints):**
  - 3 = applicable now;
  - 2 = tradable after a zero-trial gate or a data build;
  - 1 = tradable but blocked (borrow, beta, or a closed ruling);
  - 0 = not tradable at Alpaca.

**The score is B × E × F.** Graveyard rows are scored for reference but not
ranked. Ties are broken by information per trial: the cheaper the gate that can
close the row, the higher it ranks.

| rank | id | B | E | F | score | cheapest gate (trials) |
|---:|---|---:|---:|---:|---:|---|
| **1** | **MA1+MA2 (+MA5) macro-day stale-NAV flag** | 2 | 2 | 3 | 12 | NAV-response measurement (0) |
| **2** | **CA5 CEF ex-cycle freeze** | 2 | 2 | 3 | 12 | already passed; next is a pre-registration (CEF +1) |
| **3** | **CR3 equity after downgrades** | 3 | 2 | 2 | 12 | listing and shortability census (0) |
| **4** | **CR8 credit month-end, TERM-hedged** | 2 | 2 | 2 | 8 | cost arithmetic (0); expected to close itself |
| **5** | **CR14 BDC co-held loan marks** | 2 | 2 | 2 | 8 | G5 match rate (0) |
| **6** | **CA9 bond-holiday stale NAV** | 1 | 2 | 3 | 6 | NAV test on past holidays (0) |
| **7** | **CR15 listed preferreds and baby bonds** | 2 [U] | 1 | 3 | 6 | PFF additions count (0) |
| **8** | **CR6 post-reorganisation equity** | 1 [U] | 2 | 2 | 4 | emergence count (0) |
| 9 | CA12 MBS calendar | 2 | 1 | 2 | 4 | [U] |
| 10 | CA3 quarter-end window dressing | 1 | 2 | 2 | 4 | killed by D7 arithmetic now |
| 11 | MA5, MA7 (fold into #1) | 1 | 1 | 3 | 3 | — |
| 12 | CA8 fund-of-CEF reconstitution (B2) | 1 | 1 | 2 | 2 | B2 count (0) |
| — | CR12, MA6, MA8 | 1 | 1 | 1 | 1 | D7 |
| — | CR4, CR5, CR9, CR10, CA10 | — | — | 0 | 0 | infeasible at Alpaca |
| — | graveyard rows (§6) | — | — | — | — | not ranked |

**Every top-8 row has a gate that costs nothing.** Seven of them can still
close themselves at zero trials. The eighth, CA5, has already passed its gate, so
its next step is a pre-registered CEF trial.

---

## 4. The top 8

### 4.1 Macro-day stale-NAV flag (MA1, MA2, MA5): §5 holds the design

- **Mechanism.** On a scheduled rate-news day the listed price moves at once. A
  matrix-priced muni NAV, or a dealer-quoted loan NAV, moves part of the way and
  catches up over the following sessions. The discount z-score reads the gap as
  a dislocation and trades against a correct move. That is `single-fund-PD`'s
  failure, reproduced on a calendar we know a year ahead.
- **Who loses.** We do, if the band trades it. Nobody is paid to correct it,
  because the NAV is a measurement, not a price.
- **Why the current signal is blind to it.** The stale-NAV gate of 2026-10-13
  triggers only on an exact repeat (`docs/SYSTEM.md` §5). W4 found stale NAV
  explains little of the IC *on average* [doc: W4]. Neither looks at event
  days.
- **Where it should be strongest, and where it should be absent:**
  - strongest in muni and loan CEFs (MHD, MQY, JFR) on large rate-surprise
    days;
  - absent in equity CEFs, whose NAVs are struck on exchange closes, and on
    non-event days with the same |ΔIEF|. **These are the negative controls.**
- **Cheapest kill test (0 trials), still to be written:**
  `scripts/cef/macro_day_staleness.py`. For each deployed name and day, compute
  the NAV change divided by the move implied by the name's beta to same-day
  closes of IEF, HYG and MUB. The beta is estimated strictly before the day.
  Compare event days with non-event days matched on |ΔIEF| quintile, then
  measure the share of the band's turnover decided on event days.
  - **It ends the discussion if** event-day NAV response is not lower than on
    matched days, **or** event days carry no more than their share of sessions
    in turnover.
  - Their share of sessions is about 31.5 ÷ 252, re-measured at run time.
- **Trial cost.** Measuring it costs nothing. A subtract-only spec key is
  CEF 52 → 53, with a byte-for-byte no-op proof.
- **Magnitude.** Small, and bounded. It can only remove trades, so the most it
  saves is the cost and the adverse move of trades decided on flagged
  name-days. That is a TC lever, not new IC [U].

### 4.2 CEF ex-cycle freeze (CA5)

- **Mechanism, loser and gate.** These are in `results/cef/CORE_SIGNAL_CANDIDATES_2026-10-12.md`
  §3 [doc]:
  - the losers are yield buyers who buy before the record date and sell after;
  - the signal has no slope in the five sessions before an ex-date;
  - the placebo calendar does have a slope.
- **The zero-trial gate has already passed.** 20.3% of deployed turnover is
  decided in the pre-ex window [doc].
- **Negative control.** The same freeze on a placebo calendar shifted +10
  sessions.
- **Trial cost.** One CEF trial (52 → 53).
- **Magnitude.** A standalone capture is about 24bp against 2 × 32.6bp, so it is
  D2 as a sleeve. As a freeze it adds no turnover. The prior is 20–30% [doc, U].
- **Why it ranks here.** It is the only top-8 row with in-repo evidence on the
  live book.

### 4.3 Equity after rating downgrades (CR3)

- **Mechanism.** Investors under-react to a downgrade. The return arrives at
  later earnings announcements [V R5].
- **Who loses, and why they persist.** Holders of small, low-quality firms. The
  short side is costly and often unavailable, which is the limit to arbitrage.
- **Where it should be strongest, and where absent:**
  - strongest in small, low-credit-quality issuers and in downgrades that cross
    into HY;
  - **absent after upgrades**, where R5 finds no reliable abnormal returns. That
    is the negative control.
- **The D4 risk, to test.** A downgrade short loads on a distress or quality
  factor (the S3-wrapper precedent). The pre-registration needs a distress or
  quality factor in the D4 regression.
- **Cheapest kill test (0 trials), still to be written:**
  `scripts/events/downgrade_census.py`.
  - (a) Map the 2013–22 corporate downgrades in `data/agency_actions_17g7.parquet`
    to CRSP commons by CUSIP6. Count issuer-events with a listed common whose
    63-session ADV is at or above the spec's `min_adv_usd`.
  - (b) Read today's Alpaca `shortable` and `easy_to_borrow` flags for the
    2024–25 downgraded listed names.
  - **It ends the discussion if** there are fewer than 250 independent
    issuer-events (D7), **or** fewer than half the names are shortable (a
    short-only signal that cannot be shorted).
- **Trial cost.** A new source, so a counter ruling: a ratings counter, or
  LEGACY if the team lead reads 17g-7 as LEGACY's fallen-angel source.
- **Magnitude.** R5 found −10 to −14% over a year. Even after the 58% average
  post-publication decay [doc §12b], that is several hundred bp a year against
  a 32.6bp round trip at about one or two turns a year [U]. **Borrow decides it, and
  borrow is unmeasured** on paper. The costliest-to-short quintile runs about
  411bp/yr [doc §12c, S]. Uncertainty: wide.

### 4.4 Credit month-end extension, TERM-hedged (CR8)

- **Mechanism.** Index-benchmarked managers match the month-end reset; X3
  measured the Treasury version [doc].
- **Who loses.** Benchmarked managers, who pay for immediacy at the reset.
- **Where strongest, and where absent:**
  - strongest in long-duration IG at month-end;
  - absent on other sessions: X3's control, IEF on other sessions, scored
    −0.05 [doc].
- **Cheapest kill test (0 trials): already run.** The script's `x3_breakeven`
  section reads X3's fit at run time. Alpha of 5.33%/yr, divided by turnover of
  58.3 × (1 + 0.34), gives a **breakeven of about 6.8bp per unit turnover**,
  or 9.2bp unhedged [V; arithmetic on
  `results/xasset/trials/x3_fit_2026-10-14.json`].
  - **It ends the discussion if** the measured LQD plus IEF closing cost per unit
    turnover is at or above that breakeven. Measure it from Alpaca closing prints
    and quotes; do not take it from this note (H14).
  - **Also declare the 2025-07-29 Determination-Date change** as a regime break
    [V R4].
- **Trial cost.** The XASSET slate is closed at 4 of 4, so this needs a new
  declared slate and a ruling. It can close itself on a zero-trial budget.
- **Magnitude.** At most about 7bp per unit turnover, against the 15bp grid
  point, and the credit alpha is [U]. **Expect it to close.**

### 4.5 BDC co-held loan marks (CR14)

- **Mechanism.** One loan is held by several BDCs. A mark-down, or a move to
  non-accrual, at one is information about the others' next NAV.
- **Who loses.** Holders of the laggard BDC, priced off a stale reported NAV.
  Nothing forces convergence: a BDC is a closed-end vehicle with no AP.
- **This is the stale-mark well, and it is wet.** BDC alpha is 0 on market value
  but 2.74%/yr on NAV [doc §12c]: the marks are smoothed.
- **Where strongest, and where absent:**
  - strongest where co-holders use different valuation agents, and around
    non-accrual events;
  - absent where co-holders report the same mark in the same quarter. That is
    the negative control, with a permuted co-holder map as the placebo.
- **Cheapest kill test (0 trials): gate G5** [doc: plan], via
  `scripts/events/bdc_coheld_marks.py` (still to be written, through
  `scripts/data/edgar_client.py`).
  - Parse one pre-2023 quarter of schedules of investments for at least 20 BDCs.
    Match loans by borrower, maturity and spread, since ARCC's schedule carries
    no loan identifier [doc §12f].
  - **It ends the discussion if** the match rate is below 70% **or** there are
    fewer than about 150 events a year.
- **Trial cost.** A new 10-Q source, so a counter ruling.
- **Magnitude.** [U]. The breadth is real (49 BDCs, 27 shortable [V]), but the
  timing clusters in about four reporting seasons a year.

### 4.6 Bond-holiday stale NAV (CA9)

- **Mechanism, loser, control.**
  - The NAV carries bond prices while the shares trade.
  - The loser is the book, if the band trades the artefact.
  - Strongest in muni and loan CEFs; absent in equity CEFs on the same days.
- **The one observation so far is consistent with carried prices.** On
  2026-10-12 every live NAV moved by 1 cent or less, against a median 2-cent
  daily move [V; one day].
- **It decides nothing:**
  - it is one day;
  - the panel is Yahoo-sourced, and Yahoo serves stale copies
    (`results/cef/LIVE_NAV_QUALITY_2026-10-12.md` §5);
  - CEFConnect's dated rows, the second source, were not read.
- **Cheapest kill test (0 trials).** NAV changes on 2005–22 SIFMA-closed,
  NYSE-open days against adjacent days, plus the number of band trades decided
  on them, via `scripts/cef/bond_holiday_nav.py` (still to be written). It needs
  a SIFMA history fetcher; whether SIFMA publishes past years is [U].
  - **It ends the discussion if** holiday NAV changes are not smaller than
    adjacent days', **or** the band decided no trades on them.
  - **The next live case is 2026-11-11.**
- **Trial cost.** 0 to measure. CEF +1 only if a rule changes the policy.
- **Magnitude.** Two to five days a year: hygiene, not alpha.

### 4.7 Listed preferreds and baby bonds (CR15)

- **Mechanism.**
  - Index trackers, PFF ($12.0bn, 454 holdings [V R21]), PGX and PSK, must buy
    an issue when it is added.
  - The sellers are retail allottees.
  - Separately, a full call pins the price to the redemption value.
- **Who loses.** Trackers paying for immediacy at the rebalance, as R8 finds
  for bond index exclusions. It persists because trackers must track, and
  because thin $25-par issues are not worth an arbitrageur's balance sheet.
- **Where strongest, and where absent:**
  - strongest in small new issues where index demand is large against ADV;
  - absent in issues already in the index, and in issues below the index size
    floor. That is the negative control; the floor is [S R22].
- **Cheapest kill test (0 trials).** Count PFF's additions per quarter from its
  N-PORT filings, 2019–22, with the existing EDGAR client. Express each as days
  of the issue's ADV, via `scripts/events/pff_index_additions.py` (still to be
  written).
  - **It ends the discussion if** there are fewer than 30 additions a year
    **or** the median addition is below one day of ADV.
- **Trial cost.** NPORT (1 used), or a ruling.
- **Magnitude.** [U]. No study was found [S R22]. Tradability is good: 371
  issues are tradable and 276 are NYSE-listed, so the official closing print is
  mappable [V]. Only 49 are shortable, so the leg is long-only, hedged with PFF.

### 4.8 Post-reorganisation equity (CR6)

- **Mechanism.** Creditors receive equity some of them cannot hold, and the
  market under-reacts [V R6].
- **Who loses.** Forced or indifferent sellers among the former creditors [U].
- **Where strongest, and where absent:**
  - strongest where creditors take most of the new equity;
  - absent where the old equity is kept (no forced-seller base). That is the
    negative control.
- **Cheapest kill test (0 trials).** Count emergences, 2010–22, with a new
  listed common within 30 days: EDGAR 8-K item 1.03 and plan-effective 8-Ks,
  joined to new CRSP permnos. Use `scripts/events/reorg_census.py` (still to be
  written).
  - **It ends the discussion if** there are fewer than 250 events (D7), **or**
    fewer than half list on NYSE or Nasdaq within 30 days.
- **Trial cost.** EVENTS (0), if the team lead rules non-CEF EDGAR events in
  scope.
- **Magnitude.** The 1999 paper reports large 200-day excess returns [V R6]. A
  secondary source quotes 24.6–138.8% [S R7]. The 2007–11 evidence is mixed
  [V R7]. Against a 32.6bp round trip at about two turns a year, cost is not the
  issue; whether the effect survives is. Uncertainty: very wide.

---

## 5. Macro event days as a subtract-only risk flag

**The question.** Can the CEF book's behaviour around FOMC, CPI, payrolls,
refunding, debt-ceiling and shutdown days be measured as a risk flag rather than
an alpha claim? **Yes, at zero trials, and as subtract-only by construction.**

1. **What to measure** (`scripts/cef/macro_day_staleness.py`, still to be
   written; fit period only, the 2023 time holdout sealed):
   - (a) NAV-response ratios on event days against |ΔIEF|-matched non-event
     days, by group: muni, loan, multi-sector, HY;
   - (b) the share of the band's turnover decided on event days;
   - (c) the share of the group spread's move (muni against taxable, M5) on
     event days that NAV catches up on over the next 1–3 sessions.

   None of these is a strategy return. They are NAV levels, ETF closes and the
   band's own decisions.
2. **The rule, if (a) and (b) pass.**
   - On a flagged day, a name whose NAV moved less than a declared fraction of
     its beta-implied move may not open or grow a position decided that
     evening. That follows the event pod's §2.3 rule, "events can only
     subtract".
   - It never adds an order.
   - The fraction is derived from (a), not swept.
   - It is one CEF trial, with a no-op proof.
3. **The calendar.**
   - FOMC from the Fed's page (8 scheduled a year [V R17]). The repo's panel
     builder for it exists only at tag `pre-clean-slate`
     (`_archive/scripts/build_events_deploy.py`).
   - CPI and NFP from BLS.
   - Refunding from Treasury: quarterly [S], next 2026-11-04 [V R18].
   - Shutdowns as calendar-breaking rows [V R19]. The repo's CPI and NFP rows
     end in 2025-03/04, before the 42-day 2025 gap, so the panel needs a fetcher
     before use (`CLAUDE.md`: never hand-copy a data series).
4. **The Kalshi link** (branch `ss-pm-altdata`:
   `scripts/events/kalshi_public_probe.py` and
   `results/events/PREDICTION_MARKETS_ALT_DATA_2026-10-15.md`, unmerged at the
   time of writing). Kalshi lists Fed-decision and CPI markets [S R25]. Two uses
   fit a subtract-only flag:
   - (i) flag only the days where the market's implied outcome is uncertain;
   - (ii) build an ex-post surprise series from the pre-release market price, a
     free stand-in for paid consensus data.

   **Whether Kalshi's history goes back far enough to fit either is [U].** A
   vendor claims there is no backfill [S R25]. Read that job's measured answer
   before designing on it.
5. **What not to build.**
   - Long gamma into scheduled releases: the archived G6 prompt found the
     evidence points the other way (`pre-clean-slate:_archive/docs/prompts/gamma/G6_vrp_research.md`,
     citing Goyal & Saretto 2009 and Ederington & Lee 1996, as read there).
   - The announcement premium as alpha (MA3, D4).
   - The pre-FOMC drift (MA4: absent in Treasuries; gone after 2015).

---

## 6. The graveyard map

**13 of the 36 rows are already in the repo's graveyard.**

| id | status in the repo record | where |
|---|---|---|
| CR1 | WATCH S3-forced-flow (D6); KILLED S3-wrapper (D4) | `docs/RESEARCH_STATE.md` |
| CR2 | CLOSED: rising stars | `results/cef/RESEARCH_AGENDA_2026-10-08.md` §4, "Closed" |
| CR7 | CLOSED on access: CDX and equity–CDS | `results/cef/EVENT_DRIVEN_POD_2026-10-12.md` §4.4 |
| CR11 | CLOSED: CORE-b (a stratum, not a sleeve); flows PARK | `docs/RESEARCH_STATE.md` CLOSED; agenda §4 |
| CR13 | KILLED: single-fund-PD and raw-flow-z (D1); WATCH E1 and S3 | `docs/RESEARCH_STATE.md` |
| CR16 | CLOSED: CLO-ETF premium/discount | agenda §4 |
| CA1 | CLOSED: Treasury auction cycle (D2) | agenda §4 |
| CA2 | KILLED: X3 (D4, and D2 at 15bp) | `docs/RESEARCH_STATE.md` |
| CA4 | KILLED: X2 (D1) | `docs/RESEARCH_STATE.md` |
| CA6 | KILLED: M7 and "Distribution data" | `docs/RESEARCH_STATE.md`; `docs/BRIEF.md` §2 |
| CA7 | CLOSED by ruling (options) | `docs/SYSTEM.md` §5 |
| CA11 | CLOSED by ruling (carry; alpha only) | `docs/SYSTEM.md` §5, 2026-10-09 |
| MA3 | CLOSED: macro-announcement premium (agenda PARK) | agenda §4 |

**Also not new:**

- CR14 is parked (B5).
- CR8 is an open variant of the killed X3.
- MA4 is dead in the literature.
- CA5, CA8 and CA9 are queued proposals (CORE (a′), B2, N3).
- The pre-clean-slate registry names fossil `fomc_event` and `eom_duration`
  sleeve types, and fallen-angel trackers (`ff_t3_downgrade_tracker`). Their
  outcomes are not in this repo. **Treat MA1, CA2 and CR1 as possibly tried
  before [U]**, and do not cite those fossils as evidence either way.

**The patterns, again.**

1. **Five rows are the stale-mark well:** CR13, CA9, MA1, MA2 and CR14. It is dry
   in ETFs (CR13 is dead) and wet in CEFs and BDCs. On the live book it is a
   hazard to subtract.
2. **Liquid-ETF calendar effects die of term premium or costs:** X3, the auction
   cycle and X2.
3. **The breadth that remains in credit sits on the equity side:** CR3 and CR6.
   It brings the short-borrow problem and the distress-factor D4 risk with it.

---

## 7. What is not established

- **No candidate here has been tested.** Every row is a mechanism and a gate.
- **The TRACE-flag event panels count bonds by a vendor grade flag, not by the
  index providers' middle-rating rule.**
  - The fallen-angel panel's issuer counts jump in 2019: 297 issuers that year
    and 168–465 a year over 2019–25, against 28–96 a year in 2010–18. They look
    high beside the 17g-7 IG → HY counts of 19–112 issuers a year. All of these
    counts are in the script's `per_year` output.
  - Treat both as [U] until the two are reconciled.
- **The 17g-7 histories are published with a lag.**
  - Moody's ends 2023-12-15 in the panel.
  - Any backtest on them must mark rows `backfilled` (pod §3.6).
  - The share of downgraded issuers with a listed common is unmeasured.
- **The census classifies by asset name.** 388 preferreds and 159 baby bonds is
  a count by regex. The CSV lists every match so it can be checked. Issues whose
  names lack "Preferred", "Notes" or "Debentures" are missed, so it is a lower
  bound. Flags are true on 2026-10-15 only.
- **ADV figures are CRSP's to 2024-12-31**, 21 months stale [doc: universe map
  README].
- **Sources disagree on fallen-angel price pressure.**
  - Ambrose, Cai & Helwege find little pressure [V R2].
  - Ellul et al. find declines and reversals [V R1].
  - The LEGACY S3 study found a −424bp trough with 82–85% reversal [doc].
  - Reported, not reconciled.
- **Several sources are abstracts or summaries only** (R3, R16, R20, R23–R25).
  None may key a pre-registration until the primary text is fetched.

---

## 8. Sources

`docs/REFERENCES.md` §12x (rows R1–R27), added in the same commit as this
note.
