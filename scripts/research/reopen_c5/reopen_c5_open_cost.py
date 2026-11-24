"""C5 re-opened as an execution choice: the opening cross's cost (`s_open`) re-measured on recent quotes.
Zero trials. Offline: reads two local caches and two committed records; no network, no broker, no key.

    python3 scripts/research/reopen_c5/reopen_c5_open_cost.py \
        --recent-cache <main checkout>/.claude/worktrees/research-exec-capacity/results/cef/exec_capacity/_cache_exec \
        --frozen <main checkout>/.claude/worktrees/trial-c5/results/cef/c5/_cache_c5_frozen

Writes results/research/reopen_c5/reopen_c5_output_<STAMP>.txt, reopen_c5_result_<STAMP>.json and
reopen_c5_recent_pairs_<STAMP>.csv. The note is results/research/REOPEN_C5_OPEN_COST_<STAMP>.md.
Once `fetch_2023_refs.py` has filled the 2023-26 stride cache, add
`--stride-cache results/research/reopen_c5/_cache_reopen_c5_2023 --stamp <run date>` (the stamp must
differ from 2026-10-28, whose outputs are the recent-window record).

WHY THIS EXISTS
---------------
C5 (CEF trial 51) filled the evening's CEF trade at the t+1 OPENING auction instead of the t+1 close.
It was recorded KILLED D1 on the lagged-signal placebo, but the gain replicated out of sample
(holdout 2023-01-03 -> 2026-09-30: +7.12bp per unit of turnover [S]), and the 2026-10-27 audit
(results/research/DESK_METHOD_2026-10-27.md §2, §7 item 5; ruled in docs/SYSTEM.md §5) relabelled the
evidence PRESENT with the placebo split INCONCLUSIVE. The surcharge the trial charged the open fill,
`s_open` = 6.52bp [S], was measured on a 2016-22 quote sample, where the opening cross was about a
seventh of today's size (results/cef/EXEC_CAPACITY_OPEN_CROSS_2026-10-13.md §4 [S]). Against a
holdout gain of 7.12bp it "barely clears". The re-open asks: on recent quotes, is the gain per unit of
turnover minus the opening cross's surcharge still positive? This is an EXECUTION question. Hard rule 3
(order type stays MOC) is why it is measurement only.

WHAT `s_open` IS (the definition, reused, not re-implemented)
--------------------------------------------------------------
`scripts/cef/c5_open_auction.py::stage6`, on the cost table of
`scripts/cef/exec_capacity_open_cross.py::cost_table`:
  * per name-day with an auction trade (the primary's O / 6 print, or an odd-lot cross), the
    dislocation |auction price - reference mid| / mid in bp, on each side;
  * reference mids at matched horizons: h1 = the last valid consolidated NBBO before 09:31 (open) and
    1 minute before the close; h5 = before 09:35 and 5 minutes before the close (`ref_points`);
  * per horizon, the mean over name-days paired on both sides (open NBBO-referenced; close not
    unmeasured) of (open dislocation - close dislocation);
  * s_open = max(h1 mean, h5 mean).
It is an UPPER bound on the open fill's extra cost: what a participant on the imbalance side of every
cross would pay, while the other side earns it. C5's G was already priced at the opening print, so
subtracting s_open from G charges the print's distance from fair twice when C5 is not on the imbalance
side (C5's own signed dislocation in the fit was -2.87bp per material trade [S]). The comparison below
is therefore a stress, as it was in the trial.

WHAT DATA EXISTS, AND WHAT DOES NOT (established 2026-10-28, before any figure here was computed)
-----------------------------------------------------------------------------------------------
  * 2016-22: C5's FROZEN quote sample, every 14th session of 2016-01-04 -> 2022-12-30 (126 sessions),
    with SHA-256 for every file in results/cef/c5/c5_frozen_inputs_2026-10-14.json. Used here only to
    reproduce the trial's s_open exactly, as the check that this script measures the same thing.
  * 2023-26: the ONLY cached NBBO reference quotes are the EXEC note's recent window, the last 60
    sessions of its calendar, 2026-07-21 -> 2026-10-13 (fetched 2026-10-13, gitignored cache in the
    `research-exec-capacity` worktree). The 2023-01-03 -> 2026-07-20 opening-cross prints are cached
    (C5's holdout freeze) but their reference quotes are not. Fetching them is a read-only Alpaca
    market-data GET that needs QUANTT_ENV_FILE, i.e. loading the key file, which no agent may do
    (CLAUDE.md order-path rule 5). That gap is reported, not filled.

THE DESIGN, FIXED BEFORE ANY FIGURE OF THIS SCRIPT WAS SEEN
-----------------------------------------------------------
 1. Primary cost sample: the 60-session recent window, exactly as the EXEC note sampled it
    (`exec_capacity_open_cross.load_days(eras=("recent",))`). It was not chosen here.
 2. Estimate: s_open as defined above, on that sample.
 3. Its SE: of the horizon that sets s_open. Clustered by date: the date-weighted series
    x_d = D * (sum of the name-day differences on date d) / N, whose mean is exactly the pooled mean,
    put through `inference.newey_west_t` at lag 0 (the cluster-by-date SE) and at the automatic lag
    (serial correlation across consecutive sessions). The SE used is the LARGER of the two.
 4. The gain: `G.bp_per_turn` from results/cef/c5/C5_HOLDOUT_RESULT.json [S], never re-derived. Its
    SE = bp_per_turn / min(t21, t5, t_auto), the smallest of the three t's the record holds (the most
    conservative). Turnover is fixed by the holdings path, so per-turnover and per-year t's coincide.
 5. Net = gain - s_open. SE_net = sqrt(SE_gain^2 + SE_s_open^2), treating the two as independent [U]:
    the gain is a daily P&L series over 939 sessions, the cost a quote sample over 60.
 6. Reading: `inference.read_result(net, SE_net, meaningful=1.0, n_trials=1)`. meaningful = 1bp per
    unit of turnover (task, 2026-10-28). n_trials = 1: this is one pre-specified comparison of a cost
    measurement against an estimate from a holdout that was opened once under its pre-registration;
    nothing is selected among alternatives here, and the zero-trial ruling spends no counter.
 7. Beside, never deciding: the same reading with the fit's s_open (the frozen 2016-22 sample); the
    N = 52 sensitivity (the CEF counter); the recent sample cut at 2026-09-30 (the holdout's last
    day); s_open by name and by year; and a second, independent computation of the recent paired means
    from the raw cached prints and quotes.
 8. The cost grid 5 / 15 / 30bp does not apply: G is the difference between two fills of ONE holdings
    path, which share one turnover, so any per-unit cost charged to both fills cancels in G and in
    G - s_open (the trial's note says the same).

THE 2023-26 STRIDE SAMPLE (design added 2026-10-28, before any of its quotes were fetched)
-----------------------------------------------------------------------------------------
With `--stride-cache`, the script reads the cache `fetch_2023_refs.py` writes: every
`FIT_SAMPLE_EVERY`-th session of 2023-01-03 -> 2026-07-20 (64 sessions on the cached calendar), the
six reference quotes per session, and C5's frozen holdout auction prices for those days.
 S1. It scores ROUND-LOT crosses only, from the primary's `O` / `6` print prices and the cached mids
     (`independent_round_pairs`), because the holdout prints carry no size and the tape was not
     fetched. A name-day without a primary `O` / `6` print or without a quote is counted, never filled.
     The restriction's effect is measured beside on the fit sample, where both paths exist. On the
     recent window it is 0.0 (the second method above).
 S2. It becomes the PRIMARY cost sample of the reading, because it spans the period the gain spans.
     The recent window moves beside. The estimate, SE rule, gain, meaningful size and n_trials are
     those of items 2-6.
 S3. By name and by year (2023, 2024, 2025, 2026 to 07-20), and at N = 52 beside.
 S4. Every stride session must be cached, with the era, date and close the calendar gives; else it
     raises, naming the first missing ones.

HOLDOUT
-------
No return-based statistic is computed on any date from 2023-01-01. The only 2023+ inputs are quotes
and auction prices (a cost), and the trial's already-opened holdout gain, read from its record.

NO SILENT FALLBACKS
-------------------
A missing cache file, a hash mismatch, a fit s_open that does not reproduce the trial's record, a
missing record field, NaNs in a difference series, or a zero mean behind a t: each raises, naming it.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research.inference import newey_west_t, read_result  # noqa: E402

STAMP = "2026-10-28"
OUT_DIR = REPO / "results" / "research" / "reopen_c5"
FROZEN_RECORD = REPO / "results" / "cef" / "c5" / "c5_frozen_inputs_2026-10-14.json"
FIT_VERDICT = REPO / "results" / "cef" / "c5" / "C5_FIT_VERDICT.json"
HOLDOUT_RESULT = REPO / "results" / "cef" / "c5" / "C5_HOLDOUT_RESULT.json"
HORIZONS = ("h1", "h5")                     # the two that define s_open (stage6)
MEANINGFUL_BP = 1.0                         # per unit of one-way turnover; set by the task before computing
N_TRIALS = 1                                # see the docstring, design item 6
N_TRIALS_SENSITIVITY = 52                   # the CEF counter's N, beside only
HOLDOUT_LAST = "2026-09-30"                 # C5's holdout end (its record), for the report-only cut
FIT_REPRO_TOL_BP = 1e-9                     # same code, same frozen bytes: the trial's float must come back
STRIDE_FIRST = "2023-01-03"                 # C5's holdout start (its record): the stride's first session
STRIDE_LAST = "2026-07-20"                  # the day before the cached recent window begins
STRIDE_ERA = "holdout_stride"               # the `era` tag fetch_2023_refs.py writes into each session file


def shown(p: Path) -> str:
    """A path as printed and recorded: anything under a worktree of the main checkout is shown from
    `<main checkout>`, so no home directory reaches a tracked file (the repository is public)."""
    s = str(p)
    k = s.find("/.claude/worktrees/")
    return "<main checkout>" + s[k:] if k >= 0 else s


class ReopenError(RuntimeError):
    """An input this measurement needs is missing, altered, or does not reproduce."""


# =============================================================================
# pure functions (tested in scripts/research/tests/test_reopen_c5_open_cost.py)
# =============================================================================

def paired_diffs(C: pd.DataFrame, era: str, h: str) -> pd.Series:
    """(open dislocation - close dislocation) per name-day, bp, for one era and horizon.

    Exactly stage6's pairing in scripts/cef/c5_open_auction.py: close rows whose method is not
    "unmeasured", open rows whose method is "nbbo" (never the prior-close fallback, which exists only
    at h0), inner-joined on (date, ticker). Indexed by (date, ticker)."""
    need = {"era", "h", "side", "method", "date", "ticker", "abs"}
    if not need <= set(C.columns):
        raise ReopenError(f"cost table lacks columns {sorted(need - set(C.columns))}")
    gh = C[(C.era == era) & (C.h == h)]
    if gh.empty:
        raise ReopenError(f"cost table has no rows for era {era!r}, horizon {h!r}")
    cl = gh[(gh.side == "close") & (gh.method != "unmeasured")]
    op = gh[(gh.side == "open") & (gh.method == "nbbo")]
    pair = (cl.set_index(["date", "ticker"])["abs"].rename("c").to_frame()
            .join(op.set_index(["date", "ticker"])["abs"].rename("o"), how="inner"))
    d = (pair.o - pair.c).rename("diff_bp")
    if d.isna().any():
        raise ReopenError(f"{int(d.isna().sum())} paired differences are NaN ({era}, {h})")
    return d


def date_weighted_series(diff: pd.Series) -> pd.Series:
    """x_d = D * (sum of the differences on date d) / N, one value per date.

    WHY. s_open is the POOLED mean over name-days, while name-days on one date share a market and are
    not independent. The mean of x_d is exactly the pooled mean, and the variance of that mean across
    dates is the cluster-by-date variance (identical to the textbook CR0 cluster SE when every date
    has the same number of names). A HAC t of x_d therefore clusters by date and, at a positive lag,
    also allows correlation between consecutive sessions."""
    if diff.isna().any():
        raise ReopenError("date_weighted_series got NaNs; drop them explicitly and count them")
    if "date" not in (diff.index.names or []):
        raise ReopenError("the difference series must be indexed by a 'date' level")
    g = diff.groupby(level="date")
    D, N = g.ngroups, len(diff)
    if D < 3:
        raise ReopenError(f"{D} dates: too few for a clustered SE")
    return (g.sum() * D / N).sort_index()


def se_of_mean(x: pd.Series | np.ndarray, lags: int | None) -> float:
    """The HAC standard error of a series' mean, |mean / newey_west_t(x, lags)|.

    Raises on a zero mean, where the ratio is undefined; it never returns a default."""
    x = np.asarray(x, dtype=float)
    m = float(x.mean())
    if m == 0.0:
        raise ReopenError("mean is exactly zero: se = mean / t is undefined")
    return abs(m / newey_west_t(x, lags=lags))


def auto_lag(n: int) -> int:
    """`newey_west_t`'s automatic lag, floor(4 (n/100)^(2/9)) (Newey-West 1994), shown in the output."""
    return int(4 * (n / 100) ** (2 / 9))


