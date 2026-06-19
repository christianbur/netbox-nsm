(function () {
  "use strict";

  // Client-side pager for the Object Report sample lists. The full (bounded)
  // set of stored samples is already rendered into the DOM; this only shows one
  // page of rows at a time. No server round-trips, scale-safe because the
  // stored sample set is capped server-side.

  function readInt(value, fallback) {
    var n = parseInt(value, 10);
    return isNaN(n) || n <= 0 ? fallback : n;
  }

  function orT(key, fallback) {
    var i18n = window.NSM_OR_I18N || {};
    if (i18n[key] != null && i18n[key] !== "") {
      return i18n[key];
    }
    return fallback != null ? fallback : key;
  }

  function orTf(key, params, fallback) {
    var text = orT(key, fallback);
    Object.keys(params).forEach(function (k) {
      text = text.split("%(" + k + ")s").join(String(params[k]));
    });
    return text;
  }

  function buildStatus(start, end, stored, total) {
    // start/end are 1-based inclusive bounds over the stored rows.
    if (total > stored) {
      return orTf(
        "%(start)s\u2013%(end)s of %(stored)s (of %(total)s total)",
        { start: start, end: end, stored: stored, total: total },
        "%(start)s\u2013%(end)s of %(stored)s (of %(total)s total)"
      );
    }
    return orTf(
      "%(start)s\u2013%(end)s of %(stored)s",
      { start: start, end: end, stored: stored },
      "%(start)s\u2013%(end)s of %(stored)s"
    );
  }

  function setupPanel(panel) {
    if (panel.dataset.nsmOrPagerBound === "1") {
      return;
    }
    panel.dataset.nsmOrPagerBound = "1";

    var rows = Array.prototype.slice.call(
      panel.querySelectorAll(".nsm-or-sample-row")
    );
    var stored = rows.length;
    if (!stored) {
      return;
    }

    var pageSize = readInt(panel.getAttribute("data-page-size"), 50);
    var total = readInt(panel.getAttribute("data-total-count"), stored);
    var rangeEl = panel.querySelector(".nsm-or-samples-range");
    var pager = panel.querySelector(".nsm-or-pager");
    var prevBtn = panel.querySelector(".nsm-or-pager-prev");
    var nextBtn = panel.querySelector(".nsm-or-pager-next");
    var statusEl = panel.querySelector(".nsm-or-pager-status");

    var pageCount = Math.ceil(stored / pageSize);
    var current = 0;

    function render() {
      var start = current * pageSize;
      var end = Math.min(start + pageSize, stored);
      for (var i = 0; i < stored; i++) {
        rows[i].style.display = i >= start && i < end ? "" : "none";
      }
      var statusText = buildStatus(start + 1, end, stored, total);
      if (statusEl) {
        statusEl.textContent = statusText;
      }
      if (rangeEl) {
        rangeEl.textContent = "(" + statusText + ")";
      }
      if (prevBtn) {
        prevBtn.disabled = current <= 0;
      }
      if (nextBtn) {
        nextBtn.disabled = current >= pageCount - 1;
      }
    }

    if (pageCount > 1 && pager) {
      pager.classList.remove("d-none");
      pager.classList.add("d-flex");
      if (prevBtn) {
        prevBtn.addEventListener("click", function () {
          if (current > 0) {
            current -= 1;
            render();
          }
        });
      }
      if (nextBtn) {
        nextBtn.addEventListener("click", function () {
          if (current < pageCount - 1) {
            current += 1;
            render();
          }
        });
      }
    }

    render();
  }

  function init() {
    document.querySelectorAll(".nsm-or-samples").forEach(setupPanel);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
