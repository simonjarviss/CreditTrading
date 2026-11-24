"""The multi-sleeve combiner: every ENABLED sleeve of one book, netted into one order per symbol. DARK.

WHY IT EXISTS. One Alpaca account takes ONE order per symbol per session:
Alpaca rejects opposite-side orders in one symbol as wash trades, paper
included (CLAUDE.md landmine 2), and the runner sizes every order from the
account's open positions. Until this module the runner traded exactly one
frozen spec per `Book` (run.py `BOOKS`), and the book json's `sleeves[]` list was
read only by `ops/common.py::deployed_tickers`, for the refresh. Two rulings
make a second sleeve in one account concrete: the CEF account is "one combined
book" (docs/SYSTEM.md §5, 2026-10-09), and the agent lab shares the spare
account with C4, so lab sleeves "must be netted into C4's targets symbol by
symbol" (§5, 2026-10-28). The design is the portfolio framework's phase C
(results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md §2.10, §7) and the C4 deploy
plan's row 6S (branch `simon`, results/cef/C4_DEPLOY_PLAN_2026-10-27.md). The
team lead approved building it on 2026-10-28: "build the combiner, decide
placement after". Where it runs first is not decided here.

OFF BY DEFAULT, AND THE NO-OP. `load_sleeves` returns None, and the runner takes
its single-spec path exactly as before, unless an ENABLED entry of `sleeves[]`
carries `risk_budget`. The released book json carries none, so the released
session is the code before this module, byte for byte: same targets, orders,
plan.json and plan_sha. Proved against de6e9c5 on the real panel and on a
synthetic panel that never skips (quantt/session/tests/test_combine_noop.py).
With no budget anywhere the book json must still say what the runner trades:
exactly one enabled sleeve, whose spec is the book's (`BOOKS[...].spec_path`).
Anything else raises before the session starts. Until now a second enabled
sleeve was silently not traded while the refresh required its names, so every
day would have been refused (exit 4) for a sleeve nobody was trading.

WHAT IT DOES, for a book whose enabled sleeves all carry `risk_budget`:
  1. Builds each sleeve's targets from its OWN frozen spec, through the same
     `run.sleeve_targets` the single-sleeve book uses (the registry validates
     each spec). Each sleeve is shown only its own holdings (HOLDINGS below).
  2. Sizes each sleeve on its own NAV (THE RISK BUDGET below). Its weights are
     turned into whole shares by `decide.target_shares`, the single-sleeve rule:
     toward zero, and a qty target (the band's HOLD) used exactly as given.
  3. Sums the target shares per symbol and calls `decide.decide` ONCE on the
     netted book: one order per symbol, the flip, shortability and min_trade on
     the NET position, one plan_sha.
  4. Leaves the book-level limits to the runner's existing machinery on the
     netted orders: `fit_to_buying_power` and gate 8 (THE BOOK-LEVEL CAP below).
  5. Returns the per-sleeve record the runner writes to plan.json as `combine`
     (ATTRIBUTION below).
  6. Gate 9 then reads the UNION of the enabled sleeves' universes
     (`book_params`), and gate 5 and the stale-NAV gate act per sleeve
     (`gate.gate_data_by_sleeve`; STALE NAV below).

THE RISK BUDGET. `sleeves[i].risk_budget` = b, in (0, 1]: the sleeve's share
of the book's vol target. The book's vol target is the BOOK spec's
`frozen.vol_target_annual` (the spec `BOOKS[...]` names; framework §2.6: "Today:
σ* = the spec's 6%"). The sleeve is sized on

    sleeve_nav = equity × b × σ_book / σ_sleeve,

with σ_sleeve its own spec's `frozen.vol_target_annual`. Every sleeve this
registry builds vol-targets its own NAV (framework §2.2), so its ex-ante dollar
vol is σ_sleeve × sleeve_nav = b × σ_book × equity: b of the book's target,
whatever target the sleeve's own spec carries. Everything else the sleeve does
in weight units (the band, `min_abs_weight`, its own `max_gross_stress`, the
vol scalar's clip) stays relative to its own NAV: a sleeve at budget b is the
same strategy run on a smaller book. With one sleeve whose spec is the book's
and b = 1, sleeve_nav is the account equity to the bit (b × σ / σ = 1.0
exactly), which is what lets the one-sleeve combiner reproduce the
single-sleeve orders and plan_sha (test_combine_noop.py). The budgets
themselves are inputs. They come from the allocation analysis (framework §2.3
to §2.6, phase E), and nothing here derives or bounds their sum: shares of vol
add to more than 1 when sleeves diversify. The book's gross is bounded by the
book-level cap, whatever they sum to.

THE BOOK-LEVEL CAP. ONE `max_gross_stress`, the book spec's, applied once to
the NETTED book by the objects that already apply it: `run.fit_to_buying_power`
scales the opening orders to fit it (bp_shortfall "scale"), and gate 8
(`gate.stress_breach`) refuses what still breaks it. Each sleeve keeps its own
cap inside itself, relative to its own NAV. NOT CHOSEN: a second, weight-space
cap on the combined target (the sleeve's `_cap_gross`, one level up). It would
be a second object named `max_gross_stress` with different semantics from
gate 8's ("a plan that does not add gross always passes"), and it would scale
band holds into trades whenever the book sat a hair above the line at the as-of
closes. THE VALUE IS STALE FOR A COMBINED BOOK. The spec's 1.80 was derived for
the 13 names alone with M_other = $0 (its `_max_gross_stress_note`). Before a
second sleeve is enabled it must be re-derived on the combined book by the
frozen rule (framework §2.7). That is the allocation analysis's input, like the
budgets, and a spec change of the book spec.

NETTING. One order per symbol, from the sum of the sleeves' whole-share
targets. One long and one short in a symbol cross inside the book and send only
their net. The flip rule (close today, open next session) runs on the net, so
two sleeves holding opposite views never flip the account by themselves
(framework §2.10). min_trade_usd, shortability and the transmit sequence are
`decide`'s, on the net, unchanged. NOT YET ALLOWED ACROSS SLEEVES: while
SHARED_SYMBOLS_ALLOWED is False (below, HOLDINGS) no two enabled sleeves share
a symbol, so each symbol has one owner and its net is that sleeve's target. The
cross-sleeve arithmetic is kept, and tested behind the flag, for when per-sleeve
sub-ledgers exist.

HOLDINGS. Each sleeve is shown the account's positions in its own universe.
Where the universes are disjoint that is exact. The 13 and C4's 74 share none
(C4 plan §0). A HELD position in a symbol two enabled sleeves trade cannot be
split without a per-sleeve sub-ledger, which is not built (framework §2.10,
"virtual sub-ledger"). OVERLAPPING UNIVERSES ARE REFUSED UP FRONT (release-check
of 00ec423). The first build accepted two enabled sleeves sharing a symbol and
refused only a HELD shared position. That lets day one net the shared symbol
from flat and send, and then every later slot FAILs on the position day one
built: nothing can trade or exit until someone flattens it by hand. So
`load_sleeves` rejects enabled sleeves whose universes share a symbol, naming
the symbols, and `decide` refuses the same, whatever built the sleeves. The
held-shared check stays behind it, for the flag.

ATTRIBUTION (plan.json `combine`). For each enabled sleeve: its spec, budget,
vol targets and sleeve_nav; whether it was decided or held (and why); the
stale-NAV holds it got; and per symbol of its universe its attributed current
shares, its target shares, the target's kind and its reason. Together with
plan.json's netted `targets` and `orders` (after any fit), that is everything
verify, score and TCA need to split P&L by sleeve. None of them does yet. The
framework's fill rule (§2.10), to apply to FILLS when they do: a symbol's fill
is allocated pro rata to each sleeve's signed target change in it; an internal
cross trades nothing, and both legs are marked at the official close.

GATE 5, PER SLEEVE (`gate.gate_data_by_sleeve`). Each sleeve's names are
checked on their own. Before the final check (`nav_gate.final_check_at`, the
close minus 90 minutes) a failing sleeve refuses the whole decide, as today, so
the next slot retries and a NAV that lands at 22:30 is still traded. Holding a
sleeve at 22:00 would have cost it the day for data that was merely late. From
the final check, a sleeve still failing is HELD (its attributed shares kept, no
order in its names), and the other sleeves decide. That is the decoupling the
C4 plan asks for: one missing NAV in one sleeve no longer costs every other
sleeve the day. fetch_daily's exit 4 (INCOMPLETE) is exactly that per-name
condition, so it is attributed by the per-name check. Every other refresh
failure stays book-wide. A held sleeve's positions are still valued by gate 8 at
their last close, whose date is in plan.json's `closes`. A position with no
close at all refuses the book, as before.

STALE NAV, PER SLEEVE. The stale-NAV gate runs once over the union (one
panel, one CEFConnect read per name, one record). A name it holds goes ONLY to
the sleeves whose universe contains it, as that sleeve's `extras["nav_hold"]`,
and is added only when that sleeve has one, as in the single-sleeve book. It
runs on an INCOMPLETE refresh (exit 4) too, because that is the one refresh
failure after which some sleeves still decide (run.py `_nav_gate`; the first
build skipped it there and sent those sleeves unchecked). A
deferral stays book-wide by construction: there is one plan per day (run.py,
DEFERRAL AND THE ORDER PATH), and it cannot be decided for one sleeve now and
another later. It costs the other sleeves time, never the day, because from the
final check every unverified name is held by the sleeve that owns it.

PANELS, PER SLEEVE (C4 plan row 6A, 2026-10-29; run.py PER-SLEEVE PANELS). Each
sleeve's closes, NAV dates and pre-flight history are read from the panel its
own spec decides on (`SleeveEntry.panel`), so gate 5 per sleeve checks the NAV
dates that sleeve decides on and the netted orders are priced on each owner's
own closes. The stale-NAV gate and the refresh still read ONE panel: a combined
book whose sleeves read two is refused by both (`run.stale_nav_panel`,
`run.book_refresh`).

NOT BUILT HERE (each named so nobody assumes it): per-sleeve sub-ledgers, and so
any symbol two enabled sleeves share (lab sleeves netting into C4's own names
need them first); a per-sleeve opening session (a sleeve added to a live
account opens at its band edge, because the account is not flat); a refresh
per panel and a stale-NAV gate per panel (above); a per-sleeve stale-NAV mode;
sleeve `state` close_only or flat, and sleeve-scoped halts (framework §3.5);
the P&L split in verify, score and TCA; and the combined `max_gross_stress`
re-derivation.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from quantt.session import decide as dec
from src.deploy.sleeve import FLAT, LONG, SHORT, PositionTarget

# The book's vol target and every sleeve's: a FRACTION per year, in the same
# sane band the registry enforces for cef_discount (`_validate_cef_discount`):
# 0.06 is 6%; a percent written as 6 raises here instead of sizing 100x.
VOL_TARGET_BAND = (0.005, 0.40)

# May two enabled sleeves share a symbol? False until per-sleeve sub-ledgers
# exist (module docstring, HOLDINGS): `load_sleeves` and `decide` both refuse
# an overlap. Turning it on is new code (the sub-ledger), a test that fails
# without it, and the team lead's release; tests flip it only to exercise the
# netting arithmetic kept for that day, like decide.FLIP_SAME_SESSION.
SHARED_SYMBOLS_ALLOWED = False


class CombineError(ValueError):
    """The book json, a sleeve or the account cannot be combined without guessing. Names it."""


def shared_symbols(sleeves) -> dict:
    """{symbol: (sleeve names)} for every symbol in more than one sleeve's universe."""
    owners = {}
    for e in sleeves:
        for s in e.universe:
            owners.setdefault(s, []).append(e.name)
    return {s: tuple(n) for s, n in sorted(owners.items()) if len(n) > 1}


