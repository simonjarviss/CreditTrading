# Idea card — CEF rights offerings: the fall is real and large, the rebound after expiry is slow and not above its control

**Slug:** `cef_rights_offerings` · **Started:** 2026-11-16, **interrupted** that day (the editor was
force quit about 20 minutes in), **completed 2026-11-18** ·
**Status:** EXPLORE, not promoted. The pre-specified long after expiry is 0.39 gross over 60
sessions (t 1.99) and −0.03 over 20; the same funds a year earlier do almost as well per event.
The strong fact is the other side: the fund loses about 2.5% against the CEF market in the 25
sessions after the ex-rights date (t −6.4, 29% of events positive), which only a short earns ·
**Reproducer:** `QUANTT_ENV_FILE=<env> python3 results/ideas/cef_rights_offerings/stage.py`, then
`explore.py`, `QUANTT_ENV_FILE=<env> python3 …/edgar_expiry.py`, `checks.py` ·
**Panels:** CRSP closed-end funds, dead ones included, daily to **2025-12-31**; CRSP
distributions and closing quotes on R2 to **2025-12-31**; PCEF from Yahoo (2010-02-19 on, cached
copy); EDGAR prospectuses fetched 2026-11-18. Licensed rows are under `~/quantt_research/`, not
in the repository.

## What was on disk after the interruption, and what was done about it

- `stage.py` and the event list (`events.parquet`, 147 rows) existed. `quotes.parquet` was
  **0 bytes** (half-written at the kill) and was rebuilt by re-running `stage.py`; the event
  list came back identical in size and counts.
- **No `explore.py`, no results and no card existed.** So no return had been read. The rule
  below was written on 2026-11-18 before any return was read; only counts, the share of rows
  with a right value and a declaration date, and price, size and dollar volume at the ex-date
  had been looked at. No fix to a pre-specified rule was needed, because there was none.

## The idea

A fund raising money gives holders rights to buy new shares below the market. Holders who do
not want more shares sell, arbitrageurs short the fund against the rights, and the price is
said to recover once the offering closes.

## What was fixed before the test

- **Event:** CRSP distribution rows typed `SECRD` (subscription rights in the fund's own
  shares) on closed-end fund permnos; X is the ex-rights date. 147 events on 85 funds from
  2000; 117 from 2010, **7.3 a year** (6.6 a year eligible) [V].
- **Expiry:** CRSP does not carry it, so the lane's fallback was the rule: **X + 25 sessions**.
- **Trade:** long from the close of X+25 for **60 sessions** (headline) and **20** (beside it);
  decided at the close of X+24, earns X+26 on. Eligible: price ≥ $2 and 21-session dollar
  volume ≥ $500,000 at the decision.
- **Weights and hedge:** +1 split across event funds in a window, −1 across every eligible
  CEF equally; flat when no event is open.
- **Controls:** K1 the same funds 252 sessions earlier; K2 three funds nearest in market value
  with no offering within a year.
- **Checks named in advance:** mid quotes, entry a session later, PCEF as hedge, ordinary
  ex-dates in the window, real expiry dates from EDGAR.
- **Expected:** a fall through the subscription period and +1 to 2% over 20 sessions after it,
  above both controls.

## What it showed (gross, shift(2), no costs) [V]

Calendar-time books, 2000-03 to 2025-12:

| | Sharpe (t) | return / vol | halves | 2002–08 | 2009–15 | 2016–19 | 2020–22 | 2023–25 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **60 sessions, against the CEF market** | **0.39 (1.99)** | 4.9% / 12.5% | 0.51 / 0.24 | 0.69 | −0.37 | 0.87 | −0.03 | 0.80 |
| K1, same funds a year earlier | 0.12 (0.61) | 1.3% / 10.4% | | | | | | |
| K2, size-matched, no offering | −0.12 (−0.61) | −1.2% / 9.7% | | | | | | |
| 60 sessions less K2 | 0.38 (1.92) | 6.0% | | | | | | |
| long leg alone | 0.35 (1.77) | 6.1% / 17.3% | | | | | | |
| **20 sessions, against the CEF market** | **−0.03 (−0.17)** | −0.3% / 9.6% | 0.29 / −0.37 | 0.33 | 0.07 | 0.25 | −1.31 | 0.14 |

The 60-session book holds 1.9 funds on its active days (3,939 of 6,479 sessions), turns over
13.8 times a year, and its worst drawdown is −32%. The 20-session book's is −68%.

Per event, buy and hold, fund less the CEF market (eligible events):

| window (sessions from X) | n | mean | median | positive | t, clustered by month |
|---|---:|---:|---:|---:|---:|
| before, [−20, −1] | 130 | −84bp | −95bp | 44% | −1.8 |
| ex-rights day, [0] | 130 | −180bp | −232bp | 19% | −4.2 |
| **subscription, [1, 25]** | 130 | **−252bp** | **−283bp** | **29%** | **−6.4** |
| after expiry, [26, 45] | 129 | −22bp | −22bp | 47% | −0.4 |
| after expiry, [26, 85] | 122 | +169bp | +98bp | 57% | 2.8 |
| K1 a year earlier, [26, 85] | 80 | +134bp | +261bp | 62% | 1.7 |
| K2 matched, [26, 85] | 319 | −42bp | −22bp | 48% | −0.9 |
| K1 / K2, [1, 25] | 80 / 345 | +64bp / −22bp | +31 / −26bp | 53% / 45% | 1.0 / −0.7 |

All 146 events with no liquidity filter: [1, 25] −261bp (t −6.8), [26, 85] +138bp (t 2.3).

The path (122 events, cumulative, less the market, from X−20): −52bp at X−1, −242bp at X,
−408bp at X+10, −523bp at X+20, **−588bp at X+35** (the low), −380bp at X+60, −291bp at X+85.
The fund is still 3.6% behind the market 85 sessions after the ex-date (t −4.3; not
pre-specified window).

