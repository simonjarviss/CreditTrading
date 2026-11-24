# SPAC trust-value census (special situations, job 4) — 2026-10-15

**What this is.** The zero-trial census the team lead asked for on 2026-10-15
(special-situations sprint, job 4 of 6). The trade it sizes: buy a SPAC's common
below its per-share trust value, long only, and get the trust back by redeeming
at a vote or when the SPAC liquidates at its deadline. The trust sits in T-bills
or a government money fund, so the floor is defined and nothing is borrowed.
This note counts the SPACs, reads how redemption works in their filings and at
Alpaca, measures the discount and the yield the terms imply, sizes the capacity,
and proposes a gate.

**Zero trials. EVENTS stays where it is.** No return of any trade is computed.
The live section compares today's price with the trust per share. The historical
section measures **levels only**: a price and a trust per share on one date,
before 2023-01-01. Whether a position bought then was in fact redeemed, and at
what, is the trial, and nothing here reads it. CRSP is never read past
2022-12-31, and the script raises if a row past that date comes back. The
27-name CEF set is not touched.

**Reproduce.**

```bash
export QUANTT_ENV_FILE=/abs/path/config/.env    # SEC_USER_AGENT, the cef Alpaca key, R2: read, never printed
python3 scripts/events/spac_trust_census.py --frozen    # this note: the 2026-10-15 snapshot, fetching only what is missing
python3 scripts/events/spac_trust_census.py --offline   # the same, from the caches alone
python3 -m pytest scripts/events/tests/test_spac_trust_census.py
```

Outputs, all under `results/events/`:

- `spac/spac_trust_census_universe_2026-10-15.csv`: one row per SPAC, 1,489 rows. Each
  row records which rule admitted it, its dates, its status (from forms and from
  text) and its Alpaca common.
- `spac/spac_trust_census_years_2026-10-15.csv`: the per-year table in §1.
- `spac/spac_trust_census_live_2026-10-15.csv`: one row per live or delisted-but-filing
  SPAC (345 rows). Columns: trust per share with every source beside it,
  deadlines, Alpaca listing and ADV, discount, yields, the accrual model's
  columns, and the screens.
- `spac/spac_trust_census_summary_2026-10-15.json`: every figure in this note.
- The CRSP rows behind §3.2 stay in the gitignored `_cache_spac/` (CRSP is
  licensed and this repository is public).

The mechanics (§2) are coded with their quotes in `scripts/events/spac_mechanics.py`.
**On every run the census re-fetches each cited filing and verifies each quote,
raising on a miss: 48 quotes from 20 filings of the 15 sampled SPACs.**

**Data dates.**

| source | coverage |
|---|---|
| EDGAR SIC-6770 company browse | read 2026-10-15T20:24Z |
| EDGAR quarterly full indexes (424B4) | 2014-Q1 → 2026-Q4; the 2026-Q4 index read 2026-10-16T01:27Z |
| EDGAR bulk `submissions.zip` / `companyfacts.zip` | read 2026-10-15T20:33Z / 20:34Z (the SEC rebuilds both nightly) |
| EDGAR filing documents | cache first; read 2026-10-15/16, plus 591 missing filings read 2026-10-18 (§7) |
| Alpaca `GET /v2/assets` (cef paper key) | read 2026-10-16T01:06Z |
| Alpaca daily SIP bars, raw | 63 sessions, **2026-07-20 → 2026-10-15** |
| CRSP `dsf`, `dsenames`, `stkdelists` (R2) | 2014-01-01 → **2022-12-31**, never later |
| FRED DTB3, the 3-month bill | to **2026-10-14** (4.10%), read 2026-10-16T01:21Z |
| Ritter, *SPAC IPOs*, Table 15b | updated 2026-10-05; fetched 2026-10-15 |
| Alpaca documentation and fee schedule; Federal Register; Klausner et al. | fetched 2026-10-18 |

**Sources** are in `docs/REFERENCES.md` §12ac (a provisional number; the
coordinator renumbers it at merge).

**Labels.** Census counts and levels are [V]: our own method, re-run on the cited
sources. That vouches for the method's output, not for the world beyond it; the
known misses are listed in §7. Figures from the **accrual model** (§3.1) are
marked **[model]**. They assume the trust keeps earning the bill rate, gross of
the taxes and withdrawals a trust pays out of interest, so they are an upper
bound. Outside facts carry [V] (read on the fetched page), [S] (summary only) or
[U] (unknown).

---

## 0. The answer

