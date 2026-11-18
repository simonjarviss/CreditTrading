"""Promotion and the ladder: which shadow books may become paper sleeves, and which stage each
sleeve should be at. READ-ONLY. It sends nothing, writes nothing and imports no broker client.

    python3 -m quantt.sleeves.promote --shadow-state <dir> --events-state <dir> [--json]

WHY THIS EXISTS (team lead, 2026-11-18; docs/SYSTEM.md section 5, EVIDENCE_LOG E-2026-11-18-04).
The rulings made promoting a book and re-sizing a sleeve a matter of counting sessions, but
the count was done by eye from the scoreboard and the full sizes were prose in a note. This
report does the counting from the two state directories and prints the one-line edit of
`ops/sleeves/events_sleeves.json` that is due, so that the change is a routine PR.

It implements the rulings and nothing else. Where a ruling needs something nobody has
defined or recorded, the verdict is UNMEASURED and says what is missing (CLAUDE.md: a stated
gap, never a guess).

PROMOTION: TEN CLEAN ON-TIME SHADOW SESSIONS, "no UNMEASURED and no LATE day"
----------------------------------------------------------------------------
A SESSION is one row of the shadow book's `<shadow state>/<slug>/scores.csv`: the engine
appends exactly one per exchange session after the book started (shadow/engine.py `mark`).
The row for session S (column `date`, with `prev` = the session before) is CLEAN when both
  1. its `status` is SCORED or FLAT, not UNMEASURED (a held name had no close, or moved
     beyond the split guard with no split row); and
  2. the decision that FILLS on S, `decisions/<prev>.json`, exists and its `written_at` is
     before 13:00 New York on S: the engine's own on-time rule (`on_time`). No file is
     NO_DECISION (the nightly run never decided: a panel was missing, or the machine was
     off); a later one is LATE.
A FLAT day counts. The rule is a test of the feed and the plumbing, not of the return, and
an event book with no event that day still had to fetch its panels and write an on-time
decision with no weights; that is what condition 2 checks. FLAT ALONE IS NOT ENOUGH, which
is why the decision file is read: the engine also writes FLAT when there was no on-time
decision at all, so the scoreboard's "flat" column cannot tell a quiet day from a dead run.
(THIS READING IS FOR THE TEAM LEAD TO CONFIRM; the ruling does not say what a session is
for a book that is flat on most days.)
ELIGIBLE = the latest ten sessions are all clean, i.e. the run of clean sessions ending at
the last row is at least TEN. An unclean day therefore costs ten more sessions, not one.
The decision for the latest as-of date is not counted until the session it fills in has a row.

THE LADDER, counted in sessions on which the sleeve HELD A POSITION on paper
----------------------------------------------------------------------------
A position session is a row of `<events state>/sleeve_scores.csv` for the sleeve with
`n_names` > 0 (run.py `score_rows`: the names it held after that session's booking). T is
their count.
  T < 20      a QUARTER of `full_capital_usd`.
  20 to 59    a HALF "if fills track the shadow book". NOBODY HAS DEFINED "TRACK": the
              verdict is UNMEASURED and the report prints the figures a rule could be
              written on (paper P&L beside the shadow book's on the same sessions).
  T >= 60     FULL if live P&L is above -1 sigma x sqrt(T), a half between -1 and -2,
              STOPPED below -2. NO SIGMA IS RECORDED for any sleeve, and sleeve_scores.csv
              does not record the capital each session traded at, which a sigma in dollars
              needs once the stage has changed: UNMEASURED, naming both.
STOPPED is `enabled: false` (config.py requires capital_usd > 0, and a disabled sleeve is
flattened), so a `capital_usd` of zero cannot occur and the stages a file can hold are a
quarter, a half and one. The report REFUSES, naming the sleeve, a `capital_usd` that is not
`full_capital_usd` x one of those: a size off the ladder is a hand edit nobody ruled on.

THE PROMOTION GATE ON A LISTED SLEEVE. The book file's note says a sleeve is enabled only
after its shadow book is eligible. The report applies that to a sleeve that has never held a
position (CHANGE NEEDED: `enabled: false`). It does not apply it again to a sleeve that has
traded: `enabled: false` there FLATTENS it, and no ruling says a later unclean shadow day
demotes a sleeve.

EXIT CODES
   0  AGREE        every sleeve's capital_usd and enabled are what the rules say.
  30  CHANGE       at least one edit of the book file is due (printed), nothing unmeasured.
  31  UNMEASURED   at least one sleeve's verdict could not be measured (printed, with the
                   path or the missing rule). Edits that are due are still printed.
  32  REFUSED      the book file cannot be used, or a capital_usd is off the ladder.
A shadow book that is not a sleeve never changes the exit code: listing it is a decision,
not a correction.

WHY IT DOES NOT IMPORT `shadow` OR `run.py`: the live path never imports shadow
(shadow/tests/test_boundary.py), and run.py holds the send path. The two facts taken from
them, the 13:00 cutoff and the score file's header, are restated here and pinned to the
originals by tests (quantt/sleeves/tests/test_promote.py).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from quantt.sleeves import config

REPO = Path(__file__).resolve().parents[2]
BOOK_PATH = REPO / "ops" / "sleeves" / "events_sleeves.json"
NY = ZoneInfo("America/New_York")
ON_TIME_CUTOFF = dt.time(13, 0)            # shadow.engine.ON_TIME_CUTOFF, pinned by a test
SHADOW_STATUSES = ("SCORED", "FLAT", "UNMEASURED")   # every status shadow.engine writes
SCORES_COLUMNS = ("date", "slug", "shares_value", "cash", "pnl", "day_change", "n_names",
                  "equity_change", "residual")      # quantt.sleeves.run.SCORES_COLUMNS, pinned by a test
BOOK_ROW = "_book"                         # run.py's row for the whole account; not a sleeve
CLEAN_SESSIONS_TO_PROMOTE = 10             # team lead, 2026-11-18
HALF_FROM, FULL_FROM = 20, 60              # position sessions; team lead, 2026-11-18
STAGES = {"QUARTER": 0.25, "HALF": 0.5, "FULL": 1.0}
CENT = 0.005                               # two dollar figures are the same within half a cent
EXIT_AGREE, EXIT_CHANGE, EXIT_UNMEASURED, EXIT_REFUSED = 0, 30, 31, 32
AGREE, CHANGE, UNMEASURED = "AGREE", "CHANGE NEEDED", "UNMEASURED"
RULING = "docs/SYSTEM.md section 5, team lead 2026-11-18"
NO_TRACK_RULE = (f"'if fills track the shadow book' has no written definition ({RULING}); "
                 "the team lead has not yet said what difference fails")
NO_SIGMA = ("no sigma is recorded for this sleeve: the book file has no such field (the only "
            "candidate on record is the backtest volatility quoted in its _note_sleeves, which no "
            "ruling names as the sigma), and sleeve_scores.csv does not record the capital_usd each "
            "session traded at, which a sigma in dollars needs")


class PromoteError(RuntimeError):
    """The report refuses; the message names the sleeve or the file."""


class Unreadable(Exception):
    """An input is missing or not in the expected form. Reported as UNMEASURED with this
    message, which names the path; never read as zero sessions."""


# ------------------------------------------------------------------ shadow side

def _date(text: str, where: str) -> dt.date:
    try:
        return dt.date.fromisoformat(text)
    except (TypeError, ValueError):
        raise Unreadable(f"{where}: {text!r} is not a date") from None


def shadow_sessions(book_dir: Path) -> list:
    """[{date, prev, status, kind, why, pnl_price_usd}] for every row of the book's
    scores.csv, in file order. `kind` is CLEAN, UNMEASURED, LATE or NO_DECISION (module
    docstring). Raises Unreadable, naming the path, if the record cannot be read."""
    scores = book_dir / "scores.csv"
    if not book_dir.is_dir():
        raise Unreadable(f"{book_dir} is not a directory")
    if not scores.is_file():
        raise Unreadable(f"{scores} does not exist (no session marked yet, or the state is not readable from here)")
    try:
        with scores.open(newline="") as fh:
            rd = csv.DictReader(fh)
            if not {"date", "prev", "status", "pnl_price_usd"} <= set(rd.fieldnames or ()):
                raise Unreadable(f"{scores}: header {rd.fieldnames} lacks date, prev, status or pnl_price_usd")
            rows = list(rd)
    except OSError as e:
        raise Unreadable(f"{scores}: {type(e).__name__}") from None
    out, last = [], None
    for n, r in enumerate(rows, start=2):
        where = f"{scores} line {n}"
        day, prev = _date(r["date"], where), _date(r["prev"], where)
        if r["status"] not in SHADOW_STATUSES:
            raise Unreadable(f"{where}: status {r['status']!r} is not one of {SHADOW_STATUSES}")
        if not prev < day or (last is not None and prev != last):
            # the engine scores consecutive sessions; a hole or a repeat means this is not its file
            raise Unreadable(f"{where}: session {day} with prev {prev} does not follow {last}")
        last = day
        kind, why = "CLEAN", ""
        if r["status"] == "UNMEASURED":
            kind, why = "UNMEASURED", r.get("detail") or "scores.csv gives no detail"
        else:
            kind, why = _decision_kind(book_dir / "decisions" / f"{prev.isoformat()}.json", day)
        out.append({"date": day, "prev": prev, "status": r["status"], "kind": kind, "why": why,
                    "pnl_price_usd": r["pnl_price_usd"]})
    return out


def _decision_kind(path: Path, fill: dt.date) -> tuple:
    """CLEAN if the decision at `path` was written before 13:00 New York on its fill session.
    ALIGNMENT: the decision as of `prev` fills on `fill`, the row's own date, so the cutoff
    is on the row's date; nothing dated after the row is read."""
    if not path.is_file():
        return "NO_DECISION", f"{path} does not exist"
    try:
        written = dt.datetime.fromisoformat(json.loads(path.read_text())["written_at"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise Unreadable(f"{path}: written_at cannot be read ({type(e).__name__})") from None
    if written.tzinfo is None:
        raise Unreadable(f"{path}: written_at {written} carries no time zone")
    cutoff = dt.datetime.combine(fill, ON_TIME_CUTOFF, tzinfo=NY)
    if written < cutoff:
        return "CLEAN", ""
    return "LATE", f"written {written.isoformat()}, not before {cutoff.isoformat()}"


def shadow_book(state: Path, slug: str) -> dict:
    """One shadow book's promotion record. `measured` False carries the reason and no count."""
    try:
        rows = shadow_sessions(state / slug)
    except Unreadable as e:
        return {"slug": slug, "measured": False, "why": str(e), "eligible": None}
    streak = 0
    for r in reversed(rows):
        if r["kind"] != "CLEAN":
            break
        streak += 1
    unclean = [r for r in rows if r["kind"] != "CLEAN"]
    return {"slug": slug, "measured": True, "sessions": len(rows),
            "clean_total": len(rows) - len(unclean), "clean_streak": streak,
            "streak_first": rows[-streak]["date"].isoformat() if streak else None,
            "first": rows[0]["date"].isoformat() if rows else None,
            "last": rows[-1]["date"].isoformat() if rows else None,
            "unclean": [{"date": r["date"].isoformat(), "kind": r["kind"], "why": r["why"]} for r in unclean],
            "eligible": streak >= CLEAN_SESSIONS_TO_PROMOTE, "_rows": rows}


def shadow_slugs(state: Path) -> list:
    """Every directory under the shadow state that holds a `decisions/` directory: the books
    the shadow runner has actually run, whatever branch its clone follows."""
    if not state.is_dir():
        raise Unreadable(f"shadow state {state} is not a directory")
    return sorted(p.name for p in state.iterdir() if (p / "decisions").is_dir())


# ------------------------------------------------------------------ sleeve side

def sleeve_rows(events_state: Path) -> dict:
    """{slug: [row, ...]} from the events runner's sleeve_scores.csv, in file order."""
    path = events_state / "sleeve_scores.csv"
    if not path.is_file():
        raise Unreadable(f"{path} does not exist (the events runner has booked no session, or the state is "
                         "not readable from here)")
    try:
        with path.open(newline="") as fh:
            rd = csv.DictReader(fh)
            if tuple(rd.fieldnames or ()) != SCORES_COLUMNS:
                raise Unreadable(f"{path}: header {rd.fieldnames} is not {list(SCORES_COLUMNS)}")
            rows = list(rd)
    except OSError as e:
        raise Unreadable(f"{path}: {type(e).__name__}") from None
    out: dict = {}
    for n, r in enumerate(rows, start=2):
        _date(r["date"], f"{path} line {n}")
        try:
            r["_n"] = int(r["n_names"])
        except (TypeError, ValueError):
            raise Unreadable(f"{path} line {n}: n_names {r['n_names']!r} is not a whole number") from None
        if r["slug"] != BOOK_ROW:
            out.setdefault(r["slug"], []).append(r)
    return out


def stage_of(sleeve) -> str:
    """The ladder stage `capital_usd` is, or a refusal naming the sleeve."""
    for name, frac in STAGES.items():
        if abs(sleeve.capital_usd - sleeve.full_capital_usd * frac) <= CENT:
            return name
    allowed = ", ".join(f"{sleeve.full_capital_usd * f:,.2f} ({n.lower()})" for n, f in STAGES.items())
    raise PromoteError(f"sleeve {sleeve.slug}: capital_usd {sleeve.capital_usd:,.2f} is not on the ladder for "
                       f"full_capital_usd {sleeve.full_capital_usd:,.2f}; it must be one of {allowed}. "
                       "STOPPED is enabled=false, not another size")


def tracking(rows: list, shadow: dict, capital_usd: float, shadow_state: Path, slug: str) -> dict:
    """Paper P&L beside the shadow book's on the sessions both measured. Figures only: no
    pass or fail exists (NO_TRACK_RULE). The shadow book's P&L is on its own notional; the
    rescaled line multiplies it by capital_usd / notional and so ASSUMES today's capital_usd
    on every session, which is exact only while the sleeve's stage has not changed."""
    if not shadow.get("measured"):
        return {"measured": False, "why": shadow.get("why", "no shadow record")}
    by_date = {r["date"].isoformat(): r for r in shadow["_rows"]}
    paper = shadow_usd = 0.0
    used, skipped = [], []
    for r in rows:
        if r["_n"] == 0:
            continue
        s = by_date.get(r["date"])
        if r["day_change"] == "" or s is None or s["status"] == "UNMEASURED":
            skipped.append(r["date"])
            continue
        paper += float(r["day_change"])
        shadow_usd += float(s["pnl_price_usd"])        # FLAT rows carry 0.0; SCORED the price line
        used.append(r["date"])
    out = {"measured": True, "sessions_compared": len(used), "sessions_skipped": skipped,
           "paper_pnl_usd": round(paper, 2), "shadow_pnl_usd_at_shadow_notional": round(shadow_usd, 2)}
    notionals = set()
    for d in used:
        p = shadow_state / slug / "decisions" / f"{by_date[d]['prev'].isoformat()}.json"
        try:
            notionals.add(float(json.loads(p.read_text())["notional_usd"]))
        except (OSError, ValueError, KeyError, TypeError):
            notionals.add(None)
    if len(notionals) == 1 and None not in notionals:
        scaled = shadow_usd * capital_usd / notionals.pop()
        out.update(shadow_pnl_usd_at_capital_usd=round(scaled, 2), difference_usd=round(paper - scaled, 2))
    else:
        out["rescaled"] = ("UNMEASURED: the shadow decisions on these sessions do not all carry one readable "
                           "notional_usd" if used else "UNMEASURED: no session to compare")
    return out


def sleeve_report(sleeve, rows_by_slug, shadow: dict, shadow_state: Path) -> dict:
    """One sleeve's verdict. `rows_by_slug` is sleeve_rows()'s dict, or an Unreadable."""
    stage = stage_of(sleeve)
    out = {"slug": sleeve.slug, "family": sleeve.family, "enabled": sleeve.enabled,
           "full_capital_usd": sleeve.full_capital_usd, "capital_usd": sleeve.capital_usd, "stage_in_file": stage,
           "shadow_clean_streak": shadow.get("clean_streak"), "shadow_eligible": shadow.get("eligible"),
           "edits": [], "missing": []}
    if isinstance(rows_by_slug, Unreadable):
        out.update(position_sessions=None, verdict=UNMEASURED, missing=[str(rows_by_slug)])
        if shadow.get("eligible") is False and sleeve.enabled:
            out["missing"].append(f"its shadow book has {shadow['clean_streak']} of {CLEAN_SESSIONS_TO_PROMOTE} "
                                  "clean sessions: if this sleeve has never held a position, the edit due is "
                                  f"\"enabled\": false for {sleeve.slug}")
        return out
    rows = rows_by_slug.get(sleeve.slug, [])
    held = [r for r in rows if r["_n"] > 0]
    T = len(held)
    out.update(position_sessions=T, rows=len(rows),
               first_position=held[0]["date"] if held else None, last_position=held[-1]["date"] if held else None)
    if rows:
        out["live_pnl_usd"] = float(rows[-1]["pnl"]) if rows[-1]["pnl"] != "" else None
        if out["live_pnl_usd"] is None:
            out["live_pnl_note"] = f"UNMEASURED: the {rows[-1]['date']} row has no pnl (a held name had no close)"
    # ---- the capital the ladder says
    if T < HALF_FROM:
        out.update(stage_due="QUARTER", capital_due=sleeve.full_capital_usd * STAGES["QUARTER"])
        if stage != "QUARTER":
            out["edits"].append(f"\"capital_usd\": {out['capital_due']!r} for {sleeve.slug} (now {sleeve.capital_usd!r})")
    elif T < FULL_FROM:
        out.update(stage_due=f"HALF if fills track the shadow book ({sleeve.full_capital_usd * STAGES['HALF']:,.2f})",
                   capital_due=None, tracking=tracking(rows, shadow, sleeve.capital_usd, shadow_state, sleeve.slug))
        out["missing"].append(NO_TRACK_RULE)
    else:
        out.update(stage_due="FULL, HALF or STOPPED by live P&L against -1 and -2 sigma x sqrt(T)", capital_due=None,
                   tracking=tracking(rows, shadow, sleeve.capital_usd, shadow_state, sleeve.slug))
        out["missing"].append(NO_SIGMA)
    # ---- the promotion gate, for a sleeve that has never held a position
    if T == 0 and sleeve.enabled:
        if not shadow.get("measured"):
            out["missing"].append(f"promotion gate: {shadow.get('why', 'no shadow record')}")
        elif not shadow["eligible"]:
            out["edits"].append(f"\"enabled\": false for {sleeve.slug} (its shadow book has {shadow['clean_streak']} "
                                f"of {CLEAN_SESSIONS_TO_PROMOTE} clean sessions and the sleeve has never held a position)")
    out["verdict"] = UNMEASURED if out["missing"] else CHANGE if out["edits"] else AGREE
    return out


# ------------------------------------------------------------------ the report

def build(book_path: Path, shadow_state: Path, events_state: Path) -> dict:
    try:
        cfg = config.load(book_path)
    except (OSError, ValueError) as e:        # ConfigError and a json error are ValueErrors
        raise PromoteError(f"the book file cannot be used: {e}") from None
    off = []
    for s in cfg.sleeves:
        try:
            stage_of(s)
        except PromoteError as e:
            off.append(str(e))
    if off:
        raise PromoteError("\n".join(off))
    notes = []
    try:
        slugs = shadow_slugs(shadow_state)
    except Unreadable as e:
        slugs, notes = [], [f"UNMEASURED: {e}"]
    shadow = {slug: shadow_book(shadow_state, slug) for slug in sorted(set(slugs) | set(cfg.slugs))}
    try:
        rows = sleeve_rows(events_state)
    except Unreadable as e:
        rows = e
        notes.append(f"UNMEASURED, every sleeve: {e}")
    sleeves = [sleeve_report(s, rows, shadow[s.slug], shadow_state) for s in cfg.sleeves]
    books = [{**{k: v for k, v in b.items() if k != "_rows"}, "is_sleeve": b["slug"] in cfg.slugs}
             for b in shadow.values()]
    code = (EXIT_UNMEASURED if any(s["verdict"] == UNMEASURED for s in sleeves)
            else EXIT_CHANGE if any(s["verdict"] == CHANGE for s in sleeves) else EXIT_AGREE)
    return {"book_file": str(book_path), "shadow_state": str(shadow_state), "events_state": str(events_state),
            "book": cfg.book, "notes": notes, "shadow_books": books, "sleeves": sleeves, "exit_code": code}


def _usd(v) -> str:
    return "UNMEASURED" if v is None else f"{v:,.2f}"


def render(rep: dict) -> str:
    out = [f"# Promotion and ladder report: the {rep['book']} book", "",
           f"Read-only. Book file `{rep['book_file']}`; shadow state `{rep['shadow_state']}`; events state "
           f"`{rep['events_state']}`. Shadow figures are SIMULATED. Rules: {RULING}.", ""]
    out += [f"**{n}**" for n in rep["notes"]] + ([""] if rep["notes"] else [])
    out += [f"## Shadow books: {CLEAN_SESSIONS_TO_PROMOTE} clean on-time sessions in a row to promote", "",
            "| book | sessions | clean | clean run to the last session | first | last | eligible | a sleeve |",
            "|---|---|---|---|---|---|---|---|"]
    for b in rep["shadow_books"]:
        sl = "yes" if b["is_sleeve"] else "no"
        if not b["measured"]:
            out.append(f"| {b['slug']} | UNMEASURED | UNMEASURED | UNMEASURED | | | UNMEASURED | {sl} |")
            continue
        run = f"{b['clean_streak']}" + (f" (from {b['streak_first']})" if b["clean_streak"] else "")
        out.append(f"| {b['slug']} | {b['sessions']} | {b['clean_total']} | {run} | {b['first'] or 'none'} | "
                   f"{b['last'] or 'none'} | {'YES' if b['eligible'] else 'no'} | {sl} |")
    for b in rep["shadow_books"]:
        if not b["measured"]:
            out.append(f"- {b['slug']}: UNMEASURED: {b['why']}")
        for u in b.get("unclean", []):
            out.append(f"- {b['slug']} {u['date']}: {u['kind']}: {u['why']}")
    out += ["", "## Sleeves: the ladder, in sessions with a position on paper", "",
            "| sleeve | family | enabled | position sessions | stage the ladder says | capital_usd it implies | "
            "capital_usd in the file | full size | shadow clean run | verdict |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for s in rep["sleeves"]:
        T = "UNMEASURED" if s["position_sessions"] is None else str(s["position_sessions"])
        gate = "UNMEASURED" if s["shadow_clean_streak"] is None else str(s["shadow_clean_streak"])
        out.append(f"| {s['slug']} | {s['family']} | {'yes' if s['enabled'] else 'no'} | {T} | "
                   f"{s.get('stage_due', 'UNMEASURED')} | {_usd(s.get('capital_due'))} | "
                   f"{_usd(s['capital_usd'])} ({s['stage_in_file'].lower()}) | {_usd(s['full_capital_usd'])} | "
                   f"{gate} | {s['verdict']} |")
    for s in rep["sleeves"]:
        for e in s["edits"]:
            out.append(f"- {s['slug']}: CHANGE NEEDED in ops/sleeves/events_sleeves.json: {e}")
        for m in s["missing"]:
            if f"UNMEASURED, every sleeve: {m}" in rep["notes"]:
                continue                               # said once, above the tables
            out.append(f"- {s['slug']}: UNMEASURED: {m}")
        t = s.get("tracking")
        if t and t["measured"]:
            scaled = (f"{t['shadow_pnl_usd_at_capital_usd']:+,.2f} at today's capital_usd (assumed on every session), "
                      f"difference {t['difference_usd']:+,.2f}" if "difference_usd" in t else t["rescaled"])
            out.append(f"- {s['slug']}: tracking, {t['sessions_compared']} session(s) compared, "
                       f"{len(t['sessions_skipped'])} skipped as unmeasured: paper {t['paper_pnl_usd']:+,.2f}; shadow "
                       f"{t['shadow_pnl_usd_at_shadow_notional']:+,.2f} at its own notional, {scaled}. No pass or fail: "
                       "the rule is not defined")
        elif t:
            out.append(f"- {s['slug']}: tracking UNMEASURED: {t['why']}")
        if "live_pnl_usd" in s:
            out.append(f"- {s['slug']}: live P&L to its last row {_usd(s['live_pnl_usd'])}"
                       + (f" ({s['live_pnl_note']})" if "live_pnl_note" in s else ""))
    word = {EXIT_AGREE: "AGREE", EXIT_CHANGE: "CHANGE NEEDED", EXIT_UNMEASURED: "UNMEASURED"}[rep["exit_code"]]
    out += ["", f"Exit {rep['exit_code']}: {word}.", ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m quantt.sleeves.promote", description=__doc__.split("\n\n")[0])
    ap.add_argument("--shadow-state", required=True, type=Path, help="the shadow runner's state directory")
    ap.add_argument("--events-state", required=True, type=Path, help="the events runner's state directory")
    ap.add_argument("--book-file", type=Path, default=BOOK_PATH, help="default: this clone's ops/sleeves/events_sleeves.json")
    ap.add_argument("--json", action="store_true", help="print the report as json")
    a = ap.parse_args(argv)
    try:
        rep = build(a.book_file, a.shadow_state, a.events_state)
    except PromoteError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return EXIT_REFUSED
    print(json.dumps(rep, indent=1, default=str) if a.json else render(rep))
    return rep["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
