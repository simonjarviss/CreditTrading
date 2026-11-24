"""The evidence log's format check and its append-only rule. Synthetic entries test the
parser only; none of their figures is a claim about the book."""
from __future__ import annotations

from scripts.report import evidence_log as elog

GOOD = """### E-2026-09-10-01 · A synthetic correction entry
- kind: correction
- era: HISTORY
- date: 2026-09-10
- figures:
  - figure one 1.0 -> 2.0 [S]
  - figure two 3 [V]
- source: `results/x.md` @ `abc1234`
- supports: §2, §4
- status: supersedes nothing (test)"""

LIVE = """### E-2026-10-02-90 · A synthetic live day
- kind: live-pnl
- era: ALPACA
- date: 2026-10-02
- figures:
  - snapshot -50.00 USD [S]
- source: `results/report/data/live/cef/scores.csv` @ `pull:0123456789ab`
- supports: §5
- status: current"""


def test_a_good_entry_validates():
    assert elog.validate(elog.parse(GOOD + "\n\n" + LIVE)) == []


def test_defects_are_named():
    bad = GOOD.replace(" [S]", "").replace("era: HISTORY", "era: ALPACA").replace("@ `abc1234`", "")
    errs = " | ".join(elog.validate(elog.parse(bad)))
    assert "without a [V]/[S]/[U] tag" in errs
    assert "era must be HISTORY" in errs
    assert "source must name" in errs


def test_duplicate_and_mismatched_date():
    errs = elog.validate(elog.parse(GOOD + "\n\n" + GOOD.replace("date: 2026-09-10", "date: 2026-09-11")))
    assert any("duplicate id" in e for e in errs)
    assert any("does not match the id" in e for e in errs)


def test_append_only_allows_appends_and_refuses_edits_deletes_inserts():
    old = "# log\n\n" + GOOD
    assert elog.check_append_only(old, old + "\n\n" + LIVE) == []
    assert any("edited" in e for e in elog.check_append_only(old, old.replace("1.0 -> 2.0", "1.0 -> 2.5")))
    assert any("removed" in e for e in elog.check_append_only(old + "\n\n" + LIVE, old))
    inserted = "# log\n\n" + LIVE.replace("2026-10-02-90", "2026-09-01-01").replace(
        "era: ALPACA", "era: HISTORY").replace("date: 2026-10-02", "date: 2026-09-01") + "\n\n" + GOOD
    assert any("appended" in e for e in elog.check_append_only(old, inserted))


def test_tag_counts():
    assert elog.tag_counts(elog.parse(GOOD + "\n\n" + LIVE)) == {"V": 1, "S": 2, "U": 0, "none": 0}


def test_the_repositorys_log_validates():
    """The committed log itself must pass `validate`. Without this test, CI never ran the checker, and on
    2026-11-03 a bad merge (b66179f) interleaved five entries' bodies and still went green
    (EVIDENCE_LOG E-2026-11-04-10)."""
    from pathlib import Path
    log = Path(__file__).resolve().parents[3] / "results" / "report" / "EVIDENCE_LOG.md"
    errs = elog.validate(elog.parse(log.read_text()))
    assert errs == [], "\n".join(errs[:20])
