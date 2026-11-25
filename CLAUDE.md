# QUANTT

A small systematic trading desk. **Scope is open** (team lead, 2026-11-09,
`docs/SYSTEM.md` §5): any asset class and any style, with many independent sleeves
built toward one combined book. **The mission, and the pipeline every idea follows
(idea, explore, paper, go-live proposal, live), is `docs/MISSION.md`. Read it at the
start of every session.** What trades today is two paper sleeves, the core credit
closed-end-fund discount book and C4 (five more CEF families), on Alpaca paper, with
MOC orders on a schedule from a cloud VM. Team lead: Simon Jarvis. Real capital is
planned (`docs/SYSTEM.md` §5).

**The book trades on Alpaca paper**, run by `quantt/` from a prod clone of this
repository held at a release tag (IBKR was retired on 2026-09-28). Prod is moving
from the team lead's laptop (launchd) to an Azure VM (systemd): `docs/RUNBOOK.md`
§8, `docs/ROADMAP.md` phase 6. **Which machine is prod, and whether it is armed,
is never written here: `python3 -m ops.orient` measures it.** **The plan, step by
step, is `docs/ROADMAP.md`.**

**This file holds the rules, which do not rot. It holds no figures about the
book, which do.** Start every session with:

```bash
python3 -m ops.orient      # ~3s: where you are, which machine is prod and armed, the Alpaca accounts, spec, counters, panels
```

Then **`docs/SYSTEM.md`** — what we trade, how it runs, what we know, what has
been decided. **`docs/INDEX.md`** says which file owns every other question.
Read `docs/MISSION.md` and `results/IDEA_LEDGER.md` before any research; `docs/BRIEF.md`
is the theory and market structure of the CEF sleeves.

| you want | ask |
|---|---|
| any number about the accounts, the spec or the counters | `python3 -m ops.orient` (a section that cannot measure says `UNMEASURED`, never a guess) |
| which machine is prod, at which tag, armed or not | `python3 -m ops.orient` PROD (alone: `python3 -m ops.prod_state`) |
| what the system is, how it runs, the standing decisions | `docs/SYSTEM.md` |
| what has been tested, and what it showed | `results/IDEA_LEDGER.md`; before 2026-11-09, `docs/RESEARCH_STATE.md` (history: its counters are frozen) |
| whether a document still says true things | `python3 -m ops.doc_audit` |
| who keeps which lane, and how work reaches `main` and prod | `docs/TEAM.md` (setting up: `docs/ONBOARDING.md`) |

**There is no archive.** Everything from before 2026-09-28 — the IBKR system, the
research notes, the old research families — lives only in git at the tag
`pre-clean-slate` (`docs/HISTORY.md` says what was there and how to recover it).
It is provenance, never evidence of what is true now. Do not rebuild an `pre-clean-slate:_archive/`
folder: delete what is dead, and let git keep it.

---

## Who you are working for

This repository is worked by the team lead and by analysts, each in a lane
(`docs/TEAM.md`; team lead, 2026-10-22). **Know whose session this is before you
act.** If the person has not said (an analyst's `~/.claude/CLAUDE.md` says it), ask
once.

**Wherever a rule here says "the team lead", it means the team lead and nobody
else.** An analyst's request does not stand in for the team lead's approval. In an
analyst's session:

- **Never send, replace or cancel an order at any broker**, never run
  `quantt.session` or `quantt.collect`, and never run the full
  `quantt.broker.alpaca_probe` (its snapshots are the book's record; `--check-keys`
  is fine). The analyst's `config/.env` holds their own paper account under the
  book's variable names, so any of these would act on that account, or record it
  as the book's.
- **Never create, move or delete a tag, never push to `main`**, and never touch
  the VM. GitHub refuses the first two; the analyst has no route to the third.
- **Work on the analyst's branch** (`ryan`, `james` or `lucy`; the team lead's
  is `simon`), create no other branch on GitHub, and deliver through a pull
  request.
  The team lead is the only reviewer and the only person who merges.
- **Start no paper or shadow book.** Promoting an idea to paper is for the team
  lead's sessions (`docs/SYSTEM.md` §5, 2026-11-09, which leaves the analysts'
  process as `docs/TEAM.md` has it).
