# The standard: a clean platform, and what real money adds

> Asked for by the team lead on 2026-11-22: the infrastructure and the strategy are
> "very disorganized and not done at the proper standard", and capital cannot be
> deployed on them. This file says what "done properly" means. The rulings that
> shaped it are `docs/SYSTEM.md` §5, "Team lead, 2026-11-22". The external sources
> are Part C; their quotes and status are `docs/REFERENCES.md` §12st.
>
> **It holds no status.** Whether a check passes is measured on the day (§0.3) and
> reported by the audit (§0.4), never written here.

## 0. How to use it

### 0.1 Two parts

| part | applies to | when |
|---|---|---|
| **A. The platform** | everything on the desk that runs on a schedule or can send an order, paper and shadow included | now: it is the target of the clean-up |
| **B. Real money** | a book proposed for real capital | at its go-live proposal (`/go-live`). Real capital waits for a real-money broker (B1) |

**Scope** (team lead, 2026-11-22: "everything on the desk"): the core CEF book, C4,
the events account and its sleeves, the b6 benchmark, the shadow runner and its
books, the nightly collectors, the report jobs and the dashboard exporter. Research
code under `scripts/` is in scope only where the live path calls it (`docs/TEAM.md`
§2).

### 0.2 What it does not gate

**Research carries on as it is** (team lead, 2026-11-22). Idea, Explore and Paper
follow `docs/MISSION.md` §7 unchanged. The standard gates two things only:

- **a change to the platform**, which must not move it further from Part A;
- **real money**, which needs Part A and Part B to pass.

### 0.3 How a check is measured

