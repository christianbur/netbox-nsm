"""Explicit netbox_branching DB routing for NSM junction / child models."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import TypeVar

from django.db import models, transaction

__all__ = (
    "branch_db_alias",
    "db_alias_for_instance",
    "detect_instance_db_alias",
    "resolve_db_alias",
    "branch_aware_manager",
    "branch_aware_related",
    "branch_save_instance",
    "ensure_branch_context",
    "pin_instance_db_alias",
    "junction_transaction",
    "router_write_alias",
    "router_write_alias",
    "required_junction_db_alias",
    "use_db_alias",
)

M = TypeVar("M", bound=models.Model)

_forced_db_alias: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "nsm_forced_db_alias", default=None
)


def branch_db_alias() -> str | None:
    """Return ``schema_<branch>`` when a branch is active (``active_branch`` context)."""
    try:
        from netbox_branching.contextvars import active_branch

        branch = active_branch.get()
        if branch:
            return f"schema_{branch.schema_name}"
    except ImportError:
        pass
    return None


def _branch_schema_alias(branch) -> str:
    return f"schema_{branch.schema_name}"


def _branch_from_request(request) -> object | None:
    if request is None:
        return None
    branch = getattr(request, "active_branch", None)
    if branch:
        return branch
    try:
        from netbox_branching.constants import COOKIE_NAME, QUERY_PARAM
        from netbox_branching.models import Branch

        schema_id = (
            request.GET.get(QUERY_PARAM)
            or request.POST.get("nsm_branch")
            or request.COOKIES.get(COOKIE_NAME)
        )
        if not schema_id:
            return None
        branch = Branch.objects.get(schema_id=schema_id)
        return branch if branch.ready else None
    except Exception:
        return None


def detect_instance_db_alias(instance) -> str | None:
    """
    Probe which DB alias actually stores *instance*.

    After ``PrimaryModelForm.save()`` a new Rule may exist only in a branch
    schema while ``instance._state.db`` still reads ``default``.
    """
    if instance is None:
        return None
    pk = getattr(instance, "pk", None)
    if not pk:
        return None

    model = instance.__class__
    in_default = model.objects.using("default").filter(pk=pk).exists()

    branch_aliases: list[str] = []
    try:
        from netbox_branching.models import Branch

        for branch in Branch.objects.all():
            if not branch.ready:
                continue
            alias = _branch_schema_alias(branch)
            if model.objects.using(alias).filter(pk=pk).exists():
                branch_aliases.append(alias)
    except ImportError:
        pass

    if len(branch_aliases) == 1 and not in_default:
        return branch_aliases[0]
    if in_default and not branch_aliases:
        return "default"
    if in_default and branch_aliases:
        return None
    if branch_aliases:
        return branch_aliases[0]
    return None


@contextmanager
def use_db_alias(alias: str | None):
    """Pin junction-table writes to *alias* for the duration of the block."""
    if not alias:
        yield None
        return
    token = _forced_db_alias.set(alias)
    try:
        yield alias
    finally:
        _forced_db_alias.reset(token)


def resolve_db_alias(
    instance=None, request=None, *, forced_alias: str | None = None
) -> str | None:
    """
    Resolve the PostgreSQL schema alias for junction-table writes.

    Order: forced alias → request branch → contextvar → instance state → DB probe.
    """
    if forced_alias:
        return forced_alias

    pinned = _forced_db_alias.get()
    if pinned:
        return pinned

    branch = _branch_from_request(request)
    if branch:
        return _branch_schema_alias(branch)

    alias = branch_db_alias()
    if alias:
        return alias

    if instance is not None:
        db = getattr(getattr(instance, "_state", None), "db", None)
        if db and str(db).startswith("schema_"):
            return str(db)

        detected = detect_instance_db_alias(instance)
        if detected:
            return detected

    return None


def db_alias_for_instance(instance=None, request=None) -> str | None:
    """Backward-compatible alias for :func:`resolve_db_alias`."""
    return resolve_db_alias(instance=instance, request=request)


def router_write_alias(model_class) -> str | None:
    """Same DB alias NetBox uses inside ``ObjectEditView.post()`` (``active_branch``)."""
    from django.db import router as django_router

    alias = django_router.db_for_write(model_class)
    return alias or None


def required_junction_db_alias(
    instance=None, request=None, *, hint: str | None = None
) -> str | None:
    """
    Resolve DB alias for junction writes.

    Prefer the branching router (``extras.taggeditem`` pattern), then explicit
    hints / request / DB probe when ``active_branch`` was cleared mid-save.
    """
    from netbox_nsm.models import RuleObjectItem

    if hint:
        return hint

    pinned = _forced_db_alias.get()
    if pinned:
        return pinned

    routed = router_write_alias(RuleObjectItem)
    if routed:
        return routed

    alias = resolve_db_alias(instance=instance, request=request)
    if alias:
        return alias

    if instance is not None and getattr(instance, "pk", None):
        detected = detect_instance_db_alias(instance)
        if detected:
            return detected

    return branch_db_alias()


def branch_aware_manager(
    model_class: type[M],
    instance=None,
    request=None,
    *,
    db_alias: str | None = None,
) -> models.Manager[M]:
    alias = db_alias or required_junction_db_alias(instance=instance, request=request)
    if not alias:
        raise RuntimeError(
            f"Cannot resolve branch DB alias for {model_class._meta.label}"
        )
    return model_class.objects.using(alias)


def branch_aware_related(
    related_manager,
    instance=None,
    request=None,
    *,
    db_alias: str | None = None,
):
    alias = db_alias or required_junction_db_alias(instance=instance, request=request)
    if not alias:
        raise RuntimeError("Cannot resolve branch DB alias for related manager")
    return related_manager.using(alias)


def pin_instance_db_alias(instance, request=None) -> None:
    """Keep ``instance._state.db`` aligned with the schema that holds the row."""
    alias = resolve_db_alias(instance=instance, request=request)
    if alias and instance is not None:
        instance._state.db = alias


def branch_save_instance(instance, request=None, **kwargs):
    """``save()`` on the same DB alias as *instance* (or the active branch)."""
    alias = resolve_db_alias(instance=instance, request=request)
    if alias:
        instance.save(using=alias, **kwargs)
        instance._state.db = alias
    else:
        instance.save(**kwargs)


@contextmanager
def junction_transaction(
    instance=None, request=None, *, forced_alias: str | None = None
):
    """Run junction-table writes on the same DB alias as the parent Rule."""
    alias = required_junction_db_alias(
        instance=instance, request=request, hint=forced_alias
    )
    if not alias:
        raise RuntimeError("Cannot write NSM junction tables without a branch DB alias")
    with transaction.atomic(using=alias):
        yield alias


@contextmanager
def ensure_branch_context(request=None):
    """Activate the branch from *request* for junction-table writes."""
    try:
        from netbox_branching.utilities import activate_branch
    except ImportError:
        yield
        return

    branch = _branch_from_request(request)
    if branch:
        with activate_branch(branch):
            yield
    else:
        yield
