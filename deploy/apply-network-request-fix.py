from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
TEMPLATES = ROOT / "deploy" / "fork-templates"


def read(rel):
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"missing file: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel, text):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_once(text, old, new, label):
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_zhihu_module():
    rel = "src/api/utils/zhihu-module.js"
    text = read(rel)

    import_line = "import { signWebRequest } from './zse96-web.js';"
    if import_line not in text:
        text = replace_once(
            text,
            "import { ensureGuestCredential } from './guest-request.js';",
            "import { ensureGuestCredential } from './guest-request.js';\n" + import_line,
            rel + " web signer import",
        )

    helpers = '''\nfunction normalizeZhihuUrl(url) {
    if (typeof url !== 'string') return url;
    return url
        .replace(/^http:\\/\\/api\\.zhihu\\.com(?=\\/|$)/i, 'https://api.zhihu.com')
        .replace(/^http:\\/\\/www\\.zhihu\\.com(?=\\/|$)/i, 'https://www.zhihu.com');
}

function getCookieValue(cookieString, name) {
    if (!cookieString) return '';
    const prefix = `${name}=`;
    const entry = cookieString
        .split(';')
        .map(item => item.trim())
        .find(item => item.startsWith(prefix));
    return entry ? entry.slice(prefix.length) : '';
}
'''
    if "function normalizeZhihuUrl(url)" not in text:
        text = replace_once(text, "\nclass ZhihuRequest {", helpers + "\nclass ZhihuRequest {", rel + " helpers")

    text = text.replace("        console.log('UpdateLoginData:', loginData);\n", "")
    text = text.replace("        loginData = loginData.guest || loginData;", "        loginData = loginData?.guest || loginData || {};")

    old_cookie = '''        const cookieData = { ...(loginData.cookie || {}) };
        if (loginData.udid) {
            cookieData.d_c0 = loginData.udid;
        }
        this.cookie = Object.entries(cookieData)'''
    new_cookie = '''        const cookieData = { ...(loginData.cookie || {}) };
        if (!cookieData.d_c0 && loginData.d_c0) {
            cookieData.d_c0 = loginData.d_c0;
        }
        this.cookieData = cookieData;
        this.cookie = Object.entries(cookieData)'''
    if new_cookie not in text:
        text = replace_once(text, old_cookie, new_cookie, rel + " preserve d_c0")

    reset_zst = '''        this.zst81 = undefined;
        this.zst82 = undefined;
        if (Array.isArray(zsts) && zsts.length > 0) {'''
    if reset_zst not in text:
        text = replace_once(
            text,
            "        if (Array.isArray(zsts) && zsts.length > 0) {",
            reset_zst,
            rel + " zst reset",
        )

    web_headers = '''        const browserUserAgent = typeof navigator !== 'undefined'
            ? navigator.userAgent
            : 'Mozilla/5.0';
        this.webDefaultHeaders = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": browserUserAgent,
            "Referer": "https://www.zhihu.com/",
            ...(this.cookie && { "Cookie": this.cookie }),
            ...defaultHeaders,
        };
'''
    if "this.webDefaultHeaders = {" not in text:
        text = replace_once(
            text,
            "        console.log('Login data updated');",
            web_headers + "\n        console.log('Login data updated');",
            rel + " web headers",
        )

    request_method = '''    async request(method, url, data = "", {
        headers = {},
        encryptBody = true,
        isWWW = false,
        encryptHead = false,
        requireWebSignature = false,
        requestMode = null,
    } = {}) {
        method = method.toUpperCase();
        const isGet = method === 'GET';
        url = normalizeZhihuUrl(url);

        const isWebRequest = requestMode === 'web';
        let baseDefaultHeaders = this.defaultHeaders;
        if (isWebRequest) {
            baseDefaultHeaders = this.webDefaultHeaders;
        } else if (isWWW) {
            baseDefaultHeaders = this.commonDefaultHeaders;
        }

        const incomingCookie = headers.Cookie || headers.cookie;
        const instanceCookie = baseDefaultHeaders.Cookie || "";

        let finalCookie = "";
        if (instanceCookie || incomingCookie) {
            const cookieMap = {};
            if (instanceCookie) {
                instanceCookie.split(';').forEach(cookie => {
                    const [name, ...valueParts] = cookie.trim().split('=');
                    if (name) {
                        cookieMap[name] = valueParts.join('=');
                    }
                });
            }
            if (incomingCookie) {
                incomingCookie.split(';').forEach(cookie => {
                    const [name, ...valueParts] = cookie.trim().split('=');
                    if (name) {
                        cookieMap[name] = valueParts.join('=');
                    }
                });
            }

            finalCookie = Object.entries(cookieMap)
                .filter(([_, value]) => value)
                .map(([name, value]) => `${name}=${value}`)
                .join('; ');
        }

        let body = null;
        if (!isGet && data) {
            body = isWebRequest
                ? data
                : (encryptBody ? this.encryptData(data, false) : data);
        }

        const requestHeaders = {
            ...baseDefaultHeaders,
            ...headers,
        };
        delete requestHeaders.Cookie;
        delete requestHeaders.cookie;
        if (finalCookie) {
            requestHeaders.Cookie = finalCookie;
        }

        if (isWebRequest) {
            delete requestHeaders.Authorization;
            delete requestHeaders.authorization;
            delete requestHeaders['x-ms-id'];
            delete requestHeaders['x-udid'];
            delete requestHeaders['X-ZST-81'];
            delete requestHeaders['X-ZST-82'];
            delete requestHeaders['x-Zse-93'];
            delete requestHeaders['x-Zse-96'];
            delete requestHeaders['x-zse-93'];
            delete requestHeaders['x-zse-96'];

            const dC0 = getCookieValue(finalCookie, 'd_c0');
            if (dC0) {
                const signature = signWebRequest(url, dC0, isGet ? null : body);
                requestHeaders['x-zse-93'] = signature.zse93;
                requestHeaders['x-zse-96'] = signature.zse96;
                requestHeaders['x-requested-with'] = 'fetch';
            } else if (requireWebSignature) {
                throw new Error('Web 请求缺少有效 d_c0，无法发送需要签名的请求');
            }
        } else if (isGet || encryptHead || !data) {
            requestHeaders["x-Zse-96"] = `1.0_${this.encryptData(url)}`;
        }

        if (!isGet && data && !requestHeaders["Content-Type"]) {
            requestHeaders["Content-Type"] = isWebRequest
                ? "application/json"
                : "application/x-www-form-urlencoded";
        }

        const fetchOptions = {
            headers: requestHeaders,
        };

        switch (method) {
            case 'GET':
                return unifiedFetch.get(url, fetchOptions);
            case 'POST':
                return unifiedFetch.post(url, body, fetchOptions);
            case 'PUT':
                return unifiedFetch.put(url, body, fetchOptions);
            case 'PATCH':
                return unifiedFetch.patch(url, body, fetchOptions);
            case 'DELETE':
                return unifiedFetch.delete(url, fetchOptions);
            default:
                throw new Error(`Unsupported method: ${method}`);
        }
    }
'''
    pattern = r"    async request\(method, url, data = \"\", \{.*?\n    \}\n\n    get\(url, options\)"
    if "requireWebSignature = false" not in text:
        updated, count = re.subn(pattern, request_method + "\n    get(url, options)", text, count=1, flags=re.S)
        if count != 1:
            raise RuntimeError(rel + " request method")
        text = updated

    old_http_fix = '''            if (data.startsWith("http://api.zhihu.com")) {
                data = data.replace("http://", "https://");
            }'''
    if old_http_fix in text:
        text = text.replace(old_http_fix, "            data = normalizeZhihuUrl(data);", 1)

    write(rel, text)


