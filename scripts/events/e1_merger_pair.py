"""E1: the NAV-for-NAV CEF merger pair (EVENTS trial 1, approved 2026-10-19 with amendment 1).

    python3 scripts/events/e1_merger_pair.py stage0      # Stage 0: DG-E1-1..7, the counts, the halt list
    python3 scripts/events/e1_merger_pair.py fit         # stages 1-6; writes the fit verdict (stage 7 commits it)
    python3 scripts/events/e1_merger_pair.py holdout     # stage 8: the holdouts, OPENED ONCE

  Offline helpers (no credential is read):
    python3 scripts/events/e1_merger_pair.py stage-crsp --from DIR [--from DIR ...]
        # assemble the fit reader's CRSP extract from extracts already pulled by the same SQL

  Team lead only (each loads a credential from the env file; an agent never runs them):
    QUANTT_ENV_FILE=<env> python3 scripts/events/e1_merger_pair.py fetch-edgar    # DG-E1-2 dates, DG-E1-3 filings
    QUANTT_ENV_FILE=<env> python3 scripts/events/e1_merger_pair.py pull-crsp      # the fit reader's extract (R2)
    QUANTT_ENV_FILE=<env> python3 scripts/events/e1_merger_pair.py pull-holdout   # the holdout reader's extract (R2),
                                                                                 # refused before the fit verdict commit

WHAT THIS IS
------------
The trial script `results/events/PREREG_E1_MERGER_PAIR_2026-10-19.md` names (§6.4, §14). EVENTS trial 1,
judged at N = 6 (decision 1). After an EDGAR-dated NAV-for-NAV merger announcement between two
listed CEFs: long the target, short the acquirer, $1 for $1, from the close of A+1 to completion
(or to the close after a failure is public). Muni deals decide (decision 2); every other segment
is reported beside them and never decides.

AMENDMENT 1 (team lead, 2026-10-19, before any E1 return): "ignore fees, just look at PnL".
Borrow is never in a verdict. f_max is computed and printed (stages 4 and 7) and decides
nothing; the four borrow schedules are printed in their own labelled columns. Stage 4's 15bp
execution-cost test and the 5 / 15 / 30bp grid stand (the coordinator's reading of "fees").

THE ORDER OF EVALUATION (PREREG §10), and what this script refuses
------------------------------------------------------------------
  0  data gates DG-E1-1..7, the counts, both identity checks, the quality screen, k, the
     cap's binding share. ANY gate failure is a HALT, referred to the team lead; no E1
     statistic is computed past it. `fit` refuses unless the committed Stage-0 record says
     STAGE 0: CLEAR and every Stage-0 flag has a recorded ruling (`require_stage0_rulings`,
     the house rule of 2026-10-19, `.claude/skills/prereg/SKILL.md` §4b).
  1  fit muni per deal (completed and failed): median > 60bp AND group-clustered t >= 2.0, else KILL D1
  2  control 1 (the same pair a year earlier): median < 1/2 x treatment, else KILL
  3  control 2 (a non-merging same-sponsor fund in place of the target): the same; HALT if
     fewer than 75% of fit muni deals have one
  4  the tradable sleeve's net at 15bp (event turnover) > 0, else KILL D2; f_max printed
  5  R-D4: alpha t >= 3.0 and every |summed beta| <= 0.10, else KILL D4
  6  the bar: validate._dsr at N = 6 > 0.95, else NEITHER
  7  the fit verdict, k and f_max are committed (by hand) before any holdout number exists
  8  the holdouts, opened once: name + time pooled; three signs > 0, else KILL D3
Every statistic of every stage is computed and printed whatever the verdict; the verdict is
the first failing rule in that order. The holdout can kill; it can never rescue.

ALIGNMENT (H1, H7), stated and asserted
---------------------------------------
* A filing dated A is public by 22:00 ET on A (EDGAR's acceptance rule moves a filing after
  17:30 to the next business day, REFERENCES §12z). The decision is the evening of A; the
  fill is the close of the target's first session after A (`merger_pairs._announcement_row`'s
  d_in); the first return earned is the session after the fill. In the harness the weight
  sits on the market session before the fill and `evaluate()` applies shift(2);
  `band_frontier.event_hold` RAISES if a leg's fill is not strictly after A.
* A completed deal earns through the payment date dlpdt: the target's delisting return is
  booked on the dlpdt row, the acquirer's own returns run to dlpdt, and the legs leave H two
  sessions before dlpdt so their last earned return is dlpdt's. A failed deal is decided out
  on the evening of the failure filing date F and closed at the close of F+1.
* Every estimate that a later stage uses (k, f_max, the cap) comes from the fit only, is
  written to the fit verdict file, and is read back -- never re-fitted -- by the holdout.
* The fit reader is `crsp_events.daily`, which cannot return a 2023+ row. The holdout reader
  (`holdout_daily`) refuses unless the fit verdict is committed and says the holdout opens.

RETURNS (H15): CRSP `ret`, a total return; the short pays its distributions inside it.
`evaluate()` sums with pandas' skipna, so before any P&L the held name-days are checked
(`hold_gaps`): each is a finite `ret`, a missing-price gap of <= 10 sessions that the next
`ret` spans (CRSP's convention, tested on these extracts by `merger_pairs.bridging_check`),
or a target's sessions between its last trade and the payment date that its delisting
return spans. Anything else excludes the deal, counted. Nothing is filled with zero.

PUBLIC REPOSITORY: CRSP is licensed. Tracked outputs carry aggregates, counts, CRSP-free
EDGAR facts (CIKs, accessions, quotes) and tickers with dates; never a row-level price or
return. Row-level files go to `results/events/e1/_cache_e1/` (gitignored).

IMPLEMENTATION READINGS (the pre-registration is silent; each is listed in the Stage 0 note for the
team lead to correct before Stage 1). RULED 2026-10-20: all twelve accepted as recommended
(team lead, "accept all recommended"; PREREG amendment 2; results/events/E1_RULINGS_FORM_2026-10-20.md):
  R1 identity check 1 compares to 1e-12 against the published per-deal values as re-computed
     by `merger_pairs.announcement_sample_edgar` in memory, and at the published file's own
     precision (%.8g, string-equal) against `merger_ann_sample_edgar.csv`; the published
     aggregates in the tracked `merger_ann_edgar_summary.json` must match exactly.
  R2 a sleeve leg's weight is 1/n_g, n_g = the group's PRICED deals in that sleeve's set.
  R3 control 1's window length is counted in target sessions: (d_in, dlstdt] for a completed
     deal, (d_in, F+1] for a failed one; it ends 252 target sessions before d_in.
  R4 control 2's ADV is the 63-session mean of price x volume ending the session before A,
     for the target and each candidate; a candidate whose CRSP name cannot be matched to an
     EDGAR CIK (so its merger filings cannot be checked) is not a candidate, and is counted.
  R5 eras assign a deal by its fill date d_in.
  R6 the conversion residual in the sleeve is |R_T(dlpdt) - R_A(dlpdt)| x the converted
     weight; per deal (buy and hold) it is |pair return|, so units are 2 + |pair|.
  R7 the Stage-0 rulings file is `results/events/e1/e1_stage0_rulings.csv`: the E1
     pre-registration declares none (it predates §4b), so the house template's path is used.
  R8 DG-E1-5 asks for MUB/IEF/HYG coverage to 2024-12-31, but the only declared CRSP reader
     that may read 2023+ rows is the holdout reader, after the fit verdict. No E1 statistic
     uses factor returns after 2022, so DG-E1-5 clears on coverage of the fit window.
  R9 control 2's candidates are not filtered for `cef_universe.csv` names or the spec's 13 (the
     pre-registration names no such filter). A universe name chosen as a control is a return on
     the 27-name set; E1 consumes that set at Stage 1 anyway (decision 3).
  R10 DG-E1-3's census keeps every merger episode no matched CRSP completion explains; the
     "both parties listed CEFs/BDCs" test is left to the reading, which alone names the
     counterparty, so open-end trusts' N-14 episodes are read and recorded as not_a_listed_pair.
  R11 control 2's holdout exclusion uses holdout deal windows from dates only, [A, exit + 1 day],
     wider than the traded window, so no holdout price is read before the fit verdict.
  R12 stage 8 opens after any committed fit verdict except a HALT; after a KILL or NEITHER it is
     report-only and the verdict stays the fit's (`holdout_opens`). Until the 2026-10-20 ruling
     `holdout` refused after any non-pass.

Tests: scripts/events/tests/test_e1_merger_pair.py (synthetic frames; the network is blocked),
scripts/cef/tests/test_event_hold.py (the two band_frontier helpers).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("compute.use_numexpr", False)   # DG-E1-6 (scripts/events/numexpr_fault.py)

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:  # run as a script, not -m
    sys.path.insert(0, str(REPO))

from scripts.cef import band_frontier as bf  # noqa: E402
from scripts.events import crsp_events as ce  # noqa: E402
from scripts.events import merger_pairs as mp  # noqa: E402

# --------------------------------------------------------------------------- declared constants
PREREG = REPO / "results" / "events" / "PREREG_E1_MERGER_PAIR_2026-10-19.md"
PREREG_COUNTS = REPO / "results" / "events" / "e1_prereg_counts_2026-10-19.json"
OUT_DIR = REPO / "results" / "events" / "e1"
CACHE = OUT_DIR / "_cache_e1"                                    # gitignored (results/**/_cache_*)
STAGE0_JSON = OUT_DIR / "e1_stage0.json"
STAGE0_OUT = OUT_DIR / "e1_stage0_output.txt"
STAGE0_FLAGS = OUT_DIR / "e1_stage0_flags.csv"
RULINGS = OUT_DIR / "e1_stage0_rulings.csv"                       # reading R7
READINGS = OUT_DIR / "e1_failed_deal_readings.csv"                # DG-E1-3, written by a reader
# The readings after every round and ruling (`e1_failed_reading.dg3_state`), written by Stage 0
# and committed with its record: the ONLY failed-deal source the fit and the holdout read. The
# round-1 file above holds 3 in-trial deals; the ruled set Stage 0 cleared holds 13 (2026-10-22).
READINGS_RULED = OUT_DIR / "e1_failed_deal_readings_ruled.csv"
CENSUS = OUT_DIR / "e1_failed_census.csv"                         # DG-E1-3 candidates (EDGAR facts only)
CENSUS_SUPP = OUT_DIR / "e1_failed_census_supp.csv"               # ruling 9 (amendment 3): acquirer episodes a completion explained
DG3_RULINGS = OUT_DIR / "e1_dg3_rulings.csv"                       # amendments 3 and 4's record (items 1-11)
# Amendment 4 (team lead, 2026-10-21, before any E1 return): the deal universe of §4.1 takes CRSP
# delisting codes 231 AND 331 when the delisting maps to the acquirer's permno (CRSP codes many CEF
# reorganisations 331). Its counts: UNIVERSE_COUNTS; the 331 deals' EDGAR dates: DATES_331.
UNIVERSE_CODES = (231, 331)
UNIVERSE_COUNTS = OUT_DIR / "e1_universe_counts_2026-10-21.json"
DATES_331 = CACHE / "e1_331_edgar_dates.csv"                       # gitignored: CRSP permnos
DATES_331_SUMMARY = OUT_DIR / "e1_331_edgar_dates_summary.json"
A4_CRSP_PERMNOS = CACHE / "amendment4_crsp_permnos.txt"
FIT_JSON = OUT_DIR / "e1_fit_verdict.json"
FIT_OUT = OUT_DIR / "e1_fit_output.txt"
HOLDOUT_JSON = OUT_DIR / "e1_holdout.json"
HOLDOUT_OUT = OUT_DIR / "e1_holdout_output.txt"
HOLDOUT_MARKER = OUT_DIR / "e1_holdout_opened.txt"
FIT_DATES = REPO / "results" / "events" / "merger_edgar_dates.csv"            # edgar_merger_dates.py (gitignored)
FIT_DATES_SUMMARY = REPO / "results" / "events" / "merger_edgar_dates_summary.json"
PUBLISHED_DEALS = REPO / "results" / "events" / "merger_ann_sample_edgar.csv"  # merger_pairs.py --edgar-dates (gitignored)
PUBLISHED_SUMMARY = REPO / "results" / "events" / "merger_ann_edgar_summary.json"
HOLDOUT_DATES = CACHE / "e1_holdout_edgar_dates.csv"              # gitignored: CRSP permnos
HOLDOUT_DATES_SUMMARY = OUT_DIR / "e1_holdout_edgar_dates_summary.json"
EPISODES = REPO / "results" / "events" / "edgar_cef_bdc_episodes.csv"         # fetch_edgar_events.py
EDGAR_UNION = CACHE / "edgar_union"     # EDGAR caches already fetched, linked; results/events/E1_STAGE0_2026-10-19.md §3
FF_CACHE = REPO / "results" / "cef" / "w4" / "_cache_w4" / "ff5_umd_daily.parquet"  # fetch_ff_factors.py
BORROW = REPO / "data" / "cef" / "cef_borrow_history.parquet"

N_EVENTS = 6                 # decision 1, fixed on approval 2026-10-19 (docs/RESEARCH_STATE.md)
MEDIAN_KILL = 0.0060         # stage 1: median per deal must exceed 60bp (plan §3 row 2)
T_KILL = 2.0                 # stage 1: group-clustered t >= 2.0
CONTROL_FRACTION = 0.5       # stages 2-3: a control at >= 1/2 the treatment's median kills
CONTROL2_MIN_SHARE = 0.75    # stage 3: HALT below 75% of fit muni deals with a control
D4_ALPHA_T = 3.0             # stage 5 (decision 8)
D4_MAX_BETA = 0.10
DSR_PASS = 0.95              # stage 6
GRID_BP = (5, 15, 30)
DECIDING_BP = 15
CTRL_LAG = 252               # control 1 ends 252 target sessions before entry
ADV_SESSIONS = 63
CTRL2_PRE, CTRL2_POST = 252, 21   # control 2: no merger episode from A-252 sessions to exit+21
SEED = 20261019
REPS = 10_000
NW_L, NW_L_LONG = 21, 63
BOOT_BLOCK, BOOT_BLOCK_ALT = 63, 21
FAIL_WINDOW_DAYS = 730            # §4.3: no CRSP completion within 730 days
EPISODE_START, EPISODE_END = pd.Timestamp("2009-07-01"), pd.Timestamp("2024-12-31")
FMAX_MARGIN = 0.5                 # §5.3 (report-only under amendment 1)
CAPITALS = (1e5, 1e6, 1e7)
PARTICIPATION_GUARD = 0.05        # the desk's convention (plan_diagnostics.py prints it); reported only
FIT_START, FIT_END = pd.Timestamp("2009-07-01"), pd.Timestamp("2022-12-31")
# The market calendar must hold every fit deal's window; a 2010 completion can be announced in 2009
# (amendment 4's BZA, BCL, BCK -> BFZ: A = 2009-06-23). Not a rule parameter: where the sessions start.
CAL_START = pd.Timestamp("2008-07-01")
HOLDOUT_START, CRSP_END = ce.TIME_HOLDOUT, pd.Timestamp("2024-12-31")
ERAS = (("2010-14", "2010-01-01", "2014-12-31"), ("2015-19", "2015-01-01", "2019-12-31"),
        ("2020-22", "2020-01-01", "2022-12-31"))
HOLDOUT_ERA = ("2023-24", "2023-01-01", "2024-12-31")
ETF_TICKERS = ("MUB", "IEF", "HYG")
FF6 = ("mktrf", "smb", "hml", "rmw", "cma", "umd")
PRICED = ("ok", "bridged")
FIT_SET, HOLDOUT_SETS = "fit_seen", ("name_holdout", "time_holdout")
BORROW_MEAS_START = pd.Timestamp("2021-09-13")
# Reading R12, ruled 2026-10-20 (team lead: "accept all recommended"; PREREG amendment 2): the
# holdout opens after any committed fit verdict except a HALT; after a KILL or NEITHER it is
# report-only and the verdict stays the fit's. Was None (refuse after any non-pass) until then.
HOLDOUT_OPENS_AFTER_FIT_KILL: bool | None = True

READING_COLUMNS = ("episode_cik", "episode_accession", "deal_id", "role", "counterparty_cik",
                   "counterparty_name", "both_listed", "outcome", "in_trial",
                   "target_cik", "acquirer_cik", "target_ticker", "acquirer_ticker", "ann_date", "ann_accession", "ann_quote",
                   "fail_date", "fail_accession", "fail_quote", "outcome_date", "outcome_accession",
                   "outcome_quote", "read_by", "read_on")
OUTCOMES = ("completed", "completed_other_structure", "completed_after_crsp", "terminated",
            "vote_failed", "withdrawn", "superseded", "not_a_listed_pair")
FAILED_OUTCOMES = ("terminated", "vote_failed", "withdrawn", "superseded")
# The filings DG-E1-3's readers see for each census episode: these forms, filed from 30 days
# before the episode's first filing to 730 days after (`fetch-edgar` fetched exactly these).
CENSUS_FORMS = ("425", "N-14", "N-14/A", "N-14 8C", "N-14 8C/A", "PREM14A", "DEFM14A", "DEFA14A", "DEF 14A",
                "PRE 14A", "8-K", "RW", "N-8F")
CENSUS_PRE_DAYS = 30
# A targeted fetch (`fetch-edgar --cik`) also takes the fund's annual and semi-annual reports, which
# report shareholder-meeting results (how SBI -> MMU's 2023 vote ended is not in MMU's filings).
TARGETED_FORMS = CENSUS_FORMS + ("N-CSR", "N-CSRS", "DEFA14A")


class GateError(RuntimeError):
    """A gate could not clear, or a stage was asked to run out of order."""


def _rel(p: Path) -> str:
    """A path as the repo names it, or whole when it lies outside (a test's tmp dir)."""
    try:
        return str(Path(p).relative_to(REPO))
    except ValueError:
        return str(p)


# =========================================================================== CRSP access

def _dsf_path(perms) -> Path:
    """Where `crsp_events.daily(perms)` keeps its extract (the permno list is in the name)."""
    _, h = ce._plist(perms)
    return ce.CACHE / f"dsf_{h}.parquet"


def crsp_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """CRSP names and delistings from the cache only. `crsp_events.names()` would pull from R2
    on a miss, which loads a credential: refuse instead, naming the command."""
    for f in ("dsenames.parquet", "dsedelist.parquet"):
        if not (ce.CACHE / f).exists():
            raise GateError(f"DG-E1-1: {_rel(ce.CACHE / f)} is missing; the team lead runs "
                            "`python3 scripts/events/crsp_events.py` (R2) or a cache is copied in")
    return ce.names(), ce.delistings()


def fit_daily(perms) -> pd.DataFrame:
    """The fit reader: `crsp_events.daily` (every row before 2023-01-01, none after; asserted
    there), on an extract that already exists. It never pulls: a missing extract raises naming
    `stage-crsp` (offline) and `pull-crsp` (the team lead)."""
    p = _dsf_path(perms)
    if not p.exists():
        raise GateError(f"DG-E1-1: no cached CRSP extract for these {len(set(perms))} permnos ({p.name}); "
                        "run `stage-crsp --from <dir>` if extracts exist, else the team lead runs `pull-crsp`")
    d = ce.daily(perms)
    if len(d) and d["date"].max() >= HOLDOUT_START:
        raise AssertionError("the fit reader returned a 2023+ row")
    return d


def raw_prc_negative(perms) -> pd.DataFrame:
    """(permno, date) rows where CRSP's raw `prc` is negative: no closing trade, the bid/ask
    average stands in (the fill-day quality screen, §8.2). `crsp_events.daily` returns |prc|,
    so the sign is read from the same cached extract."""
    raw = pd.read_parquet(_dsf_path(perms), columns=["permno", "date", "prc"])
    raw["date"] = pd.to_datetime(raw["date"])
    return raw.loc[raw["prc"] < 0, ["permno", "date"]]


def _committed_clean(*paths: Path) -> None:
    for p in paths:
        r = subprocess.run(["git", "ls-files", "--error-unmatch", str(p)], cwd=REPO, capture_output=True)
        if r.returncode:
            raise GateError(f"{p.relative_to(REPO)} is not committed")
        r = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(p)], cwd=REPO)
        if r.returncode:
            raise GateError(f"{p.relative_to(REPO)} differs from its committed version")


