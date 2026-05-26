from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0074_security_rule_groups"),
    ]

    operations = [
        migrations.AddField(
            model_name="objectcustomtype",
            name="display_template",
            field=models.CharField(
                blank=True,
                default="",
                max_length=500,
                help_text=(
                    "Display template for objects of this type. "
                    "Use {name} and field data keys, e.g. \"{name} ({port}/{protocol})\". "
                    "If empty, the object name is used."
                ),
            ),
        ),
        migrations.AddField(
            model_name="securityzonepolicyrulebook",
            name="rule_comment_template",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Markdown comment template pre-filled when adding new rules. "
                    "Supports {rule_name}, {index}, {rulebook}."
                ),
            ),
        ),
    ]
