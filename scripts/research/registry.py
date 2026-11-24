"""The trial registry: every trial's daily P&L series, stored where the inference
module can read it back.

WHY THIS FILE EXISTS (2026-10-27). The team lead ruled (docs/SYSTEM.md §5,
2026-10-27) that the paper's deflated-Sharpe bar gates "once trials store their
daily P&L series". That bar uses the Gumbel expected maximum, the effective N
and the measured cross-trial V[SR_n]. Until then, the desk's sqrt(2 ln N) on the
raw counter gates. Every input the paper's bar needs beyond the selected
strategy is a property of the whole SET of trials:

  - the effective number of independent trials: N_hat = rho_bar + (1 - rho_bar) M,
    which needs every trial's series to measure rho_bar
    (Bailey & López de Prado 2014, Appendix A.3);
  - the variance of Sharpe ratios across trials, V[SR_n];
  - the T x N P&L matrix that PBO/CSCV ranks (Bailey, Borwein, López de Prado &
    Zhu 2017).

A counter cannot supply any of them. López de Prado & Lewis (2019): "ignorance
of [E[K] and E[V[SR_k]]] makes it impossible to assess whether a discovery is
false" (3-0 verified, 2026-10-27). So every trial stores its series here, and
`bar_inputs` measures the inputs at run time (H14). It never reads them from a
document.

WHAT IS STORED WHERE
- `ledger.jsonl` (tracked) has one line per stored variant: counter, trial,
  variant, the commit and whether the tree was dirty, the series' first and
  last dates, n, gross Sharpe, skew, raw kurtosis, the series' sha256 and the
  parameters.
- `series/<counter>/<trial>/<variant>.parquet` (GITIGNORED) is the series
  itself. The repository is public, and an event book's daily P&L can be one
  CRSP-licensed security's return in all but name. E1's module rule is "never a
  row-level price or return" in a tracked file. The ledger's sha256 is the
  tracked commitment: `load` refuses a series whose bytes no longer match it.

A TRIAL HERE IS THE COUNTER'S TRIAL. `trial` must be `<COUNTER>-<n>`, where
1 <= n <= the counter's canonical count: the n-th trial the counter was
incremented for (for example "CEF-53"). That is what lets `bar_inputs` measure
coverage. A free-form id once let three labels for one trial cover a counter of
three (quant-reviewer, 2026-10-28). `variant` names each configuration that
trial evaluated. Clustering for the effective N runs over variants, because
correlated variants of one idea are the case it exists for.

Names are compared case-folded, and a series file is created exclusively. On a
case-insensitive volume, variant "wide" otherwise overwrote "Wide"'s file
(quant-reviewer, 2026-10-28).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "results" / "research" / "trials"
LEDGER = "ledger.jsonl"
SLATES = ROOT / "declared_slates.json"      # tracked: the team lead's declared N per counter
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def _counters() -> dict:
    """The canonical counters, read through `ops.orient.trials()`, so there is
    one parser for the table (docs/RESEARCH_STATE.md)."""
    import sys
    sys.path.insert(0, str(REPO))
    from ops.orient import trials
    return trials()["counters"]


def _git(*args) -> str:
    out = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {out.stderr.strip()}; "
                           "a trial with no commit has no provenance")
    return out.stdout.strip()


def _series_bytes(pnl: pd.Series) -> bytes:
    """The canonical bytes a series is hashed and stored as: float64 values,
    plus the index as int64 nanoseconds. Parquet is written from these
    values, and `load` re-derives the bytes before comparing."""
    return (pnl.to_numpy(dtype="float64").tobytes()
            + pnl.index.asi8.tobytes())


def _check_series(pnl: pd.Series) -> None:
    if not isinstance(pnl, pd.Series):
        raise TypeError("pnl must be a pandas Series (one value per session)")
    if not isinstance(pnl.index, pd.DatetimeIndex) or pnl.index.tz is not None:
        raise TypeError("pnl must be indexed by tz-naive session dates")
    if not pnl.index.is_monotonic_increasing or not pnl.index.is_unique:
        raise ValueError("pnl's index must be sorted and unique")
    if len(pnl) < 2:
        raise ValueError("a series of fewer than 2 sessions has no Sharpe")
    if not np.isfinite(pnl.to_numpy(dtype=float)).all():
        raise ValueError("pnl holds NaN or inf; store the series evaluate() returned, "
                         "which has neither")
    if np.ptp(pnl.to_numpy(dtype=float)) == 0:       # std() of a constant float is ~1e-19, not 0
        raise ValueError("pnl is constant; a flat book is not a trial")


def record(pnl: pd.Series, *, counter: str, trial: str, variant: str, params: dict,
           note: str = "", root: Path = ROOT, allow_dirty: bool = False,
           judged: bool = False) -> dict:
    """Store one variant's daily P&L under its counter and trial.

    `judged=True` marks the configuration the pre-registration selects. The
    paper's bar takes ONE series per trial (`paper_sr0`): the judged one, or the
    trial's only series. A trial that stores several configurations, as PBO
    needs, must mark exactly one of them. Otherwise its stored near-duplicates
    would pull rho_bar up and the counter's bar down (quant-reviewer,
    2026-10-28: eight copies of one EVENTS trial moved the bar from 0.363 to
    0.239). Pass judged=True even on a trial's only series: an unflagged sole
    series counts, but a second variant added later leaves the trial with none
    judged, and the flag can never be added afterwards. The eight backfilled
    lines were marked judged in the ledger on 2026-10-28, sha256 unchanged.

    Refuses:
    - a counter the canonical table does not hold;
    - a name the filesystem would mangle;
    - a series with NaN, inf, an unsorted index or zero variance;
    - a dirty working tree unless `allow_dirty`, because the commit is the
      provenance and a dirty tree's commit does not reproduce the series (the
      ledger records the flag either way);
    - a second, DIFFERENT series under an existing (counter, trial, variant).
      Re-recording identical bytes is a no-op that returns the existing line,
      so a re-run is safe and a changed result can never silently replace the
      one that was judged. A re-record with a different `judged` flag is refused
      too;
    - a second judged variant in one trial.
    """
    if not isinstance(judged, bool):
        raise TypeError(f"judged must be True or False, got {judged!r}")
    _check_series(pnl)
    pnl = pd.Series(pnl.to_numpy(dtype="float64"),
                    index=pnl.index.as_unit("ns"))       # one byte layout to hash and store
    counters = _counters()
    if counter not in counters:
        raise ValueError(f"counter {counter!r} is not in the canonical table "
                         f"({sorted(counters)}); open a counter there first")
    for what, v in (("trial", trial), ("variant", variant)):
        if not _NAME.match(v):
            raise ValueError(f"{what} {v!r} must match {_NAME.pattern}")
    try:
        json.dumps(params)
    except TypeError as e:
        raise TypeError(f"params must be JSON-serialisable: {e}") from None
    n = _trial_no(counter, trial)
    if n is None or trial != f"{counter}-{n}" or not 1 <= n <= counters[counter]["trials"]:
        raise ValueError(f"trial {trial!r} must be {counter}-<n>, written without leading zeros, with "
                         f"1 <= n <= {counters[counter]['trials']} (the counter's canonical count); "
                         "increment the counter before storing the trial")
    commit = _git("rev-parse", "HEAD")
    # Untracked files count under the code directories: a new trial runner is
    # usually untracked, and HEAD would not contain the code that made the series
    # (quant-reviewer, 2026-10-28). Untracked outputs elsewhere do not count.
    dirty = bool(_git("status", "--porcelain", "--untracked-files=no")) or bool(
        _git("status", "--porcelain", "--untracked-files=all", "--", "scripts", "src", "quantt", "ops"))
    if dirty and not allow_dirty:
        raise RuntimeError("the working tree has uncommitted changes, so HEAD does not "
                           "reproduce this series; commit first, or pass allow_dirty=True "
                           "and the ledger will say so")
    root = Path(root)
    sha = hashlib.sha256(_series_bytes(pnl)).hexdigest()
    key = (counter, trial.casefold(), variant.casefold())
    existing = [r for r in _read_ledger(root)
                if (r["counter"], r["trial"].casefold(), r["variant"].casefold()) == key]
    if existing:
        if existing[-1]["sha256"] == sha and (existing[-1]["trial"], existing[-1]["variant"]) == (trial, variant):
            if existing[-1].get("judged", False) != judged:      # lines before 2026-10-28 carry no flag
                raise ValueError(f"{counter}/{trial}/{variant} is stored with judged="
                                 f"{existing[-1].get('judged', False)}; the flag is never changed after recording")
            return existing[-1]
        raise ValueError(f"{counter}/{trial}/{variant} is already stored (as "
                         f"{existing[-1]['trial']}/{existing[-1]['variant']}; names compare case-folded) "
                         "with a different series or spelling; a judged result is never replaced. "
                         "Use a new variant name")
    if judged:
        other = [r["variant"] for r in _read_ledger(root)
                 if r["counter"] == counter and _trial_no(counter, r["trial"]) == n and r.get("judged") is True]
        if other:
            raise ValueError(f"{counter}/{trial} already has a judged variant ({other[0]}); "
                             "a trial is judged on one configuration")
    rel = Path("series") / counter / trial / f"{variant}.parquet"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"{path} exists with no ledger line for it; refusing to overwrite")
    buf = io.BytesIO()
    pnl.rename("pnl").to_frame().to_parquet(buf)
    with open(path, "xb") as f:                          # exclusive create
        f.write(buf.getvalue())
    x = pnl.to_numpy(dtype=float)
    line = dict(
        ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        counter=counter, trial=trial, variant=variant, note=note,
        commit=commit, dirty=dirty,
        first=pnl.index[0].date().isoformat(), last=pnl.index[-1].date().isoformat(),
        n=len(x), sr_annual=float(x.mean() / x.std(ddof=1) * np.sqrt(252)),
        skew=float(pd.Series(x).skew()), kurt=float(pd.Series(x).kurt() + 3.0),
        sha256=sha, path=str(rel), params=params, judged=judged)
    with open(root / LEDGER, "a") as f:
        f.write(json.dumps(line, sort_keys=True) + "\n")
    return line


def _read_ledger(root: Path) -> list[dict]:
    p = Path(root) / LEDGER
    if not p.exists():
        return []
    return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]


def entries(counter: str, *, trials=None, root: Path = ROOT) -> list[dict]:
    """The ledger lines for one counter, optionally restricted to some trials."""
    rows = [r for r in _read_ledger(root) if r["counter"] == counter]
    if trials is not None:
        want = set(trials)
        rows = [r for r in rows if r["trial"] in want]
        missing = want - {r["trial"] for r in rows}
        if missing:
            raise ValueError(f"no stored series for trial(s) {sorted(missing)} on {counter}")
    return rows


def load(entry: dict, *, root: Path = ROOT) -> pd.Series:
    """One stored series. Raises if its bytes no longer match the ledger."""
    path = Path(root) / entry["path"]
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing; the series lives only on the machine "
                                "that recorded it (it is gitignored)")
    s = pd.read_parquet(path)["pnl"]
    s.index = pd.DatetimeIndex(s.index).as_unit("ns")
    if hashlib.sha256(_series_bytes(s)).hexdigest() != entry["sha256"]:
        raise ValueError(f"{path} does not match its ledger sha256; it was altered after it "
                         "was recorded")
    return s


def matrix(counter: str, *, trials=None, root: Path = ROOT) -> tuple[pd.DataFrame, dict]:
    """The T x N matrix of a counter's stored variants, on the sessions all of
    them share (PBO/CSCV and the correlation need a common T). The second value
    says how many sessions the intersection dropped, so a short variant cannot
    silently cut the sample."""
    rows = entries(counter, trials=trials, root=root)
    if not rows:
        raise ValueError(f"no stored series on {counter}")
    cols = {f"{r['trial']}/{r['variant']}": load(r, root=root) for r in rows}
    full = pd.concat(cols, axis=1)
    common = full.dropna()
    return common, dict(n_variants=len(cols), union_sessions=len(full),
                        common_sessions=len(common), dropped=len(full) - len(common))


def _trial_no(counter: str, trial: str):
    """n for a trial id "<COUNTER>-<n>", else None. Grouping keys on n, so
    "EVENTS-03" can never be a second EVENTS-3 (`record` refuses that spelling;
    quant-reviewer, 2026-10-28)."""
    m = re.match(rf"^{re.escape(counter)}-(\d+)$", trial)
    return int(m.group(1)) if m else None


def _coverage(counter: str, *, root: Path = ROOT) -> dict:
    """Which of the counter's canonical trials have a stored series, from the
    ledger lines alone. Ruling 1's switch condition (2026-10-27) needs no series
    loaded, so a stray variant on its own window cannot break it."""
    canon = _counters()[counter]["trials"]
    nums = {n for r in entries(counter, root=root)
            if (n := _trial_no(counter, r["trial"])) is not None and 1 <= n <= canon}
    return dict(canonical_trials=canon, stored_trials=len(nums),
                coverage=len(nums) / canon if canon else None,
                paper_bar_may_gate=bool(canon) and len(nums) >= canon)


def bar_inputs(counter: str, *, root: Path = ROOT) -> dict:
    """Everything the paper's deflated-Sharpe bar needs beyond the selected
    strategy, measured now from the stored series. It also says whether the
    paper's bar may gate under the 2026-10-27 ruling.

    `coverage` compares the stored TRIALS with the counter's canonical count.
    The ruling is that the paper's bar gates "once trials store their daily
    P&L series". While some of the counter's trials have no stored series, the
    measured rho_bar and V[SR] describe only part of the search, so
    `paper_bar_may_gate` is False and the desk's bar gates. This is measured at
    every call (H14). Whether to backfill old trials is the team lead's
    decision (DESK_METHOD §7 item 6).

    rho_bar is the mean off-diagonal correlation of the variants' P&L on their
    common sessions, as measured. n_effective floors it at 0 because
    effective_trials needs 0 <= rho <= 1. With one stored variant there is no
    correlation to measure: rho_bar and sr_var are None, never a stand-in.
    (rho_bar used to be 1.0 there, which would put the paper's N at 1 and its bar
    at zero.) `ill_conditioned` is True when T < M(M-1)/2: there are too few
    sessions to pin down M(M-1)/2 correlations (López de Prado & Lewis 2019).

    NEVER GATE ON n_effective AND sr_var AS RETURNED. They are raw: N counts the
    stored variants, and V is unfloored. On 2026-10-28 they put EVENTS' bar at an
    annualised 0.06. The team lead ruled the same day that the paper's bar uses
    the declared slate size and floors V at 1/T (docs/SYSTEM.md §5). That is
    `paper_sr0`, and `bars` reports it beside the desk's bar.
    """
    from scripts.research.inference import effective_trials
    cov = _coverage(counter, root=root)
    M, info = matrix(counter, root=root)
    m = M.shape[1]
    measured = m >= 2 and len(M) >= 3                   # variants on disjoint windows share no session
    if measured:
        C = M.corr().to_numpy()
        rho = float(C[~np.eye(m, dtype=bool)].mean())
    else:
        rho = None                                      # unmeasured, never a stand-in
    sr = M.mean() / M.std(ddof=1)                       # per period
    return dict(counter=counter, canonical_trials=cov["canonical_trials"], stored_trials=cov["stored_trials"],
                coverage=cov["coverage"], paper_bar_may_gate=cov["paper_bar_may_gate"],
                variants=m, T=info["common_sessions"], dropped_sessions=info["dropped"],
                rho_bar=rho,
                n_effective=(effective_trials(m, min(max(rho, 0.0), 1.0)) if measured
                             else 1.0 if m == 1 else None),
                sr_var=float(sr.var(ddof=1)) if measured else None,
                ill_conditioned=info["common_sessions"] < m * (m - 1) / 2)


class PaperBarRefused(ValueError):
    """The paper's bar cannot be computed as the team lead ruled it on 2026-10-28.
    The message names the missing input. `bars` reports it in place of the paper's
    bar, and never substitutes another bar.

    `code` says which input is missing, so a caller applies the rulings without
    parsing prose: not_qualified, one_trial, ambiguous_judged, few_sessions,
    no_series. For `one_trial` the desk's bar gates until a second trial is
    stored (team lead, 2026-10-28, later; docs/SYSTEM.md §5). Any other code
    closes the standalone route."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


