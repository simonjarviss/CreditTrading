"""Parse the kept form 487 prospectuses into a flow table: trust, deposit date, termination date, holdings.

    python3 results/ideas/uit_cef_flows/parse.py            # reads the crawl's cache, no network

WRITTEN 2026-11-18, after the interruption (the first researcher's crawl.py names a parse.py
that was never written). It reads no return.

WHAT A PROSPECTUS LOOKS LIKE (both sponsors file plain text with <TABLE> blocks)
  First Trust   one filing "FT <n>" holds one or several trusts. Each trust has a
                "Schedule of Investments" page: the trust's name, "FT <n>", "At the Opening of
                Business on the Initial Date of Deposit-<date>", then lines
                    TICKER   Name of issuer      4.00%   402   $ 15.15   $ 6,090
                and a note "(1) ... The Trust has a Mandatory Termination Date of <date>."
  Guggenheim    "Trust Portfolio", the registrant's name, the trust's name, "The Trust
                Portfolio as of the Inception Date, <date>", then the same kind of line; the
                termination date is in that trust's "Essential Information" block, BEFORE its
                portfolio ("Termination Date     December 6, 2013").
RULES (fixed here, before any return is read)
  * a holding line is a ticker of one to five capitals (an optional class suffix), a name,
    a percentage, a share count, a price and a cost, in that order, on one line;
  * a holding belongs to the last portfolio header above it;
  * a trust's termination date: First Trust, the first "Mandatory Termination Date of <date>"
    after its header and before the next trust's header, else the only termination date in
    the filing; Guggenheim, the last "Termination Date <date>" before its header. A trust
    with no date by these rules is DROPPED and counted, never guessed;
  * a trust must be filed before it terminates and terminate within 6 years of its deposit,
    or it is dropped and counted (a mis-parsed date).
Whether a line is a closed-end fund is decided in explore.py against CRSP (licensed), not here.
Output (EDGAR is public; kept beside the cache all the same): ~/quantt_research/uit_cef_flows/
trusts.parquet (one row per trust) and holdings.parquet (one row per trust and ticker).
"""
from __future__ import annotations

import gzip, json, re, sys
from collections import Counter
from pathlib import Path

import pandas as pd

OUT = Path.home() / "quantt_research" / "uit_cef_flows"
CACHE = OUT / "edgar_cache"
LOG = OUT / "filings.jsonl"
DATE = r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})"
HOLD = re.compile(r"^[ \t]{0,12}([A-Z]{1,5}(?:[./][A-Z])?)[*+#\s]\s*(\S.*?\S)\s+\(?(\d{1,3}\.\d{1,3})\)?%?\s+([\d,]+)\s+\$?\s*([\d,]+\.\d+)\s+\$?\s*([\d,]+)\s*$", re.M)
FT_HEAD = re.compile(r"Schedule of Investments(?:\s*\(cont'd\.?\))?[ \t]*\n\s*\n((?:[^\n]*\S[^\n]*\n){1,4}?)\s*FT \d+[ \t]*\n(.{0,300}?)Initial\s+Date\s+of\s+Deposit\s*-\s*" + DATE, re.S)
FT_TERM = re.compile(r"Mandatory\s+Termination\s+Date\s+of\s+" + DATE)
FT_TERM_ANY = re.compile(r"Mandatory\s+Termination\s+Date[^\n]{0,80}?" + DATE)
GU_HEAD = re.compile(r"Trust Portfolio(?:\s*\(continued\))?[ \t]*\n\s*(?:Guggenheim|Claymore)[^\n]*Series\s+\d+[ \t]*\n((?:[^\n]*\S[^\n]*\n){1,3}?)\s*The Trust Portfolio as of the Inception Date,\s+" + DATE, re.S | re.I)
GU_TERM = re.compile(r"^\s*(?:Mandatory\s+)?Termination Date\s+" + DATE, re.M)


