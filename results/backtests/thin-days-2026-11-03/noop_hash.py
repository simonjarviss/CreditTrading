"""No-op proof for the `below_min_names` harness option (report only, 2026-11-03).

Hashes what `scripts/cef/band_frontier.py` produces on its DEFAULT path, so the
same script run before and after the edit shows the default is byte-identical.
It uses only the API that existed before the edit (build_targets, build_panel,
band, band_gross_capped with and without defer_flips), so the "before" run is
the unedited harness. Each hash is sha256 over the frame's values bytes, its
index (int64 ns) and its column names, as the turnover study hashed the held
book for `defer_flips` (results/backtests/turnover-live-2026-11-02/REPORT.md).

    python3 results/backtests/thin-days-2026-11-03/noop_hash.py

Writes nothing; the caller redirects stdout to noop_before.txt / noop_after.txt.
"""
import hashlib
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[3]          # the worktree root
sys.path.insert(0, str(REPO))

import numpy as np                                    # noqa: E402
import pandas as pd                                   # noqa: E402

from scripts.cef import band_frontier as bf           # noqa: E402
from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS, SPEC_ID   # noqa: E402


def h(df: pd.DataFrame) -> str:
    m = hashlib.sha256()
    m.update(np.ascontiguousarray(df.values).tobytes())
    m.update(df.index.values.astype("datetime64[ns]").astype(np.int64).tobytes())
    m.update("|".join(map(str, df.columns)).encode())
    return m.hexdigest()


T, R = bf.build_targets()
T0, R0 = bf.build_targets(min_adv=0)                  # the WIDE set: exercises the floor path
print("spec", SPEC_ID, "| T", T.index[0].date(), "..", T.index[-1].date(), T.shape)
print("build_targets T            ", h(T))
print("build_targets R            ", h(R))
print("build_targets(min_adv=0) T ", h(T0))
print("band(T, BAND_WIDTH)        ", h(bf.band(T, BAND_WIDTH)))
print("band_gross_capped cap      ", h(bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)))
print("band_gross_capped inf      ", h(bf.band_gross_capped(T, BAND_WIDTH, np.inf)))
print("band_gross_capped defer    ", h(bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS, defer_flips=True)))
print("band_gross_capped WIDE cap ", h(bf.band_gross_capped(T0, BAND_WIDTH, MAX_GROSS_STRESS)))
