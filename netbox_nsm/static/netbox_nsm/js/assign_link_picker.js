/* Assign Link element picker – lazy browse aligned with rule_form.js */
(function () {
  "use strict";

  var form = document.getElementById("assign-form");
  if (!form) return;

  var apiBase = form.dataset.apiBase || "";
  var assignerCtId = form.dataset.assignerCtId || "";
  var prefillId = form.dataset.prefillId || "";
  var prefillDisplay = form.dataset.prefillDisplay || "";

  var typeSelect = form.querySelector(".nsm-type-select");
  var pickerWrap = form.querySelector(".nsm-element-picker-wrap");
  var searchInput = form.querySelector(".nsm-search-input");
  var listEl = document.getElementById("element-browse-list");
  var selectedWrap = form.querySelector(".nsm-selected");
  var submitBtn = document.getElementById("submit-btn");
  var errorEl = document.getElementById("element-error");

  if (!typeSelect || !pickerWrap || !searchInput || !listEl || !selectedWrap) return;

  var dropWrap = listEl.closest(".nsm-browse-drop");

  var PAGE_SIZE = 30;
  var currentCtId = null;
  var abortCtrl = null;
  var selected = {};

  var browse = {
    items: [],
    total: 0,
    offset: 0,
    loading: false,
    query: "",
    hasMore: false,
  };

  function msg(name, fallback) {
    var key = "msg" + name.charAt(0).toUpperCase() + name.slice(1);
    return form.dataset[key] || fallback;
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function debounce(fn, ms) {
    var timer;
    return function () {
      clearTimeout(timer);
      var ctx = this;
      var args = arguments;
      timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  function resetBrowse() {
    browse.items = [];
    browse.total = 0;
    browse.offset = 0;
    browse.loading = false;
    browse.query = "";
    browse.hasMore = false;
    if (abortCtrl) {
      abortCtrl.abort();
      abortCtrl = null;
    }
  }

  function hideBrowseDrop() {
    if (dropWrap) dropWrap.hidden = true;
  }

  function isSearchFocused() {
    return document.activeElement === searchInput;
  }

  function syncDropVisibility(html) {
    if (dropWrap) dropWrap.hidden = !(isSearchFocused() && (html || browse.loading));
  }

  function updateBrowseList() {
    var available = browse.items.filter(function (item) {
      return !selected[item.id];
    });

    var html = "";
    if (!browse.items.length && browse.loading) {
      html = "<div class='nsm-drop-msg'>" + esc(msg("searching", "Searching\u2026")) + "</div>";
    } else if (!available.length && !browse.loading) {
      html = "<div class='nsm-drop-msg'>" + esc(msg("noResults", "No results")) + "</div>";
    } else {
      available.forEach(function (item) {
        html += "<div class='option' data-id='" + esc(String(item.id)) + "'>"
          + "<span class='nsm-drop-name'>" + esc(item.display) + "</span>"
          + "</div>";
      });
      if (browse.loading) {
        html += "<div class='nsm-drop-msg'>" + esc(msg("searching", "Searching\u2026")) + "</div>";
      } else if (browse.hasMore) {
        html += "<div class='nsm-browse-more option'>"
          + esc(msg("loadMore", "Load more\u2026"))
          + "</div>";
      }
    }

    listEl.innerHTML = html;

    listEl.querySelectorAll(".option[data-id]").forEach(function (el) {
      el.addEventListener("mouseenter", function () {
        listEl.querySelectorAll(".option.active").forEach(function (a) { a.classList.remove("active"); });
        el.classList.add("active");
      });
      el.addEventListener("mouseleave", function () { el.classList.remove("active"); });
    });

    syncDropVisibility(html);
  }

  function loadBrowse(append) {
    if (!currentCtId) return;

    if (!append) {
      browse.items = [];
      browse.offset = 0;
      browse.total = 0;
      browse.hasMore = false;
    }
    if (browse.loading) return;

    var query = browse.query.trim();
    var apiQuery = (query === "*") ? "" : query;

    browse.loading = true;
    updateBrowseList();

    if (abortCtrl) abortCtrl.abort();
    abortCtrl = new AbortController();

    var fetchFn = (window.NSM_BRANCH_API && window.NSM_BRANCH_API.fetch) || fetch;
    var apiUrl = apiBase
      + "?ct_id=" + encodeURIComponent(currentCtId)
      + "&q=" + encodeURIComponent(apiQuery)
      + "&limit=" + PAGE_SIZE
      + "&offset=" + browse.offset;
    if (assignerCtId) {
      apiUrl += "&assigner_ct_id=" + encodeURIComponent(assignerCtId);
    }

    var headers = { "X-Requested-With": "XMLHttpRequest" };
    if (window.NSM_BRANCH_API && NSM_BRANCH_API.mergeBranchHeaders) {
      headers = NSM_BRANCH_API.mergeBranchHeaders(headers);
    }

    var opts = { headers: headers, signal: abortCtrl.signal };

    fetchFn(apiUrl, opts)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (abortCtrl && abortCtrl.signal.aborted) return;
        var results = data.results || [];
        browse.hasMore = !!data.has_more;
        browse.total = data.count || 0;
        browse.items = append ? browse.items.concat(results) : results;
        browse.offset = append ? browse.offset + results.length : results.length;
        browse.loading = false;
        updateBrowseList();
      })
      .catch(function (err) {
        if (err && err.name === "AbortError") return;
        browse.loading = false;
        browse.items = [];
        listEl.innerHTML = "<div class='nsm-drop-msg'>" + esc(msg("error", "Error loading")) + "</div>";
        syncDropVisibility(listEl.innerHTML);
      });
  }

  var debouncedBrowse = debounce(function () {
    loadBrowse(false);
  }, 300);

  function renderSelected() {
    form.querySelectorAll('input[name="object_b_id"]').forEach(function (el) { el.remove(); });

    var ids = Object.keys(selected);
    if (!ids.length) {
      selectedWrap.innerHTML = "";
      if (submitBtn) submitBtn.disabled = true;
      return;
    }

    selectedWrap.innerHTML = ids.map(function (id) {
      return "<div class='nsm-sel-item nsm-sel-item-muted' data-sel-id='" + esc(id) + "'>"
        + "<span class='nsm-sel-item-name'>" + esc(selected[id]) + "</span>"
        + "<button type='button' class='nsm-sel-item-remove' data-remove-id='" + esc(id) + "'"
        + " title='" + esc(msg("remove", "Remove")) + "'"
        + " aria-label='" + esc(msg("remove", "Remove")) + "'>"
        + "<span class='nsm-sel-item-remove-icon' aria-hidden='true'>\u00d7</span>"
        + "</button>"
        + "</div>";
    }).join("");

    selectedWrap.querySelectorAll("[data-remove-id]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        delete selected[btn.dataset.removeId];
        renderSelected();
        updateBrowseList();
      });
    });

    ids.forEach(function (id) {
      var inp = document.createElement("input");
      inp.type = "hidden";
      inp.name = "object_b_id";
      inp.value = id;
      form.appendChild(inp);
    });

    if (submitBtn) submitBtn.disabled = false;
    if (errorEl) errorEl.textContent = "";
  }

  function selectItem(id, display) {
    selected[id] = display;
    renderSelected();
  }

  typeSelect.addEventListener("change", function () {
    currentCtId = this.value || null;
    selected = {};
    renderSelected();
    resetBrowse();
    hideBrowseDrop();
    listEl.innerHTML = "";
    searchInput.value = "";
    if (errorEl) errorEl.textContent = "";

    if (!currentCtId) {
      pickerWrap.classList.add("hidden");
      return;
    }

    pickerWrap.classList.remove("hidden");
  });

  searchInput.addEventListener("input", function () {
    browse.query = searchInput.value;
    debouncedBrowse();
  });

  searchInput.addEventListener("focus", function () {
    browse.query = searchInput.value;
    debouncedBrowse();
  });

  searchInput.addEventListener("blur", function () {
    setTimeout(hideBrowseDrop, 200);
  });

  listEl.addEventListener("mousedown", function (e) {
    var moreEl = e.target.closest(".nsm-browse-more");
    if (moreEl) {
      e.preventDefault();
      loadBrowse(true);
      return;
    }

    var optionEl = e.target.closest(".option[data-id]");
    if (!optionEl) return;

    e.preventDefault();
    var nameEl = optionEl.querySelector(".nsm-drop-name");
    var display = nameEl ? nameEl.textContent.trim() : optionEl.textContent.trim();
    selectItem(optionEl.dataset.id, display);
    hideBrowseDrop();
    searchInput.value = "";
    browse.query = "";
    resetBrowse();
  });

  var propagationSelect = document.getElementById("id_propagation");
  var propagateStopWrap = document.getElementById("propagate-stop-wrap");

  function syncPropagationUi() {
    if (!propagationSelect || !propagateStopWrap) return;
    propagateStopWrap.style.display = propagationSelect.value === "direct" ? "none" : "";
  }

  if (propagationSelect) {
    propagationSelect.addEventListener("change", syncPropagationUi);
    syncPropagationUi();
  }

  if (typeSelect.value) {
    currentCtId = typeSelect.value;
    pickerWrap.classList.remove("hidden");
  }

  if (prefillId && prefillDisplay) {
    selectItem(prefillId, prefillDisplay);
  }
})();
