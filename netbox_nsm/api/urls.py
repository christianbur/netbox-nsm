from netbox.api.routers import NetBoxRouter

from .views import (
    NetBoxSecurityRootView,
    SecurityAreaViewSet,
    SecurityPolicyRulebookViewSet,
    SecurityPolicyRuleViewSet,
    SecurityPolicyAssignmentViewSet,
    SecurityObjectTypeViewSet,
    SecurityObjectViewSet,
    SecurityObjectAssignmentViewSet,
    SecurityObjectGroupViewSet,
)

app_name = "netbox_nsm"

router = NetBoxRouter()
router.APIRootView = NetBoxSecurityRootView
router.register("security-areas", SecurityAreaViewSet)
router.register("security-zone-policy-rulebooks", SecurityPolicyRulebookViewSet)
router.register("security-zone-policy-rules", SecurityPolicyRuleViewSet)
router.register(
    "security-zone-policy-rulebook-assignments",
    SecurityPolicyAssignmentViewSet,
)
router.register("object-custom-types", SecurityObjectTypeViewSet)
router.register("object-custom-objects", SecurityObjectViewSet)
router.register("object-custom-object-assignments", SecurityObjectAssignmentViewSet)
router.register("object-groups", SecurityObjectGroupViewSet)

urlpatterns = router.urls
