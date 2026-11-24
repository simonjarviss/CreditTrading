"""DG-E1-3's reading pack and collector (scripts/events/e1_failed_reading.py), on synthetic filings.

Claims about the code only. What is pinned:
* a quote copied from the rendered excerpt is found by `quote_in` in the RAW filing (rendering
  changes whitespace only), including across a tag boundary and an HTML entity;
* the SGML header's parties and CIKs are read; an 8-K's press-release exhibit is excerpted;
* outcome windows prefer the strong failure language and are capped;
* batches respect the token cap and the episode cap, deterministically;
* the collector: a quote not in the filing, a cited filing not excerpted and a date that is not
  EDGAR's are problems; in_trial is Y only for a listed pair that failed; the target's and the
  acquirer's readings of one deal share a deal_id; a pair announced twice, years apart, is two deals.
"""
import json

import pandas as pd
import pytest

from scripts.events import e1_failed_reading as fr
from scripts.events import e1_merger_pair as e1
from scripts.events.conditional_tender_census import quote_in

RAW = """<SEC-HEADER>
CONFORMED SUBMISSION TYPE:\t8-K
SUBJECT COMPANY:\t
\tCOMPANY DATA:\t
\t\tCOMPANY CONFORMED NAME:\t\t\tALPHA MUNICIPAL FUND INC
\t\tCENTRAL INDEX KEY:\t\t\t0000000020
FILED BY:\t\t
\tCOMPANY DATA:\t
\t\tCOMPANY CONFORMED NAME:\t\t\tBETA MUNICIPAL FUND
\t\tCENTRAL INDEX KEY:\t\t\t0000000030
</SEC-HEADER>
<DOCUMENT>
<TYPE>8-K
<TEXT>
<html><body><p>Item 8.01 Other Events.</p><p>Alpha&#8217;s Board <b>has terminated</b> the
Agreement and Plan of Reorganization with Beta Municipal Fund (NYSE: BMF).</p></body></html>
</TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>EX-99.1
<TEXT>
<p>PRESS RELEASE: Alpha Municipal Fund (NYSE: AMF) and Beta Municipal Fund announce that the
proposed reorganization will not proceed.</p>
</TEXT>
</DOCUMENT>
"""


def test_render_changes_whitespace_only():
    r = fr.render(RAW.split("<TEXT>")[1].split("</TEXT>")[0])
    assert "Alpha’s Board has terminated the" in r.replace("\n", " ")
    for q in ("Alpha’s Board has terminated the Agreement and Plan of Reorganization",
              "Alpha's Board has terminated", "Beta Municipal Fund (NYSE: BMF)."):
        assert quote_in(RAW, q)
    from scripts.events.conditional_tender_census import normalise
    body = RAW.split("<TEXT>")[1].split("</TEXT>")[0]
    assert normalise(fr.render(body)) == normalise(body)


def test_header_parties_and_exhibit_excerpt():
    assert fr.sgml_parties(RAW) == [{"role": "SUBJECT COMPANY", "name": "ALPHA MUNICIPAL FUND INC", "cik": 20},
                                    {"role": "FILED BY", "name": "BETA MUNICIPAL FUND", "cik": 30}]
    txt, _ = fr.excerpt_filing(RAW, "8-K")
    assert "exhibit EX-99.1" in txt and "will not proceed" in txt


def test_windows_prefer_failure_language_and_are_capped(monkeypatch):
    filler = "word " * 400
    t = (filler + " the meeting was adjourned " + filler + " the merger was terminated by the boards "
         + filler + " were not approved " + filler + " adjourn again " + filler + " has been withdrawn ")
    w = fr.windows(t, 0)
    assert len(w) == fr.MAX_WINDOWS
    labs = [lab for _, _, lab in w]
    assert labs.count("outcome") == 3          # the three strong matches win over 'adjourn'


def test_batches_respect_caps():
    sizes = {f"e{i}": 30_000 for i in range(25)}
    b = fr.plan_batches(sizes, list(sizes))
    assert all(len(x) <= fr.BATCH_MAX_EPISODES for x in b)
    assert all(sum(sizes[i] for i in x) / fr.CHARS_PER_TOKEN <= fr.BATCH_TOKENS for x in b)
    assert sorted(i for x in b for i in x) == sorted(sizes) and b == fr.plan_batches(sizes, list(sizes))


LISTED = [{"seq": 1, "date": "2015-01-05", "form": "425", "accession": "0000000020-15-000001", "included": True},
          {"seq": 2, "date": "2015-06-01", "form": "8-K", "accession": "0000000020-15-000009", "included": True},
          {"seq": 3, "date": "2015-07-01", "form": "DEF 14A", "accession": "0000000020-15-000010", "included": False}]
DOCS = {"0000000020-15-000001": "Alpha Municipal Fund (NYSE: AMF) will reorganize into Beta Municipal Fund (NYSE: BMF).",
        "0000000020-15-000009": RAW}


