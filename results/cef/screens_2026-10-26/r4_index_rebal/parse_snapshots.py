"""Parse archived fund-of-CEF ETF holdings snapshots into one long table.

WHY: the event reconstruction needs, for each snapshot date, the ETF's constituent
tickers and weights. The archived pages come in three formats:
  * PowerShares-era PCEF holdings page (2010-2013): server-rendered rows
    `TICKER | Name | x.xx%` grouped under sector headers; date in "As of m/d/yyyy".
  * Amplify family holdings CSV (2020-2021): one row per holding, with Account (ETF
    ticker), Shares, Price, MarketValue, Weightings and NetAssets.
  * YieldShares-era YYY holdings page (2013-2017): rows
    `NAME | TICKER | shares | $mv | % mkt value | % net assets` after "Holdings as of".
  * Amplify yyy-holdings page (2022+): JavaScript-filled ("Holdings as of TBD") in every
    archived capture, so it carries no holdings and is NOT parsed (recorded in NOTE.md).
Every parsed snapshot asserts that weights sum to roughly 100% of the parsed rows;
a snapshot that does not parse raises naming the file (no silent skip).

Output: out/holdings_snapshots.csv (etf, asof, source_file, ticker, name, weight_pct,
market_value, net_assets). Reads only raw/ in this folder.
"""
from __future__ import annotations

import html
import io
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SNAPS = HERE / "raw" / "wayback" / "snaps"
OUT = HERE / "out"


def _text(raw: str) -> str:
    t = re.sub(r"<script.*?</script>", "", raw, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", "", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", "|", t)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"(\|\s*)+", "|", t)


def parse_pcef_ps(p: Path) -> pd.DataFrame | None:
    t = _text(p.read_text(encoding="utf-8", errors="replace"))
    m = re.search(r"PCEF - CEF Income Composite Portfolio\|As of (\d{1,2}/\d{1,2}/\d{4})", t)
    if not m:
        raise ValueError(f"{p.name}: no 'As of' date for PCEF")
    asof = pd.Timestamp(m.group(1))
    body = t[m.end():]
    end = body.find("Fund Holdings are subject")
    # holdings run until the footer; rows are |TICKER|Name|w%|
    # the 2013-08+ layout pads the ticker cell with a trailing space ("ACG |")
    rows = re.findall(r"\|([A-Z]{1,5}) ?\|([^|]{3,90})\|(\d{1,2}\.\d{2})%", body)
    if not rows and "% of Fund" not in body:
        # the Aug and Dec 2013 captures use a new layout that loads the table by
        # script: the archived page carries no holdings. Recorded, not guessed.
        print(f"  {p.name}: no holdings table in this capture (script-loaded layout)")
        return None
    if len(rows) < 20:
        raise ValueError(f"{p.name}: only {len(rows)} holdings rows parsed")
    df = pd.DataFrame(rows, columns=["ticker", "name", "weight_pct"])
    df["weight_pct"] = df.weight_pct.astype(float)
    df = df.drop_duplicates("ticker")
    s = df.weight_pct.sum()
    if not 95 <= s <= 101.5:
        raise ValueError(f"{p.name}: PCEF weights sum to {s:.2f}%")
    df.insert(0, "asof", asof)
    df.insert(0, "etf", "PCEF")
    df["market_value"] = float("nan")
    df["net_assets"] = float("nan")
    return df


def parse_amp_csv(p: Path) -> pd.DataFrame:
    d = pd.read_csv(io.StringIO(p.read_text(encoding="utf-8", errors="replace")))
    d = d[d.Account.astype(str).str.strip() == "YYY"].copy()
    if d.empty:
        raise ValueError(f"{p.name}: no YYY rows")
    d["weight_pct"] = d.Weightings.astype(str).str.rstrip("%").astype(float)
    out = pd.DataFrame({
        "etf": "YYY", "asof": pd.to_datetime(d.Date), "ticker": d.StockTicker.astype(str).str.strip(),
        "name": d.SecurityName, "weight_pct": d.weight_pct,
        "market_value": d.MarketValue.astype(float), "net_assets": d.NetAssets.astype(float)})
    if out["asof"].nunique() != 1:
        raise ValueError(f"{p.name}: several dates in one YYY file")
    s = out.weight_pct.sum()
    if not 95 <= s <= 101.5:
        raise ValueError(f"{p.name}: YYY weights sum to {s:.2f}%")
    return out


