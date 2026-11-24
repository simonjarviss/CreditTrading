# C4 on Alpaca paper: deployment plan (read-only, 2026-10-27)

> **DRAFT for the team lead.** On 2026-10-26 the team lead said "proceed with C4", after the ex-date check came back MIXED (`results/cef/screens_2026-10-26/README.md`). This plan changes nothing. Its decisions in §3 are open.

Lines at `simon` dff4b5c. Nothing changed.

## 0. Facts

- **Nothing on the order path reads `sleeves[]`.** The runner trades one spec per `Book` (run.py:190, 538-558, 736-763).
  - The only reader is `deployed_tickers` (ops/common.py:388), which feeds `fetch_daily --require-asof` (fetch_daily.py:254).
  - **An enabled C4 entry in the core book json would make the 13's refresh exit 4 every day.**
- **The universes are disjoint** (0 of 74 in the core panel [V]), so netting is attribution by symbol and no wash trade arises (gate.py:645).
- **One account couples the 13 in five places:**
  1. gate 9, any non-universe holding (gate.py:621);
  2. gate 6, any open order (gate.py:427);
  3. gate 5, any one missing NAV (gate.py:391);
  4. verify, a missing print. Only NYSE is mapped (alpaca.py:210), and **9** of the 74 are AMEX or NASDAQ;
  5. `max_gross_stress` assumes M_other = $0 (spec :42).
- CEFConnect names a NAV symbol other than `X<TK>X` for 16 of the 74 [V, `universe.csv`]; fetch_daily hard-codes `X<TK>X` (fetch_daily.py:220).
- **Sleeve against trial**:
  - the sleeve has no M1/M2 mask;
  - its panel paths are fixed (cef_discount.py:77);
  - below `min_names` it flattens (:551), where `build_targets` holds (band_frontier.py:201).

## 1. Changes

| # | where | change | type |
|---|---|---|---|
| 1 | `cef_discount.py::_panel`, `target_positions`; `registry._validate_cef_discount` | **Reuse the sleeve with a second spec.** A new module would copy the z-score (band_frontier.py:84). Keys: `panel_source`, `nav_repeat_mask`, `zero_volume_mask`, `below_min_names` | no-op when the keys are absent |
| 2 | new `ops/specs/c4_families.frozen.json` | the frozen 74; the core's values; both masks; `hold`; its own `max_gross_stress`, re-derived by the frozen rule | read by nothing yet |
| 3 | fetch_daily parametrised (`data/cef_c4`, NAV-symbol map, own lock); distributions panel; `guard_closes`; collector `BOOKS["c4"]` (collect.py:176) | nightly data | no-op for the core |
| 4 | alpaca.py:210 | sourced AMEX and NASDAQ rows | change; prove the 13 are unchanged |
| 5 | stale NAV | **M1 catches every repeat without CEFConnect.** Trigger 2 would take 13 → 87 requests per attempt. `PanelGate` already takes its paths (nav_gate.py:404) | off for C4 |
| 6A | run.py `BOOKS["c4"]` | its own keys and state; the sleeve's own paths replace `cefmod.PX_PATH`/`NAV_PATH` (run.py:552, 753) | no-op for the core |
| 6S | new `combine.py` (framework phase C) | each sleeve's `sleeve_nav` = budget × equity; shares summed per symbol; one `decide`; a combined cap with M_other; `fit_to_buying_power` (run.py:1430) attributed per sleeve; gate 5 per sleeve | **changes the 13's sizing** |
| 7 | shortability | none: decide skips an unshortable short-open (decide.py:345); the backtest mirrors it (band_frontier.py:256) | — |
| 8 | verify/score/TCA | per book; `dist_score` `panel_path` (:347) | — |
| 9 | new `scripts/cef/c4_paper_benchmark.py` | **fidelity**: the sleeve's target before `min_abs_weight` against `build_book`'s T; anything outside the declared divergences halts. Price-only and total-return lines | research |
| 10 | H11 amendment (PREREG §14) | **Paper flatters C4: fit Sharpe 1.360 price-only against 1.217 total return** (`results/cef/screens_2026-10-26/r3_c4_exdate/NOTE.md` §2.6). Read the 5th percentile price-only against the official-fill line, and total-return against the distribution-adjusted line | prereg |
| 11 | install_prod.py:92, install_vm.py:311 | `BOOK = "cef"` is fixed: add `quantt-c4-*` units, the seed and the vault secrets | installer |

## 2. Order of work (each step tested, `/release-check`, tagged)

1. **Dark:** row 1, with a sha256 no-op proof on the real panel and a held book (test_nav_gate.py:586 pattern).
2. **Dark:** row 2, plus a fidelity test against `build_book`.
   - *Divergences the fidelity test must declare* (added 2026-10-27 by step 1, `c4-step1`): **while `below_min_names = "hold"` lasts, `max_gross_stress` is effectively off.** The sleeve holds shares, so price drift can leave the book above 1.8x; the trial holds a weight-space target and caps it every day (`cef_discount.py`, the `min_names` block). Also PREREG_C4 §3 items 5 and 6 (`min_abs_weight` and whole shares; holdings, not the stored target, as the reference state).
