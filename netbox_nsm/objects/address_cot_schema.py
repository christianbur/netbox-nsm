"""Legacy import path — use ``addresses.address_cot_schema`` instead."""

import importlib

_mod = importlib.import_module("netbox_nsm.addresses.address_cot_schema")
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
