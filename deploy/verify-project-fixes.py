from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
errors = []


def read(rel):
    path = ROOT / rel
    if not path.exists():
        errors.append(f"missing {rel}")
        return ""
    return path.read_text(encoding="utf-8")


def require(rel, token, label):
    text = read(rel)
    if token not in text:
        errors.append(f"{rel}: {label}")
    return text


def forbid(rel, token, label):
    text = read(rel)
    if token in text:
        errors.append(f"{rel}: {label}")
    return text


style = read("src/style.css")
if len(style.splitlines()) > 90:
    errors.append("src/style.css: exceeds 90 lines")

require("src/App.vue", "installPagedScroll(f7);", "paged scroll manager is not installed")
require("src/utils/paged-scroll.js", "new MutationObserver", "dynamic scroll observer is missing")
require("src/utils/paged-scroll.js", "new ResizeObserver", "viewport fill observer is missing")

http = read("src/api/http.js")
for token, label in [
    ("get data() {\n\t\treturn this._data;", "data getter is still consumptive"),
    ("is_end: source.is_end === true || !source.next", "paging end normalization is missing"),
    ("const { data, paging, ...extra } = res;", "pagination metadata preservation is missing"),
    ("delete(url, dataOrOptions, options)", "delete compatibility is missing"),
]:
    if token not in http:
        errors.append(f"src/api/http.js: {label}")

main = read("src/main.js")
for token in ["user: 'people'", "member: 'people'", "pin_general: 'pin'", "moments_pin: 'pin'", "video: 'zvideo'"]:
    if token not in main:
        errors.append(f"src/main.js: missing type alias {token}")

zhihu = read("src/api/utils/zhihu-module.js")
if "this.cookie[\"d_c0\"]" in zhihu:
    errors.append("src/api/utils/zhihu-module.js: d_c0 is written before cookie initialization")
if "Bearer \" + loginData.access_token" in zhihu:
    errors.append("src/api/utils/zhihu-module.js: undefined bearer token path remains")

following = read("src/components/home/FollowingView.vue")
for token, label in [
    ("following_questions", "invalid following questions endpoint remains"),
    ("type: 'user'", "user cards still use article-routing type"),
    ("state.hasMore = !res.paging?.is_end", "weak paging remains"),
]:
    if token in following:
        errors.append(f"src/components/home/FollowingView.vue: {label}")
if ':infinite-preloader="tabData[tab.id].loading && tabData[tab.id].hasMore"' not in following:
    errors.append("src/components/home/FollowingView.vue: loading-aware preloader is missing")

search = read("src/components/SearchPage.vue")
for token, label in [
    ("currentTabHasMore", "cross-tab hasMore state remains"),
    ("currentTab.hasMore = !!res.paging?.is_end", "reversed hasMore remains"),
    ('v-if="getTabResults(tab.id).hasMore"\n                                class="end-message', "reversed end message remains"),
    ("$http.get(suggestUrl);", "www search suggestion request lacks web mode"),
]:
    if token in search:
        errors.append(f"src/components/SearchPage.vue: {label}")

search_result = read("src/components/SearchResultView.vue")
if "itemType = 'pin';" in search_result:
    errors.append("src/components/SearchResultView.vue: undeclared itemType assignment remains")

topic = read("src/components/TopicDetail.vue")
if "metrics = null;" in topic and "let metrics = { likes, comments };" not in topic:
    errors.append("src/components/TopicDetail.vue: metrics is undeclared")
if "tabData[tabId].hasMore = !res.paging?.is_end" in topic or "dataState.hasMore = !res.paging?.is_end" in topic:
    errors.append("src/components/TopicDetail.vue: weak paging remains")

article = read("src/components/ArticleDetail.vue")
for token, label in [
    ("data.author.avatar?.avatar_image", "unsafe author avatar access remains"),
    ("data.reaction.statistics.up_vote_count", "unsafe reaction statistics access remains"),
    ("mappedItem.questionID = data.question.id", "unsafe question access remains"),
]:
    if token in article:
        errors.append(f"src/components/ArticleDetail.vue: {label}")

collection_sheet = read("src/components/CollectionSheet.vue")
if "await fetchCollections();" in collection_sheet:
    errors.append("src/components/CollectionSheet.vue: recursive pagination remains")
if "const seen = new Set();" not in collection_sheet:
    errors.append("src/components/CollectionSheet.vue: iterative pagination guard is missing")

profile = read("src/components/UserProfile.vue")
for token, label in [
    ("isFollowing: data.is_following ?? false", "follow state mapping is missing"),
    ("gender: data.gender ?? -1", "gender mapping is missing"),
    ("await Promise.all([fetchUserInfo(), fetchTabs()]);", "profile and tabs still race"),
    ("if (newId && userInfo.value) fetchContent(newId);", "active tab can fetch before profile"),
    ("const avatarUrl = userInfo.value?.avatarUrl || '';", "avatar null guard is missing"),
]:
    if token not in profile:
        errors.append(f"src/components/UserProfile.vue: {label}")
if re.search(r"\btype,\s*\n\s*id,\s*\n\s*type,", profile):
    errors.append("src/components/UserProfile.vue: duplicate type key remains")

people_more = read("src/components/PeopleMoreView.vue")
if "following_questions" in people_more:
    errors.append("src/components/PeopleMoreView.vue: invalid following questions endpoint remains")
if "following-questions" not in people_more:
    errors.append("src/components/PeopleMoreView.vue: following questions endpoint is missing")

notifications = read("src/components/NotificationsView.vue")
if "$http.get(url, { isWWW: true })" not in notifications:
    errors.append("src/components/NotificationsView.vue: www notification request lacks web mode")