def _refuse_shared(sleeves, where: str) -> None:
    shared = shared_symbols(sleeves)
    if shared and not SHARED_SYMBOLS_ALLOWED:
        raise CombineError(
            f"{where}: enabled sleeves share {sorted(shared)} ({shared}). Until per-sleeve "
            f"sub-ledgers exist a held position in a shared symbol cannot be split, so the "
            f"first session would build a position that every later session must refuse "
            f"(combine.py, HOLDINGS); disable one sleeve or make the universes disjoint")


@dataclass(frozen=True)
class SleeveEntry:
    """One ENABLED sleeve of a combined book, as `load_sleeves` read it."""
    name: str
    spec_id: str
    spec_path: str            # as the book json wrote it (repo-relative)
    universe: tuple           # sorted: the built sleeve's own `instruments()`
    risk_budget: float        # share of the book's vol target, in (0, 1]
    vol_target: float         # the sleeve spec's frozen.vol_target_annual
    targets: Callable         # (asof, holdings, sleeve_nav, opening, **kw) -> [PositionTarget]
    # The (prices, nav) panel the sleeve decides on, and so the panel the runner
    # prices, gates and NAV-checks its names on (run.py PER-SLEEVE PANELS):
    # `panel_of(spec)` of the very spec that built `targets`. None when
    # load_sleeves was given no `panel_of` (tests of the netting arithmetic);
    # the runner's `book_panels` refuses a None.
    panel: object = None