def clustered_mean(diff: pd.Series) -> dict:
    """Pooled mean of a name-day difference series, with its date-clustered SE at lag 0 and at the
    automatic lag; `se` is the larger (design item 3)."""
    x = date_weighted_series(diff)
    se0, sea = se_of_mean(x, 0), se_of_mean(x, None)
    return dict(mean=float(diff.mean()), n_name_days=int(len(diff)), n_dates=int(len(x)),
                se_l0=se0, se_auto=sea, lag_auto=auto_lag(len(x)), se=max(se0, sea),
                mean_of_date_means=float(diff.groupby(level="date").mean().mean()))


def s_open_point(diffs: dict) -> dict:
    """s_open = max over the horizons of the pooled paired mean; names the horizon that sets it."""
    missing = [h for h in HORIZONS if h not in diffs]
    if missing:
        raise ReopenError(f"no paired differences for horizon(s) {missing}")
    means = {h: float(diffs[h].mean()) for h in HORIZONS}
    h_star = max(HORIZONS, key=lambda h: means[h])
    return dict(by_h=means, s_open=means[h_star], h_star=h_star)


def gain_from_record(rec: dict) -> dict:
    """The holdout gain per unit of turnover and its SE, read from C5_HOLDOUT_RESULT.json [S].

    SE = bp_per_turn / min(t21, t5, t_auto): the smallest t the record holds (design item 4)."""
    G = rec.get("G")
    if not isinstance(G, dict):
        raise ReopenError("the holdout record has no 'G' block")
    for k in ("bp_per_turn", "t21", "t5", "t_auto", "n", "mean_bp_yr"):
        if k not in G or G[k] is None or not np.isfinite(float(G[k])):
            raise ReopenError(f"the holdout record's G block lacks a finite {k!r}")
    ts = {k: float(G[k]) for k in ("t21", "t5", "t_auto")}
    t_min = min(ts.values())
    if t_min <= 0:
        raise ReopenError(f"the smallest holdout t is {t_min}; the SE rule needs a positive t")
    g = float(G["bp_per_turn"])
    return dict(gain_bp=g, se_bp=g / t_min, t_used=t_min, t_which=min(ts, key=ts.get), ts=ts,
                sessions=int(G["n"]), mean_bp_yr=float(G["mean_bp_yr"]),
                turn_yr=float(G["mean_bp_yr"]) / g)


