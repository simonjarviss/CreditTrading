# QUANTT — the system

**The one document that says what this book is, how it runs, and what we know
about it.** Written 2026-09-13; rewritten for the move to Alpaca and the clean
slate on 2026-09-28 (the documents it replaced are at tag `pre-clean-slate`).

**It holds no figures that move.** Where a number matters, this document names
the command that produces it. Run the command. The only figures written here
are decisions (which carry a date and a decider) and a few observations that
are labelled `[V]` verified, `[S]` sourced but not re-read, or `[U]` uncertain,
each with a date and the note it came from. Why: every number this repo wrote
into prose about its own state was contradicted by another document within
days — the arm rate existed as four different fractions at once.

`docs/INDEX.md` lists which document owns which question. `CLAUDE.md` holds the
rules. `docs/ROADMAP.md` is the plan to prod. `docs/HISTORY.md` says what existed
before the clean slate; git (tag `pre-clean-slate`) holds it, as provenance, never
authority.

---

## 0. How to know anything

**Order of authority**, highest first. When two sources disagree, the higher one
is right and the lower one is a defect to fix — do not average them and do not
pick one silently.

1. **The broker** — what is resting, what executed, what is held.
2. **The frozen spec**, `ops/specs/cef_discount.frozen.json` — every live
   parameter. Prose about parameters is always downstream of it.
3. **A measuring command, run now** — `python3 -m ops.orient` first.
4. **This document** — the shape of the system and the standing decisions.
5. **A dated results note** in `results/` — true as of its date, by its method.
6. **Git history** (tag `pre-clean-slate`) — provenance only.

**Which artifact answers which question.** Keyed by question, not by quantity,
because most contradictions in this repo's history were two artifacts
answering different questions.

| question | authoritative artifact |
|---|---|
| Where am I, what is the spec, what do the Alpaca accounts look like? | `python3 -m ops.orient` |
| Is anything trading, and from where? | `python3 -m ops.orient` PROD: which machine is prod, at which tag, and whether it is armed, measured each run. The SessionStart banner and status line read the same measurement (`ops/prod_state.py`). |
| What is held, resting or executed at the broker? | The Alpaca paper account for that book — `python3 -m quantt.broker.alpaca_probe` (read-only snapshot, one account per book). The broker is the fact. |
| Is a name tradable / shortable / hard-to-borrow at Alpaca? | The probe snapshot's `assets`, dated — `borrow_status` changes daily |
| What did the IBKR book hold, send and fill? | History only, at tag `pre-clean-slate`: `pre-clean-slate:_archive/prod_state_2026-09-28/` and `pre-clean-slate:results/ops/ALPACA_MIGRATION_MANIFEST_2026-09-28.md` §7 |
| What are the live parameters? | orient SPEC, which reads the frozen spec through `scripts/cef/spec.py` |
| Gross / net Sharpe and turnover of the live policy? | `python3 scripts/cef/band_frontier.py`, re-run |
| IC, persistence, PCA, ADV, vol scalar? | `python3 scripts/cef/plan_diagnostics.py`, re-run |
| How many trials have been spent? | `docs/RESEARCH_STATE.md` counter table (not its prose); orient TRIALS derives the deflated-Sharpe bar |
| How many tests pass? | `python3 -m pytest`, run now. Never quote a stored count. |
| What is left to do for the Alpaca system? | `docs/ROADMAP.md` |
| Is an external claim verified? | `docs/REFERENCES.md` |
| Do the documents still say true things? | `python3 -m ops.doc_audit` |

---

## 1. What we trade

> **2026-11-09 (team lead, §5): this section describes the core CEF sleeve.** Scope is now open and the
> CEF book is one sleeve among those the desk is building toward one combined book (`docs/MISSION.md`).

A **systematic credit closed-end-fund discount-reversion book** that places its
own MOC orders on a schedule. It ran on an IBKR paper account until 2026-09-28
and has traded on Alpaca paper since 2026-09-29 (§4). Capital and
universe are in the frozen spec. **Mandate** (§5): on paper now, with **real capital
planned** (team lead, 2026-10-09); judged on absolute return under a vol cap.

**The trade.** A closed-end fund publishes a net asset value daily and its
shares trade at whatever the market pays. Buy funds unusually cheap against
*their own* discount history, short the ones unusually rich, in equal dollars.

**Why it is not arbitraged away.** A CEF has a fixed share count and no
authorised participants. Nothing creates or redeems shares against the basket,
so no mechanism drags price back to NAV. The mechanisms, who is on the other
side and why they stay there: `docs/BRIEF.md` §2. How the
instruments actually trade — NAV timing, ex-distribution arithmetic, the
closing auction, the short side, corporate events: `docs/BRIEF.md` §3.

**Signal.** For fund *i* on day *t*, discount `d = 100·(P − N)/N`; z-score it
against that fund's own rolling mean and standard deviation, both **shifted one
day** (point-in-time), clipped. Window: orient SPEC `z_window`. It was once
changed to the argmax of a swept column, failed out of sample hours later, and
was reverted — the project's most instructive event.

**Weights.** Cross-sectionally demeaned z, negated, scaled to unit gross, times
a volatility scalar (`vol_target_annual` from the spec over trailing realised
vol, clipped). Three consequences:

- **Cross-sectional, not absolute** — a fund is cheap relative to today's mean
  z, which makes the book dollar-neutral by construction.
- **Ranked against its own history, not peers** — ranking on the raw discount
  would be a permanent long-muni bet dressed as a signal.
- **Volatility-targeted, measured not assumed** — the strategy is best in calm
  markets; a constant-notional book takes its worst losses when each unit of
  risk pays least.

Code: `src/deploy/sleeves/cef_discount.py` **is** the strategy.

**Trading policy: a no-trade band** (since 2026-09-06). The signal is recomputed
every session; a position is left alone unless it is more than `band_width`
(orient SPEC) from target, then traded back to the **band edge, not to target**
— the proportional-cost optimum (Constantinides 1986; Davis & Norman 1990). The
width was derived from a cube-root law, not swept. `rebalance_days` is inert
while `band_width` is set; deleting `band_width` restores the previous calendar
policy exactly, which is the revert path (the v5 spec file itself is at tag
`pre-clean-slate`, `pre-clean-slate:_archive/ops/_archive/cef_discount.v5.20260731.frozen.json`).
Pre-registration: `results/cef/PREREG_BAND_2026-09-06.md`.

**Execution: MOC, and `shift(2)`.** Decide at *t*, fill in the closing auction
of *t+1*, earn the *t+2* return. Every backtest must reproduce that;
`evaluate()` in `scripts/cef/band_frontier.py` is the canonical implementation,
and `EXEC_LAG` in `scripts/cef/validate.py` is asserted at runtime. Why MOC and
not a market order: `CLAUDE.md`, order-path rule 3.

**Universe and holdouts.** The deployed names are the spec's `universe`;
`data/cef/cef_universe.csv` holds the wider set. Two holdouts are sealed until
a pre-registered test opens them (research agents may re-open one, each look counted
and labelled: §5, 2026-11-08): **the untouched CEFs** outside the deployed universe (trading any of
them consumes the set), and **a 2023-01-01 time holdout** on every fit.

---

## 2. What is established, what is conditional, what is unknown

Keeping these apart is the most important discipline here. Each claim names
the command or note that settles it. **Before quoting one, check `results/` for
a later note** — this section records the state as of its date.

### Established

| claim | settle it with |
|---|---|
| The discount signal has a real, persistent IC at the traded horizon, present across sub-periods **on the wide 17-name set without the ADV filter** (−0.078, t −11.1, 2005–22; the −0.074 quoted elsewhere). *Corrected 2026-10-11 (team lead): this row read as if it held for the book. It does not; see the deployed signal under "Measured but conditional".* | `python3 scripts/cef/plan_diagnostics.py`; `python3 scripts/cef/w4_artifacts.py`; `pre-clean-slate:results/cef/ALPHA_AUDIT_2026-09-05.md` |
| It is not credit beta, not one name, not reversal | `pre-clean-slate:results/cef/ALPHA_AUDIT_2026-09-05.md` |
| The **retired calendar policy fails** the validation battery at an obtainable price (`shift(2)`): deflated Sharpe FAIL at every trial count tried | `python3 scripts/cef/validate.py --trials <CEF counter>`; `pre-clean-slate:results/cef/EXECUTION_CONVENTION_2026-09-10.md` |
| The sealed CEF holdout was opened and its recorded verdict is **FAIL** on net Sharpe; its gross figure is not out-of-sample evidence | `pre-clean-slate:results/cef/HOLDOUT_OPENED.json` |
| The book is not short volatility in a sense that gives a hedging option a job; credit gamma is not timeable by any declared conditioner | `pre-clean-slate:results/cef/STRESS_BETA_2026-09-11.md`; `pre-clean-slate:results/gamma/CONDITIONERS_2026-09-13.md` |

### Measured but conditional

- **The signal the book actually trades is much weaker than the wide set's**
  (W4, 2026-10-11, `results/cef/W4_ARTIFACTS_2026-10-11.md`,
  `python3 scripts/cef/w4_artifacts.py`; panels to 2022-12-30 only). The 13
  deployed names with the ADV filter: IC **−0.033 (t −1.68)** on 523
  non-overlapping dates from 2013-06, significant in no single era; half the
  summed IC sits on December–January signal dates. Its P&L is stronger than its
  rank IC (factor alpha t 2.94 daily on FF5 + momentum, every |β| ≤ 0.021; 3.22 monthly with Pástor–Stambaugh), and none of bounce, stale
  NAV, distributions, ex-dates or crises explains more than about 7% of it.
- **The band's net Sharpe and turnover** come from the correct harness but have
  **never been walk-forwarded, bootstrapped or deflated** — nothing in this repo
  tests the traded policy out of sample (2026-09-13 [S], `CLAUDE.md`). That is
  the largest open research gap.
- **Borrow drag** was first charged from one day of fees; the daily fee history
  (`data/cef/cef_borrow_history.parquet`) shows much higher historical borrow on
  some names, so any net-of-borrow figure computed on one day's fees is suspect
  until re-measured. `pre-clean-slate:results/cef/BORROW_NOTE_2026-09-06.md`, `docs/BRIEF.md` H4.

### Unknown, and the unknowns dominate

- **What execution actually costs.** Very few broker-confirmed MOC sessions
  exist (all IBKR, now deleted); the standard error is too wide to act on. Alpaca
  paper fills MOC at the quote rather than in the auction [V: staff forum post,
  2026-09-28], so its paper fills cannot settle this either.
- **Whether the paper record means anything.** The pre-epoch ledger booked
  fills for sessions the account never made; only broker-confirmed fills count.
  The IBKR record ended on 2026-09-28 with 34 flatten orders left unacknowledged
  and the account's final state unknown by decision; the Alpaca book starts a new
  track record.
- **Survivorship.** The panel holds only funds alive today; every CEF that
  closed or merged is absent. The bias is upward and unmeasured.

---

## 3. What binds

The book earns through one relation, Grinold's fundamental law in the Clarke,
de Silva & Thorley (2002) form: **IR ≈ IC · TC · √BR**. Derivation and the three
meanings of "finding alpha": `docs/BRIEF.md` §1.

- **IC** is good, and sharpening it has repeatedly been the least productive
  work.
- **TC, the transfer coefficient** — how much of the ideal book survives costs,
  borrow, availability, rounding and missed sessions — is low. Measure it as net
  ÷ gross from `band_frontier.py` with borrow charged.
- **BR, breadth** — the book holds many names but most of its variance is one
  factor, municipal CEFs against taxable ones, so its effective breadth is a
  small fraction of its name count. Measure on today's weights (the IBKR-era
  dashboard's `/api/factors` did this; it was deleted and has no replacement yet).
- **Uptime** — a session that does not arm earns nothing. On IBKR the book armed
  on a small minority of eligible sessions (session logs at tag `pre-clean-slate`);
  the Alpaca runner must measure its own from day one.

**Work that raises TC or uptime beats work that sharpens IC, every time.**

---

## 4. How it runs

**Rewritten 2026-09-28.** The IBKR-era description — prod worktree and
promotion, launchd sessions, the shared account, halts, verification — is at tag
`pre-clean-slate` (`pre-clean-slate:_archive/docs/SYSTEM_2026-09-28.md` §4). None of it runs any more.

### 4.1 Where things are

*Updated 2026-10-08: this list said "nothing trades" and "prod does not exist
yet", both true when written on 2026-09-28 and false from 2026-09-29.*

- **The book trades on Alpaca paper** from a prod clone of this repository at a
  release tag. The first armed session was 2026-09-29, from the laptop under
  launchd. On 2026-10-08 prod moved to an Azure VM under systemd (§5,
  `docs/RUNBOOK.md` §8). **Which machine is prod now, at which tag, and whether
  it is armed: `python3 -m ops.orient` PROD.** It is never written here.
- **IBKR was retired on 2026-09-28.** The scheduler's jobs were unloaded, a final
  flatten was sent and then abandoned (the team lead chose not to follow it up),
  and the repo was cut to a clean slate: everything not needed for the Alpaca
  system was deleted (tag `pre-clean-slate`; `docs/HISTORY.md`). `ibkr-final`
  tags the last IBKR-era commit.
- **The strategy is unchanged in kind**: `src/deploy/sleeves/cef_discount.py` and
  its frozen spec, v7 on Alpaca since 2026-09-28 (§5). `python3 -m ops.orient`
  SPEC gives the live spec id.
- **The run package is `quantt/`**: the broker client and probe
  (`quantt/broker/`), the session runner (`quantt/session/`, design
  `docs/RUNNER.md`), the nightly collector (`quantt/collect/`) and the prod
  installers (`quantt/deploy/`: launchd and systemd).

### 4.2 What the Alpaca system must be

