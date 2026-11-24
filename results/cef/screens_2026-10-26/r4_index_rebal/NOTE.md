# R4: fund-of-CEF index reconstitution (YYY, PCEF, XMPT): zero-trial screen

**Reproduce:** `sh reproduce.sh` (part 1), then `python3 -B results/cef/screens_2026-10-26/r4_index_rebal/crsp_events.py` and `python3 -B results/cef/screens_2026-10-26/r4_index_rebal/event_study.py` (part 2, on the team lead's R2 pull). See `../README.md` for the paths.


2026-10-26. Asked for by the team lead. Report only: **no trial is spent and no counter moves.**
Graveyard neighbours: A9 (BIZD review demand, KILLED: median 0.39 days of ADV, and
`shift(2)` misses the window). B2 in `results/cef/EVENT_DRIVEN_POD_2026-10-12.md`
(~line 371) says "count events first".

## 1. Question

Do reconstitutions of the indices behind the fund-of-CEF ETFs YYY (ISE High Income
Index), PCEF (S-Network Composite Closed-End Fund Index) and XMPT (its muni CEF index)
force buying and selling in the CEFs they add, drop or reweight? Are those flows large
against the CEF's ADV? Do they leave a price-pressure-and-reversal pattern that a
`shift(2)` book could trade?

## 2. Declared design (written BEFORE any return was computed)

Nothing in this section was changed after a return was looked at. If a later section
departs from it, that section says so.

### 2.1 Events

- **Event** = one constituent change in one of the three indices on one reconstitution
  date: an **add** (Δw = +w_new), a **drop** (Δw = −w_old), or a **reweight**
  (Δw = w_new − w_old).
- **Known date** = the public announcement date of the change, not the effective date.
  Where a methodology fixes the lag (YYY: 6 trading days before effective [doc]), the
  announcement is that date. Where no public announcement before the effective date can
  be shown, the event counts as known only on its effective date, and so it has **no
  tradeable pre-effective window** under `shift(2)`.
- **Alignment.** A signal known at close A (the announcement) fills in the close-A+1
  auction and earns from close A+1. Window 1 therefore runs from close A+1 to the last
  close at which the index fund trades (the effective close E). It exists only if
  E ≥ A+2 sessions. Asserted in code.

### 2.2 Size

- **Demand** D = AUM_ETF(last known before A) × |Δw| ÷ ADV_63(name), with ADV_63 = the
  mean of close × volume over the 63 sessions ending at close A−1, from
  `data/cef/cef_prices.parquet` or `data/cef_families/cef_prices.parquet`. No AUM or
  weight is invented: an event whose AUM or Δw cannot be sourced is counted as
  **UNSIZED** and is not counted as ≥ 1 ADV.
- **Bar.** An event qualifies if D ≥ **1.0** day of ADV (the A9 bar).
- **Step-2 gate.** Step 2 runs only if **≥ 30** dated, sized, qualifying events fall
  on allowed names with A ≤ 2022-12-30 and with a Window 1 of at least one session.

### 2.3 Names

- **Allowed for returns:** the deployed 13 (`scripts/cef/spec.py` UNIVERSE); the wide
  17 (UNIVERSE + NAD, NEA, NVG, NZF, per `scripts/cef/w4_artifacts.py`); C4's families
  universe (`data/cef_families/universe.csv`, `included == True`).
- **Sealed:** the other 27 names of `data/cef/cef_universe.csv`. Events touching them
  are **counted** and excluded. No return is computed on them.
- **Everything else** (a CEF in none of these lists): counted as "outside our panels";
  no return is computed, because we hold no price panel for it.

### 2.4 Returns (step 2 only, if the gate passes)

- **Fit window only.** Every price used has date ≤ 2022-12-30, asserted in code. Events
  dated 2023+ are counted (dates and names only), never priced.
- **Windows.** W1 = close A+1 → close E (pressure). W2 = close E → close E+10 sessions
  (reversal).
- **Abnormal return** = the name's total return minus the equal-weight mean total return
  of same-family allowed CEFs that had no change in that index on that date, over the
  same window. Family = `grp` in `cef_universe.csv` (restricted to allowed names), or
  `family` in the C4 universe.
- **Signed** by the direction of the flow: AR × sign(Δw). The prediction is a positive
  signed AR in W1 and a negative one in W2.
- **Discount change** over each window: Δ(P/NAV − 1) on the same days, abnormal against
  the same control set.
- **Inference.** Mean signed AR, t clustered by reconstitution date. Gross only: no cost
  grid, as the team lead asked.

### 2.5 Negative control (declared first)

1. **Non-changers.** The same W1 and W2 on same-family CEFs that did NOT change on those
   dates, each against the mean of the others, with the event's sign. It should be zero;
   if it is as large as the treatment, the treatment is a family or date effect, not flow.
2. **Placebo dates.** The same event names and windows shifted 21 sessions earlier
   (about one month). It should be zero.

### 2.6 Verdict rule

- **INFEASIBLE** if the events cannot be dated and sized from public, credential-free
  sources for enough of 2010–2022 to apply the gate.
- **NOTHING (D7)** if they can be, but fewer than 30 qualify.
- If the gate passes: **PROMISING** only if the signed W1 or W2 AR has |t| ≥ 2 with the
  predicted sign and both controls have |t| < 1; **ARTIFACT** if a control is as large
  as the treatment; else **NOTHING**.

## 3. Sources tried

Everything below §2 was written after §2. No return was computed: the step-2 gate failed
(§5), so the only market data read is daily dollar volume (close × volume) on allowed
names, through 2022-12-30 (asserted in `size_events.py`). Panels read:
`data/cef/cef_prices.parquet` (last date 2026-10-15; read to 2022-12-30) and
`data/cef_families/cef_prices.parquet` (last date 2026-10-09; read to 2022-12-30).

| source | result | label |
|---|---|---|
| `data/holdings/nport_holdings.parquet` | holds **HYG, JNK and LQD only**. YYY, PCEF and XMPT are not in it. No local file holds any of the three | [V] |
| Nasdaq `Methodology_YLDA.pdf` (fetched 2026-10-26) | effective at the **open of the first session after the 3rd Friday of Jan/Jul**; announced **after the close on the 6th trading day before**; current caps 3.5% (top 30) / 2% / **10 days of ADV ÷ 110% of YYY's net assets**. Before 2024-07-22: 45 funds, linear rank weight, cap 3% and ADTV ÷ $10m | [V] text; **[U] for 2013–21**: the archived YYY holdings show 30 funds at up to ~4.8% each, so the early rules differed |
| Nasdaq GIW `/Index/Weighting/YLDA` | the anonymous view gives **today's names only** (60, no weights). The date picker is disabled for non-subscribers, so I did not ask for history | [V] |
| S-Network CEF Index Family methodology (VettaFi, March 2024) | CEFX: all eligible taxable fixed-income and option-income CEFs, **adjusted-net-asset weighting**, 8% cap, quarterly, effective at the **close of the quarter's last business day**. CEFMX (XMPT): rebalanced quarterly, reconstituted semiannually (Mar/Sep) | [V] text; [U] for 2010–21 |
| PCEF / XMPT announcement date | not found. A web-search summary of a 2020 UBS 424B3 on EDGAR says a press release follows "by the Monday after" the 3rd Friday. I could not fetch it (EDGAR). VettaFi said in 2023 that it would stop announcing changes with quarterly rebalances | **[U]** |
| Wayback: PowerShares PCEF holdings page | **19 snapshots, 2010-02-26 → 2013-12-19**, full holdings (70–146 names). Weights sum to 99.4–100.1% | [V] |
| Wayback: PowerShares PCEF overview page | 41 AUM points (shares × price), **$122.7m (2010-08-24) → $488.6m (2014-01-02)** | [V] |
| Wayback: Invesco-era PCEF pages, 2019–22 | 6 captures. The pages are filled by script, so no holdings | [V] |
| Wayback: YieldShares YYY holdings page | **10 dated snapshots, 2013-12-06 → 2017-04-07**, 30–31 names with market values; AUM **$14.8m → $152.0m**. Captures from 2017-04 on carry no table | [V] |
| Wayback: Amplify family holdings CSV | YYY on **2020-03-16/17** and **2021-02-17/18**; AUM $183–204m and **$296m** | [V] |
| Wayback: Amplify `yyy-holdings`, 2022–23 | 7 captures, all filled by script ("Holdings as of TBD"), so no holdings | [V] |
| Wayback: VanEck XMPT holdings | **6 snapshots, 2019-11-12 → 2021-09-20**, 58–64 names; AUM $151–212m | [V] |
| Wayback: Market Vectors XMPT page, 2011–16 | 89 captures. **Top-10 holdings only**, so adds and drops cannot be read; AUM $22.7m (2014-01-07) → $98.7m (2016-05) | [V] |
| EDGAR (N-Q, N-CSR, N-PORT-P) and R2 `crsp_q_mutualfunds.holdings` | **not used**: both are forbidden in this screen (contact header; credentials) | — |

Every fetch is logged with its URL and UTC time in `raw/fetch_log.csv` (264 lines incl. header and the early curl rows).

**Two artifacts found and removed before counting.** Left in, they would have added
**7 false ≥ 1-ADV events**:

- **NAV-symbol tickers.** From 2012-05-18 to 2013-05-10, the PCEF page lists
  ETY, EXG, QQQX, BKT, JGV, JLA and MGF under their NAV symbols (XETYX, XEXGX, XQQQX, …),
  and YYY 2021-02 lists XDLYX. Read as tickers, this fakes a drop and a re-add of each
  fund. EXG, ETY and QQQX would each have produced a "drop" and an "add" at ≥ 1 ADV.
  They are mapped back; XQQQX goes to QQQX, not QQQ.
- **A merger.** Between 2013-08-05 and 2013-12-19, COY, CYE and HYV leave PCEF while
  HYT's weight goes from 0.46% to 1.80%. That is the BlackRock high-yield merger (the
  four weights summed to 1.47%), not an index trade, and it would have counted as a
  3.06-day "reweight". Excluded.

