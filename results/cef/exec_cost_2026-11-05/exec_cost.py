"""Execution-cost study, both paper books (measured 2026-11-05).

Report only, zero trials. It measures the books' own fills against the decide-time estimate, the
official closing-auction print and the SIP quote at send, and prices counterfactual send times and
limit prices from the SIP tape. It tests no strategy and moves no counter. Note:
`results/cef/EXEC_COST_STUDY_2026-11-05.md`; output of record (aggregates only):
`results/cef/exec_cost_2026-11-05/aggregates_2026-11-05.json`.

WHY IT EXISTS. Execution cost is the largest lever left on returns. The verify line ("fill vs auction",
e.g. +18.3bp on the core on 2026-11-04) and the prior study (`results/cef/FILL_DRIFT_2026-11-02.md`:
10.8bp against the 15:50 mid, about 6bp of it the half-spread) say how much, not where it comes from,
what would cut it, or how much of it a live account would pay. On paper the plan is sent as market
`day` orders at 15:52 ET (CLAUDE.md order-path rule 3, `execution.mode = late_market`); a live account
sends MOC (`cls`). Alpaca's paper engine fills "against the best available current market price
(NBBO)", does not check quantity "against the NBBO quantities", and fills a limit only once it is
marketable [V: docs.alpaca.markets/docs/paper-trading, updated 2026-07-07, fetched 2026-11-05]. So a
paper fill is priced by the touch at the moment the order is evaluated, and every counterfactual here
is priced the same way, from the SIP quote stream.

INPUTS.
  --records DIR   private copies of the runner's state, DIR/<book>/<YYYY-MM-DD>/ with orders.jsonl,
                  plan.json, send.json and reconcile.json, as copied from the VM. They hold account
                  data (order ids, fills, equity). They are read only; nothing from them is written
                  where git can see it.
  --cache-dir DIR market data (and, for the two days whose records carry no fill price, the cef
                  account's FILL activities), written by `fetch`, read by `analyse`. Refused anywhere
                  git can see, and under data/.
FETCH is GET-only: data.alpaca.markets /v2/stocks/{quotes,trades,auctions,bars} and
/v2/stocks/meta/exchanges, and paper-api /v2/account/activities/FILL for days whose records hold no
fill price (2026-09-30 and 2026-10-01: the runner of that week wrote no `final` event and verify
errored). Keys come from the file named by QUANTT_ENV_FILE through `quantt.broker.alpaca_probe`'s
loader; they are never printed and there is no default file. No order code is imported; `_get`
refuses any other host or path.

OUTPUTS (`analyse`).
  --aggregates PATH  the JSON of record: counts, bp and USD sums by bucket, group, side, day and grid
                     point. No account or order id, no symbol, no per-order or per-fill row.
  --private-dir DIR  per-order rows and the per-name table (account data); refused where git can see.

SIGNS AND UNITS. s = +1 buy, -1 sell (a short sale is a sell). Every component is in bp of the
official close P_c of the fill day, positive = worse for us, and aggregated notional-weighted
(sum of cost$ / sum of qty_filled x P_c), the weighting verify's `fill_vs_auction_bp` uses, so the
per-day B below ties to verify exactly. Prices: P_e the plan's est_price (the panel close of the
decide date, t-1); b_s, a_s, m_s the SIP bid, ask and mid of the last valid quote at or before the
order's submit time; f the order's fill VWAP; P_c the primary exchange's official closing print
(condition M; verify's own print from reconcile.json where it exists).
  IS    s(f - P_e)/P_c     fill vs the decide-time estimate (implementation shortfall)
  OVN   s(m_s - P_e)/P_c   decide-time close -> mid at send: overnight and intraday move (the shift(2)
                           delay; the backtest bears it too, so it is not a cost against the model)
  HS    s(f - m_s)/P_c     fill vs mid at send               IS = OVN + HS
  QHS   (a_s - b_s)/2/P_c  quoted half-spread at send
  TCH   s(f - touch_s)/P_c fill vs the touch at send (ask for a buy, bid for a sell)   HS = QHS + TCH
  C2    s(P_c - m_s)/P_c   mid at send -> official close, in our trade direction
  B     s(f - P_c)/P_c     fill vs the auction print (verify's line)                 B = HS - C2
  C2a   s(m_5950 - m_s)/P_c, C2b s(P_c - m_5950)/P_c   C2 split at the 15:59:50 mid   C2 = C2a + C2b
  EF    s(f_i - m_fi)/P_c  each fill against the mid at its own transaction time (the prior study's E)
Every identity is asserted per order.

COUNTERFACTUALS (declared grids, nothing selected from them).
  Send time tau in TAU (ET): paper would fill at the touch at tau, so B_tau = s(touch_tau - P_c)/P_c,
  split into QHS_tau and C2_tau. TWAP = the mean of B_tau over the whole minutes 15:52..15:58 (the
  window the runner may use today).
  Limit L = P_e (1 + s k/1e4), k in K (k > 0 pays up to k bp through the decide-time close):
    paper rule (documented): fills at the first quote from submit to 16:00 whose touch is through L
      (ask <= L for a buy), at that touch; else expires unfilled.
    prints rule (a live continuous-market reading): marketable at submit -> the touch at submit;
      otherwise resting at L, filled at L only if a print in (submit, 16:00) trades strictly
      through L ("lenient": at L or through).
    LOC rule (a live closing-auction reading): fills at P_c if P_c is strictly through L ("lenient":
      at L). Impact of our own order on the print is not modelled (n = 0 live auction fills).
  An unfilled order leaves the book one session away from target. Its opportunity cost is
  OC = s(C_{D+1} - C_D)/C_D on SIP daily closes: the session the shift(2) book would have earned.
  It needs D+1's close, so the last day is excluded from it and counted.

STATISTICS. Pooled figures are notional-weighted. "day mean (t)" is the mean over days of each day's
notional-weighted figure, with t = mean / (sd / sqrt(days)): orders on one day share the market's
move, so the order is not the unit of independence.

ADV is the mean of SIP raw daily volume x close over the 63 sessions strictly before the fill day
(asserted: no bar dated on or after D). The closing cross is the primary exchange's condition-6
print (`results/cef/EXEC_CAPACITY_OPEN_CROSS_2026-10-13.md` §1: on a round-lot day that is the whole
cross); a day with no 6 print has no cross size and is counted, never filled in.

Reproduce (every directory outside the repository; the aggregates path may be in it):
  QUANTT_ENV_FILE=<the cef key file> python3 results/cef/exec_cost_2026-11-05/exec_cost.py fetch \\
      --records <private copies> --cache-dir <outside the repo>
  python3 results/cef/exec_cost_2026-11-05/exec_cost.py analyse --records <same> --cache-dir <same> \\
      --private-dir <outside the repo> --c4-design-turns 51.2 \\
      --verify-csv results/report/data/live/cef/verify.csv \\
      --aggregates results/cef/exec_cost_2026-11-05/aggregates_2026-11-05.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from quantt.broker import alpaca_probe as ap  # noqa: E402  (the key loader and a requests session only)
from scripts.cef.live_attribution import _refuse_data_dir, _refuse_git_visible  # noqa: E402

NY, UTC = ZoneInfo("America/New_York"), dt.timezone.utc
DATA_API = "https://data.alpaca.markets"
DATA_PATHS = ("/v2/stocks/quotes", "/v2/stocks/trades", "/v2/stocks/auctions", "/v2/stocks/bars",
              "/v2/stocks/meta/exchanges")
SIGN = {"buy": 1, "sell": -1, "sell_short": -1}
WINDOW = (dt.time(15, 30), dt.time(16, 0, 30))          # quotes and trades fetched per day (ET)
CLOSE = dt.time(16, 0)                                    # asserted against every plan's send window
SEND_WINDOW = (dt.time(15, 52), dt.time(15, 58))          # the runner's [8, 2] minutes before the close
TAU = ["15:50:00", "15:51:00", "15:52:00", "15:53:00", "15:54:00", "15:55:00", "15:56:00", "15:57:00",
       "15:58:00", "15:59:00", "15:59:30", "15:59:50"]
TWAP_TAU = ["15:52:00", "15:53:00", "15:54:00", "15:55:00", "15:56:00", "15:57:00", "15:58:00"]
K = [-50, -25, -10, 0, 10, 25, 50, 100]
PTC_CROSS = "15:58:00"                                    # post-then-cross: the remainder crosses here
ADV_N = 63
COMP = ["IS", "OVN", "OVNn", "OVNd", "HS", "QHS", "TCH", "C2", "C2a", "C2b", "B", "EF"]
CACHE_NAMES = ["bars.json", "exchanges.json"]


class StudyError(RuntimeError):
    pass


# ------------------------------------------------------------------ records (private copies)

def read_records(root: Path) -> tuple[pd.DataFrame, dict]:
    """One row per planned order on every day with an orders.jsonl, both books.

    A planned order with no submit is 'skipped' (send.json says why). The method is 'cls' when every
    submit was time_in_force cls, 'late_market' when the plan says so and every submit was a market day
    order; anything else raises.
    """
    rows, days = [], {}
    for book in ("cef", "c4"):
        bdir = root / book
        if not bdir.is_dir():
            raise StudyError(f"{bdir} is missing")
        for d in sorted(p for p in bdir.iterdir() if p.is_dir()):
            if not (d / "orders.jsonl").exists():
                continue
            if not (d / "plan.json").exists():
                raise StudyError(f"{d}: orders.jsonl without plan.json")
            plan = json.loads((d / "plan.json").read_text())
            ev = [json.loads(x) for x in (d / "orders.jsonl").read_text().splitlines() if x.strip()]
            sub = {e["client_order_id"]: e for e in ev if e["event"] == "submit"}
            fin = {e["client_order_id"]: e for e in ev if e["event"] == "final"}
            tifs = {e["time_in_force"] for e in sub.values()}
            types = {e["type"] for e in sub.values()}
            if tifs == {"cls"} and types == {"market"}:
                method = "cls"
            elif plan.get("execution") == "late_market" and tifs == {"day"} and types == {"market"}:
                method = "late_market"
                lo, hi = (pd.Timestamp(x).tz_convert(NY).time() for x in plan["send_window"])
                if (lo, hi) != SEND_WINDOW:
                    raise StudyError(f"{book} {d.name}: send window {lo}-{hi}, not {SEND_WINDOW}; "
                                     "this script assumes a 16:00 close")
            else:
                raise StudyError(f"{book} {d.name}: unrecognised method tif={tifs} type={types} "
                                 f"execution={plan.get('execution')}")
            send = json.loads((d / "send.json").read_text()) if (d / "send.json").exists() else {}
            skipped = {s.split(":")[0]: s for s in send.get("skipped", [])}
            rec = json.loads((d / "reconcile.json").read_text()) if (d / "reconcile.json").exists() else {}
            days[(book, d.name)] = dict(method=method, equity=float(plan["equity"]),
                                        rec_fills=rec.get("fills"), rec_prints=(rec.get("auction_prints_d")
                                                                                or {}).get("prices"))
            for o in plan["orders"]:
                cid = o["client_order_id"]
                s = sub.get(cid)
                # The send may re-fit quantities to buying power (send.json bp_scale_at_send, since
                # 2026-10-13), so the sent qty can differ from the plan's; symbol and side cannot.
                if s is not None and (s["symbol"], s["side"]) != (o["symbol"], o["side"]):
                    raise StudyError(f"{cid}: submit differs from the plan in symbol or side")
                f = fin.get(cid)
                rows.append(dict(
                    book=book, date=d.name, method=method, cid=cid, symbol=o["symbol"], side=o["side"],
                    s=SIGN[o["side"]], qty=int(s["qty"]) if s else int(o["qty"]), planned_qty=int(o["qty"]),
                    est_price=float(o["est_price"]),
                    current=int(o["current"]), target=int(o["target"]),
                    submitted=s is not None, skipped_reason=skipped.get(cid),
                    t_submit=pd.Timestamp(s["at"]).tz_convert(UTC) if s else pd.NaT,
                    final_status=f.get("status") if f else None,
                    final_filled=int(f["filled"]) if f and f.get("filled") is not None else None,
                    final_avg=float(f["filled_avg_price"]) if f and f.get("filled_avg_price") else None))
    O = pd.DataFrame(rows)
    if O.duplicated(["book", "date", "symbol"]).any():
        raise StudyError("two planned orders for one symbol on one day: the per-(symbol, side) join "
                         "below assumes one")
    unsent = O[~O.submitted & O.skipped_reason.isna()]
    if len(unsent):
        raise StudyError(f"planned but neither submitted nor skipped: {unsent.cid.tolist()}")
    O["kind"] = np.select(
        [(O.s > 0) & (O.current < 0), (O.s > 0), (O.s < 0) & (O.current > 0) & (O.target >= 0),
         (O.s < 0) & (O.current <= 0)],
        ["buy to cover", "buy long", "sell long", "sell short (open or add)"], "flip")
    if (O.kind == "flip").any():
        raise StudyError(f"an order crosses zero: {O[O.kind == 'flip'].cid.tolist()}")
    return O, days


def fills_for(book, date, days, cache: Path) -> list[dict]:
    """Per-fill rows for a day: reconcile.json's FILL activities, else the fetched FILL activities."""
    rf = days[(book, date)]["rec_fills"]
    if rf is None:
        p = cache / f"private_fills_{book}_{date}.json"
        if not p.exists():
            raise StudyError(f"{book} {date}: no reconcile fills and no fetched FILL activities ({p})")
        rf = json.loads(p.read_text())
    out = []
    for f in rf:
        if f.get("activity_type", "FILL") != "FILL":
            raise StudyError(f"{book} {date}: non-FILL activity in the fills")
        out.append(dict(symbol=f["symbol"], side="buy" if f["side"] == "buy" else "sell",
                        qty=int(float(f["qty"])), px=float(f["price"]),
                        t=pd.Timestamp(f["transaction_time"]).tz_convert(UTC)))
    return out


