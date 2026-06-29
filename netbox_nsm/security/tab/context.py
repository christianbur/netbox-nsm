"""Shared Security tab / panel context builders."""

from __future__ import annotations

from urllib.parse import quote

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from netbox_nsm.analysis.addr_analysis_utils import (
    _object_is_addr_analyzable,
    _object_supports_addr_analysis,
)
from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.core.display_utils import (
    get_display_template_map,
    render_object_display,
    type_config_display_name_for_ct_id,
)
from netbox_nsm.core.interface_parent import interface_parent_host_payload
from netbox_nsm.core.nsm_object_status import (
    get_nsm_object_status,
    nsm_object_status_icon_html,
)
from netbox_nsm.core.plugin_labels import get_nsm_panel_label
from netbox_nsm.security.tab.badge import count_security_tab_badge
from netbox_nsm.security.tab.security_rows import append_cot_reference_link_groups
from netbox_nsm.security.references.cot_rule_references import build_cot_security_rulebook_groups
from netbox_nsm.security.tab.links import prepare_link_tab_view
from netbox_nsm.security.tab.value_groups import nsm_object_group_value
from netbox_nsm.security.actions.panel_link_actions import (
    address_ipam_fk_action_urls,
    address_ipam_fk_ref_action_urls,
    group_m2m_action_urls,
)

__all__ = (
    "build_security_tab_context",
    "finalize_link_type_group",
    "finalize_link_type_groups",
    "panel_link_payload",
    "row_has_link_actions",
)


def panel_link_payload(linked, lct, tmpl_map, **extra):
    object_status = get_nsm_object_status(linked)
    value_key, value_label = nsm_object_group_value(linked)
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
        "value_key": value_key,
        "value_label": value_label,
        **interface_parent_host_payload(linked),
    }
    payload.update(extra)
    return payload


def row_has_link_actions(obj: dict) -> bool:
    """True when a Security link row should show action icons."""
    if obj.get("supports_addr_analysis") or obj.get("addr_analyzable"):
        return True
    if obj.get("edit_url") or obj.get("delete_url"):
        return True
    return False


def finalize_link_type_group(group: dict) -> dict:
    """Derive Security table column flags from row payloads."""
    objects = group.get("objects") or []
    show_comment = any(o.get("comment") for o in objects)
    show_actions = any(row_has_link_actions(obj) for obj in objects)
    finalized = dict(group)
    finalized["show_comment"] = show_comment
    finalized["show_actions"] = show_actions
    return finalized


def finalize_link_type_groups(groups: list) -> list:
    return [finalize_link_type_group(g) for g in groups]


