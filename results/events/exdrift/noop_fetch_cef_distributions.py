"""No-op proof for the default-off `--out` / `--tickers` options of scripts/fetch_cef_distributions.py.

    python3 -I -B results/events/exdrift/noop_fetch_cef_distributions.py   # from the repo root

WHY. The script is on the live path: the nightly collector runs it bare and it replaces
`data/cef/cef_distributions.parquet`. The 2026-10-27 edit moved its module-level code into
functions and added two options, both off by default. This proves that a bare run is
unchanged: the file as it stood at BASE (taken from git) and the edited file are each run in
their own temporary tree on the SAME fake yfinance (synthetic actions and .info for three
names, one of them EMPTY so the `.dividends` branch runs) with the clock frozen, and every
file each writes, and everything each prints, is compared byte for byte.

Synthetic data is right here: the claim is about our code, not about any market. No network,
no data/ read or written (each tree has its own data/cef/ with a synthetic price panel).
Output: results/events/exdrift/noop_fetch_cef_distributions_output.txt
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import runpy
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
BASE = "66ec3df"                      # `simon` at the cut of branch exdrift-stage0
REL = "scripts/fetch_cef_distributions.py"
OUT = Path(__file__).with_name("noop_fetch_cef_distributions_output.txt")


def fake_yfinance() -> types.ModuleType:
    idx = pd.DatetimeIndex(["2024-01-12", "2024-02-13", "2024-03-12", "2025-08-19"]).tz_localize("America/New_York")
    acts = {"AAA": pd.DataFrame({"Dividends": [0.10, 0.10, 0.11, 0.0], "Stock Splits": [0.0, 0.0, 0.0, 0.3333]}, index=idx),
            "BBB": pd.DataFrame({"Dividends": [0.05, 0.0, 0.06, 0.07], "Stock Splits": [0.0, 0.0, 0.0, 0.0]}, index=idx),
            "CCC": pd.DataFrame(columns=["Dividends", "Stock Splits"])}
    divs = {"CCC": pd.Series([0.2, 0.21], index=idx[:2], name="Dividends")}

    class Ticker:
        def __init__(self, tk):
            self.tk = tk

        @property
        def actions(self):
            return acts[self.tk]

        @property
        def dividends(self):
            return divs.get(self.tk, pd.Series(dtype=float))

        @property
        def info(self):
            return {"symbol": self.tk, "quoteType": "MUTUALFUND", "longName": f"{self.tk} Fund\nInc",
                    "longBusinessSummary": "uses leverage " * 50, "yield": 0.08}

    m = types.ModuleType("yfinance")
    m.Ticker = Ticker
    return m


def run_tree(src_text: str, root: Path) -> tuple[dict, str]:
    (root / "scripts").mkdir(parents=True)
    cef = root / "data" / "cef"
    cef.mkdir(parents=True)
    pd.DataFrame({"ticker": ["AAA", "BBB", "CCC"], "grp": ["taxable", "taxable", "muni"]}).to_csv(cef / "cef_universe.csv", index=False)
    d = pd.bdate_range("2024-01-02", "2025-09-01")
    px = pd.concat([pd.DataFrame({"date": d, "ticker": t, "close": 10.0 + i}) for i, t in enumerate(["AAA", "BBB", "CCC"])])
    px.to_parquet(cef / "cef_prices.parquet", index=False)
    before = {p.name for p in cef.iterdir()}
    script = root / REL
    script.write_text(src_text)
    buf = io.StringIO()
    saved = (sys.modules.get("yfinance"), time.sleep, pd.Timestamp.utcnow, list(sys.argv))
    sys.modules["yfinance"] = fake_yfinance()
    time.sleep = lambda s: None
    pd.Timestamp.utcnow = staticmethod(lambda: pd.Timestamp("2026-10-27 12:00:00", tz="UTC"))
    sys.argv = [str(script)]
    try:
        with contextlib.redirect_stdout(buf):
            try:
                runpy.run_path(str(script), run_name="__main__")
            except SystemExit as e:
                if e.code not in (0, None):
                    raise
    finally:
        yfm, time.sleep, pd.Timestamp.utcnow, sys.argv = saved[0], saved[1], saved[2], saved[3]
        if yfm is None:
            sys.modules.pop("yfinance", None)
        else:
            sys.modules["yfinance"] = yfm
    files = {p.name: p.read_bytes() for p in sorted(cef.iterdir()) if p.name not in before or p.name == "cef_prices.parquet"}
    return files, buf.getvalue().replace(str(root), "<ROOT>")


def main() -> int:
    if str(REPO) not in sys.path:
        sys.path.append(str(REPO))                       # ops.common, for atomic_write
    old = subprocess.run(["git", "-C", str(REPO), "show", f"{BASE}:{REL}"], check=True,
                         capture_output=True, text=True).stdout
    new = (REPO / REL).read_text()
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        fo, so = run_tree(old, Path(a))
        fn, sn = run_tree(new, Path(b))
    lines = [f"no-op proof, {REL}: {BASE} (from git) vs the working tree; fake yfinance, frozen clock"]
    ok = set(fo) == set(fn) and so == sn
    lines.append(f"files written: old {sorted(fo)}; new {sorted(fn)}")
    for k in sorted(set(fo) | set(fn)):
        ho = hashlib.sha256(fo.get(k, b"")).hexdigest()[:16]
        hn = hashlib.sha256(fn.get(k, b"")).hexdigest()[:16]
        same = fo.get(k) == fn.get(k)
        ok &= same
        lines.append(f"  {k:<28} old {ho}  new {hn}  {'IDENTICAL' if same else 'DIFFERENT'}")
    lines.append(f"stdout: {'IDENTICAL' if so == sn else 'DIFFERENT'} ({len(so.splitlines())} lines)")
    lines.append("RESULT: " + ("PASS, a bare run is byte-for-byte unchanged" if ok else "FAIL"))
    txt = "\n".join(lines)
    print(txt)
    OUT.write_text(txt + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