3. **Dark:** row 3; GETs only. Measure fetch time.
   - *As built 2026-10-29 (`c4-step3-data`, zero trials):* `fetch_daily.py --data-book c4`, `fetch_cef_distributions.py --data-book c4` and the collector's `BOOKS["c4"]` write `data/cef_c4/` under its own lock. They cover the 74 frozen funds, use the NAV symbol map `results/cef/c4/c4_nav_symbols_2026-10-14.csv`, and read no CEFConnect. Books and paths are in `scripts/cef/data_books.py`. Without `--data-book`, every fetcher matches 29e5dc0 byte for byte.
   - **Fetch time: UNMEASURED.** There was no network in the build.
   - **Seed:** `data_books.py` SEED, not run. It refuses on IGR's four bars, 2026-07-29..08-11 [V: `data_guards.guard_closes` on `data/cef_families/`, read-only, 2026-10-29. These are the same four bars as `python3 scripts/cef/data_guards.py scan`, 2026-10-19].
   - **Open:** the nightly spike guard has no rulings file. If Yahoo still serves IGR's four bars, every C4 fetch exits 6 until they leave the six-month window (about 2027-02) or a ruling path for the live panel is decided.
4. Row 4.
5. Row 6A (or 6S) and row 9, at `DRY_RUN=1` for at least 5 sessions.
   - *Row 6A as built 2026-10-29 (`c4-row6a`, DARK):* the runner reads each sleeve's closes, NAV dates, pre-flight history and stale-NAV file from the panel its spec decides on (`quantt/session/run.py` PER-SLEEVE PANELS); `require_core_panel` is gone. The released book is byte-identical to 5e627ff, with `data.missing_nav` absent and set (`quantt/session/tests/test_panels_noop.py`). An absent panel, or a universe its own panel does not cover, FAILs the decide naming it. A non-core panel's refresh is refused at gate 5 until step 3's `--data-book` fills `run.refresh_flags`. Still open: `BOOKS["c4"]` and its book json, the installer units, and verify's distributions panel (row 8).
   - *Integrated 2026-10-29 (`c4-integrate`, DARK, zero trials):*
     - steps 2 and 3 and row 6A are merged onto main 35b429f;
     - `run.refresh_flags` gives C4's panel `--data-book c4`;
     - `BOOKS["c4"]` and `ops/books/c4_families_book.json` exist, with no stale-NAV
       gate, the missing-NAV hold, report drawdown (UNMEASURED: the spec names no
       levels) and the corporate-action gate in `halt`;
     - verify scores against C4's own distributions panel (row 8);
     - row 11 is built: `install_vm --book c4`, with `--eod-from` required.

     The core's session and install are proved byte-identical to cee16ad
     (release-20261029-3). Still open, for the team lead:
     - the vault secrets;
     - the seed;
     - the release and install;
     - the halve/kill levels;
     - the cap re-derived before arming.

     The steps are `results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md`.
6. Arm, on the team lead's go.

## 3. Decisions for the team lead

1. **Same account?** Recommended: **a second paper account**, as an exception to the 2026-10-09 ruling.
   - C4 never gets capital.
   - Sharing the account forces 6S, which changes the 13.
2. **Split.** Recommended: $100k of its own, the spec's 6%, and C4's own cap.
   - If one account: C4 at the evidence floor (framework §2.12) and the 13's cap re-derived.
3. **CEFConnect.** Recommended: none for C4 until Nuveen answers.
4. **Funds Alpaca will not short.** Recommended: keep the 74 frozen, skip the short-open, substitute nothing.
5. **The stop rule.**
   - Halt on a fidelity break.
   - Reverse below the price-only 5th percentile at 120 sessions, or on a drawdown past the fit's worst.
   - Report only: the ex-date split and a post-ex drift control (`results/cef/screens_2026-10-26/r6_exdrift/`).
6. **The 9 non-NYSE funds:** source their prints, or score them as gaps.

## 4. Risks to the 13

| risk | guard |
|---|---|
| refresh or gate-5 refusal from the 74 | never enable C4 in the core json; its own data dir |
| gates 6 and 9 | 6A |
| verify FAILs on a missing print | 6A, or row 4 first |
| margin | 6A, or M_other |

**Every step proves the 13's plan.json and `plan_sha` byte-identical until C4 is switched on.**

## 5. Unmeasured

- **The 74's shortability today**: one read-only `GET /v2/assets` on the team lead's keys. The history since 2026-10-09 is in the VM's `assets.parquet` (needs ssh).
- NAV arrival and fetch time against the 25-minute cap (run.py:157).
- A second paper account [U].
- The SIP codes for AMEX and NASDAQ.
- Memory on the 1 GiB VM.
