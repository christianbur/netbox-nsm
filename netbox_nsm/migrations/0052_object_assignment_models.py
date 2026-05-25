import django.db.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("extras", "0001_initial"),
        ("netbox_nsm", "0051_alter_objectaction_action"),
    ]

    operations = [
        # ObjectLabelAssignment
        migrations.CreateModel(
            name="ObjectLabelAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
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
                (
                    "assigned_object_id",
                    models.PositiveBigIntegerField(blank=True, null=True),
                ),
                (
                    "assigned_object_type",
                    models.ForeignKey(
                        limit_choices_to=models.Q(
                            models.Q(("app_label", "dcim"), ("model", "device")),
                            models.Q(
                                ("app_label", "dcim"),
                                ("model", "virtualdevicecontext"),
                            ),
                            models.Q(
                                ("app_label", "virtualization"),
                                ("model", "virtualmachine"),
                            ),
                            models.Q(
                                ("app_label", "netbox_nsm"),
                                ("model", "securityzone"),
                            ),
                            _connector="OR",
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "label",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="netbox_nsm.objectlabel",
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
                "verbose_name": "Label Assignment",
                "verbose_name_plural": "Label Assignments",
                "ordering": ("label", "assigned_object_id"),
            },
        ),
        migrations.AddIndex(
            model_name="objectlabelassignment",
            index=models.Index(
                fields=["assigned_object_type", "assigned_object_id"],
                name="netbox_nsm_objlab_assign_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="objectlabelassignment",
            constraint=models.UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "label"),
                name="netbox_nsm_objectlabelassignment_unique",
            ),
        ),
        # ObjectSGTAssignment
        migrations.CreateModel(
            name="ObjectSGTAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
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
                (
                    "assigned_object_id",
                    models.PositiveBigIntegerField(blank=True, null=True),
                ),
                (
                    "assigned_object_type",
                    models.ForeignKey(
                        limit_choices_to=models.Q(
                            models.Q(("app_label", "dcim"), ("model", "device")),
                            models.Q(
                                ("app_label", "dcim"),
                                ("model", "virtualdevicecontext"),
                            ),
                            models.Q(
                                ("app_label", "virtualization"),
                                ("model", "virtualmachine"),
                            ),
                            models.Q(
                                ("app_label", "netbox_nsm"),
                                ("model", "securityzone"),
                            ),
                            _connector="OR",
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "sgt",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="netbox_nsm.objectsgt",
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
                "verbose_name": "SGT Assignment",
                "verbose_name_plural": "SGT Assignments",
                "ordering": ("sgt", "assigned_object_id"),
            },
        ),
        migrations.AddIndex(
            model_name="objectsgtassignment",
            index=models.Index(
                fields=["assigned_object_type", "assigned_object_id"],
                name="netbox_nsm_objsgt_assign_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="objectsgtassignment",
            constraint=models.UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "sgt"),
                name="netbox_nsm_objectsgtassignment_unique",
            ),
        ),
        # ObjectUserAssignment
        migrations.CreateModel(
            name="ObjectUserAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
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
                (
                    "assigned_object_id",
                    models.PositiveBigIntegerField(blank=True, null=True),
                ),
                (
                    "assigned_object_type",
                    models.ForeignKey(
                        limit_choices_to=models.Q(
                            models.Q(("app_label", "dcim"), ("model", "device")),
                            models.Q(
                                ("app_label", "dcim"),
                                ("model", "virtualdevicecontext"),
                            ),
                            models.Q(
                                ("app_label", "virtualization"),
                                ("model", "virtualmachine"),
                            ),
                            models.Q(
                                ("app_label", "netbox_nsm"),
                                ("model", "securityzone"),
                            ),
                            _connector="OR",
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="netbox_nsm.objectuser",
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
                "verbose_name": "User Assignment",
                "verbose_name_plural": "User Assignments",
                "ordering": ("user", "assigned_object_id"),
            },
        ),
        migrations.AddIndex(
            model_name="objectuserassignment",
            index=models.Index(
                fields=["assigned_object_type", "assigned_object_id"],
                name="netbox_nsm_objuser_assign_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="objectuserassignment",
            constraint=models.UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "user"),
                name="netbox_nsm_objectuserassignment_unique",
            ),
        ),
        # ObjectGroupAssignment
        migrations.CreateModel(
            name="ObjectGroupAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
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
                (
                    "assigned_object_id",
                    models.PositiveBigIntegerField(blank=True, null=True),
                ),
                (
                    "assigned_object_type",
                    models.ForeignKey(
                        limit_choices_to=models.Q(
                            models.Q(("app_label", "dcim"), ("model", "device")),
                            models.Q(
                                ("app_label", "dcim"),
                                ("model", "virtualdevicecontext"),
                            ),
                            models.Q(
                                ("app_label", "virtualization"),
                                ("model", "virtualmachine"),
                            ),
                            models.Q(
                                ("app_label", "netbox_nsm"),
                                ("model", "securityzone"),
                            ),
                            _connector="OR",
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="netbox_nsm.objectgroup",
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
                "verbose_name": "Group Assignment",
                "verbose_name_plural": "Group Assignments",
                "ordering": ("group", "assigned_object_id"),
            },
        ),
        migrations.AddIndex(
            model_name="objectgroupassignment",
            index=models.Index(
                fields=["assigned_object_type", "assigned_object_id"],
                name="netbox_nsm_objgrp_assign_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="objectgroupassignment",
            constraint=models.UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "group"),
                name="netbox_nsm_objectgroupassignment_unique",
            ),
        ),
    ]
