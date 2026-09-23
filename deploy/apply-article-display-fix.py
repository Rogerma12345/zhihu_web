from pathlib import Path
import re
import shutil
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
TEMPLATE_DIR = ROOT / 'deploy' / 'fork-templates' / 'article-display'
SCREENSHOT_TEMPLATE = TEMPLATE_DIR / 'ArticleDetailScreenshot.js'
HTML2CANVAS_PRO_VERSION = '2.4.2'
HTML2CANVAS_PRO_TARBALL = f'https://registry.npmjs.org/html2canvas-pro/-/html2canvas-pro-{HTML2CANVAS_PRO_VERSION}.tgz'
KATEX_VERSION = '0.18.7'
KATEX_TARBALL = f'https://registry.npmjs.org/katex/-/katex-{KATEX_VERSION}.tgz'
KATEX_COMMANDER_VERSION = '8.3.0'
KATEX_COMMANDER_TARBALL = f'https://registry.npmjs.org/commander/-/commander-{KATEX_COMMANDER_VERSION}.tgz'
KATEX_COMMANDER_INTEGRITY = 'sha512-OkTL9umf+He2DZkUq8f8J9of7yL6RJKI24dVITBmNfZBmri9zYZQrKkuXiKhyfPSu8tUhnVBB1iKXevvnlR4Ww=='

