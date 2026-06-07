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
    table.querySelectorAll("tbody tr").forEach(function (row) {
      var cell = row.cells[colIndex + 1];
      if (cell) {
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
    var table = document.querySelector(".nsm-viz-table");
    if (!table || table.dataset.nsmAxisHighlightInit === "1") {
      return;
    }
    table.dataset.nsmAxisHighlightInit = "1";

    table.querySelectorAll("tbody th.nsm-row-label").forEach(function (label) {
      var row = label.closest("tr");
      label.addEventListener("mouseenter", function () {
        toggleRowHighlight(row, true);
      });
      label.addEventListener("mouseleave", function () {
        toggleRowHighlight(row, false);
      });
    });

    table.querySelectorAll("thead th.nsm-col-label").forEach(function (header, index) {
      header.addEventListener("mouseenter", function () {
        toggleColumnHighlight(table, index, true);
      });
      header.addEventListener("mouseleave", function () {
        toggleColumnHighlight(table, index, false);
      });
    });
  }

  function initMatrixCellNavigation() {
    var table = document.querySelector(".nsm-viz-table");
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

  function boot() {
    initMatrixFilterForm();
    initMatrixAxisHighlight();
    initMatrixCellNavigation();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