Settled by the team lead on 2026-09-28 (§5) or measured from Alpaca's own
documentation the same day [V unless marked]. The design work is still ahead;
this is the brief it answers to.

- **One Alpaca paper account per book**: the CEF book and the b6 equal-weight
  credit benchmark. Alpaca rejects opposite-side orders in one symbol as wash
  trades, so books cannot share an account safely.
- **MOC via `time_in_force=cls`**, whole shares only (fractional orders cannot
  be `cls` or short). Alpaca rejects `cls` entries between 15:50 and 19:00 ET.
- **Not idempotent.** A runner must refuse to send while a set is already
  headed for an unclosed auction; Alpaca's `client_order_id` is unique only
  among *active* orders.
- **The broker is the fact.** Reconcile from Alpaca's positions, orders and
  account activities, not from a local ledger. The IBKR design's ledger
  desyncs halted all three books in September.
- **Score both P&Ls on paper.** Alpaca paper fills MOC at the quote [V: staff
  forum post], so record Alpaca's fill as the official record and the P&L at the
  official closing-auction print (`/v2/stocks/auctions`, SIP feed) beside it,
  labelled. Gross P&L only (D19/D20, 2026-09-15). The official Alpaca number is
  its end-of-day portfolio history; a reading taken after the close is a
  labelled snapshot (team lead, 2026-10-19, §5).
- **Alerting is dashboard and logs only** (hardening D3/D4, 2026-09-21,
  confirmed 2026-09-28). A monitor will be rebuilt later.

### 4.3 What counts as evidence

**Only broker-confirmed fills** count toward any live statistic. Modelled
sessions are not evidence. On Alpaca paper the fill price itself is simulated
(above), which is why the auction-print P&L is kept beside it.

### 4.4 Setting up, and reference

- Environment and data: `README.md` (setup).
- The plan to prod: `docs/ROADMAP.md`.
- Credentials live in `config/.env`, which is never printed, copied or read by
  an agent (`CLAUDE.md`, order-path rule 5).

---

## 5. Standing decisions

Moved **as recorded** from `docs/BRIEF.md` §7 and `CLAUDE.md`, in the
order they were made. Work-order ids in the rows (W14, `gamma/`, P-numbers) name
prompts that have since closed; their text is at tag `pre-clean-slate` under `pre-clean-slate:_archive/docs/prompts/`. Nothing here was re-decided when this document was
written. A later entry on the same question supersedes an earlier one only
where it says so; changing a row needs the team lead's name and a date (§7).

### Team lead, 2026-09-08

| question | decision |
|---|---|
| Universe | **Keep the 17.** They already are the liquid set (median $5.6m ADV). The 27 are the illiquid tail. Liquidity enters as a tilt (W11 §D), not a cut. |
| Gamma scalping's role | **Both** a hedge overlay judged on the tail and a timed standalone sleeve — W14 §A decides which survives. |
| Intraday scalping | **Research first** on PDI/PTY (W13 §C). MOC stays live; nothing intraday trades without its own pre-registration. |
| Decision timing | **Morning primary, evening fallback** (W3): 08:30 on yesterday's complete pair, MOC for today's close; 12:00 retry; 17:30 capture. From Thursday 2026-09-10. |
| Price source | **IBKR daily bars primary, yfinance cross-check.** |
| NAV source | **Free channels only:** yfinance X-tickers, CEFConnect dated history, sponsor first-party. Agreement to the cent, or the name is incomplete. |
| Options data | The R2 trades source if it carries HYG/LQD/TLT; QuantConnect research (results only) if not. |
| Gamma timing conditioners | **All three in one pre-registered run.** Adopt at most one. |
| Gamma sleeve size | **Derived, Σ⁻¹·IR** against the CEF book. May be zero. |
| Holdout | **Keep the 27 and add a 2023–2026 time holdout** to every fit. |
| Trial counters | **Two**: CEF and GAMMA, each its own bar. |
| Risk controls | **Arm HALVE/KILL on broker-confirmed NAV** once W6 §A lands. |
| Capital | **Paper indefinitely; a competition track record.** No real capital planned. *(Superseded 2026-10-09: real capital soon, below.)* |
| Judged on | **Absolute return.** Derive the vol target, **cap 20%**, with kill-probability and margin-cushion constraints. |
| Options permission | **Unknown** → W2 audits it first; every options part refuses to start without "permitted". |
| Other books | **Keep the five benchmarks; retire the null trader.** |

### Team lead, 2026-09-09

| question | decision |
|---|---|
| Per-fund treatment | **Seventeen sleeves, one combined book.** Each fund gets its own signal, band, budget and P&L line; they sum into one portfolio where neutrality, borrow and capacity are managed at book level. → `perfund/F3` |
| Signal structure | **Model form by group (four mechanisms), parameters by fund shrunk within group.** Four trials, not seventeen. → `perfund/F2` |
| What neutrality means | **Undecided by design.** Four candidate rules are pre-declared and tested as one grid; the tie-break is p95 net exposure, not Sharpe. → `perfund/F3` Part B |
| Gamma scalping | **A standalone programme with its own counter and track record** (`gamma/`), **and** the hedge-overlay use case kept in the CEF queue (`W14`), gated on stress-beta evidence. |
| Sources | Every external claim lives in **`docs/REFERENCES.md`** with a verification status. Prompts cite it; they do not re-derive it. |

### Team lead, 2026-09-14

Recorded during the documentation cleanup, in answer to two contradictions the
new documents exposed. Neither changes what trades.

| question | decision |
|---|---|
| Vol target until W6 | **The frozen spec's `vol_target_annual` stays in force** (0.06 when this was decided) **until W6 derives a new value** under the 2026-09-08 "derive it, cap 20%" decision. Until then the two are not in conflict: one is the setting, the other is how its replacement will be chosen. |
| Retiring the null trader | **Open, not yet actioned.** The 2026-09-08 decision stands; `phase0_null` is still a registered book and is halted in prod. Retiring it needs broker-side work a human runs (W2). |

### Team lead, 2026-09-28 — IBKR retired, move to Alpaca

Answered interactively; the full record (the migration manifest) is at tag
`pre-clean-slate`, `pre-clean-slate:results/ops/ALPACA_MIGRATION_MANIFEST_2026-09-28.md` §2 and §7.

| question | decision |
|---|---|
| Broker | **Alpaca paper**, our own choice (not a competition requirement). |
| IBKR | **Flatten, archive everything, forget it.** The flatten was sent and left unconfirmed by decision. |
| New system | **Fresh package (`quantt/`), reusing parts.** |
| Books | **The CEF strategy and the b6 equal-weight credit benchmark.** phase0/null trader, b1/b3/b4/b5 and credit_rv retire. |
| Accounts | **One Alpaca paper account per book**, $100k each (the default). |
| Scoring | **Record both**: Alpaca's paper fill is the official record; the closing-auction-print P&L is logged beside it. *(Refined 2026-10-19, below: the official Alpaca number is its end-of-day portfolio history; the 17:30 reading is a snapshot.)* |
| Hosting | **Cloud VM.** |
| Alerting | **Dashboard and logs only** (keeps hardening D3/D4). |
| Spec | **v7 from day one on Alpaca**, superseding hardening D14. `max_gross_stress` is re-derived on the Alpaca account; `min_trade_usd` and capital re-sized through `/spec-change`. |
| CEF trial counter | **48 is authoritative**; adopting v7 makes it 49. |
| Work orders, dashboard | **Archived**; new work orders as needed; a dashboard rebuilt later. `00_BRIEF` stays live as `docs/BRIEF.md`. |
| Who runs order-path commands | **The agent may, when the team lead asks in the session, after showing the concrete order list and getting a go.** |
| `CLAUDE.md` / settings | **The agent edits them directly for the migration** (supersedes hardening D15/D18 for this work). |
| Clean slate | **Delete everything not needed to run the strategy on Alpaca**, now, before building — supersedes the "never delete, archive" rule. Kept: the strategy and spec, research harness and fetchers, research memory (`RESEARCH_STATE`, `BRIEF`, `REFERENCES`), the band and group-cap pre-registrations, the agents and skills. Old research replaced by `docs/HISTORY.md`. Everything is recoverable from tag `pre-clean-slate`. |
| Research tables | **Gross P&L headline, cost grid beside it, labelled, never mixed.** |
| Universe on Alpaca | **Drop NAD, NEA, NVG, NZF** (not shortable on the Alpaca paper account, probe 2026-09-28). 17 → 13. |
| v7 on Alpaca | **`max_gross_stress` 1.80** (re-derived: Reg T **50%** margin); **`group_cap` off** (its rule gives k = 0 on 13 names, the killed hard-neutrality variant); **`min_trade_usd` $0** (the formula with no per-order fee; whole shares only); capital $100k. The 13-name backtest was **report only, not a gate**. Spec `cef_discount.v7.20260928`; `results/cef/PREREG_ALPACA_V7_2026-09-28.md`; CEF counter 48 → 50. |

### Team lead, 2026-09-28 (evening) — the runner and go-live

Answered interactively while the runner was built. The design they shape is
`docs/RUNNER.md`; the Alpaca facts behind them are
`results/ops/ALPACA_API_FACTS_2026-09-28.md`.

| question | decision |
|---|---|
| Go-live | **Armed on 2026-09-29.** The first session's order list is shown to the team lead before transmit. |
| Where prod runs | **This laptop for now**, a clone at a release tag scheduled by launchd. No VM yet; the free Google Cloud e2-micro was offered and declined for now. |
| After the first go | **The scheduled runner trades daily on its own**, behind the nine gates. Rule 1 in `CLAUDE.md` governs agents in a chat. |
| Day one | **Trade to full target** (`extras["opening_session"]`), not to the band edge. |
| Phase 3 probes | **Design around them**; no probe orders on the account. |
| If `cls` is rejected | **No trade, then ask the team lead.** No fallback to `day`. |
| Hard-to-borrow shorts | **Allowed if `shortable`**; hard-to-borrow is a warning in the preview. |
| A rejected order mid-batch | **Skip that name, send the rest**; the day is FAIL, naming it. An ambiguous submit still stops the batch. |
| Key file for the scheduled job | **Stays `config/.env`**; whether launchd can read it under `~/Downloads` is tested on install, and fails loudly if not. |
| Research and backtest | **Saved workflows** (`.claude/workflows/`); research data from the R2 WRDS mirror (`docs/DATA.md`), never on the live path. |

### Team lead, 2026-09-29 — flexible schedule and nightly data

