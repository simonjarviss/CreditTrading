# Idea card — Share-class pairs: the gap does close, but by about one quoted spread

**Slug:** `dual_class_pairs` · **Started:** 2026-11-16, **interrupted** that day (the editor
was force quit about 20 minutes in), **completed 2026-11-18** ·
**Status:** EXPLORE, not promoted. The pre-specified book is 0.89 gross (t 4.54), positive
in every era, the same on mid quotes, 0.63 with a skip day, and both controls are flat. But
it earns 28.5bp a trade against a median quoted spread of 28.9bp across the two legs, 3.1% a
year per unit of gross held, and it is negative from about 7bp of cost per unit traded. The
thin pairs, the ones the idea was about, have the widest gaps and still wider spreads ·
**Reproducer:** `QUANTT_ENV_FILE=<env> python3 results/ideas/dual_class_pairs/stage.py monthly`,
then `... stage.py daily`, then `python3 results/ideas/dual_class_pairs/explore.py` and
`checks.py` ·
**Panels:** CRSP daily (`crsp_a_stock.dsf_v2` on R2) 1999-01-04 to **2025-12-31**, delisted
securities included; scored from 2000-01-03. No Yahoo data. Licensed rows are under
`~/quantt_research/dual_class_pairs/`, not in the repository.

## What the interruption left, and what was done on resuming

- On disk on 2026-11-18: `stage.py` and `explore.py` complete, the rule written in
  `explore.py`'s docstring, no `results.json`, no card, and a **zero-byte**
  `daily.parquet` (the daily pull was cut mid-write). So **no return had been read**.
- `daily.parquet` was deleted and rebuilt with `stage.py daily` (4,618,955 rows, 1,333
  securities, last date 2025-12-31). The monthly panel, pair list and control matches from
  2026-11-16 opened cleanly and reproduce the docstring's counts (245 pairs, 158 issuers).
- `explore.py` was then run **once, unchanged**. No fix to it was needed and none was made.
- `checks.py` is new (2026-11-18) and not pre-specified.

## The idea

Two classes of one company's common stock are claims on the same cash flows, so the gap
between them should not wander. In small companies one class is thin and no large fund can
trade the gap. Schultz and Shive (2010, `docs/REFERENCES.md`) report profits on intraday
quotes. This desk decides after a close and fills at the next close; the question is what
is left at that speed.

## What was fixed before any return was read (`explore.py` docstring, 2026-11-16)

Only counts, tickers, class labels and dollar volumes had been read.

- **Pairs, by rule:** two common-share permnos of one CRSP issuer (permco) alive together
  12 months or more, 1999 to 2025, dead ones in: 245 pairs on 158 issuers [V].
- **Spread:** cumulative difference of the two classes' log total returns, read only on
  sessions when both traded. **Signal:** its deviation from the mean of the 60 sessions
  before the decision day, in units of those sessions' standard deviation (asserted in code
  that nothing dated t enters).
- **Gate:** correlation of 5-session returns over the prior 250 sessions of 0.90 or more.
  Added before any return was read, because one issuer key also joins tracking stocks.
- **Eligible:** both legs $2 or more, $100,000 a day or more, traded that day, and the gap
  at least the sum of the two legs' median quoted spreads over the prior 21 sessions.
- **Entry** |z| ≥ 2 (Gatev, Goetzmann and Rouwenhorst 2006): long the cheap class, short the
  rich one, equal dollars. **Exit:** z back through zero, 20 sessions, or a leg leaves CRSP.
- **Weights:** 5% a leg per pair, at most 20 pairs. Decided at t, filled at t+1's close,
  earning from t+2 (`harness.evaluate`).
- **Controls:** pseudo-pairs (class B replaced by a different company of the same two-digit
  SIC nearest in size the December before); the real positions 21 sessions late.
- **Checks named in advance:** one session late; mid quotes for signal and returns; trades
  whose short leg is the more liquid class at $1M a day or more; buy-and-hold per trade.
