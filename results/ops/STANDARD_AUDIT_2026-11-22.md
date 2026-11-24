# Standard audit, 2026-11-22: the platform against `docs/STANDARD.md` Part A

**What this is.** The first audit against `docs/STANDARD.md` Part A (§0.4). It is
read-only. It changed no book, spec, gate, schedule or GitHub setting, and nothing on
the VM.

**What was measured.** The repository at `origin/main` 07532f2, read in the worktree
of branch `live-standard` at 877320c (PR #98: `main` plus the standard). The live
GitHub heads were read at 16:20 ET and matched those local refs: `main` 07532f2 and
`shadow` a8e944e. The VM was not read: no auditor may ssh to it. Where a check
depends on the VM's state, the note says so.

**Reproduce.** Run the saved workflow `.claude/workflows/standard-audit.js` with args
`{repo: <a checkout at 877320c>}`. Each verdict's own command or file and line is in
the JSON. The two re-measurements in §2 are `git show origin/main:shadow/deploy/nightly.sh`
and `gh api repos/<owner>/<repo>/rulesets` (and `/branches/shadow`, `/collaborators`).

**How.** There were five auditors, one per area of Part A. Each recorded a verdict per
check, with files and lines. An independent verifier then re-measured each area,
tried to disprove each verdict, and corrected the evidence or the work order where
the auditor was wrong. Workflow run `wf_039a7231-1cb` used 10 agents and 732 tool
calls. Its first run stopped at the account's usage limit at 14:05 ET before any
auditor finished; it was re-run from the start at 15:58 ET. Every check's full
evidence from both readers is in
[`standard_audit_2026-11-22.json`](standard_audit_2026-11-22.json), verbatim.

**Provenance.** The per-check figures are the auditors' and verifiers' measurements.
Each names its command or file and line. I have not re-run them all [S]. The figures
in §2 I re-measured myself [V].

---

## 1. The result

| | auditors' verdicts | read strictly by §0.3 |
|---|---|---|
| PASS | 1 | 1 |
| PARTIAL | 24 | 17 |
| GAP | 19 | 27 |
| NOT MEASURABLE | 1 | (counted as a gap) |
| **checks audited** | **45** | **45** |

- **A5.3 has no verdict.** It is the daily acknowledgement, which the team lead
  deferred to the first go-live proposal. It names no measurer.
- **The verifiers agreed with all 45 verdicts.** They corrected the evidence or
  added to the work order on 39 of them (table in §5).
- **Why the two columns differ.** §0.3 says a check whose named measurer does not exist
  counts as a gap. The auditors marked PARTIAL where the behaviour partly holds, but
  for seven of those the named measurer does not exist: A1.1, A1.4, A2.4, A2.6, A7.1,
  A7.4 and A10.1. A10.2's 2FA settings sit outside the repository, and the checklist
  that would record them does not exist.
- **The one PASS is A3.4:** shadow books never transmit an order. `main`'s `shadow`
  package holds no order-capable call, and `shadow/tests/test_boundary.py` passes.
  The VM runs the `shadow` branch's copy, not `main`'s (§2). The boundary files are
  identical on both branches today, but nothing keeps them so.

**Plain reading.** By the auditors' verdicts, 25 of the 45 checks are at least partly
met, mostly for the core book. What is missing is mostly of three kinds:

- **Measurers:** a CI check, a test, a verdict log or a rehearsal log.
- **Stop and recovery tools:** a stop-all command, a VM-failure procedure, an off-VM
  backup and a one-command rollback.
- **The events account:** it sits outside most of what was built for the core book.

The events account is set to be armed from Monday's list (`docs/SYSTEM.md` §5,
2026-11-20: "Show me Monday's list, I say go"), so its gaps come first.

---

## 2. Act first: who can change the events book's orders

Four of the five auditors found this independently, and every verifier confirmed it,
some of them in a wider form.

**What the code does, on `main` [V]:**
- `shadow/deploy/nightly.sh` runs `git fetch origin "${SHADOW_BRANCH}"` and then
  `git checkout --detach FETCH_HEAD` before every shadow run (18:50 and 20:50 Mon-Fri,
  07:20 Tue-Sat New York). The VM's shadow clone therefore runs whatever was last
  pushed to `shadow`, with no release, no `/release-check` and no tag.
- The events runner trades that clone's output. `install_events_vm.sh` points it at
  the shadow state directory (`SHADOW_STATE`, lines 75 and 216-238), and
  `quantt/sleeves/inputs.py:9-11` says the files are "written by another process, by
  another user, from a clone that follows an unreleased branch".
