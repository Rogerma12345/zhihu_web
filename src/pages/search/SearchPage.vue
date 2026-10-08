<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue';

import TabLayout from '@/components/TabLayout.vue';
import FeedCard from '@/components/FeedCard.vue';
import $http from '@/services/http.js';
import { parseZhihuUrl } from '@/utils/url.js';
import { handleZhihuUrl, openLink } from '@/core/navigation.js';
import { settings } from '@/core/settings.js';
import { usePageState } from '@/composables/usePageState.js';
import { useTabbedPagedList } from '@/composables/useTabbedPagedList.js';
import { KEYS, getJSON, setJSON, removeKeys } from '@/services/storage.js';

const props = defineProps({
    f7router: Object
});

const query = ref('');
const activeTab = ref('general');
const isSearching = ref(false);
const searchbarRef = ref(null);

const searchHistory = ref([]);
const hotSearches = ref([]);
const isLoadingHotSearches = ref(false);
const hotSearchError = ref('');
const searchErrors = ref({});
const searchSuggestions = ref([]);
const showSuggestions = ref(false);

// 搜索标签定义
const SEARCH_TABS = [
    { id: 'general', label: '综合' },
    { id: 'realtime', label: '实时' },
    { id: 'people', label: '用户' },
    { id: 'column', label: '专栏' },
    { id: 'publication', label: '盐选内容' },
    { id: 'zvideo', label: '视频' },
    { id: 'pin', label: '想法' },
    { id: 'topic', label: '话题' }
];

const tabRefs = ref({});

// 搜索回归到重构前的 Android 接口及请求签名方式（登录与游客一致）。
const SEARCH_REQUEST_OPTIONS = {
    legacySearchRequest: true,
    suppressApiErrorToast: true,
    suppressApiErrorRedirect: true,
};
const searchRequestFor = (tabId) => {
    const isRealTime = tabId === 'realtime';
    const type = isRealTime ? 'general' : tabId;
    // 保留旧版参数顺序和 encodeURIComponent 编码方式，避免改变签名输入。
    const url = `https://api.zhihu.com/search_v3?gk_version=gz-gaokao&q=${encodeURIComponent(query.value)}&t=${type}&search_source=History&is_real_time=${isRealTime ? '1' : '0'}&correction=1&advert_count=&show_all_topics=0&pin_flow=false&restricted_scene=&restricted_field=&restricted_value=&limit=20&lc_idx=0`;
    return { url, options: SEARCH_REQUEST_OPTIONS };
};

const describeSearchError = (error) => {
    const apiCode = Number(error?.apiCode);
    if (apiCode === 40353) return '知乎要求登录后才能继续搜索（40353），可尝试 Google 站外搜索';
    if (apiCode === 40362) return '知乎暂时限制了本次搜索请求（40362），可稍后重试或使用 Google';
    if (error?.status === 403) return '知乎拒绝了本次搜索请求（HTTP 403）';
    if (error?.status === 401) return '游客凭证失效或未获授权（HTTP 401），请稍后重试';
    return error?.message || '搜索失败，请检查网络后重试';
};

// 搜索原始项 → 卡片视图模型；无作者信息或非目标类型返回 null 交给引擎过滤
const mapSearchItem = (item) => {
    const { object, type: itemType } = item;

    if (itemType === 'knowledge_ad') {
        const { url = '', body = {}, footer = null } = object;
        const title = body.title || '';
        const excerpt = body.description || '';
        return {
            id: url,
            type: 'browser',
            title,
            content: excerpt,
            excerpt,
            authorName: '',
            noAuthorPrefix: true,
            avatarUrl: '',
            footer,
            metrics: { likes: 0, comments: 0 },
            url
        };
    }

    if (!object?.author && !object?.avatar_url) return null;

    const {
        id: objectId,
        type: objectType,
        title = '',
        excerpt = '',
        url = '',
        voteup_count: likes = 0,
        comment_count: comments = 0,
        author,
        zvideo_id: zvideoId
    } = object;

    const authorName = author?.name || '';
    const avatarUrl = author?.avatar_url || object.avatar_url || '';
    const highlightTitle = item.highlight?.title || '';
    const highlightDesc = item.highlight?.description || '';

    return {
        id: objectType === 'zvideo' && zvideoId ? zvideoId : objectId,
        type: objectType,
        title: highlightTitle || title,
        content: highlightDesc || excerpt,
        excerpt: highlightDesc || excerpt,
        authorName,
        noAuthorPrefix: authorName === '',
        avatarUrl,
        footer: null,
        metrics: { likes, comments },
        url
    };
};

