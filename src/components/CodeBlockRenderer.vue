<template>
  <div class="code-block-renderer">
    <div class="code-block-toolbar">
      <span class="code-language">{{ displayLanguage }}</span>
      <button class="code-copy" type="button" @click="copyCode">
        {{ copied ? '已复制' : '复制' }}
      </button>
    </div>
    <pre class="code-pre"><code :class="`language-${normalizedLanguage}`" v-html="highlightedCode"></code></pre>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  code: {
    type: String,
    default: '',
  },
  language: {
    type: String,
    default: '',
  },
});

const copied = ref(false);
let copiedTimer = null;

const LANGUAGE_ALIASES = {
  'c++': 'cpp',
  cxx: 'cpp',
  cc: 'cpp',
  hpp: 'cpp',
  h: 'cpp',
  js: 'javascript',
  jsx: 'javascript',
  ts: 'typescript',
  tsx: 'typescript',
  py: 'python',
  sh: 'bash',
  shell: 'bash',
  zsh: 'bash',
  yml: 'yaml',
  html: 'xml',
  vue: 'xml',
  md: 'markdown',
  text: 'plaintext',
  txt: 'plaintext',
};

const KEYWORDS = {
  cpp: new Set(('alignas alignof and and_eq asm atomic_cancel atomic_commit atomic_noexcept auto bitand bitor bool break case catch char char16_t char32_t class compl concept const consteval constexpr constinit const_cast continue co_await co_return co_yield decltype default delete do double dynamic_cast else enum explicit export extern false float for friend goto if inline int long mutable namespace new noexcept not not_eq nullptr operator or or_eq private protected public register reinterpret_cast requires return short signed sizeof static static_assert static_cast struct switch template this thread_local throw true try typedef typeid typename union unsigned using virtual void volatile wchar_t while xor xor_eq').split(/\s+/)),
  c: new Set(('auto break case char const continue default do double else enum extern float for goto if int long register return short signed sizeof static struct switch typedef union unsigned void volatile while _Bool _Complex _Imaginary').split(/\s+/)),
  javascript: new Set(('await break case catch class const continue debugger default delete do else export extends false finally for from function get if import in instanceof let new null of return set static super switch this throw true try typeof undefined var void while with yield async').split(/\s+/)),
  typescript: new Set(('abstract any as asserts async await bigint boolean break case catch class const constructor continue declare default delete do else enum export extends false finally for from function get if implements import in infer instanceof interface is keyof let module namespace never new null number object of override private protected public readonly require return satisfies set static string super switch symbol this throw true try type typeof undefined unique unknown var void while with yield').split(/\s+/)),
  python: new Set(('and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield match case').split(/\s+/)),
  java: new Set(('abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new null package private protected public return short static strictfp super switch synchronized this throw throws transient true try void volatile while false').split(/\s+/)),
  go: new Set(('break default func interface select case defer go map struct chan else goto package switch const fallthrough if range type continue for import return var true false nil').split(/\s+/)),
  rust: new Set(('as async await break const continue crate dyn else enum extern false fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait true type unsafe use where while').split(/\s+/)),
  bash: new Set(('case do done elif else esac fi for function if in select then time until while coproc true false').split(/\s+/)),
  sql: new Set(('add all alter and any as asc backup between by case check column constraint create database default delete desc distinct drop exec exists foreign from full group having in index inner insert into is join key left like limit not null or order outer primary procedure right rownum select set table top truncate union unique update values view where with').split(/\s+/)),
  json: new Set(['true', 'false', 'null']),
  yaml: new Set(['true', 'false', 'null', 'yes', 'no', 'on', 'off']),
};

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function span(kind, value) {
  return `<span class="tok tok-${kind}">${escapeHtml(value)}</span>`;
}

function normalizeLanguage(value) {
  const raw = String(value || '').trim().toLowerCase();
  return LANGUAGE_ALIASES[raw] || raw || 'plaintext';
}

function configFor(language) {
  const lang = normalizeLanguage(language);
  return {
    lang,
    keywords: KEYWORDS[lang] || new Set(),
    lineCommentSlash: ['cpp', 'c', 'javascript', 'typescript', 'java', 'go', 'rust'].includes(lang),
    lineCommentHash: ['python', 'bash', 'yaml'].includes(lang),
    blockComment: ['cpp', 'c', 'javascript', 'typescript', 'java', 'go', 'rust', 'css'].includes(lang),
    preprocessor: ['cpp', 'c'].includes(lang),
  };
}

