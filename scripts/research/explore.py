"""Shared reporting for an Explore test (docs/MISSION.md section 7): gross, split, control.

WHY ONE HELPER: every idea's Explore note must show the same things in the same way, or
two ideas cannot be compared: the full-sample gross result, an early and a late half, the
eras, a control, and one chart with the equity curve (docs/MISSION.md sections 2 and 11).
Costs are deliberately absent: research is judged on gross signal (team lead, 2026-11-09,
docs/SYSTEM.md section 5). The P&L itself always comes from `harness.evaluate`, so the
shift(2) convention is the harness's and is not restated here.

Nothing here fills a gap. A NaN in a P&L series raises: the caller decides what a missing
day means before it asks for statistics.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# NUMEXPR IS TURNED OFF FOR EVERY SCRIPT THAT IMPORTS THIS MODULE. On the team lead's laptop
# numexpr returns wrong cells for BROADCAST arithmetic (`df.sub(series, axis=0)`,
# `df.div(row_sums, axis=0)`) on any frame above one million cells, differently on each run
# (scripts/events/numexpr_fault.py; results/events/REPRO_CORP_EVENTS_2026-10-11.md). The
# first wide-universe Explore run (2026-11-10, a 6,539 x 6,882 frame) hit it: weights that
# were finite in one run were not in the next, and only the harness's refusal of an
# infinite weight showed it. A cross-sectional signal on a wide panel is exactly this
# arithmetic, so the option is set here, once, rather than left to each idea's script.
pd.set_option("compute.use_numexpr", False)

PERIODS = 252
ERAS = (("2002-01-01", "2008-12-31"), ("2009-01-01", "2015-12-31"), ("2016-01-01", "2019-12-31"),
        ("2020-01-01", "2022-12-31"), ("2023-01-01", "2030-12-31"))
MIN_ERA_DAYS = 120       # an era with fewer sessions is not reported: a Sharpe on it is noise


def stats(pnl: pd.Series) -> dict:
    """Daily P&L (fraction of notional) -> the row every Explore table shows."""
    if pnl.isna().any():
        raise ValueError("pnl holds NaN; decide what a missing day means before summarising")
    sd = pnl.std()
    on = pnl[pnl != 0]
    cum = pnl.cumsum()
    return {"first": str(pnl.index.min().date()), "last": str(pnl.index.max().date()),
            "n_days": int(len(pnl)), "n_active_days": int(len(on)),
            "ann_ret": float(pnl.mean() * PERIODS), "ann_vol": float(sd * np.sqrt(PERIODS)),
            "sharpe": float(pnl.mean() / sd * np.sqrt(PERIODS)) if sd > 0 else None,
            "t": float(pnl.mean() / sd * np.sqrt(len(pnl))) if sd > 0 else None,
            "mean_bp_per_active_day": float(on.mean() * 1e4) if len(on) else None,
            "hit_rate_active_days": float((on > 0).mean()) if len(on) else None,
            "max_drawdown": float((cum - cum.cummax()).min())}


def summarise(pnl: pd.Series, *, controls: dict | None = None, extra: dict | None = None) -> dict:
    """Full sample, the two halves, the eras, and each control on the same dates."""
    mid = pnl.index[len(pnl) // 2]
    out = {"full": stats(pnl), "split_date": str(mid.date()),
           "early_half": stats(pnl.loc[:mid]), "late_half": stats(pnl.loc[mid:]), "eras": {}}
    for a, b in ERAS:
        seg = pnl.loc[a:b]
        if len(seg) >= MIN_ERA_DAYS:
            out["eras"][f"{a[:4]}-{min(int(b[:4]), seg.index.max().year)}"] = stats(seg)
    out["controls"] = {k: stats(v.reindex(pnl.index).dropna()) for k, v in (controls or {}).items()}
    out.update(extra or {})
    return out


def write(out_dir: Path, res: dict, pnl: pd.Series, *, title: str, controls: dict | None = None) -> None:
    """results.json and equity.png beside the idea's script."""
    out_dir = Path(out_dir)
    (out_dir / "results.json").write_text(json.dumps(res, indent=1))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4))
    (pnl.cumsum() * 100).plot(ax=ax, label="the idea (gross)")
    for k, v in (controls or {}).items():
        (v.reindex(pnl.index).fillna(0.0).cumsum() * 100).plot(ax=ax, label=f"control: {k}", alpha=0.6)
    ax.set_ylabel("cumulative return, % of notional (not compounded)")
    ax.set_title(title, fontsize=10)
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(out_dir / "equity.png", dpi=110)
    plt.close(fig)


def table(res: dict) -> str:
    """The markdown table an idea card pastes: one row per sample."""
    rows = [("full", res["full"]), ("early half", res["early_half"]), ("late half", res["late_half"])]
    rows += [(k, v) for k, v in res["eras"].items()] + [(f"control: {k}", v) for k, v in res["controls"].items()]
    out = ["| sample | from | to | sessions | active | return / yr | vol / yr | Sharpe | t | bp per active day | hit rate |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, s in rows:
        f = lambda v, p: "n/a" if v is None else format(v, p)
        out.append(f"| {name} | {s['first']} | {s['last']} | {s['n_days']:,} | {s['n_active_days']:,} | "
                   f"{f(s['ann_ret'], '.2%')} | {f(s['ann_vol'], '.2%')} | {f(s['sharpe'], '.2f')} | {f(s['t'], '.2f')} | "
                   f"{f(s['mean_bp_per_active_day'], '.1f')} | {f(s['hit_rate_active_days'], '.1%')} |")
    return "\n".join(out)
