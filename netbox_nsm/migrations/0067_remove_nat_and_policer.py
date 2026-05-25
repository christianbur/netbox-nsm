from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("netbox_nsm", "0066_remove_securityzone_policy_and_matrix")]

    operations = [
        migrations.DeleteModel(name="NatRuleAssignment"),
        migrations.DeleteModel(name="NatRuleSetAssignment"),
        migrations.DeleteModel(name="NatRule"),
        migrations.DeleteModel(name="NatRuleSet"),
        migrations.DeleteModel(name="NatPoolMember"),
        migrations.DeleteModel(name="NatPoolAssignment"),
        migrations.DeleteModel(name="NatPool"),
        migrations.DeleteModel(name="PolicerAssignment"),
        migrations.DeleteModel(name="Policer"),
    ]
