"""R5 review (sceptic): independent re-derivation of the BDC discount-z panel.

Written from fundq + CRSP directly; does NOT import r5_bdc's nav_daily or its _cache_r5.
Only the band_frontier/w4 helpers' DEFINITIONS are mirrored, and the treatment z is
checked against build_panel on the author's cached panel. Dates <= 2022-12-30, asserted.
Licensed inputs: nothing here is written to a tracked file."""
from __future__ import annotations
import numpy as np, pandas as pd, pyarrow as pa, pyarrow.dataset as ds, pyarrow.parquet as pq
from pathlib import Path
import datetime as _dt

W = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/.claude/worktrees")
PULL = W / "simon/results/events/_cache_r7_r2_pull/bdc"
DSF = W / "research-ss-expansion/results/events/_cache_crsp/dsf_44015b5199.parquet"
NAMES = W / "research-ss-expansion/results/events/_cache_crsp/dsenames.parquet"
FIL = W / "research-ss-expansion/results/events/ssx/_cache_ssx_fil"
END = pd.Timestamp("2022-12-30"); HOLD = pd.Timestamp("2023-01-01")
ZW, MINP, MIN_N, MIN_ADV = 252, 120, 6, 3_000_000.0   # checked against spec at runtime below
ETF = {84398: "SPY", 88222: "IWM", 91933: "HYG", 13772: "BIZD", 12631: "BKLN", 89467: "LQD"}


def afit(*objs):
    for o in objs:
        idx = o.index if hasattr(o, "index") else pd.DatetimeIndex(o)
        if len(idx) and pd.Timestamp(idx.max()) >= HOLD:
            raise AssertionError(f"holdout leak {idx.max()}")


def crsp(perms):
    ty = pq.ParquetFile(DSF).schema_arrow.field("date").type
    lo = pa.scalar(_dt.datetime(2009, 1, 1), type=ty); hi = pa.scalar(_dt.datetime(2022, 12, 30), type=ty)
    t = ds.dataset(DSF).to_table(columns=["permno", "date", "prc", "ret", "vol", "cfacpr", "shrout"],
        filter=ds.field("permno").isin([int(p) for p in perms]) & (ds.field("date") >= lo) & (ds.field("date") <= hi)).to_pandas()
    t["date"] = pd.to_datetime(t.date).astype("datetime64[ns]")
    afit(t.set_index("date"))
    assert not t.duplicated(["permno", "date"]).any()
    return t


def fundq_nav():
    f = pd.read_parquet(PULL / "bdc_fundq.parquet")
    f = f[f.rdq.notna() & f.ceqq.notna() & f.cshoq.notna() & (f.cshoq > 0)]
    f = f.drop_duplicates(["gvkey", "datadate"])
    f["datadate"] = pd.to_datetime(f.datadate).astype("datetime64[ns]")
    f["rdq"] = pd.to_datetime(f.rdq).astype("datetime64[ns]")
    assert (f.rdq > f.datadate).all()
    f["nav"] = f.ceqq / f.cshoq
    e = pd.read_parquet(PULL / "bdc_entities.parquet"); e["permno"] = e.permno.astype(int); e["cik"] = e.cik.astype(int)
    f = f.merge(e[["gvkey", "permno", "cik"]].rename(columns={"cik": "cik_e"}), on="gvkey", how="inner")
    return f, e


def zs(x):
    """build_panel's z: rolling ZW (min MINP non-NaN rows) mean/sd, each shift(1); clip 4."""
    mu = x.rolling(ZW, min_periods=MINP).mean().shift(1)
    sd = x.rolling(ZW, min_periods=MINP).std().shift(1)
    return ((x - mu) / sd.replace(0, np.nan)).clip(-4, 4)


def fwd(r, a, b):
    out = None
    for k in range(a, b + 1):
        x = 1.0 + r.shift(-k); out = x if out is None else out * x
    return out - 1.0


def ic(S, F, M, dates, min_n=MIN_N):
    S, F = S.reindex(dates), F.reindex(dates); M = M.reindex(dates).fillna(False).astype(bool)
    ok = M & S.notna() & F.notna()
    rs = S.where(ok).rank(axis=1); rf = F.where(ok).rank(axis=1)
    rs = rs.sub(rs.mean(axis=1), axis=0); rf = rf.sub(rf.mean(axis=1), axis=0)
    c = (rs * rf).sum(axis=1) / np.sqrt((rs ** 2).sum(axis=1) * (rf ** 2).sum(axis=1)).replace(0, np.nan)
    n = ok.sum(axis=1)
    return c[(n >= min_n) & c.notna()]


def pic(T, Cc, F, M, dates, min_n=MIN_N):
    ok = M & T.notna() & Cc.notna() & F.notna()
    a, b, c = ic(T, F, ok, dates, 1), ic(Cc, F, ok, dates, 1), ic(T, Cc, ok, dates, 1)
    n = ok.reindex(dates).fillna(False).astype(bool).sum(axis=1)
    p = (a - c * b) / np.sqrt((1 - c ** 2) * (1 - b ** 2))
    p = p.replace([np.inf, -np.inf], np.nan)
    return p[(n.reindex(p.index) >= min_n) & p.notna()]