# -- declared slates: the least N a trial may be judged at --------------------

def _slates() -> dict:
    """The declared slates in `results/research/trials/declared_slates.json`,
    by counter. A counter's declared N is a ruling, like its trial count: no
    code can measure it, so it is read from one tracked table rather than parsed
    out of prose. Only the team lead adds or changes a row; each row names the
    ruling it copies. The table is validated whole on every read: a misspelt
    counter would otherwise bind nothing, silently.
    """
    if not SLATES.exists():
        raise FileNotFoundError(f"{SLATES} is missing; the least declared N cannot be "
                                "determined without it")
    rows = json.loads(SLATES.read_text())["slates"]
    counters = _counters()
    out: dict = {}
    for r in rows:
        missing = {"counter", "declared_n", "status", "ruled", "source"} - set(r)
        if missing:
            raise ValueError(f"declared slate {r} lacks {sorted(missing)}")
        if r["counter"] not in counters:
            raise ValueError(f"declared slate for {r['counter']!r}, which is not a canonical counter")
        n = r["declared_n"]
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError(f"declared slate {r['counter']}: declared_n must be a positive integer, got {n!r}")
        if r["status"] not in ("standing", "closed"):
            raise ValueError(f"declared slate {r['counter']}: status must be standing or closed, got {r['status']!r}")
        # A slate can close below its N (XASSET was declared at 5 and re-declared
        # at 4), so the trials it holds are recorded, not inferred from N.
        k = r.get("closed_at")
        if r["status"] == "closed" and (isinstance(k, bool) or not isinstance(k, int) or k < 1):
            raise ValueError(f"closed slate {r['counter']}: closed_at must be the trial count when it "
                             f"closed, a positive integer, got {k!r}")
        if r["status"] == "standing" and "closed_at" in r:
            raise ValueError(f"standing slate {r['counter']} has closed_at; only a closed slate does")
        dt.date.fromisoformat(r["ruled"])
        if not str(r["source"]).strip():
            raise ValueError(f"declared slate {r['counter']} names no source")
        out.setdefault(r["counter"], []).append(r)
    for c, rs in out.items():
        if sum(r["status"] == "standing" for r in rs) > 1:
            raise ValueError(f"{c} has more than one standing declared slate")
    return out


