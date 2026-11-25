# Health check: the three paper books and the portfolio layer, 2026-11-24 evening

**Asked by the team lead, 2026-11-24 ~20:45 ET:** "go over our deployed 3 sleeves and overall
portfolio, make sure all our 3 sleeves are deployed properly with no errors and overall portfolio
layer is working as intended."

**How it was read.** 20:50 to 21:10 ET, read-only: `python3 -m ops.orient` and
`python3 -m ops.daily_page` on the laptop at `b912a56`; one ssh read per question to `quantt-vm`
(systemd state, unit environments, journals, the books' state files, the shadow decisions, the
VM's own NAV and price panels), copied to the session's scratchpad for the arithmetic; and the
public performance page as served at 21:00 ET. Nothing on prod was changed by the check. The VM
was rebooted afterwards on the team lead's go (EVIDENCE_LOG E-2026-11-24-61). Every figure is from
those reads, tonight, unless it says otherwise.

## Verdict

**All three books are deployed and traded cleanly today. No error on the order path.** The
portfolio layer reports what it was built to report, and its sums agree with the accounts. It
leaves the gaps the team lead already knows about (the events book outside the combined reads)
and surfaces two live findings: C4's short-equity tilt and late NAVs at the 22:00 decide. The team
lead's rulings on both are at the end.

## 1. The books

| | core (`cef`) | C4 (`c4`) | events |
|---|---|---|---|
| code on the VM | `release-20261124-17` (428d588) | same clone | same clone; its unit files were rendered at `release-20261123-2`, and nothing under `quantt/sleeves/`, `ops/sleeves/` or `shadow/` changed between the two tags [V `git diff --stat`] |
| arming | `DRY_RUN=0` + `AUTO_ARMED`, no HALT [V] | same [V] | send unit `DRY_RUN=0` + `AUTO_ARMED`, no HALT; plan and verify units `DRY_RUN=1` (they send nothing) [V] |
| session 2026-11-24 | decided at 22:00 on 11-23 (as-of 11-23), 0 refusals; 8 orders, 8 filled; VERIFY PASS [V] | 0 refusals; 10 orders, 10 filled; VERIFY PASS [V] | all 8 sleeves `decided` on fresh shadow decisions (written 18:50 ET on 11-23), none stale; 205 orders sent, 0 rejected, 205 filled in full; the 15:46 backup slot refused (exit 11) on four separate gates (STARTED, Alpaca order ids, exposure, positions moved); VERIFY PASS, ledger booked to 2026-11-24 [V] |
| reconciliation | 12 positions after the fills, every order final [V] | 17 positions after the fills [V] | the sleeves' ledger summed by symbol equals Alpaca's positions on all 222 symbols; 13 names sit off their net target by under $25 (`min_order_usd`), 4 targets equalled the holding [V] |
| official P&L to the 11-23 close | −$146.95 over 40 sessions; drawdown 1.60% [V orient] | −$295.44 over 39 sessions; drawdown 2.21% [V orient] | no P&L of record yet (ROADMAP 7.3); after-close reading −$240.77 on 11-24 [V verify.json] |

- The laptop's launchd scheduler is OFF; only the VM is armed [V orient].
- Tomorrow's inputs are in place: every events sleeve has a `2026-11-24.json` decision for the
  2026-11-25 session [V].
- The four failed units are expected: `quantt-cef-collect` and `quantt-c4-collect` exit 5 because
  the data day stays incomplete until the NAVs and Alpaca's end-of-day point arrive;
  `quantt-events-send` exit 11 is the refused backup slot; `quantt-reports-secret` stays failed by
  choice (email alerts skipped, 2026-11-20). The shadow runner exited 3 at 18:54 and 20:54 on one
  marks gap in one name, after writing its decisions. The live events book's verify marked that
  name from Alpaca's own bar, so the gap affects the simulated books only [V].
- The half day on 2026-11-27 is covered: the end-of-day stamp fix (PRs #83, #84) is in
  `release-20261124-17` [V `git merge-base`]; the events send has its 12:41/12:46 slots, and the
  core and C4 have 12:52/12:55 [V unit files].
- The core's own attribution to the 11-23 close: hold +$683.80, fill −$816.50, fees −$14.25 over
  40 sessions [V the 05:15 P&L report]. The book is up at the closing prints and down on paper's
  fills. That is landmine 1: paper runs no auction.

## 2. The portfolio layer

**Inside the events book.** The netting works: 247 bookings across 8 sleeves, 6 of them crossed
inside the account. The 1.5× gross cap binds already, with every sleeve at a quarter size: the
plan scaled every sleeve by 0.9586, to a gross of $146,125 on $99,892 (1.46×) [V plan.json]. Any
move up the ladder will scale every sleeve unless the account's capital or the cap rises first.
That matches the ruling "Keep $100,000 for now (raise again before any sleeve goes to half size)".

**Each book's own limits.**
- HALVE/KILL, report mode: both OK on the official series, at 1.60% and 2.21% against the 12% and
  18% lines [V the 05:45/05:50 risk reports]. At the 22:00 decide the check reads `UNMEASURED` on
  every session, because the newest end-of-day row is D−1 [V plan.json `drawdown`]. That is the
  module's documented default (`quantt/session/drawdown.py`). Its `would_on` is "refuse the
  decide", so an acting mode, as built, would refuse every session. The real-money ruling
  "act automatically" needs the read-through rule (te4's K0) applied to the main check first.
- The pre-flight stress cap scaled the core to 0.9669 of its plan. That scaling is what orient
  prints as "pre-flight WARNING"; C4 was not scaled [V].
- The vol raise's stops R1–R3 (`results/cef/PREREG_VOLTARGET_2026-10-30.md` §0.B) are
  `UNMEASURED` in the risk report by design: no code reads them. Measured tonight on the official
  series since 2026-11-03 (15 sessions): core max drawdown 1.13% (R1 line 10.14%), realised vol
  5.85%/yr (R3 line 12.07%, judged at 60 sessions); C4 max drawdown 2.43% (R1 10.04%), realised
  vol **17.53%/yr** (R3 9.90% at 60 sessions) [V]. Neither stop is due.
- The corporate-action gate (report mode on both books) reads `BLOCKING` on every session. The
  cause is Alpaca rows with no symbol: the core's 11-24 read has one, `3d567376` (a worthless
  removal dated 2026-11-23), applied to all 13 held names. None of the flagged rows resolves to a
  held name [V send.json]. Under `halt`, both books would refuse every session; "fix first, block
  later" (2026-11-24) stands. The data-QA FLAG on both books comes from the same rows.
- The second NAV source has been gone the whole session: CEFConnect answered `JSONDecodeError` for
  all 13 core funds, and its last arrival row is 2026-10-16 [V]. The core's stale-NAV gate (report)
  "would defer" 12 of 13 funds on the 11-24 session.

**Across the books.**
- `python3 -m ops.daily_page` sums core and C4 only: $199,557.61, −$442.37 to date, combined
  drawdown 0.95% [V]. The events book is missing from it (ROADMAP 7.2), and it has no P&L of
  record (7.3), no HALVE/KILL (7.4) and no corporate-action gate (7.5). All four are open under
  "Arm Monday, build them next".
- The public performance page (`event-driven.quantt.ca/performance/`, built 20:50 ET) agrees with
  the accounts. AUM $300,821 = $99,784.80 + $101,305.03 + $99,730.87, the three after-close
  readings. P&L +$1,293 = −$68 + $1,600 − $239. The core's positioning (6 long, 6 short, gross
  1.79×, net −0.16×) matches its positions after the fills at the 11-24 prints [V].
- Correlation of the core and C4's official daily returns since 2026-11-03: −0.25 (n = 15) [V].
- orient's "plan shape" counts the holdings going *into* the session (each target's `current`),
  not the plan's targets. On 11-24 it reads core "13 held, net +$5,691.63", while the book after
  the fills holds 12 names at net −$15.9k. That is a label to fix, not a trading fault
  (`ops/prod_state.py` `_SHAPE_PY`).

