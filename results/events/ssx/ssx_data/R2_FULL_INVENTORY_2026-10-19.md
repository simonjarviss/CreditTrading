# R2 full inventory: every schema and table in the WRDS mirror (2026-10-19)

**Seat:** `ssx_data` (data librarian), SS-desk expansion, team lead request of 2026-10-19.
Zero trials. Read-only. The bucket is redacted to `<bucket>`. **This is true on 2026-10-19
only.** Re-run before you quote any date or count.

| what | command | output |
|---|---|---|
| enumerate and describe every object | `QUANTT_ENV_FILE=… python3 scripts/events/ssx/ssx_data_r2_inventory.py --threads 12` (run 2026-10-19 15:25 UTC, 86 s, 0 errors) | `r2_full_inventory_2026-10-19.{csv,json}`, `r2_full_inventory_columns_2026-10-19.csv` |
| per-table appendix (size, rows, columns, date ranges) | `python3 scripts/events/ssx/ssx_data_render_inventory.py` (offline) | `R2_FULL_INVENTORY_TABLES_2026-10-19.md` |
| coverage probes for the event ideas (aggregates only) | `QUANTT_ENV_FILE=… python3 scripts/events/ssx/ssx_data_r2_event_probes.py` | `r2_event_probes_2026-10-19.json` |

**Method.** DuckDB `glob('s3://<bucket>/wrds/**')` goes through `src/data/r2.connect()`.
Object size and last-modified come from `read_blob` with only those columns projected, so
DuckDB issues a HEAD. Rows, columns and types come from the parquet footer. A date range is
the min/max of the row-group statistics of each DATE/TIMESTAMP-typed column. If any row
group lacks a statistic, the range is reported as `NO_STATS`, never as a partial range.
Dates stored as strings are not parsed. Every figure below is [V] from these commands on
2026-10-19 unless it is labelled otherwise.

---

## 1. The answer

- **The mirror holds 1,146 parquet tables in 81 schemas, 433.1 GB, about 24.4 billion
  rows** [V]. `results/data/R2_CATALOG.md` described 6 tables and listed 6 schemas.
- **The "about 412 tables" in earlier desk notes is the number of entries in the
  mirror's own `wrds/manifest.json`** (412 [V]). That file is an ingestion log keyed
  by WRDS library and, for big tables, by year chunk (`crsp.dsf/2000` …). It is not
  a table count. Its `last_updated` is 2026-06-29 for every entry. 11 entries are flagged
  `complete: false`, all of them 2026 chunks: `comp.fundq`, five `tr_ibes` tables, four
  `tr_insiders` tables and `tr_worldscope.wrds_ws_fundq`. **Do not treat 2026 rows in
  those tables as complete.**
- **The mirror is one snapshot.** Every object was last modified between 2026-06-26 and
  2026-07-03 [V], and nothing has been refreshed since. `wrds/coverage.json`
  (updated_at 2026-08-22) says ff/cboe/frb run "through 2025-01-31". That disagrees with the
  measured ends (ff 2026-04-30, frb 2025-02-13), so that file is stale and is not used.
- **It holds most of what the event ideas need for history:** Compustat, IBES, Thomson
  13F and insiders (including Form 144 and a 10b5-1 flag), SDC M&A and New Issues, MSRB
  muni trades, OTC end-of-day prices (including the GSE preferreds), FJC bankruptcy
  filings, CRSP's CIZ files to 2025-12-31, and CRSP mutual-fund holdings of
  BIZD/PFF/IJH/IJR.
- **It does not hold:**
  - Mergent FISD;
  - OptionMetrics;
  - RavenPack;
  - full Audit Analytics (only a 1,491-row sample);
  - Capital IQ;
  - TAQ;
  - DealScan;
  - Markit;
  - ISS;
  - BoardEx beyond a trial extract;
  - any ratings history after 2017-02;
  - any EDGAR filing index;
  - Russell index membership;
  - a survivorship-free S&P 400/600 membership history (§4).
