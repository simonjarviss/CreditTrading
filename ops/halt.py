"""Durable halt records and the alerting that makes a halt impossible to miss.

WHY THIS FILE EXISTS
--------------------
On 2026-07-31 two separate faults produced total silence:

  1. 09:35 — the launchd job died with exit 126 (`getcwd: Operation not
     permitted`, a TCC/Full-Disk-Access fault). It wrote two lines to a log and
     transmitted nothing.
  2. 16:33 — the CEF job DID trade, then the shadow ledger KeyErrored on a
     missing cost entry. The exception was caught and printed as one `repr()`
     line inside an otherwise successful-looking run that ended with "ok".

In both cases the operator learned nothing until a human went reading logs. For
a book that is supposed to run unattended, "the failure is in a log file" is the
same as no failure handling at all — logs are pull, and an unattended system
needs push.

So a halt here is three things at once, in increasing order of loudness:

  * `ops/HALT.md`   — durable, greppable, and read by `ops/preflight.py` as a
                      HARD GATE. This is the one that actually stops the money:
                      it survives reboots and outlives any notification.
  * macOS banner + spoken alert — reaches the operator if they are at the machine.
  * email           — reaches them if they are not.

The ordering matters. Alerting is best-effort and must NEVER be able to mask the
fault it is reporting, so every notification path is individually wrapped: an
SMTP timeout cannot prevent HALT.md from being written, and a failed banner
cannot swallow the traceback. The file write happens FIRST and unguarded.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HALT_PATH = REPO_ROOT / "ops" / "HALT.md"
HALT_ARCHIVE = REPO_ROOT / "ops" / "halts"


def scoped_path(book: str) -> Path:
    """`ops/HALT_<book>.md` — a halt that blocks ONE book.

    WHY SCOPED HALTS EXIST (2026-09-10). `ops/HALT.md` blocks every book, which
    is right for a fault nobody can explain and wrong for a fault that belongs
    to one book. Three halts in three days proved it:

      * 09-09 09:37  phase0 could not attribute JNK  -> blocked the CEF book
      * 09-09 17:25  bench_b6 could not attribute ANGL (its own $2.5k fill,
                     placed before its ledger was re-seeded) -> would have
                     blocked the CEF session at 22:45
      * both cleared by hand, both about a book that is not the strategy

    A $20,000 benchmark book must not be able to stop a $500,000 strategy over
    its own bookkeeping. `arm()` only ever refuses on symbols the book being
    armed trades, so an arming failure is inherently that book's problem.

    The scope is a DOWNGRADE for other books, never a dismissal: preflight
    reports another book's scoped halt as a non-blocking WARNING naming the
    book, so the operator still sees it on every session. A human halt, and
    anything whose cause is not provably one book's, stays global.

    Same directory and prefix as `HALT.md` on purpose: `ls ops/HALT*.md` shows
    everything that is currently blocking anything.
    """
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(book))
    if not safe:
        raise ValueError("scoped_path needs a book name")
    return REPO_ROOT / "ops" / f"HALT_{safe}.md"


def _halt_paths(book=None):
    """(path this call writes/reads, human label)."""
    return (HALT_PATH, "ops/HALT.md") if book is None else (
        scoped_path(book), f"ops/{scoped_path(book).name}")


# -- environment ----------------------------------------------------------

def _load_env_file(path=REPO_ROOT / "config" / ".env") -> dict:
    """Parse config/.env. A launchd job inherits almost no environment, so the
    alert credentials cannot be assumed to be exported — read them from disk."""
    out = {}
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def _cfg(key, default=None):
    return os.environ.get(key) or _load_env_file().get(key) or default


# -- the durable record ---------------------------------------------------

def write_halt(reason: str, detail: str = "", source: str = "",
               book: str | None = None) -> Path:
    """Record a halt and alert on it. Returns the path written.

    `book=None` writes the GLOBAL `ops/HALT.md` and blocks every book — the
    default, and correct for a human halt or a fault nobody can attribute.
    `book="cef_discount_paper"` writes `ops/HALT_cef_discount_paper.md` and
    blocks only that book; see `scoped_path` for why.

    Writing the file is deliberately NOT wrapped in try/except: if we cannot
    persist the halt we would rather crash than continue believing the book is
    protected. Every alert channel after it IS wrapped, for the opposite reason.
    """
    stamp = datetime.now()
    path, label = _halt_paths(book)
    path.parent.mkdir(parents=True, exist_ok=True)

    scope = (f"trading is BLOCKED for **{book}** until this file is cleared "
             f"(other books are warned, not blocked)" if book else
             "trading is BLOCKED until this file is cleared")
    clear_arg = f"clear_halt('what you fixed', book='{book}')" if book else \
                "clear_halt('what you fixed')"

    existing = path.read_text() if path.exists() else ""
    entry = (f"## {stamp:%Y-%m-%d %H:%M:%S}  {reason}\n\n"
             f"- **source**: `{source or 'unspecified'}`\n"
             f"- **state**: {scope}\n\n"
             f"{detail.strip()}\n\n"
             f"To clear once the cause is genuinely fixed:\n\n"
             f"    python3 -c \"from ops.halt import clear_halt; "
             f"{clear_arg}\"\n\n---\n\n")

    if book:
        header = (f"# HALT — {book}\n\n"
                  f"`ops/preflight.py` reads this file before every session of "
                  f"**{book}** and will not arm live orders for it while this "
                  f"file exists. Other books see it as a WARNING and continue: "
                  f"an arming failure is about the symbols the failing book "
                  f"trades, and one book's bookkeeping must not stop another's "
                  f"strategy. Data collection and logging continue regardless.\n\n"
                  f"Most recent halt first.\n\n---\n\n")
    else:
        header = ("# HALT — automated trading is blocked\n\n"
                  "`ops/preflight.py` reads this file before every scheduled "
                  "session and will not arm live orders while it exists. Data "
                  "collection and logging continue regardless: a halted book "
                  "still records, it just does not trade.\n\n"
                  "Most recent halt first.\n\n---\n\n")
    body = existing.split("---\n\n", 1)[1] if "---\n\n" in existing else ""
    path.write_text(header + entry + body)

    who = f"QUANTT HALT [{book}]" if book else "QUANTT HALT"
    alert(subject=f"{who}: {reason}",
          body=f"{reason}\n\nsource: {source}\nscope: {label}\n\n{detail}",
          speak=(f"Quant book {book} halted." if book
                 else "Quant book halted. Trading is blocked."))
    return path


def _parse_halt(path, book=None):
    if not path.exists():
        return None
    text = path.read_text()
    reason, when = "unknown", ""
    for line in text.splitlines():
        if line.startswith("## "):
            head = line[3:].strip()
            when, _, reason = head.partition("  ")
            break
    return {"reason": reason.strip() or "unknown", "when": when.strip(),
            "text": text, "path": str(path), "book": book,
            "scope": book or "global"}


def read_halt(book: str | None = None):
    """The halt that BLOCKS `book`, or None.

    Global first: `ops/HALT.md` blocks everything, so it wins over a scoped
    file. With `book=None` this is exactly the pre-2026-09-10 behaviour —
    global only — which is what keeps every existing caller correct.
    """
    active = _parse_halt(HALT_PATH)
    if active is not None:
        return active
    if book is None:
        return None
    return _parse_halt(scoped_path(book), book=book)


def other_book_halts(book: str | None = None) -> list:
    """Scoped halts that do NOT block `book` — advisory, for every session.

    A scoped halt is a downgrade for other books, not a dismissal: preflight
    surfaces these as non-blocking warnings so an unattended benchmark book
    sitting halted for a week cannot go unnoticed just because the strategy
    kept trading.
    """
    mine = scoped_path(book).name if book else None
    out = []
    for p in sorted((REPO_ROOT / "ops").glob("HALT_*.md")):
        if p.name == mine:
            continue
        h = _parse_halt(p, book=p.stem[len("HALT_"):])
        if h:
            out.append(h)
    return out


def clear_halt(note: str = "", book: str | None = None) -> bool:
    """Archive one halt. Deliberately a manual, attributed act.

    Self-clearing would defeat the point: the preflight gate can re-arm itself
    when its CHECKS pass, but a desync that required a ledger rebuild needs a
    human to say the rebuild happened and was correct.

    `book=None` clears the global `ops/HALT.md` only — it never touches a
    scoped halt, because clearing "the halt" must not silently unblock a book
    whose fault nobody looked at. Any scoped halts still standing are listed.
    """
    path, label = _halt_paths(book)
    if not path.exists():
        print(f"[halt] no active halt at {label}")
        if book is None:
            for h in other_book_halts():
                print(f"[halt] still blocking {h['book']}: {h['reason']} "
                      f"({h['when']}) — clear with "
                      f"clear_halt('...', book='{h['book']}')")
        return False
    HALT_ARCHIVE.mkdir(parents=True, exist_ok=True)
    tag = f"_{book}" if book else ""
    dest = HALT_ARCHIVE / f"HALT{tag}_{datetime.now():%Y%m%d_%H%M%S}.md"
    shutil.move(str(path), dest)
    if note:
        dest.write_text(dest.read_text() +
                        f"\n\nCLEARED {datetime.now():%Y-%m-%d %H:%M:%S}: {note}\n")
    print(f"[halt] cleared {label} -> {dest}")
    alert(subject=f"QUANTT halt cleared ({book or 'global'})",
          body=f"{note}\n\nscope: {label}\narchived to {dest}",
          speak="Quant halt cleared.")
    return True


# -- alerting -------------------------------------------------------------

def alert(subject: str, body: str = "", speak: str = "") -> dict:
    """Best-effort push on every configured channel. Never raises.

    Returns per-channel outcomes so a caller (and the daily log) can see which
    ones actually delivered — a silent alerting system is the exact failure this
    module exists to prevent, so "we tried to tell you" must itself be visible.
    """
    out = {}
    out["notification"] = _notify_macos(subject, body)
    if speak:
        out["speech"] = _speak(speak)
    out["email"] = _email(subject, body)
    for channel, res in out.items():
        if res is not True:
            print(f"[alert] {channel}: {res}")
    return out


def _notify_macos(title: str, body: str):
    try:
        msg = (body or "").replace('"', "'").replace("\n", " ")[:240]
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{msg}" with title "{title[:120]}"'],
            check=True, capture_output=True, timeout=10)
        return True
    except Exception as exc:
        return f"failed ({exc!r})"


def _speak(phrase: str):
    try:
        subprocess.run(["say", phrase[:200]], check=True,
                       capture_output=True, timeout=20)
        return True
    except Exception as exc:
        return f"failed ({exc!r})"


def _email(subject: str, body: str):
    """SMTP over STARTTLS. Configured entirely from config/.env:

        ALERT_EMAIL_TO=you@example.com
        ALERT_SMTP_HOST=smtp.gmail.com
        ALERT_SMTP_PORT=587
        ALERT_SMTP_USER=you@example.com
        ALERT_SMTP_PASS=<16-char Google app password, NOT the account password>

    Gmail rejects a plain account password over SMTP, so this needs an App
    Password from https://myaccount.google.com/apppasswords (requires 2FA on).
    Absent credentials is a configuration state, not an error — it returns a
    message saying so rather than raising, because a missing mail password must
    never stop a halt from being recorded.

    No address is written in this file, because the repository is public (team
    lead, 2026-11-09). With no ALERT_EMAIL_TO the alert goes to the SMTP account
    itself: until that date a hard-coded recipient filled this gap, and a machine
    that sets only the SMTP pair must not lose its halt alerts at this change.
    """
    host = _cfg("ALERT_SMTP_HOST", "smtp.gmail.com")
    port = int(_cfg("ALERT_SMTP_PORT", "587"))
    user = _cfg("ALERT_SMTP_USER")
    to = _cfg("ALERT_EMAIL_TO", user)
    password = _cfg("ALERT_SMTP_PASS")
    if not (user and password):
        return ("not configured — add ALERT_SMTP_USER and ALERT_SMTP_PASS "
                "(a Google App Password) to config/.env to enable email alerts")
    try:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = subject[:200]
        msg["From"] = user
        msg["To"] = to
        msg.set_content(f"{body}\n\n-- \nQUANTT automated book, "
                        f"{datetime.now():%Y-%m-%d %H:%M:%S} local\n"
                        f"host: {os.uname().nodename}\n")
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
        return True
    except Exception as exc:
        return f"failed ({exc!r})"


# -- heartbeat ------------------------------------------------------------

HEARTBEAT_PATH = REPO_ROOT / "ops" / "heartbeat.json"


def beat(job: str, status: str, detail: dict | None = None) -> Path:
    """Record that `job` reached `status` just now.

    Silence and success are indistinguishable to an unattended system — a job
    that never fired looks exactly like one that fired and did nothing. The
    heartbeat makes the difference observable: `ops/preflight.py` compares the
    last beat against the NYSE calendar and alerts on a session that produced no
    beat at all, which is the ONLY way the 09:35 exit-126 failure would have been
    caught automatically.
    """
    hist = {}
    if HEARTBEAT_PATH.exists():
        try:
            hist = json.loads(HEARTBEAT_PATH.read_text())
        except Exception:
            hist = {}
    # `date` IS THE DATE THIS BEAT WAS FILED, NOT THE SESSION IT DESCRIBES, and
    # that distinction cost a trading day. On 2026-09-10 the session slept and
    # filed its beat at 10:38 on 2026-09-11, stamping date=2026-09-11 with
    # armed=true. launch_job.py's same-day guard compares `prior["date"]`
    # against the session's own `today`, so the 09-11 session was refused --
    # correctly, given what it was told, since the trade phase is not
    # idempotent. One power event, two lost sessions.
    #
    # `session_date` is the decision the beat is ABOUT. Recorded ALONGSIDE
    # `date`, never instead of it: `date` answers "is this system alive right
    # now", which preflight's staleness check needs, and `session_date` answers
    # "which decision did this describe", which the guards need. Collapsing
    # them in either direction rebuilds the defect with the opposite sign.
    #
    # Additive on purpose. Nothing is rekeyed here -- the same-day guard lives
    # in the out-of-repo launch_job.py and is out of scope for this change --
    # so a reader of the old field sees exactly what it saw before.
    now = datetime.now()
    d = dict(detail or {})
    session_date = d.get("pair_date") or d.get("asof")
    hist[job] = {"status": status, "at": f"{now:%Y-%m-%d %H:%M:%S}",
                 "date": f"{now:%Y-%m-%d}",
                 "session_date": str(session_date)[:10] if session_date else None,
                 "detail": d}
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_PATH.write_text(json.dumps(hist, indent=2))
    return HEARTBEAT_PATH


def all_beats() -> dict:
    """Every job's last beat, as one dict.

    `last_beat` answers "what did THIS job do", which is the only question the
    same-day guard ever had to ask. The two-session cef schedule (ops/
    session_plan.py) asks a different one -- "has ANY cef job already armed on
    this pair, or on this date" -- and that cannot be answered one job at a
    time, because the session it has to catch is the OTHER one: yesterday
    evening's fallback, whose beat is filed under `cef_pm` and dated a
    different day.

    Returns {} rather than raising on a missing or corrupt file, which is the
    safe direction HERE and only here: an empty beat history makes both guards
    find no prior decision, and the callers treat "no evidence of a decision"
    as a reason to run preflight normally, not as authorisation to transmit.
    """
    if not HEARTBEAT_PATH.exists():
        return {}
    try:
        data = json.loads(HEARTBEAT_PATH.read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def last_beat(job: str):
    if not HEARTBEAT_PATH.exists():
        return None
    try:
        return json.loads(HEARTBEAT_PATH.read_text()).get(job)
    except Exception:
        return None
