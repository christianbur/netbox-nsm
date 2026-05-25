from netbox.api.routers import NetBoxRouter

from .views import (
    NetBoxSecurityRootView,
    CustomPrefixViewSet,
    AddressListViewSet,
    AddressListAssignmentViewSet,
    AddressSetViewSet,
    AddressSetAssignmentViewSet,
    AddressViewSet,
    AddressAssignmentViewSet,
    ApplicationItemViewSet,
    ApplicationViewSet,
    ApplicationSetViewSet,
    ApplicationAssignmentViewSet,
    ApplicationSetAssignmentViewSet,
    ObjectLabelViewSet,
    ObjectLabelAssignmentViewSet,
    ObjectActionViewSet,
    ObjectLogViewSet,
    ObjectSGTViewSet,
    ObjectSGTAssignmentViewSet,
    ObjectUserViewSet,
    ObjectUserAssignmentViewSet,
    ObjectGroupViewSet,
    ObjectGroupAssignmentViewSet,
    SecurityZoneRoleViewSet,
    SecurityZoneMatrixPolicyViewSet,
    SecurityZoneMatrixViewSet,
    SecurityZoneMatrixCellViewSet,
    SecurityZoneViewSet,
    SecurityZoneAssignmentViewSet,
    SecurityZonePolicyViewSet,
    SecurityZonePolicyRulebookViewSet,
    SecurityZonePolicyRuleViewSet,
    SecurityZonePolicyRulebookAssignmentViewSet,
    NatPoolViewSet,
    NatPoolAssignmentViewSet,
    NatPoolMemberViewSet,
    NatRuleSetViewSet,
    NatRuleSetAssignmentViewSet,
    NatRuleViewSet,
    NatRuleAssignmentViewSet,
    PolicerViewSet,
    FirewallFilterViewSet,
    FirewallFilterAssignmentViewSet,
    PolicerAssignmentViewSet,
    FirewallFilterRuleViewSet,
    FirewallRuleFromSettingViewSet,
    FirewallRuleThenSettingViewSet,
    ObjectCustomTypeViewSet,
    ObjectCustomObjectViewSet,
    ObjectNATViewSet,
    ObjectInterfaceViewSet,
    ObjectCommentViewSet,
    ObjectInstalledOnViewSet,
    ObjectFilterViewSet,
    ObjectPolicerViewSet,
)

app_name = "netbox_nsm"

router = NetBoxRouter()
router.APIRootView = NetBoxSecurityRootView
router.register("custom-prefixes", CustomPrefixViewSet)
router.register("object-addresses", AddressViewSet)
router.register("addresses", AddressViewSet, basename="address-legacy")
router.register("address-sets", AddressSetViewSet)
router.register("address-lists", AddressListViewSet)
router.register("object-services", ApplicationItemViewSet)
router.register("services", ApplicationItemViewSet, basename="applicationitem-legacy")
router.register("application-items", ApplicationItemViewSet, basename="applicationitem-model-legacy")
router.register("object-applications", ApplicationViewSet)
router.register("applications", ApplicationViewSet, basename="application-legacy")
router.register("application-sets", ApplicationSetViewSet)
router.register("object-labels", ObjectLabelViewSet)
router.register("object-label-assignments", ObjectLabelAssignmentViewSet)
router.register("labels", ObjectLabelViewSet, basename="objectlabel-legacy")
router.register("object-actions", ObjectActionViewSet)
router.register("object-logs", ObjectLogViewSet)
router.register("object-sgts", ObjectSGTViewSet)
router.register("object-sgt-assignments", ObjectSGTAssignmentViewSet)
router.register("sgts", ObjectSGTViewSet, basename="objectsgt-legacy")
router.register("object-users", ObjectUserViewSet)
router.register("object-user-assignments", ObjectUserAssignmentViewSet)
router.register("users", ObjectUserViewSet, basename="objectuser-legacy")
router.register("object-groups", ObjectGroupViewSet)
router.register("object-group-assignments", ObjectGroupAssignmentViewSet)
router.register("groups", ObjectGroupViewSet, basename="objectgroup-legacy")
router.register("security-zone-roles", SecurityZoneRoleViewSet)
router.register("security-zone-matrix-policies", SecurityZoneMatrixPolicyViewSet)
router.register("security-zone-matrices", SecurityZoneMatrixViewSet)
router.register("security-zone-matrix-cells", SecurityZoneMatrixCellViewSet)
router.register("object-zones", SecurityZoneViewSet)
router.register("zones", SecurityZoneViewSet, basename="securityzone-legacy")
router.register("security-zones", SecurityZoneViewSet, basename="securityzone-model-legacy")
router.register("security-zone-policies", SecurityZonePolicyViewSet)
router.register("security-zone-policy-rulebooks", SecurityZonePolicyRulebookViewSet)
router.register("security-zone-policy-rules", SecurityZonePolicyRuleViewSet)
router.register("nat-pools", NatPoolViewSet)
router.register("nat-pool-members", NatPoolMemberViewSet)
router.register("nat-rule-sets", NatRuleSetViewSet)
router.register("nat-rules", NatRuleViewSet)
router.register("policers", PolicerViewSet)
router.register("firewall-filters", FirewallFilterViewSet)
router.register("firewall-filter-rules", FirewallFilterRuleViewSet)
router.register("firewall-filter-rule-from-settings", FirewallRuleFromSettingViewSet)
router.register("firewall-filter-rule-then-settings", FirewallRuleThenSettingViewSet)
router.register("address-assignments", AddressAssignmentViewSet)
router.register("address-set-assignments", AddressSetAssignmentViewSet)
router.register("address-list-assignments", AddressListAssignmentViewSet)
router.register("application-assignments", ApplicationAssignmentViewSet)
router.register("application-set-assignments", ApplicationSetAssignmentViewSet)
router.register("security-zone-assignments", SecurityZoneAssignmentViewSet)
router.register(
    "security-zone-policy-rulebook-assignments",
    SecurityZonePolicyRulebookAssignmentViewSet,
)
router.register("nat-pool-assignments", NatPoolAssignmentViewSet)
router.register("nat-rule-set-assignments", NatRuleSetAssignmentViewSet)
router.register("nat-rule-assignments", NatRuleAssignmentViewSet)
router.register("firewall-filter-assignments", FirewallFilterAssignmentViewSet)
router.register("policer-assignments", PolicerAssignmentViewSet)
router.register("object-custom-types", ObjectCustomTypeViewSet)
router.register("object-nats", ObjectNATViewSet)
router.register("object-interfaces", ObjectInterfaceViewSet)
router.register("object-comments", ObjectCommentViewSet)
router.register("object-installed-ons", ObjectInstalledOnViewSet)
router.register("object-filters", ObjectFilterViewSet)
router.register("object-policers", ObjectPolicerViewSet)
router.register("object-custom-objects", ObjectCustomObjectViewSet)

urlpatterns = router.urls
