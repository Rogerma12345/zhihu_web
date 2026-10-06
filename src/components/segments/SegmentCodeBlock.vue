<script setup>
import { computed, ref } from 'vue';
import { settings } from '@/core/settings.js';
import { copyText } from '@/utils/share.js';
import { highlightCode, normalizeCodeLanguage } from '@/utils/code-highlight.js';

const props = defineProps({ segment: Object });
const copied = ref(false);
let copiedTimer = null;

const block = computed(() => props.segment?.code_block || {});
const code = computed(() => String(block.value.content || ''));
const language = computed(() => normalizeCodeLanguage(
    block.value.language || block.value.lang || block.value.code_language || '',
));
const languageLabel = computed(() => language.value === 'plaintext' ? '代码' : language.value.toUpperCase());
const highlightedCode = computed(() => highlightCode(code.value, language.value));

async function copyCode() {
    if (!await copyText(code.value)) return;
    copied.value = true;
    if (copiedTimer) clearTimeout(copiedTimer);
    copiedTimer = setTimeout(() => {
        copied.value = false;
    }, 1400);
}
</script>

<template>
    <div class="code-block-renderer" :class="{ 'code-wrap': settings.codeWrap }">
        <div class="code-block-toolbar">
            <span class="code-language">{{ languageLabel }}</span>
            <button class="code-copy" type="button" @click="copyCode">
                {{ copied ? '已复制' : '复制' }}
            </button>
        </div>
        <pre class="code-pre"><code v-html="highlightedCode"></code></pre>
    </div>
</template>

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
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    letter-spacing: 0.04em;
}

.code-copy {
    appearance: none;
    width: auto;
    min-width: 0;
    flex: 0 0 auto;
    border: 0;
    border-radius: 6px;
    padding: 4px 8px;
    color: inherit;
    background: color-mix(in srgb, var(--f7-text-color, CanvasText) 8%, transparent);
    cursor: pointer;
    white-space: nowrap;
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

.code-wrap .code-pre {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
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
