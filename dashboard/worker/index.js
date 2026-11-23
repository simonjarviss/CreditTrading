// The public site's Cloudflare Worker, `quantt-event-driven` (event-driven.quantt.ca).
//
// WHY (team lead, 2026-11-23): the site's front end deploys from this repository's `main` through
// Cloudflare Workers Builds (`npx wrangler deploy` at the repository root, wrangler.jsonc). The
// live pages cannot be built here: they come from the trading records, which live on the VM and
// never enter the repository (docs/SYSTEM.md §5, "the public site": snapshots stay on the VM).
//
// So the work is split:
//   /static/*, /robots.txt   served by Cloudflare from dashboard/public in `main` (styles, script,
//                            slides, font, the deck PDF);
//   every page               fetched from the VM, which rebuilds the pages from the records every
//                            30 minutes (dashboard/site.py), and cached here for 60 seconds.
//
// The VM's address is the Worker variable ORIGIN, set in the Cloudflare dashboard, never in this
// repository (CLAUDE.md, "Where it runs"); wrangler.jsonc sets keep_vars so a deploy keeps it.
// READ ONLY: GET and HEAD only, no cookies or query strings forwarded, nothing written.
// If the VM cannot be reached the visitor gets a plain 503 page saying so; never a stale page
// presented as current.

const CACHE_SECONDS = 60;
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
  const body = `<!doctype html><html lang="en-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Event Driven Trading</title><link rel="stylesheet" href="/static/site.css"></head><body><section class="page-head"><div class="wrap"><div class="eyebrow">Event Driven Trading</div><h1>Temporarily unavailable</h1><p class="lede">The live pages could not be reached. Please try again in a few minutes.</p></div></section></body></html>`;
  return new Response(body, {
    status: 503,
    headers: withSecurity({ "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "Retry-After": "120", "X-Unavailable": why }),
  });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/static/") || url.pathname === "/robots.txt") {
      const r = await env.ASSETS.fetch(request);
      const h = withSecurity(r.headers);
      h.set("Cache-Control", "public, max-age=3600");
      return new Response(r.body, { status: r.status, headers: h });
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", { status: 405, headers: withSecurity({ Allow: "GET, HEAD" }) });
    }
    if (!env.ORIGIN) return unavailable("origin not configured");

    const key = new Request(url.origin + url.pathname, { method: "GET" });
    const cache = caches.default;
    const hit = await cache.match(key);
    if (hit) return hit;

    let upstream;
    try {
      upstream = await fetch(new URL(url.pathname, env.ORIGIN).toString(), {
        method: "GET",
        redirect: "manual",
        headers: { "User-Agent": "quantt-event-driven-worker", Accept: "text/html" },
      });
    } catch (e) {
      return unavailable("origin unreachable");
    }
    if (upstream.status >= 500) return unavailable(`origin ${upstream.status}`);

    const h = withSecurity(upstream.headers);
    const loc = h.get("Location");
    if (loc) {                                   // the origin's redirects (e.g. /performance -> /performance/) stay on this host
      const l = new URL(loc, env.ORIGIN);
      h.set("Location", url.origin + l.pathname + l.search);
    }
    h.set("Cache-Control", upstream.status === 200 ? `public, max-age=${CACHE_SECONDS}` : "no-store");
    const resp = new Response(upstream.body, { status: upstream.status, headers: h });
    if (upstream.status === 200) ctx.waitUntil(cache.put(key, resp.clone()));
    return resp;
  },
};
