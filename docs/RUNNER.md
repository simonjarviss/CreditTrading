# The Alpaca runner — build contract

**Status: being built (2026-09-28, branch `alpaca-runner`).** This is the design every
piece of `quantt/` is written against. It covers `docs/ROADMAP.md` phase 4 plus the
deploy decisions the team lead took on 2026-09-28 (below). It holds no figures about
the book: those come from `python3 -m ops.orient`.

## Decisions it rests on (team lead, 2026-09-28)

| question | decision |
|---|---|
| Go-live | **Armed on Tue 2026-09-29.** The first armed session's concrete order list is shown to the team lead, who says go. |
| Where prod runs | **This laptop for now** (no VM). A separate clone at a release tag, scheduled by launchd. A VM later. |
| After the first go | **The scheduled runner trades daily on its own**, behind every gate below. `CLAUDE.md` order-path rule 1 governs agents in a chat, not the scheduled runner. Stop it with the halt file or `DRY_RUN=1`. |
| Day one (flat book) | **Trade to full target**, not to the band edge, so the book starts dollar-neutral. The band applies from the second session. |
| Phase 3 probes | **Design around them.** Never reuse a `client_order_id`, one netted order per symbol per session, a long↔short flip is two orders (close, then open), and never assume the uncertain answer. Day one's real orders answer 3.1 and 3.5. |
| Scoring | Alpaca's fill (official) **and** the official closing-auction print, side by side, gross. **Which Alpaca number is official, from 2026-10-19** (team lead): Alpaca's **end-of-day portfolio history** (`GET /v2/account/portfolio/history`, `timeframe=1D`), EOD(D) − EOD(previous session). The 17:30 ET `equity − last_equity` reading is a labelled **snapshot**, kept and never blended ("As built (2026-10-19)" below). **Third line from 2026-10-09** (team lead): auction-marked P&L **plus distributions** on shares held at the start of each ex-date (credited long, charged short), because Alpaca paper credits none. It is scored two sessions late, once the cross-check source has caught up, and written to `distribution_scores.csv`. It never changes the verdict (`quantt/session/dist_score.py`). |

## The session, in order

Decide on the **as-of day's complete price+NAV pair**, MOC for the **next trading
day's** close. This matches the research's `shift(2)`: decide on *t*'s data, fill
at *t+1*'s close, earn *t+2*. **When** (team lead 2026-09-29): in the **evening**
of *t*, 22:00–01:00 ET, once *t*'s NAVs are in (they landed 21:21–21:51 ET on
2026-09-28), with a **morning backstop** 06:00–15:15 ET on *t+1*. The evening and
morning runs decide on the same pair and make the same plan; an order sent after
19:00 ET is queued by Alpaca for the next day's auction [V: docs; first paper
evening send confirms it]. See "As built (2026-09-29)" below.

```
every 30 min  python3 -m quantt.session run --book cef --scheduled
              (idles outside the evening/morning slots and once the session is done)
          1. refresh    scripts/cef/fetch_daily.py --require-asof <prev trading day>
                        --nav-fallback cefconnect --book ops/books/cef_discount_book.json
                        exit != 0  -> NO TRADE today, logged (stale data never trades)
          1b. NAV gate  only when the book json sets data.stale_nav (absent: off; report:
                        record only). A NAV(D) equal to the previous NAV or to CEFConnect's
                        NAV(D-1) is checked against CEFConnect's D: stale copy -> replaced,
                        genuine repeat -> kept, unverified -> the decide is deferred to the
                        morning; from the final check the name keeps its shares.
                        "As built (2026-10-13)" below. With data.missing_nav = hold
                        (dark), a name whose NAV is not dated the as-of date is held
                        the same way from the final check. "As built (2026-10-29)".
          2. read       Alpaca account (equity), positions, closed orders, assets
          2b. drawdown  only when the book json sets risk.drawdown (absent: off; report
                        is the only mode built: record only). The drawdown from the
                        high-water mark of <state>/eod_equity.csv against the frozen
                        spec's risk.halve_drawdown / risk.kill_drawdown, recorded in
                        plan.json and the log. "As built (2026-10-19)" below. Under
                        CEF trial 55's key (dark) K0 makes its own reading of the same
                        check through the session before the as-of (the team lead's
                        ruling of 2026-11-03): only OK lets a reduced book be built.
                        "As built (2026-11-03)".
          3. decide     sleeve.target_positions(asof=<prev trading day>, MarketState(
                          holdings=<Alpaca positions>, extras={"sleeve_nav": <equity>,
                          "opening_session": <bool>}))
                        -> whole-share orders, one netted order per symbol,
                           a flip split into two orders
          3b. corp. actions  only when the book json sets corporate_actions.mode
                        (absent: off; report: record and send; halt: refuse). Every
                        non-dividend corporate action naming a held or targeted name
                        inside that name's window; again at the late-market send.
                        "As built (2026-10-28)" below.
          4. gate       gate 6's order lists, then the clock, are the last broker reads;
                        every check below; any failure -> nothing sent, logged
          5. record     <state>/<date>/STARTED written BEFORE the first order
          6. transmit   POST /v2/orders, type=market, time_in_force=cls, whole-share qty,
                        client_order_id = cef-<YYYYMMDD>-<SYMBOL>-<leg>
          7. confirm    re-read orders; every sent id must be at Alpaca, else FAIL
17:30 ET  python3 -m quantt.session verify --book cef   # post-close
          reconcile fills from the broker, fetch the official auction prints, score
          (official EOD figure or PENDING, snapshot, auction-marked), append ONE line
          to <state>/verify.log: PASS or FAIL + reason
```

## Module boundaries (one owner each)

