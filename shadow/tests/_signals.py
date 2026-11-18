"""Signals for the engine's tests only. Synthetic: they test the code, never a market claim."""
import numpy as np
import pandas as pd


def last_return(asof, panels):
    """Long yesterday's losers, short its winners, unit gross. Reads the `px` panel."""
    px = panels["px"].pivot(index="date", columns="symbol", values="close").sort_index()
    if len(px) < 2:
        return pd.Series(dtype=float)
    r = px.iloc[-1] / px.iloc[-2] - 1.0
    w = -(r - r.mean())
    return w / w.abs().sum()


def nan_weight(asof, panels):
    return pd.Series({"AAA": np.nan, "BBB": 1.0})


def boom(asof, panels):
    """A signal with a bug: raises something that is not the engine's own Unmeasured."""
    raise KeyError("no such column")
