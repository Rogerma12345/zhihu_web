from pathlib import Path
import re
import shutil
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
TEMPLATE_DIR = ROOT / 'deploy' / 'fork-templates' / 'article-display'

TEMPLATE_FILES = {
    'RenderStyledText.vue': 'src/components/RenderStyledText.vue',
    'EnhancedContentRenderer.vue': 'src/components/EnhancedContentRenderer.vue',
    'CodeBlockRenderer.vue': 'src/components/CodeBlockRenderer.vue',
    'ReferenceBlockRenderer.vue': 'src/components/ReferenceBlockRenderer.vue',
    'UnknownSegmentRenderer.vue': 'src/components/UnknownSegmentRenderer.vue',
    'content-text.js': 'src/utils/content-text.js',
}


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f'missing file: {rel}')
    return path.read_text(encoding='utf-8')


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one match, found {count}')
    return text.replace(old, new, 1)


def copy_templates() -> None:
    if not TEMPLATE_DIR.exists():
        raise RuntimeError(f'missing template directory: {TEMPLATE_DIR.relative_to(ROOT)}')
    for source_name, target_rel in TEMPLATE_FILES.items():
        source = TEMPLATE_DIR / source_name
        if not source.exists():
            raise RuntimeError(f'missing template: {source}')
        write(target_rel, source.read_text(encoding='utf-8'))


def patch_article_detail() -> None:
    rel = 'src/components/ArticleDetail.vue'
    text = read(rel)

    # Preserve the current ArticleDetail logic and only replace the rendering entry.
    if "import EnhancedContentRenderer from './EnhancedContentRenderer.vue';" not in text:
        import_patterns = [
            r"import\s+ContentRenderer\s+from\s+['\"]\./ContentRenderer\.vue['\"];?",
            r"import\s+\{?\s*ContentRenderer\s*\}?\s+from\s+['\"]\./ContentRenderer\.vue['\"];?",
        ]
        replaced = False
        for pattern in import_patterns:
            updated, count = re.subn(
                pattern,
                "import EnhancedContentRenderer from './EnhancedContentRenderer.vue';",
                text,
                count=1,
            )
            if count == 1:
                text = updated
                replaced = True
                break
        if not replaced:
            # If the renderer is globally available, add an explicit local import to avoid ambiguity.
            script_match = re.search(r'<script\s+setup[^>]*>', text)
            if not script_match:
                raise RuntimeError(f'{rel}: could not locate ContentRenderer import or <script setup>')
            pos = script_match.end()
            text = text[:pos] + "\nimport EnhancedContentRenderer from './EnhancedContentRenderer.vue';" + text[pos:]

    if '<EnhancedContentRenderer' not in text:
        exact_forms = [
            '<ContentRenderer :segments="item.structured_content" />',
            "<ContentRenderer :segments='item.structured_content' />",
        ]
        replaced = False
        for old in exact_forms:
            if old in text:
                text = text.replace(old, '<EnhancedContentRenderer :segments="item.structured_content" />', 1)
                replaced = True
                break

        if not replaced:
            renderer_pattern = re.compile(
                r'<ContentRenderer\b([^>]*?)\s*:segments\s*=\s*["\']item\.structured_content["\']([^>]*)>',
                re.S,
            )
            match = renderer_pattern.search(text)
            if not match:
                raise RuntimeError(f'{rel}: article renderer usage not found')
            before = match.group(1)
            after = match.group(2).strip()
            if after.endswith('/'):
                after = after[:-1].rstrip()
            suffix = f' {after}' if after else ''
            replacement = f'<EnhancedContentRenderer{before} :segments="item.structured_content"{suffix} />'
            text = text[:match.start()] + replacement + text[match.end():]

    # The action row must participate in document flow. A light fixed/absolute pill on a
    # dark page was both visually inconsistent and covered the current reading position.
    style_pattern = re.compile(r'(\.bottom-float-container\s*\{)(.*?)(\})', re.S)
    style_match = style_pattern.search(text)
    if not style_match:
        raise RuntimeError(f'{rel}: .bottom-float-container style block not found')

    replacement_block = '''.bottom-float-container {
  position: relative;
  inset: auto;
  bottom: auto;
  left: auto;
  transform: none;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: fit-content;
  max-width: calc(100% - 32px);
  margin: 20px auto 24px;
  padding: 10px 16px;
  border: 1px solid var(--f7-bars-border-color, color-mix(in srgb, var(--f7-text-color, #111) 13%, transparent));
  border-radius: 999px;
  background: color-mix(in srgb, var(--f7-bars-bg-color, var(--f7-page-bg-color, #fff)) 94%, transparent);
  color: var(--f7-bars-text-color, var(--f7-text-color, #111));
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}'''
    text = text[:style_match.start()] + replacement_block + text[style_match.end():]

    content_pattern = re.compile(r'(\.content-wrapper\s*\{)(.*?)(\})', re.S)
    content_match = content_pattern.search(text)
    if not content_match:
        raise RuntimeError(f'{rel}: .content-wrapper style block not found')
    content_body = content_match.group(2)
    if re.search(r'padding-bottom\s*:', content_body):
        content_body = re.sub(r'padding-bottom\s*:\s*[^;]+;', 'padding-bottom: 24px;', content_body)
    else:
        content_body += '\n  padding-bottom: 24px;'
    text = text[:content_match.start()] + content_match.group(1) + content_body + content_match.group(3) + text[content_match.end():]

    deep_styles = '''

:global(.dark) .bottom-float-container,
:global(html.dark) .bottom-float-container {
  background: color-mix(in srgb, var(--f7-bars-bg-color, #202020) 96%, transparent);
  border-color: var(--f7-bars-border-color, rgba(255, 255, 255, 0.14));
  color: var(--f7-bars-text-color, var(--f7-text-color, rgba(255, 255, 255, 0.87)));
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.38);
}
'''
    if ':global(.dark) .bottom-float-container' not in text:
        style_close = text.rfind('</style>')
        if style_close == -1:
            raise RuntimeError(f'{rel}: </style> not found')
        text = text[:style_close] + deep_styles + text[style_close:]

    write(rel, text)


