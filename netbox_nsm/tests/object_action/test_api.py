from utilities.testing import APIViewTestCases

from netbox_nsm.models import ObjectAction
from netbox_nsm.tests.custom import APITestCase, NetBoxSecurityGraphQLMixin


class ObjectActionAPITestCase(
    APITestCase,
    APIViewTestCases.GetObjectViewTestCase,
    APIViewTestCases.ListObjectsViewTestCase,
    APIViewTestCases.CreateObjectViewTestCase,
    APIViewTestCases.UpdateObjectViewTestCase,
    APIViewTestCases.DeleteObjectViewTestCase,
    NetBoxSecurityGraphQLMixin,
    APIViewTestCases.GraphQLTestCase,
):
    model = ObjectAction

    brief_fields = [
        "action",
        "description",
        "display",
        "id",
        "name",
        "url",
    ]

    create_data = [
        {"name": "action-1", "action": "allow with inspection"},
        {"name": "action-2", "action": "deny and alert"},
        {"name": "action-3", "action": "log only for 7 days"},
    ]

    bulk_update_data = {
        "action": "custom updated action",
        "description": "Test Object Actions",
    }

    @classmethod
    def setUpTestData(cls):
        ObjectAction.objects.all().delete()

        object_actions = (
            ObjectAction(name="action-4", action="permit"),
            ObjectAction(name="action-5", action="deny"),
            ObjectAction(name="action-6", action="allow with audit trail"),
        )
        ObjectAction.objects.bulk_create(object_actions)