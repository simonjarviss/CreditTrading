#!/usr/bin/env bash
# One-time root install of the shadow-book runner on the VM, beside prod and apart from it.
#
#   sudo bash install_shadow_vm.sh --vault <vault-name> [--branch shadow] [--enable]
#
# The team lead runs it (it needs sudo; docs/RUNBOOK.md section 8.10). Design and the
# rulings it implements: results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md and
# docs/SYSTEM.md section 5, "Team lead, 2026-11-09".
#
# WHAT IT MAKES
#   user quantt-shadow          no login shell, home /home/quantt-shadow (0750). Prod's user is
#                               quantt; neither can read the other's home, state or key file.
#   ~/venv                      its own Python (the version prod pins) and the packages in the
#                               clone's requirements.txt, wheels only. Prod's venv is untouched.
#   ~/quantt-shadow             a clone that FOLLOWS A BRANCH (default `shadow`). Prod is a
#                               clone at a release tag; this one is not, by design: a new
#                               shadow book is a commit to that branch and needs no release.
#   ~/shadow_state              decisions, marks, scores, the scoreboard. Never under data/.
#   quantt-shadow-secret.service  the core (cef) account's Alpaca key into /run/quantt-shadow
#                               (tmpfs, 0700, owned by that user): a COPY of that one key, fetched
#                               from the vault by the same module prod uses.
#   quantt-shadow.service/.timer  `shadow/deploy/nightly.sh`: update the clone, then
#                               `python -m shadow nightly`. 18:50 and 20:50 Mon-Fri, 07:20 Tue-Sat
#                               (New York), off prod's :10/:40 collector slots and outside its
#                               send (15:52-15:58), verify (17:30) and decide (22:00-01:00) windows.
#
# WHAT THE SEPARATE USER DOES AND DOES NOT BUY. File permissions keep shadow code away
# from prod's state and prod's key file. They do NOT keep a process on this VM away from
# the vault: the VM's identity is reachable by every local user, which is how this unit
# fetches its key. So code on the followed branch could fetch whatever that identity may
# read. The defence is who can push to the branch, and that the shadow package holds no
# order path (shadow/tests/test_boundary.py). The key fetched here can trade the core's
# paper account; it is a paper account, and never a live one.
#
# LIMITS ON THE JOB, so it cannot starve prod on a small VM: Nice=10, MemoryHigh, MemoryMax,
# CPUQuota and a start timeout (the unit below). A job killed by them shows as failed.
#
# RE-RUNNING is safe: every step checks before it acts. It refuses while any prod job is
# running or queued, because the package install competes for memory.
set -euo pipefail

ORIGIN="https://github.com/quanttqueensu/CreditTrading.git"
# NOT "shadow": Ubuntu ships a system GROUP of that name, which may read /etc/shadow, and
# useradd refuses the name (first run on the VM, 2026-11-10). Joining that group instead
# would hand the password file to the shadow runner.
SVC_USER="quantt-shadow"
HOME_DIR="/home/${SVC_USER}"
CLONE="${HOME_DIR}/quantt-shadow"
VENV="${HOME_DIR}/venv"
UV_VENV="${HOME_DIR}/.uv"
UV="${UV_VENV}/bin/uv"
STATE="${HOME_DIR}/shadow_state"
LOGS="${HOME_DIR}/logs"
RUN_DIR="/run/quantt-shadow"
ENV_FILE="${RUN_DIR}/alpaca.env"
UV_VERSION="0.12.15"     # = quantt/deploy/vm/bootstrap.sh
PY_VERSION="3.13.5"      # = quantt/deploy/vm/bootstrap.sh
TZ_NAME="America/New_York"
UNIT_DIR="${ROOT:-}/etc/systemd/system"
BRANCH="shadow"
VAULT=""
ENABLE=0

die() { echo "REFUSED: $*" >&2; exit 2; }
step() { echo "== $*"; }
as_shadow() { runuser -u "${SVC_USER}" -- env HOME="${HOME_DIR}" "$@"; }

