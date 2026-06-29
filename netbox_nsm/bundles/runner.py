"""Generic Python bundle runner — loads and calls a bundle's entrypoint script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

__all__ = ("run_bundle",)


def _load_entry(bundle_dir: Path, bundle: dict):
    """Return the entrypoint callable from the Python bundle's runner script."""
    runner_cfg = bundle.get("runner") or {}
    script_name = runner_cfg.get("script", "run.py")
    entrypoint = runner_cfg.get("entrypoint", "main")

    run_script = bundle_dir / script_name
    if not run_script.is_file():
        raise FileNotFoundError(f"Runner script not found: {run_script}")

    slug = bundle.get("_slug", bundle_dir.name)
    spec = importlib.util.spec_from_file_location(f"_nsm_bundle_{slug}", run_script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return getattr(module, entrypoint)


def run_bundle(slug: str, request: Any = None) -> Any:
    """Run a Python bundle by slug, passing *request* to its entrypoint.

    Returns whatever the entrypoint returns (typically ``None`` or an
    ``HttpResponse``).  Raises ``ValueError`` for unknown or non-Python bundles.
    """
    from netbox_nsm.bundles.dispatch import load_bundle
    from netbox_nsm.bundles.paths import bundle_json_path

    bundle_path = bundle_json_path(slug)
    bundle = load_bundle(bundle_path)
    bundle["_slug"] = slug

    if bundle.get("bundle_kind") != "python":
        raise ValueError(
            f"Bundle {slug!r} is not a Python bundle "
            f"(bundle_kind={bundle.get('bundle_kind')!r})"
        )

    bundle_dir = bundle_path.parent
    entry = _load_entry(bundle_dir, bundle)
    return entry(request)
