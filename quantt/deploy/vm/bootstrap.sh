#!/usr/bin/env bash
# One-time root bootstrap of a fresh prod VM (Ubuntu 24.04 LTS; Debian 12 also accepted).
#
#   curl -fsSLo bootstrap.sh \
#     https://raw.githubusercontent.com/quanttqueensu/CreditTrading/<TAG>/quantt/deploy/vm/bootstrap.sh
#   less bootstrap.sh            # read it before running it as root
#   sudo bash bootstrap.sh <TAG>
#
# WHY: install_vm.py builds prod from a release tag, but it needs a machine that
# already has the service user, Python 3.13.5 and the clone. This script makes
# that machine, and nothing else. It knows nothing about the cloud it runs on:
# every provider-specific piece (the key fetch) lives in quantt/deploy/azure_keyvault.py.
#
# What it sets, and why:
#   timezone America/New_York  the timers are ET wall-clock time; install_vm refuses
#                              any other zone.
#   unattended-upgrades        security updates stay on, with Automatic-Reboot "false":
#                              a reboot at 15:52 ET is a missed send, so reboot by hand,
#                              on a weekend. Both apt timers (download and upgrade) are
#                              moved to 02:00-02:30 ET, outside the job windows: decide
#                              22:00-01:00, backstop 06:00-15:15, send 15:52-15:58,
#                              verify 17:30. Persistent=false, so neither replays a
#                              missed run at boot.
#   needrestart list-only      it must never restart a service on its own after an upgrade.
#   2 GB swap                  the VM has 1 GiB of RAM, and the test suite peaked at
#                              568 MB RSS on the laptop (2026-10-07). Not encrypted by
#                              us: the kernel can page the tmpfs key file here (see
#                              boot_secrets.py; Azure disks are encrypted at rest [S]).
#   user quantt                owns the clone, the venv and the state; no login shell.
#   uv + Python 3.13.5         the laptop prod's interpreter (RUNBOOK section 0.3). uv is
#                              pinned and installed from a wheel via pip; there is no
#                              curl | sh.
#   the clone                  the repository at <TAG>, detached, with requirements.txt
#                              installed from wheels only (--no-build).
#
# Re-running: it takes the install lock (the same one install_vm takes), and
# refuses while any quantt timer runs or any quantt job runs or is queued,
# because it reinstalls packages into the venv. With prod stopped, the system
# steps (zone, apt settings, swap, user, uv, Python) are safe to repeat. The clone step is NOT a way to update: on an existing clone it
# refuses unless HEAD is already the tag's commit. Moving prod from one tag to
# another is install_vm's job, with its checks (docs/RUNBOOK.md section 8.6).
#
# Architecture: nothing here is architecture-specific. The prod VM is aarch64
# (Azure Standard_B2pts_v2, 2026-10-07). Measured 2026-10-07 for that VM:
#   * uv lists cpython-3.13.5-linux-aarch64-gnu;
#   * uv 0.12.15 and every compiled package in requirements.txt has a manylinux
#     aarch64 cp313 wheel on PyPI. So do yfinance's own compiled dependencies,
#     curl_cffi, protobuf and websockets (PyPI JSON API).
# With --no-build and --only-binary, a missing wheel fails the install loudly
# instead of starting a compile the 1 GiB VM cannot finish.
#
# Sourcing this file defines the steps and runs nothing (the tests source it with
# stubs); executing it runs main.
set -euo pipefail

ORIGIN="https://github.com/quanttqueensu/CreditTrading.git"
SVC_USER="quantt"
HOME_DIR="/home/${SVC_USER}"
PROD="${HOME_DIR}/prod/quantt-alpaca"
VENV="${HOME_DIR}/venv"
UV_VENV="${HOME_DIR}/.uv"
UV="${UV_VENV}/bin/uv"
TZ_NAME="America/New_York"
UV_VERSION="0.12.15"    # released 2026-09-15 [V: GitHub releases API, read 2026-10-07]
PY_VERSION="3.13.5"
SWAP_FILE="/swapfile"
SWAP_SIZE="2G"
ROOT="${ROOT:-}"        # prefix for the files step_apt writes; empty on the VM, a tmp dir in tests
REQUIREMENTS_RECORD=".quantt-requirements.sha256"   # = install_vm.REQUIREMENTS_RECORD
LOCK_FILE="/run/lock/quantt-install.lock"             # = install_vm.INSTALL_LOCK

