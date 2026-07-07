# Release workflow (netbox-nsm)

Development happens on **`dev`**. GitHub’s default branch is **`main`**. Release
tags are pushed on **`dev`** via **SSH** (user `christian`); GitHub Actions creates
the release and publishes to PyPI (`.github/workflows/release-on-tag.yml`).

## Standard release

1. Finish changes on `dev`.
2. Run the release wizard (from repo root or dev container mount):

   ```bash
   python3 scripts/release_wizard.py
   ```

   Or non-interactive:

   ```bash
   python3 scripts/release_wizard.py --version X.Y.Z --yes --commit --tag --push --promote-main
   ```

3. The wizard bumps version files, updates `CHANGELOG.md`, commits, tags `vX.Y.Z` on
   **`dev`**, pushes **`dev`** + tag over **SSH**, merges **`dev` → `main`**
   (regular merge, **not** squash), and pushes **`main`**.

4. **GitHub Release** is created automatically when the tag is pushed (no `gh auth`,
   no browser). Optional re-push:

   ```bash
   sudo ./scripts/github_release.sh --version X.Y.Z
   sudo ./scripts/github_release.sh --version X.Y.Z --force   # re-trigger workflow
   ```

## Why promote to `main`?

Tags are created on the release commit on **`dev`**. GitHub only shows tags on the
default branch if the tagged commit is **reachable from `main`**.

If you merge `dev` into `main` with **squash merge**, GitHub creates a **new**
commit SHA. The tag still points at the old `dev` commit, so the tag “disappears”
from the default branch view and release workflows may not see it.

**Always use a regular merge commit** (`--no-ff`) when promoting releases to
`main`.

## Manual promote (without wizard)

After a release on `dev` (tag already pushed):

```bash
sudo ./scripts/promote_release_to_main.sh --version X.Y.Z
```

## Manual GitHub release (tag already on origin)

```bash
sudo ./scripts/github_release.sh --version X.Y.Z
```

Uses `git@github.com:…` as `christian` (same pattern as `homelab/tools/github-push.sh`).

## GitHub pull requests

If you use a PR instead of the script:

- Choose **“Create a merge commit”** (not squash, not rebase).
- Do **not** retag after squash — fix by merging `dev` into `main` properly.

## Push helper (homelab)

`tools/github-push.sh netbox-nsm` pushes **`dev` only**. After release, run promote
or use `--promote-main` in the wizard so **`main`** and tag visibility stay in sync.