- **Write `docs/SYSTEM.md` §5 only to record a ruling the team lead has made.**
  Propose one in the pull request instead.

---

## Hard rules — the order path

**Not enforced by any hook.** Treat them as absolute anyway: each names an action
that cannot be undone.

1. **Never transmit an order on your own initiative.** Anything that can send,
   replace or cancel an order at a broker runs only when the team lead has asked
   for it in the session — and even then, **show the concrete order list and get
   an explicit go before transmitting.** (Until 2026-09-28 the rule was "the human
   runs it with `!`"; the team lead asked agents to run the migration commands
   themselves, and this is that instruction made durable.)
   **Paper and shadow books (team lead, 2026-11-09).** An agent may start and run a
   new paper or shadow book on its own, **only through the paper/shadow runner whose
   design the team lead has approved once**, never by an ad-hoc API call, and never
   on an account another runner is armed on (rule 2). Until that approval is
   recorded in `docs/SYSTEM.md` §5, no agent starts a paper book. Rules 2–5 bind
   every transmission. **It never applies to a real-money account**: there, every
   order needs the team lead's go on the full list, in the session.
   **Who runs a prod release (team lead, 2026-11-23, `docs/SYSTEM.md` §5).** An
   agent in the team lead's session runs the release check, then merges to
   `main`, tags and installs on the VM. **Arming or disarming a book happens only
   on the team lead's go in the session**, after the order list is shown. The
   2026-11-02 standing authority (agents arming on their own) and the 2026-10-27
   research-loop exception stay withdrawn (`docs/SYSTEM.md` §5 keeps both as
   history).
2. **The trade phase is not idempotent, and the broker does not dedupe.** Open
   positions exclude unfilled MOC orders, so a second armed run's orders fill in
   the same auction and the book doubles. At Alpaca, `client_order_id` is unique
   only among *active* orders [V: docs, 2026-09-28]. Any runner must refuse before
   transmitting if the broker shows a set already headed for an unclosed auction,
   and must record that it started before its first order goes.
3. **Order type stays MOC** (Alpaca `time_in_force=cls`). Overnight market orders
   realised 100.5bp against a 32.6bp breakeven on 2026-07-31. Alpaca rejects `cls`
   entries from 15:50 ET; NYSE cancels no MOC after 15:50. **One recorded
   exception (team lead, 2026-09-29), the paper account only:** paper runs no
   closing auction and under-fills `cls` (11 of 13 expired on 2026-09-29), so the
   book's json sets `execution.mode = late_market`: the plan is decided in the
   evening and sent as market `day` orders 8 to 2 minutes before the close
   (`docs/RUNNER.md` "Paper execution"). Delete that block to return to `cls`.
   It never applies to a live-money account.
4. **`DRY_RUN=1` is a human hard halt and always wins.**
5. **Never print, copy or transmit credentials.** To test whether a key is set,
   print the boolean, never the value. Alpaca keys live in `config/.env`
   (`ALPACA_<BOOK>_KEY_ID` / `_SECRET_KEY`), which agents never read.

## Hard rules — code

- **No silent fallbacks.** Never `except: pass`, never `fillna()` an invented
  value, never a default for missing data, never degrade to a simpler method.
  **Raise, naming what was missing.** Shipped examples sized every displayed
  target against an invented $500k book, and charged an unmeasured name a median
  fee inside a confident-looking total — both dormant for months.
- **No lookahead.** Every estimated quantity uses data strictly before the date
  it is used on. State the alignment in a comment. Assert it at runtime.
- **A new frozen-spec key must default to current behaviour**, and the no-op must
  be *proved* by diffing sleeve output byte-for-byte with the key absent. Use
  `/spec-change`.
- **The frozen spec is the only authority on a live parameter.** Read it (through
  `scripts/cef/spec.py`); never write the literal. Scripts once baselined against
  a band width the book had left, and nothing errored.
- **Any monitor is read-only.** The IBKR-era dashboard is deleted; the team
  lead will have a new one built later. No code path from a monitor transmits an
  order.
- **Docstrings explain WHY.** Most of this codebase's knowledge, especially its
  incident history, lives in them. Match that density.
- **Never hand-copy a data series.** Anything fetched gets a fetcher and a source
  note in `docs/REFERENCES.md`.
