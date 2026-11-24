"""build_panel's z (band_frontier lines 162-164) for any panel; bdc_ic.py asserts it
reproduces build_panel's z exactly on the BDC discount before it is used on log price."""
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tree"))
from scripts.cef.band_frontier import MIN_PERIODS
from scripts.cef.spec import Z_WINDOW

def zscore(x):
    mu = x.rolling(Z_WINDOW, min_periods=MIN_PERIODS).mean().shift(1)
    sd = x.rolling(Z_WINDOW, min_periods=MIN_PERIODS).std().shift(1)
    return ((x - mu) / sd.replace(0, np.nan)).clip(-4, 4)
