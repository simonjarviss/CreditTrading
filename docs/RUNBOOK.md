# Runbook: the Alpaca prod on this laptop

**What this covers:** how to release, install, arm, disarm, read a day's verdict,
and respond to a FAIL, for the CEF book on Alpaca paper. It also covers keeping
the laptop awake and moving to a VM later. The design is `docs/RUNNER.md`; the plan
is `docs/ROADMAP.md` phases 4 to 6. This file holds no figures about the book:
`python3 -m ops.orient` measures those.

**Who does what.** **TL** = the team lead. **A** = an agent. Anything that
needs `sudo`, a credential or a broker order is a TL action. An agent in a chat
transmits nothing without the TL's go on a concrete order list (`CLAUDE.md`
order-path rule 1). After the first go, the scheduled runner trades on its own,
behind the gates (`docs/RUNNER.md`).

## What prod is

Prod runs on this laptop until a VM exists (TL, 2026-09-28). It holds this
repository at a release tag and nothing else (`docs/ROADMAP.md` phase 6).

| thing | where | made by |
|---|---|---|
| code | `~/prod/quantt-alpaca`: a `git clone` of `origin`, **detached at the tag** | `install_prod` |
| price/NAV panels | `~/prod/quantt-alpaca/data/cef/cef_prices.parquet`, `cef_nav.parquet`. Copied once from the dev tree, then prod's own. | `install_prod` seeds them; `fetch_daily` appends to them |
| runtime records (`QUANTT_STATE_DIR`) | `~/quantt_state/cef/`: `<date>/STARTED`, `verify.log`, `AUTO_ARMED` | `quantt.session` (and the TL for `AUTO_ARMED`) |
| job logs | `~/quantt_state/cef/logs/{session,verify,collect}.{out,err}.log` | launchd |
| schedule | `~/Library/LaunchAgents/com.quantt.alpaca.cef.session.plist` (every 30 min at :00/:30, every day, `--scheduled`: the runner tries only 22:00–01:00 ET after the as-of close and 06:00–15:15 ET on the session date), `...cef.verify.plist` (17:30 ET, Mon–Fri) and `...cef.collect.plist` (every 30 min at :10/:40, every day) | `install_prod`, rendered from the tag's templates |
| Alpaca keys (`QUANTT_ENV_FILE`) | a file **outside** the prod clone, mode 600 | TL only. `install_prod` checks it exists and is private, and never reads it. |

**Never touch** the retired IBKR prod: `~/prod/QUANTT` and the old
`~/Library/LaunchAgents/com.quantt.*.plist` files that do not contain `alpaca`.
Retiring them is `docs/ROADMAP.md` 6.6 (TL decides, A runs). The installer
refuses a layout that overlaps `~/prod/QUANTT`, and it writes only the two
`com.quantt.alpaca.*` files.

## 0. One-time preconditions (TL)

1. **Timezone.** launchd schedules run on local wall-clock time, and the plists
   are written in US/Eastern. **Measured 2026-09-28:** this Mac is set to
   `America/Toronto`, not `America/New_York`. The installer refuses that unless
   you choose one of these:
   - set the system zone: `sudo systemsetup -settimezone America/New_York`
     (then `readlink /etc/localtime` should end in `America/New_York`), **or**
   - pass `--accept-timezone America/Toronto` to the installer. It is honoured
     only if Toronto's UTC offset equals New York's at every hour of the next
     two years, checked against this machine's tz database at install time.
2. **Key file.** Put the Alpaca paper keys (`ALPACA_CEF_KEY_ID`,
   `ALPACA_CEF_SECRET_KEY`) in a file outside the prod clone and outside
   `~/Desktop`, `~/Documents` and `~/Downloads`, then run `chmod 600 <file>`.
   Those three folders are macOS privacy-protected. The 2026-07-31 IBKR job
   died under launchd with `getcwd: Operation not permitted` (exit 126) when it
   touched one (`ops/halt.py` docstring). This dev repo is under `~/Downloads`,
   so its `config/.env` is at risk. Whether this interpreter can read there
   under launchd **has not been measured**. The installer warns rather than
   refuses, and step 3.2 below proves it either way. A suggested location is
   `~/.config/quantt/alpaca.env`. Agents never read, copy or move this file.
3. **Python.** The jobs run the interpreter the installer ran under (on
   2026-09-28 that was `/opt/anaconda3/bin/python3`, Python 3.13.5), with
   `requirements.txt` installed in it. Step 2.3 (the test suite in the prod
   clone) proves the dependencies are there.
4. **Awake in the evening (22:00–01:00 ET) or the morning (06:00–15:15 ET).** See section 7.

## 1. Release (A, with TL approval to push)

A release is an annotated tag on a commit whose suite is green. The repo's tag
names follow `release-YYYYMMDD-N`, for example `release-20261007-2`.
(Corrected 2026-10-08: this section said `vYYYY.MM.DD.N`, but every release
tag actually cut, `git tag -l 'release-*'`, uses `release-YYYYMMDD-N`.)

```bash
cd "<dev repo>"
python3 -m pytest                    # green; never quote a count
python3 -m ops.doc_audit --check
git tag -a release-20261007-2 -m "Alpaca runner: <one line>"
git push origin release-20261007-2   # the installer refuses a tag that is not on origin
```

Which branch the tag sits on (`alpaca-runner` or `main` after a merge) is the
TL's call. A tag is never moved after release. The installer refuses when
the dev repo's tag and origin's tag name different commits.

## 2. Install or update (A runs, TL approves `--load`)

```bash
cd "<dev repo>"
# 2.1 dry run: every check, then the exact steps and both rendered plists. Writes nothing.
python3 -m quantt.deploy.install_prod --tag release-20261007-2 --env-file ~/.config/quantt/alpaca.env
#       (add --accept-timezone America/Toronto if section 0.1 chose that)

# 2.2 apply: clone/fetch, checkout the tag detached, seed panels if absent,
#     make the state dir, write the plists with DRY_RUN=1. Does NOT load them.
python3 -m quantt.deploy.install_prod --tag release-20261007-2 --env-file ~/.config/quantt/alpaca.env --apply
```

2.3 **Prove the prod clone before scheduling it** (`docs/ROADMAP.md` 6.3). Use
the same interpreter:

```bash
cd ~/prod/quantt-alpaca
python3 -m pytest
python3 -m ops.doc_audit --check
python3 -m ops.orient
```

All three must be clean before 2.4.

2.4 **Load the jobs** (TL approves): re-run with `--apply --load`. This runs
`launchctl bootstrap gui/<uid>` for both plists, and boots out first any job
that is already loaded. Check both are loaded:

```bash
launchctl print gui/$(id -u)/com.quantt.alpaca.cef.session | grep -E 'state|path'
launchctl print gui/$(id -u)/com.quantt.alpaca.cef.verify  | grep -E 'state|path'
```

**The installer refuses on any of these:**
- a timezone other than New York (section 0.1)
- a missing, relative or in-prod key file
- a tag that is not on origin, that moved, or that lacks `quantt/session/__main__.py`, the templates or the sleeve
- a template at the tag whose schedule, command or environment differs from the contract
- a prod clone with any local modification or untracked file
- a job that is loaded in launchd when its plist would change but `--load` was not given (launchd would keep running the old definition)

Each refusal names the problem. Fix the cause. Do not work around it.

**Updating** to a new release is the same: tag, dry run, `--apply --load`.
Prod's panels are never overwritten, because they hold rows the dev tree may
not have. **Rolling back** is an install of the previous tag.

## 3. First sessions: shadow, then arm

3.1 **Shadow (DRY_RUN=1).** After 2.4 the jobs run on schedule and send
nothing. `DRY_RUN` is `1` in both plists, and the runner transmits only when it
is exactly `0` (`docs/RUNNER.md` gate 1).

3.2 **Prove the launchd environment now, not at 08:30.** With DRY_RUN=1 still in
the plist:

```bash
launchctl kickstart gui/$(id -u)/com.quantt.alpaca.cef.session
tail -n 50 ~/quantt_state/cef/logs/session.err.log ~/quantt_state/cef/logs/session.out.log
```

This runs one dry session immediately: the data refresh, the decision and the
gates. Nothing is sent. If the key file cannot be read (section 0.2), a module
is missing, or the working directory is refused, it shows here.

3.3 **The first armed session (Tue 2026-09-29, `docs/RUNNER.md`).** This session
is interactive. The TL runs it by hand from the prod clone, with the same
environment the plist sets:

```bash
cd ~/prod/quantt-alpaca
export QUANTT_STATE_DIR=~/quantt_state/cef QUANTT_ENV_FILE=~/.config/quantt/alpaca.env
DRY_RUN=1 python3 -m quantt.session run --book cef     # shows the order list and its plan_sha
#   the TL reads the order list and says go, or does not
DRY_RUN=0 python3 -m quantt.session run --book cef --approve <plan_sha>
```

`--approve` sends only if the freshly recomputed order list hashes to the
approved `plan_sha` (gate 2). The exact flags and output belong to
`quantt/session`. Confirm them against its `--help` at the release tag before
the session.

3.4 **Arm the schedule** after the TL's first go:

```bash
touch ~/quantt_state/cef/AUTO_ARMED                    # TL: docs/RUNNER.md gate 2
cd "<dev repo>"
python3 -m quantt.deploy.install_prod --tag <same tag> --env-file ~/.config/quantt/alpaca.env --armed --apply --load
```

A scheduled transmit needs **both** `DRY_RUN=0` in the plist **and**
`AUTO_ARMED`. It also still needs every other gate to pass: halt, clock, data,
no set already headed for the auction, shortability, exposure and sanity.

## 4. Disarm or halt

Fastest first. Each step stops the next scheduled session. **None of them
cancels an order already at Alpaca.**

