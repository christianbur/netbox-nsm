/**
 * AG Grid Rules tab — Community only (MIT). NetBox color-mode via data-ag-theme-mode.
 */
(function () {
  "use strict";

  var NSM_GRID_PROFILES = {
    rules: {
      payloadScript: "nsm-rulebook-rules-grid-data",
      configScript: "nsm-rulebook-rules-grid-config",
      gridId: "nsm-rules-ag-grid",
      loadStatusId: "nsm-ag-load-status",
      loadTrackId: "nsm-ag-load-track",
      loadProgressId: "nsm-ag-load-progress",
      loadLabelId: "nsm-ag-load-label",
      rowStatsId: "nsm-ag-row-stats",
      selectedStatsId: "nsm-ag-selected-stats",
      loadMoreBtnId: "nsm-ag-load-more",
      rulebookColumn: false,
      useServerFilterQ: false,
    },
    allRules: {
      payloadScript: "nsm-all-rules-grid-data",
      configScript: "nsm-all-rules-grid-config",
      gridId: "nsm-all-rules-ag-grid",
      loadStatusId: "nsm-all-rules-load-status",
      loadTrackId: "nsm-all-rules-load-track",
      loadProgressId: "nsm-all-rules-load-progress",
      loadLabelId: "nsm-all-rules-load-label",
      rowStatsId: "nsm-all-rules-row-stats",
      selectedStatsId: null,
      loadMoreBtnId: "nsm-all-rules-load-more",
      rulebookColumn: true,
      useServerFilterQ: true,
    },
  };

  var NSM_GRID_REGISTRY = {};
  /** Set by bindNsmGroupToolbar — enables in-place grouping without page reload. */
  var NSM_GROUP_NAV_CTX = null;

  function isNetBoxDark() {
    return document.documentElement.getAttribute("data-bs-theme") === "dark";
  }

  function netBoxAgThemeMode() {
    return isNetBoxDark() ? "dark" : "light";
  }


  function readJsonScript(id, fallbackId) {
    var el = document.getElementById(id);
    if (!el && fallbackId) {
      el = document.getElementById(fallbackId);
    }
    if (!el) {
      return null;
    }
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.error("NSM rules grid: invalid JSON in #" + id, e);
      return null;
    }
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  var NSM_GROUP_DRAG_MIME = "application/x-nsm-group-by";
  var NSM_FILTER_DRAG_MIME = "application/x-nsm-filter-cell";
  var NSM_GROUP_MAX_LEVELS = 2;
  var NSM_GROUP_MAX_MESSAGE = "Maximal zwei Spalten zur Gruppierung erlaubt.";
  var NSM_GROUP_DUPLICATE_MESSAGE =
    "Diese Spalte ist bereits in der Gruppierung enthalten.";
  var NSM_GROUP_NOT_ALLOWED_FALLBACK =
    "Feld ist in diesem Rulebook nicht konfiguriert.";
  var NSM_GROUP_DRAG_SOURCE = null;
  var NSM_GROUP_DRAG_VALUE = null;
  var POLICY_GROUP_COL_ID = "_group";
  var RULES_TAB_CACHE_TTL_MS = 10 * 60 * 1000;

  function isRulesTabRefreshRequested() {
    if (typeof window === "undefined") {
      return false;
    }
    var params = new URLSearchParams(window.location.search);
    return params.get("refresh") === "1" || params.get("cache_bust") === "1";
  }

  function stripRulesTabRefreshFromUrl() {
    if (typeof window === "undefined" || !window.history || !window.history.replaceState) {
      return;
    }
    var url = new URL(window.location.href);
    if (!url.searchParams.has("refresh") && !url.searchParams.has("cache_bust")) {
      return;
    }
    url.searchParams.delete("refresh");
    url.searchParams.delete("cache_bust");
    var next = url.searchParams.toString();
    window.history.replaceState(
      window.history.state,
      "",
      next ? "?" + next : url.pathname
    );
  }
  var NSM_GROUP_HEADER_EXCLUDED = { _group: true, _actions: true };
  var NSM_FILTER_DRAG_EXCLUDED_COLS = { _group: true, _actions: true };

  function escapeColIdForDom(colId) {
    if (colId == null) {
      return "";
    }
    return String(colId).replace(/[&<>"']/g, function (ch) {
      return (
        {
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        }[ch] || ch
      );
    });
  }

  var NSM_GROUP_HEADER_POINTER_THRESHOLD = 6;
  var NSM_GROUP_HEADER_DRAG_ACTIVE = null;

  function rulesHeaderColIdSelector(colId) {
    var safe = escapeColIdForDom(colId);
    return (
      '.ag-header-cell[col-id="' + safe.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"]'
    );
  }

  function isRulesColumnLabelHeaderCell(cell) {
    if (!cell || !cell.classList || !cell.classList.contains("ag-header-cell")) {
      return false;
    }
    var row = cell.closest(".ag-header-row");
    if (!row) {
      return true;
    }
    return !row.classList.contains("ag-header-row-column-filter");
  }

  function isGroupHeaderDragExcludedTarget(target) {
    if (!target || typeof target.closest !== "function") {
      return false;
    }
    return !!target.closest(
      ".ag-header-cell-menu-button, .ag-header-cell-filter-button, .ag-floating-filter-button-button, .ag-header-cell-resize, .ag-floating-filter, .ag-checkbox-input-wrapper, input, textarea, select, button, a"
    );
  }

  function queryRulesHeaderCells(gridEl, colId) {
    if (!gridEl || !colId) {
      return [];
    }
    var cells = [];
    var seen = new WeakSet();
    gridEl.querySelectorAll(rulesHeaderColIdSelector(colId)).forEach(function (cell) {
      if (!seen.has(cell) && isRulesColumnLabelHeaderCell(cell)) {
        seen.add(cell);
        cells.push(cell);
      }
    });
    return cells;
  }

  function queryRulesHeaderCell(gridEl, colId) {
    var cells = queryRulesHeaderCells(gridEl, colId);
    return cells.length ? cells[0] : null;
  }

  function clearGroupableHeaderCell(cell) {
    cell.classList.remove("nsm-ag-groupable-header");
    cell.removeAttribute("draggable");
    delete cell.dataset.nsmGroupValue;
  }

  function setGroupHeaderDropzoneState(dropzone, target, hover, rejected) {
    if (!dropzone) {
      return;
    }
    dropzone.classList.toggle("nsm-ag-group-dropzone-target", !!target);
    dropzone.classList.toggle("nsm-ag-group-dropzone-hover", !!hover && !rejected);
    dropzone.classList.toggle("nsm-ag-group-dropzone-rejected", !!rejected);
  }

  function groupLevelsEqual(left, right) {
    if (!left || !right || left.length !== right.length) {
      return false;
    }
    for (var i = 0; i < left.length; i += 1) {
      if (String(left[i].value || "") !== String(right[i].value || "")) {
        return false;
      }
    }
    return true;
  }

  function showGroupToolbarMessage(message) {
    var text = message == null ? "" : String(message);
    if (!text) {
      return;
    }
    var existing = document.getElementById("nsm-ag-group-toast");
    if (existing && existing.parentNode) {
      existing.parentNode.removeChild(existing);
    }
    var toast = document.createElement("div");
    toast.id = "nsm-ag-group-toast";
    toast.className = "nsm-ag-group-toast";
    toast.setAttribute("role", "status");
    toast.textContent = text;
    var panel = document.querySelector(".nsm-ag-group-panel");
    (panel || document.body).appendChild(toast);
    window.setTimeout(function () {
      toast.classList.add("nsm-ag-group-toast-fade");
      window.setTimeout(function () {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 280);
    }, 3200);
  }

  function flashGroupDropzoneRejected(dropzone) {
    if (!dropzone) {
      return;
    }
    dropzone.classList.add("nsm-ag-group-dropzone-rejected-flash");
    window.setTimeout(function () {
      dropzone.classList.remove("nsm-ag-group-dropzone-rejected-flash");
    }, 700);
  }

  function notifyGroupMaxLevelsReached(dropzone) {
    showGroupToolbarMessage(NSM_GROUP_MAX_MESSAGE);
    flashGroupDropzoneRejected(dropzone);
  }

  function notifyGroupDuplicate(dropzone) {
    showGroupToolbarMessage(NSM_GROUP_DUPLICATE_MESSAGE);
    flashGroupDropzoneRejected(dropzone);
  }

  function groupLevelsContainValue(levels, value) {
    if (!value) {
      return false;
    }
    return (levels || []).some(function (item) {
      return item.value === value;
    });
  }

  function groupByNotAllowedMessage(config) {
    if (config && config.groupByNotAllowedMessage) {
      return String(config.groupByNotAllowedMessage);
    }
    return NSM_GROUP_NOT_ALLOWED_FALLBACK;
  }

  function notifyGroupFieldNotAllowed(dropzone, config) {
    showGroupToolbarMessage(groupByNotAllowedMessage(config));
    flashGroupDropzoneRejected(dropzone);
  }

  function notifyGroupDropRejected(dropzone, reason, config) {
    if (reason === "max") {
      notifyGroupMaxLevelsReached(dropzone);
      return;
    }
    if (reason === "duplicate") {
      notifyGroupDuplicate(dropzone);
      return;
    }
    if (reason === "field_config") {
      notifyGroupFieldNotAllowed(dropzone, config);
      return;
    }
    showGroupToolbarMessage(groupByNotAllowedMessage(config));
    flashGroupDropzoneRejected(dropzone);
  }

  function resolveGroupDropRejectReason(config, dragSource) {
    var levels = readGroupLevelsFromConfig(config);
    if (levels.length >= NSM_GROUP_MAX_LEVELS && dragSource !== "pill") {
      return "max";
    }
    var value = NSM_GROUP_DRAG_VALUE;
    if (
      value &&
      dragSource !== "pill" &&
      groupLevelsContainValue(levels, value)
    ) {
      return "duplicate";
    }
    if (
      value &&
      allowedGroupByValues(config).indexOf(value) < 0
    ) {
      return "field_config";
    }
    return null;
  }

  function isGroupDropRejected(config, dragSource) {
    return !!resolveGroupDropRejectReason(config, dragSource);
  }

  function pointerHitsGroupDropzone(clientX, clientY) {
    var dropzone = document.getElementById("nsm-ag-group-dropzone");
    if (!dropzone) {
      return false;
    }
    var rect = dropzone.getBoundingClientRect();
    return (
      clientX >= rect.left &&
      clientX <= rect.right &&
      clientY >= rect.top &&
      clientY <= rect.bottom
    );
  }

  function createGroupHeaderDragGhost(config, groupValue) {
    var ghost = document.createElement("div");
    ghost.className = "nsm-ag-group-drag-ghost nsm-ag-group-pointer-ghost";
    ghost.textContent = groupOptionLabel(config, groupValue);
    ghost.setAttribute("aria-hidden", "true");
    document.body.appendChild(ghost);
    return ghost;
  }

  function positionGroupHeaderDragGhost(ghost, clientX, clientY) {
    if (!ghost) {
      return;
    }
    ghost.style.left = clientX + 12 + "px";
    ghost.style.top = clientY + 10 + "px";
  }

  function applyGroupHeaderDrop(config, groupValue) {
    var dropzone = document.getElementById("nsm-ag-group-dropzone");
    var levels = readGroupLevelsFromConfig(config);
    groupValue = normalizeGroupValue(groupValue, config) || groupValue;
    if (
      !groupValue ||
      allowedGroupByValues(config).indexOf(groupValue) < 0
    ) {
      if (groupValue) {
        notifyGroupFieldNotAllowed(dropzone, config);
      }
      return;
    }
    if (groupLevelsContainValue(levels, groupValue)) {
      notifyGroupDuplicate(dropzone);
      return;
    }
    if (levels.length >= NSM_GROUP_MAX_LEVELS) {
      notifyGroupMaxLevelsReached(dropzone);
      return;
    }
    var next = insertGroupLevel(levels, groupValue, levels.length, config);
    if (next) {
      navigateGroupingLevels(next);
    }
  }

  function finishGroupHeaderPointerDrag(session, clientX, clientY) {
    if (!session) {
      return;
    }
    if (pointerHitsGroupDropzone(clientX, clientY)) {
      applyGroupHeaderDrop(session.config, session.groupValue);
    }
    if (session.ghost && session.ghost.parentNode) {
      session.ghost.parentNode.removeChild(session.ghost);
    }
    if (session.cell) {
      session.cell.classList.remove("nsm-ag-group-dragging");
    }
    setGroupHeaderDropzoneState(session.dropzone, false, false, false);
    document.body.classList.remove("nsm-ag-group-header-drag-active");
    NSM_GROUP_DRAG_SOURCE = null;
    NSM_GROUP_DRAG_VALUE = null;
    if (NSM_GROUP_HEADER_DRAG_ACTIVE === session) {
      NSM_GROUP_HEADER_DRAG_ACTIVE = null;
    }
  }

  function beginGroupHeaderPointerDrag(cell, groupValue, config, pointerId, clientX, clientY) {
    if (NSM_GROUP_HEADER_DRAG_ACTIVE) {
      finishGroupHeaderPointerDrag(NSM_GROUP_HEADER_DRAG_ACTIVE, clientX, clientY);
    }
    var dropzone = document.getElementById("nsm-ag-group-dropzone");
    var session = {
      pointerId: pointerId,
      groupValue: groupValue,
      config: config,
      cell: cell,
      dropzone: dropzone,
      ghost: createGroupHeaderDragGhost(config, groupValue),
    };
    NSM_GROUP_HEADER_DRAG_ACTIVE = session;
    positionGroupHeaderDragGhost(session.ghost, clientX, clientY);
    cell.classList.add("nsm-ag-group-dragging");
    NSM_GROUP_DRAG_SOURCE = "header";
    NSM_GROUP_DRAG_VALUE = groupValue;
    setGroupHeaderDropzoneState(
      dropzone,
      true,
      pointerHitsGroupDropzone(clientX, clientY),
      isGroupDropRejected(config, "header")
    );
    document.body.classList.add("nsm-ag-group-header-drag-active");

    function onMove(event) {
      if (event.pointerId !== pointerId) {
        return;
      }
      event.preventDefault();
      positionGroupHeaderDragGhost(session.ghost, event.clientX, event.clientY);
      setGroupHeaderDropzoneState(
        dropzone,
        true,
        pointerHitsGroupDropzone(event.clientX, event.clientY),
        isGroupDropRejected(config, "header")
      );
    }

    function onEnd(event) {
      if (event.pointerId !== pointerId) {
        return;
      }
      document.removeEventListener("pointermove", onMove, true);
      document.removeEventListener("pointerup", onEnd, true);
      document.removeEventListener("pointercancel", onEnd, true);
      finishGroupHeaderPointerDrag(session, event.clientX, event.clientY);
    }

    document.addEventListener("pointermove", onMove, true);
    document.addEventListener("pointerup", onEnd, true);
    document.addEventListener("pointercancel", onEnd, true);
  }

  function startGroupHeaderHtml5Drag(event, cell, groupValue, config) {
    if (!event.dataTransfer) {
      return false;
    }
    event.stopPropagation();
    event.dataTransfer.setData(NSM_GROUP_DRAG_MIME, groupValue);
    event.dataTransfer.setData("text/plain", groupValue);
    event.dataTransfer.effectAllowed = "copyMove";
    var ghost = createGroupHeaderDragGhost(config, groupValue);
    event.dataTransfer.setDragImage(ghost, 16, 14);
    window.setTimeout(function () {
      if (ghost.parentNode) {
        ghost.parentNode.removeChild(ghost);
      }
    }, 0);
    cell.classList.add("nsm-ag-group-dragging");
    NSM_GROUP_DRAG_SOURCE = "header";
    NSM_GROUP_DRAG_VALUE = groupValue;
    setGroupHeaderDropzoneState(
      document.getElementById("nsm-ag-group-dropzone"),
      true,
      false,
      isGroupDropRejected(config, "header")
    );
    return true;
  }

  function scheduleGroupHeaderBind(rebindFn) {
    if (typeof rebindFn !== "function") {
      return;
    }
    rebindFn();
    window.requestAnimationFrame(rebindFn);
    window.setTimeout(rebindFn, 0);
    window.setTimeout(rebindFn, 120);
    window.setTimeout(rebindFn, 450);
  }

  function groupOptionLabel(config, value) {
    if (!value || !config || !Array.isArray(config.groupByOptions)) {
      return value || "";
    }
    for (var i = 0; i < config.groupByOptions.length; i += 1) {
      var opt = config.groupByOptions[i];
      if (String(opt.value || "") === String(value)) {
        return opt.label == null ? String(value) : String(opt.label);
      }
    }
    return String(value);
  }

  function buildGroupValueAliases(config) {
    var aliases = {};
    (config.groupByOptions || []).forEach(function (opt) {
      var value = opt.value == null ? "" : String(opt.value);
      if (!value) {
        return;
      }
      aliases[value] = value;
      if (value.indexOf("col:") !== 0) {
        return;
      }
      var colId = value.slice(4);
      aliases["col:" + colId] = value;
      var label = opt.label == null ? "" : String(opt.label);
      var parts = label.split("/");
      if (parts.length >= 2) {
        var area = parts[0].trim();
        var colLabel = parts.slice(1).join("/").trim();
        if (area && colLabel) {
          aliases["col:" + area + "::" + colLabel] = value;
        }
      }
    });
    return aliases;
  }

  function normalizeGroupValue(value, config) {
    if (!value) {
      return "";
    }
    var text = String(value);
    var allowed = allowedGroupByValues(config);
    if (allowed.indexOf(text) >= 0) {
      return text;
    }
    var aliases = buildGroupValueAliases(config);
    return aliases[text] || "";
  }

  function normalizeGroupLevelsInConfig(config) {
    if (!config) {
      return;
    }
    if (config.groupBy) {
      var primary = normalizeGroupValue(String(config.groupBy), config);
      if (primary) {
        config.groupBy = primary;
        config.groupByLabel = groupOptionLabel(config, primary);
      }
    }
    if (config.groupBy2) {
      var secondary = normalizeGroupValue(String(config.groupBy2), config);
      if (secondary) {
        config.groupBy2 = secondary;
        config.groupBy2Label = groupOptionLabel(config, secondary);
      }
    }
  }

  function buildColIdToGroupValueMap(config) {
    var map = {};
    (config.groupByOptions || []).forEach(function (opt) {
      var value = opt.value == null ? "" : String(opt.value);
      if (value.indexOf("col:") === 0) {
        map[value.slice(4)] = value;
      }
    });
    return map;
  }

  function allowedGroupByValues(config) {
    var values = [];
    (config.groupByOptions || []).forEach(function (opt) {
      var value = opt.value == null ? "" : String(opt.value);
      if (value) {
        values.push(value);
      }
    });
    return values;
  }

  function resolveGroupValueForColId(colId, config) {
    if (!colId) {
      return "";
    }
    var allowed = allowedGroupByValues(config);
    // Rulebook column uses group_by=rulebook, not col:rulebook.
    if (colId === "rulebook" && allowed.indexOf("rulebook") >= 0) {
      return "rulebook";
    }
    var colMap = buildColIdToGroupValueMap(config);
    if (colMap[colId]) {
      return colMap[colId];
    }
    var colValue = "col:" + colId;
    if (allowed.indexOf(colValue) >= 0) {
      return colValue;
    }
    var aliased = normalizeGroupValue(colValue, config);
    if (aliased) {
      return aliased;
    }
    if (allowed.indexOf(colId) >= 0) {
      return colId;
    }
    return "";
  }

  function readGroupLevelsFromConfig(config) {
    normalizeGroupLevelsInConfig(config);
    var levels = [];
    if (config && config.groupBy) {
      levels.push({ value: String(config.groupBy) });
    }
    if (config && config.groupBy2) {
      levels.push({ value: String(config.groupBy2) });
    }
    return levels;
  }

  function buildGroupValueToColIdsMap(config) {
    var map = {};
    var currentTag = null;
    (config && config.groupByOptions ? config.groupByOptions : []).forEach(function (opt) {
      var value = opt.value == null ? "" : String(opt.value);
      if (!value) {
        return;
      }
      if (value.indexOf("tag:") === 0) {
        currentTag = value;
        map[currentTag] = [];
        return;
      }
      if (value.indexOf("col:") === 0) {
        var colId = value.slice(4);
        map[value] = [colId];
        if (currentTag && map[currentTag]) {
          map[currentTag].push(colId);
        }
        return;
      }
      if (value === "rulebook") {
        map.rulebook = ["rulebook"];
        currentTag = null;
      }
    });
    return map;
  }

  function resolveColIdsForGroupValue(groupValue, config) {
    if (!groupValue) {
      return [];
    }
    var value = String(groupValue);
    if (value === "rulebook") {
      return ["rulebook"];
    }
    if (value.indexOf("col:") === 0) {
      return [value.slice(4)];
    }
    if (value.indexOf("tag:") === 0) {
      var map = buildGroupValueToColIdsMap(config);
      return (map[value] || []).slice();
    }
    return [];
  }

  function readGroupedColIdsFromConfig(config) {
    var colIds = [];
    var seen = {};
    readGroupLevelsFromConfig(config).forEach(function (level) {
      resolveColIdsForGroupValue(level.value, config).forEach(function (colId) {
        if (!colId || NSM_GROUP_HEADER_EXCLUDED[colId] || seen[colId]) {
          return;
        }
        seen[colId] = true;
        colIds.push(colId);
      });
    });
    return colIds;
  }

  function buildGridColumnIdLookup(gridApi, columnDefs) {
    var lookup = {};
    flattenColumnsForPicker(columnDefs || []).forEach(function (entry) {
      lookup[entry.colId] = true;
    });
    if (gridApi && typeof gridApi.getColumns === "function") {
      gridApi.getColumns().forEach(function (col) {
        if (col && typeof col.getColId === "function") {
          lookup[col.getColId()] = true;
        }
      });
    }
    return lookup;
  }

  function resolveGroupedColIdsOnGrid(gridApi, columnDefs, config) {
    var lookup = buildGridColumnIdLookup(gridApi, columnDefs);
    var resolved = [];
    var unresolved = [];
    readGroupLevelsFromConfig(config).forEach(function (level) {
      resolveColIdsForGroupValue(level.value, config).forEach(function (colId) {
        if (!colId || NSM_GROUP_HEADER_EXCLUDED[colId]) {
          return;
        }
        if (resolved.indexOf(colId) >= 0) {
          return;
        }
        var column =
          gridApi && typeof gridApi.getColumn === "function"
            ? gridApi.getColumn(colId)
            : null;
        if (lookup[colId] || column) {
          resolved.push(colId);
          return;
        }
        unresolved.push({ groupValue: level.value, colId: colId });
      });
    });
    if (unresolved.length) {
      console.warn(
        "NSM rules grid: grouped column mapping failed",
        unresolved,
        "knownColIds:",
        Object.keys(lookup)
      );
    }
    return resolved;
  }

  function setGridColumnsVisible(gridApi, colIds, visible) {
    if (!gridApi || typeof gridApi.setColumnsVisible !== "function" || !colIds.length) {
      return;
    }
    var keys = [];
    colIds.forEach(function (colId) {
      var column =
        typeof gridApi.getColumn === "function" ? gridApi.getColumn(colId) : null;
      keys.push(column || colId);
    });
    gridApi.setColumnsVisible(keys, visible);
  }

  function syncGroupedColumnVisibility(gridApi, columnDefs, config, profileKey) {
    if (!gridApi) {
      return [];
    }
    columnDefs = columnDefs || gridApi._nsmColumnDefs || [];
    var groupedColIds = resolveGroupedColIdsOnGrid(gridApi, columnDefs, config);
    gridApi._nsmGroupedColIds = groupedColIds.slice();
    gridApi._nsmPrevGroupedColIds = groupedColIds.slice();
    return groupedColIds;
  }

  function scheduleGroupedColumnVisibility(gridApi, columnDefs, config, profileKey) {
    if (!gridApi) {
      return;
    }
    var defs = columnDefs || gridApi._nsmColumnDefs;
    var run = function () {
      syncGroupedColumnVisibility(gridApi, defs, config, profileKey);
    };
    run();
    window.setTimeout(run, 0);
    window.setTimeout(run, 120);
    window.setTimeout(run, 450);
  }

  /**
   * Staged client download (10, 20, 40, …) loads all rules, then filter/sort run
   * locally until RULES_TAB_CACHE_TTL_MS expires or ?refresh=1 / ?cache_bust=1.
   * Server-side grouping still refetches on group_by / expansion changes
   * (use_cached=1 on Django cache); ungrouped grouping-only toggles reuse the
   * in-memory flat row cache when available.
   */
  function buildGroupingUrlParams(levels) {
    levels = (levels || []).slice(0, NSM_GROUP_MAX_LEVELS);
    var params = new URLSearchParams(window.location.search);
    params.delete("group_by");
    params.delete("group_by_2");
    params.delete("group_by_3");
    params.delete("group_mode");
    params.delete("group_mode_2");
    params.delete("group_mode_3");
    params.delete("group_obj");
    params.delete("expanded");
    if (!levels.length) {
      params.delete("collapsed");
      params.delete("group_expanded");
      return params;
    }
    params.set("group_by", levels[0].value);
    if (levels.length > 1) {
      params.set("group_by_2", levels[1].value);
    } else {
      params.delete("group_by_2");
    }
    params.set("collapsed", "all");
    return params;
  }

  function syncGroupingUrl(params, usePushState) {
    if (!params || typeof window === "undefined") {
      return;
    }
    var next = params.toString();
    var current = window.location.search.replace(/^\?/, "");
    if (next === current) {
      return;
    }
    var url = next ? "?" + next : window.location.pathname;
    if (usePushState && window.history && window.history.pushState) {
      window.history.pushState(null, "", url);
    } else if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", url);
    }
  }

  function updateConfigFromGroupLevels(config, levels) {
    if (!config) {
      return;
    }
    delete config.groupBy;
    delete config.groupBy2;
    delete config.groupByEnabled;
    delete config.groupByLabel;
    delete config.groupBy2Label;
    delete config.groupExpansionMode;
    delete config.groupExpandedKeys;
    delete config.groupCollapsedKeys;
    levels = (levels || []).slice(0, NSM_GROUP_MAX_LEVELS);
    if (!levels.length) {
      return;
    }
    config.groupBy = levels[0].value;
    config.groupByEnabled = true;
    config.groupByLabel = groupOptionLabel(config, levels[0].value);
    if (levels.length > 1) {
      config.groupBy2 = levels[1].value;
      config.groupBy2Label = groupOptionLabel(config, levels[1].value);
    }
  }

  function resetGroupExpansionForNewGrouping(state) {
    if (!state) {
      return;
    }
    state.collapseAllGroups = true;
    state.expandAllGroups = false;
    state.usesExpandedMode = false;
    state.expandedGroups = state.expandedGroups || {};
    state.collapsedGroups = state.collapsedGroups || {};
    Object.keys(state.expandedGroups).forEach(function (key) {
      delete state.expandedGroups[key];
    });
    Object.keys(state.collapsedGroups).forEach(function (key) {
      delete state.collapsedGroups[key];
    });
  }

  function ensureBaseColumnDefs(gridApi, columnDefs) {
    if (!gridApi) {
      return columnDefs || [];
    }
    if (gridApi._nsmBaseColumnDefs) {
      return gridApi._nsmBaseColumnDefs;
    }
    var base = (columnDefs || gridApi._nsmColumnDefs || []).slice();
    if (base.length && base[0].colId === POLICY_GROUP_COL_ID) {
      base = base.slice(1);
    }
    gridApi._nsmBaseColumnDefs = base;
    return base;
  }

  function gridHasRulesGroupColumn(gridApi) {
    if (!gridApi || typeof gridApi.getColumn !== "function") {
      return false;
    }
    return !!gridApi.getColumn(POLICY_GROUP_COL_ID);
  }

  function syncRulesGroupColumnDefs(gridApi, config, state, profileKey) {
    if (!gridApi || !state) {
      return;
    }
    var base = ensureBaseColumnDefs(gridApi, gridApi._nsmColumnDefs);
    var nextDefs = state.groupByEnabled
      ? prependRulesGroupColumn(base, config)
      : base.slice();
    var hadGroupCol = gridHasRulesGroupColumn(gridApi);
    var needsGroupCol = !!state.groupByEnabled;
    gridApi._nsmColumnDefs = nextDefs;

    if (hadGroupCol !== needsGroupCol) {
      var extra = gridApi._nsmDefaultColDefExtra || null;
      if (typeof gridApi.setGridOption === "function") {
        gridApi.setGridOption("columnDefs", nextDefs);
        gridApi.setGridOption(
          "defaultColDef",
          buildRulesDefaultColDef(profileKey, state.groupByEnabled, extra)
        );
      }
      initColumnVisibilityPersistence(
        gridApi,
        nextDefs,
        profileKey,
        state.groupByEnabled,
        config
      );
    } else if (needsGroupCol) {
      scheduleGroupedColumnVisibility(gridApi, nextDefs, config, profileKey);
    } else if (typeof gridApi.setColumnsVisible === "function") {
      var prevGrouped = gridApi._nsmPrevGroupedColIds || [];
      if (prevGrouped.length) {
        var stored = loadHiddenColumnIds(profileKey) || [];
        var toShow = prevGrouped.filter(function (colId) {
          return (
            isColumnPickerHideable(colId, profileKey, false) &&
            stored.indexOf(colId) < 0
          );
        });
        if (toShow.length) {
          setGridColumnsVisible(gridApi, toShow, true);
        }
      }
      gridApi._nsmGroupedColIds = [];
      gridApi._nsmPrevGroupedColIds = [];
    }

    if (state.gridEl) {
      scheduleRulesGridWidthFit(gridApi, state.gridEl);
    }
  }

  function applyRulesGroupingLevels(levels, ctx) {
    if (!ctx || !ctx.gridApi || !ctx.config || !ctx.state) {
      return false;
    }
    levels = (levels || []).slice(0, NSM_GROUP_MAX_LEVELS);
    var gridApi = ctx.gridApi;
    var config = ctx.config;
    var state = ctx.state;
    var profileKey = ctx.profileKey || "rules";
    var normalizedLevels = [];
    levels.forEach(function (spec) {
      var value = spec && spec.value != null ? String(spec.value) : "";
      var canonical = normalizeGroupValue(value, config) || value;
      if (canonical && allowedGroupByValues(config).indexOf(canonical) >= 0) {
        normalizedLevels.push({ value: canonical });
      }
    });
    levels = normalizedLevels;
    updateConfigFromGroupLevels(config, levels);
    state.groupByEnabled = !!(config.groupBy && config.groupByEnabled);
    resetGroupExpansionForNewGrouping(state);

    syncRulesGroupColumnDefs(gridApi, config, state, profileKey);
    renderGroupPills(config);
    syncGroupToolbarVisibility(config);
    if (gridApi._nsmRebindGroupHeaders) {
      scheduleGroupHeaderBind(gridApi._nsmRebindGroupHeaders);
    }

    syncGroupingUrl(buildGroupingUrlParams(levels), true);
    reloadRulesGridData(
      gridApi,
      config,
      state,
      function () {
        resetRulesRowHeights(gridApi, state.groupByEnabled);
        if (gridApi._nsmRebindGroupHeaders) {
          scheduleGroupHeaderBind(gridApi._nsmRebindGroupHeaders);
        }
        scheduleGroupedColumnVisibility(
          gridApi,
          gridApi._nsmColumnDefs,
          config,
          profileKey
        );
      },
      { groupingOnly: true }
    );
    return true;
  }

  function navigateGroupingLevels(levels) {
    if (applyRulesGroupingLevels(levels, NSM_GROUP_NAV_CTX)) {
      return;
    }
    var params = buildGroupingUrlParams(levels);
    window.location.search = params.toString();
  }

  function readDraggedGroupValue(event) {
    if (!event || !event.dataTransfer) {
      return "";
    }
    var value =
      event.dataTransfer.getData(NSM_GROUP_DRAG_MIME) ||
      event.dataTransfer.getData("text/plain") ||
      "";
    return String(value || "").trim();
  }

  function renderGroupSourceChips() {
    /* Kitchen-sink style: drag from column headers only — no separate chip row. */
  }

  function buildGroupPillElement(level, spec, config) {
    var pill = document.createElement("div");
    pill.className = "nsm-ag-group-pill";
    pill.draggable = true;
    pill.setAttribute("data-group-value", spec.value);
    pill.setAttribute("data-group-level", String(level));

    var grip = document.createElement("span");
    grip.className = "nsm-ag-group-pill-grip mdi mdi-drag";
    grip.setAttribute("aria-hidden", "true");
    pill.appendChild(grip);

    var label = document.createElement("span");
    label.className = "nsm-ag-group-pill-label";
    label.textContent = groupOptionLabel(config, spec.value);
    pill.appendChild(label);

    var removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "nsm-ag-group-pill-remove";
    removeBtn.setAttribute("aria-label", "Gruppierung entfernen");
    removeBtn.innerHTML = '<span class="mdi mdi-close" aria-hidden="true"></span>';
    removeBtn.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      var levels = readGroupLevelsFromConfig(config);
      levels.splice(level - 1, 1);
      navigateGroupingLevels(levels);
    });
    pill.appendChild(removeBtn);

    pill.addEventListener("dragstart", function (event) {
      event.dataTransfer.setData(NSM_GROUP_DRAG_MIME, spec.value);
      event.dataTransfer.setData("text/plain", spec.value);
      event.dataTransfer.setData("application/x-nsm-group-pill-level", String(level));
      event.dataTransfer.effectAllowed = "move";
      NSM_GROUP_DRAG_SOURCE = "pill";
      NSM_GROUP_DRAG_VALUE = spec.value;
      pill.classList.add("nsm-ag-group-dragging");
    });
    pill.addEventListener("dragend", function () {
      pill.classList.remove("nsm-ag-group-dragging");
      NSM_GROUP_DRAG_SOURCE = null;
      NSM_GROUP_DRAG_VALUE = null;
      setGroupHeaderDropzoneState(
        document.getElementById("nsm-ag-group-dropzone"),
        false,
        false,
        false
      );
    });

    return pill;
  }

  function renderGroupPills(config) {
    var pillsEl = document.getElementById("nsm-ag-group-pills");
    var hintEl = document.getElementById("nsm-ag-group-dropzone-hint");
    var dropzone = document.getElementById("nsm-ag-group-dropzone");
    if (!pillsEl) {
      return;
    }
    var levels = readGroupLevelsFromConfig(config).slice(0, NSM_GROUP_MAX_LEVELS);
    pillsEl.innerHTML = "";
    levels.forEach(function (spec, index) {
      if (index > 0) {
        var sep = document.createElement("span");
        sep.className = "nsm-ag-group-pill-separator";
        sep.setAttribute("aria-hidden", "true");
        sep.textContent = "\u203A";
        pillsEl.appendChild(sep);
      }
      pillsEl.appendChild(buildGroupPillElement(index + 1, spec, config));
    });
    if (hintEl) {
      hintEl.classList.toggle("d-none", levels.length > 0);
    }
    if (dropzone) {
      dropzone.classList.toggle("nsm-ag-group-dropzone-active", levels.length > 0);
    }
  }

  function insertGroupLevel(levels, value, insertIndex, config) {
    if (!value || groupLevelsContainValue(levels, value)) {
      return null;
    }
    if (allowedGroupByValues(config).indexOf(value) < 0) {
      return null;
    }
    if (levels.length >= NSM_GROUP_MAX_LEVELS) {
      return null;
    }
    if (typeof insertIndex !== "number") {
      insertIndex = levels.length;
    }
    var next = levels.slice();
    next.splice(
      Math.max(0, Math.min(insertIndex, next.length)),
      0,
      { value: value }
    );
    if (next.length > NSM_GROUP_MAX_LEVELS) {
      next = next.slice(0, NSM_GROUP_MAX_LEVELS);
    }
    return next;
  }

  function reorderGroupLevels(levels, fromLevel, toIndex) {
    if (!fromLevel || fromLevel < 1 || fromLevel > levels.length) {
      return levels;
    }
    var next = levels.slice();
    var moved = next.splice(fromLevel - 1, 1)[0];
    if (!moved) {
      return levels;
    }
    var target = Math.max(0, Math.min(toIndex, next.length));
    next.splice(target, 0, moved);
    return next;
  }

  function bindGroupDropZone(config) {
    var dropzone = document.getElementById("nsm-ag-group-dropzone");
    if (!dropzone || dropzone.dataset.nsmGroupDropBound === "1") {
      return;
    }
    dropzone.dataset.nsmGroupDropBound = "1";

    function levelsFromDrag(event, allowReorder) {
      var value = readDraggedGroupValue(event);
      value = normalizeGroupValue(value, config) || value;
      var levels = readGroupLevelsFromConfig(config);
      if (!value || allowedGroupByValues(config).indexOf(value) < 0) {
        return null;
      }
      var pillLevelRaw = event.dataTransfer.getData("application/x-nsm-group-pill-level");
      var pillLevel = pillLevelRaw ? parseInt(pillLevelRaw, 10) : 0;
      if (allowReorder && pillLevel > 0) {
        var targetPill = event.target.closest(".nsm-ag-group-pill");
        var targetLevel = targetPill
          ? parseInt(targetPill.getAttribute("data-group-level") || "0", 10)
          : levels.length + 1;
        var insertAt = targetLevel > pillLevel ? targetLevel - 2 : targetLevel - 1;
        var reordered = reorderGroupLevels(levels, pillLevel, Math.max(0, insertAt));
        return groupLevelsEqual(levels, reordered) ? null : reordered;
      }
      if (groupLevelsContainValue(levels, value)) {
        return null;
      }
      if (levels.length >= NSM_GROUP_MAX_LEVELS) {
        return null;
      }
      return insertGroupLevel(levels, value, levels.length, config);
    }

    dropzone.addEventListener("dragover", function (event) {
      event.preventDefault();
      var rejected = isGroupDropRejected(config, NSM_GROUP_DRAG_SOURCE);
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = rejected ? "none" : "move";
      }
      dropzone.classList.toggle("nsm-ag-group-dropzone-hover", !rejected);
      dropzone.classList.toggle("nsm-ag-group-dropzone-rejected", rejected);
    });
    dropzone.addEventListener("dragleave", function (event) {
      if (event.target === dropzone || !dropzone.contains(event.relatedTarget)) {
        dropzone.classList.remove("nsm-ag-group-dropzone-hover");
        dropzone.classList.remove("nsm-ag-group-dropzone-rejected");
      }
    });
    dropzone.addEventListener("drop", function (event) {
      event.preventDefault();
      dropzone.classList.remove("nsm-ag-group-dropzone-hover");
      dropzone.classList.remove("nsm-ag-group-dropzone-rejected");
      var pillLevelRaw = event.dataTransfer.getData("application/x-nsm-group-pill-level");
      var pillLevel = pillLevelRaw ? parseInt(pillLevelRaw, 10) : 0;
      var levels = readGroupLevelsFromConfig(config);
      var rejectReason = resolveGroupDropRejectReason(config, NSM_GROUP_DRAG_SOURCE);
      if (rejectReason) {
        notifyGroupDropRejected(dropzone, rejectReason, config);
        NSM_GROUP_DRAG_SOURCE = null;
        NSM_GROUP_DRAG_VALUE = null;
        return;
      }
      if (pillLevel <= 0 && levels.length >= NSM_GROUP_MAX_LEVELS) {
        notifyGroupMaxLevelsReached(dropzone);
        NSM_GROUP_DRAG_SOURCE = null;
        NSM_GROUP_DRAG_VALUE = null;
        return;
      }
      var next = levelsFromDrag(event, true);
      if (next) {
        navigateGroupingLevels(next);
      } else if (
        pillLevel <= 0 &&
        groupLevelsContainValue(levels, readDraggedGroupValue(event))
      ) {
        notifyGroupDuplicate(dropzone);
      }
      NSM_GROUP_DRAG_SOURCE = null;
      NSM_GROUP_DRAG_VALUE = null;
    });
  }

  function syncGroupToolbarVisibility(config) {
    var expandWrap = document.getElementById("nsm-ag-group-expand-wrap");
    var grouped = !!(config && config.groupBy);
    if (expandWrap) {
      expandWrap.classList.toggle("d-none", !grouped);
    }
  }

  function attachGroupableHeaderDrag(gridApi, gridEl, config, profileKey) {
    if (!gridApi || !gridEl || !config) {
      return function () {};
    }
    var allowed = allowedGroupByValues(config);
    var boundHeaderCells = new WeakSet();
    var includeRulebookColumn =
      profileKey === "allRules" && allowed.indexOf("rulebook") >= 0;

    function bindHeaderCell(cell, groupValue) {
      if (!isRulesColumnLabelHeaderCell(cell)) {
        return;
      }
      cell.setAttribute("draggable", "true");
      cell.classList.add("nsm-ag-groupable-header");
      cell.dataset.nsmGroupValue = groupValue;
      if (boundHeaderCells.has(cell)) {
        return;
      }
      boundHeaderCells.add(cell);

      cell.addEventListener(
        "dragstart",
        function (event) {
          if (isGroupHeaderDragExcludedTarget(event.target)) {
            event.preventDefault();
            return;
          }
          startGroupHeaderHtml5Drag(event, cell, groupValue, config);
        },
        true
      );
      cell.addEventListener("dragend", function () {
        cell.classList.remove("nsm-ag-group-dragging");
        NSM_GROUP_DRAG_SOURCE = null;
        NSM_GROUP_DRAG_VALUE = null;
        setGroupHeaderDropzoneState(
          document.getElementById("nsm-ag-group-dropzone"),
          false,
          false,
          false
        );
      });

      cell.addEventListener(
        "pointerdown",
        function (event) {
          if (
            event.button !== 0 ||
            !event.isPrimary ||
            isGroupHeaderDragExcludedTarget(event.target)
          ) {
            return;
          }
          var pointerId = event.pointerId;
          var startX = event.clientX;
          var startY = event.clientY;
          var pointerDragStarted = false;

          function clearPendingPointer() {
            document.removeEventListener("pointermove", onPendingMove, true);
            document.removeEventListener("pointerup", onPendingUp, true);
            document.removeEventListener("pointercancel", onPendingUp, true);
          }

          function onPendingMove(moveEvent) {
            if (moveEvent.pointerId !== pointerId || pointerDragStarted) {
              return;
            }
            var delta =
              Math.abs(moveEvent.clientX - startX) + Math.abs(moveEvent.clientY - startY);
            if (delta < NSM_GROUP_HEADER_POINTER_THRESHOLD) {
              return;
            }
            pointerDragStarted = true;
            clearPendingPointer();
            moveEvent.preventDefault();
            moveEvent.stopPropagation();
            if (typeof cell.setPointerCapture === "function") {
              try {
                cell.setPointerCapture(pointerId);
              } catch (captureErr) {
                /* ignore */
              }
            }
            beginGroupHeaderPointerDrag(
              cell,
              groupValue,
              config,
              pointerId,
              moveEvent.clientX,
              moveEvent.clientY
            );
          }

          function onPendingUp(upEvent) {
            if (upEvent.pointerId !== pointerId || pointerDragStarted) {
              return;
            }
            clearPendingPointer();
          }

          document.addEventListener("pointermove", onPendingMove, true);
          document.addEventListener("pointerup", onPendingUp, true);
          document.addEventListener("pointercancel", onPendingUp, true);
        },
        true
      );
    }

    function bindHeaders() {
      gridEl
        .querySelectorAll(".ag-header-cell.nsm-ag-groupable-header")
        .forEach(clearGroupableHeaderCell);

      var boundCells = new WeakSet();

      function bindColId(colId) {
        if (!colId || NSM_GROUP_HEADER_EXCLUDED[colId]) {
          return;
        }
        var groupValue = resolveGroupValueForColId(colId, config);
        if (!groupValue || allowed.indexOf(groupValue) < 0) {
          return;
        }
        queryRulesHeaderCells(gridEl, colId).forEach(function (cell) {
          if (boundCells.has(cell)) {
            return;
          }
          boundCells.add(cell);
          bindHeaderCell(cell, groupValue);
        });
      }

      var columns = [];
      if (typeof gridApi.getAllDisplayedColumns === "function") {
        columns = gridApi.getAllDisplayedColumns() || [];
      } else if (typeof gridApi.getColumns === "function") {
        columns = gridApi.getColumns() || [];
      }
      columns.forEach(function (col) {
        var colId = typeof col.getColId === "function" ? col.getColId() : col.colId;
        bindColId(colId);
      });

      gridEl.querySelectorAll(".ag-header-cell[col-id]").forEach(function (cell) {
        if (!isRulesColumnLabelHeaderCell(cell)) {
          return;
        }
        var colId = cell.getAttribute("col-id");
        if (!colId || NSM_GROUP_HEADER_EXCLUDED[colId]) {
          clearGroupableHeaderCell(cell);
          return;
        }
        var groupValue = resolveGroupValueForColId(colId, config);
        if (!groupValue || allowed.indexOf(groupValue) < 0) {
          clearGroupableHeaderCell(cell);
          return;
        }
        if (!boundCells.has(cell)) {
          boundCells.add(cell);
          bindHeaderCell(cell, groupValue);
        }
      });

      if (includeRulebookColumn) {
        bindColId("rulebook");
        var pinnedLeft = gridEl.querySelector(".ag-pinned-left-header");
        if (pinnedLeft) {
          pinnedLeft
            .querySelectorAll('.ag-header-cell[col-id="rulebook"]')
            .forEach(function (cell) {
              if (!isRulesColumnLabelHeaderCell(cell)) {
                return;
              }
              if (!boundCells.has(cell)) {
                boundCells.add(cell);
              }
              bindHeaderCell(cell, "rulebook");
            });
        }
      }
    }

    return bindHeaders;
  }

  function applyRulesGroupConfig(config, state) {
    if (!state) {
      return;
    }
    state.groupByEnabled = !!(config && config.groupByEnabled && config.groupBy);
    state.collapseAllGroups = false;
    state.usesExpandedMode = false;
    state.expandedGroups = state.expandedGroups || {};
    state.collapsedGroups = state.collapsedGroups || {};
    Object.keys(state.expandedGroups).forEach(function (key) {
      delete state.expandedGroups[key];
    });
    Object.keys(state.collapsedGroups).forEach(function (key) {
      delete state.collapsedGroups[key];
    });
    if (!state.groupByEnabled) {
      return;
    }
    var mode = config.groupExpansionMode || "all_collapsed";
    if (mode === "expanded") {
      state.usesExpandedMode = true;
      (config.groupExpandedKeys || []).forEach(function (key) {
        state.expandedGroups[key] = true;
      });
      return;
    }
    if (mode === "all_expanded") {
      state.usesExpandedMode = true;
      state.expandAllGroups = true;
      return;
    }
    if (mode === "collapsed") {
      (config.groupCollapsedKeys || []).forEach(function (key) {
        state.collapsedGroups[key] = true;
      });
      return;
    }
    state.collapseAllGroups = true;
  }

  function getActiveRulesFilterModel(api, config, state) {
    if (!state || !state.groupByEnabled || !api || typeof api.getFilterModel !== "function") {
      return null;
    }
    var model = api.getFilterModel();
    if (model && Object.keys(model).length) {
      return model;
    }
    return null;
  }

  var groupedFilterReloadTimer = null;
  function scheduleGroupedFilterReload(api, config, state) {
    if (!state || !state.groupByEnabled || !api) {
      return;
    }
    if (groupedFilterReloadTimer) {
      window.clearTimeout(groupedFilterReloadTimer);
    }
    groupedFilterReloadTimer = window.setTimeout(function () {
      groupedFilterReloadTimer = null;
      reloadRulesGridData(api, config, state);
    }, 300);
  }

  function bindGroupExpandCollapseButtons(config, state, gridApi) {
    var expandBtn = document.getElementById("nsm-ag-group-expand-all");
    var collapseBtn = document.getElementById("nsm-ag-group-collapse-all");
    if (!expandBtn || !collapseBtn) {
      return;
    }
    expandBtn.addEventListener("click", function () {
      if (!state || !state.groupByEnabled) {
        return;
      }
      state.collapseAllGroups = false;
      state.usesExpandedMode = true;
      state.expandAllGroups = true;
      Object.keys(state.expandedGroups).forEach(function (key) {
        delete state.expandedGroups[key];
      });
      Object.keys(state.collapsedGroups).forEach(function (key) {
        delete state.collapsedGroups[key];
      });
      syncGroupExpansionUrl(state);
      reloadRulesGridData(gridApi, config, state, null, { groupingOnly: true });
    });
    collapseBtn.addEventListener("click", function () {
      if (!state || !state.groupByEnabled) {
        return;
      }
      state.collapseAllGroups = true;
      state.usesExpandedMode = false;
      state.expandAllGroups = false;
      Object.keys(state.expandedGroups).forEach(function (key) {
        delete state.expandedGroups[key];
      });
      Object.keys(state.collapsedGroups).forEach(function (key) {
        delete state.collapsedGroups[key];
      });
      syncGroupExpansionUrl(state);
      reloadRulesGridData(gridApi, config, state, null, { groupingOnly: true });
    });
  }

  function initGroupHelpTooltip() {
    var helpBtn = document.getElementById("nsm-ag-group-help");
    if (!helpBtn || typeof bootstrap === "undefined" || !bootstrap.Tooltip) {
      return;
    }
    bootstrap.Tooltip.getOrCreateInstance(helpBtn);
  }

  function resolveRulesLoadEndRow(config, state) {
    var hardLimit = config.loadRowLimit || POLICY_GRID_FETCH_MAX;
    var total =
      (state && state.knownTotalRows) ||
      (config && config.totalCount) ||
      0;
    if (total > 0) {
      return Math.min(total, hardLimit);
    }
    return hardLimit;
  }

  function rulesFetchPageExhausted(data, startRow, endRow, loadedCount) {
    var rows = (data && data.rowData) || [];
    var pageSize = Math.max(0, endRow - startRow);
    if (pageSize <= 0) {
      return true;
    }
    if (typeof data.lastRow === "number" && loadedCount >= data.lastRow) {
      return true;
    }
    return rows.length < pageSize;
  }

  function resolveRulesInitialLoadTarget(config, state) {
    return resolveRulesLoadEndRow(config, state);
  }

  function resolveRulesMaxLoadableRows(state, config) {
    var hardLimit = config.loadRowLimit || POLICY_GRID_FETCH_MAX;
    var total =
      (state && state.knownTotalRows) ||
      (config && config.totalCount) ||
      0;
    if (total > 0) {
      return Math.min(total, hardLimit);
    }
    return hardLimit;
  }

  function canLoadMoreRulesRows(state, config) {
    if (!state || state.progressiveLoadActive || state.initialLoadActive) {
      return false;
    }
    var loaded =
      typeof state.loadedRowCount === "number"
        ? state.loadedRowCount
        : (state._accumulatedRows || []).length;
    if (loaded <= 0) {
      return false;
    }
    var maxLoadable = resolveRulesMaxLoadableRows(state, config);
    if (loaded >= maxLoadable) {
      return false;
    }
    var cache = getRulesTabDataCache(state, config);
    if (cache && cache.flatRows && cache.flatRows.length >= maxLoadable) {
      return false;
    }
    return loaded < maxLoadable;
  }

  function updateRulesLoadMoreButton(state, config, profile) {
    profile = profile || (state && state.domProfile) || NSM_GRID_PROFILES.rules;
    if (!profile.loadMoreBtnId) {
      return;
    }
    var btn = document.getElementById(profile.loadMoreBtnId);
    if (!btn) {
      return;
    }
    var show = canLoadMoreRulesRows(state, config);
    btn.classList.toggle("d-none", !show);
    if (!show) {
      return;
    }
    var loaded =
      typeof state.loadedRowCount === "number"
        ? state.loadedRowCount
        : (state._accumulatedRows || []).length;
    var maxLoadable = resolveRulesMaxLoadableRows(state, config);
    var step = config.loadMoreStep || DEFAULT_POLICY_LOAD_MORE_STEP;
    var next = Math.min(maxLoadable, loaded + step);
    btn.textContent = "Load more (" + formatRulesLoadCount(next) + " / " + formatRulesLoadCount(maxLoadable) + ")";
  }

  function rulesDescriptionLineCount(desc) {
    var raw = desc == null ? "" : String(desc);
    if (raw === "-" || !raw.trim()) {
      return 0;
    }
    var parts = raw.split(/\s→\s/);
    return parts.length >= 2 ? parts.length : 1;
  }

  function descriptionCellHtml(desc) {
    var raw = desc == null ? "" : String(desc);
    if (raw === "-") {
      raw = "";
    }
    if (!raw) {
      return '<span class="nsm-cell-empty">-</span>';
    }
    var parts = raw.split(/\s→\s/);
    if (parts.length >= 2) {
      var lines = parts
        .map(function (part) {
          var text = part.trim();
          if (!text) {
            return "";
          }
          return (
            '<span class="nsm-ag-description-part">' +
            escapeHtml(text) +
            "</span>"
          );
        })
        .join("");
      return '<div class="nsm-ag-description-lines">' + lines + "</div>";
    }
    return (
      '<span class="nsm-ag-description-text">' + escapeHtml(raw) + "</span>"
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
    } catch (e) {
      console.warn("NSM rules grid: initial filter model failed", e);
    }
  }

  function hasActiveGridFilters(api) {
    if (!api || typeof api.getFilterModel !== "function") {
      return false;
    }
    var model = api.getFilterModel();
    return !!(model && Object.keys(model).length);
  }

  function hasActiveFilterQuery(config) {
    if (config && config.useServerFilterQ) {
      if (config.activeFilterQ || config.activeRulebookId || config.activeRulebook) {
        return true;
      }
      var params = new URLSearchParams(window.location.search);
      return (
        params.has("filter_q") ||
        params.has("rulebook") ||
        params.has("rulebook_id")
      );
    }
    if (config && config.filterQuery) {
      return true;
    }
    return new URLSearchParams(window.location.search).has("filter_q");
  }

  function stripFilterQueryFromUrl(config) {
    var url = new URL(window.location.href);
    url.searchParams.delete("filter_q");
    url.searchParams.delete("nsm_q");
    url.searchParams.delete("rulebook");
    url.searchParams.delete("rulebook_id");
    var next = url.pathname + url.search + url.hash;
    window.history.replaceState(null, "", next);
    if (config) {
      config.filterQuery = "";
      if (config.useServerFilterQ) {
        config.activeFilterQ = "";
        config.activeRulebookId = null;
        config.activeRulebook = "";
      }
    }
  }

  function syncAllRulesFilterToUrl(config) {
    if (!config || !config.useServerFilterQ) {
      return;
    }
    var url = new URL(window.location.href);
    url.searchParams.delete("filter_q");
    url.searchParams.delete("rulebook");
    url.searchParams.delete("rulebook_id");
    var body = (config.activeFilterQ || "").trim();
    if (config.activeRulebookId) {
      url.searchParams.set("rulebook_id", String(config.activeRulebookId));
    } else if (config.activeRulebook) {
      url.searchParams.set("rulebook", config.activeRulebook);
    }
    if (body) {
      url.searchParams.set("filter_q", body);
    }
    var next = url.pathname + url.search + url.hash;
    window.history.replaceState(null, "", next);
    config.filterQuery = body;
  }

  function setToolbarButtonVisible(btn, visible) {
    if (!btn) {
      return;
    }
    btn.classList.toggle("d-none", !visible);
  }

  function countDisplayedRulesRows(api) {
    var displayed = 0;
    if (api && typeof api.forEachNodeAfterFilter === "function") {
      api.forEachNodeAfterFilter(function (node) {
        if (node && node.data && node.data._rowType !== "group") {
          displayed += 1;
        }
      });
    }
    return displayed;
  }

  function updateClearFiltersButton(gridApi, config) {
    var btn = document.getElementById("nsm-ag-clear-filters");
    if (!btn) {
      return;
    }
    var active = hasActiveFilterQuery(config) || hasActiveGridFilters(gridApi);
    setToolbarButtonVisible(btn, active);
    var countEl = document.getElementById("nsm-ag-filter-match-count");
    if (!countEl) {
      return;
    }
    if (!active) {
      countEl.textContent = "";
      return;
    }
    var displayed = countDisplayedRulesRows(gridApi);
    var rowLabel =
      displayed === 1
        ? btn.getAttribute("data-count-row-one") || "row"
        : btn.getAttribute("data-count-row-many") || "rows";
    countEl.textContent = "(" + displayed + " " + rowLabel + ")";
    var baseLabel = btn.getAttribute("data-clear-label") || "Clear filters";
    btn.setAttribute(
      "aria-label",
      baseLabel + " — " + displayed + " " + rowLabel
    );
  }

  function clearAllRulesFilters(gridApi, config) {
    if (gridApi && typeof gridApi.setFilterModel === "function") {
      gridApi.setFilterModel(null);
    }
    if (config && config.useServerFilterQ) {
      config.activeFilterQ = "";
      config.activeRulebookId = null;
      config.activeRulebook = "";
    }
    if (hasActiveFilterQuery(config)) {
      stripFilterQueryFromUrl(config);
    }
    filterQueryEditing = false;
    updateFilterQueryInput(gridApi, config, true);
    if (config && config.useServerFilterQ && gridApi && gridApi._nsmDatasourceState) {
      reloadRulesGridData(gridApi, config, gridApi._nsmDatasourceState);
    }
  }

  function quoteNsmQueryValue(value) {
    var text = String(value == null ? "" : value).trim();
    return (
      '"' +
      text.replace(/\\/g, "\\\\").replace(/"/g, '\\"') +
      '"'
    );
  }

  function formatShorthandFilterValue(value, operator) {
    var text = String(value == null ? "" : value).trim();
    var formatted =
      /^[\w\-:.]+$/.test(text) ? text : quoteNsmQueryValue(text);
    if (operator === "!=") {
      return "!= " + formatted;
    }
    return formatted;
  }

  function agFilterConditionToShorthand(condition) {
    if (!condition || condition.filter == null || String(condition.filter).trim() === "") {
      return null;
    }
    var value = String(condition.filter).trim();
    var agType = condition.type || "equals";
    var op = agType === "notEqual" || agType === "notContains" ? "!=" : "=";
    return formatShorthandFilterValue(value, op);
  }

  function serializeColumnFilterToNsm(shorthandName, colFilter) {
    if (!colFilter) {
      return null;
    }
    if (colFilter.conditions && colFilter.conditions.length) {
      var joinOp = (colFilter.operator || "AND").toUpperCase();
      var parts = [];
      colFilter.conditions.forEach(function (cond) {
        var clause = agFilterConditionToShorthand(cond);
        if (clause) {
          parts.push(clause);
        }
      });
      if (!parts.length) {
        return null;
      }
      var inner = parts.length === 1 ? parts[0] : parts.join(" " + joinOp + " ");
      if (shorthandName === "__bare_name__") {
        return "(" + inner + ")";
      }
      if (!shorthandName) {
        return null;
      }
      return shorthandName + "(" + inner + ")";
    }
    var single = agFilterConditionToShorthand(colFilter);
    if (!single) {
      return null;
    }
    if (shorthandName === "__bare_name__") {
      return "(" + single + ")";
    }
    if (!shorthandName) {
      return null;
    }
    return shorthandName + "(" + single + ")";
  }

  function sortedFilterModelColIds(filterModel, columnOrder) {
    var colIds = Object.keys(filterModel || {});
    if (!columnOrder || !columnOrder.length) {
      return colIds.sort();
    }
    var priority = {};
    columnOrder.forEach(function (colId, idx) {
      priority[colId] = idx;
    });
    return colIds.sort(function (a, b) {
      var rankA = Object.prototype.hasOwnProperty.call(priority, a)
        ? priority[a]
        : columnOrder.length;
      var rankB = Object.prototype.hasOwnProperty.call(priority, b)
        ? priority[b]
        : columnOrder.length;
      if (rankA !== rankB) {
        return rankA - rankB;
      }
      return a < b ? -1 : a > b ? 1 : 0;
    });
  }

  function serializeFilterModelToNsmQuery(
    filterModel,
    columnMap,
    shorthandNames,
    columnOrder
  ) {
    if (!filterModel || !columnMap) {
      return "";
    }
    var clauses = [];
    sortedFilterModelColIds(filterModel, columnOrder).forEach(function (colId) {
      var fieldPath = columnMap[colId];
      if (!fieldPath) {
        return;
      }
      var shorthand =
        shorthandNames && Object.prototype.hasOwnProperty.call(shorthandNames, colId)
          ? shorthandNames[colId]
          : fieldPath;
      var clause = serializeColumnFilterToNsm(shorthand, filterModel[colId]);
      if (clause) {
        clauses.push(clause);
      }
    });
    return clauses.join(" AND ");
  }

  var filterQueryEditing = false;
  var filterQueryValidateTimer = null;

  function setFilterQueryValidationState(state, message) {
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
      if (state === "invalid" && message) {
        errorEl.textContent = message;
        errorEl.classList.remove("d-none");
      } else {
        errorEl.textContent = "";
        errorEl.classList.add("d-none");
      }
    }
  }

  function clearFilterQueryValidationState() {
    setFilterQueryValidationState(null, "");
  }

  function fetchRulesFilterQueryValidation(config, text, callback) {
    if (!config || !config.queryValidateUrl) {
      callback(null);
      return;
    }
    var params = new URLSearchParams();
    if (config.useServerFilterQ) {
      if (config.activeRulebookId) {
        params.set("rulebook_id", String(config.activeRulebookId));
      } else if (config.activeRulebook) {
        params.set("rulebook", config.activeRulebook);
      }
      params.set("filter_q", text || "");
    } else {
      params.set("q", text || "");
    }
    var url =
      config.queryValidateUrl +
      (config.queryValidateUrl.indexOf("?") >= 0 ? "&" : "?") +
      params.toString();
    var fetchFn =
      window.NSM_BRANCH_API && window.NSM_BRANCH_API.fetch
        ? window.NSM_BRANCH_API.fetch
        : fetch;
    fetchFn(url, { credentials: "same-origin" })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        callback(data);
      })
      .catch(function () {
        callback({ valid: false, error: "Validation failed" });
      });
  }

  function scheduleFilterQueryValidation(config) {
    var input = document.getElementById("nsm-ag-filter-query");
    if (!input || !config || !config.queryValidateUrl) {
      return;
    }
    if (filterQueryValidateTimer) {
      window.clearTimeout(filterQueryValidateTimer);
    }
    filterQueryValidateTimer = window.setTimeout(function () {
      filterQueryValidateTimer = null;
      var text = (input.value || "").trim();
      if (!text) {
        clearFilterQueryValidationState();
        return;
      }
      fetchRulesFilterQueryValidation(config, text, function (data) {
        if (!data) {
          return;
        }
        if (data.valid) {
          setFilterQueryValidationState("valid", "");
          var normalizedText =
            (config.useServerFilterQ && data.filterQ) || data.normalized || "";
          if (normalizedText && normalizedText !== text && filterQueryEditing) {
            input.value = normalizedText;
          }
        } else {
          setFilterQueryValidationState("invalid", data.error || "Invalid query");
        }
      });
    }, 300);
  }

  function applyRulesFilterQuery(gridApi, config, filterModel, filterQText, scopeMeta) {
    scopeMeta = scopeMeta || {};
    if (config && config.useServerFilterQ) {
      config.activeFilterQ = (filterQText || "").trim();
      if (scopeMeta.rulebookId != null) {
        config.activeRulebookId = scopeMeta.rulebookId;
        config.activeRulebook = scopeMeta.rulebook || "";
      } else if (scopeMeta.rulebook) {
        config.activeRulebook = scopeMeta.rulebook;
        config.activeRulebookId = null;
      }
      if (gridApi && typeof gridApi.setFilterModel === "function") {
        gridApi.setFilterModel(null);
      }
    } else if (gridApi && typeof gridApi.setFilterModel === "function") {
      gridApi.setFilterModel(
        filterModel && Object.keys(filterModel).length ? filterModel : null
      );
    }
    if (config && config.useServerFilterQ) {
      if (hasActiveFilterQuery(config)) {
        syncAllRulesFilterToUrl(config);
      } else {
        stripFilterQueryFromUrl(config);
      }
    } else if (hasActiveFilterQuery(config)) {
      stripFilterQueryFromUrl(config);
    }
    filterQueryEditing = false;
    clearFilterQueryValidationState();
    if (gridApi) {
      updateClearFiltersButton(gridApi, config);
      updateFilterQueryInput(gridApi, config, true);
      if (config && config.useServerFilterQ && config.gridDataUrl) {
        var state = gridApi._nsmDatasourceState;
        if (state) {
          reloadRulesGridData(gridApi, config, state);
        }
      }
    }
  }

  function updateRowStatsForProfile(api, total, state, config, profile) {
    profile = profile || (state && state.domProfile) || NSM_GRID_PROFILES.rules;
    var rowEl = document.getElementById(profile.rowStatsId);
    var selEl = profile.selectedStatsId
      ? document.getElementById(profile.selectedStatsId)
      : null;
    if (!rowEl) {
      return;
    }
    var effectiveTotal =
      state && typeof state.knownTotalRows === "number" && state.knownTotalRows > 0
        ? state.knownTotalRows
        : total;
    var loaded =
      state && typeof state.loadedRowCount === "number"
        ? state.loadedRowCount
        : 0;
    var displayed = countDisplayedRulesRows(api);
    if (loaded > 0 && loaded < effectiveTotal) {
      var maxLoadable = resolveRulesMaxLoadableRows(state, config);
      if (maxLoadable < effectiveTotal) {
        rowEl.textContent =
          loaded + " / " + effectiveTotal + " rows loaded (showing up to " + maxLoadable + ")";
      } else {
        rowEl.textContent = loaded + " / " + effectiveTotal + " rows loaded";
      }
    } else if (displayed === effectiveTotal) {
      rowEl.textContent =
        effectiveTotal + (effectiveTotal === 1 ? " row" : " rows");
    } else {
      rowEl.textContent = displayed + " of " + effectiveTotal + " rows";
    }
    if (selEl && api) {
      var n = api.getSelectedRows().length;
      selEl.textContent = n > 0 ? n + (n === 1 ? " selected" : " selected") : "";
    }
    updateRulesLoadMoreButton(state, config, profile);
  }

  function tryApplyFilterQueryInput(gridApi, config) {
    var input = document.getElementById("nsm-ag-filter-query");
    if (!input) {
      return;
    }
    var text = (input.value || "").trim();
    if (!text) {
      applyRulesFilterQuery(gridApi, config, {}, "");
      return;
    }
    fetchRulesFilterQueryValidation(config, text, function (data) {
      if (!data || !data.valid) {
        setFilterQueryValidationState("invalid", (data && data.error) || "Invalid query");
        return;
      }
      var queryText = (
        (config.useServerFilterQ && data && data.filterQ) ||
        (data && data.normalized) ||
        text
      ).trim();
      applyRulesFilterQuery(
        gridApi,
        config,
        data.filterModel || {},
        queryText,
        {
          rulebookId: data.rulebookId,
          rulebook: data.rulebook,
        }
      );
    });
  }

  function bindFilterQueryInput(gridApi, config) {
    var input = document.getElementById("nsm-ag-filter-query");
    if (!input) {
      return;
    }
    input.readOnly = false;
    input.addEventListener("focus", function () {
      filterQueryEditing = true;
    });
    input.addEventListener("input", function () {
      filterQueryEditing = true;
      scheduleFilterQueryValidation(config);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        tryApplyFilterQueryInput(gridApi, config);
      } else if (e.key === "Escape") {
        filterQueryEditing = false;
        updateFilterQueryInput(gridApi, config, true);
      }
    });
    var applyBtn = document.getElementById("nsm-ag-filter-query-apply");
    if (applyBtn) {
      applyBtn.addEventListener("click", function () {
        tryApplyFilterQueryInput(gridApi, config);
      });
    }
  }

  function resolveFilterQueryText(gridApi, config) {
    if (config && config.useServerFilterQ && config.activeFilterQ) {
      return String(config.activeFilterQ).trim();
    }
    var model =
      gridApi && typeof gridApi.getFilterModel === "function"
        ? gridApi.getFilterModel()
        : null;
    var query = serializeFilterModelToNsmQuery(
      model,
      (config && config.filterColumnMap) || {},
      (config && config.filterColumnShorthand) || null,
      (config && config.filterQueryColumnOrder) || null
    );
    if (!query && config && config.filterQuery) {
      query = config.filterQuery;
    }
    return (query || "").trim();
  }

  function primeFilterQueryInput(config) {
    var input = document.getElementById("nsm-ag-filter-query");
    var wrap = document.getElementById("nsm-ag-filter-query-wrap");
    if (!input || !config) {
      return;
    }
    var query = resolveFilterQueryText(null, config);
    if (!query) {
      return;
    }
    input.value = query;
    if (wrap) {
      wrap.classList.remove("d-none");
    }
  }

  function copyTextViaTextarea(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
      return document.execCommand("copy");
    } catch (e) {
      return false;
    } finally {
      document.body.removeChild(ta);
    }
  }

  function copyTextToClipboard(text, callback) {
    if (!text) {
      if (callback) {
        callback(false);
      }
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(function () {
          if (callback) {
            callback(true);
          }
        })
        .catch(function () {
          if (callback) {
            callback(copyTextViaTextarea(text));
          }
        });
      return;
    }
    if (callback) {
      callback(copyTextViaTextarea(text));
    }
  }

  function updateFilterQueryInput(gridApi, config, force) {
    var input = document.getElementById("nsm-ag-filter-query");
    var wrap = document.getElementById("nsm-ag-filter-query-wrap");
    if (!input) {
      return;
    }
    if (filterQueryEditing && !force) {
      return;
    }
    var query = resolveFilterQueryText(gridApi, config);
    input.value = query;
    if (config && config.filterQueryError && query) {
      setFilterQueryValidationState("invalid", config.filterQueryError);
    } else {
      clearFilterQueryValidationState();
    }
    if (wrap) {
      wrap.classList.toggle("d-none", !query && !config.queryValidateUrl);
    }
  }

  function bindFilterQueryCopyButton(gridApi, config) {
    var btn = document.getElementById("nsm-ag-filter-query-copy");
    var input = document.getElementById("nsm-ag-filter-query");
    if (!btn || !input) {
      return;
    }
    if (btn.dataset.nsmFilterQueryCopyBound === "1") {
      return;
    }
    btn.dataset.nsmFilterQueryCopyBound = "1";
    btn.addEventListener("click", function () {
      var queryText = resolveFilterQueryText(gridApi, config);
      if (!queryText) {
        queryText = (input.value || "").trim();
      }
      if (!queryText) {
        return;
      }
      if (input.value !== queryText) {
        input.value = queryText;
      }
      var copyText = queryText;
      copyTextToClipboard(copyText, function (ok) {
        if (!ok) {
          return;
        }
        var icon = btn.querySelector("i");
        if (!icon) {
          return;
        }
        var prevClass = icon.className;
        icon.className = "mdi mdi-check";
        window.setTimeout(function () {
          icon.className = prevClass;
        }, 1500);
      });
    });
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

  function resolveCellFilterDragContext(gridApi, cellEl, event) {
    if (!gridApi || !cellEl) {
      return null;
    }
    var colId = cellEl.getAttribute("col-id");
    if (!colId || NSM_FILTER_DRAG_EXCLUDED_COLS[colId]) {
      return null;
    }
    if (event && event.target && event.target.closest) {
      if (
        event.target.closest(
          ".nsm-ag-actions-cell, .nsm-ag-action-edit, .nsm-ag-action-delete, .ag-checkbox-input, .ag-selection-checkbox"
        )
      ) {
        return null;
      }
    }
    var rowEl = cellEl.closest(".ag-row, [role='row']");
    if (!rowEl) {
      return null;
    }
    var rowIndexRaw = rowEl.getAttribute("row-index");
    if (rowIndexRaw == null || rowIndexRaw === "") {
      return null;
    }
    var rowNode = gridApi.getDisplayedRowAtIndex(parseInt(rowIndexRaw, 10));
    if (!rowNode || !rowNode.data || rowNode.data._rowType === "group") {
      return null;
    }
    var column =
      typeof gridApi.getColumn === "function" ? gridApi.getColumn(colId) : null;
    if (!column || typeof column.getColDef !== "function") {
      return null;
    }
    var colDef = column.getColDef();
    var params = {
      api: gridApi,
      column: column,
      colDef: colDef,
      data: rowNode.data,
      node: rowNode,
      value:
        typeof gridApi.getValue === "function"
          ? gridApi.getValue(colId, rowNode)
          : rowNode.data[colDef.field],
    };
    var link =
      event && event.target && event.target.closest
        ? event.target.closest(".nsm-ag-cell-link")
        : null;
    var filterValue = "";
    var displayValue = "";
    if (link) {
      displayValue = (link.getAttribute("title") || link.textContent || "").trim();
      filterValue = displayValue;
    } else if (colDef.filterValueGetter) {
      filterValue = String(colDef.filterValueGetter(params) || "").trim();
      displayValue = filterValue;
    } else if (colDef.field && rowNode.data[colDef.field] != null) {
      filterValue = String(rowNode.data[colDef.field]).trim();
      displayValue = filterValue;
    } else {
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

  function markFilterDropTargetsActive(active) {
    var wrap = document.getElementById("nsm-ag-filter-query-wrap");
    var chromeBar = document.querySelector(".nsm-ag-chrome-bar");
    var dropRow = document.querySelector(".nsm-ag-chrome-bar-row");
    [wrap, chromeBar, dropRow].forEach(function (el) {
      if (!el) {
        return;
      }
      el.classList.toggle("nsm-ag-filter-drop-target", active);
      if (!active) {
        el.classList.remove("nsm-ag-filter-drop-hover");
      }
    });
  }

  function bindCellFilterDrag(gridApi, gridEl, config) {
    if (!gridApi || !gridEl || !config || !config.filterColumnMap) {
      return;
    }
    if (gridEl.dataset.nsmFilterCellDragBound === "1") {
      return;
    }
    gridEl.dataset.nsmFilterCellDragBound = "1";

    gridEl.addEventListener(
      "mousedown",
      function (event) {
        if (event.button !== 0) {
          return;
        }
        var cell = event.target.closest(".ag-cell");
        if (!cell || !gridEl.contains(cell)) {
          return;
        }
        var colId = cell.getAttribute("col-id");
        if (!colId || !config.filterColumnMap[colId]) {
          return;
        }
        var ctx = resolveCellFilterDragContext(gridApi, cell, event);
        if (!ctx) {
          return;
        }
        cell.setAttribute("draggable", "true");
      },
      true
    );

    gridEl.addEventListener(
      "dragstart",
      function (event) {
        var cell = event.target.closest(".ag-cell");
        if (!cell || !gridEl.contains(cell)) {
          return;
        }
        var ctx = resolveCellFilterDragContext(gridApi, cell, event);
        if (!ctx || !config.filterColumnMap[ctx.colId]) {
          event.preventDefault();
          return;
        }
        if (!event.dataTransfer) {
          return;
        }
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
        ghost.className = "nsm-ag-group-drag-ghost";
        ghost.textContent = filterDragGhostLabel(config, ctx.colId, ctx.displayValue);
        ghost.setAttribute("aria-hidden", "true");
        document.body.appendChild(ghost);
        event.dataTransfer.setDragImage(ghost, 16, 14);
        window.setTimeout(function () {
          if (ghost.parentNode) {
            ghost.parentNode.removeChild(ghost);
          }
        }, 0);
        cell.classList.add("nsm-ag-cell-filter-dragging");
        markFilterDropTargetsActive(true);
      },
      true
    );

    gridEl.addEventListener(
      "dragend",
      function (event) {
        var cell = event.target.closest(".ag-cell");
        if (cell) {
          cell.removeAttribute("draggable");
          cell.classList.remove("nsm-ag-cell-filter-dragging");
        }
        markFilterDropTargetsActive(false);
      },
      true
    );
  }

  function bindFilterQueryDropTarget(gridApi, config) {
    if (!config || !config.filterColumnMap) {
      return;
    }
    var wrap = document.getElementById("nsm-ag-filter-query-wrap");
    var dropRow =
      document.querySelector(".nsm-ag-chrome-bar-row") ||
      wrap ||
      document.querySelector(".nsm-ag-chrome-bar");
    if (!dropRow || dropRow.dataset.nsmFilterDropBound === "1") {
      return;
    }
    dropRow.dataset.nsmFilterDropBound = "1";

    dropRow.addEventListener("dragover", function (event) {
      if (!isFilterCellDragEvent(event)) {
        return;
      }
      event.preventDefault();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = "copy";
      }
      dropRow.classList.add("nsm-ag-filter-drop-hover");
      if (wrap) {
        wrap.classList.add("nsm-ag-filter-drop-hover");
      }
    });
    dropRow.addEventListener("dragleave", function (event) {
      if (event.target === dropRow || !dropRow.contains(event.relatedTarget)) {
        dropRow.classList.remove("nsm-ag-filter-drop-hover");
        if (wrap) {
          wrap.classList.remove("nsm-ag-filter-drop-hover");
        }
      }
    });
    dropRow.addEventListener("drop", function (event) {
      if (!isFilterCellDragEvent(event)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      dropRow.classList.remove("nsm-ag-filter-drop-hover");
      if (wrap) {
        wrap.classList.remove("nsm-ag-filter-drop-hover");
      }
      markFilterDropTargetsActive(false);
      var raw =
        event.dataTransfer && event.dataTransfer.getData
          ? event.dataTransfer.getData(NSM_FILTER_DRAG_MIME)
          : "";
      if (!raw) {
        return;
      }
      var payload;
      try {
        payload = JSON.parse(raw);
      } catch (e) {
        return;
      }
      var fragment = buildFilterFragmentFromCell(
        config,
        payload.colId,
        payload.filterValue
      );
      if (!fragment) {
        return;
      }
      var input = document.getElementById("nsm-ag-filter-query");
      var queryWrap = document.getElementById("nsm-ag-filter-query-wrap");
      if (!input) {
        return;
      }
      input.value = mergeFilterQueryFragment(input.value, fragment);
      filterQueryEditing = true;
      if (queryWrap) {
        queryWrap.classList.remove("d-none");
      }
      input.focus();
      tryApplyFilterQueryInput(gridApi, config);
    });
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
    return "";
  }

  function objectCellFilterValue(params) {
    var field = params.colDef && params.colDef.field;
    if (params.data && field) {
      var filterKey = field + "__filter";
      if (params.data[filterKey] != null && params.data[filterKey] !== "") {
        return String(params.data[filterKey]);
      }
      var items = params.data[field];
      if (Array.isArray(items) && items.length) {
        return items
          .map(function (item) {
            return item && item.name ? String(item.name) : "";
          })
          .join(" ")
          .trim();
      }
    }
    return "";
  }

  function isRulesGroupRow(params) {
    return !!(params && params.data && params.data._rowType === "group");
  }

  var NSM_COL_VIS_STORAGE_PREFIX = "nsm-ag-col-vis-";
  var NSM_ALWAYS_VISIBLE_COLS = {
    rules: ["_actions"],
    allRules: ["_actions"],
  };

  function columnVisibilityStorageKey(profileKey) {
    return NSM_COL_VIS_STORAGE_PREFIX + profileKey;
  }

  function isColumnPickerHideable(colId, profileKey, groupByEnabled) {
    if (!colId) {
      return false;
    }
    if (colId === POLICY_GROUP_COL_ID) {
      return false;
    }
    var locked = NSM_ALWAYS_VISIBLE_COLS[profileKey] || [];
    return locked.indexOf(colId) < 0;
  }

  function flattenColumnsForPicker(columnDefs, parentHeader) {
    var out = [];
    (columnDefs || []).forEach(function (col) {
      if (col.children && col.children.length) {
        var groupName = col.headerName || parentHeader || "";
        flattenColumnsForPicker(col.children, groupName).forEach(function (child) {
          out.push(child);
        });
        return;
      }
      var colId = col.colId || col.field;
      if (!colId) {
        return;
      }
      var label = col.headerName || colId;
      if (parentHeader) {
        label = parentHeader + " / " + label;
      }
      out.push({ colId: String(colId), label: String(label) });
    });
    return out;
  }

  function loadHiddenColumnIds(profileKey) {
    try {
      var raw = window.localStorage.getItem(columnVisibilityStorageKey(profileKey));
      if (!raw) {
        return null;
      }
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.map(String) : null;
    } catch (e) {
      return null;
    }
  }

  function saveHiddenColumnIds(profileKey, hiddenIds) {
    try {
      window.localStorage.setItem(
        columnVisibilityStorageKey(profileKey),
        JSON.stringify(hiddenIds || [])
      );
    } catch (e) {
      /* ignore quota / private mode */
    }
  }

  function collectHiddenColumnIds(
    api,
    entries,
    profileKey,
    groupByEnabled,
    groupedColIds
  ) {
    var grouped = groupedColIds || (api && api._nsmGroupedColIds) || [];
    var hidden = [];
    (entries || []).forEach(function (entry) {
      if (!entry.hideable || !api || typeof api.getColumn !== "function") {
        return;
      }
      if (grouped.indexOf(entry.colId) >= 0) {
        return;
      }
      var column = api.getColumn(entry.colId);
      if (column && typeof column.isVisible === "function" && !column.isVisible()) {
        hidden.push(entry.colId);
      }
    });
    return hidden.filter(function (colId) {
      return isColumnPickerHideable(colId, profileKey, groupByEnabled);
    });
  }

  function applyStoredColumnVisibility(
    api,
    columnDefs,
    profileKey,
    groupByEnabled,
    config
  ) {
    if (!api || typeof api.setColumnsVisible !== "function") {
      return;
    }
    var stored = loadHiddenColumnIds(profileKey);
    if (!stored || !stored.length) {
      return;
    }
    var groupedColIds =
      groupByEnabled && config ? readGroupedColIdsFromConfig(config) : [];
    var known = {};
    flattenColumnsForPicker(columnDefs).forEach(function (entry) {
      known[entry.colId] = true;
    });
    var toHide = stored.filter(function (colId) {
      return (
        known[colId] &&
        groupedColIds.indexOf(colId) < 0 &&
        isColumnPickerHideable(colId, profileKey, groupByEnabled)
      );
    });
    if (toHide.length) {
      setGridColumnsVisible(api, toHide, false);
    }
  }

  var COLUMN_MENU_ITEMS_BLOCKING_REORDER = {
    pinSubMenu: true,
    resetColumns: true,
  };

  function filterColumnMenuItems(defaultItems) {
    return (defaultItems || []).filter(function (item) {
      return !COLUMN_MENU_ITEMS_BLOCKING_REORDER[item];
    });
  }

  function enforceNonMovableColumnDefs(columnDefs) {
    return (columnDefs || []).map(function (col) {
      if (col.children && col.children.length) {
        return Object.assign({}, col, {
          children: enforceNonMovableColumnDefs(col.children),
        });
      }
      return Object.assign({}, col, { suppressMovable: true });
    });
  }

  function buildColumnMainMenuItems(params, profileKey, groupByEnabled) {
    var defaultItems = filterColumnMenuItems(params.defaultItems || []);
    var colId =
      params.column && typeof params.column.getColId === "function"
        ? params.column.getColId()
        : "";
    if (!isColumnPickerHideable(colId, profileKey, groupByEnabled)) {
      return defaultItems;
    }
    return defaultItems.concat([
      "separator",
      {
        name: "Spalte ausblenden",
        action: function () {
          params.api.setColumnsVisible([colId], false);
        },
      },
    ]);
  }

  function initColumnVisibilityPersistence(
    gridApi,
    columnDefs,
    profileKey,
    groupByEnabled,
    config
  ) {
    if (!gridApi) {
      return;
    }
    gridApi._nsmColumnDefs = columnDefs;
    if (gridApi._nsmColVisBound === profileKey) {
      applyStoredColumnVisibility(
        gridApi,
        columnDefs,
        profileKey,
        groupByEnabled,
        config
      );
      scheduleGroupedColumnVisibility(gridApi, columnDefs, config, profileKey);
      return;
    }
    gridApi._nsmColVisBound = profileKey;

    var entries = flattenColumnsForPicker(columnDefs).map(function (entry) {
      return {
        colId: entry.colId,
        hideable: isColumnPickerHideable(entry.colId, profileKey, groupByEnabled),
      };
    });

    applyStoredColumnVisibility(
      gridApi,
      columnDefs,
      profileKey,
      groupByEnabled,
      config
    );
    syncGroupedColumnVisibility(gridApi, columnDefs, config, profileKey);

    if (typeof gridApi.addEventListener === "function") {
      gridApi.addEventListener("columnVisible", function () {
        var grouped = gridApi._nsmGroupedColIds || [];
        var activeGroupByEnabled = !!(
          gridApi._nsmDatasourceState && gridApi._nsmDatasourceState.groupByEnabled
        );
        saveHiddenColumnIds(
          profileKey,
          collectHiddenColumnIds(
            gridApi,
            entries,
            profileKey,
            activeGroupByEnabled,
            grouped
          )
        );
      });
    }
  }

  function buildRulesDefaultColDef(profileKey, groupByEnabled, extra) {
    var base = {
      minWidth: 72,
      sortable: true,
      filter: true,
      resizable: true,
      floatingFilter: false,
      enableCellChangeFlash: false,
      suppressHeaderMenuButton: false,
      suppressMovable: true,
      editable: false,
      wrapText: false,
      autoHeight: false,
      cellRendererSelector: buildGroupRowCellRendererSelector(),
      getMainMenuItems: function (params) {
        return buildColumnMainMenuItems(params, profileKey, groupByEnabled);
      },
    };
    if (!extra) {
      return base;
    }
    return Object.assign({}, base, extra);
  }

  function buildRulesGroupColumnDef(config) {
    return {
      colId: POLICY_GROUP_COL_ID,
      field: "_groupLabel",
      headerName: (config && config.groupColumnLabel) || "Group",
      pinned: "left",
      lockPosition: "left",
      cellRendererSelector: function (params) {
        if (params.data && params.data._rowType === "group") {
          return { component: "rulesGroupCell" };
        }
        return { component: "emptyCell" };
      },
      width: 280,
      minWidth: 160,
      maxWidth: 480,
      sortable: false,
      filter: false,
      floatingFilter: false,
      resizable: true,
      suppressHeaderMenuButton: true,
      suppressColumnsToolPanel: true,
      suppressFiltersToolPanel: true,
      suppressMovable: true,
      cellClass: "nsm-rules-group-cell",
    };
  }

  function prependRulesGroupColumn(columnDefs, config) {
    var defs = (columnDefs || []).slice();
    if (defs.length && defs[0].colId === POLICY_GROUP_COL_ID) {
      return defs;
    }
    return [buildRulesGroupColumnDef(config)].concat(defs);
  }

  function buildGroupRowCellRendererSelector() {
    return function (params) {
      if (
        params.data &&
        params.data._rowType === "group" &&
        params.colDef &&
        params.colDef.colId !== POLICY_GROUP_COL_ID
      ) {
        return { component: "emptyCell" };
      }
      return undefined;
    };
  }

  var RULES_ROW_HEIGHT = 42;
  var RULES_GROUP_ROW_HEIGHT = 36;
  var RULES_FLOATING_FILTERS_HEIGHT = 36;
  var RULES_ROW_ITEM_HEIGHT = 24;
  var RULES_ROW_CELL_PADDING = 20;
  var POLICY_CELL_TEXT_MAX = 140;
  var POLICY_GRID_FETCH_MAX = 50000;
  var DEFAULT_POLICY_LOAD_LIMIT = 500;
  var DEFAULT_POLICY_LOAD_MORE_STEP = 2000;
  var RULES_GRID_ROW_BUFFER = 5;
  var RULES_GRID_PERF_OPTIONS = {
    rowBuffer: RULES_GRID_ROW_BUFFER,
    suppressColumnVirtualisation: false,
    suppressAnimationFrame: true,
    suppressRowHoverHighlight: true,
  };

  function truncateCellText(text, maxLen) {
    var limit = maxLen == null ? POLICY_CELL_TEXT_MAX : maxLen;
    var raw = text == null ? "" : String(text);
    if (raw.length <= limit) {
      return raw;
    }
    return raw.slice(0, Math.max(0, limit - 1)) + "…";
  }

  function collectRulesObjectFields(columnDefs, out) {
    (columnDefs || []).forEach(function (col) {
      if (col.children) {
        collectRulesObjectFields(col.children, out);
        return;
      }
      if (col.cellRenderer === "objectCell" && col.field) {
        out.push({ field: col.field });
      }
    });
  }

  function maxRulesObjectItems(data, objectFields) {
    var maxItems = 1;
    (objectFields || []).forEach(function (spec) {
      var items = data && data[spec.field];
      var count = Array.isArray(items) ? items.length : 0;
      if (count > maxItems) {
        maxItems = count;
      }
    });
    return maxItems;
  }

  function rulesContentLineCount(data, objectFields) {
    var objectLines = maxRulesObjectItems(data, objectFields);
    var descLines =
      data && data._descriptionLineCount != null
        ? Number(data._descriptionLineCount)
        : rulesDescriptionLineCount(data && data.description);
    return Math.max(objectLines, descLines || 0, 1);
  }

  function computeRulesDataRowHeight(data, objectFields) {
    if (!data || data._rowType === "group") {
      return computeRulesGroupRowHeight(data);
    }
    var lines = rulesContentLineCount(data, objectFields);
    var contentHeight = Math.max(
      RULES_ROW_HEIGHT,
      RULES_ROW_CELL_PADDING + lines * RULES_ROW_ITEM_HEIGHT
    );
    if (data._rowHeight != null && !isNaN(Number(data._rowHeight))) {
      return Math.max(Number(data._rowHeight), contentHeight);
    }
    return contentHeight;
  }

  function resolveRulesRowHeight(data, objectFields) {
    return computeRulesDataRowHeight(data, objectFields);
  }

  var POLICY_TEXT_FILTER_PARAMS = {
    filterOptions: [
      "contains",
      "notContains",
      "equals",
      "notEqual",
      "startsWith",
      "endsWith",
    ],
    defaultOption: "contains",
    debounceMs: 250,
    maxNumConditions: 10,
    defaultJoinOperator: "AND",
  };

  function applyTextColumnFilters(columnDefs, options) {
    options = options || {};
    var enableFilters = options.enableColumnFilters !== false;
    var enableFloating = options.enableFloatingFilters === true;
    (columnDefs || []).forEach(function (col) {
      if (col.children) {
        applyTextColumnFilters(col.children, options);
        return;
      }
      if (
        col.cellRenderer === "objectCell" ||
        col.cellRenderer === "htmlCell" ||
        col.cellRenderer === "statusCell" ||
        col.cellRenderer === "nameLinkCell" ||
        col.cellRenderer === "indexLinkCell" ||
        col.cellRenderer === "rulebookLinkCell"
      ) {
        col.autoHeight = false;
        col.wrapText = false;
        if (enableFilters) {
          col.filter = "agTextColumnFilter";
          col.filterParams = POLICY_TEXT_FILTER_PARAMS;
          col.filterValueGetter =
            col.cellRenderer === "objectCell"
              ? objectCellFilterValue
              : htmlCellFilterValue;
        }
        if (enableFloating) {
          col.floatingFilter = true;
        }
      } else if (col.cellRenderer === "descriptionCell") {
        if (col.autoHeight == null) {
          col.autoHeight = true;
        }
        if (col.wrapText == null) {
          col.wrapText = true;
        }
        if (enableFilters) {
          col.filter = "agTextColumnFilter";
          col.filterParams = POLICY_TEXT_FILTER_PARAMS;
          col.filterValueGetter = htmlCellFilterValue;
        }
        if (enableFloating) {
          col.floatingFilter = true;
        }
      }
    });
  }

  function enableRulesFloatingFilters(api) {
    if (!api || api._nsmFloatingFiltersEnabled) {
      return;
    }
    if (typeof api.getGridOption !== "function") {
      return;
    }
    var columnDefs = api._nsmColumnDefs || api.getGridOption("columnDefs") || [];
    applyTextColumnFilters(columnDefs, {
      enableColumnFilters: true,
      enableFloatingFilters: true,
    });
    api._nsmColumnDefs = columnDefs;
    var defaultColDef = api.getGridOption("defaultColDef") || {};
    var nextDefault = Object.assign({}, defaultColDef, { floatingFilter: true });
    if (defaultColDef.filter !== false) {
      nextDefault.filter = true;
    }
    api._nsmDefaultColDefExtra = { floatingFilter: true };
    if (typeof api.setGridOption === "function") {
      api.setGridOption("floatingFiltersHeight", RULES_FLOATING_FILTERS_HEIGHT);
      api.setGridOption("columnDefs", columnDefs.slice());
      api.setGridOption("defaultColDef", nextDefault);
    }
    api._nsmFloatingFiltersEnabled = true;
    if (typeof api.refreshHeader === "function") {
      api.refreshHeader();
    }
  }

  function scheduleEnableRulesFloatingFilters(api) {
    if (!api) {
      return;
    }
    window.setTimeout(function () {
      enableRulesFloatingFilters(api);
    }, 0);
  }

  function buildObjectCellDom(items, rendererParams) {
    var colored = !(rendererParams && rendererParams.colored === false);
    var wrap = document.createElement("div");
    wrap.className = "nsm-ag-cell-list";
    if (!items || !items.length) {
      wrap.innerHTML = '<span class="nsm-cell-empty">-</span>';
      return wrap;
    }
    for (var i = 0; i < items.length; i++) {
      wrap.appendChild(buildObjectCellItem(items[i], false, colored));
    }
    return wrap;
  }

  function buildObjectCellItem(item, hidden, colored) {
    var span = document.createElement("span");
    span.className = "nsm-ag-cell-item" + (hidden ? " nsm-pill-hidden" : "");
    if (item && item.excluded) {
      span.classList.add("nsm-ag-cell-excluded");
    }
    if (colored && item && item.color) {
      var dot = document.createElement("span");
      dot.className = "nsm-ag-cell-dot";
      dot.style.backgroundColor = item.color;
      dot.setAttribute("aria-hidden", "true");
      span.appendChild(dot);
    }
    var link = document.createElement("a");
    link.href = (item && item.url) || "#";
    link.className = "nsm-ag-cell-link text-decoration-none";
    var fullName = (item && item.name) || "";
    link.title = fullName;
    link.textContent = truncateCellText(fullName);
    span.appendChild(link);
    return span;
  }

  function createRulesObjectCellRenderer() {
    return function (params) {
      return buildObjectCellDom(
        params.value,
        params.colDef && params.colDef.cellRendererParams
      );
    };
  }

  function createRulesGetRowHeight(objectFields) {
    return function (params) {
      if (params.data && params.data._rowType === "group") {
        return computeRulesGroupRowHeight(params.data);
      }
      return resolveRulesRowHeight(params.data, objectFields);
    };
  }

  function createRulesGetRowClass(objectFields) {
    return function (params) {
      if (params.data && params.data._rowType === "group") {
        return "nsm-rules-group-row";
      }
      if (params.data && rulesContentLineCount(params.data, objectFields) > 1) {
        return "nsm-rules-multi-row";
      }
      return null;
    };
  }

  function appendGroupExpansionQuery(url, state) {
    if (!state || !state.groupByEnabled) {
      return url;
    }
    if (state.expandAllGroups) {
      return url + "&expanded=all";
    }
    if (state.collapseAllGroups) {
      return url + "&collapsed=all";
    }
    var expanded = Object.keys(state.expandedGroups || {}).filter(function (key) {
      return state.expandedGroups[key];
    });
    if (expanded.length) {
      return url + "&expanded=" + encodeURIComponent(expanded.join(","));
    }
    var collapsed = Object.keys(state.collapsedGroups || {}).filter(function (key) {
      return state.collapsedGroups[key];
    });
    if (collapsed.length) {
      return url + "&collapsed=" + encodeURIComponent(collapsed.join(","));
    }
    return url + "&collapsed=all";
  }

  function syncGroupExpansionUrl(state) {
    if (!state || !state.groupByEnabled || typeof window === "undefined") {
      return;
    }
    var params = new URLSearchParams(window.location.search);
    params.delete("collapsed");
    params.delete("expanded");
    if (state.expandAllGroups) {
      params.set("expanded", "all");
    } else if (state.collapseAllGroups) {
      params.set("collapsed", "all");
    } else {
      var expanded = Object.keys(state.expandedGroups || {}).filter(function (key) {
        return state.expandedGroups[key];
      });
      if (expanded.length) {
        params.set("expanded", expanded.join(","));
      } else {
        var collapsed = Object.keys(state.collapsedGroups || {}).filter(function (key) {
          return state.collapsedGroups[key];
        });
        if (collapsed.length) {
          params.set("collapsed", collapsed.join(","));
        } else {
          params.set("collapsed", "all");
        }
      }
    }
    var next = params.toString();
    var current = window.location.search.replace(/^\?/, "");
    if (next !== current) {
      window.history.replaceState(null, "", "?" + next);
    }
  }

  function isRulesGroupCollapsed(groupKey, state) {
    if (!state) {
      return false;
    }
    if (state.expandAllGroups) {
      return false;
    }
    if (state.collapseAllGroups) {
      return true;
    }
    if (state.usesExpandedMode) {
      return !state.expandedGroups[groupKey];
    }
    return !!state.collapsedGroups[groupKey];
  }

  function toggleRulesGroupCollapse(groupKey, state) {
    if (!state) {
      return;
    }
    state.expandAllGroups = false;
    if (state.collapseAllGroups) {
      state.collapseAllGroups = false;
      state.usesExpandedMode = true;
      state.expandedGroups[groupKey] = true;
      return;
    }
    if (state.usesExpandedMode) {
      if (state.expandedGroups[groupKey]) {
        delete state.expandedGroups[groupKey];
        if (!Object.keys(state.expandedGroups).length) {
          state.collapseAllGroups = true;
          state.usesExpandedMode = false;
        }
      } else {
        state.expandedGroups[groupKey] = true;
      }
      return;
    }
    if (state.collapsedGroups[groupKey]) {
      delete state.collapsedGroups[groupKey];
    } else {
      state.collapsedGroups[groupKey] = true;
    }
  }

  function createEmptyGroupColumnCell() {
    var span = document.createElement("span");
    span.className = "nsm-ag-group-row-empty";
    span.setAttribute("aria-hidden", "true");
    return span;
  }

  function formatRulesGroupLabelText(label, count) {
    var text = label == null ? "" : String(label);
    if (!count || count <= 0) {
      return text;
    }
    var suffix = " (" + count + ")";
    if (!text) {
      return suffix.trim();
    }
    var lines = text.split("\n");
    lines[lines.length - 1] = lines[lines.length - 1] + suffix;
    return lines.join("\n");
  }

  function computeRulesGroupRowHeight(data) {
    if (!data || data._rowType !== "group") {
      return RULES_GROUP_ROW_HEIGHT;
    }
    if (data._rowHeight != null && !isNaN(Number(data._rowHeight))) {
      return Number(data._rowHeight);
    }
    var label = data._groupLabel == null ? "" : String(data._groupLabel);
    var lineCount = label ? label.split("\n").length : 1;
    return Math.max(
      RULES_GROUP_ROW_HEIGHT,
      RULES_ROW_CELL_PADDING + lineCount * RULES_ROW_ITEM_HEIGHT
    );
  }

  function createRulesGroupCellContent(params, config, state) {
    var data = params.data || {};
    if (data._rowType !== "group") {
      return createEmptyGroupColumnCell();
    }
    var wrap = document.createElement("div");
    var groupLevel = Number(data._groupLevel || 1);
    wrap.className =
      "nsm-rules-group-header nsm-rules-group-cell-inner nsm-rules-group-level-" +
      groupLevel;
    var groupKey = String(data._groupKey == null ? "" : data._groupKey);
    var collapsed = isRulesGroupCollapsed(groupKey, state);
    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "nsm-rules-group-toggle";
    toggle.setAttribute(
      "aria-label",
      collapsed ? "Expand group" : "Collapse group"
    );
    toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    toggle.innerHTML =
      '<i class="mdi ' +
      (collapsed ? "mdi-chevron-right" : "mdi-chevron-down") +
      '" aria-hidden="true"></i>';
    toggle.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      toggleRulesGroupCollapse(groupKey, state);
      syncGroupExpansionUrl(state);
      reloadRulesGridData(params.api, config, state, null, { groupingOnly: true });
    });
    wrap.appendChild(toggle);

    if (data._groupColor) {
      var dot = document.createElement("span");
      dot.className = "nsm-rules-group-dot me-2";
      dot.style.backgroundColor = data._groupColor;
      wrap.appendChild(dot);
    }

    var label = data._groupLabel == null ? "" : String(data._groupLabel);
    var count = data._ruleCount == null ? 0 : Number(data._ruleCount);
    var labelText = formatRulesGroupLabelText(label, count);
    var url = data._groupUrl || "#";
    if (url && url !== "#") {
      var link = document.createElement("a");
      link.href = url;
      link.className = "nsm-rules-group-label text-body text-decoration-none";
      link.textContent = labelText;
      wrap.appendChild(link);
    } else {
      var span = document.createElement("span");
      span.className = "nsm-rules-group-label";
      span.textContent = labelText;
      wrap.appendChild(span);
    }
    return wrap;
  }

  function createRulesGroupCellRenderer(config, state) {
    return function (params) {
      var data = params.data || {};
      if (data._rowType !== "group") {
        return createEmptyGroupColumnCell();
      }
      return createRulesGroupCellContent(params, config, state);
    };
  }

  function bindNsmGroupToolbar(gridApi, config, state, gridEl, profileKey, columnDefs) {
    normalizeGroupLevelsInConfig(config);
    renderGroupSourceChips(config);
    renderGroupPills(config);
    bindGroupDropZone(config);
    bindGroupExpandCollapseButtons(config, state, gridApi);
    syncGroupToolbarVisibility(config);
    initGroupHelpTooltip();
    if (gridApi && gridEl) {
      function currentColumnDefs() {
        return gridApi._nsmColumnDefs || columnDefs || [];
      }
      scheduleGroupedColumnVisibility(
        gridApi,
        currentColumnDefs(),
        config,
        profileKey
      );
      var rebindHeaders = attachGroupableHeaderDrag(
        gridApi,
        gridEl,
        config,
        profileKey
      );
      gridApi._nsmRebindGroupHeaders = rebindHeaders;
      if (typeof gridApi.addEventListener === "function") {
        [
          "displayedColumnsChanged",
          "columnPinned",
          "gridColumnsChanged",
          "columnVisible",
          "firstDataRendered",
        ].forEach(function (eventName) {
          gridApi.addEventListener(eventName, rebindHeaders);
        });
        gridApi.addEventListener("gridColumnsChanged", function () {
          scheduleGroupedColumnVisibility(
            gridApi,
            currentColumnDefs(),
            config,
            profileKey
          );
        });
        gridApi.addEventListener("firstDataRendered", function () {
          scheduleGroupedColumnVisibility(
            gridApi,
            currentColumnDefs(),
            config,
            profileKey
          );
        });
        gridApi.addEventListener("modelUpdated", function () {
          if (!config || !config.groupBy) {
            return;
          }
          scheduleGroupedColumnVisibility(
            gridApi,
            currentColumnDefs(),
            config,
            profileKey
          );
        });
      }
      scheduleGroupHeaderBind(rebindHeaders);
    }
    NSM_GROUP_NAV_CTX = {
      gridApi: gridApi,
      config: config,
      state: state,
      profileKey: profileKey,
      gridEl: gridEl,
    };
  }

  function buildRulesGridCacheKey(config, state) {
    var parts = [state && state.profileKey ? state.profileKey : "rules"];
    if (config && config.activeRulebookId) {
      parts.push("rb:" + String(config.activeRulebookId));
    } else if (config && config.activeRulebook) {
      parts.push("rb:" + String(config.activeRulebook));
    }
    if (config && config.activeFilterQ) {
      parts.push("fq:" + String(config.activeFilterQ));
    } else if (config && config.filterQuery) {
      parts.push("fq:" + String(config.filterQuery));
    }
    return parts.join("|");
  }

  function isRulesTabCacheFresh(cache) {
    if (!cache || !cache.fetchedAt) {
      return false;
    }
    return Date.now() - cache.fetchedAt < RULES_TAB_CACHE_TTL_MS;
  }

  function storeRulesTabDataCache(state, cacheKey, rows, totalCount) {
    if (!state) {
      return;
    }
    state.rulesDataCache = {
      cacheKey: cacheKey,
      flatRows: rows,
      totalCount: totalCount,
      fetchedAt: Date.now(),
    };
  }

  function getRulesTabDataCache(state, config) {
    if (isRulesTabRefreshRequested()) {
      return null;
    }
    var cache = state && state.rulesDataCache;
    if (!cache) {
      return null;
    }
    if (!isRulesTabCacheFresh(cache)) {
      invalidateRulesTabDataCache(state);
      return null;
    }
    if (cache.cacheKey !== buildRulesGridCacheKey(config, state)) {
      return null;
    }
    return cache;
  }

  function invalidateRulesTabDataCache(state) {
    if (state) {
      state.rulesDataCache = null;
    }
  }

  function isRulesTabDownloadComplete(state) {
    if (!state) {
      return false;
    }
    var rows = state._accumulatedRows;
    if (!rows || !rows.length) {
      return false;
    }
    var total = state.knownTotalRows || rows.length;
    return rows.length >= total;
  }

  function applyRulesTabCacheToGrid(api, config, state, cache, done) {
    if (!api || !state || !cache || !cache.flatRows || !cache.flatRows.length) {
      if (typeof done === "function") {
        done(0);
      }
      return false;
    }
    cancelProgressiveRulesLoad(state);
    state.knownTotalRows = cache.totalCount;
    state.loadedRowCount = cache.flatRows.length;
    setRulesGridRows(api, cache.flatRows.slice(), state, "set");
    notifyRulesRowsLoaded(state, cache.totalCount, false);
    window.requestAnimationFrame(function () {
      resetRulesRowHeights(api, !!(state && state.groupByEnabled));
      scheduleAutoSizeRulesContentColumns(api, state);
      enableRulesFloatingFilters(api);
    });
    if (typeof done === "function") {
      done(cache.totalCount);
    }
    return true;
  }

  function maybePersistRulesTabDataCache(state, config) {
    if (!state || state.groupByEnabled) {
      return;
    }
    if (!isRulesTabDownloadComplete(state)) {
      return;
    }
    var rows = state._accumulatedRows;
    storeRulesTabDataCache(
      state,
      buildRulesGridCacheKey(config, state),
      rows.slice(),
      state.knownTotalRows || rows.length
    );
  }

  function buildRulesGridFetchUrl(config, state, start, end, filterModel, fetchOptions) {
    fetchOptions = fetchOptions || {};
    if (!config || !config.gridDataUrl) {
      return null;
    }
    var url =
      config.gridDataUrl +
      "?startRow=" +
      encodeURIComponent(start) +
      "&endRow=" +
      encodeURIComponent(end);
    if (config.useServerFilterQ) {
      if (config.activeRulebookId) {
        url += "&rulebook_id=" + encodeURIComponent(String(config.activeRulebookId));
      } else if (config.activeRulebook) {
        url += "&rulebook=" + encodeURIComponent(config.activeRulebook);
      }
      if (config.activeFilterQ) {
        url += "&filter_q=" + encodeURIComponent(config.activeFilterQ);
      }
    } else if (config.activeFilterQ) {
      url += "&filter_q=" + encodeURIComponent(config.activeFilterQ);
    } else if (filterModel && Object.keys(filterModel).length) {
      url += "&filter=" + encodeURIComponent(JSON.stringify(filterModel));
    }
    if (config.groupBy) {
      url += "&group_by=" + encodeURIComponent(String(config.groupBy));
      if (config.groupBy2) {
        url += "&group_by_2=" + encodeURIComponent(String(config.groupBy2));
      }
      url = appendGroupExpansionQuery(url, state);
    }
    if (isRulesTabRefreshRequested()) {
      url += "&refresh=1";
    } else if (fetchOptions.useCached) {
      url += "&use_cached=1";
    }
    return url;
  }

  function rulesLoadUtf8ByteCount(text) {
    if (typeof TextEncoder !== "undefined") {
      return new TextEncoder().encode(text).length;
    }
    return new Blob([text]).size;
  }

  function recordRulesLoadBytes(state, byteCount) {
    if (!state || typeof byteCount !== "number" || byteCount <= 0) {
      return;
    }
    state.loadedBytes = (state.loadedBytes || 0) + byteCount;
  }

  function formatRulesLoadCount(value) {
    var num = Math.floor(Number(value) || 0);
    if (num < 1000) {
      return String(num);
    }
    var thousands = num / 1000;
    if (num < 10000) {
      var rounded = Math.round(thousands * 10) / 10;
      return (
        (rounded % 1 === 0 ? String(Math.round(rounded)) : rounded.toFixed(1)) +
        "k"
      );
    }
    return Math.round(thousands) + "k";
  }

  function formatRulesLoadBytes(bytes) {
    var num = Number(bytes) || 0;
    if (num <= 0) {
      return "";
    }
    if (num < 1024) {
      return num + " B";
    }
    if (num < 1024 * 1024) {
      var kb = num / 1024;
      var kbRounded = kb >= 100 ? Math.round(kb) : Math.round(kb * 10) / 10;
      return (
        (kbRounded % 1 === 0 ? String(Math.round(kbRounded)) : kbRounded.toFixed(1)) +
        " KB"
      );
    }
    var mb = num / (1024 * 1024);
    var mbRounded = mb >= 100 ? Math.round(mb) : Math.round(mb * 10) / 10;
    return (
      (mbRounded % 1 === 0 ? String(Math.round(mbRounded)) : mbRounded.toFixed(1)) +
      " MB"
    );
  }

  function resetRulesLoadMetrics(state) {
    if (!state) {
      return;
    }
    state.loadedBytes = 0;
  }

  function fetchRulesGridRows(config, state, start, end, filterModel, fetchOptions) {
    var url = buildRulesGridFetchUrl(
      config,
      state,
      start,
      end,
      filterModel,
      fetchOptions
    );
    if (!url) {
      return Promise.reject(new Error("rules grid url missing"));
    }
    return fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    }).then(function (response) {
      if (!response.ok) {
        throw new Error("rules grid fetch failed");
      }
      var headerLength = parseInt(response.headers.get("Content-Length"), 10);
      return response.text().then(function (text) {
        var byteCount =
          !isNaN(headerLength) && headerLength > 0
            ? headerLength
            : rulesLoadUtf8ByteCount(text);
        recordRulesLoadBytes(state, byteCount);
        return JSON.parse(text);
      });
    });
  }

  function buildProgressiveLoadSteps(config, targetTotal) {
    var target = Math.max(0, intTarget(targetTotal));
    if (target <= 0) {
      return [];
    }
    if (target <= 250) {
      var fine = config.gridLoadStepsFine || [5, 10, 20, 50, 100, 250];
      return buildUniqueSortedSteps(fine, target);
    }
    var options = config.gridLoadSteps;
    if (options && options.length) {
      return buildUniqueSortedSteps(options, target);
    }
    return buildExponentialLoadSteps(target, config);

    function intTarget(value) {
      var n = Number(value);
      return isNaN(n) ? 0 : Math.floor(n);
    }

    function buildUniqueSortedSteps(steps, cap) {
      var out = [];
      var seen = {};
      (steps || []).forEach(function (n) {
        if (n > 0 && n < cap && !seen[n]) {
          seen[n] = true;
          out.push(n);
        }
      });
      if (!seen[cap]) {
        out.push(cap);
      }
      out.sort(function (a, b) {
        return a - b;
      });
      return out;
    }

    function buildExponentialLoadSteps(cap, cfg) {
      var out = [];
      var batch = Number(cfg.gridLoadStepInitial) || 10;
      var maxBatch = Number(cfg.gridLoadStepMax) || 5000;
      var end = 0;
      while (end < cap) {
        end = Math.min(cap, end + batch);
        out.push(end);
        batch = Math.min(maxBatch, batch * 2);
      }
      return out;
    }
  }

  function cancelProgressiveRulesLoad(state) {
    if (!state) {
      return;
    }
    state.progressiveLoadToken = (state.progressiveLoadToken || 0) + 1;
    state.progressiveLoadActive = false;
  }

  function notifyRulesRowsLoaded(state, total, partial) {
    if (!state || typeof state.onRowsLoaded !== "function") {
      return;
    }
    state.onRowsLoaded(total, { partial: !!partial });
    updateRulesLoadStatus(state);
  }

  function hideRulesLoadStatus(state) {
    var profile =
      (state && state.domProfile) || NSM_GRID_PROFILES.rules;
    var wrap = document.getElementById(profile.loadStatusId);
    var track = document.getElementById(profile.loadTrackId);
    var progressEl = document.getElementById(profile.loadProgressId);
    var labelEl = document.getElementById(profile.loadLabelId);
    if (!wrap || !track || !progressEl || !labelEl) {
      return;
    }
    wrap.classList.add("d-none");
    progressEl.style.width = "0%";
    track.setAttribute("aria-valuenow", "0");
    track.removeAttribute("aria-valuetext");
    labelEl.textContent = "";
    labelEl.removeAttribute("title");
    resetRulesLoadMetrics(state);
  }

  function updateRulesLoadStatus(state) {
    var profile =
      (state && state.domProfile) || NSM_GRID_PROFILES.rules;
    var wrap = document.getElementById(profile.loadStatusId);
    var track = document.getElementById(profile.loadTrackId);
    var progressEl = document.getElementById(profile.loadProgressId);
    var labelEl = document.getElementById(profile.loadLabelId);
    if (!wrap || !track || !progressEl || !labelEl) {
      return;
    }

    var loaded =
      state && typeof state.loadedRowCount === "number" ? state.loadedRowCount : 0;
    var total =
      state && typeof state.knownTotalRows === "number" ? state.knownTotalRows : 0;
    var active = !!(
      state &&
      (state.progressiveLoadActive || state.initialLoadActive)
    );
    var complete = total > 0 && loaded >= total;

    if (!active || complete) {
      hideRulesLoadStatus(state);
      return;
    }

    wrap.classList.remove("d-none");
    var pct = total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
    progressEl.style.width = pct + "%";
    track.setAttribute("aria-valuenow", String(pct));
    var prefix = wrap.getAttribute("data-loading-label") || "Loading rules";
    var label = prefix + " — " + formatRulesLoadCount(loaded) + " / " + formatRulesLoadCount(total);
    if (total > 0) {
      label += " (" + pct + "%)";
    }
    var bytes =
      state && typeof state.loadedBytes === "number" ? state.loadedBytes : 0;
    var sizeLabel = formatRulesLoadBytes(bytes);
    if (sizeLabel) {
      label += " · " + sizeLabel;
    }
    labelEl.textContent = label;
    labelEl.title = prefix + " — " + loaded + " / " + total + (total > 0 ? " (" + pct + "%)" : "") + (sizeLabel ? " · " + sizeLabel : "");
    track.setAttribute("aria-valuetext", label);
  }

  function flushRulesGridAsyncTransactions(api) {
    if (api && typeof api.flushAsyncTransactions === "function") {
      api.flushAsyncTransactions();
    }
  }

  function setRulesGridRows(api, rows, state, mode) {
    if (!api) {
      return;
    }
    if (mode === "set") {
      flushRulesGridAsyncTransactions(api);
      state._accumulatedRows = rows || [];
      if (typeof api.setGridOption === "function") {
        api.setGridOption("rowData", state._accumulatedRows);
      } else if (typeof api.setRowData === "function") {
        api.setRowData(state._accumulatedRows);
      }
      return;
    }
    if (!rows || !rows.length) {
      return;
    }
    state._accumulatedRows = (state._accumulatedRows || []).concat(rows);
    if (typeof api.applyTransactionAsync === "function") {
      api.applyTransactionAsync({ add: rows });
      return;
    }
    if (typeof api.applyTransaction === "function") {
      api.applyTransaction({ add: rows });
      return;
    }
    flushRulesGridAsyncTransactions(api);
    if (typeof api.setGridOption === "function") {
      api.setGridOption("rowData", state._accumulatedRows);
    } else if (typeof api.setRowData === "function") {
      api.setRowData(state._accumulatedRows);
    }
  }

  function loadAllRulesClientRows(api, config, state, done, fetchOptions) {
    if (!config || !config.gridDataUrl) {
      if (typeof done === "function") {
        done(state && state.knownTotalRows);
      }
      return Promise.resolve([]);
    }
    if (state && state.gridEl) {
      state.gridEl.classList.add("nsm-ag-grid-loading");
    }
    state.initialLoadActive = true;
    resetRulesLoadMetrics(state);
    updateRulesLoadStatus(state);
    var totalHint = resolveRulesLoadEndRow(config, state);
    var filterModel = getActiveRulesFilterModel(api, config, state);
    return fetchRulesGridRows(
      config,
      state,
      0,
      totalHint,
      filterModel,
      fetchOptions
    )
      .then(function (data) {
        var rows = data.rowData || [];
        if (state) {
          state.knownTotalRows =
            typeof data.lastRow === "number" ? data.lastRow : rows.length;
          state.loadedRowCount = rows.length;
          state.progressiveLoadActive = false;
          state.initialLoadActive = false;
          notifyRulesRowsLoaded(state, state.knownTotalRows, false);
          maybePersistRulesTabDataCache(state, config);
          if (isRulesTabRefreshRequested()) {
            stripRulesTabRefreshFromUrl();
          }
        }
        setRulesGridRows(api, rows, state, "set");
        window.requestAnimationFrame(function () {
          resetRulesRowHeights(api, state && state.groupByEnabled);
          scheduleAutoSizeRulesContentColumns(api, state);
        });
        if (typeof done === "function") {
          done(state ? state.knownTotalRows : rows.length);
        }
        return rows;
      })
      .catch(function (err) {
        console.error("NSM rules grid: client row load failed", err);
        if (state) {
          state.progressiveLoadActive = false;
          state.initialLoadActive = false;
          updateRulesLoadStatus(state);
        }
        if (typeof done === "function") {
          done(state ? state.knownTotalRows : 0);
        }
        return [];
      })
      .finally(function () {
        if (state && state.gridEl) {
          state.gridEl.classList.remove("nsm-ag-grid-loading");
        }
        if (api && api._nsmRebindGroupHeaders) {
          scheduleGroupHeaderBind(api._nsmRebindGroupHeaders);
        }
        enableRulesFloatingFilters(api);
      });
  }

  function loadRulesClientRowsProgressive(api, config, state, done) {
    if (!config || !config.gridDataUrl) {
      if (typeof done === "function") {
        done(state && state.knownTotalRows);
      }
      return Promise.resolve([]);
    }

    var targetTotal = resolveRulesLoadEndRow(config, state);
    var steps = buildProgressiveLoadSteps(config, targetTotal);
    if (steps.length <= 1) {
      return loadAllRulesClientRows(api, config, state, done);
    }

    cancelProgressiveRulesLoad(state);
    var token = state.progressiveLoadToken;
    state.progressiveLoadActive = true;
    state.initialLoadActive = true;
    state._accumulatedRows = [];
    resetRulesLoadMetrics(state);

    if (state.gridEl) {
      state.gridEl.classList.add("nsm-ag-grid-loading");
    }
    updateRulesLoadStatus(state);

    var prevEnd = 0;

    function finishLoad() {
      flushRulesGridAsyncTransactions(api);
      state.progressiveLoadActive = false;
      state.initialLoadActive = false;
      maybePersistRulesTabDataCache(state, config);
      if (isRulesTabRefreshRequested()) {
        stripRulesTabRefreshFromUrl();
      }
      if (state.gridEl) {
        state.gridEl.classList.remove("nsm-ag-grid-loading");
      }
      updateRulesLoadStatus(state);
      if (api && api._nsmRebindGroupHeaders) {
        scheduleGroupHeaderBind(api._nsmRebindGroupHeaders);
      }
      scheduleAutoSizeRulesContentColumns(api, state);
      if (typeof done === "function") {
        done(state.knownTotalRows);
      }
      enableRulesFloatingFilters(api);
    }

    function loadStep(stepIndex) {
      if (token !== state.progressiveLoadToken) {
        return Promise.resolve([]);
      }
      if (stepIndex >= steps.length) {
        finishLoad();
        return Promise.resolve(state._accumulatedRows || []);
      }

      var endRow = steps[stepIndex];
      var startRow = prevEnd;
      var isFirst = stepIndex === 0;
      var isLast = stepIndex === steps.length - 1;
      var filterModel = getActiveRulesFilterModel(api, config, state);

      return fetchRulesGridRows(config, state, startRow, endRow, filterModel)
        .then(function (data) {
          if (token !== state.progressiveLoadToken) {
            return [];
          }
          var rows = data.rowData || [];
          if (typeof data.lastRow === "number") {
            state.knownTotalRows = data.lastRow;
          } else if (isFirst) {
            state.knownTotalRows = rows.length;
          }
          setRulesGridRows(api, rows, state, isFirst ? "set" : "add");
          state.loadedRowCount = (state._accumulatedRows || []).length;
          var fetchDone = rulesFetchPageExhausted(
            data,
            startRow,
            endRow,
            state.loadedRowCount
          );
          if (fetchDone) {
            finishLoad();
            return rows;
          }
          if (isLast) {
            state.progressiveLoadActive = false;
            state.initialLoadActive = false;
          }
          notifyRulesRowsLoaded(state, state.knownTotalRows, !isLast && !fetchDone);

          if (isFirst && state.gridEl) {
            state.gridEl.classList.remove("nsm-ag-grid-loading");
          }

          window.requestAnimationFrame(function () {
            if (isLast) {
              flushRulesGridAsyncTransactions(api);
              resetRulesRowHeights(api, state && state.groupByEnabled);
            }
          });

          prevEnd = endRow;
          return new Promise(function (resolve) {
            if (fetchDone) {
              resolve(rows);
              return;
            }
            if (isLast) {
              loadStep(stepIndex + 1).then(resolve);
              return;
            }
            window.setTimeout(function () {
              loadStep(stepIndex + 1).then(resolve);
            }, 16);
          });
        })
        .catch(function (err) {
          console.error("NSM rules grid: progressive row load failed", err);
          finishLoad();
          return [];
        });
    }

    return loadStep(0);
  }

  function loadRulesClientRows(api, config, state, done) {
    var cache = getRulesTabDataCache(state, config);
    if (
      cache &&
      cache.flatRows &&
      cache.flatRows.length &&
      state &&
      !state.groupByEnabled
    ) {
      applyRulesTabCacheToGrid(api, config, state, cache, done);
      return Promise.resolve(cache.flatRows);
    }
    if (state) {
      state.userLoadTarget = resolveRulesInitialLoadTarget(config, state);
    }
    if (state && state.groupByEnabled && state.collapseAllGroups) {
      return loadAllRulesClientRows(api, config, state, done);
    }
    return loadRulesClientRowsProgressive(api, config, state, done);
  }

  function appendRulesClientRows(api, config, state, startRow, endRow, done) {
    if (!config || !config.gridDataUrl || !api || !state) {
      if (typeof done === "function") {
        done(state ? state.loadedRowCount : 0);
      }
      return Promise.resolve([]);
    }
    if (state.gridEl) {
      state.gridEl.classList.add("nsm-ag-grid-loading");
    }
    state.initialLoadActive = true;
    updateRulesLoadStatus(state);
    var filterModel = getActiveRulesFilterModel(api, config, state);
    return fetchRulesGridRows(config, state, startRow, endRow, filterModel)
      .then(function (data) {
        var rows = data.rowData || [];
        if (typeof data.lastRow === "number") {
          state.knownTotalRows = data.lastRow;
        }
        setRulesGridRows(api, rows, state, "add");
        state.loadedRowCount = (state._accumulatedRows || []).length;
        state.initialLoadActive = false;
        notifyRulesRowsLoaded(
          state,
          state.knownTotalRows,
          state.loadedRowCount < resolveRulesMaxLoadableRows(state, config)
        );
        flushRulesGridAsyncTransactions(api);
        window.requestAnimationFrame(function () {
          resetRulesRowHeights(api, state && state.groupByEnabled);
        });
        if (typeof done === "function") {
          done(state.loadedRowCount);
        }
        return rows;
      })
      .catch(function (err) {
        console.error("NSM rules grid: append row load failed", err);
        state.initialLoadActive = false;
        updateRulesLoadStatus(state);
        if (typeof done === "function") {
          done(state ? state.loadedRowCount : 0);
        }
        return [];
      })
      .finally(function () {
        if (state.gridEl) {
          state.gridEl.classList.remove("nsm-ag-grid-loading");
        }
        if (api && api._nsmRebindGroupHeaders) {
          scheduleGroupHeaderBind(api._nsmRebindGroupHeaders);
        }
      });
  }

  function loadMoreRulesRows(api, config, state, done) {
    if (!api || !config || !state || !canLoadMoreRulesRows(state, config)) {
      if (typeof done === "function") {
        done(state ? state.loadedRowCount : 0);
      }
      return Promise.resolve([]);
    }
    var loaded =
      typeof state.loadedRowCount === "number"
        ? state.loadedRowCount
        : (state._accumulatedRows || []).length;
    var maxLoadable = resolveRulesMaxLoadableRows(state, config);
    var step = config.loadMoreStep || DEFAULT_POLICY_LOAD_MORE_STEP;
    state.userLoadTarget = Math.min(maxLoadable, loaded + step);
    return appendRulesClientRows(
      api,
      config,
      state,
      loaded,
      state.userLoadTarget,
      done
    );
  }

  function bindRulesLoadMoreButton(api, config, state, profile) {
    profile = profile || (state && state.domProfile) || NSM_GRID_PROFILES.rules;
    if (!profile.loadMoreBtnId) {
      return;
    }
    var btn = document.getElementById(profile.loadMoreBtnId);
    if (!btn || btn._nsmLoadMoreBound) {
      return;
    }
    btn._nsmLoadMoreBound = true;
    btn.addEventListener("click", function () {
      loadMoreRulesRows(api, config, state, function () {
        updateRowStatsForProfile(api, state.knownTotalRows, state, config, profile);
      });
    });
  }

  function isInfiniteRulesGrid(api) {
    if (!api || typeof api.getGridOption !== "function") {
      return false;
    }
    return api.getGridOption("rowModelType") === "infinite";
  }

  function reloadRulesGridData(gridApi, config, state, done, reloadOptions) {
    if (!gridApi || !config || !state) {
      return;
    }
    var profileKey = state.profileKey || "rules";
    var userDone = done || function () {};
    done = function (total) {
      scheduleGroupedColumnVisibility(
        gridApi,
        gridApi._nsmColumnDefs,
        config,
        profileKey
      );
      userDone(total);
    };
    reloadOptions = reloadOptions || {};
    var groupingOnly = !!reloadOptions.groupingOnly;
    var forceRefresh = isRulesTabRefreshRequested();
    if (forceRefresh) {
      invalidateRulesTabDataCache(state);
    }
    var dataCache = getRulesTabDataCache(state, config);

    if (!groupingOnly) {
      invalidateRulesTabDataCache(state);
    }

    if (isInfiniteRulesGrid(gridApi)) {
      if (typeof state.knownTotalRows !== "number" || state.knownTotalRows <= 0) {
        state.knownTotalRows = config.totalCount || 0;
      }
      if (typeof gridApi.refreshInfiniteCache === "function") {
        gridApi.refreshInfiniteCache();
      }
      updateRowStatsForProfile(
        gridApi,
        state.knownTotalRows,
        state,
        config,
        state.domProfile
      );
      done(state.knownTotalRows);
      return;
    }

    if (
      groupingOnly &&
      !forceRefresh &&
      !state.groupByEnabled &&
      dataCache &&
      dataCache.flatRows &&
      dataCache.flatRows.length
    ) {
      applyRulesTabCacheToGrid(gridApi, config, state, dataCache);
      updateRowStatsForProfile(
        gridApi,
        dataCache.totalCount,
        state,
        config,
        state.domProfile
      );
      done(dataCache.totalCount);
      return;
    }

    if (groupingOnly && !forceRefresh && state.groupByEnabled) {
      cancelProgressiveRulesLoad(state);
      state.initialLoadActive = true;
      updateRulesLoadStatus(state);
      loadAllRulesClientRows(
        gridApi,
        config,
        state,
        function (total) {
          updateRowStatsForProfile(
            gridApi,
            total,
            state,
            config,
            state.domProfile
          );
          done(total);
        },
        { useCached: true }
      );
      return;
    }

    cancelProgressiveRulesLoad(state);
    state.initialLoadActive = true;
    state.userLoadTarget = resolveRulesInitialLoadTarget(config, state);
    updateRulesLoadStatus(state);
    loadRulesClientRows(gridApi, config, state, function (total) {
      updateRowStatsForProfile(gridApi, total, state, config, state.domProfile);
      done(total);
    });
  }

  function createRulesDatasource(config, state) {
    return {
      getRows: function (params) {
        if (!config || !config.gridDataUrl) {
          params.failCallback();
          return;
        }
        var filterModel =
          (params.filterModel && Object.keys(params.filterModel).length
            ? params.filterModel
            : null) ||
          (params.api && typeof params.api.getFilterModel === "function"
            ? params.api.getFilterModel()
            : null);
        if (state && state.gridEl) {
          state.gridEl.classList.add("nsm-ag-grid-loading");
        }
        fetchRulesGridRows(
          config,
          state,
          params.startRow,
          params.endRow,
          filterModel
        )
          .then(function (data) {
            if (state) {
              state.knownTotalRows =
                typeof data.lastRow === "number" ? data.lastRow : params.endRow;
              if (typeof state.onRowsLoaded === "function") {
                state.onRowsLoaded(state.knownTotalRows);
              }
            }
            params.successCallback(data.rowData || [], data.lastRow);
            if (params.api) {
              window.requestAnimationFrame(function () {
                resetRulesRowHeights(
                  params.api,
                  state && state.groupByEnabled
                );
              });
            }
          })
          .catch(function (err) {
            console.error("NSM rules grid: datasource fetch failed", err);
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

  function enabledFilterText(enabled, statusLabels) {
    var onLabel = (statusLabels && statusLabels.on) || "On";
    var offLabel = (statusLabels && statusLabels.off) || "Off";
    if (enabled) {
      return onLabel + " on enabled aktiv ein 1";
    }
    return offLabel + " off disabled inaktiv aus 0";
  }

  var POLICY_AUTOSIZE_SKIP_COL_IDS = {
    _actions: true,
    _group: true,
  };

  function collectRulesAutoSizeColIds(columnDefs, out) {
    (columnDefs || []).forEach(function (col) {
      if (col.children) {
        collectRulesAutoSizeColIds(col.children, out);
        return;
      }
      if (!col.colId || POLICY_AUTOSIZE_SKIP_COL_IDS[col.colId]) {
        return;
      }
      if (col.pinned) {
        return;
      }
      if (col.cellRenderer === "descriptionCell") {
        return;
      }
      out.push(col.colId);
    });
  }

  function autoSizeRulesContentColumns(api, columnDefs, gridEl) {
    if (
      !api ||
      api._nsmAutoSizedColumns ||
      typeof api.autoSizeColumns !== "function"
    ) {
      return;
    }
    if (
      typeof api.getDisplayedRowCount === "function" &&
      api.getDisplayedRowCount() <= 0
    ) {
      return;
    }
    var colIds = [];
    collectRulesAutoSizeColIds(columnDefs, colIds);
    if (!colIds.length) {
      return;
    }
    api.autoSizeColumns({ colIds: colIds, skipHeader: false });
    api._nsmAutoSizedColumns = true;
    scheduleRulesGridWidthFit(api, gridEl);
  }

  function scheduleAutoSizeRulesContentColumns(api, state) {
    if (!api || !state || !state.gridEl) {
      return;
    }
    window.requestAnimationFrame(function () {
      autoSizeRulesContentColumns(api, api._nsmColumnDefs, state.gridEl);
    });
  }

  function fitRulesGridWidth(api, gridEl) {
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

  function scheduleRulesGridWidthFit(api, gridEl) {
    if (!api || !gridEl) {
      return;
    }
    window.requestAnimationFrame(function () {
      fitRulesGridWidth(api, gridEl);
    });
  }

  function applyRulesGroupRowHeights(api) {
    if (!api || typeof api.forEachNode !== "function") {
      return;
    }
    api.forEachNode(function (node) {
      if (
        node &&
        node.data &&
        node.data._rowType === "group" &&
        typeof node.setRowHeight === "function"
      ) {
        node.setRowHeight(computeRulesGroupRowHeight(node.data));
      }
    });
    if (typeof api.onRowHeightChanged === "function") {
      api.onRowHeightChanged();
    }
  }

  function resetRulesRowHeights(api, groupByEnabled) {
    if (!api) {
      return;
    }
    if (typeof api.onRowHeightChanged === "function") {
      api.onRowHeightChanged();
    } else if (typeof api.resetRowHeights === "function") {
      api.resetRowHeights();
    }
    if (groupByEnabled) {
      applyRulesGroupRowHeights(api);
    }
  }

  function initRulebookRulesAgGrid() {
    var profile = NSM_GRID_PROFILES.rules;
    var payload = readJsonScript(profile.payloadScript);
    var config = readJsonScript(profile.configScript) || {};
    primeFilterQueryInput(config);
    var gridEl = document.getElementById(profile.gridId);
    if (!payload || !gridEl) {
      return;
    }
    if (typeof agGrid === "undefined" || typeof agGrid.createGrid !== "function") {
      console.error("NSM rules grid: ag-grid-community script not loaded");
      gridEl.innerHTML =
        '<p class="text-danger p-3 mb-0">AG Grid konnte nicht geladen werden.</p>';
      return;
    }

    var canChange = !!(config.permissions && config.permissions.change);
    var canDelete = !!(config.permissions && config.permissions.delete);
    var statusLabels = config.statusLabels || {};
    var statusOnLabel = statusLabels.on || "On";
    var statusOffLabel = statusLabels.off || "Off";
    var columnDefs = enforceNonMovableColumnDefs(payload.columnDefs || []);
    var useRemoteRows = !!(config.infiniteRowModel && config.gridDataUrl);
    var collapsedGroups = {};
    var expandedGroups = {};
    var datasourceState = {
      gridEl: gridEl,
      domProfile: profile,
      profileKey: "rules",
      knownTotalRows: config.totalCount || 0,
      loadedRowCount: 0,
      loadedBytes: 0,
      groupByEnabled: false,
      collapseAllGroups: false,
      usesExpandedMode: false,
      expandAllGroups: false,
      expandedGroups: expandedGroups,
      collapsedGroups: collapsedGroups,
      progressiveLoadToken: 0,
      progressiveLoadActive: false,
      initialLoadActive: false,
      userLoadTarget: resolveRulesInitialLoadTarget(config, null),
      rulesDataCache: null,
    };
    if (isRulesTabRefreshRequested()) {
      invalidateRulesTabDataCache(datasourceState);
    }
    applyRulesGroupConfig(config, datasourceState);
    var rulesObjectFields = [];
    collectRulesObjectFields(columnDefs, rulesObjectFields);
    applyTextColumnFilters(columnDefs, {
      enableColumnFilters: true,
      enableFloatingFilters: false,
    });
    if (datasourceState.groupByEnabled) {
      columnDefs = prependRulesGroupColumn(columnDefs, config);
    }
    var totalRowCount = useRemoteRows
      ? datasourceState.knownTotalRows
      : (payload.rowData || []).length;

    var objectCellRenderer = createRulesObjectCellRenderer();

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
        '" class="text-body nsm-ag-truncate" title="' +
        escapeHtml(name) +
        '">' +
        escapeHtml(truncateCellText(name)) +
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

    var rulebookLinkCellRenderer = function (params) {
      var wrap = document.createElement("div");
      wrap.className = "nsm-ag-rulebook-cell w-100";
      var url = (params.data && params.data._rulebook_url) || "#";
      var name = params.value == null ? "" : String(params.value);
      wrap.innerHTML =
        '<a href="' +
        escapeHtml(url) +
        '" class="text-body nsm-ag-truncate" title="' +
        escapeHtml(name) +
        '">' +
        escapeHtml(truncateCellText(name)) +
        "</a>";
      return wrap;
    };

    var descriptionCellRenderer = function (params) {
      var wrap = document.createElement("div");
      wrap.className = "nsm-ag-html-cell nsm-ag-description-cell w-100";
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

    var rulesGroupCellRenderer = createRulesGroupCellRenderer(
      config,
      datasourceState
    );

    var cellRenderers = {
      objectCell: objectCellRenderer,
      htmlCell: htmlCellRenderer,
      statusCell: statusCellRenderer,
      nameLinkCell: nameLinkCellRenderer,
      indexLinkCell: indexLinkCellRenderer,
      rulebookLinkCell: rulebookLinkCellRenderer,
      descriptionCell: descriptionCellRenderer,
      actionsCell: actionsCellRenderer,
      rulesGroupCell: rulesGroupCellRenderer,
      emptyCell: function () {
        var span = document.createElement("span");
        span.className = "nsm-ag-group-row-empty";
        span.setAttribute("aria-hidden", "true");
        return span;
      },
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
      rowHeight: RULES_ROW_HEIGHT,
      getRowHeight: createRulesGetRowHeight(rulesObjectFields),
      debounceVerticalScrollbar: true,
      defaultColDef: buildRulesDefaultColDef("rules", datasourceState.groupByEnabled),
      floatingFiltersEnabled: true,
      components: cellRenderers,
      getRowClass: createRulesGetRowClass(rulesObjectFields),
      isRowSelectable: function (params) {
        return !(params.data && params.data._rowType === "group");
      },
      rowSelection: {
        mode: "multiRow",
        checkboxes: function (params) {
          return !(params.data && params.data._rowType === "group");
        },
        headerCheckbox: true,
        enableClickSelection: true,
      },
      suppressCellFocus: true,
      animateRows: false,
      suppressMovableColumns: true,
      suppressDragLeaveHidesColumns: true,
      suppressMoveWhenColumnDragging: true,
      getRowId: function (params) {
        var data = params.data || {};
        if (data._rowType === "group") {
          return String(data.pk);
        }
        return String(data.pk);
      },
      onGridReady: function (params) {
        gridApi = params.api;
        applyInitialFilterModel(params.api, config);
        updateRowStatsForProfile(params.api, totalRowCount, datasourceState, config, profile);
        updateClearFiltersButton(params.api, config);
        updateFilterQueryInput(params.api, config);
        syncBulkSelection();
        scheduleRulesGridWidthFit(params.api, gridEl);
        initColumnVisibilityPersistence(
          params.api,
          columnDefs,
          "rules",
          datasourceState.groupByEnabled,
          config
        );
        if (window.innerWidth <= 1024 && typeof params.api.closeToolPanel === "function") {
          params.api.closeToolPanel();
        }
        if (useRemoteRows) {
          loadRulesClientRows(params.api, config, datasourceState, function (
            total
          ) {
            updateRowStatsForProfile(params.api, total, datasourceState, config, profile);
          });
        }
        enableRulesFloatingFilters(params.api);
        if (params.api._nsmRebindGroupHeaders) {
          scheduleGroupHeaderBind(params.api._nsmRebindGroupHeaders);
        }
      },
      onFirstDataRendered: function (params) {
        applyInitialFilterModel(params.api, config);
        updateClearFiltersButton(params.api, config);
        updateFilterQueryInput(params.api, config);
        autoSizeRulesContentColumns(params.api, columnDefs, gridEl);
        scheduleRulesGridWidthFit(params.api, gridEl);
        resetRulesRowHeights(params.api, datasourceState.groupByEnabled);
        enableRulesFloatingFilters(params.api);
        if (params.api._nsmRebindGroupHeaders) {
          scheduleGroupHeaderBind(params.api._nsmRebindGroupHeaders);
        }
      },
      onColumnResized: function (params) {
        scheduleRulesGridWidthFit(params.api, gridEl);
      },
      onDisplayedColumnsChanged: function (params) {
        scheduleRulesGridWidthFit(params.api, gridEl);
      },
      onToolPanelVisibleChanged: function (params) {
        scheduleRulesGridWidthFit(params.api, gridEl);
      },
      onFilterChanged: function (params) {
        filterQueryEditing = false;
        updateRowStatsForProfile(params.api, totalRowCount, datasourceState, config, profile);
        updateClearFiltersButton(params.api, config);
        updateFilterQueryInput(params.api, config, true);
        resetRulesRowHeights(params.api, datasourceState.groupByEnabled);
        scheduleGroupedFilterReload(params.api, config, datasourceState);
      },
      onSelectionChanged: function () {
        syncBulkSelection();
        if (gridApi) {
          updateRowStatsForProfile(gridApi, totalRowCount, datasourceState, config, profile);
        }
      },
    };

    if (useRemoteRows) {
      gridOptions.rowModelType = "clientSide";
      gridOptions.rowData = [];
    } else {
      gridOptions.rowData = payload.rowData || [];
    }
    Object.assign(gridOptions, RULES_GRID_PERF_OPTIONS);

    datasourceState.onRowsLoaded = function (total, meta) {
      if (gridApi) {
        updateRowStatsForProfile(gridApi, total, datasourceState, config, profile);
      }
    };

    var gridApi;
    try {
      gridApi = agGrid.createGrid(gridEl, gridOptions);
      gridApi._nsmDatasourceState = datasourceState;
      gridApi._nsmDefaultColDefExtra = null;
      ensureBaseColumnDefs(gridApi, columnDefs);
      NSM_GRID_REGISTRY.rules = {
        api: gridApi,
        gridEl: gridEl,
        profile: profile,
      };
    } catch (err) {
      console.error("NSM rules grid: createGrid failed", err);
      gridEl.innerHTML =
        '<p class="text-danger p-3 mb-0">AG Grid Initialisierung fehlgeschlagen (Konsole prüfen).</p>';
      return;
    }

    bindRulesLoadMoreButton(gridApi, config, datasourceState, profile);

    var clearFiltersBtn = document.getElementById("nsm-ag-clear-filters");
    if (clearFiltersBtn) {
      clearFiltersBtn.addEventListener("click", function () {
        clearAllRulesFilters(gridApi, config);
        updateClearFiltersButton(gridApi, config);
        updateFilterQueryInput(gridApi, config);
        updateRowStatsForProfile(gridApi, totalRowCount, datasourceState, config, profile);
      });
    }

    bindFilterQueryCopyButton(gridApi, config);
    bindFilterQueryInput(gridApi, config);
    bindFilterQueryDropTarget(gridApi, config);
    bindCellFilterDrag(gridApi, gridEl, config);

    bindNsmGroupToolbar(gridApi, config, datasourceState, gridEl, "rules", columnDefs);

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
      var selected = gridApi.getSelectedRows().filter(function (row) {
        return row._rowType !== "group";
      });
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

  function normalizeAllRulesGroupableColumnDefs(columnDefs) {
    return (columnDefs || []).map(function (col) {
      if (col.children && col.children.length) {
        return Object.assign({}, col, {
          children: normalizeAllRulesGroupableColumnDefs(col.children),
        });
      }
      if (col.colId !== "rulebook") {
        return col;
      }
      var next = Object.assign({}, col, { suppressMovable: true });
      if (!next.lockPosition) {
        next.lockPosition = "left";
      }
      return next;
    });
  }

  function initAllRulesAgGrid() {
    var profile = NSM_GRID_PROFILES.allRules;
    var payload = readJsonScript(profile.payloadScript);
    var config = readJsonScript(profile.configScript) || {};
    config.useServerFilterQ = true;
    if (config.activeFilterQ && !config.filterQuery) {
      config.filterQuery = config.activeFilterQ;
    }
    primeFilterQueryInput(config);
    var gridEl = document.getElementById(profile.gridId);
    if (!payload || !gridEl) {
      return null;
    }
    if (NSM_GRID_REGISTRY.allRules && NSM_GRID_REGISTRY.allRules.api) {
      return NSM_GRID_REGISTRY.allRules.api;
    }
    if (typeof agGrid === "undefined" || typeof agGrid.createGrid !== "function") {
      console.error("NSM all-rules grid: ag-grid-community script not loaded");
      gridEl.innerHTML =
        '<p class="text-danger p-3 mb-0">AG Grid konnte nicht geladen werden.</p>';
      return null;
    }

    var readOnly = !!config.readOnly;
    var canChange =
      !readOnly && !!(config.permissions && config.permissions.change);
    var canDelete =
      !readOnly && !!(config.permissions && config.permissions.delete);
    var statusLabels = config.statusLabels || {};
    var statusOnLabel = statusLabels.on || "On";
    var statusOffLabel = statusLabels.off || "Off";
    var columnDefs = normalizeAllRulesGroupableColumnDefs(
      enforceNonMovableColumnDefs(payload.columnDefs || []).filter(function (col) {
        if (!readOnly) {
          return true;
        }
        return col.colId !== "_actions";
      })
    );
    var useRemoteRows = !!(config.infiniteRowModel && config.gridDataUrl);
    var collapsedGroups = {};
    var expandedGroups = {};
    var rulesObjectFields = [];
    collectRulesObjectFields(columnDefs, rulesObjectFields);
    applyTextColumnFilters(columnDefs, {
      enableColumnFilters: true,
      enableFloatingFilters: false,
    });
    var datasourceState = {
      gridEl: gridEl,
      domProfile: profile,
      profileKey: "allRules",
      knownTotalRows: config.totalCount || 0,
      loadedRowCount: 0,
      loadedBytes: 0,
      groupByEnabled: false,
      collapseAllGroups: false,
      usesExpandedMode: false,
      expandAllGroups: false,
      expandedGroups: expandedGroups,
      collapsedGroups: collapsedGroups,
      progressiveLoadToken: 0,
      progressiveLoadActive: false,
      initialLoadActive: false,
      userLoadTarget: resolveRulesInitialLoadTarget(config, null),
      rulesDataCache: null,
    };
    if (isRulesTabRefreshRequested()) {
      invalidateRulesTabDataCache(datasourceState);
    }
    applyRulesGroupConfig(config, datasourceState);
    if (datasourceState.groupByEnabled) {
      columnDefs = prependRulesGroupColumn(columnDefs, config);
    }
    var totalRowCount = datasourceState.knownTotalRows;

    var objectCellRenderer = createRulesObjectCellRenderer();

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

    var rulebookLinkCellRenderer = function (params) {
      var wrap = document.createElement("div");
      wrap.className = "nsm-ag-rulebook-cell w-100";
      var url = (params.data && params.data._rulebook_url) || "#";
      var name = params.value == null ? "" : String(params.value);
      wrap.innerHTML =
        '<a href="' +
        escapeHtml(url) +
        '" class="text-body nsm-ag-truncate" title="' +
        escapeHtml(name) +
        '">' +
        escapeHtml(truncateCellText(name)) +
        "</a>";
      return wrap;
    };

    var rulesGroupCellRenderer = createRulesGroupCellRenderer(
      config,
      datasourceState
    );

    var cellRenderers = {
      objectCell: objectCellRenderer,
      statusCell: function (params) {
        var wrap = document.createElement("div");
        wrap.className = "nsm-ag-status-cell";
        wrap.innerHTML = statusCellHtml(!!params.value);
        return wrap;
      },
      rulesGroupCell: rulesGroupCellRenderer,
      emptyCell: function () {
        var span = document.createElement("span");
        span.className = "nsm-ag-group-row-empty";
        span.setAttribute("aria-hidden", "true");
        return span;
      },
      nameLinkCell: function (params) {
        var wrap = document.createElement("div");
        wrap.className = "nsm-ag-name-cell w-100";
        var url = (params.data && params.data._detail_url) || "#";
        var name = params.value == null ? "" : String(params.value);
        wrap.innerHTML =
          '<a href="' +
          escapeHtml(url) +
          '" class="text-body nsm-ag-truncate" title="' +
          escapeHtml(name) +
          '">' +
          escapeHtml(truncateCellText(name)) +
          "</a>";
        return wrap;
      },
      indexLinkCell: function (params) {
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
      },
      descriptionCell: function (params) {
        var wrap = document.createElement("div");
        wrap.className = "nsm-ag-html-cell nsm-ag-description-cell w-100";
        wrap.innerHTML = descriptionCellHtml(params.value);
        return wrap;
      },
      rulebookLinkCell: rulebookLinkCellRenderer,
      actionsCell: function (params) {
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
      },
    };

    var layoutEl = gridEl.closest(".nsm-ag-grid-theme");
    applyNetBoxColorMode(layoutEl);
    var theme = resolveAgGridTheme();
    if (!theme) {
      applyLegacyThemeClass(gridEl, isNetBoxDark());
    }

    var gridApi;
    var gridOptions = {
      theme: theme || "legacy",
      columnDefs: columnDefs,
      rowHeight: RULES_ROW_HEIGHT,
      getRowHeight: createRulesGetRowHeight(rulesObjectFields),
      debounceVerticalScrollbar: true,
      defaultColDef: buildRulesDefaultColDef("allRules", datasourceState.groupByEnabled),
      floatingFiltersEnabled: true,
      components: cellRenderers,
      getRowClass: createRulesGetRowClass(rulesObjectFields),
      isRowSelectable: function (params) {
        return !(params.data && params.data._rowType === "group");
      },
      getRowId: function (params) {
        var data = params.data || {};
        if (data._rowType === "group") {
          return String(data.pk);
        }
        return String(data.pk || "");
      },
      onGridReady: function (params) {
        gridApi = params.api;
        gridApi._nsmDatasourceState = datasourceState;
        updateRowStatsForProfile(params.api, totalRowCount, datasourceState, config, profile);
        updateClearFiltersButton(params.api, config);
        updateFilterQueryInput(params.api, config);
        scheduleRulesGridWidthFit(params.api, gridEl);
        initColumnVisibilityPersistence(
          params.api,
          columnDefs,
          "allRules",
          datasourceState.groupByEnabled,
          config
        );
        if (useRemoteRows) {
          loadRulesClientRows(params.api, config, datasourceState, function (total) {
            updateRowStatsForProfile(params.api, total, datasourceState, config, profile);
          });
        }
        scheduleEnableRulesFloatingFilters(params.api);
        if (params.api._nsmRebindGroupHeaders) {
          scheduleGroupHeaderBind(params.api._nsmRebindGroupHeaders);
        }
      },
      onFirstDataRendered: function (params) {
        updateClearFiltersButton(params.api, config);
        updateFilterQueryInput(params.api, config);
        scheduleRulesGridWidthFit(params.api, gridEl);
        resetRulesRowHeights(params.api, datasourceState.groupByEnabled);
        enableRulesFloatingFilters(params.api);
        if (params.api._nsmRebindGroupHeaders) {
          scheduleGroupHeaderBind(params.api._nsmRebindGroupHeaders);
        }
      },
      onColumnResized: function (params) {
        scheduleRulesGridWidthFit(params.api, gridEl);
      },
      onDisplayedColumnsChanged: function (params) {
        scheduleRulesGridWidthFit(params.api, gridEl);
      },
      onFilterChanged: function (params) {
        filterQueryEditing = false;
        updateRowStatsForProfile(params.api, totalRowCount, datasourceState, config, profile);
        updateClearFiltersButton(params.api, config);
        updateFilterQueryInput(params.api, config, true);
        resetRulesRowHeights(params.api, datasourceState.groupByEnabled);
        scheduleGroupedFilterReload(params.api, config, datasourceState);
      },
      suppressCellFocus: true,
      animateRows: false,
      suppressMovableColumns: true,
      suppressDragLeaveHidesColumns: true,
      suppressMoveWhenColumnDragging: true,
    };

    if (useRemoteRows) {
      gridOptions.rowModelType = "clientSide";
      gridOptions.rowData = [];
    } else {
      gridOptions.rowData = payload.rowData || [];
    }
    Object.assign(gridOptions, RULES_GRID_PERF_OPTIONS);

    datasourceState.onRowsLoaded = function (total) {
      if (gridApi) {
        updateRowStatsForProfile(gridApi, total, datasourceState, config, profile);
      }
    };

    try {
      gridApi = agGrid.createGrid(gridEl, gridOptions);
      gridApi._nsmDatasourceState = datasourceState;
      gridApi._nsmDefaultColDefExtra = null;
      ensureBaseColumnDefs(gridApi, columnDefs);
      NSM_GRID_REGISTRY.allRules = {
        api: gridApi,
        gridEl: gridEl,
        profile: profile,
      };
    } catch (err) {
      console.error("NSM all-rules grid: createGrid failed", err);
      gridEl.innerHTML =
        '<p class="text-danger p-3 mb-0">AG Grid Initialisierung fehlgeschlagen (Konsole prüfen).</p>';
      return null;
    }

    bindRulesLoadMoreButton(gridApi, config, datasourceState, profile);
    bindFilterQueryCopyButton(gridApi, config);
    bindFilterQueryInput(gridApi, config);
    bindFilterQueryDropTarget(gridApi, config);
    bindCellFilterDrag(gridApi, gridEl, config);
    bindNsmGroupToolbar(gridApi, config, datasourceState, gridEl, "allRules", columnDefs);
    return gridApi;
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

  function refreshNsmGridLayout(profileKey) {
    var entry = NSM_GRID_REGISTRY[profileKey];
    if (!entry || !entry.api || !entry.gridEl) {
      return;
    }
    scheduleRulesGridWidthFit(entry.api, entry.gridEl);
    resetRulesRowHeights(entry.api, false);
    if (typeof entry.api.redrawRows === "function") {
      entry.api.redrawRows();
    }
  }

  initRulebookRulesAgGrid();
  if (document.getElementById(NSM_GRID_PROFILES.allRules.gridId)) {
    initAllRulesAgGrid();
  }
})();
