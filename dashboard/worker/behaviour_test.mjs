// The Worker's behaviour, run under Node with a stub cache and a stub origin (no network):
//   node dashboard/worker/behaviour_test.mjs [path to index.js]
// dashboard/tests/test_worker.py runs it. Exit 1 on any FAIL.
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const store = new Map();
globalThis.caches = { default: { match: async (k) => store.get(k.url)?.clone(), put: async (k, r) => { store.set(k.url, r); } } };
let calls = [];
globalThis.fetch = async (u) => {
  calls.push(u);
  const p = new URL(u).pathname;
  if (p === "/performance") return new Response("", { status: 308, headers: { Location: "https://origin.example/performance/" } });
  if (p === "/missing/") return new Response("nf", { status: 404, headers: { "Content-Type": "text/html" } });
  return new Response("<html>" + p + "</html>", { status: 200, headers: { "Content-Type": "text/html", ETag: '"abc123"', "Last-Modified": "Tue, 24 Nov 2026 04:20:00 GMT", Server: "Caddy" } });
};
const target = process.argv[2] ? pathToFileURL(resolve(process.argv[2])).href : new URL("./index.js", import.meta.url).href;
const W = (await import(target)).default;
const env = { ORIGIN: "https://origin.example" };
const waits = []; const ctx = { waitUntil: (p) => waits.push(p) };
const go = async (path, headers = {}, method = "GET") => { const r = await W.fetch(new Request("https://event-driven.quantt.ca" + path, { method, headers }), env, ctx); await Promise.all(waits); return r; };
const ok = (name, cond) => { console.log((cond ? "PASS " : "FAIL ") + name); if (!cond) process.exitCode = 1; };
let r = await go("/");
ok("first page 200, browser no-cache", r.status === 200 && r.headers.get("Cache-Control") === "no-cache" && (await r.text()) === "<html>/</html>");
ok("edge copy keeps 60 s", store.get("https://event-driven.quantt.ca/").headers.get("Cache-Control") === "public, max-age=60");
r = await go("/");
ok("second page from the edge, still no-cache", r.status === 200 && calls.length === 1 && r.headers.get("Cache-Control") === "no-cache");
r = await go("/", { "If-None-Match": '"abc123"' });
ok("matching ETag -> 304, no body", r.status === 304 && (await r.text()) === "" && r.headers.get("ETag") === '"abc123"');
r = await go("/", { "If-None-Match": 'W/"abc123"' });
ok("weak match -> 304", r.status === 304);
r = await go("/", { "If-None-Match": '"zzz"' });
ok("other ETag -> 200", r.status === 200 && (await r.text()) === "<html>/</html>");
r = await go("/", { "If-None-Match": '"zzz"', "If-Modified-Since": "Wed, 25 Nov 2026 00:00:00 GMT" });
ok("If-None-Match wins over If-Modified-Since", r.status === 200);
r = await go("/", { "If-Modified-Since": "Tue, 24 Nov 2026 04:20:00 GMT" });
ok("not modified since -> 304", r.status === 304);
r = await go("/", { "If-Modified-Since": "Tue, 24 Nov 2026 04:19:59 GMT" });
ok("modified since -> 200", r.status === 200);
r = await go("/static/site.css");
ok("static 200 no-cache; edge 1 h", r.status === 200 && r.headers.get("Cache-Control") === "no-cache" && store.get("https://event-driven.quantt.ca/static/site.css").headers.get("Cache-Control") === "public, max-age=3600");
r = await go("/missing/");
ok("404 no-store, not cached", r.status === 404 && r.headers.get("Cache-Control") === "no-store" && !store.has("https://event-driven.quantt.ca/missing/"));
r = await go("/performance");
ok("redirect stays on host", r.status === 308 && r.headers.get("Location") === "https://event-driven.quantt.ca/performance/");
r = await go("/", {}, "HEAD");
ok("HEAD 200 without body", r.status === 200 && (await r.text()) === "");
r = await go("/", {}, "POST");
ok("POST refused", r.status === 405);
ok("security headers on a 304", (await go("/", { "If-None-Match": '"abc123"' })).headers.get("Content-Security-Policy") !== null);
calls = []; r = await go("//evil.com/x");
ok("host cannot be changed", calls.length === 0 || new URL(calls[0]).host === "origin.example");
