import django_filters
from django.db.models import Q

from django_filters import FilterSet
from netbox.filtersets import NetBoxModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import (
    NSMObjectLink,
    TypeConfig,
    RulebookField,
    RulebookFieldType,
    SecurityPolicyRuleObjectItem,
    SecurityPolicyRuleGroupItem,
    SecurityPolicyRulebook,
    SecurityObjectGroup,
)

__all__ = (
    "NSMObjectLinkFilterSet",
    "TypeConfigFilterSet",
    "RulebookFieldFilterSet",
    "RulebookFieldTypeFilterSet",
    "SecurityPolicyRuleObjectItemFilterSet",
    "SecurityPolicyRuleGroupItemFilterSet",
)


class _PlainFilterSet(FilterSet):
    pass


@register_filterset
class NSMObjectLinkFilterSet(NetBoxModelFilterSet):
    object_a_type_id = django_filters.NumberFilter(
        field_name="object_a_type_id", label="Object A Type (ID)"
    )
    object_b_type_id = django_filters.NumberFilter(
        field_name="object_b_type_id", label="Object B Type (ID)"
    )
    object_a_id = django_filters.NumberFilter(
        field_name="object_a_id", label="Object A (ID)"
    )
    object_b_id = django_filters.NumberFilter(
        field_name="object_b_id", label="Object B (ID)"
    )

    class Meta:
        model = NSMObjectLink
        fields = (
            "id",
            "object_a_type_id",
            "object_a_id",
            "object_b_type_id",
            "object_b_id",
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(comment__icontains=value)


@register_filterset
class TypeConfigFilterSet(NetBoxModelFilterSet):
    matching_class = django_filters.MultipleChoiceFilter(
        choices=[
            ("address", "Address"),
            ("zone", "Zone"),
            ("label", "Label"),
            ("trust", "Trust"),
            ("service", "Service"),
            ("action", "Action"),
            ("user", "User"),
            ("application", "Application"),
            ("group", "Group"),
            ("other", "Other"),
        ],
    )
    inherit_links = django_filters.BooleanFilter()
    inherit_stop_on_own = django_filters.BooleanFilter()

    class Meta:
        model = TypeConfig
        fields = ("id", "matching_class", "inherit_links", "inherit_stop_on_own")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(content_type__app_label__icontains=value)
            | Q(content_type__model__icontains=value)
        )


class RulebookFieldFilterSet(_PlainFilterSet):
    rulebook_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SecurityPolicyRulebook.objects.all(),
        field_name="rulebook",
        label="Rulebook (ID)",
    )
    placement = django_filters.MultipleChoiceFilter(
        choices=[
            ("source", "Source"),
            ("destination", "Destination"),
            ("fixed", "Fixed"),
        ],
    )

    class Meta:
        model = RulebookField
        fields = ("id", "slug", "name", "placement")


class RulebookFieldTypeFilterSet(_PlainFilterSet):
    field_id = django_filters.ModelMultipleChoiceFilter(
        queryset=RulebookField.objects.all(),
        field_name="field",
        label="Rulebook Field (ID)",
    )
    type_config_id = django_filters.ModelMultipleChoiceFilter(
        queryset=TypeConfig.objects.all(),
        field_name="type_config",
        label="Type Config (ID)",
    )

    class Meta:
        model = RulebookFieldType
        fields = ("id", "field_id", "type_config_id")


class SecurityPolicyRuleObjectItemFilterSet(_PlainFilterSet):
    rule_id = django_filters.NumberFilter(field_name="rule_id", label="Rule (ID)")
    field_id = django_filters.NumberFilter(
        field_name="field_id", label="Rulebook Field (ID)"
    )
    content_type_id = django_filters.NumberFilter(
        field_name="content_type_id", label="Content Type (ID)"
    )
    object_id = django_filters.NumberFilter(field_name="object_id", label="Object (ID)")
    exclude = django_filters.BooleanFilter()

    class Meta:
        model = SecurityPolicyRuleObjectItem
        fields = (
            "id",
            "rule_id",
            "field_id",
            "content_type_id",
            "object_id",
            "exclude",
        )


class SecurityPolicyRuleGroupItemFilterSet(_PlainFilterSet):
    rule_id = django_filters.NumberFilter(field_name="rule_id", label="Rule (ID)")
    field_id = django_filters.NumberFilter(
        field_name="field_id", label="Rulebook Field (ID)"
    )
    security_group_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SecurityObjectGroup.objects.all(),
        field_name="security_group",
        label="Security Group (ID)",
    )
    exclude = django_filters.BooleanFilter()

    class Meta:
        model = SecurityPolicyRuleGroupItem
        fields = ("id", "rule_id", "field_id", "security_group_id", "exclude")