1. **Halt file** (seconds; survives reboots). The runner reads
   `ops.halt.read_halt("cef")` **from the prod clone**, so write the halt there.
   A halt written in the dev tree does not stop prod.
   ```bash
   cd ~/prod/quantt-alpaca
   python3 -c "from ops.halt import write_halt; write_halt('why', source='runbook', book='cef')"   # this book
   python3 -c "from ops.halt import write_halt; write_halt('why', source='runbook')"              # every book
   ```
   `write_halt` also tries a macOS banner, speech and email, but only the file
   stops trading. Clear the halt once the cause is fixed:
   `python3 -c "from ops.halt import clear_halt; clear_halt('what was fixed', book='cef')"`.
2. **Remove `AUTO_ARMED`**: `rm ~/quantt_state/cef/AUTO_ARMED`. Scheduled runs
   then fail gate 2.
3. **DRY_RUN=1**: re-install without `--armed`, with `--apply --load`. The
   installer refuses to change a loaded job's plist without `--load`, so the
   file and launchd cannot disagree.
4. **Unload the jobs**: `launchctl bootout gui/$(id -u)/com.quantt.alpaca.cef.session`
   (and `.verify`). Nothing runs at all, including verification.

**Cancelling an order already sent** is an order-path action: the TL only.
NYSE accepts no MOC cancel after 15:50 ET (`CLAUDE.md` order-path rule 3).

Note (corrected 2026-10-07): this note used to say that halt files are not
gitignored, so the installer sees them as local modifications and refuses to
update while they exist. That is no longer true. `.gitignore` now ignores
`/ops/HALT*.md`, `/ops/halts/` and `/ops/heartbeat.json`, and gives its reason
beside them, so a halt, standing or cleared, no longer makes the installer
refuse. What follows is the consequence open question 2 named: an update can
proceed while a halt stands. The halt still stops trading, because the runner
reads it at run time.

## 5. Check a day's verdict

```bash
tail -n 5 ~/quantt_state/cef/verify.log        # one line per trading day: PASS or FAIL + reason
ls ~/quantt_state/cef/$(date +%Y-%m-%d)/       # STARTED exists only if orders were sent
tail -n 50 ~/quantt_state/cef/logs/session.err.log ~/quantt_state/cef/logs/verify.err.log
launchctl print gui/$(id -u)/com.quantt.alpaca.cef.session | grep -E 'last exit|runs'
python3 -m quantt.broker.alpaca_probe --book cef   # read-only account snapshot (run from the dev repo)
```

**No line for a trading day counts as a FAIL.** Silence never counts as success
(`docs/ROADMAP.md` 4.7).

**A FAIL line beginning `MISSED:` is a day the book should have traded and did
not** (since 2026-10-09). A refusal explains a no-trade day only when a human
chose it: `DRY_RUN`, no arming, or a halt. Any other refusal is a miss, and the
line names the gate. Until 2026-10-09 such a day read `PASS ... no trade: refused`,
and that is how 2026-10-09 went unseen (`docs/RUNNER.md` "As built (2026-10-09)").

## 6. On FAIL

1. **If orders may be at risk, or the cause is unknown, halt first** (section
   4.1). A halt costs one session. An unexplained second set in the auction
   doubles the book (`CLAUDE.md` order-path rule 2).
2. Read the verdict line and the four logs (section 5). Take the account's truth from
   the broker, never a local file: run the read-only probe and compare it with
   the day's `STARTED` record.
3. **Never re-run `run` armed on the same day** to "retry". Never delete a
   `STARTED` file. Gate 6 exists because Alpaca does not dedupe
   `client_order_id` after an order closes.
4. Fix the cause in the dev repo, with a test that fails against the old
   behaviour. Then release a new tag and install it (sections 1–2). Never
   hand-edit prod.
5. Clear the halt with a note of what was fixed.

### 6.1 Corporate-action halt: a split or merger on a held name

**How it shows.** The verify line reads `MISSED: ... [data] corporate-action gate
(halt): <SYMBOL> (held) is the <role> in <type> <id> (...; long window ...)`.
The day's `plan.json` (or `send.json`, when the send refused) carries
`corporate_actions.blocking`, one row per event and name. A row holds the
event's id, type, market and process dates, its parties, the rule and the window
(`docs/RUNNER.md`, "As built (2026-10-28)").

**What clears each kind of halt** (the same table as `docs/RUNNER.md`):

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

A **short-window** row clears by itself after one session: a merger acquirer
or a reorganization's allocated leg (both judged on the market date only), or
any other match through the process date alone. Confirm the event (step 1) and let it
pass. A **long-window** row on a held name repeats every session until the steps
below are done. Alpaca paper processes no corporate actions, so the account still
holds the old count, or the old symbol (`docs/REFERENCES.md` §12pc).

1. **Confirm the event and its terms from a primary source.** Do not rely on the
   feed alone. Use the fund's press release, 8-K, N-14 or proxy on EDGAR, or the
   exchange's notice. Record:
   - the effective or ex-date;
   - the ratio: a split's old and new rates, or a merger's exchange ratio and any
     cash per share;
   - how fractional shares are settled (cash in lieu or rounding).

   When the filing and the feed disagree, report both and say which you used.
   Never average them (`CLAUDE.md`, data rules).
2. **Work out the true post-event count**, the count a broker that processes
   corporate actions would hold:
   - a split: paper qty × new_rate ÷ old_rate, then the issuer's rule for
     fractions. A 1:4 reverse split has old_rate 4 and new_rate 1, so the count
     falls to a quarter;
   - a stock dividend: the count × (1 + rate);
   - an acquiree in a stock merger: 0 shares of the old symbol, plus the count ×
     the exchange ratio in the acquirer, plus any cash;
   - an acquiree in a cash merger: 0 shares, plus cash;
   - a name change: the same count under the new symbol;
   - a spin-off: the same count of the source, plus the count × the distribution
     ratio in the new symbol.
3. **Orders go only through the team lead** (`CLAUDE.md` hard rule 1). A closing
   or rebalancing order to bring paper to the true count is an order-path action.
   Show the concrete order list, get an explicit go, and only then transmit:
   - whole shares only (landmine 3);
   - one netted order per symbol (landmine 2).

   The gate clears once the name's shares are set again after the event. That
   means a filled order in the name, submitted on the SECOND trading day after the
   event's latest date or later. An order submitted on the first trading day
   after is sized on the event's own close and does not clear it. The window
   starts at the trading day before the last fill's submission, the close it was
   sized on. Example (third review, 2026-10-29): a reverse split ex Wednesday
   10-07 and a corrective order submitted Thursday 10-08 leave the halt on; one
   submitted Friday 10-09 clears it.

   The start stays inclusive on purpose. An exclusive start would let a
   late-listed action, dated on the sizing close of an ordinary filled order,
   go unflagged, and its phantom P&L would enter without a word.
4. **Measure the phantom amount**: (paper qty − true qty) × the post-event price
   at the close used. Name the close, either the as-of close in that day's
   `plan.json` `closes` or the official closing print of the day measured, and
   label its provenance.

   Positive means paper overstates the book. For a merger, do the same for each
   leg. The old symbol is still held on paper, marked at whatever Alpaca last
   prices it at. The acquirer shares and the cash are missing from paper.
5. **Record it, dated, beside the official P&L.** Write a results note,
   `results/ops/CORP_ACTION_<SYMBOL>_<YYYY-MM-DD>.md`, holding:
   - the event id;
   - the primary source;
   - both counts;
   - the close used;
   - the phantom amount and the date it was measured.

   The official P&L is Alpaca's end-of-day history (`docs/SYSTEM.md` §5,
   2026-10-19, P&L of record).

   Say in the note what follows. **Alpaca's equity carries the phantom amount,
   and so does everything read from it, until the account is recreated.** That
   includes the end-of-day history, the drawdown check, and the runner's sizing,
   since the sleeve is sized on account equity. A rebalance corrects the count.
   It does not take the phantom amount out: paper books the trade at the
   inflated (or deflated) mark. Alpaca staff's only stated fix is "deleting the
   account and recreating it" (staff reply, 2026-07-15, §12pc).
6. **To trade on regardless** before the count is fixed, the team lead may set
   `corporate_actions.mode` to `report`. The gate then records and sends. Do it in
   the dev repo through a release (sections 1–2), never by hand-editing prod.
   Set it back to `halt` the same way.
7. **A long-window row no trade can clear: acknowledge that action** (team lead,
   2026-10-29). The case it is for: a name change, redemption, worthless removal
   or partial call carries only a process date, so a BACKFILLED one (processed
   long after it happened) is judged as if it had just happened, and repeats
   every session. A corrective order may be impossible (a redeemed or removed
   security) or pointless (the action predates the holding). Do step 1 first:
   the primary source must show what the action was and when. Then the team
   lead, and only the team lead, runs ONE command per action id:

   ```bash
   # laptop prod clone
   cd ~/prod/quantt-alpaca
   QUANTT_STATE_DIR=~/quantt_state/cef QUANTT_ENV_FILE=~/.config/quantt/alpaca.env \
     python3 -m quantt.session ca-ack --book cef --id <action id> --reason "<one line>"

   # the VM
   sudo -u quantt env HOME=/home/quantt QUANTT_STATE_DIR=/home/quantt/quantt_state/cef \
     QUANTT_ENV_FILE=/run/quantt/alpaca.env \
     bash -c 'cd /home/quantt/prod/quantt-alpaca &&
       /home/quantt/venv/bin/python -m quantt.session ca-ack --book cef --id <action id> --reason "<one line>"'
   ```

   The `<action id>` is the `id` in `corporate_actions.blocking`. The command
   reads the feed, read-only, for the names and window of the gate's latest
   record, and refuses an id the feed does not list, an id already
   acknowledged whose row and type are unchanged, a reason that is not one line, and a
   `ca_acks.json` it cannot read. Otherwise it writes the entry (id, reason, UTC time, the event as
   listed) to `<state>/ca_acks.json` atomically and prints what it
   acknowledged. The entry keeps the feed row exactly as listed, and its type.
   The gate then clears THAT ID ONLY, and only while the feed's row for it is
   unchanged in every field (dates, parties, ratio and the rest) and its type
   is unchanged. An unresolved row is acknowledged by the id its refusal
   names, a `row-sha256:...` key when its own id is null. Any other action, a
   new one on the same fund included, still halts. If Alpaca revises the row,
   or lists it under another type, the gate halts again, and the refusal names each changed field
   (`acknowledged at ..., but the feed row has changed since (...)`). Do step 1
   again for the revised action, and if it still stands run the same command
   again. For a revised row or type it replaces the old entry, which it keeps as
   `supersedes`; for an unchanged one it refuses. Never edit the file by hand. The cleared rows stay in the record
   under `corporate_actions.acknowledged`. Nothing else may write the file. A
   `ca_acks.json` the gate cannot read refuses every session (UNMEASURED) until
   it is fixed: restore it, or remove it and acknowledge again. An
   acknowledgement for a split, a stock dividend, a spin-off or a merger clears
   the halt but fixes no count: steps 2–5 still apply, and the command prints a
   NOTE saying so.

