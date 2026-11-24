# The EDGAR event fetcher, the merger announcement dates and gate G6 — 2026-10-12

**What this is.** Plan item 0.7 of `results/cef/RESEARCH_PLAN_2026-10-09.md`
(the EDGAR event fetcher), and the two questions it unblocks:

- **(a)** the merger pair's at-announcement figure on announcement dates read
  from EDGAR, against the +35bp / −19bp of `REPRO_CEF_EVENTS_2026-10-11.md` §2;
- **(b)** gate G6 (plan §2): how often the live book shorted a name under a
  pending NAV tender, merger or liquidation, and what it cost.

**Zero trials.** Nothing is pre-registered and no counter moves. (a) is
descriptive, like the re-run it extends. (b) is the zero-trial gate the plan
defines; it reports a cost, it does not adopt a filter.

**Holdouts.**
- Every return is dated before 2023-01-01. `crsp_events.daily` cannot return a
  later CRSP row; `band_frontier.fit_only` truncates the book before any policy
  runs. 2023+ events are counted or named, never priced.
- (a) computes no return on any `cef_universe.csv` fund (the re-run's
  ticker-or-permno exclusion). (b) computes returns on the 13 deployed names
  only. **The 27-name comparison set is not consumed.**

**Data dates.**

| source | coverage |
|---|---|
| EDGAR quarterly indexes (`master.gz`) | 2008-Q1 → 2026-Q4; last filing date seen 2026-10-09; fetched 2026-10-12 |
| EDGAR submissions API, filing texts | the funds named below; fetched 2026-10-12 |
| SEC ticker file | as of 2026-10-12 |
| CRSP (R2): names, delistings | to 2024-12-31 |
| CRSP (R2): daily returns | last row 2022-12-30 |
| `data/cef/` price / NAV panels (b) | prices to 2026-09-28, NAV to 2026-09-25; used to 2022-12-30 only |

**Labels.** Figures produced by the scripts named here on 2026-10-12 are [V].
The 2026-10-11 figures quoted for comparison are [V] as of that note.

## 0. The answer

- **The fetcher exists.** It covers 2,371 CEF/BDC filers and 95,155 event
  filings from 2008 (87,874 from 2010), with dated tender, merger and
  proxy-contest episodes. All 44 `cef_universe.csv` funds are in the set.
  Requests are capped at 8 a second, under the SEC's stated 10.
- **(a) The at-announcement median is positive on EDGAR dates, and larger.**
  - All 186 deals in the re-run's sample were dated from EDGAR, and 167 are
    priced: **median +86.5bp** (mean +96.6, 60.5% positive) in 102 acquirer ×
    date groups, with a group-clustered t of 1.93.
  - At 2 units of turnover per deal the median net is +76.5 / +56.5 / +26.5bp
    at 5 / 15 / 30bp. At 4 units it is +66.5 / +26.5 / **−33.5bp**: **the sign
    flips at 30bp if both legs are traded out**.
  - It lives in munis: +167bp (N 92, 47 groups, t 2.41). Taxable is +4.6bp,
    equity +15bp and BDC −87bp (N 3).
  - **On the agent's own 36 events, EDGAR dates give +15bp**, against +35bp on
    the agent's dates. On the agent's 6 EDGAR-read groups, EDGAR's dates give
    −110bp, against −19bp. Those were 18 events, and the dates moved by 0–27
    days. So the 36-event figure was small and date-fragile in both
    directions. The 167-event figure is the one to use.
