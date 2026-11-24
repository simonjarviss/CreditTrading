"""CRSP distribution declaration dates (`dsedist.dclrdt`) for the 17 credit CEFs, 2023-01-01 .. 2024-12-31.

    QUANTT_ENV_FILE=<env file> python3 scripts/events/fetch_exdrift_crsp_decl.py pull   # the team lead runs this (R2)
    python3 scripts/events/fetch_exdrift_crsp_decl.py pull --dry-run                    # the plan only; no key, no network
    python3 scripts/events/fetch_exdrift_crsp_decl.py stage --from <dir with dsenames.parquet and dsedist_*.parquet>

WHY THIS EXISTS (team lead's ruling, 2026-10-28)
-------------------------------------------------
DG-X2 of `results/events/PREREG_EXDATE_DRIFT_2026-10-26.md` needs a declaration date for every
test event. The sponsors' own releases (`fetch_exdrift_sponsor_releases.py`) cover every fund but
Nuveen's: Nuveen stopped declaring by press release in November 2019, so only 42 of its 226 test
events were found. The team lead ruled: "Nuveen declarations: recover via CRSP". CRSP's
distribution table carries the declaration date `dclrdt`, beside `exdt`, `rcrddt`, `paydt` and
`divamt` (`results/events/ssx/ssx_data/r2_full_inventory_columns_2026-10-19.csv`:
`crsp_a_stock.dsedist`). The mirror ends 2024-12-31 (same inventory), so CRSP can recover
2023-24 only.

WHAT IT READS. Two tables of the R2 WRDS mirror (`crsp_a_stock`), through `src.data.r2`:
- `dsenames`, for the permno of each of the 17 tickers. The filter is ticker in the 17, share
  code 14/44 (CEFs) and a name record that overlaps the window. Exactly one permno per ticker is
  required; anything else raises.
- `dsedist` for those permnos, with `exdt` in the window: `permno, distcd, divamt, dclrdt, exdt,
  rcrddt, paydt`. These are distribution records, not returns.

The 27 sealed `cef_universe.csv` names are never requested: the SQL filters on the 17 tickers
and then on their permnos.

TWO WAYS TO GET THE ROWS
- `pull` (the team lead, with `QUANTT_ENV_FILE`) reads the mirror live. It copies the house
  pattern of `stage_bdc_and_cefetf.py` (r7):
  - credentials only via `src.data.r2.load_config`;
  - a `Redactor` on every printed line and error;
  - the bucket shown as `<bucket>`;
  - the manifest written last and holding the SQL template, never the bucket;
  - `--dry-run` loads no config.
- `stage --from DIR` (offline) builds the same outputs from an extract of the same tables that is
  already cached on this machine. Examples are `results/events/_cache_crsp/` in a sibling worktree,
  pulled by `scripts/events/crsp_events.py`'s `dsedist` and `dsenames` SQL. It records the source
  file, its sha256 prefix and the manifest's pull time. It reads with parquet filters on the 17
  tickers and their permnos.

OUTPUT: the gitignored `results/events/exdrift/_cache_exdrift/crsp_decl/`. CRSP rows are
licensed, and the repository is public. `check_out` refuses any folder that `git check-ignore`
does not report as ignored.

Tests: `scripts/events/tests/test_fetch_exdrift_crsp_decl.py` (a fake source; no network).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events" / "exdrift" / "_cache_exdrift" / "crsp_decl"
DIST_FILE, PERM_FILE, MANIFEST = "crsp_dsedist_2023_2024.parquet", "crsp_permnos.parquet", "manifest.json"
LO, HI = dt.date(2023, 1, 1), dt.date(2024, 12, 31)
DIST_COLS = ["permno", "distcd", "divamt", "dclrdt", "exdt", "rcrddt", "paydt"]


class CrspDeclError(RuntimeError):
    """A CRSP extract that cannot be recorded as what it is; named, never filled."""


def names17() -> list[str]:
    from scripts.events.exdrift_trial import NAMES
    return list(NAMES)


class Redactor:
    """Replaces every credential value (and the bucket and endpoint) in a text (r7's pattern)."""

    def __init__(self, values: dict[str, str] | None = None):
        self._pairs = sorted(((v, tag) for v, tag in (values or {}).items() if v), key=lambda p: -len(p[0]))

    def __call__(self, text: str) -> str:
        for v, tag in self._pairs:
            text = text.replace(v, tag)
        return text


@dataclass
class Source:
    con: object
    path: Callable[[str, str], str]
    redact: Redactor

    def df(self, sql: str) -> pd.DataFrame:
        return self.con.execute(sql).df()


def r2_source() -> Source:
    from src.data import r2
    cfg = r2.load_config()
    red = Redactor({cfg.access_key_id: "<redacted>", cfg.secret_access_key: "<redacted>",
                    cfg.endpoint_host: "<endpoint>", cfg.bucket: "<bucket>"})
    try:
        con = r2.connect(cfg)
    except Exception as exc:       # re-raised redacted; nothing swallowed
        raise CrspDeclError(f"R2 connection failed: {type(exc).__name__}: {red(str(exc))}") from None
    return Source(con=con, path=lambda s, t: r2.r2_path(s, t, cfg), redact=red)


def _tick_list(ts) -> str:
    for t in ts:
        if not t.isalpha() or not t.isupper():
            raise ValueError(f"ticker {t!r} is not an upper-case symbol")
    return ",".join(f"'{t}'" for t in sorted(ts))


def names_sql(path: str, tickers) -> str:
    return (f"SELECT permno, ticker, namedt, nameendt, shrcd FROM read_parquet('{path}') "
            f"WHERE ticker IN ({_tick_list(tickers)}) AND shrcd IN (14, 44) "
            f"AND nameendt >= DATE '{LO.isoformat()}' AND namedt <= DATE '{HI.isoformat()}'")


def dist_sql(path: str, permnos) -> str:
    ps = ",".join(str(int(p)) for p in sorted(permnos))
    return (f"SELECT {', '.join(DIST_COLS)} FROM read_parquet('{path}') WHERE permno IN ({ps}) "
            f"AND exdt >= DATE '{LO.isoformat()}' AND exdt <= DATE '{HI.isoformat()}'")


def permno_map(nm: pd.DataFrame, tickers) -> pd.DataFrame:
    """One permno per ticker over the window, or raise naming every ticker that has none or two."""
    nm = nm[nm.ticker.isin(tickers) & nm.shrcd.isin([14, 44])].copy()
    for c in ("namedt", "nameendt"):
        nm[c] = pd.to_datetime(nm[c])
    nm = nm[(nm.nameendt >= pd.Timestamp(LO)) & (nm.namedt <= pd.Timestamp(HI))]
    g = nm.groupby("ticker").permno.nunique()
    bad = sorted(set(tickers) - set(g.index)) + sorted(g[g != 1].index)
    if bad:
        raise CrspDeclError(f"tickers without exactly one CEF permno in {LO}..{HI}: {bad}")
    return nm.drop_duplicates("ticker")[["ticker", "permno"]].sort_values("ticker").reset_index(drop=True)


def tidy(d: pd.DataFrame, perm: pd.DataFrame) -> pd.DataFrame:
    """Dates as dates, the ticker joined on, the window asserted (a row outside it raises)."""
    d = d[DIST_COLS].copy()
    for c in ("dclrdt", "exdt", "rcrddt", "paydt"):
        d[c] = pd.to_datetime(d[c])
    d = d.merge(perm, on="permno", how="left")
    if d.ticker.isna().any():
        raise CrspDeclError("dsedist rows for a permno outside the 17")
    if len(d) and ((d.exdt < pd.Timestamp(LO)) | (d.exdt > pd.Timestamp(HI))).any():
        raise CrspDeclError(f"a dsedist row outside {LO}..{HI} came back")
    missing = sorted(set(perm.ticker) - set(d.ticker))
    if missing:
        raise CrspDeclError(f"no dsedist row in {LO}..{HI} for {missing}")
    return d.sort_values(["ticker", "exdt"]).reset_index(drop=True)


def check_out(out: Path) -> None:
    rel = out.resolve().relative_to(REPO.resolve()) if out.resolve().is_relative_to(REPO.resolve()) else None
    if rel is None:
        return
    r = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", str(rel / "probe.parquet")])
    if r.returncode != 0:
        raise CrspDeclError(f"{out} is inside the repository and not gitignored: CRSP rows must never be committable")


def write(out: Path, d: pd.DataFrame, perm: pd.DataFrame, meta: dict) -> dict:
    from ops.common import atomic_write
    check_out(out)
    out.mkdir(parents=True, exist_ok=True)
    atomic_write(d, out / DIST_FILE)
    atomic_write(perm, out / PERM_FILE)
    man = {**meta, "rows": int(len(d)), "tickers": int(d.ticker.nunique()),
           "exdt_range": [str(d.exdt.min().date()), str(d.exdt.max().date())] if len(d) else None,
           "dclrdt_null": int(d.dclrdt.isna().sum()),
           "written_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    (out / MANIFEST).write_text(json.dumps(man, indent=1, sort_keys=True))      # written last
    return man


def pull(args, emit, source_factory) -> int:
    t17 = names17()
    shown = lambda t: f"s3://<bucket>/wrds/crsp_a_stock/{t}.parquet"           # noqa: E731
    if args.dry_run:
        emit(f"PLAN (dry run; no config loaded, no connection):\n  1. {names_sql(shown('dsenames'), t17)}\n"
             f"  2. {dist_sql(shown('dsedist'), [0])}  -- with the permnos of step 1\n  -> {args.out}")
        return 0
    src = source_factory()
    nm = src.df(names_sql(src.path("crsp_a_stock", "dsenames"), t17))
    perm = permno_map(nm, t17)
    d = tidy(src.df(dist_sql(src.path("crsp_a_stock", "dsedist"), perm.permno)), perm)
    man = write(args.out, d, perm, {"how": "pull (R2, live)", "names_sql": names_sql(shown("dsenames"), t17),
                                    "dist_sql_template": dist_sql(shown("dsedist"), [0]).replace("IN (0)", "IN (<permnos>)")})
    emit(f"{man['rows']} dsedist rows for {man['tickers']} tickers, exdt {man['exdt_range']}, dclrdt null "
         f"{man['dclrdt_null']} -> {args.out}")
    return 0


def stage(args, emit) -> int:
    """Offline: the same outputs from a cached extract of the same tables (no network, no key)."""
    src = Path(args.from_dir)
    t17 = names17()
    nm = pd.read_parquet(src / "dsenames.parquet", filters=[("ticker", "in", t17)])
    perm = permno_map(nm, t17)
    ps = [int(p) for p in perm.permno]
    files = sorted(src.glob("dsedist_*.parquet"))
    if not files:
        raise CrspDeclError(f"no dsedist_*.parquet in {src}")
    man_src = json.loads((src / "_manifest.json").read_text()) if (src / "_manifest.json").exists() else {}
    best = None
    for f in files:
        d = pd.read_parquet(f, columns=DIST_COLS, filters=[("permno", "in", ps)])
        d = d[(pd.to_datetime(d.exdt) >= pd.Timestamp(LO)) & (pd.to_datetime(d.exdt) <= pd.Timestamp(HI))]
        if d.permno.nunique() == len(ps) and (best is None or len(d) > len(best[1])):
            best = (f, d)
    if best is None:
        raise CrspDeclError(f"no extract in {src} covers all {len(ps)} permnos in {LO}..{HI}")
    f, d = best
    d = tidy(d, perm)
    h = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
    man = write(args.out, d, perm, {"how": "stage (offline, from a cached extract)", "source_file": str(f),
                                    "source_sha16": h, "source_pulled_utc": man_src.get(f.stem, {}).get("pulled_utc"),
                                    "source_sql_head": (man_src.get(f.stem, {}).get("sql") or "")[:160]})
    emit(f"{man['rows']} dsedist rows for {man['tickers']} tickers from {f.name} (pulled "
         f"{man['source_pulled_utc']}) -> {args.out}")
    return 0


def main(argv=None, source_factory: Callable[[], Source] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pull")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", type=Path, default=OUT)
    s = sub.add_parser("stage")
    s.add_argument("--from", dest="from_dir", required=True)
    s.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    holder = {"red": Redactor()}

    def factory() -> Source:
        src = (source_factory or r2_source)()
        holder["red"] = src.redact
        return src

    def emit(text: str) -> None:
        print(holder["red"](text), flush=True)

    try:
        return pull(a, emit, factory) if a.cmd == "pull" else stage(a, emit)
    except Exception:                      # reported redacted, never swallowed: exit 1
        print(holder["red"](traceback.format_exc()), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
