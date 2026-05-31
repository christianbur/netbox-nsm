(function () {
  const state = {
    data: { areas: [] },
    selected: {},
    ui: {
      activeType: "",
      filter: "",
    },
  };

  function pickerEl() {
    return document.getElementById("nsm-group-member-picker");
  }

  function membersFieldEl() {
    return document.querySelector("[name='members']");
  }

  function areasFieldEl() {
    return document.querySelector("[name='areas']");
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function ensureStyles() {
    if (document.getElementById("nsm-group-member-style")) return;
    const style = document.createElement("style");
    style.id = "nsm-group-member-style";
    style.textContent = ""
      + ".nsm-group-pills{display:flex;flex-wrap:wrap;gap:.25rem;margin-bottom:.75rem}" 
      + ".nsm-group-add-row{display:flex;gap:.25rem;margin-bottom:.5rem}" 
      + ".nsm-group-add-row select{flex:1 1 auto;min-width:0}" 
      + ".nsm-selected-empty{color:#94a3b8;font-style:italic;padding:.5rem .75rem}";
    document.head.appendChild(style);
  }

  function getPickerData() {
    const el = document.getElementById("nsm-group-member-picker-data");
    if (!el) return { areas: [] };
    try {
      const parsed = JSON.parse(el.textContent);
      if (!parsed || !Array.isArray(parsed.areas)) return { areas: [] };
      return parsed;
    } catch (_) {
      return { areas: [] };
    }
  }

  function loadInitialMembers() {
    const el = document.getElementById("nsm-group-member-initial");
    if (!el) return;
    try {
      const list = JSON.parse(el.textContent);
      if (!Array.isArray(list)) return;
      list.forEach(function (entry) {
        if (!entry || !entry.id) return;
        state.selected[String(entry.id)] = {
          id: String(entry.id),
          name: entry.name || String(entry.id),
          typeName: entry.typeName || "",
        };
      });
    } catch (_) {}
  }

  function selectedAreaIds() {
    const field = areasFieldEl();
    if (!field) return [];

    if (field.tomselect) {
      const val = field.tomselect.getValue();
      if (Array.isArray(val)) return val.map(function (v) { return String(v); }).filter(Boolean);
      if (typeof val === "string" && val.indexOf(",") !== -1) {
        return val.split(",").map(function (v) { return String(v).trim(); }).filter(Boolean);
      }
      return val ? [String(val)] : [];
    }

    return Array.from(field.options)
      .filter(function (opt) { return opt.selected; })
      .map(function (opt) { return String(opt.value); })
      .filter(Boolean);
  }

  function selectedAreasData() {
    const ids = new Set(selectedAreaIds());
    if (!ids.size) return [];
    return state.data.areas.filter(function (area) {
      return ids.has(String(area.id));
    });
  }

  function entriesForSelection(activeType) {
    const outById = {};
    selectedAreasData().forEach(function (area) {
      area.types.forEach(function (typeDef) {
        if (activeType && typeDef.name !== activeType) return;
        typeDef.entries.forEach(function (entry) {
          const id = String(entry.id);
          if (outById[id]) return;
          outById[id] = {
            id: id,
            name: String(entry.name),
            typeName: String(typeDef.name),
          };
        });
      });
    });
    const out = Object.values(outById);
    out.sort(function (a, b) {
      return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
    });
    return out;
  }

  function pruneSelectedToCurrentAreas() {
    const allowedIds = new Set(entriesForSelection("").map(function (entry) { return entry.id; }));
    Object.keys(state.selected).forEach(function (id) {
      if (!allowedIds.has(String(id))) {
        delete state.selected[String(id)];
      }
    });
  }

  function syncHiddenMembersField() {
    const field = membersFieldEl();
    if (!field) return;

    const ids = Object.keys(state.selected);

    if (field.tomselect) {
      field.tomselect.clear(true);
      ids.forEach(function (id) {
        const item = state.selected[id];
        if (!item) return;
        field.tomselect.addOption({ value: id, text: item.name });
        field.tomselect.addItem(id, true);
      });
      field.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }

    Array.from(field.options).forEach(function (opt) {
      opt.selected = ids.indexOf(String(opt.value)) !== -1;
    });

    ids.forEach(function (id) {
      if (Array.from(field.options).some(function (opt) { return String(opt.value) === id; })) return;
      const item = state.selected[id];
      if (!item) return;
      const option = document.createElement("option");
      option.value = id;
      option.text = item.name;
      option.selected = true;
      field.appendChild(option);
    });

    field.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function selectedTypeNames() {
    return new Set(
      Object.values(state.selected)
        .map(function (entry) { return entry.typeName; })
        .filter(Boolean)
    );
  }

  function render() {
    const root = pickerEl();
    if (!root) return;

    const areas = selectedAreasData();
    if (!areas.length) {
      root.innerHTML = "<div class='alert alert-warning mb-0'>" + esc("Please select at least one area first.") + "</div>";
      syncHiddenMembersField();
      return;
    }

    const rawFilter = state.ui.filter || "";
    const filter = rawFilter.toLowerCase();
    const selectedTypes = selectedTypeNames();

    let typeHint = "";
    if (selectedTypes.size > 1) {
      typeHint = "<div class='alert alert-danger py-2 mb-2'>" + esc("Members must use a single object type.") + "</div>";
    }

    let pills = "<div class='small text-muted mb-1'>" + esc("Objekttyp filtern") + "</div>";
    pills += "<div class='nsm-group-pills'>";
    pills += "<button type='button' class='" + (state.ui.activeType ? "btn btn-sm btn-outline-secondary" : "btn btn-sm btn-secondary") + "' data-nsm-type=''>" + esc("All types") + "</button>";
    const renderedTypes = new Set();
    areas.forEach(function (area) {
      area.types.forEach(function (typeDef) {
        if (renderedTypes.has(typeDef.name)) return;
        renderedTypes.add(typeDef.name);
        const active = state.ui.activeType === typeDef.name;
        pills += "<button type='button' class='" + (active ? "btn btn-sm btn-secondary" : "btn btn-sm btn-outline-secondary") + "' data-nsm-type='" + esc(typeDef.name) + "'>" + esc(typeDef.name) + "</button>";
      });
    });
    pills += "</div>";

    const allEntries = entriesForSelection(state.ui.activeType);
    const available = allEntries.filter(function (entry) {
      if (state.selected[entry.id]) return false;
      if (filter && entry.name.toLowerCase().indexOf(filter) === -1) return false;
      if (selectedTypes.size === 1 && !selectedTypes.has(entry.typeName)) return false;
      return true;
    });

    let options = "<option value=''>" + esc("- select to add -") + "</option>";
    available.forEach(function (entry) {
      const payload = JSON.stringify(entry);
      options += "<option value='" + esc(payload) + "'>" + esc(entry.name) + " - " + esc(entry.typeName) + "</option>";
    });

    let selectedHtml = "";
    const selectedItems = Object.values(state.selected).sort(function (a, b) {
      return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
    });

    if (!selectedItems.length) {
      selectedHtml = "<div class='nsm-selected-empty'>" + esc("None selected") + "</div>";
    } else {
      selectedHtml = "<ul class='list-group'>";
      selectedItems.forEach(function (item) {
        selectedHtml += ""
          + "<li class='list-group-item d-flex justify-content-between align-items-center gap-2 py-1'>"
          + "<div class='d-flex align-items-center gap-2'>"
          + "<input class='form-check-input m-0' type='checkbox' data-nsm-cb='1' data-id='" + esc(item.id) + "' />"
          + "<span>" + esc(item.name) + "</span>"
          + (item.typeName ? "<span class='text-muted small'>" + esc(item.typeName) + "</span>" : "")
          + "</div>"
          + "<button type='button' class='btn btn-sm btn-link text-danger p-0' data-nsm-remove='1' data-id='" + esc(item.id) + "' title='" + esc("Remove") + "'>x</button>"
          + "</li>";
      });
      selectedHtml += "</ul>";
    }

    root.innerHTML = ""
      + typeHint
      + pills
      + "<div class='nsm-group-add-row'>"
      + "<input type='search' class='form-control form-control-sm' placeholder='" + esc("Filter...") + "' data-nsm-filter='1' value='" + esc(rawFilter) + "' />"
      + "</div>"
      + "<div class='nsm-group-add-row'>"
      + "<select class='form-select form-select-sm' data-nsm-available='1'>" + options + "</select>"
      + "<button type='button' class='btn btn-sm btn-primary' data-nsm-add='1'>+ " + esc("Add") + "</button>"
      + "</div>"
      + selectedHtml
      + "<div class='mt-2 d-flex justify-content-end'>"
      + "<button type='button' class='btn btn-sm btn-outline-danger' data-nsm-delete-checked='1'>" + esc("Delete selected") + "</button>"
      + "</div>";

    bindEvents(root);
    syncHiddenMembersField();
  }

  function bindEvents(root) {
    root.querySelectorAll("button[data-nsm-type]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.ui.activeType = btn.dataset.nsmType || "";
        render();
      });
    });

    const filter = root.querySelector("input[data-nsm-filter]");
    if (filter) {
      filter.addEventListener("input", function () {
        state.ui.filter = filter.value;
        render();
        const fresh = pickerEl().querySelector("input[data-nsm-filter]");
        if (fresh) {
          fresh.focus();
          const v = fresh.value;
          fresh.value = "";
          fresh.value = v;
        }
      });
    }

    const addBtn = root.querySelector("button[data-nsm-add]");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        const select = root.querySelector("select[data-nsm-available]");
        if (!select || !select.value) return;
        try {
          const decoded = JSON.parse(select.value);
          if (!decoded.id) return;
          state.selected[String(decoded.id)] = {
            id: String(decoded.id),
            name: decoded.name || String(decoded.id),
            typeName: decoded.typeName || "",
          };
          render();
        } catch (_) {}
      });
    }

    root.querySelectorAll("button[data-nsm-remove]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        delete state.selected[String(btn.dataset.id)];
        render();
      });
    });

    const bulkDelete = root.querySelector("button[data-nsm-delete-checked]");
    if (bulkDelete) {
      bulkDelete.addEventListener("click", function () {
        root.querySelectorAll("input[data-nsm-cb]:checked").forEach(function (cb) {
          delete state.selected[String(cb.dataset.id)];
        });
        render();
      });
    }
  }

  function bindAreaEvents() {
    const field = areasFieldEl();
    if (!field) return;

    const update = function () {
      pruneSelectedToCurrentAreas();
      state.ui.activeType = "";
      state.ui.filter = "";
      render();
    };

    field.addEventListener("change", update);
    field.addEventListener("input", update);

    if (field.tomselect) {
      field.tomselect.on("change", update);
    }
  }

  function init() {
    const root = pickerEl();
    if (!root || root.dataset.nsmReady === "1") return;

    ensureStyles();
    state.data = getPickerData();
    state.selected = {};
    state.ui = { activeType: "", filter: "" };

    loadInitialMembers();
    pruneSelectedToCurrentAreas();
    bindAreaEvents();
    render();

    root.dataset.nsmReady = "1";
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