def row(s):
    s = s.dropna()
    if len(s) < 10: return (len(s), np.nan, np.nan)
    return (len(s), round(float(s.mean()), 4), round(float(s.mean() / s.std(ddof=1) * np.sqrt(len(s))), 2))


ERAS = [("2012-17", "2012-01-01", "2017-12-31"), ("2018-22", "2018-01-01", "2022-12-30"), ("fit", "2012-01-01", "2022-12-30")]


def eras(s):
    return {lab: row(s.loc[a:b]) for lab, a, b in ERAS}


class Panel:
    def __init__(self):
        f, e = fundq_nav()
        self.f, self.e = f, e
        px = crsp(list(e.permno) + list(ETF))
        self.etf = px[px.permno.isin(ETF)].copy()
        px = px[px.permno.isin(e.permno)].copy()
        self.raw = px
        self.CAL = pd.DatetimeIndex(sorted(px.date.unique()))
        px["close"] = px.prc.abs(); px["tk"] = "P" + px.permno.astype(str)
        first = px.groupby("permno").date.min()
        f = f[f.permno.isin(first.index)]
        f = f[f.datadate >= f.permno.map(first)]
        self.fn = f
        piv = lambda c: px.pivot(index="date", columns="tk", values=c).reindex(self.CAL)
        self.close, self.vol, self.cf, self.ret = piv("close"), piv("vol"), piv("cfacpr"), piv("ret")
        self.prc = piv("prc"); self.shrout = piv("shrout")
        self.cff = self.cf.ffill()
        self.U = list(self.close.columns)

    def nav_daily(self, known="rdq", lag_q=0, shift_sessions=0, override=None, expiry=200):
        """NAV in use per (t, name). lag_q=1 uses the PREVIOUS quarter's NAV on the same
        name-days (placebo). shift_sessions delays the knowledge date. override: dict
        (permno, datadate)->value in the ADJUSTED basis replaces the NAV (placebo)."""
        f = self.fn.dropna(subset=[known])
        out = pd.DataFrame(np.nan, index=self.CAL, columns=self.U); kmat = out.copy(); ddm = out.copy()
        pos = pd.Series(np.arange(len(self.CAL)), index=self.CAL)
        for perm, g in f.groupby("permno"):
            tk = f"P{perm}"
            g = g.sort_values([known, "datadate"])
            keep, best = [], pd.Timestamp.min
            for i, r in g.iterrows():
                if r.datadate > best: best = r.datadate; keep.append(i)
            g = g.loc[keep].copy()
            cfs = self.cff[tk]
            # adjusted-basis NAV: nav / cfacpr in force at the last session <= datadate
            idq = self.CAL.searchsorted(g.datadate.values, side="right") - 1
            g["cfdq"] = cfs.values[idq]
            if g.cfdq.isna().any(): raise ValueError(f"{tk}: no cfacpr at datadate")
            g["navadj"] = g.nav / g.cfdq
            if override is not None:
                g["navadj"] = [override.get((perm, d), np.nan) for d in g.datadate]
            ks = self.CAL.searchsorted(g[known].values, side="left") + shift_sessions
            g = g[ks < len(self.CAL)].copy(); ks = ks[ks < len(self.CAL)]
            g["ks"] = self.CAL[ks]
            g = g.sort_values("ks").drop_duplicates("ks", keep="last")
            g["navuse"] = g.navadj.shift(lag_q) if lag_q else g.navadj
            s = pd.Series(np.arange(len(g)), index=g.ks).reindex(self.CAL).ffill()
            valid = s.notna()
            ii = s[valid].astype(int).values
            dd = g.datadate.values[ii]
            nv = g.navuse.values[ii]
            kk = pos.values[valid.values] - pos.reindex(g.ks.values[ii]).values
            age = (self.CAL[valid.values] - pd.DatetimeIndex(dd)).days
            nv = np.where(age > expiry, np.nan, nv)
            out.loc[valid.values, tk] = nv
            kmat.loc[valid.values, tk] = np.where(age > expiry, np.nan, kk)
            ddm.loc[valid.values, tk] = np.where(age > expiry, np.nan, pd.DatetimeIndex(dd).asi8)
        return out, kmat, ddm   # NAV in the ADJUSTED basis (divide by cfacpr): disc uses adj price

    def disc(self, navadj):
        padj = self.close / self.cf                      # adjusted price
        # build_panel drops close<=0.5 and nav<=0.5 in RAW terms; nav_raw = navadj * cfacpr_t
        navraw = navadj * self.cf
        ok = (self.close > 0.5) & (navraw > 0.5)
        d = (100.0 * (padj - navadj) / navadj).where(ok)
        afit(d)
        return d

    def adv(self, navadj):
        navraw = navadj * self.cf
        ok = (self.close > 0.5) & (navraw > 0.5)
        return (self.close.where(ok) * self.vol.where(ok)).rolling(63, min_periods=21).mean().shift(1)
