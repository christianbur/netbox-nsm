from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, Platform, VirtualDeviceContext
from netbox.models import BaseModel, ChangeLoggedModel, NetBoxModel, PrimaryModel
from netbox.models.features import ChangeLoggingMixin
from netbox.models.features import ContactsMixin
from netbox.search import SearchIndex, register_search
from virtualization.models import VirtualMachine
from users.models import User

from netbox_nsm.constants import RULESET_ASSIGNMENT_MODELS

__all__ = (
    "RulebookTypeChoices",
    "RulebookStatusChoices",
    "RulebookFacetMode",
    "Rulebook",
    "RulebookField",
    "RulebookFieldType",
    "RulebookFieldKind",
    "Rule",
    "RuleObjectItem",
    "RuleGroupItem",
    "RulebookAssignment",
    "RulebookIndex",
)


class RulebookTypeChoices(models.TextChoices):
    SECURITY_RULES = "security_rules", _("Security Rules")


class RulebookStatusChoices(models.TextChoices):
    ACTIVE = "active", _("Active")
    DEPRECATED = "deprecated", _("Deprecated")
    RESERVED = "reserved", _("Reserved")
    CONTAINER = "container", _("Container")


class RulebookFacetMode(models.TextChoices):
    VALUE = "value", _("Pro Wert")
    SET = "set", _("Pro Kombination")
    DISABLED = "disabled", _("Disabled")


