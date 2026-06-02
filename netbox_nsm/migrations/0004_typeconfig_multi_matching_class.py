from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Allow multiple TypeConfig entries per ContentType (differentiated by matching_class).

    - Changes TypeConfig.content_type from OneToOneField → ForeignKey
    - Adds unique_together = (content_type, matching_class)
    - Drops the legacy DB column 'inherit_parent_links' (never tracked in migrations)
    """

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("netbox_nsm", "0003_rulebookfield_facet_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="typeconfig",
            name="content_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="nsm_matching_configs",
                to="contenttypes.contenttype",
                verbose_name="Object Type",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="typeconfig",
            unique_together={("content_type", "matching_class")},
        ),
        migrations.RunSQL(
            sql="ALTER TABLE netbox_nsm_typeconfig DROP COLUMN IF EXISTS inherit_parent_links",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
