import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const readSource = (path) => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8');

test('Fork 保留重构前的搜索、建议与热搜请求链路', () => {
    const page = readSource('src/pages/search/SearchPage.vue');
    const module = readSource('src/services/zhihu/module.js');

    assert.match(page, /https:\/\/api\.zhihu\.com\/search_v3\?/);
    assert.doesNotMatch(page, /https:\/\/www\.zhihu\.com\/api\/v4\/search_v3\?/);
    assert.match(page, /https:\/\/www\.zhihu\.com\/api\/v4\/search\/suggest\?q=/);
    assert.match(page, /https:\/\/api\.zhihu\.com\/search\/hot_search/);
    assert.doesNotMatch(page, /requestMode:\s*['"]web['"]/);
    assert.match(page, /legacySearchRequest:\s*true/);
    assert.match(module, /finalCookie\s*\|\|\s*legacySearchRequest/);
});

test('Fork 保留回车单次提交、搜索错误状态与 Google 默认搜索', () => {
    const page = readSource('src/pages/search/SearchPage.vue');
    const transport = readSource('src/services/zhihu/transport.js');
    const settings = readSource('src/core/settings.js');

    assert.match(page, /event\.stopImmediatePropagation\(\)/);
    assert.match(page, /event\.isComposing/);
    assert.match(page, /searchErrors\[tab\.id\]/);
    assert.match(transport, /err\.apiCode\s*=/);
    assert.match(settings, /https:\/\/www\.google\.com\/search\?q=site%3Azhihu\.com%20/);
    assert.match(settings, /saved\.searchEngineUrl\s*===\s*OLD_BING_DEFAULT/);
});
