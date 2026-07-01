from django.templatetags.static import static
from django.utils.html import format_html

from netbox.plugins import PluginTemplateExtension

from netbox_nsm.version import __version__


class NsmStylesExtension(PluginTemplateExtension):
    """Global NSM styles (rule pills, quicksearch layout fix)."""

    def head(self):
        cache_bust = f"?v={__version__}"
        return format_html(
            '<link rel="stylesheet" href="{}{}" />'
            '<link rel="stylesheet" href="{}{}" />',
            static("netbox_nsm/css/rule-pills.css"),
            cache_bust,
            static("netbox_nsm/css/quicksearch.css"),
            cache_bust,
        )


template_extensions = [NsmStylesExtension]
