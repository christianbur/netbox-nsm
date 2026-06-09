#!/usr/bin/env python3
"""Create the 100×100 / 10 000-rule COT scale demo (netbox-dev CLI).

Ausführung::

    docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_scale_demo.py

Erstellt ``nsm_rb_scale_test`` mit Zonen ``demo-0001`` … ``demo-0100`` und
10 000 Matrix-Regeln (COT Custom Objects, nicht native Rulebook-ORM).
"""
import django_bootstrap

django_bootstrap.setup()

from netbox_nsm.demos.scale_test import create_scale_test_demo

if __name__ == "__main__":
    summary = create_scale_test_demo(recreate=True)
    print(
        f"{summary['rulebook']} ({summary['rulebook_slug']}, pk={summary['rulebook_id']}): "
        f"{summary['zones']} zones, {summary['rules']} rules, "
        f"{summary['object_items']} multiobject assignments, {summary['elapsed_s']}s"
    )