class Rulebook(ContactsMixin, PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    rulebook_type = models.CharField(
        max_length=20,
        choices=RulebookTypeChoices.choices,
        default=RulebookTypeChoices.SECURITY_RULES,
    )
    status = models.CharField(
        max_length=20,
        choices=RulebookStatusChoices.choices,
        default=RulebookStatusChoices.ACTIVE,
        verbose_name=_("Status"),
    )
    rule_comment_template = models.TextField(
        blank=True,
        default="",
        help_text=_(
            "Markdown comment template pre-filled when adding new rules. "
            "Supports {rule_name}, {index}, {rulebook}."
        ),
    )
    platform = models.ForeignKey(
        to=Platform,
        on_delete=models.SET_NULL,
        related_name="nsm_rulebooks",
        blank=True,
        null=True,
        verbose_name=_("Platform"),
        help_text=_(
            "Firewall platform or security fabric (e.g. PAN-OS, Cisco ASA, TrustSec, Zscaler)."
        ),
    )
    mgmt_url = models.URLField(
        blank=True,
        default="",
        verbose_name=_("Management URL"),
        help_text=_(
            "Link to the management interface of the associated firewall or device."
        ),
    )
    parent = models.ForeignKey(
        to="self",
        on_delete=models.SET_NULL,
        related_name="children",
        blank=True,
        null=True,
        verbose_name=_("Parent rulebook"),
        help_text=_("Optional parent rulebook for hierarchical grouping."),
    )

    class Meta:
        verbose_name = _("Rulebook")
        verbose_name_plural = _("Rulebooks")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:rulebook", args=[self.pk])

    def get_rules_tab_url(self):
        return reverse("plugins:netbox_nsm:rulebook_rules", args=[self.pk])

    def hierarchy_depth(self) -> int:
        from netbox_nsm.rulebook_hierarchy import hierarchy_depth

        return hierarchy_depth(self)

    @property
    def matching_classes(self) -> set:
        return {
            ftc.type_config.matching_class
            for field in self.fields.prefetch_related("type_configs__type_config")
            for ftc in field.type_configs.all()
            if ftc.type_config.matching_class
        }

    def serialize_object(self, exclude=None):
        data = super().serialize_object(exclude=exclude)
        if self.pk:
            from netbox_nsm.rulebook_field_utils import serialize_rulebook_fields_layout
            from netbox_nsm.rulebook_rules_utils import serialize_rulebook_rules_layout

            data["fields_layout"] = serialize_rulebook_fields_layout(self)
            data["rules_layout"] = serialize_rulebook_rules_layout(self)
        return data


class _FieldPlacementChoices(models.TextChoices):
    SOURCE = "source", _("Source")
    DESTINATION = "destination", _("Destination")
    FIXED = "fixed", _("Fixed")
    SYSTEM = "system", _("System")


class RulebookFieldKind(models.TextChoices):
    OBJECT = "object", _("Object")
    SYSTEM = "system", _("System")


class RulebookField(ChangeLoggedModel):
    """A field (column) in a Rulebook's rule editor."""

    rulebook = models.ForeignKey(
        to="netbox_nsm.Rulebook",
        on_delete=models.CASCADE,
        related_name="fields",
        verbose_name=_("Rulebook"),
    )
    slug = models.SlugField(
        max_length=50,
        verbose_name=_("Slug"),
        help_text=_(
            "Internal identifier (e.g. 'source', 'destination', 'services'). "
            "Unique within the Rulebook."
        ),
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_("Name"),
        help_text=_("Display name shown in the rule editor and policy table."),
    )
    sort_order = models.PositiveIntegerField(
        default=100,
        verbose_name=_("Sort Order"),
        help_text=_("Order in which this field appears (lower comes first)."),
    )
    placement = models.CharField(
        max_length=20,
        choices=_FieldPlacementChoices.choices,
        default=_FieldPlacementChoices.SOURCE,
        verbose_name=_("Placement"),
        help_text=_("Traffic direction for this field."),
    )
    field_kind = models.CharField(
        max_length=10,
        choices=RulebookFieldKind.choices,
        default=RulebookFieldKind.OBJECT,
        verbose_name=_("Field Kind"),
        help_text=_(
            "Object fields hold security objects; system fields are built-in "
            "rule columns (Index, Status, Name, Description)."
        ),
    )
    visible = models.BooleanField(
        default=True,
        verbose_name=_("Visible"),
        help_text=_("Show this field as a column in the policy table."),
    )
    searchable = models.BooleanField(
        default=True,
        verbose_name=_("Searchable"),
        help_text=_("Include this field in query searches."),
    )
    filterable = models.BooleanField(
        default=True,
        verbose_name=_("Filterable"),
        help_text=_("Allow filtering on this field."),
    )
    facet_mode = models.CharField(
        max_length=10,
        choices=RulebookFacetMode.choices,
        default=RulebookFacetMode.VALUE,
        verbose_name=_("Facet Mode"),
        help_text=_(
            "Pro Wert: jeder Wert zählt einzeln. Pro Kombination: Wertekombinationen zählen gemeinsam. "
            "Deaktiviert: Feld nicht in der Facetten-Leiste anzeigen."
        ),
    )
    facet_weight = models.PositiveIntegerField(
        default=100,
        verbose_name=_("Facet Weight"),
        help_text=_("Facets with higher weight appear first."),
    )
    max_visible_pills = models.PositiveIntegerField(
        default=5,
        verbose_name=_("Max Visible Pills"),
        help_text=_(
            "Maximum number of object pills shown per table cell in the policy view. "
            "Additional values appear behind a +X control."
        ),
    )
    show_colored_pills = models.BooleanField(
        default=True,
        verbose_name=_("Show colored pills"),
        help_text=_(
            "Display object links as colored bubbles in the policy table. "
            "Disable to show plain text pills without background color."
        ),
    )

    class Meta:
        unique_together = (("rulebook", "slug"),)
        ordering = ("rulebook", "sort_order", "slug")
        verbose_name = _("Rulebook Field")
        verbose_name_plural = _("Rulebook Fields")

    def __str__(self):
        return f"{self.rulebook} / {self.name}"

    @property
    def is_system_field(self):
        return self.field_kind == RulebookFieldKind.SYSTEM

    @property
    def is_facetable(self):
        return self.facet_mode != RulebookFacetMode.DISABLED

    @property
    def has_subfield_types(self):
        return self.type_configs.exists()

    @property
    def is_container_field(self):
        """Object field that groups one or more sub-types (TypeConfig rows)."""
        return not self.is_system_field and self.has_subfield_types

    @property
    def shows_field_level_facets(self):
        return self.is_facetable and not self.has_subfield_types

    @property
    def display(self):
        return str(self)

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:rulebook", args=[self.rulebook_id])


class RulebookFieldType(ChangeLoggedModel):
    field = models.ForeignKey(
        to="netbox_nsm.RulebookField",
        on_delete=models.CASCADE,
        related_name="type_configs",
        verbose_name=_("Field"),
    )
    type_config = models.ForeignKey(
        to="netbox_nsm.TypeConfig",
        on_delete=models.CASCADE,
        related_name="rulebook_field_types",
        verbose_name=_("Type Config"),
    )
    sort_order = models.PositiveIntegerField(
        default=100,
        verbose_name=_("Sort Order"),
        help_text=_("Order in which this type appears within the field."),
    )
    max_items = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Max Items"),
        help_text=_(
            "Maximum number of objects of this type per rule. Leave empty for unlimited."
        ),
    )
    name_filter_regex = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Name filter (regex)"),
        help_text=_(
            "Optional Python regex on object name in the rule picker (e.g. ^prod- or Env-Prod). "
            "Empty = show all objects of this type."
        ),
    )
    visible = models.BooleanField(
        default=True,
        verbose_name=_("Visible"),
        help_text=_("Show this type as a column in the policy table."),
    )
    facet_mode = models.CharField(
        max_length=10,
        choices=RulebookFacetMode.choices,
        default=RulebookFacetMode.VALUE,
        verbose_name=_("Facet Mode"),
        help_text=_(
            "Anzeige in der Facetten-Leiste der Policy-Ansicht. "
            "Pro Wert zählt jeden Wert einzeln; Pro Kombination zählt Wertekombinationen."
        ),
    )

    class Meta:
        unique_together = (("field", "type_config"),)
        ordering = ("field", "sort_order")
        verbose_name = _("Rulebook Field Type")
        verbose_name_plural = _("Rulebook Field Types")

    def __str__(self):
        return f"{self.field} / {self.type_config}"

    @property
    def display(self):
        return str(self)

    @property
    def is_facetable(self):
        return self.facet_mode != RulebookFacetMode.DISABLED

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:rulebook", args=[self.field.rulebook_id])