**Calendar check [V].** All 11 snapshot pairs that bracket no scheduled rebalance show
**0 constituent changes**. That covers PCEF, YYY and XMPT, gaps of 1 day to 6 weeks.
Changes appear only in pairs that bracket a scheduled date. This supports the
quarter-end calendar for PCEF and the Jan/Jul calendar for YYY.

## 4. Event counts and sizes

**Coverage.** Snapshot pairs that bracket exactly one scheduled rebalance give dated events:
- PCEF: **11 of 52** quarter-ends, 2010-09 → 2013-09.
- YYY: **3 of ~18** reconstitutions, 2014-01, 2015-07 and 2016-01, when its AUM was $15–95m.
- XMPT: **1 of ~46**, 2020-12.

Together that is **15 of ~116** scheduled rebalances (~13%) [V counts; the ~18 and ~46
assume the inception dates 2013-06 and 2011-07, [S]].

**Window.**
- YYY: **4 sessions** from the `shift(2)` fill (close A+1) to the last close before the
  effective date [V on the current text].
- PCEF and XMPT: 3–8 sessions, on the [U] announcement proxy.

So, unlike A9, a pre-effective window would exist if the announcement is public.

**Snapshot bound: the ETF's full position in each allowed name, in days of ADV63 [V].**
This bounds a full add or drop at that AUM.

