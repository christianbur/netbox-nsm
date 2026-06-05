from netbox.api.routers import NetBoxRouter

from .views import (
    NetBoxSecurityRootView,
    RulebookViewSet,
    RuleViewSet,
    RulebookAssignmentViewSet,
    ObjectGroupViewSet,
    ObjectLinkViewSet,
    TypeConfigViewSet,
    RulebookFieldViewSet,
    RulebookFieldTypeViewSet,
    RuleObjectItemViewSet,
    RuleGroupItemViewSet,
)

app_name = "netbox_nsm"

router = NetBoxRouter()
router.APIRootView = NetBoxSecurityRootView
router.register("rulebooks", RulebookViewSet)
router.register("rules", RuleViewSet)
router.register("rulebook-assignments", RulebookAssignmentViewSet)
router.register("object-groups", ObjectGroupViewSet)
router.register("object-links", ObjectLinkViewSet)
router.register("type-configs", TypeConfigViewSet)
router.register("rulebook-fields", RulebookFieldViewSet)
router.register("rulebook-field-types", RulebookFieldTypeViewSet)
router.register("rule-object-items", RuleObjectItemViewSet)
router.register("rule-group-items", RuleGroupItemViewSet)

urlpatterns = router.urls
