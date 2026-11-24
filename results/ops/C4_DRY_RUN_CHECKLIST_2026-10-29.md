# C4 dry run on its own Alpaca paper account: the team lead's checklist (2026-10-29; updated 2026-11-03)

> **For the team lead. Nothing here has been run on the VM, and nothing is armed.**
> C4 (CEF trial 52) was fast-tracked on 2026-10-28/29 with every gate kept (docs/SYSTEM.md §5,
> 2026-10-29). **Updated 2026-11-02:** the integration (`c4-integrate`) is merged onto main's
> release-20261102-1 on branch **`c4-rel`**. That branch carries C4's whole path, dark: spec
> **`c4_families.v5.20261103`** (since 2026-11-03: v4.20261102 plus CEF trial 54's `level_signal`, PASSED,
> which adds ` level z_share=0.5000 s_z=... s_L=...` to every weight reason; CEF trial 53 amendment 1's
> `sizing_multiplier` **1.26**; the core's halve/kill
> levels, report only; the corporate-action gate in `report`, as the core, by the team lead's
> 2026-11-02 ruling), the data path, the per-sleeve runner, `BOOKS["c4"]`, its book json and its
> installer units. The core is proved byte-identical to 862b1d0 (below). Release is the team
> lead's. C4 spends no trial; the CEF counter is 53 because of trial 53, not C4.
> **Updated 2026-11-03:** release-20261103-1 is 336df9d (`git rev-parse release-20261103-1^{commit}`;
> merged to main as f27ef81; *corrected 2026-11-03: this line first said f27ef81 was the release*),
> with the core at **`cef_discount.v9.20261102`, ×1.30**. That release was GO for the core only.
> **release-20261103-2 is de75da4** (branch `c4-arm-prep`, merged as f7f7be5): QR1's probe read and
> step 6's opening-session check, QR3's specs named everywhere, ET1's C4 install scan of every
> book's units. Branch `c4-arm-gate` makes QR1 a CODE gate (step 6 below); `--book c4 --armed`
> waits for the release that carries it. The spec ids and multipliers on this page are checked
> against the specs by `ops/tests/test_book_text.py`.
>
> **Every step marked TEAM LEAD RUNS needs the VM, a key or an account.** No agent runs it.

Reproducer for every claim on this page (offline, no network, no keys):

```bash
python3 -m pytest quantt/session/tests/test_c4_book.py quantt/session/tests/test_c4_ca_unresolved.py \
  quantt/deploy/tests/test_install_vm_books.py quantt/session/tests/test_panels_noop.py \
  quantt/collect/tests/test_collect_books.py scripts/cef/tests/test_c4_paper_benchmark.py \
  quantt/tests/test_alpaca_probe.py quantt/session/tests/test_c4_keys_noop.py
```

The VM install wrapper used below is `docs/RUNBOOK.md` §8.3's. Every VM command is run by the
team lead, on the VM, reached through its ssh alias (written `quantt-vm` here):

```bash
qi() { sudo env PYTHONPATH=/home/quantt/prod/quantt-alpaca \
         /home/quantt/venv/bin/python -B -P -m quantt.deploy.install_vm "$@"; }
```

## What is proved before any of this

| claim | how | status |
|---|---|---|
| The core's session on `c4-rel` is 862b1d0's (main, release-20261102-1), built by `default_deps` from the released book json (gate in report, hold on) and with the gate block removed: exit, plan.json, plan_sha, orders, targets, refusals, run record, nav_gate.csv, send.json and what was sent | `quantt/session/tests/test_panels_noop.py`, synthetic panel (never skips) and the laptop's real panel with the live v8 spec; pins made in a `git archive 862b1d0` tree, unseeded and under PYTHONHASHSEED 1 | [V] 2026-11-02 |
| The core's own no-op pins are unchanged and pass | `test_combine_noop.py`, `test_missing_nav_hold.py`, `test_sizing_multiplier_noop.py`, untouched by `c4-rel` | [V] 2026-11-02 |
| C4's four optional keys, absent, are 66ec3df's 13-name book | `test_c4_keys_noop.py`, now on the core's pre-trial spec from git at 35b429f; runs on the laptop's real panel | [V] 2026-11-02 |
| The core's install is cee16ad's installer's | `quantt/deploy/tests/test_install_vm_books.py` | [V] 2026-10-29 |
| A C4 session in DRY decides from `data/cef_c4/` only, at ×1.26 (every weight target says `smult=1.2600`) | `test_c4_book.py`, fixture panel | [V] 2026-11-03 |
| The fidelity gate passes on the raised spec, and H11 reads the account's book (1.26 × the unit book capped at 1.90/1.26) | `python3 scripts/cef/c4_paper_benchmark.py run` → `results/cef/c4/c4_paper_benchmark_2026-11-02.txt` | [V] 2026-11-02 |
| `ca-ack --book c4` refuses another book's state directory before any read | `test_c4_book.py::test_c4_ca_ack_refuses_another_books_state_dir_before_any_read` | [V] 2026-11-02 |

