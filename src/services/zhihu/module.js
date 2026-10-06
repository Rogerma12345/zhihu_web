import unifiedFetch from '@/services/zhihu/transport.js';
import { tokenManager, tryRefreshToken } from '@/services/auth.js';
import { ensureGuestCredential } from '@/services/zhihu/guest.js';
import { KEYS, getString, getJSON } from '@/services/storage.js';
import { signWebRequest } from '@/services/zhihu/web-signature.js';

const appVersion = "10.12.0"
const apiVersion = "101_1_1.0"
const appBuild = "21210"
const appBundle = "com.zhihu.android"

// 数盟id 使用模拟器可以无限生成 未登录必须添加上这个
function getMsid() {
    return getString(KEYS.msid) || 'DUzQXhjAQDuNnnrXUZuXcZAHclw7VipDNE79RFV6UVhoakFRRHVObm5yWFVadVhjWkFIY2x3N1ZpcERORTc5c2h1';
}

function getUdid() {
    return getString(KEYS.udid) || 'DUzQXhjAQDuNnnrXUZuXcZAHclw7VipDNE79RFV6UVhoakFRRHVObm5yWFVadVhjWkFIY2x3N1ZpcERORTc5c2h1';
}

function normalizeZhihuUrl(url) {
    if (typeof url !== 'string') return url;
    return url
        .replace(/^http:\/\/api\.zhihu\.com(?=\/|$)/i, 'https://api.zhihu.com')
        .replace(/^http:\/\/www\.zhihu\.com(?=\/|$)/i, 'https://www.zhihu.com');
}

class ZhihuRequest {
    constructor({ encryptData, loginData, zsts = {}, defaultHeaders = {} }) {
        if (typeof encryptData !== 'function') {
            throw new Error('必须提供 encryptData 加密函数');
        }

        this.encryptData = encryptData.bind(this);

        const x_app_za = `OS=Android&Release=15&Model=Pixel&VersionName=10.12.0&VersionCode=${appBuild}&Product=com.zhihu.android&Installer=Google+Play&DeviceType=AndroidPhone`;
        this.appSpecificHeaders = {
            "x-api-version": "3.0.93",
            "x-app-version": appVersion,
            "x-app-za": x_app_za,
            "x-app-bundleid": appBundle,
            "x-app-flavor": "play",
            "x-app-build": "release",
        };

        this.updateLoginData(loginData, zsts, defaultHeaders)

    }

    updateLoginData(loginData, zsts = {}, defaultHeaders = {}) {
        // 空凭证和游客凭证不能继承上一账号的 Cookie；普通令牌刷新可沿用现有 Cookie。
        const isGuestPayload = Boolean(loginData?.guest);
        const source = loginData?.guest || loginData || {};
        this.accessToken = source.access_token ? `Bearer ${source.access_token}` : "";

        const inheritedCookie = (!loginData || isGuestPayload)
            ? {}
            : (source.cookie || this.cookieMap || {});
        const cookieMap = { ...inheritedCookie };
        if (!cookieMap.d_c0 && source.d_c0) {
            cookieMap.d_c0 = source.d_c0;
        }
        this.cookieMap = cookieMap;
        this.cookie = Object.entries(cookieMap)
            .filter(([_, v]) => v)
            .map(([k, v]) => `${k}=${v}`)
            .join('; ');

        this.zst81 = undefined;
        this.zst82 = undefined;
        if (Array.isArray(zsts) && zsts.length > 0) {
            const [zst82, zst81] = zsts;
            this.zst81 = zst81;
            this.zst82 = zst82;
        }

        const user_agent = `${appBundle}/Futureve/${appVersion} Mozilla/5.0 (Linux; Android; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/57.0.1000.10 Mobile Safari/537.36`
        this.commonDefaultHeaders = {
            "User-Agent": user_agent,
            "x-Zse-93": apiVersion,
            ...(this.cookie && { "Cookie": this.cookie }),
            ...(this.accessToken && { "Authorization": this.accessToken }),
            ...(getMsid() && { "x-ms-id": getMsid() }),
            ...(getUdid() && { "x-udid": getUdid() }),
            ...(this.zst81 && { "X-ZST-81": this.zst81 }),
            ...(this.zst82 && { "X-ZST-82": this.zst82 }),
            ...defaultHeaders,
        };

        this.defaultHeaders = {
            ...this.commonDefaultHeaders,
            ...this.appSpecificHeaders
        };

        const browserUserAgent = typeof navigator !== 'undefined'
            ? navigator.userAgent
            : 'Mozilla/5.0';
        this.webDefaultHeaders = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": browserUserAgent,
            "Referer": "https://www.zhihu.com/",
            ...(this.cookie && { "Cookie": this.cookie }),
            ...defaultHeaders,
        };

