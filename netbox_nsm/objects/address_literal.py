"""Legacy import path — use ``addresses.address_literal`` instead."""

import importlib
_mod = importlib.import_module("netbox_nsm.addresses.address_literal")
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
