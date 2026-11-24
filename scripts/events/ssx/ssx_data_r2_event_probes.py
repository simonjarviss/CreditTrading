"""Targeted coverage probes of the R2 tables the event ideas would use. Read-only.

    QUANTT_ENV_FILE=/abs/path/config/.env python3 scripts/events/ssx/ssx_data_r2_event_probes.py

Writes `results/events/ssx/ssx_data/r2_event_probes_2026-10-19.json` and prints
each probe. Aggregates only: no licensed row-level data leaves the bucket or
enters the repository (the repository is public; WRDS content is licensed).

WHY THIS EXISTS
---------------
`ssx_data_r2_inventory.py` says which tables exist and the min/max of their
date columns from parquet statistics. A min/max does not say whether a table
covers OUR instruments (closed-end funds, BDCs, GSE preferreds, $25-par
issues) or whether its early years are populated or a handful of stray rows.
Each probe below answers one such question for one idea in the 2026-10-19 data
map, by counting rows per year (or per symbol) on a few columns. A count is a
measurement of the mirror as it stands today, not a claim about the vendor's
product.

How "closed-end fund" is defined here: a CUSIP-6 that CRSP's legacy
`stocknames` ever gave share code 14 or 44 (CRSP: closed-end funds; the 13
deployed names all carry one of these, `docs/DATA.md` §4). BDCs are mostly
share code 11 in CRSP and are NOT captured by this rule; probes that need BDCs
say so.

Each probe is independent; one that fails is recorded with its error and the
script exits 1 after running the rest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events" / "ssx" / "ssx_data" / "r2_event_probes_2026-10-19.json"

GSE_PREFIX_SQL = "(symbol LIKE 'FNMA%' OR symbol LIKE 'FNMF%' OR symbol LIKE 'FMCC%' OR symbol LIKE 'FMCK%')"
ETF_TICKERS = ("BIZD", "PFF", "PGX", "PFFD", "HYG", "JNK", "MUB")


def probes(P):
    """(name, why, sql) for each probe. P(schema, table) -> the parquet path."""
    cef6 = (f"(SELECT DISTINCT substr(ncusip,1,6) AS c6 FROM read_parquet('{P('crsp_a_stock','stocknames')}') "
            "WHERE shrcd IN (14,44) AND ncusip IS NOT NULL)")
    return [
        ("insiders_table1_rows_by_year",
         "A2/D1: Thomson insider Form 4 transactions, all issuers, by filing year",
         f"SELECT year(fdate) y, count(*) n FROM read_parquet('{P('tr_insiders','table1')}') GROUP BY 1 ORDER BY 1"),
        ("insiders_table1_cef_rows_by_year",
         "A2: the same, issuers whose CUSIP-6 CRSP calls a closed-end fund (shrcd 14/44)",
         f"SELECT year(t.fdate) y, count(*) n, count(DISTINCT t.cusip6) issuers FROM read_parquet('{P('tr_insiders','table1')}') t "
         f"JOIN {cef6} c ON t.cusip6 = c.c6 GROUP BY 1 ORDER BY 1"),
        ("insiders_form144_rows_by_year",
         "post-2023 list: does Form 144 history exist before EDGAR's electronic 144?",
         f"SELECT year(fdate) y, count(*) n FROM read_parquet('{P('tr_insiders','form144')}') GROUP BY 1 ORDER BY 1"),
        ("insiders_rule10b5_rows_by_year",
         "post-2023 list: Thomson's 10b5-1 flag table, by Thomson create date",
         f"SELECT year(cdate) y, table_type, flag, count(*) n FROM read_parquet('{P('tr_insiders','rule10b5')}') "
         "GROUP BY ALL ORDER BY 1,2,3"),
        ("otc_eod_gse_symbols",
         "G2: Fannie/Freddie preferreds and commons in the OTC end-of-day file",
         f"SELECT symbol, any_value(issue) issue, any_value(sectype) sectype, count(*) n, "
         f"min(closinginsidebidpricedate) first_bid_date, max(closinginsidebidpricedate) last_bid_date "
         f"FROM read_parquet('{P('otc_endofday','endofday')}') WHERE {GSE_PREFIX_SQL} GROUP BY 1 ORDER BY 1"),
        ("otc_eod_rows_by_year",
         "G2: rows per year in the OTC end-of-day file (is the early history populated?)",
         f"SELECT year(closinginsidebidpricedate) y, count(*) n FROM read_parquet('{P('otc_endofday','endofday')}') GROUP BY 1 ORDER BY 1"),
        ("crsp_mf_etf_holdings",
         "A9/CR15: do CRSP MF holdings carry BIZD, PFF and peers? (portfolio report dates)",
         f"WITH h AS (SELECT DISTINCT ticker, crsp_portno FROM read_parquet('{P('crsp_q_mutualfunds','fund_hdr')}') "
         f"WHERE ticker IN {ETF_TICKERS}) "
         f"SELECT h.ticker, h.crsp_portno, count(*) n_rows, count(DISTINCT x.report_dt) n_reports, "
         f"min(x.report_dt) first_report, max(x.report_dt) last_report "
         f"FROM h LEFT JOIN read_parquet('{P('crsp_q_mutualfunds','holdings')}') x ON x.crsp_portno = h.crsp_portno "
         "GROUP BY 1,2 ORDER BY 1"),
        ("sdc_ni_cef_and_pfd_by_year",
         "A1/C1: SDC new issues: closed-end fund issuers (SIC 6726) and preferred-style securities, by year",
         f"SELECT year(master_deal_date) y, count(*) n_all, "
         f"count(*) FILTER (WHERE sicp = '6726') n_sic6726, "
         f"count(*) FILTER (WHERE security ILIKE '%pfd%' OR security ILIKE '%preferred%') n_pfd_text, "
         f"count(*) FILTER (WHERE (security ILIKE '%pfd%' OR security ILIKE '%preferred%' OR security ILIKE '%notes%') "
         f"AND try_cast(offerpric AS DOUBLE) = 25) n_25par "
         f"FROM read_parquet('{P('tr_sdc_ni','wrds_ni_details')}') GROUP BY 1 ORDER BY 1"),
        ("sdc_ma_cef_targets_by_year",
         "Merger arb / CEF tenders: SDC M&A deals with a SIC-6726 target, and all tender offers, by announcement year",
         f"SELECT year(dateann) y, count(*) n_all, count(*) FILTER (WHERE tsicp = '6726') n_t6726, "
         f"count(*) FILTER (WHERE tender = 'Yes' OR tender = 'Y') n_tender, "
         f"count(*) FILTER (WHERE tnation ILIKE 'United States%' AND tpublic = 'Public') n_us_public_target "
         f"FROM read_parquet('{P('tr_sdc_ma','wrds_ma_details')}') GROUP BY 1 ORDER BY 1"),
        ("sdc_ma_tender_values",
         "Which code SDC uses in `tender` (so the count above is not keyed on a guessed value)",
         f"SELECT tender, count(*) n FROM read_parquet('{P('tr_sdc_ma','wrds_ma_details')}') GROUP BY 1 ORDER BY 2 DESC LIMIT 10"),
        ("comp_sp_indices",
         "D8: Compustat index ids for the S&P 500 / 400 / 600",
         f"SELECT gvkeyx, conm, tic, indexid, idxstat FROM read_parquet('{P('comp_na_daily_all','idx_index')}') "
         "WHERE conm ILIKE 'S&P 500%' OR conm ILIKE '%MidCap 400%' OR conm ILIKE '%SmallCap 600%' ORDER BY conm"),
        ("comp_idxcst_adds_by_year",
         "D8: constituent additions (`from` dates) per year for the S&P 500/400/600 ids found above",
         f"SELECT gvkeyx, year(\"from\") y, count(*) n FROM read_parquet('{P('comp_na_daily_all','idxcst_his')}') "
         "WHERE gvkeyx IN ('000003','024248','030824') GROUP BY 1,2 ORDER BY 1,2"),
        ("comp_idxcst_has_removals",
         "D8: does the mirror's constituent history keep REMOVED members? (a `thru` date is set only for them)",
         f"SELECT 'idxcst_his' t, gvkeyx, count(*) n, count(thru) n_with_thru FROM "
         f"read_parquet('{P('comp_na_daily_all','idxcst_his')}') WHERE gvkeyx IN ('000003','024248','030824') GROUP BY 1,2 "
         f"UNION ALL SELECT 'indexcst_his', gvkeyx, count(*), count(thrudate) FROM "
         f"read_parquet('{P('comp_na_daily_all','indexcst_his')}') WHERE gvkeyx IN ('000003','024248','030824') GROUP BY 1,2 "
         "ORDER BY 1,2"),
        ("crsp_mf_sp_etf_holdings",
         "D8 cross-check: monthly holdings of the S&P 400/600 ETFs in CRSP MF (diffs = membership changes)",
         f"WITH h AS (SELECT DISTINCT ticker, crsp_portno FROM read_parquet('{P('crsp_q_mutualfunds','fund_hdr')}') "
         "WHERE ticker IN ('IJH','IJR','MDY','SLY','SPMD','SPSM')) "
         f"SELECT h.ticker, count(DISTINCT x.report_dt) n_reports, min(x.report_dt) first_report, max(x.report_dt) last_report "
         f"FROM h LEFT JOIN read_parquet('{P('crsp_q_mutualfunds','holdings')}') x ON x.crsp_portno = h.crsp_portno "
         "GROUP BY 1 ORDER BY 1"),
        ("ibes_anntims_placeholder",
         "D9: IBES announcement times equal to 00:00:00 (a placeholder, not a time) by year",
         f"SELECT year(anndats) y, count(*) n, count(*) FILTER (WHERE anntims = TIME '00:00:00') n_midnight "
         f"FROM read_parquet('{P('tr_ibes','act_epsus')}') GROUP BY 1 ORDER BY 1"),
        ("comp_seg_customer_by_year",
         "D7: Compustat customer-segment rows per year",
         f"SELECT year(datadate) y, count(*) n FROM read_parquet('{P('comp_na_daily_all','seg_customer')}') GROUP BY 1 ORDER BY 1"),
        ("ibes_act_anntims_by_year",
         "D9: IBES US EPS actuals, share with an announcement time of day, by year",
         f"SELECT year(anndats) y, count(*) n, count(anntims) n_with_time FROM read_parquet('{P('tr_ibes','act_epsus')}') "
         "GROUP BY 1 ORDER BY 1"),
        ("crsp_ciz_last_dates",
         "Correction check: last daily date in the CRSP CIZ stock file vs the legacy dsf",
         f"SELECT (SELECT max(dlycaldt) FROM read_parquet('{P('crsp_a_stock','dsf_v2')}')) ciz_last, "
         f"(SELECT max(date) FROM read_parquet('{P('crsp_a_stock','dsf')}')) legacy_last"),
        ("comp_shortint_rows_by_year",
         "G1/short-interest: Compustat short interest rows per year (current and legacy tables)",
         f"SELECT 'current' t, year(datadate) y, count(*) n FROM read_parquet('{P('comp_na_daily_all','sec_shortint')}') GROUP BY 1,2 "
         f"UNION ALL SELECT 'legacy', year(datadate), count(*) FROM read_parquet('{P('comp_na_daily_all','sec_shortint_legacy')}') GROUP BY 1,2 ORDER BY 1,2"),
    ]


def main() -> int:
    from src.data import r2
    cfg = r2.load_config()
    con = r2.connect(cfg)
    base = f"s3://{cfg.bucket}"
    P = lambda s, t: r2.r2_path(s, t, cfg)
    out, failed = {}, 0
    for name, why, sql in probes(P):
        try:
            df = con.execute(sql).df()
            out[name] = {"why": why, "rows": json.loads(df.to_json(orient="records", date_format="iso"))}
            print(f"== {name}: {why}\n{df.to_string(max_rows=80)}\n", flush=True)
        except Exception as exc:  # recorded, the run fails at the end
            msg = f"{type(exc).__name__}: {str(exc)[:400]}".replace(base, "s3://<bucket>")
            out[name] = {"why": why, "error": msg}
            failed += 1
            print(f"== {name}: ERROR {msg}\n", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=str).replace(base, "s3://<bucket>"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
