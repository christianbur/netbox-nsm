#!/usr/bin/env bash
# Push a release tag via SSH (as christian) to trigger GitHub Actions release-on-tag.yml.
#
# GitHub Releases are created by CI on tag push — no gh auth / browser login required.
#
# Usage:
#   ./scripts/github_release.sh --version 0.4.14
#   sudo ./scripts/github_release.sh --version 0.4.14
#   ./scripts/github_release.sh --version 0.4.14 --force   # re-push tag (re-run workflow)
#
# Typical flow (also wired into release_wizard.py after --push):
#   1. Commit + tag on dev
#   2. ./scripts/github_release.sh --version X.Y.Z
#   3. ./scripts/promote_release_to_main.sh --version X.Y.Z
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=git_ssh_helpers.sh
source "${SCRIPT_DIR}/git_ssh_helpers.sh"

VERSION=""
FORCE=0
DRY_RUN=0
REPO_URL="${REPO_URL:-https://github.com/christianbur/netbox-nsm}"

usage() {
  cat <<EOF
Usage: $(basename "$0") --version X.Y.Z [options]

Push tag vX.Y.Z to origin over SSH (user: ${GIT_USER}). GitHub Actions creates the
release from CHANGELOG.md (.github/workflows/release-on-tag.yml).

Options:
  --version X.Y.Z   Required release version (without leading v)
  --force           Delete and re-push the remote tag (re-triggers workflow)
  --dry-run         Print planned commands only
  -h, --help        This help

Environment:
  GIT_USER=${GIT_USER}
  REPO_URL=${REPO_URL}
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:?--version requires X.Y.Z}"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$VERSION" ]]; then
  echo "--version is required." >&2
  usage >&2
  exit 1
fi

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid version (expected X.Y.Z): ${VERSION}" >&2
  exit 1
fi

TAG="v${VERSION}"

plan() {
  echo "[dry-run] $*"
}

run_step() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    plan "$*"
    return 0
  fi
  "$@"
}

ensure_safe_directory "$ROOT_DIR"
ensure_github_ssh_remote "$ROOT_DIR"
verify_github_ssh

if ! git_user -C "$ROOT_DIR" rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Local tag ${TAG} not found. Create it first (release_wizard --tag or git tag ${TAG})." >&2
  exit 1
fi

tag_commit="$(git_user -C "$ROOT_DIR" rev-parse "$TAG^{commit}")"
echo "Tag ${TAG} → ${tag_commit}"

if [[ "$FORCE" -eq 1 ]]; then
  run_step git_user -C "$ROOT_DIR" push origin ":refs/tags/${TAG}" || true
fi

run_step git_user -C "$ROOT_DIR" push origin "$TAG"

echo "Tag ${TAG} pushed via SSH as ${GIT_USER}."
echo "GitHub Actions will create the release: ${REPO_URL}/actions/workflows/release-on-tag.yml"
echo "Release page (after workflow): ${REPO_URL}/releases/tag/${TAG}"