## The corporate-action mode: DECIDED, `report` (team lead, 2026-11-02)

**Ruled 2026-11-02 on the measurement below: C4's gate runs in `report`, the same as the core,
until the ISIN fix and the re-ruling of the unresolved rows land.** The book json's
`corporate_actions._mode_report_note` cites the ruling and says how to RESTORE `halt` (together
with the core); `test_c4_ca_unresolved.py::test_the_deployed_c4_book_sets_report_until_the_unresolved_rows_are_re_ruled`
pins it. Report records every event in `plan.json` and the run record, prints it and sends
anyway; a failed read is UNMEASURED, never clear.

What `halt` would do, measured before the ruling (when C4's book json still set it) on a synthetic replica of the three unresolved rows the core's gate hit on 2026-11-02
(ids, types, dates and missing fields from the core's own preview record of session 2026-11-03;
`quantt/session/tests/test_c4_ca_unresolved.py`, the real parser and the runner's step 3b):

| C4's account | sessions 2026-11-03 … 11-13 | why |
|---|---|---|
| **flat** (the dry sessions: DRY_RUN sends nothing) | **refused on 2026-11-03 only** (the JAGX merger, acquiree missing, effective 11-02); CLEAR from 11-04, the three recorded as unresolved | a flat book's names are all target-only, window [as-of, session] |
| **held** (after arming; fills before 10-30) | **refused on every session**, on all three | a held name's window reaches back to its last fill, and under `halt` nothing trades to move it |

So `halt` does not refuse **every** dry session on these three rows. It refuses many on the
market's other unresolved rows: on every unresolved row in the core's 2026-11-02 read (43 rows),
a flat C4 book would have been refused on **17 of the 23 sessions 2026-10-01 … 11-02**, and rows
already listed refuse 11-03, 11-09 and 11-10 [U: the feed as read on 2026-11-02, not as it stood
on each date; rows are revised and backfilled. Measured by the scratch replay of that record
through `corp_actions.blocking_events`, not committed]. **Re-measure at run time**: each refused
decide names its rows in `<D>/plan.json` `refusals`, and `corporate_actions.unresolved` lists
every one and whether it would have blocked. Under `report` those rows are in
`corporate_actions.blocking` with the session going on. When `halt` is restored, a held C4 book
refuses every session on each new unresolved row in a long-window role until it is `ca-ack`ed
(RUNBOOK §6.1): read the measurement again then.

## The steps

**0. Release and the core first. TEAM LEAD RUNS.** Merge `c4-rel` to main through a PR, run
`/release-check` on that commit, tag it (`<T>`), and install the CORE at `<T>` on the VM as for
any release (`docs/RUNBOOK.md` §8.6). Both books run from the one prod clone at one tag: `--book
c4` never checks the clone out, and refuses unless the clone is already at `<T>`. The local spec
revert tags `spec-c4_families.v1.20261029` and `spec-c4_families.v2.20261101` are on this laptop
only; push them with the release if they should travel.

**1. The vault secrets. TEAM LEAD (done, per the team lead; NOT VERIFIED).** `alpaca-c4-key-id`
and `alpaca-c4-secret-key` in the vault the core uses, holding the spare connector paper
account's keys (docs/SYSTEM.md §5, 2026-11-02). Step 4b verifies that the VM read both. For step 3
on the laptop, `config/.env` also needs `ALPACA_C4_KEY_ID` and `ALPACA_C4_SECRET_KEY`:

```bash
python3 -m quantt.broker.alpaca_probe --check-keys --book c4      # SET / NOT SET, never a value; no network
```

**2. Seed `data/cef_c4/` with the IGR ruling. TEAM LEAD RUNS** (laptop, a dev tree at `<T>`,
read-only on `data/`; then the VM):

```bash
git -C <dev tree> checkout <T>
python3 scripts/cef/data_books.py seed-c4 --from data/cef_families --out ~/c4_seed \
  --bar-rulings results/cef/c4/c4_seed_rulings_2026-10-29.json
python3 -c "import json; m=json.load(open('$HOME/c4_seed/seed_manifest.json')); print(m['treated_closes'])"
scp -r ~/c4_seed quantt-vm:                 # cef_prices.parquet, cef_nav.parquet, seed_manifest.json
ssh quantt-vm 'ls -l ~/c4_seed && sha256sum ~/c4_seed/*.parquet'
```

Expect exit 0, and `treated_closes` = IGR 2026-07-29, 08-04, 08-07, 08-11 (`rebase`, factor 3) and
nothing else. Rehearsed on 2026-10-29 into a scratch directory: exactly those four; prices 401,688
rows and NAV 325,588 rows to 2026-10-09; sha256 `3fb68e38…` and `c7073db8…`; ruling `ba09b7c4…`
[V, laptop `data/cef_families` as of 2026-10-29]. Re-check the hashes against your run, not
against these. The installer refuses a seed whose manifest does not name the tag's ruling and
frozen universe by sha256, or whose files do not match it, and seeds `data/cef_c4/` only where
it is absent.

**3. Re-derive the cap against the shared account's margin. TEAM LEAD RUNS** (laptop; the spec's
`_max_gross_stress_note`, ruling 3):

```bash
python3 -m quantt.broker.alpaca_probe --book c4      # read-only; writes results/ops/alpaca_probe/<date>_c4.json
python3 scripts/cef/c4_paper_benchmark.py recap \
  --probe results/ops/alpaca_probe/<date>_c4.json --mark-sensitivity <the lab book's>
```

It prints the rule's cap, the spec's `max_gross_stress` and `same_as_spec`, and one verdict:
- **exit 0, `SAME`**: the rule gives the spec's cap;
- **exit 2, `OVERRIDE ON RECORD`**: the rule gives less, and a team-lead override on record names
  this exact w5 and both caps (`results/cef/c4/c4_cap_override_*.json`, matched on content; an
  edited file is refused). It prints the ruling's citation. For `c4_families.v5.20261103` the rule
  gives 1.80 and the team lead kept 1.90 (`docs/SYSTEM.md` §5, "Team lead, 2026-11-03 — C4 v5's
  gross cap");
- **exit 1, `STOP`**: any other mismatch. A new spec id (`/spec-change`) and a release, or a new
  ruling with its own record, before C4 trades on that cap.

The w5 is the LIVE spec book's, taken from the committed benchmark output: the blend's on v5, the
z book's only when the spec carries no `level_signal`. `recap` refuses an output made on another
spec file, naming both sha256s. Until 2026-11-03 it read the z book's w5 whatever the spec was
(the release-check of e41f10b). True on its date only: run it again on the day of the arming go
(step 6).

**4. Install C4 UNARMED (DRY_RUN=1). TEAM LEAD RUNS** (on the VM, a weekday outside 15:30-16:00
ET, which the installer refuses):

```bash
ssh quantt-vm
sudo ls -d /etc/systemd/system/quantt-c4* /run/systemd/system/quantt-c4* 2>/dev/null   # nothing yet: any output = inspect first
qi --tag <T> --vault <V> --book c4 --eod-from <YYYY-MM-DD> --seed-from /home/<admin>/c4_seed            # DRY RUN: read every check and unit
qi --tag <T> --vault <V> --book c4 --eod-from <YYYY-MM-DD> --seed-from /home/<admin>/c4_seed --apply --enable
systemctl list-timers 'quantt-*' --no-pager              # both books' timers
systemctl cat quantt-c4-session.service | grep -E 'DRY_RUN|--book'   # expect DRY_RUN=1 and --book c4
```

Never `--armed` here. `--eod-from` is the date C4's paper account was first funded: REQUIRED,
no default, yours to state. Installed: seven `quantt-c4-*` units, state
`/home/quantt/quantt_state/c4`, keys `/run/quantt-c4/alpaca.env`, panels `data/cef_c4/`. None of
the core's units is touched.

**4b. Confirm the C4 key service fetched BOTH secrets. TEAM LEAD RUNS.** Metadata only: never
`cat`, `grep` or copy the file.

```bash
systemctl status quantt-c4-secret.service --no-pager | head -5      # "active (exited)"
sudo stat -c '%n %U:%G %a %s bytes %y' /run/quantt-c4/alpaca.env    # quantt:quantt 600, size > 0
sudo tail -n 3 /home/quantt/quantt_state/c4/logs/secret.out.log     # "wrote /run/quantt-c4/alpaca.env (mode 600):
                                                                    #  ALPACA_C4_KEY_ID, ALPACA_C4_SECRET_KEY from azure-keyvault"
sudo tail -n 20 /home/quantt/quantt_state/c4/logs/secret.err.log    # empty
```

`quantt.deploy.boot_secrets` prints the variable NAMES it wrote, never a value, and fails unless
the vault returned exactly the two names asked for. Both names on that line = both secrets
fetched. A failure leaves the service inactive; every C4 job retries it (`Wants=`).

**5. Five sessions of DRY run. TEAM LEAD RUNS the reads**, each trading day after 16:30 ET:

```bash
D=<session date>
ssh quantt-vm "sudo tail -n 30 /home/quantt/quantt_state/c4/data.log"
ssh quantt-vm "sudo tail -n 60 /home/quantt/quantt_state/c4/logs/session.out.log"
ssh quantt-vm "sudo /home/quantt/venv/bin/python -c \"import json,sys; p=json.load(open(sys.argv[1])); \
  ca=p.get('corporate_actions',{}); print(p['status'], [r['gate'] for r in p['refusals']], 'orders', len(p['orders']), \
  'ca', ca.get('status'), [u['id'][:8] for u in ca.get('unresolved',[]) if u['blocks']], \
  'dd', p.get('drawdown',{}).get('status'), 'missing_nav', p.get('missing_nav',{}).get('missing'), \
  'opening_session', p.get('opening_session'))\" \
  /home/quantt/quantt_state/c4/$D/plan.json"
ssh quantt-vm "sudo tail -n 3 /home/quantt/quantt_state/c4/verify.log"
python3 -m quantt.broker.alpaca_probe --book c4          # laptop, read-only: positions 0, open orders 0
```

Expected on each day:

- `data.log`: the first night's `fetch_daily --data-book c4` exits 0, or 6 (`SPIKE-REVERT`, an
  unruled split-like bar). If IGR's four bars come back from Yahoo, the standing rule needs a new
  ruling; until then gate 5 refuses every C4 session, **including a day a NAV is also late**:
  exit 6 outranks the INCOMPLETE exit 4 since the release-check of 8b14298 (before it, a late NAV
  turned the 6 into a 4, which the missing-NAV hold accepts at the final check, and C4 decided on
  the unruled bar). The collector then records the spike flag and leaves `prices_nav` unfinished.
- **The price basis (2026-11-04).** The first nightly fetch of 2026-11-03 wrote IGR's
  2026-05-04..09-04 closes split-adjusted (x3) against its unadjusted NAV. Since then the fetch
  puts ruled splits' pre-ex rows on the NAV's basis and refuses (exit 7, `BASIS-STEP`, nothing
  written) any split-like step against the stored rows; `data_books.py repair-basis --book c4`
  repairs the window that fetch wrote, run once on the VM before the next collect (TEAM LEAD RUNS). A new split in any C4 fund
  refuses until ruled in `results/cef/c4/c4_fetch_split_rulings_2026-11-03.json`.
- **After the first fetch, compare the replaced rows with the seed.** The fetch replaces every
  seeded row in its six-month window with Yahoo's. Look hardest at IGR (1:3 reverse split,
  2026-09-08) and the split-ruled BTO, TYG, NXG and EMO. The spike guard catches a spike that
  reverts, not a step. Any step: stop, and rule on it before arming. UNMEASURED: no network here.
