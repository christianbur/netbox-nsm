from netbox.api.routers import NetBoxRouter

from .views import (
    NetBoxSecurityRootView,
    CotRulebookAssignmentViewSet,
    ObjectLinkViewSet,
    TypeConfigViewSet,
)

app_name = "netbox_nsm"

router = NetBoxRouter()
router.APIRootView = NetBoxSecurityRootView
router.register("rulebook-assignments", CotRulebookAssignmentViewSet)
router.register("object-links", ObjectLinkViewSet, basename="objectlink")
router.register("type-configs", TypeConfigViewSet)

urlpatterns = router.urls