- `inputs.py` checks the format only: the symbol pattern at line 43, |weight| ≤ 2.0
  at line 44, and the on-time rule. It cannot tell a wrong but well-formed weight
  from a right one.
- The shadow user fetches the core account's trading key from the vault
  (`install_shadow_vm.sh:156`). The installer says that "code on the followed branch
  could fetch whatever that identity may read. The defence is who can push to the
  branch" (lines 26-31).
- The VM identity holds Key Vault Secrets User on the whole vault (`docs/RUNBOOK.md`,
  the `az role assignment` at lines 519-520; a verifier cited 513-514). Code on `shadow` could therefore read
  the keys of all three paper accounts (core, C4, events), not only the core key.

**Who can push to `shadow`.** Read from the GitHub API at 16:20 ET [V]:
- `shadow` is not protected (`protected=false`).
- The repository has two rulesets. One covers the default branch ("main: only the team
  lead updates it"). The other covers the `release-*`, `spec-*`, `pre-clean-slate` and
  `ibkr-final` tags. Neither covers `shadow`.
- Six accounts have push access, and four of them are admins. Two of the six are
  analysts' accounts. (The logins are not written here because this repository is
  public.)
- `origin/shadow` (a8e944e) is 4 commits ahead of `main` and 87 behind. Its
  `quantt/broker/alpaca.py`, which the shadow package imports, differs from main's.
- The analysts' rules (`CLAUDE.md`) forbid them to push anywhere but their own branch.
  But no setting enforces that for `shadow`.

**What it means.** Today the events units are `DRY_RUN=1`, so nothing is sent and the
risk is latent. Once the events book is armed and `AUTO_ARMED`, a push to `shadow`
by any of six accounts, or by a mistake, changes what a paper account trades the
next session. That push needs no review, and the code it carries can read every key
in the vault. This breaks A8.1 ("every unit on the VM runs from that one tag"),
A10.1 and A7.4. It also contradicts `docs/TEAM.md` §6: "Prod is out of reach either
way: the VM runs only a release tag".

**What can be done, smallest first.** The team lead decides; none of it has been done.
1. **A ruleset on `shadow`** like `main`'s, so that only the team lead updates it.
   It takes minutes on GitHub, can be undone, and closes the "who can push" half.
2. **A dated waiver under §0.5** naming A8.1 for the shadow clone, if the team lead
   wants the events book to keep trading branch-head decisions. It needs a reason
   and a date to ask again.
3. **Narrow the vault reach.** Give the shadow runner its own identity, or a vault
   holding only the key it needs, so its code cannot read the C4 or events keys.
   This is work on the Azure side.
4. **Move the events decision code under the release tag.** The events runner would
   then trade only decisions computed by released code. This is the full fix for
   A8.1, size M.

---

## 3. Ranked gaps

Ranked by what an incident would cost, and then by what other work depends on. Each
line is one work order; `docs/ROADMAP.md` Phase 7 carries them with an owner and a
status. Sizes are S (a day or less), M (a few days) and L (a week or more), as the
auditors estimated them.

### 3.1 They take effect on the day the events book is armed

| rank | work order | checks | size |
|---|---|---|---|
| 1 | Decide who can change the events book's orders: options 1-4 in §2 | A8.1, A10.1, A7.4 | S to M |
| 2 | Put the events account on every state surface: `ops.prod_state` (arming, tag, a two-scheduler WARNING per account), the banner, `ops.daily_page` | A8.5, A5.2 (interim) | M |
| 3 | Give the events account a P&L of record: an `events` entry in `quantt/collect/collect.py` BOOKS (the `eod_equity` and `account_snapshot` steps), then `pnl_report`, `daily_page` and the report units | A6.2 | M |
| 4 | Define and report HALVE and KILL for the events account (required keys in `ops/sleeves/events_sleeves.json`; `data_qa` and `risk_daily` with `--book events`) | A4.3 | M |
| 5 | A corporate-action gate in the events runner (`corp_actions.check` at PLAN and SEND). Correct `quantt/sleeves/ledger.py:16-19`, which claims the share-count check catches an action paper did not process; it cannot | A7.3 | M |
| 6 | One statement of who may merge, tag, install and arm. Today `docs/RUNBOOK.md:968` still grants agents the withdrawn 2026-11-02 authority "arming included", and `docs/SYSTEM.md` §5 has two rows from 2026-11-19 that disagree (lines 918 and 919). It needs a team-lead ruling, then the runbook and `CLAUDE.md` point at it | A1.3, A10.4 | S + ruling |

