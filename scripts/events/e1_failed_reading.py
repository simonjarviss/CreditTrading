"""DG-E1-3's reading pack and collector: the failed-deal census read by Claude Code subagents. Zero trials.

    python3 scripts/events/e1_failed_reading.py prepare --root <dir>
        # <dir>/input/: per-episode excerpts (part files), batches, INSTRUCTIONS.md, BRIEF_TEMPLATE.txt, plan.json
    python3 scripts/events/e1_failed_reading.py collect --root <dir> --model sonnet [--partial]
        # <dir>/out/<model>/*.json -> results/events/e1/e1_failed_deal_readings.csv (what Stage 0 reads),
        #   results/events/e1/e1_failed_reading_review.csv, tracked copies in results/events/e1/readings_raw/<model>/

WHY
---
E1's data gate DG-E1-3 (`results/events/PREREG_E1_MERGER_PAIR_2026-10-19.md` §4.3, §13) reads every
census candidate episode (273 on 2026-10-19; `e1_merger_pair.failed_census`), recording the outcome,
the first public filing announcing the deal and the filing that made a failure public, each with a
verbatim quote that the trial re-finds in the filing on every run. Reading R10, ruled 2026-10-20,
keeps all 273 (the counterparty is named only inside the filings). The coordinator, 2026-10-20: the
episodes are read by Sonnet subagents in batches, in the event-engine pilot's format
(`scripts/events/event_engine_pilot.py`), not by the agent that runs the trial.

WHAT A READER SEES, AND WHY AN EXCERPT
--------------------------------------
For each episode, every filing of `e1_merger_pair.CENSUS_FORMS` filed by or about the episode's CIK
from 30 days before its first filing to 730 days after (exactly what `fetch-edgar` cached), listed
with its date, form, accession and the parties its SGML header names (with their CIKs). The whole
filings run to gigabytes (7.9 GB for the 202 CIKs), so each filing is EXCERPTED by a fixed rule:
its first `HEAD_CHARS[form]` characters, plus up to `MAX_WINDOWS` windows of +-`WINDOW` characters
around outcome language (`OUTCOME_RE`), in that order of priority, within `EPISODE_CHARS` per
episode. The first filing and any RW, 8-K or DEFA14A come first. A filing or a window the budget
leaves out is LISTED as omitted, so a reader knows it has not seen it and writes null rather than
guessing. The rendering (`render`) only changes whitespace relative to `conditional_tender_census.plain`,
so a quote copied from the excerpt is found by `quote_in` in the raw filing (tested).

WHAT THE COLLECTOR DOES
-----------------------
It validates each reader's JSON (shape, the outcome vocabulary, every quote re-found in the RAW cached
filing it cites, every cited accession one of the episode's listed filings), takes each cited
filing's date from EDGAR's own filing list (a reader's date that disagrees is a problem, recorded),
assigns `deal_id` (target CIK > acquirer CIK, split when two announcements of one pair are more than
a year apart), sets `in_trial` = Y exactly when both parties are listed and the outcome is a failure,
and writes the readings file `e1_merger_pair.check_readings` validates. Problems never stop the
write: they go to the review file, and Stage 0's own check fails on them until they are resolved.
A missing reading is listed there too, and `--partial` is required to collect while any is missing.

Tests: scripts/events/tests/test_e1_failed_reading.py (synthetic filings; no network).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.events import e1_merger_pair as e1  # noqa: E402

CHARS_PER_TOKEN = 2.692307692307692   # event_engine_score.CHARS_PER_TOKEN, the design's estimate [S]
BATCH_TOKENS = 90_000                 # the pilot's per-subagent input cap (event_engine_pilot.BATCH_TOKENS)
BATCH_MAX_EPISODES = 10
EPISODE_CHARS = 40_000               # the budget for full excerpts; every filing first gets a compact one
EPISODE_MAX = 200_000                # an episode with many filings may grow to this (~74k tokens, one batch)
COMPACT_HEAD = 800                   # a compact excerpt: the lead and the strong outcome windows only
COMPACT_WINDOW = 400
COMPACT_MAX_WINDOWS = 2
PART_CHARS = 30_000                   # one Read call each (the pilot's PART_CHARS)
WRAP_AT = 1_000
WINDOW = 600
MAX_WINDOWS = 3
HEAD_CHARS = {"RW": 4_000, "8-K": 4_000, "DEFA14A": 3_000, "425": 3_000}
HEAD_DEFAULT = 2_500                  # N-14s, proxies, N-8F: the cover and letter state the deal
EXHIBIT_HEAD = 3_000                  # an 8-K's or 425's press release (EX-99*)
FIRST_PRIORITY = ("RW", "8-K", "DEFA14A")
# Outcome language, strongest first. Boilerplate ("the Agreement may be terminated") also matches the
# weaker patterns, which is why windows are capped and the strong patterns are taken first.
OUTCOME_RE = (
    re.compile(r"withdr[ae]wn?|withdraw(?:al|ing)|abandon|will not (?:proceed|be (?:consummated|completed))|"
               r"did not (?:approve|receive|obtain|achieve)|(?:was|were|has been|have been) not approved|"
               r"failed to (?:approve|obtain|receive|achieve)|insufficient (?:votes|number)|lack of (?:a )?quorum|"
               r"(?:has|have|had) (?:mutually )?(?:agreed to )?terminated|(?:was|were) terminated|no longer (?:be )?pursu", re.I),
    re.compile(r"(?:was|were|has been|have been) (?:successfully )?(?:completed|consummated)|completed the (?:reorganization|merger)|"
               r"consummation of the (?:reorganization|merger)|approved (?:by|the) (?:the )?(?:shareholders|stockholders)|"
               r"adjourn|postpone", re.I),
)
READER_OUTCOMES = tuple(o for o in e1.OUTCOMES if o != "completed_after_crsp")
_TAG_RE = re.compile(r"<[^>]{0,400}>")       # conditional_tender_census._TAG_RE, the same rule
_BLOCK_TAGS = re.compile(r"^</?(?:p|div|br|tr|li|h[1-6]|table|center|pre|ul|ol)\b", re.I)


# ============================================================ rendering and excerpts

def render(text: str) -> str:
    """HTML/SGML -> readable text that differs from `plain(text)` in whitespace only: tags become a
    space (block tags a line break), entities are decoded AFTER tags are removed (plain's order),
    spaces collapse within lines, blank lines go. So normalise(render(x)) == normalise(x)."""
    t = _TAG_RE.sub(lambda m: "\n" if _BLOCK_TAGS.match(m.group(0)) else " ", text)
    t = html.unescape(t)
    lines = (re.sub(r"[ \t\r\f\v ]+", " ", ln).strip() for ln in t.split("\n"))
    return "\n".join(ln for ln in lines if ln) + "\n"


def wrap_long_lines(text: str, width: int = WRAP_AT) -> str:
    """Break lines longer than `width` at spaces only (whitespace-only, so quotes are unaffected)."""
    out = []
    for ln in text.split("\n"):
        while len(ln) > width:
            cut = ln.rfind(" ", 0, width)
            if cut <= 0:
                cut = ln.find(" ", width)
                if cut < 0:
                    break
            out.append(ln[:cut])
            ln = ln[cut + 1:]
        out.append(ln)
    return "\n".join(out)


def sgml_parties(raw: str) -> list[dict]:
    """The parties the SGML header names: [{role, name, cik}] (SUBJECT COMPANY, FILED BY, FILER)."""
    head = raw.split("</SEC-HEADER>")[0]
    out = []
    for m in re.finditer(r"^(SUBJECT COMPANY|FILED BY|FILER):\s*(.*?)(?=^(?:SUBJECT COMPANY|FILED BY|FILER):|\Z)",
                         head, re.M | re.S):
        nm = re.search(r"COMPANY CONFORMED NAME:\s*(.+)", m.group(2))
        ck = re.search(r"CENTRAL INDEX KEY:\s*(\d+)", m.group(2))
        if nm and ck:
            out.append({"role": m.group(1), "name": nm.group(1).strip(), "cik": int(ck.group(1))})
    return out


def documents(raw: str) -> list[tuple[str, str]]:
    """[(type, text)] of a complete submission's <DOCUMENT> blocks."""
    out = []
    for block in raw.split("<DOCUMENT>")[1:]:
        m = re.search(r"<TYPE>([^\n<]+)", block)
        t = block.split("<TEXT>", 1)[1] if "<TEXT>" in block else block
        out.append(((m.group(1).strip().upper() if m else ""), t.split("</TEXT>", 1)[0]))
    return out


def _cut(text: str, n: int) -> str:
    """The first `n` characters, cut back to a line break (the whole text if shorter)."""
    if len(text) <= n:
        return text
    c = text.rfind("\n", 0, n)
    return text[:c + 1] if c > 0 else text[:n]


def windows(text: str, start_after: int, width: int = WINDOW, cap: int = MAX_WINDOWS,
            strong_only: bool = False) -> list[tuple[int, int, str]]:
    """Up to `cap` (start, end, pattern label) around OUTCOME_RE matches after `start_after`,
    strongest pattern first, merged where they overlap."""
    picked: list[tuple[int, int, str]] = []
    pats = list(zip(("outcome", "outcome-weak"), OUTCOME_RE))[: 1 if strong_only else 2]
    for lab, rx in pats:
        for m in rx.finditer(text, start_after):
            a, b = max(start_after, m.start() - width), min(len(text), m.end() + width)
            if any(a < q and b > p for p, q, _ in picked):
                continue
            picked.append((a, b, lab))
            if len(picked) >= cap:
                return sorted(picked)
    return sorted(picked)


def excerpt_filing(raw: str, form: str, compact: bool = False, heads: dict | None = None) -> tuple[str, dict]:
    """One filing's excerpt: its main document's head, its press-release exhibits' heads (8-K, 425,
    DEFA14A), then the outcome windows; returns (text, stats). `compact`: the lead (COMPACT_HEAD)
    and at most COMPACT_MAX_WINDOWS windows of strong outcome language only."""
    docs = documents(raw)
    main = [t for ty, t in docs if ty == form.upper()] or [docs[0][1] if docs else ""]
    body = render(main[0])
    head_n = COMPACT_HEAD if compact else {**HEAD_CHARS, **(heads or {})}.get(form, HEAD_DEFAULT)
    ex_n = COMPACT_HEAD if compact else EXHIBIT_HEAD
    parts = [f"--- start of the document (first {min(head_n, len(body)):,} of {len(body):,} characters) ---\n",
             _cut(body, head_n)]
    shown = len(_cut(body, head_n))
    ex_texts = []
    if form in ("8-K", "425", "DEFA14A"):
        for ty, t in docs:
            if ty.startswith("EX-99"):
                r = render(t)
                ex_texts.append(r)
                parts += [f"--- exhibit {ty} (first {min(ex_n, len(r)):,} of {len(r):,} characters) ---\n",
                          _cut(r, ex_n)]
    wins = (windows(body, shown, COMPACT_WINDOW, COMPACT_MAX_WINDOWS, strong_only=True) if compact
            else windows(body, shown))
    for a, b, lab in wins:
        # cut to whole words so a window never starts or ends inside one
        a2 = body.rfind(" ", 0, a) + 1 if a > shown else a
        b2 = body.find(" ", b) if body.find(" ", b) > 0 else b
        parts += [f"--- excerpt at characters {a2:,}-{b2:,} of the document ({lab} language) ---\n", body[a2:b2], "\n"]
    return "".join(parts), {"doc_chars": len(body), "exhibit_chars": sum(len(x) for x in ex_texts),
                            "strong": bool(OUTCOME_RE[0].search(body) or any(OUTCOME_RE[0].search(x) for x in ex_texts)),
                            "body_sha": hashlib.sha256(body.encode()).hexdigest()}


# ============================================================ the pack

def episode_filings(client, cik: int, first_date, forms: tuple = e1.CENSUS_FORMS) -> pd.DataFrame:
    """The episode's census filings from EDGAR's filing list (cached by `fetch-edgar`)."""
    from scripts.data import fetch_edgar_events as fe
    sb = fe.submissions(client, int(cik), max_age_s=None)
    f0 = pd.Timestamp(first_date)
    sb = sb[sb["form"].isin(forms) & (sb["filingDate"] >= f0 - pd.Timedelta(days=e1.CENSUS_PRE_DAYS))
            & (sb["filingDate"] <= f0 + pd.Timedelta(days=e1.FAIL_WINDOW_DAYS))]
    return sb.sort_values(["filingDate", "accessionNumber"]).reset_index(drop=True)


def episode_text(client, ep: pd.Series, budget: int = EPISODE_CHARS, heads: dict | None = None,
                 forms: tuple = e1.CENSUS_FORMS) -> tuple[str, list[dict]]:
    """The episode's reading text and its filing list, with what each filing shows.

    Every filing gets at least a COMPACT excerpt (its lead and strong outcome language), so no
    filing in the window is unseen; a filing whose main text is identical to an earlier one's (the
    same press release filed again) points to it instead. The budget is EPISODE_CHARS, raised for
    an episode whose compact excerpts alone exceed it (up to EPISODE_MAX). What is left upgrades
    filings to their FULL excerpt in priority order: the episode's first filing, filings with strong
    outcome language, RW / 8-K / DEFA14A, then the rest by date."""
    from scripts.data.edgar_client import filing_txt_url
    fl = episode_filings(client, int(ep["episode_cik"]), ep["first_date"], forms)
    first = ep["episode_accession"]
    recs = []
    for seq, r in enumerate(fl.itertuples(), 1):
        rec = {"seq": seq, "date": str(r.filingDate.date()), "form": r.form, "accession": r.accessionNumber}
        try:
            raw = client.get_text(filing_txt_url(int(ep["episode_cik"]), r.accessionNumber))
        except Exception as ex:
            recs.append({**rec, "included": False, "why": f"not cached ({type(ex).__name__})"})
            continue
        full, st = excerpt_filing(raw, r.form, heads=heads)
        comp, _ = excerpt_filing(raw, r.form, compact=True)
        parties = "; ".join(f"{p['role']} {p['name']} (CIK {p['cik']})" for p in sgml_parties(raw))
        line = (f"\n===== FILING seq={seq} | form {r.form} | filed {r.filingDate.date()} | accession "
                f"{r.accessionNumber} | {parties} =====\n")
        recs.append({**rec, "included": True, "why": None, "parties": parties, "_line": line, "_full": full,
                     "_comp": comp, "_strong": st["strong"], "_sha": st["body_sha"]})
    seen: dict[str, int] = {}
    for x in recs:
        if x["included"]:
            if x["_sha"] in seen and x["accession"] != first:
                x.update(included=False, why=f"identical text to seq={seen[x['_sha']]}")
            else:
                seen.setdefault(x["_sha"], x["seq"])
    live = [x for x in recs if x["included"]]
    compact_total = sum(len(x["_line"]) + len(x["_comp"]) for x in live)
    budget = min(max(budget, compact_total), EPISODE_MAX)
    pri = sorted(live, key=lambda x: (0 if x["accession"] == first else 1 if x["_strong"] else
                                      2 if x["form"] in FIRST_PRIORITY else 3, x["date"]))
    used = 0
    for x in pri:                                    # compact for all, in priority order, while it fits
        n = len(x["_line"]) + len(x["_comp"])
        if used + n > EPISODE_MAX:
            x.update(included=False, why="omitted: even compact excerpts exceed the episode's maximum")
            continue
        x["show"], x["mode"] = x["_comp"], "compact"
        used += n
    for x in pri:                                    # then upgrade to the full excerpt while the budget allows
        if not x["included"]:
            continue
        extra = len(x["_full"]) - len(x["_comp"])
        if used + extra <= budget:
            x["show"], x["mode"] = x["_full"], "full"
            used += extra
    head = [f"EPISODE cik={int(ep['episode_cik'])} first filing {ep['first_date']} ({ep['first_form']}, "
            f"{first}); EDGAR's last name for this CIK: {ep['company_last']}\n"]
    if first not in {x["accession"] for x in recs}:
        head.append(f"NOTE: the episode's first filing ({ep['first_form']}, {first}) is not among the fetched "
                    "forms, so it is not in this excerpt.\n")
    head.append("FILINGS IN THE WINDOW (seq | filed | form | accession | shown):\n")
    for x in recs:
        how = (f"{x['mode']} excerpt" if x["included"] else x["why"])
        head.append(f"  {x['seq']:>3} | {x['date']} | {x['form']} | {x['accession']} | {how}\n")
    body = "".join(x["_line"] + x["show"] for x in recs if x["included"])
    listed = [{k: v for k, v in x.items() if not k.startswith("_") and k not in ("show",)} for x in recs]
    return wrap_long_lines("".join(head) + body), listed


def split_parts(text: str, max_chars: int = PART_CHARS) -> list[str]:
    parts, cur, n = [], [], 0
    for ln in text.split("\n"):
        if cur and n + len(ln) + 1 > max_chars:
            parts.append("\n".join(cur) + "\n")
            cur, n = [], 0
        cur.append(ln)
        n += len(ln) + 1
    if cur:
        parts.append("\n".join(cur) + "\n")
    return parts


def plan_batches(sizes: dict[str, int], order: list[str]) -> list[list[str]]:
    """First-fit decreasing on estimated tokens, capped by BATCH_TOKENS and BATCH_MAX_EPISODES; deterministic."""
    items = sorted(order, key=lambda a: (-sizes[a], order.index(a)))
    bins: list[list[str]] = []
    load: list[float] = []
    for a in items:
        t = sizes[a] / CHARS_PER_TOKEN
        if t > BATCH_TOKENS:
            raise ValueError(f"{a}: {t:.0f} estimated tokens exceeds one batch")
        for i, b in enumerate(bins):
            if load[i] + t <= BATCH_TOKENS and len(b) < BATCH_MAX_EPISODES:
                b.append(a)
                load[i] += t
                break
        else:
            bins.append([a])
            load.append(t)
    return [sorted(b, key=order.index) for b in bins]


def ep_id(cik, acc) -> str:
    return f"{int(cik)}_{acc}"


INSTRUCTIONS = """\
# E1 failed-deal census: reader instructions (2026-10-20)

You read EDGAR filings about one proposed fund merger at a time ("an episode") and record what
they say happened. Your readings decide which proposed mergers between listed closed-end funds
FAILED, which a backtest then includes. A wrong value is worse than a null: **write null whenever
the text in front of you does not state the answer.**

## What you are given

* An episode is the merger filings of ONE fund (its EDGAR CIK), from 30 days before its first
  merger filing to 730 days after. Its text (split into parts `<cik>_<accession>.partNN.txt`)
  starts with a list of every filing in that window (form, date, accession) and how each is
  shown below:
  - a **full excerpt**: the start of the main document, the start of any press-release exhibit
    (8-K, 425, DEFA14A), and up to three passages around outcome language;
  - a **compact excerpt**: the document's first lines and up to two passages around strong
    outcome language only;
  - **identical text to seq=K**: the same document filed again, shown once.

  Each filing appears as
  `===== FILING seq=N | form ... | filed YYYY-MM-DD | accession ... | <parties with CIKs> =====`.
  **Text outside an excerpt is not in front of you: do not assume what it says.** A late filing
  in the list may carry the outcome, so look at every filing's excerpt before deciding.
* The parties line comes from EDGAR's header: SUBJECT COMPANY is the fund the filing is about;
  FILED BY or FILER is who filed it. Use these CIKs.

## What to record for each episode

Write `<cik>_<accession>.json` (the episode's id, as your batch file gives it):

```json
{
  "episode_cik": 3906,
  "episode_accession": "0001104659-09-060229",
  "episode_role": "target",
  "deals": [
    {
      "target":   {"name": "...", "cik": 1234, "ticker": "ABC"},
      "acquirer": {"name": "...", "cik": 5678, "ticker": "XYZ"},
      "both_listed": true,
      "listed_quote": {"accession": "...", "quote": "..."},
      "outcome": "terminated",
      "announcement": {"accession": "...", "date": "YYYY-MM-DD", "quote": "..."},
      "outcome_evidence": {"accession": "...", "date": "YYYY-MM-DD", "quote": "..."},
      "notes": ""
    }
  ],
  "problems": ""
}
```

Field by field:

* `episode_role`: what this episode's fund (`episode_cik`) is in the merger: `"target"` (it would
  be absorbed: its shareholders would receive the other fund's shares), `"acquirer"` (the
  surviving fund that issues shares), or `"other"`; null if the text does not say.
* `deals`: one entry per target-acquirer pair the filings propose. A filing that merges three
  funds into one acquirer is three deals. Use an empty list only if no merger of this fund is
  described at all, and then say so in `problems`.
* `target` / `acquirer`: the name as written, the CIK from a FILING header line (null if neither
  party's CIK appears), and the exchange ticker only as printed (for example "(NYSE: ABC)" gives
  "ABC"); null when not printed.
* `both_listed`: true only if the text shows BOTH funds are closed-end funds or business
  development companies whose shares trade on a stock exchange (for example a ticker with
  "NYSE" or "NYSE American" or "Nasdaq" for each, or "listed on the New York Stock Exchange").
  false if either is an open-end fund (mutual fund), an ETF, a non-traded or unlisted fund, an
  interval fund, or an operating company. null if the text does not settle it. Give the quote
  that settles it in `listed_quote` (null when null).
* `outcome`, exactly one of:
  - `"completed"`: the text states the merger was completed (closed, consummated, became effective);
  - `"completed_other_structure"`: a merger of these funds was completed, but in a different form
    from the one first proposed (a different acquirer or survivor, or cash instead of shares);
  - `"terminated"`: the funds or their boards terminated the agreement, or abandoned or ended the proposal;
  - `"vote_failed"`: the shareholder vote did not approve it, or could not reach a quorum, and it was not completed;
  - `"withdrawn"`: the registration or proxy was withdrawn (form RW, or text saying so) and the merger was not completed;
  - `"superseded"`: the proposal was replaced by a different merger proposal for the same fund;
  - `"not_a_listed_pair"`: `both_listed` is false;
  - **an N-8F** (a fund's application to deregister) is evidence only of how the fund ended: if the
    TARGET's N-8F states that it merged into the named acquirer, the outcome is `"completed"`; if it
    names a different surviving fund, or a liquidation, `"completed_other_structure"`; if it names
    neither, it settles nothing (null unless another filing does). An N-8F never shows a failure
    (team lead's rule, 2026-10-20);
  - `null`: the excerpts do not say how it ended. **This is the right answer whenever the
    outcome is not stated in front of you**; do not infer completion from silence.
* `announcement`: the earliest filing in the excerpt that publicly announces this proposed
  merger. Give its accession and filed date exactly as the FILING line gives them, and a quote
  of one or two sentences that names the merger. null if none of the excerpted filings
  announces it.
* `outcome_evidence`: the filing that first states the outcome above (for a failure, the filing
  that makes the failure public). Give its accession and filed date from the FILING line, and the
  sentence(s) stating it. null when `outcome` is null.
* `notes`: anything a second reader needs (for example "vote adjourned three times, then the
  merger was terminated").

## Quotes

Copy every quote character for character from the part files. Line breaks may be written as
single spaces, and a quote may run across two parts (join them with one space). Never
paraphrase, never fix typos, and never quote text that is not in the parts. Each quote is
checked against the filing. Quote only the filings' own text: never the `===== FILING` lines,
the filing list or the `---` markers, which this pack writes (the CIKs and dates in them are for
your fields, not for quotes).

## How to work

* Read every part file of an episode in full, in order, with the Read tool, before you write its
  JSON. Do not use Grep, Glob or any search, and do not read only part of a file.
* Use no outside knowledge of these funds, sponsors or deals. Only the text counts.
* Open only this file, your batch file and the part files your batch lists. Write only into
  the output directory your brief names. No network, no web, no `sudo`, no `ssh`. Never open
  `config/.env`, any key or credential file, or anything under the repository. Do not start
  other agents.
* **The only shell command you may run** is this parse check, once for each file you write, on that
  one file, by its full path, right after you write it:
  `python3 -c "import json,sys; json.load(open(sys.argv[1]))" <ROOT>/out/<MODEL>/<episode id>.json`
  (your brief gives ROOT and MODEL; for the batch summary the file is `_batch_<NN>.json`). Never
  put a wildcard (`*`, `?`), a directory or another reader's file in it, and never run anything
  else: no `ls`, `cat`, `find`, `grep`, `head`, no other `python3`, no loop over files.
* After your last episode, write `_batch_<NN>.json` in the output directory:
  `{"batch": "<NN>", "model_id": "<your exact model ID>", "episodes": ["<cik>_<accession>", ...],
  "parts_read": <number>, "problems": "<anything that troubled you, or empty>"}`.
"""

R2_ADDENDUM = """\
# Second reading (2026-10-20): read this page first; it overrides what follows where they differ

These episodes were read once, and that reading could not settle whether a deal between two listed
funds failed (the team lead's ruling 8). This time every filing is shown in its FULL excerpt
wherever the episode's size allows (the filing list says which). Give every deal an outcome if any
filing in front of you states one; null is still the right answer when none does. A second deal of
the same pair (for example a 2025 re-proposal) is a separate deal.

---

"""

N8F_ADDENDUM = """\
# N-8F re-reading (2026-10-20): read this page first; it overrides what follows where they differ

These episodes are read again under the team lead's N-8F rule (ruling 6, 2026-10-20), given in
the outcome definitions below. Earlier readers applied it two ways. Read every filing, record every
deal as before, and apply the rule exactly: an N-8F can make a deal `completed` or
`completed_other_structure`, never a failure, and an N-8F that names no merger settles nothing.

---

"""

R3_ADDENDUM = """\
# Third reading (2026-10-21): read this page first; it overrides what follows where they differ

Two readings could not settle these episodes (the team lead's rulings 8 and 10). Your batch file
gives each episode a `focus`: the question still open, for example the filing that makes a failed
merger public, whether both funds are exchange-listed, or how a deal ended. Read every filing in
full first, then answer the focus if any filing states it, with its quote. Record every deal as
before; the JSON shape is unchanged. null is still the right answer when no filing states it.

---

"""

SUPP_ADDENDUM = """\
# Supplementary census (2026-10-20): read this page first; it overrides what follows where they differ

Each episode here belongs to an ACQUIRING fund whose merger filings led to at least one completed
merger (the team lead's ruling 9). A single proposal often names several target funds, and one of
them can fail (for example a shareholder vote that did not pass for one target while the others
merged). Record EVERY target fund the filings name for this acquirer, each as its own deal with its
own outcome. The question that matters is which named targets did NOT complete: say so only when a
filing states it, and give its quote.

---

"""

BRIEF = """\
You are a reader for QUANTT's E1 failed-merger census (DG-E1-3, 2026-10-20). Do exactly this and nothing else.

1. Read {ROOT}/input/INSTRUCTIONS.md in full with the Read tool. It binds you.
2. Read {ROOT}/input/batches/batch_{NN}.json. It lists your episodes in order, each with its part files. Your output directory is {ROOT}/out/{MODEL}/.
3. For each episode, in the listed order: read every one of its part files in full, in order, with the Read tool; then write {ROOT}/out/{MODEL}/<episode id>.json in the shape INSTRUCTIONS.md gives (null wherever the text does not state the answer); then run exactly this, on that one file only:
   python3 -c "import json,sys; json.load(open(sys.argv[1]))" {ROOT}/out/{MODEL}/<episode id>.json
4. Write {ROOT}/out/{MODEL}/_batch_{NN}.json as INSTRUCTIONS.md describes, with your exact model ID, and run the same command on {ROOT}/out/{MODEL}/_batch_{NN}.json.

Forbidden: opening any other file or directory (in particular anything under the repository, other batches' outputs, and config/.env or any key file); Grep, Glob or any search; any shell command other than the parse check above on a file you just wrote (never a wildcard, a directory, ls, cat or any other command); network or web access; sudo; ssh; starting agents; using outside knowledge of these funds or deals.

Hand back one line: batch {NN}, your model ID, the number of JSON files written, and any problem.
"""


ROUNDS = {
    # round: (output file, review file, episode list file, budget, form heads, addendum)
    "r1": ("e1_failed_deal_readings.csv", "e1_failed_reading_review.csv", None, EPISODE_CHARS, None, ""),
    "r2": ("e1_failed_deal_readings_r2.csv", "e1_failed_reading_review_r2.csv", "e1_reading_round_r2.csv",
           EPISODE_MAX, None, "R2"),
    "n8f": ("e1_failed_deal_readings_n8f.csv", "e1_failed_reading_review_n8f.csv", "e1_reading_round_n8f.csv",
            EPISODE_MAX, {"N-8F": 20_000}, "N8F"),
    "supp": ("e1_failed_deal_readings_supp.csv", "e1_failed_reading_review_supp.csv", None, EPISODE_CHARS, None, "SUPP"),
    "r3": ("e1_failed_deal_readings_r3.csv", "e1_failed_reading_review_r3.csv", "e1_reading_round_r3.csv",
           EPISODE_MAX, {"N-8F": 20_000}, "R3"),
    # one fund's own filings for a deal its counterparty's filings leave open (SBI -> MMU, 2026-10-21)
    "r4": ("e1_failed_deal_readings_r4.csv", "e1_failed_reading_review_r4.csv", "e1_reading_round_r4.csv",
           EPISODE_MAX, {"N-CSR": 6_000, "N-CSRS": 6_000}, "R3"),
}


def round_census(rnd: str) -> pd.DataFrame:
    """The episodes a round reads: r1 the census; supp the supplementary census (ruling 9); r2 and n8f
    the episode lists their `prepare-*` commands froze in results/events/e1/."""
    if rnd == "r1":
        return pd.read_csv(e1.CENSUS)
    if rnd == "supp":
        return pd.read_csv(e1.CENSUS_SUPP)
    if rnd == "r4":       # its own list: a fund outside every census, read for one deal
        return pd.read_csv(e1.OUT_DIR / ROUNDS[rnd][2])
    ids = pd.read_csv(e1.OUT_DIR / ROUNDS[rnd][2], dtype=str)
    cen = pd.concat([pd.read_csv(e1.CENSUS), pd.read_csv(e1.CENSUS_SUPP)] if e1.CENSUS_SUPP.exists()
                    else [pd.read_csv(e1.CENSUS)], ignore_index=True)
    key = cen["episode_cik"].astype(str) + "_" + cen["episode_accession"]
    out = cen[key.isin(ids["episode"])].drop_duplicates(["episode_cik", "episode_accession"])
    if len(out) != len(ids):
        raise e1.GateError(f"round {rnd}: {len(ids) - len(out)} listed episode(s) are in no census")
    return out.reset_index(drop=True)


def prepare(root: Path, client=None, rnd: str = "r1") -> dict:
    """Write <root>/input/ (parts, batches, instructions, brief, plan) and <root>/out/ for one round."""
    client = client or e1.edgar_client(online=False)
    cen = round_census(rnd)
    _, _, _, budget, heads, add = ROUNDS[rnd]
    addendum = {"": "", "R2": R2_ADDENDUM, "N8F": N8F_ADDENDUM, "SUPP": SUPP_ADDENDUM, "R3": R3_ADDENDUM}[add]
    focus = {}
    if ROUNDS[rnd][2] and (e1.OUT_DIR / ROUNDS[rnd][2]).exists():
        fl = pd.read_csv(e1.OUT_DIR / ROUNDS[rnd][2], dtype=str, keep_default_na=False)
        focus = dict(zip(fl["episode"], fl["focus"])) if "focus" in fl else {}
    inp = root / "input"
    parts_dir, batch_dir = inp / "episodes", inp / "batches"
    for d in (parts_dir, batch_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    (root / "out").mkdir(parents=True, exist_ok=True)
    order, sizes, files, listed, hashes = [], {}, {}, {}, {}
    for _, ep in cen.iterrows():
        i = ep_id(ep["episode_cik"], ep["episode_accession"])
        txt, lst = episode_text(client, ep, budget=budget, heads=heads,
                                forms=e1.TARGETED_FORMS if rnd == "r4" else e1.CENSUS_FORMS)
        parts = split_parts(txt)
        names = []
        for k, p in enumerate(parts, 1):
            fn = parts_dir / f"{i}.part{k:02d}.txt"
            fn.write_text(p)
            names.append(str(fn))
            hashes[fn.name] = hashlib.sha256(p.encode()).hexdigest()
        order.append(i)
        sizes[i], files[i], listed[i] = len(txt), names, lst
    batches = plan_batches(sizes, order)
    plan = {"made": str(date.today()), "round": rnd, "episodes": len(order), "episode_budget_chars": budget,
            "episode_chars_cap": EPISODE_CHARS, "batch_tokens_cap_est": BATCH_TOKENS,
            "chars_per_token_assumed": CHARS_PER_TOKEN, "batches": [], "filings": listed}
    for b_i, b in enumerate(batches, 1):
        nn = f"{b_i:02d}"
        rec = {"batch": nn, "episodes": [{"id": i, "parts": files[i], "chars": sizes[i],
                                          **({"focus": focus[i]} if focus.get(i) else {})} for i in b],
               "est_input_tokens": round(sum(sizes[i] for i in b) / CHARS_PER_TOKEN)}
        (batch_dir / f"batch_{nn}.json").write_text(json.dumps(
            {**rec, "output_dir": "<ROOT>/out/<MODEL>/ as your brief names it"}, indent=1))
        plan["batches"].append(rec)
    (inp / "INSTRUCTIONS.md").write_text(addendum + INSTRUCTIONS)
    (inp / "BRIEF_TEMPLATE.txt").write_text(BRIEF)
    plan["part_sha256"] = hashes
    (inp / "plan.json").write_text(json.dumps(plan, indent=1, default=str))
    return plan


# ============================================================ collect

def validate(x: dict, eid: str, listed: list[dict], raw_text) -> list[str]:
    """Problems with one reader JSON. `raw_text(accession)` returns the raw cached filing."""
    from scripts.events.conditional_tender_census import quote_in
    p = []
    cik, acc = eid.split("_", 1)
    if str(x.get("episode_cik")) != cik or x.get("episode_accession") != acc:
        p.append("episode id differs from the file name")
    deals = x.get("deals")
    if not isinstance(deals, list):
        return p + ["deals is not a list"]
    if not deals:
        p.append("no deal recorded")
    dates = {f["accession"]: f["date"] for f in listed}
    shown = {f["accession"] for f in listed if f.get("included")}
    for k, d in enumerate(deals):
        o = d.get("outcome")
        if o is not None and o not in READER_OUTCOMES:
            p.append(f"deal {k}: outcome {o!r} is not in the vocabulary")
        if o is None:
            p.append(f"deal {k}: outcome not stated in the excerpts")
        if d.get("both_listed") is False and o not in (None, "not_a_listed_pair"):
            p.append(f"deal {k}: both_listed false but outcome {o!r}")
        for f in ("listed_quote", "announcement", "outcome_evidence"):
            q = d.get(f)
            if not q:
                continue
            a = q.get("accession")
            if a not in shown:
                p.append(f"deal {k}: {f} cites {a}, not an excerpted filing of this episode")
                continue
            if f != "listed_quote" and q.get("date") not in (None, dates.get(a)):
                p.append(f"deal {k}: {f} date {q.get('date')} differs from EDGAR's {dates.get(a)}")
            if not q.get("quote") or not quote_in(raw_text(a), q["quote"]):
                p.append(f"deal {k}: {f} quote not found in {a}")
    return p


def to_rows(x: dict, eid: str, listed: list[dict], read_by: str, read_on: str) -> list[dict]:
    """One readings row per deal (an episode with no deal gives one row with a blank outcome)."""
    cik, acc = eid.split("_", 1)
    dates = {f["accession"]: f["date"] for f in listed}
    rows = []
    for k, d in enumerate(x.get("deals") or [None]):
        d = d or {}
        t, a = d.get("target") or {}, d.get("acquirer") or {}
        o = d.get("outcome") or ""
        bl = {True: "Y", False: "N"}.get(d.get("both_listed"), "")
        ann, ev = d.get("announcement") or {}, d.get("outcome_evidence") or {}
        failed = o in e1.FAILED_OUTCOMES
        me_target = str(t.get("cik")) == cik
        cp = a if me_target else t
        rows.append({
            "episode_cik": cik, "episode_accession": acc, "deal_id": "",
            "role": x.get("episode_role") or "", "counterparty_cik": cp.get("cik") or "",
            "counterparty_name": cp.get("name") or "", "both_listed": bl, "outcome": o,
            "in_trial": "Y" if (failed and bl == "Y") else "N",
            "target_cik": t.get("cik") or "", "acquirer_cik": a.get("cik") or "",
            "target_ticker": t.get("ticker") or "", "acquirer_ticker": a.get("ticker") or "",
            "ann_date": dates.get(ann.get("accession"), "") if ann else "", "ann_accession": ann.get("accession") or "",
            "ann_quote": ann.get("quote") or "",
            "fail_date": dates.get(ev.get("accession"), "") if (failed and ev) else "",
            "fail_accession": (ev.get("accession") or "") if failed else "",
            "fail_quote": (ev.get("quote") or "") if failed else "",
            "outcome_date": dates.get(ev.get("accession"), "") if ev else "",
            "outcome_accession": ev.get("accession") or "", "outcome_quote": ev.get("quote") or "",
            "read_by": read_by, "read_on": read_on, "_k": k})
    return rows


def assign_deal_ids(R: pd.DataFrame) -> pd.Series:
    """target CIK > acquirer CIK; a pair announced twice more than a year apart is two deals (#2, ...);
    a deal with a party's CIK unknown is its own deal (ep<cik>:<k>)."""
    ids = pd.Series("", index=R.index)
    known = (R["target_cik"].astype(str) != "") & (R["acquirer_cik"].astype(str) != "")
    for pair, g in R[known].groupby([R["target_cik"].astype(str), R["acquirer_cik"].astype(str)]):
        base = f"{pair[0]}>{pair[1]}"
        d = pd.to_datetime(g["ann_date"].replace("", None))
        order = d.sort_values(na_position="last").index
        n, last = 1, None
        for ix in order:
            if last is not None and pd.notna(d[ix]) and (d[ix] - last).days > 365:
                n += 1
            if pd.notna(d[ix]):
                last = d[ix]
            ids[ix] = base if n == 1 else f"{base}#{n}"
    for ix in R.index[~known]:
        ids[ix] = f"ep{R.at[ix, 'episode_cik']}:{R.at[ix, '_k']}"
    # Two deals of ONE episode on one CIK pair (the series of one trust share a CIK) stay two deals.
    ep = R["episode_cik"].astype(str) + "|" + R["episode_accession"].astype(str)
    dup = ids.groupby([ep, ids]).cumcount()
    ids[dup > 0] = ids[dup > 0] + "/" + (dup[dup > 0] + 1).astype(str)
    return ids


def collect(root: Path, model: str, partial: bool, client=None, rnd: str | None = None) -> dict:
    from scripts.data.edgar_client import filing_txt_url
    client = client or e1.edgar_client(online=False)
    plan = json.loads((root / "input" / "plan.json").read_text())
    rnd = rnd or plan.get("round", "r1")
    if plan.get("round", "r1") != rnd:
        raise e1.GateError(f"{root} is round {plan.get('round', 'r1')!r}, not {rnd!r}")
    out_csv = e1.READINGS if rnd == "r1" else e1.OUT_DIR / ROUNDS[rnd][0]
    review_csv = e1.OUT_DIR / ROUNDS[rnd][1]
    src = root / "out" / model
    batch_of = {e["id"]: b["batch"] for b in plan["batches"] for e in b["episodes"]}
    model_ids = {}
    for f in src.glob("_batch_*.json"):
        j = json.loads(f.read_text())
        model_ids[str(j.get("batch"))] = j.get("model_id") or model
    rows, review = [], []
    missing = []
    for eid, listed in plan["filings"].items():
        f = src / f"{eid}.json"
        if not f.exists():
            missing.append(eid)
            review.append({"episode": eid, "problem": "no reading"})
            continue
        try:
            x = json.loads(f.read_text())
        except json.JSONDecodeError as ex:
            review.append({"episode": eid, "problem": f"unparseable JSON ({ex})"})
            continue
        cik = int(eid.split("_", 1)[0])
        probs = validate(x, eid, listed, lambda a: client.get_text(filing_txt_url(cik, a)))
        review += [{"episode": eid, "problem": p} for p in probs]
        bt = batch_of.get(eid)
        rows += to_rows(x, eid, listed, f"{model_ids.get(bt, model)} (batch {bt})", str(date.today()))
    if missing and not partial:
        raise e1.GateError(f"{len(missing)} episode(s) have no reading in {src} (first {missing[:4]}); "
                           "pass --partial to collect what exists")
    R = pd.DataFrame(rows)
    if len(R):
        R["deal_id"] = assign_deal_ids(R)
        R = R.drop(columns="_k")[list(e1.READING_COLUMNS)]
    else:
        R = pd.DataFrame(columns=e1.READING_COLUMNS)
    e1.OUT_DIR.mkdir(parents=True, exist_ok=True)
    R.to_csv(out_csv, index=False)
    pd.DataFrame(review, columns=["episode", "problem"]).to_csv(review_csv, index=False)
    raw = e1.OUT_DIR / "readings_raw" / (model if rnd == "r1" else f"{rnd}_{model}")
    raw.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.json"):
        shutil.copy2(f, raw / f.name)
    out = {"episodes": len(plan["filings"]), "read": len(plan["filings"]) - len(missing), "rows": int(len(R)),
           "in_trial_rows": int((R["in_trial"] == "Y").sum()) if len(R) else 0,
           "in_trial_deals": int(R.loc[R["in_trial"] == "Y", "deal_id"].nunique()) if len(R) else 0,
           "review_rows": len(review),
           "outcomes": R["outcome"].replace("", "(null)").value_counts().to_dict() if len(R) else {}}
    print(json.dumps(out, indent=1))
    print(f"wrote {e1._rel(out_csv)} and {review_csv.name}; now re-run "
          "`python3 scripts/events/e1_merger_pair.py stage0`")
    return out


# ============================================================ triage: which readings can change the trial

TRIAGE_CLASSES = {
    "T1": "in the trial: a failure, both parties listed, failure public by 2024-12-31",
    "T2": "a failure of a listed pair made public after 2024-12-31: in no set (§4.2, §4.3), recorded",
    "I1": "INDIVIDUAL: a failure whose parties' listing neither the reader nor CRSP settles",
    "I2": "INDIVIDUAL: outcome unstated, both parties listed, no CRSP completion within 730 days",
    "I3": "INDIVIDUAL: outcome unstated, listing unsettled, the episode's own fund a listed CEF or BDC-named",
    "C1": "class: CRSP shows the target merged within 730 days of A (the census rule: not a failed deal)",
    "C2": "class: not a listed pair, or completed (by the reader or by CRSP listing)",
    "C3": "class: outcome unstated, listing unsettled, the episode's own fund not a listed CEF",
}


def crsp_listed(nm: pd.DataFrame, ticker: str, when) -> bool | None:
    """§4.3's listing test: a CRSP CEF (share code 14/44) or BDC (11) permno carrying `ticker` on
    `when`, on NYSE, NYSE American or Nasdaq (exchcd 1-3). None if the ticker is blank or matches no
    single permno (unsettled, never guessed)."""
    if not ticker or not when or pd.isna(pd.Timestamp(when)):
        return None
    w = pd.Timestamp(when)
    r = nm[(nm["ticker"] == ticker) & (nm["namedt"] <= w) & (nm["nameendt"] >= w) & nm["shrcd"].isin((11, 14, 44))]
    if r["permno"].nunique() != 1:
        return None
    return bool(r["exchcd"].isin([1, 2, 3]).any())


def crsp_target_merged(nm, dl, ticker: str, when) -> bool | None:
    """True if the target's CRSP permno has a merger delisting (dlstcd 2xx) within 730 days after
    `when`; False if it has none and CRSP covers the window; None if unsettled."""
    if not ticker or not when or pd.isna(pd.Timestamp(when)):
        return None
    w = pd.Timestamp(when)
    r = nm[(nm["ticker"] == ticker) & (nm["namedt"] <= w) & (nm["nameendt"] >= w)]
    if r["permno"].nunique() != 1:
        return None
    d = dl[(dl["permno"] == int(r["permno"].iloc[0])) & (dl["dlstcd"] // 100 == 2)
           & (dl["dlstdt"] >= w) & (dl["dlstdt"] <= w + pd.Timedelta(days=e1.FAIL_WINDOW_DAYS))]
    if len(d):
        return True
    return False if w + pd.Timedelta(days=e1.FAIL_WINDOW_DAYS) <= e1.CRSP_END else None


def triage(R: pd.DataFrame, census: pd.DataFrame, nm: pd.DataFrame, dl: pd.DataFrame, own_listed: dict) -> pd.DataFrame:
    """Each readings row's class (TRIAGE_CLASSES) and whether it can change the trial. Names,
    delisting records and the readers' fields only; no price or return. `own_listed`: episode id ->
    True if the episode's own CIK maps to a CRSP CEF listed on its first filing date, or its EDGAR
    name is BDC-like (`e1_rulings_facts.r10`'s rule)."""
    first = dict(zip(census["episode_cik"].astype(str) + "_" + census["episode_accession"], census["first_date"]))
    out = []
    for r in R.itertuples(index=False):
        eid = f"{r.episode_cik}_{r.episode_accession}"
        when = r.ann_date or first.get(eid)
        lt, la = crsp_listed(nm, r.target_ticker, when), crsp_listed(nm, r.acquirer_ticker, when)
        listed = ("Y" if r.both_listed == "Y" or (lt and la) else
                  "N" if r.both_listed == "N" or lt is False or la is False else "")
        merged = crsp_target_merged(nm, dl, r.target_ticker, when)
        o = r.outcome
        if o in e1.FAILED_OUTCOMES:
            f = pd.Timestamp(r.fail_date or r.outcome_date) if (r.fail_date or r.outcome_date) else pd.NaT
            cls = ("C2" if listed == "N" else "I1" if listed == "" else
                   "T2" if (pd.notna(f) and f > e1.CRSP_END) else "T1")
        elif o in ("not_a_listed_pair", "completed", "completed_other_structure") or listed == "N":
            cls = "C2"
        elif merged:
            cls = "C1"
        elif listed == "Y":
            cls = "I2"
        else:
            cls = "I3" if own_listed.get(eid) else "C3"
        out.append({"crsp_listed_pair": listed, "crsp_target_merged_730d": {True: "Y", False: "N"}.get(merged, ""),
                    "triage": cls})
    T = pd.concat([R.reset_index(drop=True), pd.DataFrame(out)], axis=1)
    T["can_change_trial"] = T["triage"].str[0].isin(["T", "I"]).map({True: "Y", False: "N"})
    return T


# ============================================================ the DG-E1-3 rulings of 2026-10-20 (PREREG amendment 3)

MYI_RW = ("0001193125-23-268272", "2023-11-01")      # MYI's RW of File 333-274660 (ruling 3)
MYI_DEALS = frozenset({"1169034>883412", "894242>883412", "890393>883412", "891038>883412"})
MCC_DEAL = "1490349>1523526"                          # ruling 4
EXEMPT_CLASSES = ("C1", "C2", "C3")                    # ruling 5
# Ruling 15 (2026-10-21): the two muni deals read in each target's own filings (round r4); if that
# settles nothing, SBI -> MMU is excluded and counted, and NCU -> NKX's 2011 proposal takes §4.3's
# superseded rule, F = the first filing of the later proposal that completed (NKX, 2013-11-22).
R15 = {("886043_0001193125-23-074093", "SBI"): None,
       ("1195738_0001193125-11-345556", "NCU"): ("superseded", "2013-11-22", "0001193125-13-450220")}


def crsp_maps(nm: pd.DataFrame, cmap: dict):
    """(cik_of(ticker, when), tk_of(cik, when)) through CRSP names and `crsp_cik_map`'s permno -> CIK."""
    inv: dict[int, set] = {}
    for pmn, c in cmap.items():
        inv.setdefault(int(c), set()).add(int(pmn))

    def cik_of(tk, when):
        if not tk or not when:
            return None
        w = pd.Timestamp(when)
        r = nm[(nm["ticker"] == tk) & (nm["namedt"] <= w) & (nm["nameendt"] >= w) & nm["shrcd"].isin((11, 14, 44))]
        ps = set(r["permno"].astype(int))
        cs = {cmap[x] for x in ps if x in cmap}
        return next(iter(cs)) if len(cs) == 1 else None

    def tk_of(cik, when):
        if not cik or not when:
            return None
        w = pd.Timestamp(when)
        r = nm[nm["permno"].isin(inv.get(int(cik), ())) & (nm["namedt"] <= w) & (nm["nameendt"] >= w)]
        return r["ticker"].iloc[0] if r["ticker"].nunique() == 1 else None
    return cik_of, tk_of


def apply_dg3_rulings(R: pd.DataFrame, nm: pd.DataFrame, cmap: dict, dl: pd.DataFrame | None = None,
                      first: dict | None = None, r4_read: bool = False) -> pd.DataFrame:
    """The readings with rulings 2-4 applied; column `ruled` names the ruling that changed a row.

    2. A failure whose listing the reader left blank is listed when both parties' tickers map, on A,
       to listed CRSP CEFs/BDCs (`crsp_listed`); blank CIKs are filled through CRSP and the deal_id is
       re-formed as target > acquirer (so the deal joins its other readings, ruling 1).
    3. BHV, BKN, MIY and MPA -> MYI: withdrawn, both listed. Only the rows citing MYI's RW carry the
       failure (in_trial Y, F = 2023-11-01); the deal's other rows agree on the outcome, carry no
       failure date, and drop evidence of a different event (BHV's 2025 re-proposal).
    4. MCC -> CIK 1523526: not a listed pair (its quotes are moot and cleared).
    10. (ruled 2026-10-21; applied when `dl` is given) a blank outcome is settled from CRSP by
       `crsp_outcome`: completed or completed_other_structure -> that outcome, dated by the delisting
       (evidence: CRSP; no quote); not completed -> left blank with `crsp_note`, for the third
       reading to find the filing that dates the failure (§6.1 needs F).
    12. (2026-10-21) listing follows CRSP share codes: a blank ticker is taken from the reader's CIK
       through `crsp_cik_map` (BDCs included when the caller builds it so); a failure whose two
       parties are identified is listed or not by `crsp_listed`; one whose counterparty nobody
       identifies is excluded and counted (`excluded` = "12").
    13. a deal CRSP shows never completed with no dated failure is excluded and counted; ruling 10's
       730 days run from the episode's first merger filing (`first`) when a reading gives no A.
    15. the two muni deals of R15 wait for round r4; once it is read (`r4_read`), a still-blank SBI
       -> MMU is excluded and counted, and NCU -> NKX (2011) is superseded with §4.3's F.
    Ruling 14 needs the triage, so `apply_ruling_14` does it after. `excluded` rows are resolved:
    they block nothing and are counted.
    Ruling 1 is `failed_deal_rows`; ruling 5 is the exemption the caller takes from `triage`."""
    cik_of, tk_of = crsp_maps(nm, cmap)
    R = R.copy()
    R["ruled"] = R["ruled"] if "ruled" in R else ""
    R["crsp_note"] = ""
    R["excluded"] = ""
    first = first or {}
    eidx = R["episode_cik"] + "_" + R["episode_accession"]
    if dl is not None:   # ruling 12: a blank ticker from the reader's CIK, through CRSP
        for ix in R.index:
            when = R.at[ix, "ann_date"] or first.get(eidx[ix])
            for side in ("target", "acquirer"):
                if not R.at[ix, f"{side}_ticker"] and R.at[ix, f"{side}_cik"]:
                    R.at[ix, f"{side}_ticker"] = tk_of(R.at[ix, f"{side}_cik"], when) or ""
                elif R.at[ix, f"{side}_ticker"] and not R.at[ix, f"{side}_cik"]:   # and a CIK from the ticker
                    c = cik_of(R.at[ix, f"{side}_ticker"], when)
                    R.at[ix, f"{side}_cik"] = str(c) if c else ""
    for ix in R.index[R["deal_id"].isin(MYI_DEALS)]:
        when = R.at[ix, "ann_date"] or "2023-09-08"
        for side in ("target", "acquirer"):
            if not R.at[ix, f"{side}_ticker"]:
                R.at[ix, f"{side}_ticker"] = tk_of(R.at[ix, f"{side}_cik"], when) or ""
        R.loc[ix, ["outcome", "both_listed"]] = ["withdrawn", "Y"]
        if R.at[ix, "outcome_accession"] == MYI_RW[0]:
            R.loc[ix, ["in_trial", "fail_accession", "fail_quote", "fail_date"]] = [
                "Y", MYI_RW[0], R.at[ix, "outcome_quote"], MYI_RW[1]]
        else:
            R.loc[ix, ["in_trial", "fail_accession", "fail_quote", "fail_date",
                       "outcome_accession", "outcome_quote", "outcome_date"]] = ["N", "", "", "", "", "", ""]
        R.at[ix, "ruled"] = "3"
    m = R["deal_id"].eq(MCC_DEAL)
    R.loc[m, ["outcome", "both_listed", "in_trial", "fail_accession", "fail_quote", "fail_date",
              "outcome_accession", "outcome_quote", "outcome_date", "ruled"]] = [
        "not_a_listed_pair", "N", "N", "", "", "", "", "", "", "4"]
    for ix in R.index[R["outcome"].isin(e1.FAILED_OUTCOMES) & (R["both_listed"] == "") & (R["ruled"] == "")]:
        when = R.at[ix, "ann_date"] or first.get(eidx[ix])
        lt, la = crsp_listed(nm, R.at[ix, "target_ticker"], when), crsp_listed(nm, R.at[ix, "acquirer_ticker"], when)
        if dl is not None and (lt is False or la is False):          # ruling 12: identified, not listed
            R.loc[ix, ["both_listed", "in_trial", "ruled"]] = ["N", "N", "12"]
            continue
        if dl is not None and (lt is None or la is None):            # ruling 12: counterparty unidentified
            R.loc[ix, ["in_trial", "excluded"]] = ["N", "12"]
            continue
        if lt and la:
            for side in ("target", "acquirer"):
                if not R.at[ix, f"{side}_cik"]:
                    c = cik_of(R.at[ix, f"{side}_ticker"], when)
                    R.at[ix, f"{side}_cik"] = str(c) if c else ""
            if dl is not None and not R.at[ix, "fail_date"]:          # rulings 12-13: listed, failure undated
                R.loc[ix, ["both_listed", "in_trial", "ruled", "excluded"]] = ["Y", "N", "12", "13"]
                continue
            R.loc[ix, ["both_listed", "in_trial", "ruled"]] = ["Y", "Y", "2"]
            if R.at[ix, "target_cik"] and R.at[ix, "acquirer_cik"]:
                R.at[ix, "deal_id"] = f"{R.at[ix, 'target_cik']}>{R.at[ix, 'acquirer_cik']}"
    if dl is not None:
        for ix in R.index[R["outcome"] == ""]:
            o = crsp_outcome(nm, dl, R.at[ix, "target_ticker"], R.at[ix, "acquirer_ticker"],
                             R.at[ix, "ann_date"] or first.get(eidx[ix]))       # ruling 13's anchor
            if o is None:
                continue
            if o[0] in ("completed", "completed_other_structure"):
                R.loc[ix, ["outcome", "outcome_date", "in_trial", "ruled"]] = [o[0], str(o[1]), "N", "10"]
            else:
                R.at[ix, "crsp_note"] = o[0] + (f" {o[1]}" if o[1] else "")
                if (eidx[ix], R.at[ix, "target_ticker"]) not in R15:        # ruling 13
                    R.at[ix, "excluded"] = "13"
        for ix in R.index:                                                   # ruling 15, once r4 is read
            key = (eidx[ix], R.at[ix, "target_ticker"])
            if key not in R15 or R.at[ix, "outcome"] != "" or not r4_read:
                continue
            if R15[key] is None:
                R.at[ix, "excluded"] = "15"
            else:
                o, f_date, f_acc = R15[key]
                when = R.at[ix, "ann_date"] or first.get(eidx[ix])
                R.loc[ix, ["outcome", "both_listed", "in_trial", "fail_date", "fail_accession", "ann_date",
                           "ruled"]] = [o, "Y", "Y", f_date, f_acc, when, "15"]
    return R


def apply_ruling_14(R: pd.DataFrame, exempt: pd.Series) -> pd.DataFrame:
    """Ruling 14 (2026-10-21): an outcome still unstated after the readings, on a row that could
    change the trial and whose deal no other row settles, is excluded and counted (`excluded` =
    "14"). Ruling 15's two deals are left to it."""
    R = R.copy()
    eidx = R["episode_cik"] + "_" + R["episode_accession"]
    dk = e1.deal_keys(R)
    settled = set(dk[R["outcome"] != ""])
    m = ((R["outcome"] == "") & ~exempt.values & ~dk.isin(settled) & (R["excluded"] == "")
         & ~pd.Series([(e, t) in R15 for e, t in zip(eidx, R["target_ticker"])], index=R.index))
    R.loc[m, "excluded"] = "14"
    return R


def exempt_rows(T: pd.DataFrame) -> pd.Series:
    """Ruling 5: rows that cannot change the trial (triage C1-C3, or a deal announced after 2024-12-31)."""
    late = pd.to_datetime(T["ann_date"].replace("", None)) > e1.CRSP_END
    return T["triage"].isin(EXEMPT_CLASSES) | late.fillna(False)


def _key(r) -> str:
    """A deal's id within ONE episode, without the series suffix."""
    return r["deal_id"].split("/")[0]


def _match(old: list, new) -> int | None:
    """Index in `old` of the reading of the same deal as `new`, within one episode: the same
    CIK-based deal_id; else the same printed ticker pair (both readings print both); else the same
    position (ep<cik>:<k>) when neither reading names the parties. Fixed 2026-10-21: matching by
    position alone paired round 3's SBI -> MMU (its deal 0) with the supplementary reading's
    MNP -> MMU (its deal 0)."""
    k = _key(new)
    if not k.startswith("ep"):
        for i, o in enumerate(old):
            if _key(o) == k:
                return i
    tn = (new["target_ticker"], new["acquirer_ticker"])
    if all(tn):
        for i, o in enumerate(old):
            if (o["target_ticker"], o["acquirer_ticker"]) == tn:
                return i
        return None
    for i, o in enumerate(old):
        if _key(o) == k and not (o["target_ticker"] and o["acquirer_ticker"]):
            return i
    return None


def merge_rounds(R1: pd.DataFrame, R2: pd.DataFrame | None = None, N8: pd.DataFrame | None = None,
                 R3: pd.DataFrame | None = None) -> pd.DataFrame:
    """The readings after ruling 8 (second reading) and ruling 6 (N-8F re-read), with `round` and
    `merge_note` columns; rows needing a THIRD reading carry merge_note "adjudicate" and a blank outcome.

    * n8f: its rows replace the first reading's rows of its episodes (ruling 6's re-read is the reading
      under the rule).
    * r2, per episode and matched deal (`_key`):
      - one reading blank, the other not: the non-blank reading stands (a blank saw nothing);
      - both non-blank and equal: the second reading (it saw fuller excerpts);
      - one `not_a_listed_pair` with listing evidence, the other a failure or null with listing blank:
        the listing reading settles it (they answer different questions, and an unlisted pair cannot
        enter the trial);
      - otherwise different non-blank outcomes: a disagreement, adjudicated by a third reading (ruling 8);
      - a deal only one reading records: kept as read.
    """
    R = R1.copy()
    R["round"], R["merge_note"] = "r1", ""
    ek = lambda F: F["episode_cik"] + "_" + F["episode_accession"]  # noqa: E731
    if N8 is not None and len(N8):
        R = R[~ek(R).isin(set(ek(N8)))]
        R = pd.concat([R, N8.assign(round="n8f", merge_note="replaces r1 (ruling 6)")], ignore_index=True)
    if R2 is not None and len(R2):
        R = _merge_second(R, R2, ek)
    if R3 is not None and len(R3):
        R = _merge_third(R, R3, ek)
    return R.reset_index(drop=True)


def _merge_third(R: pd.DataFrame, R3: pd.DataFrame, ek) -> pd.DataFrame:
    """Ruling 8's third reading adjudicates: per episode and matched deal, a non-blank third reading
    stands (over a blank, or over a disagreement); a blank third reading leaves the deal as it was."""
    eps = set(ek(R3))
    keep, prior, out = R[~ek(R).isin(eps)], R[ek(R).isin(eps)], []
    for e, g3 in R3.groupby(ek(R3)):
        olds = [r for _, r in prior[ek(prior) == e].iterrows()]
        used = set()
        for _, r3 in g3.iterrows():
            i = _match([o if j not in used else {**o, "deal_id": "\0", "target_ticker": "\0", "acquirer_ticker": "\0"}
                        for j, o in enumerate(olds)], r3)
            if i is not None:
                used.add(i)
            old = olds[i] if i is not None else None
            if old is None or r3["outcome"] != "":
                out.append({**r3, **({"deal_id": old["deal_id"]} if old is not None else {}),
                            "round": "r3", "merge_note": "r3" if old is not None else "only r3"})
            else:
                out.append({**old, "merge_note": (old["merge_note"] + "; r3 blank").strip("; ")})
        out += [{**o, "merge_note": (o["merge_note"] + "; only before r3").strip("; ")}
                for j, o in enumerate(olds) if j not in used]
    return pd.concat([keep, pd.DataFrame(out)], ignore_index=True).fillna("")


def _merge_second(R: pd.DataFrame, R2: pd.DataFrame, ek) -> pd.DataFrame:
    eps2 = set(ek(R2))
    keep, out = R[~ek(R).isin(eps2)], []
    first = R[ek(R).isin(eps2)]
    for e, g2 in R2.groupby(ek(R2)):
        olds = [r for _, r in first[ek(first) == e].iterrows()]
        used = set()
        for _, r2 in g2.iterrows():
            i = _match([o if j not in used else {**o, "deal_id": "\0", "target_ticker": "\0", "acquirer_ticker": "\0"}
                        for j, o in enumerate(olds)], r2)
            if i is not None:
                used.add(i)
            r1 = olds[i] if i is not None else None
            if r1 is None:
                out.append({**r2, "round": "r2", "merge_note": "only r2"})
            elif r1["outcome"] == "" or r1["outcome"] == r2["outcome"]:
                out.append({**r2, "round": "r2", "merge_note": "r2" if r1["outcome"] == "" else "r1 = r2"})
            elif r2["outcome"] == "":
                out.append({**r1, "round": "r1", "merge_note": "r1 (r2 blank)"})
            elif (r2["outcome"] == "not_a_listed_pair" and r2["both_listed"] == "N" and r1["both_listed"] == "") or \
                 (r1["outcome"] == "not_a_listed_pair" and r1["both_listed"] == "N" and r2["both_listed"] == ""):
                win = r2 if r2["outcome"] == "not_a_listed_pair" else r1
                out.append({**win, "round": "r2" if win is r2 else "r1", "merge_note": "listing evidence settles"})
            else:
                out.append({**r2, "outcome": "", "in_trial": "N", "round": "r2",
                            "merge_note": f"adjudicate: r1 {r1['outcome']} vs r2 {r2['outcome']}"})
        out += [{**o, "round": "r1", "merge_note": "only r1"} for j, o in enumerate(olds) if j not in used]
    return pd.concat([keep, pd.DataFrame(out)], ignore_index=True).fillna("")


def crsp_outcome(nm: pd.DataFrame, dl: pd.DataFrame, target: str, acquirer: str, when) -> tuple | None:
    """The PROPOSED CRSP outcome rule (not ruled), on the target's CRSP delisting record within
    FAIL_WINDOW_DAYS (730, §4.3's own census window) after A:

    * delisted INTO the acquirer's permno (`nwperm`), under a merger (2xx) or exchange (3xx) code ->
      ("completed", dlstdt). CRSP codes many CEF reorganisations 331, not 231 (measured 2026-10-21:
      BHY, HIS -> HYT 2013; ARK -> DSU; BCL -> BFZ; DCW -> DCA; NMD -> NMZ), so 2xx alone misses them;
      the nwperm match, not the code, is what makes it this deal;
    * a 2xx merger into ANOTHER permno -> ("completed_other_structure", dlstdt);
    * a liquidation (4xx) -> ("not_completed_liquidated", dlstdt);
    * still listed (code 100) past A + 730 days, inside CRSP -> ("not_completed", None);
    * anything else (no record: the delisting cache holds CEF permnos only, so a BDC's is missing; a
      3xx into another permno; 5xx; a window past CRSP's end) -> None, unsettled. Nothing is guessed."""
    if not target or not when:
        return None
    w = pd.Timestamp(when)
    sel = lambda tk: nm[(nm["ticker"] == tk) & (nm["namedt"] <= w) & (nm["nameendt"] >= w)  # noqa: E731
                        & nm["shrcd"].isin((11, 14, 44))]
    r = sel(target)
    if r["permno"].nunique() != 1:
        return None
    tp = int(r["permno"].iloc[0])
    a = sel(acquirer) if acquirer else r.iloc[0:0]
    ap = int(a["permno"].iloc[0]) if a["permno"].nunique() == 1 else None
    d = dl[dl["permno"] == tp]
    if d.empty:
        return None
    d = d.sort_values("dlstdt").iloc[-1]
    code, dt = int(d["dlstcd"]), pd.Timestamp(d["dlstdt"])
    inside = w <= dt <= w + pd.Timedelta(days=e1.FAIL_WINDOW_DAYS)
    if code // 100 in (2, 3) and inside and ap is not None and int(d["nwperm"]) == ap:
        return ("completed", dt.date())
    if code // 100 == 2 and inside:
        return ("completed_other_structure", dt.date())
    if code // 100 == 4 and inside:
        return ("not_completed_liquidated", dt.date())
    if (code == 100 or dt > w + pd.Timedelta(days=e1.FAIL_WINDOW_DAYS)) and w + pd.Timedelta(days=e1.FAIL_WINDOW_DAYS) <= e1.CRSP_END:
        return ("not_completed", None)
    return None


def _read(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path, dtype=str, keep_default_na=False) if path.exists() else None


def dg3_state(nm: pd.DataFrame, dl: pd.DataFrame, names: pd.DataFrame, cen: pd.DataFrame, supp: pd.DataFrame) -> dict:
    """DG-E1-3 as the rulings stand: every round merged (rulings 6, 8), readings of episodes the
    census no longer holds set aside as moot (amendment 4 moved them out), the supplementary round
    added, rulings 2-4 and 10 applied, triaged, ruling 5's exemption computed.
    The supplementary census's episodes that were read as census episodes keep that reading."""
    from scripts.events import e1_rulings_facts as rf
    R1 = _read(e1.READINGS)
    if R1 is None:
        raise e1.GateError("no first reading")
    R = merge_rounds(R1, *(_read(e1.OUT_DIR / ROUNDS[k][0]) for k in ("r2", "n8f")))
    sp = _read(e1.OUT_DIR / ROUNDS["supp"][0])
    if sp is not None:
        R = pd.concat([R, sp.assign(round="supp", merge_note="")], ignore_index=True).fillna("")
    r3 = _read(e1.OUT_DIR / ROUNDS["r3"][0])
    if r3 is not None:   # the third reading adjudicates over every earlier round, the supplementary one included
        R = _merge_third(R, r3, lambda F: F["episode_cik"] + "_" + F["episode_accession"]).reset_index(drop=True)
    r4 = _read(e1.OUT_DIR / ROUNDS["r4"][0])
    if r4 is not None:   # one fund's own filings, re-keyed onto the episode whose deal they settle
        r4 = rekey_r4(r4, pd.read_csv(e1.OUT_DIR / ROUNDS["r4"][2], dtype=str))
        if "doc_cik" not in R:
            R["doc_cik"] = ""
        R = add_r4(R, r4)
    allc = pd.concat([cen, supp], ignore_index=True).drop_duplicates(["episode_cik", "episode_accession"])
    keys = set(allc["episode_cik"].astype(str) + "_" + allc["episode_accession"])
    ek = R["episode_cik"] + "_" + R["episode_accession"]
    moot = int((~ek.isin(keys)).sum())
    R = R[ek.isin(keys)].reset_index(drop=True)
    cmap = e1.crsp_cik_map(nm, names, bdc=True)                       # ruling 12: BDCs by CIK too
    first = dict(zip(allc["episode_cik"].astype(str) + "_" + allc["episode_accession"], allc["first_date"].astype(str)))
    Rr = apply_dg3_rulings(R, nm, cmap, dl, first=first, r4_read=(e1.OUT_DIR / ROUNDS["r4"][0]).exists())
    T = triage(Rr, allc.astype({"episode_cik": str}), nm, dl, rf.own_listed(nm, names))
    ex = exempt_rows(T)
    Rr = apply_ruling_14(Rr, ex)                                         # ruling 14
    T["excluded"] = Rr["excluded"].values
    ex = ex | (Rr["excluded"] != "").values                              # excluded and counted: resolved
    return {"R": Rr, "T": T, "exempt": ex, "census": allc, "moot_rows": moot}


def add_r4(R: pd.DataFrame, r4: pd.DataFrame) -> pd.DataFrame:
    """Round r4's readings ADDED beside the earlier readings of the same deal (matched by `_match`
    within the episode, taking that deal's id), not in their place: each row's quotes stay in its
    own fund's filings (`doc_cik`), and ruling 1 takes the deal's A as its earliest announcement over
    every row (`failed_deal_rows`). A blank row of the deal is then settled by the r4 row."""
    ek = R["episode_cik"] + "_" + R["episode_accession"]
    out = []
    for _, r in r4.iterrows():
        olds = [o for _, o in R[ek == f"{r['episode_cik']}_{r['episode_accession']}"].iterrows()]
        i = _match(olds, r)
        out.append({**r, **({"deal_id": olds[i]["deal_id"]} if i is not None else {}), "round": "r4",
                    "merge_note": "r4 beside the earlier readings" if i is not None else "only r4"})
    return pd.concat([R, pd.DataFrame(out)], ignore_index=True).fillna("") if out else R


def rekey_r4(r4: pd.DataFrame, L: pd.DataFrame) -> pd.DataFrame:
    """Round r4's rows moved onto the episode whose deal they settle (`for_episode`), with the fund
    whose filings they quote kept in `doc_cik` (check_readings re-finds the quotes there). A reading
    that records no deal (no ticker, no CIK, no outcome) settles nothing and is dropped: ruling 15's
    fallback then decides (NCU's own filings describe no NCU merger, 2026-10-21)."""
    empty = (r4["target_ticker"] == "") & (r4["acquirer_ticker"] == "") & (r4["target_cik"] == "") \
        & (r4["acquirer_cik"] == "") & (r4["outcome"] == "")
    r4 = r4[~empty]
    to = dict(zip(L["episode_cik"].astype(str) + "_" + L["episode_accession"], L["for_episode"]))
    eid = r4["episode_cik"] + "_" + r4["episode_accession"]
    if not eid.isin(to).all():
        raise e1.GateError(f"round r4 rows for an episode not in its list: {sorted(set(eid) - set(to))[:3]}")
    dest = eid.map(to)
    return r4.assign(doc_cik=r4["episode_cik"], episode_cik=dest.str.split("_").str[0],
                     episode_accession=dest.str.split("_", n=1).str[1])


def r3_list(T: pd.DataFrame, exempt: pd.Series) -> pd.DataFrame:
    """The episodes a third reading must settle (rulings 8 and 10), each with its focus."""
    dk = e1.deal_keys(T)
    settled = set(dk[T["outcome"] != ""])
    rows = []
    for r, ex, key in zip(T.itertuples(index=False), exempt, dk):
        if ex:
            continue
        pair = f"{r.target_ticker or '?'} into {r.acquirer_ticker or '?'}"
        if r.crsp_note.startswith("not_completed"):
            f = f"{pair}: CRSP shows it never completed; find the filing that makes its failure public, with its date"
        elif r.outcome in e1.FAILED_OUTCOMES and r.both_listed == "":
            f = f"{pair}: it failed ({r.outcome}); are BOTH funds exchange-listed? give each fund's ticker"
        elif r.outcome == "" and key not in settled:
            f = f"{pair}: how did it end? (outcome, the filing that says so, and both funds' tickers and listing)"
        else:
            continue
        rows.append({"episode": f"{r.episode_cik}_{r.episode_accession}", "focus": f})
    F = pd.DataFrame(rows, columns=["episode", "focus"])
    return F.groupby("episode", as_index=False)["focus"].agg(" | ".join)


def freeze_rounds(r1_root: Path, Rr: pd.DataFrame, T: pd.DataFrame) -> dict:
    """Write the episode lists of rounds r2 (ruling 8: the episodes of rows that can still change the
    trial and are not settled by rulings 2-4) and n8f (ruling 6: r1's batches 40 and 45)."""
    open_ = T["triage"].str.startswith("I") & ~exempt_rows(T) & (T["ruled"] == "")
    r2 = sorted(set(T.loc[open_, "episode_cik"] + "_" + T.loc[open_, "episode_accession"]))
    plan = json.loads((r1_root / "input" / "plan.json").read_text())
    n8f = sorted(e["id"] for b in plan["batches"] if b["batch"] in ("40", "45") for e in b["episodes"])
    for rnd, ids in (("r2", r2), ("n8f", n8f)):
        pd.DataFrame({"episode": ids}).to_csv(e1.OUT_DIR / ROUNDS[rnd][2], index=False)
    return {"r2_episodes": len(r2), "r2_rows": int(open_.sum()), "n8f_episodes": len(n8f)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--round", dest="rnd", choices=sorted(ROUNDS), default="r1")
    c = sub.add_parser("collect")
    c.add_argument("--root", type=Path, required=True)
    c.add_argument("--model", required=True)
    c.add_argument("--partial", action="store_true")
    sub.add_parser("triage")
    f4 = sub.add_parser("freeze-r4")
    f4.add_argument("--cik", required=True)
    f4.add_argument("--around", required=True)
    f4.add_argument("--for-episode", required=True, help="<cik>_<accession> of the episode whose deal it settles")
    f4.add_argument("--focus", required=True)
    fz = sub.add_parser("freeze-rounds")
    fz.add_argument("--r1-root", type=Path, required=True)
    sub.add_parser("freeze-r3")
    a = ap.parse_args(argv)
    if a.cmd == "triage":
        return run_triage()
    if a.cmd == "freeze-rounds":
        return run_freeze(a.r1_root)
    if a.cmd == "freeze-r3":
        return run_freeze_r3()
    if a.cmd == "freeze-r4":
        return run_freeze_r4(a.cik, a.around, a.for_episode, a.focus)
    if a.cmd == "prepare":
        plan = prepare(a.root, rnd=a.rnd)
        print(f"round {a.rnd}: {plan['episodes']} episodes in {len(plan['batches'])} batches under {a.root}/input/")
        return 0
    collect(a.root, a.model, a.partial)
    return 0


def ruled_triage():  # pragma: no cover - reads the CRSP cache, the EDGAR name table and the census
    """(ruled readings, their triage) with rulings 2-4 applied (the triage is ruling 5's input)."""
    from scripts.events import e1_rulings_facts as rf
    nm, dl = e1.crsp_tables()
    names = rf._names()
    cmap = e1.crsp_cik_map(nm, names)
    R = pd.read_csv(e1.READINGS, dtype=str, keep_default_na=False)
    Rr = apply_dg3_rulings(R, nm, cmap)
    cen = pd.read_csv(e1.CENSUS, dtype={"episode_cik": str})
    T = triage(Rr, cen, nm, dl, rf.own_listed(nm, names))
    return Rr, T


def run_freeze_r4(cik: str, around: str, for_episode: str, focus: str) -> int:  # pragma: no cover
    """Round r4's one-fund list, after `fetch-edgar --cik`: the episode is the fund's filings from 30
    days before `around` to 730 after, keyed by its first; its reading settles `for_episode`'s deal."""
    fl = episode_filings(e1.edgar_client(online=False), int(cik), around, e1.TARGETED_FORMS)
    if fl.empty:
        raise e1.GateError(f"CIK {cik}: no cached filing in the window; the team lead runs `fetch-edgar --cik {cik} --around {around}`")
    f = fl.iloc[0]
    row = pd.DataFrame([{"episode": f"{int(cik)}_{f['accessionNumber']}", "episode_cik": int(cik),
                         "episode_accession": f["accessionNumber"], "first_date": around, "first_form": f["form"],
                         "company_last": f.get("entity_name", ""), "for_episode": for_episode, "focus": focus}])
    path = e1.OUT_DIR / ROUNDS["r4"][2]
    if path.exists():                  # one row per fund: add this one, replacing an earlier row for it
        old = pd.read_csv(path, dtype=str)
        row = pd.concat([old[old["episode_cik"] != str(int(cik))], row.astype(str)], ignore_index=True)
    row.to_csv(path, index=False)
    print(f"round r4: CIK {cik}, {len(fl)} filings, for {for_episode}")
    return 0


def run_freeze_r3() -> int:  # pragma: no cover - reads the CRSP cache, the name table and the census
    from scripts.events import e1_rulings_facts as rf
    nm, dl = e1.crsp_tables()
    st = dg3_state(nm, dl, rf._names(), pd.read_csv(e1.CENSUS), pd.read_csv(e1.CENSUS_SUPP))
    F = r3_list(st["T"], st["exempt"])
    F.to_csv(e1.OUT_DIR / ROUNDS["r3"][2], index=False)
    print(f"round r3: {len(F)} episodes (moot readings set aside: {st['moot_rows']})")
    return 0


def run_freeze(r1_root: Path) -> int:  # pragma: no cover
    Rr, T = ruled_triage()
    print(freeze_rounds(r1_root, Rr, T))
    return 0


def run_triage() -> int:  # pragma: no cover - reads the CRSP cache and the census; its core is tested (triage)
    Rr, T = ruled_triage()
    path = e1.OUT_DIR / "e1_failed_reading_triage.csv"
    T.to_csv(path, index=False)
    by = T.groupby("triage").agg(rows=("deal_id", "size"), deals=("deal_id", "nunique"),
                                 episodes=("episode_cik", lambda v: (v + T.loc[v.index, "episode_accession"]).nunique()))
    print(by.to_string())
    print("in-trial deals (T1):", sorted(T.loc[T["triage"] == "T1", "target_ticker"] + "->" + T.loc[T["triage"] == "T1", "acquirer_ticker"]))
    print(f"wrote {e1._rel(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