- **Write a test with any change to the live path**, and check it fails against
  the old behaviour before keeping it.

## Hard rules — data

**Confident wrong numbers have cost this desk more than missing ones. Assume your
recall of any specific figure is wrong until you have fetched it.**

- **Never invent a number.** Not a placeholder, not "roughly", not a plausible
  value to keep an analysis moving. If you do not have it, the output is a stated
  gap. **A number without provenance is a rumour.**
- **Real data or nothing**, in this order: (1) the repo's own panels — check the
  last date first; (2) **Alpaca through its API**, the authority on our accounts and
  on what is tradable and shortable (`python3 -m quantt.broker.alpaca_probe`,
  read-only); (3) a **primary external source you actually fetched** —
  EDGAR, FINRA, FRED, an exchange rulebook, a fund filing, the paper itself;
  (4) a script in this repo, **re-run now**. If none yields it: say so, name what
  you tried, and stop.
- **Synthetic data tests whether a method behaves, never a claim about the
  market.** The test: is the conclusion about our code, or about the world?
- **Double-check anything that drives a decision** — a second method, an
  independent source, sign and magnitude. When two sources disagree, **do not
  average and do not pick one silently**: report it and say which you used.
- **Label provenance on every figure**: `[V]` verified, `[S]` sourced but not
  re-read, `[U]` uncertain — as `docs/REFERENCES.md` does.
- **Stale is a form of wrong.** State a panel's last date in any note that uses it.
- Recalled figures on this desk have been wrong in every direction — a statistic
  that existed in no source, a unanimous ruling that was 6–3, a finding recalled
  backwards. Fetch it.

## Hard rules — research

**Rewritten 2026-11-09** (team lead, `docs/SYSTEM.md` §5; `docs/MISSION.md` §1–§2).
Pre-registration, the trial counters and deflated-Sharpe bars, the holdout ceremony,
"no sweeping and picking", the cost grid and the alpha-only gate are **dropped**.
Paper trading is the filter. What follows is what stays: safety, and not fooling
yourself with bad code.

- **The job is to find edges and get them to paper**, not to explain why they will
  not work. Start from who loses money to you and why they keep doing it: every idea
  begins as an idea card (`docs/MISSION.md` §4.1). Breadth is the main lever.
- **No lookahead, including in the data.** A signal uses only what was available at
  decision time: NAV publication lags, filing and acceptance dates and never period
  ends, index membership as of that day, macro data at its first-release vintage.
- **Execution convention is `shift(2)`** for anything traded at the close: decide at
  *t*, MOC fill at *t+1*, earn the *t+2* return. Canonical implementation:
  `scripts/research/harness.py` (`EXEC_LAG`, `evaluate`, `report`, and the target
  builders). **Do not build another backtester**: extend this one, visibly. ML goes
  through `scripts/research/ml.py`. A sleeve with a different fill (an open, an
  intraday window) states its convention and asserts it. `/harness`.
- **Judge on gross signal. Do not model costs in research.** No cost grid, borrow
  haircut or slippage assumption, and no idea rejected on a guessed cost. Costs are
  measured from paper fills and appear only in a go-live proposal. Capacity is a
  feasibility check and is always shown: position size against average daily volume
  at $1M, $5M and $10M.
- **Split time at least once before paper**: early against late, and at least two
  market regimes. It takes five minutes and catches most bugs and flukes. Report by
  era where the sample allows (landmine 8).
- **New research is private (team lead, 2026-11-24, `docs/SYSTEM.md` §5).** This
  repository is public. From 2026-11-24, idea cards, Explore results, research
  scripts, findings notes, ledger lines and the evidence entries of research results
  go to the team lead's private repository `simonjarviss/quantt-research` (working
  copy `~/Desktop/R2_export`, under `desk/`, which mirrors this repository's paths).
  This repository takes only what the VM runs: a promoted book's config and code,
  with a one-line docstring and no research write-up or results. Where a path below
  says `results/...` for new research, read it as `desk/results/...` there.
  Analysts' sessions are not covered yet: until the team lead rules, ask before an
  analyst's research reaches either repository.
