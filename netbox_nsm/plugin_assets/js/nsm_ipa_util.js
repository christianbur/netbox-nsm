/**
 * Shared IP Analyzer utilities (i18n, fetch, object normalization, diff helpers).
 */
(function () {
  "use strict";

  var TAB_TITLE_MAX = 28;

  function ipaT(key, fallback) {
    var i18n = window.NSM_IPA_I18N || {};
    if (i18n[key] != null && i18n[key] !== "") {
      return i18n[key];
    }
    return fallback != null ? fallback : key;
  }

  function ipaTf(key, params, fallback) {
    var text = ipaT(key, fallback);
    if (params) {
      Object.keys(params).forEach(function (k) {
        text = text.split("%(" + k + ")s").join(String(params[k]));
      });
    }
    return text;
  }

  function escHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function formatTypeCountSummary(tab) {
    if (!tab) {
      return "";
    }
    if (
      tab.countSubnets != null ||
      tab.countRanges != null ||
      tab.countIps != null
    ) {
      var parts = [
        ipaTf("Subnets: %(count)s", { count: tab.countSubnets || 0 }),
        ipaTf("Ranges: %(count)s", { count: tab.countRanges || 0 }),
        ipaTf("IPs: %(count)s", {
          count: tab.countIps != null ? tab.countIps : tab.leafCount || 0,
        }),
      ];
      if (tab.countDuplicates) {
        parts.push(ipaTf("Warnings: %(count)s", { count: tab.countDuplicates }));
      }
      if (tab.countGroupDuplicates) {
        parts.push(ipaTf("Duplicates: %(count)s", { count: tab.countGroupDuplicates }));
      }
      return parts.join("  ");
    }
    return tab.leafCount
      ? ipaTf("IPs: %(count)s", { count: tab.leafCount })
      : "";
  }

  function apiUrl() {
    return window.NSM_IP_ANALYSIS_API || "/plugins/netbox-nsm/api/ip-analysis/";
  }

  function addObjectTypesApiUrl() {
    return (
      window.NSM_IP_ANALYSIS_ADD_OBJECT_TYPES_API ||
      "/plugins/netbox-nsm/api/ip-analysis/add-object-types/"
    );
  }

  function debounce(fn, ms) {
    var timer;
    return function () {
      var args = arguments;
      var ctx = this;
      clearTimeout(timer);
      timer = setTimeout(function () {
        fn.apply(ctx, args);
      }, ms);
    };
  }

  function getCsrfToken() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function nsmFetch(url, options) {
    if (window.NSM_BRANCH_API && window.NSM_BRANCH_API.fetch) {
      return window.NSM_BRANCH_API.fetch(url, options);
    }
    return fetch(url, options);
  }

  var IPA_ANALYSIS_TIMEOUT_MS = 120000;

  function parseIpaApiErrorBody(body, status) {
    if (body && typeof body === "object") {
      if (body.error != null && body.error !== "") {
        return String(body.error);
      }
      if (body.detail != null && body.detail !== "") {
        return String(body.detail);
      }
      if (body.message != null && body.message !== "") {
        return String(body.message);
      }
    }
    if (status) {
      return ipaTf("Analysis failed (HTTP %(status)s).", { status: status });
    }
    return ipaT("Analysis could not be loaded.");
  }

  function readIpaApiJson(resp) {
    return resp.text().then(function (text) {
      var body = null;
      if (text) {
        try {
          body = JSON.parse(text);
        } catch (_) {
          body = null;
        }
      }
      if (!resp.ok) {
        throw new Error(parseIpaApiErrorBody(body, resp.status));
      }
      if (body == null) {
        throw new Error(ipaT("Analysis could not be loaded."));
      }
      return body;
    });
  }

  function fetchIpaAnalysis(url, options, timeoutMs) {
    options = options || {};
    var ms = timeoutMs == null ? IPA_ANALYSIS_TIMEOUT_MS : timeoutMs;
    if (ms > 0 && typeof AbortController !== "undefined") {
      var timeoutCtrl = new AbortController();
      var timer = setTimeout(function () {
        timeoutCtrl.abort();
      }, ms);
      var userSignal = options.signal;
      if (userSignal) {
        if (userSignal.aborted) {
          timeoutCtrl.abort();
        } else {
          userSignal.addEventListener("abort", function () {
            timeoutCtrl.abort();
          });
        }
      }
      options = Object.assign({}, options, { signal: timeoutCtrl.signal });
      return nsmFetch(url, options).finally(function () {
        clearTimeout(timer);
      });
    }
    return nsmFetch(url, options);
  }

  function ipaFetchAbortMessage(err) {
    if (err && err.name === "AbortError") {
      return ipaT("Analysis timed out.");
    }
    if (err && err.message) {
      return String(err.message);
    }
    return ipaT("Analysis could not be loaded.");
  }

  function mergeBranchHeaders(headers) {
    if (window.NSM_BRANCH_API && window.NSM_BRANCH_API.mergeBranchHeaders) {
      return window.NSM_BRANCH_API.mergeBranchHeaders(headers || {});
    }
    return headers || {};
  }

  function normalizeObjects(objects) {
    var out = [];
    var seen = {};
    (objects || []).forEach(function (obj) {
      if (!obj) {
        return;
      }
      var ct = obj.ct != null ? String(obj.ct) : "";
      var pk = obj.pk != null ? String(obj.pk) : "";
      if (!ct || !pk) {
        return;
      }
      var key = ct + ":" + pk;
      if (seen[key]) {
        return;
      }
      seen[key] = true;
      out.push({
        ct: ct,
        pk: pk,
        name: obj.name != null ? String(obj.name) : "",
      });
    });
    return out;
  }

  function collectRawObjects(objects) {
    var out = [];
    (objects || []).forEach(function (obj) {
      if (!obj) {
        return;
      }
      var ct = obj.ct != null ? String(obj.ct) : "";
      var pk = obj.pk != null ? String(obj.pk) : "";
      if (!ct || !pk) {
        return;
      }
      out.push({
        ct: ct,
        pk: pk,
        name: obj.name != null ? String(obj.name) : "",
      });
    });
    return out;
  }

  function objectsKey(objects) {
    return objects
      .map(function (obj) {
        return obj.ct + ":" + obj.pk;
      })
      .sort()
      .join("|");
  }

  function tabDedupKey(objects, context) {
    var base = objectsKey(objects);
    if (!context) {
      return base;
    }
    var ruleIndex = context.ruleIndex;
    var colPosition = context.colPosition;
    if (ruleIndex != null && ruleIndex !== "" && colPosition) {
      return base + "|" + ruleIndex + "/" + colPosition;
    }
    return base;
  }

  function rulesCellTabTitle(context) {
    if (!context) {
      return null;
    }
    var ruleIndex = context.ruleIndex;
    var colPosition = context.colPosition;
    if (ruleIndex == null || ruleIndex === "" || !colPosition) {
      return null;
    }
    return ipaTf("Rule %(index)s/%(col)s", {
      index: ruleIndex,
      col: colPosition,
    });
  }

  function rulesCellContextLabel(context) {
    if (!context) {
      return "";
    }
    var ruleIndex = context.ruleIndex;
    if (ruleIndex == null || ruleIndex === "") {
      return "";
    }
    var ruleName = context.ruleName || "";
    var colPart = context.colId || context.colPosition || "";
    if (ruleName) {
      return ipaTf("Rule %(name)s (%(index)s) / %(col)s", {
        name: ruleName,
        index: ruleIndex,
        col: colPart,
      });
    }
    return ipaTf("Rule %(index)s / %(col)s", {
      index: ruleIndex,
      col: colPart,
    });
  }

  function rulesCellTotalRules(context) {
    if (!context) {
      return null;
    }
    var unfiltered = context.rulesUnfilteredTotal;
    if (unfiltered != null && unfiltered !== "") {
      return unfiltered;
    }
    var total = context.rulesTotal;
    if (total != null && total !== "") {
      return total;
    }
    return null;
  }

  function rulesCellPositionTag(context) {
    if (!context) {
      return "";
    }
    var ruleIndex = context.ruleIndex;
    var total = rulesCellTotalRules(context);
    if (ruleIndex == null || ruleIndex === "" || total == null) {
      return "";
    }
    return ipaTf("Rule %(index)s/%(total)s", {
      index: ruleIndex,
      total: total,
    });
  }

  function rulesCellDiffSideLabel(context) {
    if (!context) {
      return "";
    }
    var ruleIndex = context.ruleIndex;
    if (ruleIndex == null || ruleIndex === "") {
      return "";
    }
    var ruleName = context.ruleName || "";
    var colPart = context.colId || context.colPosition || "";
    if (ruleName && colPart) {
      return ipaTf("Rule %(name)s (%(index)s) / %(col)s", {
        name: ruleName,
        index: ruleIndex,
        col: colPart,
      });
    }
    if (ruleName) {
      return ipaTf("Rule %(name)s (%(index)s)", {
        name: ruleName,
        index: ruleIndex,
      });
    }
    if (colPart) {
      return ipaTf("Rule %(index)s / %(col)s", {
        index: ruleIndex,
        col: colPart,
      });
    }
    return ipaTf("Rule %(index)s/%(col)s", {
      index: ruleIndex,
      col: colPosition,
    });
  }

  function diffSideLabel(tab) {
    if (!tab) {
      return "";
    }
    return (
      rulesCellTabTitle(tab.context) ||
      rulesCellDiffSideLabel(tab.context) ||
      tab.contextLabel ||
      tab.title ||
      ""
    );
  }

  function diffTabContextLabel(tabs) {
    if (!tabs || !tabs.length) {
      return "";
    }
    var firstLabel = rulesCellContextLabel(tabs[0].context);
    if (!firstLabel) {
      return "";
    }
    for (var i = 1; i < tabs.length; i++) {
      if (rulesCellContextLabel(tabs[i].context) !== firstLabel) {
        return "";
      }
    }
    return firstLabel;
  }

  function tabTitle(objects, customTitle, context) {
    if (customTitle) {
      return String(customTitle);
    }
    var rulesTitle = rulesCellTabTitle(context);
    if (rulesTitle) {
      return rulesTitle;
    }
    if (!objects.length) {
      return ipaT("IP Analysis");
    }
    if (objects.length === 1) {
      return objects[0].name || ipaT("IP Analysis");
    }
    return ipaTf("%(count)s objects", { count: objects.length });
  }

  function mergedTabTitle(objectCount) {
    return ipaTf("Merged (%(count)s objects)", { count: objectCount });
  }

  function diffRulesSideShortLabel(context) {
    if (!context) {
      return "";
    }
    var ruleIndex = context.ruleIndex;
    var colPosition = context.colPosition;
    if (ruleIndex == null || ruleIndex === "" || !colPosition) {
      return "";
    }
    return ruleIndex + "/" + colPosition;
  }

  function diffTabTitleFromTabs(tabs) {
    if (!tabs || !tabs.length) {
      return ipaT("Diff");
    }
    var ruleShorts = tabs.map(function (tab) {
      return diffRulesSideShortLabel(tab.context);
    });
    if (
      ruleShorts.length === tabs.length &&
      ruleShorts.every(function (label) {
        return !!label;
      })
    ) {
      if (tabs.length === 2) {
        return ipaTf("Diff %(a)s - %(b)s", {
          a: ruleShorts[0],
          b: ruleShorts[1],
        });
      }
      if (tabs.length <= 4) {
        return ipaTf("Diff %(labels)s", { labels: ruleShorts.join(" - ") });
      }
    }
    if (tabs.length === 2) {
      var a = truncateTitle(diffSideLabel(tabs[0]) || tabs[0].title || "A");
      var b = truncateTitle(diffSideLabel(tabs[1]) || tabs[1].title || "B");
      return ipaTf("Diff (%(a)s ↔ %(b)s)", { a: a, b: b });
    }
    if (tabs.length <= 4) {
      var labels = tabs.map(function (tab) {
        return truncateTitle(diffSideLabel(tab) || tab.title || "");
      });
      return ipaTf("Diff (%(labels)s)", { labels: labels.join(" ↔ ") });
    }
    return ipaTf("Diff (%(count)s tabs)", { count: tabs.length });
  }

  function diffObjectsKey(sides) {
    return (
      "diff:" +
      (sides || [])
        .map(function (side) {
          return objectsKey((side && side.objects) || []);
        })
        .join("|")
    );
  }

  function formatDiffSummary(summary) {
    if (!summary) {
      return "";
    }
    var fundPart =
      summary.fund > 0
        ? ipaTf(" | Name conflict: %(count)s", { count: summary.fund })
        : "";
    if (summary.side_count && summary.side_count > 2) {
      var parts = [];
      (summary.only_by_side || []).forEach(function (item) {
        if (item.count > 0) {
          parts.push(
            ipaTf("%(label)s: +%(count)s", {
              label: item.label || "?",
              count: item.count,
            })
          );
        }
      });
      if (summary.in_all > 0) {
        parts.push(ipaTf("in all: %(count)s", { count: summary.in_all }));
      }
      if (summary.in_some > 0) {
        parts.push(ipaTf("in some: %(count)s", { count: summary.in_some }));
      }
      return parts.join(" | ") + fundPart;
    }
    return (
      ipaTf(
        "%(label_a)s: +%(count_a)s | %(label_b)s: +%(count_b)s | shared: %(both)s",
        {
          label_a: summary.label_a || "A",
          count_a: summary.only_a || 0,
          label_b: summary.label_b || "B",
          count_b: summary.only_b || 0,
          both: summary.both || 0,
        }
      ) + fundPart
    );
  }

  function collectObjectsFromTabs(tabs) {
    var merged = [];
    (tabs || []).forEach(function (tab) {
      (tab.objects || []).forEach(function (obj) {
        merged.push(obj);
      });
    });
    return normalizeObjects(merged);
  }

  function truncateTitle(title) {
    var text = title == null ? "" : String(title);
    if (text.length <= TAB_TITLE_MAX) {
      return text;
    }
    return text.slice(0, TAB_TITLE_MAX - 1) + "…";
  }

  function buildQuery(objects, rawObjects) {
    var params = new URLSearchParams();
    var list =
      rawObjects && rawObjects.length ? rawObjects : objects || [];
    list.forEach(function (obj) {
      params.append("ct", obj.ct);
      params.append("pk", obj.pk);
    });
    return params.toString();
  }

  function buildDiffQuery(sides) {
    var params = new URLSearchParams();
    params.append("mode", "diff");
    (sides || []).forEach(function (side, index) {
      var prefix = "s" + index + "_";
      (side.objects || []).forEach(function (obj) {
        params.append(prefix + "ct", obj.ct);
        params.append(prefix + "pk", obj.pk);
      });
      var label = (side && (side.diffLabel || side.title)) || "";
      if (label) {
        params.append(prefix + "name", label);
      }
    });
    return params.toString();
  }

  function appendExportContextParams(params, tab) {
    if (!tab) {
      return;
    }
    if (tab.title) {
      params.append("export_title", tab.title);
    }
    var ctx = tab.context;
    if (!ctx) {
      return;
    }
    if (ctx.ruleIndex != null && ctx.ruleIndex !== "") {
      params.append("ctx_rule_index", String(ctx.ruleIndex));
    }
    if (ctx.ruleName) {
      params.append("ctx_rule_name", ctx.ruleName);
    }
    if (ctx.colId) {
      params.append("ctx_col_id", ctx.colId);
    }
    if (ctx.colPosition) {
      params.append("ctx_col_position", String(ctx.colPosition));
    }
    if (ctx.rulesTotal != null && ctx.rulesTotal !== "") {
      params.append("ctx_rules_total", String(ctx.rulesTotal));
    }
    if (ctx.rulesUnfilteredTotal != null && ctx.rulesUnfilteredTotal !== "") {
      params.append("ctx_rules_unfiltered_total", String(ctx.rulesUnfilteredTotal));
    }
  }

  function buildExportQuery(tab) {
    var params = new URLSearchParams();
    params.append("format", "yaml");
    if (tab.mode === "diff") {
      params.append("mode", "diff");
      (tab.sides || []).forEach(function (side, index) {
        var prefix = "s" + index + "_";
        (side.objects || []).forEach(function (obj) {
          params.append(prefix + "ct", obj.ct);
          params.append(prefix + "pk", obj.pk);
        });
        var label = (side && (side.diffLabel || side.title)) || "";
        if (label) {
          params.append(prefix + "name", label);
        }
      });
    } else {
      var list =
        tab.rawObjects && tab.rawObjects.length ? tab.rawObjects : tab.objects || [];
      list.forEach(function (obj) {
        params.append("ct", obj.ct);
        params.append("pk", obj.pk);
      });
    }
    appendExportContextParams(params, tab);
    return params.toString();
  }

  function parseContentDispositionFilename(header) {
    if (!header) {
      return "";
    }
    var match = /filename="([^"]+)"/i.exec(header);
    return match ? match[1] : "";
  }

  function triggerBlobDownload(blob, filename) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = filename || "ipa-export.yaml";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function defaultPosition(el) {
    var vw = window.innerWidth || 1200;
    var vh = window.innerHeight || 800;
    var rect = el.getBoundingClientRect();
    el.style.left = Math.max(12, vw - rect.width - 24) + "px";
    el.style.top = Math.max(12, Math.min(vh * 0.12, vh - rect.height - 24)) + "px";
  }

  function createLoupeButton(title, obj) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "nsm-ipa-loupe";
    btn.setAttribute("aria-label", title || ipaT("Analyze object"));
    btn.title = title || ipaT("Analyze object");
    btn.innerHTML = '<i class="mdi mdi-magnify" aria-hidden="true"></i>';
    if (obj && obj.ct != null && obj.pk != null) {
      btn.setAttribute("data-ct", String(obj.ct));
      btn.setAttribute("data-pk", String(obj.pk));
      btn.setAttribute("data-name", obj.name != null ? String(obj.name) : "");
    }
    return btn;
  }

  function loadingHtml() {
    return (
      '<div class="nsm-ipa-applet-loading">' +
      '<span class="mdi mdi-loading mdi-spin" aria-hidden="true"></span> ' +
      escHtml(ipaT("Analysis running…")) +
      "</div>"
    );
  }

  function errorHtml(message) {
    return (
      '<div class="nsm-ipa-applet-error">' +
      escHtml(message || ipaT("Analysis failed.")) +
      "</div>"
    );
  }

  function stripLegacyExpandedWarnings(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll(".nsm-ipa-expanded-warnings").forEach(function (el) {
      el.remove();
    });
  }


  window.NsmIpaUtil = {
    TAB_TITLE_MAX: TAB_TITLE_MAX,
    ipaT: ipaT,
    ipaTf: ipaTf,
    escHtml: escHtml,
    formatTypeCountSummary: formatTypeCountSummary,
    apiUrl: apiUrl,
    addObjectTypesApiUrl: addObjectTypesApiUrl,
    debounce: debounce,
    getCsrfToken: getCsrfToken,
    nsmFetch: nsmFetch,
    IPA_ANALYSIS_TIMEOUT_MS: IPA_ANALYSIS_TIMEOUT_MS,
    parseIpaApiErrorBody: parseIpaApiErrorBody,
    readIpaApiJson: readIpaApiJson,
    fetchIpaAnalysis: fetchIpaAnalysis,
    ipaFetchAbortMessage: ipaFetchAbortMessage,
    mergeBranchHeaders: mergeBranchHeaders,
    normalizeObjects: normalizeObjects,
    collectRawObjects: collectRawObjects,
    objectsKey: objectsKey,
    tabDedupKey: tabDedupKey,
    rulesCellTabTitle: rulesCellTabTitle,
    rulesCellContextLabel: rulesCellContextLabel,
    rulesCellTotalRules: rulesCellTotalRules,
    rulesCellPositionTag: rulesCellPositionTag,
    rulesCellDiffSideLabel: rulesCellDiffSideLabel,
    diffSideLabel: diffSideLabel,
    diffTabContextLabel: diffTabContextLabel,
    tabTitle: tabTitle,
    mergedTabTitle: mergedTabTitle,
    diffRulesSideShortLabel: diffRulesSideShortLabel,
    diffTabTitleFromTabs: diffTabTitleFromTabs,
    diffObjectsKey: diffObjectsKey,
    formatDiffSummary: formatDiffSummary,
    collectObjectsFromTabs: collectObjectsFromTabs,
    truncateTitle: truncateTitle,
    buildQuery: buildQuery,
    buildDiffQuery: buildDiffQuery,
    buildExportQuery: buildExportQuery,
    parseContentDispositionFilename: parseContentDispositionFilename,
    triggerBlobDownload: triggerBlobDownload,
    defaultPosition: defaultPosition,
    createLoupeButton: createLoupeButton,
    loadingHtml: loadingHtml,
    errorHtml: errorHtml,
    stripLegacyExpandedWarnings: stripLegacyExpandedWarnings,
  };
  window.nsmIpaStripLegacyExpandedWarnings = stripLegacyExpandedWarnings;
})();