def minimum_declared_n(counter: str, *, pending: int = 0) -> dict:
    """The least N a trial on `counter` may declare, measured now (H14).

    `pending` is how many trials are about to be added: 1 at design time, 0
    once the pre-registration's commit has incremented the counter.
    - A standing slate: max(the counter after `pending`, the slate's N). EVENTS'
      N = 6 is shared by every EVENTS trial (team lead, 2026-10-19).
    - A closed slate: no new trial joins it. Past trials, up to the count it
      closed with (`closed_at`), keep its N. One more trial needs a new
      declaration, which is the team lead's ruling, so `needs_ruling` is True
      and there is no minimum (XASSET, closed with 4 trials at N = 4). The count
      is recorded because a slate can close below its N.
    - No slate: a running count, so the counter itself.
    A trial judged below its counter, or below a standing slate, would lower
    both bars. On 2026-10-28 an EVENTS trial declared at 3 would have faced
    0.238 in place of 0.363 (quant-reviewer).
    """
    if isinstance(pending, bool) or not isinstance(pending, int) or pending < 0:
        raise ValueError(f"pending must be a non-negative integer, got {pending!r}")
    counters = _counters()
    if counter not in counters:
        raise ValueError(f"{counter!r} is not a canonical counter ({sorted(counters)})")
    after = counters[counter]["trials"] + pending
    rows = _slates().get(counter, [])
    standing = [r for r in rows if r["status"] == "standing"]
    closed = [r for r in rows if r["status"] == "closed"]
    base = dict(counter=counter, canonical_trials=counters[counter]["trials"], pending=pending,
                counter_after=after, slate=None, minimum=None, needs_ruling=False)
    if standing:
        r = standing[0]
        return {**base, "slate": r, "minimum": max(after, r["declared_n"]),
                "why": f"standing slate N = {r['declared_n']} ({r['ruled']}) and the counter at {after}"}
    if closed:
        r = max(closed, key=lambda x: x["closed_at"])
        if after > r["closed_at"]:
            return {**base, "slate": r, "needs_ruling": True,
                    "why": f"{counter}'s slate (N = {r['declared_n']}, {r['ruled']}) closed with "
                           f"{r['closed_at']} trials; trial {after} needs a new declared slate, which is "
                           "the team lead's ruling"}
        return {**base, "slate": r, "minimum": max(after, r["declared_n"]),
                "why": f"closed slate N = {r['declared_n']} ({r['ruled']}), which judged trials 1..{r['closed_at']}"}
    return {**base, "minimum": after, "why": f"no declared slate: a running count, {after}"}


