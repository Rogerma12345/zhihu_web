import { test } from 'node:test';
import assert from 'node:assert/strict';

import { parseZhihuUrl, looksLikeZhihuUrl } from '@/utils/url.js';
import { resolveCardRoute } from '@/core/navigation.js';

const cases = [
    ['https://www.zhihu.com/question/123/answer/456', { type: 'answer', id: '456' }],
    ['https://www.zhihu.com/question/123/answers/456', { type: 'answer', id: '456' }],
    ['https://www.zhihu.com/answer/456', { type: 'answer', id: '456' }],
    ['https://www.zhihu.com/question/123', { type: 'question', id: '123' }],
    ['https://www.zhihu.com/aria/question/123/answer/456', { type: 'answer', id: '456' }],
    ['https://www.zhihu.com/tardis/sogou/ans/456', { type: 'answer', id: '456' }],
    ['https://www.zhihu.com/tardis/zm/art/789', { type: 'article', id: '789' }],
    ['https://www.zhihu.com/tardis/bd/qus/123', { type: 'question', id: '123' }],
    ['https://zhuanlan.zhihu.com/p/789', { type: 'article', id: '789' }],
    ['https://www.zhihu.com/appview/p/789', { type: 'article', id: '789' }],
    ['https://www.zhihu.com/pin/321', { type: 'pin', id: '321' }],
    ['https://www.zhihu.com/zvideo/654', { type: 'zvideo', id: '654' }],
    ['https://www.zhihu.com/collection/246', { type: 'collection', id: '246' }],
    ['https://www.zhihu.com/people/some-token', { type: 'people', id: 'some-token' }],
    ['https://www.zhihu.com/org/company-id', { type: 'people', id: 'company-id' }],
    ['https://www.zhihu.com/people/user-123/answers', { type: 'people-tab', id: 'user-123', tab: 'answer' }],
    ['https://www.zhihu.com/people/user-123/asks', { type: 'people-tab', id: 'user-123', tab: 'question' }],
    ['https://www.zhihu.com/people/user-123/columns', { type: 'people-tab', id: 'user-123', tab: 'column' }],
    ['https://www.zhihu.com/people/user-123/collections', { type: 'people-collections', id: 'user-123', tab: 'mine' }],
    ['https://www.zhihu.com/topic/19550883', { type: 'topic', id: '19550883' }],
    ['https://www.zhihu.com/column/c_123', { type: 'column', id: 'c_123' }],
    ['https://zhuanlan.zhihu.com/my-column', { type: 'column', id: 'my-column' }],
    ['https://www.zhihu.com/column', { type: 'browser', id: 'https://www.zhihu.com/column' }],
    ['https://www.zhihu.com/roundtable/12', { type: 'roundtable', id: '12' }],
    ['https://www.zhihu.com/special/12', { type: 'special', id: '12' }],
    ['https://www.zhihu.com/theater?drama_id=99', { type: 'drama', id: '99' }],
];

for (const [url, expected] of cases) {
    test(`解析 ${url.replace('https://', '')}`, async () => {
        assert.deepEqual(await parseZhihuUrl(url), expected);
    });
}

// 知乎 App 分享出来的深链：非特殊协议下首段被 WHATWG URL 放进 hostname，
// 归一为 https 后必须与网页链接得到同一结果
const deepLinks = [
    ['zhihu://answers/456', { type: 'answer', id: '456' }],
    ['zhihu://pins/321', { type: 'pin', id: '321' }],
    ['zhihu://topics/19550883', { type: 'topic', id: '19550883' }],
    ['zhihu://articles/789', { type: 'article', id: '789' }],
    ['zhihu://people/some-token', { type: 'people', id: 'some-token' }],
    ['zhihu://columns/abc', { type: 'column', id: 'abc' }],
];

for (const [url, expected] of deepLinks) {
    test(`深链 ${url}`, async () => {
        assert.deepEqual(await parseZhihuUrl(url), expected);
    });
}

test('/oia/ 中转链接剥段重试原 host', async () => {
    assert.deepEqual(
        await parseZhihuUrl('https://www.zhihu.com/oia/pin/321'),
        { type: 'pin', id: '321' }
    );
});

test('粘贴文本、末尾标点与路径尾斜杠可正常识别', async () => {
    assert.deepEqual(
        await parseZhihuUrl('知乎回答 https://www.zhihu.com/question/123/answer/456?utm=share。'),
        { type: 'answer', id: '456' }
    );
    assert.deepEqual(await parseZhihuUrl('www.zhihu.com/collection/246/'), { type: 'collection', id: '246' });
    assert.equal(looksLikeZhihuUrl('打开 https://www.zhihu.com/column'), true);
});

test('项目类链接不匹配任何站内页面', async () => {
    for (const path of ['/project/detail/6', '/project-square', '/people/user-123/projects']) {
        assert.equal((await parseZhihuUrl(`https://www.zhihu.com${path}`)).type, 'error');
    }
});

test('signin 链接交回站内登录，并带上 next', async () => {
    assert.deepEqual(
        await parseZhihuUrl('https://www.zhihu.com/signin?next=%2Fquestion%2F123'),
        { type: 'login', id: '/question/123' }
    );
});

test('非知乎域名与未知路径都不猜类型', async () => {
    assert.deepEqual(await parseZhihuUrl('https://example.com/p/1'), { type: 'browser', id: 'https://example.com/p/1' });
    assert.equal((await parseZhihuUrl('https://www.zhihu.com/nonsense')).type, 'error');
    assert.equal((await parseZhihuUrl('不是链接')).type, 'error');
});

test('resolveCardRoute 的类型→路由表与解析结果对得上', () => {
    assert.deepEqual(resolveCardRoute({ type: 'question', id: '1' }), { kind: 'route', path: '/question/1' });
    assert.deepEqual(resolveCardRoute({ type: 'people', id: 'u1' }), { kind: 'route', path: '/user/u1' });
    assert.deepEqual(resolveCardRoute({ type: 'people-tab', id: 'u1', tab: 'answer' }),
        { kind: 'route', path: '/user/u1/answer' });
    assert.deepEqual(resolveCardRoute({ type: 'collection', id: '22' }),
        { kind: 'route', path: '/collection/22' });
    assert.deepEqual(resolveCardRoute({ type: 'zvideo', id: '9' }), { kind: 'route', path: '/video/9' });
    assert.deepEqual(resolveCardRoute({ type: 'login', id: '' }), { kind: 'login' });
    assert.equal(resolveCardRoute({ type: 'drama', id: '3' }).url, 'https://www.zhihu.com/theater/3');
    assert.deepEqual(resolveCardRoute({ type: 'answer', id: '5' }), { kind: 'route', path: '/article/answer/5' });
});
