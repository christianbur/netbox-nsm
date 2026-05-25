from rest_framework.serializers import HyperlinkedIdentityField, IntegerField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import SecurityZoneRole


class SecurityZoneRoleSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityzonerole-detail"
    )
    zone_count = IntegerField(read_only=True)

    class Meta:
        model = SecurityZoneRole
        fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "zone_count",
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
            "description",
            "zone_count",
        )
