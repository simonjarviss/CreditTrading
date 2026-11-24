"""The corporate-action read cannot be broken by one field of one row: a property test.

WHY (release-check of 1c64638, 2026-11-02, reproduced). It was the fourth
single-row parsing hole in a row: "2026-02-30", "0000-00-00" and "2026-10-29\\n"
passed a `$`-anchored pattern and then raised in `fromisoformat`, so the read
failed as UNMEASURED without naming the row, and `ca-ack` (reading the same
way) could not clear it: under `halt` only a release could. The fix closes the
CLASS (alpaca.py, EVERY FIELD VALIDATED, NOTHING RAISES): every field the
reader knows the meaning of goes through a validator that returns a value or a
named fault. This test is what closes it.

THE PROPERTY. For every field of every row type the reader handles (each
type's reference row, `test_alpaca_client.CA_REFERENCE`, its dates moved to the
session date; each reorganization leg field; and the whole row), substitute
each ADVERSARIAL value, on a row naming the HELD fund CCC and on an OUTSIDE row.
Then, through `corp_actions.check` under `halt`:
  (a) the read never raises (the gate is never UNMEASURED for it);
  (b) a value the field's own rule REJECTS leaves the row either BLOCKING, the
      refusal naming a key `ca-ack` can take, or RECORDED (skipped as
      malformed, or listed as unresolved); a held-fund row always blocks;
  (c) every blocking key is addressable by `ca-ack`: one token, returned by
      ca-ack's own read, with one raw row;
  (d) the unmodified rows read exactly as well-formed rows do.
A value the field's rule ACCEPTS (a ticker such as "TBD" in a symbol field, any
token in `id`) makes a well-formed row about something else; only (a) is
asserted for it. The rules are written out here, independently of the code's.

On 1c64638 this FAILS: the count is in the commit message of the fix.

Synthetic rows test the code, never a claim about the market. Hermetic: the
real parser over a fake HTTP session, a temporary key file of test constants.
"""
import datetime as dt
import math
import re

import pytest

from quantt.broker import alpaca as al
from quantt.session import corp_actions as cam
from quantt.session.tests.test_corp_actions import CLOSED, HELD
from quantt.session.tests.test_run import ASOF, D
from quantt.tests.test_alpaca_client import (CA_REFERENCE, KEY_ID, SECRET, FakeResp,
                                             FakeSession, route)

DAY = D.isoformat()
UNI = ["AAA", "BBB", "CCC"]
TARGETS = ["AAA"]
ADVERSARIAL = [None, "", " ", "TBD", "2026-02-30", "0000-00-00", "2026-10-29\n",
               " 2026-10-29", "NaN", "inf", "-1", "0", "1e999", 0, -1.5, True, [], {},
               "X" * 10240]
SUBJECT_ROLES = {"subject", "old", "source", "acquiree"}


# --------------------------------------------- the field rules, written out here

def _is_ticker(v):
    return isinstance(v, str) and re.fullmatch(r"[A-Z][A-Z0-9.]{0,9}", v) is not None


def _is_date(v):
    if not (isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)):
        return False
    try:
        dt.date.fromisoformat(v)
        return True
    except ValueError:
        return False


def _is_number(v, zero_ok):
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        return False
    if isinstance(v, str) and not re.fullmatch(r"\d+(\.\d+)?([eE][+-]?\d+)?", v):
        return False
    x = float(v)
    return math.isfinite(x) and x >= 0 and (zero_ok or x > 0)


def _is_cusip(v):
    return isinstance(v, str) and v != "" and v == v.strip() and v.isprintable()


def accepted(kind, field, value, row):
    """Does the field's rule accept `value` (making a well-formed row)?"""
    fields = {f: (role, req) for f, role, req in al.CORPORATE_ACTION_TYPES[kind][2]}
    date_field = al.CORPORATE_ACTION_TYPES[kind][1]
    if field == "<row>":
        return False
    if field in fields:
        role, req = fields[field]
        return _is_ticker(value) or (not req and value in (None, ""))
    if field == "id":
        return isinstance(value, str) and value != "" and not any(c.isspace() for c in value)
    if field in (date_field, "process_date"):
        return _is_date(value)
    if field == "stock_movements":
        return value is None or isinstance(value, list)
    if field.startswith("stock_movements[0]."):
        leg = row["stock_movements"][0]
        k = field.split(".", 1)[1]
        if k == "symbol":
            return _is_ticker(value) or (value in (None, "") and _is_cusip(leg.get("cusip")))
        if k == "cusip":
            return value in (None, "") or _is_cusip(value)
        return value is None or _is_number(value, zero_ok=False)
    if field.endswith("_date"):
        return value is None or _is_date(value)
    if field == "rate" or field.endswith("_rate") or field == "price":
        return value is None or _is_number(value, zero_ok=(field == "cash_rate"))
    if field.endswith("cusip"):
        return value is None or _is_cusip(value)
    return True                       # a field the reader does not read


# ---------------------------------------------------------------- the harness

