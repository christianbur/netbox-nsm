from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0004_rulebookfieldtype_show_as_facet_tab"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="rulebookfieldtype",
            name="show_as_facet_tab",
        ),
    ]
