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
    ObjectLabelSerializer,
    ObjectLabelAssignmentSerializer,
    ObjectActionSerializer,
    ObjectLogSerializer,
    ObjectSGTSerializer,
    ObjectSGTAssignmentSerializer,
    ObjectUserSerializer,
    ObjectUserAssignmentSerializer,
    ObjectGroupSerializer,
    ObjectGroupAssignmentSerializer,
    SecurityZoneRoleSerializer,
    SecurityZoneMatrixPolicySerializer,
    SecurityZoneMatrixSerializer,
    SecurityZoneMatrixCellSerializer,
    SecurityZoneSerializer,
    SecurityZoneAssignmentSerializer,
    SecurityZonePolicySerializer,
    SecurityZonePolicyRulebookSerializer,
    SecurityZonePolicyRuleSerializer,
    SecurityZonePolicyRulebookAssignmentSerializer,
    NatPoolSerializer,
    NatPoolAssignmentSerializer,
    NatPoolMemberSerializer,
    NatRuleSetSerializer,
    NatRuleSetAssignmentSerializer,
    NatRuleSerializer,
    NatRuleAssignmentSerializer,
    PolicerSerializer,
    PolicerAssignmentSerializer,
    FirewallFilterSerializer,
    FirewallFilterAssignmentSerializer,
    FirewallFilterRuleSerializer,
    FirewallRuleFromSettingSerializer,
    FirewallRuleThenSettingSerializer,
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
    ObjectLabel,
    ObjectLabelAssignment,
    ObjectAction,
    ObjectLog,
    ObjectSGT,
    ObjectSGTAssignment,
    ObjectUser,
    ObjectUserAssignment,
    ObjectGroup,
    ObjectGroupAssignment,
    SecurityZoneRole,
    SecurityZoneMatrixPolicy,
    SecurityZoneMatrix,
    SecurityZoneMatrixCell,
    SecurityZone,
    SecurityZoneAssignment,
    SecurityZonePolicy,
    SecurityZonePolicyRulebook,
    SecurityZonePolicyRule,
    SecurityZonePolicyRulebookAssignment,
    NatPool,
    NatPoolAssignment,
    NatPoolMember,
    NatRuleSet,
    NatRuleSetAssignment,
    NatRule,
    NatRuleAssignment,
    Policer,
    PolicerAssignment,
    FirewallFilter,
    FirewallFilterAssignment,
    FirewallFilterRule,
    FirewallRuleFromSetting,
    FirewallRuleThenSetting,
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
    ObjectLabelFilterSet,
    ObjectLabelAssignmentFilterSet,
    ObjectActionFilterSet,
    ObjectLogFilterSet,
    ObjectSGTFilterSet,
    ObjectSGTAssignmentFilterSet,
    ObjectUserFilterSet,
    ObjectUserAssignmentFilterSet,
    ObjectGroupFilterSet,
    ObjectGroupAssignmentFilterSet,
    SecurityZoneRoleFilterSet,
    SecurityZoneMatrixPolicyFilterSet,
    SecurityZoneMatrixFilterSet,
    SecurityZoneMatrixCellFilterSet,
    SecurityZoneFilterSet,
    SecurityZoneAssignmentFilterSet,
    SecurityZonePolicyFilterSet,
    SecurityZonePolicyRulebookFilterSet,
    SecurityZonePolicyRuleFilterSet,
    SecurityZonePolicyRulebookAssignmentFilterSet,
    NatPoolFilterSet,
    NatPoolAssignmentFilterSet,
    NatPoolMemberFilterSet,
    NatRuleSetFilterSet,
    NatRuleSetAssignmentFilterSet,
    NatRuleFilterSet,
    NatRuleAssignmentFilterSet,
    PolicerFilterSet,
    PolicerAssignmentFilterSet,
    FirewallFilterFilterSet,
    FirewallFilterAssignmentFilterSet,
    FirewallFilterRuleFilterSet,
    FirewallFilterRuleFromSettingFilterSet,
    FirewallFilterRuleThenSettingFilterSet,
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


