---
paths:
  - "ops/specs/**"
  - "ops/books/*.json"
  - "config/*.yaml"
---

# Frozen specs and book files are governance objects

A key in `ops/specs/*.frozen.json` is not a constant. It is a commitment, and
changing one is a governance act with a paper trail. `.claude/settings.json` puts
these paths behind an `ask` rule for exactly this reason.

## The procedure

1. **Default to current behaviour.** A new key absent must reproduce today's
   behaviour exactly. The code change alone should be a provable no-op, so that
   activation is one visible edit. The band was verified this way: sleeve output
   byte-identical with `band_width` absent.
2. **Prove the no-op.** Diff sleeve output byte-for-byte with the key absent. Say
   in the commit message that you did, and how.
3. **Write the sibling note.** Every non-obvious key carries a `_<key>_note`
   recording what was measured, what alternative was rejected and why, and the
   exact **REVERT** — usually "delete this key". Read `_band_width_note` and
   `_min_trade_note` in `cef_discount.frozen.json`: that is the standard. They name
   the derivation, the measured plateau, the value that topped the sweep and was
   *not* chosen, and the consequence accepted knowingly.
4. **Record it before it trades.** Anything that changes traded behaviour needs a
   dated note under `results/` saying what changes, why, and how to revert,
   before the session that trades it, and a line in `results/IDEA_LEDGER.md`.
   Pre-registration and the trial counters were retired on 2026-11-09
   (`docs/SYSTEM.md` §5). Use `/spec-change`; the release is the team lead's.
5. **Bump `spec_id` and set `_supersedes`.** Never edit a spec in place without a
   new id. Since the 2026-09-28 clean slate there is no archive folder: the old
   version lives in git — **tag the commit that changes the spec**
   (`git tag spec-<old spec_id>` on the commit *before* the change) so its revert
   path is one `git show` away. The v5 spec, the band's revert path, is at tag
   `pre-clean-slate`: `git show pre-clean-slate:_archive/ops/_archive/cef_discount.v5.20260731.frozen.json`.
6. **Update `docs/RESEARCH_STATE.md` in the same commit** as the trial.

## Units are a real hazard here

`book_drawdown_suspend_pct` read `0.99` when it was meant to be *disabled*.
`pre-clean-slate:src/deploy/risk.py` computes `cap = -abs(pct)/100`, so the limit intended to be off
at 99% was live at **0.99%** — the tightest in the book — and breached at −1.84% on
2026-08-31. It is now `99.0`. **Percent keys in this repo are whole numbers.** State
the unit in the note.

## What is currently read but not acted on

`kill_drawdown` (0.18) and `halve_drawdown` (0.12) are in the frozen spec. Since
2026-10-19 the runner reads them in **report mode only**
(`quantt/session/drawdown.py`, switched by the book json's `risk.drawdown`): each
decide records the drawdown against them and acts on nothing. The sleeves'
`risk_check` still return OK unconditionally and nothing calls them. Arming
(an acting mode) is a later ruling (`docs/RUNNER.md`, "As built (2026-10-19)").
Do not quietly change the numbers: decide them with a memo, separately from arming.

## The kill rule is pre-committed

Reviewed at **60 live sessions and not before**. KILL if any of: (a) live net
Sharpe < 0.0; (b) realised slippage > 2× modelled for 5 consecutive sessions;
(c) top-minus-bottom discount spread falls below 12%, half its 22.5% at deployment.
**No extension of rope.** Do not soften this, and do not evaluate it early — a
comfortable-looking reading off two weeks of data is worse than no reading.

## Book files

`ops/books/*_book.json` carry capital, enabled flags and book-level limits.
Standing decision: **keep the five benchmarks, retire the null trader.** The
benchmarks are not decoration — with the null trader they are the only way to
separate "our signal is bad" from "our execution is bad".

## Cost model

`config/costs.yaml` and `costs_rv.yaml` carry per-name half-spreads. Two corrections
already applied and worth not undoing: the 2.5× "thin tier" multiplier is fiction
for penny-wide credit ETFs (ANGL modelled 4.334bp vs measured 1.735bp — over-charged
by exactly 2.5×), and evaluation happens on **modern-era** costs. Note that
`commission_usd_per_trade: 0.0` is the backtest's commission-free assumption and is
*not* what the live account is charged — IBKR's $1 minimum per order is what makes
`min_trade_usd` $517.
