"""Bundle discovery: builtin/ and PLUGINS_CONFIG['netbox_nsm']['bundle_paths']."""

from __future__ import annotations

from pathlib import Path

__all__ = ("BUILTIN_DIR", "bundle_json_path", "find_bundle_dirs")

BUILTIN_DIR = Path(__file__).resolve().parent / "builtin"


def _extra_bundle_paths() -> list[Path]:
    from netbox.plugins import get_plugin_config

    raw = get_plugin_config("netbox_nsm", "bundle_paths", [])
    return [Path(p) for p in (raw or [])]


def _builtin_enabled() -> bool:
    from netbox.plugins import get_plugin_config

    val = get_plugin_config("netbox_nsm", "builtin_bundles", True)
    return bool(val) if val is not None else True


def _scan_dir(search_dir: Path, bundles: dict[str, Path]) -> None:
    """Add bundle subdirectories with bundle.json from *search_dir* to *bundles*."""
    if not search_dir.is_dir():
        return
    for entry in sorted(search_dir.iterdir()):
        if entry.is_dir() and (entry / "bundle.json").is_file():
            bundles[entry.name] = entry


def find_bundle_dirs() -> dict[str, Path]:
    """Return ``{slug: bundle_dir}`` — custom paths override builtin by slug.

    Priority (low → high):
    1. ``bundles/builtin/`` — shipped with the plugin (default: enabled)
    2. Each path in ``PLUGINS_CONFIG['netbox_nsm']['bundle_paths']`` — user paths

    Same slug in multiple directories: last one (highest priority) wins.
    """
    bundles: dict[str, Path] = {}

    if _builtin_enabled():
        _scan_dir(BUILTIN_DIR, bundles)

    for extra_dir in _extra_bundle_paths():
        _scan_dir(extra_dir, bundles)

    return bundles


def bundle_json_path(slug: str) -> Path:
    """Return ``bundle.json`` for *slug* (raises ``FileNotFoundError`` if missing)."""
    bundle_dirs = find_bundle_dirs()
    if slug not in bundle_dirs:
        raise FileNotFoundError(f"Bundle not found: {slug}")
    path = bundle_dirs[slug] / "bundle.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing bundle.json for slug: {slug}")
    return path
