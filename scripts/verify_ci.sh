#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ci_workflow="$repo_root/.github/workflows/ci.yml"
contracts_workflow="$repo_root/.github/workflows/contracts.yml"

check_contains() {
  local file_path="$1"
  local expected="$2"
  local failure_message="$3"

  if ! grep -Fq "$expected" "$file_path"; then
    echo "$failure_message" >&2
    exit 1
  fi
}

check_contains "$ci_workflow" "image: redis:7-alpine" "CI workflow is missing the Redis service"
check_contains "$ci_workflow" "REDIS_URL: redis://localhost:6379/0" "CI workflow is missing the Redis test URL"
check_contains "$contracts_workflow" "cargo clippy --all-targets --all-features -- -D warnings" "Contracts workflow is missing clippy"

echo "All CI verification checks passed."
