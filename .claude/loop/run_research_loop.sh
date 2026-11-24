#!/bin/zsh
# research-loop: one daily research cycle (team lead, 2026-10-27: this laptop, one
# idea per day after the close; docs/SYSTEM.md §5).
#
# INSTALLED BY THE TEAM LEAD, NEVER BY AN AGENT. It starts a headless Claude Code
# session, and the permission flags below decide what that session may run.
# Read them before loading the plist (com.quantt.research-loop.plist.tmpl).
#
# WHAT IT REFUSES, WHATEVER THE MODEL DECIDES:
#   NO KEYS. The loop checkout holds no config/.env (it is gitignored and never
#   copied there), so the order runner cannot authenticate from it. That is the
#   structural guard; the deny list below is the second layer.
#   --disallowedTools:
#   python3 -m quantt.session   the order runner, for any book, also by the
#                               interpreter's absolute path. The loop never sends
#                               an order; lab trading is the runner's own scheduled job.
#   git push, gh pr merge       the loop commits on its own branch, and a human
#                               moves anything to main.
#   ssh                         the VM is prod and is reached only by the team lead.
# The Alpaca MCP order tools are already denied in ~/.claude/settings.json.
#
# WHY AUTO MODE AND NOT bypassPermissions: the classifier still screens every
# command the deny list does not name (it blocked an unloaded prod install on
# 2026-10-19).
#
# THE INTERPRETER IS NAMED, NEVER RESOLVED. launchd's login shell finds
# Homebrew's python3, which has no numpy: the first scheduled-path run died on
# it (2026-10-28). QUANTT_LOOP_PYTHON is the absolute path of the interpreter
# with requirements.txt installed, and its bin goes first on PATH, as
# quantt/deploy/install_prod.py does for prod.
#
# NOT UNDER ~/Desktop, ~/Documents OR ~/Downloads. macOS protects them, and a
# launchd job that touched one died with "getcwd: Operation not permitted"
# (2026-07-31, exit 126; docs/RUNBOOK.md). A git worktree of the dev repo does
# not escape it: its git data stays in the dev repo. Install the loop as its own
# clone elsewhere, as prod is (~/prod/QUANTT then). The wrapper logs a WARNING
# when the checkout is in one.
#
# THE WHOLE BODY IS ONE FUNCTION. It merges origin/main into the checkout that
# holds this file; zsh parses a function whole before running it, so a merge
# that rewrites the file cannot change what is executing.
#
# THE TRIAL SERIES MUST BE IN THE LOOP WORKTREE. They are gitignored
# (results/research/trials/series/, the repository is public), so a fresh
# worktree has the ledger's lines but none of the files, and no deflated-Sharpe
# bar can be computed after a trial is spent. Once, at install, copy that
# directory from the checkout that recorded them (on 2026-10-28 the backfill
# worktree, .claude/worktrees/research-backfill). The check below refuses a
# cycle until every ledger line loads with a matching sha256.
set -euo pipefail

main() {
  local WT="${QUANTT_LOOP_WORKTREE:?set QUANTT_LOOP_WORKTREE to the loop checkout (branch research-loop)}"
  local PY="${QUANTT_LOOP_PYTHON:?set QUANTT_LOOP_PYTHON to the absolute path of the interpreter with requirements.txt installed}"
  local LOGS="${QUANTT_LOOP_LOGS:-$HOME/quantt_state/research-loop}"
  mkdir -p "$LOGS"
  local LOG="$LOGS/loop.log"
  if [[ "$PY" != /* || ! -x "$PY" ]]; then
    echo "$(date '+%F %T') QUANTT_LOOP_PYTHON=$PY is not an absolute path to an executable; no cycle" >> "$LOG"; return 6
  fi
  export PATH="${PY:h}:$PATH"            # every python3 below, and in the session, is this one
  local d
  for d in Desktop Documents Downloads; do
    if [[ "$WT/" == "$HOME/$d/"* ]]; then
      echo "$(date '+%F %T') WARNING: $WT is under ~/$d, which macOS protects; under launchd this job may be refused (2026-07-31, exit 126). Install the loop as a clone elsewhere" >> "$LOG"
    fi
  done
  if ! command -v claude >/dev/null; then
    echo "$(date '+%F %T') claude is not on PATH ($PATH); no cycle" >> "$LOG"; return 7
  fi
  cd "$WT"
  local D
  D=$(TZ=America/New_York date +%F)
  if ! "$PY" -c "import sys, datetime as dt; sys.path.insert(0, '.'); from ops.schedule.nyse_calendar import is_trading_day; sys.exit(0 if is_trading_day(dt.date.fromisoformat('$D')) else 3)"; then
    echo "$D not an NYSE session; no cycle" >> "$LOG"; return 0
  fi
  # The loop runs under main's rules: bring them in, and stop on any conflict
  # rather than resolve it unattended.
  git fetch -q origin
  if ! git merge -q --no-edit origin/main; then
    git merge --abort || true
    echo "$D merge of origin/main conflicted; no cycle" >> "$LOG"; return 4
  fi
  # A crash is reported as a crash: on 2026-10-28 a missing numpy read as
  # "series missing or altered".
  if ! "$PY" -m scripts.research.registry verify > "$LOGS/$D.series.json" 2> "$LOGS/$D.series.err"; then
    if "$PY" -c "import json, sys; sys.exit(0 if json.load(open(sys.argv[1])).get('ok') is False else 1)" "$LOGS/$D.series.json" 2>/dev/null; then
      echo "$D trial series missing or altered in $WT (see $D.series.json); no cycle" >> "$LOG"
    else
      echo "$D registry verify could not run (see $D.series.err); no cycle" >> "$LOG"
    fi
    return 5
  fi
  # The workflow runs as a background task of the headless session, and claude -p
  # stops background tasks 10 minutes after its last turn by default: the
  # 2026-10-28 cycle was killed in Pick that way. Unlimited would let a hung
  # cycle hold the job, and launchd starts no new run while one is alive, so
  # the ceiling is 8 hours, well inside the next 17:45.
  export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS="${QUANTT_LOOP_BG_CEILING_MS:-28800000}"
  local rc=0
  claude -p "Run the research-loop workflow with args {\"date\": \"$D\"}. When it returns, print its outcome and the report commit." \
    --permission-mode auto \
    --disallowedTools "Bash(python3 -m quantt.session:*)" "Bash($PY -m quantt.session:*)" "Bash(git push:*)" "Bash(gh pr merge:*)" "Bash(ssh:*)" \
    --output-format json > "$LOGS/$D.json" 2>> "$LOG" || rc=$?
  echo "$D cycle finished (exit $rc)" >> "$LOG"
  return $rc
}

main "$@"