# ------------------------------------------------------------------ network (fetch only)

def _session():
    envf = os.environ.get("QUANTT_ENV_FILE")
    if not envf:
        raise SystemExit("QUANTT_ENV_FILE is not set: name the cef key file (there is no default)")
    k, s = ap.load_credentials("cef", ap.read_env_file(Path(envf)))
    return ap._session(k, s)


def dget(sess, path, params):
    if path not in DATA_PATHS:
        raise StudyError(f"refusing data path {path}")
    for attempt in range(6):
        r = sess.get(DATA_API + path, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(2 + 3 * attempt)
            continue
        if r.status_code != 200:
            raise StudyError(f"GET {path} -> {r.status_code}: {r.text[:200]}")
        return r.json()
    raise StudyError(f"GET {path}: still 429 after retries")


def paged(sess, path, params, key):
    out, tok = {}, None
    while True:
        p = dict(params, **({"page_token": tok} if tok else {}))
        j = dget(sess, path, p)
        for sym, v in (j.get(key) or {}).items():
            out.setdefault(sym, []).extend(v)
        nt = j.get("next_page_token")
        if not nt:
            return out
        if nt == tok:
            raise StudyError(f"{path}: page token did not advance")
        tok = nt


def et_iso(date: str, t: dt.time) -> str:
    return dt.datetime.combine(dt.date.fromisoformat(date), t, NY).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def symbols_by_day(O: pd.DataFrame) -> dict:
    """Every day: the core's frozen universe (spec), the traded names, and C4's traded names (so C4's
    quoted spreads are measured on every session, not only its one traded day)."""
    from scripts.cef.spec import UNIVERSE
    c4 = sorted(O[O.book == "c4"].symbol.unique())
    out = {}
    for d, g in O.groupby("date"):
        out[d] = sorted(set(UNIVERSE) | set(c4) | set(g.symbol))
    return out


def fetch(a) -> int:
    for d in (a.cache_dir,):
        _refuse_data_dir(d)
    O, days = read_records(a.records)
    sbd = symbols_by_day(O)
    names = [f"md_{d}_{k}.json" for d in sbd for k in ("quotes", "trades", "auctions")]
    names += CACHE_NAMES + [f"private_fills_{b}_{d}.json" for (b, d) in days]
    _refuse_git_visible(a.cache_dir, names)
    a.cache_dir.mkdir(parents=True, exist_ok=True)
    sess = _session()
    for d, syms in sbd.items():
        for key, path in (("quotes", "/v2/stocks/quotes"), ("trades", "/v2/stocks/trades")):
            p = a.cache_dir / f"md_{d}_{key}.json"
            if p.exists():
                continue
            got = paged(sess, path, dict(symbols=",".join(syms), start=et_iso(d, WINDOW[0]),
                                         end=et_iso(d, WINDOW[1]), feed="sip", limit=10000), key)
            p.write_text(json.dumps(got))
            print(f"{d} {key}: {sum(len(v) for v in got.values())} rows, {len(got)} symbols")
        p = a.cache_dir / f"md_{d}_auctions.json"
        if not p.exists():
            got = paged(sess, "/v2/stocks/auctions", dict(symbols=",".join(syms), start=et_iso(d, dt.time(0)),
                                                          end=et_iso(d, dt.time(16, 30)), feed="sip",
                                                          limit=10000), "auctions")
            p.write_text(json.dumps(got))
    allsyms = sorted(set().union(*sbd.values()))
    d0 = (pd.Timestamp(min(sbd)) - pd.Timedelta(days=130)).date().isoformat()
    # Only COMPLETE sessions: a daily bar read before today's close is a partial bar, and the
    # opportunity cost reads D+1's close from it (the 2026-11-05 first run read 11-05's bar at 10:3x ET).
    now = pd.Timestamp.now(tz=NY)
    today0 = now.normalize()
    # `end` is inclusive and a daily bar is stamped at 00:00 ET, so stop one second before today's stamp
    last_complete_end = (today0 + pd.Timedelta(hours=16, minutes=30) if now >= today0 + pd.Timedelta(hours=16, minutes=30)
                         else today0 - pd.Timedelta(seconds=1))
    end = min(pd.Timestamp(max(sbd), tz=NY) + pd.Timedelta(days=10), last_complete_end)
    bars = paged(sess, "/v2/stocks/bars", dict(symbols=",".join(allsyms), timeframe="1Day", start=d0,
                                               end=end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                               adjustment="raw", feed="sip", limit=10000), "bars")
    (a.cache_dir / "bars.json").write_text(json.dumps({"fetched_at": now.isoformat(), "bars": bars}))
    ex = dget(sess, "/v2/stocks/meta/exchanges", {})
    (a.cache_dir / "exchanges.json").write_text(json.dumps(ex))
    # FILL activities, only for days whose records carry no fill (account data: cache only)
    for (book, d), info in days.items():
        if info["rec_fills"] is not None:
            continue
        if book != "cef":
            raise StudyError(f"{book} {d}: no fills in the records and only cef keys are loaded")
        p = a.cache_dir / f"private_fills_{book}_{d}.json"
        if p.exists():
            continue
        acts, tok = [], None
        while True:
            q = f"/v2/account/activities/FILL?date={d}&direction=asc&page_size=100"
            r = ap._get(sess, q + (f"&page_token={tok}" if tok else ""))
            acts += r
            if len(r) < 100:
                break
            tok = r[-1]["id"]
        p.write_text(json.dumps(acts))
        print(f"{book} {d}: {len(acts)} FILL activities (private cache)")
    return 0


# ------------------------------------------------------------------ analysis

class Tape:
    """The SIP quotes and trades of one symbol-day, sorted; lookups never fill a gap."""

    def __init__(self, quotes: list, trades: list):
        q = pd.DataFrame(quotes)
        if q.empty:
            raise StudyError("no quotes")
        q["t"] = pd.to_datetime(q.t, utc=True, format="ISO8601")
        q = q.sort_values("t", kind="stable")
        self.n_invalid = int(((q.bp <= 0) | (q.ap <= 0) | (q.ap < q.bp)).sum())
        q = q[(q.bp > 0) & (q.ap > 0) & (q.ap >= q.bp)]
        self.qt = q.t.values.astype("datetime64[ns]").astype(np.int64)
        self.bp, self.ap = q.bp.to_numpy(float), q.ap.to_numpy(float)
        self.bs, self.as_ = q.bs.to_numpy(float), q["as"].to_numpy(float)
        t = pd.DataFrame(trades) if trades else pd.DataFrame(columns=["t", "p", "s"])
        t["t"] = pd.to_datetime(t.t, utc=True, format="ISO8601")
        self.tt = t.t.values.astype("datetime64[ns]").astype(np.int64)
        self.tp = t.p.to_numpy(float)

    def at(self, ts: pd.Timestamp, what: str):
        i = np.searchsorted(self.qt, ts.value, side="right") - 1
        if i < 0:
            raise StudyError(f"no valid quote at or before {ts} ({what})")
        return i

    def quote(self, ts, what):
        i = self.at(ts, what)
        return self.bp[i], self.ap[i], self.bs[i], self.as_[i], (ts.value - self.qt[i]) / 1e9

    def first_through(self, t0: pd.Timestamp, t1: pd.Timestamp, s: int, L: float):
        """Paper rule: the prevailing quote at t0, then each later quote before t1; the first whose touch
        is at or through L. Returns the touch price or None."""
        i0 = self.at(t0, "limit start")
        j1 = np.searchsorted(self.qt, t1.value, side="left")
        touch = self.ap[i0:j1] if s > 0 else self.bp[i0:j1]
        hit = np.nonzero(touch <= L)[0] if s > 0 else np.nonzero(touch >= L)[0]
        return float(touch[hit[0]]) if len(hit) else None

    def prints_through(self, t0, t1, s, L):
        m = (self.tt > t0.value) & (self.tt < t1.value)
        p = self.tp[m]
        if not len(p):
            return False, False
        strict = bool((p < L).any()) if s > 0 else bool((p > L).any())
        lenient = bool((p <= L).any()) if s > 0 else bool((p >= L).any())
        return strict, lenient


def et_ts(date: str, hhmmss: str) -> pd.Timestamp:
    return pd.Timestamp(f"{date} {hhmmss}", tz=NY).tz_convert(UTC)


def primary_codes(cache: Path, syms) -> dict:
    """Primary SIP exchange code per symbol: the core's names from the price panel's universe are NYSE
    (asserted against C4's frozen map where both list a name); C4's from its frozen universe file, column
    `exchange`, mapped through /v2/stocks/meta/exchanges by name, as quantt.broker.alpaca does."""
    from quantt.broker.alpaca import ASSET_EXCHANGE_SIP_NAME
    ex = json.loads((cache / "exchanges.json").read_text())
    by_name = {}
    for code, name in ex.items():
        by_name.setdefault(name, []).append(code)
    c4 = pd.read_csv(REPO / "results/cef/c4/c4_universe_frozen_2026-10-14.csv").set_index("ticker")["exchange"]
    from scripts.cef.spec import UNIVERSE
    out = {}
    for s in syms:
        exch = c4.get(s) if s in c4.index else ("NYSE" if s in UNIVERSE else None)
        if exch is None:
            raise StudyError(f"{s}: no listing exchange")
        codes = by_name.get(ASSET_EXCHANGE_SIP_NAME.get(exch, "?"), [])
        if len(codes) != 1:
            raise StudyError(f"{s}: {exch} maps to SIP codes {codes}")
        out[s] = codes[0]
    return out


def groups() -> dict:
    core = pd.read_csv(REPO / "data/cef/cef_universe.csv").set_index("ticker")["grp"].to_dict()
    c4 = pd.read_csv(REPO / "results/cef/c4/c4_universe_frozen_2026-10-14.csv").set_index("ticker")["family"]
    return {"cef": core, "c4": c4.to_dict()}


def build(O: pd.DataFrame, days: dict, cache: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    braw = json.loads((cache / "bars.json").read_text())
    fetched = pd.Timestamp(braw["fetched_at"]).tz_convert(NY)
    bars_raw = braw["bars"]
    # refuse a partial bar: a bar dated on the fetch day counts only if fetched after 16:30 ET
    fday = fetched.date().isoformat()
    for s, v in bars_raw.items():
        for b in v:
            bd = pd.Timestamp(b["t"]).tz_convert(NY).date().isoformat()
            if bd > fday or (bd == fday and fetched.time() < dt.time(16, 30)):
                raise StudyError(f"{s} {bd}: daily bar may be partial (fetched {fetched})")
    bars = {s: pd.DataFrame(v).assign(d=lambda x: pd.to_datetime(x.t).dt.tz_convert(NY).dt.date.astype(str))
            .set_index("d") for s, v in bars_raw.items()}
    from scripts.cef.spec import UNIVERSE
    cal = sorted(set().union(*(set(bars[s].index) for s in UNIVERSE)))
    nxt = {d: cal[i + 1] for i, d in enumerate(cal[:-1])}
    prv = {d: cal[i - 1] for i, d in enumerate(cal) if i}
    grp = groups()
    codes = primary_codes(cache, sorted(set(O.symbol)))
    tapes, auctions, meta = {}, {}, {"invalid_quotes_dropped": 0, "print_checks": 0, "print_mismatch": 0}

    def tape(d, s):
        if (d, s) not in tapes:
            Q = json.loads((cache / f"md_{d}_quotes.json").read_text())
            T = json.loads((cache / f"md_{d}_trades.json").read_text())
            if s not in Q:
                raise StudyError(f"{d} {s}: no quotes in the fetched window")
            tapes[(d, s)] = Tape(Q[s], T.get(s, []))
            meta["invalid_quotes_dropped"] += tapes[(d, s)].n_invalid
        return tapes[(d, s)]

    def auction(d, s):
        if d not in auctions:
            auctions[d] = json.loads((cache / f"md_{d}_auctions.json").read_text())
        rows = [p for day in auctions[d].get(s, []) for p in (day.get("c") or []) if p["x"] == codes[s]]
        m = {float(p["p"]) for p in rows if p["c"] == "M"}
        six = [float(p["s"]) for p in rows if p["c"] == "6"]
        if len(m) != 1:
            raise StudyError(f"{d} {s}: primary M prints {m}")
        if len(six) > 1:
            raise StudyError(f"{d} {s}: {len(six)} primary 6 prints")
        return m.pop(), (six[0] if six else np.nan)

    rows, frows = [], []
    for (book, d), g in O[O.submitted].groupby(["book", "date"]):
        info = days[(book, d)]
        F = pd.DataFrame(fills_for(book, d, days, cache))
        prints = info["rec_prints"] or {}
        for _, o in g.iterrows():
            f = F[(F.symbol == o.symbol) & (F.side == o.side)] if len(F) else F
            r = dict(o)
            r["grp"] = grp[book].get(o.symbol)
            if r["grp"] is None:
                raise StudyError(f"{book} {o.symbol}: no group")
            Pm, cross = auction(d, o.symbol)
            if o.symbol in prints:
                meta["print_checks"] += 1
                if abs(prints[o.symbol] - Pm) > 1e-9:
                    meta["print_mismatch"] += 1
                Pc, r["close_source"] = float(prints[o.symbol]), "verify"
            else:
                Pc, r["close_source"] = Pm, "fetched M"
            r.update(Pc=Pc, cross_shares=cross, filled=int(f.qty.sum()) if len(f) else 0)
            if pd.notna(o.final_filled) and int(o.final_filled) != r["filled"]:
                raise StudyError(f"{o.cid}: final filled {o.final_filled} vs fills {r['filled']}")
            b = bars.get(o.symbol)
            if b is None:
                raise StudyError(f"{o.symbol}: no daily bars")
            hist = b[b.index < d].tail(ADV_N)
            if len(hist) < ADV_N or hist.index.max() >= d:
                raise StudyError(f"{d} {o.symbol}: {len(hist)} bars before D for ADV")
            r["adv_usd"] = float((hist.v * hist.c).mean())
            r["C_D"] = float(b.loc[d, "c"]) if d in b.index else np.nan
            r["O_D"] = float(b.loc[d, "o"]) if d in b.index else np.nan
            r["C_prev"] = float(b.loc[prv[d], "c"]) if prv.get(d) in b.index else np.nan
            dn = nxt.get(d)
            r["C_next"] = float(b.loc[dn, "c"]) if dn is not None and dn in b.index else np.nan
            if r["filled"] == 0:
                rows.append(r)
                continue
            r["f"] = float((f.qty * f.px).sum() / f.qty.sum())
            if pd.notna(o.final_avg) and abs(o.final_avg - r["f"]) > 5e-5:
                raise StudyError(f"{o.cid}: final avg {o.final_avg} vs fill vwap {r['f']}")
            r["n_fills"] = len(f)
            r["t_fill_first"], r["t_fill_last"] = f.t.min(), f.t.max()
            r["fill_secs_after_submit"] = (f.t.max() - o.t_submit).total_seconds() if o.method == "late_market" else np.nan
            if o.method != "late_market":
                rows.append(r)
                continue
            T = tape(d, o.symbol)
            bs_, as_, bsz, asz, age = T.quote(o.t_submit, "submit")
            r.update(b_s=bs_, a_s=as_, m_s=(bs_ + as_) / 2, touch_size_s=asz if o.s > 0 else bsz, q_age_s=age)
            b9, a9, *_ = T.quote(et_ts(d, "15:59:50"), "15:59:50")
            r["m_5950"] = (b9 + a9) / 2
            ef = 0.0
            for _, x in f.iterrows():
                bf, af, *_ = T.quote(x.t, "fill")
                ef += o.s * (x.px - (bf + af) / 2) * x.qty
                frows.append(dict(book=book, date=d, symbol=o.symbol, qty=x.qty, px=x.px, bid=bf, ask=af,
                                  at_touch=bool(abs(x.px - (af if o.s > 0 else bf)) < 5e-5)))
            r["EF_usd_raw"] = ef
            for tau in TAU:
                bt, at_, *_ = T.quote(et_ts(d, tau), tau)
                r[f"touch_{tau}"], r[f"mid_{tau}"], r[f"qhs_{tau}"] = (at_ if o.s > 0 else bt), (bt + at_) / 2, (at_ - bt) / 2
            # Post at the passive touch at submit (bid for a buy, ask for a sell); on paper it fills at the
            # first later quote whose touch reaches it, at that touch; any order still open at 15:58:00
            # crosses at the 15:58:00 touch (the current window's end).
            Lp = bs_ if o.s > 0 else as_
            t58 = et_ts(d, PTC_CROSS)
            i0 = np.searchsorted(T.qt, o.t_submit.value, side="right")
            j1 = np.searchsorted(T.qt, t58.value, side="left")
            touch_seq = T.ap[i0:j1] if o.s > 0 else T.bp[i0:j1]
            hit = np.nonzero(touch_seq <= Lp)[0] if o.s > 0 else np.nonzero(touch_seq >= Lp)[0]
            r["ptc_passive_filled"] = bool(len(hit))
            r["ptc_px"] = float(touch_seq[hit[0]]) if len(hit) else r[f"touch_{PTC_CROSS}"]
            t_end = et_ts(d, "16:00:00")
            for k in K:
                L = o.est_price * (1 + o.s * k / 1e4)
                r[f"paper_fill_{k}"] = T.first_through(o.t_submit, t_end, o.s, L)
                touch0 = as_ if o.s > 0 else bs_
                marketable = (touch0 <= L) if o.s > 0 else (touch0 >= L)
                st, le = T.prints_through(o.t_submit, t_end, o.s, L)
                r[f"prints_px_{k}"] = touch0 if marketable else L
                r[f"prints_strict_{k}"], r[f"prints_lenient_{k}"] = bool(marketable or st), bool(marketable or le)
                r[f"loc_strict_{k}"] = bool(Pc < L) if o.s > 0 else bool(Pc > L)
                r[f"loc_lenient_{k}"] = bool(Pc <= L) if o.s > 0 else bool(Pc >= L)
                r[f"L_{k}"] = L
            rows.append(r)
    X = pd.DataFrame(rows)
    FR = pd.DataFrame(frows)
    meta["calendar"] = {"first": cal[0], "last": cal[-1]}
    meta["_cal"] = cal
    return X, FR, meta


def components(X: pd.DataFrame) -> pd.DataFrame:
    """Per-order components in bp of P_c and in USD on notional qty_filled x P_c; identities asserted."""
    L = X[(X.method == "late_market") & (X.filled > 0)].copy()
    s, Pc = L.s, L.Pc
    L["notional"] = L.filled * Pc
    L["traded_usd"] = L.filled * L.f
    touch = np.where(s > 0, L.a_s, L.b_s)
    bp = lambda x: x / Pc * 1e4
    L["IS"] = bp(s * (L.f - L.est_price))
    L["OVN"] = bp(s * (L.m_s - L.est_price))
    L["OVNn"] = bp(s * (L.O_D - L.est_price))      # decide-time close -> the day's open (SIP daily bar)
    L["OVNd"] = bp(s * (L.m_s - L.O_D))            # the day's open -> mid at send
    L["HS"] = bp(s * (L.f - L.m_s))
    L["QHS"] = bp((L.a_s - L.b_s) / 2)
    L["TCH"] = bp(s * (L.f - touch))
    L["C2"] = bp(s * (Pc - L.m_s))
    L["C2a"] = bp(s * (L.m_5950 - L.m_s))
    L["C2b"] = bp(s * (Pc - L.m_5950))
    L["B"] = bp(s * (L.f - Pc))
    L["EF"] = L.EF_usd_raw / L.filled / Pc * 1e4
    if L.ptc_passive_filled.isna().any():
        raise StudyError("post-then-cross flag missing on a late_market order")
    L["ptc_passive_filled"] = L.ptc_passive_filled.astype(bool)
    L["B_PTC"] = bp(s * (L.ptc_px.astype(float) - Pc))
    for lhs, rhs in (("OVN", L.OVNn + L.OVNd), ("IS", L.OVN + L.HS), ("HS", L.QHS + L.TCH), ("B", L.HS - L.C2), ("C2", L.C2a + L.C2b)):
        if not np.allclose(L[lhs], rhs, atol=1e-9):
            raise StudyError(f"identity {lhs} failed")
    for c in COMP:
        L[c + "_usd"] = L[c] / 1e4 * L.notional
    for tau in TAU:
        L[f"B_{tau}"] = bp(s * (L[f"touch_{tau}"] - Pc))
        L[f"QHS_{tau}"] = bp(L[f"qhs_{tau}"])
        L[f"C2_{tau}"] = bp(s * (Pc - L[f"mid_{tau}"]))
    L["B_TWAP"] = L[[f"B_{t}" for t in TWAP_TAU]].mean(axis=1)
    L["QHS_TWAP"] = L[[f"QHS_{t}" for t in TWAP_TAU]].mean(axis=1)
    L["OC"] = s * (L.C_next - L.C_D) / L.C_D * 1e4
    L["adv_part"] = L.traded_usd / L.adv_usd
    L["cross_part"] = L.filled / L.cross_shares
    L["tick_bp"] = 0.01 / Pc * 1e4
    L["spread_ticks"] = ((L.a_s - L.b_s) / 0.01).round(6)
    return L


def tstat(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 3 or x.std(ddof=1) == 0:
        return None
    return round(float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x)))), 2)


