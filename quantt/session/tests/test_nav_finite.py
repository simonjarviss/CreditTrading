"""Gate 5 and the stale-NAV gate refuse an infinite NAV (review of fetch_daily's NAV half, 2026-10-28).

WHY. `run.last_navs` (gate 5) and `nav_gate.panel_rows` filtered NAVs with
`notna() & > 0`, which +inf passes: an infinite NAV dated D would count as D's
NAV for gate 5, and the stale-NAV gate would compare against it (as NAV(D) or as
the previous row). fetch_daily's `has_nav` now refuses it, and these two use the
same test, `isfinite & > 0`. No NAV in the panels is infinite (measured
2026-10-28), so the change must be a no-op on them: the real-panel test below
decides the same session with the pre-fix filters and with the new ones and
requires the same exit, plan.json, orders and plan_sha.

The unit tests are synthetic panels under tmp_path. The real-panel test copies
`data/cef/` into tmp_path (read only, skipped without it), using test_nav_gate's
own real-panel fixture; CEFConnect is a fixture there, its numbers test inputs.
"""
import datetime as dt
import json
import math

import pandas as pd
import pytest

from quantt.session import nav_gate as ng
from quantt.session import run as rn
from quantt.session.tests.test_nav_gate import (ET, FakeCC, _real_panel_ready,
                                                _real_panels_with_the_documented_copies)
from quantt.session.tests.test_run import BOOK, LATE, FakeClient

INF = math.inf
D24, D25, D23 = dt.date(2026, 9, 24), dt.date(2026, 9, 25), dt.date(2026, 9, 23)


def write(path, rows):
    pd.DataFrame([{"date": pd.Timestamp(d), "nav": v, "ticker": t} for t, d, v in rows]
                 ).to_parquet(path)


def test_gate5_does_not_count_an_infinite_nav(tmp_path):
    """AAA's NAV dated 2026-09-25 is +inf: its last NAV is 2026-09-24, so gate 5
    refuses it as not dated D. On 377fe41 +inf passed as D's NAV. NaN, -inf and
    0 were already refused and still are."""
    p = tmp_path / "cef_nav.parquet"
    write(p, [("AAA", D24, 10.0), ("AAA", D25, INF), ("BBB", D25, 20.0),
              ("CCC", D24, 30.0), ("CCC", D25, -INF), ("DDD", D24, 40.0), ("DDD", D25, 0.0),
              ("EEE", D24, 50.0), ("EEE", D25, float("nan"))])
    got = rn.last_navs(p, D25, ["AAA", "BBB", "CCC", "DDD", "EEE"])
    assert got == {"AAA": D24, "BBB": D25, "CCC": D24, "DDD": D24, "EEE": D24}


def test_the_stale_nav_gate_skips_an_infinite_nav(tmp_path):
    """AAA: an +inf row between two equal NAVs. The previous NAV is the finite
    one, so NAV(D) repeats it and trigger 1 fires; on 377fe41 the +inf was the
    previous row and the stale copy went unseen. BBB: NAV(D) is +inf, so BBB
    has no NAV dated D for this gate (gate 5's to refuse); on 377fe41 it was
    judged on +inf."""
    N = pd.DataFrame([{"date": pd.Timestamp(d), "nav": v, "ticker": t} for t, d, v in (
        ("AAA", D23, 10.0), ("AAA", D24, INF), ("AAA", D25, 10.0),
        ("BBB", D24, 20.0), ("BBB", D25, INF))])
    rows = ng.panel_rows(N, D25, ("AAA", "BBB"))
    assert rows == {"AAA": (10.0, D23, 10.0)}
    assert [r.ticker for r in ng.repeats(N, D25, ("AAA", "BBB"))] == ["AAA"]


# ------------------------------------------------------------- the pre-fix filters, by hand

def _last_navs_pre_fix(nav_path, asof, universe):
    """`run.last_navs` as it was at 377fe41 (`notna() & > 0`), copied here as the
    reference the no-op is measured against."""
    N = pd.read_parquet(nav_path, columns=["date", "ticker", "nav"])
    N = N[N["ticker"].isin(list(universe))].copy()
    N["date"] = pd.to_datetime(N["date"]).dt.normalize()
    N = N[N["date"] <= pd.Timestamp(asof)]
    assert not N.duplicated(["date", "ticker"]).any()
    N = N[N["nav"].notna() & (N["nav"] > 0)]
    last = N.groupby("ticker")["date"].max()
    return {s: (None if last.get(s) is None else last.get(s).date()) for s in universe}


def _panel_rows_pre_fix(nav, asof, universe):
    """`nav_gate.panel_rows` as it was at 377fe41 (`notna() & > 0`)."""
    n = nav[nav["ticker"].isin(list(universe))][["date", "ticker", "nav"]].copy()
    n["date"] = pd.to_datetime(n["date"]).dt.normalize()
    n = n[n["date"] <= pd.Timestamp(asof)]
    assert not n.duplicated(["date", "ticker"]).any()
    n = n[n["nav"].notna() & (n["nav"] > 0)]
    out = {}
    for tk in sorted(universe):
        rows = n[n["ticker"] == tk].sort_values("date")
        if len(rows) < 2 or rows["date"].iloc[-1] != pd.Timestamp(asof):
            continue
        out[tk] = (float(rows["nav"].iloc[-1]), rows["date"].iloc[-2].date(),
                   float(rows["nav"].iloc[-2]))
    return out


@pytest.mark.skipif(not _real_panel_ready(), reason="real CEF panels absent (data/ is "
                                                     "gitignored); the synthetic tests still run")