parse() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --vault) VAULT="${2:?--vault needs a name}"; shift 2 ;;
      --branch) BRANCH="${2:?--branch needs a name}"; shift 2 ;;
      --enable) ENABLE=1; shift ;;
      *) die "unknown argument '$1'" ;;
    esac
  done
  [[ -n "${VAULT}" ]] || die "usage: sudo bash $0 --vault <vault-name> [--branch shadow] [--enable]"
  [[ "${VAULT}" =~ ^[A-Za-z0-9][A-Za-z0-9-]*$ ]] || die "vault '${VAULT}' is not a plain vault name"
  [[ "${BRANCH}" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ ]] || die "branch '${BRANCH}' is not a plain branch name"
}

step_checks() {
  [[ ${EUID} -eq 0 ]] || die "run as root"
  [[ "$(timedatectl show -p Timezone --value)" == "${TZ_NAME}" ]] \
    || die "system zone is not ${TZ_NAME}; the timer is New York wall-clock time"
  local jobs active
  jobs="$(systemctl list-jobs --no-legend 'quantt-*')" || die "cannot list systemd jobs"
  [[ -z "${jobs}" ]] || die "a quantt job is queued or running: ${jobs}"
  active="$(systemctl list-units --type=service --state=activating,running --no-legend 'quantt-cef-*' 'quantt-c4-*' | awk '{print $1}' | tr '\n' ' ')"
  [[ -z "${active// /}" ]] || die "prod job running: ${active}; run this outside prod's windows"
}

step_user() {
  step "user ${SVC_USER}"
  if getent group "${SVC_USER}" >/dev/null && ! id -u "${SVC_USER}" >/dev/null 2>&1; then
    die "a group named ${SVC_USER} exists without the user; refusing to join a group this script did not make"
  fi
  id -u "${SVC_USER}" >/dev/null 2>&1 \
    || useradd --create-home --home-dir "${HOME_DIR}" --shell /usr/sbin/nologin "${SVC_USER}"
  chmod 750 "${HOME_DIR}"
  as_shadow mkdir -p "${STATE}/panels" "${LOGS}"
  chmod 700 "${STATE}"
}

step_python() {
  step "uv ${UV_VERSION} and Python ${PY_VERSION}"
  [[ -x "${UV_VENV}/bin/pip" ]] || as_shadow python3 -m venv "${UV_VENV}"
  as_shadow "${UV_VENV}/bin/pip" install --only-binary=:all: "uv==${UV_VERSION}"
  as_shadow "${UV}" python install "${PY_VERSION}"
  [[ -x "${VENV}/bin/python" ]] || as_shadow "${UV}" venv --python "${PY_VERSION}" "${VENV}"
  local got
  got="$(as_shadow "${VENV}/bin/python" -c 'import platform; print(platform.python_version())')"
  [[ "${got}" == "${PY_VERSION}" ]] || die "venv python is ${got}, expected ${PY_VERSION}"
}

step_clone() {
  step "clone following ${BRANCH}"
  if [[ ! -d "${CLONE}/.git" ]]; then
    as_shadow git clone --quiet "${ORIGIN}" "${CLONE}"
  fi
  [[ -z "$(as_shadow git -C "${CLONE}" status --porcelain)" ]] \
    || die "${CLONE} has local modifications; it is the branch and nothing else"
  as_shadow git -C "${CLONE}" fetch --quiet origin "${BRANCH}" \
    || die "branch '${BRANCH}' is not on ${ORIGIN}; push it first"
  as_shadow git -C "${CLONE}" checkout --quiet --detach FETCH_HEAD
  [[ -f "${CLONE}/shadow/nightly.py" ]] || die "${BRANCH} has no shadow/nightly.py"
}

step_requirements() {
  step "Python packages from the clone's requirements.txt (wheels only)"
  as_shadow "${UV}" pip install --no-build --python "${VENV}/bin/python" -r "${CLONE}/requirements.txt"
  as_shadow sh -c 'sha256sum "$1" | cut -d" " -f1 > "$2"' _ "${CLONE}/requirements.txt" "${VENV}/.requirements.sha256"
}

