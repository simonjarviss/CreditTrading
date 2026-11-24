# The research evidence pack

**What it is.** The raw material a research report on this desk will one day be written from:
a dated, append-only evidence log, the live record in sanitised CSVs, and a modest set of
figures and tables rebuilt from committed sources by one command. It is **not the report**,
and it holds no essays. Started 2026-11-03 at the team lead's request ("everything we do
should be logged ... for past and future").

Reproducer: `python3 -m scripts.report.build_pack` (every figure, table and `MANIFEST.json`).

| file | holds |
|---|---|
| `EVIDENCE_LOG.md` | one dated entry per result, ruling, release, incident or live day: figures with `[V]/[S]/[U]`, source file and commit, the report section it supports. Append-only |
| `SOURCES.md` | literature and primary sources the report could cite, each FETCHED or TO VERIFY |
| `data/deployments.csv` | the deployment register: every book and sleeve that ever traded, was armed, or was built and kept off, each row citing its evidence file and commit |
| `data/live/<book>/` | the live record as **daily account-level aggregates**, sanitised by `scripts/report/snapshot_live.py`: equity (EOD record and 17:30 snapshot, labelled), P&L lines, hold and fill totals, fill-cost summaries in bp with counts, order counts, verify and gate outcomes |
| `_cache_live/<book>/` | **gitignored, never committed**: the row-level live records (per-name quantities, per-name and per-fill prices, positions, free-text verify detail). Team lead, 2026-11-03: "Aggregates in repo, rows private" |
| `figures/`, `tables/` | outputs of `build_pack.py`; each figure's footer names its sources, the commit and the data's last date |
| `MANIFEST.json` | every output, its inputs with sha256, the commit, the build time, and the **PENDING** list: each figure the committed data cannot support yet, with exactly what it needs |

## How to append

1. **An entry per event, in the same commit as the change** (`CLAUDE.md`, research rules):
   a result, a ruling, a release, an incident, a live day. The format and the tags are at the
   top of `EVIDENCE_LOG.md`, and `.claude/rules/report.md` repeats them.
2. **Copy every figure from a file you read, and name it with its commit.** Never from memory.
   Where two sources disagree, give both, tag both `[U]`, and say which is the record
   (`docs/SYSTEM.md` §0, order of authority).
3. **Never edit or delete an entry.** A correction is a new dated entry (`kind: correction`)
   naming what it supersedes. `build_pack.py` and `snapshot_live.py` both refuse a log whose
   existing entries changed (`scripts/report/evidence_log.py::check_append_only`).
4. Live days are appended automatically by `snapshot_live.py` (entry ids `E-<date>-90` for the
   core, `-91` for C4).

## The evening procedure

After verify has written the day's line (17:30 ET):

```bash
! sh vmpnl.sh                      # the team lead's local, read-only wrapper: copies the VM's P&L records (eod_equity.csv included) to the scratchpad
python3 -m scripts.report.snapshot_live --src "$(sed -n 's/^OUT="\(.*\)"$/\1/p' vmpnl.sh)" --book cef
git add results/report/data results/report/EVIDENCE_LOG.md && git commit -m "Evidence pack: live day <date>"
python3 -m scripts.report.build_pack   # refuses an uncommitted input, so it runs after the data commit
git add results/report && git commit -m "Evidence pack: rebuild for <date>"
```

`snapshot_live` writes the aggregates under `data/live/` and the rows under the gitignored
`_cache_live/`, and refuses to write a row file anywhere git can see it. C4's pull goes in
the same way with `--book c4`. `distribution_scores.csv` is required in a core pull and
optional in a C4 pull (2026-11-05), because C4's verify scores a session's distributions
two sessions late. Without it, C4 gets no distribution table, its live-day entry says the
distribution-adjusted P&L is UNMEASURED and names the file, and F07 for C4 stays PENDING. `vmpnl.sh` lives at
the main checkout's root and is not tracked. The same steps are in `docs/RUNBOOK.md` §8.6.

**Backing up the private cache is the team lead's step.** The repository has no R2 write
tool: `src/data/r2.py` is read-only by design. From the team lead's own shell, with a
write-capable R2 token loaded (agents never read `config/.env`) and the AWS CLI installed:

```bash
AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
  aws s3 sync results/report/_cache_live/ "s3://$R2_BUCKET/private/report_cache_live/" --endpoint-url "$R2_ENDPOINT"
```

`--endpoint-url` takes R2's https URL; prefix `https://` if `R2_ENDPOINT` holds the bare host.

## Where things go in an eventual report

One line per section; the log's `supports:` field uses these numbers.

| § | section | evidence |
|---|---|---|
| 1 | The deployed book: what trades in each account at the newest release, every spec key and its note, the run pipeline, every gate and its mode, the two-account structure | log §1; `tables/T03_deployed_spec_keys.csv`, `T01_releases.csv` |
| 2 | How we got here: deployments past and present, spec versions, the corrections that shaped the design, venues and releases, the trials that changed live behaviour (50, 52, 53, 54, 55) | log §2; `F01_deployment_timeline`, `F02_spec_lineage`, `T02_spec_lineage`, `F05_c4_trial52`, `F04_trial54_gate0`, `F03_trial53_halve_kill` |
| 3 | The economics: why the discount exists and reverts, who is on the other side, limits to arbitrage, the desk's measured evidence for the mechanism, costs, borrow, capacity, what would falsify it | log §3; `SOURCES.md` |
| 4 | The live record: IBKR paper (history), then Alpaca; the P&L of record against the snapshot; attribution; fills and TCA; distributions paper does not credit | log §4; `F06`–`F10`, `T10`, `T11`, `data/live/` (aggregates; rows in the private cache) |
| 5 | Risk and governance: vol target and stops, HALVE/KILL, margin, gates and refusals, incidents and fixes, the autonomy rulings, model-risk practice, limitations | log §5; `F03`, `F10`; `SOURCES.md` (SR 11-7, SR 26-2) |
| 6 | Appendix, the research record: counters over time, the trial ledger, the graveyard condensed with its two patterns | log §6; `F11_trial_counters`, `T04_counter_history`, `T05_trial_registry`, `docs/RESEARCH_STATE.md` |

## Data licensing, for whoever writes the report

| source | what it feeds | may it be published? |
|---|---|---|
| CRSP, Compustat (through the R2 WRDS mirror) | research panels, Gate 0, C4's identity checks | **No row-level data, permnos or CUSIPs** in any tracked file (`dashboard/README.md` §2, `docs/TEAM.md` §5). Aggregates and statistics only |
| SEC EDGAR | event dates, N-CSR NAVs, N-PORT | public record; cite the filing. EDGAR's fair-access policy needs a declared `User-Agent` (`docs/SYSTEM.md` §5, 2026-10-12) |
| Alpaca (paper account, market data) | the live record, official closes, corporate actions | **daily account-level aggregates only** (team lead, 2026-11-03: "Aggregates in repo, rows private"); per-name quantities, prices, positions and fills stay in the gitignored cache. Market data is under Alpaca's terms: publish derived figures, not raw feeds |
| yfinance (Yahoo) | the price, NAV and distribution panels | for research only under Yahoo's terms; publish derived figures, not the panels |
| CEFConnect | a second NAV source (now unavailable) | its terms prohibit automated commercial use (`results/ops/CEFCONNECT_TERMS_OPTIONS_2026-10-19.md`) |