def _vol_target(spec: dict, where: str) -> float:
    v = (spec.get("frozen") or {}).get("vol_target_annual")
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise CombineError(f"{where}: frozen.vol_target_annual is {v!r}; a risk budget is a "
                           f"share of the book's vol target, so every combined sleeve and the "
                           f"book spec must state one")
    lo, hi = VOL_TARGET_BAND
    if not lo <= float(v) <= hi:
        raise CombineError(f"{where}: frozen.vol_target_annual {v!r} is outside {VOL_TARGET_BAND} "
                           f"(a fraction per year: 0.06 is 6%)")
    return float(v)


def book_vol_target(book_spec: dict) -> float:
    """The book's vol target: the BOOK spec's frozen.vol_target_annual (docstring,
    THE RISK BUDGET). Raises if it is absent or not a fraction in the band, and
    if the book spec sets `sizing_multiplier` (`load_sleeves`, ONE SIZING
    AUTHORITY PER BOOK)."""
    if (book_spec.get("frozen") or {}).get("sizing_multiplier") is not None:
        raise CombineError(
            f"book spec {book_spec.get('spec_id')!r} sets frozen.sizing_multiplier, which sizes a "
            f"single-sleeve account; a combined book is sized by its budgets and this spec's vol "
            f"target, and the two would compound. Delete the multiplier or re-express it as budgets")
    return _vol_target(book_spec, f"book spec {book_spec.get('spec_id')!r}")


