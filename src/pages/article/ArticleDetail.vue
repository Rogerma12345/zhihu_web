<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue';
import { destroyOnClosed } from '@/utils/modal.js';
import ContentRenderer from '@/components/ContentRenderer.vue';
import CommentsSheet from '@/components/CommentsSheet.vue';
import CollectionSheet from '@/components/CollectionSheet.vue';
import { HistoryService } from '@/services/history.js';
import { saveContent } from '@/services/local-save.js';
import { getScrollPosition, setScrollPosition, clearScrollPosition } from '@/services/scroll-store.js';
import { f7 } from 'framework7-vue';
import html2canvas from 'html2canvas-pro';
import $http from '@/services/http.js';
import { usePageState } from '@/composables/usePageState.js';
import { useReaction } from '@/composables/useReaction.js';
import { openLink } from '@/core/navigation.js';
import { settings } from '@/core/settings.js';
import { copyText, shareText, shareFile, downloadBlob } from '@/utils/share.js';
import { segmentsToMarkdown } from '@/utils/markdown.js';
import { debounce, throttle } from '@/utils/timing.js';
import { formatCount } from '@/utils/format.js';
import PageLoader from '@/components/PageLoader.vue';
import PhotoBrowser from '@/components/PhotoBrowser.vue';

const props = defineProps({
    f7route: Object,
    f7router: Object,
    // 问题页进入回答时携带的有序回答 id，用于上下滑切换
    neighborIds: { type: Array, default: null },
    // 序列出处：question=问题页给的回答列表，feed=next-render 推荐流（还能继续往后要）
    seqSource: { type: String, default: '' },
});

const item = ref(null);
const loading = ref(true);
const showComments = ref(false);
const showCollection = ref(false);
const showToc = ref(false);
const tocItems = ref([]);
const isTocExpanded = ref(false);
const imageList = ref([]);
const activeImage = ref(0);
const photoBrowserRef = ref(null);

const { hasCache } = usePageState({
    state: {
        item,
        showComments,
        showCollection,
        showToc,
        tocItems,
        isTocExpanded,
        imageList,
        activeImage
    },
    loading,
});

const handleImageClick = (data) => {
    const urls = data.allUrls || [data.url];
    photoBrowserRef.value?.open(urls, data.index || 0);
};

const handleGalleryImageClick = (index) => {
    handleImageClick({
        url: imageList.value[index].url,
        index: index,
        allUrls: imageList.value.map(img => img.url)
    });
};

let type = props.f7route?.params?.type;
switch (type) {
    case "pin_general":
    case "moments_pin":
        type = "pin";
        break;
    case "p":
        type = "article";
        break;
    default:
        break;
}

const id = props.f7route?.params?.id;

const visibleTocItems = computed(() => {
    if (tocItems.value.length <= 3 || isTocExpanded.value) {
        return tocItems.value;
    }
    return tocItems.value.slice(0, 3);
});

// 阅读进度：滚动位置换算 0-100，离开页面时随历史再记一次并上报
let readProgress = 0;
let historyEntry = null;

// 跨重启回到上次的阅读处：按 URL 记偏移，5px 内的抖动不写盘
const routeUrl = props.f7route?.url;
let lastSavedTop = -1;

const rememberScroll = (el) => {
    if (type !== 'answer' || !routeUrl) return;
    if (Math.abs(el.scrollTop - lastSavedTop) < 5) return;
    lastSavedTop = el.scrollTop;
    setScrollPosition(routeUrl, el.scrollTop);
};

const onContentScroll = throttle(() => {
    const el = contentRef.value?.$el;
    if (!el) return;
    const max = el.scrollHeight - el.clientHeight;
    readProgress = max > 0 ? Math.min(100, Math.round((el.scrollTop / max) * 100)) : 100;
    rememberScroll(el);
}, 3000);

// 配图与代码块会陆续撑高容器，高度不足目标位置时轮询等待，超时则丢弃记录
const RESTORE_POLL_MS = 100;
const RESTORE_WAIT_MS = 5000;
let restoreTimer = null;

const restoreScroll = () => {
    const saved = getScrollPosition(routeUrl);
    if (saved <= 10) return;
    const startAt = Date.now();
    restoreTimer = setInterval(() => {
        const el = contentRef.value?.$el;
        if (!el) return stopRestorePolling();
        if (el.scrollHeight > saved) {
            el.scrollTop = saved;
            lastSavedTop = saved;
            stopRestorePolling();
        } else if (Date.now() - startAt > RESTORE_WAIT_MS) {
            clearScrollPosition(routeUrl);
            stopRestorePolling();
        }
    }, RESTORE_POLL_MS);
};

function stopRestorePolling() {
    if (restoreTimer) clearInterval(restoreTimer);
    restoreTimer = null;
}

// 相邻回答序列：本地已知的有序 id。问题页把列表传进来；直接进入与滑切则由 next-render 往后接
const answerSeq = ref(
    type === 'answer' && props.neighborIds?.length > 1 ? props.neighborIds.map(String) : null
);
// 序列出处决定能否往后接：问题页自己的回答列表到底就停，不混进推荐流
const seqSource = ref(props.neighborIds?.length > 1 ? props.seqSource || 'question' : 'feed');
const canSwipeAnswers = computed(() => type === 'answer' && !settings.answerSinglePage
    && (seqSource.value === 'feed' || answerSeq.value?.length > 1));
const swipeStart = { x: 0, y: 0, top: false, bottom: false, fromMouse: false };
// 上下滑切换：正文已经滚到边缘后，再拖过这个距离才算切条（边缘之内的那段是正常滚动）
const minSwipeDy = 90;

