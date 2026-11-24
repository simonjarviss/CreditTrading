---
name: hunt
description: Generate and rank idea cards for a theme, or across everything. Use to start a research cycle, when the Explore queue is thin, for the weekly hunt on one rotating theme, or when asked "what else could we trade". Produces short cards and a ranked list; it runs no backtest.
argument-hint: [theme, or nothing for all themes]
---

# Hunt: generate and rank idea cards

Theme: **$ARGUMENTS** (empty means across everything in `docs/MISSION.md` §5).

Scope is open (team lead, 2026-11-09, `docs/SYSTEM.md` §5): CEFs and nearby
markets, fixed income and credit, equities, ETFs and flows, futures, macro and
volatility, and free alternative data. The job is to find edges and get them to
paper.

**Every hunt covers event-driven and special situations in any asset class, and
looks for niche verticals there** (team lead, 2026-11-11, `docs/SYSTEM.md` §5; the
seed list is the block of that date in `docs/MISSION.md` §5). A hunt across
everything that returns no event or special-situation card is incomplete.

## 1. Read what exists first

- `results/IDEA_LEDGER.md`: every idea tested, one line each, and the status
  words. Its `REVIVE?` rows are old ideas whose gross effect was positive and
  whose stopping rule no longer applies. They are candidates.
- `/graveyard`: how earlier ideas failed and the two bug patterns behind most of
  them. Nothing is banned; a revival needs a new angle (new data, a new
  mechanism, a different horizon or a different instrument).
- The cards already written: `results/ideas/YYYY-MM-DD_<slug>.md`.
- For event and special-situation themes, the two catalogues and the expansion
  note under `results/events/` (`SPECIAL_SITUATIONS_CATALOGUE_CORP_2026-10-15.md`,
  `SPECIAL_SITUATIONS_CATALOGUE_CREDIT_2026-10-15.md`,
  `SS_DESK_EXPANSION_2026-10-19.md`). Cite an existing id rather than
  re-proposing it. This skill replaces the retired event-census workflow.

## 2. Generate

For each candidate write a **short card**: five to ten lines answering the
sections of `docs/MISSION.md` §4.1 in brief.

- Mechanism and counterparty first. If you cannot name who loses and why they
  keep doing it, drop the candidate or say what you would need to learn.
- For a dated event: the clock (when it is first knowable) and a count of events
  a year with distinct issuers and distinct months, because clustering in time
  overstates breadth.
- Data: which free source tests it and how far back (`data-scout`).
- Rough capacity at $1M, $5M and $10M from average daily volume or open
  interest. Label a rough figure `[U]`.
- Expected correlation with the sleeves already held.

Seats to use: `signal-hunter` generates; `market-historian-economist` supplies
mechanism and history; `market-structure-analyst`, `filings-analyst`,
`deal-analyst` and `credit-situations-analyst` supply plumbing and domain facts;
`data-scout` checks the data exists.

Favour breadth (`docs/MISSION.md` §4.2): wide universes, several horizons,
unrelated mechanisms. Aim for several mechanism types and more than one asset
class in any hunt across everything.

## 3. Rank

Score each card on four things and rank by their product:

| factor | question |
|---|---|
| strength of mechanism | is a counterparty forced or constrained, on a date we can know? |
| independence | how different is it from what the book already holds? |
| capacity | can it hold the stated capital? |
| ease of testing | is the data in the repo or one fetcher away? |

The scores are judgement. Say so, and give one line of reasoning each. Do not
present them as measurements.

## 4. Write it down

- Save the ranked list as `results/ideas/YYYY-MM-DD_hunt_<theme>.md`, naming
  every card.
- Full cards for the top of the list: `/idea <slug>`.
- Add an `IDEA` line to `results/IDEA_LEDGER.md` for each card written, in the
  same commit.
- Then `/explore <slug>` on the top few. Keep many ideas in Explore at once.

## Rules

No figure is invented: a count or capacity number is fetched and labelled
`[V]`/`[S]`/`[U]`, or stated as a gap. No backtest runs here. Nothing touches
the order path.