def _reading(outcome="terminated", both=True, ann_date="2015-01-05"):
    return {"episode_cik": 20, "episode_accession": "0000000020-15-000001", "episode_role": "target",
            "deals": [{"target": {"name": "Alpha", "cik": 20, "ticker": "AMF"},
                       "acquirer": {"name": "Beta", "cik": 30, "ticker": "BMF"}, "both_listed": both,
                       "listed_quote": {"accession": "0000000020-15-000001", "quote": "(NYSE: BMF)"},
                       "outcome": outcome,
                       "announcement": {"accession": "0000000020-15-000001", "date": ann_date,
                                        "quote": "will reorganize into Beta Municipal Fund"},
                       "outcome_evidence": {"accession": "0000000020-15-000009", "date": "2015-06-01",
                                            "quote": "has terminated the Agreement and Plan of Reorganization"},
                       "notes": ""}], "problems": ""}


def test_validate_finds_quote_citation_and_date_problems():
    eid = "20_0000000020-15-000001"
    get = DOCS.__getitem__
    assert fr.validate(_reading(), eid, LISTED, get) == []
    bad = _reading()
    bad["deals"][0]["outcome_evidence"]["quote"] = "the merger was completed"
    assert any("quote not found" in p for p in fr.validate(bad, eid, LISTED, get))
    bad = _reading()
    bad["deals"][0]["outcome_evidence"]["accession"] = "0000000020-15-000010"   # listed but not excerpted
    assert any("not an excerpted filing" in p for p in fr.validate(bad, eid, LISTED, get))
    assert any("differs from EDGAR" in p for p in fr.validate(_reading(ann_date="2015-01-06"), eid, LISTED, get))
    assert any("not stated" in p for p in fr.validate(_reading(outcome=None), eid, LISTED, get))


def test_rows_in_trial_and_deal_ids():
    eid = "20_0000000020-15-000001"
    r1 = fr.to_rows(_reading(), eid, LISTED, "m", "2026-10-20")[0]
    assert r1["in_trial"] == "Y" and r1["fail_date"] == "2015-06-01" and r1["counterparty_cik"] == 30
    assert fr.to_rows(_reading(both=False, outcome="not_a_listed_pair"), eid, LISTED, "m", "d")[0]["in_trial"] == "N"
    assert fr.to_rows(_reading(outcome="completed"), eid, LISTED, "m", "d")[0]["fail_quote"] == ""
    # the acquirer's episode reads the same deal; a second proposal of the pair three years later
    r2 = {**r1, "episode_cik": "30", "episode_accession": "0000000030-15-000002"}
    r3 = {**r1, "episode_accession": "0000000020-18-000001", "ann_date": "2018-03-01"}
    r4 = {**r1, "target_cik": "", "_k": 0}
    R = pd.DataFrame([r1, r2, r3, r4])
    ids = fr.assign_deal_ids(R)
    assert ids[0] == ids[1] == "20>30" and ids[2] == "20>30#2" and ids[3].startswith("ep20:")


def test_collect_writes_the_file_stage0_reads(tmp_path, monkeypatch):
    root = tmp_path / "pack"
    (root / "input").mkdir(parents=True)
    (root / "out" / "sonnet").mkdir(parents=True)
    eid = "20_0000000020-15-000001"
    (root / "input" / "plan.json").write_text(json.dumps(
        {"batches": [{"batch": "01", "episodes": [{"id": eid}]}], "filings": {eid: LISTED}}))
    (root / "out" / "sonnet" / f"{eid}.json").write_text(json.dumps(_reading()))
    (root / "out" / "sonnet" / "_batch_01.json").write_text(json.dumps({"batch": "01", "model_id": "claude-sonnet-x"}))
    monkeypatch.setattr(e1, "OUT_DIR", tmp_path / "e1")
    monkeypatch.setattr(e1, "READINGS", tmp_path / "e1" / "r.csv")

    class C:
        def get_text(self, url):
            acc = url.rsplit("/", 1)[1][:-4]
            return DOCS[acc]
    out = fr.collect(root, "sonnet", partial=False, client=C())
    R = pd.read_csv(tmp_path / "e1" / "r.csv", dtype=str, keep_default_na=False)
    assert list(R.columns) == list(e1.READING_COLUMNS) and out["in_trial_deals"] == 1
    assert R.loc[0, "read_by"] == "claude-sonnet-x (batch 01)" and R.loc[0, "deal_id"] == "20>30"
    cen = pd.DataFrame({"episode_cik": [20], "episode_accession": ["0000000020-15-000001"]})
    _, probs = e1.check_readings(cen, C())
    assert probs == []                          # what the collector writes passes Stage 0's own check
    (root / "out" / "sonnet" / f"{eid}.json").unlink()
    with pytest.raises(e1.GateError, match="no reading"):
        fr.collect(root, "sonnet", partial=False, client=C())


