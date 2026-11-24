"""The Cloudflare Worker's config: what Workers Builds deploys from `main` (build root `dashboard`)."""
import json
import re
from pathlib import Path

import pytest

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


def test_the_workers_behaviour_under_node():
    """dashboard/worker/behaviour_test.mjs: edge caching, browsers sent no-cache with 304 revalidation
    (the zone's 4-hour Browser Cache TTL replaced max-age, 2026-11-24), redirects kept on the host,
    405 for writes, the host never chosen by the path. Node runs it with a stub cache and origin."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: run `node dashboard/worker/behaviour_test.mjs` where it is")
    r = subprocess.run([node, str(DASH / "worker" / "behaviour_test.mjs")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "FAIL" not in r.stdout, r.stdout + r.stderr
    assert r.stdout.count("PASS") >= 16, r.stdout