## 3. Finding: C4 is short the equity market

- Since it armed on 2026-11-03, C4's realised vol is 17.53%/yr over 15 sessions, against an
  effective target of 7.56% (0.06 × 1.26) [V eod_equity.csv].
- Beta of C4's official daily return to the equal-weight median return of its own 74-fund universe
  is **−0.60** (correlation −0.85, n = 15). The core's beta to the same series is +0.06 [V, VM
  price panel].
- Its two biggest days were market days. On 2026-11-20 the universe median fell 2.56% and C4 made
  +$2,561.34 (+2.58%). On 2026-11-23 the median rose 2.75% and C4 lost $2,253.57 (−2.21%) [V].
  On 11-20 the book's largest short equity funds fell 7 to 8% at the closing print, and its long
  funds fell less [V closing prints; names and sizes kept out of the repository].
- C4's own factor report saw it every day: EQUITY at −$43,910 (−0.440 of equity), c/target 1.053,
  t −2.41, **REVIEW on 14 of 14 dates**; by family, equity_covered_call, equity_domestic and
  equity_sector are all short [V the 05:20 P&L report]. A review-line breach is report-only
  (2026-11-09).

## 4. Finding: late NAVs at the 22:00 decide

The measurement the team lead asked for ("Measure it first") is in
`results/ops/late_nav_2026-11-24/`. `measure.py` reads local copies of the VM's plans, fills and
NAV panels, and `by_session.csv` is its output: one row per book-session, counts and dollar totals
only. The per-session fund lists stay out of the repository (`.claude/rules/report.md`). The rule: a fund whose
NAV for the as-of date equalled its previous NAV row when the decide ran is "repeated". A repeated
NAV for which the VM's panel now holds a different value for that date is "late": it arrived after
the decide.

