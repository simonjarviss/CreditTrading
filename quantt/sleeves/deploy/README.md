# The events book on the VM: install and operate

**Paper only. Never run against a broker yet** (see Known gaps). The installer never arms.

## What it is

`quantt/sleeves/` trades several shadow books' decisions in ONE Alpaca paper account, "the
events book". The books, their capital and every limit are in the release-tagged
`ops/sleeves/events_sleeves.json`. Each trading day it runs three phases
(`quantt/sleeves/run.py`):

- **PLAN** reads each listed book's decision file for the previous session, nets them into one
  order per symbol and writes `<state>/<day>/plan.json`. It sends nothing.
- **SEND** sends the saved plan as market `day` orders 20 to 2 minutes before the close, if
  every gate passes (the paper exception, `docs/RUNNER.md` "Paper execution").
- **VERIFY** reconciles the orders and fills, books them into `ledger.json` (which sleeve owns
  which shares) and appends one score row per sleeve.

It runs as user `quantt` from the **prod clone at its release tag**. The shadow clone supplies
decision files only.

## Prerequisites (team lead, by hand)

1. Create a **new Alpaca paper account with $1,000,000** for this book (team lead, 2026-11-16).
   A new account starts at $100,000 by default; Alpaca's paper-trading page says the balance
   can be set to an arbitrary amount (`docs/REFERENCES.md` 12pa). No other book shares it.
2. Put its two keys in the vault as secrets `alpaca-events-key-id` and
   `alpaca-events-secret-key`. The VM's identity must be allowed to read them.
3. Release a tag that contains `quantt/sleeves/` and `ops/sleeves/events_sleeves.json`, and
   install prod at it (`docs/RUNBOOK.md` section 8). Confirm the limits in the book file first.
4. The shadow runner must have run every listed book at least once.

## Install

Outside 12:30–13:00 and 15:30–16:00 New York, on the VM:
`sudo sh /home/quantt/prod/quantt-alpaca/quantt/sleeves/deploy/install_events_vm.sh --vault <vault-name>`

What it does, in order. It stops at the first check that fails and prints why.

1. Checks: root, New York zone, no events job running, both users exist, `setfacl` present, no
   systemd drop-in for an events unit.
2. Refuses unless the prod clone is a clean checkout of a `release-*` tag holding the runner
   and the book file; reads the slugs from that file with the runner's own loader.
3. Refuses if `<state>/ledger.json` exists, unless `--keep-state`.
4. Grants `quantt` a read-only ACL on `<shadow state>/<slug>/decisions/` for those slugs, and
   pass-through only on the directories above. Then tests it as `quantt` (can read, cannot
   write, cannot list the shadow state) and as `quantt-shadow` (cannot reach the events state).
5. Creates `/home/quantt/quantt_state/events` (0700).
6. Writes `quantt-events-secret.service` and a service and timer each for plan, send and
   verify, all with `DRY_RUN=1`, and enables the timers.
7. Prints the timers and the next steps.

Re-running is safe and **sets DRY_RUN back to 1**. It touches nothing of the core book's or
C4's. `... install_events_vm.sh uninstall` removes the timers, units and ACL and leaves the
state directory alone. **If `shadow/deploy/install_shadow_vm.sh` is re-run, re-run this
installer afterwards**: its `chmod 700` on the shadow state masks the ACL, and PLAN refuses.

## Schedule (New York, Monday to Friday)

| phase | times | note |
|---|---|---|
| PLAN | 09:45, then every 30 minutes to 12:15, and 15:20 | A decision counts only if written before 09:30, so the first run is the plan; later runs retry a failure and may re-size it. |
| SEND | 15:41, 15:46 (12:41, 12:46 on a 13:00 close) | A send needs 3 s an order plus 42 s before the window ends. |
| VERIFY | 17:35 | |

The 12:41 and 12:46 sends on a normal day are before the window: they write nothing and exit
5 IDLE. Expected REFUSED lines: the 15:46 send after the 15:41 one has started, and the 15:20
plan and 15:4x sends on a 13:00 close. A re-plan that changes sizes
changes `plan_sha`, which voids an approval already given.

## First-day checklist
Manual runs use `run_events.sh`, which always sets `DRY_RUN=1` and refuses a bare `send`.

1. `sudo systemctl start quantt-events-secret.service`, then read
   `<state>/logs/secret.out.log`: it names the two variables, never a value.
2. Before 15:40: `sudo sh .../deploy/run_events.sh plan --preview`. Read the **sleeve table**
   (every sleeve has a decision or a stated reason for none) and the **order table** (count,
   sizes, the IWM short, any `WOULD REFUSE AT SEND` line).
3. Check the account is empty and `ledger.json` is absent (after dry days it exists and must
   show no shares). With positions and no ledger the runner refuses.
