# The shadow-book runner — design, approved by the team lead on 2026-11-09

**Status: APPROVED 2026-11-09** (`docs/SYSTEM.md` §5): the design as written, the VM as a separate user
and clone (§5), Alpaca's auction prints with a yfinance check (§6), and $1M per book. **Built so far:** the
engine, the book file, the scoreboard and their tests, in `shadow/` (reproducer:
`python3 -m pytest shadow/tests`). **Not built yet:** the marks and panel fetchers, the first book, and the
VM install, which is the team lead's. The text below is the proposal as approved.

**Amended later on 2026-11-09 (team lead):** the runner reads data with the core (`cef`) account's key, not a
new empty account's. The separate unix user stays and holds its own copy of that one key. §6's "should be a key
for an otherwise empty paper account" no longer applies. **Measured the same day** [V: `shadow/sources.py`
run from the laptop]: 88 of 88 auction prints for 8 symbols over 11 sessions (2026-10-26 to 2026-11-09), and
every one equal to yfinance's close. NYSE Arca listings needed a mapping the broker client lacks; it is
measured and held in `shadow/sources.py`. `docs/MISSION.md` §8.1 and §8.3 ask
for a path that can start a new book from a config without a prod release, and
`docs/SYSTEM.md` §5 (2026-11-09) says no agent starts a paper or shadow book until the team
lead has approved this design once. The team lead ruled the same day that shadow books come
first and paper accounts follow for the ideas that look best.

This note has no figures. It names the choices that are the team lead's in §8.

## 1. What a shadow book is

A shadow book is a simulated book on live data. Each evening it decides target positions
from data available that evening, and it is later marked on official closing prices as if
each trade had filled at the next close. It has no broker account, holds no trading key and
can send no order.

It answers one question that a backtest cannot: does the signal keep working on data that
did not exist when the idea was shaped. It does not answer what trading costs, whether a
short can be borrowed or how an auction fills. Those belong to a paper account and to the
go-live proposal.

**Every shadow figure is labelled SIMULATED.** `CLAUDE.md` says modelled sessions are not
evidence toward a live statistic, and that stays true.

## 2. How it is kept apart from prod

| risk | what prevents it |
|---|---|
| A shadow book sends an order | The code lives in a new top-level package, `shadow/`. It imports nothing from `quantt/session` or the broker's order methods, and a test fails if it ever does. It reads prices with GET requests only |
| A shadow book changes what prod trades on | It writes only under its own state folder and never under `data/`. A test fails on any write path outside that folder (`CLAUDE.md` landmine 9) |
| Starting a book needs a release | It does not. Prod is a clone at a release tag. The shadow runner is a second clone that follows a branch named `shadow`, so a new book is a commit to that branch |
| Unreviewed code runs next to prod's keys | The shadow clone runs as its own unix user, which cannot read prod's key files or prod's state folder (§5) |
| `quantt/` or `src/deploy/` starts to depend on research data | Unchanged rule: nothing under either imports `shadow/` or `scripts/`. The existing boundary test is extended to say so |

## 3. A book is one small file

`shadow/books/<slug>.json`, one per idea:

| key | meaning |
|---|---|
| `slug`, `card` | the idea's name and its idea card under `results/ideas/` |
| `signal` | a Python entry point, `module:function`. Given an as-of date and the panels, it returns target weights for that date. It is the same function the Explore test ran on the harness, so the backtest and the shadow book cannot drift apart |
| `universe` | where the tradable names come from, as of each date |
| `panels` | each data set the signal reads, with the fetcher that refreshes it and how fresh it must be to decide |
| `fill` | `next_close` (decide on D, fill at D+1's close, earn from then: the harness's `shift(2)`), or another stated convention such as `next_open` |
| `notional_usd` | the reference size the book is simulated at |
| `started` | the first decision date. Nothing before it is ever scored as shadow |

Starting a book is: add the file, add the signal function with its tests, push to `shadow`.

## 4. The daily cycle

One command, run after the close and again in the morning: `python3 -m shadow run`.

1. **Refresh** each panel the enabled books name, into the shadow state folder.
2. **Freshness gate, per book.** If a required panel has no row for the as-of date, the book
   records `UNMEASURED: <panel> ends <date>` for that day and does not decide. No stale value
   stands in.
3. **Decide.** Compute targets from data dated on or before the as-of date. Write
   `decisions/<date>.json`: the targets, a hash of each input panel, the code commit and the
   wall-clock time. The file is written once and never rewritten.
4. **Mark.** For each earlier decision whose fill date has passed, fill at that date's
   official close and compute the day's P&L on the positions held. Two lines are kept:
   price-only, and total return with distributions credited to longs and charged to shorts.
5. **Score.** Append one row per book to its `scores.csv`, and rebuild the scoreboard.

**The rule that keeps it honest: a decision counts only if it was written before the close
it fills at.** If the machine was off and a day is decided late, the decision is still
computed and stored, labelled `LATE`, and kept out of the scored record. Without this rule a
laptop that sleeps would quietly turn a shadow book into a backtest.

## 5. Where it runs

The runner needs a machine that is on every evening. Three options, for the team lead (§8):

| option | for | against |
|---|---|---|
| **The VM, as a separate user and clone** (recommended) | Always on. One install by the team lead, then no further VM work: the timer pulls the `shadow` branch each night | Shares the machine with prod. The separate user limits what shadow code can read; CPU and memory headroom on the VM is unmeasured and must be checked at install |
| The laptop, under launchd | No VM work at all | It sleeps. Prod left the laptop for that reason. Late days would be common and unscored |
| A scheduled GitHub Actions job | Free for a public repository and always on | The repository is public, so decisions could not be stored there. It would need private storage and a write token |

## 6. Prices for the marks

| option | for | against |
|---|---|---|
| **Alpaca's closing-auction prints, with yfinance closes as the cross-check** (recommended for US stocks, ETFs and CEFs) | The official close, the same source prod's score uses. Read-only | Needs an Alpaca key on the shadow user. The key can also trade its paper account, so it should be a key for an otherwise empty paper account |
| yfinance closes only | No key at all | Not the auction print. Fine for a simulation; a known source of small errors |

Futures, volatility indices and macro series come from free public sources, each with a
fetcher and a data card. Where two sources disagree the difference is reported and never
averaged.

## 7. The scoreboard, and what happens next

`python3 -m shadow scoreboard` writes one page for all books: days scored, days late or
unmeasured, P&L, Sharpe to date, drawdown, turnover, correlation with each other book and
with the core and C4, and each book's largest positions against average daily volume at
$1M, $5M and $10M. The repository gets aggregates only. Per-name targets stay in the state
folder, as the live rows do today.

A book that looks good on shadow moves to an Alpaca paper account. That step is not part of
this approval. It reuses the same book file and the existing `quantt` runner and its gates,
and each account needs the team lead to create it and add its keys.

**Tests written with the build:**
- a decision for date D is identical when every row after D is removed from the panels;
- re-running a decided date changes nothing and says so;
- a missing panel raises or records UNMEASURED and never decides;
- the package cannot import an order method and cannot write outside its state folder;
- a late decision is never scored.

## 8. What the team lead is asked to approve

1. **The design in §1 to §4 and §7**, as the one-time approval. After it, an agent may add,
   change and retire shadow books without asking.
2. **Where it runs** (§5).
3. **The price source for marks** (§6), and if Alpaca, which key.
4. **The reference size** each book is simulated at.