function highlightMarkup(code) {
  const escaped = escapeHtml(code);
  return escaped.replace(
    /(&lt;\/?)([A-Za-z][\w:-]*)([\s\S]*?)(\/?&gt;)/g,
    (_, open, tag, attrs, close) => {
      const highlightedAttrs = attrs.replace(
        /([:\w-]+)(\s*=\s*)(&quot;.*?&quot;|&#39;.*?&#39;|[^\s]+)/g,
        '<span class="tok tok-attr">$1</span>$2<span class="tok tok-string">$3</span>',
      );
      return `<span class="tok tok-punctuation">${open}</span>`
        + `<span class="tok tok-tag">${tag}</span>`
        + highlightedAttrs
        + `<span class="tok tok-punctuation">${close}</span>`;
    },
  );
}

function highlightPlain(code, language) {
  const cfg = configFor(language);
  if (cfg.lang === 'plaintext') return escapeHtml(code);
  if (cfg.lang === 'xml') return highlightMarkup(code);

  const source = String(code ?? '');
  const out = [];
  let i = 0;
  let lineStart = true;

  const push = (kind, value) => out.push(kind ? span(kind, value) : escapeHtml(value));

  while (i < source.length) {
    const ch = source[i];
    const next = source[i + 1] || '';

    if (ch === '\n') {
      push(null, ch);
      i += 1;
      lineStart = true;
      continue;
    }

    if (cfg.preprocessor && lineStart && ch === '#') {
      const end = source.indexOf('\n', i);
      const stop = end === -1 ? source.length : end;
      push('meta', source.slice(i, stop));
      i = stop;
      lineStart = false;
      continue;
    }

    if (cfg.lineCommentSlash && ch === '/' && next === '/') {
      const end = source.indexOf('\n', i);
      const stop = end === -1 ? source.length : end;
      push('comment', source.slice(i, stop));
      i = stop;
      lineStart = false;
      continue;
    }

    if (cfg.lineCommentHash && ch === '#') {
      const end = source.indexOf('\n', i);
      const stop = end === -1 ? source.length : end;
      push('comment', source.slice(i, stop));
      i = stop;
      lineStart = false;
      continue;
    }

    if (cfg.blockComment && ch === '/' && next === '*') {
      const end = source.indexOf('*/', i + 2);
      const stop = end === -1 ? source.length : end + 2;
      const value = source.slice(i, stop);
      push('comment', value);
      lineStart = value.endsWith('\n');
      i = stop;
      continue;
    }

    if (ch === '"' || ch === "'" || (ch === '`' && ['javascript', 'typescript'].includes(cfg.lang))) {
      const quote = ch;
      let j = i + 1;
      while (j < source.length) {
        if (source[j] === '\\') {
          j += 2;
          continue;
        }
        if (source[j] === quote) {
          j += 1;
          break;
        }
        j += 1;
      }
      push('string', source.slice(i, j));
      i = j;
      lineStart = false;
      continue;
    }

    if (/\d/.test(ch) && (i === 0 || !/[\w$]/.test(source[i - 1]))) {
      const match = source.slice(i).match(/^(?:0[xX][0-9a-fA-F]+|0[bB][01]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?:[uUlLfF]+)?/);
      if (match) {
        push('number', match[0]);
        i += match[0].length;
        lineStart = false;
        continue;
      }
    }

    if (/[A-Za-z_$]/.test(ch)) {
      const match = source.slice(i).match(/^[A-Za-z_$][\w$]*/);
      const word = match ? match[0] : ch;
      if (cfg.keywords.has(word)) {
        push(['true', 'false', 'null', 'None', 'True', 'False', 'nil'].includes(word) ? 'literal' : 'keyword', word);
      } else if (/^[A-Z][A-Za-z0-9_]*$/.test(word)) {
        push('type', word);
      } else {
        push(null, word);
      }
      i += word.length;
      lineStart = false;
      continue;
    }

    if (/[+\-*\/%=&|!<>?:~^]/.test(ch)) {
      let j = i + 1;
      while (j < source.length && /[+\-*\/%=&|!<>?:~^]/.test(source[j])) j += 1;
      push('operator', source.slice(i, j));
      i = j;
      lineStart = false;
      continue;
    }

    push(null, ch);
    if (!/\s/.test(ch)) lineStart = false;
    i += 1;
  }

  return out.join('');
}

const normalizedLanguage = computed(() => normalizeLanguage(props.language));
const displayLanguage = computed(() => {
  const lang = normalizedLanguage.value;
  if (lang === 'plaintext') return '代码';
  return lang.toUpperCase();
});
const highlightedCode = computed(() => highlightPlain(props.code, normalizedLanguage.value));

async function copyCode() {
  const text = props.code || '';
  let ok = false;
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      ok = true;
    }
  } catch {
    ok = false;
  }

  if (!ok && typeof document !== 'undefined') {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    textarea.remove();
  }

  if (ok) {
    copied.value = true;
    if (copiedTimer) clearTimeout(copiedTimer);
    copiedTimer = setTimeout(() => {
      copied.value = false;
    }, 1400);
  }
}
</script>

