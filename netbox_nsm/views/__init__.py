from netbox_nsm.rulebooks.views.cot import (
    CotRulebookBulkAssignView,
    CotRulebookChangelogView,
    CotRulebookCreateView,
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
from netbox_nsm.rulebooks.views.assignment import *
from netbox_nsm.security.views import ObjectRulesApiView
from .ip_analysis import IPAnalysisView
from .ip_analysis_api import IpAnalysisApiView
from .ip_analysis_category_api import IpAnalysisCategoryApiView
from .ip_analysis_object_api import IpAnalysisObjectDrilldownApiView
from .ip_analysis_add_object_api import IpAnalysisAddObjectTypesApiView
from .object_analyzer import ObjectAnalyzerView
from .custom_objects_sync import SyncBuiltinToCustomObjectsView, SyncTypeConfigsView
from .type_config import (
    ObjectConfigAddView,
    ObjectConfigDeleteView,
    ObjectConfigEditView,
    ObjectConfigListView,
    ObjectConfigView,
)
from .object_sync import ObjectSyncView
from .inherited_links_api import InheritedLinksApiView
from .object_link import (
    ObjectLinkAssignView,
    ObjectLinkEditView,
    ObjectLinkDeleteView,
    ObjectTypeElementsApiView,
)
from .panel_link_actions import (
    AddressIpamFkClearView,
    AddressIpamFkEditView,
    GroupM2mEditView,
    GroupM2mRemoveView,
)
from .setup import SetupSchemaValidateView, SetupView