### 3.2 Stopping and recovering: high risk, and none of it exists

| rank | work order | checks | size |
|---|---|---|---|
| 7 | A stop-all command. For every account it writes the global halt, cancels every open order, reads back that none remain, and flattens only with `--flatten`. It runs from the VM and, broker-side, from the laptop, with tests. Then a monthly timed rehearsal on paper, logged | A4.1, A4.2 | M, then S |
| 8 | A written procedure for a VM failure on a trading day, per account: stop the VM from Azure, cancel and flatten (item 7), run from the laptop only after the VM reads disarmed, and the Alpaca web steps. Then a quarterly timed rehearsal and one tested rebuild | A9.1, A9.2, A9.3 | M, S, L |
| 9 | A daily copy of every state directory off the VM, with a sha256 manifest and its own PASS/FAIL verdict. Plans, run records, verify logs, the events ledger and `shadow_state` exist nowhere else | A6.3 | M |
| 10 | One rollback command, `--to <tag>`, for core, C4, the reports and events. It replays each book's state through the older tag's gates first and refuses inside the send windows. Rehearse it | A8.3 | M |
| 11 | A verdict per job per run (PASS, FAIL or MISSED) for every unit, and a nightly checker that writes MISSED for a timer that did not fire. Then the dashboard page that shows every verdict and its age | A5.1, A5.2 | M, then L |
| 12 | Core and C4 verify compares the broker's positions with the plan's targets. A FAIL, or a missing verify, stops the next send until a person acknowledges it, as the events runner already does. Verify can run late for a missed day (today a missed 17:30 verify can never be run) | A6.1, A9.4 | M |

### 3.3 Order and data controls: high risk

| rank | work order | checks | size |
|---|---|---|---|
| 13 | Per-order limits (maximum shares, notional and ADV share) as required book-file keys, refused in all three send paths, one test per limit | A3.1 | M |
| 14 | Input checks: refuse an unverified repeat NAV on the core, or turn the stale-NAV gate on with a working referee; run C4's spike guard on the core refresh; add a split-like jump refusal for held events names; build a generated list of every live input and the check that refuses it | A7.1 | M |
| 15 | A cross-source price and NAV gate that refuses past a tolerance. It needs a team-lead ruling first, because `docs/SYSTEM.md` §5 (2026-09-28, "Two data sources disagree": "Report only ... It never blocks") rules the opposite, and a chosen second NAV source | A7.2 | ruling, then L |
| 16 | An import-boundary test in CI from the live entry points. Correct `docs/TEAM.md` §2's live-path list first: it omits `ops/halt.py`, `ops/common.py` (which loads the research backtester on every refresh), `scripts/cef/data_books.py` and `data_guards.py`, the C4 fetchers, `shadow/` and the report jobs | A2.1, A7.4 | M |

### 3.4 Medium risk

