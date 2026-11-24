export const meta = {
  name: 'daily-ops',
  description: 'Trading desk: read-only morning/evening check of the live book, data freshness and the last session verdict',
  whenToUse: 'Any time; read-only. Pass args = {state_dir: "<QUANTT_STATE_DIR>"} (the prod default is ~/quantt_state/cef).',
  phases: [
    { title: 'Read', detail: 'orient, verdict log, plan, account snapshot' },
    { title: 'Brief', detail: 'what happened, what needs the team lead' },
  ],
}

// WHY. Silence must never read as success (ROADMAP 4.7). This reads what the
// runner wrote and what the broker says, and names every gap. It cannot send an
// order: no step here calls quantt.session run without --preview and DRY_RUN=1.

const STATE = (args && args.state_dir) || '~/quantt_state/cef'
phase('Read')
const read = await agent(`Read-only. Never transmit, never print credentials.
1. python3 -m ops.orient
2. The last 5 lines of ${STATE}/verify.log and the newest ${STATE}/<date>/plan.json (orders, refusals, plan_sha) and orders.jsonl if present; the last 5 rows of ${STATE}/scores.csv.
3. python3 -m quantt.broker.alpaca_probe  (read-only account snapshot; writes results/ops/alpaca_probe/)
4. The prod clone's tag: git -C ~/prod/quantt-alpaca describe --tags; and launchctl print gui/$(id -u)/com.quantt.alpaca.cef.session | head -30 (state only; do not load/unload).
Report each item verbatim-summarised with its date. Anything missing is stated as missing, never inferred.`,
  { label: 'read', phase: 'Read' })
phase('Brief')
return await agent(`From this read-out, write a short brief for the team lead: did the last session trade and verify PASS, positions vs plan, the two P&Ls (Alpaca fill vs auction print, gross, labelled), data freshness, and a list of anything that needs a decision. Label every figure with its source. Read-out: ${read}`,
  { label: 'brief', phase: 'Brief', agentType: 'portfolio-architect' })