class ObjectLabelViewSet(NetBoxModelViewSet):
    queryset = ObjectLabel.objects.prefetch_related("tags")
    serializer_class = ObjectLabelSerializer
    filterset_class = ObjectLabelFilterSet


class ObjectLabelAssignmentViewSet(NetBoxModelViewSet):
    queryset = ObjectLabelAssignment.objects.all()
    serializer_class = ObjectLabelAssignmentSerializer
    filterset_class = ObjectLabelAssignmentFilterSet


class ObjectActionViewSet(NetBoxModelViewSet):
    queryset = ObjectAction.objects.prefetch_related("tags")
    serializer_class = ObjectActionSerializer
    filterset_class = ObjectActionFilterSet


class ObjectLogViewSet(NetBoxModelViewSet):
    queryset = ObjectLog.objects.prefetch_related("tags")
    serializer_class = ObjectLogSerializer
    filterset_class = ObjectLogFilterSet


class ObjectSGTViewSet(NetBoxModelViewSet):
    queryset = ObjectSGT.objects.prefetch_related("tags")
    serializer_class = ObjectSGTSerializer
    filterset_class = ObjectSGTFilterSet


class ObjectSGTAssignmentViewSet(NetBoxModelViewSet):
    queryset = ObjectSGTAssignment.objects.all()
    serializer_class = ObjectSGTAssignmentSerializer
    filterset_class = ObjectSGTAssignmentFilterSet


class ObjectUserViewSet(NetBoxModelViewSet):
    queryset = ObjectUser.objects.prefetch_related("tags")
    serializer_class = ObjectUserSerializer
    filterset_class = ObjectUserFilterSet


class ObjectUserAssignmentViewSet(NetBoxModelViewSet):
    queryset = ObjectUserAssignment.objects.all()
    serializer_class = ObjectUserAssignmentSerializer
    filterset_class = ObjectUserAssignmentFilterSet