- **Keep the idea ledger.** Every idea tested gets one line in
  `desk/results/IDEA_LEDGER.md` (private) in the same commit: date, idea, data, gross
  result, status. `results/IDEA_LEDGER.md` here holds every line up to 2026-11-24
  and takes none after it. It is a record, not a gate. Read both, and `/graveyard`, before starting:
  a dead idea may be revived with a new angle (new data, mechanism, horizon or
  instrument). The most common past failure is a stale-price artifact; the second,
  a control group scoring as well as the treatment. Both are bugs to check for.
- **Report exposures, do not gate on them.** Show each result's factor exposures
  (equity, rates, credit) and its correlation with the sleeves already held. Risk
  premia may be sized sleeves; exposure is managed at book level.
- **Promote to paper yourself** once an idea clears the Explore bar
  (`docs/MISSION.md` §7), through the approved paper/shadow runner (order-path
  rule 1). Real money is the team's decision on a go-live proposal with a
  strategy-specific bar.
- **Modelled sessions are not evidence.** Only broker-confirmed fills count
  toward any live statistic; a shadow book's simulated fills are labelled as
  simulated. On Alpaca paper, record both the fill Alpaca reports (the official
  record) and the P&L at the official closing-auction print, labelled separately:
  paper does not simulate the auction.
- **No decision rule may key on a number written in a document** (H14). Re-measure
  at run time and say what you do under either outcome.
- **Log it for the report.** Every result, ruling, release, incident or live-P&L
  day gets an entry, in the same commit: a research result's in the private
  repository's `desk/results/<family>/`, everything else in
  `results/report/EVIDENCE_LOG.md`, with
  provenance (`results/report/README.md`; `.claude/rules/report.md`). Live data:
  daily aggregates in the repo; rows only in the gitignored `results/report/_cache_live/`.

## Commands

```bash
python3 -m ops.orient                  # first, every session
python3 -m pytest                      # pytest.ini scopes collection; never quote a count
python3 -m ops.doc_audit               # do the documents still say true things?
python3 -m quantt.broker.alpaca_probe --check-keys   # which Alpaca keys are SET (no network)
python3 -m quantt.broker.alpaca_probe  # read-only snapshot of each paper account
python3 scripts/cef/band_frontier.py   # the trading-policy frontier
python3 scripts/cef/plan_diagnostics.py  # IC, kappa, PCA, ADV, vol scalar
python3 .claude/hooks/book_state.py -p # what the banner and status line read
```

## Layout

`src/deploy/sleeves/cef_discount.py` **is** the strategy. `ops/specs/*.frozen.json`
are governance objects, not config. `quantt/` is the new Alpaca run package.
`scripts/` is research and is never on the live path. `data/` is gigabytes and
gitignored — read the parquet, never grep it. `.claude/rules/` loads path-scoped
rules when you open matching files.

## Where it runs

**Prod is a clone of this repository at a release tag, and nothing else**
(`docs/ROADMAP.md` phase 6). It is moving from the team lead's laptop, under
launchd (`docs/RUNBOOK.md`), to an Azure VM under systemd (`docs/RUNBOOK.md` §8).
The cut-over (§8.5) must never leave two schedulers armed for one Alpaca account.
Which machine is prod right now, at which tag, and whether it is armed, is
`python3 -m ops.orient` PROD; it prints a WARNING if both machines are armed. The
VM is reached only through its ssh alias. **This repository is public: the VM's
address, the vault's name and the subscription never go in a tracked file.**

The IBKR prod worktree (`~/prod/QUANTT`) and its launchd jobs were retired on
2026-09-28; the jobs are unloaded and the tree's state is at tag
`pre-clean-slate` (`pre-clean-slate:_archive/prod_state_2026-09-28/`). It is not
the Alpaca prod. `ibkr-final` tags the last IBKR-era commit.

## Landmines

