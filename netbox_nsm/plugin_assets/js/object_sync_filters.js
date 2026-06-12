(function () {
  "use strict";

  function submitSyncQuicksearch(sectionId, formId, pageParam) {
    var form = document.getElementById(formId);
    if (!form) {
      return;
    }
    var action = form.getAttribute("action") || window.location.pathname;
    var url = new URL(action, window.location.origin);
    var params = new URLSearchParams(window.location.search);
    if (pageParam) {
      params.delete(pageParam);
    }
    document.querySelectorAll("#" + sectionId + " .nsm-rules-filter-input").forEach(function (input) {
      var name = input.getAttribute("name");
      if (!name) {
        return;
      }
      var value = (input.value || "").trim();
      if (value) {
        params.set(name, value);
      } else {
        params.delete(name);
      }
    });
    form.querySelectorAll('input[type="hidden"][name]').forEach(function (input) {
      if (input.value) {
        params.set(input.name, input.value);
      } else {
        params.delete(input.name);
      }
    });
    url.search = params.toString();
    window.location.assign(url.toString());
  }

  function syncFilterClearButton(input) {
    var field = input.closest(".nsm-rules-filter-field");
    if (!field) {
      return;
    }
    field.classList.toggle("nsm-rules-filter-field--has-value", !!(input.value || "").trim());
  }

  function bindSection(sectionId, formId, pageParam) {
    var section = document.getElementById(sectionId);
    var form = document.getElementById(formId);
    if (!section || !form || form.dataset.nsmQuicksearchBound === "1") {
      return;
    }
    form.dataset.nsmQuicksearchBound = "1";

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      submitSyncQuicksearch(sectionId, formId, pageParam);
    });

    section.querySelectorAll(".nsm-rules-filter-field").forEach(function (field) {
      var input = field.querySelector(".nsm-rules-filter-input");
      var clearBtn = field.querySelector(".nsm-rules-filter-clear");
      if (!input) {
        return;
      }
      syncFilterClearButton(input);
      input.addEventListener("input", function () {
        syncFilterClearButton(input);
      });
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          submitSyncQuicksearch(sectionId, formId, pageParam);
        }
      });
      input.addEventListener("search", function () {
        if (!(input.value || "").trim()) {
          submitSyncQuicksearch(sectionId, formId, pageParam);
        }
      });
      if (clearBtn) {
        clearBtn.addEventListener("click", function (event) {
          event.preventDefault();
          input.value = "";
          syncFilterClearButton(input);
          submitSyncQuicksearch(sectionId, formId, pageParam);
        });
      }
    });

    section.querySelectorAll(".nsm-sync-filter-apply").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        submitSyncQuicksearch(sectionId, formId, pageParam);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindSection("object-sync", "object-sync-quicksearch", "sync_page");
  });
})();
