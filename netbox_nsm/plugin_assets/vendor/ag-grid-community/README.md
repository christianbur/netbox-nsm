# AG Grid Community (vendored)

Bundled for offline use on the Rulebook **Rules** tab. Version **33.2.4** (MIT).

Refresh from jsDelivr:

```bash
BASE="https://cdn.jsdelivr.net/npm/ag-grid-community@33.2.4"
curl -fsSL -o styles/ag-grid.min.css "$BASE/styles/ag-grid.min.css"
curl -fsSL -o styles/ag-theme-quartz.min.css "$BASE/styles/ag-theme-quartz.min.css"
curl -fsSL -o dist/ag-grid-community.min.js "$BASE/dist/ag-grid-community.min.js"
```

Served via `/plugins/netbox-nsm/assets/vendor/ag-grid-community/...` (no collectstatic).

**License:** MIT only — do not bundle `ag-grid-enterprise` (commercial). Row counts use a custom status bar; filtering uses Quick Filter, floating filters, and the Filters side panel.
