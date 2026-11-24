# E1 DG-E1-3 rulings form: the failed-deal readings, triaged

**Date** 2026-10-20 · **Trial** EVENTS trial 1, E1 (`results/events/PREREG_E1_MERGER_PAIR_2026-10-19.md`)
· **Reproducers** `python3 scripts/events/e1_failed_reading.py collect --root <pack> --model sonnet`
(the readings) and `python3 scripts/events/e1_failed_reading.py triage` (the classes) · **Files**
`results/events/e1/e1_failed_deal_readings.csv`, `e1_failed_reading_review.csv`,
`e1_failed_reading_triage.csv`, `readings_raw/sonnet/`

> **RULED 2026-10-20.** The team lead answered "Accept all" to items 1–7 and chose both extra
> reading rounds, items 8 and 9 (relayed by the coordinator).
> - Recorded in `results/events/e1/e1_dg3_rulings.csv`: `ruled_by` "team lead (Simon Jarvis):
>   accept all recommended", `ruled_on` 2026-10-20.
> - Also recorded as amendment 3 of the pre-registration.
> - The packs for items 6, 8 and 9 are built by `scripts/events/e1_failed_reading.py`
>   (`prepare-n8f`, `prepare-r2`, `prepare-supp`).
>
> *Was:* **A form, not a ruling.** Every item waits on the team lead.
>
> - **No E1 statistic was computed.** The triage reads only the readers' fields, CRSP names
>   and CRSP delisting records.
> - **The readings.** 48 Sonnet batches (`claude-sonnet-5-5`) read all 273 census episodes into
>   496 deal rows.
> - **As collected, there are 6 in-trial rows and 3 in-trial deals:** RAA→BFZ (read from 4
>   episodes; it counts once), AFT→AIF and BHV→MYI. `failed_deal_rows` takes one deal per
>   `deal_id`, with A the earliest announcement and F the earliest public failure (tested).

## 1. What DG-E1-3 requires

**Every one of the 273 episodes, not only the in-trial deals.**

- §13: DG-E1-3 is "done when every episode read, every quote re-found".
- §4.3: "Each is read. … An episode that cannot be read halts Stage 0."
- §4.3 also says the reading records the outcome.

So a row with a blank outcome, a quote that is not re-found, or two readings of one deal that
disagree, each keep DG-E1-3 failing. On 2026-10-20 that is:

- 183 blank-outcome rows;
- 4 quote failures in 3 episodes;
- 8 deals whose readings disagree.

A class ruling for the rows that cannot change the trial is item 5 below.

## 2. The triage (every row, `e1_failed_reading_triage.csv`)