**An unresolved row** (docs/SYSTEM.md §5, team lead 2026-11-02 (unresolved corporate-action rows)). A row with a party symbol null or empty
(an acquirer, an acquiree, an old, new or source symbol, a split's own symbol,
or a reorganization leg with no ticker and no CUSIP) is not a read failure. The
gate treats the missing party as each held and targeted fund in turn, on the
usual windows.
- If it would block one of them, the session refuses with `an UNRESOLVED <type>
  <id> ... its <field> is missing ...; the team lead clears it with ca-ack --id
  <id>`.
- Otherwise the row is listed under `corporate_actions.unresolved` with an
  `UNRESOLVED, recorded only` log line, and the session sends.

A missing acquirer or allocated leg halts one session and then clears by
itself. Any other missing party in a held name's window halts until it is
acknowledged. Do step 1 for it; if it is not one of our funds, run the step 7
command with the id the refusal names. That id is a `row-sha256:...` key when
the row's own id is null. A revised row, or the same row under another type,
halts again.

**A skipped malformed row** (team lead 2026-10-29, `docs/SYSTEM.md` §5: "skip
it, and record it, unless it could concern one of our funds"). A row whose
every party symbol is present and none ours, but whose id or a date is
malformed, is listed under `corporate_actions.skipped_malformed` with a
`SKIPPED a malformed row` log line, and the session sends on. The same fault
on a row naming one of our funds refuses, naming the row.

## 7. Keeping the laptop awake

launchd runs a missed calendar job **once on wake**, and coalesces several
missed runs into one (`man launchd.plist`, StartCalendarInterval). Since
2026-09-29 the session job fires every 30 minutes and the runner picks its own
slots (evening 22:00–01:00 ET, morning 06:00–15:15 ET), so the laptop needs to
be awake and online for **one** slot, not at one minute. The 2026-09-29 08:30
run failed on DNS as the machine woke; under the new schedule the next slot
simply tries again. The runner's clock gate (19:15 ET on the as-of date to
15:45 ET on the session date) stops a late wake from trading. A laptop that
misses both windows trades nothing, and its verify line is a FAIL.

**Measured 2026-09-28 (`pmset -g`, `pmset -g sched`):** `SleepDisabled 1`;
`sleep 0 (sleep prevented by caffeinate, powerd)`; no scheduled or repeating
power events. Where the `caffeinate` assertion comes from was not traced. It may
be one of the retired `com.quantt.*` jobs, whose names include `awake` (name
listed, contents not read). If so, retiring them (6.6) removes it. `SleepDisabled`
is a separate setting.

A backstop wake before the morning session is a TL command that needs sudo.
It was **not run** by any agent:

```bash
sudo pmset repeat wakeorpoweron MTWRF 08:25:00
pmset -g sched                                   # verify
```

`pmset` allows **one** repeating power-on/wake event and one power-off/sleep
event (`man pmset`), so this replaces any existing repeating wake. Undo with
`sudo pmset repeat cancel`. The times are local time, so section 0.1 applies.

Unmeasured, and the TL's call: behaviour with the lid closed, on battery or
without network. Keep the laptop on power and online on trading days.

## 8. The prod VM (Azure)

**Decided by the TL on 2026-10-07:** prod moves from this laptop to an Azure
VM, on the Azure for Students subscription. The reason is the laptop's record:
from 2026-09-30 to 10-07 no order went out on 10-02, 10-05 or 10-06, because
the laptop was asleep or offline (`~/quantt_state/cef/verify.log`).
`docs/ROADMAP.md` phase 6 is the plan. This section is the procedure. The prod
rule is unchanged: the VM holds this repository at a tag and nothing else.

**This repository is public.** Never write the VM's IP address, the vault's
name, the subscription ID or the TL's IP address into a tracked file. They
appear below only as `<placeholders>`. The vault name is an installer argument.

| thing | where on the VM | made by |
|---|---|---|
| the VM | `quantt-prod` in resource group `quantt-prod`: Standard_B2pts_v2 (aarch64, 2 vCPU, 1 GiB), Ubuntu 24.04 LTS, Standard SSD 32 GB, region chosen within the subscription's allowed-locations policy | TL, 8.1 |
| admin login | `azureuser`, SSH key only, port 22 open to the TL's IP address only | TL, 8.1 |
| service user | `quantt` (no login shell); owns everything below except the units | `quantt/deploy/vm/bootstrap.sh` |
| code | `/home/quantt/prod/quantt-alpaca`: a clone of `origin`, **detached at the tag** | bootstrap, then `quantt.deploy.install_vm` |
| Python | `/home/quantt/venv`: Python 3.13.5 from uv, with `requirements.txt` installed | bootstrap |
| price/NAV panels | `<code>/data/cef/`, copied once from the laptop **prod** panels (`--seed-from`), and prod's own after that. Provenance goes in `<state>/seed.log` | `install_vm`, then the collector |
| state (`QUANTT_STATE_DIR`) | `/home/quantt/quantt_state/cef/` | `install_vm`, the runner |
| job logs | `<state>/logs/{session,verify,collect,secret}.{out,err}.log` | systemd (`StandardOutput=append:`) |
| schedule | `/etc/systemd/system/quantt-cef-{session,verify,collect}.{service,timer}`, rendered from `quantt/deploy/templates/systemd/` **at the tag**. Same commands, environment and times as the launchd jobs (a test expands both over a week) | `install_vm` |
| Alpaca keys | Key Vault secrets `alpaca-cef-key-id` and `alpaca-cef-secret-key` (vault in RBAC mode). At boot `quantt-secret.service` writes `/run/quantt/alpaca.env` (tmpfs, dir 0700, file 0600), which becomes `QUANTT_ENV_FILE`. That is once per boot when the fetch succeeds; a failed fetch is retried at every job start (see 8.3 d). Our code never writes the keys to disk, only to tmpfs. But the kernel can page process memory (tmpfs included) to the unencrypted `/swapfile` that bootstrap creates; Azure managed disks are encrypted at rest by default [S: Azure docs, not re-read] | TL puts the values in the vault; `quantt.deploy.boot_secrets` writes the file |

Everything specific to Azure is in `quantt/deploy/azure_keyvault.py`, the
provider module behind `boot_secrets --provider azure-keyvault`. The units, the
bootstrap and the installer are plain Ubuntu/systemd.

**A known gap, accepted (review 2026-10-07):** the installer runs as root, but
it executes code from the venv and the clone, and both are writable by
`quantt`. So `quantt`, or anything running as `quantt`, can make root run code
at the next install. The impact is low, because `quantt` already holds the
Alpaca keys and runs the book. Closing it would need a root-owned copy of the
installer and its interpreter.

### 8.1 Account, VM and vault (TL; an agent may run `az` with the TL's go)

These are the commands run on 2026-10-07, with placeholders:

```bash
brew install azure-cli
az login
# A new student subscription starts with these providers NotRegistered.
az provider register --namespace Microsoft.Compute
az provider register --namespace Microsoft.Network
az provider register --namespace Microsoft.KeyVault
# Where may this subscription deploy? Read the policy; never assume a region.
az policy assignment list --query "[].parameters.listOfAllowedLocations.value"
# Is the size offered in that region? (2026-10-07: Standard_B2ats_v2 was not
# offered in canadacentral; Standard_B2pts_v2 was.)
az vm list-skus -l <region> --size Standard_B2pts_v2 --output table
az group create -n quantt-prod -l <region>
az vm create -g quantt-prod -n quantt-prod \
  --image Canonical:ubuntu-24_04-lts:server-arm64:latest --size Standard_B2pts_v2 \
  --admin-username azureuser --ssh-key-values ~/.ssh/quantt_azure.pub \
  --assign-identity --nsg-rule NONE \
  --storage-sku StandardSSD_LRS --os-disk-size-gb 32 --public-ip-sku Standard
az network nsg rule create -g quantt-prod --nsg-name quantt-prodNSG -n ssh-from-team-lead \
  --priority 1000 --direction Inbound --access Allow --protocol Tcp \
  --destination-port-ranges 22 --source-address-prefixes <TL's IP>/32
az keyvault create -g quantt-prod -n <vault-name> -l <region> --enable-rbac-authorization true
# The VM's identity may READ secrets. The TL may also WRITE them.
az role assignment create --role "Key Vault Secrets User" --scope <vault resource id> \
  --assignee-object-id <VM identity principalId> --assignee-principal-type ServicePrincipal
az role assignment create --role "Key Vault Secrets Officer" --scope <vault resource id> \
  --assignee-object-id <TL's object id> --assignee-principal-type User
```

Then the **TL** creates the two secrets in the portal (Key Vault, Secrets,
Generate/Import):

- `alpaca-cef-key-id` holds the key ID;
- `alpaca-cef-secret-key` holds the secret.

Each value is one line with no surrounding spaces; `boot_secrets` refuses
anything else and names the variable. Two secrets are needed, not one dotenv
blob, because a secret name allows only `0-9 a-z A-Z -` and the portal's value
box is a single line. The keys never go into a chat or into a file in the repo.

