#!/bin/sh
# Root install of the event sleeves' PAPER runner ("the events book") on the prod VM.
#
#   sudo sh install_events_vm.sh --vault <vault-name> [--keep-state]
#   sudo sh install_events_vm.sh uninstall
#
# The team lead runs it (it needs sudo). Run the copy inside the prod clone, so the script
# and the runner are the same release: quantt/sleeves/deploy/README.md has the steps.
# IT NEVER ARMS. Every unit it writes carries DRY_RUN=1, and it creates no AUTO_ARMED.
#
# WHAT IT MAKES (nothing of the core book's or C4's is read, written or restarted)
#   <quantt home>/quantt_state/events     the state directory (0700, user quantt). It must be
#                                         named "events": quantt/sleeves/run.py refuses any other.
#   an ACL for user quantt                read-only, on <shadow state>/<slug>/decisions/ for the
#                                         slugs in the clone's ops/sleeves/events_sleeves.json,
#                                         and search-only (--x) on the three directories above
#                                         each. See WHY AN ACL below.
#   quantt-events-secret.service          the events account's two Alpaca keys, from the vault
#                                         into /run/quantt-events/alpaca.env (tmpfs, 0700), by
#                                         quantt/deploy/boot_secrets.py, the module prod uses.
#   quantt-events-plan.service/.timer     python -m quantt.sleeves plan
#   quantt-events-send.service/.timer     python -m quantt.sleeves send
#   quantt-events-verify.service/.timer   python -m quantt.sleeves verify
#
# THE CODE IT RUNS is the PROD CLONE at its installed release tag, as user quantt. Never the
# shadow clone: that one follows an unreleased branch, and what may send an order is decided
# by a release (the slugs, capital and limits are in the tagged ops/sleeves/events_sleeves.json).
# The shadow clone supplies only decision FILES, which the runner checks one by one.
#
# WHY AN ACL AND NOT A SHARED GROUP. The decisions belong to quantt-shadow, under a state
# directory of mode 0700. A shared group would mean changing the group and mode of that
# user's directories, a setgid bit so new files keep the group, and trusting its umask for
# every file written later. An ACL adds one named entry for one user on exactly the listed
# paths, a default entry so new decision files inherit r--, and is removed exactly by
# `uninstall`. quantt gets no write bit anywhere, and cannot list the shadow state or read
# a book's marks or scores: --x on a directory lets it pass through and nothing else.
# ONE TRAP: `chmod` on a directory that has an ACL rewrites the ACL's mask, and
# shadow/deploy/install_shadow_vm.sh runs `chmod 700` on the shadow state every time. After
# re-running that installer, re-run this one (the runner would refuse loudly meanwhile:
# "QUANTT_SLEEVES_DECISIONS_DIR ... is not an existing directory").
#
# THE TIMES (New York wall clock; the runner, not the timer, knows holidays and early closes)
#   PLAN    09:45 10:15 10:45 11:15 11:45 12:15 and 15:20, Mon-Fri. The first is the one that
#           matters: a decision is traded only if written before 09:30 (inputs.py), and the
#           shadow runner writes at 18:50, 20:50 and 07:20, so nothing new can arrive later.
#           The rest are retries after a failed read, and re-size on the day's asset flags.
#           PLAN refuses once the send window has started, so on a 13:00 close the 15:20 run
#           is a REFUSED, and that is correct. Off :10 and :40 (prod's collectors) and off
#           :00 and :30 (prod's sessions) on purpose: the VM has 1 GiB.
#   SEND    15:41 and 15:46; 12:41 and 12:46 for a 13:00 close. The window is 20 to 2 minutes
#           before the close. ONE service for all four, so systemd never runs two sends at
#           once. On a normal day the 12:4x runs are hours before the window: the runner
#           says so, writes nothing and exits 5 IDLE (a success here). A second send after
#           STARTED is REFUSED, which is the point of STARTED.
#   VERIFY  17:35, after the core's 17:30 and before the 17:40 collector.
#
# RE-RUNNING is safe and DISARMS: it rewrites the units with DRY_RUN=1 (AUTO_ARMED in the
# state directory is not touched; remove it yourself if you mean to disarm fully). It
# refuses inside the send windows and while an events job runs, because a timer restarted
# across a missed slot fires at once (measured on this VM, 2026-10-08; install_vm.py).
set -eu