- **Live today: 298 SPACs. 288 have a tradable common at Alpaca**: Nasdaq 244,
  NYSE 42, NYSE American 2 (Alpaca's label is `AMEX`). Nine have no common share
  at Alpaca. One, QETA, is listed there as OTC and is not tradable. Another 47
  SPACs have delisted but still file 10-Qs.
- **Typical discount: −0.58% against the trust last reported** (median, all 288).
  67% of them trade below that trust [V]. The reported trust is the June 30
  balance sheet for most, so it is **107 days stale**. Accrued at the bill rate,
  the redeemable pool's median is **−1.63%, and 90% trade below** [model].
- **Typical yield.** Assume no interest is earned after the report. Then the
  annualised yield to the next deadline is **+0.67%** (median, 274 priced in the
  pool) [V]. If the trust keeps earning the bill rate, the total yield is
  **6.14%**. That is a **spread of +2.04%/yr over the 3-month bill (4.10%)**
  [model]. The spread survives the cost grid: **+1.99 / +1.86 / +1.67%** at
  5 / 15 / 30bp. It does not change sign.
- **Near the deadline (next deadline within 6 months, 61 names)**, the market
  closes the gap to the reported trust: the median is **+0.30%**, a premium.
  Against the accrued trust the median is −0.82% and the spread is +3.20%
  [model].
- **Redemption at Alpaca.**
  - **At the deadline: yes, according to the documentation.** Alpaca's
    mandatory-actions page names "Final Liquidation" and says it "is usually
    done on SPACs". A street-name holder "will not need to take any action"
    (Social Capital Hedosophia IV's liquidation 8-K). There is no fee.
    [V] docs; [U] practice.
  - **At a vote: not documented.** Redemption at a vote is a voluntary
    election. Alpaca lists voluntary event types and **SPAC redemption is not
    one of them**. If offered, it costs **$100 per unique election**: Alpaca
    Securities' fee schedule, revised 2026-10-12. [V] fee; [U] availability.
  - **The $100 figure in REFERENCES §12k is confirmed, and it applies to
    Trading API accounts.** The fee schedule is Alpaca Securities' own.
  - **What paper does with either event is unknown** [U].
- **Capacity is small and lumpy.** A buyer is assumed to take 10% of ADV for 20
  sessions. SPAC volume arrives in a few large prints: the median name trades
  on 37 of 63 sessions, and 93 of the 288 have a median daily volume of zero.
  - **All below reported trust (188 names):** about **$12.8M** on median daily
    volume, for a one-off gain of about **$94k**. The mean daily volume gives
    $163M and $1.39M.
  - **Near the deadline and below the reported trust (14 names):** about
    **$0.75M**, for **$6k**.
  - A $100 election is repaid only at positions above **$11,250** (median
    name).
- **Gate verdict: NOT PASSED. Proposed gate G-SPAC, §5, for the team lead.**
  - **Blocking: G-S1, the redemption plumbing.** Nothing Alpaca publishes says a
    Trading API account can redeem at a SPAC vote. Nothing says what paper does
    with a SPAC liquidation.
  - **The economics pass on the model:** G-S2 (edge over cash after the cost
    grid) and G-S4 (history in both eras).
  - **G-S3 (capacity) is the team lead's sizing call.**
  - **What would be tested is about +2%/yr over bills, gross of trust taxes.**
    A trial would spend one **EVENTS** trial. Its bar is √(2 ln N) at the EVENTS
    count when it is registered.

---

## 1. Universe

### 1.1 Who is a SPAC, and how the census found them

SIC 6770 is the SEC's code for blank checks, but **it is the code a company has
today**. A SPAC that completed its deal usually takes the operating company's
code. A SIC-6770 list alone would therefore drop most completed deals, which is
survivorship. The census takes two sets of candidates:

- **3,347 CIKs** with SIC 6770 today;
- **4,704 CIKs** that filed a 424B4 (a final IPO prospectus) from 2014 on.

Their union is **7,125 candidates**. A candidate is a SPAC if both hold:

1. Its first 424B4 is dated 2010 or later.
2. That prospectus is a trust-account IPO prospectus: it names an IPO and a
   trust account on its cover, and mentions the trust account and a business
   combination at least five times each. A trust-funded XBRL balance sheet
   (trust ≥ 90% of assets within three years of the IPO) also qualifies.

**1,489 SPACs pass.** 1,484 pass on the prospectus cover; 5 pass on XBRL alone.

Each SPAC's life is dated from its forms (`spac_events`):

- **IPO:** its first 424B4.
- **Deal announced:** its first 425.
- **Deal completed:** its first 8-K with item 2.01 or 5.06.
- **Delisted:** its first 25-NSE, 25 or 15.

**568 delisted with no completion 8-K.** The text of their last 8-Ks sorts them:

- **365 liquidated**;
- **80 completed** into a new holding company, which reports under its own CIK;
- **123 unclassified**, reported as such and never guessed.

Today's status of all 1,489:

| status | n |
|---|---|
| completed | 598 |
| liquidated | 365 |
| live | 298 |
| unclassified (delisted, text inconclusive) | 123 |
| dormant (stopped filing, no delisting form) | 58 |
| delisted but still filing | 47 |

**Cross-check against CRSP's delisting codes** (linked SPACs only, CRSP
delisting within 30 days of ours; code meanings read from the codes themselves,
not from the CRSP manual, so [U]):

- **`GLI`, read as liquidation:** we call **303 liquidated, 0 completed**. 11 are
  unclassified, 1 delisted-but-filing and 1 dormant.
- **`MER`, merger:** we call **128 completed, 7 liquidated** and 22 unclassified.
- So the two sources disagree on 7 of the 438 SPACs both of them classify. 33
  more are unclassified by us.
- **`GDR`, other delistings:** 41 SPACs, spread across every status. They are
  not used in the check.

### 1.2 Per year, 2015–2026

Dates come from the forms. "Extension votes" are 8-Ks with item 5.07, before any
completion, whose text proposes to extend the deadline. The rule recognises an
extension only by the proposal's own name or by the charter wording; a looser
rule caught deal-vote boilerplate. **Ritter**'s columns are his Table 15b SPAC
IPOs and Table 15c deSPACs by merger year [V, fetched]. "Live at year end"
counts SPACs that had IPO'd and not yet completed or delisted.

| year | IPOs | Ritter IPOs | deals announced | deals completed | Ritter deSPACs | liquidations | delisted, unclassified | extension votes | SPACs with one | live at year end |
|---|---|---|---|---|---|---|---|---|---|---|
| 2015 | 19 | 20 | 3 | 4 | 9 | 0 | 2 | 4 | 3 | 26 |
| 2016 | 12 | 13 | 8 | 6 | 9 | 2 | 1 | 8 | 8 | 29 |
| 2017 | 34 | 34 | 9 | 10 | 13 | 2 | 1 | 15 | 11 | 49 |
| 2018 | 44 | 46 | 10 | 19 | 23 | 2 | 1 | 17 | 12 | 70 |
| 2019 | 55 | 59 | 27 | 25 | 25 | 4 | 3 | 20 | 14 | 91 |
| 2020 | 246 | 248 | 71 | 44 | 64 | 2 | 7 | 55 | 29 | 279 |
| 2021 | 596 | 613 | 250 | 187 | 198 | 1 | 8 | 30 | 21 | 676 |
| 2022 | 82 | 86 | 162 | 93 | 102 | 131 | 22 | 149 | 126 | 491 |
| 2023 | 32 | 31 | 140 | 87 | 98 | 170 | 16 | 419 | 300 | 234 |
| 2024 | 54 | 57 | 56 | 66 | 73 | 32 | 21 | 189 | 148 | 151 |
| 2025 | 141 | 144 | 70 | 26 | 43 | 9 | 25 | 58 | 47 | 197 |
| 2026 to 10-15 | 149 | 153 (Q1–Q3) | 75 | 28 | — | 8 | 11 | 38 | 34 | **298 today** |

- **IPOs track Ritter.** Over 2015–2025 ours are 1,315 against his 1,351
  (97%). By year they run from 92% (2016) to 103% (2023). 2026 through Q3:
  ours 146, his 153.
- **Completions run below Ritter's deSPACs**: 44 of 64 in 2020, 26 of 43 in
  2025. The shortfall is where completions are hard to see from the SPAC's own
  forms:
  - deals that closed into a new holding company but left no text we read;
  - 2025's 25 unclassified delistings;
  - pre-2014 IPOs, which the 424B4 route does not reach before 2014.
  The completion column is therefore a **floor**.
- **The liquidation wave is 2022–2023** (131 and 170), after the 2021 IPO
  boom. So is the extension wave: **419 extension votes at 300 SPACs in 2023**.
- In all, **518 SPACs held 1,003 dated extension votes**.

### 1.3 Today's live SPACs at Alpaca

All 298 live SPACs IPO'd from 2023 on: 4 in 2023, 31 in 2024, 118 in 2025 and
145 in 2026. 250 give EDGAR the state code E9 (Cayman Islands) [S]. Their base
windows, read from the latest 10-Q or else the prospectus, run 9–36 months; the
mode is 24.

- **288 have a tradable common** at Alpaca.
- **Not on Alpaca (10):** nine whose common Alpaca does not list (why is [U];
  units that have not separated are one possibility), and QETA, which Alpaca
  lists as OTC, not tradable.
- **ADV, 63 sessions to 2026-10-15** (Alpaca SIP bars; a session with no bar
  counts as zero):

| per name | p10 | median | p90 |
|---|---|---|---|
| mean daily $ volume | $78k | **$314k** | $856k |
| median daily $ volume | $0 | **$3.5k** | $128k |
| sessions with a print, of 63 | 22 | 37 | 59 |

**The mean is the wrong number to size on.** A SPAC's volume comes in a few
block-sized days. 93 of the 288 traded on fewer than half the sessions.

---

## 2. Mechanics

### 2.1 The declared sample

The order was fixed before any document was read: sha256 of
`"spac-census-2026-10-15:<cik>"` (`declared_order`). The first in that order
were drawn from each group:

| group (status from forms) | drawn | CIKs |
|---|---|---|
| live, Alpaca-tradable common | 6 | RRE Ventures (2123969), JATT II (2112446), Inflection Point VI (2102041), Bain Capital GSS (2064355), Maywood 2 (2080087), Blue Water III (2050501) |
| completed before 2023 | 3 | Cerberus Telecom (1824577), ChaSerg (1743725), InterPrivate (1789029) |
| liquidated before 2023 | 3 | CHP Merger (1785041), Social Capital Hedosophia IV (1818876), VectoIQ II (1823884) |
| had a text-confirmed extension vote | 4 | CHP Merger, Iron Horse (1901203), Zalatoris II (1853397), Aurora / Better Home (1835856) |

**One disclosed change.** The first extension draw admitted Cerberus Telecom.
Its 8-K turned out to be a deal vote that only mentioned "the potential failure
to obtain an extension". The rule was tightened because it had misclassified,
and the four were redrawn. The rule was not tightened because of what the drawn
SPAC said. Cerberus is still in the sample as the first completed SPAC. The
script recomputes the draw on every run and raises if a quote cites a CIK
outside it. **All 15 SPACs are cited.**

### 2.2 What the filings say

Each quote below is in `spac_mechanics.py`, checked against its filing on every
run.

**Trust per share at the IPO, and interest.**

- **The deposit.** RRE: "$250.0 million … ($10.00 per unit in either case),
  will be placed into a U.S.-based trust account". Across the 1,489, the
  prospectus deposit has a median of **$10.00** in every era. The mean is
  $10.05 for 2010–19, $10.06 for 2020–22 and $10.02 for 2023–26.
- **What the trust may hold.** RRE: "cash, U.S. government treasury obligations
  with a maturity of 185 days or less, or in money market funds meeting certain
  conditions under Rule 2a-7". JATT II also allows a bank demand-deposit
  account.
- **What comes out of the interest before a holder is paid.**
  - **Taxes:** "net of taxes payable" (RRE); "net of amounts withdrawn to pay
    our taxes" (Blue Water III).
  - **Dissolution expenses:** "up to $100,000 of interest".
  - **Working capital, at some SPACs:** Inflection Point VI may withdraw
    "subject to an annual limit of $500,000".
  - **Third-party claims** can push the trust below "the lesser of (i) $10.00
    per public share and (ii) the actual amount per public share held in the
    trust account" (CHP's proxy).
  - **The excise tax on redemptions** "is imposed on the repurchasing
    corporation itself, not its shareholders" (Aurora's proxy, 2023).

**Redemption rights and deadlines.**

- **Deadlines:** RRE 24 months; ChaSerg 18; InterPrivate 21; Cerberus 24. Bain
  GSS runs 24 months, or 27 "if we have executed a letter of intent …": an
  extension needing no vote. JATT II allows "such other time period pursuant
  to an amendment".
- **At the deadline:** RRE will "redeem 100% of the public shares at a per
  share price, payable in cash, equal to the aggregate amount then on deposit
  in the trust account, including interest earned thereon".
- **At a deal vote:** the trust is valued "as of two business days prior to
  the consummation".

**Extension votes and their sweeteners.**

- **A vote is a redemption window, priced at the trust.**
  - CHP's 2021 extension (to May 26, 2022): holders of **11,388,997 shares
    redeemed at about $10.06**.
  - Aurora's 2023 vote: **25,751,449 shares at $10.2178**.
  - Zalatoris II's 2024 vote: about **$11.15**.
- **Sweeteners paid by the sponsor into the trust.**
  - Zalatoris II: "the lesser of (x) $75,000 or (y) $0.025 per share for each
    Public Share outstanding … for each such Extension".
  - Iron Horse: "up to twelve (12) times on a month-to-month basis … by
    depositing the Extension Payment into the Trust Account". **A
    sponsor-deposit extension needs no holder vote, so it opens no redemption
    window.** See §4.3.
- **A holder who does not redeem keeps the right** to redeem at the deal or at
  the extended date (Zalatoris II).
- **The price beside the trust on each proxy's date:**

| proxy | close | redemption value |
|---|---|---|
| CHP 2021 | $10.05 | about $10.06 |
| Zalatoris II 2023 | $10.37 | $10.37 |
| Zalatoris II 2024 | $10.96 | $11.09 |
| Aurora 2023 | $10.17 | $10.2178 |

**Whether a holder must own by the record date: no.**

- RRE and Maywood 2: holders may redeem "irrespective of whether they vote for
  or against … or whether they were a public shareholder on the record date".
- JATT II says the same: "regardless of whether they hold public shares on the
  record date".
- CHP (2019): holders "may elect to redeem their public shares without voting".
- Caps:
  - **holder caps** of 15% (RRE) and 20% (JATT II) of the shares sold;
  - older SPACs also had a **net-tangible-assets floor** of $5,000,001 (CHP).

**The mechanics at a retail broker.**

- **At a vote, the holder must act through the broker.** RRE: "deliver their
  shares to our transfer agent electronically using the Depository Trust
  Company's DWAC … system … up to two business days prior to the scheduled
  vote". Iron Horse: tender "AT LEAST TWO BUSINESS DAYS PRIOR TO THE INITIALLY
  SCHEDULED VOTE … YOU NEED TO IDENTIFY YOURSELF AS A BENEFICIAL HOLDER".
- **The transfer agent charges the broker** "approximately $100" (RRE, Maywood
  2) or $80 (Bain GSS, ChaSerg). It is "up to the broker whether or not to pass
  this cost on".
- **At a liquidation, the holder does nothing.** Social Capital Hedosophia IV,
  2022: "Beneficial owners of the Public Shares held in 'street name,' will not
  need to take any action". The estimated payout was "approximately $10.01" a
  share, and "the Company's warrants … will expire worthless".
- **A liquidation can come early.** VectoIQ II redeemed in December 2022,
  "because the Company will not consummate an initial business combination
  within the time period required by its Charter".

### 2.3 Alpaca: can the shares be redeemed, and what does it cost

| question | answer | source | status |
|---|---|---|---|
| Liquidation at the deadline | A **mandatory** action: "Final Liquidation – … the shareholders of a company receive cash and the underlying shares are removed. This is usually done on SPACs or securities such as CVRs and escrow shares." No election, no voluntary fee. | docs, mandatory-corporate-actions (updated 2026-07-08) | [V] doc; [U] practice |
| Redemption at a vote | A holder election, so a **voluntary** action. Alpaca "works with a third party vendor"; each customer gets an e-mail "with details and instructions"; the FAQ says clients receive "a link that allows them to make an election". The documented types: Dutch auction / purchase / tender offer, conversion / exchange offer, election merger, consent request, rights offer, warrant exercise. **SPAC redemption is not named.** Notifications "will NOT be sent out … where the underlying company does not provide the necessary information to our third party". | docs, voluntary-corporate-actions (Broker API, updated 2025-09-24); support FAQ (March 2025) | [V] pages; **[U] whether SPAC redemptions are offered** |
| Cost of an election | **"Voluntary Corporate Actions Processing — $100 per unique election"** in Alpaca Securities' fee schedule, revised 2026-10-12. The Broker API FAQ says "$100 per client per voluntary corporate action". Unit splits carry "the $100.00 voluntary submission fee". **This confirms REFERENCES §12k and settles its [U] for Trading API accounts.** | `files.alpaca.markets/disclosures/library/BrokFeeSched.pdf`; docs as above | [V] |
| Other fees near the trade | DWAC transfers cost $150 per security, a DWAC reject $100. These are position-transfer fees. Whether any is charged on a redemption tender is not stated. | same fee schedule | [V] fee; [U] applicability |
| Timing of the cash | Elected shares move to a "contra" security; cash is booked "once we receive the allocation from DTC (which is normally a week or two after the client's election is submitted)" | docs, voluntary-corporate-actions | [V] |
| Paper account | The paper page lists what paper "does not account for", dividends among them. It is silent on corporate actions. **Whether paper processes a SPAC liquidation or offers an election is unknown.** | docs, paper-trading (updated 2026-07-07) | [U] |

**So: at the deadline, yes per the documentation, and free. At a vote, not
documented; $100 per election if offered.**

---

## 3. Terms-implied discount and yield

### 3.1 Today's live SPACs (as of the 2026-10-15 close)

**Trust per share** comes from the latest 10-Q or 10-K, by the balance-sheet
identity (`pick_trust_ps`). The temporary-equity line prints N shares at P a
share, worth A. The printed P is used when N × P is within 1% of the XBRL
amount A for some count N read. Otherwise the census uses A over the printed N.

Each single source fails somewhere, measured on 2026-10-18:

- **an XBRL or loosely matched share count** that was an accretion amount
  (WLCO);
- **a printed "$10.00 per share" label** beside $10.23 of value (CRAC);
- **the prior period printed first** (MMTX).

The headline sources, by count:

| source | n |
|---|---|
| printed P, checked | 195 |
| amount over printed shares | 43 |
| prospectus deposit (balance sheet before the IPO) | 33 |
| XBRL per-share price, checked | 12 |
| unchecked | 5 |

4 rows have sources more than 1% apart. All of them are flagged in the CSV.

**Two screens, applied before any statistic.**

- **The redemption window may already have closed.** 7 SPACs have held their
  deal vote, and with it passed the redemption deadline that preceded it:

| symbol | vs reported trust | deal vote |
|---|---|---|
| BKHA | −44.0% | 2026-10-13 |
| RIBB | −42.5% | 2026-09-11 |
| RDAC | −52.2% | 2025-11-24 |
| ALIS | −12.9% | 2026-10-08 |
| FVN | −13.1% | 2026-07-27 |
| RFAI | +206.9% | 2026-08-20 |
| AFJK | +4.2% | 2025-11-12 |

  Their unredeemed shares ride the merger, not the trust, so they are taken out
  of the **redeemable pool** (281 names).
- **A 5% gap screen.** No one leaves a gap that wide on a T-bill trust unless
  the right is gone or the figure is wrong. In the pool it catches one name:
  **ATII, −16.6%**, which filed its merger proxy on 2026-09-24. It stays in the
  statistics and is kept out of the capacity sums.
  - The 5% was set **after** the extreme rows had been seen. Any screen from
    2.3% to 16.6% catches the same row, so the choice moves nothing.

**The accrual model [model].** Most reported trusts are as of 2026-06-30, 107
days before the census date. The trust keeps earning, so the model:

1. accrues the trust at the mean DTB3 from the balance sheet (or the IPO, for
   the 33 pre-IPO balance sheets) to 2026-10-15;
2. accrues it again to the deadline at the last DTB3 (4.10%, 2026-10-14);
3. reports the total yield and its **spread over the bill**.

The spread is the part that is not cash: what a long-only sleeve would earn
beyond holding the bill. It is **gross of trust taxes and withdrawals**, so it
overstates. The headline stays on the **reported** trust, as the brief asks.

**Redeemable pool, medians** (n = 281; 274 have a deadline after today):

| | n | vs reported trust | below it | vs accrued trust [model] | yield to next deadline, no further interest | spread over bills to next deadline [model] |
|---|---|---|---|---|---|---|
| all | 281 | **−0.58%** | 67% | **−1.63%** | **+0.67%** | **+2.04%** |
| deal announced | 79 | +0.19% | 39% | −1.02% | −0.37% | +2.07% |
| not announced | 202 | −0.69% | 78% | −1.79% | +0.81% | +2.04% |
| next deadline ≤ 6 months | 61 | **+0.30%** | 25% | −0.82% | −1.09% | **+3.20%** |

- **Quantiles, all 281.** Against the reported trust: p10 −1.48%, p90 +1.20%.
  Against the accrued trust: p10 −2.51%, p90 −0.18% [model]. The spread to the
  next deadline: p10 +0.22%, p90 +3.64%.
- **The total yield** to the next deadline has a median of 6.14% [model].
- **To the latest deadline any filing allows**, the spread's median is +1.93%.

**After the desk's cost grid** (one buy, spread over the days to the next
deadline; no sale, because the exit is the redemption):