def patch_column_items():
    rel = "src/components/ColumnItemsView.vue"
    text = read(rel)
    text = text.replace("import { ref, onMounted, computed } from 'vue';", "import { ref, onMounted } from 'vue';")
    text = text.replace("import { f7 } from 'framework7-vue';\n", "")

    if "const loadError = ref('');" not in text:
        text = replace_once(text, "const lastResult = ref(null);", "const lastResult = ref(null);\nconst loadError = ref('');", rel + " error state")
    if "        loadError\n" not in text:
        text = replace_once(text, "        lastResult\n", "        lastResult,\n        loadError\n", rel + " history state")

    text = text.replace(
        "    if (!isRefresh && !hasMore.value) return;",
        "    if (!isRefresh && (!hasMore.value || loadError.value)) return;",
    )
    if "    if (isRefresh) {\n        loadError.value = '';\n    }" not in text:
        text = replace_once(
            text,
            "    isLoading.value = true;\n    try {",
            "    isLoading.value = true;\n    if (isRefresh) {\n        loadError.value = '';\n    }\n\n    try {",
            rel + " refresh error reset",
        )

    text = text.replace(
        "            // 幽默知乎网页api 不填写url参数无法访问\n            const url = `https://api.zhihu.com/columns/${columnId}/items?limit=20`;\n            res = await $http.get(url, { isWWW: true });",
        "            const url = `https://www.zhihu.com/api/v4/columns/${columnId}/items?limit=20&offset=0`;\n            res = await $http.get(url, {\n                requestMode: 'web'\n            });",
    )
    text = text.replace(
        "        hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);\n    } catch (e) {\n        console.error('Failed to fetch column items:', e);",
        "        hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);\n        loadError.value = '';\n    } catch (e) {\n        console.error('Failed to fetch column items:', e);\n        loadError.value = e?.message || '专栏内容加载失败';",
    )

    old_ui = '''        <div v-if="!hasMore && items.length > 0" class="padding text-align-center text-color-gray no-more">
            已加载全部内容
        </div>
        <div v-if="!isLoading && items.length === 0" class="empty-state">
            <f7-icon f7="tray_fill" size="48" color="gray" />
            <p>该专栏暂无内容</p>
        </div>'''
    new_ui = '''        <div v-if="loadError" class="error-state">
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
        </div>'''
    if new_ui not in text:
        text = replace_once(text, old_ui, new_ui, rel + " error UI")

    text = text.replace(".empty-state {", ".empty-state,\n.error-state {")
    if ".error-state .button {" not in text:
        text = text.replace("\n.no-more {", "\n.error-state .button {\n    width: 120px;\n}\n\n.no-more {", 1)

    write(rel, text)