// 悬浮按钮：一次滚一屏，容器就是正文滚动区；只对回答启用，与设置所在分组一致
const showFloatScroll = computed(() => !!item.value && type === 'answer' && settings.floatScrollButtons);

const scrollByViewport = (direction) => {
    const el = contentRef.value?.$el;
    if (!el) return;
    el.scrollBy({ top: direction * el.clientHeight, behavior: 'smooth' });
};

// 往后补一批 id：next-render 只给「下一条」方向的推荐流，往前一律不请求
const extendSeqFromFeed = async () => {
    try {
        const res = await $http.get(
            `https://api.zhihu.com/next-render?id=${id}&type=answer&scenes=recommend&context_expand=1&is_native=1&limit=5`);
        const ids = (res.data || []).filter((i) => i?.type === 'answer').map((i) => String(i.id));
        if (!ids.length) return;
        const keep = answerSeq.value?.length ? answerSeq.value : [String(id)];
        answerSeq.value = [...keep, ...ids.filter((x) => !keep.includes(x))];
    } catch {
        // 拿不到就维持现状：往后没有已知条目时滑动不响应
    }
};

// 本条已是序列末尾（或还没有序列）才需要往后取，问题页给的列表取到头就停
const ensureForward = async () => {
    if (type !== 'answer' || settings.answerSinglePage || seqSource.value !== 'feed') return;
    const seq = answerSeq.value;
    if (seq?.length && seq[seq.length - 1] !== String(id)) return;
    await extendSeqFromFeed();
};

// reloadCurrent 换页：旧实例卸载时按自身进度写历史记录并回收页面缓存，返回栈仍指回问题页
const goAdjacentAnswer = async (delta) => {
    if (delta > 0) await ensureForward();
    const seq = answerSeq.value;
    const i = seq ? seq.indexOf(String(id)) : -1;
    const target = i < 0 ? null : seq[i + delta]; // 往前只取本地已有的，越界即无响应
    if (!target) return;
    props.f7router.navigate(`/article/answer/${target}`, {
        reloadCurrent: true,
        props: { neighborIds: seq, seqSource: seqSource.value },
    });
};

// 触摸取 changedTouches，鼠标直接用事件坐标：同一份判据两边共用
const gesturePoint = (e) => e.changedTouches?.[0] || e;

const onGestureStart = (e) => {
    // 桌面没有 touch 事件，鼠标按下-拖动-抬起要走同一份判据；右键不参与滑动
    if (e.button !== undefined && e.button !== 0) return;
    const t = gesturePoint(e);
    swipeStart.x = t.clientX;
    swipeStart.y = t.clientY;
    swipeStart.fromMouse = e.type.startsWith('mouse');
    const el = contentRef.value?.$el;
    swipeStart.top = !!el && el.scrollTop <= 0;
    swipeStart.bottom = !!el && el.scrollTop + el.clientHeight >= el.scrollHeight - 2;
};

const onGestureEnd = (e) => {
    if (!canSwipeAnswers.value || showComments.value || showCollection.value || showSearch.value) return;
    const t = gesturePoint(e);
    const dy = t.clientY - swipeStart.y;
    const dx = t.clientX - swipeStart.x;
    if (Math.abs(dy) < minSwipeDy || Math.abs(dy) < Math.abs(dx) * 1.6) return; // 横向手势与小幅抖动不算
    if (dy < 0 ? !swipeStart.bottom : !swipeStart.top) return; // 上滑要已在底部，下滑要已在顶部
    // 鼠标拖动顺带划选了正文，切页后清掉那一条蓝带
    if (swipeStart.fromMouse) window.getSelection()?.removeAllRanges();
    goAdjacentAnswer(dy < 0 ? 1 : -1);
};

const fetchData = async () => {
    loading.value = true;
    try {
        const apiType = type;

        const data = await $http.get(`https://api.zhihu.com/${apiType}s/v2/${id}`);

        let segs = data.structured_content?.segments ? [...data.structured_content.segments] : [];
        if (data.relationship_tips) segs.unshift({ type: 'myapptip', myapptip: { text: data.relationship_tips.text } });
        if (data.video) segs.unshift({
            type: 'video',
            video: {
                id: data.video.attachment_id,
                title: data.video.title,
                poster: data.video.image_url || data.image_url || data.title_image || '',
            }
        });

        let bottomText = '未知';
        const info = data.content_end_info;
        if (info) {
            bottomText = info.update_time_text || info.create_time_text || '未知';
            if (info.ip_info) bottomText += ` · ${info.ip_info}`;
        }
        segs.push({ type: 'myapptip', myapptip: { text: bottomText } });

        const mappedItem = {
            id: data.id,
            title: data.header?.text || '无标题',
            authorName: data.author?.fullname || '匿名用户',
            authorId: data.author?.id,
            avatarUrl: data.author?.avatar?.avatar_image?.day || '',
            imageUrl: data.image_url || data.title_image || '',
            structured_content: segs,
            content: data.content || '',
            metrics: {
                votes: data.reaction?.statistics?.up_vote_count || 0,
                likes: data.reaction?.statistics?.like_count || 0,
                favorites: data.reaction?.statistics?.favorites || 0,
                comments: data.reaction?.statistics?.comment_count || 0
            },
            isUpvoted: data.reaction?.relation?.vote === "UP" ? true : false,
            isLiked: data.reaction?.relation?.liked || false,
            isFavorited: data.reaction?.relation?.faved || false
        };


        if (data.settings?.table_of_contents?.enabled) {
            tocItems.value = extractTOC(segs);
        }

        // 处理段落中的索引
        segs.forEach((seg, idx) => {
            seg._index = idx;
        });

        if (type === 'answer') {
            mappedItem.questionID = data.question?.id;
        }

        if (data.image_list?.images) {
            imageList.value = data.image_list.images;
        }

        item.value = mappedItem;
        // 预取下一批：不 await，用户第一次上滑时不必等网络
        ensureForward();

        // 历史：进入即记一条，离开时带真实阅读进度再记（addRecord 去重置顶并上报服务端）
        historyEntry = {
            id: mappedItem.id,
            type: type,
            title: mappedItem.title,
            preview: mappedItem.content?.substring(0, 100).replace(/<[^>]+>/g, ''),
        };
        readProgress = 0;
        HistoryService.addRecord({ ...historyEntry, progress: 0 });

        if (!hasCache.value) nextTick(restoreScroll);

    } catch (e) {
        f7.dialog.alert(`文章加载失败，请稍后重试 ${e}`, () => {
            props.f7router.back();
        });
    } finally {
        loading.value = false;
    }
};

