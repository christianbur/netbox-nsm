from django.urls import include, path
from django.views.generic import RedirectView
from utilities.urls import get_model_urls

from netbox_nsm.analyzer.api_view import AnalyzerAPIView

from .views import *  # noqa: F401
from .views.plugin_static import PluginAssetView
from netbox_nsm.rulebooks.views.list import RulebookListView

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
        "type-config/",
        include(get_model_urls("netbox_nsm", "typeconfig", detail=False)),
    ),
    path(
        "type-config/<int:pk>/",
        include(get_model_urls("netbox_nsm", "typeconfig")),
    ),
    path("rulebooks/", RulebookListView.as_view(), name="rulebook_list"),
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
        "rulebooks/cot/add/",
        CotRulebookCreateView.as_view(),
        name="cot_rulebook_add",
    ),
    path(
        "rulebooks/cot/<slug:slug>/",
        CotRulebookView.as_view(),
        name="cot_rulebook",
    ),
    path(
        "rulebooks/cot/<slug:slug>/assign/",
        CotRulebookBulkAssignView.as_view(),
        name="cot_rulebook_bulk_assign",
    ),
    path(
        "rulebooks/cot/<slug:slug>/rules/",
        CotRulebookRulesView.as_view(),
        name="cot_rulebook_rules",
    ),
    path(
        "rulebooks/cot/<slug:slug>/matrix/",
        CotRulebookMatrixView.as_view(),
        name="cot_rulebook_matrix",
    ),
    path(
        "rulebooks/cot/<slug:slug>/changelog/",
        CotRulebookChangelogView.as_view(),
        name="cot_rulebook_changelog",
    ),
    path(
        "rulebook-assignments/",
        include(
            get_model_urls("netbox_nsm", "cotrulebookassignment", detail=False)
        ),
    ),
    path(
        "rulebook-assignments/<int:pk>/",
        include(get_model_urls("netbox_nsm", "cotrulebookassignment")),
    ),
    path(
        "rules/search/",
        RedirectView.as_view(
            pattern_name="plugins:netbox_nsm:all_rules_rules",
            permanent=False,
        ),
        name="global_rules_search",
    ),
    path("ip-analysis/", IPAnalysisView.as_view(), name="ip_analysis"),
    path("api/ip-analysis/", IpAnalysisApiView.as_view(), name="ip_analysis_api"),
    path(
        "api/ip-analysis/category/",
        IpAnalysisCategoryApiView.as_view(),
        name="ip_analysis_category_api",
    ),
    path(
        "api/ip-analysis/object/",
        IpAnalysisObjectDrilldownApiView.as_view(),
        name="ip_analysis_object_api",
    ),
    path(
        "api/ip-analysis/add-object-types/",
        IpAnalysisAddObjectTypesApiView.as_view(),
        name="ip_analysis_add_object_types_api",
    ),
    path("object-analyzer/", ObjectAnalyzerView.as_view(), name="object_analyzer"),
    path("api/analyzer/", AnalyzerAPIView.as_view(), name="analyzer_api"),
    path("api/object-rules/", ObjectRulesApiView.as_view(), name="object_rules_api"),
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
