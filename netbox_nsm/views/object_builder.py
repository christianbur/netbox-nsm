import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django_tables2 import RequestConfig

from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.models import SecurityArea, SecurityObject, SecurityObjectType
from netbox_nsm.tables import SecurityAreaTable, SecurityObjectTypeTable

__all__ = ("ObjectBuilderView",)

_TABS = [
    {"slug": "types",   "label": "Types"},
    {"slug": "areas",   "label": "Areas"},
    {"slug": "import", "label": "Import"},
]


def _sensible_demo_objects(type_name, field_definitions, existing_objects):
    """Return a small, meaningful demo set for a type.

    Keep demo data compact and realistic instead of generating large synthetic batches.
    """
    name_l = (type_name or "").strip().lower()
    demos = list(existing_objects or [])

    has_linked = any(
        str((f or {}).get("type", "")) in ("object_ref", "table", "json")
        for f in field_definitions if isinstance(f, dict)
    )
    if has_linked:
        return demos

    if name_l == "action":
        return demos

    if name_l in ("services", "service"):
        wanted = [
            ("NTP", {"protocol": "udp", "destination_ports": "123"}),
            ("SMTP", {"protocol": "tcp", "destination_ports": "25"}),
            ("LDAPS", {"protocol": "tcp", "destination_ports": "636"}),
        ]
        existing_names = {str(o.get("name", "")) for o in demos if isinstance(o, dict)}
        for obj_name, field_data in wanted:
            if obj_name not in existing_names:
                demos.append({"name": obj_name, "field_data": field_data})
        return demos

    if name_l in ("applications", "application"):
        demos.extend([
            {"name": "Web-Browsing", "field_data": {"app_id": "web-browsing", "protocol": "tcp", "risk": "low"}},
            {"name": "Git", "field_data": {"app_id": "git", "protocol": "tcp", "risk": "medium"}},
            {"name": "RDP", "field_data": {"app_id": "rdp", "protocol": "tcp", "risk": "high"}},
        ])
        return demos

    if name_l == "zones":
        demos.extend([
            {"name": "LAN", "field_data": {"color": "green", "description": "Internal trusted network"}},
            {"name": "DMZ", "field_data": {"color": "orange", "description": "Public-facing services"}},
            {"name": "WAN", "field_data": {"color": "red", "description": "Internet / untrusted"}},
        ])
        return demos

    if name_l == "labels":
        demos.extend([
            {"name": "prod", "field_data": {"label_type": "Environment", "color": "red"}},
            {"name": "office", "field_data": {"label_type": "Location", "color": "blue"}},
            {"name": "web", "field_data": {"label_type": "Application", "color": "purple"}},
        ])
        return demos

    if name_l == "users":
        demos.extend([
            {"name": "LDAP-Admins", "field_data": {"user_type": "ldap", "dn": "cn=admins,ou=groups,dc=example,dc=org"}},
            {"name": "SAML-Employees", "field_data": {"user_type": "saml", "dn": "employees@example.org"}},
            {"name": "Local-Backup", "field_data": {"user_type": "local", "dn": "backup"}},
        ])
        return demos

    if name_l == "sgts":
        demos.extend([
            {"name": "SGT-10", "field_data": {"tag_id": 10, "color": "green"}},
            {"name": "SGT-20", "field_data": {"tag_id": 20, "color": "orange"}},
            {"name": "SGT-30", "field_data": {"tag_id": 30, "color": "red"}},
        ])
        return demos

    # Generic fallback: a few compact examples derived from field definitions.
    fallback_names = ["Example-A", "Example-B", "Example-C"]
    for idx, obj_name in enumerate(fallback_names, start=1):
        field_data = {}
        for field_def in field_definitions:
            if not isinstance(field_def, dict) or field_def.get("__meta__"):
                continue
            fname = field_def.get("name")
            ftype = str(field_def.get("type", "text"))
            if not fname:
                continue
            if ftype == "choice":
                choices = field_def.get("choices") or []
                field_data[fname] = choices[(idx - 1) % len(choices)] if choices else ""
            elif ftype in ("number", "integer"):
                field_data[fname] = idx
            elif ftype == "boolean":
                field_data[fname] = idx % 2 == 0
            elif ftype == "date":
                field_data[fname] = f"2026-0{idx}-01"
            elif ftype == "markdown":
                field_data[fname] = f"Demo note {idx}"
            else:
                field_data[fname] = f"demo-{fname}-{idx}"
        demos.append({"name": obj_name, "field_data": field_data})
    return demos