RUN_USER="quantt"
RUN_HOME="/home/${RUN_USER}"
PROD="${RUN_HOME}/prod/quantt-alpaca"          # = quantt/deploy/install_vm.py Layout.prod_dir
PY="${RUN_HOME}/venv/bin/python"               # = Layout.venv_python
STATE_ROOT="${RUN_HOME}/quantt_state"
STATE="${STATE_ROOT}/events"
LOGS="${STATE}/logs"
RUN_NAME="quantt-events"
RUN_DIR="/run/${RUN_NAME}"
ENV_FILE="${RUN_DIR}/alpaca.env"
SHADOW_USER="quantt-shadow"                    # = shadow/deploy/install_shadow_vm.sh
SHADOW_HOME="/home/${SHADOW_USER}"
SHADOW_STATE="${SHADOW_HOME}/shadow_state"
BOOK_FILE="ops/sleeves/events_sleeves.json"
RUNNER_FILE="quantt/sleeves/run.py"
TZ_NAME="America/New_York"
UNIT_DIR="/etc/systemd/system"
UNIT_PATH_ENV="${RUN_HOME}/venv/bin:/usr/bin:/bin:/usr/sbin:/sbin"
TIMERS="quantt-events-plan.timer quantt-events-send.timer quantt-events-verify.timer"
SERVICES="quantt-events-plan.service quantt-events-send.service quantt-events-verify.service quantt-events-secret.service"

MODE="install"
VAULT=""
KEEP_STATE=0
TAG=""
SLUGS=""

die() { echo "REFUSED: $*" >&2; exit 2; }
step() { echo "== $*"; }
as_quantt() { runuser -u "${RUN_USER}" -- env HOME="${RUN_HOME}" "$@"; }
as_shadow() { runuser -u "${SHADOW_USER}" -- env HOME="${SHADOW_HOME}" "$@"; }

usage() {
  die "usage: sudo sh $0 --vault <vault-name> [--keep-state]   |   sudo sh $0 uninstall"
}

parse() {
  while [ $# -gt 0 ]; do
    case "$1" in
      install) MODE="install"; shift ;;
      uninstall) MODE="uninstall"; shift ;;
      --vault) [ $# -ge 2 ] || die "--vault needs a name"; VAULT="$2"; shift 2 ;;
      --keep-state) KEEP_STATE=1; shift ;;
      *) die "unknown argument '$1'" ;;
    esac
  done
  if [ "${MODE}" = "install" ]; then
    [ -n "${VAULT}" ] || usage
    # A plain vault name only: it is written into a unit's command line.
    case "${VAULT}" in
      *[!A-Za-z0-9-]*|-*) die "vault '${VAULT}' is not a plain vault name" ;;
    esac
  fi
}

# ---------------------------------------------------------------- shared checks

check_root_and_zone() {
  [ "$(id -u)" -eq 0 ] || die "run as root (sudo)"
  command -v systemctl >/dev/null 2>&1 || die "systemctl not found; this is for the systemd VM"
  command -v runuser >/dev/null 2>&1 || die "runuser not found"
  [ "$(timedatectl show -p Timezone --value)" = "${TZ_NAME}" ] \
    || die "system zone is not ${TZ_NAME}; the timers are New York wall-clock time"
}

check_not_in_send_window() {
  # Weekdays 12:30-13:00 and 15:30-16:00 New York (the zone was checked above), as
  # install_vm.py refuses: stopping and restarting a timer here could replay a send slot.
  dow="$(date +%u)"
  hm="$(date +%H%M)"
  if [ "${dow}" -le 5 ]; then
    if { [ "${hm}" -ge 1230 ] && [ "${hm}" -lt 1300 ]; } || { [ "${hm}" -ge 1530 ] && [ "${hm}" -lt 1600 ]; }; then
      die "it is ${hm} New York on a weekday, inside a send window (12:30-13:00, 15:30-16:00); re-run after it"
    fi
  fi
}