// 分页走统一引擎（useTabbedPagedList），替代旧的手写 executeSearch 复刻
const {
    tabs: tabResults,
    loading: resultsLoading,
    refresh: refreshTab,
    loadMore: loadMoreTab,
    reset: resetTab,
} = useTabbedPagedList({
    name: '搜索',
    tabs: () => SEARCH_TABS.map((t) => t.id),
    fillEl: (tabId) => tabRefs.value[tabId]?.$el,
    fetch: (tabId, signal) => {
        delete searchErrors.value[tabId];
        const { url, options } = searchRequestFor(tabId);
        return $http.get(url, { ...options, signal });
    },
    map: mapSearchItem,
    onError: (error, tabId) => {
        console.error(`搜索失败 (${tabId}):`, error);
        searchErrors.value[tabId] = describeSearchError(error);
    },
});

const { hasCache } = usePageState({
    state: {
        query,
        activeTab,
        isSearching,
        tabResults
    },
    scroll: (main) => {
        const map = { main };
        // 每个 tab 各自持有 f7-page-content，它就是可滚动元素本身
        Object.entries(tabRefs.value).forEach(([id, el]) => {
            if (el) map[id] = el.$el;
        });
        return map;
    }
});

// 恢复旧版搜索建议：网页地址沿用 Android 请求链路，而非网页签名模式。
const SUGGESTION_DELAY_MS = 300;
let suggestionTimer = null;
let suggestionEpoch = 0;
let searchInputEl = null;
let submitting = false;

const hideSuggestions = () => {
    suggestionEpoch += 1;
    clearTimeout(suggestionTimer);
    searchSuggestions.value = [];
    showSuggestions.value = false;
};

const debouncedSuggestions = (value) => {
    const term = String(value || '').trim();
    hideSuggestions();
    if (!term) return;
    const epoch = suggestionEpoch;
    suggestionTimer = setTimeout(async () => {
        try {
            const url = `https://www.zhihu.com/api/v4/search/suggest?q=${encodeURIComponent(term)}`;
            const data = await $http.get(url, SEARCH_REQUEST_OPTIONS);
            if (epoch !== suggestionEpoch || query.value.trim() !== term) return;
            searchSuggestions.value = Array.isArray(data?.suggest)
                ? data.suggest.map((item) => ({ query: item?.query || (typeof item === 'string' ? item : '') })).filter((item) => item.query)
                : [];
            showSuggestions.value = searchSuggestions.value.length > 0;
        } catch (error) {
            if (epoch !== suggestionEpoch) return;
            console.warn('搜索建议不可用:', describeSearchError(error));
            searchSuggestions.value = [];
            showSuggestions.value = false;
        }
    }, SUGGESTION_DELAY_MS);
};

