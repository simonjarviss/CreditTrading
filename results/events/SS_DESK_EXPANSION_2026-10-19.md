# The event-driven and special-situations desk: expansion programme, iteration 1 — 2026-10-19

**The question** (team lead, 2026-10-19):

> "We have our current CEF strategy deployed, we want to find more ways to get
> signals, higher returns and more alpha. We are running an event driven & special
> situations desk … add more ideas and continue to iterate on it. I want us to
> expand our desk and strategies at an institutional level. Make agents to help us
> uncover what we can add / how we can add it … our data is through R2 connector
> and any free available data online is available."

The team lead's own list (A1–A7 fund structure, B1–B3 risk-removal flags, C1–C3
listed credit, D1–D3 mainstream) is the seed. This note adds to it, measures it and
says what to build.

**What this note is.**
- It is iteration 1 of a standing programme, not a one-off list.
- Ten agent seats ran at once on branch `research-ss-expansion`. Each took a family
  of candidates from a graveyard check to a measured census and a zero-trial kill
  gate. **57 candidates were assessed:** 31 censused in families A–D, and 26
  generated and screened in family G.
- The same pass built the desk that will run iterations 2 onward: **six new agent
  seats and a saved workflow** (§9).

**Zero trials.**
- No return, P&L, CAR, drift, Sharpe or hit rate of any candidate was computed, on
  any data. No counter moved: CEF 52, GAMMA 0, EVENTS 0, XASSET 4 (`python3 -m ops.orient`,
  TRIALS, 11:09 ET [V]).
- **The 2023-01-01 time holdout stayed sealed.** Event counts run to 2025-12-31 as
  counts only. Pre-event ADV uses CRSP rows dated before 2023, and only for events
  up to 2022-12-31; every census script raises on a 2023+ price row.
- **The 27-name holdout is untouched.** Universe names were counted and flagged,
  and no return of any kind was computed on them.
- The one current price cross-section (C6) is labelled as one day, and only counts
  today's opportunity set.

**Reproduce.** Every figure below is copied from a seat's results file, marked
`[doc: ssx_<seat>]`. That file names the command that produced the figure. The
seats and their entry points (`QUANTT_ENV_FILE` set; never printed):

| seat | family | deliverable | scripts |
|---|---|---|---|
| `ssx_fund1` | A1, A3, A7 | `results/events/ssx/ssx_fund1/CARDS_2026-10-19.md` | `scripts/events/ssx/ssx_fund1_census.py`, `ssx_fund1_docs.py`, `ssx_fund1_a7.py` |
| `ssx_fund2` | A4, A5, A6, A9, A16 | `results/events/ssx/ssx_fund2/CARDS_2026-10-19.md` | `scripts/events/ssx/ssx_fund2_*.py` (7 scripts plus `_common`) |
| `ssx_risk` | B1–B4, B6, B7 | `results/events/ssx/ssx_risk/CARDS_2026-10-19.md` | `scripts/events/ssx/ssx_risk_*.py` (9) |
| `ssx_lcred` | C1–C4, C6, C7, CR15 | `results/events/ssx/ssx_lcred/CARDS_2026-10-19.md` | `scripts/events/ssx/ssx_lcred_*.py` (13) |
| `ssx_ins` | D1, A2, D5, K5 | `results/events/ssx/ssx_ins/CARDS_2026-10-19.md` | `scripts/events/ssx/ssx_ins_*.py` (4) |
| `ssx_fil` | D2, D4, D6–D9 | `results/events/ssx/ssx_fil/CARDS_2026-10-19.md` | `scripts/events/ssx/ssx_fil_*.py` (9) |
| `ssx_gen` | G1–G11 and 18 self-killed | `results/events/ssx/ssx_gen/CARDS_2026-10-19.md` | `scripts/events/ssx/ssx_gen_*.py` (4) |
| `ssx_data` | the data map, R2 inventory | `results/events/ssx/ssx_data/DATA_MAP_2026-10-19.md`, `R2_FULL_INVENTORY_2026-10-19.md` | `scripts/events/ssx/ssx_data_*.py` (4) |
| `ssx_adv` | adversarial priors on all rows | `results/events/ssx/ssx_adv/PRIORS_2026-10-19.md` | `scripts/events/ssx/ssx_adv_cz_priors.py` |
| `ssx_pm` | how we add it: gross, overlay, capacity, power, brokers | `results/events/ssx/ssx_pm/HOW_WE_ADD_IT_2026-10-19.md` | `scripts/events/ssx/ssx_pm_risk_inputs.py`, `ssx_pm_arithmetic.py` |

**Data as read.**
- **R2:** the WRDS mirror, a single snapshot written 2026-06-26 → 07-03 (§7). CRSP
  legacy SIZ runs to 2024-12-31 and the CIZ files to 2025-12-31.
- **EDGAR:** quarterly master indexes 2008Q1–2025Q4 from the shared cache, plus
  about 2,300 live requests across seats, all through `scripts/data/edgar_client.py`
  at 1.5 s spacing.
- **Alpaca:** read-only GETs on 2026-10-19. **The flags are true on that date only**
  (`CLAUDE.md` landmine 5).

**Labels.** `[V]` verified, `[S]` sourced but not re-read, `[U]` uncertain, as in
`docs/REFERENCES.md`. `[doc: …]` means copied from a repo file and not re-run here.
External sources are in `docs/REFERENCES.md` §12ssx, added in the same commit.

---

## 0. The answer

1. **Eight of the 57 candidates pass their zero-trial gates on measured numbers.**
   In order of what they are worth testing (§6):
   - **D1, clustered insider buying across US equities.** 3,485 liquid clusters,
     2010–22.
   - **CR15, preferred-index (PFF) additions.** 101–143 a year in 2020–21, median
     2.02 days of ADV.
   - **D9, the earnings-date delay.** 368 liquid "late" events a year; point-in-time
     from the absence of an 8-K 2.02.
   - **A2, insider buying in CEFs and BDCs.** At least 86 liquid fund-events every
     year.
   - **A1, fund share issuance into a premium.** 55–67 issuers a year; borrow 52%,
     marginal.
   - **D6, 8-K red flags** (auditor changes, non-reliance, unplanned exits). Borrow
     is marginal, and most of the move comes before our fill.
   - **D8, S&P 400/600 changes.** A marginal pass, and the sources disagree on
     whether anything is left at our fill.
   - **B4, taxable downgrades mapped into CEF holdings.** A census pass only; it is
     not yet selective.

   **20 were killed at zero trials** and **11 parked** as calendars or risk
   inputs. One is a governance design (G3, a pooled situations book). The other 17
   of the 26 generated candidates died on the generator's own desk (§4.5).
2. **The biggest single finding is about data, not alpha.**
   - The R2 mirror holds **1,146 tables in 81 schemas** (433 GB), not the six
     curated tables `results/data/R2_CATALOG.md` describes [doc: ssx_data].
   - It includes Compustat, IBES, Thomson insiders (with Form 144 and a 10b5-1
     flag), SDC M&A and New Issues, MSRB muni trades, OTC end-of-day prices, FJC
     bankruptcy filings, CRSP mutual-fund holdings (BIZD, PFF, IJH, IJR), and the
     CRSP CIZ files to **2025-12-31**.
   - Several ideas this desk parked for "no free data" have licensed history in
     our own bucket: merger arbitrage (SDC), lock-ups and IPOs (SDC New Issues),
     earnings timing (IBES, Compustat `rdq`) and the GSE preferreds (OTC).
   - **What R2 lacks** is anything live or after mid-2026, any ratings history
     after 2017-02, Russell membership, a survivorship-free S&P 400/600
     membership, Mergent FISD, OptionMetrics, TAQ and full Audit Analytics.
3. **Three structural truths decide most rows:**
   - **(a) Published anomalies rarely pass this desk's D4 as published.** The
     adversary ran the desk's D4 test on all 207 Chen–Zimmermann predictors with
     enough 2005–24 history: FF5 + UMD + short-term reversal + Pástor–Stambaugh,
     alpha t ≥ 3.0 with every |β| ≤ 0.10. **Two pass (1.0%).** 17% clear the
     alpha leg alone, and the median post-publication return is 0.40× in-sample
     [doc: ssx_adv]. So every mainstream equity sleeve (family D) starts below
     about 1 in 6, unless the build hedges the profitability, size and reversal
     loadings that sink its published siblings.
   - **(b) `shift(2)` fills after the move in six rows: D6, D8, A5, A9, E1, G1**
     [doc: ssx_adv; ssx_fil].
     - D6: 72.7% of listed late-filing notices, and 64% of Item 4.02 filings, are
       accepted after 16:00 ET.
     - D8: S&P announces after the close.
     - G1: Rule 204 close-outs are due by the open, not the close.

     Before any such row spends a trial, measure from acceptance timestamps the
     share of the effect still left after the t+1 close.
   - **(c) Under Reg T the scarce resource is gross, and it decides which sleeves
     earn a place** [doc: ssx_pm].
     - Hedged single-name longs are gross-light: **6.0–9.7 units of gross per unit
       of idiosyncratic vol**, against the CEF book's 17.7 and the E1 muni pair's
       48.6.
     - At the ≥10% mandate a sleeve must earn at least the CEF book's **5.15%/yr
       per unit of gross** [doc: `results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md`].
     - E1 earns about 0.95%/yr per unit of gross at its documented mean: it is
       power-easy but gross-poor.
