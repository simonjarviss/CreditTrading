"""Extract fund-of-CEF ETF market value (AUM proxy) from archived issuer overview pages.

WHY: demand = ETF AUM x weight change; the AUM must be sourced, never assumed.
PowerShares overview pages (2010-2013) print "Shares Outstanding|x MM|Market Value|$y MM"
next to an "As of m/d/yyyy" quote date. Market value = shares x market price, which
differs from net assets by the ETF's own (small) premium; labelled as such.
Output: out/aum_points.csv (etf, asof, shares_mm, mktval_musd, source_file).
"""
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from parse_snapshots import _text  # noqa: E402

rows = []
for f in sorted((HERE / "raw/wayback/snaps").glob("pcef_ov_*.bin")):
    t = _text(f.read_text(errors="replace"))
    m = re.search(r"As of (\d{1,2}/\d{1,2}/\d{4})[^|]*\|Previous Close.*?Shares Outstanding\|([\d\.]+)MM\|Market Value\|\$([\d\.,]+)MM", t)
    if not m:
        m2 = re.search(r"Shares Outstanding\|([\d\.]+)MM\|Market Value\|\$([\d\.,]+)MM", t)
        d = re.findall(r"As of (\d{1,2}/\d{1,2}/\d{4})", t)
        if not m2 or not d:
            raise ValueError(f"{f.name}: no shares/market value")
        rows.append(("PCEF", pd.Timestamp(d[0]), float(m2.group(1)), float(m2.group(2).replace(",", "")), f.name))
    else:
        rows.append(("PCEF", pd.Timestamp(m.group(1)), float(m.group(2)), float(m.group(3).replace(",", "")), f.name))
df = pd.DataFrame(rows, columns=["etf", "asof", "shares_mm", "mktval_musd", "source_file"]).drop_duplicates(["etf", "asof"])
(HERE / "out").mkdir(exist_ok=True)
df.to_csv(HERE / "out/aum_points.csv", index=False)
print(df.to_string())
