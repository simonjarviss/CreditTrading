"""CEF trial 54's activation measures on the SLEEVE's construction: §3.3 re-measured, and L1's reference.

    python3 scripts/cef/c4_paper_benchmark.py stage                      # the CRSP extract (gitignored)
    python3 -B results/cef/prereg_c4_level/activation_measures.py         # ~1 min; writes the two files below

    -> results/cef/prereg_c4_level/activation_measures_2026-11-03.{txt,json}

WHY. The pre-registration's construction figures (§3.3: cap-binding share, held gross, turnover) came
from `prereg_c4_level_design.py`. That design run built its level book differently from §1.2:
  * it used every name with a z and a discount (no ADV floor);
  * it required 6 non-zero level names;
  * it fell back to z alone on days without them.
The sleeve follows §1.2 (the z's eligible names, no second floor, no fallback). So the figures are
re-measured here on the sleeve's construction, and the spec's `_level_signal_note` carries the old
and new side by side.

L1 (§6.3) is the level component's stop: "at 120 armed sessions, the level-only book's modelled P&L
... below the 5th percentile of its fit 120-session distribution -> revert level_signal". This stores
that fit reference with its commit and date. The rule re-measures it on the read date (H14); nothing
keys on the number written here.

WHAT IS COMPUTED, ALL FROM C4'S LIVE SPEC (never a literal):
  * T: the trial's z target (`c4_paper_benchmark.trial_targets`). The reproduction gate
    (`trial_book`) must pass on it first, so the returns are trial 52's.
  * T_B and T_L: `spec_targets`, the line-for-line port of trial54.py's `level_targets` (unmasked,
    as the sleeve). DG-L4 matched the sleeve against it on 907 of 907 sessions, so it is the sleeve's
    construction.
  * The account books: m x band_gross_capped(T, band, cap / m), the sizing_multiplier path.
  * §3.3 table, with the design script's own definitions. A session is "live" when the target is
    non-zero. Target gross is m x sum|T|. "At the cap" is held gross >= cap - 1e-9. Turnover is the
    mean of sum|dH| x 252 over live sessions.
  * L1: the level-only book on CRSP price-only returns (paper's P&L basis), CRSP total return beside
    it. The distribution is of 120-session cumulative returns under the stationary bootstrap, mean
    block 21. That is trial 53's R2 construction (results/cef/prereg_voltarget/stops.py and
    _common.Paths: 10,000 paths, seed 20261030). Its 5th percentile is the reference. The empirical
    5th percentile of overlapping 120-session windows is shown beside it, labelled, and does not
    decide.

FIT ONLY: every frame ends by 2022-12-30 (asserted). The CRSP values are read from the gitignored
cache and never written; the outputs are portfolio aggregates.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "results" / "cef" / "prereg_voltarget"))

from scripts.cef import band_frontier as bf  # noqa: E402
from scripts.cef import c4_families as c4  # noqa: E402
from scripts.cef import c4_paper_benchmark as bm  # noqa: E402
from src.deploy import registry  # noqa: E402

STAMP = "2026-11-03"
OUT_TXT = HERE / f"activation_measures_{STAMP}.txt"
OUT_JSON = HERE / f"activation_measures_{STAMP}.json"
HORIZON_L1 = 120          # §6.3 L1: "its fit 120-session distribution"
EPS_CAP = 1e-9            # the design script's "at the cap" tolerance


def construction(T: pd.DataFrame, m: float, cap: float, band: float) -> dict:
    """§3.3's columns for one unit target, exactly as prereg_c4_level_design.py §B defines them."""
    H = bf.band_gross_capped(T, band, cap / m) * m
    Hu = bf.band(T, band) * m
    live = T.abs().sum(axis=1) > 0
    tg = (T.abs().sum(axis=1) * m)[live]
    hg = H.abs().sum(axis=1)[live]
    ug = Hu.abs().sum(axis=1)[live]
    turn = H.diff().abs().sum(axis=1)[live].mean() * 252
    return {"target_gross": float(tg.mean()), "p_target_above_cap": float((tg > cap).mean()),
            "uncapped_held_gross": float(ug.mean()), "p_uncapped_above_cap": float((ug > cap).mean()),
            "held_gross": float(hg.mean()), "p_at_cap": float((hg >= cap - EPS_CAP).mean()),
            "turn_per_yr": float(turn), "live_sessions": int(live.sum())}


