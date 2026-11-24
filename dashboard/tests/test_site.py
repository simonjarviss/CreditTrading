"""The whole public site: every page built, every local link resolves, the disclaimer on every page,
the swap atomic, a dirty snapshot refused with nothing published."""
import datetime as dt
import json
import re
import shutil
from pathlib import Path

import pytest

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


@pytest.fixture
def snap():
    return json.loads(FIXTURE.read_text())


def build(snap, root, content, when=dt.datetime(2026, 11, 23, 23, 20, tzinfo=dt.timezone.utc)):
    return SITE.publish(snap, root, when, content=content)


def test_every_page_is_built_and_carries_the_disclaimer_and_contact(snap, tmp_path, content):
    target = build(snap, tmp_path / "site", content)
    pages = sorted(p.relative_to(target).as_posix() for p in target.rglob("*.html"))
    assert pages == ["404.html", "contact/index.html", "index.html", "library/index.html",
                     "performance/index.html", "research/index.html", "strategy/index.html", "team/index.html"]
    for p in pages:
        h = (target / p).read_text()
        assert "No client or outside capital is invested" in h, p
        assert "simon.jarvis@queensu.ca" in h, p


def test_every_local_link_and_asset_exists(snap, tmp_path, content):
    target = build(snap, tmp_path / "site", content)
    missing = []
    for page in target.rglob("*.html"):
        for ref in re.findall(r'(?:href|src)="(/[^"#]*)', page.read_text()):
            p = target / ref.lstrip("/")
            if not (p.is_file() or (p / "index.html").is_file()):
                missing.append((page.name, ref))
    assert not missing, missing


def test_the_slideshow_shows_every_kept_slide_and_the_pdf(snap, tmp_path, content):
    target = build(snap, tmp_path / "site", content)
    h = (target / "strategy" / "index.html").read_text()
    slides = json.loads((content / "slides.json").read_text())
    assert len(re.findall(r'class="thumbs"', h)) == 1
    assert h.count('data-title="') == len(slides) and f"Slide 1 of {len(slides)}" in h
    assert SITE.DECK_PDF in h


def test_the_team_page_lists_the_four_members_with_their_links(snap, tmp_path, content):
    h = (build(snap, tmp_path / "site", content) / "team" / "index.html").read_text()
    for name in ("Simon Jarvis", "Ryan Press", "James Simone", "Lucy Keith"):
        assert name in h
    assert h.count(">LinkedIn</a>") == 4


def test_the_library_links_each_source(snap, tmp_path, content):
    h = (build(snap, tmp_path / "site", content) / "library" / "index.html").read_text()
    assert "Investor Sentiment and the Closed-End Fund Puzzle" in h
    assert 'href="https://doi.org/10.1111/j.1540-6261.1991.tb03746.x"' in h


def test_a_missing_library_file_stops_the_build(snap, tmp_path, content):
    (content / "library.json").unlink()
    with pytest.raises(FileNotFoundError):
        build(snap, tmp_path / "site", content)
    assert not (tmp_path / "site" / "current").exists()


def test_the_overview_figures_come_from_the_snapshot(snap, tmp_path, content):
    h = (build(snap, tmp_path / "site", content) / "index.html").read_text()
    assert "Books trading" in h and ">3<" in h                         # three books with a session or history
    assert "Systematic strategies" in h                                # 2 core books + the event book's strategies
    assert "Paper results to date" in h                                # the live chart


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
    """What a release needs: slides for every caption, the deck, the font and the library."""
    slides = json.loads((DASH / "content" / "slides.json").read_text())
    for s in slides:
        assert (DASH / "public" / "static" / "slides" / f"slide-{s['n']:02d}.webp").is_file(), s
    assert (DASH / "public" / "static" / SITE.DECK_PDF).is_file()
    assert (DASH / "public" / "static" / "fonts" / "inter-latin-wght.woff2").is_file()
    lib = json.loads((DASH / "content" / "library.json").read_text())
    assert lib["entries"] and all(e["title"] and e["topic"] for e in lib["entries"])
    for e in lib["entries"]:
        for k in ("url", "oa_pdf_url"):
            assert e.get(k) is None or e[k].startswith("https://") or e[k].startswith("http://"), e


def test_the_worker_config_names_the_worker_and_no_address():
    """wrangler.jsonc is what Cloudflare Workers Builds deploys from `main`. It must name the Worker the
    team lead created, point at dashboard/public, keep the dashboard's ORIGIN variable across deploys,
    and carry no address of the VM (CLAUDE.md, "Where it runs")."""
    root = DASH.parent
    text = (root / "wrangler.jsonc").read_text()
    body = json.loads("\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//")))
    assert body["name"] == "quantt-event-driven"
    assert (root / body["main"]).is_file() and (root / body["assets"]["directory"] / "static" / "site.css").is_file()
    assert body["keep_vars"] is True and body["assets"]["run_worker_first"] is True
    worker = (root / body["main"]).read_text()
    for t in (text, worker):
        assert not re.search(r"cloudapp\.azure\.com|\b\d{1,3}(\.\d{1,3}){3}\b", t)
    assert "env.ORIGIN" in worker and 'request.method !== "GET"' in worker


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
    for needle in ("list-jobs", "1530", "1230", "quantt-*.d", "service.d"):
        assert needle in guard, needle
