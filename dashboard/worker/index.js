// The public site's Cloudflare Worker, `quantt-event-driven` (event-driven.quantt.ca).
//
// WHY (team lead, 2026-11-23): the site's address is event-driven.quantt.ca, served by this Worker,
// which Cloudflare Workers Builds deploys from `main` (`npx wrangler deploy`, build root directory
// `dashboard`, dashboard/wrangler.jsonc). The site itself is built on the VM from the trading records,
// every 30 minutes, by the site clone at its release tag (dashboard/site.py); the records never enter
// the repository (docs/SYSTEM.md §5, "the public site").
//
// So this Worker is a read-only caching proxy to the VM: every path, pages and /static/* alike, so a
// page and its styles always come from the same site release. Pages are cached at the edge for 60
// seconds, static files for an hour.
//
// The VM's address is the Worker variable ORIGIN (an http(s) URL), set in the Cloudflare dashboard,
// never in this repository (CLAUDE.md, "Where it runs"); wrangler.jsonc sets keep_vars so a deploy
// keeps it. GET and HEAD only; no cookies or query strings are forwarded; nothing is written. If the
// VM cannot be reached, the visitor gets a plain 503 page saying so, never a stale page as current.

const PAGE_SECONDS = 60;
const STATIC_SECONDS = 3600;
const SECURITY_HEADERS = {
  "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Strict-Transport-Security": "max-age=31536000",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

function withSecurity(headers) {
  const h = new Headers(headers);
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) h.set(k, v);
  h.delete("Server");
  h.delete("Set-Cookie");
  return h;
}

function unavailable(why) {
  // Self-contained (no stylesheet): when the VM is down its styles are too.
  const body = '<!doctype html><html lang="en-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Event Driven Trading</title></head>'
    + '<body style="margin:0;font-family:Helvetica,Arial,sans-serif;background:#0b1a33;color:#fff;min-height:100vh;display:grid;place-items:center">'
    + '<div style="max-width:560px;padding:32px"><p style="letter-spacing:.14em;text-transform:uppercase;font-size:12px;color:#a9c0e3">Event Driven Trading</p>'
    + '<h1 style="font-weight:600;font-size:36px;margin:0 0 12px">Temporarily unavailable</h1>'
    + '<p style="color:rgba(255,255,255,.8);line-height:1.6">The live pages could not be reached. Please try again in a few minutes.</p></div></body></html>';
  return new Response(body, {
    status: 503,
    headers: withSecurity({ "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "Retry-After": "120", "X-Unavailable": why }),
  });
}

function originOf(env) {
  // ORIGIN's scheme and host only; null unless it is an http(s) URL (the visitor then gets the 503 page).
  if (!env.ORIGIN) return null;
  try {
    const u = new URL(env.ORIGIN);
    return (u.protocol === "https:" || u.protocol === "http:") ? u.origin : null;
  } catch (e) {
    return null;
  }
}

function targetOn(origin, pathname) {
  // The target's host is ORIGIN's, always: only the path is set, through the pathname setter, which
  // cannot change the host. (Resolving the path against ORIGIN would let "//other.host/x" pick the host.)
  const t = new URL(origin);
  t.pathname = pathname;
  return t;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", { status: 405, headers: withSecurity({ Allow: "GET, HEAD" }) });
    }
    const origin = originOf(env);
    if (!origin) return unavailable(env.ORIGIN ? "origin is not an http(s) URL" : "origin not configured");

    const isStatic = url.pathname.startsWith("/static/");
    const key = new Request(url.origin + url.pathname, { method: "GET" });
    const cache = caches.default;
    const hit = await cache.match(key);
    if (hit) return hit;

    const target = targetOn(origin, url.pathname);
    let upstream;
    try {
      upstream = await fetch(target.toString(), {
        method: "GET",
        redirect: "manual",
        headers: { "User-Agent": "quantt-event-driven-worker" },
      });
    } catch (e) {
      return unavailable("origin unreachable");
    }
    if (upstream.status >= 500) return unavailable(`origin ${upstream.status}`);

    const h = withSecurity(upstream.headers);
    const loc = h.get("Location");
    if (loc) {                                   // the origin's redirects (e.g. /performance -> /performance/) stay on this host
      const l = new URL(loc, target);
      if (l.origin !== target.origin) return unavailable("origin redirected off-site");
      h.set("Location", url.origin + l.pathname);
    }
    const ok = upstream.status === 200;
    h.set("Cache-Control", ok ? `public, max-age=${isStatic ? STATIC_SECONDS : PAGE_SECONDS}` : "no-store");
    const resp = new Response(upstream.body, { status: upstream.status, headers: h });
    if (ok) ctx.waitUntil(cache.put(key, resp.clone()));
    return resp;
  },
};