def _check_declared(counter: str, declared_n) -> dict:
    """Refuse a declared N that is not an integer, that is below the least N, or
    that would start a slate only the team lead can declare. Both bars use it."""
    if isinstance(declared_n, bool) or not isinstance(declared_n, (int, np.integer)) or declared_n < 1:
        raise ValueError(f"declared_n must be a positive integer from the pre-registration, got {declared_n!r}")
    m = minimum_declared_n(counter)
    if m["needs_ruling"]:
        raise ValueError(f"declared_n {declared_n} on {counter}: {m['why']}")
    if declared_n < m["minimum"]:
        raise ValueError(f"declared_n {declared_n} is below {counter}'s least N {m['minimum']} "
                         f"({m['why']}); a declared slate holds every trial judged on it")
    return m


# -- the bars -----------------------------------------------------------------

def _pick(counter: str, n: int, *, root: Path = ROOT) -> dict:
    """The ledger line trial n is judged on: its only series, or the one recorded
    with judged=True. Lines are grouped by n, never by the id's spelling."""
    rs = [r for r in entries(counter, root=root) if _trial_no(counter, r["trial"]) == n]
    judged = [r for r in rs if r.get("judged") is True]
    if not rs:
        raise ValueError(f"{counter}-{n} has no stored series")
    if len(judged) > 1 or (len(rs) > 1 and len(judged) != 1):
        raise PaperBarRefused(f"{counter}-{n} stores {len(rs)} variants and {len(judged)} are marked "
                              "judged; a trial is judged on one series (record(..., judged=True) on the "
                              "configuration the pre-registration selects)", "ambiguous_judged")
    return judged[0] if judged else rs[0]


