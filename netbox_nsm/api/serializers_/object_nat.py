from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import ObjectNAT


class ObjectNATSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectnat-detail"
    )

    class Meta:
        model = ObjectNAT
        fields = (
            "id",
            "url",
            "display",
            "name",
            "nat_type",
            "source_address",
            "source_prefix",
            "destination_address",
            "destination_prefix",
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
            "nat_type",
        )