| | gross | 5bp | 15bp | 30bp |
|---|---|---|---|---|
| spread over bills, pool [model] | +2.04% (90% > 0) | +1.99% | +1.86% | **+1.67%** (87% > 0) |
| spread over bills, ≤ 6 months [model] | +3.20% (80%) | +3.07% | +2.20% | +1.61% (70%) |
| yield at reported trust, pool | +0.67% (69%) | +0.60% | +0.47% | +0.30% (59%) |
| yield at reported trust, ≤ 6 months | −1.09% (25%) | −1.27% | −1.57% | −2.16% (23%) |

- **The spread over bills does not change sign across the grid.**
- **The no-further-interest yield near the deadline is negative even gross.**
  Near the deadline the market prices in the interest earned since the last
  report. A reader who ignores accrual will see no trade there; a reader who
  trusts the model will see +2–3%/yr. **Which is right is the Q3 10-Q's trust
  figure, due in November, not a judgement.**
- **The vote route adds the $100 election.** For the median below-trust name,
  that is repaid at positions above **$11,250** at the reported trust, or
  $5,783 at the accrued trust.
- **The 14 names below the reported trust with a deadline inside 6 months** are
  in the live CSV; ILLU is the deepest, at −2.06%.
  - **A stated "next deadline" is the earliest date in a filing.** It is not
    a promise of a redemption window (§4.3).
  - **OACC** shows a +54.9% spread to a deadline 10 days away. Read: a vote or
    an extension is pending.