**Measured from the VM on 2026-10-07:**
- An IMDS token (`api-version=2018-02-01`, `resource=https://vault.azure.net`,
  header `Metadata: true`) plus
  `GET https://<vault-name>.vault.azure.net/secrets/<name>?api-version=7.4`
  returned both secret values.
- Those keys authenticated to Alpaca paper (HTTP 200, account ACTIVE).

`azure_keyvault.py` sends exactly these requests. Its docstring cites the
Microsoft Learn pages.

If the TL's IP address changes, SSH is refused. Update the rule (`az network
nsg rule update ... --source-address-prefixes <new IP>/32`). Log in with
`ssh -i ~/.ssh/quantt_azure azureuser@<vm-ip>`.

### 8.2 Bootstrap the VM (TL runs it, because it needs sudo)

The tag must contain `quantt/deploy/vm/bootstrap.sh` and
`quantt/deploy/install_vm.py`. **No tag does yet:** the first one is cut after
that code is reviewed and merged.

```bash
curl -fsSLo bootstrap.sh \
  https://raw.githubusercontent.com/quanttqueensu/CreditTrading/<tag>/quantt/deploy/vm/bootstrap.sh
less bootstrap.sh                       # read it before running it as root
sudo bash bootstrap.sh <tag>
```

What it does, and why each step is there, is in the script's header:
- timezone America/New_York;
- unattended security upgrades, with **no automatic reboot**, moved to 02:00–02:30 ET;
- needrestart set to list only;
- 2 GB swap;
- the `quantt` user;
- uv (pinned) and Python 3.13.5;
- the clone at `<tag>`, with `requirements.txt` installed.

**Re-running.** The system steps (zone, apt settings, swap, user, uv,
Python) are safe to repeat. The clone step is not an update path. On an
existing clone it refuses unless HEAD is already the tag's commit, because
moving prod between tags is the installer's job (8.6).

**Nothing compiles.** `requirements.txt` is installed with `--no-build`, and uv
itself with `--only-binary=:all:`. Every compiled dependency has an aarch64
wheel (measured 2026-10-07, the script's header), so a missing wheel fails the
install loudly instead of starting a compile the 1 GiB VM cannot finish.

**Reboots.** A kernel update still needs one. The TL does it by hand, on a
weekend. `Persistent=false` means a firing missed while the VM was **down** is
not replayed at boot [V: measured on the VM, 2026-10-08. Powered off across
the slots 04:46–04:54; after booting at 04:55:07 the next run was the regular
04:56:00]. A stop and restart **within** one boot is different: it does replay
(8.3).

**A firing that passes while its job is still running is not dropped.**
Measured on the VM, 2026-10-07 (systemd 255.4-1ubuntu8.17): it starts the job
again the moment the running one exits, even with `Persistent=false`. A
one-minute calendar timer on a 90-second job ran its 23:14:00 firing at
23:14:30. For this book: the 15:52 send polls its orders until each is final.
That usually takes seconds, and **in the worst case runs to 15:59:30**. So the
15:55 firing usually starts a session inside the window, where it idles on
STARTED. In the worst case it starts just after the window, where the date
roll idles it. That session idles only because of the runner's gates:
STARTED, and the Alpaca-clock send window. **Those
gates are the only guard on that path**, and
`quantt/session/tests/test_run.py::test_late_scheduled_decides_once_then_sends_once`
covers it. `DeferReactivation=` would remove the late start, but it needs
systemd 256 or later, and Ubuntu 24.04 ships 255.

### 8.3 Install, dry (an agent runs it; the TL approves `--enable`)

`/home/quantt` is mode 750, so `azureuser` cannot `cd` into the clone. Run the
installer through this helper instead. It runs as root, with `-B` (no root-owned
`__pycache__` in quantt's tree), `-P` (the caller's working directory is not
on `sys.path`), and the clone on `PYTHONPATH`:

```bash
qi() { sudo env PYTHONPATH=/home/quantt/prod/quantt-alpaca \
         /home/quantt/venv/bin/python -B -P -m quantt.deploy.install_vm "$@"; }
```

**a. Seed the panels** from the laptop **prod** panels, which are the newest
and the ones prod trades on. These are the files `install_prod` seeds:

```bash
# on the laptop
ssh -i ~/.ssh/quantt_azure azureuser@<vm-ip> mkdir -p /tmp/quantt-seed
scp -i ~/.ssh/quantt_azure ~/prod/quantt-alpaca/data/cef/{cef_prices.parquet,cef_nav.parquet,cef_universe.csv,cef_distributions.parquet,cef_splits.parquet} \
    azureuser@<vm-ip>:/tmp/quantt-seed/
```

**b. Dry run, then apply.** The dry run prints every check, the steps and all
seven rendered units, and writes nothing except fetched tags. Apply writes the
units with DRY_RUN=1, runs `systemctl daemon-reload`, and **enables nothing**:

```bash
qi --tag <tag> --vault <vault-name> --seed-from /tmp/quantt-seed
qi --tag <tag> --vault <vault-name> --seed-from /tmp/quantt-seed --apply
```

**c. Prove the clone** (`docs/ROADMAP.md` 6.3), as `quantt`, before anything
is scheduled:

```bash
sudo -u quantt env HOME=/home/quantt bash -c 'cd /home/quantt/prod/quantt-alpaca &&
  /home/quantt/venv/bin/python -m pytest &&
  /home/quantt/venv/bin/python -m ops.doc_audit --check &&
  /home/quantt/venv/bin/python -m ops.orient'
```

**d. Enable, still dry** (TL approves). This starts the key service and the
three timers:

```bash
qi --tag <tag> --vault <vault-name> --apply --enable
systemctl list-timers 'quantt-*'                 # next firings, shown in EDT/EST
systemctl status quantt-secret.service           # "active (exited)"
sudo ls -l /run/quantt/                          # alpaca.env -rw------- quantt; never cat it
sudo tail -n 20 /home/quantt/quantt_state/cef/logs/secret.err.log
sudo systemctl start quantt-cef-session.service  # one DRY session now; it idles outside a slot.
                                                 # Only while DRY_RUN=1, and never inside 15:40-16:00 / 12:40-13:00 ET
