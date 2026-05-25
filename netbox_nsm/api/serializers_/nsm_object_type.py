from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import NsmObjectType


class NsmObjectTypeSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:nsmobjecttype-detail"
    )

    class Meta:
        model = NsmObjectType
        fields = (
            "id",
            "url",
            "display",
            "name",
            "verbose_name",
            "verbose_name_plural",
            "slug",
            "group_name",
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
            "slug",
        )
