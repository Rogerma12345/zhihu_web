<script setup>
import { ref, onMounted, watch, nextTick, reactive, onUnmounted } from 'vue';
import { f7 } from 'framework7-vue';
import TopBar from '../TopBar.vue';
import FeedCard from '../FeedCard.vue';
import HotListCard from './HotListCard.vue';
import TabLayout from '../TabLayout.vue';
import $http from '../../api/http.js';
import MomentListCard from './MomentListCard.vue';
import RecommendUserCardList from './RecommendUserCardList.vue';
import { useUser } from '../../composables/userManager.js';

const props = defineProps({
    f7router: Object
});

const isMobile = ref(false);
const activeTab = ref('recommend');

const allTabDefinitions = {
    recommend: { id: 'recommend', label: '推荐', icon: 'home', iosIcon: 'f7:house_fill', mdIcon: 'material:home' },
    following: { id: 'following', label: '关注', icon: 'group', iosIcon: 'f7:person_2_fill', mdIcon: 'material:group' },
    hot: { id: 'hot', label: '热榜', icon: 'local_fire_department', iosIcon: 'f7:flame_fill', mdIcon: 'material:local_fire_department' },
    thoughts: { id: 'thoughts', label: '想法', icon: 'emoji_objects', iosIcon: 'f7:lightbulb_fill', mdIcon: 'material:bubble_chart' }
};

const enabledTabs = ref([]);

const loadSettings = () => {
    try {
        const stored = localStorage.getItem('home_tabs_config');
        if (stored) {
            const config = JSON.parse(stored);
            if (config.tabs && Array.isArray(config.tabs)) {
                enabledTabs.value = config.tabs
                    .filter(t => t.enabled && allTabDefinitions[t.id])
                    .map(t => allTabDefinitions[t.id]);
            }

            if (config.default && enabledTabs.value.some(t => t.id === config.default)) {
                activeTab.value = config.default;
            } else if (enabledTabs.value.length > 0) {
                activeTab.value = enabledTabs.value[0].id;
            }
        } else {
            enabledTabs.value = [
                allTabDefinitions.recommend,
                allTabDefinitions.following,
                allTabDefinitions.hot,
                allTabDefinitions.thoughts,
            ];
            activeTab.value = enabledTabs.value[0].id;
        }
    } catch (e) {
        console.error('Failed to load home settings', e);
    }

    if (enabledTabs.value.length === 0) {
        enabledTabs.value = [allTabDefinitions.recommend];
        activeTab.value = 'recommend';
    }
};

loadSettings();


const hasNextPage = (result) => {
    return Boolean(
        result?.paging &&
        result.paging.is_end !== true &&
        result.paging.next
    );
};





// 推荐模块
const lastRecommendResult = ref(null);
const recommendList = ref([]);
const hasMoreRecommend = ref(true);
const isRecommendLoading = ref(false);
const selectedSections = ref([]);
const hometab = ref([]);
const currentSectionIndex = ref(0);
let recommendRequestId = 0;

const getRecommendUrl = () => {
    const currentItem = hometab.value[currentSectionIndex.value];
    if (!currentItem) return null;

    const { section_id, sub_page_id } = currentItem;
    if (section_id === null) {
        return 'https://api.zhihu.com/topstory/recommend';
    }
    if (sub_page_id) {
        return `https://api.zhihu.com/feed-root/section/${section_id}?sub_page_id=${sub_page_id}&channelStyle=0`;
    }
    return `https://api.zhihu.com/feed-root/section/${section_id}?channelStyle=0`;
};

const mapRecommendItem = (item) => {
    if (!item || item.type !== 'feed') return null;

    const targetItem = item.target || item;
    if (!targetItem) return null;

    const type = targetItem.type;
    const id = targetItem.id;
    const authorName = targetItem.author?.name || '';
    let excerpt = targetItem.excerpt || targetItem.excerpt_title || '';
    let title = targetItem.title || item.title || '无标题';

    switch (type) {
        case 'answer':
            title = targetItem.question?.title || title;
            break;
        case 'pin':
            title = `${authorName}发表了想法`;
            break;
        default:
            break;
    }

    if (!excerpt || excerpt.trim() === '' || excerpt === '无预览内容') {
        excerpt = null;
    }

    return {
        type,
        id,
        title,
        excerpt,
        authorName,
        metrics: {
            likes: targetItem.voteup_count || targetItem.vote_count || targetItem.reaction_count || 0,
            comments: targetItem.comment_count || 0
        },
    };
};


