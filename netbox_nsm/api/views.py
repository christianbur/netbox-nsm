from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.routers import APIRootView
from rest_framework.views import APIView
from netbox.api.authentication import TokenPermissions
from netbox.api.viewsets import NetBoxModelViewSet
from users.models import Token

from .serializers import ObjectLinkSerializer

from netbox_nsm.filtersets import ObjectLinkFilterSet

from netbox_nsm.objects.object_link_service import (
    ObjectLinkRecord,
    delete_link,
    get_link_by_pk,
    get_object_link_model,
    object_link_permission,
)

# Map HTTP methods to the COT permission *action* used by ``object_link_permission``.
# Mirrors ``netbox.api.viewsets.HTTP_ACTIONS`` but is kept local so the API layer
# resolves the dynamic ``nsm_object_link`` permission the same way the UI views do.
_METHOD_TO_ACTION = {
    "GET": "view",
    "HEAD": "view",
    "OPTIONS": "view",
    "POST": "add",
    "PUT": "change",
    "PATCH": "change",
    "DELETE": "delete",
}


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


class ObjectLinkPermission(TokenPermissions):
    """Explicit, UI-consistent authorization for the dynamic ``nsm_object_link`` COT.

    ``ObjectLinkViewSet`` has no static ``queryset.model`` (its model is the
    ``nsm_object_link`` Custom Object Type, resolved at request time), so the
    stock model-based permission machinery cannot derive the required permission
    codename. This class derives it via ``object_link_permission()`` — the *same*
    helper the UI views (`views/object_link.py`) use — so REST and UI enforce the
    identical ``netbox_custom_objects.<action>_<model>`` permission.

    Token write-ability for unsafe methods is still honored (parity with
    ``TokenPermissions``). When the COT is not deployed (no model, no codename),
    read methods are allowed (nothing to expose, list is empty) and writes are
    denied.
    """

    def _required_permission(self, request):
        action = _METHOD_TO_ACTION.get(request.method)
        if action is None:
            return None
        return object_link_permission(action)

    def has_permission(self, request, view):
        # Enforce Token write ability for unsafe methods (parity with TokenPermissions).
        if isinstance(request.auth, Token) and not self._verify_write_permission(request):
            return False

        user = getattr(request, "user", None)
        if user is None or (self.authenticated_users_only and not user.is_authenticated):
            return False

        if request.method == "OPTIONS":
            return True

        perm = self._required_permission(request)
        if perm is None:
            # COT not deployed: allow read-only access, deny writes.
            return request.method in SAFE_METHODS
        return user.has_perm(perm)

    def has_object_permission(self, request, view, obj):
        if isinstance(request.auth, Token) and not self._verify_write_permission(request):
            return False

        perm = self._required_permission(request)
        if perm is None:
            return request.method in SAFE_METHODS
        return request.user.has_perm(perm)


class ObjectLinkViewSet(NetBoxModelViewSet):
    """CRUD for COT ``nsm_object_link`` rows (legacy ``/object-links/`` path)."""

    queryset = []
    serializer_class = ObjectLinkSerializer
    filterset_class = ObjectLinkFilterSet
    permission_classes = [ObjectLinkPermission]

    def initial(self, request, *args, **kwargs):
        # NetBoxModelViewSet.initial() applies ``self.queryset.restrict()``, which
        # assumes a static RestrictedQuerySet. This ViewSet's model is the dynamic
        # ``nsm_object_link`` COT, so we run DRF's auth / permission
        # (ObjectLinkPermission) / throttle pipeline via APIView.initial(), then
        # resolve and restrict the real COT queryset ourselves (cleanly skipping it
        # when the COT is not deployed instead of raising on a plain list).
        APIView.initial(self, request, *args, **kwargs)

        model = get_object_link_model()
        if model is None:
            return
        qs = model.objects.all().order_by("pk")
        if request.user.is_authenticated:
            action = _METHOD_TO_ACTION.get(request.method)
            if action and hasattr(qs, "restrict"):
                qs = qs.restrict(request.user, action)
        # Expose a real queryset so the model-dependent NetBoxModelViewSet machinery
        # (perform_create/update/destroy, serializer context) keeps working.
        self.queryset = qs

    def get_queryset(self):
        # Prefer the per-request (restricted) queryset resolved in initial().
        if hasattr(self.queryset, "model"):
            return self.queryset
        model = get_object_link_model()
        if model is None:
            return []
        return model.objects.all().order_by("pk")

    def get_object(self):
        record = get_link_by_pk(self.kwargs["pk"])
        if record is None:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        self.check_object_permissions(self.request, record.instance)
        return record.instance

    def perform_destroy(self, instance):
        delete_link(ObjectLinkRecord.from_instance(instance))
