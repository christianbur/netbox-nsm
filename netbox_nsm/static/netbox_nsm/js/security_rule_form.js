(function () {
  /**
   * Section-per-area picker.
   *
   * state.selections: keyed by "areaSlug:placement:kind:id"
   * value: { area, placement, kind, id, name, typeName }
   *
   * placement: "source" | "destination" | "fixed"
   * kind:      "object" | "group"
   */
  const state = {
    data: { areas: [] },
    selections: {},
    // per-area UI state: { activeType, filter: { source, destination, fixed } }
    ui: {},
  };

  // ─── DOM helpers ──────────────────────────────────────────────────────────

  function pickerEl() { return document.getElementById("nsm-rule-picker"); }
  function hiddenInputEl() { return document.getElementById("nsm-area-selections"); }

  function ensureStyles() {
    if (document.getElementById("nsm-security-rule-style")) return;
    const style = document.createElement("style");
    style.id = "nsm-security-rule-style";
    style.textContent = `
      .nsm-hidden-pickers { display: none; }
      .nsm-area-card { margin-bottom: 1.25rem; }
      .nsm-area-card .card-header { font-weight: 600; }
      .nsm-area-card .nsm-area-pills { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-bottom: 0.75rem; }
      .nsm-area-card .nsm-area-pills .btn { padding: 0.2rem 0.6rem; font-size: 0.85rem; }
      .nsm-column-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; }
      .nsm-column-header .badge { font-size: 0.75rem; }
      .nsm-selected-list { min-height: 2.5rem; }
      .nsm-selected-empty { color: #94a3b8; font-style: italic; padding: 0.5rem 0.75rem; }
      .nsm-add-row { display: flex; gap: 0.25rem; margin-bottom: 0.5rem; }
      .nsm-add-row select { flex: 1 1 auto; min-width: 0; }
      .nsm-area-divider { border-top: 1px dashed #cbd5e1; margin: 0.75rem 0; }
    `;
    document.head.appendChild(style);
  }

  // ─── Picker data ──────────────────────────────────────────────────────────

  function getPickerData() {
    const el = document.getElementById("nsm-rule-picker-data");
    if (!el) return { areas: [] };
    try {
      const parsed = JSON.parse(el.textContent);
      if (!parsed || !Array.isArray(parsed.areas)) return { areas: [] };
      return parsed;
    } catch (_) { return { areas: [] }; }
  }

  function loadInitialSelections() {
    const el = document.getElementById("nsm-rule-selections");
    if (!el) return;
    try {
      const list = JSON.parse(el.textContent);
      if (!Array.isArray(list)) return;
      list.forEach(function (sel) {
        if (!sel.area || !sel.placement || !sel.kind || !sel.id) return;
        const key = sel.area + ":" + sel.placement + ":" + sel.kind + ":" + sel.id;
        state.selections[key] = {
          area: sel.area,
          placement: sel.placement,
          kind: sel.kind,
          id: String(sel.id),
          name: sel.name || String(sel.id),
        };
      });
    } catch (_) {}
  }

  // ─── Selection helpers ────────────────────────────────────────────────────

  function selKey(area, placement, kind, id) {
    return area + ":" + placement + ":" + kind + ":" + String(id);
  }

  function hasSelection(area, placement, kind, id) {
    return !!state.selections[selKey(area, placement, kind, id)];
  }

  function addSelection(area, placement, kind, id, name) {
    state.selections[selKey(area, placement, kind, id)] = {
      area: area, placement: placement, kind: kind, id: String(id), name: name,
    };
    syncHiddenInput();
  }

  function removeSelection(area, placement, kind, id) {
    delete state.selections[selKey(area, placement, kind, id)];
    syncHiddenInput();
  }

  function syncHiddenInput() {
    const input = hiddenInputEl();
    if (!input) return;
    input.value = JSON.stringify(Object.values(state.selections).map(function (s) {
      return { area: s.area, placement: s.placement, kind: s.kind, id: s.id };
    }));
  }

  function selectionsForColumn(areaSlug, placement) {
    return Object.values(state.selections)
      .filter(function (s) { return s.area === areaSlug && s.placement === placement; })
      .sort(function (a, b) {
        return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
      });
  }

  // ─── UI state per area ────────────────────────────────────────────────────

  function uiFor(areaSlug) {
    if (!state.ui[areaSlug]) {
      state.ui[areaSlug] = {
        activeType: "",  // "" = all types
        filter: { source: "", destination: "", fixed: "" },
      };
    }
    return state.ui[areaSlug];
  }

  // ─── HTML escape ──────────────────────────────────────────────────────────

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ─── Rendering ────────────────────────────────────────────────────────────

  function entriesForArea(area, activeType) {
    // Flatten entries from all types (or filter by activeType), tag each with its type name.
    const out = [];
    area.types.forEach(function (typeDef) {
      if (activeType && typeDef.name !== activeType) return;
      typeDef.entries.forEach(function (entry) {
        out.push({ entry: entry, typeName: typeDef.name });
      });
    });
    out.sort(function (a, b) {
      return a.entry.name.localeCompare(b.entry.name, undefined, { sensitivity: "base" });
    });
    return out;
  }

  function renderColumnHeader(label, badgeClass) {
    return ""
      + "<div class='nsm-column-header'>"
      +   "<span class='badge " + badgeClass + "'>" + esc(label) + "</span>"
      + "</div>";
  }

  function renderColumn(area, placement, label, badgeClass) {
    const ui = uiFor(area.slug);
    const activeType = ui.activeType;
    const filter = (ui.filter[placement] || "").toLowerCase();
    const allEntries = entriesForArea(area, activeType);

    // Available = not yet selected with this placement, optionally filtered by text
    const available = allEntries.filter(function (e) {
      if (hasSelection(area.slug, placement, e.entry.kind, e.entry.id)) return false;
      if (filter && e.entry.name.toLowerCase().indexOf(filter) === -1) return false;
      return true;
    });

    let optionsHtml = "<option value=''>" + esc("— select to add —") + "</option>";
    available.forEach(function (e) {
      const payload = JSON.stringify({
        area: area.slug, placement: placement,
        kind: e.entry.kind, id: e.entry.id, name: e.entry.name,
      });
      optionsHtml += "<option value='" + esc(payload) + "'>"
        + esc(e.entry.name) + " — " + esc(e.typeName)
        + "</option>";
    });

    const selected = selectionsForColumn(area.slug, placement);
    let selectedHtml = "";
    if (!selected.length) {
      selectedHtml = "<div class='nsm-selected-empty'>" + esc("None selected") + "</div>";
    } else {
      selectedHtml = "<ul class='list-group nsm-selected-list'>";
      selected.forEach(function (s) {
        selectedHtml += ""
          + "<li class='list-group-item d-flex justify-content-between align-items-center gap-2 py-1'>"
          +   "<div class='d-flex align-items-center gap-2'>"
          +     "<input class='form-check-input m-0' type='checkbox' "
          +       "data-nsm-cb='1' "
          +       "data-area='" + esc(area.slug) + "' "
          +       "data-placement='" + esc(placement) + "' "
          +       "data-kind='" + esc(s.kind) + "' "
          +       "data-id='" + esc(s.id) + "' />"
          +     "<span>" + esc(s.name) + "</span>"
          +   "</div>"
          +   "<button type='button' class='btn btn-sm btn-link text-danger p-0' "
          +     "data-nsm-remove='1' "
          +     "data-area='" + esc(area.slug) + "' "
          +     "data-placement='" + esc(placement) + "' "
          +     "data-kind='" + esc(s.kind) + "' "
          +     "data-id='" + esc(s.id) + "' "
          +     "title='" + esc("Remove") + "'>×</button>"
          + "</li>";
      });
      selectedHtml += "</ul>";
    }

    return ""
      + renderColumnHeader(label, badgeClass)
      + "<div class='nsm-add-row'>"
      +   "<input type='search' class='form-control form-control-sm' "
      +     "placeholder='" + esc("Filter…") + "' "
      +     "data-nsm-filter='1' "
      +     "data-area='" + esc(area.slug) + "' "
      +     "data-placement='" + esc(placement) + "' "
      +     "value='" + esc(filter) + "' />"
      + "</div>"
      + "<div class='nsm-add-row'>"
      +   "<select class='form-select form-select-sm' "
      +     "data-nsm-available='1' "
      +     "data-area='" + esc(area.slug) + "' "
      +     "data-placement='" + esc(placement) + "'>"
      +     optionsHtml
      +   "</select>"
      +   "<button type='button' class='btn btn-sm btn-primary' "
      +     "data-nsm-add='1' "
      +     "data-area='" + esc(area.slug) + "' "
      +     "data-placement='" + esc(placement) + "'>"
      +     "+ " + esc("Add")
      +   "</button>"
      + "</div>"
      + selectedHtml
      + "<div class='mt-2 d-flex justify-content-end'>"
      +   "<button type='button' class='btn btn-sm btn-outline-danger' "
      +     "data-nsm-delete-checked='1' "
      +     "data-area='" + esc(area.slug) + "' "
      +     "data-placement='" + esc(placement) + "'>"
      +     esc("Delete selected")
      +   "</button>"
      + "</div>";
  }

  function renderTypePills(area) {
    const ui = uiFor(area.slug);
    let html = "<div class='nsm-area-pills'>";
    const allClass = ui.activeType === "" ? "btn btn-sm btn-secondary" : "btn btn-sm btn-outline-secondary";
    html += "<button type='button' class='" + allClass + "' "
      + "data-nsm-type='1' data-area='" + esc(area.slug) + "' data-type=''>"
      + esc("All types") + "</button>";
    area.types.forEach(function (typeDef) {
      const cls = ui.activeType === typeDef.name ? "btn btn-sm btn-secondary" : "btn btn-sm btn-outline-secondary";
      html += "<button type='button' class='" + cls + "' "
        + "data-nsm-type='1' data-area='" + esc(area.slug) + "' "
        + "data-type='" + esc(typeDef.name) + "'>"
        + esc(typeDef.name) + "</button>";
    });
    html += "</div>";
    return html;
  }

  function renderArea(area) {
    const isDirectional = area.placement_mode === "directional";
    let body = "";
    body += renderTypePills(area);

    if (isDirectional) {
      body += ""
        + "<div class='row g-3'>"
        +   "<div class='col-md-6'>" + renderColumn(area, "source", "Source", "text-bg-primary") + "</div>"
        +   "<div class='col-md-6'>" + renderColumn(area, "destination", "Destination", "text-bg-info") + "</div>"
        + "</div>";
    } else {
      body += "<div>" + renderColumn(area, "fixed", area.name, "text-bg-secondary") + "</div>";
    }

    return ""
      + "<div class='card nsm-area-card' data-nsm-area-card='" + esc(area.slug) + "'>"
      +   "<div class='card-header d-flex justify-content-between align-items-center'>"
      +     "<span>" + esc(area.display_name || area.name) + "</span>"
      +     "<span class='small text-muted'>"
      +       (isDirectional ? esc("Source / Destination") : esc("Fixed"))
      +     "</span>"
      +   "</div>"
      +   "<div class='card-body'>" + body + "</div>"
      + "</div>";
  }

  function render() {
    const root = pickerEl();
    if (!root) return;

    if (!state.data.areas.length) {
      root.innerHTML = "<div class='alert alert-warning'>"
        + esc("No areas configured. Add areas in the Object-Builder first.")
        + "</div>";
      return;
    }

    let html = "";
    state.data.areas.forEach(function (area) {
      html += renderArea(area);
    });
    root.innerHTML = html;
    bindRowEvents(root);
  }

  // ─── Events ───────────────────────────────────────────────────────────────

  function bindRowEvents(root) {
    // Type pill buttons
    root.querySelectorAll("button[data-nsm-type]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const area = btn.dataset.area;
        uiFor(area).activeType = btn.dataset.type || "";
        render();
      });
    });

    // Filter inputs (only re-render that area's available select to preserve focus)
    root.querySelectorAll("input[data-nsm-filter]").forEach(function (input) {
      input.addEventListener("input", function () {
        const area = input.dataset.area;
        const placement = input.dataset.placement;
        uiFor(area).filter[placement] = input.value;
        render();
        // restore focus to filter input after re-render
        const fresh = pickerEl().querySelector(
          "input[data-nsm-filter][data-area='" + cssEsc(area) + "'][data-placement='" + cssEsc(placement) + "']"
        );
        if (fresh) {
          fresh.focus();
          // place cursor at end
          const v = fresh.value;
          fresh.value = "";
          fresh.value = v;
        }
      });
    });

    // Add buttons
    root.querySelectorAll("button[data-nsm-add]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const area = btn.dataset.area;
        const placement = btn.dataset.placement;
        const select = root.querySelector(
          "select[data-nsm-available][data-area='" + cssEsc(area) + "'][data-placement='" + cssEsc(placement) + "']"
        );
        if (!select || !select.value) return;
        try {
          const decoded = JSON.parse(select.value);
          if (!decoded.area || !decoded.placement || !decoded.kind || !decoded.id) return;
          addSelection(decoded.area, decoded.placement, decoded.kind, decoded.id, decoded.name || decoded.id);
          render();
        } catch (_) {}
      });
    });

    // Direct remove (× button)
    root.querySelectorAll("button[data-nsm-remove]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        removeSelection(btn.dataset.area, btn.dataset.placement, btn.dataset.kind, btn.dataset.id);
        render();
      });
    });

    // Bulk delete checked
    root.querySelectorAll("button[data-nsm-delete-checked]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const area = btn.dataset.area;
        const placement = btn.dataset.placement;
        const checked = root.querySelectorAll(
          "input[data-nsm-cb][data-area='" + cssEsc(area) + "'][data-placement='" + cssEsc(placement) + "']:checked"
        );
        checked.forEach(function (cb) {
          removeSelection(cb.dataset.area, cb.dataset.placement, cb.dataset.kind, cb.dataset.id);
        });
        render();
      });
    });
  }

  function cssEsc(v) {
    if (window.CSS && typeof window.CSS.escape === "function") return window.CSS.escape(v);
    return String(v).replace(/([^a-zA-Z0-9_-])/g, "\\$1");
  }

  // ─── Init ─────────────────────────────────────────────────────────────────

  function init() {
    const picker = pickerEl();
    if (!picker || picker.dataset.nsmReady === "1") return;

    ensureStyles();
    state.data = getPickerData();
    state.selections = {};
    state.ui = {};
    loadInitialSelections();
    syncHiddenInput();
    render();

    picker.dataset.nsmReady = "1";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  document.addEventListener("htmx:load", init);
  document.addEventListener("htmx:afterSwap", init);
  window.addEventListener("load", init);
})();