const fetchRecommendData = async (isRefresh = false) => {
    if (!isRefresh && (isRecommendLoading.value || !hasMoreRecommend.value)) return;

    const url = getRecommendUrl();
    if (!url) return;

    const requestId = isRefresh ? ++recommendRequestId : recommendRequestId;

    if (isRefresh) {
        lastRecommendResult.value = null;
        hasMoreRecommend.value = true;
    }

    isRecommendLoading.value = true;

    try {
        let res;

        if (isRefresh || !lastRecommendResult.value) {
            res = await $http.get(url, { isWWW: true });
        } else {
            res = await lastRecommendResult.value.next();
        }

        if (requestId !== recommendRequestId) return;

        if (!res) {
            hasMoreRecommend.value = false;
                return;
        }

        const responseData = res.data;
        const rawList = Array.isArray(responseData) ? responseData : [];
        const mappedList = rawList.map(mapRecommendItem).filter(Boolean);

        if (isRefresh) {
            recommendList.value = mappedList;
        } else {
            recommendList.value.push(...mappedList);
        }

        lastRecommendResult.value = res;
        hasMoreRecommend.value = hasNextPage(res);
    } catch (e) {
        if (requestId === recommendRequestId) {
            console.error('Failed to fetch recommend data', e);
        }
    } finally {
        if (requestId === recommendRequestId) {
            isRecommendLoading.value = false;
        }
    }
};

const refreshHighlight = () => {
    nextTick(() => {
        f7.toolbar.setHighlight('.recommend-section-tabs');
    });
};

const fetchRecommendSections = async () => {
    if (!enabledTabs.value.some(t => t.id === 'recommend')) return;

    try {
        const res = await $http.get('https://api.zhihu.com/feed-root/sections/query/v2', {
            isWWW: true
        });

        const sections = [
            {
                section_name: '全站',
                section_id: null,
                sub_page_id: null,
            },
            ...(Array.isArray(res?.selected_sections) ? res.selected_sections : []),
        ];

        selectedSections.value = sections;
        hometab.value = sections.map(item => ({
            sub_page_id: item.sub_page_id,
            section_id: item.section_id
        }));

        if (currentSectionIndex.value >= hometab.value.length) {
            currentSectionIndex.value = 0;
        }

        if (activeTab.value === 'recommend') {
            await fetchRecommendData(true);
        }
    } catch (e) {
        console.error('Failed to fetch recommend sections', e);

        // section 列表接口失败时仍保留“全站”推荐，避免首页完全无法加载。
        if (hometab.value.length === 0) {
            selectedSections.value = [{
                section_name: '全站',
                section_id: null,
                sub_page_id: null,
            }];
            hometab.value = [{
                section_id: null,
                sub_page_id: null,
            }];
            currentSectionIndex.value = 0;

            if (activeTab.value === 'recommend') {
                await fetchRecommendData(true);
            }
        }
    } finally {
        refreshHighlight();
    }
};

const handleTabSelected = (pos) => {
    if (pos < 0 || pos >= hometab.value.length) return;
    currentSectionIndex.value = pos;
    fetchRecommendData(true);
};

const onRecommendRefresh = async (done) => {
    await fetchRecommendData(true);
    if (done) done();
};

const onRecommendInfinite = () => {
    if (hasMoreRecommend.value && !isRecommendLoading.value) {
        fetchRecommendData(false);
    }
};
// 推荐模块结束

// 关注模块
const momentsActiveTab = ref('recommend');

const loadDefaultFollowing = () => {
    try {
        const stored = localStorage.getItem('home_tabs_config');
        if (stored) {
            const config = JSON.parse(stored);
            if (config.defaultFollowing) return config.defaultFollowing;
        }
    } catch (e) {
        console.error('Failed to load defaultFollowing setting', e);
    }
    return 'recommend';
};

momentsActiveTab.value = loadDefaultFollowing();

