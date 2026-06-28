"""Validate ``nsm_address`` rows on save."""

from __future__ import annotations

from django.db.models.signals import pre_save
from django.dispatch import receiver

from netbox_nsm.addresses.address_ipam_fk import is_nsm_address_object
from netbox_nsm.addresses.address_literal import validate_address_fields


@receiver(pre_save)
def validate_nsm_address_on_save(sender, instance, **kwargs):
    if not is_nsm_address_object(instance):
        return
    validate_address_fields(instance)
