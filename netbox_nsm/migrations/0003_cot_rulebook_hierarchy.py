from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0002_add_rulebook_permission"),
    ]

    operations = [
        migrations.CreateModel(
            name="CotRulebook",
            fields=[
                (
                    "slug",
                    models.SlugField(
                        help_text="Slug of the deployed COT rulebook (nsm_rb_<name>).",
                        max_length=100,
                        primary_key=True,
                        serialize=False,
                        verbose_name="Rulebook slug",
                    ),
                ),
                (
                    "parent_slug",
                    models.SlugField(
                        blank=True,
                        default="",
                        help_text="Optional parent rulebook slug for hierarchical grouping.",
                        max_length=100,
                        verbose_name="Parent rulebook slug",
                    ),
                ),
            ],
            options={
                "verbose_name": "COT Rulebook",
                "verbose_name_plural": "COT Rulebooks",
            },
        ),
    ]
