from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import SecurityArea

__all__ = ("SecurityAreaSerializer",)


class SecurityAreaSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityarea-detail"
    )

    class Meta:
        model = SecurityArea
        fields = (
            "id",
            "url",
            "display",
            "slug",
            "name",
            "sort_order",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = (
            "id",
            "url",
            "display",
            "slug",
            "name",
            "sort_order",
        )
