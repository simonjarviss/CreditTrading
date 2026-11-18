"""Stage the rights-offering events of CRSP closed-end funds, and the quotes of those funds.

    QUANTT_ENV_FILE=<env file> python3 results/ideas/cef_rights_offerings/stage.py

WHY A SEPARATE STEP: the event list and the closing bid and ask are licensed CRSP rows, so
they are written under ~/quantt_research/cef_rights_offerings/ and never into the repository.
`explore.py` then runs with no network.

WHAT IS A RIGHTS OFFERING HERE. CRSP's CIZ distribution table types a distribution of
subscription rights in the fund's own shares as distype 'SP', disdetailtype 'SECRD',
dispaymenttype 'SS' (the legacy code 45xx that results/events/CEF_CORP_ACTION_CENSUS_2026-10-15.md
counted). `disexdt` is the first session the shares trade without the right; `disdivamt` is
CRSP's value of the right per share, which is what `dlyret` adds back on that day, so the
ex-rights price drop is not a return. A row with no `disdivamt` has no value added back:
the right did not trade (non-transferable, or unpriced). The universe is the staged CEF
panel's permnos (`securitysubtype = 'CEF'`, scripts/research/stage_crsp_cefs.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = Path.home() / "quantt_research" / "cef_rights_offerings"
PANEL = Path.home() / "quantt_research" / "crsp_cef_daily.parquet"


def main() -> int:
    from src.data import r2
    OUT.mkdir(parents=True, exist_ok=True)
    con = r2.connect()
    cef = pd.read_parquet(PANEL, columns=["permno"]).drop_duplicates()
    con.register("cef", cef)
    ev = con.execute(f"""
        select permno, disexdt as ex_date, disdeclaredt as declared, disrecorddt as record_date,
               dispaydt as pay_date, cast(disdivamt as double) as right_value,
               cast(disfacpr as double) as facpr, dispaymenttype, dispermno
        from read_parquet('{r2.r2_path("crsp_a_stock", "stkdistributions")}')
        where permno in (select permno from cef) and disexdt >= date '2000-01-01'
          and disdetailtype = 'SECRD' order by disexdt, permno""").df()
    nm = con.execute(f"""select permno, issuernm, ticker, cusip, namedt, nameenddt
        from read_parquet('{r2.r2_path("crsp_a_stock", "stocknames_v2")}')
        where permno in (select distinct permno from ev)""").df()
    ev["ex_date"] = pd.to_datetime(ev["ex_date"])
    for c in ("namedt", "nameenddt"):
        nm[c] = pd.to_datetime(nm[c])
    m = ev.merge(nm, on="permno")
    m = m[(m["namedt"] <= m["ex_date"]) & (m["ex_date"] <= m["nameenddt"])]
    ev = ev.merge(m[["permno", "ex_date", "issuernm", "ticker", "cusip"]].drop_duplicates(["permno", "ex_date"]),
                  on=["permno", "ex_date"], how="left")
    ev.to_parquet(OUT / "events.parquet", index=False)
    con.execute(f"""copy (
        select permno, dlycaldt as date, cast(dlybid as double) as bid, cast(dlyask as double) as ask,
               cast(dlyvol as double) as vol, cast(shrout as double) as shrout
        from read_parquet('{r2.r2_path("crsp_a_stock", "dsf_v2")}')
        where dlycaldt >= date '2000-01-01' and permno in (select distinct permno from ev)
          and conditionaltype = 'RW' and tradingstatusflg = 'A' order by date, permno
        ) to '{OUT / "quotes.parquet"}' (format parquet, compression zstd)""")
    print(f"{len(ev)} SECRD rows on {ev['permno'].nunique()} funds, {ev['ex_date'].min().date()} .. {ev['ex_date'].max().date()}")
    print("with a right value:", int(ev["right_value"].notna().sum()), "| with a declaration date:", int(ev["declared"].notna().sum()))
    print(ev.groupby(ev["ex_date"].dt.year).size().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