<style scoped>
.code-block-renderer {
  margin: 1em 0;
  border: 1px solid color-mix(in srgb, var(--f7-text-color, CanvasText) 12%, transparent);
  border-radius: 10px;
  overflow: hidden;
  background: color-mix(in srgb, var(--app-surface-bg, Canvas) 94%, var(--f7-text-color, CanvasText) 6%);
  color: var(--f7-text-color, CanvasText);
  --code-comment: #6a737d;
  --code-keyword: #a626a4;
  --code-string: #50a14f;
  --code-number: #986801;
  --code-type: #4078f2;
  --code-operator: #0184bc;
  --code-meta: #986801;
  --code-tag: #e45649;
  --code-attr: #986801;
  --code-punctuation: #6a737d;
}

:global(.dark .code-block-renderer),
:global(html.dark .code-block-renderer) {
  --code-comment: #7f848e;
  --code-keyword: #c678dd;
  --code-string: #98c379;
  --code-number: #d19a66;
  --code-type: #61afef;
  --code-operator: #56b6c2;
  --code-meta: #e5c07b;
  --code-tag: #e06c75;
  --code-attr: #d19a66;
  --code-punctuation: #abb2bf;
}

.code-block-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 34px;
  padding: 0 10px;
  border-bottom: 1px solid color-mix(in srgb, var(--f7-text-color, CanvasText) 10%, transparent);
  color: color-mix(in srgb, var(--f7-text-color, CanvasText) 70%, transparent);
  font-size: 12px;
}

.code-language {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  letter-spacing: 0.04em;
}

.code-copy {
  appearance: none;
  border: 0;
  border-radius: 6px;
  padding: 4px 8px;
  color: inherit;
  background: color-mix(in srgb, var(--f7-text-color, CanvasText) 8%, transparent);
  cursor: pointer;
}

.code-copy:hover {
  background: color-mix(in srgb, var(--f7-text-color, CanvasText) 13%, transparent);
}

.code-pre {
  margin: 0;
  padding: 14px 16px;
  overflow-x: auto;
  tab-size: 4;
  white-space: pre;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 13px;
  line-height: 1.62;
}

.code-pre code {
  font: inherit;
  color: inherit;
  background: transparent;
}

.code-pre :deep(.tok-comment) { color: var(--code-comment); font-style: italic; }
.code-pre :deep(.tok-keyword) { color: var(--code-keyword); font-weight: 600; }
.code-pre :deep(.tok-string) { color: var(--code-string); }
.code-pre :deep(.tok-number),
.code-pre :deep(.tok-literal) { color: var(--code-number); }
.code-pre :deep(.tok-type) { color: var(--code-type); }
.code-pre :deep(.tok-operator) { color: var(--code-operator); }
.code-pre :deep(.tok-meta) { color: var(--code-meta); }
.code-pre :deep(.tok-tag) { color: var(--code-tag); }
.code-pre :deep(.tok-attr) { color: var(--code-attr); }
.code-pre :deep(.tok-punctuation) { color: var(--code-punctuation); }
</style>
