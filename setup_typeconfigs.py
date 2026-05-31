"""Setup script: TypeConfigs + RulebookFields für alle bestehenden Rulebooks anlegen."""
from django.contrib.contenttypes.models import ContentType
from netbox_nsm.models import (
    TypeConfig, MatchingClassChoices,
    RulebookField, RulebookFieldType,
    SecurityPolicyRulebook,
)

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
        # Fallback: model-Name enthält Label
        if label_lower in ct.model.lower():
            return ct
    return None


# ── 2. TypeConfigs anlegen ─────────────────────────────────────────────────

TYPE_DEFS = [
    # (ct_resolver, matching_class, display_template, allowed_placements)
    (lambda: find_custom_ct_by_label("zones"),    "zone",    "Z:{name}",    ["source", "destination"]),
    (lambda: find_custom_ct_by_label("labels"),   "label",   "L:{name}",    ["source", "destination"]),
    (lambda: find_custom_ct_by_label("addresses"),"address", "Addr:{name}", ["source", "destination"]),
    (lambda: find_custom_ct_by_label("services"), "service", "S:{name}",    ["fixed"]),
    (lambda: find_custom_ct_by_label("action"),   "action", "A:{name}",    ["fixed"]),
    (lambda: get_ct_safe("ipam", "iprange"),  "address", "R:{name}", ["source", "destination"]),
    (lambda: get_ct_safe("ipam", "prefix"),   "address", "P:{name}", ["source"]),
]

tc_map = {}  # ct.pk → TypeConfig

for resolver, mc, tpl, placements in TYPE_DEFS:
    ct = resolver()
    if ct is None:
        print(f"  SKIP: ContentType not found for template={tpl!r}")
        continue
    tc, created = TypeConfig.objects.get_or_create(
        content_type=ct,
        defaults=dict(matching_class=mc, display_template=tpl, allowed_placements=placements),
    )
    if not created:
        tc.matching_class = mc
        tc.display_template = tpl
        tc.allowed_placements = placements
        tc.save()
    tc_map[ct.pk] = tc
    print(f"  {'NEW' if created else 'UPD'} TypeConfig [{mc:10s}]: {tc}")

print(f"\nTypeConfigs gesamt: {TypeConfig.objects.count()}")

# ── 3. RulebookFields + RulebookFieldTypes anlegen ─────────────────────────

# Standard-Felder für alle bestehenden Rulebooks:
#  source (placement=source):      Zones, Labels, Addresses, IP Range, Prefix
#  destination (placement=destination): Zones, Labels, Addresses, IP Range
#  service (placement=fixed):      Services
#  action (placement=fixed):       Action

ZONE_ONLY = [
    lambda: find_custom_ct_by_label("zones"),
]
SOURCE_CTS = [
    lambda: find_custom_ct_by_label("zones"),
    lambda: find_custom_ct_by_label("labels"),
    lambda: find_custom_ct_by_label("addresses"),
    lambda: get_ct_safe("ipam", "iprange"),
    lambda: get_ct_safe("ipam", "prefix"),
]
DEST_CTS = [
    lambda: find_custom_ct_by_label("zones"),
    lambda: find_custom_ct_by_label("labels"),
    lambda: find_custom_ct_by_label("addresses"),
    lambda: get_ct_safe("ipam", "iprange"),
]

DEFAULT_FIELD_DEFS = [
    # (slug, name, placement, sort_order, [ct_resolvers])
    ("source",      "Source",      "source",      10,  SOURCE_CTS),
    ("destination", "Destination", "destination", 20,  DEST_CTS),
    ("service",     "Service",     "fixed",       30,  [lambda: find_custom_ct_by_label("services")]),
    ("action",      "Action",      "fixed",       40,  [lambda: find_custom_ct_by_label("action")]),
]

# Per-Rulebook-Overrides: Abweichungen vom Default
# Schlüssel: Rulebook-Name; Wert: vollständige FIELD_DEFS-Liste für dieses Rulebook
RULEBOOK_FIELD_OVERRIDES = {
    "rb-matrix": [
        # Zonen-Matrix: Source/Destination = nur Zones (kein Label, Adressen usw.)
        ("source",      "Source",      "source",      10,  ZONE_ONLY),
        ("destination", "Destination", "destination", 20,  ZONE_ONLY),
        ("service",     "Service",     "fixed",       30,  [lambda: find_custom_ct_by_label("services")]),
        ("action",      "Action",      "fixed",       40,  [lambda: find_custom_ct_by_label("action")]),
    ],
}

for rulebook in SecurityPolicyRulebook.objects.all():
    print(f"\n  Rulebook: {rulebook.name!r}")
    field_defs = RULEBOOK_FIELD_OVERRIDES.get(rulebook.name, DEFAULT_FIELD_DEFS)
    for slug, name, placement, sort_order, ct_resolvers in field_defs:
        field, f_created = RulebookField.objects.get_or_create(
            rulebook=rulebook,
            slug=slug,
            defaults=dict(name=name, placement=placement, sort_order=sort_order),
        )
        if not f_created:
            field.name = name
            field.placement = placement
            field.sort_order = sort_order
            field.save()
        print(f"    {'NEW' if f_created else 'UPD'} Field: {field.slug!r} ({placement})")

        for i, resolver in enumerate(ct_resolvers):
            ct = resolver()
            if ct is None or ct.pk not in tc_map:
                continue
            tc = tc_map[ct.pk]
            ft, ft_created = RulebookFieldType.objects.get_or_create(
                field=field,
                type_config=tc,
                defaults=dict(sort_order=(i + 1) * 10),
            )
            print(f"      {'NEW' if ft_created else 'exists'} FieldType: {tc}")

print(f"\nRulebookField gesamt: {RulebookField.objects.count()}")
print(f"RulebookFieldType gesamt: {RulebookFieldType.objects.count()}")
