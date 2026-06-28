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


template_extensions = [NsmStylesExtension]
