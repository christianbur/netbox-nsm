from rest_framework.routers import APIRootView
from netbox.api.viewsets import NetBoxModelViewSet
from django.db.models import Count

from .serializers import (
    CustomPrefixSerializer,
    AddressListSerializer,
    AddressListAssignmentSerializer,
    AddressSetSerializer,
    AddressSetAssignmentSerializer,
    AddressSerializer,
    AddressAssignmentSerializer,
    ApplicationItemSerializer,
    ApplicationSerializer,
    ApplicationAssignmentSerializer,
    ApplicationSetSerializer,
    ApplicationSetAssignmentSerializer,
    ObjectActionSerializer,
    ObjectGroupSerializer,
    ObjectGroupAssignmentSerializer,
    SecurityZoneRoleSerializer,
    SecurityZoneSerializer,
    SecurityZoneAssignmentSerializer,
    SecurityZonePolicyRulebookSerializer,
    SecurityZonePolicyRuleSerializer,
    SecurityZonePolicyRulebookAssignmentSerializer,
    ObjectCustomTypeSerializer,
    ObjectCustomObjectSerializer,
    ObjectNATSerializer,
    ObjectInterfaceSerializer,
    ObjectCommentSerializer,
    ObjectInstalledOnSerializer,
    ObjectFilterSerializer,
    ObjectPolicerSerializer,
)

from netbox_nsm.models import (
    CustomPrefix,
    AddressList,
    AddressListAssignment,
    AddressSet,
    AddressSetAssignment,
    Address,
    AddressAssignment,
    ApplicationItem,
    Application,
    ApplicationAssignment,
    ApplicationSet,
    ApplicationSetAssignment,
    ObjectAction,
    ObjectGroup,
    ObjectGroupAssignment,
    SecurityZoneRole,
    SecurityZone,
    SecurityZoneAssignment,
    SecurityZonePolicyRulebook,
    SecurityZonePolicyRule,
    SecurityZonePolicyRulebookAssignment,
    ObjectCustomType,
    ObjectCustomObject,
    ObjectNAT,
    ObjectInterface,
    ObjectComment,
    ObjectInstalledOn,
    ObjectFilter,
    ObjectPolicer,
)

from netbox_nsm.filtersets import (
    CustomPrefixFilterSet,
    AddressListFilterSet,
    AddressListAssignmentFilterSet,
    AddressSetFilterSet,
    AddressSetAssignmentFilterSet,
    AddressFilterSet,
    AddressAssignmentFilterSet,
    ApplicationItemFilterSet,
    ApplicationFilterSet,
    ApplicationAssignmentFilterSet,
    ApplicationSetFilterSet,
    ApplicationSetAssignmentFilterSet,
    ObjectActionFilterSet,
    ObjectGroupFilterSet,
    ObjectGroupAssignmentFilterSet,
    SecurityZoneRoleFilterSet,
    SecurityZoneFilterSet,
    SecurityZoneAssignmentFilterSet,
    SecurityZonePolicyRulebookFilterSet,
    SecurityZonePolicyRuleFilterSet,
    SecurityZonePolicyRulebookAssignmentFilterSet,
    ObjectCustomTypeFilterSet,
    ObjectCustomObjectFilterSet,
    ObjectNATFilterSet,
    ObjectInterfaceFilterSet,
    ObjectCommentFilterSet,
    ObjectInstalledOnFilterSet,
    ObjectFilterFilterSet,
    ObjectPolicerFilterSet,
)


class NetBoxSecurityRootView(APIRootView):
    def get_view_name(self):
        return "NetBoxSecurity"


class CustomPrefixViewSet(NetBoxModelViewSet):
    queryset = CustomPrefix.objects.all()
    serializer_class = CustomPrefixSerializer
    filterset_class = CustomPrefixFilterSet


class AddressListViewSet(NetBoxModelViewSet):
    queryset = AddressList.objects.all()
    serializer_class = AddressListSerializer
    filterset_class = AddressListFilterSet


class AddressListAssignmentViewSet(NetBoxModelViewSet):
    queryset = AddressListAssignment.objects.all()
    serializer_class = AddressListAssignmentSerializer
    filterset_class = AddressListAssignmentFilterSet


class AddressSetViewSet(NetBoxModelViewSet):
    queryset = AddressSet.objects.prefetch_related("tenant", "tags")
    serializer_class = AddressSetSerializer
    filterset_class = AddressSetFilterSet


class AddressSetAssignmentViewSet(NetBoxModelViewSet):
    queryset = AddressSetAssignment.objects.all()
    serializer_class = AddressSetAssignmentSerializer
    filterset_class = AddressSetAssignmentFilterSet


class AddressViewSet(NetBoxModelViewSet):
    queryset = Address.objects.prefetch_related("tenant", "tags")
    serializer_class = AddressSerializer
    filterset_class = AddressFilterSet


class AddressAssignmentViewSet(NetBoxModelViewSet):
    queryset = AddressAssignment.objects.all()
    serializer_class = AddressAssignmentSerializer
    filterset_class = AddressAssignmentFilterSet


