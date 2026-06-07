(function () {
  "use strict";

  var NSM_FILTER_DRAG_MIME = "application/x-nsm-filter-cell";
  var FILTER_DRAG_EXCLUDED_COLS = { _actions: true };

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

  function fetchJson(url) {
    var fetchFn =
      window.NSM_BRANCH_API && window.NSM_BRANCH_API.fetch
        ? window.NSM_BRANCH_API.fetch
        : fetch;
    return fetchFn(url, { credentials: "same-origin" }).then(function (response) {
      return response.json();
    });
  }

  function setValidationState(state, message) {
    var input = document.getElementById("nsm-ag-filter-query");
    var errorEl = document.getElementById("nsm-ag-filter-query-error");
    if (!input) {
      return;
    }
    input.classList.remove("is-valid", "is-invalid");
    if (state === "valid") {
      input.classList.add("is-valid");
    } else if (state === "invalid") {
      input.classList.add("is-invalid");
    }
    if (errorEl) {
      if (message) {
        errorEl.textContent = message;
        errorEl.classList.remove("d-none");
      } else {
        errorEl.textContent = "";
        errorEl.classList.add("d-none");
      }
    }
  }

  function buildValidateUrl(config, text) {
    var params = new URLSearchParams();
    params.set("q", text || "");
    return (
      config.queryValidateUrl +
      (config.queryValidateUrl.indexOf("?") >= 0 ? "&" : "?") +
      params.toString()
    );
  }

  function navigateWithFilterQuery(text) {
    var url = new URL(window.location.href);
    url.searchParams.delete("page");
    Array.from(url.searchParams.keys()).forEach(function (key) {
      if (key.indexOf("f_") === 0) {
        url.searchParams.delete(key);
      }
    });
    if (!text) {
      url.searchParams.delete("filter_q");
      url.searchParams.delete("q");
    } else {
      url.searchParams.set("filter_q", text);
      url.searchParams.delete("q");
    }
    window.location.assign(url.toString());
  }

  function stripHtml(value) {
    var text = value == null ? "" : String(value);
    if (!/<[a-z][\s\S]*>/i.test(text)) {
      return text.trim();
    }
    var tmp = document.createElement("div");
    tmp.innerHTML = text;
    return (tmp.textContent || tmp.innerText || "").trim();
  }

  function csvEscape(value) {
    var text = value == null ? "" : String(value);
    if (/[",\n\r]/.test(text)) {
      return '"' + text.replace(/"/g, '""') + '"';
    }
    return text;
  }

  function quoteNsmQueryValue(value) {
    var text = String(value == null ? "" : value).trim();
    return '"' + text.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"';
  }

  function formatShorthandFilterValue(value, operator) {
    var text = String(value == null ? "" : value).trim();
    var formatted = /^[\w\-:.]+$/.test(text) ? text : quoteNsmQueryValue(text);
    if (operator === "!=") {
      return "!= " + formatted;
    }
    return formatted;
  }

  function buildFilterFragmentFromCell(config, colId, filterValue) {
    var columnMap = (config && config.filterColumnMap) || {};
    var shorthandNames = (config && config.filterColumnShorthand) || {};
    if (!colId || !columnMap[colId]) {
      return null;
    }
    var text = String(filterValue == null ? "" : filterValue).trim();
    if (!text) {
      return null;
    }
    var shorthand =
      shorthandNames && Object.prototype.hasOwnProperty.call(shorthandNames, colId)
        ? shorthandNames[colId]
        : columnMap[colId];
    var formatted = formatShorthandFilterValue(text, "=");
    if (shorthand === "__bare_name__") {
      return "(" + formatted + ")";
    }
    if (!shorthand) {
      return null;
    }
    return shorthand + "(" + formatted + ")";
  }

  function mergeFilterQueryFragment(existing, fragment) {
    var left = String(existing == null ? "" : existing).trim();
    var right = String(fragment == null ? "" : fragment).trim();
    if (!right) {
      return left;
    }
    if (!left) {
      return right;
    }
    return left + " AND " + right;
  }

  function filterDragGhostLabel(config, colId, displayValue) {
    var shorthandNames = (config && config.filterColumnShorthand) || {};
    var columnMap = (config && config.filterColumnMap) || {};
    var shorthand =
      shorthandNames && Object.prototype.hasOwnProperty.call(shorthandNames, colId)
        ? shorthandNames[colId]
        : columnMap[colId] || colId;
    var label = shorthand === "__bare_name__" ? "Name" : shorthand;
    return label + ": " + displayValue;
  }

  function isFilterCellDragEvent(event) {
    if (!event || !event.dataTransfer || !event.dataTransfer.types) {
      return false;
    }
    var types = event.dataTransfer.types;
    for (var i = 0; i < types.length; i += 1) {
      if (types[i] === NSM_FILTER_DRAG_MIME) {
        return true;
      }
    }
    return false;
  }

  function parseFilterCellDropPayload(event) {
    if (!isFilterCellDragEvent(event) || !event.dataTransfer) {
      return null;
    }
    var raw = event.dataTransfer.getData(NSM_FILTER_DRAG_MIME);
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function resolveRulesCellFilterDragContext(cellEl, event) {
    if (!cellEl) {
      return null;
    }
    var colId = cellEl.getAttribute("data-col-id");
    if (!colId || FILTER_DRAG_EXCLUDED_COLS[colId]) {
      return null;
    }
    if (event && event.target && event.target.closest) {
      if (
        event.target.closest(
          ".nsm-ag-action-edit, .nsm-ag-action-delete, .nsm-ag-action-clone, .form-check-input, .nsm-ipa-loupe"
        )
      ) {
        return null;
      }
    }
    var filterValue = "";
    var displayValue = "";
    var link =
      event && event.target && event.target.closest
        ? event.target.closest("a[href]")
        : null;
    if (link && cellEl.contains(link)) {
      displayValue = (
        link.getAttribute("data-nsm-filter-value") ||
        link.textContent ||
        link.getAttribute("title") ||
        ""
      ).trim();
      filterValue = displayValue;
    }
    if (!filterValue) {
      displayValue = (cellEl.textContent || "").trim();
      filterValue = displayValue;
    }
    if (!filterValue) {
      return null;
    }
    return {
      colId: colId,
      filterValue: filterValue,
      displayValue: displayValue || filterValue,
    };
  }

  function disableNativeLinkDragInCell(cell) {
    if (!cell) {
      return;
    }
    cell.querySelectorAll("a[href]").forEach(function (anchor) {
      anchor.setAttribute("draggable", "false");
    });
  }

  function markFilterDropTargetsActive(active) {
    /* Column filter inputs only — filter query bar removed. */
  }

  function bindRulesFilterQueryDropTarget(_config, _applyFilterQuery) {
    /* Filter query bar removed — column filters only. */
  }

  function exportRulesCsv(config) {
    var table = document.querySelector("#rules .nsm-rules-table");
    if (!table) {
      return;
    }
    var headerCells = table.querySelectorAll("thead .nsm-rules-head-row--primary th");
    var headers = [];
    headerCells.forEach(function (cell) {
      var text = (cell.textContent || "").trim();
      if (text) {
        headers.push(text);
      }
    });
    if (!headers.length) {
      return;
    }
    var rows = [];
    table.querySelectorAll("tbody tr.nsm-rules-data-row").forEach(function (tr) {
      var values = [];
      tr.querySelectorAll("td").forEach(function (td) {
        if (td.classList.contains("w-1")) {
          return;
        }
        values.push(stripHtml(td.innerHTML));
      });
      if (values.length) {
        rows.push(values);
      }
    });
    var lines = [headers.map(csvEscape).join(",")];
    rows.forEach(function (row) {
      lines.push(row.map(csvEscape).join(","));
    });
    var blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    var name = (config && config.rulebookName) || "rules";
    name = String(name)
      .trim()
      .replace(/[^\w\-]+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_|_$/g, "");
    var stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    var filename = (name || "rules") + "_rules_" + stamp + ".csv";
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  }

  function copyText(text, callback) {
    if (!text) {
      callback(false);
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () {
          callback(true);
        },
        function () {
          callback(false);
        }
      );
      return;
    }
    callback(false);
  }

  function bindRulesCellFilterDrag(config) {
    if (!config || !config.filterColumnMap) {
      return;
    }
    var table = document.querySelector("#rules .nsm-rules-table");
    if (!table || table.dataset.nsmFilterCellDragBound === "1") {
      return;
    }
    table.dataset.nsmFilterCellDragBound = "1";

    table.addEventListener(
      "mousedown",
      function (event) {
        if (event.button !== 0) {
          return;
        }
        var cell = event.target.closest("td.nsm-rules-td[data-col-id]");
        if (!cell || !table.contains(cell)) {
          return;
        }
        var colId = cell.getAttribute("data-col-id");
        if (!colId || !config.filterColumnMap[colId]) {
          return;
        }
        var ctx = resolveRulesCellFilterDragContext(cell, event);
        if (!ctx) {
          return;
        }
        cell.setAttribute("draggable", "true");
        disableNativeLinkDragInCell(cell);
      },
      true
    );

    table.addEventListener(
      "dragstart",
      function (event) {
        var cell = event.target.closest("td.nsm-rules-td[data-col-id]");
        if (!cell || !table.contains(cell)) {
          return;
        }
        var ctx = resolveRulesCellFilterDragContext(cell, event);
        if (!ctx || !config.filterColumnMap[ctx.colId]) {
          return;
        }
        if (!event.dataTransfer) {
          return;
        }
        disableNativeLinkDragInCell(cell);
        event.stopPropagation();
        event.dataTransfer.setData(
          NSM_FILTER_DRAG_MIME,
          JSON.stringify({
            colId: ctx.colId,
            filterValue: ctx.filterValue,
            displayValue: ctx.displayValue,
          })
        );
        event.dataTransfer.setData("text/plain", ctx.displayValue);
        event.dataTransfer.effectAllowed = "copy";
        var ghost = document.createElement("div");
        ghost.className = "nsm-rules-filter-drag-ghost";
        ghost.textContent = filterDragGhostLabel(config, ctx.colId, ctx.displayValue);
        ghost.setAttribute("aria-hidden", "true");
        document.body.appendChild(ghost);
        event.dataTransfer.setDragImage(ghost, 16, 14);
        window.setTimeout(function () {
          if (ghost.parentNode) {
            ghost.parentNode.removeChild(ghost);
          }
        }, 0);
        cell.classList.add("nsm-rules-cell-filter-dragging");
        markFilterDropTargetsActive(true);
      },
      true
    );

    table.addEventListener(
      "dragend",
      function (event) {
        var cell = event.target.closest("td.nsm-rules-td[data-col-id]");
        if (cell) {
          cell.removeAttribute("draggable");
          cell.classList.remove("nsm-rules-cell-filter-dragging");
        }
        markFilterDropTargetsActive(false);
      },
      true
    );
  }


  function bindRulesColumnFilterDropTarget(config) {
    if (!config || !config.filterColumnMap) {
      return;
    }
    var table = document.querySelector("#rules .nsm-rules-table");
    if (!table || table.dataset.nsmFloatingFilterDropBound === "1") {
      return;
    }
    table.dataset.nsmFloatingFilterDropBound = "1";

    table.addEventListener(
      "dragover",
      function (event) {
        var input = event.target.closest(".nsm-rules-filter-input[data-col-id]");
        if (!input || !isFilterCellDragEvent(event)) {
          return;
        }
        var colId = input.getAttribute("data-col-id");
        if (!colId || !config.filterColumnMap[colId]) {
          return;
        }
        event.preventDefault();
        if (event.dataTransfer) {
          event.dataTransfer.dropEffect = "copy";
        }
        input.classList.add("nsm-ag-floating-filter-drop-hover");
      },
      true
    );

    table.addEventListener(
      "dragleave",
      function (event) {
        var input = event.target.closest(".nsm-rules-filter-input[data-col-id]");
        if (
          input &&
          (!input.contains(event.relatedTarget) ||
            !event.relatedTarget ||
            !event.relatedTarget.closest(".nsm-rules-filter-input"))
        ) {
          input.classList.remove("nsm-ag-floating-filter-drop-hover");
        }
      },
      true
    );

    table.addEventListener(
      "drop",
      function (event) {
        var input = event.target.closest(".nsm-rules-filter-input[data-col-id]");
        if (!input) {
          return;
        }
        input.classList.remove("nsm-ag-floating-filter-drop-hover");
        var payload = parseFilterCellDropPayload(event);
        if (!payload) {
          return;
        }
        var colId = input.getAttribute("data-col-id");
        if (!colId || !config.filterColumnMap[colId]) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        markFilterDropTargetsActive(false);
        input.value = String(payload.filterValue == null ? "" : payload.filterValue).trim();
        input.focus();
        submitRulesQuicksearch();
      },
      true
    );
  }

  function navigateWithCellMode(mode) {
    var url = new URL(window.location.href);
    url.searchParams.delete("page");
    if (!mode || mode === "stack") {
      url.searchParams.delete("cell_mode");
    } else {
      url.searchParams.set("cell_mode", mode);
    }
    window.location.assign(url.toString());
  }

  function submitRulesQuicksearch() {
    var form = document.getElementById("rules-quicksearch");
    if (!form) {
      return;
    }
    var action = form.getAttribute("action") || window.location.pathname;
    var url = new URL(action, window.location.origin);
    var params = new URLSearchParams(window.location.search);
    params.delete("page");
    params.delete("filter_q");
    params.delete("q");
    document.querySelectorAll("#rules .nsm-rules-filter-input").forEach(function (input) {
      var name = input.getAttribute("name");
      if (!name) {
        return;
      }
      var value = (input.value || "").trim();
      if (value) {
        params.set(name, value);
      } else {
        params.delete(name);
      }
    });
    form.querySelectorAll('input[type="hidden"][name]').forEach(function (input) {
      if (input.value) {
        params.set(input.name, input.value);
      } else {
        params.delete(input.name);
      }
    });
    url.search = params.toString();
    window.location.assign(url.toString());
  }

  function bindRulesQuicksearchFilters() {
    var form = document.getElementById("rules-quicksearch");
    if (!form || form.dataset.nsmQuicksearchBound === "1") {
      return;
    }
    form.dataset.nsmQuicksearchBound = "1";
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      submitRulesQuicksearch();
    });
    document.querySelectorAll("#rules .nsm-rules-filter-input").forEach(function (input) {
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          event.stopPropagation();
          submitRulesQuicksearch();
        }
      });
      input.addEventListener("search", function () {
        if (!(input.value || "").trim()) {
          submitRulesQuicksearch();
        }
      });
    });
    document.querySelectorAll("#rules .nsm-rules-filter-apply").forEach(function (btn) {
      btn.addEventListener("click", function (event) {
        event.preventDefault();
        submitRulesQuicksearch();
      });
    });
  }

  function bindRulesCellModeSelector(config) {
    var selector = document.getElementById("nsm-rules-cell-mode-selector");
    if (!selector) {
      return;
    }
    selector.querySelectorAll(".nsm-rules-cell-mode-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mode = btn.getAttribute("data-cell-mode") || "stack";
        if (mode === (config.cellMode || "stack")) {
          return;
        }
        navigateWithCellMode(mode);
      });
    });
  }

  function bindChrome(config) {
    var input = document.getElementById("nsm-ag-filter-query");
    var applyBtn = document.getElementById("nsm-ag-filter-query-apply");
    var copyBtn = document.getElementById("nsm-ag-filter-query-copy");
    var clearBtn = document.getElementById("nsm-ag-clear-filters");
    var exportBtn = document.getElementById("nsm-ag-csv-export");
    var validateTimer = null;

    if (input && config.filterQuery) {
      input.value = config.filterQuery;
    }
    if (input && config.filterQueryError) {
      setValidationState("invalid", config.filterQueryError);
    }

    function scheduleValidation() {
      if (!input || !config.queryValidateUrl) {
        return;
      }
      if (validateTimer) {
        window.clearTimeout(validateTimer);
      }
      validateTimer = window.setTimeout(function () {
        validateTimer = null;
        var text = (input.value || "").trim();
        if (!text) {
          setValidationState(null, "");
          return;
        }
        fetchJson(buildValidateUrl(config, text))
          .then(function (data) {
            if (data && data.valid) {
              setValidationState("valid", "");
              if (data.normalized && data.normalized !== text) {
                input.value = data.normalized;
              }
            } else {
              setValidationState("invalid", (data && data.error) || "Invalid query");
            }
          })
          .catch(function () {
            setValidationState("invalid", "Validation failed");
          });
      }, 300);
    }

    function applyFilterQuery() {
      if (!input) {
        return;
      }
      var text = (input.value || "").trim();
      if (!text) {
        navigateWithFilterQuery("");
        return;
      }
      fetchJson(buildValidateUrl(config, text))
        .then(function (data) {
          if (!data || !data.valid) {
            setValidationState("invalid", (data && data.error) || "Invalid query");
            return;
          }
          var queryText = (data.normalized || text).trim();
          navigateWithFilterQuery(queryText);
        })
        .catch(function () {
          setValidationState("invalid", "Validation failed");
        });
    }

    if (input) {
      input.addEventListener("input", scheduleValidation);
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          applyFilterQuery();
        } else if (event.key === "Escape") {
          input.value = config.filterQuery || "";
          setValidationState(null, "");
        }
      });
    }
    if (applyBtn) {
      applyBtn.addEventListener("click", applyFilterQuery);
    }
    if (copyBtn && input) {
      copyBtn.addEventListener("click", function () {
        copyText(input.value || "", function () {});
      });
    }
    if (clearBtn && config.clearFiltersUrl) {
      clearBtn.classList.toggle("d-none", !config.filterQuery && !config.filterActive);
      clearBtn.addEventListener("click", function () {
        window.location.assign(config.clearFiltersUrl);
      });
    }
    if (exportBtn) {
      exportBtn.addEventListener("click", function () {
        exportRulesCsv(config);
      });
    }

    bindRulesCellFilterDrag(config);
    bindRulesFilterQueryDropTarget(config, applyFilterQuery);
    bindRulesColumnFilterDropTarget(config);
    bindRulesCellModeSelector(config);
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindRulesQuicksearchFilters();
    var config = readConfig();
    if (!config) {
      return;
    }
    bindChrome(config);
  });
})();
