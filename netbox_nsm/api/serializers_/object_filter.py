from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import ObjectFilter


class ObjectFilterSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectfilter-detail"
    )

    class Meta:
        model = ObjectFilter
        fields = (
            "id",
            "url",
            "display",
            "name",
            "family",
            "rules",
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
            "family",
        )
