# RESEARCH STATE — the research ledger

> **FROZEN AS HISTORY, 2026-11-09** (team lead, `docs/SYSTEM.md` §5, "Team lead, 2026-11-09";
> `docs/MISSION.md`). Pre-registration, the trial counters and their deflated-Sharpe bars, the
> holdout ceremony and the D-code gates no longer apply to research. **The counter table below
> stays at its 2026-11-09 values and does not move again**; `python3 -m ops.orient` still prints
> it, as history. New work is logged in `results/IDEA_LEDGER.md`, which also carries a one-line
> backfill of every row here, re-read under the new rules. Nothing below is rewritten: it is
> the evidence behind that backfill, and the ACTIVE rows still describe the sleeves on paper.

> **Citations written `pre-clean-slate:<path>`** name files deleted in the
> 2026-09-28 clean slate. Read one with `git show pre-clean-slate:<path>`;
> `docs/HISTORY.md` explains. They are provenance, not current state.

**What is canonical here:** the trial-counter table, the D1–D7 verdict legend,
and the KILLED, WATCH, ACTIVE and CLOSED tables. **Update the counter in the same
commit as any trial**, never at the end of a session. `python3 -m ops.orient`
(TRIALS) parses the counter table's bold rows; keep that shape. **Each counter row
is kept by one lane, and moves only in the commit that records the team lead's
approval** (from 2026-10-22; which lane keeps which row: `docs/TEAM.md` §1 and §4).

**What is not here:** live state, which is `python3 -m ops.orient`; what the book
is and how it runs, which is `docs/SYSTEM.md`; and narrative. The dated research
write-ups that used to follow these tables — the 2026-07-31 deployment, audit,
cost-model audit, queue, data inventory, open questions and CEF v1–v3 history,
and the W14 Part A and G6 write-ups — are in the snapshot at git tag `pre-clean-slate`
`pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md`, taken 2026-09-14 at `92734a4`.

---

Trial budgeting (per user decision 2026-07-31): the deflated-Sharpe bar applies
WITHIN a data source. Each genuinely new source gets its own counter; the legacy
counter (156) covers all ETF-price/PD work done to date.