const extractTOC = (segs) => {
    const items = [];
    segs.forEach((seg, idx) => {
        if (seg.type === 'heading' && seg.heading?.text) {
            items.push({ id: `heading-${idx}`, text: seg.heading.text, level: seg.heading.level });
        }
    });
    return items;
};



const scrollToHeading = (elementId) => {
    showToc.value = false;
    nextTick(() => {
        const el = document.getElementById(elementId);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
};

const { toggleVote, toggleLike, toggleFavorite, onCollectionSuccess } = useReaction(item, {
    name: '文章',
    type,
    id,
    onCollectSwap: () => { showCollection.value = true; },
});

const navTitleClick = () => {
    if (type == "answer") props.f7router.navigate(`/question/${item.value.questionID}`);
}

const navigateToUser = (userId) => {
    props.f7router.navigate(`/user/${userId}`);
};

onMounted(() => {
    if (!hasCache.value && id) {
        fetchData();
    }
});

const SCREENSHOT_MAX_CANVAS_EDGE = 32760;
const SCREENSHOT_MAX_CANVAS_AREA = 268000000;
const SCREENSHOT_PREFERRED_SCALE = 2;
const SCREENSHOT_MIN_SCALE = 1;
const SCREENSHOT_RESOURCE_TIMEOUT = 15000;

let screenshotInProgress = false;

const createScreenshotError = (code, message, cause) => {
    const error = new Error(message);
    error.code = code;
    if (cause) error.cause = cause;
    return error;
};

const isTransparentColor = (value) => {
    const normalized = String(value || '').replace(/\s+/g, '').toLowerCase();
    return !normalized
        || normalized === 'transparent'
        || normalized === 'rgba(0,0,0,0)'
        || normalized.endsWith('/0)');
};

const resolveCaptureBackground = (element) => {
    let current = element;
    while (current instanceof HTMLElement) {
        const backgroundColor = window.getComputedStyle(current).backgroundColor;
        if (!isTransparentColor(backgroundColor)) return backgroundColor;
        current = current.parentElement;
    }

    const rootStyle = window.getComputedStyle(document.documentElement);
    const pageBackground = rootStyle.getPropertyValue('--f7-page-bg-color').trim();
    if (pageBackground && !pageBackground.includes('var(')) return pageBackground;

    return document.documentElement.classList.contains('dark') ? '#1c1c1d' : '#ffffff';
};

const withTimeout = (promise, timeoutMs, timeoutMessage) => new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
        reject(createScreenshotError('RESOURCE_TIMEOUT', timeoutMessage));
    }, timeoutMs);

    Promise.resolve(promise).then(
        (value) => {
            window.clearTimeout(timer);
            resolve(value);
        },
        (error) => {
            window.clearTimeout(timer);
            reject(error);
        }
    );
});

const waitForCaptureImage = async (image) => {
    const source = image.currentSrc || image.src;
    if (!source) return;

    if (!image.complete) {
        await new Promise((resolve, reject) => {
            let timer = null;
            let settled = false;

            const cleanup = () => {
                if (timer !== null) window.clearTimeout(timer);
                image.removeEventListener('load', handleLoad);
                image.removeEventListener('error', handleError);
            };
            const settle = (callback) => {
                if (settled) return;
                settled = true;
                cleanup();
                callback();
            };
            const handleLoad = () => settle(resolve);
            const handleError = () => settle(() => {
                reject(createScreenshotError('IMAGE_LOAD_FAILED', `图片加载失败: ${source}`));
            });

            image.addEventListener('load', handleLoad, { once: true });
            image.addEventListener('error', handleError, { once: true });
            timer = window.setTimeout(() => settle(() => {
                reject(createScreenshotError('RESOURCE_TIMEOUT', `图片加载超时: ${source}`));
            }), SCREENSHOT_RESOURCE_TIMEOUT);

            if (image.complete) {
                queueMicrotask(() => {
                    if (image.naturalWidth > 0 && image.naturalHeight > 0) handleLoad();
                    else handleError();
                });
            }
        });
    }

    if (image.naturalWidth <= 0 || image.naturalHeight <= 0) {
        throw createScreenshotError('IMAGE_LOAD_FAILED', `图片没有可用像素: ${source}`);
    }

    if (typeof image.decode === 'function') {
        await withTimeout(
            image.decode().catch((error) => {
                if (image.complete && image.naturalWidth > 0 && image.naturalHeight > 0) return;
                throw error;
            }),
            SCREENSHOT_RESOURCE_TIMEOUT,
            `图片解码超时: ${source}`
        );
    }
};

