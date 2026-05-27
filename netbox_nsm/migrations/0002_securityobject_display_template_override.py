from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityobject",
            name="display_template_override",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional per-object display template. Overrides the type template.",
                max_length=500,
            ),
        ),
    ]
