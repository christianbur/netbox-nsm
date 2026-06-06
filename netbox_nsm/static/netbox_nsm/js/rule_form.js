/* NSM Rule Picker – server-side browse via NSM API
 *
 * Data format from server (nsm-rule-picker-catalog):
 * { areas: [{ slug, name, display_name, sort_order, types: [
 *   { name, ct_id, kind:"object", name_filter_regex? }
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

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  var _nameFilterRegexCache = {};

  function compileNameFilter(pattern) {
    if (!pattern) return null;
    if (Object.prototype.hasOwnProperty.call(_nameFilterRegexCache, pattern)) {
      return _nameFilterRegexCache[pattern];
    }
    try {
      _nameFilterRegexCache[pattern] = new RegExp(pattern);
    } catch (e) {
      _nameFilterRegexCache[pattern] = false;
    }
    return _nameFilterRegexCache[pattern];
  }

  function objectNameMatches(type, name) {
    var re = compileNameFilter(type && type.name_filter_regex);
    if (re === null || re === false) return true;
    return re.test(String(name || ""));
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

  function getPickerBrowseUrl() {
    var url = window.NSM_PICKER_BROWSE_URL;
    if (url) return url;
    return "/plugins/netbox-nsm/api/picker-browse/";
  }

  function getActiveBranchSchemaId() {
    if (window.NSM_ACTIVE_BRANCH) {
      return String(window.NSM_ACTIVE_BRANCH).trim();
    }
    var m = document.cookie.match(/(?:^|;\s*)active_branch=([^;]+)/);
    return m ? decodeURIComponent(m[1].trim()) : "";
  }

  function withBranchQuery(url) {
    var branch = getActiveBranchSchemaId();
    if (!branch) return url;
    var sep = url.indexOf("?") >= 0 ? "&" : "?";
    return url + sep + "_branch=" + encodeURIComponent(branch);
  }

  function apiFetch(url, options) {
    if (window.NSM_BRANCH_API && window.NSM_BRANCH_API.fetch) {
      return window.NSM_BRANCH_API.fetch(url, options);
    }
    options = options || {};
    options.headers = options.headers || {};
    options.credentials = options.credentials || "same-origin";
    return fetch(url, options);
  }

  function buildTypeBrowseUrl(type, apiQuery, offset, rawQuery) {
    var qParam = apiQuery ? encodeURIComponent(apiQuery) : "";
    if (!qParam && rawQuery === "*") {
      qParam = encodeURIComponent("*");
    }
    var browseBase = getPickerBrowseUrl();
    if (browseBase && type.ct_id) {
      return withBranchQuery(
        browseBase
          + "?ct=" + encodeURIComponent(type.ct_id)
          + "&limit=" + BROWSE_LIMIT
          + "&offset=" + offset
          + (qParam ? "&q=" + qParam : "")
      );
    }
    if (type.api_url) {
      return withBranchQuery(
        type.api_url
          + "?limit=" + BROWSE_LIMIT
          + "&offset=" + offset
          + (qParam ? "&q=" + qParam : "")
          + "&brief=1"
      );
    }
    return "";
  }

  function fetchBrowseType(type, apiQuery, offset, rawQuery, ctrl) {
    var nsmUrl = buildTypeBrowseUrl(type, apiQuery, offset, rawQuery);
    var restUrl = type.api_url
      ? withBranchQuery(
        type.api_url
          + "?limit=" + BROWSE_LIMIT
          + "&offset=" + offset
          + (apiQuery ? "&q=" + encodeURIComponent(apiQuery) : (rawQuery === "*" ? "&q=" + encodeURIComponent("*") : ""))
          + "&brief=1"
      )
      : "";

    function mapResponse(data) {
      var mapped = (data.results || []).map(function (obj) {
        var label = obj.display || obj.name || String(obj.id);
        return {
          kind: "object",
          id: String(type.ct_id) + "." + String(obj.id),
          name: label,
          typeName: type.name,
          matchingClass: type.matching_class || "",
          color: obj.color || "",
        };
      }).filter(function (item) {
        return objectNameMatches(type, item.name);
      });
      var total = typeof data.count === "number" ? data.count : mapped.length;
      return { items: mapped, count: total };
    }

    function doFetch(url, useRest) {
      var fetchFn = apiFetch;
      return fetchFn(url, {
        signal: ctrl.signal,
        headers: {
          Accept: "application/json",
          "X-CSRFToken": getCsrf(),
        },
      })
        .then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .then(mapResponse);
    }

    if (!nsmUrl && !restUrl) {
      return Promise.resolve({ items: [], count: 0 });
    }

    var useNsm = nsmUrl && type.ct_id && getPickerBrowseUrl();
    if (useNsm) {
      return doFetch(nsmUrl, false).catch(function (e) {
        if (e.name === "AbortError") throw e;
        if (!restUrl) {
          console.warn("NSM picker browse error:", e);
          return { items: [], count: 0 };
        }
        console.warn("NSM picker browse failed, falling back to REST:", e);
        return doFetch(restUrl, true);
      });
    }
    return doFetch(restUrl, true).catch(function (e) {
      if (e.name !== "AbortError") console.warn("NSM picker REST error:", e);
      return { items: [], count: 0 };
    });
  }

  function pickerFetch(url, options) {
    options = options || {};
    options.headers = options.headers || {};
    options.credentials = options.credentials || "same-origin";
    return fetch(url, options);
  }

  // ── Picker data ────────────────────────────────────────────────────────────

  function getPickerCatalog() {
    var el = document.getElementById("nsm-rule-picker-catalog");
    if (!el) return {};
    try {
      var raw = JSON.parse(el.textContent);
      return raw && typeof raw === "object" ? raw : {};
    } catch (_) {
      return {};
    }
  }

  function getRulebookField() {
    return document.getElementById("id_rulebook")
      || document.querySelector('select[name="rulebook"]');
  }

  function getInitialRulebookId() {
    var host = pickerEl();
    if (!host || !host.dataset.nsmInitialRulebook) return "";
    return String(host.dataset.nsmInitialRulebook);
  }

  function getSelectedRulebookId() {
    var field = getRulebookField();
    if (!field) return getInitialRulebookId();
    if (field.tomselect) {
      var tv = field.tomselect.getValue();
      if (tv) {
        return String(Array.isArray(tv) ? tv[0] : tv);
      }
    }
    if (field.value) return String(field.value);
    return getInitialRulebookId();
  }

  function syncPickerHint() {
    var hint = document.getElementById("nsm-rule-picker-hint");
    if (!hint) return;
    var showHint = !getSelectedRulebookId() || !state.data.areas.length;
    hint.classList.toggle("d-none", !showHint);
  }

  function typeKeyFromObj(tp) {
    if (!tp) return "";
    if (tp.kind === "group") return "group";
    return "object:" + String(tp.ct_id || "");
  }

  function typeObjFromKey(val, pickerTypes) {
    if (!val) return null;
    for (var i = 0; i < pickerTypes.length; i++) {
      if (typeKeyFromObj(pickerTypes[i]) === val) return pickerTypes[i];
    }
    return null;
  }

  function typeOptionLabel(tp) {
    var label = tp.name || "";
    if (tp.matching_class) label += " (" + tp.matching_class + ")";
    return label;
  }

  function pickerDataForRulebook(rbId) {
    if (!rbId) return { areas: [] };
    var catalog = getPickerCatalog();
    var data = catalog[rbId];
    if (data && Array.isArray(data.areas)) return data;
    return { areas: [] };
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
          color: sel.color || "",
          exclude: !!sel.exclude,
        };
      });
    } catch (_) {}
  }

  function typeNameFromCatalog(areaSlug, kind, id, fallback) {
    if (kind === "group") {
      return t("groups", "Groups");
    }
    if (kind !== "object") {
      return fallback || "";
    }
    var parts = String(id || "").split(".");
    if (parts.length < 2) {
      return fallback || "";
    }
    var ctId = parts[0];
    var area = (state.data.areas || []).find(function (a) {
      return a.slug === areaSlug;
    });
    if (!area) {
      return fallback || "";
    }
    var match = (area.types || []).find(function (tp) {
      return tp.kind === "object" && String(tp.ct_id) === String(ctId);
    });
    return match && match.name ? match.name : (fallback || "");
  }

  function normalizeSelectionTypeNames() {
    Object.keys(state.selections).forEach(function (key) {
      var s = state.selections[key];
      var resolved = typeNameFromCatalog(
        s.area, s.kind, s.id, s.typeName || ""
      );
      if (resolved) {
        s.typeName = resolved;
      }
    });
  }

  function displayTypeName(sel) {
    return typeNameFromCatalog(
      sel.area, sel.kind, sel.id, sel.typeName || ""
    );
  }

  function areaShowColoredPills(areaSlug) {
    var area = (state.data.areas || []).find(function (a) {
      return a.slug === areaSlug;
    });
    return !area || area.show_colored_pills !== false;
  }

  var DEFAULT_SEL_DOT_COLOR = "#94a3b8";

  function selectionItemPresentation(sel) {
    if (sel.kind !== "object") {
      return { className: "", styleAttr: "", dotStyleAttr: "" };
    }
    var objectColor = (sel.color || "").trim();
    var useColored = areaShowColoredPills(sel.area);
    if (objectColor && useColored) {
      return {
        className: " nsm-sel-item-colored",
        styleAttr: " style=\"--nsm-sel-accent:" + esc(objectColor) + ";\"",
        dotStyleAttr: " style=\"background-color:" + esc(objectColor) + ";\"",
      };
    }
    return {
      className: " nsm-sel-item-muted",
      styleAttr: "",
      dotStyleAttr: useColored
        ? " style=\"background-color:" + DEFAULT_SEL_DOT_COLOR + ";\""
        : "",
    };
  }

  // ── Selection helpers ──────────────────────────────────────────────────────

  function selKey(area, placement, kind, id) {
    return [area, placement, kind, String(id)].join(":");
  }

  function hasSelection(area, placement, kind, id) {
    return !!state.selections[selKey(area, placement, kind, id)];
  }

  function addSelection(area, placement, kind, id, name, typeName, matchingClass, color) {
    state.selections[selKey(area, placement, kind, id)] = {
      area: area, placement: placement, kind: kind, id: String(id),
      name: name || String(id), typeName: typeName || "",
      matchingClass: matchingClass || "",
      color: color || "",
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
  }

  // ── Changelog auto-fill (object picker changes) ───────────────────────────

  var initialSnapshot = null;

  function selectionsPayload(selectionsObj) {
    return Object.values(selectionsObj).map(function (s) {
      return {
        area: s.area,
        placement: s.placement,
        kind: s.kind,
        id: s.id,
        name: s.name || s.id,
        exclude: !!s.exclude,
      };
    });
  }

  function captureInitialSnapshot() {
    initialSnapshot = {
      selections: JSON.stringify(selectionsPayload(state.selections)),
    };
  }

  function selectionEntryKey(s) {
    return [s.area, s.placement, s.kind, s.id].join(":");
  }

  function diffSelections() {
    if (!initialSnapshot) return { added: [], removed: [] };
    var initial = [];
    try {
      initial = JSON.parse(initialSnapshot.selections);
    } catch (_) {}
    var cur = selectionsPayload(state.selections);
    var initialMap = {};
    initial.forEach(function (s) { initialMap[selectionEntryKey(s)] = s; });
    var curMap = {};
    cur.forEach(function (s) { curMap[selectionEntryKey(s)] = s; });
    var added = [];
    var removed = [];
    Object.keys(curMap).forEach(function (k) {
      if (!initialMap[k]) added.push(curMap[k]);
    });
    Object.keys(initialMap).forEach(function (k) {
      if (!curMap[k]) removed.push(initialMap[k]);
    });
    return { added: added, removed: removed };
  }

  function labelForSelection(s) {
    return (s.area || "?") + "/" + (s.name || s.id || "?");
  }

  function truncateChangelog(msg, maxLen) {
    if (msg.length <= maxLen) return msg;
    return msg.substring(0, maxLen - 3) + "...";
  }

  function buildChangelogSummary() {
    if (!initialSnapshot) return "";
    var diff = diffSelections();
    var parts = [];
    if (diff.added.length) {
      var addedLabels = diff.added.slice(0, 3).map(labelForSelection).join(", ");
      if (diff.added.length > 3) {
        addedLabels += " +" + (diff.added.length - 3);
      }
      parts.push(t("changelog_added", "Added") + ": " + addedLabels);
    }
    if (diff.removed.length) {
      var removedLabels = diff.removed.slice(0, 3).map(labelForSelection).join(", ");
      if (diff.removed.length > 3) {
        removedLabels += " +" + (diff.removed.length - 3);
      }
      parts.push(t("changelog_removed", "Removed") + ": " + removedLabels);
    }
    if (!parts.length) return "";
    return truncateChangelog(parts.join("; "), 200);
  }

  function ensureFormBranchAction(form) {
    var branch = getActiveBranchSchemaId();
    if (!branch) return;
    var action = form.getAttribute("action");
    if (!action) {
      action = window.location.pathname + window.location.search;
    }
    if (action.indexOf("_branch=") >= 0) return;
    var sep = action.indexOf("?") >= 0 ? "&" : "?";
    form.setAttribute("action", action + sep + "_branch=" + encodeURIComponent(branch));
  }

  function bindChangelogAutofill() {
    var picker = pickerEl();
    if (!picker) return;
    var form = picker.closest("form");
    if (!form || form.dataset.nsmChangelogBound === "1") return;
    form.dataset.nsmChangelogBound = "1";
    ensureFormBranchAction(form);
    form.addEventListener("submit", function () {
      syncHidden();
      ensureFormBranchAction(form);
      var branch = getActiveBranchSchemaId();
      if (branch) {
        var hidden = form.querySelector('input[name="nsm_branch"]');
        if (!hidden) {
          hidden = document.createElement("input");
          hidden.type = "hidden";
          hidden.name = "nsm_branch";
          form.appendChild(hidden);
        }
        hidden.value = branch;
      }

      var field = form.querySelector('[name="changelog_message"]');
      if (field && !field.value.trim()) {
        var summary = buildChangelogSummary();
        if (summary) field.value = summary;
      }
    });
  }

  function selectionsFor(areaSlug, placement) {
    return Object.values(state.selections)
      .filter(function (s) { return s.area === areaSlug && s.placement === placement; })
      .sort(function (a, b) {
        return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
      });
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

  var BROWSE_LIMIT = 30;
  var GROUP_LIST_CAP = 200;

  function loadBrowse(areaSlug, placement, areaData, append) {
    var k = searchKey(areaSlug, placement);
    var b = getBrowse(areaSlug, placement);

    if (!append) {
      b.items = [];
      b.offset = 0;
      b.total = 0;
      b._noApi = false;
      b._pickType = false;
      b._needsSearch = false;
    }
    if (b.loading) return;

    var types = areaData.types || [];
    var allObjectTypes = types.filter(function (t) { return t.kind === "object"; });
    var groupType = types.find(function (t) { return t.kind === "group"; });
    var pickerTypes = allObjectTypes.slice();
    if (groupType) {
      pickerTypes.push({
        kind: "group",
        name: t("groups", "Groups"),
        ct_id: null,
        matching_class: "",
      });
    }

    var selectedType = getSelectedType(areaSlug, placement);
    if (pickerTypes.length > 1 && !selectedType) {
      b.loading = false;
      b._pickType = true;
      b._needsSearch = false;
      updateBrowseList(areaSlug, placement);
      return;
    }

    var objectTypes = (selectedType && selectedType.kind === "object")
      ? allObjectTypes.filter(function (t) {
        return String(t.ct_id) === String(selectedType.ct_id);
      })
      : (pickerTypes.length === 1 && allObjectTypes.length === 1 ? allObjectTypes : []);
    var loadGroups = selectedType
      ? selectedType.kind === "group"
      : (!allObjectTypes.length && !!groupType);

    var query = b.query.trim();
    var apiQuery = (query === "*") ? "" : query;

    b._needsSearch = false;
    b._pickType = false;

    var apiTypes = objectTypes.filter(function (type) {
      return type.ct_id || type.api_url;
    });
    if (!apiTypes.length && !loadGroups) {
      b.loading = false;
      b.items = [];
      b.total = 0;
      b._noApi = true;
      updateBrowseList(areaSlug, placement);
      return;
    }
    b._noApi = false;
    b.loading = true;
    updateBrowseList(areaSlug, placement);

    if (state._ctrl[k]) { state._ctrl[k].abort(); }
    var ctrl = new AbortController();
    state._ctrl[k] = ctrl;

    var fetches = apiTypes.map(function (type) {
      return fetchBrowseType(type, apiQuery, b.offset, b.query.trim(), ctrl);
    });

    if (loadGroups && groupType && Array.isArray(groupType.entries)) {
      var ql = apiQuery.toLowerCase();
      var filtered = apiQuery
        ? groupType.entries.filter(function (g) {
          return g.name.toLowerCase().indexOf(ql) !== -1;
        })
        : groupType.entries.slice(0, GROUP_LIST_CAP);
      if (!apiQuery && groupType.entries.length > GROUP_LIST_CAP) {
        filtered = groupType.entries.slice(0, GROUP_LIST_CAP);
      }
      var page = filtered.slice(b.offset, b.offset + BROWSE_LIMIT)
        .map(function (g) {
          return {
            kind: "group",
            id: g.id,
            name: g.name,
            typeName: "Group",
            matchingClass: "",
          };
        });
      fetches.push(Promise.resolve({ items: page, count: filtered.length }));
    }

    Promise.all(fetches).then(function (perType) {
      if (ctrl.signal.aborted) return;
      var allNew = [].concat.apply([], perType.map(function (r) { return r.items; }));
      var maxCount = Math.max.apply(null, [0].concat(perType.map(function (r) { return r.count; })));
      b.items = append ? b.items.concat(allNew) : allNew;
      b.total = maxCount;
      b.offset = append ? b.offset + BROWSE_LIMIT : BROWSE_LIMIT;
      b.loading = false;
      b._hasMore = b.offset < b.total;
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
    if (b._pickType) {
      html = "<div class='nsm-drop-msg'>" + esc(t("pick_type", "Select a type first.")) + "</div>";
    } else if (b._needsSearch) {
      html = "";
    } else if (b._noApi) {
      html = "<div class='nsm-drop-msg text-warning'>"
        + esc(t("no_api", "No API endpoint for this type. Check type config or custom objects."))
        + "</div>";
    } else if (!b.items.length && b.loading) {
      html = "<div class='nsm-drop-msg'>" + t("searching", "Searching\u2026") + "</div>";
    } else if (!available.length && !b.loading) {
      html = "<div class='nsm-drop-msg'>" + t("no_results", "No results") + "</div>";
    } else {
      available.forEach(function (item) {
        var payload = JSON.stringify({
          area: areaSlug, placement: placement,
          kind: item.kind, id: item.id, name: item.name,
          typeName: item.typeName, matchingClass: item.matchingClass || "",
          color: item.color || "",
        });
        html += "<div class='option' data-payload='" + esc(payload) + "'>"
          + "<span class='nsm-drop-name'>" + esc(item.name) + "</span>"
          + "<span class='nsm-drop-type'>" + esc(item.typeName) + "</span>"
          + "</div>";
      });
      if (b.loading) {
        html += "<div class='nsm-drop-msg'>" + t("searching", "Searching\u2026") + "</div>";
      } else if (b._hasMore || b.offset < b.total) {
        html += "<div class='nsm-browse-more'"
          + " data-area='" + esc(areaSlug) + "'"
          + " data-placement='" + esc(placement) + "'>"
          + esc(t("load_more", "Load more")) + " (" + b.items.length + " / " + b.total + ")"
          + "</div>";
      }
    }

    listEl.innerHTML = html;

    listEl.querySelectorAll(".option[data-payload]").forEach(function (el) {
      el.addEventListener("mouseenter", function () {
        listEl.querySelectorAll(".option.active").forEach(function (a) { a.classList.remove("active"); });
        el.classList.add("active");
      });
      el.addEventListener("mouseleave", function () { el.classList.remove("active"); });
    });

    var dropWrap = listEl.closest(".nsm-browse-drop");
    if (dropWrap) {
      dropWrap.hidden = !(html || b.loading);
    }
  }

  function hideBrowseDrop(areaSlug, placement) {
    var listEl = document.querySelector(
      ".nsm-browse-list[data-area='" + cssEsc(areaSlug) + "'][data-placement='" + cssEsc(placement) + "']"
    );
    if (!listEl) return;
    var dropWrap = listEl.closest(".nsm-browse-drop");
    if (dropWrap) dropWrap.hidden = true;
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

    var html = "";
    sel.forEach(function (s) {
      var pres = selectionItemPresentation(s);
      var dotHtml = pres.dotStyleAttr
        ? "<span class='nsm-sel-item-dot'" + pres.dotStyleAttr + " aria-hidden='true'></span>"
        : "";
      html += "<div class='nsm-sel-item" + pres.className + "'" + pres.styleAttr + ">"
        + "<span class='nsm-sel-item-name'>" + dotHtml + esc(s.name)
        + (displayTypeName(s)
          ? " <span class='nsm-sel-item-type'>(" + esc(displayTypeName(s)) + ")</span>"
          : "")
        + "</span>"
        + "<button type='button' class='nsm-sel-item-remove'"
        + " data-nsm-remove='1'"
        + " data-area='" + esc(s.area) + "'"
        + " data-placement='" + esc(s.placement) + "'"
        + " data-kind='" + esc(s.kind) + "'"
        + " data-id='" + esc(s.id) + "'"
        + " title='" + t('remove', 'Remove') + "'>\u00d7</button>"
        + "</div>";
    });
    return html;
  }

  // ── Styles ─────────────────────────────────────────────────────────────────

  function ensureStyles() {
    if (document.getElementById("nsm-rule-style")) return;
    var s = document.createElement("style");
    s.id = "nsm-rule-style";
    s.textContent = [
      ".nsm-hidden-pickers { display: none; }",
      ".nsm-rule-tab-panel { padding-top: .25rem; }",
      ".nsm-element-picker-wrap.hidden { display: none !important; }",
      ".nsm-drop-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1 1 auto; }",
      ".nsm-drop-type { font-size: .72rem; opacity: .75; white-space: nowrap; flex-shrink: 0; margin-left: .5rem; }",
      ".nsm-drop-msg { padding: .5rem .75rem; color: var(--tblr-secondary-color, #6c757d); font-style: italic; font-size: .85rem; }",
      ".nsm-empty { color: var(--tblr-secondary-color, #6c757d); font-style: italic; padding: .4rem 0; font-size: .875rem; }",
      ".nsm-hint-tip { font-size: .72rem; opacity: .7; margin-top: .35rem; color: var(--tblr-secondary-color, #6c757d); }",
      ".nsm-browse-more.option { justify-content: center; color: var(--tblr-primary, #0d6efd); font-size: .8rem; }",
      ".nsm-rule-policy-tabs-layout .nsm-rule-policy-tab-content { min-height: 12rem; }",
    ].join("\n");
    document.head.appendChild(s);
  }

  // ── Policy tabs (source / destination / service / action) ─────────────────

  var STANDARD_POLICY_SLUGS = ["source", "destination", "service", "action", "info"];

  function areasBySlug() {
    var map = {};
    (state.data.areas || []).forEach(function (area) {
      map[area.slug] = area;
    });
    return map;
  }

  function getPolicySlotConfigFromServer() {
    var el = document.getElementById("nsm-rule-slots");
    if (!el) return [];
    try {
      var data = JSON.parse(el.textContent);
      return Array.isArray(data) ? data : [];
    } catch (_) {
      return [];
    }
  }

  function getConfiguredPolicySlots() {
    var labelMap = {};
    getPolicySlotConfigFromServer().forEach(function (slot) {
      labelMap[slot.slug] = slot.label;
    });
    var bySlug = areasBySlug();
    return STANDARD_POLICY_SLUGS.filter(function (slug) {
      var area = bySlug[slug];
      return area && (area.types || []).length;
    }).map(function (slug) {
      var area = bySlug[slug];
      return {
        slug: slug,
        label: labelMap[slug] || area.display_name || area.name || slug,
        kind: "object",
        area: area,
      };
    });
  }

  function extraPolicyAreas() {
    var standard = {};
    STANDARD_POLICY_SLUGS.forEach(function (slug) { standard[slug] = true; });
    return (state.data.areas || []).filter(function (area) {
      return !standard[area.slug];
    });
  }

  function isPolicyTabSlug(slug, slots) {
    return slots.some(function (slot) { return slot.slug === slug; });
  }

  function ensureActivePolicyTab(slots) {
    if (!isPolicyTabSlug(activeAreaSlug(), slots)) {
      setActiveArea((slots[0] && slots[0].slug) || "");
    }
  }

  function renderPolicyObjectPanel(slot) {
    var area = slot.area;
    var placement = area.placement || _placementForAreaSlug(area.slug);
    return "<div class='tab-pane fade show active nsm-rule-tab-panel'"
      + " data-nsm-slot='" + esc(area.slug) + "'>"
      + renderColumn(area, placement)
      + "</div>";
  }

  function renderPolicyTabs(slots) {
    var active = activeAreaSlug();
    var html = "<ul class='nav nav-tabs mb-0 nsm-rule-policy-tabs' role='tablist'>";
    slots.forEach(function (slot) {
      var isActive = slot.slug === active;
      html += "<li class='nav-item' role='presentation'>"
        + "<button type='button' class='nav-link" + (isActive ? " active" : "") + "'"
        + " role='tab'"
        + " data-nsm-area='" + esc(slot.slug) + "'>"
        + esc(slot.label)
        + "</button></li>";
    });
    html += "</ul>";
    return html;
  }

  function renderActivePolicyPanel(slots) {
    var active = activeAreaSlug();
    var slot = slots.find(function (s) { return s.slug === active; }) || slots[0];
    if (!slot) {
      return "<div class='tab-pane fade show active nsm-rule-tab-panel'></div>";
    }
    return renderPolicyObjectPanel(slot);
  }

  function renderPolicyTabsLayout(slots) {
    ensureActivePolicyTab(slots);
    return "<div class='nsm-rule-policy-tabs-layout'>"
      + renderPolicyTabs(slots)
      + "<div class='tab-content border border-top-0 rounded-bottom p-3 bg-body nsm-rule-policy-tab-content'>"
      + renderActivePolicyPanel(slots)
      + "</div></div>";
  }

  function renderExtraAreasSection(areas) {
    if (!areas.length) return "";
    if (!activeAreaSlug() || !areas.some(function (a) { return a.slug === activeAreaSlug(); })) {
      setActiveArea(areas[0].slug);
    }
    return "<div class='mt-4'>"
      + "<h3 class='h6 text-muted mb-2'>" + esc(t("additional_fields", "Additional fields")) + "</h3>"
      + renderAreaTabsForAreas(areas)
      + "<div class='tab-content border border-top-0 rounded-bottom p-3 bg-body'>"
      + renderActiveAreaFromList(areas)
      + "</div></div>";
  }

  function renderAreaTabsForAreas(areas) {
    var html = "<ul class='nav nav-tabs mb-0'>";
    areas.forEach(function (area) {
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

  function renderActiveAreaFromList(areas) {
    var slug = activeAreaSlug();
    var area = areas.find(function (a) { return a.slug === slug; }) || areas[0];
    if (!area) return "";
    var placement = area.placement || _placementForAreaSlug(area.slug);
    return "<div class='tab-pane fade show active nsm-rule-tab-panel'>"
      + renderColumn(area, placement) + "</div>";
  }

  function renderLegacyTabsLayout() {
    if (!activeAreaSlug() && state.data.areas.length) {
      setActiveArea(state.data.areas[0].slug);
    }
    return renderAreaTabs()
      + "<div class='tab-content border border-top-0 rounded-bottom p-3 bg-body'>"
      + renderActiveArea()
      + "</div>";
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
    if (!types.length) {
      return "<div class='alert alert-warning mb-0'>"
        + esc(t("no_types_field", "No types configured for this field. Add a type config under Rulebook \u2192 Fields."))
        + "</div>"
        + "<div class='nsm-selected mt-2'"
        + " data-area='" + esc(area.slug) + "'"
        + " data-placement='" + esc(placement) + "'>"
        + buildSelectedHtml(area.slug, placement)
        + "</div>";
    }
    var objectTypes = types.filter(function (tp) { return tp.kind === "object"; });
    var groupType   = types.find  (function (tp) { return tp.kind === "group"; });
    var pickerTypes = objectTypes.slice();
    if (groupType) {
      pickerTypes.push({
        kind: "group",
        name: t("groups", "Groups"),
        ct_id: null,
        matching_class: "",
      });
    }

    if (pickerTypes.length === 1 && !getSelectedType(area.slug, placement)) {
      setSelectedType(area.slug, placement, pickerTypes[0]);
    }
    var selectedType = getSelectedType(area.slug, placement);
    var pickerOpen = !!selectedType;
    var searchPh = t(
      "search_lazy",
      "Search or browse\u2026"
    );

    var html = "<div class='nsm-assign-field' data-area='" + esc(area.slug) + "'>";

    html += "<div class='mb-3'>"
      + "<label class='form-label fw-semibold'>"
      + esc(t("type", "Type")) + " <span class='text-danger'>*</span>"
      + "</label>"
      + "<select class='form-select nsm-type-select'"
      + " data-area='" + esc(area.slug) + "'"
      + " data-placement='" + esc(placement) + "'>";
    if (pickerTypes.length > 1) {
      html += "<option value=''>" + esc(t("select_type", "\u2014 Select type \u2014")) + "</option>";
    }
    pickerTypes.forEach(function (tp) {
      var val = typeKeyFromObj(tp);
      var isSel = selectedType && typeKeyFromObj(selectedType) === val;
      html += "<option value='" + esc(val) + "'" + (isSel ? " selected" : "") + ">"
        + esc(typeOptionLabel(tp))
        + "</option>";
    });
    html += "</select></div>";

    html += "<div class='mb-3 nsm-element-picker-wrap"
      + (pickerOpen ? "" : " hidden")
      + "' data-area='" + esc(area.slug) + "'"
      + " data-placement='" + esc(placement) + "'>"
      + "<label class='form-label fw-semibold'>"
      + esc(t("elements", "Elements"))
      + "</label>"
      + "<div class='ts-wrapper form-select single'>"
      + "<div class='ts-control'>"
      + "<input type='text' class='nsm-search-input' autocomplete='off'"
      + " data-area='" + esc(area.slug) + "'"
      + " data-placement='" + esc(placement) + "'"
      + " placeholder='" + esc(searchPh) + "'"
      + " value='" + esc(getBrowse(area.slug, placement).query) + "' />"
      + "</div>"
      + "<div class='ts-dropdown single nsm-browse-drop' hidden>"
      + "<div class='ts-dropdown-content nsm-browse-list'"
      + " data-area='" + esc(area.slug) + "'"
      + " data-placement='" + esc(placement) + "'></div>"
      + "</div></div>"
      + "</div>";

    html += "<div class='nsm-selected mt-2'"
      + " data-area='" + esc(area.slug) + "'"
      + " data-placement='" + esc(placement) + "'>"
      + buildSelectedHtml(area.slug, placement)
      + "</div>";

    html += "</div>";
    return html;
  }

  function renderActiveArea() {
    var slug = activeAreaSlug();
    var area = state.data.areas.find(function (a) { return a.slug === slug; })
      || state.data.areas[0];
    if (!area) return "";
    var placement = area.placement || _placementForAreaSlug(area.slug);
    return "<div class='tab-pane fade show active nsm-rule-tab-panel'>"
      + renderColumn(area, placement) + "</div>";
  }

  function render() {
    var root = pickerEl();
    if (!root) return;

    if (!getSelectedRulebookId()) {
      root.innerHTML = "<div class='alert alert-info mb-0'>"
        + esc(t("pick_rulebook", "Please select a rulebook first."))
        + "</div>";
      syncPickerHint();
      return;
    }

    if (!state.data.areas.length) {
      root.innerHTML = "<div class='alert alert-warning mb-0'>"
        + esc(t("no_object_fields", "No visible object fields in this rulebook. Add fields and type configs under Rulebook \u2192 Fields."))
        + "</div>";
      root.classList.add("nsm-lazy-picker");
      syncPickerHint();
      return;
    }

    root.classList.add("nsm-lazy-picker");
    var policySlots = getConfiguredPolicySlots();
    var html = "";
    if (policySlots.length) {
      html += renderPolicyTabsLayout(policySlots);
      html += renderExtraAreasSection(extraPolicyAreas());
    } else {
      html += renderLegacyTabsLayout();
    }
    root.innerHTML = html;
    syncPickerHint();
    bindAreaTabs(root);
    bindTypeSelects(root);
    bindSearchInputs(root);
    bindBrowseScroll(root);
    showIdleBrowseState(root);
  }

  function showIdleBrowseState(root) {
    /* Lazy browse loads on focus; no min-length gate. */
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

  function bindTypeSelects(root) {
    root.querySelectorAll("select.nsm-type-select").forEach(function (sel) {
      if (sel.dataset.nsmTypeBound === "1") return;
      sel.dataset.nsmTypeBound = "1";

      function onTypeChange() {
        var areaSlug = sel.dataset.area;
        var placement = sel.dataset.placement;
        var area = state.data.areas.find(function (a) { return a.slug === areaSlug; });
        if (!area) return;
        var types = area.types || [];
        var objectTypes = types.filter(function (tp) { return tp.kind === "object"; });
        var groupType = types.find(function (tp) { return tp.kind === "group"; });
        var pickerTypes = objectTypes.slice();
        if (groupType) {
          pickerTypes.push({
            kind: "group",
            name: t("groups", "Groups"),
            ct_id: null,
            matching_class: "",
          });
        }
        setSelectedType(areaSlug, placement, typeObjFromKey(sel.value, pickerTypes));
        var bk = searchKey(areaSlug, placement);
        state.browse[bk] = { items: [], total: 0, offset: 0, loading: false, query: "" };
        render();
      }

      sel.addEventListener("change", onTypeChange);
    });
  }

  function bindBrowseScroll(root) {
    root.querySelectorAll(".nsm-browse-list").forEach(function (listEl) {
      if (listEl.dataset.nsmScrollBound === "1") return;
      listEl.dataset.nsmScrollBound = "1";
      listEl.addEventListener("scroll", debounce(function () {
        if (listEl.scrollTop + listEl.clientHeight < listEl.scrollHeight - 48) return;
        var areaSlug = listEl.dataset.area;
        var placement = listEl.dataset.placement;
        var b = getBrowse(areaSlug, placement);
        if (b.loading || !(b._hasMore || b.offset < b.total)) return;
        var area = state.data.areas.find(function (a) { return a.slug === areaSlug; });
        if (area) loadBrowse(areaSlug, placement, area, true);
      }, 200));
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
        debouncedFn(areaSlug, placement, area);
      });

      inp.addEventListener("blur", function () {
        setTimeout(function () { hideBrowseDrop(areaSlug, placement); }, 200);
      });
    });
  }

  // Delegated click events on the root (survive inner re-renders)
  function bindRootDelegation() {
    var root = pickerEl();
    if (!root || root.dataset.nsmDelegate === "1") return;
    root.dataset.nsmDelegate = "1";

    root.addEventListener("mousedown", function (e) {
      // ── Browse list: select item ──
      var browseItem = e.target.closest(".option[data-payload]");
      if (browseItem) {
        e.preventDefault();
        var p = JSON.parse(browseItem.dataset.payload);
        addSelection(
          p.area, p.placement, p.kind, p.id, p.name, p.typeName, p.matchingClass, p.color
        );
        renderSelected(p.area, p.placement);
        updateBrowseList(p.area, p.placement);
        var inp = root.querySelector(
          "input.nsm-search-input[data-area='" + cssEsc(p.area) + "']"
        );
        if (inp) inp.value = "";
        getBrowse(p.area, p.placement).query = "";
        hideBrowseDrop(p.area, p.placement);
        return;
      }
    });

    root.addEventListener("click", function (e) {
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

  function applyRulebookPicker(preserveSelections) {
    var rbId = getSelectedRulebookId();
    state.data = pickerDataForRulebook(rbId);
    if (!preserveSelections) {
      state.selections = {};
      state.ui = { __activeArea: "", __selectedType: {} };
      state.browse = {};
      state._ctrl = {};
    } else {
      normalizeSelectionTypeNames();
    }
    syncHidden();
    render();
  }

  function bindRulebookChange() {
    var field = getRulebookField();
    if (!field) return;
    if (field.dataset.nsmRbBound === "1") return;

    function onRulebookChange() {
      applyRulebookPicker(false);
    }

    function attach() {
      field.dataset.nsmRbBound = "1";
      field.addEventListener("change", onRulebookChange);
      if (field.tomselect) {
        field.tomselect.on("change", onRulebookChange);
      }
    }

    if (field.tomselect) {
      attach();
      return;
    }

    attach();
    var tries = 0;
    var timer = setInterval(function () {
      tries += 1;
      if (field.tomselect) {
        field.tomselect.on("change", onRulebookChange);
        clearInterval(timer);
      }
      if (tries > 80) clearInterval(timer);
    }, 100);
  }

  function waitForRulebookThenRender() {
    var tries = 0;
    function tick() {
      tries += 1;
      var rbId = getSelectedRulebookId();
      if (rbId || tries > 80) {
        state.data = pickerDataForRulebook(rbId);
        render();
        return;
      }
      setTimeout(tick, 100);
    }
    tick();
  }

  function init() {
    var picker = pickerEl();
    if (!picker) return;

    ensureStyles();

    if (picker.dataset.nsmReady === "1") {
      bindChangelogAutofill();
      bindRulebookChange();
      applyRulebookPicker(true);
      return;
    }
    picker.dataset.nsmReady = "1";

    state.data = pickerDataForRulebook(getSelectedRulebookId());
    state.selections = {};
    state.ui = { __activeArea: "", __selectedType: {} };
    state.browse = {};
    state._ctrl = {};
    state.chipSel = {};

    loadInitialSelections();
    normalizeSelectionTypeNames();
    syncHidden();
    captureInitialSnapshot();
    bindChangelogAutofill();
    render();
    bindRulebookChange();
    waitForRulebookThenRender();
    if (!picker.dataset.nsmDelegate) {
      bindRootDelegation();
      picker.dataset.nsmDelegate = "1";
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  document.addEventListener("htmx:load", init);
  window.addEventListener("load", init);
})();