4. **Recommendation: declare an EVENTS slate of six, N fixed before any test runs**
   (§8.7). The slate bar at N = 6 is √(2 ln 6) = 1.89, so D1's t = 1.96 binds
   first. The six:
   - E1, the CEF/BDC merger pair (ruled);
   - NAV tenders (ruled for drafting);
   - the merger-arbitrage reconstruction (ruled);
   - SPACs via IBKR (ruled);
   - **D1 clustered insider buying** (new; passed);
   - **CR15 PFF additions** (new; passed).

   D9, B1-corp (spin-off removal) and C1-corp (dual-class) are reserves, pending
   their gates and rulings. A1 and A2 act on the book's own universe, so they
   belong on the **CEF** counter as conditioners, and at most one of them should
   run (§6).
5. **The desk now has the seats to repeat this weekly.**
   - Six seats: `event-scout`, `filings-analyst`, `deal-analyst`,
     `credit-situations-analyst`, `data-librarian`, `event-econometrician`.
   - The workflow `ss-census` takes a batch of ideas from screen to an event card
     and a gate verdict, and **cannot compute a return** (§9).
6. **Four corrections to the record, made visibly in this commit** (§12):
   - CRSP's end date in `docs/DATA.md`;
   - "monthly N-PORT" in `docs/RESEARCH_STATE.md`;
   - the submissions-API acceptance time, which can also be early (`docs/REFERENCES.md`
     §12j). That is a lookahead hazard;
   - the corp catalogue's J3 count, recorded here.
7. **What the team lead decides** is bundled in §11: the slate and its N, the
   counters for the new sources, the forward-only protocol, the admission test,
   and the IBKR set-up.

---

## 1. Where the desk stands on 2026-10-19 (the board)

Read from `docs/SYSTEM.md` §5 (team lead, 2026-10-19), `docs/RESEARCH_STATE.md`
and `python3 -m ops.orient` at 11:09 ET [V]. Nothing below is re-decided here.

| line | status | where it lives | counter |
|---|---|---|---|
| **CEF discount book** | live on the Azure VM, armed and fully automatic | `docs/SYSTEM.md`; `ops.orient` PROD | CEF 52 |
| C4: the discount z over five CEF families | PASS on the corrected book; **paper only**, no real-money sleeve (ruled 2026-10-19) | `results/cef/C4_RESULT_2026-10-14.md` §9 | CEF (trial 52) |
| C5: the t+1 opening-auction fill | KILLED, D1; a repair rule for the holdout's D-5 halt is being built | `results/cef/C5_RESULT_2026-10-14.md`; branch `trial-c5-repair` | CEF (trial 51) |
| XASSET slate X1–X4 | closed, all four fail (D1, D1, D4, D4) | `results/xasset/XASSET_RESULTS_2026-10-14.md` | XASSET 4 = N |
| **E1, the CEF/BDC merger pair** | ruled: spend an EVENTS trial, pre-registration first; IBKR borrow admissible for the short leg | branch `research-e1-prereg` (another session) | EVENTS |
| **NAV tenders** (issuer tender at % of NAV) | passed all five zero-trial gates; pre-registration being drafted | `results/events/CEF_CORP_ACTION_CENSUS_2026-10-15.md`; branch `research-navtender-prereg` | EVENTS |
| **Merger arbitrage** | failed D4 on published evidence (a short index put); **not closed**: "reconstruct with a new angle" | `results/events/MERGER_ARB_AND_IBKR_2026-10-15.md`; branch `research-merger-v2` | EVENTS |
| **SPACs** | the gate did not pass at Alpaca on redemption; redeem through IBKR and re-run the gate | `results/events/SPAC_TRUST_CENSUS_2026-10-15.md`; branch `research-spac-ibkr` | EVENTS |
| IBKR as a second broker | open, equities only, for the shorts Alpaca will not lend; the team lead holds the account and the weekly 2FA | branch `ops-ibkr-broker` | — |
| E2, convertible-issuance reversal | pre-registration drafted 2026-10-13, not approved | `results/events/PREREG_E2_CONVERT_REVERSAL_2026-10-13.md` | EVENTS |
| Event-extraction engine | design plus a 50-filing prototype; no API spend: a rules-only baseline and a Claude Code subagent pilot | `results/events/EVENT_ENGINE_DESIGN_2026-10-15.md`; branch `research-event-pilot` | 0 |
| Corp catalogue, top 8 | B1 spin-off index removal, C1 dual-class, K6 SEO reversal, J9 LETF close, K5 lock-up (**killed today**, §4.4), G3 splits, E1 special-dividend ex-day, F1 buybacks | `results/events/SPECIAL_SITUATIONS_CATALOGUE_CORP_2026-10-15.md` §0 | EVENTS / rulings |
| Credit catalogue, top 8 | MA1/2 macro-day stale-NAV flag, CA5 ex-cycle freeze (gate passed), CR3 downgrades, CR8 TERM-hedged month-end, CR14 BDC co-held marks, CA9 bond holidays (next live case 2026-11-11), CR15 preferred adds (**passed today**, §4.3), CR6 post-reorg equity | `results/events/SPECIAL_SITUATIONS_CATALOGUE_CREDIT_2026-10-15.md` §0 | mixed |
| Portfolio layer | designed; HALVE/KILL enforcement being built in report mode | `results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md`; branch `prod-riskcheck` | 0 |
| Stale-NAV gate | `report` mode on prod since `release-20261014-1` | `docs/RUNNER.md` | — |

**Dead, do not rebuild** (`docs/RESEARCH_STATE.md`, `/graveyard`):
- following activist 13Ds;
- distribution-cut signals (M7, "distribution data", killed twice);
- fallen angels through ETFs (S3-wrapper, D4);
- raw fund flows (`raw-flow-z`, D1);
- short-interest crowding (`short-pressure`, D1);
- credit-ETF lead-lag (`leadlag`, D1, non-synchronous prices);
- single-wrapper premium/discount (`single-fund-PD`, D1, stale NAV);
- `pair-reversion` (D2 plus capacity).

---

## 2. What binds

