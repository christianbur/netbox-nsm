from netbox.api.routers import NetBoxRouter

from .views import (
    NetBoxSecurityRootView,
    CustomPrefixViewSet,
    AddressListViewSet,
    AddressSetViewSet,
    AddressViewSet,
    ApplicationItemViewSet,
    ApplicationViewSet,
    ApplicationSetViewSet,
    ObjectActionViewSet,
    ObjectGroupViewSet,
    SecurityZoneViewSet,
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
router.register("object-zones", SecurityZoneViewSet)
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
