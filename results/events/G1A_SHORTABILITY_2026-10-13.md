# Gate G1a: can E1's short-acquirer leg be built? — 2026-10-13

**What this is.** Gate G1a of `results/cef/RESEARCH_PLAN_2026-10-09.md` §2, for
trial E1 (the NAV-for-NAV CEF merger pair: long target, short acquirer, from
announcement+1 to completion). The gate as written: *"Alpaca shortability today
of acquirers in pending CEF/BDC mergers, and the historical share of shortable
acquirers. Passes when most acquirers are shortable. Kills when the hedged pair
is not buildable."*

**Zero trials.** A count, not a return. No counter moves and nothing is
pre-registered. The script never reads a return column: the 167-deal sample is
selected by its `status` column and the count is asserted.

**Holdouts.**
- No return is computed on anything. The 27-name comparison set is not consumed.
- Borrow flags and fees are read for `cef_universe.csv` names (NZF, MFM, NXP,
  MHD, MQY, NAD, NVG, NEA, JFR, EDF). Those are costs and flags, not returns.
- The 2023+ time holdout is untouched: the only 2023+ figures are flags read
  today and IBKR fee levels. Neither is a return.

**Data dates.**

| source | coverage |
|---|---|
| EDGAR quarterly indexes and filings | to 2026-Q4; newest filing date 2026-10-09; fetched 2026-10-13 |
| Alpaca `GET /v2/assets/{symbol}` (paper, `cef` key) | 84 symbols, read 2026-10-13 22:23:31–22:23:35 UTC, after the close |
| Alpaca `GET /v1/corporate-actions` | effective 2025-10-13 → listed to 2028-10-12; read 2026-10-13 |
| IBKR public shortstock file `usa.txt` | header `#BOF\|2026.10.13\|18:03:03`; fetched 2026-10-13 |
| FINRA semi-monthly short-interest files | 25 settlement dates used, 2018-01-31 → 2022-03-31 |
| IBKR FEE_RATE history (`data/cef/cef_borrow_history.parquet`) | 43 names, 2021-09-13 → 2026-09-09 |
| CRSP names (R2 mirror, cached) | to 2024-12-31 |

