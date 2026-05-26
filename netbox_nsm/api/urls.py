from netbox.api.routers import NetBoxRouter

from .views import (
    NetBoxSecurityRootView,
    SecurityZonePolicyRulebookViewSet,
    SecurityZonePolicyRuleViewSet,
    SecurityZonePolicyRulebookAssignmentViewSet,
    ObjectCustomTypeViewSet,
    ObjectCustomObjectViewSet,
    ObjectCustomObjectAssignmentViewSet,
    ObjectGroupViewSet,
)

app_name = "netbox_nsm"

router = NetBoxRouter()
router.APIRootView = NetBoxSecurityRootView
router.register("security-zone-policy-rulebooks", SecurityZonePolicyRulebookViewSet)
router.register("security-zone-policy-rules", SecurityZonePolicyRuleViewSet)
router.register(
    "security-zone-policy-rulebook-assignments",
    SecurityZonePolicyRulebookAssignmentViewSet,
)
router.register("object-custom-types", ObjectCustomTypeViewSet)
router.register("object-custom-objects", ObjectCustomObjectViewSet)
router.register("object-custom-object-assignments", ObjectCustomObjectAssignmentViewSet)
router.register("object-groups", ObjectGroupViewSet)

urlpatterns = router.urls