- The evening decide is PLANNED (exit 6) on C4's 74 at ×1.26, and the 15:52 send is DRY (exit
  10). The gate is in `report`: a day whose `corporate_actions.status` is BLOCKING (an
  UNRESOLVED row in the window, as on 11-03) still decides and sends DRY; read which rows, and
  note it for the re-ruling. A REFUSED decide now means another gate.
- `drawdown`: UNMEASURED naming `eod_equity.csv` until the collector has written a row, then
  measured against the core's 0.12 / 0.18, report only.
- `missing_nav` naming any late NAV, held at the final check.
- Alpaca shows no positions and no orders on the account.
- Measure, for the arming go: the 74-name fetch time against the 25-minute cap; memory on the
  1 GiB VM when both books run; how often NAVs arrive late. All UNMEASURED today.

**6. The arming go. TEAM LEAD'S, every line.**

- **No other runner may be armed on C4's account** (CLAUDE.md order-path rule 1's 2026-10-27
  exception lets the autonomous research loop trade the agent-lab account, which since
  2026-10-28 is the spare account C4 uses; gates 6 and 9 assume one runner per account). Read
  only, the same day as the go, and stop on any unexpected line:

  ```bash
  # laptop: the loop and any launchd job
  launchctl list | grep -i quantt                          # expect com.quantt.research-loop only (no session job)
  for f in ~/Library/LaunchAgents/*quantt*.plist; do echo "== $f"; \
    plutil -p "$f" | grep -E 'quantt\.session|quantt/session|DRY_RUN|QUANTT_ENV_FILE|QUANTT_STATE_DIR'; done
                                                           # expect: no plist runs quantt.session
  test -e ~/quantt_loop/config/.env && echo "STOP: a key file in the loop clone" || echo "no key file in the loop clone"
  find ~/quantt_state ~/quantt_loop -maxdepth 3 -name AUTO_ARMED -print 2>/dev/null
                                                           # expect none outside cef/ (the laptop's retired core,
                                                           # its jobs unloaded: the launchctl line above shows it)
  # the VM: only the core's and C4's units, each on its own key file
  ssh quantt-vm 'systemctl list-unit-files "quantt-*" --no-legend --no-pager; \
    for u in $(systemctl list-unit-files "quantt-*.service" --no-legend | cut -d" " -f1); do \
      echo "== $u"; systemctl cat "$u" | grep -E "QUANTT_ENV_FILE|DRY_RUN|--book"; done; \
    sudo find /home/quantt/quantt_state -maxdepth 2 -name AUTO_ARMED -print'
                                                           # expect /run/quantt-c4 only in quantt-c4-*; AUTO_ARMED only under cef/
  # the account: nothing open, nothing held, NOTHING EVER FILLED, before the first armed session
  python3 -m quantt.broker.alpaca_probe --book c4          # "positions: 0   open orders: 0"
                                                           # "opening_session: True   (no position, and none of
                                                           #  all N closed order(s) filled; ...)"
  ```