2026-10-12 was Columbus Day, so the index has no filings for that day [S: a
federal holiday; EDGAR's calendar not fetched].

**Labels.** Figures produced on 2026-10-13 by `scripts/events/g1a_shortability.py`
are [V], each true on its date only. Figures quoted from earlier notes are [S]
here.

## 0. The answer

**G1a fails for munis, which is where E1's effect lives.**
- **Muni pair: not buildable.** In most muni deals the acquirer cannot be
  shorted at Alpaca. That holds for the pending deals today and for the
  historical acquirers on today's flags.
- **Taxable and equity: the gate passes.** But the pair earns nothing worth
  testing there.
- **BDC: partial,** on 1 pending deal and 3 historical ones.

| segment | pending: listed acquirers shortable at Alpaca today | historical acquirers shortable at Alpaca today (same fund) | verdict | second source, IBKR today |
|---|---|---|---|---|
| **muni** | **1 of 2** (MMU yes; NZF no). By deal, 1 of 3 | **7 of 23 (30%)**. By deal, 16 of 57 measured (28%) | **FAIL** | pending 3 of 3 deals; historical 17 of 23 (74%) |
| taxable income | 1 of 1 (BRW) | 14 of 18 (78%) | PASS | 1 of 1; 16 of 18 |
| equity / other | no pair pending (IAE and IHD merge into an open-end fund) | 10 of 16 (62.5%) | PASS (historical only) | —; 16 of 16 |
| BDC | 0 of 1 (LIEN) | 2 of 3 | PARTIAL | 1 of 1; 3 of 3 |
| all | 2 of 4 (2 of 5 deals) | 31 of 56 (55%) | PARTIAL | 5 of 5 deals; 48 of 56 |

The verdict rule (`segment_verdict`): "most" means more than half. A segment
passes if every Alpaca measure it has is above 1/2, fails if every one is at or
below 1/2, and is partial if they disagree. Exactly 1/2 is not most. IBKR and
FINRA are shown beside the verdict, never inside it: the book cannot borrow at
either.

**What this means for E1** (§4 has the detail):
- **The muni effect cannot be harvested at Alpaca.** On EDGAR dates the muni
  median is +167bp (t 2.41) [S: `EDGAR_EVENTS_2026-10-12.md` §3]. Most muni
  acquirers cannot be shorted, so most of the hedged pairs cannot be built.
- **Where the acquirer can be shorted, the measured effect is too small.**
  Taxable deals give +4.6bp (t 0.98) and equity +15bp (t −0.16) [S: same
  table].
  - Both are already below E1's pre-registered kill line: a median ≤ 60bp or
    a clustered t < 2 (plan §3).
  - **A taxable-only or taxable-plus-equity E1 would spend EVENTS 0→1 on a test
    that the existing descriptive figures say fails.**
  - Recommendation: do not spend the trial on that version.
- **A muni E1 restricted to Alpaca-shortable acquirers cannot be tested ex
  ante.**
  - Alpaca keeps no flag history. Filtering the 2010–22 deals on today's flags
    selects on information from the future.
  - On today's flags it would be 16 deals in 9 acquirer × announcement groups.
    That is under G1c's 30-group bar (D7).
- **At IBKR the muni short is mostly available, but borrow looks likely to
  consume the effect.** This is arithmetic on [S] inputs, not a measured net
  return.
  - At first filing, ten universe muni acquirer episodes (2021–26) paid a
    median IBKR fee of **9.43%/yr** (range 2.57–71.73) [S levels].
  - The sample's median hold is 184.5 days [S]. Over that hold, 9.43%/yr is
    about **483bp** of short notional, against the +167bp muni median gross.
  - Even today's NZF fee of 3.15% comes to about 162bp over that hold.
  - The EDGAR note charged no borrow ("not measured historically"). This is the
    first figure for it, and it looks decisive.

So **E1 as designed is not buildable for munis at Alpaca, and the segments
where it is buildable show no effect.** The decision on the trial is the team
lead's. Section 4 sets out the options.

## 1. How to re-run

```bash
export QUANTT_ENV_FILE=".../config/.env"     # Alpaca cef key, SEC_USER_AGENT, R2 (CRSP cache); never printed
python3 scripts/data/fetch_edgar_events.py             # the EDGAR cache (or --offline to rebuild from it)
python3 scripts/events/edgar_merger_dates.py           # deal dates -> merger_edgar_dates.csv (gitignored)
python3 scripts/events/merger_pairs.py --edgar-dates   # -> merger_ann_sample_edgar.csv (gitignored)
python3 scripts/events/g1a_shortability.py             # EDGAR, Alpaca, IBKR file, FINRA files; caches under _cache_g1a/
python3 scripts/events/g1a_shortability.py --offline --today 2026-10-13   # the same from the caches
python3 -m pytest scripts/events/tests/test_g1a_shortability.py
```

Outputs:
- `g1a/g1a_pending_2026-10-13.csv`: tracked. It holds only EDGAR, Alpaca and
  IBKR data.
- `g1a/g1a_summary_2026-10-13.json`: tracked. Counts only.
- `g1a/g1a_historical_deals.csv` and `g1a/g1a_detail_2026-10-13.json`: gitignored,
  because they carry CRSP names and permnos.

**The script raises rather than guess.**
- **`UnreadCandidate`** if an EDGAR deal appears that no hand reading covers.
- **`ReadingOutOfDate`** if a "pending" target has stopped trading, or Alpaca's
  feed shows its merger effective.

So the pending list cannot silently go stale. The Voya reading will raise once
IAE and IHD close, expected on or about 2026-10-16.

## 2. Pending deals today

**Method.**
1. Every merger-kind filing of the CEF/BDC fund set: 425, N-14 8C, N-14 and
   merger proxies (`fetch_edgar_events.build`).
2. Funds that share an accession number are linked, so one connected component
   is one deal. A 425 is indexed under the filer and each subject company.
3. A component is a **candidate** if a fund in it is listed today and its last
   merger filing falls within 180 days of the newest index date.
   - 180 days is the fetcher's own merger-episode gap. A CEF merger keeps
     filing until its vote.
   - The rule was chosen from that process, not fitted.
4. 12 candidates qualified. Each was read and recorded in `READINGS` with its
   accession numbers:
   - 5 are pending;
   - 3 completed in 2026: MFM, MMT and FCT;
   - 3 are not mergers: FRBP and FDUS register note exchange offers, and ASA is
     one fund's proposed conversion to a BDC;
   - the other candidate is the second Voya fund: IAE and IHD are separate
     components under one reading.

**The pending deals, 2026-10-13** (`g1a/g1a_pending_2026-10-13.csv`):

| target → acquirer | segment | announced | status (source) | acquirer at Alpaca | acquirer at IBKR (fee %/yr, shares) | target at Alpaca |
|---|---|---|---|---|---|---|
| NMS → **NZF** | muni (Nuveen) | 2026-04-29, Business Wire release [V, syndicated copy] | meeting adjourned; reconvenes **2026-10-29** (425 of 2026-09-24, 0001999371-26-021258) [V] | **not shortable**, `hard_to_borrow` | 3.15, 200,000 | active, not shortable |
| NPV → **NZF** | muni (Nuveen) | same | same | same | same | active, shortable |
| SBI → **MMU** | muni (Western Asset) | 2026-07-31, Business Wire [S, URL date] | SBI meeting **2026-11-18** (424B3 of 2026-09-22, 0001193125-26-397702); SBI shares convert "based on the net asset value" [V] | **shortable**, `easy_to_borrow` | 1.19, 40,000 | active |
| SABA → **BRW** | taxable by the name rule; a Saba multi-asset fund | 2026-08-20, Business Wire re-approval [V, syndicated copy] | N-14 8C 2026-08-27 (0001213900-26-094358), not effective; target closing Q4 2026 | **shortable**, `easy_to_borrow` | 0.43, 700,000 | active |
| REFI → **LIEN** | BDC (target is a mortgage REIT) | 2026-06-18, 8-K item 1.01 (0001213900-26-069853) [V] | N-14 8C/A 2026-09-23, EFFECT 2026-09-30; ratio is "Closing REFI NAV to the Closing LIEN NAV" [V] | **not shortable**, `hard_to_borrow` | 3.82, 1,100,000 | active |
| IAE, IHD → IEMLX | equity (Voya) | 2026-06-02 (425 press release, 0000895430-26-000004) [V] | meeting about 2026-09-28; closing about **2026-10-16** (425 of 2026-08-24) [V] | **no listing**: IEMLX is an open-end mutual fund | not in the file | active |

**Readings.**
- **NZF.**
  - NZF is a `cef_universe.csv` name: one of the four munis the live book
    dropped on Alpaca (`merger_pairs.DROPPED_ON_ALPACA`).
  - It is not among the 13 names the book trades, and the paper account holds
    no NZF (probe of 2026-10-13).
  - A pre-registered E1 that trades NMS/NPV → NZF would touch a
    `cef_universe.csv` name, and the pre-registration must say so.
- **SABA → BRW** is the second attempt. The first was terminated on 2026-03-25
  (8-K 0001398344-26-005637; N-14 withdrawn by RW 0001398344-26-005635).
- **SBI's 2023 merger into MMU failed its vote** [S: search summary of the 2023
  releases, not fetched].