- **Correction to `docs/DATA.md` §3.** "The CRSP stock file stops at 2024-12-31" is true
  of the legacy SIZ `dsf`. **The CIZ tables `dsf_v2` and `stkdlysecuritydata` run to
  2025-12-31**, as do `stkdelists` (to 2025-12-30) and `stkdistributions` (ex-dates to
  2025-12-31) [V]. French's library gives the reason: "CRSP's Stock and Indexes Legacy
  Format (FIZ) files were discontinued after the December 2024 data release. Beginning
  with the January 2025 data release, we use the new … (CIZ) files" [V, data_library.html
  fetched 2026-10-19]. So CRSP **can** check 2025 prices, on the CIZ files.
- **Licence.** The WRDS content is licensed. No row-level data left the bucket. This note
  and the JSON hold metadata and aggregate counts only, as `R2_CATALOG.md` already does.
- **Not read: a non-WRDS top-level prefix, `portfolios/`.** It has 32 objects of
  per-person files. It is outside this survey and was deliberately left unread. Only the
  object count is recorded.

## 2. Schemas (all 81)

Rows are footer counts. GB is the object size. The per-table detail is in
`R2_FULL_INVENTORY_TABLES_2026-10-19.md`.

| schema | tables | GB | rows | what it is |
|---|---|---|---|---|
| `auditsmp_all` | 15 | 0.0 | 1,491 | **Audit Analytics SAMPLE**: `nt` has 2 rows, `auditnonreli` 5, `diroffichange` 183. Unusable |
| `bank_all` | 21 | 1.21 | 9,231,339 | bank call reports, holding-company filings, structure |
| `block_all` | 3 | 0.0 | 62,925 | blockholder data, meetings 1996–2001 |
| `boardex_trial` | 36 | 0.01 | 790,813 | **trial**: `jr_board_dir_announcements` has 1,570 rows |
| `bvd_amadeus_trial`, `bvd_bvdbankf_trial`, `bvd_orbis_trial` | 3 / 6 / 9 | 0.0 | 1,021 / 1,369 / 4,402 | trials |
| `calcbench_trial` | 3 | 0.0 | 128,402 | trial |
| `cboe_all` | 1 | 0.0 | 10,742 | Cboe volatility indices to 2026-05-29 (manifest) |
| `comp_execucomp` | 15 | 0.15 | 3,444,656 | ExecuComp |
| `comp_global_daily` | 123 | 14.35 | 744,735,763 | Compustat Global |
| `comp_na_daily_all` | 203 | 11.49 | 633,280,315 | **Compustat North America** (§3) |
| `contrib_*` (11 schemas) | 41 | 74.4 | ~1.29 bn | user-contributed datasets: global factors, CEO turnover (1,438 rows, 1993–2021), classified boards, KPSS patents, bond–firm link and others |
| `crsp_a_ccm` | 11 | 0.07 | 1,976,691 | CRSP–Compustat link; `comphist` has IPO and delisting dates |
| `crsp_a_stock` | 94 | 29.09 | 1,238,839,751 | CRSP stock, legacy SIZ (to 2024-12-31) and **CIZ (to 2025-12-31)** |
| `crsp_q_indexhist` | 11 | 11.04 | 286,786,289 | CRSP index **levels**, tick and EOD, 2011–2026-03-31. Not constituents |
| `crsp_q_mutualfunds` | 29 | 15.19 | 1,063,231,788 | CRSP MF, including **holdings** (2001-12-31 → 2026-03-31) |
| `djones_all`, `dmef_all`, `doe_all`, `iri_all`, `pwt_all`, `public_all`, `macrofin_comm_trade`, `rq_all`, `totalq_all`, `phlx_all`, `ims_obp_trial`, `pitchsmp` | various | ≤ 0.25 each | small | Dow Jones averages to 2008, a direct-marketing panel to 1992, Penn World Tables, macro-finance factors, PHLX currency options and similar. Not event-relevant |
| `ff_all` | 12 | 0.0 | 74,572 | Fama-French; factors to 2026-04-30 |
| `fjc_litigation`, `fjc_linking` | 4 / 3 | 4.19 / 0.01 | 61,706,645 / 353,290 | **FJC Integrated Database: bankruptcy** (filedate 1929 → 2026-03-31), civil, criminal and appeals, plus links (bankruptcy link has 841 rows to 2019) |
| `frb_all` | 4 | 0.0 | 41,962 | H.15 rates to 2025-02-13; FX |
| `msrb_all` | 2 | 6.0 | 216,184,403 | **MSRB RTRS muni trades**, 2005-01-03 → 2025-12-31 |
| `otc_endofday` | 1 | 1.41 | 75,609,670 | **OTC Markets end-of-day prices**, to 2026-06-01 |
| `tfn`, `tr_mutualfunds` | 1 / 10 | 4.03 / 7.08 | 282,460,772 / 793,844,794 | Thomson **S12 mutual-fund holdings**, fdate 1980 → 2025-12-31 (`tfn.s12` duplicates `tr_mutualfunds.s12`) |
| `tr_13f` | 7 | 5.29 | 455,663,810 | **Thomson S34 13F holdings**, fdate 1980-03-31 → 2025-12-31 |
| `tr_common` | 30 | 26.7 | 2,217,988,654 | Refinitiv security master and identifiers |
| `tr_ds_comds`, `tr_ds_econ`, `tr_ds_equities`, `tr_ds_fut` | 10 / 7 / 43 / 20 | 0.93 / 1.92 / 97.99 / 10.84 | ~7.65 bn | **Datastream**: equities including `ds2capevent` and `ds2div`, futures, commodities, economics |
| `tr_ibes` | 166 | 45.63 | 3,551,612,387 | **IBES**: US and international detail, summary, actuals, recommendations, price targets, surprises |
| `tr_insiders` | 10 | 1.84 | 55,118,973 | **Thomson insider filings**: Forms 3/4/5 (`table1`, `table2`, `header`), **`form144`**, **`rule10b5`** |
| `tr_sdc_ma`, `tr_sdc_ni`, `tr_sdc_joint_ventures` | 6 / 5 / 1 | 0.76 / 0.27 / 0.08 | 5,876,340 / 15,835,426 / 845,943 | **SDC Platinum: M&A, New Issues**, joint ventures |
| `tr_worldscope` | 23 | 18.75 | 2,055,635,794 | Worldscope |
| `trace`, `trace_enhanced`, `trace_standard` | 1 / 14 / 23 | 10.41 / 13.23 / 10.2 | ~1.54 bn | TRACE (`trace.trace_enhanced` duplicates `trace_enhanced.trace_enhanced`) |
| `wrdsapps_*` (17 schemas) | 28 | ~6.9 | ~92 m | WRDS derived: financial ratios, event-study inputs, links (CRSP–bond, CRSP–IBES, CRSP–TAQ, CRSP–FactSet), Exhibit 21 subsidiaries (`wrds_relationships`, fdate 1993-12-22 → 2025-02-26), executive–insider link, patents |
| `wrdssec_midas` | 1 | 1.92 | 21,149,699 | SEC MIDAS market-structure metrics, 2012-01-03 → 2025-12-31 |

