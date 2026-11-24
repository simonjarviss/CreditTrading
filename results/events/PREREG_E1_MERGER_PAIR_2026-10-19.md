# Pre-registration — E1: the NAV-for-NAV CEF merger pair, acquirer shorted at Alpaca or IBKR

**Date** 2026-10-19 · **Counter** EVENTS, one trial; its number is set by the
order in which the team lead approves the EVENTS drafts · **Pass bar**
`scripts/cef/validate.py::_dsr` > 0.95 at the EVENTS N of decision 1 (default
N = 6) · **Plan** `results/cef/RESEARCH_PLAN_2026-10-09.md` §3 row 2; gates G1a
(failed at Alpaca), G1b (not measured), G1c (passed), the ETF-hedge gate
(failed) · **Author** research agent, branch `research-e1-prereg`

> **APPROVED 2026-10-19 by the team lead: EVENTS trial 1** (approved before the
> NAV-tender draft, which is trial 2). The counter moves 0 → 2 in this commit.
> Decisions 1–4 and 6–10 are approved on their defaults (§15). **Decision 5 is
> ruled otherwise, by amendment 1 below.**
>
> **Amendment 1 (team lead, 2026-10-19), before any E1 return: borrow fees are
> ignored; the trial is judged on P&L.** The ruling, verbatim: "ignore fees, just
> look at PnL". It was given after the team lead was shown that IBKR borrow over the
> hold costs at least the +167bp effect in 6 of 7 muni merger windows
> (`results/events/MERGER_ARB_V2_2026-10-19.md`, row iii-a), so that the default
> fee cap would admit almost no deal. It changes decision 5 and §5.3 as follows:
> - **The hedge route has no fee cap and no fee exit.** The acquirer is shorted at
>   Alpaca if `shortable` and `easy_to_borrow`, else at IBKR if its shortstock file
>   shows enough shares at any fee, else no trade. A recall still closes both legs.
> - **f_max is still computed and printed (stage 4, stage 7), report-only.** It
>   decides nothing.
> - **Borrow is charged only in its own labelled column** (the four borrow
>   schedules, §7), never in the verdict. This is the desk's rule for the paper
>   account: gross P&L is the headline and borrow is labelled separately (team lead,
>   D19/D20, 2026-09-15).
> - **The coordinator's reading, for the team lead to correct:** "fees" means
>   borrow fees. Stage 4's execution-cost test at 15bp, and the 5 / 15 / 30bp grid,
>   stand as written.
>
> **Amendment 2 (team lead, 2026-10-20, after Stage 0 and before any E1 return): the Stage-0
> rulings and readings R1–R12, accepted as recommended.** The ruling, verbatim: "Accept all
> recommended" (relayed by the coordinator). It covers the 15 items of
> `results/events/E1_RULINGS_FORM_2026-10-20.md`:
> - **F1–F19.** The 19 Stage-0 flags are excluded and counted (§6.3). In 18 of them the acquirer
>   is a fund the merger created, with no share to short at A+1. In 1 (BLJ) the acquirer has no
>   CRSP name or payment-date price. Recorded in `results/events/e1/e1_stage0_rulings.csv`.
> - **R1–R11** as the form states. Among them:
>   - identity check 1 binds at 1e-12 against the published code's full-precision values;
>   - DG-E1-5 clears on factor coverage of the fit window (R8);
>   - control 2 adds no universe filter (R9);
>   - all 273 census episodes are read (R10).
> - **R12, in the form's words:** "Open it after any committed fit verdict except a HALT. After a
>   KILL or NEITHER it is report-only, and the verdict stays the fit's." This settles §10's
>   silence on the holdout after a fit kill. The kill rules are unchanged.
> - **Decision 6 stays at its default: failed deals are included.**
>
> Nothing here was chosen with sight of an E1 return; none had been computed. DG-E1-1, -2 and
> -3 stay halted until the team lead's `fetch-edgar` and `pull-crsp` runs and the 273 readings
> that follow them.
>
> **Amendment 3 (team lead, 2026-10-20, at Stage 0, before any E1 return): DG-E1-3's readings
> ruled.** The ruling: "Accept all" to items 1–7 of `results/events/E1_DG3_RULINGS_FORM_2026-10-20.md`,
> with both extra reading rounds chosen (relayed by the coordinator; recorded in
> `results/events/e1/e1_dg3_rulings.csv`):
> - **1. One deal, one count.** A is the earliest announcement and F the earliest public failure
>   across the deal's episodes.
> - **2. CRSP settles a listing the reader left null** (§4.3's share-code definition).
> - **3. BHV, BKN, MIY and MPA → MYI are withdrawn, F = 2023-11-01** (MYI's RW), in the time
>   holdout.
> - **4. MCC → CIK 1523526 is not a listed pair.**
> - **5. Rows that cannot change the trial** (triage classes C1–C3, and deals announced after
>   2024-12-31) are read and excluded, not blocking.
> - **6. The N-8F rule.** Batches 40 and 45 are re-read to it.
> - **8. A second, full-excerpt reading** of the 47 episodes that could still change the trial.
> - **9. A supplementary census** of the 149 acquirer-side episodes that the 730-day rule
>   explains, which is how SBI → MMU (§2.3) was missed.
>
> §4.3's census rule is widened by item 9 only. No kill rule changes.
>
> **Amendment 4 (team lead, 2026-10-21, at Stage 0, before any E1 return): the deal universe
> takes 331, and the CRSP outcome rule.** The rulings: "Amend: include 331" and "Accept the CRSP
> rule" (relayed by the coordinator; recorded in `results/events/e1/e1_dg3_rulings.csv` items 10–11).
> - **§4.1's universe:** CRSP delisting codes **231 and 331**, when the delisting maps to the
>   acquirer's permno. CRSP codes many CEF reorganisations 331, an exchange. They are priced by
>   `merger_pairs._announcement_row` unchanged; its code guard is widened for E1 only, and the
>   default is unchanged and tested.
> - **The new deals:** the fit gains 10 (muni +4 to 99 deals in 51 groups) and the name holdout
>   gains 1. Five more are excluded because their acquirer, HYT, is a spec name. Counts:
>   `results/events/e1/e1_universe_counts_2026-10-21.json`, made with no return read.
> - **The census** counts a 331 completion too.
> - **The CRSP outcome rule (DG-E1-3):** a blank outcome is settled from CRSP within 730 days of A:
>   - a 2xx or 3xx delisting into the acquirer's permno → completed;
>   - a 2xx into another permno → completed under another structure;
>   - liquidated, or still listed → not completed. A third reading then looks for the filing that
>     dates the failure (§6.1 needs F).
>   - anything else → unsettled.
>
> No kill rule changes.
>
> **Amendment 5 (team lead, 2026-10-21, at Stage 0, before any E1 return): DG-E1-3's remaining
> rows.** The ruling: "Accept 12–15" (relayed by the coordinator; recorded in
> `results/events/e1/e1_dg3_rulings.csv` items 12–15):
> - **12.** Listing follows CRSP share codes (§4.3), by ticker or else by CIK, BDCs included. A deal
>   whose counterparty nobody identifies is excluded and counted.
> - **13.** A deal CRSP shows never completed, with no dated failure, is excluded and counted
>   (§6.1 needs F).
> - **14.** An outcome still unstated after the readings is excluded and counted.
> - **15.** SBI → MMU and NCU → NKX (2011) are read in each target's own filings. If that settles
>   nothing, SBI → MMU is excluded and counted, and NCU → NKX takes §4.3's superseded rule with
>   F = 2013-11-22.
>
> No kill rule changes.
>
> **Amendment 6 (team lead, 2026-10-22, after Stage 0 cleared, before any E1 return): a fit deal
> with no control-2 candidate.** The ruling: "Keep, with no comparison" (relayed by the coordinator;
> recorded in `results/events/e1/e1_dg3_rulings.csv` item 16):
> - **16.** ALD → PSEC (BDC, failed 2010-03-05) stays in the trial with no control 2. It is
>   recorded as "no candidate: no CEF has the first name word ALLIED", and counted.
>   - **Why a ruling was needed:** §8.2 is silent on a non-muni deal with no candidate.
>   - **Why no verdict moves:** stage 3's 75% coverage rule is over fit muni deals, and BDC deals
>     never decide (§0).
>
> No kill rule changes.
>
> *Was:* DRAFT — awaiting team-lead approval; the counter moves only in the commit that records approval.
>
> **No E1 return of any kind was computed to write this.** No pair return, no
> control return, no window sum, no P&L, no Sharpe. The only new measurements are
> deal **counts** by declared set and segment:
>
> - reproducer: `python3 scripts/events/e1_prereg_counts.py`, run 2026-10-19;
> - output: `results/events/e1_prereg_counts_2026-10-19.json` (aggregates only);
> - inputs: CRSP names and delistings from the cache `crsp_events` pulled
>   2026-10-12 (to 2024-12-31);
> - from the delisting table it loads only permno, date, code and acquirer
>   permno. The delisting return, amount and price are never loaded, and a test
>   pins that (`scripts/events/tests/test_e1_prereg_counts.py`).
>
> Every other figure is quoted from a published note, labelled [S] here, or is
> arithmetic on such figures, labelled as arithmetic. This commit moves no
> counter, changes no spec and touches nothing on the order path.

---

## 0. The declaration in one table

| item | declared |
|---|---|
| what is tested | after an EDGAR-dated NAV-for-NAV merger announcement between two exchange-listed CEFs, go **long the target and short the acquirer, $1 for $1**, from the close of A+1 to completion (shift(2): decide on the evening of A, fill at the close of A+1, earn from A+2). A failed deal is closed at the close after its failure is public |
| headline segment | **municipal** (decision 2): the target is a muni fund by `merger_pairs.classify`. Taxable, equity and BDC deals are reported beside it and never decide |
| hedge leg | **the acquirer, and nothing else.** Live: at Alpaca if `shortable` and `easy_to_borrow`; else at IBKR if its shortstock file shows enough shares at a fee ≤ f_max; else **no trade**. Never an ETF, never long-only (§5) |
| f_max | ½ × the fit's break-even borrow fee (§5.3), computed once from the fit and frozen in the fit-verdict commit |
| fit | 2010–22 completed and failed deals with no `cef_universe.csv` name: muni **95 deals in 49 groups** counted [V]. Their returns were published on 2026-10-12, so **the fit is not out of sample** (§2.3) |
| holdouts, opened once after the fit verdict | (i) **name holdout**: 2010–22 deals with a `cef_universe.csv` name, never priced, muni **31 in 15 groups** [V]; (ii) **time holdout**: completions 2023-01-01 → 2024-12-31, muni **5 in 3 groups** [V]; pooled for the rule (decision 3) |
| 27-name set | **E1 consumes it.** 10 of the name holdout's muni deals and 4 of its taxable deals are on the 27. It is consumed when Stage 1 begins |
| excluded | deals with a frozen-spec name on either side (the book's own names, decision 4): 14 deals in 4 groups [V], reported only |
| kills (plan row 2 + house rules) | median per deal ≤ 60bp, or group-clustered t < 2; either control earns ≥ ½ of the effect; sleeve net ≤ 0 at 15bp; D4; the bar; the holdout signs (§10) |
| pass | stages 1–6 and 8 all pass (§10) |

The numbered decisions for the team lead, each with a default, close the note
(§15). Approval approves the defaults unless a ruling says otherwise.

## 1. What is tested, and what is not

**Tested:** whether the target-minus-acquirer pair of a CEF NAV-for-NAV merger
earns a positive return from the close of A+1 to completion, in munis, net of
the 15bp grid, beyond factor exposure, and at the EVENTS bar. Then, once, on
deals nobody has priced.

**What changes if it passes.** Nothing in the live book. A pass makes E1 a
candidate paper sleeve under plan §4. That needs:

- a frozen-spec key that defaults to off, with a byte-for-byte no-op proof
  (`/spec-change`);
- live detection from the event engine (`results/events/EVENT_ENGINE_DESIGN_2026-10-15.md`);
- the IBKR order path (ruled 2026-10-19; not built here);
- its H11 statistic (§12) and a release.

The one-line revert is to delete that key. This trial writes no key.

**Not tested:**

- **ETF or basket hedges.** That variant failed its zero-trial gate
  (`results/events/E1_ETF_HEDGE_GATE_2026-10-15.md`), and §5 declares that a
  deal with no acquirer borrow is not traded at all.
- **Entry after A+1.** A pending deal announced before a sleeve goes live is
  not entered late. Late entry is a different trade with no published evidence.
- **A conditional entry** on the ex-ante discount gap. That needs G1b's NAV
  history, which does not exist for 2010–18.
- **Cash or cash-election mergers**, and conversions into an open-end fund or
  ETF (no listed acquirer to short).
- **Equity merger arbitrage.** The 2026-10-19 ruling reopens it as its own
  design.

## 2. Why, mechanically

### 2.1 The mechanism

- **The terminal condition.** In a NAV-for-NAV merger, each target share
  converts into acquirer shares at the ratio of the two NAVs on the closing
  date. At completion the target is therefore worth the acquirer's price times
  the NAV ratio. **The target's discount converges to the acquirer's.**
- **The trade.** When the target trades at a wider discount than the acquirer
  after the announcement, long target / short acquirer earns the gap. Its
  residual risk is the acquirer's own discount moving, which the short leg
  removes through the NAV-ratio tie.
- **The evidence that only the acquirer hedges this.** Inside a deal, the muni
  pair's dispersion is 336bp. The best ETF leaves 787bp over the same hold
  [S: `E1_ETF_HEDGE_GATE_2026-10-15.md` §3, §6].

### 2.2 Who is on the other side, and why they stay

- **Target holders who sell after the announcement.** They are mostly retail
  income buyers: some do not want the merged fund, and some sell to realise
  losses.
- **Arbitrageurs who cannot short the acquirer.** Most muni acquirers are
  thinly lent. G1a found 7 of 23 historical muni acquirers shortable at Alpaca
  and 17 of 23 listed in IBKR's file [S: `G1A_SHORTABILITY_2026-10-13.md` §3].
  The muni acquirers' IBKR fee at first filing had a median of 9.43%/yr
  [S levels, 10 episodes, 2021-12 → 2026-05].
  - Mitchell, Pulvino & Stafford (2004) attribute nearly half of a stock
    acquirer's negative announcement return to arbitrage short selling
    [S: `docs/REFERENCES.md` §12aa].
- **What that predicts, stated against ourselves.** If borrow scarcity is why
  the gap persists, part of the gross effect **is the price of borrow**. Net
  of measured borrow it may be small or nil. That is why borrow is charged in
  its own column (§7), why the live leg is capped at f_max (§5.3), and why
  the live falsifier counts admissions as well as P&L (§12).

### 2.3 What is already known, and what that does to this test

1. **The fit is spent.** The at-announcement pair on EDGAR dates (167 priced
   deals, no `cef_universe.csv` name) was computed and published on
   2026-10-12 [S: `EDGAR_EVENTS_2026-10-12.md` §3]:

   | segment | N | groups | median | mean | % > 0 | clustered t |
   |---|---:|---:|---:|---:|---:|---:|
   | muni | 92 | 47 | +167.4bp | +125.8 | 68.5% | 2.41 |
   | taxable | 39 | 30 | +4.6 | +138.1 | 51.3% | 0.98 |
   | equity / other | 33 | 26 | +15.0 | −18.2 | 51.5% | −0.16 |
   | BDC | 3 | 3 | −86.9 | −72.8 | 33% | — |
   | all | 167 | 102 | +86.5 | +96.6 | 60.5% | 1.93 |

   So **stage 1 on completed deals is close to known**, and the muni headline
   (decision 2) was **chosen after seeing this table**. The fit cannot confirm
   that choice. The tests that carry information are:
   - the failed deals (§4.3);
   - the two controls;
   - D4;
   - the bar;
   - **above all, the holdouts**, which no one has priced.
2. **The sample is survivors.** CRSP's merger delistings are completed deals
   only. Failed proposals are not rare: SBI → MMU failed its vote in 2023 [S];
   Nuveen's 2023 NXJ → NAD and NQP → NVG did not complete [S, inferred]. The
   trial adds them (§4.3).
3. **93 of 186 dates are upper bounds**, dated by the acquirer's N-14 with no
   earlier merger filing [S]. Entry is therefore late on those deals. That
   cannot leak information. It may cost return.
4. **G1b was never measured.** No NAV history exists for 2010–18 targets. The
   declared rule is unconditional, so it does not need G1b. But no hedge ratio
   can be matched to the conversion value, so the hedge is $1 for $1, as in
   the published figures.
5. **The fixed-offset figures are ex post.** For example, the muni T−63 pair
   (+148.5bp) against the same pair a year earlier (−43.5bp)
   [S: `REPRO_CEF_EVENTS_2026-10-11.md` §2]. They are anchored on completion
   and use the final ratio. They are context for control 1, never evidence.

### 2.4 The graveyard (`/graveyard`, `docs/RESEARCH_STATE.md`)

| dead mechanism | how E1 differs, and the risk that remains |
|---|---|
| **Cointegration pairs** (CEF construction: gross 1.03 → net −0.16; 32.8× leverage) and **pair-reversion** (D2 + capacity) | Those trades waited for a statistical spread to revert. E1 has a **contractual terminal condition** (conversion at the NAV ratio) on a known event. The risk that remains is capacity: muni targets' median 63-day ADV before announcement was $145k [S: ETF gate §5] |
| **The stale-price artefact** (the commonest cause of death) | P&L is price to price, ending in a CRSP conversion value. A stale close on the fill day would make the entry unexecutable. So the quality screen flags fill days with no closing trade (CRSP `prc` < 0), and a one-session-later entry (shift(3)) is reported (§8) |
| **A control scoring as well as the treatment** (the second commonest) | Two controls, each a ½ kill (§8). Control 1: the same pair a year earlier. Control 2: the target replaced by a non-merging same-sponsor fund |
| **S3-wrapper (D4)** and merger arbitrage's index (D4 in costume, `MERGER_ARB_AND_IBKR_2026-10-15.md`) | E1 is market-neutral by construction, within segment and usually within sponsor. D4 is still a kill (§8.3). Factors include the muni market (MUB), duration and credit |
| `credit_rv`, `leadlag` (stale prices, D1) | Not relevant: no ETF prices, and no lead-lag between wrappers |

## 3. Divergences from the backtest, stated up front

**Read this section before any result.** The backtest and the live trade differ
most in the leg that matters.

### 3.1 The two failed gates, and why the trial is spent anyway

- **G1a failed at Alpaca, for munis**, where the effect lives
  [S: `G1A_SHORTABILITY_2026-10-13.md` §0]:
  - pending muni acquirers: 1 of 2 shortable on 2026-10-13 (MMU yes; NZF no);
  - historical muni acquirers, on that day's flags: 7 of 23.

  The note recommended against spending EVENTS on E1 as designed. **At IBKR
  the same names were mostly available**: 17 of 23 historical muni acquirers,
  and 3 of 3 pending deals. "Not shortable" was a fact about Alpaca's supply,
  not about the asset.
- **The ETF-hedged variant failed its zero-trial gate in every segment**
  [S: `E1_ETF_HEDGE_GATE_2026-10-15.md` §0, §7]:
  - every muni ETF (MUB, VTEB, TFI, HYD, SUB, SHM, MLN, CMF, NYF) was
    `hard_to_borrow` and not shortable at Alpaca on 2026-10-15;
  - even if they could be shorted, the best hedge leaves 2.1–2.6× the
    effect's own dispersion, an implied clustered t of about 0.94.

  The note's reading was that an ETF cannot remove the CEF discount; only the
  acquirer can.
- **The team lead's rulings, 2026-10-19** (recorded in `docs/SYSTEM.md` §5 on
  `main` at `94bca4a`; this branch's base, `832aeaa`, predates them):
  - E1: "Spend an EVENTS trial on it (pre-registration first), although the
    ETF-hedge gate failed; IBKR's borrow is admissible for the short leg."
  - IBKR: "Open it as a second broker, equities only (no options data), for
    the shorts Alpaca will not lend. The team lead holds the account and the
    weekly two-factor login."

  **This draft's reading of why** (the team lead to correct it): the ETF gate
  showed the acquirer is the only workable hedge. G1a showed that hedge is
  missing at Alpaca, not in the market. Admitting IBKR's borrow makes E1 as
  designed buildable, so the trial tests the designed trade, not a substitute.
- **Declared consequence.** A deal whose acquirer neither broker lends at the
  decide, within f_max, is **excluded, not hedged otherwise**. That holds in
  the backtest's live-equivalent row and in live (§5).

### 3.2 The divergences

1. **Borrow existence and price in history are assumed, not observed.**
   - No broker has a flag or fee history before 2021-09. IBKR's FEE_RATE
     series covers only the 43 universe names [S: §12l].
   - The backtest therefore treats **every** historical acquirer as lendable
     and charges borrow on a declared schedule (§7).
   - The only historical evidence of supply: every muni acquirer FINRA covers
     (2018–22) had a reported short position at announcement, 28 of 28 [S: G1a
     H2]. That shows borrow existed somewhere, not at what price.
   - **Live trades only the deals that pass §5's routing at the decide.** At
     the fees seen so far (§5.3), that may be a small minority of muni deals.
     This is the largest divergence, and §12's admission falsifier exists for
     it.
2. **Two brokers, two accounts.**
   - Margin does not cross brokers. An IBKR-routed pair needs its own account
     cap; the CEF account's `max_gross_stress` is a book number
     [S: `MERGER_ARB_AND_IBKR_2026-10-15.md` B8].
   - The backtest caps E1 alone.
   - Both legs of a pair go to one broker, because MOC cannot be cancelled
     after 15:50 and there is no cross-broker undo [S: B8].
   - Idempotency must hold per broker (order-path rule 2). IBKR resubmits
     orders on reconnect by default [S: B6].
   - The weekly manual 2FA login is the team lead's, so an IBKR session can be
     missed. A missed entry is a missed deal, counted, never back-filled.
3. **Paper execution.**
   - **Alpaca paper:** no closing auction (the `late_market` exception, rule 3),
     no borrow fees, no dividends. The third, distribution-adjusted P&L line
     carries the short's distributions.
   - **IBKR paper:** simulated top-of-book fills, no "Auction" order type
     [S: B7]. Whether paper MOC fills at the official close, and whether paper
     charges borrow, are [U].
4. **Dates.**
   - Live: the event engine's `observed_at`; a decision at 22:00 ET can use a
     filing dated that day.
   - Backtest: EDGAR's filing date A, which already moves a filing accepted
     after 17:30 to the next business day [S: §12z].
   - Where a press release preceded the first filing, live may see the deal
     earlier than the backtest did. That is late entry in the backtest; it
     cannot leak.
5. **NAV-for-NAV is a proxy in history.**
   - The backtest uses CRSP code 231 (stock-for-stock) with an acquirer permno.
   - Live requires the exchange basis to be read from the N-14 8C before entry
     (G1a read, for example, "based on the net asset value").
   - Not every historical 231 deal was verified to be NAV-for-NAV [U].
6. **Completion is a conversion, not a trade.**
   - The received acquirer shares cover the short.
   - Only the residual (shares received minus shares short) trades.
   - The harness's Σ|ΔH| would charge four legs; the trial charges the
     residual (§6.4).
7. **The harness holds weights constant** between trades, which means daily
   rebalancing at no cost. The per-deal statistics are buy-and-hold (the
   published `_announcement_row`). The gap between the two is reported (§6.4).
8. **Recall.** Muni CEF lenders have a monthly reason to recall before record
   dates [S: `docs/BRIEF.md` §3, "The short side"]. Live, a recall closes both
   legs at the next close (§5.4). The backtest cannot model recalls.
9. **Whole shares, and small names.** At $100k a deal's legs are a few
   thousand dollars. Muni targets' median ADV was $145k [S]. Live entry is
   capped by the desk's 5% participation guard (§6.5); the backtest enters in
   one close and reports the participation it would have needed.
10. **The spec-name exclusion uses today's 13 names** on 2010–24 deals
    (decision 4). MHD and MQY are in the spec partly because they absorbed
    other funds and grew. The excluded deals are reported, not hidden.

## 4. The sample

### 4.1 Deals

- **Universe.** CRSP merger delistings of share-code 14/44 securities,
  2010-01-01 → 2024-12-31, kept to stock-for-stock deals (`dlstcd` 231) with an
  acquirer permno: `merger_pairs.build_events` with the `pairable_events`
  filter, minus its universe exclusion.
- **Plus failed deals** (§4.3).
- **A deal** is one target into one acquirer.
- **A group** is acquirer × EDGAR announcement date: one board decision,
  usually several targets. It is the clustering unit, as in the published
  figures.
- **Announcement date A.** The first merger filing of the deal's last unbroken
  run of merger filings, read before use, by `scripts/events/edgar_merger_dates.py`
  unchanged [S: `EDGAR_EVENTS_2026-10-12.md` §3]. Its rules were fixed before
  any of these returns existed.
- **Segment.** `merger_pairs.classify` on the target's CRSP name, the label
  the published table used. A regex label, not a fact about the fund [S].

### 4.2 The declared sets (each deal in exactly one)

The rule is `e1_prereg_counts.partition`, tested. Groups were checked not to
straddle two sets (the script raises if one does).

| set | rule | muni deals / groups | all segments | on the 27 | status |
|---|---|---:|---:|---:|---|
| **fit** (`fit_seen`) | completed before 2023; no `cef_universe.csv` name on either side (ticker or permno) | **95 / 49** | 186 / 109 | 0 | returns published 2026-10-12: **seen** |
| **name holdout** | completed before 2023; a `cef_universe.csv` name on either side; no spec name | **31 / 15** | 35 / 18 | 14 (10 muni) | **never priced**; sealed until opened (§10, stage 8) |
| **time holdout** | completed 2023-01-01 → 2024-12-31; no spec name | **5 / 3** | 29 / 19 | 1 | sealed (H13); 2023+ returns opened once |
| **excluded** | a frozen-spec name on either side | 9 / 2 | 14 / 4 | 0 | reported only (decision 4) |

[V: `e1_prereg_counts.py`, 2026-10-19. Groups here are acquirer × completion
date; the trial's acquirer × announcement-date groups are counted at Stage 0.]

**Reading:**
- The fit's 95 muni deals become 92 priced in the published sample. The other
  3 have no acquirer price at A+1 [S].
- **The time holdout holds almost no munis.** 5 deals in 3 groups cannot
  decide anything alone.
- **The name holdout is where the unseen evidence is.** Of its 31 muni deals:
  - 21 have one of the four munis dropped from the deployed book (NAD, NEA,
    NVG, NZF) as acquirer;
  - 10 are on the 27-name comparison set.

  Their pair returns were never computed: every published E1 figure excluded
  `cef_universe.csv` names by permno [S: `REPRO_CEF_EVENTS_2026-10-11.md`
  §2]. One deal on a universe permno, SBW → ESD (2016), was inside the
  ticker-matched fixed-offset rows (the original agent's and the re-run's
  "ticker" column) [S], never the at-announcement sample. It stays in the name
  holdout and is flagged.
- **What else touched these names:**
  - the deployed book's research has read the 4 dropped munis' prices for
    years, though never conditioned on a merger;
  - G6 priced the book's own shorts in acquirer windows of spec names only
    [S: `EDGAR_EVENTS_2026-10-12.md` §4].

  So the name holdout is unseen for E1's statistic, not for every price in
  it.
- **Completions after 2024-12-31 are not in any set.** That includes the
  2025–26 BlackRock and Nuveen muni consolidations. CRSP ends, and no other
  source has been checked for delisted-target total returns and conversion
  values. They are counted at Stage 0, not priced (decision 3 names the
  alternative).

### 4.3 Failed deals (data gate DG-E1-3)

- **Which episodes.** Every EDGAR merger episode from
  `scripts/data/fetch_edgar_events.py` with:
  - a first filing from 2009-07-01 to 2024-12-31;
  - a target and an acquirer that were both exchange-listed CEFs or BDCs
    (CRSP share code 14/44, or 11 for a BDC) on the first filing date;
  - no CRSP completion within 730 days.

  Each is read.
- **The reading records:**
  - the outcome: terminated, vote failed, withdrawn (RW), superseded, or
    completed under another structure;
  - the **first public filing announcing it**, with its accession and a
    verbatim quote;
  - all in a readings file whose quotes the trial re-finds in the filing on
    every run, or raises (the `merger_arb_readings.py` design).
- **An episode that cannot be read halts Stage 0.**
- **A failed deal's set** follows its exit (failure) date, by the same rules as
  §4.2.
- **Its return.** Long target / short acquirer, $1 for $1, from the close of
  A+1 to the close of the session after the failure filing date. Both legs
  trade out, so 4 units.
- **"Superseded"** (a fund's 2023 proposal replaced by a different 2026 merger)
  is a failure of the first proposal on the date the second is first filed.

## 5. The hedge leg, declared up front

### 5.1 What the published evidence says about lending (all [S], true on its date only)

| evidence | Alpaca | IBKR (public `shortstock/usa.txt`) | source |
|---|---|---|---|
| pending muni acquirers, 2026-10-13 | NZF not shortable (`hard_to_borrow`); MMU shortable, ETB | NZF 3.15%/yr, 200,000 shares; MMU 1.19%, 40,000 | G1a §2 |
| historical muni acquirers still listed, flags read 2026-10-13 | 7 of 23 shortable | 17 of 23 listed | G1a §3 |
| the four dropped munis and MHD/MQY, file of 2026-10-16 | all six not shortable | NZF 3.20, NAD 5.15, NVG 4.24, MHD 2.49, NEA 2.46, MQY 0.83 (%/yr) | MERGER_ARB B3 |
| universe muni acquirers' fee the day before first filing, 2021-12 → 2026-05 | — | median 9.43%/yr, range 2.57–71.73 (10 episodes) | G1a H1b; [S] levels |
| short interest at announcement, 2018–22 | — | — | FINRA: every covered muni acquirer had a position (28 of 28) [S] |
| every muni ETF, 2026-10-15 | not shortable | MUB 5.51%, VTEB 4.55% | ETF gate §5 |
| Alpaca's live fee on an easy-to-borrow short | "Free (no locate or stock borrow fees …)" | — | REFERENCES §12l [V there] |
| how a fee accrues | daily, rate ÷ 360, on 102% of the prior close | the same | §12l; `band_frontier.BORROW_DAY_COUNT`, `BORROW_COLLATERAL_MARKUP` |

### 5.2 The routing rule (live; read at each decide)

It is evaluated on the evening of A, for the acquirer, in this order. The
reads are logged with their timestamps.

1. **Alpaca.** If `GET /v2/assets/{acquirer}` shows `shortable` and
   `easy_to_borrow`, **both legs go to Alpaca**, inside the CEF account (the
   2026-10-09 "one combined book" ruling).
2. **IBKR.** Otherwise, read the newest IBKR shortstock file. If it shows the
   acquirer available, with shares ≥ the short's shares, at a fee ≤ f_max
   (§5.3), **both legs go to IBKR**.
3. **No trade.** Otherwise the deal is **excluded**, logged with the reads, and
   never traded. In particular:
   - no ETF or basket hedge, because the gate failed;
   - no long-only target, which would be beta, ruled out by "alpha only".
4. **Never split a pair across brokers.**
5. **Never let one symbol take opposite sides at two brokers in one session**
   [S: B8]. Spec names are excluded anyway (decision 4).

The target leg must be tradable at the chosen broker. Otherwise the deal is
excluded too.

### 5.3 f_max, derived

The fit gives the break-even borrow fee directly, at the 15bp grid point:

    f_be  = (m − 2 × 15bp) × 360 / (1.02 × D)       [annual rate]
    f_max = ½ × f_be

- **m** is the fit's median per-deal gross pair return, completed and failed
  muni deals together (stage 1's own statistic).
- **D** is the fit's median calendar days from the entry fill to the exit, on
  the same deals.
- **1.02 and 360** are the collateral mark-up and day count both brokers use
  (`band_frontier` constants).
- **½** keeps at least half of the median deal's net edge after borrow. It is
  the declared margin; decision 5 names the alternative.

f_max is computed once at stage 4, printed, and **frozen in the fit-verdict
commit**. It is never re-fitted on the holdout or live (H13). **No number
written here enters the rule (H14).**

*For scale only (arithmetic on [S] inputs, completed deals only, not a rule
input):*
- with m = 167.4bp and D = 243.5 days [S: ETF gate §2], f_be ≈ 1.99%/yr and
  f_max ≈ 1.0%/yr;
- at that cap, no muni acquirer in §5.1 would be admitted at IBKR except MQY
  (0.83%), which is a spec name and excluded anyway (decision 4). MMU would
  route to Alpaca for as long as it reads `easy_to_borrow`;
- **the live sleeve may admit few muni deals.** §12 makes that a falsifier.

### 5.4 While a pair is held (live only; the backtest cannot see these)

- **A recall or buy-in notice** on the acquirer: close both legs at the next
  close.
- **At IBKR:** if the acquirer's fee, read at the decide, exceeds 2 × f_max on
  5 consecutive sessions, close both legs at the next close (decision 5).
- **At Alpaca:** the acquirer turning `shortable: false` while the short is
  held does not by itself close it (Alpaca does not close an existing short on
  a flag). A recall does.
- Every forced exit is logged and counted. §12 reads them.

### 5.5 In the backtest

- **Every historical acquirer is treated as lendable** (§3.2 item 1). Borrow is
  charged on the schedules of §7.
- **R-IBKR-TODAY**, report only: the fit restricted to deals whose acquirer is
  still listed and was in IBKR's file at a fee ≤ f_max on the newest file at
  run time. This selects on information from the future (G1a §4), so it
  **never decides**.

## 6. Positions, entry, exit, sizing, and the evaluator

### 6.1 Execution convention (H1)

- **Entry.** Decide on the evening of A (a filing dated A is public by 22:00
  ET on A [S: §12z]). Fill both legs at the close of the first session after A
  (A+1). Earn from A+2.
- This is exactly `merger_pairs._announcement_row`'s entry ("entry at the close
  of A+1"), and it is what `evaluate()`'s `H.shift(2)` does to a weight first
  set on the session before the fill.
- **The runtime assertion:** the fill session is strictly after A.
- **Exit, completed deal.**
  - The target leg earns through CRSP's delisting return, booked on the
    payment-date row (`dlpdt`).
  - The acquirer leg earns through `dlpdt`, as `_announcement_row` does.
  - The conversion closes the pair.
- **Exit, failed deal.** Decide on the evening of the failure filing date F;
  close both legs at the close of F+1.

### 6.2 Sizing

- **Raw sleeve.** Each active group gets 1 unit long, split equally across its
  active targets, and 1 unit short its acquirer. An acquirer in two active
  groups is netted.
  - When a target fails out of a multi-target group, the acquirer short falls
    by that target's share at the same close.
  - The per-deal statistics stay $1 for $1, as published.
- **Sized sleeve:** k × raw, with k = `vol_target_annual` ÷ σ_fit.
  - `vol_target_annual` is read through `scripts/cef/spec.py`.
  - σ_fit is the raw sleeve's annualised daily gross P&L volatility over the
    fit, from its first position.
  - k is one constant, frozen for the holdouts and live (E2's rule, XASSET P5).
- **Tradable sleeve:** the sized sleeve with `max_gross_stress` (read through
  `spec.py`) applied row by row by the sleeve's own `_cap_gross`
  (`src/deploy/sleeves/cef_discount.py`). The share of sessions on which the
  cap binds is reported.
- **D4 betas** are read at the vol target (§8.3).

### 6.3 Returns (H15)

- **The source.** CRSP `dsf.ret`, a total return. The short acquirer pays its
  distributions inside `ret`.
- **The guard.** `evaluate()` sums `H.shift(2) * R` with pandas' `sum`, which
  **skips a NaN silently**. So the trial asserts, before calling it, that every
  held name-day has a finite `ret`, or is a gap that `merger_pairs.bridging_check`'s
  CRSP convention covers (≤ 10 sessions, the next `ret` spans it).
- **Anything else** excludes the deal, and it is counted. **Nothing is filled
  with zero.**
- **The fit reader** is `crsp_events.daily`, which cannot return a 2023+ row.
- **The holdout reader** is a separate function. It runs only after the
  fit-verdict commit exists, as in E2's DG-E2-1.

### 6.4 The evaluator: no new backtester

The trial script, `scripts/events/e1_merger_pair.py` (written after approval),
uses:

| piece | code | changed? |
|---|---|---|
| deal table and sets | `merger_pairs.build_events`, `flag_universe`, `classify`; `e1_prereg_counts.partition` | no |
| dates | `edgar_merger_dates.py`, run over all three sets (zero trials: dates are not returns) | no |
| per-deal pair, completed | `merger_pairs._announcement_row` (`pair_A1_to_close`) | no |
| per-deal pair, failed and controls | `merger_pairs.window_return` | no |
| per-deal inference | `merger_pairs.clustered_t`, `grid_table` | no |
| the sleeve | `band_frontier.evaluate(H, R)` (shift(2)), `fit_only`, `_stats`, `borrow_charge` | no |
| H from deal legs | **new** `band_frontier.event_hold(legs, index)`, beside `hold_from_refresh`, with tests. Each leg is (permno, first decision row, last decision row, weight); legs on one permno are summed. Raises on a NaN weight, on a leg outside the calendar, and on a first row whose fill is not after A | added visibly |
| turnover | **new** `band_frontier.event_turnover(H, conversions)`: Σ\|ΔH\| minus the two legs a conversion closes, plus the conversion residual (the received shares' value minus the short's, at the payment-row close) | added visibly |
| cap, bar, HAC, bootstrap | `_cap_gross`; `validate._dsr`; `w4_artifacts.nw_t`, `stationary_boot`, `block_boot_t` | no |

**Two identity checks run at Stage 0.** Both are on figures already published.

1. `_announcement_row` reproduces the published per-deal `pair_A1_to_close` on
   the 167-deal sample to 1e-12.
2. The constant-weight sleeve's summed P&L per deal is set beside the
   buy-and-hold pair. The median and the 95th percentile of |difference| are
   printed. This is reported, not a gate: the harness convention is constant
   weights.

### 6.5 Capacity (reported; it never decides)

- **Participation.** Of the sized sleeve's per-deal entry at $100k, $1m and
  $10m of capital, against each leg's 63-session ADV ending the session before
  A.
- **Capacity.** The capital at which the median deal's entry reaches the
  desk's 5% participation guard (`scripts/cef/plan_diagnostics.py`, a
  convention, not a measured impact threshold).
- **Live.** Entry above the guard is split over the following closes, each
  decided the evening before. That is a divergence, stated in §3.2.

## 7. Costs and borrow

**Gross is the headline** (D19/D20: the paper account is scored gross). **The
grid is beside it, labelled, never mixed into one column.**

- **Per deal** (the plan's unit): net = gross − c × units, at c = 5 / 15 /
  30bp.
  - Units are **2** for a completed deal (entry only; conversion closes the
    short) plus the residual.
  - Units are **4** for a failed deal.
  - Whether the sign flips across the grid is stated.
- **Sleeve:** `_stats(pnl, event_turnover)` at 5 / 15 / 30bp on all legs, and
  whether it flips sign (H3).

**Borrow is charged separately and labelled (H4).** `borrow_charge(H, fee_pct)`
runs on the short leg under each schedule. Every schedule is an assumption,
because no fee history exists for these acquirers before 2021-09:

| schedule | what it is | label |
|---|---|---|
| B0 | zero: Alpaca's ETB terms, and the paper account | counterfactual for any non-ETB acquirer |
| B-cap | a flat f_max (§5.3) on every acquirer | the worst fee the live rule admits |
| B-med | a flat median IBKR fee of universe muni acquirers the day before their first merger filing, **re-measured at run time** from `data/cef/cef_borrow_history.parquet` by G1a's H1b method (not the 9.43 written above) | universe-acquirer fees applied to other acquirers: an assumption |
| B-meas | the measured FEE_RATE series, only where the acquirer is a universe name and the window lies inside 2021-09-13 → the panel's last date (for example the NZF deals completed in 2022 and 2023); `uncovered` reported | measured; partial coverage |

**Also reported:**
- **the break-even annual fee:** the flat rate at which the fit sleeve's net
  at 15bp reaches zero. It is the borrow the effect can carry.
- **IBKR's short-proceeds interest:** 0% on the first USD 100,000 [S: B3]. On
  this account size the short earns nothing on its cash.

## 8. Inference and controls

### 8.1 Statistics

| quantity | method |
|---|---|
| **per deal** (plan row 2) | median and mean gross pair return over fit muni deals, completed and failed. **t clustered by group** (CR1, `merger_pairs.clustered_t`). Beside it: one observation per group (the group mean), and a group bootstrap (10,000 draws, seed 20261019) |
| **sleeve headline** | annualised gross Sharpe of the tradable sleeve's daily P&L over the fit, from its first position |
| **HAC t** | Newey–West, L = 21 (`w4_artifacts.nw_t`); L = 63 printed, because holds are long |
| **bootstrap** | stationary, mean block 63, 10,000 resamples, seed 20261019, for the sleeve's mean and Sharpe. Block 21 is printed |
| **the bar** | `validate._dsr(obs, T, skew, kurt, N)` on the fit's gross series; **PASS > 0.95** at N (decision 1) |
| eras (H5) | 2010–14, 2015–19, 2020–22 (fit), each with its deal count, median, clustered t and turnover sd/mean. The 2023–24 holdout is its own row |

### 8.2 Controls (both turnover-matched by construction: identical legs, notional and window length)

| stage | control | rule |
|---|---|---|
| **2** | **The same pair a year earlier** (plan row 2). The identical $1 / $1 pair over a window of the same length in sessions, ending 252 target sessions before the real entry. Exit is by trade (4 units) | **KILL** if the control's median per-deal gross ≥ ½ × the treatment's, same sign. A deal whose window precedes either fund's listing has no control, and is counted |
| **3** | **A non-merging same-sponsor fund replaces the target** (plan row 2). The fund is chosen from candidates that: are CEFs (share code 14/44); have the target's first CRSP name word (G1c's sponsor heuristic) and its segment; have prices across the whole window; are not a party to any EDGAR merger episode from 252 sessions before A to 21 after the exit; and are not a party to any name- or time-holdout deal overlapping the window (so no holdout price leaks into the fit). The nearest 63-session ADV wins (log distance; ties by lower permno). Long that fund / short the same acquirer, same window | **KILL** if its median ≥ ½ × the treatment's, same sign. **HALT** (to the team lead) if fewer than 75% of fit muni deals have a control |

**Reported, never deciding:**
- **shift(3):** entry at the close of A+2;
- the fill-day quality screen: either leg with CRSP `prc` < 0 (no closing
  trade) on the fill day;
- **R-IBKR-TODAY** (§5.5);
- all segments;
- the agent's 36 dated events.

### 8.3 Regressions

OLS with HAC covariance (maxlags 21). The P&L is a self-financing long-short,
so no risk-free rate is subtracted.

| regression | role | specification |
|---|---|---|
| **R-D4** | **decision** | daily tradable gross P&L on French Mkt-RF, SMB, HML, RMW, CMA, UMD, and on MUB, IEF and HYG total returns in excess of the bill. Each factor enters at *t* and *t*−1 (Dimson; CEFs trade thinly), and the betas are summed. **Pass: alpha t ≥ 3.0 and every \|summed β\| ≤ 0.10 at the vol target** (decision 8) |
| R-FF | reported | the French factors alone (E2's set) |
| R-BOOK | reported | on the deployed CEF book's daily P&L: correlation and beta. **Never a kill** (plan row 2 names none) |

## 9. How the rule was derived, and what was not chosen

- **Entry at A+1, held to completion.** Fixed by the published at-announcement
  measurement and by shift(2). Nothing was swept.
- **Rejected: the fixed-offset windows.** T−126 (+166bp all deals) was the
  largest pair in the published table; T−63 (+148.5bp muni) is close behind
  [S]. **Neither was chosen**: they are anchored on the completion date and the
  final ratio, which nobody knows at entry (§2.3 item 5). That is the
  `z_window = 63` lesson in another form.
- **$1 for $1.** The published unit. A conversion-matched hedge needs NAVs at
  A, which do not exist for 2010–18 (G1b).
- **Muni headline.** **Chosen after seeing the by-segment table.** The
  alternative not chosen is the plan's all-segment E1, whose published median
  (+86.5bp, t 1.93) already sits below the plan's t kill. The choice is
  decision 2. The holdouts, not the fit, test it.
- **f_max.** A formula on fit quantities (§5.3), with a declared ½ margin. Not
  chosen: the full break-even, and any fee level picked from a sweep.
- **k, the cap and the bar** follow E2's declared rules unchanged.

## 10. The order of evaluation (the exact kill rules)

| stage | statistic | rule | if it fails |
|---|---|---|---|
| 0 | DG-E1-1…7 (§13); the deal counts by set, reprinted beside §4.2's (H14); both identity checks; the quality screen; k; the cap's binding share | a gate fails | **HALT**: referred to the team lead, who rules whether to fix and go on. No E1 statistic is computed past a halt |
| — | **E1 statistics begin here; the 27-name set is consumed from here** | — | — |
| 1 | fit muni, per deal, completed and failed: median and group-clustered t | median > 60bp **and** t ≥ 2.0 (plan row 2) | **KILL D1** |
| 2 | control 1 (§8.2) | control median < ½ × treatment median | **KILL** (not the merger) |
| 3 | control 2 (§8.2) | the same | **KILL** (not the target's convergence) |
| 4 | tradable sleeve net at 15bp, all legs, event turnover; f_max computed and printed | > 0 | **KILL D2** |
| 5 | R-D4 | alpha t ≥ 3.0 and every \|summed β\| ≤ 0.10 | **KILL D4** |
| 6 | the bar: `_dsr` at N | > 0.95 | **NEITHER**: real at most, below the bar. No sleeve and no re-test on these data. The team lead rules WATCH or D5 |
| 7 | the fit verdict is committed, with k, f_max and every fit statistic | — | — |
| 8 | **the holdouts, opened once** (name + time holdout, pooled; each also reported alone): **(a)** the mean per-deal gross pair return > 0; **(b)** the holdout sleeve's mean daily gross P&L > 0, with k and the cap frozen; **(c)** the mean per deal of treatment minus control 1 > 0 | all three > 0 | **KILL D3** |
| — | the grid (5 / 15 / 30bp), the four borrow schedules, the break-even fee, the eras | reported, with whether the sign flips | — |

- **Every statistic of every stage is computed and reported**, whatever the
  verdict. The verdict is the first failing rule in this order.
- **A PASS needs stages 1–6 and 8.** The holdout can kill; **it can never
  rescue a failed fit**.
- These kill rules are pre-committed and **are not softened later**.

## 11. What we expect [U]

Arithmetic on the published figures. None of it is an E1 measurement.

- **Stage 1.** It passes on completed deals (that is known, §2.3). The failed
  deals lower the median by an amount nobody has measured. The published muni
  median is 2.8× the 60bp kill line, so a fail would mean failures are both
  common and costly.
- **Stage 2.** It probably passes. The ex-post analogue was a −43.5bp control
  against +148.5bp [S]. Stage 3 is new.
- **Stage 4** probably passes: the kill line of 60bp exceeds 2 × 15bp.
- **Stages 5 and 6 are where it most likely stops.**
  - **For scale only:** the published muni clustered t of 2.41 over about 13
    years corresponds to a sleeve Sharpe near 0.67, if the sleeve kept the
    deal-level t. It is in-sample, on survivors, so it overstates.
  - **The Sharpe `_dsr` needs** over T ≈ 3,270 fit sessions (skew 0, kurtosis
    3). T is measured at run time:

    | N | √(2 ln N) | Sharpe needed | P(pass) at a true 0.67 | at a true 0.40 |
    |---:|---:|---:|---:|---:|
    | 1 | 0 | 0.457 | 0.76 | 0.42 |
    | 4 | 1.665 | 0.919 | 0.21 | 0.04 |
    | 5 | 1.794 | 0.955 | 0.18 | 0.03 |
    | **6 (default)** | **1.893** | **0.982** | **0.15** | **0.02** |

  - **D4:** at a true Sharpe of 0.67 over 13 years, P(alpha t ≥ 3.0) ≈ 0.28.
  - **So the likeliest verdicts are a D4 kill on alpha t, or NEITHER**, as in
    E2's draft. **A PASS would be strong evidence, against the odds.**
- **Holdout.** Taking the published per-group signal-to-noise (2.41 ÷ √47 ≈
  0.35) at face value:
  - on the pooled holdout's 18 muni groups, P(sign (a) > 0) ≈ 0.93;
  - on the time holdout alone (3 groups), about 0.73;
  - under no effect, each sign is a coin flip.

  **A holdout fail would be informative. A holdout pass alone would not be.**
- **Borrow.** The break-even fee should land near the 1.99%/yr arithmetic of
  §5.3, lower once failed deals enter. That sits below the universe muni
  acquirers' median first-filing fee of 9.43% [S].
  - **The likeliest real-money reading:** the gross effect is real in munis,
    and **most of it is the price of borrow**.

Being wrong here is fine and is the point.

## 12. What would falsify it once on paper (H11)

Stated now, for an E1 sleeve that passed and was released:

- **Fidelity, per deal.** Each live deal's A, routing reads, broker, entry
  close, exit (conversion or failure) and units must match the declared rule
  run on the same inputs. A difference halts the sleeve as a bug. A missed
  entry (no IBKR session, a late filing read) is logged and counted, **never
  back-filled**.
- **Admission (D7), read 24 months after the sleeve is first armed.** If fewer
  than **3 groups** passed §5.2's routing in that time, the sleeve is shelved
  as D7 (no live breadth), whatever its P&L.
  - 3 is the fewest groups at which a group-clustered t has two degrees of
    freedom. It is a floor, not a tuned value.
  - Every excluded deal's reads are in the log, so the reason is visible.
- **Reversal, after the 10th live deal's exit or at 24 months, whichever is
  first.** Reverse if the mean live per-deal P&L is below the **5th
  percentile of the trial's own 10-deal means**.
  - The P&L is official fills, both legs, measured borrow, and distributions
    from the third P&L line.
  - The percentile is re-measured on the read date by resampling fit and
    holdout groups.
  - **No threshold is written here as a number (H14).**
- **Forced exits.** If recalls or the §5.4 fee rule force out more than half
  of the live deals, the hedge is not holdable at these brokers. **Revert**:
  shelve the sleeve, labelled D2 (borrow), and report.
- **At any time:** revert if the live drawdown exceeds the fit's worst,
  re-measured.

## 13. Data gates (Stage 0; each failure halts before any E1 statistic)

| gate | what | done when |
|---|---|---|
| **DG-E1-1** | CRSP `ret`, `prc`, `cfacpr`, `vol` and the delisting records for every party, control fund and factor ETF. The fit reader (`crsp_events.daily`) refuses 2023+; the holdout reader runs only after the fit-verdict commit | both readers pass their guards; counts reprinted beside §4.2 |
| **DG-E1-2** | EDGAR dates for the name-holdout and time-holdout deals, by `edgar_merger_dates.py` unchanged, with the share dated only by an N-14 (upper bound) printed per set | every deal dated, or counted as undatable and excluded |
| **DG-E1-3** | the failed-deal census and readings (§4.3) | every episode read, every quote re-found |
| **DG-E1-4** | the bridging check (§6.3) and the fill-day quality screen on every fit window. **Holdout windows are checked only when the holdout is opened (stage 8)**, because the check reads `ret` | the convention holds, or the deal is excluded and counted |
| **DG-E1-5** | French factors (`scripts/data/fetch_ff_factors.py`) and MUB, IEF and HYG total returns, vintage recorded; `cef_borrow_history.parquet`'s last date stated | cover 2009-07 → 2024-12-31 |
| **DG-E1-6** | `compute.use_numexpr` off, with an assertion that no P&L is denormal-like. The panel is about 3,500 sessions × several hundred permnos, above pandas' 1,000,000-cell numexpr threshold (`scripts/events/numexpr_fault.py`) | the assertion passes |
| **DG-E1-7** | the two identity checks (§6.4) | check 1 matches to 1e-12; check 2 is printed |

## 14. Trial accounting

- **EVENTS today: 0 trials** (`docs/RESEARCH_STATE.md`, read 2026-10-19).
  **This commit does not move it.**
- **When it moves:** by one, in the commit that records the team lead's
  approval of this draft (decision 10). That is C4's and C5's convention, and
  the wording `/prereg` and this draft's banner use.
- **E1's trial number** is EVENTS' count after that move. The order in which
  the team lead approves the EVENTS drafts sets it, alongside the NAV-tender
  draft (ruled 2026-10-19) and E2's.
- **`docs/RESEARCH_STATE.md` changed in this commit: no.** On approval, the
  same commit must:
  - move EVENTS;
  - record N (decision 1);
  - amend the 2026-10-09 note to say **the 27-name set is consumed by E1 at
    its Stage 1**. After that, H9 has no name comparison set.
- **Zero-trial script:** `scripts/events/e1_prereg_counts.py`, tested in
  `scripts/events/tests/test_e1_prereg_counts.py`. No existing function was
  changed.
- **Trial script (after approval):** `scripts/events/e1_merger_pair.py`. It
  adds `event_hold` and `event_turnover` to `band_frontier.py` visibly, with
  tests, and leaves `evaluate()` untouched.

## 15. Decisions for the team lead

Each has a default, so the draft is complete. Approval approves the defaults
unless a ruling says otherwise.

1. **N for the EVENTS bar.**
   - **Default: N = 6, fixed on approval and shared by every EVENTS trial.** The
     six are plan §3's E1–E4 plus the two EVENTS tests named on 2026-10-19 (NAV
     tenders; the reconstructed merger arbitrage). The Sharpe needed is 0.982.
   - Alternatives: N = 4, E2's draft default (0.919); the running count (N = 1
     if E1 runs first, 0.457).
2. **The headline segment.**
   - **Default: muni**, labelled as chosen after the by-segment table; the
     other segments reported.
   - Alternative: all segments, the plan's E1. Its published t of 1.93 is
     already under the kill line.
3. **The holdouts.**
   - **Default:** the name holdout (2010–22 deals on `cef_universe.csv` names,
     never priced) and the CRSP time holdout (2023–24), pooled for stage 8 and
     opened once after the fit verdict. **This consumes the 27-name set at
     Stage 1.**
   - Alternatives:
     - the time holdout only. It keeps the 27 for another test, but leaves a
       muni holdout of 5 deals in 3 groups;
     - also price a 2025–26 block from Alpaca bars, corporate actions and
       EDGAR. That needs a new data gate, and two sources agreeing on ratios
       and distributions.
4. **Deals on the book's own names** (a frozen-spec name on either side).
   - **Default: excluded from the trial and from live; reported only.**
   - Alternative: include them in the trial, and net them against the book
     live. That adds 9 muni deals in 2 groups (MHD and MQY, 2021), and needs a
     cross-broker same-symbol rule.
5. **The hedge route and the fee cap.**
   - **Default:**
     - Alpaca if the acquirer is `shortable` and `easy_to_borrow`; else IBKR
       at a fee ≤ f_max = ½ × the fit's break-even (§5.3), frozen at the fit
       verdict; else no trade;
     - close both legs on a recall, or after 5 consecutive IBKR reads above
       2 × f_max.
   - Alternatives:
     - f_max = the full break-even, which admits more deals and keeps no
       margin;
     - a fixed cap of the team lead's choosing;
     - no fee exit.
6. **Failed deals.**
   - **Default: included.** Exit at the close after the failure filing; an
     unread episode halts Stage 0.
   - Alternative: completed deals only, the published sample. That keeps a
     known survivorship bias.
7. **The holdout rule.**
   - **Default: three signs all > 0**: the deal mean, the sleeve mean, and
     treatment minus control 1.
   - Alternative: a one-sided t ≥ 1.645 on the deal mean. Its power is about
     0.4 at the published effect.
8. **The D4 factor set.**
   - **Default:** French six plus MUB, IEF and HYG, with Dimson-summed betas.
   - Alternative: the French six alone, E2's set.
9. **Where a passing sleeve would run.**
   - **Default:** Alpaca-routed pairs inside the CEF account. IBKR-routed
     pairs in the IBKR account, under its own gross cap (`max_gross_stress`
     applied to that account's equity).
   - Alternative: every E1 pair at IBKR. That gives one broker per sleeve and
     simpler reconciliation, but pays IBKR's commissions and short-proceeds
     terms on pairs Alpaca could hold.
   - Whether the IBKR side starts on paper or live is [U] here: IBKR paper
     needs a funded live account [S: B7].
10. **When the counter moves.**
    - **Default:** in the commit that records approval.
    - Alternative: one commit before Stage 1 begins (the XASSET convention).