def test_episode_text_shows_every_filing_and_points_duplicates(monkeypatch):
    rows = [("0000000020-15-000001", "425", "2015-01-05"), ("0000000020-15-000002", "425", "2015-01-06"),
            ("0000000020-15-000009", "8-K", "2015-06-01")]
    fl = pd.DataFrame({"accessionNumber": [r[0] for r in rows], "form": [r[1] for r in rows],
                       "filingDate": pd.to_datetime([r[2] for r in rows])})
    monkeypatch.setattr(fr, "episode_filings", lambda client, cik, first, *forms: fl)
    press = RAW.replace("8-K", "425").split("<DOCUMENT>")[0] + "<DOCUMENT>\n<TYPE>425\n<TEXT>\n<p>Alpha will reorganize into Beta.</p>\n</TEXT>\n</DOCUMENT>\n"
    docs = {"0000000020-15-000001": press, "0000000020-15-000002": press, "0000000020-15-000009": RAW}

    class C:
        def get_text(self, url):
            return docs[url.rsplit("/", 1)[1][:-4]]
    ep = pd.Series({"episode_cik": 20, "episode_accession": "0000000020-15-000001", "first_date": "2015-01-05",
                    "first_form": "425", "company_last": "ALPHA MUNICIPAL FUND INC"})
    txt, listed = fr.episode_text(C(), ep)
    by = {x["accession"]: x for x in listed}
    assert by["0000000020-15-000002"]["why"] == "identical text to seq=1"
    assert by["0000000020-15-000001"]["mode"] == "full" and by["0000000020-15-000009"]["included"]
    assert "has terminated" in txt and txt.count("Alpha will reorganize into Beta.") == 1


def test_assign_deal_ids_keeps_two_series_of_one_trust_apart():
    base = {"episode_cik": "35315", "episode_accession": "a", "target_cik": "35315", "acquirer_cik": "1562565",
            "ann_date": "2024-10-03"}
    R = pd.DataFrame([{**base, "_k": 0}, {**base, "_k": 1}])
    ids = fr.assign_deal_ids(R)
    assert list(ids) == ["35315>1562565", "35315>1562565/2"]


def _nm_dl():
    nm = pd.DataFrame({"permno": [1, 2, 3, 4], "ticker": ["AMF", "BMF", "OEF", "TGM"],
                       "namedt": pd.to_datetime(["2000-01-01"] * 4), "nameendt": pd.to_datetime(["2024-12-31"] * 4),
                       "shrcd": [14, 14, 73, 14], "exchcd": [1, 1, 3, 1], "comnam": ["A", "B", "C", "D"]})
    dl = pd.DataFrame({"permno": [4], "dlstdt": pd.to_datetime(["2016-03-01"]), "dlstcd": [231], "nwperm": [2]})
    return nm, dl


def test_triage_classes():
    nm, dl = _nm_dl()
    cen = pd.DataFrame({"episode_cik": ["20", "21", "22", "23", "24", "25"], "episode_accession": ["a"] * 6,
                        "first_date": ["2015-01-05"] * 6})
    row = {c: "" for c in e1.READING_COLUMNS}
    rows = [
        {**row, "episode_cik": "20", "episode_accession": "a", "target_ticker": "AMF", "acquirer_ticker": "BMF",
         "outcome": "withdrawn", "ann_date": "2015-01-05", "outcome_date": "2015-06-01"},          # T1 via CRSP listing
        {**row, "episode_cik": "21", "episode_accession": "a", "target_ticker": "AMF", "acquirer_ticker": "BMF",
         "outcome": "superseded", "both_listed": "Y", "ann_date": "2023-09-08", "fail_date": "2025-06-09"},  # T2
        {**row, "episode_cik": "22", "episode_accession": "a", "target_ticker": "AMF", "acquirer_ticker": "OEF",
         "outcome": "", "ann_date": "2015-01-05"},                                                   # C3: listing unsettled, own fund unlisted
        {**row, "episode_cik": "23", "episode_accession": "a", "target_ticker": "TGM", "acquirer_ticker": "BMF",
         "outcome": "", "ann_date": "2015-06-01"},                                                   # C1: CRSP merger within 730 days
        {**row, "episode_cik": "24", "episode_accession": "a", "outcome": ""},                       # I3 or C3 by own listing
        {**row, "episode_cik": "25", "episode_accession": "a", "outcome": ""},
    ]
    T = fr.triage(pd.DataFrame(rows), cen, nm, dl, {"24_a": True, "25_a": False})
    # OEF is an ETF (share code 73): no CEF permno, so that pair's listing is unsettled, not "N"
    assert list(T["triage"]) == ["T1", "T2", "C3", "C1", "I3", "C3"]
    assert T.loc[0, "crsp_listed_pair"] == "Y" and T.loc[3, "crsp_target_merged_730d"] == "Y"
    assert list(T["can_change_trial"])[:2] == ["Y", "Y"] and T.loc[5, "can_change_trial"] == "N"


