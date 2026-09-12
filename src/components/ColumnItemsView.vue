<script setup>
import { ref, onMounted } from 'vue';
import $http from '../api/http.js';
import FeedCard from './FeedCard.vue';
import { useHistory } from '../composables/useHistory.js';

const props = defineProps({
    f7route: Object,
    f7router: Object,
    routeId: String
});

const { register, restoreState } = useHistory(props, 'column_items');
const hasHistory = !!restoreState();
const columnId = props.f7route.params.id;
const items = ref([]);
const isLoading = ref(false);
const hasMore = ref(true);
const lastResult = ref(null);
const loadError = ref('');
const pageRef = ref(null);

register({
    state: {
        items,
        isLoading,
        hasMore,
        lastResult,
        loadError
    },
    scroll: () => ({
        main: pageRef.value?.$el?.querySelector('.page-content')
    })
});

const fetchItems = async (isRefresh = false) => {
    if (isLoading.value) return;
    if (!isRefresh && (!hasMore.value || loadError.value)) return;

    isLoading.value = true;
    if (isRefresh) {
        loadError.value = '';
    }

    try {
        let res;
        if (isRefresh || !lastResult.value) {
            const url = `https://www.zhihu.com/api/v4/columns/${columnId}/items?limit=20&offset=0`;
            res = await $http.get(url, {
                requestMode: 'web'
            });
        } else {
            res = await lastResult.value.next();
        }

        if (!res) {
            hasMore.value = false;
            return;
        }

        const rawList = res.data || [];
        const mapped = rawList.map(item => resolveItem(item));
        if (isRefresh) {
            items.value = mapped;
        } else {
            items.value.push(...mapped);
        }
        lastResult.value = res;
        hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);
        loadError.value = '';
    } catch (e) {
        console.error('Failed to fetch column items:', e);
        loadError.value = e?.message || '专栏内容加载失败';
    } finally {
        isLoading.value = false;
    }
};

const resolveItem = (item) => {
    const authorName = item.author?.name || '';
    const likes = item.voteup_count || 0;
    const comments = item.comment_count || 0;
    let excerpt = item.excerpt || '';
    let action = '';
    const id = item.id || '';
    const type = item.type || '';
    let title = '';
    switch (type) {
        case 'answer':
            action = '添加了回答';
            title = item.question?.title || '未知问题';
            break;
        case 'zvideo':
            action = '添加了视频';
            title = item.title || '未知视频';
            excerpt = '[视频]';
            break;
        case 'article':
            action = '添加了文章';
            title = item.title || '未知文章';
            break;
        default:
            action = '未知';
            title = item.title || item.name || '无标题';
            break;
    }
    return {
        id,
        type,
        title,
        excerpt,
        action,
        authorName,
        metrics: {
            likes,
            comments
        }
    };
};

const onRefresh = async (done) => {
    await fetchItems(true);
    done();
};

const onInfinite = () => {
    fetchItems();
};

onMounted(() => {
    if (!hasHistory) {
        fetchItems(true);
    }
});
</script>
<template>
    <f7-page name="column-items" ptr @ptr:refresh="onRefresh" infinite
        :infinite-preloader="isLoading && hasMore" @infinite="onInfinite"
        :ref="(el) => pageRef = el">
        <f7-navbar title="专栏详情" back-link="返回" />

        <div class="items-list">
            <FeedCard v-for="(item, index) in items.filter(i => i !== null)" :key="item.id + '-' + index" :item="item"
                @click="$handleCardClick(f7router, item)" />
        </div>
        <div v-if="loadError" class="error-state">
            <f7-icon f7="exclamationmark_triangle" size="40" color="red" />
            <p>专栏内容加载失败</p>
            <f7-button fill small @click="fetchItems(true)">重试</f7-button>
        </div>
        <div v-else-if="!hasMore && items.length > 0" class="padding text-align-center text-color-gray no-more">
            已加载全部内容
        </div>
        <div v-else-if="!isLoading && items.length === 0" class="empty-state">
            <f7-icon f7="tray_fill" size="48" color="gray" />
            <p>该专栏暂无内容</p>
        </div>
    </f7-page>
</template>
<style scoped>
.empty-state,
.error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 64px 32px;
    color: var(--app-text-muted);
}

.error-state .button {
    width: 120px;
}

.no-more {
    font-size: 13px;
}
</style>
