"""Late-NAV measurement, 2026-11-24 (team lead: "Measure it first"). Read-only on local copies of the VM's records.
For each decided plan: which funds' NAV for the as-of date equalled the previous NAV row AT THE DECIDE (core: nav_gate
checks triggered `yf_repeat`; C4: targets whose reason names the NAV-repeat mask, or a `z=+nan` discount reason on a held
name, which is how the band writes a masked held name it trims), and whether the VM's panel as read tonight now holds a
DIFFERENT NAV for that as-of date (= the NAV arrived after the decide: "late"), or the same one ("repeat stands").
Money: the dollars filled on those names that session (send.json `final`), against the session's total filled dollars."""
import json, glob, os
import pandas as pd
pd.set_option("compute.use_numexpr", False)
import sys
if len(sys.argv) != 2:
    raise SystemExit("usage: python3 -I measure.py ROOT   (ROOT holds vmdata/<cef,c4>/cef_nav.parquet and hist/<cef,c4>/<date>/{plan,send}.json, copied read-only from the VM)")
S = sys.argv[1]
def panel(b):
    n = pd.read_parquet(f"{S}/vmdata/{b}/cef_nav.parquet"); n["date"] = pd.to_datetime(n["date"])
    return n.pivot(index="date", columns="ticker", values="nav")
rows = []
for book, sub in (("cef", "cef"), ("c4", "c4")):
    nav = panel(sub)
    for pf in sorted(glob.glob(f"{S}/hist/{book}/20*/plan.json")):
        d = os.path.basename(os.path.dirname(pf))
        p = json.load(open(pf))
        if p.get("status") != "decided":
            rows.append(dict(book=book, session=d, status=p.get("status"))); continue
        asof = pd.Timestamp(p["asof"]); t = p.get("targets") or {}
        if book == "cef":
            ng = p.get("nav_gate") or {}
            rep = {c["ticker"]: c for c in ng.get("checks", []) if str(c.get("trigger") or "").endswith("repeat")}
            masked = set(rep)
            gate_present = bool(ng)
        else:
            masked = {k for k, v in t.items() if "nav_repeat" in str(v.get("reason")) or ("z=+nan" in str(v.get("reason")) and v.get("current"))}
            gate_present = True
        sp = os.path.join(os.path.dirname(pf), "send.json")
        fin = json.load(open(sp)).get("final", {}) if os.path.exists(sp) else {}
        filled = {k.split("-")[2]: int(v.get("filled") or 0) * float(v.get("filled_avg_price") or 0) for k, v in fin.items()}
        late, stands = [], []
        prev_dates = nav.index[nav.index < asof]
        for k in masked:
            if k not in nav or asof not in nav.index or not len(prev_dates):
                continue
            now, prev = nav.at[asof, k], nav.loc[prev_dates, k].dropna()
            if pd.isna(now) or prev.empty: continue
            (late if now != prev.iloc[-1] else stands).append(k)
        held_masked = [k for k in masked if (t.get(k) or {}).get("current")]
        rows.append(dict(book=book, session=d, asof=str(asof.date()), status="decided", gate=gate_present,
                         n_universe=len(t), masked=len(masked), late=len(late), stands=len(stands),
                         held_masked=len(held_masked),
                         usd_masked_traded=round(sum(filled.get(k, 0) for k in masked), 0),
                         usd_late_traded=round(sum(filled.get(k, 0) for k in late), 0),
                         usd_total_traded=round(sum(filled.values()), 0)))
        # No fund list is written: the repository keeps aggregates only (.claude/rules/report.md).
df = pd.DataFrame(rows)
df.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "by_session.csv"), index=False)
pd.set_option("display.width", 250)
print(df.to_string(index=False))
