# Document index — which file owns which question

**Every markdown file in this repo outside `results/` has a row here, and
`python3 -m ops.doc_audit` fails if one does not.** One question has one owner. If
you are about to write the same fact into a second file, link to the owner instead.

Figures are not owned by any document: `python3 -m ops.orient` produces them.

## Roles

| role | meaning |
|---|---|
| **entry** | Where a reader starts. Points at orient and `docs/SYSTEM.md`; carries no status figures. |
| **rules** | Durable rules that do not rot. No dated figures. |
| **manifest** | This file. |
| **canonical** | The single owner of a question about what the system is or has decided. |
| **ledger** | A canonical table that is updated in the same commit as the event it records. |
| **reference** | Stable reference material: theory, external claims, history. |
| **desk** | Agent-layer files Claude Code loads: rules, skills, subagents. Must point at owners, not restate them. |

## The index

| path or glob | role | owns | checked by |
|---|---|---|---|
| `CLAUDE.md` | rules | the hard rules for agents: order path, code, data, research; landmines; the desk | `ops.doc_audit` (desk inventory, entry point) |
| `README.md` | entry | where a human starts, setup, and the repo layout | `ops.doc_audit` (entry point) |
| `docs/INDEX.md` | manifest | which file owns which question | `ops.doc_audit` (manifest) |
| `docs/SYSTEM.md` | canonical | what we trade, how it runs, what we know, standing decisions | `ops.doc_audit` (pointers) |
| `docs/MISSION.md` | canonical | the team lead's standing brief of 2026-11-09, verbatim: the mission, what stays and what was dropped, how to think about edges, the pipeline from idea to live, the engineering and agent-layer build, the phases | — |
| `docs/STANDARD.md` | canonical | what "done properly" means: the checks the platform must meet for every book and job, what real money adds, the external sources, and where the desk departs from them; holds no status, which the audit measures | — |
| `results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md` | reference | the shadow-book runner's approved design: what a shadow book is, how it is kept apart from prod, the book file, the daily cycle and the on-time rule, where it runs, the marks; the package `shadow/` is built against it | `shadow/tests/` |
| `shadow/universes/README.md` | reference | the lists of symbols a shadow book may trade, and the repository files each list is built from | `shadow/tests/` |
| `quantt/sleeves/deploy/README.md` | reference | the event sleeves' paper runner on the VM: what the installer does, what the team lead does by hand first, the first-day checklist, exit codes, how to halt, what to do when VERIFY fails | `quantt/sleeves/tests/` |
| `results/IDEA_LEDGER.md` | ledger | every idea tested, one line each: date, idea, data, gross result, status; a record and not a gate; updated in the same commit as the test | — |
| `docs/ROADMAP.md` | ledger | every step from here to the Alpaca book in prod, and its status | `ops.doc_audit` (pointers) |
| `docs/RUNNER.md` | canonical | the Alpaca runner's design: the session, module boundaries, the nine gates | `ops.doc_audit` (pointers) |
| `docs/RUNBOOK.md` | reference | release, install, arm, disarm and check the laptop prod clone | `ops.doc_audit` (pointers) |
| `docs/DATA.md` | reference | which data source feeds what (live vs research), the R2 layout | `ops.doc_audit` (pointers) |
| `.claude/workflows/*.js` | desk | saved multi-agent workflows: research-idea (the Explore run), backtest-request, release-check, daily-ops, standard-audit (`docs/STANDARD.md` §0.4); research-loop is a retired stub | — |
| `docs/JOURNAL.md` | ledger | the day-by-day desk journal: what was tried, found, ruled, shipped to prod and earned; updated in the same commit as each change; owns nothing (every figure names its owner) | — |
| `docs/RESEARCH_STATE.md` | reference | the research record before 2026-11-09: the frozen trial counters, the D1–D7 legend, and the evidence behind every row backfilled into `results/IDEA_LEDGER.md` | `ops.orient` TRIALS |
| `docs/BRIEF.md` | reference | the edge's theory, CEF market structure, and harness rules H1–H15 | `ops.doc_audit` (spec id) |
| `docs/REFERENCES.md` | reference | every external claim and its verification status | — |
| `docs/HISTORY.md` | reference | what existed before the 2026-09-28 clean slate, and how to recover it | — |
| `docs/TEAM.md` | canonical | the lanes and who keeps which paths, the live path, how a change reaches `main` and prod, the shared-ledger rules, what an analyst never does, access | — |
| `docs/ONBOARDING.md` | reference | setting up an analyst's Mac, a map of the repository, the reading order, the tools, a glossary | — |
| `dashboard/README.md` | canonical | what the read-only dashboard may read (the nightly snapshot only), the exporter's division of labour, and what a snapshot may never carry | — |
| `dashboard/EXPORTER_SPEC.md` | reference | what the nightly snapshot exporter reads and writes, the rules it must obey, and the open questions for the team lead; a draft until the snapshot format is approved | — |
| `.github/pull_request_template.md` | rules | the questions every pull request answers before the team lead reviews it | — |
| `results/ops/STANDARD_AUDIT_2026-11-22.md` | reference | the first audit against `docs/STANDARD.md` Part A: every check with both readers' verdicts, the ranked gaps, and the findings outside the checks; superseded by the next quarterly audit | `results/ops/standard_audit_2026-11-22.json` (the workflow's verbatim output) |
| `results/ops/CEFCONNECT_TERMS_OPTIONS_2026-10-19.md` | reference | the options for CEFConnect on the live NAV path (keep and ask Nuveen, replace per use, or licence), the draft letter to Nuveen, and what each choice changes; open until the team lead picks | — |
| `results/ops/NAV_SOURCE_WORKAROUND_2026-10-19.md` | reference | legitimate routes to a NAV source this desk may trade on (NFN's licence upstream of the vendors, IBKR and Alpaca data terms, the non-professional definitions, a CEFConnect-free gate design), the Nasdaq enquiry draft, and the ranked shortlist; open until the team lead picks | — |
| `results/ops/IBKR_SECOND_BROKER_2026-10-19.md` | reference | the IBKR second-broker design and plan (routing, per-broker gates, what to revive, the step list), until a build contract replaces it | `ops.doc_audit` (reproducer) |
| `results/ops/IBKR_WORTH_IT_2026-10-19.md` | reference | whether IBKR is worth opening: the core-book benefit of the shorts Alpaca will not lend (measured, fit period), the option value through E1, NAV tenders and SPACs, the costs, and the triggers; open until the team lead rules | `scripts/ops/tests/test_ibkr_worth_it.py` |
| `.claude/README.md` | desk | the map of the agent layer | — |
| `.claude/rules/*.md` | desk | path-scoped rules loaded when matching files are opened | `ops.doc_audit` |
| `.claude/skills/*/SKILL.md` | desk | one workflow each | `ops.doc_audit` (desk inventory) |
| `.claude/agents/*.md` | desk | one specialist seat each | `ops.doc_audit` (desk inventory) |
| `results/cef/DATA_GUARDS_2026-10-19.md` | reference | the research-path data guards every trial inherits (split-like spike-and-revert bars raise; Stage-0 flags block P&L until ruled; since 2026-10-20, a recorded split applied to an already split-adjusted close raises), their rules, and what they found and touched | `scripts/cef/tests/test_data_guards.py` |
| `results/report/README.md` | reference | the research evidence pack: what it holds, how to append to it, the evening procedure, the report's section skeleton and the data-licensing note | `scripts/report/tests/` |
| `results/report/EVIDENCE_LOG.md` | ledger | the dated, append-only evidence log a research report will be written from: one entry per result, ruling, release, incident or live day, each with provenance; updated in the same commit as the event; owns nothing (every figure names its owner) | `python3 -m scripts.report.build_pack` (format, append-only) |
| `results/report/SOURCES.md` | reference | literature and primary sources the report could cite, each FETCHED (then also in `docs/REFERENCES.md`) or TO VERIFY | — |

**Not indexed, by design:** `results/**` (dated records, each true as of its date;
`ops.doc_audit` checks their pre-registration shape) and runtime output written
rather than authored — `results/ops/alpaca_probe/` and `ops/HALT*.md`. **Three
exceptions (2026-10-19):** a results note holding a decision still open for the team
lead keeps a row until the decision is recorded in `docs/SYSTEM.md` (the first:
CEFConnect); a dated design note that later build work is written against gets a
row (the first: the IBKR design); and a note defining guards every later trial
inherits gets a row (the first: the data guards). **A fifth (2026-11-09):** the idea ledger, `results/IDEA_LEDGER.md`, is a standing ledger and has a row. **A fourth (2026-11-03):** the research
evidence pack under `results/report/` is a standing, append-only record, not a dated note, so
its three authored files have rows.
