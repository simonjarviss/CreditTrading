export const meta = {
  name: 'research-idea',
  description: 'Explore run: take one idea from its idea card through the data card and audit, a gross test with one time split, regimes, exposures and a capacity table, a code review, to a ledger line and a short report',
  whenToUse: 'Run with args = the idea in one or two sentences, or {idea, slug, card}. card is the path of an existing idea card (results/ideas/YYYY-MM-DD_<slug>.md); without it the run writes one. Set ml: true if the design is a fitted model. One run. It sends no order, starts no paper or shadow book and commits nothing: it returns the files to commit together.',
  phases: [
    { title: 'Card', detail: 'signal-hunter + market-historian-economist: ledger check, the idea card' },
    { title: 'Data', detail: 'data-scout: data card; data-analyst: audit' },
    { title: 'Test', detail: 'signal-hunter or ml-engineer: gross test, time split, regimes, capacity' },
    { title: 'Review', detail: 'quant-reviewer on the code; beta-detector reports exposures and artifacts' },
    { title: 'Report', detail: 'ledger line + short report' },
  ],
}

// WHY THIS SHAPE (rebuilt 2026-11-09).
// The team lead's ruling of 2026-11-09 (docs/SYSTEM.md §5; docs/MISSION.md §1,
// §2, §7) dropped pre-registration, the trial counters and their bars, the gate
// on forecast odds, the holdout ceremony, the cost grid and the factor-exposure
// kill. Paper trading is the filter. The earlier version of this workflow was two
// runs with an approval between them and five adversaries after the test; it is in
// git history. This version is the Explore stage of the pipeline, in one run.
//
// What it keeps, because these are about wrong numbers and not about pessimism:
// - NO LOOKAHEAD. The data card states each source's publication lag, the test
//   asserts the alignment, and the code review checks it.
// - A MISSING RESULT IS NEVER READ AS A CLEAN ONE. A station that returns nothing
//   stops the run (a crashed reviewer once read the same as a clean review).
// - A CORRECTNESS FINDING IS FIXED BEFORE THE RESULT IS WRITTEN UP. The reviewer
//   did not write the code. If it finds a defect that makes a number wrong, the
//   test is re-run once with the finding, and the report says so. If the defect
//   remains, the report's status is NOT ESTABLISHED.
// - THE LEDGER LINE. Every idea tested gets one line in results/IDEA_LEDGER.md in
//   the same commit as the test. It is a record, not a gate.
//
// What it does not do: reject an idea. The only early stops are an idea with no
// stated counterparty or mechanism (there is nothing to test yet), data that does
// not exist or may not be stored, and a series that cannot carry information.
// Each stop says what would reopen it. Exposures are reported, never a veto.
// Nothing here starts a paper or shadow book: that is the /paper skill, which
// refuses until the runner's design approval is recorded in docs/SYSTEM.md §5.

const A = typeof args === 'string' ? { idea: args } : (args || {})
const IDEA = A.idea
if (!IDEA) throw new Error('research-idea needs args = the idea text, or {idea, slug, card, ml}')
const SLUG = A.slug ? ` The slug is "${A.slug}".` : ' Choose a short lower-case slug and use it in every path.'
const need = (x, what) => { if (x === null || x === undefined) throw new Error(`${what} returned nothing; the run stops rather than read a missing result as a clean one`); return x }
const RULES = 'Rules: CLAUDE.md is the authority, as it stands now, especially "Hard rules — research". Gross results only: no cost grid, borrow haircut or slippage assumption. Every figure is fetched or computed now and labelled [V]/[S]/[U] with the panel\'s last date; a figure you do not have is a stated gap. No silent fallbacks. Write nothing under data/. Never open config/.env, never use sudo, never ssh to the VM, and run nothing that can reach the order path. Do not commit.'

const CARD = { type: 'object', properties: {
  proceed: { type: 'boolean' }, slug: { type: 'string' }, card_path: { type: 'string' },
  ledger_neighbour: { type: 'string' }, what_is_different: { type: 'string' },
  mechanism: { type: 'string' }, counterparty: { type: 'string' },
  signal: { type: 'string' }, fill_convention: { type: 'string' }, control: { type: 'string' },
  regimes: { type: 'string' }, summary: { type: 'string' }, would_reopen: { type: 'string' } },
  required: ['proceed', 'slug', 'summary'] }
const GO = { type: 'object', properties: {
  proceed: { type: 'boolean' }, summary: { type: 'string' }, panel_last_dates: { type: 'string' },
  lookahead_plan: { type: 'string' }, notes: { type: 'string' }, would_reopen: { type: 'string' } },
  required: ['proceed', 'summary'] }
