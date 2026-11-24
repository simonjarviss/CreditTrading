"""Server-side SVG charts for the site. Standard library only; the page needs no chart library.

Two chart forms. A line chart over trading sessions, one line per book and one for the
accounts combined, in dollars or in percent (growth since inception, drawdown from the peak).
A bar chart of each session's P&L in dollars, coloured by sign. One y-axis per chart, always. The x-axis is the session index, so weekends and holidays leave no gaps. A
session a book has no official row for is a break in that book's line, never a value
carried from the session before. The hover layer (static/site.js) reads the same numbers
from the container's data-series attribute; with scripts off, the chart and its table
still read correctly.
"""
from __future__ import annotations

import json
import math
from html import escape

W, H = 960, 340
PAD_L, PAD_R, PAD_T, PAD_B = 72, 16, 16, 36
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def nice_ticks(lo: float, hi: float, n: int = 5) -> list:
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 0.5:
        ticks.append(round(t, 10))
        t += step
    return ticks


def usd_axis(v: float) -> str:
    if v == 0:
        return "$0"
    a = abs(v)
    s = f"${a / 1000:,.1f}k" if a >= 1000 else f"${a:,.0f}"
    return ("−" if v < 0 else "") + s.replace(".0k", "k")


def pct_axis(v: float) -> str:
    """A percent tick with the decimals it needs: +2%, −0.5%, −12.5% (release-check review,
    2026-11-24: rounding to a fixed precision printed the −12.5% gridline as −12%)."""
    if v == 0:
        return "0%"
    s = f"{abs(v) * 100:.2f}".rstrip("0").rstrip(".")
    return ("−" if v < 0 else "+") + s + "%"


AXIS = {"usd": usd_axis, "pct": pct_axis}


def _month_labels(dates: list, x, height: int) -> list:
    out, seen, last_x = [], None, -1e9
    for i, d in enumerate(dates):            # one label at each month's first session, if it has room
        if d[:7] != seen and x(i) - last_x >= 70:
            seen, last_x = d[:7], x(i)
            out.append(f'<text class="axis" x="{x(i):.1f}" y="{height - 10}" text-anchor="middle">'
                       f'{MONTHS[int(d[5:7]) - 1]} {d[:4]}</text>')
    return out


