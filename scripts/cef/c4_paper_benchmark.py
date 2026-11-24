"""C4 on paper, step 2: the frozen spec's fidelity to trial 52, its own gross cap, and the H11 lines.

    python3 scripts/cef/c4_paper_benchmark.py stage      # copy the trial's gitignored CRSP extract and Alpaca read in (read-only source)
    python3 scripts/cef/c4_paper_benchmark.py run        # all three; ~4 min; writes results/cef/c4/c4_paper_benchmark_<STAMP>.{txt,json}
                                                         #   and c4_paper_fidelity_<STAMP>.csv (STAMP below)
    python3 scripts/cef/c4_paper_benchmark.py fidelity   # the fidelity check alone (no CRSP needed); prints, writes nothing
    python3 scripts/cef/c4_paper_benchmark.py seed-rulings   # writes results/cef/c4/c4_seed_rulings_2026-10-29.json (IGR, step 3)
    python3 scripts/cef/c4_paper_benchmark.py recap --probe results/ops/alpaca_probe/<date>_c4.json --mark-sensitivity X
                                                         # the cap re-derived from a fresh account read (ruling 3) on the
                                                         #   live spec book's w5: exit 0 SAME, 2 OVERRIDE ON RECORD, 1 STOP

WHY THIS EXISTS. The team lead fast-tracked C4 (CEF trial 52) to paper on 2026-10-28 and keeps
every gate. Plan `results/cef/C4_DEPLOY_PLAN_2026-10-27.md` §2 step 2 is row 2 (the frozen spec,
`ops/specs/c4_families.frozen.json`) with a fidelity test against `build_book` (row 9), and row 10
needs the price-only and total-return benchmark lines for H11 (PREREG_C4 §14). This step enabled
nothing. (Since the C4 integration of 2026-10-29 the spec has its own book json,
ops/books/c4_families_book.json, and runner entry, run.BOOKS["c4"], which row 6A prices and gates
on data/cef_c4/; nothing schedules it until install_vm --book c4.)

1. FIDELITY (plan row 9; PREREG_C4 §14 "the live target must equal the trial script's target on
   the same panel"). On a fixed set of fit-window sessions -- every FIDELITY_STEP-th session of the
   trial's own target index from 2005-01-03, and its last, 2022-12-30 -- the LIVE sleeve, built
   from the frozen spec THROUGH THE REGISTRY (`registry.build_sleeve`, which validates first), is
   asked for its book, and its target is compared with `c4_families.build_book`'s T on the same
   panel, name by name.

   WHERE THE TWO ARE COMPARED, AND WHY THERE. `build_book` returns the frictionless pre-band
   target: z-score, eligibility, the min_names hold, the vol scalar. The sleeve computes the same
   object and then applies `min_abs_weight` (drop and re-neutralise), the band against what the
   account HOLDS and the gross cap, and emits whole shares through the runner. Those are PREREG_C4
   §3 items 5 and 6, declared before the trial ran. So the comparison point is the sleeve's `w` at
   the instant it reads `min_abs_weight`. `Probe` captures it there without changing a line of the
   sleeve: it shadows the instance's `_req` and reads the caller's frame. If the sleeve is ever
   refactored so that frame is not `target_positions` or holds no `w`, the probe RAISES
   (`ProbeError`) rather than comparing something else.

   THE HOLD. Below `min_names` the trial holds its previous TARGET; the sleeve, with
   `below_min_names = "hold"`, holds its current SHARES and never reaches `min_abs_weight`
   (§3 item 6: the reference state is holdings live, the stored target in the trial; and step 1's
   declared divergence that `max_gross_stress` is effectively off while a hold lasts). A session
   matches as a hold when the sleeve's every target says `(below_min_names=hold)` AND the trial's
   row equals its previous row exactly (a trading row never does: the vol scalar moves daily).

   WHAT HALTS. Every other outcome is outside the declared divergences and raises
   `FidelityBreak`, naming the session, the kind (hold against trade, a name eligible on one side
   only, or a weight that differs) and the largest gap. Nothing at the target level is declared:
   §3 items 1, 3, 4 and 7-10 (the decide-time NAV defect, shortability, borrow, paper execution,
   non-NYSE prints, the shared cap, survivorship) cannot show on a historical panel; item 2 (the
   masks) is now in the spec; items 5 and 6 are excluded by where the comparison sits. The size of
   item 5 is reported beside it (names the dust filter would drop), never deciding.

   THE PANEL. Both sides read the same rows: `data/cef_families/` cut at 2022-12-30 ON READ (a
   parquet filter, so no 2023+ row is materialised) into a temporary directory. The trial's code
   reads the cut through `c4.FAM_DIR` / `c4.FAM_SRC`; the sleeve reads the universe's rows of it at
   the spec's own `panel_source` paths under a temporary root (`cefmod.REPO` patched), so the
   spec's value is used as written. The nine frozen funds with no pre-2023 row have no column in
   the cut and enter the trial's T as zero columns, which is what the full-panel run gives them
   before 2023; `trial_book` proves it by reproducing the committed fit to 1e-9.

   CEF TRIAL 54 (PREREG_C4_LEVEL_2026-11-02.md §1.3 test 6, added 2026-11-03). With the spec's
   `level_signal` set, the sleeve's `w` at the min_abs_weight read is the equal-risk blend of the z and
   the within-family level, so the trial side is the trial's blend (`spec_targets`, a line-for-line
   port of trial54.py's `level_targets`, unmasked), not build_book's z-only T. Absent, `spec_targets`
   returns T itself and every line here is as before. Two controls join the list (the key dropped, the
   risk share moved), and `band_width dropped` is then REFUSED by the registry, recorded as such. H11's
   reference becomes the blended spec book (§6.3), checked against the raw primary returns. The
   reproduction gate and the cap rule still read the trial's z T: the gate proves T is trial 52's, and
   the 1.90 cap was kept, not re-derived, for trial 54 (§3.3).

2. MAX_GROSS_STRESS (spec row 2: "its own max_gross_stress, re-derived by the frozen rule"). The
   rule is the one the core's 1.80 came from, pre-registered in
   `results/cef/PREREG_GROUP_CAP_2026-09-16.md` §3b and applied for Alpaca in
   `results/cef/PREREG_ALPACA_V7_2026-09-28.md` §3b (CEF trial 50):

       G_stress = (NLV - M_other) / (m + w5) / E_book,  cap = floor_0.05(lowest reading - mark sensitivity)

   w5 is the worst 5-session total-return loss per unit of gross held, of the UNCAPPED band
   (the cap is what is being derived), computed by the v7 script's own `w5`. Before it is pointed
   at C4 it must reproduce the core's recorded 13-name w5 (0.0425814, ending 2020-03-18) on the
   core panels cut at 2022-12-30; otherwise it raises. C4's window is its fit window, from its
   first held session (PREREG_C4 §7) to 2022-12-30: the core's read ran to its panel end, but no
   2023+ C4 return is computed here. The other inputs are rulings, not reads (no broker is
   called): stated with their sources in `CAP_INPUTS`. The team lead ruled on 2026-10-29 to keep
   the derived value (1.90), that adopting it spends no CEF trial, and that it is re-derived from a
   fresh account read before arming (the spec's `_max_gross_stress_note`).

3. THE H11 LINES (plan row 10; team lead 2026-10-26: "paper is scored against a price-only
   backtest, because paper charges shorts no distribution"). The fit's daily gross P&L on CRSP
   `ret` (total return, the trial's declared primary) and on CRSP `retx` (price only).
   THE H11 REFERENCE IS THE SPEC'S BOOK (`H11_BOOK`; team lead 2026-10-29): the band and the 1.90
   cap the spec trades, because paper trades that book and not the trial's 1.80 one. PREREG_C4
   §14's 120-session percentile and the drawdown stop read `h11_reference`. The trial's own book
   (cap 1.80) is computed only as the gate that proves T is the trial's (it reproduces the
   committed 1.217 and R-P 1.360) and is labelled so. Descriptive numbers only: §14 re-measures
   the percentile and the worst drawdown on the read date (H14), and no rule reads a number
   written here.

4. THE IGR SEED RULING (team lead 2026-10-29, for step 3's seed of `data/cef_c4/`). `seed-rulings`
   writes `results/cef/c4/c4_seed_rulings_2026-10-29.json`: the same four corrected IGR bars as the
   2026-10-19 corrected book (`c4_bar_rulings_2026-10-19.json`; result note §9), in the schema
   `data_guards.load_bar_rulings` reads, with every replaced cell logged (the families panel's
   value and Alpaca's raw bar, which `holdout_review_2026-10-18/corrected.py` used), and the
   standing rule that `guard_closes` accepts exactly those four cells and nothing else. It checks,
   before writing, that `guard_closes` over the whole families panel for the 74 finds exactly those
   four and no other bar.

FIT ONLY. Every frame that reaches a statistic is asserted to end by 2022-12-30
(`w4_artifacts._assert_fit` and `_fit_dates`). The 2023 holdout is not read.

LICENSED DATA. CRSP values are read from the gitignored `results/cef/c4/_cache_c4/` (staged from
the trial-c4 worktree by `stage`, sha256-checked) and never written; the outputs are portfolio
aggregates and counts.

NO SILENT FALLBACKS. A missing input raises naming it. The only numbers typed here are the
rule's ruled inputs (`CAP_INPUTS`), each with its source; every spec value is read from a spec.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.cef import band_frontier as bf              # noqa: E402
from scripts.cef import c4_families as c4                # noqa: E402
from src.deploy import registry                          # noqa: E402
from src.deploy.sleeve import MarketState                # noqa: E402
from src.deploy.sleeves import cef_discount as cefmod    # noqa: E402

SPEC_PATH = REPO / "ops" / "specs" / "c4_families.frozen.json"
# The date stamp of a run. 2026-10-29 was the run on c4_families.v1 (kept, committed); 2026-11-02
# the re-run on the spec as raised by CEF trial 53 (sizing_multiplier 1.27, branch c4-rel), then
# re-run the same day on amendment 1's v4 (1.26, branch trial53-amend1). The 1.27 outputs are in
# git at 8b14298. 2026-11-03 is the run on c4_families.v5.20261103 (CEF trial 54's level_signal):
# fidelity against the trial's blend, and H11's reference rebuilt on the blended spec book. The v4
# outputs (2026-11-02) are kept as they were.
STAMP = "2026-11-03"
OUT_TXT = c4.OUT_DIR / f"c4_paper_benchmark_{STAMP}.txt"
OUT_JSON = c4.OUT_DIR / f"c4_paper_benchmark_{STAMP}.json"
OUT_CSV = c4.OUT_DIR / f"c4_paper_fidelity_{STAMP}.csv"
FIT_END = c4.FIT_END
HOLDOUT_START = c4.HOLDOUT_START

# The C4 panel's paths, agreed for plan row 3 (step 3 builds them nightly): the families schema
# (`date open high low close volume ticker grp` / `date nav ticker`) under its own directory, so the
# core's `data/cef/` is never written for C4. Step 1's tests already use these names.
C4_PANEL = {"prices": "data/cef_c4/cef_prices.parquet", "nav": "data/cef_c4/cef_nav.parquet"}
FAMILY_FILES = ("cef_prices", "cef_nav", "cef_actions")
TOL = 1e-12                # float dust; on the fit the two sides agree to 0.0
FIDELITY_STEP = 5          # every fifth session of T's index, and its last: ~907 of 4,531
HOLD_TAG = "(below_min_names=hold)"

# The trial's gitignored inputs, from the worktree the trial ran in (`stage` copies them in).
STAGE_TREE = "trial-c4"
CRSP_SHA256 = "47f20b474ceb6ae49f6d268b48f4992c0037105ecc3f3c0a59a1a112830df665"   # r3 NOTE: `47f20b47…`
ASSETS = c4.CACHE / "alpaca_assets_2026-10-14T214033Z.json"   # the frozen read's raw rows (c4.FROZEN_READ_UTC)

# H11's reference book (team lead 2026-10-29): the spec's own band and cap, not the trial's.
H11_BOOK = "spec_book"

# The IGR seed ruling (team lead 2026-10-29): the corrected book's four bars, for step 3's seed.
SEED_RULINGS = c4.OUT_DIR / "c4_seed_rulings_2026-10-29.json"
SEED_COLUMNS = ("open", "high", "low", "close", "volume")       # what corrected.py replaced

# max_gross_stress: the rule's inputs that are RULINGS, not reads. Nothing here calls a broker.
CAP_STEP = 0.05
CAP_INPUTS = {
    "nlv_usd": (100_000.0, "ruled, not probe-read: C4's own $100k (team lead 2026-10-26, docs/SYSTEM.md §5), "
                           "the paper default in an account never traded (created 2026-09-29) [U until a probe reads it]"),
    "m_other_usd": (0.0, "C4's own account (team lead 2026-10-26). Since 2026-10-28 the agent lab shares it; "
                         "the lab book is not built and holds nothing there [U until a probe reads it]"),
    "mark_sensitivity": (0.0, "no other book's margin moves this account today; the core's reading "
                              "(PREREG_ALPACA_V7 §3b)"),
}
# m is the core's ruled input, read from the v7 script rather than retyped: Reg T initial 0.50.


class FidelityBreak(AssertionError):
    """The live sleeve and the trial disagree outside the declared divergences. `.report` holds
    the whole comparison, so the caller can print it before stopping."""

    def __init__(self, msg: str, report: dict):
        super().__init__(msg)
        self.report = report


class ProbeError(RuntimeError):
    """The probe could not read the sleeve's target where it expects it: the sleeve changed."""


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _fit_dates(*frames) -> None:
    """H13: nothing that reaches a statistic or a comparison may carry a date after the fit."""
    for f in frames:
        idx = f.index if hasattr(f, "index") else pd.DatetimeIndex(f)
        if len(idx) and pd.Timestamp(idx.max()) > FIT_END:
            raise AssertionError(f"a frame reaches {pd.Timestamp(idx.max()).date()}, after the fit end "
                                 f"{FIT_END.date()}; the 2023 holdout is not read here")