By era, per event: the subscription fall is −296, −349, −294, **−72**, −270bp across the five
eras (2020–22 is the exception); the 60-session rebound is +418, +84, +250, −102, +363bp.

**Transferable or not:** 120 eligible events have a CRSP right value (the right traded) and
10 do not. The 10 are too few to read: [1, 25] −239bp (t −1.5), [26, 85] −51bp. On those 10
CRSP's ex-day return is not adjusted for the right (−678bp), so that figure is not a return.

## Checks named in advance (`checks.py`) [V]

| | result |
|---|---|
| C1 mid quotes | [1, 25] −243bp (t −6.1); [26, 85] +148bp (t 2.4); [26, 45] −34bp. Not a bounce |
| closing spread at entry | median 17bp, 75th percentile 27bp, 90th 43bp (127 events) |
| C2 entry one session later | 60-session book 0.54 (t 2.72); 20-session 0.18. A one-session move changes the Sharpe by 0.15, which is the noise in a book of two funds |
| C3 PCEF as the hedge, from 2010-02 | 0.25 (t 1.00); against the CEF market on the same dates 0.23 (t 0.92) |
| C4 ordinary ex-dates in [26, 85] | 2.15 per event fund against 2.24 per K2 fund; [1, 25] 0.85 against 0.95. The desk's ex-date drift cannot explain either gap |
| C5 real expiry (EDGAR, 112 of 147 events) | the offering runs a median **21 sessions** from X (10th to 90th percentile 17 to 27), so X+25 is about four sessions after the real close. Entry at the first close after the real expiry: 60-session book 0.27 (t 1.38), 20-session 0.15; the fixed rule on the same events 0.28. Per event: +20bp in the first 20 sessions (t 0.5), +196bp over 60 (t 3.0), **+170bp of it in sessions 22 to 61**. X+1 to the real expiry: −295bp (t −6.7, 25% positive) |

## Looked at afterwards (not pre-specified) [V]

- **The fall as a trade.** Short the fund from the close of X to X+25 against the CEF market,
  only where CRSP's declaration date plus one session was at least a session before X (89
  eligible events): **0.71 (t 3.58)**, 6.4% / 9.0%, halves 0.65 / 0.77, eras 0.31, 1.16, 1.15,
  0.01, 0.91; per event −243bp (t −4.9), on mid quotes −234bp. With every event (ex-date
  assumed known for the 39 with no CRSP declaration date [U]): 0.72 (t 3.64), worst drawdown
  −35%. The same book on K2 funds 0.07, on K1 dates −0.10. This was run after seeing the
  per-event table, so it is one more look, not a test.
- **The late rebound.** [46, 85]: event funds +216bp (t 3.8, 67% positive), K1 +99bp (t 1.6),
  K2 −27bp. The window was chosen from the path.
- **The desk's own funds.** 6 of these events are in the core panel's 44 tickers (3 since
  2016); 81 in the wider `data/cef_families` panel (48 since 2016).

## What I conclude

1. **The pre-specified long is not a book.** Nothing in the first 20 sessions after expiry;
   over 60 sessions 0.39 with a t of 2.0, 0.24 in the late half, 0.25 against PCEF from 2010.
   The funds that make rights offerings also beat the CEF market a year earlier by nearly as
   much per event (K1 +134bp against +169bp), so most of the "rebound" may be what these
   funds do anyway. Small capacity is not the problem: median holding trades $1.8M a day at
   $11, median fund $219M.
2. **The fall is the finding.** About 2.5% against the market in 25 sessions, in four of five
   eras, on mid quotes, fifteen times the spread, with both controls flat. It is on top of a
   1.8% loss on the ex-rights day itself that CRSP's right value does not make good.
3. **For a long-only book it is a rule about what not to hold:** a fund should not be bought or
   held between the ex-rights date and about 35 sessions after it. For the core book that is
   rare (3 events in its panel since 2016) but each one costs a few per cent.
4. **As a short book it could be a shadow candidate, subject to borrow.** About 7 events a
   year, 0.7 gross if the short can be had. That is exactly the moment arbitrageurs short the
   fund against the rights, so borrow is the open question and it was not measured.
5. **Feeds.** Alpaca's corporate-actions endpoint has a `rights_distribution` type [V: the
   endpoint's own type list, 2026-11-18]; a live query returned HTTP 401 in this session, so
   whether CEF rights appear there before the ex-date is [U]. EDGAR is enough on its own: the
   fund's 497 or N-2 names the record date and the expiry weeks ahead, and the parser here read
   an expiry for 112 of the 122 events whose fund is still a registrant.

## What would reopen it

- Borrow at Alpaca on the fund during the subscription period, for the 2024–25 events: if
  most are shortable, pre-register the short and run it as a shadow book.
- Net asset values: the offering is dilutive, so part of the fall is NAV and part is discount.
  The split says whether the discount snaps back (a trade) or the NAV is simply lower (no
  trade). 81 events are in the families panel, which has NAVs.
- The announcement date from EDGAR's first filing: the fall may start there (−84bp in the 20
  sessions before X), and a short opened at the announcement would see more of it.

## What could not be done

- CRSP misses some rights offerings (the issuance gate found 4 uncoded in 15 hand-read
  episodes), so the event list is not complete [S: `A1_CEF_ISSUANCE_GATE_2026-10-20.md`].
- Expiry dates for the 25 events whose fund is no longer a registrant, and 10 the parser could
  not read; an extension announced after the prospectus is not seen.
- Alpaca's live corporate-actions feed and borrow status (unauthorised in this session).
- Transferable against non-transferable: 10 events, too few.

**Not independently reviewed.**