def test_failed_deal_rows_take_one_deal_read_from_four_episodes(monkeypatch):
    nm, _ = _nm_dl()
    monkeypatch.setattr(e1.ce, "universe_permnos", lambda nm: {"XXX": [99]})
    monkeypatch.setattr(e1, "spec_names", lambda: set())
    row = {c: "" for c in e1.READING_COLUMNS}
    base = {**row, "deal_id": "902722>1137391", "in_trial": "Y", "outcome": "vote_failed", "target_ticker": "AMF",
            "acquirer_ticker": "BMF", "ann_date": "2009-10-26"}
    R = pd.DataFrame([{**base, "episode_cik": c, "fail_date": f} for c, f in
                      (("902722", "2009-12-28"), ("1169027", "2009-12-29"), ("1176196", "2009-12-28"), ("1181027", "2009-12-29"))])
    D = e1.failed_deal_rows(R, nm)
    assert len(D) == 1 and D.loc[0, "fail_date"] == pd.Timestamp("2009-12-28") and D.loc[0, "ann"] == pd.Timestamp("2009-10-26")


# ---------------------------------------------------------------- amendment 3 (2026-10-20)

def _row(**k):
    r = {c: "" for c in e1.READING_COLUMNS}
    r.update(k)
    return r


def test_rulings_2_to_4():
    nm = pd.DataFrame({"permno": [1, 2, 5, 6], "ticker": ["NXJ", "NAD", "BHV", "MYI"],
                       "namedt": pd.to_datetime(["2000-01-01"] * 4), "nameendt": pd.to_datetime(["2024-12-31"] * 4),
                       "shrcd": [14, 14, 44, 14], "exchcd": [1, 1, 1, 1], "comnam": ["A", "B", "C", "D"]})
    cmap = {1: 1001, 2: 1083839, 5: 1169034, 6: 883412}
    R = pd.DataFrame([
        _row(episode_cik="1083839", episode_accession="a", deal_id="ep1083839:0", target_ticker="NXJ",
             acquirer_ticker="NAD", outcome="withdrawn", ann_date="2023-08-31", fail_date="2023-11-09",
             fail_quote="q", fail_accession="x"),                                            # ruling 2
        _row(episode_cik="883412", episode_accession="b", deal_id="1169034>883412", target_cik="1169034",
             acquirer_cik="883412", outcome="withdrawn", ann_date="2023-09-08", outcome_accession=fr.MYI_RW[0],
             outcome_quote="no longer contemplated", outcome_date="2023-11-01"),             # ruling 3, the RW row
        _row(episode_cik="1169034", episode_accession="c", deal_id="1169034>883412", target_cik="1169034",
             acquirer_cik="883412", target_ticker="BHV", acquirer_ticker="MYI", outcome="superseded",
             both_listed="Y", in_trial="Y", ann_date="2023-09-08", fail_date="2025-06-09",
             outcome_accession="y", outcome_quote="2025 filing", outcome_date="2025-06-09"),  # ruling 3, BHV's row
        _row(episode_cik="1490349", episode_accession="d", deal_id=fr.MCC_DEAL, outcome="terminated",
             outcome_quote="not found", outcome_accession="z"),                              # ruling 4
    ])
    X = fr.apply_dg3_rulings(R, nm, cmap)
    assert list(X["ruled"]) == ["2", "3", "3", "4"]
    assert X.loc[0, "in_trial"] == "Y" and X.loc[0, "deal_id"] == "1001>1083839"
    assert X.loc[1, "in_trial"] == "Y" and X.loc[1, "fail_date"] == "2023-11-01" and X.loc[1, "target_ticker"] == "BHV"
    assert X.loc[2, "outcome"] == "withdrawn" and X.loc[2, "in_trial"] == "N" and X.loc[2, "fail_date"] == ""
    assert X.loc[3, "outcome"] == "not_a_listed_pair" and X.loc[3, "outcome_quote"] == ""
    # the dedupe (ruling 1) then sees one MYI deal with F = 2023-11-01, not BHV's 2025 date
    assert set(X.loc[X["in_trial"] == "Y", "deal_id"]) == {"1001>1083839", "1169034>883412"}


def test_ruling_5_exempts_rows_that_cannot_change_the_trial(tmp_path, monkeypatch):
    T = pd.DataFrame({"triage": ["C2", "I2", "T1", "I3"], "ann_date": ["2015-01-01", "2016-01-01", "2016-01-01", "2025-07-15"]})
    assert list(fr.exempt_rows(T)) == [True, False, False, True]
    cen = pd.DataFrame({"episode_cik": [20, 21], "episode_accession": ["a", "b"]})
    R = pd.DataFrame([_row(episode_cik="20", episode_accession="a", deal_id="d1", outcome=""),
                      _row(episode_cik="21", episode_accession="b", deal_id="d2", outcome="")])
    _, probs = e1.check_readings(cen, None, readings=R, exempt=pd.Series([True, False]))
    assert len(probs) == 1 and "1 row(s)" in probs[0]                    # only the non-exempt blank blocks
    _, probs = e1.check_readings(cen, None, readings=R, exempt=pd.Series([True, True]))
    assert probs == []