| counter | source | trials used |
|---|---|---|
| LEGACY | ETF prices + HYG/JNK PD + TRACE fallen-angel | 162 |
| NPORT | SEC N-PORT holdings history 2019+ | 1 |
| BREADTH | 45-instrument extended universe | 4 |
| DISP | PD dispersion / staleness decomposition | 3 |
| DEALER | NY Fed primary dealer inventory | 1 |
| MBS | mortgage prepayment staleness | 0 |
| **CEF** | **credit closed-end fund discounts** | **55** |
| **GAMMA** | **options / volatility sleeve (NEW SOURCE 2026-09-08)** | **0** |
| POSITIONING | FINRA short interest + daily short volume | 1 |
| **EVENTS** | **corporate actions from EDGAR/CRSP: CEF/BDC mergers, CEF IPOs, convertible issuance, term/tender events (NEW SOURCE 2026-10-09)** | **3** |
| **XASSET** | **cross-asset ETF/futures slate, declared up front (NEW SOURCE 2026-10-09); from 2026-10-22 also single-name equities, each slate declared up front** | **4** |
| **MACRO** | **fixed income: macro events, credit events and fixed-income instruments, as overlays on the CEF book, sleeves or hedges (NEW SOURCE 2026-10-22; widened 2026-10-26)** | **0** |
> **2026-10-22: MACRO opened at 0** (team lead, `docs/SYSTEM.md` §5, "Team lead,
> 2026-10-22, later: the lanes revised"). Opening a counter spends no trial. A
> **running count**, like EVENTS: each approved trial adds one and the bar is
> √(2 ln N). It holds every FICC event-driven signal (macro and thematic events),
> **whether an overlay on the CEF book or its own sleeve**. For this lane that sets
> aside 2026-10-09's "changes to the live CEF book stay on CEF". The same ruling
> puts single-name equities on XASSET, with each slate declared up front as before.
>
> **2026-10-26: MACRO widened to all of fixed income** (team lead, `docs/SYSTEM.md`
> §5, "Team lead, 2026-10-26"): macro events, credit events and fixed-income
> instruments, on this one running count. The counter does not move. The PM's
> EVENTS rows and the S3 row on WATCH stay where they are. Whether trial C2 (macro
> observables per fund group, planned on CEF) moves here is still open.
>
> **2026-10-19: EVENTS moves 0 → 2** (team lead; this commit records both approvals):
> - **EVENTS trial 1 is E1**, `results/events/PREREG_E1_MERGER_PAIR_2026-10-19.md`:
>   the NAV-for-NAV CEF merger pair, acquirer shorted at Alpaca or IBKR.
>   Amendment 1 (team lead, before any return): borrow fees are ignored and the
>   trial is judged on P&L, with borrow in its own labelled column.
> - **EVENTS trial 2 is NAV tenders**, `results/events/PREREG_NAV_TENDER_2026-10-19.md`:
>   tender participation, ETF-hedged, on all twelve defaults.
>   **2026-10-20: KILLED, D2, at stage 3** (`results/events/NAV_TENDER_RESULT_2026-10-20.md`;
>   `python3 scripts/events/nav_tender_trial.py fit`). After Stage 0 and 73 signed rulings,
>   104 events (96 groups) traded. Gross +1.08% per event (cluster t 2.80), above the placebo
>   p95; net at 15bp +0.59% (t 1.53 < 2.0). Sleeve gross Sharpe 0.450, net 0.381 / 0.244 /
>   0.037 at 5 / 15 / 30bp (no flip). D4 fails (alpha t 1.92, MUNI β 0.17); `_dsr` 0.39 at
>   N = 6. **The holdout was opened once after the verdict's commit and halted at its own
>   20% gate** (14 of 42 unread); no 2023–24 return was read. EVENTS stays 2.
> - **Both are judged at N = 6, bar √(2 ln 6) = 1.893,** fixed on approval and shared
>   by every EVENTS trial (E2's unapproved draft moves from N = 4 to 6).
> - **E1 consumes the 27-name set at its Stage 1** (decision 3's default). The
>   NAV-tender trial excludes all 44 universe funds and does not need it.
> - **2026-10-19: E1 Stage 0 HALTED** (`results/events/E1_STAGE0_2026-10-19.md`;
>   `python3 scripts/events/e1_merger_pair.py stage0`). DG-E1-1, -2 and -3 fail and
>   DG-E1-4 and -5 cannot complete:
>   - the 64 holdout deals are undated (299 EDGAR documents are not cached);
>   - 273 candidate failed-deal episodes are unread;
>   - 9 control-2 pool funds have no cached CRSP rows.
>
>   Each needs the team lead's credentialed fetch, or decision 6's alternative. Both identity
>   checks pass. **No E1 statistic was computed, the 27-name set is not consumed, no holdout
>   was opened, and EVENTS stays 2.**
>
> **2026-10-27: EVENTS moves 2 → 3** (team lead; this commit records the approval):
> - **EVENTS trial 3 is the post-ex-date drift, part (b)**, `results/events/PREREG_EXDATE_DRIFT_2026-10-26.md`:
>   a short at the ex-date close, covered at the +3 close, peer-hedged (H-E), on the 17 credit CEFs.
>   Approved with all 17 recommended answers in its §14.
> - **Judged at N = 7, bar √(2 ln 7) = 1.973** (decision 4). The N = 6 fixed on 2026-10-19 covered six named
>   tests, and this is not one of them. E1, NAV tenders and E2's draft keep N = 6.
> - **Part (a)**, the band's buys deferred around ex-dates, is **withdrawn on power before any data step**
>   (decision 3; expected t 0.80). It spends no trial, and CEF stays 52.
> - **Clean set:** the 17, 2023-01-01 → the last panel date, opened once (decision 5). C4's families in 2023+
>   are not computed (decision 10). Gross P&L decides; the 5/15/30bp grid and borrow sit beside it (decision 17).
> - **Stage 0 comes first**: the distribution refresh and second source (DG-X1), and declaration and record
>   dates (DG-X2/X3). No 2023+ return is computed until Stage 0 is clean.
> - **2026-10-27, Stage 0 run: HALTED** (`results/events/EXDRIFT_STAGE0_2026-10-27.md`; no counter moves). DG-X7's
>   identity gate passes (r6 and H-E's sd reproduce on the fit). DG-X1's second source, DG-X2 and DG-X3 wait on the
>   team lead's Alpaca run; DG-X4, -X5 and -X6 wait on rulings of 587 flags; k is not yet formed. No 2023+ return read.
> - **2026-10-28, Stage 0 re-run on the team lead's Alpaca fetch: HALTED.** DG-X3 passes. DG-X1 is flagged (32 BIT
>   amounts; every ex-date confirmed). **DG-X2 fails: Alpaca's announcement `declaration_date` is derived from the record
>   date, not a declaration** (PIMCO's own release contradicts it). The test cannot open until a declaration source is
>   ruled. 657 flags; the proposal is `results/events/exdrift/EXDRIFT_STAGE0_RULINGS_PROPOSAL_2026-10-28.md`. No counter
>   moves; no 2023+ return read.
> - **2026-10-28, later: Stage 0 CLEAR; k committed; the test set NOT opened.** The team lead accepted every recommended
>   ruling and ruled declarations from the sponsors' own releases (unfound = excluded and counted). 195 releases cover
>   PIMCO, DoubleLine and AllianceBernstein fully and BlackRock but for 2 events. Nuveen gives 42 of 226, because it stopped
>   declaring by press release in 2019, so 186 events are excluded. 545 events are eligible as ruled. `fit-k`: k = 0.1648,
>   cap binds on 0 rows. `open` waits on French's 202610 vintage (the X6 ruling) and the team lead's review. No counter moves.
> - **2026-10-28, evening:** Nuveen 2023–24 declarations recovered from CRSP `dclrdt`, 86 events, provisional on the team
>   lead's live pull. R10 re-ruled KEEP. 649 events are eligible. `open` is written, independently reviewed (all findings
>   fixed) and gated. Rehearsed on FIT 2021–22 it gives KILL D4 (alpha t 2.90; MUNI and TERM betas −0.41/−0.39 at
>   target). Power at 649 events: P(t ≥ 2) 0.91, P(bar) 0.43 at the fit effect. Before `open`: the team lead's R2/bars
>   run, French and IEF/HYG to 2026-10-15, and O1–O4 + GO. No counter moves; no 2023+ return read.
> - **2026-10-28, late: AMENDMENT 1** (team lead), recorded in the pre-registration before any test return. Part (b) hedges
>   each event's MUNI and TERM exposure with MUB and IEF, at frozen fit betas from stage 5's own factor model. It was
>   prompted by the fit rehearsal's D4 failure. Re-rehearsed on fit 2021–22 it still gives KILL D4 (alpha t 2.59; MUNI
>   −0.37, TERM −0.39), and the cap now binds on 41.6% of rows. O1–O4 are ruled, with the window ending 2026-10-09: 649
>   events, T 946. N stays 7; EVENTS stays 3.
> - **2026-10-28, night: D4 on the full fit window** (fit only, descriptive, `exdrift_fit_d4_full_window.csv`). The original
>   design PASSES D4 over 2007-09 → 2022: alpha t 4.57, MUNI −0.07, TERM −0.03. The −0.4 rate betas are a 2021–22 feature
>   (a smaller −0.19/−0.15 in 2010–15). Yet every era taken alone fails D4: alpha in 2005–09, rates in 2010–15 and 2021–22,
>   HY +0.21 in 2016–20. Amendment 1, in-sample, lowers alpha t to 3.97 and the deflated Sharpe to 0.93. No counter moves.
> - **2026-10-28, final: amendment 1 WITHDRAWN** (team lead). `open` runs the original design, with the window ending
>   2026-10-09. Known risk: every 3.8-year fit era failed D4 alone. `open` is not run. It waits on the team lead's
>   `run_exdrift_r2.sh`, a Stage-0 re-run that re-records the input hashes, French's 202610 vintage, and the GO row.
> - **2026-10-28, after the team lead's R2 run:** the live CRSP pull matches the provisional staging exactly. O4 passes
>   on all 24 fills. Stage 0 is re-run CLEAR with the input hashes recorded: 649 events. `open` waits only on French's
>   202610 vintage and the GO row.
>
> **2026-11-08: a verdict is a reading of one test, not the end of an idea** (team lead, `docs/SYSTEM.md` §5,
> 2026-11-08). For research agents and the loop, nothing in the KILLED tables is banned. An idea can return if the agent
> says what is different, and one that failed on a data error must deal with that error first. Every re-test and every
> holdout look is a counted trial. Where the note below says "never re-test", read it as history.
>
> **2026-10-27: evidence outcomes beside D-codes** (team lead, `docs/SYSTEM.md` §5,
> 2026-10-27; `results/research/DESK_METHOD_2026-10-27.md`). From today every
> verdict records what the test could show, beside the gate that fired:
> PRESENT (the interval excludes zero), ABSENT (it excludes every meaningful
> effect), or INCONCLUSIVE (`scripts/research/inference.py::read_result`). Only
> ABSENT justifies "never re-test without new data". Rows below are not
> rewritten; the relabels are recorded here:
> - **C5 (CEF 51)**: D1 stands as the gate that fired. Evidence: the gain is
>   **PRESENT** (fit t 2.82, holdout t 4.66 [S]); the lagged-placebo split is
>   **INCONCLUSIVE** (t −0.56, MDE about the whole gain).
> - **E1 (EVENTS 1)**: D4 stands as the gate that fired. Evidence: the alpha is
>   **INCONCLUSIVE** (alpha t 1.90, every |Σβ| ≤ 0.021 [V]), so it is a power
>   failure, not a risk premium in costume.
> - **2026-10-28, re-opens closed at the power gate (UNDERPOWERED, no data pulled):** X3 hedged
>   against TERM, G2 and MA-HZ (`docs/SYSTEM.md` §5, 2026-10-28). Re-open them only with a
>   design that changes their power.
> - **XASSET-X1**: D1 stands as the gate. Evidence: **spanned** by TSMOM^FI
>   (alpha t 0.65 [S]), i.e. D4 in substance.

> **2026-10-09: EVENTS and XASSET opened at 0** (team lead, `docs/SYSTEM.md` §5,
> 2026-10-09). Opening a counter spends no trial. **XASSET is a declared slate**: its
> five tests (`results/cef/RESEARCH_PLAN_2026-10-09.md` §3) are listed before any runs,
> and each is judged against the bar for the slate's full size, √(2 ln 5) = 1.79, not
> the running count. Options stay on GAMMA. Changes to the live CEF book stay on CEF.
> **The 27-name holdout is opened for event trades.** It is consumed by the first
> pre-registered test that computes returns on a `cef_universe.csv` name. The
> 2023-01-01 time holdout stays sealed.
> *Corrected 2026-11-01 (Q7 of CEF trial 53): for the core book its 2023+ has been seen; see
> the 2026-11-01 CEF note below.*

> **2026-10-13: the GAMMA holdout was touched before it was opened.** Recorded
> so that whoever opens it knows what has already been seen. The holdout is
> 2023+ TLT data for the options sleeve: `docs/SYSTEM.md` §5, team lead
> 2026-10-09, narrowed on 2026-10-12 to "spreads and costs from 2023+ may be
> used; return-based statistics stay sealed".
>
> Gate G2 (`results/gamma/G2_GATE_FREE_DATA_2026-10-12.md`, zero trials)
> touched it on 2026-10-12, in two ways:
>
> 1. Its G2(a) headline included one 21-session realised-vol window (IV date
>    2022-12-27) that ran on January 2023 TLT returns.
> 2. It printed and read `scripts/gamma/book_vs_shortvol.py`'s labelled 2023+
>    block of book-versus-short-variance correlations. That script's second
>    method also ran one window to 2023-01-31.
>
> An independent review caught both on 2026-10-13. The effect on G2 is
> negligible: on the strict window the upper bound nets −18.9 %² (t −1.12),
> against −18.4 (t −1.09). Both scripts now refuse 2023 returns, and tests pin
> it.
>
> Earlier, before the 2026-10-12 narrowing, `results/gamma/REPRO_TLT_VRP_2026-10-11.md`
> quoted labelled 2023+ IV−RV and book-correlation figures as "description
> only". `scripts/gamma/vrp_summary.py` still prints them, and its 2004–22 row
> also runs its last window into January 2023; neither was changed here.
> **GAMMA stays at 0.**

> **2026-11-02: trial 53's C4 value applied, counter unchanged at 53** (the approval moved it):
> `ops/specs/c4_families.frozen.json` `c4_families.v1.20261029` → `c4_families.v2.20261101`,
> `sizing_multiplier` 1.27, by the committed patch
> (`results/cef/prereg_voltarget/c4_families_sizing_multiplier_2026-11-01.patch`), on branch
> `c4-rel`, before C4's dry sessions, so that they rehearse the book C4 arms at ("C4 at its
> arming, already at ×1.27"). C4 stays unarmed. Revert: local tag `spec-c4_families.v1.20261029`.

> **2026-11-03: CEF 54 → 55** (team lead, 2026-11-03, about 09:25 ET; this commit records the approval):
> - **Trial 55 is the thin-session rule `trade_eligible`, floor 4, PAPER ONLY.**
>   - Note: `results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md`, drafted as
>     `PREREG_DRAFT_THIN_TRADE_ELIGIBLE_2026-11-03.md`.
>   - On a session with fewer than `min_names` but at least 4 eligible names, the core builds its book on
>     the eligible names instead of closing it.
>   - Keys `below_min_names: "trade_eligible"` and `below_min_names_floor: 4`. With them absent the book is
>     today's flatten book, byte-identical, which the implementation must prove.
>   - Never on a live-money account. Guarded by the paper-only client, the sleeve's refusal of the key
>     without a paper declaration, the runner's endpoint check and `docs/SYSTEM.md` §5.
> - **Not shown to be alpha** (`results/backtests/thin-third-rule-2026-11-03/REPORT.md`).
>   - Matched turnover: +2.13pp/yr, t 2.34, INCONCLUSIVE.
>   - The edge rests on PHK and PDI, and 87% of it is PIMCO. Holdout t 0.72.
>   - −2.33pp/yr net of measured 2023+ borrow.
>   - Chosen for paper because paper is scored gross (D19/D20).
>   - The drafting session recommended keeping flatten; the team lead chose approval.
> - **Judged at N = 55, bar √(2 ln 55) = 2.831**, on forward thin episodes only (2023+ is seen).
>   - PRESENT is read only at 5, 9, 13 and 20 episodes, each at the bar's one-sided p / 4 (P 0.03 / 0.22 /
>     0.54 / 0.87 at the fit effect), and is labelled unmatched (H2). It is out of reach for years.
>   - The operative rules are ABSENT (the first two episodes negative, or the mean ≤ 0 from the third) and
>     the stops K0–K3.
>   - K1–K3 are re-measured on the read date by `results/cef/prereg_thin_te4/compose.py --stamp <date>`.
> - **K0, on the account, acts in code.**
>   - A reduced build is sent only if the decide's drawdown record reads OK, and HALVE or KILL during an
>     open episode kills the trial.
>   - `drawdown.py`'s status may only restrict (flatten or hold), never size up or unlock a send, and
>     UNMEASURED flattens. A test pins this.
> - **Conditions** (the team lead took every recommended answer, §10 Q1–Q17):
>   - a dropped short flattens a reduced session;
>   - a "core ex-te4" series sits beside every core P&L report;
>   - the core's kill rule (a) is also read on full sessions alone;
>   - the K0–K3 report lines and the revert spec ship in the activation release;
>   - activation only after the core's 60-session review is graded, and after prod's counts of UNMEASURED
>     decides and missing-NAV holds (Q6, Q10).
> - **Trial 53 composes with it** (pre-registration §7, the owner's terms in its "Approval" section).
>   - m 1.30 applies on reduced sessions, with K0. Zero-edge P(HALVE) / P(KILL) at ×1.30 under te4 is
>     23.2% / 3.28%, against 16.7% / 1.69% at ×1.15.
>   - R1–R3 are read on full sessions only (Q3 (a)). That amendment to trial 53's stops is recorded in
>     `results/cef/PREREG_VOLTARGET_2026-10-30.md` in the activation commit, not before.
> - **This commit changes no spec and no live code.** The key stays absent until the activation commit.
> - **Not the nextgen shadow "CEF trial 55" (GN-N2).** The group-cap docstrings in
>   `src/deploy/sleeves/cef_discount.py` still cite that label. It is the nextgen branch's numbering (53–56),
>   which the 2026-09-28 ruling made shadow research (the CEF 48 → 50 note below). The implementation PR
>   relabels those docstrings.

> **2026-11-03: CEF moves 53 → 54** (team lead, 2026-11-03; this commit records the approval).
> **CEF trial 54 is C4-LEVEL**, `results/cef/PREREG_C4_LEVEL_2026-11-02.md`: C4's discount level against
> family peers, blended at equal risk with C4's z inside the C4 account (frozen key `level_signal` in C4's
> spec, absent = v4 byte for byte). Gate 0 (survivorship with dead funds) was cleared by the team lead
> **post-data** (b_D/b_A 1.36, CI 0.80–2.13; coverage 0.642 against an 80% reference; §4b, commit 389f61a,
> reproduced byte for byte). That is a judgment on seen data, not a pre-registered pass. The pass rule (§6.2)
> is unchanged: P1 alpha NW t ≥ √(2 ln 54) = 2.825 on the fit, the deflated-Sharpe bars at declared N = 54,
> NC1, the placebo, D4, P3, then the 2023–26 holdout's sign, opened once.

> **2026-11-02: CEF trial 53 AMENDMENT 1 — the counter does not move; CEF stays 53** (team lead,
> 2026-11-02, about 22:00 ET; `results/cef/PREREG_VOLTARGET_2026-10-30.md` §0.B). The core's
> `sizing_multiplier` goes 1.13 → **1.30** (spec `cef_discount.v9.20261102`), and C4's goes 1.27 → **1.26**
> (`c4_families.v4.20261102`, before C4 arms). The core's stops are recalibrated on the live thin-day
> rule's trading sessions: R1 10.14%, R2 −3.06%, R3 12.07%.
> - **Why.** The multipliers were derived on the harness's HOLD book, but the live core FLATTENS on
>   thin sessions. On the sessions it trades, the same rule gives ×1.30. Taken literally, on
>   calendar vol, it gives ×1.96, which the flat sessions inflate.
> - **Evidence:** `results/cef/prereg_voltarget/FLATTEN_REMEASURE_2026-11-02.md`. It is fit only, and
>   no 2023+ return was computed.
> - **It is not a trial.** The same hypothesis and rule are fed a corrected input, and no return
>   statistic decided it.
> - **The bar stays at N = 53** (2.818).
>
> **2026-11-01: CEF 52 → 53** (team lead; this commit records the approval):
> - **Trial 53 is the vol-target raise**, `results/cef/PREREG_VOLTARGET_2026-10-30.md`:
>   each account sized at its per-account equal-risk multiplier through a new frozen key,
>   `sizing_multiplier` (absent = today). `vol_target_annual` stays 0.06.
> - **Approved at the milder values, core ×1.13 and C4 ×1.27, at a 5.25% combined target**: the
>   2026-10-29 rule's term (d), derived 1.1357 / 1.2712 on C4's spec book, rounded down. These are not
>   the draft's ×1.24 / ×1.39 at 5.75%. All seven open questions take the recommended answers (§0.A of
>   the pre-registration). The answer to Q2 needs no override, because at these values term (d) holds.
> - **Judged at N = 53, bar √(2 ln 53) = 2.818.** The raise claims no Sharpe, so the bar judges
>   nothing here. It is judged by its stops (R1–R3, §6.2), read per account on the P&L of record and
>   acted on by the team lead. Verdicts are recorded as H-VT PRESENT / ABSENT / INCONCLUSIVE.
> - **Evidence:** forward paper only (Q7 below). No 2023+ return was computed. The core starts at its
>   next release; C4 starts at its arming.
> - **Q7, correction (2026-11-01):** the 2026-10-09 note above says "the 2023-01-01 time holdout stays
>   sealed". **For the core book that is no longer true.**
>   - its 2024-01-01 → 2026-07-30 returns were opened on 2026-07-31
>     (`pre-clean-slate:results/cef/HOLDOUT_OPENED.json`, FAIL on net, for z 63);
>   - the v7 pre-registration then computed the deployed book over 2013-06-14 → 2026-09-21
>     (`results/cef/PREREG_ALPACA_V7_2026-09-28.md` §5).
>
>   Treat the core's 2023+ as seen. The rule still holds for any book whose 2023+ has not been
>   computed. C4's was opened on 2026-10-18 (its row below).