| ETF | dates | AUM | median | max | names ≥ 1 ADV |
|---|---|---|---:|---:|---|
| PCEF | 2010-09 → 2011-02 | $131–192m | 0.73–0.87 | 2.1 | 6–9 of 26–33 |
| PCEF | 2012-10 → 2013-12 | $360–490m | **1.8–2.1** | 3.8 | 33–40 of 36–45 |
| YYY | 2013-12 → 2014-03 | $15–32m | 0.2–0.3 | 0.5 | 0 |
| YYY | 2015-08 → 2017-04 | $79–152m | 0.7–1.7 | 3.0 | 5–10 of 12–17 |
| YYY | 2021-02 | $296m | **1.65** | 3.9 | 11 of 14 |
| XMPT | 2019-11 → 2021-09 | $151–212m | **2.0–4.1** | 5.4 | 6 of 6 |

The XMPT row covers MHD, MQY, NAD, NEA, NVG and NZF, which sit at the 8% cap.

So the flow can be large against ADV (A9's median was 0.39). But XMPT's large positions
are in names that never leave the index, and **reweights are small**. Over the dated
events on allowed names, excluding the merger, the median reweight is:
- PCEF 0.10 days (n 376, max 0.74);
- YYY 0.04 (n 44);
- XMPT 0.01 (n 6).

**0 of 426** reweights reach 1 ADV [V]. Only additions and deletions can.

**Dated events on allowed names** (`out/events_dated.csv`):
- PCEF: 19 adds (median 0.78 days) and 1 drop (0.64).
- YYY: 8 adds (0.42) and 5 drops (0.23).
- XMPT: no adds or drops.

**GATE: dated, sized, ≥ 1 ADV, allowed names, fit window = 7 [V]. The gate needs 30.**

| E | ETF | kind | name | class | weight | demand, days of ADV |
|---|---|---|---|---|---:|---:|
| 2010-12-31 | PCEF | add | JFR | deployed 13 | 1.45% | 1.90 |
| 2010-12-31 | PCEF | add | HPF | C4 | 0.76% | 1.11 |
| 2012-12-31 | PCEF | add | DNP | C4 | 2.16% | 1.30 |
| 2013-03-28 | PCEF | add | LDP | C4 | 0.79% | 1.37 |
| 2013-03-28 | PCEF | add | HEQ | C4 | 0.40% | 1.87 |
| 2013-06-28 | PCEF | add | BIT | deployed 13 | 0.66% | 1.25 |
| 2013-09-30 | PCEF | add | FPF | C4 | 1.15% | 1.09 |

By year: 2010: 2, 2012: 1, 2013: 4.

**Independent re-derivation.** JFR's ADV63 was recomputed from the raw panel: $1.355m over
2010-09-21 → 2010-12-17, 63 sessions. The demand is 1.90 days, or 2.06 on the median dollar volume. YYY's
AUM implied by % of net assets matches the sum of market values to within 1% on all 14
snapshots [V].

Several adds are recent IPOs reaching the 3-month seasoning rule (BIT 2013-02, FPF
2013-05, LDP 2012) [S on the IPO dates; panel start dates agree for BIT].

**Undatable** adds and drops come from pairs that span ≥ 2 rebalances, sized at the near
snapshot (`out/events_undatable.csv`):
- YYY, allowed names: **57 changes, 32 at ≥ 1 ADV** (C4 adds median 1.41 days).
  - 2016-04 → 2017-02 (2 reconstitutions): 13 of 15.
  - 2017-04 → 2020-03 (6): 8 of 10.
  - 2020-03 → 2021-02 (2): 8 of 12.
- PCEF: 2 of 7.

These cannot be dated to a single rebalance, so they cannot be event-studied. They are
the history a full holdings file would add.

**Sealed holdout (27 names): counted, never sized or priced.**
- Dated: PCEF 10 adds, 1 drop and 123 reweights; YYY 1 drop and 10 reweights; XMPT 5 reweights.
- Undatable: PCEF 2 adds and 1 drop; YYY 11 adds and 4 drops.
- Today's YLDA list (2026-10-26, names only) holds 8 sealed names (BGT, DHY, EDD, EMD,
  GHY, HIO, PFL, VVR), 6 of the deployed 13 (BIT, DSL, HYT, JFR, PFN, PHK), 24 C4 names
  and 22 others [V].

