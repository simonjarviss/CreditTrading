"""Rebuild every figure and table of the research evidence pack from committed sources.

    python3 -m scripts.report.build_pack            # refuses an uncommitted input
    python3 -m scripts.report.build_pack --allow-dirty   # development only; the manifest says so

WHY THIS FILE EXISTS (2026-11-03). The team lead asked for a log, kept day by day, that a
research report can later be written from: "graphs, data, the economics, anything such a
report needs". A figure in that report is only as good as its provenance, so this builder
draws nothing it cannot trace. Every output is written with:

  * a footer naming its source file(s), the commit and the data's last date;
  * an entry in `results/report/MANIFEST.json` listing its inputs with sha256, the commit
    and whether the tree was clean, and the build time;
  * gross P&L as the headline, with the 5 / 15 / 30bp grid beside it and labelled, never
    mixed into one column (CLAUDE.md, research rules);
  * fit and holdout separated, the 2023-01-01 line marked, eras shaded where they matter
    (BRIEF H5, H13).

A figure whose data is not yet committed is listed as PENDING in the manifest with exactly
what it needs, and is never drawn from a substitute (CLAUDE.md: never fake it; no silent
fallbacks). The PENDING list is part of the output: it says what the next commit should
carry.

SOURCES. Only committed files and git objects: the trial registry through its API
(`scripts/research/registry.py::entries`, whose ledger is tracked; its series are
gitignored and so are not read), the trial result JSONs and outputs under `results/`, the
sanitised live CSVs `snapshot_live.py` writes under `results/report/data/live/`, the
authored registers under `results/report/data/` (each row cites its evidence file), and
git history itself (release tags, the frozen specs at each commit, the counter table in
`docs/RESEARCH_STATE.md` at each commit). Nothing here computes a return, opens a
holdout or reads `data/`.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from scripts.report.common import (ALPACA_START, HOLDOUT_START, OKABE_ITO as C, REPO,  # noqa: E402
                                   PackError, committed_clean, git, head_commit, sha256_bytes)
from scripts.report import evidence_log as elog  # noqa: E402

PACK_REL = "results/report"
COUNTER_DOC = "docs/RESEARCH_STATE.md"
SPEC_PATHS = ("ops/specs", "ops/_archive", "_archive/ops")


class Pending(Exception):
    """This output cannot be built from committed data yet; the message says what it needs."""


@dataclass
class Build:
    repo: Path
    allow_dirty: bool = False
    commit: str = ""
    inputs: dict = field(default_factory=dict)
    outputs: list = field(default_factory=list)
    pending: list = field(default_factory=list)
    _current: list = field(default_factory=list)

    def __post_init__(self):
        self.commit = head_commit(self.repo)
        self.short = self.commit[:7]
        self.out = self.repo / PACK_REL

    # -- inputs ---------------------------------------------------------------
    def file(self, rel: str, *, needs: str | None = None) -> Path:
        """A committed file in the tree. Missing -> Pending(needs); uncommitted -> PackError
        unless --allow-dirty, and the manifest records `committed: false` either way."""
        p = self.repo / rel
        if not p.exists():
            raise Pending(needs or f"{rel} (not in the tree)")
        clean = committed_clean(rel, self.repo)
        if not clean and not self.allow_dirty:
            raise PackError(f"{rel} is not committed (or differs from HEAD); commit it first, "
                            "or pass --allow-dirty for a development build")
        self.inputs[rel] = {"sha256": sha256_bytes(p.read_bytes()), "committed": clean}
        self._current.append(rel)
        return p

    def blob(self, rev: str, path: str) -> bytes:
        """A git object, `git show rev:path`, recorded as `git:<rev>:<path>`."""
        b = git("show", f"{rev}:{path}", repo=self.repo, text=False)
        key = f"git:{rev}:{path}"
        self.inputs[key] = {"sha256": sha256_bytes(b), "committed": True}
        self._current.append(key)
        return b

    def history(self, key: str, pairs: list) -> None:
        """Record a git-history input (many blobs) as one digest over its (commit, blob) list."""
        self.inputs[key] = {"sha256": sha256_bytes("\n".join(pairs).encode()), "committed": True,
                            "n_objects": len(pairs)}
        self._current.append(key)

    # -- outputs --------------------------------------------------------------
    def footer(self, fig, sources: list[str], last_date: str, note: str = "") -> None:
        dirty = "" if all(self.inputs[s]["committed"] for s in sources if s in self.inputs) \
            else " | UNCOMMITTED INPUT (development build)"
        text = (f"Source: {'; '.join(sources)} | commit {self.short} | data last date {last_date}"
                f"{dirty} | scripts/report/build_pack.py" + (f"\n{note}" if note else ""))
        fig.text(0.005, 0.003, text, fontsize=6.3, color=C["grey"], ha="left", va="bottom", wrap=True)

    def save_fig(self, fig, fid: str, title: str, sources: list[str], last_date: str, note: str = ""):
        self.footer(fig, sources, last_date, note)
        h = fig.get_figheight()     # footer room in inches, so tall and short figures both fit
        fig.subplots_adjust(bottom=max(fig.subplotpars.bottom, 0.95 / h), top=min(fig.subplotpars.top, 1 - 0.55 / h))
        path = self.out / "figures" / f"{fid}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=200, metadata={"Software": None})
        plt.close(fig)
        self._record(path, "figure", fid, title, sources, last_date)

    def save_table(self, df: pd.DataFrame, tid: str, title: str, sources: list[str], last_date: str):
        path = self.out / "tables" / f"{tid}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False, lineterminator="\n")
        self._record(path, "table", tid, title, sources, last_date)

    def _record(self, path, kind, oid, title, sources, last_date):
        self.outputs.append({"id": oid, "kind": kind, "title": title,
                             "path": path.relative_to(self.repo).as_posix(),
                             "sha256": sha256_bytes(path.read_bytes()), "inputs": list(sources),
                             "data_last_date": last_date})


# ----------------------------------------------------------------- styling -----
def _style():
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "legend.frameon": False, "figure.dpi": 100})


def _holdout_line(ax, label=True):
    x = pd.Timestamp(HOLDOUT_START)
    ax.axvline(x, color=C["black"], lw=0.8, ls="--")
    if label:
        ax.text(x, ax.get_ylim()[1], " 2023-01-01 holdout", fontsize=7, va="top")


def _era_shade(ax, start, end):
    """Shade the HISTORY era (before the 2026-09-28 clean slate) grey."""
    a = pd.Timestamp(ALPACA_START)
    if pd.Timestamp(start) < a:
        ax.axvspan(pd.Timestamp(start), min(a, pd.Timestamp(end)), color=C["grey"], alpha=0.12, lw=0)
        ax.text(pd.Timestamp(start), ax.get_ylim()[1], " HISTORY (IBKR era, tag pre-clean-slate)",
                fontsize=7, va="top", color=C["grey"])
    ax.text(a, ax.get_ylim()[1], " ALPACA", fontsize=7, va="top")


# ------------------------------------------------------------- git helpers -----
def release_tags(b: Build) -> pd.DataFrame:
    out = git("for-each-ref", "refs/tags/release-*", "--sort=creatordate",
              "--format=%(refname:short)\t%(creatordate:iso-strict)\t%(subject)", repo=b.repo)
    rows = []
    for ln in out.splitlines():
        tag, when, subj = (ln.split("\t") + ["", ""])[:3]
        commit = git("rev-list", "-n1", tag, repo=b.repo).strip()
        rows.append({"tag": tag, "tagged": when, "commit": commit[:7], "subject": subj})
    if not rows:
        raise Pending("release-* tags (git fetch --tags)")
    b.history("git:refs/tags/release-*", [f"{r['tag']} {r['commit']}" for r in rows])
    return pd.DataFrame(rows)


def _spec_at(b: Build, rev: str, path: str):
    try:
        return json.loads(git("show", f"{rev}:{path}", repo=b.repo))
    except (PackError, json.JSONDecodeError):
        return None


def _flatten(d: dict, prefix: str = ""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from _flatten(v, f"{prefix}{k}.")
        else:
            yield prefix, k, v, d


# ================================================================ tables ========
def t_releases(b: Build) -> pd.DataFrame:
    """Every release tag, and which core / C4 spec and multiplier it carried (read at the tag)."""
    rel = release_tags(b)
    rows = []
    for r in rel.itertuples():
        core = _spec_at(b, r.tag, "ops/specs/cef_discount.frozen.json") or {}
        c4 = _spec_at(b, r.tag, "ops/specs/c4_families.frozen.json") or {}
        rows.append({"tag": r.tag, "tagged": r.tagged[:10], "commit": r.commit,
                     "core_spec": core.get("spec_id", ""),
                     "core_sizing_multiplier": (core.get("frozen") or {}).get("sizing_multiplier", ""),
                     "c4_spec": c4.get("spec_id", ""),
                     "c4_sizing_multiplier": (c4.get("frozen") or {}).get("sizing_multiplier", ""),
                     "subject": r.subject})
    df = pd.DataFrame(rows)
    b.save_table(df, "T01_releases", "Release tags and the specs each carried",
                 ["git:refs/tags/release-*"], df["tagged"].max())
    return df


def t_spec_lineage(b: Build) -> pd.DataFrame:
    """Every frozen-spec id that ever existed on HEAD's history, where and when it first appears,
    and the first release tag that carried it."""
    log = git("log", "--format=@@%H %cI", "--name-only", "HEAD", "--", *SPEC_PATHS, repo=b.repo)
    seen, pairs = {}, []
    for chunk in log.split("@@")[1:]:
        lines = [x for x in chunk.splitlines() if x.strip()]
        h, when = lines[0].split()
        for path in lines[1:]:
            if not path.endswith(".frozen.json"):
                continue
            spec = _spec_at(b, h, path)
            if not spec or "spec_id" not in spec:
                continue
            sid = spec["spec_id"]
            pairs.append(f"{h[:12]} {path} {sid}")
            # git log runs newest first, so the last write wins = the earliest commit.
            seen[sid] = {"spec_id": sid, "family": sid.split(".")[0], "first_commit": h[:7],
                         "first_commit_date": when[:10], "first_path": path,
                         "supersedes": spec.get("_supersedes", "")}
    if not seen:
        raise Pending("frozen specs in git history")
    b.history("git:HEAD:ops/specs history", pairs)
    rel = release_tags(b)
    first_rel = {}
    for r in rel.itertuples():
        for fam in ("cef_discount", "c4_families", "bench_b6_ew_credit"):
            s = _spec_at(b, r.tag, f"ops/specs/{fam}.frozen.json")
            if s and s.get("spec_id") and s["spec_id"] not in first_rel:
                first_rel[s["spec_id"]] = (r.tag, r.tagged[:10])
    tags = git("for-each-ref", "refs/tags/spec-*", "--format=%(refname:short)", repo=b.repo).split()
    for sid, row in seen.items():
        m = re.search(r"\.v(\d+)\.(\d{8})$", sid) or re.search(r"\.(\d{8})$", sid)
        row["version"] = f"v{m.group(1)}" if m and m.lastindex == 2 else ""
        d8 = m.group(m.lastindex) if m else ""
        row["id_date"] = f"{d8[:4]}-{d8[4:6]}-{d8[6:]}" if d8 else ""
        row["first_release"], row["first_release_date"] = first_rel.get(sid, ("", ""))
        row["revert_tag"] = f"spec-{sid}" if f"spec-{sid}" in tags else ""
    df = pd.DataFrame(seen.values()).sort_values(["family", "id_date", "first_commit_date"])
    b.save_table(df, "T02_spec_lineage", "Frozen-spec lineage", ["git:HEAD:ops/specs history",
                 "git:refs/tags/release-*"], df["first_commit_date"].max())
    return df


def t_deployed_keys(b: Build, rel: pd.DataFrame) -> pd.DataFrame:
    """Every key of the core and C4 specs at the newest release tag, with its sibling note."""
    tag = rel["tag"].iloc[-1]
    rows = []
    for fam in ("cef_discount", "c4_families"):
        path = f"ops/specs/{fam}.frozen.json"
        spec = json.loads(b.blob(tag, path))
        for prefix, k, v, parent in _flatten(spec):
            if k.startswith("_"):
                continue
            note = parent.get(f"_{k}_note") or parent.get(f"_{k.removesuffix('_usd')}_note") or ""
            rows.append({"release": tag, "spec": spec.get("spec_id"), "key": prefix + k,
                         "value": json.dumps(v) if not isinstance(v, str) else v, "note": note})
    df = pd.DataFrame(rows)
    b.save_table(df, "T03_deployed_spec_keys", f"Every frozen-spec key at {tag}",
                 [f"git:{tag}:ops/specs/cef_discount.frozen.json",
                  f"git:{tag}:ops/specs/c4_families.frozen.json"], rel["tagged"].iloc[-1][:10])
    return df


def counter_history(b: Build) -> pd.DataFrame:
    # --first-parent: main's own line. Walking every merged commit interleaves side branches'
    # counts by date and draws counters that move backwards (seen 2026-11-03).
    log = git("log", "--first-parent", "--follow", "--format=@@%H %cI", "--name-only", "HEAD", "--", COUNTER_DOC,
              repo=b.repo)
    rx = re.compile(r"^\|\s*\**([A-Z][A-Z0-9_]+)\**\s*\|[^|\n]*\|\s*\**(\d+)\**\s*\|", re.M)
    rows, pairs = [], []
    for chunk in log.split("@@")[1:]:
        lines = [x for x in chunk.splitlines() if x.strip()]
        h, when = lines[0].split()
        path = lines[1] if len(lines) > 1 else COUNTER_DOC
        text = git("show", f"{h}:{path}", repo=b.repo)
        pairs.append(f"{h[:12]} {path}")
        for name, n in rx.findall(text):
            rows.append({"commit": h[:7], "committed": when, "date": when[:10], "counter": name,
                         "trials": int(n)})
    if not rows:
        raise Pending(f"a parsable counter table in {COUNTER_DOC}'s history")
    b.history(f"git:HEAD:{COUNTER_DOC} history", pairs)
    df = pd.DataFrame(rows).sort_values(["committed", "counter"])
    # one row per counter per change (drop commits that did not move it)
    df = df[df.groupby("counter")["trials"].diff().fillna(1) != 0].copy()
    df["dsr_bar"] = df["trials"].map(lambda n: round(math.sqrt(2 * math.log(n)), 3) if n > 1 else None)
    b.save_table(df, "T04_counter_history", "Trial counters as recorded at each commit",
                 [f"git:HEAD:{COUNTER_DOC} history"], df["date"].max())
    return df


def t_registry(b: Build) -> pd.DataFrame:
    """The trial registry's tracked ledger, read through its API (series are gitignored)."""
    from scripts.research import registry
    b.file("results/research/trials/ledger.jsonl")
    rows = []
    for counter in ("CEF", "EVENTS", "XASSET", "GAMMA", "MACRO"):
        for e in registry.entries(counter):
            rows.append({k: e.get(k) for k in ("counter", "trial", "variant", "first", "last", "n",
                                                "judged", "commit", "dirty")} |
                        {"sharpe": e.get("sharpe"), "note": (e.get("note") or "")[:160]})
    if not rows:
        raise Pending("entries in results/research/trials/ledger.jsonl")
    df = pd.DataFrame(rows)
    b.save_table(df, "T05_trial_registry", "Stored trial series (registry ledger)",
                 ["results/research/trials/ledger.jsonl"], str(df["last"].max()))
    return df


