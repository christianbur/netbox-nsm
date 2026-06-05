"""Serve plugin static files from the package (no collectstatic / STATIC_ROOT)."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import cache_control

_PKG_ROOT = Path(__file__).resolve().parent.parent
# plugin_assets/ first; static/netbox_nsm/ fallback (rule_form.js, nsm_lazy_picker.css, …).
_PLUGIN_ASSET_ROOTS = (
    _PKG_ROOT / "plugin_assets",
    _PKG_ROOT / "static" / "netbox_nsm",
)

_ALLOWED_PREFIXES = ("css/", "js/", "vendor/")


def _resolve_plugin_asset(rel: str) -> Path | None:
    for root in _PLUGIN_ASSET_ROOTS:
        base = root.resolve()
        full_path = (base / rel).resolve()
        try:
            full_path.relative_to(base)
        except ValueError:
            continue
        if full_path.is_file():
            return full_path
    return None


class PluginAssetView(LoginRequiredMixin, View):
    """
    GET /plugins/netbox-nsm/assets/<path>
    Files under netbox_nsm/plugin_assets/ or netbox_nsm/static/netbox_nsm/.
    """

    @method_decorator(cache_control(public=True, max_age=3600))
    def get(self, request, asset_path: str, *args, **kwargs):
        rel = asset_path.lstrip("/")
        if not rel or ".." in rel.split("/"):
            raise Http404
        if not any(rel.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
            raise Http404
        full_path = _resolve_plugin_asset(rel)
        if full_path is None:
            raise Http404
        content_type, _ = mimetypes.guess_type(full_path.name)
        return FileResponse(
            full_path.open("rb"),
            content_type=content_type or "application/octet-stream",
        )
