(function () {
  "use strict";

  var FILTER_LOUPE_EXCLUDED_COLS = { _actions: true };

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

  function chromeT(config, key, fallback) {
    var i18n = (config && config.i18n) || {};
    if (i18n[key] != null && i18n[key] !== "") {
      return i18n[key];
    }
    return fallback;
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

  function tomlString(value) {
    var text = value == null ? "" : String(value);
    return (
      '"' +
      text
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')
        .replace(/\r/g, "\\r")
        .replace(/\n/g, "\\n")
        .replace(/\t/g, "\\t") +
      '"'
    );
  }

  function tomlKey(value) {
    return tomlString(value);
  }

  function tomlArray(values) {
    return "[" + values.map(tomlString).join(", ") + "]";
  }

  function uniqueTomlKey(label, seen) {
    var base = String(label == null ? "" : label).trim() || "column";
    var key = base;
    var index = 2;
    while (Object.prototype.hasOwnProperty.call(seen, key)) {
      key = base + " " + index;
      index += 1;
    }
    seen[key] = true;
    return key;
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

  function readQuickFilterQueryText(input, config) {
    var fromInput = input ? String(input.value == null ? "" : input.value).trim() : "";
    if (fromInput) {
      return fromInput;
    }
    if (config && String(config.filterQuery || "").trim()) {
      return String(config.filterQuery).trim();
    }
    var params = new URLSearchParams(window.location.search);
    return (params.get("filter_q") || params.get("q") || "").trim();
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
    if (left.toUpperCase() === right.toUpperCase()) {
      return left;
    }
    if (/\s(AND|OR)\s/i.test(left) && !(left.charAt(0) === "(" && left.charAt(left.length - 1) === ")")) {
      left = "(" + left + ")";
    }
    return left + " AND " + right;
  }

  function findColumnQuicksearchInput(colId) {
    if (!colId) {
      return null;
    }
    var inputs = document.querySelectorAll(
      "#rules .nsm-rules-filter-input[data-col-id]"
    );
    for (var i = 0; i < inputs.length; i++) {
      if (inputs[i].getAttribute("data-col-id") === colId) {
        return inputs[i];
      }
    }
    return null;
  }

  function applyFilterFragmentToQuickSearch(config, colId, filterValue) {
    var text = String(filterValue == null ? "" : filterValue).trim();
    if (!text) {
      return;
    }
    var columnInput = findColumnQuicksearchInput(colId);
    if (columnInput) {
      var merged = mergeFilterQueryFragment(
        String(columnInput.value == null ? "" : columnInput.value).trim(),
        text
      );
      columnInput.value = merged;
      columnInput.focus();
      submitRulesQuicksearch();
      return;
    }
    var input = document.getElementById("nsm-ag-filter-query");
    if (!input) {
      return;
    }
    var fragment = buildFilterFragmentFromCell(config, colId, filterValue);
    if (!fragment) {
      return;
    }
    var liveConfig = readConfig() || config;
    var mergedQuery = mergeFilterQueryFragment(
      readQuickFilterQueryText(input, liveConfig),
      fragment
    );
    input.value = mergedQuery;
    input.focus();
    input.dispatchEvent(new Event("input", { bubbles: true }));
    if (config.queryValidateUrl) {
      return;
    }
    navigateWithFilterQuery(mergedQuery);
  }

  function resolveRulesFilterLoupeButton(event) {
    var button = event.target.closest(".nsm-rules-filter-loupe");
    if (button) {
      return button;
    }
    if (event.target.closest("a.nsm-ag-cell-link")) {
      return null;
    }
    var target = event.target.closest(".nsm-rules-filter-target--has-loupe");
    if (!target) {
      return null;
    }
    button = target.querySelector(".nsm-rules-filter-loupe");
    if (!button) {
      return null;
    }
    var loupeRect = button.getBoundingClientRect();
    if (!loupeRect.width || !loupeRect.height) {
      return button;
    }
    if (
      event.clientX < loupeRect.left ||
      event.clientX > loupeRect.right ||
      event.clientY < loupeRect.top ||
      event.clientY > loupeRect.bottom
    ) {
      return null;
    }
    return button;
  }

  function handleRulesFilterLoupeClick(event) {
    var button = resolveRulesFilterLoupeButton(event);
    if (!button) {
      return;
    }
    var rulesRoot = document.getElementById("rules");
    if (!rulesRoot || !rulesRoot.contains(button)) {
      return;
    }
    if (!button.closest("#rules .nsm-rules-table")) {
      return;
    }
    var cell = button.closest("td.nsm-rules-td[data-col-id]");
    if (!cell) {
      return;
    }
    var colId = cell.getAttribute("data-col-id");
    if (!colId || FILTER_LOUPE_EXCLUDED_COLS[colId]) {
      return;
    }
    var filterValue = String(
      button.getAttribute("data-nsm-filter-value") || ""
    ).trim();
    if (!filterValue) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    applyFilterFragmentToQuickSearch(readConfig(), colId, filterValue);
  }

  function bindRulesFilterLoupes() {
    if (document.documentElement.dataset.nsmRulesFilterLoupeBound === "1") {
      return;
    }
    document.documentElement.dataset.nsmRulesFilterLoupeBound = "1";
    document.addEventListener("click", handleRulesFilterLoupeClick, true);
  }

  function exportRulesToml(config) {
    var table = document.querySelector("#rules .nsm-rules-table");
    if (!table) {
      return;
    }
    var headerCells = table.querySelectorAll("thead .nsm-rules-head-row--primary th");
    var headers = [];
    var seenHeaders = {};
    headerCells.forEach(function (cell) {
      var text = (cell.textContent || "").trim();
      if (text) {
        headers.push(uniqueTomlKey(text, seenHeaders));
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
    var lines = [
      'format = "netbox-nsm-rules-visible-v1"',
      "rulebook = " + tomlString((config && config.rulebookName) || "rules"),
      "exported_at = " + tomlString(new Date().toISOString()),
      "visible_columns = " + tomlArray(headers),
      "",
    ];
    rows.forEach(function (row, rowIndex) {
      lines.push("[[rows]]");
      lines.push("index = " + String(rowIndex + 1));
      headers.forEach(function (header, colIndex) {
        lines.push(tomlKey(header) + " = " + tomlString(row[colIndex] || ""));
      });
      lines.push("");
    });
    var blob = new Blob([lines.join("\n")], { type: "application/toml;charset=utf-8" });
    var name = (config && config.rulebookName) || "rules";
    name = String(name)
      .trim()
      .replace(/[^\w\-]+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_|_$/g, "");
    var stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    var filename = (name || "rules") + "_rules_" + stamp + ".toml";
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

  function navigateWithColumnMode(mode) {
    var url = new URL(window.location.href);
    url.searchParams.delete("page");
    if (!mode || mode === "collapsed") {
      url.searchParams.delete("col_mode");
    } else {
      url.searchParams.set("col_mode", mode);
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

  function syncRulesFilterClearButton(input) {
    var field = input.closest(".nsm-rules-filter-field");
    if (!field) {
      return;
    }
    var hasValue = !!(input.value || "").trim();
    field.classList.toggle("nsm-rules-filter-field--has-value", hasValue);
  }

  function bindRulesFilterClearButtons() {
    document.querySelectorAll("#rules .nsm-rules-filter-field").forEach(function (field) {
      if (field.dataset.nsmFilterClearBound === "1") {
        return;
      }
      field.dataset.nsmFilterClearBound = "1";
      var input = field.querySelector(".nsm-rules-filter-input");
      var clearBtn = field.querySelector(".nsm-rules-filter-clear");
      if (!input || !clearBtn) {
        return;
      }
      syncRulesFilterClearButton(input);
      input.addEventListener("input", function () {
        syncRulesFilterClearButton(input);
      });
      clearBtn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        input.value = "";
        syncRulesFilterClearButton(input);
        input.focus();
        submitRulesQuicksearch();
      });
    });
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

  function bindRulesColumnModeToggle(config) {
    var toggle = document.getElementById("nsm-rules-col-mode-toggle");
    if (!toggle) {
      return;
    }
    toggle.addEventListener("click", function () {
      var nextMode =
        toggle.getAttribute("aria-pressed") === "true" ? "expanded" : "collapsed";
      var currentMode = config.columnMode || "expanded";
      if (nextMode === currentMode) {
        return;
      }
      navigateWithColumnMode(nextMode);
    });
  }

  function bindChrome(config) {
    var input = document.getElementById("nsm-ag-filter-query");
    var applyBtn = document.getElementById("nsm-ag-filter-query-apply");
    var copyBtn = document.getElementById("nsm-ag-filter-query-copy");
    var clearBtn = document.getElementById("nsm-ag-clear-filters");
    var exportBtn = document.getElementById("nsm-ag-toml-export");
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
              setValidationState(
                "invalid",
                (data && data.error) ||
                  chromeT(config, "invalidQuery", "Invalid query")
              );
            }
          })
          .catch(function () {
            setValidationState(
              "invalid",
              chromeT(config, "validationFailed", "Validation failed")
            );
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
            setValidationState(
              "invalid",
              (data && data.error) ||
                chromeT(config, "invalidQuery", "Invalid query")
            );
            return;
          }
          var queryText = (data.normalized || text).trim();
          navigateWithFilterQuery(queryText);
        })
        .catch(function () {
          setValidationState(
            "invalid",
            chromeT(config, "validationFailed", "Validation failed")
          );
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
        exportRulesToml(config);
      });
    }

    bindRulesCellModeSelector(config);
    bindRulesColumnModeToggle(config);
  }

  function prefillRulesFiltersFromUrl() {
    var params = new URLSearchParams(window.location.search);
    document.querySelectorAll("#rules .nsm-rules-filter-input").forEach(function (input) {
      var name = input.getAttribute("name");
      if (!name) {
        return;
      }
      if ((input.value || "").trim()) {
        return;
      }
      var fromUrl = (params.get(name) || "").trim();
      if (fromUrl) {
        input.value = fromUrl;
        return;
      }
      var colId = input.getAttribute("data-col-id") || "";
      if (!colId || colId.indexOf("::") >= 0) {
        return;
      }
      var expandedPrefix = "f_" + colId.replace(/::/g, "__") + "__ct_";
      params.forEach(function (value, key) {
        if (!fromUrl && key.indexOf(expandedPrefix) === 0) {
          fromUrl = (value || "").trim();
        }
      });
      if (fromUrl) {
        input.value = fromUrl;
      }
      syncRulesFilterClearButton(input);
    });
  }

  function initRulesFilterLoupes() {
    bindRulesFilterLoupes();
  }

  function resolveRulesPanelBottom(top) {
    var bottom = window.innerHeight;
    var footer = document.querySelector(".page-footer, footer.footer");
    if (footer) {
      var footerTop = footer.getBoundingClientRect().top;
      if (footerTop > top && footerTop < bottom) {
        bottom = footerTop;
      }
    }
    return bottom;
  }

  function syncRulesPanelHeight() {
    var rules = document.getElementById("rules");
    if (!rules) {
      return;
    }
    var panel = rules.closest(".container-fluid.tab-content");
    if (!panel) {
      return;
    }
    var panelTop = panel.getBoundingClientRect().top;
    var rulesTop = rules.getBoundingClientRect().top;
    var bottom = resolveRulesPanelBottom(panelTop);
    var panelHeight = Math.max(320, Math.floor(bottom - panelTop));
    var rulesHeight = Math.max(280, Math.floor(bottom - rulesTop));
    panel.style.setProperty("--nsm-rules-panel-height", panelHeight + "px");
    rules.style.setProperty("--nsm-rules-card-height", rulesHeight + "px");
    if (typeof window.dispatchEvent === "function") {
      window.dispatchEvent(new CustomEvent("nsm:rules-panel-height"));
    }
  }

  function initRulesPanelHeight() {
    if (!document.getElementById("rules")) {
      return;
    }
    syncRulesPanelHeight();
    window.addEventListener("resize", syncRulesPanelHeight);
    if (typeof ResizeObserver !== "undefined") {
      var observer = new ResizeObserver(syncRulesPanelHeight);
      var footer = document.querySelector(".page-footer");
      if (footer) {
        observer.observe(footer);
      }
      var header = document.querySelector(".navbar, .page-header");
      if (header) {
        observer.observe(header);
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initRulesFilterLoupes);
  } else {
    initRulesFilterLoupes();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initRulesPanelHeight();
    prefillRulesFiltersFromUrl();
    bindRulesFilterClearButtons();
    bindRulesQuicksearchFilters();
    var config = readConfig();
    if (!config) {
      return;
    }
    bindChrome(config);
  });
})();
