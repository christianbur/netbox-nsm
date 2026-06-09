"""Setup script: TypeConfigs für NSM Custom Object Types anlegen."""
from django.contrib.contenttypes.models import ContentType
from netbox_nsm.models import TypeConfig, MatchingClassChoices

# ── 1. ContentTypes ermitteln ──────────────────────────────────────────────


def get_ct_safe(app, model):
    try:
        return ContentType.objects.get(app_label=app, model=model)
    except ContentType.DoesNotExist:
        return None


def find_custom_ct_by_label(label_lower):
    """Sucht ContentType anhand des verbose_name (lowercase, ohne Through-Modelle)."""
    for ct in ContentType.objects.filter(app_label="netbox_custom_objects"):
        if ct.model.startswith("through_"):
            continue
        mc = ct.model_class()
        if mc and mc._meta.verbose_name.lower() == label_lower:
            return ct
        if label_lower in ct.model.lower():
            return ct
    return None


# ── 2. TypeConfigs anlegen ─────────────────────────────────────────────────

TYPE_DEFS = [
    (lambda: find_custom_ct_by_label("zones"), "zone", "Z:{name}", ["source", "destination"]),
    (lambda: find_custom_ct_by_label("labels"), "label", "L:{name}", ["source", "destination"]),
    (lambda: find_custom_ct_by_label("addresses"), "address", "Addr:{name}", ["source", "destination"]),
    (lambda: find_custom_ct_by_label("services"), "service", "S:{name}", ["services"]),
    (lambda: find_custom_ct_by_label("action"), "action", "A:{name}", ["action"]),
    (lambda: find_custom_ct_by_label("business apps"), "info", "{name}", ["info"]),
    (lambda: find_custom_ct_by_label("network apps"), "application", "{name}", ["services"]),
    (lambda: get_ct_safe("ipam", "iprange"), "address", "R:{name}", ["source", "destination"]),
    (lambda: get_ct_safe("ipam", "prefix"), "address", "P:{name}", ["source"]),
]

tc_map = {}

for resolver, mc, tpl, placements in TYPE_DEFS:
    ct = resolver()
    if ct is None:
        print(f"  SKIP: ContentType not found for template={tpl!r}")
        continue
    tc, created = TypeConfig.objects.get_or_create(
        content_type=ct,
        defaults=dict(
            matching_class=mc,
            display_template=tpl,
            panel_slugs=placements,
        ),
    )
    if not created:
        tc.matching_class = mc
        tc.display_template = tpl
        tc.panel_slugs = placements
        tc.save()
    tc_map[ct.pk] = tc
    print(f"  {'NEW' if created else 'UPD'} TypeConfig [{mc:10s}]: {tc}")

print(f"\nTypeConfigs gesamt: {TypeConfig.objects.count()}")
