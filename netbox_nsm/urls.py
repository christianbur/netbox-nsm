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
    # SecurityArea CRUD
    path("areas/", SecurityAreaListView.as_view(), name="securityarea-list"),
    path("areas/<int:pk>/", SecurityAreaView.as_view(), name="securityarea-detail"),
    path("areas/", include(get_model_urls("netbox_nsm", "securityarea", detail=False))),
    path("areas/<int:pk>/", include(get_model_urls("netbox_nsm", "securityarea"))),
    # Object-Builder (Areas / Types / Built-in tabs)
    path("object-builder/", ObjectBuilderView.as_view(), name="object_builder_root"),
    path("object-builder/<str:tab>/", ObjectBuilderView.as_view(), name="object_builder"),
    path("object/", ObjectsSrcDstTabsView.as_view(), name="object_tabs_root"),
    # Groups area — must come before generic object/<str:tab>/ to avoid conflict
    path("object/groups/", SecurityObjectGroupAreaView.as_view(), name="securityobjectgroup_area_root"),
    path("object/groups/<str:area>/", SecurityObjectGroupAreaView.as_view(), name="securityobjectgroup_area"),
    path("object/custom/", ObjectsCustomAreaView.as_view(), name="object_custom_root"),
    path("object/custom/<str:tab>/", ObjectsCustomAreaView.as_view(), name="object_custom_tab"),
    path("object/custom/types/install-builtins/", BuiltinTypeInstallView.as_view(), name="builtin_type_install"),
    path("object/custom/types/add/", SecurityObjectTypeEditView.as_view(), name="securityobjecttype_add"),
    path("object/custom/types/<int:pk>/", SecurityObjectTypeView.as_view(), name="securityobjecttype"),
    path("object/custom/objects/add/", ObjectCustomEditView.as_view(), name="objectcustom_add"),
    path("object/custom/objects/<int:pk>/", ObjectCustomView.as_view(), name="objectcustom"),
    # YAML Bundle export / import
    path("object/bundle/export/", NSMExportYAMLView.as_view(), name="bundle_export"),
    path("object/bundle/import/", NSMImportYAMLView.as_view(), name="bundle_import"),
    path("custom-types/", include(get_model_urls("netbox_nsm", "securityobjecttype", detail=False))),
    path("custom-types/<int:pk>/", include(get_model_urls("netbox_nsm", "securityobjecttype"))),
    path("custom-objects/", include(get_model_urls("netbox_nsm", "securityobject", detail=False))),
    path("custom-objects/<int:pk>/", include(get_model_urls("netbox_nsm", "securityobject"))),
    path("custom-object-assignments/", include(get_model_urls("netbox_nsm", "securityobjectassignment", detail=False))),
    path("custom-object-assignments/<int:pk>/", include(get_model_urls("netbox_nsm", "securityobjectassignment"))),
    path("object-groups/", include(get_model_urls("netbox_nsm", "securityobjectgroup", detail=False))),
    path("object-groups/<int:pk>/", include(get_model_urls("netbox_nsm", "securityobjectgroup"))),
    path("object/<str:tab>/", ObjectsSrcDstTabsView.as_view(), name="object_tabs"),
    # Security Policy
    path(
        "security-policy/",
        include(
            get_model_urls("netbox_nsm", "securitypolicyrulebook", detail=False)
        ),
    ),
    path(
        "security-policy/<int:pk>/",
        include(get_model_urls("netbox_nsm", "securitypolicyrulebook")),
    ),
    path(
        "security-policy/<int:pk>/visualization/",
        RedirectView.as_view(pattern_name="plugins:netbox_nsm:securitypolicyrulebook_visualization", query_string=True),
        name="securitypolicyrulebook_visualization_redirect",
    ),
    path(
        "security-policy/<int:pk>/bulk-assign/",
        SecurityPolicyRulebookBulkAssignView.as_view(),
        name="securitypolicyrulebook_bulk_assign",
    ),
    path(
        "security-rule/",
        include(
            get_model_urls("netbox_nsm", "securitypolicyrule", detail=False)
        ),
    ),
    path(
        "security-rule/<int:pk>/",
        include(get_model_urls("netbox_nsm", "securitypolicyrule")),
    ),
    path(
        "security-zone-policy-rulebook-assignments/",
        include(
            get_model_urls(
                "netbox_nsm", "securitypolicyassignment", detail=False
            )
        ),
    ),
    path(
        "security-zone-policy-rulebook-assignments/<int:pk>/",
        include(get_model_urls("netbox_nsm", "securitypolicyassignment")),
    ),
    # Device / VM — Matching Rules (virtual combined label)
    path(
        "device-security/device/<int:pk>/matching-rules/",
        DeviceMatchingRulesView.as_view(),
        name="device_matching_rules",
    ),
    path(
        "device-security/vm/<int:pk>/matching-rules/",
        DeviceMatchingRulesView.as_view(),
        {"type": "vm"},
        name="vm_matching_rules",
    ),
    # Global rules search (across all rulebooks)
    path(
        "rules/search/",
        GlobalRulesSearchView.as_view(),
        name="global_rules_search",
    ),
]