# --------------------------------------------------------------------------- spec

def load_spec(path: Path = SPEC_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing; it is C4's frozen spec (plan row 2)")
    return json.loads(path.read_text())


def build_sleeve(spec: dict):
    """The sleeve the runner would build: the registry's, which validates the spec first."""
    sl = registry.build_sleeve(spec, float(spec["capital_usd"]))
    if not isinstance(sl, cefmod.CEFDiscountSleeve):
        raise TypeError(f"spec {spec.get('spec_id')!r} built {type(sl).__name__}, not the cef_discount sleeve")
    return sl


def with_keys(spec: dict, drop=(), **keys) -> dict:
    """A deep copy of `spec` with frozen keys set or dropped (the negative controls and tests)."""
    s = json.loads(json.dumps(spec))
    for k in drop:
        if k not in s["frozen"]:
            raise KeyError(f"cannot drop {k!r}: the spec has no such frozen key")
        del s["frozen"][k]
    s["frozen"].update(keys)
    return s


# --------------------------------------------------------------------------- panels

def cut_families(dst: Path, lo=None, hi=FIT_END, src_dir: Path | None = None) -> dict:
    """Copy `data/cef_families/{prices, nav, actions}` cut to [lo, hi] into `dst`, filtering ON
    READ so no row after `hi` is ever materialised. `hi` may not pass the fit end. `lo` is for the
    tests' short panels (both sides then see the same short history). Returns rows and last date."""
    hi = pd.Timestamp(hi)
    if hi > FIT_END:
        raise AssertionError(f"cut end {hi.date()} is after the fit end {FIT_END.date()}")
    src_dir = c4.FAM_DIR if src_dir is None else src_dir
    dst.mkdir(parents=True, exist_ok=True)
    out = {}
    for f in FAMILY_FILES:
        flt = [("date", "<=", hi)] + ([("date", ">=", pd.Timestamp(lo))] if lo is not None else [])
        src = src_dir / f"{f}.parquet"
        if not src.exists():
            raise FileNotFoundError(f"{src} is missing (built by scripts/data/fetch_cef_families_yf.py)")
        d = pd.read_parquet(src, filters=flt)
        if not len(d):
            raise ValueError(f"{src.name}: no row in {lo}..{hi.date()}")
        last = pd.to_datetime(d["date"]).max()
        if last > hi:
            raise AssertionError(f"{src.name}: the filtered read returned {last.date()} > {hi.date()}")
        if f != "cef_actions" and d.duplicated(["ticker", "date"]).any():
            raise ValueError(f"{src.name}: two rows for one (ticker, date); M1's previous row is ambiguous")
        d.to_parquet(dst / f"{f}.parquet")
        out[f] = {"rows": int(len(d)), "last": str(last.date())}
    return out


@contextlib.contextmanager
def trial_reads(cut: Path):
    """The trial's own code reading the cut: `c4.FAM_DIR` and `c4.FAM_SRC` pointed at it, and the
    module's cache of paired funds emptied on the way in and out (it is filled from FAM_SRC)."""
    old = (c4.FAM_DIR, c4.FAM_SRC)
    c4.FAM_DIR, c4.FAM_SRC = cut, (cut / "cef_prices.parquet", cut / "cef_nav.parquet")
    c4._PAIRED.clear()
    try:
        yield
    finally:
        c4.FAM_DIR, c4.FAM_SRC = old
        c4._PAIRED.clear()


def trial_targets(cut: Path) -> tuple[pd.DataFrame, dict]:
    """The trial's T on the cut panel, over the frozen 74: `c4.build_book` (the declared M1|M2
    masks, `band_frontier.build_targets` with every parameter from `scripts/cef/spec.py`, as the
    trial read them), then `fit_slice`. Funds with no paired row in the cut enter as zero columns."""
    with trial_reads(cut):
        UF = c4.universes()["frozen"]
        have = set(bf.build_panel(universe=UF, source=c4.FAM_SRC)["px"].columns)
        UFd = [t for t in UF if t in have]
        T = c4.fit_slice(c4.build_book(UFd)).reindex(columns=UF, fill_value=0.0)
    _fit_dates(T)
    return T, {"universe": UF, "with_rows": UFd, "without_rows": sorted(set(UF) - have)}


def spec_targets(cut: Path, T: pd.DataFrame, spec: dict, level_only: bool = False) -> pd.DataFrame:
    """The trial-side unit target the spec's sleeve must reproduce: `T` itself when the spec carries
    no `level_signal` (byte for byte: the same object is returned), and CEF trial 54's blend when it
    does (PREREG_C4_LEVEL_2026-11-02.md §1.2; §1.3 test 6). `level_only` returns the level book with
    its own vol scalar instead (§6.2 P1's level-only book, which L1 reads).

    WHY THE PROBE NEEDS IT. The probe reads the sleeve's `w` at the `min_abs_weight` read. With the key
    set that `w` is the blend, and against build_book's z-only T every trading session would break. The
    trial's blend is the comparison, so this builds it from the trial's own machinery on the same cut.

    THE CONSTRUCTION IS THE TRIAL'S, LINE FOR LINE: `level_targets` in
    results/cef/prereg_c4_level/trial54.py (branch trial54-run at 62f006d), with no DG-L3 level masks
    and no placebo. Those are the trial's research inputs, and the sleeve has neither: DG-L4 compared
    the sleeve at 3b4c963 with exactly this unmasked blend, 907 of 907 sessions both ways. On each
    session of T's index:
      * eligible = a z-score on t and ADV through t-1 at or above the spec's floor (`build_targets`'
        rule). With fewer than min_names, hold the previous row, as build_targets and the sleeve's
        `below_min_names = "hold"` do;
      * w_z = -(z - mean z), unit gross; w_L = -(disc - family mean disc) on the same names, unit
        gross, a family with fewer than 2 eligible names contributing zero;
      * s_z, s_L, s_mix = today's weights on the last VOL_LOOKBACK price returns through t, over the
        panel's WHOLE history (the DG-L4 fix of 2026-11-03: a window cut at the fit index's first day
        broke 6 sessions in 2005);
      * mix = risk_share w_z / s_z + (1 - risk_share) w_L / s_L, unit gross; then
        T_B = mix x clip(vol_target / s_mix, 0.2, 2.5).
    risk_share and the vol target are read from the spec. The family map is the frozen CSV, the file
    the trial read, and it must equal the spec's `family_of`. If they differ, this raises: the probe
    would then be comparing two different books.

    WHERE THE TRIAL AND THE SLEEVE DIFFER, both outside anything the fit can show. On a session where
    the level book has no gross, or a vol is not positive, the trial holds its previous row and the
    sleeve RAISES. With 5 families and min_names 6 the first cannot happen: by pigeonhole some family
    has two eligible names. Neither happens on the fit.

    H7: row t reads z, disc and ADV on t (z's mean and sd end at t-1, ADV is shifted one session) and
    returns through t, nothing later; `_fit_dates` asserts no row passes the fit end."""
    lv = registry.cef_level_signal(spec["frozen"])
    if lv is None:
        if level_only:
            raise ValueError(f"spec {spec.get('spec_id')!r} carries no level_signal; there is no level book")
        return T
    f = spec["frozen"]
    fam_csv = pd.read_csv(c4.FROZEN).set_index("ticker")["family"]
    if fam_csv.to_dict() != lv["family_of"]:
        diff = sorted(t for t in set(fam_csv.index) | set(lv["family_of"])
                      if fam_csv.get(t) != lv["family_of"].get(t))
        raise ValueError(f"the spec's level_signal.family_of differs from {c4.FROZEN.name} for {diff[:10]}; the "
                         f"trial read the file, the sleeve reads the spec, so the probe would compare two books")
    with trial_reads(cut):
        UF = c4.universes()["frozen"]
        have = set(bf.build_panel(universe=UF, source=c4.FAM_SRC)["px"].columns)
        UFd = [t for t in UF if t in have]
        p = bf.build_panel(universe=UFd, source=c4.FAM_SRC, mask=c4.declared_mask(UFd, "M1M2"))
    idx = T.index
    RF = p["ret"][UFd].to_numpy()
    posF = p["ret"].index.get_indexer(idx)
    if (posF < 0).any() or not (p["ret"].index[posF] == idx).all():
        raise AssertionError("T's index is not a subset of the panel's own index")
    z, adv, disc = (p[k].reindex(idx)[UFd] for k in ("z", "adv", "disc"))
    floor, n_min = float(f["min_adv_usd"]), int(f["min_names"])
    vt, rs = float(f["vol_target_annual"]), float(lv["risk_share"])
    famv = fam_csv.reindex(UFd).to_numpy()

    def rv(j, w):
        h = np.nansum(RF[max(0, j - bf.VOL_LOOKBACK + 1):j + 1] * w, axis=1)
        return float(np.std(h, ddof=1) * np.sqrt(252)) if len(h) > 1 else np.nan

    def sc(x):                                            # build_targets' scalar, and the trial's
        return float(np.clip(vt / x, 0.2, 2.5)) if x and x > 0 else 1.0

    TL, TB = np.zeros((len(idx), len(UFd))), np.zeros((len(idx), len(UFd)))
    for i in range(len(idx)):
        zr = z.iloc[i].to_numpy()
        ok = np.isfinite(zr) & (adv.iloc[i].fillna(-1).to_numpy() >= floor)
        if ok.sum() < n_min:
            if i:
                TL[i], TB[i] = TL[i - 1], TB[i - 1]
            continue
        zz = np.where(ok, zr, np.nan)
        wz = np.where(ok, -(zz - np.nanmean(zz)), 0.0)
        wz = wz / np.abs(wz).sum()
        dv = np.where(ok, disc.iloc[i].to_numpy(), np.nan)
        wl = np.zeros(len(UFd))
        for g in pd.unique(famv[ok]):
            sel = ok & (famv == g) & np.isfinite(dv)
            if sel.sum() >= 2:
                wl[sel] = -(dv[sel] - dv[sel].mean())
        if np.abs(wl).sum() == 0:
            if i:
                TL[i], TB[i] = TL[i - 1], TB[i - 1]
            continue
        wl = wl / np.abs(wl).sum()
        j = posF[i]
        s_z, s_l = rv(j, wz), rv(j, wl)
        TL[i] = wl * sc(s_l)
        if not (s_z > 0 and s_l > 0):
            TB[i] = TB[i - 1] if i else 0.0
            continue
        mix = rs * wz / s_z + (1 - rs) * wl / s_l
        mix = mix / np.abs(mix).sum()
        TB[i] = mix * sc(rv(j, mix))
    out = pd.DataFrame(TL if level_only else TB, index=idx, columns=UFd).reindex(columns=T.columns, fill_value=0.0)
    _fit_dates(out)
    return out


def sleeve_root(cut: Path, spec: dict, root: Path) -> dict:
    """Lay the universe's rows of the cut at the spec's own `panel_source` paths under `root`, so
    the sleeve reads the trial's rows through the spec's value as written."""
    src = registry.cef_panel_source(spec["frozen"])
    if src is None:
        raise ValueError(f"spec {spec.get('spec_id')!r} has no panel_source; C4's spec must name its panel")
    uni = set(spec["frozen"]["universe"])
    out = {}
    for name, rel in zip(("cef_prices", "cef_nav"), src):
        d = pd.read_parquet(cut / f"{name}.parquet")
        d = d[d["ticker"].isin(uni)]
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        d.to_parquet(dst)
        out[rel] = int(len(d))
    return out


@contextlib.contextmanager
def repo_root(root: Path):
    """`cefmod.REPO` pointed at `root`: `panel_paths()` resolves `panel_source` against it."""
    old = cefmod.REPO
    cefmod.REPO = root
    try:
        yield
    finally:
        cefmod.REPO = old


# --------------------------------------------------------------------------- the probe

class Probe:
    """Reads the sleeve's target at the moment it asks for `min_abs_weight`.

    The sleeve's `target_positions` computes `w = w * scal * gross_leverage` and then reads
    `min_abs_weight`; that `w` is the object `build_targets` returns (module docstring). The
    instance's `_req` is shadowed (this object only; the class is untouched) and, on that one key,
    the caller's frame is read. It must be `CEFDiscountSleeve.target_positions` itself, hold a
    Series `w`, and ask once per decide; otherwise `ProbeError`."""

    def __init__(self, sleeve):
        if not isinstance(sleeve, cefmod.CEFDiscountSleeve):
            raise TypeError(f"Probe reads the cef_discount sleeve, not {type(sleeve).__name__}")
        self.sleeve = sleeve
        self._orig = sleeve._req
        self._code = cefmod.CEFDiscountSleeve.target_positions.__code__
        self.seen = None
        sleeve._req = self._req

    def _req(self, key):
        value = self._orig(key)
        if key == "min_abs_weight":
            frame = sys._getframe(1)
            try:
                if frame.f_code is not self._code:
                    raise ProbeError(f"min_abs_weight was read from {frame.f_code.co_name}, not "
                                     "CEFDiscountSleeve.target_positions; the probe no longer knows what it reads")
                if self.seen is not None:
                    raise ProbeError("min_abs_weight was read twice in one decide")
                w = frame.f_locals.get("w")
                if not isinstance(w, pd.Series):
                    raise ProbeError(f"target_positions holds no Series `w` where it reads min_abs_weight "
                                     f"(found {type(w).__name__})")
                if w.isna().any():
                    raise ProbeError(f"the sleeve's target holds NaN for {sorted(w.index[w.isna()])}")
                self.seen = {"w": w.astype(float).copy(), "scal": float(frame.f_locals["scal"])}
            finally:
                del frame
        return value

    def decide(self, asof) -> dict:
        """One decide on `asof` from a flat book (holdings empty: the comparison is of targets, and
        a hold then emits no order). Returns {kind: trade | hold | other, w, scal, reasons}."""
        self.seen = None
        ts = pd.Timestamp(asof)
        ms = MarketState(asof=ts, prices=pd.DataFrame(), holdings={},
                         extras={"sleeve_nav": float(self.sleeve.capital_usd)})
        out = self.sleeve.target_positions(ts, ms)
        reasons = sorted({t.reason for t in out})
        if self.seen is not None:
            return {"kind": "trade", "w": self.seen["w"], "scal": self.seen["scal"], "reasons": reasons}
        if out and all(HOLD_TAG in t.reason for t in out):
            return {"kind": "hold", "w": None, "scal": None, "reasons": reasons}
        return {"kind": "other", "w": None, "scal": None, "reasons": reasons}


# --------------------------------------------------------------------------- fidelity

def fidelity_dates(T: pd.DataFrame, step: int = FIDELITY_STEP) -> list[pd.Timestamp]:
    """Every `step`-th session of the trial's index from its first, and its last. Fit only."""
    idx = T.index
    d = list(idx[::step])
    if d[-1] != idx[-1]:
        d.append(idx[-1])
    _fit_dates(pd.DatetimeIndex(d))
    return d


def _trial_kind(T: pd.DataFrame, i: int) -> str:
    """build_targets holds its previous target below min_names; a trading row always moves."""
    row = T.iloc[i]
    if i == 0:
        return "hold" if (row == 0).all() else "trade"
    return "hold" if row.equals(T.iloc[i - 1]) else "trade"


def fidelity(spec: dict, cut: Path, dates, T: pd.DataFrame | None = None, root: Path | None = None,
             first_break: bool = False) -> dict:
    """The live sleeve under `spec` against the trial's T on `cut`, on `dates`. Returns the report;
    raises FidelityBreak (carrying it) on any difference outside the declared divergences.
    `first_break` stops at the first one (the negative controls)."""
    dates = [pd.Timestamp(d) for d in dates]
    if not dates:
        raise ValueError("no dates to compare")
    _fit_dates(pd.DatetimeIndex(dates))
    if T is None:
        T, _ = trial_targets(cut)
    uni = sorted(spec["frozen"]["universe"])
    if sorted(T.columns) != uni:
        raise ValueError(f"the trial's T covers {len(T.columns)} funds and the spec {len(uni)}; "
                         f"not the same universe: {sorted(set(T.columns) ^ set(uni))[:10]}")
    minw = float(spec["frozen"]["min_abs_weight"])
    tmp = None
    if root is None:
        tmp = tempfile.TemporaryDirectory(prefix="c4_sleeve_root_")
        root = Path(tmp.name)
        sleeve_root(cut, spec, root)
    rows, breaks = [], []
    try:
        with repo_root(root):
            probe = Probe(build_sleeve(spec))
            for d in dates:
                if d not in T.index:
                    raise ValueError(f"{d.date()} is not a session of the trial's index")
                i = T.index.get_loc(d)
                tk = _trial_kind(T, i)
                got = probe.decide(d)
                want = T.iloc[i][uni]
                r = dict(date=str(d.date()), trial=tk, sleeve=got["kind"], n_trial=int((want != 0).sum()),
                         n_sleeve=None, cells=0, cells_matched=0, max_gap=None, sub_min_abs=0, match=False, why="")
                if got["kind"] == "trade":
                    w = got["w"].reindex(uni).fillna(0.0)
                    stray = sorted(set(got["w"].index) - set(uni))
                    if stray:
                        raise ProbeError(f"the sleeve's target names {stray}, outside the spec's universe")
                    gap = (w - want).abs()
                    r.update(n_sleeve=int((w != 0).sum()), cells=len(uni), cells_matched=int((gap <= TOL).sum()),
                             max_gap=float(gap.max()), sub_min_abs=int(((w != 0) & (w.abs() < minw)).sum()))
                if tk == "hold" and got["kind"] == "hold":
                    r.update(match=True, why="both hold (declared: PREREG_C4 §3 item 6; step 1's hold)")
                elif tk == "trade" and got["kind"] == "trade":
                    if r["max_gap"] <= TOL:
                        r.update(match=True, why="equal")
                    else:
                        only = sorted(set(w.index[(w != 0) & (want == 0)]) | set(w.index[(w == 0) & (want != 0)]))
                        kind = "eligibility" if only else "weight"
                        worst = gap.idxmax()
                        r["why"] = (f"{kind}: largest gap {r['max_gap']:.3e} on {worst} (sleeve {w[worst]:+.6f}, "
                                    f"trial {want[worst]:+.6f})" + (f"; on one side only: {only[:6]}" if only else ""))
                        breaks.append(dict(date=r["date"], kind=kind, gap=r["max_gap"], ticker=worst,
                                           sleeve=float(w[worst]), trial=float(want[worst]), detail=r["why"]))
                else:
                    does = {"hold": "holds", "trade": "trades", "other": "does neither"}[got["kind"]]
                    r["why"] = (f"kind: the trial {'holds' if tk == 'hold' else 'trades'} and the sleeve "
                                f"{does} ({'; '.join(got['reasons'])[:160]})")
                    breaks.append(dict(date=r["date"], kind="kind", gap=None, ticker=None, sleeve=None,
                                       trial=None, detail=r["why"]))
                rows.append(r)
                if breaks and first_break:
                    break
    finally:
        if tmp is not None:
            tmp.cleanup()
    rep = summarise(rows, breaks, spec)
    if breaks:
        b = breaks[0]
        raise FidelityBreak(f"FIDELITY BREAK on {len(breaks)} of {len(rows)} session(s) compared; first "
                            f"{b['date']}: {b['detail']}", rep)
    return rep


def summarise(rows: list, breaks: list, spec: dict) -> dict:
    trade = [r for r in rows if r["sleeve"] == "trade" and r["trial"] == "trade"]
    cells = sum(r["cells"] for r in trade)
    matched = sum(r["cells_matched"] for r in trade)
    nz = sum(r["n_sleeve"] for r in trade)
    gaps = [r["max_gap"] for r in rows if r["max_gap"] is not None]
    weight_breaks = [b for b in breaks if b["gap"] is not None]
    worst = max(weight_breaks, key=lambda b: b["gap"]) if weight_breaks else None
    return dict(
        spec_id=spec.get("spec_id"), sessions=len(rows),
        first=rows[0]["date"] if rows else None, last=rows[-1]["date"] if rows else None,
        trade_sessions=sum(r["trial"] == "trade" for r in rows), hold_sessions=sum(r["trial"] == "hold" for r in rows),
        sessions_matched=sum(r["match"] for r in rows),
        session_match_rate=(sum(r["match"] for r in rows) / len(rows)) if rows else None,
        cells_compared=cells, cells_matched=matched, cell_match_rate=(matched / cells) if cells else None,
        largest_gap=max(gaps) if gaps else None, tolerance=TOL,
        largest_unexplained_gap=worst, kind_breaks=sum(b["kind"] == "kind" for b in breaks),
        breaks=breaks[:25], n_breaks=len(breaks),
        item5_sub_min_abs_names=sum(r["sub_min_abs"] for r in trade), item5_of_held_names=nz,
        item5_sessions=sum(r["sub_min_abs"] > 0 for r in trade), min_abs_weight=float(spec["frozen"]["min_abs_weight"]),
        rows=rows)


def m2_footprint(cut: Path, spec: dict) -> dict:
    """What M2 can ever mask on the cut, for the universe: paired fund-days with zero volume, and
    how many of them sit on a fund-day whose ADV (through t-1) clears the spec's floor, i.e. could
    have been eligible. Zero of the second means M2 off cannot move an eligible fund's day; it can
    still drop a day from a z-window history, which the control run measures directly."""
    f = spec["frozen"]
    p = bf.build_panel(universe=list(f["universe"]), source=(cut / "cef_prices.parquet", cut / "cef_nav.parquet"))
    m2 = p["vol"].reindex_like(p["px"]).eq(0) & p["px"].notna()
    liquid = p["adv"].reindex_like(m2).ge(float(f["min_adv_usd"]))
    hit = m2.stack()
    hit = hit[hit]
    return {"cells": int(m2.sum().sum()), "cells_with_adv_at_floor": int((m2 & liquid).sum().sum()),
            "funds": sorted(set(hit.index.get_level_values(1)))}


def controls(spec: dict) -> list[tuple[str, dict]]:
    """Specs that must NOT pass: a mask off, the hold off, and each signal parameter moved. Every
    changed value is derived from the spec's own (never a literal); `band_width` dropped is the
    calendar the sleeve falls back to."""
    f = spec["frozen"]
    return [("nav_repeat_mask off", with_keys(spec, nav_repeat_mask=False)),
            ("zero_volume_mask off", with_keys(spec, zero_volume_mask=False)),
            ("below_min_names flatten", with_keys(spec, below_min_names="flatten")),
            (f"z_window {f['z_window']} -> {f['z_window'] - 1}", with_keys(spec, z_window=f["z_window"] - 1)),
            ("vol_target_annual x 1.1", with_keys(spec, vol_target_annual=f["vol_target_annual"] * 1.1)),
            ("min_adv_usd x 0.9", with_keys(spec, min_adv_usd=f["min_adv_usd"] * 0.9)),
            (f"min_names {f['min_names']} -> {f['min_names'] + 1}", with_keys(spec, min_names=f["min_names"] + 1)),
            ("gross_leverage x 1.1", with_keys(spec, gross_leverage=f["gross_leverage"] * 1.1)),
            ("band_width dropped (the rebalance_days calendar)", with_keys(spec, drop=("band_width",)))] + (
        # CEF trial 54: the blend's own controls. Dropping the key is the z book alone; moving the
        # risk share moves the blend. With the key set, `band_width dropped` above is REFUSED by the
        # registry before the probe runs (cef_level_signal: the blend is defined through the band),
        # which `run_controls` records as a refusal, stronger than a break.
        [] if "level_signal" not in f else
        [("level_signal dropped (the z book alone)", with_keys(spec, drop=("level_signal", "_level_signal_note"))),
         (f"level_signal.risk_share {f['level_signal']['risk_share']} x 1.1",
          with_keys(spec, level_signal=dict(f["level_signal"],
                                            risk_share=float(f["level_signal"]["risk_share"]) * 1.1)))])


# --------------------------------------------------------------------------- CRSP, the trial's book, the lines

def stage() -> dict:
    """Copy the trial's gitignored inputs from its worktree (read-only source), verified."""
    from scripts.research.backfill.backfill import copy_verified, trial_tree
    src_root = trial_tree(STAGE_TREE)
    done = {}
    for dst in (c4.CRSP_RET, ASSETS, c4.ALP_POOL, c4.ALP_POOL_META):
        rel = dst.relative_to(REPO)
        done[str(rel)] = copy_verified(src_root / rel, dst)
        if subprocess.run(["git", "check-ignore", "-q", str(rel)], cwd=REPO).returncode != 0:
            raise RuntimeError(f"{rel} is not gitignored; licensed or vendor data must never be tracked")
    if _sha(c4.CRSP_RET) != CRSP_SHA256:
        raise ValueError(f"{c4.CRSP_RET.name}: sha256 is not the extract the trial and the r3 screen read")
    return done


def crsp_fit(pool) -> pd.DataFrame:
    """The trial's CRSP extract, rows <= 2022-12-30 only (parquet filter), sha-checked first."""
    if not c4.CRSP_RET.exists():
        raise FileNotFoundError(f"{c4.CRSP_RET} is missing; run `python3 scripts/cef/c4_paper_benchmark.py stage`")
    got = _sha(c4.CRSP_RET)
    if got != CRSP_SHA256:
        raise ValueError(f"{c4.CRSP_RET.name}: sha256 {got[:16]}... is not the trial's extract {CRSP_SHA256[:16]}...")
    c = pd.read_parquet(c4.CRSP_RET, filters=[("date", "<=", FIT_END)])
    c["date"] = pd.to_datetime(c["date"])
    _fit_dates(c.set_index("date"))
    missing = sorted(set(pool) - set(c["ticker"]))
    if missing:
        raise ValueError(f"the CRSP extract has no fit rows for pool funds {missing}")
    return c[c["ticker"].isin(pool)].copy()


def trial_book(cut: Path, T: pd.DataFrame) -> dict:
    """The trial's book and returns on the cut, gated: the committed fit gross Sharpe and the
    committed R-P (price-only) Sharpe must reproduce to 1e-9, or this raises. The gate is what makes
    T *the trial's* T rather than a lookalike."""
    from scripts.cef import w4_artifacts as w4
    committed = json.loads(c4.FIT_JSON.read_text())
    want_total = float(committed["stage1"]["gross_sr"])
    want_price = float(next(r["sr"] for r in committed["robustness"] if r["book"].startswith("R-P")))
    with trial_reads(cut):
        U = c4.universes()
        pool, UF = U["pool"], U["frozen"]
        px, _nav = c4.load_panels(pool)
        crsp = crsp_fit(pool)
        qr = c4.qqqx_rule(crsp, px)
        if not qr["use_predecessor"]:
            raise RuntimeError("the QQQX rule's decision differs from the fit's")
        R_ret = c4.crsp_pivot(crsp, pool, T.index, qr, "ret", px=px)
        R_retx = c4.crsp_pivot(crsp, pool, T.index, qr, "retx", px=px)
        w4._assert_fit(T.index, R_ret, R_retx)
        row, P, H, R0, p0, _ = c4.run_book("C4 (74, declared)", UF, R_ret, T=T)
        rowx, Px, Hx, R0x, p0x, _ = c4.run_book("R-P (CRSP retx: price returns)", UF, R_retx, T=T)
    for lab, got, want in (("total-return fit gross SR", row["sr"], want_total),
                           ("price-only (R-P) fit gross SR", rowx["sr"], want_price)):
        if abs(got - want) > 1e-9:
            raise RuntimeError(f"GATE FAIL: {lab} {got!r} != committed {want!r}; this T is not the trial's")
    if not (Hx.equals(H) and p0x == p0):
        raise AssertionError("the price-only line is not on the same book")
    _fit_dates(P, Px, R0, R0x)
    # R_raw / Rx_raw: the primary returns BEFORE check_held filled the z book's unheld NaN cells with 0.
    # Any other book (the level blend, CEF trial 54) is checked against these, never against R0, whose
    # zeros would let a held name meet a missing return in silence (H15).
    return dict(H=H, R0=R0, R0x=R0x, p0=p0, UF=UF, total_sr=row["sr"], price_sr=rowx["sr"],
                R_raw=R_ret[list(UF)].reindex(T.index), Rx_raw=R_retx[list(UF)].reindex(T.index))


def line(H: pd.DataFrame, R: pd.DataFrame, label: str) -> dict:
    """One benchmark line: gross P&L from the book's first held session to the fit end, its cost
    grid (H3; labelled, never mixed in), drawdown and eras (H5). Descriptive (H14)."""
    r = bf.evaluate(H, R)
    held = H.shift(2).abs().sum(axis=1)
    p0 = held.index[held > 0][0]
    P, TU = r["pnl"].loc[p0:FIT_END], r["turn_series"].loc[p0:FIT_END]
    _fit_dates(P, TU)
    eq = (1 + P).cumprod()
    dd = eq / eq.cummax() - 1
    s = c4.row_stats(P, TU)
    eras = {lab: c4.row_stats(P.loc[a:b], TU.loc[a:b]) for lab, a, b in c4.FIT_ERAS if len(P.loc[a:b]) > 20}
    return dict(label=label, first_held=str(p0.date()), last=str(P.index[-1].date()), **s,
                max_dd_pct=float(dd.min() * 100), max_dd_trough=str(dd.idxmin().date()),
                eras={k: {kk: v[kk] for kk in ("sr", "ann_pct", "turn", "net15", "net30", "flips", "days")}
                      for k, v in eras.items()},
                _P=P)


def h11_reference(tb: dict, spec: dict) -> dict:
    """H11's reference book (team lead 2026-10-29): the book the spec trades -- the trial's T under
    the SPEC's band and the SPEC's own max_gross_stress (1.90), not the trial's 1.80 -- with its
    total-return and price-only returns, each checked by `c4.check_held`. PREREG_C4 §14's
    120-session percentile (price-only against the official-fill line; total return against the
    distribution-adjusted line) and the drawdown stop read this book. Fit window here; the read
    date adds the holdout series by the same construction."""
    f = spec["frozen"]
    if "max_gross_stress" not in f:
        raise KeyError(f"{spec.get('spec_id')} has no max_gross_stress; H11 reads the spec's own cap")
    # CEF trial 53: with `sizing_multiplier` m set, the account holds m x the unit book, banded
    # on held / m and capped at max_gross_stress / m in unit weights (cef_discount.py). H11 reads
    # THAT book, so its percentile and its fit-worst drawdown are in the account's own units.
    # Absent, the line below is today's reference, unchanged.
    m = f.get("sizing_multiplier")
    cap = float(f["max_gross_stress"])
    # CEF trial 54 (PREREG_C4_LEVEL §6.3: C4's kill rule "rebuilt on the blended spec book"). With
    # `level_signal` set, the book the spec trades is the BLEND (`spec_targets`), so H11 reads that,
    # and it is checked against the raw primary returns (`trial_book`'s R_raw), never against the z
    # book's zero-filled R0. Absent, T and R0 as before, unchanged.
    lv = registry.cef_level_signal(f)
    if lv is not None:
        if "T_spec" not in tb or "R_raw" not in tb:
            raise KeyError(f"{spec.get('spec_id')} sets level_signal: H11 reads the blended spec book, and "
                           f"`tb` carries no T_spec (spec_targets) or no raw returns (trial_book)")
        T, R_src, Rx_src = tb["T_spec"], tb["R_raw"], tb["Rx_raw"]
    else:
        T, R_src, Rx_src = tb["T"], tb["R0"], tb["R0x"]
    if m is None:
        H = bf.band_gross_capped(T, float(f["band_width"]), cap)
    else:
        H = float(m) * bf.band_gross_capped(T, float(f["band_width"]), cap / float(m))
    R = c4.check_held(H, R_src.reindex(columns=H.columns), "H11 reference, total")
    Rx = c4.check_held(H, Rx_src.reindex(columns=H.columns), "H11 reference, price-only")
    _fit_dates(H, R, Rx)
    return {"H": H, "total": R, "price": Rx,
            "policy": f"band {f['band_width']} + cap {f['max_gross_stress']}"
                      + ("" if m is None else f" x sizing_multiplier {m}")
                      + ("" if lv is None else f" + level_signal (z_share {lv['risk_share']})")
                      + f" ({spec['spec_id']})"}


def lines(tb: dict, spec: dict) -> dict:
    """The H11 lines (total return and price only). `spec_book` is the H11 REFERENCE
    (`h11_reference`; team lead 2026-10-29). `trial_book` (the core's band and cap, as the trial
    read them) is the reproduction gate's book, shown for the divergence, and is NOT what H11 reads."""
    from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS
    ref = h11_reference(tb, spec)
    out = {"spec_book": {"role": "H11 REFERENCE (team lead 2026-10-29): the book paper trades",
                         "policy": ref["policy"],
                         "total": line(ref["H"], ref["total"], "spec book, CRSP ret (total return)"),
                         "price": line(ref["H"], ref["price"], "spec book, CRSP retx (price only)")},
           "trial_book": {"role": "the trial's own book: the reproduction gate only, NOT read by H11",
                          "policy": f"band {BAND_WIDTH} + cap {MAX_GROSS_STRESS} (scripts/cef/spec.py, as the trial read them)",
                          "total": line(tb["H"], tb["R0"], "trial book, CRSP ret (total return)"),
                          "price": line(tb["H"], tb["R0x"], "trial book, CRSP retx (price only)")}}
    if H11_BOOK not in out:
        raise KeyError(f"H11_BOOK {H11_BOOK!r} names no computed book")
    for b in out.values():
        leg = b["total"]["_P"] - b["price"]["_P"]
        b["distribution_leg_pct_per_yr"] = float(leg.mean() * 252 * 100)
        b["price_minus_total_sr"] = b["price"]["sr"] - b["total"]["sr"]
    return out


# --------------------------------------------------------------------------- max_gross_stress

def g_stress(nlv: float, m_other: float, m: float, w5: float, e_book: float) -> float:
    """PREREG_GROUP_CAP_2026-09-16 §3b: G_stress = (NLV - M_other) / (m + w5) / E_book."""
    if not (e_book > 0 and m + w5 > 0):
        raise ValueError(f"g_stress: E_book {e_book} and m + w5 {m + w5} must be positive")
    return (nlv - m_other) / (m + w5) / e_book


def floor_to(x: float, step: float = CAP_STEP) -> float:
    """The rule's rounding: DOWN to the step (a ceiling set above the arithmetic is no ceiling)."""
    return round(math.floor(x / step + 1e-12) * step, 2)


def core_w5_check(cut_core: Path) -> dict:
    """The v7 `w5`, on the core's 13 names and panels cut at 2022-12-30, must give the recorded
    13-name figure (0.0425814, ending 2020-03-18; the v7 note §3b) before it is trusted on C4."""
    from scripts.cef import alpaca_v7_derivation as v7
    from scripts.cef.spec import BAND_WIDTH, UNIVERSE
    from scripts.research.backfill.backfill import V7_COMMITTED, cut_parquet
    if len(UNIVERSE) != 13 or set(UNIVERSE) & set(v7.DROPPED):
        raise RuntimeError(f"the core universe is not the v7 13 ({len(UNIVERSE)} names); re-validate by hand")
    for f, col, empty in (("cef_prices", "date", False), ("cef_nav", "date", False),
                          ("cef_distributions", "ex_date", False), ("cef_splits", "ex_date", True)):
        cut_parquet(bf.DATA_DIR / f"{f}.parquet", cut_core / f"{f}.parquet", col, allow_empty=empty)
    old = bf.DATA_DIR
    bf.DATA_DIR = cut_core
    try:
        T13, R13 = bf.fit_only(*bf.build_targets(list(UNIVERSE)))
        Rt13 = bf.total_returns(R13)
        H13 = bf.band(T13, BAND_WIDTH)
        _fit_dates(T13, Rt13)
        w13, d13 = v7.w5(H13, Rt13)
    finally:
        bf.DATA_DIR = old
    got = (float(f"{w13:.7f}"), str(d13.date()))
    want = (V7_COMMITTED["w5_13"], V7_COMMITTED["w5_13_end"])
    if got != want:
        raise RuntimeError(f"the v7 w5 gives {got} on the core's 13, not the recorded {want}; "
                           "refusing to derive C4's cap with it")
    return {"w5_13": w13, "end": got[1], "recorded": list(want), "traded_start": v7.TRADED_START}


def cap_book(tb: dict, spec: dict) -> dict:
    """The book the frozen margin rule is applied to: the LIVE spec's book, with the cap removed.

    WHY (the release-check of e41f10b, 2026-11-03). Until this, `derive_cap` read the trial's z T
    whatever the spec said. On c4_families.v5 the spec trades CEF trial 54's blend, and its worst
    week per unit of gross is about twice the z book's (0.0536 against 0.0261), so the rule gives
    1.80 where the z book gives 1.90. `recap` read that z w5, and the arming gate printed "1.90,
    same as spec" for a book the rule caps at 1.80.

    THE CONSTRUCTION IS H11's (`h11_reference`), with the cap taken away, because the cap is what
    the rule derives:
      * level_signal set: m x band(T_spec, band), where T_spec is the blend (`spec_targets`) and m is
        the spec's sizing_multiplier, if set. It is checked against the RAW primary returns
        (`trial_book`'s R_raw), never against the z book's zero-filled R0 (H15).
      * absent: band(T, band) on the trial's z T and R0, exactly as before, byte for byte.
    w5 is a loss per unit of gross, so m only scales the gross it is divided by. It is applied so the
    plateau below is the account's book, as H11's is.

    Returns {T, R, H (uncapped), m (the multiplier, or 1.0 when absent), derived_on}. `derived_on`
    names the book, the spec id and the spec file's sha256, and it is written into the output json.
    `recap` refuses an output whose spec sha256 is not the live file's."""
    f = spec["frozen"]
    b = float(f["band_width"])
    lv = registry.cef_level_signal(f)
    if lv is None:
        T, R, mult = tb["T"], tb["R0"], 1.0
        H = bf.band(T, b)
        book = "z: the trial's build_book T (the spec carries no level_signal), uncapped band"
    else:
        if "T_spec" not in tb or "R_raw" not in tb:
            raise KeyError(f"{spec.get('spec_id')} sets level_signal: the cap is derived on the blended spec "
                           f"book, and `tb` carries no T_spec (spec_targets) or no raw returns (trial_book)")
        m = f.get("sizing_multiplier")
        T, R, mult = tb["T_spec"], tb["R_raw"], (1.0 if m is None else float(m))
        H = bf.band(T, b) * mult
        book = (f"blend: CEF trial 54's level_signal (z_share {lv['risk_share']}), spec_targets, "
                f"x sizing_multiplier {mult}, uncapped band")
    return {"T": T, "R": R, "H": H, "m": mult,
            "derived_on": {"book": book, "spec_id": spec.get("spec_id"), "spec_sha256": _sha(SPEC_PATH)}}


def derive_cap(tb: dict, spec: dict, cut_core: Path) -> dict:
    """C4's max_gross_stress by the frozen rule (module docstring, part 2), on the live spec's
    book (`cap_book`): the blend when the spec sets level_signal, the z book when it does not."""
    from scripts.cef import alpaca_v7_derivation as v7
    check = core_w5_check(cut_core)
    f = spec["frozen"]
    b = float(f["band_width"])
    cb = cap_book(tb, spec)
    T, mult = cb["T"], cb["m"]
    Hb = cb["H"]                               # the UNCAPPED band: the cap is what is derived
    Rb = c4.check_held(Hb, cb["R"].reindex(columns=Hb.columns), "uncapped band, total")
    held = Hb.shift(2).abs().sum(axis=1)
    p0 = held.index[held > 0][0]
    old = v7.TRADED_START
    v7.TRADED_START = str(p0.date())           # C4's traded era is its fit window (PREREG_C4 §7)
    try:
        w5, end = v7.w5(Hb, Rb)
    finally:
        v7.TRADED_START = old
    _fit_dates(pd.DatetimeIndex([end]))
    # Second method (CLAUDE.md: double-check what drives a decision): the same quantity from the
    # held weights directly, H.shift(2) * R over the gross that earned it, not through evaluate().
    hs = Hb.shift(2).fillna(0.0)
    x2 = ((hs * Rb).sum(axis=1) / hs.abs().sum(axis=1).replace(0, np.nan)).loc[p0:FIT_END].rolling(5).sum()
    if abs(-x2.min() - w5) > 1e-12 or x2.idxmin() != end:
        raise AssertionError(f"w5: the v7 function gives {w5!r} ending {end.date()}, the direct sum "
                             f"{-x2.min()!r} ending {x2.idxmin().date()}")
    worst, rr = [], x2.copy()
    for _ in range(3):                         # the worst non-overlapping 5-session windows
        d = rr.idxmin()
        worst.append([str(d.date()), float(-rr[d])])
        i = rr.index.get_loc(d)
        rr.iloc[max(0, i - 4):i + 5] = np.nan
    assets = margin_check(spec)
    e_book = float(spec["capital_usd"])
    nlv, m_other, mark = (CAP_INPUTS[k][0] for k in ("nlv_usd", "m_other_usd", "mark_sensitivity"))
    G = g_stress(nlv, m_other, v7.MARGIN, w5, e_book)
    cap = floor_to(G - mark)
    # How much worse a week would have to be to move the rule one step down (cap - CAP_STEP).
    w5_edge = (nlv - m_other) / ((cap + mark) * e_book) - v7.MARGIN
    gross = Hb.abs().sum(axis=1).loc[p0:FIT_END]
    plateau = []
    # The spec's own cap joins the grid (a no-op when it is the rule's): with an override on record it
    # is not the rule's, and the plateau must show what the spec's value costs or buys.
    spec_cap = f.get("max_gross_stress")
    grid = {1.60, 1.70, cap, round(G, 4), 1.80, 2.00} | ({float(spec_cap)} if spec_cap not in (None, "") else set())
    for c in sorted(grid) + [np.inf]:
        # absent: the trial's unit book at cap c, as before; level_signal: the account's book at its
        # cap c, m x band_gross_capped(T_spec, band, c / m), H11's construction
        Hc = bf.band_gross_capped(T, b, c) if mult == 1.0 else mult * bf.band_gross_capped(T, b, c / mult)
        Rc = c4.check_held(Hc, cb["R"].reindex(columns=Hc.columns), f"cap {c}")
        s = line(Hc, Rc, f"cap {c}")
        plateau.append(dict(cap=None if not np.isfinite(c) else c, sr=s["sr"], ann_pct=s["ann_pct"],
                            turn=s["turn"], max_gross=float(Hc.abs().sum(axis=1).loc[p0:FIT_END].max())))
    return dict(method_check=check, w5=w5, w5_window_end=str(end.date()), traded_start=str(p0.date()),
                traded_end=str(FIT_END.date()), w5_second_method="direct sum agrees to 1e-12",
                worst_windows=worst, w5_for_next_step_down=w5_edge, w5_headroom=w5_edge - w5,
                inputs={"nlv_usd": [nlv, CAP_INPUTS["nlv_usd"][1]],
                        "m_other_usd": [m_other, CAP_INPUTS["m_other_usd"][1]],
                        "m": [v7.MARGIN, "Reg T initial (team lead 2026-09-28; the core's input, "
                                         "scripts/cef/alpaca_v7_derivation.py MARGIN)"],
                        "e_book_usd": [e_book, f"capital_usd of {spec['spec_id']}"],
                        "mark_sensitivity": [mark, CAP_INPUTS["mark_sensitivity"][1]]},
                margin_at_frozen_read=assets, g_stress=G, max_gross_stress=cap,
                uncapped_max_gross=float(gross.max()), uncapped_mean_gross=float(gross.mean()),
                uncapped_share_above_cap=float((gross > cap + 1e-12).mean()),
                spec_value=f.get("max_gross_stress"), plateau=plateau, derived_on=cb["derived_on"])


def margin_check(spec: dict) -> dict:
    """The 74's Alpaca margin terms at the frozen read (2026-10-14T21:40:33Z), which the rule's
    m = 0.50 (Reg T initial) presumes: every fund marginable, maintenance at most 50%. If one were
    not, the rule as ruled would understate the margin on it, and this raises."""
    if not ASSETS.exists():
        raise FileNotFoundError(f"{ASSETS} is missing; run `python3 scripts/cef/c4_paper_benchmark.py stage`")
    a = json.loads(ASSETS.read_text())
    if a.get("read_utc") != c4.FROZEN_READ_UTC:
        raise ValueError(f"{ASSETS.name}: read {a.get('read_utc')}, not the frozen {c4.FROZEN_READ_UTC}")
    uni = set(spec["frozen"]["universe"])
    rows = {r["symbol"]: r for r in a["rows"] if r.get("symbol") in uni}
    if set(rows) != uni:
        raise ValueError(f"the frozen read lacks {sorted(uni - set(rows))}")
    bad = sorted(t for t, r in rows.items()
                 if not r.get("marginable") or float(r.get("maintenance_margin_requirement", 100)) > 50)
    if bad:
        raise ValueError(f"not marginable or maintenance above 50% at the frozen read: {bad}; "
                         "the rule's m = 0.50 does not hold for them")
    mm = sorted({float(r["maintenance_margin_requirement"]) for r in rows.values()})
    ex = pd.Series({t: r["exchange"] for t, r in rows.items()}).value_counts().to_dict()
    return {"read_utc": a["read_utc"], "funds": len(rows), "all_marginable": True,
            "maintenance_margin_pct": mm, "exchanges": ex}


# --------------------------------------------------------------------------- the IGR seed ruling

SEED_DATES = ("2026-07-29", "2026-08-04", "2026-08-07", "2026-08-11")
SEED_CLOSE_TOL = 4e-8      # c4_bar_rulings_2026-10-19.json: panel close / 3 equals Alpaca's raw close to $4e-8


def families_guard(rulings) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """`data_guards.guard_closes` over the WHOLE families panel for the frozen 74, with `rulings`:
    (raw close, close after the ruled treatments, the log). Raises as the guard raises: on any
    spike-and-revert bar no ruling covers, and on any ruling that matches no bar. A data scan of
    closes and NAVs; no return is formed."""
    from scripts.cef.band_frontier import load_families_actions
    from scripts.cef.data_guards import guard_closes
    uni = sorted(pd.read_csv(c4.FROZEN)["ticker"])
    px = pd.read_parquet(c4.FAM_DIR / "cef_prices.parquet")
    px = px[px["ticker"].isin(uni)]
    close = px.assign(date=pd.to_datetime(px["date"])).pivot_table(index="date", columns="ticker", values="close").sort_index()
    nv = pd.read_parquet(c4.FAM_DIR / "cef_nav.parquet")
    nvw = nv.assign(date=pd.to_datetime(nv["date"])).pivot_table(index="date", columns="ticker", values="nav")
    dist, spl = load_families_actions(c4.FAM_DIR / "cef_actions.parquet")
    out, log = guard_closes(close, cols=uni, lo=close.index[0], hi=close.index[-1], nav=nvw, splits=spl,
                            ex_dates=dist, rulings=rulings, context="C4 seed (families panel, the 74)")
    return close, out, log


def seed_rulings(path: Path = SEED_RULINGS) -> dict:
    """Write the team lead's 2026-10-29 IGR seed ruling (module docstring, part 4), after checking
    every claim it makes. Reads the families panel, the 2026-10-19 rulings and the staged Alpaca
    bars; writes only `path`."""
    from scripts.cef.data_guards import load_bar_rulings
    _R, src_doc = load_bar_rulings(c4.BAR_RULINGS)
    bars = src_doc["bars"]
    if [(b["ticker"], b["date"]) for b in bars] != [("IGR", d) for d in SEED_DATES]:
        raise ValueError(f"{c4.BAR_RULINGS.name} no longer holds exactly IGR's four corrected bars {SEED_DATES}")
    close, _out, log = families_guard(c4.BAR_RULINGS)
    found = sorted((r.ticker, str(pd.Timestamp(r.date).date())) for r in log.itertuples())
    if found != sorted(("IGR", d) for d in SEED_DATES):
        raise ValueError(f"the guard over the families panel treated {found}, not exactly IGR's four")
    for f in (c4.ALP_POOL, c4.ALP_POOL_META):
        if not f.exists():
            raise FileNotFoundError(f"{f} is missing; run `python3 scripts/cef/c4_paper_benchmark.py stage`")
    meta = json.loads(c4.ALP_POOL_META.read_text())
    ab = pd.read_parquet(c4.ALP_POOL)
    ab["date"] = pd.to_datetime(ab["date"])
    px = pd.read_parquet(c4.FAM_DIR / "cef_prices.parquet")
    px["date"] = pd.to_datetime(px["date"])
    cells = []
    for b in bars:
        d, tk, k = pd.Timestamp(b["date"]), b["ticker"], float(b["factor"])
        row = px[(px["ticker"] == tk) & (px["date"] == d)]
        raw = ab[(ab["ticker"] == tk) & (ab["date"] == d) & (ab["adjustment"] == "raw")]
        adj = ab[(ab["ticker"] == tk) & (ab["date"] == d) & (ab["adjustment"] == "split")]
        if not (len(row) == len(raw) == len(adj) == 1):
            raise ValueError(f"({tk}, {d.date()}): {len(row)} panel, {len(raw)} raw and {len(adj)} split-adjusted rows")
        pc = float(row["close"].iloc[0])
        if abs(pc - float(adj["close"].iloc[0])) > 1e-6:          # corrected.py's own assertion
            raise ValueError(f"({tk}, {d.date()}): the panel close {pc} is not Alpaca's split-adjusted close")
        gap = abs(float(raw["close"].iloc[0]) - pc / k)
        if gap > SEED_CLOSE_TOL:
            raise ValueError(f"({tk}, {d.date()}): Alpaca's raw close is {gap:.2e} from the panel close / {k:g}")
        cells.append({"ticker": tk, "date": b["date"],
                      "columns": {c: {"panel": float(row[c].iloc[0]), "corrected": float(raw[c].iloc[0])}
                                  for c in SEED_COLUMNS},
                      "raw_close_minus_panel_close_over_factor": gap})
    doc = {
        "ruled_by": "team lead (Simon Jarvis), answered interactively; relayed by the coordinator on 2026-10-29",
        "ruled_on": "2026-10-29",
        "record": ("this file (written by `python3 scripts/cef/c4_paper_benchmark.py seed-rulings`); "
                   "ops/specs/c4_families.frozen.json _panel_source_note"),
        "ruling": ("Seed C4's panel (data/cef_c4/, plan row 3) with the SAME four corrected IGR bars the team "
                   "lead's 2026-10-19 corrected book used (results/cef/C4_RESULT_2026-10-14.md §9; "
                   "c4_bar_rulings_2026-10-19.json): each row's open, high, low, close and volume replaced by "
                   "Alpaca's raw bar, as results/cef/c4/holdout_review_2026-10-18/corrected.py did, logged cell by "
                   "cell (`cells`). The corrected rows feed both legs, signal and return, as in the corrected book."),
        "standing_rule": ("data_guards.guard_closes accepts exactly the four cells in `bars` and nothing else. The "
                          "seed runs guard_closes on the RAW families closes of the 74 over the whole seeded span with "
                          "this file as `rulings`: it must treat exactly these four (any other spike-and-revert bar "
                          "raises, unruled; a ruling that matches no bar raises), and only then are the four rows "
                          "replaced and each replaced cell logged. The seeded panel then holds corrected bars, so a "
                          "later guard run on data/cef_c4/ must find no bar and must NOT pass this file: a fifth bar, "
                          "or one of these four coming back, needs a new ruling."),
        "source_ruling": {"path": str(c4.BAR_RULINGS.relative_to(REPO)), "sha256": _sha(c4.BAR_RULINGS)},
        "replacement_source": {
            "path": str(c4.ALP_POOL.relative_to(REPO)), "sha256": _sha(c4.ALP_POOL),
            "fetched_utc": meta.get("fetched_utc"), "selection": "ticker IGR, adjustment raw, the four dates",
            "fetcher": ("python3 scripts/data/fetch_alpaca_split_bars.py --c4-pool --start 2024-12-02 --end "
                        "2026-09-30 (docs/REFERENCES.md, the Alpaca SIP daily bars row); gitignored, staged from "
                        "the trial-c4 worktree by `c4_paper_benchmark.py stage`")},
        "checks": {
            "guard_over_families_panel": (f"guard_closes over {close.index[0].date()}..{close.index[-1].date()} for "
                                          f"the 74 treated exactly {len(found)} cells, these four"),
            "panel_close_is_alpaca_split_adjusted_close": "within 1e-6, each of the four",
            "alpaca_raw_close_is_panel_close_over_factor": f"within {SEED_CLOSE_TOL:g}, each of the four"},
        "bars": bars,
        "cells": cells,
    }
    load_bar_rulings_check(doc)
    path.write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def load_bar_rulings_check(doc: dict) -> None:
    """The file must load through `data_guards.load_bar_rulings` unchanged (step 3 passes it there)."""
    from scripts.cef.data_guards import load_bar_rulings
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "r.json"
        p.write_text(json.dumps(doc))
        load_bar_rulings(p)


# --------------------------------------------------------------------------- main

class Log:
    def __init__(self):
        self.lines: list[str] = []

    def __call__(self, s: str = "") -> None:
        print(s, flush=True)
        self.lines.append(s)


def _fmt_line(s: dict) -> str:
    return (f"{s['label']:<42}{s['sr']:8.3f}{s['ann_pct']:7.2f}{s['vol_pct']:7.2f}{s['turn']:7.1f}"
            f"{s['net5']:8.3f}{s['net15']:8.3f}{s['net30']:8.3f}{s['flips']:>7}{s['max_dd_pct']:9.2f}")


def run_fidelity(spec: dict, cut: Path, T: pd.DataFrame, say: Log, csv: Path | None = None) -> dict:
    dates = fidelity_dates(T)
    against = ("CEF trial 54's blend (spec_targets)" if registry.cef_level_signal(spec["frozen"]) is not None
               else "c4_families.build_book's T")         # absent: today's text, unchanged
    say(f"\n[1] FIDELITY: the live sleeve under {spec['spec_id']} (built through the registry) against "
        f"{against}, on {len(dates)} fit sessions ({dates[0].date()}..{dates[-1].date()}, "
        f"every {FIDELITY_STEP}th session of T's index and its last); compared at the sleeve's target "
        f"before min_abs_weight; tolerance {TOL:g}")
    try:
        rep = fidelity(spec, cut, dates, T=T)
        broke = None
    except FidelityBreak as e:
        rep, broke = e.report, e
    say(f"  sessions compared {rep['sessions']}: trial trades on {rep['trade_sessions']}, holds on "
        f"{rep['hold_sessions']}; matched {rep['sessions_matched']} ({rep['session_match_rate']:.4%})")
    say(f"  name-cells compared on trading sessions {rep['cells_compared']:,}, matched {rep['cells_matched']:,} "
        f"({rep['cell_match_rate']:.4%}); largest gap {rep['largest_gap']:.3e}; largest UNEXPLAINED gap "
        f"{'none' if rep['largest_unexplained_gap'] is None else rep['largest_unexplained_gap']}")
    say(f"  declared divergence §3 item 5, reported only: on {rep['item5_sessions']} of {rep['trade_sessions']} "
        f"trading sessions, {rep['item5_sub_min_abs_names']} of {rep['item5_of_held_names']} targeted names sit "
        f"under min_abs_weight {rep['min_abs_weight']} and the live sleeve drops them and re-neutralises")
    if csv is not None:
        pd.DataFrame(rep["rows"]).to_csv(csv, index=False)
    if broke is not None:
        say(f"  HALT: {broke}")
        raise broke
    say("  FIDELITY: every difference is inside the declared divergences (none at the target level)")
    return rep


def run_controls(spec: dict, cut: Path, T: pd.DataFrame, say: Log) -> list:
    dates = fidelity_dates(T)
    m2 = m2_footprint(cut, spec)
    say("\n[1b] NEGATIVE CONTROLS: each spec below should break fidelity (each stops at its first break)")
    out = []
    for name, sp in controls(spec):
        try:
            registry.validate_spec(sp)
        except ValueError as e:                  # refused before it could trade: stronger than a break
            r = dict(control=name, broke=True, refused=True, first=None, note=f"REFUSED by the registry: {e}"[:150])
            out.append(r)
            say(f"  {name:<52} REFUSED  {r['note']}")
            continue
        try:
            fidelity(sp, cut, dates, T=T, first_break=True)
            if name.startswith("zero_volume_mask"):
                note = (f"no break, and none can arise here: M2 masks {m2['cells']} paired fund-days of the 74 in "
                        f"the fit panel ({', '.join(m2['funds'])}), {m2['cells_with_adv_at_floor']} of them on a "
                        f"fund-day whose ADV clears the floor, so it moves no compared target (PREREG_C4 §4.3: a "
                        f"guard). The synthetic test injects a zero-volume day and shows the break")
            else:
                note = "NO BREAK: the check has no power against this change on these sessions"
            r = dict(control=name, broke=False, first=None, note=note)
        except FidelityBreak as e:
            b = e.report["breaks"][0]
            r = dict(control=name, broke=True, first=b["date"], note=b["detail"][:150])
        out.append(r)
        say(f"  {name:<52} {'BREAKS' if r['broke'] else 'no break'}  {r['first'] or ''}  {r['note']}")
    return out


def run(argv_out: bool = True) -> int:
    from scripts.cef.spec import SPEC_ID as CORE_ID
    say = Log()
    spec = load_spec()
    say(f"C4 PAPER BENCHMARK (step 2 of C4_DEPLOY_PLAN_2026-10-27; zero trials). Run "
        f"{dt.datetime.now(dt.timezone.utc).isoformat()[:16]} UTC. Spec {spec['spec_id']} "
        f"(sha256 {_sha(SPEC_PATH)[:16]}...); the trial's parameters from {CORE_ID} (scripts/cef/spec.py). "
        f"Fit window only, <= {FIT_END.date()}: no 2023+ row is read.")
    res: dict = dict(spec_id=spec["spec_id"], spec_sha256=_sha(SPEC_PATH), core_spec_id=CORE_ID,
                     run_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    with tempfile.TemporaryDirectory(prefix="c4_paper_") as tmp:
        cut, cut_core = Path(tmp) / "families", Path(tmp) / "core"
        res["families_cut"] = cut_families(cut)
        full_last = str(pd.to_datetime(pd.read_parquet(c4.FAM_DIR / "cef_prices.parquet", columns=["date"])["date"]).max().date())
        say(f"panels: data/cef_families/ (last {full_last}) cut on read at {FIT_END.date()} into a temporary "
            f"directory: {res['families_cut']}")
        T, info = trial_targets(cut)
        committed = json.loads(c4.FIT_JSON.read_text())
        if info["without_rows"] != committed["funds_without_fit_data"]:
            raise RuntimeError(f"funds without fit rows {info['without_rows']} != committed "
                               f"{committed['funds_without_fit_data']}")
        say(f"trial T: {T.shape[1]} frozen funds ({len(info['with_rows'])} with fit rows; zero columns for "
            f"{', '.join(info['without_rows'])}), {len(T)} sessions {T.index[0].date()}..{T.index[-1].date()}")
        TS = spec_targets(cut, T, spec)
        if TS is not T:
            say(f"spec target: CEF trial 54's blend (level_signal, z_share "
                f"{spec['frozen']['level_signal']['risk_share']}), built by spec_targets from the same cut; "
                f"fidelity and H11 read it, the reproduction gate and the cap rule read the trial's z T")
        res["fidelity"] = {k: v for k, v in run_fidelity(spec, cut, TS, say, csv=OUT_CSV).items() if k != "rows"}
        res["controls"] = run_controls(spec, cut, TS, say)

        say(f"\n[2] THE TRIAL'S BOOK, GATED (CRSP extract sha256 {CRSP_SHA256[:16]}..., rows <= {FIT_END.date()})")
        tb = trial_book(cut, T)
        tb["T"] = T
        tb["T_spec"] = TS
        say(f"  GATE PASS: total-return gross SR {tb['total_sr']:.12f}, price-only {tb['price_sr']:.12f}: both "
            f"the committed figures to 1e-9 (c4_fit_verdict_2026-10-14.json stage1, R-P); first held {tb['p0'].date()}")

        say(f"\n[3] MAX_GROSS_STRESS by the frozen rule (PREREG_GROUP_CAP_2026-09-16 §3b; PREREG_ALPACA_V7 §3b)")
        cap = derive_cap(tb, spec, cut_core)
        res["cap"] = cap
        mc = cap["method_check"]
        say(f"  method check: the v7 w5 on the core's 13, panels cut at {FIT_END.date()}, traded era from "
            f"{mc['traded_start']}: {mc['w5_13']:.10f} ending {mc['end']} = recorded {mc['recorded']}")
        if registry.cef_level_signal(spec["frozen"]) is not None:      # absent: today's text, unchanged
            say(f"  derived on the LIVE spec book: {cap['derived_on']['book']} ({spec['spec_id']})")
        say(f"  C4 w5 (uncapped band {spec['frozen']['band_width']}, CRSP total return, {cap['traded_start']}.."
            f"{cap['traded_end']}): {cap['w5']:.10f}, the 5 sessions ending {cap['w5_window_end']} "
            f"({cap['w5_second_method']}); the three worst non-overlapping windows "
            f"{', '.join(f'{d} {v:.4f}' for d, v in cap['worst_windows'])}")
        for k, (v, why) in cap["inputs"].items():
            say(f"    {k:<17} {v:>12,.4f}   {why}")
        mt = cap["margin_at_frozen_read"]
        say(f"    the 74 at the frozen read {mt['read_utc']}: all marginable, maintenance {mt['maintenance_margin_pct']}%, "
            f"exchanges {mt['exchanges']}")
        say(f"  G_stress = ({cap['inputs']['nlv_usd'][0]:,.0f} - {cap['inputs']['m_other_usd'][0]:,.0f}) / "
            f"({cap['inputs']['m'][0]} + {cap['w5']:.7f}) / {cap['inputs']['e_book_usd'][0]:,.0f} = {cap['g_stress']:.6f}; "
            f"floor_0.05(G - {cap['inputs']['mark_sensitivity'][0]}) = {cap['max_gross_stress']:.2f}")
        say(f"  KNOWN LIMIT: a worst week above w5 = {cap['w5_for_next_step_down']:.7f} gives the next step down "
            f"({cap['max_gross_stress'] - CAP_STEP:.2f}); the fit's sits {cap['w5_headroom']:.7f} below it. The core's "
            f"read ran to its panel end; C4's 2023-26 is not read here")
        say(f"  the uncapped band's gross over the fit: mean {cap['uncapped_mean_gross']:.2f}x, max "
            f"{cap['uncapped_max_gross']:.2f}x, above {cap['max_gross_stress']:.2f}x on {cap['uncapped_share_above_cap']:.1%} of sessions")
        say("  PLATEAU (H8; shown to prove the derived value is not on a cliff -- the value comes from the margin "
            "arithmetic, never from this): fit gross SR by cap")
        for p in cap["plateau"]:
            say(f"    cap {('none' if p['cap'] is None else p['cap']):>7}  gross SR {p['sr']:.3f}  ann {p['ann_pct']:.2f}%  "
                f"turn {p['turn']:.1f}  max gross {p['max_gross']:.2f}")
        if cap["spec_value"] is not None and abs(float(cap["spec_value"]) - cap["max_gross_stress"]) > 1e-12:
            ov = cap_override_for(spec["spec_id"], cap["w5"], cap["max_gross_stress"], float(cap["spec_value"]))
            if ov is None:
                raise RuntimeError(f"the spec's max_gross_stress {cap['spec_value']} is not the rule's "
                                   f"{cap['max_gross_stress']}, and no team-lead override on record "
                                   f"({CAP_OVERRIDE_GLOB}) names w5 {cap['w5']!r} with these caps")
            cap["override"] = {k: ov[k] for k in ("ruled", "ruled_by", "words", "citation", "_file", "key")}
            say(f"  the spec carries {cap['spec_value']}, NOT the rule's {cap['max_gross_stress']}: OVERRIDE ON RECORD "
                f"({ov['ruled_by']}, {ov['ruled']}: \"{ov['words']}\"; {ov['citation']}; {ov['_file']})")
        else:
            say(f"  the spec carries {cap['spec_value']}: the rule's value")

        say(f"\n[4] THE H11 LINES (fit; gross is the headline, the 5/15/30bp grid beside it as the real-money "
            f"view, labelled; descriptive only, H14: PREREG_C4 §14 re-measures on the read date). H11 READS THE "
            f"SPEC BOOK ({H11_BOOK}; team lead 2026-10-29): the 120-session percentile and the drawdown stop are "
            f"measured on it, never on the trial's 1.80 book")
        L = lines(tb, spec)
        say(f"  {'line':<42}{'grossSR':>8}{'ann%':>7}{'vol%':>7}{'turn':>7}{'net@5':>8}{'net@15':>8}{'net@30':>8}"
            f"{'flips?':>7}{'maxDD%':>9}")
        for key in ("spec_book", "trial_book"):
            b = L[key]
            say(f"  -- {key.replace('_', ' ')}, {b['role']}: {b['policy']}")
            for kind in ("total", "price"):
                say("  " + _fmt_line(b[kind]))
            say(f"     distribution leg (total - price) {b['distribution_leg_pct_per_yr']:+.2f}%/yr; price-only "
                f"Sharpe exceeds total by {b['price_minus_total_sr']:+.3f} (paper credits shorts no distribution)")
            for kind in ("total", "price"):
                er = b[kind]["eras"]
                say(f"     eras, {kind:<5}: " + "; ".join(f"{k} {v['sr']:.3f} ({v['ann_pct']:.2f}%)" for k, v in er.items()))
        res["lines"] = {k: {kk: ({x: y for x, y in vv.items() if x != "_P"} if isinstance(vv, dict) else vv)
                            for kk, vv in v.items()} for k, v in L.items()}
        res["h11_reference"] = H11_BOOK
        if argv_out:
            sb = write_spec_book_series(L, spec)
            say(f"  the H11 reference's daily P&L for stops.py --c4-exact: {sb.relative_to(REPO)} (gitignored)")
        say("\nBorrow is not charged in any line above (H4): all 74 were easy to borrow at the frozen read and "
            "Alpaca charges no fee on an easy-to-borrow short; one snapshot is a counterfactual over 17.8 years.")
    if argv_out:
        from scripts.research.backfill.backfill import plain
        OUT_JSON.write_text(json.dumps(plain(res), indent=1) + "\n")
        OUT_TXT.write_text("\n".join(say.lines) + "\n")
        say(f"\nwrote {OUT_TXT.relative_to(REPO)}, {OUT_JSON.relative_to(REPO)}, {OUT_CSV.relative_to(REPO)}")
    return 0


def spec_book_series_path(spec: dict) -> Path:
    """Where `run` leaves the H11 reference's daily P&L for the spec it read (gitignored: CRSP-derived)."""
    return c4.CACHE / f"h11_spec_book_{spec['spec_id']}.parquet"


def write_spec_book_series(L: dict, spec: dict) -> Path:
    """The H11 reference book's daily P&L, CRSP total return (`tr`) and price only (`pr`), in the
    account's units (m applied, the exact construction), with a sidecar naming the spec file's sha256.
    results/cef/prereg_voltarget/stops.py --c4-exact reads it, so R1-R3 are re-measured on the book the
    LIVE spec defines (PREREG_C4_LEVEL §6.3), the blend when it sets level_signal, and it refuses a
    series made from another spec. CRSP-derived and licensed: written only under the gitignored cache,
    and this refuses a path git would track."""
    b = L[H11_BOOK]
    d = pd.DataFrame({"tr": b["total"]["_P"], "pr": b["price"]["_P"]})
    if not d["tr"].index.equals(b["price"]["_P"].index) or d.isna().any().any():
        raise ValueError("the H11 reference's total and price lines are not on one calendar")
    _fit_dates(d)
    out = spec_book_series_path(spec)
    if subprocess.run(["git", "check-ignore", "-q", str(out.relative_to(REPO))], cwd=REPO).returncode != 0:
        raise RuntimeError(f"{out} is not gitignored; CRSP-derived series must never be tracked")
    out.parent.mkdir(parents=True, exist_ok=True)
    d.to_parquet(out)
    out.with_suffix(".json").write_text(json.dumps(
        {"spec_id": spec["spec_id"], "spec_sha256": _sha(SPEC_PATH), "policy": b["policy"],
         "first": str(d.index[0].date()), "last": str(d.index[-1].date()),
         "written_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}, indent=1) + "\n")
    return out


# A TEAM-LEAD OVERRIDE OF THE RULE'S CAP, ON RECORD (2026-11-03). The frozen margin rule gives C4 v5's
# blend 1.80. The team lead ruled to keep 1.90 with that figure in front of him (docs/SYSTEM.md §5,
# "Team lead, 2026-11-03 — C4 v5's gross cap"). The ruling is not the rule, so neither `run` nor `recap`
# may report the spec's cap as the rule's. An override is honoured only when a file here names, on
# content, the exact spec id, w5, rule's cap and spec cap being compared, like `ca-ack`'s
# acknowledgements: `key` is the sha256 of those four fields in canonical JSON. A file whose fields no
# longer hash to its key (an edited w5, say) is REFUSED, and a fresh w5 or cap that no file names is
# STOP. Revert: delete the file. The spec then needs the rule's cap through /spec-change, or a new
# ruling with a new file.
CAP_OVERRIDE_DIR = c4.OUT_DIR
CAP_OVERRIDE_GLOB = "c4_cap_override_*.json"
CAP_OVERRIDE_MATCHED = ("spec_id", "w5", "rule_cap", "spec_cap")
CAP_OVERRIDE_RECORD = ("ruled", "ruled_by", "words", "citation")


def cap_override_key(doc: dict) -> str:
    """The sha256 of the matched fields in canonical JSON (sorted keys, no spaces): the one form an
    override is matched on, so a changed figure is a different key."""
    core = {k: doc[k] for k in CAP_OVERRIDE_MATCHED}
    return hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def cap_override_doc(spec_id: str, w5: float, rule_cap: float, spec_cap: float, ruled: str, ruled_by: str,
                     words: str, citation: str) -> dict:
    """An override record, keyed on its content (written once per ruling; never edited)."""
    doc = {"what": "a team-lead override of the frozen margin rule's max_gross_stress for C4: the spec's cap "
                   "stands by ruling, not by the rule (scripts/cef/c4_paper_benchmark.py recap)",
           "spec_id": str(spec_id), "w5": float(w5), "rule_cap": float(rule_cap), "spec_cap": float(spec_cap),
           "ruled": str(ruled), "ruled_by": str(ruled_by), "words": str(words), "citation": str(citation),
           "revert": "delete this file; the spec then takes the rule's cap through /spec-change, or a new ruling"}
    doc["key"] = cap_override_key(doc)
    return doc


def load_cap_overrides(where: Path | None = None) -> list[dict]:
    """Every override on record, validated. A malformed file, one not ruled by the team lead, or one
    whose matched fields do not hash to its key RAISES, naming the file: an override that has been
    edited since its ruling overrides nothing, and skipping it in silence would hide that."""
    out = []
    for p in sorted((CAP_OVERRIDE_DIR if where is None else where).glob(CAP_OVERRIDE_GLOB)):
        doc = json.loads(p.read_text())
        missing = [k for k in CAP_OVERRIDE_MATCHED + CAP_OVERRIDE_RECORD + ("key",) if k not in doc]
        if missing:
            raise ValueError(f"{p.name}: an override record lacks {missing}")
        if not str(doc["ruled_by"]).lower().startswith("team lead"):
            raise ValueError(f"{p.name}: ruled_by {doc['ruled_by']!r}; only the team lead overrides the rule")
        if not all(isinstance(doc[k], (int, float)) and not isinstance(doc[k], bool)
                   for k in ("w5", "rule_cap", "spec_cap")):
            raise ValueError(f"{p.name}: w5, rule_cap and spec_cap must be numbers")
        if cap_override_key(doc) != doc["key"]:
            raise ValueError(f"{p.name}: its content (w5 {doc['w5']!r}, rule_cap {doc['rule_cap']!r}, spec_cap "
                             f"{doc['spec_cap']!r}, {doc['spec_id']}) does not match its key: edited after the "
                             f"ruling it records, so it overrides nothing")
        out.append(dict(doc, _file=str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p)))
    return out


def cap_override_for(spec_id: str, w5: float, rule_cap: float, spec_cap: float,
                     where: Path | None = None) -> "dict | None":
    """The override on record naming exactly these four, or None. Exact equality on w5: it is the
    committed derivation's float, read from the output json, not a re-estimate."""
    for doc in load_cap_overrides(where):
        if (doc["spec_id"] == spec_id and float(doc["w5"]) == float(w5)
                and float(doc["rule_cap"]) == float(rule_cap) and float(doc["spec_cap"]) == float(spec_cap)):
            return doc
    return None


def _usd(v, what: str) -> float:
    """A dollar figure as Alpaca serves it (a decimal string), or raise naming it."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{what} {v!r} is not a number") from None
    if not math.isfinite(x) or x < 0:
        raise ValueError(f"{what} {v!r} is not a finite non-negative number")
    return x


def recap(probe_path: Path, mark_sensitivity: float) -> dict:
    """THE ARMING GATE (the spec's _max_gross_stress_note, ruling 3; team lead 2026-10-29):
    the cap re-derived by the frozen rule from a FRESH read of C4's account.

    NLV is the probe snapshot's `account.equity`; M_other is its
    `account.maintenance_margin`, which is the other book's (the agent lab's) margin
    only while C4 itself holds nothing, so a snapshot holding any of C4's 74 is
    refused: M_other could not be told apart from C4's own. m and w5 are the
    committed derivation's (OUT_JSON `cap`: Reg T 0.50, the fit window's worst
    week ON THE LIVE SPEC'S BOOK, `cap_book`: the blend when the spec sets
    level_signal), E_book the spec's capital_usd, and the mark sensitivity of the
    other book is the caller's REQUIRED input (no default: it is a ruled input, as
    the core's was). An output made on another spec file is refused, naming both
    sha256s: until 2026-11-03 this read the z book's w5 whatever the spec was, and
    printed "SAME" for a v5 book the rule caps at 1.80 (the release-check of e41f10b).

    The verdict (`status`), reported with the rule's cap, the spec's cap and
    `same_as_spec` as they are: "SAME" when they agree; "OVERRIDE ON RECORD" when
    they do not and a team-lead override names this exact spec id, w5 and both caps
    (`cap_override_for`; it carries the ruling's citation); "STOP" otherwise, when the
    spec takes a new id (/spec-change) or a new ruling is recorded before C4 trades
    on that cap. It never says the book may arm: arming is the team lead's.
    Writes nothing."""
    snap = json.loads(Path(probe_path).read_text())
    if snap.get("book") != "c4":
        raise ValueError(f"{probe_path} is the probe of book {snap.get('book')!r}, not c4")
    acct = snap.get("account") or {}
    nlv = _usd(acct.get("equity"), "account.equity")
    m_other = _usd(acct.get("maintenance_margin"), "account.maintenance_margin")
    spec = load_spec()
    held_c4 = sorted(p.get("symbol") for p in (snap.get("positions") or [])
                     if p.get("symbol") in set(spec["frozen"]["universe"]))
    if held_c4:
        raise ValueError(f"the account holds C4 names {held_c4}: its maintenance margin is not "
                         f"the other book's alone, so M_other is not measured")
    # THE OUTPUT MUST BE THE LIVE SPEC'S (the release-check of e41f10b): w5 and m come from the
    # committed run, and a run made on another spec file measured another book. Both the run's spec
    # sha256 and its cap derivation's `derived_on` must name the live file.
    out = json.loads(OUT_JSON.read_text())
    live = _sha(SPEC_PATH)
    if out.get("spec_sha256") != live:
        raise ValueError(f"{OUT_JSON.name} was made from spec sha256 {out.get('spec_sha256')} ({out.get('spec_id')}); "
                         f"the live {SPEC_PATH.name} is sha256 {live} ({spec['spec_id']}). Its w5 is another book's: "
                         f"re-run `python3 scripts/cef/c4_paper_benchmark.py run` on the live spec")
    d = out["cap"]
    don = d.get("derived_on")
    if not isinstance(don, dict) or don.get("spec_sha256") != live:
        raise ValueError(f"{OUT_JSON.name}: the cap's w5 was not derived on the live spec's book (derived_on "
                         f"{don!r}); re-run `python3 scripts/cef/c4_paper_benchmark.py run`")
    w5, m = float(d["w5"]), float(d["inputs"]["m"][0])
    e_book = float(spec["capital_usd"])
    mark = _usd(mark_sensitivity, "--mark-sensitivity")
    G = g_stress(nlv, m_other, m, w5, e_book)
    cap = floor_to(G - mark)
    spec_cap = float(spec["frozen"]["max_gross_stress"])
    same = cap == spec_cap
    ov = None if same else cap_override_for(spec["spec_id"], w5, cap, spec_cap)
    status = "SAME" if same else ("OVERRIDE ON RECORD" if ov is not None else "STOP")
    return {"probe": str(probe_path), "fetched_at_utc": snap.get("fetched_at_utc"),
            "nlv_usd": nlv, "m_other_usd": m_other, "m": m, "w5": w5, "e_book_usd": e_book,
            "mark_sensitivity": mark, "g_stress": G, "cap": cap, "spec_cap": spec_cap,
            "positions": len(snap.get("positions") or []), "same_as_spec": same, "status": status,
            "derived_on": don, "override": None if ov is None else
            {k: ov[k] for k in ("ruled", "ruled_by", "words", "citation", "_file")}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=["stage", "run", "fidelity", "seed-rulings", "recap"])
    ap.add_argument("--probe", type=Path, default=None,
                    help="recap: the C4 probe snapshot (python3 -m quantt.broker.alpaca_probe --book c4)")
    ap.add_argument("--mark-sensitivity", type=float, default=None,
                    help="recap: the other book's mark sensitivity, a multiple of sleeve NAV (REQUIRED)")
    a = ap.parse_args(argv)
    from ops import netguard
    netguard.install()                         # offline: no broker, no R2, no network
    if a.what == "recap":
        if a.probe is None or a.mark_sensitivity is None:
            ap.error("recap needs --probe and --mark-sensitivity (no defaults)")
        r = recap(a.probe, a.mark_sensitivity)
        print(f"  G_stress = ({r['nlv_usd']:,.2f} - {r['m_other_usd']:,.2f}) / ({r['m']} + "
              f"{r['w5']:.7f}) / {r['e_book_usd']:,.0f} = {r['g_stress']:.6f}; less mark "
              f"{r['mark_sensitivity']}, floored to 0.05: {r['cap']:.2f}")
        print(f"  w5 {r['w5']!r} derived on {r['derived_on']['book']} ({r['derived_on']['spec_id']})")
        print(f"  the rule's cap {r['cap']:.2f}; the spec's max_gross_stress {r['spec_cap']:.2f}; "
              f"same_as_spec {r['same_as_spec']}")
        if r["status"] == "SAME":
            print("  SAME: the spec's cap is the rule's")
            return 0
        if r["status"] == "OVERRIDE ON RECORD":
            o = r["override"]
            print(f"  OVERRIDE ON RECORD: the spec's {r['spec_cap']:.2f} stands by ruling, not by the rule "
                  f"({o['ruled_by']}, {o['ruled']}: \"{o['words']}\"; {o['citation']}; {o['_file']})")
            return 2
        print(f"  STOP: the rule gives {r['cap']:.2f} and the spec carries {r['spec_cap']:.2f}, and no "
              f"team-lead override on record ({CAP_OVERRIDE_GLOB}) names w5 {r['w5']!r} with these caps. A "
              f"new spec id (/spec-change) and a release, or a new ruling, before C4 trades on this cap")
        return 1
    if a.what == "stage":
        for k, v in stage().items():
            print(f"{v:>8}  {k}")
        return 0
    if a.what == "seed-rulings":
        doc = seed_rulings()
        for c in doc["cells"]:
            print(f"  {c['ticker']} {c['date']}: " + ", ".join(
                f"{k} {v['panel']:g} -> {v['corrected']:g}" for k, v in c["columns"].items()))
        print(f"wrote {SEED_RULINGS.relative_to(REPO)}")
        return 0
    if a.what == "fidelity":
        spec = load_spec()
        with tempfile.TemporaryDirectory(prefix="c4_paper_") as tmp:
            cut = Path(tmp) / "families"
            cut_families(cut)
            T, _ = trial_targets(cut)
            run_fidelity(spec, cut, spec_targets(cut, T, spec), Log())
        return 0
    return run()


if __name__ == "__main__":
    sys.exit(main())
