"""A shadow book is one small json file: `shadow/books/<slug>.json`.

WHY A FILE AND NOT CODE: starting a book must be a commit, not a build
(results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md section 3). The file names a signal
function, the panels it reads and how the book is filled; the engine does the rest the
same way for every book, so two books cannot be scored by two conventions.

Every key is REQUIRED. A missing key raises, naming it: a default here would be a
parameter nobody chose (CLAUDE.md, no silent fallbacks).
"""
from __future__ import annotations

import datetime as dt
import importlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REQUIRED = ("slug", "card", "signal", "panels", "refresh", "fill", "notional_usd", "started", "enabled")
# The fill conventions the engine implements. `next_close` is the harness's shift(2):
# decide on D, fill at the next session's close, earn from that close on.
FILLS = ("next_close",)


class BookError(ValueError):
    """A book file that cannot be used, naming the file and the key."""


@dataclass(frozen=True)
class Panel:
    name: str
    path: str            # relative to <state>/panels/
    date_col: str        # the column that dates a row: the engine truncates on it
    required_asof: bool  # True: the book does not decide unless this panel has a row dated asof


@dataclass(frozen=True)
class Book:
    slug: str
    card: str
    signal: str
    panels: tuple[Panel, ...]
    refresh: tuple[tuple[str, ...], ...]   # commands the nightly run executes before deciding; may be empty
    fill: str
    notional_usd: float
    started: dt.date
    enabled: bool

    def signal_fn(self) -> Callable:
        """Import `module:function`. Imported at call time, so loading every book file
        (the scoreboard does) never imports every signal's dependencies."""
        mod, _, fn = self.signal.partition(":")
        if not mod or not fn:
            raise BookError(f"{self.slug}: signal {self.signal!r} is not 'module:function'")
        return getattr(importlib.import_module(mod), fn)


def load(path: Path) -> Book:
    raw = json.loads(Path(path).read_text())
    missing = [k for k in REQUIRED if k not in raw]
    if missing:
        raise BookError(f"{path}: missing key(s) {missing}")
    slug = raw["slug"]
    if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9_]+", slug):
        raise BookError(f"{path}: slug {slug!r} must be lowercase letters, digits and underscores")
    if Path(path).stem != slug:
        raise BookError(f"{path}: the file name must be the slug ({slug}.json)")
    if raw["fill"] not in FILLS:
        raise BookError(f"{path}: fill {raw['fill']!r} is not one of {FILLS}")
    notional = raw["notional_usd"]
    if not isinstance(notional, (int, float)) or isinstance(notional, bool) or notional <= 0:
        raise BookError(f"{path}: notional_usd must be a positive number")
    if not isinstance(raw["enabled"], bool):
        raise BookError(f"{path}: enabled must be true or false")
    # An empty dict is allowed and says something: the signal reads no data at all (a pure
    # calendar rule). It must still be written, so that "no panels" is a choice, not an omission.
    if not isinstance(raw["panels"], dict):
        raise BookError(f"{path}: panels must be an object (empty for a signal that reads no data)")
    panels = []
    for name, p in sorted(raw["panels"].items()):
        need = [k for k in ("path", "date_col", "required_asof") if k not in p]
        if need:
            raise BookError(f"{path}: panel {name!r} is missing {need}")
        if Path(p["path"]).is_absolute() or ".." in Path(p["path"]).parts:
            raise BookError(f"{path}: panel {name!r} path must stay inside <state>/panels/")
        panels.append(Panel(name, p["path"], p["date_col"], bool(p["required_asof"])))
    refresh = raw["refresh"]
    if not isinstance(refresh, list) or not all(
            isinstance(c, list) and c and all(isinstance(a, str) for a in c) for c in refresh):
        raise BookError(f"{path}: refresh must be a list of commands, each a non-empty list of strings")
    return Book(slug, raw["card"], raw["signal"], tuple(panels), tuple(tuple(c) for c in refresh), raw["fill"], float(notional),
                dt.date.fromisoformat(raw["started"]), raw["enabled"])


def load_all(books_dir: Path) -> list[Book]:
    return [load(p) for p in sorted(Path(books_dir).glob("*.json"))]