TEMPLATE_FILES = {
    'RenderStyledText.vue': 'src/components/RenderStyledText.vue',
    'EnhancedContentRenderer.vue': 'src/components/EnhancedContentRenderer.vue',
    'CodeBlockRenderer.vue': 'src/components/CodeBlockRenderer.vue',
    'ReferenceBlockRenderer.vue': 'src/components/ReferenceBlockRenderer.vue',
    'TableSegmentRenderer.vue': 'src/components/TableSegmentRenderer.vue',
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
                text = text.replace(old, '<EnhancedContentRenderer :segments="item.structured_content" :source-html="item.content" />', 1)
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
            replacement = f'<EnhancedContentRenderer{before} :segments="item.structured_content" :source-html="item.content"{suffix} />'
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

:global(.dark .bottom-float-container),
:global(html.dark .bottom-float-container) {
  background: color-mix(in srgb, var(--f7-bars-bg-color, #202020) 96%, transparent);
  border-color: var(--f7-bars-border-color, rgba(255, 255, 255, 0.14));
  color: var(--f7-bars-text-color, var(--f7-text-color, rgba(255, 255, 255, 0.87)));
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.38);
}
'''
    if ':global(.dark .bottom-float-container)' not in text:
        style_close = text.rfind('</style>')
        if style_close == -1:
            raise RuntimeError(f'{rel}: </style> not found')
        text = text[:style_close] + deep_styles + text[style_close:]

    write(rel, text)


def patch_screenshot_export() -> None:
    rel = 'src/components/ArticleDetail.vue'
    text = read(rel)
    if not SCREENSHOT_TEMPLATE.exists():
        raise RuntimeError(f'missing screenshot template: {SCREENSHOT_TEMPLATE.relative_to(ROOT)}')
    screenshot_template = SCREENSHOT_TEMPLATE.read_text(encoding='utf-8').rstrip() + '\n'

    managed_pattern = re.compile(
        r'// BEGIN fork screenshot export\n.*?// END fork screenshot export\n',
        re.S,
    )
    if managed_pattern.search(text):
        text = managed_pattern.sub(lambda _match: screenshot_template, text, count=1)
    else:
        legacy_pattern = re.compile(
            r'(?:\s*// Save article as image\s*)?\n?const saveAsImage = async \(\) => \{.*?\n\};\n\n(?=const openOriginalLink)',
            re.S,
        )
        updated, count = legacy_pattern.subn(
            lambda _match: '\n' + screenshot_template + '\n',
            text,
            count=1,
        )
        if count != 1:
            raise RuntimeError(f'{rel}: saveAsImage block not found')
        text = updated

    write(rel, text)


def patch_screenshot_dependency() -> None:
    package_rel = 'package.json'
    package_text = read(package_rel)
    package_pattern = re.compile(r'("html2canvas-pro"\s*:\s*)"[^"]+"')
    package_text, package_count = package_pattern.subn(
        lambda match: match.group(1) + f'"{HTML2CANVAS_PRO_VERSION}"',
        package_text,
        count=1,
    )
    if package_count != 1:
        raise RuntimeError(f'{package_rel}: html2canvas-pro dependency not found')
    write(package_rel, package_text)

    lock_rel = 'package-lock.json'
    lock_text = read(lock_rel)
    lock_text, root_count = package_pattern.subn(
        lambda match: match.group(1) + f'"{HTML2CANVAS_PRO_VERSION}"',
        lock_text,
        count=1,
    )
    if root_count != 1:
        raise RuntimeError(f'{lock_rel}: root html2canvas-pro dependency not found')

    package_block_pattern = re.compile(
        r'("node_modules/html2canvas-pro"\s*:\s*\{)(.*?)(\n\s*\})',
        re.S,
    )
    block_match = package_block_pattern.search(lock_text)
    if not block_match:
        raise RuntimeError(f'{lock_rel}: node_modules/html2canvas-pro block not found')

    body = block_match.group(2)
    body, version_count = re.subn(
        r'("version"\s*:\s*)"[^"]+"',
        lambda match: match.group(1) + f'"{HTML2CANVAS_PRO_VERSION}"',
        body,
        count=1,
    )
    body, resolved_count = re.subn(
        r'("resolved"\s*:\s*)"[^"]+"',
        lambda match: match.group(1) + f'"{HTML2CANVAS_PRO_TARBALL}"',
        body,
        count=1,
    )
    if version_count != 1 or resolved_count != 1:
        raise RuntimeError(f'{lock_rel}: html2canvas-pro package metadata incomplete')

    body = re.sub(r'\n\s*"integrity"\s*:\s*"[^"]+",?', '', body, count=1)
    replacement = block_match.group(1) + body + block_match.group(3)
    lock_text = lock_text[:block_match.start()] + replacement + lock_text[block_match.end():]
    write(lock_rel, lock_text)



def patch_formula_dependency() -> None:
    package_rel = 'package.json'
    package_text = read(package_rel)
    katex_pattern = re.compile(r'("katex"\s*:\s*)"[^"]+"')
    if katex_pattern.search(package_text):
        package_text = katex_pattern.sub(
            lambda match: match.group(1) + f'"{KATEX_VERSION}"',
            package_text,
            count=1,
        )
    else:
        dependency_anchor = f'    "html2canvas-pro": "{HTML2CANVAS_PRO_VERSION}",\n'
        if dependency_anchor not in package_text:
            raise RuntimeError(f'{package_rel}: dependency insertion anchor missing')
        package_text = package_text.replace(
            dependency_anchor,
            dependency_anchor + f'    "katex": "{KATEX_VERSION}",\n',
            1,
        )
    write(package_rel, package_text)

    lock_rel = 'package-lock.json'
    lock_text = read(lock_rel)
    root_end = lock_text.find('    "node_modules/')
    if root_end == -1:
        raise RuntimeError(f'{lock_rel}: package section boundary missing')
    root_text = lock_text[:root_end]
    remainder = lock_text[root_end:]
    if katex_pattern.search(root_text):
        root_text = katex_pattern.sub(
            lambda match: match.group(1) + f'"{KATEX_VERSION}"',
            root_text,
            count=1,
        )
    else:
        dependency_anchor = f'        "html2canvas-pro": "{HTML2CANVAS_PRO_VERSION}",\n'
        if dependency_anchor not in root_text:
            raise RuntimeError(f'{lock_rel}: root dependency insertion anchor missing')
        root_text = root_text.replace(
            dependency_anchor,
            dependency_anchor + f'        "katex": "{KATEX_VERSION}",\n',
            1,
        )
    lock_text = root_text + remainder

    katex_block = f'''    "node_modules/katex": {{
      "version": "{KATEX_VERSION}",
      "resolved": "{KATEX_TARBALL}",
      "license": "MIT",
      "dependencies": {{
        "commander": "^8.3.0"
      }},
      "bin": {{
        "katex": "cli.js"
      }}
    }},
    "node_modules/katex/node_modules/commander": {{
      "version": "{KATEX_COMMANDER_VERSION}",
      "resolved": "{KATEX_COMMANDER_TARBALL}",
      "integrity": "{KATEX_COMMANDER_INTEGRITY}",
      "license": "MIT",
      "engines": {{
        "node": ">= 12"
      }}
    }},
'''
    block_pattern = re.compile(
        r'    "node_modules/katex": \{.*?\n    \},\n'
        r'(?:    "node_modules/katex/node_modules/commander": \{.*?\n    \},\n)?',
        re.S,
    )
    if block_pattern.search(lock_text):
        lock_text = block_pattern.sub(katex_block, lock_text, count=1)
    else:
        package_anchor = '    "node_modules/kind-of": {'
        if package_anchor not in lock_text:
            raise RuntimeError(f'{lock_rel}: KaTeX package insertion anchor missing')
        lock_text = lock_text.replace(package_anchor, katex_block + package_anchor, 1)

    write(lock_rel, lock_text)


def patch_screenshot_csp() -> None:
    """Allow Blob-backed screenshot previews without broadening Blob access for other resource types."""
    for rel in ('src/index.html', 'html/index.html'):
        path = ROOT / rel
        if not path.exists():
            if rel == 'src/index.html':
                raise RuntimeError(f'missing file: {rel}')
            continue

        text = read(rel)
        meta_pattern = re.compile(
            r'(?P<prefix><meta\s+http-equiv=["\']Content-Security-Policy["\'][^>]*?content=)(?P<quote>["\'])(?P<policy>.*?)(?P=quote)',
            re.I | re.S,
        )
        match = meta_pattern.search(text)
        if not match:
            raise RuntimeError(f'{rel}: Content-Security-Policy meta tag not found')

        directives = [part.strip() for part in match.group('policy').split(';') if part.strip()]
        img_src_index = None
        default_sources = []
        for index, directive in enumerate(directives):
            tokens = directive.split()
            if not tokens:
                continue
            name = tokens[0].lower()
            if name == 'img-src':
                img_src_index = index
            elif name == 'default-src':
                default_sources = tokens[1:]

        if img_src_index is None:
            inherited_sources = [
                source for source in default_sources
                if source not in {"'unsafe-inline'", "'unsafe-eval'", "'none'"}
            ]
            if not inherited_sources:
                inherited_sources = ["'self'"]
            if 'blob:' not in inherited_sources:
                inherited_sources.append('blob:')
            directives.append('img-src ' + ' '.join(inherited_sources))
        else:
            tokens = directives[img_src_index].split()
            sources = [source for source in tokens[1:] if source != "'none'"]
            if 'blob:' not in sources:
                sources.append('blob:')
            directives[img_src_index] = 'img-src ' + ' '.join(sources or ["'self'", 'blob:'])

        policy = '; '.join(directives)
        replacement = match.group('prefix') + match.group('quote') + policy + match.group('quote')
        text = text[:match.start()] + replacement + text[match.end():]
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



# BEGIN article display v2 integrated
def _v2_read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f'missing file: {rel}')
    return path.read_text(encoding='utf-8')

def _v2_write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def _v2_ensure_script_import(text: str, import_line: str) -> str:
    if import_line in text:
        return text
    match = re.search('<script\\s+setup[^>]*>', text)
    if not match:
        raise RuntimeError('missing <script setup>')
    return text[:match.end()] + '\n' + import_line + text[match.end():]

def _v2_replace_style_block(text: str, selector: str, new_block: str) -> str:
    pattern = re.compile(f'{re.escape(selector)}\\s*\\{{.*?\\}}', re.S)
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f'missing style block: {selector}')
    return text[:match.start()] + new_block + text[match.end():]

def _v2_patch_search_page(rel: str='src/components/SearchPage.vue') -> None:
    text = _v2_read(rel)
    text = re.sub('\\s*@keydown\\.enter\\s*=\\s*"__handleSearchbarEnter"', '', text)
    text = re.sub('\\s*@submit\\.prevent\\s*=\\s*"__handleSearchbarEnter"', '', text)
    text = re.sub('\\nfunction\\s+__handleSearchbarEnter\\s*\\(event\\)\\s*\\{.*?\\n\\}\\n', '\n', text, flags=re.S)
    if 'const handleSearchbarKeydown = (event) =>' not in text:
        anchor = 'const handleTabRefresh = async (tabId, done) => {'
        helper = "const handleSearchbarKeydown = (event) => {\n    const nativeEvent = event?.originalEvent || event;\n    const isEnter = nativeEvent?.key === 'Enter' || nativeEvent?.keyCode === 13;\n    if (!isEnter) return;\n    if (nativeEvent?.isComposing || nativeEvent?.keyCode === 229) return;\n    nativeEvent?.preventDefault?.();\n    nativeEvent?.stopPropagation?.();\n    handleSearch();\n};\n\n"
        if anchor not in text:
            raise RuntimeError(f'{rel}: handleTabRefresh anchor not found')
        text = text.replace(anchor, helper + anchor, 1)
    opening = re.search('<f7-searchbar\\b[^>]*>', text, flags=re.S)
    if not opening:
        raise RuntimeError(f'{rel}: <f7-searchbar> not found')
    tag = opening.group(0)
    tag = re.sub('\\s+@keydown\\s*=\\s*"handleSearchbarKeydown"', '', tag)
    tag = re.sub('\\s+@submit\\.prevent\\s*=\\s*"handleSearch\\(\\)"', '', tag)
    tag = tag[:-1] + '\n                @keydown="handleSearchbarKeydown" @submit.prevent="handleSearch()">'
    text = text[:opening.start()] + tag + text[opening.end():]
    _v2_write(rel, text)

def _v2_patch_feed_card(rel: str='src/components/FeedCard.vue') -> None:
    text = _v2_read(rel)
    text = _v2_ensure_script_import(text, "import { htmlToPlainText } from '../utils/content-text.js';")
    text = text.replace('<div class="title" v-html="item.title"></div>', '<div class="title">{{ htmlToPlainText(item.title) }}</div>')
    text = text.replace('<span class="excerpt-text" v-html="item.excerpt"></span>', '<span class="excerpt-text">{{ htmlToPlainText(item.excerpt) }}</span>')
    text = text.replace('<div class="title" v-text="htmlToPlainText(item.title)"></div>', '<div class="title">{{ htmlToPlainText(item.title) }}</div>')
    text = text.replace('<span class="excerpt-text" v-text="htmlToPlainText(item.excerpt)"></span>', '<span class="excerpt-text">{{ htmlToPlainText(item.excerpt) }}</span>')
    if 'v-html=' in text:
        raise RuntimeError(f'{rel}: untrusted v-html remains after patch')
    _v2_write(rel, text)

def _v2_patch_user_profile(rel: str='src/components/UserProfile.vue') -> None:
    text = _v2_read(rel)
    text = _v2_ensure_script_import(text, "import { htmlToPlainText } from '../utils/content-text.js';")
    text = text.replace('<h3 v-html="item.title"></h3>', '<h3>{{ htmlToPlainText(item.title) }}</h3>')
    text = text.replace('<div class="excerpt-text" v-html="item.excerpt"></div>', '<div class="excerpt-text">{{ htmlToPlainText(item.excerpt) }}</div>')
    text = text.replace('<h3 v-text="htmlToPlainText(item.title)"></h3>', '<h3>{{ htmlToPlainText(item.title) }}</h3>')
    text = text.replace('<div class="excerpt-text" v-text="htmlToPlainText(item.excerpt)"></div>', '<div class="excerpt-text">{{ htmlToPlainText(item.excerpt) }}</div>')
    text = re.sub('(\\n\\s*return\\s*\\{\\s*\\n\\s*)title,\\s*\\n\\s*excerpt,', '\\1title: htmlToPlainText(title),\\n                    excerpt: htmlToPlainText(excerpt),', text, count=1)
    if 'v-html=' in text:
        raise RuntimeError(f'{rel}: untrusted v-html remains after patch')
    _v2_write(rel, text)

def _v2_patch_article_detail(rel: str='src/components/ArticleDetail.vue') -> None:
    text = _v2_read(rel)
    if "import EnhancedContentRenderer from './EnhancedContentRenderer.vue';" not in text:
        if "import ContentRenderer from './ContentRenderer.vue';" in text:
            text = text.replace("import ContentRenderer from './ContentRenderer.vue';", "import EnhancedContentRenderer from './EnhancedContentRenderer.vue';", 1)
        else:
            text = _v2_ensure_script_import(text, "import EnhancedContentRenderer from './EnhancedContentRenderer.vue';")
    if '<ContentRenderer' in text and 'item.structured_content' in text:
        pattern = re.compile('<ContentRenderer\\b(?P<attrs>[^>]*?:segments\\s*=\\s*["\\\']item\\.structured_content["\\\'][^>]*)>', re.S)
        match = pattern.search(text)
        if match:
            attrs = match.group('attrs')
            text = text[:match.start()] + f'<EnhancedContentRenderer{attrs}>' + text[match.end():]
    if '<EnhancedContentRenderer' not in text:
        raise RuntimeError(f'{rel}: structured content renderer was not replaced')
    enhanced_pattern = re.compile(r'<EnhancedContentRenderer\b(?P<attrs>[^>]*)>', re.S)
    enhanced_match = enhanced_pattern.search(text)
    if not enhanced_match:
        raise RuntimeError(f'{rel}: EnhancedContentRenderer opening tag not found')
    attrs = enhanced_match.group('attrs')
    if ':source-html="item.content"' not in attrs and ":source-html='item.content'" not in attrs:
        opening = enhanced_match.group(0)
        if re.search(r'/\s*>$', opening):
            replacement = re.sub(r'\s*/\s*>$', ' :source-html="item.content" />', opening)
        else:
            replacement = opening[:-1] + ' :source-html="item.content">'
        text = text[:enhanced_match.start()] + replacement + text[enhanced_match.end():]
    bottom_block = '.bottom-float-container {\n    position: relative;\n    display: flex;\n    justify-content: center;\n    width: 100%;\n    margin: 20px 0 24px;\n    pointer-events: none;\n    z-index: 20;\n}'
    text = _v2_replace_style_block(text, '.bottom-float-container', bottom_block)
    glass_block = '.glass {\n    background: transparent;\n    backdrop-filter: blur(10px);\n    -webkit-backdrop-filter: blur(10px);\n}'
    text = _v2_replace_style_block(text, '.glass', glass_block)
    content_match = re.search('(\\.content-wrapper\\s*\\{)(.*?)(\\})', text, re.S)
    if not content_match:
        raise RuntimeError(f'{rel}: .content-wrapper style block not found')
    body = content_match.group(2)
    if re.search('padding-bottom\\s*:', body):
        body = re.sub('padding-bottom\\s*:\\s*[^;]+;', 'padding-bottom: 24px;', body)
    else:
        body += '\n    padding-bottom: 24px;'
    text = text[:content_match.start()] + content_match.group(1) + body + content_match.group(3) + text[content_match.end():]
    float_match = re.search('(\\.float-bar\\s*\\{)(.*?)(\\})', text, re.S)
    if not float_match:
        raise RuntimeError(f'{rel}: .float-bar style block not found')
    fbody = float_match.group(2)
    fbody = re.sub('background\\s*:\\s*[^;]+;', 'background: var(--f7-card-bg-color, var(--f7-page-bg-color, Canvas));', fbody, count=1)
    fbody = re.sub('border\\s*:\\s*1px\\s+solid\\s+[^;]+;', 'border: 1px solid var(--f7-border-color, rgba(127, 127, 127, 0.24));', fbody, count=1)
    if 'color:' not in fbody:
        fbody += '\n    color: var(--f7-text-color, CanvasText);'
    text = text[:float_match.start()] + float_match.group(1) + fbody + float_match.group(3) + text[float_match.end():]
    text = re.sub(r'\n(?::global\(\.dark\) \.bottom-float-container|:global\(\.dark \.bottom-float-container\)),\s*\n(?::global\(html\.dark\) \.bottom-float-container|:global\(html\.dark \.bottom-float-container\))\s*\{.*?\}\s*\n', '\n', text, flags=re.S)
    _v2_write(rel, text)

def _v2_patch_enhanced_renderer(rel: str) -> None:
    text = _v2_read(rel)
    if 'defineEmits' not in text:
        anchor = 'const props = defineProps({'
        if anchor not in text:
            raise RuntimeError(f'{rel}: defineProps anchor missing')
        text = text.replace(anchor, "const emit = defineEmits(['imageClick']);\n\n" + anchor, 1)
    if '<ContentRenderer' in text and '@imageClick=' not in text:
        pattern = re.compile('(<ContentRenderer\\s*\\n\\s*v-else-if="isLegacySupported\\(segment\\?\\.type\\)"\\s*\\n\\s*:segments="\\[segment\\]"\\s*)(/>)')
        if pattern.search(text):
            text = pattern.sub(lambda m: m.group(1) + '\n        @imageClick="emit(\'imageClick\', $event)"\n      ' + m.group(2), text, count=1)
        else:
            text = text.replace(':segments="[segment]"', ':segments="[segment]" @imageClick="emit(\'imageClick\', $event)"', 1)
    _v2_write(rel, text)

def _v2_patch_content_renderer(rel: str='src/components/ContentRenderer.vue') -> None:
    text = _v2_read(rel)
    text = _v2_ensure_script_import(text, "import { htmlToPlainText, safeHttpUrl } from '../utils/content-text.js';")
    old = "        return {\n            title: segment.card.title,\n            desc: extra.desc || extra.description || '',\n            url: extra.url || '#',\n            cover: segment.card.cover\n        };"
    new = "        return {\n            title: htmlToPlainText(segment.card.title || extra.title || ''),\n            desc: htmlToPlainText(extra.desc || extra.description || segment.card.description || ''),\n            url: safeHttpUrl(extra.url || extra.href || segment.card.url || segment.card.href || '') || '#',\n            cover: segment.card.cover\n        };"
    if old in text:
        text = text.replace(old, new, 1)
    else:
        text = text.replace('title: segment.card.title,', "title: htmlToPlainText(segment.card.title || extra.title || ''),")
        text = text.replace("desc: extra.desc || extra.description || '',", "desc: htmlToPlainText(extra.desc || extra.description || segment.card.description || ''),")
        text = text.replace("url: extra.url || '#',", "url: safeHttpUrl(extra.url || extra.href || segment.card.url || segment.card.href || '') || '#',")
    text = text.replace("return { title: segment.card.title, desc: '', url: '#' };", "return { title: htmlToPlainText(segment.card.title || ''), desc: '', url: safeHttpUrl(segment.card.url || segment.card.href || '') || '#' };")
    text = text.replace("backgroundColor: '#f5f5f5'", "backgroundColor: 'var(--app-placeholder-bg)'")
    _v2_write(rel, text)

def _v2_patch_reference_renderer(rel: str) -> None:
    text = _v2_read(rel)
    text = text.replace("import { safeHttpUrl } from '../utils/content-text.js';", "import { htmlToPlainText, safeHttpUrl } from '../utils/content-text.js';")
    if 'import { htmlToPlainText, safeHttpUrl }' not in text:
        text = _v2_ensure_script_import(text, "import { htmlToPlainText, safeHttpUrl } from '../utils/content-text.js';")
    text = text.replace("return String(item?.text || '').trim();", "return htmlToPlainText(item?.text || '');")
    text = re.sub('<RenderStyledText\\s*\\n\\s*v-else\\s*\\n\\s*:text=\\"item\\?\\.text \\|\\| \'\'\\"\\s*\\n\\s*:marks=\\"item\\?\\.marks \\|\\| \\[\\]\\"\\s*\\n\\s*/>', '<span v-else>{{ cleanItemText(item) }}</span>', text, flags=re.S)
    item_href_pattern = re.compile('function itemHref\\(item\\) \\{.*?\\n\\}', re.S)
    if item_href_pattern.search(text):
        text = item_href_pattern.sub("function itemHref(item) {\n  const marks = Array.isArray(item?.marks) ? item.marks : [];\n  const markUrl = marks\n    .filter((mark) => mark?.type === 'link')\n    .map((mark) => mark?.link?.href || mark?.link?.url || mark?.href || mark?.url || '')\n    .find(Boolean);\n  const explicit = item?.link?.href || item?.link?.url || item?.href || item?.url || markUrl || '';\n  return safeHttpUrl(explicit) || findTextUrl(item?.text);\n}", text, count=1)
    text = text.replace('var(--f7-page-bg-color, #fff)', 'var(--app-surface-bg, Canvas)')
    text = text.replace('var(--f7-text-color, #111)', 'var(--f7-text-color, CanvasText)')
    _v2_write(rel, text)

def _v2_patch_render_styled_text(rel: str) -> None:
    text = _v2_read(rel)
    text = text.replace('mix-blend-mode: screen;', 'mix-blend-mode: difference;')
    text = text.replace(
        ':global(.dark) .styled-formula-image,\n:global(html.dark) .styled-formula-image {',
        ':global(.dark .styled-formula-image),\n:global(html.dark .styled-formula-image) {',
    )
    _v2_write(rel, text)

def _v2_patch_theme_fallbacks(rel: str) -> None:
    path = ROOT / rel
    if not path.exists():
        return
    text = _v2_read(rel)
    text = text.replace('var(--f7-page-bg-color, #fff)', 'var(--app-surface-bg, Canvas)')
    text = text.replace('var(--f7-text-color, #111)', 'var(--f7-text-color, CanvasText)')
    text = text.replace(
        ':global(.dark) .code-block-renderer,\n:global(html.dark) .code-block-renderer {',
        ':global(.dark .code-block-renderer),\n:global(html.dark .code-block-renderer) {',
    )
    _v2_write(rel, text)

def _v2_patch_template_copies() -> None:
    base = ROOT / 'deploy' / 'fork-templates' / 'article-display'
    if not base.exists():
        return
    enhanced = base / 'EnhancedContentRenderer.vue'
    if enhanced.exists():
        _v2_patch_enhanced_renderer(str(enhanced.relative_to(ROOT)))
    reference = base / 'ReferenceBlockRenderer.vue'
    if reference.exists():
        _v2_patch_reference_renderer(str(reference.relative_to(ROOT)))
    styled = base / 'RenderStyledText.vue'
    if styled.exists():
        _v2_patch_render_styled_text(str(styled.relative_to(ROOT)))
    for name in ['CodeBlockRenderer.vue', 'TableSegmentRenderer.vue', 'UnknownSegmentRenderer.vue']:
        component = base / name
        if component.exists():
            _v2_patch_theme_fallbacks(str(component.relative_to(ROOT)))


def _normalize_article_display_whitespace() -> None:
    """
    v1 may temporarily recreate obsolete patches which v2 removes later in
    the same apply run. Their removal can leave extra blank lines behind.
    Normalize only the two known closing-tag locations so repeated apply
    runs produce byte-for-byte identical output.
    """
    targets = (
        ('src/components/SearchPage.vue', '</script>'),
        ('src/components/ArticleDetail.vue', '</style>'),
    )

    for rel, closing_tag in targets:
        path = ROOT / rel
        if not path.exists():
            continue

        original = path.read_text(encoding='utf-8')

        # Keep exactly one blank line before the relevant closing tag.
        # 3+ newline characters => 2 newline characters.
        pattern = (
            r'\n(?:[ \t]*\n){2,}'
            + r'(?=[ \t]*'
            + re.escape(closing_tag)
            + r')'
        )

        normalized = re.sub(
            pattern,
            '\n\n',
            original,
        )

        if normalized != original:
            path.write_text(
                normalized,
                encoding='utf-8',
            )


# END article display v2 integrated

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


    # Permanent v2 pass; no standalone hotfix script is required.
    _v2_patch_search_page()
    _v2_patch_feed_card()
    _v2_patch_user_profile()
    _v2_patch_article_detail()
    patch_screenshot_export()
    patch_screenshot_dependency()
    patch_formula_dependency()
    patch_screenshot_csp()
    _v2_patch_enhanced_renderer('src/components/EnhancedContentRenderer.vue')
    _v2_patch_content_renderer()
    _v2_patch_reference_renderer('src/components/ReferenceBlockRenderer.vue')
    _v2_patch_render_styled_text('src/components/RenderStyledText.vue')
    _v2_patch_theme_fallbacks('src/components/CodeBlockRenderer.vue')
    _v2_patch_theme_fallbacks('src/components/TableSegmentRenderer.vue')
    _v2_patch_theme_fallbacks('src/components/UnknownSegmentRenderer.vue')
    _v2_patch_template_copies()

    _normalize_article_display_whitespace()
    print('article display fix applied')
    print('search Enter patched:', ', '.join(search_patched))


if __name__ == '__main__':
    main()
