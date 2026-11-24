# Snapshot exporter: spec (0.2, implemented in `dashboard/export.py`)

**This file owns** what the exporter reads, what it writes, and what it must never do. The
format is `dashboard/snapshot.py`; the privacy table is `dashboard/README.md` section 2.
Draft 0.1 (Lucy, PR #62) asked four questions; the answers are at the end.

## 1. What it does

Every 30 minutes, read the records the runners have already written and write one
`snapshot.json` into the build unit's runtime directory, for `dashboard/site.py` to render.
It opens no broker connection and no socket, sends no order, and changes nothing under the
state directory (its unit mounts the state read-only and has no network).

## 2. Where each field comes from

Paths are under `<state>/<book>/`. Files are read by header name, never by position.

| snapshot field | read from | label |
|---|---|---|
| `official.rows` (date, equity, change_usd) | `eod_equity.csv`, Alpaca's end-of-day history, the P&L of record; `read_at` = the newest row's `read_at_utc` | broker-confirmed |
| `session` (core and C4) | the newest `YYYY-MM-DD/reconcile.json`: `verdict` (its date must be the directory's), the number of `problems`, `positions_after` with the official closing prints `auction_prints_d.prices` reduced to counts (long, short, unpriced) and gross and net dollars, `orders` reduced to counts (filled in full, partly, not at all) and shares filled, `snapshot` (after-close equity and change). No symbol, share count, order line or note text is copied (team lead, 2026-11-23: aggregates only) | broker-confirmed |
| `session` (events) | the newest `YYYY-MM-DD/verify.json`: `ok`, the number of `problems` + `fails`, `positions_after` and `marks` (daily bar closes) reduced to counts and gross and net dollars, `orders` reduced to counts, `equity`. Nothing per name is copied | broker-confirmed |
| `start` (every book) | the oldest `YYYY-MM-DD/STARTED`: the first session that sent an order. A book's statistics, and its place in the portfolio, begin there, not at its funding (a dry run writes no STARTED) | recorded |
| `after_close` (events) | every `YYYY-MM-DD/verify.json` from the first send: `equity.equity`, each session's P&L being the change from the previous reading (not Alpaca's `change_usd`, which runs from its official close), with the first traded day's `last_equity` as the base and each `plan.json` `asof` checked against the previous reading's session. The event book's daily record until it has an `eod_equity.csv`; days before the first send without a reading are skipped, a missing reading after it is UNMEASURED | broker-confirmed |
| `risk` | the newest `reports/risk/*.json`: severity, gross, net, cap, concentration, drawdown levels | modelled |
| `execution` | `tca.csv`: n_orders, n_full, fill_rate_shares, slip_bp_all | broker-confirmed |
| `sleeves` (events only) | `sleeve_scores.csv`: per-strategy P&L, day change, names, capital | broker-confirmed |
| `shadow` | the shadow runner's `SCOREBOARD.md`, first table only | simulated |

## 3. Rules the exporter obeys

1. **Allow-list, not deny-list.** Named fields only; order ids, `client_order_id` and fill ids
   are never copied.
2. **A gap is written as a gap.** Missing or unreadable becomes `{"UNMEASURED": "<what was
   tried>"}`; a thing that does not exist yet becomes `{"absent": "<why>"}`. Never zero, never
   the previous value.
3. **Every measured value carries** `source`, `read_at` (UTC) and `label`.
4. **No secrets, no addresses, no paths.** Text from a record is scrubbed of paths before it is
   written.
5. **Refuse to write a dirty snapshot.** `validate` and `find_private` run first; a problem
   means nothing is written and the exit code is 2.
6. **Write atomically** (temp file, fsync, rename).
7. **A failure never touches the book.** The build unit's failure is its own; the site keeps
   its last good build.

## 4. Draft 0.1's questions, answered (team lead, 2026-11-23)

1. *How does a snapshot get from the VM into the repository?* It does not: the site is built
   and served on the VM, and snapshots stay there.
2. *The `reconcile.json` fields marked "?"* Confirmed against the records of 2026-11-20: the
   orders carry `filled_avg_price` and `filled_qty`; fills are not exported (orders carry what
   the page needs).
3. *Position prices?* Yes: the session's official closing prints (core, C4) or daily bar closes
   (events), labelled on the page.
4. *`dashboard/tests` in `pytest.ini`?* Yes.
