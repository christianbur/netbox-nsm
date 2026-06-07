from django.templatetags.static import static
from django.utils.html import format_html

from netbox.plugins import PluginTemplateExtension


def _build_ip_analysis_url(obj, ct, rulebook_groups):
    """Link to IP Analysis with this object pre-selected in column A."""
    from urllib.parse import quote

    from django.urls import reverse

    from netbox_nsm.models import TypeConfig
    from netbox_nsm.models.type_config import MatchingClassChoices

    if not TypeConfig.objects.filter(
        content_type=ct,
        matching_class=MatchingClassChoices.ADDRESS,
    ).exists():
        return None

    obj_name = str(obj)
    return (
        reverse("plugins:netbox_nsm:ip_analysis")
        + f"?ip_ct={ct.pk}&ip_pk={obj.pk}&ip_name={quote(obj_name)}"
    )


def _panel_link_payload(linked, lct, tmpl_map, **extra):
    from netbox_nsm.display_utils import render_object_display
    from netbox_nsm.views.rulebook import (
        _object_is_addr_analyzable,
        _object_supports_addr_analysis,
    )

    payload = {
        "url": (
            linked.get_absolute_url() if hasattr(linked, "get_absolute_url") else "#"
        ),
        "name": render_object_display(linked, lct.pk, tmpl_map),
        "ct_id": lct.pk,
        "obj_id": linked.pk,
        "addr_analyzable": _object_is_addr_analyzable(linked, lct.pk),
        "supports_addr_analysis": _object_supports_addr_analysis(linked),
    }
    payload.update(extra)
    return payload


def _row_has_link_actions(obj: dict) -> bool:
    """True when a Security Panel link row should show action icons."""
    if obj.get("supports_addr_analysis") or obj.get("addr_analyzable"):
        return True
    if obj.get("edit_url") or obj.get("delete_url"):
        return True
    return False


def _finalize_link_type_group(group: dict) -> dict:
    """Derive Security Panel table column flags from row payloads."""
    objects = group.get("objects") or []
    show_comment = any(o.get("comment") for o in objects)
    show_actions = any(_row_has_link_actions(obj) for obj in objects)
    finalized = dict(group)
    finalized["show_comment"] = show_comment
    finalized["show_actions"] = show_actions
    return finalized


