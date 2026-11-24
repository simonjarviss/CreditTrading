"""The whole public site: every page built, every local link resolves, the disclaimer on every page,
the swap atomic, a dirty snapshot refused with nothing published."""
import datetime as dt
import json
import re
import shutil
from pathlib import Path

import pytest

from dashboard import build as B
from dashboard import site as SITE

DASH = Path(__file__).resolve().parents[1]
FIXTURE = DASH / "fixtures" / "sample_snapshot.json"
LIB = {"entries": [
    {"topic": "Closed-end fund discounts", "kind": "paper", "authors": "Lee, Shleifer and Thaler", "year": 1991,
     "title": "Investor Sentiment and the Closed-End Fund Puzzle", "venue": "Journal of Finance 46(1), 75-109",
     "url": "https://doi.org/10.1111/j.1540-6261.1991.tb03746.x", "oa_pdf_url": None,
     "used_for": "Why discounts co-move with sentiment.", "verified_by": "crossref", "cited_in": []}]}


@pytest.fixture
def content(tmp_path):
    c = tmp_path / "content"
    shutil.copytree(DASH / "content", c)
    (c / "library.json").write_text(json.dumps(LIB))
    return c


@pytest.fixture(autouse=True)
def record_from_the_fixtures_first_send(monkeypatch):
    """The fixture's books trade from 17 Nov 2026, before the shipped RECORD_START (24 Nov), which would
    leave them no session. Tests of the record start set their own."""
    monkeypatch.setattr(B, "RECORD_START", "2026-11-17")


@pytest.fixture
def snap():
    return json.loads(FIXTURE.read_text())


def build(snap, root, content, when=dt.datetime(2026, 11, 23, 23, 20, tzinfo=dt.timezone.utc)):
    return SITE.publish(snap, root, when, content=content)


def test_every_page_is_built_and_carries_the_disclaimer_and_contact(snap, tmp_path, content):
    target = build(snap, tmp_path / "site", content)
    pages = sorted(p.relative_to(target).as_posix() for p in target.rglob("*.html"))
    assert pages == ["404.html", "contact/index.html", "index.html", "library/index.html",
                     "performance/index.html", "research/index.html", "team/index.html"]
    for p in pages:
        h = (target / p).read_text()
        assert "No client or outside capital is invested" in h, p
        assert "simon.jarvis@queensu.ca" in h, p


def test_every_local_link_and_asset_exists(snap, tmp_path, content):
    target = build(snap, tmp_path / "site", content)
    missing = []
    for page in target.rglob("*.html"):
        for ref in re.findall(r'(?:href|src)="(/[^"#?]*)', page.read_text()):
            p = target / ref.lstrip("/")
            if not (p.is_file() or (p / "index.html").is_file()):
                missing.append((page.name, ref))
    assert not missing, missing


def test_the_team_page_is_the_home_page(snap, tmp_path, content):
    """Team lead, 2026-11-24: "when we open the page, it should be the team page which shows first"."""
    target = build(snap, tmp_path / "site", content)
    home = (target / "index.html").read_text()
    assert "Lucy Keith" in home and home.count(">LinkedIn</a>") == 4 and "<title>Event Driven Trading</title>" in home
    assert (target / "team" / "index.html").read_text() == home                       # earlier links still work
    nav = home.split('<nav class="nav"', 1)[1].split("</nav>", 1)[0]
    assert nav.index('href="/"') < nav.index('href="/performance/"')
    # Team lead, 2026-11-24: "delete overview page"; and no slideshow (2026-11-23).
    assert "/overview/" not in home and not (target / "overview").exists() and not (target / "strategy").exists()


def test_a_new_book_is_dated_by_its_first_send_not_its_newest_session(snap, tmp_path, content):
    """Release-check review, 2026-11-23: "Trading since" printed the newest session, a date that moved
    forward every session. The start is the first day the runner wrote STARTED."""
    ev = next(b for b in snap["books"] if b["name"] == "events")
    assert ev["start"]["value"]["first_send"] == "2026-11-23"
    ev["session"]["value"]["date"] = "2026-11-25"           # two sessions later
    target = build(snap, tmp_path / "site", content)
    assert "Event Book<br><span class=\"meta\">from 23 Nov 2026" in (target / "performance" / "index.html").read_text()
    for page in ("index.html", "performance/index.html"):
        h = (target / page).read_text()
        assert "since 25 Nov 2026" not in h, page


def test_an_unreadable_session_is_not_called_new_or_missing(snap, tmp_path, content):
    ev = next(b for b in snap["books"] if b["name"] == "events")
    ev["session"] = {"UNMEASURED": "events/2026-11-23/verify.json: not JSON"}
    h = (build(snap, tmp_path / "site", content) / "performance" / "index.html").read_text()
    assert "Event Book: session not read." in h and "no record yet" not in h