### 3.2 History, before 2023: discount levels at fixed points before the base deadline

**Method.**

- **The SPACs.** 1,097 SPACs IPO'd 2014–2022. **1,085 are linked to a CRSP
  common** by name and listing date (unique best match, score ≥ 0.75, no ties).
- **The fixed point.** For each, the IPO date plus the base window minus 6, 3
  or 1 months. Only SPACs still alive on that date count, and only fixed points
  before 2023-01-01.
- **The trust per share** is the prospectus deposit × V(t)/V(t1). V is assets
  held in trust from XBRL balance sheets **filed by the fixed point**, so
  nothing comes from after it. A ratio outside 0.98–1.10 means redemptions or
  deposits moved the trust, and the row is refused rather than guessed.
- **The price** is the CRSP close on or before the fixed point. When nothing
  traded, CRSP gives the bid/ask midpoint, and the row is flagged.

| months before the base deadline | alive | measured | vs last known trust: median | p10 / p90 | below it | vs accrued trust [model] | spread over bills [model] |
|---|---|---|---|---|---|---|---|
| 6 | 761 | 635 | **−1.32%** | −1.88% / +0.18% | 89% | −1.72% | +3.53% |
| **3 (headline)** | 562 | 500 | **−0.59%** | −1.11% / +0.29% | **83%** | −1.06% | +4.33% |
| 1 | 351 | 304 | **−0.16%** | −1.20% / +1.00% | 60% | −0.59% | +7.07% |

