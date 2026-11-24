# Tradable universe map, 2026-10-08

**What this is.** A dated record of which credit, fixed-income and multi-asset
products Alpaca can trade and short, and how liquid each family was. It was made
for `results/cef/RESEARCH_AGENDA_2026-10-08.md` §1. **True on its date only.**
`shortable` and `easy_to_borrow` change daily, and the liquidity window ended on
2024-12-31.

**`universe_map.csv` left the repository on 2026-11-09.** It carries permnos and
CRSP-based liquidity per name, which `docs/TEAM.md` keeps off a public repository. The
team lead holds a copy; placed at this path it stays out of git. The scripts that read
it need that copy.

**How it was made.** A desk agent (market-structure-analyst) ran these steps on
2026-10-08:

1. **Alpaca.** One read-only request,
   `GET /v2/assets?status=active&asset_class=us_equity`, made with the cef book's
   paper key through `quantt/broker/alpaca_probe.py`'s own loader. It returned
   14,392 assets (`alpaca_assets_meta.json`). The raw 7MB response is not kept;
   each classified name's flags are in `universe_map.csv`.
2. **CRSP, through R2.** `dsf` over the 252 trading days to 2024-12-31:
   - ADV is the mean of |prc|×vol per name;
   - the spread is the median closing (ask−bid)/mid;
   - the floor test is the sleeve's own 63-day ADV against the spec's
     `min_adv_usd`.
3. **Classification.** ETFs are sorted into families by fund name, using pattern
   rules plus overrides (`code/classify_etf.py`). CEFs, BDCs and mREITs come from
   explicit ticker lists made by reading each CRSP name (`code/classify_cef.py`;
   the judgement calls are in its NOTES). `code/stats.py` builds the family table.

**This is a record, not a maintained script.** The code is kept exactly as run.
It reads intermediate CRSP pulls (`crsp_dsf_pool_2024.parquet` and others) that
were made ad hoc and are not kept. Re-running it means rebuilding those pulls. If
the map is to be refreshed regularly, rewrite it as `scripts/data/` code with its
own R2 queries.

**Holdout.** CEFs outside the deployed 13 are a sealed research holdout (H9).
Only their tradability and liquidity were measured here. No return statistic was
computed on them.

**Caveats.**

- **Stale and missing liquidity.** The liquidity figures are 21 months stale. On
  the 9 ETFs in `data/etf_daily.parquet` they matched that panel exactly. On the
  panel's own data to 2026-07, ADV was 0.8–1.4× the 2024 level. 345 ETFs and 11
  CEF/BDC names listed after 2024 have no liquidity figure.
- **Family membership is a judgement.**
- **Ticker reuse.** Linking CRSP to Alpaca by ticker breaks when a ticker is
  reused. Four such links were found and refused: PINC, MCVT, BNY and BTA.
- **Missing names.** 58 CEF, BDC and mREIT names alive in CRSP were absent from
  Alpaca; nobody checked why.