def test_supp_census_catches_an_acquirer_explained_by_another_targets_completion():
    ep = pd.DataFrame({"cik": [886043, 99], "first_date": pd.to_datetime(["2023-03-17", "2015-01-05"]),
                       "last_date": pd.to_datetime(["2023-05-22", "2015-06-01"]), "first_form": ["N-14 8C", "425"],
                       "first_accession": ["m-1", "z-9"], "n_filings": [3, 1], "forms": ["N-14 8C", "425"],
                       "company_last": ["WESTERN ASSET MANAGED MUNICIPALS FUND INC.", "OTHER"]})
    comp = pd.DataFrame({"cik": [886043.0, 99.0], "C": pd.to_datetime(["2023-09-01", "2015-09-01"]),
                         "role": ["acquirer", "target"]})
    s = e1.supp_census(ep, comp)
    assert list(s["episode_cik"]) == [886043]                         # the target-side completion does not qualify


def test_freeze_rounds_and_the_exact_parse_check(tmp_path, monkeypatch):
    monkeypatch.setattr(e1, "OUT_DIR", tmp_path)
    root = tmp_path / "r1"
    (root / "input").mkdir(parents=True)
    (root / "input" / "plan.json").write_text(json.dumps({"batches": [
        {"batch": "40", "episodes": [{"id": "1_a"}]}, {"batch": "41", "episodes": [{"id": "2_b"}]},
        {"batch": "45", "episodes": [{"id": "3_c"}]}]}))
    T = pd.DataFrame({"episode_cik": ["7", "8", "9"], "episode_accession": ["x", "y", "z"],
                      "triage": ["I2", "I1", "C2"], "ann_date": ["2016-01-01"] * 3, "ruled": ["", "3", ""]})
    out = fr.freeze_rounds(root, T, T)
    assert out == {"r2_episodes": 1, "r2_rows": 1, "n8f_episodes": 2}
    assert list(pd.read_csv(tmp_path / "e1_reading_round_n8f.csv")["episode"]) == ["1_a", "3_c"]
    # the readers' parse check names one file by its full path, never a wildcard
    assert '<ROOT>/out/<MODEL>/<episode id>.json' in fr.INSTRUCTIONS and "wildcard" in fr.INSTRUCTIONS
    assert '{ROOT}/out/{MODEL}/<episode id>.json' in fr.BRIEF and "*" not in fr.BRIEF.split("Forbidden")[0]


# ---------------------------------------------------------------- the merge of rounds (rulings 6, 8) and the CRSP rule

def test_merge_rounds_rules():
    b = {c: "" for c in e1.READING_COLUMNS}
    R1 = pd.DataFrame([
        {**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "10>20", "outcome": ""},                # r2 fills
        {**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "11>20", "outcome": "completed"},       # r2 blank
        {**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "ep1:2", "outcome": "withdrawn"},       # listing settles
        {**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "12>20", "outcome": "completed"},       # disagreement
        {**b, "episode_cik": "2", "episode_accession": "b", "deal_id": "ep2:0", "outcome": "completed"},       # replaced by n8f
        {**b, "episode_cik": "3", "episode_accession": "c", "deal_id": "13>30", "outcome": "not_a_listed_pair"}])
    R2 = pd.DataFrame([
        {**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "10>20", "outcome": "vote_failed"},
        {**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "11>20", "outcome": ""},
        {**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "ep1:2", "outcome": "not_a_listed_pair", "both_listed": "N"},
        {**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "12>20", "outcome": "terminated"}])
    N8 = pd.DataFrame([{**b, "episode_cik": "2", "episode_accession": "b", "deal_id": "ep2:0", "outcome": ""}])
    M = fr.merge_rounds(R1, R2, N8).set_index("deal_id")
    assert M.at["10>20", "outcome"] == "vote_failed" and M.at["11>20", "outcome"] == "completed"
    assert M.at["ep1:2", "merge_note"] == "listing evidence settles" and M.at["ep1:2", "outcome"] == "not_a_listed_pair"
    assert M.at["12>20", "outcome"] == "" and M.at["12>20", "merge_note"].startswith("adjudicate")
    assert M.at["ep2:0", "round"] == "n8f" and M.at["ep2:0", "outcome"] == ""
    assert M.at["13>30", "round"] == "r1" and len(M) == 6


def test_crsp_outcome_rule():
    nm = pd.DataFrame({"permno": [1, 2, 3, 4, 5], "ticker": ["BHY", "HYT", "RAA", "BKT", "ALD"],
                       "namedt": pd.to_datetime(["2000-01-01"] * 5), "nameendt": pd.to_datetime(["2024-12-31"] * 5),
                       "shrcd": [44, 14, 14, 14, 11], "exchcd": [1] * 5, "comnam": list("ABCDE")})
    dl = pd.DataFrame({"permno": [1, 3, 4], "dlstdt": pd.to_datetime(["2013-11-15", "2010-09-10", "2024-12-31"]),
                       "dlstcd": [331, 450, 100], "nwperm": [2, 0, 0]})
    assert fr.crsp_outcome(nm, dl, "BHY", "HYT", "2013-06-27") == ("completed", pd.Timestamp("2013-11-15").date())
    assert fr.crsp_outcome(nm, dl, "RAA", "HYT", "2009-10-26")[0] == "not_completed_liquidated"
    assert fr.crsp_outcome(nm, dl, "BKT", "HYT", "2014-06-09") == ("not_completed", None)
    assert fr.crsp_outcome(nm, dl, "ALD", "HYT", "2009-10-26") is None        # a BDC: no delisting record cached
    assert fr.crsp_outcome(nm, dl, "BKT", "HYT", "2023-06-01") is None        # window past CRSP's end


