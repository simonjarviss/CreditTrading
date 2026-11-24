"""T4 survivorship; T5 risk premium (regress the rank-weighted L/S on BDC EW, BIZD, HYG,
IWM, SPY, and on within-BDC value/size/momentum/short-term-reversal L/S); T6 concentration
(by year, ex-COVID, leave-one-name-out)."""
import sys, json, pickle
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import rv
D = pickle.load(open(HERE / "_cache/panel.pkl", "rb")); P = D["P"]
zT, zC, F, M, G0, G1, idx, nav, disc, adv, ret = (D[k] for k in ["zT", "zC", "F", "M", "G0", "G1", "idx", "nav", "disc", "adv", "ret"])
sT, sC = -zT, -zC
out = {}
# ---------------- T4 survivorship
nm = pd.read_parquet(rv.NAMES)
e = P.e
last_crsp = P.raw.groupby("permno").date.max()
nmE = nm[nm.permno.isin(e.permno)]
end_names = pd.to_datetime(nmE.groupby("permno").nameendt.max())
st_names = pd.to_datetime(nmE.groupby("permno").namedt.min())
missing = sorted(set(e.permno) - set(last_crsp.index))
out["surv"] = {
    "entities": int(len(e)), "with_crsp_rows": int(len(last_crsp)),
    "crsp_last_before_2022-12-30": int((last_crsp < rv.END).sum()),
    "crsp_last_before_2022-01-01": int((last_crsp < "2022-01-01").sum()),
    "dsenames_end_before_2022-12-30_all61": int((end_names.reindex(e.permno) < rv.END).sum()),
    "dsenames_known_all61": int(end_names.reindex(e.permno).notna().sum()),
    "cache_ends_vs_dsenames_end_days_max_dead": float(((end_names.reindex(last_crsp.index) - last_crsp).dt.days)[last_crsp < rv.END].abs().max()),
    "missing7_in_dsenames": int(pd.Index(missing).isin(nm.permno).sum()),
    "missing7_dsenames_end_before_2022": int((end_names.reindex(missing) < rv.END).sum()),
    "missing7_name_span_years": [round(float(((end_names.get(p, pd.NaT) - st_names.get(p, pd.NaT)).days) / 365.25), 1) if p in end_names.index else None for p in missing],
    "missing7_dsenames_start_years": [int(st_names[p].year) if p in st_names.index else None for p in missing],
}
lastz = zT.apply(lambda s: s.last_valid_index())
dead = last_crsp[last_crsp < rv.END]
gap = [(len(P.CAL[(P.CAL > lastz.get(f"P{p}")) & (P.CAL <= d)]) if pd.notna(lastz.get(f"P{p}")) else None) for p, d in dead.items()]
out["surv"]["dead_in_panel_sessions_from_last_z_to_last_crsp"] = sorted([g for g in gap if g is not None])
out["surv"]["dead_with_no_z"] = int(sum(g is None for g in gap))
# IC on names alive through 2022-12-30 only vs dead names (a survivor-only universe)
alive = [f"P{p}" for p in last_crsp[last_crsp >= rv.END].index]
Ma = M.copy(); Ma.loc[:, [c for c in M.columns if c not in alive]] = False
out["surv"]["ic_survivors_only_ph0"] = rv.eras(rv.ic(sT, F, Ma, G0))
out["surv"]["ic_survivors_only_ph0_ctrl"] = rv.eras(rv.ic(sC, F, Ma, G0))
print(out["surv"])

# ---------------- T5 risk premium
def lsw(S, MM):
    r = S.where(MM).rank(axis=1); r = r.sub(r.mean(axis=1), axis=0)
    return r.div(r.abs().sum(axis=1), axis=0) * 2.0           # $1 long / $1 short
def lsret(S, MM, G):
    w = lsw(S, MM & F.notna()).reindex(G); return (w * F.reindex(G)).sum(axis=1, min_count=1)
G = G0[G0 >= "2012-01-01"]
etf = P.etf.assign(tk=P.etf.permno.map(rv.ETF)).pivot(index="date", columns="tk", values="ret").reindex(P.CAL)
FE = rv.fwd(etf, 2, 3).reindex(G)
ew = F.where(M).reindex(G).mean(axis=1)
mcap = (P.close * P.shrout).reindex(idx)
past252 = (np.log1p(ret.fillna(0))).rolling(252, min_periods=200).sum().where(ret.notna())
past5 = (np.log1p(ret)).rolling(5).sum()
facs = {"VAL_disc_level": -disc.reindex(idx), "SIZE_small": -np.log(mcap), "MOM_252": past252.reindex(idx), "STR_5d": -past5.reindex(idx)}
LS = pd.DataFrame({"LS_treat": lsret(sT, M, G), "LS_ctrl": lsret(sC, M, G)})
for k, v in facs.items():
    LS[k] = lsret(v, M & v.notna(), G)
