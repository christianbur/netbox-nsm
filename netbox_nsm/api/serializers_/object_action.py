from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import ObjectAction


class ObjectActionSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectaction-detail"
    )

    class Meta:
        model = ObjectAction
        fields = (
            "id",
            "url",
            "display",
            "name",
            "action",
            "description",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = ("id", "url", "display", "name", "action")
