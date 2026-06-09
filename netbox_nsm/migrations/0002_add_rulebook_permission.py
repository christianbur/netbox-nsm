from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="cotrulebookassignment",
            options={
                "ordering": ("cot_slug", "assigned_object_id"),
                "permissions": [
                    ("view_rulebook", "Can view rulebooks"),
                    ("add_rulebook", "Can add rulebooks"),
                    ("view_rulebookassignment", "Can view rulebook assignments"),
                    ("add_rulebookassignment", "Can add rulebook assignments"),
                    ("change_rulebookassignment", "Can change rulebook assignments"),
                    ("delete_rulebookassignment", "Can delete rulebook assignments"),
                ],
                "verbose_name": "Rulebook Assignment",
                "verbose_name_plural": "Rulebook Assignments",
            },
        ),
    ]
