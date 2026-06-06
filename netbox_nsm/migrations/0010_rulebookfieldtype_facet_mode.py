from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0009_rulebook_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulebookfieldtype",
            name="facet_mode",
            field=models.CharField(
                choices=[("value", "Value"), ("set", "Set"), ("disabled", "Disabled")],
                default="value",
                help_text="Show this type in the policy facet sidebar. Value counts each value separately; Set counts value combinations.",
                max_length=10,
                verbose_name="Facet Mode",
            ),
        ),
    ]