def parse_yieldshares(p: Path) -> pd.DataFrame | None:
    """Returns None for the 2017+ captures whose page no longer carries the table
    (they print no 'Holdings as of' date); raises if a dated page does not parse."""
    t = _text(p.read_text(encoding="utf-8", errors="replace"))
    m = re.search(r"Holdings as of (\d{1,2}/\d{1,2}/\d{4}):", t)
    if not m:
        return None
    body = t[m.end():]
    rows = re.findall(r"\|([^|]{3,40})\|([A-Z]{1,5})\|([\d,]+)\|\$([\d,\.]+)\|([\d\.]+)%\|([\d\.]+)%", body)
    if len(rows) < 15:
        raise ValueError(f"{p.name}: only {len(rows)} YieldShares rows parsed")
    df = pd.DataFrame(rows, columns=["name", "ticker", "shares", "mv", "w_mv", "w_na"])
    df["market_value"] = df.mv.str.replace(",", "").astype(float)
    df["weight_pct"] = df.w_na.astype(float)
    # net assets implied by each row (mv / % of net assets); they must agree
    na = df.market_value / (df.weight_pct / 100)
    if (na.max() / na.min()) > 1.02:
        raise ValueError(f"{p.name}: implied net assets disagree across rows ({na.min():.0f}..{na.max():.0f})")
    out = pd.DataFrame({"etf": "YYY", "asof": pd.Timestamp(m.group(1)), "ticker": df.ticker,
                        "name": df.name.str.strip(), "weight_pct": df.weight_pct,
                        "market_value": df.market_value, "net_assets": float(na.median())})
    s = out.weight_pct.sum()
    if not 95 <= s <= 101.5:
        raise ValueError(f"{p.name}: YieldShares weights sum to {s:.2f}%")
    return out


def parse_yyy_html(p: Path) -> pd.DataFrame:
    raw = p.read_text(encoding="utf-8", errors="replace")
    tables = pd.read_html(io.StringIO(raw))
    best = None
    for tb in tables:
        cols = [str(c).lower() for c in tb.columns]
        if any("weight" in c for c in cols) and any("ticker" in c or "symbol" in c for c in cols):
            best = tb
            break
    if best is None:
        raise ValueError(f"{p.name}: no holdings table with ticker and weight columns")
    cols = {c: str(c).lower() for c in best.columns}
    tick = [c for c, l in cols.items() if "ticker" in l or "symbol" in l][0]
    wcol = [c for c, l in cols.items() if "weight" in l][0]
    mcol = [c for c, l in cols.items() if "market value" in l or l == "market value"]
    t = _text(raw)
    m = re.search(r"(?:as of|As of|AS OF)\s*:?\|?\s*(\d{1,2}/\d{1,2}/\d{4})", t)
    if not m:
        raise ValueError(f"{p.name}: no as-of date")
    asof = pd.Timestamp(m.group(1))
    na = re.search(r"Net Assets\|?\s*\$?([\d,\.]+)\s*(M|B|million|billion)?", t)
    net_assets = float("nan")
    if na:
        v = float(na.group(1).replace(",", ""))
        unit = (na.group(2) or "").lower()
        net_assets = v * (1e6 if unit.startswith("m") else 1e9 if unit.startswith("b") else 1.0)
    df = pd.DataFrame({
        "etf": "YYY", "asof": asof, "ticker": best[tick].astype(str).str.strip(),
        "name": best[tick].astype(str),
        "weight_pct": best[wcol].astype(str).str.rstrip("%").str.replace(",", "").astype(float),
        "market_value": (best[mcol[0]].astype(str).str.replace(r"[$,]", "", regex=True).astype(float)
                         if mcol else float("nan")),
        "net_assets": net_assets})
    s = df.weight_pct.sum()
    if not 95 <= s <= 101.5:
        raise ValueError(f"{p.name}: YYY html weights sum to {s:.2f}%")
    return df