def net_reading(gain: dict, s_open: float, se_s_open: float, *, meaningful: float, n_trials: float) -> dict:
    """gain - s_open, its SE (independence [U]), and `inference.read_result` on it."""
    if not (np.isfinite(s_open) and se_s_open > 0):
        raise ReopenError(f"s_open {s_open} with SE {se_s_open} cannot be read")
    net = gain["gain_bp"] - s_open
    se = sqrt(gain["se_bp"] ** 2 + se_s_open ** 2)
    r = read_result(net, se, meaningful, n_trials=n_trials)
    return dict(net_bp=net, se_bp=se, meaningful_bp=meaningful, n_trials=n_trials,
                net_bp_yr=net * gain["turn_yr"], **r)


def independent_round_pairs(days: dict, auctions: pd.DataFrame, open_key: str, close_key: str,
                            primary: str = "N") -> tuple[pd.Series, dict]:
    """A second method for the recent window's paired means, from the raw cache only.

    Takes the primary's round-lot cross prints straight from the auction rows (exactly one `O` print
    for the open, one `6` for the close, per name-day) and the cached reference mids, with none of
    `classify_cross`'s tape logic. It scores round crosses only, so on a window where every scored
    cross is round it must equal `paired_diffs`; anything it cannot score is counted, not filled."""
    a = auctions[auctions.x == primary]
    o = a[(a.side == "open") & (a.c == "O")]
    c = a[(a.side == "close") & (a.c == "6")]
    for lab, f in (("O", o), ("6", c)):
        dup = f.duplicated(["date", "ticker"], keep=False)
        if dup.any():
            raise ReopenError(f"{int(dup.sum())} name-days carry more than one primary {lab!r} print")
    po = o.set_index(["date", "ticker"]).p
    pc = c.set_index(["date", "ticker"]).p
    rows, skipped = [], {"no_open_print": 0, "no_close_print": 0, "no_open_quote": 0, "no_close_quote": 0}
    for ds, rec in days.items():
        for t in rec[open_key]:
            qo, qc = rec[open_key].get(t), rec[close_key].get(t)
            if (ds, t) not in po.index:
                skipped["no_open_print"] += 1
                continue
            if (ds, t) not in pc.index:
                skipped["no_close_print"] += 1
                continue
            if qo is None:
                skipped["no_open_quote"] += 1
                continue
            if qc is None:
                skipped["no_close_quote"] += 1
                continue
            do = abs(float(po[(ds, t)]) - qo["mid"]) / qo["mid"] * 1e4
            dc = abs(float(pc[(ds, t)]) - qc["mid"]) / qc["mid"] * 1e4
            rows.append(dict(date=ds, ticker=t, diff_bp=do - dc))
    s = pd.DataFrame(rows).set_index(["date", "ticker"]).diff_bp.sort_index()
    return s, skipped


