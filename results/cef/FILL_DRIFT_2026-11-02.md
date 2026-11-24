# Paper fill drift vs 15:50 information, cef account (measured 2026-11-02)

**Report only, zero trials.** This measures our own fills; it is not a strategy test. No counter moved.

**Reproducer:** `results/cef/fill_drift_2026-11-02/fill_drift.py`. Run it with QUANTT_ENV_FILE naming the cef key file. It takes `--cache-dir` (a `scripts/cef/live_attribution.py fetch` cache through 2026-10-30, kept outside the repository), `--extra-from 2026-10-31 --extra-through 2026-11-02`, `--split-after 2026-10-12` and an `--out-dir` outside the repository.
- **Output of record:** `results/cef/fill_drift_2026-11-02/aggregates_2026-11-02.json`.
- **Measured** 2026-11-02 by the main session, from a scratch script. **Re-run 2026-11-03** from the committed script: every table and the predictability block reproduced exactly [V].
- **Provenance.** Every figure below is **[V]**, from read-only GETs: FILL activities, SIP quotes, SIP raw daily bars.
- **Public repository.** Aggregates only: no account, order or activity id, and no per-fill row. The per-fill rows are account data. The script writes them only to `<out-dir>/private/`, and refuses any directory git can see or anything under data/ (TL ruling, 2026-11-02: an aggregates-only note is acceptable, as for `results/cef/LIVE_ATTRIBUTION_2026-11-02.md`).

