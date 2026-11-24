"""The live sanitiser: it drops identifiers, refuses what it does not know, and is idempotent.

Synthetic data tests the code, never a market claim: every figure below is invented to
exercise a code path and says nothing about the book. The identifiers are fabricated
shapes (a random UUID, a documentation-range IP), not real ones.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.report import evidence_log as elog
from scripts.report import snapshot_live as sl
from scripts.report.common import REPO

ORDER_ID = "11111111-2222-4333-8444-555555555555"
EVENT_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def _scores_json(order_id=ORDER_ID, extra_side=None):
    side = {"bp_vs_auction": 3.5, "order_ids": [order_id], "qty": 100, "side": "buy", "vwap": 10.0}
    if extra_side:
        side.update(extra_side)
    return json.dumps([{"auction_d": 10.0, "auction_pnl": 1.5, "auction_prev": 9.9, "fill_pnl": -0.5,
                        "held_qty": 100, "hold_pnl": 2.0, "sides": [side], "symbol": "AAA"}])


def _write_pull(d: Path, *, scores_extra_col=False, verify_line=None, event_extra=None,
                equity_note=None, side_extra=None, book="cef", dist=True):
    """A one-session pull. `book` and `dist` (2026-11-05) build a C4-shaped pull, with or
    without distribution_scores.csv; the defaults write the same bytes as before."""
    d.mkdir(parents=True, exist_ok=True)
    (d / "logs").mkdir(exist_ok=True)
    eq_h = "date,equity,last_equity,cash,long_market_value,short_market_value,n_positions,read_at_utc"
    eq_rows = ["2026-10-01,100100.00,100000.00,50000.00,60000.00,-10000.00,2,2026-10-01T21:10:00+00:00",
               "2026-10-02,100050.00,100100.00,50000.00,60000.00,-10000.00,2,2026-10-02T21:10:00+00:00"]
    if equity_note:
        eq_rows[1] = eq_rows[1].replace("2026-10-02T21:10:00+00:00", equity_note)
    (d / "equity.csv").write_text("\n".join([eq_h, *eq_rows]) + "\n")
    sc_cols = ("date,book,verdict,traded,n_orders,n_filled,alpaca_equity,alpaca_last_equity,"
               "alpaca_equity_change_usd,auction_pnl_usd,auction_hold_pnl_usd,auction_fill_pnl_usd,"
               "fill_vs_auction_bp,unmeasured,auction_condition,cost_basis,read_at,per_symbol_json")
    if scores_extra_col:
        sc_cols += ",account_id"
    pj = _scores_json(extra_side=side_extra).replace('"', '""')
    row = (f'2026-10-02,{book},PASS,True,1,1,100050.00,100100.00,-50.00,-48.00,-47.50,-0.50,3.50,,M,gross,'
           f'2026-10-02T17:30:00-04:00,"{pj}"')
    if scores_extra_col:
        row += ",PA0000000000"
    (d / "scores.csv").write_text(sc_cols + "\n" + row + "\n")
    ev = {"amount": 0.05, "id": EVENT_ID, "kind": "cash_dividend"}
    if event_extra:
        ev.update(event_extra)
    dj = json.dumps([{"alpaca_events": [ev], "dist_pnl": 5.0, "held_qty": 100, "per_share": 0.05,
                      "source": "Alpaca corporate actions", "symbol": "AAA"}]).replace('"', '""')
    if dist:
        (d / "distribution_scores.csv").write_text(
            "date,auction_pnl_usd,distribution_pnl_usd,auction_pnl_with_distributions_usd,unmeasured,"
            "per_symbol_json,source,label,written_at_utc\n"
            f'2026-10-02,-48.00,5.00,-43.00,,"{dj}",Alpaca corporate actions,distribution-adjusted,'
            "2026-10-02T21:30:00+00:00\n")
    (d / "tca.csv").write_text(
        "date,book,n_orders,n_full,shares_ordered,shares_filled,fill_rate_shares,slip_bp_buy,slip_bp_sell,"
        "slip_bp_all,slip_unmeasured,residual_gross_usd,residual_net_usd,residual_names,basis\n"
        f"2026-10-02,{book},1,1,100,100,1.0000,3.50,,3.50,,0.00,0.00,,fills vs official close\n")
    lines = [f"2026-10-02 PASS {book} traded 1 order(s), 1 filled; official PENDING (Alpaca's EOD history has "
             "no point for D 2026-10-02 (read 2026-10-02T17:30-04:00)); snapshot 17:30 ET -50.00 USD (gross); "
             "auction-marked -48.00 USD (gross); fill vs auction +3.5bp (+ = worse)",
             "shadow 2026-10-02: -40.00 USD (MODELLED: intended book at official closing prints; not broker "
             "evidence)"]
    if dist:
        lines.append("distributions 2026-10-02: -43.00 USD (distribution-adjusted)")
    if verify_line:
        lines.append(verify_line)
    (d / "logs" / "verify.out.log").write_text("\n".join(lines) + "\n")
    (d / "logs" / "verify.err.log").write_text("")
    return d


def _log(tmp: Path) -> Path:
    p = tmp / "EVIDENCE_LOG.md"
    p.write_text("# Evidence log\n\n## Entries\n")
    return p


def _all_text(out: Path) -> str:
    return "\n".join(p.read_text() for p in sorted(out.rglob("*.csv")))


def _ingest(pull, tmp: Path, **kw):
    """Every test writes both roots under tmp_path: never the repository's own cache."""
    return sl.ingest(pull, "cef", out_root=tmp / "live", cache_root=tmp / "cache", **kw)


