from rest_framework.routers import APIRootView
from rest_framework.viewsets import GenericViewSet
from netbox.api.viewsets import NetBoxModelViewSet

from .serializers import (
    SecurityPolicyRulebookSerializer,
    SecurityPolicyRuleSerializer,
    SecurityPolicyAssignmentSerializer,
    SecurityAreaSerializer,
    SecurityObjectGroupSerializer,
    NSMObjectLinkSerializer,
    TypeConfigSerializer,
    RulebookFieldSerializer,
    RulebookFieldTypeSerializer,
    SecurityPolicyRuleObjectItemSerializer,
    SecurityPolicyRuleGroupItemSerializer,
)

from netbox_nsm.models import (
    SecurityPolicyRulebook,
    SecurityPolicyRule,
    SecurityPolicyAssignment,
    SecurityArea,
    SecurityObjectGroup,
    NSMObjectLink,
    TypeConfig,
    RulebookField,
    RulebookFieldType,
    SecurityPolicyRuleObjectItem,
    SecurityPolicyRuleGroupItem,
)

from netbox_nsm.filtersets import (
    SecurityPolicyRulebookFilterSet,
    SecurityPolicyRuleFilterSet,
    SecurityPolicyAssignmentFilterSet,
    SecurityAreaFilterSet,
    SecurityObjectGroupFilterSet,
    NSMObjectLinkFilterSet,
    TypeConfigFilterSet,
    RulebookFieldFilterSet,
    RulebookFieldTypeFilterSet,
    SecurityPolicyRuleObjectItemFilterSet,
    SecurityPolicyRuleGroupItemFilterSet,
)


class NetBoxSecurityRootView(APIRootView):
    def get_view_name(self):
        return "NetBoxSecurity"


class SecurityPolicyRulebookViewSet(NetBoxModelViewSet):
    queryset = SecurityPolicyRulebook.objects.prefetch_related("tags")
    serializer_class = SecurityPolicyRulebookSerializer
    filterset_class = SecurityPolicyRulebookFilterSet


class SecurityPolicyRuleViewSet(NetBoxModelViewSet):
    queryset = SecurityPolicyRule.objects.select_related("rulebook").prefetch_related(
        "tags",
    )
    serializer_class = SecurityPolicyRuleSerializer
    filterset_class = SecurityPolicyRuleFilterSet


class SecurityPolicyAssignmentViewSet(NetBoxModelViewSet):
    queryset = SecurityPolicyAssignment.objects.all()
    serializer_class = SecurityPolicyAssignmentSerializer
    filterset_class = SecurityPolicyAssignmentFilterSet


class SecurityAreaViewSet(NetBoxModelViewSet):
    queryset = SecurityArea.objects.all()
    serializer_class = SecurityAreaSerializer
    filterset_class = SecurityAreaFilterSet


class SecurityObjectGroupViewSet(NetBoxModelViewSet):
    queryset = SecurityObjectGroup.objects.prefetch_related(
        "sub_groups", "tags"
    )
    serializer_class = SecurityObjectGroupSerializer
    filterset_class = SecurityObjectGroupFilterSet


# ── New viewsets ──────────────────────────────────────────────────────────────

class NSMObjectLinkViewSet(NetBoxModelViewSet):
    queryset = NSMObjectLink.objects.select_related(
        "object_a_type", "object_b_type"
    ).prefetch_related("tags").order_by("pk")
    serializer_class = NSMObjectLinkSerializer
    filterset_class = NSMObjectLinkFilterSet


class TypeConfigViewSet(NetBoxModelViewSet):
    queryset = TypeConfig.objects.select_related(
        "content_type"
    ).prefetch_related("tags")
    serializer_class = TypeConfigSerializer
    filterset_class = TypeConfigFilterSet


class _PlainModelViewSet(NetBoxModelViewSet):
    """ViewSet for plain models.Model subclasses (no RestrictedQuerySet).

    NetBoxModelViewSet.initial() calls queryset.restrict() which only exists
    on RestrictedQuerySet. Override to use DRF's standard initial() instead.
    NetBoxModelViewSet.get_queryset() runs prefetch/annotation analysis that
    also fails for plain models — override to return the raw queryset.
    """

    def initial(self, request, *args, **kwargs):
        # Skip NetBox's restrict() call — plain QuerySet doesn't support it.
        GenericViewSet.initial(self, request, *args, **kwargs)

    def get_queryset(self):
        # Skip NetBox's prefetch/annotation analysis for plain models.
        return self.queryset


class RulebookFieldViewSet(_PlainModelViewSet):
    queryset = RulebookField.objects.select_related("rulebook").order_by("pk")
    serializer_class = RulebookFieldSerializer
    filterset_class = RulebookFieldFilterSet


class RulebookFieldTypeViewSet(_PlainModelViewSet):
    queryset = RulebookFieldType.objects.select_related("field", "type_config").order_by("pk")
    serializer_class = RulebookFieldTypeSerializer
    filterset_class = RulebookFieldTypeFilterSet


class SecurityPolicyRuleObjectItemViewSet(_PlainModelViewSet):
    queryset = SecurityPolicyRuleObjectItem.objects.select_related(
        "rule", "field", "content_type"
    ).order_by("pk")
    serializer_class = SecurityPolicyRuleObjectItemSerializer
    filterset_class = SecurityPolicyRuleObjectItemFilterSet


class SecurityPolicyRuleGroupItemViewSet(_PlainModelViewSet):
    queryset = SecurityPolicyRuleGroupItem.objects.select_related(
        "rule", "field", "security_group"
    ).order_by("pk")
    serializer_class = SecurityPolicyRuleGroupItemSerializer
    filterset_class = SecurityPolicyRuleGroupItemFilterSet
