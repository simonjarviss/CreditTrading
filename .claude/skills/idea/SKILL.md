---
name: idea
description: Write a full idea card for one idea - mechanism, counterparty, persistence, history, data, capacity and expected correlation - at results/ideas/. Use when an idea is worth testing, before /explore, or to bring a set-aside idea back with a new angle.
argument-hint: <slug>
---

# Write an idea card

Slug: **$ARGUMENTS**

The card lives at `results/ideas/YYYY-MM-DD_<slug>.md`, dated the day it is
written (`docs/MISSION.md` §4.1). It is at most a page. Start from who loses
money to you, and why they keep doing it.

## Before writing

- Read `results/IDEA_LEDGER.md` and run `/graveyard`. If the idea, or a close
  relative, has been tested, name the row and say what is different this time.
- If the earlier failure was a stale or untradable price, say how this design
  avoids it.

## The sections

```markdown
# <idea name>  (<slug>, YYYY-MM-DD)

## Mechanism
What economic force creates the mispricing: a forced or constrained seller or
buyer, a behavioural bias, a premium for bearing something unpleasant, a
structural flow, slow information, a limit to arbitrage. What it predicts about
sign, size and horizon.

## Counterparty
Who is on the other side, and why they keep trading this way.

## Persistence
Why it has not been arbitraged away.

## History
Named episodes where it appeared and what happened to the edge in each.
Papers and books, each labelled [V] read this session, [S] from
docs/REFERENCES.md, or [U] not re-read.

## Data
The free source or repo panel that tests it, how far back it goes, its last
date, its publication lag, and the lookahead plan. The data card, if a new
source is needed.

## Capacity
Rough position size against average daily volume or open interest at $1M, $5M
and $10M. Feasibility only.

## Expected correlation
With each sleeve already held, and why.

## The test
The signal in one sentence. The fill convention (shift(2) for a close-traded
signal, or the stated alternative). One control: where the effect should be
absent. The time split and the regimes you will read.

## Status
IDEA. What would move it to Explore.
```

## Who writes what

- Mechanism, counterparty, persistence, history: `market-historian-economist`.
- Data: `data-scout` (the data card: coverage, history, publication lag, how to
  fetch, lookahead plan). Free and public data only, plus the R2 mirror.
- Plumbing and instrument facts: `market-structure-analyst`; filings:
  `filings-analyst`; deals: `deal-analyst`; listed credit:
  `credit-situations-analyst`.
- The test: `signal-hunter`.

## After writing

- Add one line to `results/IDEA_LEDGER.md` with status `IDEA`, in the same
  commit as the card.
- Next: `/explore <slug>`.

## Rules

Every figure on the card is fetched and labelled `[V]`/`[S]`/`[U]` with the
panel's last date, or stated as a gap. A citation not re-read is `[U]`. Plain
British English.
