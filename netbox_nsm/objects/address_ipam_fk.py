"""Legacy import path — use ``addresses.address_ipam_fk`` instead."""

import importlib
_mod = importlib.import_module("netbox_nsm.addresses.address_ipam_fk")
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
