from django.urls import include, path
from django.views.generic import RedirectView
from utilities.urls import get_model_urls

from netbox_nsm.analyzer.api_view import AnalyzerAPIView

from .views import *  # noqa: F401
from .views.plugin_static import PluginAssetView

app_name = "netbox_nsm"

urlpatterns = [
    path(
        "assets/<path:asset_path>",
        PluginAssetView.as_view(),
        name="plugin_asset",
    ),
    path("setup/", SetupView.as_view(), name="setup"),
    path(
        "setup/sync/custom-objects/",
        SyncBuiltinToCustomObjectsView.as_view(),
        name="custom_objects_sync",
    ),
    path(
        "setup/sync/typeconfigs/",
        SyncTypeConfigsView.as_view(),
        name="typeconfigs_sync",
    ),
    path(
        "object/groups/",
        ObjectGroupAreaView.as_view(),
        name="objectgroup_area_root",
    ),
    path(
        "object/groups/<str:area>/",
        ObjectGroupAreaView.as_view(),
        name="objectgroup_area",
    ),
    path("type-config/", TypeConfigListView.as_view(), name="typeconfig_list"),
    path("type-config/add/", TypeConfigAddView.as_view(), name="typeconfig_add"),
    path(
        "type-config/<int:pk>/",
        include(get_model_urls("netbox_nsm", "typeconfig")),
    ),
    path(
        "rulebook-field/add/", RulebookFieldAddView.as_view(), name="rulebookfield_add"
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
        include(get_model_urls("netbox_nsm", "objectgroup", detail=False)),
    ),
    path(
        "object-groups/<int:pk>/",
        include(get_model_urls("netbox_nsm", "objectgroup")),
    ),
    path(
        "rulebooks/",
        include(get_model_urls("netbox_nsm", "rulebook", detail=False)),
    ),
    path(
        "rulebooks/<int:pk>/",
        include(get_model_urls("netbox_nsm", "rulebook")),
    ),
    path(
        "rulebooks/<int:pk>/visualization/",
        RedirectView.as_view(
            pattern_name="plugins:netbox_nsm:rulebook_matrix",
            query_string=True,
            permanent=True,
        ),
        name="rulebook_visualization_redirect",
    ),
    path(
        "rulebooks/<int:pk>/zonematrix/",
        RedirectView.as_view(
            pattern_name="plugins:netbox_nsm:rulebook_matrix",
            query_string=True,
            permanent=True,
        ),
        name="rulebook_zonematrix_redirect",
    ),
    path(
        "rulebooks/<int:pk>/policy/",
        RedirectView.as_view(
            pattern_name="plugins:netbox_nsm:rulebook_rules",
            query_string=True,
            permanent=True,
        ),
        name="rulebook_policy_redirect",
    ),
    path(
        "rulebooks/<int:pk>/bulk-assign/",
        RulebookBulkAssignView.as_view(),
        name="rulebook_bulk_assign",
    ),
    path(
        "rules/",
        include(get_model_urls("netbox_nsm", "rule", detail=False)),
    ),
    path(
        "rules/<int:pk>/",
        include(get_model_urls("netbox_nsm", "rule")),
    ),
    path(
        "rulebook-assignments/",
        include(get_model_urls("netbox_nsm", "rulebookassignment", detail=False)),
    ),
    path(
        "rulebook-assignments/<int:pk>/",
        include(get_model_urls("netbox_nsm", "rulebookassignment")),
    ),
    path("rules/search/", GlobalRulesSearchView.as_view(), name="global_rules_search"),
    path("object-analyzer/", ObjectAnalyzerView.as_view(), name="object_analyzer"),
    path("api/analyzer/", AnalyzerAPIView.as_view(), name="analyzer_api"),
    path("api/object-rules/", ObjectRulesApiView.as_view(), name="object_rules_api"),
    path(
        "api/picker-browse/",
        RulePickerBrowseApiView.as_view(),
        name="rule_picker_browse_api",
    ),
    path(
        "api/rulebooks/<int:pk>/picker-data/",
        RulebookPickerDataApiView.as_view(),
        name="rulebook_picker_data_api",
    ),
    path(
        "api/rules/<int:pk>/field-selections/",
        RuleFieldSelectionsApiView.as_view(),
        name="rule_field_selections_api",
    ),
    path(
        "api/inherited-links/",
        InheritedLinksApiView.as_view(),
        name="inherited_links_api",
    ),
    path(
        "api/type-elements/",
        ObjectTypeElementsApiView.as_view(),
        name="object_type_elements_api",
    ),
    path(
        "object-link/assign/",
        ObjectLinkAssignView.as_view(),
        name="object_link_assign",
    ),
    path(
        "object-link/<int:pk>/edit/",
        ObjectLinkEditView.as_view(),
        name="object_link_edit",
    ),
    path(
        "object-link/<int:pk>/delete/",
        ObjectLinkDeleteView.as_view(),
        name="object_link_delete",
    ),
]