def patch_search_result():
    rel = "src/components/SearchResultView.vue"
    text = read(rel)

    if "const loadError = ref('');" not in text:
        text = replace_once(text, "const lastResult = ref(null);", "const lastResult = ref(null);\nconst loadError = ref('');", rel + " error state")
    if "        loadError\n" not in text:
        text = replace_once(text, "        lastResult\n", "        lastResult,\n        loadError\n", rel + " history state")

    text = text.replace(
        "        case 'people':\n            const userId = id || '';\n            return `https://www.zhihu.com/api/v4/search_v3?correction=1&t=general&q=${encodedQ}&restricted_scene=member&restricted_field=member_hash_id&restricted_value=${userId}`;",
        "        case 'people': {\n            const userId = id || '';\n            return `https://www.zhihu.com/api/v4/search_v3?correction=1&t=general&q=${encodedQ}&limit=20&offset=0&search_source=Normal&restricted_scene=member&restricted_field=member_hash_id&restricted_value=${userId}`;\n        }",
    )
    text = text.replace(
        "    if (!isRefresh && !hasMore.value) return;",
        "    if (!isRefresh && (!hasMore.value || loadError.value)) return;",
    )
    if "    if (isRefresh) {\n        loadError.value = '';\n    }" not in text:
        text = replace_once(
            text,
            "    isLoading.value = true;\n    try {",
            "    isLoading.value = true;\n    if (isRefresh) {\n        loadError.value = '';\n    }\n\n    try {",
            rel + " refresh error reset",
        )
    text = text.replace(
        "            res = await $http.get(url, { isWWW: true });",
        "            res = await $http.get(url, {\n                requestMode: 'web',\n                requireWebSignature: true\n            });",
        1,
    )
    text = text.replace(
        "            if (!url) {\n                isLoading.value = false;\n                return;\n            }",
        "            if (!url) {\n                hasMore.value = false;\n                return;\n            }",
        1,
    )
    text = text.replace("        const rawList = res.data;", "        const rawList = Array.isArray(res.data) ? res.data : [];")
    text = text.replace(
        "        hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);\n    } catch (e) {\n        console.error('Failed to fetch search results:', e);",
        "        hasMore.value = res.paging?.is_end !== true && Boolean(res.paging?.next);\n        loadError.value = '';\n    } catch (e) {\n        console.error('Failed to fetch search results:', e);\n        loadError.value = e?.message || '搜索结果加载失败';",
    )

    old_ui = '''        <div v-if="!hasMore && items.length > 0" class="padding text-align-center text-color-gray no-more">
            没有更多了
        </div>
        <div v-if="!isLoading && items.length === 0" class="empty-state">
            <f7-icon f7="search" size="48" color="gray" />
            <p>未找到相关内容</p>
        </div>'''
    new_ui = '''        <div v-if="loadError" class="error-state">
            <f7-icon f7="exclamationmark_triangle" size="40" color="red" />
            <p>搜索结果加载失败</p>
            <f7-button fill small @click="fetchItems(true)">重试</f7-button>
        </div>
        <div v-else-if="!hasMore && items.length > 0" class="padding text-align-center text-color-gray no-more">
            没有更多了
        </div>
        <div v-else-if="!isLoading && items.length === 0" class="empty-state">
            <f7-icon f7="search" size="48" color="gray" />
            <p>未找到相关内容</p>
        </div>'''
    if new_ui not in text:
        text = replace_once(text, old_ui, new_ui, rel + " error UI")

    text = text.replace(".empty-state {", ".empty-state,\n.error-state {")
    if ".error-state .button {" not in text:
        text = text.replace("\n.no-more {", "\n.error-state .button {\n    width: 120px;\n}\n\n.no-more {", 1)

    write(rel, text)


def main():
    signer_template = TEMPLATES / "zse96-web.js"
    if not signer_template.exists():
        raise RuntimeError("missing template: deploy/fork-templates/zse96-web.js")
    write("src/api/utils/zse96-web.js", signer_template.read_text(encoding="utf-8"))
    patch_zhihu_module()
    patch_column_items()
    patch_search_result()


if __name__ == "__main__":
    main()
