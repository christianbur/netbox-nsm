# Squashed initial migration for fresh empty-DB installs (no native Rulebook schema).
# Regenerate via docker/netbox_dev/scripts/generate_nsm_0001.sh when models change.

import django.core.validators
import django.db.models.deletion
import django.db.models.functions.text
import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('extras', '0138_customfieldchoiceset_choice_colors'),
        ('netbox_custom_objects', '0014_fix_mixed_case_field_names'),
        ('users', '0016_default_ordering_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='NsmUiSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('menu_label', models.CharField(default='Security', max_length=100)),
                ('panel_label', models.CharField(default='Security', max_length=100)),
                ('setup_menu_dismissed', models.BooleanField(default=False)),
                ('setup_menu_config_enabled', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'NSM UI settings',
                'verbose_name_plural': 'NSM UI settings',
            },
        ),
        migrations.CreateModel(
            name='ObjectGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('description', models.CharField(blank=True, max_length=200)),
                ('comments', models.TextField(blank=True)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('field_slugs', models.JSONField(blank=True, default=list)),
                ('color', models.CharField(blank=True, default='', max_length=7)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='users.owner')),
                ('sub_groups', models.ManyToManyField(blank=True, related_name='parent_groups', to='netbox_nsm.objectgroup')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Security Object Group',
                'verbose_name_plural': 'Security Object Groups',
                'ordering': ('name',),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='PropertyType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('description', models.CharField(blank=True, max_length=200)),
                ('comments', models.TextField(blank=True)),
                ('name', models.CharField(max_length=100, unique=True, validators=[django.core.validators.RegexValidator(message='Only lowercase alphanumeric characters and underscores are allowed. Names may not start or end with an underscore, and double underscores are not permitted.', regex='^[a-z0-9]+(_[a-z0-9]+)*$')])),
                ('verbose_name', models.CharField(blank=True, max_length=100)),
                ('verbose_name_plural', models.CharField(blank=True, max_length=100)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('group_name', models.CharField(blank=True, db_index=True, max_length=100)),
                ('schema_document', models.JSONField(blank=True, null=True)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='users.owner')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Security Property Type',
                'verbose_name_plural': 'Security Property Types',
                'ordering': ('name',),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='PropertyField',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('description', models.CharField(blank=True, max_length=200)),
                ('comments', models.TextField(blank=True)),
                ('name', models.CharField(max_length=50, validators=[django.core.validators.RegexValidator(message='Only lowercase alphanumeric characters and underscores are allowed. Names may not start or end with an underscore, and double underscores are not permitted.', regex='^[a-z0-9]+(_[a-z0-9]+)*$')])),
                ('label', models.CharField(blank=True, max_length=50)),
                ('type', models.CharField(default='text', max_length=50)),
                ('group_name', models.CharField(blank=True, max_length=50)),
                ('required', models.BooleanField(default=False)),
                ('unique', models.BooleanField(default=False)),
                ('default', models.JSONField(blank=True, null=True)),
                ('weight', models.PositiveSmallIntegerField(default=100)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='users.owner')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('security_property_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fields', to='netbox_nsm.propertytype')),
            ],
            options={
                'verbose_name': 'Security Property Field',
                'verbose_name_plural': 'Security Property Fields',
                'ordering': ('group_name', 'weight', 'name'),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Property',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('description', models.CharField(blank=True, max_length=200)),
                ('comments', models.TextField(blank=True)),
                ('name', models.CharField(max_length=150)),
                ('object_data', models.JSONField(blank=True, default=dict)),
                ('source_model', models.CharField(blank=True, max_length=64)),
                ('source_pk', models.PositiveBigIntegerField(blank=True, null=True)),
                ('color', models.CharField(blank=True, default='', max_length=7)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='users.owner')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('security_property_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='security_propertys', to='netbox_nsm.propertytype')),
            ],
            options={
                'verbose_name': 'Security Property',
                'verbose_name_plural': 'Security Properties',
                'ordering': ('security_property_type', 'name'),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('description', models.CharField(blank=True, max_length=200)),
                ('comments', models.TextField(blank=True)),
                ('slug', models.SlugField(unique=True)),
                ('name', models.CharField(max_length=100)),
                ('sort_order', models.PositiveIntegerField(default=100)),
                ('custom_object_types', models.ManyToManyField(blank=True, related_name='nsm_sections', to='netbox_custom_objects.customobjecttype')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='users.owner')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'NSM Section',
                'verbose_name_plural': 'NSM Sections',
                'ordering': ('sort_order', 'slug'),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='TypeConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('name', models.CharField(max_length=100)),
                ('matching_class', models.CharField(blank=True, default='', max_length=20)),
                ('display_template', models.CharField(blank=True, default='{name}', max_length=255)),
                ('panel_slugs', models.JSONField(blank=True, default=list)),
                ('order_id', models.PositiveIntegerField(default=100)),
                ('allow_virtual_groups', models.BooleanField(default=False)),
                ('inherit_links', models.BooleanField(default=False)),
                ('inherit_stop_on_own', models.BooleanField(default=False)),
                ('panel_linkable_types', models.JSONField(blank=True, default=list)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nsm_matching_configs', to='contenttypes.contenttype')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Type Config',
                'verbose_name_plural': 'Type Configs',
                'ordering': ('order_id', 'content_type__app_label', 'content_type__model', 'matching_class'),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='CotRulebookAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('assigned_object_id', models.PositiveBigIntegerField()),
                ('cot_slug', models.SlugField(max_length=100)),
                ('description', models.CharField(blank=True, max_length=200)),
                ('assigned_object_type', models.ForeignKey(limit_choices_to=models.Q(models.Q(models.Q(('app_label', 'dcim'), ('model', 'device')), models.Q(('app_label', 'dcim'), ('model', 'virtualdevicecontext')), models.Q(('app_label', 'virtualization'), ('model', 'virtualmachine')), _connector='OR')), on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Rulebook Assignment',
                'verbose_name_plural': 'Rulebook Assignments',
                'ordering': ('cot_slug', 'assigned_object_id'),
                'permissions': [('view_rulebook', 'Can view rulebooks'), ('view_rulebookassignment', 'Can view rulebook assignments'), ('add_rulebookassignment', 'Can add rulebook assignments'), ('change_rulebookassignment', 'Can change rulebook assignments'), ('delete_rulebookassignment', 'Can delete rulebook assignments')],
                'indexes': [models.Index(fields=['assigned_object_type', 'assigned_object_id'], name='netbox_nsm__assigne_3a5a00_idx')],
                'constraints': [models.UniqueConstraint(fields=('assigned_object_type', 'assigned_object_id', 'cot_slug'), name='netbox_nsm_cotrulebookassignment_unique_cot_assignment')],
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='ObjectGroupMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('object_id', models.PositiveBigIntegerField()),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='member_items', to='netbox_nsm.objectgroup')),
            ],
            options={
                'verbose_name': 'Security Object Group Member',
                'verbose_name_plural': 'Security Object Group Members',
                'ordering': ('group__name',),
                'indexes': [models.Index(fields=['content_type', 'object_id'], name='netbox_nsm__content_976b8a_idx')],
                'unique_together': {('group', 'content_type', 'object_id')},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='ObjectLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('object_a_id', models.PositiveBigIntegerField()),
                ('object_b_id', models.PositiveBigIntegerField()),
                ('propagation', models.CharField(default='direct', max_length=20)),
                ('propagate_stop_on_own', models.BooleanField(default=False)),
                ('comment', models.TextField(blank=True, default='')),
                ('object_a_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='contenttypes.contenttype')),
                ('object_b_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='contenttypes.contenttype')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'NSM Object Link',
                'verbose_name_plural': 'NSM Object Links',
                'indexes': [models.Index(fields=['object_a_type', 'object_a_id'], name='netbox_nsm__object__66c665_idx'), models.Index(fields=['object_b_type', 'object_b_id'], name='netbox_nsm__object__4a8592_idx'), models.Index(fields=['propagation'], name='netbox_nsm__propaga_b861c2_idx')],
                'unique_together': {('object_a_type', 'object_a_id', 'object_b_type', 'object_b_id')},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.AddConstraint(
            model_name='propertytype',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('name'), name='netbox_nsm_propertytype_name_ci_unique'),
        ),
        migrations.AddConstraint(
            model_name='propertyfield',
            constraint=models.UniqueConstraint(fields=('security_property_type', 'name'), name='netbox_nsm_propertyfield_unique_name'),
        ),
        migrations.AddConstraint(
            model_name='property',
            constraint=models.UniqueConstraint(fields=('security_property_type', 'name'), name='netbox_nsm_property_unique_type_name'),
        ),
        migrations.AddConstraint(
            model_name='property',
            constraint=models.UniqueConstraint(fields=('security_property_type', 'source_model', 'source_pk'), name='netbox_nsm_property_unique_type_source'),
        ),
        migrations.AlterUniqueTogether(
            name='typeconfig',
            unique_together={('content_type', 'matching_class')},
        ),
    ]