def test_a_blank_row_of_a_settled_deal_does_not_block():
    cen = pd.DataFrame({"episode_cik": [1, 2], "episode_accession": ["a", "b"]})
    b = {c: "" for c in e1.READING_COLUMNS}
    R = pd.DataFrame([{**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "10>20", "outcome": "completed"},
                      {**b, "episode_cik": "2", "episode_accession": "b", "deal_id": "10>20", "outcome": ""}])
    _, probs = e1.check_readings(cen, None, readings=R)
    assert probs == []


def test_a_failure_with_unsettled_listing_blocks():
    cen = pd.DataFrame({"episode_cik": [1], "episode_accession": ["a"]})
    b = {c: "" for c in e1.READING_COLUMNS}
    R = pd.DataFrame([{**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "ep1:0", "outcome": "withdrawn"}])
    _, probs = e1.check_readings(cen, None, readings=R)
    assert any("listing is unsettled" in p for p in probs)


# ---------------------------------------------------------------- amendment 4 and ruling 10 (2026-10-21)

def test_third_reading_adjudicates_and_a_blank_leaves_it():
    b = {c: "" for c in e1.READING_COLUMNS}
    R = pd.DataFrame([{**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "10>20", "outcome": ""},
                      {**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "11>20", "outcome": "completed"}])
    R3 = pd.DataFrame([{**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "10>20", "outcome": "vote_failed"},
                       {**b, "episode_cik": "1", "episode_accession": "a", "deal_id": "11>20", "outcome": ""}])
    M = fr.merge_rounds(R, R3=R3).set_index("deal_id")
    assert M.at["10>20", "outcome"] == "vote_failed" and M.at["10>20", "round"] == "r3"
    assert M.at["11>20", "outcome"] == "completed"


def test_ruling_10_settles_blank_outcomes_from_crsp():
    nm = pd.DataFrame({"permno": [1, 2, 4], "ticker": ["BHY", "HYT", "BKT"],
                       "namedt": pd.to_datetime(["2000-01-01"] * 3), "nameendt": pd.to_datetime(["2024-12-31"] * 3),
                       "shrcd": [44, 14, 14], "exchcd": [1] * 3, "comnam": list("ABC")})
    dl = pd.DataFrame({"permno": [1, 4], "dlstdt": pd.to_datetime(["2013-11-15", "2024-12-31"]),
                       "dlstcd": [331, 100], "nwperm": [2, 0]})
    b = {c: "" for c in e1.READING_COLUMNS}
    R = pd.DataFrame([{**b, "deal_id": "ep1:0", "target_ticker": "BHY", "acquirer_ticker": "HYT", "ann_date": "2013-06-27"},
                      {**b, "deal_id": "ep2:0", "target_ticker": "BKT", "acquirer_ticker": "HYT", "ann_date": "2014-06-09"},
                      {**b, "deal_id": "ep3:0", "target_ticker": "", "acquirer_ticker": "HYT", "ann_date": "2014-06-09"}])
    X = fr.apply_dg3_rulings(R, nm, {}, dl)
    assert X.loc[0, "outcome"] == "completed" and X.loc[0, "outcome_date"] == "2013-11-15" and X.loc[0, "ruled"] == "10"
    assert X.loc[1, "outcome"] == "" and X.loc[1, "crsp_note"] == "not_completed"
    assert X.loc[2, "outcome"] == "" and X.loc[2, "crsp_note"] == ""
    assert (fr.apply_dg3_rulings(R, nm, {})["outcome"] == "").all()          # without dl, ruling 10 is off


def test_r3_list_names_the_open_question():
    T = pd.DataFrame({"episode_cik": ["1", "2", "3", "4"], "episode_accession": ["a"] * 4,
                      "deal_id": ["ep1:0", "ep2:0", "ep3:0", "9>8"], "target_ticker": ["NDP", "JLS", "", "X"],
                      "acquirer_ticker": ["TTP", "", "", "Y"], "outcome": ["", "superseded", "", "completed"],
                      "both_listed": ["Y", "", "", "Y"], "crsp_note": ["not_completed", "", "", ""]})
    F = fr.r3_list(T, pd.Series([False, False, False, False]))
    assert list(F["episode"]) == ["1_a", "2_a", "3_a"]
    assert "never completed" in F.loc[0, "focus"] and "exchange-listed" in F.loc[1, "focus"] and "how did it end" in F.loc[2, "focus"]


