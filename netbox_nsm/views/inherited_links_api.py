"""Legacy import path — use ``netbox_nsm.security.views.inherited_links_api`` instead."""

import importlib
_mod = importlib.import_module("netbox_nsm.security.views.inherited_links_api")
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