> **2026-10-14: CEF 50 → 52** (team lead's approval of two pre-registrations;
> each counted in the commit that records its approval):
> - **Trial 51 is C5**, `results/cef/PREREG_C5_OPEN_AUCTION_2026-10-13.md`:
>   the t+1 opening-auction fill.
> - **Trial 52 is C4**, `results/cef/PREREG_C4_FAMILIES_2026-10-13.md`: the
>   discount z-score pooled over five CEF families.
> - **Both are judged at N = 52, bar √(2 ln 52) = 2.811.**
> - **Trial 51 (C5): KILLED, D1, at the fit (2026-10-14).** The open fill's gain G
>   (WIDE) is +293bp/yr, SR 1.16, t 2.82. The lagged-signal placebo earns more
>   (+351bp/yr), so stage 2b kills it. It also fails D4 (MUB summed β −0.22) and
>   the bar (`_dsr` 0.61 at N = 52). **The holdout (report-only) HALTED on D-5 before
>   its gain was formed (2026-10-15):** material trades on name-days with no panel
>   close, 0.19% (WIDE) and 0.29% (deployed) against a 0.1% halt. It awaits the team
>   lead, and the kill stands either way (`results/cef/C5_RESULT_2026-10-14.md`).
>   **2026-10-19: opened once under the team lead's D-5 repair rule.** A D-5
>   name-day takes the NYSE closing print where it and CEFConnect's close agree.
>   This is a deviation after the halt, recorded in the pre-registration. Residual
>   D-5 is 0, and no other class fires. **Holdout G (WIDE): +313.6bp/yr, SR 2.12,
>   NW t 4.66**, the same at every grid point (one turnover). It has the fit's
>   sign, so stage 8 passes, but it cannot rescue: **C5 stays KILLED (D1).** The
>   counter does not move.
>
> **2026-10-14: the XASSET slate is declared at N = 4**
> (`results/xasset/PREREG_XASSET_SLATE_2026-10-12.md`, revision 3, approved):
> - **X5 was withdrawn before any data step,** on power forecast from the
>   draft's own expected Sharpes. No return had been seen.
> - **Each of X1–X4 is judged at the slate bar √(2 ln 4) = 1.665**, not the
>   2026-10-09 note's 1.79.
> - **XASSET stays at 0 until a test's Stage 0b begins.** The counter moves
>   per test (revision 3).
>
> **2026-10-14, later: XASSET Stage 0a recorded; no test entered Stage 0b.**
> - **Stage 0a is in** `results/xasset/STAGE0A_2026-10-14.md`. The spec pin
>   matches, and DG1's build gates, DG2, DG3 and Q1 pass.
> - **DG1's "rebuild unchanged in every existing column" cannot hold
>   bitwise.** The yfinance leg's Adj Close return differs by up to 0.0075bp
>   between any two builds.
> - **That question, and one about the X1/X4 placebo, are with the team lead**
>   (`results/xasset/XASSET_RESULTS_2026-10-14.md`).
> - **XASSET stays 0. N stays 4.**
>
> **2026-10-14: XASSET counter moves, one commit before each test's Stage 0b**
> (team lead's rulings recorded first, in the prereg's amendment block):
> - XASSET 0 → 1: **X1's Stage 0b begins** (trial 1 of N = 4).
> - XASSET 1 → 2: **X3's Stage 0b begins** (trial 2 of N = 4).
> - XASSET 2 → 3: **X2's Stage 0b begins** (trial 3 of N = 4).
> - XASSET 3 → 4: **X4's Stage 0b begins** (trial 4 of N = 4).
>
> **2026-10-14/15: XASSET slate outcome: all four FAIL; no sleeve**
> (`results/xasset/XASSET_RESULTS_2026-10-14.md`):
> - X1: **D1**.
> - X2: **D1**.
> - X3: **D4**, and D2 at 15bp.
> - X4: **D4**, the historical-mean rule.
>
> All four holdouts were opened once. **XASSET is at 4 = N. The slate is closed.**

> **2026-10-29: C4's re-derived `max_gross_stress` (1.90, `ops/specs/c4_families.frozen.json`) spends no CEF trial; CEF stays 52** (team lead, answered interactively): it applies the frozen §3b rule with no performance test, unlike trial 50 below, where the core's adoption was counted.

> **2026-09-28: CEF 48 → 50** (`results/cef/PREREG_ALPACA_V7_2026-09-28.md`). Trial 49:
> the universe change 17 → 13 (NAD, NEA, NVG, NZF not shortable on Alpaca). Trial
> 50: `max_gross_stress` adopted and re-derived for the Alpaca account. The team lead
> ruled on 2026-09-28 that this counter (48 on `main`), not the nextgen branch's
> 53–56, is authoritative; the nextgen trials were shadow research.

