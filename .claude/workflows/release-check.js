export const meta = {
  name: 'release-check',
  description: 'Production: go/no-go on one named commit for a prod release tag (tests, doc audit, orient, independent review of the diff since the last release)',
  whenToUse: 'Before tagging a release for the prod clone. Pass args {tree, commit}: the checkout to test and the commit it must be at (a string is read as notes, and the checkout is then the working directory). Read-only: it never tags, installs, arms or sends anything; the team lead approves the tag.',
  phases: [
    { title: 'Checks', detail: 'pytest, doc_audit, orient, runner preview' },
    { title: 'Review', detail: 'quant-reviewer + execution-engineer on the diff' },
    { title: 'Decision', detail: 'go / no-go with reasons' },
  ],
}

// WHY. Prod is this repository at a tag and nothing else (docs/ROADMAP.md
// phase 6). A tag is the only thing that reaches the order path, so the tag is
// where the checks sit. A green suite says little about the code that places
// orders (CLAUDE.md), so the diff that touches the order path is reviewed by two
// seats that did not write it.
//
// WHY ONE PINNED COMMIT. On 2026-10-10 a run was asked to check b3e4e9e in the
// send-headroom worktree, but this script never read its args. The checks ran
// in the worktree; both reviewers read HEAD of the main checkout, which sat on
// another branch. The decision agent noticed and said NO-GO, but only because
// it compared the two answers by eye. Now the checks stage resolves one full SHA
// and the last release tag, every later agent is handed both and reads code
// through git at that SHA, and the script itself refuses a review that does not
// say it covered that range.

const opts = (typeof args === 'object' && args !== null) ? args : {}
const notes = typeof args === 'string' ? args : (opts.notes || '')
const tree = opts.tree || null
const want = opts.commit || null
if (want !== null && !/^[0-9a-f]{7,40}$/.test(want)) {
  throw new Error(`args.commit must be a hex SHA of 7 to 40 characters, got ${JSON.stringify(want)}`)
}
const where = tree ? `the checkout at ${tree} (run every command there: cd into it, or git -C)` : 'this repository, in your working directory'

const CHECKS_SCHEMA = {
  type: 'object',
  properties: {
    tree: { type: 'string', description: 'absolute path of the checkout the checks ran in (git rev-parse --show-toplevel)' },
    head_sha: { type: 'string', description: 'full 40-character SHA from git rev-parse HEAD in that checkout' },
    clean: { type: 'boolean', description: 'true only if git status --short --untracked-files=no printed nothing' },
    untracked: { type: 'string', description: 'git status --short output for untracked files, or empty' },
    last_tag: { type: 'string', description: "git describe --tags --abbrev=0 --match 'release-*' at HEAD, or 'none'" },
    last_tag_sha: { type: 'string', description: "full SHA from git rev-parse <last_tag>^{commit}, or 'none'" },
    log: { type: 'string', description: 'git log --oneline <last_tag>..HEAD, verbatim' },
    checks: {
      type: 'array',
      description: 'one entry for each of items 2 to 5',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          pass: { type: 'boolean' },
          detail: { type: 'string', description: 'exit code and the decisive output lines, verbatim' },
        },
        required: ['name', 'pass', 'detail'],
      },
    },
  },
  required: ['tree', 'head_sha', 'clean', 'untracked', 'last_tag', 'last_tag_sha', 'log', 'checks'],
}

phase('Checks')
const checks = await agent(`Work only in ${where}. Run and report the real output of each (do not quote a test count from memory):
1. git rev-parse --show-toplevel; git rev-parse HEAD; git status --short; git describe --tags --abbrev=0 --match 'release-*' (the last release tag, or none); git rev-parse <that tag>^{commit}; git log --oneline <that tag>..HEAD
2. python3 -m pytest -q  (tail of output). data/ is gitignored, so a fresh worktree has none: if the checkout lacks data/, symlink it to the main checkout's data/ (the first path that git worktree list prints) for the run, and remove the link afterwards if you made it. Never write into data/.
3. python3 -m ops.doc_audit --check
4. python3 -m ops.orient
5. With DRY_RUN=1 and the team lead's QUANTT_STATE_DIR pointed at a scratch directory (never the prod state dir) and QUANTT_ENV_FILE set to the main checkout's config/.env: python3 -m quantt.session run --book cef --preview --skip-refresh  — this is read-only (it prints the order list; it cannot transmit under DRY_RUN=1). If it errors, report the error verbatim.
Never print a credential.`,
  { label: 'checks', phase: 'Checks', schema: CHECKS_SCHEMA })

