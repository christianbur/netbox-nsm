"""Test helpers for ObjectLink scenarios involving custom objects."""

import uuid

from django.contrib.contenttypes.models import ContentType

from netbox_nsm.models import ObjectLink


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
    """Create ObjectLink with object_a (Prefix, IPAddress, etc.) and a custom object as object_b."""
    custom_instance = create_custom_object_instance()
    object_a_ct = ContentType.objects.get_for_model(object_a)
    custom_ct = ContentType.objects.get_for_model(custom_instance)
    link = ObjectLink.objects.create(
        object_a_type=object_a_ct,
        object_a_id=object_a.pk,
        object_b_type=custom_ct,
        object_b_id=custom_instance.pk,
        comment="custom object b link",
    )
    return link, custom_instance