die() { echo "REFUSED: $*" >&2; exit 2; }
step() { echo "== $*"; }
as_quantt() { runuser -u "${SVC_USER}" -- env HOME="${HOME_DIR}" "$@"; }

step_checks() {
  [[ ${EUID} -eq 0 ]] || die "run as root: sudo bash $0 ${TAG}"
  [[ "${TAG}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || die "tag '${TAG}' is not a plain tag name"
  # shellcheck disable=SC1091
  . /etc/os-release
  case "${ID}:${VERSION_ID}" in
    ubuntu:24.04|debian:12) ;;
    *) die "untested OS ${ID} ${VERSION_ID}; expected Ubuntu 24.04 or Debian 12" ;;
  esac
}

step_lock() {
  # One install or bootstrap at a time: the same lock install_vm takes
  # (INSTALL_LOCK). Held on fd 9 until this script exits. Opened for append,
  # so the holder's pid is not wiped before we own the lock.
  mkdir -p "$(dirname "${ROOT}${LOCK_FILE}")"
  exec 9>>"${ROOT}${LOCK_FILE}"
  if ! flock -n 9; then
    local holder
    holder="$(cat "${ROOT}${LOCK_FILE}")"
    die "another install or bootstrap is running (lock ${LOCK_FILE}, held by pid ${holder:-unknown})"
  fi
  printf '%s\n' "$$" > "${ROOT}${LOCK_FILE}"
}

step_not_live() {
  # A re-run reinstalls packages into the venv, so it must never happen under
  # a live book: not with a timer running, and not with a quantt job running
  # or queued. `is-active` misses a queued start, hence list-jobs (measured on
  # the VM 2026-10-08, install_vm.py parser comment).
  local u busy="" jobs
  for u in quantt-cef-session.timer quantt-cef-verify.timer quantt-cef-collect.timer \
           quantt-cef-session.service quantt-cef-verify.service quantt-cef-collect.service; do
    if systemctl is-active --quiet "${u}"; then busy="${busy} ${u}"; fi
  done
  jobs="$(systemctl list-jobs --no-legend 'quantt-*')" || die "cannot list systemd jobs"
  [[ -z "${jobs}" ]] || busy="${busy} (queued: ${jobs})"
  [[ -z "${busy}" ]] \
    || die "prod is live:${busy}. Stop the timers and wait for the jobs first (docs/RUNBOOK.md 8.6 step 1)"
}

step_timezone() {
  step "timezone ${TZ_NAME}"
  timedatectl set-timezone "${TZ_NAME}"
}

step_packages() {
  step "packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q
  # `acl` (setfacl, getfacl): the events book's installer grants user quantt a read-only ACL on
  # the shadow books' decisions and refuses without it (quantt/sleeves/deploy/install_events_vm.sh).
  # The first VM was bootstrapped before that installer existed, so on 2026-11-20 the package
  # was added there by hand (EVIDENCE_LOG E-2026-11-20-10); a new VM gets it here.
  apt-get install -y -q git ca-certificates python3-venv unattended-upgrades acl
}

step_apt() {
  step "unattended-upgrades: no automatic reboot; apt timers at 02:00-02:30 ET"
  mkdir -p "${ROOT}/etc/apt/apt.conf.d"
  cat > "${ROOT}/etc/apt/apt.conf.d/52quantt" <<'EOF'
// quantt (quantt/deploy/vm/bootstrap.sh): a reboot at 15:52 ET is a missed send.
Unattended-Upgrade::Automatic-Reboot "false";
EOF
  local timer
  for timer in apt-daily.timer apt-daily-upgrade.timer; do
    mkdir -p "${ROOT}/etc/systemd/system/${timer}.d"
    cat > "${ROOT}/etc/systemd/system/${timer}.d/quantt.conf" <<'EOF'
# quantt (quantt/deploy/vm/bootstrap.sh): outside every job window.
[Timer]
OnCalendar=
OnCalendar=*-*-* 02:00
RandomizedDelaySec=30m
# never replay a missed run at boot, which could land inside a job window
Persistent=false
EOF
  done
  if [[ -d "${ROOT}/etc/needrestart" ]]; then
    mkdir -p "${ROOT}/etc/needrestart/conf.d"
    echo "\$nrconf{restart} = 'l';  # quantt: list only, never restart services" \
      > "${ROOT}/etc/needrestart/conf.d/quantt.conf"
  fi
  systemctl daemon-reload
}