class ObjectGroupViewSet(NetBoxModelViewSet):
    queryset = ObjectGroup.objects.prefetch_related(
        "addresses",
        "services",
        "applications",
        "labels",
        "zones",
        "sgts",
        "users",
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


class SecurityZoneMatrixPolicyViewSet(NetBoxModelViewSet):
    queryset = SecurityZoneMatrixPolicy.objects.prefetch_related("tags")
    serializer_class = SecurityZoneMatrixPolicySerializer
    filterset_class = SecurityZoneMatrixPolicyFilterSet


class SecurityZoneMatrixViewSet(NetBoxModelViewSet):
    queryset = SecurityZoneMatrix.annotated_queryset().prefetch_related(
        "tags", "roles"
    )
    serializer_class = SecurityZoneMatrixSerializer
    filterset_class = SecurityZoneMatrixFilterSet


class SecurityZoneMatrixCellViewSet(NetBoxModelViewSet):
    queryset = SecurityZoneMatrixCell.objects.select_related(
        "matrix", "source_zone", "destination_zone", "policy"
    )
    serializer_class = SecurityZoneMatrixCellSerializer
    filterset_class = SecurityZoneMatrixCellFilterSet


class SecurityZoneViewSet(NetBoxModelViewSet):
    queryset = SecurityZone.objects.prefetch_related(
        "roles", "tenant", "tags"
    ).annotate(
        source_policy_count=Count(
            "source_zone_policies",
            distinct=True,
        ),
        destination_policy_count=Count(
            "destination_zone_policies",
            distinct=True,
        ),
    )
    serializer_class = SecurityZoneSerializer
    filterset_class = SecurityZoneFilterSet


class SecurityZoneAssignmentViewSet(NetBoxModelViewSet):
    queryset = SecurityZoneAssignment.objects.all()
    serializer_class = SecurityZoneAssignmentSerializer
    filterset_class = SecurityZoneAssignmentFilterSet


class SecurityZonePolicyViewSet(NetBoxModelViewSet):
    queryset = SecurityZonePolicy.objects.prefetch_related(
        "source_zone",
        "destination_zone",
        "source_address",
        "destination_address",
        "tags",
    )
    serializer_class = SecurityZonePolicySerializer
    filterset_class = SecurityZonePolicyFilterSet


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


class NatPoolViewSet(NetBoxModelViewSet):
    queryset = NatPool.objects.prefetch_related("tags").annotate(
        member_count=Count("natpoolmember_pools")
    )
    serializer_class = NatPoolSerializer
    filterset_class = NatPoolFilterSet


class NatPoolAssignmentViewSet(NetBoxModelViewSet):
    queryset = NatPoolAssignment.objects.all()
    serializer_class = NatPoolAssignmentSerializer
    filterset_class = NatPoolAssignmentFilterSet


class NatPoolMemberViewSet(NetBoxModelViewSet):
    queryset = NatPoolMember.objects.prefetch_related(
        "pool", "address", "prefix", "address_range", "tags"
    )
    serializer_class = NatPoolMemberSerializer
    filterset_class = NatPoolMemberFilterSet


class NatRuleSetViewSet(NetBoxModelViewSet):
    queryset = NatRuleSet.objects.prefetch_related("tags").annotate(
        rule_count=Count("natrule_rules")
    )
    serializer_class = NatRuleSetSerializer
    filterset_class = NatRuleSetFilterSet


class NatRuleSetAssignmentViewSet(NetBoxModelViewSet):
    queryset = NatRuleSetAssignment.objects.all()
    serializer_class = NatRuleSetAssignmentSerializer
    filterset_class = NatRuleSetAssignmentFilterSet


class NatRuleViewSet(NetBoxModelViewSet):
    queryset = NatRule.objects.prefetch_related(
        "source_addresses",
        "destination_addresses",
        "source_prefixes",
        "destination_prefixes",
        "source_ranges",
        "destination_ranges",
        "source_pool",
        "destination_pool",
        "pool",
        "tags",
    )
    serializer_class = NatRuleSerializer
    filterset_class = NatRuleFilterSet


class NatRuleAssignmentViewSet(NetBoxModelViewSet):
    queryset = NatRuleAssignment.objects.all()
    serializer_class = NatRuleAssignmentSerializer
    filterset_class = NatRuleAssignmentFilterSet


class PolicerViewSet(NetBoxModelViewSet):
    queryset = Policer.objects.all()
    serializer_class = PolicerSerializer
    filterset_class = PolicerFilterSet


class PolicerAssignmentViewSet(NetBoxModelViewSet):
    queryset = PolicerAssignment.objects.all()
    serializer_class = PolicerAssignmentSerializer
    filterset_class = PolicerAssignmentFilterSet


class FirewallFilterViewSet(NetBoxModelViewSet):
    queryset = FirewallFilter.objects.prefetch_related("tenant", "tags").annotate(
        rule_count=Count("firewallfilterrule_rules")
    )
    serializer_class = FirewallFilterSerializer
    filterset_class = FirewallFilterFilterSet


class FirewallFilterAssignmentViewSet(NetBoxModelViewSet):
    queryset = FirewallFilterAssignment.objects.all()
    serializer_class = FirewallFilterAssignmentSerializer
    filterset_class = FirewallFilterAssignmentFilterSet


class FirewallFilterRuleViewSet(NetBoxModelViewSet):
    queryset = FirewallFilterRule.objects.prefetch_related("tags")
    serializer_class = FirewallFilterRuleSerializer
    filterset_class = FirewallFilterRuleFilterSet


class FirewallRuleFromSettingViewSet(NetBoxModelViewSet):
    queryset = FirewallRuleFromSetting.objects.all()
    serializer_class = FirewallRuleFromSettingSerializer
    filterset_class = FirewallFilterRuleFromSettingFilterSet


class FirewallRuleThenSettingViewSet(NetBoxModelViewSet):
    queryset = FirewallRuleThenSetting.objects.all()
    serializer_class = FirewallRuleThenSettingSerializer
    filterset_class = FirewallFilterRuleThenSettingFilterSet


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