| module | owns | never |
|---|---|---|
| `quantt/broker/alpaca.py` | The REST client: account, positions, orders (list/submit), clock, calendar, assets, account activities, end-of-day portfolio history, stock auctions and corporate actions (data API). Retries only idempotent GETs. | Decides anything. Holds a default for a missing field. |
| `quantt/session/decide.py` | Pure function: sleeve targets + holdings + equity + last closes → order list. Whole shares, netting, flip split, shortability. | Touches the network. |
| `quantt/session/gate.py` | Pure checks → a list of refusals. | Transmits. |
| `quantt/session/run.py` (+ `__main__.py`) | Orchestration of the session above; the only caller of `submit_order`. | Transmits when any gate refuses. |
| `quantt/session/nav_gate.py` | The stale-NAV gate (step 1b): finds each NAV(D) equal to the previous NAV or to CEFConnect's NAV(D-1), reads CEFConnect, replaces stale copies in the NAV panel through the logged fallback, defers or holds the unverified, records every check. | Transmits. Decides a target. |
| `quantt/session/drawdown.py` | The drawdown check (step 2b): reads `<state>/eod_equity.csv` by header, the frozen spec's two drawdown lines (units-checked), and records the status and what an acting mode would do. Also CEF trial 55's K0-K3 report lines (`thin_stop_record`). Under that trial's key run.py's K0 makes its own reading of the check, through the session before the as-of (`read_through`; the team lead's ruling of 2026-11-03), and it only restricts. | Transmits. Changes an order. Falls back to `equity.csv`. |
| `quantt/session/combine.py` | The multi-sleeve combiner (2026-10-28, **dark**): reads the book json's `sleeves[]`; for a book whose enabled sleeves all carry `risk_budget`, builds each from its own spec on its own sleeve_nav, nets the whole-share targets per symbol into one `decide`, and records the per-sleeve attribution. Absent a budget, `None`: the single-spec session, byte-identical to de6e9c5 (proved by test). | Transmits. Splits a held position between sleeves. |
| `quantt/session/corp_actions.py` | The corporate-action gate (step 3b): dates each held name's shares from the account's closed orders, draws each name's window, keeps the actions that block, and writes the record and the refusal's sentence. Pure apart from the read it is handed. | Transmits. Changes an order. Reads an absent or failed feed as clear. |
| `quantt/session/verify.py` | Post-close reconcile + dual scoring + the one-line verdict. Read-only against the broker. | Transmits. |
| `src/deploy/sleeves/cef_discount.py` | The strategy. Gains `extras["opening_session"]`: when True the band is skipped (trade to full target); **absent or False is byte-identical to today** (proved by test). Gains `extras["nav_hold"]` (2026-10-13): names the stale-NAV gate could not verify by its final check keep their current shares and leave the cross-section; holds never trigger the `min_names` flatten; absent is byte-identical. | — |
| `quantt/deploy/` | launchd plist templates + an install script for the laptop prod clone + `docs/RUNBOOK.md`. | Stores a credential. |
| `src/data/r2.py` + `scripts/data/` | Research/backtest access to the R2 WRDS mirror. **Never on the live path.** | Is imported by `quantt/`. |

## The gates (all must pass to transmit; each refusal names itself)

1. `DRY_RUN` — transmits only if the environment variable is **exactly `"0"`**. Unset, empty, `1`, anything else → dry. Always wins.
2. **Arming** — transmit additionally needs **either** `--approve <plan_sha>` equal to the sha256 of the freshly recomputed order list (the interactive first session: what was approved is what is sent) **or** the file `<state>/AUTO_ARMED` (created after the team lead's first go).
3. **Halt** — `ops/halt.read_halt(book)` returns a halt → refuse.
4. **Clock** — the session date is a trading day by both calendars and Alpaca's `/v2/clock` is inside the auction's send window: the as-of evening from **19:15 ET** (Alpaca queues `cls` sent after 19:00 into the next auction) to 01:00 ET, or the session day until **15:45 ET** (Alpaca rejects `cls` from 15:50; five minutes of margin). Early-close days: use `/v2/calendar`'s close, minus 10 minutes, cls cutoff per Alpaca docs.
5. **Data** — the refresh exited 0 for the required as-of date. That checks each NAV's *date*, not its value; the stale-NAV gate (step 1b, "As built (2026-10-13)") checks the value when the book turns it on.
   - **Corporate actions** (step 3b, when the book json sets `corporate_actions.mode`; team lead 2026-10-28). Under `halt`, refuse when Alpaca lists a non-dividend corporate action (split, stock dividend, spin-off, merger, redemption, name change, worthless removal, reorganization, partial call) naming a held or targeted name, in any role, inside the window that role and match call for: the long window for an acquiree, a split, a name change and the rest, and the short window `(as-of, session]`, one session, for a merger acquirer and a reorganization's allocated leg (both on the market date only) and for any other match through the process date alone (team lead and re-review, 2026-10-29). Also refuse when that list cannot be read. The refusal is a gate-5 `data` refusal naming each event or the error. It runs at decide and again at the late-market send. Under `report` the same is recorded and the session sends. "As built (2026-10-28)" below.
6. **No set already headed for this auction** — refuse if `<state>/<date>/STARTED` exists, or Alpaca shows any order today whose `client_order_id` starts with `cef-<YYYYMMDD>-`, or any open order in the account, of any type or time in force (`gate.gate_no_set_in_auction`; *corrected 2026-11-02: this line said any open `cls` order, which the code has never been*). The two Alpaca lists are read after every other broker read, just before the gate's clock read, on both paths that transmit; a failed read refuses ("As built (2026-10-29): gate 6 reads its lists last").
7. **Shortability** — an order that opens or increases a short needs `/v2/assets/<sym>` `shortable: true` today; else that symbol sends nothing and is logged (prereg v7 §6). Never substitute a name. Under CEF trial 55's key (dark), a reduced decision that loses a short here is re-decided flat ("As built (2026-11-03)").
8. **Exposure** — projected gross ≤ spec `risk.max_gross_exposure_usd`; ≤ `max_gross_stress` × the **lower** of the equity the plan was sized on and live equity, unless the plan does not add to the gross held now (2026-10-09; the lower of the two from 2026-10-11); and, on the live account, opening notional ≤ Alpaca `buying_power` and the overnight Reg T / maintenance limits on the book after the plan (2026-10-07). *Corrected 2026-10-09: this line read "≤ `max_gross_stress` × equity, and projected initial margin ≤ Alpaca buying power", the rule that refused 2026-10-09 ("As built (2026-10-09)" below).*
9. **Sanity** — every qty a positive integer, every symbol in the frozen universe, no symbol with two opposite-side orders.

## Rules the code must obey

- No silent fallbacks: a missing field, price or env var raises, naming it (`CLAUDE.md`).
- `QUANTT_STATE_DIR` (runtime records) and `QUANTT_ENV_FILE` (Alpaca keys) are **required** environment variables for `quantt.session`; unset → raise. Keys are read with `dotenv_values` and never printed, logged or written.
- Paper endpoint only: `https://paper-api.alpaca.markets`. A live endpoint anywhere is a test failure.
- Tests never touch the network (`ops/netguard.py` blocks it); the HTTP layer is mocked.
- Every live-path change ships with a test shown to fail against the wrong behaviour.

## As built (2026-09-28, after review)

The build, two independent reviews (quant, execution) and the fixes changed or
settled these points. Alpaca facts, each with its source and status:
`results/ops/ALPACA_API_FACTS_2026-09-28.md`.

- **Flips are deferred.** Alpaca reserves the shares of a pending sell and says to
  close a long fully before opening a short [V, Alpaca Learn]; staff say two orders
  like that are not supported [S]. So a long↔short flip sends only the closing leg
  today and logs `flip deferred`; the band opens the new side next session.
- **`cls` availability is [U].** Alpaca Learn says CLS orders are for Elite Smart
  Router users. The first real `cls` order answers it. The runner never falls back
  to `day`; if every order is rejected nothing was sent and the team lead decides.
- **A rejected order skips its symbol and the rest are sent** (team lead,
  2026-09-28); the day is FAIL naming it. Anything with an unknown outcome
  (ambiguous submit, unexpected error, clock) still stops the batch.
- **Gate 7** checks `shortable` only; hard-to-borrow is a preview warning (team
  lead, 2026-09-28).
- **Gate 4** re-reads the Alpaca clock at the gate and again before every POST; the
  refresh subprocess's timeout is the time left to the cutoff.
- **Gate 5** requires an as-of **NAV** as well as an as-of close for every name.
- **Gate 6** refuses on **any** open order in the account, not only `cls`.
- **Gate 8** checks buying power against `min(buying_power, regt_buying_power)`: the
  book holds overnight, where Reg T binds, not the 4× intraday figure.
  *Superseded 2026-10-07 ("As built (2026-10-07)"): it refused a plan Alpaca would
  have accepted. Gate 8 is now an order-time and an overnight check.*
- **Send order** is `transmit_sequence` (decide.py), not alphabetical.
- **Scoring** uses only the primary listing exchange's official-close print
  (condition `M`, exchange `N` for NYSE); a missing print leaves that name
  UNMEASURED and the day FAIL. It is never substituted. *(The Alpaca figure called
  official here until 2026-10-19 is now the snapshot; see "As built (2026-10-19)".)*
- **Records:** `<state>/<D>/plan.json`, `orders.jsonl` (event log), `STARTED`,
  `reconcile.json`; `<state>/verify.log` (one line per day) and `scores.csv`.
- **Distribution-adjusted score** (third line, 2026-10-09; redesigned the same day after
  review). After the verdict, as with the shadow score, `quantt/session/dist_score.py`
  scores every session **at least two sessions old** that has no measured row yet. It
  reads that day's `reconcile.json` (`held_into_close`) and its `scores.csv` row, and
  upserts one row per session into `<state>/distribution_scores.csv`.
  - **Primary source:** Alpaca corporate actions.
  - **Cross-check:** the yfinance panel, within 0.0005 per share of rounding.
  - **When it is UNMEASURED:** a real conflict, or an ex-date only the panel lists.
  - **A zero needs both sources silent,** with the panel file rewritten after the
    close of the session following D. Otherwise the day is UNMEASURED and retried.
    A measured row is final.
  - **Never the verdict, never the exit code:** each post-verdict hook (shadow,
    distributions) is guarded separately in `main()`, and an error goes to stderr.
    `scores.csv`'s columns are unchanged.

## Paper execution (2026-09-29): decide in the evening, send as market orders at 15:52

Team lead, 2026-09-29, after the first armed session: paper filled 2 of 13 `cls`
orders (PHK 4,019/4,019, PFN 1,529/2,227; eleven expired), and Alpaca staff confirm
paper treats `cls` as a market order at the close with random partial fills. Rule 3
gets one recorded exception, **paper only**: `ops/books/cef_discount_book.json`
`execution = {mode: late_market, window_minutes_before_close: [8, 2]}`.

- **DECIDE** (evening 22:00–01:00 ET, morning backstop 06:00–15:15): refresh, read,
  decide, and every gate except dry-run, arming and clock. The plan is saved as
  `status: decided` with its `plan_sha`; nothing is sent (exit 6 PLANNED; `DECIDED`
  marker for scheduled runs).
- **APPROVE** (until `AUTO_ARMED`): `python3 -m quantt.session approve --book cef
  --date D --sha <plan_sha>` writes `<D>/APPROVED`, only for the decided plan with
  that sha, only before STARTED. Run on the team lead's explicit go (rule 1).
- **SEND** (15:52–15:58 ET, from the calendar close; 12:52–12:58 on a 13:00 close;
  launchd fires 15:52 and 15:55): the SAVED plan is loaded -- never re-decided,
  because intraday equity moves the sizing and what was approved must be what goes
  -- its orders must still hash to its sha, positions must still equal its
  "current", and dry-run, arming (`--approve`, `APPROVED` or `AUTO_ARMED`), halt,
  late clock, no-set, shortability, exposure and sanity are re-evaluated on fresh
  broker reads. Sent as `type=market, time_in_force=day`, the window re-checked
  before every POST.
- **A decided plan is never overwritten** -- not by a later manual run, and never
  by `--preview` (which would re-size on intraday equity). To re-decide on purpose,
  delete `<D>/plan.json` and `<D>/DECIDED` first.
- **A name that turned unshortable since the decision is skipped at send and the
  rest go** (team lead 2026-09-28, "skip that name, send the rest"); the arming
  check still binds to the decided plan's sha, so what goes is a subset of it.
  If that leaves nothing to send, the day is a `MISSED:` FAIL (2026-10-13, below).
- **The send records its outcome** in `<D>/send.json` (exit, refusals, skipped,
  and since 2026-10-13 `bp_scale_at_send`, the re-fit's result); verify explains
  a no-trade day from it, and a decided plan with no send record is FAIL "no send
  ran in the late window".
- **A set the window cannot finish is not started** (added 2026-10-08,
  release-check #6). `gate.gate_late_send_budget` refuses before STARTED and before
  any POST unless the time left on Alpaca's clock is at least
  `n_orders × 3 s + 42 s`; the constants and their provenance are in `gate.py`. The
  42 s margin is the connect and read timeouts plus one retry backoff (corrected
  from 30 s, release-check #7). At 13 orders a set may start until 15:56:39, so the
  15:52 send and the 15:55 retry are unaffected. The case it closes: a decide that hangs until about 15:57,
  followed by a timer firing queued behind it, would otherwise send a partial
  batch cut off at 15:58. Such a refusal is recorded as `budget_short` in
  `send.json`. verify FAILs the day when time was the only obstacle; a halt, dry run
  or arming refusal on the same send explains the day instead. (Since 2026-10-09
  every refusal but those three is a FAIL: "As built (2026-10-09)".)
- **Scoring is unchanged:** verify marks every fill against the official closing
  print (`fill_vs_auction_bp`), beside the shadow benchmark. Revisit after a week.
- **Revert:** delete the `execution` block; the runner sends `cls` exactly as before.

## As built (2026-11-09): the daily P&L report, beside the runner and outside its order path

**The job.** `scripts/ops/pnl_report.py` (timers `quantt-{cef,c4}-pnl`, 20:30 and 20:35 ET;
`docs/RUNBOOK.md` 8.12), report-only, one per book: the attribution
(`scripts/cef/live_attribution.py`) and the factor readout (`scripts/cef/exposure_readout.py`)
of the session just closed and cumulative from the first trade, written to
`<state>/reports/pnl/<date>.{md,json}`, which `scripts/ops/risk_daily.py` reads into its
attribution and factor blocks. The runner does not read these, and they cannot reach it:
the job holds no order code, no broker client and no panel lock, and it reads the account
through `scripts/ops/alpaca_read.py`, a GET-only reader with no method that can change
anything (`scripts/ops/tests/test_report_no_order_path.py` walks every import from the job and
fails on any path to order code). A review-line breach appears in the report and goes no
further: no ACT, no push (team lead, 2026-11-09).

**The reader is a copy on purpose.** It re-implements the reads the job needs from
`quantt/broker/alpaca.py` (EOD history mapped to sessions, FILL and FEE activities, calendar,
SIP daily bars, distributions, the strict corporate-action read) instead of importing
them, because that module holds `submit_order`; `scripts/ops/tests/test_alpaca_read.py` keeps
the copy honest by running both on the same fixture responses and requiring equal output,
read by read, and equal raises on the malformed shapes. Its keys are `ALPACA_<BOOK>_KEY_ID` /
`_SECRET_KEY` from the process environment only, which systemd loads from a tmpfs file of
its own per book (RUNBOOK 8.12), never `QUANTT_ENV_FILE`.

## As built (2026-11-03): CEF trial 55 ("te4"), the thin-session rule, PAPER ONLY, dark

**The rule.** `frozen.below_min_names = "trade_eligible"` with `frozen.below_min_names_floor`
(core spec; `results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md`, approved by the team lead on
2026-11-03 as CEF trial 55, paper only). On a session with fewer than `min_names` eligible funds
but at least the floor, and no NAV hold, the core sleeve builds its book on the eligible funds
with its own construction (the same z-neutralisation, vol scalar, band, gross ceiling and
`sizing_multiplier`) instead of closing it. Below the floor it goes flat, as under the default.
**The key is not set at this commit.** The activation commit sets it, with the K1-K3
thresholds, K3's run length (`risk.thin_k3_run_sessions`, required with the key) and their
notes, once the conditions in the pre-registration's "Approval" section are met. **Absent, or `"flatten"` written out, is today's book, byte for byte**: the sleeve on
every real-panel decision date against main's code
(`results/cef/te4_impl/sleeve_noop_diff_output_2026-11-03-main0b1a2ef.txt`), and the whole
session against 0b1a2ef (`quantt/session/tests/test_trade_eligible_noop.py`).

**Paper only, in two layers** (pre-registration §1.2):
1. **The sleeve** refuses to decide under the key unless it was built with `account="paper"`
   and given `extras["thin_rule"]`. Construction checks only the declaration's value, so
   `spec_panel` and `ops/common.py::deployed_tickers` still work with the key set.
   **`combine.load_sleeves` refuses a budgeted sleeve whose spec sets ANY te4 key** (the rule,
   its floor, a `risk.thin_*` key), naming it, before the sleeve is built, as it refuses
   `level_signal` (the runner owner's review 2026-11-04, item 1): the rule and its stops were
   measured on the core's own account, and netted with another sleeve it is a book nobody
   scored. Were such a sleeve built by hand, the combiner's target callable passes no
   declaration, so it would still refuse at its decide rather than decide by default.
2. **The runner** (`run.thin_rule_for`, at session start, the decide and the send alike)
   declares paper only when the broker client's `trading_endpoint`
   (`AlpacaClient.trading_endpoint`, read-only) is exactly `alpaca.PAPER_BASE`. Otherwise it
   raises `SessionError`, naming the key and the endpoint, before any sleeve is built. It also
   raises on a combined book whose spec sets the key, and on a book json without
   `risk.drawdown`, since K0 would then have no input (the runner owner's answer 4). Today the
   client can reach nothing but paper, so this check exists for the day a live-money client is
   written. **The rule never applies to a live-money account** (`docs/SYSTEM.md` §5,
   2026-11-03).

**The extras contract.** Only when the key is set, the runner passes `account="paper"` to
`build_sleeve` and `extras["thin_rule"] = {"stop": None | {"by": "K0" | "gate7", "why": str}}`
to `target_positions` (`_thin_target_kw`). With the key absent both calls are the calls made
before it existed. Under the key every target carries `meta["cef_thin"]` = {eligible, n,
min_names, floor, holds, reduced, stopped_by}. The runner reads it as a structured field, never
a reason string (`_thin_record`). It refuses a mixed answer, a floor or `min_names` that is not
the spec's, a build under a stop, and a stop it did not pass.

**K0: the first acting reader of the drawdown status, and it only restricts** (§1.3 item 5,
§6.3; the owner's term 3). K0's drawdown record is read before the sleeve runs. Only an exact
`OK` lets a reduced book be built. HALVE, KILL or UNMEASURED (no `eod_equity.csv`, a newest row
older than the read-through date, bad levels, a check that raised), or any other status,
becomes the stop `{"by": "K0"}`. A reading that raises anywhere, its read-through date
included (nyse_calendar and Alpaca's calendar disagreeing on the session before the as-of), is
recorded as UNMEASURED with the exception's type, and the session flattens: K0 fails closed.
`test_k0_fails_closed_when_its_reading_raises` and the gross pin's "raises" case cover that
branch (review finding after f3ad29f: before them, a fail-open branch passed every test).

**K0 reads through the session before the as-of** (team lead's ruling, 2026-11-03, recorded in
the pre-registration's "Approval" section and in E-2026-11-03-42). At prod's 22:00 decide the
EOD row for the as-of D is never there yet: 4 of 4 core decides that carry the drawdown field
read UNMEASURED because `eod_equity.csv`'s newest row was D−1 (E-2026-11-03-41, the owner's
finding, from prod's plan.json records [S]). K0 as first built read step 2b's record, so it
would have flattened every reduced session and the trial would never trade.

K0 now makes its own reading (`run._thin_k0_drawdown`), always from the FRESHEST row it has
(the team lead's second ruling, 2026-11-04):
- **The as-of's own row first.** It runs `drawdown.check(..., read_through=D)`, labelled 0
  sessions stale.
  - If D's row is there, it decides, whatever it reads. That includes a bad row, which reads
    UNMEASURED: K0 never falls back past a row it has.
  - This is what happens at the morning backstop. Before this ruling, K0 read D−1's row there,
    and a reduced book went out on a stale OK while D's row read KILL.
- **Only if D's row has not landed** (the 22:00 decide, every time), it runs
  `drawdown.check(..., read_through=<the session before the as-of>)`. The date comes from
  `asof_for` (nyse_calendar and Alpaca's calendar, which must agree; never a weekday guess).
  - That is the same check through the newest row on or before D−1, with the high-water mark
    over those rows.
  - The newest such row must be D−1. An older one, or a missing or bad file, reads UNMEASURED
    and the session flattens.

The record carries `read_through` and the reading's `stale` = {`row_date`, `sessions`}: 1 at the
evening decide, 0 when D's own row was read. It is stored whole in `thin_session.k0.drawdown`.

The cost, accepted by the ruling: at the evening decide, a loss on D is seen only at the next
decide, so one more reduced build can go out after a session that crossed HALVE. **Step 2b's own record (HALVE/KILL's report) is
unchanged** (`read_through` None is today's check, byte for byte) and K0 does not read it. The sleeve then takes today's flatten, with the reason in every target. A missing
record raises. K0 has one action, today's rule: it never sizes up and never unlocks a send. The
gross pin in `quantt/session/tests/test_trade_eligible_runner.py` proves it. The projected
gross after the plan under any status is at most the gross under OK, and equals the key-absent
session's. On a full session the plan is the key-absent one under every status: K0 touches
only a session the reduced build would run on.

**The gate-7 flatten** (§1.3 item 6, §7.5, §10 Q7). Gate 7 (decide's "not shortable today") may
drop an order that opens or increases a short on a reduced decision (`Decision.dropped_shorts`).
If it does, the sleeve is asked again with `{"by": "gate7"}`, the stale-NAV gate's panel check
runs again (the sleeve read the panel again), and the flat targets are decided (`_thin_gate7`).
This runs before the buying-power scaling. A flat book opens no short, so it cannot loop. On a
full session today's skip-and-continue is unchanged. The buying-power rebuild of the Decision
now carries `dropped_shorts` across.

**A short skipped at the late-market SEND: accepted and labelled** (team lead, 2026-11-03).
`_send_planned` is unchanged, on reduced and full sessions alike: a short whose name stopped
being shortable after the decide is skipped and the rest go. The next decide's
`thin_stops.send_skip` reads that session's plan.json (`thin_session.reduced`) and send.json
(`skipped`, the run record's `skipped_at_send`), and records whether the reduced session lost a
short at send. The send skips only short-opening orders, so any entry is a lost short. K3
watches the one-sided book that results. **Only a send that went is labelled** (review fix after
7fcc2b7): `_send_planned` builds its skipped list before its gates, so a refused or dry send
writes the list and sends nothing. Whether a send went is read from the session's own records
(`drawdown._send_state`; the runner owner's review of PR #55, 2026-11-04, items 5 and 10). te4
is PAPER ONLY and paper runs `late_market`, so the late-market rule is the one that runs:
- **What the send writes.** `_send_planned` writes `<D>/STARTED` before its first POST and
  never on a refusal. Its send.json carries `exit`, `plan_sha`, `skipped`, and `final` /
  `not_final`: `_poll_final` fills them only with orders Alpaca accepted and the confirm read
  found (`final` with each one's fills once it is final, `not_final` the rest at the deadline).
  A refused, dry or empty send writes them empty.
- **Sent:** STARTED exists AND send.json's `exit` is SENT (the rule-2 marker plus the send
  record), with at least one of the plan's orders in `final` / `not_final`, and **at least one
  fill** (the runner owner's round-2 answer (b), 2026-11-05). Partially filled is sent: what
  filled is the account's. An order in `not_final` was still working 30 s before the close and
  may yet fill, so a send with one stays sent, as the first review defined it.
- **Sent, nothing filled** (round-2 answer (b); `drawdown.NOTHING_FILLED`): a SENT where every
  order in `final` ended with 0 shares filled, canceled, expired or rejected, and `not_final` is
  empty. Never a FAIL: a FAIL's `final` leaves out any order whose outcome is unknown, so its
  zeros cannot say the book did not change, and it stays "sent in part". The book did not change, so it is
  **not a reduced decision**: it opens no episode, K1 does not compound its earning day, and it
  is not a reduced close for K2 or K3 (N/A, "changed nothing", naming it). A 0-share final
  under any other state (`replaced`, `done_for_day`, a `filled` with 0), or a `final` entry
  without a whole-number `filled`, is UNMEASURED, named.
- **Sent in part:** STARTED and `exit` FAIL, with `final` / `not_final` recording what went (a
  rejection skips its symbol and the rest go). It is classified from `final`: a reduced
  decision, named in the episode's `sent_in_part`. K2 and K3 then see the book it left.
- **Not sent:** DRY, REFUSED or NOTHING_TO_SEND with no STARTED and nothing recorded as gone;
  or no send.json and no STARTED (no send ran in the window).
- **Not sent, proved** (the runner owner's round-2 answer (a), 2026-11-05;
  `drawdown._zero_submissions`): a FAIL with STARTED and nothing in `final` / `not_final`
  whose records prove positively that no POST was made. `<D>/orders.jsonl` exists and holds
  ZERO `submit` events (`_transmit` appends one, fsynced, before each POST), only the
  `cutoff` / `clock_error` event `_transmit` writes when it stops at the clock read before a
  POST, naming one of the plan's orders; and `<D>/reconcile.json`, if verify has written it,
  was written with STARTED and names no order of the session's prefix
  (`<cid_prefix>-<YYYYMMDD>-`, decide's scheme; verify lists every order Alpaca holds with it).
  Every string in reconcile.json is searched except verify's own refusal of that log line
  ("orders.jsonl line n: event 'cutoff' for <cid>, which has no submit line"), which verify
  writes on exactly this case and which names an order without being one. Labelled
  `not sent: 0 submissions proved by <records>`, listing them. The reader (`_thin_read_day`)
  passes the two files as bytes; only this case parses them.
- **UNMEASURED, named:** a FAIL with nothing in `final` / `not_final` and no such proof (an
  accepted POST the confirm read did not find is in neither, so orders may have gone):
  orders.jsonl missing, unreadable, empty or holding a `submit` (an all-rejected set has one
  per order), a reconcile.json that cannot be read or names one of the session's orders; SENT or FAIL without
  STARTED; a STARTED beside a refused, dry, empty or missing send record (a later manual run's
  REFUSED over the send's, for one); another plan_sha; `final` / `not_final` missing or naming
  an order the plan does not hold; an `exit` no send writes.
- **cls** writes no send.json. A set went exactly when `<D>/STARTED` exists, including one
  whose orders then failed (its run record says what went). te4 does not trade under cls.
- `quantt/session/tests/test_thin_send_state.py` has the real send write each of these records
  and reads them back through the runner's own reader; for the proved case the real verify
  writes the reconcile.json.

**The records** appear in plan.json and the run record only when the key is set:
- `thin_session`: `rule`, `floor`, `min_names`, `decided` (did the sleeve run), `eligible` (a
  count), `eligible_names`, `holds`, `reduced` (the trial's unit of evidence, §4.2),
  `stopped_by` (K0, gate7 or null, set only where a stop removed a build that would have run),
  `k0` {`status`, `asof`, `read_through`, `stale`, `stop`, `drawdown` (K0's whole record)},
  and `gate7` {`dropped`} when it fired.
- `thin_stops`: the K0-K3 report lines (`drawdown.thin_stop_record`), **report only**. An error
  inside them is recorded as UNMEASURED, and the session goes on. **They read `eod_equity.csv`
  through K0's read-through date too**, labelled (`thin_stops.read_through` = {`date`,
  `sessions_stale`, `label`}): read through the as-of, every one of them would read UNMEASURED
  at the 22:00 decide (the quant review). They are report only, so they take the same reading
  and say so. **Exactly K0's date** (the runner owner's review 2026-11-04, item 6, on the
  freshest-row ruling): the as-of's own row at the morning backstop (0 sessions stale), D−1's
  at 22:00. `drawdown.thin_stop_record` refuses a K0 record whose read-through date is not the
  lines', so two dates are never mixed silently. **The label says what the data showed** (the
  as-of's own row there at this decide, or not there yet), never which slot ran: the function is
  not told the slot, and the row can be missing at a morning decide or there at 22:00. Until the
  review of 4e1ab0b it named "the morning backstop" or "the 22:00 decide" from the staleness
  alone, and so named the wrong slot whenever the two disagreed; the numbers were right.

| line | what it reads | its threshold |
|---|---|---|
| episode | reduced decisions (`thin_session.reduced` on a plan with no refusals, **whose targets were sent** and filled at least one share (round-2 answer (b)), by the rule in the send-skip paragraph above; §4.2) fewer than 63 sessions apart, walked back through earlier plan.json, send.json and STARTED files. A decided reduced plan whose send did not go is not a reduced decision: it opens no episode, earns K1 nothing and is not a reduced close for K2 or K3 (corrected after the reviews of 7fcc2b7, whose first build counted it). A record that cannot be read, a send whose outcome cannot be established, or a send.json or STARTED with no plan.json makes the whole episode UNMEASURED. A session with **no record at all** (no plan.json, send.json or STARTED: the runner did not run, or its decide failed before writing a plan) is a **named gap** (`episode.gaps`; the runner owner's review 2026-11-04, item 5): it makes UNMEASURED only the stops whose read window holds it, never the whole walk for 63 sessions. Those windows: the episode state (K0's KILLED), the 62 sessions before this decide, and a known reduced decision there still reads OPEN; K1, the decisions whose earning day is on or before the read-through date; K2 and the send skip, the as-of session; K3, the as-of session and the closes its run reads back until it breaks. A plan decided with the key absent ends the walk | — |
| K0 | K0's drawdown status at this decide, read through the freshest row (the as-of's own when there, else the session before it): KILLED if HALVE or KILL while an episode is open | `risk.halve_drawdown` / `kill_drawdown`, through the status |
| K1 | the maximum drawdown of the episode's earning days, compounded: a decision for session s earns eod_equity(e) / eod_equity(s) − 1 on the next session e, counted once e's row is on or before the read-through date (at 22:00 the as-of's own earning day is listed as `earned_not_yet_read` and counted at the next decide; at the morning backstop it is counted) | `risk.thin_k1_episode_drawdown` |
| K2 | the largest \|position × as-of close\| / eod_equity of the read-through date, at the close after a reduced decision. Always recorded as `equity_date`: the as-of's own row when it exists (the morning backstop), else D−1's, which then carries an `equity_note` (off by one session's return) | `risk.thin_k2_max_name_frac` |
| K3 | \|long − short\| / eod_equity of the read-through date, at that close: above the run line on `risk.thin_k3_run_sessions` reduced closes in sequence (§6.3's 3; within the open episode only, as §6.3's heading says and the runner's owner confirmed on 2026-11-04, recorded in the pre-registration's Approval section), or above the once line. The earlier closes are read back from earlier plans: the decide for session X records the close of the session before X, so the close before the as-of is in the as-of session's own plan (corrected after the reviews of 7fcc2b7, which found the first build counting one close too far back). An earlier K3 that is unmeasured, or that names another close, makes the run UNMEASURED, as does a named gap among the closes it reads back, or a run still open where the walk stopped at a record it could not read | `risk.thin_k3_net_run`, `risk.thin_k3_net_once`, `risk.thin_k3_run_sessions` |
| send_skip | the label above | — |

A line whose threshold is absent reads UNMEASURED, never a default.

**The threshold keys** (`src/deploy/registry.py` `cef_thin_stop_levels`, in the spec's `risk`
block) are set in the activation commit. Each is re-measured on its read date by
`results/cef/prereg_thin_te4/compose.py --stamp <date> --k3-run-sessions <n>` (H14; `<n>` the
spec's `risk.thin_k3_run_sessions`, below), and each needs a sibling
`_<key>_note` that names the `compose_<stamp>.json` that derived it; the registry refuses a key
without one. The registry also refuses:
- any of them, or any of their `_<key>_note`s, under another rule (the notes since the review
  of 4e1ab0b: a note left behind by a revert loaded cleanly until then);
- a non-number, NaN or a value at or below 0;
- K1 at or above 1 (a fraction, never a percent);
- K2 or K3 (either K3 line) at or above `frozen.max_gross_stress`, at construction
  (`validate_spec`, which `build_sleeve` runs before it builds), with a message naming the key,
  its value and the cap (confirmed for the runner owner's review 2026-11-04, item 4);
- the run line not below the once line;
- a near-miss spelling in `risk`, and any of them written in `frozen`.

**K3's run length, `risk.thin_k3_run_sessions`** (the runner owner's review 2026-11-04, item 9).
How many reduced closes in sequence above the run line trip K3: §6.3's 3. It was a constant in
`drawdown.py` (`THIN_K3_RUN`) until that review; the spec is the only authority on a stop's rule,
so `drawdown.thin_stop_record` now reads it from the thresholds the runner passes, and holds no
constant. Unlike the four lines it is **required** whenever `below_min_names` is
`"trade_eligible"`, with no default: a spec without it refuses at load, as one without a floor
does. The registry refuses it under any other rule, a non-int (a bool, `3.0`, a string), a value
below 2 (one close is the once line's business), a missing or empty `_thin_k3_run_sessions_note`
(the count is pre-registered, not derived by compose.py, so the note need not name a
`compose_<stamp>.json`), a near-miss spelling and the key written in `frozen`. Tests that set the
rule set it (`test_trade_eligible_runner.te4`).

**The run length and the compose run must agree** (the runner owner's round-2 answer (c),
2026-11-05). `compose.py` counted §E's fit runs with a literal 3 (and 2 for context) while the
spec carries the count, so the two could drift apart unseen. It now takes K3's run length as the
**required** argument `--k3-run-sessions` (no default; at least 2, the registry's rule), counts
§E's runs with it (runs of n above the fit p99, and of n − 1 for context) and records it in
`compose_<stamp>.json` as `k3_run_sessions`. The drafting day's files (2026-11-03) predate it and
record none. `src/deploy/tests/test_thin_k3_run_provenance.py` fails any committed spec under
`ops/specs/` that sets `risk.thin_k3_run_sessions` when a `compose_<stamp>.json` named in its te4
notes (the four lines' and the run length's own) is missing, unreadable, records no run length or
records another one, or when a K-line's note names no compose file.

**Why that guard is a test, not a registry check.** The owner asked that "the registry refuses a
spec whose risk.thin_k3_run_sessions differs from the run length recorded in the compose file its
threshold notes cite". The owner also ruled (answer 3, 2026-11-03) that the live path never reads
`results/`, and `src/deploy/registry.py` validates on the live path: the sleeve's constructor and
`run.py` call it on every session. So the guard reads `results/` in a test instead. CI runs it on
every push (`.github/workflows/checks.yml`), and prod installs only a release-checked tag
(`/release-check` runs the suite), so a spec and a compose file that disagree cannot reach a
release together. What it does not catch: a prod clone edited by hand, which no release check
sees. **The owner can overrule this** and move the check into the registry.

The live path never reads `results/`.

**Unchanged.** The missing-NAV and stale-NAV holds: with any hold present the reduced build never
runs, and today's `min_names` path decides, tag included, so the missing-NAV refusal still keys
on it (§7.7). `_send_planned`, the first-session gate, the arming refusals.

**Revert.** Set `below_min_names` back to `"flatten"`, or delete it, through `/spec-change`.
Delete the floor and the five `risk.thin_*` keys (the four lines and `thin_k3_run_sessions`) and
their notes with it, because the registry refuses them under any other rule: the keys, and since
the review of 4e1ab0b their notes too (`_below_min_names_floor_note` in `frozen`, each
`_thin_*_note` in `risk`), each named. **One note it cannot refuse:** `_below_min_names_note`,
because C4's `"hold"` spec carries it legitimately; delete it with `below_min_names`, and only
the diff below guards it. The no-op pins prove the reverted session is today's.

**Activation checklist, for the record (not done now).**
1. **The revert spec** (the runner owner's review 2026-11-04, item 2). The
revert spec built in the activation release deletes `below_min_names`, its floor and the five
`risk.thin_*` keys with their notes. With them absent, the revert spec must be **byte-identical
to the pre-te4 spec**, the spec file as it stood before the activation commit. Diff the two files
before tagging; any other difference is a second change riding on a revert. The registry's
refusals catch a te4 key or te4 note left behind, not `_below_min_names_note` and not any other
edit: the diff is the guard of record.
2. **K3's run length and its compose run** (the runner owner's round-2 answer (c), 2026-11-05).
Set `risk.thin_k3_run_sessions` to the `k3_run_sessions` recorded in the `compose_<stamp>.json`
the thresholds are taken from: **3 at the 2026-11-05 run** (`compose_2026-11-05.json`, run with
`--k3-run-sessions 3`; every figure the drafting day's). A read-date re-run (H14) records its
own; run it with the run length the spec will carry. **Cite that compose file in every threshold
note** (`_thin_k1_episode_drawdown_note`, `_thin_k2_max_name_frac_note`, `_thin_k3_net_run_note`,
`_thin_k3_net_once_note`). `src/deploy/tests/test_thin_k3_run_provenance.py` fails the activation
commit if a cited file is missing or records no run length or another one (the files of
2026-11-03 record none, so a spec citing them fails).
3. **Three fixes from the owner's release-check of 78e3483 (2026-11-09), done before the key is set.**
   - `thin_rule_for` refuses, at session start, any execution mode but `late_market`: under `cls`
     an episode could open on STARTED alone, with no fill known.
   - `_send_state`: a reduced plan the buying-power fit scaled to nothing (`bp_scale` orders_in >
     0, orders_out 0) is not sent. An empty plan with no such record still means the account
     already held its targets.
   - The drift guard (`test_thin_k3_run_provenance.py`) also compares the four K-line values and
     the compose run's m and floor with the spec. A spec value may be the compose value rounded,
     at 3 decimals or more; any other difference fails the activation commit.
4. **A known limit to revisit at activation** (the owner, 2026-11-08). A set rejected in full at
the POST (a 4xx on every order) has a `submit` line per order, so it reads UNMEASURED even though
each `rejected` event shows the order does not exist. It is rare and fails closed.

## As built (2026-10-29): gate 6 reads its lists last

**The defect** (execution-trader, release-check of 35b429f, 2026-10-29;
confirmed in code). Gate 6's Alpaca check is the only guard against a second
runner, or a lost state directory, doubling the book (CLAUDE.md order-path
rule 2), and `_transmit` never reads the orders again. Both paths that transmit
read `orders_recent` and `orders_open` early and judged them at the gate. The
late-market send read them before the asset GETs, the closed-order history and
the corporate-action pages (the gap PR #20 widened). The `cls` run, which is
also the late-market decide, read them at step 2, before the asset GETs, the
sleeve and the corporate-action pages. One GET that exhausts its retries takes
about 250 s ("Latency at the send"). The send-budget gate refuses only past the
window's end minus the set's budget, so a stall that finished earlier sent on
lists minutes old, blind to a set placed meanwhile.

**The fix** (`run._gate6_orders`). On both paths the two lists are the last
broker read before the gate's clock read: after every asset GET, the
closed-order history and the corporate-action read. The clock read stays after
them on purpose, so the late-clock and send-budget gates (gate 4 for `cls`)
judge a time after this read too: a slow read can only make them see a later
time. Between the lists and the first POST stand only that clock GET, the pure
gates, STARTED and `_transmit`'s clock GET before the POST. Neither path reads
the lists anywhere else, so no earlier read can stand in for them. A failed read
is a gate-6 refusal naming the error (`gate_no_set_in_auction(..., unread=)`),
never an empty list. It is not a FAIL, so the next slot may retry, and verify
reads the day as MISSED. The closed-order history stays at step 2 of the `cls`
run, because the decide needs it (`is_opening_session`) and step 3b dates held
names on it.

**What did not change.** With no other runner, the orders sent, send.json,
plan.json, orders.jsonl, STARTED (bar its pid) and every run record are
byte-identical to 35b429f. Records are written with sorted keys, so moving
where `orders_recent` and `orders_open` enter the run record changes no byte.
`quantt/session/tests/test_gate6_fresh.py` pins this against hashes computed by 35b429f's
code. It also has the cases that failed there: an order landing during the
corporate-action read or the asset GETs, on both paths, refuses; and a failed
read at the gate refuses.

**Not covered.** Two runners that both read before either sends still both
send; gate 6 narrows that race and cannot close it. Only one armed scheduler
per account closes it (RUNBOOK §8.5).

## As built (2026-10-29): gate 5's missing-NAV hold, dark

The team lead approved it on 2026-10-29. On 2026-10-22 PDO's NAV for the as-of
2026-10-21 never reached the panel. fetch_daily exited 4 on every slot, because
its CEFConnect fallback has failed with JSONDecodeError since 2026-10-21. Gate 5
then refused all 13 names, and the book missed the day. The why of each choice is
in `quantt/session/gate.py` `missing_nav_hold`.

- **Off by default.** The book json key is `data.missing_nav`, and `hold` is its only
  value. With the key absent, `Deps.missing_nav` is None and the session is bd87144's
  (release-20261029-1), byte for byte. The proof is hashes computed by bd87144's code
  on the real panel and on a synthetic panel that never skips: a complete day, and a
  day with one as-of NAV missing at the evening decide and at the final check
  (`quantt/session/tests/test_missing_nav_hold.py`).
- **Evening and morning, before the final check** (close − 90 min, the stale-NAV
  gate's `final_check_at`). A name whose NAV is not dated the as-of date refuses the
  decide with today's gate-5 refusals, plus one line saying it is deferred. Nothing is
  decided or marked, and the next slot re-runs the refresh. A NAV that lands in the
  meantime is simply used.
- **From the final check.** Each such name is held. It keeps its current shares, gets
  no order, leaves the cross-section and is never targeted to zero. The other names
  decide. The hold goes to the sleeve as the stale-NAV gate's `nav_hold` extra. A held
  name has no paired row on the date, so the sleeve counts it toward `min_names`: if
  the holds leave too few eligible names, the whole book holds. They never cause the
  flatten. The stale-NAV gate also runs on that exit-4 refresh.
- **Still refused, at any hour, as today.** A missing or stale close; a name with no
  NAV at all; a refresh failure other than exit 4; and more missing NAVs than
  `gate.max_missing_nav_holds` = n − `min_names`, read from the frozen spec. Past that
  limit fewer than `min_names` names would have a NAV, the sleeve could trade none of
  them on its signal, and so it is a broken feed, not a late NAV.
- **Short of `min_names` after the sleeve's own exclusions** (release-check of 6d42f4f).
  The n − `min_names` cap counts only the names without a NAV. Holds plus names the
  sleeve leaves out (illiquid, ADV unmeasured, NAV stale, no z-score, no panel) can still
  leave fewer than `min_names` names eligible on their signal. The sleeve would then hold
  the whole book, the plan would read NOTHING_TO_SEND, and the day would be marked DONE.
  Instead the day is **refused** as without the key, naming the held funds, the eligible
  count and each exclusion. The count is the sleeve's own `min_names` count, carried in a
  structured tag on its targets (`cef_discount._tag_short`); the runner never parses a
  reason string. The stale-NAV gate's own holds keep their ruled whole-book hold.
- **The age limit (team lead 2026-10-29, a policy).** A fund may be held for at most
  `data.missing_nav_max_sessions` consecutive sessions: 2. This is the book json's value,
  not a code literal, and it is required when the hold is on. It was meant to be derived
  from how long the vendor's NAV gaps last, but prod's NAV panel (copy of 2026-10-28) shows
  no gap in 12 months. The vendor backfills dates, so a late NAV survives only as a
  repeated value. Two sessions were chosen because PDO's 10-22 gap was one session long,
  so a late NAV can land the next day. The limit is to be reviewed against the live gaps
  in the run records' `nav_dates`.
  At the final check after that limit, if the fund's NAV is still not dated as-of, the day
  is **refused** exactly as without the key, with one line naming the fund and its count.
  The count is re-read at each final check from the prior sessions' plan.json
  (`run.missing_nav_streaks`). A dated NAV resets it. A record that is missing,
  unreadable or silent about the fund refuses the day; it is never counted as zero.
- **Records.** plan.json and the run record carry `missing_nav`: the action (`none`,
  `deferred`, `held` or `refused`), why, each missing name's last NAV date, the limit,
  each name's prior count (`held_before`), and what was held. The log prints one
  `MISSING NAV` line.
- **Single-sleeve book only.** A combined book holds whole sleeves
  (`gate.gate_data_by_sleeve`). The key with a combined book fails the session,
  naming it.
- **Revert:** delete both keys.

## As built (2026-10-28): the multi-sleeve combiner, dark

The team lead approved building it on 2026-10-28 ("build the combiner, decide
placement after"). One Alpaca account takes one order per symbol (CLAUDE.md
landmine 2), and the agent lab must net into C4's targets in the account they
share (`docs/SYSTEM.md` §5, 2026-10-28). The design is the portfolio framework's
phase C (`results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md` §2.10, §7). The why of
each choice is in `quantt/session/combine.py`'s docstring.

- **Off by default.** It is on only when every enabled entry of the book json's
  `sleeves[]` carries `risk_budget`. The released json carries none, so
  `Deps.sleeves` is None and the session is de6e9c5's, byte for byte. That is
  proved against hashes computed by de6e9c5's code on the real panel and on a
  synthetic panel that never skips (`quantt/session/tests/test_combine_noop.py`).
  With no budget, the json must name exactly one enabled sleeve whose spec is the
  book's, else the run fails before it starts.
- **Sizing.** sleeve_nav = equity × risk_budget × σ_book / σ_sleeve. σ_book is the
  book spec's `frozen.vol_target_annual`, so the budget is the sleeve's share of the
  book's vol target. The budgets are inputs from the allocation analysis.
- **Netting.** The sleeves' whole-share targets are summed per symbol, and `decide`
  runs once on the net: one order per symbol, flips and shortability on the net.
  **Enabled sleeves may not share a symbol** until per-sleeve sub-ledgers exist
  (release-check of 00ec423). `load_sleeves` and `combine.decide` refuse an
  overlap, naming the symbols. Accepted, the shared symbol would net from flat on
  day one, and every later session would FAIL on the position that built. The
  cross-sleeve arithmetic is kept behind `combine.SHARED_SYMBOLS_ALLOWED` (False).
- **Book-level limits.** The book spec's `max_gross_stress`, applied once to the
  netted orders by `fit_to_buying_power` and gate 8. Its value was derived for the
  13 alone and must be re-derived on the combined book before a second sleeve is
  enabled (framework §2.7).
- **Gates.** Gate 9 and the send read the union of the enabled sleeves' universes.
  Gate 5 runs per sleeve (`gate.gate_data_by_sleeve`). Before the final check
  (close − 90 min) a failing sleeve refuses the decide, as today. From the final
  check it is held at its shares and the rest decide. fetch_daily's exit 4 is
  attributed by that per-name check, and every other refresh failure stays
  book-wide. The stale-NAV gate's holds go to the sleeve that owns each name; a
  deferral stays book-wide (one plan per day). On a combined book the stale-NAV
  gate also runs when the refresh exits 4, over every enabled sleeve's names, and
  its record says so (`refresh_exit`). Exit 4 is the case in which some sleeves
  decide; 00ec423 skipped the gate there and sent them unchecked. That is safe
  because the gate never acts on a name with no NAV dated as-of; that name is
  gate 5's.
- **Attribution.** plan.json `combine`: each sleeve's spec, budget, sleeve_nav,
  status, and per symbol its current and target shares. Verify, score and TCA do
  not split P&L by sleeve yet.
- **Not built:** per-sleeve sub-ledgers (a held position in a symbol two enabled
  sleeves trade fails the session, naming it), a per-sleeve opening session, a
  refresh and a stale-NAV gate per panel (next section), sleeve `state` and
  sleeve-scoped halts (framework §3.5).

## As built (2026-10-29): each sleeve on its own panel (C4 plan row 6A), dark

The team lead fast-tracked C4 on 2026-10-28/29, keeping every gate. C4 decides on
`data/cef_c4/` (its spec's `panel_source`), the 13 on `data/cef/`. Until this the
runner priced, gated and NAV-checked every name on `data/cef/` and refused any
other panel (`require_core_panel`, C4 step 1). The why of each choice is in
`quantt/session/run.py`, PER-SLEEVE PANELS.

- **What reads the sleeve's own panel.** `spec_panel` is the sleeve's own
  `panel_paths()`. From it come the closes the orders are sized on (and gate 8 and
  the fit), the NAV dates gate 5 checks (per sleeve on a combined book) and the
  missing-NAV hold reads, the pre-flight's close history, MarketState's prices,
  the stale-NAV gate's file and the refresh's flags. verify and score read
  Alpaca's prints, not a panel; TCA's tagged fallback reads plan.json's `closes`,
  which now come from each sleeve's own panel.
- **The no-op.** The released book json, with `data.missing_nav` absent and set,
  decides byte-identically to 5e627ff through `default_deps` itself
  (`quantt/session/tests/test_panels_noop.py`, synthetic and real panel).
- **The guard.** At each read, inside the session: a sleeve whose panel files are
  absent, or whose universe has a name with no row in its own price or NAV file,
  FAILs the decide naming the files or the names. Not in `default_deps`, which the
  15:52 send also builds and which reads no panel.
- **The refresh.** `refresh_flags` is the interface C4 step 3 fills: the core
  panel gets today's `--nav-fallback cefconnect` command; a data book's panel
  (`DATA_BOOK_DIRS`: C4's `data/cef_c4/`, since the 2026-10-29 integration below)
  gets `--data-book c4`; any other panel, and a book whose sleeves read two
  panels, gets no fetcher, and gate 5 refuses the day (recorded).
  `--skip-refresh` still runs.
- **The stale-NAV gate** stays on the core panel: `data.stale_nav` on a book
  with a sleeve on another NAV file is refused before any client is built
  (CEFConnect is disabled for C4; the gate locks and logs as the core's fetch).
- **Revert:** the commit. C4's spec and book json name another panel (below).

## As built (2026-10-29): C4's own book, dark (C4 plan rows 6A, 8 and 11)

Branch `c4-integrate` merges C4 steps 2 and 3 and row 6A onto main, then builds
what C4 needs to dry-run on its own Alpaca paper account. Nothing schedules it
until the team lead installs it; the steps are
`results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md`.

- **`BOOKS["c4"]`** (`quantt/session/run.py`): spec
  `ops/specs/c4_families.frozen.json`, book json `ops/books/c4_families_book.json`,
  order ids `c4-<YYYYMMDD>-…`, keys `ALPACA_C4_KEY_ID` / `_SECRET_KEY`. A C4
  session, approve or verify refuses a state directory not named `c4`
  (`records.STATE_DIR_NAMES`) before writing anything there.
- **The book json:** one sleeve at its own $100k; late-market execution as for
  the core; the missing-NAV hold (2 sessions); drawdown in report mode, against
  the core's halve/kill levels since spec `c4_families.v3.20261102` (team lead
  2026-10-30; until v3 the spec named none and every decide recorded
  UNMEASURED); the corporate-action gate in `report`, as the core, since the
  team lead's 2026-11-02 ruling (it was `halt` until then; the ruling followed the
  measurement in the checklist's "corporate-action mode"). **No `data.stale_nav`**:
  CEFConnect is disabled for C4, and the spec's NAV-repeat mask is its defence.
- **The refresh** is `fetch_daily --data-book c4 --book ops/books/c4_families_book.json`
  under C4's own lock. Its exit 6 (an unruled spike-and-revert bar) is a gate-5
  refusal at every check. It outranks the fetch's INCOMPLETE exit 4 (since the
  release-check of 8b14298), so a late NAV, which the missing-NAV hold accepts at
  the final check, can no longer let an unruled bar through.
- **The opening-session rule and the first-session gate** (C4 only; release-check of
  336df9d, R1; the rule: team lead 2026-11-03, "just flat it", `docs/SYSTEM.md` §5,
  PR #30; the existing spare account, ruled 2026-11-02). C4's book json sets
  `execution.opening_session_fills = "own_prefix"` (`run.opening_session_fills_for`):
  `is_opening_session` then counts only fills with C4's own `c4-` prefix, so the research
  loop's fills in the shared account do not open C4 at the band edge (28-42% of target, net
  long); positions count whatever their origin. ABSENT (the core) is `any`, today's rule.
  Until C4 has a fill of its own, an ARMED C4 run that is not an opening session under that
  rule, that finds another runner's open order, or that cannot read the open orders
  (UNMEASURED), is refused before its first order, at the decide and at the send, under its
  own gate `first_session` (outside verify's DELIBERATE_GATES: a MISSED day); unarmed,
  `plan.json`/`send.json` `first_session` records it (`run.OPENING_REQUIRED_BOOKS`). The core
  reads and records nothing new.
- **verify** scores distributions against C4's own panel
  (`dist_score.PANELS["c4"]`, `data/cef_c4/cef_distributions.parquet`).
- **The installer:** `install_vm --book c4 --eod-from YYYY-MM-DD` writes seven
  `quantt-c4-*` units beside the core's (`docs/RUNBOOK.md` §8.9).
- **The no-op:** the core's session is cee16ad's with the corporate-action block
  absent, and 35b429f's as released (`tests/test_panels_noop.py`). The core's
  install is byte-identical to cee16ad's installer
  (`quantt/deploy/tests/test_install_vm_books.py`).
- **Merged onto main, 2026-11-02 (branch `c4-rel`).** On 862b1d0
  (release-20261102-1): no textual conflict. `ca-ack` gained the per-book
  state-dir rule. C4's spec took CEF trial 53's `sizing_multiplier` 1.27
  (`c4_families.v2.20261101`) and then the core's halve/kill levels
  (`v3.20261102`). `tests/test_panels_noop.py` was re-pinned on
  `git archive 862b1d0`, so the core's session is now proved to be 862b1d0's,
  with the gate block removed and as released.

## As built (2026-10-28): the corporate-action gate, `halt` on paper

**The defect.** Alpaca paper processes no corporate actions: no splits and no
mergers (`docs/REFERENCES.md` §12pc). IBKR paper processes none either, so paper
stays on Alpaca (`docs/SYSTEM.md` §5, 2026-10-28). The runner reads broker share
counts as they are and prices them at the as-of close. Take a held fund that
reverse-splits 1:4. Paper keeps the old count while the price is four times
higher, so the plan's dollar exposure, equity and the orders sent to reach
target are all wrong. Nothing handled this. The team lead ruled a HALT guard
(2026-10-28).

**What runs.** `quantt/session/corp_actions.py` is step 3b of every DECIDE, after
the decision and before the gate's clock read. It runs again at the late-market
SEND, on fresh reads, because Alpaca can list an action effective today after the
evening decide.
`AlpacaClient.corporate_actions` reads the thirteen non-dividend types: reverse,
forward and unit splits, stock dividends, spin-offs, cash, stock and
stock-and-cash mergers, redemptions, name changes, worthless removals,
reorganizations and partial calls. The request sends no `symbols` filter,
because the reference does not say which field it matches on a merger. Every
symbol field is matched client-side, so the acquirer and the acquiree are both
mapped. It asks for `data_quality=all`, which includes the early, unprocessed
records (2026-10-29). A reorganization leg with no ticker but a CUSIP names
nobody. On twelve months of the real feed, 29 reorganizations carried such legs,
and the first version of the parser raised on them (`docs/REFERENCES.md` §12pc).

**A malformed row.** Two rulings apply. The first is `docs/SYSTEM.md` §5,
team lead 2026-10-29: "skip it, and record it, unless it could concern one of
our funds". The second is docs/SYSTEM.md §5, team lead 2026-11-02 (unresolved corporate-action rows), which governs a row with a missing party.

- **An UNRESOLVED row: a party symbol null or empty.** This covers any required
  symbol field of any type and role, and a reorganization leg with no ticker
  and no CUSIP. The reader returns such a row, with its id, its raw row and the
  missing fields named, and does not raise on it. The gate treats the missing
  party as each of its names in turn (held, and targeted), in the missing
  role, on its usual short and long windows.
  - If that would block for one of them, the session refuses, naming the row
    and the field (`an UNRESOLVED ... its <field> is missing ...`).
  - Otherwise the row is recorded only, under `corporate_actions.unresolved`
    with one log line.

  A short-window case, such as a missing acquirer or allocated leg, halts one
  session and then clears. A long-window case, such as a missing subject on a
  held name, halts until the team lead acknowledges it with `ca-ack`, matched
  on its full raw content and its type. When the id is null too, the key is a
  hash of the raw row (`row-sha256:...`). An unresolved row whose dates
  cannot be read is UNDATED: keyed by its hash and treated as inside every
  window, so it halts until acknowledged.
- **Skipped and recorded.** This applies to a row whose every party symbol is
  present, none in the book's universe, with a non-party field malformed: its
  id, its date field or `process_date`. It goes in
  `corporate_actions.skipped_malformed` in plan.json, send.json and the run
  record, with one log line. The same fault on a row naming a fund of the
  universe refuses.
- **Not malformed.** Two optional party fields name nobody when empty, as the
  reference documents: a reverse split's `new_symbol` and a cash merger's
  `acquirer_symbol`. A reorganization leg with no ticker but a CUSIP also names
  nobody, the measured exception above. A required field that is absent, a
  symbol that is not a string, or a row that is not an object still fails the
  read.

**Every field validated** (release-check of 1c64638, 2026-11-02). Every
field the reader knows goes through a validator that returns a value or a named
fault, and none can raise: the party symbols, the id, every date, every ratio,
rate, cash amount and price, every CUSIP, each reorganization leg, and the row
itself. Dates must fully match YYYY-MM-DD and be real days, so "2026-02-30",
"0000-00-00" and a trailing newline are faults. Numbers must be finite and
positive (`cash_rate` may be 0).
- A fault on a party field makes the row unresolved.
- A fault on any other field of a row naming ours makes it inside every window,
  keyed for `ca-ack`.
- On a row whose parties are all present and none ours, it is skipped and
  recorded.

`quantt/session/tests/test_ca_read_property.py` substitutes 19 adversarial
values into every field of every type, on a held-fund row and on an outside
row. The read never raises, and every rejected value either blocks, naming a
key `ca-ack` can take, or is recorded.

*History, each step reproduced by a release-check.*
- 9cf5cf2 skipped a malformed row when no symbol present was ours, so a held
  fund's split with a null symbol was skipped and sent.
- 04aca24 skipped it when the subject was present and not ours, so a null
  acquirer was skipped and sent for a held acquirer.
- 709d6cb refused every such row, on a brief that was never a ruling. One
  outside row, of any date, then halted the book indefinitely, and `ca-ack`
  could not clear it.
- 1c64638 let a date such as "2026-02-30", or one with a trailing newline,
  through its pattern. The date then raised unnamed, and `ca-ack` could not
  clear it. On 1c64638 the property test fails 2026 of its 4598 cases; 794 of
  those raise.

**One id, one event** (release-check of 9630322, 2026-10-30, reproduced). Rows
naming ours are de-duplicated by id, because a page boundary can repeat a row.
The id was only required to be present, so two rows with `id: null` counted as
one, and the second was dropped. In the reviewer's probe that was a split
effective on the session date, and the gate read CLEAR under `halt`. From
9cf5cf2 such a row, and an id repeated with a different event, failed the read,
which only a release could unstick. Since 2026-11-02 (team lead: nothing may
need a release to unstick) each is keyed by its content (`row-sha256:...`,
with `row_id` the id as sent). A row naming ours with a null, empty or
non-string id is one such row; every row of an id that Alpaca lists with
different raw content is another (`conflict`). Each is judged like any row
naming ours, so it halts whenever the gate would halt for that fund, and
`ca-ack` clears it on its full raw content. None is dropped. Only an identical
repeat is one event. A malformed row naming none of ours is still skipped and
recorded, whatever its id. With a record to go to, the read now raises only on
transport and shape faults (`AlpacaClient.corporate_actions`, WHAT STILL
RAISES).

**The windows** (ET calendar dates, inclusive; the module docstring has the
alignment in full):

| window | for | why |
|---|---|---|
| long, held name: from the earlier of the date its shares were last set and the as-of date, through the session date | a market-date match in any role but a merger acquirer: acquiree, every split type, stock dividend, spin-off, reorganization, name change, redemption, worthless removal, partial call | paper never adjusts a count, so an action after the shares were last set leaves them on the wrong basis until the name trades again. A name change stays long because paper may leave the position under the old symbol |
| long, target-only name: the as-of date through the session date | the same | every order is priced at the as-of close and fills on the session date |
| short: after the as-of date, through the session date, `(as-of, session]` (team lead 2026-10-29) | a merger acquirer (all three merger types) and a reorganization's allocated leg, both on the **market date only**; and any other match through the process date alone | an acquirer's count does not change, only its price on the terms; the allocated security's holders likewise keep their count (re-review 2026-10-29, flagged to the team lead). The market date only, because the feed lists each real MQY merger twice, processed 02-23 and 02-24, and paper never applies a process date. The feed also backfills old actions years later (a 2016 split processed in 2025), so a process date by itself matters only on the day a broker applies it |

"Last set" is the NYSE trading day before the ET submission date of the latest
order in that name that filled anything. The order comes from the closed-order
history step 2 already reads. That day's close is the latest the order can have
been sized on. A late-market order submitted Monday at 15:52 ET was sized on
Friday's close, so an action effective that Saturday is inside the window
(re-review 2026-10-29). So in both modes the window can only start early. Every role blocks, each on
its own window. A short-window match blocks ONE session: the one whose window
holds its date. The next session's as-of is that date, so it is outside, and the
match clears by itself. By then the as-of close and the counts are post-event and
consistent, so there is nothing left to protect. The long window keeps the as-of
inside, because there the count is wrong.

**The query** asks for process dates from 31 days before the earliest window to
731 days after the session. The API filters on the process date. On the real
feed, process dates ran from 4 days before an action's market date to 3,358 days
after it (`corp_actions.py`, the constants' comment; §12pc).

**On a combined book** (the multi-sleeve combiner above, when a book json turns it
on), the gate's targets are the netted decision's non-zero targets **and** every
sleeve's own (`run._plan_targets`, from plan.json's `combine`). A name two sleeves
net to zero still blocks. Today enabled sleeves may not share a symbol, so the net
equals the owning sleeve's target, but the gate does not rely on that switch. The
held names are still the broker's positions. The decide and the send both run the
gate on that path (`quantt/session/tests/test_corp_actions.py`, the `combined`
tests).

A malformed `combine` record makes the session FAIL (exit 20). It does not
produce the gate's UNMEASURED: `_plan_targets` reads the record as an argument,
before the gate's own error handling, so the error ends the session as any
unexpected error does. That still fails closed, since nothing is sent. Only the
runner writes `combine`: `combine.decide` builds it in-process at decide, and
the send reads it back from that run's plan.json (third review, 2026-10-29;
no code change).

**Modes** (`ops/books/cef_discount_book.json`, `"corporate_actions": {"mode": ...}`;
absent = no gate, today's behaviour, `run.corporate_actions_for`):

- **`report`.** Records the result in plan.json, the run record and send.json,
  prints it, and sends anyway. A read that fails is recorded as UNMEASURED, never
  as clear. With a blocking event it sends the same orders as the gate absent,
  and plan.json is identical once `corporate_actions` is removed
  (`quantt/session/tests/test_corp_actions.py`).
- **`halt`** (set). A blocking event is a gate-5 `data` refusal naming the
  symbol, its role, the type, the id, the dates and the window: exit 11 REFUSED,
  nothing sent. A failed or unparseable read refuses too and names the error. So
  does a held name the order history cannot date.

**Verify.** A refused day reads `MISSED: ... [data] corporate-action gate ...`, a
FAIL. It is not a deliberate `halt`. The book should have traded and could not,
and a person has to look.

**What clears each halt** (`docs/RUNBOOK.md` §6.1 is the procedure):

| halt | what clears it |
|---|---|
| short-window match: a merger acquirer, a reorganization's allocated leg, any match through the process date alone | itself, at the next session |
| long-window match on a target-only name | itself, once the as-of date passes the event's date |
| long-window match on a held name | a filled order in the name submitted on the second trading day after the event or later, through the team lead (§6.1 step 3); or `ca-ack` of its id (step 7) |
| unresolved row (a party symbol missing), short role: acquirer, allocated leg | itself, at the next session |
| unresolved row, any other role, in a name's window | `ca-ack` of the id its refusal names (`row-sha256:...` when its own id is null); or Alpaca completing the row, which is then judged afresh |
| UNDATED unresolved row (a party missing and a date unreadable): blocks in every window | `ca-ack` of its `row-sha256:...` key; or Alpaca completing the row, which is then a new row, judged afresh |
| an acknowledged row, revised or listed under another type (`ack_mismatch`) | `ca-ack` again, which replaces the entry |
| UNMEASURED: the read or the order history failed | itself, when a later slot reads cleanly |
| a row naming ours with a null, empty or non-string id, or an id listed with different content: keyed by its content (`row-sha256:...`) and judged like any row naming ours | as for its window above; `ca-ack` of its `row-sha256:` key |
| UNMEASURED that persists: a transport or response-SHAPE fault only (a failed GET, a body that is not JSON or not an object, a type's list that is not a list, an unknown response key, a bad page token). No value in any field of any row can cause it (2026-11-02, `test_ca_read_property.py`) | Alpaca correcting the feed; otherwise a release (code or `report` mode) |
| `ca_acks.json` unreadable | restoring or removing the file, then acknowledging again |
| any of these, on the team lead's decision | `corporate_actions.mode` set to `report`, through a release |

**What clears it.** A short-window match clears by itself once the as-of passes
it. A long-window match does not clear by itself. While the gate refuses,
nothing trades, so the event stays inside the window. It clears in one of two
ways. One is a person's order in the name, through the team lead (CLAUDE.md
order-path rule 1). It must be submitted on the SECOND trading day after the
event's latest date or later. An order submitted on the first trading day after
is sized on the event's own close, and the inclusive window start keeps the
halt on. A reverse split ex Wednesday 10-07 is not cleared by a Thursday 10-08
order, and is cleared by a Friday 10-09 one. The start stays inclusive so that
a late-listed action dated on an ordinary fill's sizing close is still flagged
(third review, 2026-10-29). The other way is for the team lead to set the mode
to `report` for the sessions that should go. A third way is the team lead's
acknowledgement of the action's id (team lead, 2026-10-29). It is built for a
backfilled name change, redemption, worthless removal or partial call: these
carry only a process date, so a backfill is judged as if it had just happened,
and no trade may be able to clear it. `python3 -m quantt.session ca-ack --book
cef --id <id> --reason "..."` checks the id in the feed, read-only, and writes
`<state>/ca_acks.json` atomically, with the feed row exactly as listed and its
type. It is the only writer. The gate clears that id only, and only while the
feed's row for it still equals the acknowledged row in every field (dates,
parties, ratio and the rest) and its type is the acknowledged type. The raw row
carries no type, so the type is checked on its own (release-check of 709d6cb,
2026-11-02). An unresolved row is acknowledged by its id, or by its
`row-sha256:` key when its id is null. Any other action, a new one on the same fund
included, still halts. So does a revised row under the same id: its record
carries `ack_mismatch`, and the refusal names each changed field, so it needs
a new acknowledgement. *Added 2026-11-01 (release-check of 9cf5cf2): the
first build cleared by id alone.* The
cleared rows stay in the record under `acknowledged`. A file the gate cannot
read refuses (UNMEASURED); it is never read as empty. No file means nothing is
acknowledged. (corp_actions.py, ACKNOWLEDGEMENTS; `run.ca_ack_main`.) Until
2026-10-29 no per-event acknowledgement was built. `docs/RUNBOOK.md`,
"Corporate-action halt", is the procedure, including the phantom P&L that paper
keeps.

**Latency at the send.** The gate adds at least two GETs to the SEND phase: the
closed-order history and the corporate-action pages. Both come before the gate's
clock read. One GET that exhausts its retries takes about 250 s:
- five attempts at the 10 s connect and 30 s read timeouts, 200 s;
- the backoffs 2 + 5 + 15 + 30, 52 s;
- `alpaca.GET_BACKOFF_S` and `TIMEOUT_S` hold the constants.

The late window is 360 s (15:52–15:58 ET), and a 13-order set needs 81 s of it
(`gate.send_budget_s`). So one such stall at the 15:52 send leaves too little
time. The outcome is a refusal, never a partial or late batch. Under `halt` a
failed read refuses. A slow read that succeeds puts the gate's clock read late,
and the late-clock or send-budget gate refuses before STARTED. Either way verify
reads a MISSED FAIL. Under `report` the same time is spent although the result
blocks nothing. Normal reads take a fraction of a second; the slowest measured
order cycle, a clock GET and a POST, was 0.259 s (`gate.py`). No code was
changed for this (review 2026-10-29). Gate 6's order lists, which were read
before both of these GETs, are now read after them ("As built (2026-10-29):
gate 6 reads its lists last").

**Not covered.** Rights distributions, cash dividends and capital-gains
distributions change no share count. An action Alpaca never lists is not seen
either: its merger coverage is mostly effective actions (§12p). A split inside
the signal's own lookback is a panel-quality question for gates 5 and 1b.

## As built (2026-10-19): the drawdown check, HALVE/KILL in `report` mode

**The defect.** The frozen spec carries `risk.halve_drawdown` and
`risk.kill_drawdown`, and the standing decision is to arm HALVE/KILL on
broker-confirmed NAV (`docs/SYSTEM.md` §5, 2026-09-08). On the Alpaca path no code
read either line, and the runner never called the sleeve's `risk_check`, which
writes the lines as literals and returns OK on an exception
(`results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md` §1 item 4 and §3.4; re-verified by
grep at main `832aeaa` on 2026-10-19).

**The rule (team lead, 2026-10-19): report mode first.**
`quantt/session/drawdown.py` runs as step 2b of every DECIDE, after the account
read and before the sleeve. The late-market SEND phase does not run it: the plan
it sends already carries the record.

- **Series.** `<state>/eod_equity.csv`: Alpaca's end-of-day portfolio history
  (timeframe 1D), which the team lead ruled on 2026-10-19 is the **official** daily
  P&L. The collector writes it and backfills it from 2026-09-28. The check reads
  `date` and `equity` **by header name** and nothing else, so an empty `change_usd`
  or an added column changes nothing.
  - Absent or unreadable: **UNMEASURED, naming the file.** There is never a
    fallback to `equity.csv`. Those rows are after-hours account snapshots, and a
    snapshot can set a high-water mark the book never closed at.
  - The snapshot reading is still shown, as a second labelled line and a
    `snapshot` record. It never changes the status.
- **Measure.** HWM = the largest `equity` on rows dated on or before the as-of
  date; drawdown = 1 − newest ÷ HWM. Rows after the as-of are never read
  (asserted). The newest row must be the as-of date. If it is not, the status is
  UNMEASURED, and the figures are recorded under their own date. Whether the EOD
  row exists by the 22:00 ET evening decide was [U] when this was built; report
  mode measured it, and it does not: prod's 4 of 4 decides with the field read
  UNMEASURED because the newest row was D−1 (E-2026-11-03-41 [S]). This record is
  unchanged by that finding (what HALVE/KILL reads is the owning session's to
  rule); CEF trial 55's K0 alone reads the check through D−1 (`read_through`,
  "As built (2026-11-03)").
- **Lines.** `risk.halve_drawdown` and `risk.kill_drawdown`, read from the spec
  that `run.load_spec` loaded, never a literal. Each must be a fraction in (0, 1),
  with halve below kill. A percent written where a fraction belongs is refused,
  not rescaled (the `book_drawdown_suspend_pct` units trap).
- **Status.** KILL at or past the kill line, HALVE at or past the halve line, else
  OK; UNMEASURED when any of the above fails. The record also gives the worst
  drawdown in the series and the first date each line was crossed, which is what
  a sticky acting mode would still be holding.

**Modes** (`ops/books/cef_discount_book.json`, `"risk": {"drawdown": <mode>}`;
absent means off, and the session runs exactly as before):

- `report` **(the release setting)** records the status, the reading and what an
  acting mode **would** do in plan.json and the run record (`drawdown`), and
  prints one `DRAWDOWN` line plus the labelled snapshot line. It changes nothing.
  - The orders, the `plan_sha` and plan.json are those of a check-off session,
    byte for byte, apart from `drawdown`. This is proved on the live spec, the real
    sleeve and the real panel, with the series at OK, HALVE-deep, KILL-deep and
    absent (`quantt/session/tests/test_drawdown.py`).
  - An unexpected error is recorded as UNMEASURED with its type and never stops
    the session.
- **An acting mode is not built.** Setting anything but `report` raises
  (`run.drawdown_for`), so the book json cannot claim an armed HALVE/KILL that
  nothing enforces.

**What an acting mode would do** (recorded each session as `would_on`; a later
ruling):

- **HALVE:** size every sleeve on half its budget, so the vol target halves.
  **Sticky**: it holds until the team lead records a review, never lifted
  automatically on recovery (framework §3.4).
- **KILL:** flatten every sleeve through the normal order path, every gate
  applying. Then write `ops/HALT_cef.md`; the halt must follow the flatten's send,
  or the halt gate refuses the flatten. The team lead restarts.
- **UNMEASURED:** refuse the decide, as a named `risk` refusal; verify reads the
  day as MISSED. Why it should fail closed: `drawdown.py` docstring. A survival stop
  that fails open is the defect being replaced, and a missed day is already loud.
  The alternative for the ruling is a close-only day.
- **Before real money:** the HWM is not flow-adjusted. Alpaca paper has no
  deposits or withdrawals; a live account does.

**Records (H14).** `plan.json` and `runs/<stamp>-run.json` carry `drawdown`: the
mode, the file and series label, the as-of, the levels and their spec source, the
status (and `why` when UNMEASURED), the reading (rows, first and last date,
equity, HWM and its date, drawdown, worst drawdown and its date, first crossing
of each line), `would_on`, `acted: false` and the snapshot. Nothing else is
written.

## As built (2026-10-19): the P&L of record is Alpaca's end-of-day history

Team lead, 2026-10-19 (`docs/SYSTEM.md` §5): Alpaca's end-of-day portfolio
history is the paper book's official daily P&L. Until then verify's line called
the 17:30 ET `equity − last_equity` reading "(official, gross)". That reading is
marked after the close. On the four days compared on 2026-10-19 it disagreed
with the history every time, while the history agreed with the auction-marked
score (`docs/REFERENCES.md` §12an). Nothing on the order path changed: `run.py`,
the gates, decide, the NAV gate and the scheduler units are untouched.

- **Client** (`AlpacaClient.eod_equity_history`): one GET,
  `period=<n>M&timeframe=1D`, the shape read live. Every daily stamp must be
  exactly 00:00 UTC, the only stamp the live read and Alpaca's own example
  show, and in New York time (the evening before) it must fall on a trading
  day by `/v2/calendar`. Otherwise the call raises naming it. Together these
  stop a change of stamping convention, or an intraday reading, from being
  filed under the wrong date. **If Alpaca's winter stamps are not 00:00 UTC**
  (first one: the 2026-11-02 session), the client raises and the official
  figure stays PENDING until a person looks; it is never put on a wrong date.
  Days before the account was funded come back as equity 0 and are dropped
  by name. A zero after funding raises.
- **Final or not.** Alpaca documents neither when a day's point appears nor
  whether it changes later. It stamped the 2026-10-16 close at 20:00 ET. So a
  point whose stamp is still in the future when it is read is not used yet.
- **Verify** writes `official +X USD (Alpaca EOD history, gross)` when D's
  point and the previous session's are both in and stamped before the read.
  Otherwise it writes `official PENDING (<why>)`. Then comes
  `snapshot HH:MM ET +Y USD (gross)` (the old figure, relabelled), then the
  auction mark, unchanged. Nothing stands in for a PENDING figure. **PASS and
  FAIL do not move with it**, and an unreadable history is a PENDING reason,
  not a FAIL. `reconcile.json` keeps `official_eod` (the figure or the reason,
  and the points read) and `snapshot`. `scores.csv` gains no column: it is
  append-only with a fixed header that other code reads by name, and its
  `alpaca_equity_change_usd` is the snapshot.
- **The series of record** is `<state>/eod_equity.csv`, written by the collector's
  step `eod_equity`. **A contract**: another branch and a HALVE/KILL monitor
  read it by name. Columns are `date` (ISO session date, ET), `equity` (USD),
  `change_usd` (equity minus the previous session's row; empty for the first
  funded session and wherever the previous session is missing, never an
  invented baseline), then `read_at_utc`. Each write rewrites every funded
  session from 2026-09-28, atomically. So the first run after install
  backfills on its own. A changed value is rewritten, with a
  `DATA EOD_REVISED <date> equity <old> -> <new>` line in `data.log` and a
  report flag.
- **When the collector reads it**: every 30-minute slot until D's point is in
  the file and stamped before the read, then not again until the next data
  day, whose read re-checks every earlier day. Until D's point lands the day
  reads `INCOMPLETE eod_equity`, as it reads `INCOMPLETE prices_nav` until
  the evening NAVs arrive.

## As built (2026-10-13): the stale-NAV gate, in `report` mode first

**The defect.** Yahoo serves a NAV row dated D that still carries an older NAV, and
corrects it later. Gate 5 and `fetch_daily --require-asof` check the row's date, so
they pass it. On the laptop's paper sessions 28 of 73 checkable name-days were
decided on NAV(D−1), and 11 submitted orders were sized on one
(`results/cef/LIVE_NAV_QUALITY_2026-10-12.md` §5, `docs/REFERENCES.md` §12n).

**The rule (team lead, 2026-10-13, redesigned the same day).** The first version
("Use CEFConnect, else drop") was replayed. CEFConnect had no row for D at every
measured evening decide, so it would have dropped every suspect name, and on
2026-10-05 the drops would have flattened the whole book (`docs/REFERENCES.md` §12s).
The rule now:

- **Trigger.** The panel's NAV(D) equals, to the cent, its previous NAV row, **or**
  CEFConnect's NAV for D−1 (the previous NYSE day) when CEFConnect has that row. The
  second catches the reviewer's PDI case: 09-25 was captured as 15.06 against a 09-24
  row of 15.12, which was itself Yahoo's stale copy. 15.06 is CEFConnect's 09-24 NAV;
  the true 09-25 NAV is 15.10.
- **Resolution.** CEFConnect has D and it differs by more than half a cent: its value
  replaces the panel row through fetch_daily's logged fallback (`nav_fallback_log.csv`,
  source `cefconnect_stale_copy`). CEFConnect has D and it agrees: the row is kept.
- **Unverified** (no row for D, or an error, which is named). Never dropped.
  - Before the **final check**, the decide is **deferred**. The final check is the
    session's calendar close minus 90 minutes, on the session date: 14:30 ET, or 11:30 ET
    on a 13:00 close.
  - From the final check, a name still unverified **keeps its current shares**: no
    order in it. It leaves the cross-section and is never targeted to zero.
  - If the holds leave fewer than `min_names` eligible names, the **whole book holds**
    for the day: no order at all. The holds never trigger the sleeve's FLAT-everything
    `min_names` rule.

**Where it sits.**

- `quantt/session/nav_gate.py` runs as step 1b of `quantt/session/run.py`, after the
  refresh and before anything reads the panel. It reads CEFConnect once per deployed
  name, for D−1 and D together (`fetch_daily._cefconnect_navs`). In `on` mode it holds
  fetch_daily's panel lock from its read to its write.
- Holds reach the sleeve as `extras["nav_hold"] = {"asof", "names"}`
  (`src/deploy/sleeves/cef_discount.py` `_nav_hold`). Held names stay out of the band
  and the sleeve's gross cap, because their shares are fixed. Their gross is judged with
  the rest of the book by gate 8 and the send-time fit.
- With the extra absent, the sleeve's targets are byte-identical to the code before the
  gate: 56 panel dates, flat and held books.
- After the sleeve has read the panel, `PanelGate.still_holds` checks that it read the
  panel the gate certified, or the session FAILs.

**The deferral and the order path** (`run.py` docstring, "DEFERRAL AND THE ORDER
PATH"). A deferral is a gate-5 `data` refusal at DECIDE that names the names. Nothing
else was built for it.

- **One plan per day.** A refused plan is not `decided`: no `DECIDED` marker is written,
  and the next run overwrites plan.json. The morning backstop's slots (06:00–15:15 ET)
  re-run refresh and gate, and re-read CEFConnect. The first slot that verifies every
  name decides. If none does, the first slot at or after the final check decides,
  holding what is still unverified. A decided plan is never re-decided.
- **STARTED and idempotency (rule 2).** Untouched. A deferral happens before any order,
  and `done_reason` and gate 6 still stop a second set.
- **Approval.** A refused plan cannot be approved or sent: `approve` and the send both
  need a decided plan. APPROVED and `--approve` bind to the morning plan's `plan_sha`.
  AUTO_ARMED sends whatever is decided, as now.
- **Dry run.** A deferral is REFUSED, never DRY, so it can never write `DRY_DONE` and
  leave the morning slots idle.
- **Late-market send (rule 3, the paper exception).** The window is unchanged. The final
  check sits 82 minutes before it opens, and the 15:00 slot is left to retry a final
  decide that failed. In `cls` mode the morning slots decide and send before the cls
  cutoff.
- **Verify.** A day still deferred at the send reads `MISSED: ... [data] stale-NAV gate:
  ... deferred`: a FAIL, never a PASS.

**Modes** (`ops/books/cef_discount_book.json`, `"data": {"stale_nav": <mode>}`; absent
means off, and the session runs exactly as before):

- `report` **(the release setting)** records every check and what `on` *would* do:
  replace, keep, defer or hold. It changes nothing.
  - The orders, the `plan_sha` and plan.json are those of a gate-off session apart from
    the added `nav_gate`. This is proved on the live spec, the real sleeve and the real
    panel (`quantt/session/tests/test_nav_gate.py`).
  - An error is recorded as UNMEASURED and never stops the session.
- `on` applies the rule. Team lead: `on` after a measured week of `report`. Turning it
  on is a reviewed edit of that key, and so is the revert (delete the `data` block).

**Records (H14).** These are measured at run time and never keyed on a document.

- `plan.json` and the run record carry `nav_gate`: the mode, whether this was the final
  check, `would_defer` and `deferred`. For every deployed name they give the panel
  NAV(D), its previous row, CEFConnect's D−1 and D or the error, the trigger, the
  verdict and the action.
- `<state>/nav_gate.csv` gets one row per triggered name per decide, or one
  `no_trigger` row.
- **Record first** (2026-10-14). Under `on` that row is written *before* the panel.
  If it cannot be written, the panel is not touched and the session stops, naming
  the file.
- **A bad record file.** An empty `nav_gate.csv` or `cefconnect_arrival.csv`, or one
  with another header, is moved aside whole as `<name>.<UTC stamp>.unreadable`,
  never written into. For `nav_gate.csv` that run is UNMEASURED in `report` mode and
  stopped under `on`. The collector names both files in its detail and starts a new
  file in the same slot.
- The session log prints one `NAV GATE` line, plus one line per triggered name.

**The collector.**

- A panel NAV(D) equal to its previous NAV while CEFConnect has no row for D is a flag,
  `nav_repeat_unverified`, not a gap.
- A new watch step, `cefconnect_arrival`, polls CEFConnect each slot until every
  deployed name's row for D has appeared. It logs each row's arrival, bracketed between
  the last poll without it and the first with it, to `<state>/cefconnect_arrival.csv`.
- It keeps the collector from idling but never makes the day INCOMPLETE. Why: when
  CEFConnect publishes D decides how often a name is held, and that rests on three
  readings.

**The replay, under `on`** (report only: `python3 scripts/data/nav_gate_replay.py
--state-dir <laptop state>`; tables in `results/cef/nav_gate_replay/`; sources in
`docs/REFERENCES.md` §12s).

- **Every measured evening deferred.** All five laptop evening decides whose CEFConnect
  state the collector measured would have deferred to the morning.
- **At the final check, best case** (CEFConnect has D by then): nothing is held, stale
  copies are replaced and genuine repeats kept. That is what the one decide made with
  CEFConnect present would have done: 2026-10-01, 12:00 ET, 5 replaced and 3 kept.
- **At the final check, worst case** (CEFConnect still has no row for D): every
  triggered name keeps its shares.
  - 2026-10-05: 9 names held, 4 left eligible, so the whole book holds that day.
  - 2026-09-30 and 2026-10-02: the same is possible.
- **No date flattens the book.**
- On the local panel as captured on 2026-09-28, the second trigger catches PDI and
  replaces it with 15.10. DSL (11.11 = 11.11) is replaced with 11.10, and BIT is a
  genuine repeat.

## As built (2026-10-13): the re-fit keeps the most that fits; a send it empties is MISSED

The two non-blocking follow-ups of the 2026-10-11 release-check of
`release-20261011-1`. Neither changes a limit, a gate or what counts as a fit.

**B. The re-fit cut far more than it needed** (the execution desk's finding).
`run.fit_to_buying_power` searched its four factors on a 0.05 grid refined on
0.01, ranked first by the post-trade net's distance from the full plan's rounded
to the cent. A grid almost never lands on exact neutrality, so it took whichever
grid point came a few dollars closer, whatever that cost in trade. On the laptop's
recorded 2026-10-07 plan sent on equity 0.5% lower (the reviewer's case, a
hypothetical dip), it kept **72.0%** of the traded notional. The same objectives,
in the same order (every limit; the post-trade net closest to the full plan's; then
the most traded), are now solved exactly: with every order wholly opening or wholly
reducing, every limit is linear in each factor, so the search is a linear program in
two variables (`run._fit_cuts`). Same case: **98.7%** in whole shares, $4.61 from
the full plan's net (the grid's was $4.98 off). Reproducer: `test_fit.py`
`test_the_2026_10_07_plan_after_a_half_percent_dip_keeps_what_fits`, which carries
that plan. It failed safe before (never above a limit, never a refusal, never the
wrong side), so this is uptime, not safety.

What did not change, and is tested (`quantt/session/tests/test_fit.py`, seeded
synthetic plans checked against the released fit, kept verbatim as a test
reference, and against scipy's linear program as an independent solver): every
fitted plan passes gate 8 term for term; each order stays wholly opening or wholly
reducing, on its side, no larger than the plan's, so no name ends past the plan or
flips; whole shares round the safe way (openings down, reductions up, capped);
the stress cap is read as the gate reads it; a plan that does not add gross is not
scaled for it. Measured 2026-10-13 on 2,400 synthetic draws (`test_fit._draw` on
seeds 20000–22399, both fits; 1,741 draws where the fit binds and something fits):
gate 8 refused none of the new fits, and the mean share kept rose from 48.3% to
60.0%. In 1,738 of the 1,741 the new fit kept at least as much as the grid. The
other 3 are the 2026-10-07 neutrality rule at work: buying power binds on a small
opening buy, and the new fit trims a large reduction by the same dollars to hold the
full plan's net. The grid was too coarse to do that (0.01 of a 5,773-share order is
58 shares), so it ended $74–$1,314 further from that net, and kept up to 0.37 points
more. The committed test allows exactly that exception, and only where each dollar
of trade given up buys at least a dollar of neutrality (to within one share per
order). **For the team lead:** that is the rule as written (net first, then trade);
say if trade should come first when the difference is that small.

Three details changed: `kept` (recorded as `bp_scale.factor` and
`bp_scale_at_send.kept`) is now the share the WHOLE-SHARE orders trade, not the
fractional plan's; the fit sums the post-trade gross in the gate's own order, so its
check and gate 8's agree to the last bit; and a `PRE-FLIGHT WARNING` that the send
would scale now says to what share. When only trading nothing fits (the book above
the cap, every order adding gross), the plan comes back empty, as the grid's did.

**A. A send the re-fit scaled to nothing read PASS.** With every order scaled to
zero, the send ends `NOTHING_TO_SEND` with no refusal, and verify read the day
"nothing left to send" and passed it. Under the team lead's 2026-10-09 rule
only `DRY_RUN`, arming or a halt explains a no-trade day, so verify now reads it as
`MISSED:` naming the limit (`verify._fit_emptied`): "the send-time fit to
max_gross_stress ... kept 0 of N order(s)". The same holds when every
order was skipped as unshortable at send (named order by order), and when the
DECIDE-time fit emptied the plan. `send.json` records `bp_scale_at_send` and
`plan.json` records `bp_scale` (`orders_in`, `orders_out`, `binding`) so verify can
tell an emptied plan from one with nothing to do; a `send.json` from before
2026-10-13 that ended `NOTHING_TO_SEND` is still `MISSED:`, saying it records no
reason.

**Left for the team lead.** A send the re-fit empties exits `NOTHING_TO_SEND`, which
writes `DONE`, so the 15:55 retry does not run, even though equity may have
recovered by then. A refusal at 15:52 leaves the retry free. Whether an emptied
send should leave the retry free too is a change to the run path, not made here.

## As built (2026-10-09, amended 2026-10-11): the stress cap, missed days FAIL, the pre-flight

**The incident.** On Friday 2026-10-09 the book did not trade. Gate 8 refused both
the 15:52 send and the 15:55 retry: "projected gross $182,154.75 > max_gross_stress
1.8 x equity $100,666.16". The plan had been decided at 22:00 ET on 2026-10-08,
sized at 1.7994× that evening's equity ($101,229.74), where the sleeve's cap
binds. Equity was 0.56% lower at 15:52, so the same plan was 1.8095× the live
equity. The plan took gross **down**, from $183,413.36 to $182,154.75 at the
as-of closes, and refusing it left the book at 1.83× at that close. The verify
line read `PASS ... no trade: refused at send`. Nobody saw it until the team lead
asked how Friday went. All figures are from the prod VM's `2026-10-09/plan.json`,
`send.json` and `runs/*-run.json`.

**The audit** (`python3 -m ops.replay_exposure <copy of the prod state>`, run
2026-10-09 on all 40 recorded runs, 38 replayable). The old rule passed 2026-10-07
by $168 and 2026-10-08 by $765, both only because equity rose between the
evening decide and the send. It refused 2026-10-09 by $956 at 15:52 and $702 at
15:55. On every day the cap binds, the old rule refused whenever equity fell
before 15:52. The new code refuses none of the 38 runs. The only other
refusals of this kind on record, 2026-10-06's 21 buying-power refusals, were
already fixed on 2026-10-07; the replay confirms the new code passes them too.

What changed (team lead's go, 2026-10-09):

- **The stress cap is judged on the lower of the equity the plan was sized on
  and live equity** (`gate.stress_breach`). The send reads the plan's own
  `equity`; a plan without one is refused, never assumed. *Amended 2026-10-11
  (team lead's ruling, after the release-check review).* As first built on
  2026-10-09 it read the sized equity alone, on the argument that the 0.043×
  between the cap 1.80 and the derived G_stress 1.843 absorbs the movement. Both
  reviewers showed that holds only for a fall of up to 1 − 1.8/1.843 = 2.34%:
  past that, a plan that ADDS gross could go out above 1.843× live equity, with
  only Reg T (2.0×) left to stop it. So a plan that adds gross is held to the cap
  on whichever equity is lower, and with `bp_shortfall = scale` (prod's setting)
  the send's re-fit scales it to fit rather than refusing it. 2026-10-09's plan
  took gross down, so it still passes. Buying power and the overnight Reg T and
  maintenance limits are checked on live numbers, unchanged.
- **A plan that does not add gross always passes the stress cap**, even when the
  book is above it. A ceiling stops the book adding past it; it must never block
  a plan that brings gross down.
- **The re-fit fits the stress cap too** (`fit_to_buying_power`). Scaling
  reductions for neutrality can leave more gross than the plan, so the cap is
  one of its limits, read as the gate reads it. **Whole shares round the safe
  way** (2026-10-11): opening orders down, reducing orders up (capped at the
  order), so the whole-share plan never holds more gross or needs more buying
  power than the fractional plan that passed. Until then every order was
  floored, and both release-check reviewers produced a fitted plan that gate 8
  refused on the very cap it was fitted to. The rounded plan is re-checked. **When nothing fits** (the book
  held now is already past a limit and no scaling fixes it), the plan is
  returned unscaled with the limit named, and the gate refuses it. Until now
  that case raised `TypeError` (`coarse[1]` on `None`): a FAIL with a traceback.
- **A missed day is a FAIL** (`verify.DELIBERATE_GATES`). A no-trade day is
  explained only by a human's choice: `DRY_RUN`, no arming, or a halt. Any other
  refusal, at decide or at send, gives a FAIL line beginning `MISSED:` (and since
  2026-10-13 so does a plan the re-fit or the shortable skip left with nothing to send). It
  exits 1, so it also shows in `systemctl --failed` on the VM, and orient and
  the status line show it red.
- **The evening pre-flight** (`run.preflight_send`). After a plan is decided,
  the decide re-runs the send's exposure path (re-fit, then gate 8) on an
  account whose equity is lower by the worst one-day loss of the book held now
  over the last 252 sessions. That book moves equity until 15:52. The result goes
  into `plan.json` (`preflight`) and the session log, as `PRE-FLIGHT ok`,
  `PRE-FLIGHT WARNING` or `PRE-FLIGHT UNMEASURED`. It decides nothing, and a
  pre-flight that cannot run never stops the plan being saved. Buying power is
  held at its decide-time value. On the book held into 2026-10-12 the worst day
  was $2,074.61 (2.06% of equity) on 2026-03-20, measured on the laptop's panel
  ending 2026-09-28.
- **Orient shows the newest plan** (`ops.prod_state`, `newest plan`): its date,
  status, order count, whether it was sent, and its pre-flight. A WARNING on an
  unsent plan is a PROD caution. Only counts and verdicts leave the VM, never
  positions.

**Left as it was, for the team lead.** The overnight margin checks still refuse
a plan that leaves the book past Reg T even when the plan reduces gross. That
needs equity to fall about 8.5% with gross unchanged (the book was 1.83× at the
2026-10-09 close: equity.csv). The principle above says such a
plan should go. The team lead kept those checks unchanged on 2026-10-09, so the
question is open.

## As built (2026-10-07): buying power, scale-to-fit, fills, TCA

Execution-desk review after the first week (plan: items 3–5).
- **Gate 8 is two checks.** Order-time: opening notional (shorts ×1.03) ≤ Alpaca's
  live `buying_power` -- what Alpaca enforces. Overnight: on the book AFTER the
  plan, Reg T initial margin (50% of gross) ≤ equity, and maintenance at the
  account's live measured ratio (`maintenance_margin / current gross`, 47.8% on
  2026-10-06) ≤ equity. The old `min(buying_power, regt_buying_power)` refused
  2026-10-06's catch-up plan that Alpaca would have accepted.
- **`execution.bp_shortfall = scale`** (absent = refuse): a plan that does not fit
  is scaled with four factors (opening/reducing × buy/sell) that satisfy every
  limit and keep the post-trade net closest to the full plan's, at DECIDE and again
  at SEND on the live account. What goes is always a subset of the decided plan.
  (Searched on a grid until 2026-10-13, solved exactly since: see "As built
  (2026-10-13)".)
- **Fills are polled** to a final state (to close − 30 s) and recorded in
  `orders.jsonl` / `send.json`; unfilled shares are reported, never topped up.
- **`<state>/tca.csv`**, one row per traded day: fill rate, signed slippage vs the
  official close (buy/sell), residual vs the sent orders' targets.
  `scripts/ops/tca_backfill.py` scores past days read-only.
- Slower rebalancing was re-tested (`results/cef/FRONTIER_REPRO_2026-10-07.md`):
  no slower policy matches or beats the live band on the fit period; no trial spent.

## As built (2026-09-29): evening decision, morning backstop, nightly data

Team lead, 2026-09-29: *"we dont have to do it at 830 why have it a hard time -
should be flexible"*. The 08:30 run of that morning died on a DNS failure as the
laptop woke. What changed:

- **The session date is the auction an order sent now would join**
  (`run.session_for`): today before today's cutoff, else the next trading day.
  Both calendars must agree. `<D>` in every record is that auction's date.
- **Gate 4 and the per-POST check use one window** (`gate.in_send_window`): the
  as-of evening, 19:15 ET to 01:00 ET the next day, and the session day itself,
  00:00 ET to the cutoff. Not the daytime of a weekend or holiday in between:
  Alpaca documents no `cls` routing for those hours [U] (review 2026-09-29).
- **Known limit, kept deliberately:** `STARTED` is written before the first POST
  and blocks every later slot for that auction (CLAUDE.md rule 2). So if every
  evening order is rejected, or the clock read fails before the first POST, the
  morning backstop does not retry; the day is FAIL and the team lead decides
  (as for a `cls` rejection, 2026-09-28). Whether paper accepts an evening `cls`
  is [U] until the first evening send, which is watched live.
- **Nightly collector checks against an independent source:** it runs
  `fetch_daily` without the CEFConnect fallback, so its NAV cross-check compares
  yfinance (what is traded) against CEFConnect. The distributions script now
  writes nothing if any ticker fails, rather than dropping that ticker's
  history; transient print errors are retried, not recorded as gaps (review
  2026-09-29).
- **`--scheduled`** (launchd fires it every 30 minutes, every day): tries only
  in the evening slot (22:00 on the as-of date to 01:00) or the morning slot
  (06:00–15:15 on the session date), and only while the session is not done.
  Otherwise it prints one `IDLE` line and exits **5** with no record. A local-clock
  pre-check skips obviously-idle firings without calling Alpaca; it never permits
  one. Done means `STARTED`, `DONE` (a scheduled SENT or NOTHING_TO_SEND), or
  `DRY_DONE` (a scheduled DRY, honoured only while `DRY_RUN` is not `"0"`, so
  arming lets the next slot trade). REFUSED and FAIL leave the next slot free.
- **The refresh timeout is capped at 25 minutes**, so a hung fetch cannot hold
  the job past the next slot (launchd never runs two instances of one job).
- **Gate 6 reads orders from midnight before the as-of date**, so a Friday
  evening set is in view on Monday morning.
- **Verify** treats the next auction's runner orders as the runner's, not foreign.
- **Nightly data collector** (`quantt.collect`, launchd every 30 minutes at :10
  and :40): prices and NAVs, Alpaca's official closes, cross-checks between
  sources (**report only**, team lead 2026-09-29), an account snapshot and the
  distribution/split panels. Read-only at Alpaca. `docs/DATA.md`.
- **Shadow benchmark** (`quantt/session/shadow.py`, run by verify after the
  verdict, never able to change it): the runner's intended book, as if every
  order filled at the official closing print, marked close to close. One row per
  day in `<state>/shadow.csv`, labelled MODELLED; its state is
  `<state>/shadow_book.json`. Why: on 2026-09-29 paper filled 2 of 13 `cls`
  orders (PHK 4,019/4,019, PFN 1,529/2,227; eleven expired) although every NYSE
  auction printed more shares than we asked for; Alpaca staff confirm paper treats
  `cls` as a market order at the close with random partial fills (forum,
  2026-06-24).
