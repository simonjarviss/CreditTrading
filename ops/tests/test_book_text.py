"""Text a reader acts on names the specs as they are: the book jsons' descriptions and the C4 checklist.

WHY (release-check of 336df9d, 2026-11-03, QR3). Each activation commit of CEF trial
53 and its amendment changed a spec's `spec_id` and `sizing_multiplier` and left
the book jsons' `description` and the C4 dry-run checklist naming the old ones
(v8 x1.13 for the core, v3 x1.27 for C4). `ops.doc_audit` reads neither. The
checklist's expected `smult=1.2700` line would not have matched what the dry-run
plan shows (`smult=1.2600`) at C4's arming go. The runner reads no description,
so nothing errored; a person reading the page would have been told the wrong book.

WHAT IS CHECKED, against the specs read now (never a literal here):
  * every book json's `description` names the spec_id of the spec its one sleeve
    names, and, when that spec sets `sizing_multiplier`, says
    `sizing_multiplier <value>` with the spec's own value;
  * in results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md, every `smult=` is C4's
    multiplier to 4 dp (the sleeve's reason format, cef_discount.py `smult=`),
    every `×<m>` is C4's or the core's multiplier, and every full spec id of
    either book that is not a revert tag (`spec-...`) is the current one.
A spec change then fails here until its readers' text is updated in the same
commit (/spec-change).
"""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BOOKS = sorted((REPO / "ops" / "books").glob("*.json"))
CHECKLIST = REPO / "results" / "ops" / "C4_DRY_RUN_CHECKLIST_2026-10-29.md"


def _spec(rel: str) -> dict:
    return json.loads((REPO / rel).read_text())


def _book_spec(book: dict) -> dict:
    (sleeve,) = [s for s in book["sleeves"] if s.get("enabled", True)]
    return _spec(sleeve["spec_path"])


@pytest.mark.parametrize("path", BOOKS, ids=lambda p: p.name)
def test_every_book_description_names_its_spec_and_multiplier(path):
    book = json.loads(path.read_text())
    spec = _book_spec(book)
    d = book["description"]
    assert spec["spec_id"] in d, f"{path.name}: description does not name {spec['spec_id']}"
    for sid in re.findall(r"\b(?:cef_discount|c4_families)\.v\d+\.\d{8}\b", d):
        assert sid == spec["spec_id"], f"{path.name}: description names {sid}, not {spec['spec_id']}"
    m = spec["frozen"].get("sizing_multiplier")
    if m is not None:
        assert f"sizing_multiplier {m}" in d, \
            f"{path.name}: description does not say sizing_multiplier {m}"
        for got in re.findall(r"sizing_multiplier (\d+(?:\.\d+)?)", d):
            assert float(got) == float(m), f"{path.name}: says sizing_multiplier {got}, spec {m}"


def test_the_c4_checklist_names_the_current_specs_and_multipliers():
    text = CHECKLIST.read_text()
    c4 = _spec("ops/specs/c4_families.frozen.json")
    core = _spec("ops/specs/cef_discount.frozen.json")
    m4, mc = float(c4["frozen"]["sizing_multiplier"]), float(core["frozen"]["sizing_multiplier"])
    smults = re.findall(r"smult=(\d\.\d{4})", text)
    assert smults and all(s == f"{m4:.4f}" for s in smults), smults
    times = re.findall(r"×(\d\.\d+)", text)
    assert times and all(float(t) in (m4, mc) for t in times), times
    assert c4["spec_id"] in text and core["spec_id"] in text
    for sid in re.findall(r"(?<![-\w])(c4_families\.v\d+\.\d{8})", text):
        assert sid == c4["spec_id"], f"the checklist names {sid}; C4's spec is {c4['spec_id']}"
    for sid in re.findall(r"(?<![-\w])(cef_discount\.v\d+\.\d{8})", text):
        assert sid == core["spec_id"], f"the checklist names {sid}; the core's is {core['spec_id']}"


def test_the_opening_rule_cites_the_2026_11_03_ruling():
    """quant-reviewer 3 (release-check of 4f759a9): the own-prefix opening rule was cited
    to 2026-11-02, the date of the ACCOUNT ruling (no new account). The rule itself is the
    team lead's 2026-11-03 "just flat it", recorded in docs/SYSTEM.md section 5 on PR #30.
    Fails on 61589a8."""
    from quantt.session import run as rn
    note = json.loads((REPO / "ops/books/c4_families_book.json").read_text())[
        "execution"]["_opening_session_fills_note"]
    for where, text in (("run.is_opening_session", rn.is_opening_session.__doc__),
                        ("the book json's _opening_session_fills_note", note),
                        ("the checklist", CHECKLIST.read_text()),
                        ("docs/RUNNER.md", (REPO / "docs/RUNNER.md").read_text())):
        assert "2026-11-03" in text and "just flat it" in text, where
    assert "OPENING-SESSION RULE (team lead 2026-11-02" not in note
    assert "own_prefix\" EXISTS (C4; team lead 2026-11-02" not in rn.is_opening_session.__doc__
