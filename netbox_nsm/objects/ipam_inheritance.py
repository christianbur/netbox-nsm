"""Legacy import path — use ``addresses.ipam_inheritance`` instead."""

import importlib
_mod = importlib.import_module("netbox_nsm.addresses.ipam_inheritance")
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
