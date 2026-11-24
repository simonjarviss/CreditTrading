---
name: repro
description: Reproduce a number claimed in the docs, or verify one before quoting it. Use whenever a figure is about to drive a decision, when a document number looks stale, or when two sources disagree. Every headline figure names a script; this runs it.
argument-hint: [the number or claim to check]
---

# Reproduce before you quote

**A number without provenance is a rumour.** Confidently wrong numbers have cost
this desk more than missing ones. Assume your recall of any specific figure is
wrong until you have fetched it.

Five real examples, every one of which would have propagated into a decision: a
variance-risk-premium figure recalled as −74% exists in no reachable source; a
predictive R² recalled as "low-to-mid teens" is **6.82%**; a Supreme Court ruling
recalled as unanimous was **6–3**; a finding recalled as "open-ending halves the
discount" is backwards — it *eliminates* it; and a return-convention bias asserted
at "about 2%/yr" measured **−0.01%/yr**.

## Where the headline numbers come from

| claim | script |
|---|---|
| every number in the archived `pre-clean-slate:_archive/docs/PLAN.md` | `scripts/cef/plan_diagnostics.py` |
| the trading-policy frontier (band vs calendar, all cost columns) | `scripts/cef/band_frontier.py` |
| Σ, Σ⁻¹α, effective breadth `BR_eff` | `pre-clean-slate:scripts/cef/covariance_construction.py` |
| borrow drag on net Sharpe | `pre-clean-slate:scripts/cef/borrow_impact.py` |
| where availability binds, capacity | `pre-clean-slate:scripts/cef/borrow_capacity.py` |
| the joint cost-aware optimiser | `pre-clean-slate:scripts/cef/joint_cost_optimiser.py` |
| the original backtest (the retired calendar policy) | `scripts/cef/validate.py --trials <N>` (the flag is still required by the script; it only feeds a statistic that research no longer uses, so read the gross rows) |
| any idea tested since 2026-11-09 | the command named in its results note; its line is in `results/IDEA_LEDGER.md` |

## Panel freshness — check this first

```!
python3 - <<'PY'
import pathlib
try:
    import pandas as pd
except ImportError:
    raise SystemExit("pandas unavailable")
for rel in ["data/cef/cef_prices.parquet", "data/cef/cef_nav.parquet",
            "data/etf_daily.parquet"]:
    p = pathlib.Path(rel)
    if not p.exists():
        print(f"{rel:<34} MISSING")
        continue
    try:
        d = pd.read_parquet(p, columns=["date"])["date"]
        print(f"{rel:<34} last bar {pd.to_datetime(d).max().date()}  ({len(d):,} rows)")
    except Exception as exc:
        print(f"{rel:<34} unreadable: {type(exc).__name__}")
for rel in ["data/cef/cef_borrow.csv", "data/cef/cef_facts.csv"]:
    p = pathlib.Path(rel)
    print(f"{rel:<34} " + (f"modified {__import__('datetime').date.fromtimestamp(p.stat().st_mtime)}"
                           if p.exists() else "MISSING"))
PY
```

**Stale is a form of wrong.** State a panel's last date in any note that uses it.
The borrow panel in particular was measured **once**, on 2026-09-06, and applied to
21 years — a forward estimate, not a historical cost, and it must be labelled that
way every time it appears.

## The procedure

1. **Find the claim's source.** Grep the docs for the number. If no script is
   named, that is itself the finding: an unreproducible number is an anecdote.
2. **Run the script now.** Not a number copied from an old note.
3. **Compare.** If it differs, work out why before deciding which is right — a
   panel has usually moved, or a convention has changed.
4. **If two sources disagree, report the disagreement.** Do not average them and do
   not pick one silently. Say which you used and why.
5. **Label provenance** `[V]` verified / `[S]` sourced but not re-read / `[U]`
   uncertain, as `docs/REFERENCES.md` does.
6. **Correct in place, visibly.** Leave a dated correction rather than a silent
   edit — someone is relying on the old number somewhere.

## Numbers that are known to need care

- **`realised/modelled = 4.59×`.** Pooled across two different execution methods.
  Split by session or do not quote it.
- **Effective breadth.** 2.24 historically, **1.17** on today's live weights. Say
  which.
- **Borrow drag 1.22%/yr.** Historical counterfactual. Today's book is 3.62%.
- **Cost 21.2%/yr.** A full-sample artifact dominated by 2007–2014. Modern era is
  **1.73bp/trade**, 3.7× cheaper than the full-sample 6.36bp.
