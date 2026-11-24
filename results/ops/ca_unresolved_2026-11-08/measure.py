#!/usr/bin/env python3
"""Reproduces every measured figure in results/ops/CA_UNRESOLVED_ROWS_2026-11-08.md.

    python3 results/ops/ca_unresolved_2026-11-08/measure.py --env-file config/.env [--plans DIR]

READ-ONLY. It issues GETs through the repo's own AlpacaClient (keys loaded by the client
from `--env-file`, never printed) and writes nothing. `--plans` is an optional directory of
private plan.json copies (`<book>/<date>/plan.json`, not committed) for C4's recorded windows.

WHAT IT PRINTS. (1) What the party fields of the real feed hold. (2) The 87 funds' CUSIPs and
the longest gap between a fund's dividend rows (the CUSIP table's lookback must exceed it).
(3) The three parsers on the same feed: `--base` (before the ISIN fix), `--isin-base` (the ISIN
fix alone), and this tree (the CUSIP check): which events change. (4) The CUSIP table's state
for each book. (5) Sessions 10-01..11-09 a FLAT book would be refused under each parser, and
the rows that remain. (6) The same for the books ACTUALLY HELD: the core from its own account's
closed orders (`cam.held_since`, every session), C4 from its recorded windows (`--plans`).
The windows are `corp_actions.blocking_events` itself. The feed is as read at run time, so the
table in (5) and (6) is today's, not the one each past session could have read: the counts are
what `halt` would have done with the table as it stands now, not a replay of past reads.
"""
import argparse
import collections
import datetime as dt
import glob
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from ops.schedule.nyse_calendar import is_trading_day, previous_trading_day  # noqa: E402
from quantt.broker import alpaca as new  # noqa: E402
from quantt.session import corp_actions as cam  # noqa: E402
from quantt.session.run import BOOKS, load_spec, spec_params  # noqa: E402

START, END = dt.date(2025, 11, 1), dt.date(2028, 11, 9)     # the gate-window replay
PULL_FROM = "2023-09-01"                                    # far enough for the CUSIP table
LO, HI = dt.date(2026, 10, 1), dt.date(2026, 11, 9)
ET = ZoneInfo("America/New_York")


def parser_at(rev: str, name: str):
    """`quantt/broker/alpaca.py` as of `rev`, loaded beside this tree's."""
    src = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:quantt/broker/alpaca.py"],
                         check=True, capture_output=True, text=True).stdout
    tmp = Path(tempfile.mkdtemp()) / f"{name}.py"
    tmp.write_text(src)
    spec = importlib.util.spec_from_file_location(name, tmp)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def pull(client, params) -> list:
    pages, token = [], None
    for _ in range(new.MAX_PAGES):
        p = dict(params, **({"page_token": token} if token else {}))
        body = client._get(client._data, "/v1/corporate-actions", p)
        pages.append(body)
        token = body.get("next_page_token")
        if not token:
            return pages
    raise RuntimeError("the feed did not end")


def read_all(client, names) -> dict:
    """Every non-dividend row (market-wide) and every universe dividend row, on one read."""
    nd = pull(client, {"types": ",".join(new.CORPORATE_ACTION_TYPES), "start": PULL_FROM,
                       "end": END.isoformat(), "limit": 1000, "data_quality": "all"})
    div = pull(client, {"types": "cash_dividend", "symbols": ",".join(names), "start": PULL_FROM,
                        "end": END.isoformat(), "limit": 1000, "data_quality": "all"})
    rows_nd = [(k, r) for pg in nd for k, v in (pg["corporate_actions"] or {}).items() for r in v or []]
    rows_div = [r for pg in div for r in (pg["corporate_actions"] or {}).get("cash_dividends") or []]
    return {"nd": rows_nd, "div": rows_div}


def replay(mod, feed, names):
    """(events, skipped) from module `mod`'s real parser over `feed`, filtered as the API filters
    (process_date inside [start, end]), one page; no network."""
    env = Path(tempfile.mkdtemp()) / "k.env"             # constants; no network below
    env.write_text("ALPACA_CEF_KEY_ID=K\nALPACA_CEF_SECRET_KEY=S\n")
    import requests
    c = mod.AlpacaClient("cef", env, session=requests.Session(), sleep=lambda s: None)

    def served(base, path, params=None, **kw):
        lo, hi = params["start"], params["end"]
        inside = lambda r: lo <= str(r.get("process_date")) <= hi
        if params["types"] == "cash_dividend":
            ca = {"cash_dividends": [r for r in feed["div"] if inside(r)]}
        else:
            ca = {}
            for k, r in feed["nd"]:
                if inside(r):
                    ca.setdefault(k, []).append(r)
        return {"corporate_actions": ca, "next_page_token": None}
    c._get = served
    sk = []
    return c.corporate_actions(names, START, END, universe=names, skipped=sk, rows={}), sk


def field_value(r, f):
    if "[" not in f:
        return r.get(f)
    return r["stock_movements"][int(f.split("[")[1].split("]")[0])].get("symbol")