def _budget(entry: dict, where: str) -> float:
    b = entry.get("risk_budget")
    if isinstance(b, bool) or not isinstance(b, (int, float)) or not math.isfinite(b) \
            or not 0.0 < float(b) <= 1.0:
        raise CombineError(f"{where}: risk_budget {b!r} must be a number in (0, 1], the "
                           f"sleeve's share of the book's vol target")
    return float(b)


def load_sleeves(book_path: Path, book_spec_path: Path, repo: Path,
                 make_targets: Callable[[dict], Callable],
                 panel_of: Callable[[dict], object] | None = None) -> tuple | None:
    """The book json's `sleeves[]` as the runner reads it: None for the
    single-sleeve book (today's path), else one `SleeveEntry` per ENABLED
    sleeve, in the book json's order. See the module docstring, OFF BY DEFAULT.

    `enabled` absent is True, the rule `ops/common.py::deployed_tickers` applies
    (so the refresh checks exactly the sleeves the runner trades); present, it
    must be a bool. A DISABLED entry is not read further: not its spec, not its
    budget, not its name. `make_targets(spec)` returns the sleeve's target
    callable (run.py binds `sleeve_targets`; tests pass fakes). `panel_of(spec)`,
    when given, is the sleeve's panel (run.py binds `spec_panel`), read from the
    same spec, once; it is never called on the single-sleeve path."""
    book_path, repo = Path(book_path), Path(repo)
    book = json.loads(book_path.read_text())
    if "sleeves" not in book:
        return None            # never read by the runner before this module: today's path
    entries = book["sleeves"]
    if not isinstance(entries, list):
        raise CombineError(f"{book_path}: `sleeves` must be a list, got {type(entries).__name__}")
    enabled = []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            raise CombineError(f"{book_path}: sleeves[{i}] is not an object")
        on = e.get("enabled", True)
        if on is not True and on is not False:
            raise CombineError(f"{book_path}: sleeves[{i}].enabled {on!r} is not a bool")
        if on:
            enabled.append((i, e))
    budgeted = [i for i, e in enabled if "risk_budget" in e]
    if not budgeted:
        # The single-sleeve book: the json must name the spec the runner trades.
        if len(enabled) != 1:
            raise CombineError(
                f"{book_path}: {len(enabled)} enabled sleeves and no risk_budget. The runner "
                f"trades one spec ({book_spec_path.name}) unless every enabled sleeve carries "
                f"a risk_budget (quantt/session/combine.py); it will not trade one and ignore "
                f"the rest")
        i, e = enabled[0]
        sp = e.get("spec_path")
        if not isinstance(sp, str) or (repo / sp).resolve() != Path(book_spec_path).resolve():
            raise CombineError(
                f"{book_path}: the one enabled sleeve, sleeves[{i}], names spec_path {sp!r}, "
                f"but the runner trades {book_spec_path}; they must be the same file")
        return None
    unbudgeted = [i for i, e in enabled if "risk_budget" not in e]
    if unbudgeted:
        raise CombineError(f"{book_path}: enabled sleeves {unbudgeted} carry no risk_budget while "
                           f"{budgeted} do; a combined book sizes every enabled sleeve by its "
                           f"budget and assumes none")
    from src.deploy.registry import CEF_FLOOR_KEY, CEF_THIN_KEYS, build_sleeve
    # ONE SIZING AUTHORITY PER BOOK (CEF trial 53). A spec's `sizing_multiplier`
    # sizes a single-sleeve account (src/deploy/sleeves/cef_discount.py); a
    # combined book sizes each sleeve by its budget (THE RISK BUDGET). Both at
    # once would compound, so an enabled budgeted sleeve whose spec sets the key
    # is refused here, naming it, and a book spec that sets it is refused by
    # `book_vol_target`. Re-express it as budgets first.
    out, seen = [], set()
    for i, e in enabled:
        where = f"{book_path}: sleeves[{i}]"
        name = e.get("name")
        if not isinstance(name, str) or not name:
            raise CombineError(f"{where}: name {name!r} must be a non-empty string")
        if name in seen:
            raise CombineError(f"{where}: two enabled sleeves are named {name!r}")
        seen.add(name)
        if "spec" in e:
            raise CombineError(f"{where}: an inline `spec` is not read by the runner; name a "
                               f"frozen spec file in spec_path")
        sp = e.get("spec_path")
        if not isinstance(sp, str) or not (repo / sp).is_file():
            raise CombineError(f"{where}: spec_path {sp!r} is not a file under {repo}")
        spec = json.loads((repo / sp).read_text())
        if "capital_usd" not in spec or "spec_id" not in spec:
            raise CombineError(f"{where}: {sp} has no capital_usd or spec_id")
        if (spec.get("frozen") or {}).get("sizing_multiplier") is not None:
            raise CombineError(
                f"{where}: {sp} sets frozen.sizing_multiplier, which sizes a single-sleeve "
                f"account; a combined book sizes every sleeve by its risk_budget, and the two "
                f"would compound. Delete the multiplier or re-express it as the budget")
        # CEF TRIAL 54 (PREREG_C4_LEVEL_2026-11-02.md §1.3 test 7): `level_signal` blends C4's z and
        # family-level books at equal ex-ante risk under the account's own 1.90 cap. That construction was
        # measured as ONE account's book only: the blend's cap-binding share and turnover (§3.3), the
        # fidelity probe and the kill rule's reference are all single-sleeve objects. Netted with another
        # sleeve under a shared budget and the book-level cap, it is a book nobody measured, so a budgeted
        # sleeve whose spec carries the key (null included) is refused here, as the multiplier is.
        if "level_signal" in (spec.get("frozen") or {}):
            raise CombineError(
                f"{where}: {sp} sets frozen.level_signal (CEF trial 54), a blend measured only as a "
                f"single-sleeve account's book; a combined book would net it with other sleeves under a "
                f"shared budget and cap that were never measured with it. Trade it as its own book")
        # CEF TRIAL 55 ("te4", PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md; the runner owner's review of
        # 2026-11-04, item 1): `below_min_names = "trade_eligible"` builds a 4-5 name book on a thin
        # session, PAPER ONLY, and its stops (K0 on the account's drawdown, K1-K3 on the account's
        # equity and positions) were measured on the core's own account. Netted with another sleeve
        # under a shared budget and the book-level cap it is a book nobody scored, and its stops would
        # read an account that is not its own. So a budgeted sleeve whose spec carries ANY te4 key is
        # refused here, as level_signal is: the rule itself, its floor, or a K-line threshold or K3's
        # run length in `risk` (each present only beside the rule, so present at all is the tell).
        # Until 2026-11-04 the combiner built such a sleeve and it refused at its first decide (the
        # combiner passes no paper declaration); now it never loads.
        fr, rk = spec.get("frozen") or {}, spec.get("risk") or {}
        te4 = ([f"frozen.below_min_names={fr['below_min_names']!r}"]
               if fr.get("below_min_names") == "trade_eligible" else []) + \
            ([f"frozen.{CEF_FLOOR_KEY}"] if CEF_FLOOR_KEY in fr else []) + \
            [f"risk.{k}" for k in CEF_THIN_KEYS if isinstance(rk, dict) and k in rk]
        if te4:
            raise CombineError(
                f"{where}: {sp} sets {te4} (CEF trial 55, te4: the thin-session rule, PAPER ONLY), "
                f"built and measured for the core's own account; a combined book would net it with "
                f"other sleeves, and its stops would read an account that is not its own. Trade it "
                f"as its own book, or delete the keys")
        # The built sleeve's own instruments, as deployed_tickers reads them:
        # "the exact list the runner will trade". The registry validates the spec.
        universe = tuple(sorted(build_sleeve(spec, float(spec["capital_usd"])).instruments()))
        if not universe:
            raise CombineError(f"{where}: {sp} builds a sleeve with no instruments")
        out.append(SleeveEntry(name=name, spec_id=str(spec["spec_id"]), spec_path=sp,
                               universe=universe, risk_budget=_budget(e, where),
                               vol_target=_vol_target(spec, f"{where} ({sp})"),
                               targets=make_targets(spec),
                               panel=None if panel_of is None else panel_of(spec)))
    _refuse_shared(out, str(book_path))
    return tuple(out)


