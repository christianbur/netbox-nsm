from django.urls import include, path
from django.views.generic import RedirectView
from utilities.urls import get_model_urls

from netbox_nsm.analyzer.api_view import AnalyzerAPIView

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
    path(
        "object-builder/<str:tab>/", ObjectBuilderView.as_view(), name="object_builder"
    ),
    path(
        "object-builder/demo/custom-objects/",
        CustomObjectsDemoView.as_view(),
        name="custom_objects_demo",
    ),
    path(
        "object-builder/sync/custom-objects/",
        SyncBuiltinToCustomObjectsView.as_view(),
        name="custom_objects_sync",
    ),
    # Groups area — must come before generic object/<str:tab>/ to avoid conflict
    path(
        "object/groups/",
        SecurityObjectGroupAreaView.as_view(),
        name="securityobjectgroup_area_root",
    ),
    path(
        "object/groups/<str:area>/",
        SecurityObjectGroupAreaView.as_view(),
        name="securityobjectgroup_area",
    ),
    # Setup
    path("setup/", SetupView.as_view(), name="setup"),
    # TypeConfig
    path(
        "type-config/",
        TypeConfigListView.as_view(),
        name="typeconfig_list",
    ),
    path(
        "type-config/add/",
        TypeConfigAddView.as_view(),
        name="typeconfig_add",
    ),
    path(
        "type-config/<int:pk>/",
        include(get_model_urls("netbox_nsm", "typeconfig")),
    ),
    # RulebookField CRUD
    path(
        "rulebook-field/add/",
        RulebookFieldAddView.as_view(),
        name="rulebookfield_add",
    ),
    path(
        "rulebook-field/<int:pk>/edit/",
        RulebookFieldEditView.as_view(),
        name="rulebookfield_edit",
    ),
    path(
        "rulebook-field/<int:pk>/delete/",
        RulebookFieldDeleteView.as_view(),
        name="rulebookfield_delete",
    ),
    # RulebookFieldType CRUD
    path(
        "rulebook-field-type/add/",
        RulebookFieldTypeAddView.as_view(),
        name="rulebookfieldtype_add",
    ),
    path(
        "rulebook-field-type/<int:pk>/edit/",
        RulebookFieldTypeEditView.as_view(),
        name="rulebookfieldtype_edit",
    ),
    path(
        "rulebook-field-type/<int:pk>/delete/",
        RulebookFieldTypeDeleteView.as_view(),
        name="rulebookfieldtype_delete",
    ),
    path(
        "object-groups/",
        include(get_model_urls("netbox_nsm", "securityobjectgroup", detail=False)),
    ),
    path(
        "object-groups/<int:pk>/",
        include(get_model_urls("netbox_nsm", "securityobjectgroup")),
    ),
    # Security Policy
    path(
        "security-policy/",
        include(get_model_urls("netbox_nsm", "securitypolicyrulebook", detail=False)),
    ),
    path(
        "security-policy/<int:pk>/",
        include(get_model_urls("netbox_nsm", "securitypolicyrulebook")),
    ),
    path(
        "security-policy/<int:pk>/visualization/",
        RedirectView.as_view(
            pattern_name="plugins:netbox_nsm:securitypolicyrulebook_visualization",
            query_string=True,
        ),
        name="securitypolicyrulebook_visualization_redirect",
    ),
    path(
        "security-policy/<int:pk>/bulk-assign/",
        SecurityPolicyRulebookBulkAssignView.as_view(),
        name="securitypolicyrulebook_bulk_assign",
    ),
    path(
        "security-rule/",
        include(get_model_urls("netbox_nsm", "securitypolicyrule", detail=False)),
    ),
    path(
        "security-rule/<int:pk>/",
        include(get_model_urls("netbox_nsm", "securitypolicyrule")),
    ),
    path(
        "security-zone-policy-rulebook-assignments/",
        include(get_model_urls("netbox_nsm", "securitypolicyassignment", detail=False)),
    ),
    path(
        "security-zone-policy-rulebook-assignments/<int:pk>/",
        include(get_model_urls("netbox_nsm", "securitypolicyassignment")),
    ),
    # Global Rules Search
    path(
        "security-rule/search/",
        GlobalRulesSearchView.as_view(),
        name="global_rules_search",
    ),
    # Object Analyzer
    path(
        "object-analyzer/",
        ObjectAnalyzerView.as_view(),
        name="object_analyzer",
    ),
    # Object Analyzer JSON API
    path(
        "api/analyzer/",
        AnalyzerAPIView.as_view(),
        name="analyzer_api",
    ),
    # Lazy-load API: rules for a given object
    path(
        "api/object-rules/",
        ObjectRulesApiView.as_view(),
        name="object_rules_api",
    ),
    # Lazy-load API: inherited links for IPAM objects
    path(
        "api/inherited-links/",
        InheritedLinksApiView.as_view(),
        name="inherited_links_api",
    ),
    # Lazy-load API: elements of an NSMTypeConfig type
    path(
        "api/type-elements/",
        NSMObjectTypeElementsApiView.as_view(),
        name="object_type_elements_api",
    ),
    # NSMObjectLink assign / edit / delete
    path(
        "object-link/assign/",
        NSMObjectLinkAssignView.as_view(),
        name="nsm_object_link_assign",
    ),
    path(
        "object-link/<int:pk>/edit/",
        NSMObjectLinkEditView.as_view(),
        name="nsm_object_link_edit",
    ),
    path(
        "object-link/<int:pk>/delete/",
        NSMObjectLinkDeleteView.as_view(),
        name="nsm_object_link_delete",
    ),
]