def t_evidence_index(b: Build) -> pd.DataFrame:
    p = b.file(f"{PACK_REL}/EVIDENCE_LOG.md")
    entries = elog.parse(p.read_text())
    errs = elog.validate(entries)
    if errs:
        raise PackError("EVIDENCE_LOG.md is invalid:\n  " + "\n  ".join(errs[:20]))
    rows = [{"id": e.id, "date": e.date, "kind": e.fields["kind"], "era": e.fields["era"],
             "supports": e.fields["supports"], "n_figures": len(e.figures),
             "tags": "".join(sorted({m.group(1) for f in e.figures if (m := elog.TAG.search(f))})),
             "claim": e.claim} for e in entries]
    df = pd.DataFrame(rows).sort_values(["date", "id"])
    b.save_table(df, "T06_evidence_index", "Evidence-log index", [f"{PACK_REL}/EVIDENCE_LOG.md"],
                 df["date"].max())
    return df


# =============================================================== figures =======
def f_deployments(b: Build, rel: pd.DataFrame):
    p = b.file(f"{PACK_REL}/data/deployments.csv", needs=f"{PACK_REL}/data/deployments.csv")
    df = pd.read_csv(p, dtype=str).fillna("")
    asof = git("log", "-1", "--format=%cI", repo=b.repo).strip()[:10]
    undated = df[df["start"] == ""]["id"].tolist()   # listed in the register, never given a made-up start
    df = df[df["start"] != ""].copy()
    df["s"] = pd.to_datetime(df["start"])
    df["e"] = pd.to_datetime(df["end"].where(df["end"] != "", asof))
    df = df.sort_values(["s", "book"]).reset_index(drop=True)
    colour = {"live": C["green"], "armed": C["green"], "retired": C["grey"], "off": C["sky"],
              "shadow": C["purple"], "pending": C["orange"], "building": C["yellow"]}
    fig, ax = plt.subplots(figsize=(11.5, 0.32 * len(df) + 2.2))
    for i, r in df.iterrows():
        col = colour.get(r["status"], C["black"])
        ax.barh(i, max((r["e"] - r["s"]).days, 1), left=r["s"], color=col, height=0.6,
                hatch="//" if r["status"] in ("off", "shadow", "pending", "building") else None,
                edgecolor=C["black"], lw=0.3)
    labels = [f"{r['id']} {r['sleeve'] or r['book']} [{r['venue']}]" for _, r in df.iterrows()]
    ax.set_yticks(range(len(df)), [x if len(x) <= 58 else x[:55] + "..." for x in labels], fontsize=6.8)
    fig.subplots_adjust(left=0.36, right=0.98)
    ax.invert_yaxis()
    for t in rel.itertuples():
        x = pd.Timestamp(t.tagged[:10])
        if x >= df["s"].min():
            ax.axvline(x, color=C["vermillion"], lw=0.4, alpha=0.6)
    ax.axvline(pd.Timestamp(ALPACA_START), color=C["black"], lw=0.9)
    ax.text(pd.Timestamp(ALPACA_START), -0.9, " Alpaca (clean slate 2026-09-28)", fontsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.set_xlabel("date (thin red lines: release-* tags)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, label=s) for s, c in colour.items()
               if s in set(df["status"])]
    ax.legend(handles=handles, loc="lower left", fontsize=7, ncol=4)
    ax.set_title(f"What was live when: every book and sleeve, by status (as of {asof})")
    b.save_fig(fig, "F01_deployment_timeline", "Deployment timeline",
               [f"{PACK_REL}/data/deployments.csv", "git:refs/tags/release-*"], asof,
               "Rows are an authored register; each row cites its evidence file and commit in the CSV."
               + (f" Not drawn (no recorded start date): {', '.join(undated)}." if undated else ""))


def f_spec_lineage(b: Build, lin: pd.DataFrame):
    """One row per spec family, one marker per version at the freeze date in its id. The first
    release tag that carried each version is in T02_spec_lineage.csv, not on the plot."""
    df = lin[lin["id_date"] != ""].copy()
    df["d"] = pd.to_datetime(df["id_date"])
    order = df.groupby("family")["d"].min().sort_values().index.tolist()
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(order) + 1.8))
    cols = [C["blue"], C["orange"], C["green"], C["purple"], C["vermillion"], C["sky"]]
    for i, fam in enumerate(order):
        g = df[df["family"] == fam].sort_values("d")
        col = cols[i % len(cols)]
        ax.plot(g["d"], [i] * len(g), "-o", color=col, ms=5, lw=1)
        for k, r in enumerate(g.itertuples()):
            ax.annotate(r.version or "", (r.d, i), textcoords="offset points",
                        xytext=(0, 6 if k % 2 == 0 else -11), ha="center", fontsize=7, color=col)
    ax.set_yticks(range(len(order)), order, fontsize=7.5)
    ax.set_ylim(-0.7, len(order) - 0.3)
    ax.invert_yaxis()
    ax.axvline(pd.Timestamp(ALPACA_START), color=C["black"], lw=0.8, ls="--")
    ax.text(pd.Timestamp(ALPACA_START), -0.6, " clean slate / Alpaca", fontsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.set_xlabel("freeze date in the spec id (its YYYYMMDD suffix)")
    ax.set_title("Frozen-spec lineage: every version of each book's spec (first release per version: T02)")
    b.save_fig(fig, "F02_spec_lineage", "Spec lineage", ["git:HEAD:ops/specs history",
               "git:refs/tags/release-*"], df["id_date"].max())


def f_trial53(b: Build, rel: pd.DataFrame):
    a = "results/cef/prereg_voltarget/risk_2026-10-30.json"
    f = "results/cef/prereg_voltarget/risk_2026-11-02_flatten.json"
    hold, flat = json.loads(b.file(a).read_text()), json.loads(b.file(f).read_text())
    spec_core = json.loads(b.blob(rel["tag"].iloc[-1], "ops/specs/cef_discount.frozen.json"))
    spec_c4 = json.loads(b.blob(rel["tag"].iloc[-1], "ops/specs/c4_families.frozen.json"))
    chosen = {"core": spec_core["frozen"].get("sizing_multiplier"),
              "c4": spec_c4["frozen"].get("sizing_multiplier")}
    rows = []
    for book, src, d in (("HOLD harness book (2026-10-30)", a, hold),
                         ("FLATTEN book, calendar sessions (2026-11-02)", f, flat)):
        for block, v in d.items():
            for acct, mk in (("core", "m_core"), ("c4", "m_c4")):
                z = v.get(f"W1_{acct}_zero", {})
                ft = v.get(f"W1_{acct}_fit", {})
                rows.append({"book": book, "block": block, "account": acct, "m": v[mk],
                             "p_halve_zero_edge": z.get("halve"), "p_kill_zero_edge": z.get("kill"),
                             "p_halve_fit_edge": ft.get("halve"), "p_kill_fit_edge": ft.get("kill"),
                             "source": src})
    df = pd.DataFrame(rows).drop_duplicates(["book", "account", "m"]).sort_values(["account", "book", "m"])
    b.save_table(df, "T07_trial53_odds", "Trial 53: P(HALVE)/P(KILL) by multiplier", [a, f], "2022-12-30")
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, acct in zip(axes, ("core", "c4")):
        g = df[df["account"] == acct]
        for (book, gg), col in zip(g.groupby("book"), (C["blue"], C["orange"])):
            gg = gg.sort_values("m")
            ax.plot(gg["m"], 100 * gg["p_halve_zero_edge"], "-o", color=col, ms=4, label=f"P(HALVE) {book}")
            ax.plot(gg["m"], 100 * gg["p_kill_zero_edge"], "--s", color=col, ms=3, label=f"P(KILL) {book}")
        if chosen[acct]:
            ax.axvline(chosen[acct], color=C["green"], lw=1)
            ax.text(chosen[acct], ax.get_ylim()[1] * 0.97, f" deployed ×{chosen[acct]} (newest release)",
                    fontsize=7, color=C["green"], va="top")
        ax.set_title(f"{acct} account")
        ax.set_xlabel("sizing multiplier (×)")
    axes[0].set_ylabel("probability within 252 sessions, zero edge (%)")
    axes[1].legend(fontsize=6.3, loc="center right")
    fig.suptitle("Trial 53: P(HALVE) and P(KILL) by sizing multiplier, zero edge, W1 2013-06-25..2022-12-30 "
                 "(fit only)", fontsize=9)
    b.save_fig(fig, "F03_trial53_halve_kill", "Trial 53 HALVE/KILL odds", [a, f,
               f"git:{rel['tag'].iloc[-1]}:ops/specs/cef_discount.frozen.json"], "2022-12-30",
               "Odds as committed: worst of SB21/SB63/GAUSS, worse of total and price return "
               "(risk_output_*.txt). The 2026-11-02 rows count flat sessions; the 'while trading' odds are in "
               "flatten_remeasure_*.json.")


def f_gate0(b: Build):
    src = "results/cef/screens_2026-11-02/gate0_analysis.json"
    d = json.loads(b.file(src).read_text())
    rows = []
    for spec, v in d.items():
        for s, lab in (("A", "A survivors"), ("D", "D dead candidates"), ("B", "B = A and D together")):
            bb, t = v[f"b{s}"], v[f"t{s}"]
            se = abs(bb / t)
            rows.append({"spec": spec, "sample": lab, "slope_bp_per_pp": bb, "t": t,
                         "ci_lo": bb - 1.96 * se, "ci_hi": bb + 1.96 * se,
                         "ratio_D": v["ratio_D"], "ci_ratio_D_fund_half_year": v["ci_ratio_D_fhy"],
                         "ci_ratio_D_calendar_half_year": v["ci_ratio_D_half"], "ratio_B": v["ratio_B"],
                         "ci_ratio_B_fund_half_year": v["ci_ratio_B_fhy"]})
    df = pd.DataFrame(rows)
    b.save_table(df, "T08_trial54_gate0", "Trial 54 Gate 0 slopes", [src], "2022-12-30")
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), gridspec_kw={"width_ratios": [3, 2]})
    specs = list(d)
    cols = {"A survivors": C["blue"], "D dead candidates": C["vermillion"], "B = A and D together": C["green"]}
    for j, spec in enumerate(specs):
        g = df[df["spec"] == spec]
        for k, r in enumerate(g.itertuples()):
            y = j + (k - 1) * 0.22
            axes[0].errorbar(r.slope_bp_per_pp, y, xerr=[[r.slope_bp_per_pp - r.ci_lo], [r.ci_hi - r.slope_bp_per_pp]],
                             fmt="o", color=cols[r.sample], ms=4, capsize=2, label=r.sample if j == 0 else None)
        v = d[spec]
        lo, hi = v["ci_ratio_D_fhy"]
        axes[1].errorbar(v["ratio_D"], j, xerr=[[v["ratio_D"] - lo], [hi - v["ratio_D"]]], fmt="o",
                         color=C["vermillion"], ms=4, capsize=2)
    axes[0].axvline(0, color=C["black"], lw=0.6)
    axes[0].set_yticks(range(len(specs)), [s.replace("; cells", "\ncells") for s in specs], fontsize=6.5)
    axes[0].set_xlabel("slope of next return on discount level (bp per pp), 95% CI = ±1.96·|b/t|")
    axes[0].legend(fontsize=7, loc="lower left")
    axes[1].axvline(1, color=C["black"], lw=0.6, ls="--")
    axes[1].set_yticks(range(len(specs)), [""] * len(specs))
    axes[1].set_xlabel("b_D / b_A, 95% CI (fund-half-year bootstrap)")
    fig.suptitle("Trial 54 Gate 0 (survivorship, fit only to 2022-12-30): dead funds show the level effect "
                 "at least as strongly. Judged POST-DATA by the team lead; not a pre-registered pass.",
                 fontsize=8.5)
    b.save_fig(fig, "F04_trial54_gate0", "Trial 54 Gate 0", [src], "2022-12-30",
               "t: half-year-clustered (gate0_analysis.py). NAV coverage of dead candidates 64.2% "
               "(gate0_analysis_output.txt).")