def stride_dates(dates, first: str, last: str, every: int) -> list[str]:
    """Every `every`-th session of [first, last], starting AT `first` (the fit sample's convention,
    `fit[::FIT_SAMPLE_EVERY]`). Raises if the calendar does not cover the window, or if `first` is not
    a session."""
    ds = sorted(str(d) for d in dates)
    if every < 1:
        raise ReopenError(f"stride {every} must be >= 1")
    if not ds or ds[0] > first or ds[-1] < last:
        raise ReopenError(f"the calendar ({ds[0] if ds else '-'}..{ds[-1] if ds else '-'}) does not cover "
                          f"{first}..{last}")
    w = [d for d in ds if first <= d <= last]
    if not w or w[0] != first:
        raise ReopenError(f"{first} is not a session in the calendar")
    return w[::every]


def load_stride(cache: Path, every: int, need_keys: list[str]) -> tuple[dict, pd.DataFrame, dict]:
    """The 2023-26 stride cache: {date: session record}, its auction prices, and a SHA-256 manifest.

    Every stride session of the cached calendar must be present with era STRIDE_ERA, its own date and
    the calendar's close, and every key in `need_keys` (design item S4). The auction rows must cover
    every stride date; a date with no rows at all would otherwise read as "no print" on all 13 names."""
    for f in ("calendar.parquet", "auctions_stride.parquet"):
        if not (cache / f).exists():
            raise ReopenError(f"{f} is missing from {shown(cache)}; run fetch_2023_refs.py")
    cal = pd.read_parquet(cache / "calendar.parquet")
    want = stride_dates(list(cal.date), STRIDE_FIRST, STRIDE_LAST, every)
    close = dict(zip(cal.date, cal.close))
    missing = [d for d in want if not (cache / "days" / f"{d}.json").exists()]
    if missing:
        raise ReopenError(f"{len(missing)} of {len(want)} stride sessions are not cached (first {missing[:3]}); "
                          "run fetch_2023_refs.py")
    days = {}
    for d in want:
        rec = json.loads((cache / "days" / f"{d}.json").read_text())
        if rec.get("era") != STRIDE_ERA or rec.get("date") != d or rec.get("close") != close[d]:
            raise ReopenError(f"{d}.json is cached as {rec.get('date')}/{rec.get('close')}/{rec.get('era')}, "
                              f"expected {d}/{close[d]}/{STRIDE_ERA}")
        lack = [k for k in need_keys if k not in rec]
        if lack:
            raise ReopenError(f"{d}.json lacks {lack}; re-run fetch_2023_refs.py to complete it")
        days[d] = rec
    A = pd.read_parquet(cache / "auctions_stride.parquet")
    no_rows = sorted(set(want) - set(A.date))
    if no_rows:
        raise ReopenError(f"auctions_stride.parquet has no rows on {len(no_rows)} stride date(s) (first {no_rows[:3]})")
    manifest = {f"days/{d}.json": sha256_file(cache / "days" / f"{d}.json") for d in want}
    for f in ("calendar.parquet", "auctions_stride.parquet"):
        manifest[f] = sha256_file(cache / f)
    return days, A, manifest


