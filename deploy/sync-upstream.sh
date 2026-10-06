#!/usr/bin/env bash
set -euo pipefail

UPSTREAM_URL="${UPSTREAM_URL:-https://github.com/zhihulite/zhihu_web.git}"
UPSTREAM_BRANCH="${UPSTREAM_BRANCH:-main}"
STATE_FILE="${STATE_FILE:-.upstream-state}"

fail() {
    printf '[sync-upstream] %s\n' "$*" >&2
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

state_value() {
    local key="$1"
    awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "$STATE_FILE"
}

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || fail '当前目录不是 Git 工作区'
cd "$repo_root"
[[ -f "$STATE_FILE" ]] || fail "缺少 $STATE_FILE"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || fail '工作区存在未提交内容'

base_sha="$(state_value upstream_sha)"
[[ "$base_sha" =~ ^[0-9a-fA-F]{40}$ ]] || fail "$STATE_FILE 中的 upstream_sha 无效"
base_sha="${base_sha,,}"
original_head="$(git rev-parse HEAD)"

git fetch --no-tags "$UPSTREAM_URL" "refs/heads/${UPSTREAM_BRANCH}" || fail '获取上游失败'
upstream_sha="$(git rev-parse FETCH_HEAD)"
[[ "$upstream_sha" =~ ^[0-9a-f]{40}$ ]] || fail '无法解析上游提交'
emit_output upstream_sha "$upstream_sha"

if [[ "$upstream_sha" == "$base_sha" ]]; then
    emit_output upstream_changed false
    exit 0
fi

git cat-file -e "${base_sha}^{commit}" 2>/dev/null || fail '记录的上游基准不在当前上游历史中'
git merge-base --is-ancestor "$base_sha" "$upstream_sha" || fail '上游历史已改写，需要人工重新确定同步基准'

protected_conflicts=()
while IFS= read -r -d '' path; do
    case "$path" in
        Dockerfile|.dockerignore|.upstream-state|SELFHOST.md|deploy|deploy/*)
            protected_conflicts+=("$path")
            ;;
    esac
done < <(git diff --name-only -z --no-renames "$base_sha" "$upstream_sha")

if ((${#protected_conflicts[@]} > 0)); then
    printf '[sync-upstream] 上游修改了分支部署文件：\n' >&2
    printf '  %s\n' "${protected_conflicts[@]}" >&2
    fail '请人工处理部署文件冲突'
fi

patch_file="$(mktemp)"
trap 'rm -f "$patch_file"' EXIT

git diff --binary --full-index --no-renames "$base_sha" "$upstream_sha" -- . \
    ':(exclude).github/workflows/**' \
    ':(exclude)html/**' \
    ':(exclude)Dockerfile' \
    ':(exclude).dockerignore' \
    ':(exclude)deploy/**' \
    ':(exclude).upstream-state' \
    ':(exclude)SELFHOST.md' > "$patch_file"

if [[ -s "$patch_file" ]] && ! git apply --3way --index --whitespace=nowarn "$patch_file"; then
    conflicts="$(git diff --name-only --diff-filter=U || true)"
    git reset --hard "$original_head" >/dev/null
    if [[ -n "$conflicts" ]]; then
        printf '[sync-upstream] 未能自动合并以下上游改动：\n%s\n' "$conflicts" >&2
    fi
    fail '上游改动与分支修改冲突，工作区已恢复'
fi

emit_output upstream_changed true