if "readall', '', { isWWW: true }" not in notifications:
    errors.append("src/components/NotificationsView.vue: readall request lacks web mode")

for rel in [
    "src/components/home/CollectionsView.vue",
    "src/components/CollectionDetail.vue",
    "src/components/NotificationsView.vue",
    "src/components/PeopleListView.vue",
    "src/components/PeopleMoreView.vue",
    "src/components/ColumnItemsView.vue",
    "src/components/SearchResultView.vue",
]:
    text = read(rel)
    if "hasMore.value = !res.paging?.is_end" in text or "state.hasMore = !res.paging?.is_end" in text:
        errors.append(f"{rel}: weak paging remains")

question = read("src/components/QuestionDetail.vue")
if ':infinite-preloader="hasMore"' in question:
    errors.append("src/components/QuestionDetail.vue: preloader is detached from loading state")
if "hasMore.value = !res.paging?.is_end" in question:
    errors.append("src/components/QuestionDetail.vue: weak paging remains")

comments = read("src/components/CommentsSheet.vue")
if (
    "topHasMore.value = !res?.paging?.is_end" in comments
    or "hasMore.value = !res.paging?.is_end" in comments
    or "parentComment.hasMore = !result.paging?.is_end" in comments
):
    errors.append("src/components/CommentsSheet.vue: weak paging remains")

home = read("src/components/home/HomeView.vue")
if ':global(.home-mobile) .home-tab-shell' in home:
    errors.append("src/components/home/HomeView.vue: malformed scoped :global selector remains")
if ':global(.home-mobile .home-tab-shell)' not in home:
    errors.append("src/components/home/HomeView.vue: scoped mobile selector missing")
for token in [
    "initDynamicHomeScrollFeatures",
    "ensureViewportFilled",
    "scheduleRecommendViewportFill",
    "scheduleMomentsViewportFill",
    "scheduleThoughtsViewportFill",
    "ensureActiveTabViewport",
    "viewportFillRounds",
]:
    if token in home:
        errors.append(f"src/components/home/HomeView.vue: redundant local scroll helper remains: {token}")

# In Vue <style scoped>, :global(...) replaces the full selector. A descendant
# written after :global(...) can collapse the rule onto the global ancestor.
malformed_scoped_global = re.compile(r":global\([^\n)]+\)\s+[.#[:a-zA-Z]")
for vue_path in sorted((ROOT / "src").rglob("*.vue")):
    vue_text = vue_path.read_text(encoding="utf-8")
    if malformed_scoped_global.search(vue_text):
        errors.append(f"{vue_path.relative_to(ROOT)}: malformed scoped :global descendant selector remains")

sync = read("deploy/sync-upstream.sh")
for token, label in [
    ('python3 deploy/apply-fork-patches.py "$repo_root"', "patch reapplication is missing"),
    ('python3 deploy/verify-project-fixes.py "$repo_root"', "verification is missing"),
]:
    if token not in sync:
        errors.append(f"deploy/sync-upstream.sh: {label}")
if "fork_preserve_paths" in sync:
    errors.append("deploy/sync-upstream.sh: source preservation list still blocks upstream source updates")
if 'if [[ "$upstream_sha" == "$state_sha" ]]; then\n  python3 deploy/verify-project-fixes.py "$repo_root"' not in sync:
    errors.append("deploy/sync-upstream.sh: unchanged-upstream verification is missing")

patcher = read("deploy/apply-fork-patches.py")
main_match = re.search(r"def main\(\):(?P<body>.*?)\n\nif __name__", patcher, flags=re.S)
if main_match and "patch_workflow()" in main_match.group("body"):
    errors.append("deploy/apply-fork-patches.py: workflow patching still runs during upstream source patching")

workflow = read(".github/workflows/sync-ghcr.yml")
if "      - name: Verify fork source\n        shell: bash" not in workflow or "python3 deploy/verify-project-fixes.py ." not in workflow:
    errors.append(".github/workflows/sync-ghcr.yml: source verification is missing")
for token in ["src/components/FeedCard.vue", "src/components/home/HotListCard.vue", "src/style.css"]:
    if token in workflow:
        errors.append(f".github/workflows/sync-ghcr.yml: source path remains in infrastructure guard: {token}")

patterns = [
    r"color\s*:\s*#111\s*;",
    r"color\s*:\s*#1a1a1a\s*;",
    r"color\s*:\s*#222\s*;",
    r"color\s*:\s*#333\s*;",
    r"color\s*:\s*#444\s*;",
    r"color\s*:\s*#555\s*;",
    r"color\s*:\s*#666\s*;",
    r"color\s*:\s*#777\s*;",
    r"color\s*:\s*#888\s*;",
    r"color\s*:\s*#999\s*;",
    r"color\s*:\s*#aaa\s*;",
    r"color\s*:\s*#bbb\s*;",
    r"color\s*:\s*#8e8e93\s*;",
    r"background(?:-color)?\s*:\s*(?:#fff(?:fff)?|white|#fdfdfd|#fafafa|#f8f8f8|#f7f7f8|#f5f5f5|#f4f4f4|#f2f2f2|#f0f0f0|#eee(?:eee)?)\s*(?:!important)?\s*;",
    r"--f7-toolbar-background-color\s*:\s*#fff\s*;",
]
for path in sorted((ROOT / "src").rglob("*.vue")) + sorted((ROOT / "src").rglob("*.css")):
    if path == ROOT / "src" / "style.css":
        continue
    text = path.read_text(encoding="utf-8")
    for pattern in patterns:
        if re.search(pattern, text, flags=re.I):
            errors.append(f"{path.relative_to(ROOT)}: light-only neutral style remains: {pattern}")

if errors:
    print("\n".join(errors))
    raise SystemExit(1)

print("verification passed")
