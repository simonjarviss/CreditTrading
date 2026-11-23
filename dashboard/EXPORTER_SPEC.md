# Snapshot exporter: spec (DRAFT 0.1, for the team lead's review)

**This file owns** what the nightly exporter reads, what it writes, and what it must
never do. The format is `dashboard/snapshot.py`; the privacy table is
`dashboard/README.md` section 2. This lane writes the spec and tests; the team lead
reviews, releases and installs the exporter on the VM.

## 1. What it does

Once a night, **after** `quantt.session.verify` has written the day's records, read
those records and write **one** file, `snapshot-<session_date>.json`, in the format
of `dashboard/snapshot.py` (`schema_version` `0.1-draft`). It reads only files the
session has already recorded. It opens no broker connection, sends no order, and
changes nothing under the state directory.

## 2. Where each field comes from

Source paths are under `<state>/` (`$QUANTT_STATE_DIR`). **Fields marked ? are read
from the test fixtures and code, not from a real night: confirm them.**

| snapshot field | read from | label |
|---|---|---|
| `account.equity`, `account.last_equity` | `<D>/reconcile.json` `snapshot.equity`, `snapshot.last_equity`; `read_at` = `snapshot.clock_read_at` | broker-confirmed |
| `pnl.official_eod_change_usd` | `reconcile.json` `official_eod.change_usd`. If `official_eod.pending` is set, write UNMEASURED ("PENDING") | broker-confirmed |
| `pnl.snapshot_change_usd` | `reconcile.json` `snapshot.change_usd` | broker-confirmed |
| `pnl.auction_pnl_usd` | `scores.csv`, row for D, column `auction_pnl_usd`. A cell reading `UNMEASURED` becomes an UNMEASURED reading | modelled |
| `equity_history` | `eod_equity.csv`, last N rows, `date` and `equity` read **by header name** (the file's contract, `docs/RUNNER.md`) | broker-confirmed |
| `positions` | `reconcile.json` `positions_after`: symbol and share count only | broker-confirmed |
| `trades.orders` | `reconcile.json` `orders`: symbol, side, qty, type, status only (?) | broker-confirmed |
| `trades.fills` | `reconcile.json` `fills`: symbol, side, qty, price, time only (? field names unconfirmed) | broker-confirmed |
| `system` | `scores.csv` row for D (`verdict`, `n_orders`, `n_filled`, `traded`) and `reconcile.json` `problems` and the verdict reason | modelled |

## 3. Rules the exporter must obey

1. **Allow-list, not deny-list.** Copy named fields only. Never copy a whole record.
   Order ids, `client_order_id` and fill ids are left out.
2. **A gap is written as a gap.** Anything missing or unreadable becomes
   `{"UNMEASURED": "<what was tried>"}`. Never zero, never the previous night's value.
3. **Every measured value carries** `source` (file and field), `read_at` (UTC) and `label`.
4. **No secrets, no addresses.** Never read `config/.env` or the key file. Error text
   written into a reading is scrubbed the way `ops/prod_state.scrub` does it.
5. **Refuse to write a dirty snapshot.** Run `validate` and `find_private` on the
   result first. If either returns a problem, write nothing and exit non-zero.
6. **Write atomically** (temp file, fsync, rename), the way `quantt/session/records.py` does.
7. **A failure never touches the book.** The exporter's exit code is its own. It is
   not part of the session's verdict.

## 4. Tests the exporter ships with

- Given a recorded state directory built from synthetic files, the output passes `validate` and `find_private`.
- A missing `reconcile.json`, an unreadable `eod_equity.csv` and a pending official figure each produce UNMEASURED, not a number.
- A record seeded with a key, an IP, an account number and a `client_order_id` produces a snapshot without them (or no snapshot).
- The exporter's source imports no broker client and opens no socket.

## 5. Open questions for the team lead

1. How does a snapshot get from the VM into `dashboard/snapshots/`? (README section 1: not decided.)
2. Confirm the `reconcile.json` fields marked ? above, ideally with one sanitised real night.
3. Do you want position prices or market values? The records hold share counts only.
4. Should `pytest.ini` list `dashboard/tests` so CI runs them? (CI is yours.)