def _judged_matrix(counter: str, *, root: Path = ROOT) -> tuple[pd.DataFrame, dict]:
    """One series per counted trial, on the sessions they share: the trial's only
    stored series, or the one recorded with judged=True. The paper's N counts
    trials, so rho_bar and V[SR] must be measured across trials, never across a
    trial's own configurations (`record`'s docstring has the failure)."""
    canon = _counters()[counter]["trials"]
    nums = sorted({n for r in entries(counter, root=root)
                   if (n := _trial_no(counter, r["trial"])) is not None and 1 <= n <= canon})
    picks = [_pick(counter, n, root=root) for n in nums]
    if not picks:
        raise PaperBarRefused(f"no counted trial on {counter} has a stored series", "no_series")
    full = pd.concat({f"{r['trial']}/{r['variant']}": load(r, root=root) for r in picks}, axis=1)
    common = full.dropna()
    return common, dict(union_sessions=len(full), common_sessions=len(common),
                        dropped=len(full) - len(common))


def paper_sr0(counter: str, *, declared_n: int, root: Path = ROOT) -> dict:
    """The paper's best-of-N bar as the team lead ruled it on 2026-10-28
    (docs/SYSTEM.md §5, "How the paper's bar is computed once a counter
    qualifies"): `inference.safeguarded_sr0` at the DECLARED N, with rho_bar,
    V[SR] and the common T measured now, across one series per trial
    (`_judged_matrix`).

    WHY THIS EXISTS. `bar_inputs` hands back the raw N and V, and an agent that
    assembles the bar from them gets EVENTS' 0.06. This function is the one place
    the safeguarded bar is assembled. The loop and the statistician call it and
    never build the bar themselves. `sr_var_used` is the V the bar uses; pass it,
    with `n_effective`, to `inference.p_pass_dsr(bound="gumbel")` for a power
    figure on the same bar.

    `declared_n` is the N the trial's pre-registration declares, read from that
    record (H14), never typed as a literal. It raises ValueError below
    `minimum_declared_n`. Raises PaperBarRefused, naming the missing input, when:
    - the counter does not qualify (`paper_bar_may_gate` is False). Under the
      2026-10-27 ruling the desk's bar gates there;
    - a trial with several stored variants marks none, or several, as judged;
    - fewer than two trials are stored, so rho_bar and V[SR] are unmeasured.
    Coverage is read from the ledger lines (`_coverage`), so a stray variant on a
    window of its own cannot break the bar.
      The safeguards floor V but say nothing about an unmeasured rho.

    Which counters the ruling excludes is read from SYSTEM.md by the caller: on
    2026-10-28 that was CEF, which cannot qualify in any case (50 of its 52
    trials cannot be rebuilt). Returns sr0 per period and annualised at 252.
    """
    from scripts.research.inference import effective_trials, safeguarded_sr0
    _check_declared(counter, declared_n)
    b = _coverage(counter, root=root)
    if not b["paper_bar_may_gate"]:
        raise PaperBarRefused(f"{counter} does not qualify: {b['stored_trials']} of its "
                              f"{b['canonical_trials']} trials have a stored series", "not_qualified")
    J, info = _judged_matrix(counter, root=root)
    k, T = J.shape[1], len(J)
    if k < 2:
        raise PaperBarRefused(f"{counter} has {k} trial with a stored series; rho_bar and V[SR] "
                              "across trials are unmeasured with fewer than two; the desk's bar gates until "
                              "a second trial is stored (team lead, 2026-10-28)", "one_trial")
    if T < 3:
        raise PaperBarRefused(f"{counter}'s trials share {T} sessions; too few to measure rho_bar", "few_sessions")
    C = J.corr().to_numpy()
    rho = float(C[~np.eye(k, dtype=bool)].mean())
    v = float((J.mean() / J.std(ddof=1)).var(ddof=1))   # per-period Sharpes, across trials
    floor = 1 / T
    sr0 = safeguarded_sr0(declared_n, rho, v, T)
    return dict(counter=counter, declared_n=int(declared_n), trials=list(J.columns),
                stored_trials=b["stored_trials"], canonical_trials=b["canonical_trials"],
                rho_bar=rho, n_effective=effective_trials(declared_n, min(max(rho, 0.0), 1.0)),
                sr_var_measured=v, sr_var_floor=floor, sr_var_used=max(v, floor),
                floor_binds=v < floor, T=T, dropped_sessions=info["dropped"],
                sr0=sr0, sr0_annual=sr0 * np.sqrt(252))


