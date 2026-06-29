#!/usr/bin/env bash
# Fail if production code imports legacy analyzer paths (tests may still patch them).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PATTERN='from netbox_nsm\.(analysis|analyzer|object_report)\.|import netbox_nsm\.(analysis|analyzer|object_report)\.'

if rg -n "$PATTERN" netbox_nsm \
  --glob '!netbox_nsm/analysis/**' \
  --glob '!netbox_nsm/analyzer/**' \
  --glob '!netbox_nsm/object_report/**' \
  --glob '!netbox_nsm/tests/**' \
  --glob '!**/__pycache__/**'; then
  echo "Legacy analyzer imports found in non-shim code (use netbox_nsm.analyzers.*)." >&2
  exit 1
fi

echo "No legacy analyzer imports outside shims/tests."
