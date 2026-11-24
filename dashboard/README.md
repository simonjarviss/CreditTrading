# The public site and its dashboard

**This file owns** what the public site reads, how it reaches the web, and what a snapshot
of the book may never carry. Who keeps this folder is `docs/TEAM.md` §1 (the
dashboard-and-data lane). The rulings behind it are `docs/SYSTEM.md` §5, "Team lead,
2026-10-26" (the dashboard) and "Team lead, 2026-11-23: the public site" (hosting, content,
snapshots kept on the VM). What is true about the book right now is `python3 -m ops.orient`,
never this folder.

The site is the desk's public face for prospective investors: the team, the live paper results
of every book, the research process and the library of sources. quantt.ca, the club's site, is its style reference only.

---

## 1. What it reads, and how it reaches the web

```
the VM (prod)                                                    the web
quantt_state/<book>/  ─┐
shadow SCOREBOARD.md  ─┼─► dashboard.export ─► snapshot.json ─► dashboard.site ─► /srv/quantt-site/current ─► Caddy (HTTPS)
results/IDEA_LEDGER.md │   (read only, no network)              (pages, atomic swap)                          (the origin)
dashboard/content,     ┘
dashboard/public (at the release tag)

event-driven.quantt.ca  =  Cloudflare Worker `quantt-event-driven`, deployed from `main` (dashboard/wrangler.jsonc, build root `dashboard`):
                           a read-only caching proxy; every path, pages and /static/* alike, fetched from the origin above
```

- **Cloudflare is the public face.** The Worker relays every request to the VM and caches the
  answer at the edge: pages for 60 seconds, static files for an hour. It writes nothing and
  forwards no cookie or query string; if the VM cannot be reached it answers 503 with a page
  saying so. The VM's address is the Worker variable `ORIGIN`, set in the Cloudflare dashboard,
  never in the repository.

- **The build reads only files.** `dashboard/export.py` reads the records each runner has
  already written (`eod_equity.csv`, the newest `reconcile.json` or `verify.json`, `tca.csv`,
  the risk report, `sleeve_scores.csv`) and the shadow scoreboard. It makes no broker call
  and opens no connection. Its unit runs with `PrivateNetwork=yes` and the state
  read-only (`dashboard/deploy/install_site_vm.sh`).
- **No code path from it may send, replace or cancel an order** (`CLAUDE.md`, "Any monitor
  is read-only"). Every module imports only the standard library; `dashboard/tests` pins
  that by AST.
- **The web server serves static files only.** Caddy, as user `caddy`, serves
  `/srv/quantt-site/current` and nothing else. It cannot read the trading state or a key.
- **The site rebuilds every 30 minutes** (at :20 and :50 New York time), so each new record
  reaches the page within half an hour. The books trade once a day at the close; the page
  shows each session's after-close reading as soon as verify records it, labelled, until
  Alpaca's official end-of-day point arrives in the night.
- **Snapshots stay on the VM.** The 2026-10-26 plan to commit a nightly snapshot to
  `dashboard/snapshots/` is superseded (team lead, 2026-11-23): the page is built where the
  records are, and nothing about positions or P&L is committed to the repository.
- **The site has its own clone** on the VM, `/home/quantt/site/quantt-alpaca`, at a release
  tag. Releasing the site never moves the trading clone, so it never changes what the books
  trade; a trading release never moves the site.
- **What changes with a site release** (the VM's site clone moves to a new tag): everything a
  visitor sees, the words (`dashboard/site.py`), the team (`dashboard/content/team.json`), the
  library (`dashboard/content/library.json`) and the styles, fonts and photographs
  (`dashboard/public/`). **What changes with a merge to `main`** is only the Worker
  (`dashboard/worker/index.js`, `dashboard/wrangler.jsonc`), which Cloudflare rebuilds.

## 2. What a snapshot, and therefore the site, may never carry

The site is public. Everything on it can be copied and kept.

| never | why |
|---|---|
| a key, a token, or anything read from `config/.env` | `CLAUDE.md`, hard rule 5 |
| the Alpaca account number or id, an order id, a `client_order_id` | they identify the account |
| any per-name figure: a symbol held or traded, a share count, an order line, or the runners' note text | team lead, 2026-11-23: "aggregates only". Each session is counts and dollar exposure; the rows stay in the runners' records on the VM |
| the VM's address or hostname, the vault's name, the subscription, a path on the VM | `CLAUDE.md`, "Where it runs" |
| row-level licensed data: CRSP, TRACE, Compustat, permnos, CUSIPs | the licence, and `docs/TEAM.md` §5 |
| a figure with no source and no read time | `CLAUDE.md`, "Hard rules: data". A number the exporter could not measure is written as not measured, never filled in |

`dashboard.snapshot.find_private` checks every string and key of every snapshot against this
table, and the exporter and the site both refuse to write anything that fails it. The host
names are arguments to the installer and are never written in this repository.

## 3. The snapshot's schema

`dashboard/snapshot.py`, version 0.3: a list of books, each with five readings (`official`,
`session`, `risk`, `execution`, `sleeves`), and the shadow scoreboard. A session is aggregates
only: the verdict word, the number of notes, position counts with gross and net exposure, and
order counts (0.3, team lead, 2026-11-23). Every reading is one of
`value` (with `source`, `read_at` and a label: broker-confirmed, modelled or simulated),
`absent` (with why) or `UNMEASURED` (with what was tried), the convention of
`ops/prod_state.py`. Version 0.1-draft was Lucy's first pull request (#62); 0.2 kept its
reading convention and privacy check and widened it to every book; 0.3 removes every per-name field. The committed fixture
(`dashboard/fixtures/sample_snapshot.json`) is regenerated by
`python3 -m dashboard.fixtures.make_fixture` from synthetic records in the runners' real file
formats, and a test checks it was.

## 4. Running it

```bash
python3 -m pytest dashboard/tests                                  # the suite (CI runs it)
python3 -m dashboard.build dashboard/fixtures/sample_snapshot.json -o /tmp/perf.html   # one page from the fixture
python3 -m dashboard.fixtures.make_fixture                         # after a change to the exporter
```

On the VM, `docs/RUNBOOK.md` §8.13 has the install, the checks and the uninstall.
