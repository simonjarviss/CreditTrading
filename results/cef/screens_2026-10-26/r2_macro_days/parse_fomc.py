"""Parse the fetched Fed pages into FOMC statement dates, 2005-2022 (raw/fed -> fomc_fed.csv).

    python3 -I parse_fomc.py

Two page layouts:
* fomchistorical{YEAR}.htm (2005-2020): one <h5> per event ("January 29-30
  Meeting - 2008", "March 10 Conference Call - 2008"). A "Meeting" without
  "(unscheduled)" in its heading is a SCHEDULED meeting; a "Conference Call" or an
  "(unscheduled)" meeting is UNSCHEDULED. The statement date is the 8-digit date
  in the href of the section's "Statement" link (the release day, which for a
  two-day meeting is the second day). A section without a Statement link
  issued no statement (most conference calls) and is kept with
  statement_date empty, so it can be counted, not used.
* A heading with "(cancelled)" is a scheduled meeting that was not held
  (2020-03-17/18). It is kept, flagged `cancelled`, with no statement date.
* fomccalendars.htm (2021-2022 here): month + "dd-dd" per meeting; the
  statement is released on the meeting's last day (the Fed's practice; the
  Statement hrefs on the page carry the same date and are cross-checked).

Raises if a scheduled meeting has no derivable statement date, or if a year
does not have exactly 8 scheduled meetings (the FOMC "holds eight regularly
scheduled meetings during the year", docs/REFERENCES.md R17).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw" / "fed"
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                      "August", "September", "October", "November", "December"], 1)}


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def historical(year: int) -> list[dict]:
    h = (RAW / f"fomchistorical{year}.htm").read_text(encoding="utf-8", errors="replace")
    heads = list(re.finditer(r"<h5[^>]*>(.*?)</h5>", h, re.S))
    out = []
    for k, m in enumerate(heads):
        head = _text(m.group(1))
        if not re.search(r"(Meeting|Conference Call)", head):
            continue
        seg = h[m.end(): heads[k + 1].start() if k + 1 < len(heads) else len(h)]
        stmt = [re.search(r"(\d{8})", a.group(1)).group(1)
                for a in re.finditer(r'href="([^"]*monetary[^"]*\d{8}[^"]*)"[^>]*>\s*Statement\s*<', seg)]
        unsched = ("Conference Call" in head) or ("unscheduled" in head.lower())
        cancelled = "cancelled" in head.lower()
        href_date = pd.Timestamp(stmt[0]) if stmt else pd.NaT
        sdate, note = href_date, ""
        if not unsched and not cancelled:
            # A scheduled meeting's statement comes on its LAST day. Derive that day
            # from the heading and require the Statement href to agree; the href is a
            # page ID, and once (June 2007) it is not the release date.
            last = heading_last_day(head, year)
            if pd.isna(href_date) or href_date != last:
                key = href_date.strftime("%Y%m%d") if not pd.isna(href_date) else None
                if key not in HREF_ERRORS:
                    raise ValueError(f"{head}: Statement href {href_date} != last meeting day {last}")
                fixed, page, phrase = HREF_ERRORS[key]
                txt = (HERE / page).read_text(encoding="utf-8", errors="replace")
                if phrase not in re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", txt)):
                    raise ValueError(f"{page} does not carry {phrase!r}; the correction is unproved")
                sdate, note = pd.Timestamp(fixed), f"href {key} mislabelled; {page} reads '{phrase}'"
        out.append(dict(year=year, heading=head, scheduled=not unsched, cancelled=cancelled,
                        statement_date=sdate, href_date=href_date, note=note,
                        n_statement_links=len(stmt), page=f"fomchistorical{year}.htm"))
    return out


# Statement hrefs whose 8-digit ID is not the release date, each proved by the
# fetched statement page (raw/fed_stmt/, fetched 2026-10-26; URL in its log).
HREF_ERRORS = {
    "20070618": ("2007-06-28", "raw/fed_stmt/20070618a.htm", "June 28, 2007 FOMC statement"),
}


def heading_last_day(head: str, year: int) -> pd.Timestamp:
    """'January 29-30 Meeting - 2008' -> 2008-01-30; 'Jan/Feb 31-1 Meeting - 2017' -> 2017-02-01
    (a meeting spanning two months names both, abbreviated; its last day is in the second)."""
    abbr = {k[:3]: v for k, v in MONTHS.items()}
    toks = re.findall(r"([A-Z][a-z]+)|(\d{1,2})(?!\d)", head.split(" - ")[0])
    mon, last = None, None
    for mname, day in toks:
        if mname and (mname in MONTHS or mname[:3] in abbr):
            mon = MONTHS.get(mname, abbr.get(mname[:3]))
        elif day:
            last = (mon, int(day))
    if last is None or last[0] is None:
        raise ValueError(f"cannot read a meeting day from {head!r}")
    return pd.Timestamp(year=year, month=last[0], day=last[1])


def calendars(years=(2021, 2022)) -> list[dict]:
    h = (RAW / "fomccalendars.htm").read_text(encoding="utf-8", errors="replace")
    out = []
    for y in years:
        i = h.find(f">{y} FOMC Meetings")
        if i < 0:
            raise ValueError(f"fomccalendars.htm has no '{y} FOMC Meetings' section")
        # bound the year at the NEXT "FOMC Meetings" heading of any year: the page
        # is not strictly newest-first (a forward-year section follows 2021)
        j = h.find("FOMC Meetings", i + 20)
        seg = h[i: j if j > i else len(h)]
        # each meeting: a month cell then a date cell, e.g. "January" ... "25-26" or "15-16*"
        cells = [_text(c) for c in re.findall(r'class="[^"]*fomc-meeting__(?:month|date)[^"]*"[^>]*>(.*?)</div>', seg, re.S)]
        if len(cells) % 2:
            raise ValueError(f"{y}: odd number of month/date cells: {cells}")
        hrefs = sorted({re.search(r"(\d{8})", a).group(1) for a in re.findall(r"pressreleases/monetary(\d{8})a\.htm", seg)})
        for mo, dd in zip(cells[::2], cells[1::2]):
            mon = mo.split("/")[-1].strip()
            if mon not in MONTHS:
                raise ValueError(f"{y}: cannot read month {mo!r}")
            unsched = "unscheduled" in dd.lower() or "notation" in dd.lower()
            days = re.findall(r"\d+", dd)
            last = int(days[-1])
            m_last = MONTHS[mon]
            if "/" in mo:            # a meeting spanning two months, e.g. "Apr/May"
                m_last = MONTHS[mon]
            d = pd.Timestamp(year=y, month=m_last, day=last)
            out.append(dict(year=y, heading=f"{mo} {dd}", scheduled=not unsched,
                            cancelled="cancel" in dd.lower(), statement_date=d,
                            n_statement_links=int(d.strftime("%Y%m%d") in hrefs), page="fomccalendars.htm"))
    return out


def main():
    rows = []
    for y in range(2005, 2021):
        rows += historical(y)
    rows += calendars()
    F = pd.DataFrame(rows)
    sch = F[F.scheduled]
    # a cancelled scheduled meeting (2020-03-17/18, replaced by the unscheduled
    # 2020-03-15 meeting) has no statement; it counts toward the year's eight
    # but is not a release day
    bad = sch[sch.statement_date.isna() & ~sch.cancelled]
    if len(bad):
        raise ValueError(f"scheduled meetings with no statement date:\n{bad}")
    per_year = sch.groupby("year").size()
    if not (per_year == 8).all():
        raise ValueError(f"years without exactly 8 scheduled meetings:\n{per_year[per_year != 8]}")
    cal = F[F.page == "fomccalendars.htm"]
    if not (cal.n_statement_links == 1).all():
        raise ValueError(f"calendar-page meetings whose last day has no Statement href:\n{cal[cal.n_statement_links != 1]}")
    F.to_csv(HERE / "fomc_fed.csv", index=False)
    print(F.groupby(["year", "scheduled"]).size().unstack(fill_value=0).to_string())
    print("\nunscheduled events with a statement:")
    print(F[~F.scheduled & F.statement_date.notna()][["heading", "statement_date"]].to_string(index=False))
    print(f"\nwrote fomc_fed.csv: {len(F)} rows, {len(sch)} scheduled")


if __name__ == "__main__":
    main()
