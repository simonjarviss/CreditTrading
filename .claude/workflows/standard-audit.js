export const meta = {
  name: 'standard-audit',
  description: 'Read-only audit of the repo against docs/STANDARD.md Part A: 5 auditors, each re-measured by a verifier',
  whenToUse: 'Each quarter and after any incident (docs/STANDARD.md Part D). Pass args {repo}: the checkout to audit, at the commit the note will name. Read-only: it writes nothing; the session writes results/ops/STANDARD_AUDIT_<date>.md from its return value, with ROADMAP work orders and an EVIDENCE_LOG entry.',
  phases: [
    { title: 'Audit', detail: 'one auditor per group of Part A areas; a verdict and evidence per check' },
    { title: 'Verify', detail: 'an independent re-measurement of every verdict' },
  ],
}

// WHY. docs/STANDARD.md holds no status: whether the platform meets a check is
// measured, never written down (§0.3). This is the measurement (§0.4): one reader
// per area, and a second reader who re-opens the files and tries to disprove each
// verdict, because a single agent's audit comes back in the same confident voice
// whether it is right or not. First run 2026-11-22 (run wf_039a7231-1cb):
// results/ops/STANDARD_AUDIT_2026-11-22.md. A5.3 is not audited: it is a deferred
// ruling with no measurer. When Part A gains or loses a check, change AREAS.
//
// WHY args.repo IS REQUIRED. The readers must all read one pinned checkout; a
// default would let them read whatever folder the session happens to sit in
// (the release-check lesson of 2026-10-10). On 2026-11-22 a resume without args
// failed on `args.repo`; it now says so.
if (!args || typeof args.repo !== 'string' || !args.repo) {
  throw new Error('standard-audit needs args {repo: "<absolute path of the checkout to audit>"}')
}
const REPO = args.repo

const RULES = `
Rules for this task (read-only audit):
- Work only in the repository at: ${REPO}
- You may read files, grep, run read-only git commands (log, show, ls-tree, branch, worktree list, rev-list, diff), and run
  "python3 -m pytest <path> -q" on specific tests. You may run a type checker, linter or coverage tool ONLY if it is already
  installed (check with --version first); never pip install anything.
- Never create, modify or delete any file. Never run a git command that changes state (commit, switch, checkout, stash,
  tag, push, merge, worktree add or remove).
- Never use sudo. Never open config/.env or any key, secret or credential file. Never ssh to the VM. Never run
  "python3 -m ops.orient" or "python3 -m ops.prod_state" (they ssh to the VM), quantt.session, quantt.collect,
  quantt.broker.alpaca_probe, or anything that contacts a broker or the network. Read their code instead.
- Evidence is a file path with line numbers and a short quote, or a command you ran and its output. Measure, never recall.
Verdicts:
- PASS: the behaviour exists for every book and runner in scope AND the measurer the check names exists and shows it.
- PARTIAL: the behaviour exists for some books or runners but not all, or it exists but the named measurer does not.
- GAP: the behaviour is absent.
- NOT_MEASURABLE: it cannot be measured from the repository (VM state, GitHub or Azure settings, broker account settings).
  Say exactly what would measure it.
Scope: everything on the desk that runs on a schedule or can send an order: the core CEF runner (quantt/session), C4,
the events runner (quantt/sleeves), the shadow runner (shadow/), the nightly collectors, the report jobs, the dashboard
exporter. Find out which runner serves which book from the code; do not assume.
For each GAP or PARTIAL, write the work order that would close it as one concrete sentence (what to build or change, and
where), its size (S under a day, M a few days, L a week or more) and the risk if it stays open.
"other_findings" is for anything serious you met that no check covers (a bug, a contradiction between a document and the
code). Keep it to what matters; it may be empty.`

