"""Build and sync ``nsm_address`` rows from NetBox IPAM objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from netbox_nsm.objects.address_literal import is_literal_address
from netbox_nsm.objects.address_name_templates import render_ipam_object_name
from netbox_nsm.objects.object_builder_config import (
    BUILDABLE_IPAM_STATUSES,
    BUILDER_IGNORE_STATUS,
    IPAM_SOURCE_KEYS,
)

__all__ = (
    "BuildPreviewRow",
    "BuildResult",
    "SyncFixResult",
    "SyncIssue",
    "SyncSummary",
    "apply_sync_fixes",
    "DEPRECATED_OBJECT_STATUS",
    "expand_bulk_fix_tokens",
    "build_name",
    "create_addresses",
    "index_addresses_by_ipam_key",
    "index_groups_by_ipam_signature",
    "ipam_key_for_address",
    "ipam_key_for_ipam_obj",
    "ipam_polymorphic_kwargs",
    "is_buildable_ipam_status",
    "is_ignored_ipam_status",
    "map_status",
    "resolve_builder_config",
    "scan_sync_state",
    "source_key_for_ipam_obj",
    "sync_issue_fix_actions",
    "sync_issue_selection_id",
)

DEPRECATED_OBJECT_STATUS = "deprecated"

IpamKey = tuple[int, int]

_SOURCE_MODELS: dict[str, tuple[str, str]] = {
    "ipam.ipaddress": ("ipam", "ipaddress"),
    "ipam.prefix": ("ipam", "prefix"),
    "ipam.iprange": ("ipam", "iprange"),
}


@dataclass
class BuildPreviewRow:
    source_key: str
    ipam_obj: object
    ipam_key: IpamKey
    generated_name: str
    target_status: str
    description: str
    can_create: bool
    skip_reason: str | None = None


@dataclass
class BuildResult:
    created: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class SyncFixResult:
    fixed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class SyncIssue:
    category: str
    source_key: str | None = None
    ipam_obj: object | None = None
    ipam_key: IpamKey | None = None
    address_obj: object | None = None
    addresses: list | None = None
    group_obj: object | None = None
    groups: list | None = None
    expected_name: str | None = None
    expected_status: str | None = None
    actual_status: str | None = None
    overlap_keys: list[IpamKey] | None = None
    member_issues: list[str] | None = None
    detail: str | None = None
    can_create: bool = False

    @property
    def fix_actions(self) -> list[dict[str, str]]:
        return sync_issue_fix_actions(self)

    @property
    def has_fix_actions(self) -> bool:
        return bool(self.fix_actions)

    @property
    def sync_selection_id(self) -> str | None:
        return sync_issue_selection_id(self)


@dataclass
class SyncSummary:
    enabled: bool
    issues: list[SyncIssue] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    def count_for(self, category: str) -> int:
        return self.counts.get(category, 0)


def resolve_builder_config(cot) -> dict[str, Any] | None:
    from netbox_nsm.objects.nsm_config import resolve_object_builder_config_for_cot

    return resolve_object_builder_config_for_cot(cot)


def _content_type_for_source(source_key: str) -> ContentType:
    app_label, model = _SOURCE_MODELS[source_key]
    return ContentType.objects.get(app_label=app_label, model=model)


def _model_for_source(source_key: str):
    ct = _content_type_for_source(source_key)
    return ct.model_class()


def source_key_for_ipam_obj(ipam_obj) -> str | None:
    ct = ContentType.objects.get_for_model(ipam_obj)
    for source_key, (app_label, model) in _SOURCE_MODELS.items():
        if ct.app_label == app_label and ct.model == model:
            return source_key
    return None


def ipam_key_for_ipam_obj(ipam_obj) -> IpamKey:
    ct = ContentType.objects.get_for_model(ipam_obj)
    return ct.pk, ipam_obj.pk


def ipam_polymorphic_kwargs(ipam_obj) -> dict[str, int]:
    ct_id, obj_id = ipam_key_for_ipam_obj(ipam_obj)
    return {
        "address_content_type_id": ct_id,
        "address_object_id": obj_id,
    }


def ipam_key_for_address(addr_obj) -> IpamKey | None:
    ct_id = getattr(addr_obj, "address_content_type_id", None)
    obj_id = getattr(addr_obj, "address_object_id", None)
    if ct_id and obj_id:
        return int(ct_id), int(obj_id)
    from netbox_nsm.objects.address_ipam_fk import iter_address_ipam_fk_refs

    refs = list(iter_address_ipam_fk_refs(addr_obj))
    if not refs:
        return None
    ref = refs[0]
    return ref.ipam_ct.pk, ref.ipam_obj.pk


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


_BUILDER_COMPUTED_FIELDS = frozenset(
    {"prefix_length", "network", "host", "start_host", "end_host"}
)


def _computed_field(ipam_obj, field_name: str) -> str:
    if field_name == "host":
        return _ip_without_cidr(getattr(ipam_obj, "address", None))
    if field_name == "start_host":
        return _ip_without_cidr(getattr(ipam_obj, "start_address", None))
    if field_name == "end_host":
        return _ip_without_cidr(getattr(ipam_obj, "end_address", None))

    prefix_val = getattr(ipam_obj, "prefix", None)
    if field_name == "prefix_length":
        if prefix_val is None:
            return ""
        if hasattr(prefix_val, "prefixlen"):
            return str(prefix_val.prefixlen)
        text = str(prefix_val)
        if "/" in text:
            return text.split("/", 1)[1]
        return ""
    if field_name == "network":
        if prefix_val is None:
            return ""
        if hasattr(prefix_val, "ip"):
            try:
                return str(prefix_val.ip.network)
            except Exception:
                pass
        text = str(prefix_val)
        if "/" in text:
            return text.split("/", 1)[0]
        return text
    return ""


def build_name(ipam_obj, source_key: str, template: str) -> str:
    if not template:
        return ""

    import re

    placeholder = re.compile(r"\{(\w+)(?:\[([-]?\d+)\])?(?:!(u))?\}")

    def _replace(match: re.Match) -> str:
        field = match.group(1)
        idx = match.group(2)
        upper = match.group(3)
        if field in _BUILDER_COMPUTED_FIELDS:
            raw = _computed_field(ipam_obj, field)
        else:
            val = getattr(ipam_obj, field, "") or ""
            if idx is not None:
                try:
                    raw = str(val)[int(idx)]
                except (IndexError, ValueError, TypeError):
                    raw = ""
            else:
                raw = str(val)
        if upper:
            raw = raw.upper()
        return raw

    return placeholder.sub(_replace, template)


def map_status(ipam_status, status_map: dict[str, str], *, default: str = "active") -> str:
    if ipam_status is None:
        return default
    key = str(getattr(ipam_status, "value", ipam_status))
    return status_map.get(key, default)


def _ipam_status_key(ipam_status) -> str:
    if ipam_status is None:
        return "active"
    return str(getattr(ipam_status, "value", ipam_status))


def is_ignored_ipam_status(ipam_status, status_map: dict[str, str]) -> bool:
    """True when *ipam_status* is excluded from build and sync."""
    return map_status(ipam_status, status_map) == BUILDER_IGNORE_STATUS


def is_buildable_ipam_status(ipam_status, status_map: dict[str, str]) -> bool:
    """True when a new ``nsm_address`` may be created for this IPAM status."""
    if is_ignored_ipam_status(ipam_status, status_map):
        return False
    return _ipam_status_key(ipam_status) in BUILDABLE_IPAM_STATUSES


def _iter_queryset_or_sequence(qs_or_iterable):
    if hasattr(qs_or_iterable, "iterator"):
        yield from qs_or_iterable.iterator()
    else:
        yield from qs_or_iterable


def index_addresses_by_ipam_key(addr_qs) -> dict[IpamKey, list]:
    """Index IPAM-linked addresses; literal-only rows (e.g. ANY) are excluded."""
    index: dict[IpamKey, list] = {}
    for addr in _iter_queryset_or_sequence(addr_qs):
        if is_literal_address(addr):
            continue
        key = ipam_key_for_address(addr)
        if key is None:
            continue
        index.setdefault(key, []).append(addr)
    return index


def _group_ipam_signature(group_obj, addr_index: dict[IpamKey, list]) -> frozenset[IpamKey]:
    members_rel = getattr(group_obj, "group", None)
    if members_rel is None or not hasattr(members_rel, "all"):
        return frozenset()
    keys: set[IpamKey] = set()
    for member in members_rel.all():
        key = ipam_key_for_address(member)
        if key is not None:
            keys.add(key)
    return frozenset(keys)


def index_groups_by_ipam_signature(group_qs, addr_index: dict[IpamKey, list]) -> dict[frozenset[IpamKey], list]:
    index: dict[frozenset[IpamKey], list] = {}
    for group in _iter_queryset_or_sequence(group_qs):
        signature = _group_ipam_signature(group, addr_index)
        if not signature:
            continue
        index.setdefault(signature, []).append(group)
    return index


def _iter_ipam_objects(source_keys: Iterable[str] | None = None):
    keys = list(source_keys or IPAM_SOURCE_KEYS)
    for source_key in keys:
        model = _model_for_source(source_key)
        if model is None:
            continue
        for obj in model.objects.all().iterator():
            yield source_key, obj


def _address_model_and_cot():
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return None, None
    for slug in ("nsm_address", "nsm_addresses"):
        cot = CustomObjectType.objects.filter(slug=slug).first()
        if cot is not None:
            return cot.get_model(), cot
    return None, None


def _group_model_and_cot():
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return None, None
    for slug in ("nsm_address_group", "nsm_address_groups"):
        cot = CustomObjectType.objects.filter(slug=slug).first()
        if cot is not None:
            return cot.get_model(), cot
    return None, None


def _ipam_obj_for_key(ipam_key: IpamKey):
    ct_id, obj_id = ipam_key
    try:
        ct = ContentType.objects.get(pk=ct_id)
    except ContentType.DoesNotExist:
        return None
    model = ct.model_class()
    if model is None:
        return None
    return model.objects.filter(pk=obj_id).first()


def scan_sync_state(
    builder_config: dict[str, Any] | None,
    *,
    source_keys: Iterable[str] | None = None,
) -> SyncSummary:
    if not builder_config or not builder_config.get("enabled"):
        return SyncSummary(enabled=False)

    status_map = builder_config.get("status_map") or {}
    sources = builder_config.get("sources") or {}
    addr_model, _addr_cot = _address_model_and_cot()
    group_model, _group_cot = _group_model_and_cot()
    issues: list[SyncIssue] = []

    addr_index: dict[IpamKey, list] = {}
    if addr_model is not None:
        addr_index = index_addresses_by_ipam_key(addr_model.objects.all())

    for source_key, ipam_obj in _iter_ipam_objects(source_keys):
        ipam_status = getattr(ipam_obj, "status", None)
        if is_ignored_ipam_status(ipam_status, status_map):
            continue

        ipam_key = ipam_key_for_ipam_obj(ipam_obj)
        linked = addr_index.get(ipam_key, [])
        source_def = sources.get(source_key) or {}
        expected_name = render_ipam_object_name(
            ipam_obj, source_key, builder_config=builder_config
        )
        if not linked:
            issues.append(
                SyncIssue(
                    category="missing",
                    source_key=source_key,
                    ipam_obj=ipam_obj,
                    ipam_key=ipam_key,
                    expected_name=expected_name,
                    expected_status=map_status(ipam_status, status_map),
                    can_create=is_buildable_ipam_status(ipam_status, status_map),
                )
            )
            continue
        expected_status = map_status(ipam_status, status_map)
        for addr in linked:
            actual_status = getattr(addr, "status", None)
            if actual_status and str(actual_status) != expected_status:
                issues.append(
                    SyncIssue(
                        category="status_mismatch",
                        source_key=source_key,
                        ipam_obj=ipam_obj,
                        ipam_key=ipam_key,
                        address_obj=addr,
                        expected_status=expected_status,
                        actual_status=str(actual_status),
                    )
                )
            if expected_name and getattr(addr, "name", None) != expected_name:
                issues.append(
                    SyncIssue(
                        category="name_drift",
                        source_key=source_key,
                        ipam_obj=ipam_obj,
                        ipam_key=ipam_key,
                        address_obj=addr,
                        expected_name=expected_name,
                    )
                )

    for ipam_key, addresses in addr_index.items():
        if len(addresses) > 1:
            names = {getattr(a, "name", "") for a in addresses}
            if len(names) > 1:
                issues.append(
                    SyncIssue(
                        category="duplicate_ipam_link",
                        ipam_key=ipam_key,
                        ipam_obj=_ipam_obj_for_key(ipam_key),
                        addresses=list(addresses),
                    )
                )

    if addr_model is not None:
        for addr in addr_model.objects.iterator():
            if is_literal_address(addr):
                continue
            key = ipam_key_for_address(addr)
            if key is None:
                continue
            if _ipam_obj_for_key(key) is None:
                issues.append(
                    SyncIssue(
                        category="orphan_nsm",
                        address_obj=addr,
                        ipam_key=key,
                    )
                )

    member_issue_categories = {
        "missing",
        "orphan_nsm",
        "status_mismatch",
        "duplicate_ipam_link",
    }

    if group_model is not None and addr_index:
        group_index = index_groups_by_ipam_signature(group_model.objects.all(), addr_index)
        for signature, groups in group_index.items():
            if len(groups) > 1:
                issues.append(
                    SyncIssue(
                        category="duplicate_group_ipam",
                        groups=list(groups),
                        detail=f"{len(signature)} IPAM key(s)",
                    )
                )

        signatures = list(group_index.keys())
        for i, sig_a in enumerate(signatures):
            for sig_b in signatures[i + 1 :]:
                overlap = sig_a & sig_b
                if overlap and sig_a != sig_b:
                    issues.append(
                        SyncIssue(
                            category="group_ipam_overlap",
                            groups=group_index[sig_a] + group_index[sig_b],
                            overlap_keys=sorted(overlap),
                        )
                    )

        for group in group_model.objects.iterator():
            member_issues: list[str] = []
            members_rel = getattr(group, "group", None)
            if members_rel is None or not hasattr(members_rel, "all"):
                continue
            for member in members_rel.all():
                member_key = ipam_key_for_address(member)
                if member_key is None:
                    member_issues.append("group_member_no_ipam")
                    continue
                for issue in issues:
                    if issue.category not in member_issue_categories:
                        continue
                    if issue.address_obj is member or (
                        issue.ipam_key == member_key
                        and issue.category in ("missing", "status_mismatch", "duplicate_ipam_link")
                    ):
                        member_issues.append(issue.category)
            if member_issues:
                issues.append(
                    SyncIssue(
                        category="group_member_drift",
                        group_obj=group,
                        member_issues=sorted(set(member_issues)),
                    )
                )

    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.category] = counts.get(issue.category, 0) + 1

    return SyncSummary(enabled=True, issues=issues, counts=counts)


def sync_issue_fix_actions(issue: SyncIssue) -> list[dict[str, str]]:
    from django.utils.translation import gettext_lazy as _

    if issue.category == "name_drift" and issue.address_obj and issue.expected_name:
        pk = issue.address_obj.pk
        return [
            {
                "token": f"name_drift:rename:{pk}",
                "label": _("Rename"),
                "btn_class": "btn-warning",
                "icon": "mdi-rename-box",
                "title": _("Rename this object to the expected name"),
            },
            {
                "token": f"name_drift:replace:{pk}",
                "label": _("Create new"),
                "btn_class": "btn-outline-warning",
                "icon": "mdi-plus-circle-outline",
                "title": _(
                    "Create a correctly named object, unlink this one, and set it to deprecated"
                ),
            },
        ]
    if (
        issue.category == "status_mismatch"
        and issue.address_obj
        and issue.expected_status
    ):
        return [
            {
                "token": f"status_mismatch:{issue.address_obj.pk}",
                "label": _("Fix status"),
                "btn_class": "btn-warning",
                "icon": "mdi-wrench",
                "title": _("Set status to the expected value"),
            },
        ]
    if (
        issue.category == "missing"
        and issue.ipam_obj
        and issue.source_key
        and issue.can_create
    ):
        return [
            {
                "token": f"missing:{issue.source_key}:{issue.ipam_obj.pk}",
                "label": _("Create"),
                "btn_class": "btn-warning",
                "icon": "mdi-plus",
                "title": _("Create the missing NSM address object"),
            },
        ]
    return []


def sync_issue_selection_id(issue: SyncIssue) -> str | None:
    if issue.category == "name_drift" and issue.address_obj:
        return f"name_drift:{issue.address_obj.pk}"
    if issue.category == "status_mismatch" and issue.address_obj:
        return f"status_mismatch:{issue.address_obj.pk}"
    if (
        issue.category == "missing"
        and issue.ipam_obj
        and issue.source_key
        and issue.can_create
    ):
        return f"missing:{issue.source_key}:{issue.ipam_obj.pk}"
    return None


def expand_bulk_fix_tokens(selection_ids: Iterable[str], bulk_action: str) -> list[str]:
    """Map selected issue ids and a bulk action to concrete fix tokens."""
    action = (bulk_action or "").strip().lower()
    tokens: list[str] = []
    seen: set[str] = set()

    for selection_id in selection_ids:
        selection_id = (selection_id or "").strip()
        if not selection_id:
            continue

        token: str | None = None
        if action == "rename" and selection_id.startswith("name_drift:"):
            token = f"name_drift:rename:{selection_id.split(':', 1)[1]}"
        elif action == "replace" and selection_id.startswith("name_drift:"):
            token = f"name_drift:replace:{selection_id.split(':', 1)[1]}"
        elif action == "status" and selection_id.startswith("status_mismatch:"):
            token = selection_id
        elif action == "create" and selection_id.startswith("missing:"):
            token = selection_id

        if token and token not in seen:
            seen.add(token)
            tokens.append(token)

    return tokens


def _expected_name_for_linked_ipam(ipam_obj, source_key: str, builder_config: dict) -> str:
    return render_ipam_object_name(
        ipam_obj, source_key, builder_config=builder_config
    )


def _load_linked_address_context(
    addr_pk: int,
    builder_config: dict[str, Any],
) -> tuple[object, object, str, str, str] | tuple[None, str]:
    """Return ``(addr, ipam_obj, source_key, expected_name, expected_status)`` or error."""
    addr_model, _ = _address_model_and_cot()
    if addr_model is None:
        return None, "nsm_address Custom Object Type not found."

    addr = addr_model.objects.filter(pk=addr_pk).first()
    if addr is None:
        return None, f"Address object {addr_pk} not found."

    ipam_key = ipam_key_for_address(addr)
    if ipam_key is None:
        return None, f"Address {addr_pk} has no IPAM link."

    ipam_obj = _ipam_obj_for_key(ipam_key)
    if ipam_obj is None:
        return None, f"IPAM object for address {addr_pk} not found."

    source_key = source_key_for_ipam_obj(ipam_obj)
    if not source_key:
        return None, f"Unsupported IPAM type for address {addr_pk}."

    expected_name = _expected_name_for_linked_ipam(ipam_obj, source_key, builder_config)
    if not expected_name:
        return None, f"No build template for {source_key}."

    status_map = builder_config.get("status_map") or {}
    expected_status = map_status(getattr(ipam_obj, "status", None), status_map)
    return addr, ipam_obj, source_key, expected_name, expected_status


def _fix_name_drift(addr_pk: int, builder_config: dict[str, Any]) -> tuple[bool, str | None]:
    addr_model, _ = _address_model_and_cot()
    if addr_model is None:
        return False, "nsm_address Custom Object Type not found."

    loaded = _load_linked_address_context(addr_pk, builder_config)
    if loaded[0] is None:
        return False, loaded[1]
    addr, _ipam_obj, _source_key, expected_name, _expected_status = loaded

    current_name = getattr(addr, "name", None)
    if current_name == expected_name:
        return False, None

    if addr_model.objects.filter(name=expected_name).exclude(pk=addr.pk).exists():
        return False, f'Name "{expected_name}" is already in use.'

    addr.name = expected_name
    addr.save(update_fields=["name"])
    return True, None


def _fix_name_drift_replace(
    addr_pk: int, builder_config: dict[str, Any]
) -> tuple[bool, str | None]:
    addr_model, _ = _address_model_and_cot()
    if addr_model is None:
        return False, "nsm_address Custom Object Type not found."

    loaded = _load_linked_address_context(addr_pk, builder_config)
    if loaded[0] is None:
        return False, loaded[1]
    addr, ipam_obj, source_key, expected_name, expected_status = loaded

    current_name = getattr(addr, "name", None)
    if current_name == expected_name:
        return False, None

    if addr_model.objects.filter(name=expected_name).exists():
        return False, f'Name "{expected_name}" is already in use.'

    sources = builder_config.get("sources") or {}
    source_def = sources.get(source_key) or {}
    kwargs: dict[str, Any] = {
        "name": expected_name,
        "status": expected_status,
        **ipam_polymorphic_kwargs(ipam_obj),
    }
    if source_def.get("copy_description"):
        desc = getattr(ipam_obj, "description", "") or ""
        if desc:
            kwargs["description"] = desc

    addr_model.objects.create(**kwargs)

    from netbox_nsm.objects.address_ipam_fk import clear_address_ipam_link

    addr.status = DEPRECATED_OBJECT_STATUS
    cleared_fields = clear_address_ipam_link(addr)
    addr.save(update_fields=["status", *cleared_fields])
    return True, None


def _fix_status_mismatch(addr_pk: int, builder_config: dict[str, Any]) -> tuple[bool, str | None]:
    addr_model, _ = _address_model_and_cot()
    if addr_model is None:
        return False, "nsm_address Custom Object Type not found."

    addr = addr_model.objects.filter(pk=addr_pk).first()
    if addr is None:
        return False, f"Address object {addr_pk} not found."

    ipam_key = ipam_key_for_address(addr)
    if ipam_key is None:
        return False, f"Address {addr_pk} has no IPAM link."

    ipam_obj = _ipam_obj_for_key(ipam_key)
    if ipam_obj is None:
        return False, f"IPAM object for address {addr_pk} not found."

    status_map = builder_config.get("status_map") or {}
    expected_status = map_status(getattr(ipam_obj, "status", None), status_map)
    actual_status = getattr(addr, "status", None)
    if actual_status is not None and str(actual_status) == expected_status:
        return False, None

    addr.status = expected_status
    addr.save(update_fields=["status"])
    return True, None


def _parse_sync_fix_token(token: str) -> tuple[str, tuple] | None:
    if token.startswith("name_drift:"):
        parts = token.split(":", 2)
        if len(parts) == 3 and parts[1] in {"rename", "replace"}:
            try:
                return f"name_drift_{parts[1]}", (int(parts[2]),)
            except ValueError:
                return None
        if len(parts) == 2:
            try:
                return "name_drift_rename", (int(parts[1]),)
            except ValueError:
                return None
        return None
    if token.startswith("status_mismatch:"):
        try:
            return "status_mismatch", (int(token.split(":", 1)[1]),)
        except ValueError:
            return None
    if token.startswith("missing:"):
        parts = token.split(":", 2)
        if len(parts) != 3:
            return None
        source_key, pk_text = parts[1], parts[2]
        try:
            return "missing", (source_key, int(pk_text))
        except ValueError:
            return None
    return None


@transaction.atomic
def apply_sync_fixes(
    tokens: Iterable[str],
    builder_config: dict[str, Any],
) -> SyncFixResult:
    """Apply one-click fixes for supported sync issue categories."""
    result = SyncFixResult()
    if not builder_config or not builder_config.get("enabled"):
        result.errors.append("Object Sync is not enabled.")
        return result

    seen: set[str] = set()
    for token in tokens:
        token = (token or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)

        parsed = _parse_sync_fix_token(token)
        if parsed is None:
            result.errors.append(f"Invalid fix token: {token}")
            result.skipped += 1
            continue

        kind, args = parsed
        if kind == "name_drift_rename":
            ok, error = _fix_name_drift(args[0], builder_config)
        elif kind == "name_drift_replace":
            ok, error = _fix_name_drift_replace(args[0], builder_config)
        elif kind == "status_mismatch":
            ok, error = _fix_status_mismatch(args[0], builder_config)
        elif kind == "missing":
            create_result = create_addresses([args], builder_config)
            ok = create_result.created > 0
            error = None
            if create_result.errors:
                error = create_result.errors[0]
            elif create_result.skipped and not ok:
                error = None
        else:
            result.skipped += 1
            continue

        if error:
            result.errors.append(error)
            result.skipped += 1
        elif ok:
            result.fixed += 1
        else:
            result.skipped += 1

    return result


def build_preview_rows(
    builder_config: dict[str, Any],
    *,
    source_keys: Iterable[str] | None = None,
    addr_index: dict[IpamKey, list] | None = None,
) -> list[BuildPreviewRow]:
    if not builder_config.get("enabled"):
        return []

    status_map = builder_config.get("status_map") or {}
    sources = builder_config.get("sources") or {}
    if addr_index is None:
        addr_model, _ = _address_model_and_cot()
        addr_index = (
            index_addresses_by_ipam_key(addr_model.objects.all())
            if addr_model is not None
            else {}
        )

    rows: list[BuildPreviewRow] = []
    for source_key, ipam_obj in _iter_ipam_objects(source_keys):
        ipam_status = getattr(ipam_obj, "status", None)
        if not is_buildable_ipam_status(ipam_status, status_map):
            continue

        ipam_key = ipam_key_for_ipam_obj(ipam_obj)
        source_def = sources.get(source_key) or {}
        generated_name = render_ipam_object_name(
            ipam_obj, source_key, builder_config=builder_config
        )
        target_status = map_status(ipam_status, status_map)
        description = ""
        if source_def.get("copy_description"):
            description = getattr(ipam_obj, "description", "") or ""

        linked = addr_index.get(ipam_key, [])
        can_create = not linked
        skip_reason = None
        if linked:
            skip_reason = "already_linked"

        rows.append(
            BuildPreviewRow(
                source_key=source_key,
                ipam_obj=ipam_obj,
                ipam_key=ipam_key,
                generated_name=generated_name,
                target_status=target_status,
                description=description,
                can_create=can_create,
                skip_reason=skip_reason,
            )
        )
    return rows


@transaction.atomic
def create_addresses(
    selected: Iterable[tuple[str, int]],
    builder_config: dict[str, Any],
) -> BuildResult:
    """Create ``nsm_address`` rows for ``(source_key, ipam_pk)`` selections."""
    result = BuildResult()
    addr_model, _cot = _address_model_and_cot()
    if addr_model is None:
        result.errors.append("nsm_address Custom Object Type not found.")
        return result

    addr_index = index_addresses_by_ipam_key(addr_model.objects.all())
    status_map = builder_config.get("status_map") or {}
    sources = builder_config.get("sources") or {}

    for source_key, ipam_pk in selected:
        model = _model_for_source(source_key)
        if model is None:
            result.errors.append(f"Unknown source: {source_key}")
            result.skipped += 1
            continue
        ipam_obj = model.objects.filter(pk=ipam_pk).first()
        if ipam_obj is None:
            result.errors.append(f"IPAM object not found: {source_key}:{ipam_pk}")
            result.skipped += 1
            continue

        if not is_buildable_ipam_status(getattr(ipam_obj, "status", None), status_map):
            result.skipped += 1
            continue

        ipam_key = ipam_key_for_ipam_obj(ipam_obj)
        if addr_index.get(ipam_key):
            result.skipped += 1
            continue

        source_def = sources.get(source_key) or {}
        name = render_ipam_object_name(
            ipam_obj, source_key, builder_config=builder_config
        )
        if not name:
            result.errors.append(f"Empty name for {source_key}:{ipam_pk}")
            result.skipped += 1
            continue

        kwargs: dict[str, Any] = {
            "name": name,
            "status": map_status(getattr(ipam_obj, "status", None), status_map),
            **ipam_polymorphic_kwargs(ipam_obj),
        }
        if source_def.get("copy_description"):
            desc = getattr(ipam_obj, "description", "") or ""
            if desc:
                kwargs["description"] = desc

        addr_model.objects.create(**kwargs)
        addr_index.setdefault(ipam_key, []).append(True)
        result.created += 1

    return result
