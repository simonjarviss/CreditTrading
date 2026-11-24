"""ops/daily_page.py: the one-page read of every paper account. Synthetic replies only: these
test the code, never a claim about the accounts."""
import json
import subprocess

import pytest

from ops import daily_page as dp

HDR = "date,equity,change_usd,read_at_utc"


def eod(rows):
    return "\n".join([HDR] + [f"{d},{e},{'' if c is None else c},2026-01-01T00:00:00+00:00" for d, e, c in rows])


def risk(asof="2026-01-07", severity="INFO", act=(), unmeasured=("stops",)):
    blocks = {k: {"status": "UNMEASURED" if k in unmeasured else "INFO", "lines": [f"{k} line one", f"{k} line two", f"{k} line three"]}
              for k in ("pnl", "drawdown", "stops", "exposure", "execution")}
    return json.dumps({"book": "x", "asof": asof, "generated_at": "2026-01-08T05:45:01-05:00", "spec_id": "spec.v1",
                       "severity": severity, "act_lines": list(act), "blocks": blocks})


SCORE = """# Shadow scoreboard — 2026-01-07

**Every figure is SIMULATED**

| book | started | last | scored | flat | unmeasured | late decisions | P&L price | P&L total return | Sharpe |
|---|---|---|---|---|---|---|---|---|---|
| aaa | 2026-01-02 | 2026-01-07 | 3 | 1 | 0 | 0 | +10 | +12 | needs 20 |
| bbb | 2026-01-05 | none | 0 | 2 | 1 | 0 | none | none | needs 20 |

## Correlation
"""
CEF = [("2026-01-05", 100000.0, None), ("2026-01-06", 100500.0, 500.0), ("2026-01-07", 100200.0, -300.0)]
C4 = [("2026-01-05", 100000.0, None), ("2026-01-06", 99900.0, -100.0), ("2026-01-07", 99800.0, -100.0)]


def reply(parts: dict, missing: dict | None = None, done=True) -> str:
    out = []
    for k, v in parts.items():
        out += [dp.BEGIN + k, v, "", dp.END + k]
    for k, path in (missing or {}).items():
        out.append(f"{dp.MISSING}{k} {path}")
    return "\n".join(out + ([dp.DONE] if done else [])) + "\n"


def full(**over):
    parts = {"eod_cef": eod(CEF), "risk_cef": risk(), "eod_c4": eod(C4), "risk_c4": risk(severity="WATCH"), "shadow": SCORE}
    parts.update(over)
    return {k: v for k, v in parts.items() if v is not None}


def test_the_page_sums_the_accounts_over_their_common_sessions():
    page = dp.build(reply(full()))
    c = page["combined"]
    assert (c["books"], c["first"], c["last"], c["sessions"]) == (["cef", "c4"], "2026-01-05", "2026-01-07", 2)
    assert (c["equity"], c["day_change"], c["to_date"], c["start_equity"]) == (200000.0, -400.0, 0.0, 200000.0)
    assert (c["hwm"], c["hwm_date"]) == (200400.0, "2026-01-06") and c["drawdown"] == pytest.approx(200000 / 200400 - 1)
    cef = page["books"][0]["official"]
    assert (cef["equity"], cef["day_change"], cef["to_date"], cef["sessions"], cef["hwm_date"]) == (100200.0, -300.0, 200.0, 2, "2026-01-06")
    text = dp.render(page)
    assert "severity **WATCH**" in text and "Blocks the risk report could not measure: stops" in text
    assert "| aaa | 2026-01-02 | 3 | 1 | 0 | 0 | +12 |" in text and "SIMULATED" in text
    assert "no combined risk budget" in text


def test_an_account_that_is_a_session_behind_is_named_and_never_padded():
    """C4 has no official row for the newest session: the combined line stops at the last
    session both have and says which account is behind. Nothing is carried forward."""
    page = dp.build(reply(full(eod_c4=eod(C4[:2]))))
    c = page["combined"]
    assert (c["last"], c["sessions"], c["equity"]) == ("2026-01-06", 1, 200400.0)
    assert c["behind"] == ["c4 (newest official row 2026-01-06)"]
    assert "c4 (newest official row 2026-01-06) is behind the other account" in dp.render(page)