def by_name(diffs: dict) -> pd.DataFrame:
    """Per name and horizon: the mean over its sessions and its NW (automatic-lag) SE."""
    rows = []
    for t in sorted(set(diffs[HORIZONS[0]].index.get_level_values("ticker"))):
        row = dict(ticker=t)
        for h in HORIZONS:
            x = diffs[h].xs(t, level="ticker").sort_index()
            row[f"{h}_mean"] = float(x.mean())
            row[f"{h}_se"] = se_of_mean(x.values, None) if len(x) >= 3 else np.nan
            row[f"{h}_n"] = int(len(x))
        rows.append(row)
    return pd.DataFrame(rows).set_index("ticker")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verify_hashes(root: Path, recorded: dict, prefixes: tuple[str, ...]) -> int:
    """Every recorded file under `prefixes` exists under `root` with its recorded SHA-256. Returns
    the count checked; raises on the first mismatch or missing file."""
    keys = sorted(k for k in recorded if k.startswith(prefixes))
    if not keys:
        raise ReopenError(f"the record holds no files under {prefixes}")
    for k in keys:
        p = root / k
        if not p.exists():
            raise ReopenError(f"frozen file {k} is missing under {root}")
        if sha256_file(p) != recorded[k]:
            raise ReopenError(f"frozen file {k} does not match its recorded SHA-256")
    return len(keys)


# =============================================================================
# the run
# =============================================================================

@contextlib.contextmanager
def _pointing(X, cache: Path, w4: Path | None):
    """Point exec_capacity_open_cross at a cache for the duration (as c5_open_auction.py does)."""
    old = (X.CACHE, X.W4_CACHE)
    X.CACHE = cache
    if w4 is not None:
        X.W4_CACHE = w4
    try:
        yield
    finally:
        X.CACHE, X.W4_CACHE = old


def fit_cost_table(frozen: Path):
    """The trial's own quote_sample, on the frozen copy (scripts/cef/c5_open_auction.py::quote_sample)."""
    from scripts.cef import exec_capacity_open_cross as X
    from scripts.cef.spec import UNIVERSE
    syms = sorted(UNIVERSE)
    with _pointing(X, frozen / "exec", frozen / "w4"):
        days = X.load_days(eras=("fit",))
        fitA = X.fit_auction_rows(syms)
        Xc = X.cross_tables(days, fitA[fitA.date.isin(sorted(days))], syms)
        empty = pd.DataFrame(columns=["date", "ticker", "side", "x", "c", "p", "s", "t"])
        pc = X.prior_closes(days, empty, fitA)
        return days, X.cost_table(days, Xc, pc), fitA[fitA.date.isin(sorted(days))]


def recent_cost_table(cache: Path):
    """The EXEC note's recent window: its 60 sessions, its auction rows, its cost table."""
    from scripts.cef import exec_capacity_open_cross as X
    from scripts.cef.spec import UNIVERSE
    syms = sorted(UNIVERSE)
    ar_path = cache / "auctions_recent.parquet"
    if not ar_path.exists():
        raise ReopenError(f"{ar_path} is missing")
    with _pointing(X, cache, None):
        days = X.load_days(eras=("recent",))
        Ar = pd.read_parquet(ar_path)
        Xc = X.cross_tables(days, Ar, syms)
        empty = pd.DataFrame(columns=["date", "ticker", "side", "x", "c", "p", "s", "t"])
        pc = X.prior_closes(days, Ar, empty)
        return days, Ar, Xc, X.cost_table(days, Xc, pc)


def _fmt_cm(d: dict) -> str:
    return (f"{d['mean']:+.3f}bp  SE {d['se']:.3f} (lag0 {d['se_l0']:.3f}, lag{d['lag_auto']} {d['se_auto']:.3f})"
            f"  t {d['mean'] / d['se']:+.2f}  [{d['n_name_days']} name-days, {d['n_dates']} dates]")