const prepareCaptureResources = async (rootElement) => {
    const images = Array.from(rootElement.querySelectorAll('img'));
    const imageStates = images.map((image) => ({
        image,
        loading: image.getAttribute('loading'),
        fetchPriority: image.getAttribute('fetchpriority'),
    }));

    for (const { image } of imageStates) {
        image.setAttribute('loading', 'eager');
        image.setAttribute('fetchpriority', 'high');
    }

    if (document.fonts?.ready) {
        try {
            await withTimeout(document.fonts.ready, SCREENSHOT_RESOURCE_TIMEOUT, '字体加载超时');
        } catch (error) {
            console.warn('截图字体准备未完成:', error);
        }
    }

    const imageResults = await Promise.allSettled(images.map(waitForCaptureImage));
    const failedImages = imageResults
        .map((result, index) => ({ result, image: images[index] }))
        .filter(({ result }) => result.status === 'rejected');

    if (failedImages.length > 0) {
        console.warn('截图图片准备失败:', failedImages.map(({ result, image }) => ({
            src: image.currentSrc || image.src,
            reason: result.reason,
        })));
    }

    return {
        failedImageCount: failedImages.length,
        restore: () => {
            for (const { image, loading, fetchPriority } of imageStates) {
                if (loading === null) image.removeAttribute('loading');
                else image.setAttribute('loading', loading);

                if (fetchPriority === null) image.removeAttribute('fetchpriority');
                else image.setAttribute('fetchpriority', fetchPriority);
            }
        },
    };
};

const calculateCaptureScale = (width, height) => {
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
        throw createScreenshotError('INVALID_CAPTURE_SIZE', '截图尺寸无效');
    }

    const scaleByEdge = Math.min(
        SCREENSHOT_MAX_CANVAS_EDGE / width,
        SCREENSHOT_MAX_CANVAS_EDGE / height
    );
    const scaleByArea = Math.sqrt(SCREENSHOT_MAX_CANVAS_AREA / (width * height));
    const safeScale = Math.min(SCREENSHOT_PREFERRED_SCALE, scaleByEdge, scaleByArea);

    if (safeScale < SCREENSHOT_MIN_SCALE) {
        throw createScreenshotError('CONTENT_TOO_LONG', '文章超过单张图片尺寸限制');
    }

    return Math.max(
        SCREENSHOT_MIN_SCALE,
        Math.floor(safeScale * 100) / 100
    );
};

const canvasToPngBlob = (canvas) => new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
        if (!blob) {
            reject(createScreenshotError('PNG_ENCODING_FAILED', 'PNG 图片生成失败'));
            return;
        }
        resolve(blob);
    }, 'image/png');
});