// 回车只提交输入框原文；点选建议仅由建议项点击提交，二者互不重复触发。
const handleSearchEnter = (event) => {
    if (event.key !== 'Enter' || event.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    void handleSearch(query.value);
};

onMounted(() => {
    searchInputEl = searchbarRef.value?.$el?.querySelector('input');
    searchInputEl?.addEventListener('keydown', handleSearchEnter, true);
    if (!hasCache.value) {
        nextTick(() => searchInputEl?.focus());
        fetchHotSearches();
        loadSearchHistory();
    }
});
onUnmounted(() => {
    hideSuggestions();
    searchInputEl?.removeEventListener('keydown', handleSearchEnter, true);
});

// 加载搜索历史
const loadSearchHistory = () => {
    searchHistory.value = getJSON(KEYS.searchHistory, []);
};

// 保存搜索历史：新查询置顶，去重并限制条数
const saveSearchHistory = (text) => {
    if (!text.trim()) return;
    const index = searchHistory.value.indexOf(text);
    if (index > -1) {
        searchHistory.value.splice(index, 1);
    }
    searchHistory.value.unshift(text);
    if (searchHistory.value.length > 10) {
        searchHistory.value = searchHistory.value.slice(0, 10);
    }
    setJSON(KEYS.searchHistory, searchHistory.value);
};

// 热搜恢复重构前的 Android 接口与数据结构。
const fetchHotSearches = async () => {
    if (isLoadingHotSearches.value) return;
    isLoadingHotSearches.value = true;
    hotSearchError.value = '';
    try {
        const data = await $http.get('https://api.zhihu.com/search/hot_search', SEARCH_REQUEST_OPTIONS);
        const entries = Array.isArray(data?.hot_search_queries) ? data.hot_search_queries : [];
        hotSearches.value = entries.map((item, index) => ({
            rank: index + 1,
            title: item.query || item.real_query || '未知话题',
            hot: item.hot_show || (Number.isFinite(Number(item.hot)) ? `${Math.floor(Number(item.hot) / 10000)}万` : ''),
        }));
    } catch (error) {
        console.error('获取热搜数据失败:', error);
        hotSearches.value = [];
        hotSearchError.value = describeSearchError(error);
    } finally {
        isLoadingHotSearches.value = false;
    }
};
// 处理搜索
const handleSearch = async (text = query.value) => {
    const term = String(text || '').trim();
    if (!term || submitting) return;
    submitting = true;
    hideSuggestions();
    try {
        // 知乎 URL 继续按站内路由处理，普通外链仍在新标签页打开。
        const urlResult = await parseZhihuUrl(term);
        if (urlResult.type !== 'error' && urlResult.type !== 'browser') {
            query.value = '';
            await handleZhihuUrl(props.f7router, term);
            return;
        }
        if (urlResult.type === 'browser' && urlResult.id) {
            openLink(urlResult.id);
            return;
        }

        query.value = term;
        isSearching.value = true;
        saveSearchHistory(term);
        SEARCH_TABS.forEach((tab) => {
            delete searchErrors.value[tab.id];
            resetTab(tab.id);
        });
        await refreshTab(activeTab.value);
    } finally {
        submitting = false;
    }
};

// 站内搜索兜底：用配置的搜索引擎模板跳到站外
const handleExternalSearch = () => {
    if (!query.value.trim()) return;
    openLink(`${settings.searchEngineUrl}${encodeURIComponent(query.value)}`);
};

const searchEngineName = computed(() => {
    try {
        return new URL(settings.searchEngineUrl).hostname.replace(/^www\./, '');
    } catch {
        return '搜索引擎';
    }
});

// 处理清除历史
const handleClearHistory = () => {
    searchHistory.value = [];
    removeKeys(KEYS.searchHistory);
};

// 处理单个历史记录删除
const deleteHistoryItem = (index) => {
    searchHistory.value.splice(index, 1);
    setJSON(KEYS.searchHistory, searchHistory.value);
};

// 处理返回
const handleBack = () => {
    if (props.f7router) props.f7router.back();
};

// 处理标签页切换
const handleTabChange = (tabId) => {
    if (activeTab.value === tabId) return;
    activeTab.value = tabId;
    // 切到的标签页还没结果则懒加载取首页
    if (isSearching.value && !(tabResults[tabId]?.list.length > 0)) {
        refreshTab(tabId);
    }
};

// 处理输入框清除
const handleInputClear = () => {
    hideSuggestions();
    query.value = '';
    isSearching.value = false;
    searchbarRef.value?.$el?.querySelector('input')?.focus();
};

const handleTabRefresh = async (tabId, done) => {
    await refreshTab(tabId);
    done();
};

const handleTabLoadMore = (tabId) => {
    loadMoreTab(tabId);
};
</script>

<template>
    <f7-page class="search-page">
        <f7-navbar>
            <f7-nav-left>
                <f7-link icon-only @click="handleBack">
                    <f7-icon ios="f7:arrow_left" md="material:arrow_back" />
                </f7-link>
            </f7-nav-left>
            <f7-searchbar ref="searchbarRef" custom-search v-model:value="query"
                @searchbar:search="debouncedSuggestions($event.value)"
                @searchbar:clear="handleInputClear" placeholder="搜索..." :disable-button="false"
                clear-button></f7-searchbar>
            <f7-nav-right>
                <f7-link @click="() => handleSearch()">搜索</f7-link>
            </f7-nav-right>
        </f7-navbar>

        <!-- 旧版建议列表：仅点击建议项才使用该建议提交搜索。 -->
        <div v-if="showSuggestions && searchSuggestions.length" class="search-suggestions-container">
            <f7-list>
                <f7-list-item v-for="(item, index) in searchSuggestions" :key="`${item.query}-${index}`" link
                    :title="item.query" @click="handleSearch(item.query)" />
            </f7-list>
        </div>
        <!-- 搜索结果视图 -->
        <div v-if="isSearching && !showSuggestions" class="results-container">
            <TabLayout :tabs="SEARCH_TABS" :onChange="handleTabChange" :scrollable="true" :fixed="false"
                :auto-page-content="false">
                <!-- 每个标签页的内容 -->
                <template v-for="tab in SEARCH_TABS" :key="tab.id" #[tab.id]>
                    <f7-page-content :ref="el => tabRefs[tab.id] = el" ptr @ptr:refresh="(done) => handleTabRefresh(tab.id, done)" infinite
                        @infinite="handleTabLoadMore(tab.id)">
                        <!-- 有结果：显示列表 -->
                        <div v-if="tabResults[tab.id]?.list.length > 0" class="results-list">
                            <FeedCard v-for="(item, idx) in tabResults[tab.id].list" :key="item.id || idx"
                                :item="item" @click="$handleCardClick(f7router, item)"
                                class="result-card margin-bottom" />

                            <div v-if="searchErrors[tab.id]" class="text-color-gray text-align-center padding">
                                {{ searchErrors[tab.id] }}
                                <f7-button outline round small @click="loadMoreTab(tab.id)">重试加载</f7-button>
                            </div>
                            <div v-if="!tabResults[tab.id]?.hasMore"
                                class="end-message text-color-gray text-align-center padding">
                                已加载全部搜索结果
                            </div>
                        </div>

                        <!-- 失败不是无结果：单独展示服务端状态与 Google 入口。 -->
                        <div v-else-if="searchErrors[tab.id] && !resultsLoading[tab.id]"
                            class="empty-state display-flex flex-direction-column align-items-center justify-content-center padding-vertical">
                            <f7-icon ios="f7:exclamationmark_circle" md="material:error_outline" size="32" />
                            <span class="empty-text margin-top">{{ searchErrors[tab.id] }}</span>
                            <f7-button class="margin-top" outline round small @click="refreshTab(tab.id)">
                                重试站内搜索
                            </f7-button>
                            <f7-button class="margin-top" outline round small @click="handleExternalSearch">
                                用 {{ searchEngineName }} 站外搜索
                            </f7-button>
                        </div>
                        <!-- 无结果且加载完成：显示空状态 -->
                        <div v-else-if="!resultsLoading[tab.id]"
                            class="empty-state display-flex flex-direction-column align-items-center justify-content-center padding-vertical">
                            <f7-icon ios="f7:multiply_circle" md="material:search_off" size="32" />
                            <span class="empty-text margin-top">未找到与"{{ query }}"相关的内容</span>
                            <span class="empty-hint text-color-gray margin-top-half">尝试其他关键词，或检查拼写</span>
                            <f7-button class="margin-top" outline round small @click="handleExternalSearch">
                                用 {{ searchEngineName }} 站外搜索
                            </f7-button>
                        </div>
                    </f7-page-content>
                </template>
            </TabLayout>
        </div>

        <!-- 默认视图：历史和热搜 -->
        <div v-else-if="!isSearching" class="default-container padding">
            <!-- 搜索历史 -->
            <div v-if="searchHistory.length > 0" class="section margin-bottom">
                <div class="section-header display-flex justify-content-space-between align-items-center margin-bottom">
                    <span class="section-title font-weight-bold">搜索历史</span>
                    <f7-link icon-only @click="handleClearHistory" color="gray">
                        <f7-icon ios="f7:trash" md="material:delete" size="18" />
                    </f7-link>
                </div>
                <div class="history-chips display-flex flex-wrap" style="gap: 8px;">
                    <f7-chip v-for="(text, i) in searchHistory" :key="text" :text="text" @click="(e) => { if (!e.target.closest('.chip-delete')) handleSearch(text); }"
                        class="history-chip" outline deleteable @delete="deleteHistoryItem(i)" />
                </div>
            </div>

            <!-- 热搜列表 -->
            <div class="section" v-if="!settings.closeHotSearch">
                <div v-if="hotSearchError" class="text-color-gray margin-bottom">{{ hotSearchError }}</div>
                <div class="section-header display-flex justify-content-space-between align-items-center margin-bottom">
                    <span class="section-title font-weight-bold">全站热搜</span>
                    <f7-link icon-only @click="fetchHotSearches" :class="{ 'spinning': isLoadingHotSearches }">
                        <f7-icon ios="f7:arrow_clockwise" md="material:refresh" size="18" />
                    </f7-link>
                </div>
                <div class="list no-hairlines-md">
                    <f7-list>
                        <f7-list-item v-for="(item, index) in hotSearches" :key="index" link
                            @click="handleSearch(item.title)">
                            <div slot="media" class="trending-rank" :class="{ 'text-color-red': index < 3 }">{{
                                item.rank }}
                            </div>
                            <div slot="title">{{ item.title }}</div>
                            <div slot="after" class="text-color-gray text-size-12">{{ item.hot }}</div>
                        </f7-list-item>
                    </f7-list>
                </div>
            </div>
        </div>
    </f7-page>
</template>

<style scoped>

.results-container,
.default-container {
    flex: 1;
    height: calc(100% - 64px);
}


.results-list {
    padding-bottom: 80px;
}

.results-list>* {
    margin-bottom: 16px;
}

.empty-hint {
    margin-top: 8px;
    font-size: 14px;
    color: var(--app-sub-text);
}

.end-message {
    text-align: center;
    font-size: 14px;
    color: var(--app-sub-text);
    padding: 16px 0;
}

.section {
    padding: 16px;
    margin-bottom: 24px;
}

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.section-title {
    font-weight: bold;
    font-size: 16px;
    color: var(--f7-text-color);
    margin-bottom: 16px;
    display: block;
}

.history-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.trending-rank {
    width: 24px;
    text-align: center;
    font-weight: bold;
    font-size: 14px;
    color: var(--app-sub-text);
}
</style>