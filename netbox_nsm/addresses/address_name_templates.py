"""Jinja2-based naming templates for ``nsm_address`` / ``nsm_address_group`` objects.

Templates are configured globally via ``PLUGINS_CONFIG['netbox_nsm']``:

.. code-block:: python

    PLUGINS_CONFIG = {
        'netbox_nsm': {
            'address_name_templates': [
                {'template': 'h-{ipam>ip}', 'match': 'host'},
                {'template': 'n-{ipam>prefix>network}-{ipam>prefix>cidr}', 'match': 'prefix'},
            ],
            'address_group_name_templates': [
                {'template': 'g-{nsm>member_count}', 'match': 'any'},
            ],
        },
    }

Short syntax ``{ipam>ip}`` is converted to Jinja2 ``{{ ipam.ip }}``. Native Jinja2
(``{{ ipam.ip }}``, filters, ``{% if %}``) is supported as well. Legacy placeholders
(``{host}``, ``{network}``, ``{prefix_length}``) remain supported when no Jinja2 markers
are present.

For each IPAM object the **first matching** plugin template in the list wins.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

__all__ = (
    "ADDRESS_MATCH_ALIASES",
    "GROUP_MATCH_ALIASES",
    "build_ipam_name_context",
    "build_group_name_context",
    "convert_short_syntax_to_jinja",
    "get_address_group_name_templates",
    "get_address_name_templates",
    "infer_group_match_kind",
    "normalize_match_value",
    "normalize_name_template_list",
    "render_address_group_name",
    "render_address_name",
    "render_ipam_object_name",
    "render_template_string",
    "resolve_group_name_template",
    "resolve_ipam_name_template",
    "template_uses_jinja",
)

_SHORT_PATH_PLACEHOLDER = re.compile(
    r"\{([a-zA-Z_][\w]*(?:>[a-zA-Z_][\w]*)+)\}"
)

ADDRESS_MATCH_ALIASES = {
    "any": "*",
    "*": "*",
    "host": "ipam.ipaddress",
    "ipaddress": "ipam.ipaddress",
    "ip": "ipam.ipaddress",
    "address": "ipam.ipaddress",
    "prefix": "ipam.prefix",
    "net": "ipam.prefix",
    "network": "ipam.prefix",
    "range": "ipam.iprange",
    "iprange": "ipam.iprange",
}

GROUP_MATCH_ALIASES = {
    "any": "*",
    "*": "*",
    "prefix": "prefix_members",
    "prefixes": "prefix_members",
    "prefix_members": "prefix_members",
    "host": "host_members",
    "hosts": "host_members",
    "host_members": "host_members",
    "mixed": "mixed",
}


def normalize_match_value(value: str | None, *, aliases: dict[str, str]) -> str:
    key = (value or "any").strip().lower()
    return aliases.get(key, key)


def normalize_name_template_list(raw: list | None) -> list[dict[str, str]]:
    """Return ``[{"template": str, "match": str}, ...]`` from plugin config."""
    if not raw:
        return []
    result: list[dict[str, str]] = []
    for entry in raw:
        if isinstance(entry, str):
            text = entry.strip()
            if text:
                result.append({"template": text, "match": "any"})
            continue
        if not isinstance(entry, dict):
            continue
        template = str(entry.get("template") or "").strip()
        if not template:
            continue
        match = str(entry.get("match") or "any").strip() or "any"
        result.append({"template": template, "match": match})
    return result


@lru_cache(maxsize=1)
def get_address_name_templates() -> tuple[dict[str, str], ...]:
    from netbox.plugins import get_plugin_config

    raw = get_plugin_config("netbox_nsm", "address_name_templates", [])
    return tuple(normalize_name_template_list(raw))


@lru_cache(maxsize=1)
def get_address_group_name_templates() -> tuple[dict[str, str], ...]:
    from netbox.plugins import get_plugin_config

    raw = get_plugin_config("netbox_nsm", "address_group_name_templates", [])
    return tuple(normalize_name_template_list(raw))


def clear_name_template_caches() -> None:
    """Reset cached plugin config (tests only)."""
    get_address_name_templates.cache_clear()
    get_address_group_name_templates.cache_clear()


def convert_short_syntax_to_jinja(template: str) -> str:
    """Convert ``{ipam>prefix>network}`` placeholders to ``{{ ipam.prefix.network }}``."""

    def _replace(match: re.Match[str]) -> str:
        path = match.group(1).replace(">", ".")
        return "{{ " + path + " }}"

    return _SHORT_PATH_PLACEHOLDER.sub(_replace, template)


def template_uses_jinja(template: str) -> bool:
    if "{{" in template or "{%" in template:
        return True
    return bool(_SHORT_PATH_PLACEHOLDER.search(template))


def _ip_without_cidr(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "ip"):
        try:
            return str(value.ip)
        except Exception:
            pass
    text = str(value)
    if "/" in text:
        return text.split("/", 1)[0]
    return text


def _prefix_network_and_cidr(prefix_val) -> tuple[str, str]:
    network = ""
    cidr = ""
    if prefix_val is None:
        return network, cidr
    if hasattr(prefix_val, "prefixlen"):
        try:
            network = str(prefix_val.ip.network)
        except Exception:
            network = str(getattr(prefix_val, "ip", "") or "")
        cidr = str(prefix_val.prefixlen)
        return network, cidr
    text = str(prefix_val)
    if "/" in text:
        network, cidr = text.split("/", 1)
    else:
        network = text
    return network, cidr


def _nsm_context_fields(obj) -> dict[str, Any]:
    if obj is None:
        return {}
    fields: dict[str, Any] = {
        "name": getattr(obj, "name", "") or "",
        "status": str(getattr(obj, "status", "") or ""),
        "description": getattr(obj, "description", "") or "",
    }
    for attr in ("comments", "slug", "color"):
        if hasattr(obj, attr):
            val = getattr(obj, attr, None)
            if val not in (None, ""):
                fields[attr] = val
    return fields


def build_ipam_name_context(
    ipam_obj,
    source_key: str,
    *,
    nsm_obj=None,
) -> dict[str, Any]:
    """Build the Jinja2 context for an IPAM-backed address name."""
    ip_val = _ip_without_cidr(getattr(ipam_obj, "address", None))
    address_val = str(getattr(ipam_obj, "address", "") or "")
    network, cidr = _prefix_network_and_cidr(getattr(ipam_obj, "prefix", None))
    start_host = _ip_without_cidr(getattr(ipam_obj, "start_address", None))
    end_host = _ip_without_cidr(getattr(ipam_obj, "end_address", None))

    ipam_ctx: dict[str, Any] = {
        "source": source_key,
        "ip": ip_val,
        "address": address_val,
        "host": ip_val,
        "dns_name": getattr(ipam_obj, "dns_name", "") or "",
        "description": getattr(ipam_obj, "description", "") or "",
        "status": str(getattr(getattr(ipam_obj, "status", None), "value", getattr(ipam_obj, "status", "")) or ""),
        "prefix": {
            "network": network,
            "cidr": cidr,
            "prefix_length": cidr,
        },
        "range": {
            "start": start_host,
            "end": end_host,
            "start_host": start_host,
            "end_host": end_host,
        },
    }

    context: dict[str, Any] = {
        "ipam": ipam_ctx,
        "nsm": _nsm_context_fields(nsm_obj),
        # Legacy flat aliases (also usable in Jinja2 templates).
        "host": ip_val,
        "network": network,
        "prefix_length": cidr,
        "start_host": start_host,
        "end_host": end_host,
    }
    return context


def _iter_group_members(group_obj):
    members_rel = getattr(group_obj, "group", None)
    if members_rel is not None and hasattr(members_rel, "all"):
        yield from members_rel.all()
        return
    legacy = getattr(group_obj, "address_group", None)
    if legacy is not None and hasattr(legacy, "all"):
        yield from legacy.all()


def infer_group_match_kind(members: list) -> str:
    from netbox_nsm.addresses.ipam_keys import (
        ipam_key_for_address,
        ipam_obj_for_key,
        source_key_for_ipam_obj,
    )

    source_keys: set[str] = set()
    for member in members:
        key = ipam_key_for_address(member)
        if key is None:
            continue
        ipam_obj = ipam_obj_for_key(key)
        if ipam_obj is None:
            continue
        sk = source_key_for_ipam_obj(ipam_obj)
        if sk:
            source_keys.add(sk)
    if not source_keys:
        return "any"
    if source_keys == {"ipam.prefix"}:
        return "prefix_members"
    if source_keys == {"ipam.ipaddress"}:
        return "host_members"
    if len(source_keys) > 1:
        return "mixed"
    return "any"


def build_group_name_context(group_obj, *, members: list | None = None) -> dict[str, Any]:
    member_rows: list[dict[str, Any]] = []
    if members is None:
        members = list(_iter_group_members(group_obj))

    for member in members:
        row = {"name": getattr(member, "name", "") or "", "nsm": _nsm_context_fields(member)}
        member_rows.append(row)

    return {
        "nsm": {
            **_nsm_context_fields(group_obj),
            "member_count": len(members),
        },
        "members": member_rows,
        "group": _nsm_context_fields(group_obj),
    }


def _address_template_matches(entry: dict[str, str], source_key: str) -> bool:
    match = normalize_match_value(entry.get("match"), aliases=ADDRESS_MATCH_ALIASES)
    if match in ("*", "any"):
        return True
    return match == source_key


def _group_template_matches(entry: dict[str, str], group_kind: str) -> bool:
    match = normalize_match_value(entry.get("match"), aliases=GROUP_MATCH_ALIASES)
    if match in ("*", "any"):
        return True
    return match == group_kind


def resolve_ipam_name_template(source_key: str) -> str | None:
    for entry in get_address_name_templates():
        if _address_template_matches(entry, source_key):
            return entry["template"]
    return None


def resolve_group_name_template(group_kind: str) -> str | None:
    for entry in get_address_group_name_templates():
        if _group_template_matches(entry, group_kind):
            return entry["template"]
    return None


def _render_jinja(template: str, context: dict[str, Any]) -> str:
    from jinja2 import TemplateError
    from jinja2.sandbox import SandboxedEnvironment

    env = SandboxedEnvironment(autoescape=False)
    try:
        compiled = env.from_string(template)
        rendered = compiled.render(**context)
    except TemplateError:
        return ""
    return str(rendered).strip()


def render_template_string(
    template: str,
    ipam_obj,
    source_key: str,
    *,
    nsm_obj=None,
    extra_context: dict[str, Any] | None = None,
) -> str:
    """Render *template* for *ipam_obj* using Jinja2 or legacy placeholders."""
    if not template:
        return ""

    if template_uses_jinja(template):
        jinja_template = convert_short_syntax_to_jinja(template)
        context = build_ipam_name_context(ipam_obj, source_key, nsm_obj=nsm_obj)
        if extra_context:
            context.update(extra_context)
        return _render_jinja(jinja_template, context)

    from netbox_nsm.addresses.ipam_keys import legacy_format_template

    flat = build_ipam_name_context(ipam_obj, source_key, nsm_obj=nsm_obj)
    legacy_ctx = {**flat.get("ipam", {}), **flat.get("nsm", {})}
    return legacy_format_template(template, legacy_ctx)


def render_ipam_object_name(
    ipam_obj,
    source_key: str | None = None,
    *,
    nsm_obj=None,
) -> str:
    """Resolve and render the name for an IPAM object using plugin templates."""
    from netbox_nsm.addresses.ipam_keys import source_key_for_ipam_obj

    if source_key is None:
        source_key = source_key_for_ipam_obj(ipam_obj)
    if not source_key:
        return ""

    plugin_template = resolve_ipam_name_template(source_key)
    if plugin_template:
        return render_template_string(
            plugin_template, ipam_obj, source_key, nsm_obj=nsm_obj
        )

    return ""


def render_address_name(address_obj, ipam_ref=None) -> str:
    """Render the expected name for an ``nsm_address`` row.

    *ipam_ref* may be the linked IPAM object; when omitted it is resolved from
    *address_obj* polymorphic fields.
    """
    from netbox_nsm.addresses.ipam_keys import (
        ipam_key_for_address,
        ipam_obj_for_key,
        source_key_for_ipam_obj,
    )

    ipam_obj = ipam_ref
    source_key = source_key_for_ipam_obj(ipam_obj) if ipam_obj is not None else None

    if ipam_obj is None:
        ipam_key = ipam_key_for_address(address_obj)
        if ipam_key is None:
            return ""
        ipam_obj = ipam_obj_for_key(ipam_key)
        if ipam_obj is None:
            return ""
        source_key = source_key_for_ipam_obj(ipam_obj)

    return render_ipam_object_name(
        ipam_obj,
        source_key,
        nsm_obj=address_obj,
    )


def render_address_group_name(group_obj, *, members: list | None = None) -> str:
    """Render a name for ``nsm_address_group`` using plugin templates (first match)."""
    if members is None:
        members = list(_iter_group_members(group_obj))
    group_kind = infer_group_match_kind(members)
    template = resolve_group_name_template(group_kind)
    if not template:
        return ""

    if template_uses_jinja(template):
        jinja_template = convert_short_syntax_to_jinja(template)
        context = build_group_name_context(group_obj, members=members)
        return _render_jinja(jinja_template, context)

    from netbox_nsm.addresses.ipam_keys import legacy_format_template

    context = build_group_name_context(group_obj, members=members)
    return legacy_format_template(template, context.get("nsm", {}))
