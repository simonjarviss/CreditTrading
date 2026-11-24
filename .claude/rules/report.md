---
paths:
  - "results/**"
  - "docs/JOURNAL.md"
  - "docs/RESEARCH_STATE.md"
  - "docs/SYSTEM.md"
  - "scripts/report/**"
---

# The evidence log — every event gets an entry

`results/report/EVIDENCE_LOG.md` is the raw material for the desk's research report
(`results/report/README.md`). **Every result, ruling, release, incident or live-P&L day gets
an entry, in the same commit as the change.** Live days are appended by
`python3 -m scripts.report.snapshot_live`; everything else by hand.

## The entry

```
### E-YYYY-MM-DD-NN · one-line claim, plain British English
- kind: result | ruling | release | incident | correction | kill | counter | live-pnl | method
- era: HISTORY (before 2026-09-28, or read from tag pre-clean-slate) | ALPACA
- date: YYYY-MM-DD   (the event's date; it matches the id)
- figures:
  - <figure, with units> [S]
- source: `<path>` @ `<short commit>`   (several: separate with "; ")
- supports: §n[, §m]   (the README's report skeleton, §1 to §6)
- status: current | provenance only | superseded by <id> (<date>) | supersedes <id>
```

- **Tags.** `[S]` copied verbatim from the named committed file (the default); `[V]` only if
  that file labels the figure verified or `build_pack.py` re-derives it; `[U]` uncertain, or two
  sources disagree. A ruling with no figure writes `- none (a ruling)`.
- **Never recall a figure.** Copy it from the file you name. If you cannot find it, leave it out.
- **Two sources disagree:** give both, tag both `[U]`, and name the record (`docs/SYSTEM.md` §0).
- **Append-only.** Never edit or delete an entry: a correction is a new entry, `kind:
  correction`, saying what it supersedes. `scripts/report/evidence_log.py` checks the format and
  refuses edits; `python3 -m scripts.report.build_pack` fails on an invalid log.
- **HISTORY is provenance**, never evidence of what is true now (`CLAUDE.md`).
- **The repository is public, and keeps live AGGREGATES only** (team lead, 2026-11-03:
  "Aggregates in repo, rows private"). Per account and day: equity (EOD record and snapshot,
  labelled), P&L, hold and fill totals, fill-cost summaries in bp with counts, order counts,
  verify and gate outcomes. Per-name quantities, per-name or per-fill prices, positions and
  order-level rows go only to the gitignored `results/report/_cache_live/`; `snapshot_live.py`
  refuses to write a row file where git can see it. No figure of individual names or fills is
  committed. Never an account number or id, order id, IP, host, vault or subscription; no
  row-level CRSP, Compustat or TRACE data, permnos or CUSIPs.