4. Arm, in the order the installer prints: `DRY_RUN=0` in the send unit only; approve the first
   day's plan by its sha; create `AUTO_ARMED` only after that day's VERIFY PASSes.

## Exit codes
| code | phase | meaning for the operator |
|---|---|---|
| 0 SENT | send | Orders went. Read VERIFY at 17:35. |
| 0 PASS / 1 FAIL | verify | See "When VERIFY FAILs". |
| 3 NOTHING_TO_SEND | send | The plan held no order. Normal. |
| 4 PREVIEW | plan, send, approve | Printed only; nothing written or sent. |
| 5 IDLE | plan, send | Not a trading day, or a send before the window. Nothing written. |
| 6 PLANNED | plan | `plan.json` written. |
| 10 DRY | send | Stopped only by `DRY_RUN` or missing approval. Normal until armed. |
| 11 REFUSED | plan, send | A gate or check said no; the line names it. Nothing was sent. Read it unless it is one of the expected ones above. |
| 20 FAIL | any | An error, with a traceback, or a send that ended part-way. Read the log at once. |

Logs: `<state>/logs/{plan,send,verify,secret}.{out,err}.log`. `systemctl --failed` shows 11, 20
and a VERIFY FAIL.

## Halting
`sudo -u quantt sh -c 'echo "why" > /home/quantt/quantt_state/events/HALT'`. No send starts while the file exists. It cancels nothing already at Alpaca, and PLAN and VERIFY
still run. Remove the file to resume. `ops/HALT.md` in the prod clone halts every book. To
disarm as well: set `DRY_RUN=1` back in the send unit, remove `AUTO_ARMED` and any unsent day's
`APPROVED`.

## When VERIFY FAILs
The book stops: VERIFY writes no ledger for that session, and PLAN refuses until every earlier
session is booked. In order:
1. Write the HALT file.
2. Read `<state>/<day>/verify.json` (`problems`, `fails`) and `logs/verify.out.log`.
3. If the cause has passed (an order not yet final, a broker read that failed), run
   `run_events.sh verify --date <day>`.
4. If the ledger really is wrong (a foreign order, a position the fills do not explain), it
   must be repaired by a person against the broker's positions and fills. **Never edit
   `ledger.json` without reading `verify.json` first**, and keep a copy of the file you change.

## Promotion and the ladder

The rules are the team lead's (2026-11-18, `docs/SYSTEM.md` section 5). `quantt/sleeves/promote.py`
counts the sessions and says which edit of the book file is due. It is read-only: it sends
nothing, writes nothing and imports no broker client. Its docstring defines every term.

- **Promotion.** A shadow book may become a sleeve after **ten clean on-time shadow sessions in a
  row**. A session is one row of the book's `scores.csv`. It is clean when its status is SCORED or
  FLAT and the decision that fills on it was written before 13:00 New York that day. A flat day
  with an on-time decision counts; a flat day with no decision file does not (team lead,
  2026-11-18: "Any on-time day, ten in a row").
- **The ladder**, counted in sessions on which the sleeve held a position (`n_names` > 0 in
  `sleeve_scores.csv`): under 20 a quarter of `full_capital_usd`; 20 to 59 a half if fills track
  the shadow book; from 60 full, a half or stopped by live P&L against -1 and -2 sigma x sqrt(T).