- **Why rows are missing.** At 3 months, 54 rows have no trust balance filed
  yet and 8 had their trust moved.
- **Quote midpoints.** 141 of the 562 prices at 3 months are CRSP quote
  midpoints (no trade that day): 207 at 6 months and 83 at 1 month.
- **By era, at 3 months (H5).**

| era | n | vs last known trust: median | below it | vs accrued trust: median | below it |
|---|---|---|---|---|---|
| 2015–19 | 50 | −0.16% | 60% | −0.57% | 88% |
| 2020–22 | 450 | −0.60% | 85% | −1.08% | 93% |

- **By year** (median vs last known trust; share below it):

| year | n | median | below it |
|---|---|---|---|
| 2018 | 13 | −0.57% | 77% |
| 2019 | 22 | +0.23% | 23% |
| 2020 | 24 | +0.73% | 29% |
| 2021 | 43 | −0.65% | 79% |
| 2022 | 383 | −0.62% | 90% |

  **2022 is three-quarters of the sample.** 2019–2020 traded at a premium: deal
  hopes during the boom. The 2015–17 cells hold 15 rows between them.
- **Deal status at 3 months:** announced −0.51% (77% below, 132 rows); not
  announced −0.61% (85%, 368 rows).
- **The pull to trust.** The discount narrows as the deadline nears: −1.32% at
  6 months, −0.59% at 3 and −0.16% at 1. The three fixed points are not the
  same SPACs, so this describes levels, not a path, and no return is implied.

