from rest_framework.routers import APIRootView
from rest_framework.viewsets import GenericViewSet
from netbox.api.viewsets import NetBoxModelViewSet

from .changelog_mixins import (
    RuleAssignmentChangelogMixin,
    RulebookFieldTypeLayoutChangelogMixin,
    RulebookLayoutChangelogMixin,
    RuleRulesChangelogMixin,
)
from .serializers import (
    RulebookSerializer,
    RuleSerializer,
    RulebookAssignmentSerializer,
    ObjectGroupSerializer,
    ObjectLinkSerializer,
    TypeConfigSerializer,
    RulebookFieldSerializer,
    RulebookFieldTypeSerializer,
    RuleObjectItemSerializer,
    RuleGroupItemSerializer,
)

from netbox_nsm.models import (
    Rulebook,
    Rule,
    RulebookAssignment,
    ObjectGroup,
    ObjectLink,
    TypeConfig,
    RulebookField,
    RulebookFieldType,
    RuleObjectItem,
    RuleGroupItem,
)

from netbox_nsm.filtersets import (
    RulebookFilterSet,
    RuleFilterSet,
    RulebookAssignmentFilterSet,
    ObjectGroupFilterSet,
    ObjectLinkFilterSet,
    TypeConfigFilterSet,
    RulebookFieldFilterSet,
    RulebookFieldTypeFilterSet,
    RuleObjectItemFilterSet,
    RuleGroupItemFilterSet,
)


class NetBoxSecurityRootView(APIRootView):
    def get_view_name(self):
        return "NetBoxSecurity"


class RulebookViewSet(NetBoxModelViewSet):
    queryset = Rulebook.objects.prefetch_related("tags")
    serializer_class = RulebookSerializer
    filterset_class = RulebookFilterSet


class RuleViewSet(RuleRulesChangelogMixin, NetBoxModelViewSet):
    queryset = Rule.objects.select_related("rulebook").prefetch_related("tags")
    serializer_class = RuleSerializer
    filterset_class = RuleFilterSet


class RulebookAssignmentViewSet(NetBoxModelViewSet):
    queryset = RulebookAssignment.objects.all()
    serializer_class = RulebookAssignmentSerializer
    filterset_class = RulebookAssignmentFilterSet


class ObjectGroupViewSet(NetBoxModelViewSet):
    queryset = ObjectGroup.objects.prefetch_related("sub_groups", "tags")
    serializer_class = ObjectGroupSerializer
    filterset_class = ObjectGroupFilterSet


class ObjectLinkViewSet(NetBoxModelViewSet):
    queryset = (
        ObjectLink.objects.select_related("object_a_type", "object_b_type")
        .prefetch_related("tags")
        .order_by("pk")
    )
    serializer_class = ObjectLinkSerializer
    filterset_class = ObjectLinkFilterSet


class TypeConfigViewSet(NetBoxModelViewSet):
    queryset = TypeConfig.objects.select_related("content_type").prefetch_related(
        "tags"
    )
    serializer_class = TypeConfigSerializer
    filterset_class = TypeConfigFilterSet


class _PlainModelViewSet(NetBoxModelViewSet):
    def initial(self, request, *args, **kwargs):
        GenericViewSet.initial(self, request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset


class RulebookFieldViewSet(RulebookLayoutChangelogMixin, _PlainModelViewSet):
    queryset = RulebookField.objects.select_related("rulebook").order_by(
        "rulebook", "sort_order", "slug"
    )
    serializer_class = RulebookFieldSerializer
    filterset_class = RulebookFieldFilterSet


class RulebookFieldTypeViewSet(
    RulebookFieldTypeLayoutChangelogMixin, _PlainModelViewSet
):
    queryset = RulebookFieldType.objects.select_related(
        "field", "type_config__content_type"
    ).order_by("field", "sort_order")
    serializer_class = RulebookFieldTypeSerializer
    filterset_class = RulebookFieldTypeFilterSet


class RuleObjectItemViewSet(RuleAssignmentChangelogMixin, _PlainModelViewSet):
    queryset = RuleObjectItem.objects.select_related(
        "rule", "field", "content_type"
    ).order_by("pk")
    serializer_class = RuleObjectItemSerializer
    filterset_class = RuleObjectItemFilterSet


class RuleGroupItemViewSet(RuleAssignmentChangelogMixin, _PlainModelViewSet):
    queryset = RuleGroupItem.objects.select_related(
        "rule", "field", "security_group"
    ).order_by("pk")
    serializer_class = RuleGroupItemSerializer
    filterset_class = RuleGroupItemFilterSet
