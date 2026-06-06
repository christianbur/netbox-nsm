from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0007_remove_virtual_groups"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulebook",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="children",
                to="netbox_nsm.rulebook",
                verbose_name="Parent rulebook",
            ),
        ),
    ]