def wavg(g, col, w="notional"):
    m = np.isfinite(g[col]) & np.isfinite(g[w])
    return float((g.loc[m, col] * g.loc[m, w]).sum() / g.loc[m, w].sum()) if m.any() and g.loc[m, w].sum() > 0 else None


def r2(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), 2)


def agg(g: pd.DataFrame, cols=("B", "HS", "QHS", "TCH", "C2", "C2a", "C2b", "IS", "OVN", "OVNn", "OVNd", "EF"),
        tcols=("B", "HS", "C2", "C2a", "C2b", "OVN", "OVNn", "OVNd")) -> dict:
    d = {"orders": int(len(g)), "days": int(g.date.nunique()), "notional_usd": round(float(g.notional.sum()), 2)}
    for c in cols:
        d[c + "_bp"] = r2(wavg(g, c))
    for c in tcols:
        by_day = g.groupby("date").apply(lambda x, c=c: wavg(x, c), include_groups=False).dropna()
        d[c + "_day_mean_bp"], d[c + "_day_t"] = r2(by_day.mean() if len(by_day) else None), tstat(by_day)
    d["B_order_median_bp"] = r2(float(g.B.median()))
    return d


def tables(L: pd.DataFrame) -> dict:
    core = L[L.book == "cef"]
    T = {"all (core, late_market)": agg(core)}
    if (L.book == "c4").any():
        T["c4, 2026-11-04 (opening build)"] = agg(L[L.book == "c4"])
    T["by side (core)"] = {k: agg(g) for k, g in core.groupby(np.where(core.s > 0, "buy", "sell"))}
    T["by kind (core)"] = {k: agg(g) for k, g in core.groupby("kind")}
    T["by group (core)"] = {k: agg(g) for k, g in core.groupby("grp")}
    T["muni vs taxable (core)"] = {k: agg(g) for k, g in core.groupby(np.where(core.grp == "muni", "muni", "taxable"))}
    T["by date (core)"] = {k: agg(g) for k, g in core.groupby("date")}

    def terciles(col, label):
        q = core[col].quantile([1 / 3, 2 / 3]).to_numpy()
        cut = pd.cut(core[col], [-np.inf, q[0], q[1], np.inf], labels=[f"low (<= {q[0]:.4g})",
                     f"mid ({q[0]:.4g}, {q[1]:.4g}]", f"high (> {q[1]:.4g})"])
        T[f"by {label} tercile (core)"] = {str(k): agg(g) for k, g in core.groupby(cut, observed=True)}

    terciles("QHS", "quoted half-spread at send (bp)")
    terciles("Pc", "share price ($)")
    terciles("adv_part", "order as a fraction of 63-session $ADV")
    terciles("notional", "order notional ($)")
    cp = core[np.isfinite(core.cross_part)]
    q = cp.cross_part.quantile([1 / 3, 2 / 3]).to_numpy()
    cut = pd.cut(cp.cross_part, [-np.inf, q[0], q[1], np.inf],
                 labels=[f"low (<= {q[0]:.4g})", f"mid ({q[0]:.4g}, {q[1]:.4g}]", f"high (> {q[1]:.4g})"])
    T["by share of the day's closing cross tercile (core)"] = {str(k): agg(g) for k, g in cp.groupby(cut, observed=True)}
    T["by spread in ticks at send (core)"] = {f"{int(k)} tick(s)" if k < 3 else ">= 3 ticks": agg(g)
                                             for k, g in core.groupby(np.minimum(core.spread_ticks.round(), 3))}
    T["by period (core; split after 2026-10-12, as the prior study)"] = {
        k: agg(g) for k, g in core.groupby(np.where(core.date <= "2026-10-12", "to 10-12", "10-13 on"))}
    return T


