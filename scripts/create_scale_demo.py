#!/usr/bin/env python3
"""Create the 100×100 / 10 000-rule scale demo (netbox-dev CLI).

Example::

    docker exec netbox-dev python3 /opt/netbox-nsm/scripts/create_scale_demo.py
"""
import django_bootstrap

django_bootstrap.setup()

from netbox_nsm.demos.scale_test import create_scale_test_demo

if __name__ == "__main__":
    summary = create_scale_test_demo(recreate=True)
    print(
        f"{summary['rulebook']} (pk={summary['rulebook_id']}): "
        f"{summary['zones']} zones, {summary['rules']} rules, "
        f"{summary['object_items']} items, {summary['elapsed_s']}s"
    )