class Rule(ContactsMixin, PrimaryModel):
    rulebook = models.ForeignKey(
        to="netbox_nsm.Rulebook",
        related_name="rules",
        on_delete=models.CASCADE,
    )
    index = models.PositiveIntegerField(default=100)
    enabled = models.BooleanField(default=True)
    name = models.CharField(max_length=100)
    source_users = models.ManyToManyField(
        to=User,
        blank=True,
        related_name="%(class)s_source_users",
    )
    destination_users = models.ManyToManyField(
        to=User,
        blank=True,
        related_name="%(class)s_destination_users",
    )
    log_enabled = models.BooleanField(default=False)
    virtual_group_config = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Security Rule")
        verbose_name_plural = _("Security Rules")
        ordering = ("rulebook", "index", "name")
        constraints = (
            models.UniqueConstraint(
                fields=("rulebook", "name"),
                name="%(app_label)s_%(class)s_unique_rulebook_name",
            ),
        )

    def __str__(self):
        return f"{self.rulebook}: {self.name}"

    def action_display(self) -> str:
        """Comma-separated labels from action object/group assignments."""
        names: list[str] = []
        for item in self.object_items.select_related("field").all():
            if item.field and item.field.slug == "action":
                obj = item.assigned_object
                if obj is not None:
                    names.append(str(getattr(obj, "name", obj)))
        for item in self.group_items.select_related("field", "security_group").all():
            if item.field and item.field.slug == "action" and item.security_group_id:
                names.append(str(item.security_group.name))
        return ", ".join(names)

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:rule", args=[self.pk])

    def get_rules_grid_filter_url(self):
        """Rules tab (AG Grid) with name filter pre-applied."""
        from urllib.parse import quote

        if not self.rulebook_id:
            return self.get_absolute_url()
        escaped = self.name.replace("\\", "\\\\").replace('"', '\\"')
        q = f'name == "{escaped}"'
        base = reverse("plugins:netbox_nsm:rulebook_rules", args=[self.rulebook_id])
        return f"{base}?nsm_q={quote(q)}"

    def serialize_object(self, exclude=None):
        data = super().serialize_object(exclude=exclude)
        if self.pk:
            data["object_items"] = _serialize_rule_object_items(self)
            data["group_items"] = _serialize_rule_group_items(self)
        return data


def _object_item_changelog_key(field_slug, content_type_id, object_id):
    return f"{field_slug or ''}:ct_{content_type_id}:{object_id}"


def _group_item_changelog_key(field_slug, security_group_id):
    return f"{field_slug or ''}:grp_{security_group_id}"


def _serialize_rule_object_items(rule):
    items = {}
    for item in rule.object_items.select_related("field", "content_type"):
        field_slug = item.field.slug if item.field_id else ""
        key = _object_item_changelog_key(
            field_slug, item.content_type_id, item.object_id
        )
        items[key] = {
            "field": field_slug or None,
            "content_type": item.content_type_id,
            "object_id": item.object_id,
            "exclude": item.exclude,
        }
    return items


def _serialize_rule_group_items(rule):
    items = {}
    for item in rule.group_items.select_related("field", "security_group"):
        field_slug = item.field.slug if item.field_id else ""
        key = _group_item_changelog_key(field_slug, item.security_group_id)
        items[key] = {
            "field": field_slug or None,
            "security_group": item.security_group.name,
            "security_group_id": item.security_group_id,
            "exclude": item.exclude,
        }
    return items


class _NsmJunctionModel(ChangeLoggingMixin, BaseModel):
    """Branch-aware junction rows with changelog, without event rules."""

    class Meta:
        abstract = True