def f_c4(b: Build):
    fit_p = "results/cef/c4/c4_fit_verdict_2026-10-14.json"
    ho_p = "results/cef/c4/c4_holdout_verdict_2026-10-18.json"
    cor_p = "results/cef/c4/holdout_review_2026-10-18/checks2_output.txt"
    fit, ho = json.loads(b.file(fit_p).read_text()), json.loads(b.file(ho_p).read_text())
    m = re.search(r"IGR-corrected: 08-20 at \$0\.06 -> SR ([\d.]+) net5 ([-\d.]+) net15 ([-\d.]+) "
                  r"net30 ([-\d.]+)", b.file(cor_p).read_text())
    if not m:
        raise PackError(f"{cor_p}: the corrected-book line is not where the builder expects it")
    rows = [{"book": "fit 2005-02-22..2022-12-30", "gross": fit["cost_grid"]["gross"],
             "net5": fit["cost_grid"]["net5"], "net15": fit["cost_grid"]["net15"],
             "net30": fit["cost_grid"]["net30"], "status": "fit", "source": fit_p},
            {"book": "holdout 2023-01-01..2026-09-30, as first committed", "gross": ho["headline"]["sr"],
             "net5": ho["headline"]["net5"], "net15": ho["headline"]["net15"],
             "net30": ho["headline"]["net30"], "status": "superseded by the ruling of 2026-10-19", "source": ho_p},
            {"book": "holdout, corrected book (four IGR bars) = the verdict", "gross": float(m.group(1)),
             "net5": float(m.group(2)), "net15": float(m.group(3)), "net30": float(m.group(4)),
             "status": "the record (team lead, 2026-10-19)", "source": cor_p}]
    df = pd.DataFrame(rows)
    b.save_table(df, "T09_c4_trial52", "C4 (CEF trial 52): fit vs holdout, gross and cost grid",
                 [fit_p, ho_p, cor_p], "2026-09-30")
    fig, ax = plt.subplots(figsize=(9, 3.8))
    w = 0.18
    for i, r in df.iterrows():
        x = i * 1.2
        ax.bar(x - 1.5 * w, r["gross"], w, color=C["blue"], label="GROSS (headline)" if i == 0 else None)
        for k, (c, col) in enumerate((("net5", C["sky"]), ("net15", C["orange"]), ("net30", C["vermillion"]))):
            ax.bar(x + (k - 0.5) * w + 0.06, r[c], w, color=col, hatch="..",
                   label=f"net @ {c[3:]}bp (real-money view)" if i == 0 else None)
    ax.axvline(0.6, color=C["black"], lw=0.8, ls="--")
    ax.text(0.62, -1.0, " 2023-01-01: fit | holdout\n (opened once, 2026-10-18)", fontsize=7)
    ax.axhline(0, color=C["black"], lw=0.6)
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + 0.45 * (hi - lo))
    ax.set_xticks([i * 1.2 for i in range(len(df))], [r.replace(", ", ",\n") for r in df["book"]], fontsize=7)
    ax.set_ylabel("annualised Sharpe ratio")
    ax.legend(fontsize=7, ncol=4, loc="upper center")
    ax.set_title("C4 (CEF trial 52): gross Sharpe with the 5/15/30bp grid beside it; the net sign flips by 30bp")
    b.save_fig(fig, "F05_c4_trial52", "C4 fit vs holdout", [fit_p, ho_p, cor_p], "2026-09-30",
               "Borrow charged at zero (modelled), labelled; paper only by ruling. Corrected book: "
               "C4_RESULT_2026-10-14.md §9.")