Each check names its measurer: a CI job, a test, a script, a skill's verdict, or a
logged rehearsal. If the named measurer does not exist, the audit counts the check
as a gap. A check passes only when its measurer says so on the day it is read.
Policy limits written here (a rehearsal interval, a branch's age) are choices, not
measurements. A level that depends on the market or the book (an order limit, a
risk budget) is derived where it is used and never written here (H14).

### 0.4 The audit

Gaps are found by an audit against this file: one reader per area of Part A, each
finding with its file and line, and a second reader trying to disprove each
finding. The result is a dated note, `results/ops/STANDARD_AUDIT_<date>.md`. Every
confirmed gap becomes a work order in `docs/ROADMAP.md`. The audit is repeated each
quarter (Part D) and after any incident.

### 0.5 Waivers

A check is waived only by a dated team-lead ruling in `docs/SYSTEM.md` §5 that names
the check, the book, the reason, and when it is asked again. A waiver nobody
recorded is a failure, not a waiver.

---

## Part A — the platform

### A1. One tree, one plan, one place for each rule

| id | check | why | measured by |
|---|---|---|---|
| A1.1 | Every session, human or agent, starts from `origin/main` or a branch made from it. A checkout behind `origin/main` is named at session start | On 2026-11-22 the main dev folder was 841 commits behind `origin/main` and held an untracked copy of `CLAUDE.md` from before 2026-11-09, so every session opened there loaded superseded rules [V, `git log --oneline HEAD..origin/main`] | orient TREES and the SessionStart banner: commits behind `origin/main` |
| A1.2 | Every local branch and worktree has a reason to exist: an open pull request, a lane branch (`docs/TEAM.md` §3), or a commit in the last 14 days. Four things are always kept, because deleting them would lose work or break a running job: uncommitted changes in a worktree (and that worktree's branch), the main folder, the tree at the newest release tag, and a branch a VM clone follows (`shadow`). Anything else is tagged `archive/<branch>` and then deleted | On 2026-11-22 the team lead's laptop held 199 local branches and 143 worktrees [V, `git branch`, `git worktree list`] | a read-only script listing each branch and worktree with its reason, or "none" |
| A1.3 | The rule in force on any subject can be found in one place | `docs/SYSTEM.md` §5 holds 41 dated ruling sections in 654 lines [V, 2026-11-22, counted on `origin/main` a624e13]; a later row supersedes an earlier one only where it says so, so the rule in force has to be reconstructed | a "rules in force" table at the head of §5, one row per subject, pointing at the ruling that holds; `ops.doc_audit` checks that every row points at a ruling that exists |
| A1.4 | `CLAUDE.md` holds only rules that do not change; anything about one path lives in `.claude/rules/` | `CLAUDE.md` is loaded into every session, and a long one is followed less reliably | the quarterly review (Part D) |
| A1.5 | A written description of every control exists and matches the code | [KNIGHT] ¶9C: no "adequate written description of its risk management controls" | `docs/RUNNER.md` and this file; the audit compares them with the code |

### A2. The live path and its code

| id | check | why | measured by |
|---|---|---|---|
| A2.1 | The live path is the list in `docs/TEAM.md` §2. Live code imports no research code except a named allowlist, which only shrinks | Team lead, 2026-11-22; `docs/MISSION.md` §8.7 | CI: an import-graph test. Its first allowlist is the three files in `docs/TEAM.md` §2 |
| A2.2 | Strict type checking passes on the live path | Team lead, 2026-11-22 | CI: a type-check step |
| A2.3 | Test coverage of the live path is at or above a floor kept in the CI config; the floor only rises | Team lead, 2026-11-22 | CI: a coverage step |
| A2.4 | Every live-path change ships with a test shown to fail against the old behaviour, and code that moves is re-tested where it lands | `CLAUDE.md`, hard rules: code; [KNIGHT] ¶14 | the pull-request template; `/release-check` |
| A2.5 | No silent fallbacks on the live path: no bare `except`, no `except: pass`, no invented default for missing data | `CLAUDE.md`, hard rules: code | CI: a lint rule |
| A2.6 | One broker interface. Only the broker adapters talk to a broker; every runner sends through the interface; a paper adapter and the real-money adapter both implement it | Team lead, 2026-11-22: the standard is broker-neutral | CI: a test that only `quantt/broker/` imports an HTTP or broker client |
| A2.7 | Every switch in a book file or spec that changes behaviour is listed with its state and owner. Code behind a switch that has been off since the last quarterly review is removed or re-justified | [KNIGHT] ¶9D: no controls "to prevent the activation of code no longer intended for use" | a generated list of switches; the quarterly review |
| A2.8 | Every runner that can send an order uses one gate module | a fix to a gate lands once, for every book | the audit |

### A3. Pre-trade controls

The nine gates (`docs/RUNNER.md`, "The gates") are the base, applied by every runner
that sends (A2.8). The limits below are keys in each book file, derived from the
book and the market, never swept. **A missing limit refuses the order**, as a
missing price does ([FIA] §1.1). A breach refuses the order and names the limit.

| id | check | why | measured by |
|---|---|---|---|
| A3.1 | Per-order limits: maximum shares, notional, and share of average daily volume | [15C3-5] (c)(1)(ii); [RTS6] Art 15; [FIA] §1.1 | tests of the gate, one per limit |
| A3.2 | A price collar on any order that is not a closing-auction order, against a named reference price | [RTS6] Art 15(1) | tests of the gate |
| A3.3 | A maximum number of orders per account per session. Above it nothing is sent, and the book stays stopped until a person re-arms it | [RTS6] Art 15(1), 15(3) | tests of the gate |
| A3.4 | No set of orders is sent twice for one auction | `CLAUDE.md` order-path rule 2; [15C3-5] (c)(1)(ii) "duplicative orders" | gate 6's tests |
| A3.5 | A book reaches only its own account and endpoint. A paper book reaching a live endpoint, or one book's keys reaching another account, fails a test | `docs/RUNNER.md`, "Rules the code must obey" | the endpoint tests, per adapter |
| A3.6 | The orders sent are the orders the plan decided: the send compares its list with the plan's before sending, and VERIFY compares the broker's order list with the plan after | [KNIGHT] ¶21: no "control to compare orders leaving SMARS with those that entered it" | the runner's tests; VERIFY |

### A4. Stopping

| id | check | why | measured by |
|---|---|---|---|
| A4.1 | One command stops everything: across every account it cancels every open order and halts every runner, and with a flag it also flattens. It runs outside the runners, from the VM and from the laptop, and `docs/RUNBOOK.md` says how | [RTS6] Art 12; [FIA] §1.5; [FINRA] §II | the command's tests |
| A4.2 | It is rehearsed on paper every month and after any order-path change, and each rehearsal is logged with how long it took | a stop that has never been run is not known to work | the rehearsal log |
| A4.3 | The drawdown HALVE and KILL report on paper (team lead, 2026-10-19) and act on real money (B4) | | `docs/RUNNER.md`, "As built (2026-10-19)" |

### A5. Monitoring: the dashboard and the logs

Alerting stays the dashboard and the logs, on paper and on real money (team lead,
2026-11-22). **This departs from the sources** (Part C.2): [RTS6] Art 16 asks for
real-time alerts within five seconds, and [KNIGHT] ¶19 and ¶25 record a firm whose
errors were not alerts and whose monitoring "relied entirely on human monitoring".
With no alerts, the dashboard is the only alarm, so it has to show every failure.

| id | check | why | measured by |
|---|---|---|---|
| A5.1 | Every scheduled job writes one verdict per run: PASS, FAIL or MISSED. A job that did not run shows as MISSED; silence never reads as PASS | `docs/ROADMAP.md` 4.7; [KNIGHT] ¶19 | each job's verdict file; the audit lists jobs without one |
| A5.2 | One dashboard page shows the last verdict and its age for every account and every job | with no alerts, this page is the alarm | `dashboard/` |
| A5.3 | Whether a named person must acknowledge the last verdict before a real-money book sends again | Deferred to the first go-live proposal (team lead, 2026-11-22: "we arnt deploying capital anytime soon, we need to clean our infrastructure up") | — |

### A6. Reconciliation and records

| id | check | why | measured by |
|---|---|---|---|
| A6.1 | Every trading day, for every account, the broker's positions are compared with the positions the plan intended. A break is a FAIL, and that book sends nothing until it is resolved | `docs/SYSTEM.md` §4.2, "the broker is the fact"; [FIA] §4.1; [RTS6] Art 17 | each runner's VERIFY step |
| A6.2 | The P&L of record is the broker's end-of-day history | Team lead, 2026-10-19 | the P&L report |
| A6.3 | Every plan, order, fill and verdict is kept, complete, and copied off the VM every day | [RTS6] Art 17: records "complete, accurate and consistent"; the VM is one machine | the backup's own verdict (A5.1) |

### A7. Data

| id | check | why | measured by |
|---|---|---|---|
| A7.1 | Every input the live path decides on, and every value computed from one, has a check that refuses when it is stale or implausible and names it | `CLAUDE.md`, no silent fallbacks; [FIA] §3.1; [KNIGHT] ¶33 | gate 5 and the stale-NAV gate; the audit lists inputs without one |
| A7.2 | Prices and NAVs have a second source; a disagreement past a tolerance refuses | The second NAV source is open (team lead, 2026-11-18) | the data gate's tests |
| A7.3 | An unhandled corporate action refuses | `docs/RUNNER.md`, gate 5 | the corporate-action gate's tests |
| A7.4 | Live, research, test and simulated data are kept apart. Nothing that sends reads a laptop's `data/`, a test fixture or a shadow book's simulated fills | `docs/MISSION.md` §8.7; `CLAUDE.md` landmine 9; [KNIGHT] ¶33 (test data left in production) | A2.1's import test; the audit |
| A7.5 | Every live data source's terms allow the use made of it | `results/ops/CEFCONNECT_TERMS_OPTIONS_2026-10-19.md`, open | a team-lead ruling per source |

### A8. Releases and change

| id | check | why | measured by |
|---|---|---|---|
| A8.1 | Prod runs only a release tag of `main`, and every unit on the VM runs from that one tag | `docs/ROADMAP.md` phase 6; [KNIGHT] ¶15 | `ops.prod_state`, per unit |
| A8.2 | Every change to the live path is reviewed by someone other than its author, and `/release-check` passes on the exact commit that is tagged. The install follows the written steps in `docs/RUNBOOK.md` §8.6 | [RTS6] Art 11; [FINRA] §III; [KNIGHT] ¶15, ¶26 | the pull request's review; the skill's verdict, logged |
| A8.3 | The previous tag can be reinstalled with one documented command, rehearsed each quarter with A9. Before a rollback in an incident, check what the older code does with today's state | [KNIGHT] ¶27: uninstalling the new code "worsened the problem" | the rehearsal log |
| A8.4 | Every release, install and arming is logged | `results/report/EVIDENCE_LOG.md`; [FINRA] §II (retrievable code versions) | the log; the release tags |
| A8.5 | No account has two armed schedulers | `CLAUDE.md`, "Where it runs" | orient PROD's WARNING |

### A9. Recovery

A rehearsed procedure, not only a written one (team lead, 2026-11-22).

| id | check | why | measured by |
|---|---|---|---|
| A9.1 | A written procedure for a VM failure on a trading day: cancel every order, flatten, or run the session from a second machine; and the broker's own way of cancelling orders by hand when no machine can reach it | [RTS6] Art 14(1),(2); [FIA] §1.4 | `docs/RUNBOOK.md` |
| A9.2 | The procedure is rehearsed on paper each quarter, timed and logged | Team lead, 2026-11-22; more often than [RTS6] Art 14(4)'s annual test | the rehearsal log |
| A9.3 | The VM can be rebuilt from the repository and the vault alone: tested once, and again after any installer change | [RTS6] Art 14 | the rehearsal log |
| A9.4 | When the broker's API is down at send time, the session refuses and records MISSED | A5.1 | the runner's tests |

### A10. Access and secrets

| id | check | why | measured by |
|---|---|---|---|
| A10.1 | Only named people and the prod VM can send orders. Keys live only in the vault (VM) and `config/.env` (laptop): never in a tracked file, a log or a chat. The repository is public | `CLAUDE.md` order-path rule 5; [15C3-5] (c)(2)(iii) | a secret scan in CI |
| A10.2 | Two-factor sign-in on GitHub, Azure and every broker account | the desk's own choice; no source in Part C asks for it by name | the team lead's checklist |
| A10.3 | Keys are rotated on a schedule, and at once after any exposure | `docs/ROADMAP.md` 1.1 | the team lead's log |
| A10.4 | A list of everyone and everything with access that can change the book (GitHub admins, the VM's users, vault readers, broker logins). The VM's jobs run as a user without sudo; agents never read a key | [RTS6] Art 18(4); [FINRA] §IV; every seat's brief in `.claude/agents/` | the list; the audit |

---

## Part B — real money

Applies when a book is proposed for real capital. Part A must pass first.

| id | subject | requirement |
|---|---|---|
| B1 | Broker | The 2026-10-28 ruling stands: wait for Alpaca Canada, re-checked each quarter. The standard is broker-neutral (team lead, 2026-11-22): the chosen broker implements A2.6's interface and passes Part A against its own account in a dry run before the first real order |
| B2 | Execution | MOC; the paper `late_market` exception never applies (`CLAUDE.md` order-path rule 3). Borrow and locate are checked before each short; distributions owed on shorts and corporate actions are handled as the real account books them (`docs/MISSION.md` §8.5) |
| B3 | One risk budget | One combined risk budget across every real-money account, measured daily, with each account's limits inside it (team lead, 2026-11-22; [15C3-5] (c)(1)(i), limits "in the aggregate"). Its levels are set at the first go-live proposal |
| B4 | HALVE and KILL act | HALVE halves the next plan's gross. KILL sends nothing new, and only a person re-arms (team lead, 2026-11-22; [RTS6] Art 15(3); [FIA] §4.2) |
| B5 | Concentration and liquidity | Per-name limits as a share of equity and of average daily volume, sized to the capital proposed |
| B6 | Review | Agent review is enough: `quant-reviewer`, `/code-review` and `/release-check` (team lead, 2026-11-22) |
| B7 | Each strategy | The go-live proposal (`/go-live`, `go-live-reviewer`), plus: an independent re-derivation of its backtest on the harness (`backtest-request`); a day-by-day comparison of its paper record with the backtest on the same dates; and how many variants of the idea were tried, from `results/IDEA_LEDGER.md`, with the Sharpe deflated for them ([DSR]). The paper record is forward data nobody had seen and weighs more than a holdout already looked at ([PSEUDO]). The bar is the strategy's own (`docs/MISSION.md` §1.8) |
| B8 | First allocation | Set in each proposal; the sleeve ladder (team lead, 2026-11-18) is the default |
| B9 | Daily acknowledgement | Deferred to the first go-live proposal (A5.3) |

---

## Part C — sources

### C.1 What was read

Read on 2026-11-22; each quote, its status and its URL are in `docs/REFERENCES.md`
§12st. **None of them binds this desk.** 15c3-5 binds the broker, whose controls
stay under the broker's "direct and exclusive control", so the desk can neither see
nor set them. Its own controls have to stand on their own.

| key | source | what it is |
|---|---|---|
| [15C3-5] | SEC Rule 15c3-5, the Market Access Rule (17 CFR 240.15c3-5) | US rule for broker-dealers with market access: pre-trade capital, credit and order controls; annual review |
| [FINRA] | FINRA Regulatory Notice 15-09 | supervision and control practices for algorithmic trading; guidance, no new duty |
| [RTS6] | Commission Delegated Regulation (EU) 2017/589 (MiFID II RTS 6) | EU rule for firms trading algorithmically: testing, kill function, pre- and post-trade controls, monitoring, continuity, security, annual self-assessment |
| [FIA] | FIA, Best Practices for Automated Trading Risk Controls and System Safeguards, July 2024 | industry practice for automated trading controls |
| [KNIGHT] | SEC, In the Matter of Knight Capital Americas LLC, Release 34-70694, 2013-10-16 | the SEC's findings on the August 2012 incident: the control failures, paragraph by paragraph |
| [DSR] | Bailey and López de Prado, The Deflated Sharpe Ratio (2014) | what a backtest must report: the number of trials and their dispersion |
| [PSEUDO] | Bailey, Borwein, López de Prado and Zhu, Pseudo-Mathematics and Financial Charlatanism (2014 preprint) | minimum backtest length given the trials; the weakness of holdouts already seen |
| [AIMA] | AIMA illustrative due-diligence questionnaire, 2025 modules | the topics an allocator asks about; topics only, nothing taken from it |

### C.2 Where this standard departs from them

Recorded so that nobody mistakes a choice for an oversight.

| subject | the sources | this desk | ruled |
|---|---|---|---|
| Alerts | real-time alerts within five seconds ([RTS6] Art 16); errors as alerts and automated exposure alerts ([KNIGHT] ¶19, ¶25) | dashboard and logs only | team lead, 2026-11-22 |
| An independent risk function | limits set and monitoring done by staff independent of trading ([FIA] §1.2; [RTS6] Art 16) | the team lead sets limits and trades; there is no separate risk function | not ruled: a three-person desk; asked again at the first go-live proposal |
| Review of the order path | testing independent of the code's author ([FINRA] §III) | agent review (`quant-reviewer`, `/code-review`, `/release-check`) is enough | team lead, 2026-11-22 |
| Review interval | annual ([15C3-5] (e); [RTS6] Art 9, Art 14(4)) | quarterly | stricter than the sources |

---

## Part D — keeping it true

- **Each quarter**, the team lead and one session re-run the audit (§0.4), re-ask
  every waiver, and review A1.4, A2.7 and Part C.2. The sources ask for at least an
  annual review ([15C3-5] (e); [RTS6] Art 9).
- **After any incident**, the audit is re-run for the area it touched, and a check
  is added here if the incident showed one missing ([KNIGHT] ¶33).
- **A change to this file is a ruling**: it needs the team lead's name and the date
  in `docs/SYSTEM.md` §5.

## Changes

| date | change | by |
|---|---|---|
| 2026-11-22 | Written. Parts A and B from the team lead's answers of 2026-11-22; Part C from primary sources fetched that day (`docs/REFERENCES.md` §12st) | for the team lead |
| 2026-11-22 | Before merge, from the first audit (`results/ops/STANDARD_AUDIT_2026-11-22.md`): A1.2 names the four things always kept (uncommitted work, the main folder, the newest release tree, a branch a VM clone follows); the inventory kept the first three, and PR #99 adds the fourth | for the team lead, in PR #98 |
