/**
 * AG Grid Rules tab — Community only (MIT). NetBox color-mode via data-ag-theme-mode.
 */
(function () {
  "use strict";

  function isNetBoxDark() {
    return document.documentElement.getAttribute("data-bs-theme") === "dark";
  }

  function netBoxAgThemeMode() {
    return isNetBoxDark() ? "dark" : "light";
  }

  function readJsonScript(id) {
    var el = document.getElementById(id);
    if (!el) {
      return null;
    }
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.error("NSM policy grid: invalid JSON in #" + id, e);
      return null;
    }
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function descriptionCellHtml(desc) {
    var raw = desc == null ? "" : String(desc);
    if (raw === "-") {
      raw = "";
    }
    var short = raw.length <= 21 ? raw : raw.slice(0, 21) + "…";
    return (
      '<span title="' +
      escapeHtml(raw) +
      '">' +
      escapeHtml(short || "-") +
      "</span>"
    );
  }

  function applyInitialFilterModel(api, config) {
    if (!api || !config || !config.initialFilterModel) {
      return;
    }
    if (typeof api.setFilterModel !== "function") {
      return;
    }
    if (api._nsmInitialFilterApplied) {
      return;
    }
    try {
      api.setFilterModel(config.initialFilterModel);
      api._nsmInitialFilterApplied = true;
      if (typeof api.onFilterChanged === "function") {
        api.onFilterChanged();
      }
    } catch (e) {
      console.warn("NSM policy grid: initial filter model failed", e);
    }
  }

  function hasActiveGridFilters(api) {
    if (!api || typeof api.getFilterModel !== "function") {
      return false;
    }
    var model = api.getFilterModel();
    return !!(model && Object.keys(model).length);
  }

  function hasActiveNsmQuery(config) {
    if (config && config.nsmQ) {
      return true;
    }
    return new URLSearchParams(window.location.search).has("nsm_q");
  }

  function setToolbarButtonVisible(btn, visible) {
    if (!btn) {
      return;
    }
    btn.classList.toggle("d-none", !visible);
  }

  function updateClearFiltersButton(gridApi, config) {
    var btn = document.getElementById("nsm-ag-clear-filters");
    if (!btn) {
      return;
    }
    var active = hasActiveNsmQuery(config) || hasActiveGridFilters(gridApi);
    setToolbarButtonVisible(btn, active);
  }

  function clearAllPolicyFilters(gridApi, config) {
    if (hasActiveNsmQuery(config)) {
      window.location.href =
        (config && config.clearFiltersUrl) || window.location.pathname;
      return;
    }
    if (gridApi && typeof gridApi.setFilterModel === "function") {
      gridApi.setFilterModel(null);
    }
  }

  function htmlCellFilterValue(params) {
    var field = params.colDef && params.colDef.field;
    if (params.data && field) {
      var filterKey = field + "__filter";
      if (params.data[filterKey] != null && params.data[filterKey] !== "") {
        return String(params.data[filterKey]);
      }
      if (params.data[field] != null) {
        var html = String(params.data[field]);
        if (html) {
          var tmp = document.createElement("div");
          tmp.innerHTML = html;
          return (tmp.textContent || tmp.innerText || "").trim();
        }
      }
    }
    if (params.value != null && params.value !== "") {
      var fallback = String(params.value);
      var wrap = document.createElement("div");
      wrap.innerHTML = fallback;
      return (wrap.textContent || wrap.innerText || "").trim();
    }
    return "";
  }

  function applyTextColumnFilters(columnDefs) {
    (columnDefs || []).forEach(function (col) {
      if (col.children) {
        applyTextColumnFilters(col.children);
        return;
      }
      if (
        col.cellRenderer === "htmlCell" ||
        col.cellRenderer === "statusCell" ||
        col.cellRenderer === "descriptionCell"
      ) {
        if (col.cellRenderer === "htmlCell" || col.cellRenderer === "descriptionCell") {
          col.autoHeight = true;
          col.wrapText = true;
        }
        col.filter = "agTextColumnFilter";
        col.filterParams = {
          filterOptions: [
            "contains",
            "notContains",
            "equals",
            "notEqual",
            "startsWith",
            "endsWith",
          ],
          defaultOption: "contains",
          debounceMs: 150,
        };
        col.filterValueGetter = htmlCellFilterValue;
      }
    });
  }

  function enabledFilterText(enabled, statusLabels) {
    var onLabel = (statusLabels && statusLabels.on) || "On";
    var offLabel = (statusLabels && statusLabels.off) || "Off";
    if (enabled) {
      return onLabel + " on enabled aktiv ein 1";
    }
    return offLabel + " off disabled inaktiv aus 0";
  }

  function fitPolicyGridWidth(api, gridEl) {
    if (!api || !gridEl || typeof api.getAllDisplayedColumns !== "function") {
      return;
    }
    var cols = api.getAllDisplayedColumns();
    if (!cols || !cols.length) {
      return;
    }
    var total = 0;
    cols.forEach(function (col) {
      total += col.getActualWidth();
    });
    var sideBar = gridEl.querySelector(".ag-side-bar");
    if (sideBar && sideBar.offsetParent !== null) {
      total += sideBar.offsetWidth || 0;
    }
    gridEl.style.width = Math.ceil(total + 2) + "px";
  }

  function schedulePolicyGridWidthFit(api, gridEl) {
    if (!api || !gridEl) {
      return;
    }
    window.requestAnimationFrame(function () {
      fitPolicyGridWidth(api, gridEl);
    });
  }

  function resetPolicyRowHeights(api) {
    if (api && typeof api.resetRowHeights === "function") {
      api.resetRowHeights();
    }
  }

  function initPolicyAgGrid() {
    var payload = readJsonScript("nsm-policy-grid-data");
    var config = readJsonScript("nsm-policy-grid-config") || {};
    var gridEl = document.getElementById("nsm-policy-ag-grid");
    if (!payload || !gridEl) {
      console.warn("NSM policy grid: missing DOM or payload");
      return;
    }
    if (typeof agGrid === "undefined" || typeof agGrid.createGrid !== "function") {
      console.error("NSM policy grid: ag-grid-community script not loaded");
      gridEl.innerHTML =
        '<p class="text-danger p-3 mb-0">AG Grid konnte nicht geladen werden.</p>';
      return;
    }

    var canChange = !!(config.permissions && config.permissions.change);
    var canDelete = !!(config.permissions && config.permissions.delete);
    var statusLabels = config.statusLabels || {};
    var statusOnLabel = statusLabels.on || "On";
    var statusOffLabel = statusLabels.off || "Off";
    var columnDefs = payload.columnDefs || [];
    applyTextColumnFilters(columnDefs);

    var totalRowCount = (payload.rowData || []).length;

    var htmlCellRenderer = function (params) {
      var wrap = document.createElement("div");
      wrap.className = "nsm-ag-html-cell w-100";
      wrap.innerHTML = params.value || '<span class="nsm-cell-empty">-</span>';
      return wrap;
    };

    function statusCellHtml(enabled) {
      var label = enabled ? statusOnLabel : statusOffLabel;
      var stateClass = enabled ? "nsm-status-icon-on" : "nsm-status-icon-off";
      var iconClass = enabled ? "mdi-check" : "mdi-close";
      return (
        '<span class="nsm-status-badge nsm-status-icon ' +
        stateClass +
        '" title="' +
        escapeHtml(label) +
        '" aria-label="' +
        escapeHtml(label) +
        '">' +
        '<i class="mdi ' +
        iconClass +
        '" aria-hidden="true"></i>' +
        '<span class="nsm-status-label">' +
        escapeHtml(label) +
        "</span></span>"
      );
    }

    var statusCellRenderer = function (params) {
      var wrap = document.createElement("div");
      wrap.className = "nsm-ag-status-cell";
      wrap.innerHTML = statusCellHtml(!!params.value);
      return wrap;
    };

    var nameLinkCellRenderer = function (params) {
      var wrap = document.createElement("div");
      wrap.className = "nsm-ag-name-cell w-100";
      var url = (params.data && params.data._detail_url) || "#";
      var name = params.value == null ? "" : String(params.value);
      wrap.innerHTML =
        '<a href="' +
        escapeHtml(url) +
        '" class="text-body">' +
        escapeHtml(name) +
        "</a>";
      return wrap;
    };

    var indexLinkCellRenderer = function (params) {
      var wrap = document.createElement("div");
      wrap.className = "nsm-ag-index-cell w-100";
      var url = (params.data && params.data._detail_url) || "#";
      var name = (params.data && params.data.name) || "";
      var idx = params.value == null ? "" : String(params.value);
      wrap.innerHTML =
        '<a href="' +
        escapeHtml(url) +
        '" class="nsm-ag-cell-link text-decoration-none" title="' +
        escapeHtml(name) +
        '">' +
        escapeHtml(idx) +
        "</a>";
      return wrap;
    };

    var descriptionCellRenderer = function (params) {
      var wrap = document.createElement("div");
      wrap.className = "nsm-ag-html-cell w-100";
      wrap.innerHTML = descriptionCellHtml(params.value);
      return wrap;
    };

    var actionsCellRenderer = function (params) {
      var wrap = document.createElement("div");
      wrap.className = "nsm-ag-actions-cell text-end text-nowrap";
      var data = params.data || {};
      var editUrl = data._edit_url || "#";
      var deleteUrl = data._delete_url || "#";
      var editBtn = canChange
        ? '<a class="btn btn-warning nsm-ag-action-edit" href="' +
          escapeHtml(editUrl) +
          '" title="Edit" aria-label="Edit"><i class="mdi mdi-pencil"></i></a>'
        : '<button type="button" class="btn btn-warning" disabled aria-disabled="true" title="Edit">' +
          '<i class="mdi mdi-pencil"></i></button>';
      var deleteBtn = canDelete
        ? '<a class="btn btn-danger nsm-ag-action-delete" href="' +
          escapeHtml(deleteUrl) +
          '" title="Delete" aria-label="Delete"><i class="mdi mdi-trash-can-outline"></i></a>'
        : '<button type="button" class="btn btn-danger" disabled aria-disabled="true" title="Delete">' +
          '<i class="mdi mdi-trash-can-outline"></i></button>';
      wrap.innerHTML =
        '<span class="btn-group btn-group-sm" role="group">' +
        editBtn +
        deleteBtn +
        "</span>";
      return wrap;
    };

    var layoutEl = gridEl.closest(".nsm-ag-grid-theme");
    applyNetBoxColorMode(layoutEl);

    var theme = resolveAgGridTheme();
    if (!theme) {
      applyLegacyThemeClass(gridEl, isNetBoxDark());
    }

    var gridOptions = {
      theme: theme || "legacy",
      columnDefs: columnDefs,
      rowData: payload.rowData || [],
      rowHeight: 42,
      defaultColDef: {
        minWidth: 72,
        sortable: true,
        filter: true,
        resizable: true,
        floatingFilter: true,
        enableCellChangeFlash: false,
        suppressHeaderMenuButton: false,
        editable: false,
        wrapText: false,
        autoHeight: false,
      },
      sideBar: {
        toolPanels: [
          {
            id: "columns",
            labelDefault: "Columns",
            labelKey: "columns",
            iconKey: "columns",
            toolPanel: "agColumnsToolPanel",
          },
          {
            id: "filters",
            labelDefault: "Filters",
            labelKey: "filters",
            iconKey: "filter",
            toolPanel: "agFiltersToolPanel",
          },
        ],
        defaultToolPanel: "columns",
        position: "right",
      },
      components: {
        htmlCell: htmlCellRenderer,
        statusCell: statusCellRenderer,
        nameLinkCell: nameLinkCellRenderer,
        indexLinkCell: indexLinkCellRenderer,
        descriptionCell: descriptionCellRenderer,
        actionsCell: actionsCellRenderer,
      },
      rowSelection: {
        mode: "multiRow",
        checkboxes: true,
        headerCheckbox: true,
        enableClickSelection: true,
      },
      suppressCellFocus: true,
      animateRows: false,
      getRowId: function (params) {
        return String(params.data.pk);
      },
      onGridReady: function (params) {
        gridApi = params.api;
        applyInitialFilterModel(params.api, config);
        updateRowStats(params.api, totalRowCount);
        updateClearFiltersButton(params.api, config);
        syncBulkSelection();
        schedulePolicyGridWidthFit(params.api, gridEl);
        if (window.innerWidth <= 1024 && typeof params.api.closeToolPanel === "function") {
          params.api.closeToolPanel();
        }
      },
      onFirstDataRendered: function (params) {
        applyInitialFilterModel(params.api, config);
        updateClearFiltersButton(params.api, config);
        schedulePolicyGridWidthFit(params.api, gridEl);
        resetPolicyRowHeights(params.api);
      },
      onColumnResized: function (params) {
        schedulePolicyGridWidthFit(params.api, gridEl);
        resetPolicyRowHeights(params.api);
      },
      onDisplayedColumnsChanged: function (params) {
        schedulePolicyGridWidthFit(params.api, gridEl);
        resetPolicyRowHeights(params.api);
      },
      onToolPanelVisibleChanged: function (params) {
        schedulePolicyGridWidthFit(params.api, gridEl);
      },
      onFilterChanged: function (params) {
        updateRowStats(params.api, totalRowCount);
        updateClearFiltersButton(params.api, config);
        resetPolicyRowHeights(params.api);
      },
      onSelectionChanged: function () {
        syncBulkSelection();
        if (gridApi) {
          updateRowStats(gridApi, totalRowCount);
        }
      },
    };

    var gridApi;
    try {
      gridApi = agGrid.createGrid(gridEl, gridOptions);
    } catch (err) {
      console.error("NSM policy grid: createGrid failed", err);
      gridEl.innerHTML =
        '<p class="text-danger p-3 mb-0">AG Grid Initialisierung fehlgeschlagen (Konsole prüfen).</p>';
      return;
    }

    var clearFiltersBtn = document.getElementById("nsm-ag-clear-filters");
    if (clearFiltersBtn) {
      clearFiltersBtn.addEventListener("click", function () {
        clearAllPolicyFilters(gridApi, config);
        updateClearFiltersButton(gridApi, config);
        updateRowStats(gridApi, totalRowCount);
      });
    }

    var bulkDeleteBtn = document.getElementById("nsm-bulk-delete-btn");
    if (bulkDeleteBtn) {
      bulkDeleteBtn.addEventListener("click", function (e) {
        if (bulkDeleteBtn.classList.contains("d-none")) {
          e.preventDefault();
          return;
        }
        var msg = bulkDeleteBtn.getAttribute("data-confirm") || "Delete selected rules?";
        if (!window.confirm(msg)) {
          e.preventDefault();
        }
      });
    }

    var addRuleLink = document.getElementById("nsm-ag-add-rule");
    if (addRuleLink && addRuleLink.classList.contains("disabled")) {
      addRuleLink.addEventListener("click", function (e) {
        e.preventDefault();
      });
    }

    watchNetBoxColorMode(function () {
      applyNetBoxColorMode(layoutEl);
      if (!theme) {
        applyLegacyThemeClass(gridEl, isNetBoxDark());
      }
    });

    function updateRowStats(api, total) {
      var rowEl = document.getElementById("nsm-ag-row-stats");
      var selEl = document.getElementById("nsm-ag-selected-stats");
      if (!rowEl) {
        return;
      }
      var displayed = 0;
      api.forEachNodeAfterFilter(function () {
        displayed += 1;
      });
      if (displayed === total) {
        rowEl.textContent = total + (total === 1 ? " row" : " rows");
      } else {
        rowEl.textContent = displayed + " of " + total + " rows";
      }
      if (selEl) {
        var n = api.getSelectedRows().length;
        if (n > 0) {
          selEl.textContent = n + (n === 1 ? " selected" : " selected");
        } else {
          selEl.textContent = "";
        }
      }
    }

    function syncBulkSelection() {
      var form = document.getElementById("nsm-bulk-delete-form");
      var deleteBtn = document.getElementById("nsm-bulk-delete-btn");
      var countEl = document.getElementById("nsm-selected-count");
      if (!form || !gridApi) {
        return;
      }
      form.querySelectorAll('input[name="pk"]').forEach(function (el) {
        el.remove();
      });
      var selected = gridApi.getSelectedRows();
      selected.forEach(function (row) {
        var input = document.createElement("input");
        input.type = "checkbox";
        input.name = "pk";
        input.value = String(row.pk);
        input.checked = true;
        input.hidden = true;
        form.appendChild(input);
      });
      var n = selected.length;
      if (countEl) {
        countEl.textContent = n > 0 ? String(n) + " " : "";
      }
      if (deleteBtn) {
        setToolbarButtonVisible(deleteBtn, canDelete && n > 0);
      }
    }
  }

  function applyNetBoxColorMode(layoutEl) {
    var mode = netBoxAgThemeMode();
    if (layoutEl) {
      layoutEl.setAttribute("data-ag-theme-mode", mode);
      layoutEl.setAttribute("data-nsm-color-mode", mode);
    }
  }

  function resolveAgGridTheme() {
    if (!agGrid.themeQuartz) {
      return undefined;
    }
    var theme = agGrid.themeQuartz;
    if (agGrid.colorSchemeVariable) {
      theme = theme.withPart(agGrid.colorSchemeVariable);
    }
    if (typeof theme.withParams !== "function") {
      return theme;
    }
    return theme
      .withParams(
        {
          browserColorScheme: "light",
          backgroundColor: "#ffffff",
          foregroundColor: "#1e293b",
          accentColor: "#206bc4",
          borderColor: "#cbd5e1",
          dataBackgroundColor: "#ffffff",
          headerBackgroundColor: "#f1f5f9",
          headerTextColor: "#1e293b",
          textColor: "#1e293b",
          cellTextColor: "#1e293b",
          chromeBackgroundColor: "#f8fafc",
          oddRowBackgroundColor: "rgba(0, 0, 0, 0.02)",
        },
        "light"
      )
      .withParams(
        {
          browserColorScheme: "dark",
          backgroundColor: "#1a2332",
          foregroundColor: "#e7ebf1",
          accentColor: "#5b9bd5",
          borderColor: "rgba(255, 255, 255, 0.16)",
          dataBackgroundColor: "#1a2332",
          headerBackgroundColor: "#243044",
          headerTextColor: "#e7ebf1",
          textColor: "#e7ebf1",
          cellTextColor: "#e7ebf1",
          chromeBackgroundColor: "#243044",
          oddRowBackgroundColor: "rgba(255, 255, 255, 0.03)",
        },
        "dark"
      );
  }

  function applyLegacyThemeClass(gridEl, isDark) {
    if (!gridEl) {
      return;
    }
    gridEl.classList.remove("ag-theme-quartz", "ag-theme-quartz-dark");
    gridEl.classList.add(isDark ? "ag-theme-quartz-dark" : "ag-theme-quartz");
    enableLegacyThemeCss();
  }

  function watchNetBoxColorMode(onChange) {
    if (typeof MutationObserver !== "undefined") {
      var observer = new MutationObserver(function (records) {
        for (var i = 0; i < records.length; i += 1) {
          if (records[i].attributeName === "data-bs-theme") {
            onChange();
            return;
          }
        }
      });
      observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-bs-theme"],
      });
    }
    document.querySelectorAll(".color-mode-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        window.setTimeout(onChange, 0);
      });
    });
  }

  function enableLegacyThemeCss() {
    var link = document.getElementById("nsm-ag-legacy-theme-css");
    if (link) {
      link.disabled = false;
    }
  }

  initPolicyAgGrid();
})();