- **Expected:** positive and above both controls; smaller on mid quotes.

## What it showed (gross, shift(2), no costs) [V]

2000-01-03 to 2025-12-31. 97 pairs traded, 3,557 trades, 6.3 pairs open on average, gross
held 0.63, turnover 27.4 times a year, worst drawdown −2.9%. 28 of 83,717 held leg-days
had no CRSP return (booked as zero).

| | Sharpe (t) | return / volatility | halves | 2002–08 | 2009–15 | 2016–19 | 2020–22 | 2023–25 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **REAL, closing prices (as fixed)** | 0.89 (4.54) | 1.96% / 2.20% | 0.84 / 0.99 | 0.93 | 0.67 | 1.57 | 1.11 | 0.67 |
| control: pseudo-pairs | 0.01 (0.04) | 0.11% / 14.85% | −0.36 / 0.34 | −0.66 | 0.22 | 1.08 | 0.25 | −0.25 |
| control: positions 21 sessions late | 0.12 (0.62) | 0.25% / 2.08% | 0.20 / 0.01 | 0.03 | 0.28 | −0.01 | 0.81 | −0.88 |
| check: one session late | 0.63 (3.21) | 1.34% / 2.12% | 0.55 / 0.78 | 0.33 | 0.80 | 1.26 | 0.72 | 0.49 |
| check: mid quotes, signal and returns | 0.92 (4.71) | 1.96% / 2.12% | 0.82 / 1.08 | 0.68 | 0.71 | 1.25 | 1.58 | 0.64 |
| check: mid quotes, one session late | 0.73 (3.70) | 1.47% / 2.03% | 0.52 / 1.03 | 0.39 | 0.59 | 0.99 | 1.57 | 0.36 |
| short leg is the liquid class (≥ $1M) | 0.49 (2.52) | 0.76% / 1.55% | 0.42 / 0.63 | 0.44 | 0.42 | 1.25 | 0.53 | 0.52 |
| short leg is the thin class (the rest) | 0.69 (3.50) | 1.19% / 1.73% | 0.68 / 0.72 | 0.77 | 0.51 | 1.02 | 0.97 | 0.46 |
| without the gate (tracking stocks in) | 0.76 (3.85) | 6.55% / 8.66% | 0.61 / 0.89 | 0.72 | 0.68 | 1.71 | 0.94 | 0.18 |

The expectation held, except that mid quotes are not smaller: the result is not bid-ask
bounce. REAL less pseudo-pairs as a daily series is 0.12 (t 0.63) only because the
pseudo-pair book runs at 14.9% volatility; the control's own level is zero, which is the
comparison that matters.

**Per trade, buy and hold** (no daily rebalancing): mean +28.5bp, median +20.4bp, 60%
positive, t 7.0 treating trades as independent (they overlap, so this is overstated); on
mid quotes +28.3bp. 3,557 trades × 28.5bp × 5% a leg over 26 years is 1.95% a year, the
book's figure, so constant daily weights flatter nothing here. Pseudo-pair trades: +10.8bp,
t 0.52.

**What is held:** median price $34; median dollar volume $11.6M (long leg) and $9.6M (short
leg), $3.0M for the thinner leg; median quoted spread 10.6bp and 11.8bp; the short leg is
the thinner class in 52% of trades. Closing quotes exist on 98.1% of security-days.

**Pairs live per year** (passing gate and floors, mean a day / on any day / trades): 2000
17/30/88; 2005 22/36/170; 2008 23/31/207; 2012 14/23/97; 2015 14/21/94; 2018 22/26/155;
2021 22/24/140; 2023 20/27/123; 2025 21/27/130. Every year is in `results.json`.

## Checks that were not pre-specified (`checks.py`, 2026-11-18) [V]

