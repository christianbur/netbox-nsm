from netbox_nsm.rulebooks.views.cot import (
    CotRulebookBulkAssignView,
    CotRulebookChangelogView,
    CotRulebookCreateView,
    CotRulebookDeleteView,
    CotRulebookSchemaValidateView,
    CotRulebookMatrixView,
    CotRulebookRulesView,
    CotRulebookView,
)
from netbox_nsm.rulebooks.views.list import RulebookListView
from netbox_nsm.rulebooks.views.virtual_all import (
    AllRulesRulebookChangelogView,
    AllRulesRulebookContactsView,
    AllRulesRulebookJournalView,
    AllRulesRulebookRulesView,
    AllRulesRulebookView,
)
from netbox_nsm.analyzers.ip_analyzer.endpoints import (
    IpAnalyzerAddObjectTypesApiView,
    IpAnalyzerApiView,
    IpAnalyzerCategoryApiView,
    IpAnalyzerLegacyRedirectView,
    IpAnalyzerObjectDrilldownApiView,
)
from netbox_nsm.analyzers.object_analyzer.page_view import ObjectAnalyzerView
from netbox_nsm.analyzers.object_report.views import ObjectReportView
from .custom_objects_sync import SyncBuiltinToCustomObjectsView, SyncTypeConfigsView
from netbox_nsm.type_metadata.views import (
    TypeMetadataAddView,
    TypeMetadataDeleteView,
    TypeMetadataEditView,
    TypeMetadataListView,
    TypeMetadataView,
)
from netbox_nsm.security.views.inherited_links_api import InheritedLinksApiView
from netbox_nsm.security.views.object_link import (
    ObjectLinkAssignView,
    ObjectLinkEditView,
    ObjectLinkDeleteView,
    ObjectTypeElementsApiView,
)
from netbox_nsm.security.views.rulebook_link import RulebookLinkAssignView, RulebookLinkDeleteView
from netbox_nsm.security.views.enforcement_point_link import (
    EnforcementPointInterfaceAssignView,
    EnforcementPointLinkDeleteView,
)
from netbox_nsm.security.actions.confirm_views import (
    AddressIpamFkClearView,
    AddressIpamFkEditView,
    GroupM2mEditView,
    GroupM2mRemoveView,
)
from netbox_nsm.bundles.views import (
    SetupSchemaApplyView,
    SetupSchemaDetailView,
    SetupSchemaPreviewView,
    SetupView,
)
