#!/bin/sh
# Root install of the public site (team lead, 2026-11-23: eventdriven.quantt.ca, "website all can
# see", served from the VM) on the prod VM.
#
#   sudo sh install_site_vm.sh --hosts "<name> [<name> ...]"
#   sudo sh install_site_vm.sh uninstall
#
# Run the copy inside the prod clone, so the installer and the site code are the same release.
# The host names are arguments and never written in the repository (CLAUDE.md, "Where it runs").
#
# WHAT IT MAKES (no unit, file or state of any trading book is written, started or stopped)
#   caddy (Ubuntu package)          the web server, user `caddy`, static files only. Its Caddyfile
#                                   is rendered from dashboard/deploy/Caddyfile.tmpl. Let's Encrypt
#                                   certificates for each host name, automatically.
#   /srv/quantt-site                what Caddy serves: builds/<stamp>/ and the link `current`.
#                                   Owned by quantt (it writes builds), world-readable.
#   quantt-site.service             as user quantt, from the prod clone at its release tag:
#                                   python3 -m dashboard.export  (records -> snapshot)
#                                   python3 -m dashboard.site    (snapshot -> pages, atomic swap)
#   quantt-site.timer               every 30 minutes, at :20 and :50 New York time.
#
# WHY THE BUILD CANNOT TOUCH THE BOOK. The service runs with PrivateNetwork=yes (no network at
# all, so no broker call is possible), ProtectHome=read-only (the state directories and the clone
# are read-only to it), ProtectSystem=strict and one writable path, /srv/quantt-site. It reads no
# key file and holds no key. A failure marks this unit failed and touches nothing else; the site
# keeps the last good build.
#
# WHY THE SHADOW SCOREBOARD IS COPIED BY ROOT. It belongs to quantt-shadow under a 0700 state
# directory. One `install` command, run by systemd as root before the build ("+" prefix), copies
# that single file into the unit's runtime directory for quantt to read. No permission on the
# shadow state changes. If the file is missing the copy fails ("-" prefix: ignored) and the page
# says the scoreboard was not measured.
#
# WHY EVERY 30 MINUTES AT :20 AND :50 (team lead, 2026-11-23: "connected to our live P&L and live
# updates"). The books trade once a day, so their records change a few times a day: the evening
# verifies (17:30 core and C4, 17:35 events), the 17:40 collector, Alpaca's end-of-day history read
# in the night, the 05:45 and 05:50 risk reports, and the shadow runner (18:50, 20:50, 07:20). A
# build every half hour puts each new record on the site within 30 minutes. :20 and :50 stay off
# :00/:30 (sessions) and :10/:40 (collectors): the VM has 1 GiB. A build reads files only, so a
# run in the trading window cannot touch the send.
#
# THE INSTALLER'S UNIT NAMES ARE REGISTERED in quantt/deploy/install_vm.py SITE_UNIT_FILES, so a
# C4 or --reports install does not refuse beside them (pinned by a test).
set -eu

RUN_USER="quantt"
RUN_HOME="/home/${RUN_USER}"
PROD="${RUN_HOME}/prod/quantt-alpaca"          # = quantt/deploy/install_vm.py Layout.prod_dir
STATE_ROOT="${RUN_HOME}/quantt_state"
SHADOW_SCOREBOARD="/home/quantt-shadow/shadow_state/SCOREBOARD.md"
SITE_ROOT="/srv/quantt-site"
TZ_NAME="America/New_York"
UNIT_DIR="/etc/systemd/system"
PY="/usr/bin/python3"
CADDYFILE="/etc/caddy/Caddyfile"

MODE="install"
HOSTS=""

die() { echo "REFUSED: $*" >&2; exit 2; }
step() { echo "== $*"; }
as_quantt() { runuser -u "${RUN_USER}" -- env HOME="${RUN_HOME}" "$@"; }

parse() {
  while [ $# -gt 0 ]; do
    case "$1" in
      install) MODE="install"; shift ;;
      uninstall) MODE="uninstall"; shift ;;
      --hosts) [ $# -ge 2 ] || die "--hosts needs one or more names"; HOSTS="$2"; shift 2 ;;
      *) die "unknown argument '$1'" ;;
    esac
  done
  if [ "${MODE}" = "install" ]; then
    [ -n "${HOSTS}" ] || die "usage: sudo sh $0 --hosts \"<name> [<name> ...]\"   |   sudo sh $0 uninstall"
    for h in ${HOSTS}; do
      case "${h}" in
        *[!a-z0-9.-]*|-*|*.|.*|*..*) die "host '${h}' is not a plain lower-case DNS name" ;;
        *.*) ;;
        *) die "host '${h}' has no dot" ;;
      esac
    done
  fi
}

check_root() {
  [ "$(id -u)" -eq 0 ] || die "run as root (sudo)"
  command -v systemctl >/dev/null 2>&1 || die "systemctl not found; this is for the systemd VM"
  command -v runuser >/dev/null 2>&1 || die "runuser not found"
  [ "$(timedatectl show -p Timezone --value)" = "${TZ_NAME}" ] \
    || die "system zone is not ${TZ_NAME}; the timer is New York wall-clock time"
  [ -x "${PY}" ] || die "${PY} not found"
  "${PY}" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
    || die "${PY} is older than 3.10"
}