def holdout_gate(fit_json: Path = FIT_JSON) -> dict:
    """The holdout reader's guard (DG-E1-1): the fit verdict must be committed, unmodified, and
    say the holdout opens (PREREG §10 stage 7; E2's DG-E2-1 pattern). Returns the verdict."""
    _committed_clean(fit_json)
    v = json.loads(fit_json.read_text())
    if not v.get("stage7_fit_verdict_written"):
        raise GateError(f"{fit_json.name} is not a stage-7 fit verdict")
    if not holdout_opens(v["verdict"]):
        raise GateError(f"the fit verdict is {v['verdict']!r}: the holdout does not open after it (reading R12)")
    return v


def holdout_opens(verdict: str) -> bool:
    """Reading R12 (ruled 2026-10-20): a pass opens the holdout; a KILL or NEITHER opens it
    report-only; a HALT never does, because its verdict is not final."""
    if verdict.startswith("HALT"):
        return False
    return verdict == "FIT PASSES STAGES 1-6" or HOLDOUT_OPENS_AFTER_FIT_KILL is True


def holdout_daily(perms) -> pd.DataFrame:
    """The holdout reader: CRSP rows for the holdout parties to 2024-12-31, from the extract
    `pull-holdout` staged. Refuses before the fit verdict commit (`holdout_gate`)."""
    holdout_gate()
    s, h = ce._plist(perms)
    p = CACHE / f"holdout_dsf_{h}.parquet"
    if not p.exists():
        raise GateError(f"no holdout extract {p.name}; the team lead runs `pull-holdout`")
    d = pd.read_parquet(p)
    d["date"] = pd.to_datetime(d["date"])
    d["prc"] = d["prc"].astype(float).abs()
    for c in ("ret", "retx", "vol", "shrout", "cfacpr"):
        d[c] = d[c].astype(float)
    return d


