# Release workflow (netbox-nsm)

Development happens on **`dev`**. GitHub’s default branch is **`main`**. PyPI publish
(`.github/workflows/publish.yml`) triggers on **GitHub Releases** tied to tags on
**`main`**.

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
   **`dev`**, pushes **`dev`** + tag, then merges **`dev` → `main`** (regular merge,
   **not** squash) and pushes **`main`**.

4. On GitHub: [Create release](https://github.com/christianbur/netbox-nsm/releases/new)
   from tag `vX.Y.Z`, paste the CHANGELOG section.

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
./scripts/promote_release_to_main.sh --version X.Y.Z
```

As root (uses `sudo -u christian` for SSH):

```bash
sudo ./scripts/promote_release_to_main.sh --version X.Y.Z
```

## GitHub pull requests

If you use a PR instead of the script:

- Choose **“Create a merge commit”** (not squash, not rebase).
- Do **not** retag after squash — fix by merging `dev` into `main` properly.

## Push helper (homelab)

`tools/github-push.sh netbox-nsm` pushes **`dev` only**. After release, run promote
or use `--promote-main` in the wizard so **`main`** and tag visibility stay in sync.