def test_the_team_page_lists_the_four_members_with_their_links(snap, tmp_path, content):
    h = (build(snap, tmp_path / "site", content) / "team" / "index.html").read_text()
    for name in ("Simon Jarvis", "Ryan Press", "James Simone", "Lucy Keith"):
        assert name in h
    assert h.count(">LinkedIn</a>") == 4
    # Team lead, 2026-11-24: "add portfolio manager under me, and quantitative trading analyst under the other 3".
    assert re.findall(r'<h3>([^<]+)</h3><p class="role">([^<]+)</p>', h) == [
        ("Simon Jarvis", "Portfolio Manager"), ("Ryan Press", "Quantitative Trading Analyst"),
        ("James Simone", "Quantitative Trading Analyst"), ("Lucy Keith", "Quantitative Trading Analyst")]


def test_the_library_links_each_source(snap, tmp_path, content):
    h = (build(snap, tmp_path / "site", content) / "library" / "index.html").read_text()
    assert "Investor Sentiment and the Closed-End Fund Puzzle" in h
    assert 'href="https://doi.org/10.1111/j.1540-6261.1991.tb03746.x"' in h


def test_a_missing_library_file_stops_the_build(snap, tmp_path, content):
    (content / "library.json").unlink()
    with pytest.raises(FileNotFoundError):
        build(snap, tmp_path / "site", content)
    assert not (tmp_path / "site" / "current").exists()


def test_publish_swaps_atomically_and_keeps_three_builds(snap, tmp_path, content):
    root = tmp_path / "site"
    targets = [build(snap, root, content, dt.datetime(2026, 11, 23, 23, m, tzinfo=dt.timezone.utc)) for m in range(5)]
    assert (root / "current").resolve() == targets[-1].resolve()
    kept = sorted(p.name for p in (root / "builds").iterdir())
    assert kept == [t.name for t in targets[-3:]]


def test_a_dirty_snapshot_publishes_nothing(snap, tmp_path, content):
    snap["books"][0]["session"]["value"]["reason"] = "host 10.1.2.3"
    with pytest.raises(SystemExit, match="refused"):
        build(snap, tmp_path / "site", content)
    assert not (tmp_path / "site").exists()


def test_the_committed_content_is_complete():
    """What a release needs: the fonts, the photographs and the library."""
    for f in ("fonts/inter-latin-wght.woff2", "fonts/source-serif-4-latin-wght.woff2", "img/hero-office.webp",
              "img/quantt-logo.png", "img/quantt-logo-white.png"):
        assert (DASH / "public" / "static" / f).is_file(), f
    assert (DASH / "public" / "static" / "fonts" / "inter-latin-wght.woff2").is_file()
    lib = json.loads((DASH / "content" / "library.json").read_text())
    assert lib["entries"] and all(e["title"] and e["topic"] for e in lib["entries"])
    for e in lib["entries"]:
        for k in ("url", "oa_pdf_url"):
            assert e.get(k) is None or e[k].startswith("https://") or e[k].startswith("http://"), e


def test_every_daemon_reload_in_the_site_installer_is_guarded():
    """A reload applies to every unit on the VM, so each one must follow the guard that refuses on
    drop-ins, running quantt jobs and the send windows (execution review of 83a7b14, 2026-11-23)."""
    sh = (DASH / "deploy" / "install_site_vm.sh").read_text()
    body = sh.split("check_safe_to_reload() {", 1)[1]
    for fn in ("do_install() {", "do_uninstall() {"):
        part = body.split(fn, 1)[1].split("\n}\n", 1)[0]
        assert "systemctl daemon-reload" in part
        assert part.index("check_safe_to_reload") < part.index("systemctl daemon-reload"), fn
    guard = body.split("\n}\n", 1)[0]
    for needle in ("list-jobs", "1530", "1230", "quantt-*.d", "service.d", "NeedDaemonReload"):
        assert needle in guard, needle
    install = body.split("do_install() {", 1)[1].split("\n}\n", 1)[0]
    assert install.index("check_safe_to_reload") < install.index("install_caddy"), \
        "caddy's package post-install reloads systemd: the guard must come first"
    for line in install.splitlines():
        if "systemctl enable" in line:
            assert "--no-reload" in line, line
    for refusal in ('|| die "cannot list the running quantt units"', '|| die "cannot list the quantt units"'):
        assert refusal in guard, "a failed query must refuse, never read as nothing running"


def test_the_stylesheet_and_script_urls_change_with_their_content(snap, tmp_path, content):
    """2026-11-24: Cloudflare kept the previous release's stylesheet for up to an hour beside new pages."""
    from dashboard import layout as L
    h = (build(snap, tmp_path / "site", content) / "index.html").read_text()
    v = L.asset_version()
    assert re.fullmatch(r"[0-9a-f]{12}", v)
    assert f'href="/static/site.css?v={v}"' in h and f'src="/static/site.js?v={v}"' in h