const TEST = { type: 'object', properties: {
  script: { type: 'string' }, reproducer: { type: 'string' }, results_dir: { type: 'string' },
  panel_last_dates: { type: 'string' }, headline: { type: 'string' }, time_split: { type: 'string' },
  regimes: { type: 'string' }, capacity: { type: 'string' }, control: { type: 'string' },
  chart: { type: 'string' }, pnl_series: { type: 'string' }, notes: { type: 'string' } },
  required: ['script', 'reproducer', 'results_dir', 'panel_last_dates', 'headline', 'time_split', 'regimes', 'capacity'] }
const REVIEW = { type: 'object', properties: {
  correctness_defect: { type: 'boolean' }, findings: { type: 'string' },
  failure_scenario: { type: 'string' }, notes: { type: 'string' } },
  required: ['correctness_defect', 'findings'] }
const EXPOSURE = { type: 'object', properties: {
  artifact_found: { type: 'boolean' }, artifact: { type: 'string' },
  exposures: { type: 'string' }, correlation_with_held: { type: 'string' },
  premium: { type: 'string' }, next_test: { type: 'string' } },
  required: ['artifact_found', 'exposures'] }

phase('Card')
const history = await agent(`Idea: "${IDEA}".
Write the economics of this idea for its idea card (docs/MISSION.md §4.1), four short paragraphs: MECHANISM (the economic force, and what it predicts about sign, size and horizon); COUNTERPARTY (who is on the other side and why they keep trading that way); PERSISTENCE (why it has not been arbitraged away); HISTORY (named episodes where it appeared and what happened to the edge in each). Cite papers and books you know; mark every citation you have not re-read in this session [U]. Name the state variable and the two or more market regimes in which you expect the effect to differ. Invent no figure. ${RULES}`,
  { label: 'market-historian-economist', phase: 'Card', agentType: 'market-historian-economist' })
need(history, 'the market-historian-economist')
const card = need(await agent(`Idea: "${IDEA}".${SLUG}${A.card ? ` An idea card already exists at ${A.card}: read it and complete any missing section rather than writing a second one.` : ''}
Economics from the market-historian-economist: ${history}
1. Read results/IDEA_LEDGER.md and run /graveyard. Name the closest earlier row (ledger_neighbour) and say what is different this time: new data, a new mechanism, a different horizon or a different instrument. Nothing is banned. If the earlier failure was a stale or untradable price, say how this design avoids it.
2. Write the idea card at results/ideas/YYYY-MM-DD_<slug>.md (today's date) with the sections of docs/MISSION.md §4.1: Mechanism, Counterparty, Persistence, History, Data, Capacity (rough, labelled [U] if not measured), Expected correlation with the sleeves held; then The test: the signal in one sentence, the fill convention (shift(2) for anything traded at the close, or the stated alternative and why), one control where the effect should be absent, and the time split and regimes to be read.
3. Set proceed=false only if no counterparty or mechanism can be stated, and say in would_reopen what you would need to learn. An idea is never stopped here for being unlikely to work.
${RULES}`,
  { label: 'signal-hunter', phase: 'Card', agentType: 'signal-hunter', schema: CARD }), 'the signal-hunter (card)')
if (!card.proceed) return { stage: 'card', outcome: 'STOPPED AT CARD: nothing to test yet', card, history }

phase('Data')
const source = need(await agent(`Idea: "${IDEA}". Card: ${card.card_path || card.slug}. ${card.summary}
Write the data card for every series this test needs: source and its terms for automated research use (quoted); coverage, first and last date, cadence; history and survivorship; PUBLICATION LAG (when a value is first public against the date it describes; vintages and revisions); how to fetch (an existing fetcher by path, or build one with a test and a source note for docs/REFERENCES.md); and the LOOKAHEAD PLAN: the exact timestamp or lag the signal must use and the assertion that enforces it. Free and public data only, plus the R2 mirror through src/data/r2.py (docs/DATA.md; inventory results/events/ssx/ssx_data/R2_FULL_INVENTORY_2026-10-19.md). Fetched output goes to a research data folder, never the live data/ panels. Count independent units (distinct dates, issuers, months) and say how the sample divides into an early and a late period. Set proceed=false only if no usable free data exists or the terms forbid storing it; say in would_reopen what source would change that. Put the lookahead plan in lookahead_plan and each panel's last date in panel_last_dates. ${RULES}`,
  { label: 'data-scout', phase: 'Data', agentType: 'data-scout', schema: GO }), 'the data-scout')