check_no_events_job_running() {
  running="$(systemctl list-units --type=service --state=activating,running --no-legend 'quantt-events-*' | awk '{print $1}' | tr '\n' ' ')"
  [ -z "$(echo "${running}" | tr -d ' ')" ] \
    || die "an events job is running: ${running}; wait for it to finish (to stop a send, write ${STATE}/HALT before it starts; nothing cancels orders already at Alpaca)"
}

# -------------------------------------------------------------- install: checks

check_layout() {
  step "users, prod clone and Python"
  id -u "${RUN_USER}" >/dev/null 2>&1 || die "user ${RUN_USER} does not exist; prod is not installed here"
  id -u "${SHADOW_USER}" >/dev/null 2>&1 || die "user ${SHADOW_USER} does not exist; install the shadow runner first"
  [ -d "${PROD}/.git" ] || die "${PROD} is not a git clone"
  [ -x "${PY}" ] || die "${PY} is not an executable interpreter"
  [ -d "${STATE_ROOT}" ] || die "${STATE_ROOT} does not exist; prod is not installed here"
  [ -d "${SHADOW_STATE}" ] || die "${SHADOW_STATE} does not exist; the shadow runner has not run"
  command -v setfacl >/dev/null 2>&1 || die "setfacl not found; install the 'acl' package (apt-get install acl) and re-run"
  command -v getfacl >/dev/null 2>&1 || die "getfacl not found; install the 'acl' package (apt-get install acl) and re-run"
  for d in "${UNIT_DIR}"/quantt-events-*.d; do
    [ ! -e "${d}" ] || die "${d} exists: a drop-in would override the units this script writes (DRY_RUN among them); remove it first"
  done
}

check_release() {
  step "the prod clone is a clean checkout of a release tag that holds the runner"
  [ -z "$(as_quantt git -C "${PROD}" status --porcelain)" ] \
    || die "${PROD} has local modifications; prod is the tag and nothing else"
  tags="$(as_quantt git -C "${PROD}" tag --points-at HEAD)"
  for t in ${tags}; do
    case "${t}" in
      release-[0-9]*) TAG="${t}" ;;
    esac
  done
  [ -n "${TAG}" ] || die "${PROD} HEAD is not at a release-* tag (tags at HEAD: '${tags}')"
  for f in "${RUNNER_FILE}" "${BOOK_FILE}" quantt/deploy/boot_secrets.py; do
    as_quantt git -C "${PROD}" cat-file -e "HEAD:${f}" \
      || die "release ${TAG} does not contain ${f}; release a tag that does, install prod at it, then re-run"
    [ -f "${PROD}/${f}" ] || die "${PROD}/${f} is missing from the working tree"
  done
  echo "   release ${TAG}"
}

read_slugs() {
  step "sleeves in ${BOOK_FILE} at ${TAG}"
  # Parsed by the runner's own loader, so a book file the runner would refuse stops here.
  SLUGS="$(cd "${PROD}" && as_quantt "${PY}" -B -c '
import sys
from pathlib import Path
from quantt.sleeves import config
c = config.load(Path(sys.argv[1]))
if c.book != "events":
    raise SystemExit(f"book is {c.book!r}; this installer is for the book named events")
print("\n".join(c.slugs))
' "${BOOK_FILE}")"
  [ -n "${SLUGS}" ] || die "no sleeve read from ${BOOK_FILE}"
  for s in ${SLUGS}; do
    case "${s}" in
      *[!a-z0-9_]*|"") die "slug '${s}' is not lowercase letters, digits and underscores" ;;
    esac
    echo "   ${s}"
  done
}

check_state() {
  step "events state directory"
  if [ -e "${STATE}/ledger.json" ] && [ "${KEEP_STATE}" -ne 1 ]; then
    die "${STATE}/ledger.json exists: this book has run here before. Read it, then re-run with --keep-state to install over it (nothing in the state directory is changed either way)"
  fi
}