def _live(b: Build, book: str, name: str, needs: str) -> pd.DataFrame:
    return pd.read_csv(b.file(f"{PACK_REL}/data/live/{book}/{name}", needs=needs), dtype=str)


def f_live_equity(b: Build, rel: pd.DataFrame, book="cef", fid="F06_live_equity", title="Live equity"):
    """One account's equity: the 17:30 snapshot and, where the pull carried it, the EOD record.
    Each book is its own figure (`fid`; C4's is F06_live_equity_c4, 2026-11-05): the two
    accounts hold different books, so one axis would invite a sum nobody measured."""
    eq = _live(b, book, "equity_snapshot.csv", f"{PACK_REL}/data/live/{book}/equity_snapshot.csv "
               "(run scripts/report/snapshot_live.py on a vmpnl.sh pull)")
    srcs = [f"{PACK_REL}/data/live/{book}/equity_snapshot.csv"]
    eq["d"], eq["equity"] = pd.to_datetime(eq["date"]), eq["equity"].astype(float)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(eq["d"], eq["equity"], "-o", ms=3, color=C["orange"], label="17:30 ET snapshot (labelled, not the record)")
    note = ""
    eod_p = REPO / PACK_REL / "data" / "live" / book / "eod_equity.csv"
    if (b.repo / PACK_REL / "data" / "live" / book / "eod_equity.csv").exists():
        eod = _live(b, book, "eod_equity.csv", "")
        srcs.append(f"{PACK_REL}/data/live/{book}/eod_equity.csv")
        ax.plot(pd.to_datetime(eod["date"]), eod["equity"].astype(float), "-", color=C["blue"], lw=1.6,
                label="Alpaca EOD portfolio history (the P&L of record)")
    else:
        note = (f"PENDING: the official EOD line needs {PACK_REL}/data/live/{book}/eod_equity.csv from a "
                "vmpnl.sh pull made after its grep gained eod_equity (2026-11-03). Not drawn from the snapshot.")
        b.pending.append({"id": f"{fid}.eod", "title": "official EOD equity line",
                          "needs": note})
    for t in rel.itertuples():
        x = pd.Timestamp(t.tagged[:10])
        if eq["d"].min() <= x <= eq["d"].max() + pd.Timedelta(days=1):
            ax.axvline(x, color=C["vermillion"], lw=0.5, alpha=0.7)
            ax.text(x, ax.get_ylim()[0], t.tag.replace("release-", ""), rotation=90, fontsize=5.5,
                    va="bottom", color=C["vermillion"])
    ax.set_ylabel("account equity (USD)")
    # Plain dollars: an account that barely moved (C4 before its first send) would otherwise get
    # matplotlib's "+1e5" offset, and the ticks would read as P&L rather than equity.
    ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.set_xlabel("session date (2026); red lines: release tags")
    ax.legend(fontsize=7, loc="upper right")
    ax.set_title(f"{book} paper account equity, gross (Alpaca paper charges no borrow and credits no distributions)")
    b.save_fig(fig, fid, title, srcs + ["git:refs/tags/release-*"], eq["date"].max(), note)


