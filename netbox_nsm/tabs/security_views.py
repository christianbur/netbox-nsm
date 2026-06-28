"""Legacy import path — use ``netbox_nsm.security.tab.security_views`` instead."""

import importlib
_mod = importlib.import_module("netbox_nsm.security.tab.security_views")
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