sudo tail -n 50 /home/quantt/quantt_state/cef/logs/session.out.log /home/quantt/quantt_state/cef/logs/session.err.log
```

**If the key fetch fails**, `quantt-secret.service` is left inactive, and
every job start retries it (`Wants=`). That is self-healing: a role assignment
fixed later works at the next firing. Each job waits for the retry, though, up
to about 4 minutes when every request times out (IMDS about 142 s, then about
47 s per secret). A 4xx answer ends the fetch at once. The log carries only
the HTTP status, Azure's error codes and a hint, never the message body,
because an RBAC refusal's message names the tenant, object ids and the
`/subscriptions/...` resource id.

**The installer refuses on any of these:**
- not root;
- no `-B`;
- no `quantt` user;
- a system zone other than America/New_York;
- a vault name that is not a Key Vault name;
- a tag that is not on origin, has moved, or lacks the files the units need;
- a clone with local modifications or untracked files;
- a template at the tag whose command, environment, schedule, dependencies or
  options differ from the contract;
- a calendar line `systemd-analyze` rejects;
- missing panels and no `--seed-from`;
- **a drop-in on any quantt unit**, found two ways: by asking systemd
  (`systemctl show`), and by **scanning the disk**. Scanning is needed because
  a drop-in written without `daemon-reload` is invisible to `systemctl show`,
  and would go live at the installer's own reload (measured on the VM,
  2026-10-07). The scan covers every directory in `systemd-analyze
  unit-paths`, plus `system.control` and `transient`. It looks for:
  - `<unit>.d/`;
  - every dash prefix (`quantt-.service.d/`, `quantt-cef-.service.d/`, …);
  - the type-wide `service.d/` and `timer.d/` [S: since systemd 253].
  It also refuses a same-named unit file that outranks the installer's, or a
  unit systemd loads from any other file. Read the drop-in, remove it
  (`systemctl revert <unit>`, or delete the file), and re-run;
- **any quantt job running or queued**:
  - a `quantt-cef-*.service` that is active, activating or deactivating;
  - one with a queued `Job`. A start queued behind its dependency reads
    `is-active` inactive, so `is-active` alone misses it [V: measured on the
    VM, 2026-10-08];
  - the key service `activating`, because jobs may be queued behind it.

**One install at a time.** The installer, including a dry run, takes an
exclusive lock (`/run/lock/quantt-install.lock`) before any planning, and
`bootstrap.sh` takes the same lock. A second run refuses, naming the holder's
pid. Without the lock, a disarm could confirm DRY_RUN=1 and exit 0 while an
armed update already in flight went on to write DRY_RUN=0 and restart the
timers. The lock lives on tmpfs, so a reboot clears it.

**On `--apply` the timers are stopped for the run.** The installer stops every
running quantt-cef timer first, so no firing can start a job mid-install. It
then checks for a running or queued job, does the checkout, writes and
reloads, and checks again. Then, still with no timer running, it:
- **restarts `quantt-secret.service`**, so `/run/quantt/alpaca.env` matches
  the unit just loaded: a changed `--vault`, or keys rotated in the vault. It
  confirms the service is active and the file is 0600 and owned by quantt,
  using stat only;
- **starts every enabled timer**, plus any that was running, or enables them
  all with `--enable`;
- **reads back** from systemd that each is active, and refuses if one is not.

The end state is set by enablement, so a re-run after a refusal does leave the
timers running. To keep one timer off, disable it.

**A restart replays a slot missed during the run** [V: measured on the VM,
2026-10-08]. An enabled `Persistent=false` timer, stopped and restarted within
one boot across a missed slot, fires at once on the restart. (This corrects an
earlier line here that said it did not.) So an install that spans 15:52/15:55,
or 12:52/12:55 on an early close, would replay the send slot into a late,
partial send. **That is why the installer has two weekday windows** (narrowed
2026-10-08, release-check #5):
- **it will not start an install inside 15:30–16:00 or 12:30–13:00 ET**. That
  is a superset of the runner's late ranges, and leaves room for a run of
  about 4 minutes;
- **it will not restart the timers inside 15:52–16:00 or 12:52–13:00 ET**, the
  book's send window to the close. It checks the clock again just before the
  restart. If that check falls inside the window, it leaves the timers
  **stopped** and says so; re-run after 16:00, or 13:00.

A restart between 15:30 and 15:52 can only replay a :00/:30 session or a :40
collect, never a send. Other replays are harmless:
- a replayed :00/:30 session idles outside its slots;
- a replayed collect is just a collect;
- a replayed 17:30 verify writes the day's line;
- a replayed 22:00 decide decides once.

- **If it fails after stopping them**, whether by a refusal, a failed key
  fetch or an unexpected error, it reads the timers back and prints `timers
  left STOPPED: …` for each one that is not running. Nothing trades and no
  verify line is written until they are started again. **Prefer to re-run the
  installer**, which enforces the late-window guard. If you start them by hand
  (`sudo systemctl start …`), do it **not on a weekday inside 15:40–16:00 or
  12:40–13:00 ET**: wait until after 16:00, or 13:00 on an early close. (This
  is deliberately wider than the installer's 15:52 restart window, because a
  person is slower than a clock check.) A start
  inside 15:52–15:58 replays the missed send slot, which is a late and possibly
  partial send. Check first which DRY_RUN systemd has **loaded**, because that
  is what a start runs. The notice prints it, or `UNKNOWN` if it could not be
  read; read it yourself with
  `systemctl show -p Environment quantt-cef-session.service`.
- **A venv built from another `requirements.txt`** is refused at planning. The
  venv records the sha256 of the file it was built from
  (`/home/quantt/venv/.quantt-requirements.sha256`, written by bootstrap and
  by the 8.6 dependency step). The message gives the exact command.
- **Exit 3** (`ALERT at step …`) means a job ran or was queued after the reload,
  which should be impossible with the timers stopped. The message names the
  job, its MainPID and the DRY_RUN it started with, or says that is unknown.
  Halt with 8.6 step 1 or 2, and check Alpaca for any order it sent.

After `daemon-reload` the installer asks systemd (`systemctl show`) for every
unit's FragmentPath, DropInPaths, Environment and ExecStart (and
TimersCalendar for timers), and refuses unless they match what it wrote. A
disarm is therefore confirmed from what systemd loaded, not from the file.

Each refusal names the problem.

### 8.4 Shadow (DRY_RUN=1) beside the armed laptop

Both machines decide on their own panels. The VM sends nothing (gate 1), and
its collector and verify are read-only at Alpaca. Each evening after the
decision window, compare the VM's `<state>/<date>/plan.json` order list with
the laptop's. With the same inputs they should match. A difference names a
data or environment difference, to be explained before arming.

**The VM's verify FAILs on every shadow day the laptop trades, by design.**
Both machines share one Alpaca account. On such a day Alpaca holds orders with
the day's `client_order_id` prefix that the VM did not record, so the VM's
verify fails rules 2 to 4 (`quantt/session/verify.py`): orders not in its
`orders.jsonl`, no STARTED but orders with the day's prefix, fills that belong
to none of its orders. A shadow FAIL of exactly that form is expected. **Any
other FAIL reason is not**, and must be explained before arming.

**Watch especially** the collector logs for Yahoo rate limiting from an Azure
address. It is unmeasured [U], and a block means a stale panel, which means
no trade. How long to shadow is the TL's call; record it in `docs/ROADMAP.md`.

### 8.5 Cut-over: never two armed schedulers

Two machines armed for one account would each pass gate 6 on their own state
dir. Only the Alpaca-side check (the day's `client_order_id` prefix) would
stand between them and a doubled book (`CLAUDE.md` order-path rule 2). Do it
in this order, **after a 17:30 verify and before 22:00 ET**, which is before
the evening decide:

1. **Laptop off, for good.** `launchctl bootout` alone is not enough: the
   plists stay in `~/Library/LaunchAgents` with DRY_RUN=0, and launchd loads
   them again at the next login. So:
   ```bash
   cd "<dev repo>"
   # a. disarm the plists themselves (add --accept-timezone if section 0.1 chose it)
   python3 -m quantt.deploy.install_prod --tag <laptop's current tag> --env-file <key file> --apply --load
   # b. unload AND disable all three jobs, so no login or reboot loads them again
   for j in session verify collect; do
     launchctl bootout gui/$(id -u)/com.quantt.alpaca.cef.$j
     launchctl disable gui/$(id -u)/com.quantt.alpaca.cef.$j
   done
   launchctl print-disabled gui/$(id -u) | grep com.quantt.alpaca     # all three "disabled"
   # c. and the second key: no AUTO_ARMED
   rm ~/quantt_state/cef/AUTO_ARMED
   ```
   Then confirm with the read-only probe that no order is open at Alpaca.
2. **Stop the VM's timers:**
   `sudo systemctl stop quantt-cef-session.timer quantt-cef-verify.timer quantt-cef-collect.timer`.
3. **Carry the laptop's records across.** The opening session is decided from
   the broker (`is_opening_session`), so a fresh state dir would not re-open
   the book. But the shadow benchmark (`shadow_book.json`, `shadow.csv`),
   `scores.csv`, `equity.csv`, `verify.log` and each day's `plan.json` live in
   the state dir, and a fresh one would restart them. Move the VM's shadow
   records aside and copy the laptop's in:
   ```bash
   # laptop
   tar -C ~/quantt_state -czf /tmp/cef-state.tgz --exclude cef/AUTO_ARMED --exclude cef/logs cef
   scp -i ~/.ssh/quantt_azure /tmp/cef-state.tgz azureuser@<vm-ip>:/tmp/
   # VM
   sudo mv /home/quantt/quantt_state/cef /home/quantt/quantt_state/cef.shadow-<date>
   sudo tar -C /home/quantt/quantt_state -xzf /tmp/cef-state.tgz
   sudo chown -R quantt:quantt /home/quantt/quantt_state/cef
   ```
   The panels' provenance (`seed.log`) stays in `cef.shadow-<date>`.
4. **Arm the VM, without AUTO_ARMED** (TL). Do it before 15:30 or after 16:00
   ET on a weekday (12:30/13:00 on an early close); the installer refuses
   inside those windows (8.3):
   `qi --tag <tag> --vault <vault-name> --armed --apply --enable`.
   Do **not** create AUTO_ARMED yet. The VM's first armed send is planned from
   its own panels and its unmeasured Azure collector, so its order list is
   shown to the TL first (`CLAUDE.md` order-path rule 1, `docs/ROADMAP.md`
   6.5). With DRY_RUN=0 and no AUTO_ARMED, a scheduled send transmits only a
   plan that carries a recorded approval (gate 2).
5. **Show the first decided plan to the TL.** After the 22:00 decide (or the
   morning backstop), the plan for session date D is in
   `/home/quantt/quantt_state/cef/<D>/plan.json`, with its order list and
   `plan_sha`. Show it with `sudo cat /home/quantt/quantt_state/cef/<D>/plan.json`.
6. **On the TL's go, and only then**, record the approval for that plan:
   ```bash
   sudo -u quantt env HOME=/home/quantt QUANTT_STATE_DIR=/home/quantt/quantt_state/cef \
     bash -c 'cd /home/quantt/prod/quantt-alpaca &&
       /home/quantt/venv/bin/python -m quantt.session approve --book cef --date <D> --sha <plan_sha>'
   ```
   It refuses unless the plan for D is decided and hashes to that sha, and it
   refuses once a set has STARTED (`quantt/session/run.py`, `approve_main`). The
   scheduled 15:52 send then transmits that plan and nothing else.
7. **Watch** the 15:52 send and the 17:30 verify. **Create AUTO_ARMED only after
   that verify line PASSes** (TL):
   `sudo -u quantt touch /home/quantt/quantt_state/cef/AUTO_ARMED`. From then on
   each decided plan is sent without a per-day approval (`docs/RUNNER.md` gate 2).

**Rolling back to the laptop** after step 1 runs it in reverse. First halt the
VM (8.6) and disarm it; never have two armed schedulers. Step 1b disabled the
launchd jobs, so `install_prod --load` alone does not bring them back. Enable
them first:
`for j in session verify collect; do launchctl enable gui/$(id -u)/com.quantt.alpaca.cef.$j; done`.
Then run `install_prod --tag <tag> --env-file <key file> --apply --load`, adding
`--armed` and `AUTO_ARMED` only on the TL's go (section 3.4).

### 8.6 Daily reading, halting and updating on the VM

**The verdict:**

```bash
ssh -i ~/.ssh/quantt_azure azureuser@<vm-ip> sudo tail -n 5 /home/quantt/quantt_state/cef/verify.log
systemctl list-timers 'quantt-*'; systemctl --failed     # on the VM
```

No line for a trading day counts as a FAIL, and a `MISSED:` FAIL is a day that
should have traded (section 5). The session unit counts IDLE,
NOTHING_TO_SEND, PREVIEW, PLANNED and DRY as success (`SuccessExitStatus`), so
`systemctl --failed` shows REFUSED and FAIL. Verify exits 1 on a FAIL line, so a
missed day shows there too.

**Tonight's plan:** `python3 -m ops.orient` PROD prints the VM's `newest plan`:
its date, status, order count, whether it was sent, and its evening pre-flight.
`PRE-FLIGHT WARNING` means a day as bad as the worst of the last year would get
tomorrow's send refused or scaled. The detail is in that day's `plan.json`
(`preflight`) and the session log (`docs/RUNNER.md` "As built (2026-10-09)"). The collector's INCOMPLETE (exit
5) also shows as failed, on purpose: one that never clears is worth seeing.

**The evidence log, each evening** (after verify's 17:30 ET line; `results/report/README.md`).
Every live day gets an entry in `results/report/EVIDENCE_LOG.md`, in the same commit as its data:

```bash
! sh vmpnl.sh        # the team lead's local, read-only wrapper; it copies the VM's P&L records to the scratchpad
python3 -m scripts.report.snapshot_live --src "$(sed -n 's/^OUT="\(.*\)"$/\1/p' vmpnl.sh)" --book cef
git add results/report/data results/report/EVIDENCE_LOG.md && git commit -m "Evidence pack: live day <date>"   # aggregates only; the cache is ignored
python3 -m scripts.report.build_pack && git add results/report && git commit -m "Evidence pack: rebuild for <date>"
```

`snapshot_live` sanitises (it refuses, naming the field, anything it cannot drop) and is
idempotent: a pull it has already ingested adds nothing. **Aggregates go to the repository,
rows to the gitignored `results/report/_cache_live/`** (team lead, 2026-11-03: "Aggregates in
repo, rows private"); it refuses to write a row file where git can see it. `vmpnl.sh` copies
`eod_equity.csv` (since 2026-11-03), so the official EOD line is built from the pull. The
cache's R2 backup is the team lead's step (`results/report/README.md`).

**Halting**, the VM equivalents of section 4, fastest first. None of them
cancels an order already at Alpaca.

1. **Halt file** in the prod clone, as `quantt`:
   ```bash
   sudo -u quantt env HOME=/home/quantt bash -c 'cd /home/quantt/prod/quantt-alpaca &&
     /home/quantt/venv/bin/python -c "from ops.halt import write_halt; write_halt(\"why\", source=\"runbook\", book=\"cef\")"'
   ```
   The file is written before any alert channel is tried, and the alert
   channels are wrapped, so a missing macOS banner or speech engine does not
   stop it. Halt files are gitignored, so a standing halt does not block the
   installer.
2. **Remove AUTO_ARMED and any unsent day's APPROVED.** A per-day approval
   (`<state>/<D>/APPROVED`, written by `quantt.session approve`) arms that day's
   send on its own, without AUTO_ARMED. That is how the cut-over day (8.5) sends,
   so removing AUTO_ARMED alone would not stop it (corrected 2026-10-08,
   release-check #8). Only the runner reads APPROVED, so removing it for a day
   that has not sent is safe:
   ```bash
   sudo bash -c 'rm -f /home/quantt/quantt_state/cef/AUTO_ARMED
     for d in /home/quantt/quantt_state/cef/20*/; do
       [ -e "$d/APPROVED" ] && [ ! -e "$d/STARTED" ] && rm -v "$d/APPROVED"; done; true'
   ```
   When in doubt, step 1 (the halt file) stops every send, however it is armed.
3. **DRY_RUN=1:** re-install without `--armed` (`qi ... --apply`). **Not inside
   15:30–16:00 or 12:30–13:00 ET on a weekday**: the installer refuses there,
   because its timer restart could replay a send slot (8.3). Inside those
   windows, halt with step 1 or 2. It takes
   effect at the installer's `daemon-reload`, and the installer then confirms
   from systemd that DRY_RUN=1 is what is loaded.
   - **This step is not fast.** The installer refuses while any job runs or is
     queued (an evening decide can take minutes), and it refuses any drop-in
     on disk, because a drop-in could keep DRY_RUN=0 in force. When the halt
     is needed **now**, use step 1 or 2 first.
   - It stops the running timers for the length of the run, so no firing can
     start the old, armed unit mid-disarm. At the end it starts every enabled
     timer and reads back that each is running. If it fails part-way, it reads
     them back and names any left stopped.
   - **If it refuses after the reload**, systemd is **now** running the
     configuration shown in the refusal. Halt at once with step 1 or 2
     (`ops/HALT.md`, or remove AUTO_ARMED and any unsent day's APPROVED), then
     find the cause.
4. **Nothing runs at all, verify included:**
   `sudo systemctl disable --now quantt-cef-session.timer quantt-cef-verify.timer quantt-cef-collect.timer`.

**Updating** to a new release. Never change code under a running job.

Since 2026-11-02 an agent may run every step below itself, arming included (team lead; CLAUDE.md rule 1, standing authority; `docs/SYSTEM.md` §5). It does so only through the laptop's wrapper, and only when each gate passes: a release-check GO on the exact commit, CI passed on the PR's exact head (the merge then uses the team lead's `--admin` bypass, which main's ruleset requires for every merge, with `--match-head-commit`), a replay with no run refused now, outside the send windows, and the read-back. It stops at the first failure and records the outcome in `docs/JOURNAL.md` the same day.
**Start any `--apply` before 15:30 ET, or after 16:00.** The installer
refuses to start inside 15:30–16:00. It also refuses to restart the timers
from 15:52, which would leave them stopped, and the key fetch can take about 4
minutes. On an early close, the same applies before 12:30 or after 13:00.

1. **Stop the timers** at a quiet moment: not 15:30–16:00 ET, not 12:30–13:00 ET
   (an early close's send window), not 17:30. The installer refuses inside the
   two late windows anyway.
   The installer also stops them for its own run, but a manual `git checkout`
   (step 3) happens outside that run, so stop them here first:
   `sudo systemctl stop quantt-cef-session.timer quantt-cef-verify.timer quantt-cef-collect.timer`,
   then check that `systemctl list-jobs 'quantt-*'` lists no job and
   `systemctl show -p ActiveState quantt-cef-session.service
   quantt-cef-verify.service quantt-cef-collect.service` shows no `active` or
   `activating`. `is-active` alone misses a queued start [V, 2026-10-08]. The
   installer refuses while a job runs or is queued anyway, but a manual
   `git checkout` has no such guard.
2. **Dry run:** `qi --tag <new> --vault <vault-name>`.
   If the release changes `quantt/session/gate.py` or the send path
   (`quantt/session/run.py`), first replay the book's history through it. Copy
   the VM's day records to a scratch directory **outside the repo** (they hold
   the account's positions), then run, from the dev tree at the new tag:
   ```bash
   mkdir -p /tmp/qstate && ssh quantt-vm 'sudo tar czf - -C /home/quantt/quantt_state/cef \
       --exclude="*/data" $(sudo ls /home/quantt/quantt_state/cef | grep -E "^20")' | tar xzf - -C /tmp/qstate
   python3 -m ops.replay_exposure /tmp/qstate
   ```
   Every run the new code refuses ("now") must be one that should be refused.
   2026-10-09's refusal was this check's reason to exist.
3. **Only if** the old installer refuses because the release changed the units
   or the installer: with the timers still stopped, check out the tag as
   `quantt`:
   `sudo -u quantt git -C /home/quantt/prod/quantt-alpaca checkout --detach <new>`.
   If `requirements.txt` changed (the dry run refuses and says so), also run
   the following, which installs wheels only and records which file the venv
   was built from:
   ```bash
   sudo -u quantt env HOME=/home/quantt bash -c 'set -euo pipefail; cd /home/quantt
     /home/quantt/.uv/bin/uv pip install --no-build --python /home/quantt/venv/bin/python \
       -r /home/quantt/prod/quantt-alpaca/requirements.txt
     h=$(sha256sum /home/quantt/prod/quantt-alpaca/requirements.txt | cut -d" " -f1)
     [ -n "$h" ]
     printf "%s\n" "$h" > /home/quantt/venv/.quantt-requirements.sha256.tmp
     mv /home/quantt/venv/.quantt-requirements.sha256.tmp /home/quantt/venv/.quantt-requirements.sha256'
   ```
   It changes into `/home/quantt` first: uv reads `uv.toml` from the working
   directory, and from the admin's home it failed with "Permission denied"
   (measured on the VM, 2026-10-08). All of it runs as `quantt`. The admin user cannot read `/home/quantt`
   (mode 750). An earlier form here hashed the file as the admin user and
   piped it to `tee`, so a failed hash truncated the record (corrected
   2026-10-08). Now the record is written only after a successful hash. The
   installer prints this same command (`deps_command`) when it refuses. The
   installer does not install dependencies, and it refuses a venv whose record
   does not match the tag's `requirements.txt`.
4. **Apply and re-enable, only through the installer:**
   `qi --tag <new> --vault <vault-name> --apply --enable`, adding `--armed` if
   the VM is armed. **A re-install without `--armed` disarms.** The restart at
   the end replays any slot missed while the timers were stopped (8.3). That is
   harmless outside the late windows, and the installer refuses inside them.

**If you abandon an update after step 1**, the timers must run again, or
nothing trades and no verify line is written. **Prefer to re-run the
installer** at the current tag (`qi --tag <current> --vault <vault-name>
--apply`, with `--armed` if armed). It enforces the late-window guard and
reads back the result. If you start them by hand, check first which DRY_RUN
systemd has loaded (`systemctl show -p Environment
quantt-cef-session.service`; that is what will run). Then, **not on a weekday
inside 15:40–16:00 or 12:40–13:00 ET** (wait until after 16:00, or 13:00), run
`sudo systemctl start quantt-cef-session.timer quantt-cef-verify.timer quantt-cef-collect.timer`.
A start inside 15:52–15:58 replays the missed send slot: a late, possibly
partial send.

**Rolling back** is the same procedure with the previous tag.

**Re-running `bootstrap.sh` is not an update path.** It refuses while any quantt
timer runs or a quantt job runs or is queued, because it reinstalls packages
into the venv. It refuses while an install holds the lock, and on an existing
clone not already at the tag (8.2).

**Rotating the keys:** the TL adds a new version of both secrets in the portal,
and the latest version is what gets fetched. Then, **not inside 15:30–16:00 or
12:30–13:00 ET on a weekday** (the installer refuses there), re-run the installer
(`qi --tag <current> --vault <vault-name> --apply`, adding `--armed` if the
VM is armed). That is the safe way: it restarts `quantt-secret.service` while
the timers are stopped and no job is running, and confirms the key file. A bare
`sudo systemctl restart quantt-secret.service` also works, but only outside
every job window. Restarting removes and re-creates `/run/quantt`, so a job
starting at that instant would find no key file and fail loudly. Because the
job units use `Wants=` and not `Requires=`, a running job is never stopped by
the restart.

**Hazards of the same class, accepted (own review, 2026-10-08).** Each one
was weighed and left, with the reason:
- **Reboot mid-install.** Each unit file is written atomically, but a crash
  between two unit writes leaves a mix, and at boot systemd loads whatever is
  on disk. Enabled timers then start at boot. A missed slot is not replayed
  at boot (M2). **Until an install exits 0, assume the previous state,
  possibly armed.** If it must be halted now, use halting step 1 or 2. The
  lock is on tmpfs, so a reboot never leaves it stale.
- **Operator `systemctl` commands during an install.**
  - A drop-in written mid-run is caught by the last disk scan, or after the
    reload by `confirm_loaded` ("systemd is NOW running…").
  - A job started by hand is caught by the post-reload job check (exit 3).
  - A timer disabled mid-run (halting step 4) makes the install refuse rather
    than restart or re-enable it.
  - What is NOT caught: a job started by hand that has already finished by the
    post-reload check. The planning window rules out a send slot during an
    install, so such a job could only be a decide, an idle or a collect.
- **A halt file during an install.** The runner reads `ops/HALT.md` at run
  time, and the installer never touches it, so the halt holds.
- **Clock and DST.** The installer's windows use America/New_York via zoneinfo,
  so DST is handled. The system clock is chrony-synced. If it were wrong, the
  runner's own gates use Alpaca's clock as the second guard.
- **Holidays and early closes.** Both windows are guarded on every weekday. On
  a holiday the installer refuses for nothing, which is harmless. It needs no
  calendar to stay out of the way.
- **`--python` skips the venv check in effect.** The requirements record that
  is checked is always `/home/quantt/venv`'s, so a custom `--python` runs an
  interpreter whose packages are not checked. Use the default.

### 8.7 Cost, and the credit that keeps the book alive

Azure for Students gives $100 of credit and a limited quantity of free
services for 12 months. "Once your credit runs out, Azure disables your
services and subscription", and the same happens when the 12 months end.
**A disabled subscription stops the VM, and with it the book.** Reactivation
means upgrading to pay-as-you-go through Azure support [V: Microsoft Learn,
"Reactivate disabled Azure for Students subscription", fetched 2026-10-07].

Check the remaining credit and its expiry date at
`https://www.microsoftazuresponsorships.com/balance`. Sign in with the student
account. The expiry date is under the credit chart, and *Usage* shows the
spend per service. Measure it there; do not project from the prices below. If
the credit will not last to the end of the paper period, the TL decides
between pay-as-you-go and another host before it runs out.