const momentsTabs = [
    { id: 'recommend', label: '精选', feedType: 'recommend' },
    { id: 'timeline', label: '最新', feedType: 'timeline' },
    { id: 'pin', label: '想法', feedType: 'pin' }
];

const momentsTabData = reactive({});

momentsTabs.forEach(tab => {
    momentsTabData[tab.id] = {
        list: [],
        loading: false,
        hasMore: true,
        lastResult: null,
        requestId: 0,
    };
});

const resolveMomentsFeed = (item) => {
    const source = item?.source || {};
    const actor = source.actor || {};
    const targetItem = item?.target || item || {};
    const type = targetItem.type === 'moments_pin' ? 'pin' : targetItem.type;
    const authorName = actor.name || targetItem.author?.name || '未知用户';
    const preview = targetItem.preview || '';
    let title = targetItem.title || targetItem.excerpt_title || '';
    let excerpt = targetItem.excerpt || '';

    switch (type) {
        case 'answer':
            title = targetItem.question?.title || title;
            break;
        case 'pin':
            title = title || '一个想法';
            if (Array.isArray(targetItem.content) && targetItem.content.length > 0) {
                excerpt = targetItem.content[0]?.content || excerpt;
                if (!excerpt && targetItem.content.some(c => c.type === 'image')) {
                    excerpt = '[图片]';
                }
            }
            break;
        case 'zvideo':
            excerpt = preview || targetItem.description || '[视频]';
            break;
        default:
            break;
    }

    if (preview && preview !== '[视频]') {
        excerpt = `${authorName}: ${excerpt}`;
    }

    return {
        id: targetItem.id,
        type,
        title,
        excerpt,
        authorName,
        avatarUrl: targetItem.author?.avatar_url || actor.avatar_url || '',
        actionText: source.action_text || '',
        timeText: source.action_time ? new Date(source.action_time * 1000).toLocaleDateString() : '',
        metrics: {
            likes: targetItem.voteup_count || targetItem.reaction_count || 0,
            comments: targetItem.comment_count || 0
        }
    };
};

const resolveFeedItemIndexGroup = (item) => {
    const targetItem = item?.target || item || {};
    const type = targetItem.type === 'moments_pin' ? 'pin' : targetItem.type;
    let avatarUrl = '';
    let authorName = '未知用户';
    let actionText = '';

    if (Array.isArray(item?.actors) && item.actors.length > 0) {
        avatarUrl = item.actors[0]?.avatar_url || '';
        authorName = item.actors[0]?.name || '未知用户';
        actionText = authorName + (item.action_text || '');
    } else {
        authorName = targetItem.author?.name || '未知用户';
        avatarUrl = targetItem.author?.avatar_url || '';
    }

    const timeText = item?.action_time ? new Date(item.action_time * 1000).toLocaleDateString() : '';
    let title = targetItem.title || targetItem.excerpt_title || '';
    let excerpt = targetItem.digest || '';
    let id = targetItem.id;
    let likes = 0;
    let comments = 0;

    const parseChineseNumber = (str) => {
        if (!str) return 0;
        const num = parseFloat(str);
        if (str.includes('万')) return Math.floor(num * 10000);
        if (str.includes('千')) return Math.floor(num * 1000);
        return Math.floor(num);
    };

    if (targetItem.desc) {
        const descMatch = targetItem.desc.match(/(\d+(?:\.\d+)?[万千]?)\s*赞同/);
        if (descMatch) likes = parseChineseNumber(descMatch[1]);
        const commentMatch = targetItem.desc.match(/(\d+(?:\.\d+)?[万千]?)\s*评论/);
        if (commentMatch) comments = parseChineseNumber(commentMatch[1]);
    }

    switch (type) {
        case 'pin':
            title = title || '一个想法';
            break;
        case 'zvideo':
            if (!excerpt) excerpt = '[视频]';
            break;
        case 'drama':
            if (!excerpt) excerpt = '[直播]';
            break;
        case 'people': {
            const cardExtentData = targetItem.card_extend_data;
            if (cardExtentData) {
                authorName = cardExtentData.name || authorName;
                title = cardExtentData.description || title;
                avatarUrl = cardExtentData.avatar_url || avatarUrl;
                excerpt = cardExtentData.headline || excerpt;
                id = cardExtentData.id || id;
            }
            break;
        }
        default:
            break;
    }

    if (excerpt && excerpt !== '[视频]' && excerpt !== '[直播]') {
        excerpt = `${authorName} : ${excerpt}`;
    }

    return {
        id,
        type,
        title,
        excerpt,
        authorName,
        avatarUrl,
        actionText,
        timeText,
        unfoldShowSize: item?.unfold_show_size || 0,
        metrics: {
            likes,
            comments
        }
    };
};