> **⚠ CORRECTED 2026-09-09.** The CEF row read **18** until today, which was its
> value on 2026-07-31 when this file was last updated. It missed the +29 that
> `pre-clean-slate:results/cef/ESTIMATOR_NOTE.md` recorded that same session (9 distribution-cut
> + 16 Kalman sweeps + 4 window control) and the band trial that followed.
> **48 is correct**, and it is the figure `SYSTEM_AND_STRATEGY.md` §9 (git tag `pre-clean-slate`),
> `PREREG_BAND_2026-09-06.md` and `DUST_ORDERS_2026-09.md` have been using.
> A second counter, **GAMMA**, was opened by the 2026-09-08 standing decisions
> for the options programme (its prompts, deleted 2026-09-28, are under `pre-clean-slate:_archive/docs/prompts/gamma/`); it has its own
> deflated-Sharpe bar and the combined book is judged on the joint record.
> **This table is the canonical record — update it in the same commit as any
> trial, not at the end of a session.**

---

## Verdict legend — D1–D7

> Moved verbatim on 2026-09-13 from §2.2 of `RESEARCH_AND_METHODOLOGY.md`
> (git tag `pre-clean-slate`: `pre-clean-slate:_archive/docs/RESEARCH_AND_METHODOLOGY.md`, dated 2026-07-31).
> Every verdict in the tables below uses these codes. D1's last column was amended on 2026-11-08 (`docs/SYSTEM.md` §5):
> a code names the gate that fired, and does not end the idea.

"It didn't work" is not a diagnosis and cannot be acted on. We classify every
failure into one of seven types, because the correct response is different for
each, and the wrong response wastes weeks.

| code | what happened | what it means | what to do |
|---|---|---|---|
| **D1** | No edge even *before* trading costs | The effect does not appear | Check the data and the reasoning, and look for a missing angle. Set it aside, with reasons, if none remains |
| **D2** | Edge exists but costs eat it | A trading problem, not an idea problem | Trade less often, in bigger, better-chosen bets |
| **D3** | Great in old data, bad in new | Either overfitted, or the world changed | Check if the *mechanism* still holds. If yes, it's a regime shift. If no, we fooled ourselves |
| **D4** | Good numbers, but it's just market exposure | A risk premium wearing a costume | Demote it. It is not skill and must never be counted as skill |
| **D5** | Everything passes, Sharpe 0.3–0.6 | **This is not a failure. This is inventory** | Keep it. Several mediocre-but-different strategies beat one good one |
| **D6** | Works in one environment, not others | A conditional strategy, correctly identified | Only run it when its environment is present, and size it accordingly |
| **D7** | Fewer than ~250 independent trades | Not a result at all | You cannot conclude anything. Get more instruments, not more history |

D5 deserves emphasis because it is the most expensive mistake available. A
strategy with a Sharpe of 0.5 sounds disappointing. But five *unrelated* strategies
each at 0.5 combine to about 1.1 — because their bad days do not line up. Throwing
away 0.5s while hunting for a 1.5 is how people end up with nothing.

---

## KILLED — CEF construction variants

> Moved verbatim on 2026-09-13 from §7 of `SYSTEM_AND_STRATEGY.md`, written
> 2026-09-06 (git tag `pre-clean-slate`: `pre-clean-slate:_archive/docs/SYSTEM_AND_STRATEGY.md`). Figures are as
> measured then; section references (§1.2, §8.1) are to that document (git tag `pre-clean-slate`).

Each was measured and failed. Rebuilding one is a wasted week.

| idea | verdict |
|---|---|
| **`z_window = 63`** | Chosen on 2005–2023 with the holdout sealed. Opened hours later: **gross 1.75 but net −0.298**. Reverted to 252. *The canonical lesson: picking the argmax of a swept column.* |
| **OU / per-name κ score** | Measured 2026-09-06, **withdrawn**. κ exposure curve is flat below 0 and declining above; live setting is at the top. **Mechanism:** OU stationary variance is $\sigma^2/2\kappa$, so $\sigma^d\propto\sigma/\sqrt\kappa$ — the live z-score **already carries $\kappa^{1/2}$**. Measured slope of $\log\sigma^d$ on $\log\kappa$ = **−0.463** vs theory's −0.500. Multiplying by $(1-\phi^h)$ double-counts. |
| **Signal combination with price reversal** | Optimal combined \|IC\| 0.0748 vs 0.0747 for discount alone = **+0.1%**. Price signal 95% subsumed (weights −0.95/−0.05). |
| **Hard group (muni) neutrality** | Gross Sharpe 0.97 → 0.82. |
| **Sizing up on \|z\|** | Every threshold above zero *lowers* Sharpe: 0.81 → 0.40 → 0.29 → 0.27. |
| **Sizing up on dislocation** | Best in *calm* markets (§1.2). Produced −12.9% at 35.8% vol in 2008. |
| **Distribution data** | Failed twice — as a universe filter (1 of 8 variants beat baseline, chosen after looking at 8) and inside the Kalman (1.60 → 1.28). |
| **Cointegration pairs** | Gross 1.03 → net −0.16; needed 32.8× leverage against a 2× ceiling. |
| **Sequential Σ⁻¹α + band** | At matched turnover gross **1.07 — below plain α's 1.10**. The scalar band destroys what Σ⁻¹ buys. Use the joint objective instead (§8.1). |

**Also do not build:** machine learning (17 names, one feature, IC 0.075 — the
bias-variance trade-off is emphatically against it); regime-switching (the
dispersion-quintile table *is* the regime study, and vol targeting already
exploits it continuously); jump-diffusion (changes sizing, not signal);
Heston/SABR (we trade no derivatives); Almgren-Chriss scheduling (one auction at
<1% participation — there is nothing to schedule).

---

## KILLED so far — may return if the agent says what is different (team lead, 2026-11-08)
| id | hypothesis | cause of death | evidence | date |
|---|---|---|---|---|
| credit_rv | cross-sectional price-residual RV on credit ETFs | **D1** gross edge NEGATIVE before costs (−0.19%/yr) | sealed holdout net SR −1.44, t −2.29 | 2026-07-30 |
| E1 | HYG vs JNK raw premium/discount reversion | **D1→D5 reclassified** see WATCH | OOS SR −6.65 continuous; but band form earns 2.54%/yr→0.05%/yr, i.e. it STOPPED TRADING rather than lost | 2026-07-30 |
| S1-as-specified | per-bond staleness score using cross-issuer price disagreement | **D1** the input carries no information: median disagreement 0.09bp, p99 1.03bp across 1,132 shared bonds — all issuers buy from the SAME vendor | `pre-clean-slate:_archive/results/s1/` (git tag `pre-clean-slate`) | 2026-07-30 |
| S3-wrapper | fallen-angel forced flow expressed via ANGL/FALN vs HYG | **D4** it is a credit-quality risk premium in costume: alpha t 1.98 (need 3.0), HY beta −0.163, IG beta +0.123 (need ≤0.10). Unconditional pair (0.37) BEATS signal-conditioned (0.03–0.24) | `pre-clean-slate:results/s3/angl_expression.csv` | 2026-07-30 |
| single-fund-PD | premium/discount is still tradable in non-industrialised wrappers | **D1** dispersion is REAL and large (EMB 28.6bp, ANGL 23.3bp, viability 6-19x cost) but it is NAV staleness, not dislocation. PD predicts the NAV REVISION at t=15-24, and where it predicts price the sign is POSITIVE (EMB +15.3, LQD +11.7, HYG +10.0 on close->mid) = the ETF correctly LEADING a stale NAV. Trading it fades price discovery. Treasury controls show mid->mid t=-15..-18, a spurious-regression artifact from the shared price term, confirming the raw metric is fragile | `pre-clean-slate:_archive/results/disp/` (git tag `pre-clean-slate`) | 2026-07-31 |
| leadlag | thin wrappers lag liquid ones within an asset class (information diffusion) | **D1** pure non-synchronous trading. Raw effect was huge (mean t by group: IG_long 17.7, HY 12.4, MBS 11.7, EM 11.0, PREF 9.5) but it was measured on (H+L)/2, which is NOT a transactable price. Under executable close-to-close with the repo's T+1 convention the overall mean t goes 5.20 -> **-0.50**, and the Treasury CONTROL (+3.48) scores HIGHER than every credit group but one | `pre-clean-slate:_archive/results/leadlag/leadlag_specs.csv` (git tag `pre-clean-slate`) | 2026-07-31 |
| nport-trace-nav | rebuild daily NAV from N-PORT weights x TRACE transaction prints (mark-vs-TRACE, not mark-vs-mark) | **D7 infeasible** daily TRACE coverage of HYG's N-PORT weight is only 17-30% and DECLINING (26.5% in 2020 -> 17.4% in 2022). The bonds that print on a given day are selected for having news, so a 20%-weight subset cannot stand in for the book. N-PORT itself is sound (136,268 rows, 27 quarterly snapshots/fund, 95.3% CUSIP overlap vs the live iShares file) but is QUARTERLY not monthly, and `fair_val_level` is degenerate (135,850/135,870 corporate bonds are Level 2) | `data/holdings/nport_holdings.parquet` | 2026-07-31 |
| dealer-constraint | primary-dealer corporate inventory predicts credit excess returns (intermediary asset pricing) | **D1** ZERO credit names significant at any horizon 5-63d (best t=1.59, ANGL 42d); UST control shows the SAME magnitude (mean t 0.95-1.50), so even the sign that is there is not credit-specific | `pre-clean-slate:_archive/results/s4/dealer_constraint.csv` (git tag `pre-clean-slate`) | 2026-07-31 |
| pair-reversion | within-class wrapper pairs mean-revert; combine 22 for breadth | **D2 + capacity.** Combination thesis CONFIRMED: mean pairwise correlation +0.027, combined **GROSS Sharpe +1.03**. But (a) costs do NOT diversify while vol does, so the cost drag in Sharpe terms grows ~sqrt(N) and net falls to **-0.16**; (b) combined vol is 0.37%, so reaching the 12% mandate needs **32.8x leverage** against a ~2x Reg T ceiling. Per-pair signal is weak and honest: mean t -1.17 at h=1, 5/22 individually significant (IGLB/VCLT -3.58, SPLB/IGLB -3.20, SPHY/USHY -2.78), UST control +0.12 with 0/3 | `pre-clean-slate:_archive/results/ou/pair_sleeve_v2.csv` (git tag `pre-clean-slate`) | 2026-07-31 |
| short-pressure | crowded credit hedges (FINRA daily short volume) unwind and reverse | **D1** credit mean t 0.28/0.03/-0.20/-0.42 at h=1/3/5/10d, 2/10 names significant at the best horizon; the RATES comparison group scores HIGHER (1.01/0.92/1.05/0.45), so nothing here is credit-specific | `pre-clean-slate:_archive/results/positioning/short_pressure.csv` (git tag `pre-clean-slate`) | 2026-07-31 |
| gamma-timing-C3 | CEF discount stress nowcasts HYG realised vol, so long credit gamma can be timed | **D1 holdout.** In sample it works and is not an artifact: beside C1, β +0.0097 (t +2.42), incremental R² +0.0358, and against forward realised vol with no IV term anywhere β +0.02105 (t +3.95, n 4,851), real mean target at the 100th percentile of 20 shuffled draws. On the 2023–26 holdout the coefficient falls to **24%** of full sample (t +1.69) and on the stated target it is **−0.20**. Separately fatal: no state at any reported threshold has a positive mean target — the best is C3 > 2.0 at −0.0113, i.e. still paying 1.13 vol points. C2 is declared and UNAVAILABLE, not tested | `pre-clean-slate:results/gamma/PREREG_GAMMA_TIMING_2026-09-13.md` | 2026-09-13 |
| C5 (CEF trial 51) | filling the evening's CEF trade at the t+1 OPENING auction earns the session that t's NAV reaches (`results/cef/PREREG_C5_OPEN_AUCTION_2026-10-13.md`) | **D1, artefact control (stage 2b)**: the gain is real, +293bp/yr (SR 1.16, t 2.82, 2016–22 WIDE), but the same open fill on the trade decided a day earlier earns +351bp/yr. It is session drift on the signal's trades, not NAV arrival. Also fails D4 (MUB β −0.22) and `_dsr` (0.61 at N = 52). **Holdout (opened once, 2026-10-19, under the team lead's D-5 repair rule): G +313.6bp/yr, SR 2.12, t 4.66, the fit's sign. It cannot rescue; the kill stands** | `results/cef/C5_RESULT_2026-10-14.md`; `python3 scripts/cef/c5_open_auction.py fit`; `python3 scripts/cef/c5_open_auction.py holdout` (opens once) | 2026-10-14; holdout 2026-10-19 |
| raw-flow-z | ETF creation/redemption z-score predicts returns | **D1** precise zero: 28,025 obs, all \|t\|<0.8; Treasury control equally flat. Informed and forced flow cancel when pooled | `pre-clean-slate:results/s3/flow_regression.csv` | 2026-07-30 |