**2023+ events:** none could be counted. No 2023+ capture carries holdings.

**Projection, labelled [U] and not used for the verdict.**
- At PCEF's observed rate (7 in 11 quarters), 52 quarters would give ~33, if AUM and
  universe were stable, which they were not.
- YYY's undatable pairs suggest ~4–6 allowed ≥ 1-ADV changes per reconstitution from
  2016 on, so ~50–80 over 2016–2022.
- A full holdings history could therefore plausibly clear the gate, mostly through YYY
  and PCEF additions.

## 5. Results

Step 2 did not run. The declared gate needs ≥ 30 dated, sized, ≥ 1-ADV events on
allowed names in the fit window; the credential-free record gives **7**. **No return,
abnormal return or discount change was computed, so the negative control (same-family
non-changers, and placebo dates 21 sessions earlier) was declared but not run.**

The only control that ran is the calendar check in §3: 0 changes in 11 pairs that
bracket no rebalance.

## 6. Verdict: **INFEASIBLE**

Per §2.6: the public, credential-free record dates **15 of ~116** scheduled rebalances.
That is not enough of 2010–2022 to apply the gate, and it yields 7 qualifying events
against 30. This is not a null on the mechanism.

The sizes clear the A9 bar where it matters: additions and deletions. PCEF's full
positions reached a median of ~2 days of ADV by 2013, and YYY's ~1.7 days by 2021.
YYY also has a 4-session pre-effective window under its published calendar.