if (!source.proceed) return { stage: 'data', outcome: 'STOPPED AT DATA: no usable free data', card, source }
const audit = need(await agent(`Idea: "${IDEA}". Data card: ${source.summary}. Lookahead plan: ${source.lookahead_plan || 'see the data card'}
Audit the series before any return is computed on them: coverage, first and last dates, gaps; stale-price signatures (runs of zero returns, a NAV whose own date is earlier than its row, a price that could not be traded); bad bars, splits and corporate actions; every date join (dropped rows, forward fills into a signal, time zones); survivorship. Profile the candidate feature: dispersion, persistence against the holding window, effective breadth, correlation with the inputs of the sleeves already held, and average daily volume by name for the capacity table. Your work is descriptive; do not relate the feature to forward returns. Write the dated audit note under results/<family>/${card.slug}/. Set proceed=false only if the input cannot carry information (say why and what would reopen it). List any flagged rows that need a ruling before P&L. ${RULES}`,
  { label: 'data-analyst', phase: 'Data', agentType: 'data-analyst', schema: GO }), 'the data-analyst')
if (!audit.proceed) return { stage: 'data', outcome: 'STOPPED AT DATA AUDIT: the input cannot carry information', card, source, audit }

const runner = A.ml ? 'ml-engineer' : 'signal-hunter'
const brief = (fix) => `Idea: "${IDEA}". Card: ${card.card_path || card.slug}. Signal: ${card.signal || 'as the card states'}. Fill convention: ${card.fill_convention || 'shift(2)'}. Control: ${card.control || 'as the card states'}. Regimes: ${card.regimes || 'as the card states'}.
Data card: ${source.summary}. Lookahead plan: ${source.lookahead_plan || 'see the data card'}. Audit: ${audit.summary}
Run the Explore test (the /harness skill). Use scripts/research/harness.py: build a daily target-weight panel (cross_sectional_weights, event_weights, or the CEF builders), score it with evaluate/report. Do not build another backtester.${A.ml ? ' The model goes through scripts/research/ml.py with purged and embargoed folds; scalers and feature selection are fitted inside each fold.' : ''} Anything traded at the close is scored shift(2); another fill is stated in a comment and asserted. Assert the lookahead plan at run time and run harness.truncation_check on any new target builder. Put the script under scripts/research/${card.slug}/ and output under results/<family>/${card.slug}/.
Report, GROSS only: (1) the headline: annualised return, volatility, Sharpe, maximum drawdown, hit rate, turnover a year; (2) ONE TIME SPLIT: the same row for an early and a late period, with the split date and why; (3) AT LEAST TWO MARKET REGIMES by the state variable the card names, the label built only from data available on each date; eras where the sample allows; (4) the CAPACITY TABLE: position size against average daily volume at $1M, $5M and $10M (largest position as a share of ADV, and the share of positions above a stated participation), as feasibility and not a cost; (5) the control's row; (6) one equity-curve chart saved beside the result; (7) the per-period gross P&L series saved beside the result. Standard errors where windows overlap or events cluster come from scripts/research/inference.py, never a private copy. harness.report still returns net-of-cost columns from before the 2026-11-09 ruling: leave them out. Parameters may be explored; show the neighbours of the value you chose.${fix ? `\nA CODE REVIEW FOUND A CORRECTNESS DEFECT IN THE FIRST RUN. Fix it, add a test that fails against the old behaviour where the code is shared, re-run, and say at the top of your notes what changed in the numbers. The finding: ${fix}` : ''}
${RULES}`

phase('Test')
let test = need(await agent(brief(null), { label: runner, phase: 'Test', agentType: runner, schema: TEST }), runner)

