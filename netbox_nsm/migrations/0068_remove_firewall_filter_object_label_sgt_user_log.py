from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("netbox_nsm", "0067_remove_nat_and_policer")]

    operations = [
        migrations.RemoveField(model_name="objectgroup", name="labels"),
        migrations.RemoveField(model_name="objectgroup", name="sgts"),
        migrations.RemoveField(model_name="objectgroup", name="users"),
        migrations.DeleteModel(name="ObjectLabelAssignment"),
        migrations.DeleteModel(name="ObjectLabel"),
        migrations.DeleteModel(name="ObjectSGTAssignment"),
        migrations.DeleteModel(name="ObjectSGT"),
        migrations.DeleteModel(name="ObjectUserAssignment"),
        migrations.DeleteModel(name="ObjectUser"),
        migrations.DeleteModel(name="ObjectLog"),
        migrations.DeleteModel(name="FirewallRuleFromSetting"),
        migrations.DeleteModel(name="FirewallRuleThenSetting"),
        migrations.DeleteModel(name="FirewallFilterRule"),
        migrations.DeleteModel(name="FirewallFilterAssignment"),
        migrations.DeleteModel(name="FirewallFilter"),
    ]