## 3. Event-relevant tables: rows and date ranges

Dates are the min..max of footer statistics. The extreme values (1900-01-01, 9999-12-31)
are vendor placeholders: they are kept as measured, not cleaned.

| table | rows | date columns (min .. max) | serves |
|---|---|---|---|
| `crsp_a_stock.dsf_v2` / `stkdlysecuritydata` (CIZ daily) | 110,245,749 | dlycaldt 1925-12-31 .. **2025-12-31**; has `shrout`, `dlyorddivamt`, `dlydelflg` | prices, shares outstanding, D5 |
| `crsp_a_stock.dsf` (legacy) | 107,663,470 | date .. 2024-12-31 | as above, legacy |
| `crsp_a_stock.stkdelists` | 29,833 | delistingdt .. 2025-12-30 | merger arb, SPAC, A4 |
| `crsp_a_stock.dsedelist` / `msedelist` | 38,872 / 38,843 | dlstdt .. 2024-12-31 | legacy delistings |
| `crsp_a_stock.stkdistributions` | 1,101,681 | disexdt .. 2025-12-31; disdeclaredt 1961-10-03 .. 2025-12-31 | spin-offs, distributions |
| `crsp_a_stock.dsedist` | 1,064,794 | exdt .. 2024-12-31; dclrdt from 1961-10-03 | legacy distributions |
| `crsp_a_stock.stkshares` / `dseshares` | 3,087,489 / 2,913,355 | shrstartdt .. 2025-12-31 / shrsdt .. 2024-12-31 | A1, A3 issuance and buybacks |
| `crsp_a_stock.stksecurityinfohist`, `stocknames_v2` | 191,048 / 87,766 | .. 2025-12-31 | names, CUSIP, issuer type |
| `crsp_a_ccm.comphist` | 505,123 | hipodate 1946-01-14 .. 2026-01-09 | D5 IPO date |
| `crsp_q_mutualfunds.holdings` | 450,420,111 | report_dt 2001-12-31 .. 2026-03-31 | A9, CR15, D8 (§4) |
| `crsp_q_mutualfunds.crsp_cik_map` | 68,382 | — | fund → CIK |
| `crsp_q_mutualfunds.fund_hdr_hist` | 573,865 | chgdt .. 2026-03-30 | A5 (open-end only) |
| `tr_13f.s34` | 127,142,721 | fdate 1980-03-31 .. 2025-12-31 | 13F ownership |
| `tr_insiders.table1` (Form 4 non-derivative) | 17,358,800 | fdate 2007-08-17 .. 2026-06-26; trandate .. 2026-06-25 | A2, D1 |
| `tr_insiders.table2` (derivative) | 13,405,371 | fdate 2003-12-09 .. 2026-06-26 | A2, D1 |
| `tr_insiders.header` | 8,221,193 | fdate 2003-11-05 .. 2026-06-26 | filings |
| `tr_insiders.form144` | 1,203,450 | fdate 2001-12-31 .. 2026-06-26 | post-2023 list (§5) |
| `tr_insiders.rule10b5` | 9,598,293 | cdate 1997-09-09 .. 2026-06-25 | post-2023 list |
| `tr_sdc_ma.wrds_ma_details` | 1,617,588 | dateann 1965-01-01 .. 2026-07-01; datetender 1978-05-15 .. 2026-09-07 | merger arb, CEF tenders, spin-offs |
| `tr_sdc_ni.wrds_ni_details` | 1,718,307 | master_deal_date 1962-08-30 .. 2026-07-02 | A1, C1, D5 (has `ipo`, `quiet_period`, lock-up fields) |
| `comp_na_daily_all.funda` / `fundq` | 940,972 / 2,122,536 | datadate .. 2026-05-31; `rdq` 1971-07-28 .. 2026-06-26 | D2, D9 |
| `comp_na_daily_all.co_filedate` | 2,637,695 | filedate 1967-01-03 .. 2026-06-29 | D4 cross-check |
| `comp_na_daily_all.sec_shortint` / `_legacy` | 5,205,923 / 4,770,658 | 2006-07-14 .. 2026-06-15 / 1973-01-15 .. 2024-12-31 | short interest without FINRA's terms (§4) |
| `comp_na_daily_all.idxcst_his` | 24,322 | from .. 2026-06-24 | D8: **current members only** (§4) |
| `comp_na_daily_all.seg_customer` | 146,526 | datadate **2020-06-30** .. 2026-04-30 | D7: 2020 onward only |
| `comp_na_daily_all.io_q*` (13F aggregates) | 154,837 – 1,486,552 | datadate 2004-03-31 .. 2026-03-31 | ownership |
| `comp_na_daily_all.it_mbuysell` | 166,463 | datadate 2025-06-30 .. 2026-10-31 | recent window only |
| `comp_na_daily_all.adsprate` (S&P ratings) | 3,023,652 | datadate 1978-11-30 .. **2017-02-28** | ratings, ends 2017 |
| `comp_na_daily_all.sec_divid`, `sec_split` | 1,172,153 / 43,148 | .. 2026-06 | distributions |
| `tr_ibes.act_epsus` | 1,323,271 | anndats 1976-01-15 .. 2026-05-14 | D9 |
| `tr_ibes.det_epsus`, `recddet`, `ptgdet`, `surpsum` | 34.5 m / 3.3 m / 7.4 m / 13.7 m | .. 2026-05-14 | analysts |
| `tr_ds_equities.ds2capevent` / `ds2div` | 378,132 / 3,500,546 | announceddate .. 2026-06-24 (div) | capital events, international |
| `msrb_all.msrb` | 215,791,679 | trade_date 2005-01-03 .. 2025-12-31 | B1, B2 |
| `otc_endofday.endofday` | 75,609,670 | closinginsidebidpricedate 1990-11-19 .. 2026-06-01; shortinterestdate 2006-07-25 .. 2026-05-15 | G2 |
| `trace_enhanced.trace_enhanced` / `trace_standard.trace` | 455,675,242 / 318,892,226 | trd_exctn_dt 2002-07-01 .. 2025-12-04 / .. 2026-06-05 | B4, C2 |
| `trace_enhanced.camasterfile` | 3,410,696 | stdt .. 2026-06-05 | bond master: issuer, coupon, maturity, 144A, grade. A partial FISD substitute; it has no covenants or call schedule |
| `wrdsapps_link_crsp_bond.bondcrsp_link` | 358,312 | link .. 2025-12-31 | bond → permno |
| `fjc_litigation.bankruptcy` | 38,030,839 | filedate .. 2026-03-31 (snapshots from 2008-09-30) | B1 (chapter 9), B4, C2 |
| `wrdsapps_subsidiary.wrds_relationships` | 12,306,290 | fdate 1993-12-22 .. 2025-02-26 | D7 cross-check (Exhibit 21) |

