#!/usr/bin/env python3
"""Apply netbox-custom-objects PR #602 (config context) on release v0.5.2.

The patch is idempotent: ``--check`` reports whether it is already active;
``--apply`` skips when already patched. After a successful apply, run migrations
and restart NetBox once.

Examples (inside NetBox container or venv):

  /opt/netbox/venv/bin/python /opt/netbox-nsm/patch/apply_pr602.py --check
  /opt/netbox/venv/bin/python /opt/netbox-nsm/patch/apply_pr602.py --apply --migrate

For pip-installed packages under site-packages, run ``--apply`` as root
(``docker compose exec -u root netbox …``). Requires the ``patch`` CLI.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

TARGET_VERSION = "0.5.2"
PATCH_NAME = "netbox-custom-objects-v0.5.2.patch"
MARKER_NAME = ".nsm_patch_pr602_applied"

PATCH_ROOT = Path(__file__).resolve().parent
PATCH_FILE = PATCH_ROOT / "pr_602" / PATCH_NAME


class PatchError(RuntimeError):
    pass


def _read_version_from_init(init_py: Path) -> str | None:
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        init_py.read_text(encoding="utf-8"),
        re.M,
    )
    return match.group(1) if match else None


def read_installed_version(pkg_dir: Path) -> str | None:
    init_py = pkg_dir / "__init__.py"
    if init_py.is_file():
        version = _read_version_from_init(init_py)
        if version:
            return version
    pyproject = pkg_dir.parent / "pyproject.toml"
    if pyproject.is_file():
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(), re.M)
        if match:
            return match.group(1)
    return None


def find_netbox_custom_objects_dir() -> Path:
    env_dir = os.environ.get("NETBOX_CUSTOM_OBJECTS_DIR")
    if env_dir:
        pkg_dir = Path(env_dir).resolve()
        if (pkg_dir / "models.py").is_file():
            return pkg_dir
        raise PatchError(f"NETBOX_CUSTOM_OBJECTS_DIR is not a package: {pkg_dir}")

    venv = Path(os.environ.get("VIRTUAL_ENV", "/opt/netbox/venv"))
    site_pkg = (
        venv
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
        / "netbox_custom_objects"
    )
    for candidate in (
        site_pkg,
        Path("/opt/netbox-custom-objects/netbox_custom_objects"),
    ):
        if (candidate / "models.py").is_file():
            return candidate

    try:
        import netbox_custom_objects
    except ImportError as exc:
        raise PatchError(
            "netbox_custom_objects is not importable. Set NETBOX_CUSTOM_OBJECTS_DIR "
            "or activate the NetBox venv."
        ) from exc
    pkg_dir = Path(netbox_custom_objects.__file__).resolve().parent
    if not (pkg_dir / "models.py").is_file():
        raise PatchError(f"Unexpected package layout: {pkg_dir}")
    return pkg_dir


def patch_file_sha256() -> str:
    digest = hashlib.sha256()
    with PATCH_FILE.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_patched(pkg_dir: Path) -> bool:
    models_py = pkg_dir / "models.py"
    text = models_py.read_text(encoding="utf-8")
    migration = pkg_dir / "migrations" / "0015_customobjecttype_config_context_enabled.py"
    template = pkg_dir / "templates" / "netbox_custom_objects" / "object_configcontext.html"
    return (
        "class CustomObjectConfigContextMixin" in text
        and "config_context_enabled = models.BooleanField" in text
        and "if self.config_context_enabled:" in text
        and migration.is_file()
        and template.is_file()
    )


def write_marker(pkg_dir: Path, version: str | None) -> None:
    marker = pkg_dir.parent / MARKER_NAME
    marker.write_text(
        f"pr=602\nversion={version or 'unknown'}\npatch_sha256={patch_file_sha256()}\n",
        encoding="utf-8",
    )


def run_patch(pkg_dir: Path, *, dry_run: bool) -> None:
    if not PATCH_FILE.is_file():
        raise PatchError(f"Patch file missing: {PATCH_FILE}")

    cmd = ["patch", "-p0", "--directory", str(pkg_dir)]
    if dry_run:
        cmd.insert(1, "--dry-run")
    cmd.extend(["--forward", "--batch", "--input", str(PATCH_FILE)])

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise PatchError(
            "patch failed:\n"
            + (proc.stdout or "")
            + (proc.stderr or "")
        )


def run_migrate() -> None:
    manage_py = os.environ.get("NETBOX_MANAGE_PY", "/opt/netbox/netbox/manage.py")
    if not Path(manage_py).is_file():
        print(
            f"Skip migrate: {manage_py} not found (set NETBOX_MANAGE_PY if needed).",
            file=sys.stderr,
        )
        return
    subprocess.run(
        [sys.executable, manage_py, "migrate", "netbox_custom_objects", "--noinput"],
        check=True,
    )


def cmd_check(pkg_dir: Path, version: str | None) -> int:
    patched = is_patched(pkg_dir)
    print(f"Package:  {pkg_dir}")
    print(f"Version:  {version or '(unknown)'}")
    print(f"Target:   {TARGET_VERSION}")
    print(f"Patched:  {'yes' if patched else 'no'}")
    if version and version != TARGET_VERSION:
        print(
            f"WARNING: patch is built for v{TARGET_VERSION}; installed is v{version}.",
            file=sys.stderr,
        )
    return 0 if patched else 1


def cmd_apply(pkg_dir: Path, version: str | None, *, migrate: bool, force: bool) -> int:
    if version and version != TARGET_VERSION:
        print(
            f"WARNING: patch targets v{TARGET_VERSION}; installed version is v{version}.",
            file=sys.stderr,
        )

    if is_patched(pkg_dir) and not force:
        print("PR #602 patch already active — nothing to do.")
        return 0

    if force and is_patched(pkg_dir):
        marker = pkg_dir.parent / MARKER_NAME
        if marker.is_file():
            marker.unlink()

    print(f"Applying {PATCH_FILE.name} to {pkg_dir} …")
    run_patch(pkg_dir, dry_run=False)
    write_marker(pkg_dir, version)
    print("Patch applied.")

    if migrate:
        print("Running migrate netbox_custom_objects …")
        run_migrate()
        print("Migration finished.")
    else:
        print(
            "Next: python manage.py migrate netbox_custom_objects\n"
            "Then restart NetBox (netbox + workers)."
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 if PR #602 patch is active, 1 otherwise.",
    )
    group.add_argument(
        "--apply",
        action="store_true",
        help="Apply patch once (no-op if already active).",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="With --apply, also run manage.py migrate netbox_custom_objects.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-apply even when code already looks patched (still uses patch(1)).",
    )
    parser.add_argument(
        "--package-dir",
        metavar="PATH",
        help="Override netbox_custom_objects package directory (skip import).",
    )
    args = parser.parse_args(argv)

    try:
        if args.package_dir:
            pkg_dir = Path(args.package_dir).resolve()
            if not (pkg_dir / "models.py").is_file():
                raise PatchError(f"Not a netbox_custom_objects package: {pkg_dir}")
        else:
            pkg_dir = find_netbox_custom_objects_dir()
        version = read_installed_version(pkg_dir)
    except PatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.check:
        return cmd_check(pkg_dir, version)
    return cmd_apply(pkg_dir, version, migrate=args.migrate, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