def ensure_plain_text_import(text: str, rel: str) -> str:
    import_line = "import { htmlToPlainText } from '../utils/content-text.js';"
    if import_line in text:
        return text
    match = re.search(r'<script\s+setup[^>]*>', text)
    if not match:
        return text
    return text[:match.end()] + '\n' + import_line + text[match.end():]


def patch_search_result() -> None:
    rel = 'src/components/SearchResultView.vue'
    path = ROOT / rel
    if not path.exists():
        return
    text = read(rel)
    text = ensure_plain_text_import(text, rel)

    text = re.sub(
        r"\s*//\s*提前清洗标题和摘要中的 HTML 标签\s*\n\s*const cleanText = \(text = ''\) => text\.replace\(/<\[\^>\]\*>\??/gm, ''\);",
        "\n    const cleanText = htmlToPlainText;",
        text,
        count=1,
    )
    # Handle the exact current form if regex above does not match because of regex punctuation.
    text = text.replace(
        "    // 提前清洗标题和摘要中的 HTML 标签\n    const cleanText = (text = '') => text.replace(/<[^>]*>?/gm, '');",
        "    const cleanText = htmlToPlainText;",
    )
    text = text.replace(
        "            excerpt = obj.content?.[0]?.content || '';",
        "            excerpt = htmlToPlainText(obj.content?.[0]?.content || '');",
    )
    text = text.replace(
        "            title = obj.question?.title || title;",
        "            title = htmlToPlainText(obj.question?.title || title);",
    )

    # Always sanitize at the output boundary as endpoints are inconsistent about escaping HTML.
    old_return = '''        title,
        excerpt,
        action,
        metrics: { likes, comments },'''
    new_return = '''        title: htmlToPlainText(title),
        excerpt: htmlToPlainText(excerpt),
        action,
        metrics: { likes, comments },'''
    if old_return in text and new_return not in text:
        text = text.replace(old_return, new_return, 1)

    write(rel, text)


def patch_list_plain_text(rel: str) -> None:
    path = ROOT / rel
    if not path.exists():
        return
    text = read(rel)
    text = ensure_plain_text_import(text, rel)
    if "import { htmlToPlainText }" not in text:
        # Do not rewrite Options API components without a safe import point.
        return

    # Remote list cards should render excerpts/titles as text. This also handles doubly
    # escaped strings such as "&lt;p&gt;..." without opening v-html to user content.
    text = re.sub(
        r'v-html\s*=\s*"([^"]+)"',
        lambda m: f'v-text="htmlToPlainText({m.group(1)})"',
        text,
    )

    common_expressions = [
        'item.excerpt', 'item.content', 'item.description', 'item.title',
        'data.excerpt', 'data.content', 'data.description', 'data.title',
        'feed.excerpt', 'feed.content', 'feed.description', 'feed.title',
    ]
    for expression in common_expressions:
        text = text.replace(
            '{{ ' + expression + ' }}',
            '{{ htmlToPlainText(' + expression + ') }}',
        )

    def sanitize_interpolation(match):
        expression = match.group(1).strip()
        if 'htmlToPlainText' in expression or '(' in expression:
            return match.group(0)
        if any(token in expression for token in ['.excerpt', '.content', '.description', '.title']):
            return '{{ htmlToPlainText(' + expression + ') }}'
        return match.group(0)

    text = re.sub(r'\{\{\s*([^{}]+?)\s*\}\}', sanitize_interpolation, text)

    write(rel, text)