X0 = pd.concat([ew.rename("BDC_EW"), FE[["HYG", "IWM", "SPY", "BIZD", "BKLN"]]], axis=1)
def nw_ols(y, X, L=5):
    d = pd.concat([y, X], axis=1).dropna(); yv = d.iloc[:, 0].values; Xv = np.column_stack([np.ones(len(d)), d.iloc[:, 1:].values])
    b = np.linalg.lstsq(Xv, yv, rcond=None)[0]; u = yv - Xv @ b
    XtXi = np.linalg.inv(Xv.T @ Xv); S = (Xv * u[:, None]).T @ (Xv * u[:, None])
    for l in range(1, L + 1):
        w = 1 - l / (L + 1); G_ = (Xv[l:] * u[l:, None]).T @ (Xv[:-l] * u[:-l, None]); S += w * (G_ + G_.T)
    V = XtXi @ S @ XtXi; t = b / np.sqrt(np.diag(V))
    names = ["alpha"] + list(d.columns[1:])
    return {"n": int(len(d)), **{f"{n}": [round(float(bb if n != 'alpha' else bb * 1e4), 3), round(float(tt), 2)] for n, bb, tt in zip(names, b, t)},
            "r2": round(float(1 - u.var() / yv.var()), 3)}
specs = {"mkt": ["BDC_EW", "HYG", "IWM", "SPY"], "mkt_BIZD_2013+": ["BIZD", "HYG", "IWM"],
         "mkt+within_BDC_styles": ["BDC_EW", "HYG", "IWM", "VAL_disc_level", "SIZE_small", "MOM_252", "STR_5d"],
         "within_BDC_styles+ctrl": ["VAL_disc_level", "SIZE_small", "MOM_252", "STR_5d", "LS_ctrl"]}
XX = pd.concat([X0, LS.drop(columns=["LS_treat"])], axis=1)
out["rp"] = {}
for era, a, b in rv.ERAS:
    for sl, cols in specs.items():
        out["rp"][f"{era}|{sl}"] = nw_ols(LS.LS_treat.loc[a:b], XX[cols].loc[a:b])
out["rp"]["LS_treat_bp_per_2d_mean_t"] = {era: [round(float(LS.LS_treat.loc[a:b].mean() * 1e4), 2), round(float(LS.LS_treat.loc[a:b].mean() / LS.LS_treat.loc[a:b].std() * np.sqrt(LS.LS_treat.loc[a:b].count())), 2)] for era, a, b in rv.ERAS}
out["rp"]["LS_treat_gross_ann_ratio_DIAGNOSTIC_not_evaluate"] = {era: round(float(LS.LS_treat.loc[a:b].mean() / LS.LS_treat.loc[a:b].std() * np.sqrt(126)), 2) for era, a, b in rv.ERAS}
out["rp"]["corr_LS_treat_with"] = {c: round(float(LS.LS_treat.corr(XX[c])), 3) for c in XX.columns}
# partial ICs on within-BDC styles
out["partial_on_style"] = {}
for k, v in facs.items():
    out["partial_on_style"][k] = {"style_ic": rv.eras(rv.ic(v, F, M & v.notna(), G0)), "treat_partial": rv.eras(rv.pic(sT, v, F, M & v.notna(), G0)),
                                  "rank_corr_med": round(float(rv.ic(sT, v, M & v.notna(), G0).median()), 3)}
for k, v in out["rp"].items(): print(k, v)
for k, v in out["partial_on_style"].items(): print(k, v)

# ---------------- T6 concentration
icT = rv.ic(sT, F, M, G0); icC = rv.ic(sC, F, M, G0)
out["by_year"] = {int(y): [rv.row(icT[icT.index.year == y])[1:], rv.row(icC[icC.index.year == y])[1:]] for y in range(2012, 2023)}
covid = (icT.index >= "2020-02-20") & (icT.index <= "2020-06-30")
out["ex_covid_feb20_jun20"] = {"treat": rv.row(icT[~covid].loc["2012":"2022"]), "ctrl": rv.row(icC[~covid].loc["2012":"2022"]),
                               "partial": rv.row(rv.pic(sT, sC, F, M, G0)[lambda s: ~((s.index >= "2020-02-20") & (s.index <= "2020-06-30"))].loc["2012":"2022"])}
loo = {}
for c in M.columns:
    MM = M.copy(); MM[c] = False
    loo[c] = rv.row(rv.ic(sT, F, MM, G0).loc["2012":"2022"])
v = pd.DataFrame(loo, index=["n", "ic", "t"]).T
out["leave_one_out_fit_ph0"] = {"min_ic": float(v.ic.min()), "max_ic": float(v.ic.max()), "min_t": float(v.t.min()), "max_t": float(v.t.max())}
looD = {}
Mdep = M & (adv >= rv.MIN_ADV)
for c in M.columns:
    MM = Mdep.copy(); MM[c] = False
    looD[c] = rv.row(rv.ic(sT, F, MM, G0).loc["2012":"2017"])
vD = pd.DataFrame(looD, index=["n", "ic", "t"]).T
out["leave_one_out_deployed_2012_17"] = {"min_t": float(vD.t.min()), "max_t": float(vD.t.max())}
out["deployed_names_per_date_2012_17_median"] = float(Mdep.reindex(G0).loc["2012":"2017"].sum(axis=1).median())
out["deployed_names_per_date_2018_22_median"] = float(Mdep.reindex(G0).loc["2018":"2022"].sum(axis=1).median())
print({k: out[k] for k in ["by_year", "ex_covid_feb20_jun20", "leave_one_out_fit_ph0", "leave_one_out_deployed_2012_17", "deployed_names_per_date_2012_17_median", "deployed_names_per_date_2018_22_median"]})
json.dump(out, open(HERE / "t4_surv_rp.json", "w"), indent=1, default=str)
