from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import SecurityZoneMatrixPolicy


class SecurityZoneMatrixPolicySerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityzonematrixpolicy-detail"
    )

    class Meta:
        model = SecurityZoneMatrixPolicy
        fields = (
            "id",
            "url",
            "display",
            "name",
            "action",
            "color",
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
            "action",
            "color",
        )