        console.log('Login data updated');
    }

    async request(method, url, data = "", {
        headers = {},
        encryptBody = true,
        isWWW = false,
        encryptHead = false,
        requestMode = null,
        requireWebSignature = false,
        signal = null,
        noCredentialRebuild = false,
    } = {}) {
        method = method.toUpperCase();
        url = normalizeZhihuUrl(url);
        const isGet = method === 'GET';
        const isWebRequest = requestMode === 'web';

        // 每次尝试都按当前凭证重新组装请求，凭证刷新后的重试会重新计算签名与 Cookie。
        const assemble = () => {
            const baseDefaultHeaders = isWebRequest
                ? this.webDefaultHeaders
                : (isWWW ? this.commonDefaultHeaders : this.defaultHeaders);
            const incomingCookie = headers.Cookie || headers.cookie;
            const instanceCookie = baseDefaultHeaders.Cookie || "";
            const cookieMap = {};

            for (const source of [instanceCookie, incomingCookie]) {
                if (!source) continue;
                source.split(';').forEach((cookie) => {
                    const [name, ...valueParts] = cookie.trim().split('=');
                    if (name) cookieMap[name] = valueParts.join('=');
                });
            }

            const finalCookie = Object.entries(cookieMap)
                .filter(([_, value]) => value)
                .map(([name, value]) => `${name}=${value}`)
                .join('; ');

            let body = null;
            if (!isGet && data) {
                body = isWebRequest ? data : (encryptBody ? this.encryptData(data, false) : data);
            }

            const requestHeaders = {
                ...baseDefaultHeaders,
                ...headers,
            };
            delete requestHeaders.Cookie;
            delete requestHeaders.cookie;
            if (finalCookie) requestHeaders.Cookie = finalCookie;

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

                const dC0 = cookieMap.d_c0 || '';
                if (dC0) {
                    const signature = signWebRequest(url, dC0, isGet ? null : body);
                    requestHeaders['x-zse-93'] = signature.zse93;
                    requestHeaders['x-zse-96'] = signature.zse96;
                    requestHeaders['x-requested-with'] = 'fetch';
                } else if (requireWebSignature) {
                    throw new Error('网页请求缺少 d_c0，无法生成签名');
                }
            } else if (isGet || encryptHead || !data) {
                requestHeaders["x-Zse-96"] = `1.0_${this.encryptData(url)}`;
            }

            if (!isGet && data && !requestHeaders["Content-Type"]) {
                requestHeaders["Content-Type"] = isWebRequest
                    ? "application/json"
                    : "application/x-www-form-urlencoded";
            }

            return { headers: requestHeaders, body };
        };

        const { headers: requestHeaders, body } = assemble();
        const fetchOptions = {
            headers: requestHeaders,
            assemble,
            ...(signal && { signal }),
            ...(noCredentialRebuild && { noCredentialRebuild }),
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

    get(url, options) { return this.request('GET', url, null, options); }
    post(url, data, options) { return this.request('POST', url, data, options); }
    patch(url, data, options) { return this.request('PATCH', url, data, options); }
    put(url, data, options) { return this.request('PUT', url, data, options); }
    delete(url, options) { return this.request('DELETE', url, null, options); }

    canSignWebRequests() {
        return Boolean(this.cookieMap?.d_c0);
    }
}

let globalZhihuInstance = null;

import { getLAESInstance } from '@/services/zhihu/laes.js'
import CryptoJS from 'crypto-js';
const laes_utils = getLAESInstance();
export async function initZhihu() {
    const LAESEncrypt = laes_utils.createEncryptor("541a3a5896fbefd351917c8251328a236a7efbf27d0fad8283ef59ef07aa386dbb2b1fcbba167135d575877ba0205a02f0aac2d31957bc7f028ed5888d4bbe69ed6768efc15ab703dc0f406b301845a0a64cf3c427c82870053bd7ba6721649c3a9aca8c3c31710a6be5ce71e4686842732d9314d6898cc3fdca075db46d1ccf3a7f9b20615f4a303c5235bd02c5cdc791eb123b9d9f7e72e954de3bcbf7d314064a1eced78d13679d040dd4080640d18c37bbde", [102, 48, 53, 53, 49, 56, 53, 54, 97, 97, 53, 55, 53, 102, 97, 97]);
    function encrypt_data(data, isGetRequest = true) {
        if (typeof data !== 'string') {
            throw new Error('data must be a string');
        }

        // 网页与图片域名不使用安卓接口加密。
        if (data.startsWith("https://www.zhihu.com") || data.startsWith("http://www.zhihu.com")) return data;
        if (data.startsWith("https://lens.zhihu.com") || data.startsWith("http://lens.zhihu.com")) return data;

        if (isGetRequest) {
            const apiPrefix = 'https://api.zhihu.com';
            if (data.startsWith("http://api.zhihu.com")) {
                data = data.replace("http://", "https://");
            }
            if (!data.startsWith(apiPrefix)) {
                throw new Error(`URL must start with ${apiPrefix}`);
            }
            const apiPath = data.slice(apiPrefix.length)
            data = `${apiVersion}+${apiPath}+${appVersion}+${this.accessToken}+${getUdid()}`
            data = CryptoJS.MD5(CryptoJS.enc.Utf8.parse(data)).toString(CryptoJS.enc.Hex);
        }

        return LAESEncrypt(data);
    }

    let loginData = null;
    const isLogin = tokenManager.isLogin();
    if (isLogin) {
        await tryRefreshToken();
        loginData = tokenManager.getLoginData();
    }

    // 如果没有提供登录数据，使用默认游客账号
    if (!loginData) {
        loginData = await ensureGuestCredential();
    }

    globalZhihuInstance = new ZhihuRequest({
        encryptData: encrypt_data,
        loginData: loginData,
        zsts: getJSON(KEYS.zsts, null)
    });


    console.log('ZhihuRequest 已初始化');
    return globalZhihuInstance;
}

export function updateZhihuLoginData(loginData, zsts, defaultHeaders) {
    if (!globalZhihuInstance) {
        console.warn('ZhihuRequest 尚未初始化，请先调用 initZhihu');
        return null;
    }
    globalZhihuInstance.updateLoginData(loginData, zsts, defaultHeaders);
    return globalZhihuInstance;
}

export function getZhihuInstance() {
    return globalZhihuInstance;
}
