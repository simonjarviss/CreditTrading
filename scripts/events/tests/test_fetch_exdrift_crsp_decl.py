"""Tests for scripts/events/fetch_exdrift_crsp_decl.py: a fake source and fake caches; no network."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from scripts.events import fetch_exdrift_crsp_decl as c
from scripts.events.exdrift_trial import NAMES

KEY, SECRET = "AKIAFAKEKEY123", "fakeSecret/Value/0000"


def _names():
    rows = [dict(permno=10000 + i, ticker=t, namedt="2010-01-01", nameendt="2024-12-31", shrcd=14)
            for i, t in enumerate(NAMES)]
    rows.append(dict(permno=99999, ticker="SEALED", namedt="2010-01-01", nameendt="2024-12-31", shrcd=14))
    return pd.DataFrame(rows)


def _dist(perms):
    return pd.DataFrame([dict(permno=p, distcd=1232, divamt=0.1, dclrdt="2023-01-03", exdt="2023-01-12",
                              rcrddt="2023-01-13", paydt="2023-02-01") for p in perms])


class FakeCon:
    def __init__(self):
        self.sql = []

    def execute(self, sql):
        self.sql.append(sql)
        nm = _names()

        class R:
            def __init__(self, df):
                self._df = df

            def df(self):
                return self._df
        if "dsenames" in sql:
            return R(nm[nm.ticker.isin(NAMES)])
        return R(_dist(nm[nm.ticker.isin(NAMES)].permno))


def test_dry_run_loads_nothing(capsys):
    def boom():
        raise AssertionError("a source was built in a dry run")
    assert c.main(["pull", "--dry-run"], source_factory=boom) == 0
    out = capsys.readouterr().out
    assert "s3://<bucket>/wrds/crsp_a_stock/dsedist.parquet" in out and "SEALED" not in out


def test_pull_writes_the_17_only_and_redacts(tmp_path, capsys):
    con = FakeCon()
    src = lambda: c.Source(con=con, path=lambda s, t: f"s3://realbucket/wrds/{s}/{t}.parquet",       # noqa: E731
                           redact=c.Redactor({KEY: "<redacted>", "realbucket": "<bucket>"}))
    assert c.main(["pull", "--out", str(tmp_path / "o")], source_factory=src) == 0
    d = pd.read_parquet(tmp_path / "o" / c.DIST_FILE)
    assert set(d.ticker) == set(NAMES) and "SEALED" not in set(d.ticker)
    man = json.loads((tmp_path / "o" / c.MANIFEST).read_text())
    assert "realbucket" not in json.dumps(man) and man["rows"] == len(NAMES)
    assert all("'SEALED'" not in q for q in con.sql)
    assert "realbucket" not in capsys.readouterr().out


def test_permno_map_raises_on_two_permnos_or_none():
    nm = _names()
    nm = pd.concat([nm, pd.DataFrame([dict(permno=12345, ticker="PTY", namedt="2023-06-01", nameendt="2024-12-31", shrcd=14)])])
    with pytest.raises(c.CrspDeclError, match="PTY"):
        c.permno_map(nm, NAMES)
    with pytest.raises(c.CrspDeclError, match="NAD"):
        c.permno_map(_names()[lambda z: z.ticker != "NAD"], NAMES)


def test_tidy_refuses_a_row_outside_the_window():
    perm = c.permno_map(_names(), NAMES)
    d = _dist(perm.permno)
    d.loc[0, "exdt"] = "2025-01-15"
    with pytest.raises(c.CrspDeclError, match="outside"):
        c.tidy(d, perm)


def test_stage_from_a_cached_extract(tmp_path):
    src = tmp_path / "cache"
    src.mkdir()
    _names().to_parquet(src / "dsenames.parquet")
    perm = c.permno_map(_names(), NAMES)
    d = pd.concat([_dist(perm.permno), _dist([99999])])
    for col in ("dclrdt", "exdt", "rcrddt", "paydt"):
        d[col] = pd.to_datetime(d[col])
    d.to_parquet(src / "dsedist_abc.parquet")
    (src / "_manifest.json").write_text(json.dumps({"dsedist_abc": {"pulled_utc": "2026-10-19T00:00:00Z", "sql": "SELECT"}}))
    assert c.main(["stage", "--from", str(src), "--out", str(tmp_path / "o")]) == 0
    out = pd.read_parquet(tmp_path / "o" / c.DIST_FILE)
    assert 99999 not in set(out.permno) and len(out) == len(NAMES)
