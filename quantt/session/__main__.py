"""`python3 -m quantt.session run|approve|ca-ack|verify --book cef ...` (docs/RUNNER.md, docs/RUNBOOK.md).

Each subcommand's module is imported only when that subcommand runs: `verify`
is read-only and must not import the transmit path, and a broken import in one
must not stop the other from reporting.
"""
from __future__ import annotations

import sys


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    usage = "usage: python3 -m quantt.session {run,approve,ca-ack,verify} --book BOOK [options]"
    if not argv or argv[0] in ("-h", "--help"):
        print(usage)
        print("  run     the trading session (python3 -m quantt.session run --help)")
        print("  approve record the team lead's go for one decided late-market plan")
        print("  ca-ack  record the team lead's acknowledgement of one corporate action (by id)")
        print("  verify  post-close reconcile and scoring (python3 -m quantt.session verify --help)")
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "run":
        from quantt.session.run import main as run_main
        return run_main(rest)
    if cmd == "approve":
        from quantt.session.run import approve_main
        return approve_main(rest)
    if cmd == "ca-ack":
        from quantt.session.run import ca_ack_main
        return ca_ack_main(rest)
    if cmd == "verify":
        from quantt.session.verify import main as verify_main
        return verify_main(rest)
    print(f"unknown subcommand {cmd!r}\n{usage}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
