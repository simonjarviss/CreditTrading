#!/bin/bash
# Gate 0 of PREREG_C4_LEVEL, pull 2: dead C4-family CEFs' period-end NAVs from EDGAR N-CSR/N-CSRS.
# The team lead's run: needs SEC_USER_AGENT in $QUANTT_ENV_FILE (never printed) and pull 1's
# _cache_gate0/. INDEX_CACHE (optional) = the census's index_extra_*.parquet for 2008-Q1 on.
# Writes only gitignored caches; about 1-2 hours [U]; a rerun resumes from the EDGAR cache.
set -euo pipefail
: "${QUANTT_ENV_FILE:?set QUANTT_ENV_FILE to the absolute path of the env file holding SEC_USER_AGENT}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
cd "$ROOT"
ARGS=()
if [ -n "${INDEX_CACHE:-}" ]; then ARGS=(--index-cache "$INDEX_CACHE"); fi
python3 -B results/cef/screens_2026-11-02/gate0_pull_ncsr.py --self-test
for attempt in 1 2 3 4 5; do
    echo "== N-CSR pull (attempt $attempt)"
    if python3 -B results/cef/screens_2026-11-02/gate0_pull_ncsr.py ${ARGS[@]+"${ARGS[@]}"}; then   # bash 3.2 (macOS): an empty array under set -u
        echo "== done: results/cef/screens_2026-11-02/_cache_gate0/ncsr_manifest.json"; exit 0
    fi
    echo "   failed; retrying in 60 s (cached responses are not re-fetched)"; sleep 60
done
echo "== N-CSR pull FAILED after 5 attempts"; exit 1
