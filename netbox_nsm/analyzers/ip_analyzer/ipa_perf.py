"""IP Analyzer performance helpers: lazy-load context, cache keys, plugin settings."""

from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from typing import Any, Callable

from django.core.cache import cache
from netbox.plugins import get_plugin_config

__all__ = (
    "build_ipa_cache_key",
    "cached_ipa_payload",
    "get_ipa_analyzer_cache_timeout",
    "get_ipa_analyzer_timeout_ms",
    "ipa_lazy_context",
    "ipa_lazy_load_enabled",
    "parse_lazy_flag",
    "parse_refresh_flag",
    "should_bypass_ipa_cache",
)

_ipa_lazy_load: ContextVar[bool] = ContextVar("ipa_lazy_load", default=False)


def ipa_lazy_load_enabled() -> bool:
    return _ipa_lazy_load.get()


class ipa_lazy_context:
    """Enable or disable IPA lazy-first analysis for the current call stack."""

    def __init__(self, enabled: bool):
        self.enabled = bool(enabled)
        self._token = None

    def __enter__(self):
        self._token = _ipa_lazy_load.set(self.enabled)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._token is not None:
            _ipa_lazy_load.reset(self._token)
        return False


def get_ipa_analyzer_timeout_ms() -> int:
    try:
        return int(get_plugin_config("netbox_nsm", "ipa_analyzer_timeout_ms", 120000))
    except (TypeError, ValueError):
        return 120000


def get_ipa_analyzer_cache_timeout() -> int:
    try:
        return int(get_plugin_config("netbox_nsm", "ipa_analyzer_cache_timeout", 300))
    except (TypeError, ValueError):
        return 300


def parse_lazy_flag(request) -> bool:
    value = (request.GET.get("lazy") or "").strip().lower()
    return value in {"1", "true", "yes"}


def parse_refresh_flag(request) -> bool:
    value = (request.GET.get("refresh") or "").strip().lower()
    return value in {"1", "true", "yes"}


def should_bypass_ipa_cache(*, lazy: bool, refresh: bool, cache_timeout: int) -> bool:
    if refresh or not lazy:
        return True
    return cache_timeout <= 0


def _sorted_object_refs(selections) -> list[str]:
    refs = []
    for sel in selections or []:
        ct = sel.get("ct")
        pk = sel.get("pk")
        if ct is None or pk is None:
            continue
        refs.append(f"{ct}:{pk}")
    return sorted(refs)


def build_ipa_cache_key(
    *,
    user_id: int | None,
    mode: str,
    lazy: bool,
    selections=None,
    sides=None,
) -> str:
    payload: dict[str, Any] = {
        "mode": mode,
        "lazy": bool(lazy),
        "uid": user_id,
    }
    if mode == "diff":
        side_data = []
        for side in sides or []:
            side_data.append(
                {
                    "label": side.get("label") or "",
                    "refs": _sorted_object_refs(side.get("selections")),
                }
            )
        payload["sides"] = side_data
    else:
        payload["refs"] = _sorted_object_refs(selections)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"nsm:ipa:v2:{digest}"


def cached_ipa_payload(
    cache_key: str,
    cache_timeout: int,
    builder: Callable[[], dict],
) -> tuple[dict, bool]:
    """Return ``(payload, from_cache)``."""
    if cache_timeout <= 0:
        return builder(), False
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, True
    payload = builder()
    cache.set(cache_key, payload, cache_timeout)
    return payload, False