After the first armed session (13 `cls` orders accepted at 10:33 ET, plan_sha
`74154e1e…`, sent on the team lead's go). Design: `docs/RUNNER.md` "As built
(2026-09-29)".

| question | decision |
|---|---|
| When the session runs | **Evening primary and morning backstop.** Evening 22:00 ET, retrying every 30 min until 01:00; morning every 30 min 06:00–15:15 ET. No fixed time. |
| Data gathering | **A standalone nightly collector**: prices and NAVs cross-checked, Alpaca official closes, an account and fills snapshot, distributions and splits. |
| Two data sources disagree | **Report only.** The panel (yfinance) is traded on; the disagreement is written to the daily data report. It never blocks and is never averaged. |
| Rollout | **Deploy after the 2026-09-29 verify; the evening run stays DRY** until the team lead approves a list. The first real evening send also tests Alpaca's overnight `cls` queue on paper. |
| Paper under-fills `cls` (2 of 13 filled on 2026-09-29) | First: keep `cls` with a shadow benchmark. **Superseded the same evening:** "obviously this is unacceptable" -- **paper sends market `day` orders 15:52–15:58 ET** (decided in the evening, sent from the saved plan), a recorded exception to rule 3 for the paper account only. The shadow benchmark stays; fills are scored against the official close in bp. |
| Arming for the 15:52 send | **Fully automatic from 2026-09-29 evening:** prod installed with DRY_RUN=0 and `AUTO_ARMED`; every decided plan is sent in the late window without a per-day go. `ops/HALT.md` or reinstalling dry stops it. |
| Cloud server | **Not yet**; the laptop stays prod. Revisit after a week of fills. |
| The two unhedged longs left by that day (PHK 4,019, PFN 1,529) | **Not flattened.** Both are part of the target; the next session trades from them (the band applies: it is no longer the opening session). |

### Team lead, 2026-10-07 — the cloud VM

The "revisit after a week of fills" above. The evidence: from 2026-09-30 to
2026-10-07 the laptop sent no orders on 2026-10-02, 2026-10-05 and 2026-10-06,
each time because it was asleep or offline (`~/quantt_state/cef/verify.log` and
the day folders beside it, read 2026-10-07). The plan is `docs/ROADMAP.md`
phase 6; the procedure is `docs/RUNBOOK.md` §8.

| question | decision |
|---|---|
| Cloud server | **Azure for Students** (no card), a `Standard_B2pts_v2` VM (Arm64, like the laptop) in `canadacentral`, the allowed region closest to New York. Supersedes "Not yet" above. The laptop stays prod until the cut-over. Google Cloud's free-tier e2-micro was chosen first the same day and dropped because it needs a card. |
| What it costs | The VM size is free for 12 months; anything else (disk, public IP, Key Vault) comes out of the $100 student credit. When the credit or the 12 months run out the subscription is disabled and **the book stops**: check the balance in the portal and renew yearly while a student. |

### Team lead, 2026-10-08 — cut over to the VM today, fully automated

| question | decision |
|---|---|
| Shadow length | **Skipped.** "Why don't we just deploy everything to the VM and see if it can trade today?" The 3-trading-day shadow proposed on 2026-10-07 was replaced by one morning of dry runs on the VM. That covered the full decide from start to finish, keys and account reads, and a plan matching the laptop's (same 8 orders; 2 names 1 share apart, explained by equity read 0.02% apart). |
| Cut-over | **2026-10-08 11:32–11:38 ET**, `docs/RUNBOOK.md` §8.5, steps 1b–4. Laptop launchd jobs unloaded and disabled, laptop `AUTO_ARMED` removed (kept renamed), laptop state copied to the VM, VM armed (`DRY_RUN=0`) at `release-20261008-2`. Step 1a (re-installing the laptop plists disarmed) was blocked by the agent's permission classifier, so the disabled laptop plists still say `DRY_RUN=0` on disk. |
| First VM send | **2026-10-08, the laptop's decided plan `c5f20357…` (8 orders)**, approved by the team lead ("go") and recorded with `quantt.session approve`, sent by the VM's 15:52 timer. |
| Automation | **"I want the VM fully automated and deployed, gathering trade data and doing trades on PROD while we make improvements here on non-prod to push to VM prod."** `AUTO_ARMED` is created on the VM after the first armed send's verify PASSes. Improvements are developed in the dev tree, pass release-check, and reach the VM as release tags through `install_vm` (`docs/RUNBOOK.md` §8.6). |

### Team lead, 2026-10-09 — real capital, the research programme, and how it is counted

Answered interactively after the 2026-10-08/09 research passes
(`results/cef/RESEARCH_AGENDA_2026-10-08.md`, `results/cef/SCALING_RESEARCH_2026-10-08.md`).
The programme these rulings shape is `results/cef/RESEARCH_PLAN_2026-10-09.md`.

| question | decision |
|---|---|
| Capital | **Real capital soon.** This supersedes 2026-09-08's "Paper indefinitely; no real capital planned". Timing, size and broker are still open. Two consequences: (1) **the real-money cost re-run is the gate for deploying any capital**: measured borrow, distributions owed on shorts, real auction fills; (2) the paper `late_market` exception never applies to a live account (`CLAUDE.md` order-path rule 3). |
| Instruments in bounds | **Alpaca-listed, cash bonds, futures and swaps through another broker, and options.** Options reopen **only** through a pre-registered, standalone short-premium test that meets the six conditions in `SCALING_RESEARCH_2026-10-08.md` §7.2. This partly supersedes "options are closed" (2026-09-13, below). |
| Target and leverage | **≥10%/yr absolute return, measured gross of costs, with net shown beside it.** Reg T for now (`max_gross_stress` 1.80). The vol target is derived under W6 (cap 20%). Portfolio margin and a futures account are research items, not assumptions. |
| The 27-name holdout (H9) | **Opened for the event trades** (merger pair, corporate-action layer, CEF IPO pair, term CEFs). It supersedes 2026-09-08's "Keep the 27". The set is **consumed by the first pre-registered test that computes returns on a name in `data/cef/cef_universe.csv`**, and that pre-registration must say so. After that, H9 has no name comparison set. **The 2023-01-01 time holdout stays sealed.** |
| Trial counters | **A new counter per data source:** EVENTS (corporate actions from EDGAR and CRSP: the merger pair, CEF IPOs, convertible issuance, term and tender events) and XASSET (the cross-asset ETF and futures slate, declared up front). Options are on GAMMA. Changes to the live CEF book stay on CEF. *The author's reading, flag it if wrong:* the discount z-score on other CEF families (agenda B1) is the same data and signal, so it goes on CEF. |
| TLT short-volatility data | **Fit and decide on Cboe VXTLT, 2004–2022.** The 2023+ strike data is the GAMMA holdout, opened once for the defined-risk version. |
| Where a passing sleeve runs | **Inside the CEF account, one combined book.** Consistent with 2026-09-09's "seventeen sleeves, one combined book". |
| Deliberate beta | **No: alpha only.** A sleeve must earn beyond beta (D4). Beta is tolerated only as residual exposure, never as a sized sleeve. Carry (agenda Track D) is closed. |
| Dividends on paper | **Add a third P&L line**, distribution-adjusted: it credits distributions on longs and charges them on shorts. It sits beside Alpaca's fill and the auction-print P&L, because Alpaca paper credits no dividends. |

### Team lead, 2026-10-09 and 2026-10-11 — the missed day and the stress cap

On 2026-10-09 the VM refused both sends on `max_gross_stress` × live equity, for a
plan that took gross down; the book did not trade and verify said PASS. The
incident and the audit are `docs/RUNNER.md`, "As built (2026-10-09, amended
2026-10-11)".

| question | decision |
|---|---|
| The fix (2026-10-09) | **"Go"**, to "what can you do to make sure this never happens again": a plan that does not add gross always passes the stress cap; the send-time re-fit fits the cap as one of its limits; a no-trade day not explained by `DRY_RUN`, arming or a halt is a `MISSED:` FAIL; an advisory evening pre-flight at equity minus the held book's worst one-day loss. |
| Which equity the cap is judged on (2026-10-11) | **The lower of the equity the plan was sized on and live equity**, for a plan that adds gross. Chosen over "sizing rule only" (the sized equity alone, which the 2026-10-11 release-check showed lets an adding plan exceed the derived G_stress 1.843 × live once equity falls more than 2.34% after decide) and over a new live-bound spec key. With `bp_shortfall = scale` the send's re-fit scales such a plan to fit instead of refusing it. Uses the existing `max_gross_stress`; no new key. |

### Team lead, 2026-10-12 — open items closed

