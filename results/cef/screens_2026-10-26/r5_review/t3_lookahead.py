"""T3: lookahead through Compustat. (1) delay the knowledge date by +3/+10/+21 sessions;
(2) rdq vs the first 10-Q/10-K acceptance; (3) IC on name-days whose NAV-in-use matches a
point-in-time XBRL value already filed by t, vs the rest, 2020-22."""
import sys, json, pickle
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import rv
D = pickle.load(open(HERE / "_cache/panel.pkl", "rb")); P = D["P"]
zT, zC, F, M, G0, G1, idx, nav, dd = (D[k] for k in ["zT", "zC", "F", "M", "G0", "G1", "idx", "nav", "dd"])
sT, sC = -zT, -zC
out = {}
for k in (3, 10, 21):
    nk, _, _ = P.nav_daily("rdq", shift_sessions=k)
    zk = rv.zs(P.disc(nk)); MM = zk.notna() & zC.notna()
    out[f"known_rdq_plus_{k}_sessions"] = {ph: {"treat": rv.eras(rv.ic(-zk, F, MM, G)), "partial": rv.eras(rv.pic(-zk, sC, F, MM, G))}
                                            for ph, G in (("ph0", G0), ("ph1", G1))}
    print(k, out[f"known_rdq_plus_{k}_sessions"])
# (2) rdq vs first 10-Q/10-K acceptance (ET calendar date)
r = pd.read_parquet(rv.FIL / "d2_bdc_reports.parquet")
r["reportDate"] = pd.to_datetime(r.reportDate)
r["acc"] = pd.to_datetime(r.acceptanceDateTime, utc=True).dt.tz_convert("America/New_York")
r = r[r.form.isin(["10-Q", "10-K"])].sort_values("acc").drop_duplicates(["cik", "reportDate"])
f = P.fn.merge(r[["cik", "reportDate", "acc"]], left_on=["cik_e", "datadate"], right_on=["cik", "reportDate"], how="left")
accd = f.acc.dt.tz_localize(None).dt.normalize()
lag = (accd - f.rdq).dt.days
out["rdq_vs_first_10Q10K"] = {"matched": int(lag.notna().sum()), "unmatched": int(lag.isna().sum()),
    "rdq_after_filing_days_gt0": int((lag < 0).sum()), "rdq_after_filing_gt5d": int((lag < -5).sum()),
    "filing_after_rdq_gt5d": int((lag > 5).sum()), "filing_after_rdq_gt20d": int((lag > 20).sum()),
    "same_day": int((lag == 0).sum()), "q": [float(lag.quantile(q)) for q in (0.01, 0.1, 0.5, 0.9, 0.99)],
    "rdq_minus_datadate_days_min": int((f.rdq - f.datadate).dt.days.min())}
print(out["rdq_vs_first_10Q10K"])
# (3) XBRL point-in-time verified subset
x = pd.read_parquet(rv.FIL / "d2_bdc_navps_facts.parquet")
x["end"] = pd.to_datetime(x.end); x["filed"] = pd.to_datetime(x.filed)
x = x[x.filed <= rv.END].sort_values("filed").drop_duplicates(["cik", "end"])
m = P.fn.merge(x[["cik", "end", "val", "filed"]], left_on=["cik_e", "datadate"], right_on=["cik", "end"], how="inner")
m["ok"] = (m.nav / m.val - 1).abs() <= 0.01
out["xbrl_pit_pairs_in_panel"] = int(len(m)); out["xbrl_pit_match"] = int(m.ok.sum())
ver = pd.DataFrame(False, index=P.CAL, columns=nav.columns); bad = ver.copy()
for _, rr in m.iterrows():
    tk = f"P{rr.permno}"
    if tk not in ver.columns: continue
    hit = (dd[tk] == pd.Timestamp(rr.datadate).value) & (P.CAL >= rr.filed)
    if rr.ok: ver.loc[hit.values, tk] = True
    else: bad.loc[hit.values, tk] = True
ver, bad = ver.reindex(idx), bad.reindex(idx)
for lab, MM in (("verified", M & ver), ("not_verified", M & ~ver), ("all", M)):
    for ph, G in (("ph0", G0), ("ph1", G1)):
        s = rv.ic(sT, F, MM, G).loc["2020":"2022"]
        out[f"2020-22|{lab}|{ph}"] = rv.row(s)
out["verified_namedays_2020_22"] = int((M & ver).loc["2020":"2022"].sum().sum())
out["mismatch_namedays_2020_22"] = int((M & bad).loc["2020":"2022"].sum().sum())
print({k: v for k, v in out.items() if k.startswith("2020") or "verified" in k or "xbrl" in k or "mismatch" in k})
json.dump(out, open(HERE / "t3_lookahead.json", "w"), indent=1, default=str)
