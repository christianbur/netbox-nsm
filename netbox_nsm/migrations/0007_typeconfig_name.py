from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0005_remove_rulebookfieldtype_show_as_facet_tab"),
        ("netbox_nsm", "0006_securitypolicyrulebook_platform"),
    ]

    operations = [
        migrations.AddField(
            model_name="typeconfig",
            name="name",
            field=models.CharField(
                default="",
                help_text="Display name used as column header and type label throughout NSM.",
                max_length=100,
                verbose_name="Name",
            ),
            preserve_default=False,
        ),
    ]
