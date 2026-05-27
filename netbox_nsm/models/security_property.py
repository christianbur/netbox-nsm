from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from extras.choices import CustomFieldTypeChoices
from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = (
    "SecurityPropertyType",
    "SecurityPropertyField",
    "SecurityProperty",
    "SecurityPropertyTypeIndex",
    "SecurityPropertyIndex",
)


class SecurityPropertyType(PrimaryModel):
    name = models.CharField(
        max_length=100,
        unique=True,
        validators=(
            RegexValidator(
                regex=r"^[a-z0-9]+(_[a-z0-9]+)*$",
                message=_(
                    "Only lowercase alphanumeric characters and underscores are allowed. "
                    "Names may not start or end with an underscore, and double underscores are not permitted."
                ),
            ),
        ),
    )
    verbose_name = models.CharField(max_length=100, blank=True)
    verbose_name_plural = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    group_name = models.CharField(max_length=100, db_index=True, blank=True)
    schema_document = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = _("NSM Object Type")
        verbose_name_plural = _("NSM Object Types")
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="netbox_nsm_securitypropertytype_name_ci_unique",
            )
        ]

    @property
    def display_name(self):
        return self.verbose_name or self.name.replace("_", " ").title()

    @property
    def display_name_plural(self):
        return self.verbose_name_plural or f"{self.display_name}s"

    def __str__(self):
        return self.display_name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securitypropertytype", args=[self.pk])


class SecurityPropertyField(PrimaryModel):
    security_property_type = models.ForeignKey(
        to="netbox_nsm.SecurityPropertyType",
        on_delete=models.CASCADE,
        related_name="fields",
    )
    name = models.CharField(
        max_length=50,
        validators=(
            RegexValidator(
                regex=r"^[a-z0-9]+(_[a-z0-9]+)*$",
                message=_(
                    "Only lowercase alphanumeric characters and underscores are allowed. "
                    "Names may not start or end with an underscore, and double underscores are not permitted."
                ),
            ),
        ),
    )
    label = models.CharField(max_length=50, blank=True)
    type = models.CharField(
        verbose_name=_("type"),
        max_length=50,
        choices=CustomFieldTypeChoices,
        default=CustomFieldTypeChoices.TYPE_TEXT,
    )
    group_name = models.CharField(max_length=50, blank=True)
    required = models.BooleanField(default=False)
    unique = models.BooleanField(default=False)
    default = models.JSONField(blank=True, null=True)
    weight = models.PositiveSmallIntegerField(default=100)

    class Meta:
        verbose_name = _("NSM Object Type Field")
        verbose_name_plural = _("NSM Object Type Fields")
        ordering = ("group_name", "weight", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("security_property_type", "name"),
                name="netbox_nsm_securitypropertyfield_unique_name",
            )
        ]

    def __str__(self):
        return self.label or self.name.replace("_", " ").capitalize()

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securitypropertyfield", args=[self.pk])


class SecurityProperty(PrimaryModel):
    security_property_type = models.ForeignKey(
        to="netbox_nsm.SecurityPropertyType",
        on_delete=models.CASCADE,
        related_name="security_propertys",
    )
    name = models.CharField(max_length=150)
    object_data = models.JSONField(default=dict, blank=True)
    source_model = models.CharField(max_length=64, blank=True)
    source_pk = models.PositiveBigIntegerField(blank=True, null=True)

    class Meta:
        verbose_name = _("NSM Object")
        verbose_name_plural = _("NSM Objects")
        ordering = ("security_property_type", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("security_property_type", "name"),
                name="netbox_nsm_securityproperty_unique_type_name",
            ),
            models.UniqueConstraint(
                fields=("security_property_type", "source_model", "source_pk"),
                name="netbox_nsm_securityproperty_unique_type_source",
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securityproperty", args=[self.pk])

    @staticmethod
    def _is_empty_value(value):
        return value is None or value == ""

    def _validate_field_type(self, field_def, value, errors):
        field_name = field_def.name
        field_type = field_def.type

        if self._is_empty_value(value):
            return

        if field_type in (CustomFieldTypeChoices.TYPE_TEXT, CustomFieldTypeChoices.TYPE_LONGTEXT, CustomFieldTypeChoices.TYPE_URL):
            if not isinstance(value, str):
                errors[field_name] = _("Expected text value.")
            return

        if field_type == CustomFieldTypeChoices.TYPE_INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                errors[field_name] = _("Expected integer value.")
            return

        if field_type == CustomFieldTypeChoices.TYPE_DECIMAL:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors[field_name] = _("Expected decimal value.")
            return

        if field_type == CustomFieldTypeChoices.TYPE_BOOLEAN:
            if not isinstance(value, bool):
                errors[field_name] = _("Expected boolean value.")
            return

        if field_type in (CustomFieldTypeChoices.TYPE_SELECT, CustomFieldTypeChoices.TYPE_OBJECT):
            if not isinstance(value, str):
                errors[field_name] = _("Expected single value.")
            return

        if field_type in (CustomFieldTypeChoices.TYPE_MULTISELECT, CustomFieldTypeChoices.TYPE_MULTIOBJECT):
            if not isinstance(value, list):
                errors[field_name] = _("Expected list value.")
            return

        if field_type in (CustomFieldTypeChoices.TYPE_JSON,):
            # JSON accepts any serializable value.
            return

        if field_type in (CustomFieldTypeChoices.TYPE_DATE, CustomFieldTypeChoices.TYPE_DATETIME):
            if not isinstance(value, str):
                errors[field_name] = _("Expected ISO date/datetime string value.")

    def clean(self):
        super().clean()

        if self.object_data is None:
            self.object_data = {}

        if not isinstance(self.object_data, dict):
            raise ValidationError({"object_data": _("Object data must be a JSON object.")})

        field_defs = list(self.security_property_type.fields.all())
        known_fields = {f.name: f for f in field_defs}
        errors = {}

        for key in self.object_data.keys():
            if key not in known_fields:
                errors[key] = _("Unknown field for this object type.")

        for field_def in field_defs:
            value = self.object_data.get(field_def.name)

            if self._is_empty_value(value) and field_def.default is not None:
                self.object_data[field_def.name] = field_def.default
                value = field_def.default

            if field_def.required and self._is_empty_value(value):
                errors[field_def.name] = _("This field is required.")
                continue

            self._validate_field_type(field_def, value, errors)

            if field_def.unique and not self._is_empty_value(value):
                qs = self.__class__.objects.filter(
                    security_property_type=self.security_property_type,
                    **{f"object_data__{field_def.name}": value},
                )
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
                if qs.exists():
                    errors[field_def.name] = _("Value must be unique within this object type.")

        if errors:
            details = "; ".join(f"{key}: {value}" for key, value in errors.items())
            raise ValidationError({"object_data": details})

    def get_typed_object_data(self):
        rows = []
        for field_def in self.security_property_type.fields.all():
            rows.append(
                {
                    "name": field_def.name,
                    "label": field_def.label or field_def.name,
                    "type": field_def.type,
                    "value": self.object_data.get(field_def.name),
                }
            )
        return rows


@register_search
class SecurityPropertyTypeIndex(SearchIndex):
    model = SecurityPropertyType
    fields = (
        ("name", 200),
        ("slug", 200),
        ("description", 500),
    )


@register_search
class SecurityPropertyIndex(SearchIndex):
    model = SecurityProperty
    fields = (
        ("name", 300),
        ("description", 500),
        ("source_model", 100),
    )
