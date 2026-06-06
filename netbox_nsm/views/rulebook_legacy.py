"""
LEGACY — deaktivierte Rulebook-Views (Tabs /zonematrix/ und /policy/).

Nicht mehr via @register_model_view eingebunden. Templates unter
``templates/netbox_nsm/legacy/``. Alte URLs leiten auf /matrix/ bzw. /rules/ um.
"""

from django.utils.translation import gettext_lazy as _

from netbox.views import generic
from utilities.views import ViewTab

from netbox_nsm.models import Rulebook

__all__ = (
    "RulebookVisualizationView",
    "RulebookRulesView",
)


class RulebookVisualizationView(generic.ObjectView):
    """Klassische HTML-Zonenmatrix — ersetzt durch ``RulebookMatrixGridView`` (/matrix/)."""

    queryset = Rulebook.objects.all()
    template_name = "netbox_nsm/legacy/rulebook_matrix.html"
    tab = ViewTab(
        label=_("Zone Matrix"),
        permission="netbox_nsm.view_rulebook",
        weight=300,
    )

    def get_extra_context(self, request, instance):
        from netbox_nsm.matrix_tab_context import build_matrix_tab_context
        import netbox_nsm.views.rulebook as rulebook_views

        return build_matrix_tab_context(request, instance, view_helpers=rulebook_views)


class RulebookRulesView(generic.ObjectView):
    """Klassische Policy-Tabelle — ersetzt durch ``RulebookRulesGridView`` (/rules/)."""

    queryset = Rulebook.objects.all().prefetch_related("rules")
    template_name = "netbox_nsm/legacy/rulebook_policy_classic.html"
    tab = ViewTab(
        label=_("Policy"),
        permission="netbox_nsm.view_rulebook",
        weight=100,
        hide_if_empty=True,
    )

    def get_extra_context(self, request, instance):
        from netbox_nsm import policy_tab_context
        import netbox_nsm.views.rulebook as rulebook_views

        ctx = policy_tab_context.build_policy_tab_context(
            request,
            instance,
            view_helpers=rulebook_views,
            grid_all_rules=False,
        )
        ctx["use_ag_grid"] = False
        ctx["policy_tab_label"] = self.tab.label
        ctx["policy_tab_key"] = "policy"
        return ctx
