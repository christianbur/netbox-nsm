#!/usr/bin/env bash
# Shared git/SSH helpers for netbox-nsm release scripts (same idea as homelab/tools/github-push.sh).
set -euo pipefail

GIT_USER="${GIT_USER:-christian}"

run_as_git_user() {
  if [[ "$(id -un)" == "$GIT_USER" ]]; then
    "$@"
    return
  fi
  if [[ "$(id -u)" -eq 0 ]]; then
    sudo -u "$GIT_USER" -- "$@"
    return
  fi
  echo "Run as root or as ${GIT_USER} (current: $(id -un))." >&2
  exit 1
}

git_user() {
  run_as_git_user git "$@"
}

https_to_ssh() {
  local url="$1"
  if [[ "$url" =~ ^https://github.com/([^/]+)/([^/]+)(\.git)?$ ]]; then
    printf 'git@github.com:%s/%s.git' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]%.git}"
    return 0
  fi
  printf '%s' "$url"
}

ensure_github_ssh_remote() {
  local repo_dir="$1"
  local remote_url
  remote_url="$(git_user -C "$repo_dir" remote get-url origin 2>/dev/null || true)"
  if [[ -z "$remote_url" ]]; then
    echo "No origin remote in ${repo_dir}" >&2
    exit 1
  fi
  if [[ "$remote_url" == git@github.com:* ]]; then
    return 0
  fi
  local ssh_url
  ssh_url="$(https_to_ssh "$remote_url")"
  if [[ "$ssh_url" != "$remote_url" ]]; then
    echo "origin ${repo_dir}: ${remote_url} → ${ssh_url}"
    git_user -C "$repo_dir" remote set-url origin "$ssh_url"
  fi
}

ensure_safe_directory() {
  local dir="$1"
  git_user config --global --add safe.directory "$dir" 2>/dev/null || true
}

verify_github_ssh() {
  local output
  output="$(run_as_git_user ssh -o BatchMode=yes -o ConnectTimeout=10 -T git@github.com 2>&1 || true)"
  if grep -qi 'successfully authenticated' <<< "$output"; then
    return 0
  fi
  echo "SSH to GitHub failed for user ${GIT_USER}. Check: ssh -T git@github.com" >&2
  exit 1
}