class ApplicationItemViewSet(NetBoxModelViewSet):
    queryset = ApplicationItem.objects.prefetch_related("tags")
    serializer_class = ApplicationItemSerializer
    filterset_class = ApplicationItemFilterSet


class ApplicationViewSet(NetBoxModelViewSet):
    queryset = Application.objects.prefetch_related("tenant", "tags")
    serializer_class = ApplicationSerializer
    filterset_class = ApplicationFilterSet


class ApplicationAssignmentViewSet(NetBoxModelViewSet):
    queryset = ApplicationAssignment.objects.all()
    serializer_class = ApplicationAssignmentSerializer
    filterset_class = ApplicationAssignmentFilterSet


class ApplicationSetViewSet(NetBoxModelViewSet):
    queryset = ApplicationSet.objects.prefetch_related("tenant", "tags")
    serializer_class = ApplicationSetSerializer
    filterset_class = ApplicationSetFilterSet


class ApplicationSetAssignmentViewSet(NetBoxModelViewSet):
    queryset = ApplicationSetAssignment.objects.all()
    serializer_class = ApplicationSetAssignmentSerializer
    filterset_class = ApplicationSetAssignmentFilterSet


class ObjectActionViewSet(NetBoxModelViewSet):
    queryset = ObjectAction.objects.prefetch_related("tags")
    serializer_class = ObjectActionSerializer
    filterset_class = ObjectActionFilterSet


class ObjectGroupViewSet(NetBoxModelViewSet):
    queryset = ObjectGroup.objects.prefetch_related(
        "addresses",
        "services",
        "applications",
        "zones",
        "tags",
    )
    serializer_class = ObjectGroupSerializer
    filterset_class = ObjectGroupFilterSet


class ObjectGroupAssignmentViewSet(NetBoxModelViewSet):
    queryset = ObjectGroupAssignment.objects.all()
    serializer_class = ObjectGroupAssignmentSerializer
    filterset_class = ObjectGroupAssignmentFilterSet


class SecurityZoneRoleViewSet(NetBoxModelViewSet):
    queryset = SecurityZoneRole.annotated_queryset().prefetch_related("tags")
    serializer_class = SecurityZoneRoleSerializer
    filterset_class = SecurityZoneRoleFilterSet


class SecurityZoneViewSet(NetBoxModelViewSet):
    queryset = SecurityZone.objects.prefetch_related("roles", "tenant", "tags")
    serializer_class = SecurityZoneSerializer
    filterset_class = SecurityZoneFilterSet


class SecurityZoneAssignmentViewSet(NetBoxModelViewSet):
    queryset = SecurityZoneAssignment.objects.all()
    serializer_class = SecurityZoneAssignmentSerializer
    filterset_class = SecurityZoneAssignmentFilterSet


class SecurityZonePolicyRulebookViewSet(NetBoxModelViewSet):
    queryset = SecurityZonePolicyRulebook.objects.prefetch_related("tags")
    serializer_class = SecurityZonePolicyRulebookSerializer
    filterset_class = SecurityZonePolicyRulebookFilterSet


class SecurityZonePolicyRuleViewSet(NetBoxModelViewSet):
    queryset = SecurityZonePolicyRule.objects.select_related("rulebook").prefetch_related(
        "source_zones",
        "source_addresses",
        "source_users",
        "destination_zones",
        "destination_addresses",
        "destination_users",
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


class ObjectNATViewSet(NetBoxModelViewSet):
    queryset = ObjectNAT.objects.all()
    serializer_class = ObjectNATSerializer
    filterset_class = ObjectNATFilterSet


class ObjectInterfaceViewSet(NetBoxModelViewSet):
    queryset = ObjectInterface.objects.all()
    serializer_class = ObjectInterfaceSerializer
    filterset_class = ObjectInterfaceFilterSet


class ObjectCommentViewSet(NetBoxModelViewSet):
    queryset = ObjectComment.objects.all()
    serializer_class = ObjectCommentSerializer
    filterset_class = ObjectCommentFilterSet


class ObjectInstalledOnViewSet(NetBoxModelViewSet):
    queryset = ObjectInstalledOn.objects.all()
    serializer_class = ObjectInstalledOnSerializer
    filterset_class = ObjectInstalledOnFilterSet


class ObjectFilterViewSet(NetBoxModelViewSet):
    queryset = ObjectFilter.objects.all()
    serializer_class = ObjectFilterSerializer
    filterset_class = ObjectFilterFilterSet


class ObjectPolicerViewSet(NetBoxModelViewSet):
    queryset = ObjectPolicer.objects.all()
    serializer_class = ObjectPolicerSerializer
    filterset_class = ObjectPolicerFilterSet


class ObjectCustomObjectViewSet(NetBoxModelViewSet):
    queryset = ObjectCustomObject.objects.prefetch_related("custom_type", "tags")
    serializer_class = ObjectCustomObjectSerializer
    filterset_class = ObjectCustomObjectFilterSet