## 4. Coverage probes (`ssx_data_r2_event_probes.py`, aggregates)

- **Insider filings on closed-end funds** (`tr_insiders.table1`, issuer CUSIP-6 in CRSP
  share code 14/44):
  - 285 to 800 distinct issuers a year over 2007–2026;
  - 3,326 to 14,508 rows a year after 2007. The 2007 figure (58,064 rows) is a backfill
    spike: `table1`'s fdate begins 2007-08-17.
  - BDCs (mostly CRSP share code 11) are not in this count.
- **GSE preferreds** (`otc_endofday`): all 37 Fannie and Freddie symbols are present.
  - That is FNMA and FMCC common plus 35 preferreds: FNMAS, FNMAT, FMCKJ and the rest.
  - Each has 3,677 rows, 2011-09-01 → 2026-06-01. FNMFM starts 2011-01-11 and FNMFO
    2013-11-04.
  - **The file has nothing for these symbols before 2011-09-01**, although the file's
    rows begin in 1990.
- **ETF holdings in CRSP MF** (monthly report dates):

  | ETF | reports | first | last |
  |---|---|---|---|
  | BIZD | 136 | 2013-07-31 | 2025-11-30 |
  | PFF | 187 | 2010-06-30 | 2026-03-31 |
  | PFFD | 95 | 2017-09-30 | 2026-03-31 |
  | PGX | 183 | 2010-06-30 | 2026-03-31 |
  | IJH | 188 | 2010-06-30 | 2026-03-31 |
  | IJR | 189 | 2010-06-30 | 2026-03-31 |
  | MDY | 187 | 2010-06-30 | 2026-02-28 |
  | SPMD | 181 | 2010-06-30 | 2026-03-31 |
  | SPSM | 148 | 2013-07-31 | 2026-03-31 |
  | SLY | 150 | 2010-06-30 | 2023-05-31 |
  | HYG, JNK | 187 each | 2010-06-30 | 2026-03-31 |
  | MUB | 184 | 2010-06-30 | 2026-03-31 |