def build_security_tab_context(obj, request) -> dict:
    """Build template context for the Security tab (formerly the right panel)."""
    if not obj or not hasattr(obj, "pk"):
        return {}

    def _panel_url(url: str) -> str:
        if not url:
            return ""
        return with_branch_query(url, request) if request else url

    ct = ContentType.objects.get_for_model(obj)
    tmpl_map = get_display_template_map()
    type_label_cache: dict[int, str] = {}

    def _link_type_label(content_type) -> str:
        ct_id = content_type.pk
        if ct_id not in type_label_cache:
            type_label_cache[ct_id] = type_config_display_name_for_ct_id(ct_id)
        return type_label_cache[ct_id]

    links_by_type: dict = {}
    return_url = request.path if request else "/"

    append_cot_reference_link_groups(
        links_by_type,
        obj,
        request,
        panel_link_payload=panel_link_payload,
        tmpl_map=tmpl_map,
        type_label_fn=_link_type_label,
        return_url=return_url,
    )

    try:
        from ipam.models import (
            IPAddress as _IPAddress,
            IPRange as _IPRange,
            Prefix as _Prefix,
        )

        from netbox_nsm.addresses.address_ipam_fk import (
            get_nsm_address_model,
            iter_addresses_for_ipam_object,
        )

        if isinstance(obj, (_IPAddress, _Prefix, _IPRange)):
            _AddrModel = get_nsm_address_model()
            if _AddrModel is not None:
                _addr_ct = ContentType.objects.get_for_model(_AddrModel)
                _addr_type_key = f"{_addr_ct.app_label}__{_addr_ct.model}"
                _fk_existing_urls = {
                    o["url"] for g in links_by_type.values() for o in g["objects"]
                }
                for _addr_obj, _fk_field_name in iter_addresses_for_ipam_object(obj):
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
                        panel_link_payload(
                            _addr_obj,
                            _addr_ct,
                            tmpl_map,
                            comment="",
                            **address_ipam_fk_ref_action_urls(
                                obj,
                                _addr_obj,
                                _fk_field_name,
                                return_url,
                            ),
                        )
                    )
                    _fk_existing_urls.add(_addr_url)
    except Exception:
        pass

    try:
        from netbox_nsm.addresses.address_ipam_fk import (
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
                    panel_link_payload(
                        _ipam_obj,
                        _ipam_ct,
                        tmpl_map,
                        comment="",
                        **address_ipam_fk_action_urls(
                            obj,
                            _ref.field_name,
                            _ipam_obj,
                            return_url,
                        ),
                    )
                )
                _ipam_existing_urls.add(_ipam_url)
    except Exception:
        pass

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
                panel_link_payload(
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
                **group_m2m_action_urls(_relation, return_url, page_obj=obj),
            )
    except Exception:
        pass

    link_type_groups = finalize_link_type_groups(
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

    nsm_inherited_api_url = None
    try:
        from ipam.models import (
            IPAddress as _IPCheck,
            IPRange as _IRCheck,
            Prefix as _PfxCheck,
        )

        if isinstance(obj, (_IPCheck, _IRCheck, _PfxCheck)):
            nsm_inherited_api_url = (
                reverse("plugins:netbox_nsm:inherited_links_api")
                + f"?ct_id={ct.pk}&obj_id={obj.pk}"
            )
    except Exception:
        pass

    panel_data = build_cot_security_rulebook_groups(
        ct,
        obj.pk,
        panel_url=_panel_url,
    )
    rulebook_groups = panel_data["rulebook_groups"]
    unique_rules_total = panel_data["unique_rules_total"]

    obj_name = str(obj)
    analyzer_url = (
        reverse("plugins:netbox_nsm:object_analyzer")
        + f"?ct={ct.pk}&pk={obj.pk}&name={quote(obj_name)}"
    )
    assign_url = (
        reverse("plugins:netbox_nsm:object_link_assign")
        + f"?ct_id={ct.pk}&obj_id={obj.pk}&return_url={return_url}"
    )

    security_badge = count_security_tab_badge(obj) or None

    nsm_enforcement_point = None
    try:
        from netbox_nsm.security.enforcement_point_panel import (
            build_enforcement_point_panel,
        )

        nsm_enforcement_point = build_enforcement_point_panel(
            obj,
            request=request,
            panel_url=_panel_url,
            return_url=return_url,
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

    context = {
        "nsm_link_type_groups": link_type_groups,
        "nsm_inherited_api_url": nsm_inherited_api_url,
        "nsm_rulebook_groups": rulebook_groups,
        "nsm_unique_rules_total": unique_rules_total,
        "nsm_security_badge": security_badge,
        "nsm_assign_url": assign_url,
        "nsm_analyzer_url": analyzer_url,
        "nsm_panel_label": get_nsm_panel_label(),
        "nsm_page_addr_analyzable": _object_supports_addr_analysis(obj),
        "nsm_page_object_ct": ct.pk,
        "nsm_page_object_pk": obj.pk,
        "nsm_page_object_name": obj_name,
        "nsm_enforcement_point": nsm_enforcement_point,
        "nsm_interface_analysis": nsm_interface_analysis,
    }
    # Object-type tabs + value sub-grouping + pagination over the linked objects.
    # Overwrites ``nsm_link_type_groups`` with tab-annotated groups and adds the
    # active page slice so at most one page of rows reaches the browser.
    context.update(prepare_link_tab_view(link_type_groups, request))
    return context
