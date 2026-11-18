"""`ops/sleeves/events_sleeves.json`: which shadow books trade on paper, with how much, inside which limits.

Every key is REQUIRED and checked. A missing or mistyped key raises, naming it: a default
here would be a limit nobody chose (CLAUDE.md, no silent fallbacks). Keys starting with `_`
are notes and are ignored.

  book                 the Alpaca paper account's name: keys ALPACA_<BOOK>_KEY_ID / _SECRET_KEY,
                       client order ids `<book>-<YYYYMMDD>-<SYMBOL>-1`.
  sleeves              [{slug, family, full_capital_usd, capital_usd, enabled}]. `slug` is a
                       shadow book's; its weights are fractions of `capital_usd` here (the
                       shadow file's own notional is ignored). `enabled: false` with shares
                       still in the ledger means FLATTEN that sleeve; to stop it without
                       trading, halt the book.
                       `capital_usd` is what the runner TRADES: the sleeve's current stage on
                       the ladder. `full_capital_usd` is its full size and `family` the idea
                       it is a variant of (team lead, 2026-11-18: equal risk per family, a
                       family's variants splitting its share). The runner sizes nothing from
                       those two; they are here so the file says by itself which stage a
                       sleeve is at, and `quantt/sleeves/promote.py` (read-only) checks that
                       `capital_usd` is `full_capital_usd` x a ladder stage. Until 2026-11-18
                       the full sizes lived only in the prose of `_note_sleeves`, where no
                       program could check a stage against them.
  min_order_usd        a net order smaller than this is not sent (re-sizing noise).
  max_gross_x_equity   the book's gross after the plan, as a multiple of account equity;
                       above it every sleeve's target is scaled by one factor.
  max_name_usd         the largest net position in one symbol; above it the plan is refused,
                       naming the symbol.
  max_stale_sessions   a sleeve with no usable decision holds its shares for this many
                       sessions, then is flattened.
  max_orders           the most orders one session may send; above it the plan is refused
                       (the send window fits about a hundred; docs/RUNNER.md).
  execution            {mode: "late_market", window_minutes_before_close: [a, b]}: the paper
                       exception of 2026-09-29 (CLAUDE.md order-path rule 3). No other mode is
                       built here.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

REQUIRED = ("book", "sleeves", "min_order_usd", "max_gross_x_equity", "max_name_usd",
            "max_stale_sessions", "max_orders", "execution")
SLEEVE_KEYS = ("slug", "family", "full_capital_usd", "capital_usd", "enabled")


class ConfigError(ValueError):
    """The sleeves book file cannot be used; the message names the file and the key."""


@dataclass(frozen=True)
class Sleeve:
    slug: str
    capital_usd: float        # what the runner trades: the current ladder stage
    enabled: bool
    full_capital_usd: float   # the sleeve's full size; read by promote.py, never by the runner
    family: str               # the idea this sleeve is a variant of; read by reports only


@dataclass(frozen=True)
class Config:
    book: str
    sleeves: tuple            # of Sleeve, in file order
    min_order_usd: float
    max_gross_x_equity: float
    max_name_usd: float
    max_stale_sessions: int
    max_orders: int
    window_minutes_before_close: tuple   # (first, last), e.g. (8, 2)

    def sleeve(self, slug: str) -> Sleeve:
        for s in self.sleeves:
            if s.slug == slug:
                return s
        raise ConfigError(f"sleeve {slug!r} is not in the book file")

    @property
    def slugs(self) -> tuple:
        return tuple(s.slug for s in self.sleeves)


def _num(path, key, v, *, positive=True) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or (v <= 0 if positive else v < 0):
        raise ConfigError(f"{path}: {key} must be a finite number {'> 0' if positive else '>= 0'}, got {v!r}")
    return float(v)


def _int(path, key, v) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
        raise ConfigError(f"{path}: {key} must be a positive whole number, got {v!r}")
    return v


def load(path: Path) -> Config:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: the file must hold one object")
    missing = [k for k in REQUIRED if k not in raw]
    if missing:
        raise ConfigError(f"{path}: missing key(s) {missing}")
    unknown = [k for k in raw if k not in REQUIRED and not k.startswith("_")]
    if unknown:
        raise ConfigError(f"{path}: unknown key(s) {unknown}; a note key starts with '_'")
    book = raw["book"]
    if not isinstance(book, str) or not re.fullmatch(r"[a-z][a-z0-9]*", book):
        raise ConfigError(f"{path}: book {book!r} must be lowercase letters and digits")
    if book in ("cef", "c4", "b6"):
        raise ConfigError(f"{path}: book {book!r} is another book's account; the sleeves need their own")
    if not isinstance(raw["sleeves"], list) or not raw["sleeves"]:
        raise ConfigError(f"{path}: sleeves must be a non-empty list")
    sleeves, seen = [], set()
    for i, s in enumerate(raw["sleeves"]):
        if not isinstance(s, dict) or sorted(k for k in s if not k.startswith("_")) != sorted(SLEEVE_KEYS):
            raise ConfigError(f"{path}: sleeves[{i}] must have exactly the keys {list(SLEEVE_KEYS)}")
        slug = s["slug"]
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9_]+", slug):
            raise ConfigError(f"{path}: sleeves[{i}].slug {slug!r} must be lowercase letters, digits and underscores")
        if slug in seen:
            raise ConfigError(f"{path}: sleeve {slug!r} is listed twice")
        seen.add(slug)
        if not isinstance(s["enabled"], bool):
            raise ConfigError(f"{path}: sleeves[{i}].enabled must be true or false")
        family = s["family"]
        if not isinstance(family, str) or not re.fullmatch(r"[a-z0-9_]+", family):
            raise ConfigError(f"{path}: sleeves[{i}].family {family!r} must be lowercase letters, digits and underscores")
        sleeves.append(Sleeve(slug, _num(path, f"sleeves[{i}].capital_usd", s["capital_usd"]), s["enabled"],
                              _num(path, f"sleeves[{i}].full_capital_usd", s["full_capital_usd"]), family))
    ex = raw["execution"]
    if not isinstance(ex, dict) or ex.get("mode") != "late_market":
        raise ConfigError(f"{path}: execution.mode must be 'late_market' (the only mode built; paper only)")
    w = ex.get("window_minutes_before_close")
    if (not isinstance(w, list) or len(w) != 2 or any(isinstance(x, bool) or not isinstance(x, int) for x in w)
            or not w[0] > w[1] > 0):
        raise ConfigError(f"{path}: execution.window_minutes_before_close must be [first, last] whole minutes, first > last > 0")
    return Config(book=book, sleeves=tuple(sleeves),
                  min_order_usd=_num(path, "min_order_usd", raw["min_order_usd"], positive=False),
                  max_gross_x_equity=_num(path, "max_gross_x_equity", raw["max_gross_x_equity"]),
                  max_name_usd=_num(path, "max_name_usd", raw["max_name_usd"]),
                  max_stale_sessions=_int(path, "max_stale_sessions", raw["max_stale_sessions"]),
                  max_orders=_int(path, "max_orders", raw["max_orders"]),
                  window_minutes_before_close=(w[0], w[1]))