def detect_search_handler(text: str):
    # Prefer the same click/submit action that already works with pointer input.
    event_candidates = []
    for event, handler in re.findall(
        r'@(click|submit)(?:\.[\w.-]+)?\s*=\s*"([A-Za-z_$][\w$]*)"',
        text,
    ):
        score = 0
        lowered = handler.lower()
        if 'search' in lowered: score += 5
        if 'submit' in lowered: score += 4
        if 'query' in lowered: score += 2
        if 'clear' in lowered or 'cancel' in lowered: score -= 10
        event_candidates.append((score, handler))

    event_candidates.sort(reverse=True)
    if event_candidates and event_candidates[0][0] > 0:
        return event_candidates[0][1]

    # Fall back to a declared function whose name clearly represents submission.
    declared = set(re.findall(r'(?:function\s+|const\s+)([A-Za-z_$][\w$]*(?:Search|search|Submit|submit)[A-Za-z0-9_$]*)', text))
    declared = [name for name in declared if 'clear' not in name.lower() and 'cancel' not in name.lower()]
    declared.sort(key=lambda name: (0 if name.lower() in {'search', 'dosearch', 'performsearch', 'handlesearch', 'submitsearch'} else 1, len(name)))
    return declared[0] if declared else None


def patch_searchbar_enter() -> list[str]:
    patched = []
    component_dir = ROOT / 'src' / 'components'
    if not component_dir.exists():
        return patched

    candidates = sorted(component_dir.glob('*Search*.vue')) + sorted(component_dir.glob('*search*.vue'))
    seen = set()
    for path in candidates:
        if path in seen or path.name == 'SearchResultView.vue':
            continue
        seen.add(path)
        text = path.read_text(encoding='utf-8')
        if '<f7-searchbar' not in text:
            continue
        if '__handleSearchbarEnter' in text and '@keydown.enter=' in text:
            patched.append(str(path.relative_to(ROOT)))
            continue
        if '<script setup' not in text:
            continue

        handler = detect_search_handler(text)
        if not handler:
            continue

        opening = re.search(r'<f7-searchbar\b[^>]*>', text, flags=re.S)
        if not opening:
            continue
        tag = opening.group(0)
        if '@keydown.enter' not in tag:
            patched_tag = tag[:-1] + '\n            @keydown.enter="__handleSearchbarEnter"\n            @submit.prevent="__handleSearchbarEnter">'
            text = text[:opening.start()] + patched_tag + text[opening.end():]

        helper = f'''

function __handleSearchbarEnter(event) {{
    const nativeEvent = event?.originalEvent || event;
    if (nativeEvent?.isComposing || nativeEvent?.keyCode === 229) return;
    nativeEvent?.preventDefault?.();
    nativeEvent?.stopPropagation?.();
    return {handler}(nativeEvent);
}}
'''
        script_close = text.find('</script>')
        if script_close == -1:
            continue
        text = text[:script_close] + helper + text[script_close:]
        path.write_text(text, encoding='utf-8')
        patched.append(str(path.relative_to(ROOT)))

    return patched


def patch_sync_script(rel: str) -> None:
    path = ROOT / rel
    if not path.exists():
        return
    text = read(rel)

    no_change_anchor = '  python3 deploy/verify-network-request-fix.py "$repo_root"\n'
    if 'verify-article-display-fix.py' not in text and no_change_anchor in text:
        text = text.replace(
            no_change_anchor,
            no_change_anchor + '  python3 deploy/verify-article-display-fix.py "$repo_root"\n',
            1,
        )

    apply_anchor = 'python3 deploy/apply-network-request-fix.py "$repo_root"\n'
    if 'apply-article-display-fix.py' not in text and apply_anchor in text:
        text = text.replace(
            apply_anchor,
            apply_anchor + 'python3 deploy/apply-article-display-fix.py "$repo_root"\n',
            1,
        )

    # There are two network verification calls. Ensure the post-sync one is followed too.
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        if line.strip() == 'python3 deploy/verify-network-request-fix.py "$repo_root"':
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ''
            if next_line != 'python3 deploy/verify-article-display-fix.py "$repo_root"':
                out.append('python3 deploy/verify-article-display-fix.py "$repo_root"')
    text = '\n'.join(out) + ('\n' if text.endswith('\n') else '')

    write(rel, text)


def main() -> None:
    copy_templates()
    patch_article_detail()
    patch_search_result()
    for rel in [
        'src/components/FeedCard.vue',
        'src/components/UserProfile.vue',
    ]:
        patch_list_plain_text(rel)

    search_patched = patch_searchbar_enter()
    if not search_patched:
        raise RuntimeError('no Framework7 search component was patched for Enter submission')

    patch_sync_script('deploy/sync-upstream.sh')
    patch_sync_script('deploy/fork-templates/sync-upstream.sh')

    print('article display fix applied')
    print('search Enter patched:', ', '.join(search_patched))


if __name__ == '__main__':
    main()
