from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0002_initial_panel_linkable_types"),
    ]

    operations = [
        migrations.CreateModel(
            name="NsmUiSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "menu_label",
                    models.CharField(
                        default="Security",
                        help_text="Top-level plugin menu entry in the NetBox sidebar.",
                        max_length=100,
                        verbose_name="Menu label",
                    ),
                ),
                (
                    "panel_label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Security card title on object detail pages. Leave empty to reuse the menu label.",
                        max_length=100,
                        verbose_name="Panel label",
                    ),
                ),
            ],
            options={
                "verbose_name": "NSM UI settings",
                "verbose_name_plural": "NSM UI settings",
            },
        ),
    ]
