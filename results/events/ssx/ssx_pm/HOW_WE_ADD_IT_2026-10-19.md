# How we add it: the PM/risk seat, special-situations expansion — 2026-10-19

**Seat:** PM / risk (prefix `ssx_pm`), feeding `results/events/SS_DESK_EXPANSION_2026-10-19.md`.
**Zero trials.** No event-strategy return was computed; EVENTS stays 0, CEF 52, XASSET 4, GAMMA 0.
No spec, book, `docs/`, `ops/`, `quantt/` or `src/` file was touched. Nothing is committed.

**Reproduce:**

```bash
QUANTT_ENV_FILE=/abs/path/config/.env python3 scripts/events/ssx/ssx_pm_risk_inputs.py stage   # CRSP via R2, to 2022-12-30
python3 scripts/events/ssx/ssx_pm_risk_inputs.py report      # -> risk_inputs_2026-10-19.{json,txt}
python3 scripts/events/ssx/ssx_pm_risk_inputs.py etf         # -> etf_inputs_2026-10-19.json
python3 scripts/events/ssx/ssx_pm_arithmetic.py              # -> arithmetic_2026-10-19.{txt,json}
python3 -m pytest scripts/events/ssx/ssx_pm_test_arithmetic.py
```

**What was measured, and on what.** These are risk inputs, not strategy returns. The window is
CRSP `dsf` from 2008-11-03 to **2022-12-30**, pulled 2026-10-19 15:32 UTC. The sample is every
US common stock (share codes 10/11, NYSE/AMEX/Nasdaq) priced ≥ $5 with 63-session ADV ≥ $1m,
admitted at each year-end 2009–21. Each name's residual is then measured in the following year
against a beta estimated on the prior 250 sessions, so the beta is out of sample. The run
covers 28,286 stock-years. A separate run covers today's 50 BDCs: they are **survivors**, 266
stock-years. Both runs exclude CEFs and assert that none of the 46 `cef_universe.csv` permnos is
present, so H9 is untouched. The windows include earnings and other news. So the raw sd is an
**upper** bound on a quiet window and the MAD-based robust sd a **lower** bound; both are
printed, never averaged.

**Labels.** [V] measured here, or fetched today. [doc] copied from a repo note. [S] sourced, not
re-read. [U] uncertain.

---

## 0. The answer

1. **Once σ\* is lifted toward 9–10%, gross is the binding constraint on Reg T, and the
   admission test becomes return per unit of gross, not Sharpe.**
   - A small sleeve raises book return only if its IR exceeds **max(ρ·IR_c, ν·r_g,c/σ₁,e)**.
   - Here r_g,c is the CEF book's 5.15%/yr per unit gross (3.47% net of 15bp) [doc], ν is the
     sleeve's netting factor and σ₁,e its vol per unit gross.
   - Per event, that means an edge of at least **μ\* = r_g,c × (gross per long) × h/252**, plus
     the round trip.
   - At 2.0 gross per long, μ\* is 20bp over a 5-session hold, 82bp over 20 and 245bp over 60.
     Net of 15bp it is 74 / 115 / 225bp.
2. **E1 (the CEF merger pair, approved for an EVENTS trial) is power-easy and gross-poor.** Its
   documented mean of 126bp per deal over 168 sessions [doc] is **0.95%/yr per unit gross**
   (median 1.25%). That is a quarter to a fifth of the CEF book's 5.15%. It adds return only
   while vol, not gross, binds (today, at the spec's 6%), or under Portfolio Margin.
3. **A hedged single-name long (archetype i) is the gross-light archetype.** It takes 6.0 (small
   cap) to 9.7 (large cap) units of gross per unit of idiosyncratic vol. The CEF book takes 17.7
   and the E1 pair 48.6. The per-position IR bar is 0.31–0.50 gross (0.21–0.34 net of 15bp) [V].
4. **A shared hedge overlay saves gross only across sleeves whose hedges point opposite ways.**
   - Four sleeves that all hedge short save 1–14%.
   - A balanced mix of long-biased and short-biased sleeves saves 50–86%.
   - It fits "one netted order per symbol" (it is one more input to the combiner). It needs
     per-sleeve shadow hedges for attribution and its own pre-registration, because framework
     §3.1 says "no hedge is added".
5. **Where each archetype stops scaling, on the catalogue's ADV rule** (the MOC cross is
   smaller: §3):
   - (i) $10m, with 40% or so of spin-off and split events still fitting at $100m;
   - (ii) $1–10m, on the thinner leg;
   - (iii) about $1m, on ADV and borrow;
   - (iv) never itself; it scales with the host book, whose closing cross binds at $100k [doc].
