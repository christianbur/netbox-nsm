# Address and address-group name templates

Configure Jinja2-based naming for `nsm_address` and `nsm_address_group` objects in **`PLUGINS_CONFIG['netbox_nsm']`**. Templates apply plugin-wide (not per COT in `nsm_config` comments).

Per-type **`object_builder.sources.*.build_template`** in COT `nsm_config` remains the fallback when no plugin template matches the IPAM type.

## Configuration

```python
PLUGINS_CONFIG = {
    "netbox_nsm": {
        "address_name_templates": [
            {"template": "h-{ipam>ip}", "match": "host"},
            {"template": "H-{ipam>ip}", "match": "ipaddress"},
            {
                "template": "n-{ipam>prefix>network}-{ipam>prefix>cidr}",
                "match": "prefix",
            },
            {
                "template": "r-{ipam>range>start}-{ipam>range>end}",
                "match": "range",
            },
        ],
        "address_group_name_templates": [
            {"template": "g-{nsm>member_count}-hosts", "match": "host_members"},
            {"template": "grp-{nsm>name}", "match": "any"},
        ],
    },
}
```

Each entry is a dict with:

| Key | Description |
|-----|-------------|
| `template` | Template string (required) |
| `match` | IPAM / group kind filter (optional, default `any`) |

String-only entries are allowed: `"h-{ipam>ip}"` → match `any`.

### Match values — addresses

| `match` | IPAM source |
|---------|-------------|
| `host`, `ip`, `ipaddress` | `ipam.ipaddress` |
| `prefix`, `net`, `network` | `ipam.prefix` |
| `range`, `iprange` | `ipam.iprange` |
| `any`, `*` | all types |

Full source keys (`ipam.ipaddress`, …) also work.

### Match values — address groups

| `match` | When it applies |
|---------|-----------------|
| `host_members`, `host`, `hosts` | all members link to IP addresses |
| `prefix_members`, `prefix`, `prefixes` | all members link to prefixes |
| `mixed` | members use more than one IPAM type |
| `any`, `*` | always (use as last-resort catch-all) |

**First matching template wins** — order the list from specific to general.

## Template syntax

### Short syntax (recommended)

Curly placeholders with `>` path segments are converted to Jinja2:

| Short | Jinja2 |
|-------|--------|
| `{ipam>ip}` | `{{ ipam.ip }}` |
| `{ipam>prefix>network}` | `{{ ipam.prefix.network }}` |
| `{ipam>prefix>cidr}` | `{{ ipam.prefix.cidr }}` |
| `{nsm>name}` | `{{ nsm.name }}` |

Example: `h-{ipam>ip}` → `h-10.0.0.1` for host `10.0.0.1/32`.

### Native Jinja2

Use `{{ … }}`, filters, and control structures directly:

```jinja2
H-{{ ipam.ip | upper }}
{% if ipam.dns_name %}{{ ipam.dns_name }}{% else %}h-{{ ipam.ip }}{% endif %}
```

### Legacy Object Builder placeholders

Templates **without** Jinja2 markers (`{{`, `{%`, or `{ipam>…}`) keep the existing `{host}`, `{network}`, `{prefix_length}`, `{start_host}`, `{end_host}` behaviour from COT `object_builder` config.

## Jinja2 context — addresses

Built by `build_ipam_name_context()` / used in `render_ipam_object_name()`:

| Variable | Description |
|----------|-------------|
| `ipam.source` | `ipam.ipaddress`, `ipam.prefix`, or `ipam.iprange` |
| `ipam.ip` | Host address without CIDR (IP Address) |
| `ipam.address` | Full IP Address field (with mask) |
| `ipam.host` | Alias for `ipam.ip` |
| `ipam.dns_name` | DNS name |
| `ipam.description` | IPAM description |
| `ipam.status` | IPAM status value |
| `ipam.prefix.network` | Prefix network (no mask) |
| `ipam.prefix.cidr` | Prefix length |
| `ipam.prefix.prefix_length` | Alias for `cidr` |
| `ipam.range.start` / `.end` | Range bounds without CIDR |
| `ipam.range.start_host` / `.end_host` | Aliases |
| `nsm.name`, `nsm.status`, … | NSM address object when passed |
| `host`, `network`, `prefix_length`, … | Flat legacy aliases |

## Jinja2 context — address groups

| Variable | Description |
|----------|-------------|
| `nsm.name`, `nsm.status`, `nsm.member_count` | Group object |
| `members` | List of `{name, nsm}` per member |
| `group` | Alias for `nsm` fields on the group |

## Python API

```python
from netbox_nsm.objects.address_name_templates import (
    render_address_name,
    render_address_group_name,
    render_ipam_object_name,
)

# IPAM object (Object Builder, imports, scripts)
name = render_ipam_object_name(ip_address, "ipam.ipaddress", builder_config=cfg)

# Existing nsm_address row
name = render_address_name(address_obj)

# Address group
name = render_address_group_name(group_obj)
```

Object Builder sync (`scan_sync_state`, `create_addresses`, sync fixes) uses `render_ipam_object_name()` automatically.

## Relation to Object Config

| Layer | Location | Scope |
|-------|----------|-------|
| Plugin templates | `PLUGINS_CONFIG` | Global, Jinja2 |
| Object Builder | COT `comments` → `nsm_config.object_builder` | Per `nsm_address` type, legacy + Jinja2 |

Plugin templates take precedence when their `match` fits the IPAM type.

[← Documentation index](README.md)
