from netbox.api.routers import NetBoxRouter

from .views import (
    NetBoxSecurityRootView,
    ApplicationItemViewSet,
    ApplicationViewSet,
    ApplicationSetViewSet,
    SecurityZoneViewSet,
    SecurityZonePolicyRulebookViewSet,
    SecurityZonePolicyRuleViewSet,
    SecurityZonePolicyRulebookAssignmentViewSet,
    ObjectCustomTypeViewSet,
    ObjectCustomObjectViewSet,
    ObjectGroupViewSet,
)

app_name = "netbox_nsm"

router = NetBoxRouter()
router.APIRootView = NetBoxSecurityRootView
router.register("object-services", ApplicationItemViewSet)
router.register("object-applications", ApplicationViewSet)
router.register("application-sets", ApplicationSetViewSet)
router.register("object-zones", SecurityZoneViewSet)
router.register("security-zone-policy-rulebooks", SecurityZonePolicyRulebookViewSet)
router.register("security-zone-policy-rules", SecurityZonePolicyRuleViewSet)
router.register(
    "security-zone-policy-rulebook-assignments",
    SecurityZonePolicyRulebookAssignmentViewSet,
)
router.register("object-custom-types", ObjectCustomTypeViewSet)
router.register("object-custom-objects", ObjectCustomObjectViewSet)
router.register("object-groups", ObjectGroupViewSet)

urlpatterns = router.urls