# ---------------------------------------------------------------- install: ACL

grant_acl() {
  step "read-only ACL for ${RUN_USER} on the listed decisions directories"
  missing=""
  for s in ${SLUGS}; do
    [ -d "${SHADOW_STATE}/${s}/decisions" ] || missing="${missing} ${s}"
  done
  [ -z "${missing}" ] || die "no decisions directory under ${SHADOW_STATE} for:${missing}. Let the shadow runner run those books once, then re-run"
  setfacl -m "u:${RUN_USER}:--x" "${SHADOW_HOME}" "${SHADOW_STATE}"
  for s in ${SLUGS}; do
    dec="${SHADOW_STATE}/${s}/decisions"
    setfacl -m "u:${RUN_USER}:--x" "${SHADOW_STATE}/${s}"
    setfacl -m "u:${RUN_USER}:r-x" "${dec}"
    # New decision files inherit r-- for quantt (they are created 0666 & the default ACL).
    setfacl -d -m "u:${RUN_USER}:r--" "${dec}"
    find "${dec}" -maxdepth 1 -type f -exec setfacl -m "u:${RUN_USER}:r--" {} +
    echo "   ${dec}"
  done
}

verify_access() {
  step "check the access, both ways, before any unit is written"
  for s in ${SLUGS}; do
    dec="${SHADOW_STATE}/${s}/decisions"
    as_quantt test -r "${dec}" || die "${RUN_USER} cannot read ${dec}"
    as_quantt test -x "${dec}" || die "${RUN_USER} cannot enter ${dec}"
    if as_quantt test -w "${dec}"; then die "${RUN_USER} can WRITE ${dec}; it must be read-only"; fi
    if as_quantt test -w "${SHADOW_STATE}/${s}"; then die "${RUN_USER} can WRITE ${SHADOW_STATE}/${s}"; fi
    newest="$(find "${dec}" -maxdepth 1 -type f -name '*.json' | sort | tail -n 1)"
    if [ -n "${newest}" ]; then
      as_quantt test -r "${newest}" || die "${RUN_USER} cannot read ${newest}"
      if as_quantt test -w "${newest}"; then die "${RUN_USER} can WRITE ${newest}"; fi
    else
      echo "   note: ${dec} holds no decision file yet"
    fi
  done
  if as_quantt test -w "${SHADOW_STATE}"; then die "${RUN_USER} can WRITE ${SHADOW_STATE}"; fi
  if as_quantt test -r "${SHADOW_STATE}"; then die "${RUN_USER} can LIST ${SHADOW_STATE}; it should only pass through"; fi
  if as_quantt test -w "${SHADOW_HOME}"; then die "${RUN_USER} can WRITE ${SHADOW_HOME}"; fi
  echo "   ${RUN_USER}: read-only on the listed decisions, nothing else of ${SHADOW_USER}'s"
}

make_state() {
  step "state directory ${STATE} (0700, ${RUN_USER})"
  install -d -o "${RUN_USER}" -g "${RUN_USER}" -m 700 "${STATE}"
  install -d -o "${RUN_USER}" -g "${RUN_USER}" -m 700 "${LOGS}"
  if as_shadow test -r "${STATE}"; then die "${SHADOW_USER} can read ${STATE}"; fi
  if as_shadow test -x "${STATE}"; then die "${SHADOW_USER} can enter ${STATE}"; fi
  if as_shadow test -w "${STATE}"; then die "${SHADOW_USER} can write ${STATE}"; fi
  [ ! -e "${STATE}/AUTO_ARMED" ] || echo "   WARNING: ${STATE}/AUTO_ARMED exists (kept). The units below are DRY_RUN=1, so nothing is sent; remove the file if you did not mean it"
}

# --------------------------------------------------------------- install: units

unit_file() {
  # $1 = unit name; the body comes on stdin. Only this book's units, ever.
  case "$1" in
    quantt-events-*) ;;
    *) die "internal: '$1' is not an events unit; this script writes no other" ;;
  esac
  cat > "${UNIT_DIR}/$1"
  chmod 644 "${UNIT_DIR}/$1"
  echo "   ${UNIT_DIR}/$1"
}

