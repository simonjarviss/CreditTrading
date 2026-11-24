---
name: go-live
description: Assemble the go-live proposal for one paper or shadow book - the paper record, costs measured from paper fills, borrow availability, capacity, the gaps between paper and a real account, and a strategy-specific bar with its reasoning - for the team to decide. Use only when a book has a paper record worth proposing. It sends nothing and decides nothing.
argument-hint: <slug>
---

# Go-live proposal

Slug: **$ARGUMENTS**

This is the only stage where costs and the gaps between paper and real money
are examined (`docs/MISSION.md` §7). **The team decides.** Real money always
needs the team's explicit approval; this skill produces the document they
decide on. The seat is `go-live-reviewer`, with `execution-engineer` and
`portfolio-architect`.

## Before starting

- The book has a record: a `PAPER` or `SHADOW` row in `results/IDEA_LEDGER.md`
  and a line on `/scoreboard`. If it has only a backtest, it is not at this
  stage: go back to `/paper`.
- A proposal resting only on simulated shadow fills says so in its first line.

## The proposal

| section | content |
|---|---|
| the idea | the card in three lines: mechanism, counterparty, why it persists |
| the paper record | sessions, P&L, Sharpe to date, drawdown, turnover; live against backtest on the dates both exist |
| code review | bugs and lookahead, by `quant-reviewer`'s checklist; targets rebuilt from data truncated at each decision |
| measured costs | per-fill cost against the official closing-auction print with its standard error, split by session and method; implementation shortfall. **Measured from the paper fills, never assumed** |
| borrow | availability today for each short (read-only probe, true on its date), the measured fee where one exists |
| capacity | position size against ADV at $1M, $5M and $10M |
| paper against real | the closing auction, borrow fees, dividends and distributions owed on shorts, corporate actions, regulatory fees: each marked measured, estimated from a primary source, or unknown |
| the book | correlation with the sleeves held and contribution to the combined book |
| the bar | strategy-specific: reasoned from how often it trades and how many bets it takes; the minimum record; the live statistic and horizon that would reverse the decision |
| the ask | the recommendation, and the alternatives: longer on paper, a smaller first allocation, or do not proceed |

Every figure labelled `[V]`/`[S]`/`[U]` with its date. The bar is stated as a
method to re-measure, never as a number copied from a document.

## Where it goes

- A dated note in the idea's results folder; the ledger status becomes
  `PROPOSED`; an entry in `results/report/EVIDENCE_LOG.md`.
- The decision is put to the team lead. The answer is recorded in
  `docs/SYSTEM.md` §5.

## Lines that do not move

- **No order on a real-money account** without the team lead's explicit go in
  the session, after the full order list. `DRY_RUN=1` always wins.
- A live book is MOC, with full gates; the paper-only late-market exception
  never applies to a live-money account.
- Any release to prod is the team lead's alone. Any frozen-spec key goes through
  `/spec-change`.
- Never read `config/.env`.