const AREAS = [
  { key: 'repo-releases', ids: 'A1.1 A1.2 A1.3 A1.4 A1.5 A8.1 A8.2 A8.3 A8.4 A8.5',
    hints: 'Pointers (not conclusions): .claude/hooks/session_context.py and ops/orient.py (read, do not run) for A1.1; ' +
      'the laptop repository is shared by all worktrees, so "git branch" and "git worktree list" from the repo path show the laptop state for A1.2 ' +
      '(A1.1 asks whether the measurer exists, not only whether the main folder is current); docs/SYSTEM.md section 5 for A1.3; ' +
      'CLAUDE.md and .claude/rules/ for A1.4; docs/RUNNER.md against quantt/session/gate.py for A1.5; quantt/deploy/ installers, ' +
      'docs/RUNBOOK.md section 8, ops/prod_state.py (read only) and .claude/skills/release-check for A8.' },
  { key: 'live-code', ids: 'A2.1 A2.2 A2.3 A2.4 A2.5 A2.6 A2.7 A2.8',
    hints: 'Pointers: the live path list is docs/TEAM.md section 2; CI is .github/workflows/checks.yml; runners under quantt/session, ' +
      'quantt/sleeves, shadow/; broker code under quantt/broker; switches are keys in ops/books/*.json, ops/specs/*.json, ops/sleeves/*.json ' +
      'and shadow/books/*.json. For A2.1 build the import graph of the live path yourself (AST or grep) and list every import of scripts/ or research code. ' +
      'For A2.5 count bare "except:" and "except ...: pass" on the live path with file:line. For A2.2 and A2.3, if mypy or coverage is installed, ' +
      'say how many type errors a strict run reports on the live path (this sizes the work); if not installed, say so.' },
  { key: 'controls-stopping', ids: 'A3.1 A3.2 A3.3 A3.4 A3.5 A3.6 A4.1 A4.2 A4.3',
    hints: 'Pointers: docs/RUNNER.md "The gates"; quantt/session/gate.py and run.py; the events runner under quantt/sleeves and whatever gates it applies; ' +
      'ops/halt.py; docs/RUNBOOK.md for any stop or cancel-all procedure. For A3.1 to A3.3 look for per-order share, notional, ADV-share, price-collar ' +
      'and order-count limits and whether a missing limit refuses. For A3.6 look for a comparison of the orders sent against the decided plan, before and after sending.' },
  { key: 'monitoring-recon-recovery', ids: 'A5.1 A5.2 A6.1 A6.2 A6.3 A9.1 A9.2 A9.3 A9.4',
    hints: 'Pointers: quantt/session/verify.py and the verdict files each job writes; the events runner\'s verify; the shadow nightly; ' +
      'the collectors; the report jobs; quantt/deploy/templates for every scheduled unit (list every timer/service and whether each writes a PASS/FAIL/MISSED verdict); ' +
      'dashboard/ and its exporter for A5.2; docs/RUNBOOK.md for recovery and backups; what the runner does when the broker API errors at send time (A9.4).' },
  { key: 'data-access', ids: 'A7.1 A7.2 A7.3 A7.4 A7.5 A10.1 A10.2 A10.3 A10.4',
    hints: 'Pointers: docs/DATA.md; quantt/collect; scripts/cef/fetch_daily.py; gate 5 and the stale-NAV gate in quantt/session; the corporate-action gate; ' +
      'what the events runner and the shadow books read; results/ops/CEFCONNECT_TERMS_OPTIONS_2026-10-19.md and NAV_SOURCE_WORKAROUND_2026-10-19.md for A7.5; ' +
      'quantt/deploy/boot_secrets.py, azure_keyvault.py and the systemd templates (User=, sudo) for A10; .github/workflows for a secret scan; docs/TEAM.md section 6 for access. ' +
      'Do not open any key or secret file.' },
]

const AUDIT_SCHEMA = {
  type: 'object',
  properties: {
    area: { type: 'string' },
    checks: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' },
      verdict: { type: 'string', enum: ['PASS', 'PARTIAL', 'GAP', 'NOT_MEASURABLE'] },
      evidence: { type: 'string' },
      gap: { type: 'string' },
      work_order: { type: 'string' },
      size: { type: 'string', enum: ['S', 'M', 'L', '-'] },
      risk: { type: 'string', enum: ['high', 'medium', 'low', '-'] },
    }, required: ['id', 'verdict', 'evidence', 'gap', 'work_order', 'size', 'risk'] } },
    other_findings: { type: 'array', items: { type: 'object', properties: {
      title: { type: 'string' }, evidence: { type: 'string' }, risk: { type: 'string', enum: ['high', 'medium', 'low'] },
    }, required: ['title', 'evidence', 'risk'] } },
  },
  required: ['area', 'checks', 'other_findings'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    checks: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' },
      agree: { type: 'boolean' },
      verdict: { type: 'string', enum: ['PASS', 'PARTIAL', 'GAP', 'NOT_MEASURABLE'] },
      evidence: { type: 'string' },
      note: { type: 'string' },
    }, required: ['id', 'agree', 'verdict', 'evidence', 'note'] } },
    other_findings: { type: 'array', items: { type: 'object', properties: {
      title: { type: 'string' }, confirmed: { type: 'boolean' }, note: { type: 'string' },
    }, required: ['title', 'confirmed', 'note'] } },
  },
  required: ['checks', 'other_findings'],
}

const results = await pipeline(
  AREAS,
  (a) => agent(
    `You are auditing a small trading desk's repository against its own standard, docs/STANDARD.md.\n` +
    `Read docs/STANDARD.md section 0 and Part A first. Then measure these checks, giving each one a verdict: ${a.ids}.\n` +
    `Every check id listed must appear exactly once in "checks".\n${a.hints}\n${RULES}`,
    { label: `audit:${a.key}`, phase: 'Audit', schema: AUDIT_SCHEMA }),
  (audit, a) => audit && agent(
    `You are the second reader on an audit of a trading desk's repository against docs/STANDARD.md (read section 0 and Part A).\n` +
    `Another agent measured the checks ${a.ids} and returned the JSON below. Re-measure every check yourself, independently: ` +
    `re-open the files, do not trust the quotes. Look for errors in both directions: a GAP or PARTIAL where the behaviour in fact ` +
    `exists elsewhere in the code, and a PASS where some book or runner in scope lacks it. For each check say whether you agree, ` +
    `your own verdict, and your evidence. Then confirm or reject each of its "other_findings".\n${a.hints}\n${RULES}\n\n` +
    `The first auditor's result:\n${JSON.stringify(audit)}`,
    { label: `verify:${a.key}`, phase: 'Verify', schema: VERIFY_SCHEMA }).then(v => ({ area: a.key, audit, verify: v })),
)

const done = results.filter(Boolean)
log(`${done.length} of ${AREAS.length} areas audited and verified`)
return done
