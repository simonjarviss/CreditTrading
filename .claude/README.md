# The desk — how this repo is configured for Claude Code

Five layers, each doing what it is best at. `CLAUDE.md` is the always-on context;
everything here is the machinery around it. Rebuilt on 2026-11-09 for the
mission (`docs/MISSION.md` §9; the ruling is `docs/SYSTEM.md` §5, "Team lead,
2026-11-09"): scope is open, research is judged on gross signal, paper trading
is the filter, and the earlier research gates (pre-registration, trial counters
and their bars, the holdout ceremony, the cost grid, the factor-exposure kill)
are gone from every file here. Earlier desks are in git history.

```
.claude/
├── settings.json   permissions + hooks + status line
├── hooks/          advisory scripts; nothing blocks
├── rules/          path-scoped context, loads on demand
├── skills/         invocable procedures (/name)
├── agents/         specialist seats     (subagents)
├── workflows/      saved multi-agent pipelines
└── loop/           the retired research loop's launchd wrapper (see Workflows)
```

**Before anything else, run `python3 -m ops.orient`** (~3s). It prints where you
are, each Alpaca paper account's latest read-only snapshot, the prod machine's
official daily P&L (Alpaca's end-of-day history) beside the three scores, the live
spec and panel dates — each beside the command that produced it (its TRIALS
section shows the counters frozen on 2026-11-09, as history), and
`UNMEASURED` with a reason where it cannot measure. `CLAUDE.md` holds the rules;
`docs/SYSTEM.md` what the system is and has decided; `docs/MISSION.md` the
standing brief; `docs/ROADMAP.md` the plan to prod; `docs/INDEX.md` which file
owns every other question. `results/IDEA_LEDGER.md` is the record of every idea
tested.

**Who these rules are for.** The mission's rules apply to the team lead's
sessions. The analysts keep the process in `docs/TEAM.md` (team lead,
2026-11-09).

## Hooks — advisory

| hook | event | what it does |
|---|---|---|
| `post_edit_check.py` | `PostToolUse(Edit\|Write)` | Never blocks. Flags the bug classes this repo has actually shipped, on the lines you just added. |
| `session_context.py` | `SessionStart` | Which machine is prod and whether it is armed (a WARNING first if two are), its tag, last verdict and broker-confirmed equity, the probe snapshots' ages, and where to start. |
| `statusline.py` | status line | Model · git · context · prod machine, its arming and last verdict (`TWO ARMED` in red if two are). Never opens ssh: the VM part is the banner's reading, with its age. |
| `book_state.py` | *(library)* | The one reader behind the two above: `ops/prod_state.py` (launchd and files on the laptop; one read-only ssh call to the VM, 3 s budget, banner only), git, probe file names. No broker connection, no keys. |

**There is no blocking hook.** The order-path rules in `CLAUDE.md` are context,
not enforcement. The facts behind them are unchanged: an NYSE MOC cannot be
cancelled after 15:50 ET, and the trade phase is not idempotent — a second armed
run doubles the book.

## Rules — path-scoped, load only when relevant

| file | loads when you open |
|---|---|
| `research-harness.md` | `scripts/**`, `src/backtest/**` |
| `frozen-specs.md` | `ops/specs/**`, `ops/books/*.json`, `config/*.yaml` |
| `documents.md` | `docs/**`, `results/**`, `README.md` |

The Alpaca order path will get its own rule file when it is built
(`docs/ROADMAP.md` phase 4).

## Skills — procedures you or Claude can invoke

The pipeline (`docs/MISSION.md` §7): **idea → explore → paper → go-live proposal
→ live.** Costs and the gaps between paper and real money appear only at the
go-live proposal, measured from paper fills.

| skill | stage | use it for |
|---|---|---|
| `/hunt` | idea | generate and rank idea cards for a theme, or across everything |
| `/idea` | idea | write one full idea card (mechanism, counterparty, persistence, history, data, capacity, correlation) |
| `/explore` | explore | the gross test, one time split, regimes, exposures, capacity, code review, the ledger line |
| `/paper` | paper | promote to a shadow book or paper account. **The paper/shadow runner is not built or approved yet: the skill refuses to start a book until `docs/SYSTEM.md` §5 records the approval** |
| `/scoreboard` | paper | daily status of every paper and shadow book. Not built yet; reports what orient shows |
| `/combine` | paper | rebuild the combined-book proposal from the current sleeves |
| `/go-live` | go-live | assemble the go-live proposal, with measured costs and a strategy-specific bar, for the team |
| `/harness` | explore | how to run a backtest that is comparable to existing numbers |
| `/graveyard` | idea | what has failed so far and how; nothing is banned. Points at `results/IDEA_LEDGER.md` |
| `/repro` | any | reproduce a number before quoting it; check panel freshness |
| `/next-task` | any | what to work on, ranked by the pipeline after operations |
| `/morning-brief` | live books | data freshness, what the signal wants today, the Alpaca accounts |
| `/spec-change` | live books | safely change a frozen-spec key |

## Agents — seats

Each seat runs in isolated context and returns a summary. Ask for one by name,
or describe the task and let Claude route it. A new agent file becomes a
subagent type only in a new session.

```
market-historian-economist ─┐
data-scout → data-analyst ──┼→ signal-hunter (Explore) → quant-reviewer + beta-detector → ledger line
domain seats ───────────────┘                                   ↓ clears the Explore bar
              execution-engineer (paper/shadow runner) → portfolio-architect (combined book) → go-live-reviewer → the team decides
```

**The mission's six seats**

| agent | the seat |
|---|---|
| `market-historian-economist` | theory, crises and literature; the mechanism, counterparty, persistence and history sections of idea cards; state variables and regimes; unsure citations marked `[U]` |
| `signal-hunter` | turns an idea card into a signal and runs Explore on the harness: gross result, time split, regimes, exposures, capacity table, ledger line. Also generates ideas, including dated events |
| `data-scout` | a data card per source (coverage, history, publication lag, how to fetch, lookahead plan); fetchers; free and public data plus the R2 mirror |
| `portfolio-architect` | the combined alpha model, shrinkage toward equal risk, the risk target, regimes, capacity |
| `execution-engineer` | the paper/shadow runner, broker adapters, gates, MOC readiness, fill quality measured from paper |
| `go-live-reviewer` | only at the go-live stage: bugs, lookahead, the gaps between paper and real, costs measured from paper fills, the strategy-specific bar. It does not veto ideas earlier |

**Helpers, at any stage**

| agent | the seat |
|---|---|
| `quant-reviewer` | adversary on the code: lookahead, leakage, fallbacks, units, alignment, stale prices |
| `beta-detector` | reports exposures and artifacts: stale prices, controls, factor betas, correlation with sleeves held. It reports; it does not veto |
| `statistician` | clustering and overlap, effective sample, reading the time split, PRESENT / ABSENT / INCONCLUSIVE. Sets no bar |
| `ml-engineer` | fitted models built correctly: purged and embargoed CV, labels, leakage |
| `data-analyst` | the data audit before any return: staleness, bad bars, alignment, the feature profile |

**Domain seats**

| agent | the seat |
|---|---|
| `market-structure-analyst` | plumbing for any asset class: how the instrument trades, who is forced to trade and when, what is public when; CEF mechanics and per-name facts |
| `filings-analyst` | EDGAR forms and 8-K items, acceptance-time clocks, the SEC's structured data sets, extraction you can score |
| `deal-analyst` | merger arbitrage, tenders, fund mergers, SPACs, spin-offs, index events: terms, timelines, risk shape |
| `credit-situations-analyst` | listed preferreds and baby bonds, BDC loan marks, ratings, distress, fund leverage |

What changed on 2026-11-09, by former name: quant-researcher, backtest-engineer
and event-scout became `signal-hunter`; data-engineer became `data-scout` and
data-librarian was removed; portfolio-manager became `portfolio-architect`;
quant-trader became `execution-engineer`; event-econometrician was removed (its
clustering work is in `statistician`). The mapping and the reasons are in
`results/mission/PHASE0_2026-11-09.md` §3. The desk's statistics live in one
place, `scripts/research/inference.py`, as its backtests do in
`scripts/research/harness.py`.

## Workflows — saved multi-agent pipelines (`.claude/workflows/`)

| workflow | use it for |
|---|---|
| `research-idea` | one Explore run: idea card, data card and audit, gross test with time split, regimes, exposures and capacity, code review, ledger line and a short report |
| `backtest-request` | one backtest question on the canonical harness, gross, independently re-derived |
| `release-check` | go/no-go on one commit for a prod release tag; the team lead tags, installs and arms |
| `daily-ops` | read-only morning/evening check of the live book |
| `standard-audit` | the audit against `docs/STANDARD.md` Part A, each quarter and after an incident: one reader per area, a second reader per area trying to disprove each verdict; args `{repo}` |
| `research-loop` | **retired 2026-11-09.** It ran the dropped pre-registration process unattended. The file is a stub that returns STOPPED and uses no agent, so that the launchd wrapper in `.claude/loop/` (installed only by the team lead, in its own clone) stops cleanly if it is still loaded. Its replacements, the nightly scoreboard and the weekly hunt, are proposed to the team before anything is scheduled |

The event-census workflow was removed on 2026-11-09; `/hunt` covers its purpose.

## Maintaining this

- A convention Claude gets wrong twice → `CLAUDE.md`, or a `rules/` file if it is
  path-specific.
- A prompt you type a third time → a skill.
- Something that must happen every time → a hook, not an instruction.
- A number in any of these files is a **dated observation, not an input** (H14).
  Re-measure at run time.
