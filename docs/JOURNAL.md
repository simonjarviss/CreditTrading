# Desk journal — what we tried, found, ruled, shipped and earned, day by day

**One entry per day, newest at the bottom.** Each entry has the same five parts.
It is updated **in the same commit** as the change it records. Like the ledger
rule in `docs/RESEARCH_STATE.md`, it is never caught up at the end of a session.

It is the readable running record. **It owns nothing.** Every figure names the
file or command that owns it:
- trial counters and verdicts: `docs/RESEARCH_STATE.md`;
- team-lead rulings: `docs/SYSTEM.md` §5;
- release steps: `docs/RUNBOOK.md`;
- live figures: `python3 -m ops.orient`.

If this journal and an owner disagree, the owner is right, and the journal gets a
dated correction.

**Live P&L** is Alpaca's **official** end-of-day figure first, with the auction-marked P&L
beside it, both gross. The 17:30 ET snapshot carries after-hours marks and ran $560
too favourable over 10-07..10-30 (2026-11-02 entry), so it is never the headline. Alpaca's end-of-day history is
the **official** figure (team lead, 2026-10-19), and it lands the next day.
Until it does, the line says *official pending*. Labels: [V] measured or read
from a named source; [doc] copied from a named note.

| part | what goes in it |
|---|---|
| **Research** | every test or screen run, its verdict, its note |
| **Found** | anything discovered about the live system or the data |
| **Rulings** | team-lead decisions, pointing at `docs/SYSTEM.md` §5 |
| **Prod** | every change to the VM: release tags, data repairs, network |
| **Live** | the day's verify line and broker-confirmed equity |

---

## 2026-10-26 (Mon)

**Research (zero trials; dates ≤ 2022-12-30; gross)**: `results/cef/screens_2026-10-26/README.md`
- **Macro regime filters, by fund group:** NOTHING. No group's own macro reading changes the signal's within-group IC.
- **FOMC/CPI/NFP-day discount moves:** NOTHING. Extra reversion −6.9bp (t −0.36); the placebo scores more.
- **C4's ex-date concentration:** MIXED. A generic post-ex-date drift that a z-blind short earns. Paper overstates C4.
- **Fund-of-CEF index rebalances (YYY/PCEF/XMPT):** infeasible on free data (re-run 10-27).
- **BDC discounts:** infeasible locally (re-run 10-27).
- **New lead: the post-ex-date drift.** W4 had first recorded it, untested, on 2026-10-11.

**Rulings:** C4 proceeds toward paper despite MIXED. A pre-registration is drafted for the ex-date drift (`docs/SYSTEM.md` §5, 2026-10-26/27).

**Prod:** no change.

**Live [V, verify.log]:** PASS, 6 orders, 6 filled. Snapshot −$446.70 gross; auction-marked −$520.85.

## 2026-10-27 (Tue)

**Research**
- **BDC discounts**, on the team lead's R2 pull of Compustat: NOTHING in the tradable set. At ADV ≥ $3m the signal is short-term reversal.
- **Index rebalances**, on CRSP fund holdings: ARTIFACT pooled; the placebo scores more. PCEF alone (+184/−120bp) is a post-hoc subgroup.
- **Ex-date Stage 0:** HALTED. Alpaca's `declaration_date` is derived from the record date, so it is not a real declaration date.

**Found:** commit 7c02236's "pytest exit 0" had been read through a pipe (`| tail`), so it measured tail's exit. It was re-verified and corrected in ef6b1b4. Every later check reads the exit code without a pipe.

**Rulings** (`docs/SYSTEM.md` §5, 2026-10-26 and 2026-10-27):
- The ex-date pre-registration is approved as **EVENTS trial 3** (N = 7); part (a) is withdrawn.
- C4 gets its own paper account, the spare connector account.
- C4's setup is accepted as a set.

**Prod:** no change.

**Live [V]:** PASS, 6 orders, 6 filled. Snapshot +$251.43; auction-marked +$192.95.

## 2026-10-28 (Wed)

**Found**
- **`fetch_daily` wrote yfinance's empty ex-date rows** (no close, volume 0), which overwrote good bars. The laptop's refresh had blanked 15 bars; **prod's panel held 91 empty closes** (Feb–Apr 2026), 24 of them on the live book.

**Research:** Stage 0 cleared after rulings. Declaration dates come from the sponsors' own releases; Nuveen's are gone since 2019, so 86 of its events were recovered from CRSP.

**Rulings:**
- Fix the fetcher, NAV side included, in one release.
- Repair prod's panel from Alpaca's official prints.
- The Stage 0 rulings (sponsor declarations; keep the basket; O1–O4).

**Prod [V, ops.prod_state]**
- **16:30 ET: `release-20261028-1` (de6e9c5).** Empty price or NAV rows are never merged; NAVs must be finite (and later positive).
- **17:14 ET: prod panel repair.** 87 closes filled from Alpaca's closing-auction prints; a backup sits next to the panel; one log line per cell (`quantt_state/cef/logs/repair_empty_closes.log`). Measured effect on the day's plan: weights moved ≤ 0.0008, and PTY went flat. 4 NYSE American cells (DHY, EAD) are left empty. DHY's history is split-adjusted, so a raw print would be 10× off.

**Live [V]:** PASS, 10 orders, 10 filled. Snapshot +$414.46; auction-marked +$421.90. Equity $99,528.31 at the close. *[Corrected 2026-11-02: $99,528.31 was a 17:10 ET after-hours read; the official close was $99,535.06, official day +$421.21. See 2026-11-02.]*

## 2026-10-29 (Thu)

**Found**
- **CEFConnect has refused every scripted request since 2026-10-21** (JSONDecodeError). That is why **2026-10-22 was missed**: PDO's NAV was late, there was no fallback, and gate 5 refused all 13. It is also why the collector ended INCOMPLETE and the stale-NAV gate could verify nothing. NAV licensing is upstream, at Nasdaq Fund Network (`results/ops/NAV_SOURCE_WORKAROUND_2026-10-19.md`).
- **PR #20 (corporate-action gate, another session) put an order-path defect on `main`:** gate 6 judges order lists read before the corporate-action fetch. It is not released; a fix is on branch `fix-gate6-stale`.
- The release-check workflow on `main` names a reviewer agent (`quant-trader`) that older sessions don't have. Launch it from the main checkout, or run execution-trader by hand.

**Research (zero trials)**
- **Ex-date short on the full 2005–22 fit:** passes D4. +11.6bp per event, t 3.87, alpha t 4.57, rate betas ≈ −0.05. **Every 3.8-year era fails D4 on its own.** Amendment 1, a duration hedge, was worse and is withdrawn.
- **Risk split, after an independent review** (scratchpad `alloc/` and `alloc_review/`): equal-risk weights. Core + C4 is about 9% gross on the fit, with a realistic Sharpe of 1.2–1.5 and P(HALVE in 12m) of 4–6%. Three sleeves is about 10.6% in-sample. Reg T binds before KILL.
- **C4 step 2:** the live sleeve rebuilds the trial's book on 907 of 907 fit sessions. C4's cap is re-derived as 1.90.
- **PCEF pre-registration drafted:** about 23 test events, so power is weak.