| constraint | fact, with its date | consequence for an event sleeve |
|---|---|---|
| Mandate | **Alpha only**; D4 = alpha t ≥ 3.0 and factor betas ≤ 0.10 (`docs/SYSTEM.md` §5, 2026-10-09) | Published anomalies mostly fail as published (§0.3a). A short-put payoff fails on its kink, not its average beta (merger arb) |
| Execution | MOC (`cls`); paper `late_market`; whole shares for shorts; one netted order per symbol per book, because Alpaca rejects opposite sides as wash trades (`CLAUDE.md`) | An event announced after the close is filled at t+1's close at the earliest. Announcement-day moves are not ours (§0.3b) |
| Leverage | Reg T, `max_gross_stress` 1.80; at the ≥10% mandate gross binds, not vol [doc: ssx_pm] | Admission is judged on return per unit of gross (§8.3) |
| Brokers | Alpaca (main) and IBKR (equities, shorts Alpaca won't lend; weekly manual 2FA) | Never split a pair across brokers (§8.6) |
| Borrow | Alpaca flags churn daily. Today: preferreds 45 of 422 shortable, baby bonds 5 of 168, BDCs 23 of 34 in the BIZD set, 2025 IPOs near day 180 15 of 36, 2025 late filers 109 of 358 [doc: ssx_lcred, ssx_fund2, ssx_ins, ssx_fil] | A short-only sleeve on small or distressed names usually dies here, before any return is seen |
| Data | R2 is a frozen mid-2026 licensed snapshot; free sources are live but some are walled by their terms (§7) | History is mostly available. A live feed for each event type needs a lawful free source or a team-lead ruling |
| Holdouts | 2023-01-01 time holdout sealed; the 27-name holdout is consumed by the first test computing a return on a `cef_universe.csv` name | A source that starts after 2023 cannot be fit (§7.3). A1 and A2 touch universe names (§6) |
| Counters | CEF 52 (bar 2.811); EVENTS 0; XASSET closed at 4; GAMMA 0; NPORT 1; LEGACY 162 | Each new source needs a counter ruling. A declared slate keeps the bar honest (§8.7) |

---

## 3. Method: how an idea becomes a card at zero trials

Every candidate went through the same four steps, which `ss-census` (§9) now
automates:

1. **Screen.** `/graveyard`, both 2026-10-15 catalogues, the event pod §4. Two
   patterns killed most of the dead:
   - a stale-price artifact (price minus a mark nobody trades);
   - a control group scoring as well as the treatment.

   An idea that is either stops here.
2. **Census.** Count the events: raw, distinct issuers a year, distinct months a
   year. Clustering in time is how event counts overstate breadth. Then read
   today's tradability and borrow, pre-event ADV (events up to 2022 only), the
   point-in-time source and its timestamp semantics, and the data terms.
3. **The zero-trial gate.** A test written before the census, with a kill number:
   - fewer than 250 independent liquid events, which is D7;
   - fewer than half shortable on the short leg;
   - median demand under one day of ADV;
   - no lawful live feed;
   - the event already priced before our fill.

   It passes, kills, or cannot be measured, which counts as not established.
4. **The adversary and the PM.** Every row gets:
   - a most-likely cause of death;
   - the closest grave;
   - the D4 factors and the down-market kink test;
   - the negative control to declare in advance;
   - a stale-price check;
   - its gross efficiency, capacity ladder and time to verdict.

**The score is E·S·F**, 0–3 each, the corp catalogue's §2 rubric: E is the
independent events a year, S the plausible edge from terms or literature, F the
feasibility. Ties are broken by information per trial. **S is the weakest axis**,
because it rests on literature, and the adversary's base rate (§5) says to
discount it heavily for anything behavioural.

---

## 4. Iteration-1 results by family

### 4.1 Family A: CEF and BDC structure (closest to our edge)

| id | idea | measured | gate → verdict | E·S·F | adversary prior | seat |
|---|---|---|---|---|---|---|
| **A1** | the fund sells new shares into a premium (CEF ATM or follow-on; BDC ATM; BDC below-NAV authorisations) | 345.5 supplements/yr from 101 funds (2010–22); seeded sample: **55–67 common-share issuers/yr** (95% CIs ~29–93); ATM share rising 30 → 65/yr; 77% of issuing supplements state price > NAV (median +9.0%, indicative); median ADV BDC $2.2m, CEF $1.2m; **borrow 12 of 23 sampled 2024–25 ATM issuers = 52% (CI 33–71%)** | ≥ 30/yr ✓; ≥ ½ shortable ✓ on the point estimate, **marginal** → **PASS** | 3·2·1 = 6 | fragile: the z-score already shorts the premium tail; ATM sales are disclosed in arrears | ssx_fund1 |
| A2 | insider open-market buying in CEFs/BDCs (Form 4 code P) | ≥ 86 liquid fund-events every year 2010–22 with a $10k floor (129–216 without); CRSP match 88.1%; adviser in ~17/yr; 347 events on 40 universe symbols counted only | ≥ 50/yr ✓ → **PASS** | 3·1·2 = 6 | fragile: CEF insiders trade the discount itself; the one study reads it as reversion | ssx_ins |
| A3 | BDC 10b5-1 buybacks below NAV, and the plan expiry | terms disclosed point-in-time (ORCC 2019: $150m, buys below last NAV, 18 months); **~4 BDCs a year with an active plan in 2010–22** | ≥ 30 expiries/yr ✗ → **KILL** (count) | 0·1·2 = 0 | fragile | ssx_fund1 |
| A4 | non-traded BDC listing lock-up releases | 20 strict listings 2011–25; 40 coded releases, **only 18 before 2023, in 6 listings**; median pre-release ADV $2.97m | ≥ 30 ✗ in the fit window → **D7** | 1·1·2 | fragile | ssx_fund2 |
| A5 | adviser change of control, fee cuts, PM exits | **12 sponsor deals touching a listed family in 2010–25** (0.75/yr), 153 funds touched; advisory proposals in 2 of 30 sampled proxies | ~30 independent ✗ → **D7**; keep as an N8 hygiene calendar | 0·1·2 | fragile (day-1 re-rate missed) | ssx_fund2 |
| A6 | control-share provisions slow discount reversion (a CEF trial) | **3 sponsor-level status changes before 2023** (Eaton Vance 2020-08, Nuveen 2020-10, Nuveen suspension 2022-02). Dated rulings: SEC staff withdrew the Boulder letter 2020-05-27; 2nd Cir. *Saba v. Nuveen* 2023-11-30; *ClearBridge* affirmed 2024-06-26 [V] | ≥ 10 changes ✗ → **D7** | 0·1·3 | fragile | ssx_fund2 |
| A7 | fund leverage changes (preferred redemptions, facilities, rating actions on fund preferreds) | Rule 23c-2 notices 63/yr from 43.8 funds; Moody's on fund preferreds 13.5 issuers/yr; **overlap with distribution cuts 35.8% vs a 42.8% control** (±90d), so it is not M7 in disguise | both gates ✓ → **PARK**: no named loser on the common; 77 of 165 events on unshortable Nuveen munis | 2·1·1 | fragile | ssx_fund1 |
| A9 | BIZD (BDC index) review demand | 19.3 events/yr; median trade **0.39 days of ADV** (adds 1.24, deletes 1.30, reweights 0.23); BIZD not shortable | both ✗ → **KILL** | 2·0·2 | fragile (shift(2) misses it) | ssx_fund2 |
| A16 | unlisted BDC / interval-fund tender pressure as a private-credit stress state | unlisted BDC SC TO-I 11 (2014) → 189 (2025); N-23C3A issuers 16 → 140; tendered vs offered machine-readable in 7 of 15 | **risk input, not a trade**; D4 risk high (credit beta) | — | fragile (gamma-timing-C3's shape) | ssx_fund2 |

**A1, the event card** [doc: ssx_fund1]:
- **Mechanism.** A registered CEF may not sell common below NAV, except through
  rights, holder consent or an order (15 U.S.C. 80a-23(b) [V]). So new supply
  arrives only at a premium, and caps it. A BDC may sell below NAV after an annual
  holder vote (ICA §63(2) [V]).
- **Who loses.** Buyers at the premium: retail yield buyers and follow-on
  allottees.
- **Why it persists.** Buyers price on yield; ATM sales are disclosed in arrears;
  sponsors earn fees on new assets; about half the issuers cannot be shorted.
- **The clock.** The supplement's EDGAR acceptance. Before 2020-08-01 both CEFs and
  BDCs filed under Rule 497 (measured: 1,700 BDC 497s and no 424Bs in 2010–19);
  afterwards under 424B.
- **The expression the seat recommends: a short-side conditioner on the live book**
  (CEF counter), not a standalone EVENTS sleeve. Its first test must show that the
  supply event adds information **beyond the z-score's own premium tail**, the
  adversary's main objection. **The borrow pass is marginal:** re-read the flags on
  several dates before relying on it (H14).

### 4.2 Family B: flags that only remove risk from the live book

| id | idea | measured | gate → verdict | E·S·F | seat |
|---|---|---|---|---|---|
| B1 | muni credit events (EMMA notices) mapped through N-PORT to muni CEF holdings | **0bp new-default weight in all 24 fund-quarters of MQY and MHD** (2019-10 → 2022-11); Nuveen peers median 0.85bp. **EMMA's terms ban** "data mining, crawling, 'scraping' … or otherwise systematically download or store Content"; the feed costs $45,000/yr [V]. Default-flagged holdings show an unchanged quarterly mark 23.3% of the time vs 0.2% for others | no lawful free feed ✗; weight < 10bp ✗ → **KILL** | 1·0·0 | ssx_risk |
| B2 | disasters and state fiscal shocks for single-state muni funds | 1,161 major disasters 2008–25 (OpenFEMA); **median 17 independent (state, disaster) pairs/yr**; 22 single-state CEFs at Alpaca, 7 shortable; the deployed 13 hold none | ≥ 30 pairs ✗ → **KILL** | 1·0·1 | ssx_risk |
| B3 | muni tax-policy episodes | 9 episodes in 2008–25 (TCJA 2017-11-02 → 12-22 and the 2025 reconciliation law verified against GovInfo) | **D7**; risk calendar only. Kalshi history starts 2021-12, after 7 of the 9 | 1·0·2 | ssx_risk |
| **B4** | taxable downgrades mapped through N-PORT to HY/loan/multi CEFs | median **267bp** of NAV affected per fund-quarter (p90 838bp); severe-only 75bp; rating-panel coverage **50.3%** of credit weight (HYT 92%, JFR 85%, PIMCO 26–51%) | weight ✓; coverage ✓ **on the line** → **census PASS**; the flag binds in ~90% of fund-quarters, so it is not yet selective; live agency feed [U] | 1·3·1 | ssx_risk |
| B6 | late filings and auditor changes at funds | CEFs 2010–25: 126 NT N-CSR, 75 NT N-CEN; the deployed 13: **none**; BDC 8-K 4.01: 26 from 16 BDCs | report line only | 1·0·3 | ssx_risk |
| B7 | the CEF/BDC regulatory compliance calendar | 18f-4 2022-08-19; 2a-5 2022-09-08; T+1 2024-05-28; Names Rule 2026-06-11 / 2026-12-11; Treasury clearing 2026-12-31 / 2027-06-30; N-PORT monthly public 2027-11-17 [V, Federal Register] | risk calendar only | 0·0·3 | ssx_risk |

**Reading.** The stale-mark well is wet in CEFs, but on the evidence it does not
reach the deployed munis through credit events: MQY and MHD carried no new default
weight in 2019–22. Where the mark does lag (23.3% unchanged marks on flagged
bonds), the flagged weight is too small to move the book. **B4 is the one flag
worth an iteration-2 measurement:** the share of the band's turnover decided on
flagged name-days. A flag that binds 90% of the time is a different signal, not a
hygiene rule. The credit catalogue's queued macro-day flag (MA1/2) and bond-holiday
flag (CA9) remain the stronger hygiene candidates.

### 4.3 Family C: listed credit (preferreds, baby bonds, BDC notes)

Today's census [doc: ssx_lcred]:
- **422 listed preferreds** (407 tradable, 45 shortable) and **168 baby bonds**
  (167 tradable, 5 shortable), from 263 issuers, 97.8% mapped to a CIK.
- The 2026-10-15 census read 388 and 159. The classifier changed, and the flags
  moved: BAC.PRK was shortable then and is not now.

| id | idea | measured | gate → verdict | E·S·F |
|---|---|---|---|---|
| **CR15** | PFF must buy ICE-index additions at the month-end close | additions 2020/21/22: **111/127/47** (N-PORT) vs **101/143/45** (CRSP MF holdings), agreeing within 10%, not averaged. Median **2.02 days of pre-event ADV** (IQR 1.29–4.71; n 75); seasoned additions 4.88 days (n 22). PFF, PGX, PSK and PFFD shortable and ETB | ≥ 30/yr ✓; ≥ 1 day ADV ✓ → **PASS** | 3·1·2 = 6 |
| C1 | new $25-par issues: new-issue discount and drift to listing | 30–114 issues/yr by EDGAR (precision 25% on "Notes due" alone, so counted against the 424B's denomination); median 8 days from 424B to first exchange trade. **The grey-market leg is unreachable at Alpaca** (IIPR's 9.25% Series B, priced 2026-10-09, has no Alpaca asset [V]) | access ✗ → **KILL** | 3·1·0 |
| C2 | distress at baby-bond and preferred issuers (8-K 2.04, 1.03) | **0–7 issuer-years a year** (median 3); 7 of them are the March 2020 mortgage-REIT cluster | ≥ 30 ✗ → **KILL** (D7); D4 prior high (distress premium) | 0·1·1 |
| C3 | bank stress tests and capital rules → bank preferred calls | 17 results dates in 2015–25 (one a year since 2020) | **KILL** (D7, as expected) | 0·1·2 |
| C4 | fixed-to-floating preferreds at the float date | 83 named fixed-to-float/reset issues (10 shortable); **~6 float dates a year** (2026–30, central estimate) | ≥ 30 ✗ → **KILL** | 1·1·1 |
| C6 | short preferreds above the call price near the call date (reopens L1) | **at most 9** today (2 established, 7 not) | ≥ 10 ✗ → **KILL**; L1 stays PARK | 0·1·1 |
| C7 | BDC baby bonds lag BDC equity | 29 issues, **1 shortable**, ADV about $92k at par, **9% of sessions with no trade** | **KILL**: `leadlag`'s stale-price trap exactly | 1·0·0 |

**CR15, the event card.**
- **Mechanism.** PFF tracks ICE's PHGY. ICE rebalances on the last calendar day of
  the month, on information to the third business day before the last business
  day. The floor is $100m outstanding and the issuer cap 4.75% [S: ICE rules dated
  2021-12-26, read from a third-party copy; ice.com not read].
- **Who loses.** PFF's holders, who pay for immediacy at a known close.
- **Why it persists.** The tracker must track. A $25-par issue is too thin to be
  worth an arbitrageur's balance sheet.
- **The expression.** Long the added issue at the close; short PFF (ETB). NYSE
  issues map to the official close print.
- **Negative control** (declared now): issues listing that month **below** the
  $100m floor, and existing constituents.
- **Graveyard neighbours.** S3-forced-flow (WATCH: the mechanism is real) and
  S3-wrapper (D4). This is not the stale-mark well: the price is the issue's own
  close.
- **Weak spots:**
  - only 80 of 574 CRSP additions map to an Alpaca symbol today, so the days of
    ADV rest on a selected subsample;
  - the magnitude is [U]: no study was found;
  - 2022 had 47 additions, so the count is regime-dependent;
  - whether ICE publishes additions before the rebalance is unknown. If it does
    not, the event is known only at the close it must trade, and the trade dies
    under `shift(2)`. **That is the first iteration-2 question.**

### 4.4 Family D: mainstream equity events (more capacity, more crowded)

| id | idea | measured | gate → verdict | E·S·F | adversary prior | seat |
|---|---|---|---|---|---|---|
| **D1** | clustered open-market insider buying, all US equities | Clean clusters (≥ 3 directors/officers, 30 days, 90-day cooldown, same-price placements dropped) 8,476 in 2010–22; **3,485 with ADV ≥ $1m** (131–418 a year); CRSP match 86.5%; filed by 22:00 ET counts as that day (17 CFR 232.13(a)(4) [V]), median trade-to-file lag 1 business day | ≥ 250 ✓ → **PASS** | 3·2·2 = 12 | plausible: about 1 in 8 to survive D4 (size, value, short-term reversal; clusters bunch after sell-offs: March 2020 364 vs a monthly median of 47) | ssx_ins |
| **D9** | earnings-date delay: a report later than its usual date carries bad news | the signal is the **absence** of an 8-K 2.02 by the expected date + 5 weekdays, so it is point-in-time. 8-K 2.02 matches Compustat `rdq` on the same day for 82.9% of 117,416 10-Qs (91.8% within a day). **Mean 368 liquid late events a year** (2010: 207) | ≥ 250/yr ✓ in 12 of 13 years → **PASS** | 3·1·2 = 6 | plausible: 1 in 8. The adversary marked it infeasible (a paid calendar); this census shows a free point-in-time route, and IBES `anndats` on R2 is a cross-check | ssx_fil |
| D6 | 8-K red flags: 4.01 auditor change, 4.02 non-reliance, unplanned 5.02 | full census of 8-K items: 4.01 **1,467**, 4.02 **621** liquid events 2010–22; auditor resignations 23% of 4.01 (≈ 342 liquid); unplanned CEO/CFO ≈ 5% of 5.02; borrow 54% / 59% / 77% | ≥ 250 ✓; ≥ ½ shortable ✓ (4.01 CI straddles 50%) → **PASS, marginal** | 6 | fragile: 64% of 4.02 filed 16:00–20:00, so the −1.10% day-1 move is before our fill; about −0.9% left after day 1, before borrow | ssx_fil |
| D8 | S&P 400/600 changes: announcement → effective | ≈ 117 additions in 2024 (estimate; about 36/yr if counted by announcement date); median 3 sessions announcement → effective; our t+1 order precedes the index funds' trade in 12 of 12 sampled; implied passive demand 15.1 / 9.7 days of ADV (400 / 600; inputs [S]) | **marginal PASS** on the wording; fails by announcement date | 6 | **likely waste**: IHS Markit 2020 finds the abnormal return all on day 1 (+8.8% S&P 600, +6.1% S&P 400 adds) with no significant trend after [V vendor]; Gowri Shankar–Miller 2006 find a full reversal within 60 days. **Reported, not reconciled** | ssx_fil, ssx_adv |
| D5 | IPO quiet-period expiry (analyst initiations) | 123/yr with ADV ≥ $1m at day 25 (CRSP rule), 91 on the EDGAR-confirmed bound; FINRA 2241: 10 days, emerging-growth companies exempt [V]; the 2004 follow-up on 2001–02 IPOs finds no abnormal return [V] | on the line → **PARK** | 2·1·1 | fragile | ssx_ins |
| K5 | IPO lock-up expiry (corp catalogue gate G-K5, run) | **15 of 36** IPOs near day 180 shortable (41.7%); all 2025 IPOs 66 of 193 | < ½ ✗ → **KILL**. A way back: deals ≥ $100m are 11 of 16 shortable near day 180 (a new gate definition: ruling) | 3·2·0 | — | ssx_ins |
| D4 | late-filing notices (NT 10-K / NT 10-Q) | 63,125 notices 2008–25; 1,718 liquid events; 72.7% accepted after 16:00 ET; **30.4% of 2025 filers shortable** (survivors with a liquid 2018–22 notice: 70%, survivor-skewed) | borrow ✗ → **KILL** as written | 3 | fragile | ssx_fil |
| D2 | BDC earnings drift with NAV at earnings | XBRL NAV per share in **1.6% of BDC-quarters 2012–22** (84–92% only from 2023, inside the holdout); 17 of 20 releases print NAV as text | XBRL ≥ 80% ✗ → **KILL** (as a structured build; the event engine could read text) | 2 | **waste**: `single-fund-PD` applied to BDCs | ssx_fil |
| D7 | customer–supplier contagion after a customer's Chapter 11 | ~18 bankruptcies/yr with ≥ $1bn assets; 5 of 10 sampled had a supplier naming them (0.8 links each); Compustat `seg_customer` starts 2020-06-30 | ≥ 30 linked ✗ (≈ 14/yr) → **KILL** | 2 | fragile (customer momentum decayed) | ssx_fil |

**D1, the event card** [doc: ssx_ins]:
- **Mechanism.** Insiders buy on private information, and prices barely move when
  they report. Lakonishok–Lee 2001: the information is in purchases, concentrated
  in smaller firms [V]. Alldredge–Blank 2019: clustered purchases are followed by
  abnormal returns above 2% over the next month [V abstract].
- **Who loses.** Sellers after the Form 4 is public: attention-driven holders of
  small caps.
- **The clock.** The filing date of the Form 4 that completes the cluster. A filing
  made by 22:00 ET counts as that day, so the desk decides at t+1 and fills MOC at
  t+2.
- **The expression.** Long at MOC; short IWM or a sector SPDR. IWM, SPY, IJR and
  XLF/XLK/XLV/XLE/XLI/XBI were ETB today; KRE was not.
- **D4.** It must hedge more than beta. The pre-registration declares size, value,
  short-term reversal and liquidity loadings, and the hedge instruments for them.
  A sleeve that cannot name a hedge for its profitability or reversal loading
  should not run (the adversary's rule from the Chen–Zimmermann base rate).
- **Power.** At a 5-session hold, detecting the breakeven edge needs 594 events
  (199 on the robust σ) [doc: ssx_pm]. The census supplies about 268 liquid
  clusters a year, so power is not the constraint; D4 is.
- **Live feasibility.** The SEC's quarterly data sets lag by up to a quarter, so
  live trading needs a daily Form 4 reader. That is fetcher 1 in §7.4.
- **Unresolved source disagreement.** Thomson insider counts on R2 are far from the
  SEC data sets (2007: 414,500 vs 69,767). Thomson's date field is undocumented.
  The SEC data were used.

### 4.5 Family G: generated beyond both catalogues

The generator assessed 8 seeds and 18 ideas of its own. Six survive as cards, and
**none is ready as a standalone alpha sleeve** [doc: ssx_gen].

| id | idea | finding | verdict |
|---|---|---|---|
| G11 | record-date delivery fails, the test of corp-catalogue E3 (muni lenders recall before record dates) | fails ≥ 10k shares at the record date vs baseline, 2019–22: munis 2.73×, taxable-bond CEFs (the control) 2.30×, equity CEFs 2.85×, BDCs 3.88×. **The muni excess over the control is 1.19×: the control nearly ties** | E3 not supported on this route; its remaining test is our own `borrow_status` snapshots (close E3 if the muni pre-record flip rate is ≤ 1.5× taxable). **Calendar fact for any short leg:** fails cluster 2.3–3.9× before record dates |
| G3 | a pooled situations book: discretionary single-name situations under one counter | each situation committed to git before its first fill, traded at a fixed risk unit, never dropped; one EVENTS trial spent at the verdict; ≥ 30 closed situations; scored by pooled P&L t and log score against the market-implied probability | **governance design; needs three rulings** (§11). Kill: < 10 situations registered in 12 months. The adversary's caution: it inherits its parts' risks, costs do not diversify (`pair-reversion`), and choosing which situations to register is a sweep unless the registration rule is fixed first |
| G1 | Reg SHO threshold status / Rule 204 close-outs | rebuilt from SEC fails data plus shares outstanding (the exchange lists' terms bar storage): 30 CEF episodes 2019–22, 0 BDC, none deployed; **close-outs are due by the open** | D7 as alpha; risk use closed for the current book |
| G6 | the muni de minimis cliff | a fair-value input to muni NAVs, not alpha; the one-query gate on R2's MSRB tape is specified, **not run** | iteration 2 (cheap) |
| G10 | crypto trusts converting to ETFs (the CEF mechanism outside the 1940 Act) | 19 Grayscale trusts, 12 converted (4, 5 and 3 in 2024–26); the 3 still on OTC are tradable, not shortable | D7; G3 feeder only; **needs a mandate ruling** |
| G2 | Fannie/Freddie junior preferreds | **all 39 GSE symbols inactive and not tradable at Alpaca** [V]; R2 holds their OTC history from 2011 | IBKR only, as a G3 registration |

**Killed by the generator** (one line each in its file):
- G4, CEF→ETF conversions: covered by J7.
- G5, insurer and pension flows: X2 is already dead.
- G7, agency events in bank and insurer preferreds: nothing listed.
- G8, a non-traded BDC merged into its listed sibling: 10 in 2016–26, D7, folded
  into A4.
- G9, forced selling of fallen-angel preferreds: the ICE indices have a B3 floor,
  not an IG line.
- 18 more, among them:
  - post-tender proration dumps (C1/N2 again);
  - RMD December selling (CORE-b again);
  - XMPT rebalances (folded into B2);
  - STRATS trust certificates (0 of 10 shortable).

---

## 5. The adversary's base rates, and the patterns behind the deaths

The beta-detector seat assumed every row false, and gave a cause of death, the
nearest grave, the D4 test, the negative control and a stale-price check for each
of 38 rows [doc: ssx_adv].

**The five most likely wastes of a trial: C7, D8, D2, C6, G1.** The census
independently killed C7, D2, C6 and G1. D8 passed its census gate only marginally,
and the adversary's evidence says its effect is gone before our fill.
**Runners-up:** D5, G2, A9, J9.

**Odds of surviving D1 and D4, a judgement, not a measurement:**

| rank | row | odds | likely death |
|---:|---|---|---|
| 1 | SPAC bought below trust, held to redemption, no warrants | ~1 in 3 | D5 and Reg T gross cost; redemption plumbing |
| 2 | C1-corp dual-class spread | ~1 in 3 | D2 |
| 3 | NAV tenders | ~1 in 4 | D2: $100 per election, proration, the remainder re-widens |
| 4 | B1-corp spin-off removal close | ~1 in 5 | D7; pre-positioning |
| 5 | merger arb, stock-for-stock, acquirer-hedged, read by hand | ~1 in 5 | the kink. Only 23 of 200 months since 2010 had the market below −4%, so a kink test has little power, and its power must be pre-registered |
| 6 | **D1** clustered insider buying, hedged | ~1 in 8 | D4 |
| 7 | **D9** earnings-date delay | ~1 in 8 | D7 (in the adversary's reading) |
| 8 | E1, the CEF merger pair | ~1 in 10 | D1 at our fill; D3 borrow |
| 9 | K6 non-overnight SEO reversal | ~1 in 10 | D5 |
| 10 | **A1** ATM premium short | ~1 in 12 | D1 incremental to the z-score |

**The patterns, and one test for each, declared before any run:**
- **A published anomaly.** Pre-register the D4 regression and the hedge for each
  loading. 1.0% of 207 published predictors pass the desk's D4 as published.
- **An announcement-day effect** (D6, D8, A5, A9, E1, G1). From EDGAR acceptance
  timestamps (the header, §8.11), measure the share of the effect left after the
  t+1 close.
- **The stale-mark well** (nine rows; C7 is `leadlag` exactly, and D2 is
  `single-fund-PD` on BDCs). Re-run as executable close-to-close on auction
  prints, drop no-trade days, and add a control pair where no mechanism exists.
- **A short put** (merger arb). Test the down-market kink, regress on the Cboe PUT
  index, and state the power.
- **A distress short** (C2, D4, D6). Test the up-market kink and the profitability
  and distress loadings, with borrow measured at IBKR.

**The B flags are not ranked.** As subtract-only rules they cannot fail D4, so
their only failure mode is never binding, or binding all the time (B4).

---

## 6. Consolidated ranking: what to test, in what order

Only rows that passed a gate, plus the board items already ruled on. The columns
come from §4 and §5 and the PM seat's tables [doc: ssx_pm].

| rank | row | gate | odds | archetype (§8.3) | gross per unit idio vol | events / time to 250 independent | counter | the next step |
|---:|---|---|---|---|---|---|---|---|
| 1 | NAV tenders | passed (2026-10-15) | 1 in 4 | (i) long + HYG | — | ~9.5 groups/yr [doc] | EVENTS (slate) | pre-registration (in flight, another session) |
| 2 | E1 CEF/BDC merger pair | ruled | 1 in 10 | (ii) pair | 48.6 (gross-poor) | 7.1/yr munis; 35 yrs to 250 events | EVENTS (slate) | pre-registration (in flight); score as diversification, not as a claim on gross |
| 3 | merger-arb reconstruction | ruled | 1 in 5 (stock deals) | (ii) | — | ~210 deals/yr; 1.2 yrs | EVENTS (slate) | `deal-analyst` design that passes the kink test, with its power pre-registered |
| 4 | SPACs via IBKR | ruled | 1 in 3 | (i) T-bill-like | — | — | EVENTS (slate) | re-run the gate on IBKR's terms (in flight) |
| 5 | **D1 insider clusters** | **passed today** | 1 in 8 | (i) long + IWM/sector | 6.0–9.7 | ~268 liquid/yr; about 1 yr | EVENTS (slate) or a new INSIDER counter (ruling) | daily Form 4 reader; `event-econometrician` design with the D4 hedge set |
| 6 | **CR15 PFF additions** | **passed today** | not rated | (i) long + PFF | — | 45–143/yr | EVENTS (slate) or NPORT (ruling) | is the addition known before the rebalance close? If not, kill under `shift(2)` |
| 7 | **D9 earnings-date delay** | **passed today** | 1 in 8 | (iii) short late reporters + ETF (or long early) | 6.0–9.7 | 368/yr | EVENTS reserve | borrow on late reporters, measured at both brokers; IBES cross-check |
| 8 | C1-corp dual-class spread | **gate not yet run** | 1 in 3 | (ii) | — | continuous, 25 pairs | needs a ruling (no event) | run G-C1 (dispersion vs the cost grid; random-pair control) |
| 9 | B1-corp spin-off removal close | **gate not yet run** | 1 in 5 | (i) | — | 21/yr; 12 yrs (28 independent) | EVENTS reserve | run G-B1 (count S&P day-1 removals) |
| 10 | **A1 fund issuance into a premium** | **passed today**, borrow marginal | 1 in 12 | conditioner on the live book's short side | — | 55–67 issuers/yr | **CEF** (52 → 53) | prove it adds beyond the z-score's premium tail; a book-level test (§4.1) |
| 11 | **A2 CEF/BDC insider buying** | **passed today** | fragile | conditioner on the live book's long side | — | ≥ 86/yr | **CEF** | as A1. Choose **one** of A1 and A2 for the CEF counter |
| 12 | **D6 8-K red flags** | passed, marginal | fragile | (iii) short | — | 4.01 ~113/yr liquid | EVENTS reserve | measure the share of the effect left after the t+1 close from header timestamps |
| — | B4 downgrade flag | census pass | — | (iv) subtract-only | — | — | CEF if adopted | share of band turnover decided on flagged name-days |
| — | D8 S&P 400/600 | marginal; sources disagree | waste | — | — | — | — | do not pre-register the run-up form. A post-effective reversal form would be a new idea with its own gate |

**The one-line rule.** The rows most likely to survive converge by contract within
one asset: tenders, SPAC trust value, dual-class claims. They die, if at all, of
D2, D5 or D7. The behavioural rows (D1, D9) have the breadth, and die of D4 unless
built factor-neutral. **A desk needs both, and the portfolio layer (§8) decides
the weights.**

---

## 7. The data map

### 7.1 R2: what is there, and what is not [doc: ssx_data, `R2_FULL_INVENTORY_2026-10-19.md`]

- **The bucket.** 1,146 parquet tables in 81 schemas, 433.1 GB, about 24.4 bn rows.
- **Snapshot dates.** Every object was last modified 2026-06-26 → 07-03, and
  nothing has been refreshed since.
- **Incomplete chunks.** The mirror's `manifest.json` (412 entries, which is where
  "412 tables" came from) flags 11 chunks incomplete, all in 2026: Compustat `fundq`,
  five IBES tables, four `tr_insiders` tables and Worldscope `fundq`.
- **A stale file.** `coverage.json` is stale and should not be used.

| need | R2 table(s) | coverage | serves |
|---|---|---|---|
| prices, shares outstanding, delistings, distributions | `crsp_a_stock` CIZ (`dsf_v2`, `stkdlysecuritydata`, `stkdelists`, `stkdistributions`, `stkshares`) | to **2025-12-31** | every row; A1 (share growth), spin-offs, D5 |
| IPO dates | `crsp_a_ccm.comphist` | to 2026-01-09 | D5, K5 |
| insiders | `tr_insiders.table1/2/header`, `form144`, `rule10b5` | to 2026-06-26; Form 144 from 2001; 10b5-1 flag from 1997 | D1, A2 (cross-check; counts disagree with the SEC sets) |
| M&A, tenders | `tr_sdc_ma.wrds_ma_details` | 1965 → 2026-07-01 | merger arb, CEF tenders, spin-offs |
| new issues (IPO, quiet period, lock-up fields; $25-par) | `tr_sdc_ni.wrds_ni_details` | → 2026-07-02 ($25-par thins after 2021 [U]) | A1, C1, D5, K5 |
| earnings dates and estimates | `tr_ibes` (166 tables), `comp_na_daily_all.fundq.rdq`, `co_filedate` | IBES → 2026-05-14; Compustat → 2026-06 | D9, D4, D2 |
| fund holdings | `crsp_q_mutualfunds.holdings` (BIZD, PFF, IJH, IJR, …); `tr_13f.s34`; `tr_mutualfunds.s12` | 2001-12 → 2026-03; 13F → 2025-12-31 | A9, CR15, D8 |
| muni trades | `msrb_all` | 2005 → 2025-12-31 | B1, G6 |
| OTC prices | `otc_endofday` | → 2026-06-01 (all 37 GSE symbols from 2011-09) | G2, G10 |
| bankruptcies | `fjc_litigation` (FJC Integrated Database) | filed → 2026-03-31 (incl. chapter 9) | C2, CR6, B1 |
| short interest (under the WRDS licence, not FINRA's terms) | `comp_na_daily_all.sec_shortint` | 2006 → 2026-06-15 | borrow-risk inputs |
| bonds | `trace`, `trace_enhanced`, `trace_standard` | → 2026-06 | B4, CR-family |

**Not in R2:**
- Mergent FISD, OptionMetrics, RavenPack, Capital IQ, TAQ, DealScan, Markit, ISS;
- full Audit Analytics (a 1,491-row sample only);
- BoardEx beyond a trial extract;
- any ratings history after 2017-02;
- any EDGAR filing index;
- Russell membership.

**Two traps:**
- **S&P 400/600 membership** (`idxcst_his`) holds current members only (503/400/602
  rows, no `thru` dates). It is survivorship-biased and cannot count changes.
- **Compustat `seg_customer`** starts 2020-06.

### 7.2 Free sources and their terms [doc: ssx_data §2, ssx_risk]

| source | terms for automated research use | verdict |
|---|---|---|
| SEC EDGAR and the DERA data sets (insider transactions 2006Q1+, financial statements 2009+, N-PORT, N-CEN, fails-to-deliver) | "public information and may be copied or further distributed … without the SEC's permission" [V] | **use** (fair-access rate through `edgar_client`) |
| MSRB EMMA | bans scraping and systematic download or storage (terms dated 2026-01-01); feed $45,000/yr, history $22,500 per 12 months [V] | **walled**; history via R2 MSRB trades |
| Nasdaq / NYSE Reg SHO threshold lists | no storage or commercial use without written consent / personal non-commercial use only [V] | **walled**; rebuild from SEC fails data |
| S&P DJI | pages answer HTTP 403 to automated requests [V] | **walled**; PR Newswire copies of S&P releases were read by hand |
| OpenFEMA | attribution; use "solely for statistical research or as a reporting record" [V] | **ruling needed** for a trading flag [U] |
| FINRA (short interest, Reg SHO volume, TRACE public) | non-commercial, plus clause (m) [S, §12y] | use R2 equivalents where licensed |
| Kalshi | storage and portfolio use forbidden [doc: §12y] | do not collect |
| Fed, Treasury fiscaldata, Federal Register, GovInfo | public domain / open [V] | **use** |
| Chen–Zimmermann | code GPL-2.0, no data licence, citation requested [V] | literature priors only |
| French, AQR | no terms text on the pages | already fetched by repo scripts |

### 7.3 Sources that start after 2023-01-01: these need a forward-only protocol

| source | starts | pre-2023 history? |
|---|---|---|
| Item 408(a) 10b5-1 plan disclosures | fiscal quarters from 2023-04-01 [V] | **none** |
| Form 4 10b5-1 checkbox | forms filed from 2023-04-01 [V] | partial: SEC sets backfilled in 2025; the Thomson flag runs from 2007 (definition [U]) |
| electronic Form 144 on EDGAR | 2023-04-13 [V] | yes, through R2 Thomson Form 144 (2001+) |
| December Russell reconstitution | 2026-12-11 [V] | none (a regime change) |
| T+1 settlement (changes Reg SHO close-out timing) | 2024-05-28 [S] | a different regime before |
| structured 13D/G | 2024-12-18 [S] | text filings only |
| Treasury buyback programme | 2024 [V] | none, the 2000–02 programme aside |

**A source with no pre-2023 history cannot be fit without touching the sealed time
holdout.** Such an idea can only be judged on a forward-only paper protocol:
- fixed rules registered before the first decision;
- broker-confirmed fills only;
- nothing fitted on 2023–26;
- a minimum count stated in events.

That is a team-lead ruling (§11).

### 7.4 Fetchers to build, in priority order [doc: ssx_data §5]

1. **The EDGAR form-event and 8-K-item extractor**, from the nightly
   `submissions.zip`, an allowed host. It serves C2, D6, D4, D9, A3, A16, C1 and
   A1, and the live Form 4 reader for D1 and A2.
2. **SEC fails-to-deliver with a threshold-status rebuild.** It serves G1 and the
   G11 record-date calendar.
3. **R2 staging extracts**, gitignored because the data is licensed: SDC, Thomson
   insiders, OTC GSE prices, CRSP MF holdings diffs, IBES/Compustat dates, CIZ
   distributions and delistings.
4. SEC financial-statement data sets.
5. N-PORT bulk data sets.
6. N-CEN.
7. OpenFEMA, after the ruling.
8. ALFRED vintages. It needs a FRED API key, which is the team lead's credential.
9. Treasury buybacks and auctions.
10. EDGAR full-text search. It needs a reviewed change to `edgar_client.py`'s
    allowed hosts, and a ruling, because `fetch_edgar_events.py` deliberately
    treats it as a user interface.

**Do not build without permission:** the threshold-list scrapers, EMMA, the S&P
DJI pages.

---

## 8. How we add it: the institutional build

### 8.1 The architecture

```
 sources (EDGAR acceptance-time · R2 snapshot · Alpaca · free feeds with clean terms)
    │
    ▼
 event store (results/events/event_engine design; PIT key = header acceptance time; amendments as rows)
    │                                        ▲
    ▼                                        │ ss-census (weekly): screen → census → design → card
 event cards + zero-trial gates  ────────────┘
    │  /prereg (team lead approves; counter moves in the same commit)
    ▼
 daily target-weight panel per sleeve  ──►  evaluate() in scripts/cef/band_frontier.py, shift(2)
    │                                         (the ONE harness; extended visibly, never rebuilt)
    ▼
 portfolio combiner (framework note): admission by return per unit gross · Σ⁻¹·IR · event budgets
    │  · shared hedge overlay (registered) · per-symbol netting · broker assignment
    ▼
 runner consumers: one netted MOC set per book per day; events may only SUBTRACT intraday (event pod §2.3)
    │
    ▼
 measurement: three P&L lines per sleeve · cost clause · calibration (Brier) · nightly risk report
```

### 8.2 One harness, not a second backtester

Every event sleeve is expressed as a **daily target-weight panel**: event legs,
hedge legs, entries and exits. It is scored by the canonical `evaluate()` under
`shift(2)`: decide at t, MOC fill at t+1, earn t+2. `CLAUDE.md` forbids a new
backtester.
- **The headline is the calendar-time portfolio**, because it charges overlap and
  cost honestly. Per-event CARs are a diagnostic only.
- **Standard errors** are clustered by date.
- **The effective number of independent events** is reported beside N, as
  N_eff = N / (1 + (m − 1)ρ_c), and **D7 is judged on N_eff** [doc: ssx_pm §4].
- **Hedge betas** come from a stated window strictly before the event, asserted at
  run time.
- `event-econometrician` writes this design. Whoever runs it did not choose it.

### 8.3 Admission: return per unit of gross [doc: ssx_pm §1]

- **The two regimes.** Today, at the spec's 6% vol target, vol binds, and a small
  sleeve enters if its IR exceeds ρ·IR_c: a bar of 0.14 at ρ 0.145, 0.30 at ρ
  0.317. **At the ≥10% mandate the book sits at the gross cap**, so a sleeve must
  earn at least the CEF book's return per unit of gross: 5.15%/yr gross, 3.47% net
  of 15bp [doc].
- **Per event**, the breakeven edge is μ\* = 5.15% × (gross per long) × hold/252.
  At 2.0 gross per long, that is **20 / 82 / 245bp over 5 / 20 / 60 sessions**
  (74 / 115 / 225bp net of 15bp). Borrow on a short leg adds fee × hold/252: +159bp
  over 20 sessions at 20%/yr.
- **Gross efficiency by archetype**, in units of gross per unit of idiosyncratic
  vol:
  - (i) and (iii), single names with an ETF hedge: **6.0** (small cap), **8.2**
    (mid), **9.7** (large), **12.2** (BDC, survivors);
  - (ii) pairs: **16.4** (taxable CEF), **48.6** (the E1 muni pair);
  - the CEF book: **17.7**.

  **The single-name hedged long is the gross-light archetype.**
- **Subtract-only flags (iv)** cost 2.04bp of CEF alpha per flagged session per
  unit of gross, or more than 32bp if they force an exit and re-entry. Only flags
  that shrink a queued order are cheap.

### 8.4 A shared hedge overlay [doc: ssx_pm §2]

- **When it pays.** Netting all sleeves' factor exposures at book level and hedging
  once saves gross **only when sleeves hedge in opposite directions**. Four sleeves
  that all hedge short save 1–14%; balanced long- and short-biased mixes save
  50–86% (closed form, checked by Monte Carlo).
- **Fit with the order path.** It fits "one netted order per symbol", because the
  overlay is just another input to the combiner.
- **What it needs.** Per-sleeve shadow hedges for attribution, and **its own
  pre-registration**: the framework's §3.1 forbids unregistered hedges.
- **The caveat.** An ETF hedge removes only about 20% of a single stock's 5-session
  variance, and for micro caps a SPY hedge adds variance. The hedge is for factor
  loadings, not for idiosyncratic risk.

### 8.5 The capacity ladder (5%-of-ADV per auction) [doc: ssx_pm §3]

| archetype | stops scaling at | binding leg |
|---|---|---|
| (i) long + ETF hedge | about $10m (about 40% of spin-off and split events still fit at $100m, extrapolated) | the event name |
| (ii) pair | $1–10m | the thinner leg |
| (iii) short + ETF long | about $1m | ADV and borrow |
| (iv) subtract-only flags | never on their own | scales with the host book |

The hedge ETFs do not bind below $100m, except PFF and BKLN ($7.8m and $12m per
session at 5% of 2022 ADV). **For CEFs the closing-cross rule is 88× tighter than
the ADV rule** [doc: `results/cef/EXEC_CAPACITY_OPEN_CROSS_2026-10-13.md`]. The
same closing-cross share for common stocks is not measured.

### 8.6 Two brokers [doc: ssx_pm §5]

- **The rules.** Reg T: 50% initial margin long, 150% short [V CFR]. FINRA 4210
  maintenance [V]. Alpaca's house rules: an end-of-day check and a next-morning
  call [V]. IBKR liquidates in real time [S: its pages returned 403].
- **Never split a pair across brokers.** Each symbol is assigned to one broker.
- **The squeeze limit.** An IBKR short book hedged at Alpaca survives a rally *u*
  only if short value ÷ IBKR equity ≤ 1/(0.30 + 1.30u). That is 1.67 against IWM's
  worst 5-session rally (+22.9%), and 1.09 against a single small cap's p99.9
  (+47.2%).
- **Stress caps per account:**
  - a split single short: G 1.03;
  - a pair held in one account: 1.38–1.52;
  - the CEF book: 1.80.

### 8.7 Counters and the slate [doc: ssx_pm §7, ssx_adv]

- **The slate bar.** √(2 ln N) is 1.893 / 2.039 / 2.146 / 2.229 at N = 6 / 8 / 10
  / 12. **Up to N = 6 the bar is below 1.96, so D1's t binds first.** The D4 alpha
  t of 3.0 binds before either for nearly every row.
- **Recommendation: declare an EVENTS slate of six now, before any of them runs**,
  as XASSET did. The six:
  - E1;
  - NAV tenders;
  - the merger-arb reconstruction;
  - SPAC via IBKR;
  - D1;
  - CR15.

  Reserves (D9, B1-corp, C1-corp) enter only by an amendment recorded before their
  data step.
- **Reconcile with the drafts.** E1 and NAV tenders are being pre-registered today
  in another session. The slate declaration must be reconciled with their drafts,
  so that each is judged at the slate's N, not the running count.
- **New sources** (insider data sets, XBRL, N-PORT for CR15): a source gets its own
  counter only when it supplies the signal's information. Otherwise the trial
  goes on the slate.
- **Desk-wide count.** Print the desk-wide number of tests beside every verdict.

### 8.8 Evidence floor, time to verdict and the live statistic [doc: ssx_pm §4]

- **MDE ≈ 2.8σ/√N.** With small-cap, IWM-hedged, 5-session σ at 642bp (robust
  371), N = 250 detects 114bp (66).
- **The N needed to detect the breakeven itself**, net of 15bp, at 5 sessions:
  small cap 594 (199 robust), large cap 242, BDC 201.
- **Years to 250 independent events:**

  | family | years (independent) |
  |---|---|
  | B1-corp spin-off removal | 11.9 (27.8) |
  | G3 splits | 11.1 (25.8) |
  | special dividends | 1.3 (1.7) |
  | merger arb (all listed) | 1.2 (21) |
  | E1 munis | 35 (69) |
  | macro-day flag | 7.9 |

- **Consequence: no new event family can be graded on mean P&L within twelve
  months.** The live statistics that can be graded in time are:
  - the **cost clause** (implementation shortfall against half the breakeven, from
    20 sessions);
  - **calibration** (Brier; break rate against the posterior);
  - the mean per resolved event, at the N stated **in events** in the
    pre-registration (H11).

### 8.9 Sequence [doc: ssx_pm §6]

1. **(iv) subtract-only flags**, e.g. MA1/2, CA9, B4 if selective. They cannot
   fail D4, and they scale with the book.
2. **(i) hedged longs at Alpaca**: NAV tenders, D1, CR15, SPAC.
3. **(ii) pairs**: E1, dual-class, merger arb. Pairs come after Portfolio Margin is
   researched, because Reg T makes them gross-poor.
4. **(iii) shorts last**: D9, D6. Borrow at IBKR is measured first, and the squeeze
   limits of §8.6 apply.

Gates G0–G7 are in the PM file.

### 8.10 The portfolio overview the team lead asked for (read-only)

The nightly report and dashboard panels per sleeve [doc: ssx_pm §8, extending
`results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md` §5]:
- gross by sleeve and by broker against its cap;
- return per unit of gross, live vs pre-registered;
- open events, with days to their next dated step;
- the factor exposures before and after the overlay;
- resolved events against N_req, with the current MDE;
- the Brier score;
- the cost clause;
- borrow status changes on every short leg;
- the squeeze-limit headroom at IBKR;
- the stale-NAV and macro-day flags that bound today.

**No code path from this report sends an order** (`CLAUDE.md`).

### 8.11 Point-in-time discipline: the acceptance-time correction

The submissions API's `acceptanceDateTime` is not only sometimes late, as
`docs/REFERENCES.md` §12y/§12z recorded. **It is also sometimes early** [doc:
ssx_fil]:
- **250 NT headers:** equal 59, late 58, **early 133**.
- **FSDS 2022q1** (5,991 10-Q/10-Ks): equal 2,184, late 2,092, **early 1,715**.

An early value moves an after-close filing before the close: a 17:16 filing reads
as 13:16. **That is lookahead.** The event engine already keys on the header's
`ACCEPTANCE-DATETIME`, which is correct. Any research code that reads the API's
time must not.
- **The live rule:** `observed_at = max(header acceptance, 06:00 ET on the filing
  date)`.
- **The research rule:** "filing date ≤ t" at the 22:00 decision.

The correction is recorded on the §12j row and in §12ssx.

---

## 9. The agent desk

### 9.1 The seats (`.claude/agents/`, added 2026-10-19)

| seat | owns | typical question |
|---|---|---|
| `event-scout` | ideas as event cards: the forced party, the clock, the count, the zero-trial gate; kills its own ideas against both catalogues and the graveyard | "What else could the event desk trade in preferreds?" |
| `filings-analyst` | EDGAR form and 8-K-item map, acceptance-time PIT, the SEC data sets, scored extraction | "When is an NT 10-K first knowable, and how many a year are liquid?" |
| `deal-analyst` | merger arb, tenders, CEF/BDC mergers, SPACs, spin-offs, index events: terms from the document, timelines, the D4 kink, election mechanics | "Reconstruct merger arb so that what is left passes the kink test" |
| `credit-situations-analyst` | listed preferreds and baby bonds, BDC loan marks, ratings, distress, fund leverage, muni credit reaching NAVs | "What does this preferred's prospectus say about the float date and the call?" |
| `data-librarian` | R2 contents and gaps, free sources, PIT fields, terms of use, fetchers with source notes | "Is there pre-2023 history for this, and may we store it?" |
| `event-econometrician` | power and MDE, overlap and clustering, the `evaluate()` mapping, controls, the D4 specification; designs, never runs | "Can 40 events a year ever detect this effect?" |

**The existing seats keep their jobs:**
- `beta-detector`: the adversary;
- `quant-reviewer`: code and lookahead;
- `execution-trader`: fills, borrow, auctions;
- `portfolio-manager`: sizing and admission;
- `market-structure-analyst`: plumbing;
- `equity-research`: per-fund facts;
- `alpha-finder` and `unique-angle-researcher`: generation for the CEF book.

### 9.2 The workflow `ss-census` (`.claude/workflows/ss-census.js`)

| phase | who | what |
|---|---|---|
| Screen | `event-scout` | graveyard, both catalogues, this note; a dead or duplicate idea stops here |
| Census (parallel) | `filings-analyst`, `data-librarian`, `execution-trader`, `beta-detector`, plus the domain specialist (`deal-analyst` / `credit-situations-analyst` / `equity-research`) | count, data and terms, tradability and borrow, D4 prior and control, primary documents |
| Design | `event-econometrician` | the weight panel, windows, hedge, controls, power table; **KILL ON POWER** if the plausible effect is below the MDE |
| Card | `event-scout` | writes `results/events/cards/<id>.md`; verdict KILL / NEEDS_RULING / PASS_GATE / NOT_ESTABLISHED |

- **It cannot compute a return.** Every prompt carries the zero-trial line.
  Survivors go to `research-idea` (which spends at most one trial, after the team
  lead approves the pre-registration).
- **Run it:**
  - `Workflow({name: "ss-census", args: [{id: "CR15b", idea: "..."}, ...]})` for a
    batch, or with a single idea string;
  - or ask Claude to "run ss-census on these ideas".

### 9.3 The operating rhythm

- **Weekly census.** Batch the week's new ideas, the reserves and the
  iteration-2 questions (§10) through `ss-census`. The cards accumulate in
  `results/events/cards/`, and the next expansion note ranks them.
- **Before any trial:** `/prereg`, the team lead's approval, and the counter moved
  in the same commit.
- **After any trial:** `beta-detector` and `quant-reviewer` independently, as
  `research-idea` already does.
- **Monthly:** `data-librarian` re-runs the R2 inventory (the snapshot may be
  refreshed) and re-reads the terms of every free source in use.
- **Nightly (once sleeves run):** the read-only overview of §8.10.

---

## 10. Roadmap

| wave | work | trials | seats |
|---|---|---|---|
| **2: this week, zero trials** | (1) CR15: is the addition announced before the rebalance close? (2) D1: daily Form 4 reader + the D4 hedge set, designed. (3) D9: borrow on late reporters at both brokers; IBES cross-check. (4) A1 vs A2: a book-level test design showing the increment over the z-score; choose one. (5) B4: share of band turnover on flagged name-days. (6) Run the unrun corp gates G-C1 (dual-class) and G-B1 (spin-off removal). (7) G6: the one-query de minimis gate on R2 MSRB. (8) E3: muni vs taxable `borrow_status` flip rates before record dates, from our own snapshots, once three months exist. (9) Fetcher 1 (§7.4). | 0 | scout, filings, credit, data, econometrician, execution |
| **3: pre-registrations** | the EVENTS slate declared with N; preregs for D1 and CR15 (and the in-flight E1, NAV tenders, merger arb v2, SPAC); the shared hedge overlay's own prereg if adopted | 0 until approved | econometrician, deal, PM |
| **4: trials** | slate members run on `evaluate()`, each attacked by `beta-detector` and `quant-reviewer` | EVENTS +1 each, within N | — |
| **5: paper sleeves** | passing sleeves join the combiner on paper; live statistics are cost and calibration (§8.8) | — | PM, execution |
| **6: real money** | the cost gate (borrow measured, real auction fills); IBKR shorts under the §8.6 limits; Portfolio Margin researched before any pair is sized | — | PM, execution |

---

## 11. Decisions for the team lead

1. **The EVENTS slate.** Declare N = 6 (E1, NAV tenders, merger-arb
   reconstruction, SPAC via IBKR, D1, CR15) now, or a different N.
   *Recommended: 6, with D9, B1-corp and C1-corp as reserves entering only by a
   recorded amendment.*
2. **Counters for new sources.** D1's insider data sets: EVENTS slate, or a new
   INSIDER counter? CR15's holdings source: EVENTS, or NPORT?
   *Recommended: the slate for both. Neither source supplies the signal's
   information beyond the event itself.*
3. **The CEF counter.** One of A1 (issuance as a short-side conditioner) or A2
   (insider buying as a long-side conditioner) as trial 53, or neither yet.
   *Recommended: A1, after a zero-trial check that it adds beyond the z-score's
   premium tail.* **Either one consumes the 27-name holdout if it computes a
   return on a universe name.** The pre-registration must say so.
4. **The forward-only protocol** for sources with no pre-2023 history (Item 408,
   the December Russell reconstitution): allow it, and with what minimum count?
5. **The admission test.** Return per unit of gross as the rule once the vol
   target rises (§8.3). And whether E1 is scored as a diversification sleeve
   rather than a claim on gross.
6. **The IBKR set-up.** Whole pairs held at one broker (recommended); the capital
   split between brokers; which rally sets the squeeze limits.
7. **Terms rulings.** OpenFEMA's "statistical research" clause for a trading flag.
   Any written permission requests (EMMA, Nasdaq or NYSE threshold lists), or
   none. A FRED API key for ALFRED vintages (a credential: yours).
8. **Re-opening K5** on the ≥ $100m deal subset (11 of 16 shortable near day 180):
   a new gate definition, so yours to allow.
9. **G3, the situations book.** Which counter, the minimum N, and the scoring rule.
   Whether crypto-trust conversions (G10) are inside the mandate.
10. **An agent rule slip to note.** The `ssx_ins` seat loaded `config/.env` once,
    with `dotenv_values`, to print three set/not-set booleans. No value was
    printed. Agents are not meant to open that file at all; it did not repeat.
    The seat briefs for iteration 2 say "`--check-keys` only".

---

## 12. Corrections to the record (made visibly in this commit unless noted)

1. **`docs/DATA.md` §3: CRSP's end date.** The legacy SIZ `dsf` ends 2024-12-31.
   The **CIZ files run to 2025-12-31** (French's library: the legacy format was
   "discontinued after the December 2024 data release" [V]). The mirror is one
   snapshot of 1,146 tables, written 2026-06-26 → 07-03. A dated correction note
   was added.
2. **`docs/RESEARCH_STATE.md`: the NPORT row says "monthly holdings history 2019+".**
   Public N-PORT is one month-end snapshot per fiscal quarter, filed within 60
   days. The XML first reaches EDGAR in filings of Oct–Nov 2019 (FR 2019-03958
   [V]; EDGAR index counts [V]). Corrected in place, dated.
3. **`docs/REFERENCES.md` §12j/§12y/§12z: the API acceptance time is also early**
   on many filings (§8.11). A dated correction was appended to the §12j row; the
   detail is in §12ssx.
4. **The corp catalogue's J3** (non-traded REIT/BDC listings, "a few a year [U];
   D7 [U]"). Measured: about 1.3 strict BDC listings a year and 40 coded release
   events, still D7 in the fit window [doc: ssx_fund2]. Recorded here; the dated
   catalogue is left as written.
5. **`results/data/R2_CATALOG.md`** describes 6 tables and is not wrong, only
   partial. The full inventory is
   `results/events/ssx/ssx_data/R2_FULL_INVENTORY_2026-10-19.md`.
6. **The seat briefs' own errors**, caught by the seats:
   - "CEF at 48" was stale; it is 52;
   - "monthly N-PORT since 2019" was wrong;
   - "no Compustat segments in R2" is wrong: `seg_customer` exists from 2020-06.

---

## 13. What is not established

- **No candidate here has been tested.** Every S cell is literature or terms.
  Several key magnitudes rest on abstracts or vendor reports and may not key a
  pre-registration until the full text is read:
  - Bartov–Konchitchki;
  - Johnson–So;
  - Kausar–Taffler–Tan;
  - IHS Markit 2020;
  - the CEF-insider dissertation.
- **CR15:** its magnitude; whether additions are known before the rebalance close;
  the peer indices' dates (PGX, PFFD, PSK); the selected-subsample ADV.
- **D1:** post-publication decay for US insider purchases was not found [U]. Form 4
  acceptance times are not in the data sets. The Thomson-vs-SEC count disagreement
  is unresolved.
- **D9:** the borrow of late reporters, which cannot be measured for 2025 without
  2023+ prices; the classifier error rates.
- **A1:** the credit-vs-equity split of issuers; ATM sale amounts and dates;
  borrow on more than one date.
- **D8:** the two literature sources disagree on what is left after day 1. No
  2010–22 announcement dates were collected.
- **B4:** a lawful live ratings feed; its selectivity.
- **The PM's ρ between event sleeves and the book** is taken from C4, not
  measured. The BDC rows are survivors only. IBKR's liquidation terms are [S].
- **The closing-cross share for common stocks** is unmeasured.
- **Every Alpaca flag here is true on 2026-10-19 only.**

## 14. Files

- **This note.**
- **The seat deliverables and scripts** in the table at the top. Aggregates are in
  `results/events/ssx/<seat>/`. Licensed row-level rows are only in the gitignored
  `results/events/ssx/_cache_*`.
- **The desk:** `.claude/agents/{event-scout, filings-analyst, deal-analyst,
  credit-situations-analyst, data-librarian, event-econometrician}.md` and
  `.claude/workflows/ss-census.js`.
- **Sources:** `docs/REFERENCES.md` §12ssx, a placeholder label to be renumbered at
  merge, because another session pre-assigned §12ad–§12am.
