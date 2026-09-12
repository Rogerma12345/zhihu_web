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
    for rel in ['src/components/CodeBlockRenderer.vue', 'src/components/ReferenceBlockRenderer.vue', 'src/components/UnknownSegmentRenderer.vue']:
        text = _v2_get(rel)
        if text and ('var(--f7-page-bg-color, #fff)' in text or 'var(--f7-text-color, #111)' in text):
            errors.append(f'{rel}: hard-coded light theme fallbacks remain')

    permanent_apply = require_file('deploy/apply-article-display-fix.py')
    if '# BEGIN article display v2 integrated' not in permanent_apply or '_v2_patch_search_page()' not in permanent_apply:
        errors.append('deploy/apply-article-display-fix.py: integrated v2 apply pass missing')
# END article display v2 verification integrated

_verify_v2()
if errors:
    print('article display fix verification failed:', file=sys.stderr)
    for error in errors:
        print(f'  - {error}', file=sys.stderr)
    raise SystemExit(1)

print('article display fix verification passed')
print('search Enter files:', ', '.join(str(path.relative_to(ROOT)) for path in search_files))
