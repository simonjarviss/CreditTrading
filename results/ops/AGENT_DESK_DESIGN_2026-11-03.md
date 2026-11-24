# Agent desk, phase 1: nightly data QA per book, and a daily risk agent (DRAFT for the team lead)

> **Status, 2026-11-24.** Built on 2026-11-08 in 65a0919: `scripts/ops/data_qa.py` and
> `scripts/ops/risk_daily.py`, report-only, on VM timers (`install_vm --reports`). Those two
> scripts and `docs/RUNBOOK.md` cite this file as their design, which is why it is merged now,
> unchanged below this box (team lead, 2026-11-24). Where it differs from the code, the code is
> what runs. Its trial counts and "every tuned parameter is a trial" are superseded: the team lead
> dropped pre-registration and the trial counters on 2026-11-09 (`docs/SYSTEM.md` section 5,
> `docs/MISSION.md`).

Date: 2026-11-03   Status: **DRAFT, for the team lead's ruling**. Nothing here is built or scheduled. Zero trials.

The team lead asked on 2026-11-03 whether autonomous agents (risk manager, traders, short- and long-term
trading agents, a portfolio manager, analysts, data analysts per sleeve) could raise alpha and lower risk.
The recommendation was to build the agents that **research, monitor and propose**, and not the ones that
trade or re-tune the live book. The reasons:

- every tuned parameter is a trial (CEF stands at 55, bar 2.83);
- an LLM's trading decision cannot be backtested, pre-registered or reproduced;
- two runners on one account can double the book (CLAUDE.md rule 2).

The team lead then asked for this draft of the first two: "yes draft those".

## 0. The answer in one table