def bar_chart(points: list, label: str, height: int = 240) -> str:
    """points: [(date, dollars)]. One bar per session, green up and red down, on one dollar axis."""
    if not points:
        return '<p class="meta">No session yet.</p>'
    h = height
    dates = [d for d, _ in points]
    vals = [v for _, v in points]
    ticks = nice_ticks(min(min(vals), 0.0), max(max(vals), 0.0), 4)
    lo, hi = ticks[0], ticks[-1]
    n = len(points)
    slot = (W - PAD_L - PAD_R) / n
    bw = max(1.5, min(18.0, slot * 0.6))
    x = lambda i: PAD_L + slot * (i + 0.5)                                    # noqa: E731
    y = lambda v: PAD_T + (h - PAD_T - PAD_B) * (hi - v) / (hi - lo)          # noqa: E731
    parts = [f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="{escape(label)}">']
    for t in ticks:
        cls = "zero" if t == 0 else "grid-line"
        parts.append(f'<line class="{cls}" x1="{PAD_L}" x2="{W - PAD_R}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>')
        parts.append(f'<text class="axis" x="{PAD_L - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{usd_axis(t)}</text>')
    parts += _month_labels(dates, x, h)
    for i, v in enumerate(vals):
        top, bot = (y(v), y(0)) if v >= 0 else (y(0), y(v))
        parts.append(f'<rect class="{"bar-pos" if v >= 0 else "bar-neg"}" x="{x(i) - bw / 2:.1f}" y="{top:.1f}" '
                     f'width="{bw:.1f}" height="{max(bot - top, 0.8):.1f}" rx="2"/>')
    parts.append(f'<line class="hair" x1="0" x2="0" y1="{PAD_T}" y2="{h - PAD_B}"/>')
    parts.append("</svg>")
    data = {"x": [round(x(i), 1) for i in range(n)], "dates": dates, "fmt": "usd",
            "series": [{"name": "Portfolio P&L", "color": "#5f6670", "v": [round(v, 2) for v in vals]}]}
    return (f'<div class="chart" data-series="{escape(json.dumps(data, separators=(",", ":")))}">'
            + "".join(parts) + '<div class="tip"></div></div>')


# A horizontal bar chart has its own, narrower canvas: it sits two to a row, and text drawn on the
# 960-wide canvas would shrink to half size there.
HB_W, HB_LEFT, HB_RIGHT, HB_ROW = 560, 168, 150, 38


def hbar_chart(rows: list, label: str) -> str:
    """rows: [(name, colour, [(value, opacity)], text)]: one row per book, each value a bar drawn from a
    shared zero (a negative one to the left), and `text` its figures, right-aligned in their own column
    so a long bar never runs into them. Category names are on the left; no legend is needed."""
    if not rows:
        return '<p class="meta">Not measured.</p>'
    vals = [v for _, _, segs, _ in rows for v, _ in segs] + [0.0]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi = lo + 1.0
    x0, x1 = HB_LEFT, HB_W - HB_RIGHT
    x = lambda v: x0 + (x1 - x0) * (v - lo) / (hi - lo)                        # noqa: E731
    h = len(rows) * HB_ROW + 8
    parts = [f'<svg viewBox="0 0 {HB_W} {h}" role="img" aria-label="{escape(label)}">',
             f'<line class="zero" x1="{x(0):.1f}" x2="{x(0):.1f}" y1="2" y2="{h - 2}"/>']
    for i, (name, colour, segs, text) in enumerate(rows):
        yc = 4 + i * HB_ROW + HB_ROW / 2
        parts.append(f'<text class="cat" x="{x0 - 12}" y="{yc + 4:.1f}" text-anchor="end">{escape(name)}</text>')
        for v, op in segs:
            a, b = sorted((x(0), x(v)))
            parts.append(f'<rect x="{a:.1f}" y="{yc - 7:.1f}" width="{max(b - a, 1.0):.1f}" height="14" rx="2" '
                         f'fill="{colour}" fill-opacity="{op}"><title>{escape(name)}: {escape(text)}</title></rect>')
        parts.append(f'<text class="val" x="{HB_W - 4}" y="{yc + 4:.1f}" text-anchor="end">{escape(text)}</text>')
    parts.append("</svg>")
    return '<div class="chart hbar">' + "".join(parts) + "</div>"


def line_chart(series: list, label: str, fmt: str = "usd", height: int = H) -> str:
    """series: [{"name", "color" (a CSS colour or var), "points": [(date, value)]}]; fmt "usd" or
    "pct" (values as fractions). Returns the chart's HTML (container, SVG, legend, hover data)."""
    axis = AXIS[fmt]
    dates = sorted({d for s in series for d, _ in s["points"]})
    if len(dates) < 2:
        return '<p class="meta">The chart needs at least two sessions.</p>'
    idx = {d: i for i, d in enumerate(dates)}
    vals = [v for s in series for _, v in s["points"]]
    ticks = nice_ticks(min(min(vals), 0.0), max(max(vals), 0.0))
    lo, hi = ticks[0], ticks[-1]
    x = lambda i: PAD_L + (W - PAD_L - PAD_R) * i / (len(dates) - 1)          # noqa: E731
    y = lambda v: PAD_T + (height - PAD_T - PAD_B) * (hi - v) / (hi - lo)          # noqa: E731
    parts = [f'<svg viewBox="0 0 {W} {height}" role="img" aria-label="{escape(label)}">']
    for t in ticks:
        cls = "zero" if t == 0 else "grid-line"
        parts.append(f'<line class="{cls}" x1="{PAD_L}" x2="{W - PAD_R}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>')
        parts.append(f'<text class="axis" x="{PAD_L - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{axis(t)}</text>')
    parts += _month_labels(dates, x, height)
    hover = []
    for s in series:
        pts = dict(s["points"])
        segs, cur = [], []
        for d in dates:
            if d in pts:
                cur.append(f"{x(idx[d]):.1f},{y(pts[d]):.1f}")
            elif cur:
                segs.append(cur)
                cur = []
        if cur:
            segs.append(cur)
        width = ' style="stroke-width:2.5"' if s.get("bold") else ""
        cls = f' {s["cls"]}' if s.get("cls") else ""
        for seg in segs:
            if len(seg) == 1:
                cx, cy = seg[0].split(",")
                parts.append(f'<circle class="dot-pt{cls}" cx="{cx}" cy="{cy}" r="4" fill="{s["color"]}"/>')
            else:
                parts.append(f'<polyline class="series{cls}" stroke="{s["color"]}"{width} points="{" ".join(seg)}"/>')
        hover.append({"name": s["name"], "color": s["color"], "cls": s.get("cls", ""),
                      "v": [round(pts[d], 6 if fmt == "pct" else 2) if d in pts else None for d in dates]})
    parts.append(f'<line class="hair" x1="0" x2="0" y1="{PAD_T}" y2="{height - PAD_B}"/>')
    parts.append("</svg>")
    data = {"x": [round(x(i), 1) for i in range(len(dates))], "dates": dates, "fmt": fmt, "series": hover}
    legend = "".join(f'<span class="{s.get("cls", "")}"><span class="sw" style="background:{s["color"]}"></span>'
                     f'{escape(s["name"])}</span>' for s in series)
    view = ' data-view="portfolio"' if any(s.get("cls") for s in series) else ""
    return (f'<div class="chart"{view} data-series="{escape(json.dumps(data, separators=(",", ":")))}">'
            + "".join(parts) + '<div class="tip"></div></div>'
            + (f'<div class="legend"{view}>{legend}</div>' if len(series) > 1 else ""))
