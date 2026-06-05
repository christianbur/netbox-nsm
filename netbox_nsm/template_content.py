from django.templatetags.static import static
from django.utils.html import format_html

from netbox.plugins import PluginTemplateExtension


def _build_ip_analysis_url(obj, ct, rulebook_groups):
    """Link to rulebook IP Analysis with this object pre-selected in column A."""
    from urllib.parse import quote

    from django.urls import reverse

    from netbox_nsm.models import Rulebook, RuleObjectItem, TypeConfig
    from netbox_nsm.models.type_config import MatchingClassChoices

    if not TypeConfig.objects.filter(
        content_type=ct,
        matching_class=MatchingClassChoices.ADDRESS,
    ).exists():
        return None

    rulebook = None
    if rulebook_groups:
        rulebook = rulebook_groups[0].get("rulebook")
    if rulebook is None:
        rb_pk = (
            RuleObjectItem.objects.filter(
                content_type=ct,
                object_id=obj.pk,
                rule__rulebook_id__isnull=False,
            )
            .values_list("rule__rulebook_id", flat=True)
            .order_by("rule__rulebook__name", "rule__rulebook_id")
            .first()
        )
        if rb_pk:
            rulebook = Rulebook.objects.filter(pk=rb_pk).first()
    if rulebook is None:
        rulebook = (
            Rulebook.objects.filter(
                fields__type_configs__type_config__content_type=ct,
            )
            .distinct()
            .order_by("name", "pk")
            .first()
        )
    if rulebook is None:
        rulebook = Rulebook.objects.order_by("pk").first()
    if rulebook is None:
        return None

    obj_name = str(obj)
    return (
        reverse("plugins:netbox_nsm:rulebook_ipanalysis", kwargs={"pk": rulebook.pk})
        + f"?ip_ct={ct.pk}&ip_pk={obj.pk}&ip_name={quote(obj_name)}"
    )


class NsmStylesExtension(PluginTemplateExtension):
    """Pill styles for rulebook/rule tables (also after HTMX table refresh)."""

    def head(self):
        return format_html(
            '<link rel="stylesheet" href="{}" />',
            static("netbox_nsm/css/rule-pills.css"),
        )