phase('Review')
const reviewPrompt = (t) => `Idea: "${IDEA}". Review the code behind this Explore result: ${t.script} (reproducer: ${t.reproducer}). The data card's lookahead plan: ${source.lookahead_plan || 'see the data card'}.
Check, in this order: lookahead (shift(2) on held weights for a close-traded signal; publication lags, filing acceptance times and first-release vintages in the data; regime labels fitted on past data only; guard and truncation_check engaged); ML fold leakage if a model is fitted; silent fallbacks (except: pass, fillna of an invented value, a default for missing data); units (bp, percent, fraction; shares, dollars, share of ADV in the capacity table); alignment and joins; sign conventions; survivorship; stale or untradable prices; private copies of statistics that belong in scripts/research/inference.py; that the result is gross with no cost adjustment inside the series; that the time split and regimes are where the result says they are. Review the code, not the idea. Set correctness_defect=true only for a defect that makes a reported number wrong, and give the concrete inputs or state that produce the wrong number in failure_scenario. Reported result: ${JSON.stringify(t)}`
const [review0, expo] = await parallel([
  () => agent(reviewPrompt(test), { label: 'quant-reviewer', phase: 'Review', agentType: 'quant-reviewer', schema: REVIEW }),
  () => agent(`Idea: "${IDEA}". Explore result: ${JSON.stringify(test)}
Report what this result is made of, from the stored P&L series (${test.pnl_series || test.results_dir}). (a) ARTIFACTS: stale or untradable prices, a control that scores as well as the treatment, the execution convention, bid-ask bounce and ex-date arithmetic, survivorship, one name or one era. Set artifact_found=true only if you can show one, and give the evidence. (b) EXPOSURES: betas to equity, rates and credit and any factor that fits the sleeve, a down-market beta where the payoff could behave like a short put, alpha and its t as a description, and the correlation with each sleeve already held, with a range. If the result is mostly a known premium (carry, trend, short volatility), say which. Exposure is reported for sizing and is NOT a veto (team lead, 2026-11-09). Name the one further test that would most change the reading. ${RULES}`,
    { label: 'beta-detector', phase: 'Review', agentType: 'beta-detector', schema: EXPOSURE }),
])
let review = need(review0, 'the quant-reviewer')
need(expo, 'the beta-detector')
let rerun = false
if (review.correctness_defect) {
  rerun = true
  log(`quant-reviewer found a correctness defect; the test is re-run once with the finding`)
  phase('Test')
  test = need(await agent(brief(`${review.findings} Failure scenario: ${review.failure_scenario || 'see the findings'}`),
    { label: `${runner} (re-run)`, phase: 'Test', agentType: runner, schema: TEST }), `${runner} (re-run)`)
  phase('Review')
  review = need(await agent(reviewPrompt(test) + `\nThis is the re-run after your earlier finding: ${review.findings}. Say whether it is fixed.`,
    { label: 'quant-reviewer (re-run)', phase: 'Review', agentType: 'quant-reviewer', schema: REVIEW }), 'the quant-reviewer (re-run)')
}
const established = !review.correctness_defect && !expo.artifact_found

phase('Report')
const report = need(await agent(`Write up the Explore run on idea "${IDEA}" (slug ${card.slug}; card ${card.card_path || 'under results/ideas/'}).
Test: ${JSON.stringify(test)}
Code review (quant-reviewer${rerun ? ', after one re-run' : ''}): ${JSON.stringify(review)}
Exposures and artifacts (beta-detector): ${JSON.stringify(expo)}
Economics: ${history}
${established ? '' : 'THE RESULT IS NOT ESTABLISHED: an unresolved correctness defect or a demonstrated artifact remains. Say so in the first line of the report and in the ledger line, and name the fix. Do not present the numbers as a finding.\n'}1. Write results/<family>/${card.slug}/EXPLORE.md, short, leading with the result: the gross headline; the early and late rows; the regime rows; the exposures (reported, not a veto); the capacity table at $1M, $5M and $10M; the control's row; the chart; the reproducer command; each panel's last date. Every figure labelled [V]/[S]/[U].
2. Read the result against the card: did the sign and horizon match the mechanism, and did the effect appear where the history said it would? Then say what is next. The Explore bar is docs/MISSION.md §7: a gross effect with a sensible sign and size, holding in both halves or with a clear regime story, no lookahead, tradeable at the stated capital. If it clears, the next step is the /paper skill (which starts nothing until the runner's design approval is recorded in docs/SYSTEM.md §5). If it does not, say plainly what it showed and which angle was not tried, and either name the next tweak with its reason or mark it SET ASIDE with what would reopen it. One failed check does not end an idea.
3. Add ONE line to results/IDEA_LEDGER.md under "From 2026-11-09" in that file's format: date, idea, data (last date), gross result, status (the status words are defined at the top of the file).
4. Append an entry to results/report/EVIDENCE_LOG.md in its format (.claude/rules/report.md).
5. Update the card's Status section.
Do not commit. Return: the report's text, the exact ledger line, and the list of files that belong in one commit (card, data card and audit, script, results, ledger, evidence log). ${RULES}`,
  { label: 'report', phase: 'Report', agentType: 'signal-hunter' }), 'the report writer')
return { stage: 'explore-complete', slug: card.slug, established, rerun, card, source, audit, test, review, exposures: expo, report }