class RuleObjectItem(_NsmJunctionModel):
    rule = models.ForeignKey(
        to="netbox_nsm.Rule",
        on_delete=models.CASCADE,
        related_name="object_items",
    )
    field = models.ForeignKey(
        to="netbox_nsm.RulebookField",
        on_delete=models.PROTECT,
        related_name="rule_object_items",
        null=True,
        blank=True,
        verbose_name=_("Field"),
    )
    content_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
        related_name="nsm_rule_items",
        verbose_name=_("Objekttyp"),
    )
    object_id = models.PositiveBigIntegerField(verbose_name=_("Objekt-ID"))
    assigned_object = GenericForeignKey("content_type", "object_id")
    exclude = models.BooleanField(
        default=False,
        verbose_name=_("Exclude"),
        help_text=_(
            "If set, this object is excluded from the field (EXCEPT semantics)."
        ),
    )

    class Meta:
        unique_together = (("rule", "field", "content_type", "object_id"),)
        indexes = (models.Index(fields=("content_type", "object_id")),)
        ordering = (
            "field__sort_order",
            "field__slug",
            "object_id",
        )
        verbose_name = _("Rule Object Item")
        verbose_name_plural = _("Rule Object Items")

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.field_id and self.content_type_id:
            try:
                ft = RulebookFieldType.objects.get(
                    field=self.field,
                    type_config__content_type_id=self.content_type_id,
                )
                if ft.max_items is not None:
                    existing = RuleObjectItem.objects.filter(
                        rule=self.rule,
                        field=self.field,
                        content_type_id=self.content_type_id,
                    )
                    if self.pk:
                        existing = existing.exclude(pk=self.pk)
                    if existing.count() >= ft.max_items:
                        raise ValidationError(
                            {
                                "field": _(
                                    "Dieser Typ erlaubt maximal %(max)d Objekt(e) pro Regel."
                                )
                                % {"max": ft.max_items}
                            }
                        )
            except RulebookFieldType.DoesNotExist:
                pass

    def __str__(self):
        return f"{self.rule} / {self.field} / {self.object_id}"

    @property
    def display(self):
        return str(self)

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:rule", args=[self.rule_id])


class RuleGroupItem(_NsmJunctionModel):
    rule = models.ForeignKey(
        to="netbox_nsm.Rule",
        on_delete=models.CASCADE,
        related_name="group_items",
    )
    field = models.ForeignKey(
        to="netbox_nsm.RulebookField",
        on_delete=models.PROTECT,
        related_name="rule_group_items",
        null=True,
        blank=True,
        verbose_name=_("Field"),
    )
    security_group = models.ForeignKey(
        to="netbox_nsm.ObjectGroup",
        on_delete=models.CASCADE,
        related_name="rule_group_items",
    )
    exclude = models.BooleanField(
        default=False,
        verbose_name=_("Exclude"),
        help_text=_(
            "If set, this group is excluded from the field (EXCEPT semantics)."
        ),
    )

    class Meta:
        unique_together = (("rule", "field", "security_group"),)
        ordering = (
            "field__sort_order",
            "field__slug",
            "security_group__name",
        )
        verbose_name = _("Rule Group Item")
        verbose_name_plural = _("Rule Group Items")

    def __str__(self):
        return f"{self.rule} / {self.field} / {self.security_group}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:rule", args=[self.rule_id])


class RulebookAssignment(NetBoxModel):
    assigned_object_type = models.ForeignKey(
        to=ContentType,
        limit_choices_to=RULESET_ASSIGNMENT_MODELS,
        on_delete=models.CASCADE,
    )
    assigned_object_id = models.PositiveBigIntegerField()
    assigned_object = GenericForeignKey(
        ct_field="assigned_object_type",
        fk_field="assigned_object_id",
    )
    rulebook = models.ForeignKey(
        to="netbox_nsm.Rulebook",
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    clone_fields = ("assigned_object_type", "assigned_object_id")

    class Meta:
        indexes = (models.Index(fields=("assigned_object_type", "assigned_object_id")),)
        constraints = (
            models.UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "rulebook"),
                name="%(app_label)s_%(class)s_unique_rulebook_assignment",
            ),
        )
        ordering = ("rulebook", "assigned_object_id")
        verbose_name = _("Rulebook Assignment")
        verbose_name_plural = _("Rulebook Assignments")

    def __str__(self):
        return f"{self.assigned_object}: {self.rulebook}"

    def get_absolute_url(self):
        if self.assigned_object:
            return self.assigned_object.get_absolute_url()
        return None


@register_search
class RulebookIndex(SearchIndex):
    model = Rulebook
    fields = (
        ("name", 100),
        ("description", 500),
    )


GenericRelation(
    to=RulebookAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="device",
).contribute_to_class(Device, "nsm_rulebooks")

GenericRelation(
    to=RulebookAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualdevicecontext",
).contribute_to_class(VirtualDeviceContext, "nsm_rulebooks")

GenericRelation(
    to=RulebookAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualmachine",
).contribute_to_class(VirtualMachine, "nsm_rulebooks")