Prices [V: Azure Retail Prices API, canadacentral, 2026-10-07]:

| item | price |
|---|---|
| Standard static public IPv4 | $0.005/hour |
| Standard SSD E4 (the 32 GB OS disk) | $2.64/month |
| Key Vault | $0.03 per 10,000 operations (one fetch per boot) |

The VM's compute price was not measured here, so this table is not a total.

### 8.8 Open items for the VM

- **Yahoo from an Azure address** is unmeasured [U]. See 8.4.
- **Dependencies are pinned only at the top level** (`requirements.txt`), so
  transitive versions on the VM can differ from the laptop's. A lockfile would
  fix that. It is a TL decision, not made here.
- **Burstable CPU:** B-series sizes are burstable [S]: they run below full
  speed once their burst credit is spent. Whether that slows the evening decide or a pytest run on
  the VM is unmeasured.
### 8.9 A second book on the VM: C4 (dark, 2026-10-29)

`install_vm --book c4` installs C4's own units beside the core's: seven
`quantt-c4-*` units, the core's jobs with `--book c4` at the same times. They
touch none of the core's units. The default book is still the core, whose
install is byte-identical to release-20261029-3's
(`quantt/deploy/tests/test_install_vm_books.py`).

| what | the core | C4 |
|---|---|---|
| state | `quantt_state/cef` | `quantt_state/c4` (the runner, verify and collector refuse any other) |
| keys | `/run/quantt/alpaca.env` from `alpaca-cef-*` | `/run/quantt-c4/alpaca.env` from `alpaca-c4-*`, through `quantt-c4-secret.service` |
| panels and lock | `data/cef/`, `.fetch.lock` there | `data/cef_c4/`, its own `.fetch.lock` |
| account start | in the collector | `--eod-from`, required with no default, rendered as `QUANTT_EOD_FROM` |
| seed | `--seed-from` the laptop's `data/cef` files | `--seed-from` a `data_books.py seed-c4` directory whose manifest names the tag's IGR ruling |

