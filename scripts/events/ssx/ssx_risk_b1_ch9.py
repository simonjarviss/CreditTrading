"""B1(b): a free count of municipal bankruptcies a year, from the Federal
Judicial Center's bankruptcy case file as mirrored on R2. Zero trials.

WHY
---
EMMA's continuing-disclosure feed is the natural muni-event source, but its
terms ban automated collection and its bulk products cost money (cards, B1).
The B1 kill gate needs an independent, lawful, free count of muni
defaults/impairments. Chapter 9 of the Bankruptcy Code is the municipal
chapter, so the count of chapter 9 cases filed per year is the strictest such
count: it misses payment defaults outside bankruptcy (most muni defaults are
conduit/project bonds that never file), so it is a LOWER bound.

DATA
----
R2 `wrds/fjc_litigation/bankruptcy.parquet` (38.0m rows; a case appears once per
FJC snapshot), read through `src/data/r2.py` only. Distinct `casekey` with
original filing chapter `orgflchp` = '9', by year of `filedate`, 2008-2025, and
by `district`. Licensed (WRDS mirror): only counts leave the cache directory.
Event counts may run to 2025-12-31 (seat brief); no market data is read.

Reproduce:
    QUANTT_ENV_FILE=<abs path to config/.env> python3 scripts/events/ssx/ssx_risk_b1_ch9.py
Output: results/events/ssx/ssx_risk/b1_chapter9_per_year.csv (counts only)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = REPO / "results" / "events" / "ssx" / "ssx_risk"


def main() -> int:
    from src.data import r2
    con = r2.connect()
    p = r2.r2_path("fjc_litigation", "bankruptcy")
    chk = r2.q(con, f"SELECT orgflchp, COUNT(DISTINCT casekey) n FROM read_parquet('{p}') "
                    "WHERE filedate >= DATE '2008-01-01' AND filedate <= DATE '2025-12-31' "
                    "GROUP BY 1 ORDER BY 2 DESC")
    codes = chk.orgflchp.astype(str).str.strip().tolist()
    if "9" not in codes:
        raise ValueError(f"no orgflchp == '9' in the FJC file; codes seen: {codes[:20]}")
    y = r2.q(con, f"SELECT EXTRACT(year FROM filedate) AS year, COUNT(DISTINCT casekey) AS ch9_cases "
                  f"FROM read_parquet('{p}') WHERE TRIM(orgflchp) = '9' "
                  "AND filedate >= DATE '2008-01-01' AND filedate <= DATE '2025-12-31' GROUP BY 1 ORDER BY 1")
    d = r2.q(con, f"SELECT district, COUNT(DISTINCT casekey) AS ch9_cases FROM read_parquet('{p}') "
                  "WHERE TRIM(orgflchp) = '9' AND filedate >= DATE '2008-01-01' AND filedate <= DATE '2025-12-31' "
                  "GROUP BY 1 ORDER BY 2 DESC")
    OUT.mkdir(parents=True, exist_ok=True)
    y.to_csv(OUT / "b1_chapter9_per_year.csv", index=False)
    d.to_csv(OUT / "b1_chapter9_by_district.csv", index=False)
    summ = {"chapter_codes_2008_2025": dict(zip(codes, chk.n.astype(int).tolist())),
            "ch9_total_2008_2025": int(y.ch9_cases.sum()), "ch9_per_year_median": float(y.ch9_cases.median()),
            "ch9_per_year": dict(zip(y.year.astype(int).tolist(), y.ch9_cases.astype(int).tolist())),
            "top_districts": dict(zip(d.district.head(10).astype(str), d.ch9_cases.head(10).astype(int)))}
    (OUT / "b1_chapter9_summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
