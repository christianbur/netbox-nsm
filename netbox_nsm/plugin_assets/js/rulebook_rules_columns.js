(function () {
  "use strict";

  var STORAGE_PREFIX = "nsm-rules-col-widths:";

  function readConfig() {
    var el = document.getElementById("rules-chrome-config");
    if (!el || !el.textContent) {
      return null;
    }
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return null;
    }
  }

  function storageKey(rulebookId) {
    return STORAGE_PREFIX + String(rulebookId == null ? "0" : rulebookId);
  }

  function loadSavedWidths(rulebookId) {
    try {
      return JSON.parse(localStorage.getItem(storageKey(rulebookId)) || "{}");
    } catch (e) {
      return {};
    }
  }

  function saveWidth(rulebookId, colId, widthPx) {
    var saved = loadSavedWidths(rulebookId);
    saved[colId] = widthPx;
    localStorage.setItem(storageKey(rulebookId), JSON.stringify(saved));
  }

  function findColElement(table, colId) {
    if (!table || !colId) {
      return null;
    }
    var cols = table.querySelectorAll("colgroup col[data-col-id]");
    for (var i = 0; i < cols.length; i += 1) {
      if (cols[i].getAttribute("data-col-id") === colId) {
        return cols[i];
      }
    }
    return null;
  }

  function columnBounds(colEl) {
    var minWidth = parseInt(colEl.getAttribute("data-min-width"), 10);
    var defaultWidth = parseInt(colEl.getAttribute("data-default-width"), 10);
    if (!minWidth || minWidth < 1) {
      minWidth = 1;
    }
    if (!defaultWidth || defaultWidth < minWidth) {
      defaultWidth = minWidth;
    }
    return { minWidth: minWidth, defaultWidth: defaultWidth };
  }

  function readColumnWidth(table, colEl) {
    var rect = colEl.getBoundingClientRect();
    if (rect.width > 0) {
      return Math.round(rect.width);
    }
    var inline = parseInt(colEl.style.width, 10);
    if (inline > 0) {
      return inline;
    }
    return columnBounds(colEl).defaultWidth;
  }

  function applyColumnWidth(colEl, widthPx) {
    var bounds = columnBounds(colEl);
    var next = Math.max(bounds.minWidth, Math.round(widthPx));
    colEl.style.width = next + "px";
    return next;
  }

  function initColumnWidths(table, config) {
    var saved = loadSavedWidths(config && config.rulebookId);
    table.querySelectorAll("colgroup col[data-col-id]").forEach(function (colEl) {
      var colId = colEl.getAttribute("data-col-id");
      var bounds = columnBounds(colEl);
      var width =
        saved[colId] != null ? parseInt(saved[colId], 10) : bounds.defaultWidth;
      applyColumnWidth(colEl, width || bounds.defaultWidth);
    });
  }

  function bindColumnResize(table, config) {
    if (!table || table.dataset.nsmColumnResizeBound === "1") {
      return;
    }
    table.dataset.nsmColumnResizeBound = "1";

    var resizeState = null;

    function stopResize() {
      if (!resizeState) {
        return;
      }
      saveWidth(config.rulebookId, resizeState.colId, resizeState.width);
      resizeState = null;
      table.classList.remove("nsm-rules-table--column-resizing");
      document.body.classList.remove("nsm-rules-column-resizing");
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", stopResize);
    }

    function onMouseMove(event) {
      if (!resizeState) {
        return;
      }
      var delta = event.clientX - resizeState.startX;
      resizeState.width = applyColumnWidth(
        resizeState.colEl,
        resizeState.startWidth + delta
      );
    }

    table.querySelectorAll(".nsm-rules-col-resize-handle").forEach(function (handle) {
      handle.addEventListener("mousedown", function (event) {
        if (event.button !== 0) {
          return;
        }
        var th = handle.closest("th[data-col-id]");
        if (!th) {
          return;
        }
        var colId = th.getAttribute("data-col-id");
        var colEl = findColElement(table, colId);
        if (!colEl) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        resizeState = {
          colId: colId,
          colEl: colEl,
          startX: event.clientX,
          startWidth: readColumnWidth(table, colEl),
          width: readColumnWidth(table, colEl),
        };
        table.classList.add("nsm-rules-table--column-resizing");
        document.body.classList.add("nsm-rules-column-resizing");
        window.addEventListener("mousemove", onMouseMove);
        window.addEventListener("mouseup", stopResize);
      });
    });
  }

  function syncResizeHandleSpans(table) {
    var primaryRow = table.querySelector("thead .nsm-rules-head-row--primary");
    if (!primaryRow) {
      return;
    }
    var primaryHeight = Math.ceil(primaryRow.getBoundingClientRect().height);
    table.style.setProperty(
      "--nsm-rules-head-primary-height",
      primaryHeight + "px"
    );
  }

  function observePrimaryHeadRow(table) {
    var primaryRow = table.querySelector("thead .nsm-rules-head-row--primary");
    if (!primaryRow || typeof ResizeObserver === "undefined") {
      return;
    }
    var observer = new ResizeObserver(function () {
      syncResizeHandleSpans(table);
    });
    observer.observe(primaryRow);
  }

  function initRulesColumnResize() {
    var table = document.querySelector("#rules .nsm-rules-table");
    var config = readConfig();
    if (!table || !config) {
      return;
    }
    initColumnWidths(table, config);
    syncResizeHandleSpans(table);
    observePrimaryHeadRow(table);
    bindColumnResize(table, config);
    window.addEventListener("resize", function () {
      syncResizeHandleSpans(table);
    });
  }

  document.addEventListener("DOMContentLoaded", initRulesColumnResize);

  // --- Column visibility (Configure Table) ---

  var VISIBILITY_PREFIX = "nsm-rules-col-hidden:";

  function loadHiddenColumns(rulebookId) {
    try {
      var raw = localStorage.getItem(VISIBILITY_PREFIX + String(rulebookId == null ? "0" : rulebookId));
      var parsed = JSON.parse(raw || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function saveHiddenColumns(rulebookId, hiddenIds) {
    localStorage.setItem(
      VISIBILITY_PREFIX + String(rulebookId == null ? "0" : rulebookId),
      JSON.stringify(hiddenIds)
    );
  }

  function setColumnVisible(table, colId, visible) {
    if (!table || !colId) {
      return;
    }
    table.querySelectorAll('[data-col-id="' + colId + '"]').forEach(function (el) {
      el.classList.toggle("nsm-rules-col-hidden", !visible);
    });
  }

  function applyColumnVisibility(table, config) {
    var hidden = loadHiddenColumns(config.rulebookId);
    hidden.forEach(function (colId) {
      setColumnVisible(table, colId, false);
    });
    document.querySelectorAll(".nsm-rules-col-visibility").forEach(function (cb) {
      var colId = cb.getAttribute("data-col-id");
      cb.checked = hidden.indexOf(colId) === -1;
    });
  }

  function bindColumnVisibility(table, config) {
    document.querySelectorAll(".nsm-rules-col-visibility").forEach(function (cb) {
      if (cb.dataset.nsmColVisBound === "1") {
        return;
      }
      cb.dataset.nsmColVisBound = "1";
      cb.addEventListener("change", function () {
        var colId = cb.getAttribute("data-col-id");
        var hidden = loadHiddenColumns(config.rulebookId);
        if (cb.checked) {
          hidden = hidden.filter(function (id) {
            return id !== colId;
          });
        } else if (hidden.indexOf(colId) === -1) {
          hidden.push(colId);
        }
        saveHiddenColumns(config.rulebookId, hidden);
        setColumnVisible(table, colId, cb.checked);
        syncResizeHandleSpans(table);
      });
    });
  }

  function initRulesColumnVisibility() {
    var table = document.querySelector("#rules .nsm-rules-table");
    var config = readConfig();
    if (!table || !config) {
      return;
    }
    applyColumnVisibility(table, config);
    bindColumnVisibility(table, config);
  }

  document.addEventListener("DOMContentLoaded", initRulesColumnVisibility);
})();