| | core (28 sessions with the gate's record, 10-15..11-24) | C4 (15 sessions, 11-04..11-24) |
|---|---|---|
| sessions with at least one late NAV | 22 of 28 | 14 of 15 |
| funds repeated at the decide, mean | 4.9 of 13 | 13.8 of 74 |
| of those, later replaced by a different NAV | 85 of 136 (62%) | 148 of 207 (71%) |
| Mondays (as-of a Monday), repeated / late, mean | 7.0 / 5.5 | 27.3 / 18.0 |
| what the decide does with it | decides on the old NAV; size of the NAV error on the 85 late cases: median 24bp, 90th percentile 58bp, largest 131bp | the NAV-repeat mask makes the fund ineligible, so a held one is traded toward zero by the band |
| money | $261,091 of $1,047,477 filled (25%) was in funds decided on a NAV that later changed | $48,273 of $124,550 filled after the opening build (39%) trimmed held masked funds; $26,575 of it on NAVs that later changed |

- On the 2026-11-24 session the core decided 7 of its 13 funds on Friday's NAV (the later values
  were 1 to 4 cents different), and C4 trimmed five held funds whose NAV repeated: $23,523 of the
  $37,874 it filled [V].
- The mechanism: the missing-NAV hold waits only for an *absent* row. A row for D carrying the
  previous value passes as present. On 2026-11-19 the same source had no row at all for four core
  funds, and the decide waited (E-2026-11-19-03).
- Not measured: when each NAV lands (the collector records no arrival time), and whether the later
  value is right. It comes from the same Yahoo series, and there is no second source to confirm it.
- The team lead's 2026-11-19 ruling "no stale-NAV hold gate" was made on a different measure:
  stale copies kept in the panel (24.9% of core fund-days, ~0.26%/yr). This one is lateness at
  the decide, and most of it is corrected in the panel within a day.

## 5. The team lead's rulings tonight (question prompts, 2026-11-24 ~21:15 ET)

| question | ruling |
|---|---|
| C4's equity tilt | **"Research a fix first."** A beta- or family-neutral C4 tested on the harness and as a shadow book; the live C4 book unchanged until the result is seen |
| Late NAVs at the decide | **"Measure it first."** Section 4 is the measurement; any change is a later ruling |
| The VM's pending reboot | **"Tonight around 23:00 ET."** E-2026-11-24-61 |
| Recording this check | **"Yes, PR to main."** This note and E-2026-11-24-60, -61 and -62 |