| | data QA (per book: `cef`, `c4`) | risk (both accounts, one report) |
|---|---|---|
| **question it answers** | Is tonight's panel fit to decide on? Which name-days look wrong, and why? | Where does each account stand against every limit and stop, and what moved it? |
| **when** | after the VM's collect writes the day's panels, **before the 22:00 decide** | after the EOD stamp (20:00 New York) and the decide, in the evening routine (today's 22:17 slot) |
| **who flags** | **a deterministic script**: `scripts/ops/data_qa.py`, tested, every threshold derived and recorded | **a deterministic script**: `scripts/ops/risk_daily.py`, wrapping the existing readers below |
| **what the agent does** | Only when a flag fires: researches it (filings, distributions, splits, mergers) and **proposes a ruling** (KEEP/MASK/HOLD), to the DG-L3 standard. The team lead signs it | Writes the brief: what moved and why (attribution), what is near a limit, and which stop is due a read |
| **what it may write** | `results/ops/data_qa/<book>/<date>.{md,json}`, plus an EVIDENCE_LOG entry when it flags | `results/ops/risk/<date>.{md,json}`, plus an EVIDENCE_LOG entry |
| **what it may never do** | edit `data/`, mask a value itself, send, cancel, arm, disarm, halt | send, cancel, arm, disarm, halt, or change a spec, book json or multiplier |
| **cost** | the script is free; **no flag, no agent** | the script is free; one short agent brief per evening |

**The principle: deterministic code decides what is flagged and computes every number. Agents only triage, research
and explain. Nothing an agent writes touches the order path.** Every number in either report comes from a script
that can be re-run, never from an agent's recall (CLAUDE.md, data rules).

## 1. Nightly data QA, per book

### 1.1 Why

Six of the graveyard's thirteen deaths were stale-price artifacts (`/graveyard`, pattern 1). On 2026-11-03,
trial 54's DG-L3 found 9 NAV misprints by hand: NAVs that jump and revert while the price does not move. Two
examples are PFO, which read 16.30 for three sessions between 12.40s, and BME's +75% discount on 2021-06-28.
Today the book's own defences are the missing-NAV hold, the stale-NAV gate (report mode), the spike guard
(off for the core) and the corporate-action gate (report mode). Nothing looks for a **misprint that is
present and plausible-looking**.

### 1.2 The checks (deterministic, per name, on the day's panel)

| id | check | flags when | known positives for calibration |
|---|---|---|---|
| Q1 | panel freshness | the last price or NAV date is not the expected trading day, or the row count differs from yesterday's | the 2026-10-22 data-gate refusals (`ops.replay_exposure` output) |
| Q2 | NAV misprint | a one-day NAV move far out in the name's own trailing distribution **that reverts** within a few sessions while the price does not follow | the 9 DG-L3 masks (`results/cef/prereg_c4_level/dgl3_rulings_2026-11-03.csv`) |
| Q3 | stale NAV | the NAV is unchanged for longer than the name's own trailing norm | the stale-NAV gate's record |
| Q4 | split-like step | a price or NAV ratio near a split ratio, with no corporate-action row | IGR 1:3, 2026-09-08 (C4 seed rulings); BTO, TYG, NXG, EMO |
| Q5 | discount outlier | discount beyond the panel's ±50pp flag line | BME 2021-06-28 |
| Q6 | ADV-floor margin | the least liquid eligible name within a margin of the $3m floor: the book is "one ADV dip from a thin session" (2027-ae, 2026-11-03: median 1.13× on 6–7-name sessions) | the thin sessions in `results/backtests/thin-days-2026-11-03/` |
| Q7 | corporate actions on our names | an announcement touching a held or targeted fund inside the gate's windows, including the unresolved-party rows | the three unresolved rows (db0847b7…, e34ddd44…, 6abeb209…) |
| Q8 | first-fetch vs seed (C4, first nights only) | rows the fetch replaced differ from the seed beyond rounding | checklist step 5 |

**Thresholds follow H14 and H8.** They are not numbers written here. Each one is derived on fit data to a
declared **false-alarm budget**: at most one flag per book per week on panels with no known defect. Then they
are checked for **recall on the known positives** in the right-hand column. The derivation, its inputs and the
value chosen go into the script's docstring and a dated calibration note. Any threshold that cannot reach
the recall at the budget is reported as such, not tuned until it passes.

### 1.3 What happens on a flag

1. The script writes the flag with its evidence (the name, the date, the series either side, the rule that fired).
2. One agent (`market-structure-analyst`, or `equity-research` for a fund-specific event) researches it and
   writes a **proposed ruling** to the DG-L3 standard: KEEP (real), MASK (misprint, which leg), or HOLD (the
   name's session should hold). It cites what it fetched.
3. **The team lead signs or edits it.** A signed ruling enters the book only through the existing paths:
   - a bar or seed ruling file and a release;
   - the missing-NAV hold;
   - `ops/HALT_<book>.md`, written by the team lead.
   The agent never edits `data/` or a rulings file the book reads.
4. **A flag on a held or targeted name before the decide** is a WATCH item in the evening brief. The book still
   decides as it does today.

## 2. The daily risk agent

### 2.1 Why

The stops exist, but nothing reads them on a schedule:
- trial 53's R1–R3 per account;
- C4's H11 kill rule, rebuilt on the blended book for v5;
- trial 54's L1 at 120 armed sessions;
- HALVE 12% and KILL 18%, in report mode;
- te4's K0–K3 once active.

The core's live loss to 10-30 (−$982.14 official) was mostly a NAV component (−$2,250.74, muni shorts −$1,849)
that no daily report attributed while it happened (`results/cef/LIVE_ATTRIBUTION_2026-11-02.md`).

### 2.2 What `risk_daily.py` computes (read-only, both accounts)

| block | content | source (existing code) |
|---|---|---|
| P&L | the day and to-date P&L, official EOD (the P&L of record) and the 17:30 snapshot, labelled separately, never blended | `quantt/session/verify.py` records (`equity.csv`, `scores.csv`) |
| drawdown | against HALVE/KILL, report mode | `quantt/session/drawdown.py` |
| stops | R1–R3 per account, re-measured on the read date | `results/cef/prereg_voltarget/stops.py` (`--c4-exact` for C4 v5) |
| kill rules | the core's 60-session rule; C4's H11; trial 54's L1 at 120 sessions | `scripts/cef/c4_paper_benchmark.py` references |
| exposure | gross and net against the caps (1.80/m, 1.90/m); the margin cushion (maintenance against equity, gate 8); concentration (top name, muni share, family share) | the plan and the account snapshot in `plan.json` |
| attribution | the discount component against the NAV component, per account | `scripts/cef/live_attribution.py` |
| factor exposure | MUNI / TERM / credit / loan (the core); equity market and sector (C4) | `scripts/cef/exposure_readout.py`; the risk lanes' readouts (`docs/TEAM.md` §1) |
| execution | orders planned against filled, skipped and why; fill cost against breakeven | `results/cef/fill_drift_2026-11-02/fill_drift.py`; `tca.csv` |
| diversification | the live correlation between the two accounts, against the fit's ρ | the two EOD series |

**A missing input is UNMEASURED, named, never inferred** (CLAUDE.md: no silent fallbacks).

### 2.3 Severity, and who acts

| level | meaning | action |
|---|---|---|
| INFO | inside every limit | logged |
| WATCH | within a declared distance of a limit, or a data-QA flag on a held name | in the evening brief |
| **ACT** | a pre-registered stop has fired (e.g. R1 past D_R, or L1 at 120 sessions) | **the team lead acts**, by the route the trial's pre-registration names, usually `/spec-change` to revert. The agent writes the ACT line and the exact revert, and does nothing else |

## 3. Where they run

| phase | how | needs |
|---|---|---|
| **1 (proposed: after C4's first armed week, about 2026-11-10)** | from the laptop, in the evening routine: `vmpnl.sh` pulls the day's records read-only, the two scripts run locally, and an agent writes the briefs only when needed | the two scripts with tests; a pull of the panels' last rows (a `vmpnl.sh` addition); no credentials, because everything is read from files the runner already wrote |
| 2 | the two deterministic scripts as a **report-only VM timer**, scheduled clear of the runner's slots and outside its lock, writing to a non-git path under `quantt_state` | a release with its own release-check; the team lead's go (deferred on 2026-11-03 until after C4's first week) |
| 3 (not proposed now) | the risk agent may write `ops/HALT_<book>.md` on a **pre-registered** ACT trigger. Fail-closed only: a halt, never a send or a resize | its own ruling, pre-registered triggers, and a test that no path sends |

## 4. Tests and evidence

- **Q1–Q8:** each check has a test that injects its defect into a synthetic panel and is flagged, and a clean
  panel that is not. Synthetic data tests the code, never a market claim. Each test is shown to fail against the
  code without the check.
- **Calibration:** the note for Q2–Q6 reports false alarms on clean fit panels and recall on the known positives,
  at the threshold chosen.
- **Risk script:** `risk_daily.py` reproduces `stops.py`, `live_attribution.py` and `exposure_readout.py` byte for
  byte on the same inputs. It is a wrapper, not a second implementation.
- **The evidence pack:** every flag, ruling and ACT line gets an EVIDENCE_LOG entry
  (`results/report/README.md`, once PR #45 merges).

## 5. Questions for the team lead, each with a recommended answer

1. **Build phase 1 now, and start running it after C4's first armed week?** **Yes.** The scripts and tests can
   be built this week, off the live path. Running them from C4's first week would mix plumbing noise into the
   calibration.
2. **The false-alarm budget for data QA:** **at most one flag per book per week on clean fit panels**, with recall
   reported on the known positives. A tighter budget misses misprints; a looser one trains everyone to ignore it.
3. **ACT alerts: journal only (the 2026-11-02 ruling) or also a push notification?** **A push notification for ACT
   only.** A fired stop is the one case where a day's delay costs money. INFO and WATCH stay journal-only.
4. **Phase 2 (the VM timer):** **decide after phase 1 has run for two weeks**, with its false-alarm record in hand.
5. **Phase 3 (halt authority):** **not now.** Revisit after a month of ACT-free running, with the triggers
   pre-registered.
