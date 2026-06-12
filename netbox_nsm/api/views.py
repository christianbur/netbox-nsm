from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.routers import APIRootView
from netbox.api.viewsets import NetBoxModelViewSet

from .serializers import (
    CotRulebookAssignmentSerializer,
    ObjectLinkSerializer,
    TypeConfigSerializer,
)

from netbox_nsm.models import (
    CotRulebookAssignment,
    TypeConfig,
)

from netbox_nsm.filtersets import (
    CotRulebookAssignmentFilterSet,
    ObjectLinkFilterSet,
    TypeConfigFilterSet,
)

from netbox_nsm.objects.object_link_service import (
    ObjectLinkRecord,
    delete_link,
    get_link_by_pk,
    get_object_link_model,
)


class NetBoxSecurityRootView(APIRootView):
    def get_view_name(self):
        return "NetBoxSecurity"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        data = dict(response.data)
        namespace = request.resolver_match.namespace
        url_name = "ip-analysis"
        if namespace:
            url_name = f"{namespace}:{url_name}"
        data["ip-analysis"] = reverse(
            url_name,
            request=request,
            format=kwargs.get("format"),
        )
        return Response(data)


class CotRulebookAssignmentViewSet(NetBoxModelViewSet):
    queryset = CotRulebookAssignment.objects.all()
    serializer_class = CotRulebookAssignmentSerializer
    filterset_class = CotRulebookAssignmentFilterSet


class ObjectLinkViewSet(NetBoxModelViewSet):
    """CRUD for COT ``nsm_object_link`` rows (legacy ``/object-links/`` path)."""

    queryset = TypeConfig.objects.none()
    serializer_class = ObjectLinkSerializer
    filterset_class = ObjectLinkFilterSet

    def get_queryset(self):
        model = get_object_link_model()
        if model is None:
            return []
        return model.objects.all().order_by("pk")

    def get_object(self):
        record = get_link_by_pk(self.kwargs["pk"])
        if record is None:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        return record.instance

    def perform_destroy(self, instance):
        delete_link(ObjectLinkRecord.from_instance(instance))


class TypeConfigViewSet(NetBoxModelViewSet):
    queryset = TypeConfig.objects.select_related("content_type").prefetch_related(
        "tags"
    )
    serializer_class = TypeConfigSerializer
    filterset_class = TypeConfigFilterSet