- **Fills track** (team lead, 2026-11-18: "Paper within 2x modelled gap"): pass if the shadow
  book's P&L less the sleeve's paper P&L, over the sessions from the sleeve's first position
  on, is no more than 2 x `modelled_fill_cost_bp` x the dollars the sleeve traded on them
  (its `bookings` in each session's `verify.json`).
- **Sigma** (team lead, 2026-11-18: "Each sleeve's backtest vol"): `backtest_vol_annual` /
  sqrt(252), scaled to the capital the sleeve traded at on each position session.
- **In the book file**, `capital_usd` is the current stage and the only size the runner trades.
  `full_capital_usd`, `family`, `backtest_vol_annual` and the optional `modelled_fill_cost_bp`
  describe the sleeve and size nothing. Stopped is `"enabled": false`, which flattens the sleeve.

The routine:

1. On the VM, as a user who can read both state directories:
   `python3 -m quantt.sleeves.promote --shadow-state <shadow state> --events-state <events state>`
   (`--json` for a program; `--book-file` to check a proposed file before it is merged).
2. Read the exit code: **0** every sleeve agrees with the rules; **30** an edit is due, printed
   as one line a sleeve; **31** a verdict is UNMEASURED, with the path or the rule that is
   missing (edits that are due are still printed); **32** refused: the book file cannot be
   loaded, or a `capital_usd` is not `full_capital_usd` x a quarter, a half or one.
3. Open a PR that edits **only** `ops/sleeves/events_sleeves.json`: the `capital_usd` or `enabled`
   line the report printed, and the pinned figures in
   `quantt/sleeves/tests/test_run.py::test_the_released_book_file_loads_and_every_slug_is_a_shadow_book`.
   Paste the report into the PR. If the stage raises the shared IWM hedge above `max_name_usd`,
   that limit is the team lead's to change in the same PR (`_note_max_name_usd`).
4. The team lead merges, tags a release and installs it (`docs/RUNBOOK.md` section 8). The
   runner reads the file from the tagged prod clone, so **nothing changes until the release**:
   a new size, a new sleeve and a removed sleeve all need one. A new sleeve also needs this
   installer re-run, which grants the read ACL on its decisions and sets `DRY_RUN` back to 1.
5. To add a shadow book the report shows as eligible: add its entry (`slug`, `family`,
   `full_capital_usd`, `capital_usd` at a quarter, `enabled`) in the same kind of PR. Its full
   size and whether it joins at all are the team lead's rulings, not the report's.

What the two ladder tests read, since 2026-11-19 (team lead: the capital column "Yes, add it
now"; the cost "Card figures where measured, 15bp elsewhere"; netted trades "No, only real fills"):

- **The capital a sleeve traded at** is the `capital_usd` column of `sleeve_scores.csv`: the
  capital PLAN sized that sleeve's targets from, written into `plan.json` inside `record_sha`
  and copied to the score row by VERIFY. It is never re-read from the book file. An empty cell
  (a sleeve the plan did not list) makes the verdict UNMEASURED, naming the dates.
- **Fills track (20 to 59 position sessions).** Shortfall = the shadow book's P&L put in the
  sleeve's dollars (each session's shadow P&L x the capital carried into it / the shadow
  notional) less the sleeve's paper P&L, from its first position session. Allowance = 2 x
  `modelled_fill_cost_bp` / 10,000 x the dollars the sleeve FILLED IN THE MARKET on those
  sessions (`verify.json` bookings of kind `fill`; a cross netted inside the account pays no
  spread and earns nothing). PASS means a half, FAIL a quarter.
- **Sigma (from 60).** `backtest_vol_annual` / sqrt(252) x the root of the summed squares of the
  position sessions' capital. Live P&L above -1 of that is full size, between -1 and -2 a half,
  below -2 the edit `"enabled": false`, which flattens the sleeve.
- **`modelled_fill_cost_bp` is set for all seven sleeves**; the book file's
  `_note_modelled_fill_cost_bp` says which two are measured (the special-dividend books, from
  their card's closing spreads) and that 15bp for the other five is an assumption to be replaced
  by what paper fills show. What each card says:

  | sleeve | what its card says | where |
  |---|---|---|
  | `cef_exdate_after`, `cef_exdate_before_after` | No measured cost. The edge of 20 to 30bp per fund per leg is called "the same order as a round trip through a closed-end fund's spread": an order of magnitude, 10 to 15bp a side if read literally [U] | `results/ideas/2026-11-10_cef_exdate_drift.md`, "What the gross figure does not show" |
  | `units_exdate_after`, `units_exdate_before_after` | Nothing: "gross, no cost and no borrow modelled", and no spread is quoted | `results/ideas/2026-11-11_exdate_other_wrappers.md` |
  | `specdiv_wait_small` | Measured quoted spread at the entry close for its band ($100k to $5M a day): median 0.27%, 90th percentile 1.25%. Half the median spread is 13.5bp a side [S] | `results/ideas/2026-11-15_special_dividends.md`, "The spread, measured" |
  | `specdiv_wait` | The same table by band: median spread 0.14% at $1M to $5M a day and 0.05% at $5M and over (7bp and 2.5bp a side). No row for this book's own universe ($500k a day and over) [S] | the same section |
  | `pead_small_long` | No measured cost. The real-money grid of 5 / 15 / 30bp per unit traded, and "what these stocks cost to trade at the close is not measured" [S] | `results/ideas/2026-11-15_pead_small.md`, "Real-money view" |

**Still open:** nothing in the report is UNMEASURED by design any more. It will read UNMEASURED
when an input is missing (no `sleeve_scores.csv`, a session without a booked `verify.json`, a
shadow decision with no notional, an empty capital cell), and it names the file or date. A new
sleeve added without a `modelled_fill_cost_bp` is UNMEASURED at 20 sessions until one is ruled.

## Known gaps
- **Never run against a broker.** Every test uses a fake client. `main` and `default_deps`
  (the command line, the real client, the key file) are untested.
- **A first session sends up to about 230 orders.** Only the 15:41 send fits them; the 15:46
  retry fits about 226 at most. If the key fetch is slow at 15:41 the day may be REFUSED.
- Unmeasured or unobserved: this runner's memory on the 1 GiB VM (its send overlaps the
  core's); whether a dry day's VERIFY reads PASS; `ReadOnlyPaths=` on the clone in these units.
