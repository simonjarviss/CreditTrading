"""Tests for scripts/events/fetch_exdrift_corp_actions.py. A fake session only; the root conftest blocks sockets."""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

from scripts.events import fetch_exdrift_corp_actions as f

KEY, SECRET = "PKFAKEKEYID000000000", "fakeSecretValue0000000000000000000000000"


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body


class FakeSession:
    """Answers the three endpoints; records every call."""

    def __init__(self, ann_status=200, first_429=False):
        self.calls, self.ann_status, self.first_429 = [], ann_status, first_429
        self.headers = {"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET}

    def get(self, url, params=None, timeout=None, allow_redirects=None):
        self.redirect_flags = getattr(self, "redirect_flags", []) + [allow_redirects]
        self.calls.append((url, dict(params or {})))
        if self.first_429:
            self.first_429 = False
            return Resp(429, "slow down")
        if url.endswith(f.V1_PATH):
            if not params.get("page_token"):
                return Resp(200, {"corporate_actions": {"cash_dividends": [
                    {"id": "a", "symbol": "PTY", "rate": 0.1188, "ex_date": "2025-01-13", "record_date": "2025-01-13",
                     "payable_date": "2025-02-03", "process_date": "2025-02-03", "special": False}]},
                    "next_page_token": "p2"})
            return Resp(200, {"corporate_actions": {"capital_gains_distributions": [
                {"id": "b", "symbol": "PDI", "long_term_rate": 0.02, "short_term_rate": 0.01, "ex_date": "2024-12-27",
                 "record_date": "2024-12-27", "payable_date": "2025-01-02", "process_date": "2025-01-02"}]},
                "next_page_token": None})
        if url.endswith(f.ANN_PATH):
            if self.ann_status != 200:
                return Resp(self.ann_status, "endpoint deprecated")
            if params["symbol"] == "PTY" and params["since"] <= "2025-01-13" <= params["until"]:
                return Resp(200, [{"id": "x", "ca_type": "Dividend", "ca_sub_type": "cash", "initiating_symbol": "PTY",
                                   "declaration_date": "2025-01-02", "ex_date": "2025-01-13", "record_date": "2025-01-13",
                                   "payable_date": "2025-02-03", "cash": "0.1188"}])
            return Resp(200, [])
        if url.endswith(f.BARS_PATH):
            return Resp(200, {"bars": {"PTY": [{"t": "2026-02-12T05:00:00Z", "c": 14.1, "v": 1000}]},
                              "next_page_token": None})
        raise AssertionError(f"unexpected URL {url}")


def test_plan_is_read_only_and_the_windows_respect_90_days():
    reqs = f.plan(["PTY", "PDI"], dt.date(2023, 1, 1), dt.date(2023, 12, 31))
    assert {r["base"] for r in reqs} <= {f.DATA_BASE, f.PAPER_BASE}
    v1 = reqs[0]
    assert v1["params"]["end"] == (dt.date(2023, 12, 31) + dt.timedelta(days=f.PROCESS_LAG_DAYS)).isoformat()
    for s in ("PTY", "PDI"):
        w = [r["params"] for r in reqs[1:] if r["params"]["symbol"] == s]
        assert w[0]["since"] == "2023-01-01" and w[-1]["until"] == "2023-12-31"
        for a, b in zip(w, w[1:]):
            assert dt.date.fromisoformat(b["since"]) == dt.date.fromisoformat(a["until"]) + dt.timedelta(days=1)
        assert all((dt.date.fromisoformat(p["until"]) - dt.date.fromisoformat(p["since"])).days < 90 for p in w)


def test_dry_run_reads_no_key_and_sends_nothing(monkeypatch, capsys):
    import quantt.broker.alpaca_probe as probe

    def boom(*a, **k):
        raise AssertionError("the env file was read in a dry run")
    monkeypatch.setattr(probe, "read_env_file", boom)
    monkeypatch.setattr(f, "session_from_env", boom)
    assert f.main(["--dry-run", "--end", "2023-03-31"]) == 0
    out = capsys.readouterr().out
    assert "no key read, nothing sent" in out and "SEALED" not in out


def test_run_records_pages_and_a_refused_window_without_echoing_keys(tmp_path, monkeypatch, capsys):
    for n in ("CACHE", "RAW", "DIVS", "ANN", "BARS"):
        monkeypatch.setattr(f, n, tmp_path / getattr(f, n).name if n != "CACHE" else tmp_path)
    flags = pd.DataFrame({"check": ["X4_no_bar", "X5_nav_repeat"], "ticker": ["PTY", "PDI"],
                          "date": ["2026-02-12", "2026-02-13"]})
    s = FakeSession(first_429=True)
    raw = f.run(s, ["PTY", "PDI"], dt.date(2024, 12, 1), dt.date(2025, 2, 28), flags, sleep=lambda x: None)
    summ = f.write(raw, ["PTY", "PDI"])
    assert summ["v1_records"] == 2 and summ["announcement_rows"] == 1 and summ["bars"] == 1
    d = pd.read_parquet(f.DIVS)
    assert d.loc[d.ticker == "PDI", "amount"].iloc[0] == pytest.approx(0.03)
    a = pd.read_parquet(f.ANN)
    assert a.loc[a.ticker == "PTY", "declaration_date"].iloc[0] == pd.Timestamp("2025-01-02")
    bars_calls = [c for c in s.calls if c[0].endswith(f.BARS_PATH)]
    assert len(bars_calls) == 1 and bars_calls[0][1]["symbols"] == "PTY"     # only the X4_no_bar cell
    blob = f.RAW.read_text() + capsys.readouterr().out
    assert KEY not in blob and SECRET not in blob
    s2 = FakeSession(ann_status=410)
    raw2 = f.run(s2, ["PTY"], dt.date(2024, 12, 1), dt.date(2025, 2, 28), sleep=lambda x: None)
    a2 = f.parse_announcements(raw2["announcements"])
    assert set(a2["status"]) == {410} and a2["declaration_date"].isna().all()


def test_get_refuses_other_hosts():
    with pytest.raises(ValueError):
        f.get(FakeSession(), "https://api.alpaca.markets", "/v2/orders", {})


def test_parse_v1_refuses_an_unrequested_symbol_and_a_record_without_an_amount():
    with pytest.raises(f.FetchError, match="not requested"):
        f.parse_v1([{"cash_dividends": [{"symbol": "XYZ", "rate": 0.1, "ex_date": "2025-01-02"}]}], ["PTY"])
    with pytest.raises(f.FetchError, match="no rate"):
        f.parse_v1([{"capital_gains_distributions": [{"symbol": "PTY", "ex_date": "2025-01-02"}]}], ["PTY"])


def test_credentials_load_as_the_probe_loads_them(tmp_path):
    from quantt.broker.alpaca_probe import MissingCredential
    env = tmp_path / ".env"
    env.write_text("ALPACA_CEF_KEY_ID=" + KEY + "\n")
    with pytest.raises(MissingCredential) as e:
        f.session_from_env(env)
    assert "ALPACA_CEF_SECRET_KEY" in str(e.value) and KEY not in str(e.value)
    env.write_text(f"ALPACA_CEF_KEY_ID={KEY}\nALPACA_CEF_SECRET_KEY={SECRET}\n")
    s = f.session_from_env(env)
    assert s.headers["APCA-API-KEY-ID"] == KEY


def test_requests_name_only_the_17():
    from scripts.events.exdrift_trial import NAMES
    reqs = f.plan(f.names(), f.START, dt.date(2023, 3, 31))
    assert set(reqs[0]["params"]["symbols"].split(",")) == set(NAMES)
    assert {r["params"]["symbol"] for r in reqs[1:]} == set(NAMES)