class _Feed:
    def __init__(self, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        kf = tmp_path / "k.env"           # test constants, never config/.env
        kf.write_text(f"ALPACA_CEF_KEY_ID={KEY_ID}\nALPACA_CEF_SECRET_KEY={SECRET}\n")
        self.ca = {}
        self.client = al.AlpacaClient("cef", kf, sleep=lambda s: None, session=FakeSession(
            route({"/v1/corporate-actions": lambda p: FakeResp(
                200, {"corporate_actions": self.ca, "next_page_token": None})})))


def _rows(kind, variant):
    key, date_field, fields = al.CORPORATE_ACTION_TYPES[kind]
    row = {k: v for k, v in CA_REFERENCE[key][0].items()}
    row["stock_movements"] = [dict(m) for m in row["stock_movements"]] \
        if "stock_movements" in row else None
    if row["stock_movements"] is None:
        del row["stock_movements"]
    for f in (date_field, "process_date"):
        row[f] = DAY
    if variant == "held":
        subject = next(f for f, role, _ in fields if role in SUBJECT_ROLES)
        row[subject] = "CCC"
    return key, row


def _mutations(row):
    for f in list(row):
        if f == "stock_movements":
            for k in list(row[f][0]):
                yield f"stock_movements[0].{k}"
        yield f
    yield "<row>"


def _mutate(row, field, value):
    if field == "<row>":
        return value
    r = {k: ([dict(m) for m in v] if k == "stock_movements" else v) for k, v in row.items()}
    if field.startswith("stock_movements[0]."):
        r["stock_movements"][0][field.split(".", 1)[1]] = value
    else:
        r[field] = value
    return r


def _outcome(feed, key, row):
    """(record or the exception, ca-ack's read: (events, rows) or the exception)."""
    feed.ca = {key: [row]}
    try:
        rec = cam.check(feed.client.corporate_actions, CLOSED, HELD, TARGETS, ASOF, D, cam.HALT,
                        universe=UNI)
    except Exception as e:  # the property's (a): recorded as a failing case
        return e, None
    rows = {}
    try:
        events = feed.client.corporate_actions(sorted(rec["names"]), *rec["query"],
                                               universe=UNI, skipped=[], rows=rows)
    except Exception as e:  # (c) fails: ca-ack's read raised
        return rec, e
    return rec, (events, rows)


def _violations(kind, variant, field, value, rec, ack_read, row):
    if isinstance(rec, Exception):
        return [f"(a) raised {type(rec).__name__}: {str(rec)[:100]}"]
    if accepted(kind, field, value, row):
        return []
    out = []
    if isinstance(ack_read, Exception):
        return [f"(c) ca-ack's read raised {type(ack_read).__name__}"]
    events, rows = ack_read
    ids = {e["id"] for e in events}
    keys = {b["id"] for b in rec["blocking"]}
    text = cam.refusal_text(rec) or ""
    if variant == "held" and rec["status"] != cam.BLOCKING:
        out.append(f"(b) held-fund row not blocking: {rec['status']}")
    if rec["status"] == cam.BLOCKING:
        if not any(k in text for k in keys):
            out.append("(b) blocking, but the refusal names no key")
        for k in keys:
            if not (isinstance(k, str) and k and not any(c.isspace() for c in k)):
                out.append(f"(c) key {k!r:.40} is not one token")
            elif k not in ids or not rows.get(k) or any(r != rows[k][0] for r in rows[k]):
                out.append(f"(c) key {k[:40]} not addressable by ca-ack's read")
    else:
        recorded = rec.get("skipped_malformed") or rec.get("unresolved")
        if not recorded:
            out.append("(b) neither blocking nor recorded: dropped in silence")
    return out


CASES = [(k, v) for k in al.CORPORATE_ACTION_TYPES for v in ("held", "outside")]


@pytest.mark.parametrize("kind,variant", CASES, ids=[f"{k}-{v}" for k, v in CASES])
def test_no_single_field_can_break_the_read(tmp_path, kind, variant):
    feed = _Feed(tmp_path)
    key, row = _rows(kind, variant)
    # (d) the unmodified row reads as a well-formed row
    rec, _ = _outcome(feed, key, row)
    assert not isinstance(rec, Exception), rec
    if variant == "held":
        assert rec["status"] == cam.BLOCKING and {b["id"] for b in rec["blocking"]} == {row["id"]}
        assert "unresolved" not in rec and "skipped_malformed" not in rec
    else:
        assert rec["status"] == cam.CLEAR and rec["events"] == [] \
            and "unresolved" not in rec and "skipped_malformed" not in rec
    failures = []
    for field in _mutations(row):
        for value in ADVERSARIAL:
            r = _mutate(row, field, value)
            rec, ack_read = _outcome(feed, key, r)
            for v in _violations(kind, variant, field, value, rec, ack_read, row):
                failures.append(f"{field}={value!r:.30}: {v}")
    assert not failures, f"{len(failures)} failing case(s):\n" + "\n".join(failures[:40])
