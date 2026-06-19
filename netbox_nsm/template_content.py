from django.templatetags.static import static
from django.utils.html import format_html

from netbox.plugins import PluginTemplateExtension


class NsmStylesExtension(PluginTemplateExtension):
    """Pill styles for rulebook/rule tables (also after HTMX table refresh)."""

    def head(self):
        return format_html(
            '<link rel="stylesheet" href="{}" />',
            static("netbox_nsm/css/rule-pills.css"),
        )


class NsmSecurityLinksExtension(PluginTemplateExtension):
    """
    Legacy Security panel hook — disabled; content moved to the Security tab.

    Registered so existing plugin template extension lists stay stable; the right
    panel is intentionally empty.
    """

    models = None

    def right_page(self):
        return ""


template_extensions = [NsmStylesExtension, NsmSecurityLinksExtension]
