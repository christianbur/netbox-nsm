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

  function escHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function apiUrl() {
    return window.NSM_IP_ANALYSIS_API || "/plugins/netbox-nsm/api/ip-analysis/";
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

  function objectsKey(objects) {
    return objects
      .map(function (obj) {
        return obj.ct + ":" + obj.pk;
      })
      .sort()
      .join("|");
  }

  function tabTitle(objects, customTitle) {
    if (customTitle) {
      return String(customTitle);
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

  function buildQuery(objects) {
    var params = new URLSearchParams();
    objects.forEach(function (obj) {
      params.append("ct", obj.ct);
      params.append("pk", obj.pk);
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
    this.mergeBtnEl = null;
    this.minimized = false;
    this._merging = false;
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
      '<div class="nsm-ipa-applet-tabs" hidden>' +
        '<div class="nsm-ipa-applet-tab-list" role="tablist"></div>' +
        '<button type="button" class="btn btn-sm btn-outline-primary nsm-ipa-applet-merge" hidden title="Merge" aria-label="Merge"><i class="mdi mdi-call-merge" aria-hidden="true"></i><span>Merge</span></button>' +
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
    this.mergeBtnEl = panel.querySelector(".nsm-ipa-applet-merge");

    var header = panel.querySelector(".nsm-ipa-applet-header");
    header.addEventListener("mousedown", this._onHeaderDown.bind(this));
    panel.querySelector(".nsm-ipa-applet-close").addEventListener("click", this.close.bind(this));
    panel.querySelector(".nsm-ipa-applet-minimize").addEventListener("click", this.toggleMinimize.bind(this));

    this.tabListEl.addEventListener("click", this._onTabListClick.bind(this));
    this.mergeBtnEl.addEventListener("click", this.mergeTabs.bind(this));

    panel.querySelectorAll(".nsm-ipa-applet-resize-handle").forEach(
      function (handle) {
        handle.addEventListener("mousedown", this._onResizeDown.bind(this));
      }.bind(this)
    );
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

  Applet.prototype.findTabByObjects = function (objects) {
    var key = objectsKey(objects);
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

  Applet.prototype.renderTabs = function () {
    if (!this.tabListEl || !this.tabsEl) {
      return;
    }
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

    if (this.mergeBtnEl) {
      var canMerge = this.tabs.length > 1;
      this.mergeBtnEl.hidden = !canMerge;
      this.mergeBtnEl.disabled = !canMerge || this._merging;
    }
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
    if (tab.message && !tab.html) {
      this.bodyEl.innerHTML =
        '<div class="nsm-ipa-applet-empty">' + escHtml(tab.message) + "</div>";
    } else if (tab.html) {
      this.bodyEl.innerHTML = tab.html;
      if (window.nsmInitAddrPrefixToggle) {
        window.nsmInitAddrPrefixToggle(this.bodyEl);
      }
    } else {
      this.bodyEl.innerHTML =
        '<div class="nsm-ipa-applet-empty">Keine IP-Adressen aufgelöst.</div>';
    }
    countEl.textContent = tab.leafCount ? tab.leafCount + " IP(s)" : "";
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

    var url = apiUrl() + "?" + buildQuery(tab.objects);
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
    var objects = normalizeObjects(opts.objects);
    if (!objects.length) {
      return;
    }

    this.ensureDom();

    var existing = this.findTabByObjects(objects);
    if (existing) {
      this.showWindow();
      this.activateTab(existing.id);
      return;
    }

    var tab = {
      id: this.nextTabId++,
      title: tabTitle(objects, opts.title),
      objects: objects,
      objectsKey: objectsKey(objects),
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
  };

  var singleton = new Applet();

  function collectCellObjects(cell) {
    var objects = [];
    if (!cell) {
      return objects;
    }
    cell.querySelectorAll('.nsm-ag-cell-item[data-addr-analyzable="1"]').forEach(function (row) {
      objects.push({
        ct: row.getAttribute("data-ct"),
        pk: row.getAttribute("data-pk"),
        name: row.getAttribute("data-name") || "",
      });
    });
    return objects;
  }

  function bindGlobalHandlers() {
    document.addEventListener("click", function (e) {
      var loupe = e.target.closest(".nsm-ipa-loupe");
      if (!loupe) {
        return;
      }
      e.preventDefault();
      e.stopPropagation();

      var objects = [];
      if (loupe.hasAttribute("data-ct") && loupe.hasAttribute("data-pk")) {
        objects.push({
          ct: loupe.getAttribute("data-ct"),
          pk: loupe.getAttribute("data-pk"),
          name: loupe.getAttribute("data-name") || "",
        });
      } else {
        var cell = loupe.closest(".nsm-ag-cell-list");
        objects = collectCellObjects(cell);
      }
      if (objects.length) {
        singleton.open({ objects: objects });
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
    createLoupeButton: createLoupeButton,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindGlobalHandlers);
  } else {
    bindGlobalHandlers();
  }
})();
