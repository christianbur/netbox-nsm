"""Bundle discovery: builtin/*.json and PLUGINS_CONFIG['netbox_nsm']['bundle_paths']."""

from __future__ import annotations

from pathlib import Path

__all__ = ("BUILTIN_DIR", "bundle_json_path", "find_bundle_dirs", "find_bundle_paths")

BUILTIN_DIR = Path(__file__).resolve().parent / "builtin"


def _extra_bundle_paths() -> list[Path]:
    from netbox.plugins import get_plugin_config

    raw = get_plugin_config("netbox_nsm", "bundle_paths", [])
    return [Path(p) for p in (raw or [])]


def _builtin_enabled() -> bool:
    from netbox.plugins import get_plugin_config

    val = get_plugin_config("netbox_nsm", "builtin_bundles", True)
    return bool(val) if val is not None else True


def _scan_json_files(search_dir: Path, bundles: dict[str, Path]) -> None:
    """Register ``slug.json`` files in *search_dir* (flat layout)."""
    if not search_dir.is_dir():
        return
    for entry in sorted(search_dir.glob("*.json")):
        if entry.is_file():
            bundles[entry.stem] = entry


def _scan_bundle_subdirs(search_dir: Path, bundles: dict[str, Path]) -> None:
    """Register ``subdir/bundle.json`` (legacy / custom bundle layout)."""
    if not search_dir.is_dir():
        return
    for entry in sorted(search_dir.iterdir()):
        bundle_json = entry / "bundle.json"
        if entry.is_dir() and bundle_json.is_file():
            bundles[entry.name] = bundle_json


def find_bundle_paths() -> dict[str, Path]:
    """Return ``{slug: bundle.json path}`` — custom paths override builtin by slug."""
    bundles: dict[str, Path] = {}

    if _builtin_enabled():
        _scan_json_files(BUILTIN_DIR, bundles)

    for extra_dir in _extra_bundle_paths():
        _scan_json_files(extra_dir, bundles)
        _scan_bundle_subdirs(extra_dir, bundles)

    return bundles


def find_bundle_dirs() -> dict[str, Path]:
    """Backward-compatible alias — values are paths to ``bundle.json`` files."""
    return find_bundle_paths()


def bundle_json_path(slug: str) -> Path:
    """Return the bundle JSON file for *slug* (raises ``FileNotFoundError`` if missing)."""
    paths = find_bundle_paths()
    if slug not in paths:
        raise FileNotFoundError(f"Bundle not found: {slug}")
    path = paths[slug]
    if not path.is_file():
        raise FileNotFoundError(f"Missing bundle JSON for slug: {slug}")
    return path