---

## 4. Capacity, counterparty and risks

### 4.1 Capacity

The convention is stated, not fitted: **10% of ADV for 20 sessions** per name,
in the redeemable pool, outside the gap screen.

| set | names | capacity, median ADV | one-off gain, median ADV | capacity, mean ADV | one-off gain, mean ADV |
|---|---|---|---|---|---|
| below reported trust | 188 | **$12.8M** | **$94k** | $163M | $1.39M |
| … with next deadline ≤ 6 months | 14 | **$0.75M** | **$6k** | $10.2M | $98k |
| below accrued trust [model] | 246 | $17.9M | $279k | $216M | $3.53M |
| … with next deadline ≤ 6 months [model] | 48 | $3.4M | $32k | $48.4M | $427k |

- **Within 6 months, the median name trades $307k a day on average but $5k on
  the median day.** So a position is accumulated in someone else's block, not
  in the tape.
- **74 of the 188 names** have enough median-ADV capacity to repay one $100
  election.

### 4.2 Who sells below trust, and why

What the literature says. Klausner, Ohlrogge and Ruan, *A Sober Look at SPACs*,
Yale J. on Reg. 39:228 (2022), on the 2019–20 cohort [V, fetched]:

- **Who holds at the IPO.** Investors in SPAC IPOs are "almost entirely large
  institutional investment managers affiliated with hedge funds".
