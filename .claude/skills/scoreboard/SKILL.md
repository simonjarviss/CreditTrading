---
name: scoreboard
description: The daily status of every paper and shadow book - P&L, Sharpe to date, drawdown, turnover and correlation with the other books. Paper books come from orient; shadow books from the shadow/ package's scoreboard. Read-only.
allowed-tools: Bash(python3 -m ops.orient*) Bash(python3 -m shadow scoreboard*) Read Grep Glob
---

# Scoreboard

## The paper books (broker record)

```!
python3 -m ops.orient --no-tests 2>/dev/null | sed -n '1,70p'
```

Take every figure from that output or from the command it names. A section that
says `UNMEASURED` is reported as unmeasured. The broker's end-of-day record is
the P&L of record; the snapshot is labelled as a snapshot.

## The shadow books (simulated)

The shadow runner writes its state on the machine it runs on, which is the VM
once the team lead has installed it. Where a state directory is readable:

```bash
SHADOW_STATE_DIR=<dir> python3 -m shadow scoreboard
```

- If there is no state directory on this machine, say so, and say that no shadow
  figure was read. Do not rebuild one from a backtest.
- **Every shadow figure is SIMULATED** and is reported under that word, apart
  from the paper books' figures and never added to them.
- The page withholds Sharpe and correlations until a book has enough scored
  sessions; report the count it gives, not an estimate.
- Report each book's late and unmeasured days. A book with many of either has a
  data or scheduling fault, which outranks its P&L.

## Also report

- The ideas waiting for a book: `EXPLORE` rows in `results/IDEA_LEDGER.md`
  marked ready for shadow.
- Capacity is not on the shadow page yet (its marks carry no volume). Point at
  each idea's Explore note for it.

## After the scoreboard

`/combine` uses the books' records. `/go-live <slug>` starts from a book's
record here, and needs a paper record, which a shadow book is not.
