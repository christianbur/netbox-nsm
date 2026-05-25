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
    "SecurityZonePolicyRulebook",
    "SecurityZonePolicyRule",
    "SecurityZonePolicyRulebookAssignment",
    "SecurityZonePolicyRulebookIndex",
)


class RulebookTypeChoices(models.TextChoices):
    MATRIX = "matrix", _("Security Matrix")
    POLICY = "policy", _("Security Rules")


class SecurityZonePolicyRulebook(ContactsMixin, PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    rulebook_type = models.CharField(
        max_length=20,
        choices=RulebookTypeChoices.choices,
        default=RulebookTypeChoices.POLICY,
    )

    class Meta:
        verbose_name = _("Security Policy")
        verbose_name_plural = _("Security Policies")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securityzonepolicyrulebook", args=[self.pk])


class SecurityZonePolicyRule(ContactsMixin, PrimaryModel):
    rulebook = models.ForeignKey(
        to="netbox_nsm.SecurityZonePolicyRulebook",
        related_name="rules",
        on_delete=models.CASCADE,
    )
    index = models.PositiveIntegerField(default=100)
    enabled = models.BooleanField(default=True)
    name = models.CharField(max_length=100)
    source_zones = models.ManyToManyField(
        to="netbox_nsm.SecurityZone",
        blank=True,
        related_name="%(class)s_source_zones",
    )
    source_users = models.ManyToManyField(
        to=User,
        blank=True,
        related_name="%(class)s_source_users",
    )
    destination_zones = models.ManyToManyField(
        to="netbox_nsm.SecurityZone",
        blank=True,
        related_name="%(class)s_destination_zones",
    )
    destination_users = models.ManyToManyField(
        to=User,
        blank=True,
        related_name="%(class)s_destination_users",
    )
    services = models.ManyToManyField(
        to="netbox_nsm.ApplicationItem",
        blank=True,
        related_name="%(class)s_services",
    )
    applications = models.ManyToManyField(
        to="netbox_nsm.Application",
        blank=True,
        related_name="%(class)s_applications",
    )
    application_sets = models.ManyToManyField(
        to="netbox_nsm.ApplicationSet",
        blank=True,
        related_name="%(class)s_application_sets",
    )
    log_enabled = models.BooleanField(default=False)
    policy_action = models.CharField(
        max_length=20,
        choices=ActionChoices,
        default=ActionChoices.PERMIT,
    )
    custom_srcdst_objects = models.ManyToManyField(
        to="netbox_nsm.ObjectCustomObject",
        blank=True,
        related_name="%(class)s_custom_srcdst",
        limit_choices_to={"custom_type__area": "srcdst"},
    )
    custom_service_objects = models.ManyToManyField(
        to="netbox_nsm.ObjectCustomObject",
        blank=True,
        related_name="%(class)s_custom_services",
        limit_choices_to={"custom_type__area": "services"},
    )
    custom_action_objects = models.ManyToManyField(
        to="netbox_nsm.ObjectCustomObject",
        blank=True,
        related_name="%(class)s_custom_action",
        limit_choices_to={"custom_type__area": "action"},
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
        return reverse("plugins:netbox_nsm:securityzonepolicyrule", args=[self.pk])


class SecurityZonePolicyRulebookAssignment(NetBoxModel):
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
        to="netbox_nsm.SecurityZonePolicyRulebook",
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
class SecurityZonePolicyRulebookIndex(SearchIndex):
    model = SecurityZonePolicyRulebook
    fields = (
        ("name", 100),
        ("description", 500),
    )


GenericRelation(
    to=SecurityZonePolicyRulebookAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="device",
).contribute_to_class(Device, "security_zone_rulebooks")

GenericRelation(
    to=SecurityZonePolicyRulebookAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualdevicecontext",
).contribute_to_class(VirtualDeviceContext, "security_zone_rulebooks")

GenericRelation(
    to=SecurityZonePolicyRulebookAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualmachine",
).contribute_to_class(VirtualMachine, "security_zone_rulebooks")
