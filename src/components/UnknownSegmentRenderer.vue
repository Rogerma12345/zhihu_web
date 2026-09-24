<template>
  <div class="unknown-segment" :data-segment-type="segment?.type || 'unknown'">
    <RenderStyledText
      v-if="fallback.text"
      :text="fallback.text"
      :marks="fallback.marks"
    />
    <a
      v-else-if="fallback.url"
      class="unknown-link external prevent-router"
      :href="fallback.url"
      target="_blank"
      rel="noopener noreferrer"
    >{{ fallback.url }}</a>
    <span v-else class="unknown-placeholder">暂不支持的内容类型：{{ segment?.type || 'unknown' }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import RenderStyledText from './RenderStyledText.vue';
import { safeHttpUrl } from '../utils/content-text.js';

const props = defineProps({
  segment: {
    type: Object,
    default: () => ({}),
  },
});

function getPayload(segment) {
  if (!segment || typeof segment !== 'object') return {};
  const typed = segment.type && segment[segment.type];
  return typed && typeof typed === 'object' ? typed : segment;
}

const fallback = computed(() => {
  const payload = getPayload(props.segment);
  const text = [
    payload?.text,
    payload?.content,
    payload?.title,
    payload?.name,
    payload?.caption,
    payload?.description,
  ].find((value) => typeof value === 'string' && value.trim());

  const rawUrl = [payload?.url, payload?.href, props.segment?.url]
    .find((value) => typeof value === 'string' && value.trim());

  return {
    text: text || '',
    marks: Array.isArray(payload?.marks) ? payload.marks : [],
    url: safeHttpUrl(rawUrl || ''),
  };
});
</script>

<style scoped>
.unknown-segment {
  margin: 0.75em 0;
  color: var(--f7-text-color, inherit);
}

.unknown-placeholder {
  display: inline-block;
  padding: 0.45em 0.65em;
  border: 1px dashed color-mix(in srgb, var(--f7-text-color, CanvasText) 24%, transparent);
  border-radius: 6px;
  color: color-mix(in srgb, var(--f7-text-color, CanvasText) 58%, transparent);
  font-size: 0.86em;
}

.unknown-link {
  color: var(--f7-theme-color, #0c7ff2);
  overflow-wrap: anywhere;
}
</style>