def l1_reference(H: pd.DataFrame, R: pd.DataFrame, label: str) -> dict:
    from _common import Paths
    Rc = c4.check_held(H, R.reindex(columns=H.columns), label)
    r = bf.evaluate(H, Rc)
    held = H.shift(2).abs().sum(axis=1)
    p0 = held.index[held > 0][0]
    P = r["pnl"].loc[p0:bm.FIT_END]
    bm._fit_dates(P)
    x = P.to_numpy()
    paths = Paths()
    I21 = paths.get(len(x))[0]
    boot = np.prod(1 + x[I21[:, :HORIZON_L1]], axis=1) - 1
    roll = (1 + P).rolling(HORIZON_L1).apply(np.prod, raw=True).dropna() - 1
    return {"first_held": str(p0.date()), "last": str(P.index[-1].date()), "sessions": int(len(P)),
            "ann_pct": float(P.mean() * 252 * 100), "vol_pct": float(P.std() * np.sqrt(252) * 100),
            "gross_sr": float(P.mean() / P.std() * np.sqrt(252)),
            "p5_120_sb21": float(np.quantile(boot, 0.05)), "p50_120_sb21": float(np.quantile(boot, 0.50)),
            "p5_120_rolling_empirical": float(np.quantile(roll, 0.05)), "rolling_windows": int(len(roll)),
            "bootstrap": {"method": "stationary bootstrap, mean block 21 (_common.Paths: stops.py R2's)",
                          "reps": int(I21.shape[0]), "seed": int(paths.seed), "horizon": HORIZON_L1}}


DESIGN_OUT = REPO / "results" / "cef" / "screens_2026-11-02" / "prereg_c4_level_design_output_v4.txt"
DESIGN_ROWS = {"z-only spec book": "z_only_spec_book", "blend a = 0.5": "blend_spec_book"}


def design_run() -> dict:
    """The pre-registration's §3.3 figures, read from the committed design output (not retyped), so the
    note can set old beside new. [S]: that run's own figures, not re-run here."""
    out = {"source": f"{DESIGN_OUT.relative_to(REPO)} section B [S]"}
    for line in DESIGN_OUT.read_text().splitlines():
        for lab, key in DESIGN_ROWS.items():
            if line.strip().startswith(lab):
                v = line.strip()[len(lab):].split()
                if len(v) != 7:
                    raise ValueError(f"{DESIGN_OUT.name}: the '{lab}' row has {len(v)} fields, not 7")
                pct = lambda x: float(x.rstrip("%")) / 100.0                 # noqa: E731
                out[key] = {"target_gross": float(v[0]), "p_target_above_cap": pct(v[1]),
                            "uncapped_held_gross": float(v[2]), "p_uncapped_above_cap": pct(v[3]),
                            "held_gross": float(v[4]), "p_at_cap": pct(v[5]), "turn_per_yr": float(v[6])}
    missing = [k for k in DESIGN_ROWS.values() if k not in out]
    if missing:
        raise ValueError(f"{DESIGN_OUT.name} has no row for {missing}")
    return out


