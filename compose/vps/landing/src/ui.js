// Two small progressive enhancements for the hero and the topology plate.
// Both are no-ops without JS: the page is complete and usable without this
// file, which is why it is deferred and why nothing here creates content.
//
// It lives in its own file rather than inline in index.html so the CSP in
// ../Caddyfile can refuse inline script outright. See the comment there.
(function () {
  "use strict";

  // --- Stack figure counts up once it scrolls into view --------------------
  // The real number is already in the markup, baked at build time, so a
  // browser without IntersectionObserver simply shows it.
  (function countUp() {
    var el = document.getElementById("stack-count");
    if (!el || !("IntersectionObserver" in window)) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    var target = parseInt(el.textContent, 10);
    if (!isFinite(target) || target < 2) return;

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        io.disconnect();
        var start = performance.now(), dur = 900;
        (function step(now) {
          var p = Math.min((now - start) / dur, 1);
          el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
          if (p < 1) requestAnimationFrame(step);
        })(start);
      });
    }, { threshold: 0.6 });
    io.observe(el);
  })();

  // --- The topology plate is only a tab stop while it actually scrolls -----
  // style.css gives the plate `overflow-x: auto` below 700px, where the
  // diagram holds its width and the reader pans. Above that it fits and
  // scrolls nowhere, so the tabindex in the markup would hand keyboard users
  // a focus stop that does nothing. The attribute stays in the HTML because
  // that is the correct default when this file never runs: a dead tab stop on
  // a wide screen is a smaller failure than an unreachable scroller on a
  // narrow one.
  (function panAffordance() {
    var plate = document.querySelector(".plate-scroll");
    if (!plate || !window.matchMedia) return;

    var narrow = window.matchMedia("(max-width: 700px)");

    function sync() {
      if (narrow.matches) {
        plate.setAttribute("tabindex", "0");
      } else {
        plate.removeAttribute("tabindex");
      }
    }

    sync();
    // addEventListener on a MediaQueryList is the modern form; Safari below
    // 14 only has addListener. Neither is worth a polyfill - if both are
    // missing the initial sync above has already run and is correct until
    // the viewport changes.
    if (narrow.addEventListener) {
      narrow.addEventListener("change", sync);
    } else if (narrow.addListener) {
      narrow.addListener(sync);
    }
  })();
})();
