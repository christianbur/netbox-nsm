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
    path(
        "type-config/",
        include(get_model_urls("netbox_nsm", "typeconfig", detail=False)),
    ),
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
        "rulebooks/all-rules/",
        RedirectView.as_view(
            pattern_name="plugins:netbox_nsm:all_rules_rulebook",
            permanent=True,
        ),
        name="all_rules_legacy_overview_redirect",
    ),
    path(
        "rulebooks/all-rules/rules/",
        RedirectView.as_view(
            pattern_name="plugins:netbox_nsm:all_rules_rules",
            permanent=True,
        ),
        name="all_rules_legacy_rules_redirect",
    ),
    path(
        "rulebooks/all-rules/matrix/",
        RedirectView.as_view(
            pattern_name="plugins:netbox_nsm:all_rules_rulebook",
            permanent=True,
        ),
        name="all_rules_legacy_matrix_redirect",
    ),
    path(
        "rulebooks/0/",
        AllRulesRulebookView.as_view(),
        name="all_rules_rulebook",
    ),
    path(
        "rulebooks/0/rules/",
        AllRulesRulebookRulesView.as_view(),
        name="all_rules_rules",
    ),
    path(
        "rulebooks/0/contacts/",
        AllRulesRulebookContactsView.as_view(),
        name="all_rules_contacts",
    ),
    path(
        "rulebooks/0/journal/",
        AllRulesRulebookJournalView.as_view(),
        name="all_rules_journal",
    ),
    path(
        "rulebooks/0/changelog/",
        AllRulesRulebookChangelogView.as_view(),
        name="all_rules_changelog",
    ),
    path(
        "rulebooks/0/matrix/",
        RedirectView.as_view(
            pattern_name="plugins:netbox_nsm:all_rules_rulebook",
            permanent=True,
        ),
        name="all_rules_matrix_redirect",
    ),
    path(
        "rulebooks/<int:pk>/",
        include(get_model_urls("netbox_nsm", "rulebook")),
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
    path("ip-analysis/", IPAnalysisView.as_view(), name="ip_analysis"),
    path("api/ip-analysis/", IpAnalysisApiView.as_view(), name="ip_analysis_api"),
    path("object-analyzer/", ObjectAnalyzerView.as_view(), name="object_analyzer"),
    path(
        "api/rulebooks/<int:pk>/rules-grid/",
        RulebookRulesGridApiView.as_view(),
        name="rulebook_rules_grid_api",
    ),
    path(
        "api/rulebooks/<int:pk>/rules-grid/validate/",
        RulebookRulesGridValidateApiView.as_view(),
        name="rulebook_rules_grid_validate_api",
    ),
    path(
        "api/rulebooks/<int:pk>/matrix-grid/",
        RulebookMatrixGridApiView.as_view(),
        name="rulebook_matrix_grid_api",
    ),
    path(
        "api/rules/all-grid/",
        AllRulesGridApiView.as_view(),
        name="all_rules_grid_api",
    ),
    path(
        "api/rules/all-query-validate/",
        AllRulesQueryValidateApiView.as_view(),
        name="all_rules_query_validate_api",
    ),
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
    path(
        "panel-link/address-ipam-fk/<slug:slug>/clear/",
        AddressIpamFkClearView.as_view(),
        name="address_ipam_fk_clear",
    ),
    path(
        "panel-link/address-ipam-fk/<slug:slug>/edit/",
        AddressIpamFkEditView.as_view(),
        name="address_ipam_fk_edit",
    ),
    path(
        "panel-link/group-m2m/remove/",
        GroupM2mRemoveView.as_view(),
        name="group_m2m_remove",
    ),
    path(
        "panel-link/group-m2m/edit/",
        GroupM2mEditView.as_view(),
        name="group_m2m_edit",
    ),
]
