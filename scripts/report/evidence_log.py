"""Parse and validate `results/report/EVIDENCE_LOG.md`, and enforce that it is append-only.

WHY THIS FILE EXISTS (2026-11-03). The evidence log is the raw material a research
report on this desk will be written from. Its value is its discipline: every entry is
dated, every figure carries a provenance tag, and every entry names the file and the
commit its figures were copied from. A free-text log drifts from that within days
(docs/SYSTEM.md opens with the arm rate that existed as four fractions at once), so
the format is checked by code, not by memory:

  * `parse` reads the entries; `validate` returns every defect it finds, naming the
    entry, and never fixes one silently;
  * `check_append_only(old, new)` refuses an edit to an existing entry. A correction
    is a NEW dated entry (kind `correction`) that says what it supersedes, the way
    `docs/RESEARCH_STATE.md`'s CEF-counter correction is written. Someone may be
    relying on the old figure.

The entry format (fields fixed, in this order):

    ### E-2026-09-10-01 · one-line claim
    - kind: correction
    - era: HISTORY
    - date: 2026-09-10
    - figures:
      - walk-forward 9/9 → 7/9 [S]
    - source: `pre-clean-slate:results/cef/EXECUTION_CONVENTION_2026-09-10.md` @ `f6d155f`
    - supports: §2, §3
    - status: supersedes the shift(1) figures

Tags, as the log's header defines them: [V] re-derived by `build_pack.py` from
committed data, or labelled [V] by the source; [S] copied verbatim from the named
committed file, not re-run by the pack; [U] uncertain, or two sources disagree.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

HEADER = re.compile(r"^### (E-(\d{4}-\d{2}-\d{2})-(\d{2,3})) · (.+?)\s*$")
FIELDS = ("kind", "era", "date", "figures", "source", "supports", "status")
KINDS = {"result", "ruling", "release", "incident", "correction", "kill", "counter",
         "live-pnl", "method"}
ERAS = {"HISTORY", "ALPACA"}
ALPACA_START = "2026-09-28"
TAG = re.compile(r"\[(V|S|U)\]\s*$")
# A source names at least one backticked path and a commit, or a VM pull hash for an
# automatically appended live day (the commit that adds it does not exist yet).
SOURCE_REF = re.compile(r"`[^`]+`\s*@\s*`(?:[0-9a-f]{7,40}|pull:[0-9a-f]{12})`")
SUPPORTS = re.compile(r"§\d+")


@dataclass
class Entry:
    id: str
    claim: str
    line: int
    fields: dict = field(default_factory=dict)
    figures: list = field(default_factory=list)
    block: str = ""

    @property
    def date(self) -> str:
        return self.id[2:12]


def _blocks(text: str):
    """Yield (header_line_no, block_text) for every entry; the block runs to the next
    entry header or a level-1/2 heading."""
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.startswith("### E-")]
    for k, i in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        for j in range(i + 1, end):
            if lines[j].startswith("## ") or lines[j].startswith("# "):
                end = j
                break
        yield i + 1, "\n".join(lines[i:end]).rstrip()


def parse(text: str) -> list[Entry]:
    """Every entry in the log, in file order. Malformed headers are kept (with an
    empty id) so that `validate` can name them; nothing is dropped."""
    out = []
    for line_no, block in _blocks(text):
        head, *rest = block.splitlines()
        m = HEADER.match(head)
        e = Entry(id=m.group(1) if m else "", claim=m.group(4) if m else head, line=line_no,
                  block=block)
        current = None
        for ln in rest:
            fm = re.match(r"^- (kind|era|date|figures|source|supports|status):\s*(.*)$", ln)
            if fm:
                current = fm.group(1)
                e.fields[current] = fm.group(2).strip()
                continue
            if current == "figures" and re.match(r"^\s{2,}- ", ln):
                e.figures.append(ln.strip()[2:].strip())
            elif ln.strip() and current in e.fields:
                e.fields[current] = (e.fields[current] + " " + ln.strip()).strip()
        out.append(e)
    return out


def validate(entries: list[Entry]) -> list[str]:
    """Every defect, as 'line N, <id>: <problem>'. An empty list means the log is valid."""
    errs, seen = [], {}
    for e in entries:
        where = f"line {e.line}, {e.id or '<bad header>'}"
        if not e.id:
            errs.append(f"{where}: header must read '### E-YYYY-MM-DD-NN · claim'")
            continue
        if e.id in seen:
            errs.append(f"{where}: duplicate id (first at line {seen[e.id]})")
        seen.setdefault(e.id, e.line)
        missing = [f for f in FIELDS if f not in e.fields]
        if missing:
            errs.append(f"{where}: missing field(s) {missing}")
            continue
        order = [f for f in re.findall(r"^- (\w+):", e.block, re.M) if f in FIELDS]
        if order != list(FIELDS):
            errs.append(f"{where}: fields out of order {order}")
        if e.fields["kind"] not in KINDS:
            errs.append(f"{where}: kind {e.fields['kind']!r} not in {sorted(KINDS)}")
        if e.fields["era"] not in ERAS:
            errs.append(f"{where}: era {e.fields['era']!r} not in {sorted(ERAS)}")
        if e.fields["date"] != e.date:
            errs.append(f"{where}: date {e.fields['date']!r} does not match the id")
        if e.date < ALPACA_START and e.fields["era"] != "HISTORY":
            errs.append(f"{where}: dated before {ALPACA_START}, so era must be HISTORY")
        if not e.figures:
            errs.append(f"{where}: no figure bullets (write '- none (a ruling)')")
        for f in e.figures:
            if f.startswith("none"):
                continue
            if not TAG.search(f):
                errs.append(f"{where}: figure without a [V]/[S]/[U] tag: {f[:70]!r}")
        if not SOURCE_REF.search(e.fields["source"]):
            errs.append(f"{where}: source must name `path` @ `commit` (or `pull:<sha12>`)")
        if not SUPPORTS.search(e.fields["supports"]):
            errs.append(f"{where}: supports must name at least one §n")
        if not e.fields["status"]:
            errs.append(f"{where}: empty status")
    return errs


def check_append_only(old_text: str, new_text: str) -> list[str]:
    """Defects if `new_text` edits or removes an entry of `old_text`, or inserts a new
    entry anywhere but after the last old one. Corrections are new entries."""
    old = parse(old_text)
    new = parse(new_text)
    errs = []
    new_by_id = {e.id: e for e in new}
    for e in old:
        n = new_by_id.get(e.id)
        if n is None:
            errs.append(f"{e.id}: removed (entries are never deleted; add a correction)")
        elif n.block != e.block:
            errs.append(f"{e.id}: edited (entries are never edited; add a dated correction)")
    old_ids = [e.id for e in old]
    prefix = [e.id for e in new[:len(old_ids)]]
    if not errs and prefix != old_ids:
        errs.append("new entries must be appended after the last existing entry, not inserted")
    return errs


def tag_counts(entries: list[Entry]) -> dict:
    """How many figures carry each tag (the log's provenance self-check)."""
    c = {"V": 0, "S": 0, "U": 0, "none": 0}
    for e in entries:
        for f in e.figures:
            m = TAG.search(f)
            c[m.group(1) if m else "none"] += 1
    return c
