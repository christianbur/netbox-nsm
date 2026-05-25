from rest_framework.serializers import (
    HyperlinkedIdentityField,
    ChoiceField,
    ListField,
    IntegerField,
    ValidationError,
)
from netbox.api.serializers import PrimaryModelSerializer
from netbox_nsm.models import ApplicationItem
from netbox_nsm.choices import ProtocolChoices


class ApplicationItemSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:applicationitem-detail"
    )
    protocol = ListField(
        child=ChoiceField(choices=ProtocolChoices, required=False),
        required=False,
        default=[],
    )
    source_ports = ListField(
        child=IntegerField(),
        required=False,
        allow_empty=True,
        default=[],
    )
    destination_ports = ListField(
        child=IntegerField(),
        required=True,
        allow_empty=False,
    )

    def validate_destination_ports(self, value):
        if not value:
            raise ValidationError("Destination ports are required.")
        return value

    def validate_protocol(self, value):
        if not value:
            raise ValidationError("A protocol selection is required.")
        if len(value) != 1:
            raise ValidationError("Protocol must be a single selection.")
        return value

    def create(self, validated_data):
        if validated_data.get("index") is None:
            validated_data["index"] = ApplicationItem.get_next_index()
        return super().create(validated_data)

    class Meta:
        model = ApplicationItem
        fields = (
            "id",
            "url",
            "display",
            "name",
            "index",
            "protocol",
            "destination_ports",
            "source_ports",
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
            "index",
            "protocol",
            "destination_ports",
            "source_ports",
            "description",
        )
