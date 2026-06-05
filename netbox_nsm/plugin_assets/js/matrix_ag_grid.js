/**
 * AG Grid Zone Matrix — Community (MIT). Full-cell background fill per rule action.
 */
(function () {
  "use strict";

  function isNetBoxDark() {
    return document.documentElement.getAttribute("data-bs-theme") === "dark";
  }

  function readJsonScript(id) {
    var el = document.getElementById(id);
    if (!el) {
      return null;
    }
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.error("NSM matrix grid: invalid JSON in #" + id, e);
      return null;
    }
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function matrixCellStyle(params) {
    var v = params.value;
    if (!v || typeof v !== "object") {
      return null;
    }
    var style = {
      textAlign: "center",
      padding: "0",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    };
    if (v.isSelf) {
      style.boxShadow = "inset 0 0 0 2px rgba(251, 191, 36, 0.65)";
    }
    if (v.empty) {
      style.backgroundColor = "transparent";
      style.color = "var(--nsm-matrix-empty-text, #64748b)";
      return style;
    }
    if (v.bgSecondary && v.bg) {
      style.background = "linear-gradient(to bottom, " + v.bg + " 50%, " + v.bgSecondary + " 50%)";
    } else if (v.bg) {
      style.backgroundColor = v.bg;
    }
    style.color = "#fff";
    style.fontWeight = "600";
    style.fontSize = "0.58rem";
    style.lineHeight = "1.15";
    return style;
  }

  function matrixSourceCellStyle(params) {
    var color = params.data && params.data._sourceColor;
    if (!color) {
      return null;
    }
    return {
      backgroundColor: color,
      color: "#fff",
    };
  }

  function matrixCellRenderer(params) {
    var v = params.value;
    var wrap = document.createElement("div");
    wrap.className = "nsm-matrix-cell-inner w-100 h-100 d-flex align-items-center justify-content-center";
    if (!v || typeof v !== "object") {
      wrap.textContent = "-";
      return wrap;
    }

    if (v.directedLines && v.directedLines.length) {
      var stack = document.createElement("div");
      stack.className = "nsm-matrix-cell-directed w-100 h-100";
      v.directedLines.forEach(function (line) {
        var link = document.createElement("a");
        link.href = line.href || "#";
        link.className =
          "nsm-matrix-cell-link nsm-matrix-cell-link-directed text-decoration-none d-flex align-items-center justify-content-center px-1";
        link.textContent = line.label || "";
        link.title = line.title || line.label || "";
        if (line.empty) {
          link.classList.add("nsm-matrix-cell-link-empty");
        }
        stack.appendChild(link);
      });
      wrap.appendChild(stack);
      return wrap;
    }

    var link = document.createElement("a");
    link.href = v.href || "#";
    link.className = "nsm-matrix-cell-link text-decoration-none w-100 h-100 d-flex align-items-center justify-content-center px-1";
    link.textContent = v.label || "";
    link.title = v.title || v.label || "";
    if (v.empty) {
      link.classList.add("nsm-matrix-cell-link-empty");
    }
    wrap.appendChild(link);
    return wrap;
  }

  function matrixRowLabelCellRenderer(params) {
    var wrap = document.createElement("div");
    wrap.className = "nsm-matrix-row-label-inner";
    var url = (params.data && params.data._sourceUrl) || "#";
    var fullName =
      (params.data && params.data._sourceLabel) ||
      (params.value == null ? "" : String(params.value));
    var displayName = params.value == null ? "" : String(params.value);
    var sourceColor = params.data && params.data._sourceColor;
    if (sourceColor) {
      wrap.style.backgroundColor = sourceColor;
    }
    wrap.innerHTML =
      '<a href="' +
      escapeHtml(url) +
      '" class="nsm-matrix-axis-zone-label nsm-matrix-axis-zone-label-y' +
      (sourceColor ? " nsm-matrix-axis-zone-label-colored" : "") +
      '" title="' +
      escapeHtml(fullName) +
      '">' +
      escapeHtml(displayName) +
      "</a>";
    return wrap;
  }

  var matrixAxisFilterState = { sourceTerms: [], gridApi: null };

  function parseAxisFilterTerms(query) {
    var raw = (query || "").trim();
    if (!raw) {
      return [];
    }
    return raw
      .split(/\s+(?:AND|&&)\s+/i)
      .map(function (part) {
        return part.trim().toLowerCase();
      })
      .filter(Boolean);
  }

  function matchesAllAxisTerms(text, terms) {
    if (!terms.length) {
      return true;
    }
    var haystack = (text || "").toLowerCase();
    return terms.every(function (term) {
      return haystack.indexOf(term) !== -1;
    });
  }

  function applySourceRowFilter(api, query) {
    matrixAxisFilterState.sourceTerms = parseAxisFilterTerms(query);
    var gridApi = api || matrixAxisFilterState.gridApi;
    if (!gridApi) {
      return;
    }
    // Reset rows that may have been hidden by an older setDisplayed() path
    if (typeof gridApi.forEachNode === "function") {
      gridApi.forEachNode(function (node) {
        if (node && typeof node.setDisplayed === "function") {
          node.setDisplayed(true);
        }
      });
    }
    if (typeof gridApi.onFilterChanged === "function") {
      gridApi.onFilterChanged();
    } else if (typeof gridApi.refreshClientSideRowModel === "function") {
      gridApi.refreshClientSideRowModel("filter");
    }
  }

  function applyDestColumnFilter(api, query) {
    if (!api) {
      return;
    }
    var terms = parseAxisFilterTerms(query);
    var cols = typeof api.getColumns === "function" ? api.getColumns() : [];
    cols.forEach(function (col) {
      if (!col || typeof col.getColId !== "function") {
        return;
      }
      var colId = col.getColId();
      if (colId.indexOf("dst_") !== 0) {
        return;
      }
      var def = typeof col.getColDef === "function" ? col.getColDef() : {};
      var name = def.headerTooltip || def.headerName || "";
      var show = matchesAllAxisTerms(name, terms);
      if (typeof api.setColumnsVisible === "function") {
        api.setColumnsVisible([colId], show);
      }
    });
  }

  function MatrixDstHeader() {}

  MatrixDstHeader.prototype.init = function (params) {
    var wrap = document.createElement("div");
    wrap.className = "nsm-matrix-dst-header-inner";
    var label = document.createElement("span");
    label.className = "nsm-matrix-axis-zone-label nsm-matrix-axis-zone-label-x";
    var colDef =
      params.column && typeof params.column.getColDef === "function"
        ? params.column.getColDef()
        : {};
    var displayName = params.displayName || colDef.headerName || "";
    var fullName = colDef.headerTooltip || displayName;
    label.textContent = displayName;
    label.title = fullName;
    var layoutEl = params.eGridCell && params.eGridCell.closest(".nsm-matrix-ag-theme");
    var gridMeta = params.context && params.context.matrixGridMeta;
    var maxTextLen = (gridMeta && gridMeta.maxTextLen) || 50;
    var wordLen = matrixLongestWordLen(displayName, maxTextLen);
    var labelSpan = matrixAxisExtent(wordLen, gridMeta, layoutEl);
    label.style.maxHeight = labelSpan + "px";
    var headerBg = colDef.headerBackgroundColor;
    if (headerBg) {
      wrap.style.backgroundColor = headerBg;
      label.classList.add("nsm-matrix-axis-zone-label-colored");
    }
    wrap.appendChild(label);
    this.eGui = wrap;
  };

  MatrixDstHeader.prototype.getGui = function () {
    return this.eGui;
  };

  MatrixDstHeader.prototype.destroy = function () {
    this.eGui = null;
  };

  function MatrixCornerHeader() {}

  MatrixCornerHeader.prototype.init = function (params) {
    var wrap = document.createElement("div");
    wrap.className = "nsm-matrix-corner-header-wrap";
    wrap.innerHTML =
      '<svg class="nsm-matrix-corner-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">' +
      '<line x1="0" y1="0" x2="100" y2="100" stroke="#374a5f" stroke-width="1.5" vector-effect="non-scaling-stroke"/>' +
      "</svg>" +
      '<div class="nsm-matrix-corner-dst-block">' +
      '<span class="nsm-matrix-corner-axis-label">Destination &rarr;</span>' +
      '<label class="nsm-matrix-axis-filter-label nsm-matrix-axis-filter-label-dst">' +
      '<span class="visually-hidden">Destination filter</span>' +
      '<input type="search" class="form-control form-control-sm nsm-matrix-axis-filter" ' +
      'data-axis="x" placeholder="Filter …" autocomplete="off">' +
      "</label>" +
      "</div>" +
      '<div class="nsm-matrix-corner-src-block">' +
      '<label class="nsm-matrix-axis-filter-label nsm-matrix-axis-filter-label-src">' +
      '<span class="visually-hidden">Source filter</span>' +
      '<input type="search" class="form-control form-control-sm nsm-matrix-axis-filter" ' +
      'data-axis="y" placeholder="Filter …" autocomplete="off">' +
      "</label>" +
      '<span class="nsm-matrix-corner-axis-label">&darr; Source</span>' +
      "</div>";

    var yInput = wrap.querySelector('[data-axis="y"]');
    var xInput = wrap.querySelector('[data-axis="x"]');
    var api = params.api;

    yInput.addEventListener("input", function () {
      applySourceRowFilter(null, yInput.value);
    });
    xInput.addEventListener("input", function () {
      applyDestColumnFilter(matrixAxisFilterState.gridApi || api, xInput.value);
    });

    [yInput, xInput].forEach(function (input) {
      input.addEventListener("click", function (e) {
        e.stopPropagation();
      });
    });

    this.eGui = wrap;
  };

  MatrixCornerHeader.prototype.getGui = function () {
    return this.eGui;
  };

  MatrixCornerHeader.prototype.destroy = function () {
    this.eGui = null;
  };

  function applyNetBoxColorMode(layoutEl) {
    if (layoutEl) {
      layoutEl.setAttribute(
        "data-ag-theme-mode",
        isNetBoxDark() ? "dark" : "light"
      );
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
          borderColor: "#cbd5e1",
          headerBackgroundColor: "#1e2a38",
          headerTextColor: "#c8d8e8",
          textColor: "#1e293b",
          cellTextColor: "#1e293b",
        },
        "light"
      )
      .withParams(
        {
          browserColorScheme: "dark",
          backgroundColor: "#1a2332",
          foregroundColor: "#e7ebf1",
          borderColor: "rgba(255, 255, 255, 0.16)",
          headerBackgroundColor: "#1e2a38",
          headerTextColor: "#c8d8e8",
          textColor: "#e7ebf1",
          cellTextColor: "#e7ebf1",
        },
        "dark"
      );
  }

  function enableLegacyThemeCss() {
    var link = document.getElementById("nsm-matrix-ag-legacy-theme-css");
    if (link) {
      link.disabled = false;
    }
  }

  function applyLegacyThemeClass(gridEl, dark) {
    if (!gridEl) {
      return;
    }
    gridEl.classList.remove("ag-theme-quartz", "ag-theme-quartz-dark");
    gridEl.classList.add(dark ? "ag-theme-quartz-dark" : "ag-theme-quartz");
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

  function matrixAxisCharStepPx(layoutEl, gridMeta) {
    if (gridMeta && gridMeta.axisCharStepPx) {
      return gridMeta.axisCharStepPx;
    }
    var rootPx = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    if (layoutEl) {
      var raw = getComputedStyle(layoutEl)
        .getPropertyValue("--nsm-matrix-axis-header-font")
        .trim();
      if (raw) {
        var px = raw.endsWith("rem") ? parseFloat(raw) * rootPx : parseFloat(raw);
        if (!isNaN(px)) {
          return Math.round(px);
        }
      }
    }
    return 22;
  }

  function matrixLongestWordLen(text, maxLen) {
    var cap = maxLen || 50;
    var capped = (text || "").slice(0, cap);
    var words = capped.trim().split(/\s+/).filter(Boolean);
    if (!words.length) {
      return capped.trim().length;
    }
    return words.reduce(function (max, word) {
      return word.length > max ? word.length : max;
    }, 0);
  }

  function matrixAxisExtent(wordLen, gridMeta, layoutEl) {
    var pad = (gridMeta && gridMeta.headerPadPx) || 10;
    var charStep = matrixAxisCharStepPx(layoutEl, gridMeta);
    var minCell = (gridMeta && gridMeta.cellSizeMin) || 48;
    var maxPx = (gridMeta && gridMeta.axisMaxPx) || 140;
    if (!wordLen) {
      return minCell;
    }
    var px = Math.max(wordLen * charStep + pad, minCell);
    return Math.min(px, maxPx);
  }

  function computeMatrixHeaderHeight(columnDefs, gridMeta, layoutEl) {
    if (gridMeta && gridMeta.headerHeight) {
      return gridMeta.headerHeight;
    }
    var cornerMin = (gridMeta && gridMeta.cornerHeaderMinPx) || 96;
    var maxTextLen = (gridMeta && gridMeta.maxTextLen) || 50;
    var maxWordLen = 0;
    (columnDefs || []).forEach(function (col) {
      if (col.field && col.field.indexOf("dst_") === 0) {
        var text = col.headerName || "";
        var len = matrixLongestWordLen(text, maxTextLen);
        if (len > maxWordLen) {
          maxWordLen = len;
        }
      }
    });
    if (!maxWordLen) {
      return cornerMin;
    }
    return Math.max(matrixAxisExtent(maxWordLen, gridMeta, layoutEl), cornerMin);
  }

  function fitMatrixGridWidth(gridEl, columnDefs, sourceColWidth, dstColWidth) {
    if (!gridEl || !columnDefs) {
      return;
    }
    var dstCount = 0;
    columnDefs.forEach(function (col) {
      if (col.field && col.field.indexOf("dst_") === 0) {
        dstCount += 1;
      }
    });
    var total = sourceColWidth + dstCount * dstColWidth + 2;
    gridEl.style.width = Math.ceil(total) + "px";
  }

  function initMatrixAgGrid() {
    var payload = readJsonScript("nsm-matrix-grid-data");
    var gridEl = document.getElementById("nsm-matrix-ag-grid");
    if (!payload || !gridEl) {
      return;
    }
    if (typeof agGrid === "undefined" || typeof agGrid.createGrid !== "function") {
      gridEl.innerHTML =
        '<p class="text-danger p-3 mb-0">AG Grid konnte nicht geladen werden.</p>';
      return;
    }

    var layoutEl = gridEl.closest(".nsm-matrix-ag-theme");
    applyNetBoxColorMode(layoutEl);

    var theme = resolveAgGridTheme();
    if (!theme) {
      applyLegacyThemeClass(gridEl, isNetBoxDark());
    }

    var columnDefs = (payload.columnDefs || []).map(function (col) {
      if (col.field && col.field.indexOf("dst_") === 0) {
        return Object.assign({}, col, { cellStyle: matrixCellStyle });
      }
      if (col.field === "_sourceDisplayLabel") {
        return Object.assign({}, col, {
          cellStyle: matrixSourceCellStyle,
          cellClassRules: {
            "nsm-matrix-source-colored": function (params) {
              return !!(params.data && params.data._sourceColor);
            },
          },
        });
      }
      return col;
    });

    var headerHeight = computeMatrixHeaderHeight(
      payload.columnDefs,
      payload.gridMeta,
      layoutEl
    );
    var rowHeight =
      payload.gridMeta && payload.gridMeta.rowHeight
        ? payload.gridMeta.rowHeight
        : payload.gridMeta && payload.gridMeta.cellSize
          ? payload.gridMeta.cellSize
          : 48;
    var dstColWidth =
      payload.gridMeta && payload.gridMeta.dstColWidth
        ? payload.gridMeta.dstColWidth
        : 48;
    var sourceColWidth =
      payload.gridMeta && payload.gridMeta.sourceColWidth
        ? payload.gridMeta.sourceColWidth
        : (payload.gridMeta && payload.gridMeta.cornerFilterMinWidthPx) || 230;
    if (layoutEl) {
      layoutEl.style.setProperty("--nsm-matrix-header-height", headerHeight + "px");
      layoutEl.style.setProperty(
        "--nsm-matrix-axis-header-span",
        headerHeight + "px"
      );
      var cornerFilterMinW =
        (payload.gridMeta && payload.gridMeta.cornerFilterMinWidthPx) || 230;
      var cornerFilterMinH = headerHeight;
      layoutEl.style.setProperty(
        "--nsm-matrix-corner-filter-min-width",
        cornerFilterMinW + "px"
      );
      layoutEl.style.setProperty(
        "--nsm-matrix-corner-filter-min-height",
        cornerFilterMinH + "px"
      );
      layoutEl.style.setProperty("--nsm-matrix-row-height", rowHeight + "px");
      layoutEl.style.setProperty("--nsm-matrix-dst-col-width", dstColWidth + "px");
      layoutEl.style.setProperty("--nsm-matrix-source-col-width", sourceColWidth + "px");
    }

    var gridOptions = {
      theme: theme || "legacy",
      context: { matrixGridMeta: payload.gridMeta || {} },
      columnDefs: columnDefs,
      rowData: payload.rowData || [],
      suppressColumnMoveAnimation: true,
      suppressMovableColumns: true,
      suppressDragLeaveHidesColumns: true,
      defaultColDef: {
        resizable: false,
        sortable: false,
        filter: false,
        suppressMovable: true,
        lockPosition: true,
        suppressHeaderMenuButton: true,
      },
      components: {
        matrixCell: matrixCellRenderer,
        matrixRowLabelCell: matrixRowLabelCellRenderer,
        matrixCornerHeader: MatrixCornerHeader,
        matrixDstHeader: MatrixDstHeader,
      },
      suppressCellFocus: true,
      animateRows: false,
      domLayout: "normal",
      headerHeight: headerHeight,
      rowHeight: rowHeight,
      onGridReady: function (params) {
        matrixAxisFilterState.gridApi = params.api;
        fitMatrixGridWidth(gridEl, columnDefs, sourceColWidth, dstColWidth);
      },
      isExternalFilterPresent: function () {
        return matrixAxisFilterState.sourceTerms.length > 0;
      },
      doesExternalFilterPass: function (node) {
        return matchesAllAxisTerms(
          node.data && node.data._sourceLabel,
          matrixAxisFilterState.sourceTerms
        );
      },
    };

    try {
      agGrid.createGrid(gridEl, gridOptions);
    } catch (err) {
      console.error("NSM matrix grid: createGrid failed", err);
      gridEl.innerHTML =
        '<p class="text-danger p-3 mb-0">Matrix-Grid Initialisierung fehlgeschlagen.</p>';
      return;
    }

    watchNetBoxColorMode(function () {
      applyNetBoxColorMode(layoutEl);
      if (!theme) {
        applyLegacyThemeClass(gridEl, isNetBoxDark());
      }
    });
  }

  initMatrixAgGrid();
})();
