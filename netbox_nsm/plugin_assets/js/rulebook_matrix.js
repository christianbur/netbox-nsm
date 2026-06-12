(function () {
  "use strict";

  function toggleRowHighlight(row, active) {
    if (!row) {
      return;
    }
    row.querySelectorAll("th.nsm-row-label, td").forEach(function (cell) {
      cell.classList.toggle("nsm-viz-axis-highlight", active);
      cell.classList.toggle("nsm-viz-row-highlight", active);
    });
  }

  function toggleColumnHighlight(table, colIndex, active) {
    var headers = table.querySelectorAll("thead th.nsm-col-label");
    var header = headers[colIndex];
    if (header) {
      header.classList.toggle("nsm-viz-axis-highlight", active);
      header.classList.toggle("nsm-viz-col-highlight", active);
    }
    table.querySelectorAll("tbody tr:not(.nsm-matrix-spacer)").forEach(function (row) {
      var cell = row.cells[colIndex + 1];
      if (cell && !cell.classList.contains("nsm-matrix-spacer")) {
        cell.classList.toggle("nsm-viz-axis-highlight", active);
        cell.classList.toggle("nsm-viz-col-highlight", active);
      }
    });
  }

  function syncTomSelectValues(form) {
    form.querySelectorAll("select.nsm-matrix-axis-select").forEach(function (select) {
      if (select.tomselect) {
        select.tomselect.sync();
      }
    });
  }

  function initMatrixFilterForm() {
    var form = document.getElementById("nsm-matrix-filter-form");
    if (!form || form.dataset.nsmFilterInit === "1") {
      return;
    }
    form.dataset.nsmFilterInit = "1";

    form.querySelectorAll("select.no-ts").forEach(function (select) {
      if (select.tomselect) {
        select.tomselect.destroy();
      }
    });

    form.addEventListener("submit", function () {
      syncTomSelectValues(form);
    });
  }

  function initMatrixAxisHighlight() {
    var table = document.getElementById("nsm-matrix-table");
    if (!table || table.dataset.nsmAxisHighlightInit === "1") {
      return;
    }
    table.dataset.nsmAxisHighlightInit = "1";

    var activeRow = null;
    var activeColIndex = null;

    function clearHighlights() {
      toggleRowHighlight(activeRow, false);
      if (activeColIndex !== null) {
        toggleColumnHighlight(table, activeColIndex, false);
      }
      activeRow = null;
      activeColIndex = null;
    }

    table.addEventListener("mouseover", function (event) {
      var rowLabel = event.target.closest("tbody th.nsm-row-label");
      if (rowLabel) {
        var row = rowLabel.closest("tr");
        if (row !== activeRow) {
          toggleRowHighlight(activeRow, false);
          activeRow = row;
          toggleRowHighlight(activeRow, true);
        }
        return;
      }
      var colHeader = event.target.closest("thead th.nsm-col-label");
      if (colHeader) {
        var headers = table.querySelectorAll("thead th.nsm-col-label");
        var index = Array.prototype.indexOf.call(headers, colHeader);
        if (index >= 0 && index !== activeColIndex) {
          if (activeColIndex !== null) {
            toggleColumnHighlight(table, activeColIndex, false);
          }
          activeColIndex = index;
          toggleColumnHighlight(table, activeColIndex, true);
        }
      }
    });

    table.addEventListener("mouseleave", clearHighlights);
  }

  function initMatrixCellNavigation() {
    var table = document.getElementById("nsm-matrix-table");
    if (!table || table.dataset.nsmCellNavInit === "1") {
      return;
    }
    table.dataset.nsmCellNavInit = "1";

    table.addEventListener("click", function (event) {
      var target = event.target;
      if (!target || target.closest("a")) {
        return;
      }
      var cell = target.closest("td[data-rules-href]");
      if (!cell) {
        return;
      }
      var href = cell.getAttribute("data-rules-href");
      if (href) {
        window.location.href = href;
      }
    });
  }

  function readMatrixPayload() {
    var node = document.getElementById("nsm-matrix-data");
    if (!node || !node.textContent) {
      return null;
    }
    try {
      return JSON.parse(node.textContent);
    } catch (_err) {
      return null;
    }
  }

  function buildAddHref(payload, srcPk, dstPk) {
    var base = payload.add_url_base || "";
    var rulesUrl = payload.rules_url_base || "";
    var sep = base.indexOf("?") >= 0 ? "&" : "?";
    return (
      base +
      sep +
      "return_url=" +
      encodeURIComponent(rulesUrl) +
      "&source_zone=" +
      srcPk +
      "&destination_zone=" +
      dstPk
    );
  }

  function getCellPayload(payload, srcPk, dstPk) {
    var key = String(srcPk) + ":" + String(dstPk);
    if (payload.cells && Object.prototype.hasOwnProperty.call(payload.cells, key)) {
      return payload.cells[key];
    }
    return {
      fwd: { count: 0, color: null, label: null },
      filter_href: "",
      is_self: srcPk === dstPk,
    };
  }

  function createSpacerCell(widthPx, heightPx) {
    var td = document.createElement("td");
    td.className = "nsm-matrix-spacer";
    td.setAttribute("aria-hidden", "true");
    if (widthPx) {
      td.style.width = widthPx + "px";
      td.style.minWidth = widthPx + "px";
      td.style.maxWidth = widthPx + "px";
    }
    if (heightPx) {
      td.style.height = heightPx + "px";
    }
    return td;
  }

  function renderColumnHeader(dst, colIndex) {
    var th = document.createElement("th");
    th.className = "nsm-col-label";
    th.setAttribute("data-col-index", String(colIndex));
    th.setAttribute("data-zone-pk", String(dst.pk));

    var link = document.createElement("a");
    link.href = dst.url || "#";
    link.className = "nsm-col-text text-decoration-none";
    link.title = dst.label || "";
    link.textContent = dst.label_display || dst.label || "";
    th.appendChild(link);
    return th;
  }

  function renderMatrixColumnHeaders(headRow, dstZones) {
    while (headRow.children.length > 1) {
      headRow.removeChild(headRow.lastChild);
    }
    for (var colIndex = 0; colIndex < dstZones.length; colIndex += 1) {
      headRow.appendChild(renderColumnHeader(dstZones[colIndex], colIndex));
    }
  }

  function renderMatrixCell(payload, src, dst, cellWidth, cellHeight) {
    var cell = getCellPayload(payload, src.pk, dst.pk);
    var td = document.createElement("td");
    td.className = "nsm-viz-data-cell";
    td.setAttribute("data-zone-pk", String(dst.pk));
    var classes = [];
    if (cell.is_self) {
      classes.push("nsm-viz-cell-self");
    }
    if (cell.filter_href) {
      classes.push("nsm-viz-cell-clickable");
      td.setAttribute("data-rules-href", cell.filter_href);
    }
    if (classes.length) {
      td.className += " " + classes.join(" ");
    }
    td.style.width = cellWidth + "px";
    td.style.minWidth = cellWidth + "px";
    td.style.maxWidth = cellWidth + "px";
    td.style.height = cellHeight + "px";
    td.style.minHeight = cellHeight + "px";
    td.style.maxHeight = cellHeight + "px";

    var fwd = cell.fwd || { count: 0 };
    var link = document.createElement("a");
    link.className = "nsm-dir-badge";
    if (fwd.count === 0) {
      link.className += " nsm-dir-badge-empty";
      link.href = buildAddHref(payload, src.pk, dst.pk);
      link.title = "Add Rule";
      link.textContent = "+";
    } else if (fwd.count === 1) {
      link.href = cell.filter_href;
      link.style.backgroundColor = fwd.color || "#888888";
      link.style.color = "#fff";
      link.title = fwd.label || "";
      link.textContent = fwd.label || "?";
    } else {
      link.className += " nsm-dir-badge-count";
      link.href = cell.filter_href;
      link.title = fwd.count + " Rules";
      link.textContent = String(fwd.count);
    }
    td.appendChild(link);
    return td;
  }

  function initMatrixVirtualScroll() {
    var payload = readMatrixPayload();
    var wrapper = document.getElementById("nsm-matrix-scroll");
    var tbody = document.getElementById("nsm-matrix-body");
    var headRow = document.getElementById("nsm-matrix-head-row");
    if (!payload || !wrapper || !tbody || !headRow) {
      return;
    }

    var srcZones = payload.src_zones || [];
    var dstZones = payload.dst_zones || [];
    if (!srcZones.length || !dstZones.length) {
      tbody.innerHTML = "";
      while (headRow.children.length > 1) {
        headRow.removeChild(headRow.lastChild);
      }
      return;
    }

    renderMatrixColumnHeaders(headRow, dstZones);

    var cellWidth = payload.cell_width || 48;
    var cellHeight = payload.cell_height || 48;
    var defaultRows = payload.default_rows || 50;
    var rowBuffer = payload.row_buffer || 5;
    var renderScheduled = false;
    var lastRange = null;

    function visibleRange() {
      var scrollTop = wrapper.scrollTop;
      var viewHeight = wrapper.clientHeight;
      var scrollStartRow = Math.max(0, Math.floor(scrollTop / cellHeight) - rowBuffer);
      var scrollEndRow = Math.min(
        srcZones.length,
        Math.ceil((scrollTop + viewHeight) / cellHeight) + rowBuffer
      );
      var defaultEndRow = Math.min(srcZones.length, defaultRows);
      return {
        startRow: scrollStartRow,
        endRow: Math.max(scrollEndRow, defaultEndRow),
      };
    }

    function rangesEqual(a, b) {
      return a && b && a.startRow === b.startRow && a.endRow === b.endRow;
    }

    function appendVerticalSpacer(fragment, heightPx) {
      var spacerRow = document.createElement("tr");
      spacerRow.className = "nsm-matrix-spacer";
      var spacerCell = createSpacerCell(null, heightPx);
      spacerCell.colSpan = 1 + dstZones.length;
      spacerRow.appendChild(spacerCell);
      fragment.appendChild(spacerRow);
    }

    function renderViewport() {
      renderScheduled = false;
      var range = visibleRange();
      if (rangesEqual(range, lastRange)) {
        return;
      }
      lastRange = range;

      var scrollTop = wrapper.scrollTop;
      var scrollLeft = wrapper.scrollLeft;
      var fragment = document.createDocumentFragment();
      var topHeight = range.startRow * cellHeight;
      if (topHeight > 0) {
        appendVerticalSpacer(fragment, topHeight);
      }

      for (var rowIndex = range.startRow; rowIndex < range.endRow; rowIndex += 1) {
        var src = srcZones[rowIndex];
        var tr = document.createElement("tr");
        tr.style.height = cellHeight + "px";

        var rowLabel = document.createElement("th");
        rowLabel.className = "nsm-row-label";
        rowLabel.title = src.label || "";
        var rowLink = document.createElement("a");
        rowLink.href = src.url || "#";
        rowLink.className = "text-decoration-none";
        rowLink.style.color = "inherit";
        rowLink.textContent = src.label_display || src.label || "";
        rowLabel.appendChild(rowLink);
        tr.appendChild(rowLabel);

        for (var colIndex = 0; colIndex < dstZones.length; colIndex += 1) {
          tr.appendChild(
            renderMatrixCell(payload, src, dstZones[colIndex], cellWidth, cellHeight)
          );
        }

        fragment.appendChild(tr);
      }

      var bottomHeight = (srcZones.length - range.endRow) * cellHeight;
      if (bottomHeight > 0) {
        appendVerticalSpacer(fragment, bottomHeight);
      }

      tbody.replaceChildren(fragment);
      wrapper.scrollTop = scrollTop;
      wrapper.scrollLeft = scrollLeft;
    }

    function scheduleRender() {
      if (renderScheduled) {
        return;
      }
      renderScheduled = true;
      window.requestAnimationFrame(renderViewport);
    }

    wrapper.addEventListener("scroll", scheduleRender, { passive: true });
    window.addEventListener("resize", scheduleRender);
    renderViewport();
  }

  function boot() {
    initMatrixFilterForm();
    initMatrixVirtualScroll();
    initMatrixAxisHighlight();
    initMatrixCellNavigation();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
