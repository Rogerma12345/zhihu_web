// tests/unit/list-views.test.js
// 核对两个列表页面的 Tab 接口与请求选项。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { runInNewContext } from 'node:vm';
import { parse, compileScript } from '@vue/compiler-sfc';

function scriptOf(file) {
    const source = readFileSync(fileURLToPath(new URL(file, import.meta.url)), 'utf8');
    const { descriptor } = parse(source);
    const declarations = compileScript(descriptor, { id: file }).scriptSetupAst
        .filter((item) => item.type === 'VariableDeclaration')
        .flatMap((item) => item.declarations);
    const expression = (node) => descriptor.scriptSetup.content.slice(node.start, node.end);
    const tabs = declarations.find((item) => item.id.name === 'tabs');
    const pagedList = declarations.find((item) => item.init?.callee?.name === 'useTabbedPagedList');
    const fetch = pagedList.init.arguments[0].properties.find((item) => item.key.name === 'fetch');
    return { tabs: expression(tabs.init), fetch: expression(fetch.value) };
}

function inspect(file, values) {
    const expressions = scriptOf(file);
    const tabs = runInNewContext(expressions.tabs, {
        computed: (get) => get(),
        encodeURIComponent,
        ...values,
    });
    const calls = [];
    const fetch = runInNewContext(`(${expressions.fetch})`, {
        tabFor: (id) => tabs.find((tab) => tab.id === id),
        $http: { get: (url, options) => { calls.push({ url, options }); } },
    });
    for (const tab of tabs) fetch(tab.id, undefined);
    return { tabs, calls };
}

test('关注列表七个 Tab 均使用内部用户 ID 和 Android API', () => {
    const { tabs, calls } = inspect('../../src/pages/following/FollowingView.vue', {
        userId: { value: 'id 42' },
    });
    assert.deepEqual(Array.from(tabs, (tab) => tab.id), [
        'questions', 'collections', 'topics', 'columns', 'users', 'specials', 'roundtables'
    ]);
    assert.deepEqual(calls.map((call) => call.url), [
        'following_questions', 'following_collections', 'following_topics',
        'following_columns', 'followees', 'following_news_specials', 'following_roundtables'
    ].map((path) => `https://api.zhihu.com/people/id%2042/${path}?limit=20`));
    assert.ok(calls.every((call) => !call.options.requestMode));
});

test('收藏夹在自己主页和其他用户主页使用相应 ID', () => {
    const own = inspect('../../src/pages/collection/CollectionsView.vue', {
        effectiveUserId: { value: 'my-id' },
        isOwnProfile: { value: true },
    });
    assert.deepEqual(own.calls.map((call) => call.url), [
        'https://api.zhihu.com/people/my-id/collections_v2?limit=20',
        'https://api.zhihu.com/people/my-id/following_collections?limit=20',
        'https://api.zhihu.com/explore/collections?limit=20',
    ]);
    assert.deepEqual(own.calls.map((call) => call.options.isWWW), [true, true, false]);

    const other = inspect('../../src/pages/collection/CollectionsView.vue', {
        effectiveUserId: { value: 'other-id' },
        isOwnProfile: { value: false },
    });
    assert.equal(other.tabs.length, 2);
    assert.ok(other.calls.every((call) => call.url.includes('/people/other-id/')));
});
