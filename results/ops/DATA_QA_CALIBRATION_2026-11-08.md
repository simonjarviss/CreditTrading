# Nightly data QA: threshold calibration (2026-11-08)

Report only, zero trials. Reproducer: `python3 results/ops/data_qa_calibration/calibrate.py`.
Output of record: `results/ops/data_qa_calibration/calibration_2026-11-08.json`.
Thresholds live in `scripts/ops/data_qa.py` `THRESHOLDS`; a test pins them to that JSON.
Panels read: `data/cef` to 2026-10-14 (the core's 13 names) and `data/cef_families` to 2026-10-09
(C4's 74 frozen names; C4's own `data/cef_c4` is on the VM only). [V: read 2026-11-08]

**Method.** Fit window 2005-01-01..2022-12-31 (H13: nothing from 2023 onward enters a rate or a
choice); Q6 from 2013-01-01 (landmine 8: the book is flat before). Deployed names only; the sealed
holdout names are never read. The design's budget is at most 1 flag per book per week on panels with
no known defect, jointly over the checks with a free threshold, so each of Q2..Q6 gets 0.2/week.
Each threshold is the LEAST STRICT value on a declared grid whose fit rate is at or under its 0.2 share
(so the false-alarm rate sits close to the share by construction), with the rate one grid step
either side shown (H8). Nothing was tuned against the recall.

| check | threshold | core: flags/wk (rate at next-stricter / next-looser step) | C4: flags/wk (rate at next-stricter / next-looser step) | recall on the known positives |
|---|---|---|---|---|
| Q1 row count differs | no free threshold | price 0.004, NAV 0.010 | price 0.042, NAV 0.065 | the 2026-10-22 PDO gap, as a synthetic replica only (test): the real panel state is on the VM, not read here |
| Q2 NAV misprint | z ≥ core 6.5, C4 10.0 (over the name's own trailing mean \|r\|) | 0.192 (0.221 / 0.170) | 0.177 (0.200 / 0.161) | **C4 9/9 masks** (7 episodes; PFO's three days covered by one flag's span). Core: no positive exists (none of the 9 masks is in its 13 names) |
| Q3 stale NAV | run > the name's prior-year longest run + δ: core δ=0, C4 δ=1 | 0.110 (none looser) | 0.087 (0.400 / 0.015) | **Not measurable, and 0 by construction on the gate's record:** the stale-NAV gate's record is one-row stale copies (`results/cef/LIVE_NAV_QUALITY_2026-10-12.md`), and a one-row repeat is not a run longer than the name's norm; about a fifth of NAV rows genuinely repeat, so only the second source separates them. Reported, not tuned |
| Q4 split-like step | tol = ln(1.15) from `data_guards.SPLIT_TOL`; no free threshold | 0.000 | 0.004 (the 4 rows are real one-day moves of about -50% in EMO and KYN, 2020-03) | **IGR 1/1** (close x2.88 on 2026-09-09, NAV x2.99 on 09-08, with no corporate-action row; with the row it is silent). **BTO, NXG, EMO 0/3:** no split-sized step exists in the panel on those days: that defect was a recorded split applied to an already-adjusted close, a formula fault `data_guards.guard_split_basis` catches. TYG is not in C4's 74 names |
| Q5 discount outlier | first night of \|close/NAV − 1\| past the line: core 22%, C4 27% | 0.181 (0.206 / 0.177) | 0.189 (0.218 / 0.144) | **BME 2021-06-28 (+75.6%) flagged** at C4's 27%; BME is not in the core's universe. Counted as flags emit: first night past the line (yesterday inside or absent) |
| Q6 ADV-floor margin | margin m: core 2.5%, C4 13% | 0.200 (0.155 / 0.246) | 0.196 (0.176 / 0.246) | **Core 13/22** thin-episode starts in fit (`results/backtests/thin-days-2026-11-03/sleeve_thin.csv`, 2013 on) flagged in the 5 sessions before or on the start. C4 has no thin-session record: not measurable |

Sum of the check rates (bound on the union): core 0.683/wk, C4 0.653/wk, against the budget of 1.

**What falls short, stated as it is.** Q3 cannot catch the one-row stale copies that were its named
positives, at any threshold. Q6's 13/22 is what the budget allows on the core. Q4 misses three of the
design's five named positives because they are not panel steps. Q2's flag count is mostly one-sided
NAV moves that do not revert (about 13–14% of flags at these thresholds revert within 3 sessions):
the check names them SUSPECT, and the fraction that revert is the fraction that are misprints.

**Q5's rule, and the design's line.** A flag is the FIRST night past the line. Counting every
night past the design's flat ±50pp line ran 0.839 flags/week on the core (standing premia, not
defects), and HGLB's −39.9% on the newest C4 panel (2026-10-09) would flag nightly at any line it
sits beyond, so the first-crossing count is the honest unit of a false alarm. Measured that way the
least strict lines inside the 0.2/week share are 22% (core) and 27% (C4); the ±50pp line itself runs
0.053/wk (core) and 0.004/wk (C4), and would also flag BME. Standing names are named in the report's
Q5 line, never as flags. The team lead may prefer ±50pp (fewer flags, the same recall on the one known
positive); that is a one-line change to `THRESHOLDS` and this note.

**Q6's rule differs from the design's sentence, deliberately.** "The least liquid eligible name
within a margin of the floor" fires on about every session on C4 (median least-liquid ratio about
1.03×: with 74 names some name is always near the floor). The check instead fires on the count:
fewer than `min_names` names keep the margin, so one ADV dip makes the sleeve thin. Thin nights
themselves are not flagged; they are the sleeve's rule running, not a data defect.