def read(path: str) -> str:
    """The cached main document (crawl.py stores it gzip-compressed)."""
    from urllib.parse import urlsplit
    p = CACHE / "www.sec.gov" / urlsplit("https://www.sec.gov/Archives/" + path).path.lstrip("/")
    b = p.read_bytes()
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    t = b.decode("latin-1")
    a = t.find("<DOCUMENT>")
    t = t[a:t.find("</DOCUMENT>", a)] if a >= 0 else t
    return t


def html_rows(t: str) -> str:
    """FIX MADE 2026-11-18 (second resumption, before any return was read). Guggenheim files HTML,
    not plain text, from mid-2020: 326 kept filings had "no portfolio header". Each table row
    becomes one text line (cells joined by three spaces, two leading spaces so a wrapped name's
    second line still reads as a continuation), and the plain-text rules above then apply
    unchanged. Text outside tables is dropped: the header, the holdings and the termination
    date are all table rows in this format."""
    import html as _h
    out = []
    for m in re.finditer(r"<TR[^>]*>(.*?)</TR>", t, re.S | re.I):
        cells = [re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ")).strip()
                 for c in re.findall(r"<TD[^>]*>(.*?)</TD>", m.group(1), re.S | re.I)]
        cells = [c for c in cells if c]
        if cells:
            out.append("  " + "   ".join(cells))
    return "\n".join(out) + "\n"


def day(s: str) -> pd.Timestamp:
    return pd.to_datetime(re.sub(r"\s+", " ", s), format="%B %d, %Y")


def name_of(block: str) -> str:
    return re.sub(r"\s+", " ", block).strip()


TICK = re.compile(r"^[ \t]{0,12}([A-Z]{1,5}(?:[./][A-Z])?)[*+#\s]\s*(\S.*?)\s*$")
CONT = re.compile(r"^[ \t]+(.*?)\s*\(?(\d{1,3}\.\d{1,3})\)?%?\s+([\d,]+)\s+\$?\s*([\d,]+\.\d+)\s+\$?\s*([\d,]+)\s*$")


def find_holdings(txt: str) -> list[tuple]:
    """Holding lines, with their offset. A long fund name wraps: the ticker and the start of the
    name on one line, the rest of the name and the four numbers on the next (Guggenheim does
    this for a third of its closed-end funds), so a ticker line with no numbers is joined to a
    following line that carries them and is not itself a holding line."""
    out, off = [], 0
    lines = txt.split("\n")
    num = lambda g: (float(g[0]), int(g[1].replace(",", "")), float(g[2].replace(",", "")), int(g[3].replace(",", "")))
    full = [HOLD.match(ln) for ln in lines]
    for i, ln in enumerate(lines):
        m = full[i]
        if m:
            out.append((off, m.group(1), m.group(2), *num(m.groups()[2:])))
        elif i + 1 < len(lines) and full[i + 1] is None:
            a, b = TICK.match(ln), CONT.match(lines[i + 1])
            if a and b and not re.search(r"\d\s*$", ln):
                out.append((off, a.group(1), (a.group(2) + " " + b.group(1)).strip(), *num(b.groups()[1:])))
        off += len(ln) + 1
    return out