- **(b) G6: immaterial, so build the filter as hygiene, with no trial.**
  - From 2013-06-21 (the 13-name book's first position) to 2022-12-30, no spec
    name had a pending NAV tender for its common shares, was a merger target,
    or had a liquidation or open-ending proposal.
  - Four names were merger **acquirers**: HYT in 2013, MHD and MQY in 2020–21,
    and PDI in 2021. The book was short in those windows on **4 name-days
    (PDI), and it cost 9.1bp in total, or 0.95bp a year**.
  - That is far below the cost grid on either reading. Book turnover × 5bp is
    67.8bp a year; the bare 5bp is 5bp a year.
  - CRSP returns give the same −9.09bp.
- **Live fact (not measured; 2023+):** MHD and MQY were acquirers in a deal
  first filed on EDGAR on 2025-01-21 (425). Its last filings were 2026-02-10
  (MHD) and 2026-02-23 (MQY), matching the completions Alpaca reported for
  2026-02-09 and 2026-02-23.

## 1. How to re-run

```bash
export QUANTT_ENV_FILE=".../config/.env"            # SEC_USER_AGENT and R2 keys; never printed
python3 scripts/data/fetch_edgar_events.py          # indexes -> filings table, episodes, summary
python3 scripts/events/edgar_merger_dates.py        # CRSP sample -> EDGAR announcement dates (a)
python3 scripts/events/merger_pairs.py --edgar-dates  # the at-announcement figure on those dates
python3 scripts/events/g6_corporate_action_shorts.py  # gate G6 (b)
# each EDGAR script also takes --offline: the cache in results/events/_cache_edgar/ only
python3 -m pytest scripts/data/tests scripts/events/tests
```

## 2. Part 1 — the fetcher (plan 0.7)

**The route, and why.** This is documented on sec.gov; the sources are in
`docs/REFERENCES.md` §12g.

- **The quarterly full indexes** (`full-index/{YYYY}/QTR{n}/master.gz`). They
  are the only documented route that lists every filing of a form across all
  filers without knowing them first. That is exactly the problem: there is no
  SEC list of closed-end funds, and most funds that merged away have no ticker
  today.
  - A filing is indexed under every party. A Rule 425 appears under the
    filer and each subject company (checked on the Nuveen New York 425s of
    2012-06-22).
  - 77 requests cover 2008-Q1 to 2026-Q4.
- **The submissions API**, per named fund only. It supplies 8-K item numbers
  and full histories; its `files` pages are followed.
- **The SEC ticker file**, for "ticker where mappable": the ticker *today*.
- Full-text search is not used. Its JSON endpoint is the back end of a web
  form, not a documented API.

**Rate limit and contact.**
- The SEC's fair-access page, reviewed 2024-06-26, states "Current max request
  rate: 10 requests/second" and asks for a declared User-Agent with a contact
  address.
- `scripts/data/edgar_client.py` sends one request at a time, at least 0.125s
  apart (8/s). It sends `User-Agent`, `Accept-Encoding: gzip, deflate` and
  `Host`.
- On 403, 429 or 503 it backs off for 30s, 120s and 600s, then raises.
- The contact is read from the env file as `src/data/r2.py` reads its values.
  It is never printed, logged or cached, and the repr redacts it. A missing
  value raises naming `SEC_USER_AGENT`.
- Every response is cached under `results/events/_cache_edgar/` (gitignored),
  with a manifest of URL, time, bytes and SHA-256.

**Which funds.** The set is 2,371 CIKs.

| rule | CIKs | what it is |
|---|---:|---|
| `marker_form` | 2,109 | filed a closed-end-only form since 2008: the N-2 family, N-14 8C, N-54A/C, N-6F, N-23C-2, N-23C3A/B/C |
| `ncsr_insider` | 262 | filed an N-CSR and appears on a Form 3 or 4. Section 30(h) of the Investment Company Act puts closed-end funds, not open-end funds, under insider reporting |

- **Recall.** All 44 `cef_universe.csv` funds are in the set: 41 by marker
  form, and 3 (EDD, NIM, TEI) only by the second rule.
- **Precision of the second rule.** A reading of 60 randomly drawn names found
  6 open-end or ETF trusts: iShares Trust, Schwab Strategic Trust and others,
  which appear because the index also lists a Form 4 under its reporting
  owner. That is about 90% [U, one sample].
- Non-traded CEFs and BDCs are included; 442 funds have an exchange ticker
  today.

**Coverage**, 2010-01-01 to 2026-10-09 (`edgar_events_summary.json`;
2008–09 is kept as look-back):

| kind | forms | filings 2010+ |
|---|---|---:|
| tender | SC TO-I (6,691), SC TO-I/A (7,323), SC TO-C (535), SC TO-T(/A) (327), SC 14D9 (22) | 14,898 |
| merger | 425 (4,531), N-14 8C(/A) (688), N-14(/A) (248), DEFM14A / PREM14A (64) | 5,542 |
| vote | DEF 14A (11,197), DEFA14A (9,713), PRE 14A (2,325), DEFR/PRER14A | 23,974 |
| contest | PREC14A, DEFC14A, DFAN14A, DEFN/PREN14A | 2,042 |
| current | 8-K(/A) | 26,084 |
| offering | N-2 family (6,917), 424B1–8 (5,430) | 12,347 |
| deregistration | N-8F family | 2,987 |
| **total** | 2,285 funds | **87,874** |

**Episodes, 2010+** (`edgar_cef_bdc_episodes.csv`):
- tender: 1,133, of which 258 belong to funds listed today;
- merger: 801 (210 listed today);
- contest: 264 (131 listed today).

Most tender filings are interval funds' quarterly repurchase offers. Dates
extracted per episode:
- `first_date`: the first EDGAR filing. It is an **upper bound** on the
  announcement, because a press release can precede it and CEFs need not file
  8-Ks.
- `commence_date`: the first SC TO-I or SC TO-T (tenders).
- `last_date`: the last filing. For a tender, this is normally the final
  amendment, filed after expiry.
- `dereg_date`: an N-8F within 730 days.

The index cannot see a merger's completion date. CRSP supplies it in (a) and (b).

**Filing dates.** A filing dated t was accepted by 17:30 ET on t, under 17 CFR
232.13(a)(2) [S]. An evening decision on t may use it. A decision at t's
close must lag it a day.

## 3. Part 2(a) — merger announcement dates, and the at-announcement figure

**Method** (`scripts/events/edgar_merger_dates.py`; numbers from
`merger_edgar_dates_summary.json`).

1. **CRSP fund to CIK, by name.** CRSP's 32-character names are matched to the
   names EDGAR's indexes show in use near completion:
   - an abbreviation is a same-initial subsequence (QLTY → QUALITY);
   - state codes map to states only;
   - numbers must agree;
   - spaced initials are joined (F S K K R → FS KKR);
   - a one-letter typo is allowed (CRSP's NUVEEEN).

   A match needs a score of at least 0.85 and a margin of at least 0.02;
   otherwise it is reported unmatched.
   - **Targets:** 186 of 186 matched.
   - **Acquirers:** 184 matched. NHS is ambiguous: two CIKs carry the name, and
     both were tried. BLJ's acquirer has no CRSP name.
2. **The first merger filing** in the deal's last unbroken run of merger filings
   (no gap over 180 days) before completion. It is the earliest of:
   - a 425 or merger proxy indexed under the target;
   - an 8-K item 1.01 of either party;
   - the acquirer's N-14 8C / N-14.
3. **Read before use.** The filing's own document, not its exhibits, must name
   the target. A filing indexed under the target must also name the acquirer.
   An 8-K must carry merger-agreement language. Each rule exists because the
   first pass failed without it:
   - SUNS, OCSI and FSKR were dated by credit-facility 8-Ks, 22–24 months
     early;
   - FSKR was dated by the 425s of its own 2019 merger;
   - an exhibit's defined terms passed the merger-language test.

   17 deals had at least one candidate rejected (listed per deal).

**Dates.**
- 186 of 186 deals are dated:
  - 90 by a 425;
  - 3 by an 8-K;
  - 93 only by the acquirer's N-14, so their date is an upper bound.
- The median is 184.5 days before completion (range 84–501).
- Against the agent's dates (`merger_ann_edgar_summary.json`):
  - **the 6 groups it read in EDGAR:** NRK, BLE/BNY, SUNS and FSKR agree to
    the day; OCSI is +1 day (8-K filed the day after signing); CH is 0 days
    for 5 targets, +1 for ABE and +27 for GRR;
  - **the 7 search-summary groups:** NJV/NPN and GDF agree; BPP is +3 and MYC
    is +1. HIH is +40 and GGM/GPM +10: EDGAR has only the N-14 for these,
    where the agent had board or press dates.

**The figure.**
- Entry is at the close of A+1, held to completion: the existing
  `merger_pairs._announcement_row`, now shared by both date sources.
- CRSP total returns, pre-2023 only.
- Medians are in bp per $1 long target / $1 short acquirer.
- Net = gross − c × units. 2 units means entry only (the target's shares
  convert into the acquirer's and close the short); 4 means both legs traded
  out.
- Borrow on the acquirer is **not** charged (not measured historically; see
  G1a).

| sample | N | groups | median | mean | % > 0 | clustered t | net med 5/15/30 (×2) | net med 5/15/30 (×4) | flips? |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| **all EDGAR-dated** | **167** | **102** | **+86.5** | +96.6 | 60.5% | 1.93 | +76.5 / +56.5 / +26.5 | +66.5 / +26.5 / −33.5 | ×4 at 30bp |
| dated by a merger communication | 88 | 54 | +80.0 | +96.8 | 61.4% | 1.49 | +70 / +50 / +20 | +60 / +20 / −40 | ×4 at 30bp |
| dated by N-14 only (upper bound) | 79 | 48 | +96.3 | +96.4 | 59.5% | 1.24 | +86 / +66 / +36 | +76 / +36 / −24 | ×4 at 30bp |
| muni | 92 | 47 | +167.4 | +125.8 | 68.5% | 2.41 | +157 / +137 / +107 | +147 / +107 / +47 | no |
| taxable income | 39 | 30 | +4.6 | +138.1 | 51.3% | 0.98 | −5 / −25 / −55 | −15 / −55 / −115 | already ≤0 at 5bp |
| equity / other | 33 | 26 | +15.0 | −18.2 | 51.5% | −0.16 | +5 / −15 / −45 | −5 / −45 / −105 | yes |
| BDC | 3 | 3 | −86.9 | −72.8 | 33% | — | — | — | — |
| one obs. per group (group mean) | 102 groups | | +72.3 | +109.9 | 60.8% | | | | |
| every member at its group's earliest date | 167 | 99 | +86.5 | +97.5 | 61.1% | 1.87 | as row 1 | as row 1 | ×4 at 30bp |
| **agent's 36 events, EDGAR dates** | 36 | 17 | **+15.1** | +49.1 | 52.8% | 0.30 | +5 / −15 / −45 | | yes |
| agent's 36 events, agent dates (2026-10-11) | 36 | 15 | +35.1 | +83.9 | 55.6% | 0.47 | +25 / +5 / −25 | | yes |
| agent's 6 EDGAR-read groups, EDGAR dates | 18 | 8 | −109.8 | −100.7 | 44.4% | −0.45 | | | |
| the same, agent dates (2026-10-11) | 18 | 6 | −18.9 | −78.7 | 50% | | | | |
| agent's 7 search-summary groups, EDGAR dates | 18 | 9 | +64.8 | +198.8 | 61.1% | 0.79 | | | |

**Dropped:** 19 of 186.
- 18 have no acquirer price at A+1. These are mostly acquirers created by the
  merger, with no pre-merger trading.
- 1 has no acquirer price at payment.

**Reading, plainly.**
- **On EDGAR dates the at-announcement pair is positive.** The median is
  +86.5bp per deal across 167 deals in 102 groups, and it holds whether a group
  counts once (+72bp) or each deal does.
- **It is positive at every cost on the 2-unit convention.** With 4 units it
  turns negative at 30bp.
- **It is not robustly significant:** the clustered t is 1.93.
- **It is a muni effect** (+167bp, t 2.41). Taxable and equity deals are about
  zero or negative.
- **The −19bp "warning" of 2026-10-11 was a small-sample artefact of which
  dates had been looked up**, not a sign of the effect:
  - those 18 events give −110bp on EDGAR's dates;
  - the other 18 give +65bp;
  - the full EDGAR-dated sample gives +86.5bp.

For reference only: E1's pre-registered kill test (plan §3) is median ≤ 60bp
or clustered t < 2. This descriptive figure sits above the first threshold and
just below the second. E1's controls, failure handling and ex-ante sign (G1b)
are not in it.

## 4. Part 2(b) — gate G6

**Method** (`scripts/events/g6_corporate_action_shorts.py`;
`g6/g6_summary.json`).

**The events.** For each of the 13 spec names (spec `cef_discount.v7.20260928`,
read through `spec.py`), its full EDGAR history was taken from the submissions
API and grouped into episodes:

- **Tenders.** Each tender episode's cover page was read
  (`classify_tender`: "Title of Class of Securities").
- **Mergers.** Role is acquirer if the fund filed the N-14 8C. The end is the
  CRSP completion (codes 2xx and 3xx). The start is the earlier of the fund's
  and its targets' first merger filing.
- **Proxies and 8-Ks.** Every PRE 14A / PRER14A and 8-K was searched for
  liquidation, termination, open-ending and tender language. The 44 leads were
  read (below).

**The book.** `band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)` on
`build_targets()` and `total_returns`, fit period only. The shorts inside a
window are priced through `evaluate()` (shift(2)).

**The mask.** It is set on decision date t for first filing ≤ t ≤ end. A
filter that stays on until the final filing needs nothing later than t.

**The book**, 2013-06-21 → 2022-12-30 (9.52 years):
- gross 6.21%/yr;
- gross Sharpe 0.95;
- turnover 13.55/yr.

**Cost grid per year** = turnover × c: 67.8 / 203.3 / 406.5bp at 5 / 15 / 30bp.

| events (pre-2023, book live) | windows | short name-days | short P&L | cost, bp/yr | vs 5bp grid (67.8) | vs bare 5bp/yr |
|---|---:|---:|---:|---:|---|---|
| **G6: NAV tender + merger + liquidation** | 4 live (HYT 2013; MHD, MQY 2020–21; PDI 2021) | **4** (PDI only; 0.04% of short name-days) | **−9.09bp total** | **0.95** | far below | below |
| NAV tender (common shares) | 0 (AWF 2003 only, pre-book) | 0 | 0 | 0 | | |
| merger, fund as target | 0 (MQY 1999 only, pre-book) | 0 | 0 | 0 | | |
| liquidation / open-ending | 0 (the 44 leads read: none is a proposal for the fund) | 0 | 0 | 0 | | |
| *context: tenders for PREFERRED shares* | 16 (PIMCO ARPS: PFN 2014; PTY 2015; PCN, PHK 2015; all four 2019, 2023, 2024) | 35 (PHK 2019: 29 days, −90.2bp; PTY 2015: 6 days, −0.2bp) | −90.4bp total | 9.49 | below | above |
| *context: proxy contests* | PFN 2011–14, MHD 2011 | 1 (PFN 2013) | +8.6bp | −0.9 | | |

**CRSP check.** The same G6 shorts priced on CRSP daily total returns give
−9.09bp, identical to the panel.

**The filter's own turnover.** Zeroing those 4 shorts changes turnover by
−0.03/yr. The net gain would be about 1–2bp a year at any cost.

**The proxy and 8-K reading.** None of the 44 leads is a liquidation,
termination or open-ending proposal for the fund. They fall into five kinds:
- risk-factor boilerplate ("may cause a portfolio to liquidate positions");
- the "Conversion to open-end fund" section of every N-14 proxy;
- audit-committee charters ("termination of the independent accountant");
- advisory-contract clauses;
- one 2010 PIMCO joint proxy proposing to liquidate PCM, which is another fund.

**Reading.** **G6 does not pass.** The live book was never short a fund under a
pending NAV tender, target-side merger or liquidation before 2023. The four
acquirer-side merger windows cost 0.95bp a year: immaterial on either reading
of "the cost grid per year".

**Per the plan, build the corporate-action filter as hygiene, with no trial.**
It does not spend the C1 trial (CEF 50→51).

Two observations, neither of which is G6 and neither tested:
- **PIMCO's preferred-share tenders.** These buy auction-rate preferreds below
  liquidation preference, which is accretive to common NAV. PHK's 2019 tender
  coincided with a 29-day short that lost 90bp. That is 9.5bp a year:
  - above a bare 5bp a year;
  - below the turnover-based grid.

  It is one name and one episode. A hygiene filter could include issuer
  tenders of any class at no trial cost.
- **The book was long acquirers in their windows** (HYT, MHD, MQY, PDI) and
  those longs lost 103bp in total. A short-only filter does not touch them.

**Live facts (2023+; counted, not priced).**
- JFR was an acquirer from 2023-01-31 (N-14 8C) to its CRSP completion on
  2023-07-28.
- MHD and MQY were acquirers in the BlackRock muni consolidation, first filed
  on 2025-01-21. It completed in February 2026, outside the fit window.
- The PIMCO funds' preferred tenders recurred in 2023-08 and 2024-03.

## 5. Findings outside the questions

- **CRSP codes some CEF reorganisations as exchanges (331/332), not mergers
  (2xx).** The merger census (`dlstcd // 100 == 2`) therefore misses 16 CEF
  delistings of 2010–22 with an acquirer permno, among them BlackRock's 2013
  high-yield consolidation into HYT (COY, CYE, HYV, HIS, BHY: code 331). The
  merger-pair sample and G1c counts are short by up to that many events. They
  are not added here: that is a census change, for the merger work to decide.
- **EDGAR answers a malformed archive path with HTTP 403 "Access Denied"**, the
  same code it uses for throttling. A float CIK (`1195739.0`) cost twelve
  minutes of back-off before this was found. `filing_txt_url` now validates
  the CIK and the accession.
- **8-K item 1.01 is not a merger signal.** In the three BDC deals here,
  most of the item-1.01 8-Ks in the two years before completion were credit
  facilities. Only the 8-K's own document, read for merger-agreement language,
  separates them.

## 6. Gaps (stated, not filled)

- **93 of 186 deal dates are upper bounds** (the acquirer's N-14). A press
  release before it was not on EDGAR, so the true announcement can be earlier.
  The agent's board and press dates are earlier by 40 days (HIH group) and 10
  days (GGM). Fetching sponsors' press-release archives would close this.
- **The sample is completed deals only** (CRSP merger delistings). Failed or
  withdrawn deals are not in it, which is survivorship in deal completion.
  EDGAR's merger episodes without a CRSP completion could find them; not done.
- **The fund set is not a type certificate.** Its second rule has about 10%
  open-end false positives [U]. Any count of "CEF events" from the episodes
  table should be filtered to listed funds or checked.
- **Liquidation and open-ending are found only by reading**: no form marks
  them. G6's reading covers the 13 spec names; the episodes table has no
  liquidation kind.
- **G6's PDI window starts at PDI's N-14 8C** (2021-05-11). Neither target
  (PKO, PCI) filed a 425, so an earlier PIMCO announcement, if there was one,
  is not on EDGAR.
- **The name matcher was checked on this sample and on the agent's 13 groups,
  not against a labelled CIK list.** Each dating filing must name the target in
  its own text, which bounds the damage of a wrong match. The matched CIKs
  are in the gitignored per-deal file for review.
- **G1b (the ex-ante NAV gap) still needs plan 0.8**, which these CIKs now
  enable.

## 7. Files

- `scripts/data/edgar_client.py`: the client (rate limit, headers, back-off,
  cache, URL validation).
- `scripts/data/fetch_edgar_events.py`: the fetcher.
- `scripts/data/tests/test_edgar.py`: tests (registered in `pytest.ini`).
- `scripts/events/edgar_merger_dates.py`: (a), the dates.
- `scripts/events/merger_pairs.py`, extended visibly:
  - `_announcement_row`, shared by both date sources;
  - `pairable_events`;
  - `announcement_sample_edgar`, `edgar_report`, `clustered_t`, `grid_table`;
  - `--edgar-dates`.

  `merger_summary.json` is byte-identical with and without the extension.
- `scripts/events/g6_corporate_action_shorts.py`: (b).
- `scripts/events/tests/test_edgar_event_methods.py`: tests.
- **Tracked outputs:**
  - `edgar_events_summary.json`;
  - `edgar_cef_bdc_episodes.csv` (EDGAR only);
  - `merger_edgar_dates_summary.json`;
  - `merger_ann_edgar_summary.json`;
  - `g6/g6_summary.json`.
- **Gitignored:**
  - `edgar_cef_bdc_filings.csv.gz` (rebuilt `--offline`);
  - `merger_edgar_dates.csv`, `merger_ann_sample_edgar.csv` and
    `g6/g6_events_13_names.csv` (CRSP-joined);
  - `_cache_edgar/`.
- Sources: `docs/REFERENCES.md` §12g.