check_clone() {
  [ -f "${PROD}/dashboard/site.py" ] || die "${PROD}/dashboard/site.py not found: install a release that has the site"
  [ -f "${PROD}/dashboard/deploy/Caddyfile.tmpl" ] || die "Caddyfile template missing in ${PROD}"
  here="$(cd "$(dirname "$0")" && pwd -P)"
  [ "${here}" = "$(cd "${PROD}/dashboard/deploy" && pwd -P)" ] \
    || die "run the copy inside the prod clone (${PROD}/dashboard/deploy), not ${here}"
}

unit_file() {
  # unit_file <name> <<EOF ... EOF : write atomically, mode 0644
  tmp="${UNIT_DIR}/.$1.tmp"
  cat > "${tmp}"
  chmod 0644 "${tmp}"
  mv -f "${tmp}" "${UNIT_DIR}/$1"
}

install_caddy() {
  if ! command -v caddy >/dev/null 2>&1; then
    step "installing caddy from Ubuntu's archive"
    DEBIAN_FRONTEND=noninteractive apt-get update -q
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q caddy
  fi
  command -v caddy >/dev/null 2>&1 || die "caddy did not install"
  id caddy >/dev/null 2>&1 || die "user caddy missing after install"
  # caddy must not be able to read the trading state: check rather than assume.
  if runuser -u caddy -- test -r "${STATE_ROOT}"; then
    die "user caddy can read ${STATE_ROOT}; fix its mode before exposing a web server"
  fi
}

write_units() {
  step "writing quantt-site.service and quantt-site.timer"
  unit_file quantt-site.service <<EOF
# quantt-site.service: the public site's nightly build. READ ONLY on every trading record.
# RENDERED by dashboard/deploy/install_site_vm.sh. Do not hand-edit the installed copy.
[Unit]
Description=QUANTT public site: snapshot of the books' records and the static pages

[Service]
Type=oneshot
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${PROD}
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONUNBUFFERED=1
RuntimeDirectory=quantt-site
RuntimeDirectoryMode=0750
ExecStartPre=-+/usr/bin/install -m 0640 -o ${RUN_USER} -g ${RUN_USER} ${SHADOW_SCOREBOARD} /run/quantt-site/SCOREBOARD.md
ExecStart=${PY} -B -m dashboard.export --state-root ${STATE_ROOT} --shadow-scoreboard /run/quantt-site/SCOREBOARD.md -o /run/quantt-site/snapshot.json
ExecStart=${PY} -B -m dashboard.site --snapshot /run/quantt-site/snapshot.json --out ${SITE_ROOT}
PrivateNetwork=yes
IPAddressDeny=any
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=${SITE_ROOT}
PrivateTmp=yes
NoNewPrivileges=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
MemoryMax=300M
Nice=10
TimeoutStartSec=300
EOF
  unit_file quantt-site.timer <<EOF
# quantt-site.timer: every 30 minutes at :20 and :50, New York wall clock (the system zone).
# RENDERED by dashboard/deploy/install_site_vm.sh. Do not hand-edit the installed copy.
[Unit]
Description=QUANTT public site build schedule

[Timer]
OnCalendar=*-*-* *:20,50:00
AccuracySec=1s
Persistent=false
Unit=quantt-site.service

[Install]
WantedBy=timers.target
EOF
}

write_caddyfile() {
  step "rendering ${CADDYFILE} for: ${HOSTS}"
  [ -f "${CADDYFILE}.dist" ] || { [ -f "${CADDYFILE}" ] && cp -p "${CADDYFILE}" "${CADDYFILE}.dist"; } || true
  hosts_line="$(echo ${HOSTS} | sed 's/ /, /g')"
  tmp="${CADDYFILE}.tmp"
  sed "s|{{HOSTS}}|${hosts_line}|" "${PROD}/dashboard/deploy/Caddyfile.tmpl" > "${tmp}"
  grep -q '{{' "${tmp}" && die "the Caddyfile still has an unfilled placeholder"
  caddy validate --adapter caddyfile --config "${tmp}" >/dev/null || die "caddy rejects the rendered Caddyfile (${tmp})"
  chmod 0644 "${tmp}"
  mv -f "${tmp}" "${CADDYFILE}"
}

do_install() {
  check_root
  check_clone
  install_caddy
  step "site root ${SITE_ROOT}"
  install -d -m 0755 -o "${RUN_USER}" -g "${RUN_USER}" "${SITE_ROOT}"
  write_units
  systemctl daemon-reload
  step "first build"
  systemctl start quantt-site.service || die "the first build failed: journalctl -u quantt-site.service"
  [ -L "${SITE_ROOT}/current" ] || die "the build left no ${SITE_ROOT}/current"
  write_caddyfile
  systemctl enable caddy >/dev/null 2>&1
  systemctl restart caddy
  systemctl enable --now quantt-site.timer
  step "done. caddy: $(systemctl is-active caddy); timer: $(systemctl is-active quantt-site.timer)"
  systemctl list-timers quantt-site.timer --no-pager | sed -n 1,3p
}

do_uninstall() {
  check_root
  systemctl disable --now quantt-site.timer 2>/dev/null || true
  rm -f "${UNIT_DIR}/quantt-site.service" "${UNIT_DIR}/quantt-site.timer"
  systemctl daemon-reload
  systemctl disable --now caddy 2>/dev/null || true
  step "units removed and caddy stopped; ${SITE_ROOT} and the caddy package are left in place"
}

parse "$@"
case "${MODE}" in
  install) do_install ;;
  uninstall) do_uninstall ;;
esac
