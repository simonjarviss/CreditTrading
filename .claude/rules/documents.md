---
paths:
  - "docs/**"
  - "results/**"
  - "README.md"
---

# Writing documents and results notes

This project's documents are load-bearing. They are how a competent stranger picks
the book up cold, and how a decision made in September survives to February. Match
the register that is already there.

## The three categories, kept separate

**Established / measured-but-conditional / unknown.** Keeping these apart is the
most important discipline in this project. Never let a conditional number drift
into the established column because it has been repeated a few times.

- *Established*: IC −0.074 (t −11.6), 27 years, every sub-period; not credit beta
  (β +0.013, R² 0.0008).
  **The walk-forward and bootstrap were REMOVED from this list on 2026-09-10.**
  They read "9/9 purged walk-forward; bootstrap P(SR≤0) = 0.000%". Both were
  scored `shift(1)` — an unobtainable entry price. Corrected: **7/9** (median
  0.63, worst −0.45) and **0.300%**. This entry is the cautionary example for the
  rule above it: 9/9 was superseded on 2026-09-10 at 14:37, and it still sat in
  the *Established* column of the file that tells agents what is established.
- *Superseded, and do not restore*: 9/9 walk-forward; gross 1.26/1.27; net
  0.82/0.83; DSR 0.870 "fails only on multiplicity". All `shift(1)`.
- *Measured but conditional*: borrow at 1.22%/yr ≈ 0.23 Sharpe — **measured once**,
  on 2026-09-06, and applied to 21 years. A forward estimate, not a historical cost.
- *Unknown, and the unknowns dominate*: what execution actually costs (n = 1,
  dispersion ±93.8bp); whether the paper record means anything; survivorship, which
  these files cannot measure.

## Rules

1. **Every number names the script that reproduces it.** If it cannot be
   reproduced, it is an anecdote and must be labelled as one.
2. **Say when it was measured.** A borrow panel two days old, an option chain
   snapshotted one afternoon, a variance decomposition on a panel that ends six
   weeks ago — several figures in these documents have already gone stale. Date
   them so the reader can tell.
3. **Record negative results against yourself.** The archived `pre-clean-slate:_archive/docs/PLAN.md` §0.3 records a claim
   its own author made and then measured to be false. Do that. Say plainly when
   something did not work: one line in `results/IDEA_LEDGER.md` is enough.
4. **No decision rule may key on a number written in a document** (H14). If a
   passage reads "X is 59.6%, therefore do Y", it is wrong and should read "measure
   X this way; if it is high, Y follows; if not, Z."
5. **Correct in place, visibly.** When a figure was wrong, leave a dated correction
   note rather than a silent edit — the ex-distribution arithmetic correction in
   the brief is the model. Someone is relying on the old number somewhere.
6. **Cite externally-sourced claims into `docs/REFERENCES.md`** with a verification
   status. Prompts cite that file; they do not re-derive it.
7. **British spelling, plain sentences, no marketing.** Tables for anything with
   more than two dimensions. The audience is a competent agent picking this up cold.
8. **Research results are gross, and say so.** No cost grid, borrow haircut or
   slippage assumption in a research note (team lead, 2026-11-09, `docs/SYSTEM.md`
   §5). Lead with the result; show the time split, the regimes, the exposures and
   the capacity table beside it; one chart per idea. Measured costs appear only in
   a go-live proposal.

## Where things belong

**`docs/INDEX.md` is the list** — every authored document, its role, and the one
question it owns; `python3 -m ops.doc_audit` fails on a document with no row. The
short version:

| file | holds |
|---|---|
| `docs/SYSTEM.md` | what we trade, how it runs, what we know, standing decisions |
| `docs/MISSION.md` | the team lead's standing brief: the pipeline and the tooling |
| `results/IDEA_LEDGER.md` | every idea tested, one line each, with its gross result and status |
| `results/ideas/YYYY-MM-DD_<slug>.md` | idea cards |
| `docs/RESEARCH_STATE.md` | history before 2026-11-09: the frozen counters, the D1–D7 legend, the evidence behind each older row |
| `docs/BRIEF.md` | the theory, market structure and harness rules every prompt opens with |
| `docs/REFERENCES.md` | every external claim, with a verification status |
| `results/<family>/` | dated findings notes (and, before 2026-11-09, pre-registrations) |
| `pre-clean-slate:_archive/` | superseded documents — provenance, never authority (`pre-clean-slate:_archive/README.md`) |

**Before writing a fact into a document, find its owner in the index and link to
it.** A second copy is how this repo came to hold four different arm rates.

`results/IDEA_LEDGER.md` is the record of what has been tested — **add the line
in the same commit as the test, not at the end of a session.** The record it
replaced drifted once, for five weeks.

## Idea cards and the ledger

These replace pre-registrations for research (team lead, 2026-11-09,
`docs/SYSTEM.md` §5). The pre-registrations already under `results/` are history
and are not rewritten.

**An idea card** lives at `results/ideas/YYYY-MM-DD_<slug>.md` and answers, in at
most a page (`docs/MISSION.md` §4.1; `/idea`):

- **Mechanism**: the economic force that creates the mispricing.
- **Counterparty**: who is on the other side, and why they keep trading that way.
- **Persistence**: why it has not been arbitraged away.
- **History**: named episodes and what happened to the edge in each; citations
  labelled, anything not re-read marked `[U]`.
- **Data**: the free source that tests it, how far back, its publication lag.
- **Capacity**: rough size against average daily volume at $1M, $5M and $10M.
- **Expected correlation** with the sleeves already held.

**A ledger line** has five cells: date, idea, data (with its last date), gross
result, status. The status words are defined at the top of the ledger. It is a
record, not a gate: an idea set aside may return with a new angle, and the
re-test is another line.

A **go-live proposal** (`/go-live`) is the one document that carries measured
costs and a bar, and the bar is specific to its strategy.
