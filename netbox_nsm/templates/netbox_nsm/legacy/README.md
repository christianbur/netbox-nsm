# Legacy NSM Rulebook UI (archiviert)

Diese Dateien gehören zu den **ersetzten** Rulebook-Tabs und werden nicht mehr geroutet.

| Datei | Alter Tab | Ersatz |
|-------|-----------|--------|
| `rulebook_matrix.html` | `/rulebooks/<pk>/zonematrix/` (Zone Matrix) | `/matrix/` — AG Grid |
| `rulebook_policy_classic.html` | `/rulebooks/<pk>/policy/` (klassische Policy-Tabelle) | `/rules/` — AG Grid |

Die View-Klassen liegen in `netbox_nsm/views/rulebook_legacy.py` (ohne `@register_model_view`).

Alte URLs leiten per Redirect auf die neuen Tabs um (`urls.py`).
