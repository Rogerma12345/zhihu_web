// src/services/web-cookie.js
// 手动网页凭证的字段校验与 Cookie 字符串提取。

const WEB_COOKIE_NAMES = ['d_c0', 'z_c0'];

/** 只保留网页鉴权使用的 Cookie 字段。 */
export function normalizeWebCookies(values) {
    const result = {};
    for (const name of WEB_COOKIE_NAMES) {
        const value = values?.[name];
        if (value == null || value === '') continue;
        if (typeof value !== 'string' || value.length > 4096 || /[;\x00-\x1f\x7f]/.test(value)) {
            throw new Error(`${name} 格式无效`);
        }
        const trimmed = value.trim();
        if (trimmed) result[name] = trimmed;
    }
    return result;
}

/** 从完整的 Cookie 请求头中提取可配置字段。 */
export function extractWebCookies(text) {
    const cookies = {};
    const header = String(text || '').trim().replace(/^cookie\s*:/i, '');
    for (const part of header.split(';')) {
        const index = part.indexOf('=');
        if (index < 0) continue;
        const name = part.slice(0, index).trim();
        if (WEB_COOKIE_NAMES.includes(name)) cookies[name] = part.slice(index + 1).trim();
    }
    return normalizeWebCookies(cookies);
}