def test_identifiers_are_dropped_rows_go_private_and_aggregates_carry_no_name(tmp_path):
    pull = _write_pull(tmp_path / "pull")
    res = _ingest(pull, tmp_path, log=None)
    assert res["status"] == "ingested"
    agg, rows = _all_text(tmp_path / "live"), _all_text(tmp_path / "cache")
    for text in (agg, rows):
        assert ORDER_ID not in text and EVENT_ID not in text and "order_ids" not in text
    assert ",buy,100,10.0,3.5" in (tmp_path / "cache" / "cef" / "scores_by_symbol.csv").read_text()
    assert "cash_dividend:0.05" in (tmp_path / "cache" / "cef" / "distributions_by_symbol.csv").read_text()
    assert "AAA" not in agg                                   # no symbol anywhere in the tracked half
    for p in (tmp_path / "live" / "cef").glob("*.csv"):
        header = p.read_text().splitlines()[0].split(",")
        assert not set(header) & sl.ROW_LEVEL_COLUMNS, p.name
    daily = (tmp_path / "live" / "cef" / "fill_cost_daily.csv").read_text().splitlines()
    assert daily[1].startswith("2026-10-02,1,1,0,1000.00,3.50,3.50,3.50")


def test_unknown_column_refuses_naming_it_and_writes_nothing(tmp_path):
    pull = _write_pull(tmp_path / "pull", scores_extra_col=True)
    with pytest.raises(sl.SanitiseError, match="account_id"):
        _ingest(pull, tmp_path, log=None)
    assert not (tmp_path / "live").exists() and not (tmp_path / "cache").exists()


def test_unknown_json_key_refuses_naming_it(tmp_path):
    pull = _write_pull(tmp_path / "pull", side_extra={"client_order_id": "x"})
    with pytest.raises(sl.SanitiseError, match="client_order_id"):
        _ingest(pull, tmp_path / "a", log=None)
    pull2 = _write_pull(tmp_path / "pull2", event_extra={"cusip": "000000000"})
    with pytest.raises(sl.SanitiseError, match="cusip"):
        _ingest(pull2, tmp_path / "b", log=None)


@pytest.mark.parametrize("planted, name", [
    ("2026-10-02T21:10:00+00:00 from 192.0.2.10", "ipv4"),
    ("2026-10-02T21:10:00+00:00 " + "0f0f0f0f-1111-4222-8333-444444444444", "uuid"),
    ("2026-10-02T21:10:00+00:00 PA1B2C3D4E5F", "alpaca account number"),
    ("2026-10-02T21:10:00+00:00 example.invalid.cloudapp.azure.com", "azure host or vault"),
])
def test_an_identifier_in_a_kept_field_refuses_without_printing_it(tmp_path, planted, name):
    pull = _write_pull(tmp_path / "pull", equity_note=planted)
    with pytest.raises(sl.SanitiseError) as e:
        _ingest(pull, tmp_path, log=None)
    assert name in str(e.value) and "read_at_utc" in str(e.value)
    assert planted.split(" ", 1)[1] not in str(e.value)


def test_unknown_verify_line_and_unknown_file_refuse(tmp_path):
    pull = _write_pull(tmp_path / "pull", verify_line="something new the VM prints")
    with pytest.raises(sl.SanitiseError, match="line 4"):
        _ingest(pull, tmp_path / "a", log=None)
    pull2 = _write_pull(tmp_path / "pull2")
    (pull2 / "plan.json").write_text("{}")
    with pytest.raises(sl.SanitiseError, match="plan.json"):
        _ingest(pull2, tmp_path / "b", log=None)


