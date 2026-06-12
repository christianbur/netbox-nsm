#!/usr/bin/env bash
# Merge dev into main (regular merge, NOT squash) so release tags on dev stay
# reachable from the default branch on GitHub.
#
# Usage:
#   ./scripts/promote_release_to_main.sh
#   ./scripts/promote_release_to_main.sh --version 0.4.0
#   ./scripts/promote_release_to_main.sh --dry-run
#
# When run as root, git uses sudo -u ${GIT_USER} (same as release_wizard.py).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

GIT_USER="${GIT_USER:-christian}"
DEV_BRANCH="${DEV_BRANCH:-dev}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
VERSION=""
DRY_RUN=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Merge ${DEV_BRANCH} into ${MAIN_BRANCH} with a merge commit (no squash) and push
${MAIN_BRANCH}. Release tags on ${DEV_BRANCH} then remain visible on GitHub's
default branch.

Options:
  --version X.Y.Z   Version for merge commit message (optional)
  --dry-run         Show planned git commands only
  -h, --help        This help

Environment:
  GIT_USER=${GIT_USER}
  DEV_BRANCH=${DEV_BRANCH}
  MAIN_BRANCH=${MAIN_BRANCH}
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:?--version requires X.Y.Z}"
      shift 2
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

run_git() {
  if [[ "$(id -un)" == "$GIT_USER" ]]; then
    git -C "$ROOT_DIR" "$@"
  elif [[ "$(id -u)" -eq 0 ]]; then
    sudo -u "$GIT_USER" -- git -C "$ROOT_DIR" "$@"
  else
    echo "Run as root or as ${GIT_USER} (current: $(id -un))." >&2
    exit 1
  fi
}

plan() {
  echo "[dry-run] $*"
}

do_fetch() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    plan "git fetch origin ${DEV_BRANCH} ${MAIN_BRANCH}"
    return 0
  fi
  run_git fetch origin "${DEV_BRANCH}" "${MAIN_BRANCH}"
}

ensure_clean() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    return 0
  fi
  if [[ -n "$(run_git status --porcelain)" ]]; then
    echo "Working tree is not clean. Commit or stash changes first." >&2
    exit 1
  fi
}

merge_message() {
  if [[ -n "$VERSION" ]]; then
    printf 'Merge %s into %s for release v%s' "$DEV_BRANCH" "$MAIN_BRANCH" "$VERSION"
  else
    printf 'Merge %s into %s' "$DEV_BRANCH" "$MAIN_BRANCH"
  fi
}

promote() {
  local previous_branch merge_msg
  previous_branch="$(run_git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "$DEV_BRANCH")"
  merge_msg="$(merge_message)"

  do_fetch
  ensure_clean

  if [[ "$DRY_RUN" -eq 1 ]]; then
    plan "git checkout ${MAIN_BRANCH}  # create tracking branch if missing"
    plan "git merge --no-ff origin/${DEV_BRANCH} -m '${merge_msg}'"
    plan "git push origin ${MAIN_BRANCH}"
    plan "git checkout ${previous_branch}"
    return 0
  fi

  if run_git show-ref --verify --quiet "refs/remotes/origin/${MAIN_BRANCH}"; then
    if run_git show-ref --verify --quiet "refs/heads/${MAIN_BRANCH}"; then
      run_git checkout "$MAIN_BRANCH"
      run_git pull --ff-only origin "$MAIN_BRANCH"
    else
      run_git checkout -b "$MAIN_BRANCH" "origin/${MAIN_BRANCH}"
    fi
  else
    echo "Remote branch origin/${MAIN_BRANCH} not found." >&2
    exit 1
  fi

  if run_git merge-base --is-ancestor "origin/${DEV_BRANCH}" HEAD; then
    echo "${MAIN_BRANCH} already contains ${DEV_BRANCH} (nothing to merge)."
  else
    run_git merge --no-ff "origin/${DEV_BRANCH}" -m "$merge_msg"
  fi

  run_git push origin "$MAIN_BRANCH"

  if [[ "$previous_branch" != "$MAIN_BRANCH" ]]; then
    run_git checkout "$previous_branch"
  fi

  echo "Promoted ${DEV_BRANCH} → ${MAIN_BRANCH} (merge commit, tags on ${DEV_BRANCH} now reachable from ${MAIN_BRANCH})."
}

promote
