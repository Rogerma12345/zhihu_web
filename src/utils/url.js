// src/utils/url.js
// 知乎链接解析：将内容链接归一为站内卡片类型。
import $http from '@/services/http.js';

async function fetchVideoUrl(videoId) {
    try {
        const res = await $http.get(`https://lens.zhihu.com/api/v4/videos/${videoId}`);
        const videoLink = res.playlist?.SD?.play_url
            || res.playlist?.LD?.play_url
            || res.playlist?.HD?.play_url;
        return videoLink
            ? { type: 'browser', id: videoLink }
            : { type: 'error', message: '无法获取视频链接' };
    } catch {
        return { type: 'error', message: '网络请求失败' };
    }
}

/** 判断输入中是否包含知乎网页或 App 链接。 */
export function looksLikeZhihuUrl(text) {
    return /(?:https?:\/\/)?(?:www\.|zhuanlan\.)?zhihu\.com(?:\/|\?|$)|zhihu:\/\//i.test(String(text || ''));
}

function extractUrl(text) {
    const trimmed = String(text || '').trim();
    const match = trimmed.match(/(?:https?:\/\/|zhihu:\/\/)[^\s<>"“”]+/i);
    const url = match ? match[0].replace(/[.,。，！!；;）)]+$/, '') : trimmed;
    return /^(?:www\.|zhuanlan\.)?zhihu\.com(?:\/|\?|$)/i.test(url)
        ? `https://${url}` : url;
}

const PROFILE_TABS = {
    answers: 'answer',
    asks: 'question',
    questions: 'question',
    posts: 'article',
    articles: 'article',
    zvideos: 'zvideo',
    pins: 'pin',
    columns: 'column',
    activities: 'activities',
};

const DEEP_LINK_TYPES = {
    answers: 'answer',
    questions: 'question',
    articles: 'article',
    pins: 'pin',
    topics: 'topic',
    columns: 'column',
    collections: 'collection',
    zvideos: 'zvideo',
    people: 'people',
};

/** 解析粘贴或分享的知乎 URL；未知知乎路径返回错误，不猜测内容类型。 */
export async function parseZhihuUrl(input) {
    const url = extractUrl(input);
    try {
        const u = new URL(url);
        const { protocol, hostname, search, searchParams } = u;
        if (protocol === 'zhihu:') {
            const kind = DEEP_LINK_TYPES[hostname] || hostname;
            return parseZhihuUrl(`https://www.zhihu.com/${kind}${u.pathname}${search}`);
        }
        if (!['http:', 'https:'].includes(protocol)) {
            return { type: 'error', message: '不支持的链接协议' };
        }
        if (!['zhihu.com', 'www.zhihu.com', 'zhuanlan.zhihu.com'].includes(hostname)) {
            return { type: 'browser', id: url };
        }

        const path = u.pathname.replace(/\/+$/, '') || '/';
        let match;

        if (path.startsWith('/oia/')) {
            return parseZhihuUrl(`${u.origin}${path.slice(4)}${search}`);
        }
        if ((match = path.match(/^\/tardis\/[^/]+\/(ans|art|qus)\/(\d+)$/))) {
            const type = { ans: 'answer', art: 'article', qus: 'question' }[match[1]];
            return { type, id: match[2] };
        }
        if ((match = path.match(/^\/(?:aria\/)?question\/\d+\/answers?\/(\d+)$/))) {
            return { type: 'answer', id: match[1] };
        }
        if ((match = path.match(/^\/answer\/(\d+)$/))) return { type: 'answer', id: match[1] };
        if ((match = path.match(/^\/question\/(\d+)$/))) return { type: 'question', id: match[1] };
        if ((match = path.match(/^\/(?:p|appview\/p|article)\/(\d+)$/))) {
            return { type: 'article', id: match[1] };
        }
        if ((match = path.match(/^\/pin\/(\d+)$/))) return { type: 'pin', id: match[1] };
        if ((match = path.match(/^\/video\/(\d+)$/))) return fetchVideoUrl(match[1]);
        if ((match = path.match(/^\/zvideo\/(\d+)$/))) return { type: 'zvideo', id: match[1] };
        if ((match = path.match(/^\/collection\/(\d+)$/))) return { type: 'collection', id: match[1] };

        if ((match = path.match(/^\/(?:people|org)\/([^/]+)(?:\/([^/]+))?$/))) {
            const userId = decodeURIComponent(match[1]);
            const section = match[2];
            if (!section) return { type: 'people', id: userId };
            if (section === 'collections' || section === 'following-collections') {
                return { type: 'people-collections', id: userId, tab: section === 'collections' ? 'mine' : 'following' };
            }
            if (PROFILE_TABS[section]) return { type: 'people-tab', id: userId, tab: PROFILE_TABS[section] };
        }
        if ((match = path.match(/^\/topics?\/(\d+)$/))) return { type: 'topic', id: match[1] };
        if ((match = path.match(/^\/column\/([^/]+)$/))) {
            return { type: 'column', id: decodeURIComponent(match[1]) };
        }
        if (hostname === 'zhuanlan.zhihu.com' && (match = path.match(/^\/([^/]+)$/))) {
            return { type: 'column', id: decodeURIComponent(match[1]) };
        }
        if (path === '/column' || (hostname === 'zhuanlan.zhihu.com' && path === '/')) {
            return { type: 'browser', id: url };
        }
        if ((match = path.match(/^\/roundtable\/([^/]+)$/))) return { type: 'roundtable', id: match[1] };
        if ((match = path.match(/^\/special\/([^/]+)$/))) return { type: 'special', id: match[1] };
        if (path === '/theater') {
            const dramaId = searchParams.get('drama_id');
            return dramaId ? { type: 'drama', id: dramaId } : { type: 'browser', id: url };
        }
        if (path.startsWith('/signin')) return { type: 'login', id: searchParams.get('next') || '' };
        return { type: 'error', message: '暂不支持的知乎链接' };
    } catch {
        return { type: 'error', message: '无效链接' };
    }
}