**Why.** The live attribution (PR #26) put the fill line, each fill against that day's close, at −$308.71, or −5.5bp. Most of it fell after 10-13 (−9.5bp). On paper, the plan is sent as market `day` orders at about 15:52 ET (`late_market`, CLAUDE.md hard rule 3). So the fill line mixes the spread we pay with the market's move from 15:50 to the close. This note separates the two and asks whether the move before 15:50 predicts either.

**Scope.** 344 fills, 2026-09-29..2026-11-02: 20 sessions, 13 names, and the 6 fills of 11-02 included.
- **Fill times.** 99.4% of fills land in the 15:52 ET minute (paper `late_market`); earliest 15:52:02, latest 15:59:58.
- **Quotes.**
  - At 15:50: the last SIP quote at or before 15:50:00 ET; median age 0.0s, max 1.4s.
  - At each fill: the last SIP quote at or before its transaction time; median age 3.8s, max 12.5s.
  - No quote was crossed or locked.
- **Close.** The day's SIP daily-bar close, raw.
- **Orders.** No symbol-day had both a buy and a sell.
- **Ties to the attribution.** Over the cache's 338 fills to 10-30, B in USD is a $308.71 cost, equal to PR #26's fill line of −$308.71. A − B − C sums to $0.00 [V: `meta.ties_to_attribution`].

**Signs and units.** s = +1 for a buy, −1 for a sell or short. Every column is in bp of the 15:50 mid, notional-weighted. **Positive = worse for us.**
- A = s·(fill − mid₁₅₅₀): our fill against the 15:50 mid.
- B = s·(fill − close): our fill against the close. This is the attribution's fill line, as a cost.
- C = s·(close − mid₁₅₅₀): the market's move from 15:50 to the close, in our trade direction.
- **A = B + C exactly**, asserted.
- D = s·(fill-time mid − mid₁₅₅₀): the mid's drift from 15:50 to the fill.
- E = s·(fill − fill-time mid): the effective half-spread paid. A = D + E.

**Panels.** `data/cef/cef_universe.csv` (the group column) is read only. Every price is from Alpaca's SIP feed, read at run time.

## All fills
|     |   fills |   sym-days | notional $   |   A mid1550→fill |   B fill vs close |   C mid1550→close |   D mid1550→fill-time mid |   E fill vs fill-time mid |
|:----|--------:|-----------:|:-------------|-----------------:|------------------:|------------------:|--------------------------:|--------------------------:|
| all |     344 |        127 | 570,482      |            10.76 |               5.1 |              5.67 |                       4.6 |                      6.16 |

## By period
|          |   fills |   sym-days | notional $   |   A mid1550→fill |   B fill vs close |   C mid1550→close |   D mid1550→fill-time mid |   E fill vs fill-time mid |
|:---------|--------:|-----------:|:-------------|-----------------:|------------------:|------------------:|--------------------------:|--------------------------:|
| 10-13 on |     247 |         89 | 337,009      |             9.46 |              8.63 |              0.83 |                      3.5  |                      5.96 |
| to 10-12 |      97 |         38 | 233,473      |            12.64 |             -0    |             12.64 |                      6.19 |                      6.46 |

## By group
|       |   fills |   sym-days | notional $   |   A mid1550→fill |   B fill vs close |   C mid1550→close |   D mid1550→fill-time mid |   E fill vs fill-time mid |
|:------|--------:|-----------:|:-------------|-----------------:|------------------:|------------------:|--------------------------:|--------------------------:|
| hy    |      35 |         11 | 31,764       |             9.19 |              2.6  |              6.59 |                      3.02 |                      6.17 |
| loan  |      29 |         10 | 97,188       |             7.65 |              2.23 |              5.43 |                      0.84 |                      6.81 |
| multi |     228 |         85 | 266,533      |            14.66 |              4.97 |              9.69 |                      8.74 |                      5.92 |
| muni  |      52 |         21 | 174,998      |             6.84 |              7.33 |             -0.49 |                      0.68 |                      6.16 |

## By side
|      |   fills |   sym-days | notional $   |   A mid1550→fill |   B fill vs close |   C mid1550→close |   D mid1550→fill-time mid |   E fill vs fill-time mid |
|:-----|--------:|-----------:|:-------------|-----------------:|------------------:|------------------:|--------------------------:|--------------------------:|
| buy  |     174 |         65 | 283,972      |            14.97 |              6.65 |              8.33 |                      8.55 |                      6.42 |
| sell |     170 |         62 | 286,510      |             6.59 |              3.56 |              3.03 |                      0.69 |                      5.9  |

## Period × group (small cells: read with care)
|                  |   fills |   sym-days | notional $   |   A mid1550→fill |   B fill vs close |   C mid1550→close |   D mid1550→fill-time mid |   E fill vs fill-time mid |
|:-----------------|--------:|-----------:|:-------------|-----------------:|------------------:|------------------:|--------------------------:|--------------------------:|
| 10-13 on | hy    |      28 |          9 | 24,239       |            11.22 |             -8.45 |             19.67 |                      5.01 |                      6.21 |
| 10-13 on | loan  |      15 |          6 | 47,501       |             8.25 |             11.41 |             -3.17 |                      1.39 |                      6.85 |
| 10-13 on | multi |     160 |         59 | 138,537      |             9.19 |              7.82 |              1.37 |                      3.48 |                      5.71 |
| 10-13 on | muni  |      44 |         15 | 126,733      |             9.88 |             11.74 |             -1.85 |                      4.03 |                      5.85 |
| to 10-12 | hy    |       7 |          2 | 7,525        |             2.66 |             38.19 |            -35.53 |                     -3.38 |                      6.04 |
| to 10-12 | loan  |      14 |          4 | 49,688       |             7.09 |             -6.55 |             13.64 |                      0.31 |                      6.78 |
| to 10-12 | multi |      68 |         26 | 127,996      |            20.59 |              1.89 |             18.7  |                     14.43 |                      6.16 |
| to 10-12 | muni  |       8 |          6 | 48,265       |            -1.15 |             -4.22 |              3.08 |                     -8.14 |                      6.99 |

## Predictability: does sign(s·(mid₁₅₅₀ − previous close)) predict B or C?
Unit: symbol-day (one order per name per session; 127). x = +1 when the price had already moved in our trade direction by 15:50 (buying after a rise, selling after a fall).

| x | symbol-days | notional $ | B wtd bp | C wtd bp | B mean (t) | C mean (t) |
|---|---:|---:|---:|---:|---|---|
| +1 (moved with our side) | 80 | 329,065 | 7.56 | 6.34 | 7.62 (2.63) | 2.06 (0.63) |
| −1 (moved against our side) | 47 | 241,417 | 1.74 | 4.76 | 6.93 (1.71) | -0.91 (-0.23) |

Difference (+1 minus −1), mean over the 17 days holding both, clustered by date: B 2.95bp (t 0.55), C 0.03bp (t 0.0). Spearman over 127 symbol-days: x vs B 0.009, x vs C 0.061.
**Reading: no evidence that the pre-15:50 move predicts either B or C** at this sample (20 sessions, 127 orders). The weighted gap in B (7.6 vs 1.7bp) does not survive clustering by date.

## What it says (measurement, not a strategy claim)
1. Against the 15:50 mid, our fills cost **10.8bp** (A). About **6.2bp** of it is the half-spread paid at the fill (E: paper fills at the NBBO, so a buy pays the ask) and **4.6bp** the mid's drift in our direction in the ~2 minutes to 15:52 (D), concentrated in buys (8.6bp) and in the multi group (8.7bp).
2. Against the close, B is 5.1bp, but it splits sharply by period: **0.0bp to 10-12, 8.6bp from 10-13**. Before 10-12 the market kept moving against us after 15:50 (C 12.6bp), so a fill at 15:52 was as good as the close; after 10-13 it did not (C 0.8bp), and the half-spread shows through.
3. Buys cost more than sells on every measure (A 15.0 vs 6.6bp).
4. Twenty sessions: every period × group cell is small; nothing here is a tested effect.
