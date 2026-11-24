"""Push an ACT line to the team lead, or say loudly that it could not be delivered.

The team lead ruled on 2026-11-08 that the nightly check is owned by a VM timer,
with a push notification ONLY when a stop fires; INFO and WATCH stay in the
journal. This is that push, and only that.

WHY IT REUSES `ops.halt._email` AND NOTHING ELSE
------------------------------------------------
`_email` is the desk's existing SMTP path (STARTTLS, Gmail app password). It takes
its configuration from the process environment first (`ops.halt._cfg`), then from
`config/.env`, which does not exist on the VM. The report units get it from
`/run/quantt-reports/alert.env` (`EnvironmentFile=-`, written from the vault by
`quantt-reports-secret.service`), so nothing here reads a credential: `_email`
does, inside its own function. `alert()` (macOS banner and speech) is deliberately
not used: neither exists on the VM, and a report job has nothing to say to a
laptop.

`ops.halt` imports only the standard library, and this module calls `_email` and
nothing else from it (scripts/ops/tests/test_report_no_order_path.py pins both).
So this module cannot send, cancel or replace an order, write a halt file, or read
a broker key.

WHEN THE CHANNEL DOES NOT WORK
------------------------------
`notify_act` returns what happened. `risk_daily.py` records the literal line
`ACT: notification NOT delivered: <reason>` in the report and on stderr, and exits
non-zero (`EXIT_ACT_UNDELIVERED`), so a fired stop can never sit undelivered with
a green service. The channel being unconfigured is not an error to swallow: the
team lead has to know the push does not exist yet.
"""
from __future__ import annotations

import datetime as dt
from typing import Callable

EXIT_ACT_UNDELIVERED = 3


def _default_send(subject: str, body: str):
    # Imported here so `import scripts.ops.report_notify` stays stdlib-only at
    # module level, and a test can inject a channel without touching ops.halt.
    from ops.halt import _email
    return _email(subject, body)


def notify_act(lines: list[str], *, book: str, asof: dt.date, report_path: str,
               send: Callable[[str, str], object] | None = None) -> dict:
    """Send the ACT lines through the SMTP path. Returns {"delivered": bool,
    "reason": str|None, "channel": "email"}. Never raises: a broken channel must
    become a recorded, non-zero outcome, not a traceback that hides the line."""
    subject = f"QUANTT ACT [{book}] {asof}: {len(lines)} stop(s) fired"
    body = "\n".join(lines) + f"\n\nReport: {report_path}\nReport only: nothing was sent or cancelled.\n"
    try:
        res = (send or _default_send)(subject, body)
    except Exception as e:                      # the channel, not the stop, failed
        res = f"{type(e).__name__}: {e}"
    if res is True:
        return {"delivered": True, "reason": None, "channel": "email"}
    return {"delivered": False, "reason": str(res), "channel": "email"}


def undelivered_line(reason: str) -> str:
    return f"ACT: notification NOT delivered: {reason}"