def run(recent_cache: Path, frozen: Path, out_dir: Path, stride_cache: Path | None = None,
        stamp: str = STAMP) -> dict:
    from scripts.cef import exec_capacity_open_cross as X
    res: dict = dict(stamp=stamp, design=dict(meaningful_bp=MEANINGFUL_BP, n_trials=N_TRIALS,
                                              horizons=list(HORIZONS), se_rule="max(NW lag 0, NW auto lag) "
                                              "on the date-weighted series", gain_se_rule="bp_per_turn / "
                                              "min(t21, t5, t_auto)"))
    print(f"reopen_c5_open_cost, stamp {stamp}. Zero trials; offline; no network, broker or key.")

    # ---- 1. the definition check: the trial's s_open, reproduced on its frozen copy
    print("\n=== 1. DEFINITION CHECK: C5's s_open on its frozen 2016-22 quote sample ===")
    frec = json.loads(FROZEN_RECORD.read_text())
    n_h = verify_hashes(frozen, frec["files"], ("exec/", "w4/"))
    print(f"frozen copy {shown(frozen)}: {n_h} files under exec/ and w4/ match "
          f"{FROZEN_RECORD.relative_to(REPO)} (SHA-256)")
    fdays, Cf, fitA_days = fit_cost_table(frozen)
    fd = {h: paired_diffs(Cf, "fit", h) for h in HORIZONS}
    fs = s_open_point(fd)
    st6 = json.loads(FIT_VERDICT.read_text()).get("stage6")
    if not isinstance(st6, dict):
        raise ReopenError(f"{FIT_VERDICT.relative_to(REPO)} has no stage6 block")
    for h in HORIZONS:
        k = f"s_open_{h}"
        if k not in st6:
            raise ReopenError(f"{FIT_VERDICT.relative_to(REPO)} stage6 lacks {k}")
        dlt = fs["by_h"][h] - float(st6[k])
        print(f"  {h}: re-computed {fs['by_h'][h]:+.6f}bp, trial record {float(st6[k]):+.6f}bp, diff {dlt:+.1e}")
        if abs(dlt) > FIT_REPRO_TOL_BP:
            raise ReopenError(f"{h}: the fit s_open does not reproduce the trial's record ({dlt:+.3e}bp); "
                              "this script is not measuring the trial's quantity")
    fit_cm = {h: clustered_mean(fd[h]) for h in HORIZONS}
    for h in HORIZONS:
        print(f"  {h} on {len(fdays)} sessions: {_fmt_cm(fit_cm[h])}")
    print(f"  s_open (fit) = max(h1, h5) = {fs['s_open']:+.3f}bp, set by {fs['h_star']}. REPRODUCED.")
    res["fit"] = dict(sessions=len(fdays), first=min(fdays), last=max(fdays), s_open=fs, by_h=fit_cm,
                      frozen_files_verified=n_h)
    fy = {}
    for h in HORIZONS:
        yr = fd[h].index.get_level_values("date").str[:4]
        fy[h] = {y: clustered_mean(g) for y, g in fd[h].groupby(yr.values)}
    print("  by year (beside; cost only, so the fit period's years may be read):")
    print("    year   h1 mean (SE)        h5 mean (SE)        dates")
    for y in sorted(fy["h1"]):
        a, b = fy["h1"][y], fy["h5"][y]
        print(f"    {y}  {a['mean']:+7.2f} ({a['se']:.2f})    {b['mean']:+7.2f} ({b['se']:.2f})    {a['n_dates']}")
    res["fit"]["by_year"] = fy

    # ---- 2. the recent window
    print("\n=== 2. RECENT WINDOW: the EXEC note's last 60 sessions (the only cached 2023+ quotes) ===")
    rdays, Ar, Xr, Cr = recent_cost_table(recent_cache)
    dates = sorted(rdays)
    manifest = {f"days/{d}.json": sha256_file(recent_cache / "days" / f"{d}.json") for d in dates}
    for f in ("calendar.parquet", "auctions_recent.parquet"):
        manifest[f] = sha256_file(recent_cache / f)
    combined = hashlib.sha256("".join(f"{k}{v}" for k, v in sorted(manifest.items())).encode()).hexdigest()
    print(f"cache {shown(recent_cache)}: {len(dates)} sessions {dates[0]}..{dates[-1]}; combined SHA-256 of the "
          f"{len(manifest)} files read {combined[:16]}... (every hash in the JSON)")
    kinds = Xr.groupby(["side", "kind"]).size()
    print("crosses classified: " + "; ".join(f"{s} {k} {n}" for (s, k), n in kinds.items()))
    rd = {h: paired_diffs(Cr, "recent", h) for h in HORIZONS}
    for h in HORIZONS:
        m = Cr[(Cr.era == "recent") & (Cr.h == h)].groupby(["side", "method"]).size()
        print(f"  [{h}] reference methods: " + ", ".join(f"{a} {b} {n}" for (a, b), n in m.items()))
    rs = s_open_point(rd)
    rec_cm = {h: clustered_mean(rd[h]) for h in HORIZONS}
    for h in HORIZONS:
        print(f"  {h}: {_fmt_cm(rec_cm[h])}; mean of date means {rec_cm[h]['mean_of_date_means']:+.3f}")
    hs = rs["h_star"]
    s_recent, se_recent = rs["s_open"], rec_cm[hs]["se"]
    print(f"  s_open (recent) = max(h1, h5) = {s_recent:+.3f}bp, set by {hs}; SE {se_recent:.3f}bp")
    t_exec, _ = X._date_t(rd[hs])
    print(f"  the EXEC note's own t for this horizon (mean of date means / its SE, X._date_t): {t_exec:+.2f}")

    # second method
    indep = {}
    for h in HORIZONS:
        s2, skipped = independent_round_pairs(rdays, Ar, X.HORIZONS[h]["open"], X.HORIZONS[h]["close"])
        common = rd[h].index.intersection(s2.index)
        indep[h] = dict(mean=float(s2.mean()), n=int(len(s2)), skipped=skipped,
                        max_abs_diff_on_common=float((rd[h].loc[common] - s2.loc[common]).abs().max()),
                        only_in_primary=int(len(rd[h].index.difference(s2.index))),
                        only_in_second=int(len(s2.index.difference(rd[h].index))))
        print(f"  second method [{h}] (raw O/6 prints and cached mids, round crosses only): mean "
              f"{indep[h]['mean']:+.3f}bp on {indep[h]['n']} name-days (skipped {skipped}); against the "
              f"primary path: max |diff| on common name-days {indep[h]['max_abs_diff_on_common']:.1e}, only in "
              f"primary {indep[h]['only_in_primary']}, only in second {indep[h]['only_in_second']}")

    # by name, by year, the holdout-end cut
    BN = by_name(rd)
    print("\n  by name (each name's series over the sessions, NW automatic lag):")
    with pd.option_context("display.width", 200):
        print(BN.round(2).to_string())
    by_year = {}
    for h in HORIZONS:
        yr = rd[h].index.get_level_values("date").str[:4]
        by_year[h] = {y: clustered_mean(g) for y, g in rd[h].groupby(yr.values)}
    print("  by year: " + "; ".join(f"{h} {y} {_fmt_cm(v)}" for h in HORIZONS for y, v in by_year[h].items()))
    cut = {h: rd[h][rd[h].index.get_level_values("date") <= HOLDOUT_LAST] for h in HORIZONS}
    cut_s = s_open_point(cut)
    cut_cm = {h: clustered_mean(cut[h]) for h in HORIZONS}
    print(f"  cut at {HOLDOUT_LAST} (beside): " + "; ".join(f"{h} {_fmt_cm(cut_cm[h])}" for h in HORIZONS)
          + f"; s_open {cut_s['s_open']:+.3f}bp ({cut_s['h_star']})")

    res["recent"] = dict(sessions=len(dates), first=dates[0], last=dates[-1], cache=shown(recent_cache),
                         manifest=manifest, combined_sha256=combined, s_open=rs, by_h=rec_cm,
                         exec_note_date_t=float(t_exec),
                         second_method=indep, by_name=BN.reset_index().to_dict("records"),
                         by_year=by_year, cut_at_holdout_end=dict(s_open=cut_s, by_h=cut_cm),
                         kinds={f"{s}/{k}": int(n) for (s, k), n in kinds.items()})
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs = pd.concat({h: rd[h] for h in HORIZONS}, axis=1).reset_index()
    pairs.to_csv(out_dir / f"reopen_c5_recent_pairs_{stamp}.csv", index=False, float_format="%.6f")

    # ---- 2b. the 2023-26 stride sample (design items S1-S4), only when its cache is given
    st = None
    if stride_cache is not None:
        print(f"\n=== 2b. STRIDE SAMPLE: every {X.FIT_SAMPLE_EVERY}th session of {STRIDE_FIRST}..{STRIDE_LAST}, "
              "round-lot crosses (the gain's period) ===")
        need = sorted({X.HORIZONS[h][side] for h in HORIZONS for side in ("open", "close")})
        sdays, Sa, smanifest = load_stride(stride_cache, X.FIT_SAMPLE_EVERY, need)
        scomb = hashlib.sha256("".join(f"{k}{v}" for k, v in sorted(smanifest.items())).encode()).hexdigest()
        sdates = sorted(sdays)
        print(f"cache {shown(stride_cache)}: {len(sdates)} sessions {sdates[0]}..{sdates[-1]}; combined SHA-256 "
              f"of the {len(smanifest)} files read {scomb[:16]}...")
        sd, sskip = {}, {}
        for h in HORIZONS:
            sd[h], sskip[h] = independent_round_pairs(sdays, Sa, X.HORIZONS[h]["open"], X.HORIZONS[h]["close"])
        ss = s_open_point(sd)
        s_cm = {h: clustered_mean(sd[h]) for h in HORIZONS}
        for h in HORIZONS:
            print(f"  {h}: {_fmt_cm(s_cm[h])}; not scored {sskip[h]}")
        print(f"  s_open (stride) = max(h1, h5) = {ss['s_open']:+.3f}bp, set by {ss['h_star']}; "
              f"SE {s_cm[ss['h_star']]['se']:.3f}bp")
        SBN = by_name(sd)
        print("\n  by name (each name's series over the stride sessions, NW automatic lag):")
        with pd.option_context("display.width", 200):
            print(SBN.round(2).to_string())
        s_year = {}
        for h in HORIZONS:
            yr = sd[h].index.get_level_values("date").str[:4]
            s_year[h] = {y: clustered_mean(g) for y, g in sd[h].groupby(yr.values)}
        print("  by year:")
        for y in sorted(s_year["h1"]):
            print(f"    {y}  h1 {_fmt_cm(s_year['h1'][y])}\n          h5 {_fmt_cm(s_year['h5'][y])}")
        # S1: what the round-only restriction does where both paths exist (the fit sample)
        ro = {}
        for h in HORIZONS:
            fr, fsk = independent_round_pairs(fdays, fitA_days, X.HORIZONS[h]["open"], X.HORIZONS[h]["close"])
            ro[h] = dict(round_only=float(fr.mean()), full=float(fd[h].mean()), n_round=int(len(fr)),
                         n_full=int(len(fd[h])), not_scored=fsk)
            print(f"  round-only restriction on the fit sample [{h}]: {ro[h]['round_only']:+.3f}bp on "
                  f"{ro[h]['n_round']} name-days against the definition's {ro[h]['full']:+.3f}bp on "
                  f"{ro[h]['n_full']} (diff {ro[h]['round_only'] - ro[h]['full']:+.3f}); not scored {fsk}")
        st = dict(sessions=len(sdates), first=sdates[0], last=sdates[-1], cache=shown(stride_cache),
                  manifest=smanifest, combined_sha256=scomb, s_open=ss, by_h=s_cm, not_scored=sskip,
                  by_name=SBN.reset_index().to_dict("records"), by_year=s_year, round_only_on_fit=ro)
        res["stride"] = st
        pd.concat({h: sd[h] for h in HORIZONS}, axis=1).reset_index().to_csv(
            out_dir / f"reopen_c5_stride_pairs_{stamp}.csv", index=False, float_format="%.6f")

    # ---- 3. the reading
    print("\n=== 3. THE READING: holdout gain per unit of turnover [S] minus s_open ===")
    gain = gain_from_record(json.loads(HOLDOUT_RESULT.read_text()))
    print(f"gain [S] {HOLDOUT_RESULT.relative_to(REPO)}: {gain['gain_bp']:+.3f}bp per unit of turnover over "
          f"{gain['sessions']} sessions (mean {gain['mean_bp_yr']:+.1f}bp/yr, so {gain['turn_yr']:.2f} turns/yr); "
          f"t's {', '.join(f'{k} {v:.3f}' for k, v in gain['ts'].items())}; SE = gain / {gain['t_which']} = "
          f"{gain['se_bp']:.3f}bp")
    print(f"declared before computing: meaningful = {MEANINGFUL_BP}bp per unit of turnover; n_trials = {N_TRIALS}")
    def line(lab, r):
        return (f"  {lab}: net {r['net_bp']:+.3f}bp (SE {r['se_bp']:.3f}; {r['net_bp_yr']:+.1f}bp/yr of capital), "
                f"interval [{r['lo']:+.3f}, {r['hi']:+.3f}] at alpha {r['alpha_adj']:.5f}: {r['outcome']}, "
                f"meaningful {r['vs_meaningful']}; power at meaningful {r['power_at_meaningful']:.2f}")
    if st is not None:
        s_st, se_st = st["s_open"]["s_open"], st["by_h"][st["s_open"]["h_star"]]["se"]
        prim = net_reading(gain, s_st, se_st, meaningful=MEANINGFUL_BP, n_trials=N_TRIALS)
        print(line(f"PRIMARY, 2023-26 stride s_open {s_st:.3f}bp, N = {N_TRIALS}", prim))
        beside = {
            "recent_s_open_N1": net_reading(gain, s_recent, se_recent, meaningful=MEANINGFUL_BP, n_trials=N_TRIALS),
            "stride_s_open_N52": net_reading(gain, s_st, se_st, meaningful=MEANINGFUL_BP,
                                             n_trials=N_TRIALS_SENSITIVITY),
            "fit_s_open_N1": net_reading(gain, fs["s_open"], fit_cm[fs["h_star"]]["se"], meaningful=MEANINGFUL_BP,
                                         n_trials=N_TRIALS),
        }
        print(line(f"beside, recent s_open {s_recent:.3f}bp, N = 1", beside["recent_s_open_N1"]))
        print(line(f"beside, stride s_open, N = {N_TRIALS_SENSITIVITY}", beside["stride_s_open_N52"]))
        print(line(f"beside, the fit's s_open {fs['s_open']:.3f}bp, N = 1", beside["fit_s_open_N1"]))
        print("  cost grid 5/15/30bp: does not apply. G compares two fills of one holdings path with one turnover, "
              "so a per-unit cost charged to both cancels; the net is the same at 0, 5, 15 and 30bp.")
        res["gain"] = gain
        res["reading"] = dict(primary=prim, beside=beside)
        return res
    prim = net_reading(gain, s_recent, se_recent, meaningful=MEANINGFUL_BP, n_trials=N_TRIALS)
    print(line(f"PRIMARY, recent s_open {s_recent:.3f}bp, N = {N_TRIALS}", prim))
    beside = {
        "fit_s_open_N1": net_reading(gain, fs["s_open"], fit_cm[fs["h_star"]]["se"], meaningful=MEANINGFUL_BP,
                                     n_trials=N_TRIALS),
        "recent_s_open_N52": net_reading(gain, s_recent, se_recent, meaningful=MEANINGFUL_BP,
                                         n_trials=N_TRIALS_SENSITIVITY),
        "cut_s_open_N1": net_reading(gain, cut_s["s_open"], cut_cm[cut_s["h_star"]]["se"],
                                     meaningful=MEANINGFUL_BP, n_trials=N_TRIALS),
    }
    print(line(f"beside, the fit's s_open {fs['s_open']:.3f}bp, N = 1", beside["fit_s_open_N1"]))
    print(line(f"beside, recent s_open, N = {N_TRIALS_SENSITIVITY}", beside["recent_s_open_N52"]))
    print(line(f"beside, recent cut at {HOLDOUT_LAST}, N = 1", beside["cut_s_open_N1"]))
    print("  cost grid 5/15/30bp: does not apply. G compares two fills of one holdings path with one turnover, "
          "so a per-unit cost charged to both cancels; the net is the same at 0, 5, 15 and 30bp.")
    res["gain"] = gain
    res["reading"] = dict(primary=prim, beside=beside)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recent-cache", type=Path, required=True,
                    help="exec_capacity_open_cross's cache holding the EXEC note's recent window")
    ap.add_argument("--frozen", type=Path, required=True, help="C5's frozen copy (_cache_c5_frozen)")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--stride-cache", type=Path, default=None,
                    help="the 2023-26 stride cache fetch_2023_refs.py writes (design items S1-S4)")
    ap.add_argument("--stamp", default=STAMP, help="date stamp of the outputs (default: the recent-window run's)")
    a = ap.parse_args(argv)
    for p in [a.recent_cache, a.frozen] + ([a.stride_cache] if a.stride_cache is not None else []):
        if not p.is_dir():
            raise ReopenError(f"{p} is not a directory")
    if a.stride_cache is not None and a.stamp == STAMP:
        raise ReopenError(f"--stride-cache needs a --stamp other than {STAMP}: those outputs are the "
                          "recent-window record and must not be overwritten")
    buf = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s)
            buf.write(s)
            return len(s)

    with contextlib.redirect_stdout(Tee()):
        res = run(a.recent_cache.resolve(), a.frozen.resolve(), a.out,
                  a.stride_cache.resolve() if a.stride_cache is not None else None, a.stamp)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"reopen_c5_output_{a.stamp}.txt").write_text(buf.getvalue())
    (a.out / f"reopen_c5_result_{a.stamp}.json").write_text(json.dumps(res, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
