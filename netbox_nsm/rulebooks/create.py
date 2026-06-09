"""Create deployed COT rulebooks from bundled templates."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from netbox_nsm.objects.custom_objects_schema import slugify_identifier
from netbox_nsm.rulebooks.templates import (
    build_rulebook_document,
    format_rulebook_display_name,
    is_deployed_rulebook_slug,
    normalize_rulebook_display_name,
)

__all__ = (
    "create_cot_rulebook_from_template",
    "format_rulebook_display_name",
    "normalize_rulebook_display_name",
    "resolve_rulebook_slug",
    "update_cot_rulebook_metadata",
)


def resolve_rulebook_slug(name: str) -> str:
    suffix = slugify_identifier(name)
    if not suffix or suffix == "x":
        raise ValidationError(_("Enter a valid rulebook name."))
    slug = f"nsm_rb_{suffix}"
    if not is_deployed_rulebook_slug(slug):
        raise ValidationError(_("Invalid rulebook slug."))
    return slug


def update_cot_rulebook_metadata(
    slug: str,
    *,
    verbose_name: str,
    description: str = "",
):
    from netbox_custom_objects.models import CustomObjectType

    cot = CustomObjectType.objects.filter(slug=slug).first()
    if cot is None:
        raise ValidationError(_("Rulebook not found."))
    display_name = normalize_rulebook_display_name(verbose_name)
    cot.verbose_name = display_name
    cot.verbose_name_plural = display_name
    cot.description = (description or "").strip()
    cot.save(update_fields=["verbose_name", "verbose_name_plural", "description"])
    return cot


def create_cot_rulebook_from_template(
    *,
    template_slug: str,
    name: str,
    verbose_name: str | None = None,
    description: str | None = None,
    parent_slug: str | None = None,
):
    from netbox_custom_objects.models import CustomObjectType
    from netbox_custom_objects.schema.executor import apply_document
    from netbox_nsm.rulebooks.cot_hierarchy import set_cot_rulebook_parent, validate_cot_parent_slug

    slug = resolve_rulebook_slug(name)
    parent_slug = (parent_slug or "").strip() or None
    error = validate_cot_parent_slug(slug, parent_slug)
    if error:
        raise ValidationError(error)

    if CustomObjectType.objects.filter(slug=slug).exists():
        raise ValidationError(
            _("A rulebook with slug %(slug)s already exists.") % {"slug": slug}
        )

    display_name = (verbose_name or format_rulebook_display_name(name)).strip()
    document = build_rulebook_document(
        template_slug=template_slug,
        rulebook_slug=slug,
        verbose_name=display_name,
        description=description,
    )
    apply_document(document, allow_destructive=False)
    set_cot_rulebook_parent(slug, parent_slug)
    cot = CustomObjectType.objects.get(slug=slug)
    from netbox_nsm.rulebooks.rulebook_groups import sync_rulebook_field_groups

    sync_rulebook_field_groups(cot)
    return cot
