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
  var NSM_GROUP_MAX_MESSAGE_FALLBACK =
    "Maximum of two columns allowed for grouping.";
  var NSM_GROUP_DUPLICATE_MESSAGE_FALLBACK =
    "This column is already in the grouping.";
  var NSM_GROUP_NOT_ALLOWED_FALLBACK =
    "Field is not configured for this rulebook.";
  var NSM_MATRIX_TYPE_MISMATCH_FALLBACK =
    "Both matrix fields must use the same object type (e.g. both zones).";
  var NSM_MATRIX_DUPLICATE_MESSAGE_FALLBACK =
    "This column is already in the matrix.";
  var NSM_MATRIX_ROW_SLOT_LABEL_FALLBACK = "Row";
  var NSM_MATRIX_COL_SLOT_LABEL_FALLBACK = "Column";
  var NSM_GROUP_MAIN_LEVEL_LABEL_FALLBACK = "Main group";
  var NSM_GROUP_SUBGROUP_LEVEL_LABEL_FALLBACK = "Subgroup";
  var NSM_REMOVE_GROUPING_LABEL_FALLBACK = "Remove grouping";
  var NSM_REMOVE_MATRIX_FIELD_LABEL_FALLBACK = "Remove matrix field";
  var NSM_GROUP_DRAG_SOURCE = null;
  var NSM_GROUP_DRAG_VALUE = null;
  var NSM_MATRIX_MAX_SLOTS = 2;
  var NSM_MATRIX_ROW_SLOT = "row";
  var NSM_MATRIX_COL_SLOT = "col";
  var NSM_MATRIX_SESSION_KEY_PREFIX = "nsm-rules-matrix-";
  var NSM_FILTER_VIEW_MATRIX_NOT_READY_FALLBACK =
    "Matrix view needs row and column fields in the Matrix zone (drag two matching object columns).";
  var NSM_VIEW_DIRECTIVE_RE = /^view\s*\(\s*(matrix|group|table)\s*\)\s*$/i;
  var NSM_VIEW_DIRECTIVE_MULTIPLE_ERROR =
    "Only one view() directive allowed; use view(table), view(group), or view(matrix)";
  /** Extensible toolbar view modes (sync with filter query view()). */
  var NSM_TOOLBAR_VIEW_MODES = ["table", "group", "matrix"];
  var NSM_TOOLBAR_VIEW_MODE_DEFAULT = "table";
  var NSM_TABLE_DRAG_DISABLED_FALLBACK =
    "Switch to Group or Matrix view to organize rules by drag-and-drop.";
  var NSM_TOOLBAR_HELP_VISIBLE = false;
  var NSM_MATRIX_CTX = null;
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
    showGroupToolbarMessage(
      groupMaxMessage(
        (NSM_GROUP_NAV_CTX && NSM_GROUP_NAV_CTX.config) ||
          (NSM_MATRIX_CTX && NSM_MATRIX_CTX.config)
      )
    );
    flashGroupDropzoneRejected(dropzone);
  }

  function notifyGroupDuplicate(dropzone) {
    showGroupToolbarMessage(
      groupDuplicateMessage(
        (NSM_GROUP_NAV_CTX && NSM_GROUP_NAV_CTX.config) ||
          (NSM_MATRIX_CTX && NSM_MATRIX_CTX.config)
      )
    );
    flashGroupDropzoneRejected(dropzone);
  }

  function groupMaxMessage(config) {
    if (config && config.groupMaxMessage) {
      return String(config.groupMaxMessage);
    }
    return NSM_GROUP_MAX_MESSAGE_FALLBACK;
  }

  function groupDuplicateMessage(config) {
    if (config && config.groupDuplicateMessage) {
      return String(config.groupDuplicateMessage);
    }
    return NSM_GROUP_DUPLICATE_MESSAGE_FALLBACK;
  }

  function removeGroupingLabel(config) {
    if (config && config.removeGroupingLabel) {
      return String(config.removeGroupingLabel);
    }
    return NSM_REMOVE_GROUPING_LABEL_FALLBACK;
  }

  function removeMatrixFieldLabel(config) {
    if (config && config.removeMatrixFieldLabel) {
      return String(config.removeMatrixFieldLabel);
    }
    return NSM_REMOVE_MATRIX_FIELD_LABEL_FALLBACK;
  }

  function matrixRowSlotLabel(config) {
    if (config && config.matrixRowSlotLabel) {
      return String(config.matrixRowSlotLabel);
    }
    return NSM_MATRIX_ROW_SLOT_LABEL_FALLBACK;
  }

  function matrixColSlotLabel(config) {
    if (config && config.matrixColSlotLabel) {
      return String(config.matrixColSlotLabel);
    }
    return NSM_MATRIX_COL_SLOT_LABEL_FALLBACK;
  }

  function groupLevelRoleLabel(config, level) {
    if (level === 1) {
      if (config && config.groupMainLevelLabel) {
        return String(config.groupMainLevelLabel);
      }
      return NSM_GROUP_MAIN_LEVEL_LABEL_FALLBACK;
    }
    if (level === 2) {
      if (config && config.groupSubgroupLevelLabel) {
        return String(config.groupSubgroupLevelLabel);
      }
      return NSM_GROUP_SUBGROUP_LEVEL_LABEL_FALLBACK;
    }
    return "";
  }

  function matrixSlotRoleLabel(config, slot) {
    if (slot === NSM_MATRIX_ROW_SLOT) {
      return matrixRowSlotLabel(config);
    }
    if (slot === NSM_MATRIX_COL_SLOT) {
      return matrixColSlotLabel(config);
    }
    return "";
  }

  function buildPillLabelWithRole(roleLabel, nameLabel) {
    var label = document.createElement("span");
    label.className = "nsm-ag-group-pill-label";
    if (roleLabel) {
      var role = document.createElement("span");
      role.className = "nsm-ag-group-pill-role";
      role.textContent = roleLabel;
      label.appendChild(role);
    }
    var name = document.createElement("span");
    name.className = "nsm-ag-group-pill-name";
    name.textContent = nameLabel;
    label.appendChild(name);
    return label;
  }

  function resolveMatrixMode(config) {
    var mode = config && config.matrixMode ? String(config.matrixMode) : "directed";
    return mode === "undirected" ? "undirected" : "directed";
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
    if (reason === "view_mode") {
      showGroupToolbarMessage(dropzoneViewModeDisabledMessage(config));
      flashGroupDropzoneRejected(dropzone);
      return;
    }
    showGroupToolbarMessage(groupByNotAllowedMessage(config));
    flashGroupDropzoneRejected(dropzone);
  }

  function resolveGroupDropRejectReason(config, dragSource) {
    if (!isGroupDropzoneEnabled(config)) {
      return "view_mode";
    }
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

  function pointerHitsGroupDropzone(clientX, clientY, config) {
    if (!isGroupDropzoneEnabled(config)) {
      return false;
    }
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

  function pointerHitsMatrixDropzone(clientX, clientY, config) {
    if (!isMatrixDropzoneEnabled(config)) {
      return false;
    }
    var dropzone = document.getElementById("nsm-ag-matrix-dropzone");
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
    if (!isGroupDropzoneEnabled(config)) {
      return;
    }
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
    if (pointerHitsMatrixDropzone(clientX, clientY, session.config)) {
      applyMatrixHeaderDrop(session.config, session.groupValue, clientX, clientY);
    } else if (pointerHitsGroupDropzone(clientX, clientY, session.config)) {
      applyGroupHeaderDrop(session.config, session.groupValue);
    }
    if (session.ghost && session.ghost.parentNode) {
      session.ghost.parentNode.removeChild(session.ghost);
    }
    if (session.cell) {
      session.cell.classList.remove("nsm-ag-group-dragging");
    }
    setGroupHeaderDropzoneState(session.dropzone, false, false, false);
    setMatrixDropzoneState(document.getElementById("nsm-ag-matrix-dropzone"), false, false);
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
    var toolbarMode = resolveToolbarViewMode(config);
    if (toolbarMode === "group") {
      setGroupHeaderDropzoneState(
        dropzone,
        true,
        pointerHitsGroupDropzone(clientX, clientY, config),
        isGroupDropRejected(config, "header")
      );
    } else if (toolbarMode === "matrix") {
      var matrixDropzone = document.getElementById("nsm-ag-matrix-dropzone");
      var levels = readMatrixLevelsFromConfig(config);
      var targetSlot = levels.length ? NSM_MATRIX_COL_SLOT : NSM_MATRIX_ROW_SLOT;
      setMatrixDropzoneState(
        matrixDropzone,
        !isMatrixDropRejected(
          config,
          "header",
          targetSlot,
          levels,
          groupValue
        ),
        isMatrixDropRejected(
          config,
          "header",
          targetSlot,
          levels,
          groupValue
        )
      );
    }
    document.body.classList.add("nsm-ag-group-header-drag-active");

    function onMove(event) {
      if (event.pointerId !== pointerId) {
        return;
      }
      event.preventDefault();
      positionGroupHeaderDragGhost(session.ghost, event.clientX, event.clientY);
      var activeMode = resolveToolbarViewMode(config);
      if (activeMode === "matrix") {
        var overMatrix = pointerHitsMatrixDropzone(event.clientX, event.clientY, config);
        if (overMatrix) {
          var matrixDropzone = document.getElementById("nsm-ag-matrix-dropzone");
          var matrixLevels = readMatrixLevelsFromConfig(config);
          var matrixTargetSlot = matrixLevels.length
            ? NSM_MATRIX_COL_SLOT
            : NSM_MATRIX_ROW_SLOT;
          setGroupHeaderDropzoneState(session.dropzone, false, false, false);
          setMatrixDropzoneState(
            matrixDropzone,
            !isMatrixDropRejected(
              config,
              "header",
              matrixTargetSlot,
              matrixLevels,
              session.groupValue
            ),
            isMatrixDropRejected(
              config,
              "header",
              matrixTargetSlot,
              matrixLevels,
              session.groupValue
            )
          );
        } else {
          setMatrixDropzoneState(
            document.getElementById("nsm-ag-matrix-dropzone"),
            false,
            false
          );
        }
      } else if (activeMode === "group") {
        setMatrixDropzoneState(document.getElementById("nsm-ag-matrix-dropzone"), false, false);
        setGroupHeaderDropzoneState(
          dropzone,
          true,
          pointerHitsGroupDropzone(event.clientX, event.clientY, config),
          isGroupDropRejected(config, "header")
        );
      } else {
        setMatrixDropzoneState(document.getElementById("nsm-ag-matrix-dropzone"), false, false);
        setGroupHeaderDropzoneState(session.dropzone, false, false, false);
      }
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
    var toolbarMode = resolveToolbarViewMode(config);
    if (toolbarMode === "group") {
      setGroupHeaderDropzoneState(
        document.getElementById("nsm-ag-group-dropzone"),
        true,
        false,
        isGroupDropRejected(config, "header")
      );
    } else if (toolbarMode === "matrix") {
      setMatrixDropzoneState(
        document.getElementById("nsm-ag-matrix-dropzone"),
        !isMatrixDropRejected(
          config,
          "header",
          NSM_MATRIX_ROW_SLOT,
          readMatrixLevelsFromConfig(config),
          groupValue
        ),
        isMatrixDropRejected(
          config,
          "header",
          NSM_MATRIX_ROW_SLOT,
          readMatrixLevelsFromConfig(config),
          groupValue
        )
      );
    }
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
    params.delete("matrix_row");
    params.delete("matrix_col");
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
      syncRulesGroupedGridLayout(gridApi, state);
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
    if (levels.length > 0) {
      setToolbarViewMode(config, "group");
      clearMatrixForGrouping(config);
    }
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
        syncRulesGroupedGridLayout(gridApi, state);
        refreshRulesGroupCells(gridApi);
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

    pill.appendChild(
      buildPillLabelWithRole(
        groupLevelRoleLabel(config, level),
        groupOptionLabel(config, spec.value)
      )
    );

    var removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "nsm-ag-group-pill-remove";
    removeBtn.setAttribute("aria-label", removeGroupingLabel(config));
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
    syncGroupToolbarVisibility(config);
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
      if (!isGroupDropzoneEnabled(config)) {
        if (event.dataTransfer) {
          event.dataTransfer.dropEffect = "none";
        }
        dropzone.classList.add("nsm-ag-group-dropzone-rejected");
        dropzone.classList.remove("nsm-ag-group-dropzone-hover");
        return;
      }
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
      if (!isGroupDropzoneEnabled(config)) {
        notifyGroupDropRejected(dropzone, "view_mode", config);
        NSM_GROUP_DRAG_SOURCE = null;
        NSM_GROUP_DRAG_VALUE = null;
        return;
      }
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

  function matrixColumnMeta(config) {
    return (config && config.matrixColumnMeta) || {};
  }

  function matrixNotAllowedMessage(config) {
    if (config && config.matrixNotAllowedMessage) {
      return String(config.matrixNotAllowedMessage);
    }
    return NSM_GROUP_NOT_ALLOWED_FALLBACK;
  }

  function matrixTypeMismatchMessage(config) {
    if (config && config.matrixTypeMismatchMessage) {
      return String(config.matrixTypeMismatchMessage);
    }
    return NSM_MATRIX_TYPE_MISMATCH_FALLBACK;
  }

  function matrixDuplicateMessage(config) {
    if (config && config.matrixDuplicateMessage) {
      return String(config.matrixDuplicateMessage);
    }
    return NSM_MATRIX_DUPLICATE_MESSAGE_FALLBACK;
  }

  function isMatrixCompatibleValue(value, config) {
    value = normalizeGroupValue(value, config) || value;
    if (!value || value.indexOf("col:") !== 0) {
      return false;
    }
    return !!matrixColumnMeta(config)[value];
  }

  function readMatrixLevelsFromConfig(config) {
    var levels = [];
    if (config && config.matrixRow) {
      levels.push({ slot: NSM_MATRIX_ROW_SLOT, value: String(config.matrixRow) });
    }
    if (config && config.matrixCol) {
      levels.push({ slot: NSM_MATRIX_COL_SLOT, value: String(config.matrixCol) });
    }
    return levels;
  }

  function matrixLevelsComplete(levels) {
    return (
      levels &&
      levels.length === NSM_MATRIX_MAX_SLOTS &&
      levels.some(function (item) {
        return item.slot === NSM_MATRIX_ROW_SLOT;
      }) &&
      levels.some(function (item) {
        return item.slot === NSM_MATRIX_COL_SLOT;
      })
    );
  }

  function validateMatrixPair(rowValue, colValue, config) {
    rowValue = normalizeGroupValue(rowValue, config) || rowValue;
    colValue = normalizeGroupValue(colValue, config) || colValue;
    var meta = matrixColumnMeta(config);
    if (!meta[rowValue] || !meta[colValue]) {
      return "field_config";
    }
    if (meta[rowValue].contentTypeId !== meta[colValue].contentTypeId) {
      return "type_mismatch";
    }
    return null;
  }

  function resolveMatrixDropRejectReason(
    config,
    dragSource,
    targetSlot,
    levels,
    dragValue
  ) {
    if (!isMatrixDropzoneEnabled(config)) {
      return "view_mode";
    }
    var value =
      dragValue != null && String(dragValue) !== ""
        ? dragValue
        : NSM_GROUP_DRAG_VALUE;
    value = normalizeGroupValue(value, config) || value;
    if (!value || !isMatrixCompatibleValue(value, config)) {
      return "field_config";
    }
    levels = levels || readMatrixLevelsFromConfig(config);
    if (dragSource !== "matrix-pill") {
      var occupied = levels.some(function (item) {
        return item.value === value;
      });
      if (occupied) {
        return "duplicate";
      }
    }
    if (levels.length >= NSM_MATRIX_MAX_SLOTS && dragSource !== "matrix-pill") {
      var openSlot = !levels.some(function (item) {
        return item.slot === targetSlot;
      });
      if (!openSlot) {
        return "max";
      }
    }
    var nextLevels = matrixLevelsAfterDrop(levels, value, targetSlot, dragSource, config);
    if (matrixLevelsComplete(nextLevels)) {
      var rowVal = nextLevels.filter(function (item) {
        return item.slot === NSM_MATRIX_ROW_SLOT;
      })[0].value;
      var colVal = nextLevels.filter(function (item) {
        return item.slot === NSM_MATRIX_COL_SLOT;
      })[0].value;
      var pairErr = validateMatrixPair(rowVal, colVal, config);
      if (pairErr) {
        return pairErr;
      }
    }
    return null;
  }

  function isMatrixDropRejected(config, dragSource, targetSlot, levels, dragValue) {
    return !!resolveMatrixDropRejectReason(
      config,
      dragSource,
      targetSlot,
      levels,
      dragValue
    );
  }

  function matrixLevelsAfterDrop(levels, value, targetSlot, dragSource, config) {
    value = normalizeGroupValue(value, config) || value;
    var next = levels.slice();
    if (dragSource === "matrix-pill") {
      next = next.filter(function (item) {
        return item.slot !== targetSlot;
      });
    } else {
      next = next.filter(function (item) {
        return item.slot !== targetSlot && item.value !== value;
      });
    }
    next.push({ slot: targetSlot, value: value });
    next.sort(function (a, b) {
      if (a.slot === NSM_MATRIX_ROW_SLOT) {
        return -1;
      }
      if (b.slot === NSM_MATRIX_ROW_SLOT) {
        return 1;
      }
      return 0;
    });
    return next.slice(0, NSM_MATRIX_MAX_SLOTS);
  }

  function inferMatrixTargetSlot(event, levels) {
    var slotEl =
      event && event.target && typeof event.target.closest === "function"
        ? event.target.closest("[data-matrix-slot]")
        : null;
    if (slotEl) {
      return slotEl.getAttribute("data-matrix-slot") || NSM_MATRIX_ROW_SLOT;
    }
    if (!levels.length) {
      return NSM_MATRIX_ROW_SLOT;
    }
    if (levels.length === 1) {
      return levels[0].slot === NSM_MATRIX_ROW_SLOT
        ? NSM_MATRIX_COL_SLOT
        : NSM_MATRIX_ROW_SLOT;
    }
    return NSM_MATRIX_COL_SLOT;
  }

  function inferMatrixTargetSlotFromPoint(clientX, clientY, levels, dropzone) {
    if (typeof document.elementFromPoint === "function") {
      var hit = document.elementFromPoint(clientX, clientY);
      if (hit && dropzone && dropzone.contains(hit)) {
        return inferMatrixTargetSlot({ target: hit }, levels);
      }
    }
    return inferMatrixTargetSlot({ target: dropzone || null }, levels);
  }

  function resolveMatrixToolbarConfig(fallbackConfig) {
    return (
      (NSM_MATRIX_CTX && NSM_MATRIX_CTX.config) ||
      (NSM_GROUP_NAV_CTX && NSM_GROUP_NAV_CTX.config) ||
      fallbackConfig ||
      null
    );
  }

  function setMatrixDropzoneState(dropzone, hover, rejected) {
    if (!dropzone) {
      return;
    }
    dropzone.classList.toggle("nsm-ag-group-dropzone-hover", !!hover && !rejected);
    dropzone.classList.toggle("nsm-ag-group-dropzone-rejected", !!rejected);
    dropzone.classList.toggle(
      "nsm-ag-group-dropzone-active",
      readMatrixLevelsFromConfig(
        NSM_MATRIX_CTX && NSM_MATRIX_CTX.config ? NSM_MATRIX_CTX.config : null
      ).length > 0
    );
  }

  function notifyMatrixDropRejected(dropzone, reason, config) {
    if (reason === "duplicate") {
      showGroupToolbarMessage(matrixDuplicateMessage(config));
      flashGroupDropzoneRejected(dropzone);
      return;
    }
    if (reason === "type_mismatch") {
      showGroupToolbarMessage(matrixTypeMismatchMessage(config));
      flashGroupDropzoneRejected(dropzone);
      return;
    }
    if (reason === "field_config") {
      showGroupToolbarMessage(matrixNotAllowedMessage(config));
      flashGroupDropzoneRejected(dropzone);
      return;
    }
    if (reason === "view_mode") {
      showGroupToolbarMessage(dropzoneViewModeDisabledMessage(config));
      flashGroupDropzoneRejected(dropzone);
      return;
    }
    showGroupToolbarMessage(matrixNotAllowedMessage(config));
    flashGroupDropzoneRejected(dropzone);
  }

  function matrixOptionLabel(config, value) {
    var meta = matrixColumnMeta(config)[value];
    if (meta && meta.label) {
      return meta.label;
    }
    return groupOptionLabel(config, value);
  }

  function buildMatrixPillElement(slot, spec, config) {
    var pill = document.createElement("div");
    pill.className = "nsm-ag-group-pill nsm-ag-matrix-pill";
    pill.draggable = true;
    pill.setAttribute("data-group-value", spec.value);
    pill.setAttribute("data-matrix-slot", slot);

    var grip = document.createElement("span");
    grip.className = "nsm-ag-group-pill-grip mdi mdi-drag";
    grip.setAttribute("aria-hidden", "true");
    pill.appendChild(grip);

    pill.appendChild(
      buildPillLabelWithRole(
        matrixSlotRoleLabel(config, slot),
        matrixOptionLabel(config, spec.value)
      )
    );

    var removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "nsm-ag-group-pill-remove";
    removeBtn.setAttribute("aria-label", removeMatrixFieldLabel(config));
    removeBtn.innerHTML = '<span class="mdi mdi-close" aria-hidden="true"></span>';
    removeBtn.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      var levels = readMatrixLevelsFromConfig(config).filter(function (item) {
        return item.slot !== slot;
      });
      navigateMatrixLevels(levels);
    });
    pill.appendChild(removeBtn);

    pill.addEventListener("dragstart", function (event) {
      event.dataTransfer.setData(NSM_GROUP_DRAG_MIME, spec.value);
      event.dataTransfer.setData("text/plain", spec.value);
      event.dataTransfer.setData("application/x-nsm-matrix-slot", slot);
      event.dataTransfer.effectAllowed = "move";
      NSM_GROUP_DRAG_SOURCE = "matrix-pill";
      NSM_GROUP_DRAG_VALUE = spec.value;
      pill.classList.add("nsm-ag-group-dragging");
    });
    pill.addEventListener("dragend", function () {
      pill.classList.remove("nsm-ag-group-dragging");
      NSM_GROUP_DRAG_SOURCE = null;
      NSM_GROUP_DRAG_VALUE = null;
      setMatrixDropzoneState(document.getElementById("nsm-ag-matrix-dropzone"), false, false);
    });

    return pill;
  }

  function renderMatrixPills(config) {
    var pillsEl = document.getElementById("nsm-ag-matrix-pills");
    var hintEl = document.getElementById("nsm-ag-matrix-dropzone-hint");
    var dropzone = document.getElementById("nsm-ag-matrix-dropzone");
    if (!pillsEl) {
      return;
    }
    var levels = readMatrixLevelsFromConfig(config);
    var bySlot = {};
    levels.forEach(function (item) {
      bySlot[item.slot] = item;
    });
    pillsEl.innerHTML = "";
    [NSM_MATRIX_ROW_SLOT, NSM_MATRIX_COL_SLOT].forEach(function (slot) {
      if (bySlot[slot]) {
        pillsEl.appendChild(buildMatrixPillElement(slot, bySlot[slot], config));
      }
    });
    if (hintEl) {
      hintEl.classList.toggle("d-none", levels.length > 0);
    }
    if (dropzone) {
      dropzone.classList.toggle("nsm-ag-group-dropzone-active", levels.length > 0);
    }
    syncGroupToolbarVisibility(config);
  }

  function matrixLevelValue(levels, slot) {
    var match = (levels || []).filter(function (item) {
      return item.slot === slot;
    })[0];
    return match && match.value != null ? String(match.value) : "";
  }

  function updateConfigFromMatrixLevels(config, levels) {
    if (!config) {
      return;
    }
    delete config.matrixRow;
    delete config.matrixCol;
    delete config.matrixEnabled;
    delete config.matrixContentTypeId;
    delete config.matrixRowLabel;
    delete config.matrixColLabel;
    levels = levels || [];
    var meta = matrixColumnMeta(config);
    var rowValue = matrixLevelValue(levels, NSM_MATRIX_ROW_SLOT);
    var colValue = matrixLevelValue(levels, NSM_MATRIX_COL_SLOT);
    if (rowValue) {
      config.matrixRow = rowValue;
      if (meta[rowValue]) {
        config.matrixRowLabel = meta[rowValue].label;
      }
    }
    if (colValue) {
      config.matrixCol = colValue;
      if (meta[colValue]) {
        config.matrixColLabel = meta[colValue].label;
      }
    }
    if (!matrixLevelsComplete(levels)) {
      return;
    }
    config.matrixEnabled = true;
    config.matrixContentTypeId = meta[rowValue].contentTypeId;
  }

  function buildMatrixUrlParams(levels, config) {
    var params = new URLSearchParams(window.location.search);
    params.delete("matrix_row");
    params.delete("matrix_col");
    params.delete("obj_type");
    levels = levels || [];
    var rowValue = matrixLevelValue(levels, NSM_MATRIX_ROW_SLOT);
    var colValue = matrixLevelValue(levels, NSM_MATRIX_COL_SLOT);
    if (rowValue) {
      params.set("matrix_row", rowValue);
    }
    if (colValue) {
      params.set("matrix_col", colValue);
    }
    if (!matrixLevelsComplete(levels)) {
      params.delete("mode");
      return params;
    }
    var cfg = config || (NSM_MATRIX_CTX && NSM_MATRIX_CTX.config);
    if (cfg && cfg.matrixContentTypeId) {
      params.set("obj_type", String(cfg.matrixContentTypeId));
    }
    if (cfg && cfg.matrixMode) {
      params.set("mode", resolveMatrixMode(cfg));
    }
    return params;
  }

  function syncMatrixUrl(params, usePushState) {
    syncGroupingUrl(params, usePushState);
  }

  function persistMatrixSession(config) {
    if (!config || !config.rulebookId || typeof window.sessionStorage === "undefined") {
      return;
    }
    var key = NSM_MATRIX_SESSION_KEY_PREFIX + String(config.rulebookId);
    if (!config.matrixRow && !config.matrixCol) {
      window.sessionStorage.removeItem(key);
      return;
    }
    window.sessionStorage.setItem(
      key,
      JSON.stringify({
        matrixRow: config.matrixRow || null,
        matrixCol: config.matrixCol || null,
        draft: !config.matrixEnabled,
      })
    );
  }

  function restoreMatrixSession(config) {
    if (
      config.matrixEnabled ||
      !config.rulebookId ||
      typeof window.sessionStorage === "undefined" ||
      readGroupLevelsFromConfig(config).length > 0 ||
      (config.groupBy && config.groupByEnabled !== false)
    ) {
      return;
    }
    var raw = window.sessionStorage.getItem(
      NSM_MATRIX_SESSION_KEY_PREFIX + String(config.rulebookId)
    );
    if (!raw) {
      return;
    }
    try {
      var data = JSON.parse(raw);
      if (!data || (!data.matrixRow && !data.matrixCol)) {
        return;
      }
      var rowValue = data.matrixRow ? String(data.matrixRow) : "";
      var colValue = data.matrixCol ? String(data.matrixCol) : "";
      if (rowValue && !isMatrixCompatibleValue(rowValue, config)) {
        return;
      }
      if (colValue && !isMatrixCompatibleValue(colValue, config)) {
        return;
      }
      if (rowValue && colValue && validateMatrixPair(rowValue, colValue, config)) {
        return;
      }
      var meta = matrixColumnMeta(config);
      if (rowValue) {
        config.matrixRow = rowValue;
        if (meta[rowValue]) {
          config.matrixRowLabel = meta[rowValue].label;
        }
      }
      if (colValue) {
        config.matrixCol = colValue;
        if (meta[colValue]) {
          config.matrixColLabel = meta[colValue].label;
        }
      }
      if (rowValue && colValue && !validateMatrixPair(rowValue, colValue, config)) {
        config.matrixEnabled = true;
        config.matrixContentTypeId = meta[rowValue].contentTypeId;
      }
    } catch (sessionErr) {
      /* ignore */
    }
  }

  function clearGroupingForMatrix(config, ctx) {
    if (!config || !config.groupBy) {
      return;
    }
    updateConfigFromGroupLevels(config, []);
    if (ctx && ctx.state) {
      ctx.state.groupByEnabled = false;
      resetGroupExpansionForNewGrouping(ctx.state);
    }
    renderGroupPills(config);
    syncGroupToolbarVisibility(config);
    if (ctx && ctx.gridApi && ctx.state) {
      syncRulesGroupColumnDefs(
        ctx.gridApi,
        config,
        ctx.state,
        ctx.profileKey || "rules"
      );
    }
  }

  function clearMatrixForGrouping(config) {
    if (!config || !config.matrixEnabled) {
      return;
    }
    updateConfigFromMatrixLevels(config, []);
    renderMatrixPills(config);
    exitMatrixMode(config);
    persistMatrixSession(config);
  }

  function setRulesViewMode(matrixActive) {
    var layout = document.querySelector(".nsm-ag-grid-layout");
    if (layout) {
      layout.classList.toggle("nsm-ag-view-mode-matrix", !!matrixActive);
    }
  }

  function buildEmbeddedMatrixConfig(config) {
    return {
      gridDataUrl: config.matrixGridUrl,
      infiniteRowModel: true,
      cacheBlockSize: 50,
      totalRows: 0,
      objType: config.matrixContentTypeId,
      matrixMode: resolveMatrixMode(config),
    };
  }

  function removeLegacyMatrixGridModeChrome() {
    var legacy = document.getElementById("nsm-matrix-grid-mode-wrap");
    if (legacy) {
      legacy.remove();
    }
  }

  function applyMatrixModeChange(config, nextMode) {
    if (!config) {
      return Promise.resolve();
    }
    config.matrixMode = nextMode === "undirected" ? "undirected" : "directed";
    var params = buildMatrixUrlParams(readMatrixLevelsFromConfig(config), config);
    params.set("mode", config.matrixMode);
    syncMatrixUrl(params, true);
    if (!config.matrixEnabled) {
      return Promise.resolve();
    }
    return enterMatrixMode(config);
  }

  function fetchMatrixScaffold(config) {
    if (!config || !config.matrixGridUrl || !config.matrixContentTypeId) {
      return Promise.reject(new Error("matrix scaffold url missing"));
    }
    var params = new URLSearchParams(window.location.search);
    params.set("scaffold", "1");
    params.set("obj_type", String(config.matrixContentTypeId));
    var url = config.matrixGridUrl + "?" + params.toString();
    return fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    }).then(function (response) {
      if (!response.ok) {
        throw new Error("matrix scaffold fetch failed");
      }
      return response.json();
    });
  }

  function destroyEmbeddedMatrix() {
    if (NSM_MATRIX_CTX && NSM_MATRIX_CTX.matrixHandle) {
      NSM_MATRIX_CTX.matrixHandle.destroy();
      NSM_MATRIX_CTX.matrixHandle = null;
    }
  }

  function enterMatrixMode(config) {
    if (!config || !config.matrixEnabled) {
      exitMatrixMode(config);
      return Promise.resolve();
    }
    if (
      !window.NSM_MATRIX_AG ||
      typeof window.NSM_MATRIX_AG.createEmbeddedMatrixAgGrid !== "function"
    ) {
      console.error("NSM rules grid: matrix module missing");
      return Promise.resolve();
    }
    var gridEl = document.getElementById("nsm-rules-matrix-ag-grid");
    if (!gridEl) {
      return Promise.resolve();
    }
    destroyEmbeddedMatrix();
    removeLegacyMatrixGridModeChrome();
    setRulesViewMode(true);
    return fetchMatrixScaffold(config)
      .then(function (payload) {
        var matrixConfig = buildEmbeddedMatrixConfig(config);
        matrixConfig.totalRows =
          (payload.gridMeta && payload.gridMeta.totalRows) || 0;
        var handle = window.NSM_MATRIX_AG.createEmbeddedMatrixAgGrid(
          gridEl,
          payload,
          matrixConfig
        );
        if (NSM_MATRIX_CTX) {
          NSM_MATRIX_CTX.matrixHandle = handle;
          NSM_MATRIX_CTX.matrixConfig = matrixConfig;
        }
        syncGroupToolbarVisibility(config);
      })
      .catch(function (err) {
        console.error("NSM rules grid: matrix mode failed", err);
        setRulesViewMode(false);
      });
  }

  function exitMatrixMode(config) {
    destroyEmbeddedMatrix();
    setRulesViewMode(false);
    if (config) {
      delete config.matrixEnabled;
    }
  }

  function applyRulesMatrixLevels(levels, ctx) {
    if (!ctx || !ctx.config) {
      return false;
    }
    var config = ctx.config;
    levels = (levels || []).slice(0, NSM_MATRIX_MAX_SLOTS);
    var normalized = [];
    levels.forEach(function (spec) {
      var value = spec && spec.value != null ? String(spec.value) : "";
      var canonical = normalizeGroupValue(value, config) || value;
      if (!isMatrixCompatibleValue(canonical, config)) {
        return;
      }
      normalized.push({
        slot: spec.slot === NSM_MATRIX_COL_SLOT ? NSM_MATRIX_COL_SLOT : NSM_MATRIX_ROW_SLOT,
        value: canonical,
      });
    });
    if (matrixLevelsComplete(normalized)) {
      var err = validateMatrixPair(
        normalized.filter(function (item) {
          return item.slot === NSM_MATRIX_ROW_SLOT;
        })[0].value,
        normalized.filter(function (item) {
          return item.slot === NSM_MATRIX_COL_SLOT;
        })[0].value,
        config
      );
      if (err) {
        notifyMatrixDropRejected(
          document.getElementById("nsm-ag-matrix-dropzone"),
          err,
          config
        );
        return false;
      }
    }
    clearGroupingForMatrix(config, ctx);
    if (normalized.length > 0) {
      setToolbarViewMode(config, "matrix");
    }
    updateConfigFromMatrixLevels(config, normalized);
    renderMatrixPills(config);
    persistMatrixSession(config);
    if (matrixLevelsComplete(normalized)) {
      syncMatrixUrl(buildMatrixUrlParams(normalized, config), true);
      return enterMatrixMode(config).then(function () {
        return true;
      });
    }
    exitMatrixMode(config);
    var params = buildMatrixUrlParams(normalized, config);
    params.delete("obj_type");
    syncMatrixUrl(params, true);
    return Promise.resolve(true);
  }

  function navigateMatrixLevels(levels) {
    applyRulesMatrixLevels(levels, NSM_MATRIX_CTX).then(function (applied) {
      if (applied) {
        return;
      }
      var params = buildMatrixUrlParams(levels);
      window.location.search = params.toString();
    });
  }

  function applyMatrixHeaderDrop(config, groupValue, clientX, clientY) {
    if (!isMatrixDropzoneEnabled(config)) {
      return false;
    }
    var dropzone = document.getElementById("nsm-ag-matrix-dropzone");
    if (!pointerHitsMatrixDropzone(clientX, clientY, config)) {
      return false;
    }
    config = resolveMatrixToolbarConfig(config);
    if (!config) {
      return false;
    }
    groupValue = normalizeGroupValue(groupValue, config) || groupValue;
    var levels = readMatrixLevelsFromConfig(config);
    var targetSlot = inferMatrixTargetSlotFromPoint(
      clientX,
      clientY,
      levels,
      dropzone
    );
    var rejectReason = resolveMatrixDropRejectReason(
      config,
      NSM_GROUP_DRAG_SOURCE || "header",
      targetSlot,
      levels,
      groupValue
    );
    if (rejectReason) {
      notifyMatrixDropRejected(dropzone, rejectReason, config);
      return true;
    }
    var next = matrixLevelsAfterDrop(
      levels,
      groupValue,
      targetSlot,
      NSM_GROUP_DRAG_SOURCE || "header",
      config
    );
    navigateMatrixLevels(next);
    return true;
  }

  function bindMatrixDropZone(config) {
    var dropzone = document.getElementById("nsm-ag-matrix-dropzone");
    if (!dropzone || dropzone.dataset.nsmMatrixDropBound === "1") {
      return;
    }
    dropzone.dataset.nsmMatrixDropBound = "1";

    function activeMatrixConfig() {
      return resolveMatrixToolbarConfig(config);
    }

    dropzone.addEventListener(
      "dragover",
      function (event) {
        event.preventDefault();
        event.stopPropagation();
        var activeConfig = activeMatrixConfig();
        if (!activeConfig || !isMatrixDropzoneEnabled(activeConfig)) {
          if (event.dataTransfer) {
            event.dataTransfer.dropEffect = "none";
          }
          setMatrixDropzoneState(dropzone, false, true);
          return;
        }
        var levels = readMatrixLevelsFromConfig(activeConfig);
        var targetSlot = inferMatrixTargetSlot(event, levels);
        var dragValue = readDraggedGroupValue(event) || NSM_GROUP_DRAG_VALUE;
        var rejected = isMatrixDropRejected(
          activeConfig,
          NSM_GROUP_DRAG_SOURCE,
          targetSlot,
          levels,
          dragValue
        );
        if (event.dataTransfer) {
          event.dataTransfer.dropEffect = rejected ? "none" : "copy";
        }
        setMatrixDropzoneState(dropzone, !rejected, rejected);
      },
      true
    );
    dropzone.addEventListener("dragleave", function (event) {
      if (event.target === dropzone || !dropzone.contains(event.relatedTarget)) {
        setMatrixDropzoneState(dropzone, false, false);
      }
    });
    dropzone.addEventListener(
      "drop",
      function (event) {
        event.preventDefault();
        event.stopPropagation();
        setMatrixDropzoneState(dropzone, false, false);
        var activeConfig = activeMatrixConfig();
        if (!activeConfig || !isMatrixDropzoneEnabled(activeConfig)) {
          if (activeConfig) {
            notifyMatrixDropRejected(dropzone, "view_mode", activeConfig);
          }
          NSM_GROUP_DRAG_SOURCE = null;
          NSM_GROUP_DRAG_VALUE = null;
          return;
        }
        var value = readDraggedGroupValue(event);
        value = normalizeGroupValue(value, activeConfig) || value;
        var levels = readMatrixLevelsFromConfig(activeConfig);
        var pillSlotRaw = event.dataTransfer.getData("application/x-nsm-matrix-slot");
        var targetSlot = pillSlotRaw || inferMatrixTargetSlot(event, levels);
        var rejectReason = resolveMatrixDropRejectReason(
          activeConfig,
          NSM_GROUP_DRAG_SOURCE,
          targetSlot,
          levels,
          value
        );
        if (rejectReason) {
          notifyMatrixDropRejected(dropzone, rejectReason, activeConfig);
          NSM_GROUP_DRAG_SOURCE = null;
          NSM_GROUP_DRAG_VALUE = null;
          return;
        }
        var next = matrixLevelsAfterDrop(
          levels,
          value,
          targetSlot,
          NSM_GROUP_DRAG_SOURCE,
          activeConfig
        );
        navigateMatrixLevels(next);
        NSM_GROUP_DRAG_SOURCE = null;
        NSM_GROUP_DRAG_VALUE = null;
      },
      true
    );
  }

  function bindCsvExportButton(config, ctx) {
    var btn = document.getElementById("nsm-ag-csv-export");
    if (!btn || btn.dataset.nsmCsvExportBound === "1") {
      return;
    }
    btn.dataset.nsmCsvExportBound = "1";
    btn.addEventListener("click", function () {
      exportRulesGridCsv(config, ctx);
    });
  }

  function buildCsvFilename(config, suffix) {
    var name = (config && config.rulebookName) || "rules";
    name = String(name)
      .trim()
      .replace(/[^\w\-]+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_|_$/g, "");
    var stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    return (name || "rules") + "_" + (suffix || "export") + "_" + stamp + ".csv";
  }

  function exportRulesGridCsv(config, ctx) {
    if (config && config.matrixEnabled && NSM_MATRIX_CTX && NSM_MATRIX_CTX.matrixHandle) {
      var matrixCfg = NSM_MATRIX_CTX.matrixConfig || buildEmbeddedMatrixConfig(config);
      var matrixState = NSM_MATRIX_CTX.matrixHandle.state;
      if (window.NSM_MATRIX_AG && window.NSM_MATRIX_AG.exportMatrixCsv) {
        window.NSM_MATRIX_AG.exportMatrixCsv(
          matrixCfg,
          matrixState,
          buildCsvFilename(config, "matrix")
        );
      }
      return;
    }
    if (!ctx || !ctx.gridApi) {
      return;
    }
    var csv = buildRulesGridCsv(ctx.gridApi, ctx.config);
    if (window.NSM_MATRIX_AG && window.NSM_MATRIX_AG.downloadCsvBlob) {
      window.NSM_MATRIX_AG.downloadCsvBlob(csv, buildCsvFilename(config, "rules"));
    }
  }

  function rulesGridColumnField(col) {
    var def = typeof col.getColDef === "function" ? col.getColDef() : {};
    return def.field || col.getColId();
  }

  function stripRulesGridHtmlText(value) {
    var text = value == null ? "" : String(value);
    if (!/<[a-z][\s\S]*>/i.test(text)) {
      return text;
    }
    var tmp = document.createElement("div");
    tmp.innerHTML = text;
    return (tmp.textContent || tmp.innerText || "").trim();
  }

  function rulesGridCellCsvValue(data, col, config) {
    if (!data || !col) {
      return "";
    }
    var colId = typeof col.getColId === "function" ? col.getColId() : "";
    var field = rulesGridColumnField(col);
    var filterKey = field + "__filter";
    if (data[filterKey] != null && String(data[filterKey]).trim()) {
      return String(data[filterKey]);
    }
    var val = data[field];
    if (val == null && field !== colId) {
      val = data[colId];
    }
    if (val == null) {
      return "";
    }
    if (typeof val === "boolean" && colId === "status") {
      var labels = (config && config.statusLabels) || {};
      return val ? labels.on || "On" : labels.off || "Off";
    }
    if (typeof val === "object") {
      return "";
    }
    var text = stripRulesGridHtmlText(val);
    if (!text || text === "-") {
      return "";
    }
    return text;
  }

  function buildRulesGridCsv(gridApi, config) {
    var columns = [];
    if (typeof gridApi.getAllDisplayedColumns === "function") {
      columns = gridApi.getAllDisplayedColumns() || [];
    }
    columns = columns.filter(function (col) {
      var colId = typeof col.getColId === "function" ? col.getColId() : "";
      return colId && colId !== "_actions" && colId !== POLICY_GROUP_COL_ID;
    });
    var headers = columns.map(function (col) {
      var def = typeof col.getColDef === "function" ? col.getColDef() : {};
      return def.headerName || col.getColId();
    });
    var escapeFn =
      window.NSM_MATRIX_AG && window.NSM_MATRIX_AG.csvEscapeField
        ? window.NSM_MATRIX_AG.csvEscapeField
        : function (value) {
            return String(value == null ? "" : value);
          };
    var lines = [headers.map(escapeFn).join(",")];
    if (typeof gridApi.forEachNodeAfterFilterAndSort === "function") {
      gridApi.forEachNodeAfterFilterAndSort(function (node) {
        if (!node || !node.data || node.data._rowType === "group") {
          return;
        }
        var row = columns.map(function (col) {
          return rulesGridCellCsvValue(node.data, col, config);
        });
        lines.push(row.map(escapeFn).join(","));
      });
    }
    return lines.join("\n");
  }

  function normalizeToolbarViewMode(mode) {
    var normalized = String(mode || "").toLowerCase();
    return NSM_TOOLBAR_VIEW_MODES.indexOf(normalized) >= 0
      ? normalized
      : NSM_TOOLBAR_VIEW_MODE_DEFAULT;
  }

  function setToolbarViewMode(config, mode) {
    if (!config) {
      return;
    }
    mode = normalizeToolbarViewMode(mode);
    config.toolbarViewMode = mode;
    config.activeFilterView = mode === "table" ? null : mode;
  }

  function resolveToolbarViewMode(config) {
    if (!config) {
      return NSM_TOOLBAR_VIEW_MODE_DEFAULT;
    }
    if (config.toolbarViewMode) {
      return normalizeToolbarViewMode(config.toolbarViewMode);
    }
    if (config.activeFilterView) {
      return normalizeToolbarViewMode(config.activeFilterView);
    }
    if (readGroupLevelsFromConfig(config).length > 0 || config.groupBy) {
      return "group";
    }
    if (config.matrixEnabled || readMatrixLevelsFromConfig(config).length > 0) {
      return "matrix";
    }
    return NSM_TOOLBAR_VIEW_MODE_DEFAULT;
  }

  function resolveToolbarConfigForDropzones(fallbackConfig) {
    return (
      (NSM_GROUP_NAV_CTX && NSM_GROUP_NAV_CTX.config) ||
      (NSM_MATRIX_CTX && NSM_MATRIX_CTX.config) ||
      fallbackConfig ||
      null
    );
  }

  function isGroupDropzoneEnabled(config) {
    config = resolveToolbarConfigForDropzones(config);
    return !!(config && resolveToolbarViewMode(config) === "group");
  }

  function isMatrixDropzoneEnabled(config) {
    config = resolveToolbarConfigForDropzones(config);
    return !!(config && resolveToolbarViewMode(config) === "matrix");
  }

  function tableDragDisabledMessage(config) {
    if (config && config.tableDragDisabledMessage) {
      return String(config.tableDragDisabledMessage);
    }
    return NSM_TABLE_DRAG_DISABLED_FALLBACK;
  }

  function dropzoneViewModeDisabledMessage(config) {
    return tableDragDisabledMessage(resolveToolbarConfigForDropzones(config));
  }

  function syncDropzoneEnabledState(config) {
    if (!config) {
      return;
    }
    var toolbarMode = resolveToolbarViewMode(config);
    var groupDropzone = document.getElementById("nsm-ag-group-dropzone");
    var matrixDropzone = document.getElementById("nsm-ag-matrix-dropzone");
    var groupEnabled = toolbarMode === "group";
    var matrixEnabled = toolbarMode === "matrix";
    if (groupDropzone) {
      groupDropzone.classList.toggle("nsm-ag-dropzone-disabled", !groupEnabled);
      groupDropzone.setAttribute("aria-disabled", groupEnabled ? "false" : "true");
      if (!groupEnabled) {
        setGroupHeaderDropzoneState(groupDropzone, false, false, false);
      }
    }
    if (matrixDropzone) {
      matrixDropzone.classList.toggle("nsm-ag-dropzone-disabled", !matrixEnabled);
      matrixDropzone.setAttribute("aria-disabled", matrixEnabled ? "false" : "true");
      if (!matrixEnabled) {
        setMatrixDropzoneState(matrixDropzone, false, false);
      }
    }
  }

  function syncToolbarViewModeSelector(config) {
    var mode = resolveToolbarViewMode(config);
    var selector = document.getElementById("nsm-ag-view-mode-selector");
    if (selector) {
      selector.querySelectorAll(".nsm-ag-view-mode-btn").forEach(function (btn) {
        var active = btn.getAttribute("data-view-mode") === mode;
        btn.classList.toggle("is-active", active);
        btn.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }
    NSM_TOOLBAR_VIEW_MODES.forEach(function (panelMode) {
      var panel = document.getElementById("nsm-ag-mode-panel-" + panelMode);
      if (panel) {
        panel.classList.toggle("d-none", panelMode !== mode);
      }
    });
    return mode;
  }

  function syncFilterQueryViewDirective(config, ctx) {
    if (!config) {
      return;
    }
    var mode = resolveToolbarViewMode(config);
    var currentQuery = resolveFilterQueryText(ctx && ctx.gridApi, config);
    var parsed = parseViewDirective(currentQuery);
    var nextQuery = appendViewDirective(parsed.body, mode === "table" ? null : mode);
    config.filterQuery = nextQuery;
    if (config.useServerFilterQ) {
      config.activeFilterQ = nextQuery;
      if (hasActiveFilterQuery(config)) {
        syncAllRulesFilterToUrl(config);
      } else {
        stripFilterQueryFromUrl(config);
      }
    } else if (nextQuery) {
      syncRulesFilterQueryToUrl(config, nextQuery);
    } else if (hasActiveFilterQuery(config)) {
      stripFilterQueryFromUrl(config);
    }
    if (ctx && ctx.gridApi) {
      updateFilterQueryInput(ctx.gridApi, config, true);
    }
  }

  function applyToolbarViewMode(mode, config, ctx) {
    ctx = ctx || NSM_GROUP_NAV_CTX || NSM_MATRIX_CTX;
    if (!config) {
      return Promise.resolve(false);
    }
    mode = normalizeToolbarViewMode(mode);
    setToolbarViewMode(config, mode);

    if (mode === "table") {
      return applyFilterViewDirective("table", config, ctx, {}).then(function (applied) {
        syncToolbarViewModeSelector(config);
        syncFilterQueryViewDirective(config, ctx);
        syncGroupToolbarVisibility(config);
        return applied;
      });
    }

    if (mode === "group") {
      clearMatrixForGrouping(config);
      var levels = readGroupLevelsFromConfig(config);
      if (levels.length && ctx && ctx.gridApi) {
        applyRulesGroupingLevels(levels, ctx);
      } else if (ctx && ctx.gridApi && ctx.state) {
        updateConfigFromGroupLevels(config, []);
        ctx.state.groupByEnabled = false;
        syncRulesGroupColumnDefs(
          ctx.gridApi,
          config,
          ctx.state,
          ctx.profileKey || "rules"
        );
        renderGroupPills(config);
      }
      syncToolbarViewModeSelector(config);
      syncGroupToolbarVisibility(config);
      syncFilterQueryViewDirective(config, ctx);
      return Promise.resolve(true);
    }

    if (mode === "matrix") {
      if (ctx && ctx.gridApi) {
        clearGroupingForMatrix(config, ctx);
      }
      var matrixLevels = readMatrixLevelsFromConfig(config);
      if (matrixLevelsComplete(matrixLevels)) {
        return applyRulesMatrixLevels(matrixLevels, ctx || NSM_MATRIX_CTX).then(
          function (applied) {
            syncToolbarViewModeSelector(config);
            syncGroupToolbarVisibility(config);
            syncFilterQueryViewDirective(config, ctx);
            return applied;
          }
        );
      }
      exitMatrixMode(config);
      syncToolbarViewModeSelector(config);
      syncGroupToolbarVisibility(config);
      syncFilterQueryViewDirective(config, ctx);
      return Promise.resolve(true);
    }

    return Promise.resolve(true);
  }

  function bindToolbarViewModeSelector(config, ctx) {
    var selector = document.getElementById("nsm-ag-view-mode-selector");
    if (!selector || selector.dataset.nsmViewModeBound === "1") {
      return;
    }
    selector.dataset.nsmViewModeBound = "1";
    selector.querySelectorAll(".nsm-ag-view-mode-btn").forEach(function (btn) {
      btn.addEventListener("click", function (event) {
        event.preventDefault();
        var nextMode = btn.getAttribute("data-view-mode");
        if (!nextMode || nextMode === resolveToolbarViewMode(config)) {
          return;
        }
        applyToolbarViewMode(nextMode, config, ctx);
      });
    });
  }

  function toolbarFeaturesInUse(config) {
    var groupLevels = readGroupLevelsFromConfig(config);
    var matrixLevels = readMatrixLevelsFromConfig(config);
    return (
      groupLevels.length > 0 ||
      matrixLevels.length > 0 ||
      !!(config && config.matrixEnabled)
    );
  }

  function syncToolbarHelpVisibility(config) {
    var banner = document.getElementById("nsm-ag-toolbar-help");
    var toggleBtn = document.getElementById("nsm-ag-toolbar-help-toggle");
    if (!banner) {
      return;
    }
    if (toolbarFeaturesInUse(config)) {
      NSM_TOOLBAR_HELP_VISIBLE = false;
    }
    var show = NSM_TOOLBAR_HELP_VISIBLE && !toolbarFeaturesInUse(config);
    banner.classList.toggle("d-none", !show);
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", show ? "true" : "false");
      toggleBtn.classList.toggle("is-active", show);
      var showLabel = "Show rules view toolbar help";
      var hideLabel = "Hide rules view toolbar help";
      var label = show ? hideLabel : showLabel;
      toggleBtn.setAttribute("title", label);
      toggleBtn.setAttribute("aria-label", label);
    }
  }

  function updateMatrixModeToolbarActiveState(config) {
    var mode = resolveMatrixMode(config);
    document
      .querySelectorAll("#nsm-ag-matrix-mode-wrap .nsm-ag-matrix-mode-btn")
      .forEach(function (btn) {
        var active = btn.getAttribute("data-mode") === mode;
        btn.classList.toggle("is-active", active);
        btn.setAttribute("aria-pressed", active ? "true" : "false");
      });
  }

  function groupActionRailControlVisible(config, toolbarMode) {
    return (
      toolbarMode === "group" && readGroupLevelsFromConfig(config).length > 0
    );
  }

  function matrixActionRailControlVisible(config, toolbarMode) {
    return toolbarMode === "matrix" && !!(config && config.matrixEnabled);
  }

  function syncMatrixModeToolbarVisibility(config, toolbarMode) {
    var wrap = document.getElementById("nsm-ag-matrix-mode-wrap");
    if (!wrap) {
      return;
    }
    toolbarMode = toolbarMode || resolveToolbarViewMode(config);
    var showInActionRail = matrixActionRailControlVisible(config, toolbarMode);
    wrap.classList.toggle("d-none", !showInActionRail);
    if (showInActionRail) {
      updateMatrixModeToolbarActiveState(config);
    }
  }

  function syncToolbarActionRailVisibility(config, toolbarMode) {
    var rail = document.getElementById("nsm-ag-toolbar-action-rail");
    if (!rail) {
      return;
    }
    toolbarMode = toolbarMode || resolveToolbarViewMode(config);
    var showRail =
      groupActionRailControlVisible(config, toolbarMode) ||
      matrixActionRailControlVisible(config, toolbarMode);
    rail.classList.toggle("d-none", !showRail);
  }

  function syncGroupToolbarVisibility(config) {
    var toolbarMode = syncToolbarViewModeSelector(config);
    var expandWrap = document.getElementById("nsm-ag-group-expand-wrap");
    var showExpand = groupActionRailControlVisible(config, toolbarMode);
    if (expandWrap) {
      expandWrap.classList.toggle("d-none", !showExpand);
    }
    syncDropzoneEnabledState(config);
    syncMatrixModeToolbarVisibility(config, toolbarMode);
    syncToolbarActionRailVisibility(config, toolbarMode);
    syncToolbarHelpVisibility(config);
  }

  function bindToolbarHelpToggle(config) {
    var toggleBtn = document.getElementById("nsm-ag-toolbar-help-toggle");
    if (!toggleBtn || toggleBtn.dataset.nsmToolbarHelpToggleBound === "1") {
      return;
    }
    toggleBtn.dataset.nsmToolbarHelpToggleBound = "1";
    toggleBtn.addEventListener("click", function (event) {
      event.preventDefault();
      NSM_TOOLBAR_HELP_VISIBLE = !NSM_TOOLBAR_HELP_VISIBLE;
      syncToolbarHelpVisibility(config);
    });
  }

  function bindToolbarHelpDismiss(config) {
    var dismissBtn = document.getElementById("nsm-ag-toolbar-help-dismiss");
    if (!dismissBtn || dismissBtn.dataset.nsmToolbarHelpBound === "1") {
      return;
    }
    dismissBtn.dataset.nsmToolbarHelpBound = "1";
    dismissBtn.addEventListener("click", function (event) {
      event.preventDefault();
      NSM_TOOLBAR_HELP_VISIBLE = false;
      syncToolbarHelpVisibility(config);
    });
  }

  function bindMatrixModeToolbar(config) {
    var wrap = document.getElementById("nsm-ag-matrix-mode-wrap");
    if (!wrap || wrap.dataset.nsmMatrixModeBound === "1") {
      return;
    }
    wrap.dataset.nsmMatrixModeBound = "1";
    wrap.querySelectorAll(".nsm-ag-matrix-mode-btn").forEach(function (btn) {
      btn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        var nextMode = btn.getAttribute("data-mode");
        if (!nextMode || nextMode === resolveMatrixMode(config)) {
          return;
        }
        applyMatrixModeChange(config, nextMode).then(function () {
          updateMatrixModeToolbarActiveState(config);
        });
      });
    });
    updateMatrixModeToolbarActiveState(config);
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
        setGroupHeaderDropzoneState(
          document.getElementById("nsm-ag-group-dropzone"),
          false,
          false,
          false
        );
        setMatrixDropzoneState(
          document.getElementById("nsm-ag-matrix-dropzone"),
          false,
          false
        );
        NSM_GROUP_DRAG_SOURCE = null;
        NSM_GROUP_DRAG_VALUE = null;
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
      reloadRulesGridData(
        gridApi,
        config,
        state,
        function () {
          refreshRulesGroupCells(gridApi);
          syncRulesGroupedGridLayout(gridApi, state);
        },
        { groupingOnly: true }
      );
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
      reloadRulesGridData(
        gridApi,
        config,
        state,
        function () {
          refreshRulesGroupCells(gridApi);
          syncRulesGroupedGridLayout(gridApi, state);
        },
        { groupingOnly: true }
      );
    });
  }

  function resolveRulesGroupedFetchLimit(config) {
    return (config && config.gridAutoLoadAllMax) || POLICY_GRID_FETCH_MAX;
  }

  function resolveRulesLoadEndRow(config, state) {
    var hardLimit = config.loadRowLimit || POLICY_GRID_FETCH_MAX;
    if (state && state.groupByEnabled) {
      var groupedLimit = resolveRulesGroupedFetchLimit(config);
      if (
        state &&
        typeof state.knownTotalRows === "number" &&
        state.knownTotalRows > 0
      ) {
        return Math.min(state.knownTotalRows, groupedLimit);
      }
      return hardLimit;
    }
    var total =
      (state && state.knownTotalRows) ||
      (config && config.totalCount) ||
      0;
    if (total > 0) {
      return Math.min(total, hardLimit);
    }
    return hardLimit;
  }

  function rulesFetchPageExhausted(data, startRow, endRow, loadedCount, config, state) {
    if (typeof data.lastRow === "number") {
      if (state && state.groupByEnabled) {
        return loadedCount >= data.lastRow;
      }
      var target = resolveRulesMaxLoadableRows(state, config);
      return loadedCount >= Math.min(data.lastRow, target);
    }
    var rows = (data && data.rowData) || [];
    var pageSize = Math.max(0, endRow - startRow);
    if (pageSize <= 0) {
      return true;
    }
    return rows.length < pageSize;
  }

  function ensureRulesGridFullyLoaded(api, config, state) {
    if (!api || !config || !state || !config.gridDataUrl) {
      return Promise.resolve(state ? state.loadedRowCount || 0 : 0);
    }
    if (state.autoLoadActive) {
      return Promise.resolve(state.loadedRowCount || 0);
    }
    var loaded =
      typeof state.loadedRowCount === "number"
        ? state.loadedRowCount
        : (state._accumulatedRows || []).length;
    var total = state.knownTotalRows || 0;
    var endTarget = resolveRulesMaxLoadableRows(state, config);
    if (total > 0) {
      if (state.groupByEnabled) {
        endTarget = Math.min(total, resolveRulesGroupedFetchLimit(config));
      } else {
        endTarget = Math.min(total, endTarget);
      }
    }
    if (loaded >= endTarget) {
      return Promise.resolve(loaded);
    }
    state.autoLoadActive = true;
    return appendRulesClientRows(api, config, state, loaded, endTarget)
      .then(function () {
        state.autoLoadActive = false;
        var nextLoaded = state.loadedRowCount || 0;
        if (nextLoaded > loaded && nextLoaded < endTarget) {
          return ensureRulesGridFullyLoaded(api, config, state);
        }
        return nextLoaded;
      })
      .catch(function (err) {
        state.autoLoadActive = false;
        throw err;
      });
  }

  function resolveRulesInitialLoadTarget(config, state) {
    return resolveRulesLoadEndRow(config, state);
  }

  function resolveRulesMaxLoadableRows(state, config) {
    var hardLimit = config.loadRowLimit || POLICY_GRID_FETCH_MAX;
    if (state && state.groupByEnabled) {
      var groupedLimit = resolveRulesGroupedFetchLimit(config);
      var displayTotal =
        state &&
        typeof state.knownTotalRows === "number" &&
        state.knownTotalRows > 0
          ? state.knownTotalRows
          : 0;
      if (displayTotal > 0) {
        return Math.min(displayTotal, groupedLimit);
      }
      return groupedLimit;
    }
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
    if (config) {
      config.filterQuery = "";
      config.activeFilterView = null;
    }
    applyFilterViewDirective("table", config, NSM_GROUP_NAV_CTX || NSM_MATRIX_CTX, {});
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

  function splitTopLevelFilterText(text, keyword) {
    text = text || "";
    var kw = String(keyword || "").toUpperCase();
    var kwLen = kw.length;
    var parts = [];
    var buf = [];
    var depth = 0;
    var i = 0;
    while (i < text.length) {
      var ch = text[i];
      if (ch === "(") {
        depth += 1;
        buf.push(ch);
        i += 1;
        continue;
      }
      if (ch === ")") {
        depth -= 1;
        buf.push(ch);
        i += 1;
        continue;
      }
      if (depth === 0 && text.slice(i, i + kwLen).toUpperCase() === kw) {
        var before = i > 0 ? text[i - 1] : " ";
        var after = i + kwLen < text.length ? text[i + kwLen] : " ";
        if (
          (/\s/.test(before) || before === "(" || before === ",") &&
          (/\s/.test(after) || after === "(" || after === ",")
        ) {
          var segment = buf.join("").trim();
          if (segment) {
            parts.push(segment);
          }
          buf = [];
          i += kwLen;
          continue;
        }
      }
      buf.push(ch);
      i += 1;
    }
    var tail = buf.join("").trim();
    if (tail) {
      parts.push(tail);
    }
    return parts;
  }

  function countViewDirectives(raw) {
    var text = (raw || "").trim();
    if (!text) {
      return 0;
    }
    var count = 0;
    splitTopLevelFilterText(text, "AND").forEach(function (part) {
      part = part.trim();
      if (part && NSM_VIEW_DIRECTIVE_RE.test(part)) {
        count += 1;
      }
    });
    return count;
  }

  function parseViewDirective(raw) {
    var text = (raw || "").trim();
    if (!text) {
      return { view: null, body: "", error: null };
    }
    var viewModes = [];
    var filterParts = [];
    splitTopLevelFilterText(text, "AND").forEach(function (part) {
      part = part.trim();
      if (!part) {
        return;
      }
      var match = part.match(NSM_VIEW_DIRECTIVE_RE);
      if (match) {
        viewModes.push(match[1].toLowerCase());
        return;
      }
      filterParts.push(part);
    });
    return {
      view: viewModes.length ? viewModes[viewModes.length - 1] : null,
      body: filterParts.join(" AND ").trim(),
      error: null,
    };
  }

  function appendViewDirective(filterBody, view) {
    var parsed = parseViewDirective(filterBody);
    var body = parsed.body;
    if (!view || view === "table") {
      return body;
    }
    var directive = "view(" + String(view).toLowerCase() + ")";
    if (!body) {
      return directive;
    }
    return body + " AND " + directive;
  }

  function normalizeFilterQueryView(raw) {
    var parsed = parseViewDirective(raw);
    return appendViewDirective(parsed.body, parsed.view);
  }

  function normalizeFilterQueryConfig(config, queryText) {
    if (!config) {
      return (queryText || "").trim();
    }
    var normalized = normalizeFilterQueryView(queryText);
    config.filterQuery = normalized;
    if (config.useServerFilterQ) {
      config.activeFilterQ = normalized;
    }
    return normalized;
  }

  function matrixValueToColumnKey(value) {
    var text = (value || "").trim();
    if (text.indexOf("col:") === 0) {
      return text.slice(4);
    }
    return null;
  }

  function agGridColFilterToAxisQuery(colFilter) {
    if (!colFilter || typeof colFilter !== "object") {
      return "";
    }
    var nested = colFilter.conditions || [];
    if (nested.length) {
      var joinOp = String(colFilter.operator || "AND").toUpperCase();
      if (joinOp !== "AND" && joinOp !== "OR") {
        joinOp = "AND";
      }
      var parts = [];
      nested.forEach(function (condition) {
        if (!condition || condition.filter == null) {
          return;
        }
        var raw = String(condition.filter).trim();
        if (raw) {
          parts.push(raw);
        }
      });
      if (!parts.length) {
        return "";
      }
      if (parts.length === 1) {
        return parts[0];
      }
      return parts.join(" " + joinOp + " ");
    }
    if (colFilter.filter == null) {
      return "";
    }
    return String(colFilter.filter).trim();
  }

  function extractMatrixAxisQueries(filterModel, rowMatrixValue, colMatrixValue) {
    var rowKey = matrixValueToColumnKey(rowMatrixValue);
    var colKey = matrixValueToColumnKey(colMatrixValue);
    var srcQ = "";
    var dstQ = "";
    if (filterModel && rowKey && filterModel[rowKey]) {
      srcQ = agGridColFilterToAxisQuery(filterModel[rowKey]);
    }
    if (filterModel && colKey && filterModel[colKey]) {
      dstQ = agGridColFilterToAxisQuery(filterModel[colKey]);
    }
    return { srcQ: srcQ, dstQ: dstQ };
  }

  function syncMatrixFilterToUrl(srcQ, dstQ) {
    var params = new URLSearchParams(window.location.search);
    if (srcQ) {
      params.set("src_q", srcQ);
    } else {
      params.delete("src_q");
    }
    if (dstQ) {
      params.set("dst_q", dstQ);
    } else {
      params.delete("dst_q");
    }
    syncGroupingUrl(params, false);
  }

  function applyMatrixAxisFiltersFromModel(config, filterModel) {
    if (!config || !config.matrixEnabled) {
      return;
    }
    var levels = readMatrixLevelsFromConfig(config);
    if (!matrixLevelsComplete(levels)) {
      return;
    }
    var rowValue = matrixLevelValue(levels, NSM_MATRIX_ROW_SLOT);
    var colValue = matrixLevelValue(levels, NSM_MATRIX_COL_SLOT);
    var axis = extractMatrixAxisQueries(filterModel, rowValue, colValue);
    syncMatrixFilterToUrl(axis.srcQ, axis.dstQ);
    if (
      window.NSM_MATRIX_AG &&
      typeof window.NSM_MATRIX_AG.applyMatrixAxisFilters === "function" &&
      NSM_MATRIX_CTX &&
      NSM_MATRIX_CTX.matrixHandle &&
      NSM_MATRIX_CTX.matrixHandle.api
    ) {
      window.NSM_MATRIX_AG.applyMatrixAxisFilters(
        NSM_MATRIX_CTX.matrixHandle.api,
        axis.srcQ,
        axis.dstQ
      );
    }
  }

  function clearMatrixViewState(config, ctx) {
    updateConfigFromMatrixLevels(config, []);
    renderMatrixPills(config);
    exitMatrixMode(config);
    persistMatrixSession(config);
    var params = buildMatrixUrlParams([], config);
    params.delete("obj_type");
    syncMatrixUrl(params, true);
    if (ctx && ctx.state) {
      setRulesViewMode(false);
    }
  }

  function applyFilterViewDirective(view, config, ctx, filterModel) {
    ctx = ctx || NSM_GROUP_NAV_CTX || NSM_MATRIX_CTX;
    if (!config) {
      return Promise.resolve(false);
    }
    var mode = view || "table";
    setToolbarViewMode(config, mode);
    config.activeFilterView =
      view && view !== "table" ? String(view).toLowerCase() : null;

    if (mode === "table") {
      if (ctx && ctx.gridApi) {
        applyRulesGroupingLevels([], ctx);
      }
      return applyRulesMatrixLevels([], ctx || NSM_MATRIX_CTX).then(function () {
        setToolbarViewMode(config, "table");
        syncMatrixFilterToUrl("", "");
        syncToolbarViewModeSelector(config);
        syncGroupToolbarVisibility(config);
        return true;
      });
    }

    if (mode === "group") {
      clearMatrixViewState(config, ctx);
      var levels = readGroupLevelsFromConfig(config);
      if (levels.length && ctx && ctx.gridApi) {
        applyRulesGroupingLevels(levels, ctx);
      } else if (ctx && ctx.gridApi && ctx.state) {
        updateConfigFromGroupLevels(config, []);
        ctx.state.groupByEnabled = false;
        syncRulesGroupColumnDefs(
          ctx.gridApi,
          config,
          ctx.state,
          ctx.profileKey || "rules"
        );
        renderGroupPills(config);
        syncGroupToolbarVisibility(config);
      }
      syncMatrixFilterToUrl("", "");
      syncToolbarViewModeSelector(config);
      return Promise.resolve(true);
    }

    if (mode === "matrix") {
      if (ctx && ctx.gridApi) {
        clearGroupingForMatrix(config, ctx);
      }
      var matrixLevels = readMatrixLevelsFromConfig(config);
      if (matrixLevelsComplete(matrixLevels)) {
        return applyRulesMatrixLevels(matrixLevels, ctx || NSM_MATRIX_CTX).then(
          function () {
            applyMatrixAxisFiltersFromModel(config, filterModel);
            syncToolbarViewModeSelector(config);
            return true;
          }
        );
      }
      showGroupToolbarMessage(
        config.matrixViewNotReadyMessage || NSM_FILTER_VIEW_MATRIX_NOT_READY_FALLBACK
      );
      clearMatrixViewState(config, ctx);
      setToolbarViewMode(config, "matrix");
      syncToolbarViewModeSelector(config);
      return Promise.resolve(false);
    }

    syncToolbarViewModeSelector(config);
    return Promise.resolve(true);
  }

  function applyInitialFilterViewFromQuery(config, ctx, filterModel) {
    var raw = "";
    if (config && config.useServerFilterQ && config.activeFilterQ) {
      raw = String(config.activeFilterQ);
    } else if (typeof window !== "undefined") {
      raw =
        new URLSearchParams(window.location.search).get("filter_q") ||
        (config && config.filterQuery) ||
        "";
    } else if (config && config.filterQuery) {
      raw = config.filterQuery;
    }
    raw = (raw || "").trim();
    if (!raw) {
      return Promise.resolve();
    }
    var parsed = parseViewDirective(raw);
    if (countViewDirectives(raw) > 1) {
      var normalized = normalizeFilterQueryConfig(config, raw);
      if (config && config.useServerFilterQ) {
        if (hasActiveFilterQuery(config)) {
          syncAllRulesFilterToUrl(config);
        } else {
          stripFilterQueryFromUrl(config);
        }
      } else if (normalized) {
        syncRulesFilterQueryToUrl(config, normalized);
      }
      if (ctx && ctx.gridApi) {
        updateFilterQueryInput(ctx.gridApi, config, true);
      }
    }
    if (!parsed.view) {
      return Promise.resolve();
    }
    return applyFilterViewDirective(parsed.view, config, ctx, filterModel);
  }

  function syncRulesFilterQueryToUrl(config, queryText) {
    if (!config || typeof window === "undefined") {
      return;
    }
    var url = new URL(window.location.href);
    url.searchParams.delete("filter_q");
    var body = (queryText || "").trim();
    if (body) {
      url.searchParams.set("filter_q", body);
    }
    var next = url.pathname + url.search + url.hash;
    window.history.replaceState(null, "", next);
    config.filterQuery = body;
  }

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
    var queryText = normalizeFilterQueryView((filterQText || "").trim());
    var viewParsed = parseViewDirective(queryText);
    if (config) {
      config.filterQuery = queryText;
      config.activeFilterView =
        viewParsed.view && viewParsed.view !== "table" ? viewParsed.view : null;
    }
    if (config && config.useServerFilterQ) {
      config.activeFilterQ = queryText;
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
    } else if (queryText) {
      syncRulesFilterQueryToUrl(config, queryText);
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
      applyFilterViewDirective(
        "table",
        config,
        NSM_GROUP_NAV_CTX || NSM_MATRIX_CTX,
        {}
      );
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
      var viewMode =
        data.view != null && data.view !== ""
          ? String(data.view).toLowerCase()
          : parseViewDirective(queryText).view;
      applyFilterViewDirective(
        viewMode,
        config,
        NSM_GROUP_NAV_CTX || NSM_MATRIX_CTX,
        data.filterModel || {}
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
    if (config && config.filterQuery) {
      return String(config.filterQuery).trim();
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
    if (!query && typeof window !== "undefined") {
      query = new URLSearchParams(window.location.search).get("filter_q") || "";
    }
    query = (query || "").trim();
    var parsed = parseViewDirective(query);
    var effectiveView =
      config && config.activeFilterView ? config.activeFilterView : parsed.view;
    return appendViewDirective(parsed.body, effectiveView);
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
    if (countViewDirectives(query) > 1) {
      query = normalizeFilterQueryConfig(config, query);
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
    if (!filterValue && colDef.filterValueGetter) {
      filterValue = String(colDef.filterValueGetter(params) || "").trim();
      displayValue = filterValue;
    }
    if (!filterValue) {
      if (colDef.field && rowNode.data[colDef.field] != null) {
        filterValue = String(rowNode.data[colDef.field]).trim();
        displayValue = filterValue;
      } else {
        displayValue = (cellEl.textContent || "").trim();
        filterValue = displayValue;
      }
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

  function resolveFloatingFilterHeaderCell(target) {
    if (!target || typeof target.closest !== "function") {
      return null;
    }
    var headerCell = target.closest(".ag-header-cell[col-id]");
    if (!headerCell) {
      return null;
    }
    if (
      headerCell.classList.contains("ag-floating-filter") ||
      headerCell.querySelector(".ag-floating-filter")
    ) {
      return headerCell;
    }
    return null;
  }

  function applyColumnFilterFromCellDrop(gridApi, targetColId, filterValue) {
    if (!gridApi || !targetColId || typeof gridApi.setFilterModel !== "function") {
      return;
    }
    var text = String(filterValue == null ? "" : filterValue).trim();
    if (!text) {
      return;
    }
    var model =
      typeof gridApi.getFilterModel === "function"
        ? Object.assign({}, gridApi.getFilterModel() || {})
        : {};
    model[targetColId] = {
      filterType: "text",
      type: "contains",
      filter: text,
    };
    gridApi.setFilterModel(model);
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
        disableNativeLinkDragInCell(cell);
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

  function bindFloatingFilterDropTarget(gridApi, gridEl, config) {
    if (!gridApi || !gridEl || !config || !config.filterColumnMap) {
      return;
    }
    if (gridEl.dataset.nsmFloatingFilterDropBound === "1") {
      return;
    }
    gridEl.dataset.nsmFloatingFilterDropBound = "1";

    gridEl.addEventListener(
      "dragover",
      function (event) {
        var headerCell = resolveFloatingFilterHeaderCell(event.target);
        if (!headerCell || !isFilterCellDragEvent(event)) {
          return;
        }
        var colId = headerCell.getAttribute("col-id");
        if (!colId || !config.filterColumnMap[colId]) {
          return;
        }
        event.preventDefault();
        if (event.dataTransfer) {
          event.dataTransfer.dropEffect = "copy";
        }
        headerCell.classList.add("nsm-ag-floating-filter-drop-hover");
      },
      true
    );

    gridEl.addEventListener(
      "dragleave",
      function (event) {
        var headerCell = resolveFloatingFilterHeaderCell(event.target);
        if (
          headerCell &&
          (!headerCell.contains(event.relatedTarget) ||
            !resolveFloatingFilterHeaderCell(event.relatedTarget))
        ) {
          headerCell.classList.remove("nsm-ag-floating-filter-drop-hover");
        }
      },
      true
    );

    gridEl.addEventListener(
      "drop",
      function (event) {
        var headerCell = resolveFloatingFilterHeaderCell(event.target);
        if (!headerCell) {
          return;
        }
        headerCell.classList.remove("nsm-ag-floating-filter-drop-hover");
        var payload = parseFilterCellDropPayload(event);
        if (!payload) {
          var droppedText =
            event.dataTransfer && event.dataTransfer.getData
              ? String(event.dataTransfer.getData("text/plain") || "").trim()
              : "";
          if (/^https?:\/\//i.test(droppedText)) {
            event.preventDefault();
            event.stopPropagation();
          }
          return;
        }
        var colId = headerCell.getAttribute("col-id");
        if (!colId || !config.filterColumnMap[colId]) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        markFilterDropTargetsActive(false);
        applyColumnFilterFromCellDrop(gridApi, colId, payload.filterValue);
      },
      true
    );
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
    var enableAutoHeight = options.autoHeight !== false;
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
          col.autoHeight = enableAutoHeight;
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

  function itemIsAddrAnalyzable(item) {
    return !!(item && (item.addrAnalyzable || item.addr_analyzable));
  }

  function createItemLoupeButton(item) {
    var title = "Objekt analysieren";
    var btn;
    if (window.NsmIpAnalyzerApplet && window.NsmIpAnalyzerApplet.createLoupeButton) {
      btn = window.NsmIpAnalyzerApplet.createLoupeButton(title, item);
    } else {
      btn = document.createElement("button");
      btn.type = "button";
      btn.className = "nsm-ipa-loupe";
      btn.setAttribute("aria-label", title);
      btn.title = title;
      btn.innerHTML = '<i class="mdi mdi-magnify" aria-hidden="true"></i>';
      if (item && item.ct != null && item.pk != null) {
        btn.setAttribute("data-ct", String(item.ct));
        btn.setAttribute("data-pk", String(item.pk));
        btn.setAttribute("data-name", item.name != null ? String(item.name) : "");
      }
    }
    return btn;
  }

  function buildObjectCellItem(item, hidden, colored) {
    var span = document.createElement("span");
    span.className = "nsm-ag-cell-item" + (hidden ? " nsm-pill-hidden" : "");
    if (item && item.excluded) {
      span.classList.add("nsm-ag-cell-excluded");
    }
    if (item && item.ct != null && item.pk != null) {
      span.setAttribute("data-ct", String(item.ct));
      span.setAttribute("data-pk", String(item.pk));
      span.setAttribute("data-name", item.name != null ? String(item.name) : "");
      if (itemIsAddrAnalyzable(item)) {
        span.setAttribute("data-addr-analyzable", "1");
      }
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
    link.setAttribute("draggable", "false");
    var fullName = (item && item.name) || "";
    link.title = fullName;
    link.setAttribute("data-nsm-filter-value", fullName);
    link.textContent = truncateCellText(fullName);
    span.appendChild(link);
    if (itemIsAddrAnalyzable(item)) {
      span.appendChild(createItemLoupeButton(item));
    }
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

  function updateRulesGroupToggleButton(toggle, collapsed) {
    if (!toggle) {
      return;
    }
    toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    toggle.setAttribute(
      "aria-label",
      collapsed ? "Expand group" : "Collapse group"
    );
    toggle.classList.toggle("is-expanded", !collapsed);
  }

  function refreshRulesGroupCells(api) {
    if (!api || typeof api.refreshCells !== "function") {
      return;
    }
    api.refreshCells({
      columns: [POLICY_GROUP_COL_ID],
      force: true,
    });
  }

  function syncRulesGroupedGridLayout(api, state) {
    if (!api || !state || !state.gridEl) {
      return;
    }
    var grouped = !!state.groupByEnabled;
    state.gridEl.classList.toggle("nsm-rules-ag-grid--grouped", grouped);
    if (typeof api.setGridOption === "function") {
      api.setGridOption("domLayout", grouped ? "autoHeight" : "normal");
    }
  }

  function refreshRulesGroupedGridHeight(api, state) {
    if (!api || !state || !state.groupByEnabled) {
      return;
    }
    syncRulesGroupedGridLayout(api, state);
    resetRulesRowHeights(api, true);
    window.requestAnimationFrame(function () {
      syncRulesGroupedGridLayout(api, state);
      flushRulesGridAsyncTransactions(api);
      if (typeof api.onRowHeightChanged === "function") {
        api.onRowHeightChanged();
      }
    });
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
    toggle.innerHTML =
      '<i class="mdi mdi-chevron-right" aria-hidden="true"></i>';
    updateRulesGroupToggleButton(toggle, collapsed);
    toggle.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      toggleRulesGroupCollapse(groupKey, state);
      updateRulesGroupToggleButton(
        toggle,
        isRulesGroupCollapsed(groupKey, state)
      );
      syncGroupExpansionUrl(state);
      reloadRulesGridData(
        params.api,
        config,
        state,
        function () {
          refreshRulesGroupCells(params.api);
          refreshRulesGroupedGridHeight(params.api, state);
        },
        { groupingOnly: true }
      );
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
    restoreMatrixSession(config);
    renderGroupSourceChips(config);
    renderGroupPills(config);
    renderMatrixPills(config);
    bindGroupDropZone(config);
    bindMatrixDropZone(config);
    bindGroupExpandCollapseButtons(config, state, gridApi);
    removeLegacyMatrixGridModeChrome();
    bindMatrixModeToolbar(config);
    bindToolbarViewModeSelector(config, {
      gridApi: gridApi,
      config: config,
      state: state,
      profileKey: profileKey,
      gridEl: gridEl,
    });
    bindToolbarHelpToggle(config);
    bindToolbarHelpDismiss(config);
    syncGroupToolbarVisibility(config);
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
    NSM_MATRIX_CTX = {
      config: config,
      state: state,
      gridApi: gridApi,
      matrixHandle: null,
      matrixConfig: null,
    };
    bindCsvExportButton(config, NSM_GROUP_NAV_CTX);
    applyInitialFilterViewFromQuery(
      config,
      NSM_GROUP_NAV_CTX,
      config.initialFilterModel || null
    ).then(function () {
      if (!config || !config.matrixEnabled) {
        return;
      }
      return enterMatrixMode(config).then(function () {
        applyMatrixAxisFiltersFromModel(
          config,
          (gridApi && typeof gridApi.getFilterModel === "function"
            ? gridApi.getFilterModel()
            : null) ||
            config.initialFilterModel ||
            {}
        );
      });
    });
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
      syncRulesGroupedGridLayout(api, state);
      refreshRulesGroupCells(api);
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
        }
        setRulesGridRows(api, rows, state, "set");
        return ensureRulesGridFullyLoaded(api, config, state).then(function () {
          if (state) {
            state.progressiveLoadActive = false;
            state.initialLoadActive = false;
            notifyRulesRowsLoaded(state, state.knownTotalRows, false);
            maybePersistRulesTabDataCache(state, config);
            if (isRulesTabRefreshRequested()) {
              stripRulesTabRefreshFromUrl();
            }
          }
          window.requestAnimationFrame(function () {
            resetRulesRowHeights(api, state && state.groupByEnabled);
            scheduleAutoSizeRulesContentColumns(api, state);
            syncRulesGroupedGridLayout(api, state);
            refreshRulesGroupedGridHeight(api, state);
            refreshRulesGroupCells(api);
          });
          if (typeof done === "function") {
            done(state ? state.knownTotalRows : rows.length);
          }
          return rows;
        });
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
            state.loadedRowCount,
            config,
            state
          );

          function finishProgressiveLoad() {
            return ensureRulesGridFullyLoaded(api, config, state).then(function () {
              finishLoad();
            });
          }

          notifyRulesRowsLoaded(
            state,
            state.knownTotalRows,
            !fetchDone ||
              state.loadedRowCount <
                Math.min(
                  state.knownTotalRows || 0,
                  resolveRulesMaxLoadableRows(state, config)
                )
          );

          if (fetchDone) {
            return finishProgressiveLoad().then(function () {
              return rows;
            });
          }

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
          return ensureRulesGridFullyLoaded(api, config, state).then(function () {
            if (
              state.loadedRowCount >=
              Math.min(
                state.knownTotalRows || 0,
                resolveRulesMaxLoadableRows(state, config)
              )
            ) {
              return finishProgressiveLoad().then(function () {
                return rows;
              });
            }
            return new Promise(function (resolve) {
              window.setTimeout(function () {
                loadStep(stepIndex + 1).then(resolve);
              }, 16);
            });
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
      state.knownTotalRows = 0;
      state.loadedRowCount = 0;
      state._accumulatedRows = [];
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
    if (typeof window !== "undefined") {
      var urlFilterQ = new URLSearchParams(window.location.search).get("filter_q");
      if (urlFilterQ && countViewDirectives(urlFilterQ) > 1) {
        var normalizedUrlFilterQ = normalizeFilterQueryConfig(config, urlFilterQ);
        syncRulesFilterQueryToUrl(config, normalizedUrlFilterQ);
      }
    }
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
      autoHeight: !datasourceState.groupByEnabled,
    });
    if (datasourceState.groupByEnabled) {
      columnDefs = prependRulesGroupColumn(columnDefs, config);
      gridEl.classList.add("nsm-rules-ag-grid--grouped");
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
        '" draggable="false" data-nsm-filter-value="' +
        escapeHtml(name) +
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
        '" draggable="false" data-nsm-filter-value="' +
        escapeHtml(idx) +
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
        '" draggable="false" data-nsm-filter-value="' +
        escapeHtml(name) +
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
      domLayout: datasourceState.groupByEnabled ? "autoHeight" : "normal",
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
        syncRulesGroupedGridLayout(params.api, datasourceState);
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
        syncRulesGroupedGridLayout(params.api, datasourceState);
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
        if (meta && meta.partial) {
          ensureRulesGridFullyLoaded(gridApi, config, datasourceState).then(function () {
            updateRowStatsForProfile(
              gridApi,
              datasourceState.knownTotalRows,
              datasourceState,
              config,
              profile
            );
          });
        }
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
    bindFloatingFilterDropTarget(gridApi, gridEl, config);

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
    if (config.activeFilterQ && countViewDirectives(config.activeFilterQ) > 1) {
      normalizeFilterQueryConfig(config, config.activeFilterQ);
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
    applyTextColumnFilters(columnDefs, {
      enableColumnFilters: true,
      enableFloatingFilters: false,
      autoHeight: !datasourceState.groupByEnabled,
    });
    if (datasourceState.groupByEnabled) {
      columnDefs = prependRulesGroupColumn(columnDefs, config);
      gridEl.classList.add("nsm-rules-ag-grid--grouped");
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
        '" draggable="false" data-nsm-filter-value="' +
        escapeHtml(name) +
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
          '" draggable="false" data-nsm-filter-value="' +
          escapeHtml(name) +
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
      domLayout: datasourceState.groupByEnabled ? "autoHeight" : "normal",
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
        syncRulesGroupedGridLayout(params.api, datasourceState);
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

    datasourceState.onRowsLoaded = function (total, meta) {
      if (gridApi) {
        updateRowStatsForProfile(gridApi, total, datasourceState, config, profile);
        if (meta && meta.partial) {
          ensureRulesGridFullyLoaded(gridApi, config, datasourceState).then(function () {
            updateRowStatsForProfile(
              gridApi,
              datasourceState.knownTotalRows,
              datasourceState,
              config,
              profile
            );
          });
        }
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
    bindFloatingFilterDropTarget(gridApi, gridEl, config);
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
          oddRowBackgroundColor: "#ffffff",
          rowHoverColor: "#e8f0fa",
          selectedRowBackgroundColor: "#d1e1f3",
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
          oddRowBackgroundColor: "#1a2332",
          rowHoverColor: "#233348",
          selectedRowBackgroundColor: "#2c4560",
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
    if (entry.api._nsmDatasourceState) {
      syncRulesGroupedGridLayout(entry.api, entry.api._nsmDatasourceState);
    }
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
