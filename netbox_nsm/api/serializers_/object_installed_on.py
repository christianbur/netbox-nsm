from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import ObjectInstalledOn


class ObjectInstalledOnSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectinstalledon-detail"
    )

    class Meta:
        model = ObjectInstalledOn
        fields = (
            "id",
            "url",
            "display",
            "name",
            "device",
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