6. **Power, not cost, decides most families at zero trials.**
   - To detect the breakeven edge itself takes N ≈ 200–600 events at a 5-session hold, and up
     to about 970 at 20 sessions (raw sd).
   - Most families need more than 10 years of events to reach D7's 250 independent trades.
   - So each sleeve's live H11 statistic must be cost and calibration, which converge in weeks.
     The mean P&L per event cannot be graded inside twelve months.
7. **Two brokers: never split a pair across them.**
   - Each account carries its own stress cap, computed with no credit for the other account.
   - An IBKR short book whose hedge sits at Alpaca survives a uniform rally *u* only if short
     value ÷ IBKR equity ≤ **1/(0.30 + 1.30u)**.
   - That is 1.67× against IWM's worst 5-session rally in the window (+22.9%), and 1.09× against
     a single small-cap name's p99.9 (+47.2%).
8. **Sequence: (iv) → (i) → (ii) → (iii).** The order is survivability first, then least
   dependence on the input we do not know: borrow.

---

## 1. Archetypes and gross efficiency

**The derivation** (`entry_bar`). Two budgets bind: vol σ\* and gross G = 1.80. Add δ of a
sleeve's vol budget and cut the CEF budget by D:

- the vol constraint needs D ≤ −ρδ;
- the gross constraint needs D ≤ −δ·ν·σ₁,c/σ₁,e;
- so the return changes by δ·[IR_e − max(ρ·IR_c, ν·r_g,c/σ₁,e)].

That gives two tests:

- **(A) gross:** r_g,e/ν ≥ r_g,c. This does not depend on breadth. A sleeve of K independent
  positions has IR × √K and σ₁ ÷ √K, so its return per unit gross is its average position's.
- **(B) vol:** IR_e ≥ ρ·IR_c. It does grow with breadth.

**Today** (6% target, mean held gross 1.21 against the 1.80 cap [doc]) only (B) binds: the bar
is 0, 0.14 or 0.30 gross at ρ = 0, 0.145 or 0.317 (C4's correlation with the book, overall and
in stress [doc]). **At the ≥10%/yr mandate** the book sits at the cap and (A) binds.

| archetype (median position) | idio σ_e, annualised [V] (p25–p75) | gross per long | gross per unit idio vol | σ₁, one position | σ₁ at K = 16 | bar (A), gross | bar (A), net 15bp |
|---|---:|---:|---:|---:|---:|---:|---:|
| (i)/(iii) small cap, IWM hedge | 0.335 (0.24–0.47) | 2.01 | 6.0 | 0.167 | 0.042 | 0.31 | 0.21 |
| (i)/(iii) mid cap, SPY | 0.265 (0.20–0.38) | 2.18 | 8.2 | 0.121 | 0.030 | 0.42 | 0.29 |
| (i)/(iii) large cap, SPY | 0.212 (0.16–0.28) | 2.05 | 9.7 | 0.103 | 0.026 | 0.50 | 0.34 |
| (i)/(iii) BDC, HYG [survivors] | 0.195 (0.14–0.25) | 2.38 | 12.2 | 0.082 | 0.020 | 0.63 | 0.42 |
| (ii) E1 muni pair [doc: 336bp over 168 sessions] | 0.041 | 2.00 | 48.6 | 0.021 | 0.005 | 2.50 | 1.69 |
| (ii) taxable CEF pair [doc] | 0.122 | 2.00 | 16.4 | 0.061 | 0.015 | 0.84 | 0.57 |
| CEF book [doc] | — | — | 17.7 | 0.0565 | — | — | — |