def stage_crsp(perms, sources: list[Path], partial: bool = False) -> tuple[Path, list[int]]:
    """Build `crsp_events.daily(perms)`'s extract from extracts already pulled by the same SQL
    (`SELECT permno, date, prc, ret, retx, vol, shrout, cfacpr ... date < 2023-01-01`).

    Offline and credential-free. Every requested permno must be found; where two source
    extracts hold the same (permno, date), every column must agree exactly (the CRSP mirror is
    one vintage; a disagreement raises rather than picking one). The manifest records the
    sources' own pull times."""
    want = sorted({int(p) for p in perms})
    parts, pulled = [], {}
    for src in sources:
        man = json.loads((src / "_manifest.json").read_text()) if (src / "_manifest.json").exists() else {}
        for f in sorted(src.glob("dsf_*.parquet")):
            m = man.get(f.stem, {})
            if "date < DATE '2023-01-01'" not in m.get("sql", ""):
                continue
            d = pd.read_parquet(f, filters=[("permno", "in", want)])
            if len(d):
                parts.append(d)
                pulled[str(f.resolve())] = m.get("pulled_utc")
    if not parts:
        raise GateError("stage-crsp: no source extract holds any requested permno")
    d = pd.concat(parts, ignore_index=True)
    d["date"] = pd.to_datetime(d["date"])
    missing = sorted(set(want) - set(d["permno"].astype(int)))
    if missing and not partial:
        raise GateError(f"stage-crsp: {len(missing)} permno(s) in no source extract (first {missing[:10]}); "
                        "the team lead runs `pull-crsp`")
    want = sorted(set(want) - set(missing))      # partial: an extract of the permnos found, named by them
    cols = ["prc", "ret", "retx", "vol", "shrout", "cfacpr"]
    g = d.groupby(["permno", "date"])[cols]
    spread = (g.max() - g.min()).abs().max()
    cnt, size = g.count(), g.size()
    nan_mismatch = int(((cnt != 0) & cnt.ne(size, axis=0)).any(axis=1).sum())   # NaN in one source only
    if (spread.fillna(0) > 0).any() or nan_mismatch:
        raise GateError(f"stage-crsp: source extracts disagree on a (permno, date): {spread.to_dict()}")
    d = d.drop_duplicates(["permno", "date"]).sort_values(["permno", "date"]).reset_index(drop=True)
    if d["date"].max() >= HOLDOUT_START:
        raise AssertionError("stage-crsp: a 2023+ row")
    out = _dsf_path(want)
    ce.CACHE.mkdir(parents=True, exist_ok=True)
    d.to_parquet(out)
    path = ce.CACHE / "_manifest.json"
    m = json.loads(path.read_text()) if path.exists() else {}
    s, _ = ce._plist(want)
    m[out.stem] = {"pulled_utc": min(v for v in pulled.values() if v), "rows": int(len(d)),
                   "sql": "SELECT permno, date, prc, ret, retx, vol, shrout, cfacpr FROM read_parquet('{dsf}') "
                          f"WHERE permno IN ({s}) AND date < DATE '2023-01-01'",
                   "assembled_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "assembled_from": pulled}
    path.write_text(json.dumps(m, indent=1, sort_keys=True))
    return out, missing


# =========================================================================== deals and dates

def spec_names() -> set:
    sys.path.insert(0, str(REPO / "scripts" / "cef"))
    import spec  # noqa: E402  (the frozen spec is the only authority on the live universe)
    return set(spec.frozen("universe"))


def deal_table(nm: pd.DataFrame, dl: pd.DataFrame, codes: tuple = UNIVERSE_CODES) -> pd.DataFrame:
    """The declared partition on the full delisting table: one row per completed deal, with `part`
    and `seg`. `e1_prereg_counts.build`'s steps, with amendment 4's universe: delisting codes
    `codes` with an acquirer permno (`codes=(231,)` reproduces `pc.build` exactly: checked equal, 264
    rows, on the 2026-10-12 CRSP cache, 2026-10-21)."""
    from scripts.events import e1_prereg_counts as pc
    x = mp.build_events(nm, dl, start=pc.START, end=pc.END, extra_codes=tuple(c for c in codes if c // 100 != 2))
    x = mp.flag_universe(x, nm)
    x = x[x["dlstcd"].isin(codes) & (x["kind"] == "stock") & (x["nwperm"] > 0)].copy()
    x["seg"] = x["comnam"].map(mp.classify)
    x["spec_touch"] = pc.spec_touch(x, nm, spec_names())
    x["part"] = pc.partition(x)
    pc.assert_groups_whole(x)
    for c in ("dlpdt", "dlret", "dlamt"):
        if c not in x:
            raise GateError(f"the delisting table lacks {c}")
    return x.reset_index(drop=True)


def counts_vs_prereg(x: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Deals and acquirer x completion groups by set and segment, beside amendment 4's counts file
    (which must match: H14, re-measured, never assumed) and the pre-registration's 231-only counts."""
    from scripts.events import e1_prereg_counts as pc
    now = pd.DataFrame(pc.counts(x)).set_index(["set", "segment"])[["events", "groups_acq_x_completion"]]
    a4 = pd.DataFrame(json.loads(UNIVERSE_COUNTS.read_text())["counts"]).set_index(["set", "segment"])
    was = pd.DataFrame(json.loads(PREREG_COUNTS.read_text())["counts"]).set_index(["set", "segment"])
    t = now.join(a4[["events", "groups_acq_x_completion"]], rsuffix="_a4", how="outer").join(
        was[["events", "groups_acq_x_completion"]], rsuffix="_prereg231", how="outer").fillna(0).astype(int)
    ok = bool((t["events"] == t["events_a4"]).all() and (t["groups_acq_x_completion"] == t["groups_acq_x_completion_a4"]).all())
    return t, ok


def universe_counts(nm: pd.DataFrame, dl: pd.DataFrame) -> dict:
    """Amendment 4's deal counts by set and segment (no return of any kind is read)."""
    from scripts.events import e1_prereg_counts as pc
    x = deal_table(nm, dl)
    res = {"what": "E1 deal counts under amendment 4 (delisting codes 231 and 331 into the acquirer's permno); "
                   "counts only, no return read", "codes": list(UNIVERSE_CODES), "counts": pc.counts(x),
           "deals_331_by_set": x.loc[x["dlstcd"] == 331, "part"].value_counts().to_dict(),
           "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    UNIVERSE_COUNTS.write_text(json.dumps(res, indent=1) + "\n")
    return res


def attach_dates(x: pd.DataFrame, dates: pd.DataFrame) -> pd.DataFrame:
    """Join EDGAR announcement dates (one per target permno) to the deals; `group` is acquirer x
    announcement date, the clustering unit (§4.1)."""
    d = dates.drop_duplicates("permno").set_index("permno")
    if dates["permno"].duplicated().any():
        raise GateError("two EDGAR dates for one target permno")
    y = x.copy()
    y["ann"] = pd.to_datetime(y["permno"].map(d["ann_date"]))
    y["date_basis"] = y["permno"].map(d["date_basis"])
    y["group"] = y["nwperm"].astype(int).astype(str) + "@" + y["ann"].dt.strftime("%Y-%m-%d")
    return y


def dates_331() -> pd.DataFrame:
    """Amendment 4's 331 deals dated by `edgar_merger_dates.date_deals`, unchanged (empty if not yet run)."""
    if not DATES_331.exists():
        return pd.DataFrame(columns=["permno", "ann_date", "date_basis", "why_undated", "t_status"])
    return pd.read_csv(DATES_331)


def load_fit_dates(x: pd.DataFrame) -> pd.DataFrame:
    """`merger_edgar_dates.csv` must date exactly the fit set's 231 deals (DG-E1-2, fit half); the
    331 deals' dates (amendment 4) come from `dates_331`, and a 331 deal it lacks is left undated
    for the caller to count."""
    if not FIT_DATES.exists():
        raise GateError(f"DG-E1-2: {FIT_DATES.relative_to(REPO)} is missing; run "
                        "`python3 scripts/events/edgar_merger_dates.py --offline` against the cache that dated it")
    d = pd.read_csv(FIT_DATES)
    fit = set(x.loc[(x["part"] == FIT_SET) & (x["dlstcd"] == 231), "permno"].astype(int))
    if set(d["permno"].astype(int)) != fit:
        raise GateError(f"DG-E1-2: {FIT_DATES.name} dates {len(d)} deals; the fit set has {len(fit)}, "
                        "and they are not the same deals")
    summ = json.loads(FIT_DATES_SUMMARY.read_text())
    if summ["events"] != len(d) or summ["dated"] != int(d["ann_date"].notna().sum()):
        raise GateError(f"DG-E1-2: {FIT_DATES.name} disagrees with its committed summary")
    d3 = dates_331()
    d3 = d3[d3["permno"].isin(x.loc[(x["part"] == FIT_SET) & (x["dlstcd"] == 331), "permno"])]
    return pd.concat([d, d3], ignore_index=True)


# =========================================================================== DG-E1-2, DG-E1-3 (EDGAR)

def edgar_client(online: bool):
    """Offline (default): the union view of caches already fetched, read-only; a miss raises.
    Online (team lead only): the repo's polite client, which reads SEC_USER_AGENT from the env file."""
    from scripts.data.edgar_client import EdgarClient
    if online:
        # Online writes INTO the union view, so the next offline Stage 0 reads what was fetched.
        EDGAR_UNION.mkdir(parents=True, exist_ok=True)
        return EdgarClient(cache=EDGAR_UNION)
    if not EDGAR_UNION.exists():
        raise GateError(f"{EDGAR_UNION.relative_to(REPO)} does not exist (results/events/E1_STAGE0_2026-10-19.md §3 says how it is built)")
    return EdgarClient(offline=True, cache=EDGAR_UNION)


def date_holdouts(client, x: pd.DataFrame, today: date) -> tuple[pd.DataFrame, dict]:
    """DG-E1-2: the name- and time-holdout deals dated by `edgar_merger_dates.date_deals`,
    unchanged, on this sample (dates are not returns: zero trials)."""
    from scripts.events import edgar_merger_dates as emd
    s = x[x["part"].isin(HOLDOUT_SETS)]
    return emd.date_deals(client, today, sample=s)


def missing_documents(x: pd.DataFrame, today: date) -> tuple[list[str], dict]:
    """The EDGAR URLs DG-E1-2's dating would need that the offline cache does not hold.

    A probe: on a miss it records the URL and answers with an empty document (or, for a
    submissions list, one placeholder filing dated 1900 that no window admits), so the run
    goes on to find every miss. Deals are probed one at a time against a name table built
    once, so one deal's failure cannot hide another's misses. Its dates are DISCARDED (an
    empty document fails the text test, so they would be wrong); only the misses are used.
    They are a superset of what the real run reads: an empty document never stops a deal's
    candidate loop early. Returns (urls, {deal ticker: why the probe stopped, if it did})."""
    from scripts.data.edgar_client import EdgarClient, EdgarHTTPError
    from scripts.events import edgar_merger_dates as emd

    class Probe(EdgarClient):
        def __init__(self, **k):
            super().__init__(**k)
            self.misses: list[str] = []

        def get(self, url, max_age_s=None):
            try:
                return super().get(url, max_age_s)
            except EdgarHTTPError:
                self.misses.append(url)
                if "submissions" in url:
                    return json.dumps({"filings": {"recent": {
                        "accessionNumber": ["0000000000-00-000000"], "filingDate": ["1900-01-01"],
                        "form": ["PROBE"], "items": [""], "primaryDocument": [""]}, "files": []}}).encode()
                return "".join(f"<DOCUMENT>\n<TYPE>{f}\n<TEXT>\n</TEXT>\n</DOCUMENT>\n"
                               for f in ("425", "N-14", "N-14 8C", "PREM14A", "DEFM14A", "8-K")).encode()

    if not EDGAR_UNION.exists():
        raise GateError(f"{EDGAR_UNION.relative_to(REPO)} does not exist")
    c = Probe(offline=True, cache=EDGAR_UNION)
    table = emd.name_table(c, today)
    real = emd.name_table
    stopped = {}
    try:
        emd.name_table = lambda client, today: table
        for _, row in x[x["part"].isin(HOLDOUT_SETS)].iterrows():
            try:
                emd.date_deals(c, today, sample=pd.DataFrame([row]))
            except KeyError as ex:
                if ex.args != ("ann_form",):
                    stopped[str(row["ticker"])] = f"KeyError: {ex}"
                # else: date_deals' summary step, AFTER every document of the deal was requested;
                # it fails only because an empty document dates nothing. The misses are complete.
            except Exception as ex:  # recorded per deal; the misses already requested stand
                stopped[str(row["ticker"])] = f"{type(ex).__name__}: {str(ex)[:80]}"
    finally:
        emd.name_table = real
    return sorted(set(c.misses)), stopped


def merger_episodes() -> pd.DataFrame:
    """Every EDGAR merger episode (`fetch_edgar_events.py`, committed table) with a first filing
    in [2009-07-01, 2024-12-31] (§4.3)."""
    e = pd.read_csv(EPISODES)
    e = e[e["kind"] == "merger"].copy()
    for c in ("first_date", "last_date"):
        e[c] = pd.to_datetime(e[c])
    return e[(e["first_date"] >= EPISODE_START) & (e["first_date"] <= EPISODE_END)].reset_index(drop=True)


def completion_ciks(nm: pd.DataFrame, dl: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    """(cik, completion date, role, permno) for every CRSP merger delisting (dlstcd 2xx, and 331 under
    amendment 4) of a
    CEF permno, 2009-07-01 .. 2024-12-31, target and acquirer each matched to a CIK by
    `edgar_merger_dates.match_cik` with the dating script's own windows. Unmatched parties are
    returned with cik NaN and their status (they explain no episode)."""
    from scripts.events import edgar_merger_dates as emd
    x = mp.build_events(nm, dl, EPISODE_START, EPISODE_END, extra_codes=tuple(c for c in UNIVERSE_CODES if c // 100 != 2))
    rows = []
    for e in x.itertuples():
        C = pd.Timestamp(e.dlstdt)
        t = emd.match_cik(e.comnam, names, C - pd.Timedelta(days=emd.WINDOW_DAYS), C)
        rows.append({"cik": t.get("cik") if t["status"] == "matched" else np.nan, "C": C, "role": "target",
                     "permno": int(e.permno), "status": t["status"], "kind": e.kind})
        if isinstance(e.a_comnam, str):
            a = emd.match_cik(e.a_comnam, names, C - pd.Timedelta(days=365), C + pd.Timedelta(days=90))
            rows.append({"cik": a.get("cik") if a["status"] == "matched" else np.nan, "C": C, "role": "acquirer",
                         "permno": int(e.nwperm), "status": a["status"], "kind": e.kind})
    return pd.DataFrame(rows)


def failed_census(episodes: pd.DataFrame, comp: pd.DataFrame) -> pd.DataFrame:
    """DG-E1-3's candidates: merger episodes whose CIK is not a matched party of a CRSP merger
    completion within 730 days of the episode's first filing.

    The pre-registration also asks that both parties were listed CEFs/BDCs on the first filing
    date; the counterparty is named only inside the filings, so that test is the READING's
    (`READING_COLUMNS`: both_listed, in_trial), not this filter's. A completion after CRSP's
    last delisting (2024-12-31) is invisible here, so every episode whose window runs past it
    is a candidate too, and the reading records `completed_after_crsp`."""
    c = comp.dropna(subset=["cik"])
    by = {int(k): g["C"].values for k, g in c.groupby("cik")}
    out = []
    for e in episodes.itertuples():
        cs = by.get(int(e.cik), np.array([], dtype="datetime64[ns]"))
        lo, hi = np.datetime64(e.first_date), np.datetime64(e.first_date + pd.Timedelta(days=FAIL_WINDOW_DAYS))
        if ((cs >= lo) & (cs <= hi)).any():
            continue
        out.append({"episode_cik": int(e.cik), "episode_accession": e.first_accession,
                    "first_date": e.first_date.date(), "first_form": e.first_form,
                    "last_date": e.last_date.date(), "n_filings": int(e.n_filings), "forms": e.forms,
                    "company_last": e.company_last,
                    "window_past_crsp": bool(e.first_date + pd.Timedelta(days=FAIL_WINDOW_DAYS) > CRSP_END)})
    return pd.DataFrame(out)


def supp_census(episodes: pd.DataFrame, comp: pd.DataFrame) -> pd.DataFrame:
    """Ruling 9 (amendment 3, 2026-10-20): the merger episodes that a CRSP completion with the
    episode's CIK as ACQUIRER explains (within 730 days). The 730-day rule drops them, and with them
    any co-target that failed while another merged: SBI -> MMU (2023, §2.3) is the case that showed it."""
    c = comp[(comp["role"] == "acquirer")].dropna(subset=["cik"])
    by = {int(k): g["C"].values for k, g in c.groupby("cik")}
    out = []
    for e in episodes.itertuples():
        cs = by.get(int(e.cik), np.array([], dtype="datetime64[ns]"))
        lo, hi = np.datetime64(e.first_date), np.datetime64(e.first_date + pd.Timedelta(days=FAIL_WINDOW_DAYS))
        if ((cs >= lo) & (cs <= hi)).any():
            out.append({"episode_cik": int(e.cik), "episode_accession": e.first_accession,
                        "first_date": e.first_date.date(), "first_form": e.first_form,
                        "last_date": e.last_date.date(), "n_filings": int(e.n_filings), "forms": e.forms,
                        "company_last": e.company_last,
                        "window_past_crsp": bool(e.first_date + pd.Timedelta(days=FAIL_WINDOW_DAYS) > CRSP_END)})
    return pd.DataFrame(out)


def deal_keys(r: pd.DataFrame) -> pd.Series:
    """One deal's key across rows: a CIK-based deal_id as it is; a positional id (ep<cik>:<k>) only
    within its episode (positions are not comparable across episodes)."""
    ep = r["deal_id"].str.startswith("ep")
    return r["deal_id"].where(~ep, r["episode_cik"] + "_" + r["episode_accession"] + "|" + r["deal_id"])


def check_readings(census: pd.DataFrame, client, readings: pd.DataFrame | None = None,
                   exempt: pd.Series | None = None) -> tuple[pd.DataFrame, list[str]]:
    """DG-E1-3: every candidate episode has at least one reading row (one per deal its filings
    describe, `deal_id` distinct within the episode); every quote is re-found, on THIS run, in the
    episode CIK's own cached filing it cites (`conditional_tender_census.quote_in`, the
    merger_arb_readings design); a deal read from two episodes (its target's and its acquirer's)
    agrees on its parties, outcome and in_trial. Returns (readings, problems); any problem fails
    the gate. A blank outcome is a problem: an episode whose filings do not settle the outcome
    blocks Stage 0 until someone reads further."""
    from scripts.data.edgar_client import filing_txt_url
    from scripts.events.conditional_tender_census import quote_in
    if readings is None and not READINGS.exists():
        return pd.DataFrame(columns=READING_COLUMNS), [f"{_rel(READINGS)} does not exist: "
                                                       f"{len(census)} candidate episode(s) unread"]
    r = pd.read_csv(READINGS, dtype=str, keep_default_na=False) if readings is None else readings.reset_index(drop=True)
    # Ruling 5 (amendment 3): a row that cannot change the trial is read and does not block; its
    # blank outcome, quote and conflicts are not checked. Every episode must still have a reading.
    ex = (pd.Series(False, index=r.index) if exempt is None else exempt.reset_index(drop=True).astype(bool))
    probs = []
    miss_c = [c for c in READING_COLUMNS if c not in r.columns]
    if miss_c:
        return r, [f"{READINGS.name} lacks columns {miss_c}"]
    key = set(census["episode_cik"].astype(str) + "|" + census["episode_accession"])
    rk = r["episode_cik"] + "|" + r["episode_accession"]
    unread = sorted(key - set(rk))
    if unread:
        probs.append(f"{len(unread)} candidate episode(s) have no reading (first {unread[:5]})")
    extra = sorted(set(rk) - key)
    if extra:
        probs.append(f"{len(extra)} reading(s) of an episode not in the census (first {extra[:3]})")
    # A deal read again from ANOTHER fund's filings (round r4, `doc_cik`) is a second reading, not a duplicate.
    dup_keys = ["episode_cik", "episode_accession", "deal_id"] + (["doc_cik"] if "doc_cik" in r else [])
    if r.duplicated(dup_keys).any():
        probs.append("an episode reads one deal twice")
    # Ruling 1 (one deal, one count): a blank row of a deal another row settles is not a gap.
    dk = deal_keys(r)
    settled = set(dk[r["outcome"] != ""])
    bad = ~r["outcome"].isin(OUTCOMES) & ~ex & ~dk.isin(settled)
    if bad.any():
        probs.append(f"{int(bad.sum())} row(s) with an unknown or blank outcome {sorted(set(r.loc[bad, 'outcome']))} "
                     f"in {int((r.loc[bad, 'episode_cik'] + r.loc[bad, 'episode_accession']).nunique())} episode(s)")
    # A failure whose listing nobody settled can still be a failed listed pair: it blocks too.
    unl = r["outcome"].isin(FAILED_OUTCOMES) & (r["both_listed"] == "") & ~ex
    if unl.any():
        probs.append(f"{int(unl.sum())} failure row(s) whose listing is unsettled, in "
                     f"{int((r.loc[unl, 'episode_cik'] + r.loc[unl, 'episode_accession']).nunique())} episode(s)")
    for row in r[~ex].itertuples(index=False):
        for acc_col, q_col in (("ann_accession", "ann_quote"), ("fail_accession", "fail_quote"),
                               ("outcome_accession", "outcome_quote")):
            acc, q = getattr(row, acc_col), getattr(row, q_col)
            if getattr(row, "ruled", "") == "15" and acc_col == "fail_accession" and not q:
                continue        # ruling 15: F is §4.3's superseded date (a later proposal's first filing), not a quote
            if not acc and not q:
                continue
            if not (acc and q):
                probs.append(f"{row.episode_accession}: {acc_col} and {q_col} must both be given")
                continue
            try:   # a row read from another fund's filings (round r4) names them in doc_cik
                txt = client.get_text(filing_txt_url(int(getattr(row, "doc_cik", "") or row.episode_cik), acc))
            except Exception as ex:  # a missing document is a gate failure, named
                probs.append(f"{row.episode_accession}: {acc} cannot be read ({type(ex).__name__})")
                continue
            if not quote_in(txt, q):
                probs.append(f"{row.episode_accession}: quote not found in {acc}")
        if row.in_trial == "Y":
            if row.outcome not in FAILED_OUTCOMES or row.both_listed != "Y":
                probs.append(f"{row.episode_accession}: in_trial needs a failure outcome and both parties listed")
            by_rule = getattr(row, "ruled", "") == "15"     # F set by §4.3's superseded rule, not a quote
            if not all((row.ann_quote or by_rule, row.fail_quote or by_rule, row.fail_date, row.target_ticker,
                        row.acquirer_ticker, row.target_cik or by_rule, row.acquirer_cik or by_rule)):
                probs.append(f"{row.episode_accession}: a failed deal needs its announcement and failure quotes, "
                             "the failure date, and both parties' CIKs and tickers")
    # A blank is a reader who did not see the answer, not a contradiction: only two DIFFERENT
    # non-blank outcomes or parties for one deal disagree (fixed 2026-10-20; the first version
    # counted a blank against a value and flagged 63 deals that no reading contradicted).
    for d, g in r[(r["deal_id"] != "") & ~ex].groupby("deal_id"):
        if len(g) > 1 and any(g.loc[g[c] != "", c].nunique() > 1 for c in ("outcome", "target_cik", "acquirer_cik")):
            probs.append(f"deal {d}: its readings disagree on outcome or parties")
    return r, probs


# =========================================================================== prices, returns, guards

def price_series(dsf: pd.DataFrame) -> dict:
    """permno -> its CRSP rows indexed by date (what `merger_pairs` calls px)."""
    return {int(p): g.set_index("date").sort_index() for p, g in dsf.groupby("permno")}


def market_calendar(dsf: pd.DataFrame, lo, hi) -> pd.DatetimeIndex:
    """The sessions: every date on which some permno in the extract has a CRSP row."""
    d = pd.DatetimeIndex(sorted(dsf["date"].unique()))
    return d[(d >= pd.Timestamp(lo)) & (d <= pd.Timestamp(hi))]


def entry_session(px_t: pd.DataFrame, a: pd.Timestamp) -> pd.Timestamp | None:
    """d_in: the target's first session strictly after A (`_announcement_row`'s rule)."""
    td = px_t.index[px_t.index > a]
    return td[0] if len(td) else None


def first_session_after(cal: pd.DatetimeIndex, d: pd.Timestamp) -> pd.Timestamp:
    i = cal.searchsorted(pd.Timestamp(d), side="right")
    if i >= len(cal):
        raise GateError(f"no session after {pd.Timestamp(d).date()} in the calendar")
    return cal[i]


def deal_window(e: pd.Series, px: dict, cal: pd.DatetimeIndex, *, failed: bool = False,
                fail_date: pd.Timestamp | None = None, lag: int = 0) -> dict | None:
    """Entry and exit sessions of one deal, or None with the reason in ['why'].

    d_in is the target's first session after A (`lag` = 1 gives shift(3): one session later).
    Exit: dlpdt for a completed deal (conversion); for a failed deal, the first session after
    the failure filing date F (decided the evening of F, closed at the close of F+1)."""
    T = px.get(int(e["permno"]))
    A = px.get(int(e["nwperm"]))
    if T is None or A is None:
        return {"why": "no CRSP prices for a party"}
    a = pd.Timestamp(e["ann"])
    d_in = entry_session(T, a)
    for _ in range(lag):
        d_in = entry_session(T, d_in) if d_in is not None else None
    if d_in is None:
        return {"why": "no target session after A"}
    if failed:
        exit_ = first_session_after(cal, fail_date)
    else:
        exit_ = pd.Timestamp(e["dlpdt"])
        if pd.isna(exit_) or exit_ not in cal:
            return {"why": "payment date not a session"}
        if d_in >= pd.Timestamp(e["dlstdt"]):
            return {"why": "entry on or after the target's last session"}
    if d_in not in cal or exit_ not in cal:
        return {"why": "entry or exit outside the calendar"}
    i_in, i_ex = cal.get_loc(d_in), cal.get_loc(exit_)
    if i_ex - 2 < i_in - 1:
        return {"why": "exit before the first earned session"}
    return {"d_in": d_in, "exit": exit_, "first": cal[i_in - 1], "last": cal[i_ex - 2], "why": None}


def returns_matrix(px: dict, cal: pd.DatetimeIndex, deals: pd.DataFrame) -> pd.DataFrame:
    """R: CRSP `ret` on the calendar for every party, with each completed deal's delisting
    return booked on its payment-date row for the target (§6.1). Missing stays NaN."""
    perms = sorted(set(deals["permno"].astype(int)) | set(deals["nwperm"].astype(int)))
    R = pd.DataFrame({p: px[p]["ret"].reindex(cal) for p in perms if p in px}, index=cal)
    completed = ~deals["failed"].astype(bool) if "failed" in deals else pd.Series(True, index=deals.index)
    for e in deals[completed].itertuples():
        if pd.isna(e.dlret) or pd.isna(e.dlpdt) or pd.Timestamp(e.dlpdt) not in cal:
            continue
        p, t = int(e.permno), pd.Timestamp(e.dlpdt)
        if t < pd.Timestamp(e.dlstdt):
            raise GateError(f"{e.ticker}: payment date before the last session")
        base = R.at[t, p]
        R.at[t, p] = (1 + base) * (1 + float(e.dlret)) - 1 if pd.notna(base) else float(e.dlret)
    return R


def hold_gaps(R: pd.Series, a: pd.Timestamp, b: pd.Timestamp, spanned_until: tuple | None = None) -> str | None:
    """§6.3's guard on one leg's earned sessions (a, b]: None if every NaN is a gap of at most
    `merger_pairs.MAX_GAP` sessions that a later finite return in the window spans, or lies in
    (dlstdt, dlpdt) for a target whose delisting return is booked at `spanned_until`.
    Otherwise the reason (the deal is excluded and counted; nothing is filled)."""
    w = R.loc[(R.index > a) & (R.index <= b)]
    if w.empty:
        return "no earned session"
    nan = w.isna()
    if spanned_until is not None:
        nan &= ~((w.index > spanned_until[0]) & (w.index < spanned_until[1]))
    if not nan.any():
        return None
    if nan.iloc[-1]:
        return "missing return on the leg's last earned session"
    run = nan.astype(int).groupby((~nan).cumsum()).sum().max()
    if run > mp.MAX_GAP:
        return f"a gap of {run} sessions > {mp.MAX_GAP}"
    return None


# =========================================================================== per-deal pricing

def price_completed(e: pd.Series, px: dict, lag: int = 0) -> dict:
    """The published buy-and-hold pair, entry at the close of A+1 (`lag` = 1: A+2, shift(3)),
    through `merger_pairs._announcement_row` unchanged."""
    a = pd.Timestamp(e["ann"])
    T = px.get(int(e["permno"]))
    for _ in range(lag):
        if T is None:
            break
        nxt = entry_session(T, a)
        a = nxt if nxt is not None else a
    skips: dict = {}
    rec = mp._announcement_row(e, a, {}, px, skips, stock_codes=UNIVERSE_CODES)
    rec["skip"] = next(iter(skips), None)
    return rec


def price_failed(e: pd.Series, px: dict, cal: pd.DatetimeIndex, fail_date: pd.Timestamp) -> dict:
    """A failed deal: $1 long target / $1 short acquirer from the close of A+1 to the close of
    F+1, both traded out (4 units), `merger_pairs.window_return` on each leg."""
    w = deal_window(e, px, cal, failed=True, fail_date=fail_date)
    if w is None or w["why"]:
        return {"pair": np.nan, "why": (w or {}).get("why", "no window")}
    rt, _, st = mp.window_return(px[int(e["permno"])], w["d_in"], w["exit"])
    ra, _, sa = mp.window_return(px[int(e["nwperm"])], w["d_in"], w["exit"])
    return {"pair": rt - ra, "status": st if st != "ok" else sa, "d_in": w["d_in"], "exit": w["exit"], "why": None}


def control1(e: pd.Series, px: dict, d_in: pd.Timestamp, end_t: pd.Timestamp) -> dict:
    """Control 1 (§8.2): the identical pair over a window of the same length in target sessions
    (reading R3), ending CTRL_LAG target sessions before the real entry d_in."""
    T, A = px[int(e["permno"])], px[int(e["nwperm"])]
    td = T.index
    L = int(((td > d_in) & (td <= end_t)).sum())
    i_in = td.get_loc(d_in)
    if i_in - CTRL_LAG - L < 0:
        return {"ctrl": np.nan, "why": "window precedes the target's listing"}
    c1, c0 = td[i_in - CTRL_LAG], td[i_in - CTRL_LAG - L]
    if c0 not in A.index or c1 not in A.index:
        return {"ctrl": np.nan, "why": "window precedes the acquirer's listing or it did not trade"}
    ct, _, _ = mp.window_return(T, c0, c1)
    ca, _, _ = mp.window_return(A, c0, c1)
    return {"ctrl": ct - ca, "c0": c0, "c1": c1, "L": L, "why": None if np.isfinite(ct - ca) else "unpriced"}


def adv63(s: pd.DataFrame, before: pd.Timestamp) -> float:
    """Mean of price x volume over the 63 sessions ending the session before `before`."""
    w = s.loc[s.index < before].tail(ADV_SESSIONS)
    if len(w) < ADV_SESSIONS:
        return np.nan
    return float((w["prc"] * w["vol"]).mean())


def control2_candidates(e: pd.Series, nm: pd.DataFrame, cal: pd.DatetimeIndex, window: dict,
                        excluded: set) -> pd.DataFrame:
    """Control 2's name-based candidate pool (§8.2) before the price, EDGAR and holdout tests:
    CEF permnos (share code 14/44), not a party to this deal, whose name in force on A has the
    target's first CRSP name word and the target's segment, and whose name records span the
    window from A-252 sessions to exit+21."""
    a = pd.Timestamp(e["ann"])
    word = str(e["comnam"]).split()[0]
    lo = cal[max(cal.searchsorted(a) - CTRL2_PRE, 0)]
    hi = cal[min(cal.get_loc(window["exit"]) + CTRL2_POST, len(cal) - 1)]
    cef = nm[nm["shrcd"].isin(ce.CEF_SHRCD)]
    at = cef[(cef["namedt"] <= a) & (cef["nameendt"] >= a)]
    at = at[at["comnam"].str.split().str[0] == word]
    at = at[at["comnam"].map(mp.classify) == e["seg"]]
    span = cef.groupby("permno").agg(first=("namedt", "min"), last=("nameendt", "max"))
    at = at[~at["permno"].isin([int(e["permno"]), int(e["nwperm"])]) & ~at["permno"].isin(excluded)]
    ok = at["permno"].map(span["first"]) <= window["d_in"]
    ok &= at["permno"].map(span["last"]) >= window["exit"]
    return at[ok].drop_duplicates("permno").assign(lo=lo, hi=hi)


def pick_control2(e: pd.Series, cands: pd.DataFrame, px: dict, window: dict, cikmap: dict,
                  episodes: pd.DataFrame, holdout_windows: pd.DataFrame, cal: pd.DatetimeIndex) -> dict:
    """The control-2 fund: of the candidates with prices across the whole window, no merger
    episode from A-252 sessions to exit+21 (by CIK; reading R4), and no name- or time-holdout
    deal overlapping the window, the nearest 63-session ADV to the target's (log distance;
    ties by the lower permno)."""
    T = px[int(e["permno"])]
    a = pd.Timestamp(e["ann"])
    adv_t = adv63(T, a)
    why: dict[str, int] = {}
    keep = []
    for c in cands.itertuples():
        p = int(c.permno)
        s = px.get(p)
        if s is None:
            why["no CRSP prices"] = why.get("no CRSP prices", 0) + 1
            continue
        if not (window["d_in"] in s.index and pd.notna(s.at[window["d_in"], "prc"])
                and window["exit"] in s.index and pd.notna(s.at[window["exit"], "ret"])):
            why["no prices across the window"] = why.get("no prices across the window", 0) + 1
            continue
        cik = cikmap.get(p)
        if cik is None:
            why["no EDGAR CIK (cannot check merger filings)"] = why.get("no EDGAR CIK (cannot check merger filings)", 0) + 1
            continue
        ep = episodes[episodes["cik"] == cik]
        if ((ep["first_date"] <= c.hi) & (ep["last_date"] >= c.lo)).any():
            why["a merger episode in the window"] = why.get("a merger episode in the window", 0) + 1
            continue
        hw = holdout_windows[(holdout_windows["permno"] == p) | (holdout_windows["nwperm"] == p)]
        if ((hw["d_in"] <= window["exit"]) & (hw["exit"] >= window["d_in"])).any():
            why["a holdout deal overlaps"] = why.get("a holdout deal overlaps", 0) + 1
            continue
        adv_c = adv63(s, a)
        if not (np.isfinite(adv_c) and adv_c > 0 and np.isfinite(adv_t) and adv_t > 0):
            why["no 63-session ADV"] = why.get("no 63-session ADV", 0) + 1
            continue
        keep.append((abs(np.log(adv_c / adv_t)), p))
    if not keep:
        return {"permno": None, "why": why}
    keep.sort()
    return {"permno": keep[0][1], "why": why}


def control2_pair(e: pd.Series, px: dict, cpermno: int, window: dict) -> float:
    """Long the control fund / short the same acquirer over (d_in, exit], both traded out."""
    rc, _, _ = mp.window_return(px[cpermno], window["d_in"], window["exit"])
    ra, _, _ = mp.window_return(px[int(e["nwperm"])], window["d_in"], window["exit"])
    return rc - ra


# =========================================================================== the sleeve

def legs_and_conversions(deals: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Each priced deal gives a target leg (+w) and an acquirer leg (-w), w = 1/n_g with n_g the
    group's priced deals in this set (reading R2). A completed deal ends in a conversion on the
    session after its last decision row; a failed deal ends in a trade."""
    d = deals.copy()
    d["w"] = 1.0 / d.groupby("group")["permno"].transform("count")
    legs = pd.concat([
        pd.DataFrame({"permno": d["permno"].astype(int), "first": d["first"], "last": d["last"],
                      "weight": d["w"], "ann": d["ann"]}),
        pd.DataFrame({"permno": d["nwperm"].astype(int), "first": d["first"], "last": d["last"],
                      "weight": -d["w"], "ann": d["ann"]})], ignore_index=True)
    conv = d[~d["failed"].astype(bool)][["permno", "nwperm", "last", "w", "exit"]].rename(
        columns={"permno": "target", "nwperm": "acquirer"})
    return legs, conv


def cap_rows(H: pd.DataFrame, cap: float) -> tuple[pd.DataFrame, pd.Series]:
    """`_cap_gross` (the sleeve's own) applied row by row: (capped H, scale factor per row)."""
    from src.deploy.sleeves.cef_discount import _cap_gross
    out, f = [], []
    for _, row in H.iterrows():
        if row.abs().sum() == 0:
            out.append(row)
            f.append(1.0)
            continue
        w, s = _cap_gross(row, cap)
        out.append(w)
        f.append(s)
    return pd.DataFrame(out, index=H.index, columns=H.columns), pd.Series(f, index=H.index)


def sleeve(deals: pd.DataFrame, R: pd.DataFrame, cal: pd.DatetimeIndex, *, k: float | None, cap: float | None,
           vol_target: float) -> dict:
    """Raw, sized and tradable sleeves (§6.2) on `evaluate()` (shift(2)), with event turnover.

    `k` None: estimate it here, k = vol_target / sigma_fit, sigma_fit the raw sleeve's
    annualised daily gross P&L sd from its first position (the fit). Given: use it (frozen,
    the holdout). The cap is `max_gross_stress`, row by row through `_cap_gross`."""
    legs, conv = legs_and_conversions(deals)
    H = bf.event_hold(legs, cal)
    if H.iloc[0].abs().sum() != 0:
        raise AssertionError("the calendar must start before the first position")
    Rh = R.reindex(index=cal, columns=H.columns)
    raw = bf.evaluate(H, Rh)
    # "From its first position" (§6.2): the first decision row with a weight. The P&L on that row
    # and the fill row is zero by shift(2); starting here keeps the entry trade in the turnover.
    first = H.abs().sum(axis=1).gt(0).idxmax()
    pnl_raw = raw["pnl"].loc[first:]
    sigma = float(pnl_raw.std() * np.sqrt(252))
    k_used = vol_target / sigma if k is None else float(k)
    Hs = H * k_used
    if cap is not None:
        Ht, f = cap_rows(Hs, cap)
    else:
        Ht, f = Hs, pd.Series(1.0, index=H.index)
    res = bf.evaluate(Ht, Rh)
    pnl = res["pnl"].loc[first:]
    if (pnl.abs().between(0, 1e-300, inclusive="neither")).any():   # DG-E1-6: no denormal P&L
        raise AssertionError("a denormal-like P&L value (the numexpr fault signature)")
    C = []
    for c in conv.itertuples():
        row = cal[cal.get_loc(c.last) + 1]
        w_t = float(Ht.at[c.last, c.target])
        if not w_t > 0:
            raise AssertionError(f"{c.target}: no long weight held into its conversion")
        resid = w_t * abs(float(Rh.at[c.exit, c.target]) - float(Rh.at[c.exit, c.acquirer]))
        C.append({"row": row, "target": c.target, "acquirer": c.acquirer, "weight": w_t, "residual": resid})
    turn = bf.event_turnover(Ht, pd.DataFrame(C, columns=["row", "target", "acquirer", "weight", "residual"]))
    on = H.loc[first:].abs().sum(axis=1).gt(0)
    return {"H": Ht, "pnl": pnl, "pnl_raw": pnl_raw, "turn": turn.loc[first:], "sigma_raw": sigma, "k": k_used,
            "cap_binding_share": float((f.loc[first:][on] < 1).mean()) if on.any() else 0.0,
            "first": first, "conversions": pd.DataFrame(C), "harness_turn": raw["turn_series"].loc[first:]}


# =========================================================================== statistics

def group_boot(v: pd.Series, groups: pd.Series, reps: int = REPS, seed: int = SEED) -> dict:
    """Groups drawn with replacement (one board decision is the unit); the deal mean and median
    of each draw. Returns 95% intervals and the share of draws with mean <= 0."""
    rng = np.random.default_rng(seed)
    gl = {g: s.values for g, s in v.groupby(groups.values)}
    keys = list(gl)
    means, meds = np.empty(reps), np.empty(reps)
    for i in range(reps):
        draw = np.concatenate([gl[keys[j]] for j in rng.integers(0, len(keys), len(keys))])
        means[i], meds[i] = draw.mean(), np.median(draw)
    return {"mean_lo": float(np.percentile(means, 2.5)), "mean_hi": float(np.percentile(means, 97.5)),
            "median_lo": float(np.percentile(meds, 2.5)), "median_hi": float(np.percentile(meds, 97.5)),
            "p_mean_le_0": float((means <= 0).mean())}


def deal_stats(v: pd.Series, groups: pd.Series, units: pd.Series | None = None, boot: bool = True) -> dict:
    """Per-deal gross statistics, the grid beside them (net = gross - c x units, labelled), the
    one-observation-per-group view and the group bootstrap."""
    v = v.astype(float)
    if v.dropna().empty:
        raise ValueError("deal_stats on an empty sample: a figure with N = 0 is not a figure")
    gm = v.groupby(groups.values).mean()
    out = {"n": int(len(v)), "groups": int(groups.nunique()), "median": float(v.median()), "mean": float(v.mean()),
           "frac_pos": float((v > 0).mean()), "clustered_t": mp.clustered_t(v, groups),
           "group_level": {"n": int(len(gm)), "median": float(gm.median()), "mean": float(gm.mean()),
                           "t": float(gm.mean() / gm.std(ddof=1) * np.sqrt(len(gm))) if len(gm) > 1 else np.nan}}
    if units is not None:
        out["net_median"] = {f"{c}bp": float((v - c / 1e4 * units).median()) for c in GRID_BP}
        out["net_mean"] = {f"{c}bp": float((v - c / 1e4 * units).mean()) for c in GRID_BP}
    if boot and len(gm) > 1:
        out["group_boot"] = group_boot(v, groups)
    return out


def control_kills(ctrl_median: float, treat_median: float) -> bool:
    """§8.2: KILL if the control's median >= 1/2 the treatment's, same sign."""
    if not (np.isfinite(ctrl_median) and np.isfinite(treat_median)) or treat_median == 0:
        return True
    return bool(np.sign(ctrl_median) == np.sign(treat_median)
                and abs(ctrl_median) >= CONTROL_FRACTION * abs(treat_median))


def stage1_passes(median: float, t: float) -> bool:
    return bool(median > MEDIAN_KILL and t >= T_KILL)


def f_max(m: float, D: float) -> dict:
    """§5.3: f_be = (m - 2 x 15bp) x 360 / (1.02 x D), annual; f_max = 1/2 f_be. Report-only
    (amendment 1). The collateral mark-up and day count are band_frontier's."""
    f_be = (m - 2 * DECIDING_BP / 1e4) * bf.BORROW_DAY_COUNT / (bf.BORROW_COLLATERAL_MARKUP * D)
    return {"m": m, "D_days": D, "f_be_pct": 100 * f_be, "f_max_pct": 100 * FMAX_MARGIN * f_be}


def hac(y: pd.Series, X: pd.DataFrame, lags: int = NW_L):
    import statsmodels.api as sm
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    f = sm.OLS(d["y"], sm.add_constant(d.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return f, len(d)


def dimson(y: pd.Series, X: pd.DataFrame, cols) -> dict:
    """Each factor at t and t-1 (on the factor's own calendar), betas summed, HAC(21). The P&L is
    the tradable sleeve, already at the vol target, so the betas need no scaling."""
    cols = list(cols)
    Z = pd.concat([X[cols].reindex(y.index), X[cols].shift(1).reindex(y.index).add_suffix("_l1")], axis=1)
    f, n = hac(y, Z)
    betas = {c: float(f.params[c] + f.params[c + "_l1"]) for c in cols}
    return {"n": n, "alpha_ann": float(f.params["const"] * 252), "alpha_t": float(f.tvalues["const"]),
            "r2": float(f.rsquared), "betas": betas, "max_abs_beta": max(abs(v) for v in betas.values())}


def d4_passes(r: dict) -> bool:
    return bool(r["alpha_t"] >= D4_ALPHA_T and r["max_abs_beta"] <= D4_MAX_BETA)


def factor_frame(px: dict, etf_perm: dict) -> pd.DataFrame:
    """French FF5 + UMD (daily, decimals) and MUB, IEF, HYG CRSP total returns in excess of the
    French bill. Raises naming any missing input; nothing is filled."""
    if not FF_CACHE.exists():
        raise GateError(f"{FF_CACHE.relative_to(REPO)} is missing: `python3 scripts/data/fetch_ff_factors.py`")
    ff = pd.read_parquet(FF_CACHE)
    ff["date"] = pd.to_datetime(ff["date"])
    ff = ff.set_index("date").sort_index()
    X = ff[list(FF6)].copy()
    for tk in ETF_TICKERS:
        p = etf_perm[tk]
        if p not in px:
            raise GateError(f"no CRSP prices for {tk} (permno {p})")
        X[tk] = px[p]["ret"].reindex(X.index) - ff["rf"]
    return X


def dsr(pnl: pd.Series, n: int = N_EVENTS) -> dict:
    from scripts.cef.validate import _dsr
    sr = float(pnl.mean() / pnl.std() * np.sqrt(252))
    sk, ku = float(pnl.skew()), float(pnl.kurt() + 3.0)
    d, sr0, emax = _dsr(sr, len(pnl), sk, ku, n)
    return {"sr": sr, "T": int(len(pnl)), "skew": sk, "kurt": ku, "N": n, "dsr": float(d), "sr0": float(sr0),
            "e_max": float(emax), "passes": bool(d > DSR_PASS)}


def sleeve_stats(s: dict) -> dict:
    """`_stats` on the tradable sleeve with EVENT turnover, the HAC t's and the bootstraps."""
    from scripts.cef import w4_artifacts as w4
    st = bf._stats(s["pnl"], s["turn"])
    out = {"gross_sr": float(st["sr"]), "ann": float(st["ann"]), "vol": float(st["vol"]), "turn": float(st["turn"]),
           "net_sr": {f"{c}bp": float(v) for c, v in zip(GRID_BP, st["nets"])},
           "net_ann": {f"{c}bp": float(st["ann"] - st["turn"] * c / 1e4) for c in GRID_BP},
           "nw_t": {f"L{NW_L}": float(w4.nw_t(s["pnl"], NW_L)), f"L{NW_L_LONG}": float(w4.nw_t(s["pnl"], NW_L_LONG))},
           "harness_turn": float(s["harness_turn"].mean() * 252)}
    for b in (BOOT_BLOCK, BOOT_BLOCK_ALT):
        bt = w4.stationary_boot(s["pnl"], mean_block=b, reps=REPS, seed=SEED)
        out[f"boot_block{b}"] = {"mean_lo": float(bt["lo_mean"]) * 252, "mean_hi": float(bt["hi_mean"]) * 252,
                                 "sr_lo": float(bt["lo_sr"]), "sr_hi": float(bt["hi_sr"])}
    out["flips_sign_across_grid"] = bool(len({np.sign(v) for v in out["net_ann"].values()} | {np.sign(out["ann"])}) > 1)
    return out


def borrow_table(s: dict, sched: dict) -> dict:
    """Borrow under each schedule, in its OWN column (H4; amendment 1: never in a verdict).
    `sched` maps a label to a fee frame (percent) or a string saying why it is not computed."""
    out = {}
    for lab, fee in sched.items():
        if isinstance(fee, str):
            out[lab] = {"not_computed": fee}
            continue
        b = bf.borrow_charge(s["H"], fee)
        c = b["cost"].loc[s["first"]:]
        out[lab] = {"ann_cost": float(c.mean() * 252), "covered_share": float(b["covered_share"]),
                    "net_ann_after_borrow_15bp": float(s["pnl"].mean() * 252 - s["turn"].mean() * 252 * DECIDING_BP / 1e4
                                                       - c.mean() * 252)}
    return out


def break_even_fee(s: dict) -> float:
    """The flat annual fee (percent) at which the sleeve's net at 15bp reaches zero (§7)."""
    one = pd.DataFrame(1.0, index=s["H"].index, columns=s["H"].columns)
    per1 = float(bf.borrow_charge(s["H"], one)["cost"].loc[s["first"]:].mean() * 252)
    net15 = float(s["pnl"].mean() * 252 - s["turn"].mean() * 252 * DECIDING_BP / 1e4)
    return net15 / per1 if per1 > 0 else np.nan


def flat_fee(H: pd.DataFrame, pct: float) -> pd.DataFrame:
    return pd.DataFrame(float(pct), index=H.index, columns=H.columns)


def b_med_fee() -> dict:
    """B-med: the median IBKR fee of universe MUNI acquirers on the last date before their first
    N-14 8C merger filing, re-measured now by G1a's H1b method (g1a_shortability.py)."""
    from scripts.events.g1a_shortability import last_before
    bh = pd.read_parquet(BORROW)
    bh["date"] = pd.to_datetime(bh["date"])
    first_fee = bh.dropna(subset=["fee_rate_pct"]).groupby("ticker")["date"].min()
    ep = pd.read_csv(EPISODES)
    ep = ep[(ep["kind"] == "merger") & ep["forms"].str.contains("N-14 8C", regex=False)].copy()
    ep["first_date"] = pd.to_datetime(ep["first_date"])
    ep["tk"] = ep["ticker_now"].fillna("").str.split(";")
    ep = ep.explode("tk")
    ep = ep[ep["tk"].isin(first_fee.index) & (ep["first_date"] > ep["tk"].map(first_fee))]
    ep = ep[~ep["first_form"].str.endswith("/A")]
    bhp = bh.pivot(index="date", columns="ticker", values="fee_rate_pct").sort_index()
    fees = []
    for _, e in ep.iterrows():
        if mp.classify(str(e["company_last"]).upper()) != "muni":
            continue
        s = bhp[e["tk"]].dropna()
        fd = last_before(s.index, e["first_date"])
        if fd is not None:
            fees.append(float(s.loc[fd]))
    if not fees:
        raise GateError("B-med: no universe muni acquirer has a fee before its first filing")
    return {"n": len(fees), "median_pct": float(np.median(fees)), "panel_last": str(bh["date"].max().date())}


def b_meas_fee(H: pd.DataFrame, nm: pd.DataFrame) -> pd.DataFrame:
    """B-meas: the measured FEE_RATE series where the column is a universe name, inside
    2021-09-13 .. the panel's last date; NaN elsewhere (`borrow_charge` reports it uncovered)."""
    up = ce.universe_permnos(nm)
    perm2tk = {p: tk for tk, ps in up.items() for p in ps}
    bh = pd.read_parquet(BORROW)
    bh["date"] = pd.to_datetime(bh["date"])
    bhp = bh.pivot(index="date", columns="ticker", values="fee_rate_pct").sort_index()
    F = pd.DataFrame(np.nan, index=H.index, columns=H.columns)
    for p in H.columns:
        tk = perm2tk.get(int(p))
        if tk in bhp:
            s = bhp[tk].reindex(H.index)
            F[p] = s.where((H.index >= BORROW_MEAS_START) & (H.index <= bhp.index.max()))
    return F


def era_rows(deals: pd.DataFrame, s: dict | None) -> list[dict]:
    """H5 eras: deals by fill date (reading R5) and the sleeve's turnover per era, with the
    across-era turnover sd/mean."""
    rows = []
    for lab, a, b in ERAS:
        d = deals[(deals["d_in"] >= a) & (deals["d_in"] <= b)]
        r = {"era": lab, "deals": int(len(d))}
        if len(d) > 1:
            r.update(median=float(d["pair"].median()), clustered_t=mp.clustered_t(d["pair"], d["group"]))
        if s is not None:
            t = s["turn"].loc[a:b]
            r["turn"] = float(t.mean() * 252) if len(t) else np.nan
        rows.append(r)
    if s is not None:
        tv = np.array([r["turn"] for r in rows if np.isfinite(r.get("turn", np.nan))])
        rows.append({"era": "turnover sd/mean", "value": float(tv.std(ddof=1) / tv.mean()) if len(tv) > 1 else np.nan})
    return rows


def capacity(deals: pd.DataFrame, s: dict, px: dict) -> dict:
    """§6.5, reported only: each leg's entry dollars at $100k / $1m / $10m against its 63-session
    ADV ending the session before A, and the capital at which the median deal's larger leg
    reaches the 5% guard."""
    parts = []
    for e in deals.itertuples():
        w = abs(float(s["H"].at[e.first, e.permno])) if e.first in s["H"].index else np.nan
        adv_t, adv_a = adv63(px[int(e.permno)], e.ann), adv63(px[int(e.nwperm)], e.ann)
        parts.append(max(w / adv_t if adv_t > 0 else np.nan, w / adv_a if adv_a > 0 else np.nan))
    per_dollar = float(np.nanmedian(parts))
    return {"median_participation": {f"${c:,.0f}": c * per_dollar for c in CAPITALS},
            "capital_at_guard": PARTICIPATION_GUARD / per_dollar if per_dollar > 0 else np.nan}


# =========================================================================== Stage 0

def _identity_check_1(x_fit: pd.DataFrame, px: dict, dates: pd.DataFrame) -> dict:
    """DG-E1-7 check 1 (reading R1)."""
    ed, _ = mp.announcement_sample_edgar(x_fit, px, dates)
    trial = []
    for e in mp.pairable_events(x_fit).itertuples(index=False):
        e = pd.Series(e._asdict())
        d = dates.set_index("permno").loc[int(e["permno"])]
        if pd.isna(d["ann_date"]):
            trial.append(np.nan)
            continue
        e["ann"] = pd.Timestamp(d["ann_date"])
        trial.append(price_completed(e, px).get("pair_A1_to_close", np.nan))
    a = ed["pair_A1_to_close"].to_numpy(float)
    b = np.array(trial, float)
    same_nan = bool((np.isnan(a) == np.isnan(b)).all())
    diff = float(np.nanmax(np.abs(a - b))) if np.isfinite(a).any() else np.nan
    out = {"deals": int(len(ed)), "priced": int(np.isfinite(a).sum()), "max_abs_diff_trial_vs_published_code": diff,
           "nan_pattern_equal": same_nan, "passes_1e-12": bool(same_nan and diff <= 1e-12)}
    if PUBLISHED_DEALS.exists():
        pub = pd.read_csv(PUBLISHED_DEALS, dtype=str, keep_default_na=False)
        mine = ed.assign(pair=ed["pair_A1_to_close"].map(lambda v: "" if pd.isna(v) else f"{v:.8g}"))
        j = pub.merge(mine[["permno", "pair"]].astype(str), on="permno", how="outer", indicator=True)
        out["published_csv_rows"] = int(len(pub))
        out["published_csv_equal_at_8g"] = bool((j["_merge"] == "both").all()
                                                and (j["pair_A1_to_close"] == j["pair"]).all())
    else:
        out["published_csv_equal_at_8g"] = None
    p = ed.dropna(subset=["pair_A1_to_close"]).copy()
    p["group"] = p["nwperm"].astype(str) + "@" + p["ann"]
    summ = json.loads(PUBLISHED_SUMMARY.read_text())
    out["published_aggregates_equal"] = bool(
        mp.grid_table(p["pair_A1_to_close"], p["group"]) == summ["all"]
        and all(mp.grid_table(g["pair_A1_to_close"], g["group"]) == summ["by_class"][c] for c, g in p.groupby("cls")))
    return out


def _identity_check_2(x_fit: pd.DataFrame, px: dict, dates: pd.DataFrame, cal: pd.DatetimeIndex) -> dict:
    """DG-E1-7 check 2 (printed, not a gate): each published deal as a one-deal constant-weight
    sleeve through `event_hold` + `evaluate()`, its summed P&L beside the buy-and-hold pair."""
    y = attach_dates(x_fit, dates)
    diffs, excluded = [], {}
    for _, e in y.iterrows():
        rec = price_completed(e, px)
        bh = rec.get("pair_A1_to_close", np.nan)
        if not np.isfinite(bh):
            continue
        w = deal_window(e, px, cal)
        if w is None or w["why"]:
            excluded[w["why"]] = excluded.get(w["why"], 0) + 1
            continue
        rec1 = e.to_dict()
        rec1.update(failed=False, first=w["first"], last=w["last"], exit=w["exit"], group="g")
        one = pd.DataFrame([rec1])
        R = returns_matrix(px, cal, one)
        span = (pd.Timestamp(e["dlstdt"]), pd.Timestamp(e["dlpdt"]))
        g1 = hold_gaps(R[int(e["permno"])], w["d_in"], w["exit"], span)
        g2 = hold_gaps(R[int(e["nwperm"])], w["d_in"], w["exit"])
        if g1 or g2:
            excluded[g1 or g2] = excluded.get(g1 or g2, 0) + 1
            continue
        legs, _ = legs_and_conversions(one)
        H = bf.event_hold(legs, cal)
        pnl = bf.evaluate(H, R.reindex(columns=H.columns))["pnl"]
        diffs.append(float(pnl.sum()) - bh)
    d = np.abs(np.array(diffs))
    if (d[(d > 0)] < 1e-300).any():
        raise AssertionError("DG-E1-6: a denormal-like difference")
    return {"deals": int(len(d)), "excluded": excluded, "median_abs_diff": float(np.median(d)),
            "p95_abs_diff": float(np.percentile(d, 95))}


def stage0(args) -> int:
    """Stage 0 (§10, §13). Every gate is evaluated that can be; any failure is a HALT. No E1
    statistic is computed here: the identity checks re-derive published figures, and the
    quality screen and the bridging check are about the data."""
    log: list[str] = []

    def say(s=""):
        print(s)
        log.append(s)

    run = datetime.now(timezone.utc).isoformat(timespec="seconds")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    say(f"E1 STAGE 0 -- {run} -- HEAD {head} -- {PREREG.relative_to(REPO)}")
    gates: dict[str, dict] = {}
    flags: list[dict] = []

    # ---------------------------------------------------------------- DG-E1-6
    say("\n[DG-E1-6] pandas compute.use_numexpr: " + str(pd.get_option("compute.use_numexpr")))
    gates["DG-E1-6"] = {"status": "PASS" if pd.get_option("compute.use_numexpr") is False else "FAIL",
                        "detail": "numexpr off; the denormal assertion runs on every P&L built (identity check 2 here)"}

    # ---------------------------------------------------------------- deals and counts
    nm, dl = crsp_tables()
    man = ce.manifest()
    x = deal_table(nm, dl)
    t, ok = counts_vs_prereg(x)
    say(f"\n[COUNTS] deals and acquirer x completion groups by set, beside the pre-registration's "
        f"({PREREG_COUNTS.name}); CRSP names pulled {man['dsenames']['pulled_utc']}, delistings "
        f"{man['dsedelist']['pulled_utc']}")
    say(t.to_string())
    say(f"  identical to amendment 4's counts ({UNIVERSE_COUNTS.name}): {ok}; 331 deals by set: "
        f"{x.loc[x['dlstcd'] == 331, 'part'].value_counts().to_dict()}")
    if not ok:
        gates["COUNTS"] = {"status": "FAIL", "detail": f"the deal table differs from {UNIVERSE_COUNTS.name}"}

    # ---------------------------------------------------------------- DG-E1-2
    fd = load_fit_dates(x)
    xf_all = attach_dates(x[x["part"] == FIT_SET], fd)
    d331 = dates_331()
    need331 = x[(x["dlstcd"] == 331) & x["part"].isin((FIT_SET,) + HOLDOUT_SETS)]
    undated331 = sorted(set(need331["ticker"]) - set(need331.loc[need331["permno"].isin(d331["permno"]), "ticker"]))
    say(f"\n[DG-E1-2] fit set: {len(fd)} deals with a date row ({FIT_DATES.name} for 231, {DATES_331.name} for 331); "
        f"date basis {fd['date_basis'].value_counts().to_dict()}")
    say(f"  amendment 4: {len(need331)} 331 deals in the fit and holdouts; without a date row: {len(undated331)} "
        f"({', '.join(undated331)})" + (" -> the team lead runs `fetch-edgar --amendment4`" if undated331 else ""))
    u331 = d331[d331["ann_date"].isna() & d331["permno"].isin(need331["permno"])].merge(
        need331[["permno", "part", "seg"]], on="permno", how="left")
    if len(u331):
        say("  amendment 4's 331 deals undatable by the unchanged rule (excluded and counted, §13 DG-E1-2): "
            + "; ".join(f"{r.ticker} -> {r.a_ticker}, completed {r.completion}, {r.part}, {r.seg}: {r.why_undated}"
                        for r in u331.itertuples()))
    fit_groups = xf_all[xf_all["ann"].notna()].groupby("seg")["group"].nunique().to_dict()
    say(f"  fit deals dated: {int(xf_all['ann'].notna().sum())} of {len(xf_all)}")
    say(f"  fit groups (acquirer x announcement date) by segment: {fit_groups}")
    if HOLDOUT_DATES.exists():
        xh = x[x["part"].isin(HOLDOUT_SETS)]
        hd = pd.concat([pd.read_csv(HOLDOUT_DATES), d331[d331["permno"].isin(xh["permno"])]], ignore_index=True)
        hold_ok = (set(hd["permno"].astype(int)) == set(xh.loc[xh["dlstcd"] == 231, "permno"].astype(int))
                   | set(d331["permno"].astype(int)) & set(xh["permno"].astype(int))) and not hd["permno"].duplicated().any()
        und = hd[hd["ann_date"].isna()].merge(xh[["permno", "part", "seg"]], on="permno", how="left")
        # §13: "every deal dated, or counted as undatable and excluded". Undatable means the
        # unchanged rule found no candidate or none passed its text test (or a name match
        # failed); a document the cache lacked would have raised in `date_deals`.
        und_ok = bool((und["why_undated"].notna() | und["t_status"].ne("matched")).all())
        yh = attach_dates(xh, hd)
        dated = yh[yh["ann"].notna()]
        basis = {s_: g["date_basis"].value_counts().to_dict() for s_, g in dated.groupby("part")}
        groups = {s_: g.groupby("seg")["group"].nunique().to_dict() for s_, g in dated.groupby("part")}
        say(f"  holdout sets: {len(hd)} deals in {HOLDOUT_DATES.name} ({_rel(HOLDOUT_DATES_SUMMARY)} is its summary); "
            f"dated {len(dated)}; undatable and excluded {len(und)}: "
            + "; ".join(f"{r.ticker} -> {r.a_ticker}, completed {r.completion}, {r.part}, {r.seg}: {r.why_undated}"
                        for r in und.itertuples()))
        say(f"  date basis by set (an N-14 date is an upper bound): {basis}")
        say(f"  holdout groups (acquirer x announcement date) by set and segment: {groups}")
        gates["DG-E1-2"] = {"status": "PASS" if (hold_ok and und_ok and not undated331) else "FAIL",
                            "detail": f"holdout dates cover the 231 holdout deals: {hold_ok}; dated {len(dated)}, "
                                      f"undatable and excluded {len(und)} ({', '.join(und['ticker'])}); amendment 4's "
                                      f"331 deals without a date row: {len(undated331)} ({', '.join(undated331)})",
                            "dated": int(len(dated)), "undatable": int(len(und)), "basis_by_set": basis,
                            "groups_by_set": groups}
    else:
        today = date.fromisoformat(args.today)
        miss, stopped = missing_documents(x, today)
        n_hold = int(x["part"].isin(HOLDOUT_SETS).sum())
        say(f"  holdout sets: {n_hold} deals; no dates file. Dating them by edgar_merger_dates.date_deals "
            f"(unchanged rule) needs {len(miss)} EDGAR document(s) the offline cache does not hold "
            f"({sum('submissions' in u for u in miss)} submissions lists); probe stopped early on "
            f"{len(stopped)} deal(s): {stopped}")
        (CACHE / "dg_e1_2_missing_urls.txt").write_text("\n".join(miss) + "\n")
        gates["DG-E1-2"] = {"status": "FAIL", "detail": f"the name- and time-holdout deals are undated: {len(miss)} "
                            "EDGAR documents are not cached and fetching needs the team lead's SEC contact "
                            "(`fetch-edgar`)", "missing_documents": len(miss)}

    # ---------------------------------------------------------------- DG-E1-3
    from scripts.events import edgar_merger_dates as emd
    client = edgar_client(online=False)
    names, _ = emd.name_table(client, date.fromisoformat(args.today))
    comp = completion_ciks(nm, dl, names)
    ep = merger_episodes()
    cen = failed_census(ep, comp)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cen.to_csv(CENSUS, index=False)
    cached = 0
    from scripts.data.edgar_client import cache_path, filing_txt_url
    for r in cen.itertuples():
        cached += int(cache_path(filing_txt_url(r.episode_cik, r.episode_accession), EDGAR_UNION).exists())
    say(f"\n[DG-E1-3] merger episodes 2009-07-01..2024-12-31: {len(ep)}; CRSP merger delistings matched to CIKs: "
        f"{comp['cik'].notna().sum()} of {len(comp)} parties ({comp['status'].value_counts().to_dict()})")
    say(f"  candidate episodes (no matched CRSP completion within {FAIL_WINDOW_DAYS} days): {len(cen)}; of them "
        f"{int(cen['window_past_crsp'].sum())} run past CRSP's last delisting; first filing cached offline: {cached}")
    say(f"  by first form: {cen['first_form'].value_counts().to_dict()}")
    say(f"  -> {CENSUS.relative_to(REPO)} (EDGAR facts only)")
    supp = supp_census(ep, comp)
    supp.to_csv(CENSUS_SUPP, index=False)
    say(f"  supplementary census (ruling 9): {len(supp)} acquirer-side episodes a completion explains "
        f"-> {_rel(CENSUS_SUPP)}; MMU 2023 (SBI -> MMU) among them: {bool((supp['episode_cik'] == 886043).any())}")
    extra = {}
    if DG3_RULINGS.exists() and READINGS.exists():
        from scripts.events import e1_failed_reading as fr
        st = fr.dg3_state(nm, dl, names, cen, supp)            # rounds merged; rulings 2-4, 10 applied; triage
        Rr, T, ex = st["R"], st["T"], st["exempt"]
        T.to_csv(OUT_DIR / "e1_failed_reading_triage.csv", index=False)
        Rr.to_csv(READINGS_RULED, index=False)
        readings, probs = check_readings(st["census"], client, readings=Rr, exempt=ex)
        adj = Rr["merge_note"].str.startswith("adjudicate") & ~ex
        if adj.any():
            probs.insert(0, f"{int(adj.sum())} deal(s) the readings disagree on: a third reading (ruling 8)")
        crsp_open = Rr["crsp_note"].str.startswith("not_completed") & (Rr["outcome"] == "") & ~ex
        trial = Rr.loc[Rr["in_trial"] == "Y"]
        say(f"  rounds merged: {Rr['round'].value_counts().to_dict()}; readings of episodes amendment 4 moved out of "
            f"the census set aside: {st['moot_rows']}; ruling 10 settled {int((Rr['ruled'] == '10').sum())} row(s) from CRSP, "
            f"and found {int(crsp_open.sum())} never completed (a third reading dates their failure)")
        say(f"  rulings applied: {int(ex.sum())} of {len(Rr)} rows cannot change the trial (ruling 5); in-trial deals "
            f"{trial['deal_id'].nunique()}: " + ", ".join(sorted(set(trial['target_ticker'] + '->' + trial['acquirer_ticker']))))
        r3f = OUT_DIR / fr.ROUNDS["r3"][2]
        if r3f.exists() and not (OUT_DIR / fr.ROUNDS["r3"][0]).exists():
            probs.append(f"round r3 (rulings 8, 10): {len(pd.read_csv(r3f))} episode(s) unread")
        if not (OUT_DIR / fr.ROUNDS["r4"][0]).exists():
            r4f = OUT_DIR / fr.ROUNDS["r4"][2]
            probs.append("round r4 (ruling 15: SBI -> MMU, NCU -> NKX in each target's own filings): "
                         + (f"{len(pd.read_csv(r4f))} fund(s) unread" if r4f.exists()
                            else "awaiting the team lead's `fetch-edgar --cik`, then freeze-r4"))
        say(f"  excluded and counted (rulings 12-15): "
            f"{Rr[Rr['excluded'] != ''].groupby('excluded')['deal_id'].nunique().to_dict()} deal ids by ruling")
        extra = {"in_trial_deals_ruled": int(trial["deal_id"].nunique()),
                 "in_trial_deal_list": sorted(set(trial["target_ticker"] + "->" + trial["acquirer_ticker"])),
                 "exempt_rows": int(ex.sum()),
                 "moot_rows": st["moot_rows"], "crsp_settled": int((Rr["ruled"] == "10").sum())}
    else:
        readings, probs = check_readings(cen, client)
    gates["DG-E1-3"] = {"status": "FAIL" if probs else "PASS", "detail": "; ".join(probs) if probs else
                        f"{len(readings)} readings, every quote re-found", "candidates": int(len(cen)),
                        "first_filing_cached": cached, "supp_episodes": int(len(supp)), **extra}
    for pr in (probs or [gates["DG-E1-3"]["detail"]]):
        say(f"  DG-E1-3: {pr}")
    failed_fit = None
    if gates["DG-E1-3"]["status"] == "PASS" and extra:
        Fd = failed_deal_rows(Rr, nm)
        failed_fit = Fd[Fd["part"] == FIT_SET].reset_index(drop=True)
        say(f"  failed deals in the trial by set: {Fd['part'].value_counts().to_dict()}; by segment: "
            f"{Fd['seg'].value_counts().to_dict()}")

    # ---------------------------------------------------------------- DG-E1-1
    etf_perm = {}
    for tk in ETF_TICKERS:
        r = nm[(nm["ticker"] == tk) & (nm["shrcd"] == 73) & (nm["nameendt"] >= FIT_START)]
        if r["permno"].nunique() != 1:
            raise GateError(f"{tk}: {r['permno'].nunique()} CRSP ETF permnos")
        etf_perm[tk] = int(r["permno"].iloc[0])
    # every fit deal's parties (231 and 331, as `stage-crsp` stages them) and the factor ETFs
    fit_perms = set(xf_all["permno"].astype(int)) | set(xf_all["nwperm"].astype(int)) | set(etf_perm.values())
    if failed_fit is not None:                  # the failed fit deals' parties too, once DG-E1-3 has passed
        fit_perms |= set(failed_fit["permno"].astype(int)) | set(failed_fit["nwperm"].astype(int))
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "fit_reader_permnos.txt").write_text("\n".join(map(str, sorted(fit_perms))) + "\n")
    xd = xf_all[xf_all["ann"].notna()]          # the dated fit deals (an undatable one is excluded, counted)
    base = set(xf_all["permno"].astype(int)) | set(xf_all["nwperm"].astype(int)) | set(etf_perm.values())
    dsf, loaded, fit_reader = fit_extract(fit_perms, base if failed_fit is not None else None)
    try:
        holdout_gate()
        hold_guard = "FAIL: the holdout reader did not refuse"
    except GateError as e:
        hold_guard = f"PASS (refuses: {str(e)[:90]})"
    # Control-2 candidate pool, by name only (the price, EDGAR and holdout tests come at stage 3):
    # every candidate must have CRSP rows in some cached extract before stage 3 can pick from it.
    pool = set()
    if dsf is not None:
        px0 = price_series(dsf)
        cal0 = market_calendar(dsf, CAL_START, FIT_END)
        for _, e in xd.iterrows():
            w = deal_window(e, px0, cal0)
            if w is None or w["why"]:
                continue
            pool |= set(control2_candidates(e, nm, cal0, w, set()).permno.astype(int))
        for _, e in (failed_fit.iterrows() if failed_fit is not None else []):
            w = deal_window(e, px0, cal0, failed=True, fail_date=e["fail_date"])
            if w is not None and not w["why"]:
                pool |= set(control2_candidates(e, nm, cal0, w, set()).permno.astype(int))
    in_cache = set()
    for f in ce.CACHE.glob("dsf_*.parquet"):
        in_cache |= set(pd.read_parquet(f, columns=["permno"])["permno"].astype(int))
    pool_missing = sorted(pool - in_cache)
    p331 = need331[need331["part"] == FIT_SET]
    a4_missing = sorted((set(p331["permno"].astype(int)) | set(p331["nwperm"].astype(int))) - in_cache)
    CACHE.mkdir(parents=True, exist_ok=True)
    A4_CRSP_PERMNOS.write_text("\n".join(map(str, a4_missing)) + ("\n" if a4_missing else ""))
    (CACHE / "control2_pool_permnos.txt").write_text("\n".join(map(str, sorted(pool))) + "\n")
    (CACHE / "control2_pool_missing_permnos.txt").write_text("\n".join(map(str, pool_missing)) + "\n")
    say(f"\n[DG-E1-1] fit reader (crsp_events.daily, cached extract only): {fit_reader}")
    say(f"  holdout reader guard: {hold_guard}")
    say(f"  factor ETFs: {sorted(etf_perm)}, one CRSP ETF permno each (share code 73)")
    say("  control-2 name pool over the dated completed fit deals"
        + (f" and the {len(failed_fit)} failed fit deals" if failed_fit is not None else "")
        + f": {len(pool)} CEF permnos; without CRSP rows in the local cache: {len(pool_missing)}"
        + ("" if failed_fit is not None else "; failed deals' parties and pools: not known until DG-E1-3"))
    say(f"  amendment 4: the 331 fit deals' parties without CRSP rows in the local cache: {len(a4_missing)}"
        + (f" -> the team lead runs `pull-crsp --permnos {_rel(A4_CRSP_PERMNOS)}`" if a4_missing else ""))
    gates["DG-E1-1"] = {"status": dg1_status(fit_reader, hold_guard, pool_missing, a4_missing, failed_fit is not None),
                        "detail": f"fit reader {fit_reader.split(':')[0]}; holdout guard {hold_guard.split(' ')[0]}; "
                                  f"control-2 pool missing {len(pool_missing)}; 331 fit parties missing {len(a4_missing)}; "
                                  + ("the failed deals' parties wait on DG-E1-3" if failed_fit is None else
                                     f"the fit reader's set ({_rel(CACHE / 'fit_reader_permnos.txt')}) includes the "
                                     f"{len(failed_fit)} failed fit deals' parties"),
                        "pool": len(pool), "pool_missing": len(pool_missing)}

    # ---------------------------------------------------------------- DG-E1-4, DG-E1-7, the quality screen
    if dsf is not None:
        px = price_series(dsf)
        cal = market_calendar(dsf, CAL_START, FIT_END)
        say(f"\n[DG-E1-4] bridging check (merger_pairs.bridging_check) on the fit parties' extract: "
            f"{mp.bridging_check(dsf[~dsf['permno'].isin(etf_perm.values())])}")
        neg = raw_prc_negative(loaded)
        neg_set = set(zip(neg["permno"].astype(int), neg["date"]))
        excl, nflag, excl_perm = {}, 0, set()
        for _, e in xd.iterrows():
            w = deal_window(e, px, cal)
            if w is None or w["why"]:
                excl[(w or {}).get("why", "no window")] = excl.get((w or {}).get("why", "no window"), 0) + 1
                continue
            one = pd.DataFrame([e]).assign(failed=False)
            R = returns_matrix(px, cal, one)
            g = hold_gaps(R[int(e["permno"])], w["d_in"], w["exit"], (pd.Timestamp(e["dlstdt"]), pd.Timestamp(e["dlpdt"]))) \
                or hold_gaps(R[int(e["nwperm"])], w["d_in"], w["exit"])
            if g:
                excl[g] = excl.get(g, 0) + 1
                excl_perm.add(int(e["permno"]))
                flags.append({"check": "DG-E1-4 hold gap", "ticker": e["ticker"], "date": str(w["d_in"].date()),
                              "detail": f"{g} (deal excluded and counted)"})
            for p, tk in ((int(e["permno"]), e["ticker"]), (int(e["nwperm"]), e["a_ticker"])):
                if (p, w["d_in"]) in neg_set:
                    nflag += 1
                    flags.append({"check": "quality screen: no closing trade on the fill day", "ticker": str(tk),
                                  "date": str(w["d_in"].date()),
                                  "detail": f"CRSP prc < 0 on d_in (deal target {e['ticker']}); report-only per §8.2"})
        unpriced = {int(e["permno"]) for _, e in xd.iterrows()
                    if not np.isfinite(price_completed(e, px).get("pair_A1_to_close", np.nan))}
        say(f"  fit deals excluded by the window or the hold guard: {excl}; the same deals the published "
            f"buy-and-hold sample leaves unpriced: {excl_perm == unpriced} ({len(unpriced)} unpriced)")
        say(f"  fill-day quality screen: {nflag} leg(s) with no closing trade on the fill day (flags written)")
        fexcl = {}
        if failed_fit is not None:              # the failed fit deals' windows and fill days
            unchecked = unpriced_failed(failed_fit, px)
            for _, e in failed_fit.iterrows():
                if f"{e['ticker']} -> {e.get('a_ticker', '')}" in unchecked:
                    continue
                w = deal_window(e, px, cal, failed=True, fail_date=e["fail_date"])
                if w is None or w["why"]:
                    why = (w or {}).get("why", "no window")
                    fexcl[why] = fexcl.get(why, 0) + 1
                    flags.append({"check": "DG-E1-4 failed-deal window", "ticker": e["ticker"],
                                  "date": str(pd.Timestamp(e["ann"]).date()), "detail": f"{why} (deal excluded and counted)"})
                    continue
                R1 = returns_matrix(px, cal, pd.DataFrame([e]))
                g = hold_gaps(R1[int(e["permno"])], w["d_in"], w["exit"]) or hold_gaps(R1[int(e["nwperm"])], w["d_in"], w["exit"])
                if g:
                    fexcl[g] = fexcl.get(g, 0) + 1
                    flags.append({"check": "DG-E1-4 hold gap", "ticker": e["ticker"], "date": str(w["d_in"].date()),
                                  "detail": f"{g} (failed deal excluded and counted)"})
                for p_, tk in ((int(e["permno"]), e["ticker"]), (int(e["nwperm"]), e.get("a_ticker", ""))):
                    if (p_, w["d_in"]) in neg_set:
                        flags.append({"check": "quality screen: no closing trade on the fill day", "ticker": str(tk),
                                      "date": str(w["d_in"].date()), "detail": "CRSP prc < 0 on d_in; report-only per §8.2"})
            say(f"  failed fit deals ({len(failed_fit)}): excluded by the window or the hold guard: {fexcl}; "
                f"unchecked (no CRSP prices yet): {unchecked}")
            gates["DG-E1-4"] = dg4_gate(excl, fexcl, unchecked)
        else:
            say("  the failed deals' windows: not known until DG-E1-3")
            gates["DG-E1-4"] = {"status": "INCOMPLETE", "detail": f"completed fit deals checked ({excl}); failed deals wait on DG-E1-3"}

        x231 = x[(x["part"] == FIT_SET) & (x["dlstcd"] == 231)]          # the published sample
        i1 = _identity_check_1(x231, px, fd[fd["permno"].isin(x231["permno"])])
        say(f"\n[DG-E1-7] identity check 1 (reading R1): {i1}")
        i2 = _identity_check_2(x231, px, fd[fd["permno"].isin(x231["permno"])], cal)
        say(f"  identity check 2 (printed, not a gate): constant-weight sleeve vs buy-and-hold per deal: "
            f"median |diff| {i2['median_abs_diff']*1e4:.2f}bp, p95 {i2['p95_abs_diff']*1e4:.2f}bp over {i2['deals']} deals; "
            f"excluded {i2['excluded']}")
        gates["DG-E1-7"] = {"status": "PASS" if (i1["passes_1e-12"] and i1["published_aggregates_equal"]
                                                 and i1.get("published_csv_equal_at_8g") is not False) else "FAIL",
                            "detail": {"check1": i1, "check2": i2}}
    else:
        gates["DG-E1-4"] = {"status": "FAIL", "detail": "no fit extract"}
        gates["DG-E1-7"] = {"status": "FAIL", "detail": "no fit extract"}

    # ---------------------------------------------------------------- DG-E1-5
    ffd = None
    if FF_CACHE.exists():
        ff = pd.read_parquet(FF_CACHE)
        ffd = (str(pd.to_datetime(ff["date"]).min().date()), str(pd.to_datetime(ff["date"]).max().date()),
               str(ff["fetched_at_utc"].iloc[0]), str(ff["crsp_vintage"].iloc[0]))
    etf_span = {}
    if dsf is not None:
        for tk, p in etf_perm.items():
            s = dsf[dsf["permno"] == p]
            inwin = s[(s["date"] >= CAL_START) & (s["date"] <= FIT_END)]
            etf_span[tk] = (str(s["date"].min().date()), str(s["date"].max().date()),
                            int(inwin["ret"].isna().sum()))   # missing returns inside the fit window
    bh = pd.read_parquet(BORROW, columns=["date"])
    b_last = str(pd.to_datetime(bh["date"]).max().date())
    say(f"\n[DG-E1-5] French FF5+UMD daily: {ffd} (first, last, fetched, CRSP vintage)")
    say(f"  CRSP ETFs (first, last, missing ret inside 2009-07..2022-12) via the fit reader: {etf_span}")
    say(f"  {BORROW.relative_to(REPO)} last date: {b_last}")
    c0 = str(CAL_START.date())
    fit_cov = bool(ffd and ffd[0] <= c0 and ffd[1] >= "2024-12-31"
                   and all(v[0] <= c0 and v[1] >= "2022-12-30" and v[2] == 0 for v in etf_span.values())
                   and len(etf_span) == 3)
    gates["DG-E1-5"] = {"status": "PASS" if fit_cov else "FAIL",
                        "detail": "French covers 2009-07..2024-12; CRSP ETFs cover the fit window, which is what "
                                  "reading R8 (ruled 2026-10-20) requires" if fit_cov else
                                  "a factor input does not cover the fit window"}

    # ---------------------------------------------------------------- k and the cap
    say("\n[k, cap] not computed: the fit sleeve's deal set needs the failed deals (DG-E1-3) and the stage-0 gates")

    # ---------------------------------------------------------------- verdict
    halts = {g: v for g, v in gates.items() if v["status"] != "PASS"}
    verdict = "STAGE 0: CLEAR" if not halts else "STAGE 0: HALT"
    say(f"\n{verdict}")
    for g in sorted(gates):
        say(f"  {g}: {gates[g]['status']} -- {gates[g]['detail'] if isinstance(gates[g]['detail'], str) else '(see above)'}")
    say("\nImplementation readings for the team lead (module docstring R1-R12) apply from Stage 1.")
    F = pd.DataFrame(flags, columns=["check", "ticker", "date", "detail"])
    F.to_csv(STAGE0_FLAGS, index=False)
    STAGE0_OUT.write_text("\n".join(log) + "\n")
    STAGE0_JSON.write_text(json.dumps({
        "run_utc": run, "head": head, "verdict": verdict, "gates": gates, "counts_equal_prereg": ok,
        "fit_groups_by_segment": fit_groups, "n_flags": int(len(F)),
        "crsp_pulled": {k: man[k]["pulled_utc"] for k in ("dsenames", "dsedelist")},
        "e1_statistics_computed": False}, indent=1, default=str) + "\n")
    print(f"\nwrote {STAGE0_OUT.relative_to(REPO)}, {STAGE0_JSON.relative_to(REPO)}, {STAGE0_FLAGS.relative_to(REPO)}")
    return 0 if verdict == "STAGE 0: CLEAR" else 2


# =========================================================================== the fit and the holdout

def fit_extract(full: set, base: set | None, reader=None) -> tuple[pd.DataFrame | None, set, str]:
    """Stage 0's read of the fit extract: (rows, the permno set they cover, DG-E1-1's reader text).

    The full set (every fit deal's parties, the failed fit deals' included, and the ETFs) must
    load, or DG-E1-1 FAILS, naming it. If it fails and `base` (the completed fit deals' parties
    and the ETFs) is given, `base` is read instead so that DG-E1-4's completed deals, -5 and -7,
    which never read a failed deal's party, are still evaluated; the text says so, and the failed
    deals whose prices are missing are counted unchecked (`unpriced_failed`, `dg4_gate`). Before
    2026-10-22 one missing party (ALD) failed all four gates with one cause."""
    reader = reader or fit_daily
    try:
        d = reader(full)
        return d, full, f"PASS: {len(full)} permnos, {len(d):,} rows, last {d['date'].max().date()} (< 2023)"
    except GateError as e:
        text = f"FAIL: {e}"
    if base is None:
        return None, full, text
    try:
        d = reader(base)
    except GateError:
        return None, full, text
    return d, base, text + f" (gates DG-E1-4/5/7 evaluated on the completed fit deals' extract, {len(base)} permnos)"


def unpriced_failed(failed_fit: pd.DataFrame, px: dict) -> list[str]:
    """The failed fit deals with a party that has no prices in `px` ("TGT -> ACQ")."""
    return [f"{e['ticker']} -> {e.get('a_ticker', '')}" for _, e in failed_fit.iterrows()
            if int(e["permno"]) not in px or int(e["nwperm"]) not in px]


def dg4_gate(excl: dict, fexcl: dict, unchecked: list) -> dict:
    """DG-E1-4 once the failed deals are known: PASS only if every failed fit deal was checked."""
    return {"status": "INCOMPLETE" if unchecked else "PASS",
            "detail": f"completed fit deals {excl}; failed fit deals {fexcl}"
                      + (f"; unchecked until their prices are pulled: {unchecked}" if unchecked else "")}


def dg1_status(fit_reader: str, hold_guard: str, pool_missing, a4_missing, failed_known: bool) -> str:
    """DG-E1-1: FAIL unless the FULL fit set loaded (a fallback read for other gates never passes
    it), the holdout reader refused, and no control-2 pool fund or 331 party lacks rows;
    INCOMPLETE while the failed deals are unknown."""
    if (not fit_reader.startswith("PASS") or not hold_guard.startswith("PASS") or len(pool_missing)
            or len(a4_missing)):
        return "FAIL"
    return "PASS" if failed_known else "INCOMPLETE"


def _require_stage0_clear() -> None:
    """The fit's entry gate: the Stage-0 record is committed, says CLEAR, and every Stage-0 flag
    has a recorded ruling (`require_stage0_rulings`, reading R7)."""
    _committed_clean(STAGE0_JSON, STAGE0_FLAGS, READINGS_RULED)
    if json.loads(STAGE0_JSON.read_text())["verdict"] != "STAGE 0: CLEAR":
        raise GateError(f"{STAGE0_JSON.name} does not say STAGE 0: CLEAR; no E1 statistic is computed past a halt")
    from scripts.cef.data_guards import require_stage0_rulings
    require_stage0_rulings(pd.read_csv(STAGE0_FLAGS, dtype=str), RULINGS, keys=("check", "ticker", "date"),
                           context="E1 Stage 0")


def crsp_cik_map(nm: pd.DataFrame, names: pd.DataFrame, bdc: bool = False) -> dict:
    """permno -> EDGAR CIK for every CEF permno (share code 14/44) with a name record in
    2009-07-01 .. 2024-12-31: each (permno, CRSP name) is matched by `match_cik` over the dates
    the name was in force. A permno whose names match two CIKs, or none, is left out (reading
    R4: such a fund cannot be a control, because its merger filings cannot be checked).
    `bdc` (ruling 12, 2026-10-21) adds share-code-11 names that `merger_pairs.classify` labels a
    BDC, so a BDC party's listing can be read through its CIK too (ALD, CIK 3906)."""
    from scripts.events import edgar_merger_dates as emd
    keep = nm["shrcd"].isin(ce.CEF_SHRCD)
    if bdc:
        keep |= (nm["shrcd"] == 11) & (nm["comnam"].map(mp.classify) == "bdc")
    cef = nm[keep & (nm["nameendt"] >= EPISODE_START) & (nm["namedt"] <= CRSP_END)]
    g = cef.groupby(["permno", "comnam"]).agg(lo=("namedt", "min"), hi=("nameendt", "max")).reset_index()
    found: dict[int, set] = {}
    for r in g.itertuples():
        m = emd.match_cik(r.comnam, names, r.lo, r.hi)
        if m["status"] == "matched":
            found.setdefault(int(r.permno), set()).add(int(m["cik"]))
    return {p: next(iter(c)) for p, c in found.items() if len(c) == 1}


def ticker_permno(nm: pd.DataFrame, ticker: str, when: pd.Timestamp) -> int:
    """The listed CEF/BDC permno (share code 14/44, or 11 for a BDC) carrying `ticker` on `when`."""
    r = nm[(nm["ticker"] == ticker) & (nm["namedt"] <= when) & (nm["nameendt"] >= when)
           & nm["shrcd"].isin((11, 14, 44))]
    if r["permno"].nunique() != 1:
        raise GateError(f"{ticker} on {when.date()}: {r['permno'].nunique()} CRSP permnos")
    return int(r["permno"].iloc[0])


def failed_deal_rows(readings: pd.DataFrame, nm: pd.DataFrame) -> pd.DataFrame:
    """The failed deals the readings put in the trial, as deal rows. A = the first public filing
    announcing the deal, F = the filing that made the failure public; the set follows F by §4.2's
    rules (a spec name on either side: excluded; F in 2023+: time holdout; a cef_universe.csv
    name: name holdout; else fit)."""
    # One deal may be read from two episodes (its target's and its acquirer's filings; their
    # agreement is checked by `check_readings`): A is the earlier first public announcement and
    # F the earlier public failure.
    y = readings[readings["in_trial"] == "Y"].copy()
    r = (y.assign(ann_date=pd.to_datetime(y["ann_date"]), fail_date=pd.to_datetime(y["fail_date"]))
         .groupby("deal_id", as_index=False)
         .agg(ann_date=("ann_date", "min"), fail_date=("fail_date", "min"), target_ticker=("target_ticker", "first"),
              acquirer_ticker=("acquirer_ticker", "first")))
    # Ruling 1: A is the deal's EARLIEST announcement over every reading of it, not only the rows
    # that carry the failure (SBI -> MMU: MMU's filings announce it 2023-03-17; SBI's own, read for
    # the failure, first mention it 2023-07-28).
    allann = pd.to_datetime(readings["ann_date"].replace("", None)).groupby(readings["deal_id"]).min()
    r["ann_date"] = [min(a, allann.get(d, a)) if pd.notna(allann.get(d)) else a for d, a in zip(r["deal_id"], r["ann_date"])]
    up = ce.universe_permnos(nm)
    uni = {p for ps in up.values() for p in ps}
    spec_p = {p for tk, ps in up.items() if tk in spec_names() for p in ps}
    rows = []
    for e in r.itertuples():
        A, F = pd.Timestamp(e.ann_date), pd.Timestamp(e.fail_date)
        tp, ap = ticker_permno(nm, e.target_ticker, A), ticker_permno(nm, e.acquirer_ticker, A)
        name = ce.name_at(nm, tp, A)
        part = ("excluded_spec" if {tp, ap} & spec_p else "time_holdout" if F >= HOLDOUT_START
                else "name_holdout" if {tp, ap} & uni else FIT_SET)
        rows.append({"permno": tp, "nwperm": ap, "ticker": e.target_ticker, "a_ticker": e.acquirer_ticker,
                     "comnam": name["comnam"], "ann": A, "fail_date": F, "failed": True,
                     "seg": mp.classify(name["comnam"]), "dlstdt": pd.NaT, "dlpdt": pd.NaT, "dlret": np.nan,
                     "dlstcd": 0, "deal_id": e.deal_id, "part": part})
    d = pd.DataFrame(rows)
    if len(d):
        d["group"] = d["nwperm"].astype(str) + "@" + d["ann"].dt.strftime("%Y-%m-%d")
    return d


def price_deals(D: pd.DataFrame, px: dict, cal: pd.DatetimeIndex, R: pd.DataFrame, lag: int = 0) -> tuple[pd.DataFrame, dict]:
    """Per-deal pricing, the §6.3 guard and control 1, for completed and failed deals.

    A deal is kept only if its buy-and-hold pair is priced AND every earned session of both
    legs passes `hold_gaps`; otherwise it is excluded with its reason, counted. Units: 2 + |pair|
    for a conversion (reading R6), 4 for a failed deal (§7)."""
    rows, excl = [], {}

    def drop(why):
        excl[why] = excl.get(why, 0) + 1

    for i, e in D.iterrows():
        failed = bool(e["failed"])
        if failed:
            w = deal_window(e, px, cal, failed=True, fail_date=e["fail_date"], lag=lag)
            if w is None or w["why"]:
                drop((w or {}).get("why", "no window"))
                continue
            rt, _, st = mp.window_return(px[int(e["permno"])], w["d_in"], w["exit"])
            ra, _, sa = mp.window_return(px[int(e["nwperm"])], w["d_in"], w["exit"])
            pair = rt - ra
        else:
            pair = price_completed(e, px, lag).get("pair_A1_to_close", np.nan)
            w = deal_window(e, px, cal, lag=lag)
            if w is None or w["why"]:
                drop((w or {}).get("why", "no window"))
                continue
        if not np.isfinite(pair):
            drop("buy-and-hold pair unpriced")
            continue
        span = None if failed else (pd.Timestamp(e["dlstdt"]), pd.Timestamp(e["dlpdt"]))
        g = hold_gaps(R[int(e["permno"])], w["d_in"], w["exit"], span) or hold_gaps(R[int(e["nwperm"])], w["d_in"], w["exit"])
        if g:
            drop(g)
            continue
        end_t = w["exit"] if failed else pd.Timestamp(e["dlstdt"])
        c1 = control1(e, px, w["d_in"], end_t)
        rows.append({"row": i, **{k: e[k] for k in ("permno", "nwperm", "ticker", "seg", "group", "ann", "failed", "dlstdt", "dlpdt")},
                     "part": e.get("part"), "a_ticker": e.get("a_ticker"), "comnam": e.get("comnam"), "d_in": w["d_in"], "exit": w["exit"],
                     "first": w["first"], "last": w["last"], "pair": float(pair),
                     "units": 4.0 if failed else 2.0 + abs(float(pair)),
                     "ctrl1": c1["ctrl"], "ctrl1_why": c1["why"], "days": int((w["exit"] - w["d_in"]).days)})
    return pd.DataFrame(rows), excl


def attach_ctrl2(P: pd.DataFrame, c2: dict) -> pd.DataFrame:
    """`P` (from `price_deals`) with `ctrl2` = control 2's pair for each deal, keyed by the deal's
    row in the deal table (`P['row']`), never by the target's permno: NCU is the target of two fit
    deals (failed 2011-12-19 -> 2013-11-22, completed 2013-11-22 -> 2014-06-06), and a permno key
    gave both the last one's control (found 2026-10-22, before the fit ran). A deal with no
    control 2 is NaN, counted at stage 3."""
    if "row" not in P or P["row"].duplicated().any():
        raise ValueError("attach_ctrl2: P needs one `row` per deal (price_deals output)")
    return P.assign(ctrl2=P["row"].map(c2).astype(float))


def holdout_windows(H: pd.DataFrame) -> pd.DataFrame:
    """The holdout deals' windows for control 2's exclusion, from DATES ONLY (no holdout price is
    read before the fit verdict): [A, exit + 1 day], wider than the traded (d_in, exit], so a
    candidate near a holdout deal is excluded rather than admitted."""
    ex = H["fail_date"].where(H["failed"].astype(bool), H["dlpdt"])
    return pd.DataFrame({"permno": H["permno"].astype(int), "nwperm": H["nwperm"].astype(int),
                         "d_in": pd.to_datetime(H["ann"]), "exit": pd.to_datetime(ex) + pd.Timedelta(days=1)})


def fit_core(P: pd.DataFrame, R: pd.DataFrame, cal: pd.DatetimeIndex, X: pd.DataFrame, *, vol_target: float,
             cap: float | None, seg: str = "muni", book_pnl: pd.Series | None = None) -> dict:
    """Stages 1-6 on priced deals (`price_deals` output with `ctrl2` added), in the declared order.

    Every statistic is computed whatever an earlier stage says; the verdict is the first failing
    rule. Borrow is not here (amendment 1): `borrow_table` prints it beside, labelled."""
    M = P[P["seg"] == seg].copy()
    out: dict = {"segment": seg, "deals": int(len(M)), "completed": int((~M["failed"].astype(bool)).sum()),
                 "failed": int(M["failed"].astype(bool).sum())}
    s1 = deal_stats(M["pair"], M["group"], M["units"])
    out["stage1"] = {**s1, "passes": stage1_passes(s1["median"], s1["clustered_t"])}
    c1 = M.dropna(subset=["ctrl1"])
    out["stage2"] = {"with_control": int(len(c1)), "without": int(len(M) - len(c1)),
                     "ctrl_median": float(c1["ctrl1"].median()) if len(c1) else np.nan,
                     "treatment_median_same_deals": float(c1["pair"].median()) if len(c1) else np.nan}
    out["stage2"]["kills"] = control_kills(out["stage2"]["ctrl_median"], s1["median"])
    c2 = M.dropna(subset=["ctrl2"]) if "ctrl2" in M else M.iloc[0:0]
    share = len(c2) / len(M) if len(M) else 0.0
    out["stage3"] = {"with_control": int(len(c2)), "share": share, "halts": bool(share < CONTROL2_MIN_SHARE),
                     "ctrl_median": float(c2["ctrl2"].median()) if len(c2) else np.nan,
                     "treatment_median_same_deals": float(c2["pair"].median()) if len(c2) else np.nan}
    out["stage3"]["kills"] = control_kills(out["stage3"]["ctrl_median"], s1["median"])
    S = sleeve(M, R, cal, k=None, cap=cap, vol_target=vol_target)
    st = sleeve_stats(S)
    out["stage4"] = {**st, "k": S["k"], "sigma_raw": S["sigma_raw"], "cap_binding_share": S["cap_binding_share"],
                     "first": str(pd.Timestamp(S["first"]).date()), "passes": bool(st["net_ann"][f"{DECIDING_BP}bp"] > 0),
                     "f_max": f_max(float(M["pair"].median()), float(M["days"].median())),
                     "break_even_fee_pct": break_even_fee(S)}
    d4 = dimson(S["pnl"], X, list(FF6) + list(ETF_TICKERS))
    out["stage5"] = {**d4, "passes": d4_passes(d4), "r_ff": dimson(S["pnl"], X, list(FF6))}
    if book_pnl is not None:
        y = S["pnl"]
        b = book_pnl.reindex(y.index)
        f, n = hac(y, b.rename("book").to_frame())
        out["stage5"]["r_book"] = {"n": n, "corr": float(pd.concat([y, b], axis=1).dropna().corr().iloc[0, 1]),
                                   "beta": float(f.params["book"]), "t": float(f.tvalues["book"])}
    out["stage6"] = dsr(S["pnl"])
    order = [("stage1", lambda o: o["passes"], "KILL D1 (stage 1)"),
             ("stage2", lambda o: not o["kills"], "KILL (stage 2: control 1 earns >= half the effect)"),
             ("stage3", lambda o: not o["halts"], "HALT (stage 3: fewer than 75% of deals have a control 2)"),
             ("stage3", lambda o: not o["kills"], "KILL (stage 3: control 2 earns >= half the effect)"),
             ("stage4", lambda o: o["passes"], "KILL D2 (stage 4: net <= 0 at 15bp)"),
             ("stage5", lambda o: o["passes"], "KILL D4 (stage 5)"),
             ("stage6", lambda o: o["passes"], "NEITHER (stage 6: below the bar at N = 6)")]
    out["verdict"] = next((v for k, ok, v in order if not ok(out[k])), "FIT PASSES STAGES 1-6")
    out["sleeve"] = S
    return out


def _jsonable(o):
    """Aggregates only: drop the frames (row-level CRSP-derived values never go in a tracked file)."""
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items() if not isinstance(v, (pd.DataFrame, pd.Series))}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer, np.bool_)):
        return o.item()
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    return o


def _book_pnl() -> pd.Series:
    """R-BOOK's series: the deployed v7 book as `c4_families.book_series` builds it (live panel, band to
    the edge, gross-capped, daily gross total-return P&L)."""
    from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS
    T, Rb = bf.build_targets()
    H = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)
    return bf.evaluate(H, bf.total_returns(Rb))["pnl"]


def trial_failed_deals(nm: pd.DataFrame) -> pd.DataFrame:
    """The failed deals the fit and the holdout trade: `failed_deal_rows` on the RULED readings
    Stage 0 wrote and committed (`READINGS_RULED`), checked against the in-trial deal list in
    the committed Stage-0 record. Raises if either is missing or they disagree.

    Why: until 2026-10-22 the fit read `READINGS`, the round-1 readings alone (3 in-trial deals),
    while Stage 0 cleared the 13 of every round and ruling; nothing would have errored."""
    if not READINGS_RULED.exists():
        raise GateError(f"{_rel(READINGS_RULED)} does not exist: run stage0 (DG-E1-3 writes it)")
    rec = json.loads(STAGE0_JSON.read_text())["gates"]["DG-E1-3"] if STAGE0_JSON.exists() else {}
    want = rec.get("in_trial_deal_list")
    if want is None:
        raise GateError(f"{STAGE0_JSON.name} records no in-trial deal list (DG-E1-3): re-run stage0")
    F = failed_deal_rows(pd.read_csv(READINGS_RULED, dtype=str, keep_default_na=False), nm)
    got = sorted(set(F["ticker"] + "->" + F["a_ticker"]))
    if got != sorted(want):
        raise GateError(f"the ruled readings give {len(got)} failed deals, the Stage-0 record {len(want)}: "
                        f"only here {sorted(set(got) - set(want))}, only in the record {sorted(set(want) - set(got))}")
    return F


def _load_trial_deals(nm, dl, today: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(every completed deal dated, every failed deal) with `part`, `failed`, `group`."""
    x = deal_table(nm, dl)
    fd = load_fit_dates(x)
    if not HOLDOUT_DATES.exists():
        raise GateError("DG-E1-2: no holdout dates")
    hd = pd.read_csv(HOLDOUT_DATES)
    comp = attach_dates(x, pd.concat([fd, hd], ignore_index=True)).assign(failed=False, fail_date=pd.NaT)
    return comp, trial_failed_deals(nm)


def fit(args) -> int:  # pragma: no cover - runs only once Stage 0 is CLEAR; its core is tested (fit_core)
    """Stages 1-6 and the stage-7 verdict file. Refuses unless Stage 0 is CLEAR and ruled."""
    _require_stage0_clear()
    from scripts.cef.spec import MAX_GROSS_STRESS, VOL_TARGET
    from scripts.events import edgar_merger_dates as emd
    nm, dl = crsp_tables()
    comp, fail = _load_trial_deals(nm, dl, date.fromisoformat(args.today))
    D = pd.concat([comp[comp["part"] == FIT_SET], fail[fail["part"] == FIT_SET]], ignore_index=True)
    Hd = pd.concat([comp[comp["part"].isin(HOLDOUT_SETS)], fail[fail["part"].isin(HOLDOUT_SETS)]], ignore_index=True)
    names, _ = emd.name_table(edgar_client(online=False), date.fromisoformat(args.today))
    cikmap = crsp_cik_map(nm, names)
    episodes = merger_episodes()
    etf_perm = {tk: int(nm[(nm["ticker"] == tk) & (nm["shrcd"] == 73) & (nm["nameendt"] >= FIT_START)]["permno"].iloc[0])
                for tk in ETF_TICKERS}
    perms0 = set(D["permno"].astype(int)) | set(D["nwperm"].astype(int)) | set(etf_perm.values())
    px0 = price_series(fit_daily(perms0))
    cal = market_calendar(pd.concat([v.reset_index()[["date"]] for v in px0.values()]), CAL_START, FIT_END)
    pool = {}
    for i, e in D.iterrows():
        w = deal_window(e, px0, cal, failed=bool(e["failed"]), fail_date=e["fail_date"])
        if w is not None and not w["why"]:
            pool[i] = (w, control2_candidates(e, nm, cal, w, set()))
    perms = perms0 | {int(p) for _, c in pool.values() for p in c["permno"]}
    dsf = fit_daily(perms)
    px = price_series(dsf)
    R = returns_matrix(px, cal, D)
    P, excl = price_deals(D, px, cal, R)
    hw = holdout_windows(Hd)
    c2 = {}
    for i, e in D.iterrows():
        if i not in pool:
            continue
        w, cands = pool[i]
        pick = pick_control2(e, cands, px, w, cikmap, episodes, hw, cal)
        c2[i] = control2_pair(e, px, pick["permno"], w) if pick["permno"] else np.nan
    P = attach_ctrl2(P, c2)
    X = factor_frame(px, etf_perm)
    res = fit_core(P, R, cal, X, vol_target=VOL_TARGET, cap=MAX_GROSS_STRESS, book_pnl=_book_pnl())
    S = res.pop("sleeve")
    res["excluded"] = excl
    res["borrow"] = borrow_table(S, {
        "B0 (zero: Alpaca ETB terms, the paper account)": flat_fee(S["H"], 0.0),
        "B-cap (flat f_max)": (flat_fee(S["H"], res["stage4"]["f_max"]["f_max_pct"])
                               if res["stage4"]["f_max"]["f_max_pct"] > 0 else "f_max <= 0: the effect carries no borrow"),
        "B-med (universe muni acquirers' fee before first filing)": flat_fee(S["H"], b_med_fee()["median_pct"]),
        "B-meas (measured, universe names 2021-09-13 on)": b_meas_fee(S["H"], nm)})
    res["eras"] = era_rows(P[P["seg"] == "muni"], S)
    res["capacity"] = capacity(P[P["seg"] == "muni"], S, px)
    res["segments"] = {s: deal_stats(g["pair"], g["group"], g["units"], boot=False) for s, g in P.groupby("seg")}
    P3, _ = price_deals(D, px, cal, R, lag=1)
    res["shift3"] = deal_stats(P3.loc[P3["seg"] == "muni", "pair"], P3.loc[P3["seg"] == "muni", "group"], boot=False)
    res["stage7_fit_verdict_written"] = True
    res["frozen"] = {"k": res["stage4"]["k"], "cap": MAX_GROSS_STRESS, "f_max_pct": res["stage4"]["f_max"]["f_max_pct"],
                     "N": N_EVENTS}
    res["run_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    FIT_JSON.write_text(json.dumps(_jsonable(res), indent=1, default=str) + "\n")
    print(json.dumps(_jsonable({k: res[k] for k in ("verdict", "frozen", "stage1", "stage4")}), indent=1, default=str))
    print(f"\nwrote {FIT_JSON.relative_to(REPO)}. STAGE 7: commit it before any holdout number exists.")
    return 0


def holdout(args) -> int:  # pragma: no cover - OPENED ONCE, after the committed fit verdict
    """Stage 8 (§10): name + time holdouts pooled, each alone too; k and the cap frozen from the
    fit verdict. The marker is written before the first holdout return, so a run that dies
    half-way refuses a second run and must be reported, not repeated."""
    if HOLDOUT_MARKER.exists() or HOLDOUT_JSON.exists():
        raise GateError(f"the holdout has been opened ({HOLDOUT_MARKER.name}); it is opened once")
    v = holdout_gate()
    nm, dl = crsp_tables()
    comp, fail = _load_trial_deals(nm, dl, date.fromisoformat(args.today))
    D = pd.concat([comp[comp["part"].isin(HOLDOUT_SETS)], fail[fail["part"].isin(HOLDOUT_SETS)]], ignore_index=True)
    perms = set(D["permno"].astype(int)) | set(D["nwperm"].astype(int))
    HOLDOUT_MARKER.write_text(f"opened {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
    dsf = holdout_daily(perms)
    px = price_series(dsf)
    cal = market_calendar(dsf, CAL_START, CRSP_END)
    R = returns_matrix(px, cal, D)
    P, excl = price_deals(D, px, cal, R)
    M = P[P["seg"] == "muni"]
    out = {"excluded": excl, "fit_verdict": v["verdict"], "frozen": v["frozen"], "sets": {}}
    for lab, mask in (("pooled", M.index == M.index), ("name_holdout", M["part"] == "name_holdout"),
                      ("time_holdout", M["part"] == "time_holdout")):   # by the deal's own set, not its permno
        m = M[mask]
        if not len(m):
            out["sets"][lab] = {"deals": 0}
            continue
        S = sleeve(m, R, cal, k=v["frozen"]["k"], cap=v["frozen"]["cap"], vol_target=np.nan)
        paired = m.dropna(subset=["ctrl1"])
        out["sets"][lab] = {"deals": int(len(m)), "groups": int(m["group"].nunique()),
                            "a_mean_pair": float(m["pair"].mean()), "b_sleeve_mean_daily": float(S["pnl"].mean()),
                            "c_mean_treatment_minus_ctrl1": float((paired["pair"] - paired["ctrl1"]).mean()) if len(paired) else np.nan,
                            "stats": deal_stats(m["pair"], m["group"], m["units"], boot=False),
                            "sleeve": sleeve_stats(S)}
    pooled = out["sets"]["pooled"]
    signs = [pooled.get(k, np.nan) for k in ("a_mean_pair", "b_sleeve_mean_daily", "c_mean_treatment_minus_ctrl1")]
    out["verdict"] = "HOLDOUT SIGNS ALL > 0" if all(np.isfinite(s) and s > 0 for s in signs) else "KILL D3 (stage 8)"
    HOLDOUT_JSON.write_text(json.dumps(_jsonable(out), indent=1, default=str) + "\n")
    print(json.dumps(_jsonable(out), indent=1, default=str))
    return 0


# =========================================================================== team-lead commands

def fetch_edgar(args) -> int:  # pragma: no cover - loads the SEC contact; the team lead runs it
    """DG-E1-2 and DG-E1-3's EDGAR work, online: dates the holdout deals (writes the holdout dates
    and their summary) and caches, for every census candidate, its submissions list and every
    merger-series, proxy, 8-K and RW filing from 30 days before its first filing to 730 after.
    Reads nothing from CRSP but the cached names and delistings; computes no return."""
    from scripts.data import fetch_edgar_events as fe
    from scripts.data.edgar_client import filing_txt_url
    client = edgar_client(online=True)
    if getattr(args, "cik", None):              # one fund's filings around a date (e.g. SBI, CIK 882300)
        f0 = pd.Timestamp(args.around)
        sb = fe.submissions(client, int(args.cik), max_age_s=30 * fe.DAY)
        sb = sb[sb["form"].isin(TARGETED_FORMS) & (sb["filingDate"] >= f0 - pd.Timedelta(days=CENSUS_PRE_DAYS))
                & (sb["filingDate"] <= f0 + pd.Timedelta(days=FAIL_WINDOW_DAYS))]
        for a in sb["accessionNumber"]:
            client.get(filing_txt_url(int(args.cik), a))
        print(f"CIK {args.cik}: {len(sb)} filings cached ({sb['form'].value_counts().to_dict()})")
        return 0
    if getattr(args, "amendment4", False):     # date amendment 4's 331 deals (fit and holdouts), unchanged rule
        nm, dl = crsp_tables()
        x = deal_table(nm, dl)
        s3 = x[(x["dlstcd"] == 331) & x["part"].isin((FIT_SET,) + HOLDOUT_SETS)]
        from scripts.events import edgar_merger_dates as emd
        res, summ = emd.date_deals(client, date.today(), sample=s3)
        CACHE.mkdir(parents=True, exist_ok=True)
        res.to_csv(DATES_331, index=False)
        DATES_331_SUMMARY.write_text(json.dumps(summ, indent=1, default=str))
        print(f"amendment 4: {summ['dated']} of {summ['events']} 331 deals dated -> {_rel(DATES_331)}")
        return 0
    if getattr(args, "supp", False):
        cen = pd.read_csv(CENSUS_SUPP)          # ruling 9: the supplementary census only
        summ = None
    else:
        nm, dl = crsp_tables()
        x = deal_table(nm, dl)
        res, summ = date_holdouts(client, x, date.today())
        CACHE.mkdir(parents=True, exist_ok=True)
        res.to_csv(HOLDOUT_DATES, index=False)
        HOLDOUT_DATES_SUMMARY.write_text(json.dumps(summ, indent=1, default=str))
        cen = pd.read_csv(CENSUS)
    forms = CENSUS_FORMS
    n = 0
    for r in cen.itertuples():
        sb = fe.submissions(client, int(r.episode_cik), max_age_s=30 * fe.DAY)
        f0 = pd.Timestamp(r.first_date)
        sb = sb[sb["form"].isin(forms) & (sb["filingDate"] >= f0 - pd.Timedelta(days=CENSUS_PRE_DAYS))
                & (sb["filingDate"] <= f0 + pd.Timedelta(days=FAIL_WINDOW_DAYS))]
        for a in sb["accessionNumber"]:
            client.get(filing_txt_url(int(r.episode_cik), a))
            n += 1
    print((f"holdout deals dated: {summ['dated']} of {summ['events']}; " if summ else "") + f"census filings cached: {n}")
    return 0


def refresh_edgar_index(args) -> int:  # pragma: no cover - loads the SEC contact; the team lead runs it
    """Refresh the one EDGAR file Stage 0 cannot read offline: the OPEN quarter's full index, which
    `fetch_edgar_events.quarter_is_closed` re-fetches once a day (max_age one day; its semantics are
    unchanged here). Writes into the union cache Stage 0 reads; computes nothing. An offline
    `stage0` then works until the refreshed file is a day old (probe of 2026-10-20: it is the only
    stale or missing URL Stage 0 asks for)."""
    from scripts.events import edgar_merger_dates as emd
    today = date.fromisoformat(args.today)
    emd.name_table(edgar_client(online=True), today)
    print(f"EDGAR indexes current to {today} in {_rel(EDGAR_UNION)}; run `stage0 --today {today}` within a day")
    return 0


def pull_crsp(args) -> int:  # pragma: no cover - loads the R2 credential; the team lead runs it
    """The fit reader's extract from R2 (pre-2023 only, `crsp_events.daily`) for a permno list."""
    perms = [int(p) for p in Path(args.permnos).read_text().split()]
    d = ce.daily(perms)
    print(f"{_dsf_path(perms).relative_to(REPO)}: {len(d):,} rows, last {d['date'].max().date()}")
    return 0


def pull_holdout(args) -> int:  # pragma: no cover - loads the R2 credential; refused before the fit verdict
    """The holdout reader's extract: CRSP rows to 2024-12-31 for the holdout parties. Refused
    unless the fit verdict is committed and says the holdout opens (`holdout_gate`)."""
    holdout_gate()
    from src.data.r2 import connect, q, r2_path
    perms = [int(p) for p in Path(args.permnos).read_text().split()]
    s, h = ce._plist(perms)
    sql = (f"SELECT permno, date, prc, ret, retx, vol, shrout, cfacpr FROM read_parquet('{r2_path('crsp_a_stock', 'dsf')}') "
           f"WHERE permno IN ({s}) AND date >= DATE '2009-07-01' AND date <= DATE '2024-12-31'")
    d = q(connect(), sql)
    CACHE.mkdir(parents=True, exist_ok=True)
    d.to_parquet(CACHE / f"holdout_dsf_{h}.parquet")
    print(f"holdout extract: {len(d):,} rows")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s0 = sub.add_parser("stage0")
    s0.add_argument("--today", default=str(date.today()),
                    help="EDGAR index horizon for the offline name table (the run date). Was the fixed 2026-10-19 "
                         "until 2026-10-20: the open quarter's index must be refreshed by `refresh-edgar-index` on "
                         "the run date either way (its one-day max_age is unchanged)")
    for name in ("fit", "holdout"):
        sp = sub.add_parser(name)
        sp.add_argument("--today", default=str(date.today()),
                        help="EDGAR index horizon for the offline name table (the run date; `refresh-edgar-index` keeps it current)")
    sc = sub.add_parser("stage-crsp")
    sc.add_argument("--from", dest="sources", action="append", type=Path, required=True)
    sc.add_argument("--permnos", type=Path, help="a file of permnos; default: the fit parties and the ETFs")
    sc.add_argument("--partial", action="store_true",
                    help="stage the permnos found and list the rest (for the control-2 pool's coverage)")
    fe_p = sub.add_parser("fetch-edgar")
    fe_p.add_argument("--supp", action="store_true", help="only the supplementary census's filings (ruling 9)")
    fe_p.add_argument("--amendment4", action="store_true", help="date amendment 4's 331 deals (fit and holdouts)")
    fe_p.add_argument("--cik", help="one fund's filings around --around (TARGETED_FORMS, -30 to +730 days)")
    fe_p.add_argument("--around", help="the date the --cik window is built around (YYYY-MM-DD)")
    sub.add_parser("universe-counts")
    ri = sub.add_parser("refresh-edgar-index")
    ri.add_argument("--today", default=str(date.today()))
    pc = sub.add_parser("pull-crsp")
    pc.add_argument("--permnos", type=Path, required=True)
    ph = sub.add_parser("pull-holdout")
    ph.add_argument("--permnos", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "stage0":
        return stage0(a)
    if a.cmd == "universe-counts":
        nm, dl = crsp_tables()
        r = universe_counts(nm, dl)
        print(json.dumps({k: r[k] for k in ("codes", "deals_331_by_set")}), f"-> {_rel(UNIVERSE_COUNTS)}")
        return 0
    if a.cmd == "stage-crsp":
        nm, dl = crsp_tables()
        x = deal_table(nm, dl)
        if a.permnos:
            perms = [int(p) for p in a.permnos.read_text().split()]
        else:
            xf = x[x["part"] == FIT_SET]
            etf = {int(nm[(nm["ticker"] == tk) & (nm["shrcd"] == 73) & (nm["nameendt"] >= FIT_START)]["permno"].iloc[0])
                   for tk in ETF_TICKERS}
            perms = sorted(set(xf["permno"].astype(int)) | set(xf["nwperm"].astype(int)) | etf)
        out, missing = stage_crsp(perms, a.sources, a.partial)
        print(f"{out.relative_to(REPO)}; not in any source: {len(missing)}")
        if missing:
            (CACHE / "stage_crsp_missing_permnos.txt").write_text("\n".join(map(str, missing)) + "\n")
        return 0
    return {"fit": fit, "holdout": holdout, "fetch-edgar": fetch_edgar, "pull-crsp": pull_crsp,
            "refresh-edgar-index": refresh_edgar_index,
            "pull-holdout": pull_holdout}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
