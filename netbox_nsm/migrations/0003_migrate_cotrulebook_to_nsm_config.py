from django.db import migrations


def migrate_cotrulebook_to_nsm_config(apps, schema_editor):
    CotRulebook = apps.get_model("netbox_nsm", "CotRulebook")
    CustomObjectType = apps.get_model("netbox_custom_objects", "CustomObjectType")

    from netbox_nsm.objects.rulebook_config import (
        merge_rulebook_config_into_comments,
        normalize_rulebook_config,
    )

    for row in CotRulebook.objects.all():
        cot = CustomObjectType.objects.filter(slug=row.slug).first()
        if cot is None:
            continue
        config = normalize_rulebook_config(
            {
                "parent_slug": row.parent_slug or "",
                "matrix_tab_enabled": row.matrix_tab_enabled,
                "row_group_by_col_id": row.row_group_by_col_id or "",
            }
        )
        new_comments = merge_rulebook_config_into_comments(cot.comments or "", config)
        if cot.comments != new_comments:
            cot.comments = new_comments
            cot.save(update_fields=["comments"])


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0002_cotrulebook_row_group_by_col_id"),
        ("netbox_custom_objects", "0014_fix_mixed_case_field_names"),
    ]

    operations = [
        migrations.RunPython(
            migrate_cotrulebook_to_nsm_config,
            migrations.RunPython.noop,
        ),
        migrations.DeleteModel(
            name="CotRulebook",
        ),
    ]