def _finalize_link_type_groups(groups: list) -> list:
    return [_finalize_link_type_group(g) for g in groups]


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
        from netbox_nsm.panel_link_actions import (
            address_ipam_fk_action_urls,
            address_ipam_fk_ref_action_urls,
            group_m2m_action_urls,
            object_link_action_urls,
        )
        from netbox_nsm.object_rules_utils import build_rule_name_column_filter_url
        from netbox_nsm.branch_urls import with_branch_query

        request = self.context.get("request")

        def _panel_url(url: str) -> str:
            if not url:
                return ""
            return with_branch_query(url, request) if request else url

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
                _panel_link_payload(
                    linked,
                    lct,
                    tmpl_map,
                    comment=link.comment,
                    **object_link_action_urls(link, _return_url),
                )
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
                _panel_link_payload(
                    linked,
                    lct,
                    tmpl_map,
                    comment=link.comment,
                    **object_link_action_urls(link, _return_url),
                )
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

            from netbox_nsm.address_ipam_fk import fk_field_name_from_filter

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
                _fk_field_name = fk_field_name_from_filter(_fk_filter)
                if _fk_filter and _fk_field_name:
                    _fk_existing_urls = {
                        o["url"] for g in links_by_type.values() for o in g["objects"]
                    }
                    for _addr_obj in _AddrModel.objects.filter(**_fk_filter):
                        _addr_url = (
                            _addr_obj.get_absolute_url()
                            if hasattr(_addr_obj, "get_absolute_url")
                            else "#"
                        )
                        if _addr_url in _fk_existing_urls:
                            continue
                        if _addr_type_key not in links_by_type:
                            links_by_type[_addr_type_key] = {
                                "label": _link_type_label(_addr_ct),
                                "objects": [],
                            }
                        links_by_type[_addr_type_key]["objects"].append(
                            _panel_link_payload(
                                _addr_obj,
                                _addr_ct,
                                tmpl_map,
                                comment="",
                                **address_ipam_fk_ref_action_urls(
                                    obj,
                                    _addr_obj,
                                    _fk_field_name,
                                    _return_url,
                                ),
                            )
                        )
                        _fk_existing_urls.add(_addr_url)
        except Exception:
            pass

        # ── nsm_addresses → IPAM FK (prefix / IP / range) ───────────────
        try:
            from netbox_nsm.address_ipam_fk import (
                is_nsm_address_object,
                iter_address_ipam_fk_refs,
            )

            if is_nsm_address_object(obj):
                _ipam_existing_urls = {
                    o["url"] for g in links_by_type.values() for o in g["objects"]
                }
                for _ref in iter_address_ipam_fk_refs(obj):
                    _ipam_obj = _ref.ipam_obj
                    _ipam_ct = _ref.ipam_ct
                    _ipam_url = (
                        _ipam_obj.get_absolute_url()
                        if hasattr(_ipam_obj, "get_absolute_url")
                        else "#"
                    )
                    if _ipam_url in _ipam_existing_urls:
                        continue
                    _ipam_type_key = f"{_ipam_ct.app_label}__{_ipam_ct.model}"
                    if _ipam_type_key not in links_by_type:
                        links_by_type[_ipam_type_key] = {
                            "label": _link_type_label(_ipam_ct),
                            "objects": [],
                        }
                    links_by_type[_ipam_type_key]["objects"].append(
                        _panel_link_payload(
                            _ipam_obj,
                            _ipam_ct,
                            tmpl_map,
                            comment="",
                            **address_ipam_fk_action_urls(
                                obj,
                                _ref.field_name,
                                _ipam_obj,
                                _return_url,
                            ),
                        )
                    )
                    _ipam_existing_urls.add(_ipam_url)
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

            def _add_group_m2m_link(related, comment, **action_urls):
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
                    _panel_link_payload(
                        related,
                        ct,
                        tmpl_map,
                        comment=comment,
                        **action_urls,
                    )
                )
                _group_existing_urls.add(_url)

            for _relation in iter_group_m2m_relations(obj):
                _add_group_m2m_link(
                    _relation.related,
                    str(_gettext(_relation.label)),
                    **group_m2m_action_urls(_relation, _return_url, page_obj=obj),
                )
        except Exception:
            pass

        link_type_groups = _finalize_link_type_groups(
            [
                {
                    "type_key": k,
                    "type_label": v["label"],
                    "count": len(v["objects"]),
                    "objects": v["objects"],
                }
                for k, v in sorted(links_by_type.items(), key=lambda x: x[1]["label"])
            ]
        )
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
            RuleObjectItem.objects.filter(content_type=ct, object_id=obj.pk)
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
        field_rule_counts = {
            (row["rule__rulebook_id"], row["field_id"]): row["ucount"]
            for row in qs.order_by()
            .values("rule__rulebook_id", "field_id")
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
                    "rule_count": field_rule_counts.get((rb_pk, fid), 0),
                }
                for fid in d["_field_order"]
            ]
            rb = d["rulebook"]
            d["rules_tab_url"] = _panel_url(rb.get_rules_tab_url()) if rb else ""
            for fg in d["field_groups"]:
                for rule in fg["rules"]:
                    rule.nsm_panel_filter_url = _panel_url(
                        build_rule_name_column_filter_url(rb, rule)
                    )
            del d["_fields"], d["_field_order"]
        rulebook_groups = [by_rulebook[pk] for pk in rb_order]

        return_url = request.path if request else "/"
        from urllib.parse import quote

        from netbox_nsm.plugin_labels import get_nsm_panel_label
        from netbox_nsm.views.rulebook import _object_supports_addr_analysis

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
                "nsm_panel_label": get_nsm_panel_label(),
                "nsm_page_addr_analyzable": _object_supports_addr_analysis(obj),
                "nsm_page_object_ct": ct.pk,
                "nsm_page_object_pk": obj.pk,
                "nsm_page_object_name": obj_name,
                "nsm_enforcer_assignments": enforcer_assignments,
                "nsm_enforcer_add_url": enforcer_add_url,
            },
        )


template_extensions = [NsmStylesExtension, NsmSecurityLinksExtension]
