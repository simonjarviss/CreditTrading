#!/bin/sh
# Run one phase of the events book BY HAND on the VM, as user quantt, with the same
# environment as the installed units and DRY_RUN=1 ALWAYS.
#
#   sudo sh run_events.sh plan --preview        print today's plan; write and send nothing
#   sudo sh run_events.sh plan                  write today's plan (sends nothing)
#   sudo sh run_events.sh send --preview        run every send gate on fresh reads; send nothing
#   sudo sh run_events.sh verify [--date D]     reconcile and book a session
#   sudo sh run_events.sh approve [--date D] [--sha S]
#
# WHY IT REFUSES A BARE `send`: orders go only from quantt-events-send.service, inside the
# window, on the team lead's arming (CLAUDE.md order-path rule 1). A hand-run send would
# also write the day's send.json, which VERIFY reads. This wrapper cannot transmit: it
# sets DRY_RUN=1, and the runner sends only when DRY_RUN is exactly 0.
set -eu

RUN_USER="quantt"
RUN_HOME="/home/${RUN_USER}"
PROD="${RUN_HOME}/prod/quantt-alpaca"
PY="${RUN_HOME}/venv/bin/python"
STATE="${RUN_HOME}/quantt_state/events"
ENV_FILE="/run/quantt-events/alpaca.env"
SHADOW_STATE="/home/quantt-shadow/shadow_state"

die() { echo "REFUSED: $*" >&2; exit 2; }

[ "$(id -u)" -eq 0 ] || die "run as root (sudo); it switches to ${RUN_USER} itself"
[ $# -ge 1 ] || die "usage: sudo sh $0 plan|send|verify|approve [options]"
phase="$1"
case "${phase}" in
  plan|verify|approve) ;;
  send)
    preview=0
    for a in "$@"; do
      if [ "${a}" = "--preview" ]; then preview=1; fi
    done
    [ "${preview}" -eq 1 ] || die "a hand-run send is not offered here; use 'send --preview'. Orders go only from quantt-events-send.service"
    ;;
  *) die "unknown phase '${phase}'" ;;
esac
[ -d "${STATE}" ] || die "${STATE} does not exist; run install_events_vm.sh first"
if [ "${phase}" != "approve" ]; then
  [ -f "${ENV_FILE}" ] || die "${ENV_FILE} is absent; run: sudo systemctl start quantt-events-secret.service"
fi
cd "${PROD}"
exec runuser -u "${RUN_USER}" -- env HOME="${RUN_HOME}" DRY_RUN=1 \
  QUANTT_STATE_DIR="${STATE}" QUANTT_ENV_FILE="${ENV_FILE}" \
  QUANTT_SLEEVES_DECISIONS_DIR="${SHADOW_STATE}" PYTHONUNBUFFERED=1 \
  PATH="${RUN_HOME}/venv/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  "${PY}" -B -m quantt.sleeves "$@"