def book_universe(sleeves) -> tuple:
    """The union of the enabled sleeves' universes, sorted."""
    return tuple(sorted({s for e in sleeves for s in e.universe}))


def book_params(p: dict, sleeves) -> dict:
    """`run.spec_params(book spec)` for a combined book: the book spec's limits
    (min_trade_usd, max_gross_usd, max_gross_stress, spec_id) with the universe
    replaced by the union, which is what the closes, NAVs, assets, gate 9 and
    decide must cover."""
    return {**p, "universe": book_universe(sleeves)}


def universes(sleeves) -> dict:
    """{sleeve name: its universe}, for gate 5 per sleeve."""
    return {e.name: e.universe for e in sleeves}


def sleeve_nav(equity: float, risk_budget: float, book_vol: float, sleeve_vol: float) -> float:
    """equity × b × σ_book / σ_sleeve (docstring, THE RISK BUDGET). Written so
    that b = 1 and σ_book == σ_sleeve multiply equity by exactly 1.0."""
    return equity * (risk_budget * book_vol / sleeve_vol)


def _close(closes: dict, sym: str) -> float:
    """decide's rule for a close that sizes a weight: finite and > 0, else raise."""
    c = closes.get(sym)
    if c is None or isinstance(c, bool) or not math.isfinite(float(c)) or float(c) <= 0:
        raise CombineError(f"{sym}: no usable close ({c!r}) to size a weight target")
    return float(c)


