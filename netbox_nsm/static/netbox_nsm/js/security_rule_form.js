/* NSM Rule Picker – AJAX search edition
 *
 * Data format from server (nsm-rule-picker-data):
 * { areas: [{ slug, name, display_name, sort_order, types: [
 *   { name, ct_id, api_url, kind:"object" }  ← fetched via REST API
 *   { name:"Groups", kind:"group", entries:[{id, name}] }  ← static
 * ]}]}
 *
 * state.selections  keyed by "area:placement:kind:id"
 * state.search      keyed by "area:placement" → {query, results, loading}
 * state._ctrl       keyed by "area:placement" → AbortController
 */
(function () {
  "use strict";

  var state = {
    data: { areas: [] },
    selections: {},
    ui: { __activeArea: "" },
    search: {},
    _ctrl: {},
    vgroups: {},    // { areaSlug: true }  — areas where all items form one AND-group
  };

  // ── i18n ───────────────────────────────────────────────────────────────────
  var i18n = window.NSM_I18N || {};
  function t(key, fallback) { return i18n[key] || fallback || key; }

  // ── Helpers ────────────────────────────────────────────────────────────────

  function pickerEl() { return document.getElementById("nsm-rule-picker"); }
  function hiddenEl()  { return document.getElementById("nsm-area-selections"); }
  function vgroupHiddenEl() { return document.getElementById("nsm-virtual-group-config"); }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function cssEsc(v) {
    return (window.CSS && CSS.escape)
      ? CSS.escape(v)
      : String(v).replace(/([^a-zA-Z0-9_-])/g, "\\$1");
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      clearTimeout(t);
      var ctx = this, args = arguments;
      t = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  function getCsrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  // ── Picker data ────────────────────────────────────────────────────────────

  function getPickerData() {
    var el = document.getElementById("nsm-rule-picker-data");
    if (!el) return { areas: [] };
    try {
      var p = JSON.parse(el.textContent);
      return (p && Array.isArray(p.areas)) ? p : { areas: [] };
    } catch (_) { return { areas: [] }; }
  }

  function loadInitialSelections() {
    var el = document.getElementById("nsm-rule-selections");
    if (!el) return;
    try {
      var list = JSON.parse(el.textContent);
      if (!Array.isArray(list)) return;
      list.forEach(function (sel) {
        if (!sel.area || !sel.placement || !sel.kind || !sel.id) return;
        var k = [sel.area, sel.placement, sel.kind, String(sel.id)].join(":");
        state.selections[k] = {
          area: sel.area, placement: sel.placement,
          kind: sel.kind, id: String(sel.id),
          name: sel.name || String(sel.id),
          typeName: sel.typeName || "",
          matchingClass: sel.matchingClass || "",
          exclude: !!sel.exclude,
        };
      });
    } catch (_) {}
  }

  function loadInitialVGroups() {
    var el = document.getElementById("nsm-rule-virtual-groups");
    if (!el) return;
    try {
      var cfg = JSON.parse(el.textContent);
      if (!cfg || typeof cfg !== "object") return;
      Object.keys(cfg).forEach(function (areaSlug) {
        if (cfg[areaSlug] === true) state.vgroups[areaSlug] = true;
      });
    } catch (_) {}
  }

  // ── Selection helpers ──────────────────────────────────────────────────────

  function selKey(area, placement, kind, id) {
    return [area, placement, kind, String(id)].join(":");
  }

  function hasSelection(area, placement, kind, id) {
    return !!state.selections[selKey(area, placement, kind, id)];
  }

  function addSelection(area, placement, kind, id, name, typeName, matchingClass) {
    state.selections[selKey(area, placement, kind, id)] = {
      area: area, placement: placement, kind: kind, id: String(id),
      name: name || String(id), typeName: typeName || "",
      matchingClass: matchingClass || "",
      exclude: false,
    };
    syncHidden();
  }

  function removeSelection(area, placement, kind, id) {
    delete state.selections[selKey(area, placement, kind, id)];
    syncHidden();
  }

  function syncHidden() {
    var el = hiddenEl();
    if (!el) return;
    el.value = JSON.stringify(
      Object.values(state.selections).map(function (s) {
        return { area: s.area, placement: s.placement, kind: s.kind, id: s.id, exclude: !!s.exclude };
      })
    );
    var vgEl = vgroupHiddenEl();
    if (vgEl) vgEl.value = JSON.stringify(state.vgroups);
  }

  function selectionsFor(areaSlug, placement) {
    return Object.values(state.selections)
      .filter(function (s) { return s.area === areaSlug && s.placement === placement; })
      .sort(function (a, b) {
        return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
      });
  }

  // ── VGroup helpers ─────────────────────────────────────────────────────────

  function areaAllowsVGroups(areaSlug) {
    var area = state.data.areas.find(function (a) { return a.slug === areaSlug; });
    if (!area) return false;
    return (area.types || []).some(function (t) { return t.allow_virtual_groups; });
  }

  function isVGroupActive(areaSlug) {
    return !!state.vgroups[areaSlug];
  }

  // ── Search state ───────────────────────────────────────────────────────────

  function searchKey(area, placement) { return area + ":" + placement; }

  function getSearch(area, placement) {
    var k = searchKey(area, placement);
    if (!state.search[k]) state.search[k] = { query: "", results: [], loading: false };
    return state.search[k];
  }

  var _debouncedSearch = {};

  function ensureDebounce(areaSlug, placement) {
    var k = searchKey(areaSlug, placement);
    if (!_debouncedSearch[k]) {
      _debouncedSearch[k] = debounce(function (slug, plc, areaData) {
        doSearch(slug, plc, areaData);
      }, 250);
    }
    return _debouncedSearch[k];
  }

  function doSearch(areaSlug, placement, areaData) {
    var k = searchKey(areaSlug, placement);
    var s = getSearch(areaSlug, placement);
    var query = s.query.trim();
    var apiQuery = (query === '*') ? '' : query;  // * = show all

    if (state._ctrl[k]) { state._ctrl[k].abort(); }

    if (!query) {
      s.results = [];
      s.loading = false;
      updateDropdown(areaSlug, placement);
      return;
    }

    var ctrl = new AbortController();
    state._ctrl[k] = ctrl;
    s.loading = true;
    s.results = [];
    updateDropdown(areaSlug, placement);

    var types = areaData.types || [];
    var objectTypes = types.filter(function (t) { return t.kind === "object"; });
    var groupType   = types.find  (function (t) { return t.kind === "group"; });

    var fetches = objectTypes.map(function (type) {
      var url = type.api_url + "?q=" + encodeURIComponent(apiQuery) + "&limit=20&brief=1";
      return fetch(url, {
        signal: ctrl.signal,
        headers: { "Accept": "application/json", "X-CSRFToken": getCsrf() },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          return (data.results || []).map(function (obj) {
            return {
              kind: "object",
              id: String(type.ct_id) + "." + String(obj.id),
              name: obj.display || obj.name || String(obj.id),
              typeName: type.name,
              matchingClass: type.matching_class || "",
            };
          });
        })
        .catch(function (e) {
          if (e.name !== "AbortError") console.warn("NSM picker search error:", e);
          return [];
        });
    });

    // Groups: client-side filter (static list, no API call needed)
    if (groupType && Array.isArray(groupType.entries)) {
      var ql = apiQuery.toLowerCase();
      var groupResults = groupType.entries
        .filter(function (g) { return apiQuery === '' || g.name.toLowerCase().indexOf(ql) !== -1; })
        .map(function (g) { return { kind: "group", id: g.id, name: g.name, typeName: "Group" }; });
      fetches.push(Promise.resolve(groupResults));
    }

    Promise.all(fetches).then(function (perType) {
      if (ctrl.signal.aborted) return;
      s.results = [].concat.apply([], perType);
      s.loading = false;
      updateDropdown(areaSlug, placement);
    });
  }

  // ── Partial DOM update: dropdown ───────────────────────────────────────────

  function updateDropdown(areaSlug, placement) {
    var dropEl = document.querySelector(
      ".nsm-drop[data-area='" + areaSlug + "'][data-placement='" + placement + "']"
    );
    if (!dropEl) return;

    var s = getSearch(areaSlug, placement);

    if (!s.query.trim()) {
      dropEl.innerHTML = "";
      dropEl.hidden = true;
      return;
    }

    if (s.loading) {
      dropEl.innerHTML = "<div class='nsm-drop-msg'>" + t('searching', 'Searching\u2026') + "</div>";
      dropEl.hidden = false;
      return;
    }

    var available = s.results.filter(function (item) {
      return !hasSelection(areaSlug, placement, item.kind, item.id);
    });

    if (!available.length) {
      dropEl.innerHTML = "<div class='nsm-drop-msg'>" + t('no_results', 'No results') + "</div>";
      dropEl.hidden = false;
      return;
    }

    var html = "";
    available.forEach(function (item) {
      var payload = JSON.stringify({
        area: areaSlug, placement: placement,
        kind: item.kind, id: item.id, name: item.name, typeName: item.typeName,
        matchingClass: item.matchingClass || "",
      });
      html += "<div class='nsm-drop-item' data-payload='" + esc(payload) + "'>"
        + "<span class='nsm-drop-name'>" + esc(item.name) + "</span>"
        + "<span class='nsm-drop-type'>" + esc(item.typeName) + "</span>"
        + "</div>";
    });

    dropEl.innerHTML = html;
    dropEl.hidden = false;

    // mousedown fires before blur so the item is captured before focus is lost
    dropEl.querySelectorAll(".nsm-drop-item").forEach(function (el) {
      el.addEventListener("mousedown", function (e) {
        e.preventDefault();
        var p = JSON.parse(el.dataset.payload);
        addSelection(p.area, p.placement, p.kind, p.id, p.name, p.typeName, p.matchingClass);
        var s2 = getSearch(p.area, p.placement);
        s2.query = "";
        s2.results = [];
        var inp = document.querySelector(
          ".nsm-search-input[data-area='" + cssEsc(p.area) + "'][data-placement='" + cssEsc(p.placement) + "']"
        );
        if (inp) inp.value = "";
        updateDropdown(p.area, p.placement);
        renderSelected(p.area, p.placement);
      });
    });
  }

  // ── Partial DOM update: selected list ─────────────────────────────────────

  function renderSelected(areaSlug, placement) {
    var container = document.querySelector(
      ".nsm-selected[data-area='" + cssEsc(areaSlug) + "'][data-placement='" + cssEsc(placement) + "']"
    );
    if (!container) return;
    container.innerHTML = buildSelectedHtml(areaSlug, placement);
  }

  function buildSelectedHtml(areaSlug, placement) {
    var sel = selectionsFor(areaSlug, placement);
    if (!sel.length) {
      return "<div class='nsm-empty'>Keine Auswahl</div>";
    }

    if (areaAllowsVGroups(areaSlug)) {
      return buildVGroupHtml(areaSlug, sel);
    }

    // ── Standard list mode ──
    var html = "<ul class='list-group nsm-sel-list'>";
    sel.forEach(function (s) {
      html += "<li class='list-group-item d-flex justify-content-between align-items-center gap-2 py-1'>"
        + "<div class='d-flex align-items-center gap-2'>"
        + "<input class='form-check-input m-0' type='checkbox'"
        + " data-nsm-cb='1'"
        + " data-area='" + esc(s.area) + "'"
        + " data-placement='" + esc(s.placement) + "'"
        + " data-kind='" + esc(s.kind) + "'"
        + " data-id='" + esc(s.id) + "' />"
        + "<span>" + esc(s.name) + "</span>"
        + (s.typeName
          ? "<span class='text-muted small'>" + esc(s.typeName) + "</span>"
          : "")
        + "</div>"
        + "<div class='d-flex gap-1'>"
        + "<button type='button' class='btn btn-sm btn-link text-danger p-0'"
        + " data-nsm-remove='1'"
        + " data-area='" + esc(s.area) + "'"
        + " data-placement='" + esc(s.placement) + "'"
        + " data-kind='" + esc(s.kind) + "'"
        + " data-id='" + esc(s.id) + "'"
        + " title='" + t('remove', 'Remove') + "'>\u00d7</button>"
        + "</div>"
        + "</li>";
    });
    html += "</ul>";
    html += "<div class='mt-1 d-flex justify-content-end'>"
      + "<button type='button' class='btn btn-sm btn-outline-danger'"
      + " data-nsm-del-checked='1'"
      + " data-area='" + esc(areaSlug) + "'"
      + " data-placement='" + esc(placement) + "'>" + t('remove_selected', 'Remove selected') + "</button>"
      + "</div>";
    return html;
  }

  function buildVGroupHtml(areaSlug, sel) {
    var isGrouped = isVGroupActive(areaSlug);
    var html = "<div class='nsm-vgroup-toggle mb-2 p-2 rounded border" + (isGrouped ? " border-primary bg-primary-subtle" : "") + "'>"
      + "<div class='form-check'>"
      + "<input class='form-check-input' type='checkbox' id='nsm-vg-" + esc(areaSlug) + "'"
      + " data-nsm-vg-toggle='1'"
      + " data-area='" + esc(areaSlug) + "'"
      + (isGrouped ? " checked" : "") + ">"
      + "<label class='form-check-label small' for='nsm-vg-" + esc(areaSlug) + "'>"
      + t('as_group', 'As group') + " <span class='text-muted'>(AND \u2014 display: <em>Label1 | Label2</em>)</span>"
      + (isGrouped ? " <span class='badge bg-primary'>" + t('active', 'Active') + "</span>" : "")
      + "</label>"
      + "</div>"
      + "</div>";

    if (!sel.length) {
      html += "<div class='nsm-empty'>" + t('no_selection', 'No selection') + "</div>";
      return html;
    }

    // Items list (same as standard mode)
    var borderClass = isGrouped ? " border-start border-primary ps-2" : "";
    html += "<ul class='list-group nsm-sel-list" + borderClass + "'>";
    sel.forEach(function (s) {
      html += "<li class='list-group-item d-flex justify-content-between align-items-center gap-2 py-1'>"
        + "<div class='d-flex align-items-center gap-2'>"
        + "<span>" + esc(s.name) + "</span>"
        + (s.typeName
          ? "<span class='text-muted small'>" + esc(s.typeName) + "</span>"
          : "")
        + "</div>"
        + "<button type='button' class='btn btn-sm btn-link text-danger p-0'"
        + " data-nsm-remove='1'"
        + " data-area='" + esc(s.area) + "'"
        + " data-placement='" + esc(s.placement) + "'"
        + " data-kind='" + esc(s.kind) + "'"
        + " data-id='" + esc(s.id) + "'"
        + " title='" + t('remove', 'Remove') + "'>\u00d7</button>"
        + "</li>";
    });
    html += "</ul>";
    return html;
  }

  // ── Styles ─────────────────────────────────────────────────────────────────

  function ensureStyles() {
    if (document.getElementById("nsm-rule-style")) return;
    var s = document.createElement("style");
    s.id = "nsm-rule-style";
    s.textContent = [
      ".nsm-hidden-pickers { display: none; }",
      ".nsm-area-card { margin-bottom: 1.25rem; }",
      ".nsm-search-wrap { position: relative; margin-bottom: .5rem; }",
      ".nsm-search-input { width: 100%; }",
      ".nsm-drop {",
      "  position: absolute; top: 100%; left: 0; right: 0; z-index: 1050;",
      "  background: var(--bs-dropdown-bg, #fff);",
      "  color: var(--bs-dropdown-color, #212529);",
      "  border: 1px solid var(--bs-dropdown-border-color, #dee2e6);",
      "  border-radius: 4px; max-height: 220px; overflow-y: auto;",
      "  box-shadow: 0 4px 12px rgba(0,0,0,.15);",
      "}",
      ".nsm-drop-item {",
      "  padding: 5px 10px; cursor: pointer; color: var(--bs-dropdown-link-color, inherit);",
      "  display: flex; justify-content: space-between; align-items: center; gap: 8px;",
      "}",
      ".nsm-drop-item:hover { background: var(--bs-dropdown-link-hover-bg, #e9ecef); color: var(--bs-dropdown-link-hover-color, inherit); }",
      ".nsm-drop-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1 1 auto; }",
      ".nsm-drop-type { font-size: .72rem; color: var(--bs-secondary-color, #6c757d); white-space: nowrap; flex-shrink: 0; }",
      ".nsm-drop-msg { padding: 8px 10px; color: var(--bs-dropdown-color, #6c757d); font-style: italic; font-size: .85rem; }",
      ".nsm-selected { min-height: 2rem; margin-top: .5rem; }",
      ".nsm-empty { color: var(--bs-secondary-color, #6c757d); font-style: italic; padding: .4rem 0; }",
      ".nsm-sel-list { margin: 0; }",
      ".nsm-hint { font-size: .8rem; color: var(--bs-secondary-color, #6c757d); margin-bottom: .4rem; }",
      ".nsm-hint-tip { font-size: .72rem; opacity: .7; margin-bottom: .35rem; }",
      ".nsm-vgroup-toggle { font-size: .9rem; }",
    ].join("\n");
    document.head.appendChild(s);
  }

  // ── Full render ────────────────────────────────────────────────────────────

  function activeAreaSlug() {
    return state.ui.__activeArea
      || (state.data.areas[0] && state.data.areas[0].slug)
      || "";
  }

  function setActiveArea(slug) { state.ui.__activeArea = slug; }

  function renderAreaTabs() {
    var html = "<ul class='nav nav-tabs mb-3'>";
    state.data.areas.forEach(function (area) {
      var active = area.slug === activeAreaSlug() ? " active" : "";
      html += "<li class='nav-item'>"
        + "<button type='button' class='nav-link" + active + "'"
        + " data-nsm-area='" + esc(area.slug) + "'>"
        + esc(area.display_name || area.name)
        + "</button></li>";
    });
    html += "</ul>";
    return html;
  }

  function renderColumn(area, placement) {
    var badge = placement === "source"
      ? "text-bg-primary"
      : (placement === "destination" ? "text-bg-info" : "text-bg-secondary");
    var label = placement === "source"
      ? "Source"
      : (placement === "destination" ? "Destination" : (area.display_name || area.name));

    var types = area.types || [];
    var typeNames = types
      .filter(function (t) { return t.kind === "object"; })
      .map(function (t) { return t.name; });
    var hasGroups = types.some(function (t) { return t.kind === "group"; });
    if (hasGroups) typeNames.push(t('groups', 'Groups'));

    var placeholder = typeNames.length
      ? t('search_in', 'Search in') + ": " + typeNames.join(", ") + "\u2026"
      : t('search', 'Search') + "\u2026";
    var s = getSearch(area.slug, placement);

    return "<div class='mb-3'>"
      + (typeNames.length
        ? "<div class='nsm-hint'>" + t('types', 'Types') + ": " + esc(typeNames.join(", ")) + "</div>"
        : "")
      + "<div class='nsm-hint nsm-hint-tip'><i class='mdi mdi-lightbulb-outline me-1'></i>" + t('search_tip', 'Tip: type * to show all') + "</div>"
      + "<div class='nsm-search-wrap'>"
      + "<input type='search' class='form-control form-control-sm nsm-search-input'"
      + " autocomplete='off'"
      + " data-area='" + esc(area.slug) + "'"
      + " data-placement='" + esc(placement) + "'"
      + " placeholder='" + esc(placeholder) + "'"
      + " value='" + esc(s.query) + "' />"
      + "<div class='nsm-drop'"
      + " data-area='" + esc(area.slug) + "'"
      + " data-placement='" + esc(placement) + "'"
      + " hidden></div>"
      + "</div>"
      + "<div class='nsm-selected'"
      + " data-area='" + esc(area.slug) + "'"
      + " data-placement='" + esc(placement) + "'>"
      + buildSelectedHtml(area.slug, placement)
      + "</div>"
      + "</div>";
  }

  function renderActiveArea() {
    var slug = activeAreaSlug();
    var area = state.data.areas.find(function (a) { return a.slug === slug; })
      || state.data.areas[0];
    if (!area) return "";
    var placement = (area.slug === "source" || area.slug === "destination")
      ? area.slug
      : "fixed";
    return "<div class='card nsm-area-card'>"
      + "<div class='card-header'>" + esc(area.display_name || area.name) + "</div>"
      + "<div class='card-body'>" + renderColumn(area, placement) + "</div>"
      + "</div>";
  }

  function render() {
    var root = pickerEl();
    if (!root) return;

    if (!state.data.areas.length) {
      root.innerHTML = "<div class='alert alert-warning'>Keine Areas konfiguriert. Bitte zuerst im Object-Builder konfigurieren.</div>";
      return;
    }

    if (!activeAreaSlug() && state.data.areas.length) {
      setActiveArea(state.data.areas[0].slug);
    }

    root.innerHTML = renderAreaTabs() + renderActiveArea();
    bindAreaTabs(root);
    bindSearchInputs(root);

    // Re-open any active dropdown after re-render
    var slug = activeAreaSlug();
    var area = state.data.areas.find(function (a) { return a.slug === slug; });
    if (area) {
      var placement = (area.slug === "source" || area.slug === "destination") ? area.slug : "fixed";
      if (getSearch(slug, placement).query.trim()) {
        updateDropdown(slug, placement);
      }
    }
  }

  // ── Event binding ──────────────────────────────────────────────────────────

  function bindAreaTabs(root) {
    root.querySelectorAll("button[data-nsm-area]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setActiveArea(btn.dataset.nsmArea);
        render();
      });
    });
  }

  function bindSearchInputs(root) {
    root.querySelectorAll("input.nsm-search-input").forEach(function (inp) {
      var areaSlug  = inp.dataset.area;
      var placement = inp.dataset.placement;
      var area = state.data.areas.find(function (a) { return a.slug === areaSlug; });
      if (!area) return;

      var debouncedFn = ensureDebounce(areaSlug, placement);

      inp.addEventListener("input", function () {
        getSearch(areaSlug, placement).query = inp.value;
        debouncedFn(areaSlug, placement, area);
      });

      // Hide dropdown shortly after blur so mousedown on item can fire first
      inp.addEventListener("blur", function () {
        setTimeout(function () {
          var dropEl = document.querySelector(
            ".nsm-drop[data-area='" + areaSlug + "'][data-placement='" + placement + "']"
          );
          if (dropEl) dropEl.hidden = true;
        }, 200);
      });

      // Re-show dropdown on re-focus if query is present
      inp.addEventListener("focus", function () {
        if (getSearch(areaSlug, placement).query.trim()) {
          updateDropdown(areaSlug, placement);
        }
      });
    });
  }

  // Delegated click events on the root (survive inner re-renders)
  function bindRootDelegation() {
    var root = pickerEl();
    if (!root || root.dataset.nsmDelegate === "1") return;
    root.dataset.nsmDelegate = "1";

    // ── VGroup toggle (change event) ──
    root.addEventListener("change", function (e) {
      var toggle = e.target.closest("[data-nsm-vg-toggle]");
      if (toggle) {
        var area = toggle.dataset.area;
        if (toggle.checked) {
          state.vgroups[area] = true;
        } else {
          delete state.vgroups[area];
        }
        syncHidden();
        var placement = _placementForAreaSlug(area);
        renderSelected(area, placement);
        return;
      }
    });

    root.addEventListener("click", function (e) {
      // ── Standard: remove item ──
      var removeBtn = e.target.closest("[data-nsm-remove]");
      if (removeBtn) {
        removeSelection(
          removeBtn.dataset.area, removeBtn.dataset.placement,
          removeBtn.dataset.kind, removeBtn.dataset.id
        );
        renderSelected(removeBtn.dataset.area, removeBtn.dataset.placement);
        updateDropdown(removeBtn.dataset.area, removeBtn.dataset.placement);
        return;
      }

      // ── Standard: delete checked ──
      var delBtn = e.target.closest("[data-nsm-del-checked]");
      if (delBtn) {
        var area = delBtn.dataset.area;
        var placement = delBtn.dataset.placement;
        var container = root.querySelector(
          ".nsm-selected[data-area='" + cssEsc(area) + "'][data-placement='" + cssEsc(placement) + "']"
        );
        if (container) {
          container.querySelectorAll("input[data-nsm-cb]:checked").forEach(function (cb) {
            removeSelection(cb.dataset.area, cb.dataset.placement, cb.dataset.kind, cb.dataset.id);
          });
        }
        renderSelected(area, placement);
        updateDropdown(area, placement);
      }
    });
  }

  function _placementForAreaSlug(areaSlug) {
    if (areaSlug === "source" || areaSlug === "destination") return areaSlug;
    return "fixed";
  }

  // ── Init ───────────────────────────────────────────────────────────────────

  function init() {
    var picker = pickerEl();
    if (!picker || picker.dataset.nsmReady === "1") return;

    ensureStyles();
    state.data       = getPickerData();
    state.selections = {};
    state.ui         = {};
    state.search     = {};
    state._ctrl      = {};
    state.vgroups    = {};
    state.chipSel    = {};

    loadInitialSelections();
    loadInitialVGroups();
    syncHidden();
    render();
    bindRootDelegation();

    picker.dataset.nsmReady = "1";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  document.addEventListener("htmx:load", init);
  window.addEventListener("load", init);
})();

