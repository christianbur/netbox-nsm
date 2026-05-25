from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0064_objectcustomtype_icon"),
    ]

    operations = [
        migrations.AddField(
            model_name="objectcustomobjectassignment",
            name="comment",
            field=models.CharField(blank=True, default="", max_length=200, verbose_name="Comment"),
        ),
    ]
