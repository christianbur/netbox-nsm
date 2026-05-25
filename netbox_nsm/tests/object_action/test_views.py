from utilities.testing import ViewTestCases, create_tags

from netbox_nsm.models import ObjectAction
from netbox_nsm.tests.custom import ModelViewTestCase


class ObjectActionViewTestCase(
    ModelViewTestCase,
    ViewTestCases.GetObjectViewTestCase,
    ViewTestCases.GetObjectChangelogViewTestCase,
    ViewTestCases.CreateObjectViewTestCase,
    ViewTestCases.EditObjectViewTestCase,
    ViewTestCases.DeleteObjectViewTestCase,
    ViewTestCases.ListObjectsViewTestCase,
    ViewTestCases.BulkImportObjectsViewTestCase,
    ViewTestCases.BulkEditObjectsViewTestCase,
    ViewTestCases.BulkDeleteObjectsViewTestCase,
):
    model = ObjectAction

    @classmethod
    def setUpTestData(cls):
        ObjectAction.objects.all().delete()

        cls.object_actions = (
            ObjectAction(name="action-1", action="permit"),
            ObjectAction(name="action-2", action="deny"),
            ObjectAction(name="action-3", action="count+log"),
        )
        ObjectAction.objects.bulk_create(cls.object_actions)

        tags = create_tags("Alpha", "Bravo", "Charlie")

        cls.form_data = {
            "name": "action-4",
            "action": "permit and log to secops",
            "tags": [t.pk for t in tags],
        }

        cls.bulk_edit_data = {
            "action": "custom free text action",
            "description": "Updated Description",
        }

        cls.csv_data = (
            "name,action",
            "action-5,allow with telemetry",
            "action-6,deny and notify",
            "action-7,count only",
        )

        cls.csv_update_data = (
            "id,name,action,description",
            f"{cls.object_actions[0].pk},action-8,allow temporarily,test1",
            f"{cls.object_actions[1].pk},action-9,block hard,test2",
            f"{cls.object_actions[2].pk},action-10,log and continue,test3",
        )

    maxDiff = None