from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0041_securityzone_color"),
    ]

    operations = [
                migrations.SeparateDatabaseAndState(
                        database_operations=[
                                migrations.RunSQL(
                                        sql="""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
            AND table_name = 'netbox_nsm_objectuser'
            AND column_name = 'value'
    )
    AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
            AND table_name = 'netbox_nsm_objectuser'
            AND column_name = 'dn'
    ) THEN
        ALTER TABLE public.netbox_nsm_objectuser RENAME COLUMN value TO dn;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
            AND table_name = 'netbox_nsm_objectuser'
            AND column_name = 'name'
    ) THEN
        ALTER TABLE public.netbox_nsm_objectuser ADD COLUMN name varchar(100) NOT NULL DEFAULT '';
    END IF;

    UPDATE public.netbox_nsm_objectuser
    SET name = COALESCE(NULLIF(BTRIM(SPLIT_PART(dn, ',', 1)), ''), dn, 'Unknown');

    UPDATE public.netbox_nsm_objectuser
    SET name = BTRIM(SUBSTRING(name FROM POSITION('=' IN name) + 1))
    WHERE POSITION('=' IN name) > 0;

    ALTER TABLE public.netbox_nsm_objectuser ALTER COLUMN name DROP DEFAULT;

    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'netbox_nsm_objectuser_unique_entry_type_value'
    ) THEN
        ALTER TABLE public.netbox_nsm_objectuser DROP CONSTRAINT netbox_nsm_objectuser_unique_entry_type_value;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'netbox_nsm_objectuser_entry_type_dn_4731e1f8_uniq'
    ) THEN
        ALTER TABLE public.netbox_nsm_objectuser
            ADD CONSTRAINT netbox_nsm_objectuser_entry_type_dn_4731e1f8_uniq UNIQUE (entry_type, dn);
    END IF;
END
$$;
""",
                                        reverse_sql=migrations.RunSQL.noop,
                                ),
                        ],
                        state_operations=[
                                migrations.RenameField(
                                        model_name="objectuser",
                                        old_name="value",
                                        new_name="dn",
                                ),
                                migrations.AddField(
                                        model_name="objectuser",
                                        name="name",
                                        field=models.CharField(default="", max_length=100),
                                        preserve_default=False,
                                ),
                                migrations.AlterModelOptions(
                                        name="objectuser",
                                        options={
                                                "ordering": ("entry_type", "name"),
                                                "verbose_name": "User",
                                                "verbose_name_plural": "Users",
                                        },
                                ),
                                migrations.AlterUniqueTogether(
                                        name="objectuser",
                                        unique_together={("entry_type", "dn")},
                                ),
                        ],
        ),
        ]
