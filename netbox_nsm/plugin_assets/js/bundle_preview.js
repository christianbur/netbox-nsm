(function (global) {
  "use strict";

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatValue(value) {
    if (value === null || value === undefined || value === "") {
      return "—";
    }
    if (typeof value === "object") {
      return escapeHtml(JSON.stringify(value));
    }
    return escapeHtml(value);
  }

  function opBadge(op, i18n) {
    const labels = {
      add: i18n.opAdd,
      alter: i18n.opAlter,
      remove: i18n.opRemove,
      pending: i18n.pending,
    };
    const classes = {
      add: "bg-success-subtle text-success border border-success-subtle",
      alter: "bg-warning-subtle text-warning border border-warning-subtle",
      remove: "bg-danger-subtle text-danger border border-danger-subtle",
      pending: "bg-secondary-subtle text-secondary border border-secondary-subtle",
    };
    const label = labels[op] || op;
    const cls = classes[op] || classes.pending;
    return '<span class="badge ' + cls + '">' + escapeHtml(label) + "</span>";
  }

  function countCotChanges(cotDiff) {
    if (!cotDiff || !cotDiff.length) {
      return 0;
    }
    return cotDiff.filter(function (entry) {
      return entry.is_new || entry.has_changes || (entry.warnings && entry.warnings.length);
    }).length;
  }

  function hasDestructiveChanges(data) {
    return (data.cot_diff || []).some(function (entry) {
      return entry.has_destructive_changes;
    });
  }

  function renderChangedPairs(pairs, i18n) {
    if (!pairs || typeof pairs !== "object" || !Object.keys(pairs).length) {
      return "";
    }
    let rows = "";
    Object.entries(pairs).forEach(function ([key, values]) {
      const before = Array.isArray(values) ? values[0] : values;
      const after = Array.isArray(values) ? values[1] : "";
      rows += "<tr><th class=\"text-muted fw-normal\">" + escapeHtml(key) + "</th>"
        + "<td><code class=\"small\">" + formatValue(before) + "</code></td>"
        + "<td><code class=\"small\">" + formatValue(after) + "</code></td></tr>";
    });
    return '<div class="table-responsive"><table class="table table-sm table-bordered mb-0 nsm-bundle-diff-table">'
      + "<thead><tr><th>" + escapeHtml(i18n.attribute) + "</th><th>" + escapeHtml(i18n.before)
      + "</th><th>" + escapeHtml(i18n.after) + "</th></tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function fieldChangeName(fc) {
    return fc.db_name || (fc.schema_def && fc.schema_def.name) || "—";
  }

  function isSimpleFieldAdd(fc) {
    return fc.op === "add" && (!fc.changed_attrs || !Object.keys(fc.changed_attrs).length);
  }

  function renderFieldAddList(fieldChanges) {
    let items = "";
    fieldChanges.forEach(function (fc) {
      items += "<li><code>" + escapeHtml(fieldChangeName(fc)) + "</code></li>";
    });
    return '<ul class="nsm-bundle-field-add-list">' + items + "</ul>";
  }

  function renderFieldChanges(fieldChanges, i18n) {
    if (!fieldChanges || !fieldChanges.length) {
      return "";
    }
    if (fieldChanges.every(isSimpleFieldAdd)) {
      return renderFieldAddList(fieldChanges);
    }

    let rows = "";
    fieldChanges.forEach(function (fc) {
      const fieldName = fieldChangeName(fc);
      if (isSimpleFieldAdd(fc)) {
        rows += "<tr><td>" + opBadge(fc.op, i18n) + "</td>"
          + "<td colspan=\"2\"><code>" + escapeHtml(fieldName) + "</code></td>"
          + "<td>—</td></tr>";
        return;
      }
      let details = "—";
      if (fc.changed_attrs && Object.keys(fc.changed_attrs).length) {
        details = renderChangedPairs(fc.changed_attrs, i18n);
      } else if (fc.schema_def) {
        details = '<code class="small">' + formatValue(fc.schema_def.name || fc.schema_def) + "</code>";
      }
      rows += "<tr><td>" + opBadge(fc.op, i18n) + "</td>"
        + "<td><code>" + escapeHtml(fc.schema_id) + "</code></td>"
        + "<td><code>" + escapeHtml(fieldName) + "</code></td>"
        + "<td>" + details + "</td></tr>";
    });
    return '<div class="table-responsive"><table class="table table-sm table-hover mb-0 nsm-bundle-diff-table">'
      + "<thead><tr><th>" + escapeHtml(i18n.operation) + "</th><th>" + escapeHtml(i18n.schemaId)
      + "</th><th>" + escapeHtml(i18n.field) + "</th><th>" + escapeHtml(i18n.details) + "</th></tr></thead>"
      + "<tbody>" + rows + "</tbody></table></div>";
  }

  function renderCotTab(data, i18n) {
    const entries = (data.cot_diff || []).filter(function (entry) {
      return entry.is_new || entry.has_changes || (entry.warnings && entry.warnings.length);
    });
    if (!entries.length) {
      return '<div class="nsm-bundle-preview-empty text-muted">'
        + '<div class="mdi mdi-check-circle-outline text-success mb-2" aria-hidden="true"></div>'
        + "<p class=\"mb-0\">" + escapeHtml(i18n.noSchemaChanges) + "</p></div>";
    }

    let html = "";
    entries.forEach(function (entry) {
      const badges = [];
      if (entry.is_new) {
        badges.push('<span class="badge bg-primary-subtle text-primary border border-primary-subtle">' + escapeHtml(i18n.newType) + "</span>");
      } else if (entry.has_changes) {
        badges.push('<span class="badge bg-info-subtle text-info border border-info-subtle">' + escapeHtml(i18n.changed) + "</span>");
      }
      if (entry.has_destructive_changes) {
        badges.push('<span class="badge bg-danger-subtle text-danger border border-danger-subtle">' + escapeHtml(i18n.destructive) + "</span>");
      }

      html += '<div class="card mb-3 nsm-bundle-cot-card"><div class="card-header py-2 d-flex flex-wrap align-items-center gap-2">'
        + '<code class="mb-0">' + escapeHtml(entry.slug) + "</code>";
      if (entry.name) {
        html += '<span class="text-muted small">' + escapeHtml(entry.name) + "</span>";
      }
      html += badges.join(" ") + "</div><div class=\"card-body py-2\">";

      if (entry.warnings && entry.warnings.length) {
        html += '<div class="alert alert-warning py-2 px-3 mb-2 small"><strong>' + escapeHtml(i18n.warnings) + ":</strong><ul class=\"mb-0 ps-3\">";
        entry.warnings.forEach(function (warning) {
          html += "<li>" + escapeHtml(warning) + "</li>";
        });
        html += "</ul></div>";
      }
      if (entry.cot_changes && Object.keys(entry.cot_changes).length) {
        html += '<div class="text-muted text-uppercase small fw-semibold mb-2">' + escapeHtml(i18n.typeAttributes) + "</div>";
        html += renderChangedPairs(entry.cot_changes, i18n);
      }
      if (entry.field_changes && entry.field_changes.length) {
        html += '<div class="text-muted text-uppercase small fw-semibold mt-3 mb-2">' + escapeHtml(i18n.fieldChanges) + "</div>";
        html += renderFieldChanges(entry.field_changes, i18n);
      }
      html += "</div></div>";
    });
    return html;
  }

  function renderChoiceSetDiff(diffs, i18n) {
    if (!diffs || !diffs.length) {
      return "";
    }
    let rows = "";
    diffs.forEach(function (entry) {
      let details = "";
      if (entry.op === "add") {
        details = "<code class=\"small\">" + escapeHtml((entry.desired_choices || []).join(", ")) + "</code>";
      } else if (entry.op === "alter") {
        details = '<div class="small"><span class="text-muted">' + escapeHtml(i18n.current) + ":</span> <code>"
          + escapeHtml((entry.current_choices || []).join(", ")) + "</code><br>"
          + '<span class="text-muted">' + escapeHtml(i18n.desired) + ":</span> <code>"
          + escapeHtml((entry.desired_choices || []).join(", ")) + "</code></div>";
      }
      rows += "<tr><td>" + opBadge(entry.op, i18n) + "</td><td><code>" + escapeHtml(entry.name) + "</code></td><td>" + details + "</td></tr>";
    });
    return '<div class="text-muted text-uppercase small fw-semibold mb-2">' + escapeHtml(i18n.choiceSets) + "</div>"
      + '<div class="table-responsive mb-3"><table class="table table-sm table-hover mb-0 nsm-bundle-diff-table">'
      + "<thead><tr><th>" + escapeHtml(i18n.operation) + "</th><th>" + escapeHtml(i18n.name) + "</th><th>" + escapeHtml(i18n.choices) + "</th></tr></thead>"
      + "<tbody>" + rows + "</tbody></table></div>";
  }

  function renderObjectDiff(diffs, i18n) {
    if (!diffs || !diffs.length) {
      return "";
    }
    let rows = "";
    diffs.forEach(function (entry) {
      let details = "—";
      if (entry.op === "pending") {
        details = escapeHtml(i18n.typeNotInDb) + ": <code>" + escapeHtml((entry.names || []).join(", ")) + "</code>";
      } else if (entry.op === "add") {
        details = renderChangedPairs(
          Object.fromEntries(
            Object.entries(entry.fields || {}).map(function ([key, value]) {
              return [key, ["", value]];
            })
          ),
          i18n
        );
      } else if (entry.op === "alter") {
        details = renderChangedPairs(
          Object.fromEntries(
            Object.entries(entry.changes || {}).map(function ([key, value]) {
              return [key, [value.current, value.desired]];
            })
          ),
          i18n
        );
      }
      const nameCell = entry.name
        ? "<code>" + escapeHtml(entry.name) + "</code>"
        : "<span class=\"text-muted\">" + escapeHtml((entry.names || []).join(", ") || "—") + "</span>";
      rows += "<tr><td>" + opBadge(entry.op, i18n) + "</td><td><code>" + escapeHtml(entry.type) + "</code></td>"
        + "<td>" + nameCell + "</td><td>" + details + "</td></tr>";
    });
    return '<div class="text-muted text-uppercase small fw-semibold mb-2">' + escapeHtml(i18n.seedObjects) + "</div>"
      + '<div class="table-responsive mb-3"><table class="table table-sm table-hover mb-0 nsm-bundle-diff-table">'
      + "<thead><tr><th>" + escapeHtml(i18n.operation) + "</th><th>" + escapeHtml(i18n.type) + "</th><th>" + escapeHtml(i18n.name) + "</th><th>" + escapeHtml(i18n.details) + "</th></tr></thead>"
      + "<tbody>" + rows + "</tbody></table></div>";
  }

  function renderMetadataBlock(title, entries, i18n) {
    if (!entries || !Object.keys(entries).length) {
      return "";
    }
    let html = '<div class="text-muted text-uppercase small fw-semibold mb-2">' + escapeHtml(title) + "</div>";
    Object.entries(entries).forEach(function ([slug, block]) {
      html += '<details class="nsm-bundle-metadata-block mb-2 border rounded px-3 py-2">'
        + "<summary><code>" + escapeHtml(slug) + "</code></summary>"
        + '<pre class="small p-2 mb-0 mt-2 border rounded bg-body-secondary text-body overflow-auto" style="max-height:12rem">'
        + formatValue(block) + "</pre></details>";
    });
    return html;
  }

  function renderSideEffectsTab(data, i18n) {
    const choiceSets = renderChoiceSetDiff(data.choice_set_diff, i18n);
    const objects = renderObjectDiff(data.object_diff, i18n);
    const metadata = renderMetadataBlock(i18n.typeMetadata, (data.metadata || {}).types, i18n)
      + renderMetadataBlock(i18n.rulebookMetadata, (data.metadata || {}).rulebooks, i18n);
    if (!choiceSets && !objects && !metadata) {
      return '<div class="nsm-bundle-preview-empty text-muted">'
        + '<div class="mdi mdi-check-circle-outline text-success mb-2" aria-hidden="true"></div>'
        + "<p class=\"mb-0\">" + escapeHtml(i18n.noSideEffects) + "</p></div>";
    }
    return choiceSets + objects + metadata;
  }

  function renderSummary(data, i18n) {
    const cotCount = countCotChanges(data.cot_diff);
    const choiceCount = (data.choice_set_diff || []).length;
    const objectCount = (data.object_diff || []).length;
    const metaCount = Object.keys((data.metadata || {}).types || {}).length
      + Object.keys((data.metadata || {}).rulebooks || {}).length;
    const destructive = hasDestructiveChanges(data);
    const noChanges = !cotCount && !choiceCount && !objectCount && !metaCount;

    let html = "";
    if (noChanges) {
      html += '<span class="badge bg-success-subtle text-success border border-success-subtle">'
        + '<i class="mdi mdi-check me-1" aria-hidden="true"></i>' + escapeHtml(i18n.noChanges) + "</span>";
    } else {
      if (cotCount) {
        html += '<span class="badge bg-info-subtle text-info border border-info-subtle me-1">'
          + escapeHtml(cotCount + " " + i18n.summaryTypes) + "</span>";
      }
      if (choiceCount) {
        html += '<span class="badge bg-info-subtle text-info border border-info-subtle me-1">'
          + escapeHtml(choiceCount + " " + i18n.summaryChoiceSets) + "</span>";
      }
      if (objectCount) {
        html += '<span class="badge bg-info-subtle text-info border border-info-subtle me-1">'
          + escapeHtml(objectCount + " " + i18n.summaryObjects) + "</span>";
      }
      if (metaCount) {
        html += '<span class="badge bg-info-subtle text-info border border-info-subtle me-1">'
          + escapeHtml(metaCount + " " + i18n.summaryMetadata) + "</span>";
      }
    }
    if (destructive) {
      html += '<span class="badge bg-danger-subtle text-danger border border-danger-subtle me-1">'
        + '<i class="mdi mdi-alert-outline me-1" aria-hidden="true"></i>' + escapeHtml(i18n.destructive) + "</span>";
    }
    if (data.destructive_blocked) {
      html += '<span class="badge bg-warning-subtle text-warning border border-warning-subtle">'
        + escapeHtml(i18n.blocked) + "</span>";
    }
    return html;
  }

  function init(config) {
    const root = config.root;
    if (!root) {
      return;
    }

    const i18n = config.i18n || {};
    const previewUrl = config.previewUrl;
    const toggleBtn = root.querySelector("#bundlePreviewToggle");
    const panel = root.querySelector("#bundlePreviewPanel");
    const summaryEl = root.querySelector("#bundlePreviewSummary");
    const loadingEl = root.querySelector("#bundlePreviewLoading");
    const errorEl = root.querySelector("#bundlePreviewError");
    const schemaTab = root.querySelector("#bundlePreviewSchema");
    const sideTab = root.querySelector("#bundlePreviewSideEffects");
    const destructiveEl = root.querySelector("#allowDestructive");
    const destructiveAlert = root.querySelector("#bundlePreviewDestructiveAlert");
    let previewRequestId = 0;
    let panelOpen = false;
    let lastData = null;

    function csrfToken() {
      const input = root.querySelector("[name=csrfmiddlewaretoken]");
      return input ? input.value : "";
    }

    function setState(state, message) {
      loadingEl.classList.toggle("d-none", state !== "loading");
      errorEl.classList.toggle("d-none", state !== "error");
      root.querySelector("#bundlePreviewTabs").classList.toggle("d-none", state !== "content");
      if (state === "error") {
        errorEl.textContent = message || i18n.previewFailed;
      }
    }

    function syncDestructiveAlert(data) {
      if (!destructiveAlert) {
        return;
      }
      const show = data && (hasDestructiveChanges(data) || data.destructive_blocked);
      destructiveAlert.classList.toggle("d-none", !show);
      if (show) {
        destructiveAlert.textContent = data.destructive_blocked
          ? i18n.destructiveBlocked
          : i18n.destructivePresent;
      }
    }

    function renderPreview(data) {
      lastData = data;
      summaryEl.innerHTML = renderSummary(data, i18n);
      summaryEl.classList.remove("d-none");
      schemaTab.innerHTML = renderCotTab(data, i18n);
      sideTab.innerHTML = renderSideEffectsTab(data, i18n);
      syncDestructiveAlert(data);
      setState("content");
    }

    function fetchPreview() {
      const requestId = ++previewRequestId;
      setState("loading");
      const body = new URLSearchParams();
      body.set("csrfmiddlewaretoken", csrfToken());
      if (destructiveEl && destructiveEl.checked) {
        body.set("allow_destructive", "1");
      }

      fetch(previewUrl, {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: body.toString(),
        credentials: "same-origin",
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return {ok: response.ok, data: data};
          });
        })
        .then(function (result) {
          if (requestId !== previewRequestId) {
            return;
          }
          if (!result.ok) {
            setState("error", result.data.error || i18n.previewFailed);
            return;
          }
          renderPreview(result.data);
        })
        .catch(function () {
          if (requestId !== previewRequestId) {
            return;
          }
          setState("error", i18n.previewFailed);
        });
    }

    function stickyHeaderOffset() {
      const navbar = document.querySelector(".navbar");
      if (navbar) {
        return navbar.getBoundingClientRect().height;
      }
      return 88;
    }

    function scrollPanelIntoView(targetPanel) {
      const headerOffset = stickyHeaderOffset();
      const extraPadding = 12;
      const top = targetPanel.getBoundingClientRect().top + window.scrollY - headerOffset - extraPadding;
      window.scrollTo({top: Math.max(0, top), behavior: "smooth"});
    }

    function openPanel() {
      panelOpen = true;
      panel.classList.remove("d-none");
      toggleBtn.setAttribute("aria-expanded", "true");
      toggleBtn.innerHTML = '<i class="mdi mdi-refresh me-1" aria-hidden="true"></i>' + i18n.refreshPreview;
    }

    function togglePanel() {
      if (!panelOpen) {
        openPanel();
        fetchPreview();
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            scrollPanelIntoView(panel);
          });
        });
        return;
      }
      fetchPreview();
    }

    toggleBtn.addEventListener("click", togglePanel);

    if (destructiveEl) {
      destructiveEl.addEventListener("change", function () {
        if (panelOpen) {
          fetchPreview();
        }
      });
    }

    if (config.autoOpen) {
      openPanel();
      fetchPreview();
    }
  }

  global.NSMBundlePreview = {init: init};
})(window);
