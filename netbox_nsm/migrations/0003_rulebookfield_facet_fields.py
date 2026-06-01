from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0002_typeconfig_inherit_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulebookfield",
            name="searchable",
            field=models.BooleanField(
                default=True,
                help_text="Include this field in query searches.",
                verbose_name="Searchable",
            ),
        ),
        migrations.AddField(
            model_name="rulebookfield",
            name="filterable",
            field=models.BooleanField(
                default=True,
                help_text="Allow filtering on this field.",
                verbose_name="Filterable",
            ),
        ),
        migrations.AddField(
            model_name="rulebookfield",
            name="facetable",
            field=models.BooleanField(
                default=False,
                help_text="Show this field in the facet navigation panel.",
                verbose_name="Facetable",
            ),
        ),
        migrations.AddField(
            model_name="rulebookfield",
            name="facet_mode",
            field=models.CharField(
                choices=[("value", "Value"), ("set", "Set")],
                default="value",
                help_text=(
                    "Value: count each individual value separately. "
                    "Set: count the complete combination of values as one entry."
                ),
                max_length=10,
                verbose_name="Facet Mode",
            ),
        ),
        migrations.AddField(
            model_name="rulebookfield",
            name="facet_weight",
            field=models.PositiveIntegerField(
                default=100,
                help_text="Facets with higher weight appear first.",
                verbose_name="Facet Weight",
            ),
        ),
    ]