- **Second method.** Annualising daily residuals instead of 5-session ones gives medians of
  0.345, 0.271, 0.216 and 0.200 for the four single-name rows. They agree.
- **"Gross per long" is 1 + β.** The median betas are IWM 1.01, SPY 1.18, SPY 1.05 and HYG 1.38.
- **The hedge removes little variance.** Pooled out of sample it takes 19% of a small cap's
  5-session variance (IWM), 22% of a mid cap's and 20% of a large cap's (SPY). For micro caps
  the SPY hedge *adds* variance (−12%).
- **The lesson matches E1's.** An ETF hedges the factor, not the name.

**Breakeven edge per event**, μ\*, in bp of the long leg over the hold, at 2.0 gross per long
[V arithmetic]:

| hold (sessions) | 1 | 5 | 20 | 60 | 168 |
|---|---:|---:|---:|---:|---:|
| gross | 4 | 20 | 82 | 245 | 687 |
| net @5bp | 23 | 34 | 75 | 185 | 483 |
| net @15bp | 63 | 74 | 115 | 225 | 523 |
| net @30bp | 123 | 134 | 175 | 285 | 583 |

The rows read in two ways:

- **Short holds are cost-bound.** A 5-session event pays 60bp of round trip on four legs at
  15bp, three times its gross hurdle.
- **Long holds are gross-bound.**

**The arithmetic flips sign across the cost grid for any edge between the gross row and the
30bp row.**

**(iii) short event + ETF long.** Everything in (i) holds, with borrow added:

| fee, %/yr | added at 5 sessions | at 20 | at 60 | IR drag on a median small cap |
|---:|---:|---:|---:|---:|
| 0.5 | +1bp | +4bp | +12bp | 0.01 |
| 5 | +10bp | +40bp | +119bp | 0.15 |
| 20 | +40bp | +159bp | +476bp | 0.60 |

The CEF book's own gate failed on exactly this input (19.9%/yr paid against a 14.6% breakeven
[doc: REAL_MONEY_COSTS]).

**(iv) subtract-only flags** use no gross. The cost of a flag is the CEF alpha it forgoes:
**2.04bp per flagged session per unit of gross** (1.38bp net). A flag that only shrinks or
cancels a queued order costs nothing to trade. A flag that forces an exit and a re-entry pays 2c
per unit of gross, so it must avoid more than **32bp** of loss per flagged session at 15bp.
**Only "do not add, shrink the queued order" flags are cheap.**

**Opportunity, not gross, binds the short-hold families** (§4c table):

- At 5% of NAV per event, spin-offs, splits and specials hold 1.5–5 positions at a time and use
  only 0.15–0.54× of gross.
- Merger arbitrage at 5% per deal would want **10× NAV**, so it competes with the CEF book for
  gross on (A).

**What I am giving up.** Ranking on (A) under-weights tight pairs that diversify. That is
correct on Reg T and wrong under Portfolio Margin, which would recognise their offsets.

## 2. A shared hedge overlay

**The model** (`overlay_ratio`). Sleeve *i*'s demand in one factor ETF is N(±m, s²), with
pairwise correlation ρ. Netting at book level hedges the sum once. The table gives
E|net hedge| ÷ Σ E|per-sleeve hedge|; **saving = 1 − ratio** [V, Monte Carlo agrees to 1%]:

| sleeves | m/s | ρ = 0 | ρ = 0.2 | ρ = 0.5 |
|---|---:|---:|---:|---:|
| 4, no fixed sign | 0 | 0.50 | 0.63 | 0.79 |
| 4, all long-biased (hedge short) | 1 | 0.86 | 0.88 | 0.92 |
| 4, all long-biased | 2 | 0.99 | 0.99 | 0.99 |
| 2 long-biased + 2 short-biased | 2 | 0.20 | 0.25 | 0.31 |
| 6 long-biased + 2 short-biased | 2 | 0.50 | 0.50 | 0.53 |
| 6 long-biased + 6 short-biased | 2 | 0.11 | 0.20 | 0.29 |

**What it is worth.** At a 50% saving a small-cap (i) position goes from 2.01 to 1.50 gross
per long, and σ₁ from 0.167 to 0.223. The 15bp round trip falls from 60bp to 45bp, and the
20-session μ\* from 116bp to 87bp. The saving is per factor, netted separately in each ETF
(market, size, sector, HY, term). It also nets against the CEF book's own rates β of 0.10 [doc],
**if** the team lead allows a hedge there.

**It fits the order path.**

- The overlay is one more input to the combiner (framework §2.10), so each symbol still gets one
  netted MOC order and no wash trade can arise inside the account.
- Two conditions keep it that way: no alpha sleeve may trade an overlay ETF as a signal name, and
  each overlay symbol is assigned to one broker (§5).

**Attribution.**

- Each sleeve computes a **shadow hedge**: its own factor betas × positions, priced at the
  closing print and never sent. The sleeve's line is its positions plus its shadow hedge.
- Each sleeve's D4 test runs on that line.
- The overlay's own line is the actual hedge less the sum of the shadow hedges. That covers
  rounding, whole-share residue and timing, plus the netting saving in cost, booked like the
  crossing saving (framework §4.3).
- A residual above its measured noise fails verify.

## 3. The capacity ladder

**The rule** is the corp catalogue §1's: 5% of book per name, at most 5% of one session's ADV.
A family is usable at book size B when its ADV ≥ B. Each cell is the share of 2018–22 events
that fit [doc: `ss_catalogue/crsp_pre_event_adv.csv`]. The $100m column is a lognormal
extrapolation from the median and p25 [V]; its worst miss on the three measured columns is 1.5–5
points (18 for the dual-class pairs).

| archetype | representative family | $0.1m | $1m | $10m | $100m (extrap.) | stops on |
|---|---|---:|---:|---:|---:|---|
| (i) | spin-off parent | 0.97 | 0.92 | 0.78 | 0.41 | the event name's ADV, from about $100m |
| (i) | split ≥ 2:1 | 0.96 | 0.83 | 0.70 | 0.43 | as above |
| (i) | special dividend, common | 0.92 | 0.74 | 0.44 | 0.15 | as above, from about $10m |
| (i) | all common stocks priced ≥ $5 [V] | 0.92 | 0.78 | 0.48 | 0.14 (measured) | — |
| (ii) | dual-class, thinner line | 0.61 | 0.46 | 0.22 | 0.01 | the thinner leg, about $1m |
| (ii) | stock-for-stock merger, both legs [doc: A7] | 23 of 64 deals | 20 | 17 | — | the number of live, readable deals |
| (ii) | E1 muni target, median ADV $145k [doc] | about 1 | — | — | — | the target; stops under $1m |
| (iii) | reverse split (and only 54 of 432 shortable [doc]) | 0.82 | 0.33 | 0.10 | 0.00 | borrow and ADV, about $1m |
| (iii) | CEF rights, short the CEF | 0.98 | 0.72 | 0.07 | 0.00 | about $1–5m |
| (iv) | the host CEF book | the closing cross binds at $0.1m [doc] | | | | the host |

**The hedge ETFs do not bind below $100m, except PFF and BKLN.** At 5% of 2022 ADV [V] one
session absorbs:

| ETF | SPY | IWM | HYG | IEF | BKLN | PFF |
|---|---:|---:|---:|---:|---:|---:|
| notional per session | $1.94bn | $282m | $158m | $41m | $12m | $7.8m |

