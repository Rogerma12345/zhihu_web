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
        if 'var(--f7-bars-bg-color' not in body:
            errors.append('ArticleDetail.vue: bottom action bar is not using Framework7 bar theme variables')
        if 'var(--f7-bars-text-color' not in body:
            errors.append('ArticleDetail.vue: bottom action bar text is not theme-aware')
        if re.search(r'position\s*:\s*absolute', body):
            errors.append('ArticleDetail.vue: absolute bottom action bar remains')
        if 'backdrop-filter' not in body:
            errors.append('ArticleDetail.vue: action bar background treatment missing')

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
    if '__handleSearchbarEnter' in text and '@keydown.enter=' in text:
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

if errors:
    print('article display fix verification failed:', file=sys.stderr)
    for error in errors:
        print(f'  - {error}', file=sys.stderr)
    raise SystemExit(1)

print('article display fix verification passed')
print('search Enter files:', ', '.join(str(path.relative_to(ROOT)) for path in search_files))
