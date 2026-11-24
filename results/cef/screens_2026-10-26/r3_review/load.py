"""Review harness: load the gated context of exdate_screen.setup() with every write redirected
under r3_review/ (PANELS, OUT). Nothing in r3_c4_exdate/ is written. CRSP stays in memory."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REV = Path(__file__).resolve().parent
SCR = REV.parent
sys.path.insert(0, str(SCR / "r3_c4_exdate"))
import exdate_screen as xs   # noqa  (chdirs to tree)
xs.PANELS = REV / "_panels"
xs.OUT = REV / "out"
c4 = xs.c4

def load():
    ctx = xs.setup()
    crsp, qr, pool, idx = ctx["crsp"], ctx["qr"], ctx["pool"], ctx["idx"]
    ctx["RETp"] = c4.crsp_pivot(crsp, pool, idx, qr, "ret", check_identity=False)
    ctx["RETXp"] = c4.crsp_pivot(crsp, pool, idx, qr, "retx", check_identity=False)
    return ctx