const mapMomentsList = (rawList) => {
    const mappedList = [];

    for (const item of rawList) {
        if (!item) continue;

        switch (item.type) {
            case 'moments_feed': {
                const resolved = resolveMomentsFeed(item);
                if (resolved) mappedList.push(resolved);
                break;
            }
            case 'feed_item_index_group': {
                const resolved = resolveFeedItemIndexGroup(item);
                if (resolved) mappedList.push(resolved);
                break;
            }
            case 'item_group_card': {
                const actor = item.actor || {};
                mappedList.push({
                    type: 'collapsible_group',
                    groupText: item.group_text,
                    authorName: actor.name || '未知用户',
                    avatarUrl: actor.avatar_url || '',
                    actionText: item.action_text || '',
                    timeText: item.action_time ? new Date(item.action_time * 1000).toLocaleDateString() : '',
                    groupData: (item.data || []).map(resolveFeedItemIndexGroup).filter(Boolean),
                    unfoldShowSize: item.unfold_show_size || 0,
                    expanded: false
                });
                break;
            }
            case 'recommend_user_card_list':
                mappedList.push(item);
                break;
            case 'moments_recommend_followed_group':
                if (item.list?.length > 0) {
                    const resolved = resolveMomentsFeed(item.list[0]);
                    if (resolved) {
                        // MomentListCard 已支持 groupText；直接附着在真实条目上，
                        // 避免插入一个缺少 metrics 的伪条目导致渲染异常。
                        resolved.groupText = item.group_text || '';
                        mappedList.push(resolved);
                    }
                }
                break;
            default:
                break;
        }
    }

    return mappedList;
};


const fetchMomentsData = async (tabId, isRefresh = false) => {
    const state = momentsTabData[tabId];
    if (!state) return;
    if (!isRefresh && (state.loading || !state.hasMore)) return;

    const requestId = isRefresh ? ++state.requestId : state.requestId;

    if (isRefresh) {
        state.lastResult = null;
        state.hasMore = true;
    }

    state.loading = true;

    try {
        let res;
        if (isRefresh || !state.lastResult) {
            const feedType = momentsTabs.find(t => t.id === tabId)?.feedType;
            if (!feedType) return;
            res = await $http.get(`https://api.zhihu.com/moments_v3?feed_type=${feedType}`);
        } else {
            res = await state.lastResult.next();
        }

        if (requestId !== state.requestId) return;

        if (!res) {
            state.hasMore = false;
                return;
        }

        const responseData = res.data;
        const rawList = Array.isArray(responseData) ? responseData : [];
        const mappedList = mapMomentsList(rawList);

        if (isRefresh) {
            state.list = mappedList;
        } else {
            state.list.push(...mappedList);
        }

        state.lastResult = res;
        state.hasMore = hasNextPage(res);
    } catch (e) {
        if (requestId === state.requestId) {
            console.error(`Failed to fetch moments ${tabId}`, e);
        }
    } finally {
        if (requestId === state.requestId) {
            state.loading = false;
        }
    }
};

const onMomentsRefresh = async (tabId, done) => {
    await fetchMomentsData(tabId, true);
    if (done) done();
};

const onMomentsInfinite = (tabId) => {
    fetchMomentsData(tabId, false);
};

const handleMomentsTabChange = (tabId) => {
    momentsActiveTab.value = tabId;
    const state = momentsTabData[tabId];
    if (!state) return;

    if (state.list.length === 0) {
        if (!state.loading) fetchMomentsData(tabId, true);
    }
};

const handleRemoveRecommendUserCardList = (tabId, removedItem) => {
    momentsTabData[tabId].list = momentsTabData[tabId].list.filter(item =>
        !(item.type === 'recommend_user_card_list' && item.title === removedItem.title)
    );
};

const handleAuthorClick = (f7router, item) => {
    if (!item?.actor?.id) return;
    f7router.navigate(`/user/${item.actor.id}`);
};
// 关注模块结束