def test_row_files_are_refused_where_git_can_see_them(tmp_path):
    """The ruling of 2026-11-03 in code: rows never go to a path git tracks."""
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    pull = _write_pull(tmp_path / "pull")
    with pytest.raises(sl.SanitiseError, match="rows go only to the gitignored cache"):
        sl.ingest(pull, "cef", out_root=repo / "live", cache_root=repo / "visible_cache", log=None)
    assert not (repo / "visible_cache").exists() and not (repo / "live").exists()
    (repo / ".gitignore").write_text("private/\n")
    res = sl.ingest(pull, "cef", out_root=repo / "live", cache_root=repo / "private", log=None)
    assert res["status"] == "ingested" and (repo / "private" / "cef" / "scores_by_symbol.csv").exists()


def test_the_repositorys_cache_is_gitignored():
    rel = "results/report/_cache_live/cef/scores_by_symbol.csv"
    r = subprocess.run(["git", "-C", str(REPO), "check-ignore", rel], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == rel
    assert sl.CACHE == REPO / "results" / "report" / "_cache_live"


def test_a_row_level_column_is_refused_in_the_aggregates():
    with pytest.raises(sl.SanitiseError, match="symbol"):
        sl._refuse_row_columns("x.csv", ["date", "symbol"])


def test_idempotent_same_pull_adds_nothing(tmp_path):
    pull = _write_pull(tmp_path / "pull")
    log = _log(tmp_path)
    first = _ingest(pull, tmp_path, log=log)
    snap = {p: p.read_bytes() for p in tmp_path.rglob("*.csv") if "pull" not in p.parts}
    log_text = log.read_text()
    second = _ingest(pull, tmp_path, log=log)
    assert first["entries"] == 1 and second == {"pull": first["pull"], "status": "already ingested",
                                                "added": 0, "revised": 0, "entries": 0}
    assert {p: p.read_bytes() for p in tmp_path.rglob("*.csv") if "pull" not in p.parts} == snap
    assert log.read_text() == log_text
    forced = _ingest(pull, tmp_path, log=log, force=True)
    assert forced["added"] == 0 and forced["entries"] == 0
    assert {p: p.read_bytes() for p in tmp_path.rglob("*.csv") if "pull" not in p.parts} == snap


def test_live_entry_labels_the_snapshot_and_validates(tmp_path):
    pull = _write_pull(tmp_path / "pull")
    log = _log(tmp_path)
    _ingest(pull, tmp_path, log=log)
    entries = elog.parse(log.read_text())
    assert [e.id for e in entries] == ["E-2026-10-02-90"]
    assert elog.validate(entries) == []
    figs = " ".join(entries[0].figures)
    assert "not the P&L of record" in figs
    assert "official EOD equity change UNMEASURED" in figs     # never filled from the snapshot
    assert "AAA" not in log.read_text()


def test_pre_ruling_official_wording_is_stored_as_a_snapshot():
    v, _, _ = sl.parse_verify("2026-10-08 PASS cef traded 8 order(s), 8 filled; alpaca equity chg -8.91 USD "
                              "(official, gross); auction-marked +71.09 USD (gross); fill vs auction +15.8bp "
                              "(+ = worse)\n")
    assert v[0]["snapshot_1730_usd"] == "-8.91" and v[0]["official_usd"] == ""
    assert "pre-2026-10-19 wording" in v[0]["verify_label"]


# ------------------------------------------- a file one book may lack (2026-11-05) --
def _c4_ingest(pull, tmp: Path, **kw):
    return sl.ingest(pull, "c4", out_root=tmp / "live", cache_root=tmp / "cache", **kw)


def test_c4_without_distribution_scores_ingests_and_its_entry_names_the_file_unmeasured(tmp_path):
    """C4's first pulls carry no distribution_scores.csv (its verify scores distributions two
    sessions late). On origin/main the core's rule refused them: C4's days could not be logged."""
    pull = _write_pull(tmp_path / "pull", book="c4", dist=False)
    log = _log(tmp_path)
    res = _c4_ingest(pull, tmp_path, log=log)
    assert res["status"] == "ingested" and res["entries"] == 1
    live, cache = tmp_path / "live" / "c4", tmp_path / "cache" / "c4"
    assert (live / "scores.csv").exists() and (cache / "scores_by_symbol.csv").exists()
    # No distribution table of any kind: not an empty one, and never a zero.
    assert sorted(p.name for p in (tmp_path / "live").rglob("*distribution*")) == []
    assert sorted(p.name for p in (tmp_path / "cache").rglob("*distribution*")) == []
    entries = elog.parse(log.read_text())
    assert [e.id for e in entries] == ["E-2026-10-02-91"] and elog.validate(entries) == []
    dist_figs = [f for f in entries[0].figures if "distribution" in f]
    assert dist_figs == ["distribution-adjusted P&L UNMEASURED: distribution_scores.csv not in this pull [U]"]


def test_c4_pull_that_carries_distribution_scores_is_ingested_like_the_cores(tmp_path):
    """Optional is not ignored: once C4's verify writes the file, it is sanitised and logged."""
    pull = _write_pull(tmp_path / "pull", book="c4")
    log = _log(tmp_path)
    _c4_ingest(pull, tmp_path, log=log)
    assert "-43.00" in (tmp_path / "live" / "c4" / "distribution_scores.csv").read_text()
    assert "cash_dividend:0.05" in (tmp_path / "cache" / "c4" / "distributions_by_symbol.csv").read_text()
    figs = elog.parse(log.read_text())[0].figures
    assert "distribution-adjusted P&L -43.00 USD (credits distributions paper does not) [S]" in figs
    assert not any("UNMEASURED: distribution_scores.csv" in f for f in figs)


def test_cef_without_distribution_scores_still_refuses_naming_it(tmp_path):
    """Unchanged for the core: its pull must carry the file. The refusal through `ingest` is
    the same as on origin/main; `sanitise` handed such a pull directly now refuses by name
    too (on origin/main it raised a bare KeyError, which main() does not catch)."""
    pull = _write_pull(tmp_path / "pull", dist=False)
    with pytest.raises(sl.SanitiseError, match=r"^distribution_scores\.csv: missing from the pull at "):
        _ingest(pull, tmp_path, log=_log(tmp_path))
    assert not (tmp_path / "live").exists() and not (tmp_path / "cache").exists()
    files = {p.relative_to(pull).as_posix(): p.read_bytes() for p in pull.rglob("*") if p.is_file()}
    with pytest.raises(sl.SanitiseError, match="distribution_scores.csv: missing"):
        sl.sanitise(files, "cef")
    assert sl.required("distribution_scores.csv", "cef") and not sl.required("distribution_scores.csv", "c4")


def _two_session_cef_pull(d: Path) -> Path:
    """The core's usual evening shape: a second session (10-05) whose distribution row is not
    scored yet (two sessions late), and an EOD history with a point for each session, one of
    which disagrees with the snapshot."""
    _write_pull(d)
    with (d / "equity.csv").open("a") as f:
        f.write("2026-10-05,100080.00,100050.00,50000.00,60000.00,-10000.00,2,2026-10-05T21:10:00+00:00\n")
    pj = _scores_json().replace('"', '""')
    with (d / "scores.csv").open("a") as f:
        f.write(f'2026-10-05,cef,PASS,True,1,1,100080.00,100050.00,30.00,28.00,27.00,1.00,-2.00,,M,gross,'
                f'2026-10-05T17:30:00-04:00,"{pj}"\n')
    with (d / "tca.csv").open("a") as f:
        f.write("2026-10-05,cef,1,1,100,100,1.0000,-2.00,,-2.00,,0.00,0.00,,fills vs official close\n")
    with (d / "logs" / "verify.out.log").open("a") as f:
        f.write("2026-10-05 PASS cef traded 1 order(s), 1 filled; official PENDING (Alpaca's EOD history has "
                "no point for D 2026-10-05 (read 2026-10-05T17:30-04:00)); snapshot 17:30 ET +30.00 USD (gross); "
                "auction-marked +28.00 USD (gross); fill vs auction -2.0bp (+ = worse)\n"
                "shadow 2026-10-05: 25.00 USD (MODELLED: intended book at official closing prints; not broker "
                "evidence)\n")
    (d / "eod_equity.csv").write_text("date,equity,change_usd,read_at_utc\n"
                                      "2026-10-01,100100.00,,2026-10-02T08:40:00+00:00\n"
                                      "2026-10-02,100050.00,-50.00,2026-10-03T08:40:00+00:00\n"
                                      "2026-10-05,100079.00,29.00,2026-10-06T08:40:00+00:00\n")
    return d


# sha256 of every file a core ingest writes, from scripts/report/snapshot_live.py at origin/main
# 718b699, before the C4 change: the no-op proof (CLAUDE.md: prove a no-op byte-for-byte).
CEF_GOLDEN = {
    "EVIDENCE_LOG.md": "5c41be81c705fe49f61f824d84c82867e9effd4d882ff7e3f94dcbe7079c3512",
    "cache/cef/distributions_by_symbol.csv": "984163572061bdc183212a8d487c1e8c7f62c281b7ce60cd1edbd4e35717a40a",
    "cache/cef/scores_by_symbol.csv": "63371a186e8e092226d8eeb61e8f6aa126284b603c30e08ceeee7011a91c1ce6",
    "cache/cef/tca_residual_names.csv": "5da04bee38cead4dee9c3972fdc471c99f47d31eb4f3b9cc652d623a1e0baea6",
    "cache/cef/verify_detail.csv": "93ec26b9a8eef097f0565d56ed28940c4fbba5ffbcaefebb647315aa105ba816",
    "live/cef/distribution_scores.csv": "462e971b3e0484aeecab5dc6e0a5c8752392cf47de5267e5b61a6084fce3cae0",
    "live/cef/eod_equity.csv": "483a37dc9a43418406436c3b9055e9b567644ac4167aa26b71106047818be370",
    "live/cef/equity_snapshot.csv": "ea68661e0474b345e83ca0ec51a7a2eb7ee432c4871fa6be319b8ae3eea18646",
    "live/cef/fill_cost_daily.csv": "474a6e77679f44405539685ae72b1fd9a851e558477cb5c29af00a885475148a",
    "live/cef/fill_cost_pooled.csv": "ebf26540f02df8c16f9b206430434d219cd1ed22440348bb095102de454f986e",
    "live/cef/pulls.csv": "495fc61160846dd0a886a67eb7cb581a78074a39981d5ac57f141e63ee0db6bf",
    "live/cef/scores.csv": "205640179bc8621a50468f2a99ee23e9c9dc240a1fe6b3ec8488fee4568c7e1e",
    "live/cef/tca.csv": "cbb932017ae8c86426d3a6f0b7d300e7c00c0f19442d5b0262660a46b2707bd1",
    "live/cef/verify.csv": "ebf728cdbdfcc00644737dd5356df55dfba8e44f138a62fedc4fdde3a2f13387",
    "live/cef/verify_distributions.csv": "164dc91ab4f6d7c1916c8e1af5871196fea2aa48170ca9f430e232e6fd607652",
    "live/cef/verify_shadow.csv": "45a03451c3a6d994c97cdb30b1ab0b3019d4727bf469c8c8a6fc6452146c0921",
}


def test_cef_output_is_byte_identical_to_before_the_c4_change(tmp_path):
    pull = _two_session_cef_pull(tmp_path / "pull")
    log = _log(tmp_path)
    _ingest(pull, tmp_path, log=log)
    got = {p.relative_to(tmp_path).as_posix(): sl.sha256_bytes(p.read_bytes())
           for p in [*(tmp_path / "live").rglob("*.csv"), *(tmp_path / "cache").rglob("*.csv"), log]}
    assert got == CEF_GOLDEN


def test_a_missing_eod_point_is_not_called_a_missing_file(tmp_path):
    """The pull carries eod_equity.csv but no point for the session yet (the usual evening):
    the entry says so, and says "not in this pull" only when the file is truly absent. On
    origin/main both read "not in this pull" (E-2026-11-03-90's pull had the file)."""
    pull = _write_pull(tmp_path / "pull")
    (pull / "eod_equity.csv").write_text("date,equity,change_usd,read_at_utc\n"
                                         "2026-10-01,100100.00,,2026-10-02T08:40:00+00:00\n")
    log = _log(tmp_path)
    _ingest(pull, tmp_path, log=log)
    figs = elog.parse(log.read_text())[0].figures
    assert ("official EOD equity change UNMEASURED: eod_equity.csv in this pull has no change_usd for "
            "2026-10-02 [U]") in figs
    assert not any("not in this pull" in f for f in figs)
    pull2 = _write_pull(tmp_path / "pull2")
    log2 = tmp_path / "log2"
    log2.mkdir()
    _ingest(pull2, log2, log=_log(log2))
    assert ("official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]"
            in elog.parse((log2 / "EVIDENCE_LOG.md").read_text())[0].figures)
