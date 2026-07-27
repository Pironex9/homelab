// Live status for the hero. Same-origin: Caddy proxies /api/* to Uptime
// Kuma on this host. Kuma's status-page JSON sends no CORS headers, which
// is why this page is served from the same host rather than from a CDN.
(function () {
  "use strict";

  // COUPLED to ../Caddyfile: the two /api/status-page/ routes there are pinned
  // to this exact slug rather than a wildcard, on purpose. Changing it in only
  // one of the two files makes both fetches 404, which hides the uptime block
  // permanently and leaves nothing behind but a console.warn. Change both.
  var SLUG = "statuspage1";
  var WINDOW_HOURS = "720h"; // 30 days. The status-page JSON only exposes 24h.
  var TIMEOUT_MS = 4000;

  // allSettled waits for every promise to settle, and a stalled fetch never
  // does. Without a deadline, one hung request from Kuma leaves the block
  // hidden forever even though the other values already arrived. Every
  // request therefore carries its own abort timer.
  function fetchWithTimeout(url) {
    var controller = new AbortController();
    var timer = setTimeout(function () {
      controller.abort();
    }, TIMEOUT_MS);
    return fetch(url, { signal: controller.signal }).then(
      function (r) {
        clearTimeout(timer);
        return r;
      },
      function (err) {
        clearTimeout(timer);
        throw err;
      }
    );
  }

  function getJSON(url) {
    return fetchWithTimeout(url).then(function (r) {
      if (!r.ok) throw new Error(url + " returned " + r.status);
      return r.json();
    });
  }

  // Kuma's badge endpoint returns SVG, not JSON. The value is text content,
  // e.g. ...textLength="430">99.93%</text>
  function getBadgeUptime(id) {
    return fetchWithTimeout("/api/badge/" + id + "/uptime/" + WINDOW_HOURS)
      .then(function (r) {
        if (!r.ok) throw new Error("badge " + id + " returned " + r.status);
        return r.text();
      })
      .then(function (svg) {
        // The badge draws the value twice: a dark shadow text, then the
        // visible fill text. Take the last match, which is the visible one.
        // A monitor that is not on the public status page renders "N/A"
        // instead of a percentage, and falls through to null.
        var matches = svg.match(/>([\d.]+)%</g);
        if (!matches || !matches.length) return null;
        var last = matches[matches.length - 1];
        return parseFloat(last.slice(1, -2));
      });
  }

  // Names are kept, not just ids. A row of coloured dots with no text is
  // meaningless to a screen reader and ambiguous to everyone else: nothing
  // says which dot is which service.
  function publicMonitors(page) {
    var monitors = [];
    (page.publicGroupList || []).forEach(function (group) {
      (group.monitorList || []).forEach(function (m) {
        monitors.push({ id: m.id, name: m.name });
      });
    });
    return monitors;
  }

  function renderDots(monitors, heartbeats) {
    var container = document.getElementById("service-dots");
    if (!container) return;
    container.textContent = "";

    var list = document.createElement("ul");
    list.className = "dots";

    monitors.forEach(function (m) {
      var beats = heartbeats[m.id] || [];
      var last = beats[beats.length - 1];
      // Kuma status: 1 = up, 3 = maintenance. Anything else is not up.
      var up = !!last && (last.status === 1 || last.status === 3);

      var item = document.createElement("li");
      item.className = "dot";
      item.dataset.status = up ? "up" : "down";
      // Carries the meaning in text, not only in colour. Read aloud by
      // screen readers, shown on hover, and survives a CSS failure.
      item.title = m.name + ": " + (up ? "up" : "down");

      var label = document.createElement("span");
      label.className = "visually-hidden";
      label.textContent = item.title;
      item.appendChild(label);

      list.appendChild(item);
    });

    container.appendChild(list);
  }

  getJSON("/api/status-page/" + SLUG)
    .then(function (page) {
      var monitors = publicMonitors(page);
      if (!monitors.length) throw new Error("status page lists no public monitors");

      var ids = monitors.map(function (m) {
        return m.id;
      });

      // allSettled throughout, never all. One badge returning 404 must not
      // cost the whole figure when twelve others answered, and losing the
      // heartbeat call must not cost the figure either. Only a total absence
      // of usable values hides the block.
      return Promise.allSettled([
        Promise.allSettled(ids.map(getBadgeUptime)),
        getJSON("/api/status-page/heartbeat/" + SLUG)
      ]).then(function (outer) {
        var values = (outer[0].value || [])
          .filter(function (r) {
            return (
              r.status === "fulfilled" &&
              typeof r.value === "number" &&
              !isNaN(r.value)
            );
          })
          .map(function (r) {
            return r.value;
          });

        if (!values.length) throw new Error("no badge returned a usable value");

        var mean =
          values.reduce(function (a, b) {
            return a + b;
          }, 0) / values.length;

        document.getElementById("uptime-figure").textContent = mean.toFixed(2) + "%";

        if (outer[1].status === "fulfilled") {
          renderDots(monitors, (outer[1].value || {}).heartbeatList || {});
        } else {
          console.warn("service dots unavailable:", outer[1].reason.message);
        }

        document.getElementById("uptime-block").removeAttribute("hidden");
      });
    })
    .catch(function (err) {
      // Deliberate: the block stays hidden. A portfolio page must never
      // show a fabricated or broken availability figure.
      console.warn("live status unavailable:", err.message);
    });
})();