**The MOC caveat.** An MOC book trades in the closing cross, not in the day's volume. For CEFs
the cross is 0.57% of the day [doc]. At P_max = 10% of the cross a position is then 0.057% of
ADV, **88× tighter than the 5%-of-ADV rule**. The closing-cross share for common stocks is
**unmeasured** here [U]. The zero-trial next step is the EXEC_CAPACITY fetcher run on the
2016–22 auction prints.

## 4. The evidence floor and time to verdict

**Template, per family, before any trial:**

1. σ_h, the residual sd over the hold (below);
2. μ\*, the breakeven edge (§1);
3. the effective number of events, N_eff = N/(1 + (m − 1)ρ_c), with clusters of size m;
4. the decision: **kill on power if N_eff available in the fit window < 7.85·(σ_h/μ\*)²**, the N
   needed to detect the breakeven itself. This is the X5 precedent.

**MDE = 2.80·σ/√N**, in bp:

| σ source | σ (bp) | N = 50 | 100 | 250 | 500 |
|---|---:|---:|---:|---:|---:|
| small cap, IWM-hedged, 3d, raw / robust [V] | 497 / 280 | 197 / 111 | 139 / 78 | 88 / 50 | 62 / 35 |
| small cap, 5d, raw / robust [V] | 642 / 371 | 254 / 147 | 180 / 104 | 114 / 66 | 80 / 47 |
| small cap, 20d, raw / robust [V] | 1,281 / 824 | 507 / 327 | 359 / 231 | 227 / 146 | 160 / 103 |
| mid cap, SPY-hedged, 5d / 20d, raw [V] | 504 / 965 | 200 / 382 | 141 / 270 | 89 / 171 | 63 / 121 |
| large cap, SPY-hedged, 1d / 5d, raw [V] | 185 / 410 | 73 / 162 | 52 / 115 | 33 / 73 | 23 / 51 |
| BDC, HYG-hedged, 5d / 20d, raw [V, survivors] | 373 / 605 | 148 / 240 | 104 / 169 | 66 / 107 | 47 / 76 |
| E1 muni pair, 168d [doc] | 336 | 133 | 94 | 60 | 42 |
| taxable CEF pair, 95d [doc] | 750 | 297 | 210 | 133 | 94 |
| muni CEF target, MUB-hedged, 168d [doc] | 789 | 313 | 221 | 140 | 99 |

**The N needed to detect μ\* itself** (net of 15bp, 2.0 gross per long), raw (robust):

| | 1d | 5d | 20d | 60d |
|---|---:|---:|---:|---:|
| small cap | 166 (48) | 594 (199) | 972 (403) | 776 (383) |
| mid cap | 106 (34) | 366 (140) | 552 (277) | 439 (262) |
| large cap | 68 (22) | 242 (92) | 344 (180) | 257 (166) |
| BDC [survivors] | 75 (19) | 201 (70) | 217 (116) | 173 (87) |

E1 needs only 3.2 deals to detect its μ\* (523bp), but its documented mean is 126bp.

**For a stated effect:**

| effect | N |
|---|---:|
| lock-up, −1.5% over 3 days [S] | 86 (robust 27) |
| SEO recovery, 2.5% [V abstract] | 32 |
| spin-off, >2% over 30 days [S] | 183 |
| E1 at its mean | 56 |

**Time to D7's 250 independent trades**, from the documented event rates:

| family | events/yr (independent proxy) | years to 250, events (independent) | live positions at once |
|---|---:|---:|---:|
| B1 spin-off removal | 21.0 (9.0 months) | 11.9 (27.8) | 1.7 |
| G3 split ≥ 2:1 | 22.6 (9.7) | 11.1 (25.8) | 5.4 |
| E1c special dividend, common | 191.9 (144.6 issuers) | 1.3 (1.7) | 1.5 |
| D1 CEF rights | 6.7 (4.7) | 37 (53) | 0.4 |
| merger arb, all listed | 210 (12 months) | 1.2 (21) | 100 |
| E1 CEF merger, muni | 7.1 (3.6 groups) | 35 (69) | 4.7 |
| macro-day flag | 31.5 | 7.9 | 0.1 |

