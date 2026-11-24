"""Regenerate sample_snapshot.json: the exporter run on the synthetic state of dashboard/tests/synth.py.

    python3 -m dashboard.fixtures.make_fixture

Every number is invented (synthetic: true). The test suite checks the committed file is what this
produces, so the fixture cannot drift from the exporter.
"""
import datetime as dt
import json
import tempfile
from pathlib import Path

from dashboard import export as E
from dashboard.tests import synth

NOW = dt.datetime(2026, 11, 23, 23, 20, tzinfo=dt.timezone.utc)
FIXTURE = Path(__file__).resolve().parent / "sample_snapshot.json"


def make() -> dict:
    with tempfile.TemporaryDirectory() as d:
        st, sb = synth.make_state(Path(d))
        snap = E.export(st, sb, NOW)
    snap["synthetic"] = True
    return snap


if __name__ == "__main__":
    FIXTURE.write_text(json.dumps(make(), indent=1, sort_keys=True) + "\n")
    print(f"wrote {FIXTURE}")
