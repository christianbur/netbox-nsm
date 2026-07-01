"""Test helpers for object-link scenarios involving custom objects."""

import uuid

from netbox_nsm.security.links.link_propagation import CotObjectLinkPropagationChoices
from netbox_nsm.security.links.object_link_service import create_or_update_links


def create_custom_object_instance(*, name="NSM link test object"):
    """Create a CustomObjectType with a primary text field and one instance."""
    from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

    slug = f"nsm-link-test-{uuid.uuid4().hex[:8]}"
    cot = CustomObjectType.objects.create(
        name=name,
        verbose_name_plural=f"{name}s",
        slug=slug,
    )
    CustomObjectTypeField.objects.create(
        custom_object_type=cot,
        name="name",
        label="Name",
        type="text",
        primary=True,
        required=True,
    )
    model = cot.get_model()
    instance = model.objects.create(name="Linked custom object")
    return instance


def create_object_link_with_custom_object_b(object_a):
    """Create COT link with *object_a* and a custom object as policy side."""
    custom_instance = create_custom_object_instance()
    link, _created = create_or_update_links(
        object_a,
        custom_instance,
        cot_propagation=CotObjectLinkPropagationChoices.DIRECT,
        comment="custom object b link",
    )
    return link, custom_instance