def test_on_the_real_panel_the_finite_filter_is_byte_identical(tmp_path, monkeypatch):
    """The no-op proof, test_nav_gate's real-panel pattern: the live spec, the
    real sleeve and a copy of the real panels (with that test's documented stale
    copies put back), decided as of 2026-09-25 on a held book, the stale-NAV gate
    in report mode. (a) Decided with the pre-fix filters (`_last_navs_pre_fix`
    for gate 5, `_panel_rows_pre_fix` for the gate) and with the new ones: the
    same exit, the same plan.json byte for byte, the same orders and plan_sha.
    The real panels come out unchanged. (b) The same copy with one deployed
    name's 2026-09-25 NAV set to +inf: gate 5 now refuses that name as not dated
    D. Part (a) passes on 377fe41 by construction; part (b) failed there."""
    from src.deploy.sleeves import cef_discount as cefmod
    real = {f: f.read_bytes() for f in (cefmod.PX_PATH, cefmod.NAV_PATH)}
    (tmp_path / "panels").mkdir()
    _real_panels_with_the_documented_copies(tmp_path / "panels", monkeypatch)
    spec = json.loads((rn.REPO / "ops/specs/cef_discount.frozen.json").read_text())
    p = rn.spec_params(spec)
    asof = D25
    eve = dt.datetime(2026, 9, 25, 22, 0, tzinfo=ET)
    uni = p["universe"]
    day1 = rn.sleeve_targets(spec, p["capital_usd"], asof, {}, p["capital_usd"], True)
    closes = {s: v[0] for s, v in rn.last_closes(cefmod.PX_PATH, asof, uni).items()}
    held = {t.instrument: int(0.5 * p["capital_usd"] * float(t.weight) / closes[t.instrument])
            for t in day1 if t.weight}
    held = {s: q for s, q in held.items() if q}
    cc = {s: (10.0, 10.0) for s in uni}
    cc.update({"PDI": (15.06, 15.10), "DSL": (11.11, None), "BIT": (None, None)})

    def one(sub, navs):
        state = tmp_path / sub / "state"
        state.mkdir(parents=True)
        client = FakeClient(state, positions=held, clock_ts=eve)
        client.long_mv = sum(q * closes[s] for s, q in held.items() if q > 0)
        client.short_mv = sum(q * closes[s] for s, q in held.items() if q < 0)
        client.maint = 0.5 * (client.long_mv - client.short_mv)     # fixture, not a measurement
        deps = rn.Deps(
            client=client, env={"QUANTT_STATE_DIR": str(state), "DRY_RUN": "0"},
            refresh=lambda a, t: rn.RefreshResult(exit=0, tail="fixture"),
            closes=lambda a, u: rn.last_closes(cefmod.PX_PATH, a, u),
            navs=lambda a, u: navs(cefmod.NAV_PATH, a, u),
            targets=lambda a, h, eq, op, **kw: rn.sleeve_targets(spec, p["capital_usd"], a, h,
                                                                 eq, op, **kw),
            halts=lambda: [], utcnow=lambda: eve.astimezone(dt.timezone.utc),
            out=type("O", (), {"write": lambda s, x: None, "flush": lambda s: None})(),
            execution={**LATE, "bp_shortfall": "scale"},
            stale_nav=ng.REPORT,
            nav_gate=ng.PanelGate(nav_path=cefmod.NAV_PATH, log_path=tmp_path / "log.csv",
                                  lock_path=tmp_path / ".lock", reader=FakeCC(cc)))
        code = rn.run_session(BOOK, spec, deps)
        return code, (state / "2026-09-28" / "plan.json").read_bytes()

    # (a) the pre-fix filters against the new ones, on the same copy.
    copy_before = cefmod.NAV_PATH.read_bytes()
    with monkeypatch.context() as m:
        m.setattr(ng, "panel_rows", _panel_rows_pre_fix)
        c_old, plan_old = one("old", _last_navs_pre_fix)
    c_new, plan_new = one("new", rn.last_navs)
    assert cefmod.NAV_PATH.read_bytes() == copy_before
    assert all(f.read_bytes() == b for f, b in real.items()), "a real panel changed"
    old, new = json.loads(plan_old), json.loads(plan_new)
    assert c_new == c_old == rn.EXIT_PLANNED and new["status"] == "decided"
    assert new["orders"] and new["orders"] == old["orders"]
    assert new["plan_sha"] == old["plan_sha"]
    assert plan_new == plan_old, "plan.json differs between the pre-fix and the new filters"
    assert new["nav_gate"]["checks"] == old["nav_gate"]["checks"]

    # (b) one deployed name's NAV dated D set to +inf.
    victim = "PCN"
    assert victim in uni
    N = pd.read_parquet(cefmod.NAV_PATH)
    hit = (N["ticker"] == victim) & (pd.to_datetime(N["date"]).dt.normalize() == pd.Timestamp(asof))
    assert hit.sum() == 1
    N.loc[hit, "nav"] = INF
    N.to_parquet(cefmod.NAV_PATH)
    c_inf, plan_inf = one("inf", rn.last_navs)
    got = json.loads(plan_inf)
    assert c_inf == rn.EXIT_REFUSED and got["status"] == "refused", (c_inf, got.get("status"))
    data = [r for r in got["refusals"] if r["gate"] == "data"]
    assert any(victim in r["detail"] and f"not dated {asof}" in r["detail"] for r in data), data
    assert all(f.read_bytes() == b for f, b in real.items()), "a real panel changed"
