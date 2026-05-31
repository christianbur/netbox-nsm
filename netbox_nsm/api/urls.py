from netbox.api.routers import NetBoxRouter

from .views import (
    NetBoxSecurityRootView,
    SecurityAreaViewSet,
    SecurityPolicyRulebookViewSet,
    SecurityPolicyRuleViewSet,
    SecurityPolicyAssignmentViewSet,
    SecurityObjectGroupViewSet,
    NSMObjectLinkViewSet,
    TypeConfigViewSet,
    RulebookFieldViewSet,
    RulebookFieldTypeViewSet,
    SecurityPolicyRuleObjectItemViewSet,
    SecurityPolicyRuleGroupItemViewSet,
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
router.register("object-groups", SecurityObjectGroupViewSet)
router.register("object-links", NSMObjectLinkViewSet)
router.register("type-configs", TypeConfigViewSet)
router.register("rulebook-fields", RulebookFieldViewSet)
router.register("rulebook-field-types", RulebookFieldTypeViewSet)
router.register("rule-object-items", SecurityPolicyRuleObjectItemViewSet)
router.register("rule-group-items", SecurityPolicyRuleGroupItemViewSet)

urlpatterns = router.urls