const screenshotFileName = () => {
    const title = (item.value?.title || '知乎截图').replace(/[\\/:*?"<>|]/g, '').trim();
    return `${title || '知乎截图'}.png`;
};

const openScreenshotPreview = (blob, failedImageCount, captureScale) => {
    const previewUrl = URL.createObjectURL(blob);
    let previewUrlReleased = false;

    const releasePreviewUrl = () => {
        if (previewUrlReleased) return;
        previewUrlReleased = true;
        URL.revokeObjectURL(previewUrl);
    };

    const warnings = [];
    if (failedImageCount > 0) warnings.push(`有 ${failedImageCount} 张图片未完成加载，导出内容可能不完整。`);
    if (captureScale < SCREENSHOT_PREFERRED_SCALE) warnings.push(`文章较长，导出倍率已调整为 ${captureScale.toFixed(2)}。`);
    const warningHtml = warnings.length
        ? `<div style="margin-top: 8px; text-align: left; font-size: 12px; opacity: 0.72;">${warnings.join('<br>')}</div>`
        : '';
    const fileName = screenshotFileName();

    const dialog = f7.dialog.create({
        title: '截图预览',
        content: `
            <div style="padding: 10px; text-align: center;">
                <img src="${previewUrl}" alt="截图预览" style="max-width: 100%; max-height: 60vh; border-radius: 8px;" />
                ${warningHtml}
            </div>
        `,
        buttons: [
            { text: '取消', role: 'cancel' },
            {
                text: '保存',
                onClick: () => {
                    downloadBlob(blob, fileName);
                    f7.toast.show({ text: '截图已保存' });
                },
            },
            {
                text: '分享',
                onClick: async () => {
                    const result = await shareFile(new File([blob], fileName, { type: 'image/png' }), {
                        title: item.value?.title,
                        url: originalUrl() || undefined,
                    });
                    if (result === 'unsupported') {
                        downloadBlob(blob, fileName);
                        const url = originalUrl();
                        if (url) await copyText(url);
                        f7.toast.show({ text: url ? '当前环境不支持图片分享，已保存并复制链接' : '当前环境不支持图片分享，已保存图片' });
                    }
                },
            },
        ],
        verticalButtons: false,
        on: { closed: releasePreviewUrl },
    });
    destroyOnClosed(dialog).open();
};

const screenshotErrorMessage = (error) => {
    switch (error?.code) {
        case 'CONTENT_NOT_FOUND': return '截图失败，未找到文章内容';
        case 'INVALID_CAPTURE_SIZE': return '截图失败，文章尺寸无效';
        case 'CONTENT_TOO_LONG': return '截图失败，文章超过单张图片尺寸限制';
        case 'PNG_ENCODING_FAILED': return '截图失败，PNG 图片生成失败';
        default: return '截图生成失败，详情见控制台';
    }
};

const saveAsImage = async () => {
    if (!item.value) return;
    if (screenshotInProgress) {
        f7.toast.show({ text: '截图正在生成' });
        return;
    }

    screenshotInProgress = true;
    f7.toast.show({ text: '正在生成截图...' });

    let restoreResources = null;
    let captureRoot = null;

    try {
        captureRoot = document.querySelector('.page-current .content-wrapper');
        if (!captureRoot) throw createScreenshotError('CONTENT_NOT_FOUND', '未找到文章内容');

        const captureBackground = resolveCaptureBackground(captureRoot);
        const darkMode = document.documentElement.classList.contains('dark');
        const preparedResources = await prepareCaptureResources(captureRoot);
        restoreResources = preparedResources.restore;

        const captureWidth = Math.ceil(captureRoot.scrollWidth || captureRoot.offsetWidth);
        const captureHeight = Math.ceil(captureRoot.scrollHeight || captureRoot.offsetHeight);
        const captureScale = calculateCaptureScale(captureWidth, captureHeight);
        captureRoot.setAttribute('data-screenshot-capture-root', 'true');
        const canvas = await html2canvas(captureRoot, {
            width: captureWidth,
            height: captureHeight,
            scale: captureScale,
            useCORS: true,
            imageTimeout: SCREENSHOT_RESOURCE_TIMEOUT,
            logging: false,
            backgroundColor: captureBackground,
            onclone: (clonedDocument) => {
                clonedDocument.documentElement.classList.toggle('dark', darkMode);
                const style = clonedDocument.createElement('style');
                style.textContent = '.content-renderer, .content-renderer * { animation: none !important; opacity: 1 !important; }';
                clonedDocument.head.appendChild(style);
                const clonedRoot = clonedDocument.querySelector('[data-screenshot-capture-root="true"]');
                if (clonedRoot) {
                    clonedRoot.style.backgroundColor = captureBackground;
                    clonedRoot.style.colorScheme = darkMode ? 'dark' : 'light';
                }
            },
        });

        const blob = await canvasToPngBlob(canvas);
        openScreenshotPreview(blob, preparedResources.failedImageCount, captureScale);
    } catch (error) {
        console.error('截图生成失败:', error);
        f7.toast.show({ text: screenshotErrorMessage(error), position: 'center' });
    } finally {
        if (captureRoot) captureRoot.removeAttribute('data-screenshot-capture-root');
        restoreResources?.();
        screenshotInProgress = false;
    }
};

// 原始知乎网页链接：answer / pin / article 各自的规范 URL，其余类型不支持
const originalUrl = () => {
    switch (type) {
        case 'answer': return `https://www.zhihu.com/answer/${id}`;
        case 'pin': return `https://www.zhihu.com/pin/${id}`;
        case 'article': return `https://zhuanlan.zhihu.com/p/${id}`;
        default: return null;
    }
};

const openOriginalLink = () => {
    const url = originalUrl();
    if (url) openLink(url);
    else f7.dialog.alert(`暂不支持该链接转换 (Type: ${type}, ID: ${id})`);
};

const copyOriginalLink = async () => {
    const url = originalUrl();
    if (!url) {
        f7.dialog.alert(`暂不支持该链接复制 (Type: ${type}, ID: ${id})`);
        return;
    }
    (await copyText(url))
        ? f7.toast.show({ text: '链接已复制到剪贴板', closeTimeout: 2000 })
        : f7.toast.show({ text: '复制失败' });
};

// 正文本地存档：分段与少量元数据落盘，配图整段不入档
const saveToLocal = () => {
    const res = saveContent({
        type,
        id,
        title: item.value?.title,
        authorName: item.value?.authorName,
        questionID: item.value?.questionID,
        segments: item.value?.structured_content,
    });
    if (res.ok) {
        f7.toast.show({ text: '已保存到本地，可从侧栏「本地」打开' });
        return;
    }
    f7.toast.show({
        text: res.reason === 'quota' ? '本地存储空间不足，请先清理旧存档' : '这条内容没有可保存的文字正文',
        position: 'center',
    });
};

const shareOriginalLink = async () => {
    const url = originalUrl();
    if (!url) {
        f7.dialog.alert(`暂不支持该链接分享 (Type: ${type}, ID: ${id})`);
        return;
    }
    const result = await shareText(url, item.value?.title);
    if (result === 'copied') f7.toast.show({ text: '链接已复制到剪贴板', closeTimeout: 2000 });
};

// 正文是分段结构，Markdown 直接由段生成
const copyMarkdown = async () => {
    const markdown = segmentsToMarkdown(item.value?.structured_content);
    if (!markdown) {
        f7.toast.show({ text: '正文为空，无法复制', closeTimeout: 2000 });
        return;
    }
    (await copyText(markdown))
        ? f7.toast.show({ text: '已复制 Markdown', closeTimeout: 2000 })
        : f7.toast.show({ text: '复制失败' });
};

// 页内查找：f7-searchbar 承载输入，命中高亮由下方 TreeWalker 逻辑负责
const showSearch = ref(false);
const searchbarRef = ref(null);
const contentRef = ref(null);
const searchQuery = ref('');
const searchIndex = ref(-1);
const searchHits = ref(0);
let searchMarks = [];

const contentRoot = () => contentRef.value?.$el;

const clearSearchMarks = () => {
    searchMarks.forEach((m) => {
        const parent = m.parentNode;
        if (parent) {
            parent.replaceChild(document.createTextNode(m.textContent), m);
            parent.normalize();
        }
    });
    searchMarks = [];
};

const goHit = (i) => {
    if (!searchMarks.length) return;
    if (searchIndex.value >= 0) searchMarks[searchIndex.value].classList.remove('search-hit-active');
    searchIndex.value = (i + searchMarks.length) % searchMarks.length;
    const mark = searchMarks[searchIndex.value];
    mark.classList.add('search-hit-active');
    mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
};

const runSearch = () => {
    clearSearchMarks();
    searchIndex.value = -1;
    searchHits.value = 0;
    const q = searchQuery.value.trim();
    const root = contentRoot();
    if (!q || !root) return;

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode: (n) => (n.parentNode.nodeName === 'MARK' || !n.nodeValue.trim()
            ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);

    const lower = q.toLowerCase();
    for (const node of textNodes) {
        const text = node.nodeValue;
        const lt = text.toLowerCase();
        let idx = lt.indexOf(lower);
        if (idx === -1) continue;
        const frag = document.createDocumentFragment();
        let last = 0;
        while (idx !== -1) {
            if (idx > last) frag.appendChild(document.createTextNode(text.slice(last, idx)));
            const mark = document.createElement('mark');
            mark.className = 'search-hit';
            mark.textContent = text.slice(idx, idx + q.length);
            frag.appendChild(mark);
            searchMarks.push(mark);
            last = idx + q.length;
            idx = lt.indexOf(lower, last);
        }
        if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
        node.parentNode.replaceChild(frag, node);
    }

    searchHits.value = searchMarks.length;
    if (searchHits.value) goHit(0);
};

const onSearchInput = debounce(runSearch, 200);

watch(searchQuery, onSearchInput);

const nextHit = () => goHit(searchIndex.value + 1);
const prevHit = () => goHit(searchIndex.value - 1);

const openSearch = () => {
    showSearch.value = true;
    nextTick(() => searchbarRef.value?.$el?.querySelector('input')?.focus());
};

const closeSearch = () => {
    showSearch.value = false;
    onSearchInput.cancel();
    searchQuery.value = '';
    clearSearchMarks();
    searchHits.value = 0;
    searchIndex.value = -1;
};

// 重新拉取前先清掉页内查找的高亮标记，避免旧引用指向被替换的 DOM
const refreshArticle = () => {
    closeSearch();
    fetchData();
};

// 标题双击回到顶部：滚动容器是正文区，导航栏自身不可滚
const scrollContentTop = () => {
    contentRef.value?.$el?.scrollTo({ top: 0, behavior: 'smooth' });
};

// 标题同时担「双击回顶」与「单击进问题页」：浏览器先派发两次 click 才给 dblclick，
// 所以单击延后一个双击窗口再执行，期间收到 dblclick 就作废。
// 监听只能绑在 f7-nav-title 上 —— f7-navbar 不透传属性，绑它身上的 dblclick 落不到 DOM。
let titleTapTimer = null;
const onTitleClick = () => {
    clearTimeout(titleTapTimer);
    titleTapTimer = setTimeout(() => { titleTapTimer = null; navTitleClick(); }, 260);
};
const onTitleDblClick = () => {
    clearTimeout(titleTapTimer);
    titleTapTimer = null;
    scrollContentTop();
};

onUnmounted(() => {
    onSearchInput.cancel();
    stopRestorePolling();
    if (historyEntry && readProgress > 0) {
        HistoryService.addRecord({ ...historyEntry, progress: readProgress });
    }
});

</script>

<template>
    <f7-page class="article-detail">
        <f7-navbar>
            <f7-nav-left>
                <f7-link icon-only @click="f7router.back()">
                    <f7-icon ios="f7:arrow_left" md="material:arrow_back" />
                </f7-link>
            </f7-nav-left>
            <f7-nav-title v-if="item" @click="onTitleClick" @dblclick="onTitleDblClick">{{ item.title }}</f7-nav-title>
            <f7-nav-right>
                <f7-link icon-only popover-open=".article-actions-popover">
                    <f7-icon ios="f7:ellipsis_circle" md="material:more_horiz" />
                </f7-link>
            </f7-nav-right>
        </f7-navbar>

        <!-- 页内查找条：作为 page 的固定元素排在导航栏下方，命中计数与上下翻用 inner-end 插槽 -->
        <f7-searchbar v-if="showSearch" ref="searchbarRef" custom-search class="inpage-search"
            v-model:value="searchQuery" placeholder="页内查找" :disable-button="false" clear-button
            @keyup.enter="nextHit" @keyup.esc="closeSearch">
            <template #inner-end>
                <span class="search-count">{{ searchHits ? `${searchIndex + 1}/${searchHits}` : '0/0' }}</span>
                <f7-link icon-only :class="{ disabled: !searchHits }" @click="prevHit">
                    <f7-icon ios="f7:chevron_up" md="material:keyboard_arrow_up" />
                </f7-link>
                <f7-link icon-only :class="{ disabled: !searchHits }" @click="nextHit">
                    <f7-icon ios="f7:chevron_down" md="material:keyboard_arrow_down" />
                </f7-link>
                <f7-link icon-only @click="closeSearch">
                    <f7-icon ios="f7:xmark" md="material:close" />
                </f7-link>
            </template>
        </f7-searchbar>

        <!-- Article Actions Popover -->
        <f7-popover class="article-actions-popover">
            <f7-list>
                <f7-list-item title="查找" link popover-close @click="openSearch" />
                <f7-list-item title="刷新" link popover-close @click="refreshArticle" />
                <f7-list-item title="分享" link popover-close @click="shareOriginalLink" />
                <f7-list-item title="打开原始知乎网页" link popover-close @click="openOriginalLink" />
                <f7-list-item title="复制原始知乎链接" link popover-close @click="copyOriginalLink" />
                <f7-list-item title="以图片形式保存" link popover-close @click="saveAsImage" />
                <f7-list-item title="保存到本地" link popover-close @click="saveToLocal" />
                <f7-list-item title="复制Markdown" link popover-close @click="copyMarkdown" />
                <f7-list-item title="举报" link popover-close
                    @click="$openLink(`https://www.zhihu.com/report?id=${id}&type=${type}&source=android&ab_signature=`)" />
            </f7-list>
        </f7-popover>

        <PageLoader v-if="loading" />

        <f7-page-content v-else-if="item" ref="contentRef" class="padding-bottom full-content"
            @scroll.passive="onContentScroll"
            @touchstart.passive="onGestureStart" @touchend.passive="onGestureEnd"
            @mousedown="onGestureStart" @mouseup="onGestureEnd">

            <div v-if="item.imageUrl" class="hero-image-container">
                <img :src="item.imageUrl" class="hero-image" />
                <div class="hero-gradient"></div>
            </div>

            <div class="content-wrapper">
                <f7-card class="author-card" @click="navigateToUser(item.authorId)">
                    <f7-card-content class="display-flex align-items-center padding">
                        <img :src="item.avatarUrl" class="card-avatar" />
                        <div class="card-info margin-left">
                            <div class="card-name">{{ item.authorName }}</div>
                            <div class="card-desc">知乎用户</div>
                        </div>
                    </f7-card-content>
                </f7-card>

                <!-- TOC Card -->
                <f7-card v-if="tocItems.length > 0" class="toc-card premium-toc-card">
                    <f7-card-content>
                        <div class="toc-header-wrapper display-flex align-items-center margin-bottom">
                            <f7-icon f7="list_bullet_indent" size="20" class="margin-right-half color-theme" />
                            <div class="toc-header">文章目录</div>
                        </div>
                        <div class="toc-list-container">
                            <div v-for="toc in visibleTocItems" :key="toc.id" class="toc-item-row"
                                :class="[`level-${toc.level || 1}`]" @click="scrollToHeading(toc.id)">
                                <div class="toc-dot"></div>
                                <div class="toc-text">{{ toc.text }}</div>
                            </div>
                        </div>
                        <div v-if="tocItems.length > 3" class="toc-toggle-premium"
                            @click="isTocExpanded = !isTocExpanded">
                            <span>{{ isTocExpanded ? '收起目录' : `展开全部 ${tocItems.length} 个章节` }}</span>
                            <f7-icon :f7="isTocExpanded ? 'chevron_up' : 'chevron_down'" size="14" />
                        </div>
                    </f7-card-content>
                </f7-card>

                <ContentRenderer :segments="item.structured_content" :source-html="item.content" @imageClick="handleImageClick" />

                <div v-if="imageList.length > 0" class="image-gallery margin-top">
                    <swiper-container pagination>
                        <swiper-slide v-for="(img, index) in imageList" :key="index">
                            <img :src="img.url" style="width:100%; object-fit:contain; cursor: pointer;"
                                @click="handleGalleryImageClick(index)" />
                        </swiper-slide>
                    </swiper-container>
                </div>
            </div>
        </f7-page-content>

        <div v-if="item" class="bottom-float-container">
            <div class="float-bar">
                <div class="action-group" @click="toggleVote" :class="{ 'active-primary': item.isUpvoted === true }">
                    <f7-link icon-only>
                        <f7-icon :ios="item.isUpvoted === true ? 'f7:hand_thumbsup_fill' : 'f7:hand_thumbsup'"
                            :md="item.isUpvoted === true ? 'material:thumb_up' : 'material:thumb_up_off_alt'"
                            size="18" />
                    </f7-link>
                    <span class="action-count">{{ formatCount(item.metrics.votes) }}</span>
                </div>

                <div class="vertical-divider"></div>

                <div class="action-group" @click="toggleLike" :class="{ 'active-primary': item.isLiked }">
                    <f7-link icon-only>
                        <f7-icon :ios="item.isLiked ? 'f7:heart_fill' : 'f7:heart'"
                            :md="item.isLiked ? 'material:favorite' : 'material:favorite_border'" size="18" />
                    </f7-link>
                    <span class="action-count">{{ formatCount(item.metrics.likes) }}</span>
                </div>

                <div class="vertical-divider"></div>

                <div class="action-group" @click="toggleFavorite" :class="{ 'active-primary': item.isFavorited }">
                    <f7-link icon-only>
                        <f7-icon :ios="item.isFavorited ? 'f7:bookmark_fill' : 'f7:bookmark'"
                            :md="item.isFavorited ? 'material:bookmark' : 'material:bookmark_border'" size="18" />
                    </f7-link>
                    <span class="action-count">{{ formatCount(item.metrics.favorites) }}</span>
                </div>

                <div class="vertical-divider"></div>

                <div class="action-group" @click="showComments = true">
                    <f7-link icon-only>
                        <f7-icon ios="f7:bubble_left" md="material:chat_bubble_outline" size="18" />
                    </f7-link>
                    <span class="action-count">{{ formatCount(item.metrics.comments) }}</span>
                </div>
            </div>
        </div>

        <div v-if="showFloatScroll" class="float-scroll-buttons">
            <f7-link icon-only @click="scrollByViewport(-1)">
                <f7-icon ios="f7:chevron_up" md="material:keyboard_arrow_up" size="28" color="primary" />
            </f7-link>
            <f7-link icon-only @click="scrollByViewport(1)">
                <f7-icon ios="f7:chevron_down" md="material:keyboard_arrow_down" size="28" color="primary" />
            </f7-link>
        </div>

        <CommentsSheet v-model="showComments" :resourceId="id" :resourceType="type" :f7router="f7router" />
        <CollectionSheet v-model="showCollection" :contentId="id" :contentType="type" @success="onCollectionSuccess" />

        <f7-popover class="toc-popover" :opened="showToc" @popover:closed="showToc = false">
            <div class="display-flex justify-content-between align-items-center padding">
                <div class="font-weight-bold">目录</div>
            </div>
            <f7-list>
                <f7-list-item v-for="toc in tocItems" :key="toc.id" :title="toc.text" link
                    @click="scrollToHeading(toc.id)" popover-close />
            </f7-list>
        </f7-popover>

        <PhotoBrowser ref="photoBrowserRef" />
    </f7-page>
</template>

<style scoped>
.article-detail {
    height: 100%;
    position: relative;
    display: flex;
    flex-direction: column;
}

.toc-popover {
    position: absolute;
    top: 70px;
    right: 16px;
    width: 200px;
    max-height: 50vh;
    z-index: 100;
    display: flex;
    flex-direction: column;
    padding: 0;
}

.toc-list {
    flex: 1;
    overflow-y: auto;
}

.toc-item {
    padding: 8px 16px;
    font-size: 0.875rem;
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.hero-image-container {
    position: relative;
    width: 100%;
    height: 250px;
}

.hero-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.hero-gradient {
    position: absolute;
    inset: 0;
    opacity: 0.8;
}

.content-wrapper {
    padding: 24px;
    padding-bottom: 120px;
    max-width: 800px;
    margin: auto;
}

.article-content :deep(img) {
    max-width: 100%;
    border-radius: 8px;
    margin: 16px 0;
}

.article-content :deep(p) {
    margin-bottom: 16px;
}

.author-card {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px;
    border-radius: 16px;
    max-width: none;
}

.card-avatar {
    width: 48px;
    height: 48px;
    border-radius: 50%;
}

.card-info {
    flex: 1;
}

.card-name {
    font-weight: bold;
    font-size: 1rem;
}

.card-desc {
    font-size: 0.875rem;
}

.bottom-float-container {
    position: relative;
    display: flex;
    justify-content: center;
    width: 100%;
    margin: 20px 0 24px;
    pointer-events: none;
    z-index: 20;
}

/* 逐屏滚动按钮：贴在底栏上方右侧，避开正文与底栏的点击 */
.float-scroll-buttons {
    position: absolute;
    right: 12px;
    bottom: 88px;
    z-index: 500;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 4px 2px;
    border-radius: 24px;
    background-color: var(--f7-card-bg-color);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
    opacity: 0.9;
}

.float-bar {
    pointer-events: auto;
    display: flex;
    align-items: center;
    padding: 4px 8px;
    border-radius: 28px;
    /* 半透明底跟着页面背景走；前一行是不认 color-mix 的内核兜底 */
    background: var(--f7-page-bg-color);
    background: color-mix(in srgb, var(--f7-page-bg-color) 78%, transparent);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border: 1px solid rgba(var(--f7-theme-color-rgb), 0.15);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
    gap: 2px;
    transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.float-bar:hover {
    transform: translateY(-2px);
}

.action-group {
    display: flex;
    align-items: center;
    padding: 6px 12px;
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    color: var(--f7-text-color);
    position: relative;
    overflow: hidden;
}


.action-group:active {
    background: rgba(var(--f7-theme-color-rgb), 0.1);
    transform: scale(0.92);
}

.action-group.active-primary {
    color: var(--f7-theme-color);
    background: rgba(var(--f7-theme-color-rgb), 0.08);
}

.action-count {
    font-size: 0.85rem;
    font-weight: 700;
    margin-left: 6px;
    min-width: 24px;
}

.vertical-divider {
    width: 1px;
    height: 18px;
    background: var(--app-divider-color);
    margin: 0 4px;
}

.toc-card.premium-toc-card {
    border-radius: 16px;
    background: rgba(var(--f7-theme-color-rgb), 0.02);
    border: 1px solid rgba(var(--f7-theme-color-rgb), 0.08);
    box-shadow: none;
    margin: 16px 0 32px 0;
}

.toc-header {
    font-weight: 800;
    font-size: 1.1rem;
    color: var(--f7-theme-color);
}

.toc-list-container {
    position: relative;
    padding-left: 12px;
}

.toc-list-container::before {
    content: '';
    position: absolute;
    left: 4px;
    top: 8px;
    bottom: 8px;
    width: 2px;
    background: rgba(var(--f7-theme-color-rgb), 0.1);
    border-radius: 2px;
}

.toc-item-row {
    display: flex;
    align-items: center;
    padding: 10px 0;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
}

.toc-item-row:active {
    opacity: 0.6;
    transform: translateX(4px);
}

.toc-dot {
    width: 6px;
    height: 6px;
    background: rgba(var(--f7-theme-color-rgb), 0.3);
    border-radius: 50%;
    margin-right: 12px;
    flex-shrink: 0;
    transition: all 0.2s;
}

.toc-item-row:hover .toc-dot {
    background: var(--f7-theme-color);
    transform: scale(1.3);
}

.toc-text {
    font-size: 15px;
    color: var(--f7-text-color);
    line-height: 1.4;
    font-weight: 500;
}

.toc-item-row.level-2 {
    margin-left: 20px;
}

.toc-item-row.level-3 {
    margin-left: 40px;
}

.toc-toggle-premium {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding-top: 12px;
    margin-top: 8px;
    font-size: 13px;
    font-weight: 600;
    color: var(--f7-theme-color);
    cursor: pointer;
    border-top: 1px dashed rgba(var(--f7-theme-color-rgb), 0.1);
}

.image-gallery {
    margin-top: 32px;
    border-radius: 12px;
    overflow: hidden;
}

s-carousel-item {
    background-size: cover;
    background-position: center;
}

.inpage-search .search-count {
    font-size: 12px;
    color: var(--app-sub-text);
    min-width: 44px;
    text-align: center;
    flex-shrink: 0;
}

.inpage-search .link.disabled {
    opacity: 0.35;
    pointer-events: none;
}

:deep(mark.search-hit) {
    background: rgba(255, 205, 0, 0.4);
    color: inherit;
    padding: 0 1px;
    border-radius: 2px;
}

:deep(mark.search-hit-active) {
    background: var(--f7-theme-color);
    color: #fff;
}
</style>