**One clone, one tag.**
- `--book c4` never checks the clone out. It refuses unless the clone is
  already at the tag, so install the core first.
- The core's install refuses to move the clone while a C4 timer is enabled or
  running, or a C4 job is busy. To release: disable C4's timers, install the
  core, then re-install C4 at the same tag.

Every guard in this section applies to C4 too. The team lead's steps, from the
vault secrets to the arming go, are in
`results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md`.

### 8.10 The shadow-book runner on the VM (2026-11-09)

A second, separate thing on the VM: simulated books on live data, which send no order
(`results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md`; `docs/SYSTEM.md` §5, 2026-11-09). It
is **not prod and not a release**. It is a clone under its own unix user, `quantt-shadow` (not `shadow`: Ubuntu has a system group of that name, which guards the password file), that
follows the branch `shadow`, so a new book is a commit to that branch.

| what | prod | the shadow runner |
|---|---|---|
| user and home | `quantt`, `/home/quantt` | `quantt-shadow`, `/home/quantt-shadow` |
| code | a clone at a release tag | `/home/quantt-shadow/quantt-shadow`, following the branch `shadow` |
| state | `quantt_state/<book>` | `/home/quantt-shadow/shadow_state` |
| key file | `/run/quantt/alpaca.env` | `/run/quantt-shadow/alpaca.env`: a copy of the core account's key, for reading prices |
| units | `quantt-cef-*`, `quantt-c4-*` | `quantt-shadow-secret.service`, `quantt-shadow.service`, `quantt-shadow.timer` |
| schedule (New York) | section 8.3 | 18:50 and 20:50 Monday to Friday, 07:20 Tuesday to Saturday |

**Install (the team lead, once; it needs sudo).** Outside prod's windows (not 15:45–16:00,
17:25–17:40 or 22:00–01:00, and not at :10 or :40 past an hour); the script refuses while a
prod job runs. The branch `shadow` must exist on GitHub first.

```bash
curl -fsSLo install_shadow_vm.sh \
  https://raw.githubusercontent.com/quanttqueensu/CreditTrading/shadow/shadow/deploy/install_shadow_vm.sh
less install_shadow_vm.sh            # read it before running it as root
sudo bash install_shadow_vm.sh --vault <vault-name> --enable
```

**Check it once by hand:**

```bash
sudo systemctl start quantt-shadow-secret.service && sudo systemctl start quantt-shadow.service
sudo tail -n 20 /home/quantt-shadow/logs/nightly.out.log /home/quantt-shadow/logs/nightly.err.log
systemctl list-timers 'quantt-shadow*'
```

With no book file on the branch the run prints "no enabled book" and exits 0. The page for
every book is `/home/quantt-shadow/shadow_state/SCOREBOARD.md`.

**Stop it:** `sudo systemctl disable --now quantt-shadow.timer`. Nothing else depends on it.

**What the separate user does not protect against.** The vault is read through the VM's own
identity, which every local user can reach. File permissions keep shadow code out of prod's
state and key file, and they cover accidents; they do not stop code on the `shadow` branch
from asking the vault for a secret. Control who can push to that branch.

**Installed 2026-11-10, 11:12 New York**, by an agent at the team lead's request ("can u run
it"), in the gap between prod's jobs; it took 22 seconds [V: the run's own output]. The first
attempt, at 10:12, stopped at its first step and created nothing, because the user was then
named `shadow`. **Still not measured:** the job's memory peak (systemd reported none for the
first run), so the unit's `MemoryMax` remains a guess to read against later runs. **If `requirements.txt` changes on the branch, the nightly run refuses** until
this script is re-run.

### 8.11 The nightly report-only checks (data QA and risk)

Team lead, 2026-11-08: the nightly check is owned by a VM timer, and pushes a
notification only when a stop fires. Everything else stays in the journal
(`results/ops/AGENT_DESK_DESIGN_2026-11-03.md`, PR #46; the scripts'
docstrings give the reasons).

| job | unit | when (Mon-Fri, local) | writes |
|---|---|---|---|
| data QA per book | `quantt-{cef,c4}-dataqa` | 21:45 cef, 21:50 c4 (after the :40 collect, before the 22:00 decide) | `<state>/reports/data_qa/<date>.{md,json}` |
| risk per account | `quantt-{cef,c4}-risk` | 22:15 cef, 22:20 c4 (after the decide) | `<state>/reports/risk/<date>.{md,json}` |

These times are clear of every runner slot (session :00/:30, collect :10/:40,
send, verify 17:30), and the units cannot overrun into the next one:
`TimeoutStartSec=480`. The units carry no broker key file, no DRY_RUN and no
lock: they read the panels and the runner's files, and `ReadOnlyPaths=` the
clone. `MemoryMax=450M` (peak measured 2026-11-08 on the laptop's panels,
data_qa 220 MB for C4, risk 102 MB; read the real figure with `systemctl show
quantt-c4-dataqa -p MemoryPeak` after a first run). A failed report job is its own failed
unit: a session never depends on one.

**Install** (after the core at the tag; it never moves the clone):

```bash
qi --tag <tag> --vault <vault-name> --reports                     # dry run: every check, every unit
qi --tag <tag> --vault <vault-name> --reports --apply --enable    # writes the units, starts the timers
```

It touches no session, verify, collect or key unit. A book install's existing checks
refuse only at planning while a report job is running; it never re-asks that after it
has stopped the timers, and it never stops or starts a report timer.