// 热榜模块
const hotList = ref([]);
const isHotLoading = ref(false);

const fetchHotData = async () => {
    if (isHotLoading.value) return;
    isHotLoading.value = true;

    try {
        const res = await $http.get('https://api.zhihu.com/topstory/hot-lists/total?limit=50&mobile=true');
        const responseData = res?.data;
        const rawList = Array.isArray(responseData) ? responseData : [];
        hotList.value = rawList.map((item, i) => {
            const target = item.target || {};
            const imageArea = target.image_area || {};
            const titleArea = target.title_area || {};
            const metricsArea = target.metrics_area || {};
            const linkInfo = target.link || {};
            return {
                id: item.card_id?.split('Q_')[1] || item.card_id || i,
                rank: i + 1,
                title: titleArea.text || '无标题',
                metricsArea: metricsArea.text || '',
                url: linkInfo.url || '',
                type: 'question',
                thumbnailSrc: imageArea.url || ''
            };
        });
    } catch (e) {
        console.error('Failed to fetch hot data', e);
    } finally {
        isHotLoading.value = false;
    }
};

const onHotRefresh = async (done) => {
    await fetchHotData();
    if (done) done();
};

const handleHotListCardClick = (f7router, item) => {
    if (item.type === 'question') {
        f7router.navigate(`/question/${item.id}`);
        return;
    }
    console.error('Unexpected hot-list item type', item);
};
// 热榜模块结束

// 想法模块
const thoughtsList = ref([]);
const isThoughtsLoading = ref(false);
const hasMoreThoughts = ref(true);
const lastThoughtsResult = ref(null);
let thoughtsRequestId = 0;

const getThoughtTitle = (excerpt) => {
    if (!excerpt) return '一个想法';
    const firstLine = excerpt.split('\n')[0].trim();
    return firstLine.length > 30 ? firstLine.substring(0, 30) + '...' : firstLine;
};


const fetchThoughtsData = async (isRefresh = false) => {
    if (!isRefresh && (isThoughtsLoading.value || !hasMoreThoughts.value)) return;

    const requestId = isRefresh ? ++thoughtsRequestId : thoughtsRequestId;

    if (isRefresh) {
        lastThoughtsResult.value = null;
        hasMoreThoughts.value = true;
    }

    isThoughtsLoading.value = true;

    try {
        let res;
        const url = 'https://api.zhihu.com/prague/feed?limit=10';

        if (isRefresh || !lastThoughtsResult.value) {
            res = await $http.get(url);
        } else {
            res = await lastThoughtsResult.value.next();
        }

        if (requestId !== thoughtsRequestId) return;

        if (!res) {
            hasMoreThoughts.value = false;
                return;
        }

        const responseData = res.data;
        const rawList = Array.isArray(responseData) ? responseData : [];
        const mappedList = rawList.map(item => {
            const targetItem = item?.target || item || {};
            const excerpt = targetItem.excerpt || '';
            let image = '';

            if (Array.isArray(targetItem.images) && targetItem.images.length > 0) {
                image = targetItem.images[0]?.url || '';
            } else if (targetItem.video?.thumbnail) {
                image = targetItem.video.thumbnail;
            }

            return {
                id: targetItem.id,
                title: getThoughtTitle(excerpt),
                excerpt,
                image,
                metrics: {
                    likes: targetItem.reaction?.statistics?.up_vote_count || 0,
                    comments: targetItem.reaction?.statistics?.comment_count || 0
                },
                authorName: targetItem.author?.name || '匿名用户',
                type: 'pin'
            };
        }).filter(item => item.id != null);

        if (isRefresh) {
            thoughtsList.value = mappedList;
        } else {
            thoughtsList.value.push(...mappedList);
        }

        lastThoughtsResult.value = res;
        hasMoreThoughts.value = hasNextPage(res);
    } catch (e) {
        if (requestId === thoughtsRequestId) {
            console.error('Failed to fetch thoughts', e);
        }
    } finally {
        if (requestId === thoughtsRequestId) {
            isThoughtsLoading.value = false;
        }
    }
};

const onThoughtsRefresh = async (done) => {
    await fetchThoughtsData(true);
    if (done) done();
};