The holds behind the last column are the catalogue's, taken at a stated point (B1 20, G3 60,
merger arb 120 [U]).

**Reading.** No new event family can be graded on mean P&L inside the twelve-month horizon. The
live statistics that can be graded in time are:

- the cost clause: implementation shortfall against half the breakeven, from 20 sessions;
- calibration: the Brier score, and break rate against the posterior;
- the mean per resolved event, at the N above, **stated in events in the pre-registration**.

## 5. Two brokers (Alpaca main, IBKR for shorts Alpaca will not lend)

**The rules that apply.**

| rule | long | short | source |
|---|---|---|---|
| Reg T initial | 50% | 150% | [V] 12 CFR 220.12(a), (c) |
| FINRA maintenance | 25% | ≥ $5: max($5/sh, 30%); < $5: max($2.50/sh, 100%) | [V] Rule 4210(c)(1)–(3) |
| Alpaca house maintenance, end-of-day values | 30% above $6; 50% at $2.50–6; 100% below $2.50 | as FINRA | [V] docs, updated 2026-09-17 |

- **Alpaca:** "margin call the following morning"; it "may sell any securities in your account,
  without prior notice" [V].
- **IBKR:** "does not make margin calls. Real-time liquidations occur when your account has a
  margin deficiency" [S: IBKR campus glossary, search summary; the pages return 403 to a fetch].
- **No cross-margin, no cross-broker undo** [doc: MERGER_ARB B8].

**What breaks.**

1. **A squeeze at IBKR while the hedge sits at Alpaca.** IBKR liquidates the short in real time
   at the high. The offsetting gain is at Alpaca and cannot be moved in time (the transfer lag is
   [U]). Alpaca's long is then naked until its next close. MOC has no undo.
2. **The weekly IBKR re-authentication lapses** [doc]. The IBKR legs freeze while the Alpaca legs
   trade, so the pairs drift.
3. **IBKR's resubmit-on-reconnect default** can double an order [doc B8].
4. **Opposite-side trades in one symbol at two brokers in one auction**, for example an overlay
   ETF [doc B8].

**Limits I would set** (each derived; the stress move *u* is re-measured at each review):

| limit | rule | value on today's inputs [V] |
|---|---|---|
| L1 | **No pair split across brokers.** Both legs at IBKR, with IBKR's own hedge ETFs in symbols disjoint from Alpaca's (one symbol, one broker) | — |
| L2 | Each account's stress cap by the frozen rule's form 1/(m + w5), with **no credit for the other account** | split single small-cap short: w5 0.472, G 1.03. Split diversified short basket (IWM's worst 5-session rally): 1.37. Pair held in one account (residual p99.9 ÷ 2): small cap 1.38, mid cap 1.52. CEF book: 1.80 |
| L3 | IBKR short value ÷ IBKR equity ≤ 1/(0.30 + 1.30u), with *u* the short basket's 5-session p99.9 or its worst rally | IWM p99.9 +14.7%: 2.04 (Reg T's 2.0 binds first). IWM worst +22.9% (2008-11-28): **1.67**. Single small cap: 1.09 |
| L4 | Largest single short ≤ (1 − 0.30k)/(1.30u) of equity | at k = 1.5: mid cap 1.22, small cap 0.90, micro cap 0.59 |
| L5 | Each account self-sufficient: excess liquidity ≥ its own stress loss; no plan relies on a transfer | — |
| L6 | HALVE/KILL on the **sum** of broker-confirmed equities; a cushion alarm per account. IBKR reduces first | — |
| L7 | IBKR positions only where the legs can sit **seven days unattended** (holds of weeks or more); no new IBKR position if re-authentication is due within a session | — |
| L8 | Each broker is the fact for its own positions; an orphaned leg is flattened at the next close | — |