| EVENTS-2 NAV tenders | buy a CEF after its NAV tender is announced, tender every share, ETF-hedge its beta (`results/events/PREREG_NAV_TENDER_2026-10-19.md`) | **D2 at stage 3**: gross +1.08% per event (t 2.80, 104 events / 96 groups, 2010–22), above the placebo p95 (+0.74%); net at 15bp +0.59% (t 1.53). Sleeve gross Sharpe 0.450, net@15 0.244, net@30 0.037. Also fails D4 (alpha t 1.92, MUNI β 0.17) and `_dsr` (0.39 at N = 6). The payoff is the tender's own (A − B +0.63%, t 3.3), not the announcement drift (+0.45%, t 1.2). Capacity binds: at $1m the median entry is about half a day's volume. Holdout halted at its own 20% unread gate (14 of 42), no return read | `results/events/NAV_TENDER_RESULT_2026-10-20.md`; `python3 scripts/events/nav_tender_trial.py fit` | 2026-10-20 |
| XASSET-X1 | credit and rates trend: MOP time-series momentum on HYG LQD IEF TLT EMB PFF MUB BKLN CWB | **D1**: sized gross Sharpe 0.41, NW t 1.62 < 1.96 (2008-05 to 2022-12, T 3,693). Every later rule fails too. TSH wins net; placebo p95 0.78; alpha t 0.79 with TERM β 0.17; `_dsr` (N = 4) 0.47. Holdout Sharpe −0.39. Spanned by AQR TSMOM^FI (t 5.2) | `results/xasset/trials/x1_fit_2026-10-14.json`; `python3 scripts/xasset/x1_credit_trend.py` | 2026-10-14 |
| XASSET-X2 | front-run pension and balanced-fund rebalancing (HMM Threshold + Calendar), SPY vs IEF | **D1**: Sharpe 0.33, NW t 1.59 (2002-09 to 2022-12, T 5,118). The rates control {BIL: +w, SHY: −w} scores 0.18, at least ½ of X2's 0.33, so stage 2 fails as well. 57 turns a year; net −1.09 at 15bp. Holdout 0.25 | `results/xasset/trials/x2_fit_2026-10-14.json`; `python3 scripts/xasset/x2_rebalancing.py` | 2026-10-14 |
| XASSET-X3 | month-end Treasury extension (Hartley & Schwarz): long IEF over the last 3 sessions | **D4**: the effect is real, but it is term premium in a part-time wrapper. Sharpe 1.04, NW t 4.94; IEF on other days −0.05; placebo passes; `_dsr` 0.999; alpha t 4.54 / 4.30. But TERM β is 0.34 / 0.33 (> 0.10), as PREREG §6 stated in advance. **Also D2**: 58 turns a year, net −0.42 at 15bp. Holdout 0.59. A TERM-hedged X3 is a new trial, if wanted | `results/xasset/trials/x3_fit_2026-10-14.json`; `python3 scripts/xasset/x3_month_end.py` | 2026-10-14 |
| XASSET-X4 | multi-asset trend: MOP TSMOM on X1's nine plus SPY EFA EEM GLD DBC | **D4, the historical-mean rule**: Sharpe 0.45, NW t 1.964 (stage 1 passes, barely). The inception-to-date sign (TSH) beats it net at 5, 15 and 30bp. The placebo (p95 0.77) and D4 (alpha t 1.00) would also fail; `_dsr` 0.58. Holdout 0.19. Spanned by AQR TSMOM (t 5.3) | `results/xasset/trials/x4_fit_2026-10-14.json`; `python3 scripts/xasset/x4_multi_trend.py` | 2026-10-14 |
---

## WATCH — passed mechanism, failed magnitude
| id | hypothesis | gross edge | what it needs |
|---|---|---|---|
| MA-HZ | merger arbitrage on event-time completion hazard: long cash deals in their high-hazard weeks, short in their low-hazard weeks (Giglio & Shue 2014; `results/events/MERGER_ARB_V2_2026-10-19.md`) | **Mechanism holds, cost marginal** (zero trials, 2026-10-20): the hump HOLDS on unseen 2001–09 deals (High-week hazard 0.069 vs Low-1 0.025); the measured half-spread drag (202–233bp/yr, a lower bound) sits between the decayed (174) and late-sample (276) gross; P(D4 t ≥ 3) ≈ 1–10% | **WATCH by the team lead, 2026-10-20: no trial.** Revisit only if execution cost falls well below the decayed gross, or a longer clean sample raises D4's power |
| S3-forced-flow | IG→HY forced index deletion causes temporary price pressure | **−424bp trough, t −17.5, 82–85% reversal with dropouts carried flat**; sell imbalance 0.000→0.060 at the flip; Test 3 monotone (quiet −22% recovery = information, crisis 98% = pressure) | **D6 conditional sleeve.** Crisis regime (>400 migrations/mo) fired 4× in 273 months. Needs (a) a non-wrapper expression — 104 migrating bonds vs 350 holdings is 5× noise, (b) regime gate, (c) sized to fraction of time on. Negatively correlated with everything → marginal portfolio value >> standalone Sharpe |
| E1-band | raw PD ±2σ band | Sharpe held 0.75→2.64→0.41→0.48 across eras while return fell 2.54%→0.05%/yr | **Edge per opportunity SURVIVED; opportunity count collapsed.** Needs instruments where dispersion has NOT been industrialised by portfolio trading. See QUEUE rank 1 |

---

