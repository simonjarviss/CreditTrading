## What and why

<!-- Two or three sentences. Link the plan item or results note it answers. -->

**Lane:** FICC risk / equity risk / cross-asset signals, dashboard and data / PM

## Does it spend a trial?

- [ ] **No**: zero-trial work (feasibility, a gate, a reproduction, data, tooling, docs)
- [ ] **Yes**: counter ______. Pre-registration: `results/...`. The team lead approved it on ______, and the counter row in `docs/RESEARCH_STATE.md` moves in the commit that records that approval. No return was computed before it

## Does it touch the live path? (`docs/TEAM.md` §2)

- [ ] **No**
- [ ] **Yes**: which file(s) ______. A test fails against the old behaviour and passes now: ______. A frozen-spec or book-json change followed `/spec-change`

## Checks (`CLAUDE.md` is the authority on each)

- [ ] `python3 -m pytest` and `python3 -m ops.doc_audit --check` pass on this branch, after `git merge origin/main`
- [ ] Every figure in a note names the script that reproduces it, its date, and the last date of each panel it used
- [ ] Every table leads with gross P&L, with the 5 / 15 / 30bp grid beside it, labelled; comparisons are turnover-matched
- [ ] `/graveyard` checked before proposing a new mechanism
- [ ] No silent fallback, no invented value, no lookahead (alignment stated in a comment and asserted)
- [ ] New external claims are in `docs/REFERENCES.md` with [V] / [S] / [U], under this lane's section prefix
- [ ] No credential, no VM address, vault or subscription name, no account ID, and no row-level licensed data (CRSP, TRACE, WRDS) in any committed file
- [ ] Nothing written into `data/cef/`
- [ ] A new authored document has its row in `docs/INDEX.md`

## For the team lead

<!-- Rulings this needs from the team lead, if any, phrased as questions with options. -->