- **Alpaca's corporate-actions feed lists none of the seven pending pairs.** Its
  only future-dated stock merger is NSC → UNP, on 2027-03-31.
  - It does not list even IAE/IHD → IEMLX, three days before closing.
  - The 2026-10-11 note called the feed's pending coverage "partial at best
    [U]". On this date it is nil [V].

**What the index cannot see** (stated, not filled):
- A deal announced by press release with no EDGAR filing yet.
  - A web search on 2026-10-13 found no CEF/BDC merger announced in
    September–October 2026 [S: search summaries].
  - The latest announcements found were SABA→BRW (2026-08-20) and SBI→MMU
    (2026-07-31). Both are on EDGAR.
- A party outside the CEF/BDC fund set. The REIT target REFI and the open-end
  IEMLX appear only through the fund that filed.

## 3. The historical share: the 167 EDGAR-dated, priced deals of 2010–22

Alpaca keeps no flag history. Every source and its exact coverage:

| measure | what it is | deals covered (of 167) | result |
|---|---|---|---|
| H1: IBKR FEE_RATE history at announcement | `cef_borrow_history.parquet`; 43 universe names from 2021-09-13 | **0**. The 167 exclude every universe name by construction, and the last announcement is 2022-04-04 | — |
| H1b, context: universe acquirers in later deals | fee on the last day before the first merger filing | 12 episodes, 2021-12 → 2026-05: 10 muni, 2 taxable. These are not in the 167 | muni median **9.43%/yr** (2.57–71.73); taxable 15.58 (JFR), 16.61 (EDF) [S levels] |
| H2: FINRA short interest at announcement | reported short position at the last settlement before the announcement, under the CRSP ticker in force that day | **51** (announced after 2017-12-29; earlier files return HTTP 403) | **51 of 51 positive**: muni 28/28, taxable 12/12, equity 9/9, BDC 2/2 |
| H3: Alpaca flags today | the same fund only (below) | **109** deals; 56 of 89 acquirers | muni 16/57 deals, 7/23 acquirers; taxable 17/22, 14/18; equity 18/27, 10/16; BDC 2/3, 2/3 |
| H4: IBKR shortstock file today | shares available > 0, same names as H3 | 109; 56 acquirers | muni 41/57, 17/23; taxable 20/22, 16/18; equity 27/27, 16/16; BDC 3/3, 3/3 |