| question | decision |
|---|---|
| Alerts (healthchecks.io, proposed 2026-10-09) | **Not needed.** A missed day shows as a `MISSED:` FAIL in verify, orient and the status line. |
| SEC EDGAR contact | **The team lead's own address**, in the EDGAR request `User-Agent` only, read from `config/.env` (`SEC_USER_AGENT`) and never written into the repository. Unblocks plan 0.7 and 0.8. |
| An options quote feed (plan 0.10) | **Measure the price first**, then decide. |
| Account identifiers in probe snapshots | **Redact from now on.** The probe writes no account number or ID; the committed 2026-09-28 snapshot is redacted in a new commit (git history keeps the old value: a paper account, not worth a rewrite). |
| The 7 ETF panels rebuilt 2026-10-11 although byte-identity failed | **Keep them.** The originals stay beside them as `*.pre-20261011.bak`. |
| SYSTEM.md §2's IC row | **Corrected**: the −0.074 is the wide 17-name set; the deployed book's is −0.033 (W4). |
| TLT option spreads for gate G2 (plan 0.10) | **A historical fit-period spread series replaces "20 live sessions"**; any live capture is confirmation only. |
| Is 2023–26 TLT option data the GAMMA holdout? | **Spreads and costs from 2023+ may be used; return-based statistics stay sealed.** This narrows 2026-10-09's "the 2023+ strike data is the GAMMA holdout". |
| OptionMetrics | **Use it only if it is in our own data access.** Measured 2026-10-12: the R2 WRDS mirror (412 tables) has no `optionm` table, and there are no WRDS credentials on the desk, so it is unavailable. |
| Paid options data | **None.** Only data in our own access (R2, Alpaca's free feeds) or free data from another free API. G2 runs as a conservative gate: an upper-bound spread and a bounded-loss crash replay. |

### Team lead, 2026-10-13 — stale NAVs at decide time

The defect: Yahoo serves a NAV row dated D that carries an older NAV, and the
date-only freshness check passes it (`results/cef/LIVE_NAV_QUALITY_2026-10-12.md`
§5). The design is `docs/RUNNER.md`, "As built (2026-10-13): the stale-NAV gate";
the replays behind the redesign are `docs/REFERENCES.md` §12s.

| question | decision |
|---|---|
| A deployed name whose NAV(D) equals its NAV(D−1) at decide time | **"Use CEFConnect, else drop."** *(Superseded the same day by the redesign below: its replay found that dropping at the evening decide would have flattened the book on 2026-10-05.)* |
| The stale-NAV gate, redesigned | **Team lead, 2026-10-13: stale-NAV gate redesigned.** It triggers when NAV(D) equals the previous NAV, or CEFConnect's NAV(D−1) (the PDI case). If CEFConnect has D and differs, its value is used through the logged fallback; if it agrees, the row is kept. If CEFConnect has no row or errors, the name is not dropped: it is re-verified in the morning backstop, and still unverified at the last pre-send check it keeps its current shares and leaves the cross-section. It is never targeted to zero, and holds never trigger the `min_names` flatten. **Report mode first, `on` after a measured week.** |
| The collector | **Flag "NAV(D) = NAV(D−1) and unverified"** instead of recording a silent gap, and **log when each name's CEFConnect row for D first appears.** |
| How it is switched | A runner setting in the book json (`data.stale_nav`: absent off, `report`, `on`). Which mode is set is that file, not this one. |

### Team lead, 2026-10-14 — release, trials approved

| question | decision |
|---|---|
| `release-20261014-1` | **Installed on the VM, armed,** at 17:05 ET, after the day's send. It carries phase 0, the verify fix (MISSED on a send scaled to zero orders), the exact fit, and the stale-NAV gate in `report` mode. Release-check said GO on the second run, after the first run's two defects were fixed |
| C5, the opening-auction fill | **Approved: CEF trial 51,** on the pre-registration's defaults. Any paper `opg` test order is shown to the team lead before it is sent |
| C4, five CEF families pooled | **Approved: CEF trial 52,** on defaults 1–7. The holdout ends 2026-09-30 |
| The XASSET slate | **Approved at revision 3, with X5 withdrawn: N = 4.** The bar is √(2 ln 4) = 1.665 |
| The CRSP values in a pushed log | **Leave git history as it is.** The 11 dated differences in commit `225f459` are not printed by the script any more; public history is not rewritten |

### Team lead, 2026-10-19 — the interrupted work and the research slate

The work cut off by the usage limit on 2026-10-16 was finished and merged on
2026-10-18; these are the rulings on what it found. What each one produced is in
the notes it names; this table holds the decisions only.

| question | decision |
|---|---|
| C4 (CEF trial 52): which holdout book is the verdict | **The corrected book** (four bad IGR bars fixed): PASS, with a recorded deviation because the fix came after the opening. **Paper only; no real-money sleeve.** `results/cef/C4_RESULT_2026-10-14.md` §9 |
| C5 (CEF trial 51): the holdout's D-5 halt | **Add a repair rule**: a D-5 name-day takes the NYSE closing print where it and a second source agree; then form the holdout gain once. C5 stays KILLED (D1) whatever it shows. `results/cef/C5_RESULT_2026-10-14.md` |
| HALVE and KILL drawdown limits (in the spec, read by no live code) | **Build enforcement in `report` mode first**; the team lead installs it. `on` is a later ruling |
| CEFConnect's terms prohibit automated commercial use | **An options brief first**, with a draft permission request to Nuveen. The live path is unchanged until the team lead chooses |
| The event-extraction engine's API pilot | **No API spend.** A rules-only baseline, and a pilot run through Claude Code subagents |
| Merger arbitrage (fails D4) | **Not closed.** Reconstruct it so that what is left is alpha, and bring a design that passes D4 |
| E1, the CEF merger pair | **Spend an EVENTS trial on it** (pre-registration first), although the ETF-hedge gate failed; IBKR's borrow is admissible for the short leg |
| IBKR | **Open it as a second broker, equities only** (no options data), for the shorts Alpaca will not lend. The team lead holds the account and the weekly two-factor login. *(Narrows 2026-09-28's retirement of IBKR; the book still trades at Alpaca.)* |
| SPACs | **Redeem through IBKR**, and re-run the SPAC gate on IBKR's terms |
| NAV tenders | **Draft the pre-registration** (an EVENTS trial) |
| Process fixes from C4's IGR bars (zero trials) | **Both:** a spike-and-revert guard in `yf_total_returns`, and no P&L while any Stage-0 flag lacks a recorded ruling |
| Pushing `main` | **One push at the end of the day**, after the suite, the doc audit and the identifier scan |
| E1 (later the same day, after seeing that IBKR borrow eats the muni effect in 6 of 7 windows) | **Approved as EVENTS trial 1, with borrow fees ignored: "ignore fees, just look at PnL."** Borrow is shown in its own labelled column and decides nothing (amendment 1 of the pre-registration) |
| The NAV-tender pre-registration | **Approved as EVENTS trial 2, on all twelve defaults** |
| The EVENTS bar | **N = 6, shared by every EVENTS trial**, E2's draft included |
| C5's three readings of the repair rule | **Confirmed** (`results/cef/C5_RESULT_2026-10-14.md`) |
| The release check for HALVE/KILL | **Run after the other session's official-equity hotfix is merged into `main`** |

### Team lead, 2026-10-19 — HALVE/KILL in report mode

The frozen spec's two drawdown lines were read by no code on the Alpaca path,
and the runner never called `risk_check`
(`results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md` §1 item 4, re-verified
2026-10-19). The design is `docs/RUNNER.md`, "As built (2026-10-19): the drawdown
check".

| question | decision |
|---|---|
| HALVE/KILL on the Alpaca runner | **Report mode first.** Every decide measures the drawdown from the high-water mark against `risk.halve_drawdown` / `risk.kill_drawdown` (read from the frozen spec, never a literal) and records it, with what an acting mode would do. It changes no order. This wires the 2026-09-08 "arm HALVE/KILL on broker-confirmed NAV" decision without arming it; arming (an acting mode) is a later ruling |
| Which equity series | **Alpaca's end-of-day portfolio history (1D), the official daily P&L**, in `<state>/eod_equity.csv`. Not `equity.csv`, whose after-hours snapshots can set a false high-water mark. Absent or unreadable is UNMEASURED; never a fallback |
| How it is switched | A runner setting in the book json (`risk.drawdown`: absent off, `report`). Which mode is set is that file, not this one. An acting mode is not built, and setting one raises |

### Team lead, 2026-10-19 — P&L of record

The defect: verify's line called the 17:30 ET `equity − last_equity` reading
"(official, gross)". That reading is marked after the close. On the four days
the team lead's session compared on 2026-10-19 it disagreed with Alpaca's own
end-of-day portfolio history every time. On the same days the history agreed
with the auction-marked score (`docs/REFERENCES.md` §12an). The design is
`docs/RUNNER.md`, "As built (2026-10-19)".

| question | decision |
|---|---|
| The paper book's official daily P&L | **Alpaca's end-of-day portfolio history** (`GET /v2/account/portfolio/history`, `timeframe=1D`) is the official daily P&L of record. This refines 2026-09-28's "Alpaca's paper fill is the official record": the official number is still Alpaca's, but it is the end-of-day history, not a reading taken after the close. |
| The 17:10 / 17:30 ET `equity − last_equity` reading (`quantt/session/score.py` `alpaca_equity_change`, the verify line, `equity.csv`) | **A labelled snapshot, kept, never blended.** |

### Team lead, 2026-10-20 — IBKR and SPACs, after the evening's measurements

| question | decision |
|---|---|
| IBKR as a second broker | **Wait for a trigger** (narrows 2026-10-19's "open it"). No account, build or VM resize until one fires: E1 passes; NAV tenders pass and keep the IBKR muni hedge; the SPAC gate passes with real capital; the core-book benefit, re-run with a measured blocking rate and that day's fees, beats the fixed cost; or a proposal re-admits the four dropped munis. `results/ops/IBKR_WORTH_IT_2026-10-19.md` |
| SPACs | **Closed under D4, zero trials spent.** The deadline-only route fails the alpha-only rule at zero trials (`results/events/SPAC_DEADLINE_PRESCREEN_2026-10-19.md`); vote redemption at IBKR is moot while IBKR waits for a trigger |
| The new event paths' zero-trial checks (A1 issuance at a premium, A2 insider buying, B1/B2 muni hazard flags) | **All three closed, zero trials** (`results/events/A1_CEF_ISSUANCE_GATE_2026-10-20.md`, `results/events/A2_INSIDER_BUYING_GATE_2026-10-20.md`, `results/cef/MUNI_HAZARD_FLAGS_GATE_2026-10-20.md`) |
| E1 and NAV-tender Stage-0 rulings | **All recommended rulings accepted** (E1: 15 items, amendment 2; NAV tenders: 72 flags). Both trials wait only on the team lead's credentialed data pulls |
| C4's double-applied splits (BTO, TYG, NXG, EMO) | **drop_split.** Only the report-only R-yf row moves, 1.131 → 1.130; the verdict is unchanged |
| Merger arbitrage, MA-HZ (after the CRSP measurement: hump holds, cost marginal, P(D4 pass) about 1–10%) | **WATCH, no trial** (`results/events/MERGER_ARB_V2_2026-10-19.md` §5.6) |

### Team lead, 2026-10-22: the pod

Three analysts join for the year. Answered interactively; how it works day to day is
`docs/TEAM.md`, and setting up is `docs/ONBOARDING.md`.

| question | decision |
|---|---|
| How the work is split | *(Superseded later the same day by "the lanes revised", below.)* **Sleeve owners by counter.** One analyst keeps EVENTS; one keeps XASSET and GAMMA; one keeps the research platform (fetchers, CI, tests, the read-only dashboard). The team lead keeps the core CEF book (CEF), execution and costs, the live path and prod. "The main work falls to me" (team lead) |
| How far the platform lane reaches | *(Superseded later the same day, below.)* **Research platform only.** `quantt/` and the runner stay with the team lead |
| Live-path changes from analysts | **Yes, by pull request only.** Anyone may propose a change to any file; nothing reaches prod until the team lead tags a release |
| Review | **The team lead is the only reviewer and the only person who merges** |
| How changes arrive | **Branches in this repository**, pushed by the analysts as repository collaborators with Write. *(Revised the same day: the first answer, "one GitHub team, `credit-analysts`", cannot work from the team lead's account. The team lead is an organisation member, not an owner; a team holds only organisation members, and only an owner invites into the organisation.)* Rulesets let only the team lead update `main` and create, move or delete the protected tags. The team lead is their only bypass actor and keeps pushing `main` as before |
| Branches on GitHub | **Five, and no others**: `main`; one per analyst, cut from `main` (named for the lanes, below: `macro/work`, `equities/work`, `dashboard/work`; first cut as `events/work`, `xasset/work`, `platform/work`); and the team lead's `pm/work`. *(Revised the same day: one branch per lane, with `gamma/work` and short topic branches, became one per analyst.)* `pm/work` took in the three EVENTS branches as they were on GitHub (`trial-events-e1`, `trial-events-navtender`, `research-ss-expansion`), which were then removed from GitHub; E1's newer local commits, carrying control-pool permnos, stay off it until the team lead rules. A pull request opened by the team lead has its own branch only while it is open |
| What each lane works on this year | **A first draft in `README.md`, written from `results/cef/RESEARCH_PLAN_2026-10-09.md` and `docs/RESEARCH_STATE.md`**, for the team lead to correct before it merges |
| The organisation's owners | **Accepted, and stated.** The QUANTT organisation's owners keep admin rights over every repository in it, including the power to edit these rulesets. The rulesets do not exempt them, so a bypass is a deliberate, recorded change (`docs/TEAM.md` §6) |
| Names in the repository | *(Superseded for the branch names on 2026-10-26, below.)* **None.** The repository is public: it names lanes, and who is in them is the team lead's record and GitHub's collaborator list |
| Analysts' data access | **Each analyst holds their own**: a read-only R2 token from the team lead, a free Alpaca paper account of their own, and their own `SEC_USER_AGENT`. This narrows 2026-10-12's "the team lead's own address" to the team lead's machines. No analyst holds a key to the book's account or a route to the VM |
| The analysts' machines | **Macs** |

### Team lead, 2026-10-22, later: the lanes revised

The same day, the team lead redrew the three analyst lanes. `docs/TEAM.md` §1 holds
who keeps which paths; the counter is in `docs/RESEARCH_STATE.md`.

| question | decision |
|---|---|
| The first analyst lane | **FICC event-driven signals (macro and thematic events), integrated into the strategy.** Code in `scripts/macro/` |
| How that lane is counted | **All on a new counter, MACRO, a running count** opened at 0, whether a signal is an overlay on the CEF book or its own sleeve. For this lane it sets aside 2026-10-09's "changes to the live CEF book stay on CEF" |
| The corporate-event work (NAV tenders, the special-situations slate, E2–E4, E1's holdout) | **Moves to the team lead**, on EVENTS |
| The options test (G1, GAMMA) | **Moves to the team lead** |
| The second analyst lane | **Equities and ETFs, all on XASSET**, each slate declared up front, single names included |
| The third analyst lane | **The read-only dashboard, plus what the team lead assigns case by case.** The data platform and CI stay with the team lead unless assigned |
| The analysts' branches | **Renamed to match**: `macro/work`, `equities/work`, `dashboard/work` (they were unused, identical to `main`) |

### Team lead, 2026-10-26: what the lanes feed, and their scope to December

Answered interactively, before the analysts were invited. `docs/TEAM.md` §1 holds
who keeps which paths. The working plan to 2026-12-31 names people, so it is the
team lead's, sent to the analysts directly, and never tracked.

| question | decision |
|---|---|
| What the analysts' signals feed | **One multi-sleeve book**: the CEF book, the EVENTS sleeves and any analyst sleeve, combined at book level (`results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md`). A passing signal joins as a sleeve of its own, an overlay or conditioner on the CEF book, or a hedge |
| Whether any of the team lead's work moves to an analyst | **None.** The EVENTS rows (the special-situations slate and reserves, the ETF hedge overlay for event longs), the S3 forced-deletion row on WATCH and GAMMA stay with the team lead. The analysts bring new signals only |
| The MACRO lane's scope | **All of fixed income**, widened from "macro and thematic events": macro events (central-bank decisions, economic releases, Treasury auctions), credit events, and fixed-income instruments (rate and credit ETFs, preferreds, baby bonds), each tied to how it helps the book. Still all on MACRO, and still excluding the rows above |
| The third lane's scope | **The dashboard and the research data platform**: the fetchers and data builds the other lanes build on, and the event store once the EVENTS work on `simon` (was `pm/work`) is merged into `main`. CI (`.github/`, `pytest.ini`, `conftest.py`) stays with the team lead |
| The dashboard's data | **A nightly read-only snapshot of the book, held in the repository** under `dashboard/snapshots/`. The exporter that writes it runs on the VM, so the dashboard lane writes its spec and its tests and the team lead installs it. How a snapshot travels from the VM to the repository is **open**, for the team lead when the exporter is ready. The repository is public: a committed snapshot is published (`dashboard/README.md` says what it may never carry) |
| The analysts' tools | **Claude Code, for all three**, with the repository's skills and agents |
| The branches | **Named for the people, not the lanes**: `simon` (was `pm/work`), `ryan` (was `macro/work`), `james` (was `equities/work`), `lucy` (was `dashboard/work`), renamed on GitHub with their history. Still five on GitHub with `main`. This supersedes 2026-10-22's "names in the repository: none" for the branch names and the lane map in `docs/TEAM.md`; the repository is public, so those first names are public. Nothing else names a person |

*(Partly superseded 2026-10-09, above: one pre-registered standalone short-premium test may reopen options.)*
**Options are closed, and it is recorded rather than remembered.** `W14` Part A
measured that this book is not short volatility in any sense that gives a hedging
option a job. `G6` then measured that credit gamma costs more in variance than
equity gamma, and that no conditioner times it — C3 clears in sample and fails
the 2023–26 holdout, and no state under any conditioner at any declared
threshold has a positive mean outcome. `G7` does not run and the **GAMMA counter
stays at 0**. The pre-registration (`pre-clean-slate:results/gamma/PREREG_GAMMA_TIMING_2026-09-13.md`)
records what would reopen it. The options status tool, the option-pricing library
and the IBKR option order path were deleted on 2026-09-28 (tag `pre-clean-slate`).

---

### Team lead, 2026-10-26 and 2026-10-27 — the screens, the ex-date drift, and C4 on paper

Answered interactively. The five zero-trial screens are in `results/cef/screens_2026-10-26/README.md`. The
counter is in `docs/RESEARCH_STATE.md`.

| question | decision |
|---|---|
| Macro regime filters on the core book | **Measured first, at zero trials** (2005–22). Nothing found: no group's own observable changes the within-group IC (`r1_macro_state/`). The same goes for FOMC, CPI and NFP days (`r2_macro_days/`) |
| C4 to paper, after the ex-date check came back MIXED | **Proceed anyway** (2026-10-26). Paper is scored against a price-only backtest, because paper charges shorts no distribution. The plan is `results/cef/C4_DEPLOY_PLAN_2026-10-27.md` |
| Where C4 trades | **Its own paper account**: the never-traded paper account behind the Alpaca connector (created 2026-09-29). **This is an exception to 2026-10-09's "one combined book"**, because the runner's gates refuse a shared account (`quantt/session/gate.py` gates 6 and 9). The team lead adds its keys as `ALPACA_C4_KEY_ID` / `_SECRET_KEY` |
| C4's setup | **The plan's §3, as a set:** its own $100k, the spec's vol target and its own gross cap; no CEFConnect for C4 (the NAV-repeat mask instead); shorts Alpaca will not lend are skipped, with no substitute; halt on a fidelity break; reverse below the price-only 5th percentile at 120 sessions, or on a drawdown past the fit's worst; the 9 non-NYSE funds scored as gaps for now. *2026-10-29, within the 2026-10-28 C4 fast-track: their official closes are now mapped (NYSE American `A`, Nasdaq `Q`, condition `M`; `docs/REFERENCES.md` §12bl). Gaps already recorded for past days are not refilled by that change* |
| The post-ex-date drift | **Pre-registration approved, all 17 recommended answers** (2026-10-27). Part (b) is EVENTS trial 3 at N = 7; part (a) is withdrawn on power. `results/events/PREREG_EXDATE_DRIFT_2026-10-26.md` |
| R2 pulls for the BDC and index-rebalance screens | **Run by the team lead** (2026-10-27), into a gitignored `_cache_` folder under results/events (never committed: the rows are licensed) |

### Team lead, 2026-10-27: the research method

Answered interactively after the zero-trial audit of 82 kills and the desk
rebuild (`results/research/DESK_METHOD_2026-10-27.md` §7).

| question | decision |
|---|---|
| Which deflated-Sharpe bar gates | **The paper's bar** (Gumbel expected maximum, effective N, measured cross-trial V[SR_n]), **once trials store their daily P&L series**. Until then both bars are shown, labelled, and the desk's √(2 ln N) on the raw counter gates |
| The power gate | **In the `research-idea` workflow only**, not a `CLAUDE.md` rule. The workflow stops when any P(pass) is below 0.5, unless overridden. *(Changed 2026-11-08, above: it stops below 0.10 and warns below 0.50.)* |
| Admission by marginal contribution | **Allowed, paper only.** A sleeve that fails the standalone deflated Sharpe may join the paper book, labelled, if it adds to the book (SR > ρ·SR_book across ρ's range) and the combined net is positive across the 5/15/30bp grid. Real capital keeps the standalone gate (`results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md` §2.1). *(Paper entry became the team lead's decision on a scorecard, 2026-11-08, above. Real capital is unchanged.)* |
| Evidence outcome | **Every verdict records PRESENT / ABSENT / INCONCLUSIVE beside its D-code**, and C5, E1 and X1 are relabelled (`docs/RESEARCH_STATE.md`, 2026-10-27 note) |
| The audit's zero-trial re-opens | **All queued, in this order:** (1) NAV tenders and E1 judged by their contribution to the book, on fit-period series only; (2) C5 as an execution choice, with the opening-auction cost re-measured on 2023–26 quotes; (3) X3 hedged against TERM, power check first because its holdout is spent; (4) A1 as a conditioner, G2's two named inputs, MA-HZ on the 2001 census. Each spends no trial; any test that follows is pre-registered |
| Trial P&L series | **Backfill what is reproducible.** Re-run each past trial whose script still reproduces, store its daily series, and list those that cannot be rebuilt. The desk's bar keeps gating until it is done |
| Admission by marginal contribution, after re-open (1) (**2026-10-28**) | **Kept as written:** "Kept the paper-admission rule as written, after seeing that, under the 1.80× cap, NAV tenders lowers the book's Sharpe and E1 leaves it flat." Ruled on the first version of `results/research/REOPEN_BOOK_NAVTENDER_E1_2026-10-28.md` (b43bf35). That note's paper view, with book and sleeve both on price returns, was found afterwards by an independent review: NAV tenders no longer meets the rule, and E1 still does. Superseded the same day by the next row |
| How the paper's bar is computed once a counter qualifies (**2026-10-28**) | **With safeguards.** N is the counter's declared slate size, adjusted by the measured mean correlation (negative counts as 0). The cross-trial variance is floored at the null 1/T, because a spread measured on two to four trials is noise. `scripts/research/inference.py::safeguarded_sr0`. On the 2026-10-28 backfill (`results/research/BACKFILL_TRIAL_SERIES_2026-10-28.md`), EVENTS and XASSET qualify. Their hurdles (annualised Sharpe) are EVENTS 0.36 against the desk's 0.53, and XASSET 0.34 against 0.44. Unfloored, EVENTS' would be 0.06 |
| E1's route to paper, ruled **2026-10-28** | **Try IBKR paper.** Alpaca paper processes no corporate actions, so E1 cannot run there as specified (`results/events/E1_PAPER_BROKER_CHECK_2026-10-28.md`). Whether IBKR paper does is unknown. The check is that note's Activity Statement step, for the team lead's login |
| The broker for real capital, ruled **2026-10-28** | **Wait for Alpaca Canada.** Alpaca live is not open to Canadian residents: "Alpaca Clearing & Custody Canada Ltd. is not yet a CIRO Dealer Member". IBKR Canada is the only current broker that fits the book (`results/ops/BROKER_OPTIONS_CANADA_2026-10-28.md`), and it was not chosen. **Real capital is deferred** until Alpaca Canada is approved, which takes at least six months, scope [U]. This narrows 2026-10-09's "real capital soon". Re-check Alpaca's Canadian status each quarter: whether it offers the trading API, closing-auction orders, short selling and paper |
| Where paper runs meanwhile, ruled **2026-10-28** | **Alpaca paper, unchanged.** IBKR paper processes no dividends or splits either, so moving buys no corporate-action gain |
| A corporate-action halt gate for the paper runner, ruled **2026-10-28** | **Build a HALT guard.** Paper keeps a split or merged name at its old share count, and the runner reads broker counts as they are. So a session refuses when Alpaca lists a non-dividend corporate action naming a held or targeted name, in any role, inside that name's window. It also refuses when the list cannot be read. It runs at decide and again at the send (`docs/RUNNER.md`, "As built (2026-10-28)"). A runner setting in the book json (`corporate_actions.mode`: absent off, `report`, `halt`). Which mode is set is that file, not this one |
| The corporate-action gate's windows, ruled **2026-10-29** | **Two windows.** A merger acquirer, in any of the three merger types, and a match through the process date alone use the short window `(as-of, session]`. The acquirer is judged on its market date only: the feed listed each real MQY merger twice, processed on consecutive days. *Re-review, the same day, flagged to the team lead: a reorganization's allocated leg goes on the short window too, and a held name's long window starts at the trading day before its last fill's submission, the latest close that fill was sized on.* They halt for one session and then clear: by the next session the as-of close and the counts are post-event and consistent. Every other role keeps the long window, which reaches back to when the name's shares were last set: acquiree, splits, stock dividends, spin-offs, reorganizations, name changes (paper may leave the position under the old symbol), redemptions, worthless removals and partial calls. The feed is read with `data_quality=all`. A long-window halt on a held name follows `docs/RUNBOOK.md` §6.1, which covers phantom P&L, and orders go only through the team lead |
| E1, ruled **2026-10-28** | **Parked until real capital.** No paper account open to the desk processes mergers. A merged-away position would sit in the account and distort the P&L of record. E1 stays eligible and untraded |
| Re-opens (3) and (4), ruled **2026-10-28** | **X3 hedged against TERM: closed at the power gate.** As a fifth declared XASSET test, P(pass) is ≤ 0.13 over 10 years at net Sharpe 0.44–0.55 (`results/research/REOPEN_X3_FORWARD_POWER_2026-10-28.md`). **G2 and MA-HZ: closed, UNDERPOWERED,** with no data pulled. MA-HZ's P(pass) is ≤ 7% after post-publication decay (`results/events/MERGER_ARB_V2_2026-10-19.md`); G2's variance premium is t 1.33 before 2023, which no cost convention makes significant (`results/gamma/G2_GATE_FREE_DATA_2026-10-12.md`). **A1: run the zero-trial live-book measurement.** It compares the fit-period P&L of the book's shorts inside versus outside share-issuance programme windows. It computes P&L on the deployed names, which A1's brief excluded |
| Which bar gates the CEF counter, ruled **2026-10-28** | **The desk's √(2 ln N) on the raw counter, unchanged.** 50 of CEF's 52 trials cannot be rebuilt without opening the 2023 time holdout, or their scripts were deleted, their ids are ambiguous, or they ran at `shift(1)`. So the paper's switch condition can never be met. Those unrebuildable trials are also the ones whose correlation cannot be measured |
| Which bar gates a qualifying counter with one stored trial (**2026-10-28, later**) | **The desk's √(2 ln N) at the declared N, until a second trial is stored**; from then, the safeguarded paper bar. With one trial the correlation between trials cannot be measured, so the paper's bar is refused (`scripts/research/registry.py::paper_sr0`, refusal code `one_trial`). Extends 2026-10-27's "the desk's bar gates until the paper's inputs exist", and is the stricter of the two bars. Chosen over treating the unmeasured ρ̄ as 0, and over closing the standalone route for that trial. Any other refusal of the paper's bar still closes the standalone route |
| Which return convention decides paper admission (**2026-10-28, later**) | **Paper's own P&L of record** (Alpaca paper, which pays no distributions), on the paper view of `results/research/REOPEN_BOOK_NAVTENDER_E1_2026-10-28.md` at f7b4562. **NAV tenders does not qualify for the paper book.** On that view its gross Sharpe is 0.055 and the combined book falls from 0.959 to 0.738. It remains a real-capital candidate on total returns. **E1 qualifies.** Admission still goes through `quant-trader`'s rollout: a broker check (whether Alpaca paper processes a merger conversion is unknown), then shadow, then a paper sleeve |

### Team lead, 2026-10-27: the autonomous loop and the harness

Answered interactively in the session that ran the two deep-research reports on
method and backtest infrastructure. The reports themselves are not in the repo.
Their verified findings are cited in the docstrings of `scripts/research/`.

| question | decision |
|---|---|
| Where agents trade | **A new agent-lab Alpaca paper account**, which the team lead creates and keys (the spare connector account belongs to C4). The loop transmits there through the `quantt` runner without a per-session go (`CLAUDE.md` hard rule 1, recorded exception). **A lab sleeve is promoted into the main paper book by the loop itself** once the criteria fixed in its pre-registration are met; the VM install keeps the team lead's `!`. Live capital is unchanged: hard rule 1 |
| Who approves a trial | **The loop, with no cap.** Every trial is still counted in `docs/RESEARCH_STATE.md` in the same commit, and stores its daily P&L with `scripts/research/registry.py`. Each one raises the bar for the next |
| Where agents trade, revised 2026-10-28 | **Not a new account.** The lab uses the attached Alpaca account (the spare connector account), which C4 also trades in (team lead, 2026-10-28). The runner sizes orders from the account's open positions, and Alpaca rejects opposite-side orders in one symbol (CLAUDE.md landmine 2). So lab sleeves must be netted into C4's targets symbol by symbol, or the runner must hold positions per book. That is decided when the lab book is built, on top of C4's multi-book runner work (C4's 2026-10-27 deploy plan, row 6A, on the C4 branches) |
| Where and how often | **The team lead's laptop**, a scheduled Claude Code session, **one research cycle per day** after the close |
| The backtester | **`evaluate()` may be restructured as necessary.** Done: `scripts/research/harness.py`. `band_frontier.evaluate` delegates to it, byte-identical on the live book (`results/research/HARNESS_RESTRUCTURE_2026-10-27.md`). The named gaps were non-CEF families and an ML pipeline (`scripts/research/ml.py`) |

### Team lead, 2026-10-28 and 2026-10-29 — the data fixes, the releases, and adding all three sleeves

Answered interactively. Day by day, what was found, shipped and earned is in
`docs/JOURNAL.md`. The counters are in `docs/RESEARCH_STATE.md`.

| question | decision |
|---|---|
| `fetch_daily` wrote yfinance's empty ex-date rows over good bars | **Fix it, NAV side included, in one release.** Shipped as `release-20261028-1` |
| Prod's panel held 91 empty Feb–Apr 2026 closes, older than the refetch window | **Measure the effect, then repair** from Alpaca's official closing prints. Applied 2026-10-28; 4 NYSE American cells are left empty |
| Gross headroom for more sleeves | **Build the combiner first, dark; decide placement after.** Each addition goes live only after its own test passes (superseded below by "add all 3") |
| How risk is split | **The best risk-adjusted return, good returns.** Equal risk across sleeves, per account (independent review, 2026-10-29) |
| One missing NAV refuses all 13 names, as on 2026-10-22, since CEFConnect died | **Hold that fund and trade the rest**, for at most **2 consecutive sessions**. The limit is a POLICY, not derived, to be reviewed against the live gaps. **Switched ON 2026-10-29** (`release-20261029-3`) |
| The collector ends INCOMPLETE because CEFConnect is down | **Record CEFConnect as an unavailable second source** |
| A replacement NAV source | **The team lead chases the Nuveen and Nasdaq Fund Network replies.** No code |
| C4's gross cap | **1.90, re-derived by the core's frozen rule.** H11 and the stop rule read the 1.90 book. **Not counted as a CEF trial**: applying a frozen rule with no performance test, unlike trial 50. Re-derive against the shared account's margin before arming |
| IGR's four bad bars in C4's seed | **Seed with the trial's 2026-10-19 correction**, logged per cell. The guard accepts exactly those four |
| Two or three sleeves | **Three is preferred.** If the ex-date short passes, it trades in the **spare account beside C4** (no symbol overlap) |
| The three additions (2026-10-29) | **Add all three, on paper:** C4 (passed); the **ex-date short as a forward test** (EVENTS trial 3; the sealed 2023+ test still runs once French publishes, and trading forward does not touch it); and **PCEF reconstitution as EVENTS trial 4 (N = 8)** in a **third paper account**, approved with every recommended answer except question 1, which the team lead overrode to spend the trial. Its counter moves in the commit that records its pre-registration |
| How big the untested sleeves start | **A full equal-risk share from day one**, for all four sleeves |
| PR #20's gate-6 defect (another session's corporate-action gate) | **Fix it** (branch `fix-gate6-stale`). Nothing from `main`'s head is released until it is fixed |
| A record of progress | **A desk journal in the repo:** `docs/JOURNAL.md`, updated in the same commit as each change |
| Corporate-action gate (PR #20), a malformed row (empty or null required symbol) | **Skip it, and record it, unless it could concern one of our funds**; refuse only then. Before this, any malformed row in the market could stop the book |
| A corporate-action row with a missing (null or empty) party symbol, which can be neither ruled in nor out as ours (release-checks 2026-10-30 to 11-02) | **Team lead, 2026-11-02:** it **halts only when a well-formed row with the same type and dates would halt for one of our held funds** (the gate's short and long windows), naming the row. **The team lead clears it with `ca-ack`**, matched on its full content, so a revised row halts again. Outside those windows it is recorded only, and never needs a release to unstick. *Correction (2026-11-02): the row first written here on 2026-11-01 read "a null party symbol always refuses". That was the agent's reading of ruling A, recorded as a ruling in error. The team lead never made it, and the release-check of 2026-11-02 showed it would stop the book indefinitely on one malformed row anywhere in the market.* |
| Trial 53 (core ×1.13) and the corporate-action gate ship together (2026-11-02), but the gate's fixes might not pass review in time | **Ship trial 53 regardless**: if the gate fails its release-check, the book runs with `corporate_actions` in **report** mode (records, does not block). Prod had no gate at all before this. It switches to `halt` in the next release |
| C4's account (2026-11-02) | **No new account: the existing spare paper account** (ruled 2026-10-27). The team lead puts its API keys in the vault as `alpaca-c4-key-id` and `alpaca-c4-secret-key` (RUNBOOK §8). Putting C4 inside the core's account was declined: shared gross cap, the combiner cannot yet run with the missing-NAV hold, and the trial-53 sizing assumes two accounts |
| Corporate-action gate, a backfilled name change, redemption, worthless removal or partial call that never clears under `halt` | **It clears by the team lead's recorded acknowledgement** of that action ID only (`ca-ack` CLI, logged; RUNBOOK §6.1) |
| When `main`, with the corporate-action gate on, is released | **After A, B and the gate-6 fix are built**: one release-check, one VM update |
| Sizing the sleeves, after the four-sleeve analysis showed equal shares across three $100k accounts give about 6.1%/yr (2026-10-30) | **Maximise the % return on all capital**, the real-money view. **Core + C4** at their per-account equal-risk multipliers (core ×1.24, C4 ×1.41, 5.75% combined target; about 9% gross on the fit). The ex-date short and PCEF stay built but off, because they lower the percentage. This supersedes 2026-10-29's "full equal-risk share for every sleeve" |
| Raising the core's vol target (×1.24, about 6% → 7.4%) | **Pre-register it as CEF trial 53** (`results/cef/PREREG_VOLTARGET_2026-10-30.md`; approved 2026-11-01 at the milder ×1.13 / ×1.27, see the next section) through /spec-change. The counter moves on approval |
| C4's HALVE/KILL drawdown levels | **The core's levels**, in report mode, until a C4-specific derivation exists |
| PCEF holdings | **Invesco gave written consent** (team lead, 2026-10-30). The team lead saves a copy outside the public repo; its date and scope are cited in `docs/REFERENCES.md` before any automated download |

### Team lead, 2026-11-08 — research is not pass or fail

Answered interactively on 2026-11-08, after the team lead said of the desk's research: "not a no go no only rules, we need
to be dynamic - this is too binary". It covers the research agents and the research loop.

| question | decision |
|---|---|
| The power check in `research-idea` | **Stop only at very low odds: any P(pass) below 0.10.** From 0.10 to 0.50 the test runs, with a warning at the top of the pre-registration. The team lead can still override with `override_power`. 0.10 is the figure offered in the question |
| How long to keep working on an idea after a test falls short | **The agent judges, with reasons.** There is no fixed number of rounds. The reasons come from economics, market history and how markets have reacted historically, whether an angle is missing, and which tweaks remain. An idea is set aside only with those reasons and what would reopen it |
| How re-tests count | **Every re-test is a counted trial**, pre-registered and stored like any other |
| The holdouts | **Re-opens are allowed, any number, each look counted and labelled.** This supersedes "opened once" for research agents. After the first look the data is no longer clean, so paper trading on data that arrives afterwards is the clean check before real money |
| What decides entry to the paper account | **A scorecard with a recommendation, and the team lead decides.** Pass marks, including the deflated-Sharpe bar and the marginal route of 2026-10-27, are shown as guides. Real capital keeps its standalone gate |
| The 2026-10-27 audit's kills | **Re-review the practical blocks and the tests too weak to tell**, best first on market reasoning, skipping any already re-opened. The audit note gives counts only (26 and 20), so the loop finds them in the ledger |
| The graveyard | **Nothing is banned.** An idea can return if the agent says what is different. One that failed on a data error must deal with that error first |
| The loop's order | **Follow-ups first**, then the existing queues and new ideas |
| The analysts | **Not changed.** Their process, the guides and their end-of-November pitches stay as they are |
| The live book | **Not changed.** The order path, `DRY_RUN`, HALVE/KILL and the 60-session review stay as written |
| Not discussed, so still standing | No lookahead, no invented numbers, one harness, turnover-matched tables, and no picking the best of a swept column |

### Team lead, 2026-11-08 — the nightly check, single-name size, and the two gates

Answered interactively on 2026-11-08, after the evening check of 2026-11-05 ran three days late (`results/report/EVIDENCE_LOG.md` E-2026-11-08-03).

| question | decision |
|---|---|
| Who owns the nightly check | **A VM timer, with a push notification only when a stop fires** ("VM timer, push on stops"). The report-only data-QA and risk scripts of draft PR #46 run on the VM; everything but a fired stop stays in the journal. This narrows 2026-11-02's "journal only" for that one case, and brings forward PR #46's proposal to wait two weeks before a timer. Push needs a credential the team lead adds to the vault |
| C4's single-name size (the HQH short, about 20% of NAV) | **"Measure it, change nothing."** Per-name concentration joins the daily risk report and the equity-risk readout. No cap: one would be a new trial |
| The corporate-action gate | **"Start the fix."** Fix the bond-ISIN misread, bring the three unresolved rows to the team lead to re-rule, then return both books to `halt` through a release |
| HALVE/KILL's read at the 22:00 decide (UNMEASURED every session: `EVIDENCE_LOG` E-2026-11-03-41) | **"Fix the read, stay report-only."** The freshest-row rule ruled for te4's K0: the as-of's own EOD row if it exists, else D−1 labelled stale. Nothing acts on it. Turning HALVE/KILL on is a later ruling |

### Team lead, 2026-11-08 — the nightly check as built (PR #65)

| question | decision |
|---|---|
| Where does the nightly check live? (it lived only in an open session, ran three days late on 2026-11-05, and the 11-06 plans sent unread: E-2026-11-08-03) | **A VM timer**: `scripts/ops/data_qa.py` before the decide and `scripts/ops/risk_daily.py` after it, per book, report-only (`docs/RUNBOOK.md` 8.11) |
| What pushes? | **ACT only**: a pre-registered stop that has fired. Everything else stays in the journal. With no channel the report records `ACT: notification NOT delivered` and exits non-zero |
| Per-name concentration | **"Measure it, change nothing."** Largest name, top-3 and per-name share of NAV in the risk report; it never raises severity |
| The drawdown read at 22:15, when that day's EOD row is not written | **The freshest row**: the as-of's own row if it exists, else D−1, labelled stale. Until PR #55 merges (`drawdown.read_through`) the report reads `drawdown.check` as it stands and marks the line for follow-up |

### Team lead, 2026-11-05 — the band at the measured cost, and post-then-cross

Ruled on 2026-11-05 and relayed by the coordinating session, on `results/cef/BAND_COST_REDERIVATION_2026-11-05.md`
(PR #61, drafted as a pre-registration) and `results/cef/EXEC_COST_STUDY_2026-11-05.md` (PR #58, merged as 1f44bbf).

| question | decision |
|---|---|
| Re-derive the no-trade band from the measured execution cost? (that morning's ruling: "pre-register a re-derivation of the rebalancing band using the measured execution cost") | **"Accept: keep 4.8%, close."** Both books keep `band_width` 0.048. CLOSED at zero trials; CEF stays 55 (`docs/RESEARCH_STATE.md`, CLOSED, BAND-COST). The cube-root law at the measured paper cost gives the core 4.55% and C4 4.07%. Neither beats live beyond its own error: the core's 0.045 − 0.048 has NW t 1.34 against 2.837. Two follow-ups, both measurements: **C4's band is re-measured on its own fill cost after 21 sessions, no earlier than 2026-12-03**; and **the band is re-derived on a measured live auction impact before any real capital**, as part of the real-money cost re-run (2026-10-09) |
| Post-then-cross on paper? (the execution study's candidate 1: a passive limit at the touch at 15:52, the remainder crossed at 15:58) | **"Not now."** Not built. **Re-test after 60+ sessions of fills**: its −2.2bp against actual (95% CI −4.5 to +0.2) rests on 21 days [S: the study] |

### Team lead, 2026-11-05 — the analysts' roles reopened, and the end-of-November pitch

Answered interactively on 2026-11-05, while the analyst guide was being rewritten. It supersedes the 2026-11-03 rows below on what
the analysts work on and who does the signal work. `docs/TEAM.md` §1 holds who keeps which paths.

| question | decision |
|---|---|
| What the analysts work on | **Recommended starting points, and the work is open-ended.** `ryan` starts on FICC risk, `james` on equity risk, and `lucy` on cross-asset signals and the dashboard. These are not limits. Supersedes 2026-11-03's report-only risk lanes |
| Who may propose a signal | **Any analyst.** The team lead approves every test, and a trial still needs that approval before any return is computed (`docs/TEAM.md` §4). Supersedes 2026-11-03's "the team lead, on every counter". The PM still keeps every counter's rows |
| What each analyst delivers | **One pitch to the execs at the end of November:** an addition to the strategy, a signal, or anything else that helps overall. Each analyst pitches separately, as a short talk with slides. The date and length are still to be set |

### Team lead, 2026-11-03 — the analyst lanes redrawn as risk

*(Superseded 2026-11-05, above, on what the analysts work on and who does the signal work.)*

Answered interactively on 2026-11-03, after C4's arming was set. `docs/TEAM.md` §1 holds who keeps which paths.

| question | decision |
|---|---|
| What the analysts work on | **"Ryan work on the credit / fixed income risk, James equity risk, Lucy stays same and everything else to me, so the analysts dont have much work to do."** The fixed-income lane becomes **credit and fixed-income risk**, the equities lane becomes **equity risk**, and both are report-only: a weekly readout of the deployed book, with no signal, no trial and no live-path change. The dashboard-and-data lane is unchanged. This supersedes 2026-10-26's "the analysts bring new signals only" |
| Who does the signal work | **The team lead, on every counter.** MACRO (0) and XASSET (4) stay open, with their rows, and are kept by the PM. The E1-band WATCH row (non-industrialised fixed-income wrappers) is the PM's |
| What a risk finding feeds | **The PM's judgment.** A readout that suggests a hedge, an overlay or a signal goes to the PM, who decides whether it becomes a pre-registration. Nothing in a readout acts on the book (CLAUDE.md: any monitor is read-only) |

### Team lead, 2026-11-03 — C4 v5's gross cap (after the release-check of e41f10b)

| question | decision |
|---|---|
| The frozen margin rule (`_max_gross_stress_note`, ruling 3: "C4 arms only on the re-derived value") gives the v5 blend **1.80**, not 1.90 (blend w5 0.0536 against the z book's 0.0261; a 2020-03 week ≈ −10.2% of NLV held at 1.90, against −4.6% for the z book) | **"Keep 1.90, install tonight."** It is **an override of the rule's 1.80**, made with these figures in front of the team lead, and recorded with them. release-20261103-5 (e41f10b) was tagged unchanged and installed at 18:02 ET. Revert: a `/spec-change` to 1.80 with fidelity, H11 and the stops re-run |
| The arming gate read 1.90 because `recap` reads the z book's w5 | **To be fixed** (not ruled): `recap` must read the live spec book's w5 |

### Team lead, 2026-11-03 — the research loop becomes research-only

Answered interactively on 2026-11-03, before C4's arming, when C4 and the loop would have shared the spare account
(two runners on one account can double a book: `CLAUDE.md` rule 2).

| question | decision |
|---|---|
| May the autonomous research loop still trade? | **No: "have the loop only get us to what we should trade and deploy, and then we figure it out from there."** The 2026-10-27 exception in `CLAUDE.md` rule 1 is suspended: the loop transmits nothing, promotes no lab sleeve into the book and installs nothing. Its output is a recommendation; what trades or deploys is the team lead's call. C4 is the only runner on the spare account. Revert: delete the SUSPENDED paragraph in `CLAUDE.md` rule 1 and this row |
| Unchanged | The loop's trials are still counted and stored (2026-10-27). Its wrapper already denies `python3 -m quantt.session` and holds no key file (`.claude/loop/run_research_loop.sh`) |
| Install C4's v5 (the trial-54 blend) tonight, as a second release? | **"install tonight"**, through every gate of the standing authority (release-check GO, CI on the exact head, the replay, outside the send windows, the read-back), finished before 21:50 ET |
| The three analyst briefs | **"not yet"** |

### Team lead, 2026-11-03 — Gate 0 and CEF trial 54 (C4's family level)

Answered interactively on 2026-11-03, on `results/cef/PREREG_C4_LEVEL_2026-11-02.md` (its §0.A records it).

| question | decision |
|---|---|
| Gate 0: does survivorship explain C4's family-level discount effect? (**post-data**: ruled after the result was seen; the 2026-11-02 ruling made Gate 0 a judgment, not a mechanical gate) | **Cleared: "I approve, lets try and deploy as fast as possible".** Evidence: the prereg's §4b, commit 389f61a, reproduced byte for byte on 2026-11-03. Dead funds show the effect at least as strongly as survivors (b_D/b_A 1.36, 95% CI 0.80–2.13; negative in 30 of 33 half-years). NAV coverage 0.642 is under the 80% reference; the never-covered funds are the worst dying ones, and an adverse imputation still gives b_B/b_A 1.03. **Not a pre-registered pass**, and never to be described as one |
| Approve CEF trial 54? | **Approved. CEF 53 → 54**, with the draft's recommended answers to its open questions 2–9 (the C4 judging precedent: the fit at the bar, then the holdout's sign; risk split 0.50; the 1.90 cap kept; CRSP primary with yfinance second; borrow in its own column; sample B every five-family CEF) |
| Which accounts | **"use the 2 accounts I gave you, i dont hvae any other"**: the core account and the C4 (spare) account. No third account, for this trial or C4's arming |
| C4's first armed session (the spare account holds two old research-loop fills, so the runner's any-fill rule would open C4 at 28–42% of target) | **"just flat it"**: C4 opens from the flat account at full target. The research loop's fills do not count against C4's opening; any position does. Built as a C4-only book key (absent = today's rule, the core unchanged), released before C4 arms |
| What "as fast as possible" means | **No stage is skipped.** The trial's pass rule (§6.2) stands. The sleeve key is built in parallel with the fit stage, and each stage runs as soon as the last clears |
| CEF trial 54's K3 (D4), after the KILL was seen (**post-data**, later on 2026-11-03) | **"revive it and figure out a way to not kill it".** K3 (D4) failed as committed; overridden post-data by the team lead; the holdout decides. Not a pass of K3. P1 is lag-fragile (t 2.8271 at lag 6 as committed; 2.791 at lag 5). Evidence: `results/cef/prereg_c4_level/TRIAL54_RESULT_2026-11-03.md` |
| C4's first armed session: dry sessions (checklist step 5) | **"i want no dry sessions"**: C4 arms at its first install (2026-11-03). Its first armed decide is read before its first send, and C4 is disarmed before 15:45 ET if that plan is wrong |
| Where the pre-arming reads run (checklist steps 3 and 6), with C4's keys absent from the laptop | **"they are on the vm"**: the read-only probe and the cap re-check run on the VM, authenticated by the key file its C4 secret service wrote. No key is printed, copied or moved (`vmrelease.sh c4-probe`, git-excluded) |
| CEF trial 54's outcome (the holdout, opened once, 2026-11-03) | **PASS on the pre-registered remainder, with the holdout decisive** (`results/cef/prereg_c4_level/TRIAL54_RESULT_2026-11-03.md`): level-only gross SR 1.636; blend 14.56%/yr against z-only 10.32% [S]. Evidence INCONCLUSIVE at N = 54, K3 overridden as above. Per "deploy as fast as possible", `level_signal` is activated in C4's spec (v5) through `/spec-change` and a release-check, paper only |

### Team lead, 2026-11-03 — CEF trial 55 ("te4"): trade the eligible names on a thin session, paper only

Answered interactively on 2026-11-03, on `results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md` (its "Approval" section records the ruling, the answers to §10 Q1–Q17 and the runner owner's terms; the counter moved CEF 54 → 55 in `docs/RESEARCH_STATE.md`). The runner's part is `docs/RUNNER.md`, "As built (2026-11-03)".

| question | decision |
|---|---|
| On a session with 4–5 eligible names, build the core's book on them (`below_min_names = "trade_eligible"`, floor 4) instead of closing it? | **Approved for paper only, as CEF trial 55, with K0 and the recommended answer to every open question.** Before ruling, the team lead was shown that the rule is not shown to be alpha, that it is negative on real money, and that it is worth about zero going forward while no session is thin. The drafting session recommended keeping flatten |
| Where it may run | **`below_min_names = "trade_eligible"` is PAPER ONLY. It never applies to a live-money account,** as the `late_market` exception never does (2026-10-09). Delete the key, with its floor and its K1–K3 lines, before any live-money arming of the core. Enforced in code twice: the sleeve refuses to decide under the key without a paper declaration, and the runner declares paper only when its broker client's trading endpoint is the paper endpoint |
| A short skipped at the late-market send on a reduced session (the name stopped being shortable after the decide) | **Accept it and label it.** The send's skip-and-send stays as it is on reduced and full sessions alike. The record marks the reduced session that lost a short at send (`thin_stops.send_skip`), and K3 watches for a book that stays one-sided. Not chosen: refusing the whole send on such a session (the runner owner's preference) |
| When it trades | **Only from its activation commit**, which needs: the implementation merged; the core's 60-session review graded; the Q6/Q10 counts; the K0–K3 report lines and the pre-built revert spec in the activation release; and the trial-53 note. Until then the key is absent and the book is today's, byte for byte |

### Team lead, 2026-11-03 — the research evidence pack's live data

| question | decision |
|---|---|
| What of the paper accounts' live record may the public repository carry (PR #45, `results/report/`)? | **"Aggregates in repo, rows private."** Daily, account-level aggregates only: equity (the EOD record and the snapshot, labelled), P&L, attribution totals, fill-cost summaries in bp with counts, order counts, gate and verify outcomes (precedent: `results/cef/fill_drift_2026-11-02/`). Per-name quantities, per-name or per-fill prices, positions and order-level rows go to the gitignored `results/report/_cache_live/`; `scripts/report/snapshot_live.py` refuses to write a row file where git can see it. The branch's history was rewritten so the row files never appear in it. Backing up the cache to R2 is the team lead's step |

### Team lead, 2026-11-02 — autonomy

Answered interactively on 2026-11-02, after `release-20261102-1` went live.

| question | decision |
|---|---|
| Do the trades need the team lead's approval? | **No, and they never did.** The VM has been armed since 2026-10-08: every decided plan is sent on schedule |
| What may agents do without the team lead | **Everything, arming included:** merge, tag and install releases, and arm or disarm a book's runner, when every gate passes (CLAUDE.md rule 1, standing authority). Unchanged: `DRY_RUN=1` set by the team lead wins; credentials are never read or moved; approving a trial stays the team lead's |
| How the team lead hears about it | **The journal only** (`docs/JOURNAL.md`), with no notifications |
| How agents merge, since main's ruleset admits a merge only through the team lead's admin bypass | **Agents use `--admin`, only after CI has passed on the PR's exact head**, with `--match-head-commit`. The ruleset that keeps analysts off main is unchanged |
| C4's corporate-action gate (a flat C4 would have refused 17 of the last 23 sessions under `halt`; once holding, every session on the three unresolved rows) | **Report, the same as the core**, until the ISIN fix and the re-ruling of the unresolved rows land; then both go back to `halt` together |
| Which new signal goes to a pre-registration (screens 2026-11-02, zero trials) | **The C4 family-level discount signal only.** It takes the next CEF number at approval. Gate 0 (survivorship, re-run including dead funds) runs before any 2023+ return is read and needs the team lead's CRSP pull. Turn-of-month stays on WATCH until a test anchored on pay dates |
| The paper-fees correction to CLAUDE.md landmine 1 and `docs/REFERENCES.md` | **Not yet** (2026-11-02) |
| The Sharpe-framed NAV hedge (another session's screen) | **Closed at the power gate, UNDERPOWERED**, with zero trials. A report-only exposure readout replaces it (`docs/RESEARCH_STATE.md`, CLOSED) |

### Team lead, 2026-11-01 — the vol-target raise (CEF trial 53)

Answered interactively on the draft `results/cef/PREREG_VOLTARGET_2026-10-30.md` (written 2026-10-30;
§0.A records the approval). It also records the ruling of 2026-10-29/30 that it implements.

| question | decision |
|---|---|
| What the book optimises (2026-10-29/30) | **The percentage return on ALL capital, the real-money view.** The book is the core 13 in its own account plus C4 (74 non-credit CEFs) in the spare account. The ex-date short and PCEF stay built but OFF, because on the evidence they lower the percentage |
| How each account is sized | **At its per-account equal-risk multiplier, the milder pair: core ×1.13, C4 ×1.27, at a 5.25% combined target.** These come from the 2026-10-29 rule (its term (d): each account's mean uncapped gross within its own cap), derived 1.1357 / 1.2712 on C4's spec book and rounded down. **Chosen over** the draft's ×1.24 / ×1.39 at 5.75% (the 2026-10-28 rule, under which C4's mean uncapped gross, 2.01, is above its 1.90 cap). The 2026-10-29 rule, not the 2026-10-28 one, sets this book's target. **No override of term (d) is needed at these values.** CEF trial 53, N = 53 |
| How it is implemented | **A new optional frozen key, `sizing_multiplier`** (absent = today, byte for byte), in each cef_discount-type spec. `vol_target_annual` stays 0.06, so C4's fidelity gate and every reader of `spec.VOL_TARGET` are untouched. The core's value is its own activation commit, after the code: spec `cef_discount.v8.20261101`, which supersedes `cef_discount.v7.20260928`. C4's goes into its spec at its arming |
| The framework's gate on a vol increase (`results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md` §2.6: HALVE/KILL armed, the cost gate, 20 armed sessions, p\* stated) | **Waived for paper only,** with the raise's own stops (below) standing in for the unarmed HALVE. **Never for real money** |
| The raise's stops | **R1 (drawdown past D_R), R2 (the 120-session return below its 5th percentile), R3 (the 60-session vol above its 95th percentile)**, per account, on the P&L of record. Each is re-measured on the read date by `results/cef/prereg_voltarget/stops.py`. They are acted on by the team lead: the account's multiplier is reverted through `/spec-change`. No acting mode is built |
| When it starts | **The core at its next release; C4 at its arming,** already at ×1.27, with C4's H11 reference rebuilt on the raised book |
| The core's 2023+ "sealed" (2026-10-09's row above) | **Corrected:** for the core book it has been seen. 2024–26 was opened on 2026-07-31, and the v7 pre-registration computed 2013-06-14 → 2026-09-21. The 2026-10-09 rule still holds for any book whose 2023+ has not been computed. Dated notes are in `docs/RESEARCH_STATE.md` and the framework's §9 |
| Amendment 1 (team lead, **2026-11-02**, about 22:00 ET) | **Core ×1.30 (spec `cef_discount.v9.20261102`), C4 ×1.26 (`c4_families.v4.20261102`, before C4 arms), and the core's stops recalibrated on the live thin-day rule: R1 10.14%, R2 −3.06%, R3 12.07%.** The multipliers above were derived on the harness's thin-day HOLD book, but the live core FLATTENS. On the sessions it trades, the same rule gives ×1.30, which restores the risk this trial approved (zero-edge P(HALVE) / P(KILL) 16.7% / 1.7% while trading). The literal calendar-vol figure, ×1.96, is inflated by the flat sessions and was **not chosen**. It is **an amendment, not a new trial: CEF stays 53** (`results/cef/PREREG_VOLTARGET_2026-10-30.md` §0.B; `results/cef/prereg_voltarget/FLATTEN_REMEASURE_2026-11-02.md`) |

### Team lead, 2026-11-09 — the mission: open scope, paper as the test, the old research gates dropped

Given as a written brief, kept verbatim as `docs/MISSION.md`, and three questions answered interactively the same day
(the last three rows). **Where an earlier row in this section disagrees, this one wins**; the rows it supersedes are named
and are not rewritten. How it changes the agents' rules is `CLAUDE.md`, "Hard rules — research".

| question | decision |
|---|---|
| Scope | **Open.** CEFs and nearby markets, fixed income, equities, ETFs, futures, volatility, multi-asset; systematic, fundamental, mid-frequency, event-driven and tools that assist discretion. The CEF discount book is one sleeve, not the identity of the fund. Supersedes §1's framing of the book and 2026-10-09's "instruments in bounds" (options no longer need the pre-registered short-premium route) |
| What tests an idea | **Paper trading.** Research finds and shapes signals. An idea proves itself on paper (Alpaca, IBKR paper, or a simulated shadow book on live data) before capital |
| Costs in research | **Not modelled.** Ideas are judged on gross signal. No cost grid, borrow haircut or slippage assumption goes into a research result, and no idea is rejected on a guessed cost. Real costs are measured from paper fills and examined only in a go-live proposal. Supersedes 2026-09-28's "cost grid beside it" and the turnover-matched net comparison |
| The research gates | **Dropped: pre-registration, the trial counters and the deflated-Sharpe bar, the holdout ceremony, and "no sweeping and picking".** Supersedes 2026-09-08's two counters and time holdout, 2026-10-09's counter per source, 2026-10-27's bars and power gate, and 2026-11-08's "every re-test is a counted trial". The counter table in `docs/RESEARCH_STATE.md` is frozen at its 2026-11-09 values, as history. What stays is the hygiene in the next row |
| What stays | **No lookahead** (decision-time data only: NAV publication lags, filing dates and not period ends, index membership as of the day); **no invented numbers**, every figure labelled `[V]`, `[S]` or `[U]` with the panel's last date; **no silent fallbacks**; **an idea ledger**, `results/IDEA_LEDGER.md`, one line per idea tested, a record and not a gate; and **one time split** before paper: early against late, and at least two market regimes |
| Who promotes an idea to paper | **The agent, without asking**, through a paper and shadow path that is separate from the prod release path. The team lead approves that path's design once; until that approval no agent starts a new paper book. Supersedes 2026-11-08's "the team lead decides on a scorecard" for paper. **Real money always needs the team's explicit approval** |
| The core and C4 books | **May be changed**: reworked, retired, or folded into a combined portfolio, on paper first. A change to what prod runs still reaches the VM as a release (below) |
| Data | **Free and public only.** No paid subscription. The repository's panels, the R2 WRDS mirror for research, and free public sources |
| Go-live bars | **Set per strategy.** Each go-live proposal states its own bar, reasoned from how often the strategy trades and how many bets it takes, and the team signs off. Supersedes the single standalone deflated-Sharpe gate for real capital (2026-10-27) |
| The portfolio | **Toward one combined alpha model**: each sleeve gives a forecast, the forecasts are combined with shrinkage toward equal risk, and the whole book is sized to a risk target that the paper record supports. More risk is acceptable where the evidence supports it |
| Who installs a prod release (asked 2026-11-09) | **The team lead only.** The 2026-11-02 standing authority ("agents merge, tag, install and arm when every gate passes") is **withdrawn**. Agents prepare a release and run the release check; the team lead merges, tags, installs and arms |
| Alpha only (asked 2026-11-09) | **Dropped.** Risk premia (carry, trend, short volatility) may be sized sleeves. Factor exposures are reported beside every result and managed at book level; exposure no longer ends an idea. Supersedes 2026-10-09's "deliberate beta: no" and the D4 gate as a kill |
| `CLAUDE.md`'s research rules (asked 2026-11-09) | **Rewritten to the brief's §2.** The `/prereg` skill and the counters are retired for research; `docs/RESEARCH_STATE.md` stays as history |
| Not changed | The order-path rules (`CLAUDE.md`): no order on a real-money account without the team lead's go on the full list, `DRY_RUN=1` wins, credentials are never read. The live books' own stops and gates as they run today. `/spec-change` for any frozen-spec key. The analysts' lanes and process (`docs/TEAM.md`): **confirmed by the team lead the same day ("Keep TEAM.md process")**. The analysts still bring each test to the team lead and pitch at the end of November; only the team lead's sessions use the mission's rules |
| The paper/shadow runner's first form (asked 2026-11-09) | **Shadow books first**: simulated books on live data, with no account and no keys. Paper accounts are added for the ideas that look best. This sets the direction of the design; the design itself still needs the one-time approval above |
| The shadow-book runner's design (asked 2026-11-09) | **Approved, as the one-time approval**: `results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md`, built as the package `shadow/`. From this ruling an agent may add, change and retire **shadow** books without asking. A shadow book is simulated: it has no account and can send no order. Starting a book on a **paper account** is not covered by this approval and is a later one; real money is the team's decision, as always |
| Where the shadow runner runs (asked 2026-11-09) | **On the VM, as a separate unix user with its own clone**, which follows a branch named `shadow` so that a new book needs no release. The team lead installs it once. That user must not be able to read prod's key files or state |
| The prices that mark a shadow book (asked 2026-11-09) | **Alpaca's closing-auction prints, with yfinance closes as the cross-check.** The Alpaca key the shadow user holds should belong to an otherwise empty paper account, which the team lead creates and keys *(superseded later the same day, next row)* |
| Which key the shadow runner reads data with (asked 2026-11-09, later) | **The core (`cef`) account's key: "use the accounts we already have access to".** No new account. On the VM the shadow user stays separate and gets **its own key file holding a copy of that one key**, and still cannot read prod's state or the other account's key. That key can trade the core's paper account, so the read-only wrapper (`shadow/sources.py`) and the test that fails if `shadow/` names an order method are what stand between shadow code and an order. The research data is the R2 mirror (`src/data/r2.py`) |
| The size a shadow book is simulated at (asked 2026-11-09) | **$1M per book.** Capacity is shown at $1M, $5M and $10M |
| Refreshing research data (asked 2026-11-09) | **The agent runs the free-source fetchers** from the laptop into a research data folder, never into the live `data/` panels (`CLAUDE.md` landmine 9). The team lead runs only the R2 pulls that need the token |

### Team lead, 2026-11-11 — event-driven and special situations are part of the mission

| question | ruling |
|---|---|
| What the desk is | **An event-driven and special-situations desk as well as a systematic one, in any asset class.** Every idea hunt also looks for niche verticals along those lines. The seed list is `docs/MISSION.md` §5 (the block dated 2026-11-11). Nothing else in the 2026-11-09 ruling changes: shadow books first, no paper account for a new sleeve without the team lead, releases by the team lead only |

### Team lead, 2026-11-16 and 2026-11-18 — the event sleeves' account, how sleeves are sized, and how a book is promoted

Answered through question prompts. The 2026-11-16 rows were in `ops/sleeves/events_sleeves.json` and
`results/report/EVIDENCE_LOG.md` (E-2026-11-16-02, -03) only; they are recorded here on 2026-11-18. The 2026-11-18 rows
followed a measured comparison of sizing schemes (`EVIDENCE_LOG` E-2026-11-18-04).

| question | ruling |
|---|---|
| Where promoted event sleeves trade (2026-11-16) | **One new Alpaca paper account, $1,000,000, named `events`**, gross up to 1.5x equity. Seven shadow books are its first sleeves. The small-name special-dividend book is capped at $25,000 by what its names can absorb |
| How the sleeves in that account are sized (2026-11-18) | **Equal risk per family, not $100,000 a book.** Variants of one idea are one family and split its share. Supersedes 2026-11-16's "$100,000 each". At $100,000 a book the two units ex-date books carried 68% of the account's backtest risk [V, gross, 2000-06-01 to 2025-12-23]. Each sleeve's full size is a key in the book file (`full_capital_usd`, with its `family`), and the derivation is in its `_note_sleeves` |
| A combined risk budget across all accounts (2026-11-18) | **Not yet.** Each account keeps its own limits. Asked as "8% combined vol with HALVE at 12% and KILL at 18%"; to be asked again after the events account has traded |
| What promotes a shadow book to a paper sleeve (2026-11-18) | **Ten clean on-time shadow sessions**: no UNMEASURED and no LATE day. It tests the feed and the plumbing, not the return: no statistic exists that early |
| How a new sleeve scales (2026-11-18) | **A ladder, counted in sessions on which the sleeve held a position.** Under 20: a quarter of its full size. 20 to 59: half, if fills track the shadow book. From 60: full if live P&L is above -1 sigma x sqrt(T), half between -1 and -2 sigma, stopped below -2 sigma. Sixty sessions cannot confirm a Sharpe; the ladder only catches failures. Supersedes 2026-10-29's "a full equal-risk share from day one" for sleeves in the events account |
| What a clean session is (2026-11-18, second prompt) | **"Any on-time day, ten in a row."** A session is clean when it was measured and the decision that fills on it was written on time; a flat day with an on-time decision counts. The latest ten must all be clean. Counted by `quantt/sleeves/promote.py` (read-only) |
| What "fills track the shadow book" means (2026-11-18, second prompt) | **"Paper within 2x modelled gap."** Pass if the sleeve's paper P&L is behind the shadow book's on the same sessions by no more than twice the fill cost the model assumes on the dollars traded. The cost is an optional per-sleeve key, `modelled_fill_cost_bp`, which the team lead sets; it is absent for every sleeve, so the test reads UNMEASURED |
| The sigma of the 60-session test (2026-11-18, second prompt) | **"Each sleeve's backtest vol"**, scaled to the capital the sleeve traded at. In the book file as `backtest_vol_annual` (gross backtest, 2000-06-01 to 2025-12-23, the allocation run of E-2026-11-18-04). The events runner does not yet record the capital a sleeve traded at each session, so this test and the one above read UNMEASURED until `sleeve_scores.csv` carries it (`quantt/sleeves/deploy/README.md`, open items) |
| Recording the capital a sleeve traded at (2026-11-19) | **"Yes, add it now."** The events runner writes the capital PLAN sized each sleeve from into `plan.json` and the `capital_usd` column of `sleeve_scores.csv`. Both ladder tests read it; it changes nothing about what is planned or sent |
| The modelled fill cost per side (2026-11-19) | **"Card figures where measured, 15bp elsewhere."** `specdiv_wait_small` 13.5bp and `specdiv_wait` 7bp (measured closing half-spreads on their card); 15bp, an assumption, for the two CEF ex-date books, the two units books and `pead_small_long`, until paper fills replace it. In the book file as `modelled_fill_cost_bp` |
| Trades netted inside the account (2026-11-19) | **"No, only real fills."** A cross between two sleeves pays no spread and earns no fill-cost allowance; only market fills count as dollars traded |
| What is built first (2026-11-18) | **The runner's PR to main, then a read-only combined daily report** across the accounts (P&L and risk share by family, factor exposure, trailing correlations once 20 sessions exist) |
| Not asked, and open | A demotion rule on drawdown (the ladder's -2 sigma stop is the only one); whether the two shadow books outside the seven (`month_end_ief`, `spinoff_first_week`) become sleeves; a replacement second NAV source for the core (E-2026-11-18-03) |

### Team lead, 2026-11-19 — deploy the event sleeves now; the core's cap and the risk target are measured before anything changes

Answered through question prompts on 2026-11-19 (`EVIDENCE_LOG` E-2026-11-19-04). The reader work those prompts
followed is E-2026-11-18-25 to -28.

| question | ruling |
|---|---|
| The ten-clean-session rule for the seven event sleeves (2026-11-18) | **Waived: "waive it, i think deploying is better and we can adjust as eneded".** All seven are armed at their quarter size as soon as the account exists and the release is installed, whatever their session count (at the 2026-11-18 close: 6 and 6 for the two CEF ex-date books, 5 and 5 for the units books, 1 each for the other three [V, `ops.prod_state`]). The ladder itself was not asked about and stands. The rule stays for any book promoted later; `quantt/sleeves/promote.py` still counts it and now reports a waiver nobody coded: read its ten-session line for these seven as information |
| Where the event sleeves trade, asked again | **"Try a third paper account"**: the 2026-11-16 ruling stands. The team lead opens it in the dashboard and puts its keys in the vault. Asked because the team lead proposed folding C4 into the core's runner to free C4's account; the combiner refuses a sleeve that sets `sizing_multiplier` (both specs do) or `level_signal` (C4's does), and one $100,000 account cannot carry both books at their sizes (1.80x and about 1.23x gross) |
| The core's gross cap, which scales the book every day since the x1.30 sizing (x0.8207 on the 2026-11-19 plan) and so turns every band hold into a trade | **"Backtest the options first"**: today's order, the band applied after the cap, a higher cap, and smaller multipliers, on the canonical harness. Nothing live changes until the team lead has seen it |
| Raising an account's risk target "if it gives more return" | **"Measure first, then decide"**, in the same run |
| Who carries the open pull requests (#87 the reader, #88 the installer and QA fixes, #89 the events runner) | **One session, this one.** They are one integration branch, `events-runner-main` |
| The investor view of the paper books (2026-11-18) | **The net modelled view is the headline**: closing-auction fills, plus the distributions paper never paid, less a fetched borrow cost; the official record and the gross modelled figure beside it, each labelled |
| Not asked, and open | Whether the ladder's later stages change with the waiver; the cap and target the measurement will point to; whether Alpaca allows a third paper account at all (`docs/REFERENCES.md` 12pa: not stated) |

## 6. Governance — where each rule lives

| subject | owner |
|---|---|
| Hard rules: order path, code, data, research | `CLAUDE.md` |
| Ideas tested, and what each showed | `results/IDEA_LEDGER.md` (a record, not a gate; from 2026-11-09). `docs/RESEARCH_STATE.md` is the history before it: its counters are frozen |
| Harness rules H1–H15 (`shift(2)`, turnover matching, cost grid, eras, IC, holdouts, H14) | `docs/BRIEF.md` §5, and `/harness` |
| The mission and the pipeline (idea, explore, paper, go-live proposal, live) | `docs/MISSION.md`; §5, 2026-11-09. Pre-registration is retired for research |
| Changing a frozen spec key | `/spec-change` |
| Ideas that have failed so far — check before proposing anything; nothing is banned (2026-11-08) | `/graveyard`, and the KILLED table |
| External claims | `docs/REFERENCES.md` |
| Work orders and the plan | `docs/ROADMAP.md`. The old work orders were deleted 2026-09-28 (tag `pre-clean-slate`). |
| Which document owns which question | `docs/INDEX.md`, checked by `python3 -m ops.doc_audit` |
| Who keeps which lane; how work reaches `main` and prod; the shared-ledger rules | `docs/TEAM.md` |

---

## 7. Changes

| date | change | by |
|---|---|---|
| 2026-09-13 | Written, replacing six overlapping descriptions of the system. §5 moved verbatim; no decision re-made. | documentation cleanup, for the team lead |
| 2026-09-28 | §0, §4 rewritten for the IBKR retirement and the move to Alpaca; §5 gains the 2026-09-28 decisions; §2 and §6 repointed. Earlier text at tag `pre-clean-slate`. | Alpaca migration, for the team lead |
| 2026-09-28 | Clean slate: archive references replaced by the tag; plan moved to `docs/ROADMAP.md`. | clean slate, for the team lead |
| 2026-10-07 | §5 gains the cloud-VM decision. | cloud VM, for the team lead |
| 2026-10-08 | §5 records the cut-over to the VM and full automation. | cloud VM, for the team lead |
| 2026-10-11 | §5 records the 2026-10-09 missed-day fix and the 2026-10-11 stress-cap ruling. | release work, for the team lead |
| 2026-10-12 | §2's IC row corrected to the wide set, the deployed IC added under conditional (W4); §5 records the 2026-10-12 rulings. | for the team lead |
| 2026-10-14 | §5 records the release-20261014-1 install, the C5, C4 and XASSET (N = 4) approvals, and the ruling to leave git history alone. | for the team lead |
| 2026-10-13 | §5 records the stale-NAV ruling ("Use CEFConnect, else drop") and, the same day, its redesign: defer and hold instead of drop; report mode first. | for the team lead |
| 2026-10-19 | §5 records the rulings on the interrupted work: C4's verdict, C5's repair rule, HALVE/KILL in report mode, CEFConnect, IBKR, and the EVENTS slate. | for the team lead |
| 2026-10-19 | §5 records the HALVE/KILL report-mode ruling and the official equity series it reads. | for the team lead |
| 2026-10-19 | §5 records the P&L-of-record ruling: Alpaca's end-of-day history is official; the 17:30 reading is a snapshot. | hotfix, for the team lead |
| 2026-10-20 | §5 records IBKR waiting for a trigger, SPACs closed (D4), the three event-path closes, the trials' Stage-0 rulings and C4's split ruling. | for the team lead |
| 2026-10-22 | §5 records the pod: the lanes, review and merge, GitHub access and analysts' data access; §6 points at `docs/TEAM.md`. | team setup, for the team lead |
| 2026-10-22 | §5 records the lanes revised: MACRO (a new counter), equities and ETFs on XASSET, the dashboard; EVENTS and GAMMA work to the team lead; branches renamed. | team setup, for the team lead |
| 2026-10-26 | §5 records what the lanes feed (one multi-sleeve book), no hand-offs, MACRO widened to all of fixed income, the data platform to the dashboard lane, the dashboard's snapshot in the repository, and the branches renamed for the people. | team setup, for the team lead |
| 2026-10-28 | §5's research-method table records the team lead's 2026-10-28 ruling to keep the paper-admission rule as written, and that the later paper-view finding is not ruled on. | re-open (1), for the team lead |
| 2026-10-28 | §5's research-method table records the team lead's ruling that a counter with one stored trial gates on the desk's bar until a second is stored. | research loop, for the team lead |
| 2026-11-01 | §5 records the vol-target raise (CEF trial 53: ×1.13 / ×1.27, `sizing_multiplier`), the framework gate waived for paper, the raise's stops, and the correction that the core's 2023+ has been seen. | CEF trial 53, for the team lead |
| 2026-11-02 | §5's trial-53 table records amendment 1: core ×1.30 (spec v9), C4 ×1.26 (spec v4), the core's stops recalibrated on the live thin-day rule; CEF stays 53. | CEF trial 53 amendment 1, for the team lead |
| 2026-11-03 | §5 records the evidence pack's live-data ruling: aggregates in the repository, rows in a gitignored cache. | research evidence pack, for the team lead |
| 2026-11-05 | §5 records the analysts' roles reopened as starting points, any analyst may propose a signal, and the end-of-November pitch. | analyst guide, for the team lead |
| 2026-11-08 | §5 records that research is not pass or fail; §1's holdout sentence and the 2026-10-27 power and admission rows point at it. | research method, for the team lead |
| 2026-11-09 | §5 records the mission (`docs/MISSION.md`): open scope, paper as the test, no costs in research, the research gates dropped, self-promotion to paper through a separate path, releases by the team lead only, alpha-only dropped. §1 and §6 point at it. | the mission, for the team lead |