def classes(old, feed):
    """Unread party fields on the pre-fix parser, by what the field actually holds, over
    the gate-window feed (process dates START..END)."""
    rows_un, fields, n = set(), collections.Counter(), 0
    by_key = collections.defaultdict(list)
    for k, r in feed["nd"]:
        if START.isoformat() <= str(r.get("process_date")) <= END.isoformat():
            by_key[k].append(r)
    for kind, (key, df, fds) in old.CORPORATE_ACTION_TYPES.items():
        for r in by_key.get(key, []):
            n += 1
            unread = old._ca_read(r, kind, df, fds)[1]
            if unread:
                rows_un.add((key, r.get("id")))
            for u in unread:
                v = field_value(r, u["field"])
                c = ("null/empty" if v in (None, "") else
                     "ISIN-shaped, check digit ok" if new._CA_ISIN_RE.fullmatch(v)
                     and new._ca_isin_check_digit(v) else
                     "CUSIP-format, digit-led" if new._ca_cusip_format(v) else "other")
                fields[(kind, c)] += 1
    return n, len(rows_un), fields


def sessions(a, b):
    d = a
    while d <= b:
        if is_trading_day(d):
            yield d
        d += dt.timedelta(days=1)


def refused(events, held, targets, D):
    return cam.blocking_events(events, held=held, targets=targets, asof=previous_trading_day(D),
                               session_date=D)


def core_held(client):
    """Each session's held names and L_X, rebuilt from the core account's closed orders."""
    orders = client.orders(status="closed")
    filled = [o for o in orders if Decimal(str(o.get("filled_qty") or 0)) > 0]

    def book(D):
        qty = collections.Counter()
        seen = []
        for o in filled:
            sub = new.parse_ts(o["submitted_at"], "submitted_at").astimezone(ET).date()
            if sub >= D:
                continue
            seen.append(o)
            sgn = 1 if o["side"] == "buy" else -1
            qty[o["symbol"]] += int(sgn * Decimal(str(o["filled_qty"])))
        held = [s for s, q in qty.items() if q]
        return cam.held_since(seen, held) if held else {}
    return book