| trades by the thinner leg's dollar volume | trades | mean, close | mean, mid | median two-leg spread | mean less quoted spread |
|---|---:|---:|---:|---:|---:|
| under $500k | 958 | +39.1bp | +36.9bp | 93.7bp | −75.8bp |
| $500k to $2M | 646 | +48.5bp | +52.5bp | 46.4bp | −26.2bp |
| $2M to $10M | 757 | +14.4bp | +12.1bp | 22.6bp | −16.2bp |
| $10M and over | 1,196 | +18.2bp | +18.5bp | 10.5bp | +0.8bp |
| all | 3,557 | +28.5bp | +28.3bp | 28.9bp (mean 56.9bp) | −28.3bp |

"Less quoted spread" takes off half a spread per leg on the way in and on the way out, at
the spreads known at entry. It is a real-money view; a closing-auction fill may pay less.

| | |
|---|---|
| cost grid on the book (27.4 turns a year): 5 / 15 / 30bp | +0.59% / −2.15% / −6.27% a year; **the sign flips** at about 7bp |
| return a year per unit of gross held | 3.1% |
| exit by gap closing (2,256 trades) | +87.2bp |
| exit at 20 sessions (1,286 trades) | −72.2bp |
| exit because a leg left CRSP (9 trades) | −248.7bp mean, −11.8bp median |
| five best pairs' share of summed trade return | 20% (12% of trades); 77 of 97 pairs positive |
| mean trade without the five best pairs | +25.0bp |
| mean trade without the 20 best / 20 worst trades | +19.5bp / +35.5bp |
| worst and best trade; 1st and 99th percentile | −30.8% and +42.6%; −6.3% and +6.7% |
| mean trade by era (2000–01, 02–08, 09–15, 16–19, 20–22, 23–25) | 65, 30, 19, 29, 39, 14bp |
| short leg liquid (1,616 trades) against the rest (1,941) | +24.8bp against +31.6bp |

- **It is real and it is small.** Controls are flat, mid quotes agree, a skip day keeps
  two thirds, it is not a handful of pairs. But a trade earns one median quoted spread.
- **The thin pairs do not pay for themselves.** Under $500k a day the gap closes by 39bp
  and the two spreads cost 94bp. Only pairs trading $10M a day and more cover the quote,
  and those are not a niche.
- **A third of trades do not converge** and lose 72bp at the time stop; the few that end
  in a delisting or conversion lose more on average. The tail is the class terms differing
  in a deal.
- **Borrow:** restricting to trades whose short is the liquid class halves the book and
  leaves 0.49 (t 2.52), 0.76% a year.
- **Fading:** 14bp a trade in 2023–25 (t 1.4), the weakest era.

## What I conclude

1. Share-class gaps revert at the desk's speed; the pre-specified test passed its own
   expectations. Established on this panel.
2. It is not the niche it was proposed as. The edge per trade is about the quoted spread,
   the thinnest pairs are the worst after it, and the book earns 2% a year at 2%
   volatility with two thirds of capital deployed. It would need several times leverage
   and auction fills at no cost to matter.
3. Not a shadow candidate as fixed. Unknown, and decisive: what a closing-auction fill in
   the thin class actually costs, and whether the thin class can be borrowed at all.

## What would reopen it

- Closing-auction prints and imbalance sizes for the thin classes (TAQ), to see whether a
  market-on-close order fills at the CRSP close without moving it.
- Alpaca's easy-to-borrow flag for the thin classes of the roughly 25 pairs live today,
  measured on the day (`quantt.broker.alpaca_probe`); it was not read here.
- A dated event instead of a z-score: an announced conversion or collapse of the classes
  at a fixed ratio, where the gap has a known closing date.

## Could not do

- Borrow availability and fees: not measured. The liquid-short split is a proxy only.
- No fill-level check of the closing auction; CRSP gives the closing price and quote only.
- Tracking stocks are removed by the correlation gate, not by a flag; CRSP has none.

**Not independently reviewed.**