step_units() {
  step "systemd units"
  mkdir -p "${UNIT_DIR}"
  cat > "${UNIT_DIR}/quantt-shadow-secret.service" <<UNIT
# quantt-shadow-secret.service : a COPY of the core (cef) account's Alpaca key, from the
# vault into ${ENV_FILE} (tmpfs). WRITTEN by shadow/deploy/install_shadow_vm.sh; re-run it
# rather than hand-editing. The shadow runner only reads market data with it.
[Unit]
Description=QUANTT shadow runner: data key into ${RUN_DIR}
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=${SVC_USER}
Group=${SVC_USER}
RuntimeDirectory=quantt-shadow
RuntimeDirectoryMode=0700
WorkingDirectory=${CLONE}
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV}/bin/python -m quantt.deploy.boot_secrets --provider azure-keyvault --config vault=${VAULT} --secret alpaca-cef-key-id=ALPACA_CEF_KEY_ID --secret alpaca-cef-secret-key=ALPACA_CEF_SECRET_KEY --out ${ENV_FILE}
StandardOutput=append:${LOGS}/secret.out.log
StandardError=append:${LOGS}/secret.err.log

[Install]
WantedBy=multi-user.target
UNIT
  cat > "${UNIT_DIR}/quantt-shadow.service" <<UNIT
# quantt-shadow.service : update the clone to ${BRANCH}, then run every shadow book.
# WRITTEN by shadow/deploy/install_shadow_vm.sh. Simulated books: it sends no order.
[Unit]
Description=QUANTT shadow books (branch ${BRANCH})
Wants=quantt-shadow-secret.service
After=quantt-shadow-secret.service

[Service]
Type=oneshot
User=${SVC_USER}
Group=${SVC_USER}
WorkingDirectory=${CLONE}
Environment=SHADOW_STATE_DIR=${STATE}
Environment=QUANTT_ENV_FILE=${ENV_FILE}
Environment=SHADOW_BRANCH=${BRANCH}
Environment=SHADOW_PYTHON=${VENV}/bin/python
Environment=PYTHONUNBUFFERED=1
ExecStart=/bin/bash ${CLONE}/shadow/deploy/nightly.sh
Nice=10
MemoryHigh=300M
MemoryMax=450M
CPUQuota=60%
TimeoutStartSec=1500
StandardOutput=append:${LOGS}/nightly.out.log
StandardError=append:${LOGS}/nightly.err.log
UNIT
  cat > "${UNIT_DIR}/quantt-shadow.timer" <<UNIT
# quantt-shadow.timer : New York wall-clock time. Two evening runs after the close (the
# second catches a panel published late) and a morning backstop before the open. A
# decision written by any of them is on time (shadow/engine.py: before 13:00 on the fill
# date). Persistent=false: a missed run is not replayed at boot into one of prod's windows.
[Unit]
Description=QUANTT shadow books schedule

[Timer]
OnCalendar=Mon..Fri *-*-* 18:50:00
OnCalendar=Mon..Fri *-*-* 20:50:00
OnCalendar=Tue..Sat *-*-* 07:20:00
AccuracySec=1s
Persistent=false
Unit=quantt-shadow.service

[Install]
WantedBy=timers.target
UNIT
  systemctl daemon-reload
  systemctl enable quantt-shadow-secret.service >/dev/null
}

step_enable() {
  if [[ ${ENABLE} -eq 1 ]]; then
    step "enable the timer"
    systemctl enable --now quantt-shadow.timer
  else
    echo "timer NOT enabled (no --enable). To start it: sudo systemctl enable --now quantt-shadow.timer"
  fi
}

main() {
  parse "$@"
  step_checks
  step_user
  cd "${HOME_DIR}"
  step_python
  step_clone
  step_requirements
  step_units
  step_enable
  cat <<DONE

shadow runner installed: ${CLONE} following ${BRANCH}, state in ${STATE}.
Check it once by hand:
  sudo systemctl start quantt-shadow-secret.service && sudo systemctl start quantt-shadow.service
  sudo tail -n 20 ${LOGS}/nightly.out.log ${LOGS}/nightly.err.log
DONE
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