def regressions(L: pd.DataFrame) -> dict:
    """HS on QHS (does the paid cost track the quoted spread?), and B on QHS with the day's mean removed
    (day fixed effect), both order-level OLS with day-clustered standard errors."""
    core = L[L.book == "cef"].copy()
    out = {}
    for y, demean in (("HS", False), ("B", True)):
        d = core[[y, "QHS", "date"]].dropna().copy()
        if demean:
            for c in (y, "QHS"):
                d[c] = d[c] - d.groupby("date")[c].transform("mean")
        Xm = np.column_stack([np.ones(len(d)), d.QHS.to_numpy()])
        yv = d[y].to_numpy()
        beta, *_ = np.linalg.lstsq(Xm, yv, rcond=None)
        e = yv - Xm @ beta
        bread = np.linalg.inv(Xm.T @ Xm)
        meat = np.zeros((2, 2))
        for _, idx in d.groupby("date").indices.items():
            sc = Xm[idx].T @ e[idx]
            meat += np.outer(sc, sc)
        G = d.date.nunique()
        V = bread @ meat @ bread * G / (G - 1)
        out[f"{y} on QHS{' (day-demeaned)' if demean else ''}"] = {
            "orders": len(d), "days": G, "slope": round(float(beta[1]), 3),
            "slope_t_day_clustered": round(float(beta[1] / math.sqrt(V[1, 1])), 2),
            "intercept_bp": round(float(beta[0]), 2)}
    sp = core[["B", "HS", "QHS", "adv_part", "Pc", "notional", "cross_part"]].corr(method="spearman")
    out["spearman (core orders)"] = {f"{a} vs {b}": round(float(sp.loc[a, b]), 3) for a in ("B", "HS")
                                     for b in ("QHS", "adv_part", "Pc", "notional", "cross_part")}
    return out


