"""Stage US merger and tender-offer deals from SDC, with each target's CRSP daily rows. Research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_sdc_deals.py

WHY SDC AND NOT THE DESK'S OWN EDGAR CENSUS. The October census
(scripts/events/merger_arb_feasibility.py) finds a one-step merger by its proxy statement,
which is filed weeks after the announcement. A deal that is announced and breaks before the
proxy is never in it, so any return measured from the announcement date is conditioned on
the deal surviving its first weeks. SDC records a deal when it is announced and keeps the
withdrawn ones, with the withdrawal date. That is what a return test needs. The census stays
useful as a cross-check from each deal's first proxy date on, and it is the only free, live
source.

THE DEAL LIST (`tr_sdc_ma.wrds_ma_details`), rules fixed before any return was read:
  target      nation United States, public status Public
  form        'Merger' (a bid for the whole company); buybacks, partial stakes, asset sales out
  status      Completed, Withdrawn or Pending. 'Intended', rumours and seeking-buyer rows are
              not announced deals. Status is the FINAL status and is kept for description
              only: no entry rule may read it. The dated fields a rule may use are
              `dateann` (public), `dateeff` (completion) and `datewith` (withdrawal), each
              public on its own date.
  cash        `pct_cash` = 100; or, where SDC left the percentages empty, the consideration
              text names cash per share and no shares (`CASH_TEXT`, `SHARES_TEXT`). The two
              are compared where both exist and the agreement is printed.
  tender      SDC's `tender` flag: 'Yes' is a tender offer, 'No' a one-step merger.
  link        the target's 6-digit CUSIP equals the first six of a CRSP historical CUSIP
              whose name range covers `dateann`, on a US common share (EQTY / COM / NS).
              No such row, or more than one permno: the deal is dropped and counted.
All consideration classes are staged; the tests choose.

THE TARGET ROWS (`crsp_a_stock.dsf_v2`): each linked permno from 90 days before `dateann` to
400 days after, to 2025-12-31. `dlyret` is CRSP's total return in the CIZ format, which
carries the delisting payment on the security's last row; the test verifies that against
the legacy file's separate delisting return before relying on it.

WHERE IT WRITES: `~/quantt_research/sdc_ma_deals.parquet` and
`~/quantt_research/crsp_ma_targets_daily.parquet`. SDC and CRSP rows are licensed: never in
the repository, never under `data/`. Read-only at R2. Prints counts only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

CASH_TEXT = r"cash\s*/\s*(sh|com)"
SHARES_TEXT = r"shs\s|sh\s+(com|ord|cl)\s*/|stock|common shares|ADR|exchange ratio"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2000-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--out", type=Path, default=Path.home() / "quantt_research")
    a = ap.parse_args(argv)
    out = a.out.expanduser().resolve()
    if REPO.resolve() == out or REPO.resolve() in out.parents:
        raise SystemExit(f"refusing {out}: licensed rows stay outside the repository")
    out.mkdir(parents=True, exist_ok=True)
    from src.data import r2
    con = r2.connect()
    ma, names, dsf = (r2.r2_path("tr_sdc_ma", "wrds_ma_details"), r2.r2_path("crsp_a_stock", "stocknames_v2"),
                      r2.r2_path("crsp_a_stock", "dsf_v2"))
    con.execute(f"""
        create temp table d as
          select master_deal_no as deal, dateann, dateannorig, dateeff, datewith, status, tender,
                 pct_cash, pct_stk, pct_other, pct_unknown, attitude, attitude_change_yn, master_cusip as cusip6, tticker,
                 deal_value, pr as offer_price, consid,
                 regexp_matches(coalesce(consid, ''), '{CASH_TEXT}', 'i') as text_cash,
                 regexp_matches(coalesce(consid, ''), '{SHARES_TEXT}', 'i') as text_shares
          from read_parquet('{ma}')
          where tnation = 'United States' and tpublic = 'Public' and form = 'Merger'
            and status in ('Completed', 'Withdrawn', 'Pending')
            and dateann between cast(? as date) and cast(? as date)""", [a.start, a.end])
    other = con.execute(f"""select status, count(*) from read_parquet('{ma}')
                            where tnation = 'United States' and tpublic = 'Public' and form = 'Merger'
                              and status not in ('Completed', 'Withdrawn', 'Pending')
                              and dateann between cast(? as date) and cast(? as date) group by 1 order by 2 desc""",
                        [a.start, a.end]).fetchall()
    n_deals = con.execute("select count(*), count(distinct deal) from d").fetchone()
    if n_deals[0] != n_deals[1]:
        raise RuntimeError(f"SDC deal numbers repeat: {n_deals}")
    agree = con.execute("""select sum(case when (pct_cash = 100) = (text_cash and not text_shares) then 1 else 0 end), count(*)
                           from d where pct_cash is not null and consid is not null""").fetchone()
    con.execute("""alter table d add column cash_class varchar""")
    con.execute("""update d set cash_class = case
                     when pct_cash = 100 then 'cash'
                     when pct_cash is not null then 'not_cash'
                     when text_cash and not text_shares then 'cash_by_text'
                     when consid is null then 'unknown' else 'not_cash' end""")
    con.execute(f"""
        create temp table l as
          select d.deal, s.permno
          from d join read_parquet('{names}') s
            on substr(s.cusip, 1, 6) = d.cusip6 and d.dateann between s.namedt and s.nameenddt
          where s.securitytype = 'EQTY' and s.securitysubtype = 'COM' and s.sharetype = 'NS' and s.usincflg = 'Y'
          group by 1, 2""")
    con.execute("create temp table one as select deal, min(permno) as permno from l group by 1 having count(*) = 1")
    n_multi = con.execute("select count(*) from (select deal from l group by 1 having count(*) > 1)").fetchone()[0]
    deals = out / "sdc_ma_deals.parquet"
    con.execute(f"""copy (select d.*, one.permno from d join one using (deal) order by dateann, deal)
                    to '{deals}' (format parquet, compression zstd)""")
    rows = out / "crsp_ma_targets_daily.parquet"
    con.execute(f"""
        copy (
          with w as (select permno, min(dateann) - interval 90 day as lo, max(dateann) + interval 400 day as hi
                     from read_parquet('{deals}') group by 1)
          select x.permno, x.dlycaldt as date, cast(x.dlyret as double) as ret, cast(x.dlyprc as double) as prc,
                 cast(x.dlycap as double) as cap, cast(x.dlyprcvol as double) as dollar_volume,
                 x.dlydelflg as delflg
          from read_parquet('{dsf}') x join w on x.permno = w.permno and x.dlycaldt between w.lo and w.hi
          where x.dlycaldt <= cast(? as date)
          order by date, permno
        ) to '{rows}' (format parquet, compression zstd)""", [a.end])
    c = con.execute(f"""select tender, cash_class, status, count(*) from read_parquet('{deals}') group by 1, 2, 3 order by 1, 2, 3""").fetchall()
    r = con.execute(f"select count(*), min(date), max(date), count(distinct permno) from read_parquet('{rows}')").fetchone()
    print(f"SDC deals {a.start}..{a.end}: {n_deals[0]:,}; linked to one CRSP common share: "
          f"{con.execute(f'select count(*) from read_parquet(chr(39) || ? || chr(39))', [str(deals)]).fetchone()[0] if False else sum(x[3] for x in c):,}; "
          f"more than one permno (dropped): {n_multi:,}")
    print(f"cash by percentages agrees with cash by text on {agree[0]:,} of {agree[1]:,} deals that have both")
    n_linked = sum(x[3] for x in c)
    print(f"no CRSP common share on the announcement date (dropped): {n_deals[0] - n_linked - n_multi:,}")
    print("left out by SDC's final status (this IS a selection on a field set after the fact): "
          + (", ".join(f"{k} {v:,}" for k, v in other) or "none"))
    for tender, cls, status, n in c:
        print(f"  tender={tender:<3} {cls:<13} {status:<10} {n:>5,}")
    print(f"{rows.name}: {r[0]:,} rows, {r[1]} .. {r[2]}, {r[3]:,} permnos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
