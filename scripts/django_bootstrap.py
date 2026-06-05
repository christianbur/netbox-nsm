"""Bootstrap Django for standalone netbox-nsm scripts.

Usage at the top of any script in this directory::

    import django_bootstrap
    django_bootstrap.setup()

Or from the host/container::

    NETBOX_ROOT=/opt/netbox python3 /opt/netbox-nsm/scripts/show_diff.py

Matches netbox-custom-objects portable-schema docs: set ``DJANGO_SETTINGS_MODULE``,
add ``$NETBOX_ROOT/netbox`` to ``PYTHONPATH``, then ``django.setup()`` before
any NetBox/plugin imports.
"""

from __future__ import annotations

import os
import sys

_NETBOX_ROOT_CANDIDATES = (
    os.environ.get("NETBOX_ROOT", "").strip(),
    "/opt/netbox",
    "/app/netbox",
)


def _netbox_pythonpath() -> str | None:
    for root in _NETBOX_ROOT_CANDIDATES:
        if not root:
            continue
        pkg = os.path.join(root, "netbox")
        if os.path.isdir(os.path.join(pkg, "netbox")):
            return pkg
    return None


def setup() -> None:
    """Configure Django once; safe to call multiple times."""
    if os.environ.get("_NETBOX_NSM_DJANGO_READY"):
        return

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netbox.settings")

    pkg = _netbox_pythonpath()
    if pkg is None:
        raise RuntimeError(
            "NetBox package not found. Set NETBOX_ROOT (e.g. NETBOX_ROOT=/opt/netbox) "
            "or run via: python3 /opt/netbox/netbox/manage.py nbshell"
        )
    if pkg not in sys.path:
        sys.path.insert(0, pkg)

    import django

    django.setup()
    os.environ["_NETBOX_NSM_DJANGO_READY"] = "1"


__all__ = ("setup",)
