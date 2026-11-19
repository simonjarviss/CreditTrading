# Idea card — A stale-NAV gate with no second source: holding repeated NAVs costs more than deciding on stale ones

**Status:** SET ASIDE. Do not build the hold gate; leave the existing gate in report mode.
**Slug:** `nav_stale_gate` · **Date:** 2026-11-19 · **Book:** core (13 credit CEFs) · **Gross, canonical harness.**
Panel: the desk's `data/cef` on the laptop, last NAV 2026-10-14 (26 sessions stale against the VM). Not independently reviewed.

## What was asked

The core's stale-NAV gate (`quantt/session/nav_gate.py`) needs CEFConnect to tell a stale Yahoo NAV from a genuine
repeat. CEFConnect has served a block page since about 2026-10-21 (E-2026-11-18-03). The team lead chose "gate
without a second source" (2026-11-19). The only rule that needs no second source is the one the gate already has for
an unverified name: hold it, no trade that session. This card measures whether that is worth having.

## What the live book has been doing

Read from the VM's 38 plans (`plan.json`, the `nav_gate` block) [V]:

- The gate runs in **`report` mode**. It writes "would defer" and the book decides at its usual evening slot. No name
  has been held and no decide deferred on any session.
- From 2026-10-21 to 2026-11-19, 21 plans: every CEFConnect read was an error, and **111 of 273 name-days (40.7%)**
  had a NAV dated D equal to the cent to the previous NAV. Between 1 and 10 of the 13 names a day.
- On the true panel, **18.8%** of name-days are genuine repeats (below). So about **21.8%** of name-days are assumed
  to be stale copies. That is an inference from two shares, not a count of confirmed stale rows.

## What was fixed before any return was read

In `results/ideas/nav_stale_gate/explore.py`'s docstring. The spec's book, `build_targets` then `band`, unchanged.
A stale name-day decides on the target built from the NAV panel lagged one session. Five variants: TRUE (every NAV
current), STALE (21.8% of name-days stale at random, 200 draws), ALL_LAG (every name-day stale: the bound), HOLD_TRUE
(no trade on a genuine-repeat day), HOLD_STALE (stale and genuine repeats both held, everything else on true targets).

## What it showed

2013-06-25 to 2026-10-14, gross [V]. Turnover is the sum of absolute weight changes a year.

| variant | Sharpe | return | vol | worst drawdown | turnover | halves | 2013-15 / 2016-19 / 2020-22 / 2023-26 |
|---|---:|---:|---:|---:|---:|---|---|
| TRUE | 1.15 (t 4.20) | 7.60% | 6.60% | −14.4% | 22.4 | 0.87 / 1.45 | 1.39 / 0.56 / 1.01 / 1.79 |
| ALL_LAG | 1.03 (t 3.75) | 6.80% | 6.61% | −14.4% | 23.7 | 0.80 / 1.26 | 1.27 / 0.52 / 0.71 / 1.75 |
| HOLD_TRUE | 1.07 (t 3.89) | 7.15% | 6.70% | −14.5% | 21.2 | 0.87 / 1.27 | 1.37 / 0.55 / 0.96 / 1.51 |

| drawn variant (200 draws) | Sharpe, mean [5th, 95th] | return, mean [5th, 95th] | turnover |
|---|---|---|---:|
| STALE (what the book does now) | 1.108 [0.984, 1.208] | 7.41% [6.88%, 7.92%] | 22.8 |
| HOLD_STALE (the hold gate) | 0.990 [0.910, 1.075] | 6.71% [6.17%, 7.25%] | 19.9 |
| HOLD_STALE less STALE, per draw | −0.118 [−0.239, +0.008] | −0.70% [−1.39%, +0.05%] | −2.9 |

- **Stale NAVs cost little.** About 0.04 of Sharpe and 0.2% a year against a book with every NAV current. Even with
  every NAV a session old the book keeps 1.03. A one-session NAV move is small against the 4.8% band.
- **Holding costs more.** Not trading on a genuine repeat alone costs 0.08 of Sharpe. Holding both kinds costs 0.16
  against TRUE and 0.12 against what the book does now, and is worse than deciding on stale NAVs in about 95% of draws.
- TRUE reproduces the canonical book (1.15, t 4.20), so the harness path is the usual one.

## What I conclude

A hold gate with no second source would cost about 0.7% a year to remove a cost of about 0.2% a year. **Do not build
it.** Keep the gate in report mode, where it records the repeats, and keep the nightly data-QA flag (Q9) that names
the missing second source. A second source is still worth having for what it corrects, and the stale-copy cost is
small enough that it does not justify paying for one or weakening the free-data ruling.

## What this does not show

- Staleness is drawn at random. If stale copies cluster on large NAV moves (when a fund's NAV is late, it may be
  because something happened), the cost is higher than measured. The 2026-10-12 note found yfinance's next change
  carries the move it skipped (slope 1.19), which is consistent with plain lateness, but that is not a test of
  clustering.
- The lagged panel shifts a fund's whole NAV history by a session; a real stale copy is only the newest row. The mixed
  target frame is not re-normalised across names.
- The stale share (21.8%) is the live repeat share less the panel's genuine-repeat share, from 21 sessions.
- Gross. Holding trades less (turnover 19.9 against 22.8), so a cost per trade would narrow the gap: at 15bp on the
  2.9 difference that is about 0.04% a year, far less than the 0.70%.

## What would reopen it

A confirmed list of stale name-days (the VM's `nav_gate` checks from 2026-10-15 to -20, when CEFConnect still
answered, plus any later correction of Yahoo's rows) showing that stale copies sit on large NAV moves; or a second
source that costs nothing.