| rank | work order | checks | size |
|---|---|---|---|
| 17 | A rules-in-force table at the head of `docs/SYSTEM.md` §5, with a `doc_audit` check that each row points at a real ruling | A1.3 | M |
| 18 | Remove the stale facts from `CLAUDE.md` (lines 7-9, 97-99, 251-253, 323-325), which says it wins any conflict with a skill. Move the research-only rules to `.claude/rules/`. Record this as the first Part D review | A1.4 | S |
| 19 | An events-runner section in `docs/RUNNER.md`: which gates run at PLAN and SEND, what replaces gate 5, the infinite dollar gross ceiling, and the extra refusals. Fix gate 6's prefix, gate 9's list and the `quantt/deploy` row, with a test that every gate name is in the doc | A1.5 | S |
| 20 | One shared send-time gate composite for the core's late-market path and the events runner, so a gate fix lands for every book | A2.8 | M |
| 21 | A price collar on every non-auction order, refused outside a band around the plan's close | A3.2 | M |
| 22 | A maximum order count for core and C4, and a breach that writes a halt only a person clears | A3.3 | S |
| 23 | The core and C4 send only what the plan holds (`client_order_id`, symbol, side, qty ≤ planned), and verify FAILs on anything else | A3.6 | S |
| 24 | Each book's account id hashed in its book file; a runner refuses on a mismatch, so keys filed under the wrong book are caught | A3.5 | S |
| 25 | A durable release-check verdict per commit for every book (core, C4, events). The installers refuse a tag with no GO. Rewrite RUNBOOK §8.6 for every unit. Three of the last four releases reached the VM without the check the standard names | A8.2 | M |
| 26 | The release check runs each changed live-path test against the last tag and requires it to fail there. The PR template gains "moved code re-tested where it lands" and loses the trial and cost-grid items | A2.4 | M |
| 27 | An install and arming log written by every installer, `nightly.sh` and the `AUTO_ARMED` steps, read by `ops.prod_state` | A8.4 | S |
| 28 | A `BrokerClient` interface, the read-only client moved into `quantt/broker/`, and a test that nothing outside it calls a broker | A2.6 | M |
| 29 | A generated inventory of every switch (mode, limit, flag): its value at HEAD and at the release tag, its reader and its owner. CI fails on a key nothing reads. The book file's `limits` block is read by no code today | A2.7 | S |
| 30 | CI: type checks (strict per module, starting on the order path), a coverage floor that may only rise, and a lint for bare `except: pass` and coerce-to-zero on the live path | A2.2, A2.3, A2.5 | L, S, S |
| 31 | Access: a 2FA checklist (GitHub org, Azure, each Alpaca login); a key-rotation interval, procedure and log covering every secret unit; one access table; Bash deny rules for key files; and the key ban in three agent briefs | A10.2, A10.3, A10.4 | S, S, M |
| 32 | A per-source terms table and a team-lead ruling per data source. The desk's own reading says Yahoo and CEFConnect forbid this use | A7.5 | M |
| 33 | Correct the small contradictions between the documents and the code: F7's dead citation, F8's stale "for this release only" note, F13's pointer to a missing `ops/preflight.py`, F15's phase-4 status, F16's events README | A1.5 | S |

### 3.5 Already built: merge, then the clean-up

| rank | work order | checks | size |
|---|---|---|---|
| 34 | Review and merge PR #99. It holds `ops/checkout.py` (a checkout behind `origin/main` is named at session start) and `ops/branch_inventory.py` (every branch and worktree, with its reason or "none"). A1.2's text now lists the reasons the inventory uses. Then the archive-tag-and-delete pass, on the team lead's go for the concrete list | A1.1, A1.2 | S |

---

## 4. Findings outside the checks

The verifiers confirmed all of them. Where several auditors found the same thing it
is listed once.

| # | finding | risk | where it lands |
|---|---|---|---|
| F1 | The events book trades decisions from unreleased `shadow`-branch code that can read every vault secret (§2) | high | rank 1 |
| F2 | The events account is invisible to `ops.orient` PROD, the SessionStart banner, the status line and `ops.daily_page` (`ops/prod_state.py` builds its books from `install_vm.VM_BOOKS = {cef, c4}`) | high | rank 2 |
| F3 | The events account has no P&L of record. The collector writes Alpaca's EOD history for cef and c4 only (`quantt/collect/collect.py:242-249`); events verify scores against the equity snapshot that `docs/RUNNER.md` calls unofficial | medium | rank 3 |
| F4 | Four documents disagree on who may merge, tag, install and arm, and `docs/RUNBOOK.md:968` grants agents arming authority withdrawn on 2026-11-09 | medium to high | rank 6 |
| F5 | `CLAUDE.md` states facts §5 has since reversed: two sleeves trading, prod "moving" to the VM, and the shadow runner "not built or approved yet". It also says it wins over any skill | medium | rank 18 |
| F6 | `docs/TEAM.md` §2's live-path list omits files the VM runs | medium to high | rank 16 |
| F7 | The book file's `limits` block is read by no code, and its note cites `src/deploy/risk.py:152`, a file that no longer exists | medium | ranks 29, 33 |
| F8 | The core's corporate-action gate is in report mode, and its note says "for this release only" (2026-11-02). Later rulings keep it in report mode, so the state is ruled, but the note is stale | medium | ranks 5, 33 |
| F9 | The events runner passes an infinite dollar gross ceiling to gate 8. Its only gross limit is 1.5× equity, which binds only when a set adds gross | low to medium | rank 19 |
| F10 | Core and C4 verify cannot run for a past day, so a missed 17:30 verify leaves that session unreconciled for good | medium | rank 12 |
| F11 | `ops/common.py`, on the live path, is an old simulator module. Importing it loads the research backtester, and it holds dead code with invented defaults (`fillna` with a fallback impact, zero-filled volume) | medium | rank 16 |
| F12 | The dashboard exporter named in the standard's scope does not exist; `dashboard/` holds a README and an empty folder | low | rank 11 |
| F13 | `ops/halt.py` tells the operator, inside the halt file itself, that `ops/preflight.py` enforces the halt. The file does not exist; the runners read halts directly | low | rank 33 |
| F14 | `ops/halt.py:97-98` has `except Exception: pass` while reading the alert settings. The halt itself still works | low | rank 30 |
| F15 | `docs/ROADMAP.md` phase 4 says "4.1–4.7 done" above a table that marks them open | low | rank 33 |
| F16 | `quantt/sleeves/deploy/README.md` says the events book has "never run against a broker". It has planned against its account since 2026-11-20 | low | rank 33 |
| F17 | `quantt-reports-secret.service` stays failed by choice (§5, 2026-11-20, "Skip alerts for now"), so `systemctl --failed` is never clean, and the collect units rely on failed state as their only signal | low to medium | rank 11 |
| F18 | `results/report/EVIDENCE_LOG.md` says both "none recorded [U]" (line 2742) and "release-check GO [V]" (line 3440) for release-20261103-4. The cause is that the release check stores no verdict | low | rank 25 |

