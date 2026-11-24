# Pre-registration (APPROVED 2026-11-03, CEF trial 55): on a thin session, trade the eligible names — `below_min_names = "trade_eligible"`, floor 4, PAPER ONLY

Date: drafted 2026-11-03; **APPROVED 2026-11-03 by the team lead as CEF trial 55** (see "Approval",
next). **Nothing here trades yet.** This note edits no spec or live file, and the key activates only on
the conditions listed under "Approval". Counter: **CEF 54 → 55, in the commit that records the
approval.**
- When this note was drafted the CEF counter read 53 on `main` and on this branch [V
  `docs/RESEARCH_STATE.md`].
- CEF 54 (C4-LEVEL, PR #30) was approved earlier the same day.
- Author: an agent, for the team lead, who chose on 2026-11-03 to pre-register this rule **for paper**.
- Branch `research-thin-third-rule`. origin/main was merged at f27ef81 when this was drafted, so trial
  53's amendment 1 (#35, #36) is in view.

## Approval (2026-11-03)

**The ruling.** The team lead approved this rule at about 09:25 ET, for paper only, with K0 and the
recommended answer to every question in §10 (Q1–Q17).
- Before ruling, the team lead was shown that the rule is not shown to be alpha, that it is negative on
  real money, and that it is worth about zero going forward while no session is thin.
- The drafting session recommended keeping flatten (§10 Q1, option c). The team lead chose approval.

**The trial.**
- **CEF 54 → 55, in this commit.** Trials are numbered in approval order, and CEF 54 is C4-LEVEL.
- **Judged at N = 55:** bar 2.831, one-sided p 0.00232, so each declared PRESENT read is at p / 4 =
  0.00058 [V §G].
- §6.2's declared-reads column was simulated at N = 54 [V §G2]. The single-read figures at N = 55 differ
  from N = 54 in the third decimal [V §G].
- On every read date N is read from the counter (H14), not from this paragraph.
- **Not the nextgen shadow "CEF trial 55" (GN-N2)** that the group-cap docstrings in
  `src/deploy/sleeves/cef_discount.py` cite. That numbering was ruled shadow research on 2026-09-28
  (`docs/RESEARCH_STATE.md`, the CEF 48 → 50 note), and the implementation PR relabels it.

**The answers as approved** (the recommended answer in §10, each):

| Q | answer |
|---|---|
| 1 | approve for paper, with K0 and the conditions |
| 2 | m stays ×1.30 on reduced sessions, with K0 |
| 3 | (a): R1–R3 read on full-session earning days only while the key is set |
| 4 | K0 in code |
| 5 | K0 during an open episode means KILLED |
| 6 | measure, before activation, how often the evening decide reads UNMEASURED; never loosen K0 |
| 7 | a reduced decision that loses a short to gate 7 flattens |
| 8 | kill rule (a) is also read on full sessions alone; (c) on the spec's cross-section; (b) can be tripped by reduced sessions, accepted |
| 9 | activate only after the core's 60-session review is graded |
| 10 | no reduced build when any hold is present |
| 11 | PRESENT read only at k = 5, 9, 13 and 20, each at p / 4 |
| 12 | the min-weight guard stays at `min_names` |
| 13 | no change to the deferred flip |
| 14 | the paper-only refusal sits in the sleeve, with the runner's endpoint check behind it |
| 15 | borrow is recorded UNMEASURED per episode, and nothing is decided on it |
| 16 | the HALVE/KILL owner is told (done 2026-11-03) |
| 17 | re-measuring the core's margin cushion is trial 53's owner's job |

**The owner's terms.** The session that owns trial 53, HALVE/KILL and the runner agreed on 2026-11-03, on
these terms. They bind the implementation and the activation.
1. **Q2.** Trial 53's zero-edge P(HALVE) / P(KILL) under te4 at ×1.30, **23.2% / 3.28%**, stand beside
   the ×1.15 figure, **16.7% / 1.69%**, and beside flatten's 17.1% / 1.75% (§7.2) [V §D2]. That puts the
   extra risk on reduced sessions on the record.
2. **Q3.** The change to how R1–R3 are read amends trial 53's stops, conditional on the key. It is recorded
   as a dated note in `results/cef/PREREG_VOLTARGET_2026-10-30.md` **in the activation commit, not
   before**.
3. **Q4/Q5.** `quantt/session/drawdown.py`'s status may only ever restrict: flatten or hold. It never sizes
   up and never unlocks a send, and UNMEASURED flattens. **A test pins that no drawdown status can increase
   gross.**
4. **Q6 and Q10.** The owner measures both from prod's `plan.json` records: the drawdown status at each
   decide, and missing-NAV holds per session. The counts are reported here before activation.
5. **The implementation is its own PR.**
   - It is cut from `main` after the owner's `c4-arm-fixes` merges.
   - Its `quantt/session/run.py` changes sit in their own functions, away from the first-session gate.
   - It carries the core's no-op pins and a byte-identical sleeve diff with the key absent.
   - Every change has a test that fails on the old code.

**A ruling after approval (team lead, 2026-11-03): a short skipped at send time on a reduced session.**
- **The case.** The late-market send re-checks `shortable` at about 15:52. It skips any order that opens or
  increases a short whose name has stopped being shortable since the decide, and sends the rest
  (`quantt/session/run.py`, the send's skip, `skipped_at_send`). On a 4–5 name book that can leave the book
  one-sided for a session. §7.5's gate-7 flatten covers only a short dropped at the evening decide.
- **Ruled: accept it and label it.** Today's skip-and-send stays unchanged, on reduced and full sessions
  alike.
  - The send record shows the skipped short.
  - The session's `thin_session` record marks the reduced send as having lost a short at send time.
  - K3 watches for a book that stays one-sided.
- **The other option, not chosen.** The owning session preferred refusing the whole send on a reduced
  session that loses a short at send time, while keeping full sessions byte-identical. The team lead chose
  to leave the send path as it is.

**A second ruling after approval (team lead, 2026-11-03, after prod's Q6 count): K0 reads the previous session's EOD row.**
- **The measurement (Q6).** The owning session counted prod's core `plan.json` records: 26 decides, with
  run folders 2026-09-29..11-04.
  - The drawdown field exists in 4 decides (as-of 10-28, 10-29, 10-30, 11-02). All 4 read UNMEASURED for
    the same reason: "eod_equity.csv's newest row on or before the as-of is D−1, not the as-of D".
  - At the 22:00 ET decide, the EOD row for D is not there yet.
  - [S: the owning session's count, 2026-11-03. The run records are prod's and are not in this repository.]
- **Consequence: K0 as written made te4 inert.** Every reduced session would flatten. §6.3 had said the
  remedy would be the drawdown record's timing, never a looser K0. This ruling changes K0's reading time,
  and its cost is stated below.
- **Ruled: K0 reads D−1's row, labelled one session stale.** At the evening decide for as-of D:
  - K0 reads the account's drawdown status through the newest EOD row on or before D−1, with the
    high-water mark over the rows on or before that date.
  - If that row is older than D−1, missing or bad, K0 reads UNMEASURED and the session flattens.
  - The record carries the row's date and its staleness in sessions (1).
  - K0 stays restrict-only: it can flatten a session, never size up or unlock a send. The test that no
    drawdown status can increase gross is unchanged.
- **The cost, accepted.** A loss on day D is seen only at the next evening's decide, so one more reduced
  build can go out after a session that crossed HALVE.
  - §6.3's bootstrap modelled K0 acting from the second session after the crossing. Under D−1 it acts
    from the third.
  - So §6.3's K0 figures are slightly optimistic [U: not re-measured].
  - The kill on HALVE or KILL during an open episode reads the same D−1 status.
- **Options not chosen.**
  - Re-checking K0 before the 15:52 send. It is fresher, but it changes the send path, which the team
    lead kept unchanged.
  - Leaving K0 as written. te4 would never trade.
- **Scope.** This ruling covers K0 only. HALVE/KILL's own report, and any future `on` mode, belong to the
  owning session, which records the same finding for them.
- **Q10, the hold count.** The `missing_nav` field exists in 3 decides, none with a hold [S: the owning
  session's count, 2026-11-03]. With n = 3 the hold frequency stays UNMEASURED until there is a run of
  history. It is re-read at activation, which already waits for the core's 60-session review.

**A third ruling after approval (team lead, 2026-11-04): K0 reads the freshest EOD row it has.**
- **The case.** The verification of the te4 implementation (f3ad29f) found a gap at the morning
  backstop, when the as-of's own EOD row exists. K0 still read D−1's row there, as the second
  ruling's literal text says. In a test, that let a reduced book through on a stale OK while D's
  row read KILL.
- **Ruled: the freshest row.**
  - K0 reads the as-of's own row when it is there (labelled 0 sessions stale), whatever it reads; a
    bad row reads UNMEASURED.
  - Only when D's row has not landed does it read D−1's (labelled one session stale).
  - Anything older, or a missing or bad file, reads UNMEASURED and the session flattens.
- **Why it is safe.** A fresher row can only make K0 stricter. At the 22:00 decide nothing changes,
  because D's row is never there.
- **The other option, not chosen.** Always D−1, as first built.

**A note on K3's run (the runner's owner, 2026-11-04).** The owner confirmed on 2026-11-04 that K3's run
of 3 (§6.3) counts reduced closes within the open episode only, as §6.3's heading "K1–K3 inside an
episode" says; the rule is §6.3's and this note's, and the code (`quantt/session/drawdown.py`, which reads
the count from the spec's `risk.thin_k3_run_sessions`) implements it and does not define it.

**Two rulings by the team lead, 2026-11-08.**
- **The code ships dark.** The implementation (PR #55) merges with the key absent, so the book keeps today's flatten rule. Activation stays a separate commit and a separate decision.
- **The in-place edit is accepted.** This note's §6.3 and §11 compose commands gained `--k3-run-sessions` after approval, with a dated note and no figure changed. The team lead accepted that as it stands, rather than moving it to an addendum.

**What this commit does not do.** It sets no spec key, changes no live-path code and activates nothing.
The key stays absent until the activation commit, which needs all of:
- the implementation merged;
- the core's 60-session review graded;
- the Q6/Q10 counts;
- the K0–K3 report lines and the pre-built revert spec in the activation release;
- the trial-53 note in term 2.

---


**Revision 1, 2026-11-03, after a quant review and a PM review of ecf62ea.** Every finding was re-measured
before anything changed (`review_checks.py`, below), and §12 lists each one with its disposition. What
changed in substance:
- **K0, a whole-account stop that acts in code** (§6.3). As first drafted, the stops were split by session
  type: R1–R3 on full sessions, K1 on the episode's reduced sessions. On the fit's own path the account
  then crossed the 12% HALVE line while every acting stop stayed silent.
- **Five more conditions** (§0 "conditions"): a dropped short flattens a reduced session (§7.5); a
  "core ex-te4" series beside every report of the core's P&L (§4.4); te4 cannot rescue the core's kill
  rule (§6.4); the K0–K3 report lines are required before activation (§6.3); and activation only after the
  core's 60-session review (§6.4).
- **A reduced decision is defined by the sleeve's `reduced` flag, not by a count.** A held name now never
  coexists with a reduced build (§1.3, §4.2).
- **The cost grid counts the trading between the runs of a merged episode** (§4.4).
- **PRESENT is read at four declared episode counts, Bonferroni** (§6.1). Reading it at every episode
  against a single-read p let false PRESENTs accumulate to 1.5% by episode 13, against the 0.24% the bar
  allows.
- **The paper-only refusal sits where the key is read**, not only in the runner (§1.2).
- `compose.py` re-measures at a moved band, ceiling or panel instead of raising, and writes dated files
  without overwriting (§6.3, §11).

**Labels.**
- **[V]** computed in this session by `results/cef/prereg_thin_te4/compose.py` (2026-11-03; output
  `compose_output_2026-11-03.txt` and `.json` beside it). Fit window only: every frame ends by
  2022-12-30, asserted. Section letters (§A–§G2) refer to that output. **[V rc §Rn]** is
  `results/cef/prereg_thin_te4/review_checks.py` (2026-11-03; `review_checks_output_2026-11-03.txt`): the
  two reviews' measurements, re-run as a tracked script, fit window only, except §R8's margin what-if at
  the panel's last closes.
- **[S screen]** quoted from `results/backtests/thin-third-rule-2026-11-03/REPORT.md`, the zero-trial
  screen. **[S thin-days]** from `results/backtests/thin-days-2026-11-03/REPORT.md`. **[S T53]** from
  `results/cef/PREREG_VOLTARGET_2026-10-30.md` or `results/cef/prereg_voltarget/FLATTEN_REMEASURE_2026-11-02.md`.
  These are not re-run here, except where compose.py §A2 reproduces them; that is said where it applies.
- **[U]** an interpretation, or arithmetic on stated inputs.

**Panels and spec.**
- **Panels.** Prices end 2026-10-15 and NAV 2026-10-14. The screen cuts every return at DIST_END,
  2026-09-03 [S screen]. compose.py reads fit rows only, 2005-01-03 → 2022-12-30. Every panel is three to
  seven weeks stale against 2026-11-03.
- **Spec.** `cef_discount.v9.20261102`, on this branch and on `main`, read through `scripts/cef/spec.py`
  [V]: `sizing_multiplier` 1.30, `band_width` 0.048, `max_gross_stress` 1.8, `min_names` 6,
  `min_abs_weight` 0.005. Tag `release-20261103-1` carries the same spec id [V `git show`].
- **Prod.** Which tag prod runs, and whether it is armed, is **UNMEASURED here**. This task may not
  reach the VM; `python3 -m ops.orient` PROD answers it.

---

## 0. The draft in one table

| item | answer |
|---|---|
| **what changes** | One frozen key gains a value, and one key is new: `below_min_names: "trade_eligible"` and `below_min_names_floor: 4`. **Absent is today's rule, flatten**, and must be proved byte-identical (§1.6). On a session with fewer than `min_names` (6) but at least 4 eligible names, the core builds its book on the eligible names with its own construction, instead of closing every position. Below 4 it goes flat, as today (§1.1, §1.3) |
| **paper only** | Like the book json's `late_market` exception, it never applies to a live-money account. Today the broker client can reach only the paper endpoint. The implementation adds a refusal **where the key is read**: the sleeve raises on `trade_eligible` unless its caller declares a paper account, and the runner declares it only when its client's endpoint is the paper endpoint. A runner that does not declare it gets a refusal, not a trade (§1.2) |
| **why** | It earned the **highest gross return in every window** of the screen: fit 5.77% against hold 3.29% and flatten 1.58%/yr; 2023+ 11.50 / 10.61 / 10.63 [S screen]. Paper is scored on gross P&L with no borrow (team lead D19/D20, 2026-09-15). That is the whole case, and it is a gross case |
| **against it, up front** | **Not shown to be alpha** (§2.1). Matched-turnover gap +2.13pp/yr (t 2.34): INCONCLUSIVE under the 2.818 bar. Two names (PHK, PDI); 87% of the gap is PIMCO. Holdout +0.87 (t 0.72), one episode. Nine fit episodes at the bar, not over it. **Forward power is poor.** The exact chance of a single-read PRESENT is 0.10 after 5 episodes, and it first passes a coin flip at 10 episodes (0.52). That is 14 years away at the fit-period rate and 37 at the rate since 2023 [V §G2]. (The screen's "coin flip at 5 episodes" was a normal approximation, generous at small k.) |
| **real money** | **Negative where borrow is measured**: −2.33pp/yr against flatten on 2023+ fees. It shorts rich PIMCO funds when they are dear to borrow [S screen]. Before 2021-09-13 borrow is unmeasured |
| **the floor** | 4, **derived from the construction, not swept**. One name is 0/0, two carry only a sign, three force one side onto a single fund; four is the first count with none of these. 3 was the fit argmax and **is not chosen** (§3) |
| **today's effect** | **Zero.** No session has been thin since 2023-08-30 (783 sessions to 2026-10-14). But the least-liquid eligible name has sat at a median 1.13× the $3m ADV floor on 6–7-name sessions since 2023 [S screen §7] |
| **evaluation** | Forward only: 2023+ has been seen (H13). The unit is a **thin episode**: runs of reduced decisions merged when fewer than 63 sessions apart. A **reduced decision is one on which the sleeve's reduced build ran**, read from plan.json's structured `reduced` flag (§4.2). The statistic is the account's broker-confirmed gross P&L of record over the earning days of the episode's reduced decisions, where flatten earns exactly zero. Labelled beside it: the cost grid (gaps between runs included), the borrow it would have paid, the closing-print view, the modelled re-entry leg, the held-book days and a "core ex-te4" series (§4) |
| **verdicts** | PRESENT: read only at **k = 5, 9, 13 and 20** completed episodes, each at **the bar's one-sided p divided by 4** (Bonferroni over the declared reads). Under the null the chance of any false PRESENT by episode 20 is then 0.21%, inside the bar's 0.24% [V §G2]. ABSENT, and revert: the first two episodes both negative, or the mean ≤ 0 at any read from the third. KILLED: K0–K3 (§6) |
| **power** | Exact single-read P(PRESENT) at the fit effect is 0.10 after 5 episodes, 0.43 after 9, 0.74 after 13 [V §G]. **Under the declared reads, P(PRESENT by k) is 0.03 / 0.22 / 0.54 / 0.87 at k = 5 / 9 / 13 / 20**, and 0.01 / 0.03 / 0.06 / 0.16 at the holdout-shrunk effect [V §G2]. **This trial cannot establish alpha in any useful time.** What it can do on paper is score the gross, catch the bad case (P(ABSENT by the third episode) 3.1% at the fit effect, 52.7% at zero) and bound the risk |
| **stops** | **K0, the whole account, acts in code:** a reduced build is sent only if the decide's drawdown record (`quantt/session/drawdown.py`) reads OK. HALVE, KILL or UNMEASURED flattens that session, which is today's rule. HALVE or KILL during an open episode also KILLS the trial. K1, drawdown inside an episode ≥ D_E (10.52% on drafting day). K2, a fault detector on the largest single-name position (0.956 × equity). K3, \|net\| above 0.248 on 3 consecutive reduced sessions, or above 0.833 once. K1–K3 are re-measured on the read date by `compose.py --stamp <date>` (H14); K0 reads the spec's `risk.halve_drawdown` at run time (§6.3) |
| **conditions** | Adopted from the PM review besides K0 (its C1): K2 is relabelled a fault detector, not a concentration limit (C2); a reduced decision that loses a short to gate 7 flattens (C4); a "core ex-te4" series sits beside every report of the core's P&L, te4 cannot rescue the core's kill rule, and **te4 activates only after the core's 60-session review is graded** (C6); the K0–K3 report lines and the pre-built revert spec are required in the activation release (C1). Several of these need the team lead's ruling (§10 Q4–Q9) |
| **composition with trial 53** | **m = 1.30 multiplies the reduced book too, and trial 53's figures move** (§7.2). On W1 at ×1.30 with deferred flips: maxDD 13.76% price only and 13.79% total return, against 8.48% and 8.63%, crossing the spec's 12% HALVE line. Zero-edge P(HALVE) / P(KILL) while trading: 23.2% / 3.28% against 17.1% / 1.75%. Trial 53's rule fed te4's trading-session sd gives ×1.15, not ×1.30. The approved R3 fires 8.3% of the time on te4's fit mix, against its 5% design [V §B–§D]. **Recommended: keep m = 1.30 and read R1–R3 on full sessions only, but only with K0.** Without K0, use ×1.15 or do not approve (§7.2, §7.3, Q2–Q3) |
| **deferred flips** | On 4–5 names, a deferred flip of a one-fund side leaves the book one-sided for a session: \|net\| up to 0.833 of NAV on the fit (2019-10-09), against 0.235 with instant flips [V §E] (§7.6) |
| **revert** | Set `below_min_names` back to `"flatten"`, or delete both keys. The sleeve is then v9's, byte for byte, by the same pins. A revert during an episode closes the book at the next reduced decision (§6.5) |
| **trial** | **CEF trial 55, approved 2026-11-03.** The counter moved 54 → 55 in the commit that records the approval. The bar is read from the counter on the read date (§9) |

---

## 1. What changes

### 1.1 The key and the value

| | today (v9) | after (v10) |
|---|---|---|
| `below_min_names` | absent, which the registry reads as `"flatten"` (`src/deploy/registry.py::cef_below_min_names`) | **`"trade_eligible"`** |
| `below_min_names_floor` | does not exist | **`4`**: required when, and only when, `below_min_names` is `"trade_eligible"`; refused under `"flatten"` and `"hold"`, as the harness refuses `floor` (`band_frontier.band_gross_capped`) |
| spec id | `cef_discount.v9.20261102` | `cef_discount.v10.<activation date>`, through `/spec-change`, with tag `spec-cef_discount.v9.20261102` pushed first |
| `_below_min_names_note` | — | the WHAT / DERIVED / NOT CHOSEN / **PAPER ONLY** / READ BY / NO-OP PROOF / REVERT note, in the house shape of `_sizing_multiplier_note` |

**UNITS.** The floor is a count of eligible names, not a weight and not a fraction. The registry refuses a
non-int, a bool, anything below 2 (one name is 0/0) and anything at or above `min_names` (at `min_names`
the rule is flatten). **It does not hard-code 4.** The spec is the only authority on a live parameter
(CLAUDE.md), and the derivation's reason for 4 lives in the note.

**The default is today's.** With both keys absent, or `below_min_names: "flatten"` written explicitly, the
sleeve is v9's byte for byte (§1.6). C4's `"hold"` is untouched.

### 1.2 PAPER ONLY, and the mechanism that enforces it

The rule is chosen *because* paper scores gross without borrow (§2.3). On a live-money account its measured
sign is negative, so **it never applies to a live-money account**, as the book json's `late_market`
exception never does.

**What enforces `late_market` today** [V, read in the code at this branch's HEAD]:
1. **The broker client cannot reach a live account.** `quantt/broker/alpaca.py`: `AlpacaClient.__init__`
   raises on any trading endpoint other than `PAPER_BASE = "https://paper-api.alpaca.markets"` (l.348).
   `submit_order` checks again before every order (l.610). No book in this repository can send an order to
   a live account until a new client is written.
2. **The written scoping.** CLAUDE.md order-path rule 3 ("It never applies to a live-money account"). The
   book json's `execution._note` ("PAPER ONLY ... Not for a live-money account"). `docs/SYSTEM.md` §5,
   2026-10-09 ("the paper `late_market` exception never applies to a live account").
3. **There is no code check of `late_market` against the account type.** `run.execution_for` validates
   the mode and the window only (l.980–1002). Its enforcement is (1) plus (2).

**What enforces it for this key**, required in the implementation (the owning session's files, §1.5):
1. **The same paper-only client**, unchanged.
2. **A refusal where the key is read, failing closed** (revised after the quant review, finding 7).
   - As first drafted, the tripwire lived only in `quantt/session/run.py`. A runner that is not this one,
     such as one written for another broker or one revived from a tag, would never reach it and would trade
     the reduced set.
   - So the **sleeve** refuses instead. `CEFDiscountSleeve` raises at construction on
     `below_min_names: "trade_eligible"` unless its caller passes an explicit declaration that the account
     is paper (for example `account="paper"`). An absent or any other declaration raises, naming the key.
   - **The runner declares paper only if its broker client's trading endpoint is exactly
     `alpaca.PAPER_BASE`**, and raises `SessionError` otherwise, naming the key and the endpoint.
   - A runner that knows nothing of the declaration therefore gets a refusal, not a trade. One test per
     layer must fail without its check.
   - **Today the runner's check is unreachable** (the client can be nothing else). It exists for the day a
     live client is written.
3. **The written scoping.** The spec note opens "PAPER ONLY; never for a live-money account; delete this
   key before any live-money arming of the core". At approval, a row in `docs/SYSTEM.md` §5 records the
   ruling, beside the 2026-10-09 `late_market` row.
4. **The standing real-money gate**: "the real-money cost re-run is the gate for deploying any capital"
   (`docs/SYSTEM.md` §5, 2026-10-09). This trial's borrow column (§4.4) is part of what that re-run
   would read.

### 1.3 Exactly how the sleeve would build the reduced book

`src/deploy/sleeves/cef_discount.py::target_positions`, read at this branch's HEAD. Line numbers are
today's; the screen read the same lines 37 earlier, e.g. l.841 / l.928. **Nothing below is edited here.**

| step | where (today) | under `trade_eligible`, on a session with floor ≤ n < `min_names` eligible |
|---|---|---|
| eligibility | l.831–876 | **unchanged**. A finite z (rolling `z_window`, `.shift(1)`, clipped at ±4); a measured ADV of at least `min_adv_usd` ($3m; 63-session mean, `.shift(1)`); a NAV no older than `max_nav_age_bd`; not held by the stale-NAV or missing-NAV gate |
| the thin test | l.878, `len(row) < min_names` | n < 4: **FLAT every name, today's rule, unchanged**. 4 ≤ n < 6: **do not return; build on `row`** |
| z-neutralisation | l.948–950 | **unchanged code on the smaller set**: w = −(z − z̄) / Σ\|z − z̄\| over the n eligible names. Dollar-neutral; Σ\|w\| = 1; longs ½, shorts ½. On 19.1% of fit reduced decisions one side is a single fund [V §E] |
| vol scalar | l.953–957 | **unchanged**: rv = the annualised sd of the last 63 sessions of Σ wᵢrᵢ over these n names (today's w on past returns, panel through the decision date); w ← w × clip(0.06 / rv, 0.2, 2.5) × `gross_leverage` (1.0). On reduced decisions the scalar's median is 1.007 (p99 2.239, max 2.418), and it never reached a clip on the fit [V §E] |
| **`min_abs_weight` and the re-neutralisation guard** | l.963–970: `keep = w[\|w\| >= 0.005]`; `if len(keep) >= min_names:` re-neutralise | **Declared: the guard stays as written, comparing with `min_names`.** For any reduced set n ≤ 5 < 6, so **a reduced set is never re-neutralised**. w is kept as built, and a name under 0.005 is flattened at the output by the dust filter (l.1245), after the band. Today's sleeve already does exactly this on any ≥ 6-name session where fewer than 6 names survive the filter. **The consequence is bounded by construction**: the net residual is Σ of the dropped names' \|w\|, each under 0.005 unit. **Incidence:** the block found a sub-0.005 name on 127 of te4's 1,708 traded reduced sessions [S screen §2] |
| group cap | l.997–1000 | not set on the core spec; unchanged |
| band | l.1084–1135 | **unchanged**. The unit target is compared with held / (NAV × m); a name more than 0.048 from target trades to the band EDGE. A name no longer eligible has target 0 and is cut to ±0.048, not closed. These band residues hold about 10 names on a 4–5-name session and are below the ADV floor [S screen §5] |
| gross ceiling | l.1157–1164 | **unchanged**. `_cap_gross(w, max_gross_stress / m)` = 1.8 / 1.30 = 1.385 unit, one uniform scale-down. The held book sits at the cap on 16.9% of fit reduced decisions, against 14.6% of full ones, at ×1.30 with deferred flips [V §E] |
| output | l.1185–1263 | **unchanged**. Weight targets are m × the unit weight; a band HOLD is a share count; the dust filter reads the unit weight; decide sizes whole shares |

**New pieces** (the implementation's; not here):
1. **No silent 0/0.** On a reduced set, a non-finite weight (every z equal) **raises**, naming the
   session and the names. Today's full-book path holds silently on 0/0 under a false reason (PR #33 §5.H).
   That path is the owning session's open question 4 there, and this draft does not inherit it. No fit
   reduced session had a 0/0 row [S screen §1].
2. **A structured record of the reduced set.**
   - Every target carries `meta["cef_reduced_set"] = {"eligible", "min_names", "floor"}`, and the reason
     says "reduced set".
   - plan.json records the eligible count and a `reduced` flag as structured fields. The scorer (§4)
     never parses a reason string, as `docs/RUNNER.md` already requires for `cef_short_of_min_names`.
3. **The NAV holds** (l.878–946; revised after the quant review, finding 2). **With any hold present**
   (the stale-NAV gate's or the runner's missing-NAV hold, both reaching the sleeve through `_nav_hold`),
   **the reduced build never runs.** Today's code runs unchanged, tag included:
   - the whole book holds if `len(row) + len(held_out) >= min_names`;
   - otherwise every name but the held ones is FLAT, as today.

   **Why not build on `row` and keep the held names' shares**, as first drafted:
   - **Today the runner refuses such a day.** The core's book json sets `data.missing_nav: "hold"`
     [V `ops/books/cef_discount_book.json`]. On a decide with missing-NAV holds, `run.py` (l.1805–1827)
     refuses any decide whose targets carry the `cef_short_of_min_names` tag. The sleeve tags every return
     in the `min_names` block when holds are present (l.878–890, `_tag_short` l.342) [V code read]. A
     reduced build without the tag would have turned today's refusal into a trade, silently.
   - **The book would be one the harness never modelled:** a 4–5-name reduced book plus a held name at its
     old shares.
   - **Under flatten, such a day is not flat either.** Either the whole book holds or the runner refuses
     and the book stays as it is. So flatten's P&L that day is not zero, and E_k's counterfactual would
     break (§4.3).

   The rule is therefore simple: **holds never trigger a reduced build, as they never trigger the flatten.**
   Such days inside an episode are not reduced decisions (§4.2). They are reported beside E_k as held-book
   days (§4.4) and listed as a divergence (§8). **How often the core's holds fire is UNMEASURED here**; it
   needs prod's run records (`missing_nav` and `nav_gate` in plan.json), which this task could not reach.
4. **Unchanged on purpose.**
   - `strict` (l.749: raise rather than flatten on a missing panel) is still set only by `panel_source` or
     `"hold"`. A data shortfall under `trade_eligible` flattens, as today.
   - `gate.max_missing_nav_holds` stays n − `min_names`. Under item 3 the missing-NAV refusal is keyed on
     the same tag as today, so this rule does not widen the missing-NAV tolerance.
5. **K0 in the decide** (the PM review's C1; §6.3). Before the sleeve builds a reduced set, the runner
   reads the decide's drawdown record (`quantt/session/drawdown.py`, step 2b, already computed at every
   decide).
   - If the record reads anything but OK (HALVE, KILL or UNMEASURED), the reduced build does not run. The
     session takes today's flatten path, and plan.json records the reason as a structured field.
   - This is **the first acting use of drawdown.py's status**. It can only remove risk: its only action is
     today's rule.
   - With the key absent, nothing reads it, so the no-op pins of §1.6 hold.
   - A test must fail without it.
6. **A dropped short flattens a reduced session** (the PM review's C4; §7.5). If `decide` drops any order
   that opens or increases a short on a reduced decision (gate 7: not shortable today), the reduced
   targets are not sent. The session takes today's flatten path instead, with the reason recorded.
   - A reduced book without its short leg is not the book this trial scored.
   - On a one-fund short side it is net long by the whole long side.
   - A test must fail without it.

**Why the guard is not moved to the floor.**
- **Re-neutralising a 3-name survivor set would recreate the 3-name degeneracy** that the floor exists to
  exclude: one side would be a single fund carrying half the gross. That happens when a 4-name set loses
  one name to the dust filter.
- **Two thresholds for one block is a second rule.** With the guard at the floor, a 5-name session with
  one dust name would re-neutralise while a 6-name session with two would not.
- **The alternative's effect is the same size.** The screen's sleeve check lowered `min_names` to 3 in
  memory, so on those 127 sessions it *did* re-neutralise. The largest weight difference from the harness
  was 0.0050 [S screen §2]. The declared rule differs from the harness by the dropped names alone, each
  under 0.005.

### 1.4 What does not change

The signal; the universe (13 names); every other frozen key; `sizing_multiplier`; the band; the ceiling;
`min_names` itself (6: still the line below which the full construction is not used); every gate; the
deferred-flip rule; the execution mode. **On any session with 6 or more eligible names the target is
identical under both rules** [V compose.py, before §A: te4 and the spec build the same target on every fit session with ≥ 6
eligible, asserted].

### 1.5 The files that would change (owned by the other session; listed, not edited)

| file | change |
|---|---|
| `ops/specs/cef_discount.frozen.json` | the two keys and the note; v9 → v10 (`/spec-change`) |
| `src/deploy/registry.py` | `CEF_BELOW_MIN_NAMES` gains `"trade_eligible"`; a new `cef_below_min_names_floor(frozen)`; `_validate_cef_discount`; the misspelling guard's key list (`CEF_C4_KEYS`, 2 edits) gains `below_min_names_floor` |
| `src/deploy/sleeves/cef_discount.py` | the `min_names` block (l.878–946): the reduced branch, run only with no holds present (§1.3 item 3), the 0/0 raise, `meta["cef_reduced_set"]`; the paper declaration at construction (§1.2); a comment at l.965 saying the guard is deliberately left at `min_names`; the module docstring |
| `quantt/session/run.py` | the paper declaration and the endpoint check (§1.2); K0 (§1.3 item 5); the gate-7 flatten (§1.3 item 6); plan.json's structured eligible count, `reduced` flag and the reason K0 or gate 7 stopped a reduced build |
| `quantt/session/drawdown.py` | **required in the activation release:** report-mode lines for K0–K3 (K0: the account against HALVE during an open episode; K1–K3 against their read-date thresholds), tested. Trial 53's R1 line was deferred ("not built in this pass"), and the PM review's point stands: a stop that lives only in a document is a stop nobody reads (§6.3) |
| `scripts/cef/spec.py`, `ops/orient.py` | expose and print the key (SPEC), as for `sizing_multiplier`; spec.py as `BELOW_MIN_NAMES_FLOOR`, which compose.py reads once it exists |
| tests | `src/deploy/tests/test_below_min_names_trade_eligible.py` (the reduced target equals `band_frontier._target_row` then the band and the cap, on synthetic panels and on the real fit panel; floor validation; no reduced build with holds present, and the runner's missing-NAV refusal unchanged; the 0/0 raise; the guard). `quantt/session/tests/test_trade_eligible_noop.py` (pins, §1.6). The paper-declaration tests (sleeve and runner), the K0 test and the gate-7 test. **Each fails against the old code before it is kept** (CLAUDE.md) |
| a scorer | a read-only script that computes §4's statistics from `<state>/eod_equity.csv`, plan.json, the fills and the closing prints, including the flatten shadow (§4.4); required in the activation release |
| the revert spec | `below_min_names` set back to `"flatten"`, built through `/spec-change` and tagged in the activation release, so that a revert on K0–K3 is an install, not a build (§6.5) |
| `docs/RUNNER.md`, `docs/SYSTEM.md` §5, `docs/RESEARCH_STATE.md`, `docs/JOURNAL.md` | the rule, the paper-only ruling, the ledger (§9) |

### 1.6 The no-op proof and the revert

`/spec-change`'s proof, before the key is set:
1. **Key absent**, and **`below_min_names: "flatten"` written explicitly**: the sleeve's targets,
   plan.json, the orders and plan_sha are byte-identical to v9's code. They are pinned from the code
   *before* the change, as `quantt/session/tests/test_c4_keys_noop.py` and `test_sizing_multiplier_noop.py`
   pin theirs.
2. **Key set, on every real-panel date with ≥ 6 eligible**: the targets are byte-identical to v9's. That
   is every date since 2023-08-31 [S screen §7]. The diff covers every such date on the live panel, not a
   sample.
3. **Key set, on a reduced date**: the targets equal `band_frontier._target_row` → band → `_cap_gross` on
   the same panel, to ≤ 1e-12, except names under `min_abs_weight` (§1.3). The screen's sleeve check is
   the model (`sleeve_reduced_check.py`).

**REVERT:** `below_min_names: "flatten"`, or delete both keys. The spec id moves again through
`/spec-change`, and pin 1 proves the reverted sleeve is v9's. Or restore it whole with
`git show spec-cef_discount.v9.20261102:ops/specs/cef_discount.frozen.json`.

---

## 2. Why, mechanically — and every finding against it, first

### 2.1 Against: what the screen's attacks found (all [S screen] unless marked)

| # | finding | figure |
|---|---|---|
| 1 | **At matched turnover (H2) it is under the bar.** te4 trades 2.3× flatten's fit turnover (19.3 against 8.5/yr). Re-banded to flatten's turnover (the device declared before the first run), the gap is INCONCLUSIVE | **+2.13pp/yr, NW t 2.34** against the bar 2.818 at N = 53; interval [−0.87, +5.14]. Unmatched it reads t 4.51, but that is not an H2 comparison |
| 2 | **Two names.** | without PHK's and PDI's own P&L: +1.08 (t 1.43). A universe rebuilt without them: +2.23 (t 3.55), from 2020–22 only. The methods disagree; both are shown |
| 3 | **One sponsor.** | the six PIMCO funds carry +3.63 of +4.19pp/yr (87%); the other seven names +0.56 |
| 4 | **Independent episodes are at the bar, not over it.** | 9 fit episodes, all positive, t 3.68 against a t(8) critical value of 3.86; sign test p 0.0020 against 0.00242 |
| 5 | **The holdout does not show it.** | 2023+: +0.87pp/yr (t 0.72), one 138-session episode (+3.02pp); direction control p 0.242. **H13 is now seen for this rule** |
| 6 | **Forward power is inadequate.** | P(pass) 0.47 at 5 episodes at the fit effect (normal approximation, generous); 0.07 at the shrunk effect; 7.0 years at the fit-period rate, 18.4 at the rate since 2023 |
| 7 | **Against hold it is not robust.** | matched turnover −0.26 (t −0.30) |
| 8 | **Not every metric favours it.** | flatten has the shallowest drawdown in every window from 2015 on, and the best H13 Sharpe (2.07 against te4's 2.01) |
| 9 | **The hindsight universe.** | 77% of fit earning days (3,484 of 4,531) follow a thin decision, because the 2026 universe is projected back into years when most of it was illiquid. **These files cannot measure that hindsight.** Forward thin sessions, if any, come from one name's ADV dipping, which is a different process |
| 10 | **Concentration.** | a single name holds ≥ 0.5 of NAV on 27% of thin sessions, against 10% of active ones [S beta-detector]. At ×1.30 the held book's largest name is 0.498 of NAV at the median and 0.956 at the fit maximum [V §E] |
| 11 | **Band residues below the ADV floor.** | about 10 names held on a 4–5-name session, most at their band edge |
| 12 | **The signal decays fast.** | half the thin-day P&L is gone when the signal is 5 sessions old; a static tilt loses money (−1.63) |

### 2.2 For: the gross case, and its mechanism

- **The score.** te4 has the highest gross return in every window and with both flip modes. Fit: 5.77
  (instant) / 5.35 (deferred) against hold 3.29 / 3.16 and flatten 1.58 / 1.46%/yr. 2023+: 11.50 / 10.95
  against 10.61 / 9.85 and 10.63 / 10.34 [S screen §3].
- **Why gross.** The paper account is scored on gross P&L, with no borrow and no execution cost (team lead
  D19/D20, 2026-09-15). **That is the reason the team lead chose paper.**
- **The mechanism** [U, a reading]. The z-score's relative-value bet does not need six names to be
  defined; it needs a cross-section in which no side is forced onto one fund (§3). Flattening discards the
  signal on exactly the days it still exists.
- **Where the gap comes from.** It is real gross P&L on the panel, and its sign follows the signal:
  - not factor beta: alpha +6.26pp/yr (t 4.41), every |β| ≤ 0.06;
  - not stale prices: it survives one extra session of delay, +3.06 (t 3.62);
  - not distributions: the price leg is +4.22 of +3.94;
  - the direction matters in the fit: p < 0.002 over 500 reassignments.

  [S screen §6]
- **On paper the comparison is gross**, and the cost grid shows what the extra turnover would cost
  (§2.3). Against flatten the fit gap stays positive across the grid: +3.65 / +2.58 / +0.96pp/yr at 5 /
  15 / 30bp. In 2015–19 it flips at 30bp (−1.98) [S screen §3].

### 2.3 Real money: negative where borrow is measured

| measured window | te4 − flatten, gross → net of borrow |
|---|---|
| 2021-09-14 → 2022-12-30 | +7.72 → +2.79pp/yr (borrow took 64%) |
| 2023-01-03 → 2026-09-03 | **+0.87 → −2.33pp/yr** |
| before 2021-09-13 | **UNMEASURED** (the IBKR FEE_RATE panel starts then) |

[S screen §5]
- **A back-cast, not history** [S screen, U]: the fit at each name's median fee is +2.21; at its p90 fee,
  −2.67.
- **Why borrow takes it.** te4's thin-day shorts paid 27.9%/yr, size-weighted, in 2023, against a 6.7%
  median fee for the same names. The signal shorts rich funds when they are dear to borrow [S
  beta-detector].
- **Capacity** [U]: real money would also meet band residues below the ADV floor, and a least-liquid
  eligible name near 1.13× the floor.
- **This is why the rule is paper only (§1.2).**

### 2.4 The graveyard

Nothing in `docs/RESEARCH_STATE.md`'s KILLED tables is a thin-session rule [V, read 2026-11-03].
- **The nearest relatives** are "sizing up on |z|" and "sizing up on dislocation". Both are conditional
  sizing. This rule changes which sessions the unchanged construction runs on, not how it sizes.
- **The usual causes of death were checked** by the screen. A stale-price artefact: zero-return name-days
  4.22% on thin days against 4.70% on active ones, and no zero-volume day. A control scoring as well as
  the treatment: the direction control passes in the fit (p < 0.002) and **fails on H13 (p 0.242)** [S
  screen §6].

---

## 3. How the floor was derived

**From what the construction does at each count n** (the screen's §1, written into the harness's
docstrings before its first scoring run; the build is one commit, so git cannot show that order) [S
screen]:

| n | w = −(z − z̄) / Σ\|z − z̄\| | breaks? |
|---|---|---|
| 1 | z − z̄ = 0, so 0/0 | **undefined** |
| 2 | w = ±½ whatever \|z₁ − z₂\| is: the sign only, and each crossing reverses the whole book | **sign only** |
| 3 | the demeaned values sum to 0, so one side is one fund carrying ½ of the gross | **forced single-fund side** |
| 4 | a 2–2 split is possible; one side is a single fund on 27.3% of 4-name and 16.0% of 5-name sessions [S] (19.1% of fit reduced decisions [V §E]) | possible, not forced |

**The floor is 4**: the smallest count with none of the three degeneracies. Below it the rule does what the
sleeve does today, FLAT.

**The plateau (H8)**, read on the fit only [S screen §4]:

| floor | te − flatten, FIT, pp/yr (NW t) | per unit share of sessions traded |
|---|---|---|
| 3 | **+4.59 (4.61)**: the argmax | +10.83 |
| **4** | **+4.19 (4.51)** | +12.10 |
| 5 | +3.17 (3.74) | +12.42 |

- **The argmax, floor 3, is not chosen.** It is the count the derivation excludes: 3 names force a
  single-fund side. Choosing it would be choosing the sweep over the construction (the `z_window = 63`
  lesson).
- **4 sits on a plateau.** The sign is the same at all three floors in every fit era where they differ,
  and the edge per traded session is nearly flat. The floor sets how many sessions trade, not what each
  earns.
- **H13 could not have steered it.** Since 2015 every thin session has had 4 or 5 eligible names, so te3
  and te4 are the same book from 2015 on, and all three floors are identical on H13.
- **Not re-tuned live.** The next legitimate change to the floor is a re-derivation from the construction
  (for example, if `min_names` or the construction changes), never a re-sweep.

---

## 4. Committed in advance: the evaluation, forward only

### 4.1 What evidence is clean

**Only forward thin episodes.**
- The fit (2005–22) is in-sample for the screen.
- 2023+ was printed by the screen, so H13 is seen for this rule.
- **No historical window is clean**, and none is re-read as evidence here.
- compose.py reads fit rows only, to state composition and calibrate stops. It judges nothing.

### 4.2 The unit: thin episodes, not days

| term | definition (committed) |
|---|---|
| reduced decision | a decide on which **the sleeve's reduced build ran and its targets were sent**: plan.json's structured `reduced` flag is true (§1.3), read from the field, never re-derived from a reason string or from the eligible count. **Revised after the quant review, finding 2.** As first drafted the definition was the count `floor ≤ eligible < min_names`. A whole-book hold also records an eligible count of 4–5, so the count alone would have scored a held full book as a reduced decision |
| held-book day | a decide inside an open episode with `floor ≤ eligible < min_names` on which the reduced build did not run because a hold was present (§1.3 item 3). **Not a reduced decision.** Reported beside E_k (§4.4) |
| K0 / gate-7 flatten | a decide on which K0 or gate 7 stopped a reduced build (§1.3 items 5–6). The session takes the flatten path, so it earns 0 under both rules, and it is counted as a below-floor decision |
| below-floor decision | eligible < floor: flat under both rules (both earn 0 on its earning day) |
| thin earning day | the session two sessions after a reduced decision: decide at t (evening), late-market fill at t+1, earn t+1 close → t+2 close (shift(2)) |
| episode | runs of reduced decisions merged when **fewer than 63 sessions** apart: `build_panel`'s ADV window, the screen's rule (`third_rule.episodes`). Below-floor decisions inside it contribute 0; held-book days are reported beside it, not in it |
| completed | 63 sessions after its last reduced decision with no new one; an episode is read only when complete, so the merge is final |

Why episodes, not days.
- The days inside an episode share one liquidity state and one trailing-ADV window, so they are not
  independent.
- The screen's day-level reading (t 4.51) overstates the evidence 9 episodes give (t 3.68) [S screen].

### 4.3 The per-episode statistic, and its counterfactual

**E_k (the paper score; gross; broker-confirmed)**: the sum of the account's daily return of record
over the earning days of episode k's reduced decisions (its thin earning days).
- The daily return is equity_d / equity_{d−1} − 1, with no cash flows on paper.
- Equity is read from Alpaca's end-of-day portfolio history, `<state>/eod_equity.csv`: the official P&L
  (team lead 2026-10-19), the series the drawdown report already reads.
- It is price only: paper pays no distributions.
- No cost and no borrow are charged.

**The flatten counterfactual is exactly zero on those days.** Flatten holds no book after a reduced
decision, so E_k needs no model. It is te4's P&L minus flatten's, as the screen's episode value is
(compose.py §A2 reproduces the screen's nine values from this definition to 1e-17).
- **Why exactly zero, in the live code.** A reduced decision has no hold present (§1.3 item 3). With no
  hold, today's sleeve returns every name FLAT and tags nothing (l.929–932), so the runner has nothing to
  refuse, and the flatten book is flat after it.
- This is why the definition keys on the `reduced` flag. On a held-book day, flatten's book is not flat:
  either the whole book holds or the runner refuses the day.
- **Three parts of the difference are not in E_k**, and are labelled beside it (§4.4):
  - the re-entry trades flatten would make and te4 avoids, including those between the runs of a merged
    episode;
  - the slightly different book te4 carries into the full sessions after a run, between runs and after
    the episode;
  - the held-book days (§4.2).
- **The last minutes before the t+1 late window** are not in E_k either. Both rules hold the same book
  until then [U: small].

### 4.4 Labelled beside E_k, never mixed into it

| column | what | provenance |
|---|---|---|
| **E_k, closing-print view** | the same days, with positions marked at the official closing-auction prints and each late fill replaced by that session's official print | modelled on broker positions; CLAUDE.md's "record both", labelled separately |
| **net at 5 / 15 / 30bp** | E_k − c × (te4's traded notional − flatten's counterfactual notional) / NAV, **both counted over every decision from the episode's first reduced decision to the first decision after its last reduced one, the full sessions between runs included**. Flatten's notional is that of the flatten shadow: the sleeve read-only with the key absent, started from the account's held book at the episode's first reduced decision, marked at closes. Over a merged episode it exits and re-enters once per run. **Say whether the sign flips across the grid.** *Revised after the quant review, finding 3.* The first formula counted flatten's notional as one exit plus one re-entry, and te4's over the reduced decisions only. On the fit at ×1.30 with deferred flips, 6 of the 9 episodes have two or more runs. In five of them flatten's true notional was 4 to 14 times the formula's (21.04 against 1.46 NAV for 2020-06-23), and the formula overstated te4's extra cost: net at 15bp understated by 0.41–1.37pp of NAV per episode. In the sixth, 2010-05-05, flatten held no book beforehand, and the formula understated te4's cost by 0.13pp [V rc §R10] | te4's leg from broker fills; **flatten's leg MODELLED** (the shadow) |
| **held-book days** | each decide inside an open episode on which a hold stopped the reduced build (§1.3 item 3), with the account's P&L of record on its earning day and the flatten shadow's beside it; the count of such days per episode | broker-confirmed for te4; **flatten's MODELLED**. Never in E_k or a verdict |
| **core ex-te4** | the account's P&L of record with the earning days of reduced decisions set to 0 (flatten's earnings there, exactly), shown **beside the account series in every report of the core's P&L**. It omits the re-entry leg R_k and the cost difference, so it approximates flatten's account and is not that account. **A real-money case cites ex-te4, never the account series** (the PM review's C6) | broker-confirmed, as E_k |
| **borrow it would have paid** | Σ over thin earning days of short market value × fee / 360 × 1.02, `bf.borrow_charge`'s definition, from the freshest measured fee covering those dates | **UNMEASURED today, and so stated, never a default.** The IBKR FEE_RATE panel ends 2026-09-09 and IBKR is retired; Alpaca paper has no locates and no borrow fees |
| **re-entry leg R_k** | over the 63 sessions after the episode, the account's P&L of record minus the flatten-shadow book's (the sleeve read-only with the key absent, from flat, marked at closes) | **MODELLED**; never in a verdict. Fit analogue: +0.25 of +4.19pp/yr [S screen §3] |
| **concentration and net** | each reduced session's realised largest \|position\| / equity and \|net\| / equity, from Alpaca positions at the close | broker-confirmed; feeds K2 and K3 |
| **turnover** | te4's and the counterfactual's per episode. **H2 cannot be matched live** (the book has one band); the fit's matched comparison is INCONCLUSIVE (§2.1) | as above |
| **attribution** | E_k by name and by sponsor; E_k without PHK's and PDI's own P&L | broker positions × closes |
| **direction control** | the episode's reduced-set weights reassigned at random among the same names, 500 draws, seed 20261103 + k, → p | **MODELLED** on the panel; a negative control, not a decision rule |

**Negative control.** On every full session (≥ 6 eligible) te4 and flatten build the same target, so the
mechanism cannot act there. **Outside the 63-session re-entry window**, any difference between the
account's targets and the flatten shadow's is an implementation fault, to be found, not scored.

### 4.5 Conventions

- shift(2), the late-market send (8 to 2 minutes before the close), deferred flips: as the live runner.
- **Gross P&L is the headline**; the cost grid is the real-money view, beside it. Borrow is separate.
- The bar is √(2 ln N), with **N read from `docs/RESEARCH_STATE.md` (orient TRIALS) on the read date**,
  never from this note.
- **The floor is not re-tuned**, and **no verdict reads a 2023+ or fit return.**

---

## 5. What we expect

Each figure has its uncertainty; being wrong here is the point.

1. **Now: nothing.**
   - No session has been thin since 2023-08-30: 783 sessions to 2026-10-14. 192 sessions had exactly 6
     eligible names, the last on 2026-02-12 [S screen §7; S thin-days §5.I].
   - Until a thin session occurs, the key is inert, and the book is v9's.
2. **The forward rate is unknown.**
   - It was 0.71 episodes a year over the fit, 0.27 since 2023, and 0 since 2023-08-30 [S screen §6.M].
   - **What moves it** is one name's ADV dipping under $3m. On 6–7-name sessions since 2023, the least
     liquid eligible name sat at a median 1.13× the floor, p10 1.03× [S screen §7]. On 2026-10-14 AWF was
     just under it, at $2.97m [S thin-days §5.I].
   - Re-measure at run time: the eligible count is in plan.json every day.
3. **Per thin earning day, gross**: about +5.5 to +11.4%/yr of unit book. The low end is the holdout's
   rate and the high end the fit's [S screen §6.M].
   - At ×1.30 that is **about +2.8 to +5.9pp of NAV per 100 thin earning days** [U: × 100/252 × 1.30].
   - The holdout's rate is the only out-of-sample analogue, so expect the low end.
4. **Per episode.**
   - Fit episodes at ×1.30 with deferred flips, price only: mean +9.95pp, median +7.82pp; 8 of 9 positive;
     lengths 28 to 390 thin earning days, median 195 [V §F].
   - **Forward episodes from a one-name dip may be much shorter.** The per-episode effect then shrinks
     roughly with √length: about 1.71 × √(L/252) at the screen's day-level Sharpe [U]. That is 0.48 for a
     20-day episode, and power falls with it (§6.2).
5. **Per year, if thin sessions recur at 2023's share (15%)**: about +0.8 to +2.0pp/yr gross at ×1.13 [S
   screen §7], so roughly +0.9 to +2.3 at ×1.30 [U: scaled by 1.30 / 1.13, so 0.8 × 1.150 = 0.92 and
   2.0 × 1.150 = 2.30; the cap makes this approximate. The first draft printed +1.0; corrected after the PM
   review].
   - On real money the same rows read −2.9 and −2.1pp/yr at ×1.13, after extra turnover at 15bp and 2023+
     borrow [S screen §7]; more negative at ×1.30, since both costs scale with the book [U].
6. **Risk inside an episode** at ×1.30 with deferred flips, from the fit [V §E, §F]:
   - within-episode drawdowns of 2.2–8.9%;
   - the largest single name 0.53–0.96 of NAV;
   - a one-session \|net\| that can reach 0.83 after a deferred flip (§7.6).

---

## 6. What would falsify it, what kills it, and the revert

### 6.1 Verdicts, read at each completed forward episode

| verdict | rule (committed) | action |
|---|---|---|
| **H-TE PRESENT** | **read only at k = 5, 9, 13 and 20 completed episodes.** At such a k: the one-sample t of E_1..E_k ≥ the t(k−1) critical value at **p / 4**, where p is the bar's one-sided p (bar √(2 ln N), N read on the read date). **And** the same t on E_k without PHK's and PDI's own P&L (attribution) is > 0: the screen's two-name finding, declared as a gate (§2.1 row 2). The exact sign-flip p is reported beside it. After k = 20 PRESENT is not read again | keep; recorded with its D-code, **labelled "unmatched (H2)"**: te4 trades more than flatten, and with one band on the book no live turnover match exists (§4.4). Promotion to real money still needs the real-money gates (§1.2) and a new ruling |
| **H-TE ABSENT** | E_1 < 0 and E_2 < 0; **or** at any read with k ≥ 3, mean(E_1..E_k) ≤ 0 | **revert the same day** (§6.5) |
| **KILLED (risk)** | any of K0–K3 (§6.3) | **revert the same day**; the episode values to date are recorded |
| **INCONCLUSIVE** | none of the above | keep. The team lead reviews at each completed episode and at each anniversary of activation, with this note's power table in hand |

**Why the declared reads** (revised after the quant review, finding 4).
- As first drafted, PRESENT was tested at every completed episode against the bar's single-read p
  (0.00237 at N = 54).
- Under the null, with the ABSENT stop applied, the chance of a false PRESENT then accumulates: 0.79% by
  episode 5, 1.50% by 13 and 1.79% by 20 [V §G2, 400,000 paths]. That is 6–8 times what the bar allows,
  so such a PRESENT would not be comparable with a single-read pass at the same bar elsewhere in the
  repository.
- **Declared now: four reads, each at p / 4 (Bonferroni).** The family-wise rate is at most p by
  construction; simulated, it is 0.21% by episode 20 [V §G2].
- ABSENT is still read at every completed episode. A futility stop can only lower the false-PRESENT rate.
- The alternative, one read at k = 13 at p, has more power at 13 (0.74 against 0.54) and none before it
  (§10 Q11).

**Why this falsifier.** P(ABSENT by the third episode) is 3.1% if the fit effect is true, 18.8% at the
holdout-shrunk effect and **52.7% if the rule earns nothing** [V §G, 200,000 simulated draws]. It is a
coarse test against zero, and the honest one that this many episodes allow. **The rules are not
softened later.** Extending the episode count, adding a read, lowering the bar or dropping the PHK/PDI
gate is a new trial.

### 6.2 Power: forward P(PRESENT) by number of episodes

Per-episode effect (mean / sd) of the fit episodes at ×1.30, deferred, price only: **1.16**; at the
holdout's shrink (×0.49): **0.56** [V §F, §G]. Bar at N = 54 shown (2.825); N = 53 and 55 differ in the
third decimal [V §G].

| episodes k | t(k−1) critical, single read | **declared reads: P(PRESENT by k)**, fit / shrunk | single read at k: exact t / normal approximation, fit | single read at k: exact t / normal, shrunk | years at 0.71/yr | years at 0.27/yr |
|---:|---:|---|---|---|---:|---:|
| 3 | 14.48 | 0 / 0 (not a read) | 0.023 / 0.21 | 0.009 / 0.03 | 4.2 | 11.0 |
| 5 | 5.68 | **0.03** / 0.01 | **0.098** / 0.41 | 0.021 / 0.06 | 7.0 | 18.4 |
| 9 | 3.87 | **0.22** / 0.03 | 0.43 / 0.74 | 0.065 / 0.13 | 12.7 | 33.0 |
| 13 | 3.46 | **0.54** / 0.06 | 0.74 / 0.91 | 0.13 / 0.21 | 18.3 | 47.7 |
| 20 | 3.20 | **0.87** / 0.16 | 0.96 / 0.99 | 0.29 / 0.38 | 28.1 | 73.4 |

- **The declared-reads column is the trial's.** It is simulated with the ABSENT stop [V §G2]. Under the
  null its false-PRESENT rate is 0.06 / 0.11 / 0.16 / 0.21% by k = 5 / 9 / 13 / 20.
- **The single-read columns** are context. Exact power is from the noncentral t. The normal approximation
  is the screen's `inference.p_clear_bar` and is generous at small k [V §G].
- **The exact single-read power first passes a coin flip at k = 10 (0.52)**: 14.1 years at the fit-period
  rate, 36.7 at the rate since 2023 [V §G2].
- Years are k divided by the rate [U on S screen §6.M rates].

**Reading.** PRESENT is out of reach for a decade or more, and shorter forward episodes (§5 item 4) push
it further. **This trial measures gross paper P&L and risk on thin sessions; it does not establish
alpha.** That is said here, before any session trades it.

### 6.3 The stops: K0 on the account, K1–K3 inside an episode (H14: every threshold re-measured)

**Why K0 exists** (revised after both reviews: quant finding 1, PM F1).
- As first drafted, the stops were split by session type. R1–R3 read full sessions (§7.3's
  recommendation (a)), and K1 read the episode's reduced sessions. HALVE and KILL read the whole account,
  but they are report only.
- **On the fit's own path every acting stop stayed silent while the account crossed HALVE.** At ×1.30 with
  deferred flips, the account fell 13.76% price only from 2017-06-02 to 2018-06-05. Of that window's 253
  earning days, 185 reduced days compounded to −7.59% and 68 full days to −6.67%.
- The account first reached 12% on 2018-05-08 (2018-05-23 on total return), inside the 2017-06-21
  episode, which began with the account already 2.56% below its high. On that date:
  - R1's population (full days joined) read 6.67%, against R1's 10.14%;
  - K1's population read 7.22%, against D_E's 10.52%. [V rc §R1]
- So one drawdown was split into two populations, each below its own line.

Thresholds below are **drafting-day values only**. K1–K3 are recomputed on the read date by
`python3 results/cef/prereg_thin_te4/compose.py --stamp <read date> --k3-run-sessions <n>` (§E). The script
reads m, the band, the ceiling and `min_names` from the frozen spec at run time, and the floor from the spec
once the key exists. (Corrected 2026-11-05, the runner owner's round-2 answer (c): `--k3-run-sessions`, the
spec's `risk.thin_k3_run_sessions`, is now required and recorded in `compose_<stamp>.json`; the command read
`--stamp <read date>` alone until then.)
K0 needs no re-measure: `drawdown.py` reads the spec's `risk.halve_drawdown` at every decide.

| stop | statistic (live, broker-confirmed) | threshold: rule (drafting-day value) | fit check |
|---|---|---|---|
| **K0, the account** | the account's drawdown from its high-water mark on the P&L of record, as `quantt/session/drawdown.py` measures it at every decide (`<state>/eod_equity.csv`) | the spec's `risk.halve_drawdown`, read at run time (0.12 on drafting day) | on the fit at ×1.30 with deferred flips the account crossed it on 2018-05-08 (price only), inside the 2017-06-21 episode, while K1's population read 7.22% and R1's 6.67%: neither fired [V rc §R1] |
| **K1, drawdown** | the running maximum drawdown of the account's P&L of record, compounded over the episode's thin earning days joined end to end, from the episode's start | **D_E**: the 95th percentile of the 252-session maximum drawdown of te4's reduced-session earning-day series on the fit, at the spec's m, deferred flips; the largest of SB21 / SB63 / GAUSS; the worse of TR and PR. Trial 53's R1 construction on reduced sessions (**10.52%**; 21 / 63 / 126-session values 4.13 / 6.62 / 8.51% printed for context) | no fit episode reached it: worst 8.90% PR, 2017-06-21 → 2018-12-19 [V §F] |
| **K2, single name: a fault detector** | on any reduced session's close, the largest \|position market value\| / equity | **above the fit maximum** of the same statistic for te4's held book at the spec's m, deferred (**0.956**) | by construction, never on the fit; the fit p99 is 0.891 |
| **K3, net** | on reduced sessions' closes, \|long − short market value\| / equity | **above the fit p99 on 3 consecutive reduced sessions (0.248)**, or **above the fit maximum once (0.833)** | the 3-in-a-row rule never fired on the fit; 2-in-a-row happened once [V §E] |

**K0, exactly** (the PM review's C1, adopted).
- **It acts in code and fails closed** (§1.3 item 5). On any decide that would run a reduced build, the
  build is sent only if the decide's drawdown record reads OK. HALVE, KILL or UNMEASURED makes the session
  flatten, today's rule, with the reason recorded in plan.json.
- **HALVE or KILL read on any decide from an episode's first reduced decision until the episode is
  completed is also KILLED (risk).** The team lead reverts the key the same day, by installing the revert
  spec built in the activation release (§1.5).
- **UNMEASURED flattens the session but does not kill the trial.** A missing measurement is not a
  drawdown.
- **If HALVE or KILL ever gains an acting `on` mode, K0 still applies**: at HALVE the reduced build is
  off, not halved.
- **What K0 buys**, zero edge, 12 months, on te4's W1 trading series with the session type carried by the
  bootstrap [V rc §R3]:

  | book, price only | SB21 P(HALVE) / P(KILL) | SB63 P(HALVE) / P(KILL) |
  |---|---|---|
  | te4 at ×1.30, no K0 | 14.71% / 1.27% | 16.68% / 2.27% |
  | **te4 at ×1.30 with K0** | **14.71% / 0.13%** | **16.68% / 0.38%** |
  | te4 with reduced days at ×1.07 (m_r), no K0 | 9.02% / 0.35% | 11.67% / 0.93% |
  | flatten at ×1.30 (the anchor) | 9.35% / 0.40% | 10.89% / 0.59% |

  On total return K0 takes P(KILL) from 0.82% to 0.10% (SB21) and from 1.68% to 0.29% (SB63).
  - These are not comparable with compose §D2's worst-of figures, which include GAUSS. GAUSS cannot carry
    the session type. Compare within this table only.
  - K0 is modelled as: once the path reaches HALVE, reduced-day returns are 0 from two sessions later, and
    flatten's re-entry is ignored [U: an approximation].
  - **K0 leaves P(HALVE) unchanged, because HALVE is its trigger. It takes P(KILL) to the flatten book's
    level or below.**
  - Its cost at the fit edge is at most 0.04pp/yr in the same bootstrap [V rc §R3].
- **What K0 does not buy.**
  - On the one historical path K0 fires on 2018-05-08. It does **not** lower that path's maximum
    drawdown: 13.76% → 13.46% price only, and 13.79% → 13.86% on total return. The rest of that drawdown
    came from full sessions [V rc §R2].
  - It gives up the rest of that episode: te4 made +3.57pp from the splice to the episode's end, against
    −0.45pp after the splice.
  - As a kill it also gives up every later episode: W1 price-only return falls from 12.15%/yr to 7.53%/yr,
    against flatten's 3.87% [V rc §R2].
  - The downside if K0 is wrong: it kills te4 at the bottom of a core drawdown, one the reduced sessions
    may not have caused, and gives up the rebound.
- **One interaction to measure before activation.** Whether the EOD row for date D exists by the 22:00 ET
  evening decide "is not established" (`drawdown.py`'s docstring). If the evening decide routinely reads
  UNMEASURED, K0 as written makes te4 inert: every reduced session flattens. That is safe, but the trial
  would never trade.
  - **Re-measure it at run time**, from the run records' `drawdown.status` on the decides since the EOD
    series shipped.
  - If UNMEASURED is routine at the evening decide, the remedy is the drawdown record's timing (the
    peer's), never a looser K0.
  - If it is rare, K0 stands as written.

**K1, two limits** (the PM review's C7, and the quant review's secondary point).
- **Blind in short episodes.** K1's line is the 12-month p95 from day one. At 21 thin earning days the same
  construction's p95 is 4.13% [V §E]. In a short episode, K0 is the only operative drawdown stop.
- **Long episodes.** D_E is calibrated over 252 earning days, but fit episodes ran to 390, so on a long
  episode K1 fires more often than its 5% design [U].
- **The alternative (the team lead's choice, not recommended):** read D_E at the elapsed length, rounded up
  to the next of 21 / 63 / 126 / 252. On the fit it fires once in nine episodes (2017-06-21, price only:
  8.88% within 126 thin earning days, against 8.51%), and never on total return [V rc §R9]. It is not
  recommended over K0: it reads four lines per episode, each at its own 5% design, so its false-alarm
  rate per episode is above 5% [U].

**K2 is a fault detector, not a concentration limit** (the PM review's C2, with one correction).
- Whenever a side is a single fund, the construction puts about half the gross in that fund. That is
  19.1% of fit reduced decisions: the short side on 10.3%, the long side on 8.8% [V rc §R5].
- The ceiling bounds the fund at about ½ × `max_gross_stress` × NAV = 0.9.
- **The fit maximum, 0.956, is above 0.9** even though the harness re-applies weights every session and
  has no price drift. The excess comes from the band, which leaves the two sides unequal. (The PM review
  attributed it to drift.) Live, price drift of held shares adds to it.
- K2 therefore fires only on drift beyond the fit's band imbalance, or on a construction fault.
- Concentration itself is accepted; its price is in §7.4.

**Under either outcome of a K1–K3 re-measure:**
- **compose.py moved.** Revised after the quant review, finding 6. compose.py used to raise whenever the
  flatten book did not reproduce trial 53's 2026-11-02 json files, so a /spec-change of the band or the
  ceiling, or a revised fit row, forced a revert. It now asserts only that every scored book equals an
  independent row-by-row loop at the read date's spec (§A1). It **reports** whether the drafting-day
  references still reproduce (§A2). It writes `compose_<stamp>.*` and never overwrites another date's
  record.
- **If the read-date threshold has moved**, because m, the band, the ceiling or the panel's fit rows moved,
  the new value governs. §A2 says which inputs moved. The note's numbers do not govern.
- **If compose.py cannot run**, the threshold is **UNMEASURED**. That covers a missing panel, the
  independent loop disagreeing, a changed ADV window and a holdout leak. The rule is then to revert at the
  next reduced decision unless the measurement is restored first. A stop that cannot be read does not
  count as passed.

**Who acts.**
- **K0 acts in code** (above). Its KILLED verdict is acted on by the team lead the same day.
- **K1–K3: the team lead, through installing the revert spec, the same day a stop reads true.** No code
  acts on them; this follows trial 53's convention.
- **The K0–K3 lines in the drawdown report are REQUIRED in the activation release**, in report mode and
  tested (§1.5). Without them the key is not activated. Trial 53's R1 line was deferred ("not built in
  this pass"). A "should" here would risk becoming "never".

### 6.4 Stops that keep running, and the core's kill rule

- The spec's HALVE / KILL lines (12% / 18%, report only, `risk.drawdown: report`). They read the whole
  account. K0 now gives HALVE an acting consequence for this key only.
- Trial 53's R1–R3, read as §7.3 says.
- **The core's 60-session kill rule**: (a) live net Sharpe < 0; (b) slippage > 2× modelled for 5 sessions;
  (c) discount spread < 12%. No `.py` computes it; it is read by a human (the PM review, by grep).
  **te4 does not extend the core's rope** (the PM review's C6; the team lead's ruling, §10 Q8):
  - **(a) fires if live net Sharpe is below 0 on the whole account OR on full-session earning days
    alone.** This is stricter than today and never looser. Without it, te4's thin-day P&L could rescue a
    failing core.
  - **(c) is read on the spec's cross-section**, never on a reduced eligible set.
  - **te4 can trip (b)** through reduced-session slippage on names near the ADV floor, and no te4 stop
    comes first. That is accepted, and stated.
- **te4 activates only after the core's 60-session review has been graded** (C6). It costs nothing in
  expectation, because the key does nothing unless a session is thin. It keeps the core's first verdict
  free of te4. The review's date is UNMEASURED here: `python3 -m ops.orient` and
  `docs/RESEARCH_STATE.md` own the count.

### 6.5 The revert path

`below_min_names: "flatten"`, or both keys deleted, through `/spec-change` (§1.6). **The revert spec is
built and tagged in the activation release**, so that a revert is an install, not a build.
- **During an episode** the next reduced decision then flattens the whole book, as today. That is a full
  round trip, accepted as the cost of a kill.
- **Between episodes** a revert changes nothing that trades.
- A reverted trial is not re-opened without a new pre-registration and a new trial.

---

## 7. Composition with what is live

### 7.1 Does trial 53's multiplier apply on thin sessions under te4? Yes

The reduced build falls through to the same lines as a full session:
- the band reads held / (NAV × m);
- `_cap_gross` acts at `max_gross_stress / m`;
- the weights are emitted as m × unit.

So **m = 1.30 multiplies the reduced book**, and the ceiling stays at 1.8 × NAV. Nothing in this rule reads
m.

### 7.2 Do trial 53's figures move under te4? Yes, materially

Trial 53's exact-build rows, W1 (2013-06-25 → 2022-12-30). Every W1 thin session has 4 or 5 eligible
names, so under te4 the core trades on 100% of W1 against flatten's 43.6% [V §B]. compose.py §A2 reproduces
trial 53's committed flatten rows exactly (difference 0.0), and §A1 checks every book against an
independent loop.

| book (exact B, W1) | TR %/yr | SR | maxDD (PR) | vol while trading | held at the cap | zero-edge P(HALVE) / P(KILL), 12 months while trading |
|---|---:|---:|---|---:|---:|---|
| flatten ×1.30, instant (trial 53 as amended) | 3.78 | 0.805 | 8.26% | 7.10% | 15.2% | 16.0% / 1.54% (approved, cap model: 16.7% / 1.68% [S T53]) |
| flatten ×1.30, deferred (the live runner) | 3.50 | 0.726 | 8.48% | 7.29% | 13.6% | 17.1% / 1.75% |
| te4 ×1.30, instant | 11.90 | 1.492 | 13.27% | 7.97% | 19.9% | **23.2% / 3.28%** |
| **te4 ×1.30, deferred** | **10.90** | **1.361** | **13.76%** (2017-06-02 → 2018-06-05) | **8.01%** | **17.5%** | **23.2% / 3.28%** |
| te4 ×1.15, deferred | — | — | — | — | — | 16.7% / 1.69% |

[V §B, §D2]

**What moves:**
1. **The fit path crosses HALVE.** At ×1.30 the te4 book's W1 drawdown is 13.76%, past the spec's 12%
   line. The flatten book's is 8.48%. The crossing sits in the 2017–18 thin stretch, the same one that put
   the hold book at 14.84% before amendment 1 [S thin-days §6].
2. **The multiplier.** The 2026-10-29 rule (m_core = m_c4_rule × sd_c4 / sd_core, with m_c4_rule 1.2642 and
   sd_c4 0.003659 read from `flatten_remeasure_2026-11-02_m1.30.json` [S T53]):
   - fed te4's W1 trading-session sd, 0.004021, it gives **×1.1502 → 1.15**;
   - fed flatten's, 0.003556, it gives ×1.3007 → 1.30 [V §C].
3. **The odds.** At ×1.30 the te4 mix carries zero-edge P(HALVE) / P(KILL) of **23.2% / 3.28%** while
   trading, against the ~16–17% / ~1.5–1.7% the trial approved. At ×1.15 it carries 16.7% / 1.69%, back
   at the approved level [V §D2].
4. **The stops**, below.

**This trial never moves m** (the PM review's C5, adopted with one correction; recommended in Q2).
- **Why keep ×1.30.**
  - W1 is 56% thin sessions; the forward book has had 0% since 2023-08-30. When no session is thin, te4
    is the flatten book, so ×1.30 is right for it.
  - Cutting m to 1.15 would shrink every full session to pay for risk in episodes that may never come.
- **But only with K0** (§6.3).
  - As first drafted, this paragraph said the reduced-session risk was "better bounded where it arises, by
    K1–K3". The fit's own path refutes that. A drawdown spanning both session types passed every acting
    stop [V rc §R1].
  - With K0, zero-edge P(KILL) on te4's mix returns to the flatten book's level or below [V rc §R3].
  - **Without K0 this note does not recommend ×1.30.** Compose §D2's zero-edge P(KILL) of 3.28% is about
    twice the level trial 53 approved.
- **Re-measured at each completed episode and at each anniversary of activation (H14):**
  - s, the share of reduced decisions in the trailing 252 sessions, from plan.json's structured `reduced`
    flag;
  - m(s), trial 53's 2026-10-29 rule fed the mixture of the full- and reduced-session sd (`review_checks.py`
    §R4, to be extended to read live sessions).
- **What the re-measure triggers.**
  - If s = 0, te4 is the flatten book and trial 53's derivation is untouched.
  - If m(s), rounded down, falls below the spec's m, it is **reported to trial 53's owner as a changed
    input**. The amendment question is theirs. Meanwhile K0 bounds the tail.
- **Drafting-day values.**
  - m(0.15) = 1.2345, which rounds down to 1.23; m(0.564), W1's share, = 1.1505, which rounds down to 1.15
    [V rc §R4]. The latter matches §C's 1.1502 from the whole trading-session sd.
  - **Correction to the PM review.** The same mixture reads m(0) = 1.27, not 1.30. On the fit, te4's full
    sessions carry the band path of its reduced books into them, so their unit sd (0.003644) is above
    flatten's trading-session sd (0.003556) [V rc §R4; V §A2]. Forward, at s = 0, the books coincide and
    m is 1.30. The mixture is therefore a conservative approximation, by about 0.03.
- **Not recommended: m_r, a separate multiplier on reduced sessions.** Trial 53's rule fed the reduced-day
  unit sd alone gives m_r = 1.07 (raw 1.0781) [V rc §R3].
  - It adds a key, and it imports the hindsight universe's reduced-session sd.
  - It cuts zero-edge P(KILL) less than K0: 0.35% / 0.93% against 0.13% / 0.38%, SB21 / SB63.
  - It costs about 1.4pp/yr of fit-edge mean on the W1 mix (12.17% → 10.74%) [V rc §R3].

**Disclose either way.** Under te4, trial 53's W1 figures describe the book only while no thin session
occurs.

### 7.3 R1–R3 and HALVE / KILL: do they need anything? Yes, one decision

- **Under flatten**, a thin session is flat and "cannot trip any stop" [S T53 FLATTEN_REMEASURE §4].
  **Under te4** thin sessions trade, so R1–R3 become live during an episode, on a book their calibration
  never contained.
- **How they behave on te4's fit mix, at ×1.30 with deferred flips** [V §D, fit edge, SB21; nominal 5%]:
  - **the approved R3 (12.07%) fires 8.3% of the time**: spurious reverts of the raise, caused by te4's
    higher vol;
  - R2 fires 4.0%, R1 2.7%.
- **Recalibrated on te4's trading sessions** (exact build): R1 10.75%, R2 −2.48%, R3 15.66%. The
  exact-build flatten reference, deferred, is 10.68% / −3.26% / 12.41%, beside the approved cap-model
  10.14% / −3.06% / 12.07%.

**Recommended (Q3): (a) read R1–R3 on full-session earning days only** while this key is set: the sessions
after a decision with ≥ 6 eligible, joined end to end. **Only with K0.**
- That is exactly the population trial 53 calibrated them on: the flatten book's trading sessions *are*
  the full sessions.
- This trial's K1–K3 cover the reduced sessions. Each trial is then judged on its own sessions, and
  neither trips the other's stops.
- **(a) alone splits one drawdown into two populations, each below its own line** (both reviews).
  - On the fit, the account reached HALVE on 2018-05-08. R1's population then read 6.67%, and its worst
    over W1 was 7.36%, against 10.14%. K1's population read 7.22%, against 10.52% [V rc §R1].
  - K0 is what covers the account during an episode (§6.3).
- **Alternative (b):** recalibrate R1–R3 on te4's trading sessions (exact build: 10.75% / −2.48% / 15.66%),
  an amendment to trial 53 by its owner. It mixes the two trials' risk in one stop. It is the quant
  review's other remedy for the split, and the one to take if K0 is not approved.
- **The decision is trial 53's owner's.** This note only measures it.

**HALVE / KILL** (report only; a peer owns them).
- They still read the whole account, as now. **K0 gives HALVE an acting consequence for this key only**:
  a reduced build is not sent at HALVE, and HALVE during an open episode kills this trial. This needs the
  HALVE/KILL peer's agreement (§10).
- **A HALVE report during a thin episode is an expected event on the fit's evidence** (item 1 of §7.2),
  not a malfunction, and the peer should know before it happens.

### 7.4 The vol scalar on 4–5 names

- **It is computed on the reduced set's own weights** over its trailing 63 sessions, so a concentrated
  book is scaled down.
- **It holds less well there.** The unit te4 book's realised vol is **6.64% on reduced earning days
  against 5.78% on full ones**, for a 6% target [V §E]: about 11% over the target, and 15% above the
  full book [U: 6.64 / 6.0; 6.64 / 5.78]. The scalar's look-back of today's weights under-reads the
  concentration risk.
- The scalar never reached its 0.2 or 2.5 clip on a reduced decision [V §E].

**Where the excess sits** (the PM review's C3; ×1.30, deferred, price only, fit from 2010-05-05) [V rc §R5]:

| earning days | n | vol | excess kurtosis | worst single-name day |
|---|---:|---:|---:|---|
| reduced, target has a single-fund side | 300 | 9.96% | 48.9 | −2.85% (PHK, 2015-04-10) |
| other reduced | 1,270 | 8.34% | 25.9 | −2.66% (PDI, 2020-10-06) |
| full | 1,045 | 7.62% | 11.6 | −4.45% (HYT, 2020-03-19) |

- **No reduced book ever traded a crash.** The first reduced decision is 2010-05-05 [V §E], and there was
  none between 2020-01-02 and 2020-06-23 [V §F].
- **Stress, not history.** The fit's 10 worst equal-weight universe days (4 in 2008-09/10, 6 in 2020-03)
  were applied to every held book [V rc §R6]:

  | held books | per-book worst one-day loss, p50 / p90 / p99 / max | share with a loss over 5% |
  |---|---|---|
  | reduced (1,570) | 2.8% / 7.2% / 10.7% / 13.4% | 23% |
  | full (1,047) | 2.7% / 5.8% / 9.6% / 13.0% | 15% |

- **A crash-type day can take a reduced book past half the HALVE line in one session.** The stops act
  after it.
- **Concentration and sponsor** [V rc §R7].
  - Reduced sets are PIMCO-dominated: 3 of the eligible names are PIMCO on 1,220 of 1,570 reduced
    decisions. PIMCO's share of gross is 61% at the median on reduced books, against 50% on full books.
  - **The net PIMCO bet is no larger:** |net PIMCO| is 0.285 at the median and 0.867 at p99 of NAV,
    against 0.329 and 0.875 on full books. Its maximum is 0.961 against 0.905.
  - The munis are absent on reduced sessions (|net muni| at most 0.062, a band residue). So the book's
    muni-against-taxable common risk drops out, and its risk becomes PIMCO-idiosyncratic [U].
  - A per-name cap is **not** proposed. It would be a new construction needing its own derivation.
### 7.5 The gross ceiling, `max_gross_stress`, gate 8 and the send-time fit

- **The ceiling is unchanged.** 1.8 × NAV in account units, 1.385 in unit weights at ×1.30, applied after
  the band. Reduced decisions sit at it 16.9% of the time, full ones 14.6% [V §E].
- **Gate 8 is unchanged**: projected gross ≤ `max_gross_stress` × the lower of sized and live equity,
  unless the plan does not add gross; and buying power and Reg T on the live account.
- **One interaction.** `bp_shortfall: scale` (`fit_to_buying_power`) scales opening orders only and sends
  reductions in full. On a 4–5-name book where one side is opening and the other reducing, that leaves a
  net imbalance for the session. K3 watches the realised result.
- **A dropped short flattens the session** (the PM review's C4; §1.3 item 6).
  - Gate 7 skips any order that opens or increases a short unless Alpaca reports the name shortable today,
    with no substitute (`quantt/session/decide.py`, "not shortable today: no order sent") [V code read].
  - On a one-fund short side (10.3% of fit reduced decisions [V rc §R5]), one unshortable name removes
    the whole short side. The book is then net long by up to about 0.9 of NAV at the ceiling [U].
  - Hard-to-borrow shorts need a locate, and paper has no locates [V `docs/REFERENCES.md`]. The harness
    never modelled this.
  - As first drafted, K3 would have let it run for two sessions below 0.833. Now, on a reduced decision,
    the reduced targets are not sent if decide drops a short-opening order; the session flattens, today's
    rule.
  - It costs one round trip each time it fires. **How often it would fire is UNMEASURED**: Alpaca's
    shortability history for PHK, PDI and PTY needs keys.
- **Margin is not worsened by te4** [V rc §R8; Alpaca's tiers: short [V `docs/REFERENCES.md`], long [S, the
  PM review's fetch of docs.alpaca.markets, 2026-11-03]].
  - Maintenance as a share of equity on the fit's held books, at the panel's 2026-10-15 closes: median
    0.594 on reduced books and above 1.0 on 0.89% of them. Full te4 books: 0.681 and 1.24%. Full flatten
    books: 0.670 and 0.76%.
  - At each decision's own closes it never exceeded 0.84.
  - The blended maintenance ratio rises by at most 0.012 at the start of a reduced run, so gate 8's
    measured-ratio check is not blindsided by te4.
  - **A whole-core finding for trial 53's owner, not about te4.** At the 2026-10-15 closes every name but PHK is
    priced between $5 and $16.67, so its short carries Alpaca's $5/share minimum, above 30%. PHK at $4.08
    carries 100% on a short and 50% on a long. On those
    prices full ×1.30 books need maintenance above 0.9 of equity on 7.8–9.0% of decisions. So the margin
    cushion, not the 1.8 ceiling, can be what binds (§10).

### 7.6 The deferred-flip rule

`quantt/session/decide.py`: `FLIP_SAME_SESSION = False`. A long↔short flip sends only the closing leg
today, and the band reopens the other side from flat next session.

**On a reduced set a flip can be a whole side.** On the fit, at ×1.30, the held book's |net| on reduced
decisions reaches **0.833 of NAV with deferred flips**, against **0.235 with instant flips** (p99 0.248
against 0.175). On full decisions it reaches 0.487 [V §E].
- **Example, 2019-10-09.** HYT's target flipped from short to +0.64 long while PHK's long was cut from 0.89
  to 0.06. HYT was held flat for the session, and the book was net short 0.83 for one session.
- **Not changed here.** The deferral exists for a broker reason (CLAUDE.md landmine 4 [U]). It is part of
  what paper scores, and the fit's deferred-flip episode values are the ones quoted.
- **K3** is set so that this one-session pattern (0 runs of 3 on the fit) does not trip it, while a
  persistent one-sided book does.

### 7.7 The stale-NAV and missing-NAV holds

Holds never trigger a reduced build, as they never trigger the flatten (§1.3, new piece 3, revised after
the quant review). With any hold present, today's code runs unchanged, including the tag on which the
runner's missing-NAV refusal keys. Such days inside an episode are held-book days, reported beside E_k
(§4.4). `gate.max_missing_nav_holds` stays n − `min_names` (§1.3, new piece 4).

### 7.8 C4

**C4 does not share the account.**
- It is its own book (`ops/books/c4_families_book.json`, `c4_families_paper`) on its own Alpaca paper
  account.
- Its spec sets `below_min_names: "hold"` and `sizing_multiplier` 1.26 (`c4_families.v4.20261102`) [V].
- This key goes into the core spec only. The registry accepting `"trade_eligible"` changes nothing for a
  spec that does not set it.

---

## 8. Divergences from the backtest, stated up front

1. **Constant weights against whole shares.**
   - The harness holds a weight vector and re-applies the band and cap daily in weight space.
   - Live, a band HOLD is a share count, so held weights drift with prices between trades. Orders are
     whole shares. The dust filter flattens names under 0.005.
   - The harness models no `min_abs_weight`. The declared guard (§1.3) leaves a residual under 0.005 per
     dropped name, on about 7% of reduced sessions (127 of 1,708 [S screen]).
2. **Live eligibility gates the harness does not have.**
   - The stale-NAV gate and missing-NAV holds (§7.7), gate 5's refusals, and the corporate-action halt.
   - **Gate 7's shortability skip.** On paper a short Alpaca will not lend is skipped, with no
     substitute. On a 4–5-name book the skipped short can be a whole side, leaving the book net long; the
     harness never had this. **Revised:** on a reduced decision such a skip now flattens the session
     (§1.3 item 6, §7.5), so the unmodelled one-sided book is not traded.
3. **Paper fills at the quote, not in the auction.**
   - `late_market` sends market `day` orders 8 to 2 minutes before the close. Paper runs no closing
     auction (CLAUDE.md landmine 1).
   - E_k is on Alpaca's fills; the closing-print view sits beside it (§4.4).
4. **No borrow, no distributions, no corporate actions on paper.**
   - E_k is price only. The screen's figures are total return; the distribution leg of te4's thin-day P&L
     was −0.28 of +3.94 [S screen], so price only reads slightly higher.
   - Borrow is UNMEASURED forward (§4.4).
5. **Deferred flips** are modelled in the harness (`defer_flips=True`) as flat for one session, then the
   band from flat. That is the live rule; the instant-flip rows are context only.
6. **`bp_shortfall: scale`** scales opening orders only; the harness scales the held book uniformly
   (§7.5).
7. **The hindsight universe.**
   - The fit's thin sessions come from projecting today's 13 names into years when they were illiquid.
   - Forward thin sessions would come from one name's ADV dip, likely shorter and in a book that is
     otherwise liquid. The per-episode effect may not transfer (§5 item 4).
   - Survivorship is unmeasured.
8. **Missed sessions.** A day that does not arm, refuses or is halted still has a P&L of record. It counts
   in E_k as what the account did, which the harness never models.
9. **The 0/0 sessions.** The harness fills 0/0 with 0, and the full-book sleeve holds silently (PR #33
   §5.H). The reduced path raises (§1.3), so such a day is a missed decide with the book held in shares.
10. **The re-entry leg is modelled**, and is kept out of every verdict (§4.4).
11. **Held-book days.** The harness has no holds. Live, a hold inside an episode stops the reduced build
    (§1.3 item 3). Such days are reported beside E_k with flatten's side modelled, and are never in a
    verdict (§4.4). How often they occur is UNMEASURED here.
12. **K0 and the gate-7 flatten are not in the harness.** Each can only replace a reduced build with
    today's flatten. Every fit figure in this note is therefore te4's without them, except §6.3's K0
    rows, which model K0 [V rc §R2–§R3].

---

## 9. Trial accounting, and the exact ledger edit (for the owning session at approval)

- **Counter: CEF.** The counter moves from its value at approval, 53 today, to N = that value + 1 **in the
  commit that records the team lead's approval, not before** (`/prereg`; `docs/RESEARCH_STATE.md`'s
  rule).
- **Bar √(2 ln N):** 2.818 at 53, 2.825 one later, 2.831 two later [V §G].
- **One trial.** One rule, one derived floor, one account.
- **Updated in `docs/RESEARCH_STATE.md` in the same commit as the approval: to be done by the owning
  session.** This draft does not edit that file.
  - **Applied 2026-11-03 with N = 55**, in the approval commit. The owning session agreed that this
    session make that commit.

**The edit, exactly** (replace `<N>` with the counter's value at approval plus one, `<date>` with the
approval date, and `<file>` with the approved note's name):

1. The counter row:

```
| **CEF** | **credit closed-end fund discounts** | **<N>** |
```

2. A dated note, above the 2026-11-02 notes:

```
> **<date>: CEF <N−1> → <N>** (team lead; this commit records the approval):
> - **Trial <N> is the thin-session rule `trade_eligible`, floor 4, PAPER ONLY**
>   (`results/cef/<file>`, from `PREREG_DRAFT_THIN_TRADE_ELIGIBLE_2026-11-03.md`): on a session with
>   fewer than `min_names` but at least 4 eligible names, the core builds its book on the eligible names
>   instead of closing it. Keys `below_min_names: "trade_eligible"`, `below_min_names_floor: 4`
>   (absent = flatten, byte-identical, proved). Never on a live-money account (the paper-only client,
>   the sleeve's refusal of the key without a paper declaration, the runner's endpoint check, and
>   `docs/SYSTEM.md` §5).
> - **Not shown to be alpha** (`results/backtests/thin-third-rule-2026-11-03/REPORT.md`): matched-turnover
>   +2.13pp/yr (t 2.34), INCONCLUSIVE; PHK and PDI; 87% PIMCO; holdout t 0.72; −2.33pp/yr net of measured
>   2023+ borrow. Chosen for paper because paper is scored gross (D19/D20).
> - **Judged at N = <N>, bar √(2 ln <N>)**, on forward thin episodes only (2023+ is seen). PRESENT is out
>   of reach for years (exact P 0.10 at 5 episodes); ABSENT (first two episodes negative, or the mean
>   ≤ 0 from the third) and the stops K0–K3 are the operative rules, K1–K3 re-measured on the read
>   date by `results/cef/prereg_thin_te4/compose.py --stamp <date>`. PRESENT is read only at 5, 9, 13 and
>   20 episodes, each at the bar's one-sided p / 4 (P 0.03 / 0.22 / 0.54 / 0.87 at the fit effect), and
>   is labelled unmatched (H2).
> - **K0, the account, acts in code**: a reduced build is sent only if the decide's drawdown record reads
>   OK, and HALVE or KILL during an open episode kills the trial. Conditions: a dropped short flattens a
>   reduced session; a "core ex-te4" series beside every core P&L report; the core's kill rule (a) also
>   read on full sessions alone; K0–K3 report lines and the revert spec in the activation release;
>   activation only after the core's 60-session review <as the team lead ruled on §10 Q4–Q9>.
> - **Trial 53 composes with it** (pre-registration §7): m 1.30 applies on reduced sessions; <the team
>   lead's answer to Q3: R1–R3 read on full sessions only, with K0 / recalibrated>.
```

3. A row in the ACTIVE table, after VT:

```
| **TE4** (CEF trial <N>) | on a session with 4 or 5 eligible names, trading the eligible set with the sleeve's own construction earns more gross than closing the book (`results/cef/<file>`); keys `below_min_names: "trade_eligible"`, `below_min_names_floor: 4`; **paper only** | **APPROVED <date>** (team lead); inert until a session is thin (none since 2023-08-30 on the panel to 2026-10-14); activates only after the core's 60-session review | forward thin episodes only: ABSENT on the first two negative or a mean ≤ 0 from the third; KILLED on K0 (the account at HALVE during an open episode, acting in code) or K1–K3; PRESENT only at 5 / 9 / 13 / 20 episodes at t ≥ t(k−1) critical at p / 4, with PHK and PDI out still positive, labelled unmatched (H2) |
```

---

## 10. Open questions for the team lead, each with a recommended answer

1. **Approve for paper, with K0 and the conditions?**
   - Weigh it as follows: the gross case is real on the panel, it is not shown to be alpha, and it cannot
     be shown forward in any useful time.
   - **Recommend: approve only if the paper score of gross P&L on thin sessions is itself the objective,
     and only with K0 and the conditions (§0, Q4–Q9).** Otherwise take option (c) of the screen: record
     the screen and keep flatten, which costs nothing.
   - If the objective is evidence for real money, this trial cannot supply it (§6.2).
   - The PM review ranks it last among live-path changes on contribution to absolute return per unit of
     risk [U: a judgement]. Its forward gross is 0 while no session is thin, and about +0.9 to +2.3pp/yr
     if sessions are thin at 2023's share (§5).
2. **Trial 53's multiplier under te4?** (with trial 53's owner)
   - Re-fed te4's book, trial 53's rule gives ×1.15, against ×1.30 (§7.2).
   - **Recommend: keep ×1.30 with K0.** This trial never moves m. m(s) is re-measured and reported to
     trial 53's owner (§7.2). Record in trial 53 that its W1 figures describe the book only while no
     session is thin.
   - **Without K0: ×1.15, or do not approve.**
3. **R1–R3 under te4?** (trial 53's owner)
   - **Recommend (a), with K0: read them on full-session earning days only** while this key is set
     (§7.3). Otherwise the approved R3 fires 8.3% of the time against its 5% design on te4's fit mix.
   - If K0 is not approved, take (b): recalibrate on te4's trading sessions (10.75% / −2.48% / 15.66% on
     drafting day), an amendment to trial 53 by its owner.
4. **K0 in code?** (with the HALVE/KILL peer's agreement)
   - Under K0 a reduced build is sent only when the drawdown record reads OK; HALVE, KILL or UNMEASURED
     flattens the session (§1.3 item 5, §6.3).
   - It would be the first acting use of `drawdown.py`'s status. Its only action is today's rule, so it
     can only remove risk.
   - **Recommend: yes.**
5. **K0's consequence?**
   - The choice is between KILLED and a suspension that stays until the team lead records a review, which
     is how `drawdown.py`'s documented HALVE `on` mode would work.
   - **Recommend KILLED:** it is simple and matches K1–K3.
   - The cost: a kill ends te4 for good after any HALVE-level drawdown of the core during an episode, even
     one the reduced sessions did not cause (§6.3, "what K0 does not buy").
6. **K0 and UNMEASURED at the evening decide.**
   - If the EOD equity row for D is routinely missing at the 22:00 ET decide, K0 makes te4 inert.
   - **Recommend:** measure how often the decide reads UNMEASURED from the run records before activation,
     and fix the record's timing if needed. Never loosen K0 (§6.3).
7. **A dropped short flattens a reduced session (gate 7)?**
   - It costs one round trip each time it fires. How often it would fire is UNMEASURED: it needs keyed
     shortability history.
   - **Recommend: yes** (§7.5).
8. **The core's kill rule under te4?**
   - **Recommend:**
     - (a) fires on live net Sharpe < 0 on the whole account OR on full-session earning days alone;
     - (c) is read on the spec's cross-section;
     - accept that reduced-session slippage can trip (b) (§6.4).
   - This is stricter than today, never looser, but the rule is pre-committed, so it is the team lead's
     call.
9. **Activate only after the core's 60-session review is graded?**
   - **Recommend: yes.** It costs nothing in expectation, and it keeps the core's first verdict free of
     te4. The review's date is UNMEASURED here (§6.4).
10. **A hold on a day that could have been reduced** (with the runner's owner).
    - **Recommend: no reduced build when any hold is present.** Today's code runs, tag and refusal
      included (§1.3 item 3).
    - The alternative, trading the reduced set with the held name kept at its shares, turns today's
      missing-NAV refusal into a trade the harness never modelled.
    - How often the core's holds fire is UNMEASURED here; prod's run records answer it.
11. **The PRESENT design.**
    - **Recommend the declared reads:** k = 5, 9, 13 and 20, each at p / 4 (§6.1).
    - The alternative is one read at k = 13 at p. It has more power at 13 (0.74 against 0.54) and none
      before it.
    - Either must be fixed before approval, never after.
12. **The min-weight guard** (l.965).
    - **Recommend: leave it at `min_names`** (§1.3).
    - The alternative, the guard at the floor, re-creates the 3-name degeneracy when a 4-name set loses a
      name to the filter.
13. **The deferred flip on a one-fund side** (§7.6).
    - **Recommend: no change.** It is the broker's constraint and part of what paper scores, and K3 watches
      persistence.
    - The unmodelled gate-7 case is handled by Q7.
14. **The paper-only refusal** (§1.2).
    - **Recommend: build it in the sleeve, with the runner's endpoint check behind it.**
    - Whether the same refusal should cover `late_market` is a separate question for the runner's owner.
15. **The forward borrow column.** It is UNMEASURED: IBKR is retired and paper charges no borrow. (Paper does charge SEC and CAT regulatory fees on sales [V: the cef account's FEE activities, `results/cef/LIVE_ATTRIBUTION_2026-11-02.md`, PR #26]; that is an execution cost, not borrow.)
    - **Recommend:** record it as UNMEASURED per episode and decide nothing on it.
    - If a real-money proposal ever cites this rule, the first purchase is a point-in-time
      securities-lending history for PHK, PDI and PTY (the screen's open question 8).
16. **Tell the HALVE/KILL peer?**
    - **Recommend yes, before activation.** On the fit's evidence a HALVE report during a thin episode is
      expected: W1's drawdown at ×1.30 is 13.76% price only.
    - Under K0 such a report now has an acting consequence for this key.
17. **For trial 53's owner, about the whole core rather than te4: margin.**
    - At the 2026-10-15 closes, full ×1.30 books need maintenance above 0.9 of equity on 7.8–9.0% of fit
      decisions, and above 1.0 on 0.8–1.2% [V rc §R8].
    - Gate 8's measured-ratio check trims to this, so the margin cushion, not the 1.8 ceiling, can bind.
    - **Recommend:** the owner re-measures it on live prices at the next amendment. It is not a reason
      to hold te4.

---

## 11. Reproduce

```bash
# §A-§G2; a few minutes; fit rows only. Writes compose_<stamp>.json and compose_output_<stamp>.txt beside
# itself; --stamp defaults to today and never overwrites another date's files without --overwrite.
# Corrected 2026-11-05 (the runner owner's round-2 answer (c)): --k3-run-sessions, K3's run length (the spec's
# risk.thin_k3_run_sessions), is now REQUIRED; the drafting day counted with a literal 3, so its reproduction
# passes 3. The commands read without it until then. compose_2026-11-05.* is the drafting-day run re-made with
# the argument: every figure the same as compose_2026-11-03.json's, plus the recorded k3_run_sessions 3.
python3 results/cef/prereg_thin_te4/compose.py --stamp 2026-11-03 --k3-run-sessions 3 --overwrite   # the drafting day (then git diff)
python3 results/cef/prereg_thin_te4/compose.py --stamp <read date> --k3-run-sessions <n>           # a read-date re-measure (§6.3)
# the two reviews' measurements, §R1-§R10; about 10 s; needs compose_<stamp>.json for §R9
python3 results/cef/prereg_thin_te4/review_checks.py --stamp 2026-11-03 --overwrite
# the screen this note rests on
python3 results/backtests/thin-third-rule-2026-11-03/third_rule.py && python3 results/backtests/thin-third-rule-2026-11-03/tables.py
python3 -m pytest scripts/cef/tests/test_band_trade_eligible.py scripts/cef/tests/test_band_below_min_names.py
```

What compose.py asserts before it prints any result (it raises otherwise):
- **§A1:** every scored book (flatten and te4; m 1.00, 1.13 and the spec's m; instant and deferred
  flips) equals an independent row-by-row loop at the read date's band and ceiling. On drafting day the
  largest difference was 5.6e-17;
- `build_panel`'s ADV window is still 63 sessions; the floor satisfies 2 ≤ floor < `min_names`; the spec
  carries `sizing_multiplier`;
- no frame reaches 2023-01-01.

What it **reports, without raising (§A2)**:
- whether the flatten book at ×1.00 / 1.13 / 1.30 still equals trial 53's committed exact build
  (`prereg_voltarget/flatten_exact_2026-11-02.json`). On drafting day the largest difference was 0.0;
- whether the flatten unit book's trading-session sd equals `flatten_remeasure_2026-11-02_m1.30.json`'s
  0.003556;
- whether te4's nine fit episodes equal the screen's `results.json` (largest difference 1.4e-17).

Until the 2026-11-03 revision these were assertions; §6.3 says why they are not now.

`review_checks.py` reproduces every figure this note labels [V rc §Rn]. When it was first run, each
matched the reviewer's own scratch output (§12).

**Neither script writes anything under `data/`** (CLAUDE.md landmine 9).

---

## 12. The reviews of ecf62ea, and what was done (2026-11-03)

- **Two reviews were made of the first draft:** a quant review (7 findings) and a PM review (findings
  F1–F9, wording C1–C8).
- **Each figure they cite was re-run before the draft changed.** compose.py §G2 and `review_checks.py`
  reproduce them from tracked code, and every one matched.
- **None is refuted.** Five carry a correction, stated here and where the text was changed.

| # | finding | verdict | evidence | applied in |
|---|---|---|---|---|
| quant 1, PM F1 | splitting the stops by session type leaves the account's 13.76% fit drawdown past HALVE seen by no acting stop | **CONFIRMED** | rc §R1: 2018-05-08; R1's population 6.67% (W1 worst 7.36%) against 10.14%; K1's 7.22% (worst 8.90%) against 10.52% | K0 (§1.3 item 5, §6.3); §7.2; §7.3; Q2–Q5 |
| quant 1, secondary | D_E is a 252-day line, but episodes run to 390 days, so K1 over-fires on long episodes | kept as **[U]** | not measured | §6.3, K1's limits |
| quant 2 | on a missing-NAV-hold day the zero counterfactual fails and the count-based definition misclassifies | **CONFIRMED** | code read: `cef_discount.py` l.878–946, `_tag_short` l.342; `run.py` l.1805–1827; the core's book json sets `missing_nav: "hold"` | §1.3 item 3; §4.2 (`reduced` flag; held-book days); §4.3; §4.4; §7.7; §8 item 11; Q10 |
| quant 3 | the cost grid misses the trading between runs of a merged episode | **CONFIRMED, with a correction** | rc §R10. 6 of 9 episodes have two or more runs, not 5. In five of them the formula over-charged te4 by 0.41–1.37pp at 15bp. In 2010-05-05, where flatten held no book before the episode, it **under**-charged te4 by 0.13pp. So the error does not always run against te4 | §4.4 (window with gaps; flatten shadow) |
| quant 4 | reading PRESENT at every episode inflates the bar 6–8× | **CONFIRMED** | §G2: 0.79% / 1.50% / 1.79% false PRESENT by k = 5 / 13 / 20 against 0.24% | §6.1 (declared reads, p / 4; "unmatched (H2)"); §6.2; §9; Q11 |
| quant 5 | §0's "coin flip after 5 episodes" contradicts §6.2's exact 0.10 | **CONFIRMED** | §G2: exact power first passes 0.5 at k = 10 (0.518): 14.1 / 36.7 years | §0 |
| quant 6 | compose.py cannot re-measure after a band, ceiling or panel change, and overwrites its dated outputs | **CONFIRMED** | code read: the raises at the old l.253 / 259 / 266; `STAMP = "2026-11-03"` | compose.py (A1 asserted, A2 reported, `--stamp`, overwrite guard, floor from the spec); §6.3; §11 |
| quant 7 | the paper-only tripwire fails open | **CONFIRMED** | design: only `run.py` checked | §1.2 (the sleeve refuses without a paper declaration); §1.5; Q14 |
| PM F2, C1 | K0: a reduced build only when the drawdown reads OK; HALVE or KILL during an episode kills | **CONFIRMED** | rc §R3: P(KILL) 1.27% → 0.13% (SB21), 2.27% → 0.38% (SB63), price only; flatten 0.40% / 0.59%; fit-edge cost ≤ 0.04pp/yr. rc §R2: path maxDD 13.76% → 13.46% (PR) | §1.3 item 5; §6.3; §0; §9; Q4–Q6. **Added:** the UNMEASURED-at-the-evening-decide interaction (§6.3, Q6) |
| PM F3, C3 | the extra risk sits on single-fund-side reduced days; crash stress | **CONFIRMED** | rc §R5–§R6: 9.96% / 8.34% / 7.62% vol; stress p90 7.2% against 5.8% | §7.4 |
| PM F4, C2 | K2 is a fault detector; PIMCO dominates reduced sets, but the net PIMCO bet is no larger | **CONFIRMED, with a correction** | rc §R5, §R7. The fit maximum's excess over ½ × 1.8 comes from the band leaving the sides unequal, not from drift: the harness has none | §6.3 (K2); §7.4 |
| PM F5, C4 (gate 7) | an unshortable single short leaves the book one-sided; flatten instead | **CONFIRMED** | code read: `decide.py` gate 7; rc §R5: short side single on 10.3% | §1.3 item 6; §7.5; §8 item 2; Q7 |
| PM F6, C4 (margin) | te4 does not worsen margin; the whole core's cushion can bind | **CONFIRMED** | rc §R8: reduced 0.594 / 0.89%, full 0.681 / 1.24%, flatten 0.670 / 0.76%; ratio rise ≤ 0.012 | §7.5; Q17 |
| PM F7, C7 | K1 is blind in short episodes; a horizon-matched K1 fires once | **CONFIRMED** (minor: it reads four horizons, not five) | §E: D_E(21) 4.13%; rc §R9: PR 2017-06-21, 8.88% at L 126 | §6.3, K1's limits |
| PM F8, C6 | te4 could extend or trip the core's kill rule; activate after the 60-session review; core ex-te4 | **CONFIRMED, with a correction** | grep: no `.py` computes `kill_rule`. "Core ex-te4" is flatten's figure exactly on reduced earning days only; it omits R_k and the cost difference | §4.4; §6.4; Q8–Q9 |
| PM C5 | this trial never moves m; re-measure m(s) | **CONFIRMED, with a correction** | rc §R4: m(0.15) 1.2345, m(0.564) 1.1505; but the fit mixture reads 1.27 at s = 0, not 1.30 (te4's full days carry its band path) | §7.2 |
| PM F9, C8 | §5 item 5 should read +0.9; label 13.76% PR and 13.79% TR | **CONFIRMED** | 0.8 × 1.30 / 1.13 = 0.92 | §5; §0; §6.3 |
