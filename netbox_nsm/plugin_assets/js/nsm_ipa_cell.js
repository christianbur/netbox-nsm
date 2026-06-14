/**
 * Rules-cell loupe: collect analyzable objects and bind click handlers.
 */
(function () {
  "use strict";

  function collectCellObjects(cell) {
    var objects = [];
    if (!cell) {
      return objects;
    }
    // Visible pills carry ct/pk; compact cells only expose hidden probe markers.
    // Never collect both — that duplicated every object and tripped false "doppelt".
    // Polymorphic merged cells (Address + Address Group, …) keep the complete flat
    // list in hidden probes; prefer those so every type-group segment is included.
    var visibleSelector =
      '.nsm-ag-cell-item[data-addr-analyzable="1"]:not(.nsm-ag-cell-item--probe)';
    var probeSelector = '.nsm-ag-cell-item--probe[data-addr-analyzable="1"]';
    var rows;
    if (cell.classList.contains("nsm-ag-cell-merged")) {
      rows = cell.querySelectorAll(probeSelector);
      if (!rows.length) {
        rows = cell.querySelectorAll(visibleSelector);
      }
    } else {
      rows = cell.querySelectorAll(visibleSelector);
      if (!rows.length) {
        rows = cell.querySelectorAll(probeSelector);
      }
    }
    rows.forEach(function (row) {
      objects.push({
        ct: row.getAttribute("data-ct"),
        pk: row.getAttribute("data-pk"),
        name: row.getAttribute("data-name") || "",
      });
    });
    return objects;
  }

  function loupeCellContainer(loupe) {
    return (
      loupe.closest(".nsm-ag-cell-list") ||
      loupe.closest(".nsm-ag-cell-merged")
    );
  }

  function readRulesPageTotals() {
    var rulesRoot = document.getElementById("rules");
    if (!rulesRoot) {
      return {};
    }
    return {
      rulesTotal: rulesRoot.getAttribute("data-rules-total-rules") || null,
      rulesUnfilteredTotal:
        rulesRoot.getAttribute("data-rules-unfiltered-total") || null,
    };
  }

  function enrichRulesCellContext(context) {
    if (!context) {
      return null;
    }
    return Object.assign({}, context, readRulesPageTotals());
  }

  function readRulesCellContext(el) {
    if (!el) {
      return null;
    }
    var ruleIndex = el.getAttribute("data-rule-index");
    if (ruleIndex == null || ruleIndex === "") {
      return null;
    }
    return enrichRulesCellContext({
      ruleIndex: ruleIndex,
      ruleName: el.getAttribute("data-rule-name") || "",
      colId: el.getAttribute("data-col-id") || "",
      colPosition: el.getAttribute("data-col-position") || "",
    });
  }

  function collectRulesCellContext(loupe) {
    var cell = loupeCellContainer(loupe);
    var context = readRulesCellContext(cell);
    if (context) {
      return context;
    }
    var td = loupe.closest("td.nsm-rules-td");
    context = readRulesCellContext(td);
    if (context) {
      return context;
    }
    var tr = loupe.closest("tr.nsm-rules-data-row");
    if (!tr) {
      return null;
    }
    var ruleIndex = tr.getAttribute("data-rule-index");
    if (ruleIndex == null || ruleIndex === "") {
      return null;
    }
    return enrichRulesCellContext({
      ruleIndex: ruleIndex,
      ruleName: tr.getAttribute("data-rule-name") || "",
      colId: td ? td.getAttribute("data-col-id") || "" : "",
      colPosition: td ? td.getAttribute("data-col-position") || "" : "",
    });
  }

  function bindGlobalHandlers(applet) {
    window.__nsmIpaApplet = applet;
    document.addEventListener("click", function (e) {
      var loupe = e.target.closest(".nsm-ipa-loupe");
      if (!loupe) {
        return;
      }
      e.preventDefault();
      e.stopPropagation();

      var cell = loupeCellContainer(loupe);
      var objects = [];
      if (loupe.classList.contains("nsm-ipa-cell-loupe") && cell) {
        objects = collectCellObjects(cell);
      } else if (loupe.hasAttribute("data-ct") && loupe.hasAttribute("data-pk")) {
        objects.push({
          ct: loupe.getAttribute("data-ct"),
          pk: loupe.getAttribute("data-pk"),
          name: loupe.getAttribute("data-name") || "",
        });
      } else if (cell) {
        objects = collectCellObjects(cell);
      }
      if (objects.length) {
        var context = null;
        if (loupe.classList.contains("nsm-ipa-cell-loupe")) {
          context = collectRulesCellContext(loupe);
        }
        window.__nsmIpaApplet.open({ objects: objects, context: context });
      }
    });
  }

  window.NsmIpaCell = {
    collectCellObjects: collectCellObjects,
    loupeCellContainer: loupeCellContainer,
    readRulesCellContext: readRulesCellContext,
    readRulesPageTotals: readRulesPageTotals,
    enrichRulesCellContext: enrichRulesCellContext,
    collectRulesCellContext: collectRulesCellContext,
    bindGlobalHandlers: bindGlobalHandlers,
  };
})();
