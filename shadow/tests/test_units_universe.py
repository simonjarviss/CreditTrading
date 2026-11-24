"""The units universe: the name rule keeps partnership and trust units and drops the things
that only share the word, every book file loads, and the stored list is well formed."""
import csv
from pathlib import Path

from shadow import book as book_mod
from shadow.universes import build_units_v1 as b

ROOT = Path(__file__).resolve().parents[1]


def test_the_name_rule_keeps_units_and_drops_lookalikes():
    rows = [
        ("ET", "Energy Transfer LP Common Units"),
        ("EPD", "Enterprise Products Partners L.P. Common Stock"),
        ("PRT", "PermRock Royalty Trust Units of Beneficial Interest"),
        ("NRT", "North European Oil Royality Trust Common Stock"),          # the directory's spelling
        ("IEP", "Icahn Enterprises L.P. - Depositary Units representing Limited Partner Interests"),
        ("XXA", "Acme Acquisition Corp. Units, each consisting of one share and one warrant"),
        ("XXB", "Acme Corporation Corporate Units"),
        ("XXC", "Acme Inc. - Tangible Equity Units"),
        ("XXD", "Acme Partners L.P. 9.00% Class B Preferred Units"),
        ("XXE", "Banco Acme SA American Depositary Shares, each representing one unit"),
        ("XXF", "Acme Real Estate Investment Trust Units"),
        ("XXG", "Acme Municipal Fund Common Shares of Beneficial Interest"),
        ("AB$A", "Acme L.P. Common Units"),                                  # not a plain symbol
        ("A", "Agilent Technologies, Inc. Common Stock"),
    ]
    assert [s for s, _ in b.candidates(rows)] == ["EPD", "ET", "IEP", "NRT", "PRT"]


def test_the_stored_list_is_well_formed():
    rows = list(csv.DictReader(open(ROOT / "universes" / "units_v1.csv")))
    syms = [r["symbol"] for r in rows]
    assert len(syms) >= 20 and len(set(syms)) == len(syms)
    assert {r["source"] for r in rows} == {"nasdaqtrader_name_rule"}
    assert all(r["shortable"] in ("True", "False") and r["built"] for r in rows)


def test_every_book_file_loads():
    names = sorted(p.stem for p in (ROOT / "books").glob("*.json"))
    assert {"units_exdate_after", "units_exdate_before_after"} <= set(names)
    for n in names:
        book_mod.load(ROOT / "books" / f"{n}.json")
