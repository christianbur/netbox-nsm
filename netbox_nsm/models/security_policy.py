from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, Platform, VirtualDeviceContext
from netbox.models import NetBoxModel, PrimaryModel
from netbox.models.features import ContactsMixin
from netbox.search import SearchIndex, register_search
from virtualization.models import VirtualMachine
from users.models import User

from netbox_nsm.choices import ActionChoices
from netbox_nsm.constants import RULESET_ASSIGNMENT_MODELS

__all__ = (
    "RulebookTypeChoices",
    "SecurityPolicyRulebook",
    "RulebookField",
    "RulebookFieldType",
    "SecurityPolicyRule",
    "SecurityPolicyRuleObjectItem",
    "SecurityPolicyRuleGroupItem",
    "SecurityPolicyAssignment",
    "SecurityPolicyRulebookIndex",
)


class RulebookTypeChoices(models.TextChoices):
    POLICY = "policy", _("Security Rules")


class SecurityPolicyRulebook(ContactsMixin, PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    rulebook_type = models.CharField(
        max_length=20,
        choices=RulebookTypeChoices.choices,
        default=RulebookTypeChoices.POLICY,
    )
    platform = models.ForeignKey(
        to="dcim.Platform",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nsm_rulebooks",
        verbose_name=_("Platform"),
        help_text=_("Firewall platform or security fabric (e.g. PAN-OS, Cisco ASA, TrustSec, Zscaler)."),
    )
    mgmt_url = models.URLField(
        blank=True,
        default="",
        verbose_name=_("Management URL"),
        help_text=_("Link to the management interface of the associated firewall or device."),
    )
    rule_comment_template = models.TextField(
        blank=True,
        default="",
        help_text=_(
            "Markdown comment template pre-filled when adding new rules. "
            "Supports {rule_name}, {index}, {rulebook}."
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
        verbose_name = _("Rulebook")
        verbose_name_plural = _("Rulebooks")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[self.pk])

    @property
    def matching_classes(self) -> set:
        """Auto-derive matching strategy from all RulebookFieldType entries."""
        return {
            ftc.type_config.matching_class
            for field in self.fields.prefetch_related("type_configs__type_config")
            for ftc in field.type_configs.all()
            if ftc.type_config.matching_class
        }


class _FieldPlacementChoices(models.TextChoices):
    SOURCE = "source", _("Source")
    DESTINATION = "destination", _("Destination")
    FIXED = "fixed", _("Fixed")


class RulebookField(models.Model):
    """A field (column) in a Rulebook's rule editor, e.g. 'Source', 'Destination', 'Service'.

    Replaces the global SecurityArea model. Each Rulebook defines its own fields,
    allowing full flexibility across different vendors and use-cases.
    """

    rulebook = models.ForeignKey(
        to="netbox_nsm.SecurityPolicyRulebook",
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
    # ── Query / Facet metadata ─────────────────────────────────────────────
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
    facetable = models.BooleanField(
        default=False,
        verbose_name=_("Facetable"),
        help_text=_("Show this field in the facet navigation panel."),
    )
    facet_mode = models.CharField(
        max_length=10,
        choices=(("value", _("Value")), ("set", _("Set"))),
        default="value",
        verbose_name=_("Facet Mode"),
        help_text=_(
            "Value: count each individual value separately. "
            "Set: count the complete combination of values as one entry."
        ),
    )
    facet_weight = models.PositiveIntegerField(
        default=100,
        verbose_name=_("Facet Weight"),
        help_text=_("Facets with higher weight appear first."),
    )

    class Meta:
        unique_together = (("rulebook", "slug"),)
        ordering = ("rulebook", "sort_order", "slug")
        verbose_name = _("Rulebook Field")
        verbose_name_plural = _("Rulebook Fields")

    def __str__(self):
        return f"{self.rulebook} / {self.name}"

    @property
    def display(self):
        return str(self)


class RulebookFieldType(models.Model):
    """Associates a TypeConfig with a RulebookField.

    Defines which object types are allowed within a specific field of a Rulebook.
    """

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
    show_colored_pills = models.BooleanField(
        default=True,
        verbose_name=_("Show colored pills"),
        help_text=_(
            "Display objects of this type as colored pills (using the TypeConfig color). "
            "Disable to show plain pills without background color."
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


class SecurityPolicyRule(ContactsMixin, PrimaryModel):
    rulebook = models.ForeignKey(
        to="netbox_nsm.SecurityPolicyRulebook",
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
    policy_action = models.CharField(
        max_length=20,
        choices=ActionChoices,
        default=ActionChoices.PERMIT,
    )
    virtual_group_config = models.JSONField(
        blank=True,
        default=dict,
        verbose_name="Virtual Group Config",
        help_text=(
            "Stores virtual AND-group configuration per area. "
            "Format: {area_slug: [[id1,id2],[id3]]} — outer=OR, inner=AND."
        ),
    )

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

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securitypolicyrule", args=[self.pk])


class SecurityPolicyRuleObjectItem(models.Model):
    """Assigns any NetBox object to a rule within a specific RulebookField."""

    rule = models.ForeignKey(
        to="netbox_nsm.SecurityPolicyRule",
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
            # Bestimme den passenden RulebookFieldType für dieses Objekt
            from django.contrib.contenttypes.models import ContentType

            try:
                ft = RulebookFieldType.objects.get(
                    field=self.field,
                    type_config__content_type_id=self.content_type_id,
                )
                if ft.max_items is not None:
                    existing = SecurityPolicyRuleObjectItem.objects.filter(
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


class SecurityPolicyRuleGroupItem(models.Model):
    """Assigns a SecurityObjectGroup to a rule within a specific RulebookField."""

    rule = models.ForeignKey(
        to="netbox_nsm.SecurityPolicyRule",
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
        to="netbox_nsm.SecurityObjectGroup",
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


class SecurityPolicyAssignment(NetBoxModel):
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
        to="netbox_nsm.SecurityPolicyRulebook",
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
class SecurityPolicyRulebookIndex(SearchIndex):
    model = SecurityPolicyRulebook
    fields = (
        ("name", 100),
        ("description", 500),
    )


GenericRelation(
    to=SecurityPolicyAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="device",
).contribute_to_class(Device, "security_zone_rulebooks")

GenericRelation(
    to=SecurityPolicyAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualdevicecontext",
).contribute_to_class(VirtualDeviceContext, "security_zone_rulebooks")

GenericRelation(
    to=SecurityPolicyAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualmachine",
).contribute_to_class(VirtualMachine, "security_zone_rulebooks")
