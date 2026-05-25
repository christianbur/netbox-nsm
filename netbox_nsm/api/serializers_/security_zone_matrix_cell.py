from drf_spectacular.utils import extend_schema_field
from rest_framework.serializers import HyperlinkedIdentityField, SerializerMethodField, JSONField

from netbox.api.serializers import NetBoxModelSerializer

from netbox_nsm.models import SecurityZoneMatrixCell


class SecurityZoneMatrixCellSerializer(NetBoxModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityzonematrixcell-detail"
    )
    # explicit nested fields for easier API readability
    matrix = SerializerMethodField(read_only=True)
    source_zone = SerializerMethodField(read_only=True)
    destination_zone = SerializerMethodField(read_only=True)
    policy = SerializerMethodField(read_only=True)

    class Meta:
        model = SecurityZoneMatrixCell
        fields = (
            "id",
            "url",
            "display",
            "matrix",
            "source_zone",
            "destination_zone",
            "policy",
            "created",
            "last_updated",
        )
        brief_fields = (
            "id",
            "url",
            "display",
            "matrix",
            "source_zone",
            "destination_zone",
            "policy",
        )

    @extend_schema_field(JSONField(allow_null=True))
    def get_matrix(self, obj):
        return obj.matrix.pk if obj.matrix else None

    @extend_schema_field(JSONField(allow_null=True))
    def get_source_zone(self, obj):
        return obj.source_zone.pk if obj.source_zone else None

    @extend_schema_field(JSONField(allow_null=True))
    def get_destination_zone(self, obj):
        return obj.destination_zone.pk if obj.destination_zone else None

    @extend_schema_field(JSONField(allow_null=True))
    def get_policy(self, obj):
        return obj.policy.pk if obj.policy else None

