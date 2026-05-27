from rest_framework.routers import APIRootView
from netbox.api.viewsets import NetBoxModelViewSet

from .serializers import (
    SecurityPolicyRulebookSerializer,
    SecurityPolicyRuleSerializer,
    SecurityPolicyAssignmentSerializer,
    SecurityObjectTypeSerializer,
    SecurityObjectSerializer,
    SecurityObjectAssignmentSerializer,
    SecurityObjectGroupSerializer,
)

from netbox_nsm.models import (
    SecurityPolicyRulebook,
    SecurityPolicyRule,
    SecurityPolicyAssignment,
    SecurityObjectType,
    SecurityObject,
    SecurityObjectAssignment,
    SecurityObjectGroup,
)

from netbox_nsm.filtersets import (
    SecurityPolicyRulebookFilterSet,
    SecurityPolicyRuleFilterSet,
    SecurityPolicyAssignmentFilterSet,
    SecurityObjectTypeFilterSet,
    SecurityObjectFilterSet,
    SecurityObjectAssignmentFilterSet,
    SecurityObjectGroupFilterSet,
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
        "source_zones",
        "destination_zones",
        "tags",
    )
    serializer_class = SecurityPolicyRuleSerializer
    filterset_class = SecurityPolicyRuleFilterSet


class SecurityPolicyAssignmentViewSet(NetBoxModelViewSet):
    queryset = SecurityPolicyAssignment.objects.all()
    serializer_class = SecurityPolicyAssignmentSerializer
    filterset_class = SecurityPolicyAssignmentFilterSet


class SecurityObjectTypeViewSet(NetBoxModelViewSet):
    queryset = SecurityObjectType.objects.all()
    serializer_class = SecurityObjectTypeSerializer
    filterset_class = SecurityObjectTypeFilterSet


class SecurityObjectViewSet(NetBoxModelViewSet):
    queryset = SecurityObject.objects.prefetch_related("custom_type", "tags")
    serializer_class = SecurityObjectSerializer
    filterset_class = SecurityObjectFilterSet


class SecurityObjectAssignmentViewSet(NetBoxModelViewSet):
    queryset = SecurityObjectAssignment.objects.select_related(
        "custom_object", "assigned_object_type"
    )
    serializer_class = SecurityObjectAssignmentSerializer
    filterset_class = SecurityObjectAssignmentFilterSet


class SecurityObjectGroupViewSet(NetBoxModelViewSet):
    queryset = SecurityObjectGroup.objects.prefetch_related("members", "sub_groups", "tags")
    serializer_class = SecurityObjectGroupSerializer
    filterset_class = SecurityObjectGroupFilterSet
