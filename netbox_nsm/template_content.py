from django.templatetags.static import static
from django.utils.html import format_html

from netbox.plugins import PluginTemplateExtension


def _build_ip_analysis_url(obj, ct, rulebook_groups):
    """Link to IP Analysis with this object pre-selected in column A."""
    from urllib.parse import quote

    from django.urls import reverse

    from netbox_nsm.core.type_kind import is_address_content_model

    if not is_address_content_model(ct.model):
        return None

    obj_name = str(obj)
    return (
        reverse("plugins:netbox_nsm:ip_analysis")
        + f"?ip_ct={ct.pk}&ip_pk={obj.pk}&ip_name={quote(obj_name)}"
    )


def _panel_link_payload(linked, lct, tmpl_map, **extra):
    from netbox_nsm.core.display_utils import render_object_display
    from netbox_nsm.analysis.addr_analysis_utils import (
        _object_is_addr_analyzable,
        _object_supports_addr_analysis,
    )
    from netbox_nsm.core.interface_parent import interface_parent_host_payload
    from netbox_nsm.core.nsm_object_status import (
        get_nsm_object_status,
        nsm_object_status_icon_html,
    )

    object_status = get_nsm_object_status(linked)
    payload = {
        "url": (
            linked.get_absolute_url() if hasattr(linked, "get_absolute_url") else "#"
        ),
        "name": render_object_display(linked, lct.pk, tmpl_map),
        "ct_id": lct.pk,
        "obj_id": linked.pk,
        "addr_analyzable": _object_is_addr_analyzable(linked, lct.pk),
        "supports_addr_analysis": _object_supports_addr_analysis(linked),
        "status": object_status,
        "status_icon_html": nsm_object_status_icon_html(object_status),
        **interface_parent_host_payload(linked),
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
        from django.urls import reverse
        from netbox_nsm.security.panel_link_actions import (
            address_ipam_fk_action_urls,
            address_ipam_fk_ref_action_urls,
            group_m2m_action_urls,
            object_link_action_urls,
        )
        from netbox_nsm.security.panel import build_cot_security_panel_groups
        from netbox_nsm.core.branch_urls import with_branch_query

        request = self.context.get("request")

        def _panel_url(url: str) -> str:
            if not url:
                return ""
            return with_branch_query(url, request) if request else url

        obj = self.context.get("object")
        if not obj or not hasattr(obj, "pk"):
            return ""

        ct = ContentType.objects.get_for_model(obj)

        from netbox_nsm.core.display_utils import (
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

        # ── Object links grouped by linked-object type (COT nsm_object_link) ──
        from netbox_nsm.objects.object_link_service import build_panel_link_groups

        links_by_type: dict = {}
        _return_url = (
            self.context.get("request").path if self.context.get("request") else "/"
        )
        cot_link_groups, _cot_total = build_panel_link_groups(
            obj,
            return_url=_return_url,
            panel_link_payload=_panel_link_payload,
            object_link_action_urls=object_link_action_urls,
            type_label_fn=_link_type_label,
        )
        for group in cot_link_groups:
            links_by_type[group["type_key"]] = {
                "label": group["type_label"],
                "objects": list(group["objects"]),
            }

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

            from netbox_nsm.objects.address_ipam_fk import fk_field_name_from_filter

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
            from netbox_nsm.objects.address_ipam_fk import (
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

            from netbox_nsm.objects.group_m2m import iter_group_m2m_relations

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

        # ── Security rules that reference this object (COT rulebooks) ─────
        panel_data = build_cot_security_panel_groups(
            ct,
            obj.pk,
            panel_url=_panel_url,
        )
        rulebook_groups = panel_data["rulebook_groups"]
        unique_rules_total = panel_data["unique_rules_total"]

        return_url = request.path if request else "/"
        from urllib.parse import quote

        from netbox_nsm.core.plugin_labels import get_nsm_panel_label
        from netbox_nsm.analysis.addr_analysis_utils import _object_supports_addr_analysis

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
        from netbox_nsm.models import CotRulebookAssignment

        enforcer_assignments = []
        enforcer_add_url = None
        try:
            from dcim.models import Device, VirtualDeviceContext
            from virtualization.models import VirtualMachine

            if isinstance(obj, (Device, VirtualMachine, VirtualDeviceContext)):
                enforcer_assignments = list(
                    CotRulebookAssignment.objects.filter(
                        assigned_object_type=ct,
                        assigned_object_id=obj.pk,
                    ).order_by("cot_slug")
                )
                enforcer_add_url = (
                    reverse("plugins:netbox_nsm:cotrulebookassignment_add")
                    + f"?assigned_object_type={ct.pk}&assigned_object_id={obj.pk}&return_url={return_url}"
                )
        except Exception:
            pass

        nsm_interface_analysis = []
        try:
            from dcim.models import Device as _AnalysisDevice
            from virtualization.models import VirtualMachine as _AnalysisVM
            from netbox_nsm.security.host_interface_analysis import (
                build_host_interface_analysis,
            )

            if isinstance(obj, (_AnalysisDevice, _AnalysisVM)):
                nsm_interface_analysis = build_host_interface_analysis(
                    obj,
                    request=request,
                    panel_url=_panel_url,
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
                "nsm_interface_analysis": nsm_interface_analysis,
            },
        )


template_extensions = [NsmStylesExtension, NsmSecurityLinksExtension]
