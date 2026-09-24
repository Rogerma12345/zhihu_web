<template>
  <aside v-if="items.length" class="reference-block" aria-label="引用">
    <div class="reference-label">引用</div>
    <div
      v-for="(item, index) in items"
      :key="index"
      class="reference-item"
      :style="indentStyle(item)"
    >
      <a
        v-if="itemHref(item)"
        class="reference-link external prevent-router"
        :href="itemHref(item)"
        target="_blank"
        rel="noopener noreferrer"
      >{{ cleanItemText(item) }}</a>
      <span v-else>{{ cleanItemText(item) }}</span>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue';
import RenderStyledText from './RenderStyledText.vue';
import { htmlToPlainText, safeHttpUrl } from '../utils/content-text.js';

const props = defineProps({
  block: {
    type: Object,
    default: () => ({}),
  },
});

const items = computed(() => (
  Array.isArray(props.block?.items) ? props.block.items : []
));

function cleanItemText(item) {
  return htmlToPlainText(item?.text || '');
}

function findTextUrl(text) {
  const match = String(text || '').match(/https?:\/\/[^\s<>()]+/i);
  return match ? safeHttpUrl(match[0]) : '';
}

function itemHref(item) {
  const marks = Array.isArray(item?.marks) ? item.marks : [];
  const markUrl = marks
    .filter((mark) => mark?.type === 'link')
    .map((mark) => mark?.link?.href || mark?.link?.url || mark?.href || mark?.url || '')
    .find(Boolean);
  const explicit = item?.link?.href || item?.link?.url || item?.href || item?.url || markUrl || '';
  return safeHttpUrl(explicit) || findTextUrl(item?.text);
}

function indentStyle(item) {
  const level = Math.min(6, Math.max(0, Number(item?.indent_level) || 0));
  return { marginInlineStart: `${level * 0.75}rem` };
}
</script>

<style scoped>
.reference-block {
  margin: 1em 0;
  padding: 0.75em 0.9em;
  border-inline-start: 3px solid color-mix(in srgb, var(--f7-theme-color, #0c7ff2) 58%, transparent);
  border-radius: 0 8px 8px 0;
  background: color-mix(in srgb, var(--app-surface-bg, Canvas) 94%, var(--f7-text-color, CanvasText) 6%);
  color: var(--f7-text-color, CanvasText);
}

.reference-label {
  margin-bottom: 0.35em;
  color: color-mix(in srgb, var(--f7-text-color, CanvasText) 58%, transparent);
  font-size: 0.78em;
}

.reference-item + .reference-item {
  margin-top: 0.35em;
}

.reference-link {
  color: var(--f7-theme-color, #0c7ff2);
  text-decoration: none;
  overflow-wrap: anywhere;
}

.reference-link:hover {
  text-decoration: underline;
}
</style>
