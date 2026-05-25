from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer
from ipam.api.serializers import (
    IPAddressSerializer,
    PrefixSerializer,
    IPRangeSerializer,
)
from netbox_nsm.models import (
    NatPoolMember,
)

from netbox_nsm.api.serializers import NatPoolSerializer


class NatPoolMemberSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:natpoolmember-detail"
    )
    pool = NatPoolSerializer(nested=True, required=True, allow_null=False)
    address = IPAddressSerializer(nested=True, required=False, allow_null=True)
    prefix = PrefixSerializer(nested=True, required=False, allow_null=True)
    address_range = IPRangeSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = NatPoolMember
        fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "pool",
            "status",
            "address",
            "prefix",
            "address_range",
            "source_ports",
            "destination_ports",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = ("id", "url", "display", "name", "pool", "status")