- **They do not mean to stay.** A repeat group, the "SPAC Mafia", invests "with
  little intention of remaining invested through the merger".
- **Nearly all of them leave.** IPO investors "redeem or sell their shares by
  the time of a SPAC's merger". Mean and median redemption at the merger were
  58% and 73%.
- **What they earn, and from where.** Redeeming IPO investors "reaped an 11.6%
  annualized return … This return was primarily attributable to the free
  warrants and rights given to IPO investors."

The inference, [U]: **the seller is the IPO buyer**.

- The IPO buyer's return is in the warrant and the right.
- Once the units separate, the bare share is a T-bill with a lock-up to the
  next deadline.
- Selling it a little below trust frees capital for the next IPO, where the
  free warrants are. That is the warrant-stripped seller the brief names.
- In our data the discount is deepest where there is no deal (−0.69% against
  +0.19% with a deal announced). That fits holders who want out of a dead
  share and not of an option.

**Not measured here, [U]:** tax-loss selling (a December effect), SPAC-ETF or
index exits, and redemption-cap holders (15–20%) selling the excess. Each can be
tested on pre-2023 levels without spending a trial: for instance, the discount
by calendar month. None was run.

### 4.3 Risks

1. **The redemption window closes before the deal.** The window shuts up to two
   business days before the vote.
   - **Five live names** whose deal vote has passed sit **13–52% below** the
     trust: BKHA, RIBB, RDAC, ALIS and FVN.
   - **ATII** has filed its merger proxy and sits 16.6% below.
   - Each is listed in §3.1. A position held past the window is an equity bet
     on the target.
2. **Extension without redemption.** Some extensions need no vote:
   - Bain GSS: 27 months automatically with a letter of intent;
   - Iron Horse: monthly sponsor deposits, "up to twelve (12) times";
   - JATT II: "such other time period pursuant to an amendment".
   These open no redemption window. The stated deadline is then not an exit,
   and the yield falls with every month added.
3. **Trust shortfall.** Taxes, up to $100,000 for dissolution, working-capital
   draws (up to $500,000 a year at Inflection Point VI), and third-party claims
   beyond the sponsor's indemnity (CHP) all come out before holders. The census
   headline uses the reported trust, which is already net of past withdrawals.
   The accrual model is gross of future ones.
4. **Delisting before redemption.**
   - **Nasdaq:** a SPAC that has not completed a deal "within 36 months of the
     effectiveness of its IPO registration statement" faces immediate
     suspension, and **a hearing request "shall not stay the suspension"**
     (89 FR 58807, 2024-07-19) [V].
   - **NYSE:** filed to allow 42 months with a definitive agreement inside
     three years (89 FR 25291, 2024-04-10). It is a *proposal*; we did not
     check whether it was approved [S].
   - **The live count.** 2 live tradable SPACs already have a deadline beyond
     36 months.
   - **What suspension means for the holder.** The trust is still owed, but the
     share can leave Alpaca's tradable list. QETA, a live SPAC that Alpaca lists
     only as OTC and untradable, shows what the holder then sees.
   - **A listing notice already in hand.** RDAC received a Nasdaq notice on
     2026-08-19 for market value of listed securities below $35M (8-K item
     3.01).
5. **Broker redemption failure.**
   - Alpaca names no SPAC-redemption election.
   - Its vendor sends no notice where the issuer gives it no information.
   - Cash arrives "a week or two" after the election.
   - Each election costs $100.
   - What paper does with any of it is unknown.
   **This is the binding risk** (G-S1).
6. **Paper is not the market.** Paper does not simulate the closing auction
   (CLAUDE.md landmine 1) or dividends. Its corporate-action handling is
   unknown, so a paper trial may never see its exit.

---

## 5. Proposed gate G-SPAC and the counter (a proposal for the team lead)

**Counter.** A SPAC test is a corporate-action trade read from EDGAR, so it
belongs on **EVENTS** (SYSTEM.md §5, 2026-10-09). EVENTS reads **0** on this
branch's table. Siblings may have spent some: read it at merge. This census
spends none. A trial would be **one** EVENTS trial, judged at √(2 ln N) for N at
registration. The 2023 time holdout stays sealed. The pre-2023 realised
redemption proceeds (8-K redemption prices) are the trial's data and are
untouched here.

**Gate.** All four must pass before a pre-registration is written. Each is
re-measured by re-running this script on the day, never read from this note
(H14).

