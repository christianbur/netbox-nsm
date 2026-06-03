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
    ui: { __activeArea: "", __selectedType: {} },
    browse: {},
    _ctrl: {},
    vgroups: {},
  };

  function getSelectedType(areaSlug, placement) {
    return state.ui.__selectedType[areaSlug + ":" + placement] || null;
  }

  function setSelectedType(areaSlug, placement, typeObj) {
    state.ui.__selectedType[areaSlug + ":" + placement] = typeObj || null;
  }

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

  // ── Browse state ───────────────────────────────────────────────────────────
  // Each entry: { items:[], total:0, offset:0, loading:false, query:"" }

  function getBrowse(area, placement) {
    var k = searchKey(area, placement);
    if (!state.browse[k]) state.browse[k] = { items: [], total: 0, offset: 0, loading: false, query: "" };
    return state.browse[k];
  }

  var _debouncedBrowse = {};

  function ensureBrowseDebounce(areaSlug, placement) {
    var k = searchKey(areaSlug, placement);
    if (!_debouncedBrowse[k]) {
      _debouncedBrowse[k] = debounce(function (slug, plc, areaData) {
        loadBrowse(slug, plc, areaData, false);
      }, 300);
    }
    return _debouncedBrowse[k];
  }

  var BROWSE_LIMIT = 10;

  function loadBrowse(areaSlug, placement, areaData, append) {
    var k = searchKey(areaSlug, placement);
    var b = getBrowse(areaSlug, placement);

    if (!append) {
      b.items   = [];
      b.offset  = 0;
      b.total   = 0;
    }
    if (b.loading) return;
    b.loading = true;
    updateBrowseList(areaSlug, placement);

    if (state._ctrl[k]) { state._ctrl[k].abort(); }
    var ctrl = new AbortController();
    state._ctrl[k] = ctrl;

    var types = areaData.types || [];
    var allObjectTypes = types.filter(function (t) { return t.kind === "object"; });
    var groupType = types.find(function (t) { return t.kind === "group"; });

    var selectedType = getSelectedType(areaSlug, placement);
    var objectTypes = (selectedType && selectedType.kind === "object")
      ? allObjectTypes.filter(function (t) { return t.ct_id === selectedType.ct_id; })
      : allObjectTypes;
    var loadGroups = selectedType ? (selectedType.kind === "group") : !!groupType;

    var query = b.query.trim();
    var apiQuery = (query === "*") ? "" : query;

    var fetches = objectTypes.map(function (type) {
      var url = type.api_url
        + "?limit=" + BROWSE_LIMIT
        + "&offset=" + b.offset
        + (apiQuery ? "&q=" + encodeURIComponent(apiQuery) : "")
        + "&brief=1";
      return fetch(url, {
        signal: ctrl.signal,
        headers: { "Accept": "application/json", "X-CSRFToken": getCsrf() },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          return {
            items: (data.results || []).map(function (obj) {
              return {
                kind: "object",
                id: String(type.ct_id) + "." + String(obj.id),
                name: obj.display || obj.name || String(obj.id),
                typeName: type.name,
                matchingClass: type.matching_class || "",
              };
            }),
            count: data.count || 0,
          };
        })
        .catch(function (e) {
          if (e.name !== "AbortError") console.warn("NSM picker browse error:", e);
          return { items: [], count: 0 };
        });
    });

    // Groups: client-side filter on static list
    if (loadGroups && groupType && Array.isArray(groupType.entries)) {
      var ql = apiQuery.toLowerCase();
      var filtered = apiQuery
        ? groupType.entries.filter(function (g) { return g.name.toLowerCase().indexOf(ql) !== -1; })
        : groupType.entries;
      var page = filtered.slice(b.offset, b.offset + BROWSE_LIMIT)
        .map(function (g) { return { kind: "group", id: g.id, name: g.name, typeName: "Group", matchingClass: "" }; });
      fetches.push(Promise.resolve({ items: page, count: filtered.length }));
    }

    Promise.all(fetches).then(function (perType) {
      if (ctrl.signal.aborted) return;
      var allNew = [].concat.apply([], perType.map(function (r) { return r.items; }));
      var maxCount = Math.max.apply(null, [0].concat(perType.map(function (r) { return r.count; })));
      b.items  = append ? b.items.concat(allNew) : allNew;
      b.total  = maxCount;
      b.offset = b.items.length;
      b.loading = false;
      updateBrowseList(areaSlug, placement);
    });
  }

  // ── Partial DOM update: browse list ───────────────────────────────────────

  function updateBrowseList(areaSlug, placement) {
    var listEl = document.querySelector(
      ".nsm-browse-list[data-area='" + cssEsc(areaSlug) + "'][data-placement='" + cssEsc(placement) + "']"
    );
    if (!listEl) return;

    var b = getBrowse(areaSlug, placement);
    var available = b.items.filter(function (item) {
      return !hasSelection(areaSlug, placement, item.kind, item.id);
    });

    var html = "";
    if (!b.items.length && b.loading) {
      html = "<div class='nsm-drop-msg'>" + t("searching", "Searching\u2026") + "</div>";
    } else if (!available.length && !b.loading) {
      html = "<div class='nsm-drop-msg'>" + t("no_results", "No results") + "</div>";
    } else {
      available.forEach(function (item) {
        var payload = JSON.stringify({
          area: areaSlug, placement: placement,
          kind: item.kind, id: item.id, name: item.name,
          typeName: item.typeName, matchingClass: item.matchingClass || "",
        });
        html += "<div class='nsm-browse-item' data-payload='" + esc(payload) + "'>"
          + "<span class='nsm-drop-name'>" + esc(item.name) + "</span>"
          + "<span class='nsm-drop-type'>" + esc(item.typeName) + "</span>"
          + "</div>";
      });
      if (b.loading) {
        html += "<div class='nsm-drop-msg'>" + t("searching", "Searching\u2026") + "</div>";
      } else if (b.offset < b.total) {
        html += "<div class='nsm-browse-more'"
          + " data-area='" + esc(areaSlug) + "'"
          + " data-placement='" + esc(placement) + "'>"
          + "Mehr laden\u2026 (" + b.offset + " / " + b.total + ")"
          + "</div>";
      }
    }

    listEl.innerHTML = html;

    listEl.querySelectorAll(".nsm-browse-item").forEach(function (el) {
      el.addEventListener("mouseenter", function () { el.classList.add("active"); });
      el.addEventListener("mouseleave", function () { el.classList.remove("active"); });
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
      /* TomSelect wrapper: match Tabler form-select sizing exactly */
      ".nsm-ts-wrap { height: auto !important; padding: 0 !important; cursor: text; margin-bottom: .5rem; }",
      /* padding-right: 2.25rem leaves room for the form-select chevron arrow */
      ".nsm-ts-wrap .ts-control { padding: calc(.4375rem - 1px) 2.25rem calc(.4375rem - 1px) .75rem; min-height: auto; gap: 0; flex-wrap: nowrap; align-items: center; }",
      ".nsm-ts-wrap .ts-control input.nsm-search-input { flex: 1 1 auto; min-width: 0; margin: 0; border: 0; padding: 0; background: transparent; outline: none; color: inherit; font-size: inherit; line-height: 1.25rem; box-shadow: none; }",
      /* Type picker */
      ".nsm-ts-type-wrap { height: auto !important; padding: 0 !important; cursor: pointer; margin-bottom: .5rem; }",
      ".nsm-ts-type-wrap .ts-control { padding: calc(.4375rem - 1px) 2.25rem calc(.4375rem - 1px) .75rem; min-height: auto; display: flex; align-items: center; user-select: none; }",
      ".nsm-type-placeholder { opacity: .6; }",
      /* Dropdown: ts-dropdown CSS handles bg/border/shadow/position; we just set width */
      ".nsm-drop { width: 100%; }",
      ".nsm-drop .ts-dropdown-content { max-height: 220px; overflow-y: auto; }",
      /* Browse list – always visible, flows in document */
      ".nsm-browse-list { border: 1px solid var(--tblr-border-color, rgba(99,108,148,.25)); border-radius: var(--tblr-border-radius, .375rem); background: var(--tblr-bg-surface, #1c2333); max-height: 220px; overflow-y: auto; margin-bottom: .5rem; }",
      ".nsm-browse-item { padding: .375rem .75rem; cursor: pointer; display: flex; justify-content: space-between; align-items: center; gap: 8px; }",
      ".nsm-browse-item.active { background: rgba(var(--tblr-primary-rgb, 0,242,212), .12); }",
      ".nsm-browse-more { padding: .3rem .75rem; font-size: .8rem; color: var(--tblr-primary, #00F2D4); cursor: pointer; text-align: center; border-top: 1px solid var(--tblr-border-color, rgba(99,108,148,.2)); }",
      ".nsm-browse-more:hover { text-decoration: underline; }",
      ".nsm-drop .option { display: flex; justify-content: space-between; align-items: center; gap: 8px; }",
      ".nsm-type-drop .option { display: block; }",
      ".nsm-drop-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1 1 auto; }",
      ".nsm-drop-type { font-size: .72rem; opacity: .75; white-space: nowrap; flex-shrink: 0; }",
      ".nsm-drop-msg { padding: .5rem .75rem; color: var(--tblr-secondary-color, #6c757d); font-style: italic; font-size: .85rem; }",
      ".nsm-selected { min-height: 2rem; margin-top: .5rem; }",
      ".nsm-empty { color: var(--tblr-secondary-color, #6c757d); font-style: italic; padding: .4rem 0; }",
      ".nsm-sel-list { margin: 0; }",
      ".nsm-hint { font-size: .8rem; color: var(--tblr-secondary-color, #6c757d); margin-bottom: .4rem; }",
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
    var types = area.types || [];
    var objectTypes = types.filter(function (tp) { return tp.kind === "object"; });
    var groupType   = types.find  (function (tp) { return tp.kind === "group"; });
    var pickerTypes = objectTypes.slice();
    if (groupType) pickerTypes.push({ kind: "group", name: t('groups', 'Groups'), ct_id: null });

    // Auto-select if only one type
    if (pickerTypes.length === 1 && !getSelectedType(area.slug, placement)) {
      setSelectedType(area.slug, placement, pickerTypes[0]);
    }
    var selectedType = getSelectedType(area.slug, placement);

    var html = "<div class='mb-3'>";

    // ── Type picker (only if >1 type) ──────────────────────────────────────
    if (pickerTypes.length > 1) {
      html += "<div class='ts-wrapper form-select single nsm-ts-type-wrap mb-2'"
        + " data-area='" + esc(area.slug) + "'"
        + " data-placement='" + esc(placement) + "'>"
        + "<div class='ts-control nsm-type-control'>";
      if (selectedType) {
        html += "<span class='nsm-type-selected'>" + esc(selectedType.name) + "</span>";
      } else {
        html += "<span class='nsm-type-placeholder text-muted'>" + esc(t('select_type', 'Select type\u2026')) + "</span>";
      }
      html += "</div>"
        + "<div class='ts-dropdown single nsm-type-drop' hidden>"
        + "<div class='ts-dropdown-content'>";
      pickerTypes.forEach(function (tp) {
        var isSel = selectedType && selectedType.name === tp.name;
        html += "<div class='option" + (isSel ? " selected active" : "") + "'"
          + " data-nsm-type-pick='1'"
          + " data-area='" + esc(area.slug) + "'"
          + " data-placement='" + esc(placement) + "'"
          + " data-type-kind='" + esc(tp.kind) + "'"
          + " data-type-ctid='" + esc(tp.ct_id || '') + "'"
          + " data-type-name='" + esc(tp.name) + "'>"
          + esc(tp.name)
          + "</div>";
      });
      html += "</div></div></div>";
    }

    // ── Search box (hidden until type selected when >1 type) ───────────────
    var searchHidden = (pickerTypes.length > 1 && !selectedType);
    var placeholder = selectedType
      ? t('search_in', 'Search in') + ": " + selectedType.name + "\u2026"
      : t('search', 'Search') + "\u2026";

    html += "<div class='ts-wrapper form-select single nsm-ts-wrap'"
      + (searchHidden ? " hidden" : "") + ">"
      + "<div class='ts-control'>"
      + "<input type='text' class='nsm-search-input'"
      + " autocomplete='off'"
      + " data-area='" + esc(area.slug) + "'"
      + " data-placement='" + esc(placement) + "'"
      + " placeholder='" + esc(placeholder) + "'"
      + " value='" + esc(getBrowse(area.slug, placement).query) + "' />"
      + "</div>"
      + "</div>";

    // ── Browse list (always visible once type selected / single type) ──────
    html += "<div class='nsm-browse-list'"
      + (searchHidden ? " hidden" : "")
      + " data-area='" + esc(area.slug) + "'"
      + " data-placement='" + esc(placement) + "'>"
      + "<div class='nsm-drop-msg'>" + t("searching", "Searching\u2026") + "</div>"
      + "</div>";

    html += "<div class='nsm-hint nsm-hint-tip mt-1'>"
      + "<i class='mdi mdi-lightbulb-outline me-1'></i>"
      + t('search_tip', 'Type to filter the list')
      + "</div>";

    html += "<div class='nsm-selected'"
      + " data-area='" + esc(area.slug) + "'"
      + " data-placement='" + esc(placement) + "'>"
      + buildSelectedHtml(area.slug, placement)
      + "</div>"
      + "</div>";

    return html;
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

    // Trigger initial browse load for the active area
    var slug = activeAreaSlug();
    var area = state.data.areas.find(function (a) { return a.slug === slug; });
    if (area) {
      var placement = _placementForAreaSlug(slug);
      loadBrowse(slug, placement, area, false);
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

      var debouncedFn = ensureBrowseDebounce(areaSlug, placement);

      inp.addEventListener("input", function () {
        getBrowse(areaSlug, placement).query = inp.value;
        debouncedFn(areaSlug, placement, area);
      });

      inp.addEventListener("focus", function () {
        var wrap = inp.closest(".nsm-ts-wrap");
        if (wrap) wrap.classList.add("focus", "input-active");
      });

      inp.addEventListener("blur", function () {
        var wrap = inp.closest(".nsm-ts-wrap");
        if (wrap) wrap.classList.remove("focus", "input-active");
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
      // ── Type picker: toggle dropdown ──
      var typeWrap = e.target.closest(".nsm-ts-type-wrap");
      if (typeWrap && !e.target.closest(".nsm-type-drop")) {
        var typeDrop = typeWrap.querySelector(".nsm-type-drop");
        if (typeDrop) {
          typeDrop.hidden = !typeDrop.hidden;
          typeWrap.classList.toggle("focus", !typeDrop.hidden);
        }
        return;
      }

      // ── Type picker: select option ──
      var typePick = e.target.closest("[data-nsm-type-pick]");
      if (typePick) {
        var tpArea = typePick.dataset.area;
        var tpPlacement = typePick.dataset.placement;
        var tpObj = {
          kind: typePick.dataset.typeKind,
          ct_id: typePick.dataset.typeCtid ? parseInt(typePick.dataset.typeCtid) : null,
          name: typePick.dataset.typeName,
        };
        setSelectedType(tpArea, tpPlacement, tpObj);
        // Reset search for this area
        // Reset browse state for this area when type changes
        var bk = searchKey(tpArea, tpPlacement);
        state.browse[bk] = { items: [], total: 0, offset: 0, loading: false, query: "" };
        // Re-render column
        render();
        return;
      }

      // ── Close type drop when clicking outside ──
      if (!e.target.closest(".nsm-ts-type-wrap")) {
        root.querySelectorAll(".nsm-type-drop:not([hidden])").forEach(function (d) {
          d.hidden = true;
          var w = d.closest(".nsm-ts-type-wrap");
          if (w) w.classList.remove("focus");
        });
      }

      // ── Browse list: select item ──
      var browseItem = e.target.closest(".nsm-browse-item");
      if (browseItem) {
        var p = JSON.parse(browseItem.dataset.payload);
        addSelection(p.area, p.placement, p.kind, p.id, p.name, p.typeName, p.matchingClass);
        renderSelected(p.area, p.placement);
        updateBrowseList(p.area, p.placement);
        return;
      }

      // ── Browse list: load more ──
      var loadMoreBtn = e.target.closest(".nsm-browse-more");
      if (loadMoreBtn) {
        var lmArea = loadMoreBtn.dataset.area;
        var lmPlacement = loadMoreBtn.dataset.placement;
        var lmAreaData = state.data.areas.find(function (a) { return a.slug === lmArea; });
        if (lmAreaData) loadBrowse(lmArea, lmPlacement, lmAreaData, true);
        return;
      }

      // ── Standard: remove item ──
      var removeBtn = e.target.closest("[data-nsm-remove]");
      if (removeBtn) {
        removeSelection(
          removeBtn.dataset.area, removeBtn.dataset.placement,
          removeBtn.dataset.kind, removeBtn.dataset.id
        );
        renderSelected(removeBtn.dataset.area, removeBtn.dataset.placement);
        updateBrowseList(removeBtn.dataset.area, removeBtn.dataset.placement);
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
        updateBrowseList(area, placement);
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
    state.ui         = { __activeArea: "", __selectedType: {} };
    state.browse     = {};
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

