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
from netbox_nsm.analysis.ip import (
    IpAnalysisAddObjectTypesApiView,
    IpAnalysisApiView,
    IpAnalysisCategoryApiView,
    IpAnalysisLegacyRedirectView,
    IpAnalysisObjectDrilldownApiView,
)
from netbox_nsm.analysis.analyzer.page_view import ObjectAnalyzerView
from netbox_nsm.object_report.views import ObjectReportView
from .custom_objects_sync import SyncBuiltinToCustomObjectsView, SyncTypeConfigsView
from .type_metadata import (
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
from .rulebook_link import RulebookLinkAssignView, RulebookLinkDeleteView
from .enforcement_point_link import (
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
