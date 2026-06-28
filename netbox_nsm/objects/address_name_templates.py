"""Legacy import path — use ``addresses.address_name_templates`` instead."""

import importlib
_mod = importlib.import_module("netbox_nsm.addresses.address_name_templates")
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
