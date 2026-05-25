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
    ObjectActionViewSet,
    ObjectGroupViewSet,
    ObjectGroupAssignmentViewSet,
    SecurityZoneRoleViewSet,
    SecurityZoneViewSet,
    SecurityZoneAssignmentViewSet,
    SecurityZonePolicyRulebookViewSet,
    SecurityZonePolicyRuleViewSet,
    SecurityZonePolicyRulebookAssignmentViewSet,
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
router.register("address-sets", AddressSetViewSet)
router.register("address-lists", AddressListViewSet)
router.register("object-services", ApplicationItemViewSet)
router.register("object-applications", ApplicationViewSet)
router.register("application-sets", ApplicationSetViewSet)
router.register("object-actions", ObjectActionViewSet)
router.register("object-groups", ObjectGroupViewSet)
router.register("object-group-assignments", ObjectGroupAssignmentViewSet)
router.register("security-zone-roles", SecurityZoneRoleViewSet)
router.register("object-zones", SecurityZoneViewSet)
router.register("address-assignments", AddressAssignmentViewSet)
router.register("address-set-assignments", AddressSetAssignmentViewSet)
router.register("address-list-assignments", AddressListAssignmentViewSet)
router.register("application-assignments", ApplicationAssignmentViewSet)
router.register("application-set-assignments", ApplicationSetAssignmentViewSet)
router.register("security-zone-assignments", SecurityZoneAssignmentViewSet)
router.register("security-zone-policy-rulebooks", SecurityZonePolicyRulebookViewSet)
router.register("security-zone-policy-rules", SecurityZonePolicyRuleViewSet)
router.register(
    "security-zone-policy-rulebook-assignments",
    SecurityZonePolicyRulebookAssignmentViewSet,
)
router.register("object-custom-types", ObjectCustomTypeViewSet)
router.register("object-nats", ObjectNATViewSet)
router.register("object-interfaces", ObjectInterfaceViewSet)
router.register("object-comments", ObjectCommentViewSet)
router.register("object-installed-ons", ObjectInstalledOnViewSet)
router.register("object-filters", ObjectFilterViewSet)
router.register("object-policers", ObjectPolicerViewSet)
router.register("object-custom-objects", ObjectCustomObjectViewSet)

urlpatterns = router.urls
