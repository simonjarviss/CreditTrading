"""Map each leveraged or inverse ETF to its underlying and its leverage, by rule, from returns.

    python3 results/ideas/levered_etf_reversal/mapping.py      (after stage.py)

WHY BY REGRESSION AND NOT BY NAME: CRSP's name file carries the TRUST ("PROSHARES TRUST",
"DIREXION SHARES ETF TRUST"), not the fund's name, so "2X"/"Bull"/"Bear" cannot be read
there, and Yahoo drops dead funds. A daily leveraged fund is defined by what it does: its
daily return is b times its underlying's. So for every CRSP ETF (dead ones included):
  1. correlate its daily return with every CANDIDATE underlying over the days both traded
     (60 or more), keep the candidate with the highest correlation, require R2 >= 0.90;
  2. estimate the slope b by calendar year (40 or more days, else the fund's whole-life
     slope) and round it to the nearest of -3, -2, -1.5, -1, 1.25, 1.5, 2, 3; keep the
     fund-year only if the slope is within 12% of that multiple. A slope near +1 is a twin
     or the candidate itself and is dropped; covered-call funds (slope 0.5-0.9) are dropped.
CANDIDATES. Single stocks: every common stock ever in the largest 1,000 since 2015 (the
staged CRSP panel), returns from 2022-01-01. Index and sector: the fixed list INDEX_UNDERLYINGS
of plain equity ETFs below, written before any regression was run.
THIS READS NO FORWARD RETURN: it is a same-day fit of fund on underlying. The leverage is a
prospectus fact; estimating it inside the year it applies to uses nothing the market did
not know. Output (licensed rows, outside the repository): pairs.parquet, one row per fund-year.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore  # noqa: E402,F401  (turns numexpr off)

assert pd.get_option("compute.use_numexpr") is False
RES = Path.home() / "quantt_research"
OUT = RES / "levered_etf_reversal"
MULTIPLES = np.array([-3.0, -2.0, -1.5, -1.0, 1.25, 1.5, 2.0, 3.0])
TOL, MIN_R2, MIN_DAYS, MIN_YEAR_DAYS = 0.12, 0.90, 60, 40
# Plain equity ETFs a book here can trade. BROAD large-cap ones are listed so that funds on
# them are mapped and can be shown, but explore.py leaves them out of the book (BROAD there).
INDEX_UNDERLYINGS = ("SPY QQQ DIA IWM MDY IJR KRE KBE XBI IBB SOXX SMH GDX GDXJ XLF XLE XLK XLV XLI XLU XLB XLP XLY "
                     "XLRE XLC XOP OIH XHB ITB XRT IYR VNQ EEM EFA FXI EWZ EWJ EWY EWW EWT INDA MCHI ASHR KWEB XME "
                     "IYT ITA XAR TAN ARKK FDN IGV HACK CIBR JETS IHI SIL URA").split()


def best_fit(Y: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    """For each column of Y (funds), the column of X (candidates) with the highest squared
    correlation over the days both have a return. Masked cross-products, no filling."""
    my, mx = Y.notna().to_numpy(float), X.notna().to_numpy(float)
    y, x = Y.fillna(0.0).to_numpy(float), X.fillna(0.0).to_numpy(float)
    n = my.T @ mx
    sy, sx = y.T @ mx, my.T @ x
    sxy, syy, sxx = y.T @ x, (y * y).T @ mx, my.T @ (x * x)
    with np.errstate(divide="ignore", invalid="ignore"):
        cov = sxy - sx * sy / n
        vy, vx = syy - sy * sy / n, sxx - sx * sx / n
        r2 = np.where((n >= MIN_DAYS) & (vy > 0) & (vx > 0), cov * cov / (vy * vx), -1.0)
        j = r2.argmax(axis=1)
        i = np.arange(len(j))
        beta = cov[i, j] / vx[i, j]
    return pd.DataFrame({"fund": Y.columns, "under": X.columns[j], "r2": r2[i, j], "beta": beta, "n": n[i, j]})


def main() -> int:
    etf = pd.read_parquet(OUT / "etf_daily.parquet", columns=["permno", "ticker", "date", "ret"])
    etf["date"] = pd.to_datetime(etf["date"])
    last_tic = etf.dropna(subset=["ticker"]).groupby("permno")["ticker"].last()
    E = etf.pivot(index="date", columns="permno", values="ret")
    # index candidates: the permno that carries the ticker on the panel's last day
    last = etf[etf["date"] == etf["date"].max()].set_index("ticker")["permno"]
    missing = [t for t in INDEX_UNDERLYINGS if t not in last.index]
    print("index candidates not trading under that ticker on the last CRSP day (left out):", missing)
    idx_ids = [int(last[t]) for t in INDEX_UNDERLYINGS if t in last.index]
    stk = pd.read_parquet(RES / "crsp_top4500_daily.parquet", columns=["permno", "date", "ret", "cap_rank"])
    stk["date"] = pd.to_datetime(stk["date"])
    stk = stk[stk["date"] >= "2022-01-01"]
    keep = stk.loc[stk["cap_rank"] <= 1000, "permno"].unique()
    S = stk[stk["permno"].isin(keep)].pivot(index="date", columns="permno", values="ret").reindex(E.index)
    funds = E.drop(columns=idx_ids)
    fi = best_fit(funds, E[idx_ids]).assign(kind="index")
    fs = best_fit(funds.loc["2022-01-01":], S.loc["2022-01-01":]).assign(kind="single")
    both = pd.concat([fi, fs]).sort_values("r2", ascending=False).drop_duplicates("fund")
    both = both[both["r2"] >= MIN_R2]
    X = pd.concat([E[idx_ids], S], axis=1)
    rows = []
    for f in both.itertuples():
        d = pd.concat([E[f.fund].rename("y"), X[f.under].rename("x")], axis=1).dropna()
        for yr, g in d.groupby(d.index.year):
            b = float(np.cov(g["y"], g["x"])[0, 1] / g["x"].var()) if len(g) >= MIN_YEAR_DAYS and g["x"].var() > 0 else float(f.beta)
            m = float(MULTIPLES[np.abs(MULTIPLES - b).argmin()])
            if abs(b - m) <= TOL * abs(m):
                rows.append({"fund": int(f.fund), "fund_ticker": last_tic.get(f.fund), "under": int(f.under), "kind": f.kind,
                             "year": int(yr), "slope": b, "lev": m, "r2_life": float(f.r2), "days": int(len(g))})
    pairs = pd.DataFrame(rows)
    pairs.to_parquet(OUT / "pairs.parquet", index=False)
    print("funds with a best fit of R2 >= 0.90:", len(both), "; kept fund-years:", len(pairs), "; funds:", pairs["fund"].nunique())
    print(pairs.groupby(["kind", "lev"])["fund"].nunique().unstack(fill_value=0))
    print(pairs.groupby(["kind", "year"]).agg(funds=("fund", "nunique"), underlyings=("under", "nunique")).unstack(0).fillna(0).astype(int))
    return 0


if __name__ == "__main__":
    sys.exit(main())
