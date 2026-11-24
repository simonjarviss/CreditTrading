#!/bin/sh
# R4 reproduce. Fetches skip any capture already on disk, so a second run is offline.
# Network: web.archive.org (CDX + id_ captures) only. No credentials, no EDGAR, no broker.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
# 1. archived holdings pages (CDX lists are saved under raw/wayback/)
python3 -I fetch_wayback.py --rows raw/wayback/cdxall_invescopowershares_com_products_holdings_aspx_.txt '(?i)ticker=pcef$' pcef_ps
python3 -I fetch_wayback.py "invescopowershares.com/products/overview.aspx?ticker=PCEF" pcef_ov 2010 2014
python3 -I fetch_wayback.py "yieldshares.com/fund-holdings*" ys_hold 2013 2019
python3 -I fetch_wayback.py --rows raw/wayback/cdxx_www_vaneck_com_etf_income_xmpt_holdings_.txt 'holdings' xmpt_h
python3 -I fetch_wayback.py --rows raw/wayback/cdxx_vaneck_com_us_en_investments_cef-municipal-income-etf-xmpt_holdings_.txt 'holdings' xmpt_h2
# The two Amplify family CSVs (2020-03-17, 2021-02-17/18) were fetched with curl from
#   https://web.archive.org/web/<ts>id_/https://amplifyetfs.com/Data/Feeds/ForesideAmplify.40XL.XL_Holdings.csv
# into raw/wayback/snaps/amp_holdings_<ts>.csv (timestamps in raw/fetch_log.csv).
# 2. parse, AUM, size and count
python3 -I parse_snapshots.py
python3 -I parse_aum.py
cd "$HERE/../tree" && python3 ../r4_index_rebal/size_events.py | tee ../r4_index_rebal/out/size_events_final.txt