job_service() {
  # $1 = phase (plan|send|verify), $2 = exit codes that are a normal outcome
  unit_file "quantt-events-$1.service" <<UNIT
# quantt-events-$1.service : the events book's $1 phase (PAPER ONLY), release ${TAG}.
# WRITTEN by quantt/sleeves/deploy/install_events_vm.sh; re-run it rather than hand-editing
# (the one deliberate hand edit is DRY_RUN in the send unit, by the team lead, to arm).
# DRY_RUN=1 as installed. SEND transmits only with DRY_RUN exactly 0 AND an approval for
# the day's plan_sha or ${STATE}/AUTO_ARMED (quantt/sleeves/run.py).
# The clone is read-only to this job: it writes its state directory and nothing else.
[Unit]
Description=QUANTT events book $1 (paper; release ${TAG})
Wants=quantt-events-secret.service
After=quantt-events-secret.service

[Service]
Type=oneshot
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${PROD}
Environment=DRY_RUN=1
Environment=QUANTT_STATE_DIR=${STATE}
Environment=QUANTT_ENV_FILE=${ENV_FILE}
Environment=QUANTT_SLEEVES_DECISIONS_DIR=${SHADOW_STATE}
Environment=PATH=${UNIT_PATH_ENV}
Environment=PYTHONUNBUFFERED=1
ExecStart=${PY} -B -m quantt.sleeves $1
ReadOnlyPaths=${PROD}
$2
StandardOutput=append:${LOGS}/$1.out.log
StandardError=append:${LOGS}/$1.err.log
UNIT
}

write_units() {
  step "systemd units (DRY_RUN=1 in every one)"
  unit_file quantt-events-secret.service <<UNIT
# quantt-events-secret.service : the events paper account's Alpaca keys, from the cloud
# secret store into ${ENV_FILE} (tmpfs), once per boot when the fetch succeeds.
# WRITTEN by quantt/sleeves/deploy/install_events_vm.sh; re-run it rather than hand-editing.
# The design is quantt-secret.service's (that template; install_vm.py, THE KEY FILE): its own
# secrets, its own 0700 directory, RemainAfterExit=yes, pulled in by the job units with
# Wants= + After=, never Requires=. The core's and C4's key files are other directories.
[Unit]
Description=QUANTT events book Alpaca keys into ${RUN_DIR} (release ${TAG})
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=${RUN_USER}
Group=${RUN_USER}
RuntimeDirectory=${RUN_NAME}
RuntimeDirectoryMode=0700
WorkingDirectory=${PROD}
Environment=PATH=${UNIT_PATH_ENV}
Environment=PYTHONUNBUFFERED=1
ExecStart=${PY} -B -m quantt.deploy.boot_secrets --provider azure-keyvault --config vault=${VAULT} --secret alpaca-events-key-id=ALPACA_EVENTS_KEY_ID --secret alpaca-events-secret-key=ALPACA_EVENTS_SECRET_KEY --out ${ENV_FILE}
StandardOutput=append:${LOGS}/secret.out.log
StandardError=append:${LOGS}/secret.err.log

[Install]
WantedBy=multi-user.target
UNIT
  # Normal outcomes (quantt.session.run.EXIT_NAMES): plan 5 IDLE, 6 PLANNED; send 0 SENT,
  # 3 NOTHING_TO_SEND, 10 DRY. REFUSED (11) and FAIL (20) show as failed, on purpose.
  job_service plan "SuccessExitStatus=5 6"
  job_service send "SuccessExitStatus=3 5 10"
  job_service verify "# verify exits 0 PASS or 1 FAIL; a FAIL shows as a failed unit"
  unit_file quantt-events-plan.timer <<UNIT
# quantt-events-plan.timer : New York wall-clock time. The 09:45 run is the plan; the rest
# retry a failed read (see the header of install_events_vm.sh). Persistent=false: a missed
# run is not replayed at boot.
[Unit]
Description=QUANTT events book plan schedule

[Timer]
OnCalendar=Mon..Fri *-*-* 09:45:00
OnCalendar=Mon..Fri *-*-* 10:15:00
OnCalendar=Mon..Fri *-*-* 10:45:00
OnCalendar=Mon..Fri *-*-* 11:15:00
OnCalendar=Mon..Fri *-*-* 11:45:00
OnCalendar=Mon..Fri *-*-* 12:15:00
OnCalendar=Mon..Fri *-*-* 15:20:00
AccuracySec=1s
Persistent=false
Unit=quantt-events-plan.service

[Install]
WantedBy=timers.target
UNIT
  unit_file quantt-events-send.timer <<UNIT
# quantt-events-send.timer : 15:41 and 15:46 for a 16:00 close; 12:41 and 12:46 for a 13:00
# close (the book file's window is 20 to 2 minutes before the close). The runner's clock
# gate refuses the slots that are not today's. Persistent=false, AccuracySec=1s.
[Unit]
Description=QUANTT events book send schedule

[Timer]
OnCalendar=Mon..Fri *-*-* 15:41:00
OnCalendar=Mon..Fri *-*-* 15:46:00
OnCalendar=Mon..Fri *-*-* 12:41:00
OnCalendar=Mon..Fri *-*-* 12:46:00
AccuracySec=1s
Persistent=false
Unit=quantt-events-send.service

[Install]
WantedBy=timers.target
UNIT
  unit_file quantt-events-verify.timer <<UNIT
# quantt-events-verify.timer : 17:35 New York, Mon-Fri. Persistent=false, AccuracySec=1s.
[Unit]
Description=QUANTT events book verify schedule

[Timer]
OnCalendar=Mon..Fri *-*-* 17:35:00
AccuracySec=1s
Persistent=false
Unit=quantt-events-verify.service

[Install]
WantedBy=timers.target
UNIT
  for u in ${SERVICES}; do
    if [ "${u}" = "quantt-events-secret.service" ]; then continue; fi
    n="$(grep -c '^Environment=DRY_RUN=1$' "${UNIT_DIR}/${u}")" || true
    [ "${n}" = "1" ] || die "${UNIT_DIR}/${u} does not carry exactly one Environment=DRY_RUN=1"
  done
}

