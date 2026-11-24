"""Shared by the shadow fetchers: where a panel goes, and how it is written.

A fetcher is a `refresh` command in a book file. The nightly run executes it with
SHADOW_STATE_DIR set, and the engine then checks the panel's freshness itself, so a
fetcher never needs to say whether it succeeded beyond its exit code: a failed or partial
fetch leaves a stale panel, which the gate sees.

Panels are written to a temporary name and renamed, so a book never reads half a file.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from .. import engine

NY = ZoneInfo("America/New_York")
SETTLE = dt.time(16, 30)


def panels_dir() -> Path:
    d = engine.state_dir() / "panels"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write(df: pd.DataFrame, name: str) -> Path:
    path = panels_dir() / name
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)
    return path


def last_closed_date(now: dt.datetime | None = None) -> dt.date:
    """Today from 16:30 New York, else yesterday: a row dated later is not a close yet
    (Yahoo serves the open session's bar dated as a daily bar; docs/REFERENCES.md 12yf)."""
    ny = (now or dt.datetime.now(dt.timezone.utc)).astimezone(NY)
    return ny.date() if ny.time() >= SETTLE else ny.date() - dt.timedelta(days=1)


def universe(name: str) -> list:
    path = engine.REPO / "shadow" / "universes" / f"{name}.csv"
    syms = [r["symbol"] for r in csv.DictReader(open(path))]
    if not syms or len(set(syms)) != len(syms):
        raise ValueError(f"{path}: empty or duplicate symbols")
    return syms
