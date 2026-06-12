(function () {
  "use strict";

  var TAB_WIDTH_STORAGE_PREFIX = "nsm-rules-tab-sidebar-width:";
  var TAB_SIDEBAR_DEFAULT_WIDTH = 184;
  var TAB_SIDEBAR_MIN_WIDTH = 120;
  var TAB_SIDEBAR_MAX_WIDTH = 480;

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

  function toggleGroupChildren(groupId, expanded) {
    var selector =
      'tbody tr.nsm-rules-data-row[data-parent-group="' +
      CSS.escape(groupId) +
      '"]';
    document.querySelectorAll(selector).forEach(function (row) {
      row.classList.toggle("nsm-rules-group-child--collapsed", !expanded);
    });
    var header = document.querySelector(
      'tbody tr.nsm-rules-group-row[data-group-id="' + CSS.escape(groupId) + '"]'
    );
    if (header) {
      header.classList.toggle("is-expanded", expanded);
      var toggle = header.querySelector(".nsm-rules-group-toggle");
      if (toggle) {
        toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      }
    }
  }

  function bindGroupToggles() {
    document.querySelectorAll("#rules .nsm-rules-group-toggle").forEach(function (btn) {
      if (btn.dataset.nsmRowGroupBound === "1") {
        return;
      }
      btn.dataset.nsmRowGroupBound = "1";
      btn.addEventListener("click", function () {
        var groupId = btn.getAttribute("data-group-id");
        if (!groupId) {
          return;
        }
        var header = btn.closest("tr.nsm-rules-group-row");
        var expanded = !(header && header.classList.contains("is-expanded"));
        toggleGroupChildren(groupId, expanded);
      });
    });
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

    var saved = loadTabSidebarWidth(config && config.rulebookId);
    applyTabSidebarWidth(nav, saved != null ? saved : TAB_SIDEBAR_DEFAULT_WIDTH);

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
      if (event.button !== 0) {
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

  function ensureGroupsCollapsedByDefault() {
    document.querySelectorAll("#rules tbody tr.nsm-rules-group-row").forEach(function (header) {
      var groupId = header.getAttribute("data-group-id");
      if (!groupId) {
        return;
      }
      header.classList.remove("is-expanded");
      var toggle = header.querySelector(".nsm-rules-group-toggle");
      if (toggle) {
        toggle.setAttribute("aria-expanded", "false");
      }
      toggleGroupChildren(groupId, false);
    });
  }

  function init() {
    var config = readConfig() || {};
    bindRowGroupTabScroll();
    bindTabSidebarResizeAll(config);
    if (config.rowGroupActive && !config.rowGroupTabActive) {
      bindGroupToggles();
      ensureGroupsCollapsedByDefault();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