**What it costs.** The IBKR book is gross-poor (G 1.0–1.5) and pays 0% on short proceeds below
USD 100k [doc]. It is worth running only for edges that clear (A) at G ≈ 1.4.

## 6. Real-money sequencing

| order | archetype | why | what it needs first |
|---|---|---|---|
| 1 | **(iv) subtract-only flags** on the CEF book | no gross, no borrow, no new names; it reduces risk; its cost is measurable at once | the team lead's ruling on events-only-subtract (pod §2.3); a CEF trial if it changes the policy |
| 2 | **(i) long event + ETF hedge, Alpaca only** | the long leg needs no borrow; the hedges are easy to borrow; gross-light, so it eases the binding constraint | D4 including the down-market β where the payoff is put-like (merger arbitrage) |
| 3 | **(ii) pairs inside one broker** | gross-hungry on Reg T | Portfolio Margin, or admission only while vol binds |
| 4 | **(iii) short event + ETF long** | borrow decided the CEF gate; squeeze, recall and negative skew; needs IBKR | borrow measured at a live account; L1–L8 |

**Gates for every sleeve.**

- **G0:** HALVE/KILL armed, phase B.
- **G1:** the trial passed at the slate bar.
- **G2:** the holdout opened once.
- **G3:** a real-money cost gate, made of four parts:
  - borrow from live locate quotes, or from the IBKR file logged daily for ≥ 63 sessions;
  - participation in the sleeve's own auction ≤ P_max;
  - net > 0 at 15bp;
  - net > 0 at a 2021–22-like fee.
- **G4:** (A) or (B) cleared, on net.
- **G5:** a pre-registered H11 statistic, stated in events, plus the cost and calibration clauses.
- **G6:** a paper evidence floor first, kept out of the record.
- **G7:** the combiner's no-op proof.

## 7. Counters across many sleeves

| N | 4 | 6 | 7 | 8 | 10 | 12 | 52 |
|---|---:|---:|---:|---:|---:|---:|---:|
| √(2 ln N) | 1.665 | 1.893 | 1.973 | 2.039 | 2.146 | 2.229 | 2.811 |
| one-sided Bonferroni z(1 − 0.05/N), for context | 2.241 | 2.394 | 2.450 | 2.498 | 2.576 | 2.638 | 3.102 |

**Up to N = 6 the slate bar sits below 1.96, so D1's 1.96 binds first.**

Recommendations:

1. **Declare an EVENTS slate now**, as XASSET did: N fixed up front for a stated period.
   - It includes the approved E1 trial and the NAV-tender draft, plus every candidate that clears
     its zero-trial gate.
   - The counter moves at each test's Stage 0b.
   - A withdrawal before any data step is free (X5).
   - Kill on power with §4 before declaring.
2. **Give a new source its own counter only when it supplies the signal's information.**
   Insider filings, 17g-7 ratings and XBRL would each get one; N-PORT already has NPORT at 1.
   Event dates used only for timing stay on EVENTS. A test that conditions on a new source goes
   on that source's counter.
3. **Against counter-shopping,** print the desk-wide number of tests in the period beside every
   verdict. The allocator's shrinkage toward the cross-sleeve mean (framework §2.3) is the second
   line. Whether to gate on the desk-wide N is the team lead's call; I recommend reporting it,
   not gating on it.

## 8. The portfolio overview (read-only; extends framework §5)

**Panels.**

1. **Gross ledger:** the sum of sleeve gross and each account's netted gross against its own
   G_stress; the netting factor ν; which constraint binds, with its shadow price.
2. **Return per unit gross per sleeve:** trailing, on the three P&L lines, against r_g,c.
3. **Hedge overlay:** each sleeve's shadow hedge, the actual net hedge per ETF, the saving, the
   overlay residual, and the factor betas per sleeve and for the book against ±0.10, with t.
