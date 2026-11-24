---
name: spec-change
description: The safe procedure for changing a frozen spec key, a book limit, or a cost-model entry. Use whenever editing anything under ops/specs/, ops/books/ or config/*.yaml. Covers the no-op proof, the sibling note, the units trap and the revert path.
argument-hint: [spec key or file]
---

# Changing a frozen spec

A key in `ops/specs/*.frozen.json` is **a commitment, not a constant**. Changing
one is a governance act with a paper trail.

## Current state

```!
ls -1 ops/specs/*.frozen.json 2>/dev/null; echo "---"; python3 -c "
import json
d = json.load(open('ops/specs/cef_discount.frozen.json'))
print('spec_id:', d['spec_id'], '| supersedes:', d.get('_supersedes'))
f = d['frozen']
for k in sorted(f):
    if not k.startswith('_'):
        print(f'  {k} = {f[k]}' + ('   [has _note]' if f'_{k}_note' in f else ''))
print('risk:', d.get('risk'))
print('rebalance:', {k: v for k, v in d.get('rebalance', {}).items() if not k.startswith('_')})
"
```

## The procedure

**1. Know what authorises the change.** Until 2026-11-09 this step required a
pre-registration and a move of a trial counter. The team lead dropped both that
day (`docs/SYSTEM.md` §5); every other step below is unchanged. The core and C4
books may be changed, on paper first, and a change to what prod runs reaches the
VM only as a release, which is the team lead's alone. The reasoning for the
change goes in the sibling note (step 4).

**2. The new key must default to current behaviour.** With the key absent, the
sleeve must do exactly what it does today. The code change alone should be a
provable no-op, so that activation is one visible edit.

**3. Prove the no-op — do not assert it.** Diff sleeve output byte-for-byte with
the key absent. The band was verified this way. Record in the commit message that
you did it and how.

**4. Write the sibling `_<key>_note`.** Read `_band_width_note` and
`_min_trade_note` in `cef_discount.frozen.json` — that is the standard. Each names:
what was derived and how, the measured inputs, **the value that topped the sweep
and was deliberately not chosen**, the consequence accepted knowingly, what reads
the key, and the exact **REVERT** (usually "delete this key").

**5. Bump `spec_id`, set `_supersedes`, and tag the commit BEFORE the change**
`spec-<old spec_id>` (and push the tag). The old spec is then one
`git show spec-<old spec_id>:ops/specs/cef_discount.frozen.json` away — that is the
revert path. No `.bak` copies (clean slate, 2026-09-28). Example:
`spec-cef_discount.v6.20260906`.

**6. Log it in the same commit**: an entry in `results/report/EVIDENCE_LOG.md`,
and a line in `results/IDEA_LEDGER.md` if the change came from a tested idea.

## The units trap

`book_drawdown_suspend_pct` read `0.99` when it was meant to be *disabled*.
`pre-clean-slate:src/deploy/risk.py` computes `cap = -abs(pct)/100`, so the limit intended to be
off at 99% was live at **0.99% — the tightest in the book** — and breached at
−1.84% on 2026-08-31. It is now `99.0`.

**Percent keys in this repo are whole numbers.** State the unit in the note. Check
bp vs percent vs fraction at every boundary, and ÷252 vs ÷360 on anything that
accrues.

## Keys that are read but not acted on

`kill_drawdown` (0.18) and `halve_drawdown` (0.12) are in the frozen spec. Until
2026-10-19 no code path read them. Since then the runner reads them in **report
mode only** (`quantt/session/drawdown.py`; the book json's `risk.drawdown`): every
decide records the drawdown against them, and nothing acts. The sleeves'
`risk_check` still return OK unconditionally, and nothing calls them. The standing
decision is to arm HALVE/KILL on broker-confirmed NAV; an acting mode is a later
ruling (`docs/RUNNER.md`, "As built (2026-10-19)").

**Do not quietly change these numbers.** Wire them, then decide the numbers with a
memo. Changing a number that nothing reads is theatre; changing it *as* you wire it
conflates two decisions.

## Inert-by-design keys

`rebalance_days: 2` is **inert while `band_width` is set** — a band and a calendar
are two answers to the same question and running both compounds them. It is
retained so that deleting `band_width` restores v5 exactly. Do not "clean up" an
inert key; it is the revert path.

## After the edit

```bash
python3 -m pytest                          # never quote the count
python3 -m ops.doc_audit --check           # the spec id and notes still agree with the docs
python3 -m ops.orient --no-tests           # SPEC shows the new id and values
```

Then build the sleeve on the new spec for the last few panel dates and look at
the targets (names, gross, net) before anything trades. The IBKR preflight gate
was deleted; the Alpaca runner's gate is `docs/ROADMAP.md` 4.3.

If you changed behaviour and no test failed, that is itself a finding — add the
test.

The `PostToolUse` hook will remind you of this procedure when you edit a frozen
spec. The `ask` permission rule on `ops/specs/**` and `ops/books/**` will pause
first. Both are deliberate.
