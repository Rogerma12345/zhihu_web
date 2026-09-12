from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
TEMPLATES = ROOT / "deploy" / "fork-templates"


def target(rel):
    return ROOT / rel


def read(rel):
    path = target(rel)
    if not path.exists():
        raise RuntimeError(f"missing file: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel, value):
    path = target(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def template(name):
    path = TEMPLATES / name
    if not path.exists():
        raise RuntimeError(f"missing template: {name}")
    return path.read_text(encoding="utf-8")


def replace_once(text, old, new, label, required=True):
    count = text.count(old)
    if count == 0:
        if new in text:
            return text
        if required:
            raise RuntimeError(f"pattern not found: {label}")
        return text
    if count != 1:
        raise RuntimeError(f"pattern count {count}: {label}")
    return text.replace(old, new, 1)


def patch_app():
    rel = "src/App.vue"
    text = read(rel)
    import_line = "import { installPagedScroll } from './utils/paged-scroll.js';"
    if import_line not in text:
        text = replace_once(
            text,
            "import { checkTipVersion } from './utils/tip_manager.js';",
            "import { checkTipVersion } from './utils/tip_manager.js';\n" + import_line,
            rel + " import"
        )
    if "    installPagedScroll(f7);" not in text:
        text = replace_once(
            text,
            "  f7ready((f7) => {\n    loadThemeSettings(f7);",
            "  f7ready((f7) => {\n    installPagedScroll(f7);\n    loadThemeSettings(f7);",
            rel + " install"
        )
    write(rel, text)


def patch_main():
    rel = "src/main.js"
    text = read(rel)
    if "pin_general: 'pin'" not in text:
        pattern = r"const \$handleCardClick = \(f7router, item\) => \{\n\s*const \{ type, id \} = item;\n\s*switch \(type\) \{"
        replacement = """const $handleCardClick = (f7router, item) => {
    const { id } = item;
    const type = {
        user: 'people',
        member: 'people',
        pin_general: 'pin',
        moments_pin: 'pin',
        video: 'zvideo'
    }[item.type] || item.type;

    switch (type) {"""
        text, count = re.subn(pattern, replacement, text, count=1)
        if count != 1:
            raise RuntimeError(rel + " type aliases")
    write(rel, text)


def patch_zhihu_module():
    rel = "src/api/utils/zhihu-module.js"
    text = read(rel)
    old = """        this.accessToken = "Bearer " + loginData.access_token;
        if (loginData.udid) {
            this.cookie["d_c0"] = loginData.udid;
        }
        this.cookie = Object.entries(loginData.cookie || {})
            .filter(([_, v]) => v)
            .map(([k, v]) => `${k}=${v}`)
            .join('; ');"""
    new = """        this.accessToken = loginData.access_token ? `Bearer ${loginData.access_token}` : "";
        const cookieData = { ...(loginData.cookie || {}) };
        if (loginData.udid) {
            cookieData.d_c0 = loginData.udid;
        }
        this.cookie = Object.entries(cookieData)
            .filter(([_, v]) => v)
            .map(([k, v]) => `${k}=${v}`)
            .join('; ');"""
    if "const cookieData = { ...(loginData.cookie || {}) };" not in text:
        text = replace_once(text, old, new, rel + " login data")
    write(rel, text)


def add_null_guard(text, marker, state_expr, label):
    guard = f"        if (!res) {{\n            {state_expr} = false;\n            return;\n        }}\n"
    if guard.strip() not in text:
        text = replace_once(text, marker, guard + marker, label)
    return text


def patch_following():
    rel = "src/components/home/FollowingView.vue"
    text = read(rel)
    text = text.replace("/following_questions`", "/following-questions`")
    text = text.replace("isFollowing: item.isFollowing,", "isFollowing: item.is_following ?? item.isFollowing ?? true,")
    text = text.replace("type: 'user'", "type: 'people'")
    if "if (!userId.value) return;" not in text:
        text = replace_once(
            text,
            "const fetchTabData = async (tabId, isRefresh = false) => {\n    const state = tabData[tabId];",
            "const fetchTabData = async (tabId, isRefresh = false) => {\n    if (!userId.value) return;\n    const state = tabData[tabId];",
            rel + " user guard"
        )
    text = add_null_guard(text, "        const rawList = res.data || [];", "state.hasMore", rel + " null")
    text = text.replace("state.hasMore = !res.paging?.is_end;", "state.hasMore = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    text = text.replace(
        "onMounted(() => {\n    fetchTabData(activeTab.value, true);\n});",
        "onMounted(() => {\n    if (userId.value) fetchTabData(activeTab.value, true);\n});"
    )
    old = """<f7-page-content ptr @ptr:refresh="(done) => onRefresh(tab.id, done)" infinite
                    @infinite="onInfinite(tab.id)" class="tab-scroll-content">"""
    new = """<f7-page-content ptr @ptr:refresh="(done) => onRefresh(tab.id, done)" infinite
                    :infinite-preloader="tabData[tab.id].loading && tabData[tab.id].hasMore"
                    @infinite="onInfinite(tab.id)" class="tab-scroll-content">"""
    if ':infinite-preloader="tabData[tab.id].loading && tabData[tab.id].hasMore"' not in text:
        text = replace_once(text, old, new, rel + " preloader")
    write(rel, text)


def patch_search_page():
    rel = "src/components/SearchPage.vue"
    text = read(rel)
    text = text.replace(
        "import { ref, onMounted, nextTick, computed, onUnmounted } from 'vue';",
        "import { ref, onMounted, nextTick, onUnmounted } from 'vue';"
    )
    text = re.sub(r"\nconst currentTabHasMore = computed\(\(\) => \{.*?\n\}\);\n", "\n", text, count=1, flags=re.S)
    text = text.replace("if (!currentTabHasMore.value || isLoadingResults.value) {", "if (!currentTab.hasMore || isLoadingResults.value) {")
    text = add_null_guard(text, "        const apiData = res.data;", "currentTab.hasMore", rel + " null")
    text = text.replace("currentTab.hasMore = !!res.paging?.is_end;", "currentTab.hasMore = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    text = text.replace(
        'v-if="getTabResults(tab.id).hasMore"\n                                class="end-message',
        'v-if="!getTabResults(tab.id).hasMore"\n                                class="end-message'
    )
    text = text.replace("const res = await $http.get(suggestUrl);", "const res = await $http.get(suggestUrl, { isWWW: true });")
    old = """<f7-page-content :ref="el => tabRefs[tab.id] = el" ptr @ptr:refresh="(done) => handleTabRefresh(tab.id, done)" infinite
                        @infinite="handleTabLoadMore(tab.id)">"""
    new = """<f7-page-content :ref="el => tabRefs[tab.id] = el" ptr @ptr:refresh="(done) => handleTabRefresh(tab.id, done)" infinite
                        :infinite-preloader="isLoadingResults && getTabResults(tab.id).hasMore"
                        @infinite="handleTabLoadMore(tab.id)">"""
    if ':infinite-preloader="isLoadingResults && getTabResults(tab.id).hasMore"' not in text:
        text = replace_once(text, old, new, rel + " preloader")
    write(rel, text)


def patch_search_result():
    rel = "src/components/SearchResultView.vue"
    text = read(rel)
    text = text.replace("            itemType = 'pin';\n", "")
    text = add_null_guard(text, "        const rawList = res.data;", "hasMore.value", rel + " null")
    text = text.replace("hasMore.value = !res.paging?.is_end;", "hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    old = """<f7-page name="search-result" ptr @ptr:refresh="onRefresh" infinite @infinite="onInfinite"
        :ref="(el) => pageRef = el">"""
    new = """<f7-page name="search-result" ptr @ptr:refresh="onRefresh" infinite
        :infinite-preloader="isLoading && hasMore" @infinite="onInfinite"
        :ref="(el) => pageRef = el">"""
    if ':infinite-preloader="isLoading && hasMore"' not in text:
        text = replace_once(text, old, new, rel + " preloader")
    write(rel, text)


def patch_topic():
    rel = "src/components/TopicDetail.vue"
    text = read(rel)
    if "let metrics = { likes, comments };" not in text:
        text = replace_once(text, "    let footer = '';\n", "    let footer = '';\n    let metrics = { likes, comments };\n", rel + " metrics")
    text = text.replace("""        metrics: {
            likes,
            comments
        },""", "        metrics,")
    text = text.replace("const type = originalType === 'moments_pin' ? 'pin' : originalType;", "const type = { moments_pin: 'pin', pin_general: 'pin', video: 'zvideo' }[originalType] || originalType;")
    text = text.replace("dataState.hasMore = !res.paging?.is_end;", "dataState.hasMore = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    text = text.replace("tabData[tabId].hasMore = !res.paging?.is_end;", "tabData[tabId].hasMore = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    text = text.replace(':infinite-preloader="false"', ':infinite-preloader="tabData[tab.id].loading && tabData[tab.id].hasMore"')
    write(rel, text)


def patch_article_detail():
    rel = "src/components/ArticleDetail.vue"
    text = read(rel)
    text = text.replace('    case "pin_general":\n        type = "pin";\n        break;', '    case "pin_general":\n    case "moments_pin":\n        type = "pin";\n        break;')
    text = text.replace("avatarUrl: data.author.avatar?.avatar_image?.day || '',", "avatarUrl: data.author?.avatar?.avatar_image?.day || '',")
    text = text.replace("votes: data.reaction.statistics.up_vote_count || 0,", "votes: data.reaction?.statistics?.up_vote_count || 0,")
    text = text.replace("likes: data.reaction.statistics.like_count || 0,", "likes: data.reaction?.statistics?.like_count || 0,")
    text = text.replace("favlists: data.reaction.statistics.favorites || 0,", "favlists: data.reaction?.statistics?.favorites || 0,")
    text = text.replace("comments: data.reaction.statistics.comment_count || 0", "comments: data.reaction?.statistics?.comment_count || 0")
    text = text.replace("mappedItem.questionID = data.question.id;", "mappedItem.questionID = data.question?.id;")
    write(rel, text)


def patch_collection_sheet():
    rel = "src/components/CollectionSheet.vue"
    text = read(rel)
    pattern = r"const fetchCollections = async \(\) => \{\n.*?\n\};\n+const handleConfirm"
    replacement = """const fetchCollections = async () => {
    if (isLoading.value) return;
    isLoading.value = true;
    try {
        const url = `https://api.zhihu.com/collections/contents/${props.contentType}/${props.contentId}?limit=20`;
        let cursor = lastResult.value;
        const seen = new Set();
        while (true) {
            const res = cursor ? await cursor.next() : await $http.get(url);
            if (!res) break;
            const rawList = res.data || [];
            collections.value.push(...rawList.map(item => ({
                id: item.id,
                title: item.title,
                selected: !!item.is_favorited,
                originalSelected: !!item.is_favorited
            })));
            lastResult.value = res;
            if (res.paging?.is_end || !res.paging?.next || seen.has(res.paging.next)) break;
            seen.add(res.paging.next);
            cursor = res;
        }
    } catch (e) {
        console.error('Failed to fetch collections:', e);
    } finally {
        isLoading.value = false;
    }
};
const handleConfirm"""
    if "const seen = new Set();" not in text:
        updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
        if count != 1:
            raise RuntimeError(rel + " pagination")
        text = updated
    write(rel, text)


def patch_question():
    rel = "src/components/QuestionDetail.vue"
    text = read(rel)
    text = text.replace(':infinite-preloader="hasMore"', ':infinite-preloader="isLoadingMore && hasMore"')
    text = text.replace("hasMore.value = !res.paging?.is_end;", "hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    write(rel, text)


def patch_user_profile():
    rel = "src/components/UserProfile.vue"
    text = read(rel)
    if "isFollowing: data.is_following ?? false," not in text:
        text = replace_once(text, "            isBlocking: data.is_blocking,\n", "            isBlocking: data.is_blocking,\n            isFollowing: data.is_following ?? false,\n            gender: data.gender ?? -1,\n", rel + " following")
    elif "gender: data.gender ?? -1," not in text:
        text = replace_once(text, "            isFollowing: data.is_following ?? false,\n", "            isFollowing: data.is_following ?? false,\n            gender: data.gender ?? -1,\n", rel + " gender")
    text = text.replace("        const avatarUrl = userInfo.value.avatarUrl;", "        const avatarUrl = userInfo.value?.avatarUrl || '';")
    text = text.replace("const type = targetItem.type === 'moments_pin' ? 'pin' : targetItem.type;", "const type = { moments_pin: 'pin', pin_general: 'pin', video: 'zvideo' }[targetItem.type] || targetItem.type;")
    text = add_null_guard(text, "        let processedItems = [];", "dataState.hasMore", rel + " null")
    text = text.replace("dataState.hasMore = !res.paging?.is_end;", "dataState.hasMore = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    text = text.replace("""                    avatarUrl,
                    type,
                    id,
                    type,
                    metrics:""", """                    avatarUrl,
                    type,
                    id,
                    metrics:""")
    old_mount = """onMounted(() => {
    if (!hasHistory) {
        fetchUserInfo();
        fetchTabs().then(() => {
            if (activeTab.value) fetchContent(activeTab.value);
        });
    }

    nextTick(() => {
        if (headerRef.value) {
            headerHeight.value = headerRef.value.offsetHeight;
        }
    });
});"""
    new_mount = """onMounted(async () => {
    if (!hasHistory) {
        await Promise.all([fetchUserInfo(), fetchTabs()]);
        if (activeTab.value) await fetchContent(activeTab.value);
    }

    await nextTick();
    if (headerRef.value) {
        headerHeight.value = headerRef.value.offsetHeight;
    }
});"""
    if "await Promise.all([fetchUserInfo(), fetchTabs()]);" not in text:
        text = replace_once(text, old_mount, new_mount, rel + " mount")
    text = text.replace("watch(activeTab, (newId) => {\n    if (newId) fetchContent(newId);\n});", "watch(activeTab, (newId) => {\n    if (newId && userInfo.value) fetchContent(newId);\n});")
    old = """<f7-page-content ptr @ptr:refresh="(done) => onRefresh(tab.id, done)" infinite
                            :ref="(el) => setScrollRef(el, tab.id)" @infinite="() => onLoadMore(tab.id)"
                            class="tab-scroll-content">"""
    new = """<f7-page-content ptr @ptr:refresh="(done) => onRefresh(tab.id, done)" infinite
                            :infinite-preloader="tabData[tab.id]?.loading && tabData[tab.id]?.hasMore"
                            :ref="(el) => setScrollRef(el, tab.id)" @infinite="() => onLoadMore(tab.id)"
                            class="tab-scroll-content">"""
    if ':infinite-preloader="tabData[tab.id]?.loading && tabData[tab.id]?.hasMore"' not in text:
        text = replace_once(text, old, new, rel + " preloader")
    write(rel, text)


def patch_collections_view():
    rel = "src/components/home/CollectionsView.vue"
    text = read(rel)
    text = add_null_guard(text, "        const rawList = res.data || [];", "state.hasMore", rel + " null")
    text = text.replace("state.hasMore = !res.paging?.is_end;", "state.hasMore = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    old = """<f7-page-content ptr @ptr:refresh="(done) => onRefresh(tab.id, done)" infinite
                    @infinite="onInfinite(tab.id)" class="tab-scroll-content" :ref="(el) => setScrollRef(el, tab.id)">"""
    new = """<f7-page-content ptr @ptr:refresh="(done) => onRefresh(tab.id, done)" infinite
                    :infinite-preloader="tabData[tab.id].loading && tabData[tab.id].hasMore"
                    @infinite="onInfinite(tab.id)" class="tab-scroll-content" :ref="(el) => setScrollRef(el, tab.id)">"""
    if ':infinite-preloader="tabData[tab.id].loading && tabData[tab.id].hasMore"' not in text:
        text = replace_once(text, old, new, rel + " preloader")
    write(rel, text)


def patch_collection_detail():
    rel = "src/components/CollectionDetail.vue"
    text = read(rel)
    text = add_null_guard(text, "        const rawList = res.data || [];", "hasMore.value", rel + " null")
    text = text.replace("hasMore.value = !res.paging?.is_end;", "hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    old = """<f7-page name="collection-detail" ptr @ptr:refresh="onRefresh" infinite @infinite="onInfinite"
        :ref="(el) => pageRef = el">"""
    new = """<f7-page name="collection-detail" ptr @ptr:refresh="onRefresh" infinite
        :infinite-preloader="isLoading && hasMore" @infinite="onInfinite"
        :ref="(el) => pageRef = el">"""
    if ':infinite-preloader="isLoading && hasMore"' not in text:
        text = replace_once(text, old, new, rel + " preloader")
    write(rel, text)


def patch_notifications():
    rel = "src/components/NotificationsView.vue"
    text = read(rel)
    text = text.replace("res = await $http.get(url);", "res = await $http.get(url, { isWWW: true });")
    text = add_null_guard(text, "        const rawList = res.data || [];", "state.hasMore", rel + " null")
    text = text.replace("state.hasMore = !res.paging?.is_end;", "state.hasMore = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    text = text.replace("await $http.post('https://www.zhihu.com/api/v4/notifications/v2/default/actions/readall');", "await $http.post('https://www.zhihu.com/api/v4/notifications/v2/default/actions/readall', '', { isWWW: true });")
    old = """<f7-page-content ptr @ptr:refresh="(done) => onRefresh(tab.id, done)" infinite
                    @infinite="onInfinite(tab.id)">"""
    new = """<f7-page-content ptr @ptr:refresh="(done) => onRefresh(tab.id, done)" infinite
                    :infinite-preloader="tabData[tab.id].loading && tabData[tab.id].hasMore"
                    @infinite="onInfinite(tab.id)">"""
    if ':infinite-preloader="tabData[tab.id].loading && tabData[tab.id].hasMore"' not in text:
        text = replace_once(text, old, new, rel + " preloader")
    write(rel, text)


def patch_people_list():
    rel = "src/components/PeopleListView.vue"
    text = read(rel)
    text = add_null_guard(text, "        const rawList = res.data || [];", "hasMore.value", rel + " null")
    text = text.replace("hasMore.value = !res.paging?.is_end;", "hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    old = """<f7-page name="people-list" ptr @ptr:refresh="onRefresh" infinite @infinite="onInfinite"
        :ref="(el) => pageRef = el">"""
    new = """<f7-page name="people-list" ptr @ptr:refresh="onRefresh" infinite
        :infinite-preloader="isLoading && hasMore" @infinite="onInfinite"
        :ref="(el) => pageRef = el">"""
    if ':infinite-preloader="isLoading && hasMore"' not in text:
        text = replace_once(text, old, new, rel + " preloader")
    write(rel, text)


def patch_people_more():
    rel = "src/components/PeopleMoreView.vue"
    text = read(rel)
    old = """    if (gettype) {
        return `https://api.zhihu.com/people/${userId}/following_${gettype}`;
    }"""
    new = """    if (gettype === 'questions') {
        return `https://api.zhihu.com/people/${userId}/following-questions`;
    }
    if (gettype) {
        return `https://api.zhihu.com/people/${userId}/following_${gettype}`;
    }"""
    if "gettype === 'questions'" not in text:
        text = replace_once(text, old, new, rel + " questions url")
    text = add_null_guard(text, "        const rawList = res.data || [];", "hasMore.value", rel + " null")
    text = text.replace("hasMore.value = !res.paging?.is_end;", "hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    old = """<f7-page name="people-more" ptr @ptr:refresh="onRefresh" infinite @infinite="onInfinite"
        :ref="(el) => pageRef = el">"""
    new = """<f7-page name="people-more" ptr @ptr:refresh="onRefresh" infinite
        :infinite-preloader="isLoading && hasMore" @infinite="onInfinite"
        :ref="(el) => pageRef = el">"""
    if ':infinite-preloader="isLoading && hasMore"' not in text:
        text = replace_once(text, old, new, rel + " preloader")
    write(rel, text)


def patch_column_items():
    rel = "src/components/ColumnItemsView.vue"
    text = read(rel)
    text = add_null_guard(text, "        const rawList = res.data || [];", "hasMore.value", rel + " null")
    text = text.replace("hasMore.value = !res.paging?.is_end;", "hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    old = """<f7-page name="column-items" ptr @ptr:refresh="onRefresh" infinite @infinite="onInfinite"
        :ref="(el) => pageRef = el">"""
    new = """<f7-page name="column-items" ptr @ptr:refresh="onRefresh" infinite
        :infinite-preloader="isLoading && hasMore" @infinite="onInfinite"
        :ref="(el) => pageRef = el">"""
    if ':infinite-preloader="isLoading && hasMore"' not in text:
        text = replace_once(text, old, new, rel + " preloader")
    write(rel, text)


def patch_comments_sheet():
    rel = "src/components/CommentsSheet.vue"
    text = read(rel)
    text = text.replace("topHasMore.value = !res?.paging?.is_end;", "topHasMore.value = res?.paging?.is_end !== true && Boolean(res?.paging?.next);")
    text = text.replace("hasMore.value = !res.paging?.is_end;", "hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);")
    text = text.replace("parentComment.hasMore = !result.paging?.is_end;", "parentComment.hasMore = result.paging?.is_end !== true && Boolean(result.paging?.next);")
    write(rel, text)


def patch_home_cleanup():
    rel = "src/components/home/HomeView.vue"
    text = read(rel)
    helper_names = [
        "initDynamicHomeScrollFeatures",
        "resetViewportFill",
        "ensureViewportFilled",
        "scheduleRecommendViewportFill",
        "scheduleMomentsViewportFill",
        "scheduleThoughtsViewportFill",
        "ensureActiveTabViewport",
    ]
    for name in helper_names:
        text = re.sub(
            rf"\nconst {name} = .*?\n\}};\n",
            "\n",
            text,
            count=1,
            flags=re.S,
        )
    text = re.sub(r"^const viewportFillRounds = new Map\(\);\n", "", text, count=1, flags=re.M)
    text = re.sub(r"^const MAX_VIEWPORT_FILL_ROUNDS = \d+;\n", "", text, count=1, flags=re.M)
    text = re.sub(r"^\s*resetViewportFill\([^;\n]+\);\n", "", text, flags=re.M)
    text = re.sub(r"^\s*if \(completed\) schedule(?:Recommend|Moments|Thoughts)ViewportFill\([^;\n]*\);\n", "", text, flags=re.M)
    text = re.sub(r"^\s*schedule(?:Recommend|Moments|Thoughts)ViewportFill\([^;\n]*\);\n", "", text, flags=re.M)
    text = re.sub(r"^\s*let completed = false;\n", "", text, flags=re.M)
    text = re.sub(r"^\s*completed = true;\n", "", text, flags=re.M)
    text = re.sub(r"^\s*nextTick\(ensureActiveTabViewport\);\n", "", text, flags=re.M)
    text = re.sub(r"^\s*await initDynamicHomeScrollFeatures\(\);\n", "", text, flags=re.M)
    text = re.sub(r"^\s*ensureActiveTabViewport\(\);\n", "", text, flags=re.M)
    text = re.sub(r"\n\s*// 登录后“关注”页[^\n]*", "", text)
    text = re.sub(r"\n\s*// 如果登录发生[^\n]*", "", text)
    text = re.sub(r"(if \(state\.list\.length === 0\) \{\n\s*if \(!state\.loading\) fetchMomentsData\(tabId, true\);\n\s*\}) else \{\n\s*\}", r"\1", text, count=1)
    write(rel, text)


def patch_css_text(text):
    fixed = {
        "--f7-toolbar-background-color: #fff;": "--f7-toolbar-bg-color: var(--f7-bars-bg-color);",
        "color: #111;": "color: var(--f7-text-color);",
        "color: #1a1a1a;": "color: var(--f7-text-color);",
        "color: #222;": "color: var(--f7-text-color);",
        "color: #000;": "color: var(--f7-text-color);",
        "color: #000000;": "color: var(--f7-text-color);",
        "color: #333;": "color: var(--f7-text-color);",
        "color: #444;": "color: var(--app-text-secondary);",
        "color: #555;": "color: var(--app-text-secondary);",
        "color: #666;": "color: var(--app-text-secondary);",
        "color: #777;": "color: var(--app-text-secondary);",
        "color: #888;": "color: var(--app-text-muted);",
        "color: #999;": "color: var(--app-text-muted);",
        "color: #aaa;": "color: var(--app-text-muted);",
        "color: #bbb;": "color: var(--app-text-muted);",
        "color: #ccc;": "color: var(--app-text-muted);",
        "color: #8e8e93;": "color: var(--app-text-muted);",
        "border: 4px solid #fff;": "border: 4px solid var(--f7-page-bg-color);",
        "style=\"border: 1px solid #ccc;": "style=\"border: 1px solid var(--app-border-color);",
    }
    for old, new in fixed.items():
        text = text.replace(old, new)
    text = re.sub(r"(background(?:-color)?\s*:\s*)(?:#fff(?:fff)?|white|#fdfdfd)(\s*!important)?\s*;", r"\1var(--app-surface-bg)\2;", text, flags=re.I)
    text = re.sub(r"(background(?:-color)?\s*:\s*)(?:#fafafa|#f8f8f8|#f7f7f8|#f5f5f5|#f4f4f4|#f2f2f2)(\s*!important)?\s*;", r"\1var(--app-soft-bg)\2;", text, flags=re.I)
    text = re.sub(r"(background(?:-color)?\s*:\s*)(?:#f0f0f0|#eeeeee|#eee)(\s*!important)?\s*;", r"\1var(--app-placeholder-bg)\2;", text, flags=re.I)
    text = re.sub(r"(border(?:-top|-right|-bottom|-left)?(?:-color)?\s*:\s*)(?:1px\s+solid\s+)?(?:#eeeeee|#eee|#dddddd|#ddd|#cccccc|#ccc|#e5e5ea|#e0e0e0)(\s*!important)?\s*;", lambda m: f"{m.group(1)}{'1px solid ' if 'solid' in m.group(0) else ''}var(--app-border-color){m.group(2) or ''};", text, flags=re.I)
    text = re.sub(r"(border(?:-top|-right|-bottom|-left)?(?:-color)?\s*:\s*[^;\n]*?)rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.(?:05|08|1|10|12)\s*\)", r"\1var(--app-border-color)", text)
    text = re.sub(r"(color\s*:\s*)rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.(?:54|6|60|65|68|7|70|72)\s*\)", r"\1var(--app-text-secondary)", text)
    text = re.sub(r"(color\s*:\s*)rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.(?:38|4|40|45|5|50|52)\s*\)", r"\1var(--app-text-muted)", text)
    text = re.sub(r"(?<![\w-])bg-color-white(?![\w-])", "app-surface-bg", text)
    return text


def patch_colors():
    for pattern in ("*.vue", "*.css"):
        for path in sorted((ROOT / "src").rglob(pattern)):
            if path == ROOT / "src" / "style.css":
                continue
            text = path.read_text(encoding="utf-8")
            updated = patch_css_text(text)
            if updated != text:
                path.write_text(updated, encoding="utf-8")


def patch_workflow():
    rel = ".github/workflows/sync-ghcr.yml"
    text = read(rel)
    verify_step = """      - name: Verify fork source
        shell: bash
        run: |
          set -euo pipefail
          python3 deploy/verify-project-fixes.py .

"""
    if "      - name: Verify fork source\n" not in text:
        text = text.replace("      - name: Check synchronized workspace\n", verify_step + "      - name: Check synchronized workspace\n", 1)
    check_step = """      - name: Check synchronized workspace
        if: steps.prepare.outputs.upstream_changed == 'true'
        shell: bash
        run: |
          set -euo pipefail

          test -f src/index.html
          test -f package.json
          test -f package-lock.json
          test -f vite.config.js
          test -f workbox-config.js
          test -f deploy/nginx.conf
          python3 deploy/verify-project-fixes.py .
          if ! git diff --quiet -- \\
            Dockerfile \\
            .dockerignore \\
            deploy \\
            SELFHOST.md \\
            .github/workflows \\
            .upstream-state
          then
            echo "Fork-managed files changed before publication" >&2
            git diff -- \\
              Dockerfile \\
              .dockerignore \\
              deploy \\
              SELFHOST.md \\
              .github/workflows \\
              .upstream-state >&2
            exit 1
          fi

"""
    text = re.sub(r"      - name: Check synchronized workspace\n.*?(?=      - name: Decide whether to build)", lambda _m: check_step, text, count=1, flags=re.S)
    record_step = """      - name: Record successful upstream publication
        if: success() && steps.prepare.outputs.upstream_changed == 'true'
        shell: bash
        run: |
          set -euo pipefail

          upstream_sha="${{ steps.prepare.outputs.upstream_sha }}"
          now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

          printf 'upstream_sha=%s\\nlast_activity=%s\\n' \\
            "$upstream_sha" \\
            "$now_iso" > .upstream-state
          if ! git diff --quiet -- \\
            Dockerfile \\
            .dockerignore \\
            deploy \\
            SELFHOST.md \\
            .github/workflows
          then
            echo "Refusing to commit automatic fork-managed changes" >&2
            git diff -- \\
              Dockerfile \\
              .dockerignore \\
              deploy \\
              SELFHOST.md \\
              .github/workflows >&2
            exit 1
          fi

          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A
          git commit -m "chore: sync upstream ${upstream_sha:0:12}"
          git push origin HEAD:main
"""
    text = re.sub(r"      - name: Record successful upstream publication\n.*\Z", lambda _m: record_step, text, count=1, flags=re.S)
    write(rel, text)


def main():
    write("src/style.css", template("style.css"))
    write("src/utils/paged-scroll.js", template("paged-scroll.js"))
    write("src/api/http.js", template("http.js"))
    write("deploy/sync-upstream.sh", template("sync-upstream.sh"))
    patch_app()
    patch_main()
    patch_zhihu_module()
    patch_following()
    patch_search_page()
    patch_search_result()
    patch_topic()
    patch_article_detail()
    patch_collection_sheet()
    patch_question()
    patch_user_profile()
    patch_collections_view()
    patch_collection_detail()
    patch_notifications()
    patch_people_list()
    patch_people_more()
    patch_column_items()
    patch_comments_sheet()
    patch_home_cleanup()
    patch_colors()


if __name__ == "__main__":
    main()
