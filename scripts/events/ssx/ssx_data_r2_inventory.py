"""Every schema and table in the R2 WRDS mirror, not just the curated six. Read-only.

    QUANTT_ENV_FILE=/abs/path/config/.env \
        python3 scripts/events/ssx/ssx_data_r2_inventory.py [--threads 8]

Writes (bucket name redacted to `<bucket>` everywhere):
    results/events/ssx/ssx_data/r2_full_inventory_2026-10-19.csv   one row per table
    results/events/ssx/ssx_data/r2_full_inventory_columns_2026-10-19.csv  one row per column
    results/events/ssx/ssx_data/r2_full_inventory_2026-10-19.json  run stamp + manifest notes

WHY THIS EXISTS
---------------
`results/data/R2_CATALOG.md` (2026-09-28) lists only the schemas the team lead
named that day, and desk notes since then repeated "the WRDS mirror holds about
412 tables". Both are recalled inventories. The event-driven expansion
(team lead, 2026-10-19) needs to know whether Compustat, IBES, Thomson 13F,
Thomson insiders, SDC, Audit Analytics, Mergent FISD and OptionMetrics are in
the bucket before anyone plans a fetcher for something we may already hold.
So this script enumerates `s3://<bucket>/wrds/**` with DuckDB `glob()` and
describes every object it finds. "412" turns out to be the entry count of the
mirror's own `wrds/manifest.json` (an ingestion log keyed by WRDS library and,
for big tables, by year chunk), not the number of tables; the JSON output
records that count beside the measured one so the two cannot be confused again.

WHAT IT MEASURES, AND HOW (all footer-only; no table is scanned)
----------------------------------------------------------------
  * size and last-modified  -- `read_blob(...)` projecting only `size` and
    `last_modified`, which DuckDB answers with a HEAD per object (the content
    column is never read);
  * row count, row groups   -- `parquet_file_metadata()`, the parquet footer;
  * columns and types       -- `parquet_schema()`, the footer; logical type
    DATE / TIMESTAMP is taken from the footer, never guessed from a name;
  * min/max of each DATE/TIMESTAMP column -- the min of the row groups'
    `stats_min_value` and the max of their `stats_max_value`
    (`parquet_metadata()`). These are the writer's own statistics. If ANY row
    group lacks a statistic for that column the range is reported as
    `NO_STATS`, never as a partial range, because a partial min/max would be a
    confident wrong number. Dates stored as strings or integers are not parsed
    (that would be guessing a format); the column list shows them and the
    reader decides.

A file that cannot be described is recorded with its error text and the script
exits 1 after writing everything else, so a run cannot report success over a
hole. It never writes to the bucket.

The top-level `portfolios/` prefix in the bucket is NOT read: it is not part of
the WRDS mirror and holds per-person files that are no business of this survey.
Only its object count is recorded.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import json
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT_DIR = REPO / "results" / "events" / "ssx" / "ssx_data"
STAMP = "2026-10-19"

_DATE_LOGICAL = ("DateType", "TimestampType")
_local = threading.local()


def _con():
    """One DuckDB connection per worker thread (a connection is not thread-safe)."""
    from src.data import r2
    if getattr(_local, "con", None) is None:
        _local.con = r2.connect()
    return _local.con


def _redact(s: str, base: str) -> str:
    return s.replace(base, "s3://<bucket>")


def describe(path: str, base: str) -> dict:
    """Footer-only description of one parquet object. Errors are returned, not raised."""
    rel = path[len(base):].strip("/")            # wrds/<schema>/<table>.parquet
    _, schema, fname = rel.split("/", 2)
    out = {"schema": schema, "table": fname.removesuffix(".parquet"), "rows": None,
           "row_groups": None, "columns": [], "date_ranges": {}, "error": None}
    try:
        con = _con()
        fm = con.execute("SELECT num_rows, num_row_groups FROM parquet_file_metadata(?)",
                         [path]).fetchone()
        out["rows"], out["row_groups"] = int(fm[0]), int(fm[1])
        sch = con.execute(
            "SELECT name, type, CAST(logical_type AS VARCHAR), converted_type "
            "FROM parquet_schema(?)", [path]).fetchall()
        cols = []
        for name, ptype, ltype, ctype in sch[1:]:      # row 0 is the root 'schema' node
            lt = ltype or ""
            is_date = lt.startswith(_DATE_LOGICAL) or (ctype in ("DATE", "TIMESTAMP_MILLIS",
                                                                  "TIMESTAMP_MICROS"))
            cols.append((name, ptype, lt.split("(")[0] if lt else (ctype or ""), is_date))
        out["columns"] = cols
        date_cols = [c[0] for c in cols if c[3]]
        if date_cols and out["rows"]:
            md = con.execute(
                "SELECT path_in_schema, stats_min_value, stats_max_value "
                "FROM parquet_metadata(?) WHERE path_in_schema IN (SELECT unnest(?))",
                [path, date_cols]).fetchall()
            by: dict[str, list] = {c: [] for c in date_cols}
            for p, lo, hi in md:
                by.setdefault(p, []).append((lo, hi))
            for c, pairs in by.items():
                if not pairs or any(lo is None or hi is None for lo, hi in pairs):
                    # A row group of all-NULLs also has no min/max; reporting the
                    # others' range would still be right for the non-null values,
                    # but we cannot tell that case from a missing statistic here.
                    out["date_ranges"][c] = "NO_STATS"
                else:
                    out["date_ranges"][c] = (min(lo for lo, _ in pairs), max(hi for _, hi in pairs))
    except Exception as exc:  # recorded and fails the exit code; never swallowed
        out["error"] = _redact(f"{type(exc).__name__}: {str(exc)[:300]}", base)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args(argv)

    from src.data import r2
    cfg = r2.load_config()
    base = f"s3://{cfg.bucket}"
    con = r2.connect(cfg)
    run_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    every = [r[0] for r in con.execute("SELECT file FROM glob(?) ORDER BY file",
                                       [f"{base}/wrds/**"]).fetchall()]
    pq = [f for f in every if f.endswith(".parquet")]
    other = [_redact(f, base) for f in every if not f.endswith(".parquet")]
    blobs = {r[0]: (int(r[1]), str(r[2])) for r in con.execute(
        "SELECT filename, size, last_modified FROM read_blob(?)", [f"{base}/wrds/*/*.parquet"]
    ).fetchall()}
    n_portfolios = con.execute("SELECT count(*) FROM glob(?)", [f"{base}/portfolios/**"]).fetchone()[0]
    manifest_n = None
    try:
        manifest_n = len(json.loads(con.execute(
            "SELECT content FROM read_text(?)", [f"{base}/wrds/manifest.json"]).fetchone()[0]))
    except Exception as exc:  # recorded, not hidden
        manifest_n = f"unreadable: {type(exc).__name__}"

    with cf.ThreadPoolExecutor(max_workers=args.threads) as ex:
        reps = list(ex.map(lambda p: describe(p, base), pq))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    errors = 0
    with open(OUT_DIR / f"r2_full_inventory_{STAMP}.csv", "w", newline="") as fh, \
         open(OUT_DIR / f"r2_full_inventory_columns_{STAMP}.csv", "w", newline="") as fc:
        w = csv.writer(fh)
        w.writerow(["schema", "table", "size_mb", "last_modified", "rows", "row_groups",
                    "n_columns", "date_ranges", "error"])
        wc = csv.writer(fc)
        wc.writerow(["schema", "table", "column", "physical_type", "logical_type"])
        for p, rep in zip(pq, reps):
            size, lm = blobs.get(p, (None, None))
            dr = "; ".join(f"{k}={v if isinstance(v, str) else v[0] + '..' + v[1]}"
                           for k, v in rep["date_ranges"].items())
            w.writerow([rep["schema"], rep["table"],
                        None if size is None else round(size / 1e6, 2), lm, rep["rows"],
                        rep["row_groups"], len(rep["columns"]), dr, rep["error"]])
            for name, ptype, lt, _ in rep["columns"]:
                wc.writerow([rep["schema"], rep["table"], name, ptype, lt])
            errors += rep["error"] is not None
    summary = {
        "run_utc": run_utc, "script": "scripts/events/ssx/ssx_data_r2_inventory.py",
        "objects_under_wrds": len(every), "parquet_tables": len(pq),
        "schemas": len({r["schema"] for r in reps}), "non_parquet_objects": other,
        "manifest_json_entries": manifest_n,
        "portfolios_prefix_objects_not_read": int(n_portfolios),
        "describe_errors": errors,
        "total_size_gb": round(sum(v[0] for v in blobs.values()) / 1e9, 2),
    }
    (OUT_DIR / f"r2_full_inventory_{STAMP}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
