"""The Cloudflare Worker's config: what Workers Builds deploys from `main` (build root `dashboard`)."""
import json
import re
from pathlib import Path

DASH = Path(__file__).resolve().parents[1]


def test_the_worker_config_names_the_worker_and_no_address():
    text = (DASH / "wrangler.jsonc").read_text()
    body = json.loads("\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//")))
    assert body["name"] == "quantt-event-driven"
    assert (DASH / body["main"]).is_file()
    assert body["keep_vars"] is True and body["workers_dev"] is False and body["preview_urls"] is False
    worker = (DASH / body["main"]).read_text()
    for t in (text, worker):
        assert not re.search(r"cloudapp\.azure\.com|\b\d{1,3}(\.\d{1,3}){3}\b", t)
    assert "env.ORIGIN" in worker and 'request.method !== "GET"' in worker and "t.pathname = pathname" in worker


def test_the_build_root_does_not_look_like_a_python_project():
    """At the repository root the build image pip-installed requirements.txt and failed (build 6d2786ba)."""
    assert not (DASH.parent / "wrangler.jsonc").exists()
    assert not any((DASH / n).exists() for n in ("requirements.txt", "pyproject.toml", "Pipfile", "package.json"))