def decide(sleeves, *, asof, positions: dict, equity: float, closes: dict, shortable: dict,
           opening: bool, nav_hold: dict, held: dict, book_vol: float,
           session_date, cid_prefix: str, min_trade_usd: float,
           time_in_force: str) -> tuple:
    """The combined book's (decide.Decision, plan.json `combine` record). See
    the module docstring.

    nav_hold   {ticker: reason} the stale-NAV gate holds (union); each sleeve
               gets the ones in its universe
    held       {sleeve: [why]} gate 5 holds at the final check
               (`gate.gate_data_by_sleeve`); such a sleeve is not asked for
               targets and keeps its attributed shares
    book_vol   `book_vol_target(book spec)`
    """
    names = [e.name for e in sleeves]
    if not names or len(set(names)) != len(names):
        raise CombineError(f"sleeves {names}: need at least one, each named once")
    _refuse_shared(sleeves, "combine.decide")
    union = book_universe(sleeves)
    owners = {s: tuple(e.name for e in sleeves if s in e.universe) for s in union}
    for s, q in positions.items():
        if type(q) is not int:
            raise CombineError(f"position {s}={q!r} is not an int number of shares")
    shared = sorted(s for s, q in positions.items() if q != 0 and len(owners.get(s, ())) > 1)
    if shared:
        raise CombineError(
            f"the account holds {shared}, each in more than one enabled sleeve's universe "
            f"({ {s: owners[s] for s in shared} }); splitting a held position between "
            f"sleeves needs a per-sleeve sub-ledger, which is not built (combine.py, HOLDINGS)")
    if set(held) - set(names):
        raise CombineError(f"gate 5 held {sorted(set(held) - set(names))}, not enabled sleeves")
    if set(nav_hold) - set(union):
        raise CombineError(f"the stale-NAV gate held {sorted(set(nav_hold) - set(union))}, "
                           f"in no enabled sleeve's universe")

    record = {}
    for e in sleeves:
        mine = {s: q for s, q in positions.items() if s in e.universe}
        nav = sleeve_nav(equity, e.risk_budget, book_vol, e.vol_target)
        r = {"spec_id": e.spec_id, "spec_path": e.spec_path, "risk_budget": e.risk_budget,
             "vol_target": e.vol_target, "sleeve_nav": nav}
        rows = {}
        if e.name in held:
            why = "; ".join(held[e.name])
            r.update(status="held", held_why=list(held[e.name]))
            for s in e.universe:
                cur = mine.get(s, 0)
                rows[s] = {"current": cur, "target": cur, "kind": "held",
                           "reason": f"held at current shares: gate 5 at the final check: {why}"}
        else:
            hold = {k: v for k, v in nav_hold.items() if k in e.universe}
            kw = {"nav_hold": {"asof": asof, "names": hold}} if hold else {}
            r["status"] = "decided"
            if hold:
                r["nav_hold"] = sorted(hold)
            by = {}
            for t in e.targets(asof, mine, nav, opening, **kw):
                if t.instrument in by:
                    raise CombineError(f"sleeve {e.name} emitted two targets for {t.instrument}")
                if t.instrument not in e.universe:
                    raise CombineError(f"sleeve {e.name} emitted {t.instrument}, not in its "
                                       f"universe {list(e.universe)}")
                by[t.instrument] = t
            missing = [s for s in e.universe if s not in by]
            if missing:
                raise CombineError(f"sleeve {e.name} emitted no target for {missing}; refusing "
                                   f"to treat a missing target as flat")
            for s in e.universe:
                t = by[s]
                need = t.side != FLAT and t.qty is None
                tgt, kind = dec.target_shares(t, nav, _close(closes, s) if need else None)
                rows[s] = {"current": mine.get(s, 0), "target": tgt, "kind": kind,
                           "reason": t.reason}
        r["targets"] = rows
        record[e.name] = r

    combined = []
    for s in union:
        net = sum(record[o]["targets"][s]["target"] for o in owners[s])
        why = "combined: " + " | ".join(
            f"{o} {record[o]['targets'][s]['target']:+d} ({record[o]['targets'][s]['reason']})"
            for o in owners[s])
        if net == 0:
            combined.append(PositionTarget(instrument=s, side=FLAT, reason=why))
        else:
            combined.append(PositionTarget(instrument=s, side=LONG if net > 0 else SHORT,
                                           qty=net, reason=why))
    decision = dec.decide(combined, positions, equity, closes, shortable,
                          session_date=session_date, universe=union, cid_prefix=cid_prefix,
                          min_trade_usd=min_trade_usd, time_in_force=time_in_force)
    return decision, {"book_vol_target": book_vol, "sleeves": record}


def lines(record: dict) -> list:
    """One log line per sleeve (the combined book only)."""
    out = []
    for name, r in record["sleeves"].items():
        tg = r["targets"].values()
        out.append(f"  sleeve {name}: {r['status']}, budget {r['risk_budget']:g} of the book's "
                   f"vol target {record['book_vol_target']:g}, sleeve_nav ${r['sleeve_nav']:,.2f}, "
                   f"{sum(1 for t in tg if t['target'])} of {len(r['targets'])} names held after"
                   + (f"; HELD: {'; '.join(r['held_why'])}" if r["status"] == "held" else "")
                   + (f"; NAV holds {r['nav_hold']}" if r.get("nav_hold") else ""))
    return out