**What would make it testable** (any one; the first is cheapest):
1. **R2 `crsp_q_mutualfunds.holdings` + `portnomap` + `monthly_tna`** for the portnos of
   YYY, PCEF and XMPT. This needs the team lead's R2 credentials. The repo has already
   read it for PFF and BIZD, monthly from 2010-06 (`results/events/ssx/ssx_data/DATA_MAP_2026-10-19.md`).
   Monthly holdings bracket every quarter-end and every Jan/Jul reconstitution.
2. **EDGAR** N-Q (to 2019) and N-PORT-P exhibits (2019+), with the team lead's SEC
   user-agent. YYY's schedules are dated Jan 31 and Jul 31 [S: search result titles],
   which bracket each reconstitution.
3. **A Nasdaq GIW subscription** for YLDA's daily historical weights.

Plus, for PCEF and XMPT, the S-Network/VettaFi announcement history. Without it, those
events are known only at the effective date, and only the post-effective (W2) window is
testable.

## 7. Reproduce

```sh
sh /private/tmp/claude-501/-Users-simonjarvis-Downloads-2027-Projects-Quant---PM2027-2027/767b4ac8-7cb7-4bf6-953a-b785b037a5b4/scratchpad/r4_index_rebal/reproduce.sh
```

- Network: web.archive.org only. The fetches skip files already on disk.
- Then it runs `parse_snapshots.py`, `parse_aum.py` and, from `tree/`, `size_events.py`.
- Output goes to `out/size_events_final.txt`, identical to the run quoted here.
- Outputs: `out/holdings_snapshots.csv`, `out/aum_points.csv`,
  `out/snapshot_position_days.csv`, `out/events_dated.csv`, `out/events_undatable.csv`,
  `out/events_qualifying.csv` and `out/rebalance_calendar.csv`.

---

# Part 2 (2026-10-27): the gate re-run on CRSP mutual-fund holdings

The team lead pulled R2 `crsp_q_mutualfunds.holdings`, `portnomap` and `monthly_tna` for
YYY, PCEF and XMPT. It is staged, gitignored, under the worktree's
`results/events/_cache_r7_r2_pull/cefetf/` (manifest pulled 2026-10-27T20:01Z; window
2010-01-01..2022-12-31; holdings report_dt 2010-06-30..2022-11-30; rows with an eff_dt
after 2022-12-31 were excluded by the pull). Same brief and rules: zero trials, gross
only, allowed names only, returns ≤ 2022-12-30 asserted. No licensed value or
identifier is copied into any tracked file. This note and `out/` are untracked scratch.

## P2.1 Declared before any return was computed (addendum to §2)

§2 stands unchanged. Part 1 did not need the operational details below; this data does.
They were written before a single return was computed.

1. **Snapshots.** One per (ETF, report_dt). A snapshot is **valid** if its
   percent_tna sums to between 95 and 105. Seen before writing this: PCEF's CRSP
   snapshots from 2010-07 to 2012-12 sum to 83–92%. Against the issuer pages, CRSP
   omits 22–27 names that PCEF held (2011-07: 90 names against 117). So those PCEF
   snapshots are invalid, and PCEF events there come only from the issuer-page record
   of Part 1.
2. **Identity.** A holding is keyed by CRSP permno. A row with no permno takes the
   permno that the same ticker carries elsewhere in the pull, if that is unique;
   otherwise it is keyed by ticker. Classes:
   - the 13 come from the `stocknames` table in `results/data/cef_crosscheck_crsp_2026-09-28.md`;
   - C4 names from `data/cef_families/crsp_permno_map.csv` (current and other permnos);
   - NAD, NEA, NVG, NZF and the 27 sealed names from the permno their current ticker
     carries in the pull.

   A permno claimed by two classes raises. Any NAV symbol X<T>X is mapped as in Part 1;
   the pull contains none [V].