| class | meaning | rows | deals | episodes |
|---|---|---:|---:|---:|
| T1 | a failure, both parties listed (by the reader, or by CRSP under §4.3's own share-code definition), made public by 2024-12-31: **in the trial** | 9 | 5 | 9 |
| T2 | a failure of a listed pair made public after 2024-12-31: in no set | 1 | 1 | 1 |
| I1 | a failure whose listing neither the reader nor CRSP settles | 19 | 17 | 12 |
| I2 | outcome unstated, both listed, no CRSP completion within 730 days | 37 | 28 | 20 |
| I3 | outcome unstated, listing unsettled, the episode's own fund a listed CEF or BDC-named | 27 | 24 | 25 |
| C1 | CRSP shows the target merged within 730 days of A (the census rule: not a failed deal) | 10 | 10 | 7 |
| C2 | not a listed pair, or completed | 284 | 177 | 150 |
| C3 | outcome unstated, listing unsettled, the episode's own fund not a listed CEF | 109 | 83 | 78 |

Only T and I rows can change the trial.

## 3. Recommended rulings (accept all, or each)

1. **One deal, one count.**
   - **Recommended:** a deal read from several episodes counts once (its `deal_id`: target CIK >
     acquirer CIK). A is its earliest announcement and F its earliest public failure.
   - **Reason:** §4.1 says "A deal is one target into one acquirer". The census reads each party's
     filings, so one deal can arrive more than once.
   - **Alternative:** none that keeps §4.1.
2. **CRSP settles a listing the reader left null.**
   - **Recommended:** if both parties' printed tickers map, on A, to a CRSP CEF (share code
     14/44) or BDC (11) on NYSE, NYSE American or Nasdaq, the pair is listed.
   - **This adds NXJ→NAD, NQP→NVG and NMT→NEA.** Each is a 2023 Nuveen N-14 withdrawn by RW ("a
     proposed merger transaction that is no longer contemplated"), so all three fall in the time
     holdout.
   - **Reason:** §4.3 defines "exchange-listed" by CRSP share code. These are among the 2023
     failures §2.3 names.
   - **Alternative:** a second reading for listing only.
3. **BHV→MYI (asked as 3a): withdrawn, F = 2023-11-01.** The same ruling covers its three co-targets.
   - **The finding:** the 2023 proposal merged **BHV, BKN, MIY and MPA into MYI** under one N-14
     (File 333-274660). MYI's RW (0001193125-23-268272, 2023-11-01) states "proposed merger
     transactions that are no longer contemplated".
   - **Recommended:** all four deals are `withdrawn` with F = 2023-11-01, in the time holdout.
     Both parties are listed: each of the five CIKs maps to a CRSP CEF on NYSE on 2023-09-08
     (`e1_merger_pair.crsp_cik_map`; names only).
   - **Reason:** BHV's "superseded 2025-06-09" is the later, second proposal (BHV into MQY). F is
     the earliest public failure (§4.3, §6.1).
   - **Alternative:** superseded with F = 2025-06-09, which puts BHV→MYI in no set, beyond CRSP's
     2024-12-31. This alone would leave BKN, MIY and MPA→MYI unresolved.
4. **MCC → CIK 1523526: not a listed pair.**
   - **Reason:** the counterparty's own episode records it unlisted. Its one quote failure is
     then moot.
   - **Alternative:** a re-read.
5. **Rows that cannot change the trial (C1, C2, C3, and 8 rows of deals announced after
   2024-12-31): read; excluded from every E1 set; not blocking.**
   - This covers their blank outcomes, two quote failures in C2 rows, and six conflicts between
     a "completed" and a "not_a_listed_pair" reading. Five are listed BDCs (BBDC, GBDC, OCSL,
     CGBD, OTF) absorbing non-traded ones; the sixth's parties map to no CRSP CEF.
   - **Reason:** none of them can be a failed deal between two listed funds inside the census
     horizon.
   - **Alternative:** read every one to an outcome. That is about 400 rows, and it changes
     nothing in the trial.
6. **The N-8F rule (asked as 3b).**
   - **Recommended:**
     - a target's N-8F that states it merged into the named acquirer is `completed`;
     - one that names another survivor, or a liquidation, is `completed_other_structure`;
     - one that names neither leaves the outcome null.
     Batch 40 (`completed`) and batch 45 (null) are both re-read to this rule.
   - **Effect on the trial: none.** An N-8F never shows a failure. No T or I row cites one
     (all 13 N-8F readings are C2).
   - **Alternative:** N-8F is never outcome evidence, so all 12 become null.
7. **In-trial rows with a quote not found (asked as 3c): none.**
   - Every quote in every T1 row is re-found in its filing.
   - The only quote failure outside class C is in the MCC row (item 4).
8. **The residual: 67 rows in 54 deals and 47 episodes (I1 11, I2 34, I3 22) still could change
   the trial.**
   - **Recommended:** a second reading pass on those 47 episodes, with full excerpts of every
     filing (`e1_failed_reading.py` with a larger budget), read by Sonnet. A disagreement with
     the first pass is adjudicated by a third reading.
   - DG-E1-3 stays FAIL until then.
   - **Alternative:** whatever stays unread after the second pass is excluded and counted.
     §4.3 says an unreadable episode halts, so that would itself be a ruling.
9. **A gap in the census rule.**
   - "No CRSP completion within 730 days" cannot see a failed co-target whose acquirer
     completed another target in the same window.
   - That is how **SBI→MMU (2023), named in §2.3, is missed**: MMU's 2023 episode is explained
     by its other completed merger, and SBI filed no merger episode of its own.
   - **Recommended:** a supplementary census of the **149** acquirer-side episodes that a
     completion explained, each read only for named targets that did not complete.
   - **Alternative:** accept the gap and record it.

**If rulings 1–4 are accepted, the trial's failed deals are 9:**
- RAA→BFZ (2009, vote failed; the fit);
- AFT→AIF (2021, vote failed; the fit; A = 2021-03-18 from the acquirer's filings);
- BHV, BKN, MIY and MPA→MYI (withdrawn 2023-11-01; time holdout);
- NXJ→NAD, NQP→NVG and NMT→NEA (withdrawn 2023; time holdout).

Items 8 and 9 can add more. These are counts of deals, not returns.

## 4. The stale EDGAR index

Stage 0 needs the network for one thing only, the open quarter's full index (2026Q4). A probe on
2026-10-20 found it the only stale or missing URL among everything Stage 0 reads. Its one-day
`max_age` is unchanged. The team lead runs, from the `trial-events-e1` worktree:

    QUANTT_ENV_FILE=<absolute path to config/.env> python3 scripts/events/e1_merger_pair.py refresh-edgar-index

Then an agent runs `python3 scripts/events/e1_merger_pair.py stage0` within a day. Both default
`--today` to the run date.

## 5. 2026-10-21: after rounds r2 and n8f

> **RULED 2026-10-21.**
> - **Item 10:** "Accept the CRSP rule".
> - **Amendment 4:** "Amend: include 331". This widens the universe to code-331 reorganisations
>   into the acquirer's permno, the finding below.
>
> Both are recorded in `results/events/e1/e1_dg3_rulings.csv` (items 10–11) and in the
> pre-registration's banner. The two never-completed deals go to the third reading.
>
> *Was:* a form; nothing in this section is ruled.

**The merge** (`e1_failed_reading.merge_rounds`, rulings 8 and 6; Stage 0 runs it):
- The N-8F re-read replaces the first reading for its 19 episodes.
- For round 2's 47 episodes:
  - **no deal has two different non-blank outcomes, so no third reading is needed for a disagreement**;
  - in 4 rows the second reading's listing evidence settles a "withdrawn" pair as not listed;
  - a blank on either side is filled from the other reading.

**In-trial failed deals: 10, up from 9.** Round 2 adds **FGB→AOD**: the vote failed, made public
2024-08-29. CRSP settles the listing, so it is in the time holdout. Its segment is equity, so it is
reported and does not decide. The other nine are unchanged. (Stage 0, 2026-10-21:
`python3 scripts/events/e1_merger_pair.py stage0`.)

10. **Recommended: settle a blank outcome from CRSP.**
    - **Where it applies:** a reading leaves the outcome blank, and the target's printed ticker maps
      on A to a CRSP CEF or BDC permno. The rule is `e1_failed_reading.crsp_outcome` (tested).
    - **What it decides:**
      - delisted INTO the acquirer's permno within **730 days of A**, under a merger (2xx) or an
        exchange (3xx) code → `completed` on the delisting date;
      - a 2xx merger into another permno → `completed_other_structure`;
      - a liquidation (4xx) within 730 days → not completed (liquidated);
      - still listed at A + 730 days, inside CRSP → not completed;
      - anything else → unsettled.
    - **A not-completed deal has no dated failure,** and §6.1 needs the failure date F to exit it.
      So it goes to one more reading that looks for the failure filing. If none is found, it is
      excluded and counted.
    - **Why 730 days:**
      - It is §4.3's own census window ("no CRSP completion within 730 days").
      - It is about twice the longest typical time a CEF merger takes to complete, 4–12 months
        [S: `edgar_merger_dates.py` docstring].
      - It is measured from A, not the vote, because the readings carry no vote dates; A is the
        census's anchor.
    - **Why 3xx too:** CRSP codes many CEF reorganisations 331, an exchange, not 231. Examples
      measured 2026-10-21: BHY and HIS into HYT (2013), ARK into DSU, BCL into BFZ, DCW into DCA,
      NMD into NMZ. It is the match to the acquirer's permno that ties a delisting to this deal.
    - **What it settles:** 12 of the 31 blocking blank rows.
      - 9 rows (5 deals) become `completed`: ARK/BHD→DSU, BHY/HIS→HYT, DCW→DCA.
      - 3 rows (2 deals) become not completed: **NDP→TTP** (2020, equity) and **BKT→BHK** (2014,
        taxable). Neither is muni; both go to the failure-filing reading.
    - **In-trial deals it touches: none.** It applies only to blank outcomes. Where it does speak
      about an in-trial deal, CRSP agrees: RAA was liquidated on 2010-09-10, and AFT did not
      complete within 730 days. The other 8 in-trial deals have windows that run past CRSP's end.
    - **Alternative:** a third reading for all 12 rows.

**A finding for the record (no change proposed).** §4.1's deal universe is `dlstcd` 231. CEF
reorganisations that CRSP codes 331 are therefore in neither the fit nor the holdouts, and the
census rule cannot see them as completions. Widening the universe would be an amendment.

11. **What keeps DG-E1-3 open after item 10:**
    - **The supplementary round:** 149 episodes in 29 batches, built 2026-10-21 after the team
      lead's `fetch-edgar --supp`. SBI→MMU is in batch 27, and its excerpt names SBI.
    - **A third reading of up to 27 episodes:**
      - 19 rows that have neither an outcome nor a target ticker (19 episodes);
      - 8 failure rows whose listing is unsettled (5 episodes: PSEC 2014, JLS/JMT 2019, and one
        with no tickers);
      - the 2 not-completed deals of item 10 (3 episodes), for their failure filing.
    - **Then** the merge, and an offline Stage 0 within a day of an index refresh.

## 6. 2026-10-21, later: after amendment 4, ruling 10 and the supplementary round

Recorded from `python3 scripts/events/e1_merger_pair.py stage0` (output in `results/events/e1/`).

- **In-trial failed deals: 10, unchanged.** SBI→MMU is not yet among them:
  - its co-target MNP→MMU completed on 2023-10-13 by CRSP (ruling 10);
  - SBI's own row is blank, because its 730-day window runs past CRSP's end and the supplementary
    reader found no outcome stated.
- **Ruling 10 settled 163 reading rows from CRSP** and found 4 rows never completed: NDP→TTP and
  BKT→BHK, two episodes each.
- **The third-reading pack:** `e1_failed_reading.py prepare --round r3`, 28 episodes in 12
  batches. Each episode carries its open question:
  - 18 ask how a deal ended, SBI→MMU among them;
  - 6 ask whether both parties are listed;
  - 4 ask for the failure filing of the two never-completed deals.
- **Amendment 4 adds no reading.** Its new Stage 0 work is mechanical and needs the team lead's
  credentials:
  - dating the 11 new deals: `fetch-edgar --amendment4` (4 EDGAR documents are not cached);
  - CRSP rows for 9 new fit parties: `pull-crsp --permnos results/events/e1/_cache_e1/amendment4_crsp_permnos.txt`.
- **DG-E1-3 cannot clear yet.** It clears when round 3 settles the 22 blank rows and the 9
  unsettled-listing rows; anything round 3 leaves open needs a ruling.
- **If SBI→MMU stays open after round 3,** the next step is a fetch of SBI's own 2023 filings
  (CIK 882300). SBI filed no merger episode, so they are not in any pack.

## 7. 2026-10-21, after the third reading: what still blocks DG-E1-3

> **RULED 2026-10-21.** The team lead: "Accept 12–15" (relayed by the coordinator).
> - Recorded in `results/events/e1/e1_dg3_rulings.csv` (items 12–15) and the pre-registration's banner.
> - Applied in code, each with a test: `apply_dg3_rulings`, `apply_ruling_14`, `dg3_state`.
> - **On the readings:** 11 in-trial deals (Allied→Prospect joins). Excluded and counted: ruling 12,
>   7 deal ids; ruling 13, 5; ruling 14, 13.
> - **DG-E1-3 waits only on round r4** (SBI→MMU and NCU→NKX), once the team lead's fetches have run.
>
> *Was:* a form; nothing below is ruled.

**The third reading is merged** (`e1_failed_reading.dg3_state`):
- **Two fixes, each tested:**
  - Readings are now matched by CIK, then by printed ticker pair, and by position only when no
    reading names the parties. Position alone had paired round 3's SBI→MMU with the supplementary
    reading's MNP→MMU.
  - The supplementary round now enters before the third reading adjudicates.
- **In-trial failed deals: still 10.** Eight are muni; AFT→AIF is taxable and FGB→AOD equity.
- **Every row still blocking:** `results/events/e1/e1_dg3_blockers_2026-10-21.csv`, built from
  CRSP names and readers' fields only, with the index read as cached. Stage 0's strict record
  waits for the team lead's index refresh.

**29 rows block:** 22 have an unstated outcome (22 episodes), and 7 are failures whose listing is
unsettled (5 episodes).

| class | rows | deal ids | what they are |
|---|---:|---:|---|
| **(a) cannot change any decision** | 23 | 19 | Every one is non-muni, by its target's CRSP name or its own fund's: BDC, equity or taxable. Under decision 2, only muni deals decide |
| **(b) can** | 6 | 6 | **2 muni:** SBI→MMU (2023) and **NCU→NKX's 2011 proposal**. NCU merged into NKX only under a second proposal, first filed 2013-11-22 and completed 2014-06-06 (CRSP 231). **4 of unknown segment:** no reading names any party |

12. **Recommended: listing follows CRSP share codes (§4.3).**
    - Read each party's listing from CRSP by its printed ticker. Failing that, use its CIK through
      the trial's CRSP–CIK match, extended to share code 11 for BDCs.
    - A deal whose counterparty no reading and no CRSP record identifies is excluded and counted.
    - **Effect:**
      - **Allied→Prospect enters the trial:** an unsolicited proposal, terminated 2010-03-05.
        Both are listed BDCs in CRSP (ALD share code 11, PSEC 14). It is a fit deal in the BDC
        segment, reported and not deciding.
      - **6 rows are excluded and counted:** PSEC's 2014 bid, JLS/JMT 2019, and CIK 1796233's 2019
        RW. None is muni; one is of unknown segment.
13. **Recommended: never completed per CRSP, with no dated failure → excluded and counted.**
    - §6.1 cannot exit a deal without F.
    - Where a reading gives no announcement, ruling 10's 730 days run from the episode's first
      merger filing.
    - **Effect:** 4 deals, **none muni**: BKT→BHK (2014), NDP→TTP (2020), GDV (2014) and RVT (2011).
      NCU→NKX is left to item 15.
14. **Recommended: an outcome still unstated after three readings → excluded and counted.**
    - **Effect:** 14 rows, up to 12 deal ids, **none known to be muni.** Nine are the own funds of
      BDC, equity or taxable episodes; three are of unknown segment.
15. **Recommended: read the two muni deals in each target's own filings (round r4).**
    - The team lead fetches the filings first (commands below).
    - **If round r4 settles nothing:**
      - **SBI→MMU is excluded and counted.** It is §2.3's named failure, recorded as one the trial
        could not date.
      - **NCU→NKX takes §4.3's superseded rule:** F = the first filing of the later proposal that
        completed, 2013-11-22. Alternative: excluded and counted.

**If 12–15 are accepted** the in-trial set is 11 (10 + Allied→Prospect), plus whichever of the two
muni deals round r4 or §4.3 dates. DG-E1-3 then clears once round r4 is collected, with no
unruled row left.

**The team lead runs** (with amendment 4's script):

    QUANTT_ENV_FILE=<abs path to config/.env> python3 scripts/events/e1_merger_pair.py fetch-edgar --cik 882300 --around 2023-03-17
    QUANTT_ENV_FILE=<abs path to config/.env> python3 scripts/events/e1_merger_pair.py fetch-edgar --cik 905000 --around 2011-12-19

**Then an agent runs** `e1_failed_reading.py freeze-r4` once per fund (`--for-episode`
886043_0001193125-23-074093 for SBI, 1195738_0001193125-11-345556 for NCU), then
`prepare --round r4`, sends the pack to readers, and collects it.

## 8. 2026-10-22: Stage 0 CLEAR; ruling 16 (control 2 for ALD→PSEC)

> **RULED 2026-10-22.** The team lead: "Keep, with no comparison" (relayed by the coordinator).
> - Recorded in `results/events/e1/e1_dg3_rulings.csv` (item 16) and as amendment 6 of the
>   pre-registration.
> - Records only, no code change: the fit already leaves a deal with no candidate at NaN, counted.

**Stage 0 cleared at 732fc9d** (`results/events/E1_STAGE0_2026-10-19.md`). The fit's own
`control2_candidates` then found **no control-2 candidate for ALD→PSEC** (BDC, announced
2010-01-20, failed 2010-03-05):
- No CEF (share code 14/44) has the first name word "ALLIED" and the BDC segment.
- The other "ALLIED" names in force on A are unrelated operating companies, so allowing share
  code 11 would not supply one either.

**What the pre-registration says.**
- §8.2, stage 3: "**HALT** (to the team lead) if fewer than 75% of fit muni deals have a control".
- §0, headline segment: "Taxable, equity and BDC deals are reported beside it and never decide".
- It is silent on a non-muni deal with no candidate.

16. **Ruled: keep, with no comparison.**
    - ALD→PSEC stays in the trial with no control 2. It is recorded as "no candidate: no CEF has
      the first name word ALLIED", and counted.
    - **Effect:** none on any verdict. `fit_core` computes stage 3 on muni deals only, and the BDC
      line reports per-deal statistics with no controls.
    - **The alternative not taken:** exclude the deal and count it, as the 19 Stage 0 flags were.
      That would drop a deal the census ruled in and change the reported BDC line.