def _build_tabs(active_slug):
    tabs = []
    for t in _TABS:
        tabs.append({
            **t,
            "href": reverse("plugins:netbox_nsm:object_builder", args=[t["slug"]]),
            "active": t["slug"] == active_slug,
        })
    return tabs


class ObjectBuilderView(LoginRequiredMixin, View):
    """Combined Object-Builder page: Areas / Types / Built-in tabs."""

    def get(self, request, tab="types"):
        if tab == "builtin":
            return redirect(reverse("plugins:netbox_nsm:object_builder", args=["import"]))
        if tab not in {t["slug"] for t in _TABS}:
            return redirect(reverse("plugins:netbox_nsm:object_builder", args=["types"]))

        context = {
            "active_tab": tab,
            "tabs": _build_tabs(tab),
        }

        if tab == "types":
            qs = SecurityObjectType.objects.select_related("area").order_by("area__sort_order", "area__slug", "name")
            table = SecurityObjectTypeTable(qs)
            RequestConfig(request, paginate={"per_page": 50}).configure(table)
            context["table"] = table
            context["add_url"] = reverse("plugins:netbox_nsm:securityobjecttype_add")

        elif tab == "areas":
            system_qs = SecurityArea.objects.filter(is_system=True).order_by("sort_order", "slug")
            custom_qs = SecurityArea.objects.filter(is_system=False).order_by("sort_order", "slug")

            system_table = SecurityAreaTable(system_qs)
            custom_table = SecurityAreaTable(custom_qs)
            RequestConfig(request, paginate={"per_page": 50}).configure(system_table)
            RequestConfig(request, paginate={"per_page": 50}).configure(custom_table)

            context["system_table"] = system_table
            context["custom_table"] = custom_table
            context["add_url"] = reverse("plugins:netbox_nsm:securityarea_add")

        elif tab == "import":
            full_definitions = []
            for t in BUILTIN_CUSTOM_TYPES:
                full_definition = {
                    "name": t.get("name", ""),
                    # Keep stable slugs in JSON so imports are independent from translated/renamed area labels.
                    "area": t.get("area", ""),
                    "description": t.get("description", ""),
                    "display_template": t.get("display_template", ""),
                    "field_definitions": t.get("field_definitions", []),
                    "default_objects": t.get("default_objects", []),
                }
                full_definitions.append(full_definition)
            context["builtin_types_data"] = full_definitions
            context["builtin_types_json"] = json.dumps(full_definitions, ensure_ascii=False, indent=2)

            demo_definitions = []
            for typedef in full_definitions:
                field_defs = typedef.get("field_definitions", [])
                demo_objs = _sensible_demo_objects(
                    typedef.get("name", ""),
                    field_defs,
                    list(typedef.get("default_objects", [])),
                )
                demo_definitions.append({**typedef, "default_objects": demo_objs})
            context["builtin_types_demo_data"] = demo_definitions
            context["builtin_types_demo_json"] = json.dumps(demo_definitions, ensure_ascii=False, indent=2)

        return render(request, "netbox_nsm/object_builder.html", context)

    def post(self, request, tab="import"):
        if not request.user.has_perm("netbox_nsm.add_securityobjecttype"):
            messages.error(request, "Permission denied.")
            return redirect(reverse("plugins:netbox_nsm:object_builder", args=["import"]))

        bulk_raw = request.POST.get("builtin_types_json", "").strip()
        if not bulk_raw:
            messages.warning(request, "Keine Built-in Definition angegeben.")
            return redirect(reverse("plugins:netbox_nsm:object_builder", args=["import"]))

        try:
            definitions = json.loads(bulk_raw)
        except json.JSONDecodeError:
            messages.error(request, "Ungültiges JSON in der Built-in Definition.")
            return redirect(reverse("plugins:netbox_nsm:object_builder", args=["import"]))

        if not isinstance(definitions, list):
            messages.error(request, "Die Built-in Definition muss eine JSON-Liste sein.")
            return redirect(reverse("plugins:netbox_nsm:object_builder", args=["import"]))

        import_mode = request.POST.get("import_mode", "normal")
        create_demo_data = import_mode == "demo"

        created = 0
        created_demo = 0
        skipped_demo_linked = []

        def _demo_value(field_def, n):
            ftype = str(field_def.get("type", "text"))
            fname = str(field_def.get("name", "field"))

            if ftype in ("object_ref", "table", "json"):
                return None
            if ftype in ("number", "integer"):
                return n
            if ftype == "boolean":
                return (n % 2) == 0
            if ftype == "choice":
                choices = field_def.get("choices") or []
                if isinstance(choices, list) and choices:
                    return choices[(n - 1) % len(choices)]
                return ""
            if ftype == "date":
                day = ((n - 1) % 28) + 1
                return f"2026-01-{day:02d}"
            if ftype == "markdown":
                return f"Demo note for {fname} #{n}"
            return f"demo-{fname}-{n:03d}"

        for idx, definition in enumerate(definitions, start=1):
            if not isinstance(definition, dict):
                messages.warning(request, f"Eintrag #{idx} ist kein JSON-Objekt — übersprungen.")
                continue

            custom_name = str(definition.get("name", "")).strip()
            custom_area_value = str(definition.get("area", "")).strip()
            custom_template = str(definition.get("display_template", "")).strip()
            custom_description = str(definition.get("description", "")).strip()
            field_definitions = definition.get("field_definitions", [])
            default_objects = definition.get("default_objects", [])

            if not custom_name:
                messages.warning(request, f"Eintrag #{idx}: 'name' fehlt — übersprungen.")
                continue
            if SecurityObjectType.objects.filter(name=custom_name).exists():
                messages.warning(request, f"'{custom_name}' existiert bereits — übersprungen.")
                continue

            if not custom_area_value:
                messages.warning(request, f"'{custom_name}': 'area' fehlt — übersprungen.")
                continue

            if not isinstance(field_definitions, list):
                messages.warning(request, f"'{custom_name}': 'field_definitions' muss eine Liste sein — übersprungen.")
                continue

            if not isinstance(default_objects, list):
                messages.warning(request, f"'{custom_name}': 'default_objects' muss eine Liste sein — übersprungen.")
                continue

            area_obj = SecurityArea.objects.filter(slug=custom_area_value).first()
            if not area_obj:
                area_obj = SecurityArea.objects.filter(name__iexact=custom_area_value).first()
            if not area_obj:
                messages.warning(request, f"Area '{custom_area_value}' nicht gefunden — '{custom_name}' übersprungen.")
                continue

            obj_type = SecurityObjectType.objects.create(
                name=custom_name,
                area=area_obj,
                description=custom_description,
                field_definitions=field_definitions,
                display_template=custom_template,
            )

            for default_obj in default_objects:
                if not isinstance(default_obj, dict) or not default_obj.get("name"):
                    continue
                SecurityObject.objects.get_or_create(
                    name=default_obj["name"],
                    custom_type=obj_type,
                    defaults={"field_data": default_obj.get("field_data", {})},
                )

            if create_demo_data:
                has_linked_fields = any(
                    str((f or {}).get("type", "")) in ("object_ref", "table", "json")
                    for f in field_definitions if isinstance(f, dict)
                )

                if has_linked_fields:
                    skipped_demo_linked.append(custom_name)
                else:
                    for n in range(1, 31):
                        demo_name = f"Demo {custom_name} {n:03d}"
                        if SecurityObject.objects.filter(custom_type=obj_type, name=demo_name).exists():
                            continue

                        demo_field_data = {}
                        for field_def in field_definitions:
                            if not isinstance(field_def, dict):
                                continue
                            if field_def.get("__meta__"):
                                continue

                            field_name = field_def.get("name")
                            if not field_name:
                                continue

                            value = _demo_value(field_def, n)
                            if value is None:
                                continue
                            demo_field_data[field_name] = value

                        SecurityObject.objects.create(
                            name=demo_name,
                            custom_type=obj_type,
                            field_data=demo_field_data,
                        )
                        created_demo += 1
            created += 1

        if created:
            messages.success(request, f"{created} Typ(en) installiert.")
        if create_demo_data and created_demo:
            messages.success(request, f"{created_demo} Demo-Objekt(e) erstellt.")
        if create_demo_data and skipped_demo_linked:
            names = ", ".join(sorted(skipped_demo_linked))
            messages.warning(request, f"Demo-Daten für verknüpfte Typen übersprungen: {names}")
        return redirect(reverse("plugins:netbox_nsm:object_builder", args=["import"]))
