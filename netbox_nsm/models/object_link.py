from django.utils.translation import gettext_lazy as _

__all__ = (
    "LinkPropagationChoices",
)


class LinkPropagationChoices:
    """Propagation modes for NSM object links (COT ``nsm_object_link.propagation``)."""

    DIRECT = "direct"
    INHERIT_IPAM = "inherit_ipam"
    INHERIT_GROUP = "inherit_group"

    choices = (
        (DIRECT, _("Direct (bidirectional, visible on both sides)")),
        (
            INHERIT_IPAM,
            _("Inherit to IPAM children (prefixes, addresses, ranges)"),
        ),
        (INHERIT_GROUP, _("Inherit to group members")),
    )

    @classmethod
    def get_display(cls, value: str) -> str:
        return dict(cls.choices).get(value, value)