| | test | measured 2026-10-15 | verdict |
|---|---|---|---|
| **G-S1** | **Redemption plumbing, in writing from Alpaca:** (a) a Trading API account can elect redemption at a SPAC vote, with the cut-off against the DWAC deadline and the fee; (b) a deadline liquidation pays cash to street-name holders with no action; (c) what the **paper** account does with (a) and (b). If paper cannot, the trial must say how its exits will be broker-confirmed. | (a) not documented, [U]; fee $100 per election [V]. (b) documented [V]. (c) unknown [U]. | **NOT PASSED (blocking)** |
| **G-S2** | **Edge over cash after the cost grid:** on the redeemable pool, the median spread over the 3-month bill to the next deadline stays > 0 at 5 / 15 / 30bp; with the no-further-interest yield beside it, and the Q3 10-Qs' trust replacing the model before any trade. | +1.99 / +1.86 / +1.67% [model]; no sign flip. No-interest yield +0.60 / +0.47 / +0.30%. | passes on the model |
| **G-S3** | **Capacity:** the near-deadline set (pool, below the accrued trust, ≤ 6 months) has median-ADV capacity at or above the sleeve size the team lead sets; for the vote route, a position per name above the $100 breakeven. | 48 names, $3.4M (median ADV); breakeven $5.8k–$11.3k a name | **the team lead's sizing call** |
| **G-S4** | **History in both eras:** before 2023, most live SPACs traded below the last known trust 3 months before the base deadline, in 2015–19 and in 2020–22 alike. | 60% (n = 50) and 85% (n = 450) | passes |

**Verdict: NOT PASSED.** G-S1 blocks. Two further points for the team lead.

- **The edge.** On the model, what a trial would test is **about +2%/yr over
  bills** (+1.7% after 30bp), on a few million dollars of near-deadline
  capacity.
- **How it squares with the standing rulings.**
  - **"Alpha only; carry is closed"** (2026-10-09): the bill part of the yield
    is carry. Only the spread can count, and whether the spread is a liquidity
    premium (D4) is a question for the trial and for `beta-detector`.
  - **The ≥10%/yr gross target:** unlevered, the sleeve cannot reach it on its
    own.

**What would move G-S1** (team lead's decision; none of it is ours to do):

- a support ticket to Alpaca asking (a)–(c);
- or a paper plumbing test: hold one SPAC whose liquidation is announced
  through its payout date, and see whether paper books the cash.

The second needs an order, so it needs the team lead's explicit go
(CLAUDE.md rule 1).

---

## 6. What this does not show

- **No realised return.** Nothing here shows whether a below-trust purchase was
  redeemed at trust, how often deadlines were extended without a window, or what
  a holder actually received. That is the trial.
- **The accrual model** assumes the bill rate, gross of taxes and withdrawals.
  The Q3 10-Qs (due mid-November) will replace it with reported figures.
- **Paper's corporate-action behaviour and Alpaca's SPAC elections** are
  unknown, not negative.

## 7. Provenance, misses, and what the successor changed

- **Handover.** This census was begun on 2026-10-15 and cut off by a usage
  limit mid-run. It was finished on 2026-10-18 **as of the 2026-10-15
  snapshot**.
  - **`--frozen`** keeps every cached EDGAR document whatever its age. It
    fetches only what is missing: **591 filings** (590 complete submissions
    for the delisted SPACs' text check, and 1 RDAC 8-K). The final run made
    **no** EDGAR request, and its outputs match a run built from the
    intermediate stages byte for byte.
  - The SIC browse, the indexes and the bulk archives were **not** re-read,
    so the live count is the 2026-10-15 count.
- **Kept from the first author:**
  - the candidate route and the SPAC test;
  - event dating, text rules and the sample rule and draw;
  - 39 verified quotes;
  - the CRSP link and the historical method;
  - the Alpaca reads (assets, bars, calendar) and the Ritter benchmark.
- **Changed on 2026-10-18,** each with a test that fails on the old behaviour:
  1. **Trust per share.**
     - **The new rule.** The balance-sheet identity (`pick_trust_ps`) replaces
       "printed value first".
     - **The two regex fixes.** The printed value is now read on four more
       10-Q forms. The share count no longer reads a table row's dollar amount.
     - **What it changed.** InterPrivate V and SUMA had shown 21% discounts on
       a wrong XBRL share count. WLCO would have shown −15.6%.
  2. **Deal votes.** `is_deal_vote_text` is new, and the redeemable pool
     excludes SPACs whose deal vote has passed.
  3. **Liquidation text.** A defined term in parentheses is now read. It was
     missed on the sampled Social Capital Hedosophia IV.
  4. **The accrual model.** `accrued_terms` with FRED DTB3 adds the accrual
     columns, labelled, never the headline.
  5. **The rest.**
     - Capacity on median ADV and the cost grid.
     - The gap screen and its band.
     - Per-era and per-year historical splits; the era map had folded
       pre-2015 into 2015–19.
     - A CRSP guard for 2022 IPOs that first trade in 2023.
     - A non-unique accession index fixed.
     - 9 quotes added: Maywood 2, Social Capital IV, the trust deposit and the
       third-party claims; **48 in all**.
- **Known misses.**
  - 123 delistings are unclassified.
  - Completions are a floor (§1.2).
  - 5 live trust figures are unchecked.
  - The 12 SPACs with no CRSP link are unlinked, never forced.
  - CRSP code meanings are [U].