if (!checks) throw new Error('the checks agent returned nothing; no review was run')
const sha = checks.head_sha
const tag = checks.last_tag
if (!/^[0-9a-f]{40}$/.test(sha)) {
  return `NO-GO. The checks stage reported no full HEAD SHA (got ${JSON.stringify(sha)}), so there is no commit to review. Nothing was reviewed.`
}
if (want !== null && !sha.startsWith(want)) {
  return `NO-GO. Asked to check ${want}, but ${checks.tree} is at ${sha}. Nothing was reviewed.`
}
if (!checks.clean) {
  return `NO-GO. ${checks.tree} has uncommitted changes to tracked files, so the checks did not test ${sha}. Nothing was reviewed. Commit or remove them and run again.`
}
if (!/^release-/.test(tag) || !/^[0-9a-f]{40}$/.test(checks.last_tag_sha)) {
  return `NO-GO. No release-* tag is reachable from ${sha} (got ${JSON.stringify(tag)}), so there is no base for the diff. Name one and run again.`
}
log(`Checking ${sha.slice(0, 7)} in ${checks.tree}; reviewing ${tag}..${sha.slice(0, 7)}`)

phase('Review')
const range = `${tag}..${sha}`
const scope = `The commit under review is ${sha}. Review the diff ${range} — git -C "${checks.tree}" diff ${range} — focusing on quantt/, src/deploy/, ops/specs/, ops/books/. Other checkouts of this repository, your own working directory among them, may sit on other branches: read every file as git -C "${checks.tree}" show ${sha}:<path>, never from a working directory. Begin your answer with the line "Reviewed ${range}". Report only real defects with a concrete failure scenario.${notes ? `\nContext from whoever asked for this check. It is a claim to test, not a fact: ${notes}` : ''}`
const [qr, ex] = await parallel([
  () => agent(`${scope}\nLens: lookahead, alignment, silent fallbacks, unit/sign errors, idempotency, credential leakage.`,
    { label: 'quant-reviewer', phase: 'Review', agentType: 'quant-reviewer' }),
  () => agent(`${scope}\nLens: order-path correctness — cls cutoff, Alpaca rules (wash trade, flips, shortability, client_order_id), gates, ambiguous submits, retries.`,
    { label: 'execution-engineer', phase: 'Review', agentType: 'execution-engineer' }),
])
const covered = r => typeof r === 'string' && r.includes(`Reviewed ${range}`)

phase('Decision')
return await agent(`Give the team lead a GO or NO-GO for tagging ${sha} as the next release-YYYYMMDD-N, with one line per reason. NO-GO if any check failed, if a reviewer did not cover ${range}, or if any reviewer finding is a real defect on the order path.
Checks (run in ${checks.tree} at ${sha}; ${checks.log.split('\n').filter(Boolean).length} commit(s) since ${tag}): ${JSON.stringify(checks.checks)}
Untracked files there: ${checks.untracked || 'none'}
quant-reviewer (covered ${range}: ${covered(qr)}): ${qr}
execution-engineer (covered ${range}: ${covered(ex)}): ${ex}
Finish with the exact commands the team lead would approve but do NOT run them: git tag -a <tag> ${sha}, git push origin <tag>, then the install for whichever machine python3 -m ops.prod_state says is prod (the VM: install_vm through the qi helper, docs/RUNBOOK.md §8.3 and §8.6; the laptop: install_prod). Write the vault name as <vault-name>: this repository is public.`,
  { label: 'decision', phase: 'Decision' })