3. **Dating.** For each scheduled rebalance E, with neighbours Ep and En:
   - **pre** is the latest valid snapshot in (Ep+3d, E−3d);
   - **post** is the earliest in (E+3d, En−3d).
   - If either is missing, the rebalance is undatable.

   A month-end report on the quarter-end itself is never an endpoint. So no change is
   dated more precisely than the scheduled rebalance it brackets.
4. **Changes.**
   - An **add** is in post and absent from every valid snapshot in (Ep+3d, E−3d).
   - A **drop** is in pre and absent from every valid snapshot in (E+3d, En−3d).
   - A name that vanishes and comes back inside one inter-rebalance period is
     **flicker**: counted, never an event.
   - A **reweight** is in both, with Δw = w_post − w_pre. That includes drift, so it is
     an upper bound on the flow.
5. **Merger suspects.** An add or reweight on an allowed name is suspect when the same
   bracket drops a dead name (outside our panels) whose first name-token (the sponsor)
   matches, and whose pre-period market value is ≥ 50% of the add's post-period market
   value, or of the reweight's change in market value. The gate counts **non-suspect
   events only**. Suspects are reported.
6. **Size.** Demand = TNA (monthly_tna, the latest month-end before A) × |Δw| ÷ ADV63,
   with ADV63 strictly before A. The bar is 1.0 day; the gate is ≥ 30 events with
   A ≤ 2022-12-30 and W1 ≥ 1 session. If the gate passes on CRSP alone, Part 1's
   issuer-page events are used only as a cross-check, never pooled.
7. **Event study (only if the gate passes)**, on the qualifying events:
   - **Returns.** Total returns use the house formula (`band_frontier.total_returns`:
     the price return plus D/P(t−1), split-corrected, split-basis guard on). For C4
     names the families panel adds the team lead's split rulings
     (`results/cef/c4/c4_split_rulings_2026-10-20.json`, `drop_split`) and the bar
     rulings file. Price, NAV and action files are truncated to ≤ 2022-12-30 in my
     folder before anything is computed, so no 2023+ value is ever loaded into the
     return code.
   - **Windows.** W1 = close A+1 → close E; W2 = close E → close E+10.
   - **Abnormal return.** The name minus the equal-weight mean of its family's allowed
     names that had no add, drop or ≥ 1-ADV event in that index at that E, and that
     have returns over the whole window. An event whose control set is empty is dropped
     and counted, never filled. Family = `grp` for the 17 and `family` for C4.
   - **Sign.** +1 for an add, −1 for a drop, sign(Δw) for a reweight.
   - **Prediction.** Signed W1 > 0 and signed W2 < 0.
   - **Inference.** t clustered by (ETF, E).
   - **Discount change.** Δ(P/NAV − 1), handled the same way.
   - **Controls**, as declared in §2.5: (a) each non-changer against the mean of the
     other non-changers, with the event's sign, averaged within the event; (b) the
     event names on placebo windows shifted 21 sessions earlier, against the same
     control set.
   - **Verdict rule** as in §2.6.
   - Results are also shown by ETF. PCEF's and XMPT's announcement dates remain [U];
     YYY's is [V] on the current methodology text.

### P2.1a Amendments made after seeing the event LIST, before any return was computed

The first pass listed 161 qualifying events. Reading that list (names, weights, sizes;
no prices or returns) showed three defects in my own rules. They are fixed here, before
any return is computed.

5b. **Mergers.** Item 5's test compared each dead drop alone against 50%. It missed the
    BlackRock high-yield merger: HYT took COY, CYE and HYV, each under 50% of the
    change. It also missed the Nuveen 2016 merger into NZF, where XMPT's NZF weight is
    15.3% against an 8% cap. Two changes:
    - the test now sums the same-sponsor dead drops in the bracket;
    - a post weight above 1.25 × the largest weight in the pre snapshot is also suspect,
      because the index caps cannot produce it.

