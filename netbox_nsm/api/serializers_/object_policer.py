from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import ObjectPolicer


class ObjectPolicerSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectpolicer-detail"
    )

    class Meta:
        model = ObjectPolicer
        fields = (
            "id",
            "url",
            "display",
            "name",
            "bandwidth_limit",
            "bandwidth_percent",
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
