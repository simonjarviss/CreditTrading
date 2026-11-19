---
name: paper
description: Promote an idea that cleared Explore to a shadow book - a simulated book on live data, run by the shadow/ package. Shadow books are approved (team lead, 2026-11-09) and an agent may start one without asking. A new paper account is a separate approval, and this skill refuses to start one; a sleeve in the events account follows the promotion rule (ten clean shadow sessions, then a one-file PR). Use after /explore.
argument-hint: <slug>
---

# Promote to a shadow book

Slug: **$ARGUMENTS**

## What is approved, and what is not

Check at run time; this file may be out of date:

```!
grep -n -i "shadow" docs/SYSTEM.md | tail -12
```

- **Shadow books: approved once** (`docs/SYSTEM.md` §5, "Team lead, 2026-11-09";
  design `results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md`). An agent may add,
  change and retire a shadow book without asking. A shadow book has no account
  and can send no order.
- **A new paper account: not approved.** Refuse to create an account, a book
  config under `ops/books/` or a scheduler entry. Say that it needs the team
  lead, and offer the shadow book.
- **A sleeve in the events paper account: by the promotion rule** (`docs/SYSTEM.md`
  §5, "Team lead, 2026-11-16 and 2026-11-18"). After ten clean on-time shadow
  sessions a book may be proposed as a sleeve. Run the read-only report and
  follow `quantt/sleeves/deploy/README.md` "Promotion and the ladder":

  ```bash
  python3 -m quantt.sleeves.promote --shadow-state <dir> --events-state <dir>
  ```

  An agent may open the one-file PR on `ops/sleeves/events_sleeves.json`. The
  book's full size, the merge, the release tag, the install and arming stay the
  team lead's. Never touch the order path (`quantt/sleeves/run.py`, `net.py`,
  `ledger.py`) for a promotion.
- **Real money:** the team's decision on a `/go-live` proposal.

## Steps

1. **Check the idea cleared Explore** (`docs/MISSION.md` §7): its ledger line
   and results note exist, the effect held in the time split, and the signal
   function is the one the Explore test ran. If not, go back to `/explore`.
2. **Write the signal as a function** `signal(asof, panels) -> pandas Series` of
   weights by symbol, as fractions of the book's notional. The engine removes
   every row dated after `asof` before it calls the function
   (`shadow/engine.py`). A panel dated by anything other than when a row became
   known (a period end, a revised series) must be lagged inside the function,
   as the idea's data card says.
3. **Write the book file** `shadow/books/<slug>.json`. Every key is required
   (`shadow/book.py`): `slug`, `card`, `signal` (`module:function`), `panels`
   (each with `path`, `date_col`, `required_asof`), `refresh` (the commands that
   fetch its panels each night; may be empty), `fill` (`next_close`),
   `notional_usd` (the team lead ruled $1M per book), `started`, `enabled`.
4. **Write tests for the signal**, on synthetic data: it returns no NaN, and its
   output for a date does not change when later rows are removed.
5. **Run it once by hand** against a state directory outside the repository:

   ```bash
   SHADOW_STATE_DIR=<dir> python3 -m shadow decide --asof <YYYY-MM-DD>
   ```

   `UNMEASURED` means a required panel has no row for that date: fix the
   fetcher, never the gate.
6. **Deliver it.** The runner on the VM follows the branch `shadow`; the book
   starts when its file is on that branch. Until the team lead has done the
   one-time VM install, say that the book is written and not yet running.
7. **Ledger:** set the idea's status to `SHADOW` with its start date, in the
   same commit as the book file.

## Lines that do not move

- Every shadow figure is labelled SIMULATED and counts toward no live statistic.
- A decision written after 13:00 New York on its fill date is stored as late and
  never scored. Do not back-fill decisions to make a record.
- Nothing under `shadow/` may import `quantt.session` or name an order method;
  `shadow/tests/test_boundary.py` fails if it does.
- No order on a real-money account without the team lead's explicit go in the
  session, after the full order list. `DRY_RUN=1` always wins.
- Prod releases are the team lead's alone. A shadow book never uses one.
- Never read `config/.env`.