def f_live_daily(b: Build, book="cef"):
    sc = _live(b, book, "scores.csv", f"{PACK_REL}/data/live/{book}/scores.csv")
    # Named when absent, never defaulted: a book whose pulls carry no distribution_scores.csv
    # (C4's first week, snapshot_live 2026-11-05) has no such file, and this figure is PENDING.
    ds = _live(b, book, "distribution_scores.csv", f"{PACK_REL}/data/live/{book}/distribution_scores.csv "
               "(snapshot_live writes it only from a pull that carries distribution_scores.csv)")
    sh = _live(b, book, "verify_shadow.csv", f"{PACK_REL}/data/live/{book}/verify_shadow.csv (snapshot_live.py)")
    df = sc[["date", "alpaca_equity_change_usd", "auction_pnl_usd"]].merge(
        ds[["date", "auction_pnl_with_distributions_usd"]], on="date", how="left").merge(
        sh[["date", "shadow_modelled_usd"]], on="date", how="left")
    num = lambda s: pd.to_numeric(s, errors="coerce")   # noqa: E731  UNMEASURED/blank -> NaN, shown as a gap
    for c in df.columns[1:]:
        df[c] = num(df[c])
    df["d"] = pd.to_datetime(df["date"])
    b.save_table(df.drop(columns="d"), "T10_live_daily", "Live daily P&L, four labelled lines",
                 [f"{PACK_REL}/data/live/{book}/{n}" for n in ("scores.csv", "distribution_scores.csv",
                                                               "verify_shadow.csv")], df["date"].max())
    fig, ax = plt.subplots(figsize=(9, 3.8))
    for c, lab, col, st in (("alpaca_equity_change_usd", "17:30 snapshot (Alpaca, not the record)", C["orange"], "-o"),
                            ("auction_pnl_usd", "auction-marked (official closing print)", C["blue"], "-s"),
                            ("auction_pnl_with_distributions_usd", "distribution-adjusted (credits what paper does not)",
                             C["green"], "-^"),
                            ("shadow_modelled_usd", "shadow book (MODELLED, not evidence)", C["grey"], ":")):
        ax.plot(df["d"], df[c].cumsum(skipna=False) if False else df[c].fillna(0).cumsum(), st, ms=3,
                color=col, label=lab, lw=1)
    ax.axhline(0, color=C["black"], lw=0.5)
    ax.set_ylabel("cumulative P&L since 2026-09-28 (USD, gross)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.set_xlabel("session date (2026)")
    ax.legend(fontsize=7)
    ax.set_title(f"{book} paper book: the P&L lines kept beside each other, never blended")
    b.save_fig(fig, "F07_live_pnl_lines", "Live P&L lines",
               [f"{PACK_REL}/data/live/{book}/{n}" for n in ("scores.csv", "distribution_scores.csv",
                                                             "verify_shadow.csv")], df["date"].max(),
               "UNMEASURED days add 0 to a cumulative line and are listed in T10_live_daily.csv as blanks.")


def _md_table(text: str, heading: str) -> pd.DataFrame:
    """The first markdown table after `## heading`, as strings."""
    sec = text.split(f"## {heading}", 1)
    if len(sec) < 2:
        raise PackError(f"no section '## {heading}'")
    lines = [ln for ln in sec[1].splitlines() if ln.startswith("|")]
    rows = []
    for ln in lines:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(cells)
        if len(rows) > 1 and not ln:
            break
    head, *body = rows
    # stop at the first gap: the table ends where a non-table line appears
    out, started = [], False
    for ln in sec[1].splitlines():
        if ln.startswith("|"):
            started = True
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if set("".join(cells)) <= set("-: ") or cells == head:
                continue
            out.append(cells)
        elif started:
            break
    return pd.DataFrame(out, columns=[h or "item" for h in head])


def _usd(s: str) -> float:
    m = re.search(r"([−+-]?[\d,]+\.\d+)", s)
    if not m:
        raise PackError(f"no USD figure in {s!r}")
    return float(m.group(1).replace("−", "-").replace(",", ""))


def f_attribution(b: Build):
    src = "results/cef/LIVE_ATTRIBUTION_2026-11-02.md"
    text = b.file(src).read_text()
    comp = _md_table(text, "Components")
    want = [("hold (q_prev × close change)", "hold"), ("of which NAV part", "NAV part"),
            ("of which discount part", "discount part"), ("fill (fills against", "fill"),
            ("regulatory fees", "SEC + CAT fees"), ("distributions paper did not book", "distributions not booked")]
    rows = []
    for key, lab in want:
        hit = comp[comp.iloc[:, 0].str.startswith(key)]
        if hit.empty:
            raise PackError(f"{src}: component {key!r} not found")
        rows.append({"component": lab, "usd": _usd(hit.iloc[0, 1])})
    df = pd.DataFrame(rows)
    b.save_table(df, "T11_live_attribution", "Live attribution 2026-09-29..10-30", [src], "2026-10-30")
    fig, ax = plt.subplots(figsize=(8, 3.6))
    cols = [C["grey"], C["vermillion"], C["green"], C["orange"], C["purple"], C["sky"]]
    ax.barh(range(len(df)), df["usd"], color=cols)
    ax.set_yticks(range(len(df)), df["component"])
    ax.invert_yaxis()
    ax.axvline(0, color=C["black"], lw=0.6)
    for i, v in enumerate(df["usd"]):
        ax.text(v, i, f" {v:+,.2f}", va="center", ha="left" if v >= 0 else "right", fontsize=7)
    ax.set_xlabel("USD, cef paper account, 2026-09-29..2026-10-30")
    ax.set_title("Live attribution: the NAV move cost the book; the discount part (the strategy's bet) earned")
    b.save_fig(fig, "F08_live_attribution", "Live attribution", [src], "2026-10-30",
               "Rebuilt from Alpaca FILL activities; reconciles to the official EOD change −982.14 USD "
               "to the cent (the note's Reconciliation table). Hold = NAV part + discount part.")


def f_tca(b: Build, rel: pd.DataFrame, book="cef"):
    """Daily fill-cost summaries, from the TRACKED aggregates only. The per-fill rows are in
    the gitignored cache (team lead, 2026-11-03: "Aggregates in repo, rows private"), and a
    figure that shows individual fills is not committed, so this one draws daily statistics."""
    day_p = f"{PACK_REL}/data/live/{book}/fill_cost_daily.csv"
    pool_p = f"{PACK_REL}/data/live/{book}/fill_cost_pooled.csv"
    d = pd.read_csv(b.file(day_p, needs=f"{day_p} (snapshot_live.py)"))
    pool = pd.read_csv(b.file(pool_p, needs=f"{pool_p} (snapshot_live.py)")).set_index("group")
    d["d"] = pd.to_datetime(d["date"])
    risk_p = "results/cef/prereg_voltarget/risk_2026-11-02_flatten.json"
    risk = json.loads(b.file(risk_p).read_text())
    m_live = json.loads(b.blob(rel["tag"].iloc[-1], "ops/specs/cef_discount.frozen.json"))["frozen"].get(
        "sizing_multiplier")
    block = next((k for k, v in risk.items() if v.get("m_core") == m_live), None)
    be = risk[block]["core_breakeven_bp"] if block else None
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.vlines(d["d"], d["p10_bp"], d["p90_bp"], color=C["sky"], lw=3, alpha=0.8, label="p10 to p90 of the day's fills")
    ax.plot(d["d"], d["wmean_bp"], "o", color=C["blue"], ms=5, label="notional-weighted mean, by session")
    ax.plot(d["d"], d["median_bp"], "_", color=C["black"], ms=10, mew=1.5, label="median, by session")
    w = pool.loc["all"]
    ax.axhline(w["wmean_bp"], color=C["blue"], lw=1,
               label=f"pooled weighted mean {w['wmean_bp']:+.1f}bp (n {int(w['n_fills'])} name-side-days, "
                     f"{int(w['n_days'])} sessions)")
    for c, col in ((5, C["sky"]), (15, C["orange"]), (30, C["vermillion"])):
        ax.axhline(c, color=col, lw=1, ls="--", label=f"cost grid {c}bp")
    if be is not None:
        ax.axhline(be, color=C["green"], lw=1.4, ls="-.", label=f"model breakeven {be:.1f}bp at ×{m_live} (fit W1)")
    ax.axhline(0, color=C["black"], lw=0.5)
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + 0.55 * (hi - lo))      # headroom for the legend, above the data
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.set_xlabel("session date (2026)")
    ax.set_ylabel("fill vs official close, bp (+ = worse)")
    ax.legend(fontsize=6.3, ncol=2, loc="upper left")
    ax.set_title(f"{book} paper fill cost by session (late_market day orders, 8 to 2 min before the close)")
    b.save_fig(fig, "F09_tca", "Fill cost by session", [day_p, pool_p, risk_p,
               f"git:{rel['tag'].iloc[-1]}:ops/specs/cef_discount.frozen.json"], d["date"].max(),
               "A unit is one name, side and session (the VWAP of its fills). Paper does not run the closing "
               "auction (CLAUDE.md landmine 1): this is paper's quote fill, not a live MOC cost. Rows stay private.")