**Rulings** (`docs/SYSTEM.md` §5, 2026-10-29):
- Fast-track C4; the combiner is built first.
- Hold one fund on a missing NAV, for at most **2 sessions** (a policy, not derived); the collector marks CEFConnect as down.
- C4's cap is 1.90, **not a trial**. IGR is seeded with the trial's correction.
- Three sleeves; the ex-date sleeve goes in the spare account beside C4.
- **"Add all 3":**
  - C4 (passed);
  - the ex-date short as a **forward test** (EVENTS 3; the sealed 2023+ test still runs once French publishes);
  - PCEF as **EVENTS trial 4** (N = 8) in a **third** paper account. Its counter moves in the commit that records its pre-registration.
- **Full equal-risk share for every sleeve from day one.**
- Keep this journal.
- **Corporate-action gate (PR #20):** skip and record a malformed row unless it could be ours. A stuck backfilled action clears only by the team lead's recorded acknowledgement. Release `main` only after these and the gate-6 fix.

**Prod [V, ops.prod_state]**
- **10:36 ET: `release-20261029-1` (bd87144).** The multi-sleeve combiner, dark. The first release-check was NO-GO on two defects, both fixed.
- **19:04 ET: `release-20261029-2` (5e627ff).** The missing-NAV hold code (dark); the collector's CEFConnect-down status; official closes for NYSE American (A) and Nasdaq (Q).
- **20:20 ET: `release-20261029-3` (cee16ad).** **The missing-NAV hold is ON** (book json). It deliberately excludes PR #20.
- Ssh allowlist: the team lead's current IP was added to the VM's network rule (`vmallow.sh`, git-excluded), keeping the existing entries.
- Every release passed a release-check (both reviewers) and a history replay (0 new refusals), and was applied with `--armed`. The VM is ARMED at `release-20261029-3`.

**Live [V]:** PASS, 3 orders, 3 filled. Snapshot +$78.64; auction-marked −$13.43. Equity $99,530.59 at the close. *[Corrected 2026-11-02: a 17:10 ET read; the official close was $99,521.57, official day −$13.49.]*

**Open at end of day:**
- the gate-6 fix for PR #20 (4c63b1f, done), plus rulings A and B (being built);
- C4 integration (book, installer, verify per book);
- the ex-date and PCEF sleeves (built dark);
- the four-sleeve, three-account risk split;
- the team lead to create the C4 vault secrets and the third paper account;
- French's 202610 factors for the ex-date test;
- watch the hold's first final check (2026-10-30, 14:30 ET).

## 2026-10-30 (Fri)

**Found:**
- The gate-6 release-check found a second order-path defect in the corporate-action reader: rows de-duplicated by a null `id`. Being fixed.
- The four-sleeve, three-account split (zero trials, fit) gives **6.1%/yr gross** at full equal shares. Reg T caps each account, and PCEF's $100k sits idle on 93% of days. Core + C4 gives about 9% (scratchpad `alloc4/NOTE.md`).

**Rulings** (`docs/SYSTEM.md` §5):
- maximise % return on all capital: **core + C4**, with the ex-date short and PCEF built but off;
- raise the core's vol target as **CEF trial 53** (pre-registration drafting);
- C4 uses the core's HALVE/KILL;
- Invesco's written consent for PCEF holdings, with the team lead to file a copy.

**Prod:** no change (`release-20261029-3`, armed). The missing-NAV hold's first final check is 14:30 ET.

## 2026-11-01 (Sun)

**Research / build:**
- CEF trial 53 approved at **×1.13 core / ×1.27 C4** (CEF 52 → 53, on `prereg-voltarget` 6a86905). The `sizing_multiplier` code is a proved no-op when absent (f52a613); the core's activation is eca5feb (spec v8). Not released.
- Corporate-action gate fixes: gate 6 reads fresh orders; acks match content.

**Found:** release-checks NO-GO on 10-30 (null `id` de-duplication) and 11-01 (null subject, then null acquirer, skipped as "not ours").

**Rulings** (`docs/SYSTEM.md` §5): **any null party symbol refuses**, since it can't be proved not ours. Skip-and-record applies only when every party symbol is present and none is ours. *[Corrected 2026-11-02: this was not a team-lead ruling; see 2026-11-02.]*

**Prod:** no change.

**Live [V, ops.prod_state]:** 2026-10-30 PASS, 7 orders, 7 filled (the first session with the missing-NAV hold on). Equity $99,124.35 at the close. The 2026-11-02 plan is decided (4 orders). *[Corrected 2026-11-02: a 17:10 ET read; the official close was $99,017.86, official day −$503.71, official total since $100,000 −$982.14.]*

## 2026-11-02 (Mon)

**Found:** the release-check on 709d6cb was NO-GO.
- The 2026-11-01 "any null party refuses" rule would stop the book indefinitely: one malformed row anywhere in the market halts every session, and `ca-ack` could not clear it.
- An acknowledgement still cleared an action whose type had changed.

**Correction:** the 2026-11-01 entry recorded that rule as a team-lead ruling. It was the agent's reading of ruling A, so it is corrected in place in `docs/SYSTEM.md` §5.

**Rulings** (`docs/SYSTEM.md` §5): a row with a missing party symbol **halts only where it would halt for one of our held funds**, and the team lead clears it with `ca-ack`, matched on its full content. Outside our windows it is recorded only.

**Build:** the corporate-action read now validates every field. A property test (4,598 adversarial cases) fails 794 on 1c64638 and 0 on a40170c. **Release branch `rel-20261102`** (3478159) = the gate fixes + CEF trial 53's activation (core ×1.13, spec v8), released together.

**Found: our records flattered the account.** Reconciled day by day against Alpaca's official closes, rebuilt from each day's `last_equity` (VM `equity.csv` and `scores.csv`, copied 2026-11-02; `eod_equity.csv` not yet read):

| 10-07..10-30 | total | vs official |
|---|---|---|
| Alpaca official (end-of-day, P&L of record) | **−$1,794.53** | — |
| auction-marked score | −$1,789.74 | $4.79; never more than $0.69 on a day |
| 17:30 snapshot (`alpaca_equity_change_usd`) | −$1,234.29 | **+$560.24**: after-hours marks |

- The 17:30 snapshot carries Alpaca's after-hours marks. Each day's gap equals that day's 17:30 equity minus its official close.
- `equity.csv`'s 17:10 read differs from the official close by $52.88 a day on average, at most $332.00 (10-09).
- **This journal's 10-26..10-30 snapshots sum to −$89.05; official is −$424.44.**
- Official total since $100,000, to the 10-30 close: **−$982.14** [V, reconstructed from `last_equity`].
- Days 2026-09-30..10-02 and 10-06 have no score at all (official −$192.97, +$626.70, $0.00, +$252.63).
- From today the journal quotes the official figure first.

**Rulings** (`docs/SYSTEM.md` §5): trial 53 ships tonight even if the gate fails review (gate in report mode). C4 uses the existing spare account; no new account.

**Later on 2026-11-02:**
- **Release-check on 3478159 (the gate fixes + trial 53): NO-GO.**
  - Today's real feed carries three market-wide rows with a missing party symbol: a partial call, an SNTI spin-off and a JAGX merger. Under the unresolved-rows ruling, each halts for every held fund, so `halt` would refuse the next session.
  - `ca-ack` could write a file the gate then rejects.
  - Two no-op pins still skipped on the v7 hash.
- **Applied the team lead's fallback ruling:** the corporate-action gate ships in **report** mode, and trial 53 ships tonight. Report mode records events and sends anyway (book json `_mode_report_note`).
- **Found (another session, read-only):**
  - **Alpaca's winter end-of-day stamps are 01:00Z** (20:00 EST), and the client accepted only 00:00Z. From 11-02, the official P&L would stay PENDING; prices and NAVs are unaffected, since collector steps are independent. Fixed in this release.
  - **Paper DOES charge regulatory fees** on this account: 37 SEC and CAT fee activities, −$6.16 over 09-29..10-30 [V, that session's GET of FEE activities]. This contradicts CLAUDE.md landmine 1 and the paper rows in `docs/REFERENCES.md`; the correction goes to the team lead.
  - **Live attribution, 2026-09-15..10-30** (that session's note on branch `research-live-attribution`) [V, there]:
    - official −$982.14, rebuilt to $0.00 on all 34 sessions;
    - holding −$667.27 = NAV −$2,250.74 + discount +$1,583.47, with the muni NAVs alone −$1,849.36;
    - fills vs close −$308.71 (−5.5bp of $558,926.55 traded);
    - fees −$6.16;
    - distributions paper did not credit +$320.85, equal to our third score to the cent.
  - **The canonical harness holds on thin sessions; the live sleeve flattens.** Under a replica of the live rule, the fit-era break-even is 18.6bp, not 45.8bp [that session's turnover study, report only]. This is a question for the team lead, and trial 53's fit figures inherit it.

**C4 brought up to date with main** (branch `c4-rel`, local; not pushed, tagged, installed or armed):
- `c4-integrate` merged onto 862b1d0 (release-20261102-1) with no textual conflict. Fixed after it: `ca-ack` now refuses another book's state directory, as approve and the session do; five C4 tests that main's gate, trial 53 and the released book json broke.
- C4's spec: `c4_families.v2.20261101` (trial 53's `sizing_multiplier` 1.27, the committed patch) and then `v3.20261102` (the core's halve/kill levels, report only, per the 2026-10-30 ruling). Revert tags for v1 and v2 are local.
- The benchmark, re-run on the raised spec: fidelity passes; H11's reference is the ×1.27 book.
- The core is proved to be 862b1d0's (`test_panels_noop.py`, re-pinned there). Its own three pin files are untouched and pass.
- **C4's corporate-action `halt`, measured** on a replica of today's three unresolved rows: a flat C4 book is refused only on 11-03 (the JAGX merger); a held one on every session. On every unresolved row in today's read, a flat book would have been refused on 17 of the 23 sessions from 10-01 to 11-02 [U: feed as read today]. **Ruled the same evening: C4's gate runs in REPORT, as the core**, until the ISIN fix and the re-ruling of the unresolved rows land (book json `_mode_report_note`, with the RESTORE line; `results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md`).
- **Release-check of 8b14298: NO-GO, fixed.** C4's fetch exited 4 (INCOMPLETE) over 6 (unruled spike), and C4's missing-NAV hold accepts 4 at the final check, so on a day with a late NAV C4 would have decided on an unruled spike bar. Now 6 outranks 4 when the spike guard is on, and the collector treats a 6 that names INCOMPLETE as an unfinished step. The core runs no spike guard: its fetch is still proved byte-identical to cee16ad's.

**Rulings, about 22:00 ET** (`docs/SYSTEM.md` §5, the trial-53 table): **CEF trial 53 amendment 1 is approved.** Core ×1.13 → ×1.30 (spec `cef_discount.v9.20261102`), C4 ×1.27 → ×1.26 (`c4_families.v4.20261102`, before C4 arms), and the core's stops recalibrated on the live thin-day rule's trading sessions: R1 10.14%, R2 −3.06%, R3 12.07%. It is an amendment, not a new trial; **CEF stays 53**. The evidence is `results/cef/prereg_voltarget/FLATTEN_REMEASURE_2026-11-02.md` (PR #35) [doc]. Built on branch `trial53-amend1`, cut from `c4-rel` at 8b14298.

**Prod:** no change (`release-20261029-3`, armed; no corporate-action gate yet).

**Prod, evening of 2026-11-02 [V, `ops.prod_state` after the install]:**
- **`release-20261102-1` (f83b2a3, PR #28, merged as 862b1d0)** is installed on the VM, **ARMED**. It carries:
  - **CEF trial 53, the core at ×1.13** (spec `cef_discount.v8.20261101`), first decided at the 22:00 ET slot;
  - the corporate-action gate in **report** mode;
  - the gate-6 fresh-order fix;
  - the winter end-of-day stamp fix.
- The release-check was GO on f83b2a3, after NO-GOs on 9630322, 9cf5cf2, 04aca24, 709d6cb, 1c64638 and 3478159.
- History replay: 67 runs, **0 refused now**. Dry run clean. Applied with `--armed`.
- PR #28 was merged with the admin override. Main's CI has been red since 2026-10-29 on a research test that needs the `arch` package, which CI doesn't install; this release did not cause it.
- The Azure CLI's MFA had expired and was renewed by the team lead before the dry run.

**Open:**
- the bond-ISIN misread must be fixed before the gate returns to `halt`;
- re-pin C4's real-panel no-op test;
- CI's `arch` dependency;
- the paper-fees correction to CLAUDE.md and REFERENCES.md (team lead: not yet);
- show the team lead the first ×1.13 plan before the 2026-11-03 send.

**Rulings, later on 2026-11-02** (`docs/SYSTEM.md` §5, "autonomy"):
- **Agents may run releases and arming end to end** when every gate passes. That is now CLAUDE.md rule 1's standing authority.
- The journal is the only notice.
- The NAV hedge is closed (UNDERPOWERED).
- CI gets `requirements-research.txt` (`arch`), so main's tests can go green without touching the VM's environment.

**Found:** CLAUDE.md rule 1's 2026-10-27 exception lets the autonomous research loop trade in the same spare account that C4 will trade in. That account is flat today [V, connector read: $100,000 cash, no positions]. Before C4 is armed, the loop must be confirmed off it (rule 2).

**Research, evening of 2026-11-02** (zero trials; dates ≤ 2022-12-30; PR #30, `results/cef/screens_2026-11-02/` on its branch) [V, re-run there]:
- **Two accounts as one:**
  - the approved ×1.13 / ×1.27 is close to optimal (a joint re-split adds +0.07%/yr);
  - the accounts are uncorrelated (ρ +0.011), and Reg T never binds;
  - **arming C4 adds +6.0%/yr gross** on the fit (Sharpe 0.97 → 1.84), and turns negative between 15 and 30bp of cost.
- **New alpha:**
  - the C4 family-level discount signal is the one to **pursue**: gross Sharpe 1.12, still positive net at 30bp, correlation 0.10 with the z-book;
  - turn-of-month **pursue** as a hypothesis only: found post hoc, fails at 15bp, and part paper artefact;
  - tax-loss: WATCH;
  - killed: distribution cuts, cross-universe lead-lag, the level signal on the credit names, fast plus slow z, corporate events on the deployed 13, the live NAV drag (unpriced), the muni recall, bond holidays and leverage cost;
  - paper's uncredited distributions are a scoring artefact.
- **Found:** live turnover is 5.7× capital over 20 sessions, above the fit's 95th percentile (4.42×). On 56% of fit sessions too few names cleared, so the harness holds where the live book flattens (the other session's thin-day study).

**Rulings** (`docs/SYSTEM.md` §5):
- C4's gate runs in report mode.
- The C4 family-level signal goes to a pre-registration.
- Agents merge with the admin bypass only after CI passes on the exact head.

**Prod:** PR #29 merged (26ed351): CI is green again; autonomy is in CLAUDE.md rule 1.

## 2026-11-03 (Tue)

**C4 arming prep** (branch `c4-arm-prep`, on main f27ef81, the merge of release-20261103-1 = 336df9d; *corrected 2026-11-03: this line first said f27ef81 = release-20261103-1, but `git rev-parse release-20261103-1^{commit}` is 336df9d*). The release-check of 336df9d was GO for the core only, and the fixes below had to land before `--book c4` could be cleared. They shipped as **release-20261103-2 = de75da4** (merged as f7f7be5).
- **QR1, the C4 opening-session check:** the arming go never checked whether C4's first armed session opens at full target. The runner does so only if the account has no position and has never had a fill. The spare account is shared with the research loop, so a past fill there would open C4 at the band edge: 28–42% of target, net long [V, the release-check, `data/cef_families` to 10-09]. Now `alpaca_probe --book c4` prints `opening_session` using the runner's own rule, over the account's positions and its newest 500 closed orders. Step 6 of the checklist requires that line and the last dry plan's `opening_session` both to read True; otherwise STOP.
- **QR3:** the book jsons and the checklist now name core v9 ×1.30 and C4 v4 ×1.26 (`smult=1.2600`). `ops/tests/test_book_text.py` checks them against the specs.
- **ET1:** a C4 install now scans every book's units and any stray `quantt-` unit before it reloads. The core's install is unchanged, so the checklist adds a disk check before each core install.
- **R1, the first-session gate in code** (branch `c4-arm-gate`, left by the release-check of de75da4). Until now the only guard was checklist step 6. Now, while C4 has no fill of its own in the account, an ARMED C4 run whose account shows a position or any past fill is refused before its first order (gate 2, `arming`). The refusal names the number of filled orders and the newest one's date. Unarmed runs only record and print it, and the core is untouched. On the loop-history fixture the old runner sent 11 band-edge orders; the gate refuses. No override is built: clearing it means a fresh paper account, or a team-lead ruling.
- **R1, amended (no new account; team lead 2026-11-02).** C4's book json now sets `execution.opening_session_fills = "own_prefix"`, so only C4's own `c4-` fills count against an opening session; any position still counts. On the loop-history fixture, armed C4 now opens at full target: the same 63 orders and $188,509 gross as a fresh account. With the key absent it is still 11 band-edge orders ($20,377), which the gate refuses. The gate is narrowed: it refuses an armed first session only if the account holds a position, or an open order that is not C4's. The core has no key and is pinned byte-identical. This ships in its own release after tonight's unarmed C4 install, before any C4 arming.
- **The five fixes left by the release-check of 4f759a9** (branch `c4-arm-fixes`; the team lead ruled "no dry sessions": C4 arms at tonight's install):
  - **The gate has its own name.** A first-session refusal is now filed as `first_session` (it was `arming`), so verify scores it a MISSED day instead of a choice.
  - **A test for the cls path.** It fails when the decide-time gate line is removed.
  - **Unreadable open orders are UNMEASURED,** not clear, and armed C4 refuses on that (it failed open before).
  - **The probe pages the whole closed-order history,** as the runner does. It caps at 200 pages, beyond which it reads UNMEASURED and plan.json is the authority.
  - **Citations:** the opening rule now cites the team lead's 2026-11-03 "just flat it" (`docs/SYSTEM.md` §5, PR #30).
  - Each fix's test fails on 61589a8, and the core is unchanged by its pins.

**Prod, 16:07–16:14 ET: the core at release-20261103-4 ARMED, and C4 installed and ARMED** (standing authority; the team lead ruled "no dry sessions" and "they are on the vm").
- **Tag.** -5 (PR #41, the C4 v5 activation) had no release-check GO by 16:07, because its check died in a network outage and was restarted. So -4 = 8ce0395 went in (release-check GO 12:21 ET; PR #40 merged 4485a96).
- **Pre-flight.**
  - Today's 7-order plan was sent at 15:52 (DONE).
  - The replay: 69 runs, 0 refused now.
  - Today's send went out with 6 orders against 7 planned (gross 101,365 against 124,149). That is for tonight's read.
- **The core.**
  - stop; ET1 (no `quantt-c4*` units on disk); dry run (23 steps, no refusal); install (clone at -4, venv unchanged); apply `--armed`; verify.
  - `ops.prod_state`: VM at release-20261103-4, ARMED, timers active, laptop OFF.
- **C4.**
  - seed: treated_closes = IGR's four rebases only; sha256 `3fb68e38…` / `c7073db8…`, the same on laptop and VM.
  - dry run (18 steps) and apply (unarmed).
  - 4b: secret service active, `/run/quantt-c4/alpaca.env` quantt:quantt 600; the log names ALPACA_C4_KEY_ID and ALPACA_C4_SECRET_KEY from the vault. This is the first verification of the team lead's 11-02 "done".
- **Pre-arm reads, on the VM** (`vmrelease.sh c4-probe`):
  - positions 0, open orders 0, equity $100,000.00;
  - opening_session True under own_prefix, with 0 closed orders and 0 fills in the account's history;
  - cap re-check G_stress 1.900638 → 1.90, the same as the spec.
  - Not the core's account: the core holds positions, with equity ≈ $100,134 at the send.
  - Runners: C4's units read only `/run/quantt-c4`; AUTO_ARMED only under cef/ before arming; no laptop job loaded. The loop is research-only (the team lead, today).
- **Armed 16:13:** `c4-arm` (DRY_RUN=0, `--book c4`) and AUTO_ARMED under c4/.
  - The first armed C4 decide is 22:00 tonight, on v4 (z only) unless -5 is installed before then. The first send is 2026-11-04 15:52.

**Prod, 17:58–18:03 ET: release-20261103-5 installed. The core is unchanged and ARMED; C4 is re-armed on v5, the trial-54 blend** (team lead: "install tonight").
- **The release-check of e41f10b: NO-GO as it stood, on one ruling.** The frozen margin rule gives C4's v5 blend a cap of 1.80, not 1.90. The blend's w5 (worst 5-session loss per unit gross) is 0.0536, against the z book's 0.0261, and 0.0560 price only. In a 2020-03-12..18 week, the blend held at 1.90× loses about 10.2% of NLV, against 4.6% for the z book, and leaves equity about 5% short of initial margin.
  - The arming gate's `recap` still reads the z book's w5 from `c4_paper_benchmark_2026-11-03.json`, so the 16:13 "1.90, same as spec" was true for v4 only. **To fix: point `recap` at the live spec book's w5.**
  - **The team lead ruled "Keep 1.90, install tonight"** (`docs/SYSTEM.md` §5). That is an override of the rule's 1.80, with the blend's w5 on record.
- **Merged and tagged:** PR #41 merged as d963fb1 at its CI-green head; tag release-20261103-5 = e41f10b; the spec revert tag `spec-c4_families.v4.20261102` (ec3b01a) pushed.
- **Install sequence.**
  - `c4-stop`. The services reading "failed" were explained, not faults: the collectors' exit 5 is EXIT_INCOMPLETE (today's NAVs and EOD equity not yet in), the same as the core on 11-02. C4's 17:30 verify FAIL ("no STARTED and no plan.json") is the install-day artifact: C4 was installed after the send slot, and no gate reads a previous verdict.
  - The core: stop, dry run (23 steps), replay (69 runs, 0 refused now), install, apply `--armed`, and `ops.prod_state` showing the VM at -5, ARMED.
- **v5 on C4's real panel, read-only.**
  - A DRY preview in a scratch state dir refused on data: no NAV dated 11-03 yet, as expected before NAVs publish. It also read opening_session True, full target, and corporate actions clear.
  - `sleeve_targets` as of 2026-11-02 on the VM's C4 panel: 74 targets, 18 eligible (8 long / 10 short; 56 under the ADV floor), held gross 1.667× NAV, net 0.000, all tagged `level z_share=0.5000`.
- **C4 re-armed at 18:02.** probe: positions 0, open orders 0, opening_session True. `c4-arm` at -5; DRY_RUN=0 on both books' sessions; AUTO_ARMED under cef/ and c4/; timers active.
  - **C4's first armed decide, 22:00 tonight, is on the v5 blend.** The first sends are 2026-11-04 15:52.

**22:17–23:50 ET: the first plans read; C4 halted for 11-04 on an IGR data step** (`results/report/EVIDENCE_LOG.md` E-2026-11-03-43, -44).
- **The core's first ×1.30 plan:** 11 orders, gross 1.025× → 1.797× (the 1.80 cap binds), pre-flight ok, no refusals. It sends at 15:52 on 11-04.
- **C4's first armed plan (v5):** 15 orders, gross 1.267×, net 0, opening session CLEAR, no refusals.
- **Checklist step 5 found a STEP.** C4's first fetch replaced IGR's pre-split closes for 05-04..09-04 with Yahoo's split-adjusted ×3 against unadjusted NAVs, so IGR's discount reads about +200% for four months. The plan bought 520 IGR on it.
- **The team lead ruled "Hold C4 one day, fix IGR".** `ops/HALT_c4.md` was written on the VM at 23:47 ET; the send phase re-gates on it. The core is unaffected.
- **The fix,** a C4 fetch that keeps one price basis with its NAVs plus a step guard, goes to a release on 11-04. Then the halt clears before the 22:00 decide, and C4's first send is 11-05.

## 2026-11-04 (Wed)

**08:32–09:36 ET: the C4 IGR fix is deployed, and C4's 11-04 plan is re-decided on clean data and approved** (team lead: "can we just fix and deploy now"; `results/report/EVIDENCE_LOG.md` E-2026-11-04-11, -12).
- **The ruling.** The team lead signed the IGR split ruling: ex-date 2026-09-08, factor 1/3, to_nav_basis.
- **The release.** PR #53 was merged as b24af5e and tagged release-20261104-1 (509b3ff), after a release-check GO with conditions.
  - The core was installed ARMED and unchanged, after a replay with 0 refused now. Its ×1.30 plan sends at 15:52.
- **The repair.** The C4 panel was backed up first. repair-basis then converted 87 IGR rows at ×3.0, identical to the seed's raw closes, and IGR's premium for 05-04..09-04 is now a median of +0.64%. A direct fetch exited 0 with its BASIS IGR line.
- **The plan.** The unsent 22:00 plan was retired into `_retired/`, after confirming no send and no Alpaca orders. HALT_c4.md was cleared, and C4 was armed without AUTO_ARMED.
  - The 09:30 slot re-decided: 15 orders, gross 1.284×; IGR z −2.65, buy 1,019.
  - It was approved by sha 17ddda95… at 09:36, and AUTO_ARMED was restored.
- **Also merged:** #54, the evidence-log repair, which adds a CI test that validates the log.

**22:17 ET: the first sends, and the 11-05 plans** (`results/report/EVIDENCE_LOG.md` E-2026-11-04-13..15).
- **Both books traded and verify PASSed.**
  - The core: 11 of 11 filled, auction-marked −$232.04, fill against the auction +18.3bp.
  - C4's first session: 15 of 15 filled, auction-marked −$8.60, fill against the auction +0.7bp.
- **A correction** (E-14): the "1.797×" reported for the core's 11-04 plan was target gross. The book after the trades is 1.174×, because names inside the band don't trade to target.
- **11-05.**
  - The core decided 6 orders.
  - C4's decide is deferred on KYN's late NAV (the missing-NAV hold): it retries in later slots and decides by the 14:30 final check, with KYN held.
  - IGR's history stays clean after the nightly fetch (step 5: 0 rows moved).

## 2026-11-05 (Thu)

**The analysts' roles reopened** (team lead; `docs/SYSTEM.md` §5; `results/report/EVIDENCE_LOG.md` E-2026-11-05-31).
- The lanes become recommended starting points: FICC risk, equity risk, and cross-asset signals with the dashboard. The work is open-ended.
- Any analyst may propose a signal, and the team lead approves every test. This supersedes the 2026-11-03 report-only lanes.
- Each analyst pitches one idea to the execs at the end of November, as a short talk with slides. The date and length are still to be set.
- `docs/TEAM.md`, `docs/ONBOARDING.md`, `README.md` and the pull request template now say the same. Nothing on the live path changed.

**Execution-cost study, both paper books (report only, zero trials; `results/cef/EXEC_COST_STUDY_2026-11-05.md`, `results/report/EVIDENCE_LOG.md` E-2026-11-05-30).**
- **Where the cost comes from.** The core's paper fill vs the auction print is 7.14bp over 21 `late_market` sessions (day t 3.20). 5.90bp of it is the spread paid at send: half a cent a share, set by the tick. The remaining 1.24bp is drift to the close and not significant.
- **What would cut it.** The spread is flat from 15:51 to 15:59:30, so the send time buys no spread. Posting at the passive touch and crossing the remainder at 15:58 would have cost 4.12bp (−2.2bp, t −1.93; the CI includes zero).
- **Real money.** None of the paper cost carries over to MOC. The live cost is auction impact, which is unmeasured, on orders a notional-weighted median of 15% of the closing cross.
- **C4.** Its names quote about twice the core's spread, about 5.4%/yr at its design turnover against a modelled 10.76%/yr gross.
- **Status.** Ranked candidates are proposed and none adopted; each needs a pre-registration and a release. PR to `main`, not merged.

## 2026-11-08 (Sun)

**The check of 2026-11-05's evening, run late** (`results/report/EVIDENCE_LOG.md` E-2026-11-08-01..03).
- **Why late.** The scheduled job lives only in an open, idle session, so it ran three days after its slot. The VM was also out of reach: the ssh rule no longer matched the team lead's IP, and the team lead updated it. The VM kept running and trading throughout. The 11-06 plans sent unread.
- **Sessions.** All passed verify.
  - The core sent 5 of 6 on 11-05 (an MHD short was skipped: not shortable) and 13 of 13 on 11-06.
  - C4 sent 2 of 2 and 3 of 3.
- **Official P&L since funding.** Core −$594.02 (equity $99,405.98). C4 +$7.79 (equity $100,007.79; +$1,243.68 on 11-05, −$1,225.93 on 11-06).
- **The core's ×1.30 book has phased in:** 1.827× gross on Alpaca's values, slightly over the 1.80 cap on marks. Maintenance margin is 0.80 of equity.
- **Plans for 11-09.** The core: 13 orders, taking the book to 1.784× and net from +0.177× to +0.055×. C4: 2 orders, at 1.335×.
- **C4's data.** IGR's history is unchanged and no seed-window close moved. C4's UTF short is no longer shortable; it is an existing position and no new short is planned.

**Research is not pass or fail** (`docs/SYSTEM.md` §5, 2026-11-08; `results/report/EVIDENCE_LOG.md` E-2026-11-08-04). The team lead ruled that a failed gate should not end an idea.
- **The research line.** The power check now stops only below 0.10 and warns up to 0.50. A new Follow-up station reads every result on economics and market history, then names the next tweak or gives the reasons to set the idea aside.
- **Counting.** Every re-test and every holdout look is a counted trial, and holdouts can be re-opened. Paper trading on later data is the clean check before real money.
- **The loop.** Follow-ups come first. It no longer admits anything: it writes a scorecard and the team lead decides.
- **Not changed.** The live book's stops, real-capital admission, the analysts' process and the guides.

## 2026-11-09 (Mon)

**The mission** (`docs/SYSTEM.md` §5, 2026-11-09; `docs/MISSION.md`; `results/report/EVIDENCE_LOG.md` E-2026-11-09-01, -02).
- **Rulings.** The team lead gave a standing brief, kept verbatim as `docs/MISSION.md`.
  - Scope is open, and the CEF book is one sleeve.
  - Paper trading is the test. Research is judged on gross signal, with no cost model.
  - Pre-registration, the trial counters, the holdout ceremony, "no sweeping" and alpha-only are dropped.
  - An agent may start a paper or shadow book itself, through a separate path whose design the team lead approves once. That design is not written yet, so nothing new is on paper.
  - Prod releases are the team lead's alone again: the 2026-11-02 standing authority is withdrawn.
- **Research.** No return computed. `results/IDEA_LEDGER.md` replaces the counters and carries a one-line backfill of everything in `docs/RESEARCH_STATE.md`, which is frozen as history. 13 old ideas had a measured positive gross effect and were stopped by a gate that no longer applies.
- **Found.** `results/mission/PHASE0_2026-11-09.md`: why the book has too few bets (one signal, small universes, one horizon, gates that kept no inventory, a prod release for every sleeve); every laptop panel is stale, from about 17 sessions (the core) to seven months (futures); and the agent layer still describes the old gates. `CLAUDE.md` is rewritten and wins where they differ. The research loop now stops at its own gate until it is rebuilt.
- **Rulings, later** (`results/report/EVIDENCE_LOG.md` E-2026-11-09-03). The shadow-book runner's design is approved once (`results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md`): shadow books first, on the VM as a separate user, marked on Alpaca's auction prints with a yfinance check, $1M a book. The analysts keep `docs/TEAM.md`'s process. The agent runs the free data fetchers.
- **Built.** `shadow/`: the engine, the book file and the scoreboard, with tests (E-2026-11-09-04). No book runs yet: the fetchers, the first book and the VM install are next.
- **The desk.** Rebuilt for the mission (E-2026-11-09-05; `.claude/README.md`): seats `market-historian-economist`, `signal-hunter`, `data-scout`, `portfolio-architect`, `execution-engineer` and `go-live-reviewer`; commands `/hunt`, `/idea`, `/explore`, `/paper`, `/scoreboard`, `/combine` and `/go-live`. `/prereg` and the event census are removed, and the research loop is a stub that stops.
- **Found, later.** The R2 data API reads from the laptop: CRSP's daily file runs to 2025-12-31 [V: `results/mission/PHASE0_2026-11-09.md` §2].
- **Prod.** No change. The VM is armed at `release-20261104-1` [V: `python3 -m ops.orient`].
- **Live.** Core: verify PASS, 12 of 12 filled; official pending; snapshot equity $98,838.46 at the 2026-11-09 close [V: `python3 -m ops.orient`].

**Nightly report-only checks built** (`results/report/EVIDENCE_LOG.md` E-2026-11-09-40; PR open, not merged, not installed).
- **What.** `scripts/ops/data_qa.py` (Q1–Q8, per book) and `scripts/ops/risk_daily.py` (per account), wrapping the existing readers, on VM timers installed by a separate `install_vm --reports` (`docs/RUNBOOK.md` 8.11). Book installs and rendered units are byte-identical to before.
- **Thresholds** are derived on the fit panels to the design's budget; the calibration note says what falls short: Q3 cannot catch one-row stale copies, Q6 13/22 on the core, Q4's split-basis names are not panel steps (`results/ops/DATA_QA_CALIBRATION_2026-11-08.md`).
- **Push on ACT only** through the existing SMTP path; until the team lead adds the two vault secrets, a fired stop says `ACT: notification NOT delivered` and fails loudly.

## 2026-11-10 (Tue)

**The first shadow book** (`results/report/EVIDENCE_LOG.md` E-2026-11-10-01).
- **Research.** Month-end Treasury demand, long IEF over the last three sessions of each month, re-run gross on the harness (`results/ideas/2026-11-10_month_end_treasury.md`): Sharpe 1.07 over 2002-09 to 2026-10-09, both halves and all five eras positive, and IEF on every other session earns 0.10 [V: `python3 results/ideas/month_end_treasury/explore.py`]. It is the old XASSET-X3 with its rule unchanged.
- **Shadow.** `shadow/books/month_end_ief.json`, $1M, started 2026-11-10. Its first weighted decisions are 2026-11-23 to 11-25. Simulated: it sends no order.
- **Prod.** PRs #71 and #72 merged by the team lead on 2026-11-09 and 11-10. No release.
- **The VM.** The shadow runner is installed beside prod, at the team lead's request, as user `quantt-shadow` following the branch `shadow` (`docs/RUNBOOK.md` §8.10; E-2026-11-10-02). Its key service is active, its first run exited 0 on code `29a7006`, and its timer next fires at 18:50. Prod's units, clone and state were not touched. A first attempt at 10:12 failed at its first step and created nothing.

**The first hunt** (`results/ideas/2026-11-10_hunt_all.md`; `results/report/EVIDENCE_LOG.md` E-2026-11-10-03, -04).
- **Research.** 24 short idea cards across six mechanism types and five asset classes, ranked; each has a ledger line. Two were explored the same day, gross, on the harness:
  - **Turn of the month in equities: set aside.** Sharpe 0.48 from 1993, and SPY on every other session also scores 0.48. It is market exposure held a fifth of the time [V: `python3 results/ideas/turn_of_month_eq/explore.py`].
  - **Treasury auction cycle: explored, not promoted.** Sharpe 0.57, placebo 0.03, but 0.39 once the month-end sessions are removed and −0.02 since 2023 [V: `python3 results/ideas/ust_auction_cycle/explore.py`]. The long-bond short into the auction is the part to follow up.
- **Found.** Yahoo serves today's unfinished bar dated as a close; the new research fetcher drops it. The repo's NYSE calendar is wrong before 1998 (`docs/REFERENCES.md` §12yf).

**The first wide-universe test** (`results/report/EVIDENCE_LOG.md` E-2026-11-10-05, -06).
- **Research.** Short-term reversal within industry on the 1,500 largest US stocks, from CRSP on R2 to 2025-12-31: gross Sharpe 0.96 (t 4.90), halves 1.26 and 0.67, a stale-signal control at 0.04, and 1.35 against 0.32 by market volatility [V: `results/ideas/2026-11-10_st_reversal_wide.md`]. It clears Explore. It turns over 160 times a year, and it cannot go on shadow until a live equity panel exists.
- **Found.** The laptop's numexpr fault (`scripts/events/numexpr_fault.py`) corrupted the first run's weights, differently each time. `scripts/research/explore.py` now turns numexpr off for every Explore script, and `CLAUDE.md` landmine 11 records it. The CRSP daily file on R2 tags closed-end funds and dates each dividend, delisted funds included.

**The ex-date cycle on every closed-end fund** (`results/report/EVIDENCE_LOG.md` E-2026-11-10-07).
- **Research.** On 1,123 CEFs from CRSP (dead funds included, to 2025-12-31), a fund falls about 30bp relative to other funds over the three sessions after its ex-date, after rising about 22bp over the three before. The pre-specified book (short after, long the rest) has a gross Sharpe of 4.18, positive in every era [V: `results/ideas/2026-11-10_cef_exdate_drift.md`].
- **Checked as an artifact.** Every eligible ex-date had volume, the ex-day drop is 1.08 times the distribution, and the effect is larger in the most liquid funds. It is not stale prices.
- **Not shown by the gross figure.** Each event is worth 20 to 30bp, about a round trip through the spread; the shorts need borrow that paper does not charge; capacity is about $1–3M. It clears Explore, and the shadow book is the next build.
- **Shadow.** Two more books from 2026-11-10, $1M each, on 91 funds: `cef_exdate_after` and `cef_exdate_before_after` (`results/report/EVIDENCE_LOG.md` E-2026-11-10-08). Their ex-dates are stored by the day first seen. Three shadow books now run on the VM.

**A security fix to the broker client** (`results/report/EVIDENCE_LOG.md` E-2026-11-10-09).
- **Found.** The Alpaca client's GET and order POST, and the probe's GET, followed HTTP redirects. `requests` keeps custom headers on a redirect to another host, so a 3xx would have sent both key headers wherever it pointed. Another session's review found the same fault in its report reader and passed it on at the team lead's request. There is no evidence a redirect was ever served.
- **Fixed, not released.** Every session that carries the keys now refuses any redirect (`quantt.broker.alpaca.refuse_redirects`), and a 3xx raises naming its status; on the order POST it is the ambiguous case, never a resend. The tests run `requests`' own redirect code against a recording transport: 22 fail on the old code.
- **Prod.** Unchanged until the team lead's next release.

**Earnings drift on a wide universe, 2026-11-11** (`results/report/EVIDENCE_LOG.md` E-2026-11-11-01).
- **Research.** Drift after quarterly earnings on the 1,500 largest US stocks, IBES surprises and CRSP on R2 to 2025-12-31: the pre-specified book has a gross Sharpe of 0.21 (t 1.09); a variant sorted on the announcement move, chosen after looking, 0.73 [V: `results/ideas/2026-11-11_pead_wide.md`]. Not promoted.
- **Built.** `scripts/research/stage_ibes_surprises.py` stages the surprises outside the repository.

**Event-driven and special situations added to the mission, 2026-11-11** (`results/report/EVIDENCE_LOG.md` E-2026-11-11-02).
- **Ruled.** The team lead: the desk is event-driven and special situations as well as systematic, in any asset class, and hunts look for niche verticals there. `docs/SYSTEM.md` §5 records it; `docs/MISSION.md` §5 has the seed list; `/hunt` requires it.

**The first event test under the 2026-11-11 instruction** (`results/report/EVIDENCE_LOG.md` E-2026-11-11-03).
- **Research.** The closed-end fund ex-date trade, unchanged, on four other groups from CRSP to 2025-12-31. Partnership and trust units have it: gross Sharpe 3.03 (t 15.40), both halves, placebo −0.02. REITs weakly (0.91); ETFs and the 1,500 largest common stocks not at all [V: `results/ideas/2026-11-11_exdate_other_wrappers.md`].
- **Shadow.** Two books from 2026-11-11, $1M each, on 48 live units: `units_exdate_after` and `units_exdate_before_after` (E-2026-11-11-04). The list is rebuilt from the public exchange directory (`docs/REFERENCES.md` §12sd); 14 of the 48 were not shortable at Alpaca that day. Five shadow books now exist.

**Clustered insider buying, 2026-11-12** (`results/report/EVIDENCE_LOG.md` E-2026-11-12-01).
- **Research.** The October census rule for insider-buying clusters, tested for returns on the 2,000 largest US stocks, 2006 to 2025: gross Sharpe 0.05 (t 0.21), and what there is tracks a buy-the-losers control [V: `results/ideas/2026-11-12_insider_clusters.md`]. Set aside in liquid stocks; three quarters of the clusters are in smaller companies and are untested.

**Merger arbitrage in cash deals, 2026-11-12** (`results/report/EVIDENCE_LOG.md` E-2026-11-12-03).
- **Research.** The first returns this desk has computed on merger deals, from SDC and CRSP on R2 to 2025-12-31. Agreed (friendly) one-step cash deals earn a raw Sharpe of 0.71 (t 3.63), 0.48 over bills, with a beta of 0.17 and a 23% drawdown in 2007–08; the friendly filter was chosen after the first run. The event-time spread of the October design note is absent (0.04). An independent review re-derived the premium and found no material defect [V: `results/ideas/2026-11-12_merger_arb.md`].
- **Found.** The October EDGAR deal list only sees a deal at its proxy, so it cannot be used from the announcement date; and its 2010–22 part does not keep the first-proxy date. SDC's announcement date can be a session early (the target still rises 6.9% the session after). CRSP's new-format return carries the cash paid at closing on an extra row (`docs/REFERENCES.md` §12ma).
- **Next for this idea.** Rebuild the EDGAR list with first-proxy and termination dates: without a break date a live book holds broken deals as ordinary stocks.

**Spin-offs, 2026-11-12** (`results/report/EVIDENCE_LOG.md` E-2026-11-12-04).
- **Research.** 387 new spin-offs from CRSP, 2000 to 2025. The new company falls in each of its sessions 2 to 6 (3.2% against IWM over sessions 2–5, t −4.6) and other new listings do not. The pre-specified book, long from session 21 to 252, is weak (0.49). A short over sessions 3–5, read from the profile and so not pre-specified, has a gross Sharpe of 0.96 (t 4.84) and is positive in every era [V: `results/ideas/2026-11-12_spinoffs.md`]. An independent review found no defect; without its ten best names the book scores 0.64.
- **Open.** Whether a share can be borrowed on its second day of trading, and a live reader for upcoming spin-offs.

**The spin-off shadow book and two shadow fixes, 2026-11-14** (`results/report/EVIDENCE_LOG.md` E-2026-11-14-01).
- **Shadow.** `spinoff_first_week` starts 2026-11-16, $1M: short a new spin-off on the decisions of its first three regular-way sessions, long IWM against it. Its reader stores each Alpaca spin-off row with the day first seen, because when the feed publishes a row is not known. Six shadow books now exist.
- **Fixed.** The nightly marks step asked for every symbol on every past session; it now asks for a symbol only on sessions a decision holds it, and re-asks for a missing print for three sessions only (`shadow/nightly.py`). Needed for any book whose names change.
- **Found.** ET, SUN, SUNC and USAC print their official close on the Texas Stock Exchange, not the exchange Alpaca records, so the units books would have read UNMEASURED on every invested session. Mapped in `shadow/sources.py` (`docs/REFERENCES.md` §12so).
- **Not confirmed.** The VM has not been reachable from the laptop since 2026-11-10, so none of this, and no shadow run since 18:50 that day, has been read there. A full nightly cycle was run on the laptop against the real sources instead.

**Special dividends, the VM's shadow log, and the half-day stamp, 2026-11-15** (`results/report/EVIDENCE_LOG.md` E-2026-11-14-02, E-2026-11-15-01, E-2026-11-15-02).
- **Research.** 3,601 special cash dividends on common stocks from CRSP, 2000 to 2025. Buying the session after the announcement is public and holding to the close before the ex-date, against IWM, gives a gross Sharpe of 1.10 (t 5.57), positive in every era, 0.98 without its ten best events, and 0.62 and 0.49 on names trading $5M and $20M a day. The short after the ex-date is 0.63 and weak in liquid names; the ex-date itself is no better than an ordinary dividend [V: `results/ideas/2026-11-15_special_dividends.md`].
- **Shadow.** `specdiv_wait` is built with a first-seen reader of Alpaca's dividend feed and tested on the real feed. It is a local commit only: the team lead stopped pushes on 2026-11-15, so it is not on the VM.
- **Read.** The VM's shadow log, for the first time since 2026-11-10: the books decided and were marked on 2026-11-12 and 11-13; every run ended non-zero because four units had no closing print (fixed 2026-11-14, on the `shadow` branch) and one run stopped when Alpaca's record for ET named the exchange `TXSE` (mapped 2026-11-15 after measuring 11 listings).
- **Fixed, merged as #83.** Alpaca stamps a half day's end-of-day point at 17:00 New York; the client required 20:00 and would have stopped the official P&L record from 2026-11-27. Not released yet.

**IPO lock-ups and reverse splits, 2026-11-15** (`results/report/EVIDENCE_LOG.md` E-2026-11-15-03, E-2026-11-15-04).
- **Lock-ups.** The textbook three-session short around an IPO lock-up expiry is 0.56 gross over 2000 to 2025 and about zero since 2016; the fall now comes in the four sessions before the date, a window found after looking. Not promoted [V: `results/ideas/2026-11-15_ipo_lockups.md`].
- **Reverse splits.** Shorting a common share for 20 sessions after its reverse split, against IWM, is 1.02 gross (t 5.18) and positive in every era. Alpaca marks 4 of the 32 names such a book would hold today as shortable, so it is set aside as a short and no shadow book was built [V: `results/ideas/2026-11-15_reverse_splits.md`].
- **Local only.** Both are local commits; pushes are stopped (team lead, 2026-11-15).
- **Follow-on offerings** (E-2026-11-15-05). Buying an issuer three sessions after a follow-on is priced and holding five sessions is 0.71 gross over 2000 to 2025 and about 0.15 since 2016; the short over the next forty sessions is 0.07. Not promoted [V: `results/ideas/2026-11-15_follow_ons.md`].
- **Special dividends, corrected** (E-2026-11-15-06). Against 8-K filings, 2 of 34 sampled events were not public when the book filled. Entering one to three sessions later gives 0.89 to 0.98 instead of 1.10, and about zero in 2023–25 instead of 0.64. The trade is strong in 2008 to 2022 and unproven since; the shadow book is the test [V: `results/ideas/2026-11-15_special_dividends.md`].