6b. **Lookahead in sizing and signing.** The pre snapshot is about a month before E and
    the post snapshot about a month after, so Δw contains price drift through W1 and W2.
    Signing a reweight by sign(Δw) would credit a name that rose inside W1 or W2 with a
    "buy" sign, which is a mechanical positive AR. Sizing an add by its post weight
    selects names that rose after E. **So the event-study population is sized and signed
    on SHARES, valued at close A** (price known at A):
    - add: post shares × close A;
    - drop: pre shares × close A;
    - reweight: (post shares − g × pre shares) × close A, where g is the median ratio of
      post to pre shares over the bracket's continuing names. That ratio removes the
      ETF's own creations and redemptions. The sign is the sign of this trade.

    A reweight with a recorded split between pre and post is excluded, because its share
    counts are not comparable. The coordinator's TNA × |Δw| count is still reported as
    the requested gate (an upper bound). The event study runs only if the
    lookahead-free count is also ≥ 30.

7b. **Reading §2.6** (written before the event-study run). A control counts as
    "as large as the treatment" when its |mean| ≥ the treatment's |mean| **and** its
    |t| ≥ 1. Without the t condition, a near-zero treatment against near-zero noise
    would be called ARTIFACT. A window counts toward PROMISING only with the predicted
    sign: W1 > 0, W2 < 0.

## P2.2 Counts (CRSP holdings; `crsp_events.py`)

**Snapshots.** The holdings are monthly in most years, and sparse for PCEF in 2014–17
and YYY in 2013–17. Of PCEF's 2010–12 snapshots, 1 of 29 is valid. Every XMPT and YYY
snapshot is valid.

**Rebalances datable from inception** (a valid snapshot on each side, more than 3 days
from E) [V]:
- PCEF: 28 of 51;
- XMPT: 45 of 46;
- YYY: 18 of 21.

So 91 of 118, against 15 in Part 1.

**Identity and data checks** [V]:
- 23 vanish-and-return flickers were refused as events.
- The pull contains no NAV-symbol tickers. 43 rows took a permno from their own ticker;
  451 rows have none (cash, money-market and foreign lines).
- **Cross-source check.** The 2013 PCEF events match Part 1's issuer-page record name for
  name: HEQ and LDP (2013-03), BIT (2013-06), FPF (2013-09) and the HYT merger. Demands
  agree within 0.1 day; for example HEQ 1.75 against 1.87.
- **Mergers** excluded from the gate: 11 suspects at ≥ 1 ADV. Among them are HYT
  (2013-09), PDI absorbing PCI (2021-12), NZF (2016-03, 15.3% against an 8% cap),
  NAD and NEA (2016-09), and MHD and MQY (2021-03).

**GATE** (dated, sized, ≥ 1 ADV, allowed, non-suspect, A ≤ 2022-12-30, W1 ≥ 1 session):

| version | count | PCEF | XMPT | YYY | verdict |
|---|---:|---:|---:|---:|---|
| as requested: TNA × \|Δw\| ÷ ADV | **158** | 65 | 3 | 90 | PASS [V] |
| lookahead-free: shares × close A (P2.1a 6b) | **137** | 45 | 3 | 89 | PASS [V] |

- The lookahead-free 137 split into 57 adds, 50 drops and 30 reweights.
- By class: 28 on the deployed 13, 4 on the wide 17 and 105 on C4 names.
- They span 31 (ETF, E) clusters, 2013-03 → 2022-09.
- Median demand: PCEF 1.51 days of ADV, YYY 1.82, XMPT 1.26.
- Sealed names were counted and never priced; their events are in `out/p2_events.csv`.

## P2.3 Event study (`event_study.py`; returns ≤ 2022-12-30 asserted)

**Exclusions** [V]:
- HERZ is excluded from all returns: a split and a distribution fall on the same date,
  so the per-share basis is ambiguous and the house formula refuses to guess.
- The house split guard found 8 more vendor-adjusted split cells in the families panel:
  ASA, ZTR, AGD, AOD, CLM, CRF and SRV twice. They are treated `drop_split`, the team
  lead's 2026-10-20 treatment for the same defect, in this screen's own file
  `out/r4_split_rulings.json`. **This is not a team-lead ruling.**
- numexpr was switched off: its thread pool hung on one small division. It is an
  accelerator only.
- 7 events have no same-family control (JFR, the only allowed loan fund; and AWF and
  HYT when both changed at one E), so n = 130.

**Pooled, signed abnormal total return, gross [V]:**