def f_verify(b: Build, book="cef"):
    v = _live(b, book, "verify.csv", f"{PACK_REL}/data/live/{book}/verify.csv")
    v["d"] = pd.to_datetime(v["date"])
    cat = v.apply(lambda r: "MISSED" if r["missed"] == "True" else
                  ("traded" if r["traded"] == "True" else
                   ("refused: " + r["refusal_gates"] if r["refusal_gates"] else "no trade")), axis=1)
    cols = {"traded": C["green"], "MISSED": C["vermillion"], "no trade": C["grey"]}
    fig, ax = plt.subplots(figsize=(9, 2.6))
    for k in sorted(set(cat)):
        g = v[cat == k]
        ax.scatter(g["d"], [0] * len(g), s=80, marker="s", color=cols.get(k, C["orange"]), label=k)
    for _, r in v[v["refusal_gates"] != ""].iterrows():
        ax.annotate(r["refusal_gates"], (r["d"], 0), xytext=(0, 10), textcoords="offset points",
                    fontsize=6.5, ha="center", rotation=45)
    ax.set_yticks([])
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.set_xlabel("session date (2026), as verify recorded it at 17:30 ET")
    ax.legend(fontsize=7, ncol=4, loc="lower left")
    ax.set_title(f"{book} sessions by verify outcome, with the refusing gate named")
    b.save_fig(fig, "F10_verify_history", "Verify and gate history", [f"{PACK_REL}/data/live/{book}/verify.csv"],
               v["date"].max(), "The verify log in the pull starts 2026-10-08 (the VM). Corporate-action and "
               "missing-NAV gate records are PENDING (see the manifest).")


