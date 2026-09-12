from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
errors = []


def read(rel):
    path = ROOT / rel
    if not path.exists():
        errors.append(f"missing {rel}")
        return ""
    return path.read_text(encoding="utf-8")


def require(rel, token, label):
    text = read(rel)
    if token not in text:
        errors.append(f"{rel}: {label}")
    return text


def forbid(rel, token, label):
    text = read(rel)
    if token in text:
        errors.append(f"{rel}: {label}")
    return text


signer = read("src/api/utils/zse96-web.js")
for token, label in [
    ("const WEB_ZSE_93 = '101_3_3.0';", "web x-zse-93 version is missing"),
    ("CryptoJS.MD5", "web signature MD5 is missing"),
    ("zse96: `2.0_${encryptWebDigest(digest)}`", "web x-zse-96 generation is missing"),
]:
    if token not in signer:
        errors.append(f"src/api/utils/zse96-web.js: {label}")

module = read("src/api/utils/zhihu-module.js")
for token, label in [
    ("import { signWebRequest } from './zse96-web.js';", "web signer import is missing"),
    ("function normalizeZhihuUrl(url)", "Zhihu URL normalization is missing"),
    ("'https://api.zhihu.com'", "API HTTPS normalization is missing"),
    ("'https://www.zhihu.com'", "WWW HTTPS normalization is missing"),
    ("this.webDefaultHeaders = {", "separate web request headers are missing"),
    ("requireWebSignature = false", "web signature requirement option is missing"),
    ("requestMode = null", "explicit request mode option is missing"),
    ("const isWebRequest = requestMode === 'web';", "web mode is not isolated from legacy isWWW requests"),
    ("const signature = signWebRequest(url, dC0", "web signature generation is missing"),
    ("delete requestHeaders.Authorization;", "web request still reuses Android Authorization"),
    ("url = normalizeZhihuUrl(url);", "request URL is not normalized before signing"),
]:
    if token not in module:
        errors.append(f"src/api/utils/zhihu-module.js: {label}")

for token, label in [
    ("console.log('UpdateLoginData:', loginData);", "login credentials are still logged"),
    ("cookieData.d_c0 = loginData.udid;", "Android udid still overwrites d_c0"),
    ("`1.0_${this.encryptData(url)}`", "")
]:
    if label and token in module:
        errors.append(f"src/api/utils/zhihu-module.js: {label}")

column = read("src/components/ColumnItemsView.vue")
for token, label in [
    ("https://www.zhihu.com/api/v4/columns/${columnId}/items?limit=20&offset=0", "column web API URL is missing"),
    ("requestMode: 'web'", "column request does not use web request mode"),
    ("const loadError = ref('');", "column load error state is missing"),
    ("v-if=\"loadError\"", "column error UI is missing"),
]:
    if token not in column:
        errors.append(f"src/components/ColumnItemsView.vue: {label}")
if "https://api.zhihu.com/columns/${columnId}/items" in column:
    errors.append("src/components/ColumnItemsView.vue: obsolete API host remains")

search = read("src/components/SearchResultView.vue")
for token, label in [
    ("search_source=Normal", "search request parameters are incomplete"),
    ("requestMode: 'web'", "search request does not use web request mode"),
    ("requireWebSignature: true", "search request does not require web signature"),
    ("const loadError = ref('');", "search load error state is missing"),
    ("Array.isArray(res.data) ? res.data : []", "search result data guard is missing"),
    ("v-if=\"loadError\"", "search error UI is missing"),
]:
    if token not in search:
        errors.append(f"src/components/SearchResultView.vue: {label}")

for rel in ["deploy/sync-upstream.sh", "deploy/fork-templates/sync-upstream.sh"]:
    text = read(rel)
    for token, label in [
        ("python3 deploy/apply-network-request-fix.py", "network patch is not applied after upstream sync"),
        ("python3 deploy/verify-network-request-fix.py", "network fix is not verified after upstream sync"),
    ]:
        if token not in text:
            errors.append(f"{rel}: {label}")

if errors:
    print("network request fix verification failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)

print("network request fix verification passed")