def timing(L: pd.DataFrame) -> dict:
    out = {}
    for name, g in (("core", L[L.book == "cef"]), ("c4", L[L.book == "c4"])):
        if g.empty:
            continue
        rows = {}
        actual_day = g.groupby("date").apply(lambda x: wavg(x, "B"), include_groups=False)
        for col in [f"B_{t}" for t in TAU] + ["B_TWAP"]:
            day = g.groupby("date").apply(lambda x: wavg(x, col), include_groups=False)
            diff = (day - actual_day).dropna()
            ref = g.groupby("date").apply(lambda x: wavg(x, "B_15:52:00"), include_groups=False)
            d52 = (day - ref).dropna()
            tau = col[2:]
            rows[tau] = {"B_bp": r2(wavg(g, col)),
                         "QHS_bp": r2(wavg(g, f"QHS_{tau}") if tau != "TWAP" else wavg(g, "QHS_TWAP")),
                         "C2_bp": r2(wavg(g, f"C2_{tau}")) if tau != "TWAP" else None,
                         "minus_actual_day_mean_bp": r2(diff.mean()), "minus_actual_day_t": tstat(diff),
                         "minus_1552_day_mean_bp": r2(d52.mean()), "minus_1552_day_t": tstat(d52),
                         "B_day_sd_bp": r2(day.std(ddof=1)) if len(day) > 2 else None}
        ptc_day = g.groupby("date").apply(lambda x: wavg(x, "B_PTC"), include_groups=False)
        dptc = (ptc_day - actual_day).dropna()
        rows[f"post at the passive touch, cross the rest at {PTC_CROSS}"] = {
            "B_bp": r2(wavg(g, "B_PTC")), "passive leg fill rate (orders)": round(float(g.ptc_passive_filled.mean()), 3),
            "passive leg fill rate (notional)": round(float(g.notional[g.ptc_passive_filled].sum() / g.notional.sum()), 3),
            "B of passive fills, bp": r2(wavg(g[g.ptc_passive_filled], "B_PTC")) if g.ptc_passive_filled.any() else None,
            "B of crossed remainder, bp": r2(wavg(g[~g.ptc_passive_filled], "B_PTC")) if (~g.ptc_passive_filled).any() else None,
            "minus_actual_day_mean_bp": r2(dptc.mean()), "minus_actual_day_t": tstat(dptc),
            "B_day_sd_bp": r2(ptc_day.std(ddof=1)) if len(ptc_day) > 2 else None}
        rows["actual"] = {"B_bp": r2(wavg(g, "B")), "QHS_bp": r2(wavg(g, "QHS")), "C2_bp": r2(wavg(g, "C2")),
                          "B_day_sd_bp": r2(actual_day.std(ddof=1)) if len(actual_day) > 2 else None}
        out[name] = {"orders": len(g), "days": int(g.date.nunique()), "by_send_time": rows}
    return out