1. **Alpaca paper does not simulate the closing auction.** Staff say paper fills
   MOC at the current quote [V: forum staff post, 2026-09-28]. Paper also charges
   no borrow and no dividends [V: docs]. **It does charge regulatory fees (SEC and
   CAT)**, although Alpaca's paper page says they are not simulated [V: the cef
   account's own FEE activities, `results/cef/LIVE_ATTRIBUTION_2026-11-02.md`;
   corrected 2026-11-08, team lead]. **Paper processes no
   corporate actions at all: no splits and no mergers** [V: Alpaca staff forum
   replies, 2024-06-10 and 2026-07-15]. A held fund that splits keeps its old share
   count on paper, and a merger never converts. The runner has no handling for
   either (`results/events/E1_PAPER_BROKER_CHECK_2026-10-28.md`). Paper P&L on this
   book is structurally different from a live auction fill; score both (research
   rules above).
2. **Alpaca rejects opposite-side orders in one symbol as wash trades**, paper
   included [V: docs]. That is why each book has its own account. Within a book,
   net each symbol into one order.
3. **Fractional shares cannot be shorted or sent `cls`** [V: docs]. Whole shares
   only.
4. **A long→short flip may need two orders** (close, then open) [U: 2020 staff
   post; test it on paper before relying on either answer].
5. **`borrow_status` changes daily.** A probe snapshot is true on its date only.
6. **HYT lags the price panel by a day.** `px.iloc[-1]` can be NaN for a name;
   use `px.ffill().iloc[-1]` for that name's own last close.
7. **`PositionTarget.weight` is signed.** Do not multiply by the side sign again.
8. **The years before 2013 are flat** — too few names clear the ADV filter — so
   full-sample turnover is diluted and full-sample Sharpes are depressed. Report
   by era (H5).
9. **The live sleeve decides on `data/`.** A research script that rewrites a
   panel there rewrites what the book trades on. Write research output elsewhere.
10. **Use `ib_async`, never bare `ib_insync`**, if IBKR code is ever revived from
    tag `pre-clean-slate` — the latter hangs forever on Python 3.12+. orient
    HYGIENE counts unguarded imports by AST.

11. **numexpr returns wrong numbers on this laptop** for broadcast arithmetic
    (`df.sub(series, axis=0)`, `df.div(row_sums, axis=0)`) on a frame above one
    million cells, differently on each run (`scripts/events/numexpr_fault.py`).
    Any wide-universe research script must run with
    `pd.set_option("compute.use_numexpr", False)`; importing
    `scripts/research/explore.py` sets it. The CEF panels are too small to hit it.

## Tests

**Never quote a test count; run `python3 -m pytest`.** A green suite says little
about the code that places orders. `pytest.ini` scopes collection because a
script that opened a live broker connection at import (since deleted) was once
collected by a bare run. A directory is safe to add to `testpaths` only if
nothing it imports opens a socket at import time. The root `conftest.py` blocks
every network connection during tests (`ops/netguard.py`).

## The desk

`.claude/README.md` is the map. `.claude/hooks/` is **advisory** — the
SessionStart banner, a post-edit check and the status line; nothing blocks.
Rebuilt on 2026-11-09 for the mission (`docs/MISSION.md` §9); where a skill,
agent or workflow disagrees with this file, this file wins.

Skills, by pipeline stage: `/hunt`, `/idea`, `/explore`, `/paper`,
`/scoreboard`, `/combine`, `/go-live`; and `/harness`, `/graveyard`, `/repro`,
`/next-task`, `/morning-brief`, `/spec-change`. `/paper` and `/scoreboard`
describe a paper/shadow runner that is **not built or approved yet**: `/paper`
refuses to start a book until `docs/SYSTEM.md` §5 records the design's approval.
The pre-registration skill was removed on 2026-11-09; the IBKR-run skills were
deleted on 2026-09-28 (tag `pre-clean-slate`, under
`pre-clean-slate:_archive/claude_layer/`).

Subagents. The mission's six seats: `market-historian-economist`,
`signal-hunter`, `data-scout`, `portfolio-architect`, `execution-engineer`,
`go-live-reviewer` (go-live stage only; it does not veto ideas earlier).
Helpers at any stage: `quant-reviewer` (code), `beta-detector` (exposures and
artifacts, reported, never a veto), `statistician`, `ml-engineer`,
`data-analyst`. Domain seats: `market-structure-analyst`, `filings-analyst`,
`deal-analyst`, `credit-situations-analyst`. The saved workflow `research-idea`
chains them through one Explore run.

**Scope is open, options and futures included** (team lead, 2026-11-09):
`docs/SYSTEM.md` §5.
