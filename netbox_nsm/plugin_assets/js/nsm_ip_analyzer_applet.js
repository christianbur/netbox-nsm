/**
 * Floating draggable IP Analyzer popup for NSM.
 * window.NsmIpAnalyzerApplet.open({ objects: [{ ct, pk, name }], title?: string })
 */
(function () {
  "use strict";

  var U = window.NsmIpaUtil;
  var ipaT = U.ipaT;
  var ipaTf = U.ipaTf;
  var escHtml = U.escHtml;
  var formatTypeCountSummary = U.formatTypeCountSummary;
  var apiUrl = U.apiUrl;
  var addObjectTypesApiUrl = U.addObjectTypesApiUrl;
  var debounce = U.debounce;
  var getCsrfToken = U.getCsrfToken;
  var nsmFetch = U.nsmFetch;
  var readIpaApiJson = U.readIpaApiJson;
  var fetchIpaAnalysis = U.fetchIpaAnalysis;
  var ipaFetchAbortMessage = U.ipaFetchAbortMessage;
  var mergeBranchHeaders = U.mergeBranchHeaders;
  var normalizeObjects = U.normalizeObjects;
  var collectRawObjects = U.collectRawObjects;
  var objectsKey = U.objectsKey;
  var tabDedupKey = U.tabDedupKey;
  var rulesCellTabTitle = U.rulesCellTabTitle;
  var rulesCellContextLabel = U.rulesCellContextLabel;
  var rulesCellPositionTag = U.rulesCellPositionTag;
  var rulesCellDiffSideLabel = U.rulesCellDiffSideLabel;
  var diffSideLabel = U.diffSideLabel;
  var diffTabContextLabel = U.diffTabContextLabel;
  var tabTitle = U.tabTitle;
  var mergedTabTitle = U.mergedTabTitle;
  var diffRulesSideShortLabel = U.diffRulesSideShortLabel;
  var diffTabTitleFromTabs = U.diffTabTitleFromTabs;
  var diffObjectsKey = U.diffObjectsKey;
  var formatDiffSummary = U.formatDiffSummary;
  var collectObjectsFromTabs = U.collectObjectsFromTabs;
  var truncateTitle = U.truncateTitle;
  var buildQuery = U.buildQuery;
  var buildDiffQuery = U.buildDiffQuery;
  var buildExportQuery = U.buildExportQuery;
  var parseContentDispositionFilename = U.parseContentDispositionFilename;
  var triggerBlobDownload = U.triggerBlobDownload;
  var defaultPosition = U.defaultPosition;
  var createLoupeButton = U.createLoupeButton;
  var loadingHtml = U.loadingHtml;
  var errorHtml = U.errorHtml;
  var TAB_TITLE_MAX = U.TAB_TITLE_MAX;

  var ROOT_ID = "nsm-ipa-applet-root";
  var DRAG_THRESHOLD = 4;
  var MIN_WIDTH = 320;
  var MIN_HEIGHT = 240;
  var VIEWPORT_MARGIN = 12;
  var SIZE_STORAGE_KEY = "nsm-ipa-applet-size";
  var MIN_BODY_SCALE = 0.55;

  function Applet() {
    this.el = null;
    this.bodyEl = null;
    this.footerEl = null;
    this.titleEl = null;
    this.ruleBadgeEl = null;
    this.tabsEl = null;
    this.tabListEl = null;
    this.toolbarEl = null;
    this.toolbarActionsEl = null;
    this.addObjectMenuEl = null;
    this.addObjectModalEl = null;
    this.addObjectSearchEl = null;
    this.addObjectResultsEl = null;
    this.addObjectTitleEl = null;
    this.mergeBtnEl = null;
    this.diffBtnEl = null;
    this.exportBtnEl = null;
    this._addObjectCategories = null;
    this._addObjectCategory = null;
    this._addObjectSearchCtrl = null;
    this._addObjectSearchToken = 0;
    this.minimized = false;
    this._merging = false;
    this._diffing = false;
    this._exporting = false;
    this.dragState = null;
    this.resizeState = null;
    this.tabs = [];
    this.activeTabId = null;
    this.nextTabId = 1;
    this._onMove = this._onMove.bind(this);
    this._onUp = this._onUp.bind(this);
    this._onResizeMove = this._onResizeMove.bind(this);
    this._onResizeUp = this._onResizeUp.bind(this);
  }

  Applet.prototype.ensureDom = function () {
    if (this.el) {
      return;
    }
    var root = document.getElementById(ROOT_ID);
    if (!root) {
      root = document.createElement("div");
      root.id = ROOT_ID;
      document.body.appendChild(root);
    }

    var panel = document.createElement("div");
    panel.className = "nsm-ipa-applet";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "false");
    panel.setAttribute("aria-label", ipaT("IP Analysis"));
    panel.hidden = true;
    panel.innerHTML =
      '<div class="nsm-ipa-applet-header">' +
        '<h6 class="nsm-ipa-applet-title"><i class="mdi mdi-ip-network-outline" aria-hidden="true"></i><span class="nsm-ipa-applet-title-text">' +
        escHtml(ipaT("IP Analysis")) +
        '</span></h6>' +
        '<span class="badge bg-secondary-subtle text-secondary nsm-ipa-applet-rule-badge" hidden></span>' +
        '<div class="nsm-ipa-applet-actions">' +
          '<button type="button" class="btn btn-sm btn-ghost-secondary py-0 px-1 nsm-ipa-applet-minimize" title="' +
          escHtml(ipaT("Minimize")) +
          '" aria-label="' +
          escHtml(ipaT("Minimize")) +
          '"><i class="mdi mdi-window-minimize"></i></button>' +
          '<button type="button" class="btn btn-sm btn-ghost-secondary py-0 px-1 nsm-ipa-applet-close" title="' +
          escHtml(ipaT("Close")) +
          '" aria-label="' +
          escHtml(ipaT("Close")) +
          '"><i class="mdi mdi-close"></i></button>' +
        "</div>" +
      "</div>" +
      '<div class="nsm-ipa-applet-toolbar" hidden>' +
        '<div class="dropdown nsm-ipa-applet-add-object">' +
          '<button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle nsm-ipa-applet-add-object-toggle" data-bs-toggle="dropdown" data-bs-container="body" aria-expanded="false" title="' +
          escHtml(ipaT("Add object")) +
          '" aria-label="' +
          escHtml(ipaT("Add object")) +
          '">' +
          escHtml(ipaT("Add object")) +
          '</button>' +
          '<ul class="dropdown-menu nsm-ipa-applet-add-object-menu"></ul>' +
        "</div>" +
        '<div class="nsm-ipa-applet-toolbar-actions">' +
          '<button type="button" class="btn btn-sm btn-outline-primary nsm-ipa-applet-merge" title="' +
          escHtml(ipaT("Merge")) +
          '" aria-label="' +
          escHtml(ipaT("Merge")) +
          '"><i class="mdi mdi-call-merge" aria-hidden="true"></i><span>' +
          escHtml(ipaT("Merge")) +
          '</span></button>' +
          '<button type="button" class="btn btn-sm btn-outline-primary nsm-ipa-applet-diff" title="' +
          escHtml(ipaT("Diff")) +
          '" aria-label="' +
          escHtml(ipaT("Diff")) +
          '"><i class="mdi mdi-compare" aria-hidden="true"></i><span>' +
          escHtml(ipaT("Diff")) +
          '</span></button>' +
          '<button type="button" class="btn btn-sm btn-outline-secondary nsm-ipa-applet-export" title="' +
          escHtml(ipaT("Export displayed data and IPAM children (YAML)")) +
          '" aria-label="' +
          escHtml(ipaT("Export displayed data and IPAM children (YAML)")) +
          '"><i class="mdi mdi-download" aria-hidden="true"></i><span>' +
          escHtml(ipaT("Export YAML")) +
          '</span></button>' +
        "</div>" +
      "</div>" +
      '<div class="nsm-ipa-applet-tabs" hidden>' +
        '<div class="nsm-ipa-applet-tab-list" role="tablist"></div>' +
      "</div>" +
      '<div class="nsm-ipa-applet-add-modal" hidden>' +
        '<div class="nsm-ipa-applet-add-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="nsm-ipa-applet-add-modal-title">' +
          '<div class="nsm-ipa-applet-add-modal-head">' +
            '<h6 class="nsm-ipa-applet-add-modal-title" id="nsm-ipa-applet-add-modal-title">' +
            escHtml(ipaT("Add object")) +
            '</h6>' +
            '<button type="button" class="btn btn-sm btn-ghost-secondary py-0 px-1 nsm-ipa-applet-add-modal-close" title="' +
            escHtml(ipaT("Close")) +
            '" aria-label="' +
            escHtml(ipaT("Close")) +
            '"><i class="mdi mdi-close"></i></button>' +
          "</div>" +
          '<input type="search" class="form-control form-control-sm nsm-ipa-applet-add-search" placeholder="' +
          escHtml(ipaT("Search…")) +
          '" autocomplete="off">' +
          '<div class="nsm-ipa-applet-add-results"></div>' +
        "</div>" +
      "</div>" +
      '<div class="nsm-ipa-applet-body"></div>' +
      '<div class="nsm-ipa-applet-footer"><span class="nsm-ipa-applet-status"></span><span class="nsm-ipa-applet-count"></span></div>' +
      '<div class="nsm-ipa-applet-resize-handle nsm-ipa-applet-resize-handle--n" data-resize="n" aria-hidden="true"></div>' +
      '<div class="nsm-ipa-applet-resize-handle nsm-ipa-applet-resize-handle--e" data-resize="e" aria-hidden="true"></div>' +
      '<div class="nsm-ipa-applet-resize-handle nsm-ipa-applet-resize-handle--s" data-resize="s" aria-hidden="true"></div>' +
      '<div class="nsm-ipa-applet-resize-handle nsm-ipa-applet-resize-handle--se" data-resize="se" aria-hidden="true"></div>';

    root.appendChild(panel);
    this.el = panel;
    this.bodyEl = panel.querySelector(".nsm-ipa-applet-body");
    this.footerEl = panel.querySelector(".nsm-ipa-applet-footer");
    this.titleEl = panel.querySelector(".nsm-ipa-applet-title-text");
    this.ruleBadgeEl = panel.querySelector(".nsm-ipa-applet-rule-badge");
    this.tabsEl = panel.querySelector(".nsm-ipa-applet-tabs");
    this.tabListEl = panel.querySelector(".nsm-ipa-applet-tab-list");
    this.toolbarEl = panel.querySelector(".nsm-ipa-applet-toolbar");
    this.toolbarActionsEl = panel.querySelector(".nsm-ipa-applet-toolbar-actions");
    this.addObjectMenuEl = panel.querySelector(".nsm-ipa-applet-add-object-menu");
    this.addObjectModalEl = panel.querySelector(".nsm-ipa-applet-add-modal");
    this.addObjectSearchEl = panel.querySelector(".nsm-ipa-applet-add-search");
    this.addObjectResultsEl = panel.querySelector(".nsm-ipa-applet-add-results");
    this.addObjectTitleEl = panel.querySelector(".nsm-ipa-applet-add-modal-title");
    this.mergeBtnEl = panel.querySelector(".nsm-ipa-applet-merge");
    this.diffBtnEl = panel.querySelector(".nsm-ipa-applet-diff");
    this.exportBtnEl = panel.querySelector(".nsm-ipa-applet-export");

    var header = panel.querySelector(".nsm-ipa-applet-header");
    header.addEventListener("mousedown", this._onHeaderDown.bind(this));
    panel.querySelector(".nsm-ipa-applet-close").addEventListener("click", this.close.bind(this));
    panel.querySelector(".nsm-ipa-applet-minimize").addEventListener("click", this.toggleMinimize.bind(this));

    this.tabListEl.addEventListener("click", this._onTabListClick.bind(this));
    this.mergeBtnEl.addEventListener("click", this.mergeTabs.bind(this));
    this.diffBtnEl.addEventListener("click", this.diffTabs.bind(this));
    this.exportBtnEl.addEventListener("click", this.exportYaml.bind(this));
    this._bindAddObjectHandlers();

    panel.querySelectorAll(".nsm-ipa-applet-resize-handle").forEach(
      function (handle) {
        handle.addEventListener("mousedown", this._onResizeDown.bind(this));
      }.bind(this)
    );

    this._bindBodyScaleObserver();
    this.bodyEl.addEventListener(
      "toggle",
      function () {
        this._scheduleBodyScale();
      }.bind(this),
      true
    );
  };

  Applet.prototype._wrapBodyContent = function (html) {
    return (
      '<div class="nsm-ipa-applet-body-scale-host">' +
      '<div class="nsm-ipa-applet-body-scale">' +
      html +
      "</div></div>"
    );
  };

  Applet.prototype._fitBodyScale = function () {
    if (!this.bodyEl || this.minimized) {
      return;
    }
    var host = this.bodyEl.querySelector(".nsm-ipa-applet-body-scale-host");
    var inner = host && host.querySelector(".nsm-ipa-applet-body-scale");
    if (!inner) {
      return;
    }
    this._observeBodyScaleInner();

    inner.style.transform = "none";
    inner.style.width = "";
    host.style.width = "";
    host.style.height = "auto";

    var available = this.bodyEl.clientWidth;
    var contentW = inner.scrollWidth;
    var contentH = inner.scrollHeight;
    var hasCellTreeTable = !!inner.querySelector(".nsm-ipa-cell-tree-table");
    var scale = 1;
    if (!hasCellTreeTable && contentW > available && available > 0) {
      scale = Math.max(MIN_BODY_SCALE, available / contentW);
    }

    var scaledW = Math.ceil(contentW * scale);
    var scaledH = Math.ceil(contentH * scale);

    if (hasCellTreeTable) {
      inner.style.transform = "";
      inner.style.width = "100%";
      inner.style.minWidth = "0";
      inner.style.maxWidth = "100%";
      host.style.width = "100%";
      host.style.maxWidth = "100%";
      host.style.height = "auto";
      this.bodyEl.style.overflowX = "hidden";
    } else if (scale < 0.999) {
      inner.style.width = contentW + "px";
      inner.style.transform = "scale(" + scale + ")";
      host.style.width = scaledW + "px";
      host.style.height = scaledH + "px";
      this.bodyEl.style.overflowX = scaledW > available + 1 ? "auto" : "hidden";
    } else {
      inner.style.transform = "";
      inner.style.width = "";
      inner.style.minWidth = "";
      inner.style.maxWidth = "";
      host.style.width = "";
      host.style.maxWidth = "";
      host.style.height = "";
      this.bodyEl.style.overflowX = "hidden";
    }
  };

  Applet.prototype._observeBodyScaleInner = function () {
    if (!this._bodyScaleObserver || !this.bodyEl) {
      return;
    }
    var inner = this.bodyEl.querySelector(".nsm-ipa-applet-body-scale");
    if (!inner || inner === this._bodyScaleInner) {
      return;
    }
    if (this._bodyScaleInner) {
      this._bodyScaleObserver.unobserve(this._bodyScaleInner);
    }
    this._bodyScaleInner = inner;
    this._bodyScaleObserver.observe(inner);
  };

  Applet.prototype._scheduleBodyScale = function () {
    var self = this;
    if (this._scaleRaf) {
      cancelAnimationFrame(this._scaleRaf);
    }
    this._scaleRaf = requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        self._scaleRaf = null;
        self._fitBodyScale();
      });
    });
  };

  Applet.prototype._bindBodyScaleObserver = function () {
    if (!this.bodyEl || this._bodyScaleBound) {
      return;
    }
    this._bodyScaleBound = true;
    var self = this;
    if (typeof ResizeObserver !== "undefined") {
      this._bodyScaleObserver = new ResizeObserver(function () {
        self._scheduleBodyScale();
      });
      this._bodyScaleObserver.observe(this.bodyEl);
    }
    this._onWindowResizeForScale = function () {
      self._scheduleBodyScale();
    };
    window.addEventListener("resize", this._onWindowResizeForScale);
    this._bodyMutationObserver = new MutationObserver(function () {
      if (window.nsmIpaStripLegacyExpandedWarnings) {
        window.nsmIpaStripLegacyExpandedWarnings(self.bodyEl);
      }
      self._scheduleBodyScale();
    });
  };

  Applet.prototype._observeBodyContent = function () {
    if (!this.bodyEl || !this._bodyMutationObserver) {
      return;
    }
    this._bodyMutationObserver.disconnect();
    this._bodyMutationObserver.observe(this.bodyEl, {
      childList: true,
      subtree: true,
    });
  };

  Applet.prototype._cellTreeRowDepth = function (row) {
    var match = String(row.className || "").match(/\bnsm-ipa-depth-(\d+)\b/);
    return match ? Number(match[1]) : 0;
  };

  Applet.prototype._diffGroupFromRow = function (row) {
    var className = String(row.className || "");
    var match = className.match(/\bnsm-addr-diff-group--([^\s]+)/);
    return match ? match[1] : "";
  };

  Applet.prototype._isWarningDiffRow = function (row) {
    return (
      row.classList.contains("nsm-ipa-object-node--subnet-warning") ||
      row.classList.contains("nsm-ipa-object-node--doppelt-warning") ||
      !!row.querySelector(
        ".nsm-ipa-cell-duplicate, .nsm-ipa-cell-status--deprecated, .nsm-ipa-cell-status--reserved"
      )
    );
  };

  Applet.prototype._prepareDiffOverviewRows = function (table) {
    var tbody = table && table.tBodies && table.tBodies[0];
    if (!tbody) {
      return null;
    }
    var rows = Array.prototype.slice.call(tbody.rows || []);
    var groupByDepth = [];
    var stats = {
      total: 0,
      shared: 0,
      changes: 0,
      warnings: 0,
      fund: 0,
      hasDiff: false,
    };

    rows.forEach(
      function (row) {
        if (!row.classList.contains("nsm-ipa-cell-tree-row")) {
          return;
        }
        var depth = this._cellTreeRowDepth(row);
        groupByDepth = groupByDepth.slice(0, depth);
        var ownGroup = this._diffGroupFromRow(row);
        if (ownGroup) {
          groupByDepth[depth] = ownGroup;
          stats.hasDiff = true;
        }
        var group = ownGroup || "";
        for (var i = depth; !group && i >= 0; i--) {
          group = groupByDepth[i] || "";
        }
        var isShared = group === "both" || group === "in-all";
        var isFund = row.classList.contains("nsm-addr-diff-leaf--fund");
        var isWarning = this._isWarningDiffRow(row);
        var isChange = !!group && !isShared;

        if (row.classList.contains("nsm-addr-diff-leaf")) {
          stats.hasDiff = true;
        }
        row.dataset.nsmIpaDiffShared = isShared ? "1" : "";
        row.dataset.nsmIpaDiffChange = isChange || isFund ? "1" : "";
        row.dataset.nsmIpaDiffWarning = isWarning ? "1" : "";
        row.dataset.nsmIpaDiffFund = isFund ? "1" : "";
        stats.total += 1;
        stats.shared += isShared ? 1 : 0;
        stats.changes += isChange || isFund ? 1 : 0;
        stats.warnings += isWarning ? 1 : 0;
        stats.fund += isFund ? 1 : 0;
      }.bind(this)
    );
    return stats.hasDiff ? { rows: rows, stats: stats } : null;
  };

  Applet.prototype._applyDiffOverviewFilter = function (panel, table, rows, filter) {
    var hidden = 0;
    var visible = 0;
    rows.forEach(function (row) {
      var shared = row.dataset.nsmIpaDiffShared === "1";
      var change = row.dataset.nsmIpaDiffChange === "1";
      var warning = row.dataset.nsmIpaDiffWarning === "1";
      var fund = row.dataset.nsmIpaDiffFund === "1";
      var show = true;
      if (filter === "focus") {
        show = !shared || warning || fund;
      } else if (filter === "changes") {
        show = change || warning || fund;
      } else if (filter === "shared") {
        show = shared;
      } else if (filter === "warnings") {
        show = warning || fund;
      }
      row.classList.toggle("nsm-ipa-diff-filtered-row", !show);
      hidden += show ? 0 : 1;
      visible += show ? 1 : 0;
    });
    table.dataset.nsmIpaDiffFilter = filter;
    panel.querySelectorAll("[data-nsm-ipa-diff-filter]").forEach(function (btn) {
      var active = btn.getAttribute("data-nsm-ipa-diff-filter") === filter;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    var status = panel.querySelector(".nsm-ipa-diff-overview-status");
    if (status) {
      status.textContent = hidden
        ? ipaTf("%(hidden)s hidden, %(visible)s visible", {
            hidden: hidden,
            visible: visible,
          })
        : ipaT("All diff rows visible");
    }
  };

  Applet.prototype._initDiffOverviewForTable = function (table) {
    if (!table || table.parentElement.closest(".nsm-ipa-cell-tree-table")) {
      return;
    }
    var prepared = this._prepareDiffOverviewRows(table);
    if (!prepared) {
      return;
    }
    var stats = prepared.stats;
    var rows = prepared.rows;
    var defaultFilter =
      stats.shared >= 20 && (stats.changes > 0 || stats.warnings > 0 || stats.fund > 0)
        ? "focus"
        : "all";
    var panel = document.createElement("div");
    panel.className = "nsm-ipa-diff-overview";
    panel.setAttribute("role", "group");
    panel.setAttribute("aria-label", ipaT("Diff overview filters"));
    panel.innerHTML =
      '<div class="nsm-ipa-diff-overview-head">' +
        '<span class="nsm-ipa-diff-overview-title">' +
        escHtml(ipaT("Diff overview")) +
        "</span>" +
        '<span class="nsm-ipa-diff-overview-status"></span>' +
      "</div>" +
      '<div class="btn-group btn-group-sm nsm-ipa-diff-overview-actions" role="group">' +
        '<button type="button" class="btn btn-outline-secondary" data-nsm-ipa-diff-filter="focus">' +
        escHtml(ipaT("Focus")) +
        "</button>" +
        '<button type="button" class="btn btn-outline-secondary" data-nsm-ipa-diff-filter="changes">' +
        escHtml(ipaTf("Changes (%(count)s)", { count: stats.changes })) +
        "</button>" +
        '<button type="button" class="btn btn-outline-secondary" data-nsm-ipa-diff-filter="warnings">' +
        escHtml(ipaTf("Warnings (%(count)s)", { count: stats.warnings + stats.fund })) +
        "</button>" +
        '<button type="button" class="btn btn-outline-secondary" data-nsm-ipa-diff-filter="shared">' +
        escHtml(ipaTf("Shared (%(count)s)", { count: stats.shared })) +
        "</button>" +
        '<button type="button" class="btn btn-outline-secondary" data-nsm-ipa-diff-filter="all">' +
        escHtml(ipaT("All")) +
        "</button>" +
      "</div>";
    panel.addEventListener(
      "click",
      function (e) {
        var btn = e.target.closest("[data-nsm-ipa-diff-filter]");
        if (!btn) {
          return;
        }
        e.preventDefault();
        this._applyDiffOverviewFilter(
          panel,
          table,
          rows,
          btn.getAttribute("data-nsm-ipa-diff-filter") || "all"
        );
        this._scheduleBodyScale();
      }.bind(this)
    );
    table.parentNode.insertBefore(panel, table);
    this._applyDiffOverviewFilter(panel, table, rows, defaultFilter);
  };

  Applet.prototype._initDiffOverviewControls = function (root) {
    if (!root) {
      return;
    }
    root.querySelectorAll(".nsm-ipa-diff-overview").forEach(function (panel) {
      panel.remove();
    });
    root.querySelectorAll(".nsm-ipa-cell-tree-table").forEach(
      function (table) {
        this._initDiffOverviewForTable(table);
      }.bind(this)
    );
  };

  Applet.prototype._unobserveBodyContent = function () {
    if (this._bodyMutationObserver) {
      this._bodyMutationObserver.disconnect();
    }
  };

  Applet.prototype._onHeaderDown = function (e) {
    if (e.button !== 0 || e.target.closest("button")) {
      return;
    }
    var rect = this.el.getBoundingClientRect();
    this.dragState = {
      startX: e.clientX,
      startY: e.clientY,
      originLeft: rect.left,
      originTop: rect.top,
      moved: false,
    };
    document.addEventListener("mousemove", this._onMove);
    document.addEventListener("mouseup", this._onUp);
    e.preventDefault();
  };

  Applet.prototype._onMove = function (e) {
    if (!this.dragState) {
      return;
    }
    var dx = e.clientX - this.dragState.startX;
    var dy = e.clientY - this.dragState.startY;
    if (!this.dragState.moved && Math.abs(dx) + Math.abs(dy) < DRAG_THRESHOLD) {
      return;
    }
    this.dragState.moved = true;
    this.el.style.left = this.dragState.originLeft + dx + "px";
    this.el.style.top = this.dragState.originTop + dy + "px";
  };

  Applet.prototype._onUp = function () {
    document.removeEventListener("mousemove", this._onMove);
    document.removeEventListener("mouseup", this._onUp);
    this.dragState = null;
  };

  Applet.prototype._viewportMaxSize = function (left, top) {
    var vw = window.innerWidth || 1200;
    var vh = window.innerHeight || 800;
    return {
      width: Math.max(MIN_WIDTH, vw - left - VIEWPORT_MARGIN),
      height: Math.max(MIN_HEIGHT, vh - top - VIEWPORT_MARGIN),
    };
  };

  Applet.prototype._clampSize = function (width, height, left, top) {
    var max = this._viewportMaxSize(left, top);
    return {
      width: Math.max(MIN_WIDTH, Math.min(width, max.width)),
      height: Math.max(MIN_HEIGHT, Math.min(height, max.height)),
    };
  };

  Applet.prototype._applySize = function (width, height) {
    if (!this.el) {
      return;
    }
    var rect = this.el.getBoundingClientRect();
    var size = this._clampSize(width, height, rect.left, rect.top);
    this.el.style.width = size.width + "px";
    this.el.style.height = size.height + "px";
    this.el.style.maxHeight = "none";
    this.el.classList.add("nsm-ipa-applet--sized");
  };

  Applet.prototype._persistSize = function () {
    if (!this.el || this.minimized) {
      return;
    }
    try {
      var rect = this.el.getBoundingClientRect();
      sessionStorage.setItem(
        SIZE_STORAGE_KEY,
        JSON.stringify({
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        })
      );
    } catch (err) {
      /* sessionStorage unavailable */
    }
  };

  Applet.prototype._restoreSize = function () {
    if (!this.el) {
      return false;
    }
    try {
      var raw = sessionStorage.getItem(SIZE_STORAGE_KEY);
      if (!raw) {
        return false;
      }
      var saved = JSON.parse(raw);
      if (!saved || !saved.width || !saved.height) {
        return false;
      }
      this._applySize(saved.width, saved.height);
      return true;
    } catch (err) {
      return false;
    }
  };

  Applet.prototype._onResizeDown = function (e) {
    if (e.button !== 0 || this.minimized) {
      return;
    }
    var handle = e.currentTarget;
    var direction = handle.getAttribute("data-resize") || "se";
    var rect = this.el.getBoundingClientRect();
    this.el.style.width = rect.width + "px";
    this.el.style.height = rect.height + "px";
    this.el.style.maxHeight = "none";
    this.el.classList.add("nsm-ipa-applet--sized", "nsm-ipa-applet--resizing");
    this.resizeState = {
      direction: direction,
      startX: e.clientX,
      startY: e.clientY,
      originWidth: rect.width,
      originHeight: rect.height,
      originLeft: rect.left,
      originTop: rect.top,
    };
    document.addEventListener("mousemove", this._onResizeMove);
    document.addEventListener("mouseup", this._onResizeUp);
    e.preventDefault();
    e.stopPropagation();
  };

  Applet.prototype._onResizeMove = function (e) {
    if (!this.resizeState) {
      return;
    }
    var dx = e.clientX - this.resizeState.startX;
    var dy = e.clientY - this.resizeState.startY;
    var dir = this.resizeState.direction;
    var width = this.resizeState.originWidth;
    var height = this.resizeState.originHeight;
    var left = this.resizeState.originLeft;
    var top = this.resizeState.originTop;

    if (dir.indexOf("e") !== -1) {
      width = this.resizeState.originWidth + dx;
    }
    if (dir.indexOf("w") !== -1) {
      width = this.resizeState.originWidth - dx;
      left = this.resizeState.originLeft + dx;
    }
    if (dir.indexOf("s") !== -1) {
      height = this.resizeState.originHeight + dy;
    }
    if (dir.indexOf("n") !== -1) {
      height = this.resizeState.originHeight - dy;
      top = this.resizeState.originTop + dy;
    }

    var size = this._clampSize(width, height, left, top);

    if (dir.indexOf("n") !== -1) {
      top = this.resizeState.originTop + (this.resizeState.originHeight - size.height);
    }
    if (dir.indexOf("w") !== -1) {
      left = this.resizeState.originLeft + (this.resizeState.originWidth - size.width);
    }

    top = Math.max(VIEWPORT_MARGIN, top);
    left = Math.max(VIEWPORT_MARGIN, left);

    this.el.style.left = left + "px";
    this.el.style.top = top + "px";
    this.el.style.width = size.width + "px";
    this.el.style.height = size.height + "px";
  };

  Applet.prototype._onResizeUp = function () {
    document.removeEventListener("mousemove", this._onResizeMove);
    document.removeEventListener("mouseup", this._onResizeUp);
    if (this.el) {
      this.el.classList.remove("nsm-ipa-applet--resizing");
    }
    if (this.resizeState) {
      this._persistSize();
    }
    this.resizeState = null;
    this._scheduleBodyScale();
  };

  Applet.prototype._onTabListClick = function (e) {
    var closeBtn = e.target.closest(".nsm-ipa-applet-tab-close");
    if (closeBtn) {
      e.preventDefault();
      e.stopPropagation();
      var tabBtn = closeBtn.closest(".nsm-ipa-applet-tab");
      if (tabBtn && tabBtn.dataset.tabId) {
        this.closeTab(Number(tabBtn.dataset.tabId));
      }
      return;
    }
    var tabBtn = e.target.closest(".nsm-ipa-applet-tab");
    if (tabBtn && tabBtn.dataset.tabId) {
      e.preventDefault();
      this.activateTab(Number(tabBtn.dataset.tabId));
    }
  };

  Applet.prototype.findTabByObjects = function (objects, context) {
    var key = tabDedupKey(objects, context);
    for (var i = 0; i < this.tabs.length; i++) {
      if (this.tabs[i].objectsKey === key) {
        return this.tabs[i];
      }
    }
    return null;
  };

  Applet.prototype.getActiveTab = function () {
    for (var i = 0; i < this.tabs.length; i++) {
      if (this.tabs[i].id === this.activeTabId) {
        return this.tabs[i];
      }
    }
    return null;
  };

  Applet.prototype.setRuleBadge = function () {
    if (!this.ruleBadgeEl) {
      return;
    }
    var tab = this.getActiveTab();
    var label = tab && tab.context ? rulesCellPositionTag(tab.context) : "";
    if (!label) {
      this.ruleBadgeEl.hidden = true;
      this.ruleBadgeEl.textContent = "";
      return;
    }
    this.ruleBadgeEl.hidden = false;
    this.ruleBadgeEl.textContent = label;
  };

  Applet.prototype.setWindowTitle = function () {
    if (!this.titleEl) {
      return;
    }
    var tab = this.getActiveTab();
    if (!tab) {
      this.titleEl.textContent = ipaT("IP Analysis");
      this.setRuleBadge();
      return;
    }
    if (tab.mode === "diff") {
      this.titleEl.textContent = tab.title;
      this.setRuleBadge();
      return;
    }
    if (this.tabs.length > 1) {
      this.titleEl.textContent = ipaTf("IP Analysis (%(count)s)", {
        count: this.tabs.length,
      });
      this.setRuleBadge();
      return;
    }
    this.titleEl.textContent = tab.title;
    this.setRuleBadge();
  };

  Applet.prototype.renderToolbar = function () {
    if (!this.toolbarEl) {
      return;
    }
    var showToolbar = this.tabs.length >= 1 && this.el && !this.el.hidden;
    this.toolbarEl.hidden = !showToolbar;
    this.el.classList.toggle("nsm-ipa-applet--has-toolbar", showToolbar);

    if (this.mergeBtnEl) {
      var mergeSourceCount = this.tabs.filter(function (tab) {
        return tab.mode !== "diff" && tab.mode !== "merge";
      }).length;
      var canMerge = mergeSourceCount > 1;
      this.mergeBtnEl.disabled = !canMerge || this._merging || this._diffing || this._exporting;
    }
    if (this.diffBtnEl) {
      var diffSourceCount = this.tabs.filter(function (tab) {
        return tab.mode !== "diff";
      }).length;
      var canDiff = diffSourceCount >= 2;
      this.diffBtnEl.disabled = !canDiff || this._merging || this._diffing || this._exporting;
      var diffDisabledLabel = ipaT("Diff (at least 2 tabs required)");
      this.diffBtnEl.title = canDiff ? ipaT("Diff") : diffDisabledLabel;
      this.diffBtnEl.setAttribute(
        "aria-label",
        canDiff ? ipaT("Diff") : diffDisabledLabel
      );
    }
    if (this.exportBtnEl) {
      var activeTab = this.getActiveTab();
      var canExport =
        activeTab &&
        activeTab.status === "ready" &&
        !this._merging &&
        !this._diffing &&
        !this._exporting;
      this.exportBtnEl.disabled = !canExport;
      this.exportBtnEl.classList.toggle("disabled", !canExport);
      var exportLabel = this._exporting
        ? ipaT("Exporting…")
        : ipaT("Export displayed data and IPAM children (YAML)");
      this.exportBtnEl.title = exportLabel;
      this.exportBtnEl.setAttribute("aria-label", exportLabel);
    }
  };

  Applet.prototype.exportYaml = function () {
    var tab = this.getActiveTab();
    if (!tab || tab.status !== "ready" || this._exporting) {
      return;
    }
    this._exporting = true;
    this.renderToolbar();

    var url = apiUrl() + "?" + buildExportQuery(tab);
    var self = this;
    nsmFetch(url, {
      headers: mergeBranchHeaders({ "X-Requested-With": "XMLHttpRequest" }),
    })
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error("HTTP " + resp.status);
        }
        var filename = parseContentDispositionFilename(
          resp.headers.get("Content-Disposition")
        );
        return resp.blob().then(function (blob) {
          return { blob: blob, filename: filename };
        });
      })
      .then(function (result) {
        triggerBlobDownload(result.blob, result.filename || "ipa-export.yaml");
      })
      .catch(function () {
        window.alert(ipaT("YAML export failed."));
      })
      .finally(function () {
        self._exporting = false;
        self.renderToolbar();
      });
  };

  Applet.prototype.renderTabs = function () {
    if (!this.tabListEl || !this.tabsEl) {
      return;
    }
    this.renderToolbar();
    var showTabs = this.tabs.length > 1;
    this.tabsEl.hidden = !showTabs;
    this.el.classList.toggle("nsm-ipa-applet--has-tabs", showTabs);
    if (!showTabs) {
      this.tabListEl.innerHTML = "";
      return;
    }

    var html = "";
    this.tabs.forEach(
      function (tab) {
        var active = tab.id === this.activeTabId;
        var label = truncateTitle(tab.title);
        html +=
          '<button type="button" class="nsm-ipa-applet-tab' +
          (active ? " nsm-ipa-applet-tab--active" : "") +
          '" role="tab" aria-selected="' +
          (active ? "true" : "false") +
          '" data-tab-id="' +
          tab.id +
          '" title="' +
          escHtml(tab.title) +
          '">' +
          '<span class="nsm-ipa-applet-tab-label">' +
          escHtml(label) +
          "</span>" +
          '<span class="nsm-ipa-applet-tab-close" role="button" tabindex="-1" aria-label="' +
          escHtml(ipaT("Close tab")) +
          '" title="' +
          escHtml(ipaT("Close")) +
          '">&times;</span>' +
          "</button>";
      }.bind(this)
    );
    this.tabListEl.innerHTML = html;
  };

  Applet.prototype._loadAddObjectCategories = function () {
    if (this._addObjectCategories) {
      return Promise.resolve(this._addObjectCategories);
    }
    var self = this;
    return nsmFetch(addObjectTypesApiUrl(), {
      headers: mergeBranchHeaders({
        "X-Requested-With": "XMLHttpRequest",
        Accept: "application/json",
      }),
    })
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error("HTTP " + resp.status);
        }
        return resp.json();
      })
      .then(function (data) {
        self._addObjectCategories = data.categories || [];
        return self._addObjectCategories;
      })
      .catch(function () {
        self._addObjectCategories = [];
        return self._addObjectCategories;
      });
  };

  Applet.prototype._renderAddObjectMenu = function (categories) {
    if (!this.addObjectMenuEl) {
      return;
    }
    if (!categories.length) {
      this.addObjectMenuEl.innerHTML =
        '<li><span class="dropdown-item-text text-muted small">' +
        escHtml(ipaT("No object types available")) +
        "</span></li>";
      return;
    }
    var html = "";
    categories.forEach(function (cat) {
      html +=
        '<li><button type="button" class="dropdown-item nsm-ipa-applet-add-object-kind" data-add-category="' +
        escHtml(cat.id) +
        '">' +
        escHtml(cat.label) +
        "</button></li>";
    });
    this.addObjectMenuEl.innerHTML = html;
  };

  Applet.prototype._closeAddObjectModal = function () {
    if (!this.addObjectModalEl) {
      return;
    }
    this._addObjectSearchToken += 1;
    if (this._addObjectSearchCtrl) {
      this._addObjectSearchCtrl.abort();
      this._addObjectSearchCtrl = null;
    }
    this._addObjectCategory = null;
    this.addObjectModalEl.hidden = true;
    if (this.addObjectSearchEl) {
      this.addObjectSearchEl.value = "";
    }
    if (this.addObjectResultsEl) {
      this.addObjectResultsEl.innerHTML = "";
    }
  };

  Applet.prototype._openAddObjectModal = function (category) {
    var self = this;
    if (!category || !this.addObjectModalEl) {
      return;
    }
    this._addObjectCategory = category;
    this.addObjectModalEl.hidden = false;
    if (this.addObjectTitleEl) {
      this.addObjectTitleEl.textContent = ipaTf("Add object — %(category)s", {
        category: category.label,
      });
    }
    if (this.addObjectResultsEl) {
      this.addObjectResultsEl.innerHTML =
        '<div class="nsm-ipa-applet-add-msg">' +
        escHtml(ipaT("Enter search term…")) +
        "</div>";
    }
    if (this.addObjectSearchEl) {
      this.addObjectSearchEl.value = "";
      window.setTimeout(function () {
        self.addObjectSearchEl.focus();
      }, 0);
    }
  };

  Applet.prototype._renderAddObjectResults = function (items, message) {
    if (!this.addObjectResultsEl) {
      return;
    }
    items = items || [];
    if (message && !items.length) {
      this.addObjectResultsEl.innerHTML =
        '<div class="nsm-ipa-applet-add-msg">' + escHtml(message) + "</div>";
      return;
    }
    if (!items.length) {
      this.addObjectResultsEl.innerHTML =
        '<div class="nsm-ipa-applet-add-msg">' +
        escHtml(ipaT("No matches")) +
        "</div>";
      return;
    }
    var html = "";
    items.forEach(function (item) {
      html +=
        '<button type="button" class="nsm-ipa-applet-add-result" data-ct="' +
        escHtml(item.ct) +
        '" data-pk="' +
        escHtml(item.pk) +
        '" data-name="' +
        escHtml(item.name) +
        '">' +
        '<span class="text-truncate">' +
        escHtml(item.name) +
        "</span>" +
        '<span class="nsm-ipa-applet-add-result-type">' +
        escHtml(item.type) +
        "</span></button>";
    });
    this.addObjectResultsEl.innerHTML = html;
  };

  Applet.prototype._searchAddObject = function (query) {
    var category = this._addObjectCategory;
    if (!category || !query.trim()) {
      this._renderAddObjectResults([], ipaT("Enter search term…"));
      return;
    }
    if (this._addObjectSearchCtrl) {
      this._addObjectSearchCtrl.abort();
    }
    this._addObjectSearchCtrl = new AbortController();
    var token = ++this._addObjectSearchToken;
    var signal = this._addObjectSearchCtrl.signal;
    this._renderAddObjectResults([], ipaT("Searching…"));

    var fetches = (category.types || []).map(function (typeEntry) {
      var url =
        typeEntry.api_url +
        "?q=" +
        encodeURIComponent(query.trim()) +
        "&limit=20&brief=1";
      return nsmFetch(url, {
        signal: signal,
        headers: mergeBranchHeaders({
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": getCsrfToken(),
        }),
      })
        .then(function (resp) {
          return resp.ok ? resp.json() : { results: [] };
        })
        .then(function (data) {
          return (data.results || []).map(function (obj) {
            return {
              ct: String(typeEntry.ct_id),
              pk: String(obj.id),
              name: obj.display || obj.name || String(obj.id),
              type: typeEntry.name,
            };
          });
        })
        .catch(function (err) {
          if (err && err.name === "AbortError") {
            return [];
          }
          return [];
        });
    });

    var self = this;
    Promise.all(fetches).then(function (all) {
      if (token !== self._addObjectSearchToken) {
        return;
      }
      self._renderAddObjectResults([].concat.apply([], all));
    });
  };

  Applet.prototype._pickAddObject = function (ct, pk, name) {
    if (!ct || !pk) {
      return;
    }
    this._closeAddObjectModal();
    this.open({
      objects: [{ ct: String(ct), pk: String(pk), name: name || "" }],
    });
  };

  Applet.prototype._bindAddObjectHandlers = function () {
    var self = this;
    this._debouncedAddObjectSearch = debounce(function (query) {
      self._searchAddObject(query);
    }, 250);

    if (this.addObjectMenuEl) {
      this.addObjectMenuEl.addEventListener("click", function (e) {
        var btn = e.target.closest(".nsm-ipa-applet-add-object-kind");
        if (!btn) {
          return;
        }
        e.preventDefault();
        var categoryId = btn.getAttribute("data-add-category");
        self._loadAddObjectCategories().then(function (categories) {
          var category = categories.find(function (cat) {
            return cat.id === categoryId;
          });
          if (category) {
            self._openAddObjectModal(category);
          }
        });
      });
    }

    if (this.addObjectSearchEl) {
      this.addObjectSearchEl.addEventListener("input", function () {
        self._debouncedAddObjectSearch(self.addObjectSearchEl.value);
      });
      this.addObjectSearchEl.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
          e.preventDefault();
          self._closeAddObjectModal();
        }
        if (e.key === "Enter") {
          e.preventDefault();
          var first =
            self.addObjectResultsEl &&
            self.addObjectResultsEl.querySelector(".nsm-ipa-applet-add-result");
          if (first) {
            first.click();
          }
        }
      });
    }

    if (this.addObjectResultsEl) {
      this.addObjectResultsEl.addEventListener("click", function (e) {
        var btn = e.target.closest(".nsm-ipa-applet-add-result");
        if (!btn) {
          return;
        }
        e.preventDefault();
        self._pickAddObject(
          btn.getAttribute("data-ct"),
          btn.getAttribute("data-pk"),
          btn.getAttribute("data-name")
        );
      });
    }

    if (this.addObjectModalEl) {
      this.addObjectModalEl.addEventListener("click", function (e) {
        if (e.target === self.addObjectModalEl) {
          self._closeAddObjectModal();
        }
      });
      var closeBtn = this.addObjectModalEl.querySelector(
        ".nsm-ipa-applet-add-modal-close"
      );
      if (closeBtn) {
        closeBtn.addEventListener("click", function (e) {
          e.preventDefault();
          self._closeAddObjectModal();
        });
      }
    }

    this._loadAddObjectCategories().then(function (categories) {
      self._renderAddObjectMenu(categories);
    });
  };

  Applet.prototype.diffTabs = function () {
    var sourceTabs = this.tabs.filter(function (tab) {
      return tab.mode !== "diff";
    });
    if (sourceTabs.length < 2 || this._diffing) {
      return;
    }

    var hasObjects = sourceTabs.some(function (tab) {
      return (tab.objects || []).length > 0;
    });
    if (!hasObjects) {
      return;
    }

    var sides = sourceTabs.map(function (tab) {
      return {
        title: tab.title,
        diffLabel: diffSideLabel(tab),
        context: tab.context || null,
        objects: normalizeObjects(tab.objects),
      };
    });
    var diffKey = diffObjectsKey(sides);
    for (var i = 0; i < this.tabs.length; i++) {
      if (this.tabs[i].mode === "diff" && this.tabs[i].objectsKey === diffKey) {
        this.showWindow();
        this.activateTab(this.tabs[i].id);
        return;
      }
    }

    this._diffing = true;
    this.renderTabs();

    var diffTab = {
      id: this.nextTabId++,
      title: diffTabTitleFromTabs(sourceTabs),
      contextLabel: diffTabContextLabel(sourceTabs),
      mode: "diff",
      sides: sides,
      objectsKey: diffKey,
      status: "loading",
      html: "",
      message: "",
      error: "",
      leafCount: 0,
      unsupportedCount: 0,
      diffSummary: null,
      loadToken: 0,
      _loading: false,
    };

    this.tabs.push(diffTab);
    this.activeTabId = diffTab.id;
    this._diffing = false;

    this.showWindow();
    this.renderTabs();
    this.setWindowTitle();
    this.renderActiveContent();
    this.loadTab(diffTab);
  };

  Applet.prototype.mergeTabs = function () {
    // Source tabs are the original cell/rule tabs only; previously created
    // merge or diff result tabs are excluded so merge always operates on the
    // leaf selections (mirrors the diff source filter).
    var mergeSourceTabs = this.tabs.filter(function (tab) {
      return tab.mode !== "diff" && tab.mode !== "merge";
    });
    if (mergeSourceTabs.length < 2 || this._merging) {
      return;
    }

    var mergedObjects = collectObjectsFromTabs(mergeSourceTabs);
    if (!mergedObjects.length) {
      return;
    }

    // Reuse an existing merge tab for the same object set instead of stacking
    // duplicates (same dedup contract as diffTabs).
    var mergeKey = objectsKey(mergedObjects);
    for (var i = 0; i < this.tabs.length; i++) {
      if (this.tabs[i].mode === "merge" && this.tabs[i].objectsKey === mergeKey) {
        this.showWindow();
        this.activateTab(this.tabs[i].id);
        return;
      }
    }

    this._merging = true;
    this.renderTabs();

    var mergedTab = {
      id: this.nextTabId++,
      title: mergedTabTitle(mergedObjects.length),
      mode: "merge",
      objects: mergedObjects,
      rawObjects: mergedObjects,
      objectsKey: mergeKey,
      status: "loading",
      html: "",
      message: "",
      error: "",
      leafCount: 0,
      unsupportedCount: 0,
      loadToken: 0,
      _loading: false,
    };

    // Append as a new tab; existing tabs are preserved.
    this.tabs.push(mergedTab);
    this.activeTabId = mergedTab.id;
    this._merging = false;

    this.showWindow();
    this.renderTabs();
    this.setWindowTitle();
    this.renderActiveContent();
    this.loadTab(mergedTab);
  };

  Applet.prototype.renderActiveContent = function () {
    var tab = this.getActiveTab();
    if (!tab || !this.bodyEl || !this.footerEl) {
      return;
    }

    var statusEl = this.footerEl.querySelector(".nsm-ipa-applet-status");
    var countEl = this.footerEl.querySelector(".nsm-ipa-applet-count");

    this._unobserveBodyContent();
    if (tab.status === "loading") {
      this.bodyEl.innerHTML = loadingHtml();
      statusEl.textContent = "";
      countEl.textContent = "";
      return;
    }
    if (tab.status === "error") {
      this.bodyEl.innerHTML = errorHtml(tab.error);
      statusEl.textContent = "";
      countEl.textContent = "";
      return;
    }
    var contextBanner = "";
    if (tab.contextLabel) {
      contextBanner =
        '<div class="nsm-ipa-applet-context">' +
        escHtml(tab.contextLabel) +
        "</div>";
    }
    if (tab.message && !tab.html) {
      this.bodyEl.innerHTML =
        contextBanner +
        '<div class="nsm-ipa-applet-empty">' +
        escHtml(tab.message) +
        "</div>";
    } else if (tab.html) {
      this.bodyEl.innerHTML = contextBanner + this._wrapBodyContent(tab.html);
      if (window.nsmIpaStripLegacyExpandedWarnings) {
        window.nsmIpaStripLegacyExpandedWarnings(this.bodyEl);
      }
      if (window.nsmInitAddrPrefixToggle) {
        window.nsmInitAddrPrefixToggle(this.bodyEl);
      }
      this._initDiffOverviewControls(this.bodyEl);
      this._observeBodyContent();
      this._scheduleBodyScale();
    } else {
      this.bodyEl.innerHTML =
        contextBanner +
        '<div class="nsm-ipa-applet-empty">' +
        escHtml(ipaT("No IP addresses resolved.")) +
        "</div>";
    }
    if (tab.mode === "diff" && tab.diffSummary) {
      countEl.textContent = formatDiffSummary(tab.diffSummary);
    } else {
      countEl.textContent = formatTypeCountSummary(tab);
    }
    statusEl.textContent = tab.unsupportedCount
      ? ipaTf("%(count)s skipped", { count: tab.unsupportedCount })
      : "";
  };

  Applet.prototype._resumeStaleTabLoad = function (tab) {
    if (tab && tab.status === "loading" && !tab._loading) {
      this.loadTab(tab);
    }
  };

  Applet.prototype._applyTabAnalysisPayload = function (tab, data) {
    tab.status = "ready";
    tab.error = "";
    tab.html = data.html || "";
    tab.message = data.message || "";
    tab.leafCount = data.leaf_count || 0;
    tab.countSubnets = data.count_subnets != null ? data.count_subnets : null;
    tab.countRanges = data.count_ranges != null ? data.count_ranges : null;
    tab.countIps = data.count_ips != null ? data.count_ips : null;
    tab.countDuplicates =
      data.count_duplicates != null ? data.count_duplicates : null;
    tab.countGroupDuplicates =
      data.count_group_duplicates != null ? data.count_group_duplicates : null;
    tab.diffSummary = data.diff_summary || null;
    tab.unsupportedCount =
      data.unsupported && data.unsupported.length ? data.unsupported.length : 0;
  };

  Applet.prototype._failTabLoad = function (tab, token, message) {
    tab._loading = false;
    if (token !== tab.loadToken) {
      return;
    }
    if (!this.tabs.some(function (t) { return t.id === tab.id; })) {
      return;
    }
    tab.status = "error";
    tab.error = message || ipaT("Analysis could not be loaded.");
    if (tab.id === this.activeTabId) {
      this.renderActiveContent();
      this.renderToolbar();
    }
  };

  Applet.prototype._completeTabLoad = function (tab, token, data) {
    tab._loading = false;
    if (token !== tab.loadToken) {
      return;
    }
    if (!this.tabs.some(function (t) { return t.id === tab.id; })) {
      return;
    }
    this._applyTabAnalysisPayload(tab, data);
    if (tab.id === this.activeTabId) {
      this.renderActiveContent();
      this.renderToolbar();
    }
  };

  Applet.prototype.loadTab = function (tab) {
    if (!tab) {
      return;
    }
    if (tab.status === "ready" || tab.status === "error") {
      return;
    }
    if (tab._loading) {
      return;
    }
    tab.status = "loading";
    tab.error = "";
    tab._loading = true;
    tab.loadToken = (tab.loadToken || 0) + 1;
    var token = tab.loadToken;
    var self = this;

    if (tab.id === this.activeTabId) {
      this.renderActiveContent();
    }

    var url =
      tab.mode === "diff"
        ? apiUrl() + "?" + buildDiffQuery(tab.sides || [])
        : apiUrl() + "?" + buildQuery(tab.objects, tab.rawObjects);
    fetchIpaAnalysis(url, {
      headers: mergeBranchHeaders({ "X-Requested-With": "XMLHttpRequest" }),
    })
      .then(function (resp) {
        return readIpaApiJson(resp);
      })
      .then(function (data) {
        self._completeTabLoad(tab, token, data);
      })
      .catch(function (err) {
        self._failTabLoad(tab, token, ipaFetchAbortMessage(err));
      });
  };

  Applet.prototype.activateTab = function (tabId) {
    var found = false;
    for (var i = 0; i < this.tabs.length; i++) {
      if (this.tabs[i].id === tabId) {
        found = true;
        break;
      }
    }
    if (!found) {
      return;
    }
    this.activeTabId = tabId;
    this.renderTabs();
    this.setWindowTitle();
    var tab = this.getActiveTab();
    if (tab && tab.status === "loading" && !tab._loading) {
      this.loadTab(tab);
    } else {
      this.renderActiveContent();
    }
  };

  Applet.prototype.closeTab = function (tabId) {
    var idx = -1;
    for (var i = 0; i < this.tabs.length; i++) {
      if (this.tabs[i].id === tabId) {
        idx = i;
        break;
      }
    }
    if (idx < 0) {
      return;
    }
    var tab = this.tabs[idx];
    tab.loadToken = (tab.loadToken || 0) + 1;
    this.tabs.splice(idx, 1);

    if (!this.tabs.length) {
      this.destroyAllTabs();
      return;
    }

    if (this.activeTabId === tabId) {
      var next = this.tabs[Math.min(idx, this.tabs.length - 1)];
      this.activeTabId = next.id;
    }
    this.renderTabs();
    this.setWindowTitle();
    this.renderActiveContent();
  };

  Applet.prototype.showWindow = function () {
    this.minimized = false;
    this.el.classList.remove("nsm-ipa-applet--minimized");
    this.el.hidden = false;
    this.el.style.visibility = "hidden";
    defaultPosition(this.el);
    if (!this._restoreSize()) {
      this.el.classList.remove("nsm-ipa-applet--sized");
      this.el.style.width = "";
      this.el.style.height = "";
      this.el.style.maxHeight = "";
    }
    this.el.style.visibility = "";
    this._resumeStaleTabLoad(this.getActiveTab());
  };

  Applet.prototype.open = function (opts) {
    opts = opts || {};
    var rawObjects = collectRawObjects(opts.objects);
    var objects = normalizeObjects(opts.objects);
    if (!objects.length) {
      return;
    }

    this.ensureDom();

    var context = opts.context || null;
    var existing = this.findTabByObjects(objects, context);
    if (existing) {
      this.showWindow();
      this.activateTab(existing.id);
      return;
    }

    var tab = {
      id: this.nextTabId++,
      title: tabTitle(objects, opts.title, context),
      context: context,
      contextLabel: rulesCellContextLabel(context),
      objects: objects,
      rawObjects: rawObjects,
      objectsKey: tabDedupKey(objects, context),
      status: "loading",
      html: "",
      message: "",
      error: "",
      leafCount: 0,
      unsupportedCount: 0,
      loadToken: 0,
      _loading: false,
    };
    this.tabs.push(tab);
    this.activeTabId = tab.id;

    this.showWindow();
    this.renderTabs();
    this.setWindowTitle();
    this.renderActiveContent();
    this.loadTab(tab);
  };

  Applet.prototype.destroyAllTabs = function () {
    this._closeAddObjectModal();
    this.tabs.forEach(function (tab) {
      tab.loadToken = (tab.loadToken || 0) + 1;
    });
    this.tabs = [];
    this.activeTabId = null;
    if (this.el) {
      this.el.hidden = true;
      this.renderTabs();
      this.setWindowTitle();
    }
  };

  Applet.prototype.close = function () {
    this._closeAddObjectModal();
    this.tabs.forEach(function (tab) {
      tab.loadToken = (tab.loadToken || 0) + 1;
    });
    if (this.el) {
      this.el.hidden = true;
    }
  };

  Applet.prototype.toggleMinimize = function () {
    if (!this.el) {
      return;
    }
    if (this.resizeState) {
      this._onResizeUp();
    }
    this.minimized = !this.minimized;
    this.el.classList.toggle("nsm-ipa-applet--minimized", this.minimized);
    if (this.minimized) {
      this.el.style.height = "";
      this.el.style.maxHeight = "";
    } else if (this.el.classList.contains("nsm-ipa-applet--sized")) {
      this._restoreSize();
    }
    this._scheduleBodyScale();
  };

  var singleton = new Applet();

  window.NsmIpAnalyzerApplet = {
    open: function (opts) {
      singleton.open(opts);
    },
    close: function () {
      singleton.close();
    },
    scheduleBodyScale: function () {
      singleton._scheduleBodyScale();
    },
    createLoupeButton: createLoupeButton,
  };

  if (window.NsmIpaCell && window.NsmIpaCell.bindGlobalHandlers) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () {
        window.NsmIpaCell.bindGlobalHandlers(singleton);
      });
    } else {
      window.NsmIpaCell.bindGlobalHandlers(singleton);
    }
  }
})();
