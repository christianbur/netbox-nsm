from django.db import migrations, models


def _normalize_color(value):
    if not value:
        return "#808080"

    value = value.strip()
    if value.startswith("#"):
        hex_part = value[1:]
        if len(hex_part) == 3 and all(c in "0123456789abcdefABCDEF" for c in hex_part):
            return "#" + "".join(c * 2 for c in hex_part).lower()
        if len(hex_part) == 6 and all(c in "0123456789abcdefABCDEF" for c in hex_part):
            return "#" + hex_part.lower()

    named_colors = {
        "gray": "#808080",
        "grey": "#808080",
        "red": "#ff0000",
        "green": "#008000",
        "blue": "#0000ff",
        "yellow": "#ffff00",
        "orange": "#ffa500",
        "purple": "#800080",
        "brown": "#a52a2a",
        "black": "#000000",
        "white": "#ffffff",
    }
    return named_colors.get(value.lower(), "#808080")


def _normalize_type(raw):
    text = (raw or "").strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    if text in {"environment", "env"}:
        return "environment"
    if text in {"application", "app"}:
        return "application"
    if text in {"servicecategory", "servicecategories"}:
        return "servicecategory"
    if text in {"servicerole", "serviceroles"}:
        return "servicerole"
    return "other"


def migrate_object_labels(apps, schema_editor):
    ObjectLabel = apps.get_model("netbox_nsm", "ObjectLabel")

    for label in ObjectLabel.objects.all():
        inferred_type = _normalize_type(getattr(label, "type_short", ""))
        if inferred_type == "other":
            inferred_type = _normalize_type(getattr(label, "type_long", ""))

        label.label_type = inferred_type
        if inferred_type == "other":
            label.custom_type = (getattr(label, "type_long", "") or getattr(label, "type_short", "") or "Other").strip()[:100]
        else:
            label.custom_type = ""

        label.color = _normalize_color(getattr(label, "color", ""))
        label.save(update_fields=["label_type", "custom_type", "color"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0039_remove_application_saas"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="objectlabel",
            name="netbox_nsm_objectlabel_unique_type_short_name",
        ),
        migrations.AddField(
            model_name="objectlabel",
            name="label_type",
            field=models.CharField(
                choices=[
                    ("environment", "Environment"),
                    ("application", "Application"),
                    ("servicecategory", "ServiceCategory"),
                    ("servicerole", "ServiceRole"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="objectlabel",
            name="custom_type",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AlterField(
            model_name="objectlabel",
            name="color",
            field=models.CharField(default="#808080", max_length=7),
        ),
        migrations.RunPython(migrate_object_labels, noop_reverse),
        migrations.RemoveField(
            model_name="objectlabel",
            name="type_short",
        ),
        migrations.RemoveField(
            model_name="objectlabel",
            name="type_long",
        ),
        migrations.AlterModelOptions(
            name="objectlabel",
            options={
                "ordering": ("label_type", "custom_type", "name"),
                "verbose_name": "Label",
                "verbose_name_plural": "Labels",
            },
        ),
        migrations.AddConstraint(
            model_name="objectlabel",
            constraint=models.UniqueConstraint(
                fields=("label_type", "custom_type", "name"),
                name="netbox_nsm_objectlabel_unique_label_type_custom_type_name",
            ),
        ),
    ]
