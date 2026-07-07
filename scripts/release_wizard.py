#!/usr/bin/env python3
"""Interactive release wizard for Python projects.

Guides through version bump, CHANGELOG update, git commit, tag, and push.
Project-specific paths and behaviour are driven by an optional
``release-wizard.toml`` in the project root (or ``--config``).

When not running as the configured git user, push uses ``sudo -u <git_user>`` so
SSH keys match (same pattern as ``tools/github-push.sh``).

Without a config file, defaults apply: ``pyproject.toml`` version, ``CHANGELOG.md``,
and the git ``origin`` remote URL.

If ``CHANGELOG.md`` starts with ``## [X.Y.Z] - unreleased``, that section is imported
automatically (preserving formatting); a new unreleased section is prepended on release.

Examples::

    python3 scripts/release_wizard.py
    python3 scripts/release_wizard.py --version 0.2.2 --yes --commit --tag
    python3 scripts/release_wizard.py --dry-run --version 0.2.2
    python3 scripts/release_wizard.py --root /path/to/other-repo
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEFAULT_CHANGELOG_SECTIONS = ("Added", "Changed", "Fixed", "Removed", "Notes")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
SCRIPT_DIR = Path(__file__).resolve().parent


@dataclass
class VersionSource:
    file: Path
    label: str
    read_pattern: re.Pattern[str]
    write_pattern: re.Pattern[str]
    write_replacement: str

    def read(self) -> str:
        text = self.file.read_text(encoding="utf-8")
        match = self.read_pattern.search(text)
        if not match:
            raise RuntimeError(f"Could not parse version from {self.file}")
        return match.group(1)

    def write(self, version: str) -> str:
        replacement = self.write_replacement.format(version=version)
        text = self.file.read_text(encoding="utf-8")
        updated, count = self.write_pattern.subn(replacement, text, count=1)
        if count != 1:
            raise RuntimeError(f"Could not update version in {self.file}")
        return updated


@dataclass
class WatchGroup:
    name: str
    files: list[Path]
    reminder: str = ""


@dataclass
class ParsedChangelogSection:
    version: str
    date_label: str
    sections: dict[str, list[str]]
    header_start: int
    header_end: int

    @property
    def is_unreleased(self) -> bool:
        return self.date_label.lower() == "unreleased"

    @property
    def entry_count(self) -> int:
        return sum(len(items) for items in self.sections.values())


@dataclass
class ReleaseConfig:
    root: Path
    project_name: str
    git_user: str
    repo_url: str
    dev_branch: str
    release_branch: str
    auto_promote_to_main: bool
    changelog_path: Path
    changelog_sections: tuple[str, ...]
    changelog_import_unreleased: bool
    version_sources: list[VersionSource]
    commit_files: list[str]
    watch_groups: list[WatchGroup]
    netbox_plugin_path: Path | None
    netbox_plugin_init_file: Path | None
    manual_push_hint: str
    pypi_note: str
    config_path: Path | None = None

    @property
    def has_watch_groups(self) -> bool:
        return bool(self.watch_groups)


def _compile_pattern(pattern: str, flags: list[str] | str | None = None) -> re.Pattern[str]:
    flag_value = 0
    if flags:
        names = [flags] if isinstance(flags, str) else flags
        for name in names:
            flag_value |= getattr(re, name.upper(), 0)
    return re.compile(pattern, flag_value)


def _detect_git_root(start: Path) -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def _detect_repo_url(root: Path) -> str:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return ""
    url = result.stdout.strip()
    if url.startswith("git@"):
        host, path = url.split(":", 1)
        host = host.removeprefix("git@")
        path = path.removesuffix(".git")
        return f"https://{host}/{path}"
    return url.removesuffix(".git")


def _default_git_user() -> str:
    return os.environ.get("USER", os.environ.get("LOGNAME", "christian"))


def _default_config(root: Path) -> ReleaseConfig:
    pyproject = root / "pyproject.toml"
    return ReleaseConfig(
        root=root,
        project_name=root.name,
        git_user=_default_git_user(),
        repo_url=_detect_repo_url(root),
        dev_branch="dev",
        release_branch="main",
        auto_promote_to_main=False,
        changelog_path=root / "CHANGELOG.md",
        changelog_sections=DEFAULT_CHANGELOG_SECTIONS,
        changelog_import_unreleased=True,
        version_sources=[
            VersionSource(
                file=pyproject,
                label="pyproject.toml",
                read_pattern=re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE),
                write_pattern=re.compile(r'^version\s*=\s*"[^"]+"', re.MULTILINE),
                write_replacement='version = "{version}"',
            ),
        ],
        commit_files=["pyproject.toml", "CHANGELOG.md"],
        watch_groups=[],
        netbox_plugin_path=None,
        netbox_plugin_init_file=None,
        manual_push_hint="",
        pypi_note="",
    )


def _version_source_from_toml(root: Path, entry: dict) -> VersionSource:
    rel = entry["file"]
    return VersionSource(
        file=root / rel,
        label=entry.get("label", rel),
        read_pattern=_compile_pattern(entry["read"], entry.get("flags")),
        write_pattern=_compile_pattern(entry["write"], entry.get("flags")),
        write_replacement=entry["replace"],
    )


def _load_config(root: Path, config_path: Path | None) -> ReleaseConfig:
    path = config_path or (root / "release-wizard.toml")
    if not path.is_file():
        return _default_config(root)

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    defaults = _default_config(root)

    project = data.get("project", {})
    repo = data.get("repo", {})
    changelog = data.get("changelog", {})
    commit = data.get("commit", {})
    reminders = data.get("reminders", {})

    version_sources: list[VersionSource] = []
    for entry in data.get("version", []):
        version_sources.append(_version_source_from_toml(root, entry))

    netbox_plugin = data.get("netbox_plugin")
    netbox_plugin_path = None
    netbox_plugin_init_file = None
    if netbox_plugin:
        netbox_plugin_path = root / netbox_plugin["file"]
        if netbox_plugin.get("init_file"):
            netbox_plugin_init_file = root / netbox_plugin["init_file"]

    watch_groups: list[WatchGroup] = []
    for group in data.get("watch", []):
        watch_groups.append(
            WatchGroup(
                name=group.get("name", "Watch files"),
                files=[root / rel for rel in group.get("files", [])],
                reminder=group.get("reminder", ""),
            )
        )

    changelog_sections = tuple(changelog.get("sections", defaults.changelog_sections))
    commit_files = commit.get("files")
    if commit_files is None:
        commit_files = list({src.file.relative_to(root).as_posix() for src in version_sources})
        if netbox_plugin_path:
            commit_files.append(netbox_plugin_path.relative_to(root).as_posix())
        if netbox_plugin_init_file:
            commit_files.append(netbox_plugin_init_file.relative_to(root).as_posix())
        commit_files.append(changelog.get("file", "CHANGELOG.md"))
        commit_files = sorted(set(commit_files))

    return ReleaseConfig(
        root=root,
        project_name=project.get("name", defaults.project_name),
        git_user=project.get("git_user", defaults.git_user),
        repo_url=repo.get("url") or defaults.repo_url,
        dev_branch=repo.get("dev_branch", defaults.dev_branch),
        release_branch=repo.get("release_branch", defaults.release_branch),
        auto_promote_to_main=repo.get("auto_promote_to_main", defaults.auto_promote_to_main),
        changelog_path=root / changelog.get("file", "CHANGELOG.md"),
        changelog_sections=changelog_sections,
        changelog_import_unreleased=changelog.get("import_unreleased", True),
        version_sources=version_sources or defaults.version_sources,
        commit_files=commit_files,
        watch_groups=watch_groups,
        netbox_plugin_path=netbox_plugin_path,
        netbox_plugin_init_file=netbox_plugin_init_file,
        manual_push_hint=reminders.get("manual_push_hint", ""),
        pypi_note=reminders.get("pypi_note", ""),
        config_path=path,
    )


def _print_header(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        answer = input(f"{prompt}{suffix}: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please enter y/yes or n/no.")


def _ask_text(prompt: str, default: str | None = None) -> str:
    if default:
        value = input(f"{prompt} [{default}]: ").strip()
        return value or default
    return input(f"{prompt}: ").strip()


class ReleaseWizard:
    def __init__(self, config: ReleaseConfig) -> None:
        self.config = config
        self._use_changelog_import = False

    def _parse_changelog_top_section(self, text: str) -> ParsedChangelogSection | None:
        match = re.search(r"^## \[([^\]]+)\] - (.+)$", text, re.MULTILINE)
        if not match:
            return None

        version = match.group(1).strip()
        date_label = match.group(2).strip()
        body_start = match.end()
        next_section = text.find("\n## [", body_start)
        body = text[body_start:next_section if next_section != -1 else len(text)]

        sections: dict[str, list[str]] = {name: [] for name in self.config.changelog_sections}
        current: str | None = None
        current_bullet: list[str] = []

        def flush_bullet() -> None:
            nonlocal current_bullet
            if current and current_bullet:
                sections[current].append(" ".join(part.strip() for part in current_bullet).strip())
            current_bullet = []

        for line in body.splitlines():
            header = re.match(r"^### (.+)$", line.strip())
            if header:
                flush_bullet()
                name = header.group(1).strip()
                current = name if name in sections else None
                continue
            bullet = re.match(r"^- (.+)$", line.strip())
            if bullet:
                flush_bullet()
                if current:
                    current_bullet = [bullet.group(1)]
                continue
            if current and line.startswith(("  ", "\t")) and current_bullet:
                current_bullet.append(line.strip())
                continue
            if not line.strip():
                flush_bullet()

        flush_bullet()
        return ParsedChangelogSection(
            version=version,
            date_label=date_label,
            sections=sections,
            header_start=match.start(),
            header_end=match.end(),
        )

    def _read_changelog_import(self) -> ParsedChangelogSection | None:
        path = self.config.changelog_path
        if not path.is_file():
            return None
        parsed = self._parse_changelog_top_section(path.read_text(encoding="utf-8"))
        if parsed is None or not parsed.is_unreleased:
            return None
        if parsed.entry_count == 0:
            return None
        return parsed

    def _print_changelog_import_preview(self, parsed: ParsedChangelogSection) -> None:
        print(f"Found in {self.config.changelog_path.name}: [{parsed.version}] - {parsed.date_label}")
        for name in self.config.changelog_sections:
            bullets = parsed.sections.get(name, [])
            if not bullets:
                continue
            print(f"  ### {name} ({len(bullets)} entries)")
            for bullet in bullets[:3]:
                preview = bullet if len(bullet) <= 90 else f"{bullet[:87]}..."
                print(f"    - {preview}")
            if len(bullets) > 3:
                print(f"    - ... {len(bullets) - 3} more")

    def _collect_changelog_sections(
        self,
        interactive: bool,
        *,
        allow_import: bool,
    ) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {name: [] for name in self.config.changelog_sections}
        self._use_changelog_import = False

        if allow_import and self.config.changelog_import_unreleased:
            parsed = self._read_changelog_import()
            if parsed:
                if interactive:
                    print()
                    self._print_changelog_import_preview(parsed)
                    if _ask_yes_no("Use these entries from CHANGELOG.md?", default=True):
                        self._use_changelog_import = True
                        return parsed.sections
                else:
                    self._use_changelog_import = True
                    return parsed.sections

        if not interactive:
            return sections

        print()
        print("Changelog entries per category (Keep a Changelog).")
        print("Skip empty categories.")
        for name in self.config.changelog_sections:
            if _ask_yes_no(f'Add entries for "{name}"?', default=False):
                sections[name] = self._read_multiline_bullets(name)
        return sections

    def _running_as_git_user(self) -> bool:
        return os.environ.get("USER", os.environ.get("LOGNAME", "")) == self.config.git_user

    def _git_command(self, *args: str, remote: bool = False) -> list[str]:
        cmd = ["git", *args]
        if remote and not self._running_as_git_user() and os.geteuid() == 0:
            return ["sudo", "-u", self.config.git_user, "--", *cmd]
        return cmd

    def _run_git(self, *args: str, check: bool = False, remote: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self._git_command(*args, remote=remote),
            cwd=self.config.root,
            text=True,
            capture_output=True,
            check=check,
        )

    def _git_output(self, *args: str) -> str:
        result = self._run_git(*args)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(stderr or f"git {' '.join(args)} failed")
        return result.stdout.strip()

    def _read_plugin_releases(self) -> list[str]:
        path = self.config.netbox_plugin_path
        if path is None:
            return []
        text = path.read_text(encoding="utf-8")
        return re.findall(r"^\s*-\s*release:\s*(\S+)", text, re.MULTILINE)

    def _collect_versions(self) -> dict[str, str]:
        versions: dict[str, str] = {}
        for source in self.config.version_sources:
            versions[source.label] = source.read()
        if self.config.netbox_plugin_path:
            releases = self._read_plugin_releases()
            label = f"{self.config.netbox_plugin_path.relative_to(self.config.root)} (latest release)"
            versions[label] = releases[0] if releases else "(none)"
        return versions

    def _versions_in_sync(self) -> bool:
        values = [v for v in self._collect_versions().values() if v != "(none)"]
        if len(values) < 2:
            return True
        return len(set(values)) == 1

    def _primary_version(self) -> str:
        return self.config.version_sources[0].read()

    def _suggest_next_version(self, current: str) -> str:
        major, minor, patch = (int(x) for x in current.split("."))
        return f"{major}.{minor}.{patch + 1}"

    def _validate_version(self, version: str) -> None:
        if not VERSION_RE.match(version):
            raise ValueError(f"Invalid version (expected X.Y.Z): {version}")

    def _git_status_summary(self) -> tuple[str, bool]:
        status = self._git_output("status", "--short", "--branch")
        dirty = bool(self._git_output("status", "--porcelain"))
        return status, dirty

    def _watch_diff_summary(self, files: list[Path]) -> str:
        lines: list[str] = []
        for path in files:
            rel = path.relative_to(self.config.root)
            diff = self._run_git("diff", "--stat", str(rel))
            if diff.stdout.strip():
                lines.append(f"{rel}:")
                lines.append(diff.stdout.rstrip())
                diff_full = self._run_git("diff", "--unified=3", str(rel))
                if diff_full.stdout.strip():
                    lines.append(diff_full.stdout.rstrip())
            staged = self._run_git("diff", "--cached", "--stat", str(rel))
            if staged.stdout.strip():
                lines.append(f"{rel} (staged):")
                lines.append(staged.stdout.rstrip())
        if not lines:
            return "No local changes to watched files."
        return "\n".join(lines)

    def _watch_changed_in_worktree(self) -> dict[str, bool]:
        changed: dict[str, bool] = {}
        for group in self.config.watch_groups:
            group_changed = False
            for path in group.files:
                rel = str(path.relative_to(self.config.root))
                if self._run_git("diff", "--quiet", rel).returncode != 0:
                    group_changed = True
                    break
                if self._run_git("diff", "--cached", "--quiet", rel).returncode != 0:
                    group_changed = True
                    break
            changed[group.name] = group_changed
        return changed

    def _any_watch_changed(self, changed: dict[str, bool]) -> bool:
        return any(changed.values())

    def _read_multiline_bullets(self, section: str) -> list[str]:
        print()
        print(f'Bullet points for "{section}" (empty line to finish):')
        bullets: list[str] = []
        while True:
            line = input("  - ").strip()
            if not line:
                break
            bullets.append(line)
        return bullets

    def _render_changelog_section(self, version: str, release_date: str, sections: dict[str, list[str]]) -> str:
        lines = [f"## [{version}] - {release_date}", ""]
        has_content = False
        for name in self.config.changelog_sections:
            bullets = sections.get(name, [])
            if not bullets:
                continue
            has_content = True
            lines.append(f"### {name}")
            lines.append("")
            for bullet in bullets:
                lines.append(f"- {bullet}")
            lines.append("")
        if not has_content:
            lines.extend(["### Notes", "", "- Release", ""])
        return "\n".join(lines).rstrip() + "\n"

    def _update_changelog(self, version: str, release_date: str, sections: dict[str, list[str]]) -> str:
        text = self.config.changelog_path.read_text(encoding="utf-8")
        block = self._render_changelog_section(version, release_date, sections)
        marker = "\n## ["
        idx = text.find(marker)
        if idx == -1:
            raise RuntimeError(f"{self.config.changelog_path.name}: could not find first version section")
        updated = text[:idx] + "\n" + block + text[idx:]

        if self.config.repo_url:
            link_line = f"[{version}]: {self.config.repo_url}/releases/tag/v{version}"
            if link_line not in updated:
                updated = updated.rstrip() + "\n" + link_line + "\n"
        return updated

    def _finalize_changelog_from_file(self, version: str, release_date: str) -> str:
        text = self.config.changelog_path.read_text(encoding="utf-8")
        parsed = self._parse_changelog_top_section(text)
        if parsed is None or not parsed.is_unreleased:
            raise RuntimeError(
                f"{self.config.changelog_path.name}: expected top section "
                f'"## [X.Y.Z] - unreleased" for import'
            )

        updated, count = re.subn(
            r"^## \[([^\]]+)\] - [^\n]+$",
            f"## [{version}] - {release_date}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
        if count != 1:
            raise RuntimeError(f"{self.config.changelog_path.name}: could not update release header")

        next_version = self._suggest_next_version(version)
        insert = f"## [{next_version}] - unreleased\n\n"
        idx = updated.find("\n## [")
        if idx == -1:
            raise RuntimeError(f"{self.config.changelog_path.name}: could not find version section")
        updated = updated[: idx + 1] + insert + updated[idx + 1 :]

        if self.config.repo_url:
            link_line = f"[{version}]: {self.config.repo_url}/releases/tag/v{version}"
            if link_line not in updated:
                updated = updated.rstrip() + "\n" + link_line + "\n"
        return updated

    def _read_latest_compatibility_block(self) -> str:
        path = self.config.netbox_plugin_path
        if path is None:
            raise RuntimeError("netbox_plugin handler not configured")
        text = path.read_text(encoding="utf-8")
        match = re.search(
            r"(  - release: \S+\n    netbox_min: \S+\n    netbox_max: \S+)",
            text,
        )
        if not match:
            raise RuntimeError(f"Could not parse compatibility block from {path.name}")
        return match.group(1)

    def _parse_compatibility_limits(self, block: str) -> tuple[str, str]:
        min_match = re.search(r"netbox_min:\s*(\S+)", block)
        max_match = re.search(r"netbox_max:\s*(\S+)", block)
        if not min_match or not max_match:
            raise RuntimeError("Could not read netbox_min/netbox_max from compatibility block")
        return min_match.group(1), max_match.group(1)

    def _update_plugin_init(self, netbox_min: str, netbox_max: str) -> str:
        path = self.config.netbox_plugin_init_file
        if path is None:
            raise RuntimeError("netbox_plugin init_file not configured")
        text = path.read_text(encoding="utf-8")
        updated, min_count = re.subn(
            r'min_version\s*=\s*"[^"]+"',
            f'min_version = "{netbox_min}"',
            text,
            count=1,
        )
        if min_count != 1:
            raise RuntimeError(f"Could not update min_version in {path.name}")

        if re.search(r'max_version\s*=\s*"[^"]+"', updated):
            updated, max_count = re.subn(
                r'max_version\s*=\s*"[^"]+"',
                f'max_version = "{netbox_max}"',
                updated,
                count=1,
            )
            if max_count != 1:
                raise RuntimeError(f"Could not update max_version in {path.name}")
        else:
            updated, insert_count = re.subn(
                r'(min_version\s*=\s*"[^"]+"\n)',
                rf'\1    max_version = "{netbox_max}"\n',
                updated,
                count=1,
            )
            if insert_count != 1:
                raise RuntimeError(f"Could not insert max_version in {path.name}")
        return updated

    def _update_plugin_yaml(self, version: str) -> tuple[str, str, str]:
        path = self.config.netbox_plugin_path
        if path is None:
            raise RuntimeError("netbox_plugin handler not configured")
        text = path.read_text(encoding="utf-8")
        template = self._read_latest_compatibility_block()
        netbox_min, netbox_max = self._parse_compatibility_limits(template)

        if re.search(rf"^\s*-\s*release:\s*{re.escape(version)}\s*$", text, re.MULTILINE):
            return text, netbox_min, netbox_max

        new_block = (
            f"  - release: {version}\n"
            f"    netbox_min: {netbox_min}\n"
            f"    netbox_max: {netbox_max}"
        )
        compat_marker = "compatibility:\n"
        idx = text.find(compat_marker)
        if idx == -1:
            raise RuntimeError(f"compatibility: section not found in {path.name}")
        insert_at = idx + len(compat_marker)
        updated = text[:insert_at] + new_block + "\n" + text[insert_at:]
        return updated, netbox_min, netbox_max

    def _apply_file_updates(self, version: str, release_date: str, sections: dict[str, list[str]], dry_run: bool) -> None:
        updates: dict[Path, str] = {}
        for source in self.config.version_sources:
            updates[source.file] = source.write(version)
        if self.config.netbox_plugin_path:
            plugin_yaml, netbox_min, netbox_max = self._update_plugin_yaml(version)
            updates[self.config.netbox_plugin_path] = plugin_yaml
            if self.config.netbox_plugin_init_file:
                updates[self.config.netbox_plugin_init_file] = self._update_plugin_init(
                    netbox_min, netbox_max
                )
        if self._use_changelog_import:
            updates[self.config.changelog_path] = self._finalize_changelog_from_file(version, release_date)
        else:
            updates[self.config.changelog_path] = self._update_changelog(version, release_date, sections)

        for path, content in updates.items():
            rel = path.relative_to(self.config.root)
            if dry_run:
                print(f"[dry-run] would update: {rel}")
                continue
            path.write_text(content, encoding="utf-8")
            print(f"Updated: {rel}")

    def _show_git_diff(self) -> None:
        result = self._run_git("diff")
        staged = self._run_git("diff", "--cached")
        output = ""
        if staged.stdout:
            output += staged.stdout
        if result.stdout:
            output += result.stdout
        if output.strip():
            print(output.rstrip())
        else:
            print("(no diff)")

    def _git_commit(self, version: str, dry_run: bool) -> None:
        message = f"Release v{version}"
        if dry_run:
            print(f"[dry-run] git add + git commit -m {message!r}")
            return
        add = self._run_git("add", *self.config.commit_files)
        if add.returncode != 0:
            raise RuntimeError(add.stderr.strip() or "git add failed")
        commit = self._run_git("commit", "-m", message)
        if commit.returncode != 0:
            raise RuntimeError(commit.stderr.strip() or "git commit failed")
        print(commit.stdout.strip() or f"Commit created: {message}")

    def _ensure_github_ssh_remote(self) -> None:
        result = self._run_git("remote", "get-url", "origin", remote=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git remote get-url origin failed")
        url = result.stdout.strip()
        if url.startswith("git@github.com:"):
            return
        match = re.match(r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$", url)
        if not match:
            return
        ssh_url = f"git@github.com:{match.group(1)}/{match.group(2)}.git"
        set_url = self._run_git("remote", "set-url", "origin", ssh_url, remote=True)
        if set_url.returncode != 0:
            raise RuntimeError(set_url.stderr.strip() or "git remote set-url failed")
        print(f"origin switched to SSH: {ssh_url}")

    def _verify_github_ssh(self) -> None:
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-T", "git@github.com"]
        if not self._running_as_git_user() and os.geteuid() == 0:
            cmd = ["sudo", "-u", self.config.git_user, "--", *cmd]
        result = subprocess.run(cmd, text=True, capture_output=True)
        combined = f"{result.stdout}\n{result.stderr}"
        if "successfully authenticated" not in combined.lower():
            raise RuntimeError(
                f"SSH to GitHub failed for user {self.config.git_user}. "
                "Check: ssh -T git@github.com"
            )

    def _git_tag(self, version: str, dry_run: bool) -> None:
        tag = f"v{version}"
        if dry_run:
            print(f"[dry-run] git tag {tag}")
            return
        result = self._run_git("tag", tag)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"git tag {tag} failed")
        print(f"Tag created: {tag}")

    def _git_push(self, version: str, dry_run: bool) -> None:
        tag = f"v{version}"
        git_user = self.config.git_user
        if dry_run:
            prefix = f"sudo -u {git_user} " if not self._running_as_git_user() and os.geteuid() == 0 else ""
            print(f"[dry-run] ensure SSH origin + verify github.com")
            print(f"[dry-run] {prefix}git push && {prefix}git push origin {tag}")
            return
        self._ensure_github_ssh_remote()
        self._verify_github_ssh()
        for args in (["push"], ["push", "origin", tag]):
            result = self._run_git(*args, remote=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
            if result.stdout.strip():
                print(result.stdout.strip())
        print(
            f"Push complete (branch + tag via SSH as {git_user}; "
            "GitHub Actions creates the release)."
        )

    def _git_promote_to_main(self, version: str, dry_run: bool) -> None:
        script = self.config.root / "scripts" / "promote_release_to_main.sh"
        if not script.is_file():
            raise RuntimeError(f"Missing promote script: {script}")
        cmd: list[str] = [str(script), "--version", version]
        if dry_run:
            cmd.append("--dry-run")
        env = os.environ.copy()
        env.setdefault("GIT_USER", self.config.git_user)
        env.setdefault("DEV_BRANCH", self.config.dev_branch)
        env.setdefault("MAIN_BRANCH", self.config.release_branch)
        if dry_run:
            print(f"[dry-run] {' '.join(cmd)}")
            return
        if not self._running_as_git_user() and os.geteuid() == 0:
            cmd = ["sudo", "-u", self.config.git_user, "--", *cmd]
        result = subprocess.run(
            cmd,
            cwd=self.config.root,
            env=env,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "promote_release_to_main.sh failed")
        if result.stdout.strip():
            print(result.stdout.strip())
        print(
            f"Promoted {self.config.dev_branch} → {self.config.release_branch} "
            f"(merge commit; tag v{version} reachable from default branch)."
        )

    def _print_final_reminders(self, version: str, watch_changed: dict[str, bool]) -> None:
        _print_header("Next steps")
        step = 1
        if self.config.repo_url:
            print(
                f"{step}. GitHub release + PyPI: tag v{version} push triggers "
                f"{self.config.repo_url}/actions/workflows/release-on-tag.yml "
                "(SSH push as christian — no gh login)."
            )
            print(
                f"   Re-run release workflow: ./scripts/github_release.sh --version {version} --force"
            )
            step += 1
        if self.config.pypi_note:
            print(f"{step}. {self.config.pypi_note}")
            step += 1
        reminder_idx = step
        for group in self.config.watch_groups:
            if watch_changed.get(group.name) and group.reminder:
                print(f"{reminder_idx}. {group.reminder}")
                reminder_idx += 1
        print()

    def _parse_sections_arg(self, raw: str | None) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {name: [] for name in self.config.changelog_sections}
        if not raw:
            return sections
        current: str | None = None
        for line in raw.splitlines():
            header = re.match(r"^(\w+):\s*$", line.strip())
            if header and header.group(1) in sections:
                current = header.group(1)
                continue
            bullet = re.match(r"^-\s*(.+)", line.strip())
            if bullet and current:
                sections[current].append(bullet.group(1))
        return sections

    def run(self, args: argparse.Namespace) -> int:
        config = self.config
        interactive = not (args.yes or args.version)

        _print_header(f"{config.project_name} Release Wizard")
        print("This script guides you through version bump, CHANGELOG, commit, tag, and push.")
        print(f"Project directory: {config.root}")
        if config.config_path:
            print(f"Config: {config.config_path.relative_to(config.root)}")
        else:
            print("Config: (defaults — pyproject.toml + CHANGELOG.md)")

        try:
            self._git_output("rev-parse", "--is-inside-work-tree")
        except RuntimeError:
            print("ERROR: Not a git repository.", file=sys.stderr)
            return 1

        _print_header("Step 1 — Current version & git status")
        versions = self._collect_versions()
        for label, value in versions.items():
            print(f"  {label}: {value}")
        if not self._versions_in_sync():
            print()
            print("WARNING: Version numbers are not consistent across files.")

        status, dirty = self._git_status_summary()
        print()
        print(status or "(working tree clean)")
        if dirty:
            print()
            print("Note: Uncommitted changes present (release commit may include more than version/CHANGELOG).")

        watch_changed: dict[str, bool] = {}
        skip_watch = args.skip_watch_check or args.skip_schema_check
        if config.has_watch_groups and not skip_watch:
            watch_changed = self._watch_changed_in_worktree()
            any_changed = self._any_watch_changed(watch_changed)
            _print_header("Step 2 — Watched file changes (optional)")
            for group in config.watch_groups:
                print(f"{group.name}:")
                for path in group.files:
                    print(f"  - {path.relative_to(config.root)}")
            show_watch = False
            if interactive:
                show_watch = _ask_yes_no("Show watched file diff?", default=any_changed)
            else:
                show_watch = any_changed
            if show_watch:
                for group in config.watch_groups:
                    print()
                    print(f"--- {group.name} ---")
                    print(self._watch_diff_summary(group.files))

        _print_header("Step 3 — New version")
        current = self._primary_version()
        suggested = self._suggest_next_version(current)
        if args.version:
            new_version = args.version
        elif interactive:
            print(f"Current version: {current}")
            print(f"Suggested (patch bump): {suggested}")
            new_version = _ask_text("New version", suggested)
        else:
            new_version = suggested

        try:
            self._validate_version(new_version)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

        if new_version == current and interactive and not _ask_yes_no(
            f"Version {new_version} is the same as the current one. Continue anyway?",
            default=False,
        ):
            print("Aborted.")
            return 0

        if args.date:
            release_date = args.date
        elif interactive:
            release_date = _ask_text("Release date (YYYY-MM-DD)", date.today().isoformat())
        else:
            release_date = date.today().isoformat()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", release_date):
            print("ERROR: Invalid date (expected YYYY-MM-DD).", file=sys.stderr)
            return 1

        _print_header("Step 4 — CHANGELOG")
        allow_import = not args.no_changelog_import and not args.changelog
        if args.changelog:
            sections = self._parse_sections_arg(args.changelog)
        else:
            sections = self._collect_changelog_sections(
                interactive,
                allow_import=allow_import,
            )
            if self._use_changelog_import:
                parsed = self._read_changelog_import()
                if parsed and parsed.version != new_version:
                    print()
                    print(
                        f"NOTE: CHANGELOG unreleased section is [{parsed.version}], "
                        f"release version is [{new_version}] — header will use {new_version}."
                    )

        print()
        if self._use_changelog_import:
            print("Using CHANGELOG.md unreleased section (header/date will be finalized on write).")
        print("CHANGELOG section preview:")
        print("-" * 40)
        print(self._render_changelog_section(new_version, release_date, sections).rstrip())
        print("-" * 40)

        _print_header("Step 5 — Update files")
        print("Files to update:")
        for source in config.version_sources:
            print(f"  - {source.label}")
        if config.netbox_plugin_path:
            rel = config.netbox_plugin_path.relative_to(config.root)
            print(f"  - {rel} (compatibility release {new_version})")
        if config.netbox_plugin_init_file:
            rel = config.netbox_plugin_init_file.relative_to(config.root)
            print(f"  - {rel} (min_version / max_version)")
        print(f"  - {config.changelog_path.relative_to(config.root)}")

        apply_ok = args.yes or args.dry_run
        if interactive and not args.dry_run:
            apply_ok = _ask_yes_no("Write changes now?", default=True)
        if not apply_ok:
            print("Aborted before writing.")
            return 0

        try:
            self._apply_file_updates(new_version, release_date, sections, dry_run=args.dry_run)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

        if args.dry_run:
            print("[dry-run] Done — no files written.")
            return 0

        _print_header("Step 6 — Git diff")
        self._show_git_diff()

        do_commit = args.commit
        if interactive or not do_commit:
            if interactive:
                do_commit = _ask_yes_no(f'Create git commit "Release v{new_version}"?', default=False)
            elif args.commit:
                do_commit = True

        if do_commit:
            if interactive and not _ask_yes_no("Diff reviewed — really create commit?", default=False):
                print("Commit skipped.")
            else:
                try:
                    self._git_commit(new_version, dry_run=False)
                except RuntimeError as exc:
                    print(f"ERROR: {exc}", file=sys.stderr)
                    return 1

        do_tag = args.tag
        if interactive:
            do_tag = _ask_yes_no(f"Create git tag v{new_version}?", default=False)
        if do_tag:
            try:
                self._git_tag(new_version, dry_run=False)
            except RuntimeError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1

        do_push = args.push
        if interactive:
            do_push = _ask_yes_no("Push to origin (branch + tag)?", default=False)
        elif args.push and not args.yes:
            print("Note: --push without --yes requires interactive confirmation.")
            do_push = _ask_yes_no("Really push?", default=False)

        if do_push:
            try:
                self._git_push(new_version, dry_run=False)
            except RuntimeError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1

            do_promote = args.promote_main or config.auto_promote_to_main
            if interactive and not args.promote_main and config.auto_promote_to_main:
                do_promote = _ask_yes_no(
                    f"Merge {config.dev_branch} into {config.release_branch} "
                    f"(so tag v{new_version} stays on default branch)?",
                    default=True,
                )
            elif interactive and args.promote_main:
                do_promote = True
            if do_promote:
                try:
                    self._git_promote_to_main(new_version, dry_run=False)
                except RuntimeError as exc:
                    print(f"ERROR: {exc}", file=sys.stderr)
                    return 1
        elif interactive:
            print()
            print("Push deliberately skipped — you can push manually later:")
            if config.manual_push_hint:
                print(f"  {config.manual_push_hint}")
            print(f"  sudo -u {config.git_user} git -C {config.root} push origin v{new_version}")

        if not watch_changed and config.has_watch_groups:
            watch_changed = self._watch_changed_in_worktree()
        self._print_final_reminders(new_version, watch_changed)
        return 0


def _resolve_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    project_root = SCRIPT_DIR.parent
    if (project_root / "release-wizard.toml").is_file() or (project_root / "netbox-plugin.yaml").is_file():
        return project_root
    git_root = _detect_git_root(SCRIPT_DIR)
    return git_root or project_root


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        help="Project root (default: git toplevel or parent of scripts/)",
    )
    parser.add_argument(
        "--config",
        help="Path to release-wizard.toml (default: <root>/release-wizard.toml)",
    )
    parser.add_argument("--version", help="New version number (X.Y.Z)")
    parser.add_argument("--date", help="Release date (YYYY-MM-DD), default: today")
    parser.add_argument(
        "--changelog",
        help="Changelog text (categories as 'Added:' etc., bullet points with '-')",
    )
    parser.add_argument(
        "--no-changelog-import",
        action="store_true",
        help="Do not read the unreleased section from CHANGELOG.md",
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Answer all confirmations with yes")
    parser.add_argument("--commit", action="store_true", help="Create git commit")
    parser.add_argument("--tag", action="store_true", help="Create git tag vX.Y.Z")
    parser.add_argument("--push", action="store_true", help="Push branch and tag to origin")
    parser.add_argument(
        "--promote-main",
        action="store_true",
        help=f"After push, merge dev into main (see scripts/promote_release_to_main.sh)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show actions only, do not write")
    parser.add_argument(
        "--skip-watch-check",
        action="store_true",
        help="Skip watched-file diff step",
    )
    parser.add_argument(
        "--skip-schema-check",
        action="store_true",
        help="Alias for --skip-watch-check (backward compatible)",
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()
    root = _resolve_root(args.root)
    config_path = Path(args.config).resolve() if args.config else None
    config = _load_config(root, config_path)
    return ReleaseWizard(config).run(args)


if __name__ == "__main__":
    raise SystemExit(main())
