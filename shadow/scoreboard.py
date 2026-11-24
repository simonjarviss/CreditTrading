"""One page for every shadow book, from each book's scores.csv. SIMULATED throughout.

WHY THE THRESHOLD: a Sharpe ratio or a correlation on a handful of days is noise that
reads like a result, so neither is printed below MIN_DAYS scored sessions; the cell
says how many days there are instead (CLAUDE.md: a stated gap, never a guess).

Aggregates only. Per-name weights stay in the state directory: the repository is public
(docs/SYSTEM.md section 5, 2026-11-03: "aggregates in repo, rows private").
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import pandas as pd

from .book import Book

MIN_DAYS = 20
PERIODS = 252
SIZES_USD = (1_000_000, 5_000_000, 10_000_000)


def read_scores(state: Path, book: Book) -> pd.DataFrame:
    p = state / book.slug / "scores.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, dtype={"detail": str, "decision_asof": str})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def stats(book: Book, df: pd.DataFrame) -> dict:
    """Per-book figures on the price-only line (the total-return line beside it)."""
    out = {"slug": book.slug, "started": book.started.isoformat(), "sessions": len(df),
           "scored": 0, "flat": 0, "unmeasured": 0}
    if df.empty:
        return out
    out["flat"] = int((df["status"] == "FLAT").sum())
    out["unmeasured"] = int((df["status"] == "UNMEASURED").sum())
    sc = df[df["status"] == "SCORED"]
    out["scored"] = len(sc)
    out["last"] = df["date"].max().isoformat()
    if sc.empty:
        return out
    r = sc["pnl_price_usd"].astype(float) / book.notional_usd
    out["pnl_price_usd"] = float(sc["pnl_price_usd"].astype(float).sum())
    tot = pd.to_numeric(sc["pnl_total_usd"], errors="coerce")
    # a total with a missing day is not the total
    out["pnl_total_usd"] = float(tot.sum()) if tot.notna().all() else None
    cum = r.cumsum()
    out["max_drawdown"] = float((cum - cum.cummax()).min())
    out["mean_gross"] = float(sc["gross"].astype(float).mean())
    turn = pd.to_numeric(df["turnover"], errors="coerce").dropna()
    out["turnover_per_year"] = float(turn.sum() / len(df) * PERIODS) if len(turn) else None
    if len(sc) >= MIN_DAYS and r.std() > 0:
        out["sharpe"] = float(r.mean() / r.std() * math.sqrt(PERIODS))
    return out


def correlations(books: list[Book], frames: dict) -> pd.DataFrame | None:
    cols = {}
    for b in books:
        df = frames[b.slug]
        if df.empty:
            continue
        sc = df[df["status"] == "SCORED"]
        if len(sc) >= MIN_DAYS:
            cols[b.slug] = sc.set_index("date")["pnl_price_usd"].astype(float)
    if len(cols) < 2:
        return None
    return pd.DataFrame(cols).corr(min_periods=MIN_DAYS)


def _fmt(v, kind="num") -> str:
    if v is None:
        return "UNMEASURED"
    if kind == "usd":
        return f"{v:+,.0f}"
    if kind == "pct":
        return f"{v:+.2%}"
    return f"{v:.2f}"


def render(books: list[Book], state: Path, *, late: dict, today: dt.date) -> str:
    frames = {b.slug: read_scores(state, b) for b in books}
    lines = [f"# Shadow scoreboard — {today.isoformat()}", "",
             "**Every figure is SIMULATED**: decisions made on live data, filled at the next official close "
             "by assumption, with no cost, borrow or fill risk. It is not evidence of what trading earns "
             f"(`CLAUDE.md`). Sharpe and correlations need {MIN_DAYS} scored sessions. Notional per book is "
             "its own file's `notional_usd`; returns are on that constant notional.", "",
             "| book | started | last | scored | flat | unmeasured | late decisions | P&L price | P&L total return | "
             "Sharpe | max drawdown | mean gross | turnover / yr |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for b in books:
        s = stats(b, frames[b.slug])
        sharpe = _fmt(s["sharpe"]) if "sharpe" in s else f"needs {MIN_DAYS} (has {s['scored']})"
        lines.append("| " + " | ".join([
            b.slug + ("" if b.enabled else " (off)"), s["started"], s.get("last", "none"), str(s["scored"]),
            str(s["flat"]), str(s["unmeasured"]), str(len(late.get(b.slug, []))),
            _fmt(s.get("pnl_price_usd"), "usd") if s["scored"] else "none",
            _fmt(s.get("pnl_total_usd"), "usd") if s["scored"] else "none", sharpe,
            _fmt(s.get("max_drawdown"), "pct") if s["scored"] else "none",
            _fmt(s.get("mean_gross")) if s["scored"] else "none",
            _fmt(s.get("turnover_per_year")) if s["scored"] else "none"]) + " |")
    corr = correlations(books, frames)
    lines += ["", "## Correlation of daily P&L (price line)", ""]
    if corr is None:
        lines.append(f"Not shown: fewer than two books have {MIN_DAYS} scored sessions.")
    else:
        lines.append("| | " + " | ".join(corr.columns) + " |")
        lines.append("|---|" + "---|" * len(corr.columns))
        for i in corr.index:
            lines.append(f"| {i} | " + " | ".join("n/a" if pd.isna(v) else f"{v:+.2f}" for v in corr.loc[i]) + " |")
    lines += ["", "## Capacity", "",
              "Position size against average daily volume at "
              + ", ".join(f"${s // 1_000_000}M" for s in SIZES_USD)
              + " is UNMEASURED here: the marks carry no volume yet. It is shown in each idea's Explore "
              "result until the marks do.", ""]
    return "\n".join(lines)
