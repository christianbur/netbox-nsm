(function () {
  "use strict";

  var TAB_WIDTH_STORAGE_PREFIX = "nsm-rules-tab-sidebar-width:";
  var TAB_COLLAPSED_STORAGE_PREFIX = "nsm-rules-tab-sidebar-collapsed:";
  var TAB_SIDEBAR_DEFAULT_WIDTH = 184;
  var TAB_SIDEBAR_MIN_WIDTH = 120;
  var TAB_SIDEBAR_MAX_WIDTH = 480;
  var TAB_SIDEBAR_COLLAPSED_WIDTH = 32;

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

  function updateTabScrollButtons(viewport, prevBtn, nextBtn, vertical) {
    if (!viewport || !prevBtn || !nextBtn) {
      return;
    }
    if (vertical) {
      var maxScrollY = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
      var atTop = viewport.scrollTop <= 1;
      var atBottom = viewport.scrollTop >= maxScrollY - 1;
      prevBtn.disabled = atTop;
      nextBtn.disabled = atBottom;
      return;
    }
    var maxScroll = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
    prevBtn.disabled = viewport.scrollLeft <= 1;
    nextBtn.disabled = viewport.scrollLeft >= maxScroll - 1;
  }

  function scrollRowGroupTabs(viewport, direction, vertical) {
    if (!viewport) {
      return;
    }
    if (vertical) {
      var stepY = Math.max(120, Math.floor(viewport.clientHeight * 0.75));
      viewport.scrollBy({
        top: direction * stepY,
        behavior: "smooth",
      });
      return;
    }
    var step = Math.max(160, Math.floor(viewport.clientWidth * 0.75));
    viewport.scrollBy({
      left: direction * step,
      behavior: "smooth",
    });
  }

  function scrollActiveTabIntoView(viewport, vertical) {
    if (!viewport) {
      return;
    }
    var active = viewport.querySelector(".nav-link.active");
    if (!active) {
      return;
    }
    var tabItem = active.closest(".nav-item") || active;
    var viewportRect = viewport.getBoundingClientRect();
    var tabRect = tabItem.getBoundingClientRect();
    if (vertical) {
      viewport.scrollTop += tabRect.top - viewportRect.top;
      return;
    }
    viewport.scrollLeft += tabRect.left - viewportRect.left;
  }

  function bindRowGroupTabScrollContainer(nav) {
    if (!nav || nav.dataset.nsmRowGroupTabsBound === "1") {
      return;
    }
    nav.dataset.nsmRowGroupTabsBound = "1";

    var vertical = nav.classList.contains("nsm-rules-row-group-tabs--vertical");
    var viewport = nav.querySelector(".nsm-rules-row-group-tabs-viewport");
    var prevBtn = nav.querySelector(".nsm-rules-row-group-tabs-scroll--prev");
    var nextBtn = nav.querySelector(".nsm-rules-row-group-tabs-scroll--next");
    if (!viewport || !prevBtn || !nextBtn) {
      return;
    }

    var refresh = function () {
      updateTabScrollButtons(viewport, prevBtn, nextBtn, vertical);
    };

    prevBtn.addEventListener("click", function () {
      scrollRowGroupTabs(viewport, -1, vertical);
    });
    nextBtn.addEventListener("click", function () {
      scrollRowGroupTabs(viewport, 1, vertical);
    });
    viewport.addEventListener("scroll", refresh, { passive: true });
    window.addEventListener("resize", refresh);

    scrollActiveTabIntoView(viewport, vertical);
    refresh();
  }

  function bindRowGroupTabScroll() {
    document
      .querySelectorAll("#rules .nsm-rules-row-group-tabs")
      .forEach(bindRowGroupTabScrollContainer);
  }

  function tabSidebarStorageKey(rulebookId) {
    return TAB_WIDTH_STORAGE_PREFIX + String(rulebookId == null ? "0" : rulebookId);
  }

  function loadTabSidebarWidth(rulebookId) {
    try {
      var raw = localStorage.getItem(tabSidebarStorageKey(rulebookId));
      if (raw == null) {
        return null;
      }
      var width = parseInt(raw, 10);
      return width > 0 ? width : null;
    } catch (e) {
      return null;
    }
  }

  function saveTabSidebarWidth(rulebookId, widthPx) {
    try {
      localStorage.setItem(tabSidebarStorageKey(rulebookId), String(widthPx));
    } catch (e) {
      /* ignore quota errors */
    }
  }

  function clampTabSidebarWidth(widthPx) {
    return Math.max(
      TAB_SIDEBAR_MIN_WIDTH,
      Math.min(TAB_SIDEBAR_MAX_WIDTH, Math.round(widthPx))
    );
  }

  function applyTabSidebarWidth(nav, widthPx) {
    var next = clampTabSidebarWidth(widthPx);
    nav.style.setProperty("--nsm-rules-tab-sidebar-width", next + "px");
    nav.style.width = next + "px";
    return next;
  }

  function readTabSidebarWidth(nav) {
    var rect = nav.getBoundingClientRect();
    if (rect.width > 0) {
      return Math.round(rect.width);
    }
    var inline = parseInt(nav.style.width, 10);
    if (inline > 0) {
      return inline;
    }
    return TAB_SIDEBAR_DEFAULT_WIDTH;
  }

  function bindTabSidebarResize(nav, config) {
    var handle = nav.querySelector(".nsm-rules-row-group-tabs-resize-handle");
    if (!handle || nav.dataset.nsmTabSidebarResizeBound === "1") {
      return;
    }
    nav.dataset.nsmTabSidebarResizeBound = "1";

    if (
      !nav.classList.contains("nsm-rules-row-group-tabs--collapsed") &&
      !loadTabSidebarCollapsed(config && config.rulebookId)
    ) {
      var saved = loadTabSidebarWidth(config && config.rulebookId);
      applyTabSidebarWidth(nav, saved != null ? saved : TAB_SIDEBAR_DEFAULT_WIDTH);
    }

    var resizeState = null;

    function stopResize() {
      if (!resizeState) {
        return;
      }
      saveTabSidebarWidth(config.rulebookId, resizeState.width);
      resizeState = null;
      nav.classList.remove("nsm-rules-row-group-tabs--resizing");
      document.body.classList.remove("nsm-rules-tab-sidebar-resizing");
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", stopResize);
    }

    function onMouseMove(event) {
      if (!resizeState) {
        return;
      }
      var delta = event.clientX - resizeState.startX;
      resizeState.width = applyTabSidebarWidth(
        nav,
        resizeState.startWidth + delta
      );
    }

    handle.addEventListener("mousedown", function (event) {
      if (event.button !== 0 || nav.classList.contains("nsm-rules-row-group-tabs--collapsed")) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      resizeState = {
        startX: event.clientX,
        startWidth: readTabSidebarWidth(nav),
        width: readTabSidebarWidth(nav),
      };
      nav.classList.add("nsm-rules-row-group-tabs--resizing");
      document.body.classList.add("nsm-rules-tab-sidebar-resizing");
      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", stopResize);
    });
  }

  function bindTabSidebarResizeAll(config) {
    document
      .querySelectorAll("#rules .nsm-rules-row-group-tabs--vertical")
      .forEach(function (nav) {
        bindTabSidebarResize(nav, config);
      });
  }

  function tabSidebarCollapsedStorageKey(rulebookId) {
    return TAB_COLLAPSED_STORAGE_PREFIX + String(rulebookId == null ? "0" : rulebookId);
  }

  function loadTabSidebarCollapsed(rulebookId) {
    try {
      return localStorage.getItem(tabSidebarCollapsedStorageKey(rulebookId)) === "1";
    } catch (e) {
      return false;
    }
  }

  function saveTabSidebarCollapsed(rulebookId, collapsed) {
    try {
      localStorage.setItem(
        tabSidebarCollapsedStorageKey(rulebookId),
        collapsed ? "1" : "0"
      );
    } catch (e) {
      /* ignore quota errors */
    }
  }

  function splitTabLabelWords(text) {
    var words = text.split(/\s+/).filter(function (word) {
      return word.length > 0;
    });
    return words.length > 0 ? words : [text];
  }

  function appendVerticalWordChars(parentEl, word) {
    var wordSpan = document.createElement("span");
    wordSpan.className = "nsm-rules-row-group-tab-label-word";
    wordSpan.setAttribute("aria-hidden", "true");
    for (var i = 0; i < word.length; i += 1) {
      var charSpan = document.createElement("span");
      charSpan.className = "nsm-rules-row-group-tab-label-char";
      charSpan.textContent = word.charAt(i);
      charSpan.setAttribute("aria-hidden", "true");
      wordSpan.appendChild(charSpan);
    }
    parentEl.appendChild(wordSpan);
  }

  function splitTabLabelsForCollapsed(nav) {
    nav.querySelectorAll(".nsm-rules-row-group-tab-label").forEach(function (labelEl) {
      if (labelEl.dataset.nsmOriginalLabel != null) {
        return;
      }
      var text = labelEl.textContent.trim();
      labelEl.dataset.nsmOriginalLabel = text;
      labelEl.textContent = "";
      labelEl.classList.add("nsm-rules-row-group-tab-label--vertical-chars");
      splitTabLabelWords(text).forEach(function (word) {
        appendVerticalWordChars(labelEl, word);
      });
    });
  }

  function restoreTabLabels(nav) {
    nav.querySelectorAll(".nsm-rules-row-group-tab-label").forEach(function (labelEl) {
      var original = labelEl.dataset.nsmOriginalLabel;
      if (original == null) {
        return;
      }
      labelEl.textContent = original;
      delete labelEl.dataset.nsmOriginalLabel;
      labelEl.classList.remove("nsm-rules-row-group-tab-label--vertical-chars");
    });
  }

  function applyTabSidebarCollapsedWidth(nav) {
    nav.style.setProperty("--nsm-rules-tab-sidebar-width", TAB_SIDEBAR_COLLAPSED_WIDTH + "px");
    nav.style.width = TAB_SIDEBAR_COLLAPSED_WIDTH + "px";
  }

  function updateCollapseToggleUi(nav, collapsed) {
    var toggle = nav.querySelector(".nsm-rules-row-group-tabs-collapse");
    if (!toggle) {
      return;
    }
    toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    var label = collapsed
      ? toggle.dataset.labelExpand || "Expand rule groups sidebar"
      : toggle.dataset.labelCollapse || "Collapse rule groups sidebar";
    toggle.setAttribute("aria-label", label);
    toggle.setAttribute("title", label);
  }

  function setTabSidebarCollapsed(nav, config, collapsed, options) {
    var opts = options || {};
    if (collapsed) {
      if (!nav.classList.contains("nsm-rules-row-group-tabs--collapsed")) {
        saveTabSidebarWidth(
          config && config.rulebookId,
          readTabSidebarWidth(nav)
        );
      }
      nav.classList.add("nsm-rules-row-group-tabs--collapsed");
      splitTabLabelsForCollapsed(nav);
      applyTabSidebarCollapsedWidth(nav);
    } else {
      nav.classList.remove("nsm-rules-row-group-tabs--collapsed");
      restoreTabLabels(nav);
      var saved = loadTabSidebarWidth(config && config.rulebookId);
      applyTabSidebarWidth(nav, saved != null ? saved : TAB_SIDEBAR_DEFAULT_WIDTH);
    }
    updateCollapseToggleUi(nav, collapsed);
    saveTabSidebarCollapsed(config && config.rulebookId, collapsed);
    var viewport = nav.querySelector(".nsm-rules-row-group-tabs-viewport");
    var prevBtn = nav.querySelector(".nsm-rules-row-group-tabs-scroll--prev");
    var nextBtn = nav.querySelector(".nsm-rules-row-group-tabs-scroll--next");
    if (viewport && prevBtn && nextBtn) {
      scrollActiveTabIntoView(viewport, true);
      updateTabScrollButtons(viewport, prevBtn, nextBtn, true);
    }
    if (opts.syncHeight !== false) {
      syncSidebarToTableHeight();
    }
  }

  function bindTabSidebarCollapse(nav, config) {
    var toggle = nav.querySelector(".nsm-rules-row-group-tabs-collapse");
    if (!toggle || nav.dataset.nsmTabSidebarCollapseBound === "1") {
      return;
    }
    nav.dataset.nsmTabSidebarCollapseBound = "1";

    var collapsed = loadTabSidebarCollapsed(config && config.rulebookId);
    if (collapsed) {
      setTabSidebarCollapsed(nav, config, true, { syncHeight: false });
    } else {
      updateCollapseToggleUi(nav, false);
    }

    toggle.addEventListener("click", function () {
      var nextCollapsed = !nav.classList.contains("nsm-rules-row-group-tabs--collapsed");
      setTabSidebarCollapsed(nav, config, nextCollapsed);
    });
  }

  function bindTabSidebarCollapseAll(config) {
    document
      .querySelectorAll("#rules .nsm-rules-row-group-tabs--vertical")
      .forEach(function (nav) {
        bindTabSidebarCollapse(nav, config);
      });
  }

  function syncSidebarToTableHeight() {
    var body = document.querySelector("#rules .nsm-rules-body--with-side-tabs");
    if (!body) {
      return;
    }
    var nav = body.querySelector(".nsm-rules-row-group-tabs--vertical");
    if (!nav) {
      return;
    }
    // Match sidebar to the viewport-sized rules body, not the table content height.
    // Using the scroll container's content height grows the flex row and disables scroll.
    var height = body.clientHeight;
    if (height > 0) {
      nav.style.height = height + "px";
      nav.style.maxHeight = height + "px";
    } else {
      nav.style.removeProperty("height");
      nav.style.removeProperty("max-height");
    }
    var viewport = nav.querySelector(".nsm-rules-row-group-tabs-viewport");
    var prevBtn = nav.querySelector(".nsm-rules-row-group-tabs-scroll--prev");
    var nextBtn = nav.querySelector(".nsm-rules-row-group-tabs-scroll--next");
    if (viewport && prevBtn && nextBtn) {
      updateTabScrollButtons(viewport, prevBtn, nextBtn, true);
    }
  }

  function bindSidebarHeightSync() {
    var body = document.querySelector("#rules .nsm-rules-body--with-side-tabs");
    if (!body || body.dataset.nsmSidebarHeightSyncBound === "1") {
      return;
    }
    body.dataset.nsmSidebarHeightSyncBound = "1";

    var refresh = function () {
      syncSidebarToTableHeight();
    };

    refresh();
    window.addEventListener("resize", refresh);
    window.addEventListener("nsm:rules-panel-height", refresh);
    if (typeof ResizeObserver !== "undefined") {
      var observer = new ResizeObserver(refresh);
      observer.observe(body);
    }
  }

  function init() {
    var config = readConfig() || {};
    bindRowGroupTabScroll();
    bindTabSidebarCollapseAll(config);
    bindTabSidebarResizeAll(config);
    bindSidebarHeightSync();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