def spread_profile(X: pd.DataFrame, O: pd.DataFrame, cache: Path, days_core: list) -> dict:
    """Quoted half-spread (bp of the mid) at each tau, over EVERY name-day of the core's universe and of
    C4's traded names on every core session: market data, not our orders, so a larger sample."""
    from scripts.cef.spec import UNIVERSE
    c4 = sorted(O[O.book == "c4"].symbol.unique())
    out = {}
    for label, syms in (("core universe", list(UNIVERSE)), ("c4 traded names", c4)):
        acc = {t: [] for t in TAU}
        per_name = {s: [] for s in syms}
        for d in days_core:
            Q = json.loads((cache / f"md_{d}_quotes.json").read_text())
            for s in syms:
                if s not in Q:
                    raise StudyError(f"{d} {s}: no quotes for the spread profile")
                T = Tape(Q[s], [])
                for t in TAU:
                    b, a, *_ = T.quote(et_ts(d, t), t)
                    acc[t].append((a - b) / 2 / ((a + b) / 2) * 1e4)
                    if t == "15:52:00":
                        per_name[s].append(acc[t][-1])
        nm = np.array([np.mean(v) for v in per_name.values()])
        out[label] = {"name_days": len(acc[TAU[0]]), "names": len(syms), "sessions": len(days_core),
                      "per-name mean half-spread at 15:52, across names: min / p25 / median / p75 / max (bp)":
                          [r2(float(x)) for x in np.percentile(nm, [0, 25, 50, 75, 100])],
                      "half_spread_bp_mean": {t: r2(np.mean(v)) for t, v in acc.items()},
                      "half_spread_bp_median": {t: r2(np.median(v)) for t, v in acc.items()}}
    return out