def test_matching_prefers_the_ticker_pair_over_position():
    b = {c: "" for c in e1.READING_COLUMNS}
    old = pd.DataFrame([{**b, "episode_cik": "886043", "episode_accession": "a", "deal_id": "ep886043:0",
                         "target_ticker": "MNP", "acquirer_ticker": "MMU", "outcome": "completed"},
                        {**b, "episode_cik": "886043", "episode_accession": "a", "deal_id": "ep886043:1",
                         "target_ticker": "SBI", "acquirer_ticker": "MMU", "outcome": ""}])
    r3 = pd.DataFrame([{**b, "episode_cik": "886043", "episode_accession": "a", "deal_id": "ep886043:0",
                        "target_ticker": "SBI", "acquirer_ticker": "MMU", "outcome": "vote_failed"}])
    M = fr.merge_rounds(old, R3=r3)
    assert len(M) == 2 and not M.duplicated(["episode_cik", "episode_accession", "deal_id"]).any()
    by = M.set_index("target_ticker")
    assert by.at["SBI", "outcome"] == "vote_failed" and by.at["MNP", "outcome"] == "completed"
    assert by.at["SBI", "deal_id"] == "ep886043:1"


def test_r4_rows_settle_the_counterpartys_episode_and_quote_their_own_filings():
    b = {c: "" for c in e1.READING_COLUMNS}
    r4 = pd.DataFrame([{**b, "episode_cik": "882300", "episode_accession": "s-1", "deal_id": "ep882300:0",
                        "target_ticker": "SBI", "acquirer_ticker": "MMU", "outcome": "vote_failed"}])
    L = pd.DataFrame({"episode_cik": ["882300"], "episode_accession": ["s-1"], "for_episode": ["886043_m-1"]})
    X = fr.rekey_r4(r4, L)
    assert (X.loc[0, "episode_cik"], X.loc[0, "episode_accession"], X.loc[0, "doc_cik"]) == ("886043", "m-1", "882300")
    old = pd.DataFrame([{**b, "episode_cik": "886043", "episode_accession": "m-1", "deal_id": "ep886043:1",
                         "target_ticker": "SBI", "acquirer_ticker": "MMU", "outcome": ""}])
    M = fr.merge_rounds(old, R3=X)
    assert len(M) == 1 and M.loc[0, "outcome"] == "vote_failed" and M.loc[0, "doc_cik"] == "882300"


# ---------------------------------------------------------------- rulings 12-15 (2026-10-21)

def _nm_dl_12():
    nm = pd.DataFrame({"permno": [1, 2, 3, 4, 5, 6, 7], "ticker": ["ALD", "PSEC", "BKT", "BHK", "SBI", "NCU", "NKX"],
                       "namedt": pd.to_datetime(["2000-01-01"] * 7), "nameendt": pd.to_datetime(["2024-12-31"] * 7),
                       "shrcd": [11, 14, 14, 14, 14, 14, 14], "exchcd": [1, 3, 1, 1, 1, 1, 1],
                       "comnam": ["ALLIED CAPITAL CORP", "PROSPECT CAPITAL CORP", "B", "C", "D", "E", "F"]})
    dl = pd.DataFrame({"permno": [3, 5, 6], "dlstdt": pd.to_datetime(["2024-12-31", "2024-12-31", "2014-06-06"]),
                       "dlstcd": [100, 100, 231], "nwperm": [0, 0, 7]})
    return nm, dl


def test_ruling_12_listing_by_crsp_through_the_cik():
    nm, dl = _nm_dl_12()
    b = {c: "" for c in e1.READING_COLUMNS}
    R = pd.DataFrame([
        {**b, "episode_cik": "1287032", "episode_accession": "p", "deal_id": "3906>1287032", "target_cik": "3906",
         "acquirer_ticker": "PSEC", "outcome": "terminated", "ann_date": "2010-01-20", "fail_date": "2010-03-05"},
        {**b, "episode_cik": "1472215", "episode_accession": "j", "deal_id": "ep1472215:0", "target_ticker": "PSEC",
         "outcome": "superseded", "ann_date": "2019-03-05", "fail_date": "2019-05-23"},
        {**b, "episode_cik": "9", "episode_accession": "k", "deal_id": "ep9:0", "target_ticker": "BKT",
         "acquirer_ticker": "BHK", "outcome": "superseded", "ann_date": "2014-06-09"}])
    X = fr.apply_dg3_rulings(R, nm, {1: 3906, 2: 1287032}, dl)
    assert X.loc[0, "target_ticker"] == "ALD" and X.loc[0, "in_trial"] == "Y" and X.loc[0, "both_listed"] == "Y"
    assert X.loc[1, "excluded"] == "12" and X.loc[1, "in_trial"] == "N"          # counterparty unidentified
    assert X.loc[2, "excluded"] == "13" and X.loc[2, "in_trial"] == "N"          # listed, failure undated