- **S&P index membership (Compustat).**
  - The index ids are S&P 500 `000003`, MidCap 400 `024248` and SmallCap 600 `030824`.
  - `idxcst_his` and `indexcst_his` hold **503 / 400 / 602 rows with 0 `thru` dates**.
    They are today's members only, and every removed member is missing.
  - **Additions measured from them are survivorship-biased, and deletions cannot be
    measured at all.** The CRSP MF holdings of IJH/IJR/MDY/SPMD (monthly, 2010 onward)
    are the in-house way to see both sides.
- **SDC New Issues.**
  - Issuers with SIC 6726 (investment offices; the CEF/BDC proxy here): 316 to 1,392 a
    year over 2009–2025.
  - Rows whose description is preferred or notes and whose offer price is 25: 29 to 134 a
    year over 2009–2020, then 2 to 12 a year over 2022–2026. Either SDC's coverage of
    retail $25 issues thinned or the text rule misses them [U which]. **C1 should not rely
    on SDC.**
- **SDC M&A.**
  - Tender offers (`tender = 'Yes'`, the code measured): 30,124 in all, 589 to 1,209 a
    year since 1999.
  - Targets with SIC 6726: 71 to 294 a year since 2006.
  - US public targets: 836 to 2,091 a year since 2005.
- **IBES announcement time of day.**
  - `anntims` is never null, but 00:00:00 is a placeholder. It is 21,842 of 21,843 rows in
    1990, 14,977 of 38,326 in 1998, 145 of 35,693 in 2000, and at most 695 a year from 2005.
  - **Time of day is usable from about 2000.**