## ACTIVE
| id | hypothesis | phase | blocking gate |
|---|---|---|---|
| **CEF-DISC** | **credit closed-end fund discount reversion** | **Ran on IBKR paper 2026-07-31 → 2026-09-15; IBKR retired 2026-09-28; being rebuilt on Alpaca paper** | `docs/ROADMAP.md`; the 60-live-session review restarts with the Alpaca track record |
| COST-AUDIT | the 21.2%/yr modelled cost is a full-sample artifact | **RESOLVED, see below** | — |
| **E1** (EVENTS trial 1) | the NAV-for-NAV CEF merger pair, long target / short acquirer from A+1 to completion, muni headline (`results/events/PREREG_E1_MERGER_PAIR_2026-10-19.md`, amendment 1: borrow ignored in the verdict) | **Stage 0 HALT (2026-10-19)**: DG-E1-1/2/3 fail, DG-E1-4/5 incomplete; identity checks pass; no E1 statistic, 27-name set not consumed (`results/events/E1_STAGE0_2026-10-19.md`) | Amendment 4 (2026-10-21: the universe takes 331; the CRSP outcome rule): fit 196 deals (muni 99); the team lead's `fetch-edgar --amendment4` (11 deals to date), `pull-crsp` (9 parties) and two targeted fetches (SBI, NCU). DG-E1-3 after the third reading and rulings 12–15 (PREREG amendment 5, 2026-10-21): **Stage 0 CLEAR 2026-10-22** at 732fc9d: all seven gates pass; 13 in-trial failed deals, 10 muni. Two pre-fit bugs fixed: the failed-deal file, the control-2 key. Ruling 16 (2026-10-22, amendment 6): ALD→PSEC is kept with no control 2. The fit has not run; an independent quant review of the fit path comes first (`results/events/E1_DG3_RULINGS_FORM_2026-10-20.md` §7). `fetch-edgar` and `pull-crsp` were run 2026-10-20: DG-E1-2 now passes (63 of 64 holdout deals dated; EDI undatable and excluded) and the control-2 pool is complete. **Ruled 2026-10-20** (PREREG amendment 2): the 19 Stage-0 flags and readings R1–R12 accepted as recommended, failed deals kept (decision 6 default) |
| DISP-SCAN | PD dispersion is still wide in non-industrialised wrappers | building | — |
| NPORT | monthly holdings history 2019+ from SEC EDGAR *(corrected 2026-10-19: public N-PORT is one month-end snapshot per fiscal quarter, filed within 60 days, and its XML first reaches EDGAR in filings of Oct–Nov 2019 (FR 2019-03958 [V]; EDGAR index counts [V]); monthly public N-PORT starts 2027-11-17. `results/events/ssx/ssx_risk/CARDS_2026-10-19.md`)* | agent staging | EDGAR parse |
| BREADTH | 45-instrument universe | agent staging | data fetch |
| **C4** (CEF trial 52) | the live discount z-score pooled over five CEF families, on the 74 funds frozen at the 2026-10-14 re-read (65 with fit data) (`results/cef/PREREG_C4_FAMILIES_2026-10-13.md` and its four amendments) | **PASS on the corrected book** (team lead's ruling 2026-10-19, result note §9: gross SR 1.434, net 0.999 / **+0.130** / −1.174 at 5 / 15 / 30bp, NW t 2.89; stage 9 passes; recorded deviation, the four IGR bars fixed after the opening; **paper only, no real-money sleeve**). As first committed: PASS, labelled D2 (2026-10-18; holdout opened once at `353dc57`). Fit (2026-10-14, 3be92cd; both independent reviews confirmed it): gross SR 1.217 (NW t 5.32), `_dsr` 0.991 at N = 52, every kill passed. Holdout 2023-01-03 → 2026-09-30: gross SR **0.725** (NW t 1.32), the fit's sign (stage 8 pass); net 0.382 at 5bp, **−0.304 at 15bp** (stage 9: D2), −1.332 at 30bp, flips; 2023–24 +12.78%/yr, 2025–26 −3.50%/yr. Report-only: without IGR 1.486 (net@15 +0.086); 82% of the holdout P&L in the ex-date window [0,2] (fit 33%); rho21 with the book 0.134/0.196. Recorded deviation: BTX's Stage-0 flags were cleared after the fit P&L (zero weight in the fit) **CORRECTION PENDING (2026-10-18, result note §8):** an independent review found four bad IGR price bars (2026-07-29, 08-04, 08-07, 08-11; post-split basis inside a raw pre-split series, flagged by Stage 0 Q5 on 2026-10-14 and never triaged) costing −10.87% of capital. Corrected: gross SR 1.434, net@15 +0.130, NW t 2.89; grid still flips by 30bp. R-IGR's 1.486 was this defect. **Ruled 2026-10-19: the corrected book is the verdict** | none for the verdict: paper only by ruling. IGR's 2026-08-20 amount moves the Sharpe by 0.002 either way (§8). Before any real-money proposal: borrow measured, not modelled at zero |
| **VT** (CEF trial 53) | sizing each account at its per-account equal-risk multiplier (`results/cef/PREREG_VOLTARGET_2026-10-30.md`): the frozen key `sizing_multiplier`, core ×1.13, C4 ×1.27, at a 5.25% combined target; **amendment 1 (2026-11-02): core ×1.30 (spec v9), C4 ×1.26 (spec v4), the core's stops recalibrated on the live thin-day rule (§0.B)**; `vol_target_annual` stays 0.06 | **APPROVED 2026-11-01** (team lead). Implementation: the code commit (absent = today, proved against 35b429f's pins), then the core's value as a separate activation commit; C4's value goes in at C4's arming. Expected on the fit (model, gross): combined 8.50% TR / 9.18% PR, Sharpe 1.68 / 1.76; per account, zero-edge P(HALVE) through 2008: core 15.2% median, C4 16.3% | forward paper only: R3 at 60 armed sessions, R2 at 120, R1 at any time, per account; the core's 60-session kill rule and C4's H11 rule, which is rebuilt on the raised book |
| **C4-LEVEL** (CEF trial 54) | C4's within-family discount level, blended ½ : ½ by risk into C4's z book under one vol scalar, C4's spec multiplier, band and 1.90 cap (`results/cef/PREREG_C4_LEVEL_2026-11-02.md`; frozen key `level_signal`, spec `c4_families.v5` on activation) | **PASS on the pre-registered remainder; the holdout decided** (2026-11-03). Holdout 2023-01-03 → 2026-09-30, opened once: level-only gross SR 1.636; blend 14.56%/yr against z-only 10.32% (SR 2.065 vs 1.497); net@15 0.843 vs 0.125, no D2; the blend's net turns negative at 30bp [S: one run, internally consistent, not independently recomputed: the opened-once guard forbids it]. **K3 (D4) FAILED as committed** (HY-window alpha t 2.96 < 3.0, every \|β\| ≤ 0.082) and was **overridden post-data by the team lead** ("revive it and figure out a way to not kill it"), so it is not a pass. P1 t 2.8315 against 2.8245 after the DG-L4 fix (first read 2.8271), and lag-fragile (2.80 at lag 5 or 21). **Evidence INCONCLUSIVE at N = 54** (holdout level-on-z alpha +10.43%/yr, t 2.74; adjusted interval −2.14% to +22.99%). Gate 0 cleared post-data. The registry's judged entry is the first-read blend; the corrected series sit beside it unjudged. Paper only, as C4 | activate `level_signal` in C4's spec (PR #41) through `/spec-change` and a release; the live stops (§6.3: C4's kill rule and trial 53's stops rebuilt on the blended book, plus L1); borrow on the premium-fund shorts measured before any real-money view |
| **TE4** (CEF trial 55) | on a session with 4 or 5 eligible names, trading the eligible set with the sleeve's own construction earns more gross than closing the book (`results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md`); keys `below_min_names: "trade_eligible"`, `below_min_names_floor: 4`; **paper only** | **APPROVED 2026-11-03** (team lead). Next: the implementation PR (key absent = flatten, proved), owner-reviewed. Inert until a session is thin (none since 2023-08-30 on the panel to 2026-10-14). Activates only after the core's 60-session review is graded and prod's Q6/Q10 counts are in | forward thin episodes only: ABSENT on the first two negative or a mean ≤ 0 from the third; KILLED on K0 (the account at HALVE or KILL during an open episode, acting in code) or K1–K3; PRESENT only at 5 / 9 / 13 / 20 episodes at t ≥ t(k−1) critical at p / 4, with PHK and PDI out still positive, labelled unmatched (H2) |

> Rows above that point elsewhere in this file ("See QUEUE rank 1", "RESOLVED,
> see below") refer to sections now in the snapshot at git tag `pre-clean-slate`
> `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md`. The rows themselves are unchanged.

---

## CLOSED — measured, adopted nothing, spent no trial

| id | question | verdict | evidence | date |
|---|---|---|---|---|
| NAV-HEDGE-1 | Can an ETF overlay hedge the core's NAV moves (live NAV component −$2,250.74 over 2026-09-15..10-30, PR #26) for a better Sharpe? | **Closed at the power gate, UNDERPOWERED** (team lead, 2026-11-02). No data pulled; zero trials. P(pass) 0.07–0.11 one-sided at the factor R² 0.011–0.074 on record, and it cannot raise return on capital under Reg T. If ever run, it counts on CEF. Replaced by a report-only exposure readout (MUNI/TERM/credit/loan) | the screen note on branch `research-nav-hedge` (another session) [S, not re-read here] | 2026-11-02 |
| W14-A | Is the book short volatility in a sense that gives a hedging option a job? | **No** — the convexity overlay (W14 Part B) is closed by its own pre-written gate | `pre-clean-slate:results/cef/STRESS_BETA_2026-09-11.md`; `python3 scripts/cef/stress_beta.py` | 2026-09-11 |
| W4 | Is the deployed discount IC an artifact of distributions, bid–ask bounce, stale NAV, ex-dates or crises, and is its P&L factor beta? | **No artifact explains a material share; not factor beta** (FF5 + UMD + Pástor–Stambaugh; betas ≤ 0.10, gross alpha t on the 3.0 bar). **The deployed 13-name, ADV-filtered IC is about half the 17-name figure the docs quote, and is concentrated in Dec–Jan and volatile states.** Fit period only; the 2023 holdout was not opened. No trial spent, no counter moved | `results/cef/W4_ARTIFACTS_2026-10-11.md`; `python3 scripts/cef/w4_artifacts.py` | 2026-10-11 |
| G6 | Can long credit gamma be timed by a declared conditioner? | **No** — no conditioner times it, and G7 does not run (C3 is in KILLED above) | `pre-clean-slate:results/gamma/PREREG_GAMMA_TIMING_2026-09-13.md`, `pre-clean-slate:results/gamma/CREDIT_BASE_RATE_2026-09-13.md`, `pre-clean-slate:results/gamma/CONDITIONERS_2026-09-13.md` | 2026-09-13 |
| W10-B | Is the deployed edge selection within groups or timing between them? (the zero-trial prerequisite of C2) | **Selection.** Deployed: within −9.07bp/z (t −3.02), between −3.29 (t −0.87); within carries 89% of live gross return, and the group spread alone earned 0.03%/yr. WIDE 13-name set (context): between is paid (−9.07, t −5.21) but less than within (−12.58). Random-group control: the real difference ranks above 18 of 20. **The deployed fit sample existed on only 43.6% of sessions and almost never held the munis**, while today's book is 67% between (long multi, short muni and JFR). Part B item 2 (separately built books at matched turnover) was **not run**: a variant comparison is a trial. C2 is cut to Part C (1 trial) plus at most 2 conditional Part D groups. No trial spent, no counter moved | `results/cef/W10_PARTB_2026-10-12.md`; `python3 scripts/cef/w10_partb.py` | 2026-10-12 |
| CORE-a, CORE-b | (a) Should the discount be distribution-adjusted around specials? (b) Is the Dec–Jan concentration a tax-loss sleeve? | **(a) No**: around specials the deployed z reads funds rich and is right (slope −49.5bp/z, t −3.76; 22 dates, D7). **(b) Not as a sleeve or gate**: the effect sits in late-December signal dates, the loser/winner gradient holds in Feb–Nov too (calendar control), there are 9 seasons (D7), and a gate is in the sizing-on-dislocation family. Kept as a declared stratum. Open proposals in the same note, not run: C5 (opening-auction fill), C2 Part C, the ex-cycle freeze. No trial spent | `results/cef/CORE_SIGNAL_CANDIDATES_2026-10-12.md`; `python3 scripts/cef/core_signal_decomp.py` | 2026-10-12 |
| E1-G1a | Can E1's short-acquirer leg (CEF/BDC merger pair) be built at Alpaca? | **Not for munis, where the effect lives.** On 2026-10-13 the pending muni acquirers were 1 of 2 shortable (NZF no, MMU yes) and the historical muni acquirers 7 of 23 on today's flags: **FAIL**. Taxable (78%) and equity (62.5%) **pass**, but their at-announcement medians (+4.6bp, +15bp [S]) are already under E1's kill line. BDC is partial (n 1 and 3). At IBKR the muni shorts are mostly available, but universe muni acquirers' fees at first filing had a median of 9.43%/yr [S levels]. **E1 as designed: not recommended** (team lead to decide). No trial spent, no counter moved | `results/events/G1A_SHORTABILITY_2026-10-13.md`; `python3 scripts/events/g1a_shortability.py` | 2026-10-13 |
| A1-BOOK | Do the live book's shorts lose money inside CEF share-issuance programme windows, and would blocking them help? (re-open (4), team lead 2026-10-28) | **No.** In-window shorts earned more, not less: out − in −0.935bp per short name-day (SE 0.552), INCONCLUSIVE, leaning the other way. Blocking costs gross Sharpe 0.955 → 0.735, and still loses net of borrow. Most of the gap is calendar (−0.29bp within date), and PTY 2018–20 carries 68% of the in-window P&L. The longs control is unaffected. The windows are known only after the fact, so the block is not tradable anyway. Fit only; no trial spent | `results/research/REOPEN_A1_BOOK_WINDOWS_2026-10-28.md`; `python3 -m scripts.research.reopen_a1.book_windows` | 2026-10-28 |
| SS5-MA, SS5-IBKR | (a) Is equity merger arbitrage feasible, and alpha-only, for this desk? (b) What would IBKR as a second broker cost and unlock? | **(a) Not alpha-only on the published evidence: D4 in costume.** Net of costs MP2001's index manager has α t 2.9 and β 0.12, and β 0.49 in months below −4% (a short index put); a SPY short moves the average β, not the kink, and a long-put hedge is outside the options ruling. Deal flow (3,851 listed-target deals 2010→2026-10-16, ~210–270 a year) and large-cap acquirer borrow (23 of 25 identified pending acquirers shortable and ETB at Alpaca; IBKR median 0.41%) are not the constraint; **reading is** (regex reader right on all fields for 0 of 16 sampled deals, on none of 12 stated outside dates; 4 of 10 cash-class picks were not targets). **(b)** IBKR would let the book short the six munis Alpaca cannot (0.83–5.15%/yr today) at the cost of Pro commissions, professional market data for an entity, 0% short-proceeds interest below USD 100k, and a weekly manual 2FA login the VM cannot do. No trial spent, no counter moved | `results/events/MERGER_ARB_AND_IBKR_2026-10-15.md`; `python3 scripts/events/merger_arb_feasibility.py --today 2026-10-18` | 2026-10-18 |
| SS5-MA-v2 | Can merger arbitrage be rebuilt so that what is left passes D4? (team lead, 2026-10-19) | **One design, MA-HZ, is D4-clean by construction; its alpha leg is unlikely to be provable on our history.** Giglio & Shue's event-time result (completion hazard hump-shaped, holders under-react to the passage of time, betas flat in event time) gives a long-High / short-Low book inside the deal cross-section; published betas give it market β ≈ 0.09 linear, ≈ 0.01 in down months. The hump is present in 2010–22 cash deals (peak week 13–14, earlier than the paper's windows). Short leg buildable at Alpaca (16 of 17 Low-1 targets). Turnover 7.8–8.5×/yr; net positive at 5 and 15bp, flips at 30bp after post-publication decay. **P(alpha t ≥ 3) 1–15% on 2010–22 at the published IRs** (2–34% on a 2001 census; ≤ 7% after decay). Stock universe outcome-biased. **E1 at IBKR: dead on borrow** (≥ the +167bp effect in 6 of 7 muni windows; 196bp at today's median fee). Twelve other angles killed. No trial spent, no counter moved | `results/events/MERGER_ARB_V2_2026-10-19.md`; `python3 scripts/events/merger_arb_v2_feasibility.py --today 2026-10-19` | 2026-10-19 |
| SPAC-DL | Is the deadline-only SPAC route (buy below trust, no election, take the liquidation) alpha, or the census's +2%/yr over bills a premium in costume? (team lead, 2026-10-19) | **CLOSED by the team lead, 2026-10-20 (D4, zero trials spent).** **Not alpha at zero trials.** **As an asset class it is D4**: every pre-deal SPAC common, 2019–22, executable closes, shift(2), alpha 8.93%/yr t 2.18; MKT β 0.090 daily, 0.154 weekly, 0.463 monthly (stale prices hide it); β 0.53 in months below −4% (the merger-arb kink); −6.6% over bills in Feb–Mar 2020; top 5 names 34% of gross. No declared cut reaches t 3.0. **The census's below-trust trade is untestable without spending the trial**: 2022, the one bond-like year, has betas ≤ 0.03 but alpha +1.72%/yr t 1.93 over French RF and **+0.93%/yr t 1.05 over the census's 3-month bill**; one year cannot reach 3.0. At Alpaca: $17.9M (below accrued trust) / $3.4M (near deadline) on median ADV; the pre-vote sale at 69% of terminal events cuts the near-deadline spread to +0.19% at 30bp [model]. Census defect found: 6-K (foreign-private-issuer) deals are undated. 2015–22 asset class now seen; 2023 holdout sealed. No trial spent, no counter moved | `results/events/SPAC_DEADLINE_PRESCREEN_2026-10-19.md`; `python3 scripts/events/spac_deadline_prescreen.py` | 2026-10-19 |
| A1-ISSUANCE | Does CEF share issuance at a premium (ATM programmes, shelf offerings) give a dated event the live z-score is blind to, worth an EVENTS pre-registration? (team lead, 2026-10-19) | **CLOSED by the team lead, 2026-10-20 (zero trials).** **FAIL at zero trials; not worth a pre-registration on this data.** 33 programme events in 31 funds, 2008–22 (EDGAR supplements × CRSP beyond-DRIP share growth; ≥ 4 supplements). 4 of 15 hand-read confirmed episodes were uncoded rights offerings. Only 7 have a premium path outside the 44: premium +10.9% at the event, live z +2.02, +3.0% after 21 sessions. **None has three premium- and z-matched controls, so issuance beyond M1 is unmeasured (D7)**; gates G-A1-1, -3 and -4 fail. Access: 15 of 25 still-listed programme funds shortable at Alpaca (2026-10-12); 8 of 25 CEFs at a premium today; IBKR borrow in deployed programme windows 11.6–44.7%/yr (2021–22). **For the live book (CEF counter, not measured):** 18.1% of fit-period short name-days fell in deployed programme windows (PCN, PFN, PTY, PDI, PHK, HYT, JFR). PDI reports $1.35bn of ATM proceeds in the year to 2025-06. The next step is a G6-style P&L measurement, for the team lead's go. No trial spent, no counter moved | `results/events/A1_CEF_ISSUANCE_GATE_2026-10-20.md`; `python3 scripts/events/a1_cef_issuance_gate.py levels --edgar-cache … --crsp-cache …` | 2026-10-20 |
| MUNI-HZ (B1, B2) | Should the live book carry subtract-only hazard flags on its muni funds? B1: muni credit events from EMMA notices, mapped through N-PORT. B2: disasters and state fiscal shocks, from OpenFEMA (team lead, 2026-10-19) | **CLOSED by the team lead, 2026-10-20 (zero trials).** **Not worth building, not even in report mode** (recommendation; the team lead rules). **B1 fails on its source.** EMMA's terms bar automated and manual monitoring, and the MSRB feed costs $45,000/yr. N-PORT's own default flags are quarterly, 54–59 days late, and tiny: one new flag in 26 fit fund-quarters, at 0.055% of NAV. **B2 fails on its premise.** MHD and MQY are national funds (about 17 effective states; largest state 21–25% of NAV). A state-level flag covers 37% of muni name-days, and DR declarations lag the incident by a median 41 days. **No muni-specific stale-mark signature.** The discount did not widen on touched events (+3.3 ± 14.8bp, 2020–22). The muni-minus-taxable-control slope has t −0.97 and 0.16 (declared), 0.62 and 1.35 (post hoc). **Little to block.** At most 1.11% of 2020–22 book turnover; MHD never cleared the ADV floor in 2005–22. Also corrects `docs/BRIEF.md`: the BlackRock munis also lever through TOB trusts, and MHD's preferred is VMTP. No trial spent, no counter moved | `results/cef/MUNI_HAZARD_FLAGS_GATE_2026-10-20.md`; `python3 scripts/events/muni_hazard_gate.py run` | 2026-10-20 |
| A2-INSIDER | Do insider open-market purchases (Form 4, code P) in CEFs and BDCs carry information beyond the discount z-score? (team lead, 2026-10-19, path A2) | **CLOSED by the team lead, 2026-10-20 (zero trials).** **Recommended CLOSE, zero trials (team lead to rule): gate G2 fails.** Insiders buy wide discounts (event z mean −0.35 vs +0.03 for all fund-days), which is the book's own signal. Matched on z (group × month × z bin), the 21-session discount excess is +0.15pp (t 1.09) and the price excess +9.5bp (t 0.44), on 1,179 events, 2006–22. The second method (fund × year × z) has the opposite sign, and a cell fixed-effects regression agrees (+0.16pp, t 1.19). Negative control (H12): the equity families, where the marks channel cannot operate, beat the credit-like funds (+37bp vs −38bp price). The sales placebo has the opposite sign (pass). Net per round trip −0.5 / −20.5 / −50.5bp at 5 / 15 / 30bp. **BDCs (price only):** +100bp (t 3.13), but the sales placebo is +91bp, and matching on days since the BDC's own 10-Q cuts it to +24bp (t 0.63, report-only). It is the post-report trading window, not information; do not fetch BDC NAVs for A2. Counts: CEF 4,665 and BDC 1,508 fund-events; 1–14 a year on the 17 touched names. The 27-name set was counted only; the 2023 holdout is unread. No trial spent, no counter moved | `results/events/A2_INSIDER_BUYING_GATE_2026-10-20.md`; `python3 scripts/events/a2_insider_buying.py all` | 2026-10-20 |
| SSX-1 | Special-situations expansion, iteration 1: which of 57 new event candidates (the team lead's A–D list plus generated ones) survive a zero-trial census and kill gate? | **8 pass a gate:** D1 clustered insider buying (3,485 liquid clusters 2010–22), CR15 PFF index additions (101–143 a year 2020–21, median 2.02 days of ADV), D9 earnings-date delay (368 liquid late events a year), A2 CEF/BDC insider buying (≥ 86 a year), A1 fund issuance into a premium (55–67 issuers a year; borrow 52%, marginal), D6 8-K red flags (marginal; most of the move precedes our fill), D8 S&P 400/600 (marginal; sources disagree), B4 downgrade flag (census only). **20 killed** (among them A3, A4–A6 and C2–C4 on count, A9, B1, B2, C1 on access, C6, C7 as `leadlag`, D2, D4 and K5 on borrow, D7). The adversary's base rate: 2 of 207 published predictors pass the desk's D4 as published. No trial spent, no counter moved | `results/events/SS_DESK_EXPANSION_2026-10-19.md`; seat files under `results/events/ssx/`; `scripts/events/ssx/` | 2026-10-19 |
| SCR-MACRO-STATE | Does a fund group's own macro observable (HY OAS for hy/multi, SIFMA for munis, tri-party repo for PIMCO) change the deployed signal's within-group IC, so that a per-group macro filter could choose which funds to trade when? (team lead, 2026-10-26) | **No.** No own-observable split reaches \|t\| 2 on the deployed 13 or the wide 17. The mismatched-observable control is the same size. Within-muni IC holds in every SIFMA state (−0.077 to −0.123, all t ≤ −3.7), so there is nothing to switch off. Where anything matters, the generic vol state matters more, and it does not hold on the other phase. **A zero-trial preview of C2 Part D: a later C2 trial must declare it has seen this.** No trial spent | `results/cef/screens_2026-10-26/r1_macro_state/NOTE.md` | 2026-10-26 |
| SCR-MACRO-DAYS | Do CEF discount moves on FOMC, CPI and NFP days revert more than same-size moves on other days (an event overlay; MACRO-lane territory)? (team lead, 2026-10-26) | **No.** Extra price-leg reversion on release days is −6.9bp per unit (t −0.36; size-matched −8.1, t −0.40). Placebo weeks score +19.1 (t +0.97). Side result: ordinary-day reversion runs through **price** (−37.3, t −3.39), not NAV (+4.6, n.s.). No trial spent; MACRO not touched | `results/cef/screens_2026-10-26/r2_macro_days/NOTE.md` | 2026-10-26 |
| SCR-C4-EXDATE | Is C4's ex-date P&L concentration (fit 33.1%; holdout 82.1% committed, 52.6% corrected) a real effect of C4's signal, or an artifact? (team lead, 2026-10-26: gates moving C4 toward paper) | **Mixed.** The screen ruled out data causes: misdated NAV, disputed amounts and stale prints carry 12.6% of window P&L. **The independent review found the drift generic:** a z-blind short into ex-dates earns it, and once that profile is removed C4's own window excess is t 1.69 against the 2.0 bar. Eaton Vance covered-call funds carry 59.5% of the C4-specific excess. **Paper overstates C4:** price-only Sharpe 1.360 vs total return 1.217 on the fit. A second method finds the drift itself (post-hoc): CAR(+1..+3) −34.3bp (t −14.9) on C4's families over 2005–22, −20.5bp (t −6.8) on the credit 17. *Corrected 2026-10-27: this row first gave −30.1bp (t −5.6), the 1982–2022 figure; and W4 (2026-10-11 §1) recorded the pattern first, untested.* Its pre-registration is a draft. No trial spent | `results/cef/screens_2026-10-26/README.md`; `r3_c4_exdate/`, `r3_review/`, `r6_exdrift/` | 2026-10-26 |
| SCR-IDX-REBAL | Do fund-of-CEF index reconstitutions (YYY, PCEF, XMPT) force flow ≥ 1 day of ADV that a `shift(2)` book could trade? (team lead, 2026-10-26) | **ARTIFACT, pooled** (2026-10-27, after the team lead's R2 pull of CRSP MF holdings; *first recorded 2026-10-26 as infeasible on free data*). 137 events ≥ 1 ADV, sized without lookahead, pass the gate. Pressure is +50bp (t 2.23) and reversal −73bp (t −3.58), but **the placebo one month earlier scores +113bp (t 2.87)**, from YYY. PCEF alone: +184bp (t 5.5), then −120bp (t −5.6); placebo +8bp. That is a post-hoc subgroup, and a trial needs PCEF's announcement dates. The non-changer control was degenerate (a design error, recorded). The screen applied 8 more `drop_split` cells itself, which is not a team-lead ruling. No trial spent | `results/cef/screens_2026-10-26/r4_index_rebal/NOTE.md` | 2026-10-27 |
| SCR-BDC-DISC | Does the discount z-score work on BDCs? (team lead, 2026-10-26; preferred ETFs excluded as `single-fund-PD`, preferred CEFs already in C4) | **Nothing in the tradable set** (2026-10-27, after the team lead's R2 pull of Compustat `fundq`; *first recorded 2026-10-26 as infeasible locally*). ceqq/cshoq matches point-in-time XBRL NAV on 167 of 175 checks. All 54 BDCs: IC +0.0258 (t 5.14). It is not stale prices (traded-only +0.0271), and another fund's NAV scores +0.0093. **The independent review found:** at ADV ≥ $3m, 2012–17 is null and the 2018–22 NAV term is t 0.48 next to 5-day reversal. The tradable signal is short-term reversal; the NAV information sits below $3m ADV. The settling test, if ever wanted: 2023+ with XBRL NAV, ADV ≥ $3m, NAV term t ≥ 2.81. No trial spent | `results/cef/screens_2026-10-26/r5_bdc/NOTE.md`; `r5_review/` | 2026-10-27 |
| BAND-COST | Should the no-trade band width be re-derived from the measured paper execution cost (7.14bp; `results/cef/EXEC_COST_STUDY_2026-11-05.md`, PR #58, merged as 1f44bbf) by the cube-root law, with σ_w and κ_w re-measured on the fit? (team lead, 2026-11-05) | **Keep 4.8% on both books; zero trials, CEF stays 55** (team lead, 2026-11-05: "Accept: keep 4.8%, close"). Derived h\*: core **4.55%** (σ_w 0.0613/day, φ_w 0.958; the cost's 95% interval 3.0–14.2bp gives 3.4–5.7%); C4 **4.07%** at 12.43bp (7.14bp × quoted-spread ratio 1.741; C4's own fills are one session). Both pass the paired plateau test (grid argmax vs h\*, HAC p 0.20 / 0.14). Neither beats live: the core's 0.045 − 0.048 nets +0.04pp/yr, NW t 1.34 against the bar 2.837 at N = 56, and could not be seen live; C4's derived width is worse than live at its scaled cost (−0.058 Sharpe, HAC p 0.038 total return, unadjusted). Narrower bands trade more and cost more: no saving. The 2026-09-06 σ_w (0.04083) is not reproduced (0.0605 on the 17-name fit). Follow-ups, both measurements: C4's band re-measured on its own fill cost after 21 sessions (no earlier than 2026-12-03); the band re-derived on a measured live auction impact before any real capital. Fit only; no 2023+ figure computed | `results/cef/BAND_COST_REDERIVATION_2026-11-05.md`; `python3 -B results/cef/band_cost_2026-11-05/band_cost.py` (second method `crosscheck.py`) | 2026-11-05 |