def f_counters(b: Build, hist: pd.DataFrame):
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(9, 5), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    cols = {"CEF": C["blue"], "EVENTS": C["orange"], "XASSET": C["green"], "GAMMA": C["purple"],
            "MACRO": C["vermillion"]}
    end = pd.Timestamp(hist["date"].max())
    for name, col in cols.items():
        g = hist[hist["counter"] == name].sort_values("committed")
        if g.empty:
            continue
        x = list(pd.to_datetime(g["date"])) + [end]
        y = list(g["trials"]) + [g["trials"].iloc[-1]]
        ax.step(x, y, where="post", color=col, label=name)
        if name == "CEF":
            ax2.step(x, [math.sqrt(2 * math.log(n)) if n > 1 else float("nan") for n in y], where="post",
                     color=col, label="CEF bar √(2 ln N)")
    ax.set_ylabel("trials counted")
    ax.legend(fontsize=7, ncol=5, loc="upper left")
    ax2.set_ylabel("deflated-Sharpe bar")
    ax2.legend(fontsize=7)
    for a in (ax, ax2):
        _era_shade(a, hist["date"].min(), end)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax2.set_xlabel("commit date of docs/RESEARCH_STATE.md (the counter's canonical table)")
    static = hist[~hist["counter"].isin(cols)].groupby("counter")["trials"].last()
    ax.set_title("Appendix: trial counters as recorded at each commit "
                 f"(static: {', '.join(f'{k} {v}' for k, v in static.items())})", fontsize=9)
    b.save_fig(fig, "F11_trial_counters", "Trial counters", [f"git:HEAD:{COUNTER_DOC} history"], hist["date"].max(),
               "The CEF jump 18 -> 48 on 2026-09-10 is the recorded correction of 2026-09-09 (RESEARCH_STATE.md), "
               "not 30 trials in a day.")