def show_blockers(evs, held, targets, D):
    ev = {e["id"]: e for e in evs}
    ids = sorted({x["id"] for x in refused(evs, held, targets, D)})
    return [(i[:8], ev[i]["type"], next(iter(ev[i].get("saw", {"-": ""}).values()))[:32]) for i in ids]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--env-file", required=True, help="the file holding the book's Alpaca keys")
    ap.add_argument("--plans", help="directory of private plan.json copies (optional)")
    ap.add_argument("--base", default="a5b94c8", help="the parser before the ISIN fix")
    ap.add_argument("--isin-base", default="b7360b8", help="the parser with the ISIN fix alone")
    a = ap.parse_args()
    old, isin = parser_at(a.base, "old_alpaca"), parser_at(a.isin_base, "isin_alpaca")
    client = new.AlpacaClient("cef", a.env_file)
    uni = {b: sorted(spec_params(load_spec(BOOKS[b].spec_path))["universe"]) for b in ("cef", "c4")}
    names = sorted(set(uni["cef"]) | set(uni["c4"]))
    print("universes:", {b: len(v) for b, v in uni.items()},
          "SNTI in either:", any("SNTI" in v for v in uni.values()),
          "JAGX in either:", any("JAGX" in v for v in uni.values()))
    feed = read_all(client, names)

    n, nun, fields = classes(old, feed)
    print(f"\n(1) feed read: {n} rows, process dates {START}..{END}; unread party rows on the old parser: {nun}")
    by = collections.Counter()
    for (kind, c), v in sorted(fields.items()):
        by[c] += v
    print("    fields by class:", dict(by))
    passing = [v for _, r in feed["nd"] if START.isoformat() <= str(r.get("process_date")) <= END.isoformat()
               for k, v in r.items() if k.endswith("symbol") and new._ca_cusip_format(v)
               and new._SYMBOL_RE.fullmatch(v)]
    agree = tot = 0
    for _, r in feed["nd"]:
        cus = {x for f, x in r.items() if f.endswith("cusip")} | {m.get("cusip") for m in r.get("stock_movements") or [] if isinstance(m, dict)}
        items = [x for f, x in r.items() if f.endswith("symbol")] + [m.get("symbol") for m in r.get("stock_movements") or [] if isinstance(m, dict)]
        for x in items:
            if new._ca_cusip_format(x):
                tot += 1
                agree += x in cus
    print(f"    letter-led CUSIP-format fields that pass as tickers: {len(passing)}; "
          f"CUSIP-format party values agreeing with a CUSIP field of their row (whole pull): {agree} of {tot}")

    divs = collections.defaultdict(list)
    for r in feed["div"]:
        if r.get("ex_date"):
            divs[r["symbol"]].append((r["ex_date"], r.get("cusip")))
    flat = sorted({c for v in divs.values() for _, c in v if c})
    gaps = {s: max([(dt.date.fromisoformat(b[0]) - dt.date.fromisoformat(a[0])).days
                    for a, b in zip(sorted(v), sorted(v)[1:])] or [0]) for s, v in divs.items()}
    worst = max(gaps, key=gaps.get) if gaps else None
    print(f"\n(2) dividend rows {len(feed['div'])}; funds with a CUSIP {len(divs)} of {len(names)}; CUSIPs {len(flat)}; "
          f"issue codes {sorted(collections.Counter(c[6:8] for c in flat).items())}; "
          f"non-numeric {[c for c in flat if not c[6:8].isdigit()]}; longest gap between a fund's "
          f"dividend ex-dates {gaps.get(worst)} days ({worst})")

    res = {}
    print("\n(3) the three parsers on the same feed (`saw` aside)")
    for b in ("cef", "c4"):
        eo, so = replay(old, feed, uni[b])
        ei, si = replay(isin, feed, uni[b])
        en, sn = replay(new, feed, uni[b])
        strip = lambda e: {k: v for k, v in e.items() if k != "saw"}
        do, di, dn = ({e["id"]: strip(e) for e in x} for x in (eo, ei, en))
        print(f"    {b}: events {len(eo)} -> {len(ei)} (ISIN fix) -> {len(en)} (CUSIP check); "
              f"left at each step {len(set(do) - set(di))}, {len(set(di) - set(dn))}; added "
              f"{len(set(dn) - set(di))}; changed among the survivors "
              f"{sum(dn[i] != di[i] for i in dn if i in di)}; "
              f"bond rows {sum('bonds' in k for k in sn)}, foreign CUSIP rows "
              f"{sum('foreign_cusips' in k for k in sn)}, malformed skips "
              f"{sum('bonds' not in k and 'foreign_cusips' not in k and 'cusip_table' not in k for k in sn)}")
        print(f"    {b}: cusip_table {next(k['cusip_table'] for k in sn if 'cusip_table' in k)}")
        t0 = time.monotonic()
        live = new._CaCusipTable(client, uni[b], START, END)
        live.load()
        print(f"    {b}: the real table read took {time.monotonic() - t0:.2f}s, {live.summary()['status']}")
        still = [e for e in en if "row_id" in e and e.get("missing")]
        print(f"    {b}: still unresolved after the CUSIP check: {len(still)} "
              f"{[(e['id'][:8], e['type'], str(e['date']), list(e.get('saw', {}).values())[:1]) for e in still]}; "
              f"events naming a universe fund by ticker: {sum(1 for e in en if e.get('parties') and not e.get('missing'))}")
        res[b] = {"old": eo, "isin": ei, "new": en}

    print(f"\n(5) FLAT: sessions refused {LO}..{HI}, every universe name target-only")
    days = list(sessions(LO, HI))
    for b in ("cef", "c4"):
        for tag in ("old", "isin", "new"):
            hit = [d for d in days if refused(res[b][tag], {}, uni[b], d)]
            print(f"    {b:4s} {tag:5s} {len(hit)} of {len(days)}")
    for D in days:
        rows = show_blockers(res["c4"]["new"], {}, uni["c4"], D)
        if rows:
            print(f"    C4 flat, after: {D} {rows}")

    print(f"\n(6) THE BOOKS ACTUALLY HELD: sessions refused {LO}..{HI}")
    book = core_held(client)
    for tag in ("old", "isin", "new"):
        hit = [d for d in days if refused(res["cef"][tag], book(d), [], d)]
        print(f"    core {tag:5s} {len(hit)} of {len(days)}: {[str(d)[5:] for d in hit]}")
    for D in days:
        rows = show_blockers(res["cef"]["new"], book(D), [], D)
        if rows:
            print(f"    core held, after: {D} {rows}")
    if a.plans:
        recs = {}
        for f in sorted(glob.glob(a.plans + "/c4/*/plan.json")):
            ca = json.load(open(f)).get("corporate_actions")
            if ca and ca.get("names"):
                recs[dt.date.fromisoformat(ca["session_date"])] = {
                    "held": {s: dt.date.fromisoformat(v["held_since"]) for s, v in ca["names"].items()
                             if v.get("held_since")},
                    "targets": [s for s, v in ca["names"].items() if not v.get("held_since")]}
        last = max(recs)
        for D in (d for d in days if d >= min(recs)):
            r = recs.get(D, recs[last])
            tag = "recorded" if D in recs else f"UPPER BOUND on {last}'s windows"
            for t in ("old", "isin", "new"):
                print(f"    c4 {D} {t:5s} {len({x['id'] for x in refused(res['c4'][t], r['held'], r['targets'], D)})} blocking ({tag})")
            rows = show_blockers(res["c4"]["new"], r["held"], r["targets"], D)
            if rows:
                print(f"    c4 held, after: {D} {rows}")


if __name__ == "__main__":
    main()