step_swap() {
  step "swap ${SWAP_SIZE} at ${SWAP_FILE}"
  if ! swapon --show=NAME --noheadings | grep -qx "${SWAP_FILE}"; then
    if [[ ! -e "${SWAP_FILE}" ]]; then
      fallocate -l "${SWAP_SIZE}" "${SWAP_FILE}"
      chmod 600 "${SWAP_FILE}"
      mkswap "${SWAP_FILE}"
    fi
    swapon "${SWAP_FILE}"
  fi
  grep -q "^${SWAP_FILE} " /etc/fstab || echo "${SWAP_FILE} none swap sw 0 0" >> /etc/fstab
}

step_user() {
  step "user ${SVC_USER}"
  id -u "${SVC_USER}" >/dev/null 2>&1 \
    || useradd --create-home --home-dir "${HOME_DIR}" --shell /usr/sbin/nologin "${SVC_USER}"
  chmod 750 "${HOME_DIR}"
}

step_python() {
  step "uv ${UV_VERSION} and Python ${PY_VERSION}"
  [[ -x "${UV_VENV}/bin/pip" ]] || as_quantt python3 -m venv "${UV_VENV}"
  as_quantt "${UV_VENV}/bin/pip" install --only-binary=:all: "uv==${UV_VERSION}"
  as_quantt "${UV}" python install "${PY_VERSION}"
  [[ -x "${VENV}/bin/python" ]] || as_quantt "${UV}" venv --python "${PY_VERSION}" "${VENV}"
  local got
  got="$(as_quantt "${VENV}/bin/python" -c 'import platform; print(platform.python_version())')"
  [[ "${got}" == "${PY_VERSION}" ]] || die "venv python is ${got}, expected ${PY_VERSION}"
}

step_clone() {
  step "prod clone at ${TAG}"
  if [[ -d "${PROD}/.git" ]]; then
    [[ -z "$(as_quantt git -C "${PROD}" status --porcelain)" ]] \
      || die "${PROD} has local modifications; prod is the repository at a tag and nothing else"
    local head want
    head="$(as_quantt git -C "${PROD}" rev-parse HEAD)"
    want="$(as_quantt git -C "${PROD}" rev-parse --verify --quiet "refs/tags/${TAG}^{commit}" || true)"
    [[ -n "${want}" && "${head}" == "${want}" ]] \
      || die "${PROD} exists at ${head}, not at ${TAG}; bootstrap does not move a clone between tags. Use install_vm (docs/RUNBOOK.md section 8.6)"
    return 0
  fi
  as_quantt mkdir -p "$(dirname "${PROD}")"
  as_quantt git clone --quiet "${ORIGIN}" "${PROD}"
  as_quantt git -C "${PROD}" checkout --quiet --detach "refs/tags/${TAG}"
}

step_requirements() {
  # --no-build: a package without a wheel fails here, loudly, instead of
  # compiling on a 1 GiB VM. Not --quiet: a failure must show what failed.
  step "Python packages from ${TAG}'s requirements.txt (wheels only)"
  as_quantt "${UV}" pip install --no-build --python "${VENV}/bin/python" -r "${PROD}/requirements.txt"
  # Record WHICH requirements.txt the venv was built from. install_vm refuses
  # a tag whose requirements.txt hashes differently (install_vm.REQUIREMENTS_RECORD).
  local digest
  digest="$(sha256sum "${PROD}/requirements.txt" | cut -d' ' -f1)"
  as_quantt sh -c 'printf "%s\n" "$1" > "$2"' _ "${digest}" "${VENV}/${REQUIREMENTS_RECORD}"
}

main() {
  TAG="${1:?usage: sudo bash bootstrap.sh <release-tag>}"
  step_checks
  step_lock
  step_not_live
  step_timezone
  step_packages
  step_apt
  step_swap
  step_user
  cd "${HOME_DIR}"     # runuser keeps the working directory; quantt cannot read root's
  step_python
  step_clone
  step_requirements
  cat <<EOF

bootstrap done: ${PROD} at ${TAG}, Python ${PY_VERSION} in ${VENV}.
Next (docs/RUNBOOK.md section 8.3): copy the laptop prod's data/cef files to this VM, then
  sudo env PYTHONPATH=${PROD} ${VENV}/bin/python -B -P -m quantt.deploy.install_vm \\
    --tag ${TAG} --vault <vault-name> --seed-from <dir>
EOF
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