4. **Brokers:** per account, the cushion (excess liquidity ÷ maintenance), k against k_max, the
   largest short against x_max, days to IBKR re-authentication, and a check that no symbol is
   assigned to both brokers.
5. **Borrow:** per short, the broker, fee, ETB/HTB status, shares available and recall notices;
   the fee against the sleeve's breakeven.
6. **Event calendar:** resolutions due in the next 5 and 20 sessions; jump exposure Σx·ℓ by date
   and by cluster, against D_room.
7. **Evidence:** per sleeve, resolved events against N_req, the current MDE, Brier against the
   base rate, implementation shortfall against the breakeven, and distance to the H11 horizon.
8. **Capacity:** each order's share of its cross; days to exit at P_max.
9. **Counters:** slate N, tests used, the bar.

**Nightly report rows** (ratios only, written on the VM):

- drawdown against HALVE and KILL;
- ex-ante vol, σ\* and which constraint binds;
- per account, gross ÷ NLV against G_stress, k and the cushion;
- per sleeve: budget used, gross, r_g, the P&L lines in bp of NAV, H11 progress;
- factor betas;
- top-component and group shares;
- cluster exposure against its cap;
- the overlay residual and the attribution residual;
- stress rows: the 2008, 2020 and 2022 replays; every event breaks; every short is recalled; the
  IBKR shorts at *u* = IWM's worst rally; one name at its p99.9;
- borrow rows; capacity rows; data health; MISSED and FAIL.

## 9. Decisions only the team lead can make

1. **Adopt (A), return per unit gross, as the admission test once σ\* rises,** and (B) while the
   6% target binds.
2. **The overlay:** authorise its pre-registration, or keep per-sleeve hedges. Framework §3.1
   forbids an unregistered hedge.
3. **IBKR:** self-contained pairs (L1, recommended) against split legs; the capital split between
   accounts; which *u* sets L3 and L4.
4. **The EVENTS slate:** its N and its period; whether the desk-wide N is reported or gated on.
5. **The sequence (iv) → (i) → (ii) → (iii),** and whether flags may act on the live book.
6. **E1:** a paper and diversification sleeve, not a claimant on gross (§0.2)?
7. **The two numbers still owed from the framework:** p\* and P_max.
8. **Portfolio Margin's priority.** It is the only lever that makes (ii) gross-efficient.

**What would change my mind:** a measured stock closing-cross share near the ADV rule; sleeves
whose 21-session correlation with the book is ≥ 0.3 (then (B) binds even at the cap); Portfolio
Margin. **Downside if wrong:** if gross never binds (σ\* stays 6%), the (A) test under-admits
pairs that diversify, at a cost of at most (B)'s Sharpe gain. If gross binds and (A) is ignored,
every gross-poor sleeve displaces CEF gross that earns 4–5× more.

## 10. Not established

- **The closing-cross share of common stocks.** So the §3 capacity figures are an ADV upper
  bound.
- **The residual sd includes earnings,** so raw and robust bound it from either side.
- **The BDCs are survivors.**
- **No sector-ETF hedge was measured.**
- **The correlations between event sleeves and the book are not measured.** ρ is taken from C4.
- **IBKR's liquidation terms are [S],** and the transfer lag between brokers is [U].
- **The hedge-ETF ADV is 2022's.** 2023+ is sealed for this seat.

**Files:** `scripts/events/ssx/ssx_pm_risk_inputs.py`, `scripts/events/ssx/ssx_pm_arithmetic.py`,
`scripts/events/ssx/ssx_pm_test_arithmetic.py`; outputs in `results/events/ssx/ssx_pm/` (the CRSP
cache `_cache_crsp/` is gitignored). Sources: Alpaca margin docs; FINRA 4210; 12 CFR 220.12; IBKR
campus glossary (search) — all to be added to `docs/REFERENCES.md` by whoever merges (this seat may
not edit `docs/`).
