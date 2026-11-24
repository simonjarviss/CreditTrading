"""A session that carries the Alpaca keys never follows a redirect, so the keys never
reach a second host. Security review, 2026-11-10 (`quantt.broker.alpaca.refuse_redirects`).

HOW THIS IS TESTED WITHOUT A SOCKET. The root conftest blocks every connection, so two
loopback servers are not available. Instead a real `requests.Session` gets a recording
TRANSPORT ADAPTER in place of the network: host A answers with a 3xx whose `Location`
names host B, and the adapter records every request each host is sent, headers included.
The redirect logic that runs is `requests`' own. The first test shows the hazard itself
(an unprotected session DOES hand both key headers to host B), so that the others are
known to be testing something.
"""
import pytest
import requests
from requests.adapters import BaseAdapter

from quantt.broker import alpaca, alpaca_probe
from quantt.broker.alpaca import AlpacaClient, AlpacaHTTPError, AmbiguousSubmit, PAPER_BASE

KEY, SECRET = "FAKEKEYID0000000000", "FAKESECRETVALUE000000000000000000000000"
EVIL = "https://collector.example"
REDIRECTS = (301, 302, 303, 307, 308)


class Recording(BaseAdapter):
    """Every URL under PAPER_BASE answers `status` with Location -> EVIL; EVIL answers 200."""

    def __init__(self, status):
        super().__init__()
        self.status, self.seen = status, []

    def send(self, request, **kw):
        self.seen.append((request.method, request.url, dict(request.headers)))
        r = requests.Response()
        r.request, r.url, r._content, r._content_consumed = request, request.url, b"{}", True
        if request.url.startswith(PAPER_BASE):
            r.status_code = self.status
            r.headers["Location"] = EVIL + "/stolen" + request.path_url
        else:
            r.status_code = 200
        return r

    def close(self):
        pass

    def to_evil(self):
        return [s for s in self.seen if s[1].startswith(EVIL)]


def _session(status, protect):
    s = requests.Session()
    ad = Recording(status)
    s.mount("https://", ad)
    s.headers.update({"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET})
    if protect:
        alpaca.refuse_redirects(s)
    return s, ad


@pytest.fixture
def env_file(tmp_path):
    p = tmp_path / "keys.env"
    p.write_text(f"ALPACA_CEF_KEY_ID={KEY}\nALPACA_CEF_SECRET_KEY={SECRET}\n")
    return p


@pytest.mark.parametrize("status", REDIRECTS)
def test_the_hazard_is_real_an_unprotected_session_sends_both_keys_to_the_other_host(status):
    s, ad = _session(status, protect=False)
    s.get(PAPER_BASE + "/v2/calendar", timeout=5)
    leaked = ad.to_evil()
    assert len(leaked) == 1
    assert leaked[0][2].get("APCA-API-KEY-ID") == KEY and leaked[0][2].get("APCA-API-SECRET-KEY") == SECRET


@pytest.mark.parametrize("status", REDIRECTS)
def test_the_client_get_raises_on_a_redirect_and_the_other_host_receives_nothing(env_file, status):
    s, ad = _session(status, protect=False)                 # the client must protect it itself
    c = AlpacaClient("cef", env_file, session=s, sleep=lambda _: None)
    with pytest.raises(AlpacaHTTPError, match=f"HTTP {status}: a redirect, NOT followed") as e:
        c._get(PAPER_BASE, "/v2/calendar")
    assert e.value.status == status
    assert ad.to_evil() == [] and len(ad.seen) == 1          # one request, to Alpaca, not retried
    assert KEY not in str(e.value) and SECRET not in str(e.value) and EVIL not in str(e.value)


@pytest.mark.parametrize("status", REDIRECTS)
def test_the_order_post_on_a_redirect_is_ambiguous_and_the_other_host_receives_nothing(env_file, status):
    s, ad = _session(status, protect=False)
    c = AlpacaClient("cef", env_file, session=s, sleep=lambda _: None)
    with pytest.raises(AmbiguousSubmit, match="NOT followed") as e:
        c.submit_order("PDI", 10, "buy", "cef-20261110-PDI-1", time_in_force="day")
    assert ad.to_evil() == [] and [m for m, _, _ in ad.seen] == ["POST"]
    assert e.value.client_order_id == "cef-20261110-PDI-1" and "do NOT resend" in str(e.value)


@pytest.mark.parametrize("status", REDIRECTS)
def test_a_call_that_forgets_the_flag_still_cannot_follow(env_file, status):
    """The second layer: a script that borrows `client._session` and calls it bare."""
    s, ad = _session(status, protect=False)
    c = AlpacaClient("cef", env_file, session=s, sleep=lambda _: None)
    with pytest.raises(requests.TooManyRedirects):
        c._session.get(PAPER_BASE + "/v2/assets", timeout=5)
    assert ad.to_evil() == []


@pytest.mark.parametrize("status", REDIRECTS)
def test_the_probe_get_raises_on_a_redirect_and_the_other_host_receives_nothing(status):
    s, ad = _session(status, protect=False)
    with pytest.raises(RuntimeError, match=f"HTTP {status}"):
        alpaca_probe._get(s, "/v2/account")
    assert ad.to_evil() == []


def test_the_probes_own_session_cannot_follow_a_redirect():
    assert alpaca_probe._session(KEY, SECRET).max_redirects == 0


def test_every_client_call_passes_allow_redirects_false(env_file):
    """Read from source: a new HTTP call in either module without the flag fails here."""
    import ast
    import inspect
    for mod in (alpaca, alpaca_probe):
        tree = ast.parse(inspect.getsource(mod))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr in ("get", "post", "put", "patch", "delete", "request")
                 and any(k.arg == "timeout" for k in n.keywords)]
        assert calls, mod.__name__
        for n in calls:
            flags = [k.value.value for k in n.keywords if k.arg == "allow_redirects"]
            assert flags == [False], f"{mod.__name__} line {n.lineno}: an HTTP call without allow_redirects=False"
