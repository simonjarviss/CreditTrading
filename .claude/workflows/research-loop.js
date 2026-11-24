export const meta = {
  name: 'research-loop',
  description: 'RETIRED 2026-11-09. The daily autonomous research cycle ran the pre-registration and trial-counter process the team lead dropped that day. It stops at its gate and does nothing',
  whenToUse: 'Never. Kept only so that an installed scheduler job that still calls it stops cleanly. The replacements are the nightly scoreboard and the weekly hunt (the /scoreboard and /hunt skills), which are proposed to the team before anything is scheduled.',
  phases: [
    { title: 'Gate', detail: 'returns STOPPED: retired 2026-11-09' },
  ],
}

// WHY THIS FILE STILL EXISTS (2026-11-09).
// The team lead's ruling of 2026-11-09 (docs/SYSTEM.md §5; docs/MISSION.md §1)
// dropped pre-registration, the trial counters and their bars, and the holdout
// ceremony for research. This workflow was that process run unattended: pick an
// idea, draft and self-approve a pre-registration, spend a counted trial, record
// the bar. It must not run again in that form.
//
// It is stubbed, not deleted, because other things still point at it:
// - .claude/loop/run_research_loop.sh and its launchd template start a headless
//   session that runs "the research-loop workflow". Only the team lead installs
//   or unloads that job, in a separate clone, so an agent cannot know it is
//   unloaded. A missing workflow would fail in a way that depends on the session;
//   a workflow that returns STOPPED is a defined outcome.
// - docs/SYSTEM.md §5 and results/research/loop/STATE.md cite both paths as
//   history, and ops.doc_audit checks that paths cited there exist.
//
// The stop is unconditional and uses no agent, so it cannot spend anything, write
// anything or reach the order path. The former body is in git history
// (git log -- .claude/workflows/research-loop.js).
//
// The mission's scheduled tasks (docs/MISSION.md §9: nightly data freshness and
// scoreboard, weekly hunt and combined-book review, monthly literature sweep) are
// to be proposed to the team first, and the scoreboard waits on the paper/shadow
// runner, which is not built or approved yet.

const REASON = 'retired 2026-11-09, rebuilt as nightly scoreboard / weekly hunt'
const A = args || {}
phase('Gate')
log(`research-loop STOPPED: ${REASON}`)
return { date: A.date || null, outcome: 'STOPPED', stage: 'gate', reason: REASON,
  next: 'Nothing to do. The team lead may unload the com.quantt.research-loop job. See the /hunt and /scoreboard skills.' }
