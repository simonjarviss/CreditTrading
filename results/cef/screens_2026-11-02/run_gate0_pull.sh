#!/bin/bash
# Gate 0 (survivorship) of PREREG_C4_LEVEL: the team lead's credentialed CRSP pull from R2.
# Read-only; prints row counts and dates, never a credential; writes only the gitignored
# results/cef/screens_2026-11-02/_cache_gate0/. Needs QUANTT_ENV_FILE set to the env file
# that holds the R2 keys (an absolute path); there is no default.
set -euo pipefail
: "${QUANTT_ENV_FILE:?set QUANTT_ENV_FILE to the absolute path of the env file holding the R2 keys}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
cd "$ROOT"
python3 -B results/cef/screens_2026-11-02/gate0_pull_crsp.py --self-test
python3 -B results/cef/screens_2026-11-02/gate0_pull_crsp.py
echo "== Gate 0 pull done: results/cef/screens_2026-11-02/_cache_gate0/manifest.json"