- **C4's first armed session must be an OPENING session, in the existing spare account**
  (the release-check of 336df9d, QR1; the rule: team lead 2026-11-03, "just flat it",
  `docs/SYSTEM.md` §5, PR #30; no new account, ruled 2026-11-02). Arming needs all
  three, the same day as the go:
  1. **`opening_session: True` under C4's rule.** C4's book json sets
     `execution.opening_session_fills = "own_prefix"`: only fills carrying C4's own order-id
     prefix make a session not an opening one (`quantt/session/run.py` `is_opening_session`), so
     the research loop's past fills in this account do not starve C4's first session. Without
     the key (the default `any`) one such fill, even flattened, would open C4 from flat at the
     band EDGE: 28-42% of full target and net long +4.7% to +11.1% (the release-check, on
     `data/cef_families` to 2026-10-09, spec v4 [V there; not C4's seeded panel]).
  2. **The account flat**: no position of any origin (positions always count) and no open order
     that is not C4's.
  3. **No other runner armed on the account** (CLAUDE.md rule 1's 2026-10-27 exception: the
     gate above, laptop launchd, the loop clone, the VM's units, AUTO_ARMED).

  **The runner enforces 1 and 2** (`quantt/session/run.py` THE FIRST-SESSION GATE,
  `OPENING_REQUIRED_BOOKS`): while no filled order in the account carries C4's `c4-` prefix, an
  ARMED C4 run that is not an opening session under its rule (a position), that finds another
  runner's open order, or that could not read the open orders (`first_session.status`
  UNMEASURED, never read as none) is REFUSED before its first order, under its own gate,
  `first_session` (release-check of 4f759a9: verify scores it a MISSED day, not a human's
  choice), naming the positions, the foreign fills (count, newest date and prefix) and the
  open orders; at the evening decide (plan.json) and again at the 15:52 send (send.json), under
  `refusals` and `first_session`. An unarmed run records the same reading (`action` `clear`, or
  `reported`) and prints a `FIRST SESSION (c4)` line. **No dry sessions (team lead 2026-11-03):**
  C4 arms at its install, so the probe below is the only read before the first armed decide, and
  that decide's own gate is the hard guard. 3 is the read-only gate above; the runner cannot see
  another machine's scheduler. The reads:

  ```bash
  python3 -m quantt.broker.alpaca_probe --book c4          # "positions: 0   open orders: 0" and
                                                           # "opening_session: True (... rule 'own_prefix' ...)"
  D=<the first armed session's date>                      # after that evening's decide
  ssh quantt-vm "sudo /home/quantt/venv/bin/python -c \"import json,sys; p=json.load(open(sys.argv[1])); \
    print(p['status'], p['opening_session'], p['first_session']['status'], p['first_session']['action'])\" \
    /home/quantt/quantt_state/c4/$D/plan.json"            # decided True CLEAR clear
  ```

  The probe applies the runner's own rule, the book's, to the account's positions and its WHOLE
  closed-order history, paged as the runner pages it (`alpaca_probe.opening_read`,
  `_closed_orders`; release-check of 4f759a9: it read the newest 500 only), and names every fill
  it read (symbol, time, order-id prefix) whether or not it counts; the plan is the runner's
  own reading of the real account on the decide, and is the AUTHORITY when the probe says
  UNMEASURED (more than 200 pages, or a page it cannot trust, which raises). **False** (a
  position, or a C4 fill), **UNMEASURED**, an open order that is not C4's, or
  `first_session.action` not `clear`: STOP. Armed, the runner refuses every session (exit 11,
  `first_session`) until the account is flat. NO OVERRIDE IS BUILT. REVERT of the rule: delete the book json key and its
  note (the default `any` then makes the loop's fills count again).

  The repository has no lab book today (`BOOKS` holds `cef` and `c4` only), and the loop's
  wrapper denies `python3 -m quantt.session` and holds no key file
  (`.claude/loop/run_research_loop.sh`). When a lab runner is built for this account, this gate
  becomes the place where the two are reconciled (docs/SYSTEM.md §5, 2026-10-28).
- Re-run step 3 that day: it must say `SAME` (exit 0), or `OVERRIDE ON RECORD` (exit 2) citing the
  ruling it matched. `STOP` (exit 1) means the new spec is released, or a new ruling recorded, first.
- The corporate-action mode is decided: `report` (team lead 2026-11-02, above). Arming does not
  change it; `halt` comes back with the core's, through a release.
- The halve/kill levels are the core's, report only, until a C4 derivation exists (ruled
  2026-10-30; spec v3). Nothing acts on them.
- Then `qi --tag <T> --vault <V> --book c4 --eod-from <YYYY-MM-DD> --apply --armed` and, as the
  service user, `sudo -u quantt touch /home/quantt/quantt_state/c4/AUTO_ARMED`.
- CLAUDE.md order rule 1 holds: the first armed session's order list is shown, and the go given
  on it.

## Running both books

- **Disable C4:** `sudo systemctl disable --now quantt-c4-session.timer quantt-c4-verify.timer
  quantt-c4-collect.timer`. To halt C4 alone, write `ops/HALT_c4.md` in the prod clone.
  `ops/HALT.md` halts both books.
- **A new release:** the core's install refuses to move the shared clone while a C4 timer is
  enabled or running, or a C4 job is busy. Disable C4's timers, install the core at the new tag,
  then re-run step 4's `--apply --enable` at the same tag.
- **The core's install does not look at C4's units on disk** (its scan is pinned to cee16ad's;
  the release-check of 336df9d, ET1), yet its `daemon-reload` loads them. Before every core
  install, TEAM LEAD RUNS on the VM, and reads every line:
  `sudo ls -d /etc/systemd/system/quantt-c4* /run/systemd/system/quantt-c4* 2>/dev/null`.
  Expected: only the seven `quantt-c4-*.service`/`.timer` files `--book c4` wrote, and no
  `quantt-c4-*.d/` directory. A C4 install scans every book's units and any other `quantt-`
  unit itself (`install_vm.scan_units`), and refuses, naming the file.
- **Not built yet:** `ops.prod_state` and `ops.orient` report the core's units only; the probe
  reads C4 only when named (`--book c4`); how the agent lab's sleeves net against C4's targets in
  the shared account is decided when the lab book is built (docs/SYSTEM.md §5, 2026-10-28).
