(function () {
  const SECTION_DEFS = {
    source: [
      { field: "source_zones", label: "Zone", sourceField: "source_zones" },
      { field: "custom_srcdst_objects", label: "Object", sourceField: "custom_srcdst_objects" },
      { field: "source_groups", label: "Group", sourceField: "source_groups" },
    ],
    destination: [
      { field: "destination_zones", label: "Zone", sourceField: "destination_zones" },
      { field: "destination_custom_objects", label: "Object", sourceField: "destination_custom_objects" },
      { field: "destination_groups", label: "Group", sourceField: "destination_groups" },
    ],
    service: [
      { field: "services", label: "Service", sourceField: "services" },
      { field: "applications", label: "Application", sourceField: "applications" },
      { field: "application_sets", label: "Application Set", sourceField: "application_sets" },
      { field: "custom_service_objects", label: "Object", sourceField: "custom_service_objects" },
      { field: "service_groups", label: "Group", sourceField: "service_groups" },
    ],
    action: [
      { field: "policy_action", label: "Default Action", sourceField: "policy_action" },
      { field: "custom_action_objects", label: "Object", sourceField: "custom_action_objects" },
      { field: "action_groups", label: "Group", sourceField: "action_groups" },
    ],
  };

  function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === "function") {
      return window.CSS.escape(value);
    }
    return String(value).replace(/([^a-zA-Z0-9_-])/g, "\\$1");
  }

  function ensureStyles() {
    if (document.getElementById("nsm-security-rule-table-style")) {
      return;
    }

    const style = document.createElement("style");
    style.id = "nsm-security-rule-table-style";
    style.textContent = "\n      .nsm-selection-empty { color: #64748b; }\n      .nsm-delete-icon { border: 0; background: transparent; color: #d03c3c; font-size: 1.1rem; line-height: 1; padding: 0 .25rem; }\n      .nsm-delete-icon:hover { color: #a32626; }\n    ";
    document.head.appendChild(style);
  }

  function getSectionRoot(section) {
    return document.querySelector(".nsm-table-section[data-section='" + cssEscape(section) + "']");
  }

  function getHiddenField(section, fieldName) {
    const root = getSectionRoot(section);
    if (!root) {
      return null;
    }
    return root.querySelector("select[name='" + cssEscape(fieldName) + "']");
  }

  function getObjectSelect(section) {
    return document.querySelector("[data-add-object='" + cssEscape(section) + "']");
  }

  function getAddButton(section) {
    return document.querySelector("[data-add-row='" + cssEscape(section) + "']");
  }

  function encodeOption(field, value, label) {
    return JSON.stringify({ field: field, value: String(value), label: String(label) });
  }

  function decodeOption(value) {
    try {
      const parsed = JSON.parse(value);
      if (!parsed || typeof parsed !== "object") {
        return null;
      }
      if (!parsed.field || !parsed.value || !parsed.label) {
        return null;
      }
      return parsed;
    } catch (_err) {
      return null;
    }
  }

  function getDisplayMap() {
    const map = {};
    Object.keys(SECTION_DEFS).forEach((section) => {
      SECTION_DEFS[section].forEach((def) => {
        map[def.field + "::" + def.sourceField] = def.label;
      });
    });
    return map;
  }

  const DISPLAY_MAP = getDisplayMap();
  const selectionLabels = {};

  function getTypeLabel(fieldName, sourceField) {
    return DISPLAY_MAP[fieldName + "::" + sourceField] || fieldName;
  }

  function setSelectionLabel(section, fieldName, value, label) {
    if (!selectionLabels[section]) {
      selectionLabels[section] = {};
    }
    if (!selectionLabels[section][fieldName]) {
      selectionLabels[section][fieldName] = {};
    }
    selectionLabels[section][fieldName][String(value)] = String(label);
  }

  function clearSelectionLabel(section, fieldName, value) {
    if (selectionLabels[section] && selectionLabels[section][fieldName]) {
      delete selectionLabels[section][fieldName][String(value)];
    }
  }

  function getSelectionLabel(section, fieldName, value, fallback) {
    return (((selectionLabels[section] || {})[fieldName] || {})[String(value)]) || fallback;
  }

  function populateObjectSelect(section) {
    const objectSelect = getObjectSelect(section);
    if (!objectSelect) {
      return;
    }

    objectSelect.innerHTML = "";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Bitte auswählen";
    objectSelect.appendChild(placeholder);

    const definitions = SECTION_DEFS[section] || [];
    definitions.forEach((def) => {
      const field = getHiddenField(section, def.sourceField);
      if (!field) {
        return;
      }

      Array.from(field.options)
        .filter((opt) => !!opt.value)
        .forEach((opt) => {
          const option = document.createElement("option");
          option.value = encodeOption(def.field, opt.value, def.label);
          option.textContent = def.label + " · " + opt.textContent.trim();
          objectSelect.appendChild(option);
        });
    });

    objectSelect.disabled = objectSelect.options.length <= 1;
    objectSelect.value = "";
  }

  function selectInHiddenField(section, fieldName, value, label) {
    const field = getHiddenField(section, fieldName);
    if (!field) {
      return;
    }

    let target = Array.from(field.options).find((opt) => String(opt.value) === String(value));
    if (!target) {
      return;
    }

    if (field.multiple) {
      target.selected = true;
    } else {
      field.value = String(value);
    }

    field.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function unselectInHiddenField(section, fieldName, value) {
    const field = getHiddenField(section, fieldName);
    if (!field) {
      return;
    }

    if (field.multiple) {
      Array.from(field.options).forEach((opt) => {
        if (String(opt.value) === String(value)) {
          opt.selected = false;
        }
      });
    } else if (String(field.value) === String(value)) {
      field.value = "";
    }

    field.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function selectedRows(section) {
    const rows = [];
    const seenFields = new Set();

    (SECTION_DEFS[section] || []).forEach((def) => {
      if (seenFields.has(def.sourceField)) {
        return;
      }
      seenFields.add(def.sourceField);

      const field = getHiddenField(section, def.sourceField);
      if (!field) {
        return;
      }

      const selected = field.multiple
        ? Array.from(field.options).filter((opt) => opt.selected)
        : (field.value ? [field.options[field.selectedIndex]] : []);

      selected.forEach((opt) => {
        if (!opt || !opt.value) {
          return;
        }

        rows.push({
          field: def.sourceField,
          value: String(opt.value),
          text: opt.textContent.trim(),
          typeLabel: getSelectionLabel(section, def.sourceField, String(opt.value), def.label),
        });
      });
    });

    rows.sort((a, b) => {
      const typeCmp = a.typeLabel.localeCompare(b.typeLabel, undefined, { sensitivity: "base" });
      if (typeCmp !== 0) {
        return typeCmp;
      }
      return a.text.localeCompare(b.text, undefined, { sensitivity: "base" });
    });

    return rows;
  }

  function renderTable(section) {
    const body = document.querySelector("[data-selection-table='" + cssEscape(section) + "']");
    if (!body) {
      return;
    }

    const rows = selectedRows(section);
    body.innerHTML = "";

    if (!rows.length) {
      const tr = document.createElement("tr");
      tr.innerHTML = "<td colspan='3' class='nsm-selection-empty'>No objects selected.</td>";
      body.appendChild(tr);
      return;
    }

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + row.typeLabel + "</td>" +
        "<td>" + row.text + "</td>" +
        "<td class='text-end'><button type='button' class='nsm-delete-icon' data-remove-section='" + section + "' data-remove-field='" + row.field + "' data-remove-value='" + row.value + "' title='Delete' aria-label='Delete'>x</button></td>";
      body.appendChild(tr);
    });
  }

  function renderAll() {
    Object.keys(SECTION_DEFS).forEach((section) => {
      renderTable(section);
    });
  }

  function bindSection(section) {
    const objectSelect = getObjectSelect(section);
    const addBtn = getAddButton(section);
    if (!objectSelect || !addBtn) {
      return;
    }

    addBtn.addEventListener("click", function () {
      const decoded = decodeOption(objectSelect.value);
      if (!decoded) {
        return;
      }

      setSelectionLabel(section, decoded.field, decoded.value, decoded.label);
      selectInHiddenField(section, decoded.field, decoded.value, objectSelect.options[objectSelect.selectedIndex].textContent.trim());
      renderTable(section);
      objectSelect.value = "";
    });
  }

  function bindDelete() {
    document.querySelectorAll("[data-selection-table]").forEach((body) => {
      body.addEventListener("click", function (event) {
        const button = event.target.closest("[data-remove-field]");
        if (!button) {
          return;
        }

        const section = button.dataset.removeSection;
        const field = button.dataset.removeField;
        const value = button.dataset.removeValue;
        clearSelectionLabel(section, field, value);
        unselectInHiddenField(section, field, value);
        renderTable(section);
      });
    });
  }

  function bindHiddenSync() {
    Object.keys(SECTION_DEFS).forEach((section) => {
      const uniqueFields = new Set(SECTION_DEFS[section].map((def) => def.sourceField));
      uniqueFields.forEach((fieldName) => {
        const field = getHiddenField(section, fieldName);
        if (field) {
          field.addEventListener("change", function () {
            renderTable(section);
          });
        }
      });
    });
  }

  function init() {
    const sourceRoot = getSectionRoot("source");
    if (!sourceRoot || sourceRoot.dataset.nsmAddReady === "1") {
      return;
    }

    ensureStyles();
    Object.keys(SECTION_DEFS).forEach(bindSection);
    bindDelete();
    bindHiddenSync();
    renderAll();

    sourceRoot.dataset.nsmAddReady = "1";
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