class NsmSecurityLinksExtension(PluginTemplateExtension):
    """
    Renders a "Security" panel on every object detail page.
    Shows security policy rules that reference this object, grouped by area.
    """

    models = None  # Apply to ALL NetBox models

    def right_page(self):
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Count
        from django.urls import reverse
        from netbox_nsm.models import RuleObjectItem, ObjectLink
        from netbox_nsm.object_rules_utils import build_object_field_rules_filter_url

        obj = self.context.get("object")
        if not obj or not hasattr(obj, "pk"):
            return ""

        ct = ContentType.objects.get_for_model(obj)

        from netbox_nsm.display_utils import (
            get_display_template_map,
            render_object_display,
            type_config_display_name_for_ct_id,
        )

        tmpl_map = get_display_template_map()
        type_label_cache: dict[int, str] = {}

        def _link_type_label(content_type) -> str:
            ct_id = content_type.pk
            if ct_id not in type_label_cache:
                type_label_cache[ct_id] = type_config_display_name_for_ct_id(ct_id)
            return type_label_cache[ct_id]

        # ── ObjectLinks grouped by linked-object type ──────────────────
        from django.db.models import prefetch_related_objects as _prefetch

        fwd_links = list(
            ObjectLink.objects.filter(object_a_type=ct, object_a_id=obj.pk)
            .select_related("object_b_type")
            .order_by("created")
        )
        _prefetch(
            fwd_links, "object_b"
        )  # batch-resolve Generic FK, 1 SQL per content-type
        rev_links = list(
            ObjectLink.objects.filter(object_b_type=ct, object_b_id=obj.pk)
            .select_related("object_a_type")
            .order_by("created")
        )
        _prefetch(rev_links, "object_a")

        # key: "{app_label}__{model}" (safe for HTML IDs)
        # value: {"label": verbose_name, "objects": [...]}
        links_by_type: dict = {}
        _return_url = (
            self.context.get("request").path if self.context.get("request") else "/"
        )
        for link in fwd_links:
            linked = link.object_b
            if linked is None:
                continue
            lct = link.object_b_type
            type_key = f"{lct.app_label}__{lct.model}"
            if type_key not in links_by_type:
                links_by_type[type_key] = {
                    "label": _link_type_label(lct),
                    "objects": [],
                }
            links_by_type[type_key]["objects"].append(
                {
                    "url": (
                        linked.get_absolute_url()
                        if hasattr(linked, "get_absolute_url")
                        else "#"
                    ),
                    "name": render_object_display(linked, lct.pk, tmpl_map),
                    "comment": link.comment,
                    "delete_url": reverse(
                        "plugins:netbox_nsm:object_link_delete",
                        kwargs={"pk": link.pk},
                    )
                    + f"?return_url={_return_url}",
                    "edit_url": reverse(
                        "plugins:netbox_nsm:object_link_edit",
                        kwargs={"pk": link.pk},
                    )
                    + f"?return_url={_return_url}",
                }
            )
        for link in rev_links:
            linked = link.object_a
            if linked is None:
                continue
            lct = link.object_a_type
            type_key = f"{lct.app_label}__{lct.model}"
            if type_key not in links_by_type:
                links_by_type[type_key] = {
                    "label": _link_type_label(lct),
                    "objects": [],
                }
            links_by_type[type_key]["objects"].append(
                {
                    "url": (
                        linked.get_absolute_url()
                        if hasattr(linked, "get_absolute_url")
                        else "#"
                    ),
                    "name": render_object_display(linked, lct.pk, tmpl_map),
                    "comment": link.comment,
                    "delete_url": reverse(
                        "plugins:netbox_nsm:object_link_delete",
                        kwargs={"pk": link.pk},
                    )
                    + f"?return_url={_return_url}",
                    "edit_url": reverse(
                        "plugins:netbox_nsm:object_link_edit",
                        kwargs={"pk": link.pk},
                    )
                    + f"?return_url={_return_url}",
                }
            )

        # ── NSM address objects that reference this IPAM object via FK ────
        # nsm_addresses has ip_address / prefix / range FK fields pointing to
        # IPAM objects.  Show them in the panel even without an ObjectLink.
        try:
            from ipam.models import (
                Prefix as _Prefix,
                IPAddress as _IPAddress,
                IPRange as _IPRange,
            )
            from netbox_custom_objects.models import CustomObjectType as _COT

            _addr_cot = _COT.objects.filter(slug="nsm_addresses").first()
            if _addr_cot:
                _AddrModel = _addr_cot.get_model()
                _addr_ct = ContentType.objects.get_for_model(_AddrModel)
                _addr_type_key = f"{_addr_ct.app_label}__{_addr_ct.model}"
                _fk_filter = None
                if isinstance(obj, _IPAddress):
                    _fk_filter = {"ip_address_id": obj.pk}
                elif isinstance(obj, _Prefix):
                    _fk_filter = {"prefix_id": obj.pk}
                elif isinstance(obj, _IPRange):
                    _fk_filter = {"range_id": obj.pk}
                if _fk_filter:
                    for _addr_obj in _AddrModel.objects.filter(**_fk_filter):
                        if _addr_type_key not in links_by_type:
                            links_by_type[_addr_type_key] = {
                                "label": _link_type_label(_addr_ct),
                                "objects": [],
                            }
                        links_by_type[_addr_type_key]["objects"].append(
                            {
                                "url": (
                                    _addr_obj.get_absolute_url()
                                    if hasattr(_addr_obj, "get_absolute_url")
                                    else "#"
                                ),
                                "name": render_object_display(
                                    _addr_obj, _addr_ct.pk, tmpl_map
                                ),
                                "comment": "",
                            }
                        )
        except Exception:
            pass

        # ── group M2M: parent groups + members (both directions) ─────────
        try:
            from django.utils.translation import gettext as _gettext

            from netbox_nsm.group_m2m import iter_group_m2m_relations

            _grp_type_key = f"{ct.app_label}__{ct.model}"
            _group_existing_urls = {
                o["url"] for g in links_by_type.values() for o in g["objects"]
            }

            def _add_group_m2m_link(related, comment):
                _url = (
                    related.get_absolute_url()
                    if hasattr(related, "get_absolute_url")
                    else "#"
                )
                if _url in _group_existing_urls:
                    return
                if _grp_type_key not in links_by_type:
                    links_by_type[_grp_type_key] = {
                        "label": _link_type_label(ct),
                        "objects": [],
                    }
                links_by_type[_grp_type_key]["objects"].append(
                    {
                        "url": _url,
                        "name": render_object_display(related, ct.pk, tmpl_map),
                        "comment": comment,
                    }
                )
                _group_existing_urls.add(_url)

            for _related, _label in iter_group_m2m_relations(obj):
                _add_group_m2m_link(_related, str(_gettext(_label)))
        except Exception:
            pass

        link_type_groups = [
            {
                "type_key": k,
                "type_label": v["label"],
                "count": len(v["objects"]),
                "objects": v["objects"],
            }
            for k, v in sorted(links_by_type.items(), key=lambda x: x[1]["label"])
        ]
        total_links = sum(g["count"] for g in link_type_groups)

        # ── Inherited links – lazy-loaded via API on user request ─────────
        # Computed in InheritedLinksApiView to keep page-load fast.
        nsm_inherited_api_url = None
        try:
            from ipam.models import (
                Prefix as _PfxCheck,
                IPAddress as _IPCheck,
                IPRange as _IRCheck,
            )

            if isinstance(obj, (_IPCheck, _IRCheck, _PfxCheck)):
                nsm_inherited_api_url = (
                    reverse("plugins:netbox_nsm:inherited_links_api")
                    + f"?ct_id={ct.pk}&obj_id={obj.pk}"
                )
        except Exception:
            pass

        # ── Security rules that reference this object ─────────────────────
        FIRST_PAGE = 30
        qs = (
            RuleObjectItem.objects.filter(
                content_type=ct, object_id=obj.pk
            )
            .select_related("rule", "rule__rulebook", "field")
            .prefetch_related("field__type_configs__type_config__content_type")
            .order_by("rule__rulebook__name", "rule__index", "field__sort_order")
        )
        total_items = qs.count()
        unique_rules_total = qs.values("rule_id").distinct().count()

        # Pre-query unique rule counts per rulebook
        # .order_by() clears inherited ordering to avoid extra GROUP BY cols
        rb_unique_counts = {
            row["rule__rulebook_id"]: row["ucount"]
            for row in qs.order_by()
            .values("rule__rulebook_id")
            .annotate(ucount=Count("rule_id", distinct=True))
        }

        # Build first-page rulebook groups, sub-grouped by field (source/dest/…)
        seen_items = set()  # (field_id, rule_id) – for item-level dedup / offset calc
        by_rulebook = {}
        rb_order = []
        for item in qs[:FIRST_PAGE]:
            key = (item.field_id, item.rule_id)
            if key in seen_items:
                continue
            seen_items.add(key)
            rb = item.rule.rulebook
            rb_pk = rb.pk if rb else 0
            if rb_pk not in by_rulebook:
                by_rulebook[rb_pk] = {
                    "rulebook": rb,
                    "_fields": {},
                    "_field_order": [],
                    "unique_count": rb_unique_counts.get(rb_pk, 0),
                }
                rb_order.append(rb_pk)
            rb_data = by_rulebook[rb_pk]
            f_id = item.field_id
            if f_id not in rb_data["_fields"]:
                rb_data["_fields"][f_id] = {
                    "field": item.field,
                    "rules": [],
                    "_seen": set(),
                }
                rb_data["_field_order"].append(f_id)
            if item.rule_id not in rb_data["_fields"][f_id]["_seen"]:
                rb_data["_fields"][f_id]["_seen"].add(item.rule_id)
                rb_data["_fields"][f_id]["rules"].append(item.rule)
        for rb_pk in rb_order:
            d = by_rulebook[rb_pk]
            d["field_groups"] = [
                {
                    "field": d["_fields"][fid]["field"],
                    "rules": d["_fields"][fid]["rules"],
                    "filter_url": build_object_field_rules_filter_url(
                        d["rulebook"],
                        d["_fields"][fid]["field"],
                        obj,
                        ct,
                        display_template_map=tmpl_map,
                    ),
                }
                for fid in d["_field_order"]
            ]
            del d["_fields"], d["_field_order"]
        rulebook_groups = [by_rulebook[pk] for pk in rb_order]

        request = self.context.get("request")
        return_url = request.path if request else "/"
        from urllib.parse import quote

        obj_name = str(obj)
        analyzer_url = (
            reverse("plugins:netbox_nsm:object_analyzer")
            + f"?ct={ct.pk}&pk={obj.pk}&name={quote(obj_name)}"
        )
        ip_analysis_url = _build_ip_analysis_url(obj, ct, rulebook_groups)
        assign_url = (
            reverse("plugins:netbox_nsm:object_link_assign")
            + f"?ct_id={ct.pk}&obj_id={obj.pk}&return_url={return_url}"
        )
        api_url = (
            reverse("plugins:netbox_nsm:object_rules_api")
            + f"?ct_id={ct.pk}&obj_id={obj.pk}"
        )

        security_badge = unique_rules_total + total_links or None

        # ── Enforced rulebooks (Device/VM/VDC only) ───────────────────────
        from netbox_nsm.models import RulebookAssignment

        enforcer_assignments = []
        enforcer_add_url = None
        try:
            from dcim.models import Device, VirtualDeviceContext
            from virtualization.models import VirtualMachine

            if isinstance(obj, (Device, VirtualMachine, VirtualDeviceContext)):
                enforcer_assignments = list(
                    RulebookAssignment.objects.filter(
                        assigned_object_type=ct,
                        assigned_object_id=obj.pk,
                    )
                    .select_related("rulebook")
                    .order_by("rulebook__name")
                )
                enforcer_add_url = (
                    reverse("plugins:netbox_nsm:rulebookassignment_add")
                    + f"?assigned_object_type_id={ct.pk}&assigned_object_id={obj.pk}&return_url={return_url}"
                )
        except Exception:
            pass

        return self.render(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_link_type_groups": link_type_groups,
                "nsm_inherited_api_url": nsm_inherited_api_url,
                "nsm_rulebook_groups": rulebook_groups,
                "nsm_unique_rules_total": unique_rules_total,
                "nsm_security_badge": security_badge,
                "nsm_next_offset": len(seen_items),
                "nsm_has_more": len(seen_items) < total_items,
                "nsm_api_url": api_url,
                "nsm_assign_url": assign_url,
                "nsm_analyzer_url": analyzer_url,
                "nsm_ip_analysis_url": ip_analysis_url,
                "nsm_enforcer_assignments": enforcer_assignments,
                "nsm_enforcer_add_url": enforcer_add_url,
            },
        )


template_extensions = [NsmStylesExtension, NsmSecurityLinksExtension]
