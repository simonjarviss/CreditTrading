// Event Driven Trading: the only script on the site. One job, read-only and local: the chart
// hover (a crosshair that snaps to the nearest session, with a tooltip). It fetches nothing.
(function () {
  "use strict";

  function fmtPct(v) {
    var s = Math.abs(v * 100).toFixed(2) + "%";
    return (v > 0 ? "+" : v < 0 ? "−" : "") + s;
  }

  function fmtUsd(v) {
    var s = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    return (v > 0 ? "+$" : v < 0 ? "−$" : "$") + s;
  }

  document.querySelectorAll(".chart[data-series]").forEach(function (box) {
    var svg = box.querySelector("svg");
    var tip = box.querySelector(".tip");
    var hair = box.querySelector(".hair");
    var data;
    try { data = JSON.parse(box.getAttribute("data-series")); } catch (e) { return; }
    var xs = data.x; // pixel x of each date in viewBox units
    function show(evt) {
      var pt = svg.createSVGPoint();
      pt.x = evt.clientX; pt.y = evt.clientY;
      var loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      var best = 0, bd = Infinity;
      for (var i = 0; i < xs.length; i++) {
        var d = Math.abs(xs[i] - loc.x);
        if (d < bd) { bd = d; best = i; }
      }
      hair.setAttribute("x1", xs[best]); hair.setAttribute("x2", xs[best]);
      hair.style.visibility = "visible";
      var html = "<b>" + data.dates[best] + "</b>";
      data.series.forEach(function (s) {
        var v = s.v[best];
        html += "<div><span class=\"sw\" style=\"background:" + s.color + "\"></span>" + s.name + ": " +
          (v === null ? "no row" : (data.fmt === "pct" ? fmtPct(v) : fmtUsd(v))) + "</div>";
      });
      tip.innerHTML = html;
      tip.style.visibility = "visible";
      var r = box.getBoundingClientRect();
      var left = evt.clientX - r.left + 14;
      if (left + tip.offsetWidth > r.width) left = evt.clientX - r.left - tip.offsetWidth - 14;
      tip.style.left = Math.max(0, left) + "px";
      tip.style.top = Math.max(0, evt.clientY - r.top - tip.offsetHeight - 10) + "px";
    }
    function hide() { hair.style.visibility = "hidden"; tip.style.visibility = "hidden"; }
    svg.addEventListener("pointermove", show);
    svg.addEventListener("pointerleave", hide);
  });
})();