def parse(txt: str, sponsor: str) -> tuple[list[dict], Counter]:
    """Every trust in one prospectus: name, deposit, termination, holdings."""
    why = Counter()
    heads = []
    for m in (FT_HEAD if sponsor == "FT" else GU_HEAD).finditer(txt):
        heads.append((m.start(), name_of(m.group(1)), day(m.group(3) if sponsor == "FT" else m.group(2))))
    if not heads:
        why["no portfolio header"] += 1
        return [], why
    holds = find_holdings(txt)
    # a trust is its run of consecutive headers with one name ("cont'd" pages repeat the header)
    trusts: list[dict] = []
    for pos, nm, dep in heads:
        if trusts and trusts[-1]["trust"] == nm:
            continue
        trusts.append({"trust": nm, "deposit": dep, "pos": pos})
    all_terms = sorted({day(m.group(1)) for m in (FT_TERM_ANY if sponsor == "FT" else GU_TERM).finditer(txt)})
    out = []
    for i, t in enumerate(trusts):
        end = trusts[i + 1]["pos"] if i + 1 < len(trusts) else len(txt)
        term = None
        if sponsor == "FT":
            m = FT_TERM.search(txt, t["pos"], end)
            if m:
                term = day(m.group(1))
            elif len(all_terms) == 1:
                term = all_terms[0]
        else:
            ms = [m for m in GU_TERM.finditer(txt, 0, t["pos"])]
            prev = trusts[i - 1]["pos"] if i else 0
            ms = [m for m in ms if m.start() >= prev]          # the block between the last trust's portfolio and this one
            if ms:
                term = day(ms[-1].group(1))
            elif len(all_terms) == 1:
                term = all_terms[0]
        lines = [h for h in holds if t["pos"] <= h[0] < end]
        if term is None:
            why["no termination date"] += 1
            continue
        if not lines:
            why["no holding line"] += 1
            continue
        if not (t["deposit"] < term <= t["deposit"] + pd.Timedelta(days=366 * 6)):
            why["termination not within 6 years after deposit"] += 1
            continue
        seen, rows = set(), []
        for _, tk, nm, pct, sh, px, cost in lines:
            if tk in seen:
                continue
            seen.add(tk)
            rows.append({"ticker": tk, "name": nm, "pct": pct, "shares": sh, "price": px, "cost": cost})
        out.append({"trust": t["trust"], "deposit": t["deposit"], "termination": term, "holdings": rows})
    return out, why


def main() -> int:
    kept = [json.loads(ln) for ln in LOG.read_text().splitlines()]
    kept = [k for k in kept if k["kept"]]
    T, H, why, by_year = [], [], Counter(), Counter()
    for k in kept:
        txt = read(k["path"])
        trusts, w = parse(txt, k["sponsor"])
        if not trusts and re.search(r"<TR", txt, re.I):       # an HTML prospectus (see html_rows); First Trust's <PRE> text parses as it is
            trusts, w = parse(html_rows(txt), k["sponsor"])
        why.update(w)
        by_year[(k["filed"][:4], k["sponsor"], bool(trusts))] += 1
        for j, t in enumerate(trusts):
            if not (pd.Timestamp(k["filed"]) < t["termination"]):
                why["filed on or after termination"] += 1
                continue
            tid = f"{k['path'].split('/')[-1][:-4]}#{j}"
            T.append({"trust_id": tid, "sponsor": k["sponsor"], "registrant": k["name"], "cik": str(k["cik"]), "filed": pd.Timestamp(k["filed"]),
                      "trust": t["trust"], "deposit": t["deposit"], "termination": t["termination"],
                      "n_lines": len(t["holdings"]), "pct_sum": sum(h["pct"] for h in t["holdings"]),
                      "seed_cost": sum(h["cost"] for h in t["holdings"])})
            H += [{"trust_id": tid, **h} for h in t["holdings"]]
    T, H = pd.DataFrame(T), pd.DataFrame(H)
    T.to_parquet(OUT / "trusts.parquet"); H.to_parquet(OUT / "holdings.parquet")
    print("kept filings", len(kept), "| trusts parsed", len(T), "| holding lines", len(H))
    print("dropped:", dict(why))
    y = pd.Series(by_year).unstack().fillna(0).astype(int)
    print(y.to_string())
    print("pct_sum quantiles", T["pct_sum"].quantile([.05, .25, .5, .75, .95]).round(1).to_dict())
    print(T.groupby([T["deposit"].dt.year, "sponsor"]).size().unstack().to_string())
    (OUT / "parse_summary.json").write_text(json.dumps({"kept_filings": len(kept), "trusts": len(T), "lines": len(H), "dropped": dict(why)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
