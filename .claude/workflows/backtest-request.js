export const meta = {
  name: 'backtest-request',
  description: 'Backtest department: answer one backtest question on the canonical harness, then have it independently re-derived and reviewed',
  whenToUse: 'Run with args = the question (e.g. "band 4.8% vs 6% on the core universe, gross, early against late"). Report only; changes no spec and sends no order.',
  phases: [
    { title: 'Run', detail: 'canonical harness: gross headline, time split, exposures, capacity' },
    { title: 'Check', detail: 'independent re-derivation + review' },
    { title: 'Report', detail: 'one table, provenance labelled' },
  ],
}

// WHY TWO RUNS. "Double-check anything that drives a decision — a second
// method" (CLAUDE.md data rules). The second agent re-derives the headline
// without reading the first agent's script, so a shared bug cannot agree with
// itself. Disagreement is reported, never averaged.

const Q = typeof args === 'string' ? args : (args && args.question)
if (!Q) throw new Error('backtest-request needs args = the question')

phase('Run')
const run = await agent(`Backtest question: "${Q}".
Use the /harness skill: scripts/research/harness.py (evaluate, report, cross_sectional_weights, event_weights), or for the CEF sleeve scripts/cef/band_frontier.py (build_targets, band, band_gross_capped, evaluate, total_returns); shift(2) for anything traded at the close, total returns, live parameters from scripts/cef/spec.py (never literals). If the question needs data beyond data/cef (e.g. CRSP, TRACE, factors), use src/data/r2.py per docs/DATA.md, read-only. Output under results/backtests/<slug>/, never data/. Report GROSS only, with no cost, borrow or slippage assumption (CLAUDE.md, Hard rules, research): the headline (ann %, vol, SR, maxDD, hit rate, turn/yr); the same row for an early and a late period; at least two market regimes, the label built from past data only; eras where the sample allows; factor exposures (equity, rates, credit) and correlation with the sleeves held, reported and not a veto; position size against ADV at $1M, $5M and $10M; each panel's last date. Return the table, the reproducer command and the exact definitions used.`,
  { label: 'harness-run', phase: 'Run' })

phase('Check')
const [rederive, review] = await parallel([
  () => agent(`Independently re-derive ONLY the headline gross Sharpe and annual return for this backtest question, WITHOUT reading any script under results/backtests/ or scripts written today: "${Q}". Use the canonical harness functions directly. Then compare to this reported result and state agree/disagree with the numbers side by side: ${run}`,
    { label: 're-derive', phase: 'Check' }),
  () => agent(`Review this backtest for lookahead (including publication lags in the data), alignment, stale or untradable prices, silent fallbacks, unit errors and harness deviations. Question: "${Q}". Result: ${run}`,
    { label: 'quant-reviewer', phase: 'Check', agentType: 'quant-reviewer' }),
])

phase('Report')
const report = await agent(`Write the final report for the team lead to results/backtests/<slug>/REPORT.md and return its text. Question: "${Q}". Run: ${run}. Independent re-derivation: ${rederive}. Review: ${review}. Label every figure [V]/[S]/[U]; if the re-derivation disagrees or the review found a real defect, say so at the top and do not present the number as established.`,
  { label: 'report', phase: 'Report' })
return { run, rederive, review, report }