| | W1: close A+1 → E | W2: E → E+10 |
|---|---:|---:|
| treatment | **+50bp, t 2.23** | **−73bp, t −3.58** |
| control (a): non-changers | 0.0bp | 0.0bp |
| control (b): placebo, 21 sessions earlier | +20bp, t 1.19 | **+113bp, t 2.87** |
| signed discount change, treatment | +61bp, t 2.51 | −48bp, t −3.02 |
| signed discount change, placebo | +4bp | +118bp, t 2.98 |

n = 130 in 30 clusters.

**Control (a) is degenerate, and that is my design error.** The mean of every name
against the mean of the others is identically zero. It carries no information. The
verdict rests on control (b).

**Verdict by the declared rule (§2.6, 7b): ARTIFACT.** The placebo W2 (+113bp, t 2.87)
is larger than the treatment W2 (−73bp) and has |t| ≥ 1.

**Where the artifact is (supplementary; the split by ETF was declared in P2.1 item 7, but
nothing below changes the verdict):**

- **YYY** (84 events, 9 clusters): **no pressure**. W1 is −17bp (t −1.4) and W2 −51bp
  (t −1.9). Its **placebo W2 is +170bp (t 2.7)**, with a discount change of +180bp
  (t 2.9). That placebo window sits just after YYY's reference date, where the index
  ranks on yield and discount. Names chosen for wide discounts then re-rate. That is
  the desk's own discount-reversion signal, not index flow [U on the mechanism; V on
  the numbers].
- **PCEF** (43 events, 19 quarter-ends):
  - W1 **+184bp, t 5.46**, positive in 84% of events; W2 **−120bp, t −5.61**.
  - Placebo W1 **+8bp (t 0.23)**, placebo W2 **+7bp (t 0.31)**.
  - Signed discount change: W1 +203bp (t 5.9), W2 −99bp (t −4.0); placebo +4 and +8bp.
  - The same signs hold for adds (W1 +242 / W2 −204), drops (+215 / −101) and
    reweights (+107 / −56).
  - They also hold in both eras: 2013–17 (n 6) +268 / −163; 2018–22 (n 37) +171 / −113.
  - And on the deployed 13 alone (n 12): +260bp (t 2.7) / −154bp (t −2.4).
  - **Post-hoc:** if the change is known only at E, the reversal from an E+1 fill is
    −74bp (t −3.6), and from an E+2 fill −44bp (t −1.5).
- **XMPT:** 3 events, which is too few to read.

## P2.4 Verdict

**ARTIFACT** by the declared pooled rule. The flows clear the size gate easily: 137
lookahead-free events at ≥ 1 ADV. But the pooled pattern fails its placebo, because
YYY's selection-on-discount re-rating sits in the placebo window, and YYY shows no
pressure of its own.

**Post-hoc, not a pass:** PCEF alone shows a clean pressure-and-reversal with a
near-zero placebo. It is a hypothesis for a **PCEF-only pre-registered trial**, never
evidence. That trial would need:
1. PCEF/S-Network announcement dates verified, or a replication of CEFX eligibility and
   weights from public data at the reference date. Without one of these, only the
   E+1/E+2 reversal is tradeable.
2. The 2023+ time holdout, opened once, as the out-of-sample test.
3. A control that is not degenerate, for example a matched non-changer pseudo-event.
4. A borrow check for the drop and reversal legs.
5. A trial counter named by the team lead (EVENTS, or NPORT as B2 was filed).

## P2.5 Reproduce

```sh
cd /private/tmp/claude-501/-Users-simonjarvis-Downloads-2027-Projects-Quant---PM2027-2027/767b4ac8-7cb7-4bf6-953a-b785b037a5b4/scratchpad/tree
python3 ../r4_index_rebal/crsp_events.py   > ../r4_index_rebal/out/p2_run2.txt     # counts and the gate
python3 ../r4_index_rebal/event_study.py   > ../r4_index_rebal/out/p2_event_study.txt
```

These read the staged CRSP cache in the simon worktree, under
`results/events/_cache_r7_r2_pull/cefetf/` (gitignored, licensed). The `out/p2_*.csv`
files carry CRSP-derived values. **They are scratch, and must not be copied into any
tracked file.**