**Identity for H3 and H4.** A deal's acquirer is measured today only if all of
these hold:
- its CRSP permno is still listed on 2024-12-31;
- it has the same share code as at the announcement. One taxable acquirer
  changed share code and is excluded;
- it is active on Alpaca under its CRSP ticker;
- Alpaca's name matches CRSP's, either directly or through the EDGAR name
  history of the CIK that the SEC ticker file gives for that ticker. Seven
  renamed funds pass the second route.

Not measured:
- muni: 19 deals gone by 2024-12-31; 14 inactive on Alpaca (the 2025–26
  BlackRock and Nuveen consolidations); 2 under **BNY**, which is now BNY
  Mellon's ticker;
- taxable: JPC, a false negative of the name rule (PFD/OPPTYS), counted as
  unmeasured, never as not shortable.

**H2's reading.**
- Every covered acquirer had a reported short position when its deal was
  announced. Median position: munis about 20,900 shares, taxable 27,526,
  equity 60,175. Borrow existed somewhere.
- **This is not evidence that Alpaca would have lent.**
  - A FINRA position includes market makers' shorts.
  - The NZF and LIEN rows today show the split: shares at IBKR, a hard no at
    Alpaca.
- Six FINRA names fall below the name check. Five are visibly the same fund
  (SRV, MUJ, ENX, KYN, NNY).
- One is not resolved: on 2021-09-15 FINRA names symbol MUI "BLACKROCK
  MUNIYIELD NEW JERSEY", where CRSP has BlackRock Muni Intermediate Duration
  Fund (one deal, MFL → MUI) [U].

**Two dates of Alpaca flags.**
- Against the 2026-10-11 read (`acquirer_shortability.py`), 11 of 63 symbols
  changed `shortable` in two sessions.
- Among munis, IQI and MUA turned off, and NCA, NPV and VTN turned on.
- The muni count was 7 of 23 on both dates, on different names.
- Measured as a one-off comparison of the two cached reads; the script does
  not reproduce it.

## 4. Verdict, and what it means for E1's trial

- **Muni: FAIL.**
  - Pending: 1 of 2 acquirers shortable (1 of 3 deals).
  - Historical, on today's flags: 30% of acquirers (28% of deals).
  - At IBKR the same names are mostly available (74%), so "not shortable" is a
    fact about Alpaca's supply, not about the asset.
  - The earlier claim that muni acquirers are "mostly not shortable" [U] is
    therefore **true at Alpaca and false at IBKR**. At announcement, every
    covered muni acquirer had short interest.
- **Taxable: PASS** (pending 1/1; historical 78%).
- **Equity: PASS** (historical 62.5%; no pending pair).
- **BDC: PARTIAL** (pending 0/1; historical 2/3). Too few deals to read.

**For E1.** The plan's kill condition is "the hedged pair is not buildable". It
holds for munis, the segment that carries the whole effect. What remains:

1. **Taxable (+ equity) only.** Buildable, but the existing descriptive
   medians already sit below E1's kill line:
   - taxable +4.6bp, t 0.98, N 39;
   - equity +15bp, t −0.16, N 33.

   Running it buys a known negative with the first EVENTS trial. **Not
   recommended.**
2. **Muni, shortable acquirers only.**
   - Not testable ex ante: there is no flag history.
   - 16 deals in 9 groups on today's flags, under G1c's 30-group bar.
   - It could only run forward. Muni deals came in 47 acquirer ×
     announcement groups over 13 years [S]; at about 30% shortable that is
     roughly one qualifying group a year. On today's flags it was 9 groups in
     13 years. Reaching 30 groups would take decades. **D7.**
3. **Muni at another broker with IBKR-like supply.**
   - Available, but borrow at the fees observed at first filing would exceed
     the muni effect over a typical hold.
   - Before any trial, this needs the cost grid with **measured borrow** on
     acquirers, which the merger figures have never charged.
   - Broker choice is plan item 4.2.