def main() -> int:
    spec = bm.load_spec()
    f = spec["frozen"]
    lv = registry.cef_level_signal(f)
    if lv is None:
        raise ValueError(f"{spec['spec_id']} carries no level_signal; these are the activation's measures")
    m, cap, band = float(f["sizing_multiplier"]), float(f["max_gross_stress"]), float(f["band_width"])
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    lines = []
    say = lambda s="": (print(s), lines.append(s))                      # noqa: E731
    run_utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    say(f"CEF trial 54 activation measures ({run_utc}); code {head[:7]}{' + uncommitted edits' if dirty else ''}; "
        f"C4 spec {spec['spec_id']} (sha256 {bm._sha(bm.SPEC_PATH)[:16]}...): m {m}, cap {cap}, band {band}, "
        f"z_share {lv['risk_share']}; fit only, <= {bm.FIT_END.date()}")
    with tempfile.TemporaryDirectory(prefix="c4_level_measures_") as tmp:
        cut = Path(tmp) / "families"
        bm.cut_families(cut)
        T, _ = bm.trial_targets(cut)
        TB = bm.spec_targets(cut, T, spec)
        TL = bm.spec_targets(cut, T, spec, level_only=True)
        tb = bm.trial_book(cut, T)
    say(f"  reproduction gate PASS: trial 52's fit gross SR {tb['total_sr']:.12f} (total), {tb['price_sr']:.12f} (price)")
    rows = {"z_only_spec_book": construction(T, m, cap, band), "blend_spec_book": construction(TB, m, cap, band)}
    say(f"\n§3.3 ON THE SLEEVE'S CONSTRUCTION (account x{m}, cap {cap}, band {band}; fit sessions with a target):")
    say(f"   {'book':<18}{'target gross':>13}{'P(tgt>cap)':>11}{'uncapped held':>14}{'P(>cap)':>9}"
        f"{'held gross':>11}{'P(at cap)':>10}{'turn/yr':>9}")
    for k, r in rows.items():
        say(f"   {k:<18}{r['target_gross']:>13.3f}{r['p_target_above_cap']:>11.1%}{r['uncapped_held_gross']:>14.3f}"
            f"{r['p_uncapped_above_cap']:>9.1%}{r['held_gross']:>11.3f}{r['p_at_cap']:>10.1%}{r['turn_per_yr']:>9.1f}")
    dr = design_run()
    say(f"   beside it, the pre-registration's design run ({dr['source']}): its level book had no ADV floor, a "
        f"6-name level floor and a z-only fallback")
    for k in ("z_only_spec_book", "blend_spec_book"):
        r = dr[k]
        say(f"   {k + ' (design)':<18}{r['target_gross']:>13.3f}{r['p_target_above_cap']:>11.1%}"
            f"{r['uncapped_held_gross']:>14.3f}{r['p_uncapped_above_cap']:>9.1%}{r['held_gross']:>11.3f}"
            f"{r['p_at_cap']:>10.1%}{r['turn_per_yr']:>9.1f}")
    HL = bf.band_gross_capped(TL, band, cap / m) * m
    l1 = {"price_only": l1_reference(HL, tb["Rx_raw"], "L1 level-only book, price only"),
          "total_return": l1_reference(HL, tb["R_raw"], "L1 level-only book, total return")}
    say(f"\nL1 REFERENCE (§6.3): the level-only spec book, w_L with its own scalar, x{m}, band {band}, cap {cap}/m; "
        f"CRSP; 120-session cumulative return")
    for k, r in l1.items():
        say(f"   {k:<13} {r['first_held']}..{r['last']} ({r['sessions']} sessions): gross SR {r['gross_sr']:.3f}, "
            f"ann {r['ann_pct']:+.2f}%, vol {r['vol_pct']:.2f}%; 120-session 5th pct SB21 {r['p5_120_sb21'] * 100:+.2f}% "
            f"(median {r['p50_120_sb21'] * 100:+.2f}%); beside it, the empirical 5th pct of "
            f"{r['rolling_windows']} overlapping windows {r['p5_120_rolling_empirical'] * 100:+.2f}%")
    say("   the stop reads the PRICE-ONLY SB21 5th percentile (paper's P&L of record is price only), re-measured "
        "on the read date (H14); the total-return and empirical figures are context, not the rule")
    out = {"run_utc": run_utc, "code_head": head, "uncommitted_edits": bool(dirty), "spec_id": spec["spec_id"],
           "spec_sha256": bm._sha(bm.SPEC_PATH), "m": m, "cap": cap, "band": band, "z_share": lv["risk_share"],
           "fit_end": str(bm.FIT_END.date()), "gate": {"total_sr": tb["total_sr"], "price_sr": tb["price_sr"]},
           "section_3_3": rows, "l1": l1,
           "design_run_for_comparison": design_run()}
    OUT_JSON.write_text(json.dumps(out, indent=1) + "\n")
    OUT_TXT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT_TXT.relative_to(REPO)}, {OUT_JSON.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
