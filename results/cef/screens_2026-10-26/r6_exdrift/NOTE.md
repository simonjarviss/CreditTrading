# Post-ex-date drift in CEFs — second-method check (zero trials, 2026-10-26)

**Why.** The independent review of r3 (`../r3_review/`) found C4's ex-date concentration is a generic
post-ex drift, not the z-score. This re-measures that drift with code independent of `c4_families.py`.
**Post-hoc:** the hypothesis was formed after the fit window was seen. Nothing here is out-of-sample evidence.

**Method.** Total return = (close + cash distribution on the ex-date) / prior close − 1, minus the equal-weight
same-date mean of the panel. Split days ±5 and |r| > 30% are masked. CAR(+1..+3) is a short entered at
the ex-date close (offset 0) and covered at +3: it is known in advance and fits shift(2), and it never holds
over a record date, so it owes no distribution. t is clustered by calendar month. Dates ≤ 2022-12-30 are asserted.

| set | events | offset −1 | +1 | +2 | +3 | CAR(+1..+3) | t (month-clustered) |
|---|---:|---:|---:|---:|---:|---:|---:|
| C4 families, all years in panel (1982–2022) [V]; 2005–22 only: −34.3bp, t −14.9 [V, added 2026-10-27] | 19,653 | +9.9 | −13.3 | −9.3 | −7.5 | **−30.1bp** | −5.6 |
| … ex Eaton Vance [V] | 17,673 | | | | | −30.0bp | −5.6 |
| … ex EV, 2005–09 / 2010–15 / 2016–22 [V] | 3,063 / 4,276 / 7,164 | | | | | −33.0 / −30.5 / −38.1 | −5.2 / −8.1 / −14.8 |
| … by distribution-size quartile, low → high [V] | ~4,900 each | | | | | −24.1 / −22.5 / −34.3 / −39.6 | −2.0 / −2.4 / −3.0 / −5.9 |
| credit CEFs (deployed 13 + NAD/NEA/NVG/NZF), 2005–22 [V] | 3,226 | +11.1 | −10.1 | −4.8 | −5.6 | **−20.5bp** | −6.8 |

All families are negative; equity_global is weakest (−13.7bp, t −1.2).

**Reading.**
- Prices run up into the ex-date and fall for three sessions after it, while NAV does not (r3 and the review).
- That is the dividend-capture / yield-chaser footprint [U as a mechanism].
- It is not one sponsor (it holds ex Eaton Vance) and not one era (2005–09 too).
- It is larger for larger distributions.
- **The review's point stands:** C4's z-score is not what earns it. C4 harvests it by being net short into ex-dates.

Reproduce: `python3 -B check.py <repo>`; `python3 -B check_credit.py <repo>`
(`out.txt`, `out_credit.txt`; the credit script's per-group line errors after the pooled result prints).
