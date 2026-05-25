from rest_framework.serializers import (
    HyperlinkedIdentityField,
)
from netbox.api.serializers import PrimaryModelSerializer
from tenancy.api.serializers import TenantSerializer
from ipam.api.field_serializers import IPNetworkField
from netbox_nsm.models import CustomPrefix


class CustomPrefixSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:address-detail"
    )
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    prefix = IPNetworkField(required=False, allow_null=True)

    class Meta:
        model = CustomPrefix
        fields = (
            "id",
            "url",
            "display",
            "prefix",
            "description",
            "tenant",
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
            "prefix",
            "description",
        )
