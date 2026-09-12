#!/usr/bin/env bash
set -euo pipefail

UPSTREAM_URL="https://github.com/zhihulite/zhihu_web.git"
UPSTREAM_BRANCH="main"
STATE_FILE=".upstream-state"

log() {
  printf '[sync-upstream] %s\n' "$*"
}

fail() {
  printf '[sync-upstream] ERROR: %s\n' "$*" >&2

  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    printf '::error::%s\n' "$*" >&2
  fi

  exit 1
}

emit_output() {
  local key="$1"
  local value="$2"

  printf '%s=%s\n' "$key" "$value"

  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    printf '%s=%s\n' "$key" "$value" >> "$GITHUB_OUTPUT"
  fi
}

read_state_value() {
  local key="$1"

  awk -F= -v key="$key" \
    '$1 == key { sub(/^[^=]*=/, ""); print; exit }' \
    "$STATE_FILE"
}

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" \
  || fail "not inside a Git work tree"

cd "$repo_root"

[[ -f "$STATE_FILE" ]] \
  || fail "$STATE_FILE is missing"

command -v rsync >/dev/null 2>&1 \
  || fail "rsync is required"

command -v tar >/dev/null 2>&1 \
  || fail "tar is required"

state_sha="$(read_state_value upstream_sha)"

[[ "$state_sha" =~ ^[0-9a-fA-F]{40}$ ]] \
  || fail "invalid upstream_sha in $STATE_FILE"

state_sha="${state_sha,,}"

log "fetching ${UPSTREAM_URL} ${UPSTREAM_BRANCH}"

git fetch \
  --no-tags \
  --depth=1 \
  "$UPSTREAM_URL" \
  "refs/heads/${UPSTREAM_BRANCH}"

upstream_sha="$(git rev-parse FETCH_HEAD)"

[[ "$upstream_sha" =~ ^[0-9a-f]{40}$ ]] \
  || fail "could not resolve upstream HEAD SHA"

emit_output upstream_sha "$upstream_sha"

if [[ "$upstream_sha" == "$state_sha" ]]; then
  log "upstream is unchanged at $upstream_sha"

  emit_output upstream_changed false

  exit 0
fi

log "upstream changed: $state_sha -> $upstream_sha"

tmp_dir="$(mktemp -d)"

trap 'rm -rf "$tmp_dir"' EXIT

snapshot_dir="$tmp_dir/upstream"

mkdir -p "$snapshot_dir"

git archive --format=tar "$upstream_sha" \
  | tar -xf - -C "$snapshot_dir"

overlay_paths=(
  "Dockerfile"
  ".dockerignore"
  "deploy"
  ".upstream-state"
  "SELFHOST.md"
)

conflicts=()

for path in "${overlay_paths[@]}"; do
  if [[ -e "$snapshot_dir/$path" || -L "$snapshot_dir/$path" ]]; then
    conflicts+=("$path")
  fi
done

if ((${#conflicts[@]} > 0)); then
  printf '[sync-upstream] ERROR: upstream now contains fork overlay path(s):\n' >&2

  for path in "${conflicts[@]}"; do
    printf '  - %s\n' "$path" >&2
  done

  printf '[sync-upstream] Refusing to overwrite fork-managed content. Resolve manually.\n' >&2

  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    printf '::error::Upstream overlay conflict detected; refusing automatic sync.\n' >&2
  fi

  exit 1
fi

fork_preserve_paths=(
  "src/components/FeedCard.vue"
  "src/components/home/HotListCard.vue"
  "src/style.css"
)

log "preserving fork source overrides"

for path in "${fork_preserve_paths[@]}"; do
  log "  preserve: $path"
done

log "synchronizing upstream snapshot while preserving fork overlay and source overrides"

rsync_args=(
  --archive
  --delete

  "--exclude=/.git/"
  "--exclude=/.github/workflows/"

  "--exclude=/Dockerfile"
  "--exclude=/.dockerignore"
  "--exclude=/deploy/"
  "--exclude=/.upstream-state"
  "--exclude=/SELFHOST.md"
)

for path in "${fork_preserve_paths[@]}"; do
  rsync_args+=("--exclude=/$path")
done

rsync \
  "${rsync_args[@]}" \
  "$snapshot_dir/" \
  "$repo_root/"

emit_output upstream_changed true

log "workspace synchronized to upstream $upstream_sha; state file intentionally not updated yet"