def test_the_library_is_grouped_with_counts_and_searchable(snap, tmp_path, content, monkeypatch):
    """Team lead, 2026-11-24: "re organize the library / research its ugly"."""
    monkeypatch.setattr(SITE, "RESEARCH_UNDER_CONSTRUCTION", False)
    target = build(snap, tmp_path / "site", content)
    h = (target / "library" / "index.html").read_text()
    assert 'id="lib-search"' in h and 'class="lib-side"' in h and h.count('class="lib-row"') == len(LIB["entries"])
    assert '<span>Closed-end fund discounts</span><span class="c">1</span>' in h
    r = (target / "research" / "index.html").read_text()
    assert r.count('class="row slim timed"') == 6 and "team-atrium" not in r and "How a result is tested" in r


def test_every_page_photo_not_taken_by_quantt_is_credited_in_the_footer(snap, tmp_path, content):
    """Team lead, 2026-11-24: take the credit off the photographs. CC BY-SA still requires one, so every
    page's footer names each photograph's author and licence."""
    from dashboard import layout as L
    target = build(snap, tmp_path / "site", content)
    for page_name, key in (("team", "team"), ("library", "library"), ("research", "research"), ("contact", "contact")):
        h = (target / page_name / "index.html").read_text()
        photo = L.PHOTOS[key]
        assert photo in L.PHOTO_CREDITS, photo
        assert 'class="credit"' not in h and "Photograph:" not in h, page_name
        foot = h.split('class="foot-credits"', 1)[1].split("</p>", 1)[0]
        for who, lic, url in L.PHOTO_CREDITS.values():
            assert f"{who}</a> ({lic})" in foot and url in foot, (page_name, who)


def test_the_pages_hash_the_stylesheet_the_build_serves(snap, tmp_path, content):
    """Release-check review, 2026-11-24: the hash came from the source while the build copied the files
    after rendering, so a release checked out mid-build could pair the old hash with the new CSS."""
    import hashlib
    target = build(snap, tmp_path / "site", content)
    h = hashlib.sha256((target / "static" / "site.css").read_bytes() + (target / "static" / "site.js").read_bytes())
    assert f'site.css?v={h.hexdigest()[:12]}"' in (target / "index.html").read_text()


def test_books_trading_counts_books_that_sent_an_order(snap, tmp_path, content, monkeypatch):
    """Release-check review, 2026-11-24: a dry-run book counted as trading; an unreadable one vanished."""
    monkeypatch.setattr(SITE, "RESEARCH_UNDER_CONSTRUCTION", False)
    assert SITE.books_trading(snap) == (3, 0)
    ev = next(b for b in snap["books"] if b["name"] == "events")
    ev["start"] = {"absent": "no session has sent an order yet"}
    assert SITE.books_trading(snap) == (2, 0)
    ev["start"] = {"UNMEASURED": "STARTED unreadable"}
    h = (build(snap, tmp_path / "site", content) / "research" / "index.html").read_text()
    assert ">2<" in h and "(1 not read tonight)" in h


def test_with_every_book_unreadable_the_page_says_why(snap, tmp_path, content):
    for b in snap["books"]:
        b["official"] = {"UNMEASURED": "unreadable"}
        b["after_close"] = {"UNMEASURED": "unreadable"}
    h = (build(snap, tmp_path / "site", content) / "performance" / "index.html").read_text()
    assert "No book has a traded session" not in h and "Not included: Fixed Income Book (its official history could not be read)" in h
    assert "First figures after the close" not in h and "Key figures" not in h


def test_the_team_page_shows_the_people_then_the_pod_and_its_books(snap, tmp_path, content):
    """Team lead, 2026-11-24: "a brief overview of the multi strategy pod we are running"; then "it should be
    the team pictures first then the pod description (which needs to be organized better)"."""
    home = (build(snap, tmp_path / "site", content) / "index.html").read_text()
    assert home.index('class="people"') < home.index("A multi-strategy pod")
    pod = home.split("A multi-strategy pod", 1)[1].split("</section>", 1)[0]
    assert pod.count('class="pod-card"') == 3 and "<h4>" not in pod and "Reconciled daily" not in pod
    for title in ("Fixed Income Book", "Equity Cross-Asset Book", "Event Book"):
        assert title in pod, title


def test_the_event_books_strategy_count_comes_from_its_record(snap, tmp_path, content):
    """Release-check review of b76a7f4: "Eight strategies" was written into the text."""
    n = SITE.event_strategies(snap)
    home = (build(snap, tmp_path / "site", content) / "index.html").read_text()
    assert f"{n} strategies around scheduled corporate events" in home and "Eight strategies" not in home
    ev = next(b for b in snap["books"] if b["name"] == "events")
    ev["sleeves"] = {"UNMEASURED": "sleeve_scores.csv: unreadable"}
    home = (build(snap, tmp_path / "site2", content) / "index.html").read_text()
    assert "Strategies around scheduled corporate events" in home


def test_the_research_page_is_under_construction(snap, tmp_path, content):
    """Team lead, 2026-11-24: "make the research tab under construction right now"."""
    target = build(snap, tmp_path / "site", content)
    r = (target / "research" / "index.html").read_text()
    assert "Under construction." in r and "This page is being rebuilt." in r and "How a result is tested" not in r
    nav = (target / "index.html").read_text().split('<nav class="nav"', 1)[1].split("</nav>", 1)[0]
    assert 'href="/research/"' in nav
