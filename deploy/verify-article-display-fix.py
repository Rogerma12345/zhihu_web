from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
errors = []


def require_file(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        errors.append(f'missing file: {rel}')
        return ''
    return path.read_text(encoding='utf-8')


def require(rel: str, needle: str, label: str) -> None:
    text = require_file(rel)
    if needle not in text:
        errors.append(f'{rel}: {label}')


require('src/components/RenderStyledText.vue', "part.kind === 'formula'", 'formula branch missing')
require('src/components/RenderStyledText.vue', 'formula.content', 'formula LaTeX data missing')
require('src/components/RenderStyledText.vue', 'formula.img_url', 'formula image data missing')
require('src/components/EnhancedContentRenderer.vue', "segment?.type === 'code_block'", 'code block renderer missing')
require('src/components/EnhancedContentRenderer.vue', "segment?.type === 'reference_block'", 'reference block renderer missing')
require('src/components/EnhancedContentRenderer.vue', 'UnknownSegmentRenderer', 'unknown segment fallback missing')
require('src/components/CodeBlockRenderer.vue', 'code_block', 'code block component marker missing') if False else None
require('src/components/CodeBlockRenderer.vue', 'highlightPlain', 'syntax highlighting missing')
require('src/components/ReferenceBlockRenderer.vue', 'reference_block', 'reference block component marker missing') if False else None
require('src/components/ReferenceBlockRenderer.vue', 'indent_level', 'reference indentation missing')
require('src/utils/content-text.js', 'htmlToPlainText', 'HTML-to-text sanitizer missing')

article = require_file('src/components/ArticleDetail.vue')
if article:
    if "import EnhancedContentRenderer from './EnhancedContentRenderer.vue';" not in article:
        errors.append('ArticleDetail.vue: enhanced renderer import missing')
    if '<EnhancedContentRenderer' not in article:
        errors.append('ArticleDetail.vue: enhanced renderer usage missing')
    block = re.search(r'\.bottom-float-container\s*\{(.*?)\}', article, re.S)
    if not block:
        errors.append('ArticleDetail.vue: bottom action bar style missing')
    else:
        body = block.group(1)
        if 'position: relative' not in body:
            errors.append('ArticleDetail.vue: bottom action bar is not in document flow')
        if 'pointer-events: none' not in body:
            errors.append('ArticleDetail.vue: bottom action row container should not swallow page clicks')
        if re.search(r'position\s*:\s*absolute', body):
            errors.append('ArticleDetail.vue: absolute bottom action bar remains')

search_result = require_file('src/components/SearchResultView.vue')
if search_result:
    if 'htmlToPlainText' not in search_result:
        errors.append('SearchResultView.vue: HTML summary sanitizer missing')
    if "excerpt = obj.content?.[0]?.content || '';" in search_result:
        errors.append('SearchResultView.vue: pin HTML is still rendered as raw text')

for rel in ['src/components/FeedCard.vue', 'src/components/UserProfile.vue']:
    path = ROOT / rel
    if path.exists():
        text = path.read_text(encoding='utf-8')
        if 'v-html=' in text:
            errors.append(f'{rel}: untrusted list v-html remains')
        if 'htmlToPlainText' not in text:
            errors.append(f'{rel}: HTML summary sanitizer not wired')

search_files = []
for path in (ROOT / 'src' / 'components').glob('*.vue'):
    text = path.read_text(encoding='utf-8')
    if ('handleSearchbarKeydown' in text and '@keydown="handleSearchbarKeydown"' in text) or ('__handleSearchbarEnter' in text and '@keydown.enter=' in text):
        search_files.append(path)
if not search_files:
    errors.append('search page: Enter submission handler missing')

for rel in ['deploy/sync-upstream.sh', 'deploy/fork-templates/sync-upstream.sh']:
    text = require_file(rel)
    if text:
        if 'apply-article-display-fix.py' not in text:
            errors.append(f'{rel}: article display fix is not reapplied after upstream sync')
        if 'verify-article-display-fix.py' not in text:
            errors.append(f'{rel}: article display verification missing')

for template in [
    'RenderStyledText.vue',
    'EnhancedContentRenderer.vue',
    'CodeBlockRenderer.vue',
    'ReferenceBlockRenderer.vue',
    'UnknownSegmentRenderer.vue',
    'content-text.js',
]:
    if not (ROOT / 'deploy' / 'fork-templates' / 'article-display' / template).exists():
        errors.append(f'missing article display template: {template}')


# BEGIN article display v2 verification integrated
def _v2_get(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        errors.append(f'missing file: {rel}')
        return ''
    return path.read_text(encoding='utf-8')

def _verify_v2() -> None:
    search = _v2_get('src/components/SearchPage.vue')
    if search:
        if 'const handleSearchbarKeydown = (event) =>' not in search:
            errors.append('SearchPage.vue: direct Enter handler missing')
        if '@keydown="handleSearchbarKeydown"' not in search:
            errors.append('SearchPage.vue: searchbar keydown binding missing')
        if '@submit.prevent="handleSearch()"' not in search:
            errors.append('SearchPage.vue: searchbar submit fallback missing')
        if '__handleSearchbarEnter' in search:
            errors.append('SearchPage.vue: obsolete v1 Enter wrapper still present')
    for rel in ['src/components/FeedCard.vue', 'src/components/UserProfile.vue']:
        text = _v2_get(rel)
        if text:
            if 'v-html=' in text:
                errors.append(f'{rel}: untrusted list v-html remains')
            if 'htmlToPlainText' not in text:
                errors.append(f'{rel}: htmlToPlainText not wired')
    article = _v2_get('src/components/ArticleDetail.vue')
    if article:
        if "import EnhancedContentRenderer from './EnhancedContentRenderer.vue';" not in article:
            errors.append('ArticleDetail.vue: EnhancedContentRenderer import missing')
        if '<EnhancedContentRenderer' not in article or 'item.structured_content' not in article:
            errors.append('ArticleDetail.vue: enhanced renderer not used for article body')
        bottom = re.search('\\.bottom-float-container\\s*\\{(.*?)\\}', article, re.S)
        if not bottom:
            errors.append('ArticleDetail.vue: bottom-float-container style missing')
        else:
            body = bottom.group(1)
            if 'position: relative' not in body:
                errors.append('ArticleDetail.vue: action row not in normal layout flow')
            if re.search('position\\s*:\\s*absolute', body):
                errors.append('ArticleDetail.vue: absolute action row remains')
            if re.search('background\\s*:', body):
                errors.append('ArticleDetail.vue: outer action container should not paint a theme background')
        if 'background: rgba(255, 255, 255, 0.9)' in article:
            errors.append('ArticleDetail.vue: hard-coded light glass background remains')
        if '--f7-bg-color-rgb' in article:
            errors.append('ArticleDetail.vue: fragile --f7-bg-color-rgb action-bar fallback remains')
    renderer = _v2_get('src/components/EnhancedContentRenderer.vue')
    if renderer:
        if "defineEmits(['imageClick'])" not in renderer:
            errors.append('EnhancedContentRenderer.vue: imageClick emit missing')
        if '@imageClick="emit(\'imageClick\', $event)"' not in renderer:
            errors.append('EnhancedContentRenderer.vue: legacy imageClick is not forwarded')
    content = _v2_get('src/components/ContentRenderer.vue')
    if content:
        if 'htmlToPlainText(segment.card.title' not in content:
            errors.append('ContentRenderer.vue: link-card title sanitizer missing')
        if 'htmlToPlainText(extra.desc' not in content:
            errors.append('ContentRenderer.vue: link-card description sanitizer missing')
        if "backgroundColor: '#f5f5f5'" in content:
            errors.append('ContentRenderer.vue: hard-coded light image placeholder remains')
    reference = _v2_get('src/components/ReferenceBlockRenderer.vue')
    if reference:
        if "return htmlToPlainText(item?.text || '');" not in reference:
            errors.append('ReferenceBlockRenderer.vue: reference visible text sanitizer missing')
        if ':text="item?.text || \'\'"' in reference:
            errors.append('ReferenceBlockRenderer.vue: raw reference HTML still reaches styled text renderer')
    styled = _v2_get('src/components/RenderStyledText.vue')
    if styled:
        if 'mix-blend-mode: screen' in styled:
            errors.append('RenderStyledText.vue: formula screen blending remains')
        if 'mix-blend-mode: difference' not in styled:
            errors.append('RenderStyledText.vue: adaptive formula blending missing')
        if ':global(.dark) .styled-formula-image' in styled or ':global(html.dark) .styled-formula-image' in styled:
            errors.append('RenderStyledText.vue: malformed scoped :global selector would target the dark root')
        if ':global(.dark .styled-formula-image)' not in styled:
            errors.append('RenderStyledText.vue: scoped dark formula selector missing')

    code_renderer = _v2_get('src/components/CodeBlockRenderer.vue')
    if code_renderer:
        if ':global(.dark) .code-block-renderer' in code_renderer or ':global(html.dark) .code-block-renderer' in code_renderer:
            errors.append('CodeBlockRenderer.vue: malformed scoped :global selector remains')
        if ':global(.dark .code-block-renderer)' not in code_renderer:
            errors.append('CodeBlockRenderer.vue: scoped dark code selector missing')
    for rel in ['src/components/CodeBlockRenderer.vue', 'src/components/ReferenceBlockRenderer.vue', 'src/components/UnknownSegmentRenderer.vue']:
        text = _v2_get(rel)
        if text and ('var(--f7-page-bg-color, #fff)' in text or 'var(--f7-text-color, #111)' in text):
            errors.append(f'{rel}: hard-coded light theme fallbacks remain')

    template_styled = _v2_get('deploy/fork-templates/article-display/RenderStyledText.vue')
    if template_styled and (':global(.dark) .styled-formula-image' in template_styled or ':global(html.dark) .styled-formula-image' in template_styled):
        errors.append('RenderStyledText template: malformed scoped :global selector remains')

    template_code = _v2_get('deploy/fork-templates/article-display/CodeBlockRenderer.vue')
    if template_code and (':global(.dark) .code-block-renderer' in template_code or ':global(html.dark) .code-block-renderer' in template_code):
        errors.append('CodeBlockRenderer template: malformed scoped :global selector remains')

    permanent_apply = require_file('deploy/apply-article-display-fix.py')
    if '# BEGIN article display v2 integrated' not in permanent_apply or '_v2_patch_search_page()' not in permanent_apply:
        errors.append('deploy/apply-article-display-fix.py: integrated v2 apply pass missing')
# END article display v2 verification integrated


def _verify_screenshot_export() -> None:
    article = _v2_get('src/components/ArticleDetail.vue')
    if article:
        required_markers = {
            '// BEGIN fork screenshot export': 'managed screenshot block missing',
            'const prepareCaptureResources = async': 'resource preparation missing',
            'const resolveCaptureBackground = (element) =>': 'theme background resolver missing',
            'const calculateCaptureScale = (width, height) =>': 'canvas limit handling missing',
            'const canvasToPngBlob = (canvas) =>': 'Blob PNG encoder missing',
            'const triggerScreenshotDownload = (blob) =>': 'browser download handler missing',
            "link.download = `zhihu-${type || 'content'}-${id || 'export'}.png`;": 'download filename missing',
            'onclone: (clonedDocument) =>': 'clone theme handling missing',
            'backgroundColor: captureBackground': 'dynamic screenshot background missing',
            "imageTimeout: SCREENSHOT_RESOURCE_TIMEOUT": 'image timeout missing',
        }
        for needle, label in required_markers.items():
            if needle not in article:
                errors.append(f'ArticleDetail.vue: {label}')
        for forbidden, label in [
            ("backgroundColor: '#ffffff'", 'hard-coded white screenshot background remains'),
            ("canvas.toDataURL('image/png'", 'base64 screenshot preview remains'),
            ("window.open(url, '_blank')", 'Blob popup save path remains'),
            ("f7.toast.show({ text: '截图已保存' })", 'premature saved-state toast remains'),
        ]:
            if forbidden in article:
                errors.append(f'ArticleDetail.vue: {label}')

    template = _v2_get('deploy/fork-templates/article-display/ArticleDetailScreenshot.js')
    if template:
        if '// BEGIN fork screenshot export' not in template or '// END fork screenshot export' not in template:
            errors.append('ArticleDetailScreenshot.js: managed markers missing')
        if "backgroundColor: captureBackground" not in template:
            errors.append('ArticleDetailScreenshot.js: dynamic background handling missing')
        if 'triggerScreenshotDownload' not in template:
            errors.append('ArticleDetailScreenshot.js: download handler missing')

    package = _v2_get('package.json')
    if package and '"html2canvas-pro": "2.4.2"' not in package:
        errors.append('package.json: html2canvas-pro must be pinned to 2.4.2')

    lock = _v2_get('package-lock.json')
    if lock:
        if '"html2canvas-pro": "2.4.2"' not in lock:
            errors.append('package-lock.json: root html2canvas-pro version is not 2.4.2')
        package_block = re.search(r'"node_modules/html2canvas-pro"\s*:\s*\{(.*?)\n\s*\}', lock, re.S)
        if not package_block:
            errors.append('package-lock.json: html2canvas-pro package block missing')
        else:
            body = package_block.group(1)
            if '"version": "2.4.2"' not in body:
                errors.append('package-lock.json: installed html2canvas-pro version is not 2.4.2')
            if 'html2canvas-pro-2.4.2.tgz' not in body:
                errors.append('package-lock.json: html2canvas-pro 2.4.2 tarball missing')

    apply_script = _v2_get('deploy/apply-article-display-fix.py')
    if apply_script:
        if 'def patch_screenshot_export()' not in apply_script:
            errors.append('deploy/apply-article-display-fix.py: screenshot export patch missing')
        if 'def patch_screenshot_dependency()' not in apply_script:
            errors.append('deploy/apply-article-display-fix.py: screenshot dependency patch missing')
        if 'patch_screenshot_export()' not in apply_script or 'patch_screenshot_dependency()' not in apply_script:
            errors.append('deploy/apply-article-display-fix.py: screenshot patch is not invoked')


_verify_v2()
_verify_screenshot_export()
if errors:
    print('article display fix verification failed:', file=sys.stderr)
    for error in errors:
        print(f'  - {error}', file=sys.stderr)
    raise SystemExit(1)

print('article display fix verification passed')
print('search Enter files:', ', '.join(str(path.relative_to(ROOT)) for path in search_files))