def bars(counter: str, *, trial: str, variant: str, declared_n: int, root: Path = ROOT) -> dict:
    """Both deflated-Sharpe bars for one stored series, labelled. Which one gates
    is the team lead's, read from docs/SYSTEM.md §5 by the caller.

    - desk: √(2 ln N) with V = 1/T of THIS series (`inference.desk_dsr`, which is
      `validate._dsr`). N is declared_n, as for the paper's bar. A declared slate
      is judged at its declared size: E1 and NAV tenders were judged at
      √(2 ln 6) with two EVENTS trials spent (docs/RESEARCH_STATE.md).
    - paper: `paper_sr0`, the 2026-10-28 safeguards, through `inference.psr`. Its
      floor uses the trials' COMMON T, as the ruling's figures did; that is never
      longer than this series, so the paper's floor is never the looser one. When
      `paper_sr0` refuses, `paper` is None and `paper_refused` gives the reason.
      Nothing stands in for it.

    A declared_n the slates do not allow raises (`minimum_declared_n`), before
    either bar is computed. The series is loaded through `load`, so its bytes
    match the ledger's sha256. Skew and raw kurtosis use the ledger's formulas.
    """
    from scripts.research.inference import desk_dsr, psr, upper_bound_max_z
    _check_declared(counter, declared_n)
    canon = _counters()[counter]["trials"]
    rows = entries(counter, trials=[trial], root=root)
    hit = [r for r in rows if r["variant"] == variant]
    if len(hit) != 1:
        raise ValueError(f"{counter}/{trial}/{variant}: {len(hit)} ledger lines, need exactly one; "
                         f"stored variants are {sorted(r['variant'] for r in rows)}")
    # Only the configuration the trial is judged on gets bars. A best-of-sweep
    # variant stored beside it scored DSR 0.997 against the pre-registered
    # one's 0.729 (quant-reviewer, 2026-10-28).
    pick = _pick(counter, _trial_no(counter, trial), root=root)
    if (pick["trial"], pick["variant"]) != (hit[0]["trial"], hit[0]["variant"]):
        raise ValueError(f"{counter}/{trial}/{variant} is not the series {trial} is judged on "
                         f"({pick['variant']}); bars are computed on that one only")
    x = load(hit[0], root=root).to_numpy(dtype=float)
    T = len(x)
    sr = float(x.mean() / x.std(ddof=1))                # per period
    skew, kurt = float(pd.Series(x).skew()), float(pd.Series(x).kurt() + 3.0)
    desk_sr0 = np.sqrt(1 / T) * upper_bound_max_z(declared_n)
    out = dict(counter=counter, trial=trial, variant=variant, judged=hit[0].get("judged", False),
               T=T, sr=sr, sr_annual=sr * np.sqrt(252), skew=skew, kurt=kurt, canonical_trials=canon,
               desk=dict(n_trials=int(declared_n), T=T, sr0=desk_sr0, sr0_annual=desk_sr0 * np.sqrt(252),
                         dsr=desk_dsr(sr * np.sqrt(252), T, skew, kurt, declared_n)),
               paper=None, paper_refused=None, paper_refused_code=None)
    try:
        p = paper_sr0(counter, declared_n=declared_n, root=root)
    except PaperBarRefused as e:
        out["paper_refused"], out["paper_refused_code"] = str(e), e.code
    else:
        out["paper"] = dict(declared_n=p["declared_n"], trials=p["trials"], n_effective=p["n_effective"],
                            rho_bar=p["rho_bar"], sr_var_used=p["sr_var_used"], floor_binds=p["floor_binds"],
                            T_common=p["T"], sr0=p["sr0"], sr0_annual=p["sr0_annual"],
                            dsr=psr(sr, T, skew, kurt, p["sr0"]))
    return out