const onThoughtsInfinite = () => {
    if (hasMoreThoughts.value && !isThoughtsLoading.value) {
        fetchThoughtsData(false);
    }
};
// 想法模块结束

const loadCurrentTabData = (isRefresh) => {
    if (!activeTab.value) return;

    const dataCheckMap = {
        recommend: () => (
            recommendList.value.length > 0 ||
            Boolean(lastRecommendResult.value) ||
            isRecommendLoading.value
        ),
        hot: () => hotList.value.length > 0 || isHotLoading.value,
        thoughts: () => (
            thoughtsList.value.length > 0 ||
            Boolean(lastThoughtsResult.value) ||
            isThoughtsLoading.value
        ),
        following: () => {
            const state = momentsTabData[momentsActiveTab.value];
            return Boolean(
                state &&
                (
                    state.list.length > 0 ||
                    state.lastResult ||
                    state.loading
                )
            );
        },
    };

    if (isRefresh === undefined && dataCheckMap[activeTab.value]?.()) {
        return;
    }

    const refresh = isRefresh !== undefined ? isRefresh : true;

    switch (activeTab.value) {
        case 'recommend':
            if (hometab.value.length > 0) {
                fetchRecommendData(refresh);
            } else {
                fetchRecommendSections();
            }
            break;
        case 'hot':
            fetchHotData();
            break;
        case 'thoughts':
            fetchThoughtsData(refresh);
            break;
        case 'following':
            if (isLoggedIn.value) {
                fetchMomentsData(momentsActiveTab.value, refresh);
            }
            break;
        default:
            break;
    }
};


watch(activeTab, (newTab, oldTab) => {
    if (newTab === oldTab) return;
    loadCurrentTabData();
});

watch(currentSectionIndex, refreshHighlight);

// 使用 useUser hook
const { isLoggedIn, onUserUpdate } = useUser();
let unsubscribeUserUpdate = null;

const handleHomeSettingsChanged = async () => {
    loadSettings();
    await fetchRecommendSections();
    loadCurrentTabData();
};

onMounted(async () => {
    isMobile.value = !f7.device.desktop;

    window.addEventListener('home-settings-changed', handleHomeSettingsChanged);
    window.addEventListener('home-recommendtab-settings-changed', fetchRecommendSections);

    unsubscribeUserUpdate = onUserUpdate(async () => {
        if (!isLoggedIn.value) return;
            await fetchRecommendSections();
        if (activeTab.value === 'following') {
            fetchMomentsData(momentsActiveTab.value, true);
        }
    });

    await fetchRecommendSections();
    loadCurrentTabData();

    nextTick(() => {
        if (!isMobile.value) {
            f7.toolbar.setHighlight('.desktop-home-toolbar');
        }
    });
});

onUnmounted(() => {
    window.removeEventListener('home-settings-changed', handleHomeSettingsChanged);
    window.removeEventListener('home-recommendtab-settings-changed', fetchRecommendSections);
    if (unsubscribeUserUpdate) unsubscribeUserUpdate();
});
</script>