enable_units() {
  step "load and enable (the timers run DRY)"
  # shellcheck disable=SC2086
  systemctl stop ${TIMERS} 2>/dev/null || true
  systemctl daemon-reload
  systemctl enable quantt-events-secret.service >/dev/null
  # If the key service is already up, fetch again so the file matches the unit just written.
  systemctl try-restart quantt-events-secret.service \
    || die "quantt-events-secret.service failed to restart; read ${LOGS}/secret.err.log (it names steps and secret names, never a value)"
  # shellcheck disable=SC2086
  systemctl enable --now ${TIMERS} >/dev/null
}

summary() {
  cat <<DONE

events book installed from release ${TAG}. NOT ARMED: every unit has DRY_RUN=1 and this
script created no AUTO_ARMED. Nothing will be sent until the team lead arms it.

DONE
  systemctl list-timers 'quantt-events-*' --no-pager || true
  cat <<DONE

NEXT, BY HAND (quantt/sleeves/deploy/README.md has the full first-day checklist):

 1. Fetch the keys once and read the result (variable NAMES only are printed):
      sudo systemctl start quantt-events-secret.service
      sudo tail -n 3 ${LOGS}/secret.out.log ${LOGS}/secret.err.log

 2. Preview a plan on a trading day before 15:40 New York (prints, writes nothing, sends nothing):
      sudo sh ${PROD}/quantt/sleeves/deploy/run_events.sh plan --preview

 3. To ARM (the team lead only; outside 12:30-13:00 and 15:30-16:00 New York):
      sudo sed -i 's/^Environment=DRY_RUN=1\$/Environment=DRY_RUN=0/' ${UNIT_DIR}/quantt-events-send.service
      sudo systemctl daemon-reload
    then, for the first armed day, approve that day's plan by its sha after reading its order table:
      sudo sh ${PROD}/quantt/sleeves/deploy/run_events.sh approve
      sudo sh ${PROD}/quantt/sleeves/deploy/run_events.sh approve --sha <plan_sha>
    and only after that day's VERIFY line PASSes, for unattended sends:
      sudo -u ${RUN_USER} touch ${STATE}/AUTO_ARMED

 4. To HALT this book (no send starts while the file exists; it cancels nothing already at Alpaca):
      sudo -u ${RUN_USER} sh -c 'echo "why" > ${STATE}/HALT'
    To resume: sudo rm ${STATE}/HALT

 5. To remove: sudo sh ${PROD}/quantt/sleeves/deploy/install_events_vm.sh uninstall
DONE
}