**Reading.** `sudo tail -n 60 /home/quantt/quantt_state/cef/logs/{dataqa,risk}.out.log`
and the dated reports under `<state>/reports/`. A report that cannot measure a block
says UNMEASURED and names what is missing (on the VM today: `stops.py`'s fit series;
the attribution and factor blocks read the daily P&L job's report (8.12) and are
UNMEASURED until it has run; the drawdown reader's freshest-row rule waits on PR #55).

**Severity.** INFO stays in the file; WATCH is a line near a limit or a data-QA flag on a held name; ACT is a
pre-registered stop that has fired. Only ACT pushes (risk jobs only). **The team lead's steps
for the push to work:**

1. Create a Gmail App Password (16 characters; 2-step verification on) for the sending account.
2. In the vault the units already use, create two secrets, single-line values:
   `alert-smtp-user` (the sending address) and `alert-smtp-pass` (the app password).
3. After a release with this section's code is installed with `--reports`:
   `sudo systemctl restart quantt-reports-secret.service`, then send a test through the channel:

   ```bash
   sudo systemd-run --wait --pipe --uid=quantt --gid=quantt \
     -p EnvironmentFile=/run/quantt-reports/alert.env \
     --working-directory=/home/quantt/prod/quantt-alpaca \
     /home/quantt/venv/bin/python -B -m scripts.ops.risk_daily --book cef \
     --state-dir /home/quantt/quantt_state/cef --notify-test
   ```

Until that is done, a fired stop records `ACT: notification NOT delivered: <reason>` in
the report and the service exits 3, failed: it is never silent. Authenticated SMTP on
port 587 is allowed from Azure VMs regardless of subscription (docs/REFERENCES.md);
this code has never sent from the VM, so the test above is the first proof.

**Rollback.** On a rollback to a tag older than this section, first
`sudo systemctl disable --now quantt-{cef,c4}-{dataqa,risk}.timer` and delete the
report unit files: an older installer's C4 scan names any other `quantt-` unit file as
"no unit any book installs" and refuses.

### 8.12 The daily P&L attribution and factor readout (report only)

Team lead, 2026-11-09: a daily VM report for BOTH paper books, the P&L attribution and
the exposure readout. It is a third report kind under `--reports` (beside dataqa and
risk), one job per book:

| job | unit | when (Mon-Fri, local) | writes |
|---|---|---|---|
| P&L attribution and factor readout | `quantt-{cef,c4}-pnl` | 20:30 cef, 20:35 c4 (after the 20:00 EOD stamp, clear of the 21:40 collect) | `<state>/reports/pnl/<date>.{md,json}` (and its fetch cache `<state>/reports/pnl/_cache/`, the account's fills and equity, and yfinance's own SQLite caches `<state>/reports/pnl/_yf_cache/`; all outside git) |

What it reports, per book, for the session just closed and cumulative from the book's
first trade (read from the account's own fills, never written anywhere): official P&L
(Alpaca EOD history), hold split into NAV part and discount part, fill cost, fees,
distributions, then factor exposure at the last close against the review line
(REVIEW_FRACTION x vol_target_annual x sizing_multiplier, each read from the book's own
spec, the multiplier since the team lead's ruling of 2026-11-10 because the account holds m
x the unit book; the report prints the three inputs beside the line), headline first, by
muni/taxable (core) or by family (C4). The rebuild must reconcile to official to the
cent, or the report says so at its top (overall status UNRECONCILED, not OK). **A breach of a review line is report-only: it
appears in the report and sends NOTHING** (no push, no ACT, no halt, no trade; team lead,
2026-11-09). `risk_daily`'s attribution and factor blocks read this job's JSON and stay
UNMEASURED, named, when the job has not run.

**Exit codes** (team lead, 2026-11-10; `scripts/ops/pnl_report.py`, EXIT CODES). The report
files are written before the job exits, whatever the code, and `risk_daily` reads them the
same way after any code (its own timer; nothing ties it to this unit's result: an
unreconciled report is its WATCH).

| code | meaning | the report says |
|---|---|---|
| 0 | the attribution ran and reconciled to the cent on every session (the factor block may still be PARTIAL or UNMEASURED) | OK or PARTIAL |
| 2 | refused before reading or writing anything: no state directory, or one under data/ or visible to git | (no report) |
| 4 | incomplete: no broker read (no key, a failed read) or the attribution refused | UNMEASURED, naming why |
| 5 | unreconciled: on some session the rebuild does not equal Alpaca's official EOD change to the cent | UNRECONCILED, naming the session and the residual |
| 1 | an uncaught exception (a bug); the report may not have been written | - |

A run that is both incomplete and unreconciled exits 4: nothing could be reconciled. The
pnl unit carries no `SuccessExitStatus` (the installer refuses a rendered unit that has
one), so 4 and 5 both show as a failed `quantt-<book>-pnl.service`; read the report before
the unit's log.

**Keys (the only secrets these units touch).** The pnl jobs read the account, so they
need the account's Alpaca key, and read it from the vault at run time, never from a file
in the repo or on disk: each book has its own secret service
(`quantt-reports-{cef,c4}-pnl-keys.service`), writing that book's key to a tmpfs env file
of its own, `/run/quantt-reports-{cef,c4}-pnl/broker.env`, mode 0600, loaded only by that
book's `quantt-<book>-pnl.service` through `EnvironmentFile=`. **No new vault secret is
needed**: they use the same secrets the books' own key services already use (`alpaca-cef-key-id`,
`alpaca-cef-secret-key`, `alpaca-c4-key-id`, `alpaca-c4-secret-key`). The dataqa and
risk units stay key-free and the SMTP `alert.env` stays separate (both tested). The job's
reader is `scripts/ops/alpaca_read.py`: HTTP GET only, the paper and data hosts only, no
order code; a closure test (`scripts/ops/tests/test_report_no_order_path.py`) pins that
no import path from the job reaches order-sending code. The job takes no lock, and
`ReadOnlyPaths=` the clone. A failed key fetch or broker read marks its own unit failed and
touches nothing else.

**Install** (the team lead's step, after the release is installed; the same command as
8.11, which also installs and updates the dataqa and risk units):

```bash
qi --tag <tag> --vault <vault-name> --reports                     # dry run: every check, every unit
qi --tag <tag> --vault <vault-name> --reports --apply --enable    # writes the units, starts the timers
```

Its output names the two key services and the two env files. Then start one by hand once
the day's EOD point exists (after 20:00 ET on a trading day), and read what it wrote:

```bash
sudo systemctl start quantt-reports-cef-pnl-keys.service
sudo systemctl start quantt-cef-pnl.service
sudo tail -n 60 /home/quantt/quantt_state/cef/logs/pnl.out.log /home/quantt/quantt_state/cef/logs/pnl.err.log
sudo sed -n 1,40p /home/quantt/quantt_state/cef/reports/pnl/<date>.md
systemctl show quantt-cef-pnl -p MemoryPeak    # MemoryMax=900M is a guess, not a measurement
```

`MemoryMax=900M` (a generous first setting: the job has not been measured on the VM; the
report units' measured peaks are in 8.11) should be cut to the measured peak with margin
after the first week. The job calls yfinance for NAVs, dividends and prices (keyless); the
VM must be able to reach Yahoo. A missing NAV (a fund not published by 20:30) makes the NAV
and discount parts UNMEASURED for that name-day, named, and leaves hold, fill, fees and
the reconciliation complete. A held name yfinance has not served by the job's run (a late
same-day close; HYT lags, CLAUDE.md landmine 6), or cannot serve at all, makes the factor
block PARTIAL, not UNMEASURED (team lead, 2026-11-10): the other held names are read, the
names left out are listed with the reason and their share of the book's gross, and every
reading and REVIEW flag on the partial book says PARTIAL; `risk_daily` shows that block as a
WATCH naming the share. PARTIAL is about the as-of close only (independent review of PR #82,
2026-11-11): a name left out only on an earlier date (a fund once held that yfinance no
longer serves) is a named history note in an OK block, and `risk_daily` shows it as INFO. A
book that holds nothing at the as-of close has a FLAT factor block (the same review): it
says the book is flat and reads no exposure, flag or PARTIAL for that close, never the
previous close's reading; its history since the first trade is labelled with its dates;
the report's overall status is OK. A bug, the
no-lookahead assertion or a failed price fetch (yfinance down) while reading that history
makes the block UNMEASURED, as on a held night (second review of PR #82, 2026-11-11). FLAT
is read from the fill rebuild, so two checks guard it (team lead, 2026-11-11): the job never
says FLAT when the rebuild does not reconcile (the block is UNMEASURED, saying whether the
book is flat cannot be read from it), and `risk_daily` cross-checks every FLAT against the
collector's account record for that same close, `<state>/data/<D>/account.json` (written by
the collector's `account_snapshot` step after D's close and before the next open). The block
is INFO when that record holds no position, a WATCH naming the count and the symbols when
it holds any, and UNMEASURED when the record is missing, unreadable or for another session.
A factor ETF
without its price, or no held name with its inputs, makes the block UNMEASURED, naming it;
the attribution above it stays either way. A book whose lag rule has produced no Dimson lag
has a factor block UNMEASURED, naming the rule. Neither does today: the core's rule gives
L = 0, and C4's gave L = 2 on 2026-11-09 (`scripts/cef/exposure_readout.py`, THE C4 RULE'S
RESULT).

**Rollback.** As 8.11: on a rollback to a tag older than this section, first
`sudo systemctl disable --now quantt-{cef,c4}-pnl.timer`, then
`sudo systemctl stop quantt-reports-{cef,c4}-pnl-keys.service` (its key material goes
with its runtime directory), and delete the two pnl service files, the two pnl timer files
and the two key-service unit files.

## Open questions (for the TL)

1. **Timezone:** set this Mac to `America/New_York`, or accept `America/Toronto`
   through the installer's equivalence check? (Section 0.1.)
2. ~~**Halt files inside the prod clone** are not gitignored.~~ **Closed
   (corrected 2026-10-07):** `.gitignore` has ignored `/ops/HALT*.md`,
   `/ops/halts/` and `/ops/heartbeat.json` since commit `23eb7bc`
   (2026-09-28). The runner reads the halt at run time, so ignoring the files
   cannot let a standing halt be skipped. This item was stale from that commit on.
3. **Key file location** (section 0.2): keep `config/.env` in `~/Downloads`
   (unproven under launchd) or move it to `~/.config/quantt/`?