- **Short interest (Compustat).** The current table has 97,922 rows in 2006, then 192,690
  to 405,118 a year. The legacy table runs 1973–2024.
- **Form 144 (`tr_insiders.form144`).** Every year from 2001 to 2026 is populated: 17,263
  rows (2022) to 172,067 (2001).
- **10b5-1 flag (`tr_insiders.rule10b5`).**
  - Flag `Y` rows: 14,480 (2007), then 3,086 to 102,204 a year. Thousands of `N` rows a
    year.
  - Table type 1 or 2 matches Forms 4 `table1`/`table2` [U: Thomson's derivation of the
    flag before the 2023 checkbox is not documented here].

## 5. What is NOT in the mirror (checked against the 81 schema names)

| dataset | status | consequence |
|---|---|---|
| **Mergent FISD** | absent (no `fisd`/`mergent`) | baby-bond and preferred terms (call, float dates, covenants) come from prospectuses (EDGAR 424B). `trace_*.camasterfile` gives coupon, maturity and grade only |
| **OptionMetrics** | absent (re-confirmed; options come only from `options/*` tick files) | — |
| **RavenPack** / any news analytics | absent | Alpaca/Benzinga news is the only news source |
| **Audit Analytics** (full) | sample only: 1,491 rows across 15 tables; `nt` = 2 rows | D4 and D6 have no licensed cross-check; use EDGAR plus Compustat `co_filedate` |
| **Capital IQ**, **DealScan**, **Markit**, **ISS**, **FactSet**, **TAQ** | absent (only link tables for DealScan, FactSet, TAQ) | — |
| **Credit ratings after 2017-02** | `adsprate` ends 2017-02-28; no Moody's or Fitch | A7 needs N-PORT or 17g-7 files |
| **BoardEx** | trial extract only (1,570 announcements) | D6 cross-check is thin |
| **EDGAR filing index / WRDS SEC Analytics** | absent (only `wrdssec_midas`) | EDGAR stays the free primary |
| **Russell membership**; **survivorship-free S&P 400/600 membership** | absent; Compustat holds current members only | D8 uses ETF holdings diffs |
| **IBES Guidance** | absent | — |
| **CRSP `dsp500list`** | absent | — |
| **Thomson 13F after 2025-12-31**, **MSRB after 2025-12-31**, **TRACE enhanced after 2025-12-04**, **Compustat after 2026-06**, **IBES after 2026-05-14** | snapshot ends | forward work needs the free sources |
