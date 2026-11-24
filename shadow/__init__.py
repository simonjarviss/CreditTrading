"""Shadow books: simulated books on live data. No account, no key that trades, no order.

WHY THIS PACKAGE EXISTS
-----------------------
The team lead's mission (docs/MISSION.md section 8, 2026-11-09) needs an idea to reach
live data in a day, without a prod release. Prod is a clone at a release tag that only
the team lead installs; C4 took three weeks from approval to its first session. A shadow
book needs none of that: each evening it DECIDES target weights from data available that
evening, and it is later MARKED on official closes as if each trade filled at the next
close. The design the team lead approved once, on 2026-11-09, is
results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md (docs/SYSTEM.md section 5).

WHAT IT MUST NEVER DO, AND WHAT ENFORCES IT
-------------------------------------------
  * Send an order. Nothing here imports `quantt.session`, and nothing names the broker
    client's order method. `shadow/tests/test_boundary.py` reads this package's source
    and fails if either appears.
  * Change what prod trades on. Every write goes under the state directory named by
    SHADOW_STATE_DIR, which is required (no default: an unset variable raises), and the
    engine refuses a state directory inside the repository's `data/` (CLAUDE.md
    landmine 9).
  * Count as evidence. Every figure it writes is labelled SIMULATED (CLAUDE.md:
    "Modelled sessions are not evidence").

`quantt/` and `src/deploy/` never import this package; the same boundary test says so.
"""