def limits(L: pd.DataFrame) -> dict:
    out = {}
    for name, g in (("core", L[L.book == "cef"]), ("c4", L[L.book == "c4"])):
        if g.empty:
            continue
        rows = {}
        has_next = np.isfinite(g.OC)
        for k in K:
            pf = g[f"paper_fill_{k}"].notna()
            Bk = np.where(pf, g.s * (g[f"paper_fill_{k}"].astype(float) - g.Pc) / g.Pc * 1e4, np.nan)
            ps = g[f"prints_strict_{k}"].astype(bool)
            Bp = g.s * (g[f"prints_px_{k}"] - g.Pc) / g.Pc * 1e4
            ls = g[f"loc_strict_{k}"].astype(bool)
            n = g.notional
            # cost-equivalent on days with D+1: filled orders at their B, unfilled at OC
            ce = lambda filled, Bv: (float(((np.where(filled, Bv, g.OC)) * n)[has_next].sum() / n[has_next].sum())
                                     if has_next.any() else None)
            rows[str(k)] = {
                "paper: fill rate (orders)": round(float(pf.mean()), 3),
                "paper: fill rate (notional)": round(float(n[pf].sum() / n.sum()), 3),
                "paper: B of filled, bp": r2(float((Bk[pf] * n[pf]).sum() / n[pf].sum())) if pf.any() else None,
                "paper: OC of unfilled, bp": r2(float((g.OC[~pf & has_next] * n[~pf & has_next]).sum() / n[~pf & has_next].sum())) if (~pf & has_next).any() else None,
                "paper: cost-equivalent (filled B, unfilled OC), bp": r2(ce(pf.to_numpy(), Bk)),
                "prints strict: fill rate (notional)": round(float(n[ps].sum() / n.sum()), 3),
                "prints lenient: fill rate (notional)": round(float(n[g[f'prints_lenient_{k}'].astype(bool)].sum() / n.sum()), 3),
                "prints strict: B of filled, bp": r2(float((Bp[ps] * n[ps]).sum() / n[ps].sum())) if ps.any() else None,
                "LOC strict: fill rate (notional)": round(float(n[ls].sum() / n.sum()), 3),
                "LOC lenient: fill rate (notional)": round(float(n[g[f'loc_lenient_{k}'].astype(bool)].sum() / n.sum()), 3),
                "LOC strict: OC of unfilled, bp": r2(float((g.OC[~ls & has_next] * n[~ls & has_next]).sum() / n[~ls & has_next].sum())) if (~ls & has_next).any() else None,
            }
        if has_next.any():
            oc_day = g[has_next].groupby("date").apply(lambda x: wavg(x, "OC"), include_groups=False)
            rows["market (actual)"] = {
                "B, bp": r2(wavg(g, "B")),
                "B on the days with D+1, bp": r2(wavg(g[has_next], "B")),
                "OC of all orders (the session a missed order would forgo), bp": r2(wavg(g[has_next], "OC")),
                "OC day mean (t)": [r2(float(oc_day.mean())), tstat(oc_day)]}
        else:
            rows["market (actual)"] = {"B, bp": r2(wavg(g, "B")),
                                       "OC": "not measurable: no completed session after this book's days"}
        out[name] = {"orders": len(g), "orders_with_next_close": int(has_next.sum()),
                     "days_with_next_close": int(g[has_next].date.nunique()), "by_k_bp": rows}
    return out


def turnover(X: pd.DataFrame, days: dict, cal: list) -> dict:
    """Traded $ / decide-time equity per session, summed, x 252 / sessions in the window (every NYSE
    session in it, traded or not: a missed or refused session is part of the calendar)."""
    out = {}
    core = X[(X.book == "cef") & (X.filled > 0)]
    traded = core.assign(usd=core.filled * core.f).groupby("date").usd.sum()
    for label, lo in (("2026-09-29 on (includes the build from flat)", "2026-09-29"),
                      ("2026-10-07 on (after the build and the missed 10-02..10-06)", "2026-10-07")):
        sess = [d for d in cal if lo <= d <= max(traded.index)]
        eq = pd.Series({d: days[("cef", d)]["equity"] for (b, d) in days if b == "cef" and d >= lo})
        t = traded[traded.index >= lo]
        out[label] = {"sessions": len(sess), "sessions_traded": int(len(t)), "traded_usd": round(float(t.sum()), 2),
                      "mean_decide_equity_usd": round(float(eq.mean()), 2),
                      "turns_per_year": round(float((t / eq.reindex(t.index)).sum() * 252 / len(sess)), 2)}
    return out


def dollars(L, T, turns, c4_turns, c4_equity) -> dict:
    out = {}
    core = L[L.book == "cef"]
    bq = {"paper B (fill vs auction), measured": wavg(core, "B"), "of which the quoted half-spread at send (QHS)": wavg(core, "QHS"),
          "grid 5bp": 5.0, "grid 15bp": 15.0, "grid 30bp": 30.0}
    for lab, tv in turns.items():
        out[f"core, {lab}"] = {k: {"bp": r2(v), "pct_nav_per_year": round(v * tv["turns_per_year"] / 100, 3),
                                   "usd_per_year": round(v / 1e4 * tv["turns_per_year"] * tv["mean_decide_equity_usd"], 0)}
                               for k, v in bq.items()}
    c4 = L[L.book == "c4"]
    c4b = {"c4 paper B, 2026-11-04 (one opening-build day)": wavg(c4, "B") if len(c4) else None,
           "c4 QHS at send, 2026-11-04": wavg(c4, "QHS") if len(c4) else None,
           "core paper B, measured (applied to C4)": wavg(core, "B"),
           "grid 5bp": 5.0, "grid 15bp": 15.0, "grid 30bp": 30.0}
    out[f"c4 at its design turnover {c4_turns} turns/yr (passed in; not measured here)"] = {
        k: {"bp": r2(v), "pct_nav_per_year": round(v * c4_turns / 100, 3),
            "usd_per_year": round(v / 1e4 * c4_turns * c4_equity, 0)} for k, v in c4b.items() if v is not None}
    return out


