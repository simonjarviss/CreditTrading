"""The event sleeves' paper runner: shadow-book decisions, traded in ONE Alpaca paper account.

WHY THIS EXISTS (team lead, 2026-11-15). The core CEF paper book was flat after 34 sessions
on a rare draw of its NAV leg (results/ideas/2026-11-15_core_nav_hedge.md), and the team
lead asked for more independent books on paper sooner. Until now every new book was only
simulated (`shadow/`). The ruling: build and test a runner that sends the chosen shadow
books' decisions as orders in a separate paper account shared by all event sleeves; the
team lead installs and arms it. PAPER ONLY. Nothing in this package may ever address a
real-money account, and CLAUDE.md's order-path rules apply to it in full.

THE BOUNDARY, BOTH WAYS
  * `shadow/` still cannot send an order (shadow/tests/test_boundary.py). This package does
    not import it: it reads a shadow book's decision FILES as data, from the directory
    QUANTT_SLEEVES_DECISIONS_DIR names, and checks each one before use (`inputs.py`).
  * The slugs that may trade, their capital and every limit are in a release-tagged file,
    `ops/sleeves/events_sleeves.json` (`config.py`). A decision file for a slug not listed
    there is never read. So what a branch the shadow clone follows can change is the
    weights of listed books, inside the caps; it cannot add a book or raise a limit.

THE PIECES
  config.py   the book file; every key required.
  inputs.py   one decision per sleeve for the session, or the reason there is none.
  net.py      sleeve weights -> whole-share targets per sleeve -> ONE net target per symbol
              (Alpaca rejects opposite-side orders in one symbol as wash trades; CLAUDE.md
              landmine 2). Pure functions.
  ledger.py   who owns which shares. Orders are netted, so a sleeve's position and P&L can
              only come from this runner's own book-keeping, never from order ids. Pure.
The order phase (plan, send, verify) is built on these and on the core runner's gates and
transmit code; see docs in each module as they land.
"""