<template>
    <f7-page name="home" :page-content="false" :class="{ 'home-mobile': isMobile }">
        <template #fixed>
            <TopBar :f7router="f7router" />

            <f7-toolbar tabbar top class="desktop-home-toolbar" v-if="!isMobile">
                <f7-link
                    v-for="tab in enabledTabs"
                    :key="tab.id"
                    :tab-link="`#tab-${tab.id}`"
                    :tab-link-active="activeTab === tab.id"
                    @click="activeTab = tab.id"
                >
                    {{ tab.label }}
                </f7-link>
            </f7-toolbar>
        </template>

        <f7-tabs class="home-main-tabs" animated>
            <f7-tab
                id="tab-recommend"
                :tab-active="activeTab === 'recommend'"
                v-if="enabledTabs.some(t => t.id === 'recommend')"
            >
                <div class="home-tab-shell">
                    <f7-toolbar
                        tabbar
                        top
                        class="recommend-section-tabs tab-bar-static"
                        v-if="isLoggedIn && selectedSections.length > 0"
                    >
                        <f7-link
                            v-for="(section, index) in selectedSections"
                            :key="`${section.section_id}-${index}`"
                            :class="{ 'tab-link-active': currentSectionIndex === index }"
                            @click="handleTabSelected(index)"
                        >
                            {{ section.section_name }}
                        </f7-link>
                    </f7-toolbar>

                    <f7-page-content
                        class="home-scroll-content recommend-scroll-content"
                        ptr
                        @ptr:refresh="onRecommendRefresh"
                        infinite
                        :infinite-preloader="isRecommendLoading && hasMoreRecommend"
                        @infinite="onRecommendInfinite"
                    >
                        <div class="card-grid">
                            <FeedCard
                                class="masonry-item"
                                v-for="(item, idx) in recommendList"
                                :key="`${item.type}-${item.id ?? idx}-${idx}`"
                                :item="item"
                                @click="$handleCardClick(f7router, item)"
                            />
                        </div>

                        <div
                            class="load-more block text-align-center"
                            v-if="!hasMoreRecommend && recommendList.length > 0"
                        >
                            <span class="text-color-gray">没有更多内容了</span>
                        </div>

                        <div
                            v-if="!isRecommendLoading && recommendList.length === 0"
                            class="empty-state"
                        >
                            <f7-icon f7="tray" size="48" color="gray" />
                            <p>暂无推荐内容</p>
                        </div>
                    </f7-page-content>
                </div>
            </f7-tab>

            <f7-tab
                id="tab-following"
                :tab-active="activeTab === 'following'"
                v-if="enabledTabs.some(t => t.id === 'following')"
            >
                <div class="home-tab-shell">
                    <div v-if="!isLoggedIn" class="empty-state following-login-state">
                        <f7-icon f7="person" size="48" color="gray" />
                        <p>不登录无法加载数据</p>
                        <f7-button fill color="primary" @click="f7.dialog.alert('请点击主页右上角登录')">
                            去登录
                        </f7-button>
                    </div>

                    <TabLayout
                        v-else
                        class="home-following-layout"
                        :tabs="momentsTabs"
                        :onChange="handleMomentsTabChange"
                        :nested="true"
                        :autoPageContent="false"
                        :fixed="false"
                        :initialActiveId="momentsActiveTab"
                    >
                        <template v-for="tab in momentsTabs" :key="tab.id" #[tab.id]>
                            <f7-page-content
                                ptr
                                @ptr:refresh="(done) => onMomentsRefresh(tab.id, done)"
                                infinite
                                :infinite-preloader="momentsTabData[tab.id].loading && momentsTabData[tab.id].hasMore"
                                @infinite="onMomentsInfinite(tab.id)"
                                class="moments-scroll-content"
                                :data-feed-tab="tab.id"
                            >
                                <div class="moments-list">
                                    <template v-for="(item, index) in momentsTabData[tab.id].list" :key="index">
                                        <RecommendUserCardList
                                            v-if="item.type === 'recommend_user_card_list'"
                                            :item="item"
                                            @remove="(removedItem) => handleRemoveRecommendUserCardList(tab.id, removedItem)"
                                            @click="(item) => handleAuthorClick(f7router, item)"
                                        />
                                        <MomentListCard
                                            v-else
                                            :item="item"
                                            @click="$handleCardClick(f7router, $event)"
                                        />
                                    </template>

                                    <div
                                        v-if="!momentsTabData[tab.id].hasMore && momentsTabData[tab.id].list.length > 0"
                                        class="padding text-align-center text-color-gray"
                                    >
                                        没有更多内容了
                                    </div>

                                    <div
                                        v-if="!momentsTabData[tab.id].loading && momentsTabData[tab.id].list.length === 0"
                                        class="empty-state"
                                    >
                                        <f7-icon f7="tray" size="48" color="gray" />
                                        <p>暂无动态</p>
                                    </div>
                                </div>
                            </f7-page-content>
                        </template>
                    </TabLayout>
                </div>
            </f7-tab>

            <f7-tab
                id="tab-hot"
                :tab-active="activeTab === 'hot'"
                v-if="enabledTabs.some(t => t.id === 'hot')"
            >
                <div class="home-tab-shell">
                    <f7-page-content class="home-scroll-content" ptr @ptr:refresh="onHotRefresh">
                        <f7-list media-list no-hairlines class="hot-list">
                            <HotListCard
                                v-for="(item, index) in hotList"
                                :key="item.id"
                                :item="item"
                                :rank="index + 1"
                                @click="handleHotListCardClick(f7router, item)"
                            />
                        </f7-list>

                        <div v-if="!isHotLoading && hotList.length === 0" class="empty-state">
                            <f7-icon f7="tray" size="48" color="gray" />
                            <p>暂无热榜内容</p>
                        </div>
                    </f7-page-content>
                </div>
            </f7-tab>

            <f7-tab
                id="tab-thoughts"
                :tab-active="activeTab === 'thoughts'"
                v-if="enabledTabs.some(t => t.id === 'thoughts')"
            >
                <div class="home-tab-shell">
                    <f7-page-content
                        class="home-scroll-content thoughts-scroll-content"
                        ptr
                        @ptr:refresh="onThoughtsRefresh"
                        infinite
                        :infinite-preloader="isThoughtsLoading && hasMoreThoughts"
                        @infinite="onThoughtsInfinite"
                    >
                        <div class="card-grid">
                            <FeedCard
                                class="masonry-item"
                                v-for="(item, index) in thoughtsList"
                                :key="`${item.id ?? index}-${index}`"
                                :item="item"
                                @click="$handleCardClick(f7router, item)"
                            />
                        </div>

                        <div
                            class="load-more block text-align-center"
                            v-if="!hasMoreThoughts && thoughtsList.length > 0"
                        >
                            <span class="text-color-gray">没有更多内容了</span>
                        </div>

                        <div v-if="!isThoughtsLoading && thoughtsList.length === 0" class="empty-state">
                            <f7-icon f7="tray" size="48" color="gray" />
                            <p>暂无想法</p>
                        </div>
                    </f7-page-content>
                </div>
            </f7-tab>
        </f7-tabs>

        <f7-toolbar tabbar bottom icons v-if="isMobile" class="mobile-home-toolbar">
            <f7-toolbar-pane>
                <f7-link
                    v-for="tab in enabledTabs"
                    :key="tab.id"
                    :tab-link="`#tab-${tab.id}`"
                    :tab-link-active="activeTab === tab.id"
                    @click="activeTab = tab.id"
                    :icon-ios="tab.iosIcon"
                    :icon-md="tab.mdIcon"
                    :text="tab.label"
                />
            </f7-toolbar-pane>
        </f7-toolbar>
    </f7-page>
