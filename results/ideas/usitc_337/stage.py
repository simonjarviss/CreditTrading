"""Stage section 337 (unfair import, mostly patent) investigations at the US International Trade
Commission, matched to CRSP common stocks. Research only.

    QUANTT_ENV_FILE=<env> python3 results/ideas/usitc_337/stage.py

WHY: seen while counting antidumping petitioners for the niche hunt of 2026-11-15
(results/ideas/2026-11-15_niche_hunt.md). A company that believes imports infringe its patents
can ask the Commission to bar them. The case runs on a public, dated track: instituted,
an administrative law judge's initial determination (violation or not), a final
determination, and an exclusion order if the complainant wins. The complainant and every
respondent are named, with dates, in the Commission's public file. A small listed complainant
that wins has a legal monopoly on its product at the border; whether its share drifts after
the dated ruling has not been read on this desk.

SOURCE: https://ids.usitc.gov/investigations.json (public, no key; 37 MB). Fetched to
`~/quantt_research/usitc/investigations.json` if absent.

WHAT IT KEEPS: every investigation whose phase is 'Violation', and for each complainant and
respondent three dated events inside --start..--end: institution (`Start Date`), the initial
determination (`Initial Determination Date`, only when a determination TYPE is recorded: the
field also holds scheduled future dates), and the final determination.
THE MATCH: the participant's name against CRSP issuer names valid ON THE EVENT DATE
(stocknames_v2 name ranges), after dropping legal suffixes; exact match of the reduced name
only. A subsidiary filing under a different name is missed; a short common name could match
the wrong company, so the reduced name must be four characters or more. Market value is the
last CRSP value in the ten days up to the event.

WRITES `~/quantt_research/usitc/events_337.parquet` (one row per investigation, role, event
kind and security) and `crsp_337_daily.parquet` (daily rows of the matched securities).
CRSP rows are licensed: never in the repository. Prints counts only.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = Path.home() / "quantt_research" / "usitc"
URL = "https://ids.usitc.gov/investigations.json"
START, END = "2009-01-01", "2025-12-31"
SUFFIX = re.compile(r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LLC|LTD|LIMITED|LP|PLC|USA|US|THE|HOLDINGS|HOLDING|GROUP|"
                    r"INTERNATIONAL|INTL|TECHNOLOGIES|TECHNOLOGY)\b")


def reduce(name: str) -> str:
    s = re.sub(r"\(.*?\)", "", name.upper())
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return " ".join(SUFFIX.sub(" ", s).split())


def day(s):
    if not isinstance(s, str):
        return None
    try:
        return pd.Timestamp(dt.datetime.strptime(s, "%m-%d-%Y"))
    except ValueError:
        return None


def main() -> int:
    if REPO.resolve() in OUT.resolve().parents:
        raise SystemExit("refusing: licensed rows stay outside the repository")
    OUT.mkdir(parents=True, exist_ok=True)
    src = OUT / "investigations.json"
    if not src.exists():
        import requests
        r = requests.get(URL, timeout=300, headers={"User-Agent": "research-script/1.0"})
        r.raise_for_status()
        src.write_bytes(r.content)
    data = json.loads(src.read_text())["data"]
    from src.data import r2
    con = r2.connect()
    names = con.execute(f"""select permno, issuernm, namedt, nameenddt from read_parquet('{r2.r2_path('crsp_a_stock', 'stocknames_v2')}')
        where nameenddt >= cast(? as date) and securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'NS'""", [START]).fetchdf()
    names["namedt"], names["nameenddt"] = pd.to_datetime(names["namedt"]), pd.to_datetime(names["nameenddt"])
    by = collections.defaultdict(list)
    for r in names.itertuples(index=False):
        by[reduce(r.issuernm)].append(r)

    def match(name, d):
        k = reduce(name)
        if len(k) < 4:
            return None
        hits = {r.permno for r in by.get(k, []) if r.namedt <= d <= r.nameenddt}
        return hits.pop() if len(hits) == 1 else None      # two securities under one name: no match

    lo, hi = pd.Timestamp(START), pd.Timestamp(END)
    rows, n_inv = [], 0
    for x in data:
        if (x.get("Investigation Phase") or {}).get("Name") != "Violation":
            continue
        n_inv += 1
        events = (("institution", day(x.get("Start Date")), None),
                  ("initial", day(x.get("Initial Determination Date")), (x.get("Initial Determination Type") or {}).get("Name")),
                  ("final", day(x.get("Final Determination Date")), (x.get("Final Determination Type") or {}).get("finalDeterminationType")))
        for p in x.get("Participants") or []:
            role = p["Participant Type"]["name"]
            if role not in ("Complainant", "Respondent"):
                continue
            for kind, d, typ in events:
                if d is None or not lo <= d <= hi or (kind != "institution" and typ is None):
                    continue
                pn = match(p["Participant"]["Name"], d)
                if pn is not None:
                    rows.append({"inv": x["Investigation Number"], "role": role, "kind": kind, "date": d, "type": typ, "permno": int(pn)})
    ev = pd.DataFrame(rows).drop_duplicates(["inv", "role", "kind", "permno"])
    ids = ",".join(str(p) for p in sorted(ev["permno"].unique()))
    px = con.execute(f"""select permno, dlycaldt as date, cast(dlyret as double) as ret, cast(dlyprc as double) as prc,
            cast(dlyprcvol as double) as dollar_volume, cast(dlycap as double) as cap
        from read_parquet('{r2.r2_path('crsp_a_stock', 'dsf_v2')}')
        where permno in ({ids}) and dlycaldt between cast(? as date) - interval 60 day and cast(? as date)
        order by permno, date""", [START, END]).fetchdf()
    px["date"] = pd.to_datetime(px["date"]).astype("datetime64[ns]")
    ev["date"] = pd.to_datetime(ev["date"]).astype("datetime64[ns]")
    px["permno"] = px["permno"].astype("int64")
    ev["permno"] = ev["permno"].astype("int64")
    cap = px.dropna(subset=["cap"])[["permno", "date", "cap"]].sort_values("date")
    ev = pd.merge_asof(ev.sort_values("date"), cap, on="date", by="permno", direction="backward", tolerance=pd.Timedelta(days=10))
    ev.to_parquet(OUT / "events_337.parquet", index=False)
    px.to_parquet(OUT / "crsp_337_daily.parquet", index=False)
    ev["small"] = ev["cap"] < 5e6                      # CRSP cap is in $ thousands
    print(f"violation-phase investigations in the file: {n_inv:,}; matched event rows {len(ev):,} on {ev['permno'].nunique():,} securities; "
          f"daily rows {len(px):,} to {px['date'].max().date()}")
    print(ev.groupby(["role", "kind"]).agg(n=("permno", "size"), under_5bn=("small", "sum")).to_string())
    c = ev[(ev["role"] == "Complainant") & (ev["kind"] == "institution")]
    print("complainant institutions by year (all / under $5bn):",
          {int(y): (int(len(g)), int(g["small"].sum())) for y, g in c.groupby(c["date"].dt.year)})
    print(ev[ev["kind"] == "initial"].groupby(["role", "type"]).agg(n=("permno", "size"), under_5bn=("small", "sum")).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