def test_a_file_that_cannot_be_read_is_unmeasured_for_that_book_only():
    parts = full(eod_c4=None, risk_c4=None)
    page = dp.build(reply(parts, missing={"eod_c4": "/s/c4/eod_equity.csv", "risk_c4": "/s/c4/reports/risk/*.json"}))
    c4 = page["books"][1]
    assert "official" not in c4 and "risk" not in c4
    assert c4["unmeasured"] == ["official P&L: /s/c4/eod_equity.csv could not be read",
                                "risk report: /s/c4/reports/risk/*.json could not be read"]
    assert "official" in page["books"][0] and page["combined"] == {"unmeasured": "fewer than two accounts have a readable official history"}
    assert dp.render(page).count("UNMEASURED") >= 3


@pytest.mark.parametrize("bad, word", [
    ("date,equity,change_usd\n2026-01-05,1,", "header"),
    (HDR + "\n2026-01-05,abc,,x", "not a number"),
    (HDR + "\n2026-01-06,1,,x\n2026-01-05,1,,x", "increasing"),
    (HDR, "no rows"),
])
def test_a_malformed_equity_file_is_refused_by_name_never_half_read(bad, word):
    b = dp.build(reply(full(eod_cef=bad)))["books"][0]
    assert "official" not in b and word in b["unmeasured"][0] and "cef/eod_equity.csv" in b["unmeasured"][0]


def test_a_risk_report_in_another_shape_is_unmeasured_and_an_act_line_is_shown():
    b = dp.build(reply(full(risk_cef='{"asof": "2026-01-07"}')))["books"][0]
    assert "risk" not in b and "risk report" in b["unmeasured"][0]
    text = dp.render(dp.build(reply(full(risk_cef=risk(severity="ACT", act=["R1 fired: halve"])))))
    assert "severity **ACT**" in text and "- **ACT**: R1 fired: halve" in text


def test_a_risk_report_older_than_the_official_row_is_noted():
    text = dp.render(dp.build(reply(full(risk_cef=risk(asof="2026-01-06")))))
    assert "the risk report is as-of 2026-01-06 and the newest official row is 2026-01-07" in text


def test_a_scoreboard_without_its_table_is_unmeasured():
    page = dp.build(reply(full(shadow="# Shadow scoreboard — 2026-01-07\n\nno table\n")))
    assert "unmeasured" in page["shadow"] and "Shadow books (simulated)\n- UNMEASURED" in dp.render(page)


def test_a_reply_cut_short_or_a_failed_ssh_raises_and_nothing_is_guessed():
    def run_ok(cmd, **kw):
        assert cmd[0] == "ssh" and cmd[-1] == "sh -s" and kw["input"] == dp.REMOTE_SCRIPT
        return subprocess.CompletedProcess(cmd, 0, reply(full()), "")
    assert dp.DONE in dp.fetch(run=run_ok)
    for rc, out, word in [(0, reply(full(), done=False), "cut short"), (255, "", "exit 255")]:
        with pytest.raises(dp.PageError, match=word):
            dp.fetch(run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, rc, out, "ssh: connect to host 10.1.2.3 port 22: timed out"))
    with pytest.raises(dp.PageError, match="no end line"):
        dp.sections(dp.BEGIN + "eod_cef\nx\n")


def test_no_ssh_under_the_test_network_guard():
    with pytest.raises(dp.PageError, match="netguard"):
        dp.fetch()


def test_the_remote_script_only_reads():
    """`sudo cat`, `sudo test -r` and `sudo ls` and nothing else: no write, no systemctl, no
    broker tool. And the module imports no order code."""
    body = dp.REMOTE_SCRIPT
    sudo = [ln.split("sudo ", 1)[1].split()[0] for ln in body.replace(";", "\n").replace("$(", "\n").splitlines() if "sudo " in ln]
    assert sudo and set(sudo) <= {"cat", "test", "ls"}
    for word in ("systemctl", " rm ", " mv ", "tee", ">", "curl", "python"):
        assert word not in body.replace("2>/dev/null", ""), word
    import ast
    import pathlib
    tree = ast.parse(pathlib.Path(dp.__file__).read_text())
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m and (m.startswith("quantt") or "broker" in m or "alpaca" in m) for m in mods), mods
