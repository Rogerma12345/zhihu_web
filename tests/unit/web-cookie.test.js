import { test } from 'node:test';
import assert from 'node:assert/strict';

import { normalizeWebCookies, extractWebCookies } from '@/services/web-cookie.js';

test('只提取 d_c0 与 z_c0，保留值中的等号', () => {
    assert.deepEqual(extractWebCookies('Cookie: session=ignored; d_c0=abc==; z_c0=other=; lang=zh'), {
        d_c0: 'abc==', z_c0: 'other='
    });
    assert.deepEqual(normalizeWebCookies({ d_c0: ' value ', extra: 'ignored' }), { d_c0: 'value' });
});

test('拒绝包含换行、分号或控制字符的手动凭证', () => {
    assert.throws(() => normalizeWebCookies({ d_c0: 'value\r\nother:bad' }), /格式无效/);
    assert.throws(() => normalizeWebCookies({ z_c0: 'value;other=1' }), /格式无效/);
    assert.throws(() => normalizeWebCookies({ d_c0: 'a'.repeat(4097) }), /格式无效/);
    assert.deepEqual(normalizeWebCookies({}), {});
});
