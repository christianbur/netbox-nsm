from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import NetBoxModelSerializer, PrimaryModelSerializer

from netbox_nsm.api.serializers_.security_zone_role import SecurityZoneRoleSerializer
from netbox_nsm.models import SecurityZoneMatrix


class SecurityZoneMatrixSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityzonematrix-detail"
    )
    roles = SecurityZoneRoleSerializer(many=True, nested=True, required=False)

    class Meta:
        model = SecurityZoneMatrix
        fields = (
            "id",
            "url",
            "display",
            "name",
            "roles",
            "description",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = (
            "id",
            "url",
            "display",
            "name",
        )

    def create(self, validated_data):
        roles = validated_data.pop("roles", None)
        obj = super().create(validated_data)
        if roles is not None:
            obj.roles.set(roles)
        return obj

    def update(self, instance, validated_data):
        roles = validated_data.pop("roles", None)
        obj = super().update(instance, validated_data)
        if roles is not None:
            obj.roles.set(roles)
        return obj
