"""`python3 -m quantt.sleeves plan|send|verify|approve` (quantt/sleeves/run.py; PAPER ONLY).

    plan [--preview]             on session F before the send window ends: decide; sends nothing
    send [--preview]             inside the window: send the saved plan if every gate passes
    verify [--date D]            after the close: reconcile, book the ledger, score the sleeves
    approve [--date D] [--sha S] show a decided plan; with --sha, record the team lead's go

Needs QUANTT_STATE_DIR (a directory named after the book), QUANTT_ENV_FILE (the key file; not
for approve), and for plan QUANTT_SLEEVES_DECISIONS_DIR. `send` transmits only with DRY_RUN
exactly "0" and an approval or AUTO_ARMED. Installing and arming are the team lead's.
"""
from __future__ import annotations

import sys

if __name__ == "__main__":
    from quantt.sleeves.run import main
    sys.exit(main())
