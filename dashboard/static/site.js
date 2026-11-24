// Event Driven Trading: the only script on the site. Two jobs, both read-only and local:
// the chart hover (a crosshair that snaps to the nearest session, with a tooltip), and the
// slide viewer (buttons, arrow keys, thumbnails, #slide-N links). It fetches nothing.
(function () {
  "use strict";

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
          (v === null ? "no row" : fmtUsd(v)) + "</div>";
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

  var deck = document.querySelector(".deck[data-count]");
  if (deck) {
    var img = deck.querySelector(".slide-frame img");
    var count = deck.querySelector(".deck-count");
    var prev = deck.querySelector("button.prev");
    var next = deck.querySelector("button.next");
    var thumbs = Array.prototype.slice.call(document.querySelectorAll(".thumbs a"));
    var n = thumbs.length, i = 0;
    function go(k, push) {
      i = Math.max(0, Math.min(n - 1, k));
      var a = thumbs[i];
      img.src = a.getAttribute("href");
      img.alt = a.getAttribute("data-title");
      count.textContent = "Slide " + (i + 1) + " of " + n + ": " + a.getAttribute("data-title");
      prev.disabled = i === 0; next.disabled = i === n - 1;
      thumbs.forEach(function (t, j) { t.setAttribute("aria-current", j === i ? "true" : "false"); });
      if (push) history.replaceState(null, "", "#slide-" + (i + 1));
    }
    prev.addEventListener("click", function () { go(i - 1, true); });
    next.addEventListener("click", function () { go(i + 1, true); });
    thumbs.forEach(function (t, j) {
      t.addEventListener("click", function (e) { e.preventDefault(); go(j, true); deck.scrollIntoView({ behavior: "smooth" }); });
    });
    document.addEventListener("keydown", function (e) {
      if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
      if (e.key === "ArrowRight") { go(i + 1, true); }
      if (e.key === "ArrowLeft") { go(i - 1, true); }
    });
    var m = /^#slide-(\d+)$/.exec(location.hash);
    go(m ? parseInt(m[1], 10) - 1 : 0, false);
  }
})();