PENDING_STATIC = [
    {"id": "P1_trial54_stages", "title": "Trial 54: stage-by-stage table and fit vs holdout for the z, level "
     "and blend books", "needs": "a figure function in build_pack.py; its inputs, "
     "results/cef/prereg_c4_level/*.json, are on main since PR #42 (65ea0c1)"},
    {"id": "P6_daily_nav_discount", "title": "Daily attribution: the NAV and discount parts of hold P&L",
     "needs": "per-name NAV returns joined to the cached positions (results/report/_cache_live), written as "
     "daily account totals; the committed split covers 2026-09-29..10-30 only "
     "(results/cef/LIVE_ATTRIBUTION_2026-11-02.md, figure F08)"},
    {"id": "P2_core_tearsheet", "title": "Deployed core: fit / holdout tearsheet (daily curve, eras)",
     "needs": "a committed daily P&L series of the deployed core (the registry's series are gitignored, and "
     "CEF-50 (v7) is not in results/research/trials/ledger.jsonl); the v7 prereg commits summary rows only"},
    {"id": "P3_band_plateau", "title": "Band derivation: cube-root law and the plateau around 4.8%",
     "needs": "a committed machine-readable band grid (band width vs gross/net Sharpe and turnover) from "
     "scripts/cef/band_frontier.py; PREREG_BAND_2026-09-06.md carries prose and tables only"},
    {"id": "P4_gate_records", "title": "Corporate-action and missing-NAV gate history",
     "needs": "the VM day folders' gate records (corporate-action and NAV-hold JSON) in the vmpnl.sh pull, "
     "with a sanitising schema in snapshot_live.SCHEMAS"},
    {"id": "P5_c4_live", "title": "C4 account: P&L lines, fill cost and verify figures (its equity is "
     "F06_live_equity_c4)", "needs": "F07 for c4: results/report/data/live/c4/distribution_scores.csv, from a C4 "
     "pull that carries distribution_scores.csv (C4's verify scores a session two sessions late; its pull of "
     "2026-11-04 had none), or a variant of F07 that omits that line, labelled UNMEASURED. F09 and F10 for c4: "
     "a call in build() with their own figure ids on the committed c4 aggregates; F09 also needs C4's own "
     "breakeven, not the core's"},
]


def build(repo: Path = REPO, allow_dirty: bool = False) -> dict:
    _style()
    b = Build(repo=repo, allow_dirty=allow_dirty)
    rel = t_releases(b)
    steps = [
        ("T02_spec_lineage", "Spec lineage table", lambda: t_spec_lineage(b)),
        ("T03_deployed_spec_keys", "Deployed spec keys", lambda: t_deployed_keys(b, rel)),
        ("F01_deployment_timeline", "Deployment timeline", lambda: f_deployments(b, rel)),
        ("F03_trial53_halve_kill", "Trial 53 HALVE/KILL", lambda: f_trial53(b, rel)),
        ("F04_trial54_gate0", "Trial 54 Gate 0", lambda: f_gate0(b)),
        ("F05_c4_trial52", "C4 fit vs holdout", lambda: f_c4(b)),
        ("F06_live_equity", "Live equity", lambda: f_live_equity(b, rel)),
        ("F06_live_equity_c4", "Live equity, C4 account",
         lambda: f_live_equity(b, rel, book="c4", fid="F06_live_equity_c4", title="Live equity, C4 account")),
        ("F07_live_pnl_lines", "Live P&L lines", lambda: f_live_daily(b)),
        ("F08_live_attribution", "Live attribution", lambda: f_attribution(b)),
        ("F09_tca", "TCA", lambda: f_tca(b, rel)),
        ("F10_verify_history", "Verify history", lambda: f_verify(b)),
        ("T05_trial_registry", "Trial registry", lambda: t_registry(b)),
        ("T06_evidence_index", "Evidence index", lambda: t_evidence_index(b)),
    ]
    lineage = None
    for sid, title, fn in steps:
        b._current = []
        try:
            res = fn()
            if sid == "T02_spec_lineage":
                lineage = res
                f_spec_lineage(b, res)
        except Pending as p:
            b.pending.append({"id": sid, "title": title, "needs": str(p)})
    try:
        f_counters(b, counter_history(b))
    except Pending as p:
        b.pending.append({"id": "F11_trial_counters", "title": "Trial counters", "needs": str(p)})
    b.pending.extend(PENDING_STATIC)
    manifest = {
        "about": "Every output of the research evidence pack, its inputs with sha256, and what is PENDING. "
                 "Rebuild: python3 -m scripts.report.build_pack",
        "built_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "commit": b.commit, "clean_inputs": all(v["committed"] for v in b.inputs.values()),
        "newest_release_tag": rel["tag"].iloc[-1], "builder": "scripts/report/build_pack.py",
        "outputs": b.outputs, "inputs": dict(sorted(b.inputs.items())), "pending": b.pending,
    }
    (repo / PACK_REL / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=False) + "\n")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--allow-dirty", action="store_true")
    a = ap.parse_args(argv)
    m = build(allow_dirty=a.allow_dirty)
    print(f"built {sum(o['kind'] == 'figure' for o in m['outputs'])} figures, "
          f"{sum(o['kind'] == 'table' for o in m['outputs'])} tables; {len(m['pending'])} PENDING; "
          f"commit {m['commit'][:7]}; clean inputs: {m['clean_inputs']}")
    for p in m["pending"]:
        print(f"  PENDING {p['id']}: {p['needs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
