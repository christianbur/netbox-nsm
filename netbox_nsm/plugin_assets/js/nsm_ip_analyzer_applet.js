/**
 * Floating draggable IP Analyzer popup for NSM.
 * window.NsmIpAnalyzerApplet.open({ objects: [{ ct, pk, name }], title?: string })
 */
(function () {
  "use strict";

  var ROOT_ID = "nsm-ipa-applet-root";
  var DRAG_THRESHOLD = 4;
  var TAB_TITLE_MAX = 28;
  var MIN_WIDTH = 320;
  var MIN_HEIGHT = 240;
  var VIEWPORT_MARGIN = 12;
  var SIZE_STORAGE_KEY = "nsm-ipa-applet-size";
  var MIN_BODY_SCALE = 0.55;

  function escHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function formatTypeCountSummary(tab) {
    if (!tab) {
      return "";
    }
    if (
      tab.countSubnets != null ||
      tab.countRanges != null ||
      tab.countIps != null
    ) {
      var parts = [
        "Subnets: " + (tab.countSubnets || 0),
        "Ranges: " + (tab.countRanges || 0),
        "IPs: " + (tab.countIps != null ? tab.countIps : tab.leafCount || 0),
      ];
      if (tab.countDuplicates) {
        parts.push("Warnings: " + tab.countDuplicates);
      }
      return parts.join("  ");
    }
    return tab.leafCount ? "IPs: " + tab.leafCount : "";
  }

  function apiUrl() {
    return window.NSM_IP_ANALYSIS_API || "/plugins/netbox-nsm/api/ip-analysis/";
  }

  function addObjectTypesApiUrl() {
    return (
      window.NSM_IP_ANALYSIS_ADD_OBJECT_TYPES_API ||
      "/plugins/netbox-nsm/api/ip-analysis/add-object-types/"
    );
  }

  function debounce(fn, ms) {
    var timer;
    return function () {
      var args = arguments;
      var ctx = this;
      clearTimeout(timer);
      timer = setTimeout(function () {
        fn.apply(ctx, args);
      }, ms);
    };
  }

  function getCsrfToken() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function nsmFetch(url, options) {
    if (window.NSM_BRANCH_API && window.NSM_BRANCH_API.fetch) {
      return window.NSM_BRANCH_API.fetch(url, options);
    }
    return fetch(url, options);
  }

  function mergeBranchHeaders(headers) {
    if (window.NSM_BRANCH_API && window.NSM_BRANCH_API.mergeBranchHeaders) {
      return window.NSM_BRANCH_API.mergeBranchHeaders(headers || {});
    }
    return headers || {};
  }

  function normalizeObjects(objects) {
    var out = [];
    var seen = {};
    (objects || []).forEach(function (obj) {
      if (!obj) {
        return;
      }
      var ct = obj.ct != null ? String(obj.ct) : "";
      var pk = obj.pk != null ? String(obj.pk) : "";
      if (!ct || !pk) {
        return;
      }
      var key = ct + ":" + pk;
      if (seen[key]) {
        return;
      }
      seen[key] = true;
      out.push({
        ct: ct,
        pk: pk,
        name: obj.name != null ? String(obj.name) : "",
      });
    });
    return out;
  }

  function collectRawObjects(objects) {
    var out = [];
    (objects || []).forEach(function (obj) {
      if (!obj) {
        return;
      }
      var ct = obj.ct != null ? String(obj.ct) : "";
      var pk = obj.pk != null ? String(obj.pk) : "";
      if (!ct || !pk) {
        return;
      }
      out.push({
        ct: ct,
        pk: pk,
        name: obj.name != null ? String(obj.name) : "",
      });
    });
    return out;
  }

  function objectsKey(objects) {
    return objects
      .map(function (obj) {
        return obj.ct + ":" + obj.pk;
      })
      .sort()
      .join("|");
  }

  function tabDedupKey(objects, context) {
    var base = objectsKey(objects);
    if (!context) {
      return base;
    }
    var ruleIndex = context.ruleIndex;
    var colPosition = context.colPosition;
    if (ruleIndex != null && ruleIndex !== "" && colPosition) {
      return base + "|" + ruleIndex + "/" + colPosition;
    }
    return base;
  }

  function rulesCellTabTitle(context) {
    if (!context) {
      return null;
    }
    var ruleIndex = context.ruleIndex;
    var colPosition = context.colPosition;
    if (ruleIndex == null || ruleIndex === "" || !colPosition) {
      return null;
    }
    return "Rule " + ruleIndex + "/" + colPosition;
  }

  function rulesCellContextLabel(context) {
    if (!context) {
      return "";
    }
    var ruleIndex = context.ruleIndex;
    if (ruleIndex == null || ruleIndex === "") {
      return "";
    }
    var ruleName = context.ruleName || "";
    var colPart = context.colId || context.colPosition || "";
    if (ruleName) {
      return ruleName + " (" + ruleIndex + ") / " + colPart;
    }
    return "Regel " + ruleIndex + " / " + colPart;
  }

  function rulesCellDiffSideLabel(context) {
    if (!context) {
      return "";
    }
    var ruleIndex = context.ruleIndex;
    if (ruleIndex == null || ruleIndex === "") {
      return "";
    }
    var ruleName = context.ruleName || "";
    var colPart = context.colId || context.colPosition || "";
    if (ruleName && colPart) {
      return ruleName + " (" + ruleIndex + ") / " + colPart;
    }
    if (ruleName) {
      return ruleName + " (" + ruleIndex + ")";
    }
    if (colPart) {
      return "Rule " + ruleIndex + " / " + colPart;
    }
    var colPosition = context.colPosition;
    if (colPosition) {
      return "Rule " + ruleIndex + "/" + colPosition;
    }
    return "";
  }

  function diffSideLabel(tab) {
    if (!tab) {
      return "";
    }
    return (
      rulesCellDiffSideLabel(tab.context) ||
      tab.contextLabel ||
      tab.title ||
      ""
    );
  }

  function diffTabContextLabel(tabs) {
    if (!tabs || !tabs.length) {
      return "";
    }
    var firstLabel = rulesCellContextLabel(tabs[0].context);
    if (!firstLabel) {
      return "";
    }
    for (var i = 1; i < tabs.length; i++) {
      if (rulesCellContextLabel(tabs[i].context) !== firstLabel) {
        return "";
      }
    }
    return firstLabel;
  }

  function tabTitle(objects, customTitle, context) {
    if (customTitle) {
      return String(customTitle);
    }
    var rulesTitle = rulesCellTabTitle(context);
    if (rulesTitle) {
      return rulesTitle;
    }
    if (!objects.length) {
      return "IP-Analyse";
    }
    if (objects.length === 1) {
      return objects[0].name || "IP-Analyse";
    }
    return objects.length + " Objekte";
  }

  function mergedTabTitle(objectCount) {
    return "Merged (" + objectCount + " Objekte)";
  }

  function diffTabTitleFromTabs(tabs) {
    if (!tabs || !tabs.length) {
      return "Diff";
    }
    if (tabs.length === 2) {
      var a = truncateTitle(diffSideLabel(tabs[0]) || tabs[0].title || "A");
      var b = truncateTitle(diffSideLabel(tabs[1]) || tabs[1].title || "B");
      return "Diff (" + a + " ↔ " + b + ")";
    }
    if (tabs.length <= 4) {
      var labels = tabs.map(function (tab) {
        return truncateTitle(diffSideLabel(tab) || tab.title || "");
      });
      return "Diff (" + labels.join(" ↔ ") + ")";
    }
    return "Diff (" + tabs.length + " Tabs)";
  }

  function diffObjectsKey(sides) {
    return (
      "diff:" +
      (sides || [])
        .map(function (side) {
          return objectsKey((side && side.objects) || []);
        })
        .join("|")
    );
  }

  function formatDiffSummary(summary) {
    if (!summary) {
      return "";
    }
    var fundPart = summary.fund > 0 ? " | Fund: " + summary.fund : "";
    if (summary.side_count && summary.side_count > 2) {
      var parts = [];
      (summary.only_by_side || []).forEach(function (item) {
        if (item.count > 0) {
          parts.push((item.label || "?") + ": +" + item.count);
        }
      });
      if (summary.in_all > 0) {
        parts.push("in allen: " + summary.in_all);
      }
      if (summary.in_some > 0) {
        parts.push("in einigen: " + summary.in_some);
      }
      return parts.join(" | ") + fundPart;
    }
    return (
      (summary.label_a || "A") +
      ": +" +
      (summary.only_a || 0) +
      " | " +
      (summary.label_b || "B") +
      ": +" +
      (summary.only_b || 0) +
      " | gemeinsam: " +
      (summary.both || 0) +
      fundPart
    );
  }

  function collectObjectsFromTabs(tabs) {
    var merged = [];
    (tabs || []).forEach(function (tab) {
      (tab.objects || []).forEach(function (obj) {
        merged.push(obj);
      });
    });
    return normalizeObjects(merged);
  }

  function truncateTitle(title) {
    var text = title == null ? "" : String(title);
    if (text.length <= TAB_TITLE_MAX) {
      return text;
    }
    return text.slice(0, TAB_TITLE_MAX - 1) + "…";
  }

  function buildQuery(objects, rawObjects) {
    var params = new URLSearchParams();
    var list =
      rawObjects && rawObjects.length ? rawObjects : objects || [];
    list.forEach(function (obj) {
      params.append("ct", obj.ct);
      params.append("pk", obj.pk);
    });
    return params.toString();
  }

  function buildDiffQuery(sides) {
    var params = new URLSearchParams();
    params.append("mode", "diff");
    (sides || []).forEach(function (side, index) {
      var prefix = "s" + index + "_";
      (side.objects || []).forEach(function (obj) {
        params.append(prefix + "ct", obj.ct);
        params.append(prefix + "pk", obj.pk);
      });
      var label = (side && (side.diffLabel || side.title)) || "";
      if (label) {
        params.append(prefix + "name", label);
      }
    });
    return params.toString();
  }

  function defaultPosition(el) {
    var vw = window.innerWidth || 1200;
    var vh = window.innerHeight || 800;
    var rect = el.getBoundingClientRect();
    el.style.left = Math.max(12, vw - rect.width - 24) + "px";
    el.style.top = Math.max(12, Math.min(vh * 0.12, vh - rect.height - 24)) + "px";
  }

  function createLoupeButton(title, obj) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "nsm-ipa-loupe";
    btn.setAttribute("aria-label", title || "Objekt analysieren");
    btn.title = title || "Objekt analysieren";
    btn.innerHTML = '<i class="mdi mdi-magnify" aria-hidden="true"></i>';
    if (obj && obj.ct != null && obj.pk != null) {
      btn.setAttribute("data-ct", String(obj.ct));
      btn.setAttribute("data-pk", String(obj.pk));
      btn.setAttribute("data-name", obj.name != null ? String(obj.name) : "");
    }
    return btn;
  }

  function loadingHtml() {
    return (
      '<div class="nsm-ipa-applet-loading">' +
      '<span class="mdi mdi-loading mdi-spin" aria-hidden="true"></span> Analyse läuft…</div>'
    );
  }

  function errorHtml(message) {
    return (
      '<div class="nsm-ipa-applet-error">' +
      escHtml(message || "Analyse fehlgeschlagen.") +
      "</div>"
    );
  }

  function Applet() {
    this.el = null;
    this.bodyEl = null;
    this.footerEl = null;
    this.titleEl = null;
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
    this._addObjectCategories = null;
    this._addObjectCategory = null;
    this._addObjectSearchCtrl = null;
    this._addObjectSearchToken = 0;
    this.minimized = false;
    this._merging = false;
    this._diffing = false;
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
    panel.setAttribute("aria-label", "IP-Analyse");
    panel.hidden = true;
    panel.innerHTML =
      '<div class="nsm-ipa-applet-header">' +
        '<h6 class="nsm-ipa-applet-title"><i class="mdi mdi-ip-network-outline" aria-hidden="true"></i><span class="nsm-ipa-applet-title-text">IP-Analyse</span></h6>' +
        '<div class="nsm-ipa-applet-actions">' +
          '<button type="button" class="btn btn-sm btn-ghost-secondary py-0 px-1 nsm-ipa-applet-minimize" title="Minimieren" aria-label="Minimieren"><i class="mdi mdi-window-minimize"></i></button>' +
          '<button type="button" class="btn btn-sm btn-ghost-secondary py-0 px-1 nsm-ipa-applet-close" title="Schließen" aria-label="Schließen"><i class="mdi mdi-close"></i></button>' +
        "</div>" +
      "</div>" +
      '<div class="nsm-ipa-applet-toolbar" hidden>' +
        '<div class="dropdown nsm-ipa-applet-add-object">' +
          '<button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle nsm-ipa-applet-add-object-toggle" data-bs-toggle="dropdown" data-bs-container="body" aria-expanded="false" title="Objekt hinzufügen" aria-label="Objekt hinzufügen">Objekt hinzufügen</button>' +
          '<ul class="dropdown-menu nsm-ipa-applet-add-object-menu"></ul>' +
        "</div>" +
        '<div class="nsm-ipa-applet-toolbar-actions">' +
          '<button type="button" class="btn btn-sm btn-outline-primary nsm-ipa-applet-merge" title="Merge" aria-label="Merge"><i class="mdi mdi-call-merge" aria-hidden="true"></i><span>Merge</span></button>' +
          '<button type="button" class="btn btn-sm btn-outline-primary nsm-ipa-applet-diff" title="Diff" aria-label="Diff"><i class="mdi mdi-compare" aria-hidden="true"></i><span>Diff</span></button>' +
        "</div>" +
      "</div>" +
      '<div class="nsm-ipa-applet-tabs" hidden>' +
        '<div class="nsm-ipa-applet-tab-list" role="tablist"></div>' +
      "</div>" +
      '<div class="nsm-ipa-applet-add-modal" hidden>' +
        '<div class="nsm-ipa-applet-add-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="nsm-ipa-applet-add-modal-title">' +
          '<div class="nsm-ipa-applet-add-modal-head">' +
            '<h6 class="nsm-ipa-applet-add-modal-title" id="nsm-ipa-applet-add-modal-title">Objekt hinzufügen</h6>' +
            '<button type="button" class="btn btn-sm btn-ghost-secondary py-0 px-1 nsm-ipa-applet-add-modal-close" title="Schließen" aria-label="Schließen"><i class="mdi mdi-close"></i></button>' +
          "</div>" +
          '<input type="search" class="form-control form-control-sm nsm-ipa-applet-add-search" placeholder="Suchen…" autocomplete="off">' +
          '<div class="nsm-ipa-applet-add-results"></div>' +
        "</div>" +
      "</div>" +
      '<div class="nsm-ipa-applet-body"></div>' +
      '<div class="nsm-ipa-applet-footer"><span class="nsm-ipa-applet-status"></span><span class="nsm-ipa-applet-count"></span></div>' +
      '<div class="nsm-ipa-applet-resize-handle nsm-ipa-applet-resize-handle--e" data-resize="e" aria-hidden="true"></div>' +
      '<div class="nsm-ipa-applet-resize-handle nsm-ipa-applet-resize-handle--s" data-resize="s" aria-hidden="true"></div>' +
      '<div class="nsm-ipa-applet-resize-handle nsm-ipa-applet-resize-handle--se" data-resize="se" aria-hidden="true"></div>';

    root.appendChild(panel);
    this.el = panel;
    this.bodyEl = panel.querySelector(".nsm-ipa-applet-body");
    this.footerEl = panel.querySelector(".nsm-ipa-applet-footer");
    this.titleEl = panel.querySelector(".nsm-ipa-applet-title-text");
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

    var header = panel.querySelector(".nsm-ipa-applet-header");
    header.addEventListener("mousedown", this._onHeaderDown.bind(this));
    panel.querySelector(".nsm-ipa-applet-close").addEventListener("click", this.close.bind(this));
    panel.querySelector(".nsm-ipa-applet-minimize").addEventListener("click", this.toggleMinimize.bind(this));

    this.tabListEl.addEventListener("click", this._onTabListClick.bind(this));
    this.mergeBtnEl.addEventListener("click", this.mergeTabs.bind(this));
    this.diffBtnEl.addEventListener("click", this.diffTabs.bind(this));
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

    inner.style.transform = "none";
    host.style.height = "auto";

    var available = this.bodyEl.clientWidth;
    var contentW = inner.scrollWidth;
    var scale = 1;
    if (contentW > available && available > 0) {
      scale = Math.max(MIN_BODY_SCALE, available / contentW);
    }

    if (scale < 0.999) {
      inner.style.transform = "scale(" + scale + ")";
      host.style.height = Math.ceil(inner.offsetHeight * scale) + "px";
    } else {
      inner.style.transform = "";
      host.style.height = "";
    }
  };

  Applet.prototype._scheduleBodyScale = function () {
    var self = this;
    if (this._scaleRaf) {
      cancelAnimationFrame(this._scaleRaf);
    }
    this._scaleRaf = requestAnimationFrame(function () {
      self._scaleRaf = null;
      self._fitBodyScale();
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

    if (dir.indexOf("e") !== -1) {
      width += dx;
    }
    if (dir.indexOf("s") !== -1) {
      height += dy;
    }

    var size = this._clampSize(
      width,
      height,
      this.resizeState.originLeft,
      this.resizeState.originTop
    );
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

  Applet.prototype.setWindowTitle = function () {
    if (!this.titleEl) {
      return;
    }
    var tab = this.getActiveTab();
    if (!tab) {
      this.titleEl.textContent = "IP-Analyse";
      return;
    }
    if (this.tabs.length > 1) {
      this.titleEl.textContent = "IP-Analyse (" + this.tabs.length + ")";
      return;
    }
    this.titleEl.textContent = tab.title;
  };

  Applet.prototype.renderToolbar = function () {
    if (!this.toolbarEl) {
      return;
    }
    var showToolbar = this.tabs.length >= 1 && this.el && !this.el.hidden;
    this.toolbarEl.hidden = !showToolbar;
    this.el.classList.toggle("nsm-ipa-applet--has-toolbar", showToolbar);

    if (this.mergeBtnEl) {
      var canMerge = this.tabs.length > 1;
      this.mergeBtnEl.disabled = !canMerge || this._merging || this._diffing;
    }
    if (this.diffBtnEl) {
      var canDiff = this.tabs.length >= 2;
      this.diffBtnEl.disabled = !canDiff || this._merging || this._diffing;
      this.diffBtnEl.title = canDiff
        ? "Diff"
        : "Diff (mindestens 2 Tabs erforderlich)";
      this.diffBtnEl.setAttribute(
        "aria-label",
        canDiff ? "Diff" : "Diff (mindestens 2 Tabs erforderlich)"
      );
    }
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
          '<span class="nsm-ipa-applet-tab-close" role="button" tabindex="-1" aria-label="Tab schließen" title="Schließen">&times;</span>' +
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
        '<li><span class="dropdown-item-text text-muted small">Keine Objekttypen verfügbar</span></li>';
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
      this.addObjectTitleEl.textContent = "Objekt hinzufügen — " + category.label;
    }
    if (this.addObjectResultsEl) {
      this.addObjectResultsEl.innerHTML =
        '<div class="nsm-ipa-applet-add-msg">Suchbegriff eingeben…</div>';
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
    if (message) {
      this.addObjectResultsEl.innerHTML =
        '<div class="nsm-ipa-applet-add-msg">' + escHtml(message) + "</div>";
      return;
    }
    if (!items.length) {
      this.addObjectResultsEl.innerHTML =
        '<div class="nsm-ipa-applet-add-msg">Keine Treffer</div>';
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
      this._renderAddObjectResults([], "Suchbegriff eingeben…");
      return;
    }
    if (this._addObjectSearchCtrl) {
      this._addObjectSearchCtrl.abort();
    }
    this._addObjectSearchCtrl = new AbortController();
    var token = ++this._addObjectSearchToken;
    var signal = this._addObjectSearchCtrl.signal;
    this._renderAddObjectResults([], "Suche…");

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
    if (this.tabs.length < 2 || this._diffing) {
      return;
    }

    var sourceTabs = this.tabs.slice();
    var hasObjects = sourceTabs.some(function (tab) {
      return (tab.objects || []).length > 0;
    });
    if (!hasObjects) {
      return;
    }

    this._diffing = true;
    this.renderTabs();

    sourceTabs.forEach(function (tab) {
      tab.loadToken = (tab.loadToken || 0) + 1;
    });

    var sides = sourceTabs.map(function (tab) {
      return {
        title: tab.title,
        diffLabel: diffSideLabel(tab),
        context: tab.context || null,
        objects: normalizeObjects(tab.objects),
      };
    });

    var diffTab = {
      id: this.nextTabId++,
      title: diffTabTitleFromTabs(sourceTabs),
      contextLabel: diffTabContextLabel(sourceTabs),
      mode: "diff",
      sides: sides,
      objectsKey: diffObjectsKey(sides),
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

    this.tabs = [diffTab];
    this.activeTabId = diffTab.id;
    this._diffing = false;

    this.renderTabs();
    this.setWindowTitle();
    this.renderActiveContent();
    this.loadTab(diffTab);
  };

  Applet.prototype.mergeTabs = function () {
    if (this.tabs.length < 2 || this._merging) {
      return;
    }

    var mergedObjects = collectObjectsFromTabs(this.tabs);
    if (!mergedObjects.length) {
      return;
    }

    this._merging = true;
    this.renderTabs();

    this.tabs.forEach(function (tab) {
      tab.loadToken = (tab.loadToken || 0) + 1;
    });

    var mergedTab = {
      id: this.nextTabId++,
      title: mergedTabTitle(mergedObjects.length),
      objects: mergedObjects,
      rawObjects: mergedObjects,
      objectsKey: objectsKey(mergedObjects),
      status: "loading",
      html: "",
      message: "",
      error: "",
      leafCount: 0,
      unsupportedCount: 0,
      loadToken: 0,
      _loading: false,
    };

    this.tabs = [mergedTab];
    this.activeTabId = mergedTab.id;
    this._merging = false;

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
      if (window.nsmInitAddrPrefixToggle) {
        window.nsmInitAddrPrefixToggle(this.bodyEl);
      }
      this._observeBodyContent();
      this._scheduleBodyScale();
    } else {
      this.bodyEl.innerHTML =
        contextBanner +
        '<div class="nsm-ipa-applet-empty">Keine IP-Adressen aufgelöst.</div>';
    }
    if (tab.mode === "diff" && tab.diffSummary) {
      countEl.textContent = formatDiffSummary(tab.diffSummary);
    } else {
      countEl.textContent = formatTypeCountSummary(tab);
    }
    statusEl.textContent = tab.unsupportedCount
      ? tab.unsupportedCount + " übersprungen"
      : "";
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
    tab._loading = true;
    tab.loadToken = (tab.loadToken || 0) + 1;
    var token = tab.loadToken;

    if (tab.id === this.activeTabId) {
      this.renderActiveContent();
    }

    var url =
      tab.mode === "diff"
        ? apiUrl() + "?" + buildDiffQuery(tab.sides || [])
        : apiUrl() + "?" + buildQuery(tab.objects, tab.rawObjects);
    nsmFetch(url, {
      headers: mergeBranchHeaders({ "X-Requested-With": "XMLHttpRequest" }),
    })
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error("HTTP " + resp.status);
        }
        return resp.json();
      })
      .then(
        function (data) {
          tab._loading = false;
          if (token !== tab.loadToken) {
            return;
          }
          if (!this.tabs.some(function (t) { return t.id === tab.id; })) {
            return;
          }
          tab.status = "ready";
          tab.html = data.html || "";
          tab.message = data.message || "";
          tab.leafCount = data.leaf_count || 0;
          tab.countSubnets = data.count_subnets != null ? data.count_subnets : null;
          tab.countRanges = data.count_ranges != null ? data.count_ranges : null;
          tab.countIps = data.count_ips != null ? data.count_ips : null;
          tab.countDuplicates =
            data.count_duplicates != null ? data.count_duplicates : null;
          tab.diffSummary = data.diff_summary || null;
          tab.unsupportedCount =
            data.unsupported && data.unsupported.length
              ? data.unsupported.length
              : 0;
          if (tab.id === this.activeTabId) {
            this.renderActiveContent();
          }
        }.bind(this)
      )
      .catch(
        function () {
          tab._loading = false;
          if (token !== tab.loadToken) {
            return;
          }
          if (!this.tabs.some(function (t) { return t.id === tab.id; })) {
            return;
          }
          tab.status = "error";
          tab.error = "Analyse konnte nicht geladen werden.";
          if (tab.id === this.activeTabId) {
            this.renderActiveContent();
          }
        }.bind(this)
      );
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

  function collectCellObjects(cell) {
    var objects = [];
    if (!cell) {
      return objects;
    }
    // Visible pills carry ct/pk; compact cells only expose hidden probe markers.
    // Never collect both — that duplicated every object and tripped false "doppelt".
    var rows = cell.querySelectorAll(
      '.nsm-ag-cell-item[data-addr-analyzable="1"]:not(.nsm-ag-cell-item--probe)'
    );
    if (!rows.length) {
      rows = cell.querySelectorAll(
        '.nsm-ag-cell-item--probe[data-addr-analyzable="1"]'
      );
    }
    rows.forEach(function (row) {
      objects.push({
        ct: row.getAttribute("data-ct"),
        pk: row.getAttribute("data-pk"),
        name: row.getAttribute("data-name") || "",
      });
    });
    return objects;
  }

  function loupeCellContainer(loupe) {
    return (
      loupe.closest(".nsm-ag-cell-list") ||
      loupe.closest(".nsm-ag-cell-merged")
    );
  }

  function readRulesCellContext(el) {
    if (!el) {
      return null;
    }
    var ruleIndex = el.getAttribute("data-rule-index");
    if (ruleIndex == null || ruleIndex === "") {
      return null;
    }
    return {
      ruleIndex: ruleIndex,
      ruleName: el.getAttribute("data-rule-name") || "",
      colId: el.getAttribute("data-col-id") || "",
      colPosition: el.getAttribute("data-col-position") || "",
    };
  }

  function collectRulesCellContext(loupe) {
    var cell = loupeCellContainer(loupe);
    var context = readRulesCellContext(cell);
    if (context) {
      return context;
    }
    var td = loupe.closest("td.nsm-rules-td");
    context = readRulesCellContext(td);
    if (context) {
      return context;
    }
    var tr = loupe.closest("tr.nsm-rules-data-row");
    if (!tr) {
      return null;
    }
    var ruleIndex = tr.getAttribute("data-rule-index");
    if (ruleIndex == null || ruleIndex === "") {
      return null;
    }
    return {
      ruleIndex: ruleIndex,
      ruleName: tr.getAttribute("data-rule-name") || "",
      colId: td ? td.getAttribute("data-col-id") || "" : "",
      colPosition: td ? td.getAttribute("data-col-position") || "" : "",
    };
  }

  function bindGlobalHandlers() {
    document.addEventListener("click", function (e) {
      var loupe = e.target.closest(".nsm-ipa-loupe");
      if (!loupe) {
        return;
      }
      e.preventDefault();
      e.stopPropagation();

      var cell = loupeCellContainer(loupe);
      var objects = [];
      if (loupe.classList.contains("nsm-ipa-cell-loupe") && cell) {
        objects = collectCellObjects(cell);
      } else if (loupe.hasAttribute("data-ct") && loupe.hasAttribute("data-pk")) {
        objects.push({
          ct: loupe.getAttribute("data-ct"),
          pk: loupe.getAttribute("data-pk"),
          name: loupe.getAttribute("data-name") || "",
        });
      } else if (cell) {
        objects = collectCellObjects(cell);
      }
      if (objects.length) {
        var context = null;
        if (loupe.classList.contains("nsm-ipa-cell-loupe")) {
          context = collectRulesCellContext(loupe);
        }
        singleton.open({ objects: objects, context: context });
      }
    });
  }

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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindGlobalHandlers);
  } else {
    bindGlobalHandlers();
  }
})();
