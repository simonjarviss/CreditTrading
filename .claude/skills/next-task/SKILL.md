---
name: next-task
description: Decide what to work on next, ranked by the pipeline (idea, explore, paper, go-live proposal) after operations. Use at the start of a work session, when the queue is unclear, or when asked what matters most right now. Reads live state first (python3 -m ops.orient PROD: which machine is prod and whether it is armed), because operations outrank research whenever a book is not trading cleanly.
allowed-tools: Bash(python3 -m ops.orient*) Read Grep Glob
---

# What to work on next

## Live state

```!
python3 -m ops.orient --no-tests 2>/dev/null | sed -n '1,60p'
```

```!
grep -c "" results/IDEA_LEDGER.md 2>/dev/null; grep -nE "\| (IDEA|EXPLORE|SHADOW|PAPER|PROPOSED)[ |]" results/IDEA_LEDGER.md 2>/dev/null | tail -30
```

---

## The ranking rule

**Take no figure from this file.** The mission is more, stronger and more
independent sources of return, combined into one book and run reliably
(`docs/MISSION.md`). Breadth is the main lever. Rank work by the pipeline in
`docs/MISSION.md` §7, after operations:

**1. Keep the live books trading.** `python3 -m ops.orient` PROD says which
machine is prod and whether it is armed, and the last verify line says whether
the last session passed. A FAIL, a missed send or an unarmed prod outranks
everything below. The open operations steps are in `docs/ROADMAP.md`. Anything
that needs a release, an arming or a real-money order is the team lead's: say
what you need from them.

**2. Unblock paper.** The paper/shadow runner is the bottleneck between Explore
and a paper record. If its design approval is not recorded in `docs/SYSTEM.md`
§5, the next task is whatever gets the design to the team lead; if it is
approved and unbuilt, build it (`execution-engineer`), with tests.

**3. Promote what has cleared Explore.** Ledger rows at `EXPLORE` that meet the
Explore bar go to `/paper`.

**4. Explore the top cards.** Ledger rows at `IDEA`, and the `REVIVE?` rows of
the backfill, ranked by strength of mechanism × independence from what is held ×
capacity × ease of testing. `/explore <slug>`. Keep several running at once.

**5. Hunt.** If the top of the card list is thin or all one asset class,
`/hunt` on a theme the ledger has not covered.

**6. The combined book and the market-state layer.** `/combine` when a sleeve
joins or leaves; the state variables and regimes
(`market-historian-economist`).

**7. Go-live proposals.** `/go-live <slug>` for a book whose paper record is
long enough to propose. The team decides.

**8. Data and reliability.** Freshness of the research panels (the laptop's
`data/` is known to lag: measure it), new fetchers (`data-scout`), the fill
record against the auction print.

## Before starting anything

Read `results/IDEA_LEDGER.md` and check `/graveyard`. Nothing is banned; the two
bugs to check for in any new test are a stale-price artifact and a control that
scores as well as the treatment.

## At the end of a phase

Report to the team: what was found (gross results, labelled numbers), what is
now on paper, what you need from them, and the next three things
(`docs/MISSION.md` §10).
