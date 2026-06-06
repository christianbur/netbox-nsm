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

  function matrixCellIsSelf(params) {
    var v = params.value;
    if (v && typeof v === "object" && v.isSelf) {
      return true;
    }
    var srcPk = params.data && params.data._sourcePk;
    var colId = params.colDef && params.colDef.colId;
    if (srcPk == null || !colId || colId.indexOf("dst_") !== 0) {
      return false;
    }
    var dstPk = parseInt(colId.slice(4), 10);
    return !isNaN(dstPk) && dstPk === srcPk;
  }

  function matrixCellIsEmpty(params) {
    var v = params.value;
    if (!v || typeof v !== "object") {
      return true;
    }
    return !!v.empty;
  }

  function matrixCellStyle(params) {
    var v = params.value;
    var style = {
      textAlign: "center",
      padding: "0",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    };
    if (!v || typeof v !== "object" || v.empty) {
      style.backgroundColor = "var(--nsm-matrix-empty-bg, #ffffff)";
      style.color = "var(--nsm-matrix-empty-text, #64748b)";
      return style;
    }
    if (v.isSelf) {
      style.boxShadow = "inset 0 0 0 2px var(--nsm-matrix-self-border, rgba(253, 126, 20, 0.72))";
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

  function applyMatrixZoneAccent(el, color) {
    if (!el || !color) {
      return;
    }
    el.classList.add("nsm-matrix-zone-accent");
    el.style.setProperty("--nsm-matrix-zone-accent", color);
  }

  function matrixSourceCellStyle(params) {
    if (!(params.data && params.data._sourceColor)) {
      return null;
    }
    return null;
  }

  function matrixCellRenderer(params) {
    var v = params.value;
    var wrap = document.createElement("div");
    wrap.className = "nsm-matrix-cell-inner w-100 h-100 d-flex align-items-center justify-content-center";
    if (!v || typeof v !== "object") {
      wrap.classList.add("nsm-matrix-cell-empty");
      wrap.textContent = "-";
      return wrap;
    }
    if (v.empty) {
      wrap.classList.add("nsm-matrix-cell-empty");
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
      applyMatrixZoneAccent(wrap, sourceColor);
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

  var matrixAxisFilterState = { sourceGroups: [], sourceQuery: "", gridApi: null };

  function parseAxisFilterGroups(query) {
    var raw = (query || "").trim();
    if (!raw) {
      return [];
    }
    return raw
      .split(/\s+OR\s+/i)
      .map(function (orPart) {
        return orPart
          .split(/\s+(?:AND|&&)\s+/i)
          .map(function (part) {
            return part.trim().toLowerCase();
          })
          .filter(Boolean);
      })
      .filter(function (group) {
        return group.length > 0;
      });
  }

  function matchesAxisFilterGroups(text, groups) {
    if (!groups.length) {
      return true;
    }
    var haystack = (text || "").toLowerCase();
    return groups.some(function (andTerms) {
      return andTerms.every(function (term) {
        return haystack.indexOf(term) !== -1;
      });
    });
  }

  function refreshInfiniteMatrixCache(gridApi) {
    if (!gridApi) {
      return;
    }
    if (typeof gridApi.purgeInfiniteCache === "function") {
      gridApi.purgeInfiniteCache();
    } else if (typeof gridApi.refreshInfiniteCache === "function") {
      gridApi.refreshInfiniteCache();
    }
  }

  function applySourceRowFilter(api, query) {
    matrixAxisFilterState.sourceGroups = parseAxisFilterGroups(query);
    matrixAxisFilterState.sourceQuery = (query || "").trim();
    var gridApi = api || matrixAxisFilterState.gridApi;
    if (!gridApi) {
      return;
    }
    if (typeof gridApi.refreshInfiniteCache === "function") {
      refreshInfiniteMatrixCache(gridApi);
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
    var groups = parseAxisFilterGroups(query);
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
      var show = matchesAxisFilterGroups(name, groups);
      if (typeof api.setColumnsVisible === "function") {
        api.setColumnsVisible([colId], show);
      }
    });
  }

  function MatrixDstHeader() {}

  MatrixDstHeader.prototype.init = function (params) {
    var wrap = document.createElement("div");
    wrap.className = "nsm-matrix-dst-header-inner";
    var colDef =
      params.column && typeof params.column.getColDef === "function"
        ? params.column.getColDef()
        : {};
    var displayName = params.displayName || colDef.headerName || "";
    var fullName = colDef.headerTooltip || displayName;
    var headerUrl = colDef.headerUrl || "#";
    var label = document.createElement("a");
    label.href = headerUrl;
    label.className = "nsm-matrix-axis-zone-label nsm-matrix-axis-zone-label-x text-decoration-none";
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
      applyMatrixZoneAccent(wrap, headerBg);
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
      'data-axis="x" placeholder="dmz OR mgmt" autocomplete="off">' +
      "</label>" +
      "</div>" +
      '<div class="nsm-matrix-corner-src-block">' +
      '<label class="nsm-matrix-axis-filter-label nsm-matrix-axis-filter-label-src">' +
      '<span class="visually-hidden">Source filter</span>' +
      '<input type="search" class="form-control form-control-sm nsm-matrix-axis-filter" ' +
      'data-axis="y" placeholder="dmz OR mgmt" autocomplete="off">' +
      "</label>" +
      '<span class="nsm-matrix-corner-axis-label">&darr; Source</span>' +
      "</div>";

    var yInput = wrap.querySelector('[data-axis="y"]');
    var xInput = wrap.querySelector('[data-axis="x"]');
    var api = params.api;

    var sourceFilterTimer = null;
    yInput.addEventListener("input", function () {
      if (sourceFilterTimer) {
        clearTimeout(sourceFilterTimer);
      }
      sourceFilterTimer = setTimeout(function () {
        applySourceRowFilter(null, yInput.value);
      }, 300);
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
      return null;
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
      return null;
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

  function isEmbeddedRulesMatrix(gridEl) {
    return !!(gridEl && gridEl.closest(".nsm-rules-matrix-wrap"));
  }

  function matrixGridMaxHeightPx(gridEl) {
    if (isEmbeddedRulesMatrix(gridEl)) {
      return null;
    }
    return Math.min(Math.round(window.innerHeight * 0.75), 720);
  }

  function fitMatrixGridHeight(gridEl, headerHeight, rowHeight, rowCount, maxHeightPx) {
    if (!gridEl || rowCount < 0) {
      return;
    }
    var contentPx = headerHeight + rowCount * rowHeight;
    var heightPx =
      maxHeightPx == null ? contentPx : Math.min(contentPx, maxHeightPx);
    gridEl.style.height = Math.ceil(heightPx) + "px";
    gridEl.style.minHeight = "0";
    gridEl.style.maxHeight = Math.ceil(heightPx) + "px";
    gridEl.style.overflow = "hidden";
  }

  function resolveMatrixGridRowCount(state) {
    if (!state) {
      return 0;
    }
    var rowCount = state.knownTotalRows;
    if (state.gridApi && typeof state.gridApi.getDisplayedRowCount === "function") {
      var displayed = state.gridApi.getDisplayedRowCount();
      if (typeof displayed === "number" && displayed >= 0) {
        rowCount = displayed;
      }
    }
    return rowCount;
  }

  function clipMatrixGridBodyToRows(gridEl, rowCount, rowHeight) {
    if (!gridEl || !(rowCount > 0) || !(rowHeight > 0)) {
      return;
    }
    var bodyPx = Math.ceil(rowCount * rowHeight) + "px";
    [
      ".ag-body-viewport",
      ".ag-center-cols-viewport",
      ".ag-center-cols-container",
      ".ag-pinned-left-cols-viewport",
      ".ag-pinned-left-cols-container",
    ].forEach(function (sel) {
      var el = gridEl.querySelector(sel);
      if (!el) {
        return;
      }
      el.style.height = bodyPx;
      el.style.maxHeight = bodyPx;
      el.style.minHeight = bodyPx;
      el.style.overflow = "hidden";
    });
  }

  function applyMatrixGridHeightLayout(state, headerHeight, rowHeight) {
    if (!state || !state.gridEl) {
      return;
    }
    var rowCount = resolveMatrixGridRowCount(state);
    if (!(rowCount > 0)) {
      return;
    }
    fitMatrixGridHeight(
      state.gridEl,
      headerHeight,
      rowHeight,
      rowCount,
      matrixGridMaxHeightPx(state.gridEl)
    );
    clipMatrixGridBodyToRows(state.gridEl, rowCount, rowHeight);
  }

  function syncMatrixGridHeight(state, headerHeight, rowHeight) {
    applyMatrixGridHeightLayout(state, headerHeight, rowHeight);
    if (typeof requestAnimationFrame !== "function") {
      return;
    }
    requestAnimationFrame(function () {
      applyMatrixGridHeightLayout(state, headerHeight, rowHeight);
    });
  }

  function buildMatrixGridFetchUrl(config, startRow, endRow) {
    if (!config || !config.gridDataUrl) {
      return null;
    }
    var pageParams = new URLSearchParams(window.location.search);
    var qs = pageParams.toString();
    var srcQ = matrixAxisFilterState.sourceQuery || "";
    var url =
      config.gridDataUrl +
      (qs ? "?" + qs + "&" : "?") +
      "startRow=" +
      encodeURIComponent(startRow) +
      "&endRow=" +
      encodeURIComponent(endRow);
    if (config.objType && !pageParams.has("obj_type")) {
      url += "&obj_type=" + encodeURIComponent(String(config.objType));
    }
    if (srcQ) {
      url += "&src_q=" + encodeURIComponent(srcQ);
    }
    return url;
  }

  function matrixDstField(col) {
    if (!col) {
      return "";
    }
    return col.field || col.colId || "";
  }

  function resolveMatrixDstColumns(state, gridApi) {
    if (gridApi && typeof gridApi.getAllDisplayedColumns === "function") {
      var displayed = (gridApi.getAllDisplayedColumns() || []).filter(function (col) {
        var colId = typeof col.getColId === "function" ? col.getColId() : "";
        return colId && colId.indexOf("dst_") === 0;
      });
      if (displayed.length) {
        return displayed.map(function (col) {
          var def = typeof col.getColDef === "function" ? col.getColDef() : {};
          return {
            field: def.field || col.getColId(),
            colId: col.getColId(),
            headerName: def.headerName,
            headerTooltip: def.headerTooltip,
          };
        });
      }
    }
    var defs =
      (state && state.columnDefs) ||
      (state && state.payload && state.payload.columnDefs) ||
      [];
    return (defs || [])
      .filter(function (col) {
        var field = matrixDstField(col);
        return field && field.indexOf("dst_") === 0;
      })
      .map(function (col) {
        return Object.assign({}, col, { field: matrixDstField(col) });
      });
  }

  function collectMatrixRowsFromGridApi(gridApi) {
    var rows = [];
    if (!gridApi || typeof gridApi.forEachNode !== "function") {
      return rows;
    }
    gridApi.forEachNode(function (node) {
      if (node && node.data) {
        rows.push(node.data);
      }
    });
    return rows;
  }

  function createMatrixDatasource(config, state) {
    return {
      getRows: function (params) {
        var url = buildMatrixGridFetchUrl(config, params.startRow, params.endRow);
        if (!url) {
          params.failCallback();
          return;
        }
        if (state && state.gridEl) {
          state.gridEl.classList.add("nsm-ag-grid-loading");
        }
        fetch(url, {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        })
          .then(function (response) {
            if (!response.ok) {
              throw new Error("matrix grid fetch failed");
            }
            return response.json();
          })
          .then(function (data) {
            if (state) {
              state.knownTotalRows =
                typeof data.lastRow === "number"
                  ? data.lastRow
                  : params.endRow;
              if (state.headerHeight != null && state.rowHeight != null) {
                syncMatrixGridHeight(state, state.headerHeight, state.rowHeight);
              }
            }
            params.successCallback(data.rowData || [], data.lastRow);
          })
          .catch(function (err) {
            console.error("NSM matrix grid: datasource fetch failed", err);
            params.failCallback();
          })
          .finally(function () {
            if (state && state.gridEl) {
              state.gridEl.classList.remove("nsm-ag-grid-loading");
            }
          });
      },
    };
  }

  function createEmbeddedMatrixAgGrid(gridEl, payload, config) {
    if (!payload || !gridEl) {
      return null;
    }
    config = config || {};
    if (typeof agGrid === "undefined" || typeof agGrid.createGrid !== "function") {
      gridEl.innerHTML =
        '<p class="text-danger p-3 mb-0">AG Grid konnte nicht geladen werden.</p>';
      return null;
    }

    var layoutEl = gridEl.closest(".nsm-matrix-ag-theme");
    applyNetBoxColorMode(layoutEl);

    var theme = resolveAgGridTheme();
    if (!theme) {
      applyLegacyThemeClass(gridEl, isNetBoxDark());
    }

    var columnDefs = (payload.columnDefs || []).map(function (col) {
      if (col.field && col.field.indexOf("dst_") === 0) {
        return Object.assign({}, col, {
          cellStyle: matrixCellStyle,
          cellClassRules: {
            "nsm-matrix-self": matrixCellIsSelf,
            "nsm-matrix-empty": matrixCellIsEmpty,
          },
        });
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

    var useInfinite = !!(config.infiniteRowModel && config.gridDataUrl);
    var datasourceState = {
      gridEl: gridEl,
      knownTotalRows: config.totalRows || 0,
      columnDefs: columnDefs,
      payload: payload,
      headerHeight: headerHeight,
      rowHeight: rowHeight,
    };

    var gridOptions = {
      theme: theme || "legacy",
      context: {
        matrixGridMeta: payload.gridMeta || {},
      },
      columnDefs: columnDefs,
      debounceVerticalScrollbar: true,
      suppressHorizontalScroll: true,
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
        datasourceState.gridApi = params.api;
        fitMatrixGridWidth(gridEl, columnDefs, sourceColWidth, dstColWidth);
        syncMatrixGridHeight(datasourceState, headerHeight, rowHeight);
        if (useInfinite && matrixAxisFilterState.sourceQuery) {
          refreshInfiniteMatrixCache(params.api);
        }
      },
      onModelUpdated: function () {
        syncMatrixGridHeight(datasourceState, headerHeight, rowHeight);
      },
    };

    if (!useInfinite) {
      gridOptions.isExternalFilterPresent = function () {
        return matrixAxisFilterState.sourceGroups.length > 0;
      };
      gridOptions.doesExternalFilterPass = function (node) {
        return matchesAxisFilterGroups(
          node.data && node.data._sourceLabel,
          matrixAxisFilterState.sourceGroups
        );
      };
    }

    if (useInfinite) {
      gridOptions.rowModelType = "infinite";
      gridOptions.cacheBlockSize = config.cacheBlockSize || 50;
      gridOptions.maxBlocksInCache = 10;
      gridOptions.infiniteInitialRowCount = 1;
      gridOptions.datasource = createMatrixDatasource(config, datasourceState);
      gridOptions.getRowId = function (params) {
        return String(
          (params.data && params.data._sourceLabel) || params.data._sourceDisplayLabel
        );
      };
    } else {
      gridOptions.rowData = payload.rowData || [];
      datasourceState.knownTotalRows = (payload.rowData || []).length;
      syncMatrixGridHeight(datasourceState, headerHeight, rowHeight);
    }

    var gridApi;
    try {
      gridApi = agGrid.createGrid(gridEl, gridOptions);
    } catch (err) {
      console.error("NSM matrix grid: createGrid failed", err);
      gridEl.innerHTML =
        '<p class="text-danger p-3 mb-0">Matrix-Grid Initialisierung fehlgeschlagen.</p>';
      return null;
    }

    watchNetBoxColorMode(function () {
      applyNetBoxColorMode(layoutEl);
      if (!theme) {
        applyLegacyThemeClass(gridEl, isNetBoxDark());
      }
    });

    return {
      api: gridApi,
      state: datasourceState,
      destroy: function () {
        if (gridApi && typeof gridApi.destroy === "function") {
          gridApi.destroy();
        }
        gridEl.innerHTML = "";
        if (matrixAxisFilterState.gridApi === gridApi) {
          matrixAxisFilterState.gridApi = null;
        }
      },
    };
  }

  function fetchAllMatrixRows(config, state) {
    var total = (state && state.knownTotalRows) || 0;
    if (total <= 0) {
      total = 500;
    }
    var url = buildMatrixGridFetchUrl(config, 0, total);
    if (!url) {
      return Promise.resolve([]);
    }
    return fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("matrix export fetch failed");
        }
        return response.json();
      })
      .then(function (data) {
        return data.rowData || [];
      });
  }

  function matrixCellCsvValue(cellValue) {
    if (!cellValue || typeof cellValue !== "object") {
      return "";
    }
    if (cellValue.empty) {
      return "";
    }
    var text = "";
    if (cellValue.directedLines && cellValue.directedLines.length) {
      text = cellValue.directedLines
        .filter(function (line) {
          return line && !line.empty;
        })
        .map(function (line) {
          return line.label || "";
        })
        .join(" / ");
    } else if (cellValue.label && cellValue.label !== "+") {
      text = cellValue.label;
    }
    var colors = [];
    if (cellValue.bg) {
      colors.push(String(cellValue.bg));
    }
    if (cellValue.bgSecondary && cellValue.bgSecondary !== cellValue.bg) {
      colors.push(String(cellValue.bgSecondary));
    }
    if (text && colors.length) {
      return text + " [" + colors.join("|") + "]";
    }
    return text;
  }

  function buildMatrixCsv(dstCols, rows) {
    dstCols = dstCols || [];
    var headers = ["Source"].concat(
      dstCols.map(function (col) {
        return col.headerTooltip || col.headerName || matrixDstField(col) || "";
      })
    );
    var lines = [headers.map(csvEscapeField).join(",")];
    (rows || []).forEach(function (row) {
      var line = [row._sourceLabel || row._sourceDisplayLabel || ""];
      dstCols.forEach(function (col) {
        var field = matrixDstField(col);
        line.push(matrixCellCsvValue(row[field]));
      });
      lines.push(line.map(csvEscapeField).join(","));
    });
    return lines.join("\n");
  }

  function csvEscapeField(value) {
    var text = value == null ? "" : String(value);
    if (/[",\n\r]/.test(text)) {
      return '"' + text.replace(/"/g, '""') + '"';
    }
    return text;
  }

  function exportMatrixCsv(config, state, filename) {
    var gridApi = state && state.gridApi;
    var dstCols = resolveMatrixDstColumns(state, gridApi);
    var gridRows = collectMatrixRowsFromGridApi(gridApi);
    var knownTotal = (state && state.knownTotalRows) || 0;

    function finish(rows) {
      downloadCsvBlob(buildMatrixCsv(dstCols, rows), filename);
    }

    if (gridRows.length && (!knownTotal || gridRows.length >= knownTotal)) {
      finish(gridRows);
      return Promise.resolve();
    }

    return fetchAllMatrixRows(config, state)
      .then(function (rows) {
        finish(rows.length ? rows : gridRows);
      })
      .catch(function (err) {
        console.error("NSM matrix CSV export failed", err);
        if (gridRows.length) {
          finish(gridRows);
          return;
        }
        finish([]);
      });
  }

  function downloadCsvBlob(csv, filename) {
    var blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = filename || "export.csv";
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function applyMatrixAxisFilters(api, srcQ, dstQ) {
    applySourceRowFilter(api, srcQ || "");
    applyDestColumnFilter(api, dstQ || "");
  }

  function readMatrixAxisFiltersFromUrl() {
    if (typeof window === "undefined") {
      return { srcQ: "", dstQ: "" };
    }
    var params = new URLSearchParams(window.location.search);
    return {
      srcQ: params.get("src_q") || "",
      dstQ: params.get("dst_q") || "",
    };
  }

  function clearMatrixAxisFilters(api) {
    applyMatrixAxisFilters(api, "", "");
  }

  function initMatrixAgGrid() {
    var payload = readJsonScript("nsm-matrix-grid-data");
    var config = readJsonScript("nsm-matrix-grid-config") || {};
    var gridEl = document.getElementById("nsm-matrix-ag-grid");
    if (!payload || !gridEl) {
      return;
    }
    createEmbeddedMatrixAgGrid(gridEl, payload, config);
  }

  window.NSM_MATRIX_AG = {
    createEmbeddedMatrixAgGrid: createEmbeddedMatrixAgGrid,
    exportMatrixCsv: exportMatrixCsv,
    downloadCsvBlob: downloadCsvBlob,
    csvEscapeField: csvEscapeField,
    buildMatrixCsv: buildMatrixCsv,
    matrixCellCsvValue: matrixCellCsvValue,
    resolveMatrixDstColumns: resolveMatrixDstColumns,
    collectMatrixRowsFromGridApi: collectMatrixRowsFromGridApi,
    applyMatrixAxisFilters: applyMatrixAxisFilters,
    readMatrixAxisFiltersFromUrl: readMatrixAxisFiltersFromUrl,
    clearMatrixAxisFilters: clearMatrixAxisFilters,
  };

  initMatrixAgGrid();
})();