def analyse(a) -> int:
    _refuse_data_dir(a.private_dir)
    _refuse_git_visible(a.private_dir, ["orders.csv", "fills.csv", "by_name.csv", "spread_by_name.csv"])
    _refuse_data_dir(a.aggregates)
    O, days = read_records(a.records)
    X, FR, meta = build(O, days, a.cache_dir)
    cal = meta.pop("_cal")
    L = components(X)
    core_days = sorted(L[L.book == "cef"].date.unique())
    turns = turnover(X, days, cal)
    c4_equity = float(np.mean([v["equity"] for (b, d), v in days.items() if b == "c4"]))
    fills_meta = {
        "late_market fills, both books": int(len(FR)),
        "late_market fills by book": {b: int((FR.book == b).sum()) for b in ("cef", "c4")},
        "orders with more than one fill (share), by book": {
            b: round(float((L[L.book == b].n_fills > 1).mean()), 3) for b in ("cef", "c4") if (L.book == b).any()},
        "fills at the touch at their own time (share), both books": round(float(FR.at_touch.mean()), 3),
        "seconds from submit to last fill: median, p90, max": [r2(L.fill_secs_after_submit.median()),
                                                               r2(L.fill_secs_after_submit.quantile(.9)),
                                                               r2(L.fill_secs_after_submit.max())],
        "quote age at submit (s): median, max": [r2(L.q_age_s.median()), r2(L.q_age_s.max())],
        # time of day, not the first and last timestamps (the prior study's draft made that mistake)
        "submit time of day ET: earliest, latest": [min(t.tz_convert(NY).time() for t in L.t_submit).strftime("%H:%M:%S"),
                                                    max(t.tz_convert(NY).time() for t in L.t_submit).strftime("%H:%M:%S")],
        "last fill time of day ET: latest": max(t.tz_convert(NY).time() for t in L.t_fill_last).strftime("%H:%M:%S"),
        "order larger than the displayed touch size at send, share of orders [U: size units]": round(float((L.filled > L.touch_size_s).mean()), 3),
    }
    hs_by_name = (L[L.book == "cef"].HS_usd.groupby(L[L.book == "cef"].symbol).sum()).sort_values(ascending=False)
    fills_meta["core: share of spread dollars (HS) in the three names carrying most of it"] = round(
        float(hs_by_name.iloc[:3].sum() / hs_by_name.sum()), 3)
    for b in ("cef", "c4"):
        g = L[L.book == b]
        if len(g):
            fills_meta[f"{b}: paid vs mid at send per share traded, USD (HS in dollars / shares)"] = round(
                float((g.s * (g.f - g.m_s) * g.filled).sum() / g.filled.sum()), 5)
    cls = X[X.method == "cls"]
    meta.update({
        "measured": dt.datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "private runner records (orders.jsonl, plan.json, send.json, reconcile.json); SIP quotes, trades, "
                  "auctions and raw daily bars read through Alpaca's data API; FILL activities for days the records lack",
        "books": {b: {"days_with_orders": int(O[O.book == b].date.nunique()),
                      "planned_orders": int((O.book == b).sum()), "submitted": int((O.submitted & (O.book == b)).sum()),
                      "skipped_at_send": int((~O.submitted & (O.book == b)).sum()),
                      "late_market_orders_filled": int(((L.book == b)).sum())} for b in ("cef", "c4")},
        "core days": {"first": core_days[0], "last": core_days[-1], "late_market_days": len(core_days)},
        "cls (paper) orders on the core": {"days": int(cls.date.nunique()), "orders": int(len(cls)),
                                           "filled_any": int((cls.filled > 0).sum())},
        "orders whose sent qty differs from the plan (buying-power re-fit at send)": int(
            (O.submitted & (O.qty != O.planned_qty)).sum()),
        "unfilled late_market orders": int(((X.method == "late_market") & X.submitted & (X.filled < X.qty)).sum()),
        "closing cross: core orders with no primary 6 print": int(L[L.book == "cef"].cross_part.isna().sum()),
        "fills": fills_meta,
        "share of core notional by spread in ticks at send": {
            f"{int(k)}": round(float(v), 3) for k, v in
            (L[L.book == "cef"].groupby(np.minimum(L[L.book == "cef"].spread_ticks.round(), 3)).notional.sum()
             / L[L.book == "cef"].notional.sum()).items()},
        "core order participation": {
            "of 63-session $ADV: median, notional-weighted mean, max": [
                round(float(L[L.book == "cef"].adv_part.median()), 5), round(wavg(L[L.book == "cef"], "adv_part"), 5),
                round(float(L[L.book == "cef"].adv_part.max()), 5)],
            "of the day's closing cross: median, notional-weighted median, p90": [
                round(float(L[L.book == "cef"].cross_part.median()), 4),
                round(float(_wmedian(L[L.book == "cef"].dropna(subset=["cross_part"]), "cross_part")), 4),
                round(float(L[L.book == "cef"].cross_part.quantile(.9)), 4)]},
        "est_price vs SIP daily close of the decide date, |bp|: median, max": [
            r2(float((abs(X.est_price - X.C_prev) / X.C_prev * 1e4).median())),
            r2(float((abs(X.est_price - X.C_prev) / X.C_prev * 1e4).max()))],
        "official print vs SIP daily close on the fill day, |bp|: median, share equal": [
            r2(float((abs(L.Pc - L.C_D) / L.Pc * 1e4).median())), round(float((abs(L.Pc - L.C_D) < 5e-5).mean()), 3)],
    })
    out = {"meta": meta, "definitions": __doc__.split("SIGNS AND UNITS.")[1].split("STATISTICS.")[0].strip(),
           "tables": tables(L), "regressions": regressions(L), "timing": timing(L),
           "spread_profile": spread_profile(X, O, a.cache_dir, core_days), "limits": limits(L),
           "turnover_core": turns, "dollars": dollars(L, None, turns, a.c4_design_turns, c4_equity)}
    if a.verify_csv:
        v = pd.read_csv(a.verify_csv)
        v = v[v.book == "cef"].set_index("date").fill_vs_auction_bp
        mine = L[L.book == "cef"].groupby("date").apply(lambda x: wavg(x, "B"), include_groups=False)
        both = pd.concat([mine.rename("this"), pd.to_numeric(v, errors="coerce").rename("verify")], axis=1).dropna()
        out["meta"]["tie to verify.csv fill_vs_auction_bp"] = {
            "days": len(both), "max_abs_diff_bp": r2(float((both.this - both.verify).abs().max())),
            "verify_csv_last_date": str(v.index.max())}
    # the aggregates must carry no symbol, id or account figure beyond equity means
    text = json.dumps(out, default=str)
    for sym in sorted(set(X.symbol)):
        if f'"{sym}"' in text or f" {sym} " in text:
            raise StudyError(f"symbol {sym} leaked into the aggregates")
    for cid in X.cid:
        if cid in text:
            raise StudyError("an order id leaked into the aggregates")
    a.aggregates.parent.mkdir(parents=True, exist_ok=True)
    a.aggregates.write_text(json.dumps(out, indent=1, default=str) + "\n")
    a.private_dir.mkdir(parents=True, exist_ok=True)
    keep = [c for c in L.columns if not c.startswith(("touch_", "mid_", "qhs_", "paper_fill_", "prints_", "loc_", "L_"))]
    L[keep].to_csv(a.private_dir / "orders.csv", index=False)
    FR.to_csv(a.private_dir / "fills.csv", index=False)
    byname = {s: agg(g) for s, g in L.groupby(["book", "symbol"])}
    pd.DataFrame(byname).T.to_csv(a.private_dir / "by_name.csv")
    # per-name quoted half-spread at 15:52:00 over every core session (market data; kept private with
    # the per-name cost table so that no per-name figure is committed)
    rows = []
    for d in core_days:
        Q = json.loads((a.cache_dir / f"md_{d}_quotes.json").read_text())
        for s in sorted(Q):
            b_, a_, *_ = Tape(Q[s], []).quote(et_ts(d, "15:52:00"), "15:52")
            rows.append(dict(symbol=s, date=d, half_spread_bp=(a_ - b_) / (a_ + b_) * 1e4, mid=(a_ + b_) / 2))
    pd.DataFrame(rows).groupby("symbol").agg(half_spread_bp_mean=("half_spread_bp", "mean"),
                                             half_spread_bp_median=("half_spread_bp", "median"),
                                             mid_median=("mid", "median"), sessions=("date", "nunique")
                                             ).to_csv(a.private_dir / "spread_by_name.csv")
    print(json.dumps(out["meta"], indent=1, default=str))
    return 0


def _wmedian(g, col, w="notional"):
    g = g.sort_values(col)
    c = g[w].cumsum() / g[w].sum()
    return g[col].to_numpy()[np.searchsorted(c.to_numpy(), 0.5)]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sp = p.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("fetch")
    f.add_argument("--records", type=Path, required=True)
    f.add_argument("--cache-dir", type=Path, required=True)
    g = sp.add_parser("analyse")
    g.add_argument("--records", type=Path, required=True)
    g.add_argument("--cache-dir", type=Path, required=True)
    g.add_argument("--private-dir", type=Path, required=True)
    g.add_argument("--aggregates", type=Path, required=True)
    g.add_argument("--c4-design-turns", type=float, required=True,
                   help="C4's design turnover, turns/yr, from its spec note (no default; H14)")
    g.add_argument("--verify-csv", type=Path)
    a = p.parse_args(argv)
    return fetch(a) if a.cmd == "fetch" else analyse(a)


if __name__ == "__main__":
    raise SystemExit(main())
