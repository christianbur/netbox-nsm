from django.db import migrations, models
import django.db.models.deletion
import taggit.managers
import utilities.json


def _safe_name(base_name, fallback_prefix, pk):
    base = (base_name or "").strip()
    if not base:
        base = f"{fallback_prefix}-{pk}"
    return base[:150]


def seed_nsm_objects(apps, schema_editor):
    NsmObjectType = apps.get_model("netbox_nsm", "NsmObjectType")
    NsmObject = apps.get_model("netbox_nsm", "NsmObject")

    Address = apps.get_model("netbox_nsm", "Address")
    SecurityZone = apps.get_model("netbox_nsm", "SecurityZone")
    ObjectLabel = apps.get_model("netbox_nsm", "ObjectLabel")
    ObjectSGT = apps.get_model("netbox_nsm", "ObjectSGT")
    ObjectUser = apps.get_model("netbox_nsm", "ObjectUser")
    ObjectGroup = apps.get_model("netbox_nsm", "ObjectGroup")

    type_map = {
        "Address": "builder_address",
        "SecurityZone": "builder_zone",
        "ObjectLabel": "builder_label",
        "ObjectSGT": "builder_sgt",
        "ObjectUser": "builder_user",
        "ObjectGroup": "builder_group",
    }

    object_types = {}
    for source_model, type_name in type_map.items():
        try:
            object_types[source_model] = NsmObjectType.objects.get(name=type_name)
        except NsmObjectType.DoesNotExist:
            object_types[source_model] = None

    def ensure_unique_name(nsm_object_type, base_name, fallback_prefix, source_pk):
        candidate = _safe_name(base_name, fallback_prefix, source_pk)
        if not NsmObject.objects.filter(nsm_object_type=nsm_object_type, name=candidate).exists():
            return candidate
        suffix = f"-{source_pk}"
        head = candidate[: max(1, 150 - len(suffix))]
        return f"{head}{suffix}"

    def upsert(source_model, source_pk, nsm_object_type, base_name, fallback_prefix, payload):
        if nsm_object_type is None:
            return

        existing = NsmObject.objects.filter(
            nsm_object_type=nsm_object_type,
            source_model=source_model,
            source_pk=source_pk,
        ).first()

        if existing:
            updates = {}
            if not existing.object_data:
                updates["object_data"] = payload
            if not existing.name:
                updates["name"] = ensure_unique_name(
                    nsm_object_type,
                    base_name,
                    fallback_prefix,
                    source_pk,
                )
            if updates:
                for key, value in updates.items():
                    setattr(existing, key, value)
                existing.save(update_fields=list(updates.keys()) + ["last_updated"])
            return

        NsmObject.objects.create(
            nsm_object_type=nsm_object_type,
            name=ensure_unique_name(nsm_object_type, base_name, fallback_prefix, source_pk),
            source_model=source_model,
            source_pk=source_pk,
            object_data=payload,
        )

    for obj in Address.objects.all().iterator():
        payload = {
            "name": obj.name,
            "identifier": obj.identifier,
            "dns_name": obj.dns_name,
            "assigned_object_type_id": obj.assigned_object_type_id,
            "assigned_object_id": obj.assigned_object_id,
            "description": obj.description,
        }
        upsert("Address", obj.pk, object_types["Address"], obj.name, "address", payload)

    for obj in SecurityZone.objects.all().iterator():
        payload = {
            "name": obj.name,
            "identifier": obj.identifier,
            "color": obj.color,
            "description": obj.description,
        }
        upsert("SecurityZone", obj.pk, object_types["SecurityZone"], obj.name, "zone", payload)

    for obj in ObjectLabel.objects.all().iterator():
        payload = {
            "label_type": obj.label_type,
            "custom_type": obj.custom_type,
            "name": obj.name,
            "color": obj.color,
            "description": obj.description,
        }
        upsert("ObjectLabel", obj.pk, object_types["ObjectLabel"], obj.name, "label", payload)

    for obj in ObjectSGT.objects.all().iterator():
        payload = {
            "name": obj.name,
            "tag": obj.tag,
            "color": obj.color,
            "description": obj.description,
        }
        upsert("ObjectSGT", obj.pk, object_types["ObjectSGT"], obj.name, "sgt", payload)

    for obj in ObjectUser.objects.all().iterator():
        payload = {
            "entry_type": obj.entry_type,
            "name": obj.name,
            "dn": obj.dn,
            "description": obj.description,
        }
        upsert("ObjectUser", obj.pk, object_types["ObjectUser"], obj.name, "user", payload)

    for obj in ObjectGroup.objects.all().iterator():
        payload = {
            "name": obj.name,
            "group_type": obj.group_type,
            "description": obj.description,
        }
        upsert("ObjectGroup", obj.pk, object_types["ObjectGroup"], obj.name, "group", payload)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0044_seed_builder_object_types"),
        ("users", "0015_owner"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS netbox_nsm_nsmobject CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name="NsmObject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
                ("name", models.CharField(max_length=150)),
                ("object_data", models.JSONField(blank=True, default=dict)),
                ("source_model", models.CharField(blank=True, max_length=64)),
                ("source_pk", models.PositiveBigIntegerField(blank=True, null=True)),
                (
                    "nsm_object_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nsm_objects",
                        to="netbox_nsm.nsmobjecttype",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="users.owner",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "NSM Object",
                "verbose_name_plural": "NSM Objects",
                "ordering": ("nsm_object_type", "name"),
            },
        ),
        migrations.AddConstraint(
            model_name="nsmobject",
            constraint=models.UniqueConstraint(fields=("nsm_object_type", "name"), name="netbox_nsm_nsmobject_unique_type_name"),
        ),
        migrations.AddConstraint(
            model_name="nsmobject",
            constraint=models.UniqueConstraint(fields=("nsm_object_type", "source_model", "source_pk"), name="netbox_nsm_nsmobject_unique_type_source"),
        ),
        migrations.RunPython(seed_nsm_objects, noop_reverse),
    ]
