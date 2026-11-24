#!/usr/bin/env bash
# What quantt-shadow.service runs: move the clone to the branch's head, then run the books.
#
# WHY THE CLONE UPDATES ITSELF: that is the whole point of the shadow path
# (results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md section 2). A new book is a commit
# to the branch; no release, no install. It refuses, loudly, rather than guess, when:
#   * the working tree is not clean (someone edited the clone by hand);
#   * requirements.txt differs from the one the venv was built from. Installing packages
#     from a branch that updates itself is not something a timer should do: the team lead
#     re-runs install_shadow_vm.sh.
# If the fetch fails (network), it runs the books on the code it already has and says so:
# a decision made on yesterday's code is still an honest decision, and a skipped night is
# a hole in the record.
set -euo pipefail
: "${SHADOW_STATE_DIR:?}" "${QUANTT_ENV_FILE:?}" "${SHADOW_BRANCH:?}" "${SHADOW_PYTHON:?}"
cd "$(dirname "$0")/../.."
echo "--- $(date -Is) shadow nightly"
[[ -z "$(git status --porcelain)" ]] || { echo "REFUSED: the clone has local modifications" >&2; exit 2; }
if git fetch --quiet origin "${SHADOW_BRANCH}"; then
  git checkout --quiet --detach FETCH_HEAD
else
  echo "WARNING: could not fetch ${SHADOW_BRANCH}; running on $(git rev-parse --short HEAD)" >&2
fi
want="$(sha256sum requirements.txt | cut -d' ' -f1)"
have="$(cat "$(dirname "${SHADOW_PYTHON}")/../.requirements.sha256")"
[[ "${want}" == "${have}" ]] || { echo "REFUSED: requirements.txt changed; re-run install_shadow_vm.sh" >&2; exit 2; }
echo "code $(git rev-parse --short HEAD)"
exec "${SHADOW_PYTHON}" -B -m shadow nightly
