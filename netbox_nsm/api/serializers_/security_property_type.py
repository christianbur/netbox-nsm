from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import SecurityPropertyType


class SecurityPropertyTypeSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securitypropertytype-detail"
    )

    class Meta:
        model = SecurityPropertyType
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
