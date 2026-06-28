"""Aggregated daily object report for NSM address objects (scale-safe).

Design goals
------------
* **All analysis in Python**, reusable from REST/scripts (``build_object_report``).
* **Aggregated, not materialized** — works with > 1,000,000 objects:
    - duplicate / multi-group checks run as pure DB ``annotate``/``aggregate``
      (no N+1, no per-object Python loop over the full table),
    - the status check streams the address table with ``.iterator()`` in chunks,
      resolving IPAM statuses in bounded ``pk__in`` batches,
    - every check stores only counts + grouped breakdowns + a capped list of
      detail *samples* (``DEFAULT_SAMPLE_LIMIT``).

Checks implemented
------------------
a. ``status_mismatch`` — NSM address ``status`` differs from the status mapped
   from its linked IPAM object (via the default IPAM status map).
b. ``ipam_duplicates`` — more than one NSM address object points at the same
   IPAM resource (same ``address_content_type`` + ``address_object_id``).
c. ``ipam_orphans`` — NSM address objects with no IPAM reference at all
   (excluding intentional literal-network objects such as ``0.0.0.0/0``).
d. ``multi_group`` — an NSM address belongs to more than one address group.
e. ``empty_groups`` — address groups with no members.
f. ``single_member_groups`` — address groups that wrap exactly one member.
g. ``similar_groups`` — address groups with overlapping membership (duplicate /
   redundancy detection between ``nsm_address_group`` objects).
h. ``deprecated`` — listing/counts of deprecated NSM objects.

This module only *reads* existing helpers (``ipam_status``,
``ipam_status``) and never mutates policy data.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.utils import timezone
from django.utils.translation import gettext as _

from netbox_nsm.addresses.ipam_status import (
    BUILDER_IGNORE_STATUS,
    DEFAULT_IPAM_STATUS_MAP,
    DEPRECATED_OBJECT_STATUS,
    map_ipam_status,
)

__all__ = (
    "OBJECT_REPORT_CHECK_KEYS",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_SAMPLE_LIMIT",
    "SAMPLE_PAGE_SIZE",
    "build_object_report",
    "localize_object_report",
    "prepare_object_report_check_rows",
)

# Number of detail samples persisted per check (bounded, scale-safe). This is
# the upper bound a single run stores in ``Job.data`` regardless of how many
# objects exist, so the viewer can page through them client-side without
# re-running any analysis or loading millions of rows.
DEFAULT_SAMPLE_LIMIT = 500
# Page size used by the client-side sample paginator in the report viewer.
SAMPLE_PAGE_SIZE = 50
DEFAULT_CHUNK_SIZE = 5000

OBJECT_REPORT_CHECK_KEYS = (
    "status_mismatch",
    "ipam_duplicates",
    "ipam_orphans",
    "multi_group",
    "empty_groups",
    "single_member_groups",
    "similar_groups",
    "deprecated",
)

# Similar address-group thresholds (see ``_groups_are_similar``).
SIMILAR_GROUP_MIN_MEMBERS = 3
SIMILAR_GROUP_SMALL_MAX_MEMBERS = 4
SIMILAR_GROUP_SMALL_OVERLAP = 3
SIMILAR_GROUP_MIN_RATIO = 0.75

# IPAM source content types we audit, keyed by NetBox app_label/model.
_IPAM_MODELS = (
    ("ipam", "ipaddress"),
    ("ipam", "prefix"),
    ("ipam", "iprange"),
)


# --------------------------------------------------------------------------- #
# COT model / field resolution (read-only)
# --------------------------------------------------------------------------- #
def _cot_for_slug(slugs):
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return None
    for slug in slugs:
        cot = CustomObjectType.objects.filter(slug=slug).first()
        if cot is not None:
            return cot
    return None


def _address_cot():
    return _cot_for_slug(("nsm_address", "nsm_addresses"))


def _group_cot():
    return _cot_for_slug(("nsm_address_group", "nsm_address_groups"))


def _group_membership_through(group_cot):
    """Return ``(ThroughModel, group_field, member_field)`` for the group M2M.

    The member field on ``nsm_address_group`` (slug ``group``) is a
    ``multiobject`` field whose through table stores one FK to the group
    (source) and one FK to the member address (target). Field names are
    resolved dynamically because the table name is data-driven
    (``Through_custom_objects_<n>_group``).
    """
    if group_cot is None:
        return None, None, None
    try:
        from django.apps import apps
        from netbox_custom_objects import constants

        field = group_cot.fields.get(name="group")
        through = apps.get_model(constants.APP_LABEL, field.through_model_name)
    except Exception:
        return None, None, None

    group_model = group_cot.get_model()
    group_field = member_field = None
    for fk in through._meta.concrete_fields:
        related = getattr(fk, "related_model", None)
        if related is None:
            continue
        if related is group_model:
            group_field = fk.name
        else:
            member_field = fk.name
    if not group_field or not member_field:
        return None, None, None
    return through, group_field, member_field


def _builder_status_map():
    """Return the hardcoded IPAM→NSM status map for report checks."""
    return dict(DEFAULT_IPAM_STATUS_MAP), False


def _ipam_ct_ids():
    """Map ``content_type_id`` → ``model`` for the audited IPAM source types."""
    result = {}
    for app_label, model in _IPAM_MODELS:
        ct = ContentType.objects.filter(app_label=app_label, model=model).first()
        if ct is not None:
            result[ct.pk] = ct
    return result


def _safe_url(obj):
    getter = getattr(obj, "get_absolute_url", None)
    if not callable(getter):
        return ""
    try:
        return getter() or ""
    except Exception:
        return ""


def _sample(name, *, pk=None, url="", extra=None):
    entry = {"name": str(name), "pk": pk, "url": url or ""}
    if extra:
        entry.update(extra)
    return entry


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
def _check_status_mismatch(addr_model, *, status_map, explicit, sample_limit, chunk_size):
    """Compare NSM address status with the status mapped from its IPAM object."""
    ct_map = _ipam_ct_ids()
    pair_counts: dict[tuple[str, str], int] = {}
    orphan_count = 0
    ignored_count = 0
    checked = 0
    mismatch_total = 0
    samples: list[dict] = []

    for ct_id, ct in ct_map.items():
        ipam_model = ct.model_class()
        if ipam_model is None:
            continue
        qs = (
            addr_model.objects.filter(address_content_type_id=ct_id)
            .exclude(address_object_id__isnull=True)
            .values("id", "name", "status", "address_object_id")
        )
        chunk: list[dict] = []

        def _flush(rows):
            nonlocal orphan_count, ignored_count, checked, mismatch_total
            if not rows:
                return
            ids = {r["address_object_id"] for r in rows}
            ipam_status = dict(
                ipam_model.objects.filter(pk__in=ids).values_list("pk", "status")
            )
            for r in rows:
                ipam_pk = r["address_object_id"]
                if ipam_pk not in ipam_status:
                    orphan_count += 1
                    continue
                expected = map_ipam_status(ipam_status[ipam_pk], status_map)
                if expected == BUILDER_IGNORE_STATUS:
                    ignored_count += 1
                    continue
                checked += 1
                actual = str(r["status"] or "")
                if actual != expected:
                    mismatch_total += 1
                    key = (expected, actual)
                    pair_counts[key] = pair_counts.get(key, 0) + 1
                    if len(samples) < sample_limit:
                        samples.append(
                            _sample(
                                r["name"],
                                pk=r["id"],
                                extra={
                                    "expected": expected,
                                    "actual": actual,
                                    "ipam_type": ct.model,
                                },
                            )
                        )

        for row in qs.iterator(chunk_size=chunk_size):
            chunk.append(row)
            if len(chunk) >= chunk_size:
                _flush(chunk)
                chunk = []
        _flush(chunk)

    groups = [
        {
            "expected": expected,
            "actual": actual,
            "count": count,
            "label": f"{actual or '∅'} → {expected}",  # localized at display time
        }
        for (expected, actual), count in sorted(
            pair_counts.items(), key=lambda kv: kv[1], reverse=True
        )
    ]
    return {
        "enabled": True,
        "explicit_config": explicit,
        "count": mismatch_total,
        "checked": checked,
        "ignored": ignored_count,
        "orphans": orphan_count,
        "groups": groups,
        "samples": samples,
        "title": "IPAM status ≠ address status",
    }


def _check_ipam_duplicates(addr_model, *, sample_limit):
    """Find IPAM resources referenced by more than one NSM address object."""
    dupes = (
        addr_model.objects.exclude(address_object_id__isnull=True)
        .exclude(address_content_type_id__isnull=True)
        .values("address_content_type_id", "address_object_id")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
    )

    ct_cache: dict[int, ContentType | None] = {}

    def _ct(ct_id):
        if ct_id not in ct_cache:
            ct_cache[ct_id] = ContentType.objects.filter(pk=ct_id).first()
        return ct_cache[ct_id]

    by_type: dict[str, int] = {}
    duplicate_keys = 0
    excess_objects = 0
    samples: list[dict] = []

    for row in dupes.iterator(chunk_size=DEFAULT_CHUNK_SIZE):
        duplicate_keys += 1
        excess_objects += row["c"] - 1
        ct_id = row["address_content_type_id"]
        ct = _ct(ct_id)
        label = ct.model if ct else str(ct_id)
        by_type[label] = by_type.get(label, 0) + 1
        if len(samples) < sample_limit:
            ipam_obj = None
            mc = ct.model_class() if ct else None
            if mc is not None:
                ipam_obj = mc.objects.filter(pk=row["address_object_id"]).first()
            samples.append(
                _sample(
                    str(ipam_obj) if ipam_obj else f"{label}:{row['address_object_id']}",
                    url=_safe_url(ipam_obj) if ipam_obj else "",
                    extra={"ipam_type": label, "address_count": row["c"]},
                )
            )

    groups = [
        {"label": label, "count": count}
        for label, count in sorted(by_type.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return {
        "enabled": True,
        "count": duplicate_keys,
        "excess_objects": excess_objects,
        "groups": groups,
        "samples": samples,
        "title": "Multiple address objects per IPAM resource",
    }


def _member_identity_key(*, addr_pk, address_content_type_id=None, address_object_id=None):
    """Comparable membership token (IPAM ct+pk when linked, else address pk)."""
    if address_content_type_id and address_object_id:
        return ("ipam", int(address_content_type_id), int(address_object_id))
    return ("addr", int(addr_pk))


def _groups_are_similar(size_a: int, size_b: int, overlap: int) -> bool:
    """Return whether two address groups should be reported as similar.

    Rules (both groups must have at least ``SIMILAR_GROUP_MIN_MEMBERS`` members):

    * **Small groups (3–4 members each):** report when at least
      ``SIMILAR_GROUP_SMALL_OVERLAP`` members are shared.
    * **General:** report when ``overlap / min(size) >= SIMILAR_GROUP_MIN_RATIO``
      (equivalent to Jaccard-style overlap on the smaller set).

    Scaling note: candidate pairs are discovered via an inverted member index
    (member → groups), so work is proportional to shared membership edges, not a
    full ``O(n²)`` scan over all groups. With ~500 groups a brute-force pair loop
    would still be cheap; the index keeps the check viable as group counts grow.
    """
    if size_a < SIMILAR_GROUP_MIN_MEMBERS or size_b < SIMILAR_GROUP_MIN_MEMBERS:
        return False
    if overlap < SIMILAR_GROUP_SMALL_OVERLAP:
        return False
    if (
        size_a <= SIMILAR_GROUP_SMALL_MAX_MEMBERS
        and size_b <= SIMILAR_GROUP_SMALL_MAX_MEMBERS
    ):
        return True
    min_size = min(size_a, size_b)
    return overlap / min_size >= SIMILAR_GROUP_MIN_RATIO


def _similarity_score(size_a: int, size_b: int, overlap: int) -> float:
    union = size_a + size_b - overlap
    if union <= 0:
        return 0.0
    return round(overlap / union, 4)


def _overlap_ratio(size_a: int, size_b: int, overlap: int) -> float:
    min_size = min(size_a, size_b)
    if min_size <= 0:
        return 0.0
    return round(overlap / min_size, 4)


def _score_bucket_label(score: float) -> str:
    if score >= 0.9:
        return "≥ 90%"
    if score >= 0.75:
        return "75–89%"
    return "50–74%"


def _check_similar_groups(group_cot, addr_model, *, sample_limit):
    """Find pairs of address groups with highly overlapping membership."""
    through, group_field, member_field = _group_membership_through(group_cot)
    if through is None or group_cot is None:
        return {
            "enabled": False,
            "count": 0,
            "groups": [],
            "samples": [],
            "note": "Address group membership (COT field 'group') could not be resolved.",
            "title": "Similar address groups",
        }

    group_model = group_cot.get_model()
    member_rows = list(
        through.objects.values_list(group_field, member_field).iterator(
            chunk_size=DEFAULT_CHUNK_SIZE
        )
    )
    if not member_rows:
        return {
            "enabled": True,
            "count": 0,
            "checked_groups": 0,
            "groups": [],
            "samples": [],
            "title": "Similar address groups",
        }

    member_pks = {member_pk for _, member_pk in member_rows}
    identity_by_addr_pk: dict[int, tuple] = {}
    for row in addr_model.objects.filter(pk__in=member_pks).values(
        "pk", "address_content_type_id", "address_object_id"
    ):
        identity_by_addr_pk[row["pk"]] = _member_identity_key(
            addr_pk=row["pk"],
            address_content_type_id=row.get("address_content_type_id"),
            address_object_id=row.get("address_object_id"),
        )

    group_members: dict[int, set[tuple]] = defaultdict(set)
    for group_pk, member_pk in member_rows:
        identity = identity_by_addr_pk.get(member_pk)
        if identity is None:
            identity = ("addr", int(member_pk))
        group_members[int(group_pk)].add(identity)

    eligible = {
        pk: members
        for pk, members in group_members.items()
        if len(members) >= SIMILAR_GROUP_MIN_MEMBERS
    }
    if len(eligible) < 2:
        return {
            "enabled": True,
            "count": 0,
            "checked_groups": len(eligible),
            "groups": [],
            "samples": [],
            "title": "Similar address groups",
        }

    member_index: dict[tuple, list[int]] = defaultdict(list)
    for group_pk, members in eligible.items():
        for identity in members:
            member_index[identity].append(group_pk)

    pairs: list[dict[str, Any]] = []
    seen_pairs: set[tuple[int, int]] = set()
    for group_pk, members in eligible.items():
        candidates: set[int] = set()
        for identity in members:
            for other_pk in member_index[identity]:
                if other_pk != group_pk:
                    candidates.add(other_pk)
        size_a = len(members)
        for other_pk in candidates:
            pair_key = (group_pk, other_pk) if group_pk < other_pk else (other_pk, group_pk)
            if pair_key in seen_pairs:
                continue
            other_members = eligible.get(other_pk)
            if other_members is None:
                continue
            overlap = len(members & other_members)
            size_b = len(other_members)
            if not _groups_are_similar(size_a, size_b, overlap):
                continue
            seen_pairs.add(pair_key)
            pair_size_a = len(eligible[pair_key[0]])
            pair_size_b = len(eligible[pair_key[1]])
            score = _similarity_score(pair_size_a, pair_size_b, overlap)
            pairs.append(
                {
                    "group_a_pk": pair_key[0],
                    "group_b_pk": pair_key[1],
                    "overlap": overlap,
                    "size_a": pair_size_a,
                    "size_b": pair_size_b,
                    "overlap_ratio": _overlap_ratio(pair_size_a, pair_size_b, overlap),
                    "score": score,
                    "bucket": _score_bucket_label(score),
                }
            )

    pairs.sort(key=lambda p: (-p["score"], -p["overlap"], p["group_a_pk"], p["group_b_pk"]))

    bucket_counts: dict[str, int] = defaultdict(int)
    for pair in pairs:
        bucket_counts[pair["bucket"]] += 1
    bucket_order = ("≥ 90%", "75–89%", "50–74%")
    groups = [
        {"label": label, "count": bucket_counts[label]}
        for label in bucket_order
        if bucket_counts.get(label)
    ]

    # Only the sampled pairs need name/URL resolution — resolving every paired
    # group would load objects that are never displayed.
    sampled_pairs = pairs[:sample_limit]
    group_pks = {
        pk for pair in sampled_pairs for pk in (pair["group_a_pk"], pair["group_b_pk"])
    }
    names: dict[int, str] = {}
    urls: dict[int, str] = {}
    if group_pks:
        for row in group_model.objects.filter(pk__in=group_pks).values("id", "name"):
            names[row["id"]] = row["name"]
        for obj in group_model.objects.filter(pk__in=group_pks):
            urls[obj.pk] = _safe_url(obj)

    samples: list[dict] = []
    for pair in sampled_pairs:
        a_pk, b_pk = pair["group_a_pk"], pair["group_b_pk"]
        a_name = names.get(a_pk, f"#{a_pk}")
        b_name = names.get(b_pk, f"#{b_pk}")
        samples.append(
            _sample(
                f"{a_name} ↔ {b_name}",
                extra={
                    "group_a": a_name,
                    "group_b": b_name,
                    "group_a_url": urls.get(a_pk, ""),
                    "group_b_url": urls.get(b_pk, ""),
                    "overlap": pair["overlap"],
                    "overlap_ratio": pair["overlap_ratio"],
                    "overlap_pct": int(round(pair["overlap_ratio"] * 100)),
                    "score": pair["score"],
                    "size_a": pair["size_a"],
                    "size_b": pair["size_b"],
                },
            )
        )

    return {
        "enabled": True,
        "count": len(pairs),
        "checked_groups": len(eligible),
        "groups": groups,
        "samples": samples,
        "title": "Similar address groups",
    }


def _check_multi_group(group_cot, *, sample_limit):
    """Find NSM addresses that are members of more than one address group."""
    through, group_field, member_field = _group_membership_through(group_cot)
    if through is None:
        return {
            "enabled": False,
            "count": 0,
            "groups": [],
            "samples": [],
            "note": "Address group membership (COT field 'group') could not be resolved.",
            "title": "Address objects in multiple groups",
        }

    multi = (
        through.objects.values(member_field)
        .annotate(c=Count(group_field, distinct=True))
        .filter(c__gt=1)
    )

    member_model = None
    try:
        member_model = through._meta.get_field(member_field).related_model
    except Exception:
        member_model = None

    bucket: dict[int, int] = {}
    total = 0
    samples: list[dict] = []
    sample_ids: list[tuple[int, int]] = []

    for row in multi.iterator(chunk_size=DEFAULT_CHUNK_SIZE):
        total += 1
        n = row["c"]
        bucket[n] = bucket.get(n, 0) + 1
        if len(sample_ids) < sample_limit:
            sample_ids.append((row[member_field], n))

    if sample_ids and member_model is not None:
        sample_pks = [pk for pk, _ in sample_ids]
        names = dict(
            member_model.objects.filter(pk__in=sample_pks).values_list("pk", "name")
        )
        # Resolve sample objects once (single query) to build absolute URLs,
        # instead of a per-sample ``.first()`` lookup (N+1).
        objs = {obj.pk: obj for obj in member_model.objects.filter(pk__in=sample_pks)}
        for pk, n in sample_ids:
            obj = objs.get(pk)
            samples.append(
                _sample(
                    names.get(pk, f"#{pk}"),
                    pk=pk,
                    url=_safe_url(obj) if obj else "",
                    extra={"group_count": n},
                )
            )

    groups = [
        {"label": f"in {n} groups", "count": count, "group_count": n}
        for n, count in sorted(bucket.items())
    ]
    return {
        "enabled": True,
        "count": total,
        "groups": groups,
        "samples": samples,
        "title": "Address objects in multiple groups",
    }


def _check_deprecated(addr_model, group_cot, *, sample_limit):
    """List/count deprecated NSM address and group objects."""
    status = DEPRECATED_OBJECT_STATUS
    addr_qs = addr_model.objects.filter(status=status)
    addr_count = addr_qs.count()

    group_count = 0
    group_qs = None
    if group_cot is not None:
        group_model = group_cot.get_model()
        group_qs = group_model.objects.filter(status=status)
        group_count = group_qs.count()

    samples: list[dict] = []
    for row in addr_qs.values("id", "name").order_by("name")[:sample_limit]:
        samples.append(_sample(row["name"], pk=row["id"], extra={"kind": "address"}))
    remaining = sample_limit - len(samples)
    if group_qs is not None and remaining > 0:
        for row in group_qs.values("id", "name").order_by("name")[:remaining]:
            samples.append(_sample(row["name"], pk=row["id"], extra={"kind": "group"}))

    groups = []
    if addr_count:
        groups.append({"label": "Addresses", "count": addr_count})
    if group_count:
        groups.append({"label": "Groups", "count": group_count})
    return {
        "enabled": True,
        "count": addr_count + group_count,
        "address_count": addr_count,
        "group_count": group_count,
        "groups": groups,
        "samples": samples,
        "title": "Deprecated objects",
    }


def _check_ipam_orphans(addr_model, *, sample_limit, chunk_size):
    """Find NSM address objects that have no IPAM reference at all.

    Literal-network objects (e.g. ``0.0.0.0/0`` stored as ``nsm_config`` in
    ``comments``) intentionally have no IPAM link and are **not** orphans; they
    are counted separately and skipped.

    Candidates are only the rows whose polymorphic IPAM link is empty, so the
    iterated set is the (normally small) non-IPAM-linked tail of the table, not
    the full address table.
    """
    from types import SimpleNamespace

    from netbox_nsm.addresses.address_literal import get_network_literal

    candidates = (
        addr_model.objects.filter(address_object_id__isnull=True)
        .values("id", "name", "comments")
        .order_by("name")
    )

    orphan_count = 0
    literal_skipped = 0
    samples: list[dict] = []
    for row in candidates.iterator(chunk_size=chunk_size):
        literal = get_network_literal(SimpleNamespace(comments=row.get("comments")))
        if literal:
            literal_skipped += 1
            continue
        orphan_count += 1
        if len(samples) < sample_limit:
            samples.append(
                _sample(row["name"], pk=row["id"], extra={"kind": "address"})
            )

    return {
        "enabled": True,
        "count": orphan_count,
        "literal_skipped": literal_skipped,
        "groups": [],
        "samples": samples,
        "title": "Address objects without IPAM reference",
    }


def _check_empty_groups(group_cot, *, sample_limit):
    """Find address groups that have no members."""
    through, group_field, member_field = _group_membership_through(group_cot)
    if through is None or group_cot is None:
        return {
            "enabled": False,
            "count": 0,
            "groups": [],
            "samples": [],
            "note": "Address group membership (COT field 'group') could not be resolved.",
            "title": "Empty address groups",
        }

    group_model = group_cot.get_model()
    populated_ids = set(
        through.objects.values_list(group_field, flat=True).distinct()
    )

    empty_count = 0
    samples: list[dict] = []
    for row in group_model.objects.values("id", "name").order_by("name").iterator(
        chunk_size=DEFAULT_CHUNK_SIZE
    ):
        if row["id"] in populated_ids:
            continue
        empty_count += 1
        if len(samples) < sample_limit:
            samples.append(
                _sample(row["name"], pk=row["id"], extra={"kind": "group"})
            )

    return {
        "enabled": True,
        "count": empty_count,
        "groups": [],
        "samples": samples,
        "title": "Empty address groups",
    }


def _check_single_member_groups(group_cot, *, sample_limit):
    """Find address groups that contain exactly one member."""
    through, group_field, member_field = _group_membership_through(group_cot)
    if through is None or group_cot is None:
        return {
            "enabled": False,
            "count": 0,
            "groups": [],
            "samples": [],
            "note": "Address group membership (COT field 'group') could not be resolved.",
            "title": "Address groups with a single member",
        }

    group_model = group_cot.get_model()
    singles = (
        through.objects.values(group_field)
        .annotate(c=Count(member_field, distinct=True))
        .filter(c=1)
    )

    total = 0
    sample_ids: list[int] = []
    for row in singles.iterator(chunk_size=DEFAULT_CHUNK_SIZE):
        total += 1
        if len(sample_ids) < sample_limit:
            sample_ids.append(row[group_field])

    samples: list[dict] = []
    if sample_ids:
        names = dict(
            group_model.objects.filter(pk__in=sample_ids).values_list("pk", "name")
        )
        objs = {obj.pk: obj for obj in group_model.objects.filter(pk__in=sample_ids)}
        for pk in sample_ids:
            obj = objs.get(pk)
            samples.append(
                _sample(
                    names.get(pk, f"#{pk}"),
                    pk=pk,
                    url=_safe_url(obj) if obj else "",
                    extra={"kind": "group"},
                )
            )

    return {
        "enabled": True,
        "count": total,
        "groups": [],
        "samples": samples,
        "title": "Address groups with a single member",
    }


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def build_object_report(
    *,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict[str, Any]:
    """Build the aggregated object report as a JSON-serializable dict.

    Safe to call from a scheduled job, the REST/script layer, or a management
    command. Never mutates data.
    """
    started = time.monotonic()
    from netbox_nsm.version import __version__

    addr_cot = _address_cot()
    group_cot = _group_cot()

    if addr_cot is None:
        return {
            "generated_at": timezone.now().isoformat(),
            "version": __version__,
            "available": False,
            "message": "Custom Object Type 'nsm_address' is not deployed.",
            "totals": {},
            "checks": {},
        }

    addr_model = addr_cot.get_model()
    status_map, explicit = _builder_status_map()

    totals = {
        "addresses": addr_model.objects.count(),
        "ipam_linked": addr_model.objects.exclude(
            address_object_id__isnull=True
        ).count(),
        "groups": group_cot.get_model().objects.count() if group_cot else 0,
    }

    checks = {
        "status_mismatch": _check_status_mismatch(
            addr_model,
            status_map=status_map,
            explicit=explicit,
            sample_limit=sample_limit,
            chunk_size=chunk_size,
        ),
        "ipam_duplicates": _check_ipam_duplicates(
            addr_model, sample_limit=sample_limit
        ),
        "ipam_orphans": _check_ipam_orphans(
            addr_model, sample_limit=sample_limit, chunk_size=chunk_size
        ),
        "multi_group": _check_multi_group(group_cot, sample_limit=sample_limit),
        "empty_groups": _check_empty_groups(group_cot, sample_limit=sample_limit),
        "single_member_groups": _check_single_member_groups(
            group_cot, sample_limit=sample_limit
        ),
        "similar_groups": _check_similar_groups(
            group_cot, addr_model, sample_limit=sample_limit
        ),
        "deprecated": _check_deprecated(
            addr_model, group_cot, sample_limit=sample_limit
        ),
    }

    findings_total = sum(c.get("count", 0) for c in checks.values())

    return {
        "generated_at": timezone.now().isoformat(),
        "version": __version__,
        "available": True,
        "duration_s": round(time.monotonic() - started, 3),
        "sample_limit": sample_limit,
        "findings_total": findings_total,
        "totals": totals,
        "checks": checks,
    }


# --------------------------------------------------------------------------- #
# Display-time localization (persisted Job.data stores English msgids)
# --------------------------------------------------------------------------- #
_LEGACY_CHECK_TITLES = {
    "IPAM-Status ≠ Address-Status": "IPAM status ≠ address status",
    "Mehrere Address-Objekte je IPAM-Ressource": "Multiple address objects per IPAM resource",
    "Address-Objekte in mehreren Gruppen": "Address objects in multiple groups",
    "Ähnliche Address-Gruppen": "Similar address groups",
    "Deprecated Objekte": "Deprecated objects",
}

_LEGACY_CHECK_NOTES = {
    "Address-Group-Mitgliedschaft (COT-Feld 'group') nicht auflösbar.": (
        "Address group membership (COT field 'group') could not be resolved."
    ),
}

_LEGACY_MESSAGES = {
    "Custom Object Type 'nsm_address' ist nicht deployed.": (
        "Custom Object Type 'nsm_address' is not deployed."
    ),
}

_LEGACY_GROUP_LABELS = {
    "Adressen": "Addresses",
    "Gruppen": "Groups",
}


def _normalize_msgid(text: str, legacy: dict[str, str]) -> str:
    return legacy.get(text, text)


def _localize_group_label(check_key: str, group: dict[str, Any]) -> str:
    g = dict(group)
    if check_key == "status_mismatch":
        expected = g.get("expected", "")
        actual = g.get("actual", "")
        return _("%(actual)s → %(expected)s") % {
            "actual": actual or "∅",
            "expected": expected,
        }
    if check_key == "multi_group":
        n = g.get("group_count")
        if n is not None:
            return _("in %(n)s groups") % {"n": n}
    if check_key == "similar_groups":
        label = g.get("label", "")
        if label:
            return _(label)
    label = g.get("label", "")
    if label:
        label = _normalize_msgid(label, _LEGACY_GROUP_LABELS)
        return _(label)
    return label


def _localize_samples(samples: list[dict]) -> list[dict]:
    localized = []
    for sample in samples:
        entry = dict(sample)
        kind = entry.get("kind")
        if kind in ("address", "group"):
            entry["kind"] = _(kind)
        localized.append(entry)
    return localized


def _localize_check(check_key: str, data: dict[str, Any]) -> dict[str, Any]:
    localized = dict(data)
    title = localized.get("title")
    if title:
        localized["title"] = _(_normalize_msgid(title, _LEGACY_CHECK_TITLES))
    note = localized.get("note")
    if note:
        localized["note"] = _(_normalize_msgid(note, _LEGACY_CHECK_NOTES))
    groups = localized.get("groups")
    if groups:
        localized["groups"] = [
            {**g, "label": _localize_group_label(check_key, g)} for g in groups
        ]
    samples = localized.get("samples")
    if samples:
        localized["samples"] = _localize_samples(samples)
    return localized


def localize_object_report(report: dict[str, Any] | None) -> dict[str, Any] | None:
    """Translate user-facing strings in a stored object report for the active locale."""
    if not report:
        return report
    localized = dict(report)
    message = localized.get("message")
    if message:
        localized["message"] = _(_normalize_msgid(message, _LEGACY_MESSAGES))
    checks = localized.get("checks")
    if checks:
        localized["checks"] = {
            key: _localize_check(key, data) for key, data in checks.items()
        }
    return localized


def prepare_object_report_check_rows(
    checks: dict[str, Any] | None,
    *,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
) -> list[dict[str, Any]]:
    """Build display rows for the object report checks table."""
    if not checks:
        return []

    rows: list[dict[str, Any]] = []
    for key in OBJECT_REPORT_CHECK_KEYS:
        data = checks.get(key)
        if data is None:
            continue

        enabled = bool(data.get("enabled", True))
        count = int(data.get("count") or 0)
        samples = list(data.get("samples") or [])

        if not enabled:
            status = "disabled"
            status_label = _("n/a")
        elif count == 0:
            status = "ok"
            status_label = _("OK")
        else:
            status = "findings"
            status_label = _("Findings")

        details: list[str] = []
        if not enabled:
            note = data.get("note")
            if note:
                details.append(str(note))
        elif count == 0:
            if key == "status_mismatch" and not data.get("explicit_config"):
                details.append(
                    _("Using default status map (Object Builder not configured).")
                )
            elif key == "similar_groups":
                checked = data.get("checked_groups")
                if checked is not None:
                    details.append(
                        _("%(n)s groups with ≥ %(min)s members checked")
                        % {"n": checked, "min": SIMILAR_GROUP_MIN_MEMBERS}
                    )
            elif key == "ipam_orphans":
                skipped = data.get("literal_skipped")
                if skipped:
                    details.append(
                        _("%(n)s literal-network object(s) excluded") % {"n": skipped}
                    )
        else:
            if key == "status_mismatch":
                details.append(
                    _(
                        "%(checked)s checked · %(ignored)s ignored · "
                        "%(orphans)s without IPAM object"
                    )
                    % {
                        "checked": data.get("checked", 0),
                        "ignored": data.get("ignored", 0),
                        "orphans": data.get("orphans", 0),
                    }
                )
            elif key == "ipam_duplicates":
                excess = data.get("excess_objects")
                if excess:
                    details.append(
                        _("%(ex)s excess address object(s) overall") % {"ex": excess}
                    )
            elif key == "ipam_orphans":
                skipped = data.get("literal_skipped")
                if skipped:
                    details.append(
                        _("%(n)s literal-network object(s) excluded") % {"n": skipped}
                    )
            elif key == "similar_groups":
                checked = data.get("checked_groups")
                if checked is not None:
                    details.append(
                        _("%(n)s groups with ≥ %(min)s members checked")
                        % {"n": checked, "min": SIMILAR_GROUP_MIN_MEMBERS}
                    )

        rows.append(
            {
                "key": key,
                "title": data.get("title", key),
                "count": count,
                "enabled": enabled,
                "status": status,
                "status_label": status_label,
                "details": details,
                "groups": list(data.get("groups") or []),
                "samples": samples,
                "sample_limit": sample_limit,
                "sample_page_size": SAMPLE_PAGE_SIZE,
                "has_samples": bool(enabled and count and samples),
            }
        )

    return rows