def verify(counter: str | None = None, *, root: Path = ROOT) -> dict:
    """Load every stored series in the ledger (or one counter's) and check its
    sha256. The series are gitignored and live only in the checkout that recorded
    them, so a checkout can carry ledger lines whose files are elsewhere. The
    loop checks this before it spends a trial, not after."""
    rows = [r for r in _read_ledger(root) if counter is None or r["counter"] == counter]
    problems = []
    for r in rows:
        try:
            load(r, root=root)
        except (FileNotFoundError, ValueError) as e:
            problems.append(f"{r['counter']}/{r['trial']}/{r['variant']}: {e}")
    return dict(root=str(root), lines=len(rows), ok=not problems, problems=problems)


def main(argv=None) -> int:
    """The registry from the shell; every command prints JSON.

      bars COUNTER TRIAL VARIANT --declared-n N   both bars for one stored series
      sr0 COUNTER --declared-n N                  the paper's safeguarded bar alone
      slate COUNTER [--pending K] [--declared-n N] the least N; exit 1 if N is not allowed
      verify [COUNTER]                            every stored series loads; exit 1 if not

    `--root` reads another checkout's ledger and series: the series are
    gitignored and exist only where they were recorded. Declared slates and the
    counters are always this checkout's."""
    import argparse
    ap = argparse.ArgumentParser(prog="python3 -m scripts.research.registry")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sr0", help="the paper's safeguarded bar for a counter")
    s.add_argument("counter")
    b = sub.add_parser("bars", help="both bars for one stored series")
    b.add_argument("counter")
    b.add_argument("trial")
    b.add_argument("variant")
    for p in (s, b):
        p.add_argument("--declared-n", type=int, required=True)
    sl = sub.add_parser("slate", help="the least N a trial may declare")
    sl.add_argument("counter")
    sl.add_argument("--pending", type=int, default=0)
    sl.add_argument("--declared-n", type=int)
    v = sub.add_parser("verify", help="every stored series loads and matches its sha256")
    v.add_argument("counter", nargs="?")
    for p in (s, b, v):
        p.add_argument("--root", type=Path, default=ROOT)
    a = ap.parse_args(argv)
    code = 0
    if a.cmd == "sr0":
        r = paper_sr0(a.counter, declared_n=a.declared_n, root=a.root)
    elif a.cmd == "bars":
        r = bars(a.counter, trial=a.trial, variant=a.variant, declared_n=a.declared_n, root=a.root)
    elif a.cmd == "slate":
        r = minimum_declared_n(a.counter, pending=a.pending)
        if a.declared_n is not None:
            r["declared_n"] = a.declared_n
            r["ok"] = not r["needs_ruling"] and a.declared_n >= r["minimum"]
            code = 0 if r["ok"] else 1
    else:
        r = verify(a.counter, root=a.root)
        code = 0 if r["ok"] else 1
    print(json.dumps(r, indent=2, default=float))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
