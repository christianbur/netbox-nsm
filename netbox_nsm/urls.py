from django.urls import include, path
from django.views.generic import RedirectView
from utilities.urls import get_model_urls

# +
# Import views so the register_model_view is run. This is required for the
# URLs to be set up properly with get_model_urls().
# -
from .views import *  # noqa: F401

app_name = "netbox_nsm"

urlpatterns = [
    path("object/", ObjectsSrcDstTabsView.as_view(), name="object_tabs_root"),
    # Groups area — must come before generic object/<str:tab>/ to avoid conflict
    path("object/groups/", ObjectGroupAreaView.as_view(), name="objectgroup_area_root"),
    path("object/groups/<str:area>/", ObjectGroupAreaView.as_view(), name="objectgroup_area"),
    path("object/custom/", ObjectsCustomAreaView.as_view(), name="object_custom_root"),
    path("object/custom/<str:tab>/", ObjectsCustomAreaView.as_view(), name="object_custom_tab"),
    path("object/custom/types/install-builtins/", BuiltinTypeInstallView.as_view(), name="builtin_type_install"),
    path("object/custom/types/add/", ObjectCustomTypeEditView.as_view(), name="objectcustomtype_add"),
    path("object/custom/types/<int:pk>/", ObjectCustomTypeView.as_view(), name="objectcustomtype"),
    path("object/custom/objects/add/", ObjectCustomEditView.as_view(), name="objectcustom_add"),
    path("object/custom/objects/<int:pk>/", ObjectCustomView.as_view(), name="objectcustom"),
    # YAML Bundle export / import
    path("object/bundle/export/", NSMExportYAMLView.as_view(), name="bundle_export"),
    path("object/bundle/import/", NSMImportYAMLView.as_view(), name="bundle_import"),
    path("custom-types/", include(get_model_urls("netbox_nsm", "objectcustomtype", detail=False))),
    path("custom-types/<int:pk>/", include(get_model_urls("netbox_nsm", "objectcustomtype"))),
    path("custom-objects/", include(get_model_urls("netbox_nsm", "objectcustomobject", detail=False))),
    path("custom-objects/<int:pk>/", include(get_model_urls("netbox_nsm", "objectcustomobject"))),
    path("custom-object-assignments/", include(get_model_urls("netbox_nsm", "objectcustomobjectassignment", detail=False))),
    path("custom-object-assignments/<int:pk>/", include(get_model_urls("netbox_nsm", "objectcustomobjectassignment"))),
    path("object-groups/", include(get_model_urls("netbox_nsm", "objectgroup", detail=False))),
    path("object-groups/<int:pk>/", include(get_model_urls("netbox_nsm", "objectgroup"))),
    path("object/<str:tab>/", ObjectsSrcDstTabsView.as_view(), name="object_tabs"),
    # Security Zones
    path(
        "security-zones/",
        include(get_model_urls("netbox_nsm", "securityzone", detail=False)),
    ),
    path(
        "security-zones/<int:pk>/",
        include(get_model_urls("netbox_nsm", "securityzone")),
    ),
    # Security Policy
    path(
        "security-policy/<int:pk>/visualization/",
        RedirectView.as_view(
            url="/plugins/netbox-nsm/security-policy/%(pk)s/visualization/zonematrix/"
        ),
    ),
    path(
        "security-policy/",
        include(
            get_model_urls("netbox_nsm", "securityzonepolicyrulebook", detail=False)
        ),
    ),
    path(
        "security-policy/<int:pk>/",
        include(get_model_urls("netbox_nsm", "securityzonepolicyrulebook")),
    ),
    path(
        "security-rule/",
        include(
            get_model_urls("netbox_nsm", "securityzonepolicyrule", detail=False)
        ),
    ),
    path(
        "security-rule/<int:pk>/",
        include(get_model_urls("netbox_nsm", "securityzonepolicyrule")),
    ),
    # Security Zone Policy Rulebook Assignments
    path(
        "security-zone-policy-rulebook-assignments/",
        include(
            get_model_urls(
                "netbox_nsm", "securityzonepolicyrulebookassignment", detail=False
            )
        ),
    ),
    path(
        "security-zone-policy-rulebook-assignments/<int:pk>/",
        include(get_model_urls("netbox_nsm", "securityzonepolicyrulebookassignment")),
    ),
]