4. **Hedge the target with something other than the acquirer** (a muni ETF or
   CEF basket). That is a different trade: it leaves the acquirer's own
   discount risk open. It would be a new idea with its own graveyard check,
   not E1.

**Recommendation.** Mark E1 blocked by G1a. Do not spend EVENTS 0→1 on it as
designed. Recording the decision is the team lead's call. G1b (plan 0.8) does
not change this verdict.

## 5. Findings outside the question

- **Pending-deal flags disagree across brokers.** NZF and LIEN are
  `hard_to_borrow` and not shortable at Alpaca. IBKR has 200,000 and
  1,100,000 shares at 3.15% and 3.82%.
  - Whether a live Alpaca account would offer a locate on them could not be
    tested: the locates API is "not available in paper trading" [V,
    REFERENCES §12l].
  - Alpaca's documentation shows `shortable: true` alongside
    `hard_to_borrow` for TSLA. So `shortable: false` reads as a hard no today,
    not a locate-only state [V: docs page, updated 2026-09-17].
- **Conversions into an ETF or an open-end fund are a separate kind of event.**
  - Examples: FCT → First Trust Flexible Income ETF (FFLX, a new ETF; FCT
    delisted 2026-08-10, Form 25-NSE 0000876661-26-000668); IAE, IHD → IEMLX.
  - The acquirer does not trade on an exchange before closing, so no pair
    exists.
  - The 2010–22 sample excludes them by construction (both legs CRSP-listed).
- **Failed and repeated proposals are not rare.**
  - SABA → BRW was terminated and re-approved within five months.
  - SBI → MMU failed in 2023 [S] and is back.
  - Nuveen's 2023 N-14 8Cs for NXJ → NAD (0001193125-23-226368) and NQP → NVG
    (0001193125-23-230662) were followed by NXJ and NQP merging into NMZ in
    2026 [V: Alpaca feed]. So those 2023 proposals did not complete [inferred;
    the outcome filings were not read].
  - The CRSP sample holds completed deals only (`EDGAR_EVENTS_2026-10-12.md`
    §6). E1's failure handling is not a formality.
- **The live book is short MHD and MQY today** (probe of 2026-10-13,
  `results/ops/alpaca_probe/2026-10-13_cef.json`, untracked in the main
  checkout). Both were
  merger acquirers to 2026-02, and their IBKR fee at first filing was 7.04% and
  5.88%. This is context for C1; G6 covered the period to 2022.

## 6. Gaps (stated, not filled)

- **No Alpaca flag history exists**, so "shortable at announcement at Alpaca"
  cannot be measured for any historical deal. H3 is today's flags on the
  survivors: 109 of 167 deals.
- **IBKR FEE_RATE levels before 2026-09 have no independent source** [S,
  REFERENCES §12l]. FEE_RATE is a cost, not availability.
- **FINRA files before 2017-12-29 were not found** (HTTP 403 on every 2017 date
  tried before it). FINRA's query API needs POST and a credential, so it was
  not used.
- **The IBKR file's time zone is not stated in the file** [U]. It was fetched
  at 22:23:36 UTC (18:23 ET). The stamp, 18:03:03, is consistent with Eastern
  time.
- **The SBI → MMU announcement date is from a Business Wire URL** in a search
  result [S]. The release was not fetched. EDGAR's first filing is 2026-08-04.
- **BRW's exchange basis was not read** in its N-14 8C. The filing still has
  placeholders.
- **Segment labels follow `merger_pairs.classify`.** That rule is a name
  regex: BRW is "taxable" by name but holds a multi-asset book. LIEN is
  labelled BDC by hand, because the regex would call it equity.

## 7. Files

- `scripts/events/g1a_shortability.py`: the gate.
- `scripts/events/tests/test_g1a_shortability.py`: tests, run under
  `scripts/events/tests` in `pytest.ini`. Four were checked to fail against a
  broken rule: ≥ ½ counted as most; unmeasured counted as not shortable;
  `last_before` inclusive; share-code change ignored.
- Tracked outputs:
  - `results/events/g1a/g1a_pending_2026-10-13.csv`;
  - `results/events/g1a/g1a_summary_2026-10-13.json`.
- Gitignored:
  - `results/events/g1a/g1a_historical_deals.csv`;
  - `results/events/g1a/g1a_detail_2026-10-13.json`;
  - `results/events/_cache_g1a/`, which holds the Alpaca reads, the feed, the
    IBKR file and the FINRA files.
- Sources: `docs/REFERENCES.md` §12p.
