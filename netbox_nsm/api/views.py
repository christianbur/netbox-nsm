from rest_framework.routers import APIRootView
from netbox.api.viewsets import NetBoxModelViewSet

from .serializers import (
    ApplicationItemSerializer,
    ApplicationSerializer,
    ApplicationSetSerializer,
    SecurityZoneSerializer,
    SecurityZonePolicyRulebookSerializer,
    SecurityZonePolicyRuleSerializer,
    SecurityZonePolicyRulebookAssignmentSerializer,
    ObjectCustomTypeSerializer,
    ObjectCustomObjectSerializer,
)

from netbox_nsm.models import (
    ApplicationItem,
    Application,
    ApplicationSet,
    SecurityZone,
    SecurityZonePolicyRulebook,
    SecurityZonePolicyRule,
    SecurityZonePolicyRulebookAssignment,
    ObjectCustomType,
    ObjectCustomObject,
)

from netbox_nsm.filtersets import (
    ApplicationItemFilterSet,
    ApplicationFilterSet,
    ApplicationSetFilterSet,
    SecurityZoneFilterSet,
    SecurityZonePolicyRulebookFilterSet,
    SecurityZonePolicyRuleFilterSet,
    SecurityZonePolicyRulebookAssignmentFilterSet,
    ObjectCustomTypeFilterSet,
    ObjectCustomObjectFilterSet,
)


class NetBoxSecurityRootView(APIRootView):
    def get_view_name(self):
        return "NetBoxSecurity"


class ApplicationItemViewSet(NetBoxModelViewSet):
    queryset = ApplicationItem.objects.prefetch_related("tags")
    serializer_class = ApplicationItemSerializer
    filterset_class = ApplicationItemFilterSet


class ApplicationViewSet(NetBoxModelViewSet):
    queryset = Application.objects.prefetch_related("tenant", "tags")
    serializer_class = ApplicationSerializer
    filterset_class = ApplicationFilterSet


class ApplicationSetViewSet(NetBoxModelViewSet):
    queryset = ApplicationSet.objects.prefetch_related("tenant", "tags")
    serializer_class = ApplicationSetSerializer
    filterset_class = ApplicationSetFilterSet


class SecurityZoneViewSet(NetBoxModelViewSet):
    queryset = SecurityZone.objects.prefetch_related("tenant", "tags")
    serializer_class = SecurityZoneSerializer
    filterset_class = SecurityZoneFilterSet


class SecurityZonePolicyRulebookViewSet(NetBoxModelViewSet):
    queryset = SecurityZonePolicyRulebook.objects.prefetch_related("tags")
    serializer_class = SecurityZonePolicyRulebookSerializer
    filterset_class = SecurityZonePolicyRulebookFilterSet


class SecurityZonePolicyRuleViewSet(NetBoxModelViewSet):
    queryset = SecurityZonePolicyRule.objects.select_related("rulebook").prefetch_related(
        "source_zones",
        "destination_zones",
        "applications",
        "application_sets",
        "tags",
    )
    serializer_class = SecurityZonePolicyRuleSerializer
    filterset_class = SecurityZonePolicyRuleFilterSet


class SecurityZonePolicyRulebookAssignmentViewSet(NetBoxModelViewSet):
    queryset = SecurityZonePolicyRulebookAssignment.objects.all()
    serializer_class = SecurityZonePolicyRulebookAssignmentSerializer
    filterset_class = SecurityZonePolicyRulebookAssignmentFilterSet


class ObjectCustomTypeViewSet(NetBoxModelViewSet):
    queryset = ObjectCustomType.objects.all()
    serializer_class = ObjectCustomTypeSerializer
    filterset_class = ObjectCustomTypeFilterSet


class ObjectCustomObjectViewSet(NetBoxModelViewSet):
    queryset = ObjectCustomObject.objects.prefetch_related("custom_type", "tags")
    serializer_class = ObjectCustomObjectSerializer
    filterset_class = ObjectCustomObjectFilterSet
