from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0046_objectgroup_nested_groups"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE netbox_nsm_objectgroup "
                        "ADD COLUMN IF NOT EXISTS group_member_type varchar(20) NOT NULL DEFAULT '';"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[
                migrations.AddField(
                    model_name="objectgroup",
                    name="group_member_type",
                    field=models.CharField(
                        blank=True,
                        choices=[
                            ("addresses", "Addresses"),
                            ("services", "Services"),
                            ("applications", "Applications"),
                            ("labels", "Labels"),
                            ("zones", "Zones"),
                            ("sgts", "SGTs"),
                            ("users", "Users"),
                        ],
                        default="",
                        max_length=20,
                    ),
                ),
            ],
        ),
    ]