def parse_xmpt(p: Path) -> pd.DataFrame:
    """VanEck XMPT holdings page (2019-2021 captures). Two layouts:
    2019: `Name |TICK US |shares |mv |w`; 2020+: `TICK US |Name |FIGI |shares |Stock |mv |w`.
    Daily holdings carry their own 'as of' date; Total Net Assets is printed as $xxx.xM."""
    t = _text(p.read_text(encoding="utf-8", errors="replace"))
    m = re.search(r"Daily Holdings \(%\) \|as of (\d{2}/\d{2}/\d{2})", t)
    if not m:
        raise ValueError(f"{p.name}: no 'Daily Holdings as of' date")
    asof = pd.to_datetime(m.group(1), format="%m/%d/%y")
    na = re.search(r"Total Net Assets\|\$([\d\.]+)M", t)
    if not na:
        raise ValueError(f"{p.name}: no Total Net Assets")
    net_assets = float(na.group(1)) * 1e6
    body = t[m.end():]
    r20 = re.findall(r"\|([A-Z]{1,5}) US \|([^|]{3,60})\|BBG[0-9A-Z]{9} \|([\d,]+) \|Stock \|([\d,]+) \|([\d\.]+) ", body)
    r19 = re.findall(r"\|([^|]{3,60})\|([A-Z]{1,5}) US \|([\d,]+) \|([\d,]+) \|([\d\.]+) ", body)
    if len(r20) >= 20:
        df = pd.DataFrame(r20, columns=["ticker", "name", "shares", "mv", "w"])
    elif len(r19) >= 20:
        df = pd.DataFrame(r19, columns=["name", "ticker", "shares", "mv", "w"])
    else:
        raise ValueError(f"{p.name}: XMPT rows did not parse ({len(r20)}/{len(r19)})")
    out = pd.DataFrame({"etf": "XMPT", "asof": asof, "ticker": df.ticker, "name": df.name.str.strip(),
                        "weight_pct": df.w.astype(float),
                        "market_value": df.mv.str.replace(",", "").astype(float),
                        "net_assets": net_assets}).drop_duplicates("ticker")
    s = out.weight_pct.sum()
    if not 95 <= s <= 101.5:
        raise ValueError(f"{p.name}: XMPT weights sum to {s:.2f}%")
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    frames = []
    for p in sorted(SNAPS.glob("pcef_ps_*.bin")):
        d = parse_pcef_ps(p)
        if d is not None:
            frames.append(d.assign(source_file=p.name))
    for p in sorted(SNAPS.glob("amp_holdings_*.csv")):
        frames.append(parse_amp_csv(p).assign(source_file=p.name))
    for p in sorted(SNAPS.glob("ys_hold_2*.bin")):  # the www twin captures are byte-identical
        d = parse_yieldshares(p)
        if d is not None:
            frames.append(d.assign(source_file=p.name))
    # xmpt_mv_* (Market Vectors era, 2011-2016) pages print only the TOP 10 holdings at
    # month end, so adds and drops cannot be read from them; they are not parsed.
    for p in sorted(SNAPS.glob("xmpt_h*.bin")):
        frames.append(parse_xmpt(p).assign(source_file=p.name))
    df = pd.concat(frames, ignore_index=True)
    # one snapshot per (etf, asof): keep the first file for duplicate captures of one as-of date
    first = df.groupby(["etf", "asof"]).source_file.transform("min")
    df = df[df.source_file == first]
    df.to_csv(OUT / "holdings_snapshots.csv", index=False)
    summ = df.groupby(["etf", "asof"]).agg(n=("ticker", "size"), wsum=("weight_pct", "sum"),
                                           net_assets=("net_assets", "first"), src=("source_file", "first"))
    print(summ.to_string())


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main()
