from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_nsm", "0065_objectcustomobjectassignment_comment"),
    ]

    operations = [
        # Delete SecurityZonePolicy (M2M with zones, addresses, applications)
        migrations.DeleteModel(name="SecurityZonePolicy"),
        # Delete Matrix (MatrixCell references Matrix + MatrixPolicy → delete cells first)
        migrations.DeleteModel(name="SecurityZoneMatrixCell"),
        migrations.DeleteModel(name="SecurityZoneMatrix"),
        migrations.DeleteModel(name="SecurityZoneMatrixPolicy"),
    ]
