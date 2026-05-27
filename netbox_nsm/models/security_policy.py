from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, VirtualDeviceContext
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
    rule_comment_template = models.TextField(
        blank=True,
        default="",
        help_text=_(
            "Markdown comment template pre-filled when adding new rules. "
            "Supports {rule_name}, {index}, {rulebook}."
        ),
    )

    class Meta:
        verbose_name = _("Security Policy")
        verbose_name_plural = _("Security Policies")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[self.pk])


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


class _PlacementChoices(models.TextChoices):
    SOURCE = "source", _("Source")
    DESTINATION = "destination", _("Destination")
    FIXED = "fixed", _("Fixed")


class SecurityPolicyRuleObjectItem(models.Model):
    """Assigns a SecurityObject to a rule within a specific area and placement."""

    rule = models.ForeignKey(
        to="netbox_nsm.SecurityPolicyRule",
        on_delete=models.CASCADE,
        related_name="object_items",
    )
    area = models.ForeignKey(
        to="netbox_nsm.SecurityArea",
        on_delete=models.PROTECT,
        related_name="rule_object_items",
    )
    placement = models.CharField(max_length=20, choices=_PlacementChoices.choices)
    security_object = models.ForeignKey(
        to="netbox_nsm.SecurityObject",
        on_delete=models.CASCADE,
        related_name="rule_object_items",
    )

    class Meta:
        unique_together = (("rule", "area", "placement", "security_object"),)
        ordering = ("area__sort_order", "area__slug", "placement", "security_object__name")
        verbose_name = _("Rule Object Item")
        verbose_name_plural = _("Rule Object Items")

    def __str__(self):
        return f"{self.rule} / {self.area} / {self.placement} / {self.security_object}"


class SecurityPolicyRuleGroupItem(models.Model):
    """Assigns a SecurityObjectGroup to a rule within a specific area and placement."""

    rule = models.ForeignKey(
        to="netbox_nsm.SecurityPolicyRule",
        on_delete=models.CASCADE,
        related_name="group_items",
    )
    area = models.ForeignKey(
        to="netbox_nsm.SecurityArea",
        on_delete=models.PROTECT,
        related_name="rule_group_items",
    )
    placement = models.CharField(max_length=20, choices=_PlacementChoices.choices)
    security_group = models.ForeignKey(
        to="netbox_nsm.SecurityObjectGroup",
        on_delete=models.CASCADE,
        related_name="rule_group_items",
    )

    class Meta:
        unique_together = (("rule", "area", "placement", "security_group"),)
        ordering = ("area__sort_order", "area__slug", "placement", "security_group__name")
        verbose_name = _("Rule Group Item")
        verbose_name_plural = _("Rule Group Items")

    def __str__(self):
        return f"{self.rule} / {self.area} / {self.placement} / {self.security_group}"


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
        verbose_name = _("Security Zone Rulebook assignment")
        verbose_name_plural = _("Security Zone Rulebook assignments")

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