# -------------------------------------------------------------------- uninstall

has_acl() {
  # $1 = path, $2 = "" or "default:"
  getfacl -cpE "$1" 2>/dev/null | grep -q "^$2user:${RUN_USER}:"
}

strip_acl() {
  [ -e "$1" ] || return 0
  if has_acl "$1" ""; then setfacl -x "u:${RUN_USER}" "$1"; fi
  if [ -d "$1" ] && has_acl "$1" "default:"; then setfacl -d -x "u:${RUN_USER}" "$1"; fi
  # With no named entry left, drop the mask and the bare default entries too, so the path
  # is back to plain mode bits.
  if ! getfacl -cpE "$1" 2>/dev/null | grep -Eq '^(default:)?(user|group):[^:]+:'; then
    setfacl -b "$1"
  fi
}

uninstall() {
  check_root_and_zone
  check_not_in_send_window
  check_no_events_job_running
  step "stop and disable the timers"
  for u in ${TIMERS}; do
    systemctl disable --now "${u}" 2>/dev/null || echo "   ${u}: not loaded"
  done
  step "stop the services (stopping the key service removes ${RUN_DIR} and the key file)"
  for u in ${SERVICES}; do
    systemctl stop "${u}" 2>/dev/null || echo "   ${u}: not loaded"
  done
  systemctl disable quantt-events-secret.service 2>/dev/null || true
  step "remove the unit files"
  for u in ${TIMERS} ${SERVICES}; do
    case "${u}" in
      quantt-events-*) rm -f "${UNIT_DIR}/${u}"; echo "   ${UNIT_DIR}/${u}" ;;
      *) die "internal: '${u}' is not an events unit" ;;
    esac
  done
  systemctl daemon-reload
  # shellcheck disable=SC2086
  systemctl reset-failed ${TIMERS} ${SERVICES} 2>/dev/null || true
  step "remove ${RUN_USER}'s ACL entries from ${SHADOW_USER}'s files"
  if command -v setfacl >/dev/null 2>&1 && command -v getfacl >/dev/null 2>&1; then
    # Every book directory, not only today's listed slugs: the list may have changed since
    # the install that granted the access.
    for d in "${SHADOW_STATE}"/*; do
      [ -d "${d}" ] || continue
      if [ -d "${d}/decisions" ]; then
        for f in "${d}/decisions"/*; do
          [ -f "${f}" ] || continue
          strip_acl "${f}"
        done
        strip_acl "${d}/decisions"
      fi
      strip_acl "${d}"
    done
    strip_acl "${SHADOW_STATE}"
    strip_acl "${SHADOW_HOME}"
  else
    echo "   WARNING: setfacl/getfacl not found; the ACL entries, if any, were NOT removed"
  fi
  cat <<DONE

events book uninstalled: timers, services and the ACL are gone.
LEFT ALONE, on purpose: ${STATE} (ledger, plans, scores, logs, HALT, AUTO_ARMED), the vault
secrets, and any position in the events paper account. Nothing was sent or cancelled.
DONE
}

# ------------------------------------------------------------------------- main

main() {
  parse "$@"
  if [ "${MODE}" = "uninstall" ]; then
    uninstall
    return 0
  fi
  check_root_and_zone
  check_not_in_send_window
  check_no_events_job_running
  check_layout
  check_release
  read_slugs
  check_state
  grant_acl
  verify_access
  make_state
  write_units
  enable_units
  summary
}

main "$@"