</template>

<style scoped>

.home-tab-shell {
    width: 100%;
    height: 100%;
    min-height: 0;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    padding-top: calc(
        var(--f7-navbar-height) +
        var(--f7-safe-area-top) +
        var(--f7-toolbar-height)
    );
}

:global(.home-mobile) .home-tab-shell {
    padding-top: calc(var(--f7-navbar-height) + var(--f7-safe-area-top));
    padding-bottom: calc(var(--f7-tabbar-icons-height) + var(--f7-safe-area-bottom));
}

.home-scroll-content {
    flex: 1 1 auto;
    min-height: 0;
    height: auto !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}

.home-following-layout {
    flex: 1 1 auto;
    min-height: 0;
    height: auto !important;
}

.card-grid {
    padding: 16px;
    column-count: 1;
    column-gap: 16px;
    padding-bottom: 80px;
}

@media (min-width: 768px) {
    .card-grid {
        column-count: 2;
    }
}

.masonry-item {
    break-inside: avoid;
    margin-bottom: 16px;
}

.list-layout {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-bottom: 80px;
}

.hot-list {
    margin-top: 0;
    margin-bottom: 0;
    padding-bottom: 80px;
    background: var(--f7-page-bg-color);
}

.moments-scroll-content {
    height: 100% !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}

.moments-list {
    padding: 8px 0 80px;
}

.empty-state {
    padding: 100px 32px;
    text-align: center;
    color: var(--f7-card-footer-text-color, var(--f7-text-color));
}

.following-login-state {
    flex: 1 1 auto;
    min-height: 0;
}

.recommend-section-tabs {
    --f7-toolbar-bg-color: var(--f7-bars-bg-color);
    z-index: 100;
    flex: 0 0 var(--f7-toolbar-height);
    margin-bottom: 0;
    box-shadow: 0 1px 0 rgba(0, 0, 0, 0.1);
}
</style>
