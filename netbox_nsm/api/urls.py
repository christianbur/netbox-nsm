from django.urls import path

from netbox.api.routers import NetBoxRouter

from .ip_analyzer import IpAnalyzerRestApiView
from .nsm_config import NsmConfigApiView
from .views import (
    NetBoxSecurityRootView,
    ObjectLinkViewSet,
)

app_name = "netbox_nsm"

router = NetBoxRouter()
router.APIRootView = NetBoxSecurityRootView
router.register("object-links", ObjectLinkViewSet, basename="objectlink")

urlpatterns = [
    path("ip-analyzer/", IpAnalyzerRestApiView.as_view(), name="ip-analyzer"),
    path(
        "nsm-configs/<slug:slug>/",
        NsmConfigApiView.as_view(),
        name="nsmconfig-detail",
    ),
    *router.urls,
]