def test_rulings_13_14_15():
    nm, dl = _nm_dl_12()
    b = {c: "" for c in e1.READING_COLUMNS}
    rows = [{**b, "episode_cik": "832327", "episode_accession": "x", "deal_id": "ep832327:0", "target_ticker": "BKT",
             "acquirer_ticker": "BHK", "ann_date": "2014-06-09"},                                     # 13
            {**b, "episode_cik": "886043", "episode_accession": "0001193125-23-074093", "deal_id": "ep886043:1",
             "target_ticker": "SBI", "acquirer_ticker": "MMU", "ann_date": "2023-03-17"},             # 15: excluded once r4 read
            {**b, "episode_cik": "1195738", "episode_accession": "0001193125-11-345556", "deal_id": "ep1195738:3",
             "target_ticker": "NCU", "acquirer_ticker": "NKX"},                                       # 15: superseded
            {**b, "episode_cik": "77", "episode_accession": "y", "deal_id": "ep77:0"}]                # 14
    first = {"1195738_0001193125-11-345556": "2011-12-19"}
    X = fr.apply_dg3_rulings(pd.DataFrame(rows), nm, {}, dl, first=first, r4_read=False)
    assert X.loc[0, "excluded"] == "13" and X.loc[1, "excluded"] == "" and X.loc[2, "outcome"] == ""
    X = fr.apply_ruling_14(X, pd.Series([False] * 4))
    assert list(X["excluded"]) == ["13", "", "", "14"]                            # r4 not read: 15's deals wait
    Y = fr.apply_dg3_rulings(pd.DataFrame(rows), nm, {}, dl, first=first, r4_read=True)
    assert Y.loc[1, "excluded"] == "15"
    assert (Y.loc[2, "outcome"], Y.loc[2, "fail_date"], Y.loc[2, "in_trial"], Y.loc[2, "ann_date"]) == (
        "superseded", "2013-11-22", "Y", "2011-12-19")


def test_r4_is_added_beside_the_earlier_reading_and_an_empty_one_is_dropped():
    b = {c: "" for c in e1.READING_COLUMNS}
    R = pd.DataFrame([{**b, "episode_cik": "886043", "episode_accession": "m", "deal_id": "ep886043:1",
                       "target_ticker": "SBI", "acquirer_ticker": "MMU", "ann_date": "2023-03-17", "doc_cik": ""}])
    r4 = pd.DataFrame([{**b, "episode_cik": "882300", "episode_accession": "s", "deal_id": "ep882300:0",
                        "target_ticker": "SBI", "acquirer_ticker": "MMU", "outcome": "vote_failed", "in_trial": "Y",
                        "ann_date": "2023-07-28", "fail_date": "2024-01-30"},
                       {**b, "episode_cik": "905000", "episode_accession": "n", "deal_id": "ep905000:0"}])
    L = pd.DataFrame({"episode_cik": ["882300", "905000"], "episode_accession": ["s", "n"],
                      "for_episode": ["886043_m", "1195738_x"]})
    X = fr.add_r4(R, fr.rekey_r4(r4, L))
    assert len(X) == 2 and list(X["deal_id"]) == ["ep886043:1", "ep886043:1"] and X.loc[1, "doc_cik"] == "882300"
    _, probs = e1.check_readings(pd.DataFrame({"episode_cik": [886043], "episode_accession": ["m"]}), None,
                                 readings=X.drop(columns=["in_trial"]).assign(in_trial="N"))
    assert not any("blank outcome" in p for p in probs)          # the blank row is settled by the r4 row


def test_failed_deal_rows_take_the_earliest_announcement_over_every_reading(monkeypatch):
    nm = pd.DataFrame({"permno": [5, 6], "ticker": ["SBI", "MMU"], "namedt": pd.to_datetime(["2000-01-01"] * 2),
                       "nameendt": pd.to_datetime(["2024-12-31"] * 2), "shrcd": [14, 14], "exchcd": [1, 1],
                       "comnam": ["WESTERN ASSET INTERMED MUNI FD", "WESTERN ASSET MANAGED MUNIS FUND"]})
    monkeypatch.setattr(e1.ce, "universe_permnos", lambda nm: {"XXX": [99]})
    monkeypatch.setattr(e1, "spec_names", lambda: set())
    b = {c: "" for c in e1.READING_COLUMNS}
    R = pd.DataFrame([{**b, "deal_id": "d", "target_ticker": "SBI", "acquirer_ticker": "MMU", "ann_date": "2023-03-17"},
                      {**b, "deal_id": "d", "target_ticker": "SBI", "acquirer_ticker": "MMU", "ann_date": "2023-07-28",
                       "in_trial": "Y", "fail_date": "2024-01-30"}])
    D = e1.failed_deal_rows(R, nm)
    assert D.loc[0, "ann"] == pd.Timestamp("2023-03-17") and D.loc[0, "fail_date"] == pd.Timestamp("2024-01-30")
    assert D.loc[0, "part"] == "time_holdout" and D.loc[0, "seg"] == "muni"