**Process notes, not findings about the desk.**
- One auditor reports that a command it ran included `git ls-remote --heads origin`,
  which may have reached GitHub read-only. That was outside its no-network brief.
  Nothing was written.
- The workflow harness flagged text in the data-access results as instruction-shaped.
  It was the A10.4 evidence quoting `.claude/settings.json`'s deny rules, with nothing
  directive in it.

---

## 5. Every check, both readers

Area files: A1 and A8, repo and releases; A2, live code; A3 and A4, controls and
stopping; A5, A6 and A9, monitoring, records and recovery; A7 and A10, data and
access. "By §0.3" counts a check whose named measurer does not exist as a gap. The
last column summarises the verifier's note; the JSON holds both readers' full texts.

| check | area | auditor | verifier | by §0.3 | risk | size | what the verifier added or corrected |
|---|---|---|---|---|---|---|---|
| A1.1 | repo, releases | PARTIAL | PARTIAL | GAP | medium | S | The measurer is already built on PR #99; the work order becomes review and merge |
| A1.2 | repo, releases | GAP | GAP | GAP | low | S | Built on PR #99; its extra keep-reasons must match A1.2's text |
| A1.3 | repo, releases | GAP | GAP | GAP | medium | M | The first row should settle who runs releases and arming |
| A1.4 | repo, releases | PARTIAL | PARTIAL | GAP | medium | S | Adds `CLAUDE.md:97-99`; landmines 6 and 7 bind the live path, so they go to a live-path rule |
| A1.5 | repo, releases | PARTIAL | PARTIAL | PARTIAL | medium | S | The section must also record the infinite dollar ceiling and `first_session` |
| A2.1 | live code | GAP | GAP | GAP | high | M | Adds the `ops/common.py` → `src/backtest` edge |
| A2.2 | live code | GAP | GAP | GAP | medium | L | — |
| A2.3 | live code | GAP | GAP | GAP | medium | S | The auditor's proxy evidence for coverage was overstated |
| A2.4 | live code | PARTIAL | PARTIAL | GAP | medium | M | Adds C4 and events previews to the release check |
| A2.5 | live code | PARTIAL | PARTIAL | PARTIAL | low | S | Adds a coerce-to-zero at `scripts/cef/fetch_cef_distributions.py:179-180` |
| A2.6 | live code | PARTIAL | PARTIAL | GAP | medium | M | — |
| A2.7 | live code | PARTIAL | PARTIAL | PARTIAL | medium | S | `promotion_waived` is owner-dated |
| A2.8 | live code | PARTIAL | PARTIAL | PARTIAL | medium | M | The duplicate is two hand-written send-time lists (`run.py:2793`, `sleeves/run.py:595`), not `evaluate` |
| A3.1 | controls, stopping | GAP | GAP | GAP | high | M | The events `max_name_usd` limits an order only indirectly; the core has no per-name cap |
| A3.2 | controls, stopping | GAP | GAP | GAP | medium | M | The events runner has no `cls` mode; add a refusal for an unreadable quote |
| A3.3 | controls, stopping | PARTIAL | PARTIAL | PARTIAL | medium | S | The events order count moves from PLAN-only to the shared gate |
| A3.4 | controls, stopping | PASS | PASS | PASS | - | - | — |
| A3.5 | controls, stopping | PARTIAL | PARTIAL | PARTIAL | medium | S | C4's book note says the agent lab shares that account; whether each key maps to its account is not measurable from the repository |
| A3.6 | controls, stopping | PARTIAL | PARTIAL | PARTIAL | medium | S | Events verify never compares the broker's ordered quantity directly |
| A4.1 | controls, stopping | GAP | GAP | GAP | high | M | — |
| A4.2 | controls, stopping | GAP | GAP | GAP | medium | S | Also flag a newest rehearsal older than the last order-path commit |
| A4.3 | controls, stopping | PARTIAL | PARTIAL | PARTIAL | medium | S | The events account needs its EOD history collected first; size M, not S |
| A5.1 | monitoring, recovery | PARTIAL | PARTIAL | PARTIAL | high | M | Seven key services, not six; events verify writes no verdict on a day PLAN refused |
| A5.2 | monitoring, recovery | GAP | GAP | GAP | high | L | Interim minimum: events in `prod_state` and `daily_page` |
| A6.1 | monitoring, recovery | PARTIAL | PARTIAL | PARTIAL | high | M | The send-time position check narrows the gap but does not close it |
| A6.2 | monitoring, recovery | PARTIAL | PARTIAL | PARTIAL | medium | M | More urgent than written: arming is planned on Monday's list |
| A6.3 | monitoring, recovery | GAP | GAP | GAP | high | M | Orders, fills and `eod_equity.csv` can be rebuilt from Alpaca; plans, run records, the events ledger and `shadow_state` cannot |
| A7.1 | data, access | PARTIAL | PARTIAL | GAP | high | M | The sleeve refuses some non-finite computed values; their ranges are untested |
| A7.2 | data, access | GAP | GAP | GAP | high | L | `docs/SYSTEM.md` §5 rules "Report only" on two sources disagreeing; that ruling must be superseded first |
| A7.3 | data, access | GAP | GAP | GAP | high | M | The events account holds no spin-off sleeve (`spinoff_first_week` is shadow-only) |
| A7.4 | data, access | PARTIAL | PARTIAL | GAP | medium | S | An allowlist of TEAM.md's three files would fail at once; it must start at five |
| A7.5 | data, access | GAP | GAP | GAP | medium | M | `docs/DATA.md` omits every source behind the events account |
| A8.1 | repo, releases | PARTIAL | PARTIAL | PARTIAL | high | M | Adds: the installer should refuse a tag that is not `release-*`; the shadow clone loads its own Alpaca client with a key |
| A8.2 | repo, releases | PARTIAL | PARTIAL | PARTIAL | medium | M | Adds `shadow/` to the review scope and the removal of `RUNBOOK.md:968` |
| A8.3 | repo, releases | GAP | GAP | GAP | high | M | The replay must cover every gate and the events runner's records |
| A8.4 | repo, releases | PARTIAL | PARTIAL | PARTIAL | low | S | `nightly.sh` should log each commit it checks out; shadow-only evidence entries belong on main |
| A8.5 | repo, releases | PARTIAL | PARTIAL | PARTIAL | high | M | — |
| A9.1 | monitoring, recovery | GAP | GAP | GAP | high | M | `RUNBOOK.md:863-868` already has laptop steps for the core; build on them |
| A9.2 | monitoring, recovery | GAP | GAP | GAP | medium | S | — |
| A9.3 | monitoring, recovery | GAP | GAP | GAP | medium | L | `eod_equity.csv` is rebuilt from Alpaca, so it is not VM-only state |
| A9.4 | monitoring, recovery | PARTIAL | PARTIAL | PARTIAL | medium | S | Events behaves correctly; the gap is core and C4 |
| A10.1 | data, access | PARTIAL | PARTIAL | GAP | high | S | The vault role is vault-wide, so all three accounts' keys are reachable |
| A10.2 | data, access | NOT MEASURABLE | NOT MEASURABLE | GAP | medium | S | Under §0.3 it counts as a gap until the checklist exists |
| A10.3 | data, access | GAP | GAP | GAP | medium | S | Rotating the core key without restarting the shadow secret unit leaves shadow on a revoked key; no steps for C4 or events |
| A10.4 | data, access | PARTIAL | PARTIAL | PARTIAL | medium | M | The accepted installer gap gives `quantt` a route to root at install time |

A5.3 (the daily acknowledgement) is deferred by the team lead and names no measurer, so it was not audited.